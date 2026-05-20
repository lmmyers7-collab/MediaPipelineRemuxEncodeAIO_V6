# Claude Handoff: Cleanup, Review, And Sorting Backlog

Repository:

`C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Purpose:

This is a low-dependency task list for Claude. The goal is to reduce project clutter, improve documentation trust, sort inventories, identify stale wording, and make later Codex verification faster. These tasks are mostly administrative and review-oriented. They should not alter runtime behavior.

## Global Rules For Claude

1. Do not touch V4.
2. Do not remove, weaken, or bypass the Tk fallback.
3. Do not change FFmpeg, ffprobe, remux/encode routing, subtitle/audio policy, queue behavior, pending publish, source/scratch/output behavior, process lifecycle, command journal behavior, close-readiness behavior, settings persistence semantics, or Local API route semantics.
4. Do not add frontend-owned filesystem mutation or frontend-only mutation logic.
5. Do not run real media processing, pipeline start, audit start, CSV rerun, pending publish drain, rename apply, settings save, or release build commands.
6. Prefer Markdown-only edits. If a task asks for code inspection, read only and report findings unless the task explicitly allows a small static test/doc update.
7. Keep each task independently reviewable.
8. If a task reveals an actual code defect, document it in a findings section instead of patching behavior.
9. Preserve existing docs if uncertain. Prefer marking stale/uncertain items over deleting them.
10. End each task with a short note listing files inspected, files changed, validation run, and open questions.

## Recommended Lightweight Validation

Use the smallest useful validation. Most tasks do not need the full suite.

```powershell
Get-ChildItem Docs -Filter *.md
Select-String -Path Docs\*.md -Pattern "<term>"
python -m py_compile <changed-python-file>
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Run the release self-test only when changing release scripts, `SmokeTests/` wrappers, or docs that are explicitly checked by release/scaffold tests.

## Output Format For Each Completed Task

```text
Task ID:
Files inspected:
Files changed:
Validation:
Findings:
Open questions:
Risk:
```

## Task Index

| ID | Task | Type | Risk | Expected Output |
|---|---|---:|---:|---|
| CLN-001 | Handoff Backlog Status Reconciliation | Sorting | Low | Updated status table or new reconciliation note |
| CLN-002 | Docs Index Completeness Pass | Sorting | Low | `DOCS_INDEX.md` additions or audit notes |
| CLN-003 | Stale Schedule Read-Only Wording Audit | Review | Low | Findings doc or wording-only doc patch |
| CLN-004 | Smoke Wrapper Boundary Text Audit | Review | Low | Consistency findings and suggested fixes |
| CLN-005 | Browser Smoke Ordering And Catalog Sort | Sorting | Low | Sorted smoke catalog/runbook entries |
| CLN-006 | Root Script Inventory And Purpose Table | Inventory | Low | New root-script inventory doc |
| CLN-007 | Docs Folder Sorting Proposal | Sorting | Low | Proposed folder taxonomy; no moves |
| CLN-008 | Completed Checklist Archive Review | Cleanup | Low | List of checklists that are archive-only |
| CLN-009 | Release Self-Test Layout Inventory Check | Review | Low | Compare root docs/scripts vs release layout |
| CLN-010 | Local API Route Count Sync Audit | Review | Low | Route count doc sync findings |
| CLN-011 | WebView DOM ID Dead Reference Audit | Review | Low | Dead/missing DOM ID findings |
| CLN-012 | WebView Global Export Inventory | Inventory | Low | Per-view globals and ownership notes |
| CLN-013 | Command History Owner Coverage Audit | Review | Low | Commands without clear owner-page mapping |
| CLN-014 | Diagnostics Target Docs Sync | Review | Low | Allowlist/doc mismatch findings |
| CLN-015 | Settings Raw-Key Triage Sorting | Sorting | Low | High-impact raw-only key list |
| CLN-016 | Rename Documentation Freshness Review | Review | Low | Rename docs current/gap note |
| CLN-017 | Pending Publish Docs Freshness Review | Review | Low | Pending publish docs current/gap note |
| CLN-018 | Network Read-Only Language Audit | Review | Low | Any text implying unsafe lifecycle controls |
| CLN-019 | Tauri Preview Vs Daily Driver Wording Audit | Review | Low | Wording fixes or findings |
| CLN-020 | V3/V4/V5 Version Label Rescan | Review | Low | Updated stale label addendum |
| CLN-021 | PowerShell Host Wording Rescan | Review | Low | PS7/PS5 reference findings |
| CLN-022 | Runtime Artifact Classification Sort | Sorting | Low | Artifact table improvements or notes |
| CLN-023 | Generated/Vendor Artifact Exclusion Review | Review | Low | Packaging/documentation exclusion findings |
| CLN-024 | Test Suite Subsystem Sorting Refresh | Sorting | Low | Updated test inventory notes |
| CLN-025 | Browser Smoke Failure Triage Cheatsheet | Docs | Low | New quick triage doc or runbook section |
| CLN-026 | Operator Copy Vocabulary Consistency Pass | Review | Low | Wording findings against glossary/audit |
| CLN-027 | Real-Media Validation Worksheet Sorting | Cleanup | Low | Guidance for storing/comparing worksheets |
| CLN-028 | Changelog Navigation Health Review | Sorting | Low | Changelog index/split recommendations |
| CLN-029 | Markdown Link And File-Existence Sweep | Review | Low | Missing target findings |
| CLN-030 | Admin Task Completion Board | Sorting | Low | One-page board of Claude-safe remaining tasks |

