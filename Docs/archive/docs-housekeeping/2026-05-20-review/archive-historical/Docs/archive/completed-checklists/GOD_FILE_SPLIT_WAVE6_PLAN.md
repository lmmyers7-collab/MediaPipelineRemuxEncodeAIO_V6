# God File Split — Wave 6 Directive

> **Purpose:** Directive for Codex to execute the next round of JS view file splits.
> **Date:** 2026-05-19
> **Status:** Complete — Split 1 Queue summary/review/detail/launch children landed with priority/strategy/file-overrides command paths retained in the parent; Split 2 sample-validation nested worksheet/runbook/records children landed; Split 3 Settings raw-triage/safety-lock children landed; Split 4 Diagnostics active-jobs/log/investigation children landed.
> **Wave numbering:** Waves 1–3 = original production-code JS/Py/PS1/Rust splits (done). Wave 4 = CSS/markup partials (done). Wave 5 = test file splits (done). This is **Wave 6** — three JS view files that were not in the original god-file table but exceed the threshold based on post-split line counts.
> **Prior art:** Every split in this wave follows the same stash-global IIFE factory pattern established in Wave 3. Study `crossPageContextView.conflict.js` and its consumption block in `crossPageContextView.js` before starting. The pattern is: child defines `window.__SomeModule = { createSomeModule }`, parent reads and deletes the stash, calls the factory with injected deps, destructures returned functions.

---

## Registry reminder

**Script tags live in `index.html`** (the 97-line partial-assembly file at `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`). Page markup lives in `partials/`. All new `<script>` tags for split children go in `index.html`, immediately before the parent's existing tag.

**Inventory files to update in the same chunk as each split:**
- `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` — add new child row (Flat Exports: 1, Notes: "Split-child factory stash consumed and deleted by parent module"); update parent row flat count if it changes; update Summary counts (file count, flat total)
- `GOD_FILE_SPLIT_PLAN.md` — add execution note to §3.x and update the progress table
- `DOC_TOUCH_LOG.md` — append one row

**Gates to run after every split (use bundled Python at `DesktopApp/Runtime/Python/python.exe`):**
```
node --check <new-child>.js          # JS syntax
python.exe -m pytest tests/test_webview_inventory_docs.py tests/test_webview_navigation_static.py tests/test_webview_frontend_mutation_boundary.py -v
```
If a focused browser smoke exists for the owning page, run it too.

---

## Split 1 — `queueView.js` (3,194 lines / 152 functions) — PRIORITY 1

This is the highest-value split. Four children landed with the same stash-factory pattern. The detail child was narrowed to read-only selected-row detail, diagnostics-link rendering, excluded-row detail, and queue-open history. The parent retains all mutation paths.

### §1.1 `queueView.summary.js`

**Stash:** `window.__queueSummaryModule = { createQueueSummaryModule }`

**Injection parameters (parent passes these in):**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable,
  updateTableStatusLegend, crossPageCount }
```
*(Add any additional shared DOM helpers the extracted functions actually call — verify by inspection.)*

**Function cluster to move (all have prefix `queue` or `renderQueue` and live between lines 73–299):**
```
queuePathExtension, queueRowExtension, queueIsHiddenSidecarBlockedRow,
queueIncrementCount, queueCountRowsBy, queueCountRowsByExtension,
queueIsMovieRow, queueIsTvRow, queueBlockedRows, queueVisibleRunnableCount,
queueDisplayPayloadForVisibleRows, queueDisplayProgressForVisibleRows,
queueHiddenSidecarLine, queueEmptyStateMessage,
queueProgressPayload, queueProgressBars, queueProgressStatus,
queueProgressSummaryLines, renderQueueProgress,
queueFreshnessLine, queueSnapshotIsStale,
renderQueueSummary, queueCounts,
queueReadinessStatus, queueReadinessLines, renderQueueReadiness,
queueWorkflowStatus, queueWorkflowLines, renderQueueWorkflow
```

**Factory return:** all of the above.

**`index.html` insertion:** add immediately before `<script src="/assets/queueView.js"></script>` (line 52):
```html
<script src="/assets/queueView.summary.js"></script>
```

---

### §1.2 `queueView.launch.js`

**Stash:** `window.__queueLaunchModule = { createQueueLaunchModule }`

**Injection parameters:**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable,
  updateTableStatusLegend, getLastQueuePayload, getLastQueueRows }
```
*(Verify — some functions default to `lastQueuePayload` / `lastQueueRows`. These state variables must be injected, not accessed via `window.*`.)*

