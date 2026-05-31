"""Pure Python copy/remux/encode decision engine for Phase 04."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.contracts.source_media import SourceMediaInfo, SourceVideoStream
from app.decide.encoding_rules import effective_resolution_limit_height, video_encode_filter_reasons
from app.decide.processing_decision import (
    DecisionReason,
    EffectiveDecisionPolicy,
    ProcessingDecision,
    StreamActionSet,
    VideoStreamDecision,
    decision_policy_from_mapping,
)
from app.decide.routing_facts import estimated_bitrate_mbps, normalize_codec
from app.decide.routing_outputs import finalize_decision
from app.decide.stream_actions import audio_action, container_action, subtitle_action

_PLEX_COPY_CODECS = frozenset({"h264", "avc", "hevc", "h265", "h.265"})


class _DecisionBuilder:
    def __init__(self) -> None:
        self.reasons: list[DecisionReason] = []

    def add(
        self,
        code: str,
        text: str,
        *,
        enforcement: str = "derived",
        legacy_code: str = "",
        facts: Mapping[str, Any] | None = None,
    ) -> DecisionReason:
        normalized = code.strip().upper()
        existing = next((reason for reason in self.reasons if reason.code == normalized), None)
        if existing is not None:
            return existing
        reason = DecisionReason(
            code=normalized,
            text=text,
            enforcement=enforcement,  # type: ignore[arg-type]
            legacy_code=legacy_code,
            facts=dict(facts or {}),
        )
        self.reasons.append(reason)
        return reason


def build_processing_decision(
    source: SourceMediaInfo,
    policy: EffectiveDecisionPolicy | Mapping[str, Any] | None = None,
) -> ProcessingDecision:
    """Return a structured decision without reading files or running encoders."""

    effective_policy = decision_policy_from_mapping(policy)
    builder = _DecisionBuilder()
    primary_video = source.video_streams[0] if source.video_streams else None

    if primary_video is None:
        builder.add(
            "SOURCE_UNPROBEABLE_REJECT",
            "source has no usable video stream; rejecting before route planning",
            enforcement="hard_block",
            legacy_code="source_unprobeable_reject",
        )
        actions = StreamActionSet(video=VideoStreamDecision(action="reject"), container="unknown")
        return finalize_decision(source, effective_policy, builder.reasons, actions, "reject", "source_unprobeable_reject")

    facts = _source_facts(source, primary_video, effective_policy, builder)
    video_action = _decide_video_action(primary_video, effective_policy, builder, facts)
    selected_container_action = container_action(source, effective_policy, builder)
    audio_actions = [audio_action(stream, effective_policy, builder) for stream in source.audio_streams]
    subtitle_actions = [subtitle_action(stream, effective_policy, builder) for stream in source.subtitle_streams]

    if any(stream.action == "burn" for stream in subtitle_actions):
        video_action = video_action.model_copy(
            update={
                "action": "encode",
                "reason_codes": sorted(set(video_action.reason_codes + ["SUBTITLE_BURN_IN_REQUIRES_ENCODE"])),
            }
        )
        builder.add(
            "SUBTITLE_BURN_IN_REQUIRES_ENCODE",
            "subtitle burn-in requires video encode",
            enforcement="hard_route",
            legacy_code="subtitle_burn_in_requires_encode",
        )

    actions = StreamActionSet(
        video=video_action,
        audio=audio_actions,
        subtitles=subtitle_actions,
        container=selected_container_action,
    )
    legacy_route = "encode" if video_action.action == "encode" else "remux"
    legacy_reason = _legacy_reason_for_actions(actions, builder)
    return finalize_decision(source, effective_policy, builder.reasons, actions, legacy_route, legacy_reason)


def _decide_video_action(
    video: SourceVideoStream,
    policy: EffectiveDecisionPolicy,
    builder: _DecisionBuilder,
    facts: dict[str, Any],
) -> VideoStreamDecision:
    codec = normalize_codec(video.codec)
    height = int(facts["height"])
    estimated_bitrate = float(facts["estimated_video_bitrate_mbps"])
    bitrate_cap = float(facts["direct_copy_bitrate_cap_mbps"])
    size_over = bool(facts["source_size_over_route_limit"])
    bitrate_over = bool(facts["video_bitrate_over_direct_copy_cap"])
    mode = policy.route_threshold_mode
    routing_profile = policy.routing_profile

    if codec == "unknown":
        builder.add(
            "SOURCE_UNPROBEABLE_REJECT",
            "source video codec is unknown; rejecting before route planning",
            enforcement="hard_block",
            legacy_code="source_unprobeable_reject",
            facts={"codec": codec},
        )
        return VideoStreamDecision(
            stream_index=video.stream_index,
            action="reject",
            reason_codes=["SOURCE_UNPROBEABLE_REJECT"],
        )

    filter_reasons = video_encode_filter_reasons(policy)
    if filter_reasons:
        builder.add(
            "FILTERS_ENABLED_ENCODE_REQUIRED",
            "picture transform settings require video encode",
            enforcement="hard_route",
            legacy_code="video_filters_require_encode",
            facts={"filters": filter_reasons},
        )
        return VideoStreamDecision(
            stream_index=video.stream_index,
            action="encode",
            reason_codes=["FILTERS_ENABLED_ENCODE_REQUIRED"],
        )
    builder.add(
        "FILTERS_DISABLED_COPY_ALLOWED",
        "no video picture filters require encode",
        facts={"filters": []},
    )

    requested_height = effective_resolution_limit_height(policy)
    if requested_height > 0 and height > requested_height:
        builder.add(
            "RESOLUTION_EXCEEDS_LIMIT",
            f"source height {height}p exceeds requested output limit {requested_height}p; downscale requires encode",
            enforcement="hard_route",
            legacy_code="resolution_over_policy",
            facts={"height": height, "limit": requested_height, "resolution_limit": policy.resolution_limit},
        )
        return VideoStreamDecision(stream_index=video.stream_index, action="encode", reason_codes=["RESOLUTION_EXCEEDS_LIMIT"])

    if height > 0 and policy.max_direct_copy_height > 0 and height > policy.max_direct_copy_height:
        builder.add(
            "RESOLUTION_EXCEEDS_LIMIT",
            f"source height {height}p exceeds direct-copy limit {policy.max_direct_copy_height}p",
            enforcement="hard_route",
            legacy_code="resolution_over_policy",
            facts={"height": height, "limit": policy.max_direct_copy_height},
        )
        return VideoStreamDecision(stream_index=video.stream_index, action="encode", reason_codes=["RESOLUTION_EXCEEDS_LIMIT"])

    if height > 0:
        builder.add(
            "RESOLUTION_UNDER_LIMIT",
            f"source height {height}p is within direct-copy limit {policy.max_direct_copy_height}p",
            facts={"height": height, "limit": policy.max_direct_copy_height},
        )

    bitrate_threshold_enabled = mode in {"compatibility_advisory", "bitrate", "size_or_bitrate"}
    size_threshold_enabled = mode in {"compatibility_advisory", "size", "size_or_bitrate"}
    hard_size_threshold_mode = mode in {"size", "size_or_bitrate"}
    if estimated_bitrate <= 0:
        builder.add(
            "MISSING_BITRATE_METADATA",
            "source bitrate metadata is missing; bitrate cap is advisory for this decision",
            enforcement="advisory",
            legacy_code="missing_bitrate_metadata",
        )
    elif bitrate_over:
        if bitrate_threshold_enabled:
            builder.add(
                "VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP",
                f"estimated source bitrate {estimated_bitrate:.2f} Mbps exceeds {bitrate_cap:.2f} Mbps direct-copy cap",
                enforcement="hard_route",
                legacy_code="bitrate_over_threshold",
                facts={"estimated_mbps": estimated_bitrate, "cap_mbps": bitrate_cap},
            )
            return VideoStreamDecision(
                stream_index=video.stream_index,
                action="encode",
                reason_codes=["VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP"],
            )
        builder.add(
            "VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP",
            f"estimated source bitrate {estimated_bitrate:.2f} Mbps exceeds {bitrate_cap:.2f} Mbps, but mode {mode} ignores bitrate",
            enforcement="advisory",
            legacy_code="bitrate_threshold_ignored",
            facts={"estimated_mbps": estimated_bitrate, "cap_mbps": bitrate_cap, "route_threshold_mode": mode},
        )
    else:
        builder.add(
            "VIDEO_BITRATE_UNDER_DIRECT_COPY_CAP",
            f"estimated source bitrate {estimated_bitrate:.2f} Mbps is within {bitrate_cap:.2f} Mbps direct-copy cap",
            facts={"estimated_mbps": estimated_bitrate, "cap_mbps": bitrate_cap},
        )

    h264_ok = _h264_plex_compatible(video, policy, facts)
    size_blocks_early_copy = size_over and (
        hard_size_threshold_mode or (mode == "compatibility_advisory" and routing_profile == "archive_shrink")
    )
    if h264_ok and not size_blocks_early_copy:
        builder.add(
            "SOURCE_CODEC_COMPATIBLE",
            "H.264 source is compatible with direct-copy policy",
            legacy_code="plex_compatible_h264_remux",
            facts={"codec": codec},
        )
        return VideoStreamDecision(stream_index=video.stream_index, action="copy", reason_codes=["SOURCE_CODEC_COMPATIBLE"])

    if size_over and size_threshold_enabled:
        size_forces_encode = hard_size_threshold_mode or (
            (routing_profile == "archive_shrink" or policy.size_guard_mode == "strict") and routing_profile != "manual"
        )
        if _plex_copy_candidate(video, policy, facts) and not size_forces_encode:
            builder.add(
                "SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT",
                "source size exceeds the route limit, but compatibility policy treats this as advisory",
                enforcement="soft_target",
                legacy_code="plex_compatible_size_advisory",
                facts={"size_gb": facts["source_size_gb"], "limit_gb": facts["route_size_limit_gb"]},
            )
        else:
            builder.add(
                "SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT",
                "source size exceeds the route limit and forces encode under the effective policy",
                enforcement="hard_route",
                legacy_code="size_over_threshold",
                facts={"size_gb": facts["source_size_gb"], "limit_gb": facts["route_size_limit_gb"]},
            )
            return VideoStreamDecision(
                stream_index=video.stream_index,
                action="encode",
                reason_codes=["SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT"],
            )

    if codec in policy.direct_copy_video_codecs:
        builder.add(
            "SOURCE_CODEC_COMPATIBLE",
            f"source codec '{codec}' is direct-copy safe",
            legacy_code="codec_remux_safe",
            facts={"codec": codec},
        )
        return VideoStreamDecision(stream_index=video.stream_index, action="copy", reason_codes=["SOURCE_CODEC_COMPATIBLE"])

    builder.add(
        "SOURCE_CODEC_INCOMPATIBLE",
        f"source codec '{codec}' is not direct-copy safe; video encode is required",
        enforcement="hard_route",
        legacy_code="codec_not_remux_safe",
        facts={"codec": codec, "allowed": policy.direct_copy_video_codecs},
    )
    return VideoStreamDecision(stream_index=video.stream_index, action="encode", reason_codes=["SOURCE_CODEC_INCOMPATIBLE"])


def _source_facts(
    source: SourceMediaInfo,
    video: SourceVideoStream,
    policy: EffectiveDecisionPolicy,
    builder: _DecisionBuilder,
) -> dict[str, Any]:
    media_type = source.container.media_type
    conservative_media_type = media_type
    if media_type == "unknown":
        conservative_media_type = "tv"
        builder.add(
            "MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP",
            "media type is unknown; using the most conservative movie/TV route caps",
            enforcement="advisory",
            legacy_code="media_type_unknown_conservative_cap",
        )

    movie_size = policy.movie_route_size_limit_gb
    tv_size = policy.tv_route_size_limit_gb
    movie_bitrate = policy.movie_direct_copy_max_bitrate_mbps
    tv_bitrate = policy.tv_direct_copy_max_bitrate_mbps
    if media_type == "unknown":
        size_limit = min(value for value in (movie_size, tv_size) if value > 0) if any((movie_size, tv_size)) else 0.0
        bitrate_cap = min(value for value in (movie_bitrate, tv_bitrate) if value > 0) if any((movie_bitrate, tv_bitrate)) else 0.0
    elif conservative_media_type == "tv":
        size_limit = tv_size
        bitrate_cap = tv_bitrate
    else:
        size_limit = movie_size
        bitrate_cap = movie_bitrate

    if policy.allow_h264_compatible_direct_copy and normalize_codec(video.codec) in {"h264", "avc"}:
        if policy.h264_direct_copy_max_bitrate_mbps > 0 and bitrate_cap > 0:
            bitrate_cap = min(bitrate_cap, policy.h264_direct_copy_max_bitrate_mbps)

    estimated = estimated_bitrate_mbps(source, video)
    size_gb = source.container.file_size_bytes / (1024.0**3) if source.container.file_size_bytes > 0 else 0.0
    bitrate_over = bool(estimated > 0 and bitrate_cap > 0 and estimated > bitrate_cap)
    size_over = bool(size_gb > 0 and size_limit > 0 and size_gb > size_limit)
    return {
        "media_type": media_type,
        "effective_media_type": conservative_media_type,
        "codec": normalize_codec(video.codec),
        "height": video.height,
        "duration_seconds": source.container.duration_seconds,
        "source_size_bytes": source.container.file_size_bytes,
        "source_size_gb": round(size_gb, 3),
        "route_size_limit_gb": size_limit,
        "estimated_video_bitrate_mbps": round(estimated, 3),
        "direct_copy_bitrate_cap_mbps": bitrate_cap,
        "source_size_over_route_limit": size_over,
        "video_bitrate_over_direct_copy_cap": bitrate_over,
        "routing_profile": policy.routing_profile,
        "route_threshold_mode": policy.route_threshold_mode,
    }


def _h264_plex_compatible(video: SourceVideoStream, policy: EffectiveDecisionPolicy, facts: Mapping[str, Any]) -> bool:
    if not policy.allow_h264_compatible_direct_copy:
        return False
    codec = normalize_codec(video.codec)
    if codec not in {"h264", "avc"}:
        return False
    if policy.h264_direct_copy_max_height > 0 and video.height > 0 and video.height > policy.h264_direct_copy_max_height:
        return False
    estimated = float(facts["estimated_video_bitrate_mbps"])
    cap = min(
        value
        for value in (
            float(facts["direct_copy_bitrate_cap_mbps"]),
            policy.h264_direct_copy_max_bitrate_mbps,
        )
        if value > 0
    )
    return estimated <= 0 or cap <= 0 or estimated <= cap


def _plex_copy_candidate(video: SourceVideoStream, policy: EffectiveDecisionPolicy, facts: Mapping[str, Any]) -> bool:
    codec = normalize_codec(video.codec)
    if codec not in _PLEX_COPY_CODECS:
        return False
    if video.height > 2160:
        return False
    estimated = float(facts["estimated_video_bitrate_mbps"])
    cap = float(facts["direct_copy_bitrate_cap_mbps"])
    return cap <= 0 or estimated <= 0 or estimated <= cap


def _legacy_reason_for_actions(actions: StreamActionSet, builder: _DecisionBuilder) -> str:
    if actions.video.action == "reject":
        return "source_unprobeable_reject"
    if actions.video.action == "encode":
        for code in (
            "VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP",
            "FILTERS_ENABLED_ENCODE_REQUIRED",
            "RESOLUTION_EXCEEDS_LIMIT",
            "SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT",
            "SOURCE_CODEC_INCOMPATIBLE",
            "SUBTITLE_BURN_IN_REQUIRES_ENCODE",
        ):
            reason = next((item for item in builder.reasons if item.code == code and item.legacy_code), None)
            if reason:
                return reason.legacy_code
        return "encode_required"
    for code in ("SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT", "SOURCE_CODEC_COMPATIBLE", "CONTAINER_REMUX_ONLY"):
        reason = next((item for item in builder.reasons if item.code == code and item.legacy_code), None)
        if reason:
            return reason.legacy_code
    return "size_within_threshold"


__all__ = ["build_processing_decision"]
