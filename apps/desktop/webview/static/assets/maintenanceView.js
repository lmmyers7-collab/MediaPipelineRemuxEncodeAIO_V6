(function () {
  const commandHistoryView = window.mediaPipelineCommandHistory || {};
  const progressView = window.mediaPipelineProgressView || {};
  const renderProgressBarsInto = typeof progressView.renderProgressBarsInto === "function" ? progressView.renderProgressBarsInto : null;
  const maintenanceState = {
    lastMaintenance: null,
    lastChangeLedger: null,
    selectedMaintenanceRowKey: "",
    selectedChangeLedgerRowKey: "",
    maintenanceRefreshInFlight: false,
    maintenanceRefreshQueued: false,
    changeLedgerRefreshInFlight: false,
    maintenanceProgressPollTimer: null,
    lastReleasePreviewSignature: "",
    lastReleasePreviewOk: false,
    lastReleasePreviewMessage: "",
    maintenanceDryRunInFlight: false,
    dependencyAtlasOpenInFlight: false,
  };
  const CHANGE_LEDGER_ROW_LIMIT = 200;
  const CHANGE_LEDGER_REFRESH_TIMEOUT_MS = 120000;
  const maintenanceDryRunButtonIds = [
    "release-dry-run-button",
    "release-build-button",
    "backfill-dry-run-button",
    "dependency-atlas-button",
  ];
  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }

  function maintenanceStatusState(value) {
    const text = String(value || "").trim().toLowerCase();
    if (!text) return "empty";
    if (text === "not loaded" || text === "not checked" || text === "not selected" || text === "no selection"
        || text === "idle" || text === "none" || text === "no rows" || text.startsWith("no ")) return "empty";
    if (text.includes("stale")) return "stale";
    if (text.includes("skip")) return "skipped";
    if (text.includes("running") || text.includes("active") || text.includes("loading") || text.includes("checking")
        || text.includes("planning") || text.includes("building") || text.includes("updating") || text.includes("opening")
        || text.includes("requesting") || text.includes("busy")) return "running";
    if (text.includes("blocked") || text.includes("failed") || text.includes("error") || text.includes("missing")
        || text.includes("unavailable") || text.includes("invalid")) return "blocked";
    if (text.includes("warning") || text.includes("review") || text.includes("unknown") || text.includes("incomplete")
        || text.includes("limited")) return "warning";
    if (text === "ok" || text === "pass" || text === "ready" || text === "safe" || text === "complete"
        || text === "completed" || text === "loaded" || text === "match" || text.startsWith("ready")
        || text.includes("done")) return "ok";
    return "";
  }

  function setMaintenanceStatusText(id, text, state) {
    const normalized = maintenanceStatusState(state !== undefined ? state : text);
    if (typeof setTextState === "function") {
      setTextState(id, text, normalized);
      return;
    }
    setText(id, text);
    const node = byId(id);
    if (node) node.dataset.state = normalized;
  }

  function maintenanceTableRowStatus(value) {
    const state = maintenanceStatusState(value);
    if (state === "ok") return "match";
    if (state === "running") return "running";
    if (state === "blocked") return "blocked";
    if (state === "empty") return "empty";
    if (state === "stale") return "stale";
    if (state === "skipped") return "warning";
    return state || "unknown";
  }

  function releasePackageChipStatus(status) {
    const raw = String(status || "").trim().toLowerCase();
    if (raw === "complete" || raw === "ok") return raw;
    if (raw === "failed" || raw === "error" || raw === "blocked") return raw === "error" ? "error" : "failed";
    if (raw === "stale" || raw === "skipped") return raw;
    const state = maintenanceStatusState(raw);
    if (state === "running") return "running";
    if (state === "warning") return "warning";
    if (state === "blocked") return "failed";
    if (state === "empty") return "empty";
    return raw || "unknown";
  }

  function setMaintenanceDryRunBusy(isBusy) {
    maintenanceState.maintenanceDryRunInFlight = Boolean(isBusy);
    maintenanceDryRunButtonIds.forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = maintenanceState.maintenanceDryRunInFlight;
    });
  }

  function rejectMaintenanceDryRunWhileBusy(command, statusId, detailId) {
    if (!maintenanceState.maintenanceDryRunInFlight) return false;
    const result = {
      command,
      ok: false,
      severity: "warning",
      message: "Another maintenance command is already in progress.",
    };
    const releaseKind = releasePackageKindForCommand(command);
    if (releaseKind) setReleasePackageStatus(releaseKind, "warning", "Busy", result.message);
    appendCommandResult(result);
    setMaintenanceStatusText(statusId, "Busy", "running");
    if (detailId) setText(detailId, result.message);
    return true;
  }

  function setDependencyAtlasOpenBusy(isBusy) {
    maintenanceState.dependencyAtlasOpenInFlight = Boolean(isBusy);
    const button = byId("dependency-atlas-open-folder-button");
    if (button) button.disabled = maintenanceState.dependencyAtlasOpenInFlight;
  }

  function hasMaintenanceLoaded() {
    return maintenanceState.lastMaintenance !== null;
  }

  function getLastMaintenance() {
    return maintenanceState.lastMaintenance || {};
  }

  function getLastChangeLedger() {
    return maintenanceState.lastChangeLedger || {};
  }


  function maintenanceRowKey(item) {
    return String(item?.row_key || item?.name || "").trim();
  }

  function getSelectedMaintenanceRow() {
    const rows = Array.isArray(maintenanceState.lastMaintenance?.rows) ? maintenanceState.lastMaintenance.rows : [];
    return rows.find((item) => maintenanceRowKey(item) === maintenanceState.selectedMaintenanceRowKey) || null;
  }


  const maintenanceChangeLedgerModule = window.__maintenanceChangeLedgerModule;
  if (!maintenanceChangeLedgerModule?.createMaintenanceChangeLedger) {
    throw new Error("maintenance change-ledger module must load before maintenanceView.js");
  }
  const {
    changeLedgerRows,
    changeLedgerRowKey,
    getSelectedChangeLedgerRow,
    changeLedgerSummaryLines,
    changeLedgerCoverage,
    changeLedgerUnrecordedPaths,
    changeLedgerHygieneLines,
    renderChangeLedgerSummary,
    renderChangeLedgerHygiene,
    filteredChangeLedgerRows,
    renderChangeLedgerRows,
    changeLedgerDetailLines,
    renderChangeLedgerDetail,
    renderChangeLedger,
  } = maintenanceChangeLedgerModule.createMaintenanceChangeLedger({
    state: maintenanceState,
    setMaintenanceStatusText,
    maintenanceTableRowStatus,
  });
  delete window.__maintenanceChangeLedgerModule;

  const maintenanceHealthModule = window.__maintenanceHealthModule;
  if (!maintenanceHealthModule?.createMaintenanceHealth) {
    throw new Error("maintenance health module must load before maintenanceView.js");
  }
  const {
    selectMaintenanceRow,
    renderMaintenance,
    maintenanceProgressStatus,
    maintenanceProgressStepLines,
    maintenanceHealthErrorProgress,
    renderMaintenanceHealthProgress,
    pollMaintenanceProgress,
    startMaintenanceProgressPolling,
    stopMaintenanceProgressPolling,
    maintenanceDiagnosticsActionsForRow,
    renderMaintenanceDiagnosticsActions,
    maintenanceDetailLines,
    renderMaintenanceDetail,
    renderMaintenanceRows,
    maintenanceRequiredMissingRows,
    maintenanceOptionalWarningRows,
    maintenanceActiveRows,
    maintenanceReadinessStatus,
    activateQuickLink,
    maintenanceRealMediaBoundaryLines,
    maintenanceToolchainStatus,
    maintenanceToolchainLines,
    renderMaintenanceToolchain,
    maintenanceReadinessLines,
    renderMaintenanceReadiness,
    renderMaintenanceReadinessError,
  } = maintenanceHealthModule.createMaintenanceHealth({
    state: maintenanceState,
    renderProgressBarsInto,
    diagnosticsBridgeApi,
    setMaintenanceStatusText,
    maintenanceTableRowStatus,
    maintenanceRowKey,
    getSelectedMaintenanceRow,
    renderDryRunConfidence: (...args) => renderMaintenanceDryRunConfidence(...args),
  });
  delete window.__maintenanceHealthModule;

  const maintenanceDryRunReadinessModule = window.__maintenanceDryRunReadinessModule;
  if (!maintenanceDryRunReadinessModule?.createMaintenanceDryRunReadiness) {
    throw new Error("maintenance dry-run readiness module must load before maintenanceView.js");
  }
  const {
    isMaintenanceDryRunCommand,
    maintenanceDryRunLabel,
    maintenanceDryRunDetailLine,
    formatMaintenanceDryRunHistoryLine,
    renderMaintenanceDryRunHistory,
    maintenanceLatestDryRun,
    maintenanceDryRunConfidenceStatus,
    maintenanceReleaseOptionReviewLines,
    maintenanceDryRunConfidenceLines,
    renderMaintenanceDryRunConfidence,
    refreshChangeLedger,
    refreshMaintenance,
  } = maintenanceDryRunReadinessModule.createMaintenanceDryRunReadiness({
    state: maintenanceState,
    commandHistoryView,
    changeLedgerRowLimit: CHANGE_LEDGER_ROW_LIMIT,
    changeLedgerRefreshTimeoutMs: CHANGE_LEDGER_REFRESH_TIMEOUT_MS,
    setMaintenanceStatusText,
    renderChangeLedger,
    renderChangeLedgerDetail,
    renderMaintenance,
    maintenanceHealthErrorProgress,
    renderMaintenanceHealthProgress,
    renderMaintenanceReadinessError,
    renderDryRunProgressStart: startMaintenanceProgressPolling,
    stopMaintenanceProgressPolling,
    maintenanceReadinessStatus,
    maintenanceRequiredMissingRows,
    maintenanceOptionalWarningRows,
    maintenanceActiveRows,
    maintenanceRealMediaBoundaryLines,
    getReleaseDryRunRequest: (...args) => collectReleaseDryRunRequest(...args),
    getReleasePreviewMatchesCreate: (...args) => releasePreviewMatchesCreate(...args),
  });
  delete window.__maintenanceDryRunReadinessModule;

  const maintenanceReleaseCommandsModule = window.__maintenanceReleaseCommandsModule;
  if (!maintenanceReleaseCommandsModule?.createMaintenanceReleaseCommands) {
    throw new Error("maintenance release commands module must load before maintenanceView.js");
  }
  const {
    releaseRequestSignature,
    recordReleasePreviewResult,
    releasePreviewMatchesCreate,
    releaseBuildConfirmMessage,
    collectReleaseDryRunRequest,
    collectReleaseBuildRequest,
    releasePackageKindForCommand,
    setReleasePackageStatus,
    releasePackageResultHint,
    releasePackageResultStatus,
    renderReleasePackageInFlightProgress,
    initMaintenanceViewEvents,
    renderReleaseDryRunResult,
    releasePackageProgressBars,
    renderReleasePackageProgress,
    runReleaseDryRun,
    renderReleaseBuildResult,
    runReleaseBuild,
    renderBackfillDryRunResult,
    backfillProgressBars,
    renderBackfillProgress,
    runBackfillDryRun,
    dependencyAtlasProgressBars,
    renderDependencyAtlasProgress,
    renderDependencyAtlasResult,
    runDependencyAtlas,
    openDependencyAtlasFolder,
  } = maintenanceReleaseCommandsModule.createMaintenanceReleaseCommands({
    state: maintenanceState,
    renderProgressBarsInto,
    setMaintenanceStatusText,
    releasePackageChipStatus,
    setMaintenanceDryRunBusy,
    rejectMaintenanceDryRunWhileBusy,
    setDependencyAtlasOpenBusy,
    refreshMaintenance,
    refreshChangeLedger,
    renderChangeLedgerRows,
    renderDryRunConfidence: renderMaintenanceDryRunConfidence,
  });
  delete window.__maintenanceReleaseCommandsModule;

  /**
   * Public namespace for the Maintenance page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineMaintenanceView = {
    hasMaintenanceLoaded,
    getLastMaintenance,
    getLastChangeLedger,
    renderMaintenance,
    activateQuickLink,
    renderChangeLedger,
    renderChangeLedgerRows,
    renderChangeLedgerDetail,
    renderChangeLedgerSummary,
    renderChangeLedgerHygiene,
    changeLedgerSummaryLines,
    changeLedgerDetailLines,
    changeLedgerHygieneLines,
    changeLedgerCoverage,
    changeLedgerUnrecordedPaths,
    filteredChangeLedgerRows,
    refreshChangeLedger,
    renderMaintenanceRows,
    renderMaintenanceDetail,
    renderMaintenanceHealthProgress,
    maintenanceProgressStatus,
    maintenanceProgressStepLines,
    pollMaintenanceProgress,
    startMaintenanceProgressPolling,
    stopMaintenanceProgressPolling,
    maintenanceDetailLines,
    selectMaintenanceRow,
    getSelectedMaintenanceRow,
    maintenanceDiagnosticsActionsForRow,
    renderMaintenanceDiagnosticsActions,
    renderMaintenanceReadiness,
    renderMaintenanceToolchain,
    renderMaintenanceReadinessError,
    maintenanceStatusState,
    setMaintenanceStatusText,
    maintenanceTableRowStatus,
    maintenanceHealthErrorProgress,
    maintenanceReadinessStatus,
    maintenanceToolchainStatus,
    maintenanceToolchainLines,
    maintenanceRealMediaBoundaryLines,
    maintenanceReadinessLines,
    maintenanceDryRunConfidenceStatus,
    maintenanceDryRunConfidenceLines,
    renderMaintenanceDryRunConfidence,
    maintenanceReleaseOptionReviewLines,
    refreshMaintenance,
    setMaintenanceDryRunBusy,
    rejectMaintenanceDryRunWhileBusy,
    releaseRequestSignature,
    releasePreviewMatchesCreate,
    releaseBuildConfirmMessage,
    recordReleasePreviewResult,
    collectReleaseDryRunRequest,
    collectReleaseBuildRequest,
    initMaintenanceViewEvents,
    renderReleaseDryRunResult,
    renderReleaseBuildResult,
    renderReleasePackageProgress,
    renderReleasePackageInFlightProgress,
    releasePackageProgressBars,
    releasePackageKindForCommand,
    releasePackageResultStatus,
    setReleasePackageStatus,
    runReleaseDryRun,
    runReleaseBuild,
    renderBackfillDryRunResult,
    renderBackfillProgress,
    backfillProgressBars,
    renderDependencyAtlasResult,
    renderDependencyAtlasProgress,
    dependencyAtlasProgressBars,
    isMaintenanceDryRunCommand,
    renderMaintenanceDryRunHistory,
    runBackfillDryRun,
    runDependencyAtlas,
    openDependencyAtlasFolder,
  };
})();
