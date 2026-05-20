# Claude Handoff: V5 Transition Support Tasks Round 3

Date: 2026-05-15

Repository:

`C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Purpose:

This is a fresh set of thirty low-dependency Claude tasks for the V5 Tauri/WebView2 transition. These tasks are meant to help Codex move faster later by improving documentation freshness, inventory accuracy, operator guidance, smoke-test discoverability, and static review coverage. They should not change production media behavior.

The current engineering direction remains:

- V4 is the known-good backup and must not be touched.
- Tk remains the trusted fallback.
- WebView/Tauri remains a preview path until real-media validation proves daily-driver readiness.
- The Python backend owns all mutation, media processing, queue control, settings persistence, publish/drain, rename apply, and diagnostics allowlist behavior.
- Claude should mostly produce Markdown, inventories, audits, and small wrapper/documentation corrections.

---

## Non-Negotiable Rules For Claude

1. Do not touch `MediaPipelineRemuxEncodeAIO_V4`.
2. Do not remove, weaken, freeze, or replace the Tk desktop app.
3. Do not change FFmpeg, ffprobe, subtitle conversion, audio routing, remux/encode routing, queue launch, pending publish drain, rename apply, settings persistence, source/scratch/output safety, or Network lifecycle behavior.
4. Do not add frontend-owned filesystem mutation or frontend-only business logic.
5. Do not change Local API route contracts, command journal semantics, strict JSON handling, duplicate-command guards, close-readiness, release gates, or backend ownership boundaries.
6. Keep Network mode read-only unless the task is only documenting future work.
7. Prefer Markdown-only edits. If code inspection is needed, read and report; do not patch runtime behavior.
8. Do not run real media, FFmpeg, publish drains, rename apply, settings save, pipeline start, audit start, or CSV rerun commands.
9. Keep each task independently reviewable.
10. End each task with files inspected, files changed, validation run, findings, open questions, and risk.

---

## Suggested Baseline Validation

Before doing any broad doc updates:

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
.\DesktopApp\tauri_shell\Test-TauriShell-Build.ps1 -SkipLinkCheck
```

If either fails, stop and document the failure. Do not keep editing broad documentation from a broken baseline.

For docs-only tasks, use focused checks such as:

```powershell
Select-String -Path Docs\*.md -Pattern "<term>"
Get-ChildItem Docs -Filter "*.md" | Select-Object Name
Test-Path Docs\<expected-file>.md
```

Use the bundled PowerShell 7 host for release checks:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

---

## Task Index

| ID | Title | Type | Risk | Primary Output |
|---|---|---:|---:|---|
| CLN3-001 | Recent Launch Proof Handoff Docs Sync | Docs audit | Low | Updated doc note or findings |
| CLN3-002 | Sample Validation Record Evidence Operator Guide | Docs | Low | New short operator guide |
| CLN3-003 | Launch/Queue Smoke Wrapper Boundary Refresh | Docs/static | Low | Wrapper/doc wording audit |
| CLN3-004 | WebView Global Export Recount | Inventory | Low | Updated export inventory note |
| CLN3-005 | DOM ID Inventory Delta For Launch/Sample Validation | Inventory | Low | Updated DOM ID note |
| CLN3-006 | Test Coverage Matrix Freshness Pass | Docs audit | Low | Updated coverage notes |
| CLN3-007 | Docs Index New-Handoff Registration | Docs | Low | `DOCS_INDEX.md` delegation entry |
| CLN3-008 | Real-Media Playbook Launch Evidence Pass | Docs | Low | Updated playbook wording |
| CLN3-009 | Validation Ladder Smoke Ordering Check | Docs audit | Low | Runbook freshness note |
| CLN3-010 | Tauri Asset Gate Fragment Audit | Review | Low | Fragment/gate findings |
| CLN3-011 | Sample Validation Payload Schema Reference | Docs | Low | Schema reference section/doc |
| CLN3-012 | Command Result Owner Mapping Freshness | Review | Low | Owner mapping findings |
| CLN3-013 | Browser Smoke Mutation Matrix Refresh | Docs | Low | Updated mutation matrix |
| CLN3-014 | Operator Manual Test Script Launch Update | Docs | Low | Manual test script update |
| CLN3-015 | Changelog Latest-Entries Table Addendum | Docs | Low | Navigation addendum |
| CLN3-016 | Release Self-Test Wrapper Inventory Recheck | Docs audit | Low | Layout audit addendum |
| CLN3-017 | Root Script Boundary Text Consistency | Docs/static | Low | Boundary wording findings |
| CLN3-018 | Sample Validation Log Privacy Review | Review | Low | Privacy/path leakage note |
| CLN3-019 | Generated Worksheet Privacy Review | Review | Low | Worksheet privacy note |
| CLN3-020 | Real-Media Evidence Packet Field Glossary | Docs | Low | Glossary addendum |
| CLN3-021 | Queue/Completed/Pending Proof Chain Glossary | Docs | Low | Operator glossary additions |
| CLN3-022 | WebView Read-Only Claim Audit | Review | Low | Read-only wording findings |
| CLN3-023 | Pending Publish Real-Media Proof Doc Crosscheck | Docs audit | Low | Pending proof findings |
| CLN3-024 | Rename Docs Current-State Recheck | Docs audit | Low | Rename freshness addendum |
| CLN3-025 | Settings Builder Visibility Recheck | Docs audit | Low | Settings coverage addendum |
| CLN3-026 | Network Read-Only Status Recheck | Docs audit | Low | Network wording addendum |
| CLN3-027 | Browser Smoke Failure Cheatsheet Update | Docs | Low | Cheatsheet addendum |
| CLN3-028 | Docs Dead/Archive Classification Refresh | Docs audit | Low | Updated archive classification |
| CLN3-029 | Claude Backlog Status Board Round 3 | Admin | Low | Status board addendum |
| CLN3-030 | Return-To-Transition Summary | Admin | Low | Final handoff summary |

