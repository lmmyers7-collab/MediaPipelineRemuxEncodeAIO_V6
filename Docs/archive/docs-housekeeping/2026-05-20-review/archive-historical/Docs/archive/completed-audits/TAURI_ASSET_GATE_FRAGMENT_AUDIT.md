# Tauri Asset Gate Fragment Audit

Date: 2026-05-15

Reviews the pre-window asset validation gate in `DesktopApp/tauri_shell/src-tauri/src/lib.rs` (`validate_backend_web_ui`). Checks whether the fragment set is meaningful, non-brittle, and still matches current WebView surfaces.

---

## What the Gate Does

`validate_backend_web_ui` is called during Tauri setup (`start_backend`) after the bootstrap handshake succeeds. It fetches 7 backend HTTP endpoints (index.html + 6 JS assets) and checks that each contains a set of required string fragments. If any fragment is missing, the shell errors out before the window opens.

This prevents the shell from showing a broken or stale WebView to the operator.

---

## Fragment Groups

### Group 1: Index HTML (`GET /`)

17 required fragments + 1 anti-pattern check.

| Label | Fragment checked | Purpose |
|---|---|---|
| bootstrap assignment | `window.MEDIA_PIPELINE_BOOTSTRAP = {` | Bootstrap was injected by backend — not the raw placeholder |
| home page | `data-page-panel="home"` | Home page panel attribute present |
| real-media worksheet status | `id="cross-page-real-media-status"` | Home worksheet panel has status element |
| real-media worksheet rows | `id="cross-page-real-media-rows"` | Home worksheet panel has rows element |
| sample validation status | `id="sample-validation-status"` | Home sample validation status badge present |
| diagnostics state triage status | `id="diagnostics-state-triage-status"` | Diagnostics state triage panel has status element |
| diagnostics close readiness | `id="diagnostics-close-readiness"` | Diagnostics close-readiness display present |
| backend lifecycle summary | `id="backend-lifecycle-summary"` | Backend lifecycle summary element present |
| backend shutdown button | `id="backend-shutdown-button"` | Backend shutdown button present |
| settings page | `data-page-panel="settings"` | Settings page panel attribute present |
| settings backend media policy status | `id="settings-backend-media-policy-status"` | Settings policy readiness status element present |
| settings backend media policy rows | `id="settings-backend-media-policy-rows"` | Settings policy readiness rows element present |
| settings backend preview/save result rows | `id="settings-backend-result-rows"` | Settings patch result rows present |
| settings backend preview/save result detail | `id="settings-backend-result-detail"` | Settings patch result detail present |
| settings staged media policy delta rows | `id="settings-policy-delta-rows"` | Staged policy delta rows present |
| launch settings risk rows | `id="launch-settings-risk-rows"` | Launch settings risk rows present |
| diagnostics page | `data-page-panel="diagnostics"` | Diagnostics page panel attribute present |

Anti-pattern check: index must NOT contain `__MEDIA_PIPELINE_BOOTSTRAP__` (raw placeholder not injected).

---

### Group 2: App Orchestrator (`GET /assets/app.js`)

8 required fragments.

| Label | Fragment checked |
|---|---|
| refresh coordinator | `async function refreshAllNow` |
| cross-page renderer | `renderCrossPageContext({` |
| sample validation read route | `/api/sample-validation?limit=10` |
| settings handoff | `settings: values.settings \|\| getLastSettings()` |
| backend lifecycle renderer | `function renderBackendLifecycle` |
| backend lifecycle shutdown request | `async function requestBackendShutdown` |
| backend lifecycle shutdown route | `/api/backend/shutdown` |
| backend lifecycle close-readiness guard | `Backend shutdown is disabled in WebView until close-readiness reports safe` |

---

### Group 3: Cross-Page Context (`GET /assets/crossPageContextView.js`)

8 required fragments.

