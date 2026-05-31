"""Canonical Pydantic contracts for pipeline stage execution.

Python owns orchestration and sends one versioned request envelope to the
PowerShell engine. PowerShell executes the requested stage and writes one
versioned result envelope to stdout. Stage-specific payload/data models live
here so generated schema, runner validation, and dispatcher tests all share
one contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

STAGE_SCHEMA_VERSION: Literal["v1"] = "v1"


class StageName(str, Enum):
    """Canonical stage names dispatched by engine/entrypoint.ps1."""

    ingest = "ingest"
    probe = "probe"
    decide = "decide"
    transcode = "transcode"
    subtitle_convert = "subtitle-convert"
    audio_mix = "audio-mix"
    publish = "publish"
    drain = "drain"
    rename = "rename"


MutationIntent = Literal["dry_run", "execute"]


class StageContractModel(BaseModel):
    """Strict base for JSON-wire stage models."""

    model_config = ConfigDict(extra="forbid")


class StagePayload(StageContractModel):
    """Base request payload fields shared by every stage."""

    run_id: str = ""
    job_id: str = ""


class StageData(StageContractModel):
    """Base stage data model returned inside StageResult.data."""


class StageError(StageContractModel):
    """Structured error returned when a stage fails."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class StreamSummary(StageContractModel):
    index: int = Field(ge=0)
    kind: Literal["video", "audio", "subtitle", "data", "attachment"]
    codec: str = ""
    language: str = ""
    bitrate_bps: int = Field(default=0, ge=0)
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    channels: int = Field(default=0, ge=0)
    title: str = ""
    default: bool = False
    forced: bool = False


class IngestPayload(StagePayload):
    source_path: str = Field(min_length=1)
    scratch_root: str = Field(min_length=1)
    intent: Literal["copy_to_scratch"]


class IngestResult(StageData):
    scratch_path: str = ""
    size_bytes: int = Field(default=0, ge=0)
    sha256: str = ""


class ProbePayload(StagePayload):
    scratch_path: str = Field(min_length=1)


class ProbeResult(StageData):
    probe_ok: bool = False
    probe_error: str = ""
    tool_path: str = ""
    container: str = ""
    duration_seconds: float = Field(default=0.0, ge=0)
    bitrate_bps: int = Field(default=0, ge=0)
    video_codec: str = "unknown"
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    is_hdr: bool = False
    color_transfer: str = ""
    container_bitrate_mbps: float = Field(default=0.0, ge=0)
    estimated_bitrate_mbps: float = Field(default=0.0, ge=0)
    size_bytes: int = Field(default=0, ge=0)
    streams: list[StreamSummary] = Field(default_factory=list)


class DecidePayload(StagePayload):
    file_size_bytes: int = Field(ge=0)
    is_tv: bool = False
    duration_seconds: float = Field(default=0.0, ge=0)
    video_codec: str = ""
    video_height: int = Field(default=0, ge=0, le=4320)
    is_hdr: bool = False
    routing_profile: Literal[
        "plex_direct_stream",
        "plex_direct_play",
        "archive_shrink",
        "archive_quality",
        "manual",
    ] = "plex_direct_stream"
    route_threshold_mode: Literal[
        "compatibility_advisory",
        "size",
        "bitrate",
        "size_or_bitrate",
    ] = "compatibility_advisory"
    size_guard_mode: Literal["advisory", "strict", "off"] = "advisory"
    encode_threshold_gb: float = Field(default=8, gt=0)
    tv_encode_threshold_gb: float = Field(default=3, gt=0)
    movie_route_max_video_bitrate_mbps: float = Field(default=35.0, gt=0, le=500)
    tv_route_max_video_bitrate_mbps: float = Field(default=18.0, gt=0, le=500)
    allow_h264_remux_if_plex_compatible: bool = True
    h264_remux_max_bitrate_mbps: float = Field(default=35.0, gt=0)
    h264_remux_max_height: int = Field(default=1080, ge=1, le=4320)
    route_hints: dict[str, Any] = Field(default_factory=dict)
    source_media_profile: dict[str, Any] = Field(default_factory=dict)


