# V5 Transition Review Fix Checklist

Review date: 2026-05-18  
Scope: Safe implementation chunks for remediating `V5_TRANSITION_CODE_REVIEW.md`.

Python test runner note: use the bundled interpreter from the repository root unless a task explicitly validates system Python:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest discover -s DesktopApp\tests -q
& $py -m pytest DesktopApp\tests -q
```

## Chunk 1 - Harden Backend Shutdown Lifecycle

Rank: 1  
Promotion timing: Before daily-driver promotion  
Scope: Make `/api/backend/shutdown` fail closed when close-readiness reports active work, unless an explicit force-confirmed path is used.  
Files likely involved: `DesktopApp/mediapipeline_desktop_app/services/command_payloads_process.py`; `DesktopApp/mediapipeline_desktop_app/services/command_payloads_policy.py`; `DesktopApp/tests/test_local_api_lifecycle_contract_smoke.py`; Dashboard shutdown UI labels if needed.  
Validation commands:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest DesktopApp.tests.test_local_api_lifecycle_contract_smoke -q
```

Expected evidence: Unsafe shutdown returns a structured failure and does not arm the shutdown event; explicit force shutdown requires a force payload and records command evidence.  
Rollback risk: Medium. Existing UI expectations may need adjustment.  
Safe before or after promotion: Before only.

## Chunk 2 - Decide and Contract Queue Priority

Rank: 2  
Promotion timing: Before daily-driver promotion if priority remains visible; otherwise feature-flag before promotion and finish after.  
Scope: Either hide/remove queue priority from V5 daily-driver scope or fully document and harden GET/POST `/api/queue/priority`.  
Files likely involved: `DesktopApp/mediapipeline_desktop_app/services/routes_read.py`; `DesktopApp/mediapipeline_desktop_app/services/routes_command.py`; `DesktopApp/mediapipeline_desktop_app/services/contract_read.py`; `DesktopApp/mediapipeline_desktop_app/services/contract_command.py`; `DesktopApp/mediapipeline_desktop_app/services/command_payloads_queue_priority.py`; `DesktopApp/mediapipeline_desktop_app/services/service_priority_manifest.py`; `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; `API_ROUTE_INVENTORY.md`; route tests.  
Validation commands:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest DesktopApp.tests.test_application_facade.ApplicationFacadeTests.test_local_api_route_maps_cover_documented_api_contract -q
& $py -m unittest DesktopApp.tests.test_api_contract_payload.LocalApiContractPayloadTests.test_full_contract_keeps_effectful_routes_token_protected -q
& $py -m unittest DesktopApp.tests.test_api_route_inventory -q
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1
```

Expected evidence: Route inventory, contracts, UI call sites, and tests agree. Invalid/out-of-root/stale queue targets are rejected. Valid selected backend queue rows can be updated.  
Rollback risk: High if operators already rely on priority; Medium if hidden behind a feature flag.  
Safe before or after promotion: Before if visible; after only if disabled.

## Chunk 3 - Restore Reliability and Deferred-Publish Smokes

Rank: 3  
Promotion timing: Before daily-driver promotion  
Scope: Fix queue priority phase regression and isolate the deferred-publish drain smoke parser failure.  
Files likely involved: `Pipeline/Modules/QueuePlan.ps1`; `Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1`; `Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1`; `Pipeline/MediaPipeline_chatgpt.ps1`; generated smoke config handling.  
Validation commands:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1
$env:MEDIA_PIPELINE_KEEP_FAILED_SMOKE = '1'
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1
Remove-Item Env:\MEDIA_PIPELINE_KEEP_FAILED_SMOKE -ErrorAction SilentlyContinue
```

Expected evidence: Reliability suite passes; deferred-publish drain parks and drains media plus sidecars without reporting a false processing failure.  
Rollback risk: Medium. Queue phase contract choices can affect downstream UI and CSV flows.  
Safe before or after promotion: Before only.

## Chunk 4 - Remove Dashboard Command-Surface Drift

Rank: 4  
Promotion timing: Before daily-driver promotion  
Scope: Bring Dashboard back to the design reference: briefing, readiness, and evidence. Move or remove Start/Stop/Hard Kill/Drain shortcuts unless the design reference is formally updated first.  
Files likely involved: `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/app.js`; `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js`; WebView smoke tests; `V5_UI_DESIGN_REFERENCE.md` only if product decision changes.  
Validation commands:

```powershell
@'
from pathlib import Path
html = Path("DesktopApp/mediapipeline_desktop_app/ui_web/index.html").read_text(encoding="utf-8")
for forbidden in ["home-pipeline-start-button", "home-drain-button", "hard kill"]:
    print(forbidden, forbidden.lower() in html.lower())
