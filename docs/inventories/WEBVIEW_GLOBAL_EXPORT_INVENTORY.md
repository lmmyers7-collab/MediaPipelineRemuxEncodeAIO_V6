# WebView Global Export Inventory

Date: 2026-07-11

Inventories every `window.*` assignment in the recursive `apps/desktop/webview/static/assets/**/*.js` tree and records which backend-rendered or auxiliary HTML surface loads each script.

---

## Summary

- **284 reachable JS files** recursively inventoried under `assets/`: **83 root-level** and **201 nested**
- **56 files** contain **58 `window.mediaPipeline*` namespace assignments**
- **231 files** contain **558 flat `window.*` assignments**
- **4 files** contain no `window.*` assignment: `app/dashboard.js`, `app/lifecycleOrchestration.js`, `app/refreshCoordinator.js`, `queue/fileOverrides.drawer.js`
- **2 HTML surfaces** reference every JS asset: `main` 283, `assets/pipelineLogWindow.html` 2; **1 script** is shared across surfaces
- Backend-injected and transitional globals are included as assignments when they appear in source; the manifest records assignment occurrences, not unique API semantics.

---

## Module Inventory

The path is relative to `apps/desktop/webview/static/assets/`. Surface membership is derived from each reachable HTML document's `<script src>` list.

