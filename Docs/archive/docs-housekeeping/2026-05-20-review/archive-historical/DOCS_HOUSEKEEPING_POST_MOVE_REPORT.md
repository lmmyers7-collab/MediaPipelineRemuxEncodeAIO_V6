# Docs Housekeeping Post-Move Report

Date: 2026-05-20

Archive root:

`Docs/archive/docs-housekeeping/2026-05-20-review/`

## Summary

- Moved 87 documentation files into quarantine/archive folders.
- No files were permanently deleted.
- No source code was intentionally modified.
- Updated the active documentation navigation layer and high-visibility operator docs to reflect the V6 WebView/local-API path and removed Tk/CustomTkinter shell.
- Remaining risky references are now documented below instead of silently ignored.

## Move Counts

| Disposition | Count | Destination |
|---|---:|---|
| `CONSOLIDATE_INTO_CANONICAL` | 5 | `Docs/archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/` |
| `ARCHIVE_HISTORICAL` | 63 | `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/` |
| `DELETE_CANDIDATE` | 19 | `Docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/` |
| `DELETE_NOW_SAFE` | 0 | not used |

## Files Moved

### Consolidated After Extraction

- `Docs/architecture/DEPLOYABILITY_CHECKLIST.md`
- `Docs/architecture/TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs/DesktopApp/docs/FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md`
- `Docs/DesktopApp/README_MediaPipelineRemuxEncodeAIO_DesktopApp.md`
- `HOUSEKEEPING_REVIEW.md`

### Archive Historical

