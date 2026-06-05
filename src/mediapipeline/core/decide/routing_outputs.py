"""Output shaping for pure copy/remux/encode decisions."""

from __future__ import annotations

from typing import Any

from mediapipeline.contracts.source_media import SourceMediaInfo
from mediapipeline.contracts.verification import (
    OutputSizeCheckAction,
    VerificationGuard,
    VerificationResult,
    planned_output_size_check,
    verification_result_from_size_check,
)
from mediapipeline.core.decide.encoding_rules import planned_output_height
from mediapipeline.core.decide.processing_decision import (
    DecisionReason,
    DecisionRequirement,
    EffectiveDecisionPolicy,
    PlannedAudioEncodeOutput,
    PlannedEncodeOutput,
    PlannedSubtitleEncodeOutput,
    PlannedVideoEncodeOutput,
    ProcessingDecision,
    StreamActionSet,
    derive_route_summary,
)
from mediapipeline.core.decide.routing_facts import estimated_bitrate_mbps, normalize_codec

_COMPATIBILITY_SIZE_REASONS = frozenset(
    {
        "plex_strict_score_below_threshold",
        "codec_outside_policy",
        "resolution_over_policy",
        "bitrate_over_threshold",
        "forced_remux_rejected_unsafe_codec",
        "hardware_encoder_safe_retry_succeeded",
        "hardware_encoder_cpu_fallback",
        "gpu_unavailable_cpu_only",
    }
)


def finalize_decision(
    source: SourceMediaInfo,
    policy: EffectiveDecisionPolicy,
    reasons: list[DecisionReason],
    actions: StreamActionSet,
    legacy_route: str,
    legacy_reason_code: str,
    source_facts: dict[str, Any] | None = None,
) -> ProcessingDecision:
    summary = derive_route_summary(actions)
    if summary == "REJECT":
        legacy_route = "reject"
    elif summary == "UNKNOWN":
        legacy_route = "unknown"

    guards = verification_guards(summary, policy, source, legacy_reason_code)
    result = planned_verification_result(summary, policy, source, legacy_reason_code, guards)
    return ProcessingDecision(
        streamActions=actions,
        routeSummary=summary,
        routeReasons=reasons,
        sourceFactsUsed=source_facts_for_output(source, policy, source_facts),
        hardRulesTriggered=[reason for reason in reasons if reason.enforcement in {"hard_route", "hard_block"}],
        softTargetsExceeded=[reason for reason in reasons if reason.enforcement == "soft_target"],
        advisoryWarnings=[reason for reason in reasons if reason.enforcement == "advisory"],
        plannedOutputSummary=planned_output_summary(source, policy, actions, summary),
        plannedEncodeOutput=planned_encode_output(source, policy, actions),
        verificationRequirements=verification_requirements(summary, policy, legacy_reason_code),
        verificationGuards=guards,
        verificationResult=result,
        publishRequirements=publish_requirements(summary, policy),
        effectiveSettings=policy,
        legacyRoute=legacy_route,
        legacyReasonCode=legacy_reason_code,
    )


