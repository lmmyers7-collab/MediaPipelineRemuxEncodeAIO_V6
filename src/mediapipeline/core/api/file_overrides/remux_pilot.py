from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import uuid
from pathlib import Path
from typing import Any

from mediapipeline.core.processes.source_path_policy import path_is_under_or_equal, queue_source_roots
from mediapipeline.core.queue.file_overrides import (
    FileOverrideValidationError,
    file_overrides_to_api_payload,
    normalize_file_override_path,
    set_file_override_entries,
)

from .results import _mapping
from .series import (
    SERIES_BATCH_SCOPE,
    _read_queue_snapshot,
    _row_is_tv,
    _series_identity,
    file_override_series_preview_payload,
)


REMUX_PILOT_PROMOTE_COMMAND = "queue.file_overrides.remux_pilot_promote"
REMUX_PILOT_PROMOTE_DATA_SCHEMA = "queue_remux_pilot_promotion.v1"
REMUX_PILOT_PROMOTE_POST_KEYS = frozenset({"pilot_source_paths", "confirm_apply", "reason"})
REMUX_PILOT_PROMOTE_BATCH_ORIGIN = "remux_pilot_promotion"
REMUX_PILOT_FALLBACK_REASON_CODE = "oversized_encode_remux_fallback"
REMUX_PILOT_OVERRIDE = {"routing": {"profile": "remux"}}


def unsupported_remux_pilot_promote_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in REMUX_PILOT_PROMOTE_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported remux pilot promotion request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(REMUX_PILOT_PROMOTE_POST_KEYS))}."
    ]


def file_override_remux_pilot_promote_payload(
    *,
    resolved: Any,
    pilot_source_paths: Any,
    reason: str = "",
) -> dict[str, Any]:
    manifest_path = getattr(resolved, "file_overrides_path", None)
    if manifest_path is None:
        return _promotion_error("File overrides service unavailable: state_root is not configured.")

    pilot_paths, pilot_path_errors = _validated_pilot_paths(resolved, pilot_source_paths)
    if pilot_path_errors:
        return _promotion_error("Remux pilot promotion is blocked.", pilot_path_errors)

    completed_rows, completed_error = _read_completed_rows(getattr(resolved, "completed_manifest_path", None))
    if completed_error:
        return _promotion_error(completed_error)

    pilot_evidence, pilot_errors = _pilot_evidence_rows(
        resolved=resolved,
        pilot_paths=pilot_paths,
        completed_rows=completed_rows,
    )
    detected_series = _detected_series_from_pilots(pilot_evidence)
    if pilot_errors:
        return _promotion_error(
            "Remux pilot promotion is blocked by pilot evidence.",
            pilot_errors,
            pilot_evidence=pilot_evidence,
            detected_series=detected_series,
        )

    snapshot, snapshot_error = _read_queue_snapshot(getattr(resolved, "queue_snapshot_path", None))
    if snapshot_error:
        return _promotion_error(snapshot_error, pilot_evidence=pilot_evidence, detected_series=detected_series)
    rows = snapshot.get("rows") if isinstance(snapshot, Mapping) else None
    if not isinstance(rows, list):
        return _promotion_error(
            "Queue snapshot does not contain current queue rows.",
            pilot_evidence=pilot_evidence,
            detected_series=detected_series,
        )

    pilot_keys = {normalize_file_override_path(path) for path in pilot_paths}
    selected_source_path, selected_error = _selected_current_series_row(rows, detected_series, pilot_keys)
    if selected_error:
        return _promotion_error(
            selected_error,
            pilot_evidence=pilot_evidence,
            detected_series=detected_series,
        )

    preview = file_override_series_preview_payload(
        resolved=resolved,
        source_path=selected_source_path,
        proposed_override=dict(REMUX_PILOT_OVERRIDE),
    )
    if not preview.get("ok"):
        return _promotion_error(
            str(preview.get("message") or "Series preview is blocked."),
            _error_messages_from_preview(preview),
            pilot_evidence=pilot_evidence,
            detected_series=detected_series,
            preview=preview,
        )

    promotion_rows = _promotion_preview_rows(preview, pilot_keys)
    counts = _promotion_counts(promotion_rows)
    if counts["eligible_update_count"] <= 0:
        return _promotion_error(
            "No eligible remaining current queue rows would be updated.",
            ["No eligible remaining current queue rows would be updated."],
            pilot_evidence=pilot_evidence,
            detected_series=detected_series,
            preview={**preview, "rows": promotion_rows, "counts": counts},
        )

    eligible_rows = [
        row for row in promotion_rows
        if str(row.get("action") or "") in {"will_update", "replace_prior_batch"}
    ]
    batch_metadata = _promotion_batch_metadata(
        detected_series=detected_series,
        selected_source_path=selected_source_path,
        pilot_paths=pilot_paths,
        reason=reason,
    )

    try:
        manifest = set_file_override_entries(
            Path(manifest_path),
            [(str(row.get("source_path") or ""), dict(REMUX_PILOT_OVERRIDE)) for row in eligible_rows],
            batch_metadata=batch_metadata,
            replace_existing=True,
        )
    except FileOverrideValidationError as exc:
        return _promotion_error(
            "Invalid remux pilot promotion payload.",
            list(exc.errors),
            pilot_evidence=pilot_evidence,
            detected_series=detected_series,
            preview={**preview, "rows": promotion_rows, "counts": counts},
        )
    except Exception as exc:
        return _promotion_error(
            f"Failed to write series overrides: {exc}",
            pilot_evidence=pilot_evidence,
            detected_series=detected_series,
            preview={**preview, "rows": promotion_rows, "counts": counts},
        )

    payload = file_overrides_to_api_payload(manifest, Path(manifest_path))
    protected = counts.get("protected_manual", 0)
    skipped = counts.get("skipped", 0)
    payload.update(
        {
            "ok": True,
            "command": REMUX_PILOT_PROMOTE_COMMAND,
            "data_schema": REMUX_PILOT_PROMOTE_DATA_SCHEMA,
            "severity": "warning" if protected or skipped else "ok",
            "message": (
                f"Remux fallback pilot promotion applied to {counts['eligible_update_count']} current queue row"
                f"{'' if counts['eligible_update_count'] == 1 else 's'}; "
                f"{protected} manual row{'' if protected == 1 else 's'} protected."
            ),
            "pilot_evidence": pilot_evidence,
            "detected_series": detected_series,
            "counts": counts,
            "written_batch_metadata": batch_metadata,
            "batch": batch_metadata,
            "series_preview": {**preview, "rows": promotion_rows, "counts": counts},
            "blockers": [],
        }
    )
    return payload


