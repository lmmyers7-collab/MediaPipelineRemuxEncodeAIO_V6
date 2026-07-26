"""Build the authoritative typed record catalog for generated AI navigation."""

from __future__ import annotations

import ast
import json
import re
import unicodedata
from functools import lru_cache
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

from mediapipeline.tools.dev import generate_dependency_atlas, refresh_summaries
from mediapipeline.tools.dev.context_extractors import (
    GENERATED_NAVIGATION_FILES,
    GENERATED_NAVIGATION_PREFIXES,
    ExtractedSource,
    extract_source,
    is_generated_navigation_output,
)
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
CONTEXT_RECORD_SCHEMA_VERSION = 1
DEFAULT_EXCLUDED_EVIDENCE = frozenset(
    {"archive", "runtime_artifact", "generated", "change_evidence"}
)
RETRIEVAL_TIER_ACTIVE = "active"
RETRIEVAL_TIER_HISTORY = "history"
RETRIEVAL_TIER_ALL = "all"
RETRIEVAL_TIERS = (
    RETRIEVAL_TIER_ACTIVE,
    RETRIEVAL_TIER_HISTORY,
    RETRIEVAL_TIER_ALL,
)
ACTIVE_LOW_VALUE_PREFIXES = (
    "docs/ai-audits/",
    "docs/reviews/",
)
OPT_IN_PATH_PARTS = frozenset(
    {"fixture", "fixtures", "snapshot", "snapshots", "testdata"}
)

@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    label: str
    keywords: tuple[str, ...]
    selectors: tuple[str, ...]
    owner_domains: tuple[str, ...]
    boundary_docs: tuple[str, ...] = ()
    validation: str = "targeted unit tests"
    anchor_paths: tuple[str, ...] = ()


FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "tauri-lifecycle",
        "Tauri shell and backend lifecycle",
        ("tauri", "tauri close readiness", "close", "readiness", "shutdown", "single instance", "webview2", "bootstrap"),
        ("apps/desktop/tauri/", "tests/python/desktop/test_tauri_shell", "tests/webview/test_webview_tauri"),
        ("shell", "process", "api"),
        ("docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md",),
        "Tauri CheckOnly, shell checks, and affected lifecycle tests",
        (
            "apps/desktop/tauri/src-tauri/src/close_readiness.rs",
            "apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs",
            "src/mediapipeline/desktop/api/contract_read.py",
            "tests/python/desktop/test_application_facade_close_readiness.py",
            "docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md",
        ),
    ),
    FeatureSpec(
        "local-api",
        "Local API routes, contracts, and mutation ownership",
        ("local api", "route", "http", "endpoint", "strict json", "command journal", "contract"),
        ("src/mediapipeline/desktop/api/", "docs/inventories/API_ROUTE_INVENTORY.md", "docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md"),
        ("api", "contracts"),
        ("docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md",),
        "targeted route and strict-JSON contract tests",
    ),
    FeatureSpec(
        "desktop-application",
        "Desktop application facade and operator DTOs",
        ("application facade", "desktop service", "operator dto", "facade", "application"),
        ("src/mediapipeline/desktop/application/", "src/mediapipeline/desktop/services.py", "tests/python/desktop/test_application_facade"),
        ("application",),
    ),
    FeatureSpec(
        "webview",
        "WebView operator surface",
        ("webview", "display name", "dom", "operator surface", "javascript", "browser", "table", "view"),
        ("apps/desktop/webview/static/", "tests/webview/", "docs/inventories/WEBVIEW_", "docs/generated/WEBVIEW_"),
        ("webview",),
        validation="targeted WebView static checks and affected browser smoke",
    ),
    FeatureSpec(
        "settings-config",
        "Settings, config schema, and library profiles",
        ("settings", "config", "configuration", "library profile", "schema", "psd1"),
        ("src/mediapipeline/core/config/", "ops/pipeline/config/", "src/mediapipeline/contracts/config.py", "src/mediapipeline/contracts/schemas/config"),
        ("config", "contracts"),
        boundary_docs=("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",),
        validation="targeted config/store/schema tests",
    ),
    FeatureSpec(
        "queue-launch",
        "Queue, source scanning, and launch planning",
        ("queue", "queue snapshot", "webview queue", "queue display name", "launch", "source scan", "priority", "hold", "rerun", "schedule", "display name", "naming"),
        ("src/mediapipeline/core/queue/", "ops/pipeline/engine/queue/", "apps/desktop/webview/static/assets/queue", "tests/python/desktop/test_service_queue", "ops/pipeline/tests/Unit/Invoke-PipelineQueue"),
        ("queue", "schedule", "ingest", "application"),
        boundary_docs=("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",),
        validation="targeted queue, launch, and WebView tests",
        anchor_paths=(
            "apps/desktop/webview/static/assets/queue/sourceModel.js",
            "apps/desktop/webview/static/assets/queue/table.js",
            "src/mediapipeline/core/queue/contracts.py",
            "src/mediapipeline/core/queue/snapshot.py",
            "tests/python/desktop/test_service_queue_snapshot.py",
            "tests/webview/test_webview_browser_large_table_smoke.py",
        ),
    ),
    FeatureSpec(
        "media-processing",
        "Media decisions, FFmpeg entrypoints, and processing",
        ("ffmpeg", "ffprobe", "encode", "remux", "transcode", "stream map", "media processing", "route selection"),
        ("src/mediapipeline/core/decide/", "src/mediapipeline/core/processes/", "src/mediapipeline/core/transcode/", "ops/pipeline/engine/decide/", "ops/pipeline/engine/process/", "ops/pipeline/entrypoints/MediaPipeline/"),
        ("decide", "process", "transcode"),
        ("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",),
        "pipeline reliability checks, release gate, and representative real-media validation when behavior changes",
    ),
    FeatureSpec(
        "subtitles-audio",
        "Subtitles, audio, and stream sidecars",
        ("subtitle", "audio", "ass", "srt", "pgs", "ocr", "sidecar", "stream", "downmix"),
        ("src/mediapipeline/pipeline/ass_to_srt", "src/mediapipeline/core/subtitles/", "src/mediapipeline/core/audio/", "ops/pipeline/engine/subtitles/", "ops/pipeline/engine/audio/", "ops/pipeline/tests/Unit/Invoke-Subtitle", "ops/pipeline/tests/Unit/Invoke-Audio"),
        ("subtitles", "audio", "contracts"),
        ("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",),
        "subtitle/audio unit checks, release gate, and representative real-media validation when behavior changes",
        (
            "src/mediapipeline/pipeline/ass_to_srt_cli.py",
            "src/mediapipeline/pipeline/ass_to_srt/ass_events.py",
            "src/mediapipeline/contracts/subtitles.py",
            "ops/pipeline/engine/subtitles/ass.ps1",
            "tests/python/core/subtitles/test_ass_to_srt_helpers.py",
            "docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",
        ),
    ),
    FeatureSpec(
        "pending-publish",
        "Completed outputs, pending publish, drain, and final library",
        ("pending publish", "drain", "park", "manifest", "final library", "promotion", "completed output", "readiness"),
        ("src/mediapipeline/core/completed/", "src/mediapipeline/core/publish/", "src/mediapipeline/core/final_library/", "ops/pipeline/engine/publish/", "apps/desktop/webview/static/assets/pending", "tests/python/desktop/test_pending", "tests/python/desktop/test_final_library"),
        ("publish", "completed", "final_library"),
        ("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md", "docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md"),
        "targeted pending-publish tests, release gate, and real-media validation only when publish behavior changes",
        (
            "src/mediapipeline/core/publish/pending_service.py",
            "src/mediapipeline/core/publish/pending_manifest.py",
            "ops/pipeline/engine/publish/pending_drain_transaction.ps1",
            "tests/python/desktop/test_pending_publish_service.py",
            "docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",
            "docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md",
        ),
    ),
    FeatureSpec(
        "rename",
        "Rename planning, apply safety, and evidence",
        ("rename", "collision", "undo", "preview", "path boundary", "sidecar"),
        ("src/mediapipeline/core/rename/", "apps/desktop/webview/static/assets/rename", "tests/python/desktop/test_application_facade_rename", "tests/webview/test_webview_browser_rename"),
        ("rename",),
        ("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",),
        "targeted rename preview/apply/undo and path-boundary tests",
    ),
    FeatureSpec(
        "diagnostics-maintenance",
        "Diagnostics, maintenance, and sample validation",
        ("diagnostics", "maintenance", "repair", "reconcile", "sample validation", "audit", "metrics"),
        ("src/mediapipeline/core/diagnostics/", "src/mediapipeline/core/maintenance/", "src/mediapipeline/core/sample_validation/", "src/mediapipeline/desktop/application/sample_validation/", "apps/desktop/webview/static/assets/diagnostics", "tests/python/desktop/test_service_tdarr_matrix_audit"),
        ("diagnostics", "maintenance", "sample_validation", "metrics", "audit"),
    ),
    FeatureSpec(
        "storage-runtime",
        "Storage, paths, runtime state, and process guards",
        ("storage", "runtime state", "path", "process guard", "active job", "journal", "close readiness"),
        ("src/mediapipeline/core/storage/", "src/mediapipeline/core/paths/", "src/mediapipeline/core/processes/", "ops/pipeline/engine/storage/", "ops/pipeline/engine/paths/", "docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md"),
        ("storage", "paths", "process", "observability"),
        validation="targeted storage, process, and lifecycle tests",
    ),
    FeatureSpec(
        "network-mode",
        "Distributed worker and network mode",
        ("network", "worker", "coordinator", "claim", "release", "watch folder", "distributed"),
        ("src/mediapipeline/desktop/network/", "src/mediapipeline/desktop/watch/", "tests/python/desktop/test_network", "tests/python/desktop/test_watch_folder"),
        ("network", "watch"),
        ("docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",),
        "targeted coordinator, worker, identity, and recovery tests",
    ),
    FeatureSpec(
        "generated-context",
        "Generated context and AI navigation guardrails",
        (
            "generated context",
            "project index",
            "summary",
            "context slice",
            "context capsule",
            "task capsule",
            "feature card",
            "ai guardrail",
            "ai token usage",
            "token usage",
            "retrieval ranking",
            "repository navigation",
        ),
        ("src/mediapipeline/tools/dev/", "docs/generated/", "tests/python/tooling/", "AGENTS.md"),
        ("scripts",),
        validation="targeted tooling tests and generated-output --check modes",
        anchor_paths=(
            "src/mediapipeline/tools/dev/context_slice.py",
            "src/mediapipeline/tools/dev/context_records.py",
            "src/mediapipeline/tools/dev/context_extractors.py",
            "tests/python/tooling/test_context_slice.py",
            "tests/python/tooling/test_context_records.py",
        ),
    ),
    FeatureSpec(
        "release-validation",
        "PowerShell release, smoke, and validation wrappers",
        ("release", "package", "smoke", "validation", "guardrail", "change packet"),
        ("ops/scripts/", "ops/pipeline/tests/", "docs/testing/", "docs/change_control/"),
        ("scripts", "validation"),
        validation="affected smoke checks and release self-test when packaging changes",
    ),
)
REQUIRED_FEATURE_IDS = tuple(spec.feature_id for spec in FEATURE_SPECS)


