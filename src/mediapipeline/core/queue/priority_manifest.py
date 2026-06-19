from __future__ import annotations

# ==============================================================================
# src/mediapipeline/core/queue/priority_manifest.py
# ==============================================================================
# Non-destructive priority manifest — lets the operator flag any source path
# as High / Normal / Low / Hold without physically renaming it on disk.
#
# The manifest lives at:   state_root / "priority_manifest.json"
#
# Levels:
#   "high"   — processed before all normal entries (Priority Phase)
#   "normal" — default priority; remove pure default entries for this path
#   "low"    — processed after all normal movies and TV
#   "hold"   — excluded from queue entirely until released
#
# Entries may be file-level or folder-level.  A folder-level entry applies
# to every source path whose string representation starts with the folder
# path (case-insensitive on Windows).  File entries take precedence over
# folder entries.
#
# Schema (priority_manifest.json):
#   {
#     "version": 1,
#     "entries": {
#       "<normalised-path>": {
#         "level":   "high" | "normal" | "low" | "hold",
#         "reason":  "<operator note>",
#         "set_at":  "<ISO-8601 timestamp>",
#         "position": <float, optional manual-order position>
#       }
#     }
#   }
# ==============================================================================

import json
import math
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

VALID_LEVELS = frozenset({"high", "normal", "low", "hold"})
DEFAULT_LEVEL = "normal"
MANIFEST_VERSION = 1
_MISSING = object()


class PriorityManifestReadError(RuntimeError):
    """Raised when an existing priority manifest cannot be trusted."""


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def priority_manifest_path(state_root: Path) -> Path:
    """Return the canonical path to priority_manifest.json."""
    return state_root / "priority_manifest.json"


