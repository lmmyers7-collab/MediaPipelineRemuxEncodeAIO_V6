"""Read-only subtitle QA evidence assembled from existing backend rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from mediapipeline.contracts.subtitles import (
    SUBTITLE_QA_RESULT_SCHEMA_VERSION,
    SUBTITLE_SYNC_REVIEW_SCHEMA_VERSION,
    SUBTITLE_TRACK_INVENTORY_SCHEMA_VERSION,
)

SUBTITLE_QA_SUMMARY_SCHEMA_VERSION = "subtitle_qa_summary.v1"

_POSTURE_RANK = {
    "pass": 0,
    "not_checked": 1,
    "unknown": 2,
    "review": 3,
    "blocked": 4,
}
_SUBTITLE_TOKENS = (
    "subtitle",
    "subtitles",
    "srt",
    "ass",
    "ssa",
    "tx3g",
    "mov_text",
    "mov text",
    "pgs",
    "bdpgs",
    "hdmv_pgs_subtitle",
    "vobsub",
    "dvd_subtitle",
    "ocr",
    "sdh",
    "forced",
)
_FAILURE_TOKENS = (
    "blocked",
    "fail",
    "failure",
    "error",
    "missing",
    "invalid",
    "unusable",
    "unable",
    "bad",
    "empty",
    "tool_not_found",
    "tool missing",
    "ocr_missing",
    "negative",
    "overlap",
    "monotonic",
)
_IMAGE_SUBTITLE_CODECS = {
    "pgs",
    "bdpgs",
    "hdmv_pgs_subtitle",
    "vobsub",
    "dvd_subtitle",
}
_SUCCESS_STATUSES = {"", "ok", "pass", "passed", "success", "succeeded", "generated", "converted", "preserved"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _casefold(value: Any) -> str:
    return _text(value).casefold()


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return _casefold(value) in {"1", "true", "yes", "y", "on"}


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


def _mapping_value(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _unique_texts(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        key = text.casefold()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        text = _text(mapping.get(key))
        if text:
            return text
    return ""


def _first_number(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        number = _number_or_none(mapping.get(key))
        if number is not None:
            return number
    return None


def _decision_records(values: Any) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for item in _list_value(values):
        record = _mapping_value(item)
        if record:
            records.append(record)
    return records


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    folded = text.casefold()
    return any(token in folded for token in tokens)


def _subtitle_failure_texts(values: Iterable[Any]) -> list[str]:
    failures: list[str] = []
    for value in values:
        text = _text(value)
        folded = text.casefold()
        if text and _contains_any(folded, _SUBTITLE_TOKENS) and _contains_any(folded, _FAILURE_TOKENS):
            failures.append(text)
    return _unique_texts(failures)


def _best_posture(*postures: str) -> str:
    winner = "pass"
    for posture in postures:
        normalized = _casefold(posture) or "unknown"
        if _POSTURE_RANK.get(normalized, 2) > _POSTURE_RANK.get(winner, 0):
            winner = normalized
    return winner


def _safe_next_action(posture: str, scope: str) -> str:
    normalized = _casefold(posture)
    if normalized == "blocked":
        return "Route this item to review before trust, rerun, cleanup, pending-publish drain, or source/output file decisions."
    if normalized == "review":
        return "Inspect subtitle QA evidence in Queue, Completed, Diagnostics, and manual playback before accepting the output."
    if normalized == "unknown":
        return "Load backend subtitle inventory or Completed proof before using subtitle state in a trust decision."
    if normalized == "not_checked":
        return "Treat subtitle QA as incomplete until the backend run produces Completed subtitle evidence and playback is checked."
    if scope == "queue":
        return "Use Queue evidence only as pre-run triage; Completed and manual playback remain required before trust."
    return "Use this as supporting proof only; manual playback, subtitle, audio, and placement checks remain required."


def _manual_guardrail(scope: str) -> str:
    if scope == "queue":
        return "Mutation guardrail: Queue subtitle QA is read-only pre-run evidence and cannot launch, rewrite queue entries, convert subtitles, or touch media."
    return "Mutation guardrail: Completed subtitle QA reads existing backend metadata only; it cannot repair, rerun, OCR, sync, promote, rewrite sidecars, or touch media."


def _queue_inventory(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata_available = _bool_value(row.get("track_metadata_available"))
    track_count = _int_or_none(row.get("subtitle_track_count"))
    languages = _unique_texts(_list_value(row.get("subtitle_languages")))
    has_forced = _bool_value(row.get("has_forced_subtitles"))
    status = "not_loaded"
    if metadata_available:
        status = "present" if (track_count or 0) > 0 else "missing"
    return {
        "schema_version": SUBTITLE_TRACK_INVENTORY_SCHEMA_VERSION,
        "status": status,
        "track_metadata_available": metadata_available,
        "embedded_subtitle_count": track_count if metadata_available else None,
        "external_sidecar_count": _int_or_none(row.get("external_subtitle_count")),
        "subtitle_languages": languages,
        "has_forced_subtitles": has_forced,
        "default_subtitle_known": row.get("default_subtitle_index") not in (None, ""),
        "preferred_language_status": "not_checked",
        "preferred_language_reason": "Queue v1 does not load saved subtitle-language policy into this row.",
    }


def _queue_posture(row: Mapping[str, Any], inventory: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    blocked_fields = [
        row.get("blocked_reason_code"),
        row.get("blocked_reason"),
        row.get("runtime_outcome_error_code"),
        row.get("runtime_outcome_reason"),
        *(_list_value(row.get("runtime_check_codes"))),
        *(_list_value(row.get("runtime_check_notes"))),
        *(_list_value(row.get("review_flags"))),
    ]
    subtitle_blockers = _subtitle_failure_texts(blocked_fields)
    if subtitle_blockers:
        reasons.extend(f"Subtitle blocker signal: {item}" for item in subtitle_blockers[:4])
        return "blocked", reasons

    if not inventory.get("track_metadata_available"):
        reasons.append("Subtitle track inventory has not been loaded for this Queue row.")
        return "unknown", reasons

    count = _int_or_none(inventory.get("embedded_subtitle_count")) or 0
    languages = _list_value(inventory.get("subtitle_languages"))
    if count <= 0:
        reasons.append("No embedded subtitle streams are reported by the Queue inventory.")
        return "review", reasons
    if not languages:
        reasons.append("Subtitle streams are present but language tags are missing.")
        return "review", reasons
    if inventory.get("has_forced_subtitles"):
        reasons.append("Forced subtitle streams are present; playback/default handling needs review.")
        return "review", reasons
    reasons.append("Subtitle inventory is present, but SRT validity, conversion evidence, and sync are post-run checks.")
    return "not_checked", reasons


def build_queue_subtitle_qa(row: Mapping[str, Any]) -> dict[str, Any]:
    """Build a read-only QA packet for a Queue row."""
    inventory = _queue_inventory(row)
    posture, reasons = _queue_posture(row, inventory)
    summary = {
        "blocked": "Queue subtitle QA found a subtitle-related blocker.",
        "review": "Queue subtitle QA recommends review before launch/trust decisions.",
        "unknown": "Queue subtitle QA lacks loaded subtitle inventory.",
        "not_checked": "Queue subtitle inventory is present; post-run QA is still required.",
        "pass": "Queue subtitle evidence is coherent for pre-run triage.",
    }.get(posture, "Queue subtitle QA state is unknown.")
    return {
        "schema_version": SUBTITLE_QA_RESULT_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "scope": "queue",
        "posture": posture,
        "summary": summary,
        "reasons": reasons,
        "safe_next_action": _safe_next_action(posture, "queue"),
        "inventory": inventory,
        "policy_match": {
            "status": "not_checked",
            "preferred_languages_present": None,
            "reason": "Saved subtitle policy is not evaluated in Queue QA v1.",
        },
        "srt_validity": {
            "status": "not_checked",
            "reason": "Queue QA v1 does not parse or generate SRT files.",
        },
        "coverage": {
            "status": "not_checked",
            "reason": "Cue coverage is available only after generated subtitle evidence exists.",
        },
        "conversion_evidence": {
            "status": "not_checked",
            "sources": [],
            "failures": [],
            "reason": "Conversion/OCR evidence is post-run evidence.",
        },
        "sync_review": {
            "schema_version": SUBTITLE_SYNC_REVIEW_SCHEMA_VERSION,
            "status": "heuristic_only",
            "risk": "unknown",
            "reason": "Queue QA v1 does not run audio-derived sync estimation.",
        },
        "guardrail": _manual_guardrail("queue"),
    }


def _decision_source_codec(decision: Mapping[str, Any]) -> str:
    return _first_text(decision, "source_codec", "codec", "codec_name", "codec_tag_string").casefold()


def _decision_action(decision: Mapping[str, Any]) -> str:
    return _first_text(decision, "action", "decision", "status").casefold()


def _decision_language(decision: Mapping[str, Any]) -> str:
    return _first_text(decision, "language", "lang")


def _decision_cue_count(decision: Mapping[str, Any]) -> int | None:
    return _int_or_none(
        decision.get("cue_count")
        if "cue_count" in decision
        else decision.get("cues", decision.get("cue_total"))
    )


def _completed_inventory(row: Mapping[str, Any], decisions: list[Mapping[str, Any]]) -> dict[str, Any]:
    languages = _unique_texts(
        [
            *(_list_value(row.get("subtitle_languages"))),
            *(_decision_language(decision) for decision in decisions),
        ]
    )
    source_codecs = _unique_texts(_decision_source_codec(decision) for decision in decisions)
    actions = _unique_texts(_decision_action(decision) for decision in decisions)
    track_count = _int_or_none(row.get("subtitle_track_count"))
    if track_count is None:
        track_count = len(decisions) if decisions else _int_or_none(row.get("subtitle_decision_count"))
    status = "present" if track_count and track_count > 0 else "not_reported"
    return {
        "schema_version": SUBTITLE_TRACK_INVENTORY_SCHEMA_VERSION,
        "status": status,
        "track_metadata_available": bool(decisions or row.get("track_metadata_available")),
        "embedded_subtitle_count": track_count,
        "external_sidecar_count": _int_or_none(row.get("external_subtitle_count")),
        "subtitle_languages": languages,
        "source_codecs": source_codecs,
        "decision_actions": actions,
        "decision_count": len(decisions),
        "decision_preview": list(_list_value(row.get("subtitle_decision_preview")))[:5],
        "has_forced_subtitles": any(_bool_value(decision.get("is_forced") or decision.get("forced")) for decision in decisions)
        or _bool_value(row.get("has_forced_subtitles")),
        "has_sdh_subtitles": any(_bool_value(decision.get("is_sdh") or decision.get("sdh")) for decision in decisions),
        "default_subtitle_known": any(
            _bool_value(decision.get("is_default") or decision.get("source_is_default") or decision.get("default"))
            for decision in decisions
        ),
    }


def _completed_conversion_evidence(decisions: list[Mapping[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    sources: list[str] = []
    tools: list[str] = []
    output_paths: list[str] = []
    for decision in decisions:
        source_codec = _decision_source_codec(decision)
        action = _decision_action(decision)
        if source_codec:
            sources.append(source_codec)
        tool = _first_text(decision, "tool", "tool_name", "converter", "conversion_tool", "ocr_tool", "tool_path")
        if tool:
            tools.append(tool)
        output_path = _first_text(decision, "output_path", "srt_path", "path", "sidecar_path")
        if output_path:
            output_paths.append(output_path)
        status = _first_text(decision, "status", "conversion_status", "ocr_status")
        reason = _first_text(decision, "failure_reason", "error", "error_message", "reason", "route_reason")
        combined = " ".join([source_codec, action, status, reason])
        if _contains_any(combined, _SUBTITLE_TOKENS) and _contains_any(combined, _FAILURE_TOKENS):
            failures.append(reason or status or combined)
        cue_count = _decision_cue_count(decision)
        successful_status = bool(status) and _casefold(status) in _SUCCESS_STATUSES
        has_conversion_evidence = bool(tool or output_path or (cue_count is not None and cue_count > 0) or successful_status)
        if source_codec in _IMAGE_SUBTITLE_CODECS and action not in {"preserve", "copy", "passthrough"} and not has_conversion_evidence:
            warnings.append("Image-based subtitle source has no OCR/conversion evidence in the completed decision record.")
    status = "not_checked"
    reason = "No subtitle conversion decision records are present."
    if failures:
        status = "blocked" if any(_contains_any(item, ("missing", "fail", "error", "invalid", "unable")) for item in failures) else "review"
        reason = "Subtitle conversion/OCR failure evidence is present."
    elif warnings:
        status = "review"
        reason = "Subtitle conversion/OCR evidence is incomplete."
    elif decisions:
        status = "pass" if sources or output_paths or tools else "not_checked"
        reason = "Subtitle conversion decision records are present." if status == "pass" else "Subtitle decisions lack conversion fields."
    return {
        "status": status,
        "sources": _unique_texts(sources),
        "tools": _unique_texts(tools),
        "output_paths": _unique_texts(output_paths)[:5],
        "failures": _unique_texts(failures),
        "warnings": _unique_texts(warnings),
        "reason": reason,
    }, failures + warnings


def _completed_srt_validity(decisions: list[Mapping[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    cue_counts = [_decision_cue_count(decision) for decision in decisions]
    known_counts = [count for count in cue_counts if count is not None]
    failures: list[str] = []
    status = "not_checked"
    reason = "No generated SRT cue evidence is present."
    if known_counts:
        zero_count = [count for count in known_counts if count <= 0]
        if zero_count:
            status = "blocked"
            reason = "Generated subtitle cue evidence reports empty cues."
            failures.append("Generated subtitle cue count is zero.")
        else:
            status = "pass"
            reason = "Generated subtitle cue counts are present and non-empty."
    elif decisions:
        status = "not_checked"
        reason = "Subtitle decisions are present, but cue validity counters are not in the manifest."
    return {
        "status": status,
        "utf8": None,
        "non_empty_cues": all(count > 0 for count in known_counts) if known_counts else None,
        "monotonic_timestamps": None,
        "negative_time_count": None,
        "overlap_count": None,
        "cue_count": max(known_counts) if known_counts else None,
        "reason": reason,
    }, failures


def _completed_coverage(decisions: list[Mapping[str, Any]], row: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    first_cue = None
    last_cue = None
    duration = None
    for decision in decisions:
        first_cue = first_cue if first_cue is not None else _first_number(decision, "first_cue_seconds", "first_cue_start_seconds")
        last_cue = last_cue if last_cue is not None else _first_number(decision, "last_cue_seconds", "last_cue_end_seconds")
        duration = duration if duration is not None else _first_number(decision, "duration_seconds", "media_duration_seconds")
    duration = duration if duration is not None else _first_number(row, "duration_seconds", "media_duration_seconds")
    cue_counts = [count for count in (_decision_cue_count(decision) for decision in decisions) if count is not None]
    status = "not_checked"
    reason = "Subtitle cue coverage counters are not present."
    if first_cue is not None or last_cue is not None or duration is not None or cue_counts:
        status = "pass"
        reason = "Available cue coverage heuristics did not flag a risk."
        if first_cue is not None and first_cue >= 600:
            failures.append(f"First cue starts late at {first_cue:.0f}s.")
        if duration is not None and last_cue is not None and duration - last_cue >= 300:
            failures.append(f"Last cue ends {duration - last_cue:.0f}s before media end.")
        if duration is not None and duration >= 1800 and cue_counts and max(cue_counts) < 50:
            failures.append("Cue count is extremely low for long-form content.")
        if failures:
            status = "review"
            reason = "Cue coverage heuristics flagged possible offset or wrong-release risk."
    return {
        "status": status,
        "first_cue_seconds": first_cue,
        "last_cue_seconds": last_cue,
        "duration_seconds": duration,
        "cue_count": max(cue_counts) if cue_counts else None,
        "failures": failures,
        "reason": reason,
    }, failures


def _completed_policy_match(inventory: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    languages = {_casefold(value) for value in _list_value(inventory.get("subtitle_languages"))}
    reasons: list[str] = []
    english_present = any(value in {"eng", "en", "english"} for value in languages)
    status = "unknown"
    if languages:
        status = "pass" if english_present else "review"
        if not english_present:
            reasons.append("No English subtitle language tag is present in Completed subtitle decisions.")
    else:
        reasons.append("Subtitle decision language evidence is missing.")
    if inventory.get("has_forced_subtitles"):
        status = _best_posture(status, "review")
        reasons.append("Forced subtitle evidence is present and should be playback-checked.")
    return {
        "status": status,
        "preferred_languages_present": english_present if languages else None,
        "language_hint": "english-present" if english_present else "english-not-visible" if languages else "not_reported",
        "forced_handling_status": "review" if inventory.get("has_forced_subtitles") else "not_flagged",
        "sdh_status": "present" if inventory.get("has_sdh_subtitles") else "not_flagged",
        "reason": "Saved policy evaluation is not loaded in v1; English is reported as a compatibility hint only.",
    }, reasons


def _completed_sync_review(row: Mapping[str, Any], coverage: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    text_fields = [
        row.get("runtime_outcome_error_code"),
        row.get("runtime_outcome_reason"),
        row.get("route_reason_code"),
        row.get("route_reason"),
        *(_list_value(row.get("review_flags"))),
    ]
    sync_failures = [
        _text(item)
        for item in text_fields
        if _contains_any(_text(item), ("subtitle", "srt", "sync", "offset", "timing")) and _contains_any(_text(item), _FAILURE_TOKENS)
    ]
    failures.extend(_unique_texts(sync_failures))
    coverage_status = _casefold(coverage.get("status"))
    if coverage_status == "review":
        failures.extend(_list_value(coverage.get("failures")))
    status = "heuristic_only"
    risk = "low"
    reason = "No audio-derived subtitle sync estimation was run; only metadata heuristics are available."
    if failures:
        risk = "review"
        reason = "Subtitle sync/coverage heuristics flagged review evidence."
    elif coverage_status == "not_checked":
        risk = "unknown"
    return {
        "schema_version": SUBTITLE_SYNC_REVIEW_SCHEMA_VERSION,
        "status": status,
        "risk": risk,
        "failures": _unique_texts(failures),
        "reason": reason,
    }, failures


def build_completed_subtitle_qa(
    row: Mapping[str, Any],
    *,
    subtitle_decisions: Iterable[Mapping[str, Any]] | None = None,
    record_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only QA packet for a Completed manifest row."""
    payload = record_payload or {}
    decisions = _decision_records(subtitle_decisions if subtitle_decisions is not None else payload.get("subtitle_decisions"))
    inventory = _completed_inventory(row, decisions)
    policy_match, policy_reasons = _completed_policy_match(inventory)
    srt_validity, srt_failures = _completed_srt_validity(decisions)
    coverage, coverage_failures = _completed_coverage(decisions, row)
    conversion, conversion_failures = _completed_conversion_evidence(decisions)
    sync_review, sync_failures = _completed_sync_review(row, coverage)
    row_failures = _subtitle_failure_texts(
        [
            row.get("runtime_outcome_error_code"),
            row.get("runtime_outcome_reason"),
            row.get("validation_failure_reason"),
            row.get("operator_guidance"),
            row.get("primary_concern"),
            *(_list_value(row.get("review_flags"))),
            *(_list_value(row.get("consistency_issues"))),
        ]
    )
    posture = _best_posture(
        _casefold(policy_match.get("status")),
        _casefold(srt_validity.get("status")),
        _casefold(coverage.get("status")),
        _casefold(conversion.get("status")),
        "review" if _casefold(sync_review.get("risk")) == "review" else "pass",
        "blocked" if row_failures else "pass",
    )
    if not decisions and posture == "pass":
        posture = "unknown"
    if _casefold(row.get("output_exists")) == "false":
        posture = _best_posture(posture, "blocked")
        row_failures.append("Completed output is missing, so subtitle proof cannot be trusted.")
    reasons = _unique_texts(
        [
            *policy_reasons,
            *srt_failures,
            *coverage_failures,
            *conversion_failures,
            *sync_failures,
            *row_failures,
        ]
    )
    if not reasons:
        if decisions:
            reasons.append("Completed subtitle decision evidence is present.")
        else:
            reasons.append("No completed subtitle decision evidence is present.")
    if posture == "pass" and _casefold(srt_validity.get("status")) == "not_checked":
        posture = "not_checked"
    summary = {
        "blocked": "Completed subtitle QA found blocking subtitle evidence.",
        "review": "Completed subtitle QA needs operator review before trust.",
        "unknown": "Completed subtitle QA lacks enough subtitle evidence.",
        "not_checked": "Completed subtitle QA has decisions, but SRT validity/sync evidence is incomplete.",
        "pass": "Completed subtitle QA evidence is coherent-looking.",
    }.get(posture, "Completed subtitle QA state is unknown.")
    return {
        "schema_version": SUBTITLE_QA_RESULT_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "scope": "completed",
        "posture": posture,
        "summary": summary,
        "reasons": reasons,
        "safe_next_action": _safe_next_action(posture, "completed"),
        "inventory": inventory,
        "policy_match": policy_match,
        "srt_validity": srt_validity,
        "coverage": coverage,
        "conversion_evidence": conversion,
        "sync_review": sync_review,
        "guardrail": _manual_guardrail("completed"),
    }