**Function cluster (lines ~490–1155):**
```
queueLaunchDecisionPostureStatus, isQueueLaunchCommand,
queueLaunchDecisionLatestCommand, queueLaunchCommandIssueLevel,
queueLaunchDecisionAdd, queueLaunchBackendPreflightPayload,
queueLaunchBackendPreflightRows, queueLaunchBackendPreflightCheckpoint,
queueLaunchDecisionSelectedRowSummary,
queueCurrentFilterScope, queueFilterScopePosture, queueFilterScopeEvidence,
queueFilterScopeAction, queueFilterScopeDetailLines,
queueBackendLaunchScopeRows, queueBackendLaunchScopeStatus,
queueBackendLaunchScopeSummaryLines, renderQueueBackendLaunchScopePreview,
queueLaunchDecisionRows, queueLaunchDecisionStatus,
queueLaunchDecisionStatusState, queueLaunchDecisionSummaryLines,
queueLaunchDecisionDetailLines, selectedQueueLaunchDecisionRow,
selectQueueLaunchDecisionRow, renderQueueLaunchDecisionChecklist
```

**Factory return:** all of the above.

**`index.html` insertion:** add before `queueView.js` (after `queueView.review.js` in the implemented load order):
```html
<script src="/assets/queueView.launch.js"></script>
```

---

### §1.3 `queueView.review.js`

**Stash:** `window.__queueReviewModule = { createQueueReviewModule }`

**Injection parameters:**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable,
  updateTableStatusLegend, getLastQueuePayload, getLastQueueRows }
```

**Function cluster (lines ~1155–1520):**
```
queueReviewRowReasons, queueReviewRows, queueReviewStatus, queueReviewBoardLines,
queueReviewDigestStatus, queueReviewDigestAction, queueTableRowStatus,
queueInvestigationFilterLabel, queueMatchesInvestigationFilter,
queueFocusedInvestigationLabels, queueFilterVisibilityLines,
queueSelectedQuickSignalLines, queueSelectedAtAGlanceState,
queueSelectedAtAGlanceStatus, queueSelectedVisibilitySummary,
queueSelectedAtAGlanceLines, renderQueueSelectedAtAGlance,
queueInvestigationSignalLines, renderQueueReviewDigest, renderQueueReviewBoard,
queueFormatCounts, queueListText
```

**Factory return:** all of the above.

**`index.html` insertion:** add before `queueView.js` (after `queueView.summary.js` and before `queueView.launch.js` in the implemented load order):
```html
<script src="/assets/queueView.review.js"></script>
```

---

### §1.4 `queueView.detail.js`

**Stash:** `window.__queueDetailModule = { createQueueDetailModule }`

**Injection parameters:**
```js
{ byId, setText, queueListText, queueRowKey,
  queueSelectedQuickSignalLines, queueInvestigationSignalLines,
  queueSelectedOpenTargetLines, renderQueueSelectedAtAGlance,
  requestQueueDiagnosticsAction,
  appendDiagnosticsBridgeGroupedButtons, appendDiagnosticsBridgeButton,
  diagnosticsBridgeHandoffLines, diagnosticsBridgeRowTrustLines,
  commandHistoryCompactEvidenceLine }
