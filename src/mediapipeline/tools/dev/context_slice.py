"""Return a deterministic, token-bounded repository context capsule for a task."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from mediapipeline.tools.dev.context_records import (
    FEATURE_SPECS,
    RETRIEVAL_TIERS,
    RETRIEVAL_TIER_ACTIVE,
    ContextRecord,
    collect_context_records,
    feature_spec,
    load_records,
    low_information_terms_for,
    normalize_retrieval_text,
    normalize_retrieval_tier,
    record_is_retrievable,
    record_serialized_size_bytes,
    records_to_jsonl,
    retrieval_terms_for,
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
INTENT_ORDER = ("documentation", "tooling", "ui", "api", "tests", "media-engine")
INTENT_PHRASES = {
    "documentation": (
        "documentation only",
        "docs only",
        "documentation",
        "document",
        "docs",
        "readme",
        "operator guide",
        "markdown",
    ),
    "tooling": (
        "generated context",
        "context slice",
        "context capsule",
        "project index",
        "repository navigation",
        "retrieval ranking",
        "ai token",
        "token usage",
        "developer tooling",
        "cli tool",
        "tooling",
    ),
    "ui": ("webview", "tauri", "frontend", "operator ui", "user interface", "ui", "dom", "browser", "javascript", "css", "html"),
    "api": ("local api", "api route", "api", "endpoint", "strict json", "http route", "request contract"),
    "tests": ("regression test", "unit test", "integration test", "browser test", "smoke test", "test coverage", "testing", "tests", "test"),
    "media-engine": (
        "media policy",
        "media engine",
        "media",
        "powershell engine",
        "ffmpeg",
        "ffprobe",
        "stream mapping",
        "source movement",
        "remux",
        "encode",
        "transcode",
        "subtitle",
        "audio policy",
        "pending publish",
    ),
}
DISJOINT_INTENTS = {
    "documentation": frozenset({"ui", "api", "media-engine"}),
    "tooling": frozenset({"ui", "api", "media-engine"}),
    "ui": frozenset({"tooling", "media-engine"}),
    "api": frozenset({"tooling", "media-engine"}),
    "media-engine": frozenset({"tooling", "ui", "api"}),
}
MEDIA_FEATURES = frozenset({"media-processing", "subtitles-audio", "pending-publish"})
_QUOTED_TEXT_RE = re.compile(r"['\"]([^'\"]{2,})['\"]")


@dataclass(frozen=True)
class RankedContextItem:
    record: ContextRecord
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TaskProfile:
    normalized: str
    terms: frozenset[str]
    low_information_terms: frozenset[str]
    intents: tuple[str, ...]
    documentation_only: bool
    quoted_phrases: tuple[str, ...]


@dataclass(frozen=True)
class RecordRetrievalProfile:
    path: str
    purpose: str
    record_text: str
    basename: str
    core_terms: frozenset[str]
    structured_terms: frozenset[str]
    catalog_terms: frozenset[str]
    all_terms: frozenset[str]
    path_terms: frozenset[str]
    symbol_terms: frozenset[str]
    route_terms: frozenset[str]
    state_terms: frozenset[str]
    intents: frozenset[str]


@dataclass(frozen=True)
class RetrievalStats:
    tier: str
    catalog_count: int
    eligible_count: int
    candidate_count: int
    candidate_bytes: int


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
    omission_reasons: tuple[str, ...]
    retrieval_stats: RetrievalStats


def estimate_tokens(text: str) -> int:
    """Estimate context tokens as ceil(final UTF-8 bytes / 4)."""
    return math.ceil(len(text.encode("utf-8")) / 4)


def budget_tolerance(budget: int) -> int:
    return max(16, math.ceil(budget * 0.02))


def _contains_phrase(haystack: str, needle: str) -> bool:
    return bool(needle) and f" {needle} " in f" {haystack} "


def _task_profile(task: str) -> TaskProfile:
    normalized = normalize_retrieval_text(task)
    intent_scores: list[tuple[int, str]] = []
    for intent in INTENT_ORDER:
        matches = [
            normalize_retrieval_text(phrase)
            for phrase in INTENT_PHRASES[intent]
            if _contains_phrase(normalized, normalize_retrieval_text(phrase))
        ]
        if matches:
            intent_scores.append((max(len(match.split()) for match in matches), intent))
    intents = tuple(intent for _, intent in sorted(intent_scores, key=lambda item: (-item[0], INTENT_ORDER.index(item[1]))))
    documentation_only = any(
        _contains_phrase(normalized, phrase)
        for phrase in ("documentation only", "docs only", "only documentation")
    )
    quoted = tuple(
        sorted(
            {
                normalize_retrieval_text(match)
                for match in _QUOTED_TEXT_RE.findall(task)
                if normalize_retrieval_text(match)
            },
            key=lambda value: (value.casefold(), value),
        )
    )
    return TaskProfile(
        normalized=normalized,
        terms=frozenset(retrieval_terms_for(task)),
        low_information_terms=frozenset(low_information_terms_for(task)),
        intents=intents,
        documentation_only=documentation_only,
        quoted_phrases=quoted,
    )


def _feature_match(profile: TaskProfile) -> tuple[str, int, tuple[str, ...]]:
    scored: list[tuple[int, str, tuple[str, ...]]] = []
    for spec in FEATURE_SPECS:
        reasons: list[str] = []
        score = 0
        feature_terms = set(retrieval_terms_for(spec.feature_id, spec.label, spec.keywords))
        overlap = sorted(profile.terms.intersection(feature_terms))
        if overlap:
            score += len(overlap) * 4
            reasons.append("terms " + ", ".join(overlap[:5]))
        phrase_hits = [
            keyword
            for keyword in spec.keywords
            if " " in normalize_retrieval_text(keyword)
            and _contains_phrase(profile.normalized, normalize_retrieval_text(keyword))
        ]
        if phrase_hits:
            score += sum(14 + min(10, len(normalize_retrieval_text(hit).split()) * 3) for hit in phrase_hits)
            reasons.append("phrases " + ", ".join(phrase_hits[:3]))
        if _contains_phrase(profile.normalized, normalize_retrieval_text(spec.feature_id)):
            score += 24
            reasons.append("feature name")
        scored.append((score, spec.feature_id, tuple(reasons)))
    best_score, best_feature, best_reasons = max(scored, key=lambda item: (item[0], item[1]))
    return best_feature, best_score, best_reasons


def _record_intents_from_fields(
    *,
    path: str,
    evidence_category: str,
    layer: str,
    owner_domain: str,
    feature_group: str,
) -> frozenset[str]:
    path = path.casefold()
    categories: set[str] = set()
    if evidence_category == "documentation":
        categories.add("documentation")
    if evidence_category == "test":
        categories.add("tests")
    if (
        path.startswith("src/mediapipeline/tools/")
        or path.startswith("tests/python/tooling/")
        or path.startswith("docs/generated/")
        or path.startswith("ops/scripts/dev/")
        or path == "agents.md"
    ):
        categories.add("tooling")
    if layer == "webview-tauri" or path.startswith("tests/webview/"):
        categories.add("ui")
    if layer == "local-api" or owner_domain in {"api", "contracts"}:
        categories.add("api")
    if layer == "powershell-engine" or feature_group in MEDIA_FEATURES or path.startswith("ops/pipeline/tests/"):
        categories.add("media-engine")
    return frozenset(categories)


@lru_cache(maxsize=8192)
def _record_profile_cached(
    path: str,
    purpose: str,
    public_symbols: tuple[str, ...],
    api_routes: tuple[str, ...],
    state_files: tuple[str, ...],
    relevance_terms: tuple[str, ...],
    evidence_category: str,
    layer: str,
    owner_domain: str,
    feature_group: str,
) -> RecordRetrievalProfile:
    return RecordRetrievalProfile(
        path=normalize_retrieval_text(path),
        purpose=normalize_retrieval_text(purpose),
        record_text=normalize_retrieval_text(
            path,
            purpose,
            public_symbols,
            api_routes,
            state_files,
        ),
        basename=normalize_retrieval_text(path.rsplit("/", 1)[-1].rsplit(".", 1)[0]),
        core_terms=frozenset(retrieval_terms_for(path, purpose)),
        structured_terms=frozenset(retrieval_terms_for(public_symbols, api_routes, state_files)),
        catalog_terms=frozenset(retrieval_terms_for(relevance_terms)),
        all_terms=frozenset(
            retrieval_terms_for(
                path,
                purpose,
                public_symbols,
                api_routes,
                state_files,
                include_low_information=True,
            )
        ),
        path_terms=frozenset(retrieval_terms_for(path)),
        symbol_terms=frozenset(retrieval_terms_for(public_symbols)),
        route_terms=frozenset(retrieval_terms_for(api_routes)),
        state_terms=frozenset(retrieval_terms_for(state_files)),
        intents=_record_intents_from_fields(
            path=path,
            evidence_category=evidence_category,
            layer=layer,
            owner_domain=owner_domain,
            feature_group=feature_group,
        ),
    )


def _record_profile(record: ContextRecord) -> RecordRetrievalProfile:
    return _record_profile_cached(
        record.path,
        record.purpose,
        record.public_symbols,
        record.api_routes,
        record.state_files,
        record.relevance_terms,
        record.evidence_category,
        record.layer,
        record.owner_domain,
        record.feature_group,
    )


def _record_score(
    record: ContextRecord,
    *,
    profile: TaskProfile,
    feature_id: str,
) -> RankedContextItem:
    record_profile = _record_profile(record)
    path_lower = record_profile.path
    reasons: list[str] = []
    score = 0
    core_overlap = sorted(profile.terms.intersection(record_profile.core_terms))
    structured_overlap = sorted(profile.terms.intersection(record_profile.structured_terms))
    catalog_overlap = sorted(profile.terms.intersection(record_profile.catalog_terms))
    overlap = sorted(set(core_overlap) | set(structured_overlap) | set(catalog_overlap))
    if core_overlap:
        score += len(core_overlap) * 10
        reasons.append("direct terms: " + ", ".join(core_overlap[:5]))
    elif len(overlap) >= 2:
        score += len(overlap) * 7
        reasons.append("direct structured terms: " + ", ".join(overlap[:5]))
    elif overlap:
        score += 2
        reasons.append("incidental structured term: " + overlap[0])
    incidental_overlap = sorted(profile.low_information_terms.intersection(record_profile.all_terms))
    if incidental_overlap and not overlap:
        score -= 12
        reasons.append("incidental generic terms only: " + ", ".join(incidental_overlap[:4]))
    record_text = record_profile.record_text
    if profile.normalized and _contains_phrase(record_text, profile.normalized):
        score += 42
        reasons.append("exact task phrase")
    if feature_id == record.feature_group:
        score += 14
        reasons.append("primary feature match")
    elif feature_id in record.feature_groups:
        score += 8
        reasons.append("related feature match")
    spec = feature_spec(feature_id)
    if spec and record.path in spec.boundary_docs:
        score += 30
        reasons.append("canonical feature boundary")
    if spec and record.path in spec.anchor_paths:
        score += 36
        reasons.append("curated vertical-slice anchor")
    if record.owner_domain in profile.terms:
        score += 12
        reasons.append("owner-domain match")
    path_overlap = profile.terms.intersection(record_profile.path_terms)
    symbol_overlap = profile.terms.intersection(record_profile.symbol_terms)
    route_overlap = profile.terms.intersection(record_profile.route_terms)
    state_overlap = profile.terms.intersection(record_profile.state_terms)
    if path_overlap:
        score += len(path_overlap) * 5
        reasons.append("matching path identifiers")
    if symbol_overlap:
        score += len(symbol_overlap) * 9
        reasons.append("matching public symbol")
    if route_overlap:
        score += len(route_overlap) * 7
        reasons.append("matching API route")
    if state_overlap:
        score += len(state_overlap) * 7
        reasons.append("matching state surface")
    basename = record_profile.basename
    if _contains_phrase(profile.normalized, path_lower):
        score += 110
        reasons.append("exact repository path")
    elif _contains_phrase(profile.normalized, basename) and (
        len(retrieval_terms_for(basename)) >= 2
        or basename in profile.quoted_phrases
    ):
        score += 58
        reasons.append("exact filename")
    exact_symbols = sorted(
        symbol
        for symbol in record.public_symbols
        if _contains_phrase(profile.normalized, normalize_retrieval_text(symbol))
        and (
            set(retrieval_terms_for(symbol)).intersection(profile.terms)
            or normalize_retrieval_text(symbol) in profile.quoted_phrases
        )
    )
    if exact_symbols:
        score += 82
        reasons.append("exact public symbol: " + ", ".join(exact_symbols[:3]))
    quoted_hits = sorted(phrase for phrase in profile.quoted_phrases if _contains_phrase(record_text, phrase))
    if quoted_hits:
        score += 48
        reasons.append("quoted phrase: " + ", ".join(quoted_hits[:2]))
    categories = record_profile.intents
    for position, intent in enumerate(profile.intents):
        if intent in categories:
            score += 22 if position == 0 else 10
            reasons.append(f"{intent} intent match")
        elif position == 0 and categories.intersection(DISJOINT_INTENTS.get(intent, frozenset())):
            score -= 18
            reasons.append(f"{intent} intent mismatch")
        elif position == 0 and intent in {"tooling", "ui", "api", "media-engine"} and record.evidence_category == "production":
            score -= 32
            reasons.append(f"{intent} intent mismatch")
    if profile.documentation_only and record.evidence_category != "documentation":
        score -= 100
        reasons.append("excluded by documentation-only intent")
    score += PRIORITY_BONUS.get(record.token_priority, 0)
    score += AUTHORITY_BONUS.get(record.authority, 0)
    score += EVIDENCE_BONUS.get(record.evidence_category, 0)
    if record.path.endswith(("facade.py", "service.py", "routes.py", "handler.py", "lib.rs")):
        score += 5
        reasons.append("authority entrypoint")
    if not reasons:
        reasons.append("supporting catalog match")
    return RankedContextItem(record=record, score=score, reasons=tuple(reasons))


def _has_direct_task_evidence(item: RankedContextItem) -> bool:
    prefixes = (
        "direct terms:",
        "direct structured terms:",
        "exact task phrase",
        "exact repository path",
        "exact filename",
        "exact public symbol:",
        "quoted phrase:",
        "owner-domain match",
        "matching path identifiers",
        "matching API route",
        "matching state surface",
        "canonical feature boundary",
        "curated vertical-slice anchor",
    )
    return any(reason.startswith(prefixes) for reason in item.reasons)


def _is_exact_record_request(record: ContextRecord, profile: TaskProfile) -> bool:
    record_profile = _record_profile(record)
    if _contains_phrase(profile.normalized, record_profile.path):
        return True
    if record_profile.basename in profile.quoted_phrases:
        return True
    return any(
        normalize_retrieval_text(symbol) in profile.quoted_phrases
        or profile.normalized == normalize_retrieval_text(symbol)
        for symbol in record.public_symbols
    )


def _is_default_candidate(
    record: ContextRecord,
    *,
    profile: TaskProfile,
    feature_id: str,
    feature_score: int,
) -> bool:
    record_profile = _record_profile(record)
    spec = feature_spec(feature_id)
    if spec and record.path in (*spec.anchor_paths, *spec.boundary_docs):
        return True
    if feature_score >= 8 and (feature_id == record.feature_group or feature_id in record.feature_groups):
        return True
    direct_overlap = profile.terms.intersection(
        record_profile.core_terms | record_profile.structured_terms | record_profile.catalog_terms
    )
    if len(direct_overlap) >= 2:
        return True
    if record.owner_domain in profile.terms:
        return True
    if profile.quoted_phrases and any(
        _contains_phrase(record_profile.record_text, phrase) for phrase in profile.quoted_phrases
    ):
        return True
    return False


def rank_records_with_stats(
    records: Iterable[ContextRecord],
    *,
    task: str,
    include_history: bool = False,
    retrieval_tier: str = RETRIEVAL_TIER_ACTIVE,
) -> tuple[str, int, list[RankedContextItem], RetrievalStats]:
    profile = _task_profile(task)
    feature_id, feature_score, _ = _feature_match(profile)
    tier = normalize_retrieval_tier(retrieval_tier, include_history=include_history)
    catalog = sorted(records, key=lambda record: (record.path.casefold(), record.path))
    exact_paths = {
        record.path for record in catalog if _is_exact_record_request(record, profile)
    }
    allowed_records = [
        record
        for record in catalog
        if record.path in exact_paths or record_is_retrievable(record, tier)
    ]
    candidate_records = [
        record
        for record in allowed_records
        if record.path in exact_paths
        or _is_default_candidate(
            record,
            profile=profile,
            feature_id=feature_id,
            feature_score=feature_score,
        )
    ]
    ranked = [
        _record_score(record, profile=profile, feature_id=feature_id)
        for record in candidate_records
    ]
    ranked.sort(key=lambda item: (-item.score, item.record.path.casefold(), item.record.path))

    # Dependency distance and explicit test relationships are calculated after
    # lexical/feature seeds, then folded into a second deterministic sort.
    spec = feature_spec(feature_id)
    seed_items = (
        []
        if spec and spec.anchor_paths and feature_score >= 12
        else [item for item in ranked if _has_direct_task_evidence(item)][:4]
    )
    related_paths: dict[str, tuple[int, str]] = {}
    for item in seed_items:
        for path in item.record.outbound_dependencies:
            related_paths.setdefault(path, (11, "dependency of a top match"))
        for path in item.record.inbound_dependents:
            related_paths.setdefault(path, (11, "dependent of a top match"))
        for path in item.record.associated_tests:
            related_paths.setdefault(path, (18, "associated test for a top match"))
    candidate_paths = {record.path for record in candidate_records}
    allowed_by_path = {record.path: record for record in allowed_records}
    for path in sorted(related_paths, key=lambda value: (value.casefold(), value)):
        related = allowed_by_path.get(path)
        if related and path not in candidate_paths:
            ranked.append(_record_score(related, profile=profile, feature_id=feature_id))
            candidate_records.append(related)
            candidate_paths.add(path)
    rescored: list[RankedContextItem] = []
    for item in ranked:
        relation = related_paths.get(item.record.path)
        if relation:
            bonus, reason = relation
            if item.record.evidence_category == "test" and reason != "associated test for a top match":
                bonus += 3
            item = replace(item, score=item.score + bonus, reasons=item.reasons + (reason,))
        rescored.append(item)
    rescored.sort(key=lambda item: (-item.score, item.record.path.casefold(), item.record.path))
    stats = RetrievalStats(
        tier=tier,
        catalog_count=len(catalog),
        eligible_count=len(allowed_records),
        candidate_count=len(candidate_records),
        candidate_bytes=sum(record_serialized_size_bytes(record) for record in candidate_records),
    )
    return feature_id, feature_score, rescored, stats


def rank_records(
    records: Iterable[ContextRecord],
    *,
    task: str,
    include_history: bool = False,
    retrieval_tier: str = RETRIEVAL_TIER_ACTIVE,
) -> tuple[str, int, list[RankedContextItem]]:
    feature_id, feature_score, ranked, _ = rank_records_with_stats(
        records,
        task=task,
        include_history=include_history,
        retrieval_tier=retrieval_tier,
    )
    return feature_id, feature_score, ranked


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
        "direct terms:",
        "direct structured terms:",
        "exact task phrase",
        "exact repository path",
        "exact filename",
        "exact public symbol:",
        "quoted phrase:",
        "canonical feature boundary",
        "curated vertical-slice anchor",
        "owner-domain match",
        "matching path identifiers",
        "matching API route",
        "matching state surface",
        "dependency of a top match",
        "dependent of a top match",
        "associated test for a top match",
    )
    return any(reason.startswith(prefixes) for reason in item.reasons)


def _has_blocking_intent_mismatch(item: RankedContextItem, profile: TaskProfile) -> bool:
    if not profile.intents:
        return False
    mismatch = f"{profile.intents[0]} intent mismatch"
    exact_override = (
        "exact repository path",
        "exact filename",
        "exact public symbol:",
        "quoted phrase:",
    )
    return mismatch in item.reasons and not any(reason.startswith(exact_override) for reason in item.reasons)


def _capsule_with_items(
    *,
    task: str,
    budget: int,
    feature_id: str,
    feature_score: int,
    ranked: list[RankedContextItem],
    relevant_count: int,
    retrieval_stats: RetrievalStats,
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
    suggested = tuple(spec.keywords[:6]) if spec else tuple(sorted(retrieval_terms_for(task))[:6])
    omission_reasons: list[str] = []
    low_relevance_count = max(0, len(ranked) - relevant_count)
    budget_omitted_count = max(0, relevant_count - len(items))
    if low_relevance_count:
        omission_reasons.append(f"{low_relevance_count} records lacked direct task evidence or intent alignment")
    if budget_omitted_count:
        omission_reasons.append(f"{budget_omitted_count} relevant records did not fit the requested token budget")
    policy_excluded_count = retrieval_stats.catalog_count - retrieval_stats.eligible_count
    prefilter_excluded_count = retrieval_stats.eligible_count - retrieval_stats.candidate_count
    if prefilter_excluded_count:
        omission_reasons.append(
            f"{prefilter_excluded_count} eligible records had no direct task, feature, or relationship match"
        )
    if policy_excluded_count:
        omission_reasons.append(
            f"{policy_excluded_count} records were excluded by the {retrieval_stats.tier} retrieval tier"
        )
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
        omitted_count=max(0, retrieval_stats.catalog_count - len(items)),
        high_risk_relevant=high_risk,
        validation_rungs=validation,
        state_files=state_files,
        suggested_terms=suggested,
        truncation_notes=truncation_notes,
        omission_reasons=tuple(omission_reasons),
        retrieval_stats=retrieval_stats,
    )


def _finalize_estimate(capsule: ContextCapsule, output_format: str) -> ContextCapsule:
    current = capsule
    for _ in range(10):
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
    retrieval_tier: str = RETRIEVAL_TIER_ACTIVE,
    output_format: str = "markdown",
) -> ContextCapsule:
    if budget < 200:
        raise ValueError("budget must be at least 200 estimated tokens")
    record_list = list(records)
    profile = _task_profile(task)
    feature_id, feature_score, ranked, retrieval_stats = rank_records_with_stats(
        record_list,
        task=task,
        include_history=include_history,
        retrieval_tier=retrieval_tier,
    )
    direct_scores = [item.score for item in ranked if _has_direct_task_evidence(item)]
    # Authority/priority bonuses can make a record score highly even when the
    # task vocabulary matched nothing. Feature confidence therefore remains
    # decisive low-confidence signal unless an exact path/symbol match exists.
    low_confidence = feature_score < 8 and max(direct_scores, default=0) < 45
    if profile.documentation_only:
        relevant = [
            item
            for item in ranked
            if item.record.evidence_category == "documentation"
            and item.score >= 20
            and _has_task_relevance(item)
        ]
    elif low_confidence:
        relevant = [item for item in ranked if item.score >= 30 and _has_direct_task_evidence(item)][:8]
    else:
        relevant = [
            item
            for item in ranked
            if item.score >= 22
            and _has_task_relevance(item)
            and not _has_blocking_intent_mismatch(item, profile)
        ]

    # Curated anchors are preferred only for a confident feature match. The
    # remaining candidates preserve global score order; no unrelated layer is
    # forced into the capsule merely to create a vertical slice.
    selected: list[RankedContextItem] = []
    selected_paths: set[str] = set()
    spec = feature_spec(feature_id)
    high_risk_match = any(
        item.record.risk_tier == "high"
        and item.record.evidence_category == "production"
        and item.score >= 20
        for item in relevant
    )
    if spec and (feature_score >= 12 or high_risk_match):
        ranked_by_path = {item.record.path: item for item in relevant}
        seed_paths = (
            (*spec.boundary_docs, *spec.anchor_paths)
            if feature_score >= 12
            else spec.boundary_docs
        )
        for path in seed_paths:
            candidate = ranked_by_path.get(path)
            if candidate and path not in selected_paths:
                selected.append(candidate)
                selected_paths.add(path)
    directory_counts: dict[str, int] = {}
    deferred: list[RankedContextItem] = []
    for item in relevant:
        if item.record.path not in selected_paths:
            directory = item.record.path.rsplit("/", 1)[0] if "/" in item.record.path else ""
            if directory_counts.get(directory, 0) >= 3:
                deferred.append(item)
                continue
            selected.append(item)
            selected_paths.add(item.record.path)
            directory_counts[directory] = directory_counts.get(directory, 0) + 1
    for item in deferred:
        if item.record.path not in selected_paths:
            selected.append(item)
            selected_paths.add(item.record.path)

    fitted: list[RankedContextItem] = []
    for item in selected:
        trial = fitted + [item]
        trial_capsule = _capsule_with_items(
            task=task,
            budget=budget,
            feature_id=feature_id,
            feature_score=feature_score,
            ranked=ranked,
            relevant_count=len(relevant),
            retrieval_stats=retrieval_stats,
            items=trial,
            low_confidence=low_confidence,
            truncation_notes=("lower-ranked secondary results omitted to honor the requested budget",)
            if len(trial) < len(relevant)
            else (),
        )
        trial_capsule = _finalize_estimate(trial_capsule, output_format)
        if trial_capsule.estimated_tokens <= budget:
            fitted = trial
        elif fitted:
            # Records are already ranked. Once the next record breaches the
            # budget, avoid re-serializing the same full capsule for every
            # lower-ranked candidate in a large catalog.
            break

    notes = (
        ("lower-ranked secondary results omitted to honor the requested budget",)
        if len(fitted) < len(relevant)
        else ()
    )
    capsule = _capsule_with_items(
        task=task,
        budget=budget,
        feature_id=feature_id,
        feature_score=feature_score,
        ranked=ranked,
        relevant_count=len(relevant),
        retrieval_stats=retrieval_stats,
        items=fitted,
        low_confidence=low_confidence,
        truncation_notes=notes,
    )
    capsule = _finalize_estimate(capsule, output_format)
    # Remove fitted records until the final rendered bytes are within the hard
    # requested limit. Small budgets use the compact renderer below.
    while capsule.estimated_tokens > budget and capsule.items:
        capsule = _capsule_with_items(
            task=task,
            budget=budget,
            feature_id=feature_id,
            feature_score=feature_score,
            ranked=ranked,
            relevant_count=len(relevant),
            retrieval_stats=retrieval_stats,
            items=list(capsule.items[:-1]),
            low_confidence=low_confidence,
            truncation_notes=notes,
        )
        capsule = _finalize_estimate(capsule, output_format)
    if capsule.estimated_tokens > budget:
        raise ValueError(f"requested budget {budget} is too small for capsule metadata")
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


def _retrieval_stats_to_dict(stats: RetrievalStats) -> dict[str, object]:
    return {
        "tier": stats.tier,
        "catalog_count": stats.catalog_count,
        "eligible_count": stats.eligible_count,
        "candidate_count": stats.candidate_count,
        "candidate_bytes": stats.candidate_bytes,
    }


def render_capsule(capsule: ContextCapsule, *, output_format: str = "markdown") -> str:
    if output_format == "json":
        if capsule.requested_budget <= 400:
            compact_payload = {
                "estimated_tokens": capsule.estimated_tokens,
                "feature_id": capsule.feature_id,
                "high_risk_relevant": capsule.high_risk_relevant,
                "items": [
                    {"path": item.record.path, "score": item.score, "why": list(item.reasons[:2])}
                    for item in capsule.items
                ],
                "low_confidence": capsule.low_confidence,
                "omission_reasons": list(capsule.omission_reasons),
                "requested_budget": capsule.requested_budget,
                "retrieval": _retrieval_stats_to_dict(capsule.retrieval_stats),
                "task": capsule.task,
            }
            return json.dumps(compact_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
        payload = {
            "task": capsule.task,
            "requested_budget": capsule.requested_budget,
            "retrieval": _retrieval_stats_to_dict(capsule.retrieval_stats),
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
            "omission_reasons": list(capsule.omission_reasons),
            "truncation_notes": list(capsule.truncation_notes),
            "suggested_terms": list(capsule.suggested_terms),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if capsule.requested_budget <= 400:
        lines = [
            "# Task context capsule",
            f"Task: {capsule.task}",
            f"Feature: `{capsule.feature_id}`",
        ]
        if capsule.low_confidence:
            lines.append("No confident feature match; refine the task.")
        for item in capsule.items:
            lines.append(f"- `{item.record.path}` — Why: {'; '.join(item.reasons[:2])}.")
        lines.append(f"Budget: {capsule.estimated_tokens}/{capsule.requested_budget} estimated tokens.")
        lines.append(
            "Retrieval: "
            f"{capsule.retrieval_stats.candidate_count}/{capsule.retrieval_stats.eligible_count} candidates, "
            f"{capsule.retrieval_stats.candidate_bytes} bytes ({capsule.retrieval_stats.tier} tier)."
        )
        lines.extend(f"Omitted: {reason}." for reason in capsule.omission_reasons)
        return "\n".join(lines) + "\n"

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
            "Retrieval candidates: "
            f"**{capsule.retrieval_stats.candidate_count}** / {capsule.retrieval_stats.eligible_count} eligible "
            f"({capsule.retrieval_stats.candidate_bytes} compact JSONL bytes; `{capsule.retrieval_stats.tier}` tier).",
            f"Omitted matching records: **{capsule.omitted_count}**.",
        )
    )
    for note in capsule.truncation_notes:
        lines.append(f"- {note}")
    for reason in capsule.omission_reasons:
        lines.append(f"- Omitted: {reason}.")
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
        if estimate_tokens(rendered) > 3000:
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
    parser.add_argument(
        "--retrieval-tier",
        choices=RETRIEVAL_TIERS,
        default=RETRIEVAL_TIER_ACTIVE,
        help="Retrieval scope: active (default), history, or all generated/runtime evidence.",
    )
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="Compatibility alias that promotes the active tier to history.",
    )
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
            retrieval_tier=args.retrieval_tier,
            output_format=args.format,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(render_capsule(capsule, output_format=args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
