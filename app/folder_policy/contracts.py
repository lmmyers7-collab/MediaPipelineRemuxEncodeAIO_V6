from __future__ import annotations

from pathlib import Path
from typing import Any

from app.folder_policy.constants import FOLDER_POLICY_SCHEMA_VERSION


def default_folder_policy(folder: Path) -> dict[str, Any]:
    return {
        "schema_version": FOLDER_POLICY_SCHEMA_VERSION,
        "folder": str(folder),
        "audio": {
            "passthrough_profile": "",
            "passthrough_codecs": [],
            "preferred_default_languages": [],
            "transcode_codec": "",
            "transcode_bitrate": "",
            "downmix_mode": "",
            "max_channels": None,
        },
        "subtitles": {
            "ass": {"enabled": True},
            "tx3g": {"enabled": True},
            "bdpgs": {"enabled": False},
        },
        "routing": {
            "routing_profile": "",
            "size_guard_mode": "",
            "allow_h264_remux_if_plex_compatible": None,
            "h264_remux_max_bitrate_mbps": None,
            "h264_remux_max_height": None,
            "force_route": "auto",
            "prefer_route": "auto",
            "max_video_bitrate_mbps": None,
            "max_resolution_height": None,
            "allowed_video_codecs": [],
            "plex_strict_mode": False,
            "allow_unsafe_forced_remux": False,
            "reason": "",
        },
        "validation": {
            "sample_file": "",
            "require_uniform_stream_topology": True,
        },
    }


def stream_signature(stream: dict[str, Any]) -> dict[str, Any]:
    tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
    disposition = stream.get("disposition") if isinstance(stream.get("disposition"), dict) else {}
    return {
        "index": stream.get("index"),
        "type": str(stream.get("codec_type") or ""),
        "codec": str(stream.get("codec_name") or "").lower(),
        "channels": int(stream.get("channels") or 0),
        "language": str(tags.get("language") or "und").lower(),
        "title": str(tags.get("title") or ""),
        "default": bool(disposition.get("default")),
        "forced": bool(disposition.get("forced")),
    }


def stream_topology(signature: dict[str, Any]) -> dict[str, list[tuple[Any, ...]]]:
    return {
        "audio": [(item["codec"], item["language"], item["channels"]) for item in signature["audio"]],
        "subtitles": [(item["codec"], item["language"]) for item in signature["subtitles"]],
    }
