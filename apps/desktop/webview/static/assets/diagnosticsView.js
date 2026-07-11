(function () {
  let diagnosticsOpenInFlight = false;

  const diagnosticsTailView = window.mediaPipelineDiagnosticsTailView || {};
  const selectedDiagnosticsTailTarget = diagnosticsTailView.selectedDiagnosticsTailTarget || window.selectedDiagnosticsTailTarget || function () { return ""; };
  const selectedDiagnosticsTailMaxBytes = diagnosticsTailView.selectedDiagnosticsTailMaxBytes || window.selectedDiagnosticsTailMaxBytes || function () { return "65536"; };
  const setDiagnosticsTailTarget = diagnosticsTailView.setDiagnosticsTailTarget || window.setDiagnosticsTailTarget || function () {};
  const setDiagnosticsTailStatus = diagnosticsTailView.setDiagnosticsTailStatus || window.setDiagnosticsTailStatus || function () {};
  const setDiagnosticsTailBusy = diagnosticsTailView.setDiagnosticsTailBusy || window.setDiagnosticsTailBusy || function () {};
  const renderDiagnosticsTail = diagnosticsTailView.renderDiagnosticsTail || window.renderDiagnosticsTail || function () {};
  const requestDiagnosticsTail = diagnosticsTailView.requestDiagnosticsTail || window.requestDiagnosticsTail || async function () {};
  const diagnosticsStateSummaryView = window.mediaPipelineDiagnosticsStateSummaryView || {};
  const diagnosticsStateOperatorStatus = diagnosticsStateSummaryView.diagnosticsStateOperatorStatus || function (item) {
    return item?.operator_status || item?.status || "";
  };
  const diagnosticsStateRecommendedFirstAction = diagnosticsStateSummaryView.diagnosticsStateRecommendedFirstAction || function () {
    return "inspect this state artifact.";
  };
  const commandHistoryView = window.mediaPipelineCommandHistory || {};

  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }

  let lastDiagnosticsLogRows = [];
  let tdarrMatrixConsoleState = null;


  function setDiagnosticsPanelStatus(id, message, state) {
    if (typeof setPanelStatus === "function") {
      setPanelStatus(id, message, state);
    } else {
      setText(id, message);
    }
  }

  function setDiagnosticsOpenStatus(message, state) {
    setDiagnosticsPanelStatus("diagnostics-open-status", message, state);
    setDiagnosticsPanelStatus("home-runtime-open-status", message, state);
  }

  function setDiagnosticsOpenBusy(isBusy, sourceButton = null) {
    diagnosticsOpenInFlight = Boolean(isBusy);
    if (!sourceButton || typeof setActionBusy === "function") return;
    sourceButton.disabled = diagnosticsOpenInFlight;
    sourceButton.setAttribute("aria-busy", diagnosticsOpenInFlight ? "true" : "false");
  }

  function rejectDiagnosticsOpenWhileBusy() {
    if (!diagnosticsOpenInFlight) return false;
    const result = {
      command: "diagnostics.open",
      ok: false,
      severity: "warning",
      message: "Another diagnostics open command is already in progress.",
    };
    appendCommandResult(result);
    setDiagnosticsOpenStatus(result.message, "loading");
    return true;
  }

  const diagnosticsMatrixConsoleModule = window.__diagnosticsMatrixConsoleModule;
  if (!diagnosticsMatrixConsoleModule?.createDiagnosticsMatrixConsoleModule) throw new Error("Missing Diagnostics Tdarr Matrix console module");
  delete window.__diagnosticsMatrixConsoleModule;
  const diagnosticsMatrixConsole = diagnosticsMatrixConsoleModule.createDiagnosticsMatrixConsoleModule({
    appendCells, appendCommandResult, apiGet, apiPost, byId, setDiagnosticsPanelStatus,
    setInlineActionStatus: window.setInlineActionStatus, setText,
  });
  const {
    getTdarrMatrixConsoleState, setTdarrMatrixAuditStatus, setTdarrMatrixAuditDetail, setTdarrMatrixAuditBusy,
    stopTdarrMatrixBackgroundPoll, scheduleTdarrMatrixBackgroundPoll, tdarrMatrixAuditActionLabel,
    tdarrMatrixDeleteConfirmReady, tdarrMatrixActionGate, updateTdarrMatrixActionGates,
    updateTdarrMatrixRerunButtons, renderTdarrMatrixAuditFindings, renderTdarrMatrixBucketCoverage,
    renderTdarrMatrixProofPackRows, renderTdarrMatrixRunComparison, renderTdarrMatrixConsole,
    requestTdarrMatrixConsole, requestTdarrMatrixEvidenceOpen, requestTdarrMatrixRerun,
    requestTdarrMatrixRunComparison, requestTdarrMatrixAudit,
  } = diagnosticsMatrixConsole;
  tdarrMatrixConsoleState = getTdarrMatrixConsoleState();
  function diagnosticsTextLines(value) {
    if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
    const text = String(value || "").trim();
    return text ? text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean) : [];
  }

  function diagnosticsLongRunReliabilityLines(autonomyHealth) {
    const health = autonomyHealth && typeof autonomyHealth === "object" ? autonomyHealth : {};
    const runtime = health.runtime_reliability && typeof health.runtime_reliability === "object" ? health.runtime_reliability : {};
    if (!Object.keys(runtime).length) return [];
    const continuous = runtime.continuous_round_state || {};
    const flags = runtime.control_flags || {};
    const pending = runtime.pending_publish_backpressure || {};
    const workers = runtime.worker_slots || {};
    const stateDb = runtime.state_db || {};
    const stateDbMaintenance = stateDb.last_maintenance && typeof stateDb.last_maintenance === "object" ? stateDb.last_maintenance : {};
    const lines = [
      `Autonomy health: ${health.overall_status || "unknown"}; blockers=${Number(health.blocked_count || 0)}; review=${Number(health.review_count || 0)}`,
      `Continuous rounds: consecutive_failures=${Number(continuous.consecutive_unexpected_round_failures || 0)}; blocked=${Boolean(continuous.blocked)}; probe_backoff_seconds=${Number(continuous.probe_backoff_seconds || 0)}`,
      `Control flags: pause=${Boolean(flags.pause_flag_present)}; pause_age_seconds=${flags.pause_age_seconds ?? "n/a"}; stop=${Boolean(flags.stop_flag_present)}`,
      `Pending backpressure: blocked=${Boolean(pending.blocked)}; reason=${pending.block_reason || "none"}; manifests=${Number(pending.manifest_count || 0)}; oldest_age_seconds=${pending.oldest_age_seconds ?? "n/a"}`,
      `Worker slots: active=${Number(workers.active_child_count || 0)}; stale_heartbeats=${Number(workers.stale_heartbeat_count || 0)}; oldest_age_seconds=${workers.oldest_child_age_seconds ?? "n/a"}`,
      `State DB: db_bytes=${Number(stateDb.db_size_bytes || 0)}; wal_bytes=${Number(stateDb.wal_size_bytes || 0)}; maintenance_ok=${stateDbMaintenance.ok ?? "n/a"}; maintenance_reason=${stateDbMaintenance.reason || "none"}`,
    ];
    return lines;
  }

  function progressCompactionKey(line) {
    const text = String(line || "").trim();
    const match = text.match(/^(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+)?(?:\[[A-Z]+\]\s+)?([A-Z][A-Z0-9_-]*)\s*:\s*(\d{1,3})%\s*$/i);
    if (!match) return "";
    return `${match[1].toUpperCase()}:${match[2]}`;
  }

  function compactRepeatedProgressLines(value) {
    const lines = diagnosticsTextLines(value);
    const compacted = [];
    let pending = null;
    const flushPending = () => {
      if (!pending) return;
      compacted.push(
        pending.count > 1
          ? `${pending.lastLine} (shown once; ${pending.count} repeated progress updates collapsed)`
          : pending.lastLine
      );
      pending = null;
    };

    lines.forEach((line) => {
      const key = progressCompactionKey(line);
      if (!key) {
        flushPending();
        compacted.push(line);
        return;
      }
      if (pending && pending.key === key) {
        pending.count += 1;
        pending.lastLine = line;
        return;
      }
      flushPending();
      pending = { key, lastLine: line, count: 1 };
    });
    flushPending();
    return compacted.join("\n");
  }

  function compactedDiagnosticsTextLines(value) {
    return diagnosticsTextLines(compactRepeatedProgressLines(value));
  }

  function setTextIfChanged(id, value) {
    const node = byId(id);
    const text = String(value || "");
    if (node && node.textContent === text) return;
    setText(id, text);
  }

  function diagnosticsSeverityForLine(line) {
    const text = String(line || "").toLowerCase();
    if (/\b(error|failed|failure|exception|traceback|unavailable|denied|blocked|corrupt|malformed|invalid|unreadable|locked)\b/.test(text)) {
      return "error";
    }
    if (/\b(warn|warning|stale|orphan|missing|retry|timeout|partial|unknown|skipped)\b/.test(text)) {
      return "warning";
    }
    if (/\b(active|running|processing|launching|publishing)\b/.test(text)) {
      return "active";
    }
    return "info";
  }

  function diagnosticsMalformedStateLines(lines) {
    return lines.filter((line) => /\b(corrupt|malformed|invalid|unreadable|locked|stale|orphan|pid|activejobs|progress)\b/i.test(line));
  }

  function boundedDiagnosticsText(value, maxChars = 1600) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.length <= maxChars ? text : `${text.slice(0, maxChars)}...`;
  }

  function diagnosticsRealMediaBoundaryLines() {
    return [
      "Real-media validation lens:",
      "- Diagnostics can prove only evidence that exists in backend logs, ActiveJobs, state artifacts, command history, manifests, sidecars, and pending-publish records.",
      "- A clean preview launch, build check, or release self-test is not proof of FFmpeg route correctness, subtitle OCR/SRT output, audio selection, Output Size Check behavior, source stability, or publish completion for a real media file.",
      "- Missing diagnostics evidence is not success. For first daily-driver validation, compare Last Stderr, Run Logs, Queue route fields, Completed output proof/size growth, and Pending Publish drain summary after a small known run.",
    ];
  }

  function diagnosticsActionLabel(action) {
    if (!action) return "";
    const bridge = diagnosticsBridgeApi();
    if (typeof bridge.diagnosticsBridgeActionLabel === "function") {
      return bridge.diagnosticsBridgeActionLabel(action);
    }
    const verb = action.kind === "tail" ? "Read" : "Open";
    return action.label || `${verb} ${String(action.target || "").replaceAll("_", " ")}`;
  }

  function diagnosticsOrderedActions(actions) {
    const candidates = Array.isArray(actions) ? actions.filter((action) => action && action.target) : [];
    const bridge = diagnosticsBridgeApi();
    if (typeof bridge.diagnosticsBridgeOrderedActions === "function") {
      return bridge.diagnosticsBridgeOrderedActions(candidates);
    }
    return candidates;
  }

  function diagnosticsActionGroups(actions) {
    const ordered = diagnosticsOrderedActions(actions);
    return {
      readFirst: ordered.filter((action) => action.kind === "tail"),
      openNext: ordered.filter((action) => action.kind !== "tail"),
    };
  }

  function diagnosticsActionGroupText(actions) {
    return actions.length ? actions.map(diagnosticsActionLabel).join(" -> ") : "none inferred";
  }

  function diagnosticsActionPlanLines(sourceLabel, actions, contextText = "") {
    const groups = diagnosticsActionGroups(actions);
    const lines = [
      "Diagnostics action plan:",
      `Source: ${sourceLabel || "selected diagnostics row"}`,
      `Read first: ${diagnosticsActionGroupText(groups.readFirst)}`,
      `Open next: ${diagnosticsActionGroupText(groups.openNext)}`,
    ];
    if (contextText) lines.push(`Why: ${contextText}`);
    lines.push("Order rationale: read bounded backend text first when available, then shell-open folders/files only when more context is needed.");
    lines.push("Guardrail: action targets are backend allowlist identifiers, not frontend filesystem paths.");
    return lines;
  }

  function appendDiagnosticsActionGroup(container, groupLabel, actions) {
    const actionRows = Array.isArray(actions) ? actions : [];
    if (!container || !actionRows.length) return;
    const key = String(groupLabel || "").toLowerCase().includes("read") ? "readFirst" : "openNext";
    const groups = { readFirst: [], openNext: [] };
    groups[key] = actionRows;
    window.mediaPipelineDom?.renderOpenTargetActionGroups?.(container, groups, {
      append: true,
      labelFor: diagnosticsActionLabel,
      groupDataset: "diagnosticsActionGroup",
      actionDataset: "diagnosticsLogAction",
      targetDataset: "diagnosticsLogTarget",
      onTail: (target, _action, button) => requestDiagnosticsTail(target, button),
      onOpen: (target, _action, button) => requestDiagnosticsOpen(target, button),
    });
    const groupValue = String(groupLabel || "").toLowerCase().replace(/\s+/g, "-");
    container.querySelectorAll("button[data-open-target-action-group]").forEach((button) => {
      if (button.dataset.openTargetActionGroup !== groupValue) return;
      if (button.dataset.openTargetAction === "tail") {
        button.dataset.readDiagnosticsTail = button.dataset.openTarget || "";
      } else {
        button.dataset.openDiagnostics = button.dataset.openTarget || "";
      }
    });
  }

  function diagnosticsArtifactsForLine(line) {
    const text = String(line || "");
    return diagnosticsArtifactTargets
      .filter((artifact) => artifact.patterns.some((pattern) => pattern.test(text)))
      .slice(0, 4);
  }

  function initDiagnosticsViewEvents() {
    const logFilter = byId("diagnostics-log-filter");
    if (logFilter) logFilter.addEventListener("input", () => renderDiagnosticsLogTable());
    const logSeverity = byId("diagnostics-log-severity");
    if (logSeverity) logSeverity.addEventListener("change", () => renderDiagnosticsLogTable());
    const tailButton = byId("diagnostics-tail-refresh-button");
    if (tailButton) tailButton.addEventListener("click", requestDiagnosticsTail);
    document.querySelectorAll("[data-read-diagnostics-tail]").forEach((button) => {
      if (button.dataset.diagnosticsTailBound === "true") return;
      button.dataset.diagnosticsTailBound = "true";
      button.addEventListener("click", () => requestDiagnosticsTail(button.dataset.readDiagnosticsTail || "", button));
    });
    document.querySelectorAll("[data-tdarr-matrix-audit-action]").forEach((button) => {
      button.addEventListener("click", () => requestTdarrMatrixAudit(button.dataset.tdarrMatrixAuditAction || ""));
    });
    const tdarrDeleteConfirm = byId("tdarr-matrix-delete-confirm");
    if (tdarrDeleteConfirm) tdarrDeleteConfirm.addEventListener("input", updateTdarrMatrixActionGates);
    document.querySelectorAll("[data-tdarr-proof-pack-view]").forEach((button) => {
      button.addEventListener("click", () => {
        tdarrMatrixConsoleState.activePack = button.dataset.tdarrProofPackView || "proof-pack";
        renderTdarrMatrixProofPackRows();
      });
    });
    const tdarrFilter = byId("tdarr-matrix-audit-filter");
    if (tdarrFilter) tdarrFilter.addEventListener("input", () => {
      renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings });
      renderTdarrMatrixProofPackRows();
    });
    const tdarrSeverity = byId("tdarr-matrix-audit-severity-filter");
    if (tdarrSeverity) tdarrSeverity.addEventListener("change", () => renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings }));
    const tdarrBucket = byId("tdarr-matrix-audit-bucket-filter");
    if (tdarrBucket) tdarrBucket.addEventListener("change", () => {
      renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings });
      renderTdarrMatrixProofPackRows();
    });
    const tdarrLoadLatest = byId("tdarr-matrix-audit-load-latest");
    if (tdarrLoadLatest) tdarrLoadLatest.addEventListener("click", () => requestTdarrMatrixConsole());
    const tdarrRerunSelected = byId("tdarr-matrix-audit-rerun-selected");
    if (tdarrRerunSelected) tdarrRerunSelected.addEventListener("click", () => requestTdarrMatrixRerun("selected"));
    const tdarrRerunFailures = byId("tdarr-matrix-audit-rerun-failures");
    if (tdarrRerunFailures) tdarrRerunFailures.addEventListener("click", () => requestTdarrMatrixRerun("latest_failures"));
    const compareRefresh = byId("tdarr-matrix-compare-refresh");
    if (compareRefresh) compareRefresh.addEventListener("click", requestTdarrMatrixRunComparison);
    updateTdarrMatrixActionGates();
  }

  const diagnosticsArtifactTargets = [
    {
      name: "BDPGS OCR settings evidence",
      target: "",
      patterns: [/\bbdpgs\b/i, /\bpgs(?:tosrt|[-_\s]to[-_\s]srt)?\b/i, /\bpgstosrt\b/i, /\btessdata\b/i, /\btesseract\b/i, /\bocr\b/i, /\bsubtitle(?:s)?\b.*\bsrt\b/i],
      hint: "Select the Diagnostics State Artifact Summary row 'settings_bdpgs_ocr_paths' and then review Settings > Media Output if saved OCR tool or tessdata path evidence is blocked. Diagnostics does not edit settings or run OCR.",
    },
    {
      name: "VobSub OCR settings evidence",
      target: "",
      patterns: [/\bvobsub\b/i, /\bdvd[_\s-]?subtitle\b/i, /\bs[_-]?vobsub\b/i, /\bseconv\b/i, /\btesseract\b/i, /\bidx\b/i, /\bsub\b/i, /\bocr\b/i, /\bsubtitle(?:s)?\b.*\bsrt\b/i],
      hint: "Select the Diagnostics State Artifact Summary row 'settings_vobsub_ocr_paths' and then review Settings > Media Output if saved Subtitle Edit or Tesseract evidence is blocked. Diagnostics does not edit settings or run OCR.",
    },
    {
      name: "ActiveJobs",
      target: "active_jobs",
      patterns: [/\bactivejobs\b/i, /\bactive job/i, /\borphan(?:ed)?\b/i, /\bpid\b/i, /\brunning\b/i, /\blaunching\b/i],
      hint: "Open Active Jobs and compare with Close Readiness before closing or clearing runtime state.",
    },
    {
      name: "Progress state",
      target: "state",
      patterns: [/\bprogress\b/i, /\bpipeline_progress\b/i, /\bcurrentstagepercent\b/i],
      hint: "Open State Folder and Run Logs; malformed progress can hide live work from the shell.",
    },
    {
      name: "Run logs",
      target: "run_logs",
      tailTarget: "last_stderr_log",
      tailName: "Last Stderr",
      patterns: [/\berror\b/i, /\bexception\b/i, /\btraceback\b/i, /\bffmpeg\b/i, /\bstderr\b/i, /\bfailed\b/i, /\bfailure\b/i],
      hint: "Open Run Logs and Last Stderr first, then check the newest failure or audit report if present.",
    },
    {
      name: "Launch logs",
      target: "last_stderr_log",
      tailTarget: "last_stderr_log",
      tailName: "Last Stderr",
      patterns: [/\blaunch\b/i, /\bstdout\b/i, /\bstderr\b/i, /\bstart(?:ed)?\b/i, /\bsubprocess\b/i],
      hint: "Open Last Stdout and Last Stderr to inspect the launcher boundary.",
    },
    {
      name: "Queue snapshot",
      target: "queue_snapshot",
      tailTarget: "queue_snapshot",
      tailName: "Queue Snapshot",
      patterns: [/\bqueue\b/i, /\bclaim\b/i, /\breclaim\b/i, /\bskipped\b/i, /\brunnable\b/i],
      hint: "Open Queue Snapshot when processing appears idle but rows should be runnable.",
    },
    {
      name: "Pending publish",
      target: "pending_publish",
      tailTarget: "last_stderr_log",
      tailName: "Last Stderr",
      patterns: [/\bpending publish\b/i, /\bpublish\b/i, /\bpark(?:ed)?\b/i, /\bdeferred\b/i, /\bdrain\b/i, /\borphan payload\b/i, /\bmissing sidecar\b/i, /\bunreadable manifest\b/i, /\binvalid manifest\b/i],
      hint: "Open Pending Folder and Run Logs before rerunning work that may already be parked, orphaned, or blocked by malformed manifests.",
    },
    {
      name: "Failure reports",
      target: "failed_reports",
      tailTarget: "latest_failure_report",
      tailName: "Latest Failure Report",
      patterns: [/\bfailure report\b/i, /\bfailed marker\b/i, /\bclassification\b/i, /\bremediation\b/i],
      hint: "Open Failure Reports and Failure Markers to confirm the last deterministic failure class.",
    },
    {
      name: "Cluster log",
      target: "cluster_log",
      tailTarget: "cluster_log",
      tailName: "Cluster Log",
      patterns: [/\bworker\b/i, /\bcoordinator\b/i, /\bcluster\b/i, /\bheartbeat\b/i, /\bnetwork\b/i],
      hint: "Open Cluster Log for coordinator/worker events. WebView network lifecycle remains read-only.",
    },
  ];

