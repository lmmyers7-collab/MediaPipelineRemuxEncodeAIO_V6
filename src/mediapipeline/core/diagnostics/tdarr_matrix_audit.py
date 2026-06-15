"""Backend-owned Tdarr Matrix audit command policy and service runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.dto_base import json_safe
from mediapipeline.desktop.subprocess_runner import run_capture
from mediapipeline.core.diagnostics.tdarr_matrix_proof import (
    tdarr_case_keys_for_pack,
    tdarr_expected_manifest_count,
    tdarr_proof_pack_root,
    tdarr_proof_runs_root,
)

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional desktop dependency
    psutil = None  # type: ignore


TDARR_MATRIX_AUDIT_COMMAND = "diagnostics.tdarr_matrix_audit"
TDARR_MATRIX_AUDIT_REFRESH_HINT = "diagnostics"
TDARR_MATRIX_AUDIT_PROGRESS_SCHEMA_VERSION = "desktop_tdarr_matrix_audit_progress.v1"
TDARR_MATRIX_AUDIT_TOOL_MODULE = "mediapipeline.tools.dev.tdarr_matrix_audit"
TDARR_PROOF_PACK_TOOL_MODULE = "mediapipeline.tools.dev.tdarr_proof_pack"
TDARR_MATRIX_AUDIT_ALLOWED_ACTIONS = (
    "prepare-proof-pack",
    "report",
    "smoke-pack",
    "proof-pack",
    "strict-report",
    "cleanup-plan",
    "cleanup-archive",
    "cleanup-delete",
)
TDARR_MATRIX_AUDIT_FINDINGS_PREVIEW_LIMIT = 50

# Number of diagnostic buckets the run-samples harness iterates. Must stay equal to
# len(materialize_tdarr_test_library.BUCKET_SERIES) and tdarr_matrix_audit.BUCKET_ORDER;
# enforced by test_bucket_definitions_are_in_sync. Used to size the runner timeout (G1).
TDARR_MATRIX_AUDIT_BUCKET_COUNT = 6
# Fixed slack added on top of the worst-case prepare + sample budget so audit/IO overhead
# cannot trip the outer process timeout.
TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS = 300

TDARR_MATRIX_AUDIT_PRESETS: dict[str, dict[str, Any]] = {
    "prepare-proof-pack": {
        "label": "Prepare Tdarr Proof Pack",
        "mode": "proof-pack-materialize",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 7200,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
    "report": {
        "label": "Prepare Tdarr Proof Pack Audit Report",
        "mode": "report",
        "report_only": True,
        "prepare_timeout_seconds": 1800,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 900,
        "hash_sources": True,
    },
    "smoke-pack": {
        "label": "Run Tdarr Smoke Pack",
        "mode": "run-samples",
        "report_only": True,
        "prepare_timeout_seconds": 600,
        "sample_timeout_seconds": 900,
        "samples_per_bucket": 0,
        "sample_count_hint": tdarr_expected_manifest_count("smoke-pack"),
        "case_pack": "smoke-pack",
        "runner_timeout_seconds": 24000,
        "background": True,
    },
    "proof-pack": {
        "label": "Run Tdarr Proof Pack",
        "mode": "run-samples",
        "report_only": True,
        "prepare_timeout_seconds": 600,
        "sample_timeout_seconds": 1800,
        "samples_per_bucket": 0,
        "sample_count_hint": tdarr_expected_manifest_count("proof-pack"),
        "case_pack": "proof-pack",
        "runner_timeout_seconds": 172200,
        "background": True,
    },
    # strict-report is a STATIC gate (G9): it runs the pipeline validate / effective-config /
    # queue-snapshot commands, audits the queue snapshot and path containment, and verifies
    # source hashes (hash_sources). It does NOT process media, and it fails only on
    # critical/error findings -- audio-only "processed successfully" stays an advisory warning
    # and does not fail the gate. See docs/dev/tdarr-matrix-audit-gaps.md G9.
    "strict-report": {
        "label": "Run Tdarr Proof Pack Strict Report Gate",
        "mode": "report",
        "report_only": False,
        "prepare_timeout_seconds": 1800,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 900,
        "hash_sources": True,
    },
    "cleanup-plan": {
        "label": "Plan Tdarr Full Matrix Cleanup",
        "mode": "proof-pack-cleanup",
        "cleanup_action": "plan",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 900,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
    "cleanup-archive": {
        "label": "Archive Tdarr Full Matrix Evidence",
        "mode": "proof-pack-cleanup",
        "cleanup_action": "archive",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 1800,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
    "cleanup-delete": {
        "label": "Delete Verified Tdarr Full Matrix",
        "mode": "proof-pack-cleanup",
        "cleanup_action": "delete",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 3600,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
}


def _command_result(**fields: Any) -> Any:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


def normalize_tdarr_matrix_audit_action(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("_", "-")
    return text or "report"


def tdarr_matrix_audit_preset(action: Any) -> dict[str, Any] | None:
    normalized = normalize_tdarr_matrix_audit_action(action)
    preset = TDARR_MATRIX_AUDIT_PRESETS.get(normalized)
    if preset is None:
        return None
    return {"action": normalized, **preset}


def tdarr_matrix_audit_runner_timeout(preset: dict[str, Any]) -> int:
    """Minimum safe outer-process timeout for a preset (G1).

    ``prepare_pipeline_evidence`` runs three pipeline commands, each bounded by
    ``prepare_timeout_seconds``. ``run-samples`` then processes
    ``samples_per_bucket * TDARR_MATRIX_AUDIT_BUCKET_COUNT`` files, each bounded by
    ``sample_timeout_seconds``. The configured ``runner_timeout_seconds`` is treated as a
    floor, so this only ever raises the cap, never lowers it.
    """
    prepare = 3 * int(preset.get("prepare_timeout_seconds", 0) or 0)
    if str(preset.get("mode") or "") == "run-samples":
        sample_count = (
            int(preset.get("sample_count_hint", 0) or 0)
            if bool(preset.get("sample_count_hint")) or bool(preset.get("all_samples")) or bool(preset.get("case_pack"))
            else int(preset.get("samples_per_bucket", 0) or 0) * TDARR_MATRIX_AUDIT_BUCKET_COUNT
        )
    else:
        sample_count = 0
    samples = sample_count * int(preset.get("sample_timeout_seconds", 0) or 0)
    derived = prepare + samples + TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS
    floor = int(preset.get("runner_timeout_seconds", 0) or 0)
    return max(30, floor, derived)


def tdarr_matrix_default_library_root(workspace_root: Path) -> Path:
    return tdarr_proof_pack_root(workspace_root)


def tdarr_matrix_default_runs_root(workspace_root: Path) -> Path:
    return tdarr_proof_runs_root(workspace_root)


def tdarr_matrix_background_run_id(action: str, runs_root: Path) -> str:
    suffixes = {
        "smoke-pack": "-smoke-pack",
        "proof-pack": "-proof-pack",
    }
    suffix = suffixes.get(normalize_tdarr_matrix_audit_action(action), "")
    base = datetime.now(timezone.utc).strftime(f"run-%Y%m%d-%H%M%S{suffix}")
    candidate = base
    index = 2
    while (runs_root / candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _tdarr_matrix_report_path(run_root: Path) -> Path:
    return run_root / "manifests" / "audit" / "tdarr_matrix_audit_report.json"


def _tdarr_matrix_run_sentinel(run_root: Path) -> dict[str, Any]:
    sentinel = run_root / ".tdarr-matrix-audit-run.json"
    try:
        payload = json.loads(sentinel.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _tdarr_matrix_background_process_metadata_path(runs_root: Path, run_id: str) -> Path:
    return runs_root / "_background" / f"{run_id}.process.json"


def _tdarr_matrix_read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _tdarr_matrix_process_start_time_text(pid: int, *, psutil_module: Any | None = None) -> str:
    if psutil_module is None:
        psutil_module = psutil
    if pid <= 0 or psutil_module is None:
        return ""
    try:
        process = psutil_module.Process(pid)
        created = float(process.create_time())
    except Exception:
        return ""
    return datetime.fromtimestamp(created, timezone.utc).isoformat()


def _tdarr_matrix_timestamp_matches(expected: Any, actual: Any, *, tolerance_seconds: float = 2.0) -> bool:
    try:
        expected_time = datetime.fromisoformat(str(expected).replace("Z", "+00:00")).astimezone(timezone.utc)
        actual_time = datetime.fromisoformat(str(actual).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return False
    return abs((expected_time - actual_time).total_seconds()) <= tolerance_seconds


def _tdarr_matrix_background_process_state(
    runs_root: Path,
    run_id: str,
    *,
    psutil_module: Any | None = None,
) -> dict[str, Any]:
    if psutil_module is None:
        psutil_module = psutil
    metadata_path = _tdarr_matrix_background_process_metadata_path(runs_root, run_id)
    metadata = _tdarr_matrix_read_json(metadata_path)
    pid = _int_value(metadata.get("pid"))
    if pid <= 0:
        return {
            "live": False,
            "reason": "missing_background_pid",
            "pid": 0,
            "metadata_path": str(metadata_path),
        }
    expected_start = str(metadata.get("process_start_time") or "")
    if not expected_start:
        return {
            "live": False,
            "reason": "missing_process_start_time",
            "pid": pid,
            "metadata_path": str(metadata_path),
        }
    if psutil_module is None:
        return {
            "live": False,
            "reason": "process_liveness_unavailable",
            "pid": pid,
            "metadata_path": str(metadata_path),
        }
    try:
        process = psutil_module.Process(pid)
        alive = bool(process.is_running()) and process.status() != psutil_module.STATUS_ZOMBIE
    except psutil_module.NoSuchProcess:
        return {
            "live": False,
            "reason": "process_not_found",
            "pid": pid,
            "metadata_path": str(metadata_path),
        }
    except Exception as exc:
        return {
            "live": False,
            "reason": f"process_liveness_check_failed: {exc}",
            "pid": pid,
            "metadata_path": str(metadata_path),
        }
    if not alive:
        return {
            "live": False,
            "reason": "process_not_running",
            "pid": pid,
            "metadata_path": str(metadata_path),
        }
    actual_start = _tdarr_matrix_process_start_time_text(pid, psutil_module=psutil_module)
    if not actual_start or not _tdarr_matrix_timestamp_matches(expected_start, actual_start):
        return {
            "live": False,
            "reason": "pid_identity_mismatch",
            "pid": pid,
            "metadata_path": str(metadata_path),
        }
    return {
        "live": True,
        "reason": "",
        "pid": pid,
        "metadata_path": str(metadata_path),
        "process_start_time": expected_start,
    }


def tdarr_matrix_incomplete_full_run_evidence(
    runs_root: Path,
    *,
    selected_count: int,
    psutil_module: Any | None = None,
) -> dict[str, Any]:
    if psutil_module is None:
        psutil_module = psutil
    if not runs_root.exists():
        return {"active": None, "stale": None}
    active_candidates: list[tuple[Path, dict[str, Any]]] = []
    stale_candidates: list[tuple[Path, dict[str, Any]]] = []
    for child in runs_root.iterdir():
        if not child.is_dir() or child.name == "_background":
            continue
        if _tdarr_matrix_report_path(child).exists():
            continue
        sentinel = _tdarr_matrix_run_sentinel(child)
        if _int_value(sentinel.get("selected_count")) < selected_count:
            continue
        process_state = _tdarr_matrix_background_process_state(
            runs_root,
            child.name,
            psutil_module=psutil_module,
        )
        if bool(process_state.get("live")):
            active_candidates.append((child, process_state))
        else:
            stale_candidates.append((child, process_state))
    if active_candidates:
        active_candidates.sort(key=lambda item: item[0].stat().st_mtime, reverse=True)
        return {"active": active_candidates[0][0], "active_process": active_candidates[0][1], "stale": None}
    if stale_candidates:
        stale_candidates.sort(key=lambda item: item[0].stat().st_mtime, reverse=True)
        return {"active": None, "stale": stale_candidates[0][0], "stale_process": stale_candidates[0][1]}
    return {"active": None, "stale": None}


def tdarr_matrix_incomplete_full_run(runs_root: Path, *, selected_count: int) -> Path | None:
    evidence = tdarr_matrix_incomplete_full_run_evidence(runs_root, selected_count=selected_count)
    active = evidence.get("active")
    return active if isinstance(active, Path) else None


def tdarr_matrix_default_entrypoint(workspace_root: Path) -> Path:
    return workspace_root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1"


def tdarr_matrix_runner_script(workspace_root: Path) -> Path:
    return workspace_root / "ops" / "scripts" / "dev" / "run-python-tool.py"


def tdarr_matrix_audit_arguments(
    *,
    action: str,
    library_root: Path,
    powershell: str,
    entrypoint: Path,
    runs_root: Path | None = None,
    case_keys: list[str] | tuple[str, ...] | None = None,
    run_id: str = "",
    confirm_delete_full_matrix: bool = False,
) -> list[str]:
    preset = tdarr_matrix_audit_preset(action)
    if preset is None:
        raise ValueError(f"Unsupported Tdarr Matrix audit action: {action}")
    mode = str(preset["mode"])
    if mode == "proof-pack-materialize":
        return [
            "materialize",
            "--proof-root",
            str(library_root),
        ]
    if mode == "proof-pack-cleanup":
        args = [
            "cleanup",
            "--proof-root",
            str(library_root),
            "--action",
            str(preset.get("cleanup_action") or "plan"),
        ]
        if str(preset.get("cleanup_action") or "") == "delete" and confirm_delete_full_matrix:
            args.append("--confirm-delete-full-matrix")
        return args

    args = [
        str(preset["mode"]),
        "--library-root",
        str(library_root),
        "--powershell",
        str(powershell),
        "--entrypoint",
        str(entrypoint),
        "--prepare-timeout-seconds",
        str(int(preset["prepare_timeout_seconds"])),
    ]
    if mode == "report":
        args.append("--prepare-evidence")
        if preset.get("hash_sources"):
            args.append("--hash-sources")
    else:
        args.extend(
            [
                "--sample-timeout-seconds",
                str(int(preset["sample_timeout_seconds"])),
            ]
        )
        if runs_root is not None:
            args.extend(["--runs-root", str(runs_root)])
        requested_case_keys = list(case_keys or ())
        if not requested_case_keys and preset.get("case_pack"):
            requested_case_keys = list(tdarr_case_keys_for_pack(str(preset["case_pack"])))
        if requested_case_keys:
            for case_key in requested_case_keys:
                text = str(case_key or "").strip()
                if text:
                    args.extend(["--case-key", text])
        elif bool(preset.get("all_samples")):
            args.append("--all-samples")
        else:
            args.extend(["--samples-per-bucket", str(int(preset["samples_per_bucket"]))])
        run_id_text = str(run_id or "").strip()
        if run_id_text:
            args.extend(["--run-id", run_id_text])
    if bool(preset["report_only"]):
        args.append("--report-only")
    return args


def _parse_last_json_object(text: str) -> dict[str, Any]:
    stripped = str(text or "").strip()
    if not stripped:
        return {}
    decoder = json.JSONDecoder()
    candidate: dict[str, Any] = {}
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and not stripped[index + end :].strip():
            candidate = parsed
    return candidate


def _int_value(value: Any) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return 0


def _bounded_text(value: Any, *, limit: int = 3000) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


def _finding_preview_row(finding: Any) -> dict[str, Any]:
    row = dict(finding or {}) if isinstance(finding, dict) else {}
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    worker_result = evidence.get("worker_result") if isinstance(evidence.get("worker_result"), dict) else {}
    return {
        "severity": str(row.get("severity") or ""),
        "code": str(row.get("code") or ""),
        "message": _bounded_text(row.get("message"), limit=240),
        "case_id": str(row.get("case_id") or ""),
        "view": str(row.get("view") or ""),
        "diagnostic_bucket": str(row.get("diagnostic_bucket") or ""),
        "generated_path": _bounded_text(row.get("generated_path"), limit=360),
        "source_path": _bounded_text(row.get("source_path"), limit=360),
        "media_kind": str(worker_result.get("MediaKind") or ""),
        "route": str(worker_result.get("Route") or ""),
        "route_reason_code": str(worker_result.get("RouteReasonCode") or ""),
        "status": str(worker_result.get("Status") or ""),
        "reason": _bounded_text(worker_result.get("Reason"), limit=240),
        "source_name": _bounded_text(worker_result.get("SourceName"), limit=360),
    }


def tdarr_matrix_audit_findings_preview(
    report_path: Any,
    *,
    limit: int = TDARR_MATRIX_AUDIT_FINDINGS_PREVIEW_LIMIT,
) -> dict[str, Any]:
    path_text = str(report_path or "").strip()
    if not path_text:
        return {"findings_preview": [], "findings_preview_total": 0, "findings_preview_error": ""}
    path = Path(path_text)
    if not path.exists():
        return {
            "findings_preview": [],
            "findings_preview_total": 0,
            "findings_preview_error": f"Report file is missing: {path}",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "findings_preview": [],
            "findings_preview_total": 0,
            "findings_preview_error": f"Could not read report findings: {exc}",
        }
    findings = payload.get("findings") if isinstance(payload, dict) else []
    if not isinstance(findings, list):
        return {
            "findings_preview": [],
            "findings_preview_total": 0,
            "findings_preview_error": "Report findings field is not a list.",
        }
    bounded_limit = max(0, int(limit))
    preview = [_finding_preview_row(finding) for finding in findings[:bounded_limit]]
    return {
        "findings_preview": preview,
        "findings_preview_total": len(findings),
        "findings_preview_error": "",
    }


def tdarr_matrix_audit_progress_payload(result: dict[str, Any]) -> dict[str, Any]:
    success = bool(result.get("success"))
    timed_out = bool(result.get("timed_out"))
    background_started = bool(result.get("background_started"))
    already_running = bool(result.get("already_running"))
    stale_incomplete_run = bool(result.get("stale_incomplete_run"))
    action = str(result.get("action") or "")
    mode = str(result.get("mode") or "")
    finding_count = _int_value(result.get("finding_count"))
    status = "active" if background_started or already_running else "complete" if success and finding_count == 0 else "warning" if success else "blocked" if timed_out or stale_incomplete_run else "error"
    detail = (
        f"{result.get('label') or 'Tdarr Matrix audit'} started in background as {result.get('run_id') or 'a new run'}."
        if background_started
        else f"{result.get('label') or 'Tdarr Matrix audit'} is already running as {result.get('run_id') or 'an existing run'}."
        if already_running
        else
        f"{result.get('label') or 'Tdarr Matrix audit'} completed with {finding_count} finding(s)."
        if success
        else f"{result.get('label') or 'Tdarr Matrix audit'} timed out."
        if timed_out
        else f"{result.get('label') or 'Tdarr Matrix audit'} found a stale incomplete run that requires review: {result.get('stale_reason') or 'unknown'}."
        if stale_incomplete_run
        else f"{result.get('label') or 'Tdarr Matrix audit'} failed with exit {_int_value(result.get('returncode'))}."
    )
    run_samples = mode == "run-samples"
    steps = [
        {
            "key": "prepare",
            "label": "Prepare Evidence",
            "status": "active" if background_started or already_running else "complete" if success else "blocked" if timed_out or stale_incomplete_run else "error",
            "detail": f"Action {action}; report-only={bool(result.get('report_only'))}.",
        },
        {
            "key": "samples",
            "label": "Sample Processing",
            "status": "active" if already_running else "pending" if background_started else "complete" if success and run_samples else "skipped" if not run_samples else "blocked" if timed_out or stale_incomplete_run else "error",
            "detail": (
                f"Selected {result.get('selected_count') or 0} generated source path(s)."
                if run_samples
                else "Report mode does not process sample files."
            ),
        },
        {
            "key": "report",
            "label": "Audit Report",
            "status": "pending" if background_started or already_running else "complete" if success and result.get("report_path") else "blocked" if success else "blocked" if timed_out or stale_incomplete_run else "error",
            "detail": f"Report: {result.get('report_path') or 'not written'}",
        },
    ]
    completed = sum(1 for step in steps if step["status"] in {"complete", "skipped"})
    percent = 1.0 if background_started or already_running else 100.0 if success else round((completed / len(steps)) * 100.0, 1)
    bar = {
        "id": "tdarr_matrix_audit",
        "label": "Tdarr Matrix audit",
        "mode": "stepped",
        "percent": percent,
        "status": status,
        "detail": detail,
        "source": TDARR_MATRIX_AUDIT_COMMAND,
        "stale": False,
        "step_index": completed,
        "step_total": len(steps),
    }
    return {
        "schema_version": TDARR_MATRIX_AUDIT_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "action": action,
        "mode": mode,
        "detail": detail,
        "steps": steps,
        "progress_bars": [bar],
    }


def tdarr_matrix_audit_invalid_action_result(action: Any) -> Any:
    normalized = normalize_tdarr_matrix_audit_action(action)
    message = f"Tdarr Matrix audit action is not allowed: {normalized}."
    return _command_result(
        command=TDARR_MATRIX_AUDIT_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=[message, f"Allowed actions: {', '.join(TDARR_MATRIX_AUDIT_ALLOWED_ACTIONS)}"],
        refresh_hint=TDARR_MATRIX_AUDIT_REFRESH_HINT,
        data={
            "action": normalized,
            "allowed_actions": list(TDARR_MATRIX_AUDIT_ALLOWED_ACTIONS),
            "writes_canonical_tdarr_cache": False,
        },
    )


def tdarr_matrix_audit_unavailable_result(reason: str) -> Any:
    return _command_result(
        command=TDARR_MATRIX_AUDIT_COMMAND,
        ok=False,
        message=f"Tdarr Matrix audit runner is not available: {reason}",
        severity="error",
        errors=[reason],
        refresh_hint=TDARR_MATRIX_AUDIT_REFRESH_HINT,
        data={"writes_canonical_tdarr_cache": False},
    )


def tdarr_matrix_audit_exception_result(exc: Exception) -> Any:
    error = _bounded_text(exc)
    return _command_result(
        command=TDARR_MATRIX_AUDIT_COMMAND,
        ok=False,
        message=f"Tdarr Matrix audit failed: {error}",
        severity="error",
        errors=[error],
        refresh_hint=TDARR_MATRIX_AUDIT_REFRESH_HINT,
        data={"writes_canonical_tdarr_cache": False},
    )


def tdarr_matrix_audit_result(result: dict[str, Any]) -> Any:
    success = bool(result.get("success"))
    timed_out = bool(result.get("timed_out"))
    background_started = bool(result.get("background_started"))
    returncode = _int_value(result.get("returncode"))
    finding_count = _int_value(result.get("finding_count"))
    mode = str(result.get("mode") or "")
    label = str(result.get("label") or "Tdarr Matrix audit")
    already_running = bool(result.get("already_running"))
    if background_started:
        message = f"{label} started in background as {result.get('run_id') or 'a new run'}."
    elif already_running:
        message = f"{label} is already running as {result.get('run_id') or 'an existing run'}."
    elif success:
        if mode == "run-samples":
            message = f"{label} complete: {result.get('selected_count') or 0} selected sample row(s), {finding_count} finding(s)."
        else:
            message = f"{label} complete: {result.get('manifest_count') or 0} manifest row(s), {finding_count} finding(s)."
    elif timed_out:
        message = f"{label} timed out."
    else:
        message = f"{label} failed with exit {returncode}."
    severity = "warning" if already_running else "info" if background_started else "warning" if success and finding_count else "info" if success else "warning" if timed_out else "error"
    error_text = _bounded_text(result.get("stderr") or result.get("stdout") or f"returncode={returncode}")
    progress = tdarr_matrix_audit_progress_payload(result)
    findings_preview = tdarr_matrix_audit_findings_preview(result.get("report_path"))
    data = {
        "schema_version": "desktop_tdarr_matrix_audit_result.v1",
        "action": result.get("action", ""),
        "label": label,
        "mode": mode,
        "report_only": bool(result.get("report_only")),
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": result.get("elapsed_seconds", 0.0),
        "background_started": background_started,
        "already_running": already_running,
        "run_id": str(result.get("run_id") or ""),
        "pid": _int_value(result.get("pid")),
        "command": result.get("command", ""),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "manifest_count": _int_value(result.get("manifest_count")),
        "selected_count": _int_value(result.get("selected_count")),
        "finding_count": finding_count,
        "report_path": str(result.get("report_path") or ""),
        "run_root": str(result.get("run_root") or ""),
        "library_root": str(result.get("library_root") or ""),
        "writes_canonical_tdarr_cache": False,
        "writes_tdarr_matrix_run_root": mode == "run-samples",
        "tdarr_matrix_audit_progress": progress,
        "progress_bars": progress["progress_bars"],
        **findings_preview,
        "findings_preview_limit": TDARR_MATRIX_AUDIT_FINDINGS_PREVIEW_LIMIT,
        "findings_preview_truncated": _int_value(findings_preview.get("findings_preview_total")) > TDARR_MATRIX_AUDIT_FINDINGS_PREVIEW_LIMIT,
    }
    return _command_result(
        command=TDARR_MATRIX_AUDIT_COMMAND,
        ok=success,
        message=message,
        severity=severity,
        errors=[] if success else [error_text],
        refresh_hint=TDARR_MATRIX_AUDIT_REFRESH_HINT,
        data=json_safe(data),
    )


class TdarrMatrixAuditServiceMixin:
    """Runs the Tdarr Matrix developer audit tool through the stable tool wrapper."""

    def tdarr_matrix_audit_python_path(self) -> Path:
        candidates = (
            self.workspace_root / "apps" / "desktop" / "runtime" / "Python" / "python.exe",
            self.app_root / "runtime" / "Python" / "python.exe",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path(sys.executable)

    def run_tdarr_matrix_audit(
        self,
        *,
        action: str,
        case_keys: list[str] | tuple[str, ...] | None = None,
        confirm_delete_full_matrix: bool = False,
    ) -> dict[str, Any]:
        preset = tdarr_matrix_audit_preset(action)
        if preset is None:
            raise ValueError(f"Unsupported Tdarr Matrix audit action: {action}")
        workspace_root = Path(self.workspace_root)
        runner = tdarr_matrix_runner_script(workspace_root)
        library_root = tdarr_matrix_default_library_root(workspace_root)
        runs_root = tdarr_matrix_default_runs_root(workspace_root)
        entrypoint = tdarr_matrix_default_entrypoint(workspace_root)
        python_path = self.tdarr_matrix_audit_python_path()
        tool_module = str(preset.get("tool_module") or TDARR_MATRIX_AUDIT_TOOL_MODULE)
        if not runner.exists():
            return self._tdarr_matrix_missing_result(preset, runner, library_root)
        manifest_path = library_root / "manifests" / "materialized_library.csv"
        if str(preset.get("mode") or "") in {"report", "run-samples"} and not manifest_path.exists():
            return self._tdarr_matrix_missing_library_result(preset, library_root, manifest_path)
        powershell = self._tdarr_matrix_powershell_host()
        background = bool(preset.get("background"))
        if background:
            existing_evidence = tdarr_matrix_incomplete_full_run_evidence(
                runs_root,
                selected_count=_int_value(preset.get("sample_count_hint")),
                psutil_module=psutil,
            )
            existing = existing_evidence.get("active")
            if existing is not None:
                return self._tdarr_matrix_existing_full_run_result(
                    preset=preset,
                    library_root=library_root,
                    run_root=existing,
                    process_state=existing_evidence.get("active_process") if isinstance(existing_evidence, dict) else None,
                )
            stale = existing_evidence.get("stale") if isinstance(existing_evidence, dict) else None
            if stale is not None:
                return self._tdarr_matrix_stale_full_run_result(
                    preset=preset,
                    library_root=library_root,
                    run_root=stale,
                    process_state=existing_evidence.get("stale_process") if isinstance(existing_evidence, dict) else None,
                )
        run_id = tdarr_matrix_background_run_id(str(preset["action"]), runs_root) if background else ""
        audit_args = tdarr_matrix_audit_arguments(
            action=str(preset["action"]),
            library_root=library_root,
            powershell=powershell,
            entrypoint=entrypoint,
            runs_root=runs_root,
            case_keys=case_keys,
            run_id=run_id,
            confirm_delete_full_matrix=confirm_delete_full_matrix,
        )
        args = [
            str(python_path),
            str(runner),
            tool_module,
            *audit_args,
        ]
        command_line = subprocess.list2cmdline(args)
        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.info("Tdarr Matrix audit requested: %s", command_line)
        env = self._tdarr_matrix_launch_environment()
        started = time.monotonic()
        if background:
            return self._run_tdarr_matrix_audit_background(
                args=args,
                command_line=command_line,
                workspace_root=workspace_root,
                env=env,
                preset=preset,
                library_root=library_root,
                runs_root=runs_root,
                run_id=run_id,
                started=started,
            )
        capture = run_capture(
            args,
            cwd=str(workspace_root),
            env=env,
            encoding="utf-8",
            errors="replace",
            timeout_seconds=tdarr_matrix_audit_runner_timeout(preset),
            extra_popen_kwargs=self._tdarr_matrix_subprocess_kwargs(),
            label="tdarr matrix audit",
            kill_tree=getattr(self, "kill_process_tree", None),
        )
        stdout = capture.stdout or ""
        parsed = _parse_last_json_object(stdout)
        stderr = capture.stderr or capture.kill_message or ""
        returncode = -1 if capture.returncode is None else int(capture.returncode)
        result: dict[str, Any] = {
            "success": returncode == 0 and not capture.timed_out,
            "timed_out": bool(capture.timed_out),
            "returncode": returncode,
            "command": command_line,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_seconds": time.monotonic() - started,
            "library_root": str(library_root),
            **preset,
            **parsed,
        }
        return result

    def _run_tdarr_matrix_audit_background(
        self,
        *,
        args: list[str],
        command_line: str,
        workspace_root: Path,
        env: dict[str, str],
        preset: dict[str, Any],
        library_root: Path,
        runs_root: Path,
        run_id: str,
        started: float,
    ) -> dict[str, Any]:
        runs_root.mkdir(parents=True, exist_ok=True)
        log_root = runs_root / "_background"
        log_root.mkdir(parents=True, exist_ok=True)
        stdout_path = log_root / f"{run_id}.stdout.log"
        stderr_path = log_root / f"{run_id}.stderr.log"
        stdout_handle = stdout_path.open("ab")
        stderr_handle = stderr_path.open("ab")
        kwargs: dict[str, Any] = {
            "cwd": str(workspace_root),
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": stdout_handle,
            "stderr": stderr_handle,
        }
        kwargs.update(self._tdarr_matrix_subprocess_kwargs())
        if os.name == "nt":
            kwargs.setdefault(
                "creationflags",
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            kwargs.setdefault("start_new_session", True)
        try:
            proc = subprocess.Popen(args, **kwargs)
        finally:
            stdout_handle.close()
            stderr_handle.close()
        run_root = runs_root / run_id
        audit_dir = run_root / "manifests" / "audit"
        pid = int(getattr(proc, "pid", 0) or 0)
        process_start_time = _tdarr_matrix_process_start_time_text(pid, psutil_module=psutil)
        process_metadata = {
            "schema_version": "tdarr_matrix_background_process.v1",
            "run_id": run_id,
            "pid": pid,
            "process_start_time": process_start_time,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
        try:
            _tdarr_matrix_background_process_metadata_path(runs_root, run_id).write_text(
                json.dumps(process_metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        return {
            "success": True,
            "timed_out": False,
            "background_started": True,
            "returncode": 0,
            "pid": pid,
            "run_id": run_id,
            "command": command_line,
            "stdout": f"Background stdout: {stdout_path}",
            "stderr": f"Background stderr: {stderr_path}",
            "elapsed_seconds": time.monotonic() - started,
            "library_root": str(library_root),
            "run_root": str(run_root),
            "report_path": str(audit_dir / "tdarr_matrix_audit_report.json"),
            "selected_count": _int_value(preset.get("sample_count_hint")),
            "finding_count": 0,
            **preset,
        }

    def _tdarr_matrix_existing_full_run_result(
        self,
        *,
        preset: dict[str, Any],
        library_root: Path,
        run_root: Path,
        process_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = run_root.name
        audit_dir = run_root / "manifests" / "audit"
        process_state = process_state or {}
        return {
            "success": True,
            "timed_out": False,
            "already_running": True,
            "returncode": 0,
            "pid": _int_value(process_state.get("pid")),
            "run_id": run_id,
            "command": "",
            "stdout": "",
            "stderr": "",
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            "run_root": str(run_root),
            "report_path": str(audit_dir / "tdarr_matrix_audit_report.json"),
            "selected_count": _int_value(preset.get("sample_count_hint")),
            "finding_count": 0,
            **preset,
        }

    def _tdarr_matrix_stale_full_run_result(
        self,
        *,
        preset: dict[str, Any],
        library_root: Path,
        run_root: Path,
        process_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = run_root.name
        audit_dir = run_root / "manifests" / "audit"
        process_state = process_state or {}
        stale_reason = str(process_state.get("reason") or "stale_incomplete_run")
        return {
            "success": False,
            "timed_out": False,
            "already_running": False,
            "stale_incomplete_run": True,
            "stale_reason": stale_reason,
            "returncode": 2,
            "pid": _int_value(process_state.get("pid")),
            "run_id": run_id,
            "command": "",
            "stdout": "",
            "stderr": f"Stale Tdarr Proof Pack run requires review before another proof run starts: {stale_reason}",
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            "run_root": str(run_root),
            "report_path": str(audit_dir / "tdarr_matrix_audit_report.json"),
            "selected_count": _int_value(preset.get("sample_count_hint")),
            "finding_count": 0,
            "process_metadata_path": str(process_state.get("metadata_path") or ""),
            **preset,
        }

    def _tdarr_matrix_missing_result(self, preset: dict[str, Any], runner: Path, library_root: Path) -> dict[str, Any]:
        return {
            "success": False,
            "timed_out": False,
            "returncode": 127,
            "command": f'"{self.tdarr_matrix_audit_python_path()}" "{runner}" {TDARR_MATRIX_AUDIT_TOOL_MODULE}',
            "stdout": "",
            "stderr": f"Tdarr Matrix audit runner not found: {runner}",
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            **preset,
        }

    def _tdarr_matrix_missing_library_result(self, preset: dict[str, Any], library_root: Path, manifest_path: Path) -> dict[str, Any]:
        guidance = (
            "python -m mediapipeline.tools.dev.tdarr_proof_pack materialize"
        )
        return {
            "success": False,
            "timed_out": False,
            "returncode": 2,
            "command": "",
            "stdout": "",
            "stderr": (
                f"Tdarr Proof Pack is not materialized (missing {manifest_path}). "
                f"Generate it first, then re-run this audit: {guidance}"
            ),
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            **preset,
        }

    def _tdarr_matrix_powershell_host(self) -> str:
        resolver = getattr(self, "resolve_powershell_host", None)
        if callable(resolver):
            resolved = resolver()
            if resolved:
                return str(resolved)
        return "pwsh"

    def _tdarr_matrix_launch_environment(self) -> dict[str, str]:
        builder = getattr(self, "_build_launch_environment", None)
        env = builder() if callable(builder) else dict(os.environ)
        src_root = Path(self.workspace_root) / "src"
        if src_root.exists():
            src_root_text = str(src_root)
            existing = env.get("PYTHONPATH", "")
            parts = [part for part in existing.split(os.pathsep) if part]
            if src_root_text.casefold() not in {part.casefold() for part in parts}:
                parts.insert(0, src_root_text)
            env["PYTHONPATH"] = os.pathsep.join(parts)
        return env

    def _tdarr_matrix_subprocess_kwargs(self) -> dict[str, Any]:
        kwargs = getattr(self, "_subprocess_kwargs_hidden", None)
        if callable(kwargs):
            value = kwargs()
            return dict(value or {}) if isinstance(value, dict) else {}
        return {}


__all__ = [
    "TDARR_MATRIX_AUDIT_ALLOWED_ACTIONS",
    "TDARR_MATRIX_AUDIT_BUCKET_COUNT",
    "TDARR_MATRIX_AUDIT_COMMAND",
    "TDARR_MATRIX_AUDIT_PRESETS",
    "TDARR_MATRIX_AUDIT_PROGRESS_SCHEMA_VERSION",
    "TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS",
    "TDARR_MATRIX_AUDIT_FINDINGS_PREVIEW_LIMIT",
    "TdarrMatrixAuditServiceMixin",
    "tdarr_matrix_background_run_id",
    "tdarr_matrix_incomplete_full_run_evidence",
    "tdarr_matrix_incomplete_full_run",
    "normalize_tdarr_matrix_audit_action",
    "tdarr_matrix_audit_arguments",
    "tdarr_matrix_audit_findings_preview",
    "tdarr_matrix_audit_runner_timeout",
    "tdarr_matrix_audit_exception_result",
    "tdarr_matrix_audit_invalid_action_result",
    "tdarr_matrix_audit_preset",
    "tdarr_matrix_audit_progress_payload",
    "tdarr_matrix_audit_result",
    "tdarr_matrix_audit_unavailable_result",
]
