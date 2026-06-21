(function () {
  const launchReadinessView = window.mediaPipelineLaunchReadinessView || {};
  const launchReadinessStatus = window.launchReadinessStatus || launchReadinessView.launchReadinessStatus || function () { return "Checking"; };
  const launchReadinessLines = window.launchReadinessLines || launchReadinessView.launchReadinessLines || function () { return []; };
  const renderLaunchReadiness = window.renderLaunchReadiness || launchReadinessView.renderLaunchReadiness || function () {};
  const launchHistoryView = window.mediaPipelineLaunchHistoryView || {};
  const isLaunchCommand = window.isLaunchCommand || launchHistoryView.isLaunchCommand || function () { return false; };
  const launchHistoryLine = window.launchHistoryLine || launchHistoryView.launchHistoryLine || function () { return ""; };
  const renderLaunchCommandHistory = window.renderLaunchCommandHistory || launchHistoryView.renderLaunchCommandHistory || function () {};
  const domHelpers = window.mediaPipelineDom || {};
  const jsonDetailText = domHelpers.jsonDetailText || function (options = {}) {
    const label = options.label || "JSON detail";
    try {
      return `${label}:\n${JSON.stringify(options.value, null, 2)}`;
    } catch (error) {
      return `${label}:\nJSON render error: ${error instanceof Error ? error.message : String(error)}`;
    }
  };
  const renderJsonDetail = domHelpers.renderJsonDetail || function (id, options = {}) {
    setText(id, jsonDetailText(options));
  };
  const LAUNCH_TAB_STORAGE_KEY = "mediapipeline-launch-tab";
  let launchCommandInFlight = false;
  let controlCommandInFlight = false;
  let pipelineFileBrowseInFlight = false;
  let pipelineStartScope = "queue";
  let selectedLaunchSettingsRiskKey = "";
  let selectedLaunchPolicyBoundaryKey = "";
  let selectedLaunchSettingsIntentKey = "";
  let selectedLaunchScopeReconciliationKey = "";
  let selectedLaunchStartDecisionKey = "";
  let selectedLaunchCompactGateKey = "";
  let selectedLaunchRealMediaProofKey = "";
  let selectedLaunchSampleExecutionKey = "";
  let lastLaunchRealMediaProofContext = {};
  let lastLaunchCommandState = { snapshot: null, closeReadiness: null };

  const launchCoordinatorState = {
    get launchCommandInFlight() { return launchCommandInFlight; },
    set launchCommandInFlight(value) { launchCommandInFlight = Boolean(value); },
    get controlCommandInFlight() { return controlCommandInFlight; },
    set controlCommandInFlight(value) { controlCommandInFlight = Boolean(value); },
    get pipelineFileBrowseInFlight() { return pipelineFileBrowseInFlight; },
    set pipelineFileBrowseInFlight(value) { pipelineFileBrowseInFlight = Boolean(value); },
    get pipelineStartScope() { return pipelineStartScope; },
    set pipelineStartScope(value) { pipelineStartScope = String(value || "queue"); },
    get lastLaunchCommandState() { return lastLaunchCommandState; },
    set lastLaunchCommandState(value) { lastLaunchCommandState = value && typeof value === "object" ? value : { snapshot: null, closeReadiness: null }; },
  };

  const launchControllerStateModule = window.__launchControllerStateModule || {};
  delete window.__launchControllerStateModule;
  const launchControllerState = typeof launchControllerStateModule.createLaunchControllerStateModule === "function"
    ? launchControllerStateModule.createLaunchControllerStateModule({
      state: launchCoordinatorState,
      getCommandHistory: function () {
        if (typeof window.getCommandHistory === "function") return window.getCommandHistory();
        if (typeof window.mediaPipelineCommandHistory?.getCommandHistory === "function") return window.mediaPipelineCommandHistory.getCommandHistory();
        return [];
      },
    })
    : {};
  const {
    launchPipelineIsActive = function () { return false; },
    pipelineProgressIsStuck = function () { return false; },
    pipelineProgressIsStale = function () { return false; },
    launchPauseRequested = function () { return false; },
    latestCommandEntry = function () { return null; },
    commandEntryState = function () { return ""; },
    commandEntrySummary = function () { return ""; },
    pipelineControllerState = function () { return "idle"; },
    pipelineControllerStageSummary = function () { return "No active backend work."; },
  } = launchControllerState;

  const launchStartRequestModule = window.__launchStartRequestModule || {};
  delete window.__launchStartRequestModule;
  const launchStartRequest = typeof launchStartRequestModule.createLaunchStartRequestModule === "function"
    ? launchStartRequestModule.createLaunchStartRequestModule({
      byId: typeof byId === "function" ? byId : window.byId,
    })
    : {};
  const {
    launchPreflightRequestMatches = function () { return false; },
    collectPipelineStartRequest = function () { return { mode: "validate", sleep_seconds: 30, show_config: false, show_console: false, schedule_override: "" }; },
    collectRerunStartRequest = function (options = {}) { return { csv_path: "", dry_run: Boolean(options.dry_run), stage_mode: "copy", original_mode: "keep", return_mode: "park", show_console: false }; },
  } = launchStartRequest;

  const launchStatusRenderModule = window.__launchStatusRenderModule || {};
  delete window.__launchStatusRenderModule;
  const launchStatusRender = typeof launchStatusRenderModule.createLaunchStatusRenderModule === "function"
    ? launchStatusRenderModule.createLaunchStatusRenderModule({
      byId: typeof byId === "function" ? byId : window.byId,
      commandEntryState,
      commandEntrySummary,
      commandResultDisplayMessage: typeof commandResultDisplayMessage === "function" ? commandResultDisplayMessage : window.commandResultDisplayMessage,
      jsonDetailText,
      latestCommandEntry,
      launchCommandCorrelationRows: typeof launchCommandCorrelationRows === "function" ? launchCommandCorrelationRows : window.launchCommandCorrelationRows,
      launchCommandCorrelationStatus: typeof launchCommandCorrelationStatus === "function" ? launchCommandCorrelationStatus : window.launchCommandCorrelationStatus,
      launchCommandDiagnosticsActions: typeof launchCommandDiagnosticsActions === "function" ? launchCommandDiagnosticsActions : window.launchCommandDiagnosticsActions,
      launchPipelineIsActive,
      pipelineControllerStageSummary,
      pipelineControllerState,
      pipelineProgressIsStuck,
      pipelineProgressIsStale,
      setText: typeof setText === "function" ? setText : window.setText,
      state: launchCoordinatorState,
    })
    : {};
  const {
    setPipelineControlMessage = function (message) { setText("control-status", message); setText("home-control-message", message); },
    setPipelineSingleFileBrowseStatus = function (message) { setText("pipeline-single-file-browse-status", message); },
    renderPipelineControllerStatus = function () {},
    setStartupBanner = function () {},
    clearStartupBanner = function () {},
    launchCommandStatusLabel = function (result, successLabel = "Started") { return result?.ok ? successLabel : result?.severity || "Blocked"; },
    launchCommandResultCorrelationLines = function () { return []; },
    formatLaunchCommandDetail = function (result) { return String(result?.message || ""); },
    renderLaunchCommandResult = function (statusId, detailId, result) { setText(statusId, launchCommandStatusLabel(result)); if (detailId) setText(detailId, formatLaunchCommandDetail(result)); },
  } = launchStatusRender;

  const launchScopeControlsModule = window.__launchScopeControlsModule || {};
  delete window.__launchScopeControlsModule;
  const launchScopeControls = typeof launchScopeControlsModule.createLaunchScopeControlsModule === "function"
    ? launchScopeControlsModule.createLaunchScopeControlsModule({
      byId: typeof byId === "function" ? byId : window.byId,
      onControlsChanged: function () { updateLaunchCommandButtonStates(); },
      renderAllLaunchPreflights: function () { renderAllLaunchPreflights(); },
      setPipelineSingleFileBrowseStatus,
      state: launchCoordinatorState,
    })
    : {};
  const {
    pipelineSingleFileValue = function () { return String(byId("pipeline-start-single-file")?.value || "").trim(); },
    pipelineModeLabel = function (mode) { return mode || "Pipeline"; },
    syncPipelineScopeControls = function () {},
    selectPipelineScopePreset = function () {},
    syncPipelineModeControls = function () {},
    selectPipelineModePreset = function () {},
  } = launchScopeControls;

  const launchCommandButtonsModule = window.__launchCommandButtonsModule || {};
  delete window.__launchCommandButtonsModule;
  const launchCommandButtons = typeof launchCommandButtonsModule.createLaunchCommandButtonsModule === "function"
    ? launchCommandButtonsModule.createLaunchCommandButtonsModule({
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      clearStartupBanner,
      collectPipelineStartRequest,
      collectRerunStartRequest,
      launchBackendPreflightOverallStatus: (...args) => launchBackendPreflightOverallStatus(...args),
      launchBackendPreflightPayloadForTarget: (...args) => launchBackendPreflightPayloadForTarget(...args),
      launchBackendPreflightRows: (...args) => launchBackendPreflightRows(...args),
      launchPauseRequested,
      launchPipelineIsActive,
      launchPreflightRequestMatches,
      launchStartDecisionPostureFromStatus: (...args) => launchStartDecisionPostureFromStatus(...args),
      launchStartDecisionRows: (...args) => launchStartDecisionRows(...args),
      launchStartDecisionStatus: (...args) => launchStartDecisionStatus(...args),
      launchStartDecisionWorstPosture: (...args) => launchStartDecisionWorstPosture(...args),
      pipelineProgressIsStuck,
      pipelineProgressIsStale,
      pipelineSingleFileValue,
      renderPipelineControllerStatus,
      setPipelineControlMessage,
      setText: typeof setText === "function" ? setText : window.setText,
      syncPipelineScopeControls,
      state: launchCoordinatorState,
    })
    : {};
  const {
    controlActionLabels = { pause: "Pause / Resume", rescan: "Rescan", stop: "Stop After Current", kill: "Force Stop" },
    updateLaunchCommandButtonStates = function () {},
    setLaunchCommandBusy = function (isBusy) { launchCoordinatorState.launchCommandInFlight = isBusy; },
    setLaunchCommandButtonState = function () {},
    rejectLaunchCommandWhileBusy = function () { return false; },
    setControlCommandBusy = function (isBusy) { launchCoordinatorState.controlCommandInFlight = isBusy; },
    rejectControlCommandWhileBusy = function () { return false; },
    confirmControlAction = function () { return true; },
    nextLaunchCommandFrame = async function () {},
  } = launchCommandButtons;

  function launchTabIds() {
    return ["pipeline", "rerun", "history", "readiness"];
  }

  function activateLaunchTab(tabId, options = {}) {
    const page = document.querySelector('[data-page-panel="launch"]');
    if (!page) return;
    const selected = launchTabIds().includes(tabId) ? tabId : "pipeline";
    const persist = options?.persist !== false;
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-launch-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .launch-tab-panel[data-launch-tab-panel]"));
    buttons.forEach((button) => {
      const active = button.dataset.launchTab === selected;
      button.setAttribute("aria-selected", String(active));
    });
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.launchTabPanel === selected);
    });
    if (persist) {
      try { localStorage.setItem(LAUNCH_TAB_STORAGE_KEY, selected); } catch (_) {}
    }
    if (typeof window.mediaPipelineAppLifecycle?.syncTabAccessibility === "function") window.mediaPipelineAppLifecycle.syncTabAccessibility();
    if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
  }

  function initLaunchTabNav() {
    const page = document.querySelector('[data-page-panel="launch"]');
    if (!page) return;
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-launch-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .launch-tab-panel[data-launch-tab-panel]"));
    if (!buttons.length || !panels.length) return;
    buttons.forEach((button) => {
      button.addEventListener("click", () => activateLaunchTab(button.dataset.launchTab || "pipeline"));
    });
    let stored = "pipeline";
    try { stored = localStorage.getItem(LAUNCH_TAB_STORAGE_KEY) || "pipeline"; } catch (_) {}
    activateLaunchTab(stored);
  }

  document.addEventListener("click", (event) => {
    const button = event.target?.closest?.('[data-page-panel="launch"] .settings-tab-btn[data-launch-tab]');
    if (!button) return;
    activateLaunchTab(button.dataset.launchTab || "pipeline");
  });

  const launchRiskState = {
    get selectedLaunchSettingsRiskKey() {
      return selectedLaunchSettingsRiskKey;
    },
    set selectedLaunchSettingsRiskKey(value) {
      selectedLaunchSettingsRiskKey = value || "";
    },
    get selectedLaunchPolicyBoundaryKey() {
      return selectedLaunchPolicyBoundaryKey;
    },
    set selectedLaunchPolicyBoundaryKey(value) {
      selectedLaunchPolicyBoundaryKey = value || "";
    },
    get selectedLaunchSettingsIntentKey() {
      return selectedLaunchSettingsIntentKey;
    },
    set selectedLaunchSettingsIntentKey(value) {
      selectedLaunchSettingsIntentKey = value || "";
    },
  };

  const launchRiskModule = window.__launchViewRiskModule || {};
  delete window.__launchViewRiskModule;
  const launchRiskFallbackRows = function () { return []; };
  const launchRiskFallbackLines = function () { return []; };
  const launchRiskFallbackStatus = function () { return "Unknown"; };
  const launchRiskFallbackWorkspace = function () { return {}; };
  const launchRiskFallbackPayload = function (payload = null) { return payload && typeof payload === "object" ? payload : {}; };
  const launchRiskFallbackRender = function () {};
  const launchRisk = typeof launchRiskModule.createLaunchRiskModule === "function"
    ? launchRiskModule.createLaunchRiskModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      activateLaunchTab: (...args) => activateLaunchTab(...args),
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      collectPipelineStartRequest: (...args) => collectPipelineStartRequest(...args),
      formatSettingsChoiceLabel: typeof window.formatSettingsChoiceLabel === "function" ? window.formatSettingsChoiceLabel : (typeof formatSettingsChoiceLabel === "function" ? formatSettingsChoiceLabel : null),
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastLaunchReadinessPayload: typeof window.getLastLaunchReadinessPayload === "function" ? () => window.getLastLaunchReadinessPayload() : (typeof getLastLaunchReadinessPayload === "function" ? () => getLastLaunchReadinessPayload() : () => ({})),
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : () => []),
      getLastSettings: typeof window.getLastSettings === "function" ? () => window.getLastSettings() : (typeof getLastSettings === "function" ? () => getLastSettings() : () => ({})),
      isLaunchCommand,
      launchHistoryLine: typeof launchHistoryLine === "function" ? launchHistoryLine : window.launchHistoryLine,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pipelineModeLabel,
      queueCurrentFilterScope: typeof window.queueCurrentFilterScope === "function" ? window.queueCurrentFilterScope : (typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope : null),
      queueFilterScopeDetailLines: typeof window.queueFilterScopeDetailLines === "function" ? window.queueFilterScopeDetailLines : (typeof queueFilterScopeDetailLines === "function" ? queueFilterScopeDetailLines : null),
      scheduleDisplayValue: typeof scheduleDisplayValue === "function" ? scheduleDisplayValue : window.scheduleDisplayValue,
      setText: typeof setText === "function" ? setText : window.setText,
      settingsCommandHistoryLine: typeof window.mediaPipelineSettingsCommandHistory?.settingsCommandHistoryLine === "function" ? window.mediaPipelineSettingsCommandHistory.settingsCommandHistoryLine : null,
      settingsLaunchImpactRows: typeof window.settingsLaunchImpactRows === "function" ? window.settingsLaunchImpactRows : (typeof settingsLaunchImpactRows === "function" ? settingsLaunchImpactRows : null),
      settingsLaunchImpactStatus: typeof window.settingsLaunchImpactStatus === "function" ? window.settingsLaunchImpactStatus : (typeof settingsLaunchImpactStatus === "function" ? settingsLaunchImpactStatus : null),
      settingsOperatorTrustStatus: typeof window.settingsOperatorTrustStatus === "function" ? window.settingsOperatorTrustStatus : (typeof settingsOperatorTrustStatus === "function" ? settingsOperatorTrustStatus : null),
      settingsPatchEffectiveChangedEntries: typeof window.settingsPatchEffectiveChangedEntries === "function" ? window.settingsPatchEffectiveChangedEntries : (typeof settingsPatchEffectiveChangedEntries === "function" ? settingsPatchEffectiveChangedEntries : null),
      settingsPatchIsTouched: typeof window.settingsPatchIsTouched === "function" ? window.settingsPatchIsTouched : (typeof settingsPatchIsTouched === "function" ? settingsPatchIsTouched : null),
      settingsPolicyDeltaRows: typeof window.settingsPolicyDeltaRows === "function" ? window.settingsPolicyDeltaRows : (typeof settingsPolicyDeltaRows === "function" ? settingsPolicyDeltaRows : null),
      settingsPolicyDeltaStatus: typeof window.settingsPolicyDeltaStatus === "function" ? window.settingsPolicyDeltaStatus : (typeof settingsPolicyDeltaStatus === "function" ? settingsPolicyDeltaStatus : null),
      state: launchRiskState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    launchSettingsWorkspace = launchRiskFallbackWorkspace,
    launchSettingsTrustStatus = launchRiskFallbackStatus,
    launchSettingsDecision = function () { return { decision: "unknown", status: "Unknown", mode: "unknown", reasons: [], guidance: "Launch settings risk module is unavailable." }; },
    launchSettingsDecisionLines = launchRiskFallbackLines,
    launchUnsavedSettingsPatchLines = launchRiskFallbackLines,
    launchSettingsRiskLines = launchRiskFallbackLines,
    launchRealMediaReadinessLines = launchRiskFallbackLines,
    launchSettingsRiskRows = launchRiskFallbackRows,
    launchSettingsRiskStatus = launchRiskFallbackStatus,
    launchSettingsRiskSummaryLines = launchRiskFallbackLines,
    launchSettingsRiskDetailLines = launchRiskFallbackLines,
    renderLaunchSettingsRiskHandoff = launchRiskFallbackRender,
    launchPolicyBoundaryRows = launchRiskFallbackRows,
    launchPolicyBoundaryStatus = launchRiskFallbackStatus,
    launchPolicyBoundarySummaryLines = launchRiskFallbackLines,
    launchPolicyBoundaryDetailLines = launchRiskFallbackLines,
    renderLaunchPolicyBoundary = launchRiskFallbackRender,
    launchSettingsIntentPayload = launchRiskFallbackPayload,
    launchSettingsIntentLatestCommand = function () { return null; },
    launchSettingsIntentCommandLine = function () { return "No matching command is visible in recent command history."; },
    launchSettingsIntentRows = launchRiskFallbackRows,
    launchSettingsIntentStatus = launchRiskFallbackStatus,
    launchSettingsIntentSummaryLines = launchRiskFallbackLines,
    launchSettingsIntentDetailLines = launchRiskFallbackLines,
    renderLaunchSettingsIntentChecklist = launchRiskFallbackRender,
  } = launchRisk;

  const launchPreflightFallbackRows = function () { return []; };
  const launchPreflightFallbackLines = function () { return []; };
  const launchPreflightFallbackStatus = function () { return "Unknown"; };
  const launchPreflightFallbackRender = function () {};
  let launchPilotReadinessContext = function (context = lastLaunchRealMediaProofContext) { return context && typeof context === "object" ? context : {}; };
  let launchPilotPathFromRow = function (row) { return row?.source_path || row?.path || row?.file || row?.input_path || ""; };
  let launchPilotRowLabel = function (row) { return row?.display_name || row?.relative_path || row?.source_path || row?.path || row?.file || ""; };
  let launchPilotRunReadinessRows = launchPreflightFallbackRows;
  let launchPilotRunReadinessStatus = launchPreflightFallbackStatus;
  let launchPilotRunReadinessSummaryLines = launchPreflightFallbackLines;
  let launchPilotRunReadinessDetailLines = launchPreflightFallbackLines;
  let renderLaunchPilotRunReadiness = launchPreflightFallbackRender;
  let launchBackendPreflightOverallStatus = function () { return "Not loaded"; };
  let launchBackendPreflightStatusState = function () { return "unknown"; };
  let launchBackendPreflightRows = launchPreflightFallbackRows;
  let getLastLaunchBackendPreflightPayloads = launchPreflightFallbackRows;
  let launchBackendPreflightPayloadForTarget = function () { return null; };
  let getLastLaunchBackendPreflightRefreshInfo = function () { return { loaded_at: "", request_count: 0, payload_count: 0, fetch_failure_count: 0 }; };
  let launchBackendPreflightSummaryLines = launchPreflightFallbackLines;
  let launchBackendPreflightDetailLines = launchPreflightFallbackLines;
  let renderLaunchBackendPreflight = launchPreflightFallbackRender;
  let refreshLaunchBackendPreflight = async function () {};
  let pipelineLaunchPreflightLines = launchPreflightFallbackLines;
  let rerunLaunchPreflightLines = launchPreflightFallbackLines;
  let renderLaunchPreflight = function (id, lines) { setText(id, (lines || []).join("\n")); };
  let renderAllLaunchPreflights = launchPreflightFallbackRender;
  let isPipelineControlCommand = function (entry) { return String(entry?.command || "").toLowerCase().startsWith("pipeline.control."); };
  let pipelineControlHistoryLine = function (entry) { return String(entry?.message || entry?.command || "pipeline.control"); };
  let renderPipelineControlHistory = launchPreflightFallbackRender;

  function pipelineControlHistoryEntries(history = []) {
    return Array.isArray(history) ? history.filter(isPipelineControlCommand) : [];
  }

  function renderPipelineControlLatest(history = []) {
    const entries = pipelineControlHistoryEntries(history);
    const latest = entries[0] || null;
    if (!latest) {
      setText("control-latest", "No pipeline control command in recent history.");
      return;
    }
    setText("control-latest", pipelineControlHistoryLine(latest));
  }

  function renderLaunchLatestCommandEvidence(history = []) {
    const entries = Array.isArray(history) ? history : [];
    const latest = entries.find((entry) => isLaunchCommand(entry)) || null;
    if (!latest) {
      setText("launch-latest-command-evidence", "No Launch command result loaded. Pipeline, CSV rerun, and Pending Publish command results will appear here immediately after submission or cancellation.");
      return;
    }
    const line = typeof launchHistoryLine === "function"
      ? launchHistoryLine(latest)
      : commandEntrySummary(latest, "Launch command recorded.");
    setText("launch-latest-command-evidence", [
      "Latest Launch command:",
      line,
      "Full command journal and correlation details remain in the History subtab.",
    ].join("\n"));
  }

  function renderPipelineControlJournal(history = [], renderFullHistory = null) {
    renderLaunchLatestCommandEvidence(history);
    renderPipelineControlLatest(history);
    if (typeof renderFullHistory === "function") renderFullHistory(history);
    renderPipelineControllerStatus();
  }

  const launchScopeState = {
    get selectedLaunchScopeReconciliationKey() {
      return selectedLaunchScopeReconciliationKey;
    },
    set selectedLaunchScopeReconciliationKey(value) {
      selectedLaunchScopeReconciliationKey = value || "";
    },
    get selectedLaunchStartDecisionKey() {
      return selectedLaunchStartDecisionKey;
    },
    set selectedLaunchStartDecisionKey(value) {
      selectedLaunchStartDecisionKey = value || "";
    },
    get selectedLaunchCompactGateKey() {
      return selectedLaunchCompactGateKey;
    },
    set selectedLaunchCompactGateKey(value) {
      selectedLaunchCompactGateKey = value || "";
    },
  };

  const launchScopeModule = window.__launchViewScopeModule || {};
  delete window.__launchViewScopeModule;
  const launchScopeFallbackRows = function () { return []; };
  const launchScopeFallbackLines = function () { return []; };
  const launchScopeFallbackStatus = function () { return "Unknown"; };
  const launchScopeFallbackRender = function () {};
  const launchScope = typeof launchScopeModule.createLaunchScopeModule === "function"
    ? launchScopeModule.createLaunchScopeModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      collectPipelineStartRequest: (...args) => collectPipelineStartRequest(...args),
      commandHistoryIssueLevel: typeof window.commandHistoryIssueLevel === "function" ? window.commandHistoryIssueLevel : (typeof commandHistoryIssueLevel === "function" ? commandHistoryIssueLevel : null),
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastLaunchBackendPreflightPayloads: () => getLastLaunchBackendPreflightPayloads(),
      getLastLaunchBackendPreflightRefreshInfo: () => getLastLaunchBackendPreflightRefreshInfo() || {},
      getLastQueuePayload: typeof window.getLastQueuePayload === "function" ? () => window.getLastQueuePayload() : (typeof getLastQueuePayload === "function" ? () => getLastQueuePayload() : () => null),
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : () => []),
      getLaunchRealMediaContext: () => lastLaunchRealMediaProofContext || {},
      isLaunchCommand,
      launchBackendPreflightOverallStatus: (...args) => launchBackendPreflightOverallStatus(...args),
      launchBackendPreflightPayloadForTarget: (...args) => launchBackendPreflightPayloadForTarget(...args),
      launchBackendPreflightRows: (...args) => launchBackendPreflightRows(...args),
      launchBackendPreflightStatusState: (...args) => launchBackendPreflightStatusState(...args),
      launchBackendPreflightSummaryLines: (...args) => launchBackendPreflightSummaryLines(...args),
      launchCommandReviewRows: typeof window.launchCommandReviewRows === "function" ? window.launchCommandReviewRows : (typeof launchCommandReviewRows === "function" ? launchCommandReviewRows : null),
      launchCommandReviewStatus: typeof window.launchCommandReviewStatus === "function" ? window.launchCommandReviewStatus : (typeof launchCommandReviewStatus === "function" ? launchCommandReviewStatus : null),
      launchCommandReviewSummaryLines: typeof window.launchCommandReviewSummaryLines === "function" ? window.launchCommandReviewSummaryLines : (typeof launchCommandReviewSummaryLines === "function" ? launchCommandReviewSummaryLines : null),
      launchPolicyBoundaryRows: (...args) => launchPolicyBoundaryRows(...args),
      launchPolicyBoundaryStatus: (...args) => launchPolicyBoundaryStatus(...args),
      launchPolicyBoundarySummaryLines: (...args) => launchPolicyBoundarySummaryLines(...args),
      launchReadinessLines: typeof launchReadinessLines === "function" ? launchReadinessLines : null,
      launchReadinessStatus: typeof launchReadinessStatus === "function" ? launchReadinessStatus : null,
      launchRealMediaProofRows: (...args) => launchRealMediaProofRows(...args),
      launchRealMediaProofStatus: (...args) => launchRealMediaProofStatus(...args),
      launchRealMediaProofSummaryLines: (...args) => launchRealMediaProofSummaryLines(...args),
      launchRealMediaSample: (...args) => launchRealMediaSample(...args),
      launchSampleExecutionRows: (...args) => launchSampleExecutionRows(...args),
      launchSampleExecutionStatus: (...args) => launchSampleExecutionStatus(...args),
      launchSampleExecutionSummaryLines: (...args) => launchSampleExecutionSummaryLines(...args),
      launchSampleSetCoverageEvidence: (...args) => launchSampleSetCoverageEvidence(...args),
      launchSettingsIntentCommandLine: (...args) => launchSettingsIntentCommandLine(...args),
      launchSettingsIntentLatestCommand: (...args) => launchSettingsIntentLatestCommand(...args),
      launchSettingsIntentPayload: (...args) => launchSettingsIntentPayload(...args),
      launchSettingsIntentRows: (...args) => launchSettingsIntentRows(...args),
      launchSettingsIntentStatus: (...args) => launchSettingsIntentStatus(...args),
      launchSettingsIntentSummaryLines: (...args) => launchSettingsIntentSummaryLines(...args),
      launchSettingsWorkspace: (...args) => launchSettingsWorkspace(...args),
      launchTimingStatus: typeof launchTimingStatus === "function" ? launchTimingStatus : null,
      launchTimingTrustLines: typeof launchTimingTrustLines === "function" ? launchTimingTrustLines : null,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pipelineModeLabel,
      queueCurrentFilterScope: typeof window.queueCurrentFilterScope === "function" ? window.queueCurrentFilterScope : (typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope : null),
      queueFilterScopeDetailLines: typeof window.queueFilterScopeDetailLines === "function" ? window.queueFilterScopeDetailLines : (typeof queueFilterScopeDetailLines === "function" ? queueFilterScopeDetailLines : null),
      queueLaunchDecisionPostureStatus: typeof window.queueLaunchDecisionPostureStatus === "function" ? window.queueLaunchDecisionPostureStatus : (typeof queueLaunchDecisionPostureStatus === "function" ? queueLaunchDecisionPostureStatus : null),
      queueLaunchDecisionRows: typeof window.queueLaunchDecisionRows === "function" ? window.queueLaunchDecisionRows : (typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows : null),
      queueLaunchDecisionStatus: typeof window.queueLaunchDecisionStatus === "function" ? window.queueLaunchDecisionStatus : (typeof queueLaunchDecisionStatus === "function" ? queueLaunchDecisionStatus : null),
      queueLaunchDecisionSummaryLines: typeof window.queueLaunchDecisionSummaryLines === "function" ? window.queueLaunchDecisionSummaryLines : (typeof queueLaunchDecisionSummaryLines === "function" ? queueLaunchDecisionSummaryLines : null),
      scheduleDisplayValue: typeof scheduleDisplayValue === "function" ? scheduleDisplayValue : window.scheduleDisplayValue,
      scheduleWatcherSummary: typeof scheduleWatcherSummary === "function" ? scheduleWatcherSummary : window.scheduleWatcherSummary,
      setText: typeof setText === "function" ? setText : window.setText,
      showPage: typeof showPage === "function" ? showPage : window.showPage,
      activateLaunchTab: (...args) => activateLaunchTab(...args),
      state: launchScopeState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    launchScopeReconciliationRows = launchScopeFallbackRows,
    launchScopeReconciliationStatus = launchScopeFallbackStatus,
    launchScopeReconciliationSummaryLines = launchScopeFallbackLines,
    launchScopeReconciliationDetailLines = launchScopeFallbackLines,
    renderLaunchScopeReconciliation = launchScopeFallbackRender,
    launchStartDecisionPostureFromStatus = launchScopeFallbackStatus,
    launchStartDecisionWorstPosture = launchScopeFallbackStatus,
    launchStartDecisionRank = function () { return 0; },
    launchStartDecisionRowStatus = launchScopeFallbackStatus,
    launchStartDecisionRows = launchScopeFallbackRows,
    launchStartDecisionStatus = launchScopeFallbackStatus,
    launchStartDecisionSummaryLines = launchScopeFallbackLines,
    launchStartDecisionDetailLines = launchScopeFallbackLines,
    renderLaunchStartDecisionSummary = launchScopeFallbackRender,
    launchCompactGateRows = launchScopeFallbackRows,
    launchCompactGateOverallStatus = launchScopeFallbackStatus,
    renderLaunchCompactGate = launchScopeFallbackRender,
  } = launchScope;

  const launchRealMediaState = {
    get context() {
      return lastLaunchRealMediaProofContext;
    },
    set context(value) {
      lastLaunchRealMediaProofContext = value && typeof value === "object" ? value : {};
    },
    get selectedLaunchRealMediaProofKey() {
      return selectedLaunchRealMediaProofKey;
    },
    set selectedLaunchRealMediaProofKey(value) {
      selectedLaunchRealMediaProofKey = value || "";
    },
    get selectedLaunchSampleExecutionKey() {
      return selectedLaunchSampleExecutionKey;
    },
    set selectedLaunchSampleExecutionKey(value) {
      selectedLaunchSampleExecutionKey = value || "";
    },
  };

  const launchRealMediaModule = window.__launchViewRealMediaModule || {};
  delete window.__launchViewRealMediaModule;
  const launchRealMediaFallbackRows = function () { return []; };
  const launchRealMediaFallbackLines = function () { return []; };
  const launchRealMediaFallbackStatus = function () { return "Unknown"; };
  const launchRealMediaFallbackObject = function () { return {}; };
  const launchRealMediaFallbackRender = function () {};
  const launchRealMedia = typeof launchRealMediaModule.createLaunchRealMediaModule === "function"
    ? launchRealMediaModule.createLaunchRealMediaModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : null),
      getSelectedQueueRow: typeof window.getSelectedQueueRow === "function" ? () => window.getSelectedQueueRow() : (typeof getSelectedQueueRow === "function" ? () => getSelectedQueueRow() : null),
      launchPilotPathFromRow: (...args) => launchPilotPathFromRow(...args),
      launchPilotReadinessContext: (...args) => launchPilotReadinessContext(...args),
      launchPilotRowLabel: (...args) => launchPilotRowLabel(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      renderLaunchPilotRunReadiness: (...args) => renderLaunchPilotRunReadiness(...args),
      renderLaunchStartDecisionSummary: (...args) => renderLaunchStartDecisionSummary(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      state: launchRealMediaState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    launchRealMediaSample = launchRealMediaFallbackObject,
    launchWorksheetEvidence = launchRealMediaFallbackObject,
    launchWorksheetRunRows = launchRealMediaFallbackRows,
    launchWorksheetRunsMatchingSample = launchRealMediaFallbackRows,
    launchPolicyAlignmentPayload = launchRealMediaFallbackObject,
    launchPolicyAlignmentRows = launchRealMediaFallbackRows,
    launchQueueIntentCategoryMatch = launchRealMediaFallbackStatus,
    launchPolicyAlignmentQueueIntentEvidence = launchRealMediaFallbackObject,
    launchSampleSetCoverageEvidence = launchRealMediaFallbackObject,
    launchSampleSetCoverageLine = function () { return "Pilot category coverage: not loaded"; },
    launchSampleValidationRecordEvidence = launchRealMediaFallbackObject,
    launchSampleValidationRecordRows = launchRealMediaFallbackRows,
    launchSampleValidationRecordsMatchingSample = launchRealMediaFallbackRows,
    launchRealMediaProofRows = launchRealMediaFallbackRows,
    launchRealMediaProofStatus = launchRealMediaFallbackStatus,
    launchRealMediaProofSummaryLines = launchRealMediaFallbackLines,
    launchRealMediaProofDetailLines = launchRealMediaFallbackLines,
    renderLaunchRealMediaProofHandoff = launchRealMediaFallbackRender,
    launchSampleExecutionRows = launchRealMediaFallbackRows,
    launchSampleExecutionStatus = launchRealMediaFallbackStatus,
    launchSampleExecutionSummaryLines = launchRealMediaFallbackLines,
    launchSampleExecutionDetailLines = launchRealMediaFallbackLines,
    renderLaunchSampleExecutionChecklist = launchRealMediaFallbackRender,
  } = launchRealMedia;

  const launchPreflightModule = window.__launchViewPreflightModule || {};
  delete window.__launchViewPreflightModule;
  const launchPreflight = typeof launchPreflightModule.createLaunchPreflightModule === "function"
    ? launchPreflightModule.createLaunchPreflightModule({
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      collectPipelineStartRequest: (...args) => collectPipelineStartRequest(...args),
      collectRerunStartRequest: (...args) => collectRerunStartRequest(...args),
      commandHistoryCompactEvidenceLine: typeof window.commandHistoryCompactEvidenceLine === "function" ? window.commandHistoryCompactEvidenceLine : (typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null),
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastQueuePayload: typeof window.getLastQueuePayload === "function" ? () => window.getLastQueuePayload() : (typeof getLastQueuePayload === "function" ? () => getLastQueuePayload() : () => null),
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : () => []),
      getLastSnapshot: typeof window.getLastSnapshot === "function" ? () => window.getLastSnapshot() : () => null,
      getSelectedQueueRow: typeof window.getSelectedQueueRow === "function" ? () => window.getSelectedQueueRow() : (typeof getSelectedQueueRow === "function" ? () => getSelectedQueueRow() : () => null),
      launchPolicyAlignmentQueueIntentEvidence: (...args) => launchPolicyAlignmentQueueIntentEvidence(...args),
      launchPreflightRequestMatches,
      launchPolicyBoundaryRows: (...args) => launchPolicyBoundaryRows(...args),
      launchPolicyBoundaryStatus: (...args) => launchPolicyBoundaryStatus(...args),
      launchRealMediaProofRows: (...args) => launchRealMediaProofRows(...args),
      launchRealMediaProofStatus: (...args) => launchRealMediaProofStatus(...args),
      launchRealMediaProofSummaryLines: (...args) => launchRealMediaProofSummaryLines(...args),
      launchRealMediaReadinessLines: (...args) => launchRealMediaReadinessLines(...args),
      launchRealMediaSample: (...args) => launchRealMediaSample(...args),
      launchSampleExecutionRows: (...args) => launchSampleExecutionRows(...args),
      launchSampleExecutionStatus: (...args) => launchSampleExecutionStatus(...args),
      launchSampleExecutionSummaryLines: (...args) => launchSampleExecutionSummaryLines(...args),
      launchSampleSetCoverageEvidence: (...args) => launchSampleSetCoverageEvidence(...args),
      launchSettingsDecisionLines: (...args) => launchSettingsDecisionLines(...args),
      launchSettingsIntentPayload: (...args) => launchSettingsIntentPayload(...args),
      launchSettingsIntentRows: (...args) => launchSettingsIntentRows(...args),
      launchSettingsIntentStatus: (...args) => launchSettingsIntentStatus(...args),
      launchSettingsRiskLines: (...args) => launchSettingsRiskLines(...args),
      launchSettingsTrustStatus: (...args) => launchSettingsTrustStatus(...args),
      launchSettingsWorkspace: (...args) => launchSettingsWorkspace(...args),
      launchStartDecisionPostureFromStatus: (...args) => launchStartDecisionPostureFromStatus(...args),
      launchStartDecisionRank: (...args) => launchStartDecisionRank(...args),
      launchStartDecisionRowStatus: (...args) => launchStartDecisionRowStatus(...args),
      launchStartDecisionWorstPosture: (...args) => launchStartDecisionWorstPosture(...args),
      launchUnsavedSettingsPatchLines: (...args) => launchUnsavedSettingsPatchLines(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pipelineModeLabel,
      queueLaunchDecisionRows: typeof window.queueLaunchDecisionRows === "function" ? window.queueLaunchDecisionRows : (typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows : null),
      queueLaunchDecisionStatus: typeof window.queueLaunchDecisionStatus === "function" ? window.queueLaunchDecisionStatus : (typeof queueLaunchDecisionStatus === "function" ? queueLaunchDecisionStatus : null),
      renderLaunchPolicyBoundary: (...args) => renderLaunchPolicyBoundary(...args),
      renderLaunchRealMediaProofHandoff: (...args) => renderLaunchRealMediaProofHandoff(...args),
      renderLaunchScopeReconciliation: (...args) => renderLaunchScopeReconciliation(...args),
      renderLaunchSettingsIntentChecklist: (...args) => renderLaunchSettingsIntentChecklist(...args),
      renderLaunchSettingsRiskHandoff: (...args) => renderLaunchSettingsRiskHandoff(...args),
      renderLaunchStartDecisionSummary: (...args) => renderLaunchStartDecisionSummary(...args),
      renderLaunchTimingTrust: typeof window.renderLaunchTimingTrust === "function" ? window.renderLaunchTimingTrust : (typeof renderLaunchTimingTrust === "function" ? renderLaunchTimingTrust : null),
      renderQueueLaunchDecisionChecklist: typeof window.renderQueueLaunchDecisionChecklist === "function" ? window.renderQueueLaunchDecisionChecklist : (typeof renderQueueLaunchDecisionChecklist === "function" ? renderQueueLaunchDecisionChecklist : null),
      renderScheduleTimingTrust: typeof window.renderScheduleTimingTrust === "function" ? window.renderScheduleTimingTrust : (typeof renderScheduleTimingTrust === "function" ? renderScheduleTimingTrust : null),
      setText: typeof setText === "function" ? setText : window.setText,
      state: launchRealMediaState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  launchPilotReadinessContext = typeof launchPreflight.launchPilotReadinessContext === "function" ? launchPreflight.launchPilotReadinessContext : launchPilotReadinessContext;
  launchPilotPathFromRow = typeof launchPreflight.launchPilotPathFromRow === "function" ? launchPreflight.launchPilotPathFromRow : launchPilotPathFromRow;
  launchPilotRowLabel = typeof launchPreflight.launchPilotRowLabel === "function" ? launchPreflight.launchPilotRowLabel : launchPilotRowLabel;
  launchPilotRunReadinessRows = typeof launchPreflight.launchPilotRunReadinessRows === "function" ? launchPreflight.launchPilotRunReadinessRows : launchPilotRunReadinessRows;
  launchPilotRunReadinessStatus = typeof launchPreflight.launchPilotRunReadinessStatus === "function" ? launchPreflight.launchPilotRunReadinessStatus : launchPilotRunReadinessStatus;
  launchPilotRunReadinessSummaryLines = typeof launchPreflight.launchPilotRunReadinessSummaryLines === "function" ? launchPreflight.launchPilotRunReadinessSummaryLines : launchPilotRunReadinessSummaryLines;
  launchPilotRunReadinessDetailLines = typeof launchPreflight.launchPilotRunReadinessDetailLines === "function" ? launchPreflight.launchPilotRunReadinessDetailLines : launchPilotRunReadinessDetailLines;
  renderLaunchPilotRunReadiness = typeof launchPreflight.renderLaunchPilotRunReadiness === "function" ? launchPreflight.renderLaunchPilotRunReadiness : renderLaunchPilotRunReadiness;
  launchBackendPreflightOverallStatus = typeof launchPreflight.launchBackendPreflightOverallStatus === "function" ? launchPreflight.launchBackendPreflightOverallStatus : launchBackendPreflightOverallStatus;
  launchBackendPreflightStatusState = typeof launchPreflight.launchBackendPreflightStatusState === "function" ? launchPreflight.launchBackendPreflightStatusState : launchBackendPreflightStatusState;
  launchBackendPreflightRows = typeof launchPreflight.launchBackendPreflightRows === "function" ? launchPreflight.launchBackendPreflightRows : launchBackendPreflightRows;
  getLastLaunchBackendPreflightPayloads = typeof launchPreflight.getLastLaunchBackendPreflightPayloads === "function" ? launchPreflight.getLastLaunchBackendPreflightPayloads : getLastLaunchBackendPreflightPayloads;
  launchBackendPreflightPayloadForTarget = typeof launchPreflight.launchBackendPreflightPayloadForTarget === "function" ? launchPreflight.launchBackendPreflightPayloadForTarget : launchBackendPreflightPayloadForTarget;
  getLastLaunchBackendPreflightRefreshInfo = typeof launchPreflight.getLastLaunchBackendPreflightRefreshInfo === "function" ? launchPreflight.getLastLaunchBackendPreflightRefreshInfo : getLastLaunchBackendPreflightRefreshInfo;
  launchBackendPreflightSummaryLines = typeof launchPreflight.launchBackendPreflightSummaryLines === "function" ? launchPreflight.launchBackendPreflightSummaryLines : launchBackendPreflightSummaryLines;
  launchBackendPreflightDetailLines = typeof launchPreflight.launchBackendPreflightDetailLines === "function" ? launchPreflight.launchBackendPreflightDetailLines : launchBackendPreflightDetailLines;
  renderLaunchBackendPreflight = typeof launchPreflight.renderLaunchBackendPreflight === "function" ? launchPreflight.renderLaunchBackendPreflight : renderLaunchBackendPreflight;
  refreshLaunchBackendPreflight = typeof launchPreflight.refreshLaunchBackendPreflight === "function" ? launchPreflight.refreshLaunchBackendPreflight : refreshLaunchBackendPreflight;
  pipelineLaunchPreflightLines = typeof launchPreflight.pipelineLaunchPreflightLines === "function" ? launchPreflight.pipelineLaunchPreflightLines : pipelineLaunchPreflightLines;
  rerunLaunchPreflightLines = typeof launchPreflight.rerunLaunchPreflightLines === "function" ? launchPreflight.rerunLaunchPreflightLines : rerunLaunchPreflightLines;
  renderLaunchPreflight = typeof launchPreflight.renderLaunchPreflight === "function" ? launchPreflight.renderLaunchPreflight : renderLaunchPreflight;
  renderAllLaunchPreflights = typeof launchPreflight.renderAllLaunchPreflights === "function" ? launchPreflight.renderAllLaunchPreflights : renderAllLaunchPreflights;
  isPipelineControlCommand = typeof launchPreflight.isPipelineControlCommand === "function" ? launchPreflight.isPipelineControlCommand : isPipelineControlCommand;
  pipelineControlHistoryLine = typeof launchPreflight.pipelineControlHistoryLine === "function" ? launchPreflight.pipelineControlHistoryLine : pipelineControlHistoryLine;
  {
    const renderPipelineControlFullHistory = typeof launchPreflight.renderPipelineControlHistory === "function" ? launchPreflight.renderPipelineControlHistory : renderPipelineControlHistory;
    renderPipelineControlHistory = (history = []) => renderPipelineControlJournal(history, renderPipelineControlFullHistory);
  }
  {
    const renderAllLaunchPreflightDetails = renderAllLaunchPreflights;
    renderAllLaunchPreflights = (...args) => {
      const result = renderAllLaunchPreflightDetails(...args);
      renderLaunchCompactGate();
      return result;
    };
  }

  function initLaunchViewEvents() {
    initLaunchTabNav();
    const refreshLaunchControlsForInput = () => {
      syncPipelineModeControls();
      renderAllLaunchPreflights();
      updateLaunchCommandButtonStates();
    };
    document.querySelectorAll("[data-pipeline-mode-preset]").forEach((button) => {
      button.addEventListener("click", () => selectPipelineModePreset(button.dataset.pipelineModePreset || ""));
    });
    document.querySelectorAll("[data-pipeline-scope-preset]").forEach((button) => {
      button.addEventListener("click", () => selectPipelineScopePreset(button.dataset.pipelineScopePreset || ""));
    });
    [
      "pipeline-start-mode",
      "pipeline-start-single-file",
      "pipeline-start-sleep",
      "pipeline-start-schedule-override",
      "pipeline-start-show-config",
      "pipeline-start-show-console",
      "rerun-start-csv-path",
      "rerun-start-show-console",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", refreshLaunchControlsForInput);
      element.addEventListener("change", refreshLaunchControlsForInput);
    });
    ["launch-backend-preflight-refresh-button", "pipeline-compact-gate-refresh-button"].forEach((id) => {
      const backendPreflightRefresh = byId(id);
      if (!backendPreflightRefresh) return;
      backendPreflightRefresh.addEventListener("click", async () => {
        await refreshLaunchBackendPreflight();
        renderLaunchCompactGate();
        updateLaunchCommandButtonStates();
      });
    });
    const pipelineFileBrowseButton = byId("pipeline-single-file-browse-button");
    if (pipelineFileBrowseButton) {
      pipelineFileBrowseButton.addEventListener("click", () => browsePipelineSingleFile());
    }
    const pipelineFileClearButton = byId("pipeline-single-file-clear-button");
    if (pipelineFileClearButton) {
      pipelineFileClearButton.addEventListener("click", () => clearPipelineSingleFile());
    }
    initLaunchRecoveryActionEvents();
    renderAllLaunchPreflights();
    refreshLaunchBackendPreflight()
      .then(() => {
        renderLaunchCompactGate();
        updateLaunchCommandButtonStates();
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        setText("launch-backend-preflight-status", "Load failed");
        const statusNode = byId("launch-backend-preflight-status");
        if (statusNode) statusNode.dataset.state = "warning";
        setText("launch-backend-preflight-summary", [
          "Pipeline backend preflight did not load automatically.",
          `Error: ${message}`,
          "Action: refresh the backend preflight from Launch before starting the media pipeline.",
          "Mutation guardrail: automatic preflight loading is read-only and cannot launch, reserve locks, save settings, drain, rename, publish, or touch media files.",
        ].join("\n"));
        renderLaunchCompactGate();
        updateLaunchCommandButtonStates();
      });
    syncPipelineModeControls();
    updateLaunchCommandButtonStates();
  }

  function initLaunchRecoveryActionEvents() {
    const page = document.querySelector('[data-page-panel="launch"]') || document;
    if (!page || page.__launchRecoveryEventsBound === true) return;
    page.__launchRecoveryEventsBound = true;
    page.addEventListener("click", async (event) => {
      const button = event.target?.closest?.("[data-launch-recovery-action]");
      if (!button) return;
      event.preventDefault();
      const action = String(button.dataset.launchRecoveryAction || "").toLowerCase();
      if (action === "drain_pending_pushes") {
        await startPendingPublishDrain();
      } else if (action === "archive_state_journals") {
        await startStateJournalArchive(button);
      } else if (action === "pending_publish_recovery_plan") {
        if (typeof window.showPage === "function") window.showPage("pending");
        setText("launch-readiness-action-status", "Open Pending Publish and review the recovery plan before draining parked outputs.");
      }
    });
  }

  async function requestPipelineControl(action) {
    const normalized = String(action || "").trim().toLowerCase();
    if (rejectControlCommandWhileBusy(normalized || "unknown")) return;
    if (!normalized) {
      const result = {
        command: "pipeline.control.unknown",
        ok: false,
        severity: "error",
        message: "No pipeline control action was selected.",
      };
      appendCommandResult(result);
      setPipelineControlMessage(result.message);
      return;
    }
    setPipelineControlMessage(`Confirming ${controlActionLabels[normalized] || normalized}...`);
    document.querySelectorAll(`[data-control-action="${normalized}"]`).forEach((button) => {
      button.dataset.commandState = "confirming";
    });
    await nextLaunchCommandFrame();
    if (!confirmControlAction(normalized)) {
      const result = {
        command: `pipeline.control.${normalized}`,
        ok: false,
        severity: "info",
        message: `${controlActionLabels[normalized] || normalized} canceled.`,
      };
      appendCommandResult(result);
      setPipelineControlMessage(result.message);
      updateLaunchCommandButtonStates();
      return;
    }
    setControlCommandBusy(true);
    setPipelineControlMessage(`Sending ${controlActionLabels[normalized] || normalized}...`);
    try {
      const result = await apiPost("/api/pipeline/control", { action: normalized });
      appendCommandResult(result);
      setPipelineControlMessage(result.message || "Control request sent.");
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: `pipeline.control.${normalized}`,
        ok: false,
        severity: "error",
        message,
      });
      setPipelineControlMessage(`Control request failed: ${message}`);
    } finally {
      setControlCommandBusy(false);
    }
  }

  async function browsePipelineSingleFile() {
    if (pipelineFileBrowseInFlight || launchCommandInFlight) {
      setPipelineSingleFileBrowseStatus("Single-file browser is busy. Wait for the current Launch command to finish.");
      return;
    }
    if (launchPipelineIsActive()) {
      setPipelineSingleFileBrowseStatus("Single-file browser is disabled while backend work is active.");
      return;
    }
    const input = byId("pipeline-start-single-file");
    const initialPath = String(input?.value || "").trim();
    const request = { selection_mode: "files", initial_path: initialPath };
    pipelineStartScope = "single_file";
    pipelineFileBrowseInFlight = true;
    syncPipelineScopeControls();
    updateLaunchCommandButtonStates();
    setPipelineSingleFileBrowseStatus("Opening Windows file browser...");
    try {
      const result = await apiPost("/api/pipeline/browse-file", request);
      appendCommandResult(result);
      const data = result.data && typeof result.data === "object" ? result.data : {};
      const selectedPath = String(data.selected_path || "").trim();
      if (!result.ok) {
        setPipelineSingleFileBrowseStatus(result.message || "Windows file browser failed.");
        return;
      }
      if (data.canceled || !selectedPath) {
        setPipelineSingleFileBrowseStatus(result.message || "Windows file browser canceled. No Launch field was changed.");
        return;
      }
      if (input) {
        input.value = selectedPath;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      pipelineStartScope = "single_file";
      syncPipelineScopeControls();
      setPipelineSingleFileBrowseStatus(`Single file staged: ${selectedPath}`);
      renderAllLaunchPreflights();
      updateLaunchCommandButtonStates();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const routeMissing = String(message || "").trim().toLowerCase() === "not found";
      const displayMessage = routeMissing
        ? "Pipeline single-file browser route is not available in the running backend. Restart the Local API/Tauri shell, then open Launch again."
        : `Windows file browser failed:\n${message}`;
      appendCommandResult({
        command: "pipeline.browse_file",
        ok: false,
        severity: "error",
        message: displayMessage,
      });
      setPipelineSingleFileBrowseStatus(displayMessage);
    } finally {
      pipelineFileBrowseInFlight = false;
      updateLaunchCommandButtonStates();
    }
  }

  function clearPipelineSingleFile() {
    const input = byId("pipeline-start-single-file");
    if (input) {
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    pipelineStartScope = "queue";
    syncPipelineScopeControls();
    setPipelineSingleFileBrowseStatus("Single-file staging cleared.");
    renderAllLaunchPreflights();
    updateLaunchCommandButtonStates();
  }

  function pipelineStartConfirmMessage(request, label) {
    const scope = request?.single_file ? "Single File" : "Queue";
    const parts = [
      `Submit ${label} for ${scope}? Backend will re-check queue, settings, schedule, and locks before starting.`,
    ];
    if (String(request?.mode || "").toLowerCase() === "continuous") {
      parts.push("Continuous mode keeps requesting work until stopped or schedule policy blocks work.");
    }
    if (request?.schedule_override) {
      parts.push("Schedule override is selected for this submission.");
    }
    return parts.join("\n");
  }

  async function startPipelineFromForm() {
    if (rejectLaunchCommandWhileBusy("pipeline.start", "pipeline-launch-status", "pipeline-launch-detail")) return;
    const request = collectPipelineStartRequest();
    renderLaunchPreflight("pipeline-launch-preflight", pipelineLaunchPreflightLines(request));
    const label = pipelineModeLabel(request.mode);
    const startBtn = byId("pipeline-start-button");
    const startBtnText = startBtn ? startBtn.textContent : "";
    setLaunchCommandButtonState("pipeline-start-button", "confirming", "Confirming...");
    setText("pipeline-launch-status", "Confirming");
    setText("pipeline-launch-detail", pipelineStartConfirmMessage(request, label));
    await nextLaunchCommandFrame();
    if (!window.confirm(pipelineStartConfirmMessage(request, label))) {
      const canceled = {
        command: "pipeline.start",
        ok: false,
        severity: "info",
        message: `${label} canceled.`,
      };
      appendCommandResult(canceled);
      setText("pipeline-launch-status", "Canceled");
      setText("pipeline-launch-detail", canceled.message);
      if (startBtn) startBtn.textContent = startBtnText || "Start Pipeline";
      updateLaunchCommandButtonStates();
      return;
    }
    if (startBtn) startBtn.textContent = "Launching…";
    setLaunchCommandBusy(true);
    setStartupBanner("Spooling up tasks…");
    setText("pipeline-launch-status", "Starting...");
    renderJsonDetail("pipeline-launch-detail", {
      label: "Submitted request",
      value: request,
      intro: "Pipeline start request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/pipeline/start", request);
      appendCommandResult(result);
      renderLaunchCommandResult("pipeline-launch-status", "pipeline-launch-detail", result, request);
      if (result.ok) {
        const pidMatch = String(result.message || "").match(/\bPID\s*(\d+)\b/i);
        const pid = pidMatch ? pidMatch[1] : "";
        window.setTopbarPendingLaunch?.({ pid });
        setStartupBanner(pid
          ? `Pipeline starting — PID ${pid}. Waiting for first status update…`
          : "Pipeline starting. Waiting for first status update…"
        );
      }
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
      if (result.ok) {
        window.setTimeout(refreshAll, 2000);
        window.setTimeout(refreshAll, 6000);
        window.setTimeout(refreshAll, 12000);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "pipeline.start",
        ok: false,
        severity: "error",
        message,
      });
      renderLaunchCommandResult("pipeline-launch-status", "pipeline-launch-detail", {
        command: "pipeline.start",
        ok: false,
        severity: "error",
        message,
      }, request);
    } finally {
      setLaunchCommandBusy(false);
      if (startBtn) startBtn.textContent = startBtnText || "Start Pipeline";
      syncPipelineModeControls();
    }
  }

  async function startPendingPublishDrain() {
    if (rejectLaunchCommandWhileBusy("pending_publish.drain", "pending-drain-status", "pending-drain-detail")) return;
    const guard = typeof pendingDrainGuardState === "function" ? pendingDrainGuardState() : null;
    if (guard && guard.allowed === false) {
      const rejected = {
        command: "pending_publish.drain",
        ok: false,
        severity: "warning",
        message: guard.message || "Pending publish drain blocked by WebView evidence.",
        data: {
          frontend_guard: true,
          decision_status: guard.decision_status || "unknown",
        },
      };
      appendCommandResult(rejected);
      setText("pending-drain-status", "Blocked");
      setText("pending-drain-detail", typeof pendingDrainGuardLines === "function" ? pendingDrainGuardLines(guard).join("\n") : rejected.message);
      if (typeof renderPendingDrainGuard === "function") renderPendingDrainGuard();
      return;
    }
    const request = {
      mode: "drain_pending_pushes",
      sleep_seconds: 30,
      show_config: false,
      show_console: false,
      schedule_override: "",
    };
    const confirmMessage = guard?.confirm_message || "Publish parked pending outputs now?";
    const drainBtn = byId("pending-drain-button");
    const drainBtnText = drainBtn ? drainBtn.textContent : "";
    setLaunchCommandButtonState("pending-drain-button", "confirming", "Confirming...");
    setText("pending-drain-status", "Confirming");
    setText("pending-drain-detail", confirmMessage);
    await nextLaunchCommandFrame();
    if (!window.confirm(confirmMessage)) {
      const canceled = {
        command: "pending_publish.drain",
        ok: false,
        severity: "info",
        message: "Pending publish drain canceled.",
      };
      appendCommandResult(canceled);
      setText("pending-drain-status", "Canceled");
      setText("pending-drain-detail", canceled.message);
      if (drainBtn) drainBtn.textContent = drainBtnText || "Drain Parked Outputs";
      updateLaunchCommandButtonStates();
      return;
    }
    if (drainBtn) drainBtn.textContent = "Draining...";
    setLaunchCommandBusy(true);
    setText("pending-drain-status", "Draining...");
    renderJsonDetail("pending-drain-detail", {
      label: "Submitted request",
      value: request,
      intro: "Pending publish drain request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/pipeline/start", request);
      const drainResult = {
        ...result,
        command: "pending_publish.drain",
      };
      appendCommandResult(drainResult);
      renderLaunchCommandResult("pending-drain-status", "pending-drain-detail", drainResult, request);
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "pending_publish.drain",
        ok: false,
        severity: "error",
        message,
      });
      renderLaunchCommandResult("pending-drain-status", "pending-drain-detail", {
        command: "pending_publish.drain",
        ok: false,
        severity: "error",
        message,
      }, request);
    } finally {
      setLaunchCommandBusy(false);
      if (drainBtn) drainBtn.textContent = drainBtnText || "Drain Parked Outputs";
    }
  }

  async function startStateJournalArchive(sourceButton = null) {
    if (rejectLaunchCommandWhileBusy("maintenance.archive_state_journals", "launch-readiness-status", "launch-readiness-action-status")) return;
    const request = {
      confirm_archive: true,
      reason: "launch recovery",
    };
    const confirmMessage = [
      "Archive the oversized backend event journal now?",
      "The backend may only move State\\Progress\\pipeline_events.jsonl into ArchivedEvents and create a fresh empty replacement.",
      "Media, queue, pending publish, completed manifest, and final output files are not touched by this action.",
    ].join("\n");
    const button = sourceButton || null;
    const buttonText = button ? button.textContent : "";
    if (button) button.dataset.commandState = "confirming";
    setText("launch-readiness-action-status", confirmMessage);
    await nextLaunchCommandFrame();
    if (!window.confirm(confirmMessage)) {
      const canceled = {
        command: "maintenance.archive_state_journals",
        ok: false,
        severity: "info",
        message: "State journal archive canceled.",
      };
      appendCommandResult(canceled);
      setText("launch-readiness-action-status", canceled.message);
      if (button) {
        button.dataset.commandState = "";
        button.textContent = buttonText || "Archive Event Journal";
      }
      updateLaunchCommandButtonStates();
      return;
    }
    if (button) button.textContent = "Archiving...";
    setLaunchCommandBusy(true);
    renderJsonDetail("launch-readiness-action-status", {
      label: "Submitted request",
      value: request,
      intro: "State journal archive request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/maintenance/archive-state-journals", request);
      appendCommandResult(result);
      renderLaunchCommandResult("launch-readiness-status", "launch-readiness-action-status", result, request);
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      } else {
        await refreshLaunchBackendPreflight();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "maintenance.archive_state_journals",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      renderLaunchCommandResult("launch-readiness-status", "launch-readiness-action-status", result, request);
    } finally {
      setLaunchCommandBusy(false);
      if (button) {
        button.dataset.commandState = "";
        button.textContent = buttonText || "Archive Event Journal";
      }
    }
  }

  async function startRerunFromForm(options = {}) {
    if (rejectLaunchCommandWhileBusy("rerun.start", "rerun-launch-status", "rerun-launch-detail")) return;
    const dryRun = typeof options === "boolean" ? options : Boolean(options.dry_run);
    const request = collectRerunStartRequest({ dry_run: dryRun });
    const actionLabel = request.dry_run ? "CSV rerun dry run" : "CSV rerun";
    renderLaunchPreflight("rerun-launch-preflight", rerunLaunchPreflightLines(request));
    if (!request.csv_path.trim()) {
      const missing = {
        command: "rerun.start",
        ok: false,
        severity: "error",
        message: "CSV path is required.",
      };
      appendCommandResult(missing);
      setText("rerun-launch-status", "Error");
      setText("rerun-launch-detail", missing.message);
      return;
    }
    const rerunButtonId = request.dry_run ? "rerun-dry-run-button" : "rerun-start-button";
    const rerunBtn = byId(rerunButtonId);
    const rerunBtnText = rerunBtn ? rerunBtn.textContent : "";
    setLaunchCommandButtonState(rerunButtonId, "confirming", request.dry_run ? "Confirming Preview..." : "Confirming Start...");
    setText("rerun-launch-status", "Confirming");
    setText("rerun-launch-detail", request.dry_run
      ? "Confirm CSV rerun preview. Dry-run should produce backend evidence without staging, moving, publishing, or touching media."
      : "Confirm live CSV rerun with copy / keep / park policy."
    );
    await nextLaunchCommandFrame();
    if (!window.confirm(request.dry_run
      ? "Preview CSV rerun as a dry run? This should produce backend evidence without staging, moving, publishing, or touching media."
      : "Start live CSV rerun with copy / keep / park policy?"
    )) {
      const canceled = {
        command: "rerun.start",
        ok: false,
        severity: "info",
        message: `${actionLabel} canceled.`,
        data: { dry_run: Boolean(request.dry_run) },
      };
      appendCommandResult(canceled);
      setText("rerun-launch-status", "Canceled");
      setText("rerun-launch-detail", canceled.message);
      if (rerunBtn) rerunBtn.textContent = rerunBtnText || (request.dry_run ? "Preview CSV Rerun" : "Start CSV Rerun");
      updateLaunchCommandButtonStates();
      return;
    }
    if (rerunBtn) rerunBtn.textContent = request.dry_run ? "Previewing..." : "Starting...";
    setLaunchCommandBusy(true);
    setText("rerun-launch-status", request.dry_run ? "Previewing..." : "Starting...");
    renderJsonDetail("rerun-launch-detail", {
      label: "Submitted request",
      value: request,
      intro: request.dry_run
        ? "CSV rerun dry-run request confirmed by the operator and about to be submitted."
        : "Live CSV rerun request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/rerun/start", request);
      appendCommandResult(result);
      renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", result, request);
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "rerun.start",
        ok: false,
        severity: "error",
        message,
      });
      renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", {
        command: "rerun.start",
        ok: false,
        severity: "error",
        message,
      }, request);
    } finally {
      setLaunchCommandBusy(false);
      if (rerunBtn) rerunBtn.textContent = rerunBtnText || (request.dry_run ? "Preview CSV Rerun" : "Start CSV Rerun");
    }
  }

  /**
   * Public namespace for the Launch page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineLaunchView = {
    requestPipelineControl,
    setControlCommandBusy,
    rejectControlCommandWhileBusy,
    isPipelineControlCommand,
    pipelineControlHistoryLine,
    renderPipelineControlHistory,
    launchReadinessStatus,
    launchReadinessLines,
    renderLaunchReadiness,
    setLaunchCommandBusy,
    updateLaunchCommandButtonStates,
    rejectLaunchCommandWhileBusy,
    collectPipelineStartRequest,
    syncPipelineModeControls,
    selectPipelineModePreset,
    browsePipelineSingleFile,
    clearPipelineSingleFile,
    pipelineStartConfirmMessage,
    startPipelineFromForm,
    startPendingPublishDrain,
    startStateJournalArchive,
    collectRerunStartRequest,
    startRerunFromForm,
    pipelineModeLabel,
    launchCommandStatusLabel,
    launchCommandResultCorrelationLines,
    formatLaunchCommandDetail,
    renderLaunchCommandResult,
    launchSettingsWorkspace,
    launchSettingsTrustStatus,
    launchSettingsDecision,
    launchSettingsDecisionLines,
    launchUnsavedSettingsPatchLines,
    launchSettingsRiskLines,
    launchRealMediaReadinessLines,
    launchSettingsRiskRows,
    launchSettingsRiskStatus,
    launchSettingsRiskSummaryLines,
    launchSettingsRiskDetailLines,
    renderLaunchSettingsRiskHandoff,
    launchPolicyBoundaryRows,
    launchPolicyBoundaryStatus,
    launchPolicyBoundarySummaryLines,
    launchPolicyBoundaryDetailLines,
    renderLaunchPolicyBoundary,
    launchSettingsIntentRows,
    launchSettingsIntentStatus,
    launchSettingsIntentSummaryLines,
    launchSettingsIntentDetailLines,
    renderLaunchSettingsIntentChecklist,
    launchScopeReconciliationRows,
    launchScopeReconciliationStatus,
    launchScopeReconciliationSummaryLines,
    launchScopeReconciliationDetailLines,
    renderLaunchScopeReconciliation,
    launchStartDecisionRows,
    launchStartDecisionStatus,
    launchStartDecisionSummaryLines,
    launchStartDecisionDetailLines,
    renderLaunchStartDecisionSummary,
    launchCompactGateRows,
    launchCompactGateOverallStatus,
    renderLaunchCompactGate,
    launchRealMediaProofRows,
    launchRealMediaProofStatus,
    launchRealMediaProofSummaryLines,
    launchRealMediaProofDetailLines,
    launchWorksheetEvidence,
    launchWorksheetRunRows,
    launchWorksheetRunsMatchingSample,
    launchPolicyAlignmentPayload,
    launchPolicyAlignmentRows,
    launchQueueIntentCategoryMatch,
    launchPolicyAlignmentQueueIntentEvidence,
    launchSampleSetCoverageEvidence,
    launchSampleSetCoverageLine,
    launchSampleValidationRecordEvidence,
    launchSampleValidationRecordRows,
    launchSampleValidationRecordsMatchingSample,
    renderLaunchRealMediaProofHandoff,
    launchSampleExecutionRows,
    launchSampleExecutionStatus,
    launchSampleExecutionSummaryLines,
    launchSampleExecutionDetailLines,
    renderLaunchSampleExecutionChecklist,
    launchPilotRunReadinessRows,
    launchPilotRunReadinessStatus,
    launchPilotRunReadinessSummaryLines,
    launchPilotRunReadinessDetailLines,
    renderLaunchPilotRunReadiness,
    launchBackendPreflightRows,
    getLastLaunchBackendPreflightPayloads,
    launchBackendPreflightPayloadForTarget,
    getLastLaunchBackendPreflightRefreshInfo,
    launchBackendPreflightSummaryLines,
    launchBackendPreflightDetailLines,
    renderLaunchBackendPreflight,
    refreshLaunchBackendPreflight,
    pipelineLaunchPreflightLines,
    rerunLaunchPreflightLines,
    isLaunchCommand,
    renderLaunchCommandHistory,
    launchHistoryLine,
    renderAllLaunchPreflights,
    activateLaunchTab,
    initLaunchTabNav,
    initLaunchViewEvents,
    initLaunchRecoveryActionEvents,
  };
  window.requestPipelineControl = requestPipelineControl;
  window.isPipelineControlCommand = isPipelineControlCommand;
  window.pipelineControlHistoryLine = pipelineControlHistoryLine;
  window.renderPipelineControlHistory = renderPipelineControlHistory;
  window.launchReadinessStatus = launchReadinessStatus;
  window.launchReadinessLines = launchReadinessLines;
  window.renderLaunchReadiness = renderLaunchReadiness;
  window.syncPipelineModeControls = syncPipelineModeControls;
  window.selectPipelineModePreset = selectPipelineModePreset;
  window.browsePipelineSingleFile = browsePipelineSingleFile;
  window.clearPipelineSingleFile = clearPipelineSingleFile;
  window.startPipelineFromForm = startPipelineFromForm;
  window.startStateJournalArchive = startStateJournalArchive;
  window.collectRerunStartRequest = collectRerunStartRequest;
  window.startRerunFromForm = startRerunFromForm;
  window.launchSettingsWorkspace = launchSettingsWorkspace;
  window.launchSettingsTrustStatus = launchSettingsTrustStatus;
  window.launchSettingsDecision = launchSettingsDecision;
  window.launchSettingsDecisionLines = launchSettingsDecisionLines;
  window.launchSettingsRiskLines = launchSettingsRiskLines;
  window.launchRealMediaReadinessLines = launchRealMediaReadinessLines;
  window.launchSettingsRiskRows = launchSettingsRiskRows;
  window.launchSettingsRiskStatus = launchSettingsRiskStatus;
  window.launchSettingsRiskSummaryLines = launchSettingsRiskSummaryLines;
  window.renderLaunchSettingsRiskHandoff = renderLaunchSettingsRiskHandoff;
  window.launchPolicyBoundaryStatus = launchPolicyBoundaryStatus;
  window.launchPolicyBoundarySummaryLines = launchPolicyBoundarySummaryLines;
  window.launchPolicyBoundaryDetailLines = launchPolicyBoundaryDetailLines;
  window.renderLaunchPolicyBoundary = renderLaunchPolicyBoundary;
  window.launchSettingsIntentRows = launchSettingsIntentRows;
  window.launchSettingsIntentStatus = launchSettingsIntentStatus;
  window.launchSettingsIntentSummaryLines = launchSettingsIntentSummaryLines;
  window.launchSettingsIntentDetailLines = launchSettingsIntentDetailLines;
  window.renderLaunchSettingsIntentChecklist = renderLaunchSettingsIntentChecklist;
  window.launchScopeReconciliationStatus = launchScopeReconciliationStatus;
  window.launchScopeReconciliationSummaryLines = launchScopeReconciliationSummaryLines;
  window.launchScopeReconciliationDetailLines = launchScopeReconciliationDetailLines;
  window.launchStartDecisionRows = launchStartDecisionRows;
  window.launchStartDecisionStatus = launchStartDecisionStatus;
  window.launchStartDecisionSummaryLines = launchStartDecisionSummaryLines;
  window.launchStartDecisionDetailLines = launchStartDecisionDetailLines;
  window.launchCompactGateRows = launchCompactGateRows;
  window.launchCompactGateOverallStatus = launchCompactGateOverallStatus;
  window.renderLaunchCompactGate = renderLaunchCompactGate;
  window.launchRealMediaProofRows = launchRealMediaProofRows;
  window.launchRealMediaProofStatus = launchRealMediaProofStatus;
  window.launchRealMediaProofSummaryLines = launchRealMediaProofSummaryLines;
  window.launchRealMediaProofDetailLines = launchRealMediaProofDetailLines;
  window.launchWorksheetEvidence = launchWorksheetEvidence;
  window.launchWorksheetRunRows = launchWorksheetRunRows;
  window.launchWorksheetRunsMatchingSample = launchWorksheetRunsMatchingSample;
  window.launchPolicyAlignmentPayload = launchPolicyAlignmentPayload;
  window.launchPolicyAlignmentRows = launchPolicyAlignmentRows;
  window.launchQueueIntentCategoryMatch = launchQueueIntentCategoryMatch;
  window.launchPolicyAlignmentQueueIntentEvidence = launchPolicyAlignmentQueueIntentEvidence;
  window.launchSampleSetCoverageLine = launchSampleSetCoverageLine;
  window.launchSampleValidationRecordEvidence = launchSampleValidationRecordEvidence;
  window.launchSampleValidationRecordRows = launchSampleValidationRecordRows;
  window.launchSampleValidationRecordsMatchingSample = launchSampleValidationRecordsMatchingSample;
  window.launchSampleExecutionRows = launchSampleExecutionRows;
  window.launchSampleExecutionStatus = launchSampleExecutionStatus;
  window.launchSampleExecutionSummaryLines = launchSampleExecutionSummaryLines;
  window.launchSampleExecutionDetailLines = launchSampleExecutionDetailLines;
  window.launchPilotRunReadinessRows = launchPilotRunReadinessRows;
  window.launchPilotRunReadinessStatus = launchPilotRunReadinessStatus;
  window.launchPilotRunReadinessSummaryLines = launchPilotRunReadinessSummaryLines;
  window.launchPilotRunReadinessDetailLines = launchPilotRunReadinessDetailLines;
  window.launchBackendPreflightRows = launchBackendPreflightRows;
  window.getLastLaunchBackendPreflightPayloads = getLastLaunchBackendPreflightPayloads;
  window.launchBackendPreflightPayloadForTarget = launchBackendPreflightPayloadForTarget;
  window.getLastLaunchBackendPreflightRefreshInfo = getLastLaunchBackendPreflightRefreshInfo;
  window.launchBackendPreflightSummaryLines = launchBackendPreflightSummaryLines;
  window.launchBackendPreflightDetailLines = launchBackendPreflightDetailLines;
  window.renderLaunchBackendPreflight = renderLaunchBackendPreflight;
  window.refreshLaunchBackendPreflight = refreshLaunchBackendPreflight;
  window.pipelineLaunchPreflightLines = pipelineLaunchPreflightLines;
  window.rerunLaunchPreflightLines = rerunLaunchPreflightLines;
  window.isLaunchCommand = isLaunchCommand;
  window.renderLaunchCommandHistory = renderLaunchCommandHistory;
  window.launchHistoryLine = launchHistoryLine;
  window.initLaunchViewEvents = initLaunchViewEvents;
})();
