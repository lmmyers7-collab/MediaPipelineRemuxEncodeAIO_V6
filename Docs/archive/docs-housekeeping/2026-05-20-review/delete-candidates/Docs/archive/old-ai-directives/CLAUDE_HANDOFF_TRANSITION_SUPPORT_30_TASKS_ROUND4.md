# Claude Handoff: V5 Transition Support Tasks Round 4

Date: 2026-05-15

Repository:

`C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Purpose:

This is another set of thirty low-dependency Claude tasks for the V5 Tauri/WebView2 transition. Round 4 is focused on administrative cleanup, documentation freshness, inventory verification, operator guidance, and test-discoverability after the latest WebView parity work around Launch/Queue/Pending scope confidence.

Claude should treat these as support tasks for Codex, not as runtime remediation. The goal is to make later Codex verification faster and safer without changing production behavior.

Current context:

- V4 remains the known-good backup and must not be touched.
- Tk remains the trusted fallback.
- WebView/Tauri remains a preview path, not the daily-driver replacement.
- The Python backend owns all mutation, media processing, queue control, pending-publish drain, rename apply, settings persistence, diagnostics allowlists, and process lifecycle behavior.
- Recent WebView work added Queue `Backend Launch Scope Preview` and Pending Publish `Backend Drain Scope Preview` panels. These are read-only evidence surfaces that clarify backend route authority versus visible table filters and selected rows.

---

## Non-Negotiable Rules For Claude

1. Do not touch `MediaPipelineRemuxEncodeAIO_V4`.
2. Do not remove, weaken, freeze, or replace the Tk desktop app.
3. Do not change FFmpeg, ffprobe, subtitle conversion, audio routing, remux/encode routing, queue launch, pending-publish drain, rename apply, settings persistence, source/scratch/output safety, Network lifecycle behavior, or media policy.
4. Do not add frontend-owned filesystem mutation or frontend-only mutation logic.
5. Do not change Local API route contracts, command journal semantics, strict JSON handling, duplicate-command guards, close-readiness, release gates, or backend ownership boundaries.
6. Do not run real media, FFmpeg, publish drains, rename apply, settings save, pipeline start, audit start, CSV rerun, or destructive cleanup commands.
7. Prefer Markdown-only edits. If source inspection is needed, read and report findings; do not patch runtime code unless a task explicitly asks for a static test/doc-only correction.
8. Keep Network mode read-only in all wording unless documenting future work.
9. Keep each task independently reviewable.
10. End every completed task with: files inspected, files changed, validation run, findings, open questions, and risk.

---

## Suggested Baseline Validation

Before doing broad documentation updates:

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
.\DesktopApp\tauri_shell\Test-TauriShell-Build.ps1 -SkipLinkCheck
```

If either fails, stop and document the failure. Do not keep editing broad transition docs from a broken baseline.

For docs-only tasks, prefer focused checks:

```powershell
Get-ChildItem Docs -Filter "*.md" | Select-Object Name
Select-String -Path Docs\*.md -Pattern "<term>"
Test-Path Docs\<expected-file>.md
```

For root-wrapper or release-boundary tasks, use the bundled PowerShell 7 host:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

---

## Completion Note Format

Claude should finish each task with:

```text
Task ID:
Files inspected:
Files changed:
Validation:
Findings:
Open questions:
Risk:
```

---

## Task Index