- `Docs/proposals/GOD_FILE_SPLIT_PLAN.md`
- `V5_TRANSITION_CODE_REVIEW.md`
- `Docs/archive/completed-audits/CHANGELOG_NAVIGATION_PROPOSAL.md`
- `Docs/archive/completed-audits/CLAUDE_REVIEW_TARGETS_RECENT_WEBVIEW_HARDENING.md`
- `Docs/archive/completed-audits/COMMAND_HISTORY_CONSISTENCY_AUDIT.md`
- `Docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`
- `Docs/archive/completed-audits/FRONTEND_MODULE_SIZE_COHESION_REPORT.md`
- `Docs/archive/completed-audits/NETWORK_READ_ONLY_PARITY_AUDIT.md`
- `Docs/archive/completed-audits/PACKAGING_MANIFEST_REVIEW.md`
- `Docs/archive/completed-audits/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md`
- `Docs/archive/completed-audits/RELEASE_SELF_TEST_LAYOUT_AUDIT.md`
- `Docs/archive/completed-audits/STAGE16_UI_REF_AUDIT.md`
- `Docs/archive/completed-audits/TAURI_ASSET_GATE_FRAGMENT_AUDIT.md`
- `Docs/archive/completed-audits/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md`
- `Docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- `Docs/archive/completed-audits/WEBVIEW_OPERATOR_ERROR_MESSAGE_REVIEW.md`
- `Docs/archive/historical-reviews/GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md`
- `Docs/archive/historical-reviews/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md`
- `Docs/archive/historical-reviews/V3_RELIABILITY_NOTES.md`
- `Docs/archive/historical-reviews/V4_MIGRATION_NOTES.md`
- `Docs/archive/admin-audits/BROWSER_SMOKE_CATALOG_SORT_FINDINGS.md`
- `Docs/archive/admin-audits/CHANGELOG_NAVIGATION_HEALTH_REVIEW.md`
- `Docs/archive/admin-audits/COMMAND_HISTORY_OWNER_COVERAGE_AUDIT.md`
- `Docs/archive/admin-audits/DIAGNOSTICS_TARGET_SYNC_AUDIT.md`
- `Docs/archive/admin-audits/GENERATED_VENDOR_EXCLUSION_REVIEW.md`
- `Docs/archive/admin-audits/MARKDOWN_LINK_FILE_EXISTENCE_SWEEP.md`
- `Docs/archive/admin-audits/NETWORK_READONLY_WORDING_AUDIT.md`
- `Docs/archive/admin-audits/OPERATOR_COPY_CONSISTENCY_REVIEW.md`
- `Docs/archive/admin-audits/PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md`
- `Docs/archive/admin-audits/POWERSHELL_HOST_WORDING_AUDIT.md`
- `Docs/archive/admin-audits/RENAME_DOCS_FRESHNESS_REVIEW.md`
- `Docs/archive/admin-audits/RUNTIME_ARTIFACT_SORTING_NOTES.md`
- `Docs/archive/admin-audits/SCHEDULE_STALE_READONLY_WORDING_AUDIT.md`
- `Docs/archive/admin-audits/STALE_DOCS_TODO_AUDIT.md`
- `Docs/archive/admin-audits/WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md`
- `Docs/archive/admin-audits/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`
- `Docs/archive/admin-audits/WEBVIEW_OPERATOR_COPY_AUDIT.md`
- `Docs/archive/admin-audits/WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md`
- `Docs/archive/completed-checklists/ADMIN_TASK_COMPLETION_BOARD.md`
- `Docs/archive/completed-checklists/CHECKLIST_ARCHIVE_REVIEW.md`
- `Docs/archive/completed-checklists/CODE_CLEANUP_CHECKLIST.md`
- `Docs/archive/completed-checklists/CONTROL_SURFACE_HARDENING_CHECKLIST.md`
- `Docs/archive/completed-checklists/GOD_FILE_SPLIT_PLAN.md`
- `Docs/archive/completed-checklists/GOD_FILE_SPLIT_WAVE6_PLAN.md`
- `Docs/archive/completed-checklists/NETWORK_MODE_CHECKLIST.md`
- `Docs/archive/completed-checklists/UI_CHECKLIST.md`
- `Docs/archive/completed-checklists/UI_CHECKLIST_2.md`
- `Docs/archive/completed-checklists/UI_CHECKLIST_3.md`
- `Docs/archive/completed-checklists/V5_HOUSEKEEPING_BEFORE_TRANSITION_RESUME.md`
- `Docs/archive/completed-checklists/V5_PROGRESS_BARS_PLAN.md`
- `Docs/archive/historical-plans/ACTIVE_FIX_CHECKLIST_20260520_ARCHIVED.md`
- `Docs/archive/historical-plans/V5_TAURI_TRANSITION_CURRENT_PLAN_20260520_ARCHIVED.md`
- `Docs/archive/historical-plans/V5_TRANSITION_REVIEW_FIX_CHECKLIST_20260520_ARCHIVED.md`
- `Docs/archive/historical-plans/V5_TRANSITION_STATUS_BOARD_20260520_ARCHIVED.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE11_CLAUDE.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE12_CLAUDE.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE1_CODEX.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE2_CLAUDE.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE3_CODEX.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE5_CODEX.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE7_CODEX.md`
- `Docs/archive/ui-impl-specs/V5_UI_IMPL_STAGE9_CODEX.md`
- `Docs/archive/ui-impl-specs/V5_UI_PANEL_ORDER_PASS.md`

### Delete Candidates Moved To Quarantine Only

- `Docs/archive/admin-audits/DOCS_DEAD_MARKDOWN_AUDIT.md`
- `Docs/archive/admin-audits/DOCS_FOLDER_SORTING_PROPOSAL.md`
- `Docs/archive/admin-audits/HOUSEKEEPING_AUDIT_REPORT.md`
- `Docs/archive/admin-audits/HOUSEKEEPING_EXECUTION_CHECKLIST.md`
- `Docs/archive/admin-audits/LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md`
- `Docs/archive/admin-audits/MD_CLEANUP_AUDIT_REPORT.md`
- `Docs/archive/admin-audits/STALE_VERSION_LABEL_AUDIT.md`
- `Docs/archive/admin-audits/STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md`
- `Docs/archive/admin-audits/TAURI_DAILY_DRIVER_WORDING_AUDIT.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_20_TASK_BACKLOG.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_CLEANUP_REVIEW_SORTING_BACKLOG.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_ROUND3_COMPLETION_SUMMARY.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_ROUND4_COMPLETION_SUMMARY.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_STATUS_RECONCILIATION.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md`
- `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND4.md`

## Updated Active Docs

- `Docs/DOCS_INDEX.md`
- `Docs/TLDR.md`
- `Docs/README_MediaPipelineRemuxEncodeAIO.md`
- `AI_AGENT_START_HERE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `Docs/ACTIVE_FIX_CHECKLIST.md`
- `Docs/active-plans/V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- `Docs/active-plans/V5_TRANSITION_STATUS_BOARD.md`
- `V5_TRANSITION_REVIEW_FIX_CHECKLIST.md`
- `Docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `Docs/operator/OPERATOR_GLOSSARY.md`
- `Docs/DesktopApp/docs/README.md`
- `Docs/inventories/PACKAGING_DEPENDENCY_INVENTORY.md`
- `Docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- `Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
- `Docs/Pipeline/NEW_PC_CHECKLIST_MediaPipelineRemuxEncodeAIO.md`
- `Docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`
- `Docs/inventories/ROOT_SCRIPT_INVENTORY.md`
- `Docs/proposals/CODE_MANAGEMENT_CLEANUP_PLAN.md`
- `Docs/architecture/DECISIONS_AND_HISTORY.md`

