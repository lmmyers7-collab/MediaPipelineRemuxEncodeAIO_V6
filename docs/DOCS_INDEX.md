# MediaPipelineRemuxEncodeAIO Documentation Index

Last updated: 2026-07-04

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
- `archive/docs-housekeeping/2026-07-04-doc-cleanup/`: completed plans,
  stale session notes, and obsolete architecture proposals moved out of active
  guidance.

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

- `implementation/library-route-map/`: planning pack for backend-authored
  Library Route Map views and validation handoffs.
- `implementation/css-split/`: planning pack for splitting large WebView CSS
  parents while preserving plain-CSS import order.
- `implementation/webview-large-file-refactor-prework/`: prework prompts and
  baselines for future large WebView module splits.
- `implementation/network-view-troubleshooting-refactor/`: planning pack for a
  troubleshooting-oriented `networkView.js` split.
- `implementation/network-csv-rerun/PREWORK.md`: investigation-first planning
  source for making CSV rerun a future Network coordinator/worker workload.
- `implementation/pipeline-processing-split/`: planning pack for splitting the
  critical PowerShell encode/remux processing path by failure boundary.
- `implementation/reports-view-refactor/`: planning pack for splitting
  `reportsView.js` into Reports-owned child modules.
- `implementation/encoder-breadth-av1-plan.md`: active encoder breadth/AV1 implementation plan for the remaining hardware/runtime validation workstream.
- `implementation/ruff-rule-expansion/B_C4_UP_FINDINGS_REMEDIATION.md`: work ledger for cleaning Ruff `B`, `C4`, and `UP` candidate findings before any noisy family becomes blocking.

Completed implementation packs moved out of active guidance are indexed under
`archive/docs-housekeeping/2026-07-04-doc-cleanup/`.

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
- `testing/THIRTY_DAY_SOAK_TEST_DESIGN.md`
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

- `sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`
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
- `archive/docs-housekeeping/2026-07-04-doc-cleanup/`: completed release,
  test-split, architecture-boundary, documentation-cleanup, network hardening,
  queue scan, and stale session-log material moved out of active guidance.

Do not use quarantined docs as active guidance unless a current doc explicitly points to one for historical evidence. Use `ARCHIVED_MD_INDEX.md` for the archive inventory.
