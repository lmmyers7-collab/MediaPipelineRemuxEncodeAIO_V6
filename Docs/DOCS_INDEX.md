# MediaPipelineRemuxEncodeAIO V6 Documentation Index

Last updated: 2026-06-04

This is the active documentation map for the current promoted V6 tree. It reflects the quarantine move plus the operator's later manual deletion of several active doc folders. The legacy desktop shell is not part of this V6 folder, and WebView/Tauri is the promoted operator surface.

## Start Here

- `..\README.md`: root operator entry point.
- `..\AGENTS.md`: root entry point for AI/code agents.
- `CURRENT_PROJECT_STATE.md`: current architecture, launch paths, operating state, safety assumptions, and obsolete instructions.
- `..\OPEN_WORK_CHECKLIST.md`: active work queue and closed promotion-gate record.
- `TLDR.md`: fast operator summary.
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
- `..\OPEN_WORK_CHECKLIST.md`: active work queue and promotion-gate record.
- `generated/PROJECT_INDEX.md`: generated per-source navigation index.
- `generated/PIPELINE_MAP.md`: generated stage contract map.
- `generated/DEPENDENCY_GRAPH.md`: generated cross-domain dependency graph.
- `generated/FILE_SUMMARIES.md`: summary-system guide.

## Implementation Plans

- `implementation/v6-release-foundation/README.md`: `V6.0.0` portable Tauri release-foundation planning pack.
- `implementation/v6-release-foundation/PHASE_0_DOCS_ONLY_PLANNING.md`: docs-only planning and validation.
- `implementation/v6-release-foundation/PHASE_1_RELEASE_IDENTITY.md`: `V6.0.0` release identity alignment plan.
- `implementation/v6-release-foundation/PHASE_2_FILE_LAYOUT_CLEANUP.md`: file-layout cleanup and document-placement helper plan.
- `implementation/v6-release-foundation/PHASE_3_DOCUMENTATION_CLEANUP.md`: active documentation cleanup plan.
- `implementation/v6-release-foundation/PHASE_4_TAURI_RELEASE_CANDIDATE.md`: Tauri portable release candidate build plan.
- `implementation/v6-release-foundation/PHASE_5_PACKAGE_OPEN_CLOSE_VALIDATION.md`: package/open/close validation plan.
- `implementation/v6-release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`: repeatable real-media pilot plan.
- `implementation/v6-release-foundation/PHASE_7_FINALIZATION.md`: change-control and release metadata finalization plan.

## Archived Compatibility Redirects

- `archive/ai/AI_AGENT_START_HERE.md`: archived redirect to `..\AGENTS.md`.
- `archive/ai/AI_DIRECTIVE.md`: archived redirect to `..\AGENTS.md`.
- `ACTIVE_FIX_CHECKLIST.md`: redirect to `CURRENT_PROJECT_STATE.md` and `..\OPEN_WORK_CHECKLIST.md`.

`Docs/active-plans/` currently contains no Markdown files.

## Architecture

- `architecture/CONFIG_KEY_GLOSSARY.md`: config-key glossary by subsystem.
- `architecture/DECISIONS_AND_HISTORY.md`: durable architecture, safety, media policy, rename, WebView/Tauri, and documentation decisions.
- `architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`: mutation classification for Local API routes.
- `architecture/LOCAL_API_SECURITY_SURFACE.md`: localhost API, token bootstrap, security headers, and WebView/Tauri authority boundary.
- `architecture/LOGGING_CONVENTION.md`: logging and structured-artifact conventions for PowerShell, Python, and WebView work.
- `architecture/MODULE_MAP.md`: codebase layer map and feature-placement guide.
- `architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`: design-only lifecycle command gates for future Network commands.
- `architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`: current read-only Network page boundaries.
- `architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`: design-only gates for future Completed/Pending repair routes.
- `architecture/SETTINGS_RAW_KEY_TRIAGE.md`: settings builder/raw-key coverage and intentionally hidden auth keys.
- `architecture/STATE_SURFACE_INVENTORY.md`: mutable state inventory across PowerShell, Python, and WebView modules.
- `architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`: Tauri/WebView2 shell to Python backend lifecycle boundary.
- `architecture/V5_MIGRATION_RISK_REGISTER.md`: inherited V5 transition risk register still useful for V6 safety review.

## Audits

- `audits/latest.md`: redirect to archived historical audit snapshot and current-state docs.
- `audits/DEAD_EXPORT_AUDIT_2026-05-19.md`: redirect to archived dead-export audit evidence.
- `audits/CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md`: redirect to archived V5/WebView/Tauri audit evidence.

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
- `testing/TEST_COVERAGE_MATRIX.md`
- `testing/VALIDATION_LADDER_RUNBOOK.md`
- `testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`
- `testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- `..\SmokeTests\README.md`

Smoke wrappers live under `..\SmokeTests\`. Do not add new smoke wrappers at the repository root.

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
- `sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `sample-validation/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md`
- `RealMediaValidationRuns/README.md`: non-sensitive status anchor for the 2026-05-28 operator-attested representative real-media validation.

Run-specific worksheets may remain local or excluded from release packaging when they contain personal source/output paths.

## Desktop App And WebView

- `DesktopApp/docs/README.md`
- `DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`
- `..\DesktopApp\tauri_shell\README.md`

## UI Planning

- `ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`: active planning and execution tracker for the 13-tab WebView workflow redesign.
- `ui/V6_OPERATOR_UX_REMEDIATION_REMAINING_TASKS.md`: redirect to the archived completed UX-001 through UX-017 remediation tracker.

The old DesktopApp overview and feature comparison docs remain in `archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/`; recover only specific paragraphs into current canonical docs.

## Runtime And Tool Placeholders

- `..\DesktopApp\Runtime\Python\README_portable_python_here.txt`
- `..\Pipeline\Runtime\Python\README_portable_python_here.txt`
- `..\Pipeline\Tools\ffmpeg\bin\README_ffmpeg_here.txt`
- `..\Pipeline\Tools\MKVToolNix\README_mkvtoolnix_here.txt`

## Empty Topic Folders

These folders currently exist but contain no Markdown/text documentation files:

- `active-plans/`
- `Pipeline/`
- `proposals/`

## Archive And Quarantine

- `archive/docs-housekeeping/2026-05-20-review/archive-historical/`: 65 completed or historical docs kept for rollback/reference only.
- `archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/`: 5 docs whose useful content should live in current canonical docs instead of remaining active.
- `archive/docs-housekeeping/2026-05-20-review/delete-candidates/`: 19 quarantine-only delete candidates.
- `archive/docs-housekeeping/2026-06-04-completed-md-pass/`: completed or superseded historical audits, dependency-refactor tracker docs, and UX remediation tracker docs moved out of active topic folders.

Do not use quarantined docs as active guidance unless a current doc explicitly points to one for historical evidence. Use `ARCHIVED_MD_INDEX.md` for the archive inventory.
