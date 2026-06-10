"""Verification and publish guard contracts for pipeline plans."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VERIFICATION_RESULT_SCHEMA_VERSION: Literal["verification_result.v1"] = "verification_result.v1"

GuardStage = Literal["PRE_ROUTE", "PLAN", "POST_PROCESS", "PRE_PUBLISH"]
GuardEnforcement = Literal["HARD_ROUTE", "HARD_BLOCK", "SOFT_TARGET", "ADVISORY"]
OutputSizeCheckAction = Literal["disabled", "warn_only", "block_publish", "fail_job", "fallback_remux"]
OutputSizeCheckStatus = Literal["disabled", "planned", "passed", "warning", "blocked", "failed"]


class VerificationModel(BaseModel):
    """Strict base for verification and publish guard contracts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class VerificationGuard(VerificationModel):
    code: str
    name: str
    stage: GuardStage
    enforcement: GuardEnforcement
    condition: str
    on_pass: str = Field(alias="onPass")
    on_fail: str = Field(alias="onFail")
    message: str


class OutputSizeCheck(VerificationModel):
    action: OutputSizeCheckAction
    status: OutputSizeCheckStatus
    source_size_bytes: int | None = Field(default=None, ge=0, alias="sourceSizeBytes")
    target_output_size_bytes: int | None = Field(default=None, ge=0, alias="targetOutputSizeBytes")
    growth_tolerance_percent: float | None = Field(default=None, ge=0, alias="growthTolerancePercent")
    actual_output_size_bytes: int | None = Field(default=None, ge=0, alias="actualOutputSizeBytes")
    overage_bytes: int = Field(default=0, ge=0, alias="overageBytes")
    overage_percent: float = Field(default=0.0, ge=0, alias="overagePercent")
    on_fail: str = Field(default="record", alias="onFail")
    message: str


class VerificationResult(VerificationModel):
    schema_version: Literal["verification_result.v1"] = Field(
        default=VERIFICATION_RESULT_SCHEMA_VERSION,
        alias="schemaVersion",
    )
    status: Literal["planned", "passed", "warning", "blocked", "failed", "disabled"] = "planned"
    guards: list[VerificationGuard] = Field(default_factory=list)
    output_size_check: OutputSizeCheck | None = Field(default=None, alias="outputSizeCheck")
    advisory_warnings: list[str] = Field(default_factory=list, alias="advisoryWarnings")
    failures: list[str] = Field(default_factory=list)
    publish_blockers: list[str] = Field(default_factory=list, alias="publishBlockers")


def output_size_check_action_from_settings(
    mode: str | None,
    on_exceeded: str | None = None,
) -> OutputSizeCheckAction:
    """Normalize legacy Output Size Check settings or v2 on-exceeded actions."""

    action = str(on_exceeded or "").strip().lower().replace("-", "_").replace(" ", "_")
    if action in {"disabled", "disable", "ignore", "off"}:
        return "disabled"
    if action in {"warn", "warning", "warn_only", "advisory"}:
        return "warn_only"
    if action in {"block", "block_publish", "hold", "hold_for_review", "park", "park_pending_publish"}:
        return "block_publish"
    if action in {"fail", "fail_job", "error", "strict_fail"}:
        return "fail_job"
    if action in {"fallback_remux", "fallback_to_remux", "remux_fallback", "try_remux"}:
        return "fallback_remux"

    legacy_mode = str(mode or "").strip().lower()
    if legacy_mode == "off":
        return "disabled"
    if legacy_mode == "strict":
        return "fail_job"
    if legacy_mode in {"fallback_remux", "fallback_to_remux", "remux_fallback", "try_remux"}:
        return "fallback_remux"
    return "warn_only"


def planned_output_size_check(
    *,
    action: OutputSizeCheckAction,
    source_size_bytes: int | None,
    growth_tolerance_percent: float | None,
    applies: bool,
) -> OutputSizeCheck:
    """Return a dry-run output size check with no actual output yet."""

    if not applies or action == "disabled":
        return OutputSizeCheck(
            action="disabled",
            status="disabled",
            sourceSizeBytes=source_size_bytes,
            growthTolerancePercent=growth_tolerance_percent,
            onFail="continue",
            message="Output Size Check disabled or not applicable to this route.",
        )
    target = _target_output_size(source_size_bytes, growth_tolerance_percent)
    return OutputSizeCheck(
        action=action,
        status="planned",
        sourceSizeBytes=source_size_bytes,
        targetOutputSizeBytes=target,
        growthTolerancePercent=growth_tolerance_percent,
        onFail=_output_size_on_fail(action),
        message="Output Size Check will run after processing before publish.",
    )


