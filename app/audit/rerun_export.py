from __future__ import annotations

import csv
import io
from pathlib import Path

from mediapipeline_desktop_app.models import AuditRecord, ResolvedPaths
from app.audit.rerun_contracts import RerunCsvExportServiceProtocol
from app.audit.rerun_csv import (
    RERUN_CSV_COLUMNS,
    apply_rerun_source_metadata,
    build_rerun_csv_row,
    source_stat_to_rerun_values,
)
from app.audit.rerun_file_io import atomic_write_text


def _append_rerun_note(row: dict[str, str], note: str) -> None:
    existing = str(row.get("notes") or "").strip()
    row["notes"] = f"{existing}; {note}" if existing else note


def save_rerun_records_csv_for_service(
    service: RerunCsvExportServiceProtocol,
    output_path: Path,
    records: list[AuditRecord],
    resolved: ResolvedPaths,
    *,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
) -> int:
    if not records:
        raise ValueError("No audit records were supplied for rerun export.")
    stage_mode = "copy"
    original_mode = "keep"
    return_mode = "park"
    source_paths = [path for path in (record.path for record in records) if path]
    source_metadata = service._load_rerun_source_metadata(resolved, source_paths)

    rows: list[dict[str, str]] = []
    for record in records:
        source_path = record.path
        if not source_path:
            continue
        row = build_rerun_csv_row(
            record,
            stage_mode=stage_mode,
            original_mode=original_mode,
            return_mode=return_mode,
        )
        if row is None:
            continue
        metadata = source_metadata.get(str(source_path).casefold())
        if metadata:
            row = apply_rerun_source_metadata(row, metadata)
        if not row["source_size"] or not row["source_mtime_utc"]:
            try:
                stat = source_path.stat()
                row["source_size"], row["source_mtime_utc"] = source_stat_to_rerun_values(stat.st_size, stat.st_mtime)
            except OSError as exc:
                row["enabled"] = "false"
                _append_rerun_note(row, f"source stat failed: {exc}")
        rows.append(row)

    if not rows:
        raise ValueError("No rerun rows with source paths were available for export.")

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(RERUN_CSV_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    atomic_write_text(output_path, buffer.getvalue(), encoding="utf-8")
    return len(rows)
