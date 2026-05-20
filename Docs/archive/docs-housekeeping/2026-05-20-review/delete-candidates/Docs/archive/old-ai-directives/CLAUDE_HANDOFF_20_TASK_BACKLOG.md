# Claude Handoff: 20 Bounded V5 Transition Tasks

Repository:

`C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Purpose:

This document carves out twenty bounded tasks that can be delegated to Claude while Codex continues V5 transition work. These tasks are intentionally scoped to documentation, test wrappers, static coverage, parity audits, and low-risk WebView/Tauri validation. They should not change media-processing policy, backend mutation semantics, source/scratch/output behavior, or Tk fallback behavior.

## Global Rules For Claude

1. Do not touch V4.
2. Do not weaken or remove Tk.
3. Do not add frontend-owned filesystem mutation.
4. Do not add frontend-only mutation workflows.
5. Do not change FFmpeg, subtitle, audio, remux/encode, pending-publish, source deletion, scratch-copy, or media policy unless a task explicitly says to document an issue.
6. Do not change Local API route semantics, command journal behavior, strict JSON handling, duplicate command guards, close-readiness checks, or command contracts.
7. Keep Network mode read-only.
8. Prefer docs, static tests, wrappers, smoke test organization, and audit artifacts.
9. Keep each task as a separate patch-like unit where possible.
10. After each task, report files changed, tests run, and anything intentionally deferred.

## Coordination Notes

These files may be touched only by the task that names them:

- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `DesktopApp/tests/test_tauri_shell_scaffold.py`
- `Docs/DOCS_INDEX.md`
- `Docs/TLDR.md`
- `Docs/REMEDIATION_CHANGELOG.md`
- Root `Test-WebView*.ps1` wrapper files

Do not edit these recent Codex-owned implementation files unless the task explicitly references them:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js`
- `DesktopApp/tests/test_webview_browser_settings_launch_smoke.py`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/renameView.js`
- `DesktopApp/tests/test_webview_browser_rename_smoke.py`

Use bundled PowerShell 7 for release checks:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Windows PowerShell 5 may misparse PowerShell 7 syntax in the pipeline and should not be used as the release parser host.

## Universal Validation Commands

Run the smallest relevant subset first. If a task touches WebView/Tauri/static assets, also run Tauri shell scaffold tests.

```powershell
python -m py_compile <changed-python-file>
python -m unittest <specific-test-module-or-test-case> -q
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
python -m unittest discover -s DesktopApp\tests -q
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Do not run tool integration or end-to-end smoke unless specifically asked; those are longer and may require real bundled tools/media assumptions.

## Task Index

| ID | Title | Type | Risk | Dependency | Primary Output |
|---|---|---:|---:|---|---|
| C-001 | Root wrapper for Rename Readiness smoke | Test/Release | Low | None | New root wrapper + release layout |
| C-002 | Root wrapper for Settings/Launch browser smoke | Test/Release | Low | Codex-added browser smoke exists | New root wrapper + release layout |
| C-003 | WebView smoke wrapper catalog update | Docs | Low | C-001/C-002 preferred | Updated docs index/TLDR/changelog |
| C-004 | Tauri parity matrix refresh | Docs/Audit | Low | None | Updated parity matrix |
| C-005 | WebView operator copy consistency audit | Docs/Audit | Low | None | New audit doc |
| C-006 | Diagnostics read-only target runbook | Docs | Low | None | New diagnostics runbook |
| C-007 | Settings builder coverage matrix | Docs/Test | Low | None | Coverage matrix and optional static test |
| C-008 | Local API command/read route ownership map | Docs | Low | None | Route ownership doc |
| C-009 | Browser smoke execution runbook | Docs | Low | C-001/C-002 helpful | Runbook for browser smokes |
| C-010 | Read-only Network parity audit | Docs/Audit | Low | None | Network parity findings |
| C-011 | Rename safety fixture/test inventory | Docs/Audit | Low | None | Rename test gap matrix |
| C-012 | Pending-publish fixture inventory | Docs/Audit | Low | None | Pending-publish state matrix |
| C-013 | Static DOM ID namespace audit | Test | Low | None | Static test or audit doc |
| C-014 | Version label and stale V3/V4 text audit | Docs/Audit | Low | None | Stale-label report |
| C-015 | PowerShell host expectation audit | Docs/Test | Medium | None | PS7-vs-PS5 guidance or safe test |
| C-016 | Real-media validation playbook refresh | Docs | Low | None | Updated playbook |
| C-017 | Tauri lifecycle boundary notes | Docs | Low | None | Backend lifecycle notes |
| C-018 | WebView navigation/accessibility static smoke | Test | Low | None | Static/browser smoke |
| C-019 | Command history consistency audit | Test/Docs | Low | None | Static test or gap doc |
| C-020 | Module ownership and over-fragmentation review | Docs/Audit | Low | None | Architecture review addendum |