| ID | Title | Type | Risk | Primary Output |
|---|---|---:|---:|---|
| CLN4-001 | Queue Backend Scope Preview Docs Sync | Docs audit | Low | Updated docs or freshness findings |
| CLN4-002 | Pending Backend Scope Preview Docs Sync | Docs audit | Low | Updated docs or freshness findings |
| CLN4-003 | Scope Preview Operator Mini-Guide | Docs | Low | New short operator guide section/doc |
| CLN4-004 | Launch/Queue/Pending Scope Vocabulary Audit | Review | Low | Vocabulary findings or wording patch |
| CLN4-005 | WebView DOM ID Inventory Scope Delta | Inventory | Low | Inventory addendum |
| CLN4-006 | WebView Global Export Count Recheck | Inventory | Low | Updated count or findings |
| CLN4-007 | Browser Smoke Catalog Scope-Preview Refresh | Docs | Low | Smoke catalog update/finding |
| CLN4-008 | Browser Smoke Mutation Matrix Scope Refresh | Docs | Low | Mutation matrix update/finding |
| CLN4-009 | Test Coverage Matrix Scope-Preview Refresh | Docs | Low | Coverage matrix update/finding |
| CLN4-010 | Launch Queue Readiness Smoke Readability Pass | Docs/test review | Low | Findings only unless wording doc update |
| CLN4-011 | Pending Drain Guard Smoke Readability Pass | Docs/test review | Low | Findings only unless wording doc update |
| CLN4-012 | Large Table Smoke Scope Boundary Review | Docs/test review | Low | Findings only unless wording doc update |
| CLN4-013 | Scope Panels In Manual Operator Test Script | Docs | Low | Manual test script update |
| CLN4-014 | Scope Panels In Validation Ladder Runbook | Docs | Low | Runbook update |
| CLN4-015 | Queue/Pending Scope In TLDR | Docs | Low | TLDR update or confirmation |
| CLN4-016 | Current Plan Latest Checkpoint Prune/Sync | Docs | Low | Plan update or note |
| CLN4-017 | Changelog Latest-Entries Navigation Update | Docs | Low | Changelog top table update |
| CLN4-018 | Docs Index Handoff Registration | Docs | Low | `DOCS_INDEX.md` entry |
| CLN4-019 | No-Touch Boundary Register Scope Review | Docs audit | Low | Boundary register note/update |
| CLN4-020 | Command Ownership Matrix Scope Crosscheck | Docs audit | Low | Crosscheck findings |
| CLN4-021 | Local API Evidence/Mutation Matrix Scope Crosscheck | Docs audit | Low | Crosscheck findings |
| CLN4-022 | API Route Inventory Scope Crosscheck | Docs audit | Low | Crosscheck findings |
| CLN4-023 | Pending Publish Failure Playbook Scope Update | Docs | Low | Playbook update/finding |
| CLN4-024 | Completed/Pending Proof Docs Crosscheck | Docs audit | Low | Findings |
| CLN4-025 | Diagnostics Read-Only Target Runbook Crosslink | Docs | Low | Crosslink update/finding |
| CLN4-026 | Operator Glossary Scope Terms | Docs | Low | Glossary additions |
| CLN4-027 | Screenshot/Image Reference Staleness Sweep | Admin audit | Low | Findings |
| CLN4-028 | Real-Media Validation Playbook Scope Evidence Pass | Docs | Low | Playbook update/finding |
| CLN4-029 | Round 4 Status Board Addendum | Admin | Low | Status board note |
| CLN4-030 | Return-To-Transition Summary For Codex | Admin | Low | Final handoff summary |

---

## CLN4-001 - Queue Backend Scope Preview Docs Sync

**Goal:** Confirm active docs mention the Queue `Backend Launch Scope Preview` accurately.

**Inspect:**

- `Docs\TLDR.md`
- `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- `Docs\TEST_COVERAGE_MATRIX.md`
- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`

**Allowed changes:** Documentation wording only.

**Acceptance criteria:**

- The docs say Queue filters and selected rows are display/detail context only.
- The docs say `/api/pipeline/start` remains backend-owned.
- The docs do not imply WebView can narrow launch scope or mutate queue state.

**Validation:**

```powershell
Select-String -Path Docs\TLDR.md,Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md,Docs\TEST_COVERAGE_MATRIX.md,Docs\WEBVIEW_SMOKE_TEST_CATALOG.md -Pattern "Backend Launch Scope Preview|Queue filters|/api/pipeline/start"
```

---

## CLN4-002 - Pending Backend Scope Preview Docs Sync

**Goal:** Confirm active docs mention the Pending Publish `Backend Drain Scope Preview` accurately.

