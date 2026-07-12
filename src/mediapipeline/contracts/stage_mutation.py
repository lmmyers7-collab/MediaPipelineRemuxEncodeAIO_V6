"""Modeled mutation-capable stage request and result models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from .stage_base import MutationIntent, StageContractModel, StageData, StagePayload
from .stage_decide import DecideResult

class IngestPayload(StagePayload):
    source_path: str = Field(min_length=1)
    scratch_root: str = Field(min_length=1)
    operation: Literal["copy_to_scratch"] = "copy_to_scratch"
    intent: MutationIntent
    confirm_ingest: StrictBool = False
    operation_id: str = ""
    scratch_reservation_id: str = ""
    dry_run_fingerprint: str = ""

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> IngestPayload:
        if self.intent == "execute" and not self.confirm_ingest:
            raise ValueError("Ingest execute intent requires confirm_ingest=true.")
        if self.intent == "execute":
            try:
                UUID(self.operation_id)
            except (TypeError, ValueError, AttributeError):
                raise ValueError("Ingest execute intent requires a UUID operation_id.") from None
            if not self.scratch_reservation_id.strip():
                raise ValueError("Ingest execute intent requires scratch_reservation_id.")
            if len(self.dry_run_fingerprint) != 64 or any(ch not in "0123456789abcdef" for ch in self.dry_run_fingerprint):
                raise ValueError("Ingest execute intent requires a lowercase SHA-256 dry_run_fingerprint.")
        return self

class IngestResult(StageData):
    scratch_path: str = ""
    size_bytes: int = Field(default=0, ge=0)
    sha256: str = ""
    source_sha256: str = ""
    source_unchanged: bool = False
    evidence_path: str = ""
    rollback_actions: list[str] = Field(default_factory=list)
    recovery_actions: list[str] = Field(default_factory=list)
    boundary_checks: list[str] = Field(default_factory=list)
    operation_id: str = ""
    scratch_reservation_id: str = ""
    dry_run_fingerprint: str = ""

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
    confirm_transcode: StrictBool = False

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
    input_ass_path: str = Field(min_length=1)
    scratch_root: str = Field(min_length=1)
    source_roots: list[str] = Field(min_length=1)
    operation: Literal["ass_sidecar_to_srt"] = "ass_sidecar_to_srt"
    intent: MutationIntent
    confirm_subtitle_convert: StrictBool = False
    operation_id: str = ""
    dry_run_fingerprint: str = ""

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> SubtitleConvertPayload:
        if self.intent == "execute" and not self.confirm_subtitle_convert:
            raise ValueError("Subtitle conversion execute intent requires confirm_subtitle_convert=true.")
        if self.intent == "execute":
            try:
                UUID(self.operation_id)
            except (TypeError, ValueError, AttributeError):
                raise ValueError("Subtitle conversion execute intent requires a UUID operation_id.") from None
            if len(self.dry_run_fingerprint) != 64 or any(
                ch not in "0123456789abcdef" for ch in self.dry_run_fingerprint
            ):
                raise ValueError(
                    "Subtitle conversion execute intent requires a lowercase SHA-256 dry_run_fingerprint."
                )
        return self

class SubtitleConvertResult(StageData):
    input_ass_path: str = ""
    output_srt_path: str = ""
    tracks_converted: int = Field(default=0, ge=0)
    sidecars_written: list[str] = Field(default_factory=list)
    cues_written: int = Field(default=0, ge=0)
    encoding: str = ""
    input_sha256_before: str = ""
    input_sha256_after: str = ""
    output_sha256: str = ""
    evidence_path: str = ""
    dry_run_fingerprint: str = ""
    source_boundary_untouched: bool = False
    review_required: bool = False
    review_reason: str = ""
    rollback_actions: list[str] = Field(default_factory=list)
    recovery_actions: list[str] = Field(default_factory=list)
    boundary_checks: list[str] = Field(default_factory=list)
    operation_id: str = ""

class AudioMixPayload(StagePayload):
    scratch_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    passthrough_profile: str = "plex_balanced"
    compatible_audio_codecs: list[str] = Field(default_factory=list)
    preferred_default_languages: list[str] = Field(default_factory=list)
    intent: MutationIntent
    confirm_audio_mix: StrictBool = False

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
    confirm_publish: StrictBool = False

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
    confirm_drain: StrictBool = False

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
    scratch_root: str = Field(min_length=1)
    source_roots: list[str] = Field(min_length=1)
    proposed_name: str = Field(min_length=1)
    operation: Literal["rename_within_scratch"] = "rename_within_scratch"
    intent: MutationIntent
    confirm_apply: StrictBool = False
    operation_id: str = ""
    dry_run_fingerprint: str = ""

    @model_validator(mode="after")
    def _require_execute_confirmation(self) -> RenamePayload:
        if self.intent == "execute" and not self.confirm_apply:
            raise ValueError("Rename execute intent requires confirm_apply=true.")
        if Path(self.proposed_name).name != self.proposed_name or self.proposed_name in {".", ".."}:
            raise ValueError("Rename proposed_name must be one file name without path separators.")
        if self.intent == "execute":
            try:
                UUID(self.operation_id)
            except (TypeError, ValueError, AttributeError):
                raise ValueError("Rename execute intent requires a UUID operation_id.") from None
            if len(self.dry_run_fingerprint) != 64 or any(
                ch not in "0123456789abcdef" for ch in self.dry_run_fingerprint
            ):
                raise ValueError("Rename execute intent requires a lowercase SHA-256 dry_run_fingerprint.")
        return self

class RenameResult(StageData):
    original_path: str = ""
    final_path: str = ""
    sidecars_renamed: list[str] = Field(default_factory=list)
    undo_record_path: str = ""
    dry_run_fingerprint: str = ""
    content_sha256_before: str = ""
    content_sha256_after: str = ""
    source_boundary_untouched: bool = False
    rollback_actions: list[str] = Field(default_factory=list)
    recovery_actions: list[str] = Field(default_factory=list)
    boundary_checks: list[str] = Field(default_factory=list)
    operation_id: str = ""
