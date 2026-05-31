"""Fact helpers for pure copy/remux/encode decisions."""

from __future__ import annotations

from typing import Any

from app.contracts.source_media import SourceMediaInfo, SourceVideoStream


def estimated_bitrate_mbps(source: SourceMediaInfo, video: SourceVideoStream) -> float:
    if source.container.file_size_bytes > 0 and source.container.duration_seconds > 0:
        return (source.container.file_size_bytes * 8.0) / source.container.duration_seconds / 1_000_000.0
    if video.bitrate_bps > 0:
        return video.bitrate_bps / 1_000_000.0
    if source.container.overall_bitrate_bps > 0:
        return source.container.overall_bitrate_bps / 1_000_000.0
    return 0.0


def normalize_codec(value: Any) -> str:
    text = normalize_text(value)
    return text or "unknown"


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


__all__ = ["estimated_bitrate_mbps", "normalize_codec", "normalize_text"]
