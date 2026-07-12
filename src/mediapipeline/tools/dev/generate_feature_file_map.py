"""Generate docs/generated/FEATURE_FILE_MAP.md from docs/generated/PROJECT_INDEX.md."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from mediapipeline.tools.dev.release_package_scope import (
    is_release_excluded_path,
    release_excluded_prefixes,
)

REPO_ROOT = find_repo_root(Path(__file__))
GENERATED_DOCS_ROOT = REPO_ROOT / "docs" / "generated"
PROJECT_INDEX_PATH = GENERATED_DOCS_ROOT / "PROJECT_INDEX.md"
FEATURE_MAP_PATH = GENERATED_DOCS_ROOT / "FEATURE_FILE_MAP.md"
RUN_COMMAND = (
    "apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py "
    "mediapipeline.tools.dev.generate_feature_file_map"
)

PROJECT_INDEX_ROW_RE = re.compile(r"^\| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (.*) \|$")
BACKTICK_RE = re.compile(r"`([^`]+)`")
LEGACY_ROOTS = ("app/", "DesktopApp/", "Pipeline/")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


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
    limit: int = 18


@dataclass(frozen=True)
class PathReferenceFinding:
    path: str
    reason_code: str
    reason: str


FEATURE_GROUPS: tuple[FeatureGroup, ...] = (
    FeatureGroup(
        "Tauri shell and backend lifecycle",
        (
            "apps/desktop/tauri/",
            "apps/desktop/webview/static/assets/tauriLifecycleBridge.js",
            "tests/python/desktop/test_tauri_shell_scaffold.py",
            "tests/webview/test_webview_tauri_lifecycle_bridge.py",
        ),
    ),
    FeatureGroup(
        "Local API routes, contracts, and mutation ownership",
        (
            "src/mediapipeline/desktop/api/",
            "docs/inventories/API_ROUTE_INVENTORY.md",
            "docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md",
            "docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md",
            "tests/python/desktop/test_api_route_inventory.py",
        ),
    ),
    FeatureGroup(
        "Desktop application facade and operator DTOs",
        (
            "src/mediapipeline/desktop/application/",
            "tests/python/desktop/test_application_facade",
        ),
    ),
    FeatureGroup(
        "WebView operator surface",
        (
            "apps/desktop/webview/static/",
            "tests/webview/",
            "docs/generated/WEBVIEW_",
        ),
    ),
    FeatureGroup(
        "Settings, config schema, and library profiles",
        (
            "src/mediapipeline/core/config/",
            "ops/pipeline/config/",
            "src/mediapipeline/contracts/config.py",
            "src/mediapipeline/contracts/schemas/config.v1.schema.json",
            "tests/python/desktop/test_service_config",
            "tests/python/desktop/test_settings",
        ),
    ),
    FeatureGroup(
        "Queue, source scanning, and launch planning",
        (
            "src/mediapipeline/core/queue/",
            "ops/pipeline/engine/queue/",
            "tests/python/desktop/test_service_queue",
            "ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1",
        ),
    ),
    FeatureGroup(
        "Media decisions, FFmpeg entrypoints, and processing",
        (
            "src/mediapipeline/core/decide/",
            "src/mediapipeline/core/processes/",
            "ops/pipeline/engine/decide/",
            "ops/pipeline/engine/process/",
            "ops/pipeline/entrypoints/MediaPipeline/",
            "ops/pipeline/tests/Unit/Invoke-MediaRouteSelectionChecks.ps1",
        ),
    ),
    FeatureGroup(
        "Subtitles, audio, and stream sidecars",
        (
            "src/mediapipeline/pipeline/ass_to_srt",
            "ops/pipeline/engine/subtitles/",
            "ops/pipeline/engine/audio/",
            "ops/pipeline/tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1",
            "ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1",
        ),
    ),
    FeatureGroup(
        "Completed outputs, publish, drain, and final library",
        (
            "src/mediapipeline/core/completed/",
            "src/mediapipeline/core/publish/",
            "src/mediapipeline/core/final_library/",
            "ops/pipeline/engine/publish/",
            "tests/python/desktop/test_final_library_promotion.py",
        ),
    ),
    FeatureGroup(
        "Rename planning, apply safety, and evidence",
        (
            "src/mediapipeline/core/rename/",
            "apps/desktop/webview/static/assets/rename",
            "apps/desktop/webview/static/assets/renameView.js",
            "tests/python/desktop/test_application_facade_rename.py",
            "tests/webview/test_webview_browser_rename_smoke.py",
        ),
    ),
    FeatureGroup(
        "Diagnostics, maintenance, and sample validation",
        (
            "src/mediapipeline/core/diagnostics/",
            "src/mediapipeline/core/maintenance/",
            "src/mediapipeline/core/sample_validation/",
            "src/mediapipeline/desktop/application/sample_validation/",
            "tests/python/desktop/test_service_tdarr_matrix_audit.py",
            "tests/python/desktop/test_application_facade_maintenance.py",
        ),
    ),
    FeatureGroup(
        "Storage, paths, runtime state, and process guards",
        (
            "src/mediapipeline/core/storage/",
            "src/mediapipeline/core/paths/",
            "ops/pipeline/engine/storage/",
            "ops/pipeline/engine/paths/",
            "tests/python/desktop/test_phase4_storage_observability.py",
        ),
    ),
    FeatureGroup(
        "Distributed worker and network mode",
        (
            "src/mediapipeline/desktop/network/",
            "src/mediapipeline/desktop/watch/",
            "tests/python/desktop/test_network",
            "tests/python/desktop/test_watch_folder",
        ),
    ),
    FeatureGroup(
        "Generated context, release tooling, and guardrails",
        (
            "src/mediapipeline/tools/",
            "docs/generated/PROJECT_INDEX.md",
            "docs/generated/DEPENDENCY_GRAPH.md",
            "docs/generated/PIPELINE_MAP.md",
            "docs/generated/FEATURE_FILE_MAP.md",
            "ops/release/changes/unreleased/",
            "tests/python/tooling/",
        ),
    ),
    FeatureGroup(
        "PowerShell release, smoke, and validation wrappers",
        (
            "ops/scripts/",
            "ops/pipeline/tests/",
            "tests/python/desktop/test_browser_smoke_support.py",
        ),
    ),
)


def table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def parse_project_index(text: str) -> list[IndexEntry]:
    entries: list[IndexEntry] = []
    for line in text.splitlines():
        match = PROJECT_INDEX_ROW_RE.match(line)
        if not match:
            continue
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
    if normalized.endswith("/"):
        return path.startswith(normalized)
    return path == normalized or path.startswith(normalized)


def entries_for_group(entries: list[IndexEntry], group: FeatureGroup) -> list[IndexEntry]:
    selected = [
        entry
        for entry in entries
        if any(selector_matches(entry.file, selector) for selector in group.selectors)
    ]
    selected.sort(key=lambda entry: (PRIORITY_RANK.get(entry.priority, 9), entry.file))
    return selected


def path_reference_findings(text: str, root: Path = REPO_ROOT) -> list[PathReferenceFinding]:
    findings: list[PathReferenceFinding] = []
    excluded_prefixes = release_excluded_prefixes(root)
    seen: set[str] = set()
    for token in BACKTICK_RE.findall(text):
        path = token.replace("\\", "/").strip()
        if path in seen:
            continue
        seen.add(path)
        if " " in path or "\t" in path or "*" in path:
            continue
        if not any(separator in path for separator in ("/", "\\")):
            continue
        if path.startswith(LEGACY_ROOTS):
            findings.append(
                PathReferenceFinding(
                    path=path,
                    reason_code="LEGACY_ROOT_REFERENCE",
                    reason="feature map references a removed legacy root",
                )
            )
            continue
        if path.startswith("http://") or path.startswith("https://"):
            continue
        candidate = root / path
        if not candidate.exists():
            if is_release_excluded_path(path, excluded_prefixes):
                # Path intentionally omitted from this release package (e.g. the
                # test suite); the feature map legitimately still references it.
                continue
            findings.append(
                PathReferenceFinding(
                    path=path,
                    reason_code="REFERENCED_PATH_MISSING",
                    reason="feature map references a path that does not exist",
                )
            )
    return findings


def render_path_list(entries: list[IndexEntry], limit: int) -> str:
    if not entries:
        return "_No indexed files matched this group._"
    visible = entries[:limit]
    parts = [f"`{entry.file}`" for entry in visible]
    remaining = len(entries) - len(visible)
    if remaining > 0:
        parts.append(f"{remaining} more indexed file(s)")
    return "<br>".join(parts)


def render_feature_map(entries: list[IndexEntry]) -> str:
    lines: list[str] = []
    lines.append("# FEATURE_FILE_MAP")
    lines.append("")
    lines.append(f"Generated by `{RUN_COMMAND}` from `docs/generated/PROJECT_INDEX.md`. Do not hand-edit.")
    lines.append("")
    lines.append(
        "This generated map groups active source and documentation files by operator-facing feature area. "
        "It is a navigation aid, not a source of truth; use `docs/generated/PROJECT_INDEX.md` for the full one-row-per-file index."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Indexed source files considered: **{len(entries)}**")
    lines.append(f"- Feature groups emitted: **{len(FEATURE_GROUPS)}**")
    lines.append("- Every backticked repo-relative path in this file is checked for existence by the generator.")
    lines.append("")
    lines.append("## Feature Groups")
    lines.append("")
    lines.append("| Feature | Primary files |")
    lines.append("|---|---|")
    for group in FEATURE_GROUPS:
        selected = entries_for_group(entries, group)
        lines.append(f"| {table_cell(group.label)} | {table_cell(render_path_list(selected, group.limit))} |")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    lines.append("- `mediapipeline.tools.dev.generate_feature_file_map --check` fails when this file drifts.")
    lines.append("- The check also fails on missing repo-relative path references and removed legacy roots.")
    lines.append("")
    return "\n".join(lines)


def render_findings(findings: list[PathReferenceFinding]) -> str:
    lines = [f"Feature file map path reference findings ({len(findings)}):"]
    for finding in findings[:80]:
        lines.append(f"  {finding.path}: {finding.reason_code} - {finding.reason}")
    return "\n".join(lines)


def check_file(expected: str) -> bool:
    ok = True
    findings = path_reference_findings(expected)
    if findings:
        print(render_findings(findings), file=sys.stderr)
        ok = False
    if not FEATURE_MAP_PATH.exists():
        print(f"Missing generated file: {FEATURE_MAP_PATH.relative_to(REPO_ROOT)}")
        return False
    actual = FEATURE_MAP_PATH.read_text(encoding="utf-8", errors="replace")
    actual_findings = path_reference_findings(actual)
    if actual_findings:
        print(render_findings(actual_findings), file=sys.stderr)
        ok = False
    if actual == expected:
        if ok:
            print(f"OK: {FEATURE_MAP_PATH.relative_to(REPO_ROOT)} is current.")
        return ok
    rel = FEATURE_MAP_PATH.relative_to(REPO_ROOT)
    print(f"{rel} is stale. Run: {RUN_COMMAND}")
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=f"{rel} (current)",
        tofile=f"{rel} (expected)",
        lineterm="",
    )
    for line in list(diff)[:160]:
        print(line)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify docs/generated/FEATURE_FILE_MAP.md without rewriting.",
    )
    args = parser.parse_args(argv)

    try:
        entries = load_project_index()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    expected = render_feature_map(entries)
    if args.check:
        return 0 if check_file(expected) else 1

    GENERATED_DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    FEATURE_MAP_PATH.write_text(expected, encoding="utf-8", newline="\n")
    findings = path_reference_findings(expected)
    if findings:
        print(render_findings(findings), file=sys.stderr)
        return 1
    print(f"Wrote {FEATURE_MAP_PATH.relative_to(REPO_ROOT)} from {PROJECT_INDEX_PATH.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