**Inspect:**

- `Docs\TLDR.md`
- `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- `Docs\TEST_COVERAGE_MATRIX.md`
- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`
- `Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`

**Allowed changes:** Documentation wording only.

**Acceptance criteria:**

- The docs say Pending filters and selected rows do not narrow backend drain scope.
- The docs say `drain_pending_pushes` remains backend-owned.
- The docs do not imply the scope preview publishes, repairs, rewrites, deletes, or moves files.

**Validation:**

```powershell
Select-String -Path Docs\*.md -Pattern "Backend Drain Scope Preview|drain_pending_pushes|Pending filters"
```

---

## CLN4-003 - Scope Preview Operator Mini-Guide

**Goal:** Create a short operator-facing guide explaining what the new Queue/Pending scope preview panels mean.

**Preferred output:** `Docs\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md`

**Include:**

- What the Queue Backend Launch Scope Preview proves.
- What it does not prove.
- What the Pending Backend Drain Scope Preview proves.
- What it does not prove.
- How to interpret filters, selected rows, render caps, and command-history evidence.
- Safe next actions when hidden blocked/review rows exist.

**Allowed changes:** New Markdown doc and optional `DOCS_INDEX.md` entry.

**Validation:**

```powershell
Test-Path Docs\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md
Select-String -Path Docs\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md -Pattern "selected row|filters|backend-owned|Mutation guardrail"
```

---

## CLN4-004 - Launch/Queue/Pending Scope Vocabulary Audit

**Goal:** Check that scope-related wording uses consistent operator vocabulary.

**Inspect:**

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `Docs\TERMINOLOGY_CONSISTENCY_GUIDE.md`
- `Docs\archive\admin-audits\WEBVIEW_OPERATOR_COPY_AUDIT.md`

**Allowed changes:** Prefer findings only. Wording-only docs changes are allowed. Do not patch JS unless Codex explicitly asks later.

**Acceptance criteria:**

- Terms like `backend-owned`, `read-only`, `display filter`, `selected row`, `Mutation guardrail`, and `scope` are used consistently.
- Any risky or ambiguous phrase is listed with exact file and line.

**Validation:**

```powershell
Select-String -Path DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js,DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js,DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js -Pattern "scope|backend-owned|Mutation guardrail|selected row"
```

---

## CLN4-005 - WebView DOM ID Inventory Scope Delta

**Goal:** Verify `WEBVIEW_DOM_ID_INVENTORY.md` contains all newly added scope-preview IDs.

**Inspect:**

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `Docs\WEBVIEW_DOM_ID_INVENTORY.md`

**Expected IDs:**

- `queue-backend-scope-status`
- `queue-backend-scope-summary`
- `queue-backend-scope-rows`
- `queue-backend-scope-legend`
- `pending-backend-scope-status`
- `pending-backend-scope-summary`
- `pending-backend-scope-rows`
- `pending-backend-scope-legend`

**Allowed changes:** Inventory doc only.

**Validation:**

```powershell
Select-String -Path Docs\WEBVIEW_DOM_ID_INVENTORY.md -Pattern "queue-backend-scope|pending-backend-scope"
```

---

## CLN4-006 - WebView Global Export Count Recheck

**Goal:** Recount flat `window.*` exports after the scope-preview additions and update or confirm `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`.

