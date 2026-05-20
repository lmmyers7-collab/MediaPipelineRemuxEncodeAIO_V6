# Claude Handoff: V5 Transition Support Tasks

Date: 2026-05-14

Purpose: provide Claude with a fresh set of bounded, low-dependency support tasks that help the V5 Tauri/WebView2 transition without touching production-sensitive media behavior.

This task list is intended for offloading review, documentation reconciliation, validation evidence gathering, and administrative cleanup while Codex continues implementation work.

---

## Non-Negotiable Rules

1. Do not touch `MediaPipelineRemuxEncodeAIO_V4`.
2. Do not weaken, remove, freeze, or replace the Tk desktop app.
3. Do not change FFmpeg, ffprobe, subtitle conversion, audio routing, remux/encode routing, queue launch, pending publish drain, rename apply, settings persistence, source/scratch/output safety, or Network lifecycle behavior.
4. Do not add frontend-owned filesystem mutation or frontend-only business logic.
5. Do not change Local API route contracts, command journal semantics, strict JSON handling, duplicate-command guards, close-readiness, release gates, or backend ownership boundaries.
6. Prefer docs, inventories, static checks, and smoke-result evidence. If a task discovers a code issue, document it and stop rather than patching risky runtime logic.
7. Every task output must state files inspected, files changed, commands run, and remaining uncertainty.
8. If a task edits docs, keep wording consistent with: `preview`, `backend-owned`, `read-only`, `mutation guardrail`, `Tk remains fallback`, and `real-media validation is still required`.
9. Final task must return control to the V5 transition by summarizing completed work and recommended next implementation batch.

---

## Recommended Validation Before Starting

Run at least these lightweight checks before editing:

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
.\DesktopApp\tauri_shell\Test-TauriShell-Build.ps1 -SkipLinkCheck
```

If those fail, stop and record the failure. Do not continue with broad doc edits until the baseline is understood.

---

## Task Format

Each task below includes:

- **Goal**
- **Scope**
- **Allowed changes**
- **Validation**
- **Do not touch**
- **Deliverable**

Tasks are intentionally independent. Claude can complete any subset, but should not combine unrelated tasks into risky edits.

---

## CLN2-01: Validation Ladder Freshness Review

**Goal:** Confirm `VALIDATION_LADDER_RUNBOOK.md` reflects the current smoke/test layout after the browser-smoke runner hardening.

**Scope:**

- `Docs\VALIDATION_LADDER_RUNBOOK.md`
- `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`
- `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`
- Root `Test-WebView*.ps1` wrappers

**Allowed changes:** Documentation wording only.

**Validation:**

```powershell
Get-ChildItem -Filter "Test-WebView*.ps1" | Select-Object Name
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

**Do not touch:** Any test implementation or app code.

**Deliverable:** A short section in the runbook or a separate note stating any stale ladder entries and exact corrections made.

---

## CLN2-02: Browser Smoke Runner Failure Triage Addendum

**Goal:** Expand browser-smoke failure interpretation now that the shared runner owns timeout conversion, JSON parsing, no-pipe launch, and bounded browser termination.

**Scope:**

- `Docs\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md`
- `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`
- `DesktopApp\tests\webview_browser_smoke_support.py` for reference only

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md,Docs\BROWSER_SMOKE_TEST_RUNBOOK.md -Pattern "TimeoutExpired|Timed out|JSON|stdout|stderr|terminateBrowser"
```

**Do not touch:** Python smoke runner code.

**Deliverable:** Add failure signatures for timeout conversion, malformed JSON result line, no JSON result line, and browser termination failures.

---

## CLN2-03: Root Script Inventory Sync

**Goal:** Verify `ROOT_SCRIPT_INVENTORY.md` still lists all current root `.ps1` and `.bat` scripts, including WebView/Tauri wrappers.

**Scope:**

- `Docs\ROOT_SCRIPT_INVENTORY.md`
- Root `*.ps1`
- Root `*.bat`

**Allowed changes:** Documentation inventory only.

**Validation:**

```powershell
Get-ChildItem -File -Include *.ps1,*.bat | Sort-Object Name | Select-Object Name
```

**Do not touch:** Root scripts.

**Deliverable:** Updated inventory or a note stating it is already current.

---

## CLN2-04: Release Layout Gate Coverage Review

**Goal:** Confirm the release self-test layout gate includes all new V5 scripts/docs needed for WebView/Tauri validation.

**Scope:**

- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `Docs\RELEASE_SELF_TEST_LAYOUT_AUDIT.md`
- `Docs\RELEASE_PACKAGE_ADMIN_INVENTORY.md`

**Allowed changes:** Documentation and audit notes only unless a missing layout gate is obvious and low-risk.

**Validation:**

```powershell
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