| File | HTML surface(s) | Namespace assignments | Flat exports |
| --- | --- | --- | ---: |
| `apiClient.js` | `main`, `assets/pipelineLogWindow.html` | mediaPipelineApi | 4 |
| `app/closeReadiness.js` | `main` | mediaPipelineAppCloseReadiness | 0 |
| `app/dashboard.js` | `main` | - | 0 |
| `app/home/dailyDriver.js` | `main` | - | 1 |
| `app/home/queueProjection.js` | `main` | - | 1 |
| `app/home.js` | `main` | mediaPipelineAppHome | 0 |
| `app/homeReadiness.js` | `main` | mediaPipelineAppHomeReadiness | 0 |
| `app/layoutManager/drawer.js` | `main` | - | 1 |
| `app/layoutManager/normalization.js` | `main` | - | 1 |
| `app/layoutManager.js` | `main` | mediaPipelineAppLayoutManager | 0 |
| `app/lifecycle/navigation.js` | `main` | - | 1 |
| `app/lifecycle/topbar.js` | `main` | - | 1 |
| `app/lifecycle.js` | `main` | mediaPipelineAppLifecycle | 0 |
| `app/lifecycleOrchestration.js` | `main` | - | 0 |
| `app/refresh.js` | `main` | mediaPipelineAppRefresh | 0 |
| `app/refreshCoordinator.js` | `main` | - | 0 |
| `app/rowOpenActions.js` | `main` | mediaPipelineAppRowOpenActions | 0 |
| `app/tauriLifecycle.js` | `main` | mediaPipelineAppTauriLifecycle | 0 |
| `app/topbar.js` | `main` | mediaPipelineAppTopbar | 0 |
| `app/uiPreferences.js` | `main` | - | 1 |
| `app.js` | `main` | - | 11 |
| `commandHistory/diagnosticEvidence.js` | `main` | - | 1 |
| `commandHistory/diagnostics.js` | `main` | - | 1 |
| `commandHistory/formatters.js` | `main` | - | 1 |
| `commandHistory/resolutionChecklist.js` | `main` | - | 1 |
| `commandHistory.js` | `main` | mediaPipelineCommandHistory | 3 |
| `completed/evidence/acceptance.js` | `main` | - | 1 |
| `completed/evidence/commands.js` | `main` | - | 1 |
| `completed/evidence/filterScope.js` | `main` | - | 1 |
| `completed/evidence/pendingProofModel.js` | `main` | - | 1 |
| `completed/evidence/pendingProofView.js` | `main` | - | 1 |
| `completed/evidence/routeAgreement.js` | `main` | - | 1 |
| `completed/filters.js` | `main` | - | 1 |
| `completed/openActions.js` | `main` | - | 1 |
| `completed/presentation.js` | `main` | - | 1 |
| `completed/promotionCommands.js` | `main` | - | 1 |
| `completed/proof/pilotEvidence.js` | `main` | - | 1 |
| `completed/review/healthSignals.js` | `main` | - | 1 |
| `completed/review/integrity.js` | `main` | - | 1 |
| `completed/review/investigationFilters.js` | `main` | - | 1 |
| `completed/review/metricsValidation.js` | `main` | - | 1 |
| `completed/review/reviewRows.js` | `main` | - | 1 |
| `completed/review/selectedAtAGlance.js` | `main` | - | 1 |
| `completed/review/selectedEvidence.js` | `main` | - | 1 |
| `completed/review/sizeReview.js` | `main` | - | 1 |
| `completed/review/tablePanels.js` | `main` | - | 1 |
| `completed/review/workflowOverview.js` | `main` | - | 1 |
| `completed/selection.js` | `main` | - | 1 |
| `completed/sizeMode.js` | `main` | - | 1 |
| `completed/statusBoards.js` | `main` | - | 1 |
| `completed/table.js` | `main` | - | 1 |
| `completedView.diagnostics.js` | `main` | - | 1 |
| `completedView.evidence.js` | `main` | - | 1 |
| `completedView.js` | `main` | mediaPipelineCompletedView | 0 |
| `completedView.proof.js` | `main` | - | 1 |
| `completedView.repair.js` | `main` | - | 1 |
| `completedView.review.js` | `main` | - | 1 |
| `contractView.js` | `main` | mediaPipelineContractView | 0 |
| `crossPageContextView.conflict.js` | `main` | - | 1 |
| `crossPageContextView.js` | `main` | mediaPipelineLastCrossPageContext, mediaPipelineCrossPageContextView | 64 |
| `crossPageContextView.sample.js` | `main` | - | 1 |
| `crossPageContextView.sampleValidation.js` | `main` | - | 1 |
| `crossPageContextView.sampleValidation.records.js` | `main` | - | 1 |
| `crossPageContextView.sampleValidation.runbook.js` | `main` | - | 1 |
| `crossPageContextView.sampleValidation.worksheet.js` | `main` | - | 1 |
| `crossPageContextView.settings.js` | `main` | - | 1 |
| `diagnostics/firstResponse.js` | `main` | - | 1 |
| `diagnostics/matrixConsole.js` | `main` | - | 1 |
| `diagnostics/triage.js` | `main` | - | 1 |
| `diagnosticsBridge.js` | `main` | mediaPipelineDiagnosticsBridge | 0 |
| `diagnosticsStateSummaryView.js` | `main` | mediaPipelineDiagnosticsStateSummaryView | 0 |
| `diagnosticsTailView.js` | `main` | mediaPipelineDiagnosticsTailView | 0 |
| `diagnosticsView.activejobs.js` | `main` | - | 1 |
| `diagnosticsView.investigation.js` | `main` | - | 1 |
| `diagnosticsView.js` | `main` | mediaPipelineDiagnosticsView | 60 |
| `diagnosticsView.log.js` | `main` | - | 1 |
| `dom/filtering.js` | `main` | - | 1 |
| `dom/query.js` | `main` | - | 1 |
| `dom/status.js` | `main` | - | 1 |
| `dom/table.js` | `main` | - | 1 |
| `dom/text.js` | `main` | - | 1 |
| `domHelpers.js` | `main` | mediaPipelineDom | 22 |
| `floatingPipelineLog.js` | `main` | mediaPipelineFloatingPipelineLog | 0 |
| `formatters.js` | `main` | mediaPipelineFormatters | 0 |
| `launch/commandButtons.js` | `main` | - | 1 |
| `launch/commandOrchestration.js` | `main` | - | 1 |
| `launch/controllerState.js` | `main` | - | 1 |
| `launch/preflight/pilotReadiness.js` | `main` | - | 1 |
| `launch/rerunEvidence.js` | `main` | - | 1 |
| `launch/rerunFacade.js` | `main` | - | 1 |
| `launch/rerunOrchestration.js` | `main` | - | 1 |
| `launch/rerunPresentation.js` | `main` | - | 1 |
| `launch/risk/mediaPolicyValues.js` | `main` | - | 1 |
| `launch/risk/policyBoundary.js` | `main` | - | 1 |
| `launch/risk/policyPatch.js` | `main` | - | 1 |
| `launch/risk/riskRows.js` | `main` | - | 1 |
| `launch/risk/settingsAccess.js` | `main` | - | 1 |
| `launch/scope/compactGate.js` | `main` | - | 1 |
| `launch/scopeControls.js` | `main` | - | 1 |
| `launch/startRequest.js` | `main` | - | 1 |
| `launch/statusRender.js` | `main` | - | 1 |
| `launchHistoryView.js` | `main` | mediaPipelineLaunchHistoryView | 0 |
| `launchReadinessView.js` | `main` | mediaPipelineLaunchReadinessView | 0 |
| `launchView.js` | `main` | mediaPipelineCsvRerunWorkflow, mediaPipelineLaunchView | 0 |
| `launchView.preflight.js` | `main` | - | 1 |
| `launchView.realmedia.js` | `main` | - | 1 |
| `launchView.risk.js` | `main` | - | 1 |
| `launchView.scope.js` | `main` | - | 1 |
| `librariesRouteMap.js` | `main` | mediaPipelineLibraryRouteMap | 0 |
| `maintenance/changeLedger.js` | `main` | - | 1 |
| `maintenance/dryRunReadiness.js` | `main` | - | 1 |
| `maintenance/health.js` | `main` | - | 1 |
| `maintenance/releaseCommands.js` | `main` | - | 1 |
| `maintenanceView.js` | `main` | mediaPipelineMaintenanceView | 0 |
| `metricsView.js` | `main` | mediaPipelineMetricsView | 0 |
| `network/config.js` | `main` | - | 1 |
| `network/configDiagnostics.js` | `main` | - | 1 |
| `network/events.js` | `main` | - | 1 |
| `network/evidence.js` | `main` | - | 1 |
| `network/lifecycle.commands.js` | `main` | - | 1 |
| `network/lifecycle.model.js` | `main` | - | 1 |
| `network/lifecycle.results.js` | `main` | - | 1 |
| `network/lifecycle.view.js` | `main` | - | 1 |
| `network/lifecycleContract.js` | `main` | - | 1 |
| `network/openHistory.js` | `main` | - | 1 |
| `network/overviewModel.js` | `main` | - | 1 |
| `network/overviewTiles.js` | `main` | - | 1 |
| `network/queueProjection.js` | `main` | - | 1 |
| `network/readiness.js` | `main` | - | 1 |
| `network/rerunEvidence.js` | `main` | - | 1 |
| `network/roleDashboard.js` | `main` | - | 1 |
| `network/settingsHandoff.js` | `main` | - | 1 |
| `network/setup.commands.js` | `main` | - | 1 |
| `network/stateFiles.js` | `main` | - | 1 |
| `network/status.js` | `main` | - | 1 |
| `network/workers.model.js` | `main` | - | 1 |
| `network/workers.view.js` | `main` | - | 1 |
| `networkView.js` | `main` | mediaPipelineNetworkView | 0 |
| `operatorToast.js` | `main` | mediaPipelineOperatorToast | 0 |
| `pathPicker.js` | `main` | mediaPipelinePathPicker | 0 |
| `pendingPublish/actionCenter.js` | `main` | - | 1 |
| `pendingPublish/confidence/postDrainTrust.js` | `main` | - | 1 |
| `pendingPublish/defaultAdapters.js` | `main` | - | 1 |
| `pendingPublish/details.js` | `main` | - | 1 |
| `pendingPublish/filters.js` | `main` | - | 1 |
| `pendingPublish/rendering.js` | `main` | - | 1 |
| `pendingPublish/summary.js` | `main` | - | 1 |
| `pendingPublish/tableSupport.js` | `main` | - | 1 |
| `pendingPublishView.confidence.js` | `main` | - | 1 |
| `pendingPublishView.diagnostics.js` | `main` | - | 1 |
| `pendingPublishView.drain.js` | `main` | - | 1 |
| `pendingPublishView.js` | `main` | mediaPipelinePendingPublishView | 92 |
| `pendingPublishView.recovery.js` | `main` | - | 1 |
| `pendingPublishView.repair.js` | `main` | - | 1 |
| `pipelineLogWindow.js` | `assets/pipelineLogWindow.html` | mediaPipelinePipelineLogWindow | 0 |
| `pipelineLogWindowBridge.js` | `main` | mediaPipelinePipelineLogWindowBridge | 0 |
| `progress/activeWork.js` | `main` | - | 1 |
| `progress/audit.js` | `main` | - | 1 |
| `progress/barPresentation.js` | `main` | - | 1 |
| `progress/barState.js` | `main` | - | 1 |
| `progress/csvRerun.js` | `main` | - | 1 |
| `progress/details.js` | `main` | - | 1 |
| `progress/diagnostics.js` | `main` | - | 1 |
| `progress/evidence.js` | `main` | - | 1 |
| `progress/evidenceRows.js` | `main` | - | 1 |
| `progress/ffmpegEta.js` | `main` | - | 1 |
| `progress/liveRun.js` | `main` | - | 1 |
| `progress/timelineCore.js` | `main` | - | 1 |
| `progress/timelineView.js` | `main` | - | 1 |
| `progress/worker.js` | `main` | - | 1 |
| `progressView.js` | `main` | mediaPipelineProgressView | 0 |
| `provenanceView.js` | `main` | mediaPipelineProvenanceView | 0 |
| `queue/controls.js` | `main` | - | 1 |
| `queue/decisionSummary.js` | `main` | - | 1 |
| `queue/excluded.js` | `main` | - | 1 |
| `queue/fileOverrides.drawer.api.js` | `main` | - | 1 |
| `queue/fileOverrides.drawer.focus.js` | `main` | - | 1 |
| `queue/fileOverrides.drawer.form.js` | `main` | - | 1 |
| `queue/fileOverrides.drawer.js` | `main` | - | 0 |
| `queue/fileOverrides.drawer.series.js` | `main` | - | 1 |
| `queue/fileOverrides.drawer.state.js` | `main` | - | 1 |
| `queue/fileOverrides.drawer.tracks.js` | `main` | - | 1 |
| `queue/fileOverrides.routePreview.js` | `main` | - | 1 |
| `queue/manualOrder.js` | `main` | - | 1 |
| `queue/openActions.js` | `main` | - | 1 |
| `queue/priority.js` | `main` | - | 1 |
| `queue/rerunApi.js` | `main` | - | 1 |
| `queue/rerunRequest.js` | `main` | - | 1 |
| `queue/scan.js` | `main` | - | 1 |
| `queue/selection.js` | `main` | - | 1 |
| `queue/sourceModel.js` | `main` | - | 1 |
| `queue/sourceRender.js` | `main` | - | 1 |
| `queue/statusPanels.js` | `main` | - | 1 |
| `queue/strategy.js` | `main` | - | 1 |
| `queue/table.js` | `main` | - | 1 |
| `queue/tableView.js` | `main` | - | 1 |
| `queue/tabs.js` | `main` | - | 1 |
| `queueView.detail.js` | `main` | - | 1 |
| `queueView.js` | `main` | mediaPipelineQueueView | 79 |
| `queueView.launch.js` | `main` | - | 1 |
| `queueView.rerun.js` | `main` | - | 1 |
| `queueView.review.js` | `main` | - | 1 |
| `queueView.summary.js` | `main` | - | 1 |
| `recoverySupportView.js` | `main` | mediaPipelineRecoverySupportView | 0 |
| `rename/applyReadiness.js` | `main` | mediaPipelineRenameApplyReadinessSlice | 0 |
| `rename/applyResult.js` | `main` | mediaPipelineRenameApplyResultSlice | 0 |
| `rename/cleaningFilters.js` | `main` | - | 1 |
| `rename/cleaningWorkbench.js` | `main` | - | 1 |
| `rename/commandEvidence.js` | `main` | - | 1 |
| `rename/confirmSummary.js` | `main` | - | 1 |
| `rename/dialogs.js` | `main` | - | 1 |
| `rename/editing.js` | `main` | - | 1 |
| `rename/interactions.js` | `main` | - | 1 |
| `rename/paths.js` | `main` | - | 1 |
| `rename/preview.js` | `main` | mediaPipelineRenamePreviewSlice | 0 |
| `rename/previewLifecycle.js` | `main` | - | 1 |
| `rename/selection.js` | `main` | - | 1 |
| `renameHistoryView.js` | `main` | mediaPipelineRenameHistoryView | 0 |
| `renameLabels.js` | `main` | mediaPipelineRenameLabels | 0 |
| `renameView.js` | `main` | mediaPipelineRenameView | 0 |
| `reports/audit/progress.js` | `main` | - | 1 |
| `reports/audit/sources.js` | `main` | - | 1 |
| `reports/auditCommands.js` | `main` | - | 1 |
| `reports/auditModel.js` | `main` | - | 1 |
| `reports/auditView.js` | `main` | - | 1 |
| `reports/failureCommands.js` | `main` | - | 1 |
| `reports/failureModel.js` | `main` | - | 1 |
| `reports/failureView.js` | `main` | - | 1 |
| `reports/investigation.js` | `main` | - | 1 |
| `reports/shared.js` | `main` | - | 1 |
| `reports/shell.js` | `main` | - | 1 |
| `reports/state.js` | `main` | - | 1 |
| `reports/triage.js` | `main` | - | 1 |
| `reportsView.js` | `main` | mediaPipelineReportsView | 0 |
| `runMonitorView.js` | `main` | mediaPipelineRunMonitor | 0 |
| `schedule/editor.js` | `main` | - | 1 |
| `schedule/watchFolder.js` | `main` | - | 1 |
| `scheduleView.js` | `main` | mediaPipelineScheduleView | 0 |
| `settings/backendResult.js` | `main` | - | 1 |
| `settings/builderControls.js` | `main` | - | 1 |
| `settings/finalLibraryPromotion.js` | `main` | - | 1 |
| `settings/metadataFields.js` | `main` | - | 1 |
| `settings/patchInteractions.js` | `main` | - | 1 |
| `settings/patchOverview.js` | `main` | - | 1 |
| `settings/patchReadiness.js` | `main` | - | 1 |
| `settings/patchReview.js` | `main` | - | 1 |
| `settings/policyImpact/effectivePolicyView.js` | `main` | - | 1 |
| `settings/policyImpact/mediaProjection.js` | `main` | - | 1 |
| `settings/policyImpact.js` | `main` | - | 1 |
| `settings/presetLibrary.js` | `main` | mediaPipelinePresetLibraryView | 0 |
| `settings/routePolicyModel.js` | `main` | mediaPipelineRoutePolicyModel | 0 |
| `settings/view/builder.js` | `main` | - | 1 |
| `settings/view/commands.js` | `main` | - | 1 |
| `settings/view/facade.js` | `main` | - | 1 |
| `settings/view/impact.js` | `main` | - | 1 |
| `settings/view/lifecycle.js` | `main` | - | 1 |
| `settings/view/review.js` | `main` | - | 1 |
| `settings/wizard/libraryEditor.js` | `main` | - | 1 |
| `settings/wizard/previewRender.js` | `main` | - | 1 |
| `settingsCommandHistory.js` | `main` | mediaPipelineSettingsCommandHistory | 0 |
| `settingsLibraries/facade.js` | `main` | - | 1 |
| `settingsLibraries/interaction.js` | `main` | - | 1 |
| `settingsLibraries/model.js` | `main` | - | 1 |
| `settingsLibraries/render.js` | `main` | - | 1 |
| `settingsLibraries/summary.js` | `main` | - | 1 |
| `settingsLibraries.js` | `main` | mediaPipelineSettingsLibraries | 0 |
| `settingsMetadata.js` | `main` | mediaPipelineSettingsMetadata | 0 |
| `settingsOverview.js` | `main` | mediaPipelineSettingsOverview | 0 |
| `settingsView.builders.audio.js` | `main` | - | 1 |
| `settingsView.builders.file_safety.js` | `main` | - | 1 |
| `settingsView.builders.network.js` | `main` | - | 1 |
| `settingsView.builders.pending.js` | `main` | - | 1 |
| `settingsView.builders.quality.js` | `main` | - | 1 |
| `settingsView.builders.queue.js` | `main` | - | 1 |
| `settingsView.builders.runtime.js` | `main` | - | 1 |
| `settingsView.builders.subtitle.js` | `main` | - | 1 |
| `settingsView.builders.video.js` | `main` | - | 1 |
| `settingsView.js` | `main` | mediaPipelineSettingsView | 0 |
| `settingsView.rawTriage.js` | `main` | - | 1 |
| `settingsView.safetyLocks.js` | `main` | - | 1 |
| `settingsWizard.js` | `main` | mediaPipelineSettingsWizard | 0 |
| `tauriLifecycleBridge.js` | `main` | mediaPipelineTauriLifecycleBridge | 0 |
| `telemetry/gpuProjection.js` | `main` | - | 1 |
| `telemetryView.js` | `main` | mediaPipelineTelemetryView | 0 |

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
| `crossPageContextView.js` | `queueView.js` (`getSelectedQueueRow`, `selectQueueRow`), `completedView.js` (`mediaPipelineCompletedView.getSelectedCompletedRow`, `selectCompletedRow`), `pendingPublishView.js` (`getSelectedPendingRow`, `selectPendingRow`), `settingsView.js` (`mediaPipelineSettingsView.getLastSettings`), `app.js` (`showPage`) |
| `crossPageContextView.sampleValidation.js` | `crossPageContextView.sampleValidation.worksheet.js` (`__crossPageSvWorksheetModule` nested split-child factory stash, consumed and deleted during load), `crossPageContextView.sampleValidation.runbook.js` (`__crossPageSvRunbookModule` nested split-child factory stash, consumed and deleted during load), `crossPageContextView.sampleValidation.records.js` (`__crossPageSvRecordsModule` nested split-child factory stash, consumed and deleted during load) |
| `queueView.js` | `queueView.summary.js` (`__queueSummaryModule` split-child factory stash, consumed and deleted during load), `queueView.review.js` (`__queueReviewModule` split-child factory stash, consumed and deleted during load), `queueView.detail.js` (`__queueDetailModule` split-child factory stash, consumed and deleted during load), `queueView.launch.js` (`__queueLaunchModule` split-child factory stash, consumed and deleted during load), `queueView.rerun.js` (`__queueRerunModule` split-child factory stash, consumed and deleted during load) |
| `reports/auditCommands.js` | `app.js` (`showPage`) and `queueView.js` (`mediaPipelineQueueView.activateQueueTab`, `mediaPipelineQueueView.selectRerunCsvPathForPreview`) for the Audit-to-Queue CSV Rerun handoff after backend CSV export |
| `diagnosticsView.js` | `diagnosticsView.activejobs.js` (`__diagnosticsActiveJobsModule` split-child factory stash, consumed and deleted during load), `diagnosticsView.log.js` (`__diagnosticsLogModule` split-child factory stash, consumed and deleted during load), `diagnosticsView.investigation.js` (`__diagnosticsInvestigationModule` split-child factory stash, consumed and deleted during load), `diagnosticsBridge.js` (`mediaPipelineDiagnosticsBridge` namespace helpers), `diagnosticsTailView.js` (`mediaPipelineDiagnosticsTailView` tail functions), `queueView.js` (`queueReviewRows`), `completedView.js` (`mediaPipelineCompletedView.completedReviewRows`, `mediaPipelineCompletedView.selectCompletedFinalTrustStep`), `pendingPublishView.js` (`pendingReviewRows`), `crossPageContextView.js` (`crossPageConflictRows`), `commandHistory.js` (`mediaPipelineCommandHistory.commandHistoryIssueEntries`, `mediaPipelineCommandHistory.commandHistoryOwnerPage`, `mediaPipelineCommandHistory.commandHistorySuggestedAction`), `diagnosticsStateSummaryView.js` (`mediaPipelineDiagnosticsStateSummaryView.diagnosticsStateOperatorStatus`, `mediaPipelineDiagnosticsStateSummaryView.diagnosticsStateRecommendedFirstAction`) |
| `diagnosticsStateSummaryView.js` | `diagnosticsBridge.js` (`mediaPipelineDiagnosticsBridge` namespace helpers), `diagnosticsView.js` compatibility globals (`requestDiagnosticsTail`, `requestDiagnosticsOpen`) after full script load |
| `settingsView.js` | `settingsView.rawTriage.js` (`__settingsRawTriageModule` split-child factory stash, consumed and deleted during load), `settingsView.safetyLocks.js` (`__settingsSafetyLocksModule` split-child factory stash, consumed and deleted during load), and builder child stashes already listed in the module inventory |
| `app.js` | Page and shared modules (reads their flat exports to wire DOM events and orchestrate refresh) |