## Remaining Broken Or Risky References

These references remain after the move. They were not changed because this pass was documentation-only and did not modify source code, tests, release scripts, or the protected AI directive.

| File | Line | Reference | Risk |
|---|---:|---|---|
| `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` | 481 | `Docs\DesktopApp\README_MediaPipelineRemuxEncodeAIO_DesktopApp.md` | Release self-test may fail because that doc was moved to quarantine. |
| `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` | 309 | `Docs\architecture\DEPLOYABILITY_CHECKLIST.md` | Reliability regression check may fail because that doc was moved to quarantine. |
| `Pipeline\Tests\Unit\Invoke-ActiveDocsReferenceChecks.ps1` | 103 | `Docs\architecture\DEPLOYABILITY_CHECKLIST.md` | Active-doc reference check may fail because the old deployability checklist path no longer exists. |
| `AI_DIRECTIVE.md` | 18, 40, 203, 359, 364 | `Docs/proposals/GOD_FILE_SPLIT_PLAN.md` | Directive still points at a moved split-plan stub. It should be updated only with explicit operator approval. |

## Docs Still Needing Consolidation

- `Docs/ARCHIVED_MD_INDEX.md`: still indexes the pre-quarantine archive layout and should be rewritten around `Docs/archive/docs-housekeeping/2026-05-20-review/`.
- `Docs/ONBOARDING.md`: still references older housekeeping and split-plan locations.
- Several inventory/operator docs still cite moved completed-audit evidence under old `Docs/archive/completed-audits/` or `Docs/archive/admin-audits/` paths. They are not all operator-blocking, but they should be updated opportunistically when those docs are touched.
- `Docs/testing/TEST_COVERAGE_MATRIX.md` still mentions a Tk fallback launcher gate. This is stale for V6 and should be reconciled with the actual V6 tests.
- Historical worksheets under `Docs/RealMediaValidationRuns/` still contain old Tk fallback rows. Treat those as historical evidence, not current instructions.

## Quarantine Candidates, Not True Deletions Yet

Everything under `delete-candidates/` is still only a quarantine candidate. Do not permanently delete until:

1. Release/self-test references above are fixed or intentionally waived.
2. `AI_DIRECTIVE.md` is explicitly approved for update or the old split-plan redirect is intentionally restored.
3. `Docs/ARCHIVED_MD_INDEX.md` is rewritten for the new quarantine layout.
4. A follow-up scan confirms no active docs, scripts, launchers, tests, release packaging, or setup tooling point at the old paths.

## Final Deletion Recommendation

No permanent deletion now.

After the quarantine review passes, the safest later deletion set is the 19 files under:

`Docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/`

Keep the `archive-historical/` and `consolidated-after-extraction/` folders until the operator confirms the active docs contain all needed content and the release/test references are repaired.
