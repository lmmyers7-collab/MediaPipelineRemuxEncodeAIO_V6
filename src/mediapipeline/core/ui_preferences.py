"""Neutral UI preference persistence helpers shared by API and UI code."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


UI_PREFERENCES_SCHEMA_VERSION = "desktop_ui_preferences.v1"
UI_PREFERENCES_FILE_VERSION = 1
MAX_UI_PREFERENCE_KEYS = 300
MAX_UI_PREFERENCE_VALUE_CHARS = 256_000
MAX_UI_PREFERENCES_TOTAL_CHARS = 1_000_000
_UI_PREFERENCE_KEY_RE = re.compile(r"^mediapipeline[-.][A-Za-z0-9_.:-]{1,160}$")


def ui_preferences_path(state_root: Path) -> Path:
    return Path(state_root) / "ui_preferences.json"


def _empty_preferences(*, source: str = "default") -> dict[str, Any]:
    return {
        "schema_version": UI_PREFERENCES_SCHEMA_VERSION,
        "version": UI_PREFERENCES_FILE_VERSION,
        "updated_at": "",
        "source_surface": "",
        "source": source,
        "storage": {},
    }


def _clean_storage(value: Any) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    if not isinstance(value, dict):
        return {}, ["storage must be an object"]

    cleaned: dict[str, str] = {}
    total_chars = 0
    for raw_key, raw_value in value.items():
        if len(cleaned) >= MAX_UI_PREFERENCE_KEYS:
            warnings.append(f"ignored additional keys after {MAX_UI_PREFERENCE_KEYS}")
            break
        key = str(raw_key or "").strip()
        if not _UI_PREFERENCE_KEY_RE.match(key):
            warnings.append(f"ignored unsupported key: {key[:80]}")
            continue
        text = str(raw_value)
        if len(text) > MAX_UI_PREFERENCE_VALUE_CHARS:
            warnings.append(f"ignored oversized value for key: {key}")
            continue
        if total_chars + len(key) + len(text) > MAX_UI_PREFERENCES_TOTAL_CHARS:
            warnings.append("ignored keys after total UI preference payload limit")
            break
        cleaned[key] = text
        total_chars += len(key) + len(text)
    return cleaned, warnings


def read_ui_preferences(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _empty_preferences()
    if not isinstance(payload, dict):
        return _empty_preferences()
    storage, warnings = _clean_storage(payload.get("storage"))
    result = _empty_preferences(source="state_file")
    result.update(
        {
            "updated_at": str(payload.get("updated_at") or ""),
            "source_surface": str(payload.get("source_surface") or ""),
            "storage": storage,
        }
    )
    if warnings:
        result["warnings"] = warnings
    return result


def write_ui_preferences(path: Path, storage: Any, *, source_surface: str = "") -> dict[str, Any]:
    cleaned, warnings = _clean_storage(storage)
    payload: dict[str, Any] = {
        "schema_version": UI_PREFERENCES_SCHEMA_VERSION,
        "version": UI_PREFERENCES_FILE_VERSION,
        "updated_at": datetime.now(UTC).isoformat(),
        "source_surface": str(source_surface or "")[:80],
        "source": "state_file",
        "storage": cleaned,
    }
    if warnings:
        payload["warnings"] = warnings
    _write_atomic(Path(path), payload)
    return payload


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        delay_seconds = 0.05
        for attempt in range(7):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt >= 6:
                    raise
                time.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 2, 1.0)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


__all__ = [
    "UI_PREFERENCES_SCHEMA_VERSION",
    "UI_PREFERENCES_FILE_VERSION",
    "MAX_UI_PREFERENCE_KEYS",
    "MAX_UI_PREFERENCE_VALUE_CHARS",
    "MAX_UI_PREFERENCES_TOTAL_CHARS",
    "read_ui_preferences",
    "ui_preferences_path",
    "write_ui_preferences",
]