const diagnosticsActiveJobsModule = window.__diagnosticsActiveJobsModule || {};
delete window.__diagnosticsActiveJobsModule;
const diagnosticsActiveJobs = typeof diagnosticsActiveJobsModule.createDiagnosticsActiveJobsModule === "function"
  ? diagnosticsActiveJobsModule.createDiagnosticsActiveJobsModule({
    appendCells,
    appendDiagnosticsActionGroup,
    boundedDiagnosticsText,
    byId,
    clearRows,
    diagnosticsActionGroups,
    diagnosticsActionPlanLines,
    makeRowSelectable,
    setText,
    updateTableStatusLegend,
  })
  : {};
const activeJobRowKey = diagnosticsActiveJobs.activeJobRowKey || function () { return ""; };
const getSelectedActiveJobRow = diagnosticsActiveJobs.getSelectedActiveJobRow || function () { return null; };
const selectActiveJobRow = diagnosticsActiveJobs.selectActiveJobRow || function () {};
const activeJobDiagnosticsActions = diagnosticsActiveJobs.activeJobDiagnosticsActions || function () { return []; };
const activeJobRowPosture = diagnosticsActiveJobs.activeJobRowPosture || function () { return "review"; };
const activeJobRowsStatusText = diagnosticsActiveJobs.activeJobRowsStatusText || function () { return "No ActiveJobs rows"; };
const diagnosticsActiveJobRealMediaTraceLines = diagnosticsActiveJobs.diagnosticsActiveJobRealMediaTraceLines || function () { return []; };
const renderActiveJobDiagnosticsActions = diagnosticsActiveJobs.renderActiveJobDiagnosticsActions || function () {};
const renderActiveJobRows = diagnosticsActiveJobs.renderActiveJobRows || function () {};
const renderActiveJobDetail = diagnosticsActiveJobs.renderActiveJobDetail || function () {};

  const diagnosticsTriageModule = window.__diagnosticsTriageModule;
  if (!diagnosticsTriageModule?.createDiagnosticsTriageModule) throw new Error("Missing Diagnostics triage module");
  delete window.__diagnosticsTriageModule;
  const diagnosticsTriage = diagnosticsTriageModule.createDiagnosticsTriageModule({
    appendDiagnosticsActionGroup, byId, diagnosticsActionGroups, diagnosticsActionPlanLines,
    diagnosticsArtifactsForLine, diagnosticsLongRunReliabilityLines, diagnosticsTextLines,
    compactedDiagnosticsTextLines, setDiagnosticsPanelStatus, setText,
  });
  const {
    diagnosticsSourceLines, diagnosticsArtifactMatches, renderDiagnosticsDrilldownActions,
    renderDiagnosticsDrilldown, renderDiagnosticsTriage, diagnosticsFormatCounts,
    diagnosticsSafeRows, diagnosticsFirstResponseAdd,
  } = diagnosticsTriage;

