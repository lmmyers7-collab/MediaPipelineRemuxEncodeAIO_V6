"""Controlled rollout helpers for the HandBrake/remux planner."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from mediapipeline.core.config.preset_policy import PRESET_POLICY_WRITE_FORMAT

PLANNER_ROLLOUT_SCHEMA_VERSION: Literal["planner_rollout.v1"] = "planner_rollout.v1"
PLANNER_COMPARISON_SCHEMA_VERSION: Literal["planner_comparison.v1"] = "planner_comparison.v1"

PlannerRolloutStage = Literal[
    "legacy",
    "shadow",
    "selected_jobs",
    "ui_old_backend",
    "new_planner_default",
    "deprecation_cleanup",
]
ExecutionAuthority = Literal[
    "legacy_powershell",
    "legacy_powershell_with_python_preview",
    "python_planner_cutover",
]
PlannerComparisonStatus = Literal["disabled", "match", "divergent", "unknown"]

_STAGE_KEY = "PlannerRolloutStage"
_USE_NEW_PLANNER_KEYS = ("UsePythonPlanner", "EnablePythonPlanner", "EnableNewPlanner")
_UI_KEYS = ("EnableHandBrakeSettingsUi", "EnableHandbrakeSettingsUi", "EnableNewPlannerUi")
_COMPARISON_KEYS = ("PlannerComparisonLogging", "EnablePlannerComparisonLogging")
_CUTOVER_APPROVAL_KEYS = ("NewPlannerCutoverApproved", "PlannerCutoverApproved")

_STAGE_ALIASES: Mapping[str, PlannerRolloutStage] = {
    "": "legacy",
    "0": "legacy",
    "legacy": "legacy",
    "legacy_only": "legacy",
    "old": "legacy",
    "old_path": "legacy",
    "stage1": "shadow",
    "stage_1": "shadow",
    "parallel": "shadow",
    "parallel_planning": "shadow",
    "shadow": "shadow",
    "shadow_only": "shadow",
    "stage2": "selected_jobs",
    "stage_2": "selected_jobs",
    "feature_flag": "selected_jobs",
    "selected": "selected_jobs",
    "selected_jobs": "selected_jobs",
    "test_library": "selected_jobs",
    "stage3": "ui_old_backend",
    "stage_3": "ui_old_backend",
    "ui": "ui_old_backend",
    "ui_old_backend": "ui_old_backend",
    "new_ui_old_backend": "ui_old_backend",
    "stage4": "new_planner_default",
    "stage_4": "new_planner_default",
    "default_new": "new_planner_default",
    "new_default": "new_planner_default",
    "new_planner_default": "new_planner_default",
    "cutover": "new_planner_default",
    "stage5": "deprecation_cleanup",
    "stage_5": "deprecation_cleanup",
    "cleanup": "deprecation_cleanup",
    "deprecation_cleanup": "deprecation_cleanup",
}

_ROUTE_ALIASES: Mapping[str, str] = {
    "copy": "COPY",
    "direct_copy": "COPY",
    "passthrough": "COPY",
    "remux": "REMUX",
    "direct_stream": "REMUX",
    "encode": "ENCODE",
    "transcode": "ENCODE",
    "reject": "REJECT",
    "blocked": "REJECT",
    "unknown": "UNKNOWN",
}


class RolloutModel(BaseModel):
    """Strict base for rollout DTOs."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", populate_by_name=True)


class PlannerRolloutState(RolloutModel):
    schema_version: Literal["planner_rollout.v1"] = Field(
        default=PLANNER_ROLLOUT_SCHEMA_VERSION,
        alias="schemaVersion",
    )
    stage: PlannerRolloutStage = "legacy"
    execution_authority: ExecutionAuthority = Field(default="legacy_powershell", alias="executionAuthority")
    new_planner_requested: bool = Field(default=False, alias="newPlannerRequested")
    new_planner_execution_enabled: bool = Field(default=False, alias="newPlannerExecutionEnabled")
    new_ui_enabled: bool = Field(default=False, alias="newUiEnabled")
    comparison_logging_enabled: bool = Field(default=False, alias="comparisonLoggingEnabled")
    dry_run_only: bool = Field(default=True, alias="dryRunOnly")
    preset_write_format: Literal["legacy"] = Field(default=PRESET_POLICY_WRITE_FORMAT, alias="presetWriteFormat")
    config_keys_used: list[str] = Field(default_factory=list, alias="configKeysUsed")
    warnings: list[str] = Field(default_factory=list)
    operator_actions_required: list[str] = Field(default_factory=list, alias="operatorActionsRequired")


