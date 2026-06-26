# MediaPipelineRemuxEncodeAIO Documentation Index

Last updated: 2026-06-24

This is the active documentation map for the current promoted tree. It reflects the quarantine move plus the operator's later manual deletion of several active doc folders. The legacy desktop shell is not part of this current folder, and WebView/Tauri is the promoted operator surface.

## Start Here

- `..\README.md`: root operator entry point.
- `..\AGENTS.md`: root entry point for AI/code agents.
- `CURRENT_PROJECT_STATE.md`: current architecture, launch paths, operating state, safety assumptions, and obsolete instructions.
- `..\docs/OPEN_WORK_CHECKLIST.md`: active work queue and closed promotion-gate record.
- `README_MediaPipelineRemuxEncodeAIO.md`: bundle overview, launchers, setup, release packaging, and important paths.
- `DOCS_INDEX.md`: this file.

## Housekeeping

- Older root housekeeping reports were moved under `archive/docs-housekeeping/2026-05-20-review/archive-historical/` as superseded historical evidence.
- `ARCHIVED_MD_INDEX.md`: current archive/quarantine index.
- `archive/docs-housekeeping/2026-05-20-review/`: original housekeeping quarantine root.
- `archive/docs-housekeeping/2026-06-04-completed-md-pass/`: completed/superseded Markdown archive pass.

## Active Root Docs

- `..\README.md`: root operator entry point.
- `..\AGENTS.md`: root AI/code-agent entry point.
- `architecture/ARCHITECTURE.md`: concise architecture map.
- `..\CHANGELOG.md`: canonical shipped-status log.
- `..\docs/OPEN_WORK_CHECKLIST.md`: active work queue and promotion-gate record.
- `generated/PROJECT_INDEX.md`: generated per-source navigation index.
- `generated/PIPELINE_MAP.md`: generated stage contract map.
- `generated/DEPENDENCY_GRAPH.md`: generated cross-domain dependency graph.
- `generated/FILE_SUMMARIES.md`: summary-system guide.

## Implementation Plans