const diagnosticsLogModule = window.__diagnosticsLogModule || {};
delete window.__diagnosticsLogModule;
const diagnosticsLog = typeof diagnosticsLogModule.createDiagnosticsLogModule === "function"
  ? diagnosticsLogModule.createDiagnosticsLogModule({
    appendCells,
    appendDiagnosticsActionGroup,
    boundedDiagnosticsText,
    byId,
    clearRows,
    diagnosticsActionGroups,
    diagnosticsActionPlanLines,
    diagnosticsArtifactsForLine,
    diagnosticsSeverityForLine,
    diagnosticsSourceLines,
    makeRowSelectable,
    readLastDiagnosticsLogRows: () => lastDiagnosticsLogRows,
    setText,
    updateTableStatusLegend,
    writeLastDiagnosticsLogRows: (rows) => { lastDiagnosticsLogRows = Array.isArray(rows) ? rows : []; },
  })
  : {};
const diagnosticsLineTimestamp = diagnosticsLog.diagnosticsLineTimestamp || function () { return ""; };
const diagnosticsLogRows = diagnosticsLog.diagnosticsLogRows || function () { return []; };
const diagnosticsLogRowKey = diagnosticsLog.diagnosticsLogRowKey || function () { return ""; };
const diagnosticsLogRowActions = diagnosticsLog.diagnosticsLogRowActions || function () { return []; };
const diagnosticsLogRowNextStep = diagnosticsLog.diagnosticsLogRowNextStep || function () { return ""; };
const diagnosticsLogRealMediaTraceLines = diagnosticsLog.diagnosticsLogRealMediaTraceLines || function () { return []; };
const diagnosticsLogGuidanceLines = diagnosticsLog.diagnosticsLogGuidanceLines || function () { return []; };
const renderDiagnosticsLogActions = diagnosticsLog.renderDiagnosticsLogActions || function () {};
const filteredDiagnosticsLogRows = diagnosticsLog.filteredDiagnosticsLogRows || function () { return []; };
const getLastDiagnosticsLogRows = diagnosticsLog.getLastDiagnosticsLogRows || function () { return lastDiagnosticsLogRows.slice(); };
const selectDiagnosticsLogRow = diagnosticsLog.selectDiagnosticsLogRow || function () {};
const getSelectedDiagnosticsLogRow = diagnosticsLog.getSelectedDiagnosticsLogRow || function () { return null; };
const renderDiagnosticsLogRows = diagnosticsLog.renderDiagnosticsLogRows || function () {};
const renderDiagnosticsLogDetail = diagnosticsLog.renderDiagnosticsLogDetail || function () {};
const renderDiagnosticsLogTable = diagnosticsLog.renderDiagnosticsLogTable || function () {};


  const diagnosticsFirstResponseModule = window.__diagnosticsFirstResponseModule;
  if (!diagnosticsFirstResponseModule?.createDiagnosticsFirstResponseModule) throw new Error("Missing Diagnostics first-response module");
  delete window.__diagnosticsFirstResponseModule;
  const diagnosticsFirstResponse = diagnosticsFirstResponseModule.createDiagnosticsFirstResponseModule({
    appendCells, appendDiagnosticsActionGroup, byId, clearRows, commandHistoryView, diagnosticsActionGroups,
    diagnosticsConflictSignalLabel: (...args) => diagnosticsConflictSignalLabel(...args), diagnosticsFirstResponseAdd, diagnosticsFormatCounts, diagnosticsLogRows,
    diagnosticsMalformedStateLines, diagnosticsRealMediaBoundaryLines, diagnosticsStateOperatorStatus: (...args) => diagnosticsStateOperatorStatus(...args),
    diagnosticsStateRecommendedFirstAction: (...args) => diagnosticsStateRecommendedFirstAction(...args), diagnosticsTextLines, makeRowSelectable, setDiagnosticsPanelStatus,
    setText, updateTableStatusLegend,
  });
  const {
    diagnosticsFirstResponsePostureStatus, diagnosticsSamplePolicyReconciliation, diagnosticsFirstResponseRows,
    diagnosticsFirstResponseStatus, diagnosticsFirstResponseSummaryLines, selectedDiagnosticsFirstResponseRow,
    diagnosticsFirstResponseDetailLines, renderDiagnosticsFirstResponse, diagnosticsInvestigationTrailLines,
    renderDiagnosticsInvestigationActions, renderDiagnosticsInvestigationTrail,
  } = diagnosticsFirstResponse;

