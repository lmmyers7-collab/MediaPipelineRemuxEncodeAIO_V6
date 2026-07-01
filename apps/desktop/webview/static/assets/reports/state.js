// reports/state.js
// Split child of reportsView.js. Loaded before reportsView.js; the parent owns
// this single state object and passes it to later Reports child modules.

(function () {
  "use strict";

  function createReportsState() {
    return {
      lastReportSnapshot: {},
      lastReportSettings: {},
      lastFailurePreviewPayload: {},
      lastFailureArtifactSummary: {},
      selectedFailureArtifactPaths: new Set(),
      lastFailureRows: [],
      lastFailureResolutionGroups: [],
      selectedFailureGroupKey: "",
      selectedFailureRowKey: "",
      selectedFailureRowKeys: new Set(),
      lastAuditPreviewPayload: {},
      lastAuditRows: [],
      selectedAuditRowKey: "",
      selectedAuditRowKeys: new Set(),
      lastAuditControls: {},
      lastReportAuditSources: {},
      selectedReportAuditSourceIds: new Set(),
      lastFailureEmptyMessage: "No failure rows available.",
      lastAuditEmptyMessage: "No audit rows available.",
      activeFailureFilterChip: "all",
      activeAuditFilterChip: "all",
      reportAuditStartBusy: false,
      reportAuditCommandBusy: "",
      reportAuditAcceptedRun: null,
      reportAuditTimerId: 0,
      reportAuditRefreshTimerIds: [],
      failureClearBusy: false,
      lastFailureClearPreview: null,
      failureArchiveBusy: false,
      lastFailureArchivePreview: null,
      failureArtifactCleanupBusy: false,
      lastFailureArtifactCleanupPreview: null,
      failureLifecycleBusy: false,
      lastFailureLifecyclePreview: null,
      reportsTabNavInitialized: false,
      reportsViewEventsInitialized: false,
    };
  }

  window.__reportsViewStateModule = {
    createReportsState,
  };
})();
