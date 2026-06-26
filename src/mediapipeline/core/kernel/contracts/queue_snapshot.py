from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import ContractError, bool_field, float_field, int_field, list_field, require_mapping, require_schema_version, text_field


QUEUE_PLAN_SNAPSHOT_SCHEMA_VERSION = "queue_plan_snapshot.v1"


@dataclass(frozen=True)
class QueuePlanRow:
    global_order: int
    phase: str
    media_kind: str
    queue_index: int
    queue_total: int
    is_priority: bool
    source_path: str
    root_path: str
    relative_path: str
    display_name: str
    size_gb: float
    route: str
    route_reason_code: str
    route_reason: str
    route_decision_trace: list[Any]
    estimated_bitrate_mbps: float
    route_size_threshold_gb: float
    route_bitrate_threshold_mbps: float
    route_threshold_mode: str
    size_over_threshold: bool
    bitrate_over_threshold: bool
    blocked_reason_code: str
    blocked_reason: str
    runtime_checks_deferred: bool
    runtime_check_codes: list[Any]
    runtime_check_notes: list[Any]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> "QueuePlanRow":
        data = require_mapping(payload, "queue plan row")
        source_path = text_field(data, "source_path").strip()
        if not source_path:
            raise ContractError("queue plan row source_path is required")
        return cls(
            global_order=int_field(data, "global_order"),
            phase=text_field(data, "phase"),
            media_kind=text_field(data, "media_kind"),
            queue_index=int_field(data, "queue_index"),
            queue_total=int_field(data, "queue_total"),
            is_priority=bool_field(data, "is_priority"),
            source_path=source_path,
            root_path=text_field(data, "root_path"),
            relative_path=text_field(data, "relative_path"),
            display_name=text_field(data, "display_name"),
            size_gb=float_field(data, "size_gb"),
            route=text_field(data, "route"),
            route_reason_code=text_field(data, "route_reason_code"),
            route_reason=text_field(data, "route_reason"),
            route_decision_trace=list_field(data, "route_decision_trace"),
            estimated_bitrate_mbps=float_field(data, "estimated_bitrate_mbps"),
            route_size_threshold_gb=float_field(data, "route_size_threshold_gb"),
            route_bitrate_threshold_mbps=float_field(data, "route_bitrate_threshold_mbps"),
            route_threshold_mode=text_field(data, "route_threshold_mode"),
            size_over_threshold=bool_field(data, "size_over_threshold"),
            bitrate_over_threshold=bool_field(data, "bitrate_over_threshold"),
            blocked_reason_code=text_field(data, "blocked_reason_code"),
            blocked_reason=text_field(data, "blocked_reason"),
            runtime_checks_deferred=bool_field(data, "runtime_checks_deferred"),
            runtime_check_codes=list_field(data, "runtime_check_codes"),
            runtime_check_notes=list_field(data, "runtime_check_notes"),
            raw=data,
        )


@dataclass(frozen=True)
class QueuePlanExcludedRow:
    source_order: int
    reason_code: str
    reason: str
    phase: str
    media_kind: str
    source_path: str
    root_path: str
    relative_path: str
    display_name: str
    size_gb: float
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> "QueuePlanExcludedRow":
        data = require_mapping(payload, "queue plan excluded row")
        source_path = text_field(data, "source_path").strip()
        if not source_path:
            raise ContractError("queue plan excluded row source_path is required")
        reason_code = text_field(data, "reason_code").strip()
        if not reason_code:
            raise ContractError("queue plan excluded row reason_code is required")
        return cls(
            source_order=int_field(data, "source_order"),
            reason_code=reason_code,
            reason=text_field(data, "reason"),
            phase=text_field(data, "phase"),
            media_kind=text_field(data, "media_kind"),
            source_path=source_path,
            root_path=text_field(data, "root_path"),
            relative_path=text_field(data, "relative_path"),
            display_name=text_field(data, "display_name"),
            size_gb=float_field(data, "size_gb"),
            raw=data,
        )


@dataclass(frozen=True)
class QueuePlanSnapshot:
    schema_version: str
    produced_at: str
    config_path: str
    local_base: str
    source_movies: str
    source_tv: str
    outsource: str
    movie_count_total: int
    tv_count_total: int
    priority_count: int
    runnable_count: int
    total_row_count: int = 0
    shown_row_count: int = 0
    row_limit: int = 0
    rows_truncated: bool = False
    excluded_count: int = 0
    excluded_row_limit: int = 0
    excluded_rows_truncated: bool = False
    rows: list[QueuePlanRow] = field(default_factory=list)
    excluded_rows: list[QueuePlanExcludedRow] = field(default_factory=list)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> "QueuePlanSnapshot":
        data = require_mapping(payload, "queue plan snapshot")
        schema_version = require_schema_version(data, QUEUE_PLAN_SNAPSHOT_SCHEMA_VERSION)
        produced_at = text_field(data, "produced_at").strip()
        if not produced_at:
            raise ContractError("produced_at is required")
        row_payloads = list_field(data, "rows")
        rows = [QueuePlanRow.from_mapping(row) for row in row_payloads]
        excluded_payloads = list_field(data, "excluded_rows")
        excluded_rows = [QueuePlanExcludedRow.from_mapping(row) for row in excluded_payloads]
        return cls(
            schema_version=schema_version,
            produced_at=produced_at,
            config_path=text_field(data, "config_path"),
            local_base=text_field(data, "local_base"),
            source_movies=text_field(data, "source_movies"),
            source_tv=text_field(data, "source_tv"),
            outsource=text_field(data, "outsource"),
            movie_count_total=int_field(data, "movie_count_total"),
            tv_count_total=int_field(data, "tv_count_total"),
            priority_count=int_field(data, "priority_count"),
            runnable_count=int_field(data, "runnable_count"),
            total_row_count=int_field(data, "total_row_count"),
            shown_row_count=int_field(data, "shown_row_count"),
            row_limit=int_field(data, "row_limit"),
            rows_truncated=bool_field(data, "rows_truncated"),
            excluded_count=int_field(data, "excluded_count"),
            excluded_row_limit=int_field(data, "excluded_row_limit"),
            excluded_rows_truncated=bool_field(data, "excluded_rows_truncated"),
            rows=rows,
            excluded_rows=excluded_rows,
            raw=data,
        )
