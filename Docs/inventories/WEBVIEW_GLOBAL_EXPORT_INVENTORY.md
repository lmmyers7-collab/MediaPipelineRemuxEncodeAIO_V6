# WebView Global Export Inventory

Date: 2026-06-23

Inventories all `window.*` assignments in `apps/desktop/webview/static/assets/*.js`. Source: generated scan of `window.{name} =` assignments across all 74 JS files.

---

## Summary

- **74 JS files** total in `assets/`
- **34 files** export a primary namespace object (`window.mediaPipeline* = { ... }`)
- **48 files** also export flat functions directly onto `window`
- **40 files** have no primary namespace object: `app.js`, `completedView.diagnostics.js`, `completedView.evidence.js`, `completedView.proof.js`, `completedView.repair.js`, `completedView.review.js`, `crossPageContextView.conflict.js`, `crossPageContextView.sample.js`, `crossPageContextView.sampleValidation.js`, `crossPageContextView.sampleValidation.records.js`, `crossPageContextView.sampleValidation.runbook.js`, `crossPageContextView.sampleValidation.worksheet.js`, `crossPageContextView.settings.js`, `diagnosticsView.activejobs.js`, `diagnosticsView.investigation.js`, `diagnosticsView.log.js`, `launchView.preflight.js`, `launchView.realmedia.js`, `launchView.risk.js`, `launchView.scope.js`, `pendingPublishView.confidence.js`, `pendingPublishView.diagnostics.js`, `pendingPublishView.drain.js`, `pendingPublishView.recovery.js`, `pendingPublishView.repair.js`, `queueView.detail.js`, `queueView.launch.js`, `queueView.review.js`, `queueView.summary.js`, `settingsView.builders.audio.js`, `settingsView.builders.file_safety.js`, `settingsView.builders.network.js`, `settingsView.builders.pending.js`, `settingsView.builders.quality.js`, `settingsView.builders.queue.js`, `settingsView.builders.runtime.js`, `settingsView.builders.subtitle.js`, `settingsView.builders.video.js`, `settingsView.rawTriage.js`, `settingsView.safetyLocks.js`
- **Flat export total:** 435
- **1 backend-injected bootstrap global** (`window.MEDIA_PIPELINE_BOOTSTRAP`) is read by `apiClient.js`
- **All 32 object-literal namespace objects** have adjacent `Public namespace` JSDoc boundary comments. `test_webview_inventory_docs.py` fails if a future `window.mediaPipeline* = { ... }` namespace object is added without that boundary note. (`tauriLifecycleBridge.js` exports its `mediaPipelineTauriLifecycleBridge` namespace via `Object.freeze(...)`, which is outside that JSDoc check.)

---

