"""Fail fast on new files that violate the architecture-overhaul layout.

The current tree still contains grandfathered V6 legacy files. This guard is
therefore creation-only by default: it checks added, renamed/copied, and
untracked paths from the working tree, while allowing edits to existing legacy
files until their owning domain is migrated.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_ROOT_STATUS_DOCS = {
    "OPEN_WORK_CHECKLIST.md",
}


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str
    source_path: str | None = None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: str
    reason: str
    fix: str


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def is_creation_status(status: str) -> bool:
    return "?" in status or any(marker in status for marker in ("A", "R", "C"))


def parse_porcelain_status_line(line: str) -> ChangedPath | None:
    if not line.strip():
        return None
    if len(line) < 4:
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


def staged_creation_candidates(text: str) -> list[ChangedPath]:
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
    return staged_creation_candidates(result.stdout)


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


def findings_for_path(path: str) -> list[Finding]:
    rel = normalize_path(path)
    name = PurePosixPath(rel).name
    suffix = PurePosixPath(rel).suffix.lower()
    stem = PurePosixPath(rel).stem
    findings: list[Finding] = []

    if _is_direct_child(rel, "DesktopApp/mediapipeline_desktop_app/application") and fnmatchcase(
        name, "facade_*.py"
    ):
        findings.append(
            Finding(
                rule_id="ARCH001",
                path=rel,
                reason="New flat application facade files preserve the legacy suffix-based layout.",
                fix="Place new application code under app/<domain>/<role>.py instead.",
            )
        )

    if _is_direct_child(rel, "DesktopApp/mediapipeline_desktop_app") and fnmatchcase(
        name, "service_*.py"
    ):
        findings.append(
            Finding(
                rule_id="ARCH002",
                path=rel,
                reason="New flat service files preserve the legacy suffix-based layout.",
                fix="Place new service code under app/<domain>/<role>.py instead.",
            )
        )

    if _is_direct_child(rel, "DesktopApp/mediapipeline_desktop_app/api") and fnmatchcase(
        name, "command_payloads_*.py"
    ):
        findings.append(
            Finding(
                rule_id="ARCH003",
                path=rel,
                reason="New command_payloads_* modules extend a validation fan-out targeted for removal.",
                fix="Use the target app/<domain>/ contract or schema boundary instead.",
            )
        )

    if _is_direct_child(rel, "Pipeline/Modules") and suffix == ".ps1" and "." in stem:
        findings.append(
            Finding(
                rule_id="ARCH004",
                path=rel,
                reason="New dotted PowerShell modules keep the legacy Pipeline/Modules naming pattern alive.",
                fix="Place new PowerShell engine code under engine/<domain>/<role>.ps1 instead.",
            )
        )

    if (
        _is_root_path(rel)
        and name.endswith(("_REPORT.md", "_FIXES.md", "_CHECKLIST.md"))
        and name not in ALLOWED_ROOT_STATUS_DOCS
    ):
        findings.append(
            Finding(
                rule_id="ARCH005",
                path=rel,
                reason="New top-level status Markdown files become non-canonical project state.",
                fix="Use CHANGELOG.md, the relevant Docs/ page, or OPEN_WORK_CHECKLIST.md as appropriate.",
            )
        )

    if _is_root_path(rel) and suffix in {".bat", ".cmd", ".ps1"}:
        findings.append(
            Finding(
                rule_id="ARCH006",
                path=rel,
                reason="New or reintroduced root launchers bypass the scripts/ layout.",
                fix="Use scripts/dev, scripts/operator, scripts/release, or scripts/verify-env.* instead.",
            )
        )

    return findings


def findings_for_paths(paths: Iterable[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        findings.extend(findings_for_path(path))
    return findings


def render_findings(findings: Iterable[Finding]) -> str:
    lines = [
        "Architecture guardrails found violation(s):",
        "Fix the flagged path or design. Do not weaken this guard unless the architecture policy changed and matching tests/docs are updated.",
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
    args = parser.parse_args(argv)

    try:
        candidates = collect_candidates(args)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: unable to collect architecture guardrail candidates: {exc}", file=sys.stderr)
        return 2

    findings = findings_for_paths(candidate.path for candidate in candidates)
    if findings:
        print(render_findings(findings), file=sys.stderr)
        return 1

    print(f"Architecture guardrails passed. Checked {len(candidates)} creation candidate(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