- `implementation/documentation-cleanup-goal-prompt.md`: four-phase documentation cleanup goal prompt for canonical drift fixes, completed-plan archival, evidence snapshot triage, and generated navigation refresh.
- `implementation/library-route-map/README.md`: no-plugin Library Route Map planning pack for placing backend-authored route maps, route tables, selected-file traces, profile comparison, guided existing-policy editing, and validation handoff on the Libraries tab.
- `implementation/library-route-map/PHASE_1_READ_ONLY_LIBRARY_ROUTE_MAP.md`: read-only Libraries tab route map and decision matrix plan.
- `implementation/library-route-map/PHASE_2_SELECTED_FILE_DRY_RUN_TRACE.md`: selected Queue/Completed/Sample Validation file dry-run trace plan.
- `implementation/library-route-map/PHASE_3_PROFILE_COMPARE_AND_DIFF.md`: side-by-side Library Profile route and settings comparison plan.
- `implementation/library-route-map/PHASE_4_GUIDED_POLICY_EDITING.md`: graph-node navigation into existing backend-owned Library Profile controls.
- `implementation/library-route-map/PHASE_5_ROUTE_MAP_VALIDATION_HANDOFF.md`: Launch, Completed, Pending Publish, Diagnostics, and Sample Validation evidence handoff plan.
- `implementation/local-api-test-split/README.md`: planning pack for splitting the oversized Local API/WebView static test god-file into troubleshooting-oriented modules.
- `implementation/local-api-test-split/PRE_WORK_AND_BASELINE.md`: prework, baseline validation, method inventory, assertion inventory, and stop conditions before moving tests.
- `implementation/local-api-test-split/PHASE_1_TEST_HARNESS_AND_SHARED_FIXTURES.md`: shared test support extraction plan before moving test ownership.
- `implementation/local-api-test-split/PHASE_2_WEB_STATIC_EXTRACTION.md`: plan for extracting the giant Web prototype/static assertions into page-focused Web static modules.
- `implementation/local-api-test-split/PHASE_3_LOCAL_API_ROUTE_DOMAIN_EXTRACTION.md`: plan for splitting Local API route tests by HTTP, lifecycle, process, queue, rename, diagnostics, network, repair, and settings ownership.
- `implementation/local-api-test-split/PHASE_4_QUEUE_RENAME_CONTRACT_DECOMPOSITION.md`: queue/rename long-contract decomposition plan.
- `implementation/local-api-test-split/PHASE_5_CLEANUP_DOCS_AND_DISCOVERY.md`: cleanup, docs, generated-summary, discovery, and change-packet closure plan.
- `implementation/local-api-test-split/ASSERTION_MIGRATION_LEDGER.md`: fill-in ledger proving moved/deleted assertions are accounted for during the split.
- `implementation/local-api-test-split/VALIDATION.md`: per-phase validation commands and docs-only planning validation for the test split.
- `implementation/local-api-test-split/ADVERSARIAL_REVIEW.md`: failure-first review checklist for lost assertions, duplicate tests, weakened guardrails, and helper risk.
- `implementation/local-api-test-split/EXECUTION_PROMPTS.md`: bounded prompts for executing each test-split phase with a fresh agent.
- `implementation/css-split/README.md`: planning pack for splitting the oversized WebView CSS parents while preserving import order, test coverage, static serving, and browser-layout validation.
- `implementation/css-split/STYLES_COMPONENTS_SPLIT.md`: one-at-a-time plan for splitting `styles.components.css` into shared component child CSS files.
- `implementation/css-split/STYLES_PAGES_SPLIT.md`: one-at-a-time plan for splitting `styles.pages.css` into Home, Settings, Network, Reports, and responsive page CSS files.
- `implementation/css-split/STYLES_QUEUE_SPLIT.md`: one-at-a-time plan for splitting `styles.queue.css` into Queue, priority/order, and File Override drawer CSS files.
- `implementation/webview-large-file-refactor-prework/networkView.prework-prompt.md`: prework prompt for a troubleshooting-oriented `networkView.js` split, anchored to the existing Network planning pack and backend-owned lifecycle/setup boundaries.
- `implementation/webview-large-file-refactor-prework/renameView.prework-prompt.md`: prework prompt for a troubleshooting-oriented `renameView.js` split, including preview/apply/undo safety, strict confirmations, path intake, workbench, and dialog ledgers.
- `implementation/webview-large-file-refactor-prework/renameView.phase0-baseline.md`: Phase 0 prework baseline for a troubleshooting-oriented `renameView.js` split, recording the namespace export ledger, route/DOM ledgers, source-only guardrails, mutable state, seams, rollback rules, and validation gate.
- `implementation/webview-large-file-refactor-prework/queueView.prework-prompt.md`: prework prompt for a troubleshooting-oriented `queueView.js` split, including existing child modules, queue command routes, selection/filter state, and compatibility exports.
- `implementation/webview-large-file-refactor-prework/settingsView.prework-prompt.md`: prework prompt for a troubleshooting-oriented `settingsView.js` split, including existing builder modules, settings preview/save contracts, strict confirmations, and staged patch state.
- `implementation/webview-large-file-refactor-prework/settingsView.baseline.md`: prework baseline for a troubleshooting-oriented `settingsView.js` split, recording facade exports, child-module boundaries, route/DOM ledgers, mutable state, future extraction seams, rollback rules, and validation evidence.
- `implementation/webview-large-file-refactor-prework/settingsLibraries.prework-prompt.md`: prework prompt for a troubleshooting-oriented `settingsLibraries.js` split, including Library Profile inheritance, override staging, Settings preview/save delegation, and route/promotion evidence.
- `implementation/network-view-troubleshooting-refactor/README.md`: troubleshooting-oriented plan for splitting `networkView.js` while preserving backend-owned Network lifecycle/setup routes, dry-run freshness, strict confirmations, worker/state-file evidence, and diagnostics handoffs.
- `implementation/network-view-troubleshooting-refactor/PHASE_0_BASELINE.md`: Phase 0 export ledger, direct caller baseline, route/DOM/command-owner baseline, and parent-plus-child guardrail migration record.
- `implementation/pipeline-processing-split/README.md`: planning pack for splitting the critical PowerShell encode/remux processing path by troubleshooting and failure boundary.
- `implementation/pipeline-processing-split/PRE_WORK.md`: pre-work, stop conditions, behavior inventory, and baseline validation for the pipeline split.
- `implementation/pipeline-processing-split/TARGET_ARCHITECTURE.md`: target encode/remux module boundaries, public contracts, loader rules, and troubleshooting map.
- `implementation/pipeline-processing-split/PHASE_1_BASELINE_AND_CONTRACT_FREEZE.md`: characterization and contract-freeze phase before moving PowerShell behavior.
- `implementation/pipeline-processing-split/PHASE_2_REMUX_EXTRACTION.md`: behavior-preserving remux extraction plan.
- `implementation/pipeline-processing-split/PHASE_3_ENCODE_CORE_EXTRACTION.md`: encode context, preflight, attempt-plan, command-builder, and execution extraction plan.
- `implementation/pipeline-processing-split/PHASE_4_ENCODE_FALLBACK_VERIFICATION_SIZE.md`: encode fallback, verification, size guard, and publish handoff extraction plan.
- `implementation/pipeline-processing-split/PHASE_5_DISPATCHER_LOAD_ORDER_CLEANUP.md`: dispatcher, module loader, wrapper, generated-summary, and cleanup phase.
- `implementation/pipeline-processing-split/VALIDATION.md`: per-phase validation ladder and real-media evidence matrix for the split.
- `implementation/pipeline-processing-split/ADVERSARIAL_REVIEW.md`: failure-first review checklist for assuming the split broke behavior and proving otherwise.
- `implementation/pipeline-processing-split/EXECUTION_PROMPTS.md`: bounded goal-oriented prompts for executing each split planning document with a fresh AI coding tool.
- `implementation/reports-view-refactor/README.md`: planning pack for splitting `reportsView.js` into Reports-owned WebView child modules while preserving namespace exports, backend-owned command routes, and preview-first guardrails.
- `implementation/release-foundation/README.md`: `2026.06.04.001` portable Tauri release-foundation planning pack.
- `implementation/release-foundation/PHASE_0_DOCS_ONLY_PLANNING.md`: docs-only planning and validation.
- `implementation/release-foundation/PHASE_1_RELEASE_IDENTITY.md`: `2026.06.04.001` release identity alignment plan.
- `implementation/release-foundation/PHASE_2_FILE_LAYOUT_CLEANUP.md`: file-layout cleanup and document-placement helper plan.
- `implementation/release-foundation/PHASE_3_DOCUMENTATION_CLEANUP.md`: active documentation cleanup plan.
- `implementation/release-foundation/PHASE_4_TAURI_RELEASE_CANDIDATE.md`: Tauri portable release candidate build plan.
- `implementation/release-foundation/PHASE_5_PACKAGE_OPEN_CLOSE_VALIDATION.md`: package/open/close validation plan.
- `implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`: repeatable real-media pilot plan.
- `implementation/release-foundation/PHASE_7_FINALIZATION.md`: change-control and release metadata finalization plan.
- `implementation/encoder-breadth-av1-plan.md`: active encoder breadth/AV1 implementation plan for the remaining hardware/runtime validation workstream.

