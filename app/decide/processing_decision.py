"""Strict DTOs for Python-owned copy/remux/encode decisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.decision_policy import EffectiveDecisionPolicy
from app.contracts.verification import (
    OutputSizeCheckAction,
    VerificationGuard,
    VerificationResult,
)

PROCESSING_DECISION_SCHEMA_VERSION: Literal["processing_decision.v1"] = "processing_decision.v1"

VideoAction = Literal["copy", "encode", "reject", "unknown"]
AudioAction = Literal["copy", "transcode", "drop", "unknown"]
SubtitleAction = Literal["copy", "convert", "burn", "drop", "unknown"]
ContainerAction = Literal["keep", "remux", "change", "unknown"]
RouteSummary = Literal["COPY", "REMUX", "ENCODE", "REJECT", "UNKNOWN"]
RuleEnforcement = Literal["hard_route", "hard_block", "soft_target", "advisory", "derived", "conditional"]
RoutingProfile = Literal["plex_direct_stream", "plex_direct_play", "archive_shrink", "archive_quality", "manual"]
RouteThresholdMode = Literal["compatibility_advisory", "size", "bitrate", "size_or_bitrate"]
SizeGuardMode = Literal["advisory", "strict", "off"]
ResolutionLimit = Literal["source", "480p", "720p", "1080p", "2160p", "custom"]
ScalingPolicy = Literal["never_upscale", "allow_upscale", "preserve_source"]
VideoTargetMode = Literal["auto", "constant_quality", "average_bitrate", "max_bitrate"]
SubtitleMode = Literal["keep", "drop", "convert_preferred", "burn_forced"]

REQUIRED_REASON_CODES: frozenset[str] = frozenset(
    {
        "SOURCE_CODEC_COMPATIBLE",
        "SOURCE_CODEC_INCOMPATIBLE",
        "VIDEO_BITRATE_UNDER_DIRECT_COPY_CAP",
        "VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP",
        "RESOLUTION_UNDER_LIMIT",
        "RESOLUTION_EXCEEDS_LIMIT",
        "FILTERS_DISABLED_COPY_ALLOWED",
        "FILTERS_ENABLED_ENCODE_REQUIRED",
        "CONTAINER_REMUX_ONLY",
        "AUDIO_PASSTHROUGH_ALLOWED",
        "AUDIO_TRANSCODE_REQUIRED",
        "SUBTITLE_BURN_IN_REQUIRES_ENCODE",
        "SUBTITLE_FORMAT_INCOMPATIBLE_WITH_CONTAINER",
        "AUDIO_CODEC_INCOMPATIBLE_WITH_CONTAINER",
        "MISSING_BITRATE_METADATA",
        "MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP",
        "SOURCE_UNPROBEABLE_REJECT",
    }
)


class DecisionModel(BaseModel):
    """Strict base for new decision contracts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DecisionReason(DecisionModel):
    code: str
    text: str
    enforcement: RuleEnforcement = "derived"
    legacy_code: str = ""
    facts: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code", mode="before")
    @classmethod
    def _normalize_code(cls, value: Any) -> str:
        return str(value).strip().upper()


class DecisionRequirement(DecisionModel):
    code: str
    text: str
    enforcement: RuleEnforcement


class VideoStreamDecision(DecisionModel):
    stream_index: int = Field(default=0, ge=0)
    action: VideoAction
    output_codec: str = ""
    reason_codes: list[str] = Field(default_factory=list)


class AudioStreamDecision(DecisionModel):
    stream_index: int = Field(default=0, ge=0)
    action: AudioAction
    output_codec: str = ""
    reason_codes: list[str] = Field(default_factory=list)


class SubtitleStreamDecision(DecisionModel):
    stream_index: int = Field(default=0, ge=0)
    action: SubtitleAction
    output_codec: str = ""
    reason_codes: list[str] = Field(default_factory=list)


class StreamActionSet(DecisionModel):
    video: VideoStreamDecision
    audio: list[AudioStreamDecision] = Field(default_factory=list)
    subtitles: list[SubtitleStreamDecision] = Field(default_factory=list)
    container: ContainerAction


class PlannedVideoEncodeOutput(DecisionModel):
    active: bool = False
    codec: str = ""
    codec_family: str = Field(default="", alias="codecFamily")
    encoder_backend: str = Field(default="", alias="encoderBackend")
    target_mode: VideoTargetMode = Field(default="auto", alias="targetMode")
    quality_target: int | None = Field(default=None, alias="qualityTarget")
    target_bitrate_mbps: float | None = Field(default=None, alias="targetBitrateMbps")
    max_bitrate_mbps: float | None = Field(default=None, alias="maxBitrateMbps")
    resolution_limit: ResolutionLimit = Field(default="source", alias="resolutionLimit")
    output_height: int = Field(default=0, ge=0, alias="outputHeight")
    filters: list[str] = Field(default_factory=list)
    forced_by: list[str] = Field(default_factory=list, alias="forcedBy")


class PlannedAudioEncodeOutput(DecisionModel):
    transcode_streams: list[int] = Field(default_factory=list, alias="transcodeStreams")
    output_codec: str = Field(default="", alias="outputCodec")
    passthrough_streams: list[int] = Field(default_factory=list, alias="passthroughStreams")
    dropped_streams: list[int] = Field(default_factory=list, alias="droppedStreams")


class PlannedSubtitleEncodeOutput(DecisionModel):
    copied_streams: list[int] = Field(default_factory=list, alias="copiedStreams")
    converted_streams: list[int] = Field(default_factory=list, alias="convertedStreams")
    burned_streams: list[int] = Field(default_factory=list, alias="burnedStreams")
    dropped_streams: list[int] = Field(default_factory=list, alias="droppedStreams")


