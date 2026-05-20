# Housekeeping Audit Report

Audit date: 2026-05-15

Repository audited: `C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Scope: full V5 application folder, excluding destructive cleanup. This report inventories clutter, source-of-truth documents, generated artifacts, oversized files, duplicate/legacy planning material, smoke tests, config/tooling surfaces, and cleanup opportunities. No files were deleted, moved, or behavior-modified during this audit.

Execution update after operator approval: completed/archive-classified Markdown files were moved into `Docs\archive\`, old config backups were moved into `Pipeline\ConfigBackups\archive\2026-05-15\`, old run logs were moved into `DesktopApp\RunLogs\archive\2026-05-15\`, and project-authored Python cache folders outside bundled/runtime/vendor trees were removed. Source code, live config, runtime state, bundled tools, bundled runtimes, Tauri build/dependency folders, and media pipeline behavior were not changed.

Search ergonomics update: a root `.rgignore` was added so routine `rg` searches skip bundled runtimes, generated Tauri dependency/build folders, archived logs/backups, Python caches, and local media workspaces by default. Use `rg -u` when intentionally auditing generated/vendor/package surfaces.

Tauri build-output update: generated Rust build output at `DesktopApp\tauri_shell\src-tauri\target\` was pruned after confirming no V5 process was running. `node_modules\` and `src-tauri\gen\` were kept because they are small and support immediate preview work. A future Tauri build will recreate `target\`.

## Executive Summary

The V5 folder is workable, but it is heavy and noisy for future AI/code work. The main maintainability drag is not one broken subsystem; it is the combination of generated artifacts, accumulated logs, many historical Markdown plans, giant remediation logs, large smoke/test files, and bundled runtimes/tools living beside project-authored code.

The safest immediate housekeeping is documentation archiving, log/cache pruning, and clearer onboarding boundaries. The highest-risk cleanup is anything that touches bundled runtimes/tools, live config/state, pending publish artifacts, FFmpeg/media policy, Tk fallback, or Tauri backend lifecycle.

Current measured snapshot:

| Area | Observed count / size | Notes |
| --- | ---: | --- |
| Total files from `rg --files` | 10,566 | Includes generated/vendor/runtime files. |
| Top-level source folders | 5 | `.claude`, `DesktopApp`, `Docs`, `Pipeline`, `SmokeTests`. |
| `DesktopApp` | about 5.8 GB | Dominated by bundled Python runtime, Tauri build artifacts, `node_modules`, and logs. |
| `Pipeline` | about 1.2 GB | Dominated by bundled tools and PowerShell 7 runtime. |
| Markdown files | 130 | 125 under `Docs`, 1 under `SmokeTests`, 1 Tauri README, 3 vendor `node_modules` docs. |
| Logs excluding bundled/vendor trees | 1,026 files, about 23 MB | Mostly `DesktopApp\RunLogs`. |
| Python bytecode excluding bundled/vendor trees | 488 `.pyc` | Regenerable cache clutter. |
| Config backups | 34 backup-ish PSD1 files | Keep until explicit retention policy is approved. |
| Smoke wrappers | 26 under `SmokeTests` | Dedicated folder is now in place and documented. |

## 1. Current App Structure Summary

| Path | Apparent role | Housekeeping notes |
| --- | --- | --- |
| `.claude\` | Local Claude/assistant metadata. | Do not include in release packages. Safe to ignore or archive after human approval. |
| `DesktopApp\` | Python Tk desktop app, local API backend, WebView static app, Tauri shell, bundled Python runtime, tests, run logs. | Active. Contains both source and generated/runtime payloads, so searches should exclude generated subtrees. |
| `DesktopApp\mediapipeline_desktop_app\` | Main Python package for app services, local API routes, contracts, views, network modules, and WebView assets. | Active. Do not bulk refactor for housekeeping. |
| `DesktopApp\mediapipeline_desktop_app\ui_web\static\` | WebView frontend assets and page modules. | Active. Several large JS files are known cohesion concerns, but not cleanup targets without a feature trigger. |
| `DesktopApp\tauri_shell\` | Tauri/WebView2 preview shell. | Active preview. `node_modules`, `src-tauri\target`, and `src-tauri\gen` are generated/build artifacts. |
| `DesktopApp\Runtime\Python\` | Bundled Python runtime. | Do not touch during housekeeping. Exclude from code searches unless auditing packaging. |
| `DesktopApp\RunLogs\` | Runtime stdout/stderr/log artifacts. | Safe cleanup candidate only after app is closed and retention policy is approved. |
| `Pipeline\` | PowerShell pipeline engine, modules, config, tests, bundled tools/runtime. | Active production-sensitive engine. Do not delete or reorganize without targeted validation. |
| `Pipeline\Modules\` | PowerShell modules for naming, routing, subtitle/audio handling, config schema, probe, pending transactions, native tools. | Active. No housekeeping moves recommended. |
| `Pipeline\Tests\` | PowerShell reliability and regression tests. | Active. One file is very large but it is a release-safety asset. |
| `Pipeline\Tools\` | Bundled FFmpeg/MKVToolNix/PgsToSrt-style tool payloads. | Do not touch. |
| `Pipeline\PowerShell-7.6.0-win-x64\` | Bundled PowerShell 7 runtime. | Do not touch. |
| `Docs\` | Current docs plus many historical audits, Claude handoffs, checklists, proposals, and generated admin reviews. | Highest-value cleanup area: archive completed/historical docs while preserving index. |
| `SmokeTests\` | Dedicated folder for root smoke wrappers. | Good current organization. Keep wrappers here. |
| Root `.bat` and `.ps1` scripts | Launchers, environment verifier, release builder, release self-test, real-media worksheet helper. | Active. Keep visible at root because they are operator entry points. |

## 2. Clutter Inventory

### Generated, Temporary, Or Rebuildable

| Item | Evidence | Recommendation | Risk classification |
| --- | --- | --- | --- |
| `DesktopApp\RunLogs\` | 1,026 `.log` files, about 23 MB. | Archive or prune by date after confirming app/backend are stopped. Keep latest diagnostic evidence when investigating active bugs. | SAFE CLEANUP with process check. |
| `DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.log` | Runtime desktop app log, about 621 KB. | Rotate/archive after retaining recent failure evidence. | SAFE CLEANUP with process check. |
| Project-authored `__pycache__` folders | Found under `DesktopApp\mediapipeline_desktop_app`, `DesktopApp\tests`, and `Pipeline`. | Remove caches outside bundled runtime after tests/app are closed. | SAFE CLEANUP. |
| Project-authored `.pyc` files | 488 outside excluded vendor/runtime/build trees. | Remove with `__pycache__` cleanup. | SAFE CLEANUP. |
| `DesktopApp\tauri_shell\node_modules\` | Generated dependency tree, includes 3 vendor Markdown files. | Keep while actively developing unless install/rebuild path is confirmed. If pruned, validate `npm install` and Tauri checks. | REVIEW BEFORE CHANGE. |
| `DesktopApp\tauri_shell\src-tauri\target\` | Rust/Tauri build output. | Prune only if rebuild time is acceptable and Tauri toolchain is confirmed. | REVIEW BEFORE CHANGE. |
| `DesktopApp\tauri_shell\src-tauri\gen\` | Generated Tauri mobile/build metadata. | Prune only if Tauri regenerates it reliably. | REVIEW BEFORE CHANGE. |
| `DesktopApp\RunLogs\webview_*_localapi.pid` | Two stale-looking PID files. | Do not delete until no matching process is running. Add stale-PID check to cleanup script later. | REVIEW BEFORE CHANGE. |
| `*.lock` | One project-authored `.lock` outside excluded trees plus Cargo.lock. | `Cargo.lock` must stay. Any runtime lock must be checked against active process owner. | REVIEW BEFORE CHANGE. |

### Backups And Historical State

| Item | Evidence | Recommendation | Risk classification |
| --- | --- | --- | --- |
| `Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1` | 31 timestamped backups. | Keep latest N after operator approves retention policy. Move older backups to archive, not delete. | REVIEW BEFORE CHANGE. |
| `Pipeline\MediaPipeline_config_chatgpt.psd1.bak.*` | 3 older backup-extension variants. | Compare against current config or archive under config-backups. | REVIEW BEFORE CHANGE. |
| `Docs\REMEDIATION_CHANGELOG.md` | about 1.49 MB, large forensic history. | Keep, but add navigation/index later. Do not use as onboarding entry. | DO NOT TOUCH YET except non-destructive index. |
| Many completed audit/checklist Markdown files | Prior `Docs\MD_CLEANUP_AUDIT_REPORT.md` classifies completed docs. | Archive completed docs after approval into `Docs\archive\...`. | SAFE CLEANUP after approval. |

### Misplaced Or Potentially Confusing

| Item | Why it slows work | Recommendation | Risk classification |
| --- | --- | --- | --- |
| Historical V3/V4 docs in active docs tree | Can confuse future agents about current V5 state. | Archive historical docs or add stronger headers that they are reference-only. | REVIEW BEFORE CHANGE. |
| Active and completed Claude handoff files mixed together | Future AI agents may treat stale task lists as current orders. | Reconcile three still-marked-active Claude files, then archive closed handoffs. | REVIEW BEFORE CHANGE. |
| Vendor Markdown under `node_modules` | Inflates Markdown searches and doc counts. | Exclude from doc inventories; do not treat as project docs. | SAFE CLEANUP in docs; REVIEW if pruning `node_modules`. |
| Huge JS/test files | Slow review and increase cognitive load. | Do not split just for housekeeping; split only when feature work creates a cohesive extraction. | DO NOT TOUCH YET. |

## 3. Efficiency Problems

| Problem | Evidence | Impact | Cleanup direction |
| --- | --- | --- | --- |
| Searches traverse generated/runtime trees unless carefully excluded. | 10,566 files; runtime/tool/vendor/build trees dominate. | AI agents waste time reading non-project code. | Add or maintain `.rgignore` later; current `.gitignore` already excludes many generated paths. |
| Markdown set is too large for onboarding. | 130 Markdown files; many are completed audits/handoffs. | Future agents may follow stale plans. | Use `CURRENT_PROJECT_STATE.md`, `ACTIVE_FIX_CHECKLIST.md`, and `DOCS_INDEX.md` as entry points; archive completed docs. |
| Runtime logs pollute grep results. | 1,026 logs; previous searches returned log hits unless `RunLogs` excluded. | False positives and slow audits. | Prune/archive old logs and add explicit search exclude guidance. |
| Large WebView files remain hard to scan. | `settingsView.js` 4,169 lines, `index.html` 3,878 lines, `completedView.js` 3,645 lines. | Harder to review UI changes safely. | Feature-triggered cohesive extraction only; avoid pass-through micro modules. |
| Large tests are valuable but hard to maintain. | `test_application_facade.py` 7,617 lines; PowerShell reliability regression 6,018 lines. | Test failures are harder to localize. | Split by behavior only when tests are touched, not as blind cleanup. |
| Config backups are flat in `Pipeline\`. | 34 backup-ish PSD1 files. | Makes active config harder to spot. | Introduce approved backup retention/archive folder. |
| Root scripts are numerous but mostly intentional. | Root contains launchers, release checks, and worksheet helper. | New users may not know which to run. | Keep root scripts visible; rely on `Docs\ROOT_SCRIPT_INVENTORY.md` and `Docs\DOCS_INDEX.md`. |

## 4. Risk Classification

### SAFE CLEANUP

These are low-risk if performed with the app/backend stopped and after a quick validation run:

- Archive completed Markdown files already classified as `ARCHIVE` in `Docs\MD_CLEANUP_AUDIT_REPORT.md`.
- Keep active docs at `Docs\` root and move completed admin/AI/historical docs to `Docs\archive\old-ai-directives\`, `Docs\archive\admin-audits\`, and `Docs\archive\historical-reviews\`.
- Remove project-authored `__pycache__` and `.pyc` outside `DesktopApp\Runtime`, `node_modules`, `src-tauri\target`, `Pipeline\Tools`, and `Pipeline\PowerShell-7.6.0-win-x64`.
- Archive old `DesktopApp\RunLogs` entries by date after retaining recent diagnostics.
- Keep smoke wrappers in `SmokeTests\` and update docs if new wrappers are added.
- Add an `AI_AGENT_START_HERE.md` or keep `Docs\CURRENT_PROJECT_STATE.md` clearly linked from `Docs\DOCS_INDEX.md`.

### REVIEW BEFORE CHANGE

These probably improve cleanliness but can affect local developer workflow, diagnostics, or reproducibility:

- Prune `DesktopApp\tauri_shell\node_modules`.
- Prune `DesktopApp\tauri_shell\src-tauri\target` or `src-tauri\gen`.
- Delete stale `.pid` or runtime `.lock` files.
- Move or prune old `Pipeline\MediaPipeline_config_chatgpt*.backup*` files.
- Split large JS modules or large tests.
- Archive `CLAUDE_HANDOFF_TRANSITION_SUPPORT_*` files still listed as active in `DOCS_INDEX.md`.
- Rename or relocate V3/V4 historical docs.
- Add `.rgignore` if there is concern about hiding useful search results.

### DO NOT TOUCH YET

These are production-sensitive or migration-sensitive:

- V4 backup folder outside this repo.
- `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` and Tk fallback behavior.
- `Pipeline\MediaPipeline_chatgpt.ps1` behavior and module import sequence.
- FFmpeg/ffprobe command generation, stream mapping, subtitle conversion, audio routing, remux/encode policy.
- Pending publish manifests, drain logic, source/scratch/output movement, cleanup, retry, and recovery state.
- `Pipeline\Tools\` and `Pipeline\PowerShell-7.6.0-win-x64\`.
- `DesktopApp\Runtime\Python\`.
- Live config: `Pipeline\MediaPipeline_config_chatgpt.psd1`.
- Runtime state/manifest/cache files that may describe active jobs or pending publishes.
- Command journal, duplicate command guards, strict JSON route handling, close-readiness, and backend lifecycle safety checks.

## 5. Active Source-Of-Truth Files

Future AI agents should read these first, in this order:

| Priority | File | Why |
| ---: | --- | --- |
| 1 | `Docs\CURRENT_PROJECT_STATE.md` | Current architecture, launchers, migration state, no-touch areas, obsolete instruction warnings. |
| 2 | `Docs\ACTIVE_FIX_CHECKLIST.md` | Active unresolved work only. |
| 3 | `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md` | Current transition plan and migration health checkpoint. |
| 4 | `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md` | Tk vs WebView parity status and gaps. |
| 5 | `Docs\NO_TOUCH_BOUNDARY_REGISTER.md` | High-risk boundaries and validation gates. |
| 6 | `Docs\VALIDATION_LADDER_RUNBOOK.md` | Which tests/checks to run per change type. |
| 7 | `Docs\TEST_COVERAGE_MATRIX.md` | WebView test coverage by page. |
| 8 | `Docs\TEST_SUITE_SUBSYSTEM_INVENTORY.md` | Targeted test commands by subsystem. |
| 9 | `Docs\DOCS_INDEX.md` | Broad doc index after the agent knows current state. |
| 10 | `Docs\TLDR.md` | Operator quick reference. |

Recommended optional additions:

- `AI_AGENT_START_HERE.md`: root-level one-page redirect to the source-of-truth docs and safety rules.
- `ARCHITECTURE.md`: thin index that points to existing architecture docs instead of duplicating them.
- `TESTING.md`: thin index that points to validation ladder, coverage matrix, smoke catalog, and subsystem inventory.
- `CHANGELOG.md`: thin index/TOC for `Docs\REMEDIATION_CHANGELOG.md` if the giant changelog remains intact.

## 6. Markdown / Documentation Cleanup

Markdown inventory snapshot: 130 files total.

| Category | Files | Classification |
| --- | --- | --- |
| Vendor/generated Markdown | `DesktopApp\tauri_shell\node_modules\@tauri-apps\cli-win32-x64-msvc\README.md`; `DesktopApp\tauri_shell\node_modules\@tauri-apps\cli\CHANGELOG.md`; `DesktopApp\tauri_shell\node_modules\@tauri-apps\cli\README.md` | DELETE CANDIDATE only if pruning `node_modules`; otherwise ignore. |
| Core current-state docs | `Docs\CURRENT_PROJECT_STATE.md`; `Docs\ACTIVE_FIX_CHECKLIST.md`; `Docs\DECISIONS_AND_HISTORY.md`; `Docs\ARCHIVED_MD_INDEX.md`; `Docs\DOCS_INDEX.md`; `Docs\TLDR.md` | KEEP AS SOURCE OF TRUTH. |
| Transition architecture docs | `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`; `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`; `Docs\V5_MIGRATION_RISK_REGISTER.md`; `Docs\TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`; `Docs\TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md`; `Docs\GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md` | Keep current plan/risk/boundary/parity as source of truth; merge/archive older groundwork and framework decision after rationale is preserved. |
| Safety and contract docs | `Docs\NO_TOUCH_BOUNDARY_REGISTER.md`; `Docs\STATE_FILE_SCHEMA_REFERENCE.md`; `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`; `Docs\LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`; `Docs\API_ROUTE_INVENTORY.md`; `Docs\COMMAND_OWNERSHIP_MATRIX.md`; `Docs\WEBVIEW_APIPOST_MUTATION_REVIEW.md`; `Docs\COMMAND_HISTORY_CONSISTENCY_AUDIT.md` | Mostly KEEP AS SOURCE OF TRUTH; command history audit can be merged later. |
| Validation docs | `Docs\VALIDATION_LADDER_RUNBOOK.md`; `Docs\TEST_COVERAGE_MATRIX.md`; `Docs\TEST_SUITE_SUBSYSTEM_INVENTORY.md`; `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`; `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`; `Docs\SMOKE_TEST_INVENTORY.md`; `Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`; `Docs\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md`; `Docs\BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`; `Docs\WEBVIEW_SMOKE_RESULT_TEMPLATE.md`; `SmokeTests\README.md` | KEEP AS SOURCE OF TRUTH. |
| Real-media validation docs | `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`; `Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`; `Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md`; `Docs\RealMediaValidationRuns\README.md`; `Docs\V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md`; `Docs\SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`; `Docs\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md` | Keep playbook/template/artifact/schema docs; review the template review once gaps are closed. |
| Operator docs | `Docs\README_MediaPipelineRemuxEncodeAIO.md`; `Docs\DesktopApp\README_MediaPipelineRemuxEncodeAIO_DesktopApp.md`; `Docs\DesktopApp\docs\README.md`; `Docs\Pipeline\README_MediaPipelineRemuxEncodeAIO_Deployment.md`; `Docs\Pipeline\NEW_PC_CHECKLIST_MediaPipelineRemuxEncodeAIO.md`; `Docs\OPERATOR_GLOSSARY.md`; `Docs\TERMINOLOGY_CONSISTENCY_GUIDE.md`; `Docs\FAILURE_TRIAGE_WORKSHEET.md`; `Docs\WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`; `Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md`; `DesktopApp\tauri_shell\README.md` | KEEP AS SOURCE OF TRUTH, but reconcile old V3/V4 wording where still present. |
| Runtime/log/package docs | `Docs\LOG_ARTIFACT_CATALOG.md`; `Docs\RUNTIME_ARTIFACT_INVENTORY.md`; `Docs\archive\admin-audits\RUNTIME_ARTIFACT_SORTING_NOTES.md`; `Docs\PACKAGING_DEPENDENCY_INVENTORY.md`; `Docs\PACKAGING_MANIFEST_REVIEW.md`; `Docs\RELEASE_PACKAGE_ADMIN_INVENTORY.md`; `Docs\RELEASE_SELF_TEST_LAYOUT_AUDIT.md`; `Docs\ROOT_SCRIPT_INVENTORY.md`; `Docs\archive\admin-audits\GENERATED_VENDOR_EXCLUSION_REVIEW.md` | Keep inventories; archive completed reviews/sort notes after unresolved package gaps are merged. |
| Settings/config docs | `Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md`; `Docs\SETTINGS_KEY_OWNERSHIP_MAP.md`; `Docs\SETTINGS_RAW_KEY_TRIAGE.md`; `Docs\CONFIG_KEY_GLOSSARY_DRAFT.md` | Keep maps; promote/merge glossary and raw-key triage later. |
| Rename/pending/network docs | `Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md`; `Docs\RENAME_SAFETY_TEST_INVENTORY.md`; `Docs\archive\admin-audits\RENAME_DOCS_FRESHNESS_REVIEW.md`; `Docs\PENDING_PUBLISH_FIXTURE_INVENTORY.md`; `Docs\archive\admin-audits\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md`; `Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`; `Docs\archive\completed-checklists\NETWORK_MODE_CHECKLIST.md`; `Docs\NETWORK_READ_ONLY_PARITY_AUDIT.md`; `Docs\archive\admin-audits\NETWORK_READONLY_WORDING_AUDIT.md`; `Docs\NETWORK_UX_IMPROVEMENTS.md` | Keep edge/test/read-only docs; archive completed freshness/wording/checklist docs; review network UX before acting. |
| Diagnostics docs | `Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`; `Docs\DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`; `Docs\archive\admin-audits\DIAGNOSTICS_TARGET_SYNC_AUDIT.md` | Keep first two; archive completed sync audit. |
| DOM/frontend docs | `Docs\WEBVIEW_DOM_ID_INVENTORY.md`; `Docs\archive\admin-audits\WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md`; `Docs\archive\admin-audits\WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`; `Docs\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`; `Docs\archive\admin-audits\WEBVIEW_OPERATOR_COPY_AUDIT.md`; `Docs\WEBVIEW_OPERATOR_ERROR_MESSAGE_REVIEW.md`; `Docs\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md`; `Docs\archive\admin-audits\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md`; `Docs\FRONTEND_MODULE_SIZE_COHESION_REPORT.md`; `Docs\TAURI_ASSET_GATE_FRAGMENT_AUDIT.md` | Keep inventories/guides/cohesion report; archive completed audits after index preservation. |
| Completed UI/control/checklists | `Docs\archive\completed-checklists\UI_CHECKLIST.md`; `Docs\archive\completed-checklists\UI_CHECKLIST_2.md`; `Docs\archive\completed-checklists\UI_CHECKLIST_3.md`; `Docs\archive\completed-checklists\CONTROL_SURFACE_HARDENING_CHECKLIST.md`; `Docs\archive\completed-checklists\CODE_CLEANUP_CHECKLIST.md`; `Docs\DEPLOYABILITY_CHECKLIST.md`; `Docs\UI_IMPROVEMENT_CHECKLIST.md` | Archive completed checklists; review UI improvement checklist for remaining product ideas. |
| Claude/admin handoffs | `Docs\archive\old-ai-directives\CLAUDE_HANDOFF_20_TASK_BACKLOG.md`; `Docs\archive\old-ai-directives\CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md`; `Docs\archive\old-ai-directives\CLAUDE_HANDOFF_CLEANUP_REVIEW_SORTING_BACKLOG.md`; `Docs\archive\old-ai-directives\CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md`; `Docs\archive\old-ai-directives\CLAUDE_HANDOFF_ROUND3_COMPLETION_SUMMARY.md`; `Docs\archive\old-ai-directives\CLAUDE_HANDOFF_STATUS_RECONCILIATION.md`; `Docs\CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md`; `Docs\CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md`; `Docs\CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND4.md`; `Docs\archive\completed-checklists\ADMIN_TASK_COMPLETION_BOARD.md` | Archive completed handoffs; human-review the three transition-support docs still marked active. |
| Stale/version/doc cleanup audits | `Docs\MD_CLEANUP_AUDIT_REPORT.md`; `Docs\DOCS_DEAD_MARKDOWN_AUDIT.md`; `Docs\DOCS_FOLDER_SORTING_PROPOSAL.md`; `Docs\archive\admin-audits\MARKDOWN_LINK_FILE_EXISTENCE_SWEEP.md`; `Docs\archive\completed-checklists\CHECKLIST_ARCHIVE_REVIEW.md`; `Docs\archive\admin-audits\STALE_DOCS_TODO_AUDIT.md`; `Docs\archive\admin-audits\STALE_VERSION_LABEL_AUDIT.md`; `Docs\archive\admin-audits\STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md`; `Docs\CHANGELOG_NAVIGATION_HEALTH_REVIEW.md`; `Docs\CHANGELOG_NAVIGATION_PROPOSAL.md` | Keep latest cleanup report and proposal until this report supersedes pieces; archive completed audits. |
| Historical migration docs | `Docs\archive\historical-reviews\V4_MIGRATION_NOTES.md`; `Docs\archive\historical-reviews\V3_RELIABILITY_NOTES.md`; `Docs\archive\completed-checklists\V5_HOUSEKEEPING_BEFORE_TRANSITION_RESUME.md`; `Docs\V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md`; `Docs\V5_TRANSITION_STATUS_BOARD.md`; `Docs\DesktopApp\docs\FEATURE_OUTLINE_AND_SOFTWARE_COMPARISON.md` | Archive historical docs after preserving durable decisions; review feature outline/status board for active content. |
| New housekeeping outputs | `HOUSEKEEPING_AUDIT_REPORT.md`; `HOUSEKEEPING_EXECUTION_CHECKLIST.md` | KEEP during housekeeping effort. |

Minimum final documentation layout:

- Keep at root of `Docs\`: current state, active checklist, decisions/history, docs index, TLDR, transition plan, parity matrix, migration risk register, no-touch register, validation ladder, test matrices, route/command ownership maps, state schema, smoke inventory.
- Move completed/historical docs after approval to:
  - `Docs\archive\old-ai-directives\`
  - `Docs\archive\admin-audits\`
  - `Docs\archive\historical-reviews\`
  - `Docs\archive\completed-checklists\`

## 7. Code Cleanup Opportunities

These are recommendations only, not changes to make during housekeeping without a feature/testing trigger.

| Area | Evidence | Recommendation | Risk |
| --- | --- | --- | --- |
| Large WebView modules | `settingsView.js` 4,169 lines; `completedView.js` 3,645; `launchView.js` 3,519; `pendingPublishView.js` 3,180. | Extract only cohesive, reusable pieces when actively modifying that page. Do not create thin pass-through modules just to reduce line count. | Medium. |
| Large test files | `test_application_facade.py` 7,617 lines; `test_network_persistence.py` 4,422; `test_controllers.py` 4,257. | Split only when tests are touched for real changes; preserve coverage and fixture behavior. | Medium. |
| Large PowerShell tests | `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` 6,018 lines. | Treat as release-safety asset; split only into test helper modules with exact parity validation. | High. |
| Main pipeline script | `Pipeline\MediaPipeline_chatgpt.ps1` 2,457 lines. | Do not housekeeping-refactor. Only extract when addressing a specific media-policy or orchestration risk. | High. |
| WebView `index.html` | 3,878 lines. | Later component/layout cleanup may help, but avoid changing DOM IDs unless smoke tests and DOM inventory are updated. | Medium. |
| Runtime logs in search scope | Logs appear in grep output when not excluded. | Add search commands in docs with `-g '!DesktopApp/RunLogs/**'`. Consider `.rgignore` later. | Low. |
| Duplicate generic names | Duplicate `README.md`, `diagnostics.py`, `index.html`, `__init__.py` are mostly legitimate by package/folder. | No action unless a duplicate is truly obsolete. | Low. |
| TODO/FIXME audit | Existing doc says zero code TODO/FIXME; quick grep mostly found docs/logs/vendor. | Keep this as a periodic audit, not an immediate cleanup. | Low. |

## 8. Test Cleanup Opportunities

| Area | Evidence | Recommendation | Risk |
| --- | --- | --- | --- |
| Smoke wrappers | 26 wrappers now under `SmokeTests\`; `Docs\SMOKE_TEST_INVENTORY.md` exists. | Keep in dedicated folder. Add future smoke wrappers there only. | Low. |
| Browser smokes skip behavior | Many tests intentionally `SkipTest` when Node/Chrome/Edge is unavailable. | Keep skip behavior; do not convert to hard failures unless environment is controlled. | Low. |
| Giant facade/network/controller tests | Very large tests are hard to navigate. | When touching related code, split by behavior family while keeping helper fixtures shared. | Medium. |
| Runtime fixture generation | Tests mostly generate temp state/config. | Preserve temp-only behavior; do not point tests at live source/output/scratch. | High. |
| PowerShell release reliability test | Large but release-critical. | Avoid pruning or reorganizing during housekeeping. | High. |
| Test cache artifacts | `DesktopApp\tests\__pycache__` and `.pyc`. | Safe to remove after tests stop. | Low. |

## 9. Config And Tooling Cleanup

| Item | Current state | Recommendation | Risk |
| --- | --- | --- | --- |
| `.gitignore` | Already excludes `__pycache__`, `.pyc`, Tauri `node_modules`, `target`, logs, RunLogs, runtime output, config backups, local media workspaces, generated reports, OS/editor noise, release copies. | Good baseline. Consider adding `.rgignore` with the same generated/runtime exclusions for faster audits. | Low. |
| Root launchers | Desktop app, Local API, Tauri preview, environment verify, release build/test, real-media worksheet helper. | Keep visible. Do not bury operator entry points. | Low. |
| Config backups | Many backups in `Pipeline\`. | Create retention/archive plan: keep latest 5-10 near active config, move older to `Pipeline\ConfigBackups\archive\` or `Docs\archive\housekeeping\...\config-backups-index.md`. | Medium. |
| Bundled PowerShell 7 | Present under `Pipeline\PowerShell-7.6.0-win-x64`. | Keep. Do not replace with system PS5 assumptions. | High. |
| Bundled Python runtime | Present under `DesktopApp\Runtime\Python`. | Keep. Do not prune caches inside runtime unless rebuilding package. | High. |
| Tauri dependencies | `node_modules`, Cargo target/gen present. | Decide whether V5 working tree keeps generated dev dependencies or relies on install/rebuild. | Medium. |
| No visible `.git` in folder | `.gitignore` exists but repo may not be a Git checkout at this folder. | If source control matters, initialize/confirm version control outside housekeeping. | Medium. |

## 10. Recommended Phased Cleanup Plan

### Phase H0 - Freeze And Safety Snapshot

- Goal: establish baseline before any cleanup moves.
- Files likely affected: none.
- Risk level: Low.
- Expected benefit: prevents accidental loss of diagnostics or active work.
- Validation:
  - Confirm app/backend/Tauri preview are stopped.
  - Run `.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke`.
  - Record current file counts and latest log timestamps.

### Phase H1 - Documentation Archive Pass

- Goal: reduce AI/doc clutter without deleting context.
- Files likely affected: `Docs\*.md`, `Docs\archive\...`.
- Risk level: Low to Medium.
- Expected benefit: future agents read current source-of-truth docs first and stop following stale task lists.
- Validation:
  - Move only files classified `ARCHIVE`.
  - Keep `Docs\DOCS_INDEX.md`, `Docs\ARCHIVED_MD_INDEX.md`, and `Docs\CURRENT_PROJECT_STATE.md` updated.
  - Run Markdown link/file existence sweep or at least verify indexed paths exist.

### Phase H2 - Generated Cache Cleanup

- Goal: remove regenerable project-authored caches.
- Files likely affected: project `__pycache__`, project `.pyc`.
- Risk level: Low.
- Expected benefit: faster searches and less noise.
- Validation:
  - Exclude `DesktopApp\Runtime`, `node_modules`, Tauri `target`, `Pipeline\Tools`, and bundled PowerShell runtime.
  - Run targeted Python tests after cleanup.

### Phase H3 - Log Retention And Runtime Artifact Archive

- Goal: control `RunLogs` growth while preserving useful diagnostics.
- Files likely affected: `DesktopApp\RunLogs`, `DesktopApp\*.log`, runtime `.pid`.
- Risk level: Medium.
- Expected benefit: faster search and cleaner diagnostics.
- Validation:
  - Confirm no active process owns logs/PID.
  - Archive rather than delete old logs.
  - Keep latest successful and latest failed run evidence.
  - Launch app and confirm Diagnostics can still explain missing/empty old logs gracefully.

### Phase H4 - Config Backup Retention

- Goal: make active config easier to find while preserving rollback.
- Files likely affected: `Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1`, `.bak.*`.
- Risk level: Medium.
- Expected benefit: less clutter around live config.
- Validation:
  - Compare backup timestamps.
  - Keep latest N backups.
  - Move older backups to archive folder, not delete.
  - Run config parser/schema tests and release self-test.

### Phase H5 - Search/Tooling Ergonomics

- Goal: help future agents avoid generated/runtime trees.
- Files likely affected: possible `.rgignore`, docs.
- Risk level: Low.
- Expected benefit: faster audits and fewer false positives.
- Validation:
  - Confirm `rg --files` still finds source/test/docs.
  - Document how to include generated/vendor trees when intentionally auditing packaging.

### Phase H6 - Optional Build Artifact Prune

- Goal: reclaim disk by pruning generated Tauri build/dependency artifacts.
- Files likely affected: `DesktopApp\tauri_shell\node_modules`, `DesktopApp\tauri_shell\src-tauri\target`, `DesktopApp\tauri_shell\src-tauri\gen`.
- Risk level: Medium.
- Expected benefit: large disk reduction.
- Validation:
  - Confirm Node/npm/Rust/Tauri rebuild commands.
  - Run Tauri checks before and after.
  - Do not perform if rapid local WebView development is ongoing.

### Phase H7 - Code/Test Cohesion Cleanup Only When Triggered

- Goal: reduce oversized source/test files without architecture churn.
- Files likely affected: large JS/test modules touched by active feature work.
- Risk level: Medium to High.
- Expected benefit: better long-term maintainability.
- Validation:
  - Extract cohesive behavior only.
  - Preserve DOM IDs, route contracts, mutation boundaries, Tk fallback, and tests.
  - Run targeted tests plus affected smoke wrappers.

## Destructive Actions Not Performed

Audit-stage note: before operator approval, no files were deleted, moved, or modified. After approval, the execution update at the top of this report records the completed reversible archive/cache-cleanup actions.

## Immediate Recommendation

Approve Phase H1 first: archive completed Markdown/task/audit clutter into `Docs\archive\...` while updating `DOCS_INDEX.md` and `ARCHIVED_MD_INDEX.md`. This gives the best efficiency gain with the least operational risk. After that, approve H2 cache cleanup and H3 log retention separately.