const diagnosticsInvestigationModule = window.__diagnosticsInvestigationModule || {};
delete window.__diagnosticsInvestigationModule;
const diagnosticsInvestigation = typeof diagnosticsInvestigationModule.createDiagnosticsInvestigationModule === "function"
  ? diagnosticsInvestigationModule.createDiagnosticsInvestigationModule({
    appendCells,
    appendDiagnosticsActionGroup,
    byId,
    clearRows,
    diagnosticsActionGroups,
    diagnosticsMalformedStateLines,
    diagnosticsOrderedActions,
    diagnosticsSafeRows,
    diagnosticsSamplePolicyReconciliation,
    diagnosticsTextLines,
    makeRowSelectable,
    setText,
    updateTableStatusLegend,
  })
  : {};
const diagnosticsStateIssueRows = diagnosticsInvestigation.diagnosticsStateIssueRows || function () { return []; };
const diagnosticsPageReviewRows = diagnosticsInvestigation.diagnosticsPageReviewRows || function () { return []; };
const diagnosticsCrossPageConflictRows = diagnosticsInvestigation.diagnosticsCrossPageConflictRows || function () { return []; };
const diagnosticsConflictSignalLabel = diagnosticsInvestigation.diagnosticsConflictSignalLabel || function (item) { return String(item || "cross-page conflict"); };
const diagnosticsCommandIssueRows = diagnosticsInvestigation.diagnosticsCommandIssueRows || function () { return []; };
const diagnosticsInvestigationAddAction = diagnosticsInvestigation.diagnosticsInvestigationAddAction || function () {};
const diagnosticsInvestigationActions = diagnosticsInvestigation.diagnosticsInvestigationActions || function () { return []; };
const diagnosticsInvestigationStatus = diagnosticsInvestigation.diagnosticsInvestigationStatus || function () { return "No blockers"; };
const diagnosticsListText = diagnosticsInvestigation.diagnosticsListText || function (value) { return Array.isArray(value) && value.length ? value.join(", ") : "none"; };
const diagnosticsRowLabel = diagnosticsInvestigation.diagnosticsRowLabel || function () { return "Diagnostics row"; };
const diagnosticsOwnerDefaultAction = diagnosticsInvestigation.diagnosticsOwnerDefaultAction || function () { return "Review owning page."; };
const diagnosticsOwnerRowSeverity = diagnosticsInvestigation.diagnosticsOwnerRowSeverity || function () { return "review"; };
const diagnosticsOwnerHandoffRowKey = diagnosticsInvestigation.diagnosticsOwnerHandoffRowKey || function () { return ""; };
const diagnosticsCompletedFinalTrustStepForRow = diagnosticsInvestigation.diagnosticsCompletedFinalTrustStepForRow || function () { return {}; };
const diagnosticsCompletedFinalTrustLines = diagnosticsInvestigation.diagnosticsCompletedFinalTrustLines || function () { return []; };
const diagnosticsCompletedPolicyReconciliationLines = diagnosticsInvestigation.diagnosticsCompletedPolicyReconciliationLines || function () { return []; };
const diagnosticsOwnerHandoffRows = diagnosticsInvestigation.diagnosticsOwnerHandoffRows || function () { return []; };
const diagnosticsOwnerHandoffStatus = diagnosticsInvestigation.diagnosticsOwnerHandoffStatus || function () { return "No flagged rows"; };
const diagnosticsOwnerHandoffSummaryLines = diagnosticsInvestigation.diagnosticsOwnerHandoffSummaryLines || function () { return []; };
const diagnosticsOwnerHandoffActions = diagnosticsInvestigation.diagnosticsOwnerHandoffActions || function () { return []; };
const diagnosticsOwnerPageId = diagnosticsInvestigation.diagnosticsOwnerPageId || function () { return ""; };
const diagnosticsOwnerSelectFunction = diagnosticsInvestigation.diagnosticsOwnerSelectFunction || function () { return null; };
const diagnosticsOwnerNavigationLabel = diagnosticsInvestigation.diagnosticsOwnerNavigationLabel || function () { return "Go To Owner Row"; };
const setDiagnosticsOwnerHandoffNavStatus = diagnosticsInvestigation.setDiagnosticsOwnerHandoffNavStatus || function () {};
const navigateDiagnosticsOwnerHandoffRow = diagnosticsInvestigation.navigateDiagnosticsOwnerHandoffRow || function () { return false; };
const getSelectedDiagnosticsOwnerHandoffRow = diagnosticsInvestigation.getSelectedDiagnosticsOwnerHandoffRow || function () { return null; };
const selectDiagnosticsOwnerHandoffRow = diagnosticsInvestigation.selectDiagnosticsOwnerHandoffRow || function () {};
const renderDiagnosticsOwnerHandoffActions = diagnosticsInvestigation.renderDiagnosticsOwnerHandoffActions || function () {};
const diagnosticsSampleValidationComparisonLines = diagnosticsInvestigation.diagnosticsSampleValidationComparisonLines || function () { return []; };
const renderDiagnosticsOwnerHandoffDetail = diagnosticsInvestigation.renderDiagnosticsOwnerHandoffDetail || function () {};
const renderDiagnosticsOwnerHandoffTable = diagnosticsInvestigation.renderDiagnosticsOwnerHandoffTable || function () {};
const renderDiagnosticsOwnerHandoff = diagnosticsInvestigation.renderDiagnosticsOwnerHandoff || function () {};
const isDiagnosticsOpenCommand = diagnosticsInvestigation.isDiagnosticsOpenCommand || function () { return false; };
const diagnosticsOpenHistoryLine = diagnosticsInvestigation.diagnosticsOpenHistoryLine || function () { return ""; };
const renderDiagnosticsOpenHistory = diagnosticsInvestigation.renderDiagnosticsOpenHistory || function () {};
  function diagnosticsPayloadFirstString(payload, keys) {
    for (const key of keys || []) {
      const value = payload?.[key];
      if (value === undefined || value === null || value === false) continue;
      const text = Array.isArray(value) ? value.join("; ") : String(value);
      if (text.trim()) return text.trim();
    }
    return "";
  }

  function diagnosticsPayloadFlag(payload, keys) {
    return (keys || []).some((key) => Boolean(payload?.[key]));
  }

  function diagnosticsLogPanelStatus(value, payload, options = {}) {
    const textValue = String(value || "");
    const metadata = diagnosticsPayloadFirstString(payload, options.stateKeys || []);
    const lowerMetadata = metadata.toLowerCase();
    const errorText = diagnosticsPayloadFirstString(payload, options.errorKeys || []);
    const label = options.label || "Diagnostics log";
    if (errorText || /\b(?:error|failed|failure|exception|read[_ -]?error)\b/.test(lowerMetadata)) {
      return {
        label: "Read error",
        state: "blocked",
        fallback: `${label} read error. ${errorText || metadata || "Backend diagnostics payload reported a read error."}`,
      };
    }
    if (diagnosticsPayloadFlag(payload, options.unavailableKeys || []) || /\bunavailable\b/.test(lowerMetadata)) {
      return {
        label: "Unavailable",
        state: "warning",
        fallback: `${label} unavailable. Refresh diagnostics after confirming Local API and backend state.`,
      };
    }
    if (diagnosticsPayloadFlag(payload, options.missingKeys || []) || /\b(?:missing|not found|not_found)\b/.test(lowerMetadata)) {
      return {
        label: "Missing",
        state: "warning",
        fallback: `${label} missing. Use File Log bounded tail or State Summary before acting on this absence.`,
      };
    }
    if (diagnosticsPayloadFlag(payload, options.truncatedKeys || []) || /\b(?:truncated|partial)\b/.test(lowerMetadata)) {
      return {
        label: "Loaded truncated",
        state: "warning",
        fallback: textValue || `${label} loaded with a truncation or partial-read marker.`,
      };
    }
    if (textValue.trim()) {
      return { label: "Loaded", state: "ready", fallback: textValue };
    }
    return {
      label: "Empty",
      state: "empty",
      fallback: options.emptyText || `No ${label.toLowerCase()} loaded.`,
    };
  }

  function renderDiagnostics(diagnostics) {
    const payload = diagnostics || {};
    renderDiagnosticsTriage(payload);
    renderDiagnosticsDrilldown(payload);
    renderDiagnosticsLogRows(payload);
    setText("recent-errors", (payload.recent_errors || []).join("\n") || "No recent errors.");
    setText("recent-events", (payload.recent_events || []).join("\n") || "No recent events.");
    setText("active-jobs", (payload.active_jobs || []).join("\n") || "No ActiveJobs records.");
    renderActiveJobRows(payload.active_job_rows || []);
    const pipelineLog = String(payload.log_tail || "");
    const launchLog = String(payload.launch_logs || "");
    const pipelineStatus = diagnosticsLogPanelStatus(pipelineLog, payload, {
      label: "Pipeline log tail",
      stateKeys: ["log_tail_state", "log_tail_status", "pipeline_log_state", "pipeline_log_status"],
      errorKeys: ["log_tail_error", "pipeline_log_error", "log_tail_read_error"],
      unavailableKeys: ["log_tail_unavailable", "pipeline_log_unavailable"],
      missingKeys: ["log_tail_missing", "pipeline_log_missing"],
      truncatedKeys: ["log_tail_truncated", "pipeline_log_truncated"],
      emptyText: "No pipeline log tail loaded.",
    });
    const launchStatus = diagnosticsLogPanelStatus(launchLog, payload, {
      label: "Launch log",
      stateKeys: ["launch_logs_state", "launch_log_state", "launch_logs_status", "launch_log_status"],
      errorKeys: ["launch_logs_error", "launch_log_error", "launch_logs_read_error"],
      unavailableKeys: ["launch_logs_unavailable", "launch_log_unavailable"],
      missingKeys: ["launch_logs_missing", "launch_log_missing"],
      truncatedKeys: ["launch_logs_truncated", "launch_log_truncated"],
      emptyText: "No launch logs loaded.",
    });
    setDiagnosticsPanelStatus("diagnostics-pipeline-log-status", pipelineStatus.label, pipelineStatus.state);
    setDiagnosticsPanelStatus("diagnostics-launch-log-status", launchStatus.label, launchStatus.state);
    setTextIfChanged("log-tail", compactRepeatedProgressLines(pipelineLog) || pipelineStatus.fallback);
    setTextIfChanged("launch-logs", launchLog || launchStatus.fallback);
  }

  function diagnosticsFailureMessage(failure) {
    const message = failure?.message || failure?.reason || "Couldn't refresh diagnostics: backend request failed before error details were available (unexpected error). Try again.";
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    return `Refresh failed at ${time}; showing stale data if previously loaded. ${message}`;
  }

  function renderDiagnosticsRefreshFailures(failures = []) {
    const items = Array.isArray(failures) ? failures : [];
    const byName = (name) => items.find((item) => String(item?.name || "").toLowerCase() === name);
    const diagnosticsFailure = byName("diagnostics");
    if (diagnosticsFailure) {
      const message = diagnosticsFailureMessage(diagnosticsFailure);
      [
        "diagnostics-triage-status",
        "diagnostics-drilldown-status",
        "diagnostics-log-status",
        "diagnostics-pipeline-log-status",
        "diagnostics-launch-log-status",
        "active-job-detail-status",
      ].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
    const stateFailure = byName("diagnostics state summary");
    if (stateFailure) {
      const message = diagnosticsFailureMessage(stateFailure);
      [
        "diagnostics-state-summary-status",
        "diagnostics-state-recovery-status",
        "diagnostics-state-triage-status",
      ].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
    const commandsFailure = byName("commands");
    if (commandsFailure) {
      const message = diagnosticsFailureMessage(commandsFailure);
      [
        "diagnostics-command-status",
        "diagnostics-command-drilldown-status",
        "diagnostics-command-owner-status",
        "diagnostics-command-evidence-status",
        "diagnostics-command-resolution-status",
      ].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
    const contractFailure = byName("contract");
    if (contractFailure) {
      const message = diagnosticsFailureMessage(contractFailure);
      ["api-contract-status", "api-contract-safety-status"].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
  }

  async function requestDiagnosticsOpen(target, sourceButton = null) {
    if (rejectDiagnosticsOpenWhileBusy()) {
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, "Open already in progress.", "warning");
      }
      return;
    }
    const normalized = String(target || "").trim();
    if (!normalized) {
      const result = {
        command: "diagnostics.open",
        ok: false,
        severity: "error",
        message: "No diagnostics target was selected.",
      };
      appendCommandResult(result);
      setDiagnosticsOpenStatus(result.message, "warning");
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, result.message, "warning");
      }
      return;
    }
    setDiagnosticsOpenBusy(true, sourceButton);
    if (sourceButton && typeof setActionBusy === "function") {
      setActionBusy(sourceButton, true, `Opening ${normalized}...`);
    }
    setDiagnosticsOpenStatus(`Opening ${normalized}...`, "loading");
    try {
      const result = await apiPost("/api/diagnostics/open", { target: normalized });
      appendCommandResult(result);
      setDiagnosticsOpenStatus(result.message || "Open request sent.", result.ok === false ? "blocked" : "ready");
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, result.message || "Open request sent.", result.ok === false ? "blocked" : "ready");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "diagnostics.open",
        ok: false,
        severity: "error",
        message,
      });
      setDiagnosticsOpenStatus(`Open failed: ${message}`, "blocked");
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, `Open failed: ${message}`, "blocked");
      }
    } finally {
      if (sourceButton && typeof setActionBusy === "function") {
        setActionBusy(sourceButton, false);
      }
      setDiagnosticsOpenBusy(false, sourceButton);
    }
  }

  /**
   * Public namespace for the Diagnostics page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineDiagnosticsView = {
    renderDiagnostics,
    renderDiagnosticsRefreshFailures,
    renderDiagnosticsTriage,
    renderDiagnosticsDrilldown,
    diagnosticsTextLines,
    compactRepeatedProgressLines,
    compactedDiagnosticsTextLines,
    setTextIfChanged,
    diagnosticsSeverityForLine,
    diagnosticsMalformedStateLines,
    diagnosticsRealMediaBoundaryLines,
    diagnosticsArtifactMatches,
    diagnosticsSourceLines,
    diagnosticsArtifactTargets,
    diagnosticsActionLabel,
    diagnosticsActionGroups,
    diagnosticsActionPlanLines,
    diagnosticsFormatCounts,
    diagnosticsStateIssueRows,
    diagnosticsPageReviewRows,
    diagnosticsCrossPageConflictRows,
    diagnosticsConflictSignalLabel,
    diagnosticsCommandIssueRows,
    diagnosticsInvestigationActions,
    diagnosticsInvestigationStatus,
    diagnosticsSamplePolicyReconciliation,
    diagnosticsFirstResponseRows,
    diagnosticsFirstResponseStatus,
    diagnosticsFirstResponseSummaryLines,
    diagnosticsFirstResponsePostureStatus,
    selectedDiagnosticsFirstResponseRow,
    diagnosticsFirstResponseDetailLines,
    renderDiagnosticsFirstResponse,
    diagnosticsInvestigationTrailLines,
    renderDiagnosticsInvestigationActions,
    renderDiagnosticsInvestigationTrail,
    diagnosticsListText,
    diagnosticsRowLabel,
    diagnosticsOwnerDefaultAction,
    diagnosticsOwnerRowSeverity,
    diagnosticsOwnerHandoffRowKey,
    diagnosticsCompletedFinalTrustStepForRow,
    diagnosticsCompletedFinalTrustLines,
    diagnosticsCompletedPolicyReconciliationLines,
    diagnosticsOwnerHandoffRows,
    diagnosticsOwnerHandoffStatus,
    diagnosticsOwnerHandoffSummaryLines,
    diagnosticsOwnerHandoffActions,
    diagnosticsOwnerPageId,
    diagnosticsOwnerSelectFunction,
    diagnosticsOwnerNavigationLabel,
    setDiagnosticsOwnerHandoffNavStatus,
    navigateDiagnosticsOwnerHandoffRow,
    getSelectedDiagnosticsOwnerHandoffRow,
    selectDiagnosticsOwnerHandoffRow,
    renderDiagnosticsOwnerHandoffActions,
    diagnosticsSampleValidationComparisonLines,
    renderDiagnosticsOwnerHandoffDetail,
    renderDiagnosticsOwnerHandoffTable,
    renderDiagnosticsOwnerHandoff,
    appendDiagnosticsActionGroup,
    activeJobRowKey,
    selectActiveJobRow,
    getSelectedActiveJobRow,
    activeJobDiagnosticsActions,
    diagnosticsActiveJobRealMediaTraceLines,
    renderActiveJobDiagnosticsActions,
    renderActiveJobRows,
    renderActiveJobDetail,
    diagnosticsLineTimestamp,
    diagnosticsLogRows,
    diagnosticsLogRowKey,
    diagnosticsArtifactsForLine,
    diagnosticsLogRowActions,
    diagnosticsLogRowNextStep,
    diagnosticsLogRealMediaTraceLines,
    diagnosticsLogGuidanceLines,
    renderDiagnosticsLogActions,
    filteredDiagnosticsLogRows,
    getLastDiagnosticsLogRows,
    selectDiagnosticsLogRow,
    getSelectedDiagnosticsLogRow,
    renderDiagnosticsLogRows,
    renderDiagnosticsLogDetail,
    selectedDiagnosticsTailTarget,
    selectedDiagnosticsTailMaxBytes,
    setDiagnosticsTailTarget,
    setDiagnosticsTailStatus,
    setDiagnosticsTailBusy,
    renderDiagnosticsTail,
    requestDiagnosticsTail,
    initDiagnosticsViewEvents,
    renderDiagnosticsDrilldownActions,
    requestTdarrMatrixAudit,
    renderTdarrMatrixAuditFindings,
    renderTdarrMatrixBucketCoverage,
    renderTdarrMatrixRunComparison,
    renderTdarrMatrixConsole,
    requestTdarrMatrixConsole,
    requestTdarrMatrixEvidenceOpen,
    requestTdarrMatrixRerun,
    requestTdarrMatrixRunComparison,
    setDiagnosticsOpenStatus,
    setDiagnosticsOpenBusy,
    rejectDiagnosticsOpenWhileBusy,
    requestDiagnosticsOpen,
    isDiagnosticsOpenCommand,
    diagnosticsOpenHistoryLine,
    renderDiagnosticsOpenHistory,
  };
  window.renderDiagnostics = renderDiagnostics;
  window.renderDiagnosticsRefreshFailures = renderDiagnosticsRefreshFailures;
  window.diagnosticsTextLines = diagnosticsTextLines;
  window.diagnosticsSeverityForLine = diagnosticsSeverityForLine;
  window.diagnosticsMalformedStateLines = diagnosticsMalformedStateLines;
  window.diagnosticsSourceLines = diagnosticsSourceLines;
  window.diagnosticsActionGroups = diagnosticsActionGroups;
  window.diagnosticsActionPlanLines = diagnosticsActionPlanLines;
  window.diagnosticsStateIssueRows = diagnosticsStateIssueRows;
  window.diagnosticsPageReviewRows = diagnosticsPageReviewRows;
  window.diagnosticsCrossPageConflictRows = diagnosticsCrossPageConflictRows;
  window.diagnosticsConflictSignalLabel = diagnosticsConflictSignalLabel;
  window.diagnosticsCommandIssueRows = diagnosticsCommandIssueRows;
  window.diagnosticsInvestigationActions = diagnosticsInvestigationActions;
  window.diagnosticsInvestigationStatus = diagnosticsInvestigationStatus;
  window.diagnosticsSamplePolicyReconciliation = diagnosticsSamplePolicyReconciliation;
  window.renderDiagnosticsInvestigationTrail = renderDiagnosticsInvestigationTrail;
  window.diagnosticsListText = diagnosticsListText;
  window.diagnosticsRowLabel = diagnosticsRowLabel;
  window.diagnosticsOwnerDefaultAction = diagnosticsOwnerDefaultAction;
  window.diagnosticsOwnerRowSeverity = diagnosticsOwnerRowSeverity;
  window.diagnosticsOwnerHandoffRowKey = diagnosticsOwnerHandoffRowKey;
  window.diagnosticsCompletedFinalTrustStepForRow = diagnosticsCompletedFinalTrustStepForRow;
  window.diagnosticsCompletedFinalTrustLines = diagnosticsCompletedFinalTrustLines;
  window.diagnosticsCompletedPolicyReconciliationLines = diagnosticsCompletedPolicyReconciliationLines;
  window.diagnosticsOwnerHandoffRows = diagnosticsOwnerHandoffRows;
  window.diagnosticsOwnerHandoffStatus = diagnosticsOwnerHandoffStatus;
  window.diagnosticsOwnerHandoffSummaryLines = diagnosticsOwnerHandoffSummaryLines;
  window.diagnosticsOwnerHandoffActions = diagnosticsOwnerHandoffActions;
  window.diagnosticsOwnerPageId = diagnosticsOwnerPageId;
  window.diagnosticsOwnerSelectFunction = diagnosticsOwnerSelectFunction;
  window.diagnosticsOwnerNavigationLabel = diagnosticsOwnerNavigationLabel;
  window.setDiagnosticsOwnerHandoffNavStatus = setDiagnosticsOwnerHandoffNavStatus;
  window.getSelectedDiagnosticsOwnerHandoffRow = getSelectedDiagnosticsOwnerHandoffRow;
  window.selectDiagnosticsOwnerHandoffRow = selectDiagnosticsOwnerHandoffRow;
  window.renderDiagnosticsOwnerHandoffActions = renderDiagnosticsOwnerHandoffActions;
  window.diagnosticsSampleValidationComparisonLines = diagnosticsSampleValidationComparisonLines;
  window.renderDiagnosticsOwnerHandoffDetail = renderDiagnosticsOwnerHandoffDetail;
  window.renderDiagnosticsOwnerHandoffTable = renderDiagnosticsOwnerHandoffTable;
  window.appendDiagnosticsActionGroup = appendDiagnosticsActionGroup;
  window.activeJobRowKey = activeJobRowKey;
  window.selectActiveJobRow = selectActiveJobRow;
  window.getSelectedActiveJobRow = getSelectedActiveJobRow;
  window.activeJobDiagnosticsActions = activeJobDiagnosticsActions;
  window.diagnosticsActiveJobRealMediaTraceLines = diagnosticsActiveJobRealMediaTraceLines;
  window.renderActiveJobDiagnosticsActions = renderActiveJobDiagnosticsActions;
  window.renderActiveJobRows = renderActiveJobRows;
  window.renderActiveJobDetail = renderActiveJobDetail;
  window.diagnosticsLineTimestamp = diagnosticsLineTimestamp;
  window.diagnosticsLogRows = diagnosticsLogRows;
  window.diagnosticsArtifactsForLine = diagnosticsArtifactsForLine;
  window.renderDiagnosticsLogActions = renderDiagnosticsLogActions;
  window.filteredDiagnosticsLogRows = filteredDiagnosticsLogRows;
  window.getLastDiagnosticsLogRows = getLastDiagnosticsLogRows;
  window.selectDiagnosticsLogRow = selectDiagnosticsLogRow;
  window.getSelectedDiagnosticsLogRow = getSelectedDiagnosticsLogRow;
  window.renderDiagnosticsLogRows = renderDiagnosticsLogRows;
  window.renderDiagnosticsLogDetail = renderDiagnosticsLogDetail;
  window.requestDiagnosticsTail = requestDiagnosticsTail;
  window.requestDiagnosticsOpen = requestDiagnosticsOpen;
})();
