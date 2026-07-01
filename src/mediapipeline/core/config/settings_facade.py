"""Settings workspace and validation facade adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from mediapipeline.core.config.library_profiles import (
    library_compatibility_presets,
    library_profile_state_from_config,
)
from mediapipeline.core.config.identity import config_identity_block_reasons
from mediapipeline.core.config.settings_policy import (
    settings_encoder_capability_report,
    settings_tool_path_evidence,
    settings_validation_exception_result,
    settings_validation_missing_values_result,
    settings_validation_result,
    settings_validation_unavailable_result,
    settings_workspace_paths,
)
from mediapipeline.core.processes.path_evidence import configured_path_health, path_health_warning_lines
from mediapipeline.core.config.settings_risk_policy import (
    build_current_settings_risk_summary,
    build_media_policy_readiness,
    build_settings_policy_impact,
)
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.config.profiles import config_profile_path, config_profiles_dir

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult
    from mediapipeline.core.kernel.dto_workspaces import SettingsWorkspaceDto


def _settings_workspace_dto(**fields: Any) -> "SettingsWorkspaceDto":
    from mediapipeline.core.kernel.dto_workspaces import SettingsWorkspaceDto

    return SettingsWorkspaceDto(**fields)


class SettingsFacadeMixin:
    """Settings workspace and validation helpers for the application facade."""

    def get_settings_workspace(self, resolved: ResolvedPaths) -> SettingsWorkspaceDto:
        """Return a redacted, read-only settings snapshot for future shells."""
        config = dict(resolved.config_data or {})
        config_identity = dict(getattr(resolved, "config_identity", {}) or {})
        errors: list[str] = []
        warnings: list[str] = []
        block_reasons = config_identity_block_reasons(config_identity)
        if block_reasons:
            errors.append("Active config is not a verified operator config.")
            errors.extend(block_reasons)
        if str(config_identity.get("snapshot_error") or "").strip():
            warnings.append(f"Last-known-good config snapshot unavailable: {config_identity['snapshot_error']}")
        validator = getattr(self.service, "validate_config_values", None)
        if callable(validator) and config:
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
        risk_summary = build_current_settings_risk_summary(config)
        media_policy_readiness = build_media_policy_readiness(config)
        library_profile_state: list[dict[str, Any]] = []
        try:
            library_profile_state = library_profile_state_from_config(config)
        except Exception as exc:
            warnings.append(f"Library profile inheritance evidence unavailable: {exc}")
        tool_path_evidence = settings_tool_path_evidence(resolved, config)
        path_health = configured_path_health(resolved)
        warnings.extend(path_health_warning_lines(path_health))
        return _settings_workspace_dto(
            app_version=self.app_version,
            config_path=str(resolved.config_path),
            workspace_root=str(resolved.workspace_root),
            app_root=str(resolved.app_root),
            paths=settings_workspace_paths(resolved, config),
            config_identity=config_identity,
            config=self._redacted_config(config),
            field_definitions=self._settings_field_definitions(),
            library_profile_state=library_profile_state,
            library_compatibility_presets=library_compatibility_presets(),
            key_count=len(config),
            profiles=profiles,
            profile_summary=self._settings_profile_summary(resolved, config, profiles),
            risk_summary=risk_summary,
            media_policy_readiness=media_policy_readiness,
            policy_impact=build_settings_policy_impact(
                config,
                risk_summary=risk_summary,
                media_policy_readiness=media_policy_readiness,
                errors=errors,
                warnings=warnings,
            ),
            tool_path_evidence=tool_path_evidence,
            encoder_capability_report=settings_encoder_capability_report(resolved),
            path_health=path_health,
            persistence_authority=str(getattr(resolved, "persistence_authority", "") or "psd1_compatibility"),
            settings_store_status=dict(getattr(resolved, "settings_store_status", {}) or {}),
            projection_status=dict(getattr(resolved, "projection_status", {}) or {}),
            migration_journal=[str(item) for item in getattr(resolved, "migration_journal", []) or []],
            legacy_extras_count=int(getattr(resolved, "legacy_extras_count", 0) or 0),
            psd1_drift_status=str(getattr(resolved, "psd1_drift_status", "") or "unknown"),
            errors=errors,
            warnings=warnings,
        )

    def preview_settings_psd1_import(self, resolved: ResolvedPaths) -> CommandResult:
        importer = getattr(self.service, "import_psd1_settings_preview", None)
        if not callable(importer):
            from mediapipeline.core.kernel.dto_commands import CommandResult

            return CommandResult(
                command="settings.import_psd1_preview",
                ok=False,
                severity="error",
                message="Settings PSD1 import preview is unavailable in this service.",
                errors=["settings_store_import_unavailable"],
                data={"writes_config": False, "writes_store": False},
            )
        try:
            data = importer(resolved)
        except Exception as exc:
            from mediapipeline.core.kernel.dto_commands import CommandResult

            return CommandResult(
                command="settings.import_psd1_preview",
                ok=False,
                severity="error",
                message=f"Settings PSD1 import preview failed: {exc}",
                errors=[str(exc)],
                data={"writes_config": False, "writes_store": False},
            )
        from mediapipeline.core.kernel.dto_commands import CommandResult

        errors = [str(item) for item in data.get("errors") or []]
        warnings = [str(item) for item in data.get("warnings") or []]
        return CommandResult(
            command="settings.import_psd1_preview",
            ok=not errors,
            severity="error" if errors else "warning" if warnings else "info",
            message="Settings PSD1 import preview is ready." if not errors else "Settings PSD1 import preview found blocking errors.",
            errors=errors,
            warnings=warnings,
            data=data,
        )

    def import_settings_psd1(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        from mediapipeline.core.kernel.dto_commands import CommandResult

        if request.get("confirm_import") is not True:
            return CommandResult(
                command="settings.import_psd1",
                ok=False,
                severity="warning",
                message="Settings PSD1 import requires explicit confirmation.",
                warnings=["confirm_import must be true."],
                data={"writes_config": False, "writes_store": False},
            )
        importer = getattr(self.service, "import_psd1_settings", None)
        if not callable(importer):
            return CommandResult(
                command="settings.import_psd1",
                ok=False,
                severity="error",
                message="Settings PSD1 import is unavailable in this service.",
                errors=["settings_store_import_unavailable"],
                data={"writes_config": False, "writes_store": False},
            )
        try:
            data = importer(resolved)
        except Exception as exc:
            return CommandResult(
                command="settings.import_psd1",
                ok=False,
                severity="error",
                message=f"Settings PSD1 import failed: {exc}",
                errors=[str(exc)],
                data={"writes_config": False, "writes_store": False},
            )
        return CommandResult(
            command="settings.import_psd1",
            ok=True,
            severity="info",
            message="Settings PSD1 imported into JSON authority.",
            data=data,
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

    def _settings_profile_summary(
        self,
        resolved: ResolvedPaths,
        config: dict[str, Any],
        profiles: list[str],
    ) -> dict[str, Any]:
        profiles_dir = config_profiles_dir(resolved.config_path)
        summary: dict[str, Any] = {
            "schema_version": "desktop_settings_profile_summary.v1",
            "read_only": True,
            "active_config_path": str(resolved.config_path),
            "active_config_exists": resolved.config_path.exists(),
            "active_config_modified_utc": _path_modified_utc(resolved.config_path),
            "profiles_dir": str(profiles_dir),
            "profile_count": len(profiles),
            "profiles": profiles,
            "default_profile_name": "Default",
            "default_profile_path": "",
            "default_profile_exists": False,
            "default_profile_modified_utc": "",
            "default_profile_status": "unavailable",
            "default_profile_status_state": "unknown",
            "operator_status": "Default profile unavailable",
            "mismatch_count": 0,
            "mismatch_keys": [],
            "mismatch_keys_truncated": False,
            "webview_profile_operations": {
                "save_default_profile": False,
                "load_profile": False,
                "reason": "Profile save/load routes are not exposed by the Local API in this build.",
            },
            "summary_lines": [],
        }
        try:
            _, default_profile_path = config_profile_path(resolved.config_path, "Default")
        except Exception as exc:
            summary["operator_status"] = "Default profile path blocked"
            summary["default_profile_status"] = "path_error"
            summary["default_profile_status_state"] = "blocked"
            summary["summary_lines"] = [
                f"Profiles available: {_format_profiles(profiles)}.",
                f"Active config: {resolved.config_path}",
                f"Default profile path could not be resolved: {exc}",
                "WebView profile operations: read-only; profile save/load controls are not exposed by the Local API in this build.",
            ]
            return summary

        summary["default_profile_path"] = str(default_profile_path)
        summary["default_profile_exists"] = default_profile_path.exists()
        summary["default_profile_modified_utc"] = _path_modified_utc(default_profile_path)
        if not default_profile_path.exists():
            summary["default_profile_status"] = "missing"
            summary["default_profile_status_state"] = "empty"
            summary["operator_status"] = "Default profile missing"
            summary["summary_lines"] = [
                f"Profiles available: {_format_profiles(profiles)}.",
                f"Active config: {resolved.config_path}",
                f"Default profile: {default_profile_path}",
                "Default profile status: missing. Use a backend-owned profile save flow before relying on it for recovery.",
                "WebView profile operations: read-only; profile save/load controls are not exposed by the Local API in this build.",
            ]
            return summary

        loader = getattr(self.service, "load_config_data", None)
        if not callable(loader):
            summary["default_profile_status"] = "compare_unavailable"
            summary["default_profile_status_state"] = "unknown"
            summary["operator_status"] = "Default profile exists"
            summary["summary_lines"] = [
                f"Profiles available: {_format_profiles(profiles)}.",
                f"Active config: {resolved.config_path}",
                f"Default profile: {default_profile_path}",
                f"Default profile modified: {summary['default_profile_modified_utc'] or 'unknown'}",
                "Default profile status: exists, but this service cannot compare it with current settings.",
                "WebView profile operations: read-only; profile save/load controls are not exposed by the Local API in this build.",
            ]
            return summary

        try:
            profile_config = dict(loader(default_profile_path, resolved.powershell_host) or {})
            mismatch_keys = _settings_profile_mismatch_keys(config, profile_config)
        except Exception as exc:
            summary["default_profile_status"] = "compare_failed"
            summary["default_profile_status_state"] = "warning"
            summary["operator_status"] = "Default profile comparison failed"
            summary["summary_lines"] = [
                f"Profiles available: {_format_profiles(profiles)}.",
                f"Active config: {resolved.config_path}",
                f"Default profile: {default_profile_path}",
                f"Default profile modified: {summary['default_profile_modified_utc'] or 'unknown'}",
                f"Default profile status: comparison failed: {exc}",
                "WebView profile operations: read-only; profile save/load controls are not exposed by the Local API in this build.",
            ]
            return summary

        mismatch_preview_limit = 24
        summary["mismatch_count"] = len(mismatch_keys)
        summary["mismatch_keys"] = mismatch_keys[:mismatch_preview_limit]
        summary["mismatch_keys_truncated"] = len(mismatch_keys) > mismatch_preview_limit
        if mismatch_keys:
            key_preview = ", ".join(mismatch_keys[:8])
            if len(mismatch_keys) > 8:
                key_preview += f", and {len(mismatch_keys) - 8} more"
            summary["default_profile_status"] = "differs_from_current"
            summary["default_profile_status_state"] = "warning"
            summary["operator_status"] = "Default profile differs from current settings"
            summary["summary_lines"] = [
                f"Profiles available: {_format_profiles(profiles)}.",
                f"Active config: {resolved.config_path}",
                f"Default profile: {default_profile_path}",
                f"Active config modified: {summary['active_config_modified_utc'] or 'unknown'}",
                f"Default profile modified: {summary['default_profile_modified_utc'] or 'unknown'}",
                f"Default profile status: differs from current settings on {len(mismatch_keys)} key(s): {key_preview}.",
                "WebView profile operations: read-only; profile save/load controls are not exposed by the Local API in this build.",
            ]
            return summary

        summary["default_profile_status"] = "matches_current"
        summary["default_profile_status_state"] = "match"
        summary["operator_status"] = "Default profile matches current settings"
        summary["summary_lines"] = [
            f"Profiles available: {_format_profiles(profiles)}.",
            f"Active config: {resolved.config_path}",
            f"Default profile: {default_profile_path}",
            f"Active config modified: {summary['active_config_modified_utc'] or 'unknown'}",
            f"Default profile modified: {summary['default_profile_modified_utc'] or 'unknown'}",
            "Default profile status: matches current settings.",
            "WebView profile operations: read-only; profile save/load controls are not exposed by the Local API in this build.",
        ]
        return summary


def _path_modified_utc(path: Any) -> str:
    try:
        modified = path.stat().st_mtime
    except (AttributeError, OSError):
        return ""
    return datetime.fromtimestamp(modified, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_profiles(profiles: list[str]) -> str:
    if not profiles:
        return "none"
    preview = ", ".join(profiles[:8])
    if len(profiles) > 8:
        preview += f", and {len(profiles) - 8} more"
    return f"{len(profiles)} ({preview})"


def _settings_profile_mismatch_keys(active_config: dict[str, Any], profile_config: dict[str, Any]) -> list[str]:
    sentinel = object()
    mismatch_keys: list[str] = []
    for key in sorted({str(item) for item in active_config.keys()} | {str(item) for item in profile_config.keys()}):
        active_value = active_config.get(key, sentinel)
        profile_value = profile_config.get(key, sentinel)
        if active_value is sentinel or profile_value is sentinel:
            mismatch_keys.append(key)
            continue
        if _settings_profile_compare_value(active_value) != _settings_profile_compare_value(profile_value):
            mismatch_keys.append(key)
    return mismatch_keys


def _settings_profile_compare_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _settings_profile_compare_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_settings_profile_compare_value(item) for item in value]
    if isinstance(value, str):
        return value.replace("\\", "/")
    return value

__all__ = [
    "SettingsFacadeMixin",
]
