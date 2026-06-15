"""Generate per-source-file summaries under docs/generated/summaries/.

One summary file per source file in the configured roots, plus existing
summary records whose source files still exist. Summaries carry YAML
frontmatter (file path, sha256, last_modified, token_priority, owner_domain)
and a short Markdown body listing module purpose plus public symbols when the
file type can be parsed cheaply.

Modes:
  --all                Regenerate summaries for every in-scope source file.
  --changed            Regenerate only for files changed vs HEAD.
  --staged             Regenerate only for files staged for commit (use in
                       pre-commit hook).
  --check              Exit 1 if any summary's recorded sha256 differs from
                       the source file. Print stale paths.
  --paths PATH ...     Regenerate the named paths (relative to repo root).

The script avoids any third-party dependency; stdlib only. PowerShell
parsing is regex-based and intentionally shallow.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from mediapipeline.tools.dev.release_package_scope import (
    is_release_excluded_path,
    release_excluded_prefixes,
)
from typing import Iterable

REPO_ROOT = find_repo_root(Path(__file__))
SUMMARY_ROOT = REPO_ROOT / "docs" / "generated" / "summaries"

SOURCE_ROOTS = [
    "src/mediapipeline/core",
    "src/mediapipeline/contracts",
    "src/mediapipeline/desktop",
    "src/mediapipeline/pipeline",
    "src/mediapipeline/tools",
    "apps/desktop/webview/static",
    "apps/desktop/tauri/src-tauri/src",
    "ops/pipeline/engine",
    "ops/pipeline/entrypoints",
    "ops/pipeline/config",
    "ops/pipeline/tests",
    "ops/scripts",
    "tests",
]

ROOT_SOURCE_FILES = {
    "ops/pipeline/entrypoints/MediaPipeline.ps1",
    "ops/pipeline/entrypoints/Audit-MediaLibrary.ps1",
    "ops/pipeline/entrypoints/Setup-MediaPipeline.ps1",
    "ops/pipeline/config/MediaPipeline_config_template.psd1",
    "src/mediapipeline/pipeline/ass_to_srt_cli.py",
    "src/mediapipeline/contracts/schemas/config.v1.schema.json",
    "src/mediapipeline/contracts/schemas/risky_file_registry.v1.schema.json",
    "src/mediapipeline/contracts/schemas/stages.v1.schema.json",
}

VOLATILE_GENERATED_SUMMARY_FILES = {
    "docs/generated/DEPENDENCY_GRAPH.md",
    "docs/generated/FEATURE_FILE_MAP.md",
    "docs/generated/PROJECT_INDEX.md",
}

EXCLUDE_SOURCE_PREFIXES = {
    "ops/pipeline/config/backups",
}

EXCLUDE_DIR_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "target",
    "gen",
    "Runtime",
    "Tools",
    "PowerShell-7.6.0-win-x64",
}

SOURCE_EXTS = {".py", ".ps1", ".psm1", ".psd1", ".rs", ".js", ".mjs", ".css", ".html", ".bat"}

OWNER_DOMAIN_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"src/mediapipeline/core/api"), "api"),
    (re.compile(r"src/mediapipeline/core/audit"), "audit"),
    (re.compile(r"ops/pipeline/entrypoints/Audit-MediaLibrary"), "audit"),
    (re.compile(r"ops/pipeline/entrypoints/MediaPipeline/"), "process"),
    (re.compile(r"ops/pipeline/config/setup"), "scripts"),
    (re.compile(r"src/mediapipeline/pipeline/ass_to_srt(?:_cli\.py|/)"), "subtitles"),
    (re.compile(r"src/mediapipeline/core/kernel"), "kernel"),
    (re.compile(r"src/mediapipeline/core/maintenance"), "maintenance"),
    (re.compile(r"src/mediapipeline/core/folder_policy"), "folder_policy"),
    (re.compile(r"src/mediapipeline/core/paths"), "paths"),
    (re.compile(r"src/mediapipeline/core/schedule"), "schedule"),
    (re.compile(r"src/mediapipeline/core/files"), "files"),
    (re.compile(r"src/mediapipeline/core/shared"), "shared"),
    (re.compile(r"src/mediapipeline/core/sample_validation"), "sample_validation"),
    (re.compile(r"src/mediapipeline/core/validation"), "validation"),
    (re.compile(r"src/mediapipeline/core/metrics"), "metrics"),
    (re.compile(r"src/mediapipeline/core/orchestration"), "orchestration"),
    (re.compile(r"src/mediapipeline/core/processes"), "process"),
    (re.compile(r"src/mediapipeline/core/ingest"), "ingest"),
    (re.compile(r"src/mediapipeline/core/metadata"), "metadata"),
    (re.compile(r"src/mediapipeline/core/decide"), "decide"),
    (re.compile(r"src/mediapipeline/core/diagnostics"), "diagnostics"),
    (re.compile(r"src/mediapipeline/core/failures"), "failures"),
    (re.compile(r"src/mediapipeline/core/queue"), "queue"),
    (re.compile(r"src/mediapipeline/core/transcode"), "transcode"),
    (re.compile(r"src/mediapipeline/core/subtitles"), "subtitles"),
    (re.compile(r"src/mediapipeline/core/audio"), "audio"),
    (re.compile(r"src/mediapipeline/core/completed"), "completed"),
    (re.compile(r"src/mediapipeline/core/final_library"), "final_library"),
    (re.compile(r"src/mediapipeline/core/publish"), "publish"),
    (re.compile(r"src/mediapipeline/core/rename"), "rename"),
    (re.compile(r"src/mediapipeline/core/storage"), "storage"),
    (re.compile(r"src/mediapipeline/core/network"), "network"),
    (re.compile(r"src/mediapipeline/core/status"), "observability"),
    (re.compile(r"src/mediapipeline/core/telemetry"), "observability"),
    (re.compile(r"src/mediapipeline/core/observability"), "observability"),
    (re.compile(r"src/mediapipeline/contracts/schemas/config"), "config"),
    (re.compile(r"src/mediapipeline/contracts/schemas/stages"), "contracts"),
    (re.compile(r"src/mediapipeline/contracts/schemas/risky_file_registry"), "scripts"),
    (re.compile(r"src/mediapipeline/core/config"), "config"),
    (re.compile(r"src/mediapipeline/contracts"), "contracts"),
    (re.compile(r"ops/pipeline/engine/(\w+)/"), r"\1"),
    (re.compile(r"src/mediapipeline/desktop/api/"), "api"),
    (re.compile(r"src/mediapipeline/desktop/application/sample_validation"), "sample_validation"),
    (re.compile(r"src/mediapipeline/desktop/application/"), "application"),
    (re.compile(r"src/mediapipeline/desktop/watch/"), "watch"),
    (re.compile(r"src/mediapipeline/desktop/network/"), "network"),
    (re.compile(r"src/mediapipeline/desktop/contracts/"), "contracts"),
    (re.compile(r"apps/desktop/webview/static/"), "webview"),
    (re.compile(r"apps/desktop/tauri"), "shell"),
    (re.compile(r"tests/"), "tests"),
    (re.compile(r"tests/python/desktop/"), "tests"),
    (re.compile(r"ops/pipeline/tests"), "tests"),
    (re.compile(r"ops/scripts/|src/mediapipeline/tools/"), "scripts"),
]

HIGH_PRIORITY_HINTS = (
    "transcode",
    "subtitles",
    "mediapipeline.pipeline.ass_to_srt_cli",
    "ass_to_srt",
    "publish/drain",
    "publish/pending",
    "decide",
    "rename/apply",
    "FFmpeg",
    "MediaProbe",
    "Publish.",
    "Pending",
    "EncodePolicy",
    "Routing",
    "Subtitles.",
)
LOW_PRIORITY_HINTS = (
    "__init__",
    "_pycache_",
    "fixtures/",
    "ui_web/static/test_",
)


@dataclass
class PySymbols:
    docstring: str = ""
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    in_repo_imports: list[str] = field(default_factory=list)


@dataclass
class PsSymbols:
    synopsis: str = ""
    functions: list[str] = field(default_factory=list)
    dot_includes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OrphanSummary:
    summary_path: Path
    reason_code: str
    reason: str
    recorded_file: str = ""

    @property
    def display_path(self) -> str:
        return self.summary_path.relative_to(REPO_ROOT).as_posix()


# ---------- helpers ----------

def is_source_file(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = ""
    if is_excluded_source_path(rel):
        return False
    if rel in ROOT_SOURCE_FILES:
        return True
    if rel.startswith("ops/release/changes/") and path.suffix.lower() == ".json":
        return True
    if path.suffix.lower() not in SOURCE_EXTS:
        return False
    for part in path.parts:
        if part in EXCLUDE_DIR_PARTS:
            return False
    return True


def is_excluded_source_path(recorded: str | Path) -> bool:
    rel = Path(recorded).as_posix()
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in EXCLUDE_SOURCE_PREFIXES)


def in_scope_roots(rel_path: Path) -> bool:
    rel = rel_path.as_posix()
    if is_excluded_source_path(rel):
        return False
    if rel in ROOT_SOURCE_FILES:
        return True
    return any(rel.startswith(root + "/") or rel == root for root in SOURCE_ROOTS)


def is_volatile_generated_summary_source(recorded: str | Path) -> bool:
    return Path(recorded).as_posix() in VOLATILE_GENERATED_SUMMARY_FILES


def iter_source_files() -> Iterable[Path]:
    for root_file in sorted(ROOT_SOURCE_FILES):
        path = REPO_ROOT / root_file
        if path.is_file() and is_source_file(path):
            yield path
    for root in SOURCE_ROOTS:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if not is_source_file(path):
                continue
            yield path


def iter_existing_summary_sources() -> Iterable[Path]:
    repo_root = REPO_ROOT.resolve()
    for summary_path in iter_summary_files():
        recorded = summary_recorded_file(summary_path)
        if not recorded:
            continue
        recorded_path = Path(recorded)
        if recorded_path.is_absolute():
            continue
        if is_excluded_source_path(recorded_path):
            continue
        if is_volatile_generated_summary_source(recorded_path):
            continue
        source = (REPO_ROOT / recorded_path).resolve()
        try:
            source.relative_to(repo_root)
        except ValueError:
            continue
        if source.is_file():
            yield source


def iter_known_source_files() -> Iterable[Path]:
    seen: set[Path] = set()
    for path in list(iter_source_files()) + list(iter_existing_summary_sources()):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield path


def summary_path_for_source(rel_path: str | Path, suffix: str) -> Path:
    return SUMMARY_ROOT / Path(rel_path).with_suffix(suffix + ".md")


def is_refreshable_source_path(
    path: Path,
    *,
    explicit: bool = False,
    allow_existing_summary: bool = False,
) -> bool:
    if not path.is_file():
        return False
    if not is_source_file(path):
        return False
    try:
        rel_path = path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    rel = rel_path.as_posix()
    if is_volatile_generated_summary_source(rel):
        return False
    if in_scope_roots(rel_path):
        return True
    if explicit and rel.startswith("ops/release/changes/") and path.suffix.lower() == ".json":
        return True
    return allow_existing_summary and summary_path_for_source(rel, path.suffix).is_file()


def iter_summary_files() -> Iterable[Path]:
    if not SUMMARY_ROOT.exists():
        return []
    return sorted(SUMMARY_ROOT.rglob("*.md"))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def frontmatter_value(summary_path: Path, key: str) -> str | None:
    text = summary_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def summary_recorded_file(summary_path: Path) -> str | None:
    return frontmatter_value(summary_path, "file")


def orphan_summaries(sources: Iterable[Path] | None = None) -> list[OrphanSummary]:
    source_paths = list(iter_known_source_files() if sources is None else sources)
    excluded_prefixes = release_excluded_prefixes(REPO_ROOT)
    expected: dict[str, Path] = {}
    for source in source_paths:
        try:
            rel = source.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        expected[rel] = summary_path_for_source(rel, source.suffix)

    findings: list[OrphanSummary] = []
    for summary_path in iter_summary_files():
        recorded = summary_recorded_file(summary_path)
        if not recorded:
            findings.append(
                OrphanSummary(
                    summary_path=summary_path,
                    reason_code="SUMMARY_FILE_MISSING",
                    reason="summary has no frontmatter file field",
                )
            )
            continue
        recorded_path = Path(recorded)
        if recorded_path.is_absolute():
            findings.append(
                OrphanSummary(
                    summary_path=summary_path,
                    reason_code="SUMMARY_FILE_ABSOLUTE",
                    reason="summary file field must be repo-relative",
                    recorded_file=recorded,
                )
            )
            continue
        normalized_recorded = recorded_path.as_posix()
        if is_release_excluded_path(normalized_recorded, excluded_prefixes):
            # Source intentionally omitted from this release package (e.g. tests);
            # its shipped summary is expected, not an orphan.
            continue
        if is_excluded_source_path(normalized_recorded):
            findings.append(
                OrphanSummary(
                    summary_path=summary_path,
                    reason_code="SOURCE_FILE_EXCLUDED",
                    reason="recorded source file is excluded from generated summaries",
                    recorded_file=normalized_recorded,
                )
            )
            continue
        if normalized_recorded in VOLATILE_GENERATED_SUMMARY_FILES:
            findings.append(
                OrphanSummary(
                    summary_path=summary_path,
                    reason_code="VOLATILE_GENERATED_SUMMARY",
                    reason="generated navigation output summaries are not stable inputs",
                    recorded_file=normalized_recorded,
                )
            )
            continue
        expected_summary = expected.get(normalized_recorded)
        if expected_summary is None:
            findings.append(
                OrphanSummary(
                    summary_path=summary_path,
                    reason_code="SOURCE_FILE_MISSING",
                    reason="recorded source file no longer exists or is out of summary scope",
                    recorded_file=normalized_recorded,
                )
            )
            continue
        if summary_path != expected_summary:
            findings.append(
                OrphanSummary(
                    summary_path=summary_path,
                    reason_code="SUMMARY_PATH_MISMATCH",
                    reason=f"summary is not at expected path {expected_summary.relative_to(REPO_ROOT).as_posix()}",
                    recorded_file=normalized_recorded,
                )
            )
    return findings


def owner_domain_for(rel_path: str) -> str:
    for pat, sub in OWNER_DOMAIN_HINTS:
        m = pat.search(rel_path)
        if m:
            if "\\" in sub or sub.startswith("\\"):
                return m.expand(sub)
            return sub
    return "unknown"


def token_priority_for(rel_path: str) -> str:
    posix = rel_path.replace("\\", "/")
    if any(h in posix for h in HIGH_PRIORITY_HINTS):
        return "high"
    if any(h in posix for h in LOW_PRIORITY_HINTS):
        return "low"
    return "medium"


def pipeline_stage_for(rel_path: str) -> str:
    posix = rel_path.replace("\\", "/")
    mapping = [
        ("ingest", "ingest"),
        ("metadata/probe", "metadata"),
        ("metadata/naming", "metadata"),
        ("MediaProbe", "metadata"),
        ("Naming.", "metadata"),
        ("decide", "decide"),
        ("Routing.", "decide"),
        ("EncodePolicy", "decide"),
        ("transcode", "transcode"),
        ("ffmpeg", "transcode"),
        ("mediapipeline.pipeline.ass_to_srt_cli", "subtitles"),
        ("ass_to_srt", "subtitles"),
        ("subtitles", "subtitles"),
        ("Subtitles.", "subtitles"),
        ("audio", "audio"),
        ("Audio.", "audio"),
        ("publish", "publish"),
        ("Publish.", "publish"),
        ("Pending", "publish"),
        ("rename", "rename"),
        ("network", "network"),
        ("api/", "api"),
        ("orchestration", "orchestration"),
        ("queue", "orchestration"),
        ("Queue", "orchestration"),
        ("schedule", "orchestration"),
        ("observability", "observability"),
        ("telemetry", "observability"),
        ("status", "observability"),
        ("diagnost", "observability"),
        ("Audit-MediaLibrary", "observability"),
        ("audit", "observability"),
        ("Setup-MediaPipeline", "setup"),
        ("setup", "setup"),
        ("contracts", "contracts"),
        ("config", "config"),
    ]
    for needle, stage in mapping:
        if needle in posix:
            return stage
    return "n/a"


# ---------- python parsing ----------

ROUTE_DECORATOR_NAMES = {"route", "get", "post", "put", "delete", "patch", "websocket"}


def parse_python(path: Path) -> PySymbols:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return PySymbols(docstring=f"(syntax error parsing {path.name})")

    sym = PySymbols()
    sym.docstring = (ast.get_docstring(tree) or "").strip().split("\n", 1)[0]

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            sym.classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                sym.functions.append(f"{node.name}()")
            for dec in node.decorator_list:
                route = _route_path_from_decorator(dec)
                if route:
                    sym.routes.append(route)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(".") or module.startswith("app") or module.startswith("mediapipeline"):
                sym.in_repo_imports.append(module or "(relative)")

    sym.classes = sorted(set(sym.classes))[:15]
    sym.functions = sorted(set(sym.functions))[:20]
    sym.routes = sorted(set(sym.routes))[:15]
    sym.in_repo_imports = sorted(set(sym.in_repo_imports))[:15]
    return sym


def _route_path_from_decorator(dec: ast.expr) -> str | None:
    target = dec.func if isinstance(dec, ast.Call) else dec
    name = ""
    if isinstance(target, ast.Attribute):
        name = target.attr
    elif isinstance(target, ast.Name):
        name = target.id
    if name not in ROUTE_DECORATOR_NAMES:
        return None
    if not isinstance(dec, ast.Call) or not dec.args:
        return name
    first = dec.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return f"{name.upper()} {first.value}"
    return name


# ---------- powershell parsing ----------

PS_SYNOPSIS_RE = re.compile(r"\.SYNOPSIS\s*\n\s*(.+?)(?:\n\s*\.|\n\s*#>)", re.IGNORECASE | re.DOTALL)
PS_FUNCTION_RE = re.compile(r"^\s*function\s+([A-Za-z][A-Za-z0-9_\-]*)", re.MULTILINE)
PS_DOTSOURCE_RE = re.compile(r"^\s*\.\s+\$?[\w:.\\/\$\(\)]+[\\\/]([\w.\-]+\.ps1)", re.MULTILINE)


def parse_powershell(path: Path) -> PsSymbols:
    text = path.read_text(encoding="utf-8", errors="replace")
    sym = PsSymbols()
    m = PS_SYNOPSIS_RE.search(text)
    if m:
        sym.synopsis = m.group(1).strip().split("\n", 1)[0]
    sym.functions = sorted(set(PS_FUNCTION_RE.findall(text)))[:25]
    sym.dot_includes = sorted(set(PS_DOTSOURCE_RE.findall(text)))[:15]
    return sym


# ---------- summary rendering ----------

def existing_summary_sha(summary_path: Path) -> str | None:
    if not summary_path.exists():
        return None
    text = summary_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^sha256:\s*([0-9a-f]+)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def existing_last_reviewed(summary_path: Path) -> str | None:
    if not summary_path.exists():
        return None
    text = summary_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^last_reviewed:\s*(\S+)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def render_summary(rel_path: str, source: Path) -> str:
    sha = sha256_of(source)
    stat = source.stat()
    last_mod = datetime.fromtimestamp(stat.st_mtime).date().isoformat()
    today = date.today().isoformat()
    owner = owner_domain_for(rel_path)
    priority = token_priority_for(rel_path)
    stage = pipeline_stage_for(rel_path)
    summary_path = summary_path_for_source(rel_path, source.suffix)
    prior_reviewed = existing_last_reviewed(summary_path) or today

    lines: list[str] = []
    lines.append("---")
    lines.append(f"file: {rel_path}")
    lines.append(f"pipeline_stage: {stage}")
    lines.append(f"token_priority: {priority}")
    lines.append(f"owner_domain: {owner}")
    lines.append(f"last_modified: {last_mod}")
    lines.append(f"last_reviewed: {prior_reviewed}")
    lines.append(f"sha256: {sha}")
    lines.append("---")
    lines.append(f"# `{rel_path}`")
    lines.append("")

    suffix = source.suffix.lower()
    if suffix == ".py":
        sym = parse_python(source)
        lines.append(f"**Purpose:** {sym.docstring or '(no module docstring)'}")
        lines.append("")
        if sym.classes:
            lines.append("**Classes:** " + ", ".join(f"`{c}`" for c in sym.classes))
        if sym.functions:
            lines.append("**Public functions:** " + ", ".join(f"`{f}`" for f in sym.functions))
        if sym.routes:
            lines.append("**HTTP routes:** " + ", ".join(f"`{r}`" for r in sym.routes))
        if sym.in_repo_imports:
            lines.append("**In-repo imports:** " + ", ".join(f"`{i}`" for i in sym.in_repo_imports))
    elif suffix in (".ps1", ".psm1"):
        sym = parse_powershell(source)
        lines.append(f"**Purpose:** {sym.synopsis or '(no .SYNOPSIS block)'}")
        lines.append("")
        if sym.functions:
            lines.append("**Functions:** " + ", ".join(f"`{f}`" for f in sym.functions))
        if sym.dot_includes:
            lines.append("**Dot-sourced:** " + ", ".join(f"`{d}`" for d in sym.dot_includes))
    elif suffix == ".psd1":
        lines.append("**Purpose:** PowerShell data file (config or manifest).")
    elif suffix == ".rs":
        lines.append("**Purpose:** Rust source (Tauri shell).")
    else:
        lines.append("**Purpose:** (unparsed)")

    lines.append("")
    lines.append(f"_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths {rel_path}`._")
    lines.append("")
    return "\n".join(lines)


def write_summary(rel_path: str, source: Path) -> bool:
    """Return True if the summary was written or changed."""
    summary_path = summary_path_for_source(rel_path, source.suffix)
    new_content = render_summary(rel_path, source)
    if summary_path.exists() and summary_path.read_text(encoding="utf-8") == new_content:
        return False
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(new_content, encoding="utf-8")
    return True


# ---------- git helpers ----------

def git_changed(staged: bool) -> list[Path]:
    args = ["git", "diff", "--name-only"]
    if staged:
        args.append("--cached")
    else:
        args.append("HEAD")
    try:
        out = subprocess.check_output(args, cwd=REPO_ROOT, text=True)
    except subprocess.CalledProcessError:
        return []
    result: list[Path] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        p = REPO_ROOT / line
        if is_refreshable_source_path(p, allow_existing_summary=True):
            result.append(p)
    return result


# ---------- main ----------

def collect_sources(args: argparse.Namespace) -> list[Path]:
    if args.paths:
        return [
            REPO_ROOT / p
            for p in args.paths
            if is_refreshable_source_path(REPO_ROOT / p, explicit=True, allow_existing_summary=True)
        ]
    if args.changed:
        return git_changed(staged=False)
    if args.staged:
        return git_changed(staged=True)
    return list(iter_known_source_files())


def cmd_check(sources: list[Path], *, check_orphans: bool = False) -> int:
    stale: list[str] = []
    missing: list[str] = []
    for path in sources:
        rel = path.relative_to(REPO_ROOT).as_posix()
        summary_path = summary_path_for_source(rel, path.suffix)
        recorded = existing_summary_sha(summary_path)
        if recorded is None:
            missing.append(rel)
            continue
        if recorded != sha256_of(path):
            stale.append(rel)
    orphans = orphan_summaries(sources) if check_orphans else []
    if not stale and not missing and not orphans:
        print(f"OK: {len(sources)} source files all have current summaries and no orphan summaries.")
        return 0
    if missing:
        print(f"Missing summaries ({len(missing)}):")
        for p in missing[:50]:
            print(f"  {p}")
    if stale:
        print(f"Stale summaries ({len(stale)}):")
        for p in stale[:50]:
            print(f"  {p}")
    if orphans:
        print(f"Orphan summaries ({len(orphans)}):")
        for finding in orphans[:50]:
            suffix = f" -> {finding.recorded_file}" if finding.recorded_file else ""
            print(f"  {finding.display_path}: {finding.reason_code}{suffix}")
    print("Run: apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed   (or --all --prune-orphans)")
    return 1


def prune_orphan_summaries(sources: list[Path]) -> int:
    removed = 0
    summary_root = SUMMARY_ROOT.resolve()
    for finding in orphan_summaries(sources):
        path = finding.summary_path
        try:
            path.resolve().relative_to(summary_root)
        except ValueError:
            print(f"Refusing to prune summary outside docs/generated/summaries/: {path}", file=sys.stderr)
            continue
        if path.suffix.lower() != ".md":
            print(f"Refusing to prune non-Markdown summary path: {path}", file=sys.stderr)
            continue
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            print(f"ERROR pruning {path.relative_to(REPO_ROOT).as_posix()}: {exc}", file=sys.stderr)
    return removed


def cmd_generate(sources: list[Path], *, prune_orphans: bool = False) -> int:
    written = 0
    unchanged = 0
    for path in sources:
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            changed = write_summary(rel, path)
        except OSError as exc:
            print(f"ERROR writing summary for {rel}: {exc}", file=sys.stderr)
            return 2
        if changed:
            written += 1
        else:
            unchanged += 1
    pruned = prune_orphan_summaries(sources) if prune_orphans else 0
    suffix = f", {pruned} orphan summaries pruned" if prune_orphans else ""
    print(f"Summaries: {written} written, {unchanged} unchanged{suffix}. Source files: {len(sources)}.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="Regenerate every in-scope summary.")
    mode.add_argument("--changed", action="store_true", help="Regenerate for files changed vs HEAD.")
    mode.add_argument("--staged", action="store_true", help="Regenerate for staged files (pre-commit).")
    mode.add_argument("--check", action="store_true", help="Verify summary freshness; exit non-zero if stale.")
    parser.add_argument("--prune-orphans", action="store_true", help="With --all, remove summaries for deleted/out-of-scope sources.")
    parser.add_argument("--paths", nargs="*", default=[], help="Specific paths to operate on.")
    args = parser.parse_args(argv)
    if args.prune_orphans and not args.all:
        parser.error("--prune-orphans must be used with --all")

    SUMMARY_ROOT.mkdir(exist_ok=True)

    if not (args.all or args.changed or args.staged or args.check or args.paths):
        # Default: regenerate for changed files (cheap), fall back to all if none changed.
        sources = git_changed(staged=False)
        if not sources:
            print("No changed source files vs HEAD; nothing to do. Use --all to regenerate everything.")
            return 0
        return cmd_generate(sources)

    sources = collect_sources(args)
    if args.check:
        # In --check mode, always check the full inventory unless paths/changed/staged is set.
        check_orphans = not (args.paths or args.changed or args.staged)
        if check_orphans:
            sources = list(iter_known_source_files())
        return cmd_check(sources, check_orphans=check_orphans)

    return cmd_generate(sources, prune_orphans=args.prune_orphans)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
