"""Return a deterministic, token-bounded repository context capsule for a task."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

from mediapipeline.tools.dev.context_records import (
    DEFAULT_EXCLUDED_EVIDENCE,
    FEATURE_SPECS,
    ContextRecord,
    collect_context_records,
    feature_spec,
    load_records,
    records_to_jsonl,
    terms_for,
    validate_record_paths,
)
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_INDEX_PATH = REPO_ROOT / "docs" / "generated" / "PROJECT_INDEX.jsonl"
DEFAULT_BUDGET = 3000
LAYER_ORDER = (
    "webview-tauri",
    "local-api",
    "python-domain",
    "powershell-engine",
    "state-config",
    "tests",
    "boundary-validation-docs",
    "secondary-evidence",
)
LAYER_LABELS = {
    "webview-tauri": "WebView / Tauri",
    "local-api": "Local API",
    "python-domain": "Python domain / services",
    "powershell-engine": "PowerShell engine",
    "state-config": "State / config surfaces",
    "tests": "Tests",
    "boundary-validation-docs": "Boundary / validation documentation",
    "secondary-evidence": "Secondary evidence",
}
EVIDENCE_BONUS = {
    "production": 14,
    "test": 7,
    "documentation": 5,
    "generated": 1,
    "change_evidence": 0,
    "archive": -3,
    "runtime_artifact": -5,
}
PRIORITY_BONUS = {"high": 8, "medium": 3, "low": 0}
AUTHORITY_BONUS = {
    "backend-mutation-authority": 12,
    "backend-authority": 10,
    "backend-route-adapter": 9,
    "canonical-boundary": 8,
    "frontend-display-and-intent": 6,
    "verification-evidence": 4,
}


@dataclass(frozen=True)
class RankedContextItem:
    record: ContextRecord
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ContextCapsule:
    task: str
    requested_budget: int
    estimated_tokens: int
    feature_id: str
    feature_label: str
    authority_owner: str
    confidence_score: int
    low_confidence: bool
    items: tuple[RankedContextItem, ...]
    omitted_count: int
    high_risk_relevant: bool
    validation_rungs: tuple[str, ...]
    state_files: tuple[str, ...]
    suggested_terms: tuple[str, ...]
    truncation_notes: tuple[str, ...]


def estimate_tokens(text: str) -> int:
    """Estimate context tokens as ceil(final UTF-8 bytes / 4)."""
    return math.ceil(len(text.encode("utf-8")) / 4)


def budget_tolerance(budget: int) -> int:
    return max(16, math.ceil(budget * 0.02))


def _feature_match(task: str) -> tuple[str, int, tuple[str, ...]]:
    task_lower = task.casefold()
    task_terms = set(terms_for(task))
    scored: list[tuple[int, str, tuple[str, ...]]] = []
    for spec in FEATURE_SPECS:
        reasons: list[str] = []
        score = 0
        feature_terms = set(terms_for(spec.feature_id, spec.label, spec.keywords))
        overlap = sorted(task_terms.intersection(feature_terms))
        if overlap:
            score += len(overlap) * 5
            reasons.append("terms " + ", ".join(overlap[:5]))
        phrase_hits = [keyword for keyword in spec.keywords if " " in keyword and keyword.casefold() in task_lower]
        if phrase_hits:
            score += len(phrase_hits) * 12
            reasons.append("phrases " + ", ".join(phrase_hits[:3]))
        if spec.feature_id.replace("-", " ") in task_lower:
            score += 16
            reasons.append("feature name")
        scored.append((score, spec.feature_id, tuple(reasons)))
    best_score, best_feature, best_reasons = max(scored, key=lambda item: (item[0], item[1]))
    return best_feature, best_score, best_reasons


def _record_score(
    record: ContextRecord,
    *,
    task: str,
    task_terms: set[str],
    feature_id: str,
) -> RankedContextItem:
    path_lower = record.path.casefold()
    purpose_lower = record.purpose.casefold()
    reasons: list[str] = []
    score = 0
    record_terms = set(record.relevance_terms) or set(
        terms_for(record.path, record.purpose, record.public_symbols, record.api_routes, record.state_files)
    )
    overlap = sorted(task_terms.intersection(record_terms))
    if overlap:
        score += len(overlap) * 7
        reasons.append("task terms: " + ", ".join(overlap[:5]))
    task_lower = task.casefold().strip()
    if task_lower and task_lower in f"{path_lower} {purpose_lower}":
        score += 24
        reasons.append("exact task phrase")
    if feature_id == record.feature_group:
        score += 24
        reasons.append("primary feature match")
    elif feature_id in record.feature_groups:
        score += 15
        reasons.append("related feature match")
    spec = feature_spec(feature_id)
    if spec and record.path in spec.boundary_docs:
        score += 30
        reasons.append("canonical feature boundary")
    if spec and record.path in spec.anchor_paths:
        score += 36
        reasons.append("curated vertical-slice anchor")
    if record.owner_domain in task_terms:
        score += 7
        reasons.append("owner-domain match")
    score += PRIORITY_BONUS.get(record.token_priority, 0)
    score += AUTHORITY_BONUS.get(record.authority, 0)
    score += EVIDENCE_BONUS.get(record.evidence_category, 0)
    if record.path.endswith(("facade.py", "service.py", "routes.py", "handler.py", "lib.rs")):
        score += 5
        reasons.append("authority entrypoint")
    if record.api_routes and task_terms.intersection(terms_for(record.api_routes)):
        score += 5
        reasons.append("matching API route")
    if record.state_files and task_terms.intersection(terms_for(record.state_files)):
        score += 5
        reasons.append("matching state surface")
    if not reasons:
        reasons.append("supporting catalog match")
    return RankedContextItem(record=record, score=score, reasons=tuple(reasons))


def rank_records(
    records: Iterable[ContextRecord],
    *,
    task: str,
    include_history: bool = False,
) -> tuple[str, int, list[RankedContextItem]]:
    feature_id, feature_score, _ = _feature_match(task)
    task_terms = set(terms_for(task))
    allowed_records = []
    for record in records:
        if record.evidence_category in {"runtime_artifact", "generated"}:
            continue
        if not include_history and record.evidence_category in DEFAULT_EXCLUDED_EVIDENCE:
            continue
        allowed_records.append(record)
    ranked = [
        _record_score(record, task=task, task_terms=task_terms, feature_id=feature_id)
        for record in allowed_records
    ]
    ranked.sort(key=lambda item: (-item.score, item.record.path.casefold(), item.record.path))

    # Dependency distance and explicit test relationships are calculated after
    # lexical/feature seeds, then folded into a second deterministic sort.
    seed_paths = {item.record.path for item in ranked[:8] if item.score >= 20}
    related_paths: dict[str, str] = {}
    for item in ranked[:8]:
        if item.record.path not in seed_paths:
            continue
        for path in item.record.outbound_dependencies:
            related_paths.setdefault(path, "dependency of a top match")
        for path in item.record.inbound_dependents:
            related_paths.setdefault(path, "dependent of a top match")
        for path in item.record.associated_tests:
            related_paths.setdefault(path, "associated test for a top match")
    rescored: list[RankedContextItem] = []
    for item in ranked:
        relation = related_paths.get(item.record.path)
        if relation:
            bonus = 18 if item.record.evidence_category == "test" else 11
            item = replace(item, score=item.score + bonus, reasons=item.reasons + (relation,))
        rescored.append(item)
    rescored.sort(key=lambda item: (-item.score, item.record.path.casefold(), item.record.path))
    return feature_id, feature_score, rescored


def _owner_for(items: Iterable[RankedContextItem]) -> str:
    candidates = [
        item
        for item in items
        if item.record.evidence_category == "production"
        and item.record.authority.startswith("backend")
    ]
    if not candidates:
        candidates = [item for item in items if item.record.evidence_category == "production"]
    return candidates[0].record.owner_domain if candidates else "undetermined"


def _has_task_relevance(item: RankedContextItem) -> bool:
    prefixes = (
        "task terms:",
        "exact task phrase",
        "primary feature match",
        "related feature match",
        "canonical feature boundary",
        "curated vertical-slice anchor",
        "owner-domain match",
        "matching API route",
        "matching state surface",
        "dependency of a top match",
        "dependent of a top match",
        "associated test for a top match",
    )
    return any(reason.startswith(prefixes) for reason in item.reasons)


def _capsule_with_items(
    *,
    task: str,
    budget: int,
    feature_id: str,
    feature_score: int,
    ranked: list[RankedContextItem],
    items: list[RankedContextItem],
    low_confidence: bool,
    truncation_notes: tuple[str, ...],
) -> ContextCapsule:
    spec = feature_spec(feature_id)
    state_files = tuple(
        sorted(
            {state for item in items for state in item.record.state_files},
            key=lambda value: (value.casefold(), value),
        )[:16]
    )
    validation = tuple(
        dict.fromkeys(item.record.validation_rung for item in items if item.record.validation_rung)
    )[:6]
    high_risk = any(
        item.record.risk_tier == "high"
        and item.record.evidence_category == "production"
        and item.score >= 20
        for item in items
    )
    suggested = tuple(spec.keywords[:6]) if spec else tuple(sorted(terms_for(task))[:6])
    return ContextCapsule(
        task=task,
        requested_budget=budget,
        estimated_tokens=0,
        feature_id=feature_id,
        feature_label=spec.label if spec else "Repository-wide support",
        authority_owner=_owner_for(items),
        confidence_score=feature_score,
        low_confidence=low_confidence,
        items=tuple(items),
        omitted_count=max(0, len(ranked) - len(items)),
        high_risk_relevant=high_risk,
        validation_rungs=validation,
        state_files=state_files,
        suggested_terms=suggested,
        truncation_notes=truncation_notes,
    )


def _finalize_estimate(capsule: ContextCapsule, output_format: str) -> ContextCapsule:
    current = capsule
    for _ in range(4):
        rendered = render_capsule(current, output_format=output_format)
        estimate = estimate_tokens(rendered)
        if estimate == current.estimated_tokens:
            break
        current = replace(current, estimated_tokens=estimate)
    return current


def build_context_capsule(
    records: Iterable[ContextRecord],
    *,
    task: str,
    budget: int = DEFAULT_BUDGET,
    include_history: bool = False,
    output_format: str = "markdown",
) -> ContextCapsule:
    if budget < 200:
        raise ValueError("budget must be at least 200 estimated tokens")
    feature_id, feature_score, ranked = rank_records(records, task=task, include_history=include_history)
    max_score = ranked[0].score if ranked else 0
    # Authority/priority bonuses can make a record score highly even when the
    # task vocabulary matched nothing. Feature confidence therefore remains
    # the decisive low-confidence signal.
    low_confidence = feature_score < 5
    if low_confidence:
        ranked = [item for item in ranked if item.score >= max_score - 3][:5]
    else:
        ranked = [item for item in ranked if item.score >= 18 and _has_task_relevance(item)]

    # Seed one best candidate per relevant layer so the result is a vertical
    # implementation slice before filling remaining budget by global rank.
    selected: list[RankedContextItem] = []
    selected_paths: set[str] = set()
    spec = feature_spec(feature_id)
    if spec:
        ranked_by_path = {item.record.path: item for item in ranked}
        for path in spec.anchor_paths:
            candidate = ranked_by_path.get(path)
            if candidate and path not in selected_paths:
                selected.append(candidate)
                selected_paths.add(path)
    for layer in LAYER_ORDER:
        candidate = next((item for item in ranked if item.record.layer == layer), None)
        if candidate and candidate.record.path not in selected_paths:
            selected.append(candidate)
            selected_paths.add(candidate.record.path)
    for item in ranked:
        if item.record.path not in selected_paths:
            selected.append(item)
            selected_paths.add(item.record.path)

    tolerance = budget_tolerance(budget)
    fitted: list[RankedContextItem] = []
    for item in selected:
        trial = fitted + [item]
        trial_capsule = _capsule_with_items(
            task=task,
            budget=budget,
            feature_id=feature_id,
            feature_score=feature_score,
            ranked=ranked,
            items=trial,
            low_confidence=low_confidence,
            truncation_notes=("lower-ranked secondary results omitted to honor the requested budget",)
            if len(trial) < len(ranked)
            else (),
        )
        trial_capsule = _finalize_estimate(trial_capsule, output_format)
        if trial_capsule.estimated_tokens <= budget + tolerance or not fitted:
            fitted = trial

    notes = (
        ("lower-ranked secondary results omitted to honor the requested budget",)
        if len(fitted) < len(ranked)
        else ()
    )
    capsule = _capsule_with_items(
        task=task,
        budget=budget,
        feature_id=feature_id,
        feature_score=feature_score,
        ranked=ranked,
        items=fitted,
        low_confidence=low_confidence,
        truncation_notes=notes,
    )
    capsule = _finalize_estimate(capsule, output_format)
    # If the fixed header alone plus the first record breaches an unusually low
    # budget, retain the unambiguous path and compact the optional metadata.
    while capsule.estimated_tokens > budget + tolerance and len(capsule.items) > 1:
        capsule = _capsule_with_items(
            task=task,
            budget=budget,
            feature_id=feature_id,
            feature_score=feature_score,
            ranked=ranked,
            items=list(capsule.items[:-1]),
            low_confidence=low_confidence,
            truncation_notes=notes,
        )
        capsule = _finalize_estimate(capsule, output_format)
    return capsule


def _item_to_dict(item: RankedContextItem) -> dict[str, object]:
    return {
        "path": item.record.path,
        "layer": item.record.layer,
        "purpose": item.record.purpose,
        "owner_domain": item.record.owner_domain,
        "authority": item.record.authority,
        "evidence_category": item.record.evidence_category,
        "risk_tier": item.record.risk_tier,
        "score": item.score,
        "why": list(item.reasons),
        "dependencies": list(item.record.outbound_dependencies[:6]),
        "dependents": list(item.record.inbound_dependents[:6]),
        "tests": list(item.record.associated_tests[:6]),
        "api_routes": list(item.record.api_routes[:8]),
        "state_files": list(item.record.state_files[:8]),
        "validation": item.record.validation_rung,
    }


def render_capsule(capsule: ContextCapsule, *, output_format: str = "markdown") -> str:
    if output_format == "json":
        payload = {
            "task": capsule.task,
            "requested_budget": capsule.requested_budget,
            "estimated_tokens": capsule.estimated_tokens,
            "feature_id": capsule.feature_id,
            "feature": capsule.feature_label,
            "authority_owner": capsule.authority_owner,
            "confidence_score": capsule.confidence_score,
            "low_confidence": capsule.low_confidence,
            "high_risk_relevant": capsule.high_risk_relevant,
            "items": [_item_to_dict(item) for item in capsule.items],
            "state_files": list(capsule.state_files),
            "validation_rungs": list(capsule.validation_rungs),
            "omitted_count": capsule.omitted_count,
            "truncation_notes": list(capsule.truncation_notes),
            "suggested_terms": list(capsule.suggested_terms),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    lines = [
        "# Task context capsule",
        "",
        f"Task: {capsule.task}",
        f"Feature: {capsule.feature_label} (`{capsule.feature_id}`)",
        f"Authority owner: `{capsule.authority_owner}`",
        "Layer reminder: Tauri/WebView -> Local API -> Python domain/contracts -> PowerShell engine -> tools/filesystem.",
        "The frontend displays state and stages intent; backend and PowerShell own mutation and media policy.",
        "",
    ]
    if capsule.low_confidence:
        lines.extend(
            [
                "No confident feature match was found. Start with these nearest catalog results and refine the task.",
                "Suggested search terms: " + ", ".join(f"`{term}`" for term in capsule.suggested_terms),
                "",
            ]
        )
    grouped: dict[str, list[RankedContextItem]] = {layer: [] for layer in LAYER_ORDER}
    for item in capsule.items:
        grouped.setdefault(item.record.layer, []).append(item)
    for layer in LAYER_ORDER:
        items = grouped.get(layer, [])
        if not items:
            continue
        lines.extend((f"## {LAYER_LABELS.get(layer, layer)}", ""))
        for item in items:
            reason = "; ".join(item.reasons[:3])
            lines.append(f"- `{item.record.path}` — {item.record.purpose} Why: {reason}.")
            relations: list[str] = []
            if item.record.outbound_dependencies:
                relations.append("depends on " + ", ".join(f"`{path}`" for path in item.record.outbound_dependencies[:3]))
            if item.record.inbound_dependents:
                relations.append("used by " + ", ".join(f"`{path}`" for path in item.record.inbound_dependents[:3]))
            if item.record.associated_tests:
                relations.append("tests " + ", ".join(f"`{path}`" for path in item.record.associated_tests[:3]))
            if relations:
                lines.append("  " + "; ".join(relations) + ".")
        lines.append("")
    if capsule.state_files:
        lines.extend(("## State / manifest identifiers", "", ", ".join(f"`{value}`" for value in capsule.state_files), ""))
    lines.extend(("## Validation and risk", ""))
    for rung in capsule.validation_rungs:
        lines.append(f"- {rung}")
    if capsule.high_risk_relevant:
        lines.append("- High-risk boundary is relevant: read the returned boundary document before changing production behavior.")
    else:
        lines.append("- No mutation-level warning was added; selected work is not classified as high-risk production mutation.")
    lines.extend(
        (
            "",
            "## Budget",
            "",
            f"Estimated tokens: **{capsule.estimated_tokens}** / requested **{capsule.requested_budget}**.",
            f"Omitted matching records: **{capsule.omitted_count}**.",
        )
    )
    for note in capsule.truncation_notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def check_index(path: Path = DEFAULT_INDEX_PATH) -> int:
    if not path.is_file():
        print(f"Missing generated context index: {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1
    try:
        records = load_records(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid generated context index: {exc}", file=sys.stderr)
        return 1
    findings = validate_record_paths(records, REPO_ROOT)
    if findings:
        print(f"Context index path findings ({len(findings)}):", file=sys.stderr)
        for finding in findings[:80]:
            print(f"  {finding}", file=sys.stderr)
        return 1
    expected = records_to_jsonl(collect_context_records())
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        print("PROJECT_INDEX.jsonl is stale. Run generate_project_index.", file=sys.stderr)
        return 1
    for task in (
        "pending publish drain readiness",
        "WebView queue display name",
        "Tauri close readiness",
        "ASS subtitle conversion",
    ):
        capsule = build_context_capsule(records, task=task, budget=3000)
        rendered = render_capsule(capsule)
        if estimate_tokens(rendered) > 3000 + budget_tolerance(3000):
            print(f"Budget self-check failed for: {task}", file=sys.stderr)
            return 1
        if capsule.low_confidence or not capsule.items:
            print(f"Retrieval self-check lacked confidence for: {task}", file=sys.stderr)
            return 1
    print(f"OK: {path.relative_to(REPO_ROOT)} is current and representative slices fit 3,000 tokens.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", help="Natural-language task to retrieve repository context for.")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="Approximate output token budget (minimum 200).")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--include-history", action="store_true", help="Include archive and change-evidence records.")
    parser.add_argument("--check", action="store_true", help="Validate index freshness, paths, and representative retrievals.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.check:
        return check_index(args.index)
    if not args.task:
        parser.error("--task is required unless --check is used")
    if not args.index.is_file():
        print(f"Missing generated context index: {args.index}", file=sys.stderr)
        return 1
    try:
        records = load_records(args.index)
        capsule = build_context_capsule(
            records,
            task=args.task,
            budget=args.budget,
            include_history=args.include_history,
            output_format=args.format,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(render_capsule(capsule, output_format=args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
