from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.queue.file_overrides import (
    FILE_OVERRIDE_BATCH_METADATA_KEY,
    FileOverrideValidationError,
    file_override_payload_warnings,
    file_overrides_to_api_payload,
    normalize_file_override_path,
    read_file_overrides,
    resolve_file_override_match,
    set_file_override_entry,
    validate_file_override_payload,
)

from .results import _mapping


SERIES_PREVIEW_SCHEMA_VERSION = "queue_file_override_series_preview.v1"
SERIES_PREVIEW_COMMAND = "queue.file_overrides.series_preview"
SERIES_APPLY_COMMAND = "queue.file_overrides.series_apply"
SERIES_PREVIEW_POST_KEYS = frozenset({"path", "proposed_override"})
SERIES_APPLY_POST_KEYS = frozenset({"path", "proposed_override", "confirm_apply", "preview_fingerprint"})
SERIES_BATCH_SCOPE = "series_current_queue"
SERIES_BATCH_ORIGIN = "series_batch"

_SEASON_FOLDER_RE = re.compile(r"^(season\s*\d+|s\d+|specials?|ovas?|ova|season\s*0+)$", re.IGNORECASE)


def unsupported_series_preview_key_errors(request: Mapping[str, Any]) -> list[str]:
    return _unsupported_key_errors(request, SERIES_PREVIEW_POST_KEYS, "series preview")


def unsupported_series_apply_key_errors(request: Mapping[str, Any]) -> list[str]:
    return _unsupported_key_errors(request, SERIES_APPLY_POST_KEYS, "series apply")


def _unsupported_key_errors(request: Mapping[str, Any], allowed: frozenset[str], label: str) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in allowed)
    if not unknown:
        return []
    return [
        f"Unsupported {label} request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(allowed))}."
    ]


def validate_series_override_payload(value: Any) -> tuple[dict[str, Any], list[str], list[str]]:
    if value in (None, ""):
        return {}, ["'proposed_override' is required."], []
    if not isinstance(value, Mapping):
        return {}, ["'proposed_override' must be an object."], []
    proposed = _mapping(value)
    errors = validate_file_override_payload(proposed)
    if not proposed and not errors:
        errors.append("'proposed_override' must contain at least one supported override field.")
    warnings = [str(item) for item in file_override_payload_warnings(proposed)]
    return proposed, errors, warnings


def file_override_series_preview_payload(
    *,
    resolved: Any,
    source_path: str,
    proposed_override: dict[str, Any],
    validation_warnings: list[str] | None = None,
) -> dict[str, Any]:
    manifest_path = getattr(resolved, "file_overrides_path", None)
    if manifest_path is None:
        return _series_preview_error("File overrides service unavailable: state_root is not configured.")

    snapshot, snapshot_error = _read_queue_snapshot(getattr(resolved, "queue_snapshot_path", None))
    if snapshot_error:
        return _series_preview_error(snapshot_error)

    rows = snapshot.get("rows") if isinstance(snapshot, Mapping) else None
    if not isinstance(rows, list):
        return _series_preview_error("Queue snapshot does not contain current queue rows.")

    source_key = normalize_file_override_path(source_path)
    selected = _find_row_by_source(rows, source_key)
    if selected is None:
        return _series_preview_error("Selected source path is not present in the latest queue snapshot; refresh Queue first.")
    if not _row_is_tv(selected):
        return _series_preview_error("Apply to Series is available only for TV queue rows.")

    selected_identity = _series_identity(selected)
    if not selected_identity.get("show_root_key"):
        return _series_preview_error("Selected TV row does not expose enough folder evidence to detect a series root.")

    manifest = read_file_overrides(Path(manifest_path))
    preview_rows = _series_preview_rows(rows, selected_identity, manifest)
    counts = _series_counts(preview_rows)
    blockers: list[str] = []
    if counts["eligible_update_count"] <= 0:
        blockers.append("No eligible current queue rows would be updated.")

    warnings = _warning_rows(validation_warnings or [])
    preview_fingerprint = _series_preview_fingerprint(
        source_key=source_key,
        selected_identity=selected_identity,
        proposed_override=proposed_override,
        preview_rows=preview_rows,
    )

    payload = {
        "ok": not blockers,
        "command": SERIES_PREVIEW_COMMAND,
        "severity": "error" if blockers else ("warning" if warnings or counts["protected_manual"] else "ok"),
        "schema_version": SERIES_PREVIEW_SCHEMA_VERSION,
        "preview_only": True,
        "message": _series_preview_message(counts, blockers),
        "selected_source_path": source_path,
        "detected": {
            "show_name": selected_identity.get("show_name", ""),
            "show_root": selected_identity.get("show_root", ""),
            "show_root_key": selected_identity.get("show_root_key", ""),
            "source_root": selected_identity.get("source_root", ""),
            "confidence": "high",
            "confidence_reason": "Same configured TV source root and same detected show folder.",
        },
        "proposed_override": proposed_override,
        "proposed_fields": _proposed_field_paths(proposed_override),
        "counts": counts,
        "rows": preview_rows,
        "warnings": warnings,
        "blockers": [{"code": "blocked", "message": message} for message in blockers],
        "preview_fingerprint": preview_fingerprint,
    }
    return payload


