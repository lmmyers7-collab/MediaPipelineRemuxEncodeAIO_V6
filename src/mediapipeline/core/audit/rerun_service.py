from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.desktop.models import AuditRecord, CompletedJobRecord, FailureRecord, ResolvedPaths
from mediapipeline.core.audit.rerun_export import save_rerun_records_csv_for_service
from mediapipeline.core.audit.rerun_records import (
    audit_correlation_lookup_key,
    audit_row_value,
    correlate_audit_record as correlate_audit_record_helper,
    format_audit_correlation as format_audit_correlation_helper,
    rerun_media_kind_from_audit,
)
from mediapipeline.core.audit.rerun_io import (
    load_audit_records as load_audit_records_file,
    load_failure_marker_records as load_failure_marker_records_file,
    load_failure_records as load_failure_records_file,
    save_audit_records_csv as save_audit_records_csv_file,
)
from mediapipeline.core.audit.rerun_metadata import (
    load_rerun_source_metadata_for_service,
    rerun_source_metadata_script_path_for_service,
)
from mediapipeline.desktop.subprocess_runner import run_capture


class AuditRerunServiceMixin:
    def latest_failure_report(self, resolved: ResolvedPaths) -> Path | None:
        return self.latest_matching_file(resolved.failed_reports_path, "round_failures_*.txt")

    def newest_audit_csv(self, resolved: ResolvedPaths, priority_only: bool) -> Path | None:
        return self.latest_audit_csv(resolved, priority_only=priority_only)

    def newest_failure_json(self, resolved: ResolvedPaths) -> Path | None:
        return self.latest_failure_json(resolved)

    def _audit_correlation_lookup_key(self, value: str) -> str:
        return audit_correlation_lookup_key(value)

    def correlate_audit_record(
        self,
        record: AuditRecord,
        completed_records: list[CompletedJobRecord],
        failure_records: list[FailureRecord],
    ) -> dict[str, Any]:
        return correlate_audit_record_helper(record, completed_records, failure_records)

    def format_audit_correlation(
        self,
        record: AuditRecord,
        completed_records: list[CompletedJobRecord],
        failure_records: list[FailureRecord],
    ) -> list[str]:
        return format_audit_correlation_helper(record, completed_records, failure_records)

    def load_audit_records(self, csv_path: Path) -> list[AuditRecord]:
        return load_audit_records_file(csv_path)

    def save_audit_records_csv(self, output_path: Path, records: list[AuditRecord]) -> int:
        return save_audit_records_csv_file(output_path, records)

    @staticmethod
    def _audit_row_value(record: AuditRecord, *names: str) -> str:
        return audit_row_value(record, *names)

    def _rerun_source_metadata_script_path(self, resolved: ResolvedPaths) -> Path:
        return rerun_source_metadata_script_path_for_service(self, resolved)

    def _load_rerun_source_metadata(self, resolved: ResolvedPaths, source_paths: list[Path]) -> dict[str, dict[str, Any]]:
        return load_rerun_source_metadata_for_service(self, resolved, source_paths, run_capture_func=run_capture)

    def _rerun_media_kind_from_audit(self, record: AuditRecord) -> str:
        return rerun_media_kind_from_audit(record)

    def save_rerun_records_csv(
        self,
        output_path: Path,
        records: list[AuditRecord],
        resolved: ResolvedPaths,
        *,
        stage_mode: str,
        original_mode: str,
        return_mode: str,
    ) -> int:
        return save_rerun_records_csv_for_service(
            self,
            output_path,
            records,
            resolved,
            stage_mode=stage_mode,
            original_mode=original_mode,
            return_mode=return_mode,
        )

    def load_failure_records(self, json_path: Path) -> list[FailureRecord]:
        return load_failure_records_file(json_path)

    def load_failure_marker_records(self, resolved: ResolvedPaths) -> list[FailureRecord]:
        return load_failure_marker_records_file(resolved)
