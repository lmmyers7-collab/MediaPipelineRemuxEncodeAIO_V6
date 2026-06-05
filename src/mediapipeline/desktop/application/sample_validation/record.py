from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...config_keys import KEY_OUTSOURCE
from ...models import ResolvedPaths
from .evidence import SAMPLE_VALIDATION_EVIDENCE_KEYS
from .pilot_plan import SAMPLE_VALIDATION_SAMPLE_CATEGORY_KEYS
from .summary import SAMPLE_VALIDATION_CHECK_KEYS


SAMPLE_VALIDATION_RECORD_SCHEMA = "sample_validation_record.v1"
SAMPLE_VALIDATION_REQUEST_MAX_BYTES = 64 * 1024
SAMPLE_VALIDATION_NOTE_MAX_CHARS = 4000
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600
SAMPLE_VALIDATION_EVIDENCE_LIMIT = 24
SAMPLE_VALIDATION_DECISIONS = {"accepted", "hold_review", "manual_review", "rerun_backend"}
SAMPLE_VALIDATION_PROOF_STRENGTHS = {"exact-path", "partial-exact", "filename-advisory", "none"}
LEGACY_OUTPUT_ROOT_CONFIG_KEYS = ("OutsourcePath", "ServerOut", "OutputRoot")


def _normalized_sample_validation_record(
    resolved: ResolvedPaths,
    request: Mapping[str, Any],
    *,
    app_version: str,
    warnings: list[str],
    errors: list[str],
) -> dict[str, Any]:
    schema = _clean_text(request.get("schema") or request.get("schema_version"))
    if schema != SAMPLE_VALIDATION_RECORD_SCHEMA:
        errors.append(f"schema must be {SAMPLE_VALIDATION_RECORD_SCHEMA}.")
    decision = _clean_text(request.get("operator_decision")).casefold()
    if decision not in SAMPLE_VALIDATION_DECISIONS:
        errors.append(f"operator_decision must be one of: {', '.join(sorted(SAMPLE_VALIDATION_DECISIONS))}.")
    proof_strength = _normalize_proof_strength(request.get("proof_strength"), warnings)
    source_path = _clean_text(request.get("source_path"))
    output_path = _clean_text(request.get("output_path"))
    if not source_path and not output_path:
        errors.append("source_path and output_path cannot both be empty.")
    _warn_path_outside_known_roots(resolved, source_path, "source_path", warnings)
    _warn_path_outside_known_roots(resolved, output_path, "output_path", warnings)
    checks = _normalize_checks(request.get("checks"))
    evidence = _normalize_evidence(request.get("evidence"))
    sample_category = _normalize_sample_category(request.get("sample_category") or request.get("category"), warnings)
    operator_notes = _clean_text(request.get("operator_notes"), max_chars=SAMPLE_VALIDATION_NOTE_MAX_CHARS)
    if len(str(request.get("operator_notes") or "")) > SAMPLE_VALIDATION_NOTE_MAX_CHARS:
        warnings.append(f"operator_notes was truncated to {SAMPLE_VALIDATION_NOTE_MAX_CHARS} characters.")
    _validation_evidence_warnings(decision, proof_strength, evidence, operator_notes, sample_category, warnings)
    record = {
        "schema": SAMPLE_VALIDATION_RECORD_SCHEMA,
        "record_id": _clean_text(request.get("record_id")) or f"sample-{uuid4().hex}",
        "created_at": _clean_text(request.get("created_at")) or _utc_now(),
        "created_by": _clean_text(request.get("created_by")) or "operator",
        "shell": _clean_text(request.get("shell")) or "webview",
        "app_version": _clean_text(request.get("app_version")) or app_version,
        "source_path": source_path,
        "output_path": output_path,
        "sample_label": _clean_text(request.get("sample_label")),
        "sample_category": sample_category,
        "proof_strength": proof_strength,
        "operator_decision": decision,
        "checks": checks,
        "evidence": evidence,
        "operator_notes": operator_notes,
    }
    for key in (
        "route_reason",
        "route_action",
        "encoder",
        "subtitle_summary",
        "audio_summary",
        "pending_manifest_path",
        "completed_manifest_row_key",
    ):
        value = _clean_text(request.get(key))
        if value:
            record[key] = value
    for key in ("source_size_bytes", "output_size_bytes"):
        value = _optional_int(request.get(key))
        if value is not None:
            record[key] = value
    value = _optional_float(request.get("size_growth_percent"))
    if value is not None:
        record["size_growth_percent"] = value
    return record


def _normalize_sample_category(value: Any, warnings: list[str]) -> str:
    category = _clean_text(value).casefold()
    if not category:
        return ""
    if category in SAMPLE_VALIDATION_SAMPLE_CATEGORY_KEYS:
        return category
    warnings.append(
        "sample_category was not one of the known representative pilot categories; it was omitted. "
        f"Known categories: {', '.join(sorted(SAMPLE_VALIDATION_SAMPLE_CATEGORY_KEYS))}."
    )
    return ""