def _normalise(path: str | Path) -> str:
    """Return a normalised string key for a path (lowercased, forward slashes)."""
    return str(path).replace("\\", "/").lower().rstrip("/")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_priority_manifest(path: Path, *, fail_closed: bool = False) -> dict:
    """
    Load and validate the manifest.

    Missing manifests are treated as empty. Existing but unreadable or invalid
    manifests can either fall back to empty for legacy read-only callers or
    raise PriorityManifestReadError when fail_closed is true.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        if not isinstance(data, dict):
            return _manifest_read_failure(path, "manifest root is not an object", fail_closed=fail_closed)
        if data.get("version") != MANIFEST_VERSION:
            return _manifest_read_failure(path, "manifest version is unsupported", fail_closed=fail_closed)
        entries = data.get("entries")
        if not isinstance(entries, dict):
            return _manifest_read_failure(path, "manifest entries are not an object", fail_closed=fail_closed)
        return data
    except FileNotFoundError:
        return _empty_manifest()
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _manifest_read_failure(path, str(exc), fail_closed=fail_closed)


def _empty_manifest() -> dict:
    return {"version": MANIFEST_VERSION, "entries": {}}


def _manifest_read_failure(path: Path, reason: str, *, fail_closed: bool) -> dict:
    if fail_closed:
        raise PriorityManifestReadError(f"Priority manifest is unreadable at {path}: {reason}")
    return _empty_manifest()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_manifest_level(manifest: dict, source_path: str | Path) -> str:
    """
    Resolve the effective priority level for *source_path*.

    Resolution order (first match wins):
      1. Exact file-level entry
      2. Parent folder entries — deepest ancestor first
      3. DEFAULT_LEVEL ("normal") if no entry found

    Returns one of: "high", "normal", "low", "hold".
    """
    entries: dict = manifest.get("entries", {})
    if not entries:
        return DEFAULT_LEVEL

    norm = _normalise(source_path)

    # 1. Exact match
    if norm in entries:
        level = str(entries[norm].get("level", DEFAULT_LEVEL)).lower()
        return level if level in VALID_LEVELS else DEFAULT_LEVEL

    return _get_parent_manifest_level(entries, norm)


def has_manifest_priority_entry(manifest: dict, source_path: str | Path) -> bool:
    """Return true when a valid exact or inherited manifest priority entry applies."""
    entries: dict = manifest.get("entries", {})
    if not entries:
        return False

    norm = _normalise(source_path)
    if norm in entries:
        level = str(entries[norm].get("level", DEFAULT_LEVEL)).lower()
        return level in VALID_LEVELS

    for key, entry in entries.items():
        if key == norm:
            continue
        if norm.startswith(key + "/"):
            level = str(entry.get("level", DEFAULT_LEVEL)).lower()
            if level in VALID_LEVELS:
                return True
    return False


def _get_parent_manifest_level(entries: dict, norm: str) -> str:
    # Folder match — collect all ancestor entries, pick deepest
    best_len = -1
    best_level = DEFAULT_LEVEL
    for key, entry in entries.items():
        if key == norm:
            continue
        # A folder entry's key should not end with "/" — _normalise strips that.
        # A source path *starts with* the folder key followed by "/"
        if norm.startswith(key + "/") and len(key) > best_len:
            level = str(entry.get("level", DEFAULT_LEVEL)).lower()
            if level in VALID_LEVELS:
                best_len = len(key)
                best_level = level

    return best_level


def get_parent_manifest_level(manifest: dict, source_path: str | Path) -> str:
    """Return the inherited parent-folder priority level for *source_path*."""
    entries: dict = manifest.get("entries", {})
    if not entries:
        return DEFAULT_LEVEL
    return _get_parent_manifest_level(entries, _normalise(source_path))


def get_manifest_entry(manifest: dict, source_path: str | Path) -> dict | None:
    """Return the raw manifest entry dict for *source_path*, or None."""
    entries: dict = manifest.get("entries", {})
    norm = _normalise(source_path)
    return entries.get(norm)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def set_manifest_entry(
    manifest_path: Path,
    source_path: str | Path,
    level: str,
    reason: str = "",
    position: object = _MISSING,
) -> dict:
    """
    Atomically update a single entry in the manifest.

    If *level* is "normal", pure default entries are removed while
    manual-order/deadline fields are preserved.
    Returns the updated manifest dict.
    """
    level = str(level).lower()
    if level not in VALID_LEVELS:
        raise ValueError(f"Invalid priority level: {level!r}. Must be one of {sorted(VALID_LEVELS)}")

    manifest = read_priority_manifest(manifest_path, fail_closed=True)
    entries: dict = manifest.setdefault("entries", {})
    norm = _normalise(source_path)

    existing = entries.get(norm)
    entry = _updated_manifest_entry(
        existing if isinstance(existing, dict) else {},
        level=level,
        reason=reason,
        reason_was_supplied=True,
        set_at=datetime.now(timezone.utc).isoformat(),
        position=position,
    )

    parent_level = get_parent_manifest_level(manifest, source_path)
    if level == "normal" and parent_level == DEFAULT_LEVEL and not _entry_has_non_default_fields(entry):
        # Remove a pure default marker, but keep manual-order/deadline fields.
        entries.pop(norm, None)
    else:
        entries[norm] = entry

    _write_manifest_atomic(manifest_path, manifest)
    return manifest


def set_manifest_entries_bulk(
    manifest_path: Path,
    items: list[dict],
) -> dict:
    """
    Atomically update multiple entries in one write.

    Each item in *items* must be a dict with keys:
      path   (str)              — source path or folder
      level  (str)              — "high" | "normal" | "low" | "hold"
      reason (str, optional)    — operator note
      position (float, optional)— manual-order position
    """
    manifest = read_priority_manifest(manifest_path, fail_closed=True)
    entries: dict = manifest.setdefault("entries", {})
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in items:
        level = str(item.get("level", "normal")).lower()
        if level not in VALID_LEVELS:
            continue
        norm = _normalise(str(item.get("path", "")))
        if not norm:
            continue
        existing = entries.get(norm)
        entry = _updated_manifest_entry(
            existing if isinstance(existing, dict) else {},
            level=level,
            reason=item.get("reason", _MISSING),
            reason_was_supplied="reason" in item,
            set_at=now_iso,
            position=item.get("position", _MISSING),
        )
        parent_level = _get_parent_manifest_level(entries, norm)
        if level == "normal" and parent_level == DEFAULT_LEVEL and not _entry_has_non_default_fields(entry):
            entries.pop(norm, None)
        else:
            entries[norm] = entry

    _write_manifest_atomic(manifest_path, manifest)
    return manifest


def clear_priority_manifest(manifest_path: Path) -> dict:
    """Atomically remove every priority/hold entry from the manifest."""
    manifest = _empty_manifest()
    _write_manifest_atomic(manifest_path, manifest)
    return manifest


def _coerce_manifest_position(value: object) -> float | None:
    if value in (None, ""):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("Manual order position must be a finite number.")
    return numeric


def _updated_manifest_entry(
    existing: dict,
    *,
    level: str,
    reason: object,
    reason_was_supplied: bool,
    set_at: str,
    position: object,
) -> dict:
    entry = dict(existing)
    entry["level"] = level
    if reason_was_supplied:
        entry["reason"] = str(reason).strip()
    else:
        entry["reason"] = str(entry.get("reason", "")).strip()
    entry["set_at"] = set_at
    if position is not _MISSING:
        coerced = _coerce_manifest_position(position)
        if coerced is None:
            entry.pop("position", None)
        else:
            entry["position"] = coerced
    return entry


def _entry_has_non_default_fields(entry: dict) -> bool:
    default_keys = {"level", "reason", "set_at"}
    return any(key not in default_keys for key in entry)


def _write_manifest_atomic(path: Path, manifest: dict) -> None:
    """Write *manifest* to *path* using a temp-file + replace pattern."""
    path.parent.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    tmp = path.parent / f".{path.name}.{uid}.tmp"
    try:
        tmp.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # os.replace is atomic on the same filesystem
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Serialise for API response
# ---------------------------------------------------------------------------

def manifest_to_api_payload(manifest: dict, manifest_path: Path) -> dict:
    """Convert the manifest to a stable API-safe dict."""
    return {
        "ok": True,
        "version": manifest.get("version", MANIFEST_VERSION),
        "manifest_path": str(manifest_path),
        "entry_count": len(manifest.get("entries", {})),
        "entries": {
            k: _entry_to_api_payload(v)
            for k, v in manifest.get("entries", {}).items()
        },
    }


def _entry_to_api_payload(entry: dict) -> dict:
    payload = {
        "level": entry.get("level", DEFAULT_LEVEL),
        "reason": entry.get("reason", ""),
        "set_at": entry.get("set_at", ""),
    }
    for key in ("position", "wanted_by"):
        if key in entry:
            payload[key] = entry.get(key)
    return payload
