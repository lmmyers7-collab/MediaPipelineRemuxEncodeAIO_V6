# V5 Transition Code Review

Review date: 2026-05-18  
Repository: `C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

## 1) Executive Summary

V5 is not ready for daily-driver promotion. The backend/media pipeline has several strong foundations: V4 remains documented as the stable fallback, bundled PowerShell/Python/FFmpeg tooling is preferred, normal processing copies sources to scratch before processing, pending publish is modeled as parked artifacts plus sidecars, and the local API has token protection and command journaling hooks.

The transition risk is concentrated in four areas:

- Backend command contracts allow at least one unsafe direct mutation path: `/api/backend/shutdown` can request shutdown even when close-readiness says active work may still be running.
- A new queue priority route and WebView toolbar exist outside the route inventory and documented contract, and the route accepts frontend-submitted path strings without enough backend ownership of queue scope.
- V5 WebView design compliance has drifted from `V5_UI_DESIGN_REFERENCE.md`: Dashboard has mutation controls, evidence panels contain command/navigation controls, page titles and panel names are not canonical, and CSS includes raw color/size/opacity patterns.
- Validation is not green: PowerShell contract schema checks passed, but the reliability regression suite failed on queue priority contract drift, end-to-end deferred-publish drain smoke failed, and Python tests could not run because `pytest` is not installed in the current environment.

The report below treats WebView as an operator control and monitoring surface only. Queue planning, route safety, publish/drain decisions, media policy, file safety, and output acceptance must remain backend-authored unless the docs explicitly change that contract.

## 2) Daily-Driver Readiness Verdict

Verdict: **Not ready for daily-driver promotion. Keep V4 as the stable fallback.**

Reasons:

- A direct backend lifecycle command can succeed while the backend says it is not safe to close.
- Queue priority mutation is implemented and exposed before API inventory, route contract, preconditions, and regression expectations are aligned.
- Required validation suites are red or unavailable in this environment.
- The WebView UI no longer matches the V5 design reference source of truth closely enough to be considered a trustworthy operator shell.
- `Docs/CURRENT_PROJECT_STATE.md` still says reliability regression checks and release self-tests passed as of 2026-05-17, but the 2026-05-18 validation run found failures.

Daily-driver promotion should wait until findings V5-F001 through V5-F007 are resolved and the suggested validation commands in section 20 are green on the target Windows bundle.

## 3) Highest-Risk Findings

### V5-F001

ID: V5-F001  
Severity: Blocker  
Area: Backend/API lifecycle safety  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/services/command_payloads_process.py::_backend_shutdown_payload`; `DesktopApp/mediapipeline_desktop_app/services/command_payloads_policy.py::backend_shutdown_success_payload`; `DesktopApp/tests/test_local_api_lifecycle_contract_smoke.py`; `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/app.js`  
Evidence: `command_payloads_process.py` requests backend shutdown after calculating close-readiness. When close-readiness fails, it builds `safe_to_close=False`, optionally skips cleanup unless `force_active_work_shutdown` is set, and still calls `_request_backend_shutdown_after_response()`. `command_payloads_policy.py` returns an `ok: true` command result with warning severity for unsafe shutdown. `test_local_api_lifecycle_contract_smoke.py` asserts that unsafe shutdown returns HTTP 200, `ok: true`, warning severity, and sets the shutdown event. The WebView adds a UI-level guard in `app.js`, but the route itself still accepts direct tokened POST.  
Why It Matters: Backend routes, not the WebView, must enforce process lifecycle safety. A UI guard does not protect local API callers, tests, future Tauri bridge code, or accidental automation. This can terminate the desktop host while queue, publish, or subprocess work is active.  
Recommended Fix: Make `/api/backend/shutdown` fail closed when `safe_to_close` is false unless an explicit, separately confirmed force path is used. Return `ok: false`, an error severity, and operator evidence for normal unsafe requests. Keep force shutdown as an explicit payload with audited confirmation, cleanup policy, and tests.  
Suggested Test: Update `DesktopApp/tests/test_local_api_lifecycle_contract_smoke.py` so unsafe shutdown does not arm the shutdown event. Add a positive force-shutdown test that requires the explicit force flag and confirms journal/history evidence.  
Regression Risk: Medium. The UI currently expects a warning success path, so button handling and labels need a small contract update.  
Priority: P0 before daily-driver promotion.

### V5-F002