---

## CLN3-001 - Recent Launch Proof Handoff Docs Sync

**Goal:** Confirm active docs describe the current Launch Real-Media Sample Proof Handoff accurately, including generated worksheet evidence and Sample Validation record evidence.

**Scope:**

- `Docs\TLDR.md`
- `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`
- `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`

**Allowed changes:** Documentation wording only.

**Validation:**

```powershell
Select-String -Path Docs\TLDR.md,Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md,Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md,Docs\WEBVIEW_SMOKE_TEST_CATALOG.md,Docs\BROWSER_SMOKE_TEST_RUNBOOK.md -Pattern "Sample Validation record evidence|Generated worksheet evidence|Launch Real-Media"
```

**Do not touch:** `launchView.js`, backend API code, tests.

**Deliverable:** Updated wording or a short findings note stating all docs are current.

---

## CLN3-002 - Sample Validation Record Evidence Operator Guide

**Goal:** Create a short operator-focused guide explaining what Sample Validation records prove and what they do not prove.

**Scope:**

- New `Docs\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- Existing `Docs\V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md` as reference
- Existing `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` as reference

**Allowed changes:** New Markdown doc and optional index entry.

**Validation:**

```powershell
Test-Path Docs\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md
Select-String -Path Docs\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md -Pattern "does not accept|does not launch|read-only|operator evidence"
```

**Do not touch:** Sample validation API implementation.

**Deliverable:** A concise guide with sections: purpose, when to record, stale/current/review meaning, safe next action, and mutation boundary.

---

## CLN3-003 - Launch/Queue Smoke Wrapper Boundary Refresh

**Goal:** Verify the root Launch/Queue browser smoke wrapper boundary text matches current behavior after worksheet and validation-record evidence were added.

**Scope:**

- `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1`
- `Docs\archive\admin-audits\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md`
- `Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`

**Allowed changes:** Wrapper `Write-Host` boundary text and docs only if stale.

**Validation:**

```powershell
Select-String -Path .\SmokeTests\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1 -Pattern "Boundary:"
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold.TauriShellScaffoldTests.test_webview_browser_launch_queue_readiness_smoke_script_is_bounded -q
```

**Do not touch:** Browser smoke Python scenario or WebView JS.

**Deliverable:** Boundary-text findings and any exact wording updates.

---

## CLN3-004 - WebView Global Export Recount

**Goal:** Recount WebView namespace and flat compatibility exports after recent Launch/Home helper exports.

**Scope:**

- `Docs\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js` for read-only count

**Allowed changes:** Documentation inventory only.

**Validation:**

```powershell
Select-String -Path Docs\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md -Pattern "crossPageContextView|launchView|flat"
```

**Do not touch:** JavaScript files.

**Deliverable:** Updated counts or a findings note showing exact count method.

---

## CLN3-005 - DOM ID Inventory Delta For Launch/Sample Validation

**Goal:** Check whether `WEBVIEW_DOM_ID_INVENTORY.md` needs updates for current Launch and Home Sample Validation panels.

**Scope:**

- `Docs\WEBVIEW_DOM_ID_INVENTORY.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js`

**Allowed changes:** Documentation inventory only.

**Validation:**

```powershell
Select-String -Path Docs\WEBVIEW_DOM_ID_INVENTORY.md -Pattern "launch-real-media-proof|sample-validation"
```

**Do not touch:** HTML or JS.

**Deliverable:** Inventory update or list of missing DOM IDs for Codex.

---

## CLN3-006 - Test Coverage Matrix Freshness Pass

**Goal:** Confirm `TEST_COVERAGE_MATRIX.md` reflects the current tests for Launch, Home, Sample Validation, and browser smokes.

**Scope:**

- `Docs\TEST_COVERAGE_MATRIX.md`
- `DesktopApp\tests\test_webview_browser_launch_queue_readiness_smoke.py`
- `DesktopApp\tests\test_webview_browser_sample_validation_smoke.py`
- `DesktopApp\tests\test_webview_browser_home_live_state_smoke.py`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\TEST_COVERAGE_MATRIX.md -Pattern "Launch|Sample Validation|Generated worksheet|validation-record"
```

