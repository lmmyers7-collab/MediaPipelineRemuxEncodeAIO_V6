"""Generate per-source-file summaries under summaries/.

One summary file per Python or PowerShell source file in the configured
roots. Summaries carry YAML frontmatter (file path, sha256, last_modified,
token_priority, owner_domain) and a short Markdown body listing module
purpose plus public symbols.

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
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_ROOT = REPO_ROOT / "summaries"

SOURCE_ROOTS = [
    "app",
    "engine",
    "scripts",
    "tests",
    "DesktopApp/mediapipeline_desktop_app",
    "DesktopApp/tauri_shell/src-tauri/src",
    "Pipeline/Modules",
    "Pipeline/Tests",
]

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

SOURCE_EXTS = {".py", ".ps1", ".psm1", ".psd1", ".rs"}

OWNER_DOMAIN_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"app/api"), "api"),
    (re.compile(r"app/orchestration"), "orchestration"),
    (re.compile(r"app/ingest"), "ingest"),
    (re.compile(r"app/metadata"), "metadata"),
    (re.compile(r"app/decide"), "decide"),
    (re.compile(r"app/transcode"), "transcode"),
    (re.compile(r"app/subtitles"), "subtitles"),
    (re.compile(r"app/audio"), "audio"),
    (re.compile(r"app/publish"), "publish"),
    (re.compile(r"app/rename"), "rename"),
    (re.compile(r"app/storage"), "storage"),
    (re.compile(r"app/network"), "network"),
    (re.compile(r"app/observability"), "observability"),
    (re.compile(r"app/config"), "config"),
    (re.compile(r"app/contracts"), "contracts"),
    (re.compile(r"engine/(\w+)/"), r"\1"),
    (re.compile(r"DesktopApp/.*/api/"), "api"),
    (re.compile(r"DesktopApp/.*/application/"), "application"),
    (re.compile(r"DesktopApp/.*/network/"), "network"),
    (re.compile(r"DesktopApp/.*/contracts/"), "contracts"),
    (re.compile(r"DesktopApp/.*/ui_web/"), "webview"),
    (re.compile(r"DesktopApp/tauri_shell"), "shell"),
    (re.compile(r"DesktopApp/tests/"), "tests"),
    (re.compile(r"Pipeline/Modules/(Audio|Audit|MediaProbe|Naming|Subtitles|Publish|Routing|EncodePolicy|PipelineEngine|LocalWorkerSlots|DecisionTrace|FailureCodes|FailureState|PendingTransactions|PendingManifestStore|PendingPublishIndex|PendingPush|QueuePlan|Routing|Setup|Root)"), r"\1"),
    (re.compile(r"Pipeline/Modules"), "engine-legacy"),
    (re.compile(r"Pipeline/Tests"), "tests"),
    (re.compile(r"scripts/"), "scripts"),
]

HIGH_PRIORITY_HINTS = (
    "transcode",
    "subtitles",
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


# ---------- helpers ----------

def is_source_file(path: Path) -> bool:
    if path.suffix.lower() not in SOURCE_EXTS:
        return False
    for part in path.parts:
        if part in EXCLUDE_DIR_PARTS:
            return False
    return True


def in_scope_roots(rel_path: Path) -> bool:
    rel = rel_path.as_posix()
    return any(rel.startswith(root + "/") or rel == root for root in SOURCE_ROOTS)


def iter_source_files() -> Iterable[Path]:
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


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
        ("contracts", "contracts"),
        ("config", "config"),
        ("observability", "observability"),
        ("telemetry", "observability"),
        ("status", "observability"),
        ("diagnost", "observability"),
        ("audit", "observability"),
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
    summary_path = SUMMARY_ROOT / Path(rel_path).with_suffix(source.suffix + ".md")
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
    lines.append(f"_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths {rel_path}`._")
    lines.append("")
    return "\n".join(lines)


def write_summary(rel_path: str, source: Path) -> bool:
    """Return True if the summary was written or changed."""
    summary_path = SUMMARY_ROOT / Path(rel_path).with_suffix(source.suffix + ".md")
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
        if p.is_file() and is_source_file(p) and in_scope_roots(p.relative_to(REPO_ROOT)):
            result.append(p)
    return result


# ---------- main ----------

def collect_sources(args: argparse.Namespace) -> list[Path]:
    if args.paths:
        return [REPO_ROOT / p for p in args.paths if (REPO_ROOT / p).is_file()]
    if args.changed:
        return git_changed(staged=False)
    if args.staged:
        return git_changed(staged=True)
    return list(iter_source_files())


def cmd_check(sources: list[Path]) -> int:
    stale: list[str] = []
    missing: list[str] = []
    for path in sources:
        rel = path.relative_to(REPO_ROOT).as_posix()
        summary_path = SUMMARY_ROOT / Path(rel).with_suffix(path.suffix + ".md")
        recorded = existing_summary_sha(summary_path)
        if recorded is None:
            missing.append(rel)
            continue
        if recorded != sha256_of(path):
            stale.append(rel)
    if not stale and not missing:
        print(f"OK: {len(sources)} source files all have current summaries.")
        return 0
    if missing:
        print(f"Missing summaries ({len(missing)}):")
        for p in missing[:50]:
            print(f"  {p}")
    if stale:
        print(f"Stale summaries ({len(stale)}):")
        for p in stale[:50]:
            print(f"  {p}")
    print("Run: python scripts/dev/refresh_summaries.py --changed   (or --all)")
    return 1


def cmd_generate(sources: list[Path]) -> int:
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
    print(f"Summaries: {written} written, {unchanged} unchanged. Source files: {len(sources)}.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="Regenerate every in-scope summary.")
    mode.add_argument("--changed", action="store_true", help="Regenerate for files changed vs HEAD.")
    mode.add_argument("--staged", action="store_true", help="Regenerate for staged files (pre-commit).")
    mode.add_argument("--check", action="store_true", help="Verify summary freshness; exit non-zero if stale.")
    parser.add_argument("--paths", nargs="*", default=[], help="Specific paths to operate on.")
    args = parser.parse_args(argv)

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
        if not (args.paths or args.changed or args.staged):
            sources = list(iter_source_files())
        return cmd_check(sources)

    return cmd_generate(sources)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