def file_override_series_apply_payload(
    *,
    resolved: Any,
    source_path: str,
    proposed_override: dict[str, Any],
    preview_fingerprint: str,
    validation_warnings: list[str] | None = None,
) -> dict[str, Any]:
    manifest_path = getattr(resolved, "file_overrides_path", None)
    if manifest_path is None:
        return _series_apply_error("File overrides service unavailable: state_root is not configured.")

    preview = file_override_series_preview_payload(
        resolved=resolved,
        source_path=source_path,
        proposed_override=proposed_override,
        validation_warnings=validation_warnings,
    )
    if not preview.get("ok"):
        return _series_apply_error(str(preview.get("message") or "Series preview is blocked."), preview.get("blockers"))

    actual_fingerprint = str(preview.get("preview_fingerprint") or "")
    if not preview_fingerprint or preview_fingerprint != actual_fingerprint:
        return _series_apply_error("Series preview is stale; preview the series again before applying.")

    eligible_rows = [
        row for row in preview.get("rows", [])
        if isinstance(row, Mapping) and str(row.get("action") or "") in {"will_update", "replace_prior_batch"}
    ]
    if not eligible_rows:
        return _series_apply_error("No eligible current queue rows would be updated.")

    batch_id = f"series-{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()
    detected = _mapping(preview.get("detected"))
    batch_metadata = {
        "origin": SERIES_BATCH_ORIGIN,
        "batch_id": batch_id,
        "batch_label": f"Series batch: {detected.get('show_name') or 'TV series'}",
        "batch_scope": SERIES_BATCH_SCOPE,
        "batch_source_path": source_path,
        "batch_detected_root": detected.get("show_root", ""),
        "batch_detected_name": detected.get("show_name", ""),
        "created_at": created_at,
    }

    manifest = None
    try:
        for row in eligible_rows:
            manifest = set_file_override_entry(
                Path(manifest_path),
                str(row.get("source_path") or ""),
                proposed_override,
                batch_metadata=batch_metadata,
                replace_existing=True,
            )
    except FileOverrideValidationError as exc:
        return _series_apply_error("Invalid series override payload.", exc.errors)
    except Exception as exc:
        return _series_apply_error(f"Failed to write series overrides: {exc}")
    if manifest is None:
        manifest = read_file_overrides(Path(manifest_path))

    payload = file_overrides_to_api_payload(manifest, Path(manifest_path))
    payload.update(
        {
            "ok": True,
            "command": SERIES_APPLY_COMMAND,
            "severity": "ok",
            "message": (
                f"Series override applied to {len(eligible_rows)} current queue row"
                f"{'' if len(eligible_rows) == 1 else 's'}; "
                f"{preview.get('counts', {}).get('protected_manual', 0)} manual row"
                f"{'' if preview.get('counts', {}).get('protected_manual', 0) == 1 else 's'} protected."
            ),
            "batch": batch_metadata,
            "series_preview": preview,
        }
    )
    return payload