**Do not touch:** Test code.

**Deliverable:** Coverage matrix correction or confirmation.

---

## CLN3-007 - Docs Index New-Handoff Registration

**Goal:** Register this CLN3 handoff document in `DOCS_INDEX.md` under Delegation And Archive Docs.

**Scope:**

- `Docs\DOCS_INDEX.md`
- `Docs\CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md`

**Allowed changes:** Documentation index only.

**Validation:**

```powershell
Select-String -Path Docs\DOCS_INDEX.md -Pattern "CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3"
```

**Do not touch:** Any completed handoff docs except for cross-reference wording if required.

**Deliverable:** One active entry in the index.

---

## CLN3-008 - Real-Media Playbook Launch Evidence Pass

**Goal:** Ensure the real-media validation playbook tells the operator exactly where to inspect worksheet and validation-record evidence before Launch.

**Scope:**

- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md` if CLN3-002 exists

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md -Pattern "Launch|worksheet|validation-record|Sample Validation record"
```

**Do not touch:** WebView code or sample-validation API.

**Deliverable:** Playbook update or findings note.

---

## CLN3-009 - Validation Ladder Smoke Ordering Check

**Goal:** Check whether `VALIDATION_LADDER_RUNBOOK.md` lists current root smoke wrappers in a useful order.

**Scope:**

- `Docs\VALIDATION_LADDER_RUNBOOK.md`
- Root `Test-WebView*.ps1`
- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Get-ChildItem -File -Filter "Test-WebView*.ps1" | Sort-Object Name | Select-Object Name
Select-String -Path Docs\VALIDATION_LADDER_RUNBOOK.md -Pattern "Test-WebViewBrowserLaunchQueueReadinessSmoke|Test-WebViewBrowserSampleValidationSmoke"
```

**Do not touch:** Root wrapper implementation.

**Deliverable:** Updated ordering note or confirmation.

---

## CLN3-010 - Tauri Asset Gate Fragment Audit

**Goal:** Verify the Tauri pre-window asset gate checks meaningful fragments for the current WebView surfaces without becoming brittle.

**Scope:**

- `DesktopApp\tauri_shell\src-tauri\src\lib.rs`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
- `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

**Allowed changes:** Documentation/finding note only. If a fragment is clearly stale, report it for Codex.

**Validation:**

