from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
from typing import Any

from ...models import ResolvedPaths


SAMPLE_VALIDATION_RECONCILIATION_SCHEMA = "desktop_sample_validation_reconciliation.v1"
SAMPLE_VALIDATION_CURRENT_EVIDENCE_SCHEMA = "desktop_sample_validation_current_evidence.v1"
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600


def sample_validation_reconciliation_payload(
    resolved: ResolvedPaths,
    records: list[Mapping[str, Any]],
    *,
    artifact_errors: list[str] | None = None,
) -> dict[str, Any]:
    """Compare recent validation records with current backend-read evidence.

    This is intentionally a stale-evidence detector, not an output acceptance
    rule. It reads bounded backend artifacts and never probes arbitrary media
    paths or mutates state.
    """

    errors = list(artifact_errors or [])
    index = _current_validation_artifact_index(resolved, errors)
    rows = [_reconcile_validation_record(record, index) for record in records[:10]]
    stale_count = sum(1 for row in rows if row.get("status") == "stale")
    review_count = sum(1 for row in rows if row.get("severity") == "warning")
    current_count = sum(1 for row in rows if row.get("status") == "current")
    if errors:
        operator_status = "blocked"
        safe_next_action = "Resolve unreadable backend evidence before trusting historical sample validation records."
    elif not records:
        operator_status = "not-started"
        safe_next_action = "No sample validation records are loaded; run a known sample and record evidence after comparing current artifacts."
    elif stale_count:
        operator_status = "stale"
        safe_next_action = "Treat stale validation records as historical notes only; rerun or re-check the sample before daily-driver trust."
    elif review_count:
        operator_status = "review"
        safe_next_action = "Current evidence exists but has review conditions; inspect the record row before relying on it."
    elif current_count:
        operator_status = "current"
        safe_next_action = "Recent validation records still match current backend evidence; still verify playback/output manually before relying on WebView daily use."
    else:
        operator_status = "unknown"
        safe_next_action = "Current backend evidence is inconclusive; compare Queue, Completed, Pending Publish, and Diagnostics manually."
    summary_lines = [
        f"Reconciliation posture: {operator_status}",
        f"Recent records checked: {len(rows)}; current={current_count}; review={review_count}; stale={stale_count}; errors={len(errors)}",
        f"Safe next action: {safe_next_action}",
        "Boundary: reconciliation is read-only historical evidence comparison and cannot accept, repair, rerun, drain, publish, rewrite, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_RECONCILIATION_SCHEMA,
        "operator_status": operator_status,
        "record_count": len(records),
        "checked_count": len(rows),
        "current_count": current_count,
        "review_count": review_count,
        "stale_count": stale_count,
        "error_count": len(errors),
        "rows": rows,
        "artifact_counts": {
            "queue_sources": len(index["queue_sources"]),
            "completed_sources": len(index["completed_sources"]),
            "completed_outputs": len(index["completed_outputs"]),
            "pending_path_clues": len(index["pending_path_clues"]),
            "diagnostics_loaded": bool(index["diagnostics_text"]),
        },
        "errors": errors,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only stale-evidence comparison. This does not mark jobs complete, clear failures, drain pending publish, "
            "rewrite manifests/sidecars, launch work, save settings, rename files, or probe/mutate source/output/scratch media."
        ),
    }


def sample_validation_current_evidence_payload(resolved: ResolvedPaths, record: Mapping[str, Any]) -> dict[str, Any]:
    """Compare one proposed validation record with current bounded backend evidence."""

    errors: list[str] = []
    row = _reconcile_validation_record(record, _current_validation_artifact_index(resolved, errors))
    return {
        "schema_version": SAMPLE_VALIDATION_CURRENT_EVIDENCE_SCHEMA,
        "record_id": row.get("record_id", ""),
        "sample_label": row.get("sample_label", ""),
        "status": row.get("status", "unknown"),
        "severity": row.get("severity", "warning"),
        "matches": row.get("matches", {}),
        "missing_current_evidence": row.get("missing_current_evidence", []),
        "evidence": row.get("evidence", ""),
        "safe_next_action": row.get("safe_next_action", ""),
        "artifact_errors": errors,
        "guardrail": (
            "Read-only current-evidence preview. This does not mark jobs complete, clear failures, drain pending publish, "
            "rewrite manifests/sidecars, launch work, save settings, rename files, or probe/mutate source/output/scratch media."
        ),
    }