class PlannerComparisonRecord(RolloutModel):
    schema_version: Literal["planner_comparison.v1"] = Field(
        default=PLANNER_COMPARISON_SCHEMA_VERSION,
        alias="schemaVersion",
    )
    enabled: bool = False
    status: PlannerComparisonStatus = "disabled"
    legacy_route: str = Field(default="", alias="legacyRoute")
    legacy_reason_code: str = Field(default="", alias="legacyReasonCode")
    python_route: str = Field(default="", alias="pythonRoute")
    python_reason_codes: list[str] = Field(default_factory=list, alias="pythonReasonCodes")
    evidence_source: str = Field(default="processing_decision_snapshot", alias="evidenceSource")
    notes: list[str] = Field(default_factory=list)


def resolve_planner_rollout_config(value: Mapping[str, Any] | None = None) -> PlannerRolloutState:
    """Resolve rollout state from the existing config mapping shape.

    The recognized keys are intentionally extras-compatible so legacy PSD1/JSON
    configs still load. Nothing here starts execution; callers must treat this
    as rollout evidence unless a later operator-approved cutover wires it in.
    """

    config = {str(key): item for key, item in dict(value or {}).items()}
    keys_used: list[str] = []
    warnings: list[str] = []

    raw_stage = config.get(_STAGE_KEY, "")
    if _STAGE_KEY in config:
        keys_used.append(_STAGE_KEY)
    stage = _normalize_stage(raw_stage)
    if raw_stage not in (None, "") and stage == "legacy" and _normalized_text(raw_stage) not in _STAGE_ALIASES:
        warnings.append(f"Unknown PlannerRolloutStage {raw_stage!r}; keeping legacy execution authority.")

    use_new_planner, used = _first_truthy(config, _USE_NEW_PLANNER_KEYS)
    keys_used.extend(used)
    ui_requested, used = _first_truthy(config, _UI_KEYS)
    keys_used.extend(used)
    comparison_requested, used = _first_truthy(config, _COMPARISON_KEYS)
    keys_used.extend(used)
    cutover_approved, used = _first_truthy(config, _CUTOVER_APPROVAL_KEYS)
    keys_used.extend(used)

    if stage == "legacy":
        if comparison_requested:
            stage = "shadow"
        elif ui_requested:
            stage = "ui_old_backend"
        elif use_new_planner:
            stage = "selected_jobs"

    new_planner_requested = use_new_planner or stage in {
        "selected_jobs",
        "new_planner_default",
        "deprecation_cleanup",
    }
    new_ui_enabled = ui_requested or stage in {
        "ui_old_backend",
        "new_planner_default",
        "deprecation_cleanup",
    }
    comparison_logging_enabled = comparison_requested or stage in {
        "shadow",
        "selected_jobs",
        "new_planner_default",
        "deprecation_cleanup",
    }
    cutover_stage = stage in {"new_planner_default", "deprecation_cleanup"}
    execution_enabled = bool(new_planner_requested and cutover_stage and cutover_approved)

    if new_planner_requested and not execution_enabled:
        warnings.append(
            "New planner execution is requested only as preview/shadow evidence; legacy PowerShell remains authoritative."
        )
    if cutover_stage and not cutover_approved:
        warnings.append("Planner cutover stage requested without NewPlannerCutoverApproved; execution stays legacy.")
    if execution_enabled:
        warnings.append(
            "Planner cutover is enabled in rollout state, but production execution must still be wired and validated separately."
        )

    authority: ExecutionAuthority = "legacy_powershell"
    if execution_enabled:
        authority = "python_planner_cutover"
    elif stage != "legacy" or comparison_logging_enabled or new_ui_enabled:
        authority = "legacy_powershell_with_python_preview"

    operator_actions = [
        "Review old/new planner differences before any cutover.",
        "Run the validation ladder and representative real-media validation before production route replacement.",
        "Keep PRESET_POLICY_WRITE_FORMAT as legacy until a later operator-approved persistence migration.",
    ]

    return PlannerRolloutState(
        stage=stage,
        executionAuthority=authority,
        newPlannerRequested=new_planner_requested,
        newPlannerExecutionEnabled=execution_enabled,
        newUiEnabled=new_ui_enabled,
        comparisonLoggingEnabled=comparison_logging_enabled,
        dryRunOnly=not execution_enabled,
        presetWriteFormat=PRESET_POLICY_WRITE_FORMAT,
        configKeysUsed=sorted(set(keys_used), key=str.casefold),
        warnings=warnings,
        operatorActionsRequired=operator_actions,
    )


