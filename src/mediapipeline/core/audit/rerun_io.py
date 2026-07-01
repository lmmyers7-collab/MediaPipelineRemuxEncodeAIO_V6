from __future__ import annotations

import csv
import io
from pathlib import Path

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.audit.contracts import AuditRecord
from mediapipeline.core.failures.contracts import FailureRecord
from mediapipeline.core.failures.markers import failure_record_from_marker_payload
from mediapipeline.core.audit.rerun_file_io import atomic_write_text, read_json_file


def load_audit_records(csv_path: Path) -> list[AuditRecord]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Audit CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            normalized = {str(key): str(value or "") for key, value in row.items() if key is not None}
            rows.append(AuditRecord(source_csv=csv_path, row=normalized))
        return rows


def save_audit_records_csv(output_path: Path, records: list[AuditRecord]) -> int:
    if not records:
        raise ValueError("No audit records were supplied for export.")

    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record.row.keys():
            if key in seen:
                continue
            seen.add(key)
            fieldnames.append(key)

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow({key: record.row.get(key, "") for key in fieldnames})
    atomic_write_text(output_path, buffer.getvalue(), encoding="utf-8")
    return len(records)


def load_failure_records(json_path: Path) -> list[FailureRecord]:
    if not json_path.exists():
        raise FileNotFoundError(f"Failure JSON not found: {json_path}")
    raw = read_json_file(json_path) or []
    if not isinstance(raw, list):
        raise RuntimeError(f"Failure JSON has an unexpected shape: {json_path}")
    records: list[FailureRecord] = []
    for item in raw:
        if isinstance(item, dict):
            records.append(FailureRecord(source_json=json_path, payload=item))
    return records


def load_failure_marker_records(resolved: ResolvedPaths) -> list[FailureRecord]:
    markers_dir = resolved.failed_markers_path
    if not markers_dir or not markers_dir.exists():
        return []

    records: list[FailureRecord] = []
    for marker_file in sorted(markers_dir.glob("*.json")):
        try:
            raw = read_json_file(marker_file)
            record = failure_record_from_marker_payload(marker_file, raw)
            if record is not None:
                records.append(record)
        except Exception:
            continue
    return records
