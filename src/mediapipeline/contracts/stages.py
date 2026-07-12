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
from datetime import datetime, UTC
from typing import Any, Literal, TypeAlias, cast

from pydantic import BaseModel, Field, ValidationError, model_validator

from mediapipeline.contracts.stage_base import (
    MutationIntent,
    STAGE_SCHEMA_VERSION,
    StageContractModel,
    StageData,
    StageError,
    StageName,
    StagePayload,
    StreamSummary,
)
from mediapipeline.contracts.stage_decide import DecidePayload, DecideResult
from mediapipeline.contracts.stage_mutation import (
    AudioMixPayload,
    AudioMixResult,
    DrainPayload,
    DrainResult,
    IngestPayload,
    IngestResult,
    PublishPayload,
    PublishResult,
    RenamePayload,
    RenameResult,
    SubtitleConvertPayload,
    SubtitleConvertResult,
    TranscodeAttempt,
    TranscodePayload,
    TranscodeResult,
)
from mediapipeline.contracts.stage_probe import ProbePayload, ProbeResult


























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
    execution_backend: Literal["disabled", "powershell", "python"] = "disabled"
    enablement_blocker: str = ""
    required_validation: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.execution_backend == "disabled" and self.mutation_capable and not self.enablement_blocker:
            raise ValueError("Disabled mutation-capable stages require an enablement blocker.")
        if self.execution_backend != "disabled" and self.enablement_blocker:
            raise ValueError("Enabled stages cannot retain an enablement blocker.")

    @property
    def enabled_in_dispatcher(self) -> bool:
        return self.execution_backend != "disabled"

    @property
    def enabled_in_entrypoint(self) -> bool:
        """Compatibility evidence for stages implemented by the PowerShell entrypoint."""

        return self.execution_backend == "powershell"


STAGE_REGISTRY: dict[StageName, StageContract] = {
    StageName.ingest: StageContract(
        IngestPayload,
        IngestResult,
        "pipeline.stage.ingest",
        mutation_capable=True,
        execution_backend="powershell",
    ),
    StageName.probe: StageContract(
        ProbePayload,
        ProbeResult,
        "pipeline.stage.probe",
        execution_backend="powershell",
    ),
    StageName.decide: StageContract(
        DecidePayload,
        DecideResult,
        "pipeline.stage.decide",
        execution_backend="powershell",
    ),
    StageName.transcode: StageContract(
        TranscodePayload,
        TranscodeResult,
        "pipeline.stage.transcode",
        mutation_capable=True,
        enablement_blocker="production_ffmpeg_policy_parity_and_real_media_required",
        required_validation=(
            "powershell_unit_and_reliability",
            "tool_integration",
            "representative_encode_and_remux_media",
            "stream_mapping_and_recovery_parity",
        ),
    ),
    StageName.subtitle_convert: StageContract(
        SubtitleConvertPayload,
        SubtitleConvertResult,
        "pipeline.stage.subtitle_convert",
        mutation_capable=True,
        execution_backend="python",
    ),
    StageName.audio_mix: StageContract(
        AudioMixPayload,
        AudioMixResult,
        "pipeline.stage.audio_mix",
        mutation_capable=True,
        enablement_blocker="production_audio_policy_parity_and_multi_audio_real_media_required",
        required_validation=(
            "audio_policy_unit_coverage",
            "representative_multi_audio_media",
            "passthrough_transcode_downmix_default_language_parity",
        ),
    ),
    StageName.publish: StageContract(
        PublishPayload,
        PublishResult,
        "pipeline.stage.publish",
        mutation_capable=True,
        enablement_blocker="manifest_publish_transaction_parity_and_real_media_required",
        required_validation=(
            "publish_partial_and_sidecar_transaction_parity",
            "pending_park_and_recovery_fixture_coverage",
            "representative_publish_media",
            "final_placement_proof",
        ),
    ),
    StageName.drain: StageContract(
        DrainPayload,
        DrainResult,
        "pipeline.stage.drain",
        mutation_capable=True,
        enablement_blocker="pending_manifest_transaction_parity_and_deferred_publish_real_media_required",
        required_validation=(
            "trusted_pending_manifest_parity",
            "copy_hash_sidecar_and_attempt_state_recovery",
            "pending_publish_fixture_coverage",
            "representative_deferred_publish_to_drain_media",
        ),
    ),
    StageName.rename: StageContract(
        RenamePayload,
        RenameResult,
        "pipeline.stage.rename",
        mutation_capable=True,
        execution_backend="python",
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
    """Schema bundle used only to generate src/mediapipeline/contracts/schemas/stages.v1.schema.json."""

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
    finished = finished_at or datetime.now(UTC)
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