## Module Inventory
| File | Namespace Object | Flat Exports | Notes |
|---|---|---:|---|
| `apiClient.js` | mediaPipelineApi | 4 | Generated from current `window.* =` assignments |
| `app.js` | - | 10 | Generated from current `window.* =` assignments |
| `commandHistory.js` | mediaPipelineCommandHistory | 3 | Generated from current `window.* =` assignments |
| `completedView.diagnostics.js` | - | 1 | Generated from current `window.* =` assignments |
| `completedView.evidence.js` | - | 1 | Generated from current `window.* =` assignments |
| `completedView.js` | mediaPipelineCompletedView | 0 | Generated from current `window.* =` assignments |
| `completedView.proof.js` | - | 1 | Generated from current `window.* =` assignments |
| `completedView.repair.js` | - | 1 | Generated from current `window.* =` assignments |
| `completedView.review.js` | - | 1 | Generated from current `window.* =` assignments |
| `contractView.js` | mediaPipelineContractView | 0 | Generated from current `window.* =` assignments |
| `crossPageContextView.conflict.js` | - | 1 | Generated from current `window.* =` assignments |
| `crossPageContextView.js` | mediaPipelineLastCrossPageContext, mediaPipelineCrossPageContextView | 64 | Generated from current `window.* =` assignments |
| `crossPageContextView.sample.js` | - | 1 | Generated from current `window.* =` assignments |
| `crossPageContextView.sampleValidation.js` | - | 1 | Generated from current `window.* =` assignments |
| `crossPageContextView.sampleValidation.records.js` | - | 1 | Generated from current `window.* =` assignments |
| `crossPageContextView.sampleValidation.runbook.js` | - | 1 | Generated from current `window.* =` assignments |
| `crossPageContextView.sampleValidation.worksheet.js` | - | 1 | Generated from current `window.* =` assignments |
| `crossPageContextView.settings.js` | - | 1 | Generated from current `window.* =` assignments |
| `diagnosticsBridge.js` | mediaPipelineDiagnosticsBridge | 0 | Generated from current `window.* =` assignments |
| `diagnosticsStateSummaryView.js` | mediaPipelineDiagnosticsStateSummaryView | 0 | Generated from current `window.* =` assignments |
| `diagnosticsTailView.js` | mediaPipelineDiagnosticsTailView | 0 | Generated from current `window.* =` assignments |
| `diagnosticsView.activejobs.js` | - | 1 | Generated from current `window.* =` assignments |
| `diagnosticsView.investigation.js` | - | 1 | Generated from current `window.* =` assignments |
| `diagnosticsView.js` | mediaPipelineDiagnosticsView | 60 | Generated from current `window.* =` assignments |
| `diagnosticsView.log.js` | - | 1 | Generated from current `window.* =` assignments |
| `domHelpers.js` | mediaPipelineDom | 22 | Generated from current `window.* =` assignments |
| `formatters.js` | mediaPipelineFormatters | 0 | Generated from current `window.* =` assignments |
| `launchHistoryView.js` | mediaPipelineLaunchHistoryView | 0 | Generated from current `window.* =` assignments |
| `launchReadinessView.js` | mediaPipelineLaunchReadinessView | 0 | Generated from current `window.* =` assignments |
| `launchView.js` | mediaPipelineLaunchView | 0 | Generated from current `window.* =` assignments |
| `launchView.preflight.js` | - | 1 | Generated from current `window.* =` assignments |
| `launchView.realmedia.js` | - | 1 | Generated from current `window.* =` assignments |
| `launchView.risk.js` | - | 1 | Generated from current `window.* =` assignments |
| `launchView.scope.js` | - | 1 | Generated from current `window.* =` assignments |
| `librariesRouteMap.js` | mediaPipelineLibraryRouteMap | 0 | Generated from current `window.* =` assignments |
| `maintenanceView.js` | mediaPipelineMaintenanceView | 0 | Generated from current `window.* =` assignments |
| `metricsView.js` | mediaPipelineMetricsView | 0 | Generated from current `window.* =` assignments |
| `networkView.js` | mediaPipelineNetworkView | 0 | Generated from current `window.* =` assignments |
| `pendingPublishView.confidence.js` | - | 1 | Generated from current `window.* =` assignments |
| `pendingPublishView.diagnostics.js` | - | 1 | Generated from current `window.* =` assignments |
| `pendingPublishView.drain.js` | - | 1 | Generated from current `window.* =` assignments |
| `pendingPublishView.js` | mediaPipelinePendingPublishView | 92 | Generated from current `window.* =` assignments |
| `pendingPublishView.recovery.js` | - | 1 | Generated from current `window.* =` assignments |
| `pendingPublishView.repair.js` | - | 1 | Generated from current `window.* =` assignments |
| `progressView.js` | mediaPipelineProgressView | 0 | Generated from current `window.* =` assignments |
| `queueView.detail.js` | - | 1 | Generated from current `window.* =` assignments |
| `queueView.js` | mediaPipelineQueueView | 84 | Generated from current `window.* =` assignments |
| `queueView.launch.js` | - | 1 | Generated from current `window.* =` assignments |
| `queueView.review.js` | - | 1 | Generated from current `window.* =` assignments |
| `queueView.summary.js` | - | 1 | Generated from current `window.* =` assignments |
| `renameHistoryView.js` | mediaPipelineRenameHistoryView | 0 | Generated from current `window.* =` assignments |
| `renameLabels.js` | mediaPipelineRenameLabels | 0 | Generated from current `window.* =` assignments |
| `renameView.js` | mediaPipelineRenameView | 0 | Generated from current `window.* =` assignments |
| `reportsView.js` | mediaPipelineReportsView | 0 | Generated from current `window.* =` assignments |
| `scheduleView.js` | mediaPipelineScheduleView | 0 | Generated from current `window.* =` assignments |
| `settingsCommandHistory.js` | mediaPipelineSettingsCommandHistory | 0 | Generated from current `window.* =` assignments |
| `settingsLibraries.js` | mediaPipelineSettingsLibraries | 0 | Generated from current `window.* =` assignments |
| `settingsMetadata.js` | mediaPipelineSettingsMetadata | 0 | Generated from current `window.* =` assignments |
| `settingsOverview.js` | mediaPipelineSettingsOverview | 0 | Generated from current `window.* =` assignments |
| `settingsView.builders.audio.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.file_safety.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.network.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.pending.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.quality.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.queue.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.runtime.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.subtitle.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.builders.video.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.js` | mediaPipelineSettingsView | 57 | Generated from current `window.* =` assignments |
| `settingsView.rawTriage.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsView.safetyLocks.js` | - | 1 | Generated from current `window.* =` assignments |
| `settingsWizard.js` | mediaPipelineSettingsWizard | 0 | Generated from current `window.* =` assignments |
| `tauriLifecycleBridge.js` | mediaPipelineTauriLifecycleBridge | 0 | Generated from current `window.* =` assignments |
| `telemetryView.js` | mediaPipelineTelemetryView | 0 | Generated from current `window.* =` assignments |

---

## Backend-Injected Globals

| Global | Set by | Purpose |
|---|---|---|
| `window.MEDIA_PIPELINE_BOOTSTRAP` | Backend (HTML template injection) | Startup config object; `apiClient.js` reads it at module load time for API base URL and auth token |

This is the only global not set by a JS module file. It is read-only from the frontend's perspective.

---

## Cross-Module Consumption Pattern

Several modules call other modules' flat exports via `typeof window.X === "function"` guards, and newer consumers prefer `window.mediaPipeline*` namespace helpers. This is the designed inter-module communication pattern (no module bundler; load-order safety via guards).

