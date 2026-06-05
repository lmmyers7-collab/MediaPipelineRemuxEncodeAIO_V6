"""Profile-specific direct-copy predicates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mediapipeline.contracts.source_media import SourceVideoStream
from mediapipeline.core.decide.processing_decision import EffectiveDecisionPolicy
from mediapipeline.core.decide.routing_facts import normalize_codec
from mediapipeline.core.decide.routing_size_policy import _positive_min

_PLEX_COPY_CODECS = frozenset({"h264", "avc", "hevc", "h265", "h.265"})

def _h264_plex_compatible(video: SourceVideoStream, policy: EffectiveDecisionPolicy, facts: Mapping[str, Any]) -> bool:
    if not policy.allow_h264_compatible_direct_copy:
        return False
    codec = normalize_codec(video.codec)
    if codec not in {"h264", "avc"}:
        return False
    if policy.h264_direct_copy_max_height > 0 and video.height > 0 and video.height > policy.h264_direct_copy_max_height:
        return False
    estimated = float(facts["estimated_video_bitrate_mbps"])
    cap = _positive_min(
        float(facts["direct_copy_bitrate_cap_mbps"]),
        policy.h264_direct_copy_max_bitrate_mbps,
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