'@ | python -
```

Expected evidence: Dashboard evidence panels contain no mutation buttons except Copy; Launch owns Start Pipeline; Pending Publish owns drain confirmation.  
Rollback risk: Medium. Operator shortcut removal changes workflow.  
Safe before or after promotion: Before.

## Chunk 5 - Enforce Panel Types, Canonical Titles, and Evidence Rules

Rank: 5  
Promotion timing: Before daily-driver promotion for evidence rules; title cleanup can follow immediately after if no command drift remains.  
Scope: Ensure every `section.panel` has `data-panel-type="evidence"` or `interactive`, evidence panels are read-only except Copy, and page/panel names match `V5_UI_DESIGN_REFERENCE.md` Section 8.  
Files likely involved: `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; WebView DOM tests; `WEBVIEW_DOM_ID_INVENTORY.md`; `DOC_TOUCH_LOG.md`.  
Validation commands:

```powershell
@'
from html.parser import HTMLParser
from pathlib import Path
class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.panels = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and "panel" in attrs.get("class", "").split():
            self.panels.append(attrs.get("data-panel-type"))
p = P()
p.feed(Path("DesktopApp/mediapipeline_desktop_app/ui_web/index.html").read_text(encoding="utf-8"))
bad = [x for x in p.panels if x not in {"evidence", "interactive"}]
print("invalid panel types", bad)
raise SystemExit(1 if bad else 0)
'@ | python -
```

Expected evidence: Static panel test passes; evidence panels do not contain launch, rename, save, drain, delete, overwrite, promote, demote, start, stop, or kill controls.  
Rollback risk: Low to Medium. Mostly markup, but moving controls can affect JS selectors.  
Safe before or after promotion: Before for evidence safety.

## Chunk 6 - Fail Closed on Unknown Destination Space

Rank: 6  
Promotion timing: Before daily-driver promotion  
Scope: Treat unknown destination free space as unsafe before copy, and preserve deferred-publish behavior when local artifacts are safely parked.  
Files likely involved: `Pipeline/Modules/Disk.ps1`; `Pipeline/Modules/PublishCompletion.ps1`; low-space/pending publish tests.  
Validation commands:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1
```

Expected evidence: Unknown-space copy attempts fail before mutation with a structured code; low-space output publish defers safely and keeps media plus sidecars parked.  
Rollback risk: Medium. Some network destinations with unreadable free-space metadata may now require operator action.  
Safe before or after promotion: Before.

## Chunk 7 - Move Readiness and Severity Facts to Backend DTOs

Rank: 7  
Promotion timing: Before promotion if any command button is enabled from these facts; otherwise after blockers.  
Scope: Ensure Launch readiness, drain safety, route safety, output acceptance, and diagnostics severity are backend-authored when they affect commands. Frontend-only calculations should be labeled advisory.  
Files likely involved: `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js`; `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/diagnosticsTailView.js`; backend facade/service DTO builders; launch and diagnostics tests.  
Validation commands:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest DesktopApp.tests.test_local_api_lifecycle_contract_smoke DesktopApp.tests.test_application_facade -q
```

Expected evidence: Disabled command labels cite backend-authored reasons; frontend log word counts do not gate commands.  
Rollback risk: Medium. DTO changes can affect several pages.  
Safe before or after promotion: Before if gating commands; otherwise after.

## Chunk 8 - Repair Python Test Environment and Route Inventory Tests

Status: Completed 2026-05-18. Bundled Python test execution is documented, route inventory drift is covered by `test_api_route_inventory.py`, DOM/global inventory drift is covered by `test_webview_inventory_docs.py`, and `test_webview_frontend_mutation_boundary.py` now gates command-route ownership plus repair/reconcile design-only exposure.