def evaluate_output_size_check(
    *,
    action: OutputSizeCheckAction,
    source_size_bytes: int,
    actual_output_size_bytes: int,
    growth_tolerance_percent: float,
) -> OutputSizeCheck:
    """Evaluate an actual output size check without touching files."""

    if action == "disabled":
        return OutputSizeCheck(
            action="disabled",
            status="disabled",
            sourceSizeBytes=source_size_bytes,
            actualOutputSizeBytes=actual_output_size_bytes,
            growthTolerancePercent=growth_tolerance_percent,
            onFail="continue",
            message="Output Size Check disabled.",
        )

    target = _target_output_size(source_size_bytes, growth_tolerance_percent)
    if target is None or source_size_bytes <= 0 or actual_output_size_bytes <= 0:
        return OutputSizeCheck(
            action=action,
            status="warning",
            sourceSizeBytes=max(0, source_size_bytes),
            actualOutputSizeBytes=max(0, actual_output_size_bytes),
            growthTolerancePercent=max(0.0, growth_tolerance_percent),
            onFail="record_advisory_warning",
            message="Output Size Check could not compare source and output sizes.",
        )

    if actual_output_size_bytes <= target:
        return OutputSizeCheck(
            action=action,
            status="passed",
            sourceSizeBytes=source_size_bytes,
            targetOutputSizeBytes=target,
            actualOutputSizeBytes=actual_output_size_bytes,
            growthTolerancePercent=growth_tolerance_percent,
            onFail=_output_size_on_fail(action),
            message="Output Size Check passed.",
        )

    overage = actual_output_size_bytes - target
    overage_percent = round((overage / target) * 100.0, 3) if target > 0 else 0.0
    status: OutputSizeCheckStatus
    if action == "block_publish":
        status = "blocked"
    elif action == "fail_job" or action == "fallback_remux":
        status = "failed"
    else:
        status = "warning"
    return OutputSizeCheck(
        action=action,
        status=status,
        sourceSizeBytes=source_size_bytes,
        targetOutputSizeBytes=target,
        actualOutputSizeBytes=actual_output_size_bytes,
        growthTolerancePercent=growth_tolerance_percent,
        overageBytes=overage,
        overagePercent=overage_percent,
        onFail=_output_size_on_fail(action),
        message=(
            "Output Size Check exceeded: actual output is "
            f"{overage} byte(s) over the planned target."
        ),
    )


def verification_result_from_size_check(
    check: OutputSizeCheck,
    *,
    guards: list[VerificationGuard] | None = None,
) -> VerificationResult:
    """Shape check status into separate advisory, failure, and publish-blocker lists."""

    warnings: list[str] = []
    failures: list[str] = []
    blockers: list[str] = []
    status: Literal["planned", "passed", "warning", "blocked", "failed", "disabled"]
    status = check.status if check.status in {"planned", "passed", "warning", "blocked", "failed", "disabled"} else "planned"
    if check.status == "warning":
        warnings.append(check.message)
    elif check.status == "blocked":
        blockers.append(check.message)
    elif check.status == "failed":
        failures.append(check.message)
    return VerificationResult(
        status=status,
        guards=list(guards or []),
        outputSizeCheck=check,
        advisoryWarnings=warnings,
        failures=failures,
        publishBlockers=blockers,
    )


def _target_output_size(source_size_bytes: int | None, growth_tolerance_percent: float | None) -> int | None:
    if source_size_bytes is None or source_size_bytes <= 0:
        return None
    tolerance = max(0.0, float(growth_tolerance_percent or 0.0))
    return int(round(float(source_size_bytes) * (1.0 + (tolerance / 100.0))))


def _output_size_on_fail(action: OutputSizeCheckAction) -> str:
    if action == "block_publish":
        return "park_pending_publish"
    if action == "fail_job":
        return "fail_job"
    if action == "fallback_remux":
        return "try_remux_else_fail_job"
    if action == "warn_only":
        return "record_advisory_warning"
    return "continue"


__all__ = [
    "VERIFICATION_RESULT_SCHEMA_VERSION",
    "GuardEnforcement",
    "GuardStage",
    "OutputSizeCheck",
    "OutputSizeCheckAction",
    "OutputSizeCheckStatus",
    "VerificationGuard",
    "VerificationResult",
    "evaluate_output_size_check",
    "output_size_check_action_from_settings",
    "planned_output_size_check",
    "verification_result_from_size_check",
]