---

## CLN-001 - Handoff Backlog Status Reconciliation

Goal:

Review the existing Claude handoff files and classify which tasks appear completed, obsolete, duplicated, still useful, or unsafe.

Inspect:

- `Docs\CLAUDE_HANDOFF_20_TASK_BACKLOG.md`
- `Docs\CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md`
- `Docs\CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md`
- Current `Docs\DOCS_INDEX.md`

Deliverable:

- Create `Docs\CLAUDE_HANDOFF_STATUS_RECONCILIATION.md` or update this file with a status table.

Acceptance:

- Each older Claude task is assigned one status: `done`, `still useful`, `obsolete`, `duplicated`, or `needs Codex decision`.
- Do not delete old handoff docs.
- Include a "safe next 5 tasks" list.

Validation:

```powershell
Select-String -Path Docs\CLAUDE_HANDOFF*.md -Pattern "Task|C-|ADM|CLN"
```

## CLN-002 - Docs Index Completeness Pass

Goal:

Make sure `Docs\DOCS_INDEX.md` mentions the current high-value docs and does not miss newly created handoff docs, smoke runbooks, or risk registers.

Inspect:

- `Docs\DOCS_INDEX.md`
- `Get-ChildItem Docs -Filter *.md`

Deliverable:

- Update `Docs\DOCS_INDEX.md` or create `Docs\DOCS_INDEX_MISSING_ITEMS.md` if uncertain.

Acceptance:

- New Claude handoff docs are discoverable.
- Browser smoke docs are discoverable.
- No completed archive is described as active implementation work.

Validation:

```powershell
Get-ChildItem Docs -Filter *.md
Select-String -Path Docs\DOCS_INDEX.md -Pattern "CLAUDE_HANDOFF|WEBVIEW_SMOKE|BROWSER_SMOKE"
```

## CLN-003 - Stale Schedule Read-Only Wording Audit

Goal:

Find remaining documentation or operator text that says WebView Schedule is fully read-only or has no editor after the backend-owned Schedule Editor was added.

Inspect:

- `Docs`
- `DesktopApp\tauri_shell\README.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`

Deliverable:

- Wording-only doc patch, or `Docs\SCHEDULE_STALE_READONLY_WORDING_AUDIT.md`.

Acceptance:

- It is still okay to say "coverage detail is evidence-only."
- It is not okay to say "no WebView schedule editor" unless clearly historical.
- It must still say WebView does not own continuous schedule-stop watcher behavior.

Validation:

