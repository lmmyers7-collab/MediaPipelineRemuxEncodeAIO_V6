"""Generate human, machine, and dependency views from one typed source catalog."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

from mediapipeline.tools.dev.context_records import (
    ContextRecord,
    collect_context_records,
    records_to_jsonl,
    validate_record_paths,
)
from mediapipeline.tools.paths import find_repo_root
from mediapipeline.tools.dev.release_package_scope import (
    is_release_excluded_path,
    release_excluded_prefixes,
)

REPO_ROOT = find_repo_root(Path(__file__))
SUMMARY_ROOT = REPO_ROOT / "docs" / "generated" / "summaries"
GENERATED_DOCS_ROOT = REPO_ROOT / "docs" / "generated"
INDEX_PATH = GENERATED_DOCS_ROOT / "PROJECT_INDEX.md"
JSONL_PATH = GENERATED_DOCS_ROOT / "PROJECT_INDEX.jsonl"
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


def _summary_rows(summaries: list[Path]) -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for s in summaries:
        text = s.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        file = fm.get("file", "?")
        domain = fm.get("owner_domain", "?")
        priority = fm.get("token_priority", "?")
        stage = fm.get("pipeline_stage", "?")
        purpose = short_purpose(text)
        rows.append((file, domain, priority, stage, purpose))
    return rows


def _record_rows(records: list[ContextRecord]) -> list[tuple[str, str, str, str, str]]:
    return [
        (record.path, record.owner_domain, record.token_priority, record.pipeline_stage, record.purpose)
        for record in records
    ]


def render_index(items: list[Path] | list[ContextRecord]) -> str:
    rows = _summary_rows(items) if items and isinstance(items[0], Path) else _record_rows(items)  # type: ignore[arg-type]
    counts: dict[str, int] = defaultdict(int)
    priorities: dict[str, int] = defaultdict(int)
    evidence: dict[str, int] = defaultdict(int)
    record_by_path = {record.path: record for record in items if isinstance(record, ContextRecord)}
    for file, domain, priority, _, _ in rows:
        counts[domain] += 1
        priorities[priority] += 1
        if file in record_by_path:
            evidence[record_by_path[file].evidence_category] += 1

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
    if evidence:
        lines.append("- By evidence category:")
        for category in sorted(evidence):
            lines.append(f"  - `{category}`: {evidence[category]}")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("| File | Domain | Priority | Stage | Purpose |")
    lines.append("|---|---|---|---|---|")
    for file, domain, priority, stage, purpose in rows:
        safe_purpose = purpose.replace("|", "\\|")
        if len(safe_purpose) > 110:
            safe_purpose = safe_purpose[:109].rstrip() + "…"
        lines.append(f"| `{file}` | {domain} | {priority} | {stage} | {safe_purpose} |")
    lines.append("")
    return "\n".join(lines)


def render_graph(items: list[Path] | list[ContextRecord]) -> str:
    edges: dict[tuple[str, str], int] = defaultdict(int)
    nodes: set[str] = set()
    if items and isinstance(items[0], ContextRecord):
        records = items  # type: ignore[assignment]
        by_path = {record.path: record for record in records}
        for record in records:
            nodes.add(record.owner_domain)
            for target_path in record.outbound_dependencies:
                target_record = by_path.get(target_path)
                if target_record and target_record.owner_domain != record.owner_domain:
                    edges[(record.owner_domain, target_record.owner_domain)] += 1
                    nodes.add(target_record.owner_domain)
    else:
        for summary in items:  # type: ignore[assignment]
            text = summary.read_text(encoding="utf-8", errors="replace")
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

    records = collect_context_records()
    path_findings = validate_record_paths(records)
    if path_findings:
        print(f"Context record path findings ({len(path_findings)}):", file=sys.stderr)
        for finding in path_findings[:80]:
            print(f"  {finding}", file=sys.stderr)
        return 1
    index = render_index(records)
    jsonl = records_to_jsonl(records)
    graph = render_graph(records)
    if args.check:
        ok = check_file(INDEX_PATH, index)
        ok = check_file(JSONL_PATH, jsonl) and ok
        ok = check_file(GRAPH_PATH, graph) and ok
        if ok:
            print(
                "OK: "
                f"{INDEX_PATH.relative_to(REPO_ROOT)} and "
                f"{JSONL_PATH.relative_to(REPO_ROOT)} and "
                f"{GRAPH_PATH.relative_to(REPO_ROOT)} are current."
            )
            return 0
        return 1

    GENERATED_DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(index, encoding="utf-8", newline="\n")
    JSONL_PATH.write_text(jsonl, encoding="utf-8", newline="\n")
    GRAPH_PATH.write_text(graph, encoding="utf-8", newline="\n")
    print(
        f"Wrote {INDEX_PATH.relative_to(REPO_ROOT)}, {JSONL_PATH.relative_to(REPO_ROOT)}, "
        f"and {GRAPH_PATH.relative_to(REPO_ROOT)} from {len(records)} typed source records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
