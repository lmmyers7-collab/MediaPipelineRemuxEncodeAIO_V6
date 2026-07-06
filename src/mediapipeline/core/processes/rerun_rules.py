"""Backend-owned CSV rerun remediation rule decisions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


RERUN_RULE_DECISION_SCHEMA_VERSION = "desktop_rerun_rule_decision.v1"

BAD_DOWNLOAD_FULL_RERUN = "bad_download_full_rerun"
LEGACY_PIPELINE_STANDARDIZE = "legacy_pipeline_standardize"
SUBTITLE_REMEDIATION = "subtitle_remediation"
AUDIO_LANGUAGE_REMEDIATION = "audio_language_remediation"
CONTAINER_CODEC_REMEDIATION = "container_codec_remediation"
MANUAL_REVIEW_REQUIRED = "manual_review_required"
BLOCKED_MISSING_RULE_INPUT = "blocked_missing_rule_input"

RERUN_RULE_IDS = (
    BAD_DOWNLOAD_FULL_RERUN,
    LEGACY_PIPELINE_STANDARDIZE,
    SUBTITLE_REMEDIATION,
    AUDIO_LANGUAGE_REMEDIATION,
    CONTAINER_CODEC_REMEDIATION,
    MANUAL_REVIEW_REQUIRED,
    BLOCKED_MISSING_RULE_INPUT,
)

RERUN_RULE_CSV_COLUMNS = (
    "rerun_rule_id",
    "rerun_rule_label",
    "rerun_rule_status",
    "rerun_rule_reason",
    "rerun_rule_destination_behavior",
    "rerun_rule_replacement_eligible",
    "rerun_rule_required_confirmations",
    "rerun_rule_runtime_options",
)

DEFAULT_ALLOWED_EXECUTION_MODES = ("one_at_a_time", "windowed", "batch_stage_all")
DEFAULT_DESTINATION_BEHAVIOR = "auto_replace_clean_else_pending_review"
RERUNNABLE_REMEDIATION_RULE_IDS = (
    SUBTITLE_REMEDIATION,
    AUDIO_LANGUAGE_REMEDIATION,
    CONTAINER_CODEC_REMEDIATION,
)

_RULE_LABELS = {
    BAD_DOWNLOAD_FULL_RERUN: "Bad Download Full Rerun",
    LEGACY_PIPELINE_STANDARDIZE: "Legacy Pipeline Standardize",
    SUBTITLE_REMEDIATION: "Subtitle Remediation",
    AUDIO_LANGUAGE_REMEDIATION: "Audio Language Remediation",
    CONTAINER_CODEC_REMEDIATION: "Container/Codec Remediation",
    MANUAL_REVIEW_REQUIRED: "Manual Review Required",
    BLOCKED_MISSING_RULE_INPUT: "Blocked: Missing Rule Input",
}

_BAD_DOWNLOAD_PATTERNS = (
    "bad_download",
    "bad-download",
    "download",
    "redownload",
    "re-download",
    "corrupt",
    "corruption",
    "truncated",
    "partial",
    "source_integrity",
    "source-integrity",
    "ffprobe",
    "probe_failed",
    "probe-failed",
    "unreadable",
    "zero_bytes",
    "zero-byte",
)
_SUBTITLE_PATTERNS = (
    "subtitle",
    "subtitles",
    "caption",
    "srt",
    "tx3g",
    "pgs",
    "bdpgs",
    "vobsub",
    "ass",
    "ssa",
    "ocr",
    "forced",
)
_AUDIO_PATTERNS = (
    "audio",
    "language",
    "lang",
    "commentary",
    "aac",
    "ac3",
    "eac3",
    "dts",
    "truehd",
    "atmos",
    "downmix",
    "channel",
)
_CONTAINER_CODEC_PATTERNS = (
    "container",
    "codec",
    "format",
    "video",
    "remux",
    "encode",
    "transcode",
    "h264",
    "h265",
    "hevc",
    "av1",
    "mpeg",
    "stream",
    "bitrate",
    "hdr",
)
_LEGACY_PATTERNS = (
    "legacy",
    "old_pipeline",
    "older_pipeline",
    "pipeline_version",
    "standardize",
    "rerun_pipeline",
    "needs_rerun",
    "current_spec",
)
_MANUAL_PATTERNS = (
    "manual",
    "operator",
    "manual_review",
    "manual-review",
    "review_required",
    "review-required",
    "unsafe",
    "ambiguous",
    "unknown",
)


@dataclass(frozen=True)
class RerunRuleDecision:
    rule_id: str
    label: str
    status: str
    severity: str
    reason: str
    allowed_execution_modes: tuple[str, ...]
    destination_behavior: str
    replacement_eligible: bool
    required_confirmations: tuple[str, ...]
    runtime_options: dict[str, Any]
    evidence: dict[str, Any]
    blocked_reasons: tuple[str, ...] = ()
    warning_reasons: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
            "rule_id": self.rule_id,
            "label": self.label,
            "status": self.status,
            "severity": self.severity,
            "reason": self.reason,
            "allowed_execution_modes": list(self.allowed_execution_modes),
            "destination_behavior": self.destination_behavior,
            "replacement_eligible": self.replacement_eligible,
            "required_confirmations": list(self.required_confirmations),
            "runtime_options": dict(self.runtime_options),
            "evidence": dict(self.evidence),
            "blocked_reasons": list(self.blocked_reasons),
            "warning_reasons": list(self.warning_reasons),
        }


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized(value: Any) -> str:
    return _clean_text(value).casefold().replace("-", "_").replace(" ", "_")


def _row_text(row: Mapping[str, Any], *keys: str) -> str:
    lowered = {str(key).casefold(): value for key, value in row.items()}
    for key in keys:
        text = _clean_text(lowered.get(key.casefold()))
        if text:
            return text
    return ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            items.extend(_string_list(item))
        return [item for item in items if item]
    if isinstance(value, Mapping):
        return [_clean_text(value.get("code") or value.get("issue_code") or value.get("reason") or json.dumps(dict(value), sort_keys=True))]
    text = _clean_text(value)
    if not text:
        return []
    return [item.strip() for item in text.replace(";", ",").replace("|", ",").split(",") if item.strip()]


def _issue_values(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "audit_issue_codes",
        "IssueCodes",
        "NonSidecarIssueCodes",
        "PrimaryIssueCode",
        "primary_issue_code",
        "effective_bucket",
        "EffectiveBucket",
        "priority_fix_level",
        "PriorityFixLevel",
        "notes",
    ):
        values.extend(_string_list(row.get(key)))
    return [value for value in values if value]


def _haystack(row: Mapping[str, Any]) -> str:
    values = _issue_values(row)
    return " ".join(values).casefold().replace("-", "_")


def _matched(haystack: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if pattern.casefold().replace("-", "_") in haystack]


def _review_bucket(row: Mapping[str, Any]) -> bool:
    bucket = _normalized(_row_text(row, "effective_bucket", "EffectiveBucket", "Bucket"))
    priority = _normalized(_row_text(row, "priority_fix_level", "PriorityFixLevel"))
    return bucket in {"review", "manual_review", "needs_review"} or priority in {"review", "manual_review"}


def _has_source_identity(row: Mapping[str, Any]) -> bool:
    return bool(_row_text(row, "source_identity_v2", "SourceIdentityV2"))


def _has_planned_final(row: Mapping[str, Any]) -> bool:
    return bool(_row_text(row, "plex_planned_path", "PlannedOutputPath", "planned_output_path", "final_output_path"))


def _base_evidence(
    row: Mapping[str, Any],
    *,
    source_path: str,
    matched_keywords: list[str],
    source_exists: bool | None,
    is_absolute_source: bool | None,
    valid_extension: bool | None,
    duplicate_source: bool,
) -> dict[str, Any]:
    return {
        "schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
        "issue_values": _issue_values(row),
        "effective_bucket": _row_text(row, "effective_bucket", "EffectiveBucket", "Bucket"),
        "primary_issue_code": _row_text(row, "primary_issue_code", "PrimaryIssueCode"),
        "media_kind": _row_text(row, "media_kind", "MediaKind", "MediaType"),
        "source_path_present": bool(source_path),
        "source_exists": source_exists,
        "source_is_absolute": is_absolute_source,
        "source_extension_valid": valid_extension,
        "source_identity_present": _has_source_identity(row),
        "planned_final_present": _has_planned_final(row),
        "duplicate_source": bool(duplicate_source),
        "matched_keywords": matched_keywords,
    }


def _decision(
    rule_id: str,
    *,
    status: str,
    severity: str,
    reason: str,
    evidence: dict[str, Any],
    destination_behavior: str = DEFAULT_DESTINATION_BEHAVIOR,
    replacement_eligible: bool = True,
    allowed_execution_modes: tuple[str, ...] = DEFAULT_ALLOWED_EXECUTION_MODES,
    required_confirmations: tuple[str, ...] = ("confirm_replace_final",),
    runtime_options: dict[str, Any] | None = None,
    blocked_reasons: tuple[str, ...] = (),
    warning_reasons: tuple[str, ...] = (),
) -> RerunRuleDecision:
    options = {
        "rule_id": rule_id,
        "destination_behavior": destination_behavior,
        "replacement_eligible": replacement_eligible,
    }
    if runtime_options:
        options.update(runtime_options)
    return RerunRuleDecision(
        rule_id=rule_id,
        label=_RULE_LABELS[rule_id],
        status=status,
        severity=severity,
        reason=reason,
        allowed_execution_modes=allowed_execution_modes,
        destination_behavior=destination_behavior,
        replacement_eligible=replacement_eligible,
        required_confirmations=required_confirmations,
        runtime_options=options,
        evidence=evidence,
        blocked_reasons=blocked_reasons,
        warning_reasons=warning_reasons,
    )


def _blocked(
    rule_id: str,
    *,
    reason: str,
    evidence: dict[str, Any],
    code: str,
) -> RerunRuleDecision:
    return _decision(
        rule_id,
        status="blocked",
        severity="error",
        reason=reason,
        evidence=evidence,
        destination_behavior="blocked_manual_review",
        replacement_eligible=False,
        allowed_execution_modes=(),
        required_confirmations=(),
        blocked_reasons=(code,),
    )


def _ready_remediation(
    rule_id: str,
    *,
    reason: str,
    evidence: dict[str, Any],
    review_bucket: bool,
) -> RerunRuleDecision:
    if review_bucket:
        evidence = dict(evidence)
        evidence["review_bucket_present"] = True
        reason = (
            f"{reason} Audit review bucket is preserved as evidence; "
            "this backend remediation rule remains runnable."
        )
    return _decision(
        rule_id,
        status="ready",
        severity="ok",
        reason=reason,
        evidence=evidence,
    )


def classify_rerun_rule(
    row: Mapping[str, Any],
    *,
    source_path: str = "",
    source_exists: bool | None = None,
    is_absolute_source: bool | None = None,
    valid_extension: bool | None = None,
    duplicate_source: bool = False,
) -> RerunRuleDecision:
    """Classify a CSV rerun row into a backend-owned remediation policy."""

    source = _clean_text(source_path or _row_text(row, "source_path", "Path", "SourcePath"))
    text = _haystack(row)

    if not source:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=[],
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _blocked(
            BLOCKED_MISSING_RULE_INPUT,
            reason="CSV rerun rule selection requires an absolute source_path.",
            evidence=evidence,
            code="rule blocked: missing source_path",
        )
    if is_absolute_source is False:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=[],
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _blocked(
            BLOCKED_MISSING_RULE_INPUT,
            reason="CSV rerun rule selection requires an absolute source_path.",
            evidence=evidence,
            code="rule blocked: relative source_path",
        )
    if source_exists is False:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=[],
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _blocked(
            BLOCKED_MISSING_RULE_INPUT,
            reason="CSV rerun rule selection requires the source file to be present.",
            evidence=evidence,
            code="rule blocked: source file not found",
        )
    if valid_extension is False:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=[],
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _blocked(
            BLOCKED_MISSING_RULE_INPUT,
            reason="CSV rerun rule selection requires a configured media file extension.",
            evidence=evidence,
            code="rule blocked: invalid media extension",
        )

    bad_download = _matched(text, _BAD_DOWNLOAD_PATTERNS)
    if bad_download:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=bad_download,
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _blocked(
            BAD_DOWNLOAD_FULL_RERUN,
            reason="Audit evidence indicates source acquisition or probe integrity risk; backend requires manual source review before rerun.",
            evidence=evidence,
            code="rule blocked: bad download/source integrity requires manual review",
        )

    review_warning = _review_bucket(row)
    subtitle = _matched(text, _SUBTITLE_PATTERNS)
    if subtitle:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=subtitle,
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _ready_remediation(
            SUBTITLE_REMEDIATION,
            reason="Issue evidence is subtitle-focused; rerun uses backend subtitle policy and normal clean-return destination handling.",
            evidence=evidence,
            review_bucket=review_warning,
        )

    audio = _matched(text, _AUDIO_PATTERNS)
    if audio:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=audio,
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _ready_remediation(
            AUDIO_LANGUAGE_REMEDIATION,
            reason="Issue evidence is audio or language focused; rerun uses backend audio/language policy and normal clean-return destination handling.",
            evidence=evidence,
            review_bucket=review_warning,
        )

    container = _matched(text, _CONTAINER_CODEC_PATTERNS)
    if container:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=container,
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _ready_remediation(
            CONTAINER_CODEC_REMEDIATION,
            reason="Issue evidence is container, codec, or video focused; rerun uses backend remux/encode policy and normal clean-return destination handling.",
            evidence=evidence,
            review_bucket=review_warning,
        )

    manual = _matched(text, _MANUAL_PATTERNS)
    if manual or review_warning:
        evidence = _base_evidence(
            row,
            source_path=source,
            matched_keywords=manual or ["review_bucket"],
            source_exists=source_exists,
            is_absolute_source=is_absolute_source,
            valid_extension=valid_extension,
            duplicate_source=duplicate_source,
        )
        return _blocked(
            MANUAL_REVIEW_REQUIRED,
            reason="Audit metadata is manual, ambiguous, or review-only; backend blocks automatic CSV rerun until an operator resolves the row.",
            evidence=evidence,
            code="rule blocked: manual review required",
        )

    legacy = _matched(text, _LEGACY_PATTERNS)
    evidence = _base_evidence(
        row,
        source_path=source,
        matched_keywords=legacy,
        source_exists=source_exists,
        is_absolute_source=is_absolute_source,
        valid_extension=valid_extension,
        duplicate_source=duplicate_source,
    )
    return _decision(
        LEGACY_PIPELINE_STANDARDIZE,
        status="ready",
        severity="ok",
        reason="No narrower remediation rule matched; backend uses the standard legacy/current-spec rerun policy.",
        evidence=evidence,
    )


def rerun_rule_csv_values(decision: RerunRuleDecision) -> dict[str, str]:
    return {
        "rerun_rule_id": decision.rule_id,
        "rerun_rule_label": decision.label,
        "rerun_rule_status": decision.status,
        "rerun_rule_reason": decision.reason,
        "rerun_rule_destination_behavior": decision.destination_behavior,
        "rerun_rule_replacement_eligible": "true" if decision.replacement_eligible else "false",
        "rerun_rule_required_confirmations": ", ".join(decision.required_confirmations),
        "rerun_rule_runtime_options": json.dumps(decision.runtime_options, sort_keys=True),
    }


def _explicit_decision(row: Mapping[str, Any]) -> RerunRuleDecision | None:
    rule_id = _normalized(_row_text(row, "rerun_rule_id", "rule_id"))
    if rule_id not in RERUN_RULE_IDS:
        return None
    status = _normalized(_row_text(row, "rerun_rule_status", "rule_status") or "ready")
    if status not in {"ready", "warning", "blocked"}:
        status = "ready"
    severity = "error" if status == "blocked" else "warning" if status == "warning" else "ok"
    replacement_text = _normalized(_row_text(row, "rerun_rule_replacement_eligible", "replacement_eligible"))
    replacement_eligible = replacement_text not in {"false", "0", "no", "blocked"}
    reason = _row_text(row, "rerun_rule_reason", "rule_reason") or "CSV rerun rule evidence was supplied by the backend."
    if (
        status == "warning"
        and replacement_eligible
        and rule_id in RERUNNABLE_REMEDIATION_RULE_IDS
        and "audit bucket requests operator review" in reason.casefold()
    ):
        status = "ready"
        severity = "ok"
        reason = (
            reason.replace(" Audit bucket requests operator review before launch scope is finalized.", "")
            + " Audit review bucket is preserved as evidence; this backend remediation rule remains runnable."
        )
    destination_behavior = _row_text(row, "rerun_rule_destination_behavior", "destination_behavior") or DEFAULT_DESTINATION_BEHAVIOR
    confirmations = tuple(_string_list(_row_text(row, "rerun_rule_required_confirmations", "required_confirmations")))
    runtime_options: dict[str, Any] = {
        "rule_id": rule_id,
        "destination_behavior": destination_behavior,
        "replacement_eligible": replacement_eligible,
    }
    raw_options = _row_text(row, "rerun_rule_runtime_options", "runtime_options")
    if raw_options:
        try:
            parsed = json.loads(raw_options)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, Mapping):
            runtime_options.update(dict(parsed))
    evidence = {
        "schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
        "explicit_rule_fields": True,
        "issue_values": _issue_values(row),
        "effective_bucket": _row_text(row, "effective_bucket", "EffectiveBucket", "Bucket"),
        "primary_issue_code": _row_text(row, "primary_issue_code", "PrimaryIssueCode"),
    }
    return RerunRuleDecision(
        rule_id=rule_id,
        label=_row_text(row, "rerun_rule_label", "rule_label") or _RULE_LABELS[rule_id],
        status=status,
        severity=severity,
        reason=reason,
        allowed_execution_modes=DEFAULT_ALLOWED_EXECUTION_MODES if status != "blocked" else (),
        destination_behavior=destination_behavior,
        replacement_eligible=replacement_eligible,
        required_confirmations=confirmations if confirmations else (("confirm_replace_final",) if replacement_eligible else ()),
        runtime_options=runtime_options,
        evidence=evidence,
        blocked_reasons=(f"rule blocked: {reason}",) if status == "blocked" else (),
        warning_reasons=(f"rule warning: {reason}",) if status == "warning" else (),
    )


def rerun_rule_decision_from_mapping(row: Mapping[str, Any]) -> RerunRuleDecision:
    return _explicit_decision(row) or classify_rerun_rule(row)


def rerun_rule_counts(rows: list[RerunRuleDecision]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in rows:
        counts[decision.rule_id] = counts.get(decision.rule_id, 0) + 1
    return dict(sorted(counts.items()))


__all__ = [
    "AUDIO_LANGUAGE_REMEDIATION",
    "BAD_DOWNLOAD_FULL_RERUN",
    "BLOCKED_MISSING_RULE_INPUT",
    "CONTAINER_CODEC_REMEDIATION",
    "DEFAULT_DESTINATION_BEHAVIOR",
    "LEGACY_PIPELINE_STANDARDIZE",
    "MANUAL_REVIEW_REQUIRED",
    "RERUN_RULE_CSV_COLUMNS",
    "RERUN_RULE_DECISION_SCHEMA_VERSION",
    "RERUN_RULE_IDS",
    "RerunRuleDecision",
    "SUBTITLE_REMEDIATION",
    "classify_rerun_rule",
    "rerun_rule_counts",
    "rerun_rule_csv_values",
    "rerun_rule_decision_from_mapping",
]