```powershell
Select-String -Path Docs\*.md,DesktopApp\tauri_shell\README.md -Pattern "no WebView schedule editor|read-only Schedule|Schedule page is read-only|until backend save contract"
```

## CLN-004 - Smoke Wrapper Boundary Text Audit

Goal:

Review `SmokeTests/Test-WebView*.ps1` wrappers and check whether their boundary text matches what each smoke actually does.

Inspect:

- `Test-WebView*.ps1`
- Matching `DesktopApp\tests\test_webview*.py` files

Deliverable:

- `Docs\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md` with mismatches and suggested text.

Acceptance:

- Call out stale phrases like "read-only" when a backend-owned mutation exists.
- Ensure mutation boundaries are precise: "does not save settings" vs "does save schedule app-state through backend."
- Do not edit wrappers unless the mismatch is trivial and obviously stale.

Validation:

```powershell
Get-ChildItem -Filter "Test-WebView*.ps1"
Select-String -Path Test-WebView*.ps1 -Pattern "Boundary:"
```

## CLN-005 - Browser Smoke Ordering And Catalog Sort

Goal:

Sort browser smoke lists consistently across runbooks and docs.

Inspect:

- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`
- `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`
- `Docs\WEBVIEW_SMOKE_RESULT_TEMPLATE.md`
- `Docs\VALIDATION_LADDER_RUNBOOK.md`
- `DesktopApp\tauri_shell\README.md`

Deliverable:

- Wording/order-only doc patch.

Acceptance:

- Browser smokes appear in a consistent order.
- Non-browser and browser-backed smokes are clearly separated.
- Schedule browser smoke appears near Schedule, not buried at the end.

Validation:

```powershell
Select-String -Path Docs\*.md,DesktopApp\tauri_shell\README.md -Pattern "Test-WebViewBrowser"
```

## CLN-006 - Root Script Inventory And Purpose Table

Goal:

Create a concise inventory of root scripts so a maintainer can quickly see what each script is for.

Inspect:

- Root `*.ps1`
- Root `*.bat`
- Root `*.cmd` if any

Deliverable:

- `Docs\ROOT_SCRIPT_INVENTORY.md`

Acceptance:

- For each script: purpose, safe to run?, mutates files?, requires browser?, requires media?, expected duration.
- Explicitly mark dangerous or real-operation scripts.
- Include Tauri/WebView preview wrappers and release checks.

Validation:

```powershell
Get-ChildItem -File -Include *.ps1,*.bat,*.cmd
```

## CLN-007 - Docs Folder Sorting Proposal

Goal:

Propose a cleaner docs taxonomy without moving files yet.

Inspect:

- `Docs` root
- `Docs\DesktopApp`
- `Docs\Pipeline`
- `Docs\RealMediaValidationRuns`

Deliverable:

- `Docs\DOCS_FOLDER_SORTING_PROPOSAL.md`

Acceptance:

- Group docs into proposed categories: operator, validation, architecture, migration, audits, handoffs, archives.
- Identify files that should stay at root for discoverability.
- Do not move files.

Validation:

```powershell
Get-ChildItem Docs -Recurse -Filter *.md | Select-Object FullName
```

## CLN-008 - Completed Checklist Archive Review

Goal:

Identify checklists that are completed/archive-only and should not be confused with active backlog.

Inspect:

- `Docs\UI_CHECKLIST*.md`
- `Docs\CODE_CLEANUP_CHECKLIST.md`
- `Docs\CONTROL_SURFACE_HARDENING_CHECKLIST.md`
- `Docs\NETWORK_MODE_CHECKLIST.md`
- Other checklist docs

Deliverable:

- `Docs\CHECKLIST_ARCHIVE_REVIEW.md`

Acceptance:

- Classify each checklist as active, archive, superseded, or decision-needed.
- Suggest a docs index wording change if needed.
- Do not delete checklists.

Validation:

```powershell
Get-ChildItem Docs -Filter "*CHECKLIST*.md"
```

## CLN-009 - Release Self-Test Layout Inventory Check

Goal:

Compare release self-test layout expectations with current root docs/scripts and identify missing or stale entries.

Inspect:

- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- root scripts
- `Docs\DOCS_INDEX.md`

Deliverable:

- `Docs\RELEASE_SELF_TEST_LAYOUT_AUDIT.md`

Acceptance:

- List root files checked by release self-test.
- List root smoke wrappers not checked, if any.
- List docs that are important but not release-gated.
- Do not change release script unless the omission is obvious and low risk.

Validation:

```powershell
Select-String -Path Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -Pattern "SmokeTests WebView|Docs index|Path ="
```

## CLN-010 - Local API Route Count Sync Audit

Goal:

Confirm docs route counts match actual Local API contracts.

Inspect:

- `DesktopApp\mediapipeline_desktop_app\api\contract.py`
- `contract_read.py`
- `contract_command.py`
- `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `Docs\LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`