def _subtitle_qa_for_row(scope: str, row: Mapping[str, Any]) -> Mapping[str, Any]:
    qa = row.get("subtitle_qa")
    if isinstance(qa, Mapping):
        return qa
    return build_queue_subtitle_qa(row) if scope == "queue" else build_completed_subtitle_qa(row)


def _summary_entry(scope: str, row: Mapping[str, Any]) -> dict[str, Any]:
    qa = dict(_subtitle_qa_for_row(scope, row))
    return {
        "schema_version": SUBTITLE_QA_RESULT_SCHEMA_VERSION,
        "scope": scope,
        "row_key": _text(row.get("row_key")),
        "display_name": _first_text(row, "display_name", "lookup_title", "output_file", "relative_path", "source_path", "output_path"),
        "source_path": _text(row.get("source_path")),
        "output_path": _text(row.get("output_path")),
        "posture": _casefold(qa.get("posture")) or "unknown",
        "summary": _text(qa.get("summary")),
        "safe_next_action": _text(qa.get("safe_next_action")),
        "subtitle_qa": qa,
    }


def _count_postures(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in _POSTURE_RANK}
    for row in rows:
        posture = _casefold(row.get("posture")) or "unknown"
        counts[posture if posture in counts else "unknown"] += 1
    return counts