**Inspect:**

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js`
- `Docs\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`

**Allowed changes:** Inventory doc only.

**Suggested command:**

```powershell
Select-String -Path DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js -Pattern "window\.[A-Za-z0-9_]+\\s*=" | Measure-Object
```

**Acceptance criteria:**

- `queueView.js` and `pendingPublishView.js` export counts are current.
- The total flat export count is current.
- Any mismatch is documented.

---

## CLN4-007 - Browser Smoke Catalog Scope-Preview Refresh

**Goal:** Ensure `WEBVIEW_SMOKE_TEST_CATALOG.md` accurately describes which browser smokes prove the new scope panels.

**Inspect:**

- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`
- `Test-WebViewBrowserLargeTableSmoke.ps1`
- `Test-WebViewBrowserPendingDrainGuardSmoke.ps1`
- `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Large Table smoke mentions Queue Backend Launch Scope Preview and Pending Backend Drain Scope Preview.
- Pending Drain Guard smoke mentions Backend Drain Scope Preview.
- Launch/Queue Readiness smoke mentions Queue Backend Launch Scope Preview.

---

## CLN4-008 - Browser Smoke Mutation Matrix Scope Refresh

**Goal:** Confirm `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` describes the new scope-preview checks without overstating them.

**Inspect:**

- `Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Scope-preview checks are listed as rendering/evidence checks only.
- The matrix still clearly states no pipeline start, drain, publish, rename, settings save, or media touch happens.

---

## CLN4-009 - Test Coverage Matrix Scope-Preview Refresh

**Goal:** Confirm `TEST_COVERAGE_MATRIX.md` reflects new browser coverage for Queue/Pending scope previews.

**Inspect:**

- `Docs\TEST_COVERAGE_MATRIX.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Queue section lists Backend Launch Scope Preview coverage.
- Pending Publish section lists Backend Drain Scope Preview coverage.
- Gaps remain honest: actual drain and real pipeline launch are not smoke-exercised.

---

## CLN4-010 - Launch Queue Readiness Smoke Readability Pass

**Goal:** Review the browser smoke that covers Launch/Queue readiness for readability and future maintainability.

**Inspect:**

- `DesktopApp\tests\test_webview_browser_launch_queue_readiness_smoke.py`

**Allowed changes:** Findings only, unless fixing comments/docs. Do not change assertions unless Codex asks.

**Questions to answer:**

- Are the scope-preview assertions easy to find?
- Are helper names understandable?
- Does the smoke clearly prevent mutation POSTs?
- Is failure output likely to be actionable?

**Output:** Findings section in task completion note or a short Markdown addendum.

---

## CLN4-011 - Pending Drain Guard Smoke Readability Pass

**Goal:** Review the Pending Drain Guard smoke for clarity after the Backend Drain Scope Preview additions.

**Inspect:**

- `DesktopApp\tests\test_webview_browser_pending_drain_guard_smoke.py`

**Allowed changes:** Findings only, unless fixing comments/docs.

**Questions to answer:**

- Does the test prove the panel is read-only?
- Does it prove no `/api/pipeline/start` POST is sent before the guarded click?
- Does it remain understandable if another row/state is added later?

---

## CLN4-012 - Large Table Smoke Scope Boundary Review

**Goal:** Review Large Table smoke coverage for Queue/Pending scope previews.

**Inspect:**

- `DesktopApp\tests\test_webview_browser_large_table_smoke.py`

**Allowed changes:** Findings only, unless fixing comments/docs.

**Questions to answer:**

- Does it prove 250-row render cap wording?
- Does it prove hidden blocked/review rows remain visible in scope evidence?
- Does it prove selected-row detail is not backend processing/drain scope?

---

## CLN4-013 - Scope Panels In Manual Operator Test Script

**Goal:** Add or confirm manual test steps for the Queue and Pending scope-preview panels.

**Inspect:**

- `Docs\WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Queue manual test includes applying a filter, selecting a row, and confirming Backend Launch Scope Preview wording.
- Pending manual test includes applying a filter, selecting a row, and confirming Backend Drain Scope Preview wording.
- The script states these panels do not mutate files.

---

## CLN4-014 - Scope Panels In Validation Ladder Runbook

**Goal:** Add the scope-preview panels to the appropriate validation rung.

**Inspect:**

- `Docs\VALIDATION_LADDER_RUNBOOK.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Scope previews are listed as WebView parity/operator-trust checks, not real-media proof.
- Real-media FFmpeg proof remains a later rung.

---

## CLN4-015 - Queue/Pending Scope In TLDR

**Goal:** Confirm `TLDR.md` gives the operator a concise explanation of the new scope panels.

**Inspect:**

- `Docs\TLDR.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- The explanation is short.
- It does not make TLDR too dense.
- It preserves Tk fallback and WebView preview wording.