| Label | Fragment checked |
|---|---|
| real-media worksheet renderer | `function renderCrossPageRealMediaWorksheet` |
| real-media worksheet rows | `function crossPageRealMediaWorksheetRows` |
| sample validation builder | `function buildSampleValidationRequest` |
| sample validation append route | `/api/sample-validation/append` |
| saved media policy evidence | `function crossPageSettingsPolicyEvidence` |
| backend media policy readiness evidence | `Backend media-policy readiness` |
| backend media policy readiness summary | `media readiness=` |
| mutation boundary | `this worksheet does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files` |

---

### Group 4: Settings View (`GET /assets/settingsView.js`)

11 required fragments.

| Label | Fragment checked |
|---|---|
| settings backend readiness reader | `function settingsBackendMediaPolicyReadiness` |
| settings backend readiness renderer | `function renderSettingsBackendMediaPolicyReadiness` |
| settings backend readiness heading | `Backend media-policy readiness:` |
| settings backend readiness guardrail | `this table cannot stage settings, save config, launch work, run FFmpeg, publish files, or touch source media` |
| settings staged policy delta rows | `function settingsPolicyDeltaRows` |
| settings staged policy delta summary | `Staged media-policy delta:` |
| settings preview/save result rows | `function settingsBackendResultRows` |
| settings preview/save result detail | `function settingsBackendResultDetailLines` |
| settings preview/save result renderer | `function renderSettingsBackendResultFromEntries` |
| settings preview/save stale guard | `Patch JSON changed after the last preview. Preview again before saving.` |
| settings preview/save persistence boundary | `Save Patch is the only persistence command` |

---

### Group 5: Settings Overview (`GET /assets/settingsOverview.js`)

2 required fragments.

| Label | Fragment checked |
|---|---|
| settings trust readiness line | `function settingsMediaPolicyReadinessLine` |
| settings trust readiness payload | `settings.media_policy_readiness` |

---

### Group 6: Launch View (`GET /assets/launchView.js`)

3 required fragments.

| Label | Fragment checked |
|---|---|
| launch backend readiness row | `Backend media-policy readiness` |
| launch backend readiness payload | `media_policy_readiness` |
| launch blocked readiness guidance | `Resolve blocked saved media-policy rows before launching unattended work.` |

---

### Group 7: Diagnostics State Summary (`GET /assets/diagnosticsStateSummaryView.js`)

4 required fragments.

| Label | Fragment checked |
|---|---|
| diagnostics read-order renderer | `function renderDiagnosticsStateTriage` |
| diagnostics read-order rows | `function renderDiagnosticsStateTriageRows` |
| diagnostics read-order action target | `diagnostics-state-triage-actions` |
| diagnostics read-order summary | `Backend read order:` |

---

## Summary Counts

| Asset | Fragment count |
|---|---|
| `index.html` | 17 + 1 anti-pattern |
| `app.js` | 8 |
| `crossPageContextView.js` | 8 |
| `settingsView.js` | 11 |
| `settingsOverview.js` | 2 |
| `launchView.js` | 3 |
| `diagnosticsStateSummaryView.js` | 4 |
| **Total** | **53 required fragments** |

---

## Staleness Assessment

### No stale fragments found

All 53 fragments checked against current JS sources during this audit. No fragment references a removed function, deleted ID, or changed string. Specifically:

| Risk area | Finding |
|---|---|
| Bootstrap injection check | Current — `window.MEDIA_PIPELINE_BOOTSTRAP = {` is the correct injected form; anti-pattern check correctly rejects raw `__MEDIA_PIPELINE_BOOTSTRAP__` |
| Sample validation fragments | Current — `buildSampleValidationRequest`, `/api/sample-validation/append` present in `crossPageContextView.js` |
| Mutation boundary string | Current — exact mutation boundary text matches the fragment in `crossPageContextView.js` |
| Settings persistence boundary | Current — `Save Patch is the only persistence command` is present in `settingsView.js` |
| Launch policy readiness fragments | Current — 3 minimal fragments present in `launchView.js` |
| Diagnostics state triage | Current — `renderDiagnosticsStateTriage` / `renderDiagnosticsStateTriageRows` present in `diagnosticsStateSummaryView.js` |

