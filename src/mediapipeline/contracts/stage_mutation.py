"""Modeled mutation-capable stage request and result models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .stage_base import MutationIntent, StageContractModel, StageData, StagePayload
from .stage_decide import DecideResult

class IngestPayload(StagePayload):
    source_path: str = Field(min_length=1)
    scratch_root: str = Field(min_length=1)
    intent: Literal["copy_to_scratch"]

class IngestResult(StageData):
    scratch_path: str = ""
    size_bytes: int = Field(default=0, ge=0)
    sha256: str = ""

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
