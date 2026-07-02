"""Flag marketing buzzwords (marketecture) in docs and source.

Keeps project language concrete by failing on clear marketing fluff such as
"world-class", "synergy", or "cutting-edge". Ambiguous technical words
(robust, leverage, scalable, first-class) are deliberately not listed to avoid
false positives. Suppress a justified single line with the inline marker
"allow-marketecture".

By default this scans the content of changed files in the working tree, so it
never blocks on pre-existing wording in files the current task did not touch.
Use --all for a full-repository audit, --staged from pre-commit, --git-diff
<base> in CI, or --paths in tests.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from collections.abc import Iterable, Sequence


REPO_ROOT = find_repo_root(Path(__file__))
POLICY_PATH = REPO_ROOT / "docs" / "inventories" / "MARKETECTURE_GUARDRAIL.v1.json"
SCHEMA_VERSION = "marketecture_guardrail.v1"
SUPPRESSION_MARKER = "allow-marketecture"

# Fallback values used when the policy file is missing or unreadable. The policy
# file at POLICY_PATH is the source of truth; these mirrors only keep the guard
# functional in a degraded checkout.
BUILTIN_TERMS: tuple[str, ...] = (
    "world-class",
    "best-in-class",
    "best-of-breed",
    "cutting-edge",
    "bleeding-edge",
    "state-of-the-art",
    "next-generation",
    "next-gen",
    "game-changer",
    "game-changing",
    "revolutionary",
    "paradigm shift",
    "synergy",
    "synergies",
    "turnkey",
    "supercharge",
    "supercharged",
    "frictionless",
    "rock-solid",
    "battle-tested",
    "enterprise-grade",
    "military-grade",
    "future-proof",
    "secret sauce",
    "unparalleled",
    "blazing-fast",
    "blazing fast",
    "lightning-fast",
    "one-stop shop",
    "hyper-scale",
    "web-scale",
)

BUILTIN_INCLUDE_GLOBS: tuple[str, ...] = (
    "**/*.md",
    "**/*.py",
    "**/*.ps1",
    "**/*.psm1",
    "**/*.js",
    "**/*.mjs",
    "**/*.rs",
)

BUILTIN_EXCLUDE_GLOBS: tuple[str, ...] = (
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/Runtime/**",
    "**/runtime/**",
    "**/target/**",
    "docs/archive/**",
    "LocalBase/**",
    "external-rollback/**",
    "docs/inventories/MARKETECTURE_GUARDRAIL.v1.json",
    "src/mediapipeline/tools/dev/check_marketecture.py",
    "tests/python/desktop/test_marketecture_guard.py",
)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: str
    line: int
    term: str
    detail: str


@dataclass(frozen=True)
class CandidatePath:
    path: str
    status: str = "PATH"


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _load_policy(path: Path = POLICY_PATH) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_terms(path: Path = POLICY_PATH) -> list[str]:
    policy = _load_policy(path)
    terms = policy.get("terms")
    if isinstance(terms, list):
        cleaned = [str(term).strip().lower() for term in terms if str(term).strip()]
        if cleaned:
            return cleaned
    return [term.lower() for term in BUILTIN_TERMS]


def load_include_globs(path: Path = POLICY_PATH) -> list[str]:
    policy = _load_policy(path)
    globs = policy.get("include_globs")
    if isinstance(globs, list) and globs:
        return [str(item) for item in globs if str(item).strip()]
    return list(BUILTIN_INCLUDE_GLOBS)


def load_exclude_globs(path: Path = POLICY_PATH) -> list[str]:
    policy = _load_policy(path)
    globs = policy.get("exclude_globs")
    if isinstance(globs, list) and globs:
        return [str(item) for item in globs if str(item).strip()]
    return list(BUILTIN_EXCLUDE_GLOBS)


def load_suppression_marker(path: Path = POLICY_PATH) -> str:
    policy = _load_policy(path)
    marker = policy.get("suppression_marker")
    if isinstance(marker, str) and marker.strip():
        return marker.strip()
    return SUPPRESSION_MARKER


def compile_terms(terms: Iterable[str]) -> list[tuple[str, re.Pattern[str]]]:
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for term in terms:
        # Match the term as a standalone token: not bordered by a word character
        # or hyphen, so "world-class" matches while "synergyx" or an inner
        # fragment of a longer hyphenated identifier does not produce noise.
        pattern = re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.IGNORECASE)
        compiled.append((term, pattern))
    return compiled


def findings_for_text(
    text: str,
    relative_path: str,
    *,
    term_patterns: Sequence[tuple[str, re.Pattern[str]]] | None = None,
    suppression_marker: str = SUPPRESSION_MARKER,
) -> list[Finding]:
    patterns = term_patterns if term_patterns is not None else compile_terms(load_terms())
    rel = normalize_path(relative_path)
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if suppression_marker and suppression_marker in line:
            continue
        for term, pattern in patterns:
            if pattern.search(line):
                findings.append(
                    Finding(
                        rule_id="MKT001",
                        path=rel,
                        line=line_no,
                        term=term,
                        detail=f"marketing buzzword: {term}",
                    )
                )
    return findings


def _matches_glob(rel: str, pattern: str) -> bool:
    norm = normalize_path(pattern)
    if fnmatchcase(rel, norm):
        return True
    # A leading "**/" should also match at the repository root, where there is
    # no parent segment before the named directory (e.g. "**/node_modules/**"
    # must match "node_modules/pkg/readme.md").
    if norm.startswith("**/") and fnmatchcase(rel, norm[3:]):
        return True
    return False


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    rel = normalize_path(path)
    return any(_matches_glob(rel, pattern) for pattern in patterns)


def is_scannable(path: str, include_globs: Iterable[str], exclude_globs: Iterable[str]) -> bool:
    return _matches_any(path, include_globs) and not _matches_any(path, exclude_globs)


def parse_porcelain_status_line(line: str) -> CandidatePath | None:
    if not line.strip() or len(line) < 4:
        return None
    status = line[:2]
    payload = line[3:].strip()
    if " -> " in payload:
        _source, payload = payload.split(" -> ", 1)
    if not payload:
        return None
    return CandidatePath(path=normalize_path(payload), status=status)


def changed_candidates_from_status(text: str) -> list[CandidatePath]:
    candidates: list[CandidatePath] = []
    for line in text.splitlines():
        candidate = parse_porcelain_status_line(line)
        # Deletions are filtered later by the on-disk is_file() check.
        if candidate:
            candidates.append(candidate)
    return candidates


def staged_candidates_from_name_status(text: str) -> list[CandidatePath]:
    candidates: list[CandidatePath] = []
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        candidates.append(CandidatePath(path=normalize_path(fields[-1]), status=fields[0]))
    return candidates


def git_changed_candidates() -> list[CandidatePath]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return changed_candidates_from_status(result.stdout)


def git_staged_candidates() -> list[CandidatePath]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=ACMR"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return staged_candidates_from_name_status(result.stdout)


def git_diff_candidates(base_ref: str) -> list[CandidatePath]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "--diff-filter=ACMR", f"{base_ref}...HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return staged_candidates_from_name_status(result.stdout)


def git_all_candidates() -> list[CandidatePath]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [CandidatePath(path=normalize_path(line), status="ALL") for line in result.stdout.splitlines() if line.strip()]


def collect_candidates(args: argparse.Namespace) -> list[CandidatePath]:
    if args.paths:
        return [CandidatePath(path=normalize_path(path)) for path in args.paths]
    if args.all:
        return git_all_candidates()
    if args.git_diff:
        return git_diff_candidates(args.git_diff)
    if args.staged:
        return git_staged_candidates()
    return git_changed_candidates()


def findings_for_candidates(
    candidates: Iterable[CandidatePath],
    *,
    root: Path = REPO_ROOT,
    include_globs: Sequence[str],
    exclude_globs: Sequence[str],
    term_patterns: Sequence[tuple[str, re.Pattern[str]]],
    suppression_marker: str,
) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    seen: set[str] = set()
    scanned = 0
    for candidate in candidates:
        rel = normalize_path(candidate.path)
        if rel in seen:
            continue
        seen.add(rel)
        if not is_scannable(rel, include_globs, exclude_globs):
            continue
        full_path = root / rel
        if not full_path.is_file():
            continue
        scanned += 1
        text = full_path.read_text(encoding="utf-8", errors="ignore")
        findings.extend(
            findings_for_text(
                text,
                rel,
                term_patterns=term_patterns,
                suppression_marker=suppression_marker,
            )
        )
    return findings, scanned


def render_findings(findings: Sequence[Finding], *, scanned: int, report_limit: int) -> str:
    if not findings:
        return f"Marketecture guard passed. Scanned {scanned} file(s)."
    lines = [f"Marketecture guard found {len(findings)} buzzword finding(s) across {scanned} scanned file(s):"]
    ordered = sorted(findings, key=lambda item: (item.path, item.line, item.term))
    for finding in ordered[:report_limit]:
        lines.append(f"- {finding.rule_id}: {finding.path}:{finding.line}: {finding.detail}")
    if len(findings) > report_limit:
        lines.append(f"... {len(findings) - report_limit} additional finding(s) omitted by report_limit.")
    lines.append(
        "Replace the flagged wording with concrete language, or add the inline marker "
        f"'{SUPPRESSION_MARKER}' on the line if the term is genuinely warranted."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Scan all tracked and untracked source candidates.")
    parser.add_argument("--staged", action="store_true", help="Scan staged added/copied/renamed/modified paths.")
    parser.add_argument("--git-diff", metavar="BASE_REF", help="Scan changed paths between BASE_REF...HEAD.")
    parser.add_argument("--paths", nargs="*", default=[], help="Scan explicit repo-relative paths.")
    parser.add_argument("--report-limit", type=int, default=50, help="Maximum findings to print.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    include_globs = load_include_globs()
    exclude_globs = load_exclude_globs()
    term_patterns = compile_terms(load_terms())
    suppression_marker = load_suppression_marker()

    try:
        candidates = collect_candidates(args)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: unable to collect marketecture candidates: {exc}", file=sys.stderr)
        return 2

    findings, scanned = findings_for_candidates(
        candidates,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        term_patterns=term_patterns,
        suppression_marker=suppression_marker,
    )

    if args.json:
        print(
            json.dumps(
                {"ok": not findings, "scanned": scanned, "findings": [finding.__dict__ for finding in findings]},
                indent=2,
            )
        )
        return 1 if findings else 0

    output = render_findings(findings, scanned=scanned, report_limit=args.report_limit)
    print(output, file=sys.stderr if findings else sys.stdout)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
