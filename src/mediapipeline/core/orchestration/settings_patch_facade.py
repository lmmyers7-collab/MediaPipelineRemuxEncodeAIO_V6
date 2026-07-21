"""Settings patch preview/save facade adapter with pipeline-plan preview."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, TypeAlias

from pydantic import ValidationError

from mediapipeline.core.config.rollout import planner_comparison_from_decision_snapshot, resolve_planner_rollout_config
from mediapipeline.core.config.settings_patch_policy import (
    _command_result,
    settings_patch_preview_result,
    settings_review_digest,
    settings_save_authority_conflict_result,
    settings_save_busy_result,
    settings_save_config_blocked_result,
    settings_save_confirmation_required_result,
    settings_save_exception_result,
    settings_save_idempotent_replay_result,
    settings_save_no_changes_result,
    settings_save_review_confirmation_error,
    settings_save_review_confirmation_required_result,
    settings_save_service_unavailable_result,
    settings_save_success_result,
    settings_save_validation_error_result,
    settings_config_digest,
)
from mediapipeline.core.config.authority_lock import SettingsAuthorityLockError
from mediapipeline.core.config.settings_store import SettingsAuthorityConflictError
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message
from mediapipeline.contracts.source_media import SourceMediaInfo
from mediapipeline.core.orchestration.planner import build_pipeline_plan_from_preset
from mediapipeline.core.paths.contracts import ResolvedPaths


_PIPELINE_PLAN_PREVIEW_AUTHORITY = "python_preview_legacy_execution_still_authoritative"
_PIPELINE_PLAN_PREVIEW_WARNING = (
    "Settings PipelinePlan preview is dry-run only; production execution still uses the legacy PowerShell path until cutover."
)
CommandResult: TypeAlias = Any


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
        preview_resolved = resolved
        authority_digest = ""
        authority_loader = getattr(self.service, "load_settings_authority", None)
        if callable(authority_loader):
            try:
                authority = authority_loader(resolved.config_path, resolved.powershell_host)
            except Exception:
                return _command_result(
                    command="settings.preview_patch",
                    ok=False,
                    severity="error",
                    message="Settings preview blocked because the JSON authority could not be verified.",
                    errors=["Refresh settings after the authority is repaired, then preview the patch again."],
                    data={"writes_config": False, "authority_verified": False},
                )
            if not isinstance(authority, dict):
                return _command_result(
                    command="settings.preview_patch",
                    ok=False,
                    severity="error",
                    message="Settings preview blocked because the JSON authority could not be verified.",
                    errors=["The settings authority did not contain a configuration object."],
                    data={"writes_config": False, "authority_verified": False},
                )
            preview_resolved = replace(resolved, config_data=dict(authority))
            authority_digest = settings_config_digest(authority)
        patch = self._settings_patch_candidate(preview_resolved, request, command="settings.preview_patch")
        if patch["fatal_result"] is not None:
            return patch["fatal_result"]
        if authority_digest:
            patch["authority_config_digest"] = authority_digest
        return settings_patch_preview_result(resolved, patch)

    def settings_patch_request_with_review_confirmation(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a save request bound to the current backend preview candidate."""
        preview = self.preview_settings_patch(resolved, request)
        data = preview.data if isinstance(preview.data, dict) else {}
        confirmed_request = dict(request)
        if isinstance(data.get("review_confirmation"), dict):
            confirmed_request["review_confirmation"] = dict(data["review_confirmation"])
        return confirmed_request

    def preview_settings_pipeline_plan(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Preview the Python planner result from strict source facts without saving settings."""
        try:
            source = SourceMediaInfo.model_validate(request.get("source_media"))
        except ValidationError as exc:
            return _command_result(
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
            return _command_result(
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
            return _command_result(
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
        return _command_result(
            command="settings.pipeline_plan_preview",
            ok=True,
            severity="warning",
            message="Settings PipelinePlan preview ready. Dry-run only; legacy execution remains authoritative.",
            warnings=warnings,
            data=data,
        )

    def save_settings_patch(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Validate and save explicit settings changes to the active PSD1 config."""
        if request.get("confirm_save") is not True:
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
            authority_loader = getattr(self.service, "load_settings_authority", None)
            submitted_confirmation = request.get("review_confirmation")
            submitted_authority_digest = (
                str(submitted_confirmation.get("authority_config_digest") or "")
                if isinstance(submitted_confirmation, dict)
                else ""
            )
            current_authority_digest = ""
            save_resolved = resolved
            if callable(authority_loader) and submitted_authority_digest:
                current_authority = authority_loader(resolved.config_path, resolved.powershell_host)
                if not isinstance(current_authority, dict):
                    return settings_save_review_confirmation_required_result(
                        submitted=submitted_confirmation,
                        reason="Settings authority could not be verified at commit time; save was blocked.",
                    )
                save_resolved = replace(resolved, config_data=dict(current_authority))
                current_authority_digest = settings_config_digest(current_authority)
                submitted_candidate_digest = str(submitted_confirmation.get("candidate_config_digest") or "")
                if (
                    current_authority_digest != submitted_authority_digest
                    and current_authority_digest != submitted_candidate_digest
                ):
                    return settings_save_authority_conflict_result(
                        expected_digest=submitted_authority_digest,
                        current_digest=current_authority_digest,
                        candidate_digest=submitted_candidate_digest,
                    )
            patch = self._settings_patch_candidate(save_resolved, request, command="settings.save_patch")
            if submitted_authority_digest:
                patch["authority_config_digest"] = submitted_authority_digest
            if patch["fatal_result"] is not None:
                return patch["fatal_result"]
            errors = patch["errors"]
            warnings = patch["warnings"]
            changed_keys = patch["changed_keys"]
            removed_keys = patch["removed_keys"]
            if errors:
                return settings_save_validation_error_result(errors, warnings)
            idempotent_replay = (
                isinstance(submitted_confirmation, dict)
                and bool(current_authority_digest)
                and current_authority_digest != submitted_authority_digest
                and current_authority_digest == str(submitted_confirmation.get("candidate_config_digest") or "")
                and settings_config_digest(patch["merged"]) == current_authority_digest
                and settings_review_digest(patch["request_evidence"])
                == str(submitted_confirmation.get("request_digest") or "")
            )
            authority_saver = getattr(self.service, "save_settings_authority", None)
            if idempotent_replay:
                if not callable(authority_saver):
                    return settings_save_service_unavailable_result()
                result = authority_saver(
                    save_resolved,
                    dict(patch["merged"]),
                    expected_authority_digest=submitted_authority_digest,
                )
                return settings_save_idempotent_replay_result(
                    result,
                    patch,
                    submitted_confirmation,
                    warnings,
                )
            if not changed_keys and not removed_keys:
                return settings_save_no_changes_result(warnings)
            review_confirmation_error = settings_save_review_confirmation_error(request, patch)
            if review_confirmation_error is not None:
                return review_confirmation_error
            serializer = getattr(self.service, "serialize_psd1_document", None)
            saver = getattr(self.service, "save_config_document", None)
            if callable(authority_saver):
                result = authority_saver(
                    save_resolved,
                    dict(patch["merged"]),
                    expected_authority_digest=submitted_authority_digest,
                )
            elif callable(serializer) and callable(saver):
                document_text = str(serializer(patch["merged"]))
                result = saver(
                    resolved.config_path,
                    document_text,
                    True,
                    config_values=dict(patch["merged"]),
                    powershell_host=resolved.powershell_host,
                )
            else:
                return settings_save_service_unavailable_result()
        except SettingsAuthorityConflictError as exc:
            return settings_save_authority_conflict_result(
                expected_digest=exc.expected_digest,
                current_digest=exc.current_digest,
                candidate_digest=exc.candidate_digest,
            )
        except SettingsAuthorityLockError as exc:
            return settings_save_busy_result(str(exc))
        except Exception as exc:
            return settings_save_exception_result(exc, warnings)
        finally:
            self._release_settings_save_lock(lock)

        hot_apply_results: list[dict[str, Any]] = []
        hot_apply = getattr(self, "_hot_apply_running_worker_settings", None)
        if callable(hot_apply):
            try:
                hot_apply_results = list(
                    hot_apply(
                        changed_keys=list(changed_keys),
                        merged_config=dict(patch["merged"]),
                        warnings=warnings,
                    )
                    or []
                )
            except Exception as exc:
                warnings.append(f"Running worker hot-apply check failed after settings save: {exc}")

        command_result = settings_save_success_result(result, patch, warnings)
        if hot_apply_results:
            command_result.data["network_worker_hot_apply"] = hot_apply_results
        return command_result

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