def _validated_pilot_paths(resolved: Any, value: Any) -> tuple[list[str], list[str]]:
    if not isinstance(value, list):
        return [], ["'pilot_source_paths' must be a list of exactly 3 source paths."]
    if len(value) != 3:
        return [], ["'pilot_source_paths' must contain exactly 3 distinct source paths."]

    roots = queue_source_roots(resolved)
    if not roots:
        return [], ["SourceMovies, SourceTV, and LibraryProfiles are not configured; queue source path updates are unavailable."]

    paths: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value, start=1):
        path_text = str(raw or "").strip()
        if not path_text:
            errors.append(f"pilot_source_paths[{index}] is required.")
            continue
        candidate = Path(path_text)
        if not candidate.is_absolute():
            errors.append(f"pilot_source_paths[{index}] must be an absolute path under configured source roots.")
            continue
        if not path_is_under_or_equal(candidate, roots):
            errors.append(f"pilot_source_paths[{index}] is outside configured source roots.")
            continue
        key = normalize_file_override_path(candidate)
        if key in seen:
            errors.append("'pilot_source_paths' must contain exactly 3 distinct source paths.")
            continue
        seen.add(key)
        paths.append(str(candidate))
    if len(paths) != 3 and not any("exactly 3" in error for error in errors):
        errors.append("'pilot_source_paths' must contain exactly 3 distinct source paths.")
    return paths, errors


def _read_completed_rows(manifest_path: Any) -> tuple[list[dict[str, Any]], str]:
    if manifest_path is None:
        return [], "Completed manifest path is not configured; pilot evidence is unavailable."
    path = Path(manifest_path)
    if not path.exists():
        return [], f"Completed manifest was not found: {path}"
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            text = line.strip()
            if not text:
                continue
            parsed = json.loads(text)
            if isinstance(parsed, Mapping):
                rows.append(dict(parsed))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [], f"Completed manifest could not be read: {exc}"
    return rows, ""


