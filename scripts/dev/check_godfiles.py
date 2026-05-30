"""Warn when source files become too large to refactor safely."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "Docs" / "inventories" / "GOD_FILE_GUARDRAIL.v1.json"
SCHEMA_VERSION = "god_file_guardrail.v1"


@dataclass(frozen=True)
class CandidatePath:
    path: str
    status: str = "PATH"
    is_new: bool = False


@dataclass(frozen=True)
class Thresholds:
    warn_lines: int
    max_lines: int
    new_file_max_lines: int
    growth_warn_lines: int
    source: str
    allowlisted: bool = False
    allowlist_reason: str = ""
    feature: str = ""


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    path: str
    line_count: int
    limit: int
    message: str
    previous_line_count: int | None = None
    policy_source: str = ""
    reason: str = ""


@dataclass(frozen=True)
class PolicyFinding:
    rule_id: str
    path: str
    message: str


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and value > 0


def validate_policy(policy: dict[str, Any]) -> list[PolicyFinding]:
    findings: list[PolicyFinding] = []
    if policy.get("schema_version") != SCHEMA_VERSION:
        findings.append(PolicyFinding("GFP001", str(POLICY_PATH), f"schema_version must be {SCHEMA_VERSION}"))

    defaults = policy.get("defaults")
    if not isinstance(defaults, dict):
        findings.append(PolicyFinding("GFP002", "defaults", "defaults must be an object"))
        return findings

    for key in ("include_globs", "exclude_globs"):
        if not _string_list(defaults.get(key)):
            findings.append(PolicyFinding("GFP003", f"defaults.{key}", f"{key} must be a string list"))
    for key in ("warn_lines", "max_lines", "new_file_max_lines", "growth_warn_lines", "report_limit"):
        if not _positive_int(defaults.get(key)):
            findings.append(PolicyFinding("GFP004", f"defaults.{key}", f"{key} must be a positive integer"))

    for section in ("patterns", "allowlist"):
        entries = policy.get(section, [])
        if not isinstance(entries, list):
            findings.append(PolicyFinding("GFP005", section, f"{section} must be a list"))
            continue
        seen_ids: set[str] = set()
        for index, entry in enumerate(entries):
            entry_path = f"{section}[{index}]"
            if not isinstance(entry, dict):
                findings.append(PolicyFinding("GFP006", entry_path, "entry must be an object"))
                continue
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not entry_id.strip():
                findings.append(PolicyFinding("GFP007", entry_path, "entry id must be a non-empty string"))
            elif entry_id in seen_ids:
                findings.append(PolicyFinding("GFP008", entry_path, f"duplicate entry id: {entry_id}"))
            else:
                seen_ids.add(entry_id)
            if not _string_list(entry.get("path_globs")):
                findings.append(PolicyFinding("GFP009", entry_path, "path_globs must be a non-empty string list"))
            for key in ("warn_lines", "max_lines", "new_file_max_lines", "growth_warn_lines"):
                if key in entry and not _positive_int(entry.get(key)):
                    findings.append(PolicyFinding("GFP010", f"{entry_path}.{key}", f"{key} must be a positive integer"))
            if section == "allowlist" and not isinstance(entry.get("reason"), str):
                findings.append(PolicyFinding("GFP011", entry_path, "allowlist entries require a reason"))

    return findings


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    rel = normalize_path(path)
    return any(fnmatchcase(rel, normalize_path(pattern)) for pattern in patterns)


def is_included(path: str, policy: dict[str, Any]) -> bool:
    defaults = policy.get("defaults", {})
    include_globs = defaults.get("include_globs", [])
    exclude_globs = defaults.get("exclude_globs", [])
    return _matches_any(path, include_globs) and not _matches_any(path, exclude_globs)


def thresholds_for_path(path: str, policy: dict[str, Any]) -> Thresholds:
    defaults = policy["defaults"]
    data: dict[str, object] = {
        "warn_lines": defaults["warn_lines"],
        "max_lines": defaults["max_lines"],
        "new_file_max_lines": defaults["new_file_max_lines"],
        "growth_warn_lines": defaults["growth_warn_lines"],
        "source": "defaults",
        "allowlisted": False,
        "allowlist_reason": "",
        "feature": "",
    }

    for entry in policy.get("patterns", []):
        if isinstance(entry, dict) and _matches_any(path, entry.get("path_globs", [])):
            for key in ("warn_lines", "max_lines", "new_file_max_lines", "growth_warn_lines"):
                if key in entry:
                    data[key] = entry[key]
            data["source"] = str(entry.get("id", "patterns"))

    for entry in policy.get("allowlist", []):
        if isinstance(entry, dict) and _matches_any(path, entry.get("path_globs", [])):
            for key in ("warn_lines", "max_lines", "new_file_max_lines", "growth_warn_lines"):
                if key in entry:
                    data[key] = entry[key]
            data["source"] = str(entry.get("id", "allowlist"))
            data["allowlisted"] = True
            data["allowlist_reason"] = str(entry.get("reason", ""))
            data["feature"] = str(entry.get("feature", ""))

    return Thresholds(
        warn_lines=int(data["warn_lines"]),
        max_lines=int(data["max_lines"]),
        new_file_max_lines=int(data["new_file_max_lines"]),
        growth_warn_lines=int(data["growth_warn_lines"]),
        source=str(data["source"]),
        allowlisted=bool(data["allowlisted"]),
        allowlist_reason=str(data["allowlist_reason"]),
        feature=str(data["feature"]),
    )


def line_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text:
        return 0
    return len(text.splitlines())


def previous_head_line_count(path: str) -> int | None:
    rel = normalize_path(path)
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            cwd=REPO_ROOT,
            check=True,
            encoding="utf-8",
            errors="ignore",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    if not result.stdout:
        return 0
    return len(result.stdout.splitlines())


def analyze_candidate(
    candidate: CandidatePath,
    policy: dict[str, Any],
    *,
    root: Path = REPO_ROOT,
    strict: bool = False,
    enforce_new: bool = False,
    previous_lines: int | None = None,
) -> list[Finding]:
    rel = normalize_path(candidate.path)
    if not is_included(rel, policy):
        return []
    full_path = root / rel
    if not full_path.is_file():
        return []

    thresholds = thresholds_for_path(rel, policy)
    current_lines = line_count(full_path)
    findings: list[Finding] = []
    new_limit = thresholds.new_file_max_lines

    if candidate.is_new and current_lines > new_limit and not thresholds.allowlisted:
        severity = "error" if enforce_new else "warning"
        findings.append(
            Finding(
                rule_id="GOD003",
                severity=severity,
                path=rel,
                line_count=current_lines,
                limit=new_limit,
                message="New source file exceeds the new-file size limit; split it or add a documented allowlist entry.",
                policy_source=thresholds.source,
            )
        )
    elif current_lines > thresholds.max_lines:
        severity = "error" if strict and not thresholds.allowlisted else "warning"
        findings.append(
            Finding(
                rule_id="GOD002",
                severity=severity,
                path=rel,
                line_count=current_lines,
                limit=thresholds.max_lines,
                message="Source file exceeds the god-file maximum for its policy group.",
                policy_source=thresholds.source,
                reason=thresholds.allowlist_reason,
            )
        )
    elif current_lines > thresholds.warn_lines:
        findings.append(
            Finding(
                rule_id="GOD001",
                severity="warning",
                path=rel,
                line_count=current_lines,
                limit=thresholds.warn_lines,
                message="Source file is above the warning threshold; consider extracting the next cohesive slice.",
                policy_source=thresholds.source,
                reason=thresholds.allowlist_reason,
            )
        )

    previous = previous_lines
    if previous is None and not candidate.is_new:
        previous = previous_head_line_count(rel)
    if previous is not None:
        growth = current_lines - previous
        should_watch_growth = current_lines > thresholds.warn_lines or thresholds.allowlisted
        if growth >= thresholds.growth_warn_lines and should_watch_growth:
            findings.append(
                Finding(
                    rule_id="GOD004",
                    severity="warning",
                    path=rel,
                    line_count=current_lines,
                    limit=thresholds.growth_warn_lines,
                    message="Touched source file grew substantially; prefer extracting or splitting before adding more behavior.",
                    previous_line_count=previous,
                    policy_source=thresholds.source,
                    reason=thresholds.allowlist_reason,
                )
            )

    return findings


def analyze_candidates(
    candidates: Iterable[CandidatePath],
    policy: dict[str, Any],
    *,
    root: Path = REPO_ROOT,
    strict: bool = False,
    enforce_new: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for candidate in candidates:
        rel = normalize_path(candidate.path)
        if rel in seen:
            continue
        seen.add(rel)
        findings.extend(analyze_candidate(candidate, policy, root=root, strict=strict, enforce_new=enforce_new))
    return findings


def parse_porcelain_status_line(line: str) -> CandidatePath | None:
    if not line.strip() or len(line) < 4:
        return None
    status = line[:2]
    payload = line[3:].strip()
    if " -> " in payload:
        _source, payload = payload.split(" -> ", 1)
    path = normalize_path(payload)
    is_new = "?" in status or any(marker in status for marker in ("A", "R", "C"))
    return CandidatePath(path=path, status=status, is_new=is_new)


def changed_candidates_from_status(text: str) -> list[CandidatePath]:
    candidates: list[CandidatePath] = []
    for line in text.splitlines():
        candidate = parse_porcelain_status_line(line)
        if candidate:
            candidates.append(candidate)
    return candidates


def staged_candidates_from_name_status(text: str) -> list[CandidatePath]:
    candidates: list[CandidatePath] = []
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0]
        path = fields[-1]
        is_new = status.startswith(("A", "C", "R"))
        candidates.append(CandidatePath(path=normalize_path(path), status=status, is_new=is_new))
    return candidates


def git_changed_candidates() -> list[CandidatePath]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return changed_candidates_from_status(result.stdout)


def git_staged_candidates() -> list[CandidatePath]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=ACMR"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return staged_candidates_from_name_status(result.stdout)


def git_all_candidates() -> list[CandidatePath]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [CandidatePath(path=normalize_path(line), status="ALL") for line in result.stdout.splitlines() if line.strip()]


def collect_candidates(args: argparse.Namespace) -> list[CandidatePath]:
    if args.paths:
        return [CandidatePath(path=normalize_path(path), is_new=args.new) for path in args.paths]
    if args.all:
        return git_all_candidates()
    if args.staged:
        return git_staged_candidates()
    return git_changed_candidates()


def render_policy_findings(findings: Iterable[PolicyFinding]) -> str:
    lines = ["God-file guard policy validation failed:"]
    for finding in findings:
        lines.append(f"- {finding.rule_id}: {finding.path}: {finding.message}")
    return "\n".join(lines)


def render_findings(findings: list[Finding], *, checked_count: int, report_limit: int) -> str:
    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]
    if not findings:
        return f"God-file guard passed. Checked {checked_count} candidate path(s)."

    lines = [
        f"God-file guard found {len(errors)} error(s) and {len(warnings)} warning(s) across {checked_count} candidate path(s)."
    ]
    ordered = sorted(findings, key=lambda item: (item.severity != "error", item.path, item.rule_id))
    for finding in ordered[:report_limit]:
        lines.append(
            f"- {finding.severity.upper()} {finding.rule_id}: {finding.path} has {finding.line_count} lines "
            f"(limit {finding.limit}; policy {finding.policy_source})"
        )
        lines.append(f"  {finding.message}")
        if finding.previous_line_count is not None:
            delta = finding.line_count - finding.previous_line_count
            lines.append(f"  Previous HEAD line count: {finding.previous_line_count}; delta: {delta}.")
        if finding.reason:
            lines.append(f"  Allowlist reason: {finding.reason}")
    if len(findings) > report_limit:
        lines.append(f"... {len(findings) - report_limit} additional finding(s) omitted by report_limit.")
    return "\n".join(lines)


def _json_payload(findings: list[Finding], policy_findings: list[PolicyFinding]) -> str:
    return json.dumps(
        {
            "ok": not policy_findings and not any(finding.severity == "error" for finding in findings),
            "findings": [finding.__dict__ for finding in findings],
            "policy_findings": [finding.__dict__ for finding in policy_findings],
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Check all tracked and untracked source candidates.")
    parser.add_argument("--staged", action="store_true", help="Check staged added/copied/renamed/modified paths.")
    parser.add_argument("--paths", nargs="*", default=[], help="Check explicit repo-relative paths.")
    parser.add_argument("--new", action="store_true", help="Treat explicit --paths as new files.")
    parser.add_argument("--strict", action="store_true", help="Fail on non-allowlisted max-line violations.")
    parser.add_argument("--enforce-new", action="store_true", help="Fail when a new non-allowlisted file exceeds its new-file limit.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    try:
        policy = load_policy()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: unable to load god-file policy: {exc}", file=sys.stderr)
        return 2

    policy_findings = validate_policy(policy)
    if policy_findings:
        if args.json:
            print(_json_payload([], policy_findings))
        else:
            print(render_policy_findings(policy_findings), file=sys.stderr)
        return 2

    try:
        candidates = collect_candidates(args)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: unable to collect god-file candidates: {exc}", file=sys.stderr)
        return 2

    findings = analyze_candidates(candidates, policy, strict=args.strict, enforce_new=args.enforce_new)
    if args.json:
        print(_json_payload(findings, []))
    else:
        report_limit = int(policy["defaults"].get("report_limit", 30))
        output = render_findings(findings, checked_count=len(candidates), report_limit=report_limit)
        print(output, file=sys.stderr if any(finding.severity == "error" for finding in findings) else sys.stdout)
    return 1 if any(finding.severity == "error" for finding in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