## Task Details

### C-001: Root Wrapper For Rename Readiness Smoke

Goal:

Add a root-level wrapper for the existing non-browser rename readiness smoke so operators and release checks can run it consistently.

Allowed files:

- Create `Test-WebViewRenameReadinessSmoke.ps1`
- Update `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- Update `DesktopApp/tests/test_tauri_shell_scaffold.py`
- Update docs only if required for release/test references

Do not touch:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/renameView.js`
- `DesktopApp/mediapipeline_desktop_app/service_rename.py`
- Backend rename routes

Acceptance:

- Root wrapper invokes the existing Python/unittest smoke.
- Release self-test layout recognizes the wrapper.
- Tauri shell scaffold/static tests expect the wrapper.
- No rename behavior changes.

Validation:

```powershell
.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

### C-002: Root Wrapper For Settings/Launch Browser Smoke

Goal:

Add a root-level wrapper for Codex’s new browser-backed Settings-to-Launch smoke.

Allowed files:

- Create `Test-WebViewBrowserSettingsLaunchSmoke.ps1`
- Update `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- Update `DesktopApp/tests/test_tauri_shell_scaffold.py`
- Update docs only if required for wrapper discovery

Do not touch:

- `DesktopApp/tests/test_webview_browser_settings_launch_smoke.py` unless the wrapper exposes a naming/import issue.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js`
- Settings backend save/preview behavior

Acceptance:

- Wrapper runs `DesktopApp.tests.test_webview_browser_settings_launch_smoke`.
- Wrapper skips/fails consistently with the existing browser smoke pattern when Node/Chrome/Edge is unavailable.
- Release layout recognizes the wrapper.

Validation:

```powershell
.\SmokeTests\Test-WebViewBrowserSettingsLaunchSmoke.ps1
python -m unittest DesktopApp.tests.test_webview_browser_settings_launch_smoke -q
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

### C-003: WebView Smoke Wrapper Catalog Update

Goal:

Update human-facing docs so the growing smoke-wrapper set is understandable.

Allowed files:

- `Docs/DOCS_INDEX.md`
- `Docs/TLDR.md`
- `Docs/REMEDIATION_CHANGELOG.md`
- Optionally create `Docs/WEBVIEW_SMOKE_TEST_CATALOG.md`

Acceptance:

- Lists each `SmokeTests/Test-WebView*.ps1` wrapper.
- Explains browser-backed vs non-browser smokes.
- States that browser smokes require Node and Chrome/Edge.
- States that smoke tests do not prove real FFmpeg/media behavior.

Validation:

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

### C-004: Tauri Parity Matrix Refresh

Goal:

Refresh the parity matrix to reflect current WebView status without changing code.

Allowed files:

- `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md`
- Optionally `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Acceptance:

- Covers Home, Live, Queue, Completed, Pending Publish, Rename, Launch, Diagnostics, Settings, Maintenance, Schedule, Network.
- For each workflow, records Tk status, WebView status, missing actions, backend dependency, safety risk, and next task.
- Clearly identifies that Tk remains fallback.

Validation:

Manual doc review. No code tests required unless docs tests enforce links.

### C-005: WebView Operator Copy Consistency Audit

Goal:

Create an audit of confusing operator-facing text in WebView static assets.

Allowed files:

- Create `Docs/WEBVIEW_OPERATOR_COPY_AUDIT.md`

Do not change UI text in this task unless the issue is typo-only and risk-free.

Acceptance:

- Finds inconsistent labels such as launch/start, preview/apply, save/reload, staged/saved, ready/review/blocked.
- Groups findings by page.
- Recommends exact text changes but does not implement them unless trivial.

Validation:

No code tests required.

### C-006: Diagnostics Read-Only Target Runbook

Goal:

Document every diagnostics target exposed to WebView and what it is safe for.

Allowed files:

- Create `Docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`

Acceptance:

- Lists allowlisted tail/open targets.
- Explains what each target helps diagnose.
- Explains what it does not mutate.
- Includes operator sequence: queue issue, completed issue, pending publish issue, settings issue.

Validation:

Optional:

```powershell
python -m unittest DesktopApp.tests.test_webview_browser_diagnostics_handoff_smoke -q
```

### C-007: Settings Builder Coverage Matrix

Goal:

Map backend config schema fields to WebView structured settings builders.

Allowed files:

- Create `Docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- Optional static test in `DesktopApp/tests/test_settings_builder_coverage_static.py`