Rank: 8  
Promotion timing: Before daily-driver promotion  
Scope: Document or add the Python test bootstrap path, then make route inventory tests compare implemented routes, contracts, inventories, and UI call sites.  
Files likely involved: `DesktopApp/requirements*.txt` or project test bootstrap docs if present; `DesktopApp/tests`; `API_ROUTE_INVENTORY.md`; `Docs/CURRENT_PROJECT_STATE.md`.  
Validation commands:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest discover -s DesktopApp\tests -q
& $py -m pytest DesktopApp\tests -q
```

Expected evidence: Python tests run on a clean workspace without manual package guessing; route drift fails tests immediately.  
Rollback risk: Low. Test infrastructure only.  
Safe before or after promotion: Before.

## Chunk 9 - Add Source No-Mutation Assertions to Browser Smokes

Status: Completed 2026-05-18. Every fixture-backed browser smoke now captures and re-checks media/sidecar/manifest SHA-256 evidence before temporary fixture cleanup; 19 browser tests passed with the gate active.

Rank: 9  
Promotion timing: Before daily-driver promotion  
Scope: Convert "does not mutate" browser smoke claims into hash-based source and sidecar assertions.  
Files likely involved: `SmokeTests/Test-WebViewBrowser*.ps1`; `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`; smoke fixture helpers.  
Validation commands:

```powershell
Get-ChildItem -Path SmokeTests -Filter 'Test-WebViewBrowser*.ps1' | Sort-Object Name | Select-Object Name
```

Expected evidence: Browser smokes record source hashes before and after; tests fail if media/source sidecars change during read-only UI flows.  
Rollback risk: Low. Test-only, but may expose existing hidden mutation.  
Safe before or after promotion: Before.

## Chunk 10 - Clean CSS Token Violations

Status: Completed 2026-05-18. Remaining raw color/font/spacing/opacity drift in layout/customize and queue priority/strategy CSS was tokenized; `test_webview_css_design_tokens.py` now enforces the gate.

Rank: 10  
Promotion timing: Before UI signoff; after safety blockers  
Scope: Replace raw hex/hsl/rgba fallbacks, arbitrary sizes, and opacity-based de-emphasis with documented tokens.  
Files likely involved: `DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css`; CSS lint test; `V5_UI_DESIGN_REFERENCE.md` if new tokens are truly required.  
Validation commands:

```powershell
Select-String -Path DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css -Pattern '#[0-9a-fA-F]{3,8}\b'
Select-String -Path DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css -Pattern 'rgba\(|hsl\('
Select-String -Path DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css -Pattern 'opacity:\s*0\.|font-size:\s*[0-9]+px|gap:\s*[0-9]+px|padding:\s*[0-9]+px'
```

Expected evidence: Static scan has no violations outside approved token definitions; screenshots show no degraded status-chip contrast.  
Rollback risk: Low to Medium. Visual changes need screenshot review.  
Safe before or after promotion: Prefer before; can follow P0 safety fixes.

## Chunk 11 - Regenerate DOM, Global Export, and API Inventories

Status: Completed 2026-05-18. DOM and global-export inventories were regenerated from live WebView assets; API route inventory consistency remains covered by the route contract drift gate; `test_webview_inventory_docs.py` now fails stale DOM/global manifests.

Rank: 11  
Promotion timing: Before closing transition tasks; after related code fixes  
Scope: Regenerate inventories from current code and reconcile conflicting totals.  
Files likely involved: `WEBVIEW_DOM_ID_INVENTORY.md`; `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`; `API_ROUTE_INVENTORY.md`; `DOC_TOUCH_LOG.md`; `DOCS_INDEX.md`; inventory generator scripts if present.  
Validation commands:

```powershell
& DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_inventory_docs DesktopApp.tests.test_api_route_inventory -q
& DesktopApp\Runtime\Python\python.exe -m py_compile DesktopApp\tests\test_webview_inventory_docs.py
```

Expected evidence: Inventories match live code, route totals are consistent, and touch-log entries explain visible operator changes.  
Rollback risk: Low. Documentation only unless generators are changed.  
Safe before or after promotion: Before final signoff; after blocker code settles.

## Chunk 12 - Validate Pending Publish Sidecar Drain End to End

Status: Completed 2026-05-18. Pending drain now backs up/restores external tx3g sidecars around retry publish, rolls sidecars back on sidecar-write or final media-reveal failure, and has reliability coverage for media-plus-sidecar success, reveal failure preservation, drain summary evidence, and retry recovery.

Rank: 12  
Promotion timing: Before daily-driver promotion  
Scope: Add focused tests that parked media plus sidecars drain atomically and failed drains preserve parked artifacts.  
Files likely involved: `Pipeline/Modules/PendingTransactions.ps1`; `Pipeline/Modules/PublishCompletion.ps1`; `Pipeline/Tests`; smoke fixtures.  
Validation commands:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1
```

Expected evidence: Drain removes parked artifacts only after final reveal succeeds; failures leave retryable pending state and operator-visible evidence.  
Rollback risk: Medium if implementation changes are needed; Low if tests only.  
Safe before or after promotion: Before.