---

## CLN4-016 - Current Plan Latest Checkpoint Prune/Sync

**Goal:** Review the top `Latest WebView parity checkpoint` section in `V5_TAURI_TRANSITION_CURRENT_PLAN.md` for freshness and bloat.

**Inspect:**

- `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- New scope-preview work is represented.
- Repeated or stale bullets are not duplicated unnecessarily.
- The plan still warns against over-fragmentation and production cutover too early.

---

## CLN4-017 - Changelog Latest-Entries Navigation Update

**Goal:** Ensure `REMEDIATION_CHANGELOG.md` top table includes the latest scope-preview entry and remains useful for navigation.

**Inspect:**

- `Docs\REMEDIATION_CHANGELOG.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- The latest entry table includes Queue/Pending Backend Scope Preview Panels.
- The entry title is searchable.
- Validation and regression-risk sections are present.

---

## CLN4-018 - Docs Index Handoff Registration

**Goal:** Register this Round 4 handoff and any new Round 4 output docs in `DOCS_INDEX.md`.

**Inspect:**

- `Docs\DOCS_INDEX.md`
- `Docs\CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND4.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Round 4 is marked active until completed.
- If CLN4-003 creates `WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md`, index it under Operator Docs or Engineering Docs as appropriate.

---

## CLN4-019 - No-Touch Boundary Register Scope Review

**Goal:** Confirm no-touch boundaries still mention the correct authority split for queue launch and pending-publish drain.

**Inspect:**

- `Docs\NO_TOUCH_BOUNDARY_REGISTER.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Queue launch remains backend-owned.
- Pending-publish drain remains backend-owned.
- Scope preview panels are clearly evidence-only if mentioned.

---

## CLN4-020 - Command Ownership Matrix Scope Crosscheck

**Goal:** Cross-check command ownership docs against scope-preview claims.

**Inspect:**

- `Docs\COMMAND_OWNERSHIP_MATRIX.md`
- `Docs\COMMAND_HISTORY_CONSISTENCY_AUDIT.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`

**Allowed changes:** Prefer findings; docs-only updates allowed.

**Acceptance criteria:**

- `pipeline.start` and pending drain ownership are consistent.
- Command history is not described as a retry or mutation control.
- Any stale route count or owner wording is reported.

---

## CLN4-021 - Local API Evidence/Mutation Matrix Scope Crosscheck

**Goal:** Confirm the route/effect matrix aligns with the new panels.

**Inspect:**

- `Docs\LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `Docs\WEBVIEW_APIPOST_MUTATION_REVIEW.md`

**Allowed changes:** Docs only or findings only.

**Acceptance criteria:**

- Scope preview panels do not imply new API routes.
- `/api/pipeline/start` remains correctly classified as process launch / pending drain depending mode.
- Read-only WebView rendering remains distinct from backend command routes.

---

## CLN4-022 - API Route Inventory Scope Crosscheck

**Goal:** Verify that recent scope-preview work did not require route-count changes and docs still say 43 routes only if true.

**Inspect:**

- `Docs\API_ROUTE_INVENTORY.md`
- `Docs\archive\admin-audits\LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md`
- `DesktopApp\mediapipeline_desktop_app\api.py`

**Allowed changes:** Findings or docs-only corrections.

**Validation:**

```powershell
Select-String -Path Docs\API_ROUTE_INVENTORY.md,Docs\archive\admin-audits\LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md -Pattern "43|21 GET|22 POST"
```

---

## CLN4-023 - Pending Publish Failure Playbook Scope Update

**Goal:** Review whether the Pending Publish playbook should mention Backend Drain Scope Preview as an early evidence panel.

**Inspect:**

- `Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- The playbook does not tell the operator to drain from filtered/selected rows.
- The playbook explains that hidden blocked/review rows still matter.
- The playbook keeps recovery dry-run and Diagnostics before drain in risky cases.