| Consumer | Reads From |
|---|---|
| `crossPageContextView.js` | `queueView.js` (`getSelectedQueueRow`, `selectQueueRow`), `completedView.js` (`mediaPipelineCompletedView.getSelectedCompletedRow`, `selectCompletedRow`), `pendingPublishView.js` (`getSelectedPendingRow`, `selectPendingRow`), `settingsView.js` (`getLastSettings`), `app.js` (`showPage`) |
| `crossPageContextView.sampleValidation.js` | `crossPageContextView.sampleValidation.worksheet.js` (`__crossPageSvWorksheetModule` nested split-child factory stash, consumed and deleted during load), `crossPageContextView.sampleValidation.runbook.js` (`__crossPageSvRunbookModule` nested split-child factory stash, consumed and deleted during load), `crossPageContextView.sampleValidation.records.js` (`__crossPageSvRecordsModule` nested split-child factory stash, consumed and deleted during load) |
| `queueView.js` | `queueView.summary.js` (`__queueSummaryModule` split-child factory stash, consumed and deleted during load), `queueView.review.js` (`__queueReviewModule` split-child factory stash, consumed and deleted during load), `queueView.detail.js` (`__queueDetailModule` split-child factory stash, consumed and deleted during load), `queueView.launch.js` (`__queueLaunchModule` split-child factory stash, consumed and deleted during load) |
| `diagnosticsView.js` | `diagnosticsView.activejobs.js` (`__diagnosticsActiveJobsModule` split-child factory stash, consumed and deleted during load), `diagnosticsView.log.js` (`__diagnosticsLogModule` split-child factory stash, consumed and deleted during load), `diagnosticsView.investigation.js` (`__diagnosticsInvestigationModule` split-child factory stash, consumed and deleted during load), `diagnosticsBridge.js` (`mediaPipelineDiagnosticsBridge` namespace helpers), `diagnosticsTailView.js` (`mediaPipelineDiagnosticsTailView` tail functions), `queueView.js` (`queueReviewRows`), `completedView.js` (`mediaPipelineCompletedView.completedReviewRows`, `mediaPipelineCompletedView.selectCompletedFinalTrustStep`), `pendingPublishView.js` (`pendingReviewRows`), `crossPageContextView.js` (`crossPageConflictRows`), `commandHistory.js` (`mediaPipelineCommandHistory.commandHistoryIssueEntries`, `mediaPipelineCommandHistory.commandHistoryOwnerPage`, `mediaPipelineCommandHistory.commandHistorySuggestedAction`), `diagnosticsStateSummaryView.js` (`mediaPipelineDiagnosticsStateSummaryView.diagnosticsStateOperatorStatus`, `mediaPipelineDiagnosticsStateSummaryView.diagnosticsStateRecommendedFirstAction`) |
| `diagnosticsStateSummaryView.js` | `diagnosticsBridge.js` (`mediaPipelineDiagnosticsBridge` namespace helpers), `diagnosticsView.js` compatibility globals (`requestDiagnosticsTail`, `requestDiagnosticsOpen`) after full script load |
| `settingsView.js` | `settingsView.rawTriage.js` (`__settingsRawTriageModule` split-child factory stash, consumed and deleted during load), `settingsView.safetyLocks.js` (`__settingsSafetyLocksModule` split-child factory stash, consumed and deleted during load), and builder child stashes already listed in the module inventory |
| `app.js` | Page and shared modules (reads their flat exports to wire DOM events and orchestrate refresh) |

---

## Namespace Object Naming Convention

All 35 namespace objects follow the `window.mediaPipeline{ModuleRole}` pattern:
- `window.mediaPipelineApi` — infrastructure
- `window.mediaPipelineDom` — infrastructure
- `window.mediaPipelineFormatters` — infrastructure
- `window.mediaPipeline{Page}View` — page view modules (14 view modules)
- `window.mediaPipelineCommandHistory` — cross-page shared module
- `window.mediaPipeline{Sub}` — sub-modules (launchReadinessView, launchHistoryView, renameHistoryView, renameLabels, settingsMetadata, settingsOverview, settingsCommandHistory, diagnosticsStateSummaryView, diagnosticsTailView, diagnosticsBridge)

No namespace object uses a generic name (e.g., not `window.view` or `window.api`). All are unambiguously prefixed with `mediaPipeline`.

Each namespace object is documented with an adjacent JSDoc boundary block:

- It identifies the object as the public namespace for the module.
- It directs new code to prefer namespace access.
- It labels any remaining flat `window.*` assignments as transitional compatibility aliases when present.

This is an object-boundary rule, not a mandate to add JSDoc to every internal helper.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| All 74 JS files inventoried | Pass |
| Namespace objects identified per file | Pass - 34 namespace-owning files; 40 no-namespace files listed in Summary |
| Namespace object JSDoc boundary present | Pass - 32/32 namespace objects have adjacent `Public namespace` comments guarded by `test_webview_inventory_docs.py` |
| Cross-module consumption documented | Pass |
| Backend-injected globals identified | Pass — 1 (MEDIA_PIPELINE_BOOTSTRAP) |
| No anonymous or generic window.* globals found | Pass |

The summary, module table, and machine-generated manifest in this file are the current authoritative inventory. Historical dated reviews below are retained for audit context and should not be used as current totals.

---

## Historical Freshness Review — 2026-05-15 (CLN3-004)

Historical addendum: the Diagnostics First Response Checklist added selectable row detail and 2 more flat exports to `diagnosticsView.js` (`selectedDiagnosticsFirstResponseRow` and `diagnosticsFirstResponseDetailLines`). Queue, Completed, and Pending Publish selected-row at-a-glance strips added 12 flat exports across `queueView.js`, `completedView.js`, and `pendingPublishView.js`. Rename Apply Outcome Review added 5 flat exports to `renameView.js` (`renderRenameApplyOutcomeReview`, `renameApplyOutcomeRows`, `renameApplyOutcomeStatus`, `renameApplyOutcomeSummaryLines`, and `renameApplyOutcomeStatusState`). Settings Effective Policy Trust added 6 flat exports to `settingsView.js` (`settingsEffectivePolicyRows`, `settingsEffectivePolicyTrustStatus`, `settingsEffectivePolicySummaryLines`, `settingsEffectivePolicyDetailLines`, `renderSettingsEffectivePolicyTrustFromEntries`, and `renderSettingsEffectivePolicyTrustForError`). At that point, the flat-export total was **1044** across 28 files, with `diagnosticsView.js` at **91**, `queueView.js` at **89**, `completedView.js` at **116**, `pendingPublishView.js` at **118**, `renameView.js` at **64**, and `settingsView.js` at **125** flat exports.