class DecideResult(StageData):
    route: Literal["remux", "encode", "skip"]
    should_encode: bool = False
    reason_code: str = ""
    reason: str = ""
    display_route: str = ""
    source_codec: str = ""
    size_gb: float = Field(default=0.0, ge=0)
    threshold_gb: float = Field(default=0.0, ge=0)
    requires_codec_probe: bool = False
    fallback_from_remux: bool = False
    estimated_bitrate_mbps: float = Field(default=0.0, ge=0)
    bitrate_threshold_mbps: float = Field(default=0.0, ge=0)
    size_over_threshold: bool = False
    bitrate_over_threshold: bool = False
    plex_compatibility_score: float = Field(default=0.0, ge=0, le=100)
    routing_profile: str = ""
    route_threshold_mode: str = ""
    size_guard_mode: str = ""
    encoder_profile: str = ""
    actions: dict[str, Any] = Field(default_factory=dict)
    decision_trace: list[dict[str, Any]] = Field(default_factory=list)
    route_hints: dict[str, Any] = Field(default_factory=dict)
    source_media_profile: dict[str, Any] = Field(default_factory=dict)


class TranscodePayload(StagePayload):
    scratch_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    decision: DecideResult
    video_codec: str = Field(default="hevc_nvenc", min_length=1)
    video_preset: str = Field(default="p7", min_length=1)
    video_quality: int = Field(default=22, ge=0)
    output_container: Literal["mkv", "mp4"] = "mkv"
    extra_video_flags: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=21600, ge=1)
    intent: MutationIntent
    confirm_transcode: bool = False

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> TranscodePayload:
        if self.intent == "execute" and not self.confirm_transcode:
            raise ValueError("Transcode execute intent requires confirm_transcode=true.")
        return self


class TranscodeAttempt(StageContractModel):
    attempt_no: int = Field(ge=1)
    encoder: str = ""
    started_at: str = ""
    ended_at: str = ""
    exit_code: int = 0
    log_path: str = ""


class TranscodeResult(StageData):
    output_path: str = ""
    output_size_bytes: int = Field(default=0, ge=0)
    attempts: list[TranscodeAttempt] = Field(default_factory=list)


class SubtitleConvertPayload(StagePayload):
    scratch_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    keep_languages: list[str] = Field(default_factory=list)
    convert_tx3g_to_srt: bool = True
    convert_bdpgs_to_srt: bool = False
    bdpgs_ocr_tool_path: str = ""
    bdpgs_ocr_tessdata_path: str = ""
    intent: MutationIntent
    confirm_subtitle_convert: bool = False

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> SubtitleConvertPayload:
        if self.intent == "execute" and not self.confirm_subtitle_convert:
            raise ValueError("Subtitle conversion execute intent requires confirm_subtitle_convert=true.")
        if self.convert_bdpgs_to_srt and not self.bdpgs_ocr_tool_path.strip():
            raise ValueError("BDPGS conversion requires bdpgs_ocr_tool_path.")
        return self


class SubtitleConvertResult(StageData):
    tracks_kept: int = Field(default=0, ge=0)
    tracks_converted: int = Field(default=0, ge=0)
    sidecars_written: list[str] = Field(default_factory=list)
    review_required: bool = False
    review_reason: str = ""


class AudioMixPayload(StagePayload):
    scratch_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    passthrough_profile: str = "plex_balanced"
    compatible_audio_codecs: list[str] = Field(default_factory=list)
    preferred_default_languages: list[str] = Field(default_factory=list)
    intent: MutationIntent
    confirm_audio_mix: bool = False

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> AudioMixPayload:
        if self.intent == "execute" and not self.confirm_audio_mix:
            raise ValueError("Audio mix execute intent requires confirm_audio_mix=true.")
        return self


class AudioMixResult(StageData):
    tracks_passed_through: int = Field(default=0, ge=0)
    tracks_transcoded: int = Field(default=0, ge=0)
    tracks_downmixed: int = Field(default=0, ge=0)
    default_track_language: str = ""


class PublishPayload(StagePayload):
    output_path: str = Field(min_length=1)
    final_root: str = Field(min_length=1)
    is_tv: bool = False
    create_tv_subfolder: bool = True
    deferred_publish: bool = False
    robocopy_flags: list[str] = Field(default_factory=list)
    min_free_space_gb: int = Field(default=50, ge=0)
    intent: MutationIntent
    confirm_publish: bool = False

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> PublishPayload:
        if self.intent == "execute" and not self.confirm_publish:
            raise ValueError("Publish execute intent requires confirm_publish=true.")
        return self