def _bounded_limit(value: Any, *, default: int = 250, maximum: int = 500) -> int:
    try:
        number = int(value or default)
    except (TypeError, ValueError):
        number = default
    return max(1, min(maximum, number))


def subtitle_qa_summary_from_payloads(
    queue_payload: Mapping[str, Any] | None,
    completed_payload: Mapping[str, Any] | None,
    *,
    limit: Any = 250,
) -> dict[str, Any]:
    """Combine Queue and Completed row QA into a read-only summary payload."""
    max_rows = _bounded_limit(limit)
    rows: list[dict[str, Any]] = []
    for scope, payload in (("queue", queue_payload or {}), ("completed", completed_payload or {})):
        for row in _list_value(payload.get("rows")):
            row_map = _mapping_value(row)
            if row_map:
                rows.append(_summary_entry(scope, row_map))
    rows.sort(key=lambda item: (_POSTURE_RANK.get(_casefold(item.get("posture")), 2) * -1, item.get("scope", ""), item.get("display_name", "")))
    limited = rows[:max_rows]
    return {
        "schema_version": SUBTITLE_QA_SUMMARY_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "status": "complete",
        "rows_loaded": len(rows),
        "rows_returned": len(limited),
        "counts": _count_postures(rows),
        "rows": limited,
        "guardrail": "Subtitle QA summary is read-only; it cannot launch work, run OCR/sync tools, repair subtitles, rewrite manifests, publish, drain, or touch media.",
    }


