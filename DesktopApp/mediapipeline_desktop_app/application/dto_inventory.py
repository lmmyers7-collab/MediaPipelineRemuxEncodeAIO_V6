from __future__ import annotations

from dataclasses import dataclass, field

from .dto_base import JsonMap, dto_mapping


@dataclass(frozen=True)
class QueuePreviewDto:
    rows: list[JsonMap] = field(default_factory=list)
    source: str = ""
    queue_progress: JsonMap = field(default_factory=dict)
    progress_bars: list[JsonMap] = field(default_factory=list)
    produced_at: str = ""
    produced_age_seconds: int | None = None
    produced_age_text: str = ""
    produced_freshness_status: str = "unknown"
    produced_stale_after_seconds: int = 3600
    snapshot_file_mtime_utc: str = ""
    snapshot_file_age_seconds: int | None = None
    snapshot_file_age_text: str = ""
    snapshot_file_freshness_status: str = "unknown"
    snapshot_file_stale_after_seconds: int = 3600
    snapshot_file_error: str = ""
    config_path: str = ""
    local_base: str = ""
    source_movies: str = ""
    source_tv: str = ""
    outsource: str = ""
    movie_count_total: int = 0
    tv_count_total: int = 0
    source_count_total: int = 0
    priority_count: int = 0
    runnable_count: int = 0
    completed_excluded_count: int = 0
    excluded_row_count: int = 0
    excluded_row_limit: int = 0
    excluded_rows_truncated: bool = False
    excluded_reason_counts: JsonMap = field(default_factory=dict)
    excluded_media_type_counts: JsonMap = field(default_factory=dict)
    excluded_rows: list[JsonMap] = field(default_factory=list)
    blocked_row_count: int = 0
    blocked_reason_code_counts: JsonMap = field(default_factory=dict)
    blocked_reason_counts: JsonMap = field(default_factory=dict)
    runtime_check_deferred_count: int = 0
    runtime_check_code_counts: JsonMap = field(default_factory=dict)
    runtime_outcome_source: str = ""
    runtime_outcome_event_count: int = 0
    runtime_outcome_match_count: int = 0
    runtime_outcome_warning: str = ""
    runtime_outcome_status_counts: JsonMap = field(default_factory=dict)
    runtime_outcome_event_type_counts: JsonMap = field(default_factory=dict)
    runtime_outcome_error_code_counts: JsonMap = field(default_factory=dict)
    runtime_outcome_freshness_counts: JsonMap = field(default_factory=dict)
    available_open_target_counts: JsonMap = field(default_factory=dict)
    completed_collision_status: str = "unknown"
    completed_collision_severity: str = "unknown"
    completed_collision_guidance: str = ""
    completed_collision_lines: list[str] = field(default_factory=list)
    completed_collision_flags: list[str] = field(default_factory=list)
    completed_collision_row_level_available: bool = False
    route_counts: JsonMap = field(default_factory=dict)
    route_reason_counts: JsonMap = field(default_factory=dict)
    operator_status_counts: JsonMap = field(default_factory=dict)
    operator_status_state_counts: JsonMap = field(default_factory=dict)
    operator_severity_counts: JsonMap = field(default_factory=dict)
    operator_trust_state_counts: JsonMap = field(default_factory=dict)
    phase_counts: JsonMap = field(default_factory=dict)
    media_type_counts: JsonMap = field(default_factory=dict)
    source_root_counts: JsonMap = field(default_factory=dict)
    season_counts: JsonMap = field(default_factory=dict)
    priority_reason_counts: JsonMap = field(default_factory=dict)
    priority_visible_count: int = 0
    invalid_row_count: int = 0
    total_visible_size_gb: float = 0.0
    total_visible_size_text: str = "0.00 GB"
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_queue_preview.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class CompletedPreviewDto:
    rows: list[JsonMap] = field(default_factory=list)
    source: str = ""
    manifest_mtime_utc: str = ""
    manifest_age_seconds: int | None = None
    manifest_age_text: str = ""
    manifest_freshness_status: str = "unknown"
    manifest_stale_after_seconds: int = 604800
    manifest_error: str = ""
    count: int = 0
    missing_output_count: int = 0
    encode_count: int = 0
    remux_count: int = 0
    route_counts: JsonMap = field(default_factory=dict)
    publish_counts: JsonMap = field(default_factory=dict)
    health_counts: JsonMap = field(default_factory=dict)
    operator_status_counts: JsonMap = field(default_factory=dict)
    operator_status_state_counts: JsonMap = field(default_factory=dict)
    operator_severity_counts: JsonMap = field(default_factory=dict)
    operator_trust_state_counts: JsonMap = field(default_factory=dict)
    consistency_status_counts: JsonMap = field(default_factory=dict)
    consistency_severity_counts: JsonMap = field(default_factory=dict)
    validation_status_state_counts: JsonMap = field(default_factory=dict)
    size_bucket_counts: JsonMap = field(default_factory=dict)
    media_type_counts: JsonMap = field(default_factory=dict)
    decision_totals: JsonMap = field(default_factory=dict)
    runtime_outcome_source: str = ""
    runtime_outcome_event_count: int = 0
    runtime_outcome_match_count: int = 0
    runtime_outcome_warning: str = ""
    runtime_outcome_status_counts: JsonMap = field(default_factory=dict)
    runtime_outcome_event_type_counts: JsonMap = field(default_factory=dict)
    runtime_outcome_error_code_counts: JsonMap = field(default_factory=dict)
    runtime_outcome_freshness_counts: JsonMap = field(default_factory=dict)
    available_open_target_counts: JsonMap = field(default_factory=dict)
    size_growth_count: int = 0
    size_growth_over_5_count: int = 0
    size_policy_available_count: int = 0
    size_policy_exceeded_count: int = 0
    size_policy_blocked_count: int = 0
    size_policy_within_limit_count: int = 0
    size_policy_status_counts: JsonMap = field(default_factory=dict)
    size_policy_mode_counts: JsonMap = field(default_factory=dict)
    size_unknown_count: int = 0
    missing_sidecar_count: int = 0
    output_sidecar_mismatch_count: int = 0
    stale_sidecar_count: int = 0
    missing_manifest_output_path_count: int = 0
    total_output_bytes: int = 0
    total_output_size_text: str = "0 B"
    inventory_progress: JsonMap = field(default_factory=dict)
    progress_bars: list[JsonMap] = field(default_factory=list)
    validation_state: JsonMap = field(default_factory=dict)
    completed_pending_proof: JsonMap = field(default_factory=dict)
    final_library_promotion: JsonMap = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_completed_preview.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class PendingPublishPreviewDto:
    pending_root: str = ""
    exists: bool = False
    rows: list[JsonMap] = field(default_factory=list)
    health_rows: list[JsonMap] = field(default_factory=list)
    count: int = 0
    payload_count: int = 0
    total_bytes: int = 0
    total_size_text: str = "0 B"
    missing_local_count: int = 0
    health_count: int = 0
    state_counts: JsonMap = field(default_factory=dict)
    route_counts: JsonMap = field(default_factory=dict)
    diagnostic_status_counts: JsonMap = field(default_factory=dict)
    diagnostic_status_state_counts: JsonMap = field(default_factory=dict)
    diagnostic_severity_counts: JsonMap = field(default_factory=dict)
    operator_trust_state_counts: JsonMap = field(default_factory=dict)
    recovery_class_counts: JsonMap = field(default_factory=dict)
    recommended_open_target_counts: JsonMap = field(default_factory=dict)
    available_open_target_counts: JsonMap = field(default_factory=dict)
    issue_count: int = 0
    ready_count: int = 0
    orphan_payload_count: int = 0
    invalid_manifest_count: int = 0
    missing_sidecar_count: int = 0
    recovery_summary: JsonMap = field(default_factory=dict)
    drain_summary: JsonMap = field(default_factory=dict)
    drain_confidence: JsonMap = field(default_factory=dict)
    inventory_progress: JsonMap = field(default_factory=dict)
    progress_bars: list[JsonMap] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    schema_version: str = "desktop_pending_publish_preview.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class PublishReconciliationDto:
    rows: list[JsonMap] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    status: str = "not_loaded"
    completed_source: str = ""
    pending_root: str = ""
    drain_summary_path: str = ""
    completed_count: int = 0
    pending_count: int = 0
    drain_item_count: int = 0
    exact_pending_destination_count: int = 0
    exact_pending_source_count: int = 0
    drain_output_count: int = 0
    drain_source_count: int = 0
    same_leaf_hint_count: int = 0
    missing_with_pending_proof_count: int = 0
    missing_with_drain_proof_count: int = 0
    missing_without_proof_count: int = 0
    warning_count: int = 0
    blocker_count: int = 0
    completed_pending_proof: JsonMap = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    schema_version: str = "desktop_publish_reconciliation.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class FailurePreviewDto:
    rows: list[JsonMap] = field(default_factory=list)
    source: str = ""
    source_kind: str = "latest_json"
    count: int = 0
    operator_required_count: int = 0
    permanent_count: int = 0
    transient_count: int = 0
    retry_state: JsonMap = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_failure_preview.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class AuditPreviewDto:
    rows: list[JsonMap] = field(default_factory=list)
    source: str = ""
    priority_only: bool = False
    count: int = 0
    high_priority_count: int = 0
    rerun_count: int = 0
    redownload_count: int = 0
    review_count: int = 0
    duplicate_group_count: int = 0
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_audit_preview.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)

__all__ = [
    "QueuePreviewDto",
    "CompletedPreviewDto",
    "PendingPublishPreviewDto",
    "PublishReconciliationDto",
    "FailurePreviewDto",
    "AuditPreviewDto",
]