---

## Namespace Object Naming Convention

All **58 namespace assignments across 56 files** use the `window.mediaPipeline{ModuleRole}` prefix. Nested split modules are included in the recursive table and manifest above.

The legacy JSDoc boundary rule remains scoped to root-level object-literal namespace exports: the comment identifies the public namespace, directs new code toward namespace access, and labels remaining flat exports as compatibility aliases. Nested modules are inventoried recursively but are not silently promoted into that separate documentation contract.

Current root-level boundary result: **41/41 object-literal namespace assignments documented**.

---

## Acceptance Criteria

| Criterion | Status |
| --- | --- |
| All recursively discovered JS assets inventoried | Pass - 284 files |
| Every reachable main/auxiliary HTML surface represented | Pass - 2 surfaces |
| Namespace assignments identified per file | Pass - 58 assignments |
| Flat assignments identified per file | Pass - 558 assignments |
| Root-level namespace-object JSDoc boundary present | Pass - 41/41 |
| Cross-module consumption documented | Pass |

The summary, recursive module table, and machine-generated manifest in this file are the current authoritative inventory. Historical dated reviews below are retained for audit context and must not be used as current totals.

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

## Machine-Generated Recursive Global Export Manifest

Generated by `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.generate_webview_inventory_docs` from every script referenced by the main and auxiliary HTML surfaces. Counts are assignment occurrences: **58 namespace** and **558 flat**.