def source_facts_for_output(
    source: SourceMediaInfo,
    policy: EffectiveDecisionPolicy,
    routing_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary = source.video_streams[0] if source.video_streams else None
    facts: dict[str, Any] = {
        "media_type": source.container.media_type,
        "source_container": source.container.format_name,
        "source_size_bytes": source.container.file_size_bytes,
        "duration_seconds": source.container.duration_seconds,
        "primary_video_codec": normalize_codec(primary.codec) if primary else "",
        "primary_video_height": primary.height if primary else 0,
        "estimated_video_bitrate_mbps": round(estimated_bitrate_mbps(source, primary), 3) if primary else 0.0,
        "output_container": policy.output_container,
    }
    if routing_facts:
        facts.update(routing_facts)
        facts["source_container"] = source.container.format_name
        facts["primary_video_codec"] = normalize_codec(primary.codec) if primary else ""
        facts["primary_video_height"] = primary.height if primary else 0
        facts["output_container"] = policy.output_container
    return facts


def planned_output_summary(
    source: SourceMediaInfo,
    policy: EffectiveDecisionPolicy,
    actions: StreamActionSet,
    summary: str,
) -> dict[str, Any]:
    primary = source.video_streams[0] if source.video_streams else None
    return {
        "route_summary": summary,
        "container": policy.output_container,
        "video": actions.video.action,
        "video_codec": normalize_codec(primary.codec) if primary else "",
        "audio": {
            "copy": sum(1 for item in actions.audio if item.action == "copy"),
            "transcode": sum(1 for item in actions.audio if item.action == "transcode"),
            "drop": sum(1 for item in actions.audio if item.action == "drop"),
        },
        "subtitles": {
            "copy": sum(1 for item in actions.subtitles if item.action == "copy"),
            "convert": sum(1 for item in actions.subtitles if item.action == "convert"),
            "burn": sum(1 for item in actions.subtitles if item.action == "burn"),
            "drop": sum(1 for item in actions.subtitles if item.action == "drop"),
        },
    }


def planned_encode_output(
    source: SourceMediaInfo,
    policy: EffectiveDecisionPolicy,
    actions: StreamActionSet,
) -> PlannedEncodeOutput:
    primary = source.video_streams[0] if source.video_streams else None
    video_active = actions.video.action == "encode"
    return PlannedEncodeOutput(
        video=PlannedVideoEncodeOutput(
            active=video_active,
            codec=policy.video_output_codec if video_active else normalize_codec(primary.codec) if primary else "",
            codecFamily=policy.video_codec_family if video_active else normalize_codec(primary.codec) if primary else "",
            encoderBackend=policy.video_encoder_backend if video_active else "copy",
            targetMode=policy.video_target_mode,
            qualityTarget=policy.video_quality_target if video_active else None,
            targetBitrateMbps=policy.video_target_bitrate_mbps if video_active else None,
            maxBitrateMbps=policy.video_max_bitrate_mbps if video_active else None,
            resolutionLimit=policy.resolution_limit,
            outputHeight=planned_output_height(primary, policy, actions.video.action),
            filters=policy.video_filter_names if video_active else [],
            forcedBy=actions.video.reason_codes,
        ),
        audio=PlannedAudioEncodeOutput(
            transcodeStreams=[item.stream_index for item in actions.audio if item.action == "transcode"],
            outputCodec=policy.audio_transcode_codec if any(item.action == "transcode" for item in actions.audio) else "",
            passthroughStreams=[item.stream_index for item in actions.audio if item.action == "copy"],
            droppedStreams=[item.stream_index for item in actions.audio if item.action == "drop"],
        ),
        subtitles=PlannedSubtitleEncodeOutput(
            copiedStreams=[item.stream_index for item in actions.subtitles if item.action == "copy"],
            convertedStreams=[item.stream_index for item in actions.subtitles if item.action == "convert"],
            burnedStreams=[item.stream_index for item in actions.subtitles if item.action == "burn"],
            droppedStreams=[item.stream_index for item in actions.subtitles if item.action == "drop"],
        ),
        container=policy.output_container,
    )


def verification_requirements(summary: str, policy: EffectiveDecisionPolicy, legacy_reason_code: str = "") -> list[DecisionRequirement]:
    requirements = [
        DecisionRequirement(code="OUTPUT_FILE_EXISTS", text="processed output file must exist before publish", enforcement="hard_block"),
        DecisionRequirement(code="OUTPUT_PROBE_REQUIRED", text="probe planned output before publish", enforcement="hard_block"),
        DecisionRequirement(code="DURATION_MATCH_REQUIRED", text="verify output duration against source", enforcement="hard_block"),
        DecisionRequirement(code="EXPECTED_STREAMS_PRESENT", text="verify expected video, audio, and subtitle stream outcomes", enforcement="hard_block"),
        DecisionRequirement(code="VIDEO_STREAM_PROBEABLE", text="output video stream must be probeable/playable before publish", enforcement="hard_block"),
        DecisionRequirement(code="SUBTITLE_OUTCOME_RECORDED", text="subtitle copy/convert/OCR outcomes must be recorded; failures route to review", enforcement="hard_block"),
    ]
    size_action = _size_check_action(policy)
    if summary == "ENCODE" and size_action != "disabled":
        growth = _size_growth_tolerance_percent(policy, legacy_reason_code)
        code = {
            "warn_only": "OUTPUT_SIZE_CHECK_WARN_ONLY",
            "block_publish": "OUTPUT_SIZE_CHECK_BLOCK_PUBLISH",
            "fail_job": "OUTPUT_SIZE_CHECK_FAIL_JOB",
            "disabled": "OUTPUT_SIZE_CHECK_DISABLED",
        }[size_action]
        requirements.append(
            DecisionRequirement(
                code=code,
                text=f"apply Output Size Check after encode with {growth:g}% growth tolerance",
                enforcement="hard_block" if size_action in {"block_publish", "fail_job"} else "advisory",
            )
        )
    requirements.append(
        DecisionRequirement(
            code="CHECKSUM_IF_SUPPORTED",
            text="record checksum/hash verification when the execution path supports it",
            enforcement="advisory",
        )
    )
    return requirements


def publish_requirements(summary: str, policy: EffectiveDecisionPolicy | None = None) -> list[DecisionRequirement]:
    if summary == "REJECT":
        return [
            DecisionRequirement(
                code="NO_PUBLISH_FOR_REJECTED_SOURCE",
                text="rejected sources must not publish output",
                enforcement="hard_block",
            )
        ]
    requirements = [
        DecisionRequirement(
            code="PENDING_PUBLISH_SAFETY_REQUIRED",
            text="unsafe final placement must use pending publish parking",
            enforcement="hard_block",
        ),
        DecisionRequirement(code="MANIFEST_EVIDENCE_REQUIRED", text="publish requires manifest and sidecar evidence", enforcement="hard_block"),
    ]
    if policy is not None and _size_check_action(policy) == "block_publish":
        requirements.append(
            DecisionRequirement(
                code="OUTPUT_SIZE_BLOCK_USES_PENDING_PUBLISH",
                text="Output Size Check block-publish failures park output through the existing pending-publish flow",
                enforcement="hard_block",
            )
        )
    if policy is not None and _size_check_action(policy) == "fail_job":
        requirements.append(
            DecisionRequirement(
                code="OUTPUT_SIZE_FAILS_JOB_BEFORE_PUBLISH",
                text="Output Size Check fail-job failures use current failure handling and do not publish output",
                enforcement="hard_block",
            )
        )
    return requirements


def verification_guards(
    summary: str,
    policy: EffectiveDecisionPolicy,
    source: SourceMediaInfo,
    legacy_reason_code: str,
) -> list[VerificationGuard]:
    guards = [
        VerificationGuard(
            code="OUTPUT_FILE_EXISTS",
            name="Output file exists",
            stage="POST_PROCESS",
            enforcement="HARD_BLOCK",
            condition="processed output path is present and non-empty",
            onPass="continue_verification",
            onFail="fail_job",
            message="Missing or empty outputs must not publish.",
        ),
        VerificationGuard(
            code="OUTPUT_DURATION_SANITY",
            name="Output duration sanity",
            stage="POST_PROCESS",
            enforcement="HARD_BLOCK",
            condition="output duration reconciles with source duration tolerance",
            onPass="continue_verification",
            onFail="fail_job",
            message="Duration mismatches fail verification before publish.",
        ),
        VerificationGuard(
            code="EXPECTED_STREAMS_PRESENT",
            name="Expected streams present",
            stage="POST_PROCESS",
            enforcement="HARD_BLOCK",
            condition="planned video, audio, and subtitle stream outcomes are present or intentionally removed",
            onPass="continue_verification",
            onFail="fail_job",
            message="Missing stream evidence must not silently publish.",
        ),
        VerificationGuard(
            code="SUBTITLE_OUTCOME_REVIEW",
            name="Subtitle outcome review",
            stage="POST_PROCESS",
            enforcement="HARD_BLOCK",
            condition="subtitle conversion/OCR succeeds or routes to review",
            onPass="continue_verification",
            onFail="fail_job",
            message="Subtitle conversion/OCR failure routes to review rather than silent publish.",
        ),
    ]
    size_guard = _output_size_guard(summary, policy, source, legacy_reason_code)
    if size_guard is not None:
        guards.append(size_guard)
    guards.append(
        VerificationGuard(
            code="PENDING_PUBLISH_SAFETY",
            name="Pending publish safety",
            stage="PRE_PUBLISH",
            enforcement="HARD_BLOCK",
            condition="final destination is safe and publish evidence can be written",
            onPass="publish_or_continue",
            onFail="park_pending_publish",
            message="Unsafe final placement uses the existing pending-publish park/drain flow.",
        )
    )
    return guards


def planned_verification_result(
    summary: str,
    policy: EffectiveDecisionPolicy,
    source: SourceMediaInfo,
    legacy_reason_code: str,
    guards: list[VerificationGuard],
) -> VerificationResult:
    size_check = planned_output_size_check(
        action=_size_check_action(policy),
        source_size_bytes=source.container.file_size_bytes or None,
        growth_tolerance_percent=_size_growth_tolerance_percent(policy, legacy_reason_code),
        applies=summary == "ENCODE",
    )
    return verification_result_from_size_check(size_check, guards=guards)


def _output_size_guard(
    summary: str,
    policy: EffectiveDecisionPolicy,
    source: SourceMediaInfo,
    legacy_reason_code: str,
) -> VerificationGuard | None:
    action = _size_check_action(policy)
    if summary != "ENCODE" or action == "disabled":
        return None
    enforcement = "ADVISORY" if action == "warn_only" else "HARD_BLOCK"
    return VerificationGuard(
        code="OUTPUT_SIZE_CHECK",
        name="Output Size Check",
        stage="POST_PROCESS",
        enforcement=enforcement,
        condition=(
            "actual output size is within "
            f"{_size_growth_tolerance_percent(policy, legacy_reason_code):g}% growth tolerance"
        ),
        onPass="continue_verification",
        onFail=_size_check_on_fail(action),
        message=_size_check_message(action, source),
    )


def _size_check_action(policy: EffectiveDecisionPolicy) -> OutputSizeCheckAction:
    return policy.output_size_check_action or "warn_only"


def _size_growth_tolerance_percent(policy: EffectiveDecisionPolicy, legacy_reason_code: str) -> float:
    reason = legacy_reason_code.strip().lower()
    if policy.routing_profile == "plex_direct_play" or reason in _COMPATIBILITY_SIZE_REASONS:
        return policy.compatibility_encode_growth_tolerance_percent
    return policy.quality_encode_growth_tolerance_percent


def _size_check_on_fail(action: OutputSizeCheckAction) -> str:
    if action == "block_publish":
        return "park_pending_publish"
    if action == "fail_job":
        return "fail_job"
    return "record_advisory_warning"


def _size_check_message(action: OutputSizeCheckAction, source: SourceMediaInfo) -> str:
    source_size = source.container.file_size_bytes
    size_text = f"source size {source_size} byte(s)" if source_size > 0 else "source size unknown"
    if action == "block_publish":
        return f"Output Size Check can block publish and park output with manifest evidence; {size_text}."
    if action == "fail_job":
        return f"Output Size Check can fail the job before publish; {size_text}."
    return f"Output Size Check warning records advisory evidence without blocking publish; {size_text}."


__all__ = [
    "finalize_decision",
    "planned_verification_result",
    "publish_requirements",
    "verification_guards",
    "verification_requirements",
]
