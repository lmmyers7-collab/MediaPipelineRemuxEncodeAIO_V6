# Markdown Cleanup Audit Report

Audit date: 2026-05-15

Scope: all `*.md` files returned by `rg --files -g "*.md"` from the V5 repository root. This report is intentionally non-destructive: no Markdown files were deleted or moved during this cleanup pass.

Follow-up note: after this audit snapshot, smoke wrappers were moved into `SmokeTests/` and two new Markdown files were added: `Docs/SMOKE_TEST_INVENTORY.md` and `SmokeTests/README.md`.

## Summary

- Total Markdown files found: 123.
- Generated/vendor Markdown files: 3 under `DesktopApp/tauri_shell/node_modules/`.
- Project-controlled Markdown files: 120.
- Main problem: the documentation set contains useful current references mixed with completed AI task backlogs, stale audit outputs, overlapping checklists, and large historical transition plans.
- Recommended immediate source-of-truth set:
  - `Docs/CURRENT_PROJECT_STATE.md`
  - `Docs/ACTIVE_FIX_CHECKLIST.md`
  - `Docs/DECISIONS_AND_HISTORY.md`
  - `Docs/ARCHIVED_MD_INDEX.md`
  - `Docs/DOCS_INDEX.md`
  - `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md`
  - `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md`
  - `Docs/VALIDATION_LADDER_RUNBOOK.md`
  - `Docs/TEST_COVERAGE_MATRIX.md`
  - `Docs/NO_TOUCH_BOUNDARY_REGISTER.md`
  - `Docs/V5_MIGRATION_RISK_REGISTER.md`

## Classification Key

- **KEEP AS SOURCE OF TRUTH**: actively useful for current operation, safety, migration, testing, contracts, or architecture.
- **MERGE INTO SUMMARY**: useful durable context exists, but future agents should read the consolidated docs first.
- **ARCHIVE**: completed, historical, superseded, or AI-handoff material. Retain for traceability, but do not use as active direction.
- **DELETE CANDIDATE**: generated/vendor or obviously disposable. Do not delete without an explicit cleanup decision.
- **NEEDS HUMAN REVIEW**: may contain operator-specific evidence, unresolved product decisions, or active-but-uncertain guidance.

## Proposed Final Documentation Layout

Keep these files at `Docs/` root for fast onboarding:

- `CURRENT_PROJECT_STATE.md`: current project purpose, run paths, architecture, migration status, known-safe behavior, blockers, test gates, and risky areas.
- `ACTIVE_FIX_CHECKLIST.md`: unresolved or partially resolved work only, grouped by priority and subsystem.
- `DECISIONS_AND_HISTORY.md`: important decisions and why they were made, without old task noise.
- `ARCHIVED_MD_INDEX.md`: one-line index of old AI directives, completed backlogs, stale audits, and archival docs.
- `DOCS_INDEX.md`: broad index for operator and engineering references.
- `TLDR.md`: operator-friendly quick reference.

Recommended archive folder, pending human approval:

- `Docs/archive/old-ai-directives/`: Claude handoffs, completed sprint boards, completed UI/control checklists, stale one-off audits.
- `Docs/archive/historical-reviews/`: large framework/audit/review documents superseded by current state docs but worth keeping.
- `Docs/archive/admin-audits/`: link sweeps, wording audits, route-count sync audits, and other completed administrative checks.

No delete action is recommended without approval. The only delete candidates are generated vendor Markdown files under `node_modules`, and even those should be removed only as part of a normal dependency cleanup.

## Inventory And Classification