def _pilot_evidence_rows(
    *,
    resolved: Any,
    pilot_paths: list[str],
    completed_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    completed_by_source: dict[str, dict[str, Any]] = {}
    for row in completed_rows:
        source_key = normalize_file_override_path(row.get("source_path") or "")
        if source_key:
            completed_by_source[source_key] = row

    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    show_root_keys: set[str] = set()
    for path_text in pilot_paths:
        source_key = normalize_file_override_path(path_text)
        row = completed_by_source.get(source_key)
        identity = _pilot_series_identity(resolved, path_text)
        show_root_key = str(identity.get("show_root_key") or "")
        if show_root_key:
            show_root_keys.add(show_root_key)

        item = {
            "source_path": path_text,
            "source_key": source_key,
            "completed": bool(row),
            "final_route": "",
            "route_reason_code": "",
            "fallback_remux_triggered": False,
            "publish_state": "",
            "media_type": "",
            "detected_series": identity,
        }
        if not row:
            errors.append(f"Pilot source has no completed evidence: {path_text}")
            evidence.append(item)
            continue

        final_route = _route_text(row)
        reason_code = _route_reason_code(row)
        fallback_triggered = _fallback_size_policy_triggered(row)
        publish_state = _publish_state(row)
        media_type = str(row.get("media_type") or row.get("media_kind") or "").strip().casefold()
        item.update(
            {
                "final_route": final_route,
                "route_reason_code": reason_code,
                "fallback_remux_triggered": fallback_triggered,
                "publish_state": publish_state,
                "media_type": media_type,
            }
        )

        if not _completed_row_is_tv(resolved, row, path_text):
            errors.append(f"Pilot source is not completed TV media: {path_text}")
        if not show_root_key:
            errors.append(f"Pilot source does not expose enough folder evidence to detect a series root: {path_text}")
        if publish_state not in {"published", "completed", "success"}:
            errors.append(f"Pilot source did not complete successfully: {path_text}")
        if final_route != "remux":
            errors.append(f"Pilot source final route must be remux: {path_text}")
        if reason_code != REMUX_PILOT_FALLBACK_REASON_CODE:
            errors.append(
                f"Pilot source route_reason_code must be {REMUX_PILOT_FALLBACK_REASON_CODE}: {path_text}"
            )
        if not fallback_triggered:
            errors.append(f"Pilot source lacks structured fallback-remux size-policy evidence: {path_text}")
        evidence.append(item)

    if len(show_root_keys) > 1:
        errors.append("Pilot sources must belong to the same detected series root.")
    return evidence, errors


def _pilot_series_identity(resolved: Any, source_path: str) -> dict[str, str]:
    root = _best_source_root(resolved, source_path)
    relative_path = ""
    if root is not None:
        try:
            relative_path = str(Path(source_path).relative_to(root))
        except ValueError:
            relative_path = ""
    return _series_identity(
        {
            "source_path": source_path,
            "root_path": str(root or ""),
            "relative_path": relative_path,
            "media_kind": "tv",
        }
    )


def _best_source_root(resolved: Any, source_path: str) -> Path | None:
    candidate = Path(source_path)
    matches = [root for root in queue_source_roots(resolved) if path_is_under_or_equal(candidate, [root])]
    if not matches:
        return None
    return max(matches, key=lambda root: len(str(root)))


def _detected_series_from_pilots(pilot_evidence: list[dict[str, Any]]) -> dict[str, str]:
    for item in pilot_evidence:
        identity = _mapping(item.get("detected_series"))
        if identity.get("show_root_key"):
            return {
                "show_name": str(identity.get("show_name") or ""),
                "show_root": str(identity.get("show_root") or ""),
                "show_root_key": str(identity.get("show_root_key") or ""),
                "source_root": str(identity.get("source_root") or ""),
                "confidence": "high",
                "confidence_reason": "All three pilot paths resolved to the same configured source show folder with TV evidence.",
            }
    return {}


def _completed_row_is_tv(resolved: Any, row: Mapping[str, Any], source_path: str) -> bool:
    media_type = str(row.get("media_type") or row.get("media_kind") or "").strip().casefold()
    if media_type:
        return media_type == "tv"
    if row.get("is_tv") is True:
        return True
    source_tv = getattr(resolved, "source_tv", None)
    return bool(source_tv and path_is_under_or_equal(Path(source_path), [Path(source_tv)]))


def _selected_current_series_row(
    rows: list[Any],
    detected_series: Mapping[str, str],
    pilot_keys: set[str],
) -> tuple[str, str]:
    show_root_key = str(detected_series.get("show_root_key") or "")
    if not show_root_key:
        return "", "Pilot sources did not produce a detected series root."

    matched_any = False
    for row_value in rows:
        if not isinstance(row_value, Mapping):
            continue
        row = dict(row_value)
        if not _row_is_tv(row):
            continue
        identity = _series_identity(row)
        if str(identity.get("show_root_key") or "") != show_root_key:
            continue
        matched_any = True
        source_path = str(row.get("source_path") or "").strip()
        if source_path and normalize_file_override_path(source_path) not in pilot_keys:
            return source_path, ""

    if matched_any:
        return "", "No eligible remaining current queue row was found for the detected pilot series."
    return "", "No current queue row was found for the detected pilot series; refresh Queue before applying."


def _promotion_preview_rows(preview: Mapping[str, Any], pilot_keys: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_value in preview.get("rows", []):
        if not isinstance(row_value, Mapping):
            continue
        row = dict(row_value)
        source_key = normalize_file_override_path(row.get("source_path") or "")
        if source_key in pilot_keys and str(row.get("action") or "") in {"will_update", "replace_prior_batch"}:
            row["action"] = "skipped"
            row["reason"] = "Pilot row already provided completed fallback evidence; promotion writes remaining current queue rows only."
        rows.append(row)
    return rows


def _promotion_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
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


def _promotion_batch_metadata(
    *,
    detected_series: Mapping[str, str],
    selected_source_path: str,
    pilot_paths: list[str],
    reason: str,
) -> dict[str, Any]:
    batch_id = f"remux-pilot-{uuid.uuid4().hex[:12]}"
    return {
        "origin": REMUX_PILOT_PROMOTE_BATCH_ORIGIN,
        "batch_id": batch_id,
        "batch_label": f"3-pilot remux fallback promotion: {detected_series.get('show_name') or 'TV series'}",
        "batch_scope": SERIES_BATCH_SCOPE,
        "batch_source_path": selected_source_path,
        "batch_detected_root": str(detected_series.get("show_root") or ""),
        "batch_detected_name": str(detected_series.get("show_name") or ""),
        "pilot_source_paths": list(pilot_paths),
        "reason": str(reason or "").strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _route_text(row: Mapping[str, Any]) -> str:
    route_plan = _mapping(row.get("route_plan"))
    return str(row.get("route") or route_plan.get("route") or "").strip().casefold()


def _route_reason_code(row: Mapping[str, Any]) -> str:
    route_plan = _mapping(row.get("route_plan"))
    return str(row.get("route_reason_code") or route_plan.get("route_reason_code") or route_plan.get("reason_code") or "").strip()


def _publish_state(row: Mapping[str, Any]) -> str:
    return str(row.get("publish_state") or "published").strip().casefold()


def _fallback_size_policy_triggered(value: Any, *, depth: int = 0) -> bool:
    if depth > 8:
        return False
    if isinstance(value, Mapping):
        for key in (
            "should_fallback_remux",
            "fallback_remux_triggered",
            "fallback_remux_applied",
            "fallback_remux",
            "shouldFallbackRemux",
        ):
            if value.get(key) is True:
                return True
        return any(_fallback_size_policy_triggered(child, depth=depth + 1) for child in value.values())
    if isinstance(value, list):
        return any(_fallback_size_policy_triggered(child, depth=depth + 1) for child in value)
    return False


def _error_messages_from_preview(preview: Mapping[str, Any]) -> list[str]:
    messages: list[str] = []
    for item in preview.get("errors", []):
        text = str(item or "").strip()
        if text:
            messages.append(text)
    for blocker in preview.get("blockers", []):
        if isinstance(blocker, Mapping):
            text = str(blocker.get("message") or "").strip()
        else:
            text = str(blocker or "").strip()
        if text and text not in messages:
            messages.append(text)
    return messages


def _promotion_error(
    message: str,
    errors: list[str] | None = None,
    *,
    pilot_evidence: list[dict[str, Any]] | None = None,
    detected_series: Mapping[str, Any] | None = None,
    preview: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    error_rows = [str(error) for error in (errors or [message]) if str(error).strip()]
    return {
        "ok": False,
        "command": REMUX_PILOT_PROMOTE_COMMAND,
        "data_schema": REMUX_PILOT_PROMOTE_DATA_SCHEMA,
        "severity": "error",
        "message": message,
        "errors": error_rows or [message],
        "pilot_evidence": list(pilot_evidence or []),
        "detected_series": dict(detected_series or {}),
        "counts": _mapping(preview.get("counts")) if isinstance(preview, Mapping) else {},
        "series_preview": dict(preview or {}),
        "blockers": [{"code": "blocked", "message": error} for error in (error_rows or [message])],
    }
