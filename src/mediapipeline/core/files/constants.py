from __future__ import annotations


MEDIA_FILE_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts", ".webm"})
SIDECAR_FILE_SUFFIXES = frozenset({".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".sup"})
VLC_LONG_PATH_THRESHOLD = 240


__all__ = [
    "MEDIA_FILE_SUFFIXES",
    "SIDECAR_FILE_SUFFIXES",
    "VLC_LONG_PATH_THRESHOLD",
]