class PlannedEncodeOutput(DecisionModel):
    video: PlannedVideoEncodeOutput = Field(default_factory=PlannedVideoEncodeOutput)
    audio: PlannedAudioEncodeOutput = Field(default_factory=PlannedAudioEncodeOutput)
    subtitles: PlannedSubtitleEncodeOutput = Field(default_factory=PlannedSubtitleEncodeOutput)
    container: str = ""
    remux_first: bool = Field(default=True, alias="remuxFirst")


class ProcessingDecision(DecisionModel):
    schema_version: Literal["processing_decision.v1"] = PROCESSING_DECISION_SCHEMA_VERSION
    stream_actions: StreamActionSet = Field(alias="streamActions")
    route_summary: RouteSummary = Field(alias="routeSummary")
    route_reasons: list[DecisionReason] = Field(default_factory=list, alias="routeReasons")
    source_facts_used: dict[str, Any] = Field(default_factory=dict, alias="sourceFactsUsed")
    hard_rules_triggered: list[DecisionReason] = Field(default_factory=list, alias="hardRulesTriggered")
    soft_targets_exceeded: list[DecisionReason] = Field(default_factory=list, alias="softTargetsExceeded")
    advisory_warnings: list[DecisionReason] = Field(default_factory=list, alias="advisoryWarnings")
    planned_output_summary: dict[str, Any] = Field(default_factory=dict, alias="plannedOutputSummary")
    planned_encode_output: PlannedEncodeOutput = Field(default_factory=PlannedEncodeOutput, alias="plannedEncodeOutput")
    verification_requirements: list[DecisionRequirement] = Field(default_factory=list, alias="verificationRequirements")
    verification_guards: list[VerificationGuard] = Field(default_factory=list, alias="verificationGuards")
    verification_result: VerificationResult = Field(default_factory=VerificationResult, alias="verificationResult")
    publish_requirements: list[DecisionRequirement] = Field(default_factory=list, alias="publishRequirements")
    effective_settings: EffectiveDecisionPolicy = Field(alias="effectiveSettings")
    legacy_route: str = Field(default="", alias="legacyRoute")
    legacy_reason_code: str = Field(default="", alias="legacyReasonCode")


_LEGACY_POLICY_ALIASES: Mapping[str, str] = {
    "RoutingProfile": "routing_profile",
    "RouteThresholdMode": "route_threshold_mode",
    "SizeGuardMode": "size_guard_mode",
    "OutputSizeCheckAction": "output_size_check_action",
    "MaxEncodeGrowthPercent": "quality_encode_growth_tolerance_percent",
    "CompatibilityEncodeGrowthPercent": "compatibility_encode_growth_tolerance_percent",
    "EncodeThresholdGB": "movie_route_size_limit_gb",
    "TVEncodeThresholdGB": "tv_route_size_limit_gb",
    "MovieRouteMaxVideoBitrateMbps": "movie_direct_copy_max_bitrate_mbps",
    "TVRouteMaxVideoBitrateMbps": "tv_direct_copy_max_bitrate_mbps",
    "AllowH264RemuxIfPlexCompatible": "allow_h264_compatible_direct_copy",
    "H264RemuxMaxBitrateMbps": "h264_direct_copy_max_bitrate_mbps",
    "H264RemuxMaxHeight": "h264_direct_copy_max_height",
    "OutputContainer": "output_container",
    "RemuxSafeVideoCodecs": "direct_copy_video_codecs",
    "VideoCodec": "video_output_codec",
    "VideoQuality": "video_quality_target",
    "AudioPassthroughProfile": "audio_passthrough_profile",
    "CompatibleAudioCodecs": "audio_passthrough_codecs",
    "AudioTranscodeCodec": "audio_transcode_codec",
    "AudioMaxChannels": "audio_max_channels",
}


def decision_policy_from_mapping(value: EffectiveDecisionPolicy | Mapping[str, Any] | None) -> EffectiveDecisionPolicy:
    """Build an effective decision policy from abstract or legacy-key mappings."""

    if isinstance(value, EffectiveDecisionPolicy):
        return value
    if value is None:
        return EffectiveDecisionPolicy()

    data: dict[str, Any] = {}
    for key, item in value.items():
        target = _LEGACY_POLICY_ALIASES.get(str(key), str(key))
        data[target] = item
    return EffectiveDecisionPolicy.model_validate(data)


def derive_route_summary(actions: StreamActionSet) -> RouteSummary:
    """Derive the display route from per-stream actions."""

    if actions.video.action == "reject":
        return "REJECT"
    if actions.video.action == "unknown" or actions.container == "unknown":
        return "UNKNOWN"
    if actions.video.action == "encode" or any(stream.action == "burn" for stream in actions.subtitles):
        return "ENCODE"
    if (
        actions.container in {"remux", "change"}
        or any(stream.action in {"transcode", "drop"} for stream in actions.audio)
        or any(stream.action in {"convert", "drop"} for stream in actions.subtitles)
    ):
        return "REMUX"
    return "COPY"


__all__ = [
    "PROCESSING_DECISION_SCHEMA_VERSION",
    "REQUIRED_REASON_CODES",
    "AudioAction",
    "AudioStreamDecision",
    "ContainerAction",
    "DecisionReason",
    "DecisionRequirement",
    "EffectiveDecisionPolicy",
    "ProcessingDecision",
    "OutputSizeCheckAction",
    "PlannedAudioEncodeOutput",
    "PlannedEncodeOutput",
    "PlannedSubtitleEncodeOutput",
    "PlannedVideoEncodeOutput",
    "RouteSummary",
    "StreamActionSet",
    "SubtitleAction",
    "SubtitleStreamDecision",
    "VideoAction",
    "VideoStreamDecision",
    "decision_policy_from_mapping",
    "derive_route_summary",
]
