(function () {
  const launchReadinessView = window.mediaPipelineLaunchReadinessView || {};
  const launchReadinessStatus = launchReadinessView.launchReadinessStatus || window.launchReadinessStatus || function () { return "Checking"; };
  const launchReadinessLines = launchReadinessView.launchReadinessLines || window.launchReadinessLines || function () { return []; };
  const launchTimingStatus = launchReadinessView.launchTimingStatus || window.launchTimingStatus || null;
  const launchTimingTrustLines = launchReadinessView.launchTimingTrustLines || window.launchTimingTrustLines || null;
  const renderLaunchTimingTrust = launchReadinessView.renderLaunchTimingTrust || window.renderLaunchTimingTrust || null;
  const renderLaunchReadiness = launchReadinessView.renderLaunchReadiness || window.renderLaunchReadiness || function () {};
  const getLastLaunchReadinessPayload = launchReadinessView.getLastLaunchReadinessPayload || window.getLastLaunchReadinessPayload || null;
  const scheduleView = window.mediaPipelineScheduleView || {};
  const renderScheduleTimingTrust = typeof scheduleView.renderScheduleTimingTrust === "function" ? scheduleView.renderScheduleTimingTrust : null;
  const scheduleDisplayValue = typeof scheduleView.scheduleDisplayValue === "function" ? scheduleView.scheduleDisplayValue : null;
  const scheduleWatcherSummary = typeof scheduleView.scheduleWatcherSummary === "function" ? scheduleView.scheduleWatcherSummary : null;
  const settingsOverview = window.mediaPipelineSettingsOverview || {};
  const settingsView = window.mediaPipelineSettingsView || {};
  const settingsOperatorTrustStatus = typeof settingsOverview.settingsOperatorTrustStatus === "function" ? settingsOverview.settingsOperatorTrustStatus : null;
  const commandHistoryView = window.mediaPipelineCommandHistory || {};
  const launchHistoryView = window.mediaPipelineLaunchHistoryView || {};
  const isLaunchCommand = launchHistoryView.isLaunchCommand || function () { return false; };
  const launchHistoryLine = launchHistoryView.launchHistoryLine || function () { return ""; };
  const launchCommandCorrelationRows = launchHistoryView.launchCommandCorrelationRows || window.launchCommandCorrelationRows || null;
  const launchCommandCorrelationStatus = launchHistoryView.launchCommandCorrelationStatus || window.launchCommandCorrelationStatus || null;
  const launchCommandDiagnosticsActions = launchHistoryView.launchCommandDiagnosticsActions || window.launchCommandDiagnosticsActions || null;
  const launchCommandReviewRows = launchHistoryView.launchCommandReviewRows || window.launchCommandReviewRows || null;
  const launchCommandReviewStatus = launchHistoryView.launchCommandReviewStatus || window.launchCommandReviewStatus || null;
  const launchCommandReviewSummaryLines = launchHistoryView.launchCommandReviewSummaryLines || window.launchCommandReviewSummaryLines || null;
  const renderLaunchCommandHistory = launchHistoryView.renderLaunchCommandHistory || function () {};
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
  const RERUN_EXECUTION_LABELS = {
    one_at_a_time: "One at a time",
    windowed: "Windowed",
    batch_stage_all: "Batch stage all",
  };
  const RERUN_POLICY_CHOICES = {
    destination: {
      auto: {
        label: "Auto destination",
        detail: "Frontend resolves to the least destructive destination that fits the selected collision and original policy.",
        state: "ok",
      },
      review_workspace: {
        label: "Review workspace",
        detail: "Verified outputs stay in review; final library placement is not attempted from this selection.",
        state: "ok",
      },
      pending_publish: {
        label: "Pending publish",
        detail: "Verified outputs are parked for backend drain proof before final placement.",
        state: "review",
      },
      publish_non_overlap: {
        label: "Publish with non-overlap name",
        detail: "Backend may publish verified output only when the final path can avoid replacing an existing file.",
        state: "review",
      },
      publish_replace_final: {
        label: "Publish and replace final output",
        detail: "Backend requires final-output proof and replace confirmation before any final-library replacement.",
        state: "blocked",
      },
    },
    collision: {
      auto: {
        label: "Auto collision",
        detail: "Frontend resolves to suffix unless final replacement is required by the destination.",
        state: "ok",
      },
      suffix: {
        label: "Suffix when needed",
        detail: "Backend uses a non-overlap name instead of overwriting a destination.",
        state: "ok",
      },
      fail: {
        label: "Block on overlap",
        detail: "A destination overlap blocks the row before final placement.",
        state: "review",
      },
      replace_final: {
        label: "Replace final output",
        detail: "Replacement is allowed only with backend confirmation and output proof.",
        state: "blocked",
      },
    },
    original: {
      auto: {
        label: "Auto original action",
        detail: "Frontend keeps the original unless final replacement is selected, then it holds the original after proof.",
        state: "ok",
      },
      keep: {
        label: "Keep original",
        detail: "The original file remains untouched after output proof.",
        state: "ok",
      },
      rename_after_publish: {
        label: "Keep but rename after publish",
        detail: "After publish proof, backend may rename the original for traceability.",
        state: "review",
      },
      move_to_hold_after_publish: {
        label: "Move to original hold after publish",
        detail: "After publish proof, backend may move the original into cleanup hold for operator review.",
        state: "review",
      },
      hold_then_delete_after_publish: {
        label: "Hold then mark cleanup-ready",
        detail: "After proof, backend can mark the original cleanup-ready in hold; deletion remains a separate cleanup decision.",
        state: "blocked",
      },
    },
  };
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
  let lastRerunPreviewPayload = null;
  let rerunPreviewRefreshTimer = null;
  let rerunOriginalPolicyTouched = false;

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
    collectRerunPreviewRequest = function () { return { csv_path: "", execution_mode: "one_at_a_time", destination_mode: "review_workspace", original_policy: "keep", collision_policy: "suffix", window_size: 1, scope: { enabled_only: true, skip_blocked: false, skip_warning_rows: false, first_n: 0, issue_filters: [], bucket_filters: [], preview_limit: 50 } }; },
    collectRerunScopeRequest = function () { return { enabled_only: true, skip_blocked: false, skip_warning_rows: false, first_n: 0, issue_filter: "", bucket_filter: "", preview_limit: 50 }; },
    collectRerunStartRequest = function (options = {}) { return { csv_path: "", dry_run: Boolean(options.dry_run), plan_only: Boolean(options.plan_only), execution_mode: "one_at_a_time", destination_mode: "review_workspace", original_policy: "keep", collision_policy: "suffix", window_size: 1, confirm_replace_final: false, confirm_original_policy: false, confirm_delete_original: false, scope: collectRerunScopeRequest() }; },
    resolveRerunPolicySelection = function (raw = {}) {
      const destinationMode = raw.destination_mode && raw.destination_mode !== "auto"
        ? raw.destination_mode
        : raw.collision_policy === "replace_final" || (raw.original_policy && raw.original_policy !== "auto" && raw.original_policy !== "keep") ? "pending_publish" : "review_workspace";
      const collisionPolicy = raw.collision_policy && raw.collision_policy !== "auto"
        ? raw.collision_policy
        : destinationMode === "publish_replace_final" ? "replace_final" : "suffix";
      const originalPolicy = raw.original_policy && raw.original_policy !== "auto"
        ? raw.original_policy
        : destinationMode === "publish_replace_final" || collisionPolicy === "replace_final" ? "move_to_hold_after_publish" : "keep";
      return { destination_mode: destinationMode, collision_policy: collisionPolicy, original_policy: originalPolicy };
    },
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
      launchCommandCorrelationRows: typeof launchCommandCorrelationRows === "function" ? launchCommandCorrelationRows : null,
      launchCommandCorrelationStatus: typeof launchCommandCorrelationStatus === "function" ? launchCommandCorrelationStatus : null,
      launchCommandDiagnosticsActions: typeof launchCommandDiagnosticsActions === "function" ? launchCommandDiagnosticsActions : null,
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
      rerunPreviewBlockedReason,
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
    return ["pipeline", "rerun", "history"];
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
      getLastLaunchReadinessPayload: typeof getLastLaunchReadinessPayload === "function" ? () => getLastLaunchReadinessPayload() : () => ({}),
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : () => []),
      getLastSettings: typeof window.getLastSettings === "function" ? () => window.getLastSettings() : (typeof getLastSettings === "function" ? () => getLastSettings() : () => ({})),
      isLaunchCommand,
      launchHistoryLine,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pipelineModeLabel,
      queueCurrentFilterScope: typeof window.queueCurrentFilterScope === "function" ? window.queueCurrentFilterScope : (typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope : null),
      queueFilterScopeDetailLines: typeof window.queueFilterScopeDetailLines === "function" ? window.queueFilterScopeDetailLines : (typeof queueFilterScopeDetailLines === "function" ? queueFilterScopeDetailLines : null),
      scheduleDisplayValue,
      setText: typeof setText === "function" ? setText : window.setText,
      settingsCommandHistoryLine: typeof window.mediaPipelineSettingsCommandHistory?.settingsCommandHistoryLine === "function" ? window.mediaPipelineSettingsCommandHistory.settingsCommandHistoryLine : null,
      settingsLaunchImpactRows: typeof settingsView.settingsLaunchImpactRows === "function" ? settingsView.settingsLaunchImpactRows : null,
      settingsLaunchImpactStatus: typeof settingsView.settingsLaunchImpactStatus === "function" ? settingsView.settingsLaunchImpactStatus : null,
      settingsOperatorTrustStatus,
      settingsPatchEffectiveChangedEntries: typeof settingsView.settingsPatchEffectiveChangedEntries === "function" ? settingsView.settingsPatchEffectiveChangedEntries : null,
      settingsPatchIsTouched: typeof settingsView.settingsPatchIsTouched === "function" ? settingsView.settingsPatchIsTouched : null,
      settingsPolicyDeltaRows: typeof settingsView.settingsPolicyDeltaRows === "function" ? settingsView.settingsPolicyDeltaRows : null,
      settingsPolicyDeltaStatus: typeof settingsView.settingsPolicyDeltaStatus === "function" ? settingsView.settingsPolicyDeltaStatus : null,
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
      commandHistoryIssueLevel: typeof commandHistoryView.commandHistoryIssueLevel === "function" ? commandHistoryView.commandHistoryIssueLevel : null,
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
      launchCommandReviewRows: typeof launchCommandReviewRows === "function" ? launchCommandReviewRows : null,
      launchCommandReviewStatus: typeof launchCommandReviewStatus === "function" ? launchCommandReviewStatus : null,
      launchCommandReviewSummaryLines: typeof launchCommandReviewSummaryLines === "function" ? launchCommandReviewSummaryLines : null,
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
      scheduleDisplayValue,
      scheduleWatcherSummary,
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
      renderLaunchTimingTrust: typeof renderLaunchTimingTrust === "function" ? renderLaunchTimingTrust : null,
      renderQueueLaunchDecisionChecklist: typeof window.renderQueueLaunchDecisionChecklist === "function" ? window.renderQueueLaunchDecisionChecklist : (typeof renderQueueLaunchDecisionChecklist === "function" ? renderQueueLaunchDecisionChecklist : null),
      renderScheduleTimingTrust: typeof renderScheduleTimingTrust === "function" ? renderScheduleTimingTrust : null,
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
    const refreshLaunchControlsForInput = (event = null) => {
      syncPipelineModeControls();
      applyRerunPolicySelectionRules(event);
      syncRerunOriginalPolicyForDestination(event);
      renderRerunHandlingSummary();
      renderAllLaunchPreflights();
      updateLaunchCommandButtonStates();
      if (String(event?.target?.id || "").startsWith("rerun-")) {
        scheduleRerunPreviewRefresh();
      }
      applyRerunPreviewButtonState();
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
      "rerun-start-execution-mode",
      "rerun-start-window-size",
      "rerun-start-destination-mode",
      "rerun-start-collision-policy",
      "rerun-start-original-policy",
      "rerun-scope-enabled-only",
      "rerun-scope-skip-blocked",
      "rerun-scope-skip-warning-rows",
      "rerun-scope-first-n",
      "rerun-scope-issue-filter",
      "rerun-scope-bucket-filter",
      "rerun-preview-limit",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", refreshLaunchControlsForInput);
      element.addEventListener("change", refreshLaunchControlsForInput);
    });
    applyRerunPolicySelectionRules();
    syncRerunOriginalPolicyForDestination();
    renderRerunHandlingSummary();
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
    const inspectCsvButton = byId("rerun-inspect-csv-button");
    if (inspectCsvButton) {
      inspectCsvButton.addEventListener("click", () => inspectSelectedRerunCsv().catch((error) => {
        setText("rerun-launch-detail", error instanceof Error ? error.message : String(error));
      }));
    }
    const openCsvButton = byId("rerun-open-csv-button");
    if (openCsvButton) {
      openCsvButton.addEventListener("click", () => openSelectedRerunCsv("import_csv").catch((error) => {
        setText("rerun-launch-detail", error instanceof Error ? error.message : String(error));
      }));
    }
    const openCsvFolderButton = byId("rerun-open-csv-folder-button");
    if (openCsvFolderButton) {
      openCsvFolderButton.addEventListener("click", () => openSelectedRerunCsv("csv_folder").catch((error) => {
        setText("rerun-launch-detail", error instanceof Error ? error.message : String(error));
      }));
    }
    initLaunchRecoveryActionEvents();
    renderAllLaunchPreflights();
    refreshRerunPreview({ quiet: true }).catch(() => {});
    refreshLaunchBackendPreflight()
      .then(() => {
        renderLaunchCompactGate();
        updateLaunchCommandButtonStates();
        applyRerunPreviewButtonState();
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        setText("launch-backend-preflight-status", "Load failed");
        const statusNode = byId("launch-backend-preflight-status");
        if (statusNode) statusNode.dataset.state = "warning";
        setText("launch-backend-preflight-summary", [
          "Pipeline backend preflight did not load automatically.",
          `Error: ${message}`,
          "Action: refresh the backend preflight from Launch for current evidence; routine Start still submits to backend guards.",
          "Mutation guardrail: automatic preflight loading is read-only and cannot launch, reserve locks, save settings, drain, rename, publish, or touch media files.",
        ].join("\n"));
        renderLaunchCompactGate();
        updateLaunchCommandButtonStates();
      });
    syncPipelineModeControls();
    updateLaunchCommandButtonStates();
  }

  function initLaunchRecoveryActionEvents() {
    if (!document || document.__launchRecoveryEventsBound === true) return;
    document.__launchRecoveryEventsBound = true;
    document.addEventListener("click", async (event) => {
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
      `Submitting ${label} for ${scope}. Backend will re-check queue, settings, schedule, and locks before starting.`,
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
    setLaunchCommandButtonState("pipeline-start-button", "submitting", "Starting...");
    setText("pipeline-launch-status", "Starting...");
    setText("pipeline-launch-detail", pipelineStartConfirmMessage(request, label));
    await nextLaunchCommandFrame();
    if (startBtn) startBtn.textContent = "Launching…";
    setLaunchCommandBusy(true);
    setStartupBanner("Spooling up tasks…");
    setText("pipeline-launch-status", "Starting...");
    renderJsonDetail("pipeline-launch-detail", {
      label: "Submitted request",
      value: request,
      intro: "Pipeline start request submitted to the backend; backend launch guards remain authoritative.",
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

  function rerunPreviewCounts(payload) {
    return payload && typeof payload === "object" && payload.counts && typeof payload.counts === "object" ? payload.counts : {};
  }

  function rerunPreviewScope(payload) {
    return payload && typeof payload === "object" && payload.scope && typeof payload.scope === "object" ? payload.scope : collectRerunScopeRequest();
  }

  function rerunCount(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function rerunLabelFromChoice(kind, value) {
    return rerunPolicyChoice(kind, value).label || String(value || "");
  }

  function rerunPreviewConflictLines(payload) {
    if (!payload || typeof payload !== "object") return [];
    const counts = rerunPreviewCounts(payload);
    const scope = rerunPreviewScope(payload);
    const lines = [];
    const safeModes = payload.safe_modes === true;
    const blockedModes = rerunCount(counts.blocked_mode_rows);
    const blockedScoped = rerunCount(counts.blocked_scoped_rows);
    const effectiveScoped = rerunCount(counts.effective_scoped_rows);
    const affectedRows = blockedScoped || blockedModes || rerunCount(counts.blocked_rows);

    if (!safeModes || blockedModes > 0) {
      const affectedText = affectedRows > 0 ? `${affectedRows} row(s)` : "The selected row scope";
      lines.push(`${affectedText} are blocked by the rerun lifecycle policy, not by a CSV read error.`);
      const conflicts = [];
      if (payload.destination_mode && payload.destination_mode !== "review_workspace") {
        conflicts.push(`Destination is ${rerunLabelFromChoice("destination", payload.destination_mode)}`);
      }
      if (payload.collision_policy === "replace_final") {
        conflicts.push(`Destination collision is ${rerunLabelFromChoice("collision", payload.collision_policy)}`);
      }
      if (payload.original_policy && payload.original_policy !== "keep") {
        conflicts.push(`Original After Proof is ${rerunLabelFromChoice("original", payload.original_policy)}`);
      }
      if (payload.stage_mode && payload.stage_mode !== "copy") {
        conflicts.push(`stage_mode=${payload.stage_mode}`);
      }
      if (payload.return_mode && payload.return_mode !== "park") {
        conflicts.push(`return_mode=${payload.return_mode}`);
      }
      if (conflicts.length) {
        lines.push(`Selected policy conflict: ${conflicts.join("; ")}.`);
      }
      lines.push("Executable CSV rerun currently only supports scratch-copy staging, review-workspace parking, and keeping the original untouched.");
      lines.push("Change Destination to review workspace, Destination Collision to suffix when needed, and Original After Proof to keep original, then inspect the CSV again.");
    }

    if (effectiveScoped > 0 && blockedScoped >= effectiveScoped) {
      lines.push("Every effective scoped row is blocked, so the current execution mode stages 0 rows.");
    } else if (scope.skip_blocked && blockedModes > 0) {
      lines.push("Skip Blocked can remove blocked rows from the scoped CSV only when at least one non-blocked scoped row remains.");
    }

    if (rerunCount(counts.missing_source_rows) > 0) {
      lines.push(`${rerunCount(counts.missing_source_rows)} row(s) are missing source_path values.`);
    }
    return Array.from(new Set(lines));
  }

  function rerunSummaryLines(payload) {
    if (!payload || typeof payload !== "object") return ["No CSV rerun preview loaded."];
    const counts = rerunPreviewCounts(payload);
    const scope = rerunPreviewScope(payload);
    const lines = [
      `Status: ${payload.status || "unknown"} - ${payload.message || ""}`.trim(),
      `CSV: ${payload.csv_path || "not selected"}`,
      `Rows: total ${counts.total_rows || 0}; enabled ${counts.enabled_rows || 0}; disabled ${counts.disabled_rows || 0}; effective scoped ${counts.effective_scoped_rows || 0}`,
      `Blockers: blocked rows ${counts.blocked_rows || 0}; blocked modes ${counts.blocked_mode_rows || 0}; blocked scoped ${counts.blocked_scoped_rows || 0}; missing source ${counts.missing_source_rows || 0}; duplicate source ${counts.duplicate_source_rows || 0}`,
      `Warnings: ${counts.warning_rows || 0}`,
      `Scope: enabled only ${scope.enabled_only ? "yes" : "no"}; skip blocked ${scope.skip_blocked ? "yes" : "no"}; skip warnings ${scope.skip_warning_rows ? "yes" : "no"}; first rows ${scope.first_n || 0}; issue "${scope.issue_filter || ""}"; bucket "${scope.bucket_filter || ""}"`,
    ];
    const conflicts = rerunPreviewConflictLines(payload);
    if (conflicts.length) lines.push("", "Why blocked:", ...conflicts.map((item) => `- ${item}`));
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    if (warnings.length) lines.push("", "Warnings:", ...warnings.map((item) => `- ${item}`));
    return lines;
  }

  function clearElement(element) {
    if (!element) return;
    while (element.firstChild) element.removeChild(element.firstChild);
  }

  function appendCell(row, text) {
    const cell = document.createElement("td");
    cell.textContent = text;
    row.appendChild(cell);
    return cell;
  }

  function renderRerunRecentCsvs(payload) {
    const tbody = byId("rerun-recent-csv-rows");
    if (!tbody) return;
    clearElement(tbody);
    const rows = payload && Array.isArray(payload.recent_csvs) ? payload.recent_csvs : [];
    if (!rows.length) {
      const row = document.createElement("tr");
      appendCell(row, "No recent CSV evidence loaded.").colSpan = 4;
      tbody.appendChild(row);
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCell(row, item.label || item.path || "CSV");
      appendCell(row, item.source || "");
      appendCell(row, item.modified_at || "");
      const action = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button";
      button.textContent = "Use";
      button.title = item.path || "";
      button.addEventListener("click", () => {
        const input = byId("rerun-start-csv-path");
        if (input) input.value = item.path || "";
        scheduleRerunPreviewRefresh(0);
        renderAllLaunchPreflights();
        updateLaunchCommandButtonStates();
        applyRerunPreviewButtonState();
      });
      action.appendChild(button);
      row.appendChild(action);
      tbody.appendChild(row);
    });
  }

  function rerunPolicyChoice(kind, value) {
    const key = String(value || "");
    const choices = RERUN_POLICY_CHOICES[kind] || {};
    if (choices[key]) return choices[key];
    return {
      label: key || "Unknown",
      detail: "Backend will apply the selected policy when the request is accepted.",
      state: "review",
    };
  }

  function rerunExecutionLabel(value) {
    const key = String(value || "one_at_a_time");
    return RERUN_EXECUTION_LABELS[key] || key;
  }

  function setRerunHandlingText(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.textContent = value;
  }

  function renderRerunHandlingCard(kind, choice) {
    const card = document.querySelector(`[data-rerun-policy-card="${kind}"]`);
    if (card) card.dataset.state = choice.state || "review";
    setRerunHandlingText(`[data-rerun-policy-summary="${kind}"]`, choice.label);
    setRerunHandlingText(`[data-rerun-policy-detail="${kind}"]`, choice.detail);
  }

  function rerunFinalReplacementSelected(request) {
    return request?.destination_mode === "publish_replace_final" || request?.collision_policy === "replace_final";
  }

  function rerunPolicySelectId(kind) {
    return {
      destination: "rerun-start-destination-mode",
      collision: "rerun-start-collision-policy",
      original: "rerun-start-original-policy",
    }[kind] || "";
  }

  function rerunPolicyRequestKey(kind) {
    return {
      destination: "destination_mode",
      collision: "collision_policy",
      original: "original_policy",
    }[kind] || "";
  }

  function rerunPolicyKindFromElement(element) {
    const id = String(element?.id || "");
    if (id === "rerun-start-destination-mode") return "destination";
    if (id === "rerun-start-collision-policy") return "collision";
    if (id === "rerun-start-original-policy") return "original";
    return "";
  }

  function rerunRawPolicySelection() {
    return {
      destination_mode: byId("rerun-start-destination-mode")?.value || "review_workspace",
      collision_policy: byId("rerun-start-collision-policy")?.value || "suffix",
      original_policy: byId("rerun-start-original-policy")?.value || "keep",
    };
  }

  function rerunPolicyConflictReason(kind, value, raw = rerunRawPolicySelection()) {
    const selected = String(value || "");
    if (!selected || selected === "auto") return "";
    const destination = kind === "destination" ? selected : String(raw.destination_mode || "review_workspace");
    const collision = kind === "collision" ? selected : String(raw.collision_policy || "suffix");
    const original = kind === "original" ? selected : String(raw.original_policy || "keep");
    const collisionFixed = collision !== "auto";
    const originalFixed = original !== "auto";
    const destinationFixed = destination !== "auto";

    if (kind === "destination") {
      if (selected === "review_workspace" && originalFixed && original !== "keep") {
        return "Original-source action needs publish proof; auto will keep the original.";
      }
      if (selected === "publish_non_overlap" && collision === "replace_final") {
        return "Non-overlap destination cannot also replace final output; auto will use suffix collision.";
      }
      if (selected === "publish_replace_final" && collisionFixed && collision !== "replace_final") {
        return "Final replacement requires replace-final collision; auto will align collision and original handling.";
      }
    }

    if (kind === "collision") {
      if (selected === "replace_final" && destinationFixed && !["pending_publish", "publish_replace_final"].includes(destination)) {
        return "Replace-final collision needs a publish destination; auto will use pending publish and original hold.";
      }
      if (selected !== "replace_final" && destination === "publish_replace_final") {
        return "Publish-and-replace destination requires replace-final collision; auto will align destination and original handling.";
      }
    }

    if (kind === "original" && selected !== "keep" && destination === "review_workspace") {
      return "Original-source action needs publish proof; auto will use pending publish with the least destructive collision.";
    }

    return "";
  }

  function setRerunPolicySelectAuto(kind) {
    const select = byId(rerunPolicySelectId(kind));
    if (!select) return;
    const hasAuto = Array.from(select.options || []).some((option) => option.value === "auto");
    if (hasAuto) select.value = "auto";
    if (kind === "original") {
      rerunOriginalPolicyTouched = false;
      select.dataset.rerunOriginalPolicySource = "auto";
    }
  }

  function updateRerunPolicyOptionStates() {
    const raw = rerunRawPolicySelection();
    ["destination", "collision", "original"].forEach((kind) => {
      const select = byId(rerunPolicySelectId(kind));
      if (!select || !select.options) return;
      let conflictCount = 0;
      Array.from(select.options).forEach((option) => {
        const baseLabel = option.dataset.rerunBaseLabel || option.textContent || option.value;
        option.dataset.rerunBaseLabel = baseLabel;
        const reason = rerunPolicyConflictReason(kind, option.value, raw);
        if (reason) conflictCount += 1;
        option.dataset.rerunConflict = reason ? "true" : "false";
        option.setAttribute("aria-disabled", reason ? "true" : "false");
        option.title = reason;
        option.textContent = reason ? `${baseLabel} (auto adjusts)` : baseLabel;
      });
      select.dataset.rerunHasConflicts = conflictCount > 0 ? "true" : "false";
      select.dataset.rerunAuto = select.value === "auto" ? "true" : "false";
    });
  }

  function applyRerunPolicySelectionRules(event = null) {
    const kind = rerunPolicyKindFromElement(event?.target);
    if (!kind) {
      updateRerunPolicyOptionStates();
      return;
    }
    const raw = rerunRawPolicySelection();
    const key = rerunPolicyRequestKey(kind);
    const reason = rerunPolicyConflictReason(kind, raw[key], raw);
    if (kind === "original") {
      rerunOriginalPolicyTouched = raw.original_policy !== "auto";
      event.target.dataset.rerunOriginalPolicySource = raw.original_policy === "auto" ? "auto" : "manual";
    }
    if (reason) {
      ["destination", "collision", "original"].forEach((candidate) => {
        if (candidate !== kind) setRerunPolicySelectAuto(candidate);
      });
      setText("rerun-mode-policy-note", `Auto-adjusted ${kind} pairing. ${reason} Backend still receives concrete policy values after auto resolution.`);
    }
    updateRerunPolicyOptionStates();
  }

  function syncRerunOriginalPolicyForDestination(event = null) {
    const select = byId("rerun-start-original-policy");
    if (!select) return;
    if (String(event?.target?.id || "") === "rerun-start-original-policy") {
      rerunOriginalPolicyTouched = select.value !== "auto";
      select.dataset.rerunOriginalPolicySource = select.value === "auto" ? "auto" : "manual";
      return;
    }
    if (select.value === "auto") {
      rerunOriginalPolicyTouched = false;
      select.dataset.rerunOriginalPolicySource = "auto";
    }
  }

  function rerunPolicyChoiceForSummary(kind, rawValue, resolvedValue) {
    const resolved = resolvedValue || rawValue;
    const choice = { ...rerunPolicyChoice(kind, resolved) };
    if (rawValue === "auto") {
      choice.label = `Auto: ${choice.label}`;
      choice.detail = `${choice.detail} Auto resolved from the current destination/collision/original equation before backend submit.`;
    }
    return choice;
  }

  function rerunOriginalPolicyChoiceForSummary(request, raw = rerunRawPolicySelection()) {
    const choice = rerunPolicyChoiceForSummary("original", raw.original_policy, request.original_policy || "keep");
    if (!rerunFinalReplacementSelected(request)) return choice;
    if (raw.original_policy === "auto" && request.original_policy === "move_to_hold_after_publish") {
      choice.detail = `${choice.detail} Auto-selected because final replacement is selected.`;
      return choice;
    }
    if (request.original_policy !== "move_to_hold_after_publish") {
      choice.detail = `${choice.detail} Replacement is usually paired with original hold; this manual choice will be sent as selected.`;
      if (choice.state === "ok") choice.state = "review";
    }
    return choice;
  }

  function renderRerunHandlingSummary(request = collectRerunStartRequest()) {
    const raw = rerunRawPolicySelection();
    renderRerunHandlingCard("destination", rerunPolicyChoiceForSummary("destination", raw.destination_mode, request.destination_mode || "review_workspace"));
    renderRerunHandlingCard("collision", rerunPolicyChoiceForSummary("collision", raw.collision_policy, request.collision_policy || "suffix"));
    renderRerunHandlingCard("original", rerunOriginalPolicyChoiceForSummary(request, raw));
    updateRerunPolicyOptionStates();
  }

  function rerunStartPolicySummary(request) {
    const execution = rerunExecutionLabel(request.execution_mode);
    const windowSize = Number(request.window_size || 1);
    const raw = rerunRawPolicySelection();
    const destination = rerunPolicyChoiceForSummary("destination", raw.destination_mode, request.destination_mode || "review_workspace");
    const collision = rerunPolicyChoiceForSummary("collision", raw.collision_policy, request.collision_policy || "suffix");
    const original = rerunOriginalPolicyChoiceForSummary(request, raw);
    return `${execution} (window ${Number.isFinite(windowSize) ? Math.max(1, Math.round(windowSize)) : 1}); destination: ${destination.label}; collision: ${collision.label}; original after proof: ${original.label}`;
  }

  function selectedOptionValues(select) {
    if (!select || !select.options) return [];
    return Array.from(select.options).filter((option) => option.selected).map((option) => option.value);
  }

  function renderRerunSelectOptions(id, options) {
    const select = byId(id);
    if (!select || !Array.isArray(options)) return;
    const selected = new Set(selectedOptionValues(select));
    clearElement(select);
    options.forEach((item) => {
      const value = String(item.value || item.label || "");
      if (!value) return;
      const option = document.createElement("option");
      option.value = value;
      option.textContent = item.count ? `${item.label || value} (${item.count})` : (item.label || value);
      option.selected = selected.has(value);
      select.appendChild(option);
    });
  }

  function renderRerunFilterOptions(payload) {
    const options = payload && typeof payload.filter_options === "object" ? payload.filter_options : {};
    renderRerunSelectOptions("rerun-scope-issue-filter", options.issue_filters || []);
    renderRerunSelectOptions("rerun-scope-bucket-filter", options.bucket_filters || []);
  }

  function renderRerunPreviewTiles(payload) {
    const container = byId("rerun-preview-tiles");
    if (!container) return;
    clearElement(container);
    const tiles = payload && Array.isArray(payload.tiles) ? payload.tiles : [];
    if (!tiles.length) {
      container.textContent = "No CSV rerun status tiles loaded.";
      return;
    }
    tiles.forEach((tile) => {
      const item = document.createElement("div");
      item.className = "command-history-entry";
      const label = document.createElement("strong");
      label.textContent = `${tile.label || tile.key || "Tile"}: ${tile.value ?? ""}`;
      item.appendChild(label);
      if (tile.detail) {
        const detail = document.createElement("span");
        detail.textContent = String(tile.detail);
        item.appendChild(detail);
      }
      container.appendChild(item);
    });
  }

  function renderRerunPreviewRows(payload) {
    const tbody = byId("rerun-preview-rows");
    if (!tbody) return;
    clearElement(tbody);
    const rows = payload && Array.isArray(payload.rows) ? payload.rows : [];
    if (!rows.length) {
      const row = document.createElement("tr");
      appendCell(row, "No CSV rerun rows loaded.").colSpan = 6;
      tbody.appendChild(row);
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.rowState = item.status || "unknown";
      appendCell(row, String((item.row_index || 0) + 1));
      appendCell(row, `${item.status || "unknown"}${item.in_scope ? "" : " / filtered"}`);
      appendCell(row, item.source_path || "");
      appendCell(row, [item.issue || "", item.bucket || ""].filter(Boolean).join(" / "));
      appendCell(row, `${rerunPolicyChoice("destination", (payload && payload.destination_mode) || "review_workspace").label} / ${rerunExecutionLabel((payload && payload.execution_mode) || "one_at_a_time")}`);
      appendCell(row, item.reason || "");
      tbody.appendChild(row);
    });
  }

  function renderRerunHistorySummary() {
    const history = typeof window.getCommandHistory === "function"
      ? window.getCommandHistory()
      : typeof window.mediaPipelineCommandHistory?.getCommandHistory === "function"
      ? window.mediaPipelineCommandHistory.getCommandHistory()
      : [];
    const entries = Array.isArray(history)
      ? history.filter((entry) => String(entry.command || "") === "rerun.start").slice(0, 6)
      : [];
    if (!entries.length) {
      setText("rerun-history-summary", "No CSV rerun history loaded.");
      return;
    }
    setText("rerun-history-summary", entries.map((entry) => {
      const data = entry.data && typeof entry.data === "object" ? entry.data : {};
      return `${entry.started_at || entry.completed_at || "recent"} | ${entry.ok ? "ok" : "failed"} | ${data.csv_path || data.source_csv_path || ""} | ${entry.message || ""}`;
    }).join("\n"));
  }

  function renderRerunPolicyPanel(payload) {
    const counts = rerunPreviewCounts(payload);
    const request = collectRerunStartRequest();
    const destination = rerunPolicyChoice("destination", (payload && payload.destination_mode) || request.destination_mode);
    const collision = rerunPolicyChoice("collision", (payload && payload.collision_policy) || request.collision_policy);
    const original = rerunOriginalPolicyChoiceForSummary({
      ...request,
      destination_mode: (payload && payload.destination_mode) || request.destination_mode,
      collision_policy: (payload && payload.collision_policy) || request.collision_policy,
      original_policy: (payload && payload.original_policy) || request.original_policy,
    });
    const lines = [
      `Execution: ${rerunExecutionLabel((payload && payload.execution_mode) || request.execution_mode)}; window=${(payload && payload.window_size) || request.window_size}.`,
      `Destination handling: ${destination.label}. ${destination.detail}`,
      `When output exists: ${collision.label}. ${collision.detail}`,
      `Old source after proof: ${original.label}. ${original.detail}`,
      `Backend confirmations: replace final ${request.confirm_replace_final ? "included" : "not included"}; original action ${request.confirm_original_policy ? "included" : "not included"}.`,
      `Blocked rows in preview: ${counts.blocked_mode_rows || 0}.`,
    ];
    setText("rerun-policy-panel", lines.join("\n"));
  }

  function selectedRerunCsvCandidate() {
    const current = String(byId("rerun-start-csv-path")?.value || "").trim().toLowerCase();
    const candidates = lastRerunPreviewPayload && Array.isArray(lastRerunPreviewPayload.recent_csvs)
      ? lastRerunPreviewPayload.recent_csvs
      : [];
    return candidates.find((item) => String(item.path || "").trim().toLowerCase() === current) || null;
  }

  async function inspectSelectedRerunCsv() {
    const result = await refreshRerunPreview({ quiet: false });
    renderJsonDetail("rerun-launch-detail", {
      label: "CSV inspect",
      value: result,
      intro: "Backend read-only inspect of the selected rerun CSV.",
    });
  }

  async function openSelectedRerunCsv(target) {
    const selected = selectedRerunCsvCandidate();
    if (!selected || !selected.csv_key) {
      setText("rerun-launch-status", "CSV not in import list");
      setText("rerun-launch-detail", "Open CSV actions are limited to backend-known import/scoped CSV candidates.");
      return;
    }
    const result = await apiPost("/api/rerun/open", {
      target,
      csv_key: selected.csv_key,
    });
    appendCommandResult(result);
    renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", result, { target, csv_key: selected.csv_key });
  }

  function renderRerunPreview(payload) {
    lastRerunPreviewPayload = payload && typeof payload === "object" ? payload : null;
    renderRerunHandlingSummary();
    setText("rerun-preview-summary", rerunSummaryLines(lastRerunPreviewPayload).join("\n"));
    renderRerunRecentCsvs(lastRerunPreviewPayload);
    renderRerunFilterOptions(lastRerunPreviewPayload);
    renderRerunPreviewTiles(lastRerunPreviewPayload);
    renderRerunPreviewRows(lastRerunPreviewPayload);
    renderRerunPolicyPanel(lastRerunPreviewPayload);
    renderRerunHistorySummary();
    applyRerunPreviewButtonState();
  }

  function rerunPreviewBlockedReason(precollectedRequest = null) {
    const request = precollectedRequest && typeof precollectedRequest === "object"
      ? precollectedRequest
      : collectRerunStartRequest();
    if (!String(request.csv_path || "").trim()) return "CSV path is required before dry-run or live start.";
    if (request.destination_mode === "publish_replace_final" && request.confirm_replace_final !== true) {
      return "Publish and replace requires backend confirmation.";
    }
    if (request.original_policy && request.original_policy !== "keep" && request.confirm_original_policy !== true) {
      return "Old-source policy requires backend confirmation.";
    }
    if (request.original_policy === "hold_then_delete_after_publish" && request.confirm_delete_original !== true) {
      return "Hold/delete intent requires confirmation; deletion remains separate cleanup.";
    }
    if (!lastRerunPreviewPayload) return "Backend CSV preview has not loaded yet.";
    const counts = rerunPreviewCounts(lastRerunPreviewPayload);
    if (lastRerunPreviewPayload.status === "blocked") {
      const conflicts = rerunPreviewConflictLines(lastRerunPreviewPayload);
      return conflicts[0] || lastRerunPreviewPayload.message || "CSV preview is blocked.";
    }
    if (Number(counts.effective_scoped_rows || 0) <= 0) return "No effective scoped rows are available.";
    return "";
  }

  function applyRerunPreviewButtonState() {
    const busy = Boolean(launchCoordinatorState.launchCommandInFlight);
    const reason = rerunPreviewBlockedReason();
    const button = byId("rerun-start-button");
    if (!button) return;
    const disabled = busy || Boolean(reason);
    button.disabled = disabled;
    button.setAttribute("aria-disabled", disabled ? "true" : "false");
    button.title = disabled ? (reason || "Launch command is already in progress.") : "Review backend preview and start CSV rerun.";
  }

  async function refreshRerunPreview(options = {}) {
    const request = collectRerunPreviewRequest();
    renderLaunchPreflight("rerun-launch-preflight", rerunLaunchPreflightLines(collectRerunStartRequest({ dry_run: false })));
    if (!options.quiet) {
      setText("rerun-launch-status", "Reading CSV");
      setText("rerun-launch-detail", "Reading backend CSV rerun preview.");
    }
    try {
      const result = await apiPost("/api/rerun/preview", request);
      renderRerunPreview(result);
      if (!options.quiet) {
        setText("rerun-launch-status", result.status || (result.ok ? "Ready" : "Blocked"));
        renderJsonDetail("rerun-launch-detail", {
          label: "CSV rerun preview",
          value: result,
          intro: "Backend read-only CSV rerun preview.",
        });
      }
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "rerun.preview",
        ok: false,
        severity: "error",
        status: "blocked",
        message,
        errors: [message],
        counts: {},
        rows: [],
        recent_csvs: [],
      };
      renderRerunPreview(result);
      if (!options.quiet) {
        setText("rerun-launch-status", "Error");
        setText("rerun-launch-detail", message);
      }
      return result;
    }
  }

  function scheduleRerunPreviewRefresh(delayMs = 350) {
    if (rerunPreviewRefreshTimer) window.clearTimeout(rerunPreviewRefreshTimer);
    rerunPreviewRefreshTimer = window.setTimeout(() => {
      rerunPreviewRefreshTimer = null;
      refreshRerunPreview({ quiet: true }).catch(() => {});
    }, Math.max(0, Number(delayMs) || 0));
  }

  function rerunCsvLeaf(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.split(/[\\/]/).filter(Boolean).pop() || text;
  }

  function renderRerunTopbarPending(request, actionLabel, statusLabel, waitLabel) {
    const csvLeaf = rerunCsvLeaf(request.csv_path);
    const activity = csvLeaf ? `${actionLabel} ${statusLabel}: ${csvLeaf}` : `${actionLabel} ${statusLabel}`;
    window.mediaPipelineAppTopbar?.renderTopbarActivity?.({
      activity,
      current_work: { phase_label: actionLabel },
      progress: { CurrentStage: "CSV rerun" },
    });
    window.setTopbarPendingLaunch?.({
      label: actionLabel,
      status_label: statusLabel,
      wait_label: waitLabel,
    });
  }

  function renderRerunTopbarFinished(request, actionLabel, message) {
    const csvLeaf = rerunCsvLeaf(request.csv_path);
    const activity = csvLeaf ? `${message}: ${csvLeaf}` : message;
    window.clearTopbarPendingLaunch?.();
    window.mediaPipelineAppTopbar?.renderTopbarActivity?.({
      activity,
      current_work: { phase_label: actionLabel },
      progress: { CurrentStage: "CSV rerun" },
    });
  }

  async function startRerunFromForm(options = {}) {
    if (rejectLaunchCommandWhileBusy("rerun.start", "rerun-launch-status", "rerun-launch-detail")) return;
    const request = collectRerunStartRequest({ dry_run: false, plan_only: false });
    const actionLabel = "CSV rerun";
    const modeSummary = rerunStartPolicySummary(request);
    renderLaunchPreflight("rerun-launch-preflight", rerunLaunchPreflightLines(request));
    if (!request.csv_path.trim()) {
      const missing = {
        command: "rerun.start",
        ok: false,
        severity: "blocked",
        message: "CSV path is required.",
        frontend_guard: true,
      };
      renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", missing, request);
      applyRerunPreviewButtonState();
      return;
    }
    const preview = await refreshRerunPreview({ quiet: true });
    if (!preview || preview.status === "blocked") {
      const blocked = {
        command: "rerun.start",
        ok: false,
        severity: "blocked",
        message: preview?.message || "CSV rerun preview is blocked.",
        frontend_guard: true,
        data: preview || {},
      };
      renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", blocked, request);
      applyRerunPreviewButtonState();
      return;
    }
    const rerunButtonId = "rerun-start-button";
    const rerunBtn = byId(rerunButtonId);
    const rerunBtnText = rerunBtn ? rerunBtn.textContent : "";
    setLaunchCommandButtonState(rerunButtonId, "confirming", "Confirming...");
    setText("rerun-launch-status", "Confirming");
    setText("rerun-launch-detail", `Confirm live CSV rerun with ${modeSummary} policy.`);
    await nextLaunchCommandFrame();
    if (!window.confirm(`Start live CSV rerun with ${modeSummary} policy?`)) {
      const canceled = {
        command: "rerun.start",
        ok: false,
        severity: "info",
        message: `${actionLabel} canceled.`,
        data: { dry_run: Boolean(request.dry_run), plan_only: Boolean(request.plan_only) },
      };
      appendCommandResult(canceled);
      setText("rerun-launch-status", "Canceled");
      setText("rerun-launch-detail", canceled.message);
      if (rerunBtn) rerunBtn.textContent = rerunBtnText || "Review & Start";
      updateLaunchCommandButtonStates();
      return;
    }
    if (rerunBtn) rerunBtn.textContent = "Starting...";
    setLaunchCommandBusy(true);
    setText("rerun-launch-status", "Starting...");
    renderJsonDetail("rerun-launch-detail", {
      label: "Submitted request",
      value: request,
      intro: "Live CSV rerun request confirmed by the operator and about to be submitted.",
    });
    renderRerunTopbarPending(request, actionLabel, "submitted", "waiting for backend response");
    try {
      const result = await apiPost("/api/rerun/start", request);
      appendCommandResult(result);
      renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", result, request);
      if (result.ok) {
        const pidMatch = String(result.message || "").match(/\bPID\s*(\d+)\b/i);
        const pid = pidMatch ? pidMatch[1] : "";
        window.setTopbarPendingLaunch?.({
          label: actionLabel,
          pid,
          status_label: "accepted",
          wait_label: "waiting for backend event",
        });
        window.mediaPipelineAppTopbar?.renderTopbarActivity?.({
          activity: `${actionLabel} accepted${rerunCsvLeaf(request.csv_path) ? `: ${rerunCsvLeaf(request.csv_path)}` : ""}`,
          current_work: { phase_label: actionLabel },
          progress: { CurrentStage: "CSV rerun" },
        });
      } else {
        renderRerunTopbarFinished(request, actionLabel, `${actionLabel} did not start`);
      }
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      renderRerunTopbarFinished(request, actionLabel, `${actionLabel} failed: ${message}`);
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
      if (rerunBtn) rerunBtn.textContent = rerunBtnText || "Review & Start";
      applyRerunPreviewButtonState();
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
    collectRerunPreviewRequest,
    collectRerunScopeRequest,
    collectRerunStartRequest,
    refreshRerunPreview,
    inspectSelectedRerunCsv,
    openSelectedRerunCsv,
    renderRerunPreview,
    renderRerunHistorySummary,
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
})();
