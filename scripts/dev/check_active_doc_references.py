"""Check active Markdown references for stale moved-doc and legacy-shell names."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

MOVED_DOCS = {
    "Docs/API_ROUTE_INVENTORY.md": "Docs/inventories/API_ROUTE_INVENTORY.md",
    "Docs/COMMAND_OWNERSHIP_MATRIX.md": "Docs/inventories/COMMAND_OWNERSHIP_MATRIX.md",
    "Docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md": "Docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md",
    "Docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md": "Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md",
    "Docs/FAILURE_TRIAGE_WORKSHEET.md": "Docs/operator/FAILURE_TRIAGE_WORKSHEET.md",
    "Docs/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md": "Docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md",
    "Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md": "Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md",
    "Docs/LOG_ARTIFACT_CATALOG.md": "Docs/inventories/LOG_ARTIFACT_CATALOG.md",
    "Docs/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md": "Docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md",
    "Docs/NETWORK_UX_IMPROVEMENTS.md": "Docs/ARCHIVED_MD_INDEX.md",
    "Docs/NO_TOUCH_BOUNDARY_REGISTER.md": "Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md",
    "Docs/OPERATOR_GLOSSARY.md": "Docs/operator/OPERATOR_GLOSSARY.md",
    "Docs/POWERSHELL_HOST_EXPECTATIONS.md": "Docs/operator/POWERSHELL_HOST_EXPECTATIONS.md",
    "Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md": "Docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md",
    "Docs/RUNTIME_ARTIFACT_INVENTORY.md": "Docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md",
    "Docs/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md": "Docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md",
    "Docs/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md": "Docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md",
    "Docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md": "Docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md",
    "Docs/SETTINGS_KEY_OWNERSHIP_MAP.md": "Docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md",
    "Docs/SETTINGS_RAW_KEY_TRIAGE.md": "Docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md",
    "Docs/SMOKE_TEST_INVENTORY.md": "Docs/inventories/SMOKE_TEST_INVENTORY.md",
    "Docs/STATE_FILE_SCHEMA_REFERENCE.md": "Docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md",
    "Docs/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md": "Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md",
    "Docs/TAURI_WEBVIEW_PARITY_MATRIX.md": "Docs/archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/Docs/architecture/TAURI_WEBVIEW_PARITY_MATRIX.md",
    "Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md": "Docs/operator/TERMINOLOGY_CONSISTENCY_GUIDE.md",
    "Docs/TEST_COVERAGE_MATRIX.md": "Docs/testing/TEST_COVERAGE_MATRIX.md",
    "Docs/UI_IMPROVEMENT_CHECKLIST.md": "Docs/ARCHIVED_MD_INDEX.md",
    "Docs/V5_MIGRATION_RISK_REGISTER.md": "Docs/architecture/V5_MIGRATION_RISK_REGISTER.md",
    "Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md": "Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md",
    "Docs/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md": "Docs/sample-validation/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md",
    "Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md": "Docs/ARCHIVED_MD_INDEX.md",
    "Docs/V5_TRANSITION_STATUS_BOARD.md": "Docs/ARCHIVED_MD_INDEX.md",
    "Docs/VALIDATION_LADDER_RUNBOOK.md": "Docs/testing/VALIDATION_LADDER_RUNBOOK.md",
    "Docs/WEBVIEW_DOM_ID_INVENTORY.md": "Docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md",
    "Docs/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md": "Docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md",
    "Docs/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md": "Docs/operator/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md",
    "Docs/WEBVIEW_SMOKE_RESULT_TEMPLATE.md": "Docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md",
    "Docs/WEBVIEW_SMOKE_TEST_CATALOG.md": "Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
    "Docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md": "Docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md",
    "Docs/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md": "Docs/testing/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md",
    "Docs/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md": "Docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md",
    "Docs/BROWSER_SMOKE_TEST_RUNBOOK.md": "Docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md",
    "Docs/COMMAND_HISTORY_CONSISTENCY_AUDIT.md": "Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/COMMAND_HISTORY_CONSISTENCY_AUDIT.md",
    "Docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md": "Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md",
    "Docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md": "Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/FRONTEND_MODULE_SIZE_COHESION_REPORT.md",
    "Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md": "Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md",
    "Docs/RELEASE_PACKAGE_ADMIN_INVENTORY.md": "Docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md",
    "Docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md": "Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md",
    "Docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md": "Docs/operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md",
    "Docs/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md": "Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md",
    "Docs/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md": "Docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/Docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md",
    "Docs/proposals/GOD_FILE_SPLIT_WAVE6_PLAN.md": "Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-checklists/GOD_FILE_SPLIT_WAVE6_PLAN.md",
}

ARCHIVED_HOUSEKEEPING_DOCS = ("HOUSEKEEPING_AUDIT_REPORT.md", "HOUSEKEEPING_EXECUTION_CHECKLIST.md")
REQUIRED_ACTIVE_DOCS = (
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "Docs/architecture/ARCHITECTURE.md",
    "Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md",
    "Docs/CURRENT_PROJECT_STATE.md",
    "OPEN_WORK_CHECKLIST.md",
)
HANDOFF_PATH_RESTRICTED_RELATIVES = {
    "Docs/CURRENT_PROJECT_STATE.md",
    "Docs/ACTIVE_FIX_CHECKLIST.md",
    "Docs/active-plans/V5_TRANSITION_STATUS_BOARD.md",
    "Docs/architecture/DEPLOYABILITY_CHECKLIST.md",
    "V5_TRANSITION_REVIEW_FIX_CHECKLIST.md",
}
REMOVED_SHELL_SCAN_EXCLUSIONS = {
    "Docs/DOC_TOUCH_LOG.md",
    "CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md",
    "DOCS_HOUSEKEEPING_AUDIT.md",
    "DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md",
    "DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md",
}
REMOVED_SHELL_PATTERN = re.compile(
    r"CustomTkinter|customtkinter|tkinter|\bTk\b|Tk-owned|Tk fallback|"
    r"Tk replacement|replace Tk|Tk as|Tk app|Tk shell|Tk main",
    re.IGNORECASE,
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
    return "/Docs/archive/" in f"/{normalize_path(rel)}"


def collect_active_markdown_files(root: Path = REPO_ROOT) -> list[Path]:
    files: list[Path] = []
    docs = root / "Docs"
    if docs.exists():
        for path in docs.rglob("*.md"):
            rel = normalize_path(path.relative_to(root))
            if _is_archive_path(rel) or rel == "Docs/REMEDIATION_CHANGELOG.md":
                continue
            files.append(path)
    tauri = root / "DesktopApp" / "tauri_shell"
    if tauri.exists():
        files.extend(path for path in tauri.iterdir() if path.is_file() and (path.suffix == ".md" or path.name.startswith("README")))
    files.extend(path for path in root.iterdir() if path.is_file() and (path.suffix == ".md" or path.name.startswith("README")))
    return sorted(set(files))


def missing_moved_doc_targets(root: Path = REPO_ROOT, moved_docs: dict[str, str] = MOVED_DOCS) -> list[str]:
    missing: list[str] = []
    for target in moved_docs.values():
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
            if rel == "Docs/ARCHIVED_MD_INDEX.md":
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

        if rel not in REMOVED_SHELL_SCAN_EXCLUSIONS and REMOVED_SHELL_PATTERN.search(line):
            findings.append(DocFinding("DOC004", rel, line_no, "removed legacy desktop-shell wording"))

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