```powershell
Select-String -Path DesktopApp\tauri_shell\src-tauri\src\lib.rs -Pattern "validate_backend_web_ui|fragment|asset"
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

**Do not touch:** Rust code unless separately assigned.

**Deliverable:** `Docs\TAURI_ASSET_GATE_FRAGMENT_AUDIT.md` or an addendum to an existing Tauri doc.

---

## CLN3-011 - Sample Validation Payload Schema Reference

**Goal:** Document the important fields in `/api/sample-validation` read, preview, append, worksheet, pilot-plan, evidence-packet, and reconciliation payloads.

**Scope:**

- `DesktopApp\mediapipeline_desktop_app\application\facade_sample_validation_policy.py`
- `Docs\V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md`
- New optional `Docs\SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md -Pattern "desktop_sample_validation|sample_validation_record|desktop_real_media"
```

**Do not touch:** API code.

**Deliverable:** Schema reference with mutation-boundary note.

---

## CLN3-012 - Command Result Owner Mapping Freshness

**Goal:** Confirm recent commands and sample-validation entries still map to correct owner pages.

**Scope:**

- `Docs\COMMAND_OWNERSHIP_MATRIX.md`
- `Docs\COMMAND_HISTORY_CONSISTENCY_AUDIT.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\COMMAND_OWNERSHIP_MATRIX.md,Docs\COMMAND_HISTORY_CONSISTENCY_AUDIT.md -Pattern "sample_validation|pipeline.start|settings.save|rename.apply"
```

**Do not touch:** Command-history JS or backend command journal.

**Deliverable:** Findings note or doc correction.

---

## CLN3-013 - Browser Smoke Mutation Matrix Refresh

**Goal:** Ensure `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` describes all browser smokes and their allowed/non-allowed effects.

**Scope:**

- `Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`
- Root `Test-WebViewBrowser*.ps1`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Get-ChildItem -File -Filter "Test-WebViewBrowser*.ps1" | Select-Object Name
Select-String -Path Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md -Pattern "Does not|POST|mutation"
```

**Do not touch:** Smoke code.

**Deliverable:** Updated matrix or confirmation.

---

## CLN3-014 - Operator Manual Test Script Launch Update

**Goal:** Update the manual WebView operator test script so a human can verify Launch worksheet and validation-record evidence.

**Scope:**

- `Docs\WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md -Pattern "Launch|worksheet|validation record|Sample Validation"
```

**Do not touch:** WebView code.

**Deliverable:** Manual Launch verification steps.

---

## CLN3-015 - Changelog Latest-Entries Table Addendum

**Goal:** Make the top of `REMEDIATION_CHANGELOG.md` easier to scan without splitting the file.

**Scope:**

- `Docs\REMEDIATION_CHANGELOG.md`
- `Docs\archive\admin-audits\CHANGELOG_NAVIGATION_HEALTH_REVIEW.md`
- `Docs\CHANGELOG_NAVIGATION_PROPOSAL.md`

**Allowed changes:** Documentation only. Avoid large rewrites.

**Validation:**

```powershell
Get-Content Docs\REMEDIATION_CHANGELOG.md -TotalCount 80
```

**Do not touch:** Historical changelog entries except to add a small navigation table or latest-entry note.

**Deliverable:** Small top-level "Latest Entries" table or a proposal note if not safe.

---

## CLN3-016 - Release Self-Test Wrapper Inventory Recheck

**Goal:** Check that release self-test layout expectations include all `SmokeTests/` wrappers and docs added during recent V5 transition work.

**Scope:**

- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `Docs\RELEASE_SELF_TEST_LAYOUT_AUDIT.md`
- `Docs\ROOT_SCRIPT_INVENTORY.md`

**Allowed changes:** Documentation only unless a missing doc/script line is clearly a release self-test omission and is separately approved.

**Validation:**

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

**Do not touch:** Release builder or packaging behavior.

**Deliverable:** Audit addendum with pass/fail and missing candidates.

---

## CLN3-017 - Root Script Boundary Text Consistency

**Goal:** Confirm root wrapper boundary text uses consistent terms: `temporary local API`, `backend-owned`, `read-only`, `does not process media`, and `skips cleanly`.

**Scope:**

- Root `Test-*.ps1`
- `Docs\archive\admin-audits\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md`

**Allowed changes:** Boundary text and docs only.

**Validation:**