def _read_queue_snapshot(snapshot_path: Any) -> tuple[dict[str, Any], str]:
    if snapshot_path is None:
        return {}, "Queue snapshot path is not configured; series preview is unavailable."
    path = Path(snapshot_path)
    if not path.exists():
        return {}, f"Queue snapshot was not found: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {}, f"Queue snapshot could not be read: {exc}"
    if not isinstance(data, dict):
        return {}, "Queue snapshot must be a JSON object."
    return data, ""


def _find_row_by_source(rows: list[Any], source_key: str) -> dict[str, Any] | None:
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if normalize_file_override_path(row.get("source_path") or "") == source_key:
            return dict(row)
    return None


def _row_is_tv(row: Mapping[str, Any]) -> bool:
    media_kind = str(row.get("media_kind") or "").strip().casefold()
    media_type = str(row.get("media_type") or "").strip().casefold()
    return media_kind == "tv" or media_type == "tv" or bool(row.get("is_tv"))


def _series_identity(row: Mapping[str, Any]) -> dict[str, str]:
    source_path = str(row.get("source_path") or "").strip()
    source_root = str(row.get("root_path") or row.get("source_root") or "").strip()
    relative_path = str(row.get("relative_path") or "").strip()
    relative_parts = _path_parts(relative_path)
    if source_root and relative_parts:
        show_name = relative_parts[0]
        show_root = _join_path_text(source_root, show_name)
        return _identity(source_root, show_root, show_name)

    parts = _path_parts(source_path)
    if not parts:
        return {}
    parent_parts = parts[:-1]
    if not parent_parts:
        return {}
    if _SEASON_FOLDER_RE.match(parent_parts[-1] or "") and len(parent_parts) >= 2:
        show_parts = parent_parts[:-1]
    else:
        show_parts = parent_parts
    show_name = show_parts[-1] if show_parts else str(row.get("show_sort_key") or row.get("show_folder") or "").strip()
    show_root = "/".join(show_parts)
    source_root_text = source_root or _infer_source_root_from_show_root(show_root)
    return _identity(source_root_text, show_root, show_name)


def _identity(source_root: str, show_root: str, show_name: str) -> dict[str, str]:
    return {
        "source_root": source_root,
        "source_root_key": normalize_file_override_path(source_root),
        "show_root": show_root,
        "show_root_key": normalize_file_override_path(show_root),
        "show_name": show_name,
        "show_name_key": _title_key(show_name),
    }


def _infer_source_root_from_show_root(show_root: str) -> str:
    parts = _path_parts(show_root)
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def _path_parts(value: str) -> list[str]:
    return [part for part in str(value or "").replace("\\", "/").split("/") if part]


def _join_path_text(root: str, child: str) -> str:
    root_text = str(root or "").rstrip("\\/")
    return f"{root_text}\\{child}" if root_text else child