```
`requestQueueDiagnosticsAction` stays in the parent because it dispatches Diagnostics open/tail commands. The child receives it only as an injected callback for button wiring.

**Function cluster — row detail and diagnostics (lines ~1831–2200):**
```
queueRowReviewChecklistLines, queueRowIssueDigestLines,
queueRowCombinedReviewPlanLines, queueRealMediaTraceLines,
queueRowTrustSummaryLines, queueDiagnosticsActionsForRow,
queueAddDiagnosticsAction, queueDiagnosticsGuidanceLines,
queueDiagnosticsActionStatusText, renderQueueDiagnosticsLinks,
queueRouteReasoningLines, renderQueueDetail, renderQueueExcludedDetail
```

**Function cluster — open history (lines ~2503–2740):**
```
isQueueOpenCommand, queueOpenHistoryLine, renderQueueOpenHistory
```

**Command-adjacent cluster retained in `queueView.js` — priority toolbar (lines ~2740–2961):**
```
queuePriorityBadgeLabel, initQueuePriorityToolbar, initQueueStrategySelector
```

**Command-adjacent cluster retained in `queueView.js` — file-settings drawer (lines ~2961–3195):**
```
parseLangList, langCodesToRules, rulesToLangInput,
openFileSettingsDrawer, closeFileSettingsDrawer, clearDrawerForm,
syncSubFilterFields, populateDrawerForm, buildOverridePayload,
initFileSettingsDrawer
```
The priority/strategy/file-overrides functions continue to own the `/api/queue/priority`, `/api/queue/strategy`, and `/api/queue/file-overrides` POST paths in the parent.

**Factory return:** all of the above.

**`index.html` insertion:** added before `queueView.launch.js` and `queueView.js` (after `queueView.review.js`):
```html
<script src="/assets/queueView.detail.js"></script>
```

**Execution note — 2026-05-19:** `queueView.detail.js` landed as a read-only stash-global child consumed and deleted by `queueView.js`. The child owns selected-row review/checklist/detail text, diagnostics-link rendering, excluded-row detail, and queue-open history rendering. The parent keeps Queue open, Diagnostics open/tail dispatch, priority, strategy, file-overrides, state variables, selection, row rendering, event wiring, and all POST routes.

---

### §1.5 What stays in `queueView.js` (red line — do not move)

```
lastQueuePayload, lastQueueRows, selectedQueueRowKey, selectedQueueExcludedRowKey
(all module-scope state variables)
renderQueue                  (main render orchestrator — calls children via injected fns)
renderQueueRows              (main table renderer — DOM mutation)
makeRouteChip                (chip builder used inline by renderQueueRows)
resetQueueFilters            (mutates DOM filter state)
setQueueOpenBusy             (busy-state flag mutation)
rejectQueueOpenWhileBusy     (guard check)
getLastQueuePayload          (state accessor — injected into children)
getLastQueueRows             (state accessor — injected into children)
queueExcludedRowKey          (key helper used in selectQueueExcludedRow)
selectQueueRow               (navigation/selection — injected into children)
selectQueueExcludedRow       (navigation/selection)
initQueueViewEvents          (event wiring — owns DOM listeners)
window.mediaPipelineQueueView namespace object and all flat exports
stash consumption blocks for all four children (conflict → summary → launch → review → detail)
```

---

## Split 2 — `crossPageContextView.sampleValidation.js` (2,673 lines / 128 functions) — PRIORITY 2

This file is itself a stash-global factory (`createCrossPageSampleValidationModule`). All 128 functions are nested inside that factory. The split strategy: extract the three largest internal clusters into their own stash-global factory files, which the `sampleValidation.js` factory consumes before exporting its own stash. The chain:

```
sampleValidation.worksheet.js   → defines window.__crossPageSvWorksheetModule
sampleValidation.runbook.js     → defines window.__crossPageSvRunbookModule
sampleValidation.records.js     → defines window.__crossPageSvRecordsModule
crossPageContextView.sampleValidation.js → consumes those three stashes, exports window.__crossPageSampleValidationModule
crossPageContextView.js         → consumes window.__crossPageSampleValidationModule (unchanged)
```

### §2.1 `crossPageContextView.sampleValidation.worksheet.js`

**Stash:** `window.__crossPageSvWorksheetModule = { createCrossPageSvWorksheetModule }`

**Injection parameters:** Pass whatever shared helpers the worksheet cluster uses from the parent factory's `deps` parameter (e.g., path accessors, `crossPageRows`, `crossPageLeaf`, `crossPageNormalizePath`). Identify by inspection.

**Function cluster:** all functions whose names contain `Worksheet`, `worksheet`, `PolicyAlignment`, `policyAlignment`, `SampleSetGuide`, `sampleSetGuide`, `SampleCategory`, `sampleCategory`. These are the worksheet parsing, policy alignment matching, and sample-set category helpers.

**Factory return:** all extracted functions.

---

### §2.2 `crossPageContextView.sampleValidation.runbook.js`

**Stash:** `window.__crossPageSvRunbookModule = { createCrossPageSvRunbookModule }`

**Function cluster:** all functions whose names contain `Runbook`, `runbook`, `CutoverGate`, `cutoverGate`, `Cutover`, `cutover`, `PilotPlan`, `pilotPlan`, `Pilot`, `pilot` (the cutover gate and runbook guidance helpers).

**Factory return:** all extracted functions.

---

### §2.3 `crossPageContextView.sampleValidation.records.js`

**Stash:** `window.__crossPageSvRecordsModule = { createCrossPageSvRecordsModule }`

**Function cluster:** all functions whose names contain `Record`, `record`, `Preview`, `preview`, `Append`, `append`, `AcceptanceGate`, `acceptanceGate`, `CompletedPacket`, `completedPacket` (the record review, preview, and append helpers).

**Factory return:** all extracted functions.

---

### §2.4 `crossPageContextView.sampleValidation.js` — consume and pass through

Inside `createCrossPageSampleValidationModule`, add consumption blocks at the top of the factory body (before any cluster that uses them):

```js
const __worksheetMod = window.__crossPageSvWorksheetModule || {};
delete window.__crossPageSvWorksheetModule;
const _worksheet = typeof __worksheetMod.createCrossPageSvWorksheetModule === "function"
  ? __worksheetMod.createCrossPageSvWorksheetModule({ /* inject deps */ })
  : {};
