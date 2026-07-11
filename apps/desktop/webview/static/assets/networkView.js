(function () {
  const settingsOverview = window.mediaPipelineSettingsOverview || {};
  const configValue = typeof settingsOverview.configValue === "function" ? settingsOverview.configValue : null;
  const progressView = window.mediaPipelineProgressView || {};
  const renderProgressBarsInto = typeof progressView.renderProgressBarsInto === "function" ? progressView.renderProgressBarsInto : null;
  const fallbackNetworkKeys = [
    ["Mode", "NetworkRole", "Network Role", "How this workstation participates in network processing."],
    ["Coordinator", "CoordinatorPort", "Listen Port", "TCP port for the coordinator HTTP API."],
    ["Coordinator", "CoordinatorBindAddress", "Bind Address", "Local interface used by the coordinator API."],
    ["Coordinator", "CoordinatorAlsoEncodeLocally", "Encode Locally", "Whether the coordinator also claims local work."],
    ["Coordinator", "CoordinatorHeartbeatTimeoutMins", "Heartbeat Timeout", "Minutes before stale worker jobs are reclaimed."],
    ["Coordinator", "CoordinatorMaxJobRetries", "Max Same-Reason Retries", "Repeated same-reason worker/source failures before the coordinator suppresses redispatch to that worker."],
    ["Coordinator", "WorkerConfigOverrides", "Worker Overrides", "Disabled by backend policy; retained only for config compatibility."],
    ["Worker", "WorkerCoordinatorUrl", "Coordinator URL", "Remote coordinator endpoint used by this worker."],
    ["Worker", "WorkerName", "Worker Name", "Display name shown on the coordinator worker board."],
    ["Worker", "WorkerPollIntervalSecs", "Poll Interval", "Maximum seconds between coordinator claim attempts."],
    ["Worker", "WorkerSourcePathMap", "Source Path Map", "Path rewrites from coordinator UNC roots to local worker roots."],
  ];
  let lastNetworkWorkerRows = [];
  let lastNetworkWorkersPayload = {};
  let selectedNetworkWorkerKey = "";
  let selectedNetworkLifecycleKey = "";
  let selectedNetworkEvidenceKey = "";
  let selectedNetworkStateFileKey = "";
  let networkWorkerStatusFilter = "";
  let networkWorkerSearchText = "";
  let networkWorkerViewPreset = "";
  let networkViewEventsInitialized = false;
  let lastNetworkLifecyclePayload = {};
  const networkLifecycleDryRunEvidence = new Map();

  const __networkConfigDiagnosticsMod = window.__networkConfigDiagnosticsModule || {};
  delete window.__networkConfigDiagnosticsModule;
  const _networkConfigDiagnostics = typeof __networkConfigDiagnosticsMod.createNetworkConfigDiagnosticsModule === "function"
    ? __networkConfigDiagnosticsMod.createNetworkConfigDiagnosticsModule({
      byId: typeof byId === "function" ? byId : window.byId,
      configValue,
      fallbackNetworkKeys,
    })
    : {};
  const {
    coordinatorTarget = function () { return ""; },
    displayConfigValue = function (_config, _key, fallback = "") { return fallback; },
    isNetworkSecretSettingKey = function () { return false; },
    networkCoordinatorBindEndpoint = function () { return ""; },
    networkCoordinatorConnectivityLines = function () { return []; },
    networkDiagnosticLayerByKey = function () { return null; },
    networkDiagnosticLayers = function () { return {}; },
    networkDiagnosticLayerLines = function () { return []; },
    networkDiagnosticLayerPosture = function () { return "unknown"; },
    networkRows = function () { return []; },
    networkRuntimeStatus = function () { return { label: "Unknown", severity: "unknown" }; },
    networkStateFilesDiagnosticStatus = function () { return "unknown"; },
    networkStatusTone = function () { return "unknown"; },
    networkTokenPostureLines = function () { return []; },
    networkLifecycleStateFor = function (_payload, role) { return { role, status: "unknown", raw: {} }; },
    rawConfigValue = function (_config, _key, fallback = "") { return fallback; },
    redactedNetworkUrl = function () { return ""; },
    renderNetworkDiagnosticRail = function () {},
    settingsConfig = function () { return {}; },
    visibleNetworkMode = function () { return "standalone"; },
    visibleNetworkModeLabel = function () { return "Standalone"; },
  } = _networkConfigDiagnostics;

  const __networkStatusMod = window.__networkStatusModule || {};
  delete window.__networkStatusModule;
  const _networkStatus = typeof __networkStatusMod.createNetworkStatusModule === "function"
    ? __networkStatusMod.createNetworkStatusModule({
      byId,
      closeReadinessIsSafe: (...args) => closeReadinessIsSafe(...args),
      coordinatorTarget,
      documentRef: document,
      networkDiagnosticLayerByKey,
      networkDiagnosticLayerPosture,
      networkDiagnosticLayers,
      networkLifecycleDryRunRecord: (...args) => networkLifecycleDryRunRecord(...args),
      networkLifecycleRelevantRoles: (...args) => networkLifecycleRelevantRoles(...args),
      networkRuntimeStatus,
      networkStateFileCompactLines: (...args) => networkStateFileCompactLines(...args),
      networkStateFileRows: (...args) => networkStateFileRows(...args),
      networkStateFileStatus: (...args) => networkStateFileStatus(...args),
      networkStateFilesDiagnosticStatus,
      networkStatusTone,
      networkWorkerStatusState: (...args) => networkWorkerStatusState(...args),
      renderNetworkDiagnosticRail,
      setText,
      visibleNetworkMode,
      visibleNetworkModeLabel,
      workerHeartbeatText: (...args) => workerHeartbeatText(...args),
    })
    : {};
  const {
    networkAttentionItems = function () { return []; },
    renderNetworkAttentionStack = function () {},
    networkTopologyNodes = function () { return []; },
    renderNetworkTopologyStrip = function () {},
    setNetworkGate = function () {},
    renderNetworkActionReadinessGates = function () {},
    networkWorkerDriftPayload = function () { return {}; },
    networkWorkerDriftFieldText = function () { return "none"; },
    networkWorkerDriftStatusText = function () { return "Not loaded"; },
    networkWorkerDriftSummaryLines = function () { return []; },
    networkWorkerPolicyDivergencePayload = function () { return {}; },
    networkWorkerPolicyDivergenceText = function () { return "ready"; },
    networkWorkerPolicyDivergenceStatusText = function () { return "Not loaded"; },
    networkWorkerPolicyDivergenceActive = function () { return false; },
    networkWorkerPolicyDivergenceSummaryLines = function () { return []; },
    renderNetworkStatusBanner = function () {},
  } = _networkStatus;



  const __networkConfigMod = window.__networkConfigModule || {};
  delete window.__networkConfigModule;
  const _networkConfig = typeof __networkConfigMod.createNetworkConfigModule === "function"
    ? __networkConfigMod.createNetworkConfigModule({
      byId,
      documentRef: document,
      networkCoordinatorConnectivityLines,
      updatePagePanelEmptyStates: (...args) => {
        if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates(...args);
      },
      visibleNetworkMode,
    })
    : {};
  const {
    obviousWorkerCoordinatorUrlIssue = function () { return ""; },
    networkGuidance = function () { return []; },
    networkModeModelLines = function () { return []; },
    renderNetworkSummaryRows = function () {},
    networkRolePanelIds = function () { return []; },
    syncNetworkRoleDashboards = function () {},
  } = _networkConfig;



  const __networkQueueProjectionMod = window.__networkQueueProjectionModule || {};
  delete window.__networkQueueProjectionModule;
  const _networkQueueProjection = typeof __networkQueueProjectionMod.createNetworkQueueProjectionModule === "function"
    ? __networkQueueProjectionMod.createNetworkQueueProjectionModule()
    : {};
  const {
    networkBasename = function () { return ""; },
    networkClaimedKeySet = function () { return new Set(); },
    networkClaimIsActive = function () { return false; },
    networkDisplayValue = function (_value, fallback = "-") { return fallback; },
    networkMatchedQueueRow = function () { return null; },
    networkNumber = function (_value, fallback = 0) { return fallback; },
    networkPriorityText = function () { return "normal"; },
    networkQueueFileLabel = function () { return "Unknown file"; },
    networkQueueMatchMaps = function () { return { byPath: new Map() }; },
    networkQueueOrder = function (_row, index) { return index + 1; },
    networkQueueRowClaimed = function () { return false; },
    networkQueueRows = function () { return []; },
    networkQueueStatus = function () { return "Not loaded"; },
    networkReviewTile = function (label, value, detail = "", tone = "") { return { label, value, detail, tone }; },
    networkRouteEvidence = function () { return ""; },
    networkRouteLabel = function () { return ""; },
    networkRouteTone = function () { return "review"; },
    networkSizeText = function () { return "-"; },
    networkWorkerHasClaimEvidence = function () { return false; },
    networkWorkerLooksCompleteOrIdle = function () { return false; },
  } = _networkQueueProjection;

  const __networkLifecycleContractMod = window.__networkLifecycleContractModule || {};
  delete window.__networkLifecycleContractModule;
  const _networkLifecycleContract = typeof __networkLifecycleContractMod.createNetworkLifecycleContractModule === "function"
    ? __networkLifecycleContractMod.createNetworkLifecycleContractModule({
      closeReadinessLine: (...args) => closeReadinessLine(...args),
      networkCoordinatorJoinBlobRoute: (...args) => networkCoordinatorJoinBlobRoute(...args),
      networkWorkerDiscoverCoordinatorsRoute: (...args) => networkWorkerDiscoverCoordinatorsRoute(...args),
      networkWorkerJoinClusterRoute: (...args) => networkWorkerJoinClusterRoute(...args),
      networkWorkerTestConnectionRoute: (...args) => networkWorkerTestConnectionRoute(...args),
      rawConfigValue,
    })
    : {};
  const {
    contractSummary = function () { return ""; },
    configFlagText = function (_config, _key, fallback = "not configured") { return fallback; },
    configuredStatus = function () { return "not configured"; },
    networkPathMapStatus = function () { return "not configured"; },
    routeExists = function () { return false; },
    networkLifecycleBoundaryLines = function () { return []; },
    networkLifecycleBoundaryStatus = function () { return "Not loaded"; },
    networkLifecycleContractSummary = function () { return "Not loaded"; },
    networkLifecycleContracts = function () { return []; },
    networkLifecycleDryRunRouteCount = function () { return 0; },
    networkLifecycleMutationRouteCount = function () { return 0; },
    networkLifecycleRouteAvailable = function () { return false; },
    networkLifecycleRoutePath = function () { return ""; },
    networkLifecycleRouteRow = function () { return null; },
    networkRouteSummaryLines = function () { return []; },
    networkRouteSummaryStatus = function () { return "Not loaded"; },
    networkSetupMutationRouteRows = function () { return []; },
    networkSetupMutationRouteSummary = function () { return "none"; },
  } = _networkLifecycleContract;

  const __networkOverviewModelMod = window.__networkOverviewModelModule || {};
  delete window.__networkOverviewModelModule;
  const _networkOverviewModel = typeof __networkOverviewModelMod.createNetworkOverviewModelModule === "function"
    ? __networkOverviewModelMod.createNetworkOverviewModelModule({
      coordinatorTarget, displayConfigValue, networkBasename, networkClaimedKeySet, networkClaimIsActive,
      networkLifecycleRouteAvailable, networkMatchedQueueRow, networkNumber, networkPriorityText,
      networkQueueFileLabel, networkQueueMatchMaps, networkQueueOrder, networkQueueRowClaimed,
      networkQueueRows, networkQueueStatus, networkReviewTile, networkRouteEvidence, networkRouteLabel,
      networkRouteTone, networkSizeText, networkStateFileStatus: (...args) => networkStateFileStatus(...args),
      networkWorkerDriftFieldText: (...args) => networkWorkerDriftFieldText(...args),
      networkWorkerDriftPayload: (...args) => networkWorkerDriftPayload(...args),
      networkWorkerDriftStatusText: (...args) => networkWorkerDriftStatusText(...args),
      networkWorkerPolicyDivergenceActive: (...args) => networkWorkerPolicyDivergenceActive(...args),
      networkWorkerPolicyDivergenceStatusText: (...args) => networkWorkerPolicyDivergenceStatusText(...args),
      networkWorkerPolicyDivergenceText: (...args) => networkWorkerPolicyDivergenceText(...args),
      networkWorkerProgressStatus: (...args) => networkWorkerProgressStatus(...args),
      networkWorkerStatusState: (...args) => networkWorkerStatusState(...args),
      rawConfigValue, visibleNetworkModeLabel, workerHeartbeatText: (...args) => workerHeartbeatText(...args),
      workerProgressText: (...args) => workerProgressText(...args),
    })
    : {};
  const {
    networkCoordinatorOverviewModel = function () { return { status: "Unknown", activeRows: [], onDeckRows: [], tiles: [], summaryLines: [] }; },
    networkWorkerOverviewModel = function () { return { status: "Unknown", claimRows: [], tiles: [], summaryLines: [], remoteQueueSummary: "" }; },
  } = _networkOverviewModel;

  const __networkRoleDashboardMod = window.__networkRoleDashboardModule || {};
  delete window.__networkRoleDashboardModule;
  const _networkRoleDashboard = typeof __networkRoleDashboardMod.createNetworkRoleDashboardModule === "function"
    ? __networkRoleDashboardMod.createNetworkRoleDashboardModule({
      byId,
      clearRows,
      documentRef: document,
      networkCoordinatorOverviewModel,
      networkWorkerOverviewModel,
      renderOverviewTiles: typeof renderOverviewTiles === "function" ? renderOverviewTiles : function () {},
      renderNetworkWorkerRows: (...args) => renderNetworkWorkerRows(...args),
      setText,
      state: {
        get workerViewPreset() { return networkWorkerViewPreset; },
        set workerViewPreset(value) { networkWorkerViewPreset = String(value || ""); },
        get workersPayload() { return lastNetworkWorkersPayload; },
      },
      syncNetworkWorkerViewPresetButtons: (...args) => syncNetworkWorkerViewPresetButtons(...args),
    })
    : {};
  const {
    focusNetworkQuickLink = function () { return false; },
    activateQuickLink = function () { return true; },
    networkTileTone = function () { return "muted"; },
    networkStatusChip = function () { return null; },
    networkRouteChip = function () { return null; },
    networkAppendCell = function () { return null; },
    renderCoordinatorActiveRows = function () {},
    renderCoordinatorQueueRows = function () {},
    renderWorkerClaimRows = function () {},
    renderNetworkRoleDashboards = function () {},
  } = _networkRoleDashboard;




  const __networkLifecycleViewMod = window.__networkLifecycleViewModule || {};
  delete window.__networkLifecycleViewModule;
  const _networkLifecycleView = typeof __networkLifecycleViewMod.createNetworkLifecycleViewModule === "function"
    ? __networkLifecycleViewMod.createNetworkLifecycleViewModule({
      byId,
      coordinatorTarget,
      documentRef: document,
      networkLifecycleRouteAvailable,
      networkLifecycleRoutePath,
      networkLifecycleStateFor,
      networkRuntimeStatus,
      networkTokenPostureLines,
      obviousWorkerCoordinatorUrlIssue,
      renderNetworkDiagnosticRail,
      setText,
      state: {
        get dryRunEvidence() { return networkLifecycleDryRunEvidence; },
        get lifecyclePayload() { return lastNetworkLifecyclePayload; },
        set lifecyclePayload(value) { lastNetworkLifecyclePayload = value && typeof value === "object" ? value : {}; },
      },
      visibleNetworkMode,
      visibleNetworkModeLabel,
    })
    : {};
  const {
    networkLifecycleDryRunKey = function () { return ""; },
    closeReadinessIsSafe = function () { return false; },
    networkLifecycleFingerprint = function () { return ""; },
    networkLifecycleDryRunRecord = function () { return null; },
    pruneNetworkLifecycleDryRunEvidence = function () {},
    networkLifecycleDryRunAllowsConfirmed = function () { return false; },
    networkLifecycleDryRunRequirementLine = function () { return "Matching dry-run required."; },
    rememberNetworkLifecycleDryRun = function () {},
    networkWorkerTestConnectionRoute = function () { return ""; },
    networkCommandRouteByDataSchema = function () { return ""; },
    networkCoordinatorJoinBlobRoute = function () { return ""; },
    networkWorkerJoinClusterRoute = function () { return ""; },
    networkWorkerDiscoverCoordinatorsRoute = function () { return ""; },
    networkLifecycleRelevantRole = function () { return ""; },
    networkLifecycleRelevantRoles = function () { return []; },
    networkLifecycleControlLines = function () { return []; },
    setNetworkSetupRouteStatus = function () {},
    renderNetworkJoinControls = function () {},
    renderNetworkLifecycleControls = function () {},
  } = _networkLifecycleView;



  const __networkLifecycleResultsMod = window.__networkLifecycleResultsModule || {};
  delete window.__networkLifecycleResultsModule;
  const _networkLifecycleResults = typeof __networkLifecycleResultsMod.createNetworkLifecycleResultsModule === "function"
    ? __networkLifecycleResultsMod.createNetworkLifecycleResultsModule({
      byId,
      documentRef: document,
      renderNetworkJoinControls,
      setText,
      settingsConfig,
      state: {
        get lifecyclePayload() { return lastNetworkLifecyclePayload; },
      },
      windowRef: window,
    })
    : {};
  const {
    networkLifecycleCommandResultLines = function () { return []; },
    networkTestConnectionResultLines = function () { return []; },
    networkCoordinatorDiscoveryResultLines = function () { return []; },
    renderNetworkCoordinatorDiscoveryList = function () {},
    stageDiscoveredCoordinatorUrl = function () { return false; },
    networkJoinBlobResultLines = function () { return []; },
    networkJoinImportResultLines = function () { return []; },
  } = _networkLifecycleResults;



  const __networkSetupCommandsMod = window.__networkSetupCommandsModule || {};
  delete window.__networkSetupCommandsModule;
  const _networkSetupCommands = typeof __networkSetupCommandsMod.createNetworkSetupCommandsModule === "function"
    ? __networkSetupCommandsMod.createNetworkSetupCommandsModule({
      byId,
      confirmNetworkSetupCommand: (...args) => confirmNetworkSetupCommand(...args),
      networkCoordinatorDiscoveryResultLines,
      networkCoordinatorJoinBlobRoute,
      networkJoinBlobResultLines,
      networkJoinImportResultLines,
      networkWorkerDiscoverCoordinatorsRoute,
      networkWorkerJoinClusterRoute,
      postNetworkRoute: (...args) => postNetworkRoute(...args),
      refreshAll: (...args) => { if (typeof refreshAll === "function") refreshAll(...args); },
      renderNetworkCoordinatorDiscoveryList,
      renderNetworkJoinControls,
      setText,
      settingsConfig,
      state: {
        get lifecyclePayload() { return lastNetworkLifecyclePayload; },
      },
    })
    : {};
  const {
    createNetworkJoinBlob = async function () { return null; },
    copyNetworkJoinBlob = async function () { return false; },
    importNetworkJoinBlob = async function () { return null; },
    discoverNetworkCoordinators = async function () { return null; },
  } = _networkSetupCommands;



  const __networkLifecycleCommandsMod = window.__networkLifecycleCommandsModule || {};
  delete window.__networkLifecycleCommandsModule;
  const _networkLifecycleCommands = typeof __networkLifecycleCommandsMod.createNetworkLifecycleCommandsModule === "function"
    ? __networkLifecycleCommandsMod.createNetworkLifecycleCommandsModule({
      apiPost: (...args) => window.apiPost.apply(window, args),
      byId,
      coordinatorTarget,
      networkLifecycleCommandResultLines,
      networkLifecycleDryRunAllowsConfirmed,
      networkLifecycleDryRunRequirementLine,
      networkLifecycleRoutePath,
      networkLifecycleStateFor,
      networkTestConnectionResultLines,
      networkTokenPostureLines,
      networkWorkerTestConnectionRoute,
      obviousWorkerCoordinatorUrlIssue,
      rememberNetworkLifecycleDryRun,
      renderNetworkActionReadinessGates,
      renderNetworkLifecycleControls,
      refreshAll: (...args) => { if (typeof refreshAll === "function") refreshAll(...args); },
      setText,
      settingsConfig,
      state: {
        get lifecyclePayload() { return lastNetworkLifecyclePayload; },
      },
      visibleNetworkModeLabel,
    })
    : {};
  const {
    networkLifecycleConfirmationLines = function () { return []; },
    confirmNetworkLifecycleCommand = async function () { return false; },
    confirmNetworkSetupCommand = async function () { return false; },
    postNetworkRoute = async function () { throw new Error("Unsupported Network route."); },
    postNetworkLifecycleRoute = async function () { throw new Error("Unsupported Network route."); },
    runGuidedNetworkLifecycleCommand = async function () {},
    runNetworkLifecycleCommand = async function () {},
    runNetworkWorkerTestConnection = async function () { return null; },
  } = _networkLifecycleCommands;



  function networkOpenTargets() {
    return ["run_logs", "cluster_log", "active_jobs", "config", "state"];
  }

  function networkOpenCommandTarget(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object"
      ? raw.request
      : raw.submitted_request && typeof raw.submitted_request === "object"
        ? raw.submitted_request
        : {};
    return String(data.target || request.target || "").toLowerCase();
  }

  const __networkSettingsHandoffMod = window.__networkSettingsHandoffModule || {};
  delete window.__networkSettingsHandoffModule;
  const _networkSettingsHandoff = typeof __networkSettingsHandoffMod.createNetworkSettingsHandoffModule === "function"
    ? __networkSettingsHandoffMod.createNetworkSettingsHandoffModule({ byId, setText, windowRef: window })
    : {};
  const {
    networkSettingsPatchStatusText = function () { return "Staged Patch: none"; },
    renderNetworkSettingsPatchHandoff = function () {},
    previewNetworkSettingsPatch = async function () {},
    saveNetworkSettingsPatch = async function () {},
  } = _networkSettingsHandoff;



  const __networkOpenHistoryMod = window.__networkOpenHistoryModule || {};
  delete window.__networkOpenHistoryModule;
  const _networkOpenHistory = typeof __networkOpenHistoryMod.createNetworkOpenHistoryModule === "function"
    ? __networkOpenHistoryMod.createNetworkOpenHistoryModule({
      commandHistoryCompactEvidenceLine: typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null,
      networkOpenCommandTarget,
      networkOpenTargets,
      setText,
    })
    : {};
  const {
    isNetworkOpenCommand = function () { return false; },
    networkOpenHistoryLine = function () { return ""; },
    renderNetworkOpenHistory = function () {},
  } = _networkOpenHistory;



  const __networkReadinessMod = window.__networkReadinessModule || {};
  delete window.__networkReadinessModule;
  const _networkReadiness = typeof __networkReadinessMod.createNetworkReadinessModule === "function"
    ? __networkReadinessMod.createNetworkReadinessModule({
      configFlagText,
      coordinatorTarget,
      displayConfigValue,
      networkCoordinatorBindEndpoint,
      networkLifecycleBoundaryLines,
      networkLifecycleBoundaryStatus,
      networkPathMapStatus,
      networkRouteSummaryLines,
      networkRouteSummaryStatus,
      networkTokenPostureLines,
      routeExists,
      setText,
    })
    : {};
  const {
    closeReadinessLine = function () { return "Close readiness: not loaded"; },
    networkReadinessStatus = function () { return "Not loaded"; },
    snapshotStateLine = function () { return "Pipeline state: not loaded"; },
    networkReadinessLines = function () { return []; },
    renderNetworkReadiness = function () {},
  } = _networkReadiness;



  const __networkLifecycleModelMod = window.__networkLifecycleModelModule || {};
  delete window.__networkLifecycleModelModule;
  const _networkLifecycleModel = typeof __networkLifecycleModelMod.createNetworkLifecycleModelModule === "function"
    ? __networkLifecycleModelMod.createNetworkLifecycleModelModule({
      appendCells,
      byId,
      clearRows,
      closeReadinessLine,
      coordinatorTarget,
      displayConfigValue,
      documentRef: document,
      makeRowSelectable,
      networkCoordinatorBindEndpoint,
      networkLifecycleContractSummary,
      networkLifecycleContracts,
      networkLifecycleDryRunRouteCount,
      networkLifecycleMutationRouteCount,
      networkPathMapStatus,
      networkSetupMutationRouteRows,
      networkSetupMutationRouteSummary,
      networkStateFileCompactLines: (...args) => networkStateFileCompactLines(...args),
      networkStateFileStatus: (...args) => networkStateFileStatus(...args),
      networkWorkerRowsNeedingReview: (...args) => networkWorkerRowsNeedingReview(...args),
      networkWorkerStatusState: (...args) => networkWorkerStatusState(...args),
      routeExists,
      setText,
      snapshotStateLine,
      state: {
        get selectedLifecycleKey() { return selectedNetworkLifecycleKey; },
        set selectedLifecycleKey(value) { selectedNetworkLifecycleKey = String(value || ""); },
      },
      updateTableStatusLegend,
    })
    : {};
  const {
    networkLifecycleStatusState = function () { return "unknown"; },
    networkLifecycleGate = function () { return {}; },
    networkLifecycleRows = function () { return []; },
    networkLifecycleStatus = function () { return "Not loaded"; },
    networkLifecycleSummaryLines = function () { return []; },
    getSelectedNetworkLifecycleRow = function () { return null; },
    networkLifecycleDetailLines = function () { return []; },
    renderNetworkLifecycleHandoff = function () {},
  } = _networkLifecycleModel;



  const networkStateFilesModule = window.__networkStateFilesModule || {};
  delete window.__networkStateFilesModule;
  const networkStateFiles = typeof networkStateFilesModule.createNetworkStateFilesModule === "function"
    ? networkStateFilesModule.createNetworkStateFilesModule({
      byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend,
      networkStateFilesDiagnosticStatus,
      getSelectedKey: () => selectedNetworkStateFileKey,
      setSelectedKey: (value) => { selectedNetworkStateFileKey = value; },
    })
    : {};
  const {
    networkStateFileCompactLines = () => [],
    networkStateFileDetailLines = () => [],
    networkStateFileRows = () => [],
    networkStateFileStatus = () => "unknown",
    networkStateFileSummaryLines = () => [],
    renderNetworkStateFiles = () => {},
  } = networkStateFiles;

  const networkEvidenceModule = window.__networkEvidenceModule || {};
  delete window.__networkEvidenceModule;
  const networkEvidence = typeof networkEvidenceModule.createNetworkEvidenceModule === "function"
    ? networkEvidenceModule.createNetworkEvidenceModule({
      byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend,
      networkRuntimeStatus, networkLifecycleStateFor, networkLifecycleRelevantRoles,
      networkWorkerDriftPayload, networkWorkerDriftSummaryLines,
      networkWorkerPolicyDivergencePayload, networkWorkerPolicyDivergenceSummaryLines,
      networkDiagnosticLayerPosture, networkDiagnosticLayerLines, networkStateFilesDiagnosticStatus,
      networkStateFileCompactLines, networkStateFileSummaryLines, networkLifecycleControlLines, networkTokenPostureLines,
      networkCoordinatorConnectivityLines,
      networkWorkerStatusState: (...args) => networkWorkerStatusState(...args), routeExists, networkLifecycleContracts, networkPathMapStatus,
      configuredStatus, coordinatorTarget, displayConfigValue, networkCoordinatorBindEndpoint,
      configFlagText, closeReadinessLine, snapshotStateLine, networkLifecycleContractSummary,
      networkLifecycleDryRunRouteCount, networkLifecycleMutationRouteCount,
      networkSetupMutationRouteRows, networkSetupMutationRouteSummary,
      getSelectedKey: () => selectedNetworkEvidenceKey,
      setSelectedKey: (value) => { selectedNetworkEvidenceKey = value; },
    })
    : {};
  const {
    networkEvidenceRows = () => [],
    networkEvidenceStatus = () => "No evidence",
    networkEvidenceSummaryLines = () => [],
    renderNetworkEvidenceChecklist = () => {},
  } = networkEvidence;

  const __networkWorkersModelMod = window.__networkWorkersModelModule || {};
  delete window.__networkWorkersModelModule;
  const _networkWorkersModel = typeof __networkWorkersModelMod.createNetworkWorkersModelModule === "function"
    ? __networkWorkersModelMod.createNetworkWorkersModelModule({
      appendCells,
      byId,
      clearRows,
      documentRef: document,
      networkRows,
      networkWorkerHasClaimEvidence,
      networkWorkerLooksCompleteOrIdle,
      setText,
      state: {
        get selectedWorkerKey() { return selectedNetworkWorkerKey; },
        set selectedWorkerKey(value) { selectedNetworkWorkerKey = String(value || ""); },
        get workerRows() { return lastNetworkWorkerRows; },
        set workerRows(value) { lastNetworkWorkerRows = Array.isArray(value) ? value : []; },
        get workerSearchText() { return networkWorkerSearchText; },
        set workerSearchText(value) { networkWorkerSearchText = String(value || ""); },
        get workerStatusFilter() { return networkWorkerStatusFilter; },
        set workerStatusFilter(value) { networkWorkerStatusFilter = String(value || ""); },
        get workerViewPreset() { return networkWorkerViewPreset; },
        set workerViewPreset(value) { networkWorkerViewPreset = String(value || ""); },
      },
      workerHeartbeatText: (...args) => workerHeartbeatText(...args),
      workerProgressText: (...args) => workerProgressText(...args),
    })
    : {};
  const {
    renderNetworkSettingsRows = function () {},
    workerDisplayValue = function (value, fallback = "-") { return value ?? fallback; },
    networkWorkerRowKey = function () { return ""; },
    getSelectedNetworkWorkerRow = function () { return null; },
    networkWorkerStatusState = function () { return "unknown"; },
    networkWorkerFilterText = function () { return ""; },
    networkWorkerMatchesStatusFilter = function () { return true; },
    networkWorkerMatchesViewPreset = function () { return true; },
    filteredNetworkWorkerRows = function (rows) { return Array.isArray(rows) ? rows : []; },
    networkWorkerViewPresetLabel = function () { return "All"; },
    networkWorkerFilterLabel = function () { return "none"; },
    networkWorkerRowsNeedingReview = function () { return []; },
    renderNetworkWorkerFilterSummary = function () {},
    networkWorkerDetailLines = function () { return []; },
    workerLibraryCapabilityText = function () { return "unknown/not reported"; },
    workerPendingDoneReportText = function () { return "-"; },
    workerLastResultText = function () { return "-"; },
    workerThroughputText = function () { return "-"; },
  } = _networkWorkersModel;



  const __networkWorkersViewMod = window.__networkWorkersViewModule || {};
  delete window.__networkWorkersViewModule;
  const _networkWorkersView = typeof __networkWorkersViewMod.createNetworkWorkersViewModule === "function"
    ? __networkWorkersViewMod.createNetworkWorkersViewModule({
      byId,
      clearRows,
      documentRef: document,
      filteredNetworkWorkerRows,
      getSelectedNetworkWorkerRow,
      makeRowSelectable,
      networkAppendCell,
      networkStatusTone,
      networkWorkerDetailLines,
      networkWorkerDriftPayload,
      networkWorkerDriftStatusText,
      networkWorkerRowKey,
      networkWorkerStatusState,
      renderNetworkWorkerFilterSummary,
      renderProgressBarsInto,
      setText,
      state: {
        get lifecyclePayload() { return lastNetworkLifecyclePayload; },
        set lifecyclePayload(value) { lastNetworkLifecyclePayload = value && typeof value === "object" ? value : {}; },
        get selectedWorkerKey() { return selectedNetworkWorkerKey; },
        set selectedWorkerKey(value) { selectedNetworkWorkerKey = String(value || ""); },
        get workerRows() { return lastNetworkWorkerRows; },
        set workerRows(value) { lastNetworkWorkerRows = Array.isArray(value) ? value : []; },
        get workersPayload() { return lastNetworkWorkersPayload; },
        set workersPayload(value) { lastNetworkWorkersPayload = value && typeof value === "object" ? value : {}; },
      },
      syncNetworkWorkerViewPresetButtons: (...args) => syncNetworkWorkerViewPresetButtons(...args),
      updateTableStatusLegend,
      workerDisplayValue,
      workerLastResultText,
      workerPendingDoneReportText,
      workerThroughputText,
    })
    : {};
  const {
    appendNetworkInspectorRow = function () {},
    renderNetworkWorkerDetail = function () {},
    selectNetworkWorkerRow = function () {},
    workerHeartbeatText = function () { return "-"; },
    workerProgressText = function () { return "-"; },
    networkWorkerProgressStatus = function () { return "Not loaded"; },
    networkWorkerProgressSummaryLines = function () { return []; },
    renderNetworkWorkerProgress = function () {},
    renderNetworkWorkerRows = function () {},
  } = _networkWorkersView;



  function openNetworkDrawer(id) {
    const drawer = byId(id);
    if (!drawer) return;
    if ("open" in drawer) drawer.open = true;
    else drawer.setAttribute("open", "open");
    const summary = drawer.querySelector?.("summary");
    summary?.focus?.({ preventScroll: true });
  }

  function syncNetworkWorkerViewPresetButtons() {
    document.querySelectorAll("[data-network-worker-view]").forEach((button) => {
      const active = String(button.dataset.networkWorkerView || "") === String(networkWorkerViewPreset || "");
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.classList.toggle("is-active", active);
    });
  }

  const networkEventsModule = window.__networkEventsModule || {};
  delete window.__networkEventsModule;
  const networkEvents = typeof networkEventsModule.createNetworkEventsModule === "function"
    ? networkEventsModule.createNetworkEventsModule({
        byId,
        renderNetworkWorkerRows,
        syncNetworkWorkerViewPresetButtons,
        previewNetworkSettingsPatch,
        saveNetworkSettingsPatch,
        runNetworkLifecycleCommand,
        runNetworkWorkerTestConnection,
        openNetworkDrawer,
        createNetworkJoinBlob,
        copyNetworkJoinBlob,
        importNetworkJoinBlob,
        discoverNetworkCoordinators,
        stageDiscoveredCoordinatorUrl,
        renderNetworkJoinControls,
        settingsConfig,
        getLastNetworkLifecyclePayload: () => lastNetworkLifecyclePayload,
        getLastNetworkWorkersPayload: () => lastNetworkWorkersPayload,
        getNetworkViewEventsInitialized: () => networkViewEventsInitialized,
        setNetworkViewEventsInitialized: (value) => { networkViewEventsInitialized = Boolean(value); },
        getNetworkWorkerSearchText: () => networkWorkerSearchText,
        setNetworkWorkerSearchText: (value) => { networkWorkerSearchText = value; },
        getNetworkWorkerStatusFilter: () => networkWorkerStatusFilter,
        setNetworkWorkerStatusFilter: (value) => { networkWorkerStatusFilter = value; },
        getNetworkWorkerViewPreset: () => networkWorkerViewPreset,
        setNetworkWorkerViewPreset: (value) => { networkWorkerViewPreset = value; },
      })
    : {};
  const { initNetworkViewEvents = () => {} } = networkEvents;

  function renderNetworkWorkers(networkWorkers) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const workerState = payload.worker_state && typeof payload.worker_state === "object" ? payload.worker_state : {};
    setText(
      "network-worker-status",
      payload.error
        ? "Unavailable"
        : `${rows.length} worker row${rows.length === 1 ? "" : "s"}`
    );
    const lines = [
      payload.error ? `Persisted worker state: unavailable (${payload.error})` : "Persisted worker state: loaded",
      `State source: ${payload.source || "runtime_state_files"}`,
      `Runtime evidence role: ${payload.role || "unknown"}`,
      `Last reported active workers: ${payload.active_count || 0}`,
      `Last reported idle workers: ${payload.idle_count || 0}`,
      `Session completed from persisted state: ${payload.session_completed || 0}`,
      `Session failed from persisted state: ${payload.session_failed || 0}`,
      `Coordinator state file: ${payload.coordinator_inflight_path || "not resolved"}`,
      `Worker state file: ${payload.worker_state_path || "not resolved"}`,
      `Cluster log file: ${payload.cluster_log_path || "not resolved"}`,
      payload.role === "worker"
        ? "Worker mode note: the coordinator worker list is persisted on the coordinator host, not in this worker state folder."
        : "",
      ...networkDiagnosticLayerLines(payload).slice(0, 5),
      ...networkStateFileCompactLines(payload.state_files || []),
      "Lifecycle controls remain backend-owned. This panel is read-only persisted state, not a live coordinator control surface.",
    ].filter(Boolean);
    if (workerState.job_id || workerState.source_file || workerState.pending_done_report) {
      lines.push(
        "",
        "Local worker state:",
        `- Job: ${workerState.job_id || "(none)"}`,
        `- File: ${workerState.source_file || "(none)"}`,
        `- Pending done report: ${workerState.pending_done_report ? "yes" : "no"}`
      );
    }
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 8).forEach((warning) => lines.push(`- ${warning}`));
    }
    renderNetworkSummaryRows("network-worker-summary", lines);
    renderNetworkWorkerProgress(payload);
    renderNetworkWorkerRows(payload);
  }

  function networkRerunLeaf(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.split(/[\\/]/).filter(Boolean).pop() || text;
  }

  function networkRerunCompactPath(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const leaf = networkRerunLeaf(text);
    return leaf && leaf !== text ? `${leaf}\n${text}` : text;
  }

  const networkRerunEvidenceModule = window.__networkRerunEvidenceModule || {};
  delete window.__networkRerunEvidenceModule;
  const networkRerunEvidence = typeof networkRerunEvidenceModule.createNetworkRerunEvidenceModule === "function"
    ? networkRerunEvidenceModule.createNetworkRerunEvidenceModule({
      byId, setText, clearRows, networkAppendCell, networkStatusChip, networkRerunLeaf, networkRerunCompactPath,
    })
    : {};
  const { renderNetworkRerunRows = () => {} } = networkRerunEvidence;

  function renderNetworkView(payload = {}) {
    initNetworkViewEvents();
    const settings = payload.settings || {};
    const contract = payload.contract || {};
    const queue = payload.queue || {};
    const networkWorkers = payload.networkWorkers || {};
    const config = settingsConfig(settings);
    const role = String(rawConfigValue(config, "NetworkRole", "standalone") || "standalone").toLowerCase();
    const visibleRole = visibleNetworkMode(config);
    const pollInterval = displayConfigValue(config, "WorkerPollIntervalSecs", "not configured");
    const localApiState = contract?.schema_version ? "contract loaded" : "not loaded";
    const guidance = networkGuidance(visibleRole === "coordinator_local" ? "coordinator" : role, networkWorkers);

    setText("network-role", visibleNetworkModeLabel(config));
    setText("network-coordinator-target", coordinatorTarget(config, networkWorkers));
    setText("network-worker-poll", pollInterval);
    setText("network-local-api", localApiState);
    setText("network-status", settings.error ? "Settings unavailable" : "Backend lifecycle controls");
    renderNetworkStatusBanner(payload, config);
    renderNetworkTopologyStrip(config, networkWorkers);
    renderNetworkActionReadinessGates(payload, config);
    syncNetworkRoleDashboards(config);
    renderNetworkRoleDashboards({ queue, networkWorkers, config, contract });
    renderNetworkSummaryRows("network-summary", guidance);
    renderNetworkSummaryRows("network-mode-model", networkModeModelLines(visibleRole));
    setText("network-api-status", contract?.schema_version || "Not loaded");
    setText("network-api-summary", contractSummary(contract));
    renderNetworkReadiness(payload, role, config);
    renderNetworkLifecycleControls(payload, role, config);
    renderNetworkLifecycleHandoff(payload, role, config);
    renderNetworkEvidenceChecklist(payload, role, config);
    renderNetworkStateFiles(networkWorkers);
    renderNetworkSettingsRows(settings);
    renderNetworkSettingsPatchHandoff();
    renderNetworkRerunRows(payload.rerunResults || {});
    renderNetworkWorkers(networkWorkers);
    if (typeof getCommandHistory === "function") renderNetworkOpenHistory(getCommandHistory());
  }

  /**
   * Public namespace for the Workers page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineNetworkView = {
    networkRows,
    syncNetworkRoleDashboards,
    networkCoordinatorOverviewModel,
    networkWorkerOverviewModel,
    renderNetworkRoleDashboards,
    renderCoordinatorActiveRows,
    renderCoordinatorQueueRows,
    renderWorkerClaimRows,
    visibleNetworkMode,
    visibleNetworkModeLabel,
    networkReadinessLines,
    networkRuntimeStatus,
    networkStatusTone,
    networkDiagnosticLayerByKey,
    renderNetworkDiagnosticRail,
    networkWorkerDriftPayload,
    networkWorkerDriftFieldText,
    networkWorkerDriftStatusText,
    networkWorkerDriftSummaryLines,
    renderNetworkStatusBanner,
    obviousWorkerCoordinatorUrlIssue,
    networkLifecycleMutationRouteCount,
    networkAttentionItems,
    renderNetworkAttentionStack,
    networkTopologyNodes,
    renderNetworkTopologyStrip,
    renderNetworkActionReadinessGates,
    networkLifecycleDryRunRouteCount,
    networkSetupMutationRouteSummary,
    networkLifecycleRouteRow,
    networkLifecycleRoutePath,
    networkLifecycleRouteAvailable,
    networkLifecycleDryRunAllowsConfirmed,
    networkWorkerTestConnectionRoute,
    networkWorkerDiscoverCoordinatorsRoute,
    networkCoordinatorJoinBlobRoute,
    networkWorkerJoinClusterRoute,
    networkLifecycleRelevantRole,
    networkLifecycleRelevantRoles,
    networkLifecycleControlLines,
    networkLifecycleCommandResultLines,
    networkTestConnectionResultLines,
    networkCoordinatorDiscoveryResultLines,
    renderNetworkCoordinatorDiscoveryList,
    discoverNetworkCoordinators,
    stageDiscoveredCoordinatorUrl,
    networkJoinBlobResultLines,
    networkJoinImportResultLines,
    networkLifecycleRows,
    networkLifecycleStatus,
    networkLifecycleSummaryLines,
    networkLifecycleDetailLines,
    renderNetworkLifecycleHandoff,
    networkEvidenceRows,
    networkEvidenceStatus,
    networkEvidenceSummaryLines,
    renderNetworkEvidenceChecklist,
    networkStateFileRows,
    networkStateFileStatus,
    networkStateFileSummaryLines,
    networkStateFileDetailLines,
    renderNetworkStateFiles,
    renderNetworkRerunRows,
    networkWorkerRowKey,
    networkWorkerStatusState,
    networkWorkerFilterText,
    filteredNetworkWorkerRows,
    networkWorkerDetailLines,
    workerLastResultText,
    workerThroughputText,
    renderNetworkWorkerDetail,
    renderNetworkWorkerProgress,
    networkWorkerProgressStatus,
    networkWorkerProgressSummaryLines,
    selectNetworkWorkerRow,
    initNetworkViewEvents,
    renderNetworkWorkers,
    renderNetworkWorkerRows,
    networkOpenTargets,
    isNetworkOpenCommand,
    networkOpenHistoryLine,
    renderNetworkOpenHistory,
    renderNetworkSettingsPatchHandoff,
    activateQuickLink,
    renderNetworkLifecycleControls,
    runGuidedNetworkLifecycleCommand,
    runNetworkLifecycleCommand,
    runNetworkWorkerTestConnection,
    createNetworkJoinBlob,
    copyNetworkJoinBlob,
    importNetworkJoinBlob,
    previewNetworkSettingsPatch,
    saveNetworkSettingsPatch,
    renderNetworkView,
  };
})();