**Do not touch:** Release builder packaging behavior unless explicitly assigned later.

**Deliverable:** A short audit update listing checked files and any missing gate candidates.

---

## CLN2-05: Docs Index Delegation Section Cleanup

**Goal:** Make the `DOCS_INDEX.md` delegation/archive section easier to scan without turning it into a graveyard.

**Scope:**

- `Docs\DOCS_INDEX.md`
- `Docs\CLAUDE_HANDOFF*.md`

**Allowed changes:** Documentation index wording only.

**Validation:**

```powershell
Get-ChildItem Docs\CLAUDE_HANDOFF*.md | Select-Object Name
Select-String -Path Docs\DOCS_INDEX.md -Pattern "CLAUDE_HANDOFF"
```

**Do not touch:** Completed handoff files unless correcting broken titles.

**Deliverable:** Index entries that clearly mark each handoff as active, reference-only, or completed.

---

## CLN2-06: Tauri Preview Status Language Sweep

**Goal:** Ensure all active docs still describe Tauri/WebView2 as preview and Tk as fallback.

**Scope:**

- `Docs\TLDR.md`
- `Docs\V5_TRANSITION_STATUS_BOARD.md`
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\archive\admin-audits\TAURI_DAILY_DRIVER_WORDING_AUDIT.md`
- `DesktopApp\tauri_shell\README.md`

**Allowed changes:** Documentation wording only.

**Validation:**

```powershell
rg -n "daily-driver|daily driver|fallback|preview|production replacement|supported operator UI" Docs DesktopApp\tauri_shell\README.md
```

**Do not touch:** Launchers or runtime behavior.

**Deliverable:** A short freshness note or small wording fixes where docs overstate WebView readiness.

---

## CLN2-07: Real-Media Validation Worksheet Dry Run

**Goal:** Confirm worksheet generation still works and outputs only Markdown evidence under the expected folder.

**Scope:**

- `New-RealMediaValidationWorksheet.ps1`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\RealMediaValidationRuns\README.md`

**Allowed changes:** Documentation only. Generated worksheet may be created and then documented; do not commit personal paths unless intentionally anonymized.

**Validation:**

```powershell
.\New-RealMediaValidationWorksheet.ps1 -SamplePath "C:\Temp\sample-validation-placeholder.mkv" -Shell "WebView preview"
```

**Do not touch:** Pipeline launch, media processing, or validation record append routes.

**Deliverable:** Note whether generated worksheet fields match the playbook and whether cleanup/anonymization is needed.

---

## CLN2-08: WebView Smoke Boundary Text Sweep

**Goal:** Recheck every root WebView smoke wrapper boundary line after recent runner changes.

**Scope:**

- Root `Test-WebView*.ps1`
- `Docs\archive\admin-audits\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md`
- `Docs\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`

**Allowed changes:** Documentation and wrapper comment/Write-Host boundary text only if stale.

**Validation:**