---

## CLN4-024 - Completed/Pending Proof Docs Crosscheck

**Goal:** Ensure Completed-to-Pending proof docs do not conflict with Backend Drain Scope Preview wording.

**Inspect:**

- `Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- `Docs\archive\admin-audits\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md`
- `Docs\PENDING_PUBLISH_FIXTURE_INVENTORY.md`

**Allowed changes:** Findings or docs-only update.

**Acceptance criteria:**

- Completed/Pending proof remains evidence, not publish proof by itself.
- Pending empty view is not treated as proof of successful publish.
- Same-leaf duplicate hints are not treated as exact proof.

---

## CLN4-025 - Diagnostics Read-Only Target Runbook Crosslink

**Goal:** Add or verify a crosslink from diagnostics target guidance to Queue/Pending scope previews.

**Inspect:**

- `Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- `Docs\DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Diagnostics targets are still described as read/tail/open allowlist targets only.
- Queue/Pending scope panels are recommended as page-context evidence before launch/drain.

---

## CLN4-026 - Operator Glossary Scope Terms

**Goal:** Add glossary definitions for terms that repeatedly appear in the new panels.

**Inspect:**

- `Docs\OPERATOR_GLOSSARY.md`

**Suggested terms:**

- Backend scope
- Display filter
- Selected row
- Render cap
- Backend-owned command
- Evidence-only panel

**Allowed changes:** Docs only.

---

## CLN4-027 - Screenshot/Image Reference Staleness Sweep

**Goal:** Find Markdown references to screenshots/images that may now be stale after WebView changes.

**Inspect:**

- `Docs\*.md`
- `DesktopApp\docs\*.md`

**Allowed changes:** Findings only unless fixing obviously broken Markdown links.

**Suggested command:**

```powershell
Select-String -Path Docs\*.md,DesktopApp\docs\*.md -Pattern "!\[|\.png|\.jpg|screenshot|image"
```

**Output:** List stale-looking image references and whether an updated screenshot should be captured by Codex later.

---

## CLN4-028 - Real-Media Validation Playbook Scope Evidence Pass

**Goal:** Confirm the real-media validation playbook tells the operator how to use scope previews during sample runs.

**Inspect:**

- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Queue Backend Launch Scope Preview is mentioned before starting a sample run.
- Pending Backend Drain Scope Preview is mentioned before interpreting parked output state.
- The playbook still states real-media output proof requires actual Completed/Diagnostics/Pending evidence, not just WebView readiness.

---

## CLN4-029 - Round 4 Status Board Addendum

**Goal:** Add a status note for Round 4 delegated tasks.

**Inspect:**

- `Docs\V5_TRANSITION_STATUS_BOARD.md`
- `Docs\archive\completed-checklists\ADMIN_TASK_COMPLETION_BOARD.md`

**Allowed changes:** Docs only.

**Acceptance criteria:**

- Round 4 is tracked as active/open until completed.
- The board does not mark tasks complete preemptively.
- It points back to this handoff file.

---

## CLN4-030 - Return-To-Transition Summary For Codex

**Goal:** After Claude completes whatever subset of this backlog is feasible, produce a final handoff summary that lets Codex resume implementation work quickly.

**Preferred output:** `Docs\CLAUDE_HANDOFF_ROUND4_COMPLETION_SUMMARY.md`

**Must include:**

- Tasks completed.
- Files changed.
- Docs that need Codex verification.
- Any stale docs or mismatch findings.
- Any recommended follow-up tasks.
- Explicit statement: "Return to original V5 Tauri/WebView2 transition work."

**Allowed changes:** New Markdown summary only.

**Validation:**

```powershell
Test-Path Docs\CLAUDE_HANDOFF_ROUND4_COMPLETION_SUMMARY.md
Select-String -Path Docs\CLAUDE_HANDOFF_ROUND4_COMPLETION_SUMMARY.md -Pattern "Return to original V5 Tauri/WebView2 transition work"
```