Deliverable:

- Wording-only doc patch or `Docs\LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md`.

Acceptance:

- Actual read/command/total counts are recorded.
- Route effect categories are current.
- Schedule preview/save and sample validation routes are accounted for.

Validation:

```powershell
python - <<'PY'
from mediapipeline_desktop_app.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
print(len(LOCAL_API_READ_ROUTE_CONTRACT), len(LOCAL_API_COMMAND_ROUTE_CONTRACT))
PY
```

Run from `DesktopApp` if importing package modules directly.

## CLN-011 - WebView DOM ID Dead Reference Audit

Goal:

Find IDs used by JavaScript but missing from `index.html`, and IDs present in HTML but apparently unused.

Inspect:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js`

Deliverable:

- `Docs\WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md`

Acceptance:

- Separate `missing in HTML`, `unused in JS`, and `intentionally dynamic`.
- Do not edit JS/HTML unless fixing a typo-level documentation reference.

Validation:

```powershell
Select-String -Path DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js -Pattern 'byId\("|getElementById\("'
```

## CLN-012 - WebView Global Export Inventory

Goal:

Inventory globals exposed by each WebView asset and flag accidental broad coupling.

Inspect:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js`

Deliverable:

- `Docs\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`

Acceptance:

- Table columns: asset, namespace object, direct `window.*` globals, reason, likely owner, concern.
- Flag duplicate names or globals that seem unused.
- No code edits.

Validation:

```powershell
Select-String -Path DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js -Pattern "window\."
```

## CLN-013 - Command History Owner Coverage Audit

Goal:

Check whether command history owner-page mapping covers all current command names.

Inspect:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`
- `DesktopApp\mediapipeline_desktop_app\api\contract_command.py`
- command-producing facade policy files

Deliverable:

- `Docs\COMMAND_HISTORY_OWNER_COVERAGE_AUDIT.md`

Acceptance:

- List each known command prefix/name and owner page.
- Identify commands that fall back to Diagnostics.
- Suggest mapping improvements, but do not patch JS unless obviously missing and safe.

Validation:

```powershell
Select-String -Path DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js -Pattern "command.startsWith|command ==="
```

## CLN-014 - Diagnostics Target Docs Sync

Goal:

Confirm diagnostics open/tail targets in docs match backend allowlists.

Inspect:

- diagnostics command/read payload code
- `Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`

Deliverable:

- Wording-only doc patch or `Docs\DIAGNOSTICS_TARGET_SYNC_AUDIT.md`.

Acceptance:

- All allowlisted targets appear in the runbook.
- Tail-only vs open-target behavior is clearly separated.
- No arbitrary path wording is introduced.

Validation:

```powershell
Select-String -Path DesktopApp\mediapipeline_desktop_app\**\*.py -Pattern "diagnostics.*target|allowlist|allowed_targets"
```

## CLN-015 - Settings Raw-Key Triage Sorting

Goal:

Identify high-impact config keys that still rely on raw JSON editing in WebView Settings.

Inspect:

- `Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- settings metadata files
- `settingsView.js`

Deliverable:

- Update `Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md` or create `Docs\SETTINGS_RAW_KEY_TRIAGE.md`.

Acceptance:

