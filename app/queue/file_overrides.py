from __future__ import annotations

# ==============================================================================
# app/queue/file_overrides.py
# ==============================================================================
# Per-file (and per-folder) à-la-carte processing overrides.
#
# The overrides manifest lives at:   state_root / "file_overrides.json"
#
# Entries may be file-level or folder-level.  A folder-level entry applies to
# every source path whose normalised string starts with the folder key + "/".
# File-level entries take precedence over folder entries; deepest folder wins
# among folder entries.
#
# Schema (file_overrides.json):
#   {
#     "version": 1,
#     "entries": {
#       "<normalised-path>": {
#         "set_at":  "<ISO-8601>",
#         "audio": {
#           "keepTracks":           [{"language":"eng"}, {"language":"jpn"}],
#           "dropTracks":           [{"language":"und"}],
#           "renameTracks":         [{"language":"eng","channels":6,"newTitle":"English 5.1"}],
#           "maxChannels":          6,
#           "downmixMode":          "max_channels",
#           "transcodeCodec":       "eac3",
#           "transcodeBitrate":     "640k",
#           "preferDefaultLanguage":"eng"
#         },
#         "subtitles": {
#           "keepTracks":           [{"language":"eng","forced":false}],
#           "dropTracks":           [{"language":"und"}],
#           "renameTracks":         [{"language":"eng","forced":false,"newTitle":"English"}],
#           "correctLanguageTags":  {"und":"eng"},
#           "stripAll":             false
#         }
#       }
#     }
#   }
# ==============================================================================

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

FILE_OVERRIDES_VERSION = 1
_EMPTY: dict = {"version": FILE_OVERRIDES_VERSION, "entries": {}}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def file_overrides_path(state_root: Path) -> Path:
    """Return the canonical path to file_overrides.json."""
    return state_root / "file_overrides.json"


def _normalise(path: str | Path) -> str:
    return str(path).replace("\\", "/").lower().rstrip("/")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_file_overrides(path: Path) -> dict:
    """Load and validate the manifest. Returns an empty manifest on any error."""
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        if not isinstance(data, dict):
            return _empty_manifest()
        if data.get("version") != FILE_OVERRIDES_VERSION:
            return _empty_manifest()
        if not isinstance(data.get("entries"), dict):
            return _empty_manifest()
        return data
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return _empty_manifest()


def _empty_manifest() -> dict:
    return {"version": FILE_OVERRIDES_VERSION, "entries": {}}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_file_override_entry(manifest: dict, source_path: str | Path) -> dict | None:
    """
    Resolve the effective override object for *source_path*.

    Resolution order (first match wins):
      1. Exact file-level entry
      2. Deepest ancestor folder entry
      3. None — no override

    Returns a copy of the entry dict (without "set_at") or None.
    """
    entries: dict = manifest.get("entries", {})
    if not entries:
        return None

    norm = _normalise(source_path)

    # 1. Exact match
    if norm in entries:
        entry = dict(entries[norm])
        entry.pop("set_at", None)
        return entry

    # 2. Folder prefix match — deepest ancestor wins
    best_len = -1
    best_entry = None
    for key, entry in entries.items():
        if norm.startswith(key + "/") and len(key) > best_len:
            best_len = len(key)
            best_entry = entry

    if best_entry is not None:
        result = dict(best_entry)
        result.pop("set_at", None)
        return result

    return None


def list_override_entries(manifest: dict) -> list[dict]:
    """Return a list of all entries with their path and content."""
    return [
        {"path": k, **v}
        for k, v in manifest.get("entries", {}).items()
    ]


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def set_file_override_entry(
    manifest_path: Path,
    source_path: str | Path,
    override_data: dict,
) -> dict:
    """
    Atomically set or update the override for *source_path*.

    Pass an empty dict {} to clear the entry (same as calling
    ``clear_file_override_entry``).  Returns the updated manifest.
    """
    manifest = read_file_overrides(manifest_path)
    entries: dict = manifest.setdefault("entries", {})
    norm = _normalise(source_path)

    if not override_data:
        entries.pop(norm, None)
    else:
        existing = entries.get(norm, {})
        # Deep-merge: keep set_at from existing, add/replace everything else
        merged = {**existing, **_sanitise_override(override_data)}
        merged["set_at"] = datetime.now(timezone.utc).isoformat()
        entries[norm] = merged

    _write_atomic(manifest_path, manifest)
    return manifest


def clear_file_override_entry(manifest_path: Path, source_path: str | Path) -> dict:
    """Remove the override entry for *source_path*. Returns updated manifest."""
    return set_file_override_entry(manifest_path, source_path, {})


def _sanitise_override(data: dict) -> dict:
    """Remove top-level keys that are reserved / managed by the service."""
    reserved = {"set_at", "version"}
    return {k: v for k, v in data.items() if k not in reserved}


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def _write_atomic(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    tmp = path.parent / f".{path.name}.{uid}.tmp"
    try:
        tmp.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# API serialisation helper
# ---------------------------------------------------------------------------

def file_overrides_to_api_payload(manifest: dict, manifest_path: Path) -> dict:
    """Convert the manifest to a stable API-safe dict."""
    entries = manifest.get("entries", {})
    return {
        "ok":             True,
        "version":        manifest.get("version", FILE_OVERRIDES_VERSION),
        "manifest_path":  str(manifest_path),
        "entry_count":    len(entries),
        "entries": {
            k: {
                "set_at":    v.get("set_at", ""),
                "audio":     v.get("audio"),
                "subtitles": v.get("subtitles"),
            }
            for k, v in entries.items()
        },
    }
