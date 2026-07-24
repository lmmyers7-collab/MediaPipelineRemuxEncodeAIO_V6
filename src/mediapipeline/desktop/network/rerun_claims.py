"""Coordinator-owned claim state for Network CSV rerun rows."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from collections.abc import Callable, Mapping

from mediapipeline.core.kernel.config_key_groups import KEY_COORDINATOR_MAX_JOB_RETRIES
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.network.url_policy import redact_network_secret_text
from mediapipeline.core.processes.rerun_results import (
    NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION,
    apply_network_rerun_destination_policy,
)
from mediapipeline.core.processes.source_probe import (
    run_source_probe,
    source_content_hash_timeout_seconds,
)

from .protocol import ClaimResponse
from .registry import normalize_source_identity

NETWORK_RERUN_BATCH_SCHEMA_VERSION = "desktop_rerun_network_batch.v1"
NETWORK_RERUN_ROW_JOB_KIND = "csv_rerun_row"
NETWORK_RERUN_REDUCER_SCHEMA_VERSION = "desktop_rerun_network_result_reduction.v1"
NETWORK_RERUN_ACTIVE_STATUSES = {"active", "running", "stopping", "stopped_after_current", "paused"}
NETWORK_RERUN_DEFAULT_RETRY_LIMIT = 3
NETWORK_RERUN_MAX_RETRY_LIMIT = 100
NETWORK_RERUN_RETRY_BASE_SECONDS = 15
NETWORK_RERUN_RETRY_MAX_SECONDS = 15 * 60
NETWORK_RERUN_HISTORY_LIMIT = 12
NETWORK_RERUN_SOURCE_PROBE_TIMEOUT_SECONDS = 2.0
NETWORK_RERUN_FFPROBE_TIMEOUT_SECONDS = 5.0
NETWORK_RERUN_SOURCE_SAMPLE_BYTES = 1024 * 1024
NETWORK_RERUN_ARTIFACT_MAX_BYTES = 1024 * 1024
NETWORK_RERUN_CONTENT_SHA256_ALGORITHM = "sha256-full-file"
NETWORK_RERUN_BATCH_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
NETWORK_RERUN_TERMINAL_ROW_STATUSES = {
    "complete",
    "completed",
    "destination_policy_applied",
    "destination_policy_failed",
    "failed",
    "pending_publish",
    "published_non_overlap",
    "published_replace_final",
    "retry_exhausted",
    "review_required",
    "review_workspace",
    "skipped",
    "worker_failed_pending_reduction",
    "worker_review_pending_reduction",
}
NETWORK_RERUN_REVIEW_ROW_STATUSES = {
    "review_required",
    "review_workspace",
    "worker_review_pending_reduction",
}
NETWORK_RERUN_FAILED_ROW_STATUSES = {
    "destination_policy_failed",
    "failed",
    "retry_exhausted",
    "worker_failed_pending_reduction",
}

# A single process-local critical section protects every Network batch JSON
# read-modify-write transaction. Atomic os.replace prevents torn files, while
# this lock prevents two coordinator threads from replacing each other's rows.
_NETWORK_RERUN_BATCH_STATE_LOCK = threading.RLock()
_NETWORK_RERUN_ACTIVE_DESTINATION_OPERATIONS: set[str] = set()


@dataclass(frozen=True)
class NetworkRerunClaimLease:
    response: ClaimResponse
    state_path: Path
    previous_payload: dict[str, Any]
    worker_id: str


def network_rerun_state_root_for_app(app: Any) -> Path | None:
    resolved = getattr(app, "resolved", None)
    if resolved is None:
        return None
    state_root = getattr(resolved, "state_root", None)
    if state_root is None and getattr(resolved, "local_base", None) is not None:
        state_root = Path(resolved.local_base) / "State"
    if state_root is None:
        return None
    return Path(state_root) / "Rerun" / "Network"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return 0


def _is_sha256_hex(value: str) -> bool:
    normalized = str(value or "").strip().casefold()
    return len(normalized) == 64 and all(character in "0123456789abcdef" for character in normalized)


def _read_state(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Network CSV rerun state root must be a JSON object: {path}")
    if str(payload.get("schema_version") or "") != NETWORK_RERUN_BATCH_SCHEMA_VERSION:
        raise RuntimeError(f"Network CSV rerun state schema mismatch: {path}")
    return payload


def _write_state(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(
            json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="",
        )
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _row_source_path(row: Mapping[str, Any]) -> str:
    return str(row.get("source_path") or "").strip()


def _row_library_id(row: Mapping[str, Any]) -> str:
    mapping = row.get("source_mapping")
    if isinstance(mapping, Mapping):
        mapped = str(mapping.get("library_id") or "").strip()
        if mapped:
            return mapped
    return str(row.get("library_id") or "").strip()


def _row_relative_path(row: Mapping[str, Any]) -> str:
    mapping = row.get("source_mapping")
    if isinstance(mapping, Mapping):
        mapped = str(mapping.get("relative_path") or "").strip()
        if mapped:
            return mapped
    return ""


def _accessible_library_allowed(row: Mapping[str, Any], accessible_library_ids: list[str] | None) -> bool:
    if accessible_library_ids is None:
        return True
    library_id = _row_library_id(row)
    if not library_id:
        return True
    allowed = {str(item).casefold() for item in accessible_library_ids if str(item).strip()}
    return library_id.casefold() in allowed


def _row_output_handoff(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("output_handoff")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _configured_retry_limit(app: Any) -> int:
    resolved = getattr(app, "resolved", None)
    config = getattr(resolved, "config_data", {}) if resolved is not None else {}
    raw = (
        config.get(KEY_COORDINATOR_MAX_JOB_RETRIES, NETWORK_RERUN_DEFAULT_RETRY_LIMIT)
        if isinstance(config, Mapping)
        else NETWORK_RERUN_DEFAULT_RETRY_LIMIT
    )
    try:
        configured = int(raw)
    except (TypeError, ValueError):
        configured = NETWORK_RERUN_DEFAULT_RETRY_LIMIT
    return max(1, min(configured, NETWORK_RERUN_MAX_RETRY_LIMIT))


def _row_retry_limit(
    row: Mapping[str, Any],
    *,
    default: int = NETWORK_RERUN_DEFAULT_RETRY_LIMIT,
) -> int:
    configured = _safe_int(row.get("retry_limit"))
    if configured <= 0:
        configured = default
    return max(1, min(configured, NETWORK_RERUN_MAX_RETRY_LIMIT))


def _retry_after_seconds(retry_count: int) -> int:
    exponent = min(max(0, retry_count - 1), 6)
    return min(NETWORK_RERUN_RETRY_MAX_SECONDS, NETWORK_RERUN_RETRY_BASE_SECONDS * (2**exponent))


def _retry_is_due(row: Mapping[str, Any]) -> bool:
    if str(row.get("status") or "").strip() != "retry_scheduled":
        return True
    raw = str(row.get("next_retry_at_utc") or "").strip()
    if not raw:
        return False
    try:
        next_retry = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if next_retry.tzinfo is None:
            next_retry = next_retry.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return False
    return datetime.now(UTC) >= next_retry


def _parse_utc(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _killable_source_probe(
    operation: str,
    path: Path,
    *,
    timeout_seconds: float | None = None,
    max_bytes: int = NETWORK_RERUN_ARTIFACT_MAX_BYTES,
) -> dict[str, Any]:
    return run_source_probe(
        operation,
        path,
        timeout_seconds=(
            NETWORK_RERUN_SOURCE_PROBE_TIMEOUT_SECONDS
            if timeout_seconds is None
            else timeout_seconds
        ),
        sample_bytes=NETWORK_RERUN_SOURCE_SAMPLE_BYTES,
        max_bytes=max_bytes,
    )


def _bounded_path_stat(path: Path) -> dict[str, Any]:
    return _killable_source_probe("stat", path)


def _bounded_file_sha256(path: Path, *, size_bytes: int = 0) -> str:
    return str(
        _killable_source_probe(
            "sha256",
            path,
            timeout_seconds=source_content_hash_timeout_seconds(size_bytes),
        ).get("digest")
        or ""
    )


def _bounded_sample_sha256(path: Path, size: int) -> str:
    del size
    return str(_killable_source_probe("sample_sha256", path).get("digest") or "")


def _ffprobe_candidates(app: Any) -> tuple[list[Path], bool]:
    resolved = getattr(app, "resolved", None)
    if resolved is None:
        return [], False
    config = getattr(resolved, "config_data", None)
    configured = ""
    if isinstance(config, Mapping):
        lowered = {str(key).casefold(): value for key, value in config.items()}
        configured = str(lowered.get("ffprobepath") or "").strip()
    candidates: list[Path] = [Path(configured)] if configured else []
    pipeline_path = getattr(resolved, "pipeline_path", None)
    if pipeline_path:
        pipeline_root = Path(pipeline_path).parent
        if pipeline_root.name.casefold() == "entrypoints":
            pipeline_root = pipeline_root.parent
        candidates.extend(
            (
                pipeline_root / "tools" / "ffmpeg" / "bin" / "ffprobe.exe",
                pipeline_root / "tools" / "ffmpeg" / "bin" / "ffprobe",
            )
        )
    workspace_root = getattr(resolved, "workspace_root", None)
    if workspace_root:
        candidates.extend(
            (
                Path(workspace_root) / "ops" / "pipeline" / "tools" / "ffmpeg" / "bin" / "ffprobe.exe",
                Path(workspace_root) / "ops" / "pipeline" / "tools" / "ffmpeg" / "bin" / "ffprobe",
            )
        )
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key and key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped, bool(configured)


def _resolve_ffprobe_path(app: Any) -> tuple[Path | None, str]:
    candidates, configured = _ffprobe_candidates(app)
    for index, candidate in enumerate(candidates):
        try:
            candidate_stat = _bounded_path_stat(candidate)
        except FileNotFoundError:
            if configured and index == 0:
                return None, "configured_ffprobe_missing"
            continue
        except TimeoutError:
            return None, "ffprobe_path_probe_timeout"
        except OSError:
            if configured and index == 0:
                return None, "configured_ffprobe_unreachable"
            continue
        if candidate_stat.get("kind") == "file":
            return candidate, ""
        if configured and index == 0:
            return None, "configured_ffprobe_not_a_file"
    return None, "ffprobe_unavailable"


def _ffprobe_identity_fields(ffprobe: Path, source: Path) -> tuple[float, str]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name",
            "-of",
            "json",
            "--",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(0.1, float(NETWORK_RERUN_FFPROBE_TIMEOUT_SECONDS)),
        check=False,
        creationflags=creationflags,
    )
    if completed.returncode != 0:
        raise OSError(f"ffprobe exited with {completed.returncode}")
    payload = json.loads(completed.stdout or "{}")
    duration = 0.0
    try:
        duration = float((payload.get("format") or {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    codec = ""
    for stream in payload.get("streams") or []:
        if isinstance(stream, Mapping) and str(stream.get("codec_type") or "") == "video":
            codec = str(stream.get("codec_name") or "").strip().casefold()
            break
    return duration, codec


def _source_identity_v2(
    *,
    app: Any,
    source: Path,
    source_size: int,
    algorithm: str,
) -> tuple[str, str]:
    normalized = str(algorithm or "").strip().casefold()
    if normalized in {"sha256", "full-sha256", "sha256-full-file"}:
        try:
            return _bounded_file_sha256(source, size_bytes=source_size), ""
        except TimeoutError:
            return "", "source_identity_probe_timeout"
        except OSError:
            return "", "source_identity_read_failed"
    if normalized not in {"", "identity-v2", "rerun_csv_v2", "size-duration-codec-sample-v1"}:
        return "", "source_identity_algorithm_unsupported"
    try:
        sample_hash = _bounded_sample_sha256(source, source_size)
    except TimeoutError:
        return "", "source_identity_probe_timeout"
    except OSError:
        return "", "source_identity_read_failed"
    ffprobe, ffprobe_error = _resolve_ffprobe_path(app)
    if ffprobe is None:
        return "", ffprobe_error or "ffprobe_unavailable"
    try:
        duration, codec = _ffprobe_identity_fields(ffprobe, source)
    except subprocess.TimeoutExpired:
        return "", "source_identity_ffprobe_timeout"
    except (OSError, ValueError, json.JSONDecodeError):
        return "", "source_identity_ffprobe_failed"
    duration_text = f"{round(duration, 3):.3f}".rstrip("0").rstrip(".") or "0"
    fingerprint = (
        f"{source_size}|duration={duration_text}|vcodec={codec.casefold()}|sample={sample_hash}"
    )
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(), ""


def _source_root_for_replay(row: Mapping[str, Any], *, app: Any, source: Path) -> Path:
    resolved = getattr(app, "resolved", None)
    config = getattr(resolved, "config_data", None)
    library_id = _row_library_id(row).casefold()
    candidates: list[Path] = []

    def add_candidate(value: Any) -> None:
        text = str(value or "").strip()
        if text:
            candidates.append(Path(os.path.expandvars(text)).expanduser())

    if resolved is not None:
        add_candidate(getattr(resolved, "source_movies", None))
        add_candidate(getattr(resolved, "source_tv", None))
    if isinstance(config, Mapping):
        lowered = {str(key).casefold(): value for key, value in config.items()}
        add_candidate(lowered.get("sourcemovies"))
        add_candidate(lowered.get("sourcetv"))
        profiles = lowered.get("libraryprofiles")
        if library_id and isinstance(profiles, list):
            for profile in profiles:
                if not isinstance(profile, Mapping):
                    continue
                profile_lowered = {str(key).casefold(): value for key, value in profile.items()}
                if str(profile_lowered.get("id") or "").strip().casefold() != library_id:
                    continue
                root_text = str(
                    profile_lowered.get("source_path")
                    or profile_lowered.get("source_root")
                    or ""
                ).strip()
                if root_text:
                    add_candidate(root_text)
    try:
        source_key = os.path.normcase(os.path.abspath(str(source)))
    except (OSError, ValueError):
        source_key = os.path.normcase(str(source))
    matches: list[tuple[int, int, Path]] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            candidate_key = os.path.normcase(os.path.abspath(str(candidate)))
            if candidate_key in seen or os.path.commonpath([source_key, candidate_key]) != candidate_key:
                continue
        except (OSError, ValueError):
            continue
        seen.add(candidate_key)
        matches.append((len(candidate.parts), len(candidate_key), candidate))
    if matches:
        return max(matches, key=lambda item: (item[0], item[1]))[2]
    anchor = str(source.anchor or "").strip()
    return Path(anchor) if anchor else source.parent


def _source_replay_evidence(row: Mapping[str, Any], *, app: Any) -> dict[str, Any]:
    source_path = _row_source_path(row)
    path = Path(source_path) if source_path else None
    expected_size = _safe_int(row.get("source_size"))
    expected_mtime = _parse_utc(row.get("source_mtime_utc"))
    expected_identity_v2 = str(row.get("source_identity_v2") or "").strip()
    identity_algorithm = str(row.get("source_identity_v2_algorithm") or "").strip()
    expected_content_sha256 = str(row.get("source_content_sha256") or "").strip()
    content_sha256_algorithm = str(row.get("source_content_sha256_algorithm") or "").strip()
    exists = False
    current_size = 0
    current_mtime: datetime | None = None
    observed_identity_v2 = ""
    observed_content_sha256 = ""
    mismatches: list[str] = []
    probe_error = ""
    source_root = ""
    root_reachable = False
    availability_code = "source_available"
    if path is None:
        mismatches.append("source_path_missing")
        availability_code = "source_missing"
    else:
        root = _source_root_for_replay(row, app=app, source=path)
        source_root = str(root)
        try:
            root_stat = _bounded_path_stat(root)
            if root_stat.get("kind") != "directory":
                mismatches.append("source_location_unavailable")
                availability_code = "source_location_unavailable"
                probe_error = "configured source root is not a directory"
            else:
                root_reachable = True
        except FileNotFoundError:
            mismatches.append("source_location_unavailable")
            availability_code = "source_location_unavailable"
            probe_error = "configured source root does not exist"
        except TimeoutError as exc:
            mismatches.append("source_access_failed")
            availability_code = "source_access_failed"
            probe_error = str(exc)
        except OSError as exc:
            mismatches.append("source_access_failed")
            availability_code = "source_access_failed"
            probe_error = str(exc)
        if root_reachable:
            try:
                source_stat = _bounded_path_stat(path)
                if source_stat.get("kind") != "file":
                    mismatches.append("source_missing")
                    availability_code = "source_missing"
                else:
                    exists = True
                    current_size = max(0, int(source_stat.get("size") or 0))
                    current_mtime = datetime.fromtimestamp(float(source_stat.get("mtime") or 0.0), UTC)
            except FileNotFoundError:
                mismatches.append("source_missing")
                availability_code = "source_missing"
                probe_error = "source root is reachable but the source file does not exist"
            except TimeoutError as exc:
                mismatches.append("source_access_failed")
                availability_code = "source_access_failed"
                probe_error = str(exc)
            except OSError as exc:
                mismatches.append("source_access_failed")
                availability_code = "source_access_failed"
                probe_error = str(exc)
    if exists and expected_size > 0 and current_size != expected_size:
        mismatches.append("source_size_mismatch")
    if exists and expected_mtime is not None and current_mtime is not None:
        if abs((current_mtime - expected_mtime).total_seconds()) > 2.0:
            mismatches.append("source_mtime_mismatch")
    if exists and path is not None:
        content_baseline_valid = True
        if not expected_content_sha256:
            mismatches.append("source_content_sha256_missing")
            content_baseline_valid = False
        elif not _is_sha256_hex(expected_content_sha256):
            mismatches.append("source_content_sha256_invalid")
            content_baseline_valid = False
        if content_sha256_algorithm != NETWORK_RERUN_CONTENT_SHA256_ALGORITHM:
            mismatches.append("source_content_sha256_algorithm_invalid")
            content_baseline_valid = False
        if content_baseline_valid:
            try:
                observed_content_sha256 = _bounded_file_sha256(path, size_bytes=current_size)
            except TimeoutError as exc:
                mismatches.extend(("source_content_sha256_probe_timeout", "source_access_failed"))
                availability_code = "source_access_failed"
                probe_error = probe_error or str(exc)
            except OSError as exc:
                mismatches.extend(("source_content_sha256_read_failed", "source_access_failed"))
                availability_code = "source_access_failed"
                probe_error = probe_error or str(exc)
            else:
                if expected_content_sha256.casefold() != observed_content_sha256.casefold():
                    mismatches.append("source_content_sha256_mismatch")
        if not expected_identity_v2:
            mismatches.append("source_identity_v2_missing")
        elif identity_algorithm.casefold() in {"sha256", "full-sha256", "sha256-full-file"} and observed_content_sha256:
            observed_identity_v2 = observed_content_sha256
            if expected_identity_v2.casefold() != observed_identity_v2.casefold():
                mismatches.append("source_identity_v2_mismatch")
        else:
            observed_identity_v2, identity_error = _source_identity_v2(
                app=app,
                source=path,
                source_size=current_size,
                algorithm=identity_algorithm,
            )
            if identity_error:
                mismatches.append(identity_error)
                probe_error = probe_error or identity_error
                if identity_error in {
                    "source_identity_probe_timeout",
                    "source_identity_read_failed",
                    "source_identity_ffprobe_timeout",
                    "source_identity_ffprobe_failed",
                }:
                    mismatches.append("source_access_failed")
                    availability_code = "source_access_failed"
            elif expected_identity_v2.casefold() != observed_identity_v2.casefold():
                mismatches.append("source_identity_v2_mismatch")
    return {
        "schema_version": "desktop_rerun_network_source_replay_evidence.v1",
        "checked_at_utc": _now(),
        "source_path": source_path,
        "source_root": source_root,
        "root_reachable": root_reachable,
        "source_exists": exists,
        "availability_code": availability_code,
        "retryable": availability_code in {"source_location_unavailable", "source_access_failed"},
        "expected_size": expected_size,
        "observed_size": current_size,
        "expected_mtime_utc": expected_mtime.isoformat() if expected_mtime is not None else "",
        "observed_mtime_utc": current_mtime.isoformat() if current_mtime is not None else "",
        "expected_source_identity_v2": expected_identity_v2,
        "observed_source_identity_v2": observed_identity_v2,
        "source_identity_v2_algorithm": identity_algorithm or "size-duration-codec-sample-v1",
        "expected_source_content_sha256": expected_content_sha256,
        "observed_source_content_sha256": observed_content_sha256,
        "source_content_sha256_algorithm": content_sha256_algorithm,
        "probe_error": redact_network_secret_text(probe_error),
        "matches": not mismatches,
        "mismatches": mismatches,
    }


def _append_bounded(row: dict[str, Any], key: str, entry: Mapping[str, Any], *, limit: int = 20) -> None:
    existing = row.get(key)
    entries = [item for item in existing if isinstance(item, Mapping)] if isinstance(existing, list) else []
    entries.append(dict(entry))
    row[key] = entries[-limit:]


def _record_row_lifecycle(
    row: dict[str, Any],
    *,
    state: str,
    at_utc: str,
    reason_code: str,
    what: str,
    why: str,
    next_action: str,
    operator_action: str,
    operator_action_required: bool,
    job_id: str = "",
    worker_id: str = "",
) -> None:
    _record_row_transition(
        row,
        state=state,
        at_utc=at_utc,
        reason_code=reason_code,
        what=what,
        why=why,
        next_action=next_action,
        operator_action=operator_action,
        operator_action_required=operator_action_required,
        job_id=job_id,
        worker_id=worker_id,
    )
    failure = {
        "at_utc": at_utc,
        "reason_code": reason_code,
        "reason": why,
        "state": state,
        "job_id": job_id,
        "worker_id": worker_id,
        "next_action": next_action,
        "operator_action": operator_action,
    }
    if not isinstance(row.get("first_failure"), Mapping):
        row["first_failure"] = dict(failure)
    row["last_failure"] = dict(failure)


def _record_row_transition(
    row: dict[str, Any],
    *,
    state: str,
    at_utc: str,
    reason_code: str,
    what: str,
    why: str,
    next_action: str,
    operator_action: str,
    operator_action_required: bool,
    job_id: str = "",
    worker_id: str = "",
) -> None:
    row["reason_code"] = reason_code
    row["last_error"] = why
    row["what"] = what
    row["why"] = why
    row["when"] = at_utc
    row["next_action"] = next_action
    row["automatic_next_action"] = next_action if not operator_action_required else ""
    row["operator_action"] = operator_action
    row["available_operator_action"] = operator_action
    row["operator_action_required"] = operator_action_required
    _append_bounded(
        row,
        "timeline",
        {
            "state": state,
            "at_utc": at_utc,
            "reason_code": reason_code,
            "what": what,
            "why": why,
            "next": next_action,
            "operator_action": operator_action,
            "job_id": job_id,
            "worker_id": worker_id,
        },
        limit=NETWORK_RERUN_HISTORY_LIMIT,
    )


def _mark_source_replay_review(row: dict[str, Any], evidence: Mapping[str, Any]) -> None:
    now = str(evidence.get("checked_at_utc") or _now())
    mismatches = [str(item) for item in evidence.get("mismatches") or []]
    unavailable = any(
        item in mismatches
        for item in {
            "source_identity_probe_timeout",
            "source_identity_read_failed",
            "source_identity_ffprobe_timeout",
            "source_identity_ffprobe_failed",
            "ffprobe_unavailable",
            "ffprobe_path_probe_timeout",
        }
    )
    reason_code = "network_source_identity_unavailable" if unavailable else "network_source_identity_changed"
    why = (
        "The coordinator could not safely verify the planned source identity before dispatch."
        if unavailable
        else "The source at the planned path no longer matches the persisted retry identity evidence."
    )
    row["source_replay_evidence"] = dict(evidence)
    row["status"] = "review_required"
    row["claim_status"] = "review_required"
    row["claimable"] = False
    row["terminal"] = True
    row["manual_recovery_required"] = True
    row["manual_recovery_available"] = False
    row["updated_at"] = now
    _record_row_lifecycle(
        row,
        state="review_required",
        at_utc=now,
        reason_code=reason_code,
        what="Automatic Network CSV rerun dispatch was blocked.",
        why=f"{why} Mismatches: {', '.join(mismatches)}.",
        next_action="Review the source identity and create a fresh rerun plan with current evidence.",
        operator_action="Review the changed source; do not retry the stale row.",
        operator_action_required=True,
    )


def _schedule_source_replay_retry(
    row: dict[str, Any],
    evidence: Mapping[str, Any],
    *,
    retry_limit: int,
) -> None:
    row["source_replay_evidence"] = dict(evidence)
    row["retry_limit"] = retry_limit
    availability_code = str(evidence.get("availability_code") or "source_access_failed")
    detail = str(evidence.get("probe_error") or availability_code)
    _apply_retry_schedule(
        row,
        {
            "schema_version": NETWORK_RERUN_REDUCER_SCHEMA_VERSION,
            "reducer_phase": "coordinator_pre_dispatch_source_probe",
            "reduced_at_utc": str(evidence.get("checked_at_utc") or _now()),
            "classification": "source_access_retryable",
            "accepted": False,
            "retryable": True,
            "terminal": False,
            "reason_code": availability_code,
            "reason": detail,
            "what": "Network CSV rerun source access is temporarily unavailable.",
            "why": detail,
            "next_action": "Wait for the bounded backend source probe retry.",
            "operator_action": "Restore the source share or access if operator intervention is needed.",
            "source_replay_evidence": dict(evidence),
        },
    )


def _row_claimable(row: Mapping[str, Any], *, allow_local_handoff: bool) -> bool:
    if row.get("claimable") is not True:
        return False
    if str(row.get("status") or "").strip() not in {"pending_claim", "retryable", "retry_scheduled"}:
        return False
    if not _retry_is_due(row):
        return False
    if not _row_source_path(row):
        return False
    if not str(row.get("planned_output_path") or "").strip():
        return False
    handoff = _row_output_handoff(row)
    if handoff.get("ready") is not True:
        return False
    if not allow_local_handoff and handoff.get("remote_worker_compatible") is not True:
        return False
    return True


def _claimable_batch(payload: Mapping[str, Any]) -> bool:
    if payload.get("claim_provider_enabled") is not True:
        return False
    if payload.get("worker_execution_enabled") is not True:
        return False
    if payload.get("rows_claimable") is not True:
        return False
    return str(payload.get("status") or "").strip() in NETWORK_RERUN_ACTIVE_STATUSES


def _source_identity(row: Mapping[str, Any], source_path: str) -> dict[str, Any]:
    mapping = row.get("source_mapping")
    if isinstance(mapping, Mapping):
        method = str(mapping.get("method") or "")
    else:
        method = ""
    return {
        "schema_version": "desktop_rerun_network_source_identity.v1",
        "method": method or "coordinator_source_path",
        "source_path": source_path,
        "source_identity": normalize_source_identity(source_path),
        "library_id": _row_library_id(row),
        "relative_path": _row_relative_path(row),
        "source_size": _safe_int(row.get("source_size")),
        "source_mtime_utc": str(row.get("source_mtime_utc") or ""),
        "source_identity_v2": str(row.get("source_identity_v2") or ""),
        "source_identity_v2_algorithm": str(row.get("source_identity_v2_algorithm") or ""),
        "source_content_sha256": str(row.get("source_content_sha256") or ""),
        "source_content_sha256_algorithm": str(
            row.get("source_content_sha256_algorithm") or ""
        ),
    }


def _claim_metadata(
    *,
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
    state_path: Path,
    source_path: str,
    worker_id: str,
    worker_name: str,
) -> dict[str, Any]:
    return {
        "job_kind": NETWORK_RERUN_ROW_JOB_KIND,
        "rerun_batch_id": str(payload.get("batch_id") or ""),
        "rerun_row_key": str(row.get("row_key") or ""),
        "rerun_row_index": _safe_int(row.get("row_index")),
        "planned_output_path": str(row.get("planned_output_path") or ""),
        "output_handoff": _row_output_handoff(row),
        "source_identity": _source_identity(row, source_path),
        "coordinator_source_path": source_path,
        "worker_source_path": "",
        "handoff_probe": {},
        "destination_policy_applied": False,
        "batch_state_path": str(state_path),
        "worker_id": worker_id,
        "worker_name": worker_name,
    }


def _row_record(row: Mapping[str, Any], source_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        source_path=source_path,
        library_id=_row_library_id(row),
        relative_path=_row_relative_path(row),
        priority=False,
    )


def _update_counts(payload: dict[str, Any]) -> None:
    rows = [row for row in payload.get("rows") or [] if isinstance(row, dict)]
    payload["row_count"] = len(rows)
    payload["claimable_row_count"] = sum(1 for row in rows if row.get("claimable") is True)
    payload["claimed_row_count"] = sum(1 for row in rows if str(row.get("status") or "") == "claimed")
    payload["completed_pending_reduction_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "worker_completed_pending_reduction"
    )
    payload["failed_pending_reduction_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "worker_failed_pending_reduction"
    )
    payload["review_pending_reduction_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "worker_review_pending_reduction"
    )
    payload["retry_scheduled_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "retry_scheduled"
    )
    payload["retry_exhausted_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "retry_exhausted"
    )
    payload["review_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") in NETWORK_RERUN_REVIEW_ROW_STATUSES
    )
    payload["failed_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") in NETWORK_RERUN_FAILED_ROW_STATUSES
    )
    payload["skipped_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "skipped"
    )
    terminal_rows = [
        row
        for row in rows
        if row.get("terminal") is True
        or str(row.get("status") or "") in NETWORK_RERUN_TERMINAL_ROW_STATUSES
    ]
    payload["terminal_row_count"] = len(terminal_rows)
    payload["active_row_count"] = max(0, len(rows) - len(terminal_rows))
    payload["manual_recovery_row_count"] = sum(
        1 for row in rows if row.get("manual_recovery_required") is True
    )
    payload["batch_terminal"] = bool(rows) and len(terminal_rows) == len(rows)
    if payload["batch_terminal"]:
        if payload["review_row_count"]:
            status = "review_required"
        elif payload["retry_exhausted_row_count"]:
            status = "retry_exhausted"
        elif payload["failed_row_count"]:
            status = "failed"
        elif payload["skipped_row_count"]:
            status = "completed_with_skips"
        else:
            status = "complete"
        terminal_at = str(payload.get("terminal_at_utc") or _now())
        payload["status"] = status
        payload["rows_claimable"] = False
        payload["terminal_at_utc"] = terminal_at
        if status in {"complete", "completed_with_skips"}:
            payload.setdefault("completed_at_utc", terminal_at)
        elif status == "review_required":
            payload.setdefault("review_required_at_utc", terminal_at)
        else:
            payload.setdefault("failed_at_utc", terminal_at)


def claim_next_network_rerun_row(
    *,
    app: Any,
    registry: Any,
    worker_id: str,
    worker_name: str,
    accessible_library_ids: list[str] | None,
    encode_config_for_row: Callable[[Any], dict[str, Any]],
    allow_local_handoff: bool,
    job_id: str | None = None,
) -> NetworkRerunClaimLease | None:
    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        reconcile_orphaned_network_rerun_destination_policies(app)
        return _claim_next_network_rerun_row_locked(
            app=app,
            registry=registry,
            worker_id=worker_id,
            worker_name=worker_name,
            accessible_library_ids=accessible_library_ids,
            encode_config_for_row=encode_config_for_row,
            allow_local_handoff=allow_local_handoff,
            job_id=job_id,
        )


def _claim_next_network_rerun_row_locked(
    *,
    app: Any,
    registry: Any,
    worker_id: str,
    worker_name: str,
    accessible_library_ids: list[str] | None,
    encode_config_for_row: Callable[[Any], dict[str, Any]],
    allow_local_handoff: bool,
    job_id: str | None = None,
) -> NetworkRerunClaimLease | None:
    root = network_rerun_state_root_for_app(app)
    if root is None or not root.exists():
        return None
    paths = sorted(root.glob("*.json"))
    for path in paths:
        payload = _read_state(path)
        if not _claimable_batch(payload):
            continue
        rows = payload.get("rows")
        if not isinstance(rows, list):
            continue
        for row in sorted((item for item in rows if isinstance(item, dict)), key=lambda item: _safe_int(item.get("row_index"))):
            if not _row_claimable(row, allow_local_handoff=allow_local_handoff):
                continue
            if not _accessible_library_allowed(row, accessible_library_ids):
                continue
            replay_evidence = _source_replay_evidence(row, app=app)
            row["source_replay_evidence"] = replay_evidence
            if replay_evidence.get("matches") is not True:
                if replay_evidence.get("retryable") is True:
                    _schedule_source_replay_retry(
                        row,
                        replay_evidence,
                        retry_limit=_row_retry_limit(row, default=_configured_retry_limit(app)),
                    )
                else:
                    _mark_source_replay_review(row, replay_evidence)
                payload["updated_at_utc"] = _now()
                _update_counts(payload)
                _write_state(path, payload)
                continue
            source_path = _row_source_path(row)
            if registry.is_in_flight(source_path):
                continue
            claim_id = str(job_id or uuid.uuid4())
            metadata = _claim_metadata(
                payload=payload,
                row=row,
                state_path=path,
                source_path=source_path,
                worker_id=worker_id,
                worker_name=worker_name,
            )
            metadata["job_id"] = claim_id
            record = _row_record(row, source_path)
            encode_config = dict(encode_config_for_row(record) or {})
            encode_config["__job_kind"] = NETWORK_RERUN_ROW_JOB_KIND
            encode_config["__claim_metadata"] = metadata
            ok = registry.claim(
                job_id=claim_id,
                worker_id=worker_id,
                worker_name=worker_name,
                source_path=source_path,
                encode_config=encode_config,
                priority=False,
                estimated_size_gb=0.0,
                accessible_library_ids=accessible_library_ids,
                job_kind=NETWORK_RERUN_ROW_JOB_KIND,
                claim_metadata=metadata,
            )
            if not ok:
                continue
            previous_payload = copy.deepcopy(payload)
            now = _now()
            retry_count = _safe_int(row.get("retry_count"))
            attempt_count = max(_safe_int(row.get("attempt_count")), retry_count) + 1
            row["attempt_count"] = attempt_count
            row["retry_count"] = retry_count
            row["retry_limit"] = _row_retry_limit(row, default=_configured_retry_limit(app))
            row["retry_after_seconds"] = 0
            row["next_retry_at_utc"] = ""
            row["last_attempt_started_at_utc"] = now
            row["terminal"] = False
            row["manual_recovery_required"] = False
            row["manual_recovery_available"] = False
            _append_bounded(
                row,
                "attempt_history",
                {
                    "attempt_count": attempt_count,
                    "retry_count": retry_count,
                    "job_id": claim_id,
                    "worker_id": worker_id,
                    "worker_name": worker_name,
                    "started_at_utc": now,
                },
                limit=NETWORK_RERUN_HISTORY_LIMIT,
            )
            row["status"] = "claimed"
            row["claim_status"] = "claimed"
            row["claimable"] = False
            row["active_claim"] = {
                "job_id": claim_id,
                "worker_id": worker_id,
                "worker_name": worker_name,
                "claimed_at_utc": now,
                "source_path": source_path,
                "source_identity": metadata["source_identity"],
            }
            payload["status"] = "active"
            payload["updated_at_utc"] = now
            _update_counts(payload)
            try:
                _write_state(path, payload)
            except Exception:
                registry.rollback_claim(claim_id, worker_id)
                raise
            response = ClaimResponse(
                status="ok",
                job_id=claim_id,
                source_path=source_path,
                library_id=metadata["source_identity"]["library_id"],
                relative_path=metadata["source_identity"]["relative_path"],
                priority=False,
                estimated_size_gb=0.0,
                encode_config=encode_config,
                retry_on_failure=True,
                job_kind=NETWORK_RERUN_ROW_JOB_KIND,
                rerun_batch_id=metadata["rerun_batch_id"],
                rerun_row_key=metadata["rerun_row_key"],
                rerun_row_index=metadata["rerun_row_index"],
                planned_output_path=metadata["planned_output_path"],
                output_handoff=metadata["output_handoff"],
                source_identity=metadata["source_identity"],
                coordinator_source_path=source_path,
                destination_policy_applied=False,
            )
            return NetworkRerunClaimLease(
                response=response,
                state_path=path,
                previous_payload=previous_payload,
                worker_id=worker_id,
            )
    return None


def request_network_rerun_row_retry(
    *,
    app: Any,
    batch_id: str,
    row_key: str,
    request_id: str,
    reason: str,
    confirm_retry: bool = False,
) -> CommandResult:
    command = "rerun.network.retry"
    batch_key = str(batch_id or "").strip()
    row_key_text = str(row_key or "").strip()
    request_key = str(request_id or "").strip()
    reason_text = str(reason or "").strip()
    if confirm_retry is not True:
        return CommandResult(
            command=command,
            ok=False,
            message="Network CSV rerun manual retry requires confirm_retry=true.",
            severity="error",
            errors=["confirm_retry_required"],
        )
    if not batch_key or not row_key_text or not request_key or not reason_text:
        return CommandResult(
            command=command,
            ok=False,
            message="Network CSV rerun manual retry requires batch_id, row_key, request_id, and reason.",
            severity="error",
            errors=["manual_retry_identity_required"],
        )
    root = network_rerun_state_root_for_app(app)
    if root is None:
        return CommandResult(
            command=command,
            ok=False,
            message="Network CSV rerun state root is unavailable.",
            severity="error",
            errors=["network_rerun_state_root_unavailable"],
        )
    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        for path in sorted(root.glob("*.json")) if root.exists() else []:
            payload = _read_state(path)
            if str(payload.get("batch_id") or "") != batch_key:
                continue
            rows = payload.get("rows")
            if not isinstance(rows, list):
                break
            for row in rows:
                if not isinstance(row, dict) or str(row.get("row_key") or "") != row_key_text:
                    continue
                outcomes = [
                    dict(item)
                    for item in row.get("manual_retry_outcomes") or []
                    if isinstance(item, Mapping)
                ]
                prior_outcome = next(
                    (
                        item
                        for item in outcomes
                        if str(item.get("request_id") or "") == request_key
                    ),
                    None,
                )
                if prior_outcome is not None:
                    prior_data = dict(prior_outcome.get("data") or {})
                    prior_data["idempotent"] = True
                    return CommandResult(
                        command=command,
                        ok=prior_outcome.get("ok") is True,
                        message=str(prior_outcome.get("message") or "Manual retry request was already evaluated."),
                        severity=str(prior_outcome.get("severity") or "info"),
                        errors=[str(item) for item in prior_outcome.get("errors") or []],
                        refresh_hint=str(prior_outcome.get("refresh_hint") or ""),
                        data=prior_data,
                    )
                history = [
                    dict(item)
                    for item in row.get("manual_retry_history") or []
                    if isinstance(item, Mapping)
                ]
                prior = next(
                    (item for item in history if str(item.get("request_id") or "") == request_key),
                    None,
                )
                if prior is not None:
                    return CommandResult(
                        command=command,
                        ok=True,
                        message="Duplicate Network CSV rerun manual retry request was already applied.",
                        refresh_hint="rerun_results",
                        data={
                            "batch_id": batch_key,
                            "row_key": row_key_text,
                            "request_id": request_key,
                            "status": str(row.get("status") or ""),
                            "idempotent": True,
                            "state_path": str(path),
                        },
                    )
                if (
                    str(row.get("status") or "") != "retry_exhausted"
                    or row.get("manual_recovery_available") is not True
                    or isinstance(row.get("active_claim"), Mapping)
                ):
                    result = CommandResult(
                        command=command,
                        ok=False,
                        message="Network CSV rerun row is not eligible for another manual retry.",
                        severity="warning",
                        errors=["manual_retry_duplicate_guard"],
                        data={
                            "batch_id": batch_key,
                            "row_key": row_key_text,
                            "request_id": request_key,
                            "status": str(row.get("status") or ""),
                            "idempotent": False,
                        },
                    )
                    _append_bounded(
                        row,
                        "manual_retry_outcomes",
                        {
                            "request_id": request_key,
                            "evaluated_at_utc": _now(),
                            **result.to_mapping(),
                        },
                        limit=256,
                    )
                    payload["updated_at_utc"] = _now()
                    _write_state(path, payload)
                    return result
                evidence = _source_replay_evidence(row, app=app)
                if evidence.get("matches") is not True:
                    row["source_replay_evidence"] = dict(evidence)
                    denial = {
                        "request_id": request_key,
                        "requested_at_utc": _now(),
                        "reason": reason_text,
                        "availability_code": str(evidence.get("availability_code") or ""),
                        "mismatches": list(evidence.get("mismatches") or []),
                    }
                    _append_bounded(row, "manual_retry_denials", denial, limit=NETWORK_RERUN_HISTORY_LIMIT)
                    if evidence.get("retryable") is not True:
                        _mark_source_replay_review(row, evidence)
                    payload["updated_at_utc"] = _now()
                    _update_counts(payload)
                    result = CommandResult(
                        command=command,
                        ok=False,
                        message="Network CSV rerun manual retry was blocked because source identity is not currently verifiable.",
                        severity="warning",
                        errors=["manual_retry_source_not_ready"],
                        data={
                            "batch_id": batch_key,
                            "row_key": row_key_text,
                            "request_id": request_key,
                            "status": str(row.get("status") or ""),
                            "source_replay_evidence": dict(evidence),
                            "idempotent": False,
                        },
                    )
                    _append_bounded(
                        row,
                        "manual_retry_outcomes",
                        {
                            "request_id": request_key,
                            "evaluated_at_utc": _now(),
                            **result.to_mapping(),
                        },
                        limit=256,
                    )
                    _write_state(path, payload)
                    return result
                now = _now()
                event = {
                    "request_id": request_key,
                    "requested_at_utc": now,
                    "reason": reason_text,
                    "previous_status": str(row.get("status") or ""),
                    "previous_retry_count": _safe_int(row.get("retry_count")),
                    "retry_limit": _row_retry_limit(row, default=_configured_retry_limit(app)),
                    "source_replay_evidence": dict(evidence),
                }
                _append_bounded(row, "manual_retry_history", event, limit=NETWORK_RERUN_HISTORY_LIMIT)
                _append_bounded(
                    row,
                    "timeline",
                    {
                        "state": "pending_claim",
                        "at_utc": now,
                        "reason_code": "network_manual_retry_requested",
                        "what": "An explicit Network CSV rerun manual retry was accepted.",
                        "why": reason_text,
                        "next": "Wait for the coordinator to claim the row after fresh source verification.",
                        "operator_action": "No additional action is required unless the row fails again.",
                        "request_id": request_key,
                    },
                    limit=NETWORK_RERUN_HISTORY_LIMIT,
                )
                row.update(
                    {
                        "status": "pending_claim",
                        "claim_status": "pending_claim",
                        "claimable": True,
                        "terminal": False,
                        "retry_count": 0,
                        "retry_after_seconds": 0,
                        "next_retry_at_utc": "",
                        "manual_recovery_required": False,
                        "manual_recovery_available": False,
                        "operator_action_required": False,
                        "manual_retry_request_id": request_key,
                        "last_manual_retry": event,
                        "source_replay_evidence": dict(evidence),
                        "reason_code": "network_manual_retry_requested",
                        "what": "An explicit Network CSV rerun manual retry was accepted.",
                        "why": reason_text,
                        "when": now,
                        "next_action": "Wait for the coordinator to claim the row after fresh source verification.",
                        "automatic_next_action": "Wait for the coordinator claim.",
                        "operator_action": "No additional action is required unless the row fails again.",
                        "available_operator_action": "Review backend evidence while the retry is pending.",
                        "updated_at": now,
                    }
                )
                previous_terminal_at = str(payload.get("terminal_at_utc") or "")
                payload["status"] = "active"
                payload["rows_claimable"] = True
                payload["batch_terminal"] = False
                payload["reopened_at_utc"] = now
                payload["last_terminal_at_utc"] = previous_terminal_at
                payload.pop("terminal_at_utc", None)
                payload["updated_at_utc"] = now
                _update_counts(payload)
                result = CommandResult(
                    command=command,
                    ok=True,
                    message="Network CSV rerun row reopened for one explicit manual retry.",
                    refresh_hint="rerun_results",
                    data={
                        "batch_id": batch_key,
                        "row_key": row_key_text,
                        "request_id": request_key,
                        "status": "pending_claim",
                        "idempotent": False,
                        "state_path": str(path),
                    },
                )
                _append_bounded(
                    row,
                    "manual_retry_outcomes",
                    {
                        "request_id": request_key,
                        "evaluated_at_utc": now,
                        **result.to_mapping(),
                    },
                    limit=256,
                )
                _write_state(path, payload)
                return result
            break
    return CommandResult(
        command=command,
        ok=False,
        message="Network CSV rerun batch or row was not found.",
        severity="warning",
        errors=["network_rerun_row_not_found"],
        data={"batch_id": batch_key, "row_key": row_key_text, "request_id": request_key},
    )


def rollback_network_rerun_claim(
    lease: NetworkRerunClaimLease,
    registry: Any,
    *,
    reason: str,
) -> None:
    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        if not lease.state_path.exists():
            raise FileNotFoundError(f"Network rerun batch state is unavailable: {lease.state_path}")
        payload = _read_state(lease.state_path)
        row_key = str(lease.response.rerun_row_key or "")
        for row in payload.get("rows") or []:
            if not isinstance(row, dict) or str(row.get("row_key") or "") != row_key:
                continue
            active_claim = row.get("active_claim")
            if not isinstance(active_claim, Mapping):
                raise RuntimeError(f"Network rerun row {row_key!r} no longer has an active claim")
            if (
                str(active_claim.get("job_id") or "") != lease.response.job_id
                or str(active_claim.get("worker_id") or "") != lease.worker_id
            ):
                raise RuntimeError(f"Network rerun row {row_key!r} claim ownership changed before rollback")
            now = _now()
            row["status"] = "pending_claim"
            row["claim_status"] = "claim_rolled_back"
            row["claimable"] = True
            row.pop("active_claim", None)
            row["last_claim_rollback"] = {
                "job_id": lease.response.job_id,
                "worker_id": lease.worker_id,
                "reason": redact_network_secret_text(reason),
                "rolled_back_at_utc": now,
            }
            payload["updated_at_utc"] = now
            payload["status"] = "active"
            payload["rows_claimable"] = True
            _update_counts(payload)
            _write_state(lease.state_path, payload)
            released = registry.rollback_claim(lease.response.job_id, lease.worker_id)
            if released is None:
                raise RuntimeError(
                    f"Registry retained network rerun claim {lease.response.job_id!r} after batch rollback"
                )
            return
        raise RuntimeError(f"Network rerun row {row_key!r} was not found during claim rollback")


def _metadata_state_path(metadata: Mapping[str, Any], app: Any) -> Path | None:
    batch_id = str(metadata.get("rerun_batch_id") or "").strip()
    root = network_rerun_state_root_for_app(app)
    if root is None or NETWORK_RERUN_BATCH_ID_PATTERN.fullmatch(batch_id) is None:
        return None
    try:
        resolved_root = root.resolve(strict=False)
        expected = (resolved_root / f"{batch_id}.json").resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None
    if expected.parent != resolved_root or not _path_under_or_equal(str(expected), str(resolved_root)):
        return None
    raw = str(metadata.get("batch_state_path") or "").strip()
    if raw:
        try:
            supplied = Path(raw).resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            return None
        if _path_key_for_boundary(supplied) != _path_key_for_boundary(expected):
            return None
    return expected


def _request_text(request: Any, key: str) -> str:
    return str(getattr(request, key, "") or "").strip()


def _request_bool(request: Any, key: str, *, default: bool = False) -> bool:
    value = getattr(request, key, default)
    if isinstance(value, bool):
        return value
    return bool(value)


def _request_int(request: Any, key: str, *, default: int = 0) -> int:
    try:
        return max(0, int(getattr(request, key, default) or 0))
    except Exception:
        return default


def _request_mapping(request: Any, key: str) -> dict[str, Any]:
    value = getattr(request, key, None)
    return dict(value) if isinstance(value, Mapping) else {}


def _path_key_for_boundary(path: Path) -> str:
    try:
        text = str(path.resolve(strict=False))
    except OSError:
        text = str(path)
    return os.path.normcase(text.rstrip("\\/"))


def _path_under_or_equal(path_text: str, root_text: str) -> bool:
    path_raw = str(path_text or "").strip()
    root_raw = str(root_text or "").strip()
    if not path_raw or not root_raw:
        return False
    path_key = _path_key_for_boundary(Path(path_raw))
    root_key = _path_key_for_boundary(Path(root_raw))
    if path_key == root_key:
        return True
    return path_key.startswith(root_key + os.sep) or path_key.startswith(root_key + "/") or path_key.startswith(root_key + "\\")


def _artifact_text(payload: Mapping[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip()


def _read_worker_result_artifact(
    path_text: str,
    *,
    inline_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path_raw = str(path_text or "").strip()
    inline = dict(inline_payload) if isinstance(inline_payload, Mapping) else {}
    evidence: dict[str, Any] = {
        "path": path_raw,
        "supplied": bool(inline),
        "transport": "inline_signed_request" if inline else "none",
        "status": "not_supplied",
        "valid": None,
        "schema_version": "",
        "fields": {},
        "error": "",
    }
    if inline:
        payload: Any = inline
    elif path_raw:
        evidence.update(
            {
                "transport": "legacy_worker_local_path",
                "status": "legacy_path_unavailable",
                "error": (
                    "Legacy worker-local artifact paths are diagnostic only and are not "
                    "dereferenced by the coordinator."
                ),
            }
        )
        return evidence, None
    else:
        return evidence, None
    if not isinstance(payload, dict):
        evidence.update({"status": "invalid_root", "valid": False, "error": "worker result artifact root is not an object"})
        return evidence, None
    schema = _artifact_text(payload, "SchemaVersion")
    evidence["schema_version"] = schema
    evidence["fields"] = {
        "job_kind": _artifact_text(payload, "JobKind"),
        "rerun_batch_id": _artifact_text(payload, "RerunBatchId"),
        "rerun_row_key": _artifact_text(payload, "RerunRowKey"),
        "worker_claim_id": _artifact_text(payload, "WorkerClaimId"),
        "worker_run_id": _artifact_text(payload, "WorkerRunId"),
        "success": payload.get("Success") if isinstance(payload.get("Success"), bool) else None,
        "status": _artifact_text(payload, "Status"),
        "output_path": _artifact_text(payload, "OutputPath"),
        "output_size_bytes": _safe_int(payload.get("OutputSizeBytes")),
        "publish_state": _artifact_text(payload, "PublishState"),
        "publish_mode": _artifact_text(payload, "PublishMode"),
        "route": _artifact_text(payload, "Route"),
    }
    if schema != "local_worker_result.v1":
        evidence.update({"status": "invalid_schema", "valid": False, "error": "worker result artifact schema is not local_worker_result.v1"})
        return evidence, payload
    evidence.update({"status": "ok", "valid": True})
    return evidence, payload


def _source_identity_evidence(
    *,
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    request: Any,
) -> tuple[dict[str, Any], list[str]]:
    expected_source_path = _row_source_path(row) or str(metadata.get("coordinator_source_path") or "")
    expected_identity = normalize_source_identity(expected_source_path)
    metadata_identity_raw = metadata.get("source_identity")
    metadata_identity = dict(metadata_identity_raw) if isinstance(metadata_identity_raw, Mapping) else {}
    expected_identity = str(metadata_identity.get("source_identity") or expected_identity)
    request_identity = _request_mapping(request, "source_identity") or metadata_identity
    request_identity_value = str(request_identity.get("source_identity") or "").strip()
    expected_size = _safe_int(row.get("source_size") or metadata_identity.get("source_size"))
    request_size = _safe_int(request_identity.get("source_size"))
    expected_mtime = str(row.get("source_mtime_utc") or metadata_identity.get("source_mtime_utc") or "").strip()
    request_mtime = str(request_identity.get("source_mtime_utc") or "").strip()
    expected_identity_v2 = str(
        row.get("source_identity_v2") or metadata_identity.get("source_identity_v2") or ""
    ).strip()
    request_identity_v2 = str(request_identity.get("source_identity_v2") or "").strip()
    expected_content_sha256 = str(
        row.get("source_content_sha256")
        or metadata_identity.get("source_content_sha256")
        or ""
    ).strip()
    expected_content_sha256_algorithm = str(
        row.get("source_content_sha256_algorithm")
        or metadata_identity.get("source_content_sha256_algorithm")
        or ""
    ).strip()
    request_content_sha256 = str(request_identity.get("source_content_sha256") or "").strip()
    request_content_sha256_algorithm = str(
        request_identity.get("source_content_sha256_algorithm") or ""
    ).strip()
    request_coordinator_path = _request_text(request, "coordinator_source_path")
    worker_source_path = _request_text(request, "worker_source_path") or str(metadata.get("worker_source_path") or "")
    mismatches: list[str] = []
    if request_identity_value and expected_identity and request_identity_value != expected_identity:
        mismatches.append("source_identity_mismatch")
    if request_coordinator_path and expected_source_path:
        if normalize_source_identity(request_coordinator_path) != normalize_source_identity(expected_source_path):
            mismatches.append("coordinator_source_path_mismatch")
    if expected_size > 0 and request_size > 0 and request_size != expected_size:
        mismatches.append("source_size_mismatch")
    if expected_mtime and request_mtime:
        expected_mtime_value = _parse_utc(expected_mtime)
        request_mtime_value = _parse_utc(request_mtime)
        if (
            expected_mtime_value is None
            or request_mtime_value is None
            or abs((request_mtime_value - expected_mtime_value).total_seconds()) > 2.0
        ):
            mismatches.append("source_mtime_mismatch")
    if expected_identity_v2 and request_identity_v2 and expected_identity_v2.casefold() != request_identity_v2.casefold():
        mismatches.append("source_identity_v2_mismatch")
    expected_content_valid = True
    request_content_valid = True
    if not expected_content_sha256:
        mismatches.append("source_content_sha256_missing")
        expected_content_valid = False
    elif not _is_sha256_hex(expected_content_sha256):
        mismatches.append("source_content_sha256_invalid")
        expected_content_valid = False
    if expected_content_sha256_algorithm != NETWORK_RERUN_CONTENT_SHA256_ALGORITHM:
        mismatches.append("source_content_sha256_algorithm_invalid")
        expected_content_valid = False
    if not request_content_sha256:
        mismatches.append("request_source_content_sha256_missing")
        request_content_valid = False
    elif not _is_sha256_hex(request_content_sha256):
        mismatches.append("request_source_content_sha256_invalid")
        request_content_valid = False
    if request_content_sha256_algorithm != NETWORK_RERUN_CONTENT_SHA256_ALGORITHM:
        mismatches.append("request_source_content_sha256_algorithm_invalid")
        request_content_valid = False
    if (
        expected_content_valid
        and request_content_valid
        and expected_content_sha256.casefold() != request_content_sha256.casefold()
    ):
        mismatches.append("source_content_sha256_mismatch")
    return (
        {
            "schema_version": "desktop_rerun_network_reducer_source_identity.v1",
            "expected_source_path": expected_source_path,
            "expected_source_identity": expected_identity,
            "request_source_identity": request_identity_value,
            "expected_source_size": expected_size,
            "request_source_size": request_size,
            "expected_source_mtime_utc": expected_mtime,
            "request_source_mtime_utc": request_mtime,
            "expected_source_identity_v2": expected_identity_v2,
            "request_source_identity_v2": request_identity_v2,
            "expected_source_content_sha256": expected_content_sha256,
            "request_source_content_sha256": request_content_sha256,
            "expected_source_content_sha256_algorithm": expected_content_sha256_algorithm,
            "request_source_content_sha256_algorithm": request_content_sha256_algorithm,
            "request_coordinator_source_path": request_coordinator_path,
            "worker_source_path": worker_source_path,
            "library_id": _row_library_id(row),
            "relative_path": _row_relative_path(row),
            "matches": not mismatches,
            "mismatches": list(mismatches),
        },
        mismatches,
    )


def _output_evidence(request: Any, planned_output_path: str) -> dict[str, Any]:
    output_path = _request_text(request, "output_path")
    path = Path(output_path) if output_path else None
    exists = False
    probe_status = "not_supplied" if path is None else "missing"
    probe_error = ""
    stale = False
    size_bytes = _request_int(request, "output_size_bytes", default=0)
    if path is not None:
        try:
            probe = _bounded_path_stat(path)
            exists = probe.get("kind") == "file"
            probe_status = "ok" if exists else "not_file"
            size_bytes = max(size_bytes, _safe_int(probe.get("size")))
        except FileNotFoundError:
            probe_status = "missing"
        except (TimeoutError, PermissionError, OSError) as exc:
            probe_status = "access_failed"
            probe_error = redact_network_secret_text(exc)
            stale = True
    under_handoff = _path_under_or_equal(output_path, planned_output_path)
    return {
        "schema_version": "desktop_rerun_network_reducer_output.v1",
        "path": output_path,
        "planned_output_path": planned_output_path,
        "exists": exists,
        "is_file": exists,
        "size_bytes": size_bytes,
        "under_planned_handoff": under_handoff,
        "probe_status": probe_status,
        "probe_error": probe_error,
        "stale": stale,
    }


def _artifact_mismatches(
    artifact: Mapping[str, Any],
    *,
    request: Any,
    batch_id: str,
    row_key: str,
    job_id: str,
) -> list[str]:
    if artifact.get("valid") is not True:
        return ["worker_result_artifact_invalid"] if artifact.get("supplied") else []
    fields = artifact.get("fields")
    if not isinstance(fields, Mapping):
        return ["worker_result_artifact_invalid"]
    mismatches: list[str] = []
    artifact_job_kind = str(fields.get("job_kind") or "")
    if artifact_job_kind and artifact_job_kind != NETWORK_RERUN_ROW_JOB_KIND:
        mismatches.append("artifact_job_kind_mismatch")
    artifact_batch_id = str(fields.get("rerun_batch_id") or "")
    if artifact_batch_id and artifact_batch_id != batch_id:
        mismatches.append("artifact_batch_id_mismatch")
    artifact_row_key = str(fields.get("rerun_row_key") or "")
    if artifact_row_key and artifact_row_key != row_key:
        mismatches.append("artifact_row_key_mismatch")
    artifact_claim_id = str(fields.get("worker_claim_id") or "")
    if artifact_claim_id and job_id and artifact_claim_id != job_id:
        mismatches.append("artifact_claim_id_mismatch")
    artifact_success = fields.get("success")
    if isinstance(artifact_success, bool) and artifact_success != _request_bool(request, "success"):
        mismatches.append("artifact_success_mismatch")
    return mismatches


def _worker_result_snapshot(
    *,
    metadata: Mapping[str, Any],
    request: Any,
    now: str,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "desktop_rerun_network_worker_result_snapshot.v1",
        "job_id": _request_text(request, "job_id") or str(metadata.get("job_id") or ""),
        "worker_id": _request_text(request, "worker_id"),
        "success": _request_bool(request, "success"),
        "reported_at_utc": now,
        "output_path": _request_text(request, "output_path"),
        "output_size_bytes": _request_int(request, "output_size_bytes", default=0),
        "completion_status": _request_text(request, "completion_status"),
        "publish_state": _request_text(request, "publish_state"),
        "publish_mode": _request_text(request, "publish_mode"),
        "route": _request_text(request, "route"),
        "queue_terminal": _request_bool(request, "queue_terminal"),
        "retry_on_failure": _request_bool(request, "retry_on_failure", default=True),
        "reason_code": _request_text(request, "reason_code"),
        "reason": redact_network_secret_text(_request_text(request, "reason") or _request_text(request, "error_message")),
        "planned_output_path": str(metadata.get("planned_output_path") or _request_text(request, "planned_output_path")),
        "coordinator_source_path": str(metadata.get("coordinator_source_path") or _request_text(request, "coordinator_source_path")),
        "worker_source_path": str(metadata.get("worker_source_path") or _request_text(request, "worker_source_path")),
        "source_identity": dict(metadata.get("source_identity") or _request_mapping(request, "source_identity")),
        "handoff_probe": dict(metadata.get("handoff_probe") or _request_mapping(request, "handoff_probe")),
        "destination_policy_applied": _request_bool(request, "destination_policy_applied"),
        "pending_reduction": True,
        "worker_result_artifact_path": str(artifact.get("path") or ""),
        "worker_result_artifact_status": str(artifact.get("status") or ""),
    }


def _duplicate_reducer_result(row: dict[str, Any], *, request: Any, now: str) -> bool:
    existing = row.get("reducer_result")
    if not isinstance(existing, Mapping):
        return False
    job_id = _request_text(request, "job_id")
    if not job_id or str(existing.get("job_id") or "") != job_id:
        return False
    worker_id = _request_text(request, "worker_id")
    if not worker_id or str(existing.get("worker_id") or "") != worker_id:
        return False
    row["duplicate_done_count"] = _safe_int(row.get("duplicate_done_count")) + 1
    row["last_duplicate_done_at_utc"] = now
    _append_bounded(
        row,
        "reducer_events",
        {
            "schema_version": NETWORK_RERUN_REDUCER_SCHEMA_VERSION,
            "event": "duplicate_done_ignored",
            "job_id": job_id,
            "worker_id": worker_id,
            "recorded_at_utc": now,
        },
    )
    return True


def _mismatch_reason_code(mismatches: list[str]) -> str:
    if any(item.startswith("artifact_") or item == "worker_result_artifact_invalid" for item in mismatches):
        return "network_worker_artifact_mismatch"
    if any(item.startswith("active_claim_") for item in mismatches):
        return "network_active_claim_mismatch"
    if any(
        item in {
            "source_identity_mismatch",
            "coordinator_source_path_mismatch",
            "source_size_mismatch",
            "source_mtime_mismatch",
            "source_identity_v2_mismatch",
            "source_content_sha256_missing",
            "source_content_sha256_invalid",
            "source_content_sha256_algorithm_invalid",
            "request_source_content_sha256_missing",
            "request_source_content_sha256_invalid",
            "request_source_content_sha256_algorithm_invalid",
            "source_content_sha256_mismatch",
        }
        for item in mismatches
    ):
        return "network_source_identity_mismatch"
    if any(item.startswith("request_") for item in mismatches):
        return "network_request_identity_mismatch"
    return "network_result_integrity_mismatch"


def _build_reducer_result(
    *,
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    request: Any,
    now: str,
    late: bool = False,
) -> dict[str, Any]:
    batch_id = str(payload.get("batch_id") or metadata.get("rerun_batch_id") or _request_text(request, "rerun_batch_id"))
    row_key = str(row.get("row_key") or metadata.get("rerun_row_key") or _request_text(request, "rerun_row_key"))
    job_id = _request_text(request, "job_id") or str(metadata.get("job_id") or "")
    planned_output_path = str(metadata.get("planned_output_path") or row.get("planned_output_path") or _request_text(request, "planned_output_path"))
    artifact, _artifact_payload = _read_worker_result_artifact(
        _request_text(request, "worker_result_artifact_path"),
        inline_payload=_request_mapping(request, "worker_result_artifact"),
    )
    output = _output_evidence(request, planned_output_path)
    identity, identity_mismatches = _source_identity_evidence(row=row, metadata=metadata, request=request)
    mismatches: list[str] = list(identity_mismatches)
    req_batch = _request_text(request, "rerun_batch_id")
    req_row = _request_text(request, "rerun_row_key")
    if req_batch and req_batch != batch_id:
        mismatches.append("request_batch_id_mismatch")
    if req_row and req_row != row_key:
        mismatches.append("request_row_key_mismatch")
    active_claim = row.get("active_claim")
    if isinstance(active_claim, Mapping) and not late:
        if job_id and str(active_claim.get("job_id") or "") != job_id:
            mismatches.append("active_claim_job_id_mismatch")
        request_worker_id = _request_text(request, "worker_id")
        if request_worker_id and str(active_claim.get("worker_id") or "") != request_worker_id:
            mismatches.append("active_claim_worker_id_mismatch")
    mismatches.extend(_artifact_mismatches(artifact, request=request, batch_id=batch_id, row_key=row_key, job_id=job_id))

    success = _request_bool(request, "success")
    retry_on_failure = _request_bool(request, "retry_on_failure", default=True)
    queue_terminal = _request_bool(request, "queue_terminal")
    destination_policy_applied = _request_bool(request, "destination_policy_applied")
    publish_state = _request_text(request, "publish_state")
    reason = redact_network_secret_text(_request_text(request, "reason") or _request_text(request, "error_message"))
    reason_code = _request_text(request, "reason_code")
    classification = "success"
    accepted = False
    retryable = False
    terminal = False
    pending_destination_policy = False
    requires_review = False
    operator_action_required = False
    manual_recovery_required = False
    what = "Network CSV rerun worker result was reduced."
    next_action = "Continue with backend-owned destination policy."
    operator_action = ""

    if late:
        classification = "late_done_report"
        reason = reason or "Done report arrived after the active claim was no longer current."
    elif mismatches:
        classification = "corrupt_result"
        retryable = False
        terminal = True
        requires_review = True
        operator_action_required = True
        manual_recovery_required = True
        reason_code = _mismatch_reason_code(mismatches)
        reason = reason or "; ".join(mismatches)
        what = "Automatic Network CSV rerun result handling was blocked."
        next_action = "Review worker, claim, artifact, and source identity evidence before any new run."
        operator_action = "Resolve the mismatch and create or request a fresh safe rerun; do not replay this result."
    elif success:
        if destination_policy_applied:
            classification = "review"
            terminal = True
            requires_review = True
            operator_action_required = True
            manual_recovery_required = True
            reason_code = "network_destination_policy_ownership_violation"
            reason = "Worker reported destination policy was applied before coordinator reduction."
        elif "pending" in publish_state.casefold():
            classification = "review"
            terminal = True
            requires_review = True
            operator_action_required = True
            manual_recovery_required = True
            reason_code = "network_worker_publish_state_ambiguous"
            reason = "Worker reported worker-owned pending publish state before coordinator reduction."
        elif not output["exists"]:
            classification = "output_missing"
            retryable = False
            terminal = True
            requires_review = True
            operator_action_required = True
            manual_recovery_required = True
            reason_code = "network_output_missing_after_success"
            reason = reason or "Worker reported success but the handoff output is missing."
        elif not output["under_planned_handoff"]:
            classification = "review"
            terminal = True
            requires_review = True
            operator_action_required = True
            manual_recovery_required = True
            reason_code = "network_output_outside_planned_handoff"
            reason = "Worker output path is outside the planned row handoff folder."
        else:
            accepted = True
            pending_destination_policy = True
            reason_code = reason_code or "network_worker_output_accepted"
            reason = reason or "Worker handoff output is ready for coordinator destination policy."
        if requires_review:
            what = "Network CSV rerun output requires operator review."
            next_action = "Inspect the output and identity evidence before starting another attempt."
            operator_action = "Review the row evidence; do not automatically retry ambiguous output."
    else:
        artifact_fields = artifact.get("fields") if isinstance(artifact, Mapping) else None
        artifact_output_path = (
            str(artifact_fields.get("output_path") or "").strip()
            if isinstance(artifact_fields, Mapping)
            else ""
        )
        artifact_output_size = (
            _safe_int(artifact_fields.get("output_size_bytes"))
            if isinstance(artifact_fields, Mapping)
            else 0
        )
        output_reported = bool(
            output.get("exists") is True
            or str(output.get("path") or "").strip()
            or _safe_int(output.get("size_bytes")) > 0
            or artifact_output_path
            or artifact_output_size > 0
        )
        if output_reported:
            classification = "review"
            terminal = True
            retryable = False
            requires_review = True
            operator_action_required = True
            manual_recovery_required = True
            reason_code = (
                "network_worker_failure_existing_output"
                if output.get("exists") is True
                else "network_worker_failure_ambiguous_output"
            )
            reason = (
                "Worker reported failure after an attempt output was written."
                if output.get("exists") is True
                else "Worker reported failure with ambiguous output evidence."
            )
            what = "Automatic retry was blocked to prevent duplicate or overwrite risk."
            next_action = "Review and reconcile the attempt-scoped output before creating a fresh rerun plan."
            operator_action = "Do not retry this row until the output is explicitly reconciled with cleanup proof."
        else:
            terminal = bool(queue_terminal or not retry_on_failure)
            retryable = not terminal
            classification = "failed_terminal" if terminal else "failed_retryable"
            reason_code = reason_code or ("network_worker_failure_terminal" if terminal else "network_worker_failure_retryable")
            reason = reason or "Worker reported failure before coordinator destination policy."
            what = "Network CSV rerun worker attempt failed."
            if terminal:
                operator_action_required = True
                manual_recovery_required = True
                next_action = "Review the terminal worker failure before requesting another run."
                operator_action = "Resolve the worker failure and explicitly request a new rerun if safe."
            else:
                next_action = "Wait for the bounded backend retry window."
                operator_action = "Wait for automatic retry or review evidence without changing row state."

    return {
        "schema_version": NETWORK_RERUN_REDUCER_SCHEMA_VERSION,
        "reducer_phase": "phase_5_coordinator_result_reducer",
        "reduced_at_utc": now,
        "job_id": job_id,
        "worker_id": _request_text(request, "worker_id"),
        "batch_id": batch_id,
        "row_key": row_key,
        "classification": classification,
        "accepted": accepted,
        "retryable": retryable,
        "terminal": terminal,
        "pending_destination_policy": pending_destination_policy,
        "destination_policy_applied": destination_policy_applied,
        "reason_code": reason_code,
        "reason": reason,
        "requires_review": requires_review,
        "manual_recovery_required": manual_recovery_required,
        "operator_action_required": operator_action_required,
        "what": what,
        "why": reason,
        "when": now,
        "next_action": next_action,
        "operator_action": operator_action,
        "mismatches": mismatches,
        "source_identity": identity,
        "output_artifact": output,
        "worker_result_artifact": artifact,
    }


def _apply_retry_schedule(row: dict[str, Any], result: Mapping[str, Any]) -> None:
    now = datetime.now(UTC)
    retry_limit = _row_retry_limit(row)
    retry_count = min(_safe_int(row.get("retry_count")) + 1, retry_limit)
    attempt_count = max(_safe_int(row.get("attempt_count")), retry_count)
    exhausted = retry_count >= retry_limit
    retry_after = 0 if exhausted else _retry_after_seconds(retry_count)
    next_retry_at = "" if exhausted else (now + timedelta(seconds=retry_after)).isoformat()
    retry_state = "retry_exhausted" if exhausted else "retry_scheduled"

    row["status"] = retry_state
    row["claim_status"] = retry_state
    row["claimable"] = not exhausted
    row["attempt_count"] = attempt_count
    row["retry_count"] = retry_count
    row["retry_limit"] = retry_limit
    row["retry_after_seconds"] = retry_after
    row["next_retry_at_utc"] = next_retry_at
    row["terminal"] = exhausted
    row["manual_recovery_required"] = exhausted
    row["manual_recovery_available"] = exhausted
    row["operator_action_required"] = exhausted
    row["updated_at"] = now.isoformat()
    retry_event = {
        "status": retry_state,
        "attempt_count": attempt_count,
        "retry_count": retry_count,
        "retry_limit": retry_limit,
        "retry_after_seconds": retry_after,
        "scheduled_at_utc": now.isoformat(),
        "next_retry_at_utc": next_retry_at,
        "job_id": str(result.get("job_id") or ""),
        "worker_id": str(result.get("worker_id") or ""),
        "reason_code": str(result.get("reason_code") or ""),
        "reason": str(result.get("reason") or ""),
    }
    row["last_retry"] = retry_event
    _append_bounded(row, "retry_history", retry_event, limit=NETWORK_RERUN_HISTORY_LIMIT)
    persisted_result = dict(row.get("reducer_result") or result)
    persisted_result.update(
        {
            "retry_state": retry_state,
            "retry_count": retry_count,
            "retry_limit": retry_limit,
            "retry_after_seconds": retry_after,
            "next_retry_at_utc": next_retry_at,
            "retryable": not exhausted,
            "terminal": exhausted,
            "manual_recovery_required": exhausted,
        }
    )
    row["reducer_result"] = persisted_result
    next_action = (
        "Restore or repair the dependency, then request one explicit manual retry."
        if exhausted
        else f"Wait until {next_retry_at} for the bounded backend retry."
    )
    operator_action = (
        "Review the failure evidence and request a manual retry only after the cause is resolved."
        if exhausted
        else "No operator mutation is required while the backend retry is scheduled."
    )
    _record_row_lifecycle(
        row,
        state=retry_state,
        at_utc=now.isoformat(),
        reason_code=str(result.get("reason_code") or "network_worker_failure_retryable"),
        what=(
            "Automatic Network CSV rerun retries were exhausted."
            if exhausted
            else "A bounded Network CSV rerun retry was scheduled."
        ),
        why=str(result.get("reason") or "Worker attempt failed."),
        next_action=next_action,
        operator_action=operator_action,
        operator_action_required=exhausted,
        job_id=str(result.get("job_id") or ""),
        worker_id=str(result.get("worker_id") or ""),
    )


def _apply_review_result(row: dict[str, Any], result: Mapping[str, Any]) -> None:
    at_utc = str(result.get("reduced_at_utc") or result.get("when") or _now())
    row["status"] = "review_required"
    row["claim_status"] = "review_required"
    row["claimable"] = False
    row["terminal"] = True
    row["manual_recovery_required"] = True
    row["manual_recovery_available"] = False
    row["operator_action_required"] = True
    row["updated_at"] = at_utc
    persisted_result = dict(row.get("reducer_result") or result)
    persisted_result.update(
        {
            "retryable": False,
            "terminal": True,
            "requires_review": True,
            "manual_recovery_required": True,
            "operator_action_required": True,
        }
    )
    row["reducer_result"] = persisted_result
    _record_row_lifecycle(
        row,
        state="review_required",
        at_utc=at_utc,
        reason_code=str(result.get("reason_code") or "network_result_requires_review"),
        what=str(result.get("what") or "Network CSV rerun result requires operator review."),
        why=str(result.get("why") or result.get("reason") or "Result evidence is unsafe or ambiguous."),
        next_action=str(result.get("next_action") or "Review the row evidence before starting a new run."),
        operator_action=str(result.get("operator_action") or "Resolve the evidence mismatch; do not auto-retry this row."),
        operator_action_required=True,
        job_id=str(result.get("job_id") or ""),
        worker_id=str(result.get("worker_id") or ""),
    )


def _apply_reducer_result(row: dict[str, Any], result: Mapping[str, Any]) -> None:
    classification = str(result.get("classification") or "")
    row["reducer_result"] = dict(result)
    row["claim_status"] = "done_reported"
    row["claimable"] = False
    row.pop("active_claim", None)
    if result.get("accepted") is True:
        row["status"] = "worker_completed_pending_reduction"
        output = result.get("output_artifact")
        if isinstance(output, Mapping):
            row["verified_output_path"] = str(output.get("path") or "")
    elif result.get("requires_review") is True or classification in {"review", "corrupt_result", "output_missing"}:
        _apply_review_result(row, result)
    elif result.get("retryable") is True:
        _apply_retry_schedule(row, result)
    else:
        row["status"] = "worker_failed_pending_reduction"
        row["terminal"] = True
        row["manual_recovery_required"] = True
        row["manual_recovery_available"] = True
        row["operator_action_required"] = True
        _record_row_lifecycle(
            row,
            state="worker_failed_pending_reduction",
            at_utc=str(result.get("reduced_at_utc") or _now()),
            reason_code=str(result.get("reason_code") or "network_worker_failure_terminal"),
            what=str(result.get("what") or "Network CSV rerun worker attempt failed terminally."),
            why=str(result.get("why") or result.get("reason") or "Worker attempt failed."),
            next_action=str(result.get("next_action") or "Review the failure before requesting a new run."),
            operator_action=str(result.get("operator_action") or "Resolve the failure and request a new rerun if safe."),
            operator_action_required=True,
            job_id=str(result.get("job_id") or ""),
            worker_id=str(result.get("worker_id") or ""),
        )


def _destination_policy_enabled(payload: Mapping[str, Any]) -> bool:
    return payload.get("destination_policy_application_enabled") is True


def _destination_policy_applying_result(
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
    now: str,
    *,
    operation_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION,
        "phase": "phase_6_destination_policy_integration",
        "batch_id": str(payload.get("batch_id") or ""),
        "row_key": str(row.get("row_key") or ""),
        "operation_id": operation_id,
        "status": "applying",
        "ok": False,
        "terminal": False,
        "started_at_utc": now,
        "message": "Coordinator destination policy is applying.",
    }


def _destination_policy_unavailable_result(
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
    now: str,
    *,
    operation_id: str,
) -> dict[str, Any]:
    result = _destination_policy_applying_result(
        payload,
        row,
        now,
        operation_id=operation_id,
    )
    result.update(
        {
            "status": "failed",
            "errors": ["resolved_paths_unavailable"],
            "message": "Resolved path context is unavailable for Network CSV rerun destination policy.",
            "completed_at_utc": now,
        }
    )
    return result


def _destination_policy_ambiguous_result(
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
    now: str,
    *,
    operation_id: str,
    error: str,
) -> dict[str, Any]:
    return {
        "schema_version": NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION,
        "phase": "phase_6_destination_policy_integration",
        "batch_id": str(payload.get("batch_id") or ""),
        "row_key": str(row.get("row_key") or ""),
        "operation_id": operation_id,
        "status": "outcome_ambiguous",
        "ok": False,
        "terminal": True,
        "requires_review": True,
        "reason_code": "network_destination_policy_outcome_ambiguous_after_restart",
        "message": "Destination policy outcome is ambiguous; the coordinator will not replay media mutation automatically.",
        "error": redact_network_secret_text(error),
        "completed_at_utc": now,
    }


def _apply_destination_policy_result(row: dict[str, Any], result: Mapping[str, Any]) -> None:
    action = str(result.get("action") or "")
    status = str(result.get("status") or "")
    persisted_result = dict(result)
    if persisted_result.get("ok") is not True:
        persisted_result["terminal"] = True
        persisted_result.setdefault("completed_at_utc", _now())
    row["destination_policy_result"] = persisted_result
    row["claimable"] = False
    row["terminal"] = True
    row["destination_policy_applied"] = result.get("ok") is True
    row["updated_at"] = str(result.get("completed_at_utc") or result.get("started_at_utc") or _now())
    if result.get("ok") is True:
        row["reducer_result"] = {
            **dict(row.get("reducer_result") or {}),
            "pending_destination_policy": False,
            "destination_policy_applied": True,
        }
        if action == "review_workspace" or status == "review_workspace":
            row["status"] = "review_workspace"
            row["review_output_path"] = str(result.get("review_output_path") or row.get("verified_output_path") or "")
            row["reason"] = str(result.get("message") or "Network CSV rerun output requires review.")
        elif action == "pending_publish" or status == "pending_publish":
            row["status"] = "pending_publish"
            row["pending_publish_manifest_path"] = str(result.get("pending_publish_manifest_path") or "")
            row["pending_publish_payload_path"] = str(result.get("pending_publish_payload_path") or "")
            row["server_out"] = str(result.get("server_out") or row.get("final_output_path") or "")
            row["reason"] = str(result.get("message") or "Network CSV rerun output parked in Pending Publish.")
        elif status in {"published_replace_final", "published_non_overlap"}:
            row["status"] = status
            row["published_path"] = str(result.get("published_path") or "")
            row["server_out"] = str(result.get("published_path") or row.get("final_output_path") or "")
            row["reason"] = str(result.get("message") or "Network CSV rerun output published by coordinator policy.")
        else:
            row["status"] = "destination_policy_applied"
            row["reason"] = str(result.get("message") or "Network CSV rerun destination policy applied.")
        row["claim_status"] = str(row["status"])
        row["manual_recovery_required"] = False
        row["manual_recovery_available"] = False
        row["operator_action_required"] = False
        _record_row_transition(
            row,
            state=str(row["status"]),
            at_utc=str(result.get("completed_at_utc") or _now()),
            reason_code=str(result.get("reason_code") or f"network_destination_policy_{row['status']}"),
            what="Coordinator destination policy reached a terminal outcome.",
            why=str(result.get("message") or row.get("reason") or "Destination policy completed."),
            next_action=(
                "Use Pending Publish controls when the destination becomes safe."
                if row["status"] == "pending_publish"
                else "Review the output in its coordinator workspace."
                if row["status"] == "review_workspace"
                else "No automatic action remains for this row."
            ),
            operator_action=(
                "Drain Pending Publish when backend safety evidence permits."
                if row["status"] == "pending_publish"
                else "Review the output before choosing a publish action."
                if row["status"] == "review_workspace"
                else "No operator action is required."
            ),
            operator_action_required=row["status"] in {"pending_publish", "review_workspace"},
        )
        return
    row["reducer_result"] = {
        **dict(row.get("reducer_result") or {}),
        "pending_destination_policy": False,
        "destination_policy_applied": False,
        "destination_policy_failed": True,
    }
    row["status"] = "destination_policy_failed"
    row["claim_status"] = "destination_policy_failed"
    row["terminal"] = True
    row["manual_recovery_required"] = True
    row["manual_recovery_available"] = False
    row["operator_action_required"] = True
    row["reason"] = str(result.get("message") or "Network CSV rerun destination policy failed.")
    _record_row_lifecycle(
        row,
        state="destination_policy_failed",
        at_utc=str(result.get("completed_at_utc") or _now()),
        reason_code=str(result.get("reason_code") or "network_destination_policy_failed"),
        what="Coordinator destination policy failed terminally.",
        why=str(result.get("message") or "Destination policy failed."),
        next_action="Review handoff and destination evidence before creating a new operation.",
        operator_action="Resolve the destination-policy failure; automatic replay is disabled.",
        operator_action_required=True,
    )


def _request_metadata(request: Any, app: Any) -> dict[str, Any]:
    metadata = {
        "job_kind": NETWORK_RERUN_ROW_JOB_KIND,
        "rerun_batch_id": _request_text(request, "rerun_batch_id"),
        "rerun_row_key": _request_text(request, "rerun_row_key"),
        "planned_output_path": _request_text(request, "planned_output_path"),
        "source_identity": _request_mapping(request, "source_identity"),
        "coordinator_source_path": _request_text(request, "coordinator_source_path"),
        "worker_source_path": _request_text(request, "worker_source_path"),
        "handoff_probe": _request_mapping(request, "handoff_probe"),
        "destination_policy_applied": _request_bool(request, "destination_policy_applied"),
    }
    path = _metadata_state_path(metadata, app)
    if path is not None:
        metadata["batch_state_path"] = str(path)
    return metadata


def _row_matches(row: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    return str(row.get("row_key") or "") == str(metadata.get("rerun_row_key") or "")


def _active_claim_matches(row: Mapping[str, Any], *, job_id: str, worker_id: str) -> bool:
    active_claim = row.get("active_claim")
    if not isinstance(active_claim, Mapping):
        return False
    return (
        bool(job_id)
        and bool(worker_id)
        and str(active_claim.get("job_id") or "") == job_id
        and str(active_claim.get("worker_id") or "") == worker_id
    )


def _batch_identity_matches(payload: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    batch_id = str(metadata.get("rerun_batch_id") or "")
    return bool(batch_id) and str(payload.get("batch_id") or "") == batch_id


def _late_reclaim_identity_matches(
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    request: Any,
    late_report: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(late_report, Mapping):
        return False
    request_job_id = _request_text(request, "job_id")
    request_worker_id = _request_text(request, "worker_id")
    row_source_path = _row_source_path(row)
    return (
        bool(request_job_id)
        and bool(request_worker_id)
        and bool(row_source_path)
        and late_report.get("accepted") is True
        and str(late_report.get("authorization_status") or "") == "accepted"
        and str(late_report.get("job_id") or "") == request_job_id
        and str(late_report.get("worker_id") or "") == request_worker_id
        and str(late_report.get("reclaimed_worker_id") or "") == request_worker_id
        and str(late_report.get("job_kind") or "") == NETWORK_RERUN_ROW_JOB_KIND
        and str(late_report.get("rerun_batch_id") or "") == str(metadata.get("rerun_batch_id") or "")
        and str(late_report.get("rerun_row_key") or "") == str(metadata.get("rerun_row_key") or "")
        and normalize_source_identity(str(late_report.get("source_path") or ""))
        == normalize_source_identity(row_source_path)
    )


def update_network_rerun_row_released(
    *,
    app: Any,
    job: Any,
    worker_id: str,
    reason: str = "",
    retry_at_utc: str = "",
) -> bool:
    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        return _update_network_rerun_row_released_locked(
            app=app,
            job=job,
            worker_id=worker_id,
            reason=reason,
            retry_at_utc=retry_at_utc,
        )


def _update_network_rerun_row_released_locked(
    *,
    app: Any,
    job: Any,
    worker_id: str,
    reason: str = "",
    retry_at_utc: str = "",
) -> bool:
    metadata = getattr(job, "claim_metadata", {}) if getattr(job, "claim_metadata", None) else {}
    if not isinstance(metadata, Mapping) or metadata.get("job_kind") != NETWORK_RERUN_ROW_JOB_KIND:
        return False
    path = _metadata_state_path(metadata, app)
    if path is None or not path.exists():
        return False
    payload = _read_state(path)
    if not _batch_identity_matches(payload, metadata):
        return False
    now = _now()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not _row_matches(row, metadata):
            continue
        job_id = str(getattr(job, "job_id", "") or "")
        if not _active_claim_matches(row, job_id=job_id, worker_id=worker_id):
            return False
        retry_at = _parse_utc(retry_at_utc)
        if retry_at is not None:
            retry_count = _safe_int(row.get("retry_count")) + 1
            retry_limit = _row_retry_limit(row, default=_configured_retry_limit(app))
            row["retry_count"] = retry_count
            row["retry_limit"] = retry_limit
            if retry_count >= retry_limit:
                row["status"] = "retry_exhausted"
                row["claim_status"] = "retry_exhausted"
                row["claimable"] = False
                row["terminal"] = True
                row["manual_recovery_required"] = True
                row["manual_recovery_available"] = True
                row["next_retry_at_utc"] = ""
            else:
                row["status"] = "retry_scheduled"
                row["claim_status"] = "retry_scheduled"
                row["claimable"] = True
                row["terminal"] = False
                row["next_retry_at_utc"] = retry_at.isoformat()
                row["retry_after_seconds"] = max(
                    0,
                    int((retry_at - datetime.now(UTC)).total_seconds()),
                )
            _record_row_lifecycle(
                row,
                state=str(row["status"]),
                at_utc=now,
                reason_code="network_stale_claim_reclaimed",
                what="The coordinator reclaimed a Network CSV rerun claim after its heartbeat expired.",
                why=redact_network_secret_text(reason) or "Worker heartbeat lease expired.",
                next_action=(
                    "Wait until the stale-worker quarantine expires before another claim."
                    if row["status"] == "retry_scheduled"
                    else "Review the exhausted stale-claim history before an explicit retry."
                ),
                operator_action="Verify the previous worker is stopped if it may still be writing output.",
                operator_action_required=row["status"] == "retry_exhausted",
                job_id=str(getattr(job, "job_id", "") or ""),
                worker_id=worker_id,
            )
        else:
            row["status"] = "pending_claim"
            row["claim_status"] = "released"
            row["claimable"] = True
            row["terminal"] = False
        row.pop("active_claim", None)
        row["last_release"] = {
            "job_id": str(getattr(job, "job_id", "") or ""),
            "worker_id": worker_id,
            "released_at_utc": now,
            "reason": redact_network_secret_text(reason),
        }
        payload["updated_at_utc"] = _now()
        _update_counts(payload)
        _write_state(path, payload)
        return True
    return False


def update_network_rerun_row_done(
    *,
    app: Any,
    job: Any,
    request: Any,
) -> bool:
    work: dict[str, Any] | None
    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        accepted, work = _prepare_network_rerun_row_done_locked(
            app=app,
            job=job,
            request=request,
        )
    if not accepted or work is None:
        return accepted

    operation_id = str(work["operation_id"])
    payload_snapshot = dict(work["payload"])
    row_snapshot = dict(work["row"])
    resolved = getattr(app, "resolved", None)
    if resolved is None:
        destination_result = _destination_policy_unavailable_result(
            payload_snapshot,
            row_snapshot,
            _now(),
            operation_id=operation_id,
        )
    else:
        try:
            destination_result = apply_network_rerun_destination_policy(
                resolved,
                payload_snapshot,
                row_snapshot,
                product_version=str(
                    getattr(app, "product_version", "")
                    or getattr(app, "_product_version", "")
                    or ""
                ),
            )
        except Exception as exc:
            destination_result = _destination_policy_ambiguous_result(
                payload_snapshot,
                row_snapshot,
                _now(),
                operation_id=operation_id,
                error=str(exc),
            )
    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        return _finalize_network_rerun_destination_policy_locked(
            path=Path(work["path"]),
            row_key=str(work["row_key"]),
            operation_id=operation_id,
            result=destination_result,
        )


def _prepare_network_rerun_row_done_locked(
    *,
    app: Any,
    job: Any,
    request: Any,
) -> tuple[bool, dict[str, Any] | None]:
    metadata = getattr(job, "claim_metadata", {}) if getattr(job, "claim_metadata", None) else {}
    if not isinstance(metadata, Mapping) or metadata.get("job_kind") != NETWORK_RERUN_ROW_JOB_KIND:
        return False, None
    metadata = dict(metadata)
    metadata.setdefault("job_id", str(getattr(job, "job_id", "") or _request_text(request, "job_id")))
    path = _metadata_state_path(metadata, app)
    if path is None or not path.exists():
        return False, None
    payload = _read_state(path)
    if not _batch_identity_matches(payload, metadata):
        return False, None
    now = _now()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not _row_matches(row, metadata):
            continue
        existing_result = row.get("reducer_result")
        request_job_id = _request_text(request, "job_id") or str(metadata.get("job_id") or "")
        duplicate_candidate = (
            isinstance(existing_result, Mapping)
            and bool(request_job_id)
            and str(existing_result.get("job_id") or "") == request_job_id
        )
        if duplicate_candidate and _duplicate_reducer_result(row, request=request, now=now):
            payload["updated_at_utc"] = now
            _update_counts(payload)
            _write_state(path, payload)
            return True, None
        request_worker_id = _request_text(request, "worker_id") or str(metadata.get("worker_id") or "")
        if not _active_claim_matches(row, job_id=request_job_id, worker_id=request_worker_id):
            return False, None
        artifact, _payload = _read_worker_result_artifact(
            _request_text(request, "worker_result_artifact_path"),
            inline_payload=_request_mapping(request, "worker_result_artifact"),
        )
        row["worker_result"] = _worker_result_snapshot(metadata=metadata, request=request, now=now, artifact=artifact)
        reducer_result = _build_reducer_result(
            payload=payload,
            row=row,
            metadata=metadata,
            request=request,
            now=now,
        )
        _apply_reducer_result(row, reducer_result)
        if reducer_result.get("accepted") is True and _destination_policy_enabled(payload):
            operation_id = str(uuid.uuid4())
            row["destination_policy_operation_id"] = operation_id
            row["destination_policy_result"] = _destination_policy_applying_result(
                payload,
                row,
                now,
                operation_id=operation_id,
            )
            row["status"] = "destination_policy_applying"
            row["claim_status"] = "destination_policy_applying"
            row["claimable"] = False
            row["terminal"] = False
            _record_row_transition(
                row,
                state="destination_policy_applying",
                at_utc=now,
                reason_code="network_destination_policy_applying",
                what="Coordinator destination policy intent was persisted.",
                why="Media I/O is executing outside the global Network batch-state lock.",
                next_action="Wait for exact operation-ID finalization.",
                operator_action="No operator action is required while the coordinator is running.",
                operator_action_required=False,
                job_id=request_job_id,
                worker_id=request_worker_id,
            )
            payload["updated_at_utc"] = now
            _update_counts(payload)
            _write_state(path, payload)
            _NETWORK_RERUN_ACTIVE_DESTINATION_OPERATIONS.add(operation_id)
            return (
                True,
                {
                    "path": str(path),
                    "row_key": str(row.get("row_key") or ""),
                    "operation_id": operation_id,
                    "payload": copy.deepcopy(payload),
                    "row": copy.deepcopy(row),
                },
            )
        payload["updated_at_utc"] = now
        _update_counts(payload)
        _write_state(path, payload)
        return True, None
    return False, None


def _finalize_network_rerun_destination_policy_locked(
    *,
    path: Path,
    row_key: str,
    operation_id: str,
    result: Mapping[str, Any],
) -> bool:
    _NETWORK_RERUN_ACTIVE_DESTINATION_OPERATIONS.discard(operation_id)
    if not path.exists():
        return False
    payload = _read_state(path)
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or str(row.get("row_key") or "") != row_key:
            continue
        if (
            str(row.get("status") or "") != "destination_policy_applying"
            or str(row.get("destination_policy_operation_id") or "") != operation_id
        ):
            return False
        persisted_result = dict(result)
        persisted_result["operation_id"] = operation_id
        if str(persisted_result.get("status") or "") == "outcome_ambiguous":
            row["destination_policy_result"] = persisted_result
            row["status"] = "review_required"
            row["claim_status"] = "review_required"
            row["claimable"] = False
            row["terminal"] = True
            row["manual_recovery_required"] = True
            row["manual_recovery_available"] = False
            row["operator_action_required"] = True
            _record_row_lifecycle(
                row,
                state="review_required",
                at_utc=str(persisted_result.get("completed_at_utc") or _now()),
                reason_code="network_destination_policy_outcome_ambiguous_after_restart",
                what="Destination policy execution ended without a provable outcome.",
                why=str(persisted_result.get("message") or "Destination policy outcome is ambiguous."),
                next_action="Inspect the handoff, pending-publish, and final destinations before choosing a new action.",
                operator_action="Review destination evidence; do not replay this operation automatically.",
                operator_action_required=True,
            )
        else:
            _apply_destination_policy_result(row, persisted_result)
        payload["updated_at_utc"] = _now()
        _update_counts(payload)
        _write_state(path, payload)
        return True
    return False


def reconcile_orphaned_network_rerun_destination_policies(app: Any) -> int:
    """Terminalize persisted applying intents without replaying media mutation."""

    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        root = network_rerun_state_root_for_app(app)
        if root is None or not root.exists():
            return 0
        reconciled = 0
        for path in sorted(root.glob("*.json")):
            payload = _read_state(path)
            changed = False
            for row in payload.get("rows") or []:
                if not isinstance(row, dict) or str(row.get("status") or "") != "destination_policy_applying":
                    continue
                operation_id = str(row.get("destination_policy_operation_id") or "")
                if operation_id and operation_id in _NETWORK_RERUN_ACTIVE_DESTINATION_OPERATIONS:
                    continue
                result = _destination_policy_ambiguous_result(
                    payload,
                    row,
                    _now(),
                    operation_id=operation_id,
                    error="persisted destination-policy intent was found without a terminal outcome",
                )
                row["destination_policy_result"] = result
                row["status"] = "review_required"
                row["claim_status"] = "review_required"
                row["claimable"] = False
                row["terminal"] = True
                row["manual_recovery_required"] = True
                row["manual_recovery_available"] = False
                row["operator_action_required"] = True
                _record_row_lifecycle(
                    row,
                    state="review_required",
                    at_utc=str(result["completed_at_utc"]),
                    reason_code="network_destination_policy_outcome_ambiguous_after_restart",
                    what="Coordinator startup found an unfinished destination-policy intent.",
                    why="The prior process may have mutated media before interruption, so automatic replay is unsafe.",
                    next_action="Inspect destination evidence and resolve the row manually.",
                    operator_action="Review handoff, pending-publish, and final paths before taking action.",
                    operator_action_required=True,
                )
                changed = True
                reconciled += 1
            if changed:
                payload["updated_at_utc"] = _now()
                _update_counts(payload)
                _write_state(path, payload)
        return reconciled


def record_late_network_rerun_row_done(
    *,
    app: Any,
    request: Any,
    late_report: Mapping[str, Any] | None = None,
    only_duplicate: bool = False,
) -> bool:
    with _NETWORK_RERUN_BATCH_STATE_LOCK:
        return _record_late_network_rerun_row_done_locked(
            app=app,
            request=request,
            late_report=late_report,
            only_duplicate=only_duplicate,
        )


def _record_late_network_rerun_row_done_locked(
    *,
    app: Any,
    request: Any,
    late_report: Mapping[str, Any] | None = None,
    only_duplicate: bool = False,
) -> bool:
    metadata = _request_metadata(request, app)
    if metadata.get("job_kind") != NETWORK_RERUN_ROW_JOB_KIND:
        return False
    if not str(metadata.get("rerun_batch_id") or "") or not str(metadata.get("rerun_row_key") or ""):
        return False
    path = _metadata_state_path(metadata, app)
    if path is None or not path.exists():
        return False
    payload = _read_state(path)
    if not _batch_identity_matches(payload, metadata):
        return False
    now = _now()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not _row_matches(row, metadata):
            continue
        if only_duplicate:
            if _duplicate_reducer_result(row, request=request, now=now):
                payload["updated_at_utc"] = now
                _update_counts(payload)
                _write_state(path, payload)
                return True
            return False
        if not _late_reclaim_identity_matches(row, metadata, request, late_report):
            return False
        artifact, _payload = _read_worker_result_artifact(
            _request_text(request, "worker_result_artifact_path"),
            inline_payload=_request_mapping(request, "worker_result_artifact"),
        )
        late_result = _build_reducer_result(
            payload=payload,
            row=row,
            metadata=metadata,
            request=request,
            now=now,
            late=True,
        )
        if late_report is not None:
            late_result["registry_late_report"] = dict(late_report)
        row["last_late_worker_result"] = _worker_result_snapshot(metadata=metadata, request=request, now=now, artifact=artifact)
        row["last_late_reducer_result"] = late_result
        row["late_done_count"] = _safe_int(row.get("late_done_count")) + 1
        _append_bounded(row, "late_worker_results", late_result)
        payload["updated_at_utc"] = now
        _update_counts(payload)
        _write_state(path, payload)
        return True
    return False


__all__ = [
    "NETWORK_RERUN_ROW_JOB_KIND",
    "NetworkRerunClaimLease",
    "claim_next_network_rerun_row",
    "network_rerun_state_root_for_app",
    "record_late_network_rerun_row_done",
    "request_network_rerun_row_retry",
    "rollback_network_rerun_claim",
    "update_network_rerun_row_done",
    "update_network_rerun_row_released",
]
