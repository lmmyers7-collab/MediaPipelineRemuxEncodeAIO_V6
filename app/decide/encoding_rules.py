"""Pure helpers for Phase 06 encoding-model route triggers."""

from __future__ import annotations

from app.contracts.source_media import SourceAudioStream, SourceVideoStream
from app.decide.processing_decision import EffectiveDecisionPolicy
from app.decide.routing_facts import normalize_codec

_RESOLUTION_HEIGHTS: dict[str, int] = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "2160p": 2160,
}


def effective_resolution_limit_height(policy: EffectiveDecisionPolicy) -> int:
    """Return the maximum output height requested by the encoding model."""

    if policy.resolution_limit == "custom":
        return int(policy.custom_max_height or 0)
    return _RESOLUTION_HEIGHTS.get(policy.resolution_limit, 0)


def video_encode_filter_reasons(policy: EffectiveDecisionPolicy) -> list[str]:
    """Return active picture-transform settings that require video encode."""

    reasons = list(policy.video_filter_names)
    if policy.crop_mode in {"auto", "custom"}:
        reasons.append(f"crop:{policy.crop_mode}")
    return sorted(set(item for item in reasons if item))


def audio_transcode_reason(stream: SourceAudioStream, policy: EffectiveDecisionPolicy) -> str:
    """Return a short reason when the audio model requires transcode."""

    codec = normalize_codec(stream.codec)
    if policy.audio_force_transcode:
        return "audio policy explicitly forces transcode"
    if codec not in policy.audio_passthrough_codecs:
        return f"audio codec '{codec}' is outside passthrough policy"
    if policy.audio_max_channels > 0 and stream.channels > policy.audio_max_channels:
        return f"audio stream has {stream.channels} channels above policy cap {policy.audio_max_channels}"
    return ""


def planned_output_height(video: SourceVideoStream | None, policy: EffectiveDecisionPolicy, video_action: str) -> int:
    """Return the planned display height for structured output evidence."""

    if video is None:
        return 0
    limit = effective_resolution_limit_height(policy)
    if video_action != "encode" or limit <= 0:
        return video.height
    if policy.scaling_policy == "allow_upscale":
        return limit
    return min(video.height, limit)


__all__ = [
    "audio_transcode_reason",
    "effective_resolution_limit_height",
    "planned_output_height",
    "video_encode_filter_reasons",
]