class PublishResult(StageData):
    final_path: str = ""
    parked: bool = False
    pending_publish_id: str = ""
    manifest_path: str = ""


class DrainPayload(StagePayload):
    pending_publish_id: str = Field(min_length=1)
    final_root: str = Field(min_length=1)
    allow_overwrite: bool = False
    parallelism: int = Field(default=1, ge=1)
    intent: MutationIntent
    confirm_drain: bool = False

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> DrainPayload:
        if self.intent == "execute" and not self.confirm_drain:
            raise ValueError("Drain execute intent requires confirm_drain=true.")
        return self


class DrainResult(StageData):
    moved: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    manifest_path: str = ""


class RenamePayload(StagePayload):
    target_path: str = Field(min_length=1)
    proposed_name: str = Field(min_length=1)
    aggressive_episode_parsing: bool = False
    is_tv: bool = False
    intent: MutationIntent
    confirm_apply: bool = False

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> RenamePayload:
        if self.intent == "execute" and not self.confirm_apply:
            raise ValueError("Rename execute intent requires confirm_apply=true.")
        return self


class RenameResult(StageData):
    final_path: str = ""
    sidecars_renamed: list[str] = Field(default_factory=list)
    undo_record_path: str = ""


StagePayloadUnion: TypeAlias = (
    IngestPayload
    | ProbePayload
    | DecidePayload
    | TranscodePayload
    | SubtitleConvertPayload
    | AudioMixPayload
    | PublishPayload
    | DrainPayload
    | RenamePayload
)

StageDataUnion: TypeAlias = (
    IngestResult
    | ProbeResult
    | DecideResult
    | TranscodeResult
    | SubtitleConvertResult
    | AudioMixResult
    | PublishResult
    | DrainResult
    | RenameResult
)


@dataclass(frozen=True)
class StageContract:
    payload_model: type[StagePayload]
    result_model: type[StageData]
    journal_event_type: str
    mutation_capable: bool = False
    enabled_in_entrypoint: bool = False


STAGE_REGISTRY: dict[StageName, StageContract] = {
    StageName.ingest: StageContract(
        IngestPayload,
        IngestResult,
        "pipeline.stage.ingest",
        mutation_capable=True,
    ),
    StageName.probe: StageContract(
        ProbePayload,
        ProbeResult,
        "pipeline.stage.probe",
        enabled_in_entrypoint=True,
    ),
    StageName.decide: StageContract(
        DecidePayload,
        DecideResult,
        "pipeline.stage.decide",
        enabled_in_entrypoint=True,
    ),
    StageName.transcode: StageContract(
        TranscodePayload,
        TranscodeResult,
        "pipeline.stage.transcode",
        mutation_capable=True,
    ),
    StageName.subtitle_convert: StageContract(
        SubtitleConvertPayload,
        SubtitleConvertResult,
        "pipeline.stage.subtitle_convert",
        mutation_capable=True,
    ),
    StageName.audio_mix: StageContract(
        AudioMixPayload,
        AudioMixResult,
        "pipeline.stage.audio_mix",
        mutation_capable=True,
    ),
    StageName.publish: StageContract(
        PublishPayload,
        PublishResult,
        "pipeline.stage.publish",
        mutation_capable=True,
    ),
    StageName.drain: StageContract(
        DrainPayload,
        DrainResult,
        "pipeline.stage.drain",
        mutation_capable=True,
    ),
    StageName.rename: StageContract(
        RenamePayload,
        RenameResult,
        "pipeline.stage.rename",
        mutation_capable=True,
    ),
}