Re-run of post-namespace flat export counts after recent Launch Real-Media Proof Handoff, Launch Scope Reconciliation, Launch Start Decision Summary, Launch Sample Validation record, and Home Sample Validation worksheet exports.

**Counting methodology**: post-namespace flat assignments only — lines of the form `window.X = value;` appearing after the namespace object `};` close and before the IIFE `})();`. The namespace object itself (`window.mediaPipeline* = {...}`) is excluded. This is consistent with the original CLN2-17 methodology.

Note: a linter pass stored incorrect values for two modules (crossPageContextView: 43, launchView: 82). The 43 was the count of entries *inside* the namespace object body, not flat exports after it. The 82 for launchView included the namespace object assignment itself. These have been corrected below.

| Module | CLN2-17 count | CLN3-004 count | Delta | New functions |
|---|---|---|---|---|
| `crossPageContextView.js` | 21 | 31 | +10 | worksheet run match helpers, sample validation record match helpers, reconciliation helpers, initSampleValidationViewEvents |
| `launchView.js` | 75 | 86 | +11 | launchRealMediaProofRows/Status/SummaryLines/DetailLines, launchWorksheetEvidence/RunRows/RunsMatchingSample, launchSampleValidationRecordEvidence/Rows/RecordsMatchingSample, launchStartDecisionRows/Status/SummaryLines/DetailLines/Render |
| `contractView.js` | 6 | 6 | 0 | — |
| `networkView.js` | 7 | 7 | 0 | — |

**Historical total: 1006 flat exports across 28 files** (was 985 at CLN2-17, +21).

---

## Delta Review — 2026-05-18 (Dashboard command-surface cleanup)

The home-page schedule toggle quick action was removed when Dashboard command shortcuts were moved back to their owning pages. The two Stage 12 schedule-toggle flat exports were removed from `scheduleView.js`; schedule mutation is now available only through the Schedule page editor controls.

| Module | Previous count | New count | Delta | New exports |
|---|---|---|---|---|
| `scheduleView.js` | Stage 12 plus quick-toggle exports | current | -2 | none |

No new exports were added to replace the removed quick-toggle functions. The Schedule page keeps its existing preview/save workflow and backend-owned `/api/schedule/save` command path.

Launch preflight helpers are namespace-only through `mediaPipelineLaunchView`; split modules receive helpers through dependency injection.

**Running total note:** this delta removes two Stage 12 flat exports; full export totals should be regenerated in the dedicated inventory regeneration chunk.

---

## Historical Freshness Review — 2026-05-15 (CLN2-17)

Re-counted flat `window.*` exports in all 30 JS files using a Python script that isolates the post-namespace flat export block (lines after the closing `};` of the namespace object, before the IIFE `})();`). The `window.\w+ =` grep pattern produces false positives from `typeof window.X === "function"` guards; the script avoids these by restricting the count window.

| Module | Previous count | Current count | Delta | Reason |
|---|---|---|---|---|
| `contractView.js` | 2 | 6 | +4 | Reconciliation panel and scope boundary exports added |
| `crossPageContextView.js` | 16 | 43 | +27 | Sample-validation worksheet, record/reconciliation, and launch-proof context exports added |
| `launchView.js` | 59 | 82 | +23 | Launch proof evidence, validation-record evidence, active media policy boundary, and preflight panel exports added |
| `networkView.js` | 6 | 7 | +1 | CDP/smoke-support telemetry export added |

**Historical total: 1001 flat compatibility exports across 30 files** (was 959, delta +42).

All 30 files were re-checked. No files were added or removed. The two-layer namespace + flat export pattern is unchanged. No anonymous globals introduced.

---

## Task Output

```
Task ID: CLN-012
Files inspected: All 30 assets/*.js files (grep window.* = assignments)
Files changed: docs\inventories\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md (created)
Validation: Test-Path docs\inventories\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md
Findings: 29 namespace objects + 959 flat exports across 28 files. app.js is orchestrator-only (0 exports). settingsMetadata.js has namespace object only. MEDIA_PIPELINE_BOOTSTRAP is the only backend-injected global.
Open questions: None.
Risk: Low — documentation only.
```

---

---

## Machine-Generated Flat Export Manifest - 2026-06-23

Generated from `apps/desktop/webview/static/assets/*.js` by scanning `window.* =` assignments. Namespace objects are listed separately from flat exports.

Flat export total: 435

<!-- BEGIN GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->
### apiClient.js

Namespace objects: mediaPipelineApi

Flat exports (4):
```text
MEDIA_PIPELINE_BOOTSTRAP
MEDIA_PIPELINE_TAURI_BOOTSTRAP
apiGet
apiPost
```

### app.js

Namespace objects: none

Flat exports (10):
```text
showPage
refreshAll
refreshAllNow
setTopbarPendingLaunch
externalDependencyRows
externalDependencyOverallStatus
externalDependencySummaryLines
externalDependencyEvidenceText
renderExternalDependencyDigest
getLastSnapshot
```

### commandHistory.js

Namespace objects: mediaPipelineCommandHistory

