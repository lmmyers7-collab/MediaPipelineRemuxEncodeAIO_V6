from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import stream_signature


def parse_ffprobe_stream_signature(media_path: Path, stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout or "{}")
    streams = payload.get("streams") if isinstance(payload, dict) else []
    if not isinstance(streams, list):
        streams = []
    normalized = [stream_signature(stream) for stream in streams if isinstance(stream, dict)]
    return {
        "path": str(media_path),
        "audio": [stream for stream in normalized if stream["type"] == "audio"],
        "subtitles": [stream for stream in normalized if stream["type"] == "subtitle"],
    }
