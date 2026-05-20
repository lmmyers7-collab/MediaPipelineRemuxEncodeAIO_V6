# Docs Folder Sorting Proposal

Date: 2026-05-14

Proposes a cleaner taxonomy for the `Docs/` folder. No files are moved. This is a structural suggestion for future organization; all files remain at their current paths.

---

## Current State

The `Docs/` folder contains approximately 90+ Markdown files at the root (plus `DesktopApp/docs/`, `Pipeline/`, and `RealMediaValidationRuns/` subfolders). Files span operator runbooks, engineering audits, architecture decisions, test inventories, migration plans, completed archives, and delegation backlogs — all at the same level with no visual grouping.

---

## Proposed Taxonomy (No Moves Required)

The following groupings reflect what already exists. Moving files is not recommended — it would break all existing cross-references. Instead, these groupings should be reflected in `DOCS_INDEX.md` section headings.

### Category 1: Operator Quick Start (Stay At Root)

Files that operators need on first deployment. Must remain easily findable:

| File | Reason to keep at root |
|---|---|
| `README_MediaPipelineRemuxEncodeAIO.md` | Bundle overview; primary first-read |
| `TLDR.md` | Daily-use summary; most-accessed file |
| `OPERATOR_GLOSSARY.md` | Terminology reference; linked from all runbooks |
| `VALIDATION_LADDER_RUNBOOK.md` | Ordered validation runbook; required for Rung 0 |
| `COMPLETED_PENDING_FAILURE_PLAYBOOK.md` | Operator recovery playbook |
| `FAILURE_TRIAGE_WORKSHEET.md` | Copyable worksheet for incident capture |
| `WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md` | Manual validation; 13-page walkthrough |
| `PACKAGING_DEPENDENCY_INVENTORY.md` | Setup guide for new machines |
| `RELEASE_PACKAGE_ADMIN_INVENTORY.md` | Release build/test reference |
| `REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` | Copyable evidence template |
| `WEBVIEW_SMOKE_RESULT_TEMPLATE.md` | Copyable smoke result template |
| `BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` | Browser environment checklist |

---

### Category 2: Smoke Testing

Files covering smoke wrappers, mutation guarantees, failure triage, and smoke catalog:

| File |
|---|
| `WEBVIEW_SMOKE_TEST_CATALOG.md` |
| `BROWSER_SMOKE_TEST_RUNBOOK.md` |
| `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` |
| `BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md` |
| `TEST_COVERAGE_MATRIX.md` |

---

### Category 3: Test Suite Inventories

Files mapping tests to subsystems and coverage:

| File |
|---|
| `TEST_SUITE_SUBSYSTEM_INVENTORY.md` |
| `RENAME_SAFETY_TEST_INVENTORY.md` |
| `PENDING_PUBLISH_FIXTURE_INVENTORY.md` |

---

### Category 4: Architecture and API

Core engineering references that rarely change:

| File |
|---|
| `GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md` |
| `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` |
| `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` |
| `API_ROUTE_INVENTORY.md` |
| `COMMAND_OWNERSHIP_MATRIX.md` |
| `STATE_FILE_SCHEMA_REFERENCE.md` |
| `LOG_ARTIFACT_CATALOG.md` |
| `RUNTIME_ARTIFACT_INVENTORY.md` |
| `NO_TOUCH_BOUNDARY_REGISTER.md` |
| `TAURI_BACKEND_LIFECYCLE_BOUNDARY.md` |
| `TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md` |
| `V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md` |
| `FRONTEND_MODULE_SIZE_COHESION_REPORT.md` |

---

### Category 5: Audit and Review

Point-in-time audits and consistency reviews:

| File |
|---|
| `WEBVIEW_DOM_ID_INVENTORY.md` |
| `archive/admin-audits/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md` |
| `WEBVIEW_APIPOST_MUTATION_REVIEW.md` |
| `archive/admin-audits/WEBVIEW_OPERATOR_COPY_AUDIT.md` |
| `WEBVIEW_OPERATOR_ERROR_MESSAGE_REVIEW.md` |
| `DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` |
| `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` |
| `SETTINGS_BUILDER_COVERAGE_MATRIX.md` |
| `SETTINGS_KEY_OWNERSHIP_MAP.md` |
| `COMMAND_HISTORY_CONSISTENCY_AUDIT.md` |
| `NETWORK_READ_ONLY_PARITY_AUDIT.md` |
| `NETWORK_MODE_READ_ONLY_DOCUMENTATION.md` |
| `PACKAGING_MANIFEST_REVIEW.md` |
| `archive/admin-audits/STALE_VERSION_LABEL_AUDIT.md` |
| `archive/admin-audits/STALE_DOCS_TODO_AUDIT.md` |
| `DOCS_DEAD_MARKDOWN_AUDIT.md` |
| `TERMINOLOGY_CONSISTENCY_GUIDE.md` |
| `REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md` |

---

### Category 6: CLN Sprint Audit Docs (2026-05-14)

All documents produced by the CLN cleanup/review/sorting sprint. May warrant a `Docs/CLN_Audits/` subfolder if count continues to grow:

