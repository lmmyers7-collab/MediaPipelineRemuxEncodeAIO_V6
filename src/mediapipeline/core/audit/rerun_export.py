from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.audit.contracts import AuditRecord
from mediapipeline.core.audit.rerun_contracts import RerunCsvExportServiceProtocol
from mediapipeline.core.audit.rerun_csv import (
    RERUN_CSV_COLUMNS,
    apply_rerun_source_metadata,
    append_rerun_note,
    build_rerun_csv_row,
    disable_duplicate_planned_output_rows,
    rerun_output_container_from_config,
    normalize_source_content_sha256,
    normalize_source_content_sha256_algorithm,
    source_stat_to_rerun_values,
)
from mediapipeline.core.audit.rerun_file_io import atomic_write_text


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
        row = apply_rerun_source_metadata(row, metadata)
        if not row["source_size"] or not row["source_mtime_utc"]:
            try:
                stat = source_path.stat()
                row["source_size"], row["source_mtime_utc"] = source_stat_to_rerun_values(stat.st_size, stat.st_mtime)
            except OSError as exc:
                row["enabled"] = "false"
                append_rerun_note(row, f"source stat failed: {exc}")
        row["source_content_sha256"] = normalize_source_content_sha256(
            row.get("source_content_sha256")
        )
        row["source_content_sha256_algorithm"] = normalize_source_content_sha256_algorithm(
            row.get("source_content_sha256_algorithm")
        )
        if not row["source_content_sha256"] or not row["source_content_sha256_algorithm"]:
            row["source_content_sha256"] = ""
            row["source_content_sha256_algorithm"] = ""
            row["enabled"] = "false"
            append_rerun_note(
                row,
                "automatic rerun disabled: durable full-content SHA-256 metadata is unavailable",
            )
        rows.append(row)

    if not rows:
        raise ValueError("No rerun rows with source paths were available for export.")

    config_data = getattr(resolved, "config_data", None)
    disable_duplicate_planned_output_rows(
        rows,
        output_container=rerun_output_container_from_config(config_data if isinstance(config_data, Mapping) else None),
    )

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(RERUN_CSV_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    atomic_write_text(output_path, buffer.getvalue(), encoding="utf-8")
    return len(rows)
