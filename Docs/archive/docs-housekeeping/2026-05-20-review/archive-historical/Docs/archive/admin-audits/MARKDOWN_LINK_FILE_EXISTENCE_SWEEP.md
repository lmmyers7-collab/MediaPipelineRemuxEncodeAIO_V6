# Markdown Link and File-Existence Sweep

Date: 2026-05-14

Scans all markdown files in `Docs/` for cross-file links and verifies referenced files exist. Separately checks that DOCS_INDEX.md entries match actual files on disk.

---

## Summary

- **Zero cross-file hyperlinks** found in `Docs/*.md` — all `](` link syntax is heading anchors (`#section-name`) within the same file
- **All DOCS_INDEX.md entries verified present** on disk (see table below)
- **No broken links or phantom file references** detected
- **New CLN sprint output docs** (18 files created during CLN-001 through CLN-030) are present on disk but not yet listed in DOCS_INDEX.md; that gap is covered by the DOCS_INDEX update task

---

## Link Syntax Findings

### Cross-file hyperlinks

Pattern searched: `](` in all `Docs/*.md` files.

**Result**: All `](` occurrences are heading anchors of the form `[label](#heading-slug)`. These are within-file navigation links used in `CHANGELOG_NAVIGATION_PROPOSAL.md` and `CHANGELOG_NAVIGATION_HEALTH_REVIEW.md`. No link points to another file.

**Implication**: There are no broken cross-file hyperlinks in the Docs/ markdown corpus. The documentation convention uses backtick notation (`` `FILENAME.md` ``) for cross-document references rather than hyperlinks.

### Backtick cross-references

Docs use prose references like:
- `` companion to `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` ``
- `` see `WEBVIEW_SMOKE_TEST_CATALOG.md` ``

These are not machine-verifiable hyperlinks; they are text references. All sampled backtick-referenced files verified present on disk.

---

## DOCS_INDEX.md File-Existence Check

Files referenced in DOCS_INDEX.md (as of this audit date) verified against `Docs/**/*.md` on disk:

### Operator Docs (all present)

| File | Present |
|---|---|
| `Docs/README_MediaPipelineRemuxEncodeAIO.md` | Yes |
| `Docs/TLDR.md` | Yes |
| `Docs/WEBVIEW_SMOKE_TEST_CATALOG.md` | Yes |
| `Docs/OPERATOR_GLOSSARY.md` | Yes |
| `Docs/VALIDATION_LADDER_RUNBOOK.md` | Yes |
| `Docs/PACKAGING_DEPENDENCY_INVENTORY.md` | Yes |
| `Docs/RELEASE_PACKAGE_ADMIN_INVENTORY.md` | Yes |
| `Docs/WEBVIEW_SMOKE_RESULT_TEMPLATE.md` | Yes |
| `Docs/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` | Yes |
| `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` | Yes |
| `Docs/FAILURE_TRIAGE_WORKSHEET.md` | Yes |
| `Docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md` | Yes |
| `Docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md` | Yes |
| `Docs/Pipeline/NEW_PC_CHECKLIST_MediaPipelineRemuxEncodeAIO.md` | Yes |
| `Docs/Pipeline/README_MediaPipelineRemuxEncodeAIO_Deployment.md` | Yes |
| `Docs/DesktopApp/README_MediaPipelineRemuxEncodeAIO_DesktopApp.md` | Yes |
| `Docs/RealMediaValidationRuns/README.md` | Yes |

### Engineering Docs (all present)