@dataclass(frozen=True)
class ContextRecord:
    path: str
    file_type: str
    purpose: str
    owner_domain: str
    feature_group: str
    pipeline_stage: str
    token_priority: str
    source_hash: str
    evidence_category: str
    layer: str
    authority: str
    risk_tier: str
    validation_rung: str
    public_symbols: tuple[str, ...] = ()
    outbound_dependencies: tuple[str, ...] = ()
    inbound_dependents: tuple[str, ...] = ()
    associated_tests: tuple[str, ...] = ()
    api_routes: tuple[str, ...] = ()
    state_files: tuple[str, ...] = ()
    dom_selectors: tuple[str, ...] = ()
    invoked_stages: tuple[str, ...] = ()
    invoked_tools: tuple[str, ...] = ()
    feature_groups: tuple[str, ...] = ()
    relevance_terms: tuple[str, ...] = ()
    schema_version: int = CONTEXT_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def canonical_path(path: str | Path) -> str:
    value = str(path).replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return PurePosixPath(value).as_posix()


def normalize_retrieval_tier(
    retrieval_tier: str = RETRIEVAL_TIER_ACTIVE,
    *,
    include_history: bool = False,
) -> str:
    normalized = retrieval_tier.strip().casefold()
    if include_history and normalized == RETRIEVAL_TIER_ACTIVE:
        normalized = RETRIEVAL_TIER_HISTORY
    if normalized not in RETRIEVAL_TIERS:
        raise ValueError(f"retrieval tier must be one of: {', '.join(RETRIEVAL_TIERS)}")
    return normalized