Acceptance:

- Lists all known `CONFIG_FIELD_DEFINITIONS` keys.
- Identifies whether each is covered by a structured WebView builder, raw JSON only, read-only display only, or intentionally hidden.
- Flags high-impact fields still raw-only.

Validation:

If adding a test:

```powershell
python -m py_compile DesktopApp\tests\test_settings_builder_coverage_static.py
python -m unittest DesktopApp.tests.test_settings_builder_coverage_static -q
```

### C-008: Local API Command/Read Route Ownership Map

Goal:

Document Local API routes and classify mutation ownership.

Allowed files:

- Create `Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`

Acceptance:

- Separates read routes from command routes.
- Lists route, command/effect, backend owner, frontend page, mutation risk.
- Confirms mutation routes are backend-owned.
- Flags routes that require token/auth.

Validation:

Optional:

```powershell
python -m unittest DesktopApp.tests.test_application_facade.LocalApiServerTests.test_web_and_tauri_shell_reference_all_local_api_contract_routes -q
```

### C-009: Browser Smoke Execution Runbook

Goal:

Create a practical runbook for browser-backed WebView smoke tests.

Allowed files:

- Create `Docs/BROWSER_SMOKE_TEST_RUNBOOK.md`

Acceptance:

- Documents Node and Chrome/Edge requirements.
- Explains what failures usually mean.
- Explains how to run individual browser smokes and full discovery.
- Explains why browser smokes are UI/runtime checks, not media-pipeline proof.

Validation:

No code tests required.

### C-010: Read-Only Network Parity Audit

Goal:

Audit the current Network page against the rule that WebView network mode remains read-only.

Allowed files:

- Create `Docs/NETWORK_READ_ONLY_PARITY_AUDIT.md`

Do not add network start/stop controls.

Acceptance:

- Lists visible Network data in Tk and WebView.
- Identifies missing read-only coordinator/worker visibility.
- Identifies what would be required before safe lifecycle controls can exist.
- Explicitly recommends no mutation controls until lifecycle ownership is designed and tested.

Validation:

No code tests required.

### C-011: Rename Safety Fixture/Test Inventory

Goal:

Inventory rename safety test coverage and remaining fixture gaps.

Allowed files:

- Create `Docs/RENAME_SAFETY_TEST_INVENTORY.md`

Do not alter rename behavior.

Acceptance:

- Covers TV season inference, specials/S00, movie scrubbing, force pipeline name, duplicate destination block, sidecar rename, rollback/transaction risk.
- Identifies existing tests and missing tests.
- Recommends concrete fixtures.

Validation:

Optional:

```powershell
python -m unittest DesktopApp.tests.test_webview_browser_rename_smoke -q
python -m unittest DesktopApp.tests.test_webview_rename_readiness_smoke -q
```

### C-012: Pending-Publish Fixture Inventory

Goal:

Document pending-publish state shapes and validation gaps.

Allowed files:

- Create `Docs/PENDING_PUBLISH_FIXTURE_INVENTORY.md`

Do not change pending-publish drain behavior.

Acceptance:

- Lists parked, ready, missing payload, missing sidecar, unreadable manifest, partial upload, stale local file, destination collision, auth/network failure scenarios.
- Maps each to expected operator-facing WebView state.
- Recommends tests but does not implement drain logic changes.

Validation:

Optional:

```powershell
python -m unittest discover -s DesktopApp\tests -p "*pending*" -q
```

### C-013: Static DOM ID Namespace Audit

Goal:

Ensure page-scoped DOM IDs remain unique and page-specific IDs stay in intended sections.

Allowed files:

- Optional new test: `DesktopApp/tests/test_webview_static_dom_id_namespace.py`
- Or doc-only output: `Docs/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`

Acceptance:

- Detect duplicate IDs in `index.html`.
- Check important page prefixes stay on their page where practical.
- Do not require fragile full HTML parsing if a simple robust parser is already available.

Validation:

```powershell
python -m py_compile DesktopApp\tests\test_webview_static_dom_id_namespace.py
python -m unittest DesktopApp.tests.test_webview_static_dom_id_namespace -q
```

### C-014: Version Label And Stale V3/V4 Text Audit

Goal:

Find stale V3/V4 labels or docs that could confuse V5 transition status.

Allowed files:

- Create `Docs/STALE_VERSION_LABEL_AUDIT.md`

Do not mass-replace version strings. Some V4 references are intentional backup/migration notes.

