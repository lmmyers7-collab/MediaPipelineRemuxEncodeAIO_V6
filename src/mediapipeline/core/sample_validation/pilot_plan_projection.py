from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .readiness import SAMPLE_VALIDATION_ACCEPTANCE_CHECKS
from .worksheet import _sample_set_worksheet_samples


SAMPLE_VALIDATION_SAMPLE_SET_GUIDE_SCHEMA = "desktop_real_media_sample_set_guide.v1"
SAMPLE_VALIDATION_PILOT_PLAN_SCHEMA = "desktop_real_media_pilot_plan.v1"
SAMPLE_VALIDATION_EXECUTION_CHECKLIST_SCHEMA = "desktop_real_media_execution_checklist.v1"
SAMPLE_VALIDATION_CUTOVER_GATE_SCHEMA = "desktop_webview_cutover_gate.v1"
SAMPLE_VALIDATION_PILOT_RUNBOOK_SCHEMA = "desktop_real_media_pilot_runbook.v1"
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600
SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "category_key": "h264-remux-safe",
        "category": "H.264 remux/direct-play copy",
        "required": True,
        "evidence_goal": "A small H.264/AVC source that should copy/remux without video encode and without output growth.",
        "operator_action": "Validate route reason, completed output, sidecar/manifest, size posture, and Plex direct-play playback.",
        "owner_pages": ("Home", "Queue", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "subtitle-srt-generation",
        "category": "Preferred-language subtitle to SRT",
        "required": True,
        "evidence_goal": "A preferred-language ASS/TX3G/BDPGS subtitle case that should add SRT while preserving originals unless settings say otherwise.",
        "operator_action": "Validate subtitle conversion result, retained original subtitle tracks, diagnostics evidence, and manual-review behavior on failure.",
        "owner_pages": ("Home", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "audio-routing",
        "category": "Audio routing/default language",
        "required": True,
        "evidence_goal": "A source with meaningful audio-selection risk, such as multiple languages, multichannel audio, or passthrough/downmix expectations.",
        "operator_action": "Validate default language, passthrough/transcode decision, channel layout, and Plex playback behavior.",
        "owner_pages": ("Home", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "encode-size-policy",
        "category": "Encode and size policy",
        "required": True,
        "evidence_goal": "A source that must encode or is likely to trigger output-growth review, route policy, or size-limit guidance.",
        "operator_action": "Validate encode reason, output-size ratio, quality posture, sidecar route metadata, and any manual review threshold.",
        "owner_pages": ("Home", "Queue", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "deferred-publish",
        "category": "Deferred publish/final placement",
        "required": False,
        "evidence_goal": "A sample that proves final output placement or Pending Publish parking/drain posture when upload-constrained publishing is enabled.",
        "operator_action": "Validate pending manifest, parked/final output, sidecar/manifest consistency, and drain visibility without starting network mutation from WebView.",
        "owner_pages": ("Home", "Completed", "Pending Publish", "Diagnostics"),
    },
)
SAMPLE_VALIDATION_SAMPLE_CATEGORY_KEYS = {
    str(category["category_key"]) for category in SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES
}



def _sample_set_current_accepted_records(
    records: list[Mapping[str, Any]],
    reconciliation: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    current_ids = {
        _clean_text(row.get("record_id"))
        for row in reconciliation.get("rows", [])
        if isinstance(row, Mapping)
        and _clean_text(row.get("status")).casefold() == "current"
        and _clean_text(row.get("operator_decision")).casefold() == "accepted"
    }
    return [
        record
        for record in records
        if _clean_text(record.get("operator_decision")).casefold() == "accepted"
        and _clean_text(record.get("record_id")) in current_ids
    ]


def _pilot_status_from_row(row: Mapping[str, Any], *, missing_status: str) -> str:
    severity = _clean_text(row.get("severity")).casefold()
    status = _clean_text(row.get("status")).casefold()
    if severity == "error" or status == "unreadable":
        return "blocked"
    if status == "ready":
        return "ready"
    if status in {"review", "empty"} or severity == "warning":
        return "review"
    if status in {"missing", "not-started"}:
        return missing_status
    return status or missing_status


def _pilot_plan_row(stage: str, status: str, evidence: str, operator_action: str, *, required: bool = True) -> dict[str, Any]:
    severity = "error" if status == "blocked" else "warning" if status not in {"ready", "manual"} else "info"
    return {
        "stage": stage,
        "status": status,
        "severity": severity,
        "required": required,
        "evidence": evidence,
        "operator_action": operator_action,
    }


def _pilot_execution_row(
    phase: str,
    check: str,
    stage_row: Mapping[str, Any],
    owner_page: str,
    backend_evidence: str,
    operator_proof: str,
    unsafe_if_ignored: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    status = _clean_text(stage_row.get("status")) or "unknown"
    severity = _clean_text(stage_row.get("severity")) or ("error" if status == "blocked" else "warning")
    evidence = _clean_text(stage_row.get("evidence")) or backend_evidence
    return {
        "phase": phase,
        "check": check,
        "status": status,
        "severity": severity,
        "required": required,
        "owner_page": owner_page,
        "backend_evidence": backend_evidence,
        "current_evidence": evidence,
        "operator_proof": operator_proof,
        "safe_next_action": _clean_text(stage_row.get("operator_action")) or operator_proof,
        "unsafe_if_ignored": unsafe_if_ignored,
        "guardrail": (
            "Read-only execution checklist. It cannot launch, accept, repair, publish, rename, rewrite manifests, save settings, "
            "or touch source/output/scratch media."
        ),
    }


def _cutover_gate_row(
    checkpoint: str,
    status: str,
    evidence: str,
    safe_next_action: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    severity = "error" if status == "blocked" else "warning" if status != "ready" else "info"
    return {
        "checkpoint": checkpoint,
        "status": status,
        "severity": severity,
        "required": required,
        "evidence": evidence,
        "safe_next_action": safe_next_action,
        "guardrail": "Read-only cutover-gate evidence; backend-owned workflow state remains authoritative.",
    }


def _sample_set_guide_row(
    category: Mapping[str, Any],
    worksheet_samples: list[Mapping[str, Any]],
    accepted_records: list[Mapping[str, Any]],
    current_accepted_records: list[Mapping[str, Any]],
    reconciliation_by_id: Mapping[str, Mapping[str, Any]],
    *,
    blocked: bool,
    current_required_checks_complete: bool,
    current_recommended_checks_complete: bool,
) -> dict[str, Any]:
    category_key = _clean_text(category.get("category_key"))
    matching_samples = [
        sample
        for sample in worksheet_samples
        if _sample_set_category_matches(category_key, _clean_text(sample.get("match_text"), max_chars=2000))
    ]
    accepted_matching_records = [
        record
        for record in accepted_records
        if _sample_record_matches_category(category_key, record)
    ]
    matching_records = [
        record
        for record in current_accepted_records
        if _sample_record_matches_category(category_key, record)
    ]
    stale_record_count = 0
    review_record_count = 0
    for record in accepted_matching_records:
        reconciliation = reconciliation_by_id.get(_clean_text(record.get("record_id")), {})
        status = _clean_text(reconciliation.get("status")).casefold()
        if status == "stale":
            stale_record_count += 1
        elif status and status != "current":
            review_record_count += 1
        elif not status:
            review_record_count += 1
    if blocked:
        status = "blocked"
        severity = "error"
        safe_next_action = "Resolve blocked backend evidence before using this sample category."
    elif matching_records and current_required_checks_complete and (current_recommended_checks_complete or category_key == "h264-remux-safe"):
        status = "ready"
        severity = "info"
        safe_next_action = "Keep this category in the regression set and rerun it after route, subtitle, audio, publish, or settings changes."
    elif accepted_matching_records:
        status = "review"
        severity = "warning"
        safe_next_action = "An accepted category record exists, but current backend reconciliation is not clean; re-check Queue, Completed, Pending Publish, and Diagnostics proof."
    elif matching_samples and current_accepted_records:
        status = "review"
        severity = "warning"
        safe_next_action = "Open the matching worksheet/sample and append or update an accepted validation record whose label or notes identify this category."
    elif matching_samples:
        status = "planned"
        severity = "warning"
        safe_next_action = "Run this planned worksheet sample through backend-owned Launch, then capture Queue, Completed, Diagnostics, playback, and size evidence."
    else:
        status = "needs-sample"
        severity = "warning" if category.get("required") else "info"
        safe_next_action = _clean_text(category.get("operator_action")) or "Add a representative sample for this category."
    sample_labels = _dedupe(
        [
            _clean_text(sample.get("source_leaf")) or _clean_text(sample.get("source_path"), max_chars=200)
            for sample in matching_samples
        ]
    )[:3]
    record_labels = _dedupe(
        [
            _clean_text(record.get("sample_label")) or _safe_leaf(_clean_text(record.get("source_path"), max_chars=2000))
            for record in accepted_matching_records
        ]
    )[:3]
    evidence = (
        f"worksheet matches={len(matching_samples)}; accepted category records={len(accepted_matching_records)}; current accepted category records={len(matching_records)}; stale category records={stale_record_count}; review category records={review_record_count}; "
        f"generic current accepted records={len(current_accepted_records)}; required checks complete={_yes_no(current_required_checks_complete)}; "
        f"recommended checks complete={_yes_no(current_recommended_checks_complete)}"
    )
    return {
        "category_key": category_key,
        "category": _clean_text(category.get("category")),
        "status": status,
        "severity": severity,
        "required": bool(category.get("required")),
        "worksheet_sample_count": len(matching_samples),
        "accepted_record_match_count": len(accepted_matching_records),
        "current_record_match_count": len(matching_records),
        "stale_record_match_count": stale_record_count,
        "review_record_match_count": review_record_count,
        "generic_current_accepted_record_count": len(current_accepted_records),
        "sample_examples": sample_labels,
        "record_examples": record_labels,
        "evidence_goal": _clean_text(category.get("evidence_goal"), max_chars=1000),
        "evidence": evidence,
        "operator_action": _clean_text(category.get("operator_action"), max_chars=1000),
        "owner_pages": list(category.get("owner_pages") or ()),
        "safe_next_action": safe_next_action,
        "proof_boundary": (
            "Category status prefers explicit sample_category records. Older validation records without a category are matched only from label, path, notes, or evidence text."
        ),
        "guardrail": "Read-only sample-set row. It cannot launch work, mutate media, accept outputs, publish, rename, or save settings.",
    }


def _sample_set_record_text(record: Mapping[str, Any]) -> str:
    parts = [
        _clean_text(record.get("sample_category")),
        _clean_text(record.get("sample_label")),
        _clean_text(record.get("source_path"), max_chars=2000),
        _clean_text(record.get("output_path"), max_chars=2000),
        _clean_text(record.get("operator_notes"), max_chars=2000),
    ]
    evidence = record.get("evidence")
    if isinstance(evidence, Mapping):
        for values in evidence.values():
            if isinstance(values, list):
                for item in values[:5]:
                    if isinstance(item, Mapping):
                        parts.extend([_clean_text(item.get("field")), _clean_text(item.get("value"), max_chars=1000)])
    return " ".join(parts)


def _sample_record_matches_category(category_key: str, record: Mapping[str, Any]) -> bool:
    explicit = _clean_text(record.get("sample_category")).casefold()
    if explicit:
        return explicit == category_key.casefold()
    return _sample_set_category_matches(category_key, _sample_set_record_text(record))


def _sample_set_category_matches(category_key: str, raw_text: str) -> bool:
    text = f" {raw_text.casefold().replace('_', ' ').replace('-', ' ').replace('.', ' ')} "
    compact = raw_text.casefold()
    if category_key and category_key.casefold() in compact:
        return True
    if category_key == "h264-remux-safe":
        return any(token in text for token in (" h264 ", " h 264 ", " avc ")) and any(
            token in text for token in (" remux ", " copy ", " direct play ", " direct stream ")
        )
    if category_key == "subtitle-srt-generation":
        return (" subtitle " in text or any(token in text for token in (" ass ", " ssa ", " tx3g ", " pgs ", " bdpgs "))) and " srt " in text
    if category_key == "audio-routing":
        return any(token in text for token in (" audio ", " channel ", " passthrough ", " downmix ", " language ", " aac ", " ac3 ", " eac3 ", " flac "))
    if category_key == "encode-size-policy":
        return any(token in text for token in (" encode ", " transcode ", " hevc ", " x265 ", " nvenc ", " size ", " growth ", " bitrate "))
    if category_key == "deferred-publish":
        return any(token in text for token in (" deferred ", " pending ", " publish ", " drain ", " final placement ", " parked "))
    return False


def _safe_leaf(raw_path: str) -> str:
    text = _clean_text(raw_path, max_chars=2000)
    if not text:
        return ""
    try:
        return Path(text).name
    except (OSError, ValueError):
        return text


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return text[:max_chars]


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result

__all__ = (
    "_sample_set_current_accepted_records",
    "_pilot_status_from_row",
    "_pilot_plan_row",
    "_pilot_execution_row",
    "_cutover_gate_row",
    "_sample_set_guide_row",
    "_sample_set_record_text",
    "_sample_record_matches_category",
    "_sample_set_category_matches",
    "_safe_leaf",
    "_clean_text",
    "_yes_no",
    "_dedupe",
)