def _validation_evidence_warnings(
    decision: str,
    proof_strength: str,
    evidence: Mapping[str, list[Any]],
    operator_notes: str,
    sample_category: str,
    warnings: list[str],
) -> None:
    if not any(evidence.get(key) for key in SAMPLE_VALIDATION_EVIDENCE_KEYS):
        warnings.append("No evidence arrays are populated; this record will be notes-only.")
    if decision != "accepted":
        return
    if not sample_category:
        warnings.append("Accepted decision has no sample_category; the Real-Media Sample Set Guide will treat it as generic evidence.")
    if proof_strength == "filename-advisory" and not operator_notes:
        warnings.append("Filename-only advisory proof is being accepted without operator notes.")
    if not evidence.get("completed"):
        warnings.append("Accepted decision has no Completed evidence; verify output, sidecar, route, and size manually.")
    pending_text = _evidence_text(evidence.get("pending_publish", []))
    if any(term in pending_text for term in ("blocker", "blocked", "do not drain", "missing payload", "invalid manifest")):
        warnings.append("Accepted decision includes Pending Publish blocker text; inspect parked payloads and drain state.")
    diagnostics_text = _evidence_text(evidence.get("diagnostics", []))
    if any(term in diagnostics_text for term in ("error", "failed", "failure", "exception", "traceback")):
        warnings.append("Accepted decision includes Diagnostics failure/error text; inspect logs before trusting the sample.")


def _normalize_proof_strength(value: Any, warnings: list[str]) -> str:
    raw = _clean_text(value).casefold().replace("_", "-").replace(" ", "-")
    aliases = {
        "strong-exact-path-trace": "exact-path",
        "exact-path-trace": "exact-path",
        "partial-exact-proof": "partial-exact",
        "filename-only-advisory": "filename-advisory",
        "no-evidence": "none",
    }
    normalized = aliases.get(raw, raw)
    if normalized not in SAMPLE_VALIDATION_PROOF_STRENGTHS:
        if normalized:
            warnings.append(f"Unknown proof_strength '{normalized}' was normalized to 'none'.")
        return "none"
    return normalized


def _normalize_checks(value: Any) -> dict[str, bool]:
    source = value if isinstance(value, Mapping) else {}
    return {key: bool(source.get(key)) for key in SAMPLE_VALIDATION_CHECK_KEYS}


def _normalize_evidence(value: Any) -> dict[str, list[Any]]:
    source = value if isinstance(value, Mapping) else {}
    return {key: _normalize_evidence_list(source.get(key)) for key in SAMPLE_VALIDATION_EVIDENCE_KEYS}


def _normalize_evidence_list(value: Any) -> list[Any]:
    raw_items = value if isinstance(value, list) else [] if value in (None, "") else [value]
    return [_normalize_evidence_item(item) for item in raw_items[:SAMPLE_VALIDATION_EVIDENCE_LIMIT]]


def _normalize_evidence_item(item: Any) -> Any:
    if isinstance(item, Mapping):
        normalized: dict[str, Any] = {}
        for key, value in list(item.items())[:12]:
            if isinstance(value, (str, int, float, bool)) or value is None:
                normalized[_clean_text(key, max_chars=80)] = _clean_text(value)
        return normalized
    return _clean_text(item)


def _evidence_text(items: list[Any]) -> str:
    return " ".join(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str).casefold() for item in items)


def _warn_path_outside_known_roots(resolved: ResolvedPaths, raw_path: str, label: str, warnings: list[str]) -> None:
    if not raw_path:
        return
    try:
        path = Path(raw_path)
    except (TypeError, ValueError):
        warnings.append(f"{label} is not a valid path string.")
        return
    if not path.is_absolute():
        warnings.append(f"{label} is not absolute; validation evidence may be stale or ambiguous.")
        return
    roots = _known_validation_roots(resolved)
    if not roots:
        return
    if not any(_path_is_relative_to(path, root) for root in roots):
        warnings.append(f"{label} is outside known source/output/state roots; treat this record as advisory.")


def _known_validation_roots(resolved: ResolvedPaths) -> list[Path]:
    candidates: list[Any] = [
        resolved.source_movies,
        resolved.source_tv,
        resolved.pending_push_path,
        resolved.state_root,
        resolved.local_base,
        resolved.workspace_root,
        resolved.app_root,
        resolved.completed_manifest_path.parent if resolved.completed_manifest_path else None,
        resolved.config_data.get(KEY_OUTSOURCE) if isinstance(resolved.config_data, Mapping) else None,
    ]
    if isinstance(resolved.config_data, Mapping):
        candidates.extend(resolved.config_data.get(key) for key in LEGACY_OUTPUT_ROOT_CONFIG_KEYS)
    roots: list[Path] = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            roots.append(Path(candidate))
        except TypeError:
            continue
    return roots


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        normalized_path = Path(os.path.normcase(os.path.abspath(path)))
        normalized_root = Path(os.path.normcase(os.path.abspath(root)))
        return normalized_path == normalized_root or normalized_root in normalized_path.parents
    except (OSError, ValueError):
        return False


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:max_chars]


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None
    return round(parsed, 3)


def _json_size(value: Any, errors: list[str]) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        errors.append(f"Sample validation payload is not strict JSON: {exc}")
        return SAMPLE_VALIDATION_REQUEST_MAX_BYTES + 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