| Markdown file | Classification | Recommended action | Reason / evidence | Risk if lost |
| --- | --- | --- | --- | --- |
| `DesktopApp/tauri_shell/node_modules/@tauri-apps/cli-win32-x64-msvc/README.md` | DELETE CANDIDATE | Leave untouched unless pruning `node_modules` | Generated package README; not project-authored. | Low if package lock/install workflow is preserved. |
| `DesktopApp/tauri_shell/node_modules/@tauri-apps/cli/CHANGELOG.md` | DELETE CANDIDATE | Leave untouched unless pruning `node_modules` | Generated package changelog; not project-authored. | Low; recoverable from npm package. |
| `DesktopApp/tauri_shell/node_modules/@tauri-apps/cli/README.md` | DELETE CANDIDATE | Leave untouched unless pruning `node_modules` | Generated package README; not project-authored. | Low; recoverable from npm package. |
| `DesktopApp/tauri_shell/README.md` | KEEP AS SOURCE OF TRUTH | Keep | Current Tauri/WebView2 preview launch, validation ladder, and backend lifecycle notes. | Medium; operators lose preview launch/run context. |
| `Docs/archive/completed-checklists/ADMIN_TASK_COMPLETION_BOARD.md` | ARCHIVE | Move later to archive | All CLN/CLN3 admin tasks marked complete. | Low; completion history only. |
| `Docs/API_ROUTE_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Authoritative GET/POST route inventory and effect classes. | High; route contract drift becomes harder to detect. |
| `Docs/archive/admin-audits/BROWSER_SMOKE_CATALOG_SORT_FINDINGS.md` | ARCHIVE | Move later to archive | One-off catalog ordering audit; findings complete. | Low. |
| `Docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` | KEEP AS SOURCE OF TRUTH | Keep | Current mutation-boundary guarantees for WebView smokes. | High; safety contract evidence would be lost. |
| `Docs/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md` | KEEP AS SOURCE OF TRUTH | Keep | Current smoke failure signatures and first actions. | Medium; debugging browser smoke failures slows down. |
| `Docs/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` | KEEP AS SOURCE OF TRUTH | Keep | Current Node/Chrome/Edge readiness checks. | Medium. |
| `Docs/BROWSER_SMOKE_TEST_RUNBOOK.md` | KEEP AS SOURCE OF TRUTH | Keep | Current browser smoke invocation and failure interpretation. | High; test execution confidence drops. |
| `Docs/CHANGELOG_NAVIGATION_HEALTH_REVIEW.md` | MERGE INTO SUMMARY | Merge, then archive | Useful diagnosis of huge changelog navigation pain; not active by itself. | Low after `ACTIVE_FIX_CHECKLIST` keeps the unresolved item. |
| `Docs/CHANGELOG_NAVIGATION_PROPOSAL.md` | NEEDS HUMAN REVIEW | Keep until pruning decision | Contains unchecked archive-split criteria for the giant changelog. | Medium; premature archiving could lose traceability. |
| `Docs/archive/completed-checklists/CHECKLIST_ARCHIVE_REVIEW.md` | ARCHIVE | Move later to archive | Completed checklist classification snapshot. | Low. |
| `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_20_TASK_BACKLOG.md` | ARCHIVE | Move later to old AI directives | Completed/mostly reconciled Claude task backlog. | Low; status is summarized elsewhere. |
| `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md` | ARCHIVE | Move later to old AI directives | Completed administrative task backlog. | Low. |
| `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_CLEANUP_REVIEW_SORTING_BACKLOG.md` | ARCHIVE | Move later to old AI directives | Completed cleanup/review/sorting handoff. | Low. |
| `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md` | ARCHIVE | Move later to old AI directives | Wrapper task completed; smoke exists. | Low. |
| `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_ROUND3_COMPLETION_SUMMARY.md` | ARCHIVE | Move later to old AI directives | Historical completion summary. | Low. |
| `Docs/archive/old-ai-directives/CLAUDE_HANDOFF_STATUS_RECONCILIATION.md` | ARCHIVE | Move later to old AI directives | Historical reconciliation snapshot. | Low. |
| `Docs/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md` | NEEDS HUMAN REVIEW | Keep until operator confirms closed | `DOCS_INDEX.md` labels this active even though many tasks appear superseded. | Medium; may still contain unmerged work expectations. |
| `Docs/CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md` | NEEDS HUMAN REVIEW | Keep until operator confirms closed | `DOCS_INDEX.md` labels this active; likely completed but not formally closed. | Medium. |
| `Docs/CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND4.md` | NEEDS HUMAN REVIEW | Keep until operator confirms closed | `DOCS_INDEX.md` labels this active; task status needs reconciliation. | Medium. |
| `Docs/archive/completed-checklists/CODE_CLEANUP_CHECKLIST.md` | ARCHIVE | Move later to archive | V4 cleanup archive with completed rows pruned. | Low. |
| `Docs/COMMAND_HISTORY_CONSISTENCY_AUDIT.md` | MERGE INTO SUMMARY | Merge key contract, then archive | Useful command journal schema notes; one-off audit form. | Medium if command journal schema is not retained elsewhere. |
| `Docs/archive/admin-audits/COMMAND_HISTORY_OWNER_COVERAGE_AUDIT.md` | ARCHIVE | Move later to admin audits | Coverage check completed and indexed. | Low. |
| `Docs/COMMAND_OWNERSHIP_MATRIX.md` | KEEP AS SOURCE OF TRUTH | Keep | Command route ownership and mutation classes. | High. |
| `Docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md` | KEEP AS SOURCE OF TRUTH | Keep | Operator playbook for Completed/Pending failures. | High. |
| `Docs/CONFIG_KEY_GLOSSARY_DRAFT.md` | MERGE INTO SUMMARY | Keep until promoted or merged | Useful config glossary but marked draft. | Medium; config meaning and risk notes useful. |
| `Docs/archive/completed-checklists/CONTROL_SURFACE_HARDENING_CHECKLIST.md` | ARCHIVE | Move later to archive | Completed control-surface archive. | Low. |
| `Docs/DEPLOYABILITY_CHECKLIST.md` | KEEP AS SOURCE OF TRUTH | Keep | Current deployability status and cleanup chunks. | Medium. |
| `Docs/DesktopApp/docs/FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md` | NEEDS HUMAN REVIEW | Keep and reconcile title/scope | User-updated feature outline, but title still says V4 while repo is V5. | Medium; intended design spec could be misread as stale. |
| `Docs/DesktopApp/docs/README.md` | KEEP AS SOURCE OF TRUTH | Keep | Desktop app structure and backend integration notes. | Medium. |
| `Docs/archive/historical-reviews/V3_RELIABILITY_NOTES.md` | ARCHIVE | Move later to historical reviews | Historical filename and V4 reliability content. | Low. |
| `Docs/DesktopApp/README_MediaPipelineRemuxEncodeAIO_DesktopApp.md` | KEEP AS SOURCE OF TRUTH | Keep | Desktop app purpose, launch modes, and UI responsibilities. | Medium. |
| `Docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` | KEEP AS SOURCE OF TRUTH | Keep | Diagnostics allowlisted target usage and operator sequences. | High. |
| `Docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` | KEEP AS SOURCE OF TRUTH | Keep | 20 target allowlist reference and safety guarantee. | High. |
| `Docs/archive/admin-audits/DIAGNOSTICS_TARGET_SYNC_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed sync audit. | Low. |
| `Docs/DOCS_DEAD_MARKDOWN_AUDIT.md` | MERGE INTO SUMMARY | Merge into this cleanup system, then archive | Older markdown audit; partially superseded by this report. | Low after this report. |
| `Docs/DOCS_FOLDER_SORTING_PROPOSAL.md` | MERGE INTO SUMMARY | Merge taxonomy, then archive | Useful non-moving taxonomy proposal; superseded by current consolidation plan. | Low. |
| `Docs/DOCS_INDEX.md` | KEEP AS SOURCE OF TRUTH | Keep and update | Broad index and discoverability hub. | High. |
| `Docs/FAILURE_TRIAGE_WORKSHEET.md` | KEEP AS SOURCE OF TRUTH | Keep | Operator worksheet for pipeline failures. | Medium. |
| `Docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md` | MERGE INTO SUMMARY | Merge current concerns, then archive | One-off cohesion report; useful warning against over-splitting. | Medium if module size risks are forgotten. |
| `Docs/archive/admin-audits/GENERATED_VENDOR_EXCLUSION_REVIEW.md` | ARCHIVE | Move later to admin audits | Completed generated/vendor exclusion review. | Low. |
| `Docs/GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md` | MERGE INTO SUMMARY | Merge decision into history, then archive | Foundational Tauri/WebView2 decision; too long for daily onboarding. | Medium unless decision rationale is preserved. |
| `Docs/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | KEEP AS SOURCE OF TRUTH | Keep | Read vs mutation route safety matrix. | High. |
| `Docs/archive/admin-audits/LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed route-count sync audit. | Low. |
| `Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | KEEP AS SOURCE OF TRUTH | Keep | Complete route ownership map. | High. |
| `Docs/LOG_ARTIFACT_CATALOG.md` | KEEP AS SOURCE OF TRUTH | Keep | Runtime artifact and log ownership map. | High. |
| `Docs/archive/admin-audits/MARKDOWN_LINK_FILE_EXISTENCE_SWEEP.md` | ARCHIVE | Move later to admin audits | Completed file-existence sweep. | Low. |
| `Docs/archive/completed-checklists/NETWORK_MODE_CHECKLIST.md` | ARCHIVE | Move later to archive | Completed network mode implementation archive. | Low. |
| `Docs/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md` | KEEP AS SOURCE OF TRUTH | Keep | Current read-only WebView Network scope. | High. |
| `Docs/NETWORK_READ_ONLY_PARITY_AUDIT.md` | MERGE INTO SUMMARY | Merge key gaps, then archive | Useful gaps, but not the primary current source. | Medium if coordinator/worker gaps are lost. |
| `Docs/archive/admin-audits/NETWORK_READONLY_WORDING_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed wording audit. | Low. |
| `Docs/NETWORK_UX_IMPROVEMENTS.md` | NEEDS HUMAN REVIEW | Keep until product decision | Planned network UX improvements; mutation must remain disabled. | Medium. |
| `Docs/NO_TOUCH_BOUNDARY_REGISTER.md` | KEEP AS SOURCE OF TRUTH | Keep | High-risk boundaries and gates. | Critical. |
| `Docs/archive/admin-audits/OPERATOR_COPY_CONSISTENCY_REVIEW.md` | ARCHIVE | Move later to admin audits | Completed copy review; terminology guide remains source. | Low. |
| `Docs/OPERATOR_GLOSSARY.md` | KEEP AS SOURCE OF TRUTH | Keep | Operator vocabulary source. | Medium. |
| `Docs/PACKAGING_DEPENDENCY_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Bundled/external dependency inventory. | High. |
| `Docs/PACKAGING_MANIFEST_REVIEW.md` | MERGE INTO SUMMARY | Merge unresolved packaging concerns, then archive | Gap report; useful until release manifest choices are confirmed. | Medium. |
| `Docs/archive/admin-audits/PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md` | ARCHIVE | Move later to admin audits | Completed freshness review. | Low. |
| `Docs/PENDING_PUBLISH_FIXTURE_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Pending-publish fixture and coverage reference. | High. |
| `Docs/Pipeline/NEW_PC_CHECKLIST_MediaPipelineRemuxEncodeAIO.md` | KEEP AS SOURCE OF TRUTH | Keep | New machine setup checklist. | Medium. |
| `Docs/Pipeline/README_MediaPipelineRemuxEncodeAIO_Deployment.md` | KEEP AS SOURCE OF TRUTH | Keep | Deployment and setup validation notes. | Medium. |
| `Docs/POWERSHELL_HOST_EXPECTATIONS.md` | KEEP AS SOURCE OF TRUTH | Keep | Bundled PS7 host rules. | High. |
| `Docs/archive/admin-audits/POWERSHELL_HOST_WORDING_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed wording audit. | Low. |
| `Docs/README_MediaPipelineRemuxEncodeAIO.md` | KEEP AS SOURCE OF TRUTH | Keep | Main bundle README. | High. |
| `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md` | NEEDS HUMAN REVIEW | Keep until template gaps closed | Identifies gaps in validation template. | Medium. |
| `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` | KEEP AS SOURCE OF TRUTH | Keep | Copyable real-media evidence template. | High. |
| `Docs/RealMediaValidationRuns/README.md` | KEEP AS SOURCE OF TRUTH | Keep | Generated validation worksheet folder rules. | Medium. |
| `Docs/RELEASE_PACKAGE_ADMIN_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Release package inclusion/exclusion expectations. | High. |
| `Docs/RELEASE_SELF_TEST_LAYOUT_AUDIT.md` | MERGE INTO SUMMARY | Merge important self-test gaps, then archive | One-off layout audit; useful release-gate context. | Medium. |
| `Docs/REMEDIATION_CHANGELOG.md` | KEEP AS SOURCE OF TRUTH | Keep, but do not use as onboarding entry | Full remediation history; very large and hard to navigate. | High for forensic history, low for daily planning. |
| `Docs/archive/admin-audits/RENAME_DOCS_FRESHNESS_REVIEW.md` | ARCHIVE | Move later to admin audits | Completed freshness review. | Low. |
| `Docs/RENAME_SAFETY_TEST_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Rename tests and fixture coverage. | High. |
| `Docs/RENAME_TOOL_EDGE_CASE_CATALOG.md` | KEEP AS SOURCE OF TRUTH | Keep | Rename behavior examples and edge cases. | High. |
| `Docs/ROOT_SCRIPT_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Root script purpose and safety classification. | High. |
| `Docs/RUNTIME_ARTIFACT_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Runtime state artifacts and safe-delete rules. | High. |
| `Docs/archive/admin-audits/RUNTIME_ARTIFACT_SORTING_NOTES.md` | ARCHIVE | Move later to admin audits | Completed sort notes. | Low. |
| `Docs/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md` | KEEP AS SOURCE OF TRUTH | Keep | Sample validation schema contract. | High. |
| `Docs/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md` | KEEP AS SOURCE OF TRUTH | Keep | Operator guide for sample validation records. | Medium. |
| `Docs/archive/admin-audits/SCHEDULE_STALE_READONLY_WORDING_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed wording audit. | Low. |
| `Docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md` | KEEP AS SOURCE OF TRUTH | Keep | Structured settings coverage and raw-key gaps. | High. |
| `Docs/SETTINGS_KEY_OWNERSHIP_MAP.md` | KEEP AS SOURCE OF TRUTH | Keep | Settings ownership and risk tiers. | High. |
| `Docs/SETTINGS_RAW_KEY_TRIAGE.md` | MERGE INTO SUMMARY | Merge unresolved raw-key risks, then archive | Specific raw-key triage; may be superseded by coverage matrix. | Medium. |
| `Docs/archive/admin-audits/STALE_DOCS_TODO_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed stale docs/TODO audit. | Low. |
| `Docs/archive/admin-audits/STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md` | ARCHIVE | Move later to admin audits | Completed addendum. | Low. |
| `Docs/archive/admin-audits/STALE_VERSION_LABEL_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed stale version audit; current risks moved to active checklist. | Low. |
| `Docs/STATE_FILE_SCHEMA_REFERENCE.md` | KEEP AS SOURCE OF TRUTH | Keep | State file schema contracts. | Critical. |
| `Docs/TAURI_ASSET_GATE_FRAGMENT_AUDIT.md` | MERGE INTO SUMMARY | Merge gate expectations, then archive | One-off asset gate audit. | Medium. |
| `Docs/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md` | KEEP AS SOURCE OF TRUTH | Keep | Backend lifecycle ownership and production requirements. | High. |
| `Docs/archive/admin-audits/TAURI_DAILY_DRIVER_WORDING_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed wording audit. | Low. |
| `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md` | KEEP AS SOURCE OF TRUTH | Keep | Current daily-use parity matrix and gaps. | High. |
| `Docs/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md` | MERGE INTO SUMMARY | Merge durable direction, then archive later | Original transition groundwork; superseded by current plan but useful history. | Medium. |
| `Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md` | KEEP AS SOURCE OF TRUTH | Keep | Preferred vocabulary and avoided terms. | Medium. |
| `Docs/TEST_COVERAGE_MATRIX.md` | KEEP AS SOURCE OF TRUTH | Keep | WebView page test coverage matrix. | High. |
| `Docs/TEST_SUITE_SUBSYSTEM_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Targeted test commands by subsystem. | High. |
| `Docs/TLDR.md` | KEEP AS SOURCE OF TRUTH | Keep and align with current state | Operator quick reference. | High. |
| `Docs/archive/completed-checklists/UI_CHECKLIST_2.md` | ARCHIVE | Move later to archive | Completed UI archive. | Low. |
| `Docs/archive/completed-checklists/UI_CHECKLIST_3.md` | ARCHIVE | Move later to archive | Completed UI archive. | Low. |
| `Docs/archive/completed-checklists/UI_CHECKLIST.md` | ARCHIVE | Move later to archive | Completed UI archive. | Low. |
| `Docs/UI_IMPROVEMENT_CHECKLIST.md` | NEEDS HUMAN REVIEW | Keep until product triage | Future UI ideas; may contain still-wanted improvements. | Medium. |
| `Docs/archive/historical-reviews/V4_MIGRATION_NOTES.md` | ARCHIVE | Move later to historical reviews | Historical V3/V4 curation context. | Low. |
| `Docs/archive/completed-checklists/V5_HOUSEKEEPING_BEFORE_TRANSITION_RESUME.md` | ARCHIVE | Move later to archive | Completed 2026-05-14 housekeeping. | Low. |
| `Docs/V5_MIGRATION_RISK_REGISTER.md` | KEEP AS SOURCE OF TRUTH | Keep | Active migration risk register. | Critical. |
| `Docs/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md` | MERGE INTO SUMMARY | Merge architectural warnings, then archive | Useful cohesion/fragmentation review. | Medium. |
| `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` | KEEP AS SOURCE OF TRUTH | Keep | Real-media validation gate before daily-driver claims. | Critical. |
| `Docs/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md` | KEEP AS SOURCE OF TRUTH | Keep | Evidence artifact design and boundaries. | High. |
| `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md` | KEEP AS SOURCE OF TRUTH | Keep | Active transition plan and migration health checkpoint. | Critical. |
| `Docs/V5_TRANSITION_STATUS_BOARD.md` | MERGE INTO SUMMARY | Merge into current state, then archive later | Useful status board, but partly superseded by consolidated current state. | Medium. |
| `Docs/VALIDATION_LADDER_RUNBOOK.md` | KEEP AS SOURCE OF TRUTH | Keep | Authoritative validation ladder. | Critical. |
| `Docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md` | KEEP AS SOURCE OF TRUTH | Keep | Frontend mutation boundary audit. | High. |
| `Docs/archive/admin-audits/WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed dead-reference audit. | Low. |
| `Docs/WEBVIEW_DOM_ID_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | DOM ID ownership inventory, though noted partial. | Medium. |
| `Docs/archive/admin-audits/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed namespace audit. | Low. |
| `Docs/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` | KEEP AS SOURCE OF TRUTH | Keep | Current JS global export inventory and bootstrap boundary. | Medium. |
| `Docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md` | KEEP AS SOURCE OF TRUTH | Keep | Manual operator validation script for all pages. | High. |
| `Docs/archive/admin-audits/WEBVIEW_OPERATOR_COPY_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed copy audit; terminology guide is active source. | Low. |
| `Docs/WEBVIEW_OPERATOR_ERROR_MESSAGE_REVIEW.md` | MERGE INTO SUMMARY | Merge actionable wording gaps, then archive | Useful message classes; one-off review form. | Medium. |
| `Docs/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md` | KEEP AS SOURCE OF TRUTH | Keep | Scope-preview operator guidance for backend-owned actions. | High. |
| `Docs/archive/admin-audits/WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md` | ARCHIVE | Move later to admin audits | Completed smoke wrapper boundary text audit. | Low. |
| `Docs/WEBVIEW_SMOKE_RESULT_TEMPLATE.md` | KEEP AS SOURCE OF TRUTH | Keep | Copyable smoke result template. | Medium. |
| `Docs/WEBVIEW_SMOKE_TEST_CATALOG.md` | KEEP AS SOURCE OF TRUTH | Keep | Current WebView smoke catalog. | High. |