## Removed Compatibility Redirects

- Former `AI_AGENT_START_HERE.md`, `AI_DIRECTIVE.md`, and `AI_HANDOFF.md`
  material is superseded by root `AGENTS.md` and is not part of the current
  active guidance surface.

No active standalone fix-checklist redirect remains; use
`CURRENT_PROJECT_STATE.md` and `..\docs/OPEN_WORK_CHECKLIST.md`.

`docs/active-plans/` currently contains no Markdown files.

## Architecture

- `architecture/CONFIG_KEY_GLOSSARY.md`: config-key glossary by subsystem.
- `architecture/DECISIONS_AND_HISTORY.md`: durable architecture, safety, media policy, rename, WebView/Tauri, and documentation decisions.
- `architecture/god-file-splits/README.md`: per-file split plans for current monolithic/high-strain production and tooling files.
- `architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`: mutation classification for Local API routes.
- `architecture/LOCAL_API_SECURITY_SURFACE.md`: localhost API, token bootstrap, security headers, and WebView/Tauri authority boundary.
- `architecture/LOGGING_CONVENTION.md`: logging and structured-artifact conventions for PowerShell, Python, and WebView work.
- `architecture/MODULE_MAP.md`: codebase layer map and feature-placement guide.
- `architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`: backend-owned Network lifecycle/setup route contract, including provider-guarded dry-run/start/stop routes, discovery, test-connection, and join/import setup boundaries.
- `architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`: current read-only Network page boundaries.
- `architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`: backend dry-run and confirmed apply contract for selected Completed/Pending repair routes, with startup reconciliation dry-run only.
- `reviews/network-coordinator-worker-mode-2026-06-15/DISPOSITION_LEDGER.md`: per-finding disposition ledger for the 2026-06-15 network coordinator/worker review.
- `architecture/SETTINGS_RAW_KEY_TRIAGE.md`: settings builder/raw-key coverage and intentionally hidden auth keys.
- `architecture/STATE_SURFACE_INVENTORY.md`: mutable state inventory across PowerShell, Python, and WebView modules.
- `architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`: Tauri/WebView2 shell to Python backend lifecycle boundary.

## Audits