const { crossPageSvWorksheetFn1 = noop, ... } = _worksheet;

// repeat for runbook, records
```

Remove the extracted function bodies from this file. The factory return shape must be identical to pre-split (no call-site changes in `crossPageContextView.js`).

**`index.html` insertion:** add before `crossPageContextView.sampleValidation.js` (line 61):
```html
<script src="/assets/crossPageContextView.sampleValidation.worksheet.js"></script>
<script src="/assets/crossPageContextView.sampleValidation.runbook.js"></script>
<script src="/assets/crossPageContextView.sampleValidation.records.js"></script>
```

**Execution note — 2026-05-19:** `crossPageContextView.sampleValidation.worksheet.js`, `crossPageContextView.sampleValidation.runbook.js`, and `crossPageContextView.sampleValidation.records.js` landed as nested stash-global children consumed and deleted by `crossPageContextView.sampleValidation.js`. The parent now keeps the Sample Validation preview/append POST routes, request/result handling, record panel orchestration, and final `window.__crossPageSampleValidationModule` export while the three children own read-only worksheet/policy/sample-set, runbook/cutover/pilot, and completed-record/acceptance evidence helpers. No API route, backend sample-validation policy, queue/launch/publish behavior, DOM ID, or media/source-file mutation behavior changed.

---

## Split 3 — `settingsView.js` (3,873 lines / 203 functions) — PRIORITY 3

Two clearly isolated read-only clusters at the top of the file (lines ~14–488). The 3,000-line middle section (field-state management, builder orchestration, event wiring) is too coupled to split further — leave it alone.

### §3.1 `settingsView.rawTriage.js`

**Stash:** `window.__settingsRawTriageModule = { createSettingsRawTriageModule }`

**Injection parameters:**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend }
```

**Function cluster (lines ~14–425):**
```
setSettingsRows, renderSettingsRows,
settingsKnownFieldKeys, settingsRawKeyImpact, settingsRawKeyReviewNote,
settingsRawTriageRows, settingsRawTriageStatus, settingsRawTriageSummaryLines,
boundedSettingsValueText, selectedSettingsRawTriageRow, settingsRawTriageDetailLines,
renderSettingsRawTriage,
settingsRawActionPlanStatus, settingsRawActionPlanRows,
settingsRawActionPlanSummaryLines, selectedSettingsRawActionPlanRow,
settingsRawActionPlanDetailLines, renderSettingsRawActionPlan
```

