"""Display-only adapters for legacy config to PresetV2 fields."""

from __future__ import annotations

def _video_codec_family(codec: str) -> str:
    normalized = codec.strip().lower()
    if "264" in normalized or normalized.startswith(("avc", "x264")):
        return "h264"
    if "265" in normalized or "hevc" in normalized or normalized.startswith("x265"):
        return "hevc"
    if "av1" in normalized:
        return "av1"
    if normalized == "copy":
        return "copy"
    return "hevc"

def _encoder_backend(codec: str) -> str:
    normalized = codec.strip().lower()
    if "nvenc" in normalized:
        return "nvenc"
    if normalized.startswith(("libx264", "x264")):
        return "x264"
    if normalized.startswith(("libx265", "x265")):
        return "x265"
    if "qsv" in normalized:
        return "qsv"
    if "av1" in normalized:
        return "svt_av1"
    if normalized == "copy":
        return "copy"
    return "auto"