def _current_validation_artifact_index(resolved: ResolvedPaths, errors: list[str]) -> dict[str, Any]:
    queue_sources: set[str] = set()
    completed_sources: set[str] = set()
    completed_outputs: set[str] = set()
    pending_path_tokens: set[str] = set()
    pending_text_parts: list[str] = []
    diagnostics_parts: list[str] = []

    path = resolved.queue_snapshot_path
    if path and Path(path).exists():
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            for row in _payload_rows(payload, "rows", "queue"):
                for value in _row_path_values(row, ("source_path", "source", "input_path", "file_path", "path")):
                    _add_path_token(queue_sources, value)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Queue snapshot could not be read for sample-validation reconciliation: {exc}")

    path = resolved.completed_manifest_path
    if path and Path(path).exists():
        try:
            records, _invalid_count = _read_jsonl_records(Path(path), limit=400)
            for record in records:
                for value in _row_path_values(record, ("source_path", "source", "input_path")):
                    _add_path_token(completed_sources, value)
                for value in _row_path_values(record, ("output_path", "output_file", "output", "destination_path", "final_path")):
                    _add_path_token(completed_outputs, value)
        except OSError as exc:
            errors.append(f"Completed manifest could not be read for sample-validation reconciliation: {exc}")

    pending_root = resolved.pending_push_path
    if pending_root and Path(pending_root).exists():
        pending_tokens, pending_text = _pending_publish_reconciliation_clues(Path(pending_root))
        pending_path_tokens.update(pending_tokens)
        if pending_text:
            pending_text_parts.append(pending_text)

    for run_log in _run_log_candidates(resolved):
        if not run_log.exists():
            continue
        try:
            diagnostics_parts.append(_read_tail_text(run_log, 96 * 1024).casefold())
        except OSError as exc:
            errors.append(f"Run log {run_log.name} could not be read for sample-validation reconciliation: {exc}")

    return {
        "queue_sources": queue_sources,
        "completed_sources": completed_sources,
        "completed_outputs": completed_outputs,
        "pending_path_tokens": pending_path_tokens,
        "pending_path_clues": pending_text_parts,
        "pending_text": "\n".join(pending_text_parts).casefold(),
        "diagnostics_text": "\n".join(diagnostics_parts).casefold(),
    }


def _reconcile_validation_record(record: Mapping[str, Any], index: Mapping[str, Any]) -> dict[str, Any]:
    record_id = _clean_text(record.get("record_id")) or "unknown"
    source_path = _clean_text(record.get("source_path"))
    output_path = _clean_text(record.get("output_path"))
    decision = _clean_text(record.get("operator_decision")).casefold() or "unknown"
    proof = _clean_text(record.get("proof_strength")).casefold() or "unknown"
    checks = record.get("checks") if isinstance(record.get("checks"), Mapping) else {}
    source_token = _path_token(source_path)
    output_token = _path_token(output_path)
    matches = {
        "queue_source": bool(source_token and source_token in index["queue_sources"]),
        "completed_source": bool(source_token and source_token in index["completed_sources"]),
        "completed_output": bool(output_token and output_token in index["completed_outputs"]),
        "pending_source_or_output": bool(
            (source_token and source_token in index["pending_path_tokens"])
            or (output_token and output_token in index["pending_path_tokens"])
            or _text_contains_path_clue(str(index.get("pending_text") or ""), source_path)
            or _text_contains_path_clue(str(index.get("pending_text") or ""), output_path)
        ),
        "diagnostics_source_or_output": bool(
            _text_contains_path_clue(str(index.get("diagnostics_text") or ""), source_path)
            or _text_contains_path_clue(str(index.get("diagnostics_text") or ""), output_path)
        ),
    }
    missing: list[str] = []
    if output_path and not matches["completed_output"]:
        missing.append("Completed manifest no longer contains the recorded output path.")
    if source_path and not (matches["completed_source"] or matches["queue_source"]):
        missing.append("Current Queue/Completed evidence no longer contains the recorded source path.")
    if bool(checks.get("ffmpeg_log_checked") or checks.get("diagnostics_checked")) and not matches["diagnostics_source_or_output"]:
        missing.append("Current run logs do not contain a source/output clue for this record.")

    has_current_completed_proof = bool(matches["completed_output"] or matches["completed_source"])
    if decision == "accepted" and proof in {"exact-path", "partial-exact"} and not has_current_completed_proof:
        status = "stale"
        severity = "warning"
        safe_next_action = "Do not rely on this accepted record as current proof; rerun or re-check Queue, Completed, Pending Publish, and Diagnostics."
    elif matches["pending_source_or_output"]:
        status = "review"
        severity = "warning"
        safe_next_action = "Recorded source/output appears in Pending Publish evidence; verify parked/drained state before trusting the record."
    elif missing:
        status = "review"
        severity = "warning"
        safe_next_action = "Review missing current evidence before relying on this historical validation note."
    elif has_current_completed_proof or matches["queue_source"] or matches["diagnostics_source_or_output"]:
        status = "current"
        severity = "info"
        safe_next_action = "Current backend evidence still references this record; verify playback/output manually before daily-driver trust."
    else:
        status = "unknown"
        severity = "warning"
        safe_next_action = "No current backend artifact clearly matches this record; treat it as historical context only."

    evidence_parts = [
        f"queue_source={_yes_no(matches['queue_source'])}",
        f"completed_source={_yes_no(matches['completed_source'])}",
        f"completed_output={_yes_no(matches['completed_output'])}",
        f"pending={_yes_no(matches['pending_source_or_output'])}",
        f"diagnostics={_yes_no(matches['diagnostics_source_or_output'])}",
    ]
    return {
        "record_id": record_id,
        "created_at": _clean_text(record.get("created_at")),
        "operator_decision": decision,
        "proof_strength": proof,
        "sample_label": _clean_text(record.get("sample_label")),
        "source_path": source_path,
        "output_path": output_path,
        "status": status,
        "severity": severity,
        "matches": matches,
        "missing_current_evidence": missing,
        "evidence": "; ".join(evidence_parts),
        "safe_next_action": safe_next_action,
    }


