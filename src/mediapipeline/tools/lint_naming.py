"""Fail on new filenames that recreate deprecated overhaul-era patterns.

The repository still contains grandfathered legacy files. This lint therefore
checks creation candidates by default: added/copied/renamed/untracked paths in
the current working tree. Use --paths in tests, --staged from pre-commit, and
--git-diff <base> in CI pull-request checks.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root, PurePosixPath
from typing import Iterable


REPO_ROOT = find_repo_root(Path(__file__))

ALLOWED_ROOT_STATUS_DOCS = {
    "docs/OPEN_WORK_CHECKLIST.md",
}

FORBIDDEN_SUFFIXES = ("_chatgpt", "_old", "_new")


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str
    source_path: str | None = None


@dataclass(frozen=True)
class NamingFinding:
    rule_id: str
    path: str
    reason: str
    fix: str


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(normalize_path(path)).parts


def _is_root_path(path: str) -> bool:
    return len(_parts(path)) == 1


def _is_direct_child(path: str, parent: str) -> bool:
    rel = normalize_path(path)
    prefix = normalize_path(parent) + "/"
    if not rel.startswith(prefix):
        return False
    return "/" not in rel[len(prefix) :]


def is_creation_status(status: str) -> bool:
    return "?" in status or any(marker in status for marker in ("A", "R", "C"))


def parse_porcelain_status_line(line: str) -> ChangedPath | None:
    if not line.strip() or len(line) < 4:
        return None
    status = line[:2]
    payload = line[3:].strip()
    source_path: str | None = None
    path = payload
    if " -> " in payload:
        source_path, path = payload.split(" -> ", 1)
    return ChangedPath(
        status=status,
        path=normalize_path(path),
        source_path=normalize_path(source_path) if source_path else None,
    )


def creation_candidates_from_status(text: str) -> list[ChangedPath]:
    candidates: list[ChangedPath] = []
    for line in text.splitlines():
        changed = parse_porcelain_status_line(line)
        if changed and is_creation_status(changed.status):
            candidates.append(changed)
    return candidates


def creation_candidates_from_name_status(text: str) -> list[ChangedPath]:
    candidates: list[ChangedPath] = []
    for line in text.splitlines():
        fields = line.split("\t")
        if not fields:
            continue
        status = fields[0]
        if status.startswith(("A", "C")) and len(fields) >= 2:
            candidates.append(ChangedPath(status=status, path=normalize_path(fields[-1])))
        elif status.startswith("R") and len(fields) >= 3:
            candidates.append(
                ChangedPath(
                    status=status,
                    path=normalize_path(fields[-1]),
                    source_path=normalize_path(fields[-2]),
                )
            )
    return candidates


def git_working_tree_candidates() -> list[ChangedPath]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return creation_candidates_from_status(result.stdout)


def git_staged_candidates() -> list[ChangedPath]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=ACR"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return creation_candidates_from_name_status(result.stdout)


def git_diff_candidates(base_ref: str) -> list[ChangedPath]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "--diff-filter=ACR", f"{base_ref}...HEAD"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return creation_candidates_from_name_status(result.stdout)


def findings_for_path(path: str, *, is_new: bool = True) -> list[NamingFinding]:
    if not is_new:
        return []

    rel = normalize_path(path)
    name = PurePosixPath(rel).name
    suffix = PurePosixPath(rel).suffix.lower()
    stem = PurePosixPath(rel).stem
    stem_folded = stem.casefold()
    findings: list[NamingFinding] = []

    if _is_direct_child(rel, "src/mediapipeline/desktop/application") and fnmatchcase(
        name, "facade_*.py"
    ):
        findings.append(
            NamingFinding(
                rule_id="NAME001",
                path=rel,
                reason="New flat application facade files preserve the legacy suffix-based layout.",
                fix="Place new backend application code under src/mediapipeline/core/<domain>/<role>.py instead.",
            )
        )

    if _is_direct_child(rel, "src/mediapipeline/desktop") and fnmatchcase(name, "service_*.py"):
        findings.append(
            NamingFinding(
                rule_id="NAME002",
                path=rel,
                reason="New flat service files preserve the legacy suffix-based layout.",
                fix="Place new service code under src/mediapipeline/core/<domain>/<role>.py or src/mediapipeline/desktop/<domain>/<role>.py instead.",
            )
        )

    if _is_direct_child(rel, "src/mediapipeline/desktop/api") and fnmatchcase(
        name, "command_payloads_*.py"
    ):
        findings.append(
            NamingFinding(
                rule_id="NAME003",
                path=rel,
                reason="New command_payloads_* modules extend a validation fan-out targeted for removal.",
                fix="Use the target src/mediapipeline/core/<domain>/ contract or schema boundary instead.",
            )
        )

    if _is_direct_child(rel, "Pipeline/Modules") and suffix == ".ps1" and "." in stem:
        findings.append(
            NamingFinding(
                rule_id="NAME004",
                path=rel,
                reason="New dotted PowerShell modules keep the legacy Pipeline/Modules naming pattern alive.",
                fix="Place new PowerShell engine code under ops/pipeline/engine/<domain>/<role>.ps1 instead.",
            )
        )

    if (
        _is_root_path(rel)
        and suffix == ".md"
        and name.endswith(("_REPORT.md", "_FIXES.md", "_CHECKLIST.md"))
        and name not in ALLOWED_ROOT_STATUS_DOCS
    ):
        findings.append(
            NamingFinding(
                rule_id="NAME005",
                path=rel,
                reason="New top-level report/fix/checklist Markdown becomes non-canonical project state.",
                fix="Use CHANGELOG.md, the relevant docs/ page, or docs/OPEN_WORK_CHECKLIST.md as appropriate.",
            )
        )

    if _is_root_path(rel) and suffix in {".bat", ".ps1"}:
        findings.append(
            NamingFinding(
                rule_id="NAME006",
                path=rel,
                reason="New or reintroduced root launchers bypass the scripts/ layout.",
                fix="Use ops/scripts/dev, ops/scripts/operator, ops/scripts/release, or ops/scripts/dev/verify-env.* instead.",
            )
        )

    forbidden_suffix = next((item for item in FORBIDDEN_SUFFIXES if stem_folded.endswith(item)), "")
    if forbidden_suffix:
        findings.append(
            NamingFinding(
                rule_id="NAME007",
                path=rel,
                reason=f"New files must not use the deprecated {forbidden_suffix!r} suffix.",
                fix="Use the canonical target name now; keep historical context in CHANGELOG.md or ADRs.",
            )
        )

    return findings


def findings_for_paths(paths: Iterable[str], *, is_new: bool = True) -> list[NamingFinding]:
    findings: list[NamingFinding] = []
    for path in paths:
        findings.extend(findings_for_path(path, is_new=is_new))
    return findings


def render_findings(findings: Iterable[NamingFinding]) -> str:
    lines = [
        "Naming lint found violation(s):",
        "Fix the flagged path or use an existing compatibility shim. Do not add new legacy-pattern files.",
    ]
    for finding in findings:
        lines.extend(
            (
                f"- {finding.rule_id}: {finding.path}",
                f"  Reason: {finding.reason}",
                f"  Fix: {finding.fix}",
            )
        )
    return "\n".join(lines)


def collect_candidates(args: argparse.Namespace) -> list[ChangedPath]:
    if args.paths:
        return [ChangedPath(status="PATH", path=normalize_path(path)) for path in args.paths]
    if args.git_diff:
        return git_diff_candidates(args.git_diff)
    if args.staged:
        return git_staged_candidates()
    return git_working_tree_candidates()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Treat the listed repo-relative paths as new creation candidates.",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check staged added/copied/renamed paths instead of the full working tree.",
    )
    parser.add_argument(
        "--git-diff",
        metavar="BASE_REF",
        help="Check added/copied/renamed paths between BASE_REF...HEAD.",
    )
    args = parser.parse_args(argv)

    try:
        candidates = collect_candidates(args)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: unable to collect naming-lint candidates: {exc}", file=sys.stderr)
        return 2

    findings = findings_for_paths(candidate.path for candidate in candidates)
    if findings:
        print(render_findings(findings), file=sys.stderr)
        return 1

    print(f"Naming lint passed. Checked {len(candidates)} creation candidate(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