```powershell
Select-String -Path .\SmokeTests\Test-WebView*.ps1 -Pattern "Boundary:"
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

**Do not touch:** Python test logic.

**Deliverable:** Updated boundary audit or confirmation that all wrappers remain accurate.

---

## CLN2-09: API Route Count Consistency Sweep

**Goal:** Confirm all route-count docs now agree with the implemented Local API contracts.

**Scope:**

- `DesktopApp\mediapipeline_desktop_app\api\contract_read.py`
- `DesktopApp\mediapipeline_desktop_app\api\contract_command.py`
- `Docs\API_ROUTE_INVENTORY.md`
- `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `Docs\LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- `Docs\archive\admin-audits\LOCAL_API_ROUTE_COUNT_SYNC_AUDIT.md`

**Allowed changes:** Documentation only unless a doc says 41/20/20 when code now says 43/21/22.

**Validation:**

```powershell
python - <<'PY'
from mediapipeline_desktop_app.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
print(len(LOCAL_API_READ_ROUTE_CONTRACT), len(LOCAL_API_COMMAND_ROUTE_CONTRACT), len(LOCAL_API_READ_ROUTE_CONTRACT)+len(LOCAL_API_COMMAND_ROUTE_CONTRACT))
PY
```

**Do not touch:** API route code.

**Deliverable:** Route-count sync note with exact current counts.

---

## CLN2-10: Diagnostics Target Count Consistency Sweep

**Goal:** Confirm all diagnostics target docs still agree on the 20 backend-allowlisted targets.

**Scope:**

- `Docs\DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`
- `Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- `Docs\archive\admin-audits\DIAGNOSTICS_TARGET_SYNC_AUDIT.md`
- Backend diagnostics allowlist code for reference only

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md,Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md,Docs\archive\admin-audits\DIAGNOSTICS_TARGET_SYNC_AUDIT.md -Pattern "20"
```

**Do not touch:** Diagnostics open/tail allowlist behavior.

**Deliverable:** Confirmation note or targeted corrections.

---

## CLN2-11: Settings Raw-Key Follow-Up Review

**Goal:** Identify which remaining raw-only Settings keys are worth future WebView builder work, without implementing them.

**Scope:**

- `Docs\SETTINGS_RAW_KEY_TRIAGE.md`
- `Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- `Docs\SETTINGS_KEY_OWNERSHIP_MAP.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsMetadata.js`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\SETTINGS_RAW_KEY_TRIAGE.md,Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md -Pattern "raw-only|hidden|Bdpgs|Ocr|Tessdata"
```

**Do not touch:** Settings save/preview code.

**Deliverable:** Ranked list of remaining raw keys with recommended priority and rationale.

---

## CLN2-12: Rename Documentation Drift Review

**Goal:** Confirm rename docs still match current WebView behavior: templates, selected scope, force pipeline, sidecars, large-batch render cap, and pipeline handoff.

**Scope:**

- `Docs\archive\admin-audits\RENAME_DOCS_FRESHNESS_REVIEW.md`
- `Docs\RENAME_TOOL_EDGE_CASE_CATALOG.md`
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\renameView.js` for reference only

**Allowed changes:** Documentation only.

**Validation:**

```powershell
python -m unittest DesktopApp.tests.test_webview_rename_readiness_smoke DesktopApp.tests.test_webview_browser_rename_smoke -q
```

**Do not touch:** Rename planner/apply logic.

**Deliverable:** Update docs if behavior has drifted; otherwise append a dated no-drift note.

---

## CLN2-13: Pending Publish Documentation Drift Review

**Goal:** Confirm Pending Publish docs still separate recovery dry-run, publish button guard, drain command ownership, and true repair deferral.

**Scope:**

- `Docs\archive\admin-audits\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md`
- `Docs\COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\V5_TRANSITION_STATUS_BOARD.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
python -m unittest DesktopApp.tests.test_webview_browser_pending_drain_guard_smoke DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke -q
```

**Do not touch:** Pending publish drain or recovery code.

**Deliverable:** Updated freshness note or no-drift confirmation.

---

## CLN2-14: Network Read-Only Guardrail Review

**Goal:** Confirm Network docs and WebView text still make lifecycle controls Tk-owned/read-only.

**Scope:**

- `Docs\archive\admin-audits\NETWORK_READONLY_WORDING_AUDIT.md`
- `Docs\NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`
- `Docs\NETWORK_READ_ONLY_PARITY_AUDIT.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\networkView.js`

**Allowed changes:** Documentation or copy wording only.

**Validation:**

```powershell
python -m unittest DesktopApp.tests.test_webview_browser_network_smoke -q
```

**Do not touch:** Network coordinator/worker lifecycle code.

**Deliverable:** Confirm no lifecycle controls are implied in WebView docs.

---

## CLN2-15: Operator Glossary Coverage Addendum

**Goal:** Add or confirm glossary entries for newer V5 operator terms.