## Chunk 13 - Worker/Network Read-Only Confirmation

Status: Completed 2026-05-18. Workers page buttons are now guarded by `test_webview_network_read_only_boundary.py`, which allows only diagnostics-open controls on the page, rejects worker lifecycle/mutation control attributes, rejects Network-owned command calls in `networkView.js`, and verifies `/api/network/workers` remains a read-only route.

Rank: 13  
Promotion timing: After safety blockers, before final UI signoff  
Scope: Confirm Distributed Workers remains read-only unless command routes and tests exist.  
Files likely involved: `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; worker/network JS assets; worker route docs/tests; `V5_UI_DESIGN_REFERENCE.md`.  
Validation commands:

```powershell
& DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_network_read_only_boundary -q
& DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_browser_network_smoke DesktopApp.tests.test_webview_network_read_only_boundary -q
```

Expected evidence: No start/stop/promote/demote controls appear in worker evidence panels.  
Rollback risk: Low.  
Safe before or after promotion: Before UI signoff; after P0/P1 fixes.

## Chunk 14 - Release and Tauri/WebView2 Promotion Gate

Status: Completed 2026-05-18 for source/dev bundle validation and current-handoff transfer prep. Full unskipped release self-test passed with bundled tool integration and end-to-end smoke included; bundled Python `unittest` and `pytest` suites passed; browser smoke no-mutation suite passed; Tauri `-CheckOnly` prerequisite and build gates passed. A fresh current-handoff package named `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` passed copied-bundle release self-test and package-mode Tauri launch/close locally. This does not claim PG-3 clean-machine proof because the local boundary report detected developer tools on the development workstation; broader representative real-media daily-driver proof also remains open.

Rank: 14  
Promotion timing: Final gate before daily-driver promotion  
Scope: Run the complete portable bundle validation after blockers are fixed, including bundled tools, browser smokes, mutation smokes, release self-tests, and clean-machine Tauri/WebView2 checks.  
Files likely involved: Release scripts; `Pipeline/PowerShell-7.6.0-win-x64`; `DesktopApp`; `SmokeTests`; packaging docs; `Docs/CURRENT_PROJECT_STATE.md`; `ACTIVE_FIX_CHECKLIST.md`.  
Validation commands:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-ContractSchemaChecks.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest discover -s DesktopApp\tests -q
& $py -m pytest DesktopApp\tests -q
$bundle = "C:\Path\To\MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116"
& (Join-Path $bundle "Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe") -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bundle "DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1") -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30
```

Expected evidence: All suites pass from the portable bundle; docs name V4 as fallback and V5 as daily-driver candidate only after proof; release notes include known residual transition debt.  
Rollback risk: Low if validation only; Medium if packaging fixes are needed.  
Safe before or after promotion: Before only.

## Chunk 15 - V4 Fallback and Documentation Hygiene

Status: Completed 2026-05-18 for documentation hygiene pass. Updated current-state/readme/start-here/status/index/mutation-matrix docs to keep Tk/V4 fallback explicit, source/dev V5 validation current, PG-3/real-media gates open, route counts at 50, and reorg paths accurate.

Rank: 15  
Promotion timing: After blocker fixes; before public/operator handoff  
Scope: Update docs to reflect current architecture, validation status, and fallback strategy without embedding roadmap/changelog content into the UI.  
Files likely involved: `Docs/README_MediaPipelineRemuxEncodeAIO.md`; `Docs/CURRENT_PROJECT_STATE.md`; `Docs/ACTIVE_FIX_CHECKLIST.md`; `Docs/DOC_TOUCH_LOG.md`; `Docs/DOCS_INDEX.md`; `Docs/REMEDIATION_CHANGELOG.md`; parity and inventory docs.  
Validation commands:

```powershell
Select-String -Path AI_AGENT_START_HERE.md,Docs/README_MediaPipelineRemuxEncodeAIO.md,Docs/CURRENT_PROJECT_STATE.md,Docs/ACTIVE_FIX_CHECKLIST.md,Docs/active-plans/V5_TRANSITION_STATUS_BOARD.md -Pattern 'V4|V5|daily-driver|fallback|passed|failed|PG-3|source/dev'
```

Expected evidence: Docs no longer claim stale passing validation; V4 fallback and V5 promotion gates are explicit; new review artifacts are indexed and touch-logged.  
Rollback risk: Low. Documentation only.  
Safe before or after promotion: Before handoff; after code/test facts are stable.