<!-- BEGIN GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->
### `apiClient.js`

Surfaces: `main`, `assets/pipelineLogWindow.html`

Namespace assignments (1):
```text
mediaPipelineApi
```

Flat exports (4):
```text
MEDIA_PIPELINE_BOOTSTRAP
MEDIA_PIPELINE_TAURI_BOOTSTRAP
apiGet
apiPost
```

### `app/closeReadiness.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppCloseReadiness
```

Flat exports (0):
```text
```

### `app/dashboard.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (0):
```text
```

### `app/home/dailyDriver.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__homeDailyDriverModule
```

### `app/home/queueProjection.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__homeQueueProjectionModule
```

### `app/home.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppHome
```

Flat exports (0):
```text
```

### `app/homeReadiness.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppHomeReadiness
```

Flat exports (0):
```text
```

### `app/layoutManager/drawer.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__layoutManagerDrawerModule
```

### `app/layoutManager/normalization.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__layoutManagerNormalizationModule
```

### `app/layoutManager.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppLayoutManager
```

Flat exports (0):
```text
```

### `app/lifecycle/navigation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__appLifecycleNavigationModule
```

### `app/lifecycle/topbar.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__appLifecycleTopbarModule
```

### `app/lifecycle.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppLifecycle
```

Flat exports (0):
```text
```

### `app/lifecycleOrchestration.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (0):
```text
```