**Factory return:** all of the above.

**`index.html` insertion:** add before `<script src="/assets/settingsView.js"></script>` (line 77):
```html
<script src="/assets/settingsView.rawTriage.js"></script>
```

---

### §3.2 `settingsView.safetyLocks.js`

**Stash:** `window.__settingsSafetyLocksModule = { createSettingsSafetyLocksModule }`

**Injection parameters:**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend }
```

**Function cluster (lines ~426–488):**
```
settingsValueIsNonEmpty, settingsSafetyLockRisk, settingsSafetyLockRows,
settingsSafetyLockStatus, settingsSafetyLockSummaryLines, renderSettingsSafetyLocks
```

**Factory return:** all of the above.

**`index.html` insertion:** add before `settingsView.js` (after `settingsView.rawTriage.js`):
```html
<script src="/assets/settingsView.safetyLocks.js"></script>
```

**Execution note — 2026-05-19:** `settingsView.rawTriage.js` and `settingsView.safetyLocks.js` landed as read-only stash-global children consumed and deleted by `settingsView.js`. The parent keeps Settings state, builder orchestration, event wiring, Preview/Save/Reload/Validate command routes, command busy guards, and the canonical `window.mediaPipelineSettingsView` namespace/flat exports. The raw-triage child owns settings-row filtering, raw-key triage, and raw action-plan evidence. The safety-lock child owns saved safety-lock review evidence. No API route, settings persistence behavior, backend validation, media policy, DOM ID, or media/source-file mutation behavior changed.

---

### §3.3 What stays in `settingsView.js` (do not move)

Everything from line ~488 onward: field-state variables, builder orchestration, `initSettingsViewEvents`, `getLastSettings`, save/preview command flow, and stash consumption blocks for all builder children. The `setSettingsRows`/`renderSettingsRows` functions stay in the rawTriage child (they are settings-specific row display helpers, not global utilities).

---

## Split 4 — `diagnosticsView.js` (2,325 lines / 110 functions) — PRIORITY 4

Three children. All read-only — `setDiagnosticsOpenBusy`, `rejectDiagnosticsOpenWhileBusy`, and `initDiagnosticsViewEvents` stay in the parent.

### §4.1 `diagnosticsView.activejobs.js`

**Stash:** `window.__diagnosticsActiveJobsModule = { createDiagnosticsActiveJobsModule }`

**Injection parameters:**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend,
  boundedDiagnosticsText, diagnosticsActionGroups, diagnosticsActionPlanLines,
  appendDiagnosticsActionGroup }
```
*(The text/action helpers at lines 44–152 stay in the parent and are injected here.)*

**Function cluster (lines ~152–329):**
```
activeJobRowKey, getSelectedActiveJobRow, selectActiveJobRow,
activeJobDiagnosticsActions, activeJobRowPosture, activeJobRowsStatusText,
renderActiveJobDiagnosticsActions, diagnosticsActiveJobRealMediaTraceLines,
renderActiveJobDetail, renderActiveJobRows
```

**Factory return:** all of the above.

**`index.html` insertion:** add before `<script src="/assets/diagnosticsView.js"></script>` (line 81):
```html
<script src="/assets/diagnosticsView.activejobs.js"></script>
```

---

### §4.2 `diagnosticsView.log.js`

**Stash:** `window.__diagnosticsLogModule = { createDiagnosticsLogModule }`

**Injection parameters:**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend,
  diagnosticsTextLines, diagnosticsSeverityForLine, diagnosticsActionPlanLines,
  appendDiagnosticsActionGroup, diagnosticsArtifactsForLine, diagnosticsSourceLines,
  readLastDiagnosticsLogRows, writeLastDiagnosticsLogRows }
