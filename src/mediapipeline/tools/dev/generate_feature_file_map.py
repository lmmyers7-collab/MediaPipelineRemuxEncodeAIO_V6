"""Generate ranked feature navigation and compact vertical-slice cards."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from mediapipeline.tools.dev.context_records import (
    FEATURE_SPECS,
    ContextRecord,
    FeatureSpec,
    authority_for,
    collect_context_records,
    evidence_category_for,
    feature_scores,
    layer_for,
    owner_domain_for,
    risk_tier_for,
    terms_for,
    token_priority_for,
    validate_record_paths,
    validation_rung_for,
)
from mediapipeline.tools.dev.context_extractors import ExtractedSource
from mediapipeline.tools.dev.release_package_scope import (
    is_release_excluded_path,
    release_excluded_prefixes,
)
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
GENERATED_DOCS_ROOT = REPO_ROOT / "docs" / "generated"
PROJECT_INDEX_PATH = GENERATED_DOCS_ROOT / "PROJECT_INDEX.md"
FEATURE_MAP_PATH = GENERATED_DOCS_ROOT / "FEATURE_FILE_MAP.md"
FEATURE_CARD_ROOT = GENERATED_DOCS_ROOT / "feature-cards"
RUN_COMMAND = (
    "apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py "
    "mediapipeline.tools.dev.generate_feature_file_map"
)
PROJECT_INDEX_ROW_RE = re.compile(r"^\| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (.*) \|$")
BACKTICK_RE = re.compile(r"`([^`]+)`")
LEGACY_ROOTS = ("app/", "DesktopApp/", "Pipeline/")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
AUTHORITY_RANK = {
    "backend-mutation-authority": 0,
    "backend-authority": 1,
    "backend-route-adapter": 2,
    "frontend-display-and-intent": 3,
    "canonical-boundary": 4,
    "verification-evidence": 5,
    "supporting-evidence": 6,
    "secondary-evidence": 7,
}
EVIDENCE_ORDER = (
    "production",
    "test",
    "documentation",
    "generated",
    "change_evidence",
    "archive",
    "runtime_artifact",
)
CARD_LAYER_ORDER = (
    "webview-tauri",
    "local-api",
    "python-domain",
    "state-config",
    "powershell-engine",
    "tests",
    "boundary-validation-docs",
)
CARD_LAYER_LABELS = {
    "webview-tauri": "WebView / Tauri",
    "local-api": "API route",
    "python-domain": "Python facade / domain service",
    "state-config": "Contract / state / config",
    "powershell-engine": "PowerShell execution",
    "tests": "Tests",
    "boundary-validation-docs": "Boundaries / validation",
}


@dataclass(frozen=True)
class IndexEntry:
    file: str
    domain: str
    priority: str
    stage: str
    purpose: str


@dataclass(frozen=True)
class FeatureGroup:
    label: str
    selectors: tuple[str, ...]
    limit: int = 12


@dataclass(frozen=True)
class PathReferenceFinding:
    path: str
    reason_code: str
    reason: str


# Compatibility surface for existing callers; the authoritative taxonomy is
# FEATURE_SPECS in context_records.py.
FEATURE_GROUPS: tuple[FeatureGroup, ...] = tuple(
    FeatureGroup(spec.label, spec.selectors) for spec in FEATURE_SPECS
)


def table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def parse_project_index(text: str) -> list[IndexEntry]:
    entries: list[IndexEntry] = []
    for line in text.splitlines():
        match = PROJECT_INDEX_ROW_RE.match(line)
        if match:
            entries.append(
                IndexEntry(
                    file=match.group(1),
                    domain=match.group(2).strip(),
                    priority=match.group(3).strip(),
                    stage=match.group(4).strip(),
                    purpose=match.group(5).strip(),
                )
            )
    return entries


def load_project_index() -> list[IndexEntry]:
    if not PROJECT_INDEX_PATH.exists():
        raise FileNotFoundError(f"Missing generated file: {PROJECT_INDEX_PATH.relative_to(REPO_ROOT)}")
    return parse_project_index(PROJECT_INDEX_PATH.read_text(encoding="utf-8", errors="replace"))


def selector_matches(path: str, selector: str) -> bool:
    normalized = selector.replace("\\", "/")
    return path == normalized or path.startswith(normalized)


def entries_for_group(entries: list[IndexEntry], group: FeatureGroup) -> list[IndexEntry]:
    selected = [
        entry
        for entry in entries
        if any(selector_matches(entry.file, selector) for selector in group.selectors)
    ]
    return sorted(selected, key=lambda entry: (PRIORITY_RANK.get(entry.priority, 9), entry.file.casefold(), entry.file))


def path_reference_findings(text: str, root: Path = REPO_ROOT) -> list[PathReferenceFinding]:
    findings: list[PathReferenceFinding] = []
    excluded_prefixes = release_excluded_prefixes(root)
    seen: set[str] = set()
    for token in BACKTICK_RE.findall(text):
        path = token.replace("\\", "/").strip()
        if path in seen:
            continue
        seen.add(path)
        if any(char in path for char in (" ", "\t", "*")):
            continue
        if not any(separator in path for separator in ("/", "\\")):
            continue
        if path.startswith(LEGACY_ROOTS):
            findings.append(PathReferenceFinding(path, "LEGACY_ROOT_REFERENCE", "feature output references a removed legacy root"))
            continue
        if path.startswith(("http://", "https://")):
            continue
        if not (root / path).exists() and not is_release_excluded_path(path, excluded_prefixes):
            findings.append(PathReferenceFinding(path, "REFERENCED_PATH_MISSING", "feature output references a path that does not exist"))
    return findings


def render_findings(findings: Sequence[PathReferenceFinding]) -> str:
    lines = [f"Feature navigation path reference findings ({len(findings)}):"]
    lines.extend(f"  {item.path}: {item.reason_code} - {item.reason}" for item in findings[:80])
    return "\n".join(lines)


def _entry_to_record(entry: IndexEntry) -> ContextRecord:
    category = evidence_category_for(entry.file)
    layer = layer_for(entry.file, category)
    authority = authority_for(entry.file, category, layer)
    extracted = ExtractedSource(file_type=Path(entry.file).suffix.lstrip(".").upper() or "file", purpose=entry.purpose)
    scores = feature_scores(entry.file, entry.domain, extracted)
    groups = tuple(feature_id for _, feature_id in scores)
    primary = groups[0] if groups else "repository-general"
    return ContextRecord(
        path=entry.file,
        file_type=extracted.file_type,
        purpose=entry.purpose,
        owner_domain=entry.domain or owner_domain_for(entry.file),
        feature_group=primary,
        pipeline_stage=entry.stage,
        token_priority=entry.priority or token_priority_for(entry.file, category),
        source_hash="0" * 64,
        evidence_category=category,
        layer=layer,
        authority=authority,
        risk_tier=risk_tier_for(entry.file, authority),
        validation_rung=validation_rung_for(entry.file, primary, category),
        feature_groups=groups,
        relevance_terms=terms_for(entry.file, entry.purpose, entry.domain),
    )


def _coerce_records(items: Iterable[ContextRecord | IndexEntry]) -> list[ContextRecord]:
    return [item if isinstance(item, ContextRecord) else _entry_to_record(item) for item in items]


def records_for_feature(records: Iterable[ContextRecord], feature: FeatureSpec) -> list[ContextRecord]:
    selected = [
        record
        for record in records
        if feature.feature_id == record.feature_group
        or feature.feature_id in record.feature_groups
        or any(selector_matches(record.path, selector) for selector in feature.selectors)
        or record.path in feature.boundary_docs
    ]
    return sorted(
        selected,
        key=lambda record: (
            EVIDENCE_ORDER.index(record.evidence_category) if record.evidence_category in EVIDENCE_ORDER else 99,
            AUTHORITY_RANK.get(record.authority, 99),
            PRIORITY_RANK.get(record.token_priority, 9),
            record.path.casefold(),
            record.path,
        ),
    )


def relevance_reason(record: ContextRecord) -> str:
    if record.authority == "canonical-boundary":
        return "canonical boundary"
    if record.authority.startswith("backend"):
        return f"{record.owner_domain} authority"
    if record.authority == "frontend-display-and-intent":
        return "operator display/intent surface"
    if record.evidence_category == "test":
        return "verification evidence"
    if record.evidence_category == "documentation":
        return "active documentation"
    return record.purpose.rstrip(".")[:90]


def _render_primary(records: Sequence[ContextRecord], limit: int = 10) -> str:
    primary = [record for record in records if record.evidence_category == "production"][:limit]
    if not primary:
        return "_No production authority file matched._"
    return "<br>".join(f"`{record.path}` — {relevance_reason(record)}" for record in primary)


def _secondary_counts(records: Sequence[ContextRecord]) -> str:
    counts = Counter(record.evidence_category for record in records if record.evidence_category != "production")
    if not counts:
        return "none"
    return ", ".join(f"{category}: {counts[category]}" for category in EVIDENCE_ORDER if counts.get(category))


def render_feature_map(items: Iterable[ContextRecord | IndexEntry]) -> str:
    records = _coerce_records(items)
    lines = [
        "# FEATURE_FILE_MAP",
        "",
        f"Generated by `{RUN_COMMAND}` from the shared source record catalog. Do not hand-edit.",
        "",
        "This map ranks authority-owning production entrypoints first. Tests, documentation, generated data, history, and change packets remain queryable as secondary evidence but never become default primary files.",
        "",
        "## Summary",
        "",
        f"- Catalog records considered: **{len(records)}**",
        f"- Feature groups emitted: **{len(FEATURE_SPECS)}**",
        "- `ops/release/changes/**` is excluded from every primary-file list.",
        "",
        "## Feature groups",
        "",
        "| Feature | Authority-owning primary files | Secondary evidence |",
        "|---|---|---|",
    ]
    for feature in FEATURE_SPECS:
        selected = records_for_feature(records, feature)
        lines.append(
            f"| {table_cell(feature.label)} | {table_cell(_render_primary(selected))} | {table_cell(_secondary_counts(selected))} |"
        )
    lines.extend(
        (
            "",
            "## Validation",
            "",
            "- `mediapipeline.tools.dev.generate_feature_file_map --check` verifies this map and every feature card.",
            "- The check fails on drift, unexpected card files, missing repo-relative paths, or removed legacy roots.",
            "",
        )
    )
    return "\n".join(lines)


def feature_card_path(root: Path, feature_id: str) -> Path:
    return root / f"{feature_id}.md"


def _card_layer_records(records: Sequence[ContextRecord], layer: str) -> list[ContextRecord]:
    candidates = [record for record in records if record.layer == layer]
    if layer not in {"tests", "boundary-validation-docs"}:
        candidates = [record for record in candidates if record.evidence_category == "production"]
    return candidates[:5]


def render_feature_cards(records: Iterable[ContextRecord]) -> dict[str, str]:
    catalog = list(records)
    cards: dict[str, str] = {}
    for feature in FEATURE_SPECS:
        selected = records_for_feature(catalog, feature)
        lines = [
            f"# {feature.label}",
            "",
            f"Generated by `{RUN_COMMAND}`. Do not hand-edit.",
            "",
            f"Feature ID: `{feature.feature_id}`  ",
            f"Primary owner domains: {', '.join(f'`{owner}`' for owner in feature.owner_domains) or '`undetermined`'}  ",
            f"Validation: {feature.validation}",
            "",
            "## Vertical slice",
            "",
        ]
        for layer in CARD_LAYER_ORDER:
            layer_records = _card_layer_records(selected, layer)
            if not layer_records:
                continue
            lines.append(f"### {CARD_LAYER_LABELS[layer]}")
            lines.append("")
            for record in layer_records:
                lines.append(f"- `{record.path}` — {relevance_reason(record)}; {record.purpose}")
            lines.append("")
        lines.extend(("## Why these files", ""))
        primary = [record for record in selected if record.evidence_category == "production"][:8]
        if primary:
            for record in primary:
                lines.append(f"- `{record.path}`: {relevance_reason(record)}.")
        else:
            lines.append("- No production authority file currently matches; use the context-slice query for nearest evidence.")
        lines.extend(("", "## Tests and validation", ""))
        tests = [record for record in selected if record.evidence_category == "test"][:8]
        if tests:
            lines.extend(f"- `{record.path}`" for record in tests)
        else:
            lines.append("- No directly classified test; run the owning targeted validation rung.")
        lines.append(f"- Smallest validation rung: {feature.validation}.")
        if feature.boundary_docs:
            lines.append("- Boundaries: " + ", ".join(f"`{path}`" for path in feature.boundary_docs) + ".")
        counts = Counter(record.evidence_category for record in selected)
        lines.extend(("", "## Secondary evidence", ""))
        lines.append(
            "Counts only (request explicitly when needed): "
            + ", ".join(f"{category}={counts.get(category, 0)}" for category in EVIDENCE_ORDER if category != "production")
            + "."
        )
        lines.append("")
        cards[feature.feature_id] = "\n".join(lines)
    return cards


def write_or_check_cards(cards: dict[str, str], root: Path, *, check: bool) -> bool:
    expected_names = {f"{feature_id}.md" for feature_id in cards}
    actual_names = {path.name for path in root.glob("*.md")} if root.exists() else set()
    ok = actual_names == expected_names
    for feature_id, expected in sorted(cards.items()):
        path = feature_card_path(root, feature_id)
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8", errors="replace") != expected:
                ok = False
            continue
        root.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8", newline="\n")
    if not check and root.exists():
        for path in root.glob("*.md"):
            if path.name not in expected_names:
                path.unlink()
        ok = True
    return ok


def check_file(expected: str) -> bool:
    findings = path_reference_findings(expected)
    ok = not findings
    if findings:
        print(render_findings(findings), file=sys.stderr)
    if not FEATURE_MAP_PATH.exists():
        print(f"Missing generated file: {FEATURE_MAP_PATH.relative_to(REPO_ROOT)}")
        return False
    actual = FEATURE_MAP_PATH.read_text(encoding="utf-8", errors="replace")
    if actual != expected:
        rel = FEATURE_MAP_PATH.relative_to(REPO_ROOT)
        print(f"{rel} is stale. Run: {RUN_COMMAND}")
        for line in list(
            difflib.unified_diff(
                actual.splitlines(), expected.splitlines(), fromfile=f"{rel} (current)", tofile=f"{rel} (expected)", lineterm=""
            )
        )[:160]:
            print(line)
        ok = False
    elif ok:
        print(f"OK: {FEATURE_MAP_PATH.relative_to(REPO_ROOT)} is current.")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify feature map and cards without rewriting.")
    args = parser.parse_args(argv)
    records = collect_context_records()
    path_findings = validate_record_paths(records)
    if path_findings:
        print(f"Context record path findings ({len(path_findings)}):", file=sys.stderr)
        for finding in path_findings[:80]:
            print(f"  {finding}", file=sys.stderr)
        return 1
    expected_map = render_feature_map(records)
    cards = render_feature_cards(records)
    card_findings = path_reference_findings("\n".join(cards.values()))
    if card_findings:
        print(render_findings(card_findings), file=sys.stderr)
        return 1
    if args.check:
        map_ok = check_file(expected_map)
        cards_ok = write_or_check_cards(cards, FEATURE_CARD_ROOT, check=True)
        if not cards_ok:
            print(f"{FEATURE_CARD_ROOT.relative_to(REPO_ROOT)} is stale or has unexpected cards. Run: {RUN_COMMAND}")
        return 0 if map_ok and cards_ok else 1
    GENERATED_DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    FEATURE_MAP_PATH.write_text(expected_map, encoding="utf-8", newline="\n")
    write_or_check_cards(cards, FEATURE_CARD_ROOT, check=False)
    print(f"Wrote {FEATURE_MAP_PATH.relative_to(REPO_ROOT)} and {len(cards)} feature cards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
