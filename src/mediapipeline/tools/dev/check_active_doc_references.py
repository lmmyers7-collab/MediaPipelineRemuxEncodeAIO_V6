"""Check active Markdown references for stale moved-doc and legacy-shell names."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root, PurePosixPath
from collections.abc import Iterable


REPO_ROOT = find_repo_root(Path(__file__))

MOVED_DOCS = {
    "docs/API_ROUTE_INVENTORY.md": "docs/inventories/API_ROUTE_INVENTORY.md",
    "docs/COMMAND_OWNERSHIP_MATRIX.md": "docs/inventories/COMMAND_OWNERSHIP_MATRIX.md",
    "docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md": "docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md",
    "docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md": "docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md",
    "docs/FAILURE_TRIAGE_WORKSHEET.md": "docs/operator/FAILURE_TRIAGE_WORKSHEET.md",
    "docs/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md": "docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md",
    "docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md": "docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md",
    "docs/LOG_ARTIFACT_CATALOG.md": "docs/inventories/LOG_ARTIFACT_CATALOG.md",
    "docs/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md": "docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md",
    "docs/NETWORK_UX_IMPROVEMENTS.md": "docs/ARCHIVED_MD_INDEX.md",
    "docs/NO_TOUCH_BOUNDARY_REGISTER.md": "docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",
    "docs/OPERATOR_GLOSSARY.md": "docs/operator/OPERATOR_GLOSSARY.md",
    "docs/POWERSHELL_HOST_EXPECTATIONS.md": "docs/operator/POWERSHELL_HOST_EXPECTATIONS.md",
    "docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md": "docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md",
    "docs/RUNTIME_ARTIFACT_INVENTORY.md": "docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md",
    "docs/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md": "docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md",
    "docs/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md": "docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md",
    "docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md": "docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md",
    "docs/SETTINGS_KEY_OWNERSHIP_MAP.md": "docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md",
    "docs/SETTINGS_RAW_KEY_TRIAGE.md": "docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md",
    "docs/SMOKE_TEST_INVENTORY.md": "docs/inventories/SMOKE_TEST_INVENTORY.md",
    "docs/STATE_FILE_SCHEMA_REFERENCE.md": "docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md",
    "docs/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md": "docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md",
    "docs/TAURI_WEBVIEW_PARITY_MATRIX.md": "docs/archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/docs/architecture/TAURI_WEBVIEW_PARITY_MATRIX.md",
    "docs/TERMINOLOGY_CONSISTENCY_GUIDE.md": "docs/operator/TERMINOLOGY_CONSISTENCY_GUIDE.md",
    "docs/TEST_COVERAGE_MATRIX.md": "docs/testing/TEST_COVERAGE_MATRIX.md",
    "docs/UI_IMPROVEMENT_CHECKLIST.md": "docs/ARCHIVED_MD_INDEX.md",
    "docs/" + "V" + "5_TAURI_TRANSITION_CURRENT_PLAN.md": "docs/ARCHIVED_MD_INDEX.md",
    "docs/" + "V" + "5_TRANSITION_STATUS_BOARD.md": "docs/ARCHIVED_MD_INDEX.md",
    "docs/VALIDATION_LADDER_RUNBOOK.md": "docs/testing/VALIDATION_LADDER_RUNBOOK.md",
    "docs/WEBVIEW_DOM_ID_INVENTORY.md": "docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md",
    "docs/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md": "docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md",
    "docs/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md": "docs/operator/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md",
    "docs/WEBVIEW_SMOKE_RESULT_TEMPLATE.md": "docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md",
    "docs/WEBVIEW_SMOKE_TEST_CATALOG.md": "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
    "docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md": "docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md",
    "docs/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md": "docs/testing/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md",
    "docs/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md": "docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md",
    "docs/BROWSER_SMOKE_TEST_RUNBOOK.md": "docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md",
    "docs/COMMAND_HISTORY_CONSISTENCY_AUDIT.md": "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/COMMAND_HISTORY_CONSISTENCY_AUDIT.md",
    "docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md": "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md",
    "docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md": "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/FRONTEND_MODULE_SIZE_COHESION_REPORT.md",
    "docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md": "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md",
    "docs/RELEASE_PACKAGE_ADMIN_INVENTORY.md": "docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md",
    "docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md": "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md",
    "docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md": "docs/operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md",
    "docs/" + "V" + "5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md": "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/" + "V" + "5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md",
    "docs/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md": "docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md",
    "docs/proposals/GOD_FILE_SPLIT_WAVE6_PLAN.md": "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-checklists/GOD_FILE_SPLIT_WAVE6_PLAN.md",
}

ARCHIVED_HOUSEKEEPING_DOCS = ("HOUSEKEEPING_AUDIT_REPORT.md", "HOUSEKEEPING_EXECUTION_CHECKLIST.md")
REQUIRED_ACTIVE_DOCS = (
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/CURRENT_PROJECT_STATE.md",
    "docs/OPEN_WORK_CHECKLIST.md",
)
HANDOFF_PATH_RESTRICTED_RELATIVES = {
    "docs/CURRENT_PROJECT_STATE.md",
    "docs/ACTIVE_FIX_CHECKLIST.md",
    "docs/active-plans/" + "V" + "5_TRANSITION_STATUS_BOARD.md",
    "docs/architecture/DEPLOYABILITY_CHECKLIST.md",
    "V" + "5_TRANSITION_REVIEW_FIX_CHECKLIST.md",
}
REMOVED_SHELL_SCAN_EXCLUSIONS = {
    "docs/DOC_TOUCH_LOG.md",
    "CODE_REVIEW_WEBVIEW_TAURI_AUDIT.md",
    "DOCS_HOUSEKEEPING_AUDIT.md",
    "DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md",
    "DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md",
}
VERSION_LABEL_SCAN_EXCLUSIONS = {
    "CHANGELOG.md",
    "docs/ARCHIVED_MD_INDEX.md",
    "docs/change_control/CHANGELOG.md",
    "docs/change_control/CHANGE_INDEX.md",
    "docs/change_control/RELEASE_HISTORY.md",
}
HISTORICAL_NAVIGATION_DOCS = {
    "docs/REMEDIATION_CHANGELOG.md",
}
HISTORICAL_REFERENCE_EXCLUSIONS = HISTORICAL_NAVIGATION_DOCS | {
    "docs/change_control/CHANGELOG.md",
    "docs/change_control/CHANGE_INDEX.md",
    "docs/change_control/RELEASE_HISTORY.md",
}
REMOVED_SHELL_PATTERN = re.compile(
    r"CustomTkinter|customtkinter|tkinter|\bTk\b|Tk-owned|Tk fallback|"
    r"Tk replacement|replace Tk|Tk as|Tk app|Tk shell|Tk main",
    re.IGNORECASE,
)
REMOVED_QUICK_START_NAME = "T" + "LDR"
REMOVED_QUICK_START_PATTERN = re.compile(
    rf"(?:docs[\\/])?{REMOVED_QUICK_START_NAME}\.md",
    re.IGNORECASE,
)
VERSION_LINE_LABEL_PATTERN = re.compile(
    r"\bV[0-9]+(?:\.[0-9]+(?:\.[0-9]+)?)?\b|"
    r"\bv[0-9]+\.\d{3}\b|"
    r"MediaPipelineRemuxEncodeAIO[_ -]?V[0-9]+\b|"
    r"_V[0-9]+\b"
)


@dataclass(frozen=True)
class DocFinding:
    rule_id: str
    path: str
    line: int
    detail: str


def normalize_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip("/")


def _is_archive_path(rel: str) -> bool:
    return "/docs/archive/" in f"/{normalize_path(rel)}"


def _allows_historical_references(rel: str) -> bool:
    rel = normalize_path(rel)
    return _is_archive_path(rel) or rel in HISTORICAL_REFERENCE_EXCLUSIONS


def collect_active_markdown_files(root: Path = REPO_ROOT) -> list[Path]:
    files: list[Path] = []
    docs = root / "docs"
    if docs.exists():
        for path in docs.rglob("*.md"):
            rel = normalize_path(path.relative_to(root))
            if (
                _is_archive_path(rel)
                # The compact index intentionally repeats legacy headings; the
                # detailed payload is covered by the docs/archive exclusion.
                or rel in HISTORICAL_NAVIGATION_DOCS
                or rel.startswith("docs/generated/summaries/")
            ):
                continue
            files.append(path)
    tauri = root / "apps" / "desktop" / "tauri"
    if tauri.exists():
        files.extend(path for path in tauri.iterdir() if path.is_file() and (path.suffix == ".md" or path.name.startswith("README")))
    files.extend(path for path in root.iterdir() if path.is_file() and (path.suffix == ".md" or path.name.startswith("README")))
    return sorted(set(files))


def missing_moved_doc_targets(root: Path = REPO_ROOT, moved_docs: dict[str, str] = MOVED_DOCS) -> list[str]:
    missing: list[str] = []
    for target in moved_docs.values():
        if _is_archive_path(target):
            continue
        if not (root / PurePosixPath(target)).is_file():
            missing.append(target)
    return missing


def missing_required_active_docs(root: Path = REPO_ROOT, required_docs: Iterable[str] = REQUIRED_ACTIVE_DOCS) -> list[str]:
    return [doc for doc in required_docs if not (root / PurePosixPath(doc)).is_file()]


def findings_for_text(
    text: str,
    relative_path: str,
    *,
    moved_docs: dict[str, str] = MOVED_DOCS,
) -> list[DocFinding]:
    rel = normalize_path(relative_path)
    findings: list[DocFinding] = []
    for old in moved_docs:
        variants = {old, old.replace("/", "\\")}
        for variant in variants:
            if variant in text:
                findings.append(DocFinding("DOC001", rel, 0, f"stale moved-doc reference: {variant}"))

    for line_no, line in enumerate(text.splitlines(), start=1):
        for doc_name in ARCHIVED_HOUSEKEEPING_DOCS:
            if rel == "docs/ARCHIVED_MD_INDEX.md":
                continue
            allowed = re.search(
                rf"(((Docs[\\/])?archive[\\/]admin-audits[\\/])|"
                rf"(delete-candidates[\\/]Docs[\\/]archive[\\/]admin-audits[\\/])){re.escape(doc_name)}",
                line,
            )
            if doc_name in line and not allowed:
                findings.append(DocFinding("DOC002", rel, line_no, f"root housekeeping doc name: {doc_name}"))

        if rel in HANDOFF_PATH_RESTRICTED_RELATIVES and re.search(r"C:\\Users\\lmmye\\.*CurrentHandoff", line):
            findings.append(DocFinding("DOC003", rel, line_no, "absolute current-handoff path"))

        if not _allows_historical_references(rel) and REMOVED_QUICK_START_PATTERN.search(line):
            findings.append(DocFinding("DOC006", rel, line_no, "removed active quick-start reference"))

        if rel not in REMOVED_SHELL_SCAN_EXCLUSIONS and REMOVED_SHELL_PATTERN.search(line):
            findings.append(DocFinding("DOC004", rel, line_no, "removed legacy desktop-shell wording"))

        if rel not in VERSION_LABEL_SCAN_EXCLUSIONS and VERSION_LINE_LABEL_PATTERN.search(line):
            findings.append(DocFinding("DOC005", rel, line_no, "active V-line product/release label"))

    return findings


def findings_for_files(files: Iterable[Path], root: Path = REPO_ROOT) -> list[DocFinding]:
    findings: list[DocFinding] = []
    for path in files:
        rel = normalize_path(path.relative_to(root))
        text = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(findings_for_text(text, rel))
    return findings


def render_findings(findings: Iterable[DocFinding], missing_targets: Iterable[str]) -> str:
    lines = ["Active doc reference check found violation(s):"]
    for target in missing_targets:
        lines.append(f"- DOC000: missing mapped target: {target}")
    for finding in findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        lines.append(f"- {finding.rule_id}: {location}: {finding.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to scan.")
    args = parser.parse_args(argv)

    missing = missing_moved_doc_targets(args.root)
    missing.extend(f"required active doc: {doc}" for doc in missing_required_active_docs(args.root))
    findings = findings_for_files(collect_active_markdown_files(args.root), args.root)
    if missing or findings:
        print(render_findings(findings, missing), file=sys.stderr)
        return 1

    print("Active doc reference checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