Flat exports (3):
```text
appendCommandResult
getCommandHistory
commandHistoryCompactEvidenceLine
```

### completedView.diagnostics.js

Namespace objects: none

Flat exports (1):
```text
__completedViewDiagnosticsModule
```

### completedView.evidence.js

Namespace objects: none

Flat exports (1):
```text
__completedViewEvidenceModule
```

### completedView.js

Namespace objects: mediaPipelineCompletedView

Flat exports (0):
```text
```

### completedView.proof.js

Namespace objects: none

Flat exports (1):
```text
__completedViewProofModule
```

### completedView.repair.js

Namespace objects: none

Flat exports (1):
```text
__completedViewRepairModule
```

### completedView.review.js

Namespace objects: none

Flat exports (1):
```text
__completedViewReviewModule
```

### contractView.js

Namespace objects: mediaPipelineContractView

Flat exports (0):
```text
```

### crossPageContextView.conflict.js

Namespace objects: none

Flat exports (1):
```text
__crossPageConflictModule
```

### crossPageContextView.js

Namespace objects: mediaPipelineLastCrossPageContext, mediaPipelineCrossPageContextView

Flat exports (64):
```text
renderCrossPageContext
renderCrossPageConflictBoard
renderCrossPageSampleCorrelation
renderCrossPageValidationTemplate
crossPageConflictRows
crossPageConflictStatus
crossPageSampleRows
crossPageSampleStatus
crossPageValidationTemplateLines
crossPageSampleValidationEvidence
crossPageRealMediaWorksheetRows
crossPageRealMediaWorksheetStatus
renderCrossPageRealMediaWorksheet
sampleValidationCutoverRows
sampleValidationCutoverStatus
sampleValidationCutoverSummaryLines
sampleValidationCutoverDetailLines
sampleValidationGapPayload
sampleValidationGapRows
sampleValidationGapStatus
sampleValidationGapSummaryLines
sampleValidationGapDetailLines
sampleValidationRunbookPayload
sampleValidationRunbookRows
sampleValidationRunbookStatus
sampleValidationRunbookSummaryLines
sampleValidationRunbookMarkdownLines
sampleValidationRunbookDetailLines
sampleValidationSampleSetRows
sampleValidationSampleSetStatus
sampleValidationSampleSetSummaryLines
sampleValidationSampleSetCoverageLine
sampleValidationSampleSetDetailLines
sampleValidationSampleSetKey
sampleValidationCategorySummaryStatus
sampleValidationCategorySummaryLines
sampleValidationCategorySummaryDetailLines
sampleValidationExecutionRows
sampleValidationExecutionStatus
sampleValidationWorksheetRows
sampleValidationWorksheetRunMatchesSample
sampleValidationWorksheetSummaryLines
sampleValidationWorksheetDetailLines
sampleValidationRecordRows
sampleValidationReconciliationRows
sampleValidationReconciliationForRecord
sampleValidationRecordMatchesSample
sampleValidationRecordComparisonRowsForPaths
sampleValidationRecordsMatchingSample
sampleValidationRecordLines
sampleValidationCompletedPacketStatus
sampleValidationCompletedPolicyReconciliationRow
sampleValidationCompletedPolicyReconciliationStatus
sampleValidationCompletedPacketSummaryLines
sampleValidationCompletedPacketDetailLines
sampleValidationCompletedPacketMarkdownLines
sampleValidationAcceptanceGateStatus
sampleValidationAcceptanceGateSummaryLines
sampleValidationAcceptanceGateDetailLines
sampleValidationRecordReviewStatus
sampleValidationRecordReviewSummaryLines
sampleValidationRecordReviewDetailLines
sampleValidationShellSurface
initSampleValidationViewEvents
```

### crossPageContextView.sample.js

Namespace objects: none

Flat exports (1):
```text
__crossPageSampleModule
```

### crossPageContextView.sampleValidation.js

Namespace objects: none

Flat exports (1):
```text
__crossPageSampleValidationModule
```

### crossPageContextView.sampleValidation.records.js

Namespace objects: none

Flat exports (1):
```text
__crossPageSvRecordsModule
```

### crossPageContextView.sampleValidation.runbook.js

Namespace objects: none

Flat exports (1):
```text
__crossPageSvRunbookModule
```

### crossPageContextView.sampleValidation.worksheet.js

Namespace objects: none

Flat exports (1):
```text
__crossPageSvWorksheetModule
```

### crossPageContextView.settings.js

Namespace objects: none

Flat exports (1):
```text
__crossPageSettingsModule
```

### diagnosticsBridge.js

Namespace objects: mediaPipelineDiagnosticsBridge

Flat exports (0):
```text
```

### diagnosticsStateSummaryView.js

Namespace objects: mediaPipelineDiagnosticsStateSummaryView

Flat exports (0):
```text
```

### diagnosticsTailView.js

Namespace objects: mediaPipelineDiagnosticsTailView

Flat exports (0):
```text
```

### diagnosticsView.activejobs.js

Namespace objects: none

Flat exports (1):
```text
__diagnosticsActiveJobsModule
```

### diagnosticsView.investigation.js

Namespace objects: none

Flat exports (1):
```text
__diagnosticsInvestigationModule
```

### diagnosticsView.js

Namespace objects: mediaPipelineDiagnosticsView