class StageRequest(StageContractModel):
    schema_version: Literal["v1"] = STAGE_SCHEMA_VERSION
    stage: StageName
    payload: StagePayloadUnion

    @model_validator(mode="before")
    @classmethod
    def _coerce_stage_payload(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        raw = dict(data)
        stage_value = raw.get("stage")
        if stage_value is None:
            return raw
        try:
            stage = StageName(stage_value)
        except ValueError:
            return raw
        contract = STAGE_REGISTRY.get(stage)
        if contract is None:
            return raw
        raw["payload"] = contract.payload_model.model_validate(raw.get("payload") or {})
        return raw

    @model_validator(mode="after")
    def _stage_matches_payload(self) -> StageRequest:
        expected = STAGE_REGISTRY[self.stage].payload_model
        if not isinstance(self.payload, expected):
            raise ValueError(f"Payload for stage {self.stage.value!r} must be {expected.__name__}.")
        return self


class StageResult(StageContractModel):
    schema_version: Literal["v1"] = STAGE_SCHEMA_VERSION
    stage: str = Field(min_length=1)
    ok: bool
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    journal_event_type: str = Field(min_length=1)
    data: dict[str, Any] | None = None
    error: StageError | None = None

    @model_validator(mode="after")
    def _data_or_error(self) -> StageResult:
        if self.ok:
            if self.error is not None:
                raise ValueError("Successful stage results must not include error.")
            if self.data is None:
                self.data = {}
        elif self.error is None:
            raise ValueError("Failed stage results must include error.")
        return self


class StageContractSchema(StageContractModel):
    """Schema bundle used only to generate schemas/stages.v1.schema.json."""

    request: StageRequest
    result: StageResult
    payload: StagePayloadUnion
    data: StageDataUnion


def stage_contract(stage: StageName | str) -> StageContract:
    return STAGE_REGISTRY[StageName(stage)]


def stage_payload_model(stage: StageName | str) -> type[StagePayload]:
    return stage_contract(stage).payload_model


def stage_result_model(stage: StageName | str) -> type[StageData]:
    return stage_contract(stage).result_model


def build_stage_request(stage: StageName | str, payload: StagePayload | Mapping[str, Any]) -> StageRequest:
    stage_name = StageName(stage)
    payload_model = stage_payload_model(stage_name)
    typed_payload = payload if isinstance(payload, payload_model) else payload_model.model_validate(payload)
    return StageRequest(stage=stage_name, payload=cast(StagePayloadUnion, typed_payload))


def validate_stage_data(stage: StageName | str, data: Mapping[str, Any] | StageData) -> StageData:
    data_model = stage_result_model(stage)
    if isinstance(data, data_model):
        return data
    return data_model.model_validate(data)


def stage_journal_event_type(stage: StageName | str) -> str:
    return stage_contract(stage).journal_event_type


def make_stage_result(
    *,
    stage: StageName | str,
    ok: bool,
    started_at: datetime,
    finished_at: datetime | None = None,
    data: Mapping[str, Any] | StageData | None = None,
    error: StageError | Mapping[str, Any] | None = None,
    journal_event_type: str | None = None,
) -> StageResult:
    finished = finished_at or datetime.now(timezone.utc)
    stage_text = stage.value if isinstance(stage, StageName) else str(stage)
    known_stage = stage_text in StageName._value2member_map_
    if isinstance(data, BaseModel):
        data_payload: dict[str, Any] | None = data.model_dump(mode="json")
    elif data is None:
        data_payload = None
    else:
        data_payload = dict(data)
    typed_error = None if error is None else error if isinstance(error, StageError) else StageError.model_validate(error)
    return StageResult(
        stage=stage_text,
        ok=ok,
        started_at=started_at,
        finished_at=finished,
        duration_ms=max(0, int((finished - started_at).total_seconds() * 1000)),
        journal_event_type=journal_event_type
        or (stage_journal_event_type(StageName(stage_text)) if known_stage else "pipeline.stage.unknown"),
        data=data_payload,
        error=typed_error,
    )


def validation_error_message(exc: ValidationError) -> str:
    first: Any = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = str(first.get("msg") or exc)
    return f"{location}: {message}" if location else message


__all__ = [
    "STAGE_SCHEMA_VERSION",
    "StageName",
    "MutationIntent",
    "StagePayload",
    "StageData",
    "StageError",
    "StageRequest",
    "StageResult",
    "StageContract",
    "StageContractSchema",
    "StreamSummary",
    "IngestPayload",
    "IngestResult",
    "ProbePayload",
    "ProbeResult",
    "DecidePayload",
    "DecideResult",
    "TranscodePayload",
    "TranscodeResult",
    "TranscodeAttempt",
    "SubtitleConvertPayload",
    "SubtitleConvertResult",
    "AudioMixPayload",
    "AudioMixResult",
    "PublishPayload",
    "PublishResult",
    "DrainPayload",
    "DrainResult",
    "RenamePayload",
    "RenameResult",
    "StagePayloadUnion",
    "StageDataUnion",
    "STAGE_REGISTRY",
    "stage_contract",
    "stage_payload_model",
    "stage_result_model",
    "build_stage_request",
    "validate_stage_data",
    "stage_journal_event_type",
    "make_stage_result",
    "validation_error_message",
]
