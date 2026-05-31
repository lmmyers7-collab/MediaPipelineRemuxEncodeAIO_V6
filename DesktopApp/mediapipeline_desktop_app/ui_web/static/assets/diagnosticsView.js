(function () {
  let diagnosticsOpenInFlight = false;
  const diagnosticsTailView = window.mediaPipelineDiagnosticsTailView || {};
  const selectedDiagnosticsTailTarget = window.selectedDiagnosticsTailTarget || diagnosticsTailView.selectedDiagnosticsTailTarget || function () { return ""; };
  const selectedDiagnosticsTailMaxBytes = window.selectedDiagnosticsTailMaxBytes || diagnosticsTailView.selectedDiagnosticsTailMaxBytes || function () { return "65536"; };
  const setDiagnosticsTailTarget = window.setDiagnosticsTailTarget || diagnosticsTailView.setDiagnosticsTailTarget || function () {};
  const setDiagnosticsTailStatus = window.setDiagnosticsTailStatus || diagnosticsTailView.setDiagnosticsTailStatus || function () {};
  const setDiagnosticsTailBusy = window.setDiagnosticsTailBusy || diagnosticsTailView.setDiagnosticsTailBusy || function () {};
  const renderDiagnosticsTail = window.renderDiagnosticsTail || diagnosticsTailView.renderDiagnosticsTail || function () {};
  const requestDiagnosticsTail = window.requestDiagnosticsTail || diagnosticsTailView.requestDiagnosticsTail || async function () {};
  let lastDiagnosticsLogRows = [];
  let selectedDiagnosticsFirstResponseKey = "";

  function setDiagnosticsOpenStatus(message) {
    setText("diagnostics-open-status", message);
    setText("home-runtime-open-status", message);
  }

  function setDiagnosticsOpenBusy(isBusy) {
    diagnosticsOpenInFlight = Boolean(isBusy);
    document.querySelectorAll("[data-open-diagnostics]").forEach((button) => {
      button.disabled = diagnosticsOpenInFlight;
    });
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
    setDiagnosticsOpenStatus(result.message);
    return true;
  }

  function diagnosticsTextLines(value) {
    if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
    const text = String(value || "").trim();
    return text ? text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean) : [];
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
    if (typeof window.diagnosticsBridgeActionLabel === "function") {
      return window.diagnosticsBridgeActionLabel(action);
    }
    const verb = action.kind === "tail" ? "Read" : "Open";
    return action.label || `${verb} ${String(action.target || "").replaceAll("_", " ")}`;
  }

  function diagnosticsOrderedActions(actions) {
    const candidates = Array.isArray(actions) ? actions.filter((action) => action && action.target) : [];
    if (typeof window.diagnosticsBridgeOrderedActions === "function") {
      return window.diagnosticsBridgeOrderedActions(candidates);
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
      onTail: (target) => requestDiagnosticsTail(target),
      onOpen: (target) => requestDiagnosticsOpen(target),
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
    const forceResetButton = byId("diagnostics-force-reset-button");
    if (forceResetButton) forceResetButton.addEventListener("click", async () => {
      const confirmed = window.confirm(
        "Reset stuck progress to idle?\n\nThis sends the Force Stop command, which terminates any remaining pipeline processes and resets the progress state to idle.\n\nUse only when the pipeline shows an active stage but no process is actually running."
      );
      if (!confirmed) return;
      const statusEl = byId("diagnostics-force-reset-status");
      if (statusEl) statusEl.textContent = "Sending force reset...";
      forceResetButton.disabled = true;
      try {
        const post = typeof apiPost === "function" ? apiPost : (typeof window.apiPost === "function" ? window.apiPost : null);
        if (!post) throw new Error("apiPost not available.");
        const result = await post("/api/pipeline/control", { action: "kill" });
        const msg = String(result?.message || "Reset sent.");
        if (statusEl) statusEl.textContent = msg;
        if (typeof appendCommandResult === "function") appendCommandResult(result);
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        if (statusEl) statusEl.textContent = `Reset failed: ${msg}`;
      } finally {
        forceResetButton.disabled = false;
      }
    });
  }

  const diagnosticsArtifactTargets = [
    {
      name: "BDPGS OCR settings evidence",
      target: "",
      patterns: [/\bbdpgs\b/i, /\bpgs(?:tosrt|[-_\s]to[-_\s]srt)?\b/i, /\bpgstosrt\b/i, /\btessdata\b/i, /\btesseract\b/i, /\bocr\b/i, /\bsubtitle(?:s)?\b.*\bsrt\b/i],
      hint: "Select the Diagnostics State Artifact Summary row 'settings_bdpgs_ocr_paths' and then review Settings > Subtitles if saved OCR tool or tessdata path evidence is blocked. Diagnostics does not edit settings or run OCR.",
    },
    {
      name: "VobSub OCR settings evidence",
      target: "",
      patterns: [/\bvobsub\b/i, /\bdvd[_\s-]?subtitle\b/i, /\bs[_-]?vobsub\b/i, /\bseconv\b/i, /\btesseract\b/i, /\bidx\b/i, /\bsub\b/i, /\bocr\b/i, /\bsubtitle(?:s)?\b.*\bsrt\b/i],
      hint: "Select the Diagnostics State Artifact Summary row 'settings_vobsub_ocr_paths' and then review Settings > Subtitles if saved Subtitle Edit or Tesseract evidence is blocked. Diagnostics does not edit settings or run OCR.",
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
      hint: "Open Pending Publish and read Last Stderr before rerunning work that may already be parked, orphaned, or blocked by malformed manifests.",
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
  function diagnosticsSourceLines(diagnostics) {
    const groups = [
      ["Recent errors", diagnostics?.recent_errors],
      ["Recent events", diagnostics?.recent_events],
      ["ActiveJobs", diagnostics?.active_jobs],
      ["Warnings", diagnostics?.warnings],
      ["Pipeline log tail", diagnostics?.log_tail],
      ["Launch logs", diagnostics?.launch_logs],
    ];
    const entries = [];
    groups.forEach(([source, value]) => {
      diagnosticsTextLines(value).slice(-50).forEach((line) => {
        entries.push({ source, line });
      });
    });
    return entries;
  }

  function diagnosticsArtifactMatches(diagnostics) {
    const entries = diagnosticsSourceLines(diagnostics || {});
    return diagnosticsArtifactTargets
      .map((artifact) => {
        const samples = [];
        let count = 0;
        entries.forEach((entry) => {
          if (!artifact.patterns.some((pattern) => pattern.test(entry.line))) return;
          count += 1;
          if (samples.length < 3) {
            samples.push(`${entry.source}: ${entry.line}`);
          }
        });
        return {
          ...artifact,
          count,
          samples,
        };
      })
      .filter((artifact) => artifact.count > 0)
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
  }

  function renderDiagnosticsDrilldownActions(matches) {
    const actions = byId("diagnostics-drilldown-actions");
    if (!actions) return;
    actions.replaceChildren();
    matches.slice(0, 6).forEach((artifact) => {
      const button = document.createElement("button");
      button.className = "secondary-button";
      button.type = "button";
      button.dataset.openDiagnostics = artifact.target;
      button.textContent = `Open ${artifact.name}`;
      button.addEventListener("click", () => requestDiagnosticsOpen(artifact.target));
      actions.appendChild(button);
      if (artifact.tailTarget) {
        const tailButton = document.createElement("button");
        tailButton.className = "secondary-button";
        tailButton.type = "button";
        tailButton.dataset.readDiagnosticsTail = artifact.tailTarget;
        tailButton.textContent = `Read ${artifact.tailName || artifact.name}`;
        tailButton.addEventListener("click", () => requestDiagnosticsTail(artifact.tailTarget));
        actions.appendChild(tailButton);
      }
    });
  }

  function renderDiagnosticsDrilldown(diagnostics) {
    const matches = diagnosticsArtifactMatches(diagnostics || {});
    renderDiagnosticsDrilldownActions(matches);
    const status = matches.length ? `${matches.length} artifact hint(s)` : "No artifacts";
    setText("diagnostics-drilldown-status", status);
    const lines = [
      "Artifact drilldown is read-only. Open and Read buttons below use backend allowlists; the frontend never sends arbitrary paths.",
    ];
    if (!matches.length) {
      lines.push("No artifact-specific clues were found in the current diagnostics payload.");
      lines.push("Close Readiness remains the first stop before clearing state, closing the app, or deleting runtime files.");
      setText("diagnostics-drilldown-summary", lines.join("\n"));
      return;
    }
    matches.forEach((artifact) => {
      lines.push("", `${artifact.name} (${artifact.count} clue${artifact.count === 1 ? "" : "s"}; open target: ${artifact.target})`);
      lines.push(`Next step: ${artifact.hint}`);
      artifact.samples.forEach((sample) => lines.push(`- ${sample}`));
    });
    lines.push("", "Close Readiness remains the first stop before clearing state, closing the app, or deleting runtime files.");
    setText("diagnostics-drilldown-summary", lines.join("\n"));
  }

  function renderDiagnosticsTriage(diagnostics) {
    const recentErrors = diagnosticsTextLines(diagnostics?.recent_errors);
    const recentEvents = diagnosticsTextLines(diagnostics?.recent_events);
    const activeJobs = diagnosticsTextLines(diagnostics?.active_jobs);
    const warnings = diagnosticsTextLines(diagnostics?.warnings);
    const logLines = diagnosticsTextLines(diagnostics?.log_tail).slice(-20);
    const launchLines = diagnosticsTextLines(diagnostics?.launch_logs).slice(-20);
    const allLines = [
      ...recentErrors,
      ...recentEvents,
      ...activeJobs,
      ...warnings,
      ...logLines,
      ...launchLines,
    ];
    const counts = allLines.reduce((acc, line) => {
      const severity = diagnosticsSeverityForLine(line);
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});
    const malformedLines = diagnosticsMalformedStateLines(allLines).slice(0, 8);
    const status = counts.error
      ? "Errors"
      : counts.warning
        ? "Warnings"
        : counts.active
          ? "Active"
          : allLines.length
            ? "Informational"
            : "No issues";
    setText("diagnostics-triage-status", status);
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload: diagnostics,
        label: "Diagnostics",
        rowCount: allLines.length,
        artifactLine: `Readable lines: errors ${recentErrors.length}; events ${recentEvents.length}; ActiveJobs ${activeJobs.length}; warnings ${warnings.length}.`,
        refreshAction: "Use Refresh Diagnostics or topbar Refresh. This re-reads logs/state only and does not repair, clear, delete, rerun, publish, or move files.",
      })
      : [];
    const lines = [
      ...freshnessLines,
      `Recent errors: ${recentErrors.length}`,
      `Recent events: ${recentEvents.length}`,
      `ActiveJobs lines: ${activeJobs.length}`,
      `Warnings: ${warnings.length}`,
      `Severity groups: error ${counts.error || 0}; warning ${counts.warning || 0}; active ${counts.active || 0}; info ${counts.info || 0}`,
    ];
    if (malformedLines.length) {
      lines.push("", "Malformed/stale runtime-state hint(s):");
      malformedLines.forEach((line) => lines.push(`- ${line}`));
      lines.push("Next step: Check Close Readiness first. If it is blocked, inspect ActiveJobs, progress files, Run Logs, and State Folder before closing or clearing runtime files.");
    } else if (counts.error) {
      lines.push("", "Next step: Open Run Logs and Last Stderr, then review the newest failure/audit report if one exists.");
    } else if (counts.warning) {
      lines.push("", "Next step: Review warnings and refresh once; if the same warning persists, open the relevant state/log location below.");
    } else if (counts.active) {
      lines.push("", "Next step: Active work appears to be present. Use Close Readiness and ActiveJobs before exiting.");
    } else {
      lines.push("", "Next step: No diagnostics issues are currently visible from the backend snapshot.");
    }
    setText("diagnostics-triage-summary", lines.join("\n"));
  }

  function diagnosticsFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries
      .sort(([left], [right]) => String(left).localeCompare(String(right)))
      .map(([key, count]) => `${key || "unknown"}=${count}`)
      .join(", ");
  }

  function diagnosticsSafeRows(payload) {
    return Array.isArray(payload?.rows) ? payload.rows : [];
  }

  function diagnosticsFirstResponseAdd(rows, key, step, posture, evidence, action) {
    rows.push({ key, step, posture, evidence, action });
  }

  function diagnosticsFirstResponsePostureStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized.includes("blocked") || normalized.includes("do not")) return "blocked";
    if (normalized.includes("review") || normalized.includes("warning")) return "warning";
    if (normalized.includes("read") || normalized.includes("stale") || normalized.includes("unknown")) return "changed";
    if (normalized.includes("ready")) return "match";
    return "unknown";
  }

  function diagnosticsSamplePolicyReconciliation(context = {}) {
    const log = context.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
    const policy = log.policy_alignment && typeof log.policy_alignment === "object" ? log.policy_alignment : {};
    const policyRows = Array.isArray(policy.rows) ? policy.rows : [];
    const completedPolicyRow = typeof window.sampleValidationCompletedPolicyReconciliationRow === "function"
      ? window.sampleValidationCompletedPolicyReconciliationRow(context || {})
      : null;
    const completedPolicyStatus = typeof window.sampleValidationCompletedPolicyReconciliationStatus === "function"
      ? window.sampleValidationCompletedPolicyReconciliationStatus(context || {})
      : (completedPolicyRow ? "Review" : "No saved-policy row");
    const completedPosture = typeof window.sampleValidationCompletedPacketPostureStatus === "function"
      ? window.sampleValidationCompletedPacketPostureStatus(completedPolicyRow)
      : String(completedPolicyRow?.posture || "").toLowerCase();
    const normalizedPolicyStatus = String(policy.operator_status || "").toLowerCase();
    const blockedPolicy = Number(policy.blocked_count || 0) > 0
      || ["blocked", "missing", "not-ready"].includes(normalizedPolicyStatus)
      || completedPosture === "blocked";
    const reviewPolicy = Number(policy.review_count || 0) > 0
      || Number(policy.missing_count || 0) > 0
      || !policyRows.length
      || !completedPolicyRow
      || ["warning", "changed", "unknown"].includes(completedPosture)
      || String(completedPolicyStatus || "").toLowerCase().includes("review")
      || String(completedPolicyStatus || "").toLowerCase().includes("no saved-policy");
    const posture = blockedPolicy ? "Blocked review" : reviewPolicy ? "Review" : "Ready";
    const evidence = [
      `saved policy=${policy.operator_status || "not loaded"}`,
      `required=${policy.required_ready_count || 0}/${policy.required_count || policyRows.filter((row) => row.required !== false).length}`,
      `policy rows=${policyRows.length}`,
      `completed reconciliation=${completedPolicyStatus}`,
      `completed evidence=${completedPolicyRow?.evidence || "not loaded"}`,
    ].join("; ");
    const action = blockedPolicy
      ? "Open Settings policy evidence, then Completed > Selected Pilot Evidence Packet > Saved policy reconciliation before accepting or rerunning."
      : reviewPolicy
        ? "Use Home > Sample Validation and Completed > Saved policy reconciliation to decide whether missing category proof is acceptable review evidence."
        : "Use policy reconciliation as supporting evidence only; playback, subtitle, audio, size, and final-placement proof still decide acceptance.";
    return {
      posture,
      evidence,
      action,
      policy,
      policyRows,
      completedPolicyRow,
      completedPolicyStatus,
      completedPosture,
    };
  }

  function diagnosticsFirstResponseRows(context = {}) {
    const payload = context || {};
    const diagnostics = payload.diagnostics || {};
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const failures = Array.isArray(payload.failures) ? payload.failures : [];
    const requiredFailures = failures.filter((failure) => failure.required);
    const activeRows = Array.isArray(diagnostics.active_job_rows) ? diagnostics.active_job_rows : [];
    const activeJobBlocked = activeRows.filter((row) => activeJobRowPosture(row) === "blocked").length;
    const activeJobReview = activeRows.filter((row) => activeJobRowPosture(row) === "warning").length;
    const allLines = [
      ...diagnosticsTextLines(diagnostics.recent_errors),
      ...diagnosticsTextLines(diagnostics.warnings),
      ...diagnosticsTextLines(diagnostics.active_jobs),
      ...diagnosticsTextLines(diagnostics.log_tail).slice(-20),
      ...diagnosticsTextLines(diagnostics.launch_logs).slice(-20),
    ];
    const malformedLines = diagnosticsMalformedStateLines(allLines);
    const severityCounts = diagnosticsLogRows(diagnostics).reduce((acc, row) => {
      const key = row.severity || "info";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const closeState = String(payload.closeReadiness?.state || payload.closeReadiness?.status || "").trim().toLowerCase();
    const closeSafe = payload.closeReadiness && payload.closeReadiness.safe_to_close === true;
    const closeBlocked = payload.closeReadiness && payload.closeReadiness.safe_to_close === false;
    const snapshotState = String(payload.snapshot?.pipeline_state || payload.closeReadiness?.state || "unknown").trim();
    const reviewRows = queueReviews.length + completedReviews.length + pendingReviews.length;
    const rows = [];

    diagnosticsFirstResponseAdd(
      rows,
      "refresh-health",
      "Refresh payload health",
      requiredFailures.length ? "Blocked" : failures.length ? "Review" : "Ready",
      `required failures=${requiredFailures.length}; supporting failures=${Math.max(0, failures.length - requiredFailures.length)}`,
      requiredFailures.length
        ? "Refresh again, then inspect failed backend read(s) before trusting any WebView panel."
        : failures.length
          ? "Use the failed panel names as read-first context before unattended work."
          : "All loaded refresh payloads needed by Diagnostics are available.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "close-active-work",
      "Close readiness / active work",
      closeBlocked ? "Review" : closeSafe ? "Ready" : "Read evidence",
      `close=${payload.closeReadiness ? (closeSafe ? "safe" : "not safe") : "unknown"}; state=${snapshotState}; reason=${payload.closeReadiness?.reason || "none"}`,
      closeBlocked
        ? "Do not close or start competing work until ActiveJobs, Progress, Last Stderr, and Run Logs agree."
        : closeSafe
          ? "Close-readiness is not blocking; continue with state/log checks if another page looks wrong."
          : "Wait for close-readiness or inspect ActiveJobs before treating the session as idle.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "activejobs-progress",
      "ActiveJobs / progress",
      activeJobBlocked ? "Blocked review" : activeJobReview ? "Review" : activeRows.length ? "Read evidence" : "Ready",
      `active-job rows=${activeRows.length}; blocked=${activeJobBlocked}; review=${activeJobReview}; pipeline state=${snapshotState}`,
      activeJobBlocked
        ? "Select the malformed/orphaned ActiveJobs row, read Last Stderr, then compare Close Readiness before clearing or rerunning."
        : activeJobReview
          ? "Inspect ActiveJobs detail and progress freshness before closing or starting more work."
          : activeRows.length
            ? "Use ActiveJobs as process-lifecycle evidence only; Completed/Pending still prove output state."
            : "No structured ActiveJobs rows are loaded.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "state-artifacts",
      "State artifacts / read order",
      stateIssues.some((item) => String(typeof window.diagnosticsStateOperatorStatus === "function" ? window.diagnosticsStateOperatorStatus(item) : item.operator_status || item.status || "").toLowerCase() === "blocked") ? "Blocked review" : stateIssues.length ? "Review" : "Ready",
      `state artifact issues=${stateIssues.length}; read-order rows=${Array.isArray(payload.stateSummary?.triage) ? payload.stateSummary.triage.length : 0}`,
      stateIssues.length
        ? "Use State Artifact Summary and Backend Read Order before rerun, drain, cleanup, or shutdown decisions."
        : "No state artifact blocker is visible; keep using page-specific evidence for workflow decisions.",
    );

    const dependencyContext = {
      settings: payload.settings || {},
      stateSummary: payload.stateSummary || {},
      maintenance: payload.maintenance || (typeof window.getLastMaintenance === "function" ? window.getLastMaintenance() : {}),
    };
    const dependencyStatus = typeof window.externalDependencyOverallStatus === "function"
      ? window.externalDependencyOverallStatus(dependencyContext)
      : (stateIssues.length ? "review" : "unknown");
    const dependencyEvidence = typeof window.externalDependencyEvidenceText === "function"
      ? window.externalDependencyEvidenceText(dependencyContext)
      : `settings dependency issue rows=${stateIssues.length}; maintenance evidence=not loaded`;
    diagnosticsFirstResponseAdd(
      rows,
      "external-dependencies",
      "External dependency readiness",
      dependencyStatus === "blocked" ? "Blocked review" : dependencyStatus === "ready" ? "Ready" : "Review",
      dependencyEvidence,
      dependencyStatus === "blocked"
        ? "Resolve blocked Settings OCR or Maintenance toolchain evidence before rerun, launch, package, or manual-review decisions."
        : dependencyStatus === "ready"
          ? "Loaded Settings OCR and Maintenance toolchain evidence has no visible blocker; still validate real media output separately."
          : "Open Settings > Subtitles for OCR evidence or Maintenance > Environment Health for toolchain evidence before long unattended processing.",
    );

    const policyHandoff = diagnosticsSamplePolicyReconciliation(payload);
    diagnosticsFirstResponseAdd(
      rows,
      "sample-policy-reconciliation",
      "Sample Validation policy reconciliation",
      policyHandoff.posture,
      policyHandoff.evidence,
      policyHandoff.action,
    );

    diagnosticsFirstResponseAdd(
      rows,
      "command-issues",
      "Recent command issues",
      commandIssues.length ? "Review" : "Ready",
      `warning/error command rows=${commandIssues.length}`,
      commandIssues.length
        ? "Open Command Result Drilldown and Command Failure Resolution before repeating the owning command."
        : "No warning/error command result is visible in the loaded command history.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "owning-pages",
      "Owning page handoff",
      crossPageConflicts.some((row) => row.severity === "blocked") ? "Blocked review" : crossPageConflicts.length || reviewRows ? "Review" : "Ready",
      `Queue=${queueReviews.length}; Completed=${completedReviews.length}; Pending=${pendingReviews.length}; cross-page conflicts=${crossPageConflicts.length}`,
      crossPageConflicts.length || reviewRows
        ? "Use Owning Page Evidence Handoff, then return to Queue/Completed/Pending before launch, rerun, drain, cleanup, or acceptance."
        : "No owning-page review rows are visible in the loaded Queue/Completed/Pending payloads.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "logs-malformed",
      "Logs and malformed-state clues",
      severityCounts.error || malformedLines.length ? "Review" : severityCounts.warning ? "Read evidence" : "Ready",
      `log severity=${diagnosticsFormatCounts(severityCounts)}; malformed/stale clues=${malformedLines.length}`,
      severityCounts.error || malformedLines.length
        ? "Read bounded Last Stderr or the matching artifact before trusting idle/ready-looking UI state."
        : severityCounts.warning
          ? "Read the warning log row if it relates to the workflow you are about to repeat."
          : "No warning/error log clue is visible in the loaded diagnostics text.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "decision-boundary",
      "Decision boundary",
      "Ready - read-only",
      "Diagnostics first response is evidence only.",
      "Return to the owning page for backend-owned launch, drain, rename, save, rerun, cleanup, or publish actions.",
    );

    return rows;
  }

  function diagnosticsFirstResponseStatus(context = {}) {
    const rows = diagnosticsFirstResponseRows(context);
    if (rows.some((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "blocked")) return "Do not proceed";
    if (rows.some((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "warning")) return "Review first";
    if (rows.some((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "changed")) return "Read evidence";
    return rows.length ? "Ready-looking" : "Not loaded";
  }

  function diagnosticsFirstResponseSummaryLines(context = {}) {
    const rows = diagnosticsFirstResponseRows(context);
    const counts = rows.reduce((acc, row) => {
      const status = diagnosticsFirstResponsePostureStatus(row.posture);
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});
    const first = rows.find((row) => ["blocked", "warning"].includes(diagnosticsFirstResponsePostureStatus(row.posture)))
      || rows.find((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "changed")
      || rows[0];
    const lines = [
      "Diagnostics first-response checklist:",
      `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.warning || 0}; read-first=${counts.changed || 0}; ready=${counts.match || 0}.`,
      "Purpose: pick the first evidence surface to inspect before launch, drain, rerun, cleanup, shutdown, rename, settings save, or publish decisions.",
    ];
    if (first) {
      lines.push(`First action: ${first.step} - ${first.action}`);
    } else {
      lines.push("First action: refresh Diagnostics; no first-response evidence is loaded.");
    }
    lines.push("Read order: bounded text first, backend-selected artifact opens next, owning page before any mutation command.");
    lines.push("Mutation guardrail: this checklist cannot launch, drain, save, rename, repair, delete, publish, clear state, or touch files.");
    return lines;
  }

  function selectedDiagnosticsFirstResponseRow(rows = []) {
    if (!selectedDiagnosticsFirstResponseKey) return null;
    return (Array.isArray(rows) ? rows : []).find((row) => row.key === selectedDiagnosticsFirstResponseKey) || null;
  }

  function diagnosticsFirstResponseDetailLines(row, context = {}) {
    if (!row) {
      return [
        "No diagnostics first-response row selected.",
        "Select a row to inspect the evidence, the owning surface, and the safe next step before repeating any command.",
        "Mutation guardrail: first-response detail is read-only and cannot launch, drain, save, rename, repair, publish, clear state, or touch media.",
      ];
    }
    const payload = context || {};
    const diagnostics = payload.diagnostics || {};
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const failures = Array.isArray(payload.failures) ? payload.failures : [];
    const activeRows = Array.isArray(diagnostics.active_job_rows) ? diagnostics.active_job_rows : [];
    const malformedLines = diagnosticsMalformedStateLines([
      ...diagnosticsTextLines(diagnostics.recent_errors),
      ...diagnosticsTextLines(diagnostics.warnings),
      ...diagnosticsTextLines(diagnostics.active_jobs),
      ...diagnosticsTextLines(diagnostics.log_tail).slice(-20),
      ...diagnosticsTextLines(diagnostics.launch_logs).slice(-20),
    ]);
    const severityCounts = diagnosticsLogRows(diagnostics).reduce((acc, item) => {
      const key = item.severity || "info";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const lines = [
      `First-response step: ${row.step}`,
      `Posture: ${row.posture}`,
      `Evidence: ${row.evidence}`,
      `Safe next step: ${row.action}`,
      "",
    ];

    if (row.key === "refresh-health") {
      const requiredFailures = failures.filter((failure) => failure.required);
      lines.push(
        "Why this gate matters: every downstream Diagnostics row depends on the refresh payload being coherent.",
        `Required refresh failures: ${requiredFailures.length}`,
        `Supporting refresh failures: ${Math.max(0, failures.length - requiredFailures.length)}`,
      );
      if (failures.length) {
        lines.push("Refresh failure sample:");
        failures.slice(0, 6).forEach((failure) => lines.push(`- ${failure.name || "refresh"}: ${failure.message || "failed"}${failure.required ? " (required)" : ""}`));
      }
    } else if (row.key === "close-active-work") {
      lines.push(
        "Why this gate matters: close-readiness owns process lifecycle safety before shutdown, relaunch, role changes, or competing work.",
        `Close readiness safe: ${payload.closeReadiness?.safe_to_close === true ? "yes" : payload.closeReadiness?.safe_to_close === false ? "no" : "unknown"}`,
        `Close reason: ${payload.closeReadiness?.reason || payload.closeReadiness?.state || "not loaded"}`,
        `Snapshot state: ${payload.snapshot?.pipeline_state || payload.snapshot?.state || "not loaded"}`,
      );
    } else if (row.key === "activejobs-progress") {
      const blocked = activeRows.filter((item) => activeJobRowPosture(item) === "blocked").length;
      const review = activeRows.filter((item) => activeJobRowPosture(item) === "warning").length;
      lines.push(
        "Why this gate matters: ActiveJobs and progress prove process lifecycle only; they do not prove output correctness.",
        `ActiveJob rows: ${activeRows.length}`,
        `Blocked rows: ${blocked}`,
        `Active/review rows: ${review}`,
      );
      activeRows.slice(0, 5).forEach((item) => lines.push(`- ${item.record_file || item.launch_id || "active job"}: ${item.status || "unknown"}; ${item.issue || item.current_stage || item.job_kind || "no issue text"}`));
    } else if (row.key === "state-artifacts") {
      lines.push(
        "Why this gate matters: malformed, stale, or missing state can make ready-looking tables lie.",
        `State artifact issue rows: ${stateIssues.length}`,
        `Backend read-order rows: ${Array.isArray(payload.stateSummary?.triage) ? payload.stateSummary.triage.length : 0}`,
      );
      stateIssues.slice(0, 6).forEach((item) => {
        const status = typeof window.diagnosticsStateOperatorStatus === "function" ? window.diagnosticsStateOperatorStatus(item) : item.operator_status || item.status || "review";
        lines.push(`- ${item.label || item.target || "artifact"}: ${status}; ${item.operator_guidance || item.error || item.warning || "review required"}`);
      });
    } else if (row.key === "external-dependencies") {
      lines.push(
        "Why this gate matters: OCR/toolchain/raw-key blockers can make reruns fail even when queue and output state look coherent.",
        "Primary owner: Settings for saved OCR/raw-key evidence; Maintenance for runtime toolchain evidence.",
      );
      if (typeof window.externalDependencySummaryLines === "function") {
        lines.push(...window.externalDependencySummaryLines({
          settings: payload.settings || {},
          stateSummary: payload.stateSummary || {},
          maintenance: payload.maintenance || (typeof window.getLastMaintenance === "function" ? window.getLastMaintenance() : {}),
        }).slice(0, 10));
      } else {
        lines.push("External dependency digest helper is not loaded; open Settings and Maintenance for current evidence.");
      }
    } else if (row.key === "sample-policy-reconciliation") {
      const handoff = diagnosticsSamplePolicyReconciliation(payload);
      lines.push(
        "Why this gate matters: accepted Sample Validation evidence should not look current when saved route/size/subtitle/audio/publish policy is missing, blocked, or not visibly reconciled with the selected Completed output.",
        `Saved policy alignment: ${handoff.policy.operator_status || "not loaded"}`,
        `Policy rows loaded: ${handoff.policyRows.length}`,
        `Completed saved-policy reconciliation: ${handoff.completedPolicyStatus}`,
        `Completed reconciliation posture: ${handoff.completedPolicyRow?.posture || "not loaded"}`,
        `Completed reconciliation evidence: ${handoff.completedPolicyRow?.evidence || "not loaded"}`,
        "Read order: Home > Sample Validation Completed Evidence Handoff -> Completed > Selected Pilot Evidence Packet > Saved policy reconciliation -> Settings media policy -> manual playback/subtitle/audio/size checks.",
        "Owner pages: Home owns Preview/Append evidence; Completed owns post-run output proof; Settings owns saved policy."
      );
      if (Array.isArray(handoff.completedPolicyRow?.detail) && handoff.completedPolicyRow.detail.length) {
        lines.push("Saved-policy reconciliation detail sample:");
        handoff.completedPolicyRow.detail.slice(0, 8).forEach((line) => lines.push(`- ${line}`));
      }
    } else if (row.key === "command-issues") {
      lines.push(
        "Why this gate matters: repeating a failed command without owner-page context can duplicate work or hide the real blocker.",
        `Warning/error command rows: ${commandIssues.length}`,
      );
      commandIssues.slice(0, 6).forEach((entry) => {
        const owner = typeof window.commandHistoryOwnerPage === "function" ? window.commandHistoryOwnerPage(entry) : "Diagnostics";
        const issue = typeof window.commandHistoryIssueLevel === "function" ? window.commandHistoryIssueLevel(entry) : entry.severity || "review";
        lines.push(`- ${owner}: ${entry.command || "command"}; issue=${issue}; ${entry.message || ""}`);
      });
    } else if (row.key === "owning-pages") {
      lines.push(
        "Why this gate matters: Diagnostics should route decisions back to the owning page instead of becoming a repair surface.",
        `Queue review rows: ${queueReviews.length}`,
        `Completed review rows: ${completedReviews.length}`,
        `Pending Publish review rows: ${pendingReviews.length}`,
        `Cross-page conflicts: ${crossPageConflicts.length}`,
      );
      crossPageConflicts.slice(0, 5).forEach((item) => lines.push(`- ${item.owner || item.page || "owner"}: ${item.reason || item.signal || item.severity || "review"}`));
    } else if (row.key === "logs-malformed") {
      lines.push(
        "Why this gate matters: stderr/log/state text often contains the fastest explanation for subprocess, ffprobe, publish, lock, and malformed-state failures.",
        `Log severity counts: ${diagnosticsFormatCounts(severityCounts)}`,
        `Malformed/stale clue count: ${malformedLines.length}`,
      );
      malformedLines.slice(0, 8).forEach((line) => lines.push(`- ${line}`));
    } else if (row.key === "decision-boundary") {
      lines.push(
        "Why this gate matters: Diagnostics is evidence and navigation, not workflow ownership.",
        "Return to Queue for launch scope, Completed for output trust/rerun decisions, Pending Publish for drain posture, Settings for config persistence, Rename for file rename transactions, and Maintenance for dry-run package/backfill checks.",
      );
    }

    lines.push(
      "",
      "Read order: bounded text first, backend-selected artifact opens next, owning page before any mutation command.",
      "Mutation guardrail: this detail cannot launch, drain, save, rename, repair, delete, publish, clear state, open arbitrary paths, rewrite manifests, or touch source/output/scratch media.",
    );
    return lines;
  }

  function renderDiagnosticsFirstResponse(context = {}) {
    const payload = context || {};
    const rows = diagnosticsFirstResponseRows(payload);
    const status = diagnosticsFirstResponseStatus(payload);
    setText("diagnostics-first-response-status", status);
    const statusNode = byId("diagnostics-first-response-status");
    if (statusNode) {
      const state = status === "Do not proceed"
        ? "blocked"
        : status === "Review first"
          ? "warning"
          : status === "Read evidence"
            ? "changed"
            : status === "Ready-looking"
              ? "ready"
              : "unknown";
      statusNode.dataset.state = state;
    }
    setText("diagnostics-first-response-summary", diagnosticsFirstResponseSummaryLines(payload).join("\n"));
    const tbody = byId("diagnostics-first-response-rows");
    if (!tbody) return;
    if (!rows.length) {
      selectedDiagnosticsFirstResponseKey = "";
      clearRows(tbody, 4, "No diagnostics first-response rows loaded.");
      updateTableStatusLegend("diagnostics-first-response-legend", tbody, "Diagnostics first-response rows");
      setText("diagnostics-first-response-detail", diagnosticsFirstResponseDetailLines(null, payload).join("\n"));
      return;
    }
    if (!rows.some((row) => row.key === selectedDiagnosticsFirstResponseKey)) {
      selectedDiagnosticsFirstResponseKey = rows[0].key;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.rowKey = item.key;
      row.dataset.status = diagnosticsFirstResponsePostureStatus(item.posture);
      appendCells(row, [item.step || "", item.posture || "", item.evidence || "", item.action || ""]);
      makeRowSelectable(row, () => {
        selectedDiagnosticsFirstResponseKey = item.key;
        renderDiagnosticsFirstResponse(payload);
      }, {
        selected: item.key === selectedDiagnosticsFirstResponseKey,
        label: `Diagnostics first-response ${item.step || item.key}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-first-response-legend", tbody, "Diagnostics first-response rows");
    setText("diagnostics-first-response-detail", diagnosticsFirstResponseDetailLines(selectedDiagnosticsFirstResponseRow(rows), payload).join("\n"));
  }

  function diagnosticsInvestigationTrailLines(context) {
    const payload = context || {};
    const diagnostics = payload.diagnostics || {};
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const failures = Array.isArray(payload.failures) ? payload.failures : [];
    const allLines = [
      ...diagnosticsTextLines(diagnostics.recent_errors),
      ...diagnosticsTextLines(diagnostics.warnings),
      ...diagnosticsTextLines(diagnostics.active_jobs),
      ...diagnosticsTextLines(diagnostics.log_tail).slice(-20),
      ...diagnosticsTextLines(diagnostics.launch_logs).slice(-20),
    ];
    const malformedLines = diagnosticsMalformedStateLines(allLines).slice(0, 5);
    const closeState = String(payload.closeReadiness?.state || "").trim() || "unknown";
    const lines = [
      "Diagnostics investigation trail:",
      `Overall status: ${diagnosticsInvestigationStatus(payload)}`,
      `Close readiness: ${closeState}${payload.closeReadiness?.reason ? ` - ${payload.closeReadiness.reason}` : ""}`,
      `Refresh failures: ${failures.length}${failures.some((failure) => failure.required) ? " (required failure present)" : ""}`,
      `State artifact issues: ${stateIssues.length}`,
      `Recent command issues: ${commandIssues.length}`,
      `Cross-page conflict rows: ${crossPageConflicts.length}`,
      `Page review rows: queue=${queueReviews.length}; completed=${completedReviews.length}; pending=${pendingReviews.length}`,
      `Diagnostics severity groups: ${diagnosticsFormatCounts((diagnosticsLogRows(diagnostics) || []).reduce((acc, row) => {
        const key = row.severity || "info";
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {}))}`,
    ];
    lines.push("", ...diagnosticsRealMediaBoundaryLines());
    lines.push("");
    if (failures.length) {
      lines.push("Refresh/API issue(s):");
      failures.slice(0, 5).forEach((failure) => lines.push(`- ${failure.name || "refresh"}: ${failure.message || "failed"}${failure.required ? " (required)" : ""}`));
    }
    if (stateIssues.length) {
      lines.push("", "State artifact issue(s) to inspect first:");
      stateIssues.slice(0, 5).forEach((item) => {
        const status = typeof window.diagnosticsStateOperatorStatus === "function" ? window.diagnosticsStateOperatorStatus(item) : item.operator_status || item.status || "review";
        const action = typeof window.diagnosticsStateRecommendedFirstAction === "function" ? window.diagnosticsStateRecommendedFirstAction(item) : "inspect this state artifact.";
        lines.push(`- ${item.label || item.target || "artifact"}: ${status}; ${item.operator_guidance || item.error || item.warning || "review required"}; first action: ${action}`);
      });
    }
    if (commandIssues.length) {
      lines.push("", "Recent command issue(s):");
      commandIssues.slice(0, 5).forEach((entry) => {
        const owner = typeof window.commandHistoryOwnerPage === "function" ? window.commandHistoryOwnerPage(entry) : "Diagnostics";
        const action = typeof window.commandHistorySuggestedAction === "function" ? window.commandHistorySuggestedAction(entry) : "inspect command details and diagnostics.";
        lines.push(`- ${entry.command || entry.raw?.command || "command"} (${owner}): ${entry.message || entry.result || "issue"}; next: ${action}`);
      });
    }
    if (pendingReviews.length || queueReviews.length || completedReviews.length) {
      lines.push("", "Cross-page row review(s):");
      pendingReviews.slice(0, 3).forEach(({ row, reasons }) => lines.push(`- Pending: ${row.local_file || row.server_out || row.manifest_path || "row"} - ${(reasons || []).slice(0, 2).join("; ") || "review"}; ${row.safe_next_action || row.operator_guidance || "build a recovery dry-run before drain."}`));
      queueReviews.slice(0, 3).forEach(({ row, reasons }) => lines.push(`- Queue: ${row.display_name || row.relative_path || row.source_path || "row"} - ${(reasons || []).slice(0, 2).join("; ") || "review"}; ${row.safe_next_action || row.operator_guidance || "use queue diagnostics before launch."}`));
      completedReviews.slice(0, 3).forEach(({ row, reasons }) => lines.push(`- Completed: ${row.lookup_title || row.output_file || row.output_path || "row"} - ${(reasons || []).slice(0, 2).join("; ") || "review"}; ${row.safe_next_action || row.operator_guidance || "compare manifest/output proof before rerun."}`));
    }
    if (crossPageConflicts.length) {
      lines.push("", "Cross-page conflict handoff(s):");
      crossPageConflicts.slice(0, 5).forEach((item) => {
        const confidence = item.confidence === "same-leaf-review" ? "advisory filename-only" : "exact path";
        lines.push(`- ${diagnosticsConflictSignalLabel(item)} (${confidence}; ${item.severity || "review"}): ${item.evidence || "review loaded Queue/Completed/Pending payloads"}; ${item.action || "review owning pages before action."}`);
      });
    }
    if (malformedLines.length) {
      lines.push("", "Malformed/stale clue(s):");
      malformedLines.forEach((line) => lines.push(`- ${line}`));
    }
    lines.push("");
    if (stateIssues.length || commandIssues.length || crossPageConflicts.length || pendingReviews.length || queueReviews.length || completedReviews.length || malformedLines.length || failures.length) {
      lines.push("Recommended order: read bounded text first, inspect backend-selected artifacts next, then return to the owning page before any launch, drain, rerun, cleanup, or close decision.");
    } else {
      lines.push("Recommended order: no immediate blockers are visible. If pages still disagree, start with State Artifact Summary, then Run Logs, then the owning page.");
    }
    lines.push("Mutation guardrail: this trail is read-only; it does not repair, clear, drain, launch, rerun, delete, rewrite, move, or publish files.");
    return lines;
  }

  function renderDiagnosticsInvestigationActions(context) {
    const container = byId("diagnostics-investigation-actions");
    if (!container) return;
    container.replaceChildren();
    const groups = diagnosticsActionGroups(diagnosticsInvestigationActions(context || {}));
    appendDiagnosticsActionGroup(container, "Read first", groups.readFirst);
    appendDiagnosticsActionGroup(container, "Open next", groups.openNext);
  }

  function renderDiagnosticsInvestigationTrail(context = {}) {
    setText("diagnostics-investigation-status", diagnosticsInvestigationStatus(context || {}));
    setText("diagnostics-investigation-trail", diagnosticsInvestigationTrailLines(context || {}).join("\n"));
    renderDiagnosticsInvestigationActions(context || {});
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
    setText("log-tail", payload.log_tail || "No pipeline log tail loaded.");
    setText("launch-logs", payload.launch_logs || "No launch logs loaded.");
  }

  async function requestDiagnosticsOpen(target) {
    if (rejectDiagnosticsOpenWhileBusy()) return;
    const normalized = String(target || "").trim();
    if (!normalized) {
      const result = {
        command: "diagnostics.open",
        ok: false,
        severity: "error",
        message: "No diagnostics target was selected.",
      };
      appendCommandResult(result);
      setDiagnosticsOpenStatus(result.message);
      return;
    }
    setDiagnosticsOpenBusy(true);
    setDiagnosticsOpenStatus("Opening...");
    try {
      const result = await apiPost("/api/diagnostics/open", { target: normalized });
      appendCommandResult(result);
      setDiagnosticsOpenStatus(result.message || "Open request sent.");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "diagnostics.open",
        ok: false,
        severity: "error",
        message,
      });
      setDiagnosticsOpenStatus(`Open failed: ${message}`);
    } finally {
      setDiagnosticsOpenBusy(false);
    }
  }

  /**
   * Public namespace for the Diagnostics page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineDiagnosticsView = {
    renderDiagnostics,
    renderDiagnosticsTriage,
    renderDiagnosticsDrilldown,
    diagnosticsTextLines,
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
    setDiagnosticsOpenStatus,
    setDiagnosticsOpenBusy,
    rejectDiagnosticsOpenWhileBusy,
    requestDiagnosticsOpen,
    isDiagnosticsOpenCommand,
    diagnosticsOpenHistoryLine,
    renderDiagnosticsOpenHistory,
  };
  window.renderDiagnostics = renderDiagnostics;
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
  window.diagnosticsLogRowKey = diagnosticsLogRowKey;
  window.diagnosticsArtifactsForLine = diagnosticsArtifactsForLine;
  window.diagnosticsLogRowActions = diagnosticsLogRowActions;
  window.diagnosticsLogRowNextStep = diagnosticsLogRowNextStep;
  window.diagnosticsLogRealMediaTraceLines = diagnosticsLogRealMediaTraceLines;
  window.diagnosticsLogGuidanceLines = diagnosticsLogGuidanceLines;
  window.renderDiagnosticsLogActions = renderDiagnosticsLogActions;
  window.filteredDiagnosticsLogRows = filteredDiagnosticsLogRows;
  window.getLastDiagnosticsLogRows = getLastDiagnosticsLogRows;
  window.selectDiagnosticsLogRow = selectDiagnosticsLogRow;
  window.getSelectedDiagnosticsLogRow = getSelectedDiagnosticsLogRow;
  window.renderDiagnosticsLogRows = renderDiagnosticsLogRows;
  window.renderDiagnosticsLogDetail = renderDiagnosticsLogDetail;
  window.selectedDiagnosticsTailTarget = selectedDiagnosticsTailTarget;
  window.selectedDiagnosticsTailMaxBytes = selectedDiagnosticsTailMaxBytes;
  window.setDiagnosticsTailTarget = setDiagnosticsTailTarget;
  window.setDiagnosticsTailStatus = setDiagnosticsTailStatus;
  window.setDiagnosticsTailBusy = setDiagnosticsTailBusy;
  window.renderDiagnosticsTail = renderDiagnosticsTail;
  window.requestDiagnosticsTail = requestDiagnosticsTail;
  window.initDiagnosticsViewEvents = initDiagnosticsViewEvents;
  window.requestDiagnosticsOpen = requestDiagnosticsOpen;
  window.isDiagnosticsOpenCommand = isDiagnosticsOpenCommand;
  window.diagnosticsOpenHistoryLine = diagnosticsOpenHistoryLine;
  window.renderDiagnosticsOpenHistory = renderDiagnosticsOpenHistory;
})();
