"""Versioned, backend-authored evidence for one accepted Run Once workload.

The persisted contract is intentionally strict. It is the correlation boundary between
the accepted Backend Queue plan, PowerShell runtime evidence, and terminal artifacts.
Display projections may suppress stale claims, but they must never reconstruct missing
membership, stages, routes, or track decisions from legacy progress or filename text.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RUN_MONITOR_SCHEMA_VERSION: Literal["pipeline_run_monitor.v1"] = "pipeline_run_monitor.v1"
RUN_MONITOR_POINTER_SCHEMA_VERSION: Literal["pipeline_run_monitor_pointer.v1"] = "pipeline_run_monitor_pointer.v1"
RUN_MONITOR_PROJECTION_SCHEMA_VERSION: Literal["desktop_run_monitor.v1"] = "desktop_run_monitor.v1"

RUN_MONITOR_STAGE_IDS = (
    "accepted",
    "source_discovery",
    "copy_to_scratch",
    "probe",
    "route_decision",
    "audio",
    "subtitles",
    "transcode",
    "mux",
    "verification",
    "sidecar_writing",
    "publish",
    "final_evidence",
)
RUN_LIFECYCLE_STATES = frozenset(
    {
        "starting",
        "scanning",
        "running",
        "paused",
        "stop_requested",
        "stopping",
        "completed",
        "failed",
        "blocked",
        "review",
        "stopped",
        "force_stopped",
        "unknown",
    }
)
TERMINAL_RUN_LIFECYCLE_STATES = frozenset({"completed", "failed", "blocked", "review", "stopped", "force_stopped"})
ITEM_LIFECYCLE_STATES = frozenset(
    {"accepted", "queued", "active", "completed", "failed", "skipped", "blocked", "review", "parked", "stopped", "unknown"}
)
TERMINAL_ITEM_LIFECYCLE_STATES = frozenset(
    {"completed", "failed", "skipped", "blocked", "review", "parked", "stopped"}
)
STAGE_STATES = frozenset(
    {"not_started", "active", "completed", "skipped", "not_applicable", "unknown", "blocked", "review", "failed"}
)
AUDIO_COLLECTION_STATES = frozenset(
    {"awaiting_evidence", "not_applicable", "active", "completed", "failed", "review", "unknown"}
)
SUBTITLE_COLLECTION_STATES = frozenset(
    {"awaiting_evidence", "not_applicable", "active", "completed", "failed", "review", "unknown"}
)

RunLifecycleState = Literal[
    "starting",
    "scanning",
    "running",
    "paused",
    "stop_requested",
    "stopping",
    "completed",
    "failed",
    "blocked",
    "review",
    "stopped",
    "force_stopped",
    "unknown",
]
ItemLifecycleState = Literal[
    "accepted",
    "queued",
    "active",
    "completed",
    "failed",
    "skipped",
    "blocked",
    "review",
    "parked",
    "stopped",
    "unknown",
]
RunMonitorStageId = Literal[
    "accepted",
    "source_discovery",
    "copy_to_scratch",
    "probe",
    "route_decision",
    "audio",
    "subtitles",
    "transcode",
    "mux",
    "verification",
    "sidecar_writing",
    "publish",
    "final_evidence",
]
StageState = Literal[
    "not_started",
    "active",
    "completed",
    "skipped",
    "not_applicable",
    "unknown",
    "blocked",
    "review",
    "failed",
]
CollectionState = Literal[
    "awaiting_evidence",
    "not_applicable",
    "active",
    "completed",
    "failed",
    "review",
    "unknown",
]
TrackState = Literal[
    "awaiting_evidence",
    "not_applicable",
    "active",
    "completed",
    "failed",
    "review",
    "skipped",
    "dropped",
    "unknown",
]
TERMINAL_TRACK_STATES = frozenset({"not_applicable", "completed", "failed", "review", "skipped", "dropped"})
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


def _validated_iso_timestamp(value: str, *, optional: bool) -> str:
    text = str(value or "").strip()
    if not text:
        if optional:
            return value
        raise ValueError("timestamp must not be blank")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO-8601 timestamp") from exc
    return value


def _validate_track_timeline(
    *,
    label: str,
    state: TrackState,
    started_at: str,
    updated_at: str,
    completed_at: str,
) -> None:
    """Validate track claims without inventing timestamps for legacy non-active evidence."""

    if state == "active":
        if not started_at.strip() or not updated_at.strip() or completed_at.strip():
            raise ValueError(f"active {label} track requires started_at and updated_at without completed_at")
        return
    if state in TERMINAL_TRACK_STATES:
        if not updated_at.strip() or not completed_at.strip():
            raise ValueError(f"{state} {label} track requires updated_at and completed_at")
        return
    if completed_at.strip():
        raise ValueError(f"nonterminal {label} track must not carry completed_at")


def _validate_collection_active_tracks(*, label: str, state: CollectionState, tracks: list[Any]) -> None:
    active_count = sum(track.state == "active" for track in tracks)
    if state == "active" and active_count == 0:
        raise ValueError(f"active {label} collection requires active per-track evidence")
    if state != "active" and active_count:
        raise ValueError(f"active {label} track requires an active {label} collection")


class RunMonitorModel(BaseModel):
    """Strict base for persisted Run Monitor records."""

    model_config = ConfigDict(extra="forbid")


class EvidenceRecord(RunMonitorModel):
    source: str = Field(min_length=1)
    provenance: Literal[
        "backend_confirmed",
        "queue_plan",
        "engine_event",
        "worker_heartbeat",
        "terminal",
        "inferred",
        "unknown",
    ]
    recorded_at: str = Field(min_length=1)

    @field_validator("source", "recorded_at")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("recorded_at")
    @classmethod
    def _iso_timestamp(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=False)


class ProgressEvidence(RunMonitorModel):
    kind: Literal["none", "indeterminate", "determinate"] = "none"
    numerator: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    denominator: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _valid_progress_pair(self) -> ProgressEvidence:
        if self.kind == "determinate":
            if self.numerator is None or self.denominator is None:
                raise ValueError("determinate progress requires numerator and denominator")
            if self.numerator > self.denominator:
                raise ValueError("progress numerator must not exceed denominator")
        elif self.numerator is not None or self.denominator is not None:
            raise ValueError(f"{self.kind} progress must not carry numerator or denominator")
        return self

    @property
    def fraction(self) -> float | None:
        if self.kind != "determinate" or self.numerator is None or self.denominator is None:
            return None
        return self.numerator / self.denominator


class StageEvidence(RunMonitorModel):
    stage_id: RunMonitorStageId
    state: StageState
    started_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    detail: str = ""
    reason_code: str = ""
    progress: ProgressEvidence = Field(default_factory=ProgressEvidence)
    evidence: EvidenceRecord

    @field_validator("started_at", "updated_at", "completed_at")
    @classmethod
    def _valid_optional_timestamp(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=True)

    @model_validator(mode="after")
    def _valid_timeline_state(self) -> StageEvidence:
        terminal_states = {"completed", "skipped", "not_applicable", "blocked", "review", "failed"}
        if self.state == "active":
            if not self.started_at.strip() or not self.updated_at.strip() or self.completed_at.strip():
                raise ValueError("active stage requires started_at and updated_at without completed_at")
        elif self.state in terminal_states:
            if not self.updated_at.strip() or not self.completed_at.strip():
                raise ValueError(f"{self.state} stage requires updated_at and completed_at")
        elif self.state == "not_started":
            if any(value.strip() for value in (self.started_at, self.updated_at, self.completed_at)):
                raise ValueError("not_started stage must not carry timeline timestamps")
            if self.progress.kind != "none":
                raise ValueError("not_started stage must not carry progress")
        if self.state != "active" and self.progress.kind == "indeterminate":
            raise ValueError("non-active stage must not carry indeterminate progress")
        return self


class RouteEvidence(RunMonitorModel):
    state: Literal["available", "awaiting_evidence", "not_applicable", "unknown"]
    route: str = ""
    reason: str = ""
    reason_code: str = ""
    evidence: EvidenceRecord

    @model_validator(mode="after")
    def _available_route_has_value(self) -> RouteEvidence:
        if self.state == "available" and not self.route.strip():
            raise ValueError("available route evidence requires route")
        if self.state != "available" and self.route.strip():
            raise ValueError(f"{self.state} route evidence must not carry a route value")
        if self.state == "awaiting_evidence" and any(value.strip() for value in (self.reason, self.reason_code)):
            raise ValueError("awaiting route evidence must not carry reason values")
        return self


class RouteEvidenceSet(RunMonitorModel):
    planned: RouteEvidence
    executed: RouteEvidence
    final: RouteEvidence


class AudioTrackEvidence(RunMonitorModel):
    track_id: str = Field(min_length=1)
    stream_index: NonNegativeInt
    language: str = ""
    source_codec: str = ""
    source_channels: NonNegativeInt = 0
    source_layout: str = ""
    planned_action: str = ""
    current_action: str = ""
    state: TrackState
    started_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    output_codec: str = ""
    output_channels: NonNegativeInt = 0
    output_layout: str = ""
    is_default: bool = False
    reason_code: str = ""
    reason: str = ""
    progress: ProgressEvidence = Field(default_factory=ProgressEvidence)
    result: str = ""
    evidence: EvidenceRecord

    @field_validator("started_at", "updated_at", "completed_at")
    @classmethod
    def _valid_optional_timestamp(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=True)

    @model_validator(mode="after")
    def _valid_progress_state(self) -> AudioTrackEvidence:
        _validate_track_timeline(
            label="audio",
            state=self.state,
            started_at=self.started_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )
        if self.state != "active" and self.progress.kind == "indeterminate":
            raise ValueError("non-active audio track must not carry indeterminate progress")
        return self


class SubtitleTrackEvidence(RunMonitorModel):
    track_id: str = Field(min_length=1)
    stream_index: NonNegativeInt | None = None
    source_ordinal: NonNegativeInt | None = None
    language: str = ""
    source_codec: str = ""
    source_type: Literal["text", "image", "unknown"] = "unknown"
    source_kind: Literal["embedded", "sidecar", "unknown"] = "unknown"
    preserve: bool = True
    extract: bool = False
    convert: bool = False
    ocr: bool = False
    write_embedded: bool = False
    write_sidecar: bool = False
    planned_action: str = ""
    current_action: str = ""
    state: TrackState
    started_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    output_codec: str = ""
    output_location: Literal[
        "embedded",
        "external_sidecar",
        "burned_into_video",
        "dropped",
        "not_applicable",
        "unknown",
    ] = "unknown"
    output_path: str = ""
    parked_path: str = ""
    intended_final_path: str = ""
    reason_code: str = ""
    reason: str = ""
    step_index: NonNegativeInt = 0
    step_total: NonNegativeInt = 0
    step_name: str = ""
    progress_unit: Literal["", "items", "pages", "cues", "frames", "seconds", "bytes", "percent", "unknown"] = ""
    cue_count: NonNegativeInt | None = None
    progress: ProgressEvidence = Field(default_factory=ProgressEvidence)
    result: str = ""
    evidence: EvidenceRecord

    @field_validator("started_at", "updated_at", "completed_at")
    @classmethod
    def _valid_optional_timestamp(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=True)

    @model_validator(mode="after")
    def _valid_progress_state(self) -> SubtitleTrackEvidence:
        _validate_track_timeline(
            label="subtitle",
            state=self.state,
            started_at=self.started_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )
        if self.state != "active" and self.progress.kind == "indeterminate":
            raise ValueError("non-active subtitle track must not carry indeterminate progress")
        if self.step_index > self.step_total:
            raise ValueError("subtitle step_index must not exceed step_total")
        if self.step_total == 0 and self.step_index != 0:
            raise ValueError("subtitle step_index requires a positive step_total")
        return self


class AudioEvidence(RunMonitorModel):
    state: CollectionState
    policy_final: bool = False
    tracks: list[AudioTrackEvidence] = Field(default_factory=list)
    evidence: EvidenceRecord

    @model_validator(mode="after")
    def _unique_tracks(self) -> AudioEvidence:
        _validate_unique_track_identity(self.tracks, "audio")
        if self.state == "not_applicable" and self.tracks:
            raise ValueError("not_applicable audio evidence must not contain tracks")
        _validate_collection_active_tracks(label="audio", state=self.state, tracks=self.tracks)
        return self


class SubtitleEvidence(RunMonitorModel):
    state: CollectionState
    policy_final: bool = False
    tracks: list[SubtitleTrackEvidence] = Field(default_factory=list)
    evidence: EvidenceRecord

    @model_validator(mode="after")
    def _unique_tracks(self) -> SubtitleEvidence:
        _validate_unique_track_identity(self.tracks, "subtitle")
        if self.state == "not_applicable" and self.tracks:
            raise ValueError("not_applicable subtitle evidence must not contain tracks")
        _validate_collection_active_tracks(label="subtitle", state=self.state, tracks=self.tracks)
        return self


def _validate_unique_track_identity(tracks: list[Any], label: str) -> None:
    track_ids = [str(track.track_id) for track in tracks]
    stream_indexes = [int(track.stream_index) for track in tracks if track.stream_index is not None]
    source_ordinals = [int(track.source_ordinal) for track in tracks if getattr(track, "source_ordinal", None) is not None]
    if len(track_ids) != len(set(track_ids)):
        raise ValueError(f"duplicate {label} track_id")
    if len(stream_indexes) != len(set(stream_indexes)):
        raise ValueError(f"duplicate {label} stream_index")
    if len(source_ordinals) != len(set(source_ordinals)):
        raise ValueError(f"duplicate {label} source_ordinal")


class SidecarEvidence(RunMonitorModel):
    kind: str = Field(min_length=1)
    state: Literal["written", "parked", "failed", "review", "skipped", "unknown"]
    path: str = ""
    reason: str = ""
    evidence: EvidenceRecord


class OutputEvidence(RunMonitorModel):
    state: Literal[
        "awaiting_evidence",
        "not_applicable",
        "active",
        "verified",
        "published",
        "parked",
        "failed",
        "review",
        "unknown",
    ]
    scratch_path: str = ""
    working_output_path: str = ""
    published_path: str = ""
    parked_path: str = ""
    intended_final_path: str = ""
    size_bytes: NonNegativeInt | None = None
    verification_state: Literal["not_started", "active", "completed", "not_applicable", "failed", "blocked", "review", "unknown"]
    sidecars: list[SidecarEvidence] = Field(default_factory=list)
    evidence: EvidenceRecord


class TerminalReference(RunMonitorModel):
    kind: Literal["completed", "pending_publish", "failure", "review", "report", "manifest", "sidecar"]
    reference: str = Field(min_length=1)
    path: str = ""
    evidence: EvidenceRecord


class FailureEvidence(RunMonitorModel):
    state: Literal["none", "recoverable", "fatal", "review", "blocked", "force_stopped", "unknown"]
    reason_code: str = ""
    reason: str = ""
    retryable: bool | None = None
    reference: str = ""
    evidence: EvidenceRecord


class RecoveryEvidence(RunMonitorModel):
    owner: str = "pipeline"
    next_action: str = ""
    retryable: bool | None = None
    evidence: EvidenceRecord


class SourceIdentity(RunMonitorModel):
    value: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)


class RunMonitorItem(RunMonitorModel):
    job_id: str = Field(min_length=1)
    source_identity: SourceIdentity
    source_path: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    display_name_evidence: EvidenceRecord | None = None
    parent_context: str = ""
    position: PositiveInt
    total: PositiveInt
    lifecycle_state: ItemLifecycleState
    lifecycle_evidence: EvidenceRecord
    updated_at: str = Field(min_length=1)
    routes: RouteEvidenceSet
    stages: list[StageEvidence]
    audio: AudioEvidence
    subtitles: SubtitleEvidence
    output: OutputEvidence
    terminal_references: list[TerminalReference] = Field(default_factory=list)
    failure: FailureEvidence
    recovery: RecoveryEvidence

    @field_validator("updated_at")
    @classmethod
    def _valid_updated_at(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=False)

    @model_validator(mode="after")
    def _complete_stage_ledger(self) -> RunMonitorItem:
        stage_ids = tuple(stage.stage_id for stage in self.stages)
        if stage_ids != RUN_MONITOR_STAGE_IDS:
            raise ValueError(f"stage ledger must contain each canonical stage exactly once in order; got {stage_ids}")
        active_count = sum(stage.state == "active" for stage in self.stages)
        if active_count > 1:
            raise ValueError("stage ledger may contain at most one active stage")
        if self.lifecycle_state in TERMINAL_ITEM_LIFECYCLE_STATES and active_count:
            raise ValueError("terminal item must not retain an active stage")
        active_track_claim = any(
            collection.state == "active" or any(track.state == "active" for track in collection.tracks)
            for collection in (self.audio, self.subtitles)
        )
        if self.lifecycle_state != "active" and active_track_claim:
            raise ValueError("active track evidence requires an active item lifecycle")
        return self

    def stage(self, stage_id: RunMonitorStageId) -> StageEvidence:
        return next(stage for stage in self.stages if stage.stage_id == stage_id)


class AcceptedQueueIdentity(RunMonitorModel):
    schema_version: Literal["queue_plan_fingerprint.v1"]
    fingerprint: str = Field(min_length=1)
    accepted_count: NonNegativeInt


class StopAfterCurrentEvidence(RunMonitorModel):
    state: Literal["not_requested", "requested", "acknowledged", "stopping", "completed", "unavailable"]
    requested_at: str = ""
    evidence: EvidenceRecord

    @field_validator("requested_at")
    @classmethod
    def _valid_requested_at(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=True)


class RunOutcomeEvidence(RunMonitorModel):
    state: Literal["pending", "completed", "failed", "blocked", "review", "stopped", "force_stopped", "unknown"]
    reason_code: str = ""
    reason: str = ""
    retryable: bool | None = None
    owner: str = "pipeline"
    next_action: str = ""
    evidence: EvidenceRecord


class RunScopedCounts(RunMonitorModel):
    accepted: NonNegativeInt = 0
    queued: NonNegativeInt = 0
    active: NonNegativeInt = 0
    completed: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    skipped: NonNegativeInt = 0
    blocked: NonNegativeInt = 0
    review: NonNegativeInt = 0
    parked: NonNegativeInt = 0
    stopped: NonNegativeInt = 0


class RunSummaryEvidence(RunMonitorModel):
    run_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    mode: Literal["once"]
    scope: Literal["backend_queue"]
    accepted_queue: AcceptedQueueIdentity
    lifecycle_state: RunLifecycleState
    started_at: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)
    ended_at: str = ""
    stop_after_current: StopAfterCurrentEvidence
    outcome: RunOutcomeEvidence | None = None
    counts: RunScopedCounts
    evidence: EvidenceRecord

    @field_validator("started_at", "updated_at")
    @classmethod
    def _valid_required_timestamp(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=False)

    @field_validator("ended_at")
    @classmethod
    def _valid_ended_at(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=True)


class CurrentWorkerEvidence(RunMonitorModel):
    worker_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    state: Literal["starting", "active", "paused", "stopping", "unknown"]
    stage_id: RunMonitorStageId
    route: str = ""
    progress: ProgressEvidence = Field(default_factory=ProgressEvidence)
    updated_at: str = Field(min_length=1)
    evidence: EvidenceRecord

    @field_validator("updated_at")
    @classmethod
    def _valid_updated_at(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=False)


class RunMonitorRecord(RunMonitorModel):
    schema_version: Literal["pipeline_run_monitor.v1"] = RUN_MONITOR_SCHEMA_VERSION
    write_sequence: PositiveInt
    run: RunSummaryEvidence
    items: list[RunMonitorItem]
    current_workers: list[CurrentWorkerEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _correlated_exact_run_membership(self) -> RunMonitorRecord:
        expected_count = self.run.accepted_queue.accepted_count
        if len(self.items) != expected_count:
            raise ValueError(f"accepted item count must equal accepted_count {expected_count}; got {len(self.items)}")
        if self.run.counts.accepted != expected_count:
            raise ValueError("run-scoped accepted count must equal accepted queue count")

        job_ids = [item.job_id for item in self.items]
        source_identities = [item.source_identity.value for item in self.items]
        source_paths = [item.source_path.casefold() for item in self.items]
        positions = [item.position for item in self.items]
        if len(job_ids) != len(set(job_ids)):
            raise ValueError("duplicate job_id in accepted run workload")
        if len(source_identities) != len(set(source_identities)):
            raise ValueError("duplicate source identity in accepted run workload")
        if len(source_paths) != len(set(source_paths)):
            raise ValueError("duplicate source path in accepted run workload")
        if len(positions) != len(set(positions)):
            raise ValueError("duplicate position in accepted run workload")
        if positions != list(range(1, expected_count + 1)):
            raise ValueError("run positions must be contiguous, ordered, and one-based")
        if any(item.total != expected_count for item in self.items):
            raise ValueError("every item total must equal the accepted run workload total")

        expected_by_state = {
            state: sum(item.lifecycle_state == state for item in self.items)
            for state in ("queued", "active", "completed", "failed", "skipped", "blocked", "review", "parked", "stopped")
        }
        for state, expected in expected_by_state.items():
            if getattr(self.run.counts, state) != expected:
                raise ValueError(f"run-scoped {state} count does not match item lifecycle states")

        accepted_job_ids = set(job_ids)
        worker_ids: set[str] = set()
        for worker in self.current_workers:
            if worker.run_id != self.run.run_id:
                raise ValueError("current worker run_id must match monitor run_id")
            if worker.job_id not in accepted_job_ids:
                raise ValueError("current worker job_id must identify an accepted run item")
            if worker.worker_id in worker_ids:
                raise ValueError("duplicate current worker_id")
            worker_ids.add(worker.worker_id)
        if self.run.lifecycle_state in TERMINAL_RUN_LIFECYCLE_STATES:
            if self.current_workers:
                raise ValueError("terminal run must not retain current workers")
            nonterminal_items = [
                item.job_id for item in self.items if item.lifecycle_state not in TERMINAL_ITEM_LIFECYCLE_STATES
            ]
            if nonterminal_items:
                raise ValueError("terminal run must not retain nonterminal items")
            if not self.run.ended_at.strip():
                raise ValueError("terminal run requires ended_at")
        return self


class RunMonitorPointer(RunMonitorModel):
    schema_version: Literal["pipeline_run_monitor_pointer.v1"] = RUN_MONITOR_POINTER_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)

    @field_validator("updated_at")
    @classmethod
    def _valid_updated_at(cls, value: str) -> str:
        return _validated_iso_timestamp(value, optional=False)


__all__ = [
    "AUDIO_COLLECTION_STATES",
    "ITEM_LIFECYCLE_STATES",
    "RUN_LIFECYCLE_STATES",
    "RUN_MONITOR_POINTER_SCHEMA_VERSION",
    "RUN_MONITOR_PROJECTION_SCHEMA_VERSION",
    "RUN_MONITOR_SCHEMA_VERSION",
    "RUN_MONITOR_STAGE_IDS",
    "STAGE_STATES",
    "SUBTITLE_COLLECTION_STATES",
    "TERMINAL_RUN_LIFECYCLE_STATES",
    "TERMINAL_ITEM_LIFECYCLE_STATES",
    "AcceptedQueueIdentity",
    "AudioEvidence",
    "AudioTrackEvidence",
    "CurrentWorkerEvidence",
    "EvidenceRecord",
    "FailureEvidence",
    "OutputEvidence",
    "ProgressEvidence",
    "RecoveryEvidence",
    "RouteEvidence",
    "RouteEvidenceSet",
    "RunMonitorItem",
    "RunMonitorPointer",
    "RunMonitorRecord",
    "RunOutcomeEvidence",
    "RunScopedCounts",
    "RunSummaryEvidence",
    "SidecarEvidence",
    "SourceIdentity",
    "StageEvidence",
    "StopAfterCurrentEvidence",
    "SubtitleEvidence",
    "SubtitleTrackEvidence",
    "TerminalReference",
]