```powershell
Select-String -Path .\Test-*.ps1 -Pattern "Boundary:"
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

**Do not touch:** Test implementation logic.

**Deliverable:** Consistency findings and small wording fixes if needed.

---

## CLN3-018 - Sample Validation Log Privacy Review

**Goal:** Review docs and sample-validation guidance for accidental encouragement to commit personal paths from `State\Validation\sample_validation_log.jsonl`.

**Scope:**

- `Docs\V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md` if present
- `.gitignore` only for read-only inspection

**Allowed changes:** Documentation warnings only.

**Validation:**

```powershell
Select-String -Path Docs\*.md -Pattern "sample_validation_log|personal paths|Validation"
```

**Do not touch:** `.gitignore` unless separately assigned.

**Deliverable:** Privacy review note and doc wording if needed.

---

## CLN3-019 - Generated Worksheet Privacy Review

**Goal:** Confirm generated worksheet docs clearly state worksheets may contain personal paths and should stay out of clean release packages.

**Scope:**

- `Docs\RealMediaValidationRuns\README.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\archive\admin-audits\GENERATED_VENDOR_EXCLUSION_REVIEW.md`
- Release packaging docs for read-only reference

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\RealMediaValidationRuns\README.md,Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md,Docs\archive\admin-audits\GENERATED_VENDOR_EXCLUSION_REVIEW.md -Pattern "personal paths|excluded|release"
```

**Do not touch:** Release builder.

**Deliverable:** Privacy/exclusion findings.

---

## CLN3-020 - Real-Media Evidence Packet Field Glossary

**Goal:** Explain evidence-packet terms like Queue route proof, Completed output proof, Diagnostics proof, Pending Publish posture, stop condition, and safe next action.

**Scope:**

- `Docs\OPERATOR_GLOSSARY.md`
- `Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\OPERATOR_GLOSSARY.md -Pattern "Queue route proof|Completed output|Pending Publish posture|stop condition"
```

**Do not touch:** Evidence-packet code.

**Deliverable:** Glossary additions or a new short glossary addendum.

---

## CLN3-021 - Queue/Completed/Pending Proof Chain Glossary

**Goal:** Clarify how Queue, Completed, and Pending Publish evidence relate without implying any one panel alone proves real-media acceptance.

**Scope:**

- `Docs\OPERATOR_GLOSSARY.md`
- `Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\OPERATOR_GLOSSARY.md,Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md,Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md -Pattern "proof|acceptance|Pending Publish|Completed"
```

**Do not touch:** Completed/Pending WebView code.

**Deliverable:** Proof-chain wording update.

---

## CLN3-022 - WebView Read-Only Claim Audit

**Goal:** Find active docs claiming a page is read-only where the page now has backend-owned mutation controls, and correct wording to say "read-only panel" or "backend-owned command" as appropriate.

**Scope:**

- `Docs\*.md`
- `Docs\DesktopApp\*.md`

**Allowed changes:** Documentation wording only.

**Validation:**

```powershell
rg -n "read-only|readonly|does not mutate|backend-owned" Docs -g "*.md"
```

**Do not touch:** Code.

**Deliverable:** Wording fixes or findings table.

---

## CLN3-023 - Pending Publish Real-Media Proof Doc Crosscheck

**Goal:** Check whether pending-publish docs explain how parked outputs interact with Sample Validation, Completed proof, and Launch readiness evidence.

**Scope:**

- `Docs\archive\admin-audits\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md`
- `Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\archive\admin-audits\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md,Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md,Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md -Pattern "Sample Validation|Completed|Pending Publish|parked"
```

**Do not touch:** Pending Publish code or drain behavior.

**Deliverable:** Crosscheck note and wording updates if needed.

---

## CLN3-024 - Rename Docs Current-State Recheck

**Goal:** Confirm Rename docs still match the TV/movie rename tool after recent season logic, scrub filters, sidecar tagging, and apply-readiness work.

**Scope:**

- `Docs\archive\admin-audits\RENAME_DOCS_FRESHNESS_REVIEW.md`
- `Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md`
- `Docs\TLDR.md`
- Rename tests for read-only reference

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\archive\admin-audits\RENAME_DOCS_FRESHNESS_REVIEW.md,Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md,Docs\TLDR.md -Pattern "season|movie|scrub|sidecar|Apply Readiness"
```

**Do not touch:** Rename service or WebView code.

**Deliverable:** Freshness addendum or confirmation.

---

## CLN3-025 - Settings Builder Visibility Recheck

**Goal:** Check whether Settings docs still reflect structured builders for video/remux/encode, audio, subtitles, pending publish, and raw-only fields.

**Scope:**

- `Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- `Docs\SETTINGS_KEY_OWNERSHIP_MAP.md`
- `Docs\SETTINGS_RAW_KEY_TRIAGE.md`
- `Docs\TLDR.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md,Docs\SETTINGS_KEY_OWNERSHIP_MAP.md,Docs\SETTINGS_RAW_KEY_TRIAGE.md -Pattern "audio|subtitle|pending|raw-only|builder"
```