```

**Function cluster (lines ~329–611):**
```
diagnosticsLineTimestamp, diagnosticsLogRows, diagnosticsLogRowKey,
diagnosticsLogFilterText, diagnosticsLogSeverityFilter, diagnosticsLogSearchText,
diagnosticsArtifactsForLine, diagnosticsLogRowActions, diagnosticsLogRowNextStep,
diagnosticsLogRealMediaTraceLines, filteredDiagnosticsLogRows,
getSelectedDiagnosticsLogRow, selectDiagnosticsLogRow, renderDiagnosticsLogDetail,
diagnosticsLogGuidanceLines, renderDiagnosticsLogGuidance, renderDiagnosticsLogActions,
renderDiagnosticsLogTable, renderDiagnosticsLogRows, getLastDiagnosticsLogRows
```

**Note:** `diagnosticsArtifactsForLine` appears both in this cluster and as a dependency. If it is used by both the log board and the drilldown (lines ~693+), keep it in the parent and inject it into both children.

**Factory return:** all of the above (minus any moved back to parent — verify).

**`index.html` insertion:** add before `diagnosticsView.js` (after `diagnosticsView.activejobs.js`):
```html
<script src="/assets/diagnosticsView.log.js"></script>
```

---

### §4.3 `diagnosticsView.investigation.js`

**Stash:** `window.__diagnosticsInvestigationModule = { createDiagnosticsInvestigationModule }`

**Injection parameters:**
```js
{ byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend,
  diagnosticsTextLines, diagnosticsMalformedStateLines, diagnosticsActionGroups,
  diagnosticsOrderedActions, diagnosticsSafeRows, diagnosticsSamplePolicyReconciliation,
  appendDiagnosticsActionGroup }
```

**Function cluster — investigation engine (lines ~848–960):**
```
diagnosticsStateIssueRows, diagnosticsPageReviewRows,
diagnosticsCrossPageConflictRows, diagnosticsConflictSignalLabel,
diagnosticsCommandIssueRows, diagnosticsInvestigationAddAction,
diagnosticsInvestigationActions, diagnosticsInvestigationStatus
```

**Function cluster — owner handoff board (lines ~1747–2114):**
```
diagnosticsOwnerHandoffStatus, diagnosticsOwnerHandoffSummaryLines,
diagnosticsHandoffTailTargets, diagnosticsOwnerHandoffActions,
diagnosticsOwnerPageId, diagnosticsOwnerSelectFunction,
diagnosticsOwnerNavigationLabel, setDiagnosticsOwnerHandoffNavStatus,
navigateDiagnosticsOwnerHandoffRow, getSelectedDiagnosticsOwnerHandoffRow,
selectDiagnosticsOwnerHandoffRow, renderDiagnosticsOwnerHandoffActions,
diagnosticsSampleValidationComparisonLines, renderDiagnosticsOwnerHandoffDetail,
renderDiagnosticsOwnerHandoffTable, renderDiagnosticsOwnerHandoff,
isDiagnosticsOpenCommand, diagnosticsOpenHistoryLine, renderDiagnosticsOpenHistory
```

**Factory return:** all of the above.

**`index.html` insertion:** add before `diagnosticsView.js` (after `diagnosticsView.log.js`):
```html
<script src="/assets/diagnosticsView.investigation.js"></script>
```

---

### §4.4 What stays in `diagnosticsView.js` (do not move)

```
lastDiagnosticsLogRows (state variable)
setDiagnosticsOpenStatus, setDiagnosticsOpenBusy, rejectDiagnosticsOpenWhileBusy
diagnosticsTextLines, diagnosticsSeverityForLine, diagnosticsMalformedStateLines,
boundedDiagnosticsText, diagnosticsRealMediaBoundaryLines
diagnosticsActionLabel, diagnosticsOrderedActions, diagnosticsActionGroups,
diagnosticsActionGroupText, diagnosticsActionPlanLines, appendDiagnosticsActionGroup
  (all shared text/action helpers — injected into all three children)
diagnosticsSourceLines          (read by window.mediaPipelineDiagnosticsView at call time
                                 from crossPageContextView.sample.js — must stay on the
                                 namespace object)
diagnosticsArtifactMatches      (used by drilldown — keep in parent unless also needed
                                 by log child, in which case inject into log child)
