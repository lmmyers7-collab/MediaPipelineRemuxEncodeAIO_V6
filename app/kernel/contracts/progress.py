from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import ContractError, bool_field, dict_field, int_field, require_mapping, text_field


def _nullable_text_field(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _nullable_float_field(payload: Mapping[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{key} must be a number or null") from exc
    if result < 0.0 or result > 100.0:
        raise ContractError(f"{key} must be between 0 and 100")
    return result


def _nonnegative_int_field(payload: Mapping[str, Any], key: str) -> int:
    value = int_field(payload, key)
    if value < 0:
        raise ContractError(f"{key} must be greater than or equal to 0")
    return value


@dataclass(frozen=True)
class ProgressState:
    progress_version: int
    last_update: str
    status: str
    session_started_at: str | None = None
    current_file: str | None = None
    current_file_display: str | None = None
    current_file_path: str | None = None
    current_media_type: str | None = None
    current_library_id: str | None = None
    current_library_name: str | None = None
    current_library_designation: str | None = None
    current_library_source_root: str | None = None
    current_library_output_root: str | None = None
    current_queue_phase: str | None = None
    current_queue_index: int = 0
    current_queue_total: int = 0
    current_route: str | None = None
    current_stage: str | None = None
    current_stage_percent: float | None = None
    current_item_started_at: str | None = None
    current_stage_started_at: str | None = None
    copy_state: str | None = None
    push_state: str | None = None
    sidecar_state: str | None = None
    pause_requested: bool = False
    stop_requested: bool = False
    control_requests: dict[str, Any] = field(default_factory=dict)
    total_processed: int = 0
    encoded: int = 0
    remuxed: int = 0
    failed: int = 0
    movies: int = 0
    tv_episodes: int = 0
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> "ProgressState":
        data = require_mapping(payload, "progress state")
        progress_version = _nonnegative_int_field(data, "ProgressVersion")
        if progress_version < 1:
            raise ContractError("ProgressVersion must be greater than or equal to 1")
        last_update = text_field(data, "LastUpdate").strip()
        if not last_update:
            raise ContractError("LastUpdate is required")
        status = text_field(data, "Status").strip()
        if not status:
            raise ContractError("Status is required")
        return cls(
            progress_version=progress_version,
            last_update=last_update,
            status=status,
            session_started_at=_nullable_text_field(data, "SessionStartedAt"),
            current_file=_nullable_text_field(data, "CurrentFile"),
            current_file_display=_nullable_text_field(data, "CurrentFileDisplay"),
            current_file_path=_nullable_text_field(data, "CurrentFilePath"),
            current_media_type=_nullable_text_field(data, "CurrentMediaType"),
            current_library_id=_nullable_text_field(data, "CurrentLibraryId"),
            current_library_name=_nullable_text_field(data, "CurrentLibraryName"),
            current_library_designation=_nullable_text_field(data, "CurrentLibraryDesignation"),
            current_library_source_root=_nullable_text_field(data, "CurrentLibrarySourceRoot"),
            current_library_output_root=_nullable_text_field(data, "CurrentLibraryOutputRoot"),
            current_queue_phase=_nullable_text_field(data, "CurrentQueuePhase"),
            current_queue_index=_nonnegative_int_field(data, "CurrentQueueIndex"),
            current_queue_total=_nonnegative_int_field(data, "CurrentQueueTotal"),
            current_route=_nullable_text_field(data, "CurrentRoute"),
            current_stage=_nullable_text_field(data, "CurrentStage"),
            current_stage_percent=_nullable_float_field(data, "CurrentStagePercent"),
            current_item_started_at=_nullable_text_field(data, "CurrentItemStartedAt"),
            current_stage_started_at=_nullable_text_field(data, "CurrentStageStartedAt"),
            copy_state=_nullable_text_field(data, "CopyState"),
            push_state=_nullable_text_field(data, "PushState"),
            sidecar_state=_nullable_text_field(data, "SidecarState"),
            pause_requested=bool_field(data, "PauseRequested"),
            stop_requested=bool_field(data, "StopRequested"),
            control_requests=dict_field(data, "ControlRequests"),
            total_processed=_nonnegative_int_field(data, "TotalProcessed"),
            encoded=_nonnegative_int_field(data, "Encoded"),
            remuxed=_nonnegative_int_field(data, "Remuxed"),
            failed=_nonnegative_int_field(data, "Failed"),
            movies=_nonnegative_int_field(data, "Movies"),
            tv_episodes=_nonnegative_int_field(data, "TVEpisodes"),
            raw=data,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            **dict(self.raw),
            "ProgressVersion": self.progress_version,
            "LastUpdate": self.last_update,
            "SessionStartedAt": self.session_started_at,
            "CurrentFile": self.current_file,
            "CurrentFileDisplay": self.current_file_display,
            "CurrentFilePath": self.current_file_path,
            "CurrentMediaType": self.current_media_type,
            "CurrentLibraryId": self.current_library_id,
            "CurrentLibraryName": self.current_library_name,
            "CurrentLibraryDesignation": self.current_library_designation,
            "CurrentLibrarySourceRoot": self.current_library_source_root,
            "CurrentLibraryOutputRoot": self.current_library_output_root,
            "CurrentQueuePhase": self.current_queue_phase,
            "CurrentQueueIndex": self.current_queue_index,
            "CurrentQueueTotal": self.current_queue_total,
            "CurrentRoute": self.current_route,
            "CurrentStage": self.current_stage,
            "CurrentStagePercent": self.current_stage_percent,
            "CurrentItemStartedAt": self.current_item_started_at,
            "CurrentStageStartedAt": self.current_stage_started_at,
            "CopyState": self.copy_state,
            "PushState": self.push_state,
            "SidecarState": self.sidecar_state,
            "PauseRequested": self.pause_requested,
            "StopRequested": self.stop_requested,
            "ControlRequests": dict(self.control_requests),
            "Status": self.status,
            "TotalProcessed": self.total_processed,
            "Encoded": self.encoded,
            "Remuxed": self.remuxed,
            "Failed": self.failed,
            "Movies": self.movies,
            "TVEpisodes": self.tv_episodes,
        }