def _title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _series_preview_rows(
    rows: list[Any],
    selected_identity: Mapping[str, str],
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    selected_show_root = str(selected_identity.get("show_root_key") or "")
    selected_show_name_key = str(selected_identity.get("show_name_key") or "")
    for index, row_value in enumerate(rows):
        if not isinstance(row_value, Mapping):
            continue
        row = dict(row_value)
        if not _row_is_tv(row):
            continue
        identity = _series_identity(row)
        source_path = str(row.get("source_path") or "").strip()
        if not source_path:
            result.append(_preview_row(row, index=index, action="issue", reason="Queue row has no source path."))
            continue
        same_show_root = str(identity.get("show_root_key") or "") == selected_show_root
        same_show_name = bool(selected_show_name_key and str(identity.get("show_name_key") or "") == selected_show_name_key)
        if not same_show_root:
            if same_show_name:
                result.append(_preview_row(row, index=index, action="skipped", reason="Same show name but different source/show root."))
            continue
        result.append(_matched_preview_row(row, index=index, manifest=manifest))
    return result


def _matched_preview_row(row: Mapping[str, Any], *, index: int, manifest: Mapping[str, Any]) -> dict[str, Any]:
    source_path = str(row.get("source_path") or "").strip()
    match = resolve_file_override_match(dict(manifest), source_path)
    entry = match.get("entry")
    if isinstance(entry, dict) and match.get("is_exact"):
        batch = _batch_metadata(entry)
        if batch:
            return _preview_row(
                row,
                index=index,
                action="replace_prior_batch",
                reason=f"Existing series batch override will be replaced ({batch.get('batch_id') or 'unknown batch'}).",
                batch=batch,
            )
        return _preview_row(row, index=index, action="protected_manual", reason="Exact manual file override is protected.")
    return _preview_row(row, index=index, action="will_update", reason="Current queue row matches the detected series root.")


def _batch_metadata(entry: Mapping[str, Any]) -> dict[str, Any]:
    batch = entry.get(FILE_OVERRIDE_BATCH_METADATA_KEY)
    if not isinstance(batch, Mapping):
        return {}
    origin = str(batch.get("origin") or "").strip()
    batch_id = str(batch.get("batch_id") or "").strip()
    if origin == SERIES_BATCH_ORIGIN or batch_id:
        return dict(batch)
    return {}


def _preview_row(
    row: Mapping[str, Any],
    *,
    index: int,
    action: str,
    reason: str,
    batch: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "index": index,
        "action": action,
        "source_path": str(row.get("source_path") or "").strip(),
        "display_name": str(row.get("display_name") or Path(str(row.get("source_path") or "")).name).strip(),
        "relative_path": str(row.get("relative_path") or "").strip(),
        "season_number": _safe_int(row.get("season_number")),
        "episode_number": _safe_int(row.get("episode_number")),
        "reason": reason,
        "batch": dict(batch or {}),
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _series_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total_rows": len(rows),
        "will_update": 0,
        "replace_prior_batch": 0,
        "protected_manual": 0,
        "skipped": 0,
        "issue": 0,
        "eligible_update_count": 0,
    }
    for row in rows:
        action = str(row.get("action") or "")
        if action in counts:
            counts[action] += 1
        if action in {"will_update", "replace_prior_batch"}:
            counts["eligible_update_count"] += 1
    return counts


def _proposed_field_paths(data: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for section_name in ("routing", "video", "audio", "subtitles"):
        section = data.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for key in sorted(section.keys()):
            paths.append(f"{section_name}.{key}")
    return paths


def _warning_rows(warnings: list[str]) -> list[dict[str, str]]:
    return [{"code": "warning", "message": str(warning)} for warning in warnings if str(warning).strip()]


def _series_preview_fingerprint(
    *,
    source_key: str,
    selected_identity: Mapping[str, str],
    proposed_override: Mapping[str, Any],
    preview_rows: list[dict[str, Any]],
) -> str:
    data = {
        "source_key": source_key,
        "show_root_key": selected_identity.get("show_root_key", ""),
        "proposed_override": proposed_override,
        "rows": [
            {
                "source_path": normalize_file_override_path(row.get("source_path") or ""),
                "action": row.get("action"),
                "batch_id": _mapping(row.get("batch")).get("batch_id", ""),
            }
            for row in preview_rows
        ],
    }
    text = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _series_preview_message(counts: Mapping[str, int], blockers: list[str]) -> str:
    if blockers:
        return "Series override preview is blocked."
    eligible = int(counts.get("eligible_update_count") or 0)
    protected = int(counts.get("protected_manual") or 0)
    return f"Series override preview ready: {eligible} row{'' if eligible == 1 else 's'} will update; {protected} manual row{'' if protected == 1 else 's'} protected."


def _series_preview_error(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": SERIES_PREVIEW_COMMAND,
        "severity": "error",
        "schema_version": SERIES_PREVIEW_SCHEMA_VERSION,
        "preview_only": True,
        "message": message,
        "errors": [message],
        "warnings": [],
        "blockers": [{"code": "blocked", "message": message}],
        "counts": {},
        "rows": [],
    }


def _series_apply_error(message: str, blockers: Any = None) -> dict[str, Any]:
    errors = [message]
    if isinstance(blockers, list):
        for blocker in blockers:
            if isinstance(blocker, Mapping):
                text = str(blocker.get("message") or "").strip()
                if text and text not in errors:
                    errors.append(text)
            elif str(blocker or "").strip() and str(blocker) not in errors:
                errors.append(str(blocker))
    return {
        "ok": False,
        "command": SERIES_APPLY_COMMAND,
        "severity": "error",
        "schema_version": "desktop_command_result.v1",
        "message": message,
        "errors": errors,
        "refresh_hint": "queue",
    }