renderDiagnosticsDrilldownActions, renderDiagnosticsDrilldown, renderDiagnosticsTriage
diagnosticsFormatCounts, diagnosticsSafeRows
initDiagnosticsViewEvents       (event wiring — must stay)
renderDiagnostics               (main orchestrator — must stay)
window.mediaPipelineDiagnosticsView namespace object and all flat exports
stash consumption blocks for all three children
```

**Execution note — 2026-05-19:** `diagnosticsView.activejobs.js`, `diagnosticsView.log.js`, and `diagnosticsView.investigation.js` landed as read-only stash-global children consumed and deleted by `diagnosticsView.js`. The parent keeps Diagnostics open/tail command busy guards, shared text/action helpers, artifact drilldown, source-line helpers, event wiring, the render orchestrator, and the canonical `window.mediaPipelineDiagnosticsView` namespace/flat exports. The active-jobs child owns structured ActiveJobs row selection/detail/action evidence. The log child owns log row parsing/filtering/detail/action guidance. The investigation child owns cross-page/page-review issue rows, owning-page handoff, completed final-trust/policy handoffs, and diagnostics open-history rendering. No API route, diagnostics target allowlist, backend state/readiness authority, DOM ID, media policy, queue/drain/publish decision, or media/source-file mutation behavior changed.

---

## Execution order summary

| Step | File to create | Parent to update | Index.html change |
|---|---|---|---|
| 1 | `queueView.summary.js` | `queueView.js` | before `queueView.js` |
| 2 | `queueView.review.js` | `queueView.js` | before `queueView.js` |
| 3 | `queueView.launch.js` | `queueView.js` | before `queueView.js` |
| 4 | `queueView.detail.js` | `queueView.js` | before `queueView.launch.js` and `queueView.js` |
| 5 | `crossPageContextView.sampleValidation.worksheet.js` | `crossPageContextView.sampleValidation.js` | before `sampleValidation.js` |
| 6 | `crossPageContextView.sampleValidation.runbook.js` | `crossPageContextView.sampleValidation.js` | before `sampleValidation.js` |
| 7 | `crossPageContextView.sampleValidation.records.js` | `crossPageContextView.sampleValidation.js` | before `sampleValidation.js` |
| 8 | `settingsView.rawTriage.js` | `settingsView.js` | before `settingsView.js` |
| 9 | `settingsView.safetyLocks.js` | `settingsView.js` | before `settingsView.js` |
| 10 | `diagnosticsView.activejobs.js` | `diagnosticsView.js` | before `diagnosticsView.js` |
| 11 | `diagnosticsView.log.js` | `diagnosticsView.js` | before `diagnosticsView.js` |
| 12 | `diagnosticsView.investigation.js` | `diagnosticsView.js` | before `diagnosticsView.js` |

**Wave 6 split status:** `queueView.summary.js`, `queueView.review.js`, `queueView.detail.js`, and `queueView.launch.js` landed; `crossPageContextView.sampleValidation.worksheet.js`, `.runbook.js`, and `.records.js` landed; `settingsView.rawTriage.js` and `settingsView.safetyLocks.js` landed; `diagnosticsView.activejobs.js`, `.log.js`, and `.investigation.js` landed. Queue priority, strategy, file-overrides, queue open, and Diagnostics open/tail dispatch intentionally remain in `queueView.js`.

---

## Constraints and red lines

1. **No behaviour changes.** Splits are pure refactors. Any bug found during a split must be noted but not fixed in the same chunk.
2. **Namespace export shape is frozen.** `window.mediaPipelineQueueView`, `window.mediaPipelineDiagnosticsView`, and `window.mediaPipelineSettingsView` must export the same functions as before each split. No function may be added to or removed from the namespace objects.
3. **State variables never move.** `lastQueuePayload`, `lastQueueRows`, `lastDiagnosticsLogRows`, and all `selected*` variables stay in the parent IIFE. Children receive current values through injection parameters, not by reading `window.*` globals directly.
4. **`diagnosticsSourceLines` must remain on `window.mediaPipelineDiagnosticsView`.** It is read at call time by `crossPageContextView.sample.js` via `window.mediaPipelineDiagnosticsView.diagnosticsSourceLines`. Do not move it out of the namespace export.
5. **Each split gets its own chunk** (separate Codex session or commit). Do not combine two parent files in one chunk.
6. **Run the gate suite after every chunk.** A chunk is not complete until `test_webview_inventory_docs.py` passes.