def planner_comparison_from_decision_snapshot(
    decision_snapshot: Mapping[str, Any] | None,
    *,
    rollout_state: PlannerRolloutState | Mapping[str, Any] | None = None,
    legacy_route: str | None = None,
    legacy_reason_code: str | None = None,
) -> PlannerComparisonRecord:
    """Build an inspectable old/new route comparison for dry-run previews."""

    state = _rollout_state(rollout_state)
    snapshot = dict(decision_snapshot or {})
    python_route = _normalized_route(snapshot.get("routeSummary"))
    legacy_raw = legacy_route if legacy_route is not None else str(snapshot.get("legacyRoute", "") or "")
    legacy_route_normalized = _normalized_route(legacy_raw)
    legacy_reason = legacy_reason_code if legacy_reason_code is not None else str(snapshot.get("legacyReasonCode", "") or "")
    reason_codes = [
        str(item.get("code", "")).strip().upper()
        for item in snapshot.get("routeReasons", [])
        if isinstance(item, Mapping) and str(item.get("code", "")).strip()
    ]

    if not state.comparison_logging_enabled:
        return PlannerComparisonRecord(
            enabled=False,
            status="disabled",
            legacyRoute=legacy_route_normalized,
            legacyReasonCode=legacy_reason,
            pythonRoute=python_route,
            pythonReasonCodes=reason_codes,
        )

    if not python_route or not legacy_route_normalized:
        status: PlannerComparisonStatus = "unknown"
    elif python_route == legacy_route_normalized:
        status = "match"
    else:
        status = "divergent"

    notes = [
        "Comparison is dry-run evidence only; it does not change queue, execution, publish, or cleanup behavior."
    ]
    if legacy_route is None:
        notes.append(
            "Legacy route came from the Python decision compatibility field; production PowerShell old-path logging is not wired here."
        )

    return PlannerComparisonRecord(
        enabled=True,
        status=status,
        legacyRoute=legacy_route_normalized,
        legacyReasonCode=legacy_reason,
        pythonRoute=python_route,
        pythonReasonCodes=reason_codes,
        notes=notes,
    )


def _rollout_state(value: PlannerRolloutState | Mapping[str, Any] | None) -> PlannerRolloutState:
    if isinstance(value, PlannerRolloutState):
        return value
    if isinstance(value, Mapping):
        return PlannerRolloutState.model_validate(value)
    return resolve_planner_rollout_config()


def _normalize_stage(value: Any) -> PlannerRolloutStage:
    return _STAGE_ALIASES.get(_normalized_text(value), "legacy")


def _normalized_route(value: Any) -> str:
    text = _normalized_text(value)
    return _ROUTE_ALIASES.get(text, text.upper() if text else "")


def _first_truthy(config: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[bool, list[str]]:
    used = [key for key in keys if key in config]
    return any(_truthy(config.get(key)) for key in keys), used


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return _normalized_text(value) in {"1", "true", "yes", "on", "enabled", "enable"}


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().casefold()


__all__ = [
    "PLANNER_COMPARISON_SCHEMA_VERSION",
    "PLANNER_ROLLOUT_SCHEMA_VERSION",
    "PlannerComparisonRecord",
    "PlannerComparisonStatus",
    "PlannerRolloutStage",
    "PlannerRolloutState",
    "planner_comparison_from_decision_snapshot",
    "resolve_planner_rollout_config",
]
