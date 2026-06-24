from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.desktop.api.path_dialogs import select_windows_paths_with_dialog
from mediapipeline.desktop.application.dto import CommandResult

from .command_results import (
    resolved_paths_unavailable_payload,
    settings_reload_exception_payload,
    settings_reload_missing_resolved_payload,
    settings_reload_success_payload,
    settings_reload_unavailable_payload,
    settings_save_reload_failure_payload,
    settings_save_reload_success_payload,
)


_SETTINGS_PATH_BROWSE_KEYS: dict[str, dict[str, str]] = {
    "SourceMovies": {
        "label": "Movies source",
        "target_kind": "source_root",
    },
    "SourceTV": {
        "label": "TV source",
        "target_kind": "source_root",
    },
    "Outsource": {
        "label": "Final output",
        "target_kind": "output_root",
    },
    "LocalBase": {
        "label": "Scratch / LocalBase",
        "target_kind": "scratch_root",
    },
    "FinalLibraryPromotionRuleSourceRoot": {
        "label": "Final library promotion source root",
        "target_kind": "promotion_source_root",
    },
    "FinalLibraryPromotionRuleDestinationRoot": {
        "label": "Final library promotion destination root",
        "target_kind": "promotion_destination_root",
    },
}


def _validate_settings_browse_path(setting_key: str, raw_path: str) -> dict[str, Any]:
    info = _SETTINGS_PATH_BROWSE_KEYS.get(setting_key, {})
    label = info.get("label") or setting_key
    target_kind = info.get("target_kind") or "folder"
    path_text = str(raw_path or "").strip()
    validation: dict[str, Any] = {
        "schema_version": "desktop_settings_path_validation.v1",
        "setting_key": setting_key,
        "label": label,
        "target_kind": target_kind,
        "path": path_text,
        "exists": False,
        "is_dir": False,
        "is_absolute": False,
        "status_state": "blocked",
        "message": "No folder was selected.",
    }
    if not path_text:
        return validation
    try:
        candidate = Path(path_text)
        validation["is_absolute"] = candidate.is_absolute()
        validation["exists"] = candidate.exists()
        validation["is_dir"] = candidate.is_dir()
    except OSError as exc:
        validation["message"] = f"Selected {label} path could not be checked: {exc}"
        return validation

    if not validation["is_absolute"]:
        validation["status_state"] = "blocked"
        validation["message"] = f"Selected {label} path is not absolute. Choose a full folder path before Preview Patch or Save Patch."
    elif not validation["exists"]:
        validation["status_state"] = "blocked"
        validation["message"] = f"Selected {label} folder does not exist. Create or mount it before Preview Patch or Save Patch."
    elif not validation["is_dir"]:
        validation["status_state"] = "blocked"
        validation["message"] = f"Selected {label} path exists but is not a folder."
    else:
        validation["status_state"] = "ready"
        validation["message"] = f"Selected {label} folder exists. Merge File Safety Patch, then Preview Patch before saving."
    return validation