def _row_path_values(row: Mapping[str, Any], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, (str, int, float)):
            text = _clean_text(value)
            if text:
                values.append(text)
    return values


def _add_path_token(tokens: set[str], raw_path: str) -> None:
    token = _path_token(raw_path)
    if token:
        tokens.add(token)


def _path_token(raw_path: str) -> str:
    text = _clean_text(raw_path, max_chars=2000)
    if not text:
        return ""
    try:
        path = Path(text)
        if path.is_absolute():
            return os.path.normcase(os.path.abspath(path))
    except (OSError, ValueError):
        pass
    return text.casefold()


def _text_contains_path_clue(text: str, raw_path: str) -> bool:
    value = _clean_text(raw_path, max_chars=2000)
    if not text or not value:
        return False
    folded = value.casefold()
    if folded and folded in text:
        return True
    try:
        leaf = Path(value).name.casefold()
    except (OSError, ValueError):
        leaf = ""
    return bool(leaf and len(leaf) >= 8 and leaf in text)


def _pending_publish_reconciliation_clues(root: Path, *, limit: int = 80, max_bytes: int = 64 * 1024) -> tuple[set[str], str]:
    tokens: set[str] = set()
    text_parts: list[str] = []
    scanned = 0
    try:
        for item in root.rglob("*"):
            if not item.is_file():
                continue
            scanned += 1
            if scanned > limit:
                text_parts.append(f"pending publish reconciliation scan capped after {limit} files")
                break
            _add_path_token(tokens, str(item))
            name = item.name.casefold()
            if not (name.endswith(".json") or name.endswith(".jsonl") or name.endswith(".manifest")):
                text_parts.append(str(item).casefold())
                continue
            try:
                text = _read_tail_text(item, max_bytes).casefold()
            except OSError:
                continue
            text_parts.append(text)
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, Mapping):
                for value in _mapping_string_values(payload):
                    _add_path_token(tokens, value)
    except OSError:
        text_parts.append("pending publish reconciliation scan failed")
    return tokens, "\n".join(text_parts)


def _mapping_string_values(payload: Mapping[str, Any], *, limit: int = 80) -> list[str]:
    values: list[str] = []
    stack: list[Any] = [payload]
    while stack and len(values) < limit:
        value = stack.pop()
        if isinstance(value, Mapping):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value[:limit])
        elif isinstance(value, (str, int, float)):
            text = _clean_text(value, max_chars=2000)
            if text:
                values.append(text)
    return values


def _payload_rows(payload: Any, *keys: str) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _read_jsonl_records(path: Path, *, limit: int) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                invalid_count += 1
                continue
            if isinstance(payload, dict):
                records.append(payload)
            else:
                invalid_count += 1
    return records[-limit:], invalid_count


def _run_log_candidates(resolved: ResolvedPaths) -> list[Path]:
    roots = [
        Path(resolved.local_base) if resolved.local_base else None,
        Path(resolved.app_root) if resolved.app_root else None,
        Path(resolved.workspace_root) if resolved.workspace_root else None,
        Path(resolved.state_root) if resolved.state_root else None,
    ]
    names = ("run.stderr.log", "run.stdout.log", "last_stderr.log", "last_stdout.log")
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if root is None:
            continue
        for base in (root / "RunLogs", root / "apps" / "desktop" / "runlogs", root / "State" / "RunLogs"):
            for name in names:
                path = base / name
                key = os.path.normcase(os.path.abspath(path))
                if key not in seen:
                    candidates.append(path)
                    seen.add(key)
    return candidates


def _read_tail_text(path: Path, max_bytes: int) -> str:
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        return handle.read(max_bytes).decode("utf-8", errors="replace")


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return text[:max_chars]


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"