- Classify raw-only keys as high/medium/low operator impact.
- Separate intentionally hidden dangerous keys from missing structured builders.
- No settings behavior changes.

Validation:

```powershell
Select-String -Path Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md -Pattern "raw|hidden|builder"
```

## CLN-016 - Rename Documentation Freshness Review

Goal:

Check whether rename docs reflect the current standalone Rename tool, movie/TV split, final-name overrides, checked-row scope, and backend-owned apply.

Inspect:

- `Docs\RENAME_SAFETY_TEST_INVENTORY.md`
- `Docs\TLDR.md`
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
- Rename WebView/static docs if any

Deliverable:

- `Docs\RENAME_DOCS_FRESHNESS_REVIEW.md` or doc wording patch.

Acceptance:

- Docs do not imply Rename is queue-integrated only.
- Docs mention backend-owned apply and selected/checked scope.
- Docs do not promise unsupported PowerRename-level freeform behavior.

Validation:

```powershell
Select-String -Path Docs\*.md -Pattern "Rename|PowerRename|checked|selected_sources|final name"
```

## CLN-017 - Pending Publish Docs Freshness Review

Goal:

Check pending-publish docs for stale statements about drain, recovery dry-run, reconciliation, and mutation ownership.

Inspect:

- `Docs\PENDING_PUBLISH_FIXTURE_INVENTORY.md`
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `Docs\V5_MIGRATION_RISK_REGISTER.md`

Deliverable:

- `Docs\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md` or wording-only patch.

Acceptance:

- Drain remains backend-owned through process launch mode.
- Recovery plan is dry-run only.
- No docs imply frontend can repair/drain/publish directly.

Validation:

```powershell
Select-String -Path Docs\*.md -Pattern "Pending Publish|recovery-plan|drain|publish"
```

## CLN-018 - Network Read-Only Language Audit

Goal:

Find any wording that implies WebView Network can start/stop coordinator or worker lifecycle when it is still read-only.

Inspect:

- `Docs\NETWORK*.md`
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `networkView.js`
- `index.html`

Deliverable:

- `Docs\NETWORK_READONLY_WORDING_AUDIT.md` or wording-only patch.

Acceptance:

- Network lifecycle controls remain explicitly Tk/backend-future only.
- Read-only worker visibility is clearly described.
- No operator instructions to start workers from WebView.

Validation:

```powershell
Select-String -Path Docs\*.md,DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\networkView.js -Pattern "start worker|stop worker|lifecycle|read-only"
```

## CLN-019 - Tauri Preview Vs Daily Driver Wording Audit

Goal:

Ensure docs do not overstate Tauri/WebView readiness or imply Tk can be retired now.

Inspect:

- `Docs\TLDR.md`
- `Docs\V5_TRANSITION_STATUS_BOARD.md`
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `DesktopApp\tauri_shell\README.md`
- root launchers docs

Deliverable:

- `Docs\TAURI_DAILY_DRIVER_WORDING_AUDIT.md` or wording-only patch.

Acceptance:

- WebView/Tauri is preview or partial parity.
- Tk fallback remains default/trusted.
- Any daily-driver language includes validation caveats.

Validation:

```powershell
Select-String -Path Docs\*.md,DesktopApp\tauri_shell\README.md -Pattern "daily|fallback|preview|retire|production"
```

## CLN-020 - V3/V4/V5 Version Label Rescan

Goal:

Rescan for stale product labels after recent V5 transition work.

Inspect:

- all project-owned text/code, excluding bundled runtimes, node_modules, logs, generated docs
- existing stale label audits

Deliverable:

- Update `Docs\STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md` or create a new addendum.

Acceptance:

- Classify each V3/V4 hit as stale, intentional historical context, V4 backup boundary, or false positive.
- Do not edit version labels unless clearly wrong in docs.

Validation:

```powershell
rg -n "V3|v3|V4|v4|v4\\.000|V5|v5" -g "!DesktopApp/tauri_shell/node_modules/**" -g "!Pipeline/Runtime/**" -g "!DesktopApp/Runtime/**"
```