Flat exports (60):
```text
renderDiagnostics
renderDiagnosticsRefreshFailures
diagnosticsTextLines
diagnosticsSeverityForLine
diagnosticsMalformedStateLines
diagnosticsSourceLines
diagnosticsActionGroups
diagnosticsActionPlanLines
diagnosticsStateIssueRows
diagnosticsPageReviewRows
diagnosticsCrossPageConflictRows
diagnosticsConflictSignalLabel
diagnosticsCommandIssueRows
diagnosticsInvestigationActions
diagnosticsInvestigationStatus
diagnosticsSamplePolicyReconciliation
renderDiagnosticsInvestigationTrail
diagnosticsListText
diagnosticsRowLabel
diagnosticsOwnerDefaultAction
diagnosticsOwnerRowSeverity
diagnosticsOwnerHandoffRowKey
diagnosticsCompletedFinalTrustStepForRow
diagnosticsCompletedFinalTrustLines
diagnosticsCompletedPolicyReconciliationLines
diagnosticsOwnerHandoffRows
diagnosticsOwnerHandoffStatus
diagnosticsOwnerHandoffSummaryLines
diagnosticsOwnerHandoffActions
diagnosticsOwnerPageId
diagnosticsOwnerSelectFunction
diagnosticsOwnerNavigationLabel
setDiagnosticsOwnerHandoffNavStatus
getSelectedDiagnosticsOwnerHandoffRow
selectDiagnosticsOwnerHandoffRow
renderDiagnosticsOwnerHandoffActions
diagnosticsSampleValidationComparisonLines
renderDiagnosticsOwnerHandoffDetail
renderDiagnosticsOwnerHandoffTable
appendDiagnosticsActionGroup
activeJobRowKey
selectActiveJobRow
getSelectedActiveJobRow
activeJobDiagnosticsActions
diagnosticsActiveJobRealMediaTraceLines
renderActiveJobDiagnosticsActions
renderActiveJobRows
renderActiveJobDetail
diagnosticsLineTimestamp
diagnosticsLogRows
diagnosticsArtifactsForLine
renderDiagnosticsLogActions
filteredDiagnosticsLogRows
getLastDiagnosticsLogRows
selectDiagnosticsLogRow
getSelectedDiagnosticsLogRow
renderDiagnosticsLogRows
renderDiagnosticsLogDetail
requestDiagnosticsTail
requestDiagnosticsOpen
```

### diagnosticsView.log.js

Namespace objects: none

Flat exports (1):
```text
__diagnosticsLogModule
```

### domHelpers.js

Namespace objects: mediaPipelineDom

Flat exports (22):
```text
byId
setText
applyDiagnosticCallouts
applyProseBoxDispositions
setTextState
clearRows
appendCells
filterRows
makeRowSelectable
selectRowInGroup
normalizeBackendStatusState
setPanelStatus
setInlineActionStatus
setActionBusy
backendRowStatusState
updateTableStatusLegend
formatStatusCounts
tableStatusFilterLabel
tableStatusMatchesFilter
filterRowsByStatus
filterRowsByInvestigation
enhanceDataTables
```

### formatters.js

Namespace objects: mediaPipelineFormatters

Flat exports (0):
```text
```

### launchHistoryView.js

Namespace objects: mediaPipelineLaunchHistoryView

Flat exports (0):
```text
```

### launchReadinessView.js

Namespace objects: mediaPipelineLaunchReadinessView

Flat exports (0):
```text
```

### launchView.js

Namespace objects: mediaPipelineLaunchView

Flat exports (0):
```text
```

### launchView.preflight.js

Namespace objects: none

Flat exports (1):
```text
__launchViewPreflightModule
```

### launchView.realmedia.js

Namespace objects: none

Flat exports (1):
```text
__launchViewRealMediaModule
```

### launchView.risk.js

Namespace objects: none

Flat exports (1):
```text
__launchViewRiskModule
```

### launchView.scope.js

Namespace objects: none

Flat exports (1):
```text
__launchViewScopeModule
```

### librariesRouteMap.js

Namespace objects: mediaPipelineLibraryRouteMap

Flat exports (0):
```text
```

### maintenanceView.js

Namespace objects: mediaPipelineMaintenanceView

Flat exports (0):
```text
```

### metricsView.js

Namespace objects: mediaPipelineMetricsView

Flat exports (0):
```text
```

### networkView.js

Namespace objects: mediaPipelineNetworkView

Flat exports (0):
```text
```

### pendingPublishView.confidence.js

Namespace objects: none

Flat exports (1):
```text
__pendingPublishConfidenceModule
```

### pendingPublishView.diagnostics.js

Namespace objects: none

Flat exports (1):
```text
__pendingPublishDiagnosticsModule
```

### pendingPublishView.drain.js

Namespace objects: none

Flat exports (1):
```text
__pendingPublishDrainModule
```

### pendingPublishView.js

Namespace objects: mediaPipelinePendingPublishView

