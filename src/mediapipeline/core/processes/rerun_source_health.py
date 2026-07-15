"""Backend-owned source availability and identity classification for CSV reruns."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path, PureWindowsPath
import stat
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.source_probe import run_source_probe


SOURCE_HEALTH_SCHEMA_VERSION = "desktop_rerun_source_health.v1"
SOURCE_AVAILABLE = "source_available"
SOURCE_LOCATION_UNAVAILABLE = "source_location_unavailable"
SOURCE_MISSING = "source_missing"
SOURCE_ACCESS_FAILED = "source_access_failed"
SOURCE_IDENTITY_CHANGED = "source_identity_changed"
SOURCE_PROBE_TIMEOUT_SECONDS = 2.0
RootProbeCache = dict[str, tuple[bool, os.stat_result | BaseException]]


@dataclass(frozen=True)
class RerunSourceHealth:
    code: str
    detail: str
    source_path: str
    source_root: str
    root_reachable: bool
    source_exists: bool
    retryable: bool
    operator_action_required: bool
    automatic_next_action: str
    available_operator_action: str
    observed_at: str
    observed_size: int | None = None
    observed_mtime_utc: str = ""

    @property
    def available(self) -> bool:
        return self.code == SOURCE_AVAILABLE

    @property
    def waiting(self) -> bool:
        return self.code in {SOURCE_LOCATION_UNAVAILABLE, SOURCE_ACCESS_FAILED}

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": SOURCE_HEALTH_SCHEMA_VERSION,
            "code": self.code,
            "detail": self.detail,
            "source_path": self.source_path,
            "source_root": self.source_root,
            "root_reachable": self.root_reachable,
            "source_exists": self.source_exists,
            "retryable": self.retryable,
            "operator_action_required": self.operator_action_required,
            "automatic_next_action": self.automatic_next_action,
            "available_operator_action": self.available_operator_action,
            "observed_at": self.observed_at,
            "observed_size": self.observed_size,
            "observed_mtime_utc": self.observed_mtime_utc,
        }


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_value(mapping: Mapping[str, Any], *names: str) -> str:
    lowered = {str(key).casefold(): value for key, value in mapping.items()}
    for name in names:
        text = _clean_text(lowered.get(name.casefold()))
        if text:
            return text
    return ""


def _windows_parts(value: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in PureWindowsPath(value).parts)


def _native_parts(value: str) -> tuple[str, ...]:
    return tuple(os.path.normcase(part) for part in Path(value).parts)


def _looks_windows_path(value: str) -> bool:
    path = PureWindowsPath(value)
    return bool(path.drive or value.startswith(("\\\\", "//")))


def _parts(value: str) -> tuple[str, ...]:
    return _windows_parts(value) if _looks_windows_path(value) else _native_parts(value)


def _path_is_under(source_path: str, root_path: str) -> bool:
    source_parts = _parts(source_path)
    root_parts = _parts(root_path)
    return bool(root_parts) and len(source_parts) >= len(root_parts) and source_parts[: len(root_parts)] == root_parts


def _configured_roots(resolved: ResolvedPaths | None) -> list[str]:
    if resolved is None:
        return []
    candidates: list[str] = []
    for attr in ("source_movies", "source_tv"):
        text = _clean_text(getattr(resolved, attr, None))
        if text:
            candidates.append(text)
    config = getattr(resolved, "config_data", None)
    if isinstance(config, Mapping):
        lowered = {str(key).casefold(): value for key, value in config.items()}
        for key in ("sourcemovies", "sourcetv"):
            text = _clean_text(lowered.get(key))
            if text:
                candidates.append(text)
        profiles = lowered.get("libraryprofiles")
        if isinstance(profiles, Iterable) and not isinstance(profiles, (str, bytes, Mapping)):
            for profile in profiles:
                if not isinstance(profile, Mapping):
                    continue
                text = _mapping_value(profile, "source_path", "source_root", "SourcePath", "SourceRoot")
                if text:
                    candidates.append(text)
    deduped: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for item in candidates:
        root_key = _parts(item)
        if root_key and root_key not in seen:
            seen.add(root_key)
            deduped.append(item)
    return deduped


def _source_root(source_path: str, resolved: ResolvedPaths | None) -> str:
    matches = [root for root in _configured_roots(resolved) if _path_is_under(source_path, root)]
    if matches:
        return max(matches, key=lambda item: len(_parts(item)))
    if _looks_windows_path(source_path):
        return PureWindowsPath(source_path).anchor
    return Path(source_path).anchor


def _health(
    *,
    code: str,
    detail: str,
    source_path: str,
    source_root: str,
    root_reachable: bool,
    source_exists: bool,
    retryable: bool,
    operator_action_required: bool,
    automatic_next_action: str,
    available_operator_action: str,
    observed_size: int | None = None,
    observed_mtime_utc: str = "",
) -> RerunSourceHealth:
    return RerunSourceHealth(
        code=code,
        detail=detail,
        source_path=source_path,
        source_root=source_root,
        root_reachable=root_reachable,
        source_exists=source_exists,
        retryable=retryable,
        operator_action_required=operator_action_required,
        automatic_next_action=automatic_next_action,
        available_operator_action=available_operator_action,
        observed_at=datetime.now(UTC).isoformat(),
        observed_size=observed_size,
        observed_mtime_utc=observed_mtime_utc,
    )


def _expected_size(row: Mapping[str, Any] | None) -> int | None:
    if not isinstance(row, Mapping):
        return None
    text = _mapping_value(row, "source_size", "SourceSizeBytes", "SizeBytes")
    try:
        parsed = int(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _expected_mtime(row: Mapping[str, Any] | None) -> datetime | None:
    if not isinstance(row, Mapping):
        return None
    text = _mapping_value(row, "source_mtime_utc", "SourceLastWriteUtc", "LastWriteTimeUtc")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _bounded_stat(path: Path, *, timeout_seconds: float = SOURCE_PROBE_TIMEOUT_SECONDS) -> os.stat_result:
    payload = run_source_probe("stat", path, timeout_seconds=timeout_seconds)
    kind = str(payload.get("kind") or "other").casefold()
    mode = stat.S_IFREG if kind == "file" else stat.S_IFDIR if kind == "directory" else 0
    try:
        size = max(0, int(payload.get("size") or 0))
        mtime = float(payload.get("mtime") or 0.0)
    except (TypeError, ValueError) as exc:
        raise OSError("source probe returned invalid stat evidence") from exc
    return os.stat_result((mode, 0, 0, 0, 0, 0, size, mtime, mtime, mtime))


def _bounded_root_stat(root: Path, cache: RootProbeCache | None) -> os.stat_result:
    if cache is None:
        return _bounded_stat(root)
    key = os.path.normcase(str(root))
    cached = cache.get(key)
    if cached is None:
        try:
            value: os.stat_result | BaseException = _bounded_stat(root)
            cached = (True, value)
        except BaseException as exc:
            cached = (False, exc)
        cache[key] = cached
    ok, value = cached
    if ok:
        return value  # type: ignore[return-value]
    raise value  # type: ignore[misc]


def probe_rerun_source_health(
    source_path: str,
    *,
    resolved: ResolvedPaths | None,
    row: Mapping[str, Any] | None = None,
    root_probe_cache: RootProbeCache | None = None,
) -> RerunSourceHealth:
    """Classify root reachability, leaf presence/access, and cheap identity evidence.

    Full ``source_identity_v2`` verification remains a PowerShell staging
    boundary because recomputing sampled media identity during an API preview
    can be expensive. Size and mtime evidence are still checked here so an
    already-visible change is blocked before staging.
    """

    source_text = _clean_text(source_path)
    root_text = _source_root(source_text, resolved)
    source = Path(source_text)
    root = Path(root_text) if root_text else None
    try:
        if root is None:
            raise FileNotFoundError("source root could not be determined")
        root_stat = _bounded_root_stat(root, root_probe_cache)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise FileNotFoundError("configured source root is not a directory")
    except FileNotFoundError:
        return _health(
            code=SOURCE_LOCATION_UNAVAILABLE,
            detail=f"Configured source root is temporarily unavailable: {root_text or '<unknown>'}",
            source_path=source_text,
            source_root=root_text,
            root_reachable=False,
            source_exists=False,
            retryable=True,
            operator_action_required=False,
            automatic_next_action="Wait for the source location, then retry the availability probe with bounded backoff.",
            available_operator_action="Restore the mapped drive/share or request Retry now.",
        )
    except (PermissionError, TimeoutError, OSError) as exc:
        return _health(
            code=SOURCE_ACCESS_FAILED,
            detail=f"Source root access failed: {exc}",
            source_path=source_text,
            source_root=root_text,
            root_reachable=False,
            source_exists=False,
            retryable=True,
            operator_action_required=False,
            automatic_next_action="Retry the source access probe with bounded backoff.",
            available_operator_action="Check credentials/permissions or request Retry now.",
        )

    try:
        source_stat = _bounded_stat(source)
        if not stat.S_ISREG(source_stat.st_mode):
            raise FileNotFoundError("source path is not a regular file")
    except FileNotFoundError:
        return _health(
            code=SOURCE_MISSING,
            detail=f"Source root is reachable but the source file was not found at the expected path: {source_text}",
            source_path=source_text,
            source_root=root_text,
            root_reachable=True,
            source_exists=False,
            retryable=False,
            operator_action_required=True,
            automatic_next_action="Do not stage or retry automatically.",
            available_operator_action="Restore the expected file or update the CSV after verifying source identity.",
        )
    except (PermissionError, TimeoutError, OSError) as exc:
        return _health(
            code=SOURCE_ACCESS_FAILED,
            detail=f"Source file access failed: {exc}",
            source_path=source_text,
            source_root=root_text,
            root_reachable=True,
            source_exists=False,
            retryable=True,
            operator_action_required=False,
            automatic_next_action="Retry the source access probe with bounded backoff.",
            available_operator_action="Check credentials/permissions or request Retry now.",
        )

    observed_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC)
    expected_size = _expected_size(row)
    expected_mtime = _expected_mtime(row)
    identity_reasons: list[str] = []
    if expected_size is not None and expected_size != source_stat.st_size:
        identity_reasons.append(f"size expected={expected_size} observed={source_stat.st_size}")
    if expected_mtime is not None and abs((observed_mtime - expected_mtime).total_seconds()) > 2:
        identity_reasons.append(
            f"mtime expected={expected_mtime.isoformat()} observed={observed_mtime.isoformat()}"
        )
    if identity_reasons:
        return _health(
            code=SOURCE_IDENTITY_CHANGED,
            detail="Source identity changed: " + "; ".join(identity_reasons),
            source_path=source_text,
            source_root=root_text,
            root_reachable=True,
            source_exists=True,
            retryable=False,
            operator_action_required=True,
            automatic_next_action="Do not copy or resume this row automatically.",
            available_operator_action="Review the changed source and generate a new CSV or explicitly re-plan the row.",
            observed_size=source_stat.st_size,
            observed_mtime_utc=observed_mtime.isoformat(),
        )

    return _health(
        code=SOURCE_AVAILABLE,
        detail="Source root and expected file are reachable; staging must still revalidate full source identity.",
        source_path=source_text,
        source_root=root_text,
        root_reachable=True,
        source_exists=True,
        retryable=False,
        operator_action_required=False,
        automatic_next_action="Revalidate source identity at the staging boundary, then copy to scratch.",
        available_operator_action="No operator action is required.",
        observed_size=source_stat.st_size,
        observed_mtime_utc=observed_mtime.isoformat(),
    )


__all__ = [
    "RerunSourceHealth",
    "SOURCE_ACCESS_FAILED",
    "SOURCE_AVAILABLE",
    "SOURCE_HEALTH_SCHEMA_VERSION",
    "SOURCE_IDENTITY_CHANGED",
    "SOURCE_LOCATION_UNAVAILABLE",
    "SOURCE_MISSING",
    "SOURCE_PROBE_TIMEOUT_SECONDS",
    "probe_rerun_source_health",
]