## CLN-021 - PowerShell Host Wording Rescan

Goal:

Find docs or scripts that incorrectly imply Windows PowerShell 5 is the preferred host.

Inspect:

- docs
- root scripts
- setup/release scripts

Deliverable:

- `Docs\POWERSHELL_HOST_WORDING_AUDIT.md` or patch `Docs\POWERSHELL_HOST_EXPECTATIONS.md`.

Acceptance:

- Bundled PowerShell 7.6.0 is documented as preferred.
- PS5 references are classified as fallback, historical, or stale.
- Do not change script execution policy unless clearly documented-only.

Validation:

```powershell
Select-String -Path Docs\*.md,*.ps1,*.bat -Pattern "Windows PowerShell|PowerShell 5|pwsh|PowerShell-7.6.0"
```

## CLN-022 - Runtime Artifact Classification Sort

Goal:

Improve sorting/grouping of runtime artifacts by owner and safe action.

Inspect:

- `Docs\RUNTIME_ARTIFACT_INVENTORY.md`
- diagnostics/state summary docs
- release exclusion docs

Deliverable:

- Update `Docs\RUNTIME_ARTIFACT_INVENTORY.md` or create `Docs\RUNTIME_ARTIFACT_SORTING_NOTES.md`.

Acceptance:

- Artifacts are grouped as state, logs, progress, manifests, pending publish, queue, validation evidence, generated reports.
- Include safe-to-delete or do-not-delete guidance where already known.
- Do not invent cleanup policies.

Validation:

```powershell
Select-String -Path Docs\RUNTIME_ARTIFACT_INVENTORY.md -Pattern "safe|delete|State|RunLogs|Pending"
```

## CLN-023 - Generated/Vendor Artifact Exclusion Review

Goal:

Check that docs and release scripts consistently exclude generated/vendor artifacts from release and audit scope.

Inspect:

- release builder/self-test docs
- `Docs\RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- `Docs\PACKAGING_DEPENDENCY_INVENTORY.md`
- `DesktopApp\tauri_shell\node_modules` references

Deliverable:

- `Docs\GENERATED_VENDOR_EXCLUSION_REVIEW.md`.

Acceptance:

- Confirm bundled runtime/tool payloads vs generated dependency folders are described correctly.
- Call out any ambiguous directories.
- No deletions.

Validation:

```powershell
Select-String -Path Docs\*.md,*.ps1 -Pattern "node_modules|__pycache__|RunLogs|Runtime|Tools|generated|exclude"
```

## CLN-024 - Test Suite Subsystem Sorting Refresh

Goal:

Refresh the test suite inventory after recent browser schedule smoke additions.

Inspect:

- `Docs\TEST_SUITE_SUBSYSTEM_INVENTORY.md`
- `DesktopApp\tests`

Deliverable:

- Update `Docs\TEST_SUITE_SUBSYSTEM_INVENTORY.md` or add a dated addendum.

Acceptance:

- New browser schedule smoke is included.
- Total test count expectations are either current or described as variable.
- Targeted test commands are accurate.

Validation:

```powershell
Get-ChildItem DesktopApp\tests -Filter "test_*.py"
python -m unittest discover -s DesktopApp\tests -p "test_webview_browser_*.py" -q
```

## CLN-025 - Browser Smoke Failure Triage Cheatsheet

Goal:

Create a quick guide for interpreting browser smoke failures.

Inspect:

- existing browser smoke runbook
- browser smoke support helper
- recent smoke wrappers

Deliverable:

- `Docs\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md`

Acceptance:

- Covers missing Node, missing Chrome/Edge, CDP connection timeout, console errors, backend route failures, assertion text mismatch, and skipped tests.
- States what failures do and do not prove.
- No code changes.

Validation:

```powershell
Test-Path Docs\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md
```

## CLN-026 - Operator Copy Vocabulary Consistency Pass

Goal:

Compare current operator-facing docs and WebView copy against the established vocabulary.

Inspect:

- `Docs\WEBVIEW_OPERATOR_COPY_AUDIT.md`
- WebView JS files
- main operator docs

Deliverable:

- `Docs\OPERATOR_COPY_CONSISTENCY_REVIEW.md`.

Acceptance:

- Identify inconsistent phrases for backend-owned, read-only, mutation guardrail, evidence-only, blocked, review, ready.
- Suggest wording fixes.
- Do not mass-edit UI copy.

Validation:

```powershell
Select-String -Path Docs\*.md,DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js -Pattern "Mutation guardrail|read-only|backend-owned|evidence-only"
```

## CLN-027 - Real-Media Validation Worksheet Sorting

Goal:

Review where real-media validation worksheets should live and how they should be named/compared.

Inspect:

- `Docs\RealMediaValidationRuns\README.md`
- `New-RealMediaValidationWorksheet.ps1`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`