ID: V5-F002  
Severity: Blocker  
Area: API contract, route inventory, queue mutation  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/services/routes_read.py`; `DesktopApp/mediapipeline_desktop_app/services/routes_command.py`; `DesktopApp/mediapipeline_desktop_app/services/command_payloads_queue_priority.py`; `DesktopApp/mediapipeline_desktop_app/services/contract_read.py`; `DesktopApp/mediapipeline_desktop_app/services/contract_command.py`; `API_ROUTE_INVENTORY.md`; `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`  
Evidence: GET `/api/queue/priority` is registered in `routes_read.py`, and POST `/api/queue/priority` is registered in `routes_command.py`. The route is not present in `contract_read.py`, `contract_command.py`, or `API_ROUTE_INVENTORY.md`, which still reports 43 total routes. The actual route surface is 46 if `/api/health` is counted, or 45 excluding health. `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` still refers to a 41-route contract. The Queue page exposes priority buttons at `index.html` lines 1099-1110.  
Why It Matters: Mutation routes must be documented, inventoried, classified, preconditioned, journaled, and tested before becoming operator-visible. This route mutates state used by queue planning, so route drift can break V4/V5 parity and source-file safety assumptions.  
Recommended Fix: Decide whether queue priority is in scope for V5 promotion. If not, feature-flag or remove the toolbar and route exposure. If yes, add the route to read and command contracts, update `API_ROUTE_INVENTORY.md`, add command effect classification, add negative tests, and document operator-visible behavior in the design and touch logs.  
Suggested Test: Add a route inventory test that fails when `routes_read.py`/`routes_command.py` contain paths missing from contract files and docs. Add POST tests for invalid path, missing row, stale queue row, out-of-root path, and valid row-key update.  
Regression Risk: High if the route is removed without checking existing operators. Medium if the route is kept and fully contracted.  
Priority: P0 before daily-driver promotion.

### V5-F003

ID: V5-F003  
Severity: High  
Area: Queue priority file safety  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/services/service_priority_manifest.py`; `DesktopApp/mediapipeline_desktop_app/services/command_payloads_queue_priority.py`; `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`  
Evidence: `service_priority_manifest.py` normalizes path strings by lowercasing, replacing separators, and trimming trailing slashes. `set_entry` and `set_bulk` accept arbitrary `source_path` values and write them into `State\Queue\queue_priority_manifest.json`. `command_payloads_queue_priority.py` validates only level and non-empty path for normal single updates. The WebView toolbar submits selected queue paths from the frontend. There is no clear backend containment check against configured source roots or a backend-authored queue row key.  
Why It Matters: The UI must not author arbitrary file scope for queue planning. Prefix-style path matching can also misclassify sibling paths when folder names share prefixes. Queue inclusion and priority scope should be backend-authored from known source roots and queue snapshots.  
Recommended Fix: Accept backend row IDs or canonical backend-selected paths instead of free-form frontend paths. Validate every target against configured `SourceMovies`/`SourceTV` roots and loaded queue snapshot membership. Use boundary-aware path containment helpers instead of string-prefix semantics.  
Suggested Test: Add negative tests for `C:\outside\file.mkv`, sibling prefix paths, `..\` traversal, nonexistent stale queue rows, and mismatched movie/TV roots. Add a positive test for a selected queue row generated by the backend.  
Regression Risk: Medium. Existing priority entries may need migration or rejection with clear operator evidence.  
Priority: P0 before daily-driver promotion if priority remains enabled.

### V5-F004

ID: V5-F004  
Severity: High  
Area: PowerShell queue contract regression  
Files/Functions: `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; `Pipeline\Modules\QueuePlan.ps1::New-MediaQueuePhasePlan`  
Evidence: Running `pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1` failed with `priority queue item contract changed`. The failing check expects `PriorityEntries[0].QueueItemType -eq 'media_queue_item.v1'` and `PriorityEntries[0].QueuePhase -eq 'priority'`. `QueuePlan.ps1` now assigns `priority_movie` or `priority_tv` for high-priority movie/TV entries, while the legacy flat `PriorityEntries` list is not normalized back to `priority` unless the mixed-priority branch is active.  
Why It Matters: Queue plan shape is a backend contract consumed by tests, UI state, and remediation flows. A changed `QueuePhase` without contract migration can break launch scope previews, drain decisions, and operator evidence.  
Recommended Fix: Decide the queue phase contract. If `PriorityEntries` is the legacy flat contract, normalize that collection to `priority` while keeping typed `PriorityMovieEntries`/`PriorityTvEntries`. If typed phases are the new contract, update schemas, route docs, tests, and UI copy together.  
Suggested Test: Rerun `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` and add a focused unit test that asserts both legacy flat and typed priority collections.  
Regression Risk: Medium. Downstream consumers may rely on either the old or new phase strings.  
Priority: P0 before daily-driver promotion.

### V5-F005

ID: V5-F005  
Severity: High  
Area: End-to-end deferred publish validation  
Files/Functions: `Pipeline\Tests\Invoke-EndToEndSmokeChecks.ps1`; `Pipeline\MediaPipeline_chatgpt.ps1`; deferred publish drain path  
Evidence: Running `pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1` failed during the deferred-publish drain smoke with `MediaPipeline_chatgpt.ps1: Missing closing '}' in statement block or type definition.` Standalone parser checks for `Pipeline\MediaPipeline_chatgpt.ps1` passed under both system PowerShell and bundled PowerShell 7.6.1, so the failure appears tied to the smoke invocation, generated config, or drain execution path rather than a simple source parse failure.  
Why It Matters: Pending publish and deferred publish are explicit V5 safety goals. A drain smoke failure blocks confidence that low-space parking and later publish are safe.  
Recommended Fix: Preserve the failed smoke workspace, inspect generated config and logs, and isolate whether the drain invocation, dot-sourced modules, generated hashtable, or bundled shell path triggers the parser error. Add a regression that runs the exact drain command after parking artifacts.  
Suggested Test: Run `$env:MEDIA_PIPELINE_KEEP_FAILED_SMOKE='1'; pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1`, then inspect the preserved temp workspace and rerun only the deferred-publish drain step.  
Regression Risk: Low to Medium. Fix may be test harness-only, but it touches release confidence.  
Priority: P0 before daily-driver promotion.

### V5-F006

