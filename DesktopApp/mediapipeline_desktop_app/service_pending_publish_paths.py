from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from .service_pending_publish_format import format_bytes_compact, format_pending_timestamp


def path_from_manifest(manifest: dict[str, Any], *keys: str) -> Path | None:
    for key in keys:
        value = manifest.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return Path(text)
    return None


def path_from_texts(*values: str) -> Path | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return Path(text)
    return None


def pending_item_mtime(item: Path) -> float:
    with contextlib.suppress(OSError):
        return item.stat().st_mtime
    return 0.0


def build_pending_orphan_payload_row(payload_path: Path) -> dict[str, Any]:
    size = 0
    with contextlib.suppress(OSError):
        size = payload_path.stat().st_size
    return {
        "manifest_path": "",
        "parked_at": "",
        "parked_at_display": format_pending_timestamp(pending_item_mtime(payload_path)),
        "age_text": "",
        "publish_mode": "",
        "route": "",
        "state": "orphan_payload",
        "local_file": str(payload_path),
        "local_exists": payload_path.exists(),
        "server_out": "",
        "source_path": "",
        "output_size": int(size),
        "size_text": format_bytes_compact(int(size)),
        "sidecar_count": 0,
        "missing_sidecar_count": 0,
        "sidecar_paths": [],
        "error": "Payload file has no matching .manifest.json.",
    }