def record_is_retrievable(record: ContextRecord, retrieval_tier: str) -> bool:
    """Return whether a catalog record participates in the requested tier."""

    tier = normalize_retrieval_tier(retrieval_tier)
    if tier == RETRIEVAL_TIER_ALL:
        return True
    if record.evidence_category in {"generated", "runtime_artifact"}:
        return False
    normalized = canonical_path(record.path).casefold()
    parts = {part.casefold() for part in PurePosixPath(normalized).parts}
    if parts.intersection(OPT_IN_PATH_PARTS):
        return False
    if tier == RETRIEVAL_TIER_ACTIVE:
        if record.evidence_category in {"archive", "change_evidence"}:
            return False
        if any(normalized.startswith(prefix) for prefix in ACTIVE_LOW_VALUE_PREFIXES):
            return False
    return True


def record_serialized_size_bytes(record: ContextRecord) -> int:
    """Measure compact JSONL bytes considered when a record is ranked."""

    serialized = json.dumps(
        record.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return len((serialized + "\n").encode("utf-8"))


def evidence_category_for(path: str) -> str:
    normalized = canonical_path(path)
    lowered = normalized.casefold()
    if lowered.startswith(("docs/archive/", "archive/")):
        return "archive"
    if lowered.startswith("ops/release/changes/"):
        return "change_evidence"
    if lowered.startswith(("localbase/", "apps/desktop/runtime/")) or "/runtime/" in lowered:
        return "runtime_artifact"
    if lowered.startswith("docs/generated/"):
        return "generated"
    if lowered.startswith("tests/") or lowered.startswith("ops/pipeline/tests/"):
        return "test"
    if lowered.startswith("docs/") or lowered.endswith("agents.md") or lowered == "readme.md":
        return "documentation"
    return "production"


def owner_domain_for(path: str) -> str:
    owner = refresh_summaries.owner_domain_for(path)
    if owner != "unknown":
        return owner
    parts = PurePosixPath(canonical_path(path)).parts
    if path.startswith("docs/"):
        return "documentation"
    if path.startswith("ops/release/changes/"):
        return "release_evidence"
    if path.startswith("ops/"):
        return parts[2] if len(parts) > 2 else "operations"
    if path.startswith("src/mediapipeline/"):
        return parts[2] if len(parts) > 2 else "python"
    if path.startswith("apps/desktop/tauri/"):
        return "shell"
    if path.startswith("apps/desktop/webview/"):
        return "webview"
    return "repository"


def token_priority_for(path: str, evidence_category: str) -> str:
    lowered = canonical_path(path).casefold()
    if evidence_category != "production":
        return "low"
    existing = refresh_summaries.token_priority_for(path)
    if existing == "high":
        return "high"
    authority_markers = (
        "/api/",
        "/entrypoints/",
        "facade",
        "service",
        "policy",
        "contract",
        "handler",
        "runner",
        "orchestrat",
        "lifecycle",
        "publish",
        "queue",
        "rename",
        "subtitles",
        "audio",
        "transcode",
        "process",
    )
    if any(marker in lowered for marker in authority_markers):
        return "high"
    if lowered.endswith(("/__init__.py", ".css", ".html")) or any(
        marker in lowered for marker in ("/fixtures/", "/constants", "/labels", "/tokens")
    ):
        return "low"
    return "medium"


def layer_for(path: str, evidence_category: str) -> str:
    normalized = canonical_path(path)
    if evidence_category == "test":
        return "tests"
    if normalized.startswith("apps/desktop/"):
        return "webview-tauri"
    if normalized.startswith("src/mediapipeline/desktop/api/"):
        return "local-api"
    if normalized.startswith("src/mediapipeline/"):
        if "/contracts/" in normalized or "/config/" in normalized:
            return "state-config"
        return "python-domain"
    if normalized.startswith(("ops/pipeline/engine/", "ops/pipeline/entrypoints/")):
        return "powershell-engine"
    if normalized.startswith("ops/pipeline/config/") or "STATE_FILE" in normalized.upper():
        return "state-config"
    if normalized.startswith("docs/"):
        if any(part in normalized for part in ("/operator/", "/testing/", "/architecture/", "/inventories/")):
            return "boundary-validation-docs"
        return "secondary-evidence"
    return "secondary-evidence"


def authority_for(path: str, evidence_category: str, layer: str) -> str:
    lowered = canonical_path(path).casefold()
    if evidence_category == "test":
        return "verification-evidence"
    if evidence_category in {"archive", "change_evidence", "generated"}:
        return "secondary-evidence"
    if layer == "boundary-validation-docs":
        return "canonical-boundary"
    if layer == "webview-tauri" and "/webview/" in lowered:
        return "frontend-display-and-intent"
    if layer == "local-api":
        return "backend-route-adapter"
    if layer in {"python-domain", "powershell-engine", "state-config"}:
        mutation_terms = ("apply", "drain", "publish", "rename", "delete", "write", "save", "launch", "process", "queue")
        return "backend-mutation-authority" if any(term in lowered for term in mutation_terms) else "backend-authority"
    return "supporting-evidence"


def risk_tier_for(path: str, authority: str) -> str:
    lowered = canonical_path(path).casefold()
    high_risk = (
        "ffmpeg",
        "transcode",
        "subtitle",
        "audio",
        "publish",
        "final_library",
        "rename",
        "network",
        "queue",
        "settings",
        "config",
        "lifecycle",
        "process",
    )
    if any(term in lowered for term in high_risk) and authority.startswith("backend"):
        return "high"
    if authority in {"backend-mutation-authority", "backend-route-adapter", "canonical-boundary"}:
        return "medium"
    return "low"


def validation_rung_for(path: str, feature_id: str, evidence_category: str) -> str:
    if evidence_category == "documentation":
        return "documentation reference checks and generated-context drift checks"
    spec = feature_spec(feature_id)
    if spec:
        return spec.validation
    if evidence_category == "test":
        return "run the owning targeted test"
    return "targeted unit tests for the owning domain"


_WORD_RE = re.compile(r"[a-z0-9]+")
_UNICODE_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_IDENTIFIER_SEPARATOR_RE = re.compile(r"[_./\\:#-]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "might",
        "must",
        "of",
        "on",
        "or",
        "should",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)
LOW_INFORMATION_TERMS = frozenset(
    {
        "analyze",
        "cleanup",
        "codebase",
        "excessive",
        "file",
        "files",
        "find",
        "identify",
        "improve",
        "improvement",
        "improvements",
        "issue",
        "issues",
        "opportunities",
        "opportunity",
        "related",
        "relevant",
        "request",
        "requests",
        "source",
        "sources",
        "specific",
        "task",
        "tasks",
        "usage",
    }
)


def terms_for(*values: object) -> tuple[str, ...]:
    text = " ".join(str(value) for value in values if value)
    return tuple(sorted({word for word in _WORD_RE.findall(text.casefold()) if word not in _STOP_WORDS and len(word) > 1}))


@lru_cache(maxsize=65536)
def _normalize_retrieval_text_cached(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    expanded = _IDENTIFIER_SEPARATOR_RE.sub(" ", _CAMEL_BOUNDARY_RE.sub(" ", normalized))
    return " ".join(expanded.casefold().split())


def normalize_retrieval_text(*values: object) -> str:
    """Normalize user-facing retrieval text without changing catalog serialization."""

    return _normalize_retrieval_text_cached(" ".join(str(value) for value in values if value))


@lru_cache(maxsize=65536)
def _retrieval_terms_cached(raw: str, include_low_information: bool) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", raw)
    expanded = _IDENTIFIER_SEPARATOR_RE.sub(" ", _CAMEL_BOUNDARY_RE.sub(" ", normalized))
    excluded = _STOP_WORDS if include_low_information else _STOP_WORDS | LOW_INFORMATION_TERMS
    words = {
        word.casefold()
        for word in _UNICODE_WORD_RE.findall(expanded)
        if word.casefold() not in excluded and len(word) > 1
    }
    compact_identifiers = {
        word.casefold()
        for word in _UNICODE_WORD_RE.findall(_IDENTIFIER_SEPARATOR_RE.sub(" ", normalized))
        if word.casefold() not in excluded and len(word) > 1
    }
    return tuple(sorted(words | compact_identifiers))


def retrieval_terms_for(
    *values: object,
    include_low_information: bool = False,
) -> tuple[str, ...]:
    """Return Unicode- and identifier-aware terms for live retrieval."""

    raw = " ".join(str(value) for value in values if value)
    return _retrieval_terms_cached(raw, include_low_information)


def low_information_terms_for(*values: object) -> tuple[str, ...]:
    """Return generic request terms retained only for diagnostics and penalties."""

    all_terms = set(retrieval_terms_for(*values, include_low_information=True))
    return tuple(sorted(all_terms.intersection(LOW_INFORMATION_TERMS)))


def _selector_matches(path: str, selector: str) -> bool:
    selector = canonical_path(selector)
    return path == selector or path.startswith(selector)


def feature_scores(path: str, owner_domain: str, extracted: ExtractedSource) -> list[tuple[int, str]]:
    haystack = " ".join(
        (
            path,
            owner_domain,
            extracted.purpose,
            " ".join(extracted.public_symbols),
            " ".join(extracted.api_routes),
            " ".join(extracted.state_files),
        )
    ).casefold()
    scores: list[tuple[int, str]] = []
    for spec in FEATURE_SPECS:
        score = 0
        if any(_selector_matches(path, selector) for selector in spec.selectors):
            score += 12
        if owner_domain in spec.owner_domains:
            score += 5
        score += sum(3 for keyword in spec.keywords if keyword.casefold() in haystack)
        if path in spec.boundary_docs:
            score += 14
        # A shared owner domain or one generic keyword is not enough to claim a
        # feature relationship. Requiring combined evidence prevents broad
        # domains such as process/scripts from polluting vertical slices.
        if score >= 8:
            scores.append((score, spec.feature_id))
    return sorted(scores, key=lambda item: (-item[0], item[1]))


def feature_spec(feature_id: str) -> FeatureSpec | None:
    return next((spec for spec in FEATURE_SPECS if spec.feature_id == feature_id), None)


def _resolve_relative_dependency(root: Path, source_path: Path, token: str) -> str | None:
    cleaned = token.strip().strip("'\"").replace("\\", "/")
    if not cleaned:
        return None
    if cleaned.casefold().startswith("$psscriptroot"):
        cleaned = cleaned[len("$PSScriptRoot") :].lstrip("/\\")
        candidate = source_path.parent / cleaned
    elif cleaned.startswith("."):
        candidate = source_path.parent / cleaned
    else:
        return None
    candidates = [candidate]
    if not candidate.suffix:
        candidates.extend(candidate.with_suffix(suffix) for suffix in (".py", ".js", ".mjs", ".ps1", ".psm1"))
        candidates.extend((candidate / f"index{suffix}") for suffix in (".js", ".mjs"))
    root_resolved = root.resolve()
    for item in candidates:
        try:
            resolved = item.resolve()
            rel = resolved.relative_to(root_resolved).as_posix()
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            return rel
    return None


def _python_edges(root: Path, source_paths: Sequence[Path]) -> dict[str, set[str]]:
    package_roots = tuple(
        (name, root / relative)
        for name, relative in (
            ("mediapipeline.core", "src/mediapipeline/core"),
            ("mediapipeline.contracts", "src/mediapipeline/contracts"),
            ("mediapipeline.desktop", "src/mediapipeline/desktop"),
            ("mediapipeline.pipeline", "src/mediapipeline/pipeline"),
            ("mediapipeline.tools", "src/mediapipeline/tools"),
            ("tests", "tests"),
        )
    )
    index = generate_dependency_atlas.iter_python_modules(package_roots)
    allowed = {path.resolve() for path in source_paths if path.suffix.lower() == ".py"}
    edges: dict[str, set[str]] = defaultdict(set)
    for source_path, module_name in index.path_modules.items():
        if source_path.resolve() not in allowed:
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8", errors="replace"), filename=str(source_path))
        except SyntaxError:
            continue
        source_rel = source_path.resolve().relative_to(root.resolve()).as_posix()
        for target_module in generate_dependency_atlas.import_targets(tree, module_name, source_path, index):
            target_path = index.module_paths.get(target_module)
            if target_path is None:
                continue
            try:
                edges[source_rel].add(target_path.resolve().relative_to(root.resolve()).as_posix())
            except ValueError:
                continue
    return edges


def _candidate_sources(root: Path, paths: Iterable[Path] | None) -> list[Path]:
    if paths is not None:
        candidates = list(paths)
    elif root.resolve() == REPO_ROOT.resolve():
        candidates = list(refresh_summaries.iter_known_source_files())
    else:
        candidates = [path for path in root.rglob("*") if path.is_file()]
    output: dict[str, Path] = {}
    root_resolved = root.resolve()
    for path in candidates:
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(root_resolved).as_posix()
        except (OSError, ValueError):
            continue
        if not resolved.is_file() or is_generated_navigation_output(rel):
            continue
        output[rel] = resolved
    return [output[key] for key in sorted(output, key=lambda value: (value.casefold(), value))]


def collect_context_records(
    root: Path = REPO_ROOT,
    paths: Iterable[Path] | None = None,
) -> list[ContextRecord]:
    """Collect typed records directly from source plus canonical indexed docs."""
    root = root.resolve()
    source_paths = _candidate_sources(root, paths)
    python_edges = _python_edges(root, source_paths)
    extracted_by_path: dict[str, ExtractedSource] = {}
    for source in source_paths:
        rel = source.relative_to(root).as_posix()
        extracted_by_path[rel] = extract_source(source, rel)

    base_records: list[ContextRecord] = []
    for source in source_paths:
        rel = source.relative_to(root).as_posix()
        extracted = extracted_by_path[rel]
        category = evidence_category_for(rel)
        owner = owner_domain_for(rel)
        scores = feature_scores(rel, owner, extracted)
        groups = tuple(feature_id for _, feature_id in scores)
        feature_id = groups[0] if groups else "repository-general"
        layer = layer_for(rel, category)
        authority = authority_for(rel, category, layer)
        dependencies = set(python_edges.get(rel, set()))
        for token in extracted.dependencies:
            resolved = _resolve_relative_dependency(root, source, token)
            if resolved:
                dependencies.add(resolved)
        priority = token_priority_for(rel, category)
        record = ContextRecord(
            path=rel,
            file_type=extracted.file_type,
            purpose=extracted.purpose,
            owner_domain=owner,
            feature_group=feature_id,
            pipeline_stage=refresh_summaries.pipeline_stage_for(rel),
            token_priority=priority,
            source_hash=refresh_summaries.sha256_of(source),
            evidence_category=category,
            layer=layer,
            authority=authority,
            risk_tier=risk_tier_for(rel, authority),
            validation_rung=validation_rung_for(rel, feature_id, category),
            public_symbols=extracted.public_symbols,
            outbound_dependencies=tuple(sorted(dependencies, key=lambda value: (value.casefold(), value))),
            api_routes=extracted.api_routes,
            state_files=extracted.state_files,
            dom_selectors=extracted.dom_selectors,
            invoked_stages=extracted.invoked_stages,
            invoked_tools=extracted.invoked_tools,
            feature_groups=groups,
            relevance_terms=terms_for(
                rel,
                extracted.purpose,
                owner,
                feature_id,
                extracted.public_symbols,
                extracted.api_routes,
                extracted.state_files,
            ),
        )
        base_records.append(record)

    record_by_path = {record.path: record for record in base_records}
    inbound: dict[str, set[str]] = defaultdict(set)
    for record in base_records:
        for target in record.outbound_dependencies:
            if target in record_by_path:
                inbound[target].add(record.path)

    tests = [record for record in base_records if record.evidence_category == "test"]
    finalized: list[ContextRecord] = []
    for record in base_records:
        inbound_paths = tuple(sorted(inbound.get(record.path, set()), key=lambda value: (value.casefold(), value)))
        related_tests: set[str] = {
            path for path in inbound_paths if record_by_path[path].evidence_category == "test"
        }
        if record.evidence_category == "production":
            record_terms = set(record.relevance_terms)
            candidates: list[tuple[int, str]] = []
            for test in tests:
                score = 0
                if record.feature_group in test.feature_groups:
                    score += 8
                score += min(6, len(record_terms.intersection(test.relevance_terms)))
                if record.owner_domain and record.owner_domain in test.relevance_terms:
                    score += 2
                if score >= 5:
                    candidates.append((score, test.path))
            related_tests.update(path for _, path in sorted(candidates, key=lambda item: (-item[0], item[1]))[:8])
        finalized.append(
            replace(
                record,
                inbound_dependents=inbound_paths,
                associated_tests=tuple(sorted(related_tests, key=lambda value: (value.casefold(), value))[:10]),
            )
        )
    return sorted(finalized, key=lambda record: (record.path.casefold(), record.path))


def records_to_jsonl(records: Iterable[ContextRecord]) -> str:
    lines = [
        json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for record in sorted(records, key=lambda item: (item.path.casefold(), item.path))
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def records_from_jsonl(text: str) -> list[ContextRecord]:
    records: list[ContextRecord] = []
    tuple_fields = {
        "public_symbols",
        "outbound_dependencies",
        "inbound_dependents",
        "associated_tests",
        "api_routes",
        "state_files",
        "dom_selectors",
        "invoked_stages",
        "invoked_tools",
        "feature_groups",
        "relevance_terms",
    }
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("schema_version") != CONTEXT_RECORD_SCHEMA_VERSION:
            raise ValueError(f"Unsupported context-record schema on line {line_number}")
        for key in tuple_fields:
            payload[key] = tuple(payload.get(key, ()))
        records.append(ContextRecord(**payload))
    return records


def load_records(path: Path) -> list[ContextRecord]:
    return records_from_jsonl(path.read_text(encoding="utf-8"))


def validate_record_paths(records: Iterable[ContextRecord], root: Path = REPO_ROOT) -> list[str]:
    findings: list[str] = []
    root_resolved = root.resolve()
    for record in records:
        candidate = Path(record.path)
        if candidate.is_absolute():
            findings.append(f"absolute path is forbidden: {record.path}")
            continue
        try:
            resolved = (root_resolved / candidate).resolve()
            resolved.relative_to(root_resolved)
        except (OSError, ValueError):
            findings.append(f"path escapes repository: {record.path}")
            continue
        if not resolved.is_file():
            findings.append(f"record path does not exist: {record.path}")
        for related in (*record.outbound_dependencies, *record.inbound_dependents, *record.associated_tests):
            related_path = root_resolved / related
            if not related_path.is_file():
                findings.append(f"related path does not exist: {record.path} -> {related}")
    return sorted(set(findings), key=lambda value: (value.casefold(), value))


__all__ = [
    "ACTIVE_LOW_VALUE_PREFIXES",
    "CONTEXT_RECORD_SCHEMA_VERSION",
    "ContextRecord",
    "DEFAULT_EXCLUDED_EVIDENCE",
    "FEATURE_SPECS",
    "FeatureSpec",
    "GENERATED_NAVIGATION_FILES",
    "GENERATED_NAVIGATION_PREFIXES",
    "OPT_IN_PATH_PARTS",
    "RETRIEVAL_TIERS",
    "RETRIEVAL_TIER_ACTIVE",
    "RETRIEVAL_TIER_ALL",
    "RETRIEVAL_TIER_HISTORY",
    "REQUIRED_FEATURE_IDS",
    "LOW_INFORMATION_TERMS",
    "collect_context_records",
    "evidence_category_for",
    "feature_spec",
    "is_generated_navigation_output",
    "load_records",
    "low_information_terms_for",
    "normalize_retrieval_text",
    "normalize_retrieval_tier",
    "record_is_retrievable",
    "record_serialized_size_bytes",
    "records_from_jsonl",
    "records_to_jsonl",
    "retrieval_terms_for",
    "validate_record_paths",
]