### `app/refresh.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppRefresh
```

Flat exports (0):
```text
```

### `app/refreshCoordinator.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (0):
```text
```

### `app/rowOpenActions.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppRowOpenActions
```

Flat exports (0):
```text
```

### `app/tauriLifecycle.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppTauriLifecycle
```

Flat exports (0):
```text
```

### `app/topbar.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineAppTopbar
```

Flat exports (0):
```text
```

### `app/uiPreferences.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__appUiPreferencesModule
```

### `app.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (11):
```text
showPage
refreshAll
refreshAllNow
setTopbarPendingLaunch
clearTopbarPendingLaunch
externalDependencyRows
externalDependencyOverallStatus
externalDependencySummaryLines
externalDependencyEvidenceText
renderExternalDependencyDigest
getLastSnapshot
```

### `commandHistory/diagnosticEvidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__commandHistoryDiagnosticEvidenceModule
```

### `commandHistory/diagnostics.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__commandHistoryDiagnostics
```

### `commandHistory/formatters.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__commandHistoryFormatters
```

### `commandHistory/resolutionChecklist.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__commandHistoryResolutionChecklistModule
```

### `commandHistory.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineCommandHistory
```

Flat exports (3):
```text
appendCommandResult
getCommandHistory
commandHistoryCompactEvidenceLine
```

### `completed/evidence/acceptance.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewEvidenceAcceptanceModule
```

### `completed/evidence/commands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewEvidenceCommandsModule
```

### `completed/evidence/filterScope.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewEvidenceFilterScopeModule
```

### `completed/evidence/pendingProofModel.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedPendingProofModelModule
```

### `completed/evidence/pendingProofView.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedPendingProofViewModule
```

### `completed/evidence/routeAgreement.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewEvidenceRouteAgreementModule
```

### `completed/filters.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewFiltersModule
```

### `completed/openActions.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewOpenActionsModule
```

### `completed/presentation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedPresentationModule
```

### `completed/promotionCommands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewPromotionCommandsModule
```

### `completed/proof/pilotEvidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedPilotEvidenceModule
```

### `completed/review/healthSignals.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewReviewHealthSignalsModule
```

### `completed/review/integrity.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewReviewIntegrityModule
```

### `completed/review/investigationFilters.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewReviewInvestigationFiltersModule
```

### `completed/review/metricsValidation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedReviewMetricsValidationModule
```

### `completed/review/reviewRows.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewReviewRowsModule
```

### `completed/review/selectedAtAGlance.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedReviewSelectedAtAGlanceModule
```

### `completed/review/selectedEvidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedReviewSelectedEvidenceModule
```

### `completed/review/sizeReview.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewReviewSizeReviewModule
```

### `completed/review/tablePanels.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedReviewTablePanelsModule
```

### `completed/review/workflowOverview.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedReviewWorkflowOverviewModule
```

### `completed/selection.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewSelectionModule
```

### `completed/sizeMode.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedSizeModeModule
```

### `completed/statusBoards.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewStatusBoardsModule
```

### `completed/table.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewTableModule
```

### `completedView.diagnostics.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewDiagnosticsModule
```

### `completedView.evidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewEvidenceModule
```

### `completedView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineCompletedView
```

Flat exports (0):
```text
```

### `completedView.proof.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewProofModule
```

### `completedView.repair.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewRepairModule
```

### `completedView.review.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__completedViewReviewModule
```

### `contractView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineContractView
```

Flat exports (0):
```text
```

### `crossPageContextView.conflict.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__crossPageConflictModule
```

### `crossPageContextView.js`

Surfaces: `main`

Namespace assignments (2):
```text
mediaPipelineLastCrossPageContext
mediaPipelineCrossPageContextView
```

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

### `crossPageContextView.sample.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__crossPageSampleModule
```

### `crossPageContextView.sampleValidation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__crossPageSampleValidationModule
```

### `crossPageContextView.sampleValidation.records.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__crossPageSvRecordsModule
```

### `crossPageContextView.sampleValidation.runbook.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__crossPageSvRunbookModule
```

### `crossPageContextView.sampleValidation.worksheet.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__crossPageSvWorksheetModule
```

### `crossPageContextView.settings.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__crossPageSettingsModule
```

### `diagnostics/firstResponse.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__diagnosticsFirstResponseModule
```

### `diagnostics/matrixConsole.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__diagnosticsMatrixConsoleModule
```

### `diagnostics/triage.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__diagnosticsTriageModule
```

### `diagnosticsBridge.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineDiagnosticsBridge
```

Flat exports (0):
```text
```

### `diagnosticsStateSummaryView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineDiagnosticsStateSummaryView
```

Flat exports (0):
```text
```

### `diagnosticsTailView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineDiagnosticsTailView
```

Flat exports (0):
```text
```

### `diagnosticsView.activejobs.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__diagnosticsActiveJobsModule
```

### `diagnosticsView.investigation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__diagnosticsInvestigationModule
```

### `diagnosticsView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineDiagnosticsView
```

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

### `diagnosticsView.log.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__diagnosticsLogModule
```

### `dom/filtering.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__domFilteringModule
```

### `dom/query.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__domQueryModule
```

### `dom/status.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__domStatusModule
```

### `dom/table.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__domTableModule
```

### `dom/text.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__domTextModule
```

### `domHelpers.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineDom
```

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

### `floatingPipelineLog.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineFloatingPipelineLog
```

Flat exports (0):
```text
```

### `formatters.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineFormatters
```

Flat exports (0):
```text
```

### `launch/commandButtons.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchCommandButtonsModule
```

### `launch/commandOrchestration.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchCommandOrchestrationModule
```

### `launch/controllerState.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchControllerStateModule
```

### `launch/preflight/pilotReadiness.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchPilotReadinessModule
```

### `launch/rerunEvidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRerunEvidenceModule
```

### `launch/rerunFacade.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRerunFacade
```

### `launch/rerunOrchestration.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRerunOrchestrationModule
```

### `launch/rerunPresentation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRerunPresentationModule
```

### `launch/risk/mediaPolicyValues.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRiskMediaPolicyValuesModule
```

### `launch/risk/policyBoundary.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRiskPolicyBoundaryModule
```

### `launch/risk/policyPatch.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRiskPolicyPatchModule
```

### `launch/risk/riskRows.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRiskRowsModule
```

### `launch/risk/settingsAccess.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchRiskSettingsAccessModule
```

### `launch/scope/compactGate.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchCompactGateModule
```

### `launch/scopeControls.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchScopeControlsModule
```

### `launch/startRequest.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchStartRequestModule
```

### `launch/statusRender.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchStatusRenderModule
```

### `launchHistoryView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineLaunchHistoryView
```

Flat exports (0):
```text
```

### `launchReadinessView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineLaunchReadinessView
```

Flat exports (0):
```text
```

### `launchView.js`

Surfaces: `main`

Namespace assignments (2):
```text
mediaPipelineCsvRerunWorkflow
mediaPipelineLaunchView
```

Flat exports (0):
```text
```

### `launchView.preflight.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchViewPreflightModule
```

### `launchView.realmedia.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchViewRealMediaModule
```

### `launchView.risk.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchViewRiskModule
```

### `launchView.scope.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__launchViewScopeModule
```

### `librariesRouteMap.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineLibraryRouteMap
```

Flat exports (0):
```text
```

### `maintenance/changeLedger.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__maintenanceChangeLedgerModule
```

### `maintenance/dryRunReadiness.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__maintenanceDryRunReadinessModule
```

### `maintenance/health.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__maintenanceHealthModule
```

### `maintenance/releaseCommands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__maintenanceReleaseCommandsModule
```

### `maintenanceView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineMaintenanceView
```

Flat exports (0):
```text
```

### `metricsView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineMetricsView
```

Flat exports (0):
```text
```

### `network/config.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkConfigModule
```

### `network/configDiagnostics.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkConfigDiagnosticsModule
```

### `network/events.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkEventsModule
```

### `network/evidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkEvidenceModule
```

### `network/lifecycle.commands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkLifecycleCommandsModule
```

### `network/lifecycle.model.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkLifecycleModelModule
```

### `network/lifecycle.results.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkLifecycleResultsModule
```

### `network/lifecycle.view.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkLifecycleViewModule
```

### `network/lifecycleContract.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkLifecycleContractModule
```

### `network/openHistory.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkOpenHistoryModule
```

### `network/overviewModel.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkOverviewModelModule
```

### `network/overviewTiles.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkOverviewTilesModule
```

### `network/queueProjection.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkQueueProjectionModule
```

### `network/readiness.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkReadinessModule
```

### `network/rerunEvidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkRerunEvidenceModule
```

### `network/roleDashboard.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkRoleDashboardModule
```

### `network/settingsHandoff.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkSettingsHandoffModule
```

### `network/setup.commands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkSetupCommandsModule
```

### `network/stateFiles.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkStateFilesModule
```

### `network/status.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkStatusModule
```

### `network/workers.model.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkWorkersModelModule
```

### `network/workers.view.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__networkWorkersViewModule
```

### `networkView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineNetworkView
```

Flat exports (0):
```text
```

### `operatorToast.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineOperatorToast
```

Flat exports (0):
```text
```

### `pathPicker.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelinePathPicker
```

Flat exports (0):
```text
```

### `pendingPublish/actionCenter.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishActionCenterModule
```

### `pendingPublish/confidence/postDrainTrust.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPostDrainTrustModule
```

### `pendingPublish/defaultAdapters.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishDefaultAdaptersModule
```

### `pendingPublish/details.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishDetailsModule
```

### `pendingPublish/filters.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishFiltersModule
```

### `pendingPublish/rendering.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishRenderingModule
```

### `pendingPublish/summary.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishSummaryModule
```

### `pendingPublish/tableSupport.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishTableSupportModule
```

### `pendingPublishView.confidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishConfidenceModule
```

### `pendingPublishView.diagnostics.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishDiagnosticsModule
```

### `pendingPublishView.drain.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishDrainModule
```

### `pendingPublishView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelinePendingPublishView
```

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

### `pendingPublishView.recovery.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishRecoveryModule
```

### `pendingPublishView.repair.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__pendingPublishRepairModule
```

### `pipelineLogWindow.js`

Surfaces: `assets/pipelineLogWindow.html`

Namespace assignments (1):
```text
mediaPipelinePipelineLogWindow
```

Flat exports (0):
```text
```

### `pipelineLogWindowBridge.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelinePipelineLogWindowBridge
```

Flat exports (0):
```text
```

### `progress/activeWork.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressActiveWorkModule
```

### `progress/audit.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressAuditModule
```

### `progress/barPresentation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressBarPresentationModule
```

### `progress/barState.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressBarStateModule
```

### `progress/csvRerun.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressCsvRerunModule
```

### `progress/details.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressDetailsModule
```

### `progress/diagnostics.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressDiagnosticsModule
```

### `progress/evidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressEvidenceModule
```

### `progress/evidenceRows.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressEvidenceRowsModule
```

### `progress/ffmpegEta.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressFfmpegEtaModule
```

### `progress/liveRun.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressLiveRunModule
```

### `progress/timelineCore.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressTimelineCoreModule
```

### `progress/timelineView.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressTimelineViewModule
```

### `progress/worker.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__progressWorkerModule
```

### `progressView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineProgressView
```

Flat exports (0):
```text
```

### `provenanceView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineProvenanceView
```

Flat exports (0):
```text
```

### `queue/controls.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueControlsModule
```

### `queue/decisionSummary.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueDecisionModule
```

### `queue/excluded.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueExcludedModule
```

### `queue/fileOverrides.drawer.api.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueFileOverridesDrawerApiModule
```

### `queue/fileOverrides.drawer.focus.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueFileOverridesDrawerFocusModule
```

### `queue/fileOverrides.drawer.form.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueFileOverridesDrawerFormModule
```

### `queue/fileOverrides.drawer.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (0):
```text
```

