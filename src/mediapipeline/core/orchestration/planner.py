"""Dry-run PipelinePlan builder for Python-owned routing decisions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import PureWindowsPath
from typing import Any

from mediapipeline.core.config.preset_migration import (
    effective_decision_policy_from_legacy_or_preset,
    preset_v2_from_legacy_config,
)
from mediapipeline.core.config.preset_policy import PresetV2
from mediapipeline.contracts.pipeline_plan import (
    CommandPlan,
    CommandPreviewStep,
    PipelinePlan,
    PlanOutputProposal,
    PlanReason,
    PlanStreamAction,
    RuntimeFallbackBranch,
)
from mediapipeline.contracts.source_media import SourceMediaInfo
from mediapipeline.core.decide.processing_decision import ProcessingDecision
from mediapipeline.core.decide.routing import build_processing_decision
from mediapipeline.core.decide.routing_facts import normalize_codec

_ABSTRACT_PREVIEW_WARNING = (
    "Phase 07 dry-run preview only; Phase 07B PowerShell executor must build concrete FFmpeg arguments from this plan."
)


def build_pipeline_plan_from_preset(
    source: SourceMediaInfo,
    preset: PresetV2 | Mapping[str, Any] | None = None,
    *,
    plan_id: str | None = None,
) -> PipelinePlan:
    """Build a dry-run plan from source facts and a legacy or PresetV2 policy."""

    preset_model = _preset_v2_from_input(preset)
    policy = effective_decision_policy_from_legacy_or_preset(preset_model)
    decision = build_processing_decision(source, policy)
    return build_pipeline_plan(source, decision, preset=preset_model, plan_id=plan_id)


def build_pipeline_plan(
    source: SourceMediaInfo,
    decision: ProcessingDecision,
    *,
    preset: PresetV2 | Mapping[str, Any] | None = None,
    plan_id: str | None = None,
) -> PipelinePlan:
    """Convert a ProcessingDecision into an abstract dry-run PipelinePlan.

    This function does not build executable FFmpeg arguments, touch files, or
    switch production execution. It shapes the Python-owned WHAT for Phase 07B.
    """

    output = _output_proposal(source, decision)
    stream_actions = _stream_actions(source, decision)
    reason_summary = [
        PlanReason(code=reason.code, text=reason.text, enforcement=reason.enforcement, legacyCode=reason.legacy_code)
        for reason in decision.route_reasons
    ]
    warnings = _plan_warnings(decision)
    publish_strategy = _publish_strategy(decision, preset)
    effective_preset_snapshot = _effective_preset_snapshot(decision, preset)
    stable_plan_id = plan_id or _stable_plan_id(
        source,
        decision,
        publish_strategy=publish_strategy,
        effective_preset_snapshot=effective_preset_snapshot,
    )
    command_plan = _command_plan(stable_plan_id, source, decision, warnings)
    return PipelinePlan(
        planId=stable_plan_id,
        sourceId=source.container.source_id or source.container.path,
        sourcePath=source.container.path,
        output=output,
        routeSummary=decision.route_summary,
        streamActions=stream_actions,
        reasonSummary=reason_summary,
        warnings=warnings,
        publishStrategy=publish_strategy,
        verificationRequirements=[
            requirement.model_dump(mode="json", by_alias=True) for requirement in decision.verification_requirements
        ],
        verificationGuards=decision.verification_guards,
        verificationResult=decision.verification_result,
        publishRequirements=[
            requirement.model_dump(mode="json", by_alias=True) for requirement in decision.publish_requirements
        ],
        runtimeFallbacks=_runtime_fallbacks(decision),
        commandPlans=[command_plan],
        effectivePresetSnapshot=effective_preset_snapshot,
        decisionSnapshot=decision.model_dump(mode="json", by_alias=True),
    )


def _preset_v2_from_input(preset: PresetV2 | Mapping[str, Any] | None) -> PresetV2:
    if isinstance(preset, PresetV2):
        return preset
    if isinstance(preset, Mapping) and preset.get("version") == 2:
        return PresetV2.model_validate(preset)
    return preset_v2_from_legacy_config(preset)


def _stable_plan_id(
    source: SourceMediaInfo,
    decision: ProcessingDecision,
    *,
    publish_strategy: str,
    effective_preset_snapshot: Mapping[str, Any],
) -> str:
    seed = json.dumps(
        {
            "sourceId": source.container.source_id or source.container.path,
            "sourcePath": source.container.path,
            "decision": decision.model_dump(mode="json", by_alias=True),
            "publishStrategy": publish_strategy,
            "effectivePresetSnapshot": dict(effective_preset_snapshot),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"pipeline-plan-{digest}"


def _output_proposal(source: SourceMediaInfo, decision: ProcessingDecision) -> PlanOutputProposal:
    container = decision.effective_settings.output_container
    extension = f".{container}"
    path = _proposal_path(source.container.path, extension)
    return PlanOutputProposal(
        path=path,
        container=container,
        extension=extension,
        sourceContainer=source.container.format_name,
        remuxRequired=decision.stream_actions.container in {"remux", "change"},
        copyUnchangedPossible=decision.route_summary == "COPY" and decision.stream_actions.container == "keep",
    )


def _proposal_path(source_path: str, extension: str) -> str:
    if not source_path.strip():
        return f"planned-output{extension}"
    path = PureWindowsPath(source_path)
    stem = path.stem or "planned-output"
    name = f"{stem}.planned{extension}"
    if str(path.parent) in {"", "."}:
        return name
    return str(path.with_name(name))


def _stream_actions(source: SourceMediaInfo, decision: ProcessingDecision) -> list[PlanStreamAction]:
    video_source = source.video_streams[0] if source.video_streams else None
    actions = [
        PlanStreamAction(
            streamType="video",
            streamIndex=decision.stream_actions.video.stream_index,
            action=decision.stream_actions.video.action,
            inputCodec=normalize_codec(video_source.codec) if video_source else "",
            outputCodec=decision.stream_actions.video.output_codec or decision.planned_encode_output.video.codec,
            reasonCodes=decision.stream_actions.video.reason_codes,
        ),
        PlanStreamAction(
            streamType="container",
            action=decision.stream_actions.container,
            inputCodec=source.container.format_name,
            outputCodec=decision.effective_settings.output_container,
            reasonCodes=_reason_codes_for(decision, "CONTAINER_REMUX_ONLY"),
        ),
    ]

    audio_by_index = {stream.stream_index: stream for stream in source.audio_streams}
    for item in decision.stream_actions.audio:
        audio_source = audio_by_index.get(item.stream_index)
        actions.append(
            PlanStreamAction(
                streamType="audio",
                streamIndex=item.stream_index,
                action=item.action,
                inputCodec=normalize_codec(audio_source.codec) if audio_source else "",
                outputCodec=item.output_codec,
                reasonCodes=item.reason_codes,
            )
        )

    subtitle_by_index = {stream.stream_index: stream for stream in source.subtitle_streams}
    for subtitle_item in decision.stream_actions.subtitles:
        subtitle_source = subtitle_by_index.get(subtitle_item.stream_index)
        actions.append(
            PlanStreamAction(
                streamType="subtitle",
                streamIndex=subtitle_item.stream_index,
                action=subtitle_item.action,
                inputCodec=normalize_codec(subtitle_source.codec) if subtitle_source else "",
                outputCodec=subtitle_item.output_codec,
                reasonCodes=subtitle_item.reason_codes,
            )
        )
    return actions


def _reason_codes_for(decision: ProcessingDecision, *codes: str) -> list[str]:
    wanted = {code.upper() for code in codes}
    return [reason.code for reason in decision.route_reasons if reason.code in wanted]


def _plan_warnings(decision: ProcessingDecision) -> list[str]:
    warnings = [_ABSTRACT_PREVIEW_WARNING, "Production execution remains on the existing PowerShell path for Phase 07."]
    warnings.extend(reason.text for reason in decision.advisory_warnings)
    return warnings


def _command_plan(
    plan_id: str,
    source: SourceMediaInfo,
    decision: ProcessingDecision,
    warnings: list[str],
) -> CommandPlan:
    steps = _command_steps(source, decision)
    reason_codes = [reason.code for reason in decision.route_reasons]
    preview_lines = _preview_lines(decision, steps, reason_codes)
    return CommandPlan(
        commandPlanId=f"{plan_id}-abstract-command",
        routeSummary=decision.route_summary,
        reasonCodes=reason_codes,
        previewLines=preview_lines,
        steps=steps,
        warnings=warnings,
    )


def _command_steps(source: SourceMediaInfo, decision: ProcessingDecision) -> list[CommandPreviewStep]:
    if decision.route_summary == "REJECT":
        return [
            CommandPreviewStep(
                stepId="no-command",
                operation="no_command",
                streamType="source",
                label="No command",
                dryRunText="Rejected source produces no remux, encode, publish, or cleanup command.",
                details={"routeSummary": decision.route_summary},
            )
        ]

    if decision.route_summary == "COPY" and decision.stream_actions.container == "keep":
        return [
            CommandPreviewStep(
                stepId="copy-source",
                operation="copy_source",
                streamType="source",
                label="Copy source unchanged",
                dryRunText="Copy the source payload unchanged through the existing scratch/publish safety path.",
                details={"sourcePath": source.container.path},
            ),
            _verify_step(),
            _publish_step(),
        ]

    steps: list[CommandPreviewStep] = [_video_step(decision)]
    steps.extend(_audio_steps(decision))
    steps.extend(_subtitle_steps(decision))
    steps.append(
        CommandPreviewStep(
            stepId="mux-container",
            operation="mux_container",
            streamType="container",
            label=f"Mux {decision.effective_settings.output_container.upper()} container",
            dryRunText=f"Mux the planned stream actions into {decision.effective_settings.output_container.upper()} using the Phase 07B executor.",
            details={
                "containerAction": decision.stream_actions.container,
                "outputContainer": decision.effective_settings.output_container,
            },
        )
    )
    steps.append(_verify_step())
    steps.append(_publish_step())
    return steps


def _video_step(decision: ProcessingDecision) -> CommandPreviewStep:
    video = decision.stream_actions.video
    planned = decision.planned_encode_output.video
    if video.action == "encode":
        return CommandPreviewStep(
            stepId=f"video-{video.stream_index}-encode",
            operation="encode_video",
            streamType="video",
            streamIndex=video.stream_index,
            label="Encode video",
            dryRunText=f"Encode video stream {video.stream_index} with {planned.codec}; concrete arguments remain PowerShell-owned.",
            details={
                "codec": planned.codec,
                "codecFamily": planned.codec_family,
                "encoderBackend": planned.encoder_backend,
                "targetMode": planned.target_mode,
                "qualityTarget": planned.quality_target,
                "targetBitrateMbps": planned.target_bitrate_mbps,
                "maxBitrateMbps": planned.max_bitrate_mbps,
                "outputHeight": planned.output_height,
                "filters": planned.filters,
                "reasonCodes": video.reason_codes,
            },
        )
    return CommandPreviewStep(
        stepId=f"video-{video.stream_index}-copy",
        operation="copy_video",
        streamType="video",
        streamIndex=video.stream_index,
        label="Copy video",
        dryRunText=f"Copy video stream {video.stream_index} without video transcode.",
        details={"reasonCodes": video.reason_codes},
    )


def _audio_steps(decision: ProcessingDecision) -> list[CommandPreviewStep]:
    steps: list[CommandPreviewStep] = []
    for item in decision.stream_actions.audio:
        operation = {
            "copy": "copy_audio",
            "transcode": "transcode_audio",
            "drop": "drop_audio",
            "unknown": "copy_audio",
        }[item.action]
        output = item.output_codec or decision.effective_settings.audio_transcode_codec if item.action == "transcode" else item.output_codec
        steps.append(
            CommandPreviewStep(
                stepId=f"audio-{item.stream_index}-{item.action}",
                operation=operation,  # type: ignore[arg-type]
                streamType="audio",
                streamIndex=item.stream_index,
                label=f"{item.action.title()} audio",
                dryRunText=f"{item.action.title()} audio stream {item.stream_index}.",
                details={"outputCodec": output, "reasonCodes": item.reason_codes},
            )
        )
    return steps


def _subtitle_steps(decision: ProcessingDecision) -> list[CommandPreviewStep]:
    steps: list[CommandPreviewStep] = []
    for item in decision.stream_actions.subtitles:
        operation = {
            "copy": "copy_subtitle",
            "convert": "convert_subtitle",
            "burn": "burn_subtitle",
            "drop": "drop_subtitle",
            "unknown": "copy_subtitle",
        }[item.action]
        steps.append(
            CommandPreviewStep(
                stepId=f"subtitle-{item.stream_index}-{item.action}",
                operation=operation,  # type: ignore[arg-type]
                streamType="subtitle",
                streamIndex=item.stream_index,
                label=f"{item.action.title()} subtitle",
                dryRunText=f"{item.action.title()} subtitle stream {item.stream_index}.",
                details={"outputCodec": item.output_codec, "reasonCodes": item.reason_codes},
            )
        )
    return steps


def _verify_step() -> CommandPreviewStep:
    return CommandPreviewStep(
        stepId="verify-output",
        operation="verify_output",
        streamType="verification",
        label="Verify output",
        dryRunText="Probe duration, size, stream evidence, and sidecar/manifest requirements before publish.",
    )


def _publish_step() -> CommandPreviewStep:
    return CommandPreviewStep(
        stepId="publish-safety",
        operation="publish_safety",
        streamType="publish",
        label="Apply publish safety",
        dryRunText="Use pending-publish parking if final placement is unsafe; do not bypass manifest evidence.",
    )


def _preview_lines(
    decision: ProcessingDecision,
    steps: list[CommandPreviewStep],
    reason_codes: list[str],
) -> list[str]:
    return [
        f"route: {decision.route_summary}",
        f"why: {', '.join(reason_codes) if reason_codes else 'no route reasons recorded'}",
        f"video action: {decision.stream_actions.video.action}",
        f"container action: {decision.stream_actions.container} -> {decision.effective_settings.output_container}",
        "steps: " + " -> ".join(step.operation for step in steps),
    ]


def _publish_strategy(decision: ProcessingDecision, preset: PresetV2 | Mapping[str, Any] | None) -> str:
    if decision.route_summary == "REJECT":
        return "no_publish"
    preset_model = _preset_v2_from_input(preset) if preset is not None else None
    if preset_model and preset_model.publish.deferred_publish:
        return "park_pending_publish"
    return "publish_with_pending_safety"


def _runtime_fallbacks(decision: ProcessingDecision) -> list[RuntimeFallbackBranch]:
    fallbacks: list[RuntimeFallbackBranch] = []
    if decision.route_summary in {"COPY", "REMUX"} and decision.stream_actions.video.action == "copy":
        fallbacks.append(
            RuntimeFallbackBranch(
                fallbackId="remux-codec-recheck",
                mode="typed_executor_outcome",
                trigger="executor reports copied video codec or container cannot be safely remuxed",
                action="return typed outcome for Python re-plan; do not silently switch routes in PowerShell",
                owner="executor_returns_typed_outcome",
                reasonCodes=["SOURCE_CODEC_INCOMPATIBLE"],
                notes=["Models the current remux-to-encode fallback as an explicit future back-edge."],
            )
        )
    if decision.stream_actions.video.action == "encode" and decision.planned_encode_output.video.encoder_backend == "nvenc":
        fallbacks.append(
            RuntimeFallbackBranch(
                fallbackId="nvenc-cpu-fallback",
                mode="conditional_branch",
                trigger="NVENC unavailable or hardware encode fails with a retryable hardware error",
                action="retry through a Python-authored CPU encode branch in Phase 07B/rollout",
                reasonCodes=["HARDWARE_ENCODER_CPU_FALLBACK"],
                notes=["Concrete CPU FFmpeg arguments remain PowerShell-owned and are not built in Phase 07."],
            )
        )
    return fallbacks


def _effective_preset_snapshot(
    decision: ProcessingDecision,
    preset: PresetV2 | Mapping[str, Any] | None,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "effectiveDecisionPolicy": decision.effective_settings.model_dump(mode="json", by_alias=True),
    }
    if preset is not None:
        preset_model = _preset_v2_from_input(preset)
        snapshot["presetV2"] = preset_model.model_dump(mode="json", by_alias=True)
    return snapshot


__all__ = ["build_pipeline_plan", "build_pipeline_plan_from_preset"]
