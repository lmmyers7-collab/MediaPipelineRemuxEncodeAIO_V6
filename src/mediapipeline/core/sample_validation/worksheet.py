from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths


SAMPLE_VALIDATION_WORKSHEET_RUNS_SCHEMA = "desktop_real_media_worksheet_runs.v1"
SAMPLE_VALIDATION_WORKSHEET_READ_BYTES = 128 * 1024
SAMPLE_VALIDATION_WORKSHEET_RUN_LIMIT = 20
SAMPLE_VALIDATION_WORKSHEET_SAMPLE_LIMIT = 12
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600


def sample_validation_worksheet_runs_payload(resolved: ResolvedPaths, *, limit: int = 10) -> dict[str, Any]:
    directory = Path(resolved.workspace_root or resolved.app_root) / "Docs" / "RealMediaValidationRuns"
    normalized_limit = max(1, min(SAMPLE_VALIDATION_WORKSHEET_RUN_LIMIT, int(limit or 10)))
    if not directory.exists():
        return {
            "schema_version": SAMPLE_VALIDATION_WORKSHEET_RUNS_SCHEMA,
            "ok": True,
            "exists": False,
            "directory": str(directory),
            "limit": normalized_limit,
            "run_count": 0,
            "sample_count": 0,
            "packet_row_count": 0,
            "rows": [],
            "operator_status": "not-started",
            "safe_next_action": "Generate a worksheet before the real-media pilot run if you want persistent Markdown evidence beside Sample Validation records.",
            "warnings": ["No generated real-media validation worksheet folder exists yet."],
            "errors": [],
            "guardrail": _worksheet_runs_guardrail(),
        }
    try:
        candidates = [
            item
            for item in directory.iterdir()
            if item.is_file() and item.suffix.casefold() == ".md" and item.name.casefold() != "readme.md"
        ]
    except OSError as exc:
        return {
            "schema_version": SAMPLE_VALIDATION_WORKSHEET_RUNS_SCHEMA,
            "ok": False,
            "exists": True,
            "directory": str(directory),
            "limit": normalized_limit,
            "run_count": 0,
            "sample_count": 0,
            "packet_row_count": 0,
            "rows": [],
            "operator_status": "blocked",
            "safe_next_action": "Resolve worksheet folder read errors before relying on generated pilot-run evidence.",
            "warnings": [],
            "errors": [f"Could not list generated real-media validation worksheets: {exc}"],
            "guardrail": _worksheet_runs_guardrail(),
        }
    candidates.sort(key=_safe_mtime, reverse=True)
    rows = [_worksheet_run_row(path) for path in candidates[:normalized_limit]]
    warnings = [warning for row in rows for warning in row.get("warnings", [])]
    errors = [error for row in rows for error in row.get("errors", [])]
    sample_count = sum(int(row.get("sample_count") or 0) for row in rows)
    packet_row_count = sum(int(row.get("packet_row_count") or 0) for row in rows)
    run_count = len(rows)
    if errors:
        operator_status = "blocked"
        safe_next_action = "Fix unreadable generated worksheets before using them as pilot evidence."
    elif not run_count:
        operator_status = "not-started"
        safe_next_action = "Generate a worksheet with New-RealMediaValidationWorksheet.ps1 before or during the pilot run."
    elif any(row.get("operator_status") == "blocked" for row in rows):
        operator_status = "blocked"
        safe_next_action = "Review worksheets with blocked pilot packet rows before accepting a sample evidence note."
    elif any(row.get("operator_status") in {"needs-evidence", "review"} for row in rows):
        operator_status = "review"
        safe_next_action = "Open the latest worksheet and fill packet/status fields from Home Sample Validation preview before appending evidence."
    else:
        operator_status = "worksheet-evidence-present"
        safe_next_action = "Compare worksheet packet fields with current Queue, Completed, Pending Publish, Diagnostics, and Sample Validation evidence."
    newest = rows[0] if rows else {}
    summary_lines = [
        f"Generated real-media worksheets: {operator_status}",
        f"Runs loaded: {run_count}; samples={sample_count}; packet rows={packet_row_count}; warnings={len(warnings)}; errors={len(errors)}",
        f"Newest worksheet: {newest.get('file_name') or 'none'}",
        f"Safe next action: {safe_next_action}",
        "Boundary: worksheet evidence is read-only Markdown context and cannot accept outputs, launch, publish, drain, save settings, rename, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_WORKSHEET_RUNS_SCHEMA,
        "ok": not errors,
        "exists": True,
        "directory": str(directory),
        "limit": normalized_limit,
        "run_count": run_count,
        "sample_count": sample_count,
        "packet_row_count": packet_row_count,
        "operator_status": operator_status,
        "safe_next_action": safe_next_action,
        "newest": newest,
        "rows": rows,
        "summary_lines": summary_lines,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(errors),
        "guardrail": _worksheet_runs_guardrail(),
    }