### `queue/fileOverrides.drawer.series.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueFileOverridesDrawerSeriesModule
```

### `queue/fileOverrides.drawer.state.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueFileOverridesDrawerStateModule
```

### `queue/fileOverrides.drawer.tracks.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueFileOverridesDrawerTracksModule
```

### `queue/fileOverrides.routePreview.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueFileOverridesRoutePreviewModule
```

### `queue/manualOrder.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueManualOrderModule
```

### `queue/openActions.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueOpenActionsModule
```

### `queue/priority.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queuePriorityModule
```

### `queue/rerunApi.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueRerunApiModule
```

### `queue/rerunRequest.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueRerunRequestModule
```

### `queue/scan.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueScanModule
```

### `queue/selection.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueSelectionModule
```

### `queue/sourceModel.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueSourceModelModule
```

### `queue/sourceRender.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueSourceRenderModule
```

### `queue/statusPanels.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueStatusPanelsModule
```

### `queue/strategy.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueStrategyModule
```

### `queue/table.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueTableModule
```

### `queue/tableView.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueTableViewModule
```

### `queue/tabs.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueTabsModule
```

### `queueView.detail.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueDetailModule
```

### `queueView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineQueueView
```

Flat exports (79):
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
isQueueOpenCommand
queueOpenHistoryLine
renderQueueOpenHistory
```