def _row_matches_id(row: Mapping[str, Any], item_id: str) -> bool:
    needle = item_id.casefold()
    values = [
        row.get("row_key"),
        row.get("source_path"),
        row.get("output_path"),
        row.get("sidecar_path"),
        row.get("display_name"),
        row.get("relative_path"),
        row.get("output_file"),
    ]
    return any(_text(value).casefold() == needle for value in values if _text(value))


def subtitle_qa_item_from_payloads(
    queue_payload: Mapping[str, Any] | None,
    completed_payload: Mapping[str, Any] | None,
    item_id: Any,
    *,
    limit: Any = 250,
) -> dict[str, Any]:
    """Return the QA packet for one loaded Queue/Completed row."""
    target = _text(item_id)
    if not target:
        return {
            "schema_version": SUBTITLE_QA_RESULT_SCHEMA_VERSION,
            "evidence_authority": "backend",
            "scope": "unknown",
            "posture": "blocked",
            "summary": "'id' is required to preview a subtitle QA item.",
            "reasons": ["Missing id."],
            "safe_next_action": "Pass a loaded Queue or Completed row_key, source_path, or output_path.",
            "guardrail": "No filesystem path was opened or probed.",
        }
    for scope, payload in (("queue", queue_payload or {}), ("completed", completed_payload or {})):
        for row in _list_value(payload.get("rows"))[: _bounded_limit(limit)]:
            row_map = _mapping_value(row)
            if row_map and _row_matches_id(row_map, target):
                entry = _summary_entry(scope, row_map)
                result = dict(entry["subtitle_qa"])
                result.update(
                    {
                        "status": "matched",
                        "scope": scope,
                        "row_key": entry["row_key"],
                        "display_name": entry["display_name"],
                        "source_path": entry["source_path"],
                        "output_path": entry["output_path"],
                    }
                )
                return result
    return {
        "schema_version": SUBTITLE_QA_RESULT_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "scope": "unknown",
        "posture": "unknown",
        "summary": "No loaded Queue or Completed row matched the requested subtitle QA id.",
        "reasons": ["The preview route only matches rows already loaded by backend Queue/Completed payloads."],
        "safe_next_action": "Refresh Queue/Completed evidence and retry with the row_key shown by the backend.",
        "guardrail": "The item lookup did not open, probe, or mutate the supplied id.",
    }


__all__ = [
    "SUBTITLE_QA_RESULT_SCHEMA_VERSION",
    "SUBTITLE_TRACK_INVENTORY_SCHEMA_VERSION",
    "SUBTITLE_SYNC_REVIEW_SCHEMA_VERSION",
    "SUBTITLE_QA_SUMMARY_SCHEMA_VERSION",
    "build_queue_subtitle_qa",
    "build_completed_subtitle_qa",
    "subtitle_qa_summary_from_payloads",
    "subtitle_qa_item_from_payloads",
]
