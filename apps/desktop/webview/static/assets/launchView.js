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
        detail: "Backend auto-return policy replaces clean outputs and parks outputs with issue evidence in Pending Publish/review.",
        state: "ok",
      },
      auto_replace_clean_else_pending_review: {
        label: "Auto replace clean, else Pending Publish",
        detail: "Backend replaces clean verified outputs with strict confirmation; outputs with issue evidence are parked for Pending Publish/review.",
        state: "blocked",
      },
      review_workspace: {
        label: "Review workspace (review before final placement)",
        detail: "Verified outputs stay in review. Original source files are never replaced, and final library placement is not attempted from this selection.",
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
        detail: "Auto-return and final-replacement destinations resolve to replace-final collision; other destinations resolve to suffix.",
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
  let rerunFacade = {};

  function queueRerunRouteDispatcher(name) {
    const dispatcher = window.mediaPipelineQueueView?.[name];
    if (typeof dispatcher === "function") return dispatcher;
    throw new Error("Queue CSV Rerun route dispatcher is unavailable.");
  }

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
    launchActiveJobKind = function () { return ""; },
    launchRerunCsvIsActive = function () { return false; },
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
  } = launchStartRequest;
  const queueRerunRequestModule = window.__queueRerunRequestModule || {};
  delete window.__queueRerunRequestModule;
  const queueRerunRequest = typeof queueRerunRequestModule.createQueueRerunRequestModule === "function"
    ? queueRerunRequestModule.createQueueRerunRequestModule({
      byId: typeof byId === "function" ? byId : window.byId,
    })
    : {};
  const {
    collectRerunExecutionTarget = function () { return "local"; },
    collectRerunMinimumWorkerCount = function () { return 1; },
    collectRerunNetworkStartDryRunRequest = function () { return { csv_path: "", execution_mode: "one_at_a_time", destination_mode: "auto_replace_clean_else_pending_review", collision_policy: "replace_final", window_size: 1, scope: collectRerunScopeRequest(), minimum_worker_count: 1, reason: "WebView Network CSV rerun operator review" }; },
    collectRerunNetworkStartRequest = function (dryRunResult = {}) {
      const data = dryRunResult && typeof dryRunResult.data === "object" ? dryRunResult.data : dryRunResult;
      return { ...collectRerunNetworkStartDryRunRequest(), dry_run_fingerprint: String(data?.dry_run_fingerprint || ""), confirm_start: true };
    },
    collectRerunPreviewRequest = function () { return { csv_path: "", execution_mode: "one_at_a_time", destination_mode: "auto_replace_clean_else_pending_review", collision_policy: "replace_final", window_size: 1, scope: { enabled_only: true, skip_blocked: false, skip_warning_rows: false, first_n: 0, issue_filters: [], bucket_filters: [], preview_limit: 50 } }; },
    collectRerunScopeRequest = function () { return { enabled_only: true, skip_blocked: false, skip_warning_rows: false, first_n: 0, issue_filter: "", bucket_filter: "", preview_limit: 50 }; },
    collectRerunStartRequest = function (options = {}) { return { csv_path: "", dry_run: Boolean(options.dry_run), plan_only: Boolean(options.plan_only), execution_mode: "one_at_a_time", destination_mode: "auto_replace_clean_else_pending_review", collision_policy: "replace_final", window_size: 1, confirm_replace_final: true, confirm_source_overwrite: false, scope: collectRerunScopeRequest() }; },
      resolveRerunPolicySelection = function (raw = {}) {
        const destinationMode = raw.destination_mode && raw.destination_mode !== "auto"
          ? raw.destination_mode
        : raw.collision_policy === "replace_final" ? "auto_replace_clean_else_pending_review" : "review_workspace";
      const collisionPolicy = raw.collision_policy && raw.collision_policy !== "auto"
        ? raw.collision_policy
        : ["auto_replace_clean_else_pending_review", "publish_replace_final"].includes(destinationMode) ? "replace_final" : "suffix";
      return { destination_mode: destinationMode, collision_policy: collisionPolicy };
    },
  } = queueRerunRequest;

  function rerunExecutionTarget() {
    return collectRerunExecutionTarget() === "network" ? "network" : "local";
  }

  function rerunIsNetworkMode() {
    return rerunExecutionTarget() === "network";
  }

  function rerunPreviewRouteName() {
    return rerunIsNetworkMode() ? "/api/rerun/network-preview" : "/api/rerun/preview";
  }

  function rerunStartRouteName() {
    return rerunIsNetworkMode() ? "/api/rerun/network/start" : "/api/rerun/start";
  }

  function rerunExecutionTargetLabel() {
    return rerunIsNetworkMode() ? "Network CSV rerun" : "Local CSV rerun";
  }

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
      launchActiveJobKind,
      launchRerunCsvIsActive,
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
      launchBackendPreflightOverallStatus: (...args) => launchBackendPreflightOverallStatus(...args),
      launchBackendPreflightPayloadForTarget: (...args) => launchBackendPreflightPayloadForTarget(...args),
      launchBackendPreflightRows: (...args) => launchBackendPreflightRows(...args),
      launchPauseRequested,
      launchPipelineIsActive,
      launchActiveJobKind,
      launchRerunCsvIsActive,
      launchPreflightRequestMatches,
      launchStartDecisionPostureFromStatus: (...args) => launchStartDecisionPostureFromStatus(...args),
      launchStartDecisionRows: (...args) => launchStartDecisionRows(...args),
      launchStartDecisionStatus: (...args) => launchStartDecisionStatus(...args),
      launchStartDecisionWorstPosture: (...args) => launchStartDecisionWorstPosture(...args),
      pipelineProgressIsStuck,
      pipelineProgressIsStale,
      pipelineSingleFileValue,
      rerunPreviewBlockedReason: (...args) => rerunFacade.rerunPreviewBlockedReason(...args),
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
    return ["pipeline", "history"];
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
      button.addEventListener("keydown", (event) => {
        const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
        if (!keys.includes(event.key)) return;
        event.preventDefault();
        const current = buttons.indexOf(button);
        const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus();
        activateLaunchTab(buttons[next].dataset.launchTab || "pipeline");
      });
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
      getLastSettings: typeof window.mediaPipelineSettingsView?.getLastSettings === "function" ? () => window.mediaPipelineSettingsView.getLastSettings() : () => ({}),
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
  let refreshLaunchBackendPreflightEncoderCapability = async function () {};
  let pipelineLaunchPreflightLines = launchPreflightFallbackLines;
  let rerunQueuePreflightLines = launchPreflightFallbackLines;
  let renderLaunchPreflight = function (id, lines) { setText(id, (lines || []).join("\n")); };
  let renderAllLaunchPreflights = launchPreflightFallbackRender;
  let isPipelineControlCommand = function (entry) {
    const command = String(entry?.command || "").toLowerCase();
    return command.startsWith("pipeline.control.") || command.startsWith("rerun.control.");
  };
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
      setText("launch-latest-command-evidence", "No Launch command result loaded. Pipeline and Pending Publish command results appear here immediately after submission or cancellation. CSV rerun command history is reviewed from Queue > CSV Rerun.");
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
      apiGet: (...args) => window.mediaPipelineApi.apiGet(...args),
      apiPost: (...args) => window.mediaPipelineApi.apiPost(...args),
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
  refreshLaunchBackendPreflightEncoderCapability = typeof launchPreflight.refreshLaunchBackendPreflightEncoderCapability === "function" ? launchPreflight.refreshLaunchBackendPreflightEncoderCapability : refreshLaunchBackendPreflightEncoderCapability;
  pipelineLaunchPreflightLines = typeof launchPreflight.pipelineLaunchPreflightLines === "function" ? launchPreflight.pipelineLaunchPreflightLines : pipelineLaunchPreflightLines;
  rerunQueuePreflightLines = typeof launchPreflight.rerunQueuePreflightLines === "function" ? launchPreflight.rerunQueuePreflightLines : rerunQueuePreflightLines;
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

  const launchCommandOrchestrationFactory = window.__launchCommandOrchestrationModule || {};
  delete window.__launchCommandOrchestrationModule;
  const launchCommandOrchestration = launchCommandOrchestrationFactory.createLaunchCommandOrchestrationModule({
    Event: window.Event,
    apiPost: (...args) => window.mediaPipelineApi.apiPost(...args),
    appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
    byId: typeof byId === "function" ? byId : window.byId,
    collectPipelineStartRequest, confirmControlAction, controlActionLabels, initLaunchTabNav,
    launchPipelineIsActive, launchRerunCsvIsActive, nextLaunchCommandFrame,
    pendingDrainGuardState: (...args) => pendingDrainGuardState(...args),
    pipelineLaunchPreflightLines, pipelineModeLabel, queueRerunRouteDispatcher,
    refreshAll: (...args) => window.refreshAll(...args),
    refreshLaunchBackendPreflight, refreshLaunchBackendPreflightEncoderCapability,
    refreshRerunResults: (...args) => rerunFacade.refreshRerunResults(...args),
    rejectControlCommandWhileBusy, rejectLaunchCommandWhileBusy, renderAllLaunchPreflights,
    renderJsonDetail, renderLaunchCommandResult, renderLaunchCompactGate, renderLaunchPreflight,
    selectPipelineModePreset, selectPipelineScopePreset, setControlCommandBusy, setLaunchCommandBusy,
    setLaunchCommandButtonState, setPipelineControlMessage, setPipelineSingleFileBrowseStatus,
    setStartupBanner, setText: typeof setText === "function" ? setText : window.setText,
    state: launchCoordinatorState, syncPipelineModeControls, syncPipelineScopeControls, updateLaunchCommandButtonStates,
  });
  const {
    initLaunchViewEvents,
    initLaunchRecoveryActionEvents,
    requestPipelineControl,
    browsePipelineSingleFile,
    clearPipelineSingleFile,
    pipelineStartConfirmMessage,
    renderPipelineStartSafetySummary,
    startPipelineFromForm,
    startPendingPublishDrain,
    startStateJournalArchive,
  } = launchCommandOrchestration;

  const rerunFacadeFactory = window.__launchRerunFacade || {};
  delete window.__launchRerunFacade;
  rerunFacade = rerunFacadeFactory.createLaunchRerunFacade({
    appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
    byId: typeof byId === "function" ? byId : window.byId,
    collectRerunMinimumWorkerCount, collectRerunNetworkStartDryRunRequest, collectRerunNetworkStartRequest,
    collectRerunPreviewRequest, collectRerunScopeRequest, collectRerunStartRequest, launchCoordinatorState,
    nextLaunchCommandFrame, queueRerunRouteDispatcher,
    refreshAll: (...args) => window.refreshAll(...args),
    rejectLaunchCommandWhileBusy, renderAllLaunchPreflights, renderJsonDetail, renderLaunchCommandResult,
    renderLaunchPreflight, RERUN_EXECUTION_LABELS, RERUN_POLICY_CHOICES, rerunExecutionTargetLabel,
    rerunIsNetworkMode, rerunPreviewRouteName, rerunQueuePreflightLines, rerunStartRouteName,
    setLaunchCommandBusy, setLaunchCommandButtonState,
    setText: typeof setText === "function" ? setText : window.setText,
    updateLaunchCommandButtonStates,
  });

  function renderRerunQueuePreflight() {
    renderLaunchPreflight("rerun-queue-preflight", rerunQueuePreflightLines(collectRerunStartRequest({ dry_run: false })));
  }

  /**
   * Public namespace for the Queue CSV rerun workflow helpers.
   * Prefer this namespace from new code; flat window.* exports are not provided.
   */
  window.mediaPipelineCsvRerunWorkflow = {
    collectRerunExecutionTarget,
    collectRerunMinimumWorkerCount,
    collectRerunNetworkStartDryRunRequest,
    collectRerunNetworkStartRequest,
    collectRerunPreviewRequest,
    collectRerunScopeRequest,
    collectRerunStartRequest,
    ...rerunFacade,
    rerunQueuePreflightLines,
    renderRerunQueuePreflight,
  };

  /**
   * Public namespace for the Launch page module.
   * Prefer this namespace from new code over flat window.* exports; CSV rerun workflow helpers live on
   * window.mediaPipelineCsvRerunWorkflow.
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
    refreshLaunchBackendPreflightEncoderCapability,
    pipelineLaunchPreflightLines,
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
