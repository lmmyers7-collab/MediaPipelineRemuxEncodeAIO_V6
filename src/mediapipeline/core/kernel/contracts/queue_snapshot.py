from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import ntpath
import posixpath
import re
from typing import Any

from .base import ContractError, bool_field, float_field, int_field, list_field, require_mapping, require_schema_version, text_field


QUEUE_PLAN_SNAPSHOT_SCHEMA_VERSION = "queue_plan_snapshot.v1"
PLANNED_DISPLAY_NAME_SOURCE = "plex_destination_plan.v1"
ACCEPTED_RUN_ROWS_FINGERPRINT_SCHEMA = "accepted_run_rows_fingerprint.v1"
_ASCII_PATH_CASE_TRANSLATION = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)


def _accepted_row_value(row: Mapping[str, Any] | Any, key: str) -> str:
    value = row.get(key) if isinstance(row, Mapping) else getattr(row, key, "")
    return "" if value is None else str(value)


def _normalize_fingerprint_path(value: object) -> str:
    text = "" if value is None else str(value)
    if not text.strip():
        return text
    if "\\" in text or re.match(r"^[A-Za-z]:", text) or text.startswith("//"):
        text = ntpath.abspath(text)
    else:
        text = posixpath.abspath(text)
    # Fingerprint v1 uses ASCII-only path case normalization. This is
    # byte-identical in Python and PowerShell and deliberately preserves
    # non-ASCII distinctions such as Straße versus STRASSE.
    return text.replace("\\", "/").translate(_ASCII_PATH_CASE_TRANSLATION)


