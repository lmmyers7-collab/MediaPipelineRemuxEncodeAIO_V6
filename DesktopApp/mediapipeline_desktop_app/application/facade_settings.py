from __future__ import annotations

from typing import Any

from ..models import ResolvedPaths
from .dto import CommandResult, SettingsWorkspaceDto
from .facade_settings_policy import (
    settings_validation_exception_result,
    settings_validation_missing_values_result,
    settings_validation_result,
    settings_validation_unavailable_result,
    settings_tool_path_evidence,
    settings_workspace_paths,
)
from .settings_risk_policy import build_current_settings_risk_summary, build_media_policy_readiness


class SettingsFacadeMixin:
    """Settings workspace and validation helpers for the application facade."""

    def get_settings_workspace(self, resolved: ResolvedPaths) -> SettingsWorkspaceDto:
        """Return a redacted, read-only settings snapshot for future shells."""
        config = dict(resolved.config_data or {})
        errors: list[str] = []
        warnings: list[str] = []
        validator = getattr(self.service, "validate_config_values", None)
        if callable(validator):
            try:
                raw_errors, raw_warnings = validator(config)
                errors.extend(str(item) for item in raw_errors)
                warnings.extend(str(item) for item in raw_warnings)
            except Exception as exc:
                warnings.append(f"Settings validation unavailable: {exc}")
        profiles: list[str] = []
        profile_lister = getattr(self.service, "list_config_profiles", None)
        if callable(profile_lister):
            try:
                profiles = [str(item) for item in profile_lister(resolved.config_path)]
            except Exception as exc:
                warnings.append(f"Config profiles unavailable: {exc}")
        return SettingsWorkspaceDto(
            app_version=self.app_version,
            config_path=str(resolved.config_path),
            workspace_root=str(resolved.workspace_root),
            app_root=str(resolved.app_root),
            paths=settings_workspace_paths(resolved, config),
            config=self._redacted_config(config),
            field_definitions=self._settings_field_definitions(),
            key_count=len(config),
            profiles=profiles,
            risk_summary=build_current_settings_risk_summary(config),
            media_policy_readiness=build_media_policy_readiness(config),
            tool_path_evidence=settings_tool_path_evidence(resolved, config),
            errors=errors,
            warnings=warnings,
        )

    def validate_settings_values(self, request: dict[str, Any]) -> CommandResult:
        values = request.get("values")
        if not isinstance(values, dict):
            return settings_validation_missing_values_result()
        validator = getattr(self.service, "validate_config_values", None)
        if not callable(validator):
            return settings_validation_unavailable_result()
        try:
            raw_errors, raw_warnings = validator(values)
        except Exception as exc:
            return settings_validation_exception_result(exc)
        return settings_validation_result(values, raw_errors, raw_warnings)

__all__ = [
    "SettingsFacadeMixin",
]