**Do not touch:** Settings UI/backend code.

**Deliverable:** Visibility/freshness note.

---

## CLN3-026 - Network Read-Only Status Recheck

**Goal:** Reconfirm all docs still state WebView Network is read-only and no coordinator/worker lifecycle controls exist there.

**Scope:**

- `Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`
- `Docs\archive\admin-audits\NETWORK_READONLY_WORDING_AUDIT.md`
- `Docs\NETWORK_UX_IMPROVEMENTS.md`
- `Docs\TLDR.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md,Docs\archive\admin-audits\NETWORK_READONLY_WORDING_AUDIT.md,Docs\NETWORK_UX_IMPROVEMENTS.md,Docs\TLDR.md -Pattern "read-only|start|stop|coordinator|worker"
```

**Do not touch:** Network code.

**Deliverable:** Network wording addendum.

---

## CLN3-027 - Browser Smoke Failure Cheatsheet Update

**Goal:** Update smoke failure triage docs with the latest Launch/Queue readiness fixture shape and validation-record evidence failure modes.

**Scope:**

- `Docs\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md`
- `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`
- `DesktopApp\tests\test_webview_browser_launch_queue_readiness_smoke.py` for read-only reference

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md,Docs\BROWSER_SMOKE_TEST_RUNBOOK.md -Pattern "LaunchQueue|Launch/Queue|validation record|worksheet"
```

**Do not touch:** Smoke runner code.

**Deliverable:** Failure triage addendum.

---

## CLN3-028 - Docs Dead/Archive Classification Refresh

**Goal:** Refresh dead/archive documentation classification now that more Claude handoff docs and recent transition docs exist.

**Scope:**

- `Docs\archive\admin-audits\DOCS_DEAD_MARKDOWN_AUDIT.md`
- `Docs\DOCS_INDEX.md`
- `Docs\CLAUDE_HANDOFF*.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Get-ChildItem Docs -Filter "*.md" | Select-Object Name
Select-String -Path Docs\archive\admin-audits\DOCS_DEAD_MARKDOWN_AUDIT.md -Pattern "CLAUDE_HANDOFF|Archive|Keep Active"
```

**Do not touch:** Move/delete no files.

**Deliverable:** Classification update or findings note. No file moves.

---

## CLN3-029 - Claude Backlog Status Board Round 3

**Goal:** Add CLN3 task tracking to the admin task completion board or create a round-3 status board.

**Scope:**

- `Docs\archive\completed-checklists\ADMIN_TASK_COMPLETION_BOARD.md`
- `Docs\CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md`

**Allowed changes:** Documentation/admin status only.

**Validation:**

```powershell
Select-String -Path Docs\archive\completed-checklists\ADMIN_TASK_COMPLETION_BOARD.md -Pattern "CLN3"
```

**Do not touch:** Completed C, C-ADM, CLN, or CLN2 records except to cross-reference round 3.

**Deliverable:** A table listing all 30 CLN3 tasks with status `Pending` unless completed.

---

## CLN3-030 - Return-To-Transition Summary

**Goal:** After Claude completes any subset of CLN3 tasks, produce a concise return-to-Codex summary that points back to the main V5 transition work.

**Scope:**

- New or updated `Docs\archive\old-ai-directives\CLAUDE_HANDOFF_ROUND3_COMPLETION_SUMMARY.md`
- Any CLN3 output docs produced by Claude
- `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md` for context only

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Test-Path Docs\archive\old-ai-directives\CLAUDE_HANDOFF_ROUND3_COMPLETION_SUMMARY.md
Select-String -Path Docs\archive\old-ai-directives\CLAUDE_HANDOFF_ROUND3_COMPLETION_SUMMARY.md -Pattern "Return to transition|Next Codex batch|Completed|Blocked"
```

**Do not touch:** Runtime code, tests, release scripts.

**Deliverable:** Summary with completed tasks, changed files, validation run, unresolved risks, and recommended next Codex implementation batch. The final recommendation must explicitly return to the original V5 Tauri/WebView2 transition.


