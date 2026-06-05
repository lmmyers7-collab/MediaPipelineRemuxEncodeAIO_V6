"""Serializable abstract pipeline plans for dry-run previews."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from mediapipeline.contracts.verification import VerificationGuard, VerificationResult

PIPELINE_PLAN_SCHEMA_VERSION: Literal["pipeline_plan.v1"] = "pipeline_plan.v1"

PlanIntent = Literal["dry_run"]
PlanRouteSummary = Literal["COPY", "REMUX", "ENCODE", "REJECT", "UNKNOWN"]
PlanOperation = Literal[
    "copy_source",
    "copy_video",
    "encode_video",
    "copy_audio",
    "transcode_audio",
    "drop_audio",
    "copy_subtitle",
    "convert_subtitle",
    "burn_subtitle",
    "drop_subtitle",
    "mux_container",
    "verify_output",
    "publish_safety",
    "no_command",
]
PlanStreamType = Literal["source", "video", "audio", "subtitle", "container", "verification", "publish"]
FallbackMode = Literal["conditional_branch", "typed_executor_outcome"]


class PipelinePlanModel(BaseModel):
    """Strict base model for new pipeline-plan contracts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PlanReason(PipelinePlanModel):
    code: str
    text: str
    enforcement: str = "derived"
    legacy_code: str = Field(default="", alias="legacyCode")


class PlanStreamAction(PipelinePlanModel):
    stream_type: PlanStreamType = Field(alias="streamType")
    stream_index: int | None = Field(default=None, ge=0, alias="streamIndex")
    action: str
    input_codec: str = Field(default="", alias="inputCodec")
    output_codec: str = Field(default="", alias="outputCodec")
    reason_codes: list[str] = Field(default_factory=list, alias="reasonCodes")


class PlanOutputProposal(PipelinePlanModel):
    path: str
    container: str
    extension: str
    source_container: str = Field(default="", alias="sourceContainer")
    remux_required: bool = Field(alias="remuxRequired")
    copy_unchanged_possible: bool = Field(default=False, alias="copyUnchangedPossible")


class CommandPreviewStep(PipelinePlanModel):
    step_id: str = Field(alias="stepId")
    operation: PlanOperation
    stream_type: PlanStreamType = Field(alias="streamType")
    stream_index: int | None = Field(default=None, ge=0, alias="streamIndex")
    label: str
    dry_run_text: str = Field(alias="dryRunText")
    details: dict[str, Any] = Field(default_factory=dict)


class CommandPlan(PipelinePlanModel):
    command_plan_id: str = Field(alias="commandPlanId")
    route_summary: PlanRouteSummary = Field(alias="routeSummary")
    dry_run_only: bool = Field(default=True, alias="dryRunOnly")
    can_execute: bool = Field(default=False, alias="canExecute")
    preview_kind: Literal["abstract"] = Field(default="abstract", alias="previewKind")
    executor: str = "phase07b_powershell_plan_executor"
    reason_codes: list[str] = Field(default_factory=list, alias="reasonCodes")
    preview_lines: list[str] = Field(default_factory=list, alias="previewLines")
    steps: list[CommandPreviewStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuntimeFallbackBranch(PipelinePlanModel):
    fallback_id: str = Field(alias="fallbackId")
    mode: FallbackMode
    trigger: str
    action: str
    owner: Literal["python_planner", "executor_returns_typed_outcome"] = "python_planner"
    reason_codes: list[str] = Field(default_factory=list, alias="reasonCodes")
    notes: list[str] = Field(default_factory=list)


class PipelinePlan(PipelinePlanModel):
    schema_version: Literal["pipeline_plan.v1"] = Field(default=PIPELINE_PLAN_SCHEMA_VERSION, alias="schemaVersion")
    plan_id: str = Field(alias="planId")
    intent: PlanIntent = "dry_run"
    source_id: str = Field(alias="sourceId")
    source_path: str = Field(default="", alias="sourcePath")
    output: PlanOutputProposal
    route_summary: PlanRouteSummary = Field(alias="routeSummary")
    stream_actions: list[PlanStreamAction] = Field(default_factory=list, alias="streamActions")
    reason_summary: list[PlanReason] = Field(default_factory=list, alias="reasonSummary")
    warnings: list[str] = Field(default_factory=list)
    publish_strategy: str = Field(alias="publishStrategy")
    verification_requirements: list[dict[str, Any]] = Field(default_factory=list, alias="verificationRequirements")
    verification_guards: list[VerificationGuard] = Field(default_factory=list, alias="verificationGuards")
    verification_result: VerificationResult = Field(default_factory=VerificationResult, alias="verificationResult")
    publish_requirements: list[dict[str, Any]] = Field(default_factory=list, alias="publishRequirements")
    runtime_fallbacks: list[RuntimeFallbackBranch] = Field(default_factory=list, alias="runtimeFallbacks")
    command_plans: list[CommandPlan] = Field(default_factory=list, alias="commandPlans")
    effective_preset_snapshot: dict[str, Any] = Field(default_factory=dict, alias="effectivePresetSnapshot")
    decision_snapshot: dict[str, Any] = Field(default_factory=dict, alias="decisionSnapshot")


__all__ = [
    "PIPELINE_PLAN_SCHEMA_VERSION",
    "CommandPlan",
    "CommandPreviewStep",
    "PipelinePlan",
    "PlanOutputProposal",
    "PlanReason",
    "PlanStreamAction",
    "RuntimeFallbackBranch",
]
