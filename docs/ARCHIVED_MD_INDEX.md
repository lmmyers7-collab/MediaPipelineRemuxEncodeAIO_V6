# Archived Markdown Index

Last updated: 2026-07-04

This index reflects the current archive/quarantine layout after the housekeeping move and the operator's later manual deletion of some active docs. The old `docs/archive/admin-audits/`, `completed-audits/`, `completed-checklists/`, `historical-plans/`, `historical-reviews/`, `old-ai-directives/`, and `ui-impl-specs/` paths should no longer be treated as active archive roots. The preserved copies live under:

`docs/archive/docs-housekeeping/2026-05-20-review/`

Completed Markdown archived on 2026-06-04 lives under:

`docs/archive/docs-housekeeping/2026-06-04-completed-md-pass/`

Completed implementation plans and 2026-06 audit/review evidence pruned from
the active docs tree on 2026-06-24 live under:

`docs/archive/docs-housekeeping/2026-06-24-doc-prune/`

Completed plans, obsolete proposals, and stale session notes pruned from the
active docs tree on 2026-07-04 live under:

`docs/archive/docs-housekeeping/2026-07-04-doc-cleanup/`

## Archive Root Summary

| Folder | Count | Meaning |
|---|---:|---|
| `archive-historical/` | 65 | Completed, superseded, or historical docs retained for reference. |
| `consolidated-after-extraction/` | 5 | Docs whose active value should be merged into canonical docs, not restored as standalone guidance. |
| `delete-candidates/` | 19 | Quarantine-only deletion candidates. Do not treat these as deleted unless a later review confirms removal. |
| `../2026-06-04-completed-md-pass/` | 25 moved docs plus README | Completed/superseded historical audits, dependency-refactor tracker docs, and UX remediation tracker docs moved out of active topic folders. |
| `../2026-06-24-doc-prune/` | Current docs cleanup archive | Completed implementation plans plus 2026-06 audit/review evidence snapshots moved out of active topic folders. |
| `../2026-07-04-doc-cleanup/` | Current docs cleanup archive | Completed release/test-split/architecture-boundary docs, obsolete architecture proposals, and stale session notes moved out of active topic folders. |

## Historical Archive Groups

Under `archive-historical/`:

| Original group | Count | Current location |
|---|---:|---|
| Root historical reviews/reports | 3 | `archive-historical/V5_TRANSITION_CODE_REVIEW.md`, `archive-historical/DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md`, `archive-historical/DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md` |
| Proposal history | 1 | `archive-historical/docs/proposals/GOD_FILE_SPLIT_PLAN.md` |
| Admin audits | 18 | `archive-historical/docs/archive/admin-audits/` |
| Completed audits | 14 | `archive-historical/docs/archive/completed-audits/` |
| Completed checklists | 12 | `archive-historical/docs/archive/completed-checklists/` |
| Historical plans | 4 | `archive-historical/docs/archive/historical-plans/` |
| Historical reviews | 4 | `archive-historical/docs/archive/historical-reviews/` |
| UI implementation specs | 9 | `archive-historical/docs/archive/ui-impl-specs/` |

## Consolidated After Extraction

- `consolidated-after-extraction/.../DEPLOYABILITY_CHECKLIST.md`
- `consolidated-after-extraction/.../TAURI_WEBVIEW_PARITY_MATRIX.md`
- `consolidated-after-extraction/.../FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md`
- `consolidated-after-extraction/.../README_MediaPipelineRemuxEncodeAIO_DesktopApp.md`
- `consolidated-after-extraction/HOUSEKEEPING_REVIEW.md`

These files should remain quarantined unless a human wants to recover a specific paragraph into `DOCS_INDEX.md`, `CURRENT_PROJECT_STATE.md`, operator docs, testing docs, release docs, or the active README.

## Delete Candidates

Under `delete-candidates/docs/archive/admin-audits/`:

- `DOCS_DEAD_MARKDOWN_AUDIT.md`
- `DOCS_FOLDER_SORTING_PROPOSAL.md`
- `HOUSEKEEPING_AUDIT_REPORT.md`
- `HOUSEKEEPING_EXECUTION_CHECKLIST.md`
- `LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md`
- `MD_CLEANUP_AUDIT_REPORT.md`
- `STALE_VERSION_LABEL_AUDIT.md`
- `STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md`
- `TAURI_DAILY_DRIVER_WORDING_AUDIT.md`

Under `delete-candidates/docs/archive/old-ai-directives/`:

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

Under `docs/archive/docs-housekeeping/2026-06-04-completed-md-pass/`:

- `audits/latest.md`
- `audits/CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md`
- `audits/DEAD_EXPORT_AUDIT_2026-05-19.md`
- `dependency-refactor/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`
- `dependency-refactor/dependency-refactor-phases/`: completed phase tracker files from `00_navigation_and_tracker.md` through `07_full_cleanup_review_and_done.md`.
- `ui/V6_OPERATOR_UX_REMEDIATION_REMAINING_TASKS.md`

## Documentation Cleanup Pass - 2026-07-04

Under `docs/archive/docs-housekeeping/2026-07-04-doc-cleanup/`:

- `README.md`: classification notes for this archive pass.
- `implementation/architecture-boundary-cleanup/`: completed GitHub #23
  dependency-boundary planning pack and edge ledger.
- `implementation/local-api-test-split/`: executed Local API/WebView static
  test split planning pack and assertion ledger.
- `implementation/release-foundation/`: completed `2026.06.04.001` release
  foundation phase plans. The reusable real-media pilot checklist remains
  active at `docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`.
- `implementation/documentation-cleanup-goal-prompt.md`: completed prompt-only
  documentation cleanup plan.
- `architecture/NETWORK_WORKER_HARDENING_PLAN.md`: completed network
  worker/coordinator hardening plan.
- `architecture/QUEUE_SOURCE_SCAN_AND_CURATION_PLAN.md`: historical queue scan
  and curation proposal not listed in the current active backlog.
- `sessions/SESSION-2026-06-02-to-2026-06-23.md`: stale session log moved out
  of active guidance.

## Active Docs Not Archived

Use `DOCS_INDEX.md` for the current active documentation map. Notable active docs include:

- `CURRENT_PROJECT_STATE.md`
- `README_MediaPipelineRemuxEncodeAIO.md`
- `DOCS_INDEX.md`
- `REMEDIATION_CHANGELOG.md`
- `audits/` redirect stubs
- `reviews/function-module-audit-2026-06-11/FINDINGS_REGISTER.md`
- `reviews/network-coordinator-worker-mode-2026-06-15/FINDINGS_REGISTER.md`
- `reviews/network-coordinator-worker-mode-2026-06-15/DISPOSITION_LEDGER.md`
- `architecture/`
- `inventories/`
- `operator/`
- `sample-validation/`
- `testing/`
- `ui/`

## Deleted Or Empty Active Areas

The following active documentation areas were present in older indexes but currently contain no Markdown/text docs:

- `docs/active-plans/`
- `docs/ACTIVE_FIX_CHECKLIST.md`
- `docs/DOC_TOUCH_LOG.md`
- `docs/SESSION.md`
- `docs/Pipeline/`
- `docs/proposals/`

If those docs are restored later, update both this file and `DOCS_INDEX.md` in the same pass.