ID: V5-F006  
Severity: High  
Area: WebView Dashboard command boundary  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/app.js`; `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js`; `V5_UI_DESIGN_REFERENCE.md`  
Evidence: The Dashboard contains `Run Controls` with Start, Stop, and Hard Kill buttons and `Quick Actions` with `Publish Parked Outputs`. `V5_UI_DESIGN_REFERENCE.md` Section 8 defines Dashboard as briefing/readiness/evidence and says `Pipeline Overview` is read-only evidence with no buttons except Copy. Launch and drain controls belong to Launch/Pending with backend preconditions and confirmation hierarchy.  
Why It Matters: Dashboard becomes a duplicate command surface and weakens operator mental models. Critical mutation commands are easier to trigger away from their evidence and confirmation context.  
Recommended Fix: Move start/stop/kill/drain affordances back to their canonical pages, or formally update the design reference, route contracts, inventory, and tests before keeping them on Dashboard. Hard kill and drain should not be large/red by default.  
Suggested Test: Add a static UI contract test that Dashboard evidence panels contain only Copy tertiary actions and that Start Pipeline appears only on Launch unless the design reference explicitly allows another location.  
Regression Risk: Medium. Removing Dashboard shortcuts changes operator workflow but restores documented hierarchy.  
Priority: P1 before daily-driver promotion.

### V5-F007

ID: V5-F007  
Severity: High  
Area: WebView evidence-panel compliance  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; `V5_UI_DESIGN_REFERENCE.md` Section 8 and Section 10  
Evidence: `index.html` has 99 `section.panel` elements. One panel, `At A Glance`, uses invalid `data-panel-type="status"`. Evidence panels such as `Queue Snapshot` and `Recently Completed` contain navigation buttons, while the design reference says evidence panels may only contain a tertiary Copy action. `Pipeline Overview` is marked interactive and contains many sample-validation controls even though the design says Dashboard `Pipeline Overview` is read-only evidence.  
Why It Matters: Evidence surfaces must be trustworthy and non-mutating. Mixed panels make it hard to tell whether a surface is proof, navigation, or command.  
Recommended Fix: Change every `section.panel` to `data-panel-type="evidence"` or `interactive`. Move navigation and sample-validation controls into explicit interactive panels with canonical names, or update Section 8 first if the product decision is intentional.  
Suggested Test: Add a DOM static test that verifies valid `data-panel-type` values, forbids mutation controls in evidence panels, and compares panel headings to Section 8 canonical names.  
Regression Risk: Low to Medium. Mostly markup/classification, but controls may need relocation.  
Priority: P1 before daily-driver promotion.

### V5-F008

ID: V5-F008  
Severity: Medium  
Area: WebView page title and panel naming parity  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; `V5_UI_DESIGN_REFERENCE.md` Section 8  
Evidence: Nav labels are canonical, but hidden H1 titles are generic: `Telemetry`, `Queue`, `Output`, `Publish`, `Rename`, `Launch`, `Reports`, `Network`, `Maintenance`, `Diagnostics`, and `Settings` instead of `Hardware Telemetry`, `Processing Queue`, `Pipeline Output`, `Pending Publish`, `Rename Files`, `Launch Pipeline`, `Reports & Audit`, `Distributed Workers`, `Maintenance Tools`, `System Diagnostics`, and `Pipeline Settings`. Noncanonical panels include `Source Scan Progress`, `Audit Progress`, `Worker Progress`, and `Health Progress`.  
Why It Matters: Section 8 is the source of truth for operator vocabulary and DOM/inventory checks. Drift increases parity risk and makes automation brittle.  
Recommended Fix: Normalize page titles and panel names to Section 8, or update the design reference before shipping intentional new names.  
Suggested Test: Generate a page/panel inventory from `index.html` and compare it to a machine-readable Section 8 list.  
Regression Risk: Low. Text and selectors may be affected if tests rely on headings.  
Priority: P2 before or shortly after promotion, but before closing UI tasks.

### V5-F009

ID: V5-F009  
Severity: Medium  
Area: Action hierarchy and destructive-adjacent controls  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/ui_web/index.html`; `V5_UI_DESIGN_REFERENCE.md`  
Evidence: Pending publish has `pending-drain-button` styled as `danger-button` for `Publish Parked Outputs`. Dashboard has Hard Kill and Publish Parked Outputs controls styled as danger buttons. The design reference says destructive or destructive-adjacent actions should not be large/red by default and only become primary/red at the confirmation step where appropriate.  
Why It Matters: Publishing parked output and killing processes are high-impact actions. Red/default-danger treatment on the main page can either overstate normal operations or normalize destructive controls.  
Recommended Fix: Use secondary/tertiary action styling before confirmation. Make the confirmation dialog the only place where danger styling is used for destructive actions.  
Suggested Test: Add a UI static test that blocks `.danger-button` for launch, drain, kill, delete, overwrite, promote/demote, and save actions outside confirmation containers.  
Regression Risk: Low. Primarily visual/action hierarchy.  
Priority: P2 before daily-driver promotion.

### V5-F010

