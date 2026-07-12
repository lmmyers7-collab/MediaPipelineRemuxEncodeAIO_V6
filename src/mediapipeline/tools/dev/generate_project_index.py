"""Generate docs/generated/PROJECT_INDEX.md and docs/generated/DEPENDENCY_GRAPH.md from docs/generated/summaries/.

docs/generated/PROJECT_INDEX.md is a flat table: one row per source file with path,
owner_domain, token_priority, pipeline_stage, and a short purpose line
extracted from its summary.

docs/generated/DEPENDENCY_GRAPH.md emits a Mermaid graph of cross-domain imports (Python)
and dot-includes (PowerShell). Edges are aggregated by owner_domain pair
so the graph stays legible.

Run after refresh_summaries.py. Use --check in pre-commit/CI to verify
docs/generated/PROJECT_INDEX.md and docs/generated/DEPENDENCY_GRAPH.md are current without rewriting
them.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from mediapipeline.tools.dev.release_package_scope import (
    is_release_excluded_path,
    release_excluded_prefixes,
)

REPO_ROOT = find_repo_root(Path(__file__))
SUMMARY_ROOT = REPO_ROOT / "docs" / "generated" / "summaries"
GENERATED_DOCS_ROOT = REPO_ROOT / "docs" / "generated"
INDEX_PATH = GENERATED_DOCS_ROOT / "PROJECT_INDEX.md"
GRAPH_PATH = GENERATED_DOCS_ROOT / "DEPENDENCY_GRAPH.md"
RUN_COMMAND = (
    "apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py "
    "mediapipeline.tools.dev.generate_project_index"
)
VOLATILE_GENERATED_SUMMARY_FILES = {
    "docs/generated/DEPENDENCY_GRAPH.md",
    "docs/generated/FEATURE_FILE_MAP.md",
    "docs/generated/PROJECT_INDEX.md",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
PURPOSE_RE = re.compile(r"\*\*Purpose:\*\*\s*(.+)")
IMPORTS_RE = re.compile(r"\*\*In-repo imports:\*\*\s*(.+)")
DOTINC_RE = re.compile(r"\*\*Dot-sourced:\*\*\s*(.+)")


@dataclass(frozen=True)
class OrphanSummaryFinding:
    summary_path: Path
    reason_code: str
    reason: str
    recorded_file: str = ""

    @property
    def display_path(self) -> str:
        return self.summary_path.relative_to(REPO_ROOT).as_posix()


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def parse_first(text: str, regex: re.Pattern[str]) -> str:
    m = regex.search(text)
    return m.group(1).strip() if m else ""


def canonical_path_sort_key(path: Path) -> tuple[str, str]:
    normalized = path.as_posix()
    return normalized.casefold(), normalized


def iter_summaries() -> list[Path]:
    summaries: list[Path] = []
    for summary in sorted(SUMMARY_ROOT.rglob("*.md"), key=canonical_path_sort_key):
        text = summary.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm.get("file", "").replace("\\", "/") in VOLATILE_GENERATED_SUMMARY_FILES:
            continue
        summaries.append(summary)
    return summaries


def expected_summary_path_for_file(file_path: str) -> Path:
    source = Path(file_path)
    return SUMMARY_ROOT / source.with_suffix(source.suffix + ".md")


def orphan_summary_findings(summaries: list[Path]) -> list[OrphanSummaryFinding]:
    findings: list[OrphanSummaryFinding] = []
    excluded_prefixes = release_excluded_prefixes(REPO_ROOT)
    for summary in summaries:
        text = summary.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        recorded = fm.get("file", "")
        if not recorded:
            findings.append(
                OrphanSummaryFinding(
                    summary_path=summary,
                    reason_code="SUMMARY_FILE_MISSING",
                    reason="summary has no frontmatter file field",
                )
            )
            continue
        source_path = Path(recorded)
        if source_path.is_absolute():
            findings.append(
                OrphanSummaryFinding(
                    summary_path=summary,
                    reason_code="SUMMARY_FILE_ABSOLUTE",
                    reason="summary file field must be repo-relative",
                    recorded_file=recorded,
                )
            )
            continue
        if is_release_excluded_path(source_path.as_posix(), excluded_prefixes):
            # The recorded source was intentionally omitted from this release
            # package (e.g. the test suite). Its shipped summary is not an orphan.
            continue
        if not (REPO_ROOT / source_path).is_file():
            findings.append(
                OrphanSummaryFinding(
                    summary_path=summary,
                    reason_code="SOURCE_FILE_MISSING",
                    reason="recorded source file no longer exists",
                    recorded_file=source_path.as_posix(),
                )
            )
            continue
        expected = expected_summary_path_for_file(source_path.as_posix())
        if summary != expected:
            findings.append(
                OrphanSummaryFinding(
                    summary_path=summary,
                    reason_code="SUMMARY_PATH_MISMATCH",
                    reason=f"summary is not at expected path {expected.relative_to(REPO_ROOT).as_posix()}",
                    recorded_file=source_path.as_posix(),
                )
            )
    return findings


def render_orphan_summary_findings(findings: list[OrphanSummaryFinding]) -> str:
    lines = [
        f"Orphan summaries found ({len(findings)}). Run: apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --all --prune-orphans"
    ]
    for finding in findings[:80]:
        suffix = f" -> {finding.recorded_file}" if finding.recorded_file else ""
        lines.append(f"  {finding.display_path}: {finding.reason_code}{suffix}")
    return "\n".join(lines)


def short_purpose(text: str, limit: int = 90) -> str:
    p = parse_first(text, PURPOSE_RE)
    p = p.replace("(no module docstring)", "—").replace("(no .SYNOPSIS block)", "—")
    if len(p) > limit:
        p = p[: limit - 1].rstrip() + "…"
    return p


def render_index(summaries: list[Path]) -> str:
    rows: list[tuple[str, str, str, str, str]] = []
    counts: dict[str, int] = defaultdict(int)
    priorities: dict[str, int] = defaultdict(int)
    for s in summaries:
        text = s.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        file = fm.get("file", "?")
        domain = fm.get("owner_domain", "?")
        priority = fm.get("token_priority", "?")
        stage = fm.get("pipeline_stage", "?")
        purpose = short_purpose(text)
        rows.append((file, domain, priority, stage, purpose))
        counts[domain] += 1
        priorities[priority] += 1

    lines: list[str] = []
    lines.append("# PROJECT_INDEX")
    lines.append("")
    lines.append(f"Generated by `{RUN_COMMAND}`. Do not hand-edit.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Source files indexed: **{len(rows)}**")
    lines.append("- By owner domain:")
    for dom in sorted(counts):
        lines.append(f"  - `{dom}`: {counts[dom]}")
    lines.append("- By token priority:")
    for pri in ("high", "medium", "low"):
        lines.append(f"  - `{pri}`: {priorities.get(pri, 0)}")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("| File | Domain | Priority | Stage | Purpose |")
    lines.append("|---|---|---|---|---|")
    for file, domain, priority, stage, purpose in rows:
        safe_purpose = purpose.replace("|", "\\|")
        lines.append(f"| `{file}` | {domain} | {priority} | {stage} | {safe_purpose} |")
    lines.append("")
    return "\n".join(lines)


def render_graph(summaries: list[Path]) -> str:
    edges: dict[tuple[str, str], int] = defaultdict(int)
    nodes: set[str] = set()
    for s in summaries:
        text = s.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        src_domain = fm.get("owner_domain", "unknown")
        nodes.add(src_domain)
        py_imports = parse_first(text, IMPORTS_RE)
        if py_imports:
            for tok in re.findall(r"`([^`]+)`", py_imports):
                target = _domain_of_python_import(tok)
                if target and target != src_domain:
                    edges[(src_domain, target)] += 1
                    nodes.add(target)
        ps_inc = parse_first(text, DOTINC_RE)
        if ps_inc:
            for tok in re.findall(r"`([^`]+)`", ps_inc):
                target = _domain_of_ps_include(tok)
                if target and target != src_domain:
                    edges[(src_domain, target)] += 1
                    nodes.add(target)

    lines: list[str] = []
    lines.append("# DEPENDENCY_GRAPH")
    lines.append("")
    lines.append(f"Generated by `{RUN_COMMAND}`. Do not hand-edit.")
    lines.append("Edges aggregate cross-domain Python imports and PowerShell dot-includes.")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph LR")
    for node in sorted(nodes):
        safe = re.sub(r"[^A-Za-z0-9_]", "_", node) or "unknown"
        lines.append(f"  {safe}[\"{node}\"]")
    for (src, dst), n in sorted(edges.items(), key=lambda kv: (-kv[1], kv[0])):
        src_id = re.sub(r"[^A-Za-z0-9_]", "_", src) or "unknown"
        dst_id = re.sub(r"[^A-Za-z0-9_]", "_", dst) or "unknown"
        lines.append(f"  {src_id} -->|{n}| {dst_id}")
    lines.append("```")
    lines.append("")
    lines.append("## Edge counts")
    lines.append("")
    lines.append("| From | To | Edges |")
    lines.append("|---|---|---|")
    for (src, dst), n in sorted(edges.items(), key=lambda kv: (-kv[1], kv[0]))[:200]:
        lines.append(f"| {src} | {dst} | {n} |")
    lines.append("")
    return "\n".join(lines)


def _domain_of_python_import(tok: str) -> str:
    # Strip package roots and infer domain from path.
    norm = tok.replace(".", "/").strip("/")
    if "facade" in norm:
        return "application"
    if norm.startswith("app/"):
        parts = norm.split("/")
        return parts[1] if len(parts) > 1 else "app"
    if norm.startswith("mediapipeline/core/"):
        parts = norm.split("/")
        return parts[2] if len(parts) > 2 else "core"
    if "api" in norm:
        return "api"
    if "network" in norm:
        return "network"
    if "contract" in norm:
        return "contracts"
    return ""


def _domain_of_ps_include(tok: str) -> str:
    name = tok.split(".")[0]
    return name or ""


def check_file(path: Path, expected: str) -> bool:
    if not path.exists():
        print(f"Missing generated file: {path.relative_to(REPO_ROOT)}")
        return False
    actual = path.read_text(encoding="utf-8", errors="replace")
    if actual == expected:
        return True
    rel = path.relative_to(REPO_ROOT)
    print(f"{rel} is stale. Run: {RUN_COMMAND}")
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=f"{rel} (current)",
        tofile=f"{rel} (expected)",
        lineterm="",
    )
    for line in list(diff)[:120]:
        print(line)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify docs/generated navigation files without rewriting.",
    )
    args = parser.parse_args(argv)

    if not SUMMARY_ROOT.exists():
        print("docs/generated/summaries/ does not exist. Run refresh_summaries.py first.")
        return 1
    summaries = iter_summaries()
    orphans = orphan_summary_findings(summaries)
    if orphans:
        print(render_orphan_summary_findings(orphans), file=sys.stderr)
        return 1
    index = render_index(summaries)
    graph = render_graph(summaries)
    if args.check:
        ok = check_file(INDEX_PATH, index)
        ok = check_file(GRAPH_PATH, graph) and ok
        if ok:
            print(
                "OK: "
                f"{INDEX_PATH.relative_to(REPO_ROOT)} and "
                f"{GRAPH_PATH.relative_to(REPO_ROOT)} are current."
            )
            return 0
        return 1

    GENERATED_DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(index, encoding="utf-8", newline="\n")
    GRAPH_PATH.write_text(graph, encoding="utf-8", newline="\n")
    print(
        f"Wrote {INDEX_PATH.relative_to(REPO_ROOT)} and {GRAPH_PATH.relative_to(REPO_ROOT)} "
        f"from {len(summaries)} summaries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
