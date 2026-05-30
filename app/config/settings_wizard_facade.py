"""Settings setup wizard facade adapter."""

from __future__ import annotations

from typing import Any

from app.config.settings_wizard import (
    preview_settings_wizard,
    probe_ffmpeg_hardware,
    save_settings_wizard,
    settings_wizard_defaults,
    settings_wizard_status,
    validate_ffmpeg_tools,
    validate_wizard_paths,
    validate_worker_settings,
)
from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.models import ResolvedPaths


class SettingsWizardFacadeMixin:
    """Guided setup over the existing settings patch/save boundary."""

    def get_settings_wizard_status(self, resolved: ResolvedPaths) -> dict[str, Any]:
        return settings_wizard_status(resolved, self.service)

    def get_settings_wizard_defaults(self, resolved: ResolvedPaths) -> dict[str, Any]:
        return settings_wizard_defaults(resolved, self.service)

    def validate_settings_wizard_paths(self, request: dict[str, Any]) -> CommandResult:
        data = validate_wizard_paths(dict(request.get("wizard") or request))
        return CommandResult(
            command="settings.wizard.validate_paths",
            ok=bool(data.get("ok")),
            message="Settings Wizard path validation completed." if data.get("ok") else "Settings Wizard path validation found blockers.",
            severity="info" if data.get("ok") else "error",
            warnings=[str(item) for item in data.get("warnings", [])],
            errors=[str(item) for item in data.get("errors", [])],
            refresh_hint="settings",
            data=data,
        )

    def validate_settings_wizard_tools(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        data = validate_ffmpeg_tools(resolved, request)
        return CommandResult(
            command="settings.wizard.validate_tools",
            ok=bool(data.get("ok")),
            message="Settings Wizard tool validation completed.",
            severity="info" if data.get("ok") else "error",
            warnings=[str(item) for item in data.get("warnings", [])],
            errors=[str(item) for item in data.get("errors", [])],
            refresh_hint="settings",
            data=data,
        )

    def probe_settings_wizard_hardware(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        data = probe_ffmpeg_hardware(resolved, request)
        return CommandResult(
            command="settings.wizard.probe_hardware",
            ok=bool(data.get("ok")),
            message="Settings Wizard hardware probe completed.",
            severity="info" if data.get("ok") else "warning",
            warnings=[str(item) for item in data.get("warnings", [])],
            errors=[str(item) for item in data.get("errors", [])],
            refresh_hint="settings",
            data=data,
        )

    def validate_settings_wizard_workers(self, request: dict[str, Any]) -> CommandResult:
        wizard = dict(request.get("wizard") or request)
        data = validate_worker_settings(dict(wizard.get("workers") or {}))
        return CommandResult(
            command="settings.wizard.validate_workers",
            ok=bool(data.get("ok")),
            message="Settings Wizard worker validation completed." if data.get("ok") else "Settings Wizard worker validation found blockers.",
            severity="info" if data.get("ok") else "error",
            warnings=[str(item) for item in data.get("warnings", [])],
            errors=[str(item) for item in data.get("errors", [])],
            refresh_hint="settings",
            data=data,
        )

    def preview_settings_wizard(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        return preview_settings_wizard(self, resolved, request)

    def save_settings_wizard(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        return save_settings_wizard(self, resolved, request)


__all__ = ["SettingsWizardFacadeMixin"]
