"""Settings patch preview/save facade adapter with pipeline-plan preview."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from mediapipeline.core.config.rollout import planner_comparison_from_decision_snapshot, resolve_planner_rollout_config
from mediapipeline.core.config.settings_patch_policy import (
    settings_patch_preview_result,
    settings_save_busy_result,
    settings_save_config_blocked_result,
    settings_save_confirmation_required_result,
    settings_save_exception_result,
    settings_save_no_changes_result,
    settings_save_service_unavailable_result,
    settings_save_success_result,
    settings_save_validation_error_result,
)
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message
from mediapipeline.contracts.source_media import SourceMediaInfo
from mediapipeline.core.orchestration.planner import build_pipeline_plan_from_preset
from mediapipeline.desktop.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult


_PIPELINE_PLAN_PREVIEW_AUTHORITY = "python_preview_legacy_execution_still_authoritative"
_PIPELINE_PLAN_PREVIEW_WARNING = (
    "Settings PipelinePlan preview is dry-run only; production execution still uses the legacy PowerShell path until cutover."
)


class SettingsPatchFacadeMixin:
    """Settings patch preview and save command adapters."""

    if TYPE_CHECKING:
        service: Any

        def _settings_patch_candidate(
            self,
            resolved: ResolvedPaths,
            request: dict[str, Any],
            *,
            command: str,
        ) -> dict[str, Any]: ...

    def preview_settings_patch(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Preview explicit settings changes without writing PSD1 config."""
        patch = self._settings_patch_candidate(resolved, request, command="settings.preview_patch")
        if patch["fatal_result"] is not None:
            return patch["fatal_result"]
        return settings_patch_preview_result(resolved, patch)

    def preview_settings_pipeline_plan(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Preview the Python planner result from strict source facts without saving settings."""
        from mediapipeline.desktop.application.dto_commands import CommandResult

        try:
            source = SourceMediaInfo.model_validate(request.get("source_media"))
        except ValidationError as exc:
            return CommandResult(
                command="settings.pipeline_plan_preview",
                ok=False,
                severity="error",
                message="Settings PipelinePlan preview requires a strict source_media.v1 SourceMediaInfo object.",
                errors=[str(error.get("msg") or error) for error in exc.errors()],
                data={
                    "schema_version": "pipeline_plan_preview_error.v1",
                    "dry_run_only": True,
                    "can_execute": False,
                    "authority": _PIPELINE_PLAN_PREVIEW_AUTHORITY,
                    "writes_config": False,
                    "mutates_media": False,
                },
            )

        patch_request = dict(request)
        patch_request.setdefault("changes", {})
        patch_request.setdefault("remove_keys", [])
        patch = self._settings_patch_candidate(resolved, patch_request, command="settings.pipeline_plan_preview")
        if patch["fatal_result"] is not None:
            return patch["fatal_result"]
        warnings = list(patch["warnings"])
        if patch["errors"]:
            return CommandResult(
                command="settings.pipeline_plan_preview",
                ok=False,
                severity="error",
                message="Settings PipelinePlan preview was blocked by settings patch validation.",
                warnings=warnings,
                errors=list(patch["errors"]),
                data={
                    "schema_version": "pipeline_plan_preview_error.v1",
                    "dry_run_only": True,
                    "can_execute": False,
                    "authority": _PIPELINE_PLAN_PREVIEW_AUTHORITY,
                    "writes_config": False,
                    "mutates_media": False,
                    "changed_keys": list(patch["changed_keys"]),
                    "removed_keys": list(patch["removed_keys"]),
                    "risk_summary": patch["risk_summary"],
                },
            )

        try:
            plan = build_pipeline_plan_from_preset(source, patch["merged"])
        except ValidationError as exc:
            return CommandResult(
                command="settings.pipeline_plan_preview",
                ok=False,
                severity="error",
                message="Settings PipelinePlan preview was blocked by planner validation.",
                warnings=warnings,
                errors=[str(error.get("msg") or error) for error in exc.errors()],
                data={
                    "schema_version": "pipeline_plan_preview_error.v1",
                    "dry_run_only": True,
                    "can_execute": False,
                    "authority": _PIPELINE_PLAN_PREVIEW_AUTHORITY,
                    "writes_config": False,
                    "mutates_media": False,
                    "changed_keys": list(patch["changed_keys"]),
                    "removed_keys": list(patch["removed_keys"]),
                    "risk_summary": patch["risk_summary"],
                },
            )
        data = plan.model_dump(mode="json", by_alias=True)
        rollout_state = resolve_planner_rollout_config(patch["merged"])
        planner_comparison = planner_comparison_from_decision_snapshot(
            data.get("decisionSnapshot", {}),
            rollout_state=rollout_state,
        )
        data.setdefault("warnings", [])
        if _PIPELINE_PLAN_PREVIEW_WARNING not in data["warnings"]:
            data["warnings"].append(_PIPELINE_PLAN_PREVIEW_WARNING)
        for warning in rollout_state.warnings:
            if warning not in data["warnings"]:
                data["warnings"].append(warning)
        data.setdefault("effectivePresetSnapshot", {})
        data["effectivePresetSnapshot"]["rollout"] = rollout_state.model_dump(mode="json", by_alias=True)
        data["effectivePresetSnapshot"]["plannerComparison"] = planner_comparison.model_dump(mode="json", by_alias=True)
        data["effectivePresetSnapshot"]["settingsPreview"] = {
            "dryRunOnly": True,
            "canExecute": False,
            "authority": _PIPELINE_PLAN_PREVIEW_AUTHORITY,
            "writesConfig": False,
            "mutatesMedia": False,
            "changedKeys": list(patch["changed_keys"]),
            "removedKeys": list(patch["removed_keys"]),
            "riskSummary": patch["risk_summary"],
        }
        warnings.append(_PIPELINE_PLAN_PREVIEW_WARNING)
        warnings.extend(rollout_state.warnings)
        return CommandResult(
            command="settings.pipeline_plan_preview",
            ok=True,
            severity="warning",
            message="Settings PipelinePlan preview ready. Dry-run only; legacy execution remains authoritative.",
            warnings=warnings,
            data=data,
        )

    def save_settings_patch(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Validate and save explicit settings changes to the active PSD1 config."""
        if not bool(request.get("confirm_save", False)):
            return settings_save_confirmation_required_result()
        config_identity = dict(getattr(resolved, "config_identity", {}) or {})
        if config_identity.get("blocks_operations") is True:
            return settings_save_config_blocked_result(
                config_operation_block_message(config_identity, "Settings save"),
                config_operation_block_data(config_identity),
            )
        lock, block_message = self._acquire_settings_save_lock()
        if block_message:
            return settings_save_busy_result(block_message)
        warnings: list[str] = []
        try:
            patch = self._settings_patch_candidate(resolved, request, command="settings.save_patch")
            if patch["fatal_result"] is not None:
                return patch["fatal_result"]
            errors = patch["errors"]
            warnings = patch["warnings"]
            changed_keys = patch["changed_keys"]
            removed_keys = patch["removed_keys"]
            if errors:
                return settings_save_validation_error_result(errors, warnings)
            if not changed_keys and not removed_keys:
                return settings_save_no_changes_result(warnings)
            serializer = getattr(self.service, "serialize_psd1_document", None)
            saver = getattr(self.service, "save_config_document", None)
            if not callable(serializer) or not callable(saver):
                return settings_save_service_unavailable_result()
            document_text = str(serializer(patch["merged"]))
            result = saver(
                resolved.config_path,
                document_text,
                True,
                config_values=patch["merged"],
                powershell_host=resolved.powershell_host,
            )
        except Exception as exc:
            return settings_save_exception_result(exc, warnings)
        finally:
            self._release_settings_save_lock(lock)
        return settings_save_success_result(result, patch, warnings)

    def _acquire_settings_save_lock(self) -> tuple[object | None, str]:
        lock = getattr(self, "_settings_save_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_settings_save_exception("Settings save lock acquisition failed", exc)
            return None, f"Settings patch save blocked because the lock could not be verified: {exc}"
        if not acquired:
            return None, "Settings patch save blocked because another settings save command is already in progress."
        return lock, ""

    def _release_settings_save_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_settings_save_exception("Settings save lock release failed", exc)

    def _log_settings_save_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(getattr(self, "service", None), "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "SettingsPatchFacadeMixin",
]