class LocalApiSettingsCommandPayloadMixin:
    def _settings_preset_library_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.list", "settings")
        return self.facade.list_preset_library(resolved).to_mapping()

    def _settings_validate_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.validate_settings_values(request).to_mapping()

    def _settings_preset_library_validate_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.validate", "settings")
        return self.facade.validate_preset_library(resolved, request).to_mapping()

    def _settings_preset_library_compare_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.compare", "settings")
        return self.facade.compare_preset_library(resolved, request).to_mapping()

    def _settings_preset_library_import_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.import_preview", "settings")
        return self.facade.import_preset_library_preview(resolved, request).to_mapping()

    def _settings_preset_library_save_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.save", "settings")
        return self.facade.save_preset_library(resolved, request).to_mapping()

    def _settings_preset_library_export_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.export", "settings")
        return self.facade.export_preset_library(resolved, request).to_mapping()

    def _settings_preset_library_apply_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.apply_preview", "settings")
        return self.facade.preview_preset_library_apply(resolved, request).to_mapping()

    def _settings_preset_library_apply_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preset_library.apply", "settings")
        return self.facade.apply_preset_library(resolved, request).to_mapping()

    def _settings_browse_path_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        setting_key = str(request.get("setting_key") or "").strip()
        info = _SETTINGS_PATH_BROWSE_KEYS.get(setting_key)
        if info is None:
            return CommandResult(
                command="settings.browse_path",
                ok=False,
                severity="error",
                message="Settings folder browse only supports allowlisted source, output, scratch, and final library path keys.",
                errors=["unsupported_setting_key"],
                data={
                    "schema_version": "desktop_settings_path_browse.v1",
                    "setting_key": setting_key,
                    "allowed_setting_keys": sorted(_SETTINGS_PATH_BROWSE_KEYS),
                    "writes_config": False,
                    "stages_only": True,
                },
            ).to_mapping()

        requested_mode = str(request.get("selection_mode") or "folder").strip().lower()
        if requested_mode not in {"", "folder"}:
            return CommandResult(
                command="settings.browse_path",
                ok=False,
                severity="error",
                message="Settings path browse only supports selecting folders.",
                errors=["unsupported_selection_mode"],
                data={
                    "schema_version": "desktop_settings_path_browse.v1",
                    "setting_key": setting_key,
                    "allowed_selection_modes": ["folder"],
                    "writes_config": False,
                    "stages_only": True,
                },
            ).to_mapping()

        initial_path = str(request.get("initial_path") or "")
        label = info["label"]
        picker = getattr(self, "_settings_path_picker", None)
        picker_kwargs = {
            "selection_mode": "folder",
            "initial_path": initial_path,
            "dialog_description": f"Select the {label} folder for Settings staging",
        }
        if callable(picker):
            result = picker(setting_key=setting_key, **picker_kwargs)
        else:
            result = select_windows_paths_with_dialog(**picker_kwargs)
        paths = [str(path).strip() for path in result.get("paths", []) if str(path).strip()]
        selected_path = paths[0] if paths else ""
        canceled = bool(result.get("canceled", False))
        picker_ok = bool(result.get("ok", False))
        validation = _validate_settings_browse_path(setting_key, selected_path)
        validation_ready = validation.get("status_state") == "ready"
        ok = picker_ok and (canceled or validation_ready)
        if canceled:
            message = "Windows folder browser canceled. No Settings field was changed."
            severity = "info"
        elif picker_ok and validation_ready:
            message = f"Windows folder browser selected {label}: {selected_path}"
            severity = "info"
        elif picker_ok:
            message = str(validation.get("message") or "Selected Settings folder did not pass backend validation.")
            severity = "warning"
        else:
            message = str(result.get("message") or "Windows folder browser failed.")
            severity = "error"
        return CommandResult(
            command="settings.browse_path",
            ok=ok,
            severity=severity,
            message=message,
            errors=[str(error) for error in result.get("errors", [])],
            data={
                "schema_version": "desktop_settings_path_browse.v1",
                "setting_key": setting_key,
                "label": label,
                "target_kind": info["target_kind"],
                "paths": paths,
                "selected_path": selected_path,
                "selection_mode": "folder",
                "canceled": canceled,
                "path_count": len(paths),
                "source": "windows_file_browser",
                "validation": validation,
                "allowed_setting_keys": sorted(_SETTINGS_PATH_BROWSE_KEYS),
                "writes_config": False,
                "stages_only": True,
            },
        ).to_mapping()

    def _settings_preview_patch_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preview_patch", "settings")
        return self.facade.preview_settings_patch(resolved, request).to_mapping()

    def _settings_pipeline_plan_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.pipeline_plan_preview", "settings")
        return self.facade.preview_settings_pipeline_plan(resolved, request).to_mapping()

    def _settings_save_patch_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.save_patch", "settings")
        payload = self.facade.save_settings_patch(resolved, request).to_mapping()
        if payload.get("ok") and self.resolved_reload is not None:
            try:
                reloaded = self.resolved_reload()
                payload = settings_save_reload_success_payload(payload, reloaded)
            except Exception as exc:
                self.logger.exception("local API settings reload after save failed")
                payload = settings_save_reload_failure_payload(payload, exc)
        elif payload.get("ok"):
            data = dict(payload.get("data") or {})
            data["reloaded"] = False
            warnings = list(payload.get("warnings") or [])
            warnings.append(
                "Settings were written to disk but the backend reload function is not configured. "
                "Use Reload From Disk to apply."
            )
            payload = {**payload, "data": data, "warnings": warnings}
        return payload

    def _settings_import_psd1_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        _ = request
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.import_psd1_preview", "settings")
        return self.facade.preview_settings_psd1_import(resolved).to_mapping()

    def _settings_import_psd1_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.import_psd1", "settings")
        payload = self.facade.import_settings_psd1(resolved, request).to_mapping()
        if payload.get("ok") and self.resolved_reload is not None:
            try:
                reloaded = self.resolved_reload()
                payload = settings_save_reload_success_payload(payload, reloaded)
            except Exception as exc:
                self.logger.exception("local API settings PSD1 import reload failed")
                payload = settings_save_reload_failure_payload(payload, exc)
        return payload

    def _settings_wizard_validate_paths_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.validate_settings_wizard_paths(request).to_mapping()

    def _settings_wizard_validate_tools_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.wizard.validate_tools", "settings")
        return self.facade.validate_settings_wizard_tools(resolved, request).to_mapping()

    def _settings_wizard_probe_hardware_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.wizard.probe_hardware", "settings")
        return self.facade.probe_settings_wizard_hardware(resolved, request).to_mapping()

    def _settings_wizard_validate_workers_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.validate_settings_wizard_workers(request).to_mapping()

    def _settings_wizard_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.wizard.preview", "settings")
        return self.facade.preview_settings_wizard(resolved, request).to_mapping()

    def _settings_wizard_save_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.wizard.save", "settings")
        payload = self.facade.save_settings_wizard(resolved, request).to_mapping()
        if payload.get("ok") and self.resolved_reload is not None:
            try:
                reloaded = self.resolved_reload()
                payload = settings_save_reload_success_payload(payload, reloaded)
            except Exception as exc:
                self.logger.exception("local API settings wizard reload after save failed")
                payload = settings_save_reload_failure_payload(payload, exc)
        elif payload.get("ok"):
            data = dict(payload.get("data") or {})
            data["reloaded"] = False
            warnings = list(payload.get("warnings") or [])
            warnings.append(
                "Settings were written to disk but the backend reload function is not configured. "
                "Use Reload From Disk to apply."
            )
            payload = {**payload, "data": data, "warnings": warnings}
        return payload

    def _settings_reload_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        _ = request
        if self.resolved_reload is None:
            return settings_reload_unavailable_payload()
        try:
            resolved = self.resolved_reload()
        except Exception as exc:
            self.logger.exception("local API settings reload failed")
            return settings_reload_exception_payload(exc)
        if resolved is None:
            return settings_reload_missing_resolved_payload()
        return settings_reload_success_payload(resolved)