**Scope:**

- `Docs\OPERATOR_GLOSSARY.md`
- `Docs\TERMINOLOGY_CONSISTENCY_GUIDE.md`

**Candidate terms:**

- Browser-backed smoke
- CDP
- Backend-owned
- Mutation guardrail
- Sample Validation Record
- Publish Reconciliation
- Active Media Policy Boundary
- Continuous schedule-stop watcher

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\OPERATOR_GLOSSARY.md -Pattern "Sample Validation|Publish Reconciliation|Active Media Policy|schedule-stop|Mutation guardrail"
```

**Do not touch:** UI copy unless separately assigned.

**Deliverable:** Glossary addendum for missing terms.

---

## CLN2-16: Changelog Navigation Mini-Index Proposal

**Goal:** Improve navigation of the large `REMEDIATION_CHANGELOG.md` without splitting it.

**Scope:**

- `Docs\REMEDIATION_CHANGELOG.md`
- `Docs\CHANGELOG_NAVIGATION_PROPOSAL.md`
- `Docs\archive\admin-audits\CHANGELOG_NAVIGATION_HEALTH_REVIEW.md`

**Allowed changes:** Prefer a separate generated/proposed index document. Only edit the changelog if the insertion is small and safe.

**Validation:**

```powershell
Select-String -Path Docs\REMEDIATION_CHANGELOG.md -Pattern "^## " | Select-Object -First 20
```

**Do not touch:** Changelog entries’ historical content.

**Deliverable:** A proposed mini-index grouped by subsystem/date. Do not split archive files.

---

## CLN2-17: Frontend Module Export Inventory Refresh

**Goal:** Refresh counts in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` after recent WebView work.

**Scope:**

- `Docs\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js`

**Allowed changes:** Documentation inventory only.

**Validation:**

```powershell
rg -n "window\\." DesktopApp\mediapipeline_desktop_app\ui_web\static\assets
node --check DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js
```

**Do not touch:** JS behavior or exports.

**Deliverable:** Updated counts or a dated addendum.

---

## CLN2-18: DOM ID Inventory Delta Review

**Goal:** Identify missing DOM IDs from the current partial inventory and decide whether a full inventory refresh is worth doing.

**Scope:**

- `Docs\WEBVIEW_DOM_ID_INVENTORY.md`
- `Docs\archive\admin-audits\WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js`

**Allowed changes:** Documentation inventory only.

**Validation:**

```powershell
rg -n "id=|byId\\(|getElementById\\(" DesktopApp\mediapipeline_desktop_app\ui_web\static
```

**Do not touch:** HTML/JS IDs.

**Deliverable:** Delta report listing missing high-value IDs and whether full refresh is recommended.

---

## CLN2-19: Real-Media Validation Evidence Template Review

**Goal:** Confirm `REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` and playbook capture the newest proof boards and backend reconciliation panels.

**Scope:**

- `Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md`
- `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\TLDR.md`

**Allowed changes:** Documentation only.

**Validation:**

```powershell
Select-String -Path Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md,Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md -Pattern "Publish Reconciliation|Real-Media Output Proof|Sample Validation|size|subtitle|audio"
```

**Do not touch:** Sample validation API or worksheet generator.

**Deliverable:** Updated template/checklist wording if needed.

---

## CLN2-20: Return-To-Transition Handoff Summary

**Goal:** Summarize all completed Claude tasks and hand control back to the main V5 transition work.

**Scope:**

- Any docs changed during CLN2 tasks
- `Docs\V5_TRANSITION_STATUS_BOARD.md`
- `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

**Allowed changes:** One concise completion section or a new dated summary note.

**Validation:**

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

**Do not touch:** Runtime code.

**Deliverable:** Final handoff summary with:

- Completed tasks
- Files changed
- Commands run
- Any stale docs left intentionally unchanged
- Recommended next implementation batch for Codex

---

## Suggested Completion Report Format

Claude should finish each task with:

```markdown
Task:
Changed:
Inspected:
Validation:
Findings:
Risks:
Recommended follow-up:
```

For the final CLN2-20 summary:

```markdown
Completed:
Deferred:
Validation run:
Docs updated:
Open questions:
Return-to-transition recommendation:
```