Acceptance:

- Greps for `V3`, `v3`, `V4`, `v4.`, `V5`, `v5`.
- Classifies each as expected, stale, or needs operator decision.
- Recommends targeted changes only.

Validation:

No code tests required.

### C-015: PowerShell Host Expectation Audit

Goal:

Document and, if safe, test that release and parser checks are expected to run through bundled PowerShell 7.

Allowed files:

- Create `Docs/POWERSHELL_HOST_EXPECTATIONS.md`
- Optional small static test if existing release checks already expose this safely.

Do not rewrite the release self-test.

Acceptance:

- Explains why Windows PowerShell 5 can fail on PS7 syntax.
- Lists scripts that should be launched via bundled `pwsh.exe`.
- Recommends whether root `.bat` launchers should enforce bundled PS7.
- Does not alter pipeline scripts.

Validation:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

### C-016: Real-Media Validation Playbook Refresh

Goal:

Refresh real-media validation instructions for V5 daily-use readiness.

Allowed files:

- `Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`

Acceptance:

- Separates UI smoke, backend route smoke, release checks, and real media proof.
- Adds sample media categories: low-bitrate H.264, PGS subtitles, TX3G subtitles, ASS/SSA, multi-audio, network output, pending publish.
- Lists exact evidence to capture: source size, output size, route reason, sidecar, completed manifest, pending publish state, stderr tail.

Validation:

No code tests required.

### C-017: Tauri Lifecycle Boundary Notes

Goal:

Document the intended Tauri/WebView2 backend lifecycle boundary.

Allowed files:

- Create `Docs/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
- Optionally update `Docs/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md` with a link

Acceptance:

- States that backend owns process starts/stops and mutation.
- States WebView shell should treat Local API as authority.
- Describes future production needs: spawn, health wait, token handling, close readiness, shutdown sequencing, orphan cleanup.
- Does not implement lifecycle changes.

Validation:

No code tests required.

### C-018: WebView Navigation/Accessibility Static Smoke

Goal:

Add or improve a static test that validates navigation buttons and page panels remain paired.

Allowed files:

- Optional new test: `DesktopApp/tests/test_webview_navigation_static.py`

Acceptance:

- Every `data-page` nav button has a matching `data-page-panel`.
- Every page panel has a nav button unless intentionally hidden.
- Active/visible defaults are sane.
- Does not test visual layout.

Validation:

```powershell
python -m py_compile DesktopApp\tests\test_webview_navigation_static.py
python -m unittest DesktopApp.tests.test_webview_navigation_static -q
```

### C-019: Command History Consistency Audit

Goal:

Audit command-history display consistency across Launch, Settings, Diagnostics, Pending Publish, Rename, and Maintenance.

Allowed files:

- Create `Docs/COMMAND_HISTORY_CONSISTENCY_AUDIT.md`
- Optional static test if there is a clear non-fragile invariant

Acceptance:

- Lists each command history panel/helper.
- Identifies inconsistent labels, missing severity/result handling, or missing diagnostics handoff.
- Recommends consolidation only if it reduces actual duplication.
- Does not alter command journal semantics.

Validation:

Optional:

```powershell
python -m unittest DesktopApp.tests.test_webview_command_evidence_smoke -q
```

### C-020: Module Ownership And Over-Fragmentation Review

Goal:

Review whether recent refactors improved maintainability or created excessive fragmentation.

Allowed files:

- Create `Docs/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md`

Do not refactor code in this task.

Acceptance:

- Reviews `DesktopApp/mediapipeline_desktop_app/application`, `api`, `services`, `ui_web/static/assets`, and Tauri shell boundaries.
- Identifies modules that are too thin, too broad, or appropriately scoped.
- Recommends consolidation only where it reduces cognitive load without weakening safety.
- Calls out areas that should stop being refactored for now.

Validation:

No code tests required.

## Preferred Order

If Claude is doing one task at a time, the safest order is:

1. C-001
2. C-002
3. C-003
4. C-004
5. C-006
6. C-009
7. C-016
8. C-017
9. C-007
10. C-008
11. C-010
12. C-011
13. C-012
14. C-013
15. C-018
16. C-019
17. C-014
18. C-015
19. C-005
20. C-020

## Final Report Expected From Claude

For each completed task, Claude should report:

```text
Task ID:
Changed files:
Tests run:
Result:
Deferred items:
Risks/assumptions:
Suggested next Claude task:
```

Any task that touches release checks or `SmokeTests/` wrappers should explicitly confirm that the release self-test was run through bundled PowerShell 7.