Deliverable:

- Update `Docs\RealMediaValidationRuns\README.md` or create `Docs\REAL_MEDIA_VALIDATION_WORKSHEET_SORTING.md`.

Acceptance:

- Naming convention is clear.
- Personal path sensitivity is called out.
- Release package inclusion/exclusion is clear.
- No generated worksheets are created unless specifically requested.

Validation:

```powershell
Select-String -Path Docs\RealMediaValidationRuns\README.md,New-RealMediaValidationWorksheet.ps1 -Pattern "RealMediaValidation|worksheet|personal|release"
```

## CLN-028 - Changelog Navigation Health Review

Goal:

Review `Docs\REMEDIATION_CHANGELOG.md` for navigability and propose the next non-invasive cleanup.

Inspect:

- `Docs\REMEDIATION_CHANGELOG.md`
- `Docs\CHANGELOG_NAVIGATION_PROPOSAL.md`

Deliverable:

- `Docs\CHANGELOG_NAVIGATION_HEALTH_REVIEW.md`.

Acceptance:

- Do not split the changelog.
- Identify top-level entries that would benefit from index tags.
- Recommend a safe next step.

Validation:

```powershell
Select-String -Path Docs\REMEDIATION_CHANGELOG.md -Pattern "^## "
```

## CLN-029 - Markdown Link And File-Existence Sweep

Goal:

Find Markdown references to local docs/scripts that no longer exist.

Inspect:

- `Docs\*.md`
- `DesktopApp\tauri_shell\README.md`

Deliverable:

- `Docs\MARKDOWN_LINK_FILE_EXISTENCE_SWEEP.md`

Acceptance:

- List missing referenced files/scripts.
- List references that are intentionally external or examples.
- Do not auto-delete references.

Validation:

Use simple text search first. A scripted checker is allowed if it only reads files and writes the report.

```powershell
Select-String -Path Docs\*.md,DesktopApp\tauri_shell\README.md -Pattern "\.md|\.ps1|\.bat|\.py"
```

## CLN-030 - Admin Task Completion Board

Goal:

Create a single board showing remaining admin/documentation/review tasks that are safe for Claude or another assistant.

Inspect:

- all `Docs\CLAUDE_HANDOFF*.md`
- docs index
- this file

Deliverable:

- `Docs\ADMIN_TASK_COMPLETION_BOARD.md`

Acceptance:

- Columns: task, source doc, status, owner-suitable, risk, next validation.
- Separate Claude-safe from Codex-only tasks.
- Include a "do not delegate" section for risky runtime/media work.

Validation:

```powershell
Get-ChildItem Docs -Filter "CLAUDE_HANDOFF*.md"
Test-Path Docs\ADMIN_TASK_COMPLETION_BOARD.md
```

## Good First Batch For Claude

If Claude needs a starting subset, assign these first:

1. `CLN-003` - Stale Schedule Read-Only Wording Audit
2. `CLN-004` - Smoke Wrapper Boundary Text Audit
3. `CLN-006` - Root Script Inventory And Purpose Table
4. `CLN-010` - Local API Route Count Sync Audit
5. `CLN-024` - Test Suite Subsystem Sorting Refresh

These are useful, low-risk, and easy for Codex to verify afterward.