## Minimum Useful Documentation Set Going Forward

### Source Of Truth

- `Docs/CURRENT_PROJECT_STATE.md`
- `Docs/ACTIVE_FIX_CHECKLIST.md`
- `Docs/DECISIONS_AND_HISTORY.md`
- `Docs/ARCHIVED_MD_INDEX.md`
- `Docs/DOCS_INDEX.md`
- `Docs/TLDR.md`
- `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs/V5_MIGRATION_RISK_REGISTER.md`
- `Docs/NO_TOUCH_BOUNDARY_REGISTER.md`
- `Docs/VALIDATION_LADDER_RUNBOOK.md`
- `Docs/TEST_COVERAGE_MATRIX.md`
- `Docs/TEST_SUITE_SUBSYSTEM_INVENTORY.md`
- `Docs/STATE_FILE_SCHEMA_REFERENCE.md`
- `Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `Docs/COMMAND_OWNERSHIP_MATRIX.md`
- `Docs/BROWSER_SMOKE_TEST_RUNBOOK.md`
- `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`

### Merge Into Summaries

- GUI framework choice, V5 groundwork, transition status, module ownership, command history consistency, settings raw-key triage, and changelog navigation concerns should be summarized into `DECISIONS_AND_HISTORY.md` and `ACTIVE_FIX_CHECKLIST.md`.
- Administrative audit findings should be summarized into `ARCHIVED_MD_INDEX.md`.

### Archive Later

- Completed Claude handoffs.
- Completed UI/control cleanup checklists.
- Completed wording, sync, sort, dead-reference, and freshness audits.
- Historical V3/V4 migration notes.

### Needs Human Review Before Archiving

- The three `CLAUDE_HANDOFF_TRANSITION_SUPPORT_*` files still marked active in `DOCS_INDEX.md`.
- `Docs/NETWORK_UX_IMPROVEMENTS.md`.
- `Docs/UI_IMPROVEMENT_CHECKLIST.md`.
- `Docs/DesktopApp/docs/FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md`.
- `Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md`.
- `Docs/CHANGELOG_NAVIGATION_PROPOSAL.md`.

## Risks Of Consolidation

- The large `REMEDIATION_CHANGELOG.md` is too valuable for forensic history to delete, but too large to use as onboarding. Keep it and route future agents to the consolidated current-state docs first.
- Several "audit" documents are accurate snapshots, not living contracts. Moving them without an index would make it hard to understand why a decision was made.
- Some Claude handoff files may still contain tasks that were never formally reconciled. They should be archived only after checking against `archive/completed-checklists/ADMIN_TASK_COMPLETION_BOARD.md`, `archive/old-ai-directives/CLAUDE_HANDOFF_STATUS_RECONCILIATION.md`, and current code/tests.
- Generated vendor docs under `node_modules` should not be treated as project documentation; deleting them manually is not recommended inside this doc cleanup.

## Destructive Actions Not Performed

- No Markdown files were deleted.
- No Markdown files were moved.
- No archive folder was created yet.
- No generated vendor files were pruned.

## Recommended Next Cleanup Step

After human approval, create `Docs/archive/old-ai-directives/`, `Docs/archive/admin-audits/`, and `Docs/archive/historical-reviews/`, then move only files classified as **ARCHIVE**. Keep this report and `ARCHIVED_MD_INDEX.md` at `Docs/` root so future agents can recover context without scanning every old file.