### `queueView.launch.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueLaunchModule
```

### `queueView.rerun.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueRerunModule
```

### `queueView.review.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueReviewModule
```

### `queueView.summary.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__queueSummaryModule
```

### `recoverySupportView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRecoverySupportView
```

Flat exports (0):
```text
```

### `rename/applyReadiness.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRenameApplyReadinessSlice
```

Flat exports (0):
```text
```

### `rename/applyResult.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRenameApplyResultSlice
```

Flat exports (0):
```text
```

### `rename/cleaningFilters.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameCleaningFiltersModule
```

### `rename/cleaningWorkbench.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameCleaningWorkbenchModule
```

### `rename/commandEvidence.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameCommandEvidenceModule
```

### `rename/confirmSummary.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameConfirmSummaryModule
```

### `rename/dialogs.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameDialogsModule
```

### `rename/editing.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameEditingModule
```

### `rename/interactions.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameInteractionsModule
```

### `rename/paths.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renamePathsModule
```

### `rename/preview.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRenamePreviewSlice
```

Flat exports (0):
```text
```

### `rename/previewLifecycle.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renamePreviewLifecycleModule
```

### `rename/selection.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__renameSelectionModule
```

### `renameHistoryView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRenameHistoryView
```

Flat exports (0):
```text
```

### `renameLabels.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRenameLabels
```

Flat exports (0):
```text
```

### `renameView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRenameView
```

Flat exports (0):
```text
```

### `reports/audit/progress.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsAuditProgressModule
```

### `reports/audit/sources.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsAuditSourcesModule
```

### `reports/auditCommands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewAuditCommandsModule
```

### `reports/auditModel.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewAuditModelModule
```

### `reports/auditView.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewAuditViewModule
```

### `reports/failureCommands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewFailureCommandsModule
```

### `reports/failureModel.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewFailureModelModule
```

### `reports/failureView.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewFailureViewModule
```

### `reports/investigation.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewInvestigationModule
```

### `reports/shared.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewSharedModule
```

### `reports/shell.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewShellModule
```

### `reports/state.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewStateModule
```

### `reports/triage.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__reportsViewTriageModule
```

### `reportsView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineReportsView
```

Flat exports (0):
```text
```

### `runMonitorView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRunMonitor
```

Flat exports (0):
```text
```

### `schedule/editor.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__scheduleEditorModule
```

### `schedule/watchFolder.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__scheduleWatchFolderModule
```

### `scheduleView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineScheduleView
```

Flat exports (0):
```text
```

### `settings/backendResult.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsBackendResultModule
```

### `settings/builderControls.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsBuilderControlsModule
```

### `settings/finalLibraryPromotion.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsFinalLibraryPromotionModule
```

### `settings/metadataFields.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsMetadataFieldsModule
```

### `settings/patchInteractions.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsPatchInteractionsModule
```

### `settings/patchOverview.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsPatchOverviewModule
```

### `settings/patchReadiness.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsPatchReadinessModule
```

### `settings/patchReview.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsPatchReviewModule
```

### `settings/policyImpact/effectivePolicyView.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsEffectivePolicyViewModule
```

### `settings/policyImpact/mediaProjection.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsMediaProjectionModule
```

### `settings/policyImpact.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsPolicyImpactModule
```

### `settings/presetLibrary.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelinePresetLibraryView
```

Flat exports (0):
```text
```

### `settings/routePolicyModel.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineRoutePolicyModel
```

Flat exports (0):
```text
```

### `settings/view/builder.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewBuilderModule
```

### `settings/view/commands.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewCommandsModule
```

### `settings/view/facade.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewFacade
```

### `settings/view/impact.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewImpactModule
```

### `settings/view/lifecycle.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewLifecycleModule
```

### `settings/view/review.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewReviewModule
```

### `settings/wizard/libraryEditor.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsWizardLibraryEditorModule
```

### `settings/wizard/previewRender.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsWizardPreviewRenderModule
```

### `settingsCommandHistory.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineSettingsCommandHistory
```

Flat exports (0):
```text
```

### `settingsLibraries/facade.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsLibrariesFacade
```

### `settingsLibraries/interaction.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsLibrariesInteractionModule
```

### `settingsLibraries/model.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsLibrariesModelModule
```

### `settingsLibraries/render.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsLibrariesRenderingModule
```

### `settingsLibraries/summary.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsLibrariesSummaryModule
```

### `settingsLibraries.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineSettingsLibraries
```

Flat exports (0):
```text
```

### `settingsMetadata.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineSettingsMetadata
```

Flat exports (0):
```text
```

### `settingsOverview.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineSettingsOverview
```

Flat exports (0):
```text
```

### `settingsView.builders.audio.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewAudioBuilderModule
```

### `settingsView.builders.file_safety.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewFileSafetyBuilderModule
```

### `settingsView.builders.network.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewNetworkBuilderModule
```

### `settingsView.builders.pending.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewPendingPublishBuilderModule
```

### `settingsView.builders.quality.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewQualityBuilderModule
```

### `settingsView.builders.queue.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewQueueBuilderModule
```

### `settingsView.builders.runtime.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewRuntimeBuilderModule
```

### `settingsView.builders.subtitle.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewSubtitleBuilderModule
```

### `settingsView.builders.video.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsViewVideoBuilderModule
```

### `settingsView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineSettingsView
```

Flat exports (0):
```text
```

### `settingsView.rawTriage.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsRawTriageModule
```

### `settingsView.safetyLocks.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__settingsSafetyLocksModule
```

### `settingsWizard.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineSettingsWizard
```

Flat exports (0):
```text
```

### `tauriLifecycleBridge.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineTauriLifecycleBridge
```

Flat exports (0):
```text
```

### `telemetry/gpuProjection.js`

Surfaces: `main`

Namespace assignments (0):
```text
```

Flat exports (1):
```text
__telemetryGpuProjectionModule
```

### `telemetryView.js`

Surfaces: `main`

Namespace assignments (1):
```text
mediaPipelineTelemetryView
```

Flat exports (0):
```text
```

<!-- END GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->
