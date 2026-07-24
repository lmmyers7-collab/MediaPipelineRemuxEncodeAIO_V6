from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.config.preset_migration import (
    legacy_config_patch_from_preset_v2,
    preset_v2_legacy_apply_unsupported_differences,
)
from mediapipeline.core.config.preset_policy import PresetV2, preset_v2_validation_issues
from mediapipeline.core.kernel.dto_commands import CommandResult


PRESET_LIBRARY_SCHEMA_VERSION = "preset_library.v1"
PRESET_LIBRARY_RECORD_SCHEMA_VERSION = "preset_library_record.v1"
PRESET_LIBRARY_APPLY_PREVIEW_SCHEMA_VERSION = "preset_library_apply_preview.v1"
PRESET_LIBRARY_IMPORT_PREVIEW_SCHEMA_VERSION = "preset_library_import_preview.v1"


def preset_library_path(resolved: Any) -> Path:
    raw = getattr(resolved, "state_root", None)
    if raw:
        state_root = Path(raw)
    else:
        app_root = getattr(resolved, "app_root", None) or getattr(resolved, "workspace_root", None) or "."
        state_root = Path(app_root) / "State"
    return state_root / "PresetLibrary" / "presets.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-").lower()
    return text or f"preset-{uuid.uuid4().hex[:8]}"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _empty_library() -> dict[str, Any]:
    return {"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "records": []}


class _PresetLibraryFormatError(ValueError):
    """Persisted preset state is unsupported and must not be rewritten."""


def _validated_library_record(
    row: object,
    *,
    index: int,
    seen_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise _PresetLibraryFormatError(f"Preset library records[{index}] must be a JSON object.")
    record = dict(row)
    if record.get("schema_version") != PRESET_LIBRARY_RECORD_SCHEMA_VERSION:
        raise _PresetLibraryFormatError(
            f"Preset library records[{index}] has an unsupported record schema_version."
        )
    preset_id = str(record.get("id") or "").strip()
    if not preset_id:
        raise _PresetLibraryFormatError(f"Preset library records[{index}].id must be non-empty.")
    identity = preset_id.casefold()
    if identity in seen_ids:
        raise _PresetLibraryFormatError(f"Preset library contains duplicate id: {preset_id}.")
    seen_ids.add(identity)
    if not str(record.get("name") or "").strip():
        raise _PresetLibraryFormatError(f"Preset library records[{index}].name must be non-empty.")
    tags = record.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise _PresetLibraryFormatError(f"Preset library records[{index}].tags must be a list of strings.")
    try:
        PresetV2.model_validate(record.get("preset_v2"))
    except Exception as exc:
        raise _PresetLibraryFormatError(
            f"Preset library records[{index}].preset_v2 does not satisfy the PresetV2 contract."
        ) from exc
    return record


def _load_library(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_library()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _PresetLibraryFormatError("Preset library is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise _PresetLibraryFormatError("Preset library root must be a JSON object.")
    if payload.get("schema_version") != PRESET_LIBRARY_SCHEMA_VERSION:
        raise _PresetLibraryFormatError("Preset library has an unsupported schema_version.")
    records = payload.get("records")
    if not isinstance(records, list):
        raise _PresetLibraryFormatError("Preset library records must be a JSON array.")
    seen_ids: set[str] = set()
    validated_records = [
        _validated_library_record(row, index=index, seen_ids=seen_ids)
        for index, row in enumerate(records)
    ]
    return {"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "records": validated_records}


def _library_recovery_data(path: Path, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": PRESET_LIBRARY_SCHEMA_VERSION,
        "path": str(path),
        "library_state": "recovery_required",
        "recovery_required": True,
        "original_bytes_preserved": path.exists(),
        "safe_next_action": (
            "Restore a known-good presets.json or repair it to the documented preset_library.v1 schema, "
            "then retry. The backend will not overwrite unsupported state."
        ),
        **fields,
    }


def _record_from_request(request: Mapping[str, Any], existing: Mapping[str, Any] | None = None) -> dict[str, Any]:
    preset = PresetV2.model_validate(request.get("preset_v2"))
    preset_json = preset.model_dump(mode="json", by_alias=True)
    now = _now()
    preset_id = _slug(request.get("id") or (existing or {}).get("id") or request.get("name") or preset.name)
    name = str(request.get("name") or preset.name).strip() or preset.name
    tags = request.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return {
        "schema_version": PRESET_LIBRARY_RECORD_SCHEMA_VERSION,
        "id": preset_id,
        "name": name,
        "description": str(request.get("description") or "").strip(),
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
        "source": str(request.get("source") or "operator").strip() or "operator",
        "created_at": str((existing or {}).get("created_at") or now),
        "updated_at": now,
        "imported_from": str(request.get("imported_from") or "").strip(),
        "preset_v2": preset_json,
    }


def _find_record(library: Mapping[str, Any], preset_id: object) -> dict[str, Any] | None:
    wanted = str(preset_id or "").strip().casefold()
    for record in library.get("records") or []:
        if isinstance(record, Mapping) and str(record.get("id") or "").casefold() == wanted:
            return dict(record)
    return None


def _record_or_inline_preset(library: Mapping[str, Any], request: Mapping[str, Any], *, key: str = "id") -> tuple[dict[str, Any], str]:
    if request.get(key):
        record = _find_record(library, request.get(key))
        if record is None:
            raise ValueError(f"Preset id was not found: {request.get(key)}")
        return record, str(record.get("id") or "")
    preset = PresetV2.model_validate(request.get("preset_v2"))
    record = _record_from_request({"name": preset.name, "preset_v2": preset.model_dump(mode="json", by_alias=True), "source": "inline"})
    return record, "inline"


def _command_result(**fields: Any) -> CommandResult:
    return CommandResult(**fields)


class PresetLibraryFacadeMixin:
    def list_preset_library(self, resolved: Any) -> CommandResult:
        path = preset_library_path(resolved)
        try:
            data = _load_library(path)
            data["path"] = str(path)
        except _PresetLibraryFormatError as exc:
            return _command_result(
                command="settings.preset_library.list",
                ok=False,
                severity="error",
                message=f"Preset library recovery is required: {exc}",
                errors=[str(exc)],
                refresh_hint="settings",
                data=_library_recovery_data(path, records=[], error=str(exc)),
            )
        except Exception as exc:
            return _command_result(
                command="settings.preset_library.list",
                ok=False,
                severity="error",
                message=f"Could not read preset library: {exc}",
                errors=[str(exc)],
                refresh_hint="settings",
                data={"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "records": []},
            )
        return _command_result(
            command="settings.preset_library.list",
            ok=True,
            message=f"Loaded {len(data['records'])} preset record(s).",
            refresh_hint="settings",
            data=data,
        )

    def validate_preset_library(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        _ = resolved
        issues = preset_v2_validation_issues(request.get("preset_v2"))
        return _command_result(
            command="settings.preset_library.validate",
            ok=not issues,
            severity="info" if not issues else "warning",
            message="PresetV2 validation passed." if not issues else f"PresetV2 validation found {len(issues)} issue(s).",
            warnings=[issue.message for issue in issues],
            refresh_hint="settings",
            data={
                "schema_version": "preset_library_validation.v1",
                "valid": not issues,
                "issues": [issue.model_dump(mode="json") for issue in issues],
            },
        )

    def save_preset_library(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        path = preset_library_path(resolved)
        try:
            library = _load_library(path)
            existing = _find_record(library, request.get("id"))
            record = _record_from_request(request, existing)
            records = [dict(row) for row in library["records"] if str(row.get("id") or "").casefold() != record["id"].casefold()]
            records.append(record)
            records.sort(key=lambda row: str(row.get("name") or row.get("id") or "").casefold())
            payload = {"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "records": records}
            _atomic_write_json(path, payload)
        except _PresetLibraryFormatError as exc:
            return _command_result(
                command="settings.preset_library.save",
                ok=False,
                severity="error",
                message=f"Preset save blocked; library recovery is required: {exc}",
                errors=[str(exc)],
                refresh_hint="settings",
                data=_library_recovery_data(path, record=None),
            )
        except Exception as exc:
            return _command_result(
                command="settings.preset_library.save",
                ok=False,
                severity="error",
                message=f"Could not save preset: {exc}",
                errors=[str(exc)],
                refresh_hint="settings",
                data={"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "record": None, "path": str(path)},
            )
        return _command_result(
            command="settings.preset_library.save",
            ok=True,
            message=f"Preset saved: {record['name']}.",
            refresh_hint="settings",
            data={"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "record": record, "path": str(path)},
        )

    def export_preset_library(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        try:
            library = _load_library(preset_library_path(resolved))
            record, _source = _record_or_inline_preset(library, request)
        except Exception as exc:
            return _command_result(
                command="settings.preset_library.export",
                ok=False,
                severity="error",
                message=f"Could not export preset: {exc}",
                errors=[str(exc)],
                refresh_hint="settings",
                data={"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "record": None},
            )
        return _command_result(
            command="settings.preset_library.export",
            ok=True,
            message=f"Preset export ready: {record['name']}.",
            refresh_hint="settings",
            data={"schema_version": PRESET_LIBRARY_SCHEMA_VERSION, "record": record},
        )

    def compare_preset_library(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        try:
            library = _load_library(preset_library_path(resolved))
            left_request = {"id": request.get("left_id"), "preset_v2": request.get("left_preset_v2")}
            right_request = {"id": request.get("right_id"), "preset_v2": request.get("right_preset_v2")}
            left, left_source = _record_or_inline_preset(library, left_request)
            right, right_source = _record_or_inline_preset(library, right_request)
            left_patch = legacy_config_patch_from_preset_v2(left["preset_v2"])
            right_patch = legacy_config_patch_from_preset_v2(right["preset_v2"])
            keys = sorted(set(left_patch) | set(right_patch), key=str.casefold)
            diff = [
                {"key": key, "left": left_patch.get(key), "right": right_patch.get(key)}
                for key in keys
                if left_patch.get(key) != right_patch.get(key)
            ]
        except Exception as exc:
            return _command_result(
                command="settings.preset_library.compare",
                ok=False,
                severity="error",
                message=f"Could not compare presets: {exc}",
                errors=[str(exc)],
                refresh_hint="settings",
                data={"schema_version": "preset_library_compare.v1", "differences": []},
            )
        return _command_result(
            command="settings.preset_library.compare",
            ok=True,
            severity="info" if not diff else "warning",
            message=f"Preset comparison ready with {len(diff)} changed key(s).",
            refresh_hint="settings",
            data={
                "schema_version": "preset_library_compare.v1",
                "left": {"id": left_source, "record": left},
                "right": {"id": right_source, "record": right},
                "differences": diff,
            },
        )

    def import_preset_library_preview(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        _ = resolved
        candidates: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, item in enumerate(request.get("records") or []):
            if not isinstance(item, Mapping):
                errors.append(f"records[{index}] must be an object")
                continue
            try:
                candidates.append(_record_from_request(item))
            except Exception as exc:
                errors.append(f"records[{index}]: {exc}")
        return _command_result(
            command="settings.preset_library.import_preview",
            ok=not errors,
            severity="info" if not errors else "warning",
            message=f"Preset import preview found {len(candidates)} candidate record(s).",
            errors=errors,
            refresh_hint="settings",
            data={
                "schema_version": PRESET_LIBRARY_IMPORT_PREVIEW_SCHEMA_VERSION,
                "candidate_records": candidates,
                "would_write_path": str(preset_library_path(resolved)),
                "writes_config": False,
            },
        )

    def preview_preset_library_apply(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        try:
            library = _load_library(preset_library_path(resolved))
            record, source = _record_or_inline_preset(library, request)
            legacy_patch = legacy_config_patch_from_preset_v2(record["preset_v2"])
            unsupported_differences = preset_v2_legacy_apply_unsupported_differences(
                record["preset_v2"],
                getattr(resolved, "config_data", None),
            )
            unsupported_paths = [str(difference["path"]) for difference in unsupported_differences]
            settings_preview = None
            preview = getattr(self, "preview_settings_patch", None)
            if callable(preview):
                settings_preview = preview(resolved, {"changes": legacy_patch, "remove_keys": []}).to_mapping()
        except Exception as exc:
            return _command_result(
                command="settings.preset_library.apply_preview",
                ok=False,
                severity="error",
                message=f"Could not preview preset apply: {exc}",
                errors=[str(exc)],
                refresh_hint="settings",
                data={"schema_version": PRESET_LIBRARY_APPLY_PREVIEW_SCHEMA_VERSION, "writes_config": False, "legacy_patch": {}},
            )
        return _command_result(
            command="settings.preset_library.apply_preview",
            ok=True,
            severity="warning",
            message=(
                f"Preset apply is blocked because {len(unsupported_differences)} reviewed policy field(s) "
                "cannot be represented by the current settings adapter."
                if unsupported_differences
                else f"Preset apply preview ready: {record['name']}."
            ),
            warnings=(
                [
                    "Confirmed apply will not write settings until every differing preset policy field is supported: "
                    + ", ".join(unsupported_paths)
                ]
                if unsupported_differences
                else []
            ),
            refresh_hint="settings",
            data={
                "schema_version": PRESET_LIBRARY_APPLY_PREVIEW_SCHEMA_VERSION,
                "preset_id": source,
                "record": record,
                "legacy_patch": legacy_patch,
                "apply_supported": not unsupported_differences,
                "unsupported_paths": unsupported_paths,
                "unsupported_differences": unsupported_differences,
                "writes_config": False,
                "affects_future_launches_only": True,
                "settings_preview": settings_preview,
            },
        )

    def apply_preset_library(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        if request.get("confirm_apply") is not True:
            return _command_result(
                command="settings.preset_library.apply",
                ok=False,
                severity="warning",
                message="Preset apply requires explicit confirmation.",
                warnings=["confirm_apply must be true."],
                refresh_hint="settings",
                data={"schema_version": PRESET_LIBRARY_APPLY_PREVIEW_SCHEMA_VERSION, "writes_config": False, "legacy_patch": {}},
            )
        preview = self.preview_preset_library_apply(resolved, request)
        if not preview.ok:
            return preview
        unsupported_differences = list(preview.data.get("unsupported_differences") or [])
        if unsupported_differences:
            unsupported_paths = [str(item.get("path") or "") for item in unsupported_differences]
            return _command_result(
                command="settings.preset_library.apply",
                ok=False,
                severity="error",
                message=(
                    f"Preset apply blocked before settings save: {len(unsupported_differences)} reviewed policy "
                    "field(s) are not supported by the current settings adapter."
                ),
                errors=["Unsupported preset policy fields: " + ", ".join(unsupported_paths)],
                refresh_hint="settings",
                data=preview.data,
            )
        save = getattr(self, "save_settings_patch", None)
        if not callable(save):
            return _command_result(
                command="settings.preset_library.apply",
                ok=False,
                severity="error",
                message="Settings save service is not available for preset apply.",
                errors=["save_settings_patch is not available."],
                refresh_hint="settings",
                data=preview.data,
            )
        save_request = {"changes": dict(preview.data.get("legacy_patch") or {}), "remove_keys": []}
        confirmation_builder = getattr(self, "settings_patch_request_with_review_confirmation", None)
        if callable(confirmation_builder):
            save_request = confirmation_builder(resolved, save_request)
        result = save(resolved, {**save_request, "confirm_save": True})
        data = dict(result.data or {})
        data["preset_library_apply_preview"] = preview.data
        data["affects_future_launches_only"] = True
        return _command_result(
            command="settings.preset_library.apply",
            ok=bool(result.ok),
            severity=str(result.severity),
            message=str(result.message),
            warnings=list(result.warnings),
            errors=list(result.errors),
            job_id=str(result.job_id),
            refresh_hint=str(result.refresh_hint or "settings"),
            log_paths=dict(result.log_paths),
            data=data,
        )


__all__ = [
    "PRESET_LIBRARY_SCHEMA_VERSION",
    "PresetLibraryFacadeMixin",
    "preset_library_path",
]