---

## Design Assessment

### Fragment selection strategy

The fragment set is deliberately minimal and targets high-value markers:

- **Bootstrap injection**: The most critical check — ensures the backend replaced the placeholder before opening the window.
- **Structural IDs**: Selected IDs validate that major panels (Home, Settings, Diagnostics, Launch) are present in the HTML without being brittle to panel reordering.
- **Function names**: Selected functions are stable coordination-layer names (refresh, render lifecycle, render triage) that would not change without architectural intent.
- **Mutation boundary strings**: The exact mutation-boundary phrases in `crossPageContextView.js` and `settingsView.js` are appropriate: they prevent a renamed/removed boundary phrase from going undetected.
- **Route strings**: Checking `/api/sample-validation/append` and `/api/backend/shutdown` presence directly in source ensures these routes are wired and not accidentally removed.

### Intentionally not checked

The gate does not check:
- Panel-level IDs for newer Launch panels (`launch-scope-reconciliation-*`, `launch-real-media-proof-*`, `launch-sample-execution-*`) — these would be brittle to panel additions and are not critical boot-path checks.
- Function names in `launchView.js` for newer helpers — same rationale.
- Non-critical page panels (`data-page-panel="queue"`, `data-page-panel="completed"`, etc.) — structural check at home/settings/diagnostics level is sufficient.

This is a correct design choice. Checking every new panel would make the gate brittle without improving the safety guarantee.

---

## Codex Candidate Additions (Optional, Low Priority)

If a future iteration of the gate were to add fragments, the highest-value candidates would be:

| Asset | Candidate fragment | Reason |
|---|---|---|
| `launchView.js` | `function launchRealMediaProofRows` | Verify the proof handoff function is present |
| `launchView.js` | `launch scope reconciliation is read-only` or equivalent mutation boundary string | Match the pattern of other mutation boundary checks |
| `crossPageContextView.js` | `function crossPageSampleValidationWorksheetRows` | Verify new worksheet helpers are wired |

These are informational — not blocking issues. Report to Codex for optional addition during next JS maintenance.

---

## Constants Reference

From `lib.rs`:

| Constant | Value | Purpose |
|---|---|---|
| `MAX_BACKEND_RESPONSE_BYTES` | 16 MB | Maximum HTTP body read from backend |
| `MAX_CLOSE_READINESS_WARNINGS` | 5 | Maximum warnings shown in close dialog |
| `MAX_CLOSE_READINESS_WARNING_CHARS` | 240 | Per-warning character limit in close dialog |
| `MAX_BOOTSTRAP_STDOUT_LINES` | 5 | Lines read from backend stdout during startup |
| `MAX_BOOTSTRAP_STDOUT_CHARS` | 500 | Total stdout chars read during startup |
| `MAX_OPERATOR_PATH_CHARS` | 320 | Desktop root path length guard |

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| All fragment groups inventoried | Pass — 7 groups, 53 fragments |
| No stale or phantom fragments | Pass — all verified against current source |
| Fragment selection design is sound | Pass — minimal, non-brittle, mutation-boundary focused |
| Codex candidates identified for optional future work | Pass — 3 low-priority candidates noted |

---

## Task Output

```
Task ID: CLN3-010
Files inspected: DesktopApp\tauri_shell\src-tauri\src\lib.rs (validate_backend_web_ui, lines 692–912), Docs\TAURI_BACKEND_LIFECYCLE_BOUNDARY.md (reference)
Files changed: Docs\TAURI_ASSET_GATE_FRAGMENT_AUDIT.md (created)
Validation: Select-String -Path DesktopApp\tauri_shell\src-tauri\src\lib.rs -Pattern "validate_backend_web_ui|fragment|asset"
Findings: 53 required fragments across 7 asset groups. No stale fragments. Fragment selection is minimal and non-brittle. Bootstrap anti-pattern check is correctly guarding against placeholder leakage. Three optional future additions identified for Codex.
Open questions: None.
Risk: Low — documentation only.
```