ID: V5-F010  
Severity: Medium  
Area: Frontend readiness inference  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js`; `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/diagnosticsTailView.js`; backend launch and diagnostics DTOs  
Evidence: `launchView.js` builds local preflight and launch decision text from frontend state and exposes `window.pipelineLaunchPreflightLines`. `diagnosticsTailView.js` counts log words such as `error`, `failed`, and `fatal` to derive `operatorStatus` values like blocked/review/ready. Backend start revalidates launch, and diagnostics tail uses allowlisted target keys, but the UI still presents derived readiness-like facts.  
Why It Matters: The frontend may display readiness, route safety, or diagnostic severity differently from the backend. V5's operating model requires backend-authored launch and safety decisions.  
Recommended Fix: Move readiness/severity fields into backend DTOs or label frontend-only views as advisory and avoid enabling commands from inferred state. Use a dedicated backend launch preflight route if the UI needs authoritative gate reasons.  
Suggested Test: Add a negative launch test where frontend-visible rows look valid but backend launch is blocked, and verify the button remains disabled with backend-authored reason. Add diagnostics tests for benign log text containing the word `failed`.  
Regression Risk: Medium. DTO and UI state changes can affect multiple pages.  
Priority: P2 before promotion if these fields gate commands; otherwise immediately after blockers.

### V5-F011

ID: V5-F011  
Severity: Medium  
Area: CSS token discipline and visual system compliance  
Files/Functions: `DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css`; `V5_UI_DESIGN_REFERENCE.md` Sections 2, 3, and 10  
Evidence: `styles.css` includes raw fallback hex values and undefined token fallbacks such as `var(--red-900, #450a0a)`, `var(--red-700, #b91c1c)`, `var(--blue-800, #1e3a5f)`, and `var(--red-200, #fecaca)`. It also includes raw `rgba(0, 0, 0, 0.5)` shadow, raw `hsl(5 68% 48% / 0.35)` in keyframes, arbitrary `font-size: 10px`, `gap: 2px`, `padding: 2px 7px`, and opacity-based de-emphasis such as `opacity: 0.45`.  
Why It Matters: The design reference explicitly forbids raw hex, one-off hsl, arbitrary font/spacing values, invented shadows, and opacity-based text de-emphasis. These patterns create inconsistent status chips and lower accessibility confidence.  
Recommended Fix: Replace raw fallbacks with defined tokens, add any needed tokens to the reference first, remove opacity de-emphasis in favor of explicit token colors, and normalize sizes/spacing to the scale.  
Suggested Test: Add a CSS lint script that allows hsl only in token definitions and fails on raw hex, raw rgba shadows, opacity on text/status classes, and pixel sizes outside documented tokens.  
Regression Risk: Low to Medium. Visual changes may need screenshot review.  
Priority: P3 after safety blockers but before UI signoff.

### V5-F012

ID: V5-F012  
Severity: Medium  
Area: PowerShell disk-space fail-closed behavior  
Files/Functions: `Pipeline\Modules\Disk.ps1::Get-FreeSpaceGBAny`; `Pipeline\Modules\Disk.ps1::Copy-FileRobocopy`; publish/copy callers  
Evidence: `Get-FreeSpaceGBAny` can return `-1` for unknown or timed-out destination free space. `Copy-FileRobocopy` only blocks when `$dstFree -ge 0 -and $dstFree -lt $reserveGB`, so unknown free space proceeds to copy.  
Why It Matters: Unknown destination space should not be treated as safe for output copy. This can convert a recoverable deferred-publish case into a partial copy, false success, or unclear failure.  
Recommended Fix: Treat unknown destination space as a structured preflight failure before copy. For final output publish, park artifacts and return deferred publish when local artifacts are safely parked.  
Suggested Test: Mock `Get-FreeSpaceGBAny` returning `-1` and assert copy is blocked before mutation. Add a low-space/unknown-space pending-publish regression that leaves parked media plus sidecars intact.  
Regression Risk: Medium. Some environments with unreadable free space may now require explicit operator action.  
Priority: P2 before daily-driver promotion.

### V5-F013

ID: V5-F013  
Severity: Low  
Area: Runtime state layout consistency  
Files/Functions: `Pipeline\MediaPipeline_chatgpt.ps1`; `Pipeline\Modules\StateStore.ps1`  
Evidence: `MediaPipeline_chatgpt.ps1` creates `LocalStateLayout` and stores the event log under `State\Progress`, but `LogFile` remains `Join-Path $LocalBase "pipeline_debug.log"` and `LockFile` remains `Join-Path $LocalBase "pipeline.lock"`. `StateStore.ps1` still contains legacy event-log migration helpers.  
Why It Matters: The V5 operating model centers runtime state under `LocalBase\State`. Root-level logs and locks complicate cleanup, packaging, diagnostics, and operator state inspection.  
Recommended Fix: Decide whether root log/lock paths are intentional compatibility artifacts. If not, migrate them under `State` with backward-compatible discovery and docs.  
Suggested Test: Add a state-layout test that creates a temp `LocalBase`, runs a no-op/audit mode, and asserts all expected runtime state paths.  
Regression Risk: Medium if external scripts tail root-level files.  
Priority: P3 after safety blockers.

### V5-F014

ID: V5-F014  
Severity: Medium  
Area: Test environment and false confidence  
Files/Functions: `DesktopApp/tests`; `Pipeline/Tests`; `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`; `Docs/CURRENT_PROJECT_STATE.md`  
Evidence: `python -m pytest ...` failed with `No module named pytest`. PowerShell contract schema checks passed, but reliability and end-to-end smokes failed. `Docs/CURRENT_PROJECT_STATE.md` says reliability regression checks and release self-tests passed as of 2026-05-17, which is stale after the 2026-05-18 run. Browser mutation matrix route counts are also stale.  
Why It Matters: A transition workspace can appear safe because docs and cache artifacts say tests exist, while the current environment cannot run them or current tests fail.  
Recommended Fix: Add a bootstrap/test environment command for Python, make route-count tests authoritative, and update current-state docs after green validation only.  
Suggested Test: Run the full command set in section 20 on a clean Windows bundle and archive the exact output path in the remediation log.  
Regression Risk: Low. Test-only plus docs, but it may reveal more failures.  
Priority: P1 before promotion.

### V5-F015

ID: V5-F015  
Severity: Medium  
Area: Documentation and inventory drift  
Files/Functions: `WEBVIEW_DOM_ID_INVENTORY.md`; `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`; `API_ROUTE_INVENTORY.md`; `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`; `DOC_TOUCH_LOG.md`; `REMEDIATION_CHANGELOG.md`; `Docs/CURRENT_PROJECT_STATE.md`  
Evidence: `index.html` currently has 1009 unique IDs; `WEBVIEW_DOM_ID_INVENTORY.md` reports 972. The JS asset folder has 30 files, but namespace/global export totals in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` are internally inconsistent and stale. `API_ROUTE_INVENTORY.md` says 43 routes while route files expose more. `DOC_TOUCH_LOG.md` requires inventory/touch-log updates for route, DOM, export, and UI changes, but current implementation has drifted.  
Why It Matters: V5 uses inventories as safety rails for a Tauri/WebView2 transition. Stale inventories make smoke tests and reviews less meaningful.  
Recommended Fix: Regenerate inventories after blocker remediation, reconcile conflicting totals, and add the new review files to doc indexes/touch logs in a separate documentation update.  
Suggested Test: Add CI/static checks that compare live DOM IDs, global exports, and route maps to inventory files.  
Regression Risk: Low. Documentation and checks only.  
Priority: P2 after command-safety fixes.

## 4) Architecture and Boundary Review

The documented architecture is sound: V4/Tk remains the stable fallback, V5 is the active remediation/WebView transition workspace, and WebView/Tauri must stay a control and monitoring surface. `Docs/CURRENT_PROJECT_STATE.md` explicitly says the frontend must not own filesystem mutation, media policy, settings persistence, queue mutation, pending drain, rename, or process lifecycle decisions.

Current code only partially honors that boundary. Backend start has meaningful precondition validation and rechecks schedule/active-work/launch-lock state before starting the pipeline. Diagnostics open/tail uses backend allowlist target identifiers rather than frontend file paths. Rename, settings, and pending publish are routed through backend services.

The main boundary violations are the unsafe backend shutdown contract, the undocumented queue priority mutation route, and Dashboard duplicating launch/drain/kill command surfaces. Frontend code also derives readiness-like and diagnostic status language in several places. These are fixable, but they should be treated as architectural issues rather than UI polish.

## 5) WebView UI Compliance Review

`V5_UI_DESIGN_REFERENCE.md` is explicit that it is the source of truth. The current WebView has correct canonical nav labels for the 13 pages, but the page titles, panel names, panel types, action hierarchy, and CSS token usage have drifted.

Observed page-title drift:

| Page | Current H1 | Required title |
| --- | --- | --- |
| Telemetry | `Telemetry` | `Hardware Telemetry` |
| Queue | `Queue` | `Processing Queue` |
| Output | `Output` | `Pipeline Output` |
| Publish | `Publish` | `Pending Publish` |
| Rename | `Rename` | `Rename Files` |
| Launch | `Launch` | `Launch Pipeline` |
| Reports | `Reports` | `Reports & Audit` |
| Workers | `Network` | `Distributed Workers` |
| Maintenance | `Maintenance` | `Maintenance Tools` |
| Diagnostics | `Diagnostics` | `System Diagnostics` |
| Settings | `Settings` | `Pipeline Settings` |

Observed panel issues:

- `At A Glance` uses `data-panel-type="status"`, but Section 10 only allows `evidence` or `interactive`.
- `Queue Snapshot` and `Recently Completed` are evidence panels with navigation buttons, while evidence panels may only contain Copy.
- Dashboard `Pipeline Overview` is interactive and contains sample-validation controls, but the design reference makes it read-only evidence.
- Noncanonical panel names such as `Source Scan Progress`, `Audit Progress`, `Worker Progress`, and `Health Progress` should either be renamed to Section 8 names or added to the design reference before implementation.

Action hierarchy issues:

- Dashboard has Start, Stop, Hard Kill, and Publish Parked Outputs controls.
- Pending publish exposes Publish Parked Outputs as a danger button.
- Launch includes controls above the Start Pipeline panel, weakening the rule that panels above Start Pipeline are read-only evidence.

CSS issues are covered in V5-F011. They are not cosmetic-only because the design reference treats token discipline as a reliability and trust requirement.

## 6) Backend/API Contract Review

Positive findings:

- `DesktopApp/mediapipeline_desktop_app/services/handler.py` requires auth for registered GET and POST handlers, with `/api/health` handled separately.
- `DesktopApp/mediapipeline_desktop_app/services/command_journal.py` provides bounded command history and atomic save behavior.
- Launch/start route code validates mode, schedule gate, launch lock, active work, and argument shape before spawning work.
- Diagnostics open/tail uses named allowlist targets instead of arbitrary frontend paths.

Contract risks:

- `/api/backend/shutdown` violates backend-owned precondition enforcement by succeeding even when unsafe.
- `/api/queue/priority` exists outside contracts and inventory.
- Route inventory totals are stale, and tests are not currently proving that implemented route maps match documented contract files.
- Some read surfaces derive operator status in frontend code. Reads should remain side-effect free, but readiness facts should come from backend DTOs when they affect command availability.

Command routes needing special regression coverage:

- Launch/start, stop, pause, kill, and backend shutdown.
- Rename apply.
- Save settings and schedule save.
- Clear failures and audit/rerun.
- Pending publish drain.
- Maintenance/release package.
- Diagnostics log tail/open.
- Worker/network endpoints.
- Queue priority if retained.

## 7) PowerShell Pipeline Review

Positive findings:

- `Pipeline\MediaPipeline_chatgpt.ps1` prefers bundled PowerShell 7 before system PowerShell and prefers bundled FFmpeg/ffprobe/MKVToolNix/Python tools before system tools unless fallback is explicitly allowed.
- Config loading centers on `Pipeline\MediaPipeline_config_chatgpt.psd1`, with a legacy fallback.
- Scratch-copy behavior is present for remux and encode paths. `Ensure-ScratchCopy` copies to scratch, writes source fingerprint evidence, verifies copy, and cleans scratch on failure.
- Pending publish implementation parks local output plus relevant sidecars and treats low-space output parking as deferred publish, not a processing failure.
- Rerun CSV handling rejects invalid original mode and uses copy-only/audit behavior rather than mutating sources.

Risks:

- Queue priority phase contract currently fails the reliability regression suite.
- End-to-end deferred-publish drain smoke fails under the harness.
- `Disk.ps1` treats unknown destination free space as allowed-to-copy.
- Runtime state is mostly under `LocalBase\State`, but debug log and lock file remain at `LocalBase` root.

The PowerShell side is closer to the desired backend-owned media policy than the WebView, but it currently needs regression repair before promotion.

## 8) Python Host/App Review

Positive findings:

- The local API handler applies token protection to registered route maps.
- Command journaling exists and filters structured command results.
- Process launch/start code validates backend preconditions and uses active-work blockers.
- Diagnostics open policy normalizes target identifiers and rejects unknown targets.
- Settings, schedule, rename, diagnostics, and pending publish surfaces are generally routed through backend services instead of frontend direct filesystem mutation.

Risks:

- Backend shutdown lifecycle is unsafe by contract, not just by UI.
- Queue priority service writes a manifest from frontend-submitted path strings.
- Python test environment is incomplete in this workspace, so host/app tests could not be executed.
- Several UI-facing DTOs and frontend helpers can create state desynchronization if the frontend presents derived status as authoritative.

The highest-priority Python fixes are lifecycle command safety, queue priority contract ownership, and restoring executable test coverage.

## 9) V4-to-V5 Parity Review

V4 remains the stable fallback. V5 WebView should be judged by operator capability, backend safety, and evidence quality, not by exact widget replication.

Fully or mostly ported capabilities:

- Dashboard/status monitoring.
- Telemetry readouts.
- Queue and completed item visibility.
- Output and evidence packet viewing.
- Pending publish inspection and drain entry point.
- Rename preview/apply through backend.
- Settings display/save through backend.
- Diagnostics tail/open through allowlisted targets.
- Maintenance and release-package surfaces.

Partial or risky capabilities:

- Launch/start/stop/kill exists but command hierarchy has spread to Dashboard.
- Queue priority is newly exposed and undocumented.
- Workers/network appears read-oriented, which matches the design reference, but any lifecycle controls should remain absent unless documented.
- Repair/reconcile and sample-validation flows appear in Dashboard despite not being canonical Dashboard panels.

Missing or still transition debt:

- Clean-machine Tauri/WebView2 package validation.
- Representative real-media validation beyond synthetic smokes.
- Green reliability and end-to-end smoke runs.
- Full DOM/global/route inventory parity.

Daily-driver blockers are safety and contract issues, not exact V4 widget parity.

## 10) File Safety and State Integrity Review

Source-file protection is mostly respected in the PowerShell media path: normal remux/encode operations copy sources to scratch first, and source deletion remains an explicit policy toggle rather than default behavior.

State integrity concerns:

- Queue priority manifest writes are based on frontend-provided path strings rather than backend-owned row identity.
- Unknown destination free space proceeds in `Copy-FileRobocopy`.
- Root-level `pipeline_debug.log` and `pipeline.lock` remain outside the main `State` layout.
- Tests need to prove that browser smoke and command smoke flows do not mutate source media or source-side sidecars.

Recommended safety posture:

- Fail closed on ambiguous file scope, unknown disk space, and stale queue rows.
- Treat source mutation as an explicit backend-owned policy with visible evidence.
- Add no-mutation assertions around every browser smoke labeled "does not mutate."

## 11) Pending Publish and Deferred Publish Review

The pending publish model is one of the stronger V5 areas. `PublishCompletion.ps1` and pending transaction helpers model parked output as media plus sidecars, and low-space final publish can be deferred without converting the original processing run into a false failure.

The current blocker is validation: the end-to-end deferred-publish drain smoke failed under the harness. Until that is understood and fixed, the implementation should not be considered production-proven.

UI issues:

- Pending drain should not be a default danger action.
- Drain scope must remain read-only evidence until backend confirms eligibility.
- The UI should distinguish loaded/backend scope from visible-filtered rows before any drain confirmation.

## 12) Diagnostics and Recovery Review

Positive findings:

- Diagnostics open/tail routes use allowlisted target identifiers.
- Frontend text says diagnostics are backend allowlist-based.
- State summary and log targets are surfaced as operator evidence.

Risks:

- `diagnosticsTailView.js` derives blocked/review/ready status by scanning log words. This can be useful as advisory evidence, but it should not be presented as backend-authored health.
- Backend shutdown can proceed while unsafe, which undermines diagnostics/recovery expectations.
- End-to-end smoke failure needs preserved logs and operator-visible error evidence.

Recommended recovery improvements:

- Add backend-authored diagnostics severity fields where command gating depends on status.
- Preserve failed smoke workspaces automatically when release or end-to-end tests fail.
- Make unsafe lifecycle requests fail with recovery instructions.

## 13) Settings/Config Review

The operating model expects live config in `Pipeline\MediaPipeline_config_chatgpt.psd1` and the clean template in `Pipeline\MediaPipeline_config_template.psd1`. The pipeline code loads the chatgpt config by default and falls back to a legacy config name.

Settings risks:

- Save Settings must remain the only primary settings mutation.
- Config Health and Policy Readiness panels should be read-only at the top of Settings.
- Any WebView-side derivation of policy readiness should be advisory unless backed by backend DTOs.
- Folder-level policy validation should include nested source/scratch/output/pending-publish paths and should report explicit containment conflicts.

Recommended next review after blockers: run a focused settings negative test for nested paths, invalid source/output overlap, source deletion toggle, system-tool fallback toggles, and preservation of unknown config keys.

## 14) Rename/Queue/Launch/Output Workflow Review

Rename:

- Rename should stay backend-owned: preview, collisions, apply, sidecar handling, and audit evidence should not be reconstructed in the frontend.
- Confirm apply has command history and failure evidence before daily-driver use.

Queue:

- Queue viewing is useful, but queue priority mutation is not ready until route contracts and backend path validation are fixed.
- Launch scope previews must distinguish backend-loaded rows from visible-filtered rows.

Launch:

- Backend start has useful precondition validation.
- UI command hierarchy needs cleanup: Dashboard should not duplicate launch controls, and Launch should use backend-authored readiness gates.

Output:

- Output evidence packet should remain read-only with copy-only evidence controls.
- Output acceptance must be backend-authored after verification, not inferred by frontend status chips.

## 15) Worker/Network Mode Review

The design reference makes Distributed Workers read-only unless a documented backend route, precondition validation, command history, and tests exist. The current WebView should therefore avoid start/stop/promote/demote controls for workers.

Recommended checks:

- Confirm worker page panels are `data-panel-type="evidence"` unless they only contain safe filtering/copy actions.
- Confirm any network/worker endpoint is read-only or has explicit command contract, journal entry, and tests.
- Keep worker lifecycle management V4-only or backend-only until the transition docs explicitly permit WebView controls.

## 16) Packaging/Release Review

Positive findings:

- Bundled PowerShell 7, FFmpeg/ffprobe, MKVToolNix, Python, and related tools are preferred before system tools.
- Parser checks passed for the main pipeline script under both system PowerShell and bundled PowerShell.

Release blockers:

- Reliability regression and end-to-end smoke tests are red.
- Python route/host tests could not run due missing `pytest`.
- Current project state docs overstate validation status.
- Clean-machine Tauri/WebView2 packaging should wait until API and UI contracts are stable again.

Packaging should not be used as evidence of readiness until the full validation set in section 20 passes from the portable bundle.

## 17) Test Coverage and Validation Gaps

Validation run on 2026-05-18:

| Check | Result | Notes |
| --- | --- | --- |
| PowerShell contract schema checks | Passed | `Pipeline/Tests/Unit/Invoke-ContractSchemaChecks.ps1` |
| Main pipeline parser, system PowerShell | Passed | `Pipeline/MediaPipeline_chatgpt.ps1` |
| Main pipeline parser, bundled PowerShell | Passed | Bundled `pwsh.exe` reported 7.6.1 |
| Reliability regression checks | Failed | `priority queue item contract changed` |
| End-to-end smoke checks | Failed | Deferred-publish drain smoke hit parser error under harness |
| Python pytest subset | Not run | `No module named pytest` |
| DOM/panel static scan | Failed | Invalid panel type and design drift |
| Route inventory static scan | Failed | Implemented routes exceed documented contracts |

Remediation note, 2026-05-18: follow-up chunks now use the bundled interpreter at `DesktopApp\Runtime\Python\python.exe`; route inventory drift coverage was added in `DesktopApp\tests\test_api_route_inventory.py`. Treat the table above as the original review snapshot, not current post-remediation status.

Coverage gaps:

- Unsafe command negative tests should be as strong as happy-path tests.
- Browser mutation smokes need explicit no-mutation assertions on source files and sidecars.
- Route inventory tests must compare implemented maps, contracts, inventories, and UI call sites.
- CSS token lint should run before UI tasks close.
- Disabled/error states need browser smoke coverage, not only happy-path rendering.

## 18) Documentation and Inventory Gaps

Stale or conflicting docs:

- `API_ROUTE_INVENTORY.md` route count is stale and omits `/api/queue/priority`.
- `WEBVIEW_DOM_ID_INVENTORY.md` reports 972 IDs; current `index.html` has 1009 unique IDs.
- `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` has inconsistent namespace/global totals.
- `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` still refers to a 41-route contract.
- `Docs/CURRENT_PROJECT_STATE.md` says reliability regression checks and release self-tests passed, but current validation is red.
- `REMEDIATION_CHANGELOG.md` records Dashboard command additions, but `V5_UI_DESIGN_REFERENCE.md` was not updated to allow those panels.

Documentation hygiene recommendation:

- Treat `V5_UI_DESIGN_REFERENCE.md` as source of truth until deliberately changed.
- After blocker fixes, regenerate inventories from code.
- Add these review files to `DOCS_INDEX.md` and `DOC_TOUCH_LOG.md` in a separate documentation-only change. I did not update those files during this review because the user requested only the two review artifacts.

## 19) Prioritized Remediation Plan

1. Fix backend shutdown to fail closed when unsafe, then update lifecycle tests.
2. Decide queue priority scope. Either remove/feature-flag it or fully contract and harden it.
3. Restore green PowerShell reliability and end-to-end deferred-publish smoke tests.
4. Remove or redesign Dashboard mutation controls according to `V5_UI_DESIGN_REFERENCE.md`.
5. Fix evidence panel typing, canonical page titles, and panel names.
6. Fail closed on unknown destination free space and add low-space/unknown-space tests.
7. Move readiness/severity facts into backend DTOs where they affect command availability.
8. Clean CSS token violations and add lint.
9. Regenerate route, DOM ID, and global export inventories.
10. Run full browser, Python, PowerShell, and release self-tests from the portable bundle.
11. Update current-state docs only after the above validation is green.

## 20) Suggested Test Commands

Run from:

```powershell
Set-Location 'C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5'
```

PowerShell parser and schema:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-ContractSchemaChecks.ps1

$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path 'Pipeline/MediaPipeline_chatgpt.ps1'),
  [ref]$tokens,
  [ref]$errors
) | Out-Null
if ($errors.Count) { $errors | Format-List *; exit 1 }
'parse ok'

& 'Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe' -NoProfile -ExecutionPolicy Bypass -Command @'
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path "Pipeline/MediaPipeline_chatgpt.ps1"),
  [ref]$tokens,
  [ref]$errors
) | Out-Null
if ($errors.Count) { $errors | Format-List *; exit 1 }
"bundled parse ok"
'@
```

PowerShell regression and end-to-end:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1

$env:MEDIA_PIPELINE_KEEP_FAILED_SMOKE = '1'
pwsh -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1
Remove-Item Env:\MEDIA_PIPELINE_KEEP_FAILED_SMOKE -ErrorAction SilentlyContinue
```

Python API/host tests:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m unittest `
  DesktopApp.tests.test_application_facade.ApplicationFacadeTests.test_local_api_route_maps_cover_documented_api_contract `
  DesktopApp.tests.test_api_contract_payload.LocalApiContractPayloadTests.test_full_contract_keeps_effectful_routes_token_protected `
  DesktopApp.tests.test_api_route_inventory `
  DesktopApp.tests.test_local_api_lifecycle_contract_smoke `
  -q
& $py -m pytest DesktopApp\tests -q
```

Use the bundled interpreter above for portable-bundle validation. System Python may not have `pytest` installed and is not the canonical V5 test environment.

Route inventory check:

```powershell
@'
from pathlib import Path
import ast
root = Path("DesktopApp/mediapipeline_desktop_app/api")
for name in ["routes_read.py", "routes_command.py", "contract_read.py", "contract_command.py"]:
    text = (root / name).read_text(encoding="utf-8")
    tree = ast.parse(text)
    routes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("/api/"):
            routes.append(node.value)
    print(name, len(sorted(set(routes))), sorted(set(routes)))
'@ | DesktopApp\Runtime\Python\python.exe -
DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_api_route_inventory -q
```

DOM/panel compliance check:

```powershell
@'
from html.parser import HTMLParser
from pathlib import Path
class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.panels = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "section" and "panel" in attrs.get("class", "").split():
            self.panels.append(attrs.get("data-panel-type"))
p = P()
p.feed(Path("DesktopApp/mediapipeline_desktop_app/ui_web/index.html").read_text(encoding="utf-8"))
print("ids", len(p.ids), "unique", len(set(p.ids)))
print("invalid panel types", sorted({x for x in p.panels if x not in {"evidence", "interactive"}}))
'@ | python -
```

CSS token scan:

```powershell
Select-String -Path DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css -Pattern '#[0-9a-fA-F]{3,8}\b'
Select-String -Path DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css -Pattern 'rgba\(|hsl\('
Select-String -Path DesktopApp/mediapipeline_desktop_app/ui_web/static/styles.css -Pattern 'opacity:\s*0\.|font-size:\s*[0-9]+px|gap:\s*[0-9]+px|padding:\s*[0-9]+px'
```

Browser smoke discovery:

```powershell
Get-ChildItem -Path SmokeTests -Filter 'Test-WebViewBrowser*.ps1' | Sort-Object Name | Select-Object Name
```

Run the browser smoke scripts after the local API/WebView host is started, using the repo's documented smoke workflow. Mutation-boundary smokes should record source file hashes before and after.

## 21) Open Questions

1. Is queue priority intended to be part of V5 daily-driver scope, or should it remain hidden until the route contract and queue-planning schema are finalized?
2. Should Dashboard include any command shortcuts, or is `V5_UI_DESIGN_REFERENCE.md` still authoritative that Dashboard is evidence/readiness only?
3. Is root-level `pipeline_debug.log` and `pipeline.lock` intentional V4 compatibility, or should these migrate under `LocalBase\State`?
4. What is the expected bootstrap command for Python tests in a clean portable workspace?
5. Should unsafe backend shutdown be available only through a force-confirmation route, or removed entirely from WebView/Tauri?
6. Which docs should be the canonical daily-driver promotion gate: `Docs/CURRENT_PROJECT_STATE.md`, `ACTIVE_FIX_CHECKLIST.md`, or a new release-readiness checklist?
7. Should frontend-derived diagnostics severity remain advisory text, or should all diagnostic severity labels come from backend DTOs?