def _fingerprint_field(value: object, *, path: bool = False) -> str:
    text = "" if value is None else str(value)
    if path:
        text = _normalize_fingerprint_path(text)
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\p")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def accepted_run_rows_fingerprint(rows: list[Mapping[str, Any] | Any] | tuple[Mapping[str, Any] | Any, ...]) -> str:
    """Return the v1 cross-runtime digest for an uncapped accepted Run Once workload.

    Path fields are made absolute, use forward slashes, and fold ASCII A-Z only;
    non-ASCII code points and all non-path fields remain exact before escaping.
    """
    lines = [f"schema={ACCEPTED_RUN_ROWS_FINGERPRINT_SCHEMA}"]
    for row in rows:
        parts = (
            "accepted",
            _accepted_row_value(row, "run_queue_index"),
            _accepted_row_value(row, "run_queue_total"),
            _accepted_row_value(row, "source_identity"),
            _accepted_row_value(row, "source_identity_algorithm"),
            _fingerprint_field(_accepted_row_value(row, "source_path"), path=True),
            _accepted_row_value(row, "planned_display_name"),
            _accepted_row_value(row, "planned_display_name_source"),
            _fingerprint_field(_accepted_row_value(row, "parent_context"), path=True),
            _accepted_row_value(row, "route"),
            _accepted_row_value(row, "route_reason_code"),
            _accepted_row_value(row, "route_reason"),
            _fingerprint_field(_accepted_row_value(row, "intended_final_path"), path=True),
        )
        lines.append("|".join(_fingerprint_field(part) for part in parts))
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


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
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> QueuePlanRow:
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
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> QueuePlanExcludedRow:
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
class QueueAcceptedRunRow:
    source_identity: str
    source_identity_algorithm: str
    source_path: str
    display_name: str
    planned_display_name: str
    planned_display_name_source: str
    parent_context: str
    run_queue_index: int
    run_queue_total: int
    route: str
    route_reason_code: str
    route_reason: str
    intended_final_path: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> QueueAcceptedRunRow:
        data = require_mapping(payload, "queue accepted run row")
        source_identity = text_field(data, "source_identity").strip()
        source_identity_algorithm = text_field(data, "source_identity_algorithm").strip()
        source_path = text_field(data, "source_path").strip()
        display_name = text_field(data, "display_name").strip()
        planned_display_name = text_field(data, "planned_display_name").strip()
        planned_display_name_source = text_field(data, "planned_display_name_source").strip()
        if not source_identity or not source_identity_algorithm or not source_path:
            raise ContractError("accepted run row requires source identity, algorithm, and path")
        if not display_name:
            raise ContractError("accepted run row display_name requires backend naming-plan evidence")
        run_queue_index = int_field(data, "run_queue_index")
        run_queue_total = int_field(data, "run_queue_total")
        if run_queue_index <= 0 or run_queue_total <= 0:
            raise ContractError("accepted run row requires positive run-wide position and total")
        return cls(
            source_identity=source_identity,
            source_identity_algorithm=source_identity_algorithm,
            source_path=source_path,
            display_name=display_name,
            planned_display_name=planned_display_name,
            planned_display_name_source=planned_display_name_source,
            parent_context=text_field(data, "parent_context"),
            run_queue_index=run_queue_index,
            run_queue_total=run_queue_total,
            route=text_field(data, "route"),
            route_reason_code=text_field(data, "route_reason_code"),
            route_reason=text_field(data, "route_reason"),
            intended_final_path=text_field(data, "intended_final_path"),
            raw=data,
        )

    @property
    def has_verified_planned_display_name(self) -> bool:
        return bool(
            self.planned_display_name
            and self.planned_display_name_source == PLANNED_DISPLAY_NAME_SOURCE
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
    queue_snapshot_origin: str = "unknown"
    queue_preview_request_id: str = ""
    queue_input_fingerprint_schema: str = ""
    queue_input_fingerprint: str = ""
    queue_input_components: Mapping[str, Any] = field(default_factory=dict)
    queue_plan_fingerprint_schema: str = ""
    queue_plan_fingerprint: str = ""
    accepted_run_rows_fingerprint_schema: str = ""
    accepted_run_rows_fingerprint: str = ""
    pending_publish_index_health: Mapping[str, Any] = field(default_factory=dict)
    pending_publish_backpressure: Mapping[str, Any] = field(default_factory=dict)
    total_row_count: int = 0
    shown_row_count: int = 0
    row_limit: int = 0
    rows_truncated: bool = False
    excluded_count: int = 0
    excluded_row_limit: int = 0
    excluded_rows_truncated: bool = False
    accepted_run_rows: list[QueueAcceptedRunRow] = field(default_factory=list)
    rows: list[QueuePlanRow] = field(default_factory=list)
    excluded_rows: list[QueuePlanExcludedRow] = field(default_factory=list)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def accepted_run_rows_fingerprint_is_valid(self) -> bool:
        return bool(
            self.accepted_run_rows_fingerprint_schema == ACCEPTED_RUN_ROWS_FINGERPRINT_SCHEMA
            and self.accepted_run_rows_fingerprint
            and self.accepted_run_rows_fingerprint
            == accepted_run_rows_fingerprint(tuple(self.accepted_run_rows))
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> QueuePlanSnapshot:
        data = require_mapping(payload, "queue plan snapshot")
        schema_version = require_schema_version(data, QUEUE_PLAN_SNAPSHOT_SCHEMA_VERSION)
        produced_at = text_field(data, "produced_at").strip()
        if not produced_at:
            raise ContractError("produced_at is required")
        row_payloads = list_field(data, "rows")
        rows = [QueuePlanRow.from_mapping(row) for row in row_payloads]
        excluded_payloads = list_field(data, "excluded_rows")
        excluded_rows = [QueuePlanExcludedRow.from_mapping(row) for row in excluded_payloads]
        accepted_payloads = list_field(data, "accepted_run_rows")
        accepted_run_rows = [QueueAcceptedRunRow.from_mapping(row) for row in accepted_payloads]
        if accepted_run_rows:
            positions = [row.run_queue_index for row in accepted_run_rows]
            totals = {row.run_queue_total for row in accepted_run_rows}
            identities = [row.source_identity for row in accepted_run_rows]
            paths = [_normalize_fingerprint_path(row.source_path) for row in accepted_run_rows]
            if positions != list(range(1, len(accepted_run_rows) + 1)) or totals != {len(accepted_run_rows)}:
                raise ContractError("accepted run rows must be ordered, contiguous, and share the full total")
            if len(identities) != len(set(identities)) or len(paths) != len(set(paths)):
                raise ContractError("accepted run rows must have unique source identities and paths")
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
            queue_snapshot_origin=text_field(data, "queue_snapshot_origin") or "unknown",
            queue_preview_request_id=text_field(data, "desktop_queue_preview_request_id"),
            queue_input_fingerprint_schema=text_field(data, "queue_input_fingerprint_schema"),
            queue_input_fingerprint=text_field(data, "queue_input_fingerprint"),
            queue_input_components=(
                data.get("queue_input_components")
                if isinstance(data.get("queue_input_components"), Mapping)
                else {}
            ),
            queue_plan_fingerprint_schema=text_field(data, "queue_plan_fingerprint_schema"),
            queue_plan_fingerprint=text_field(data, "queue_plan_fingerprint"),
            accepted_run_rows_fingerprint_schema=text_field(data, "accepted_run_rows_fingerprint_schema"),
            accepted_run_rows_fingerprint=text_field(data, "accepted_run_rows_fingerprint"),
            pending_publish_index_health=(
                data.get("pending_publish_index_health")
                if isinstance(data.get("pending_publish_index_health"), Mapping)
                else {}
            ),
            pending_publish_backpressure=(
                data.get("pending_publish_backpressure")
                if isinstance(data.get("pending_publish_backpressure"), Mapping)
                else {}
            ),
            total_row_count=int_field(data, "total_row_count"),
            shown_row_count=int_field(data, "shown_row_count"),
            row_limit=int_field(data, "row_limit"),
            rows_truncated=bool_field(data, "rows_truncated"),
            excluded_count=int_field(data, "excluded_count"),
            excluded_row_limit=int_field(data, "excluded_row_limit"),
            excluded_rows_truncated=bool_field(data, "excluded_rows_truncated"),
            accepted_run_rows=accepted_run_rows,
            rows=rows,
            excluded_rows=excluded_rows,
            raw=data,
        )
