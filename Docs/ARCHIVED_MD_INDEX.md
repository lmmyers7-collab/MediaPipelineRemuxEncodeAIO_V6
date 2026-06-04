# Archived Markdown Index

Last updated: 2026-06-04

This index reflects the current archive/quarantine layout after the housekeeping move and the operator's later manual deletion of some active docs. The old `Docs/archive/admin-audits/`, `completed-audits/`, `completed-checklists/`, `historical-plans/`, `historical-reviews/`, `old-ai-directives/`, and `ui-impl-specs/` paths should no longer be treated as active archive roots. The preserved copies live under:

`Docs/archive/docs-housekeeping/2026-05-20-review/`

Completed Markdown archived on 2026-06-04 lives under:

`Docs/archive/docs-housekeeping/2026-06-04-completed-md-pass/`

## Archive Root Summary

| Folder | Count | Meaning |
|---|---:|---|
| `archive-historical/` | 65 | Completed, superseded, or historical docs retained for reference. |
| `consolidated-after-extraction/` | 5 | Docs whose active value should be merged into canonical docs, not restored as standalone guidance. |
| `delete-candidates/` | 19 | Quarantine-only deletion candidates. Do not treat these as deleted unless a later review confirms removal. |
| `../2026-06-04-completed-md-pass/` | 25 moved docs plus README | Completed/superseded historical audits, dependency-refactor tracker docs, and UX remediation tracker docs moved out of active topic folders. |

## Historical Archive Groups

Under `archive-historical/`:

| Original group | Count | Current location |
|---|---:|---|
| Root historical reviews/reports | 3 | `archive-historical/V5_TRANSITION_CODE_REVIEW.md`, `archive-historical/DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md`, `archive-historical/DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md` |
| Proposal history | 1 | `archive-historical/Docs/proposals/GOD_FILE_SPLIT_PLAN.md` |
| Admin audits | 18 | `archive-historical/Docs/archive/admin-audits/` |
| Completed audits | 14 | `archive-historical/Docs/archive/completed-audits/` |
| Completed checklists | 12 | `archive-historical/Docs/archive/completed-checklists/` |
| Historical plans | 4 | `archive-historical/Docs/archive/historical-plans/` |
| Historical reviews | 4 | `archive-historical/Docs/archive/historical-reviews/` |
| UI implementation specs | 9 | `archive-historical/Docs/archive/ui-impl-specs/` |

## Consolidated After Extraction

- `consolidated-after-extraction/.../DEPLOYABILITY_CHECKLIST.md`
- `consolidated-after-extraction/.../TAURI_WEBVIEW_PARITY_MATRIX.md`
- `consolidated-after-extraction/.../FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md`
- `consolidated-after-extraction/.../README_MediaPipelineRemuxEncodeAIO_DesktopApp.md`
- `consolidated-after-extraction/HOUSEKEEPING_REVIEW.md`

These files should remain quarantined unless a human wants to recover a specific paragraph into `DOCS_INDEX.md`, `CURRENT_PROJECT_STATE.md`, operator docs, testing docs, release docs, or the active README/TLDR.

## Delete Candidates

Under `delete-candidates/Docs/archive/admin-audits/`:

- `DOCS_DEAD_MARKDOWN_AUDIT.md`
- `DOCS_FOLDER_SORTING_PROPOSAL.md`
- `HOUSEKEEPING_AUDIT_REPORT.md`
- `HOUSEKEEPING_EXECUTION_CHECKLIST.md`
- `LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md`
- `MD_CLEANUP_AUDIT_REPORT.md`
- `STALE_VERSION_LABEL_AUDIT.md`
- `STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md`
- `TAURI_DAILY_DRIVER_WORDING_AUDIT.md`

Under `delete-candidates/Docs/archive/old-ai-directives/`:

- `CLAUDE_HANDOFF_20_TASK_BACKLOG.md`
- `CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md`
- `CLAUDE_HANDOFF_CLEANUP_REVIEW_SORTING_BACKLOG.md`
- `CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md`
- `CLAUDE_HANDOFF_ROUND3_COMPLETION_SUMMARY.md`
- `CLAUDE_HANDOFF_ROUND4_COMPLETION_SUMMARY.md`
- `CLAUDE_HANDOFF_STATUS_RECONCILIATION.md`
- `CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md`
- `CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md`
- `CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND4.md`

## Completed Markdown Pass - 2026-06-04

Under `Docs/archive/docs-housekeeping/2026-06-04-completed-md-pass/`:

- `audits/latest.md`
- `audits/CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md`
- `audits/DEAD_EXPORT_AUDIT_2026-05-19.md`
- `dependency-refactor/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`
- `dependency-refactor/dependency-refactor-phases/`: completed phase tracker files from `00_navigation_and_tracker.md` through `07_full_cleanup_review_and_done.md`.
- `ui/V6_OPERATOR_UX_REMEDIATION_REMAINING_TASKS.md`

## Active Docs Not Archived

Use `DOCS_INDEX.md` for the current active documentation map. Notable active docs include:

- `CURRENT_PROJECT_STATE.md`
- `TLDR.md`
- `README_MediaPipelineRemuxEncodeAIO.md`
- `DOCS_INDEX.md`
- `DOC_TOUCH_LOG.md`
- `REMEDIATION_CHANGELOG.md`
- `ACTIVE_FIX_CHECKLIST.md`
- `audits/` redirect stubs
- `architecture/`
- `inventories/`
- `operator/`
- `sample-validation/`
- `testing/`
- `DesktopApp/docs/`
- `ui/`

## Deleted Or Empty Active Areas

The following active documentation areas were present in older indexes but currently contain no Markdown/text docs:

- `Docs/active-plans/`
- `Docs/Pipeline/`
- `Docs/proposals/`
- `Docs/RealMediaValidationRuns/`

If those docs are restored later, update both this file and `DOCS_INDEX.md` in the same pass.