def _worksheet_run_row(path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        text = _read_head_text(path, SAMPLE_VALIDATION_WORKSHEET_READ_BYTES)
    except OSError as exc:
        errors.append(f"{path.name}: {exc}")
        text = ""
    try:
        stat = path.stat()
        size_bytes = int(stat.st_size)
        modified_at = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
    except OSError as exc:
        size_bytes = 0
        modified_at = ""
        warnings.append(f"{path.name}: could not read file metadata: {exc}")
    sample_rows = _worksheet_sample_rows(text)
    packet_rows = _worksheet_packet_rows(text)
    if size_bytes > SAMPLE_VALIDATION_WORKSHEET_READ_BYTES:
        warnings.append(f"{path.name}: worksheet read was capped at {SAMPLE_VALIDATION_WORKSHEET_READ_BYTES} bytes.")
    generated = "Generated by New-RealMediaValidationWorksheet.ps1" in text
    if text and not generated:
        warnings.append(f"{path.name}: worksheet does not include the generator marker.")
    operator = _worksheet_identity_value(text, "Operator")
    shell = _worksheet_identity_value(text, "Launch surface")
    status = _worksheet_operator_status(packet_rows, sample_rows, errors)
    return {
        "file_name": path.name,
        "run_id": _worksheet_run_id(path),
        "path": str(path),
        "size_bytes": size_bytes,
        "modified_at": modified_at,
        "generated_by_helper": generated,
        "operator": operator,
        "shell": shell,
        "operator_status": status,
        "sample_count": len(sample_rows),
        "packet_row_count": len(packet_rows),
        "samples": sample_rows,
        "packet_rows": packet_rows,
        "evidence": _worksheet_evidence_line(sample_rows, packet_rows, status),
        "safe_next_action": _worksheet_safe_next_action(status),
        "warnings": warnings,
        "errors": errors,
        "guardrail": _worksheet_runs_guardrail(),
    }


def _worksheet_sample_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _extract_markdown_table_rows(text, "Sample Batch", max_rows=SAMPLE_VALIDATION_WORKSHEET_SAMPLE_LIMIT):
        sample_number = _clean_text(row.get("#"))
        source = _clean_text(row.get("Source file"), max_chars=2000)
        category = _clean_text(row.get("Category"))
        expected_route = _clean_text(row.get("Expected route"))
        if not (source or category or expected_route):
            continue
        rows.append(
            {
                "sample_number": sample_number,
                "source_path": source,
                "category": category,
                "expected_route": expected_route,
                "source_leaf": _safe_leaf(source),
            }
        )
    return rows


def _worksheet_packet_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _extract_markdown_table_rows(text, "WebView Pilot Evidence Packet Capture", max_rows=SAMPLE_VALIDATION_WORKSHEET_SAMPLE_LIMIT):
        sample_number = _clean_text(row.get("Sample #"))
        label = _clean_text(row.get("Sample label"))
        packet_status = _clean_text(row.get("Packet status"))
        stop_condition = _clean_text(row.get("Stop condition hit?"))
        proof_fields = {
            "queue_route_proof": _clean_text(row.get("Queue route proof")),
            "completed_output_sidecar_proof": _clean_text(row.get("Completed output/sidecar proof")),
            "diagnostics_run_log_proof": _clean_text(row.get("Diagnostics/run-log proof")),
            "pending_publish_posture": _clean_text(row.get("Pending Publish posture")),
            "playback_subtitle_audio_size_proof": _clean_text(row.get("Playback/subtitle/audio/size proof")),
        }
        if not (label or packet_status or stop_condition or any(proof_fields.values())):
            continue
        rows.append(
            {
                "sample_number": sample_number,
                "sample_label": label,
                "packet_status": packet_status,
                "stop_condition_hit": stop_condition,
                **proof_fields,
            }
        )
    return rows


def _sample_set_worksheet_samples(worksheet_runs: Mapping[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for run in worksheet_runs.get("rows", []):
        if not isinstance(run, Mapping):
            continue
        run_name = _clean_text(run.get("file_name"))
        for sample in run.get("samples", []):
            if not isinstance(sample, Mapping):
                continue
            category = _clean_text(sample.get("category"))
            source_path = _clean_text(sample.get("source_path"), max_chars=2000)
            expected_route = _clean_text(sample.get("expected_route"))
            samples.append(
                {
                    "run": run_name,
                    "sample_number": _clean_text(sample.get("sample_number")),
                    "category": category,
                    "source_path": source_path,
                    "source_leaf": _clean_text(sample.get("source_leaf")) or _safe_leaf(source_path),
                    "expected_route": expected_route,
                    "match_text": " ".join([category, source_path, expected_route, _clean_text(sample.get("source_leaf"))]),
                }
            )
    return samples


def _extract_markdown_table_rows(text: str, heading: str, *, max_rows: int) -> list[dict[str, str]]:
    if not text:
        return []
    heading_marker = f"## {heading}".casefold()
    folded = text.casefold()
    start = folded.find(heading_marker)
    if start < 0:
        return []
    section = text[start:]
    next_heading = section.find("\n## ", 4)
    if next_heading >= 0:
        section = section[:next_heading]
    table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return []
    header = _split_markdown_row(table_lines[0])
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = _split_markdown_row(line)
        if not cells or all(_is_markdown_separator_cell(cell) for cell in cells):
            continue
        row = {header[index]: cells[index] if index < len(cells) else "" for index in range(len(header))}
        rows.append(row)
        if len(rows) >= max_rows:
            break
    return rows


def _split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(stripped):
        char = stripped[index]
        if char == "\\" and index + 1 < len(stripped) and stripped[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _is_markdown_separator_cell(cell: str) -> bool:
    return bool(cell) and all(char in "-: " for char in cell)


def _worksheet_identity_value(text: str, field: str) -> str:
    for row in _extract_markdown_table_rows(text, "Validation Run Identity", max_rows=16):
        if _clean_text(row.get("Field")).casefold() == field.casefold():
            return _clean_text(row.get("Value"))
    return ""


def _worksheet_run_id(path: Path) -> str:
    stem = path.stem
    prefix = "real_media_validation_"
    return stem[len(prefix):] if stem.startswith(prefix) else stem


def _worksheet_operator_status(packet_rows: list[dict[str, Any]], sample_rows: list[dict[str, Any]], errors: list[str]) -> str:
    if errors:
        return "blocked"
    if not sample_rows:
        return "empty"
    if not packet_rows:
        return "needs-evidence"
    statuses = [_clean_text(row.get("packet_status")).casefold() for row in packet_rows]
    stop_values = [_clean_text(row.get("stop_condition_hit")).casefold() for row in packet_rows]
    if any(value in {"yes", "y", "true", "blocked"} for value in stop_values):
        return "blocked"
    if any("blocked" in status for status in statuses):
        return "blocked"
    if any(not status for status in statuses):
        return "needs-evidence"
    if any("review" in status or "hold" in status or "warning" in status for status in statuses):
        return "review"
    return "worksheet-evidence-present"


def _worksheet_evidence_line(sample_rows: list[dict[str, Any]], packet_rows: list[dict[str, Any]], status: str) -> str:
    categories = _dedupe([_clean_text(row.get("category")) for row in sample_rows if _clean_text(row.get("category"))])
    routes = _dedupe([_clean_text(row.get("expected_route")) for row in sample_rows if _clean_text(row.get("expected_route"))])
    return (
        f"status={status}; samples={len(sample_rows)}; packet_rows={len(packet_rows)}; "
        f"categories={', '.join(categories) if categories else 'not filled'}; "
        f"expected_routes={', '.join(routes) if routes else 'not filled'}"
    )


def _worksheet_safe_next_action(status: str) -> str:
    if status == "blocked":
        return "Resolve blocked worksheet packet rows before appending or accepting sample evidence."
    if status == "needs-evidence":
        return "Run Home Sample Validation preview after processing the sample and copy the packet fields into the worksheet."
    if status == "review":
        return "Compare review packet rows with current Queue, Completed, Pending Publish, and Diagnostics evidence."
    if status == "empty":
        return "Regenerate or fill the worksheet with at least one source sample before treating it as pilot evidence."
    return "Use the worksheet as read-only context alongside current backend evidence and Sample Validation records."


def _worksheet_runs_guardrail() -> str:
    return (
        "Read-only generated worksheet evidence. It does not accept outputs, mark jobs complete, clear failures, launch work, "
        "publish or drain Pending Publish, save settings, rename files, rewrite manifests/sidecars, or touch source/output/scratch media."
    )


def _safe_mtime(path: Path) -> float:
    try:
        return float(path.stat().st_mtime)
    except OSError:
        return 0.0


def _safe_leaf(raw_path: str) -> str:
    text = _clean_text(raw_path, max_chars=2000)
    if not text:
        return ""
    try:
        return Path(text).name
    except (OSError, ValueError):
        return text


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:max_chars]


def _read_head_text(path: Path, max_bytes: int) -> str:
    with path.open("rb") as handle:
        return handle.read(max_bytes).decode("utf-8", errors="replace")


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result
