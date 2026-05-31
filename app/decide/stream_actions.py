"""Per-stream action helpers for the pure decision engine."""

from __future__ import annotations

from typing import Any

from app.contracts.source_media import SourceAudioStream, SourceMediaInfo, SourceSubtitleStream
from app.decide.encoding_rules import audio_transcode_reason
from app.decide.processing_decision import AudioStreamDecision, EffectiveDecisionPolicy, SubtitleStreamDecision
from app.decide.routing_facts import normalize_codec, normalize_text

_MP4_FORMAT_MARKERS = frozenset({"mp4", "mov", "m4a", "3gp", "3g2", "mj2", "quicktime"})
_MKV_FORMAT_MARKERS = frozenset({"matroska", "mkv", "webm"})


def container_action(source: SourceMediaInfo, policy: EffectiveDecisionPolicy, builder: Any) -> str:
    if policy.force_container_remux or not _container_matches(source.container.format_name, policy.output_container):
        builder.add(
            "CONTAINER_REMUX_ONLY",
            f"output container policy requires remux to {policy.output_container}",
            enforcement="conditional",
            legacy_code="container_remux_only",
            facts={"source_container": source.container.format_name, "output_container": policy.output_container},
        )
        return "remux"
    return "keep"


def audio_action(stream: SourceAudioStream, policy: EffectiveDecisionPolicy, builder: Any) -> AudioStreamDecision:
    codec = normalize_codec(stream.codec)
    if policy.output_container == "mp4" and codec not in policy.mp4_audio_copy_codecs:
        builder.add(
            "AUDIO_CODEC_INCOMPATIBLE_WITH_CONTAINER",
            f"audio codec '{codec}' cannot be copied to MP4 by the Phase 04 policy",
            enforcement="hard_route",
            legacy_code="audio_codec_incompatible_with_container",
            facts={"stream_index": stream.stream_index, "codec": codec, "output_container": policy.output_container},
        )
        builder.add(
            "AUDIO_TRANSCODE_REQUIRED",
            f"audio stream {stream.stream_index} requires transcode for container compatibility",
            enforcement="hard_route",
            legacy_code="audio_transcode_required",
        )
        return AudioStreamDecision(
            stream_index=stream.stream_index,
            action="transcode",
            output_codec="aac",
            reason_codes=["AUDIO_CODEC_INCOMPATIBLE_WITH_CONTAINER", "AUDIO_TRANSCODE_REQUIRED"],
        )

    policy_reason = audio_transcode_reason(stream, policy)
    if policy_reason:
        builder.add(
            "AUDIO_TRANSCODE_REQUIRED",
            f"audio stream {stream.stream_index} requires transcode: {policy_reason}",
            enforcement="hard_route",
            legacy_code="audio_transcode_required",
            facts={"stream_index": stream.stream_index, "codec": codec, "channels": stream.channels},
        )
        return AudioStreamDecision(
            stream_index=stream.stream_index,
            action="transcode",
            output_codec=policy.audio_transcode_codec,
            reason_codes=["AUDIO_TRANSCODE_REQUIRED"],
        )

    builder.add(
        "AUDIO_PASSTHROUGH_ALLOWED",
        f"audio codec '{codec}' can be copied under the Phase 04 container policy",
        facts={"stream_index": stream.stream_index, "codec": codec},
    )
    return AudioStreamDecision(stream_index=stream.stream_index, action="copy", reason_codes=["AUDIO_PASSTHROUGH_ALLOWED"])


def subtitle_action(stream: SourceSubtitleStream, policy: EffectiveDecisionPolicy, builder: Any) -> SubtitleStreamDecision:
    codec = normalize_codec(stream.codec)
    if policy.subtitle_mode == "drop":
        return SubtitleStreamDecision(stream_index=stream.stream_index, action="drop", reason_codes=["SUBTITLE_POLICY_DROP"])
    if policy.subtitle_burn_in_forced and stream.forced:
        builder.add(
            "SUBTITLE_BURN_IN_REQUIRES_ENCODE",
            f"forced subtitle stream {stream.stream_index} is configured for burn-in",
            enforcement="hard_route",
            legacy_code="subtitle_burn_in_requires_encode",
            facts={"stream_index": stream.stream_index, "codec": codec},
        )
        return SubtitleStreamDecision(
            stream_index=stream.stream_index,
            action="burn",
            reason_codes=["SUBTITLE_BURN_IN_REQUIRES_ENCODE"],
        )
    if policy.output_container == "mp4" and codec not in policy.mp4_subtitle_copy_codecs:
        builder.add(
            "SUBTITLE_FORMAT_INCOMPATIBLE_WITH_CONTAINER",
            f"subtitle codec '{codec}' cannot be copied to MP4 by the Phase 04 policy",
            enforcement="hard_route",
            legacy_code="subtitle_format_incompatible_with_container",
            facts={"stream_index": stream.stream_index, "codec": codec, "output_container": policy.output_container},
        )
        action = "burn" if stream.image_based else "convert"
        return SubtitleStreamDecision(
            stream_index=stream.stream_index,
            action=action,  # type: ignore[arg-type]
            output_codec="" if action == "burn" else "mov_text",
            reason_codes=["SUBTITLE_FORMAT_INCOMPATIBLE_WITH_CONTAINER"],
        )
    return SubtitleStreamDecision(stream_index=stream.stream_index, action="copy")


def _container_matches(format_name: str, output_container: str) -> bool:
    parts = {normalize_text(part) for part in format_name.replace(";", ",").split(",") if part.strip()}
    markers = _MKV_FORMAT_MARKERS if output_container == "mkv" else _MP4_FORMAT_MARKERS
    return any(part in markers for part in parts)


__all__ = ["audio_action", "container_action", "subtitle_action"]