- `audits/latest.md`: redirect to archived historical audit snapshot and current-state docs.
- `audits/DEAD_EXPORT_AUDIT_2026-05-19.md`: redirect to archived dead-export audit evidence.
- `audits/CODE_REVIEW_WEBVIEW_TAURI_AUDIT.md`: redirect to archived WebView/Tauri audit evidence.
- `reviews/function-module-audit-2026-06-11/FINDINGS_REGISTER.md`: active reference for the fixed/deferred function-module audit disposition.
- `reviews/network-coordinator-worker-mode-2026-06-15/FINDINGS_REGISTER.md`: active reference for the network coordinator/worker finding set.
- `reviews/network-coordinator-worker-mode-2026-06-15/DISPOSITION_LEDGER.md`: active per-finding disposition ledger for the 2026-06-15 network coordinator/worker review.

Other 2026-06 audit/review packs are historical evidence snapshots and should live under `archive/docs-housekeeping/2026-06-24-doc-prune/`.

## Inventories

- `inventories/API_ROUTE_INVENTORY.md`
- `inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `inventories/LOG_ARTIFACT_CATALOG.md`
- `inventories/PACKAGING_DEPENDENCY_INVENTORY.md`
- `inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`
- `inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- `inventories/RENAME_SAFETY_TEST_INVENTORY.md`
- `inventories/RENAME_TOOL_EDGE_CASE_CATALOG.md`
- `inventories/ROOT_SCRIPT_INVENTORY.md`
- `inventories/RUNTIME_ARTIFACT_INVENTORY.md`
- `inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- `inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
- `inventories/SMOKE_TEST_INVENTORY.md`
- `inventories/STATE_FILE_SCHEMA_REFERENCE.md`
- `inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md`
- `inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`

## Testing And Validation

- `testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`
- `testing/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md`
- `testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`
- `testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- `testing/FFMPEG_MEDIA_POLICY_REGRESSION_MATRIX.md`
- `testing/TEST_COVERAGE_MATRIX.md`
- `testing/VALIDATION_LADDER_RUNBOOK.md`
- `testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`
- `testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- `..\ops/scripts/smoke\README.md`

Smoke wrappers live under `..\ops/scripts/smoke\`. Do not add new smoke wrappers at the repository root.

## Operator Guides

- `operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- `operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- `operator/FAILURE_TRIAGE_WORKSHEET.md`
- `operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `operator/OPERATOR_GLOSSARY.md`
- `operator/POWERSHELL_HOST_EXPECTATIONS.md`
- `operator/TERMINOLOGY_CONSISTENCY_GUIDE.md`
- `operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`
- `operator/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md`

## Sample Validation

- `sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`
- `sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- `RealMediaValidationRuns/README.md`: non-sensitive status anchor for the 2026-05-28 operator-attested representative real-media validation.

Run-specific worksheets may remain local or excluded from release packaging when they contain personal source/output paths.

## Desktop App And WebView

- `desktop/README.md`
- `..\apps\desktop\tauri\README.md`

## UI Planning

- `ui/`: UI reference and workflow material. Completed remediation trackers are archived.

The old desktop overview and feature comparison docs remain in `archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/`; recover only specific paragraphs into current canonical docs.

## Runtime And Tool Placeholders

- `..\apps\desktop\runtime\Python\README_portable_python_here.txt`
- `..\ops\pipeline\runtime\Python\README_portable_python_here.txt`
- `..\ops\pipeline\tools\ffmpeg\bin\README_ffmpeg_here.txt`
- `..\ops\pipeline\tools\MKVToolNix\README_mkvtoolnix_here.txt`

## Empty Topic Folders

These folders currently exist but contain no Markdown/text documentation files:

- `active-plans/`
- `proposals/`

## Archive And Quarantine

- `archive/docs-housekeeping/2026-05-20-review/archive-historical/`: 65 completed or historical docs kept for rollback/reference only.
- `archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/`: 5 docs whose useful content should live in current canonical docs instead of remaining active.
- `archive/docs-housekeeping/2026-05-20-review/delete-candidates/`: 19 quarantine-only delete candidates.
- `archive/docs-housekeeping/2026-06-04-completed-md-pass/`: completed or superseded historical audits, dependency-refactor tracker docs, and UX remediation tracker docs moved out of active topic folders.
- `archive/docs-housekeeping/2026-06-24-doc-prune/`: completed implementation plans plus 2026-06 audit/review evidence snapshots pruned from the active docs tree.

Do not use quarantined docs as active guidance unless a current doc explicitly points to one for historical evidence. Use `ARCHIVED_MD_INDEX.md` for the archive inventory.