| File | Task |
|---|---|
| `archive/old-ai-directives/CLAUDE_HANDOFF_STATUS_RECONCILIATION.md` | CLN-001 |
| `ROOT_SCRIPT_INVENTORY.md` | CLN-006 |
| `RELEASE_SELF_TEST_LAYOUT_AUDIT.md` | CLN-009 |
| `archive/admin-audits/LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md` | CLN-010 |
| `archive/admin-audits/SCHEDULE_STALE_READONLY_WORDING_AUDIT.md` | CLN-003 |
| `archive/admin-audits/COMMAND_HISTORY_OWNER_COVERAGE_AUDIT.md` | CLN-013 |
| `SETTINGS_RAW_KEY_TRIAGE.md` | CLN-015 |
| `archive/admin-audits/TAURI_DAILY_DRIVER_WORDING_AUDIT.md` | CLN-019 |
| `archive/admin-audits/POWERSHELL_HOST_WORDING_AUDIT.md` | CLN-021 |
| `BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md` | CLN-025 |
| `archive/admin-audits/OPERATOR_COPY_CONSISTENCY_REVIEW.md` | CLN-026 |
| `archive/admin-audits/RENAME_DOCS_FRESHNESS_REVIEW.md` | CLN-016 |
| `archive/admin-audits/PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md` | CLN-017 |
| `archive/admin-audits/NETWORK_READONLY_WORDING_AUDIT.md` | CLN-018 |
| `CHANGELOG_NAVIGATION_HEALTH_REVIEW.md` | CLN-028 |
| `archive/admin-audits/BROWSER_SMOKE_CATALOG_SORT_FINDINGS.md` | CLN-005 |
| `archive/admin-audits/DIAGNOSTICS_TARGET_SYNC_AUDIT.md` | CLN-014 |
| `archive/admin-audits/RUNTIME_ARTIFACT_SORTING_NOTES.md` | CLN-022 |
| `archive/admin-audits/GENERATED_VENDOR_EXCLUSION_REVIEW.md` | CLN-023 |

---

### Category 7: Migration and Transition

V5 transition planning and risk tracking:

| File |
|---|
| `V5_TAURI_TRANSITION_CURRENT_PLAN.md` |
| `V5_TRANSITION_STATUS_BOARD.md` |
| `V5_MIGRATION_RISK_REGISTER.md` |
| `V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md` |
| `archive/completed-checklists/V5_HOUSEKEEPING_BEFORE_TRANSITION_RESUME.md` |
| `TAURI_WEBVIEW_PARITY_MATRIX.md` |

---

### Category 8: Active Checklists and Plans

Non-archive checklists that track remaining work:

| File | Status |
|---|---|
| `DEPLOYABILITY_CHECKLIST.md` | Active — release readiness tracking |
| `UI_IMPROVEMENT_CHECKLIST.md` | Active — future UI ideas |
| `NETWORK_UX_IMPROVEMENTS.md` | Active — planned but not implemented |
| `CHANGELOG_NAVIGATION_PROPOSAL.md` | Active proposal; not yet implemented |

---

### Category 9: Completed Archives

Finished work whose content no longer drives new changes:

| File | Status |
|---|---|
| `archive/completed-checklists/CODE_CLEANUP_CHECKLIST.md` | Completed 2026-05-06 |
| `archive/completed-checklists/CONTROL_SURFACE_HARDENING_CHECKLIST.md` | Completed |
| `archive/completed-checklists/NETWORK_MODE_CHECKLIST.md` | Completed |
| `archive/completed-checklists/UI_CHECKLIST.md`, `archive/completed-checklists/UI_CHECKLIST_2.md`, `archive/completed-checklists/UI_CHECKLIST_3.md` | Completed |
| `REMEDIATION_CHANGELOG.md` | Living archive; large |
| `archive/historical-reviews/V4_MIGRATION_NOTES.md` | Historical |

---

### Category 10: Handoff and Delegation

Claude/Codex task backlogs and reconciliation:

| File |
|---|
| `archive/old-ai-directives/CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md` |
| `archive/old-ai-directives/CLAUDE_HANDOFF_20_TASK_BACKLOG.md` |
| `archive/old-ai-directives/CLAUDE_HANDOFF_CLEANUP_REVIEW_SORTING_BACKLOG.md` |
| `archive/old-ai-directives/CLAUDE_HANDOFF_STATUS_RECONCILIATION.md` |
| `archive/old-ai-directives/CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md` |

---

## Files That Should Stay At Root For Discoverability

The following files must remain at `Docs/` root and be linked from `DOCS_INDEX.md` directly. They should not be moved to subdirectories even if subdirectories are created:

- `README_MediaPipelineRemuxEncodeAIO.md`
- `TLDR.md`
- `OPERATOR_GLOSSARY.md`
- `DOCS_INDEX.md` (the index itself)
- Any operator runbook referenced by release self-test or onboarding

---

## Recommendation

Do not move any files. Instead:

1. Update `DOCS_INDEX.md` section headings to reflect these 10 categories
2. Consider creating a `Docs/CLN_Audits/` subfolder if the CLN sprint generates more than 25 audit docs
3. Move only after confirming no cross-references will break

---

## Task Output

```
Task ID: CLN-007
Files inspected: Docs/ folder listing (Glob), Docs\DOCS_INDEX.md
Files changed: Docs\DOCS_FOLDER_SORTING_PROPOSAL.md (created)
Validation: Categorized all 90+ docs from folder listing. Cross-referenced existing DOCS_INDEX.md sections.
Findings: 10 proposed categories. No files need to move. CLN sprint docs may warrant a subfolder if count exceeds 25.
Open questions: Operator to decide whether to reorganize DOCS_INDEX.md sections.
Risk: Low — documentation only; no files moved.
```
