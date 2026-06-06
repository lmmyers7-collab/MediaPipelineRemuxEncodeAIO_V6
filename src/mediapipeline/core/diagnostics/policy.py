"""Read-only diagnostics payload and summary policy helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import os
from pathlib import Path
import re
import stat
from typing import Any

from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from mediapipeline.core.status.active_jobs import active_job_detail_rows

DIAGNOSTICS_TAIL_SCHEMA_VERSION = "desktop_diagnostics_tail.v1"
DIAGNOSTICS_TAIL_DEFAULT_MAX_BYTES = 65_536
DIAGNOSTICS_TAIL_MIN_BYTES = 1_024
DIAGNOSTICS_TAIL_MAX_BYTES = 262_144
DIAGNOSTICS_TAIL_ISSUE_LINE_LIMIT = 5

_DIAGNOSTICS_TAIL_ERROR_TERMS = (
    "error",
    "failed",
    "failure",
    "exception",
    "traceback",
    "denied",
    "blocked",
    "corrupt",
    "malformed",
    "invalid",
    "unreadable",
    "locked",
    "fatal",
)
_DIAGNOSTICS_TAIL_WARNING_TERMS = (
    "warn",
    "warning",
    "stale",
    "orphan",
    "missing",
    "retry",
    "timeout",
    "partial",
    "unknown",
    "skipped",
)
_DIAGNOSTICS_TAIL_ACTIVE_TERMS = (
    "active",
    "running",
    "processing",
    "launching",
    "publishing",
    "ffmpeg",
    "ffprobe",
    "powershell",
)
_DIAGNOSTICS_TAIL_STATE_TERMS = (
    "activejobs",
    "queue",
    "completed",
    "pending",
    "manifest",
    "sidecar",
    "progress",
    "pid",
)
_DIAGNOSTICS_TAIL_NEGATED_ERROR_RE = re.compile(
    r"\b(?:no|without)\b(?:\s+[\w-]+){0,4}\s+errors?\b"
    r"|\b0\s+errors?\b"
    r"|\berrors?\s*[:=]\s*0\b"
    r"|\berror[_ -]?count\s*[:=]\s*0\b"
)
_DIAGNOSTICS_TAIL_NEGATED_FAILURE_RE = re.compile(
    r"\b(?:no|without)\b(?:\s+[\w-]+){0,4}\s+fail(?:ed|ures?|ure)?\b"
    r"|\b0\s+fail(?:ed|ures?|ure)?\b"
    r"|\bfail(?:ed|ures?|ure)?\s*[:=]\s*0\b"
)


def _split_summary_lines(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [str(item) for item in value if str(item).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _diagnostics_tail_status_state(operator_status: str) -> str:
    normalized = str(operator_status or "").strip().casefold().replace("_", " ")
    if normalized in {"blocked", "error", "critical", "failed"}:
        return "blocked"
    if normalized in {"review", "not available", "unavailable"}:
        return "warning"
    if normalized == "active":
        return "running"
    if normalized in {"ready", "empty", "unknown"}:
        return normalized
    return "unknown"


def diagnostics_tail_line_contains_term(line: str, term: str) -> bool:
    folded = str(line or "").casefold()
    needle = str(term or "").casefold()
    if not needle:
        return False
    if needle == "error" and _DIAGNOSTICS_TAIL_NEGATED_ERROR_RE.search(folded):
        return False
    if needle in {"failed", "failure"} and _DIAGNOSTICS_TAIL_NEGATED_FAILURE_RE.search(folded):
        return False
    return needle in folded


def _line_contains_any(line: str, terms: tuple[str, ...]) -> bool:
    return any(diagnostics_tail_line_contains_term(line, term) for term in terms)


def _tail_issue_lines(lines: list[str], terms: tuple[str, ...]) -> list[str]:
    matches = [line for line in lines if _line_contains_any(line, terms)]
    return matches[-DIAGNOSTICS_TAIL_ISSUE_LINE_LIMIT:]


def diagnostics_tail_evidence(
    *,
    text: str,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    ok: bool = False,
    exists: bool = False,
    is_file: bool = False,
    truncated: bool = False,
) -> dict[str, Any]:
    """Summarize bounded diagnostics-tail text without adding new file access."""
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    warning_rows = list(warnings or [])
    error_rows = list(errors or [])
    error_lines = _tail_issue_lines(lines, _DIAGNOSTICS_TAIL_ERROR_TERMS)
    warning_lines = _tail_issue_lines(lines, _DIAGNOSTICS_TAIL_WARNING_TERMS)
    active_lines = _tail_issue_lines(lines, _DIAGNOSTICS_TAIL_ACTIVE_TERMS)
    state_lines = _tail_issue_lines(lines, _DIAGNOSTICS_TAIL_STATE_TERMS)
    error_count = sum(1 for line in lines if _line_contains_any(line, _DIAGNOSTICS_TAIL_ERROR_TERMS))
    warning_count = sum(1 for line in lines if _line_contains_any(line, _DIAGNOSTICS_TAIL_WARNING_TERMS))
    active_count = sum(1 for line in lines if _line_contains_any(line, _DIAGNOSTICS_TAIL_ACTIVE_TERMS))
    state_count = sum(1 for line in lines if _line_contains_any(line, _DIAGNOSTICS_TAIL_STATE_TERMS))

    if error_rows or error_count:
        operator_status = "blocked"
        safe_next_action = "Read the issue lines, then compare with the owning page and ActiveJobs before retrying, closing, draining, or rerunning."
    elif warning_rows or warning_count or truncated:
        operator_status = "review"
        safe_next_action = "Review the warning/truncation evidence and compare with the owning page before changing workflow state."
    elif active_count:
        operator_status = "active"
        safe_next_action = "Compare active-process clues with Close Readiness and ActiveJobs before starting or closing work."
    elif ok and exists and is_file and lines:
        operator_status = "ready"
        safe_next_action = "No high-risk tail terms were detected in the returned window; still verify against the owning page before accepting a run."
    elif ok and exists and is_file:
        operator_status = "empty"
        safe_next_action = "The target file exists but returned no text in the bounded window; compare with artifact age and owning-page state."
    else:
        operator_status = "unavailable"
        safe_next_action = "Use the warnings/errors and State Artifact Summary to determine whether the artifact is expected to exist."

    return {
        "evidence_authority": "backend",
        "operator_status": operator_status,
        "operator_status_state": _diagnostics_tail_status_state(operator_status),
        "line_count": len(lines),
        "error_count": error_count + len(error_rows),
        "warning_count": warning_count + len(warning_rows),
        "active_count": active_count,
        "state_count": state_count,
        "truncated": bool(truncated),
        "issue_lines": error_lines,
        "warning_lines": warning_lines,
        "active_lines": active_lines,
        "state_lines": state_lines,
        "safe_next_action": safe_next_action,
        "guardrail": "Diagnostics tail evidence is read-only and comes from backend allowlisted targets only.",
    }


def clamp_diagnostics_tail_bytes(value: int | str | None) -> int:
    try:
        requested = int(value if value is not None else DIAGNOSTICS_TAIL_DEFAULT_MAX_BYTES)
    except (TypeError, ValueError):
        requested = DIAGNOSTICS_TAIL_DEFAULT_MAX_BYTES
    return max(DIAGNOSTICS_TAIL_MIN_BYTES, min(DIAGNOSTICS_TAIL_MAX_BYTES, requested))


def diagnostics_tail_base_payload(
    *,
    target: str,
    label: str,
    path: Path | None,
    max_bytes: int,
    ok: bool,
    exists: bool = False,
    is_file: bool = False,
    size_bytes: int = 0,
    truncated: bool = False,
    text: str = "",
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    normalized_warnings = list(warnings or [])
    normalized_errors = list(errors or [])
    return {
        "schema_version": DIAGNOSTICS_TAIL_SCHEMA_VERSION,
        "ok": bool(ok),
        "target": str(target or ""),
        "label": str(label or target or ""),
        "path": str(path or ""),
        "exists": bool(exists),
        "is_file": bool(is_file),
        "size_bytes": int(size_bytes or 0),
        "max_bytes": int(max_bytes),
        "truncated": bool(truncated),
        "text": str(text or ""),
        "warnings": normalized_warnings,
        "errors": normalized_errors,
        "evidence": diagnostics_tail_evidence(
            text=str(text or ""),
            warnings=normalized_warnings,
            errors=normalized_errors,
            ok=bool(ok),
            exists=bool(exists),
            is_file=bool(is_file),
            truncated=bool(truncated),
        ),
    }


def diagnostics_tail_disallowed_payload(target: str, max_bytes: int, allowed_targets_message: str) -> dict[str, Any]:
    return diagnostics_tail_base_payload(
        target=target,
        label=target,
        path=None,
        max_bytes=max_bytes,
        ok=False,
        errors=["Diagnostics tail target is not allowed.", allowed_targets_message],
    )


def diagnostics_tail_missing_payload(target: str, label: str, max_bytes: int) -> dict[str, Any]:
    return diagnostics_tail_base_payload(
        target=target,
        label=label,
        path=None,
        max_bytes=max_bytes,
        ok=False,
        warnings=[f"No path is configured for {label}."],
    )


def diagnostics_tail_file_payload(target: str, label: str, path: Path, max_bytes: int) -> dict[str, Any]:
    try:
        path_stat = path.stat()
    except FileNotFoundError:
        return diagnostics_tail_base_payload(
            target=target,
            label=label,
            path=path,
            max_bytes=max_bytes,
            ok=False,
            warnings=[f"{label} does not exist yet."],
        )
    except OSError as exc:
        return diagnostics_tail_base_payload(
            target=target,
            label=label,
            path=path,
            max_bytes=max_bytes,
            ok=False,
            errors=[f"Could not inspect {label}: {exc}"],
        )

    size_bytes = int(path_stat.st_size)
    is_file = stat.S_ISREG(path_stat.st_mode)
    if not is_file:
        return diagnostics_tail_base_payload(
            target=target,
            label=label,
            path=path,
            max_bytes=max_bytes,
            ok=False,
            exists=True,
            is_file=False,
            size_bytes=size_bytes,
            warnings=[f"{label} resolves to a folder or non-regular file. Use Open Locations for this target."],
        )

    try:
        with path.open("rb") as handle:
            if size_bytes > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
            raw = handle.read(max_bytes)
    except OSError as exc:
        return diagnostics_tail_base_payload(
            target=target,
            label=label,
            path=path,
            max_bytes=max_bytes,
            ok=False,
            exists=True,
            is_file=True,
            size_bytes=size_bytes,
            errors=[f"Could not read {label}: {exc}"],
        )

    return diagnostics_tail_base_payload(
        target=target,
        label=label,
        path=path,
        max_bytes=max_bytes,
        ok=True,
        exists=True,
        is_file=True,
        size_bytes=size_bytes,
        truncated=size_bytes > max_bytes,
        text=raw.decode("utf-8", errors="replace"),
    )


def diagnostics_active_job_rows(method: Callable[[ResolvedPaths], object] | None, resolved: ResolvedPaths) -> list[str]:
    if not callable(method):
        return []
    try:
        return [str(item) for item in method(resolved)]  # type: ignore[misc]
    except Exception as exc:
        return [f"ActiveJobs summary unavailable: {exc}"]


def diagnostics_active_job_detail_rows(resolved: ResolvedPaths) -> list[dict[str, Any]]:
    try:
        return active_job_detail_rows(resolved.active_jobs_path)
    except Exception as exc:
        return [{"source": "unavailable", "status": "unavailable", "issue": f"ActiveJobs detail unavailable: {exc}"}]


def diagnostics_summary_lines(method_name: str, method: Callable[[Snapshot], object] | None, snapshot: Snapshot) -> list[str]:
    if not callable(method):
        return []
    try:
        return _split_summary_lines(method(snapshot))  # type: ignore[misc]
    except Exception as exc:
        return [f"{method_name} unavailable: {exc}"]


def diagnostics_launch_log_summary(method: Callable[[], object] | None) -> str:
    if not callable(method):
        return ""
    try:
        return str(method() or "")  # type: ignore[misc]
    except Exception as exc:
        return f"Launch log summary unavailable: {exc}"


def diagnostics_warnings(snapshot: Snapshot) -> list[str]:
    if snapshot.last_error:
        return [str(snapshot.last_error)]
    return []

__all__ = [
    "DIAGNOSTICS_TAIL_SCHEMA_VERSION",
    "DIAGNOSTICS_TAIL_DEFAULT_MAX_BYTES",
    "DIAGNOSTICS_TAIL_MIN_BYTES",
    "DIAGNOSTICS_TAIL_MAX_BYTES",
    "DIAGNOSTICS_TAIL_ISSUE_LINE_LIMIT",
    "diagnostics_tail_line_contains_term",
    "diagnostics_tail_evidence",
    "clamp_diagnostics_tail_bytes",
    "diagnostics_tail_base_payload",
    "diagnostics_tail_disallowed_payload",
    "diagnostics_tail_missing_payload",
    "diagnostics_tail_file_payload",
    "diagnostics_active_job_rows",
    "diagnostics_active_job_detail_rows",
    "diagnostics_summary_lines",
    "diagnostics_launch_log_summary",
    "diagnostics_warnings",
]