| File | Present |
|---|---|
| `Docs/CODE_CLEANUP_CHECKLIST.md` | Yes |
| `Docs/CONTROL_SURFACE_HARDENING_CHECKLIST.md` | Yes |
| `Docs/DEPLOYABILITY_CHECKLIST.md` | Yes |
| `Docs/NETWORK_MODE_CHECKLIST.md` | Yes |
| `Docs/NETWORK_READ_ONLY_PARITY_AUDIT.md` | Yes |
| `Docs/REMEDIATION_CHANGELOG.md` | Yes |
| `Docs/GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md` | Yes |
| `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md` | Yes |
| `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` | Yes |
| `Docs/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md` | Yes |
| `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md` | Yes |
| `Docs/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md` | Yes |
| `Docs/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md` | Yes |
| `Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | Yes |
| `Docs/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | Yes |
| `Docs/API_ROUTE_INVENTORY.md` | Yes |
| `Docs/COMMAND_OWNERSHIP_MATRIX.md` | Yes |
| `Docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md` | Yes |
| `Docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` | Yes |
| `Docs/WEBVIEW_DOM_ID_INVENTORY.md` | Yes |
| `Docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md` | Yes |
| `Docs/STATE_FILE_SCHEMA_REFERENCE.md` | Yes |
| `Docs/LOG_ARTIFACT_CATALOG.md` | Yes |
| `Docs/TEST_COVERAGE_MATRIX.md` | Yes |
| `Docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` | Yes |
| `Docs/SETTINGS_KEY_OWNERSHIP_MAP.md` | Yes |
| `Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md` | Yes |
| `Docs/RENAME_TOOL_EDGE_CASE_CATALOG.md` | Yes |
| `Docs/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md` | Yes |
| `Docs/PACKAGING_MANIFEST_REVIEW.md` | Yes |
| `Docs/WEBVIEW_OPERATOR_ERROR_MESSAGE_REVIEW.md` | Yes |
| `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md` | Yes |
| `Docs/DOCS_DEAD_MARKDOWN_AUDIT.md` | Yes |
| `Docs/RENAME_SAFETY_TEST_INVENTORY.md` | Yes |
| `Docs/PENDING_PUBLISH_FIXTURE_INVENTORY.md` | Yes |
| `Docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md` | Yes |
| `Docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` | Yes |
| `Docs/BROWSER_SMOKE_TEST_RUNBOOK.md` | Yes |
| `Docs/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md` | Yes |
| `Docs/COMMAND_HISTORY_CONSISTENCY_AUDIT.md` | Yes |
| `Docs/STALE_VERSION_LABEL_AUDIT.md` | Yes |
| `Docs/STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md` | Yes |
| `Docs/POWERSHELL_HOST_EXPECTATIONS.md` | Yes |
| `Docs/WEBVIEW_OPERATOR_COPY_AUDIT.md` | Yes |
| `Docs/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md` | Yes |
| `Docs/STALE_DOCS_TODO_AUDIT.md` | Yes |
| `Docs/CHANGELOG_NAVIGATION_PROPOSAL.md` | Yes |
| `Docs/RUNTIME_ARTIFACT_INVENTORY.md` | Yes |
| `Docs/TEST_SUITE_SUBSYSTEM_INVENTORY.md` | Yes |
| `Docs/CONFIG_KEY_GLOSSARY_DRAFT.md` | Yes |
| `Docs/NO_TOUCH_BOUNDARY_REGISTER.md` | Yes |
| `Docs/V5_TRANSITION_STATUS_BOARD.md` | Yes |
| `Docs/V5_MIGRATION_RISK_REGISTER.md` | Yes |
| `Docs/NETWORK_UX_IMPROVEMENTS.md` | Yes |
| `Docs/DesktopApp/docs/README.md` | Yes |
| `Docs/DesktopApp/docs/V3_RELIABILITY_NOTES.md` | Yes |
| `Docs/DesktopApp/docs/FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md` | Yes |
| `Docs/V5_HOUSEKEEPING_BEFORE_TRANSITION_RESUME.md` | Yes |
| `Docs/ROOT_SCRIPT_INVENTORY.md` | Yes |
| `Docs/RELEASE_SELF_TEST_LAYOUT_AUDIT.md` | Yes |
| `Docs/LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md` | Yes |
| `Docs/SCHEDULE_STALE_READONLY_WORDING_AUDIT.md` | Yes |
| `Docs/COMMAND_HISTORY_OWNER_COVERAGE_AUDIT.md` | Yes |
| `Docs/SETTINGS_RAW_KEY_TRIAGE.md` | Yes |