Flat exports (92):
```text
renderPendingPublish
renderPendingFileInventory
renderPendingDetail
getLastPendingPublishPayload
renderPendingDrainEvidence
renderPendingDrainProgress
renderPendingDrainEvents
renderPendingDrainSummary
renderPendingDrainCorrelation
renderPendingDrainActionConfidence
renderPendingBackendDrainScopePreview
pendingBackendDrainScopeRows
pendingBackendDrainScopeStatus
pendingBackendDrainScopeSummaryLines
renderPendingDrainDecisionChecklist
pendingValidationStatus
pendingReviewRows
renderPendingReviewDigest
pendingEvidenceClass
pendingEvidenceRows
pendingEvidenceStatus
pendingDrainEvidenceLines
pendingEvidenceAction
pendingCurrentFilterScope
pendingCurrentFilterScopeEvidence
pendingCurrentFilterScopeAction
pendingSampleValidationHandoffLines
pendingDrainEventsStatus
pendingDrainEventsLines
pendingDrainEventsFromSnapshot
pendingDrainSummaryStatus
pendingDrainSummaryLines
pendingDrainSummaryPayload
pendingDrainLatestCommand
pendingDrainCommandIssueLevel
pendingDrainSummaryIssueLevel
pendingDrainCorrelationStatus
pendingDrainCorrelationLines
pendingDrainConfidenceRows
pendingDrainConfidenceStatus
pendingDrainConfidenceSummaryLines
pendingDrainDecisionRows
pendingDrainDecisionStatus
pendingDrainDecisionStatusState
pendingDrainDecisionSummaryLines
pendingDrainDecisionDetailLines
pendingDrainDecisionPostureStatus
pendingPostDrainTrustRows
pendingPostDrainTrustStatus
pendingPostDrainTrustSummaryLines
pendingPostDrainTrustDetailLines
pendingPostDrainTrustPostureStatus
pendingDrainGuardState
pendingDrainGuardLines
renderPendingDrainGuard
pendingDrainOverviewState
renderPendingDrainOverview
pendingFormatCounts
pendingListText
pendingSelectedOpenTargetLines
pendingDiagnosticsActionsForRow
pendingDiagnosticsGuidanceLines
renderPendingDiagnosticsLinks
requestPendingDiagnosticsAction
selectPendingRow
getSelectedPendingRow
pendingRowKey
setPendingOpenBusy
rejectPendingOpenWhileBusy
requestPendingPublishOpen
renderPendingDrainHistory
isPendingDrainCommand
pendingDrainHistoryLine
pendingDrainSearchText
renderPendingOpenHistory
isPendingOpenCommand
pendingOpenHistoryLine
setPendingRecoveryPlanBusy
rejectPendingRecoveryPlanWhileBusy
requestPendingRecoveryPlan
pendingRecoveryPlanResultLines
pendingRecoveryPlanRowKey
pendingRecoveryPlanRowStatus
pendingRecoveryPlanEvidenceText
pendingRecoveryPlanActionText
pendingRecoveryPlanRowDetailLines
renderPendingRecoveryPlanRows
selectPendingRecoveryPlanRow
renderPendingRecoveryPlanRowDetail
renderPendingRecoveryPlanHistory
isPendingRecoveryPlanCommand
pendingRecoveryPlanHistoryLine
```

### pendingPublishView.recovery.js

Namespace objects: none

Flat exports (1):
```text
__pendingPublishRecoveryModule
```

### pendingPublishView.repair.js

Namespace objects: none

Flat exports (1):
```text
__pendingPublishRepairModule
```

### progressView.js

Namespace objects: mediaPipelineProgressView

Flat exports (0):
```text
```

### queueView.detail.js

Namespace objects: none

Flat exports (1):
```text
__queueDetailModule
```

### queueView.js

Namespace objects: mediaPipelineQueueView

Flat exports (84):
```text
__queueSetFileDrawer
renderQueue
resetQueueFilters
renderQueueDetail
renderQueueProgress
queueProgressPayload
queueProgressBars
queueProgressStatus
queueProgressSummaryLines
renderQueueSummary
renderQueueReadiness
renderQueueWorkflow
renderQueueBackendLaunchScopePreview
queueBackendLaunchScopeRows
queueBackendLaunchScopeStatus
queueBackendLaunchScopeSummaryLines
renderQueueLaunchDecisionChecklist
renderQueueReviewBoard
renderQueueExcludedDetail
queueReadinessStatus
queueReadinessLines
queueRuntimeLines
queueValidationStatus
queueWorkflowStatus
queueWorkflowLines
queueLaunchDecisionRows
queueLaunchDecisionStatus
queueLaunchDecisionStatusState
queueLaunchDecisionSummaryLines
queueLaunchDecisionDetailLines
queueLaunchDecisionPostureStatus
queueLaunchDecisionLatestCommand
queueCurrentFilterScope
queueFilterScopePosture
queueFilterScopeEvidence
queueFilterScopeAction
queueFilterScopeDetailLines
queueLaunchBackendPreflightPayload
queueLaunchBackendPreflightCheckpoint
isQueueLaunchCommand
queueReviewStatus
queueReviewBoardLines
queueReviewRows
renderQueueReviewDigest
queueReviewDigestStatus
queueReviewDigestAction
queueListText
queueSelectedOpenTargetLines
queueRowReviewChecklistLines
queueRowIssueDigestLines
queueSelectedQuickSignalLines
queueSelectedAtAGlanceState
queueSelectedAtAGlanceStatus
queueSelectedAtAGlanceLines
renderQueueSelectedAtAGlance
queueFilterVisibilityLines
queueFocusedInvestigationLabels
queueInvestigationSignalLines
queueRealMediaTraceLines
queueRowTrustSummaryLines
queueDiagnosticsActionsForRow
queueDiagnosticsGuidanceLines
renderQueueDiagnosticsLinks
requestQueueDiagnosticsAction
queueCollisionLines
queueFormatCounts
queueFreshnessLine
queueSnapshotIsStale
selectQueueRow
getSelectedQueueRow
getSelectedQueuePriorityRows
getSelectedQueuePriorityRowKeys
getLastQueuePayload
getLastQueueRows
queueRowKey
requestQueueOpen
requestQueueScan
queueScanIsRunning
queueScanStatusLines
queueSourceInventoryLines
renderQueueScanArtifacts
isQueueOpenCommand
queueOpenHistoryLine
renderQueueOpenHistory
```

