/* App event binding and startup lifecycle orchestration. Loaded before app.js; callbacks run after the façade defines compatibility globals. */
document.addEventListener("DOMContentLoaded", async () => {
  renderBrandVersion();
  initKeyboardShortcuts();
  await restoreSharedUiPreferences();
  installSharedUiPreferenceStorageSync();
  initNavigation();
  initLayoutManager();
  initAdvancedToggle();
  initEvidenceToggle();
  initThemeToggle();
  initLaunchEvidenceToggle();
  initCollapsibleSummaries();
  window.mediaPipelineDom?.enhanceDataTables?.();
  initPageRefreshButtons();
  initSettingsTabNav();
  initDiagnosticsTabNav();
  initCompletedTabNav();
  startSharedUiPreferenceRemoteRefresh();
  if (typeof applyDiagnosticCallouts === "function") applyDiagnosticCallouts(document);
  window.mediaPipelineDom?.applyProseBoxDispositions?.(document);
  applyDefaultActionTooltips();
  window.addEventListener("mediapipeline:backend-lifecycle", handleTauriBackendLifecycleEvent);
  window.mediaPipelineTauriLifecycleBridge?.replayLatestBackendLifecycleEvent?.();
  window.addEventListener("beforeunload", (event) => {
    if (!closeReadinessRequiresWarning()) return;
    const message = closeReadinessWarningMessage();
    event.preventDefault();
    event.returnValue = message;
    return message;
  });
  const refreshButton = byId("refresh-button");
  if (refreshButton) refreshButton.addEventListener("click", refreshAll);
  const homeRefreshButton = byId("home-refresh-button");
  if (homeRefreshButton) homeRefreshButton.addEventListener("click", refreshAll);
  const backendShutdownButton = byId("backend-shutdown-button");
  if (backendShutdownButton) backendShutdownButton.addEventListener("click", requestBackendShutdown);
  const renameUsesStandaloneWorkbench = Boolean(byId("rename-apply-button"));
  const renameView = window.mediaPipelineRenameView || {};
  const renamePreviewButton = byId("rename-preview-button");
  if (renamePreviewButton && !renameUsesStandaloneWorkbench) renamePreviewButton.addEventListener("click", () => renameView.refreshRenamePreview?.());
  const renamePreviewTopButton = byId("rename-preview-top-button");
  if (renamePreviewTopButton) renamePreviewTopButton.addEventListener("click", () => renameView.refreshRenamePreview?.());
  const renameUseSelectedQueueButton = byId("rename-use-selected-queue-button");
  if (renameUseSelectedQueueButton) renameUseSelectedQueueButton.addEventListener("click", () => renameView.useSelectedQueueRowForRename?.());
  const renameUseLoadedQueueButton = byId("rename-use-loaded-queue-button");
  if (renameUseLoadedQueueButton) renameUseLoadedQueueButton.addEventListener("click", () => renameView.useLoadedQueueRowsForRename?.());
  const renameBrowseFilesButton = byId("rename-browse-files-button");
  if (renameBrowseFilesButton && !renameUsesStandaloneWorkbench) renameBrowseFilesButton.addEventListener("click", () => renameView.browseRenamePaths?.("files"));
  const renameBrowseFolderButton = byId("rename-browse-folder-button");
  if (renameBrowseFolderButton && !renameUsesStandaloneWorkbench) renameBrowseFolderButton.addEventListener("click", () => renameView.browseRenamePaths?.("folder"));
  const renameAddPathButton = byId("rename-add-path-button");
  if (renameAddPathButton) renameAddPathButton.addEventListener("click", () => renameView.addRenamePathFromInput?.());
  const renameClearPathsButton = byId("rename-clear-paths-button");
  if (renameClearPathsButton && !renameUsesStandaloneWorkbench) renameClearPathsButton.addEventListener("click", () => renameView.clearRenamePaths?.());
  const renameAddPathInput = byId("rename-add-path-input");
  if (renameAddPathInput) {
    renameAddPathInput.addEventListener("input", () => renameView.syncRenameCommandButtons?.());
    renameAddPathInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      renameView.addRenamePathFromInput?.();
    });
  }
  const renamePaths = byId("rename-paths");
  if (renamePaths) renamePaths.addEventListener("input", () => {
    renameView.renderRenameFileSourceSummary?.();
    renameView.syncRenameCommandButtons?.();
  });
  renameView.renderRenameFileSourceSummary?.();
  const renameSaveOverrideButton = byId("rename-save-override-button");
  if (renameSaveOverrideButton) renameSaveOverrideButton.addEventListener("click", () => renameView.applyRenameSelectedOverride?.());
  const renameClearOverrideButton = byId("rename-clear-override-button");
  if (renameClearOverrideButton) renameClearOverrideButton.addEventListener("click", () => renameView.clearRenameSelectedOverride?.());
  const renameApplySelectedButton = byId("rename-apply-selected-button");
  if (renameApplySelectedButton && !renameUsesStandaloneWorkbench) renameApplySelectedButton.addEventListener("click", () => renameView.applySelectedRename?.());
  const renameCheckApplicableButton = byId("rename-check-applicable-button");
  if (renameCheckApplicableButton) renameCheckApplicableButton.addEventListener("click", () => renameView.checkApplicableRenameRows?.());
  const renameCheckAllButton = byId("rename-check-all-button");
  if (renameCheckAllButton) renameCheckAllButton.addEventListener("click", () => renameView.checkAllRenameRows?.());
  const renameClearChecksButton = byId("rename-clear-checks-button");
  if (renameClearChecksButton) renameClearChecksButton.addEventListener("click", () => renameView.clearCheckedRenameRows?.());
  const renameMoveCheckedUpButton = byId("rename-move-checked-up-button");
  if (renameMoveCheckedUpButton) renameMoveCheckedUpButton.addEventListener("click", () => renameView.moveCheckedRenamePaths?.(-1));
  const renameMoveCheckedDownButton = byId("rename-move-checked-down-button");
  if (renameMoveCheckedDownButton) renameMoveCheckedDownButton.addEventListener("click", () => renameView.moveCheckedRenamePaths?.(1));
  const renameNaturalSortButton = byId("rename-natural-sort-button");
  if (renameNaturalSortButton) renameNaturalSortButton.addEventListener("click", () => renameView.naturalSortRenamePaths?.());
  const renameBulkScope = byId("rename-bulk-scope");
  if (renameBulkScope) renameBulkScope.addEventListener("change", () => {
    renameView.renderRenameBulkEditor?.();
    renameView.syncRenameCommandButtons?.();
  });
  const renameBulkStageButton = byId("rename-bulk-stage-button");
  if (renameBulkStageButton) renameBulkStageButton.addEventListener("click", () => renameView.stageRenameBulkEdit?.());
  const renameBulkUsePipelineButton = byId("rename-bulk-use-pipeline-button");
  if (renameBulkUsePipelineButton) renameBulkUsePipelineButton.addEventListener("click", () => renameView.usePipelineNamesForRenameScope?.());
  const renameBulkForceButton = byId("rename-bulk-force-button");
  if (renameBulkForceButton) renameBulkForceButton.addEventListener("click", () => renameView.setRenameBulkForce?.(true));
  const renameBulkClearForceButton = byId("rename-bulk-clear-force-button");
  if (renameBulkClearForceButton) renameBulkClearForceButton.addEventListener("click", () => renameView.setRenameBulkForce?.(false));
  const renameBulkClearButton = byId("rename-bulk-clear-button");
  if (renameBulkClearButton) renameBulkClearButton.addEventListener("click", () => renameView.clearRenameBulkOverrides?.());
  renameView.initRenameCleaningFilterEditorEvents?.();
  // Standalone Rename workbench wiring: 3-step workflow, confirm + result dialogs,
  // mode-based field visibility, drop zone, modern folder picker via folder_files mode.
  renameView.renameInitWorkbenchEvents?.();
  initSettingsViewEvents();
  window.mediaPipelineSettingsLibraries?.initSettingsLibrariesEvents?.({ refreshAll });
  window.mediaPipelinePresetLibraryView?.initPresetLibraryEvents?.();
  window.mediaPipelineLibraryRouteMap?.initLibraryRouteMapEvents?.({ refreshAll });
  window.mediaPipelineSettingsWizard?.initSettingsWizardEvents?.({
    refreshAll,
    setSettingsCommandBusy: window.mediaPipelineSettingsView?.setSettingsCommandBusy,
    rejectSettingsCommandWhileBusy: window.mediaPipelineSettingsView?.rejectSettingsCommandWhileBusy,
  });
  const launchView = window.mediaPipelineLaunchView || {};
  launchView.initLaunchViewEvents?.();
  window.mediaPipelineFloatingPipelineLog?.initFloatingPipelineLogEvents?.();
  window.mediaPipelinePipelineLogWindowBridge?.initPipelineLogWindowBridgeEvents?.();
  window.mediaPipelineMetricsView?.initMetricsViewEvents?.();
  window.mediaPipelineReportsView?.initReportsViewEvents?.();
  window.mediaPipelineScheduleView?.initScheduleViewEvents?.();
  window.mediaPipelineDiagnosticsView?.initDiagnosticsViewEvents?.();
  window.mediaPipelineNetworkView?.initNetworkViewEvents?.();
  window.mediaPipelineContractView?.initContractViewEvents?.();
  const maintenanceView = window.mediaPipelineMaintenanceView || {};
  maintenanceView.initMaintenanceViewEvents?.();
  window.mediaPipelineRecoverySupportView?.initRecoverySupportEvents?.();
  if (typeof initSampleValidationViewEvents === "function") initSampleValidationViewEvents();
  const pipelineStartButton = byId("pipeline-start-button");
  if (pipelineStartButton) pipelineStartButton.addEventListener("click", () => launchView.startPipelineFromForm?.());
  const pendingDrainButton = byId("pending-drain-button");
  if (pendingDrainButton) pendingDrainButton.addEventListener("click", () => window.mediaPipelineLaunchView?.startPendingPublishDrain?.());
  const pendingRecoveryPlanSelectedButton = byId("pending-recovery-plan-selected-button");
  if (pendingRecoveryPlanSelectedButton) pendingRecoveryPlanSelectedButton.addEventListener("click", () => requestPendingRecoveryPlan("selected"));
  const pendingRecoveryPlanAllButton = byId("pending-recovery-plan-all-button");
  if (pendingRecoveryPlanAllButton) pendingRecoveryPlanAllButton.addEventListener("click", () => requestPendingRecoveryPlan("all"));
  const maintenanceRefreshButton = byId("maintenance-refresh-button");
  if (maintenanceRefreshButton) maintenanceRefreshButton.addEventListener("click", () => maintenanceView.refreshMaintenance?.());
  const releaseDryRunButton = byId("release-dry-run-button");
  if (releaseDryRunButton) releaseDryRunButton.addEventListener("click", () => maintenanceView.runReleaseDryRun?.());
  const releaseBuildButton = byId("release-build-button");
  if (releaseBuildButton) releaseBuildButton.addEventListener("click", () => maintenanceView.runReleaseBuild?.());
  const backfillDryRunButton = byId("backfill-dry-run-button");
  if (backfillDryRunButton) backfillDryRunButton.addEventListener("click", () => maintenanceView.runBackfillDryRun?.());
  const dependencyAtlasButton = byId("dependency-atlas-button");
  if (dependencyAtlasButton) dependencyAtlasButton.addEventListener("click", () => maintenanceView.runDependencyAtlas?.());
  const dependencyAtlasOpenFolderButton = byId("dependency-atlas-open-folder-button");
  if (dependencyAtlasOpenFolderButton) dependencyAtlasOpenFolderButton.addEventListener("click", () => maintenanceView.openDependencyAtlasFolder?.());
  const queueFilter = byId("queue-filter");
  if (queueFilter) queueFilter.addEventListener("input", () => window.mediaPipelineQueueView?.renderQueueRows?.());
  const queueStatusFilter = byId("queue-status-filter");
  if (queueStatusFilter) queueStatusFilter.addEventListener("change", () => window.mediaPipelineQueueView?.renderQueueRows?.());
  const queueInvestigationFilter = byId("queue-investigation-filter");
  if (queueInvestigationFilter) queueInvestigationFilter.addEventListener("change", () => window.mediaPipelineQueueView?.renderQueueRows?.());
  const queueClearFiltersButton = byId("queue-clear-filters-button");
  if (queueClearFiltersButton) queueClearFiltersButton.addEventListener("click", () => window.mediaPipelineQueueView?.resetQueueFilters?.());
  const completedFilter = byId("completed-filter");
  if (completedFilter) completedFilter.addEventListener("input", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedStatusFilter = byId("completed-status-filter");
  if (completedStatusFilter) completedStatusFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedLibraryFilter = byId("completed-library-filter");
  if (completedLibraryFilter) completedLibraryFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedInvestigationFilter = byId("completed-investigation-filter");
  if (completedInvestigationFilter) completedInvestigationFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedClearFiltersButton = byId("completed-clear-filters-button");
  if (completedClearFiltersButton) completedClearFiltersButton.addEventListener("click", () => window.mediaPipelineCompletedView?.resetCompletedFilters?.());
  const completedShowSelectedButton = byId("completed-show-selected-button");
  if (completedShowSelectedButton) completedShowSelectedButton.addEventListener("click", () => window.mediaPipelineCompletedView?.showSelectedCompletedRow?.());
  const completedRefreshCurrentOutputButton = byId("completed-refresh-current-output-button");
  if (completedRefreshCurrentOutputButton) completedRefreshCurrentOutputButton.addEventListener("click", refreshCurrentOutputStatus);
  const completedHistoryFilter = byId("completed-history-filter");
  if (completedHistoryFilter) completedHistoryFilter.addEventListener("input", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedHistoryStatusFilter = byId("completed-history-status-filter");
  if (completedHistoryStatusFilter) completedHistoryStatusFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedHistoryInvestigationFilter = byId("completed-history-investigation-filter");
  if (completedHistoryInvestigationFilter) completedHistoryInvestigationFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedHistoryClearFiltersButton = byId("completed-history-clear-filters-button");
  if (completedHistoryClearFiltersButton) completedHistoryClearFiltersButton.addEventListener("click", () => window.mediaPipelineCompletedView?.resetCompletedHistoryFilters?.());
  document.querySelectorAll("[data-completed-size-column-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      window.mediaPipelineCompletedView?.setCompletedSizeColumnMode?.(button.dataset.completedSizeColumnMode || "size");
    });
  });
  const publishReconciliationRefreshButton = byId("publish-reconciliation-refresh-button");
  if (publishReconciliationRefreshButton) publishReconciliationRefreshButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestPublishReconciliation?.());
  const completedCopyEvidenceButton = byId("completed-copy-evidence-button");
  if (completedCopyEvidenceButton) completedCopyEvidenceButton.addEventListener("click", () => window.mediaPipelineCompletedView?.copyCompletedEvidencePacket?.());
  const finalLibraryPromoteButton = byId("final-library-promote-button");
  if (finalLibraryPromoteButton) finalLibraryPromoteButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestFinalLibraryPromotion?.());
  document.querySelectorAll("[data-completed-promote-selected]").forEach((button) => {
    button.addEventListener("click", () => window.mediaPipelineCompletedView?.requestSelectedFinalLibraryPromotion?.());
  });
  const finalLibraryPauseButton = byId("final-library-pause-button");
  if (finalLibraryPauseButton) finalLibraryPauseButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestFinalLibraryPromotionPause?.());
  const finalLibraryResumeButton = byId("final-library-resume-button");
  if (finalLibraryResumeButton) finalLibraryResumeButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestFinalLibraryPromotionResume?.());
  const pendingFilter = byId("pending-filter");
  if (pendingFilter) pendingFilter.addEventListener("input", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingStatusFilter = byId("pending-status-filter");
  if (pendingStatusFilter) pendingStatusFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingInvestigationFilter = byId("pending-investigation-filter");
  if (pendingInvestigationFilter) pendingInvestigationFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingClearFiltersButton = byId("pending-clear-filters-button");
  if (pendingClearFiltersButton) pendingClearFiltersButton.addEventListener("click", () => window.mediaPipelinePendingPublishView?.resetPendingFilters?.());
  const failureFilter = byId("failure-filter");
  if (failureFilter) failureFilter.addEventListener("input", () => {
    window.mediaPipelineReportsView?.renderFailureResolutionGroups?.();
    window.mediaPipelineReportsView?.renderFailureRows?.();
  });
  const failureSourceMarkers = byId("failure-source-markers");
  if (failureSourceMarkers) failureSourceMarkers.addEventListener("change", refreshAll);
  const auditPreviewFilter = byId("audit-preview-filter");
  if (auditPreviewFilter) auditPreviewFilter.addEventListener("input", () => window.mediaPipelineReportsView?.renderAuditRows?.());
  const auditPreviewPriorityOnly = byId("audit-preview-priority-only");
  if (auditPreviewPriorityOnly) auditPreviewPriorityOnly.addEventListener("change", refreshAll);
  document.querySelectorAll("[data-control-action]").forEach((button) => {
    button.addEventListener("click", () => launchView.requestPipelineControl?.(button.dataset.controlAction || ""));
  });
  document.querySelectorAll("[data-open-diagnostics]").forEach((button) => {
    button.addEventListener("click", () => requestDiagnosticsOpen(button.dataset.openDiagnostics || "", button));
  });
  initBackendRowOpenActions();
  updatePagePanelEmptyStates();
  const startupStartedMs = window.performance?.now?.() || Date.now();
  window.performance?.mark?.("mediapipeline-startup-critical-start");
  void refreshAll({ automatic: true, initialCritical: true, page: "home" }).finally(() => {
    const criticalReadyMs = (window.performance?.now?.() || Date.now()) - startupStartedMs;
    window.performance?.mark?.("mediapipeline-startup-critical-ready");
    window.performance?.measure?.(
      "mediapipeline-startup-critical-data",
      "mediapipeline-startup-critical-start",
      "mediapipeline-startup-critical-ready",
    );
    const startupPerformance = {
      schema_version: "webview_startup_performance.v1",
      critical_ready_ms: Math.max(0, Math.round(criticalReadyMs * 10) / 10),
      critical_request_count: CORE_REFRESH_REQUESTS.size,
      secondary_scheduled: true,
    };
    window.setTimeout(() => {
      void refreshAll({ automatic: true, page: "home" }).finally(() => {
        const fullReadyMs = (window.performance?.now?.() || Date.now()) - startupStartedMs;
        const completedPerformance = {
          ...startupPerformance,
          full_ready_ms: Math.max(0, Math.round(fullReadyMs * 10) / 10),
          secondary_complete: true,
        };
        window.dispatchEvent(new CustomEvent("mediapipeline:startup-performance", {
          detail: completedPerformance,
        }));
      });
    }, 0);
  });
  window.setInterval(() => refreshAll({ automatic: true }), AUTOMATIC_REFRESH_INTERVAL_MS);
});