### Delegation And Archive Docs (all present)

| File | Present |
|---|---|
| `Docs/CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md` | Yes |
| `Docs/CLAUDE_HANDOFF_20_TASK_BACKLOG.md` | Yes |
| `Docs/CLAUDE_HANDOFF_CLEANUP_REVIEW_SORTING_BACKLOG.md` | Yes |
| `Docs/CLAUDE_HANDOFF_STATUS_RECONCILIATION.md` | Yes |
| `Docs/CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md` | Yes |

### UI Planning Docs and Migration Notes (all present)

| File | Present |
|---|---|
| `Docs/UI_CHECKLIST.md` | Yes |
| `Docs/UI_CHECKLIST_2.md` | Yes |
| `Docs/UI_CHECKLIST_3.md` | Yes |
| `Docs/UI_IMPROVEMENT_CHECKLIST.md` | Yes |
| `Docs/V4_MIGRATION_NOTES.md` | Yes |

---

## Files Present on Disk but NOT in DOCS_INDEX.md

These CLN sprint output docs exist on disk but were not yet added to DOCS_INDEX.md. They are not broken references — they are documentation coverage gaps in the index.

| File | Created By |
|---|---|
| `Docs/TAURI_DAILY_DRIVER_WORDING_AUDIT.md` | CLN-019 |
| `Docs/POWERSHELL_HOST_WORDING_AUDIT.md` | CLN-021 |
| `Docs/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md` | CLN-025 |
| `Docs/OPERATOR_COPY_CONSISTENCY_REVIEW.md` | CLN-026 |
| `Docs/RENAME_DOCS_FRESHNESS_REVIEW.md` | CLN-016 |
| `Docs/PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md` | CLN-017 |
| `Docs/NETWORK_READONLY_WORDING_AUDIT.md` | CLN-018 |
| `Docs/CHANGELOG_NAVIGATION_HEALTH_REVIEW.md` | CLN-028 |
| `Docs/BROWSER_SMOKE_CATALOG_SORT_FINDINGS.md` | CLN-005 |
| `Docs/DIAGNOSTICS_TARGET_SYNC_AUDIT.md` | CLN-014 |
| `Docs/RUNTIME_ARTIFACT_SORTING_NOTES.md` | CLN-022 |
| `Docs/GENERATED_VENDOR_EXCLUSION_REVIEW.md` | CLN-023 |
| `Docs/WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md` | CLN-004 |
| `Docs/ADMIN_TASK_COMPLETION_BOARD.md` | CLN-030 |
| `Docs/DOCS_FOLDER_SORTING_PROPOSAL.md` | CLN-007 |
| `Docs/CHECKLIST_ARCHIVE_REVIEW.md` | CLN-008 |
| `Docs/WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md` | CLN-011 (this session) |
| `Docs/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` | CLN-012 (this session) |
| `Docs/MARKDOWN_LINK_FILE_EXISTENCE_SWEEP.md` | CLN-029 (this session) |

These 19 files should be added to DOCS_INDEX.md Engineering Docs section.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| No broken cross-file hyperlinks in Docs/ | Pass — zero cross-file hyperlinks exist |
| All DOCS_INDEX.md entries exist on disk | Pass — all 80+ referenced files verified present |
| New sprint docs accounted for | Pass — 19 CLN sprint docs noted as not yet indexed |

---

## Task Output

```
Task ID: CLN-029
Files inspected: All Docs/*.md (](  link grep); Docs/DOCS_INDEX.md entries cross-checked against Glob results
Files changed: Docs\MARKDOWN_LINK_FILE_EXISTENCE_SWEEP.md (created)
Validation: Test-Path Docs\MARKDOWN_LINK_FILE_EXISTENCE_SWEEP.md
Findings: Zero cross-file hyperlinks found. All DOCS_INDEX.md entries verified present. 19 CLN sprint output docs on disk but not yet in DOCS_INDEX.md.
Open questions: None.
Risk: Low — documentation only.
```