### queueView.launch.js

Namespace objects: none

Flat exports (1):
```text
__queueLaunchModule
```

### queueView.review.js

Namespace objects: none

Flat exports (1):
```text
__queueReviewModule
```

### queueView.summary.js

Namespace objects: none

Flat exports (1):
```text
__queueSummaryModule
```

### renameHistoryView.js

Namespace objects: mediaPipelineRenameHistoryView

Flat exports (0):
```text
```

### renameLabels.js

Namespace objects: mediaPipelineRenameLabels

Flat exports (0):
```text
```

### renameView.js

Namespace objects: mediaPipelineRenameView

Flat exports (0):
```text
```

### reportsView.js

Namespace objects: mediaPipelineReportsView

Flat exports (0):
```text
```

### scheduleView.js

Namespace objects: mediaPipelineScheduleView

Flat exports (0):
```text
```

### settingsCommandHistory.js

Namespace objects: mediaPipelineSettingsCommandHistory

Flat exports (0):
```text
```

### settingsLibraries.js

Namespace objects: mediaPipelineSettingsLibraries

Flat exports (0):
```text
```

### settingsMetadata.js

Namespace objects: mediaPipelineSettingsMetadata

Flat exports (0):
```text
```

### settingsOverview.js

Namespace objects: mediaPipelineSettingsOverview

Flat exports (0):
```text
```

### settingsView.builders.audio.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewAudioBuilderModule
```

### settingsView.builders.file_safety.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewFileSafetyBuilderModule
```

### settingsView.builders.network.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewNetworkBuilderModule
```

### settingsView.builders.pending.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewPendingPublishBuilderModule
```

### settingsView.builders.quality.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewQualityBuilderModule
```

### settingsView.builders.queue.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewQueueBuilderModule
```

### settingsView.builders.runtime.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewRuntimeBuilderModule
```

### settingsView.builders.subtitle.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewSubtitleBuilderModule
```

### settingsView.builders.video.js

Namespace objects: none

Flat exports (1):
```text
__settingsViewVideoBuilderModule
```

### settingsView.js

Namespace objects: mediaPipelineSettingsView

Flat exports (57):
```text
settingsRawActionPlanRows
settingsRawActionPlanStatus
settingsRawActionPlanSummaryLines
settingsRawActionPlanDetailLines
renderSettingsRawActionPlan
renderSettings
getLastSettings
settingsPolicyDeltaRows
settingsPolicyDeltaStatus
settingsLaunchImpactRows
settingsLaunchImpactStatus
settingsPatchIsTouched
settingsPatchEffectiveChangedEntries
syncVideoDetailSettingsBuilderFromConfig
collectVideoDetailSettingsBuilderPatch
applyVideoDetailSettingsBuilderToPatch
renderVideoDetailSettingsBuilderGuidance
markVideoDetailSettingsBuilderDirty
syncFileSafetySettingsBuilderFromConfig
syncQualityDetailSettingsBuilderFromConfig
collectQualityDetailSettingsBuilderPatch
applyQualityDetailSettingsBuilderToPatch
renderQualityDetailSettingsBuilderGuidance
markQualityDetailSettingsBuilderDirty
collectFileSafetySettingsBuilderPatch
applyFileSafetySettingsBuilderToPatch
renderFileSafetySettingsBuilderGuidance
markFileSafetySettingsBuilderDirty
syncNetworkSettingsBuilderFromConfig
collectNetworkSettingsBuilderPatch
applyNetworkSettingsBuilderToPatch
renderNetworkSettingsBuilderGuidance
markNetworkSettingsBuilderDirty
syncQueueSettingsBuilderFromConfig
collectQueueSettingsBuilderPatch
applyQueueSettingsBuilderToPatch
renderQueueSettingsBuilderGuidance
markQueueSettingsBuilderDirty
syncRuntimeSettingsBuilderFromConfig
collectRuntimeSettingsBuilderPatch
applyRuntimeSettingsBuilderToPatch
renderRuntimeSettingsBuilderGuidance
markRuntimeSettingsBuilderDirty
syncPendingPublishSettingsBuilderFromConfig
collectPendingPublishSettingsBuilderPatch
applyPendingPublishSettingsBuilderToPatch
renderPendingPublishSettingsBuilderGuidance
markPendingPublishSettingsBuilderDirty
syncFinalLibraryPromotionSettingsBuilderFromConfig
collectFinalLibraryPromotionSettingsPatch
previewFinalLibraryPromotionSettings
saveFinalLibraryPromotionSettings
renderFinalLibraryPromotionSettingsGuidance
markFinalLibraryPromotionSettingsBuilderDirty
renderSettingsMediaPolicyCrossCheck
writeSettingsPatchJson
initSettingsViewEvents
```

### settingsView.rawTriage.js

Namespace objects: none

Flat exports (1):
```text
__settingsRawTriageModule
```

### settingsView.safetyLocks.js

Namespace objects: none

Flat exports (1):
```text
__settingsSafetyLocksModule
```

### settingsWizard.js

Namespace objects: mediaPipelineSettingsWizard

Flat exports (0):
```text
```

### tauriLifecycleBridge.js

Namespace objects: mediaPipelineTauriLifecycleBridge

Flat exports (0):
```text
```

### telemetryView.js

Namespace objects: mediaPipelineTelemetryView

Flat exports (0):
```text
```

<!-- END GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->
