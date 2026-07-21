(function () {
  let lastCrossPageContext = {};
  let sampleValidationInFlight = false;
  let sampleValidationManualChecks = {};
  let selectedSampleValidationSampleSetKey = "";
  let selectedSampleValidationSampleSetRow = null;
  let selectedSampleValidationCompletedPacketKey = "";
  let selectedSampleValidationAcceptanceGateKey = "";
  let selectedSampleValidationRecordReviewKey = "";
  let selectedSampleValidationCategorySummaryKey = "";
  const SAMPLE_VALIDATION_CHECK_FIELDS = [
    ["queue_route_checked", "queue route", "sample-validation-check-queue-route"],
    ["completed_output_checked", "completed output", "sample-validation-check-completed-output"],
    ["sidecar_manifest_checked", "sidecar/manifest", "sample-validation-check-sidecar-manifest"],
    ["size_growth_checked", "size growth", "sample-validation-check-size-growth"],
    ["diagnostics_checked", "diagnostics", "sample-validation-check-diagnostics"],
    ["subtitle_checked", "subtitle", "sample-validation-check-subtitle"],
    ["audio_checked", "audio", "sample-validation-check-audio"],
    ["pending_publish_checked", "pending publish", "sample-validation-check-pending-publish"],
  ];

  // ---------------------------------------------------------------------------
  // Shared utilities — used by children (via injection) and by parent functions
  // ---------------------------------------------------------------------------

  function crossPageRows(payload) {
    return Array.isArray(payload?.rows) ? payload.rows : [];
  }

  function crossPageCount(value) {
    const number = Number(value || 0);
    return Number.isFinite(number) ? Math.max(0, Math.round(number)) : 0;
  }

  function crossPageRunnableCount(queue) {
    if (queue && Object.prototype.hasOwnProperty.call(queue, "runnable_count")) {
      return crossPageCount(queue.runnable_count);
    }
    return crossPageRows(queue).length;
  }

  function crossPageFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries.map(([key, count]) => `${key || "unknown"}=${count}`).join(", ");
  }

  function crossPageNormalizePath(value) {
    const s = String(value || "").trim().replace(/\//g, "\\");
    const unc = s.startsWith("\\\\") ? "\\\\" : "";
    return (unc + s.slice(unc.length).replace(/\\+/g, "\\")).toLowerCase();
  }

  function crossPagePathLooksAbsolute(value) {
    const text = String(value || "").trim();
    return Boolean(text && (/^[a-zA-Z]:[\\/]/.test(text) || /^\\\\/.test(text) || text.includes("\\") || text.includes("/")));
  }

  function crossPageLeaf(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const parts = text.split(/[\\/]/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : text;
  }

  function crossPageFirstValue(row, keys) {
    for (const key of keys) {
      const value = row?.[key];
      if (value !== undefined && value !== null && String(value).trim()) return String(value).trim();
    }
    return "";
  }

  function crossPagePathSet(rows, keys) {
    const values = new Set();
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      keys.forEach((key) => {
        const normalized = crossPageNormalizePath(row?.[key]);
        if (normalized) values.add(normalized);
      });
    });
    return values;
  }

  function crossPageIntersectionCount(left, right) {
    let count = 0;
    left.forEach((value) => {
      if (right.has(value)) count += 1;
    });
    return count;
  }

  function crossPageDiagnosticsCounts(diagnostics) {
    const view = window.mediaPipelineDiagnosticsView || {};
    const sourceLines = typeof view.diagnosticsSourceLines === "function"
      ? view.diagnosticsSourceLines(diagnostics || {})
      : [];
    const severityForLine = typeof view.diagnosticsSeverityForLine === "function"
      ? view.diagnosticsSeverityForLine
      : function () { return "info"; };
    return sourceLines.reduce((counts, entry) => {
      const severity = severityForLine(entry.line);
      counts[severity] = (counts[severity] || 0) + 1;
      return counts;
    }, {});
  }

  function crossPageRuntimeFailureCount(counts) {
    return Object.entries(counts && typeof counts === "object" ? counts : {}).reduce((total, [key, value]) => {
      const text = String(key || "").toLowerCase();
      if (!/fail|skip|stop|error|blocked|conflict/.test(text)) return total;
      return total + crossPageCount(value);
    }, 0);
  }

  // ---------------------------------------------------------------------------
  // Per-page path accessors — injected into both conflict and sample children
  // ---------------------------------------------------------------------------

  function crossPageQueueSource(row) {
    return crossPageFirstValue(row, ["source_path", "path", "file", "input_path"]);
  }

  function crossPageQueueRuntimeOutput(row) {
    return crossPageFirstValue(row, ["runtime_outcome_output_path", "output_path", "server_out"]);
  }

  function crossPageCompletedSource(row) {
    return crossPageFirstValue(row, ["source_path", "SourcePath", "input_path"]);
  }

  function crossPageCompletedOutput(row) {
    return crossPageFirstValue(row, ["output_path", "server_out", "destination_path", "final_path", "output_file"]);
  }

  function crossPagePendingSource(row) {
    return crossPageFirstValue(row, ["source_path", "input_path", "source_file"]);
  }

  function crossPagePendingDestination(row) {
    return crossPageFirstValue(row, ["server_out", "destination_path", "output_path"]);
  }

  function crossPagePendingLocal(row) {
    return crossPageFirstValue(row, ["local_file", "payload_path", "manifest_path"]);
  }

  function crossPageRowLabel(row, kind) {
    if (kind === "queue") {
      return crossPageFirstValue(row, ["display_name", "relative_path", "source_path"]) || "(queue row)";
    }
    if (kind === "completed") {
      return crossPageFirstValue(row, ["lookup_title", "output_file", "title", "output_path", "source_path"]) || "(completed row)";
    }
    if (kind === "pending") {
      return crossPageFirstValue(row, ["lookup_title", "output_file", "title", "server_out", "local_file", "source_path"]) || "(pending row)";
    }
    return "(row)";
  }

  // ---------------------------------------------------------------------------
  // Consume split children — conflict, sample, settings, sampleValidation
  // Stashes are deleted immediately after consumption; zero extra globals remain.
  // ---------------------------------------------------------------------------

  // -- Conflict child --
  const __conflictMod = window.__crossPageConflictModule || {};
  delete window.__crossPageConflictModule;
  const _conflict = typeof __conflictMod.createCrossPageConflictModule === "function"
    ? __conflictMod.createCrossPageConflictModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      crossPageCount,
      crossPageCompletedOutput,
      crossPageCompletedSource,
      crossPageLeaf,
      crossPageNormalizePath,
      crossPagePathLooksAbsolute,
      crossPagePendingDestination,
      crossPagePendingLocal,
      crossPagePendingSource,
      crossPageQueueRuntimeOutput,
      crossPageQueueSource,
      crossPageRowLabel,
      crossPageRows,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      setText: typeof setText === "function" ? setText : window.setText,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const _conflictNoop = function () {};
  const {
    crossPageConflictRows = _conflictNoop,
    crossPageConflictSignalLabel = _conflictNoop,
    crossPageConflictStatus = _conflictNoop,
    crossPageConflictSummary = _conflictNoop,
    crossPageConflictScope = _conflictNoop,
    crossPageSelectConflict = _conflictNoop,
    renderCrossPageConflictBoard = _conflictNoop,
  } = _conflict;

  // -- Sample child --
  const __sampleMod = window.__crossPageSampleModule || {};
  delete window.__crossPageSampleModule;
  const _sample = typeof __sampleMod.createCrossPageSampleModule === "function"
    ? __sampleMod.createCrossPageSampleModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      crossPageCompletedOutput,
      crossPageCompletedSource,
      crossPageLeaf,
      crossPageNormalizePath,
      crossPagePathLooksAbsolute,
      crossPagePendingDestination,
      crossPagePendingLocal,
      crossPagePendingSource,
      crossPageQueueRuntimeOutput,
      crossPageQueueSource,
      crossPageRowLabel,
      crossPageRows,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      setText: typeof setText === "function" ? setText : window.setText,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const _sampleNoop = function () {};
  const {
    crossPageSampleRows = _sampleNoop,
    crossPageSampleStatus = _sampleNoop,
    crossPageSampleEvidenceForSeed = _sampleNoop,
    crossPageValidationTemplateStatus = _sampleNoop,
    crossPageValidationTemplateLines = _sampleNoop,
    renderCrossPageSampleCorrelation = _sampleNoop,
    renderCrossPageValidationTemplate = _sampleNoop,
  } = _sample;

  // -- Settings child --
  const __settingsMod = window.__crossPageSettingsModule || {};
  delete window.__crossPageSettingsModule;
  const _settings = typeof __settingsMod.createCrossPageSettingsModule === "function"
    ? __settingsMod.createCrossPageSettingsModule({ crossPageCount })
    : {};
  const _settingsNoop = function () {};
  const {
    crossPageSettingsPolicyEvidence = _settingsNoop,
  } = _settings;

  // -- SampleValidation child (existing split, landed Wave 1) --
  const crossPageSampleValidationState = {
    get lastCrossPageContext() { return lastCrossPageContext; },
    set lastCrossPageContext(value) { lastCrossPageContext = value || {}; },
    get sampleValidationInFlight() { return sampleValidationInFlight; },
    set sampleValidationInFlight(value) { sampleValidationInFlight = Boolean(value); },
    get sampleValidationManualChecks() { return sampleValidationManualChecks; },
    set sampleValidationManualChecks(value) { sampleValidationManualChecks = value && typeof value === "object" ? value : {}; },
    get selectedSampleValidationSampleSetKey() { return selectedSampleValidationSampleSetKey; },
    set selectedSampleValidationSampleSetKey(value) { selectedSampleValidationSampleSetKey = value || ""; },
    get selectedSampleValidationSampleSetRow() { return selectedSampleValidationSampleSetRow; },
    set selectedSampleValidationSampleSetRow(value) { selectedSampleValidationSampleSetRow = value || null; },
    get selectedSampleValidationCompletedPacketKey() { return selectedSampleValidationCompletedPacketKey; },
    set selectedSampleValidationCompletedPacketKey(value) { selectedSampleValidationCompletedPacketKey = value || ""; },
    get selectedSampleValidationAcceptanceGateKey() { return selectedSampleValidationAcceptanceGateKey; },
    set selectedSampleValidationAcceptanceGateKey(value) { selectedSampleValidationAcceptanceGateKey = value || ""; },
    get selectedSampleValidationRecordReviewKey() { return selectedSampleValidationRecordReviewKey; },
    set selectedSampleValidationRecordReviewKey(value) { selectedSampleValidationRecordReviewKey = value || ""; },
    get selectedSampleValidationCategorySummaryKey() { return selectedSampleValidationCategorySummaryKey; },
    set selectedSampleValidationCategorySummaryKey(value) { selectedSampleValidationCategorySummaryKey = value || ""; },
  };
  const crossPageSampleValidationModule = window.__crossPageSampleValidationModule || {};
  delete window.__crossPageSampleValidationModule;
  const crossPageSampleValidation = typeof crossPageSampleValidationModule.createCrossPageSampleValidationModule === "function"
    ? crossPageSampleValidationModule.createCrossPageSampleValidationModule({
      apiPost: (...args) => {
        const request = typeof window.apiPost === "function"
          ? window.apiPost
          : typeof apiPost === "function"
            ? apiPost
            : null;
        if (typeof request !== "function") {
          return Promise.reject(new Error("apiPost is not available."));
        }
        return request(...args);
      },
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      appendCommandResult: window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      crossPageCount,
      crossPageDiagnosticsCounts,
      crossPageFormatCounts,
      crossPageRows,
      crossPageSampleRows,
      crossPageSettingsPolicyEvidence,
      crossPageValidationTemplateLines,
      crossPageSampleValidationState,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      refreshAll: typeof refreshAll === "function" ? refreshAll : window.refreshAll,
      sampleValidationCheckFields: SAMPLE_VALIDATION_CHECK_FIELDS,
      setText: typeof setText === "function" ? setText : window.setText,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const crossPageSampleValidationNoop = function () {};
  const {
    crossPageSamplePageStrength = crossPageSampleValidationNoop,
    crossPageWorksheetRow = crossPageSampleValidationNoop,
    crossPageSampleValidationEvidence = crossPageSampleValidationNoop,
    crossPageRealMediaWorksheetRows = crossPageSampleValidationNoop,
    crossPageRealMediaWorksheetStatus = crossPageSampleValidationNoop,
    crossPageRealMediaWorksheetSummary = crossPageSampleValidationNoop,
    crossPageRealMediaWorksheetDetailLines = crossPageSampleValidationNoop,
    renderCrossPageRealMediaWorksheet = crossPageSampleValidationNoop,
    sampleValidationProofStrength = crossPageSampleValidationNoop,
    sampleValidationPath = crossPageSampleValidationNoop,
    sampleValidationEvidence = crossPageSampleValidationNoop,
    sampleValidationChecks = crossPageSampleValidationNoop,
    sampleValidationChecksFromUi = crossPageSampleValidationNoop,
    sampleValidationMergedChecks = crossPageSampleValidationNoop,
    sampleValidationShellSurface = crossPageSampleValidationNoop,
    syncSampleValidationCheckControls = crossPageSampleValidationNoop,
    sampleValidationCheckedSummary = crossPageSampleValidationNoop,
    sampleValidationLogSummaryLines = crossPageSampleValidationNoop,
    sampleValidationAuditPayload = crossPageSampleValidationNoop,
    sampleValidationAuditSummaryLines = crossPageSampleValidationNoop,
    sampleValidationPolicyAlignmentPayload = crossPageSampleValidationNoop,
    sampleValidationPolicyAlignmentSummaryLines = crossPageSampleValidationNoop,
    sampleValidationReadinessLines = crossPageSampleValidationNoop,
    sampleValidationReconciliationLines = crossPageSampleValidationNoop,
    sampleValidationGapPayload = crossPageSampleValidationNoop,
    sampleValidationGapRows = crossPageSampleValidationNoop,
    sampleValidationGapState = crossPageSampleValidationNoop,
    sampleValidationGapStatus = crossPageSampleValidationNoop,
    sampleValidationGapSummaryLines = crossPageSampleValidationNoop,
    sampleValidationGapDetailLines = crossPageSampleValidationNoop,
    renderSampleValidationGapSummary = crossPageSampleValidationNoop,
    sampleValidationRunbookPayload = crossPageSampleValidationNoop,
    sampleValidationRunbookRows = crossPageSampleValidationNoop,
    sampleValidationRunbookState = crossPageSampleValidationNoop,
    sampleValidationRunbookStatus = crossPageSampleValidationNoop,
    sampleValidationRunbookSummaryLines = crossPageSampleValidationNoop,
    sampleValidationRunbookMarkdownLines = crossPageSampleValidationNoop,
    sampleValidationRunbookDetailLines = crossPageSampleValidationNoop,
    renderSampleValidationRunbook = crossPageSampleValidationNoop,
    sampleValidationPilotPlanLines = crossPageSampleValidationNoop,
    sampleValidationCutoverPayload = crossPageSampleValidationNoop,
    sampleValidationCutoverRows = crossPageSampleValidationNoop,
    sampleValidationCutoverState = crossPageSampleValidationNoop,
    sampleValidationCutoverStatus = crossPageSampleValidationNoop,
    sampleValidationCutoverSummaryLines = crossPageSampleValidationNoop,
    sampleValidationCutoverDetailLines = crossPageSampleValidationNoop,
    renderSampleValidationCutoverGate = crossPageSampleValidationNoop,
    sampleValidationSampleSetPayload = crossPageSampleValidationNoop,
    sampleValidationSampleSetRows = crossPageSampleValidationNoop,
    sampleValidationSampleSetState = crossPageSampleValidationNoop,
    sampleValidationSampleSetStatus = crossPageSampleValidationNoop,
    sampleValidationSampleSetSummaryLines = crossPageSampleValidationNoop,
    sampleValidationSampleSetCoverageLine = crossPageSampleValidationNoop,
    sampleValidationSampleSetDetailLines = crossPageSampleValidationNoop,
    sampleValidationSampleSetKey = crossPageSampleValidationNoop,
    selectSampleValidationSampleSetRow = crossPageSampleValidationNoop,
    selectedSampleValidationSampleSet = crossPageSampleValidationNoop,
    sampleValidationCategorySummaryRows = crossPageSampleValidationNoop,
    sampleValidationCategorySummaryState = crossPageSampleValidationNoop,
    sampleValidationCategorySummaryStatus = crossPageSampleValidationNoop,
    sampleValidationCategorySummaryLines = crossPageSampleValidationNoop,
    sampleValidationCategorySummaryDetailLines = crossPageSampleValidationNoop,
    selectedSampleValidationCategorySummaryRow = crossPageSampleValidationNoop,
    renderSampleValidationCategorySummary = crossPageSampleValidationNoop,
    useSelectedSampleSetCategory = crossPageSampleValidationNoop,
    renderSampleValidationSampleSetGuide = crossPageSampleValidationNoop,
    sampleValidationExecutionRows = crossPageSampleValidationNoop,
    sampleValidationExecutionState = crossPageSampleValidationNoop,
    sampleValidationExecutionStatus = crossPageSampleValidationNoop,
    sampleValidationExecutionSummaryLines = crossPageSampleValidationNoop,
    sampleValidationExecutionDetailLines = crossPageSampleValidationNoop,
    renderSampleValidationExecutionChecklist = crossPageSampleValidationNoop,
    sampleValidationWorksheetPayload = crossPageSampleValidationNoop,
    sampleValidationWorksheetRows = crossPageSampleValidationNoop,
    sampleValidationPathToken = crossPageSampleValidationNoop,
    sampleValidationWorksheetRunMatchesSample = crossPageSampleValidationNoop,
    sampleValidationWorksheetStatus = crossPageSampleValidationNoop,
    sampleValidationWorksheetSummaryLines = crossPageSampleValidationNoop,
    sampleValidationWorksheetDetailLines = crossPageSampleValidationNoop,
    sampleValidationRecordRows = crossPageSampleValidationNoop,
    sampleValidationReconciliationRows = crossPageSampleValidationNoop,
    sampleValidationReconciliationForRecord = crossPageSampleValidationNoop,
    sampleValidationRecordMatchesSample = crossPageSampleValidationNoop,
    sampleValidationRecordComparisonRowsForPaths = crossPageSampleValidationNoop,
    sampleValidationRecordsMatchingSample = crossPageSampleValidationNoop,
    sampleValidationRecordDecisionIsAccepted = crossPageSampleValidationNoop,
    sampleValidationRecordReviewCandidate = crossPageSampleValidationNoop,
    sampleValidationRecordReviewRowStatus = crossPageSampleValidationNoop,
    sampleValidationRecordReviewRows = crossPageSampleValidationNoop,
    sampleValidationRecordReviewStatus = crossPageSampleValidationNoop,
    sampleValidationRecordReviewSummaryLines = crossPageSampleValidationNoop,
    sampleValidationRecordReviewDetailLines = crossPageSampleValidationNoop,
    selectedSampleValidationRecordReviewRow = crossPageSampleValidationNoop,
    renderSampleValidationRecordReview = crossPageSampleValidationNoop,
    renderSampleValidationWorksheets = crossPageSampleValidationNoop,
    buildSampleValidationRequest = crossPageSampleValidationNoop,
    sampleValidationSummaryLines = crossPageSampleValidationNoop,
    sampleValidationStatus = crossPageSampleValidationNoop,
    sampleValidationRecordLines = crossPageSampleValidationNoop,
    sampleValidationRecordCurrentEvidenceLabel = crossPageSampleValidationNoop,
    sampleValidationRecordGapLabel = crossPageSampleValidationNoop,
    sampleValidationRecordRowState = crossPageSampleValidationNoop,
    renderSampleValidationRecords = crossPageSampleValidationNoop,
    sampleValidationCompletedPacketRows = crossPageSampleValidationNoop,
    sampleValidationCompletedPacketPostureStatus = crossPageSampleValidationNoop,
    sampleValidationCompletedPacketStatus = crossPageSampleValidationNoop,
    sampleValidationCompletedPolicyReconciliationRow = crossPageSampleValidationNoop,
    sampleValidationCompletedPolicyReconciliationStatus = crossPageSampleValidationNoop,
    sampleValidationCompletedPacketSummaryLines = crossPageSampleValidationNoop,
    sampleValidationCompletedPacketDetailLines = crossPageSampleValidationNoop,
    sampleValidationCompletedPacketMarkdownLines = crossPageSampleValidationNoop,
    selectedSampleValidationCompletedPacketRow = crossPageSampleValidationNoop,
    renderSampleValidationCompletedPacketHandoff = crossPageSampleValidationNoop,
    sampleValidationAcceptanceCheckLabels = crossPageSampleValidationNoop,
    sampleValidationAcceptanceGateRowStatus = crossPageSampleValidationNoop,
    sampleValidationAcceptanceGateRows = crossPageSampleValidationNoop,
    sampleValidationAcceptanceGateStatus = crossPageSampleValidationNoop,
    sampleValidationAcceptanceGateSummaryLines = crossPageSampleValidationNoop,
    sampleValidationAcceptanceGateDetailLines = crossPageSampleValidationNoop,
    selectedSampleValidationAcceptanceGateRow = crossPageSampleValidationNoop,
    renderSampleValidationAcceptanceGate = crossPageSampleValidationNoop,
    renderSampleValidationRecordPanel = crossPageSampleValidationNoop,
    sampleValidationResultLines = crossPageSampleValidationNoop,
    previewSampleValidationRecord = crossPageSampleValidationNoop,
    appendSampleValidationRecord = crossPageSampleValidationNoop,
    initSampleValidationViewEvents = crossPageSampleValidationNoop,
  } = crossPageSampleValidation;

  // ---------------------------------------------------------------------------
  // Top-level status and context summary — parent-owned orchestration layer
  // (uses crossPageConflictRows / crossPageConflictSummary from conflict child)
  // ---------------------------------------------------------------------------

  function crossPageStatus(context) {
    const failures = Array.isArray(context.failures) ? context.failures : [];
    if (failures.some((item) => item.required)) return "Backend issue";
    const queue = context.queue || {};
    const completed = context.completed || {};
    const pending = context.pending || {};
    if (pending.error || queue.error || completed.error) return "Payload issue";
    const conflictRows = crossPageConflictRows(context || {});
    if (conflictRows.some((row) => row.severity === "blocked")) return "Conflict blocker";
    if (conflictRows.some((row) => row.severity === "warning")) return "Conflict review";
    if (crossPageCount(pending.issue_count) || crossPageCount(pending.health_count)) return "Pending review";
    if (crossPageCount(completed.missing_output_count) || crossPageCount(completed.size_growth_over_5_count)) return "Completed review";
    if (crossPageRuntimeFailureCount(queue.runtime_outcome_status_counts) || crossPageRuntimeFailureCount(completed.runtime_outcome_status_counts)) return "Runtime review";
    if (crossPageRunnableCount(queue)) return "Queue ready";
    return "Context loaded";
  }

  function crossPageStatusTone(status) {
    const text = String(status || "").trim().toLowerCase();
    if (/backend|payload|blocker|blocked/.test(text)) return "danger";
    if (/review|stale|runtime|pending|completed/.test(text)) return "warning";
    if (/ready|loaded/.test(text)) return "success";
    return "info";
  }

  function crossPageNextStep(context) {
    const queue = context.queue || {};
    const completed = context.completed || {};
    const pending = context.pending || {};
    const diagnosticsCounts = crossPageDiagnosticsCounts(context.diagnostics || {});
    if (crossPageCount(pending.issue_count) || crossPageCount(pending.health_count)) {
      return "Review Pending Publish issues before rerunning or draining; use the row diagnostics and backend-allowlisted diagnostics links.";
    }
    const conflictRows = crossPageConflictRows(context || {});
    if (conflictRows.some((row) => row.severity === "blocked")) {
      return "Review cross-page blocked overlaps before Launch, drain, rerun, cleanup, or output deletion.";
    }
    if (conflictRows.some((row) => row.severity === "warning")) {
      return "Review exact cross-page overlaps before Launch; filename-only matches are advisory and need folder comparison.";
    }
    if (crossPageCount(completed.missing_output_count)) {
      if (!crossPageRows(pending).length) {
        return "Completed has missing-output rows while Pending Publish is empty. Review Completed Output Proof, durable drain summary, Run Logs, and Last Stderr before rerun; empty pending state is not publish proof.";
      }
      return "Review Completed missing-output rows before trusting completed history or rerunning files.";
    }
    if (crossPageCount(completed.size_growth_over_5_count)) {
      return "Review Completed size-growth rows before treating recent encodes as successful output policy.";
    }
    if (diagnosticsCounts.error || diagnosticsCounts.warning) {
      return "Open Diagnostics and inspect the current warnings/errors before unattended operation.";
    }
    if (crossPageRunnableCount(queue)) {
      return "Queue has visible work. Use Launch for backend-owned processing after schedule and settings preflight look correct.";
    }
    return "No immediate cross-page conflict is visible. Refresh before starting long unattended work.";
  }

  function crossPageInvestigationOrder(context) {
    const queue = context.queue || {};
    const completed = context.completed || {};
    const pending = context.pending || {};
    const diagnosticsCounts = crossPageDiagnosticsCounts(context.diagnostics || {});
    const steps = ["Operator investigation order:"];
    const addStep = (text) => steps.push(`${steps.length}. ${text}`);
    if (context.failures?.length || diagnosticsCounts.error || diagnosticsCounts.warning) {
      addStep("Diagnostics: resolve refresh failures, malformed state, Last Stderr, and ActiveJobs uncertainty first.");
    }
    if (crossPageCount(pending.issue_count) || crossPageCount(pending.health_count)) {
      addStep("Pending Publish: review do-not-drain, missing payload, sidecar, invalid manifest, and warning rows before rerun or drain.");
    }
    if (crossPageCount(completed.missing_output_count) || crossPageCount(completed.size_growth_over_5_count) || crossPageCount(completed.missing_sidecar_count) || crossPageCount(completed.output_sidecar_mismatch_count)) {
      addStep("Completed: verify output proof, size growth, and sidecar consistency before treating prior work as success.");
    }
    if (crossPageCount(queue.invalid_row_count) || crossPageCount(queue.blocked_row_count)) {
      addStep("Queue: inspect blocked/invalid rows before Launch.");
    }
    if (crossPageRunnableCount(queue)) {
      addStep("Launch: start backend-owned processing only after Queue, Completed, Pending Publish, Diagnostics, schedule, and saved settings agree.");
    } else {
      addStep("Launch: do not start processing from empty or unresolved context; refresh and inspect owning pages first.");
    }
    if (steps.length === 2) {
      steps.splice(1, 0, "1. No cross-page blocker is obvious from loaded payloads; refresh once before unattended operation.");
      steps[2] = `2. ${steps[2].replace(/^\d+\.\s*/, "")}`;
    }
    return steps;
  }

  function crossPageContextLines(context) {
    const queue = context.queue || {};
    const completed = context.completed || {};
    const pending = context.pending || {};
    const diagnosticsCounts = crossPageDiagnosticsCounts(context.diagnostics || {});
    const queueRows = crossPageRows(queue);
    const completedRows = crossPageRows(completed);
    const pendingRows = crossPageRows(pending);
    const queueSources = crossPagePathSet(queueRows, ["source_path", "path", "file", "input_path"]);
    const completedSources = crossPagePathSet(completedRows, ["source_path", "SourcePath"]);
    const completedOutputs = crossPagePathSet(completedRows, ["output_path", "output_file", "server_out"]);
    const pendingSources = crossPagePathSet(pendingRows, ["source_path"]);
    const pendingOutputs = crossPagePathSet(pendingRows, ["server_out"]);
    const queueCompletedSourceOverlap = crossPageIntersectionCount(queueSources, completedSources);
    const pendingCompletedOutputOverlap = crossPageIntersectionCount(pendingOutputs, completedOutputs);
    const queuePendingSourceOverlap = crossPageIntersectionCount(queueSources, pendingSources);
    const conflictRows = crossPageConflictRows(context || {});
    const lines = [
      "Cross-page context is read-only and derived from already-loaded backend payloads.",
      `Queue: rows=${queueRows.length}, runnable=${crossPageRunnableCount(queue)}, age=${String(queue.snapshot_file_freshness_status || "unknown")}, excluded=${crossPageCount(queue.completed_excluded_count)}`,
      `Completed: rows=${completed.count || completedRows.length || 0}, missing outputs=${crossPageCount(completed.missing_output_count)}, size growth >5%=${crossPageCount(completed.size_growth_over_5_count)}, manifest freshness=${completed.manifest_freshness_status || "unknown"}`,
      `Pending Publish: rows=${pending.count || pendingRows.length || 0}, ready=${crossPageCount(pending.ready_count)}, issue=${crossPageCount(pending.issue_count)}, diagnostic statuses=${crossPageFormatCounts(pending.diagnostic_status_counts)}`,
      crossPageCount(completed.missing_output_count) && !pendingRows.length
        ? "Missing-output posture: Completed reports missing outputs while Pending Publish is empty; use Completed Output Proof, durable drain summary, Run Logs, and Last Stderr before rerun."
        : "",
      `Diagnostics: error=${diagnosticsCounts.error || 0}, warning=${diagnosticsCounts.warning || 0}, active=${diagnosticsCounts.active || 0}`,
      "",
      "Exact-match cross-checks:",
      `- Queued source also in Completed source history: ${queueCompletedSourceOverlap}`,
      `- Pending destination also in Completed output history: ${pendingCompletedOutputOverlap}`,
      `- Pending source also visible in Queue: ${queuePendingSourceOverlap}`,
      crossPageConflictSummary(context || {}),
      "",
      `Runtime history: queue matches=${crossPageCount(queue.runtime_outcome_match_count)}, completed matches=${crossPageCount(completed.runtime_outcome_match_count)}`,
      `Queue runtime statuses: ${crossPageFormatCounts(queue.runtime_outcome_status_counts)}`,
      `Completed runtime statuses: ${crossPageFormatCounts(completed.runtime_outcome_status_counts)}`,
      "",
      ...crossPageInvestigationOrder(context),
      "",
      `Next step: ${crossPageNextStep(context)}`,
      "Mutation guardrail: this panel does not start, repair, rerun, drain, delete, or rewrite files. Use backend-owned page commands only.",
    ];
    const failures = Array.isArray(context.failures) ? context.failures : [];
    if (failures.length) {
      lines.push("", "Refresh issue(s):");
      failures.slice(0, 6).forEach((failure) => {
        lines.push(`- ${failure.name || "read"}: ${failure.message || ""}`);
      });
    }
    return lines;
  }

  function crossPageContextTiles(context = {}) {
    const queue = context.queue || {};
    const completed = context.completed || {};
    const pending = context.pending || {};
    const diagnosticsCounts = crossPageDiagnosticsCounts(context.diagnostics || {});
    const queueRows = crossPageRows(queue);
    const completedRows = crossPageRows(completed);
    const pendingRows = crossPageRows(pending);
    const conflictRows = crossPageConflictRows(context || {});
    const status = crossPageStatus(context);
    const queueRunnable = crossPageRunnableCount(queue);
    const queueIssues = crossPageCount(queue.invalid_row_count) + crossPageCount(queue.blocked_row_count);
    const completedMissing = crossPageCount(completed.missing_output_count);
    const completedSizeGrowth = crossPageCount(completed.size_growth_over_5_count);
    const pendingReady = crossPageCount(pending.ready_count);
    const pendingIssues = crossPageCount(pending.issue_count);
    const pendingHealth = crossPageCount(pending.health_count);
    const diagnosticErrors = diagnosticsCounts.error || 0;
    const diagnosticWarnings = diagnosticsCounts.warning || 0;
    const diagnosticActive = diagnosticsCounts.active || 0;
    const conflictBlocked = conflictRows.filter((row) => row.severity === "blocked").length;
    const conflictWarnings = conflictRows.filter((row) => row.severity === "warning").length;
    return [
      {
        label: "Queue",
        value: `${queueRunnable} runnable`,
        detail: `rows=${queueRows.length}, age=${String(queue.snapshot_file_freshness_status || "unknown")}, excluded=${crossPageCount(queue.completed_excluded_count)}`,
        tone: queueIssues ? "warning" : (queueRunnable ? "info" : "muted"),
      },
      {
        label: "Completed",
        value: `${completedMissing} missing`,
        detail: `rows=${completed.count || completedRows.length || 0}, size >5%=${completedSizeGrowth}, freshness=${completed.manifest_freshness_status || "unknown"}`,
        tone: completedMissing ? "danger" : (completedSizeGrowth ? "warning" : "success"),
      },
      {
        label: "Pending Publish",
        value: `${pendingReady} ready`,
        detail: `rows=${pending.count || pendingRows.length || 0}, issue=${pendingIssues}, health=${pendingHealth}`,
        tone: pendingIssues ? "danger" : (pendingHealth ? "warning" : (pendingReady ? "success" : "muted")),
      },
      {
        label: "Diagnostics",
        value: `${diagnosticErrors} error / ${diagnosticWarnings} warning`,
        detail: `active=${diagnosticActive}, statuses=${crossPageFormatCounts(pending.diagnostic_status_counts)}`,
        tone: diagnosticErrors ? "danger" : (diagnosticWarnings ? "warning" : (diagnosticActive ? "info" : "success")),
      },
      {
        label: "Next Step",
        value: status,
        detail: `conflicts=${conflictBlocked} blocked, ${conflictWarnings} warning. ${crossPageNextStep(context)}`,
        tone: crossPageStatusTone(status),
        wide: true,
      },
    ];
  }

  // ---------------------------------------------------------------------------
  // Top-level render orchestrator
  // ---------------------------------------------------------------------------

  function renderCrossPageContext(context = {}) {
    lastCrossPageContext = context || {};
    window.mediaPipelineLastCrossPageContext = lastCrossPageContext;
    if (typeof setPanelStatus === "function") setPanelStatus("cross-page-context-status", crossPageStatus(context));
    else setText("cross-page-context-status", crossPageStatus(context));
    const renderReviewTileBoard = window.mediaPipelineDom?.renderReviewTileBoard || window.renderReviewTileBoard;
    if (typeof renderReviewTileBoard === "function") {
      renderReviewTileBoard("cross-page-context-board", crossPageContextTiles(context), {
        emptyTile: {
          label: "Context",
          value: "Not loaded",
          detail: "Queue, Completed, Pending Publish, and Diagnostics context has not loaded yet.",
          tone: "muted",
          wide: true,
        },
      });
    }
    setText("cross-page-context-summary", crossPageContextLines(context).join("\n"));
    renderCrossPageConflictBoard(context);
    renderCrossPageSampleCorrelation(context);
    renderCrossPageValidationTemplate(context);
    renderCrossPageRealMediaWorksheet(context);
    renderSampleValidationRecordPanel(context);
  }

  // ---------------------------------------------------------------------------
  // Namespace + flat exports — identical shape to pre-split
  // ---------------------------------------------------------------------------

  /**
   * Public namespace for the cross-page context module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineCrossPageContextView = {
    renderCrossPageContext,
    crossPageContextLines,
    crossPageContextTiles,
    crossPageStatus,
    crossPageNextStep,
    crossPageInvestigationOrder,
    renderCrossPageConflictBoard,
    crossPageConflictRows,
    crossPageConflictStatus,
    crossPageConflictSummary,
    renderCrossPageSampleCorrelation,
    crossPageSampleRows,
    crossPageSampleStatus,
    crossPageSampleEvidenceForSeed,
    crossPageValidationTemplateStatus,
    crossPageValidationTemplateLines,
    renderCrossPageValidationTemplate,
    crossPageSettingsPolicyEvidence,
    crossPageSampleValidationEvidence,
    crossPageRealMediaWorksheetRows,
    crossPageRealMediaWorksheetStatus,
    crossPageRealMediaWorksheetSummary,
    renderCrossPageRealMediaWorksheet,
    sampleValidationCutoverRows,
    sampleValidationCutoverStatus,
    sampleValidationCutoverSummaryLines,
    sampleValidationCutoverDetailLines,
    renderSampleValidationCutoverGate,
    sampleValidationGapPayload,
    sampleValidationGapRows,
    sampleValidationGapStatus,
    sampleValidationGapSummaryLines,
    sampleValidationGapDetailLines,
    renderSampleValidationGapSummary,
    sampleValidationRunbookPayload,
    sampleValidationRunbookRows,
    sampleValidationRunbookStatus,
    sampleValidationRunbookSummaryLines,
    sampleValidationRunbookMarkdownLines,
    sampleValidationRunbookDetailLines,
    renderSampleValidationRunbook,
    sampleValidationSampleSetRows,
    sampleValidationSampleSetStatus,
    sampleValidationSampleSetSummaryLines,
    sampleValidationSampleSetCoverageLine,
    sampleValidationSampleSetDetailLines,
    sampleValidationSampleSetKey,
    useSelectedSampleSetCategory,
    renderSampleValidationSampleSetGuide,
    sampleValidationCategorySummaryRows,
    sampleValidationCategorySummaryStatus,
    sampleValidationCategorySummaryLines,
    sampleValidationCategorySummaryDetailLines,
    renderSampleValidationCategorySummary,
    sampleValidationExecutionRows,
    sampleValidationExecutionStatus,
    renderSampleValidationExecutionChecklist,
    sampleValidationWorksheetRows,
    sampleValidationWorksheetRunMatchesSample,
    sampleValidationWorksheetSummaryLines,
    sampleValidationWorksheetDetailLines,
    sampleValidationRecordRows,
    sampleValidationReconciliationRows,
    sampleValidationReconciliationForRecord,
    sampleValidationRecordMatchesSample,
    sampleValidationRecordComparisonRowsForPaths,
    sampleValidationRecordsMatchingSample,
    sampleValidationRecordLines,
    renderSampleValidationWorksheets,
    sampleValidationCompletedPacketRows,
    sampleValidationCompletedPacketStatus,
    sampleValidationCompletedPolicyReconciliationRow,
    sampleValidationCompletedPolicyReconciliationStatus,
    sampleValidationCompletedPacketSummaryLines,
    sampleValidationCompletedPacketDetailLines,
    sampleValidationCompletedPacketMarkdownLines,
    renderSampleValidationCompletedPacketHandoff,
    sampleValidationAcceptanceGateRows,
    sampleValidationAcceptanceGateStatus,
    sampleValidationAcceptanceGateSummaryLines,
    sampleValidationAcceptanceGateDetailLines,
    renderSampleValidationAcceptanceGate,
    sampleValidationRecordReviewRows,
    sampleValidationRecordReviewStatus,
    sampleValidationRecordReviewSummaryLines,
    sampleValidationRecordReviewDetailLines,
    renderSampleValidationRecordReview,
    sampleValidationShellSurface,
    buildSampleValidationRequest,
    renderSampleValidationRecordPanel,
    initSampleValidationViewEvents,
    crossPageConflictSignalLabel,
    crossPagePathSet,
    crossPageIntersectionCount,
    crossPageDiagnosticsCounts,
  };
  window.renderCrossPageContext = renderCrossPageContext;
  window.renderCrossPageConflictBoard = renderCrossPageConflictBoard;
  window.renderCrossPageSampleCorrelation = renderCrossPageSampleCorrelation;
  window.renderCrossPageValidationTemplate = renderCrossPageValidationTemplate;
  window.crossPageConflictRows = crossPageConflictRows;
  window.crossPageSampleRows = crossPageSampleRows;
  window.crossPageValidationTemplateLines = crossPageValidationTemplateLines;
  window.crossPageSampleValidationEvidence = crossPageSampleValidationEvidence;
  window.crossPageRealMediaWorksheetRows = crossPageRealMediaWorksheetRows;
  window.crossPageRealMediaWorksheetStatus = crossPageRealMediaWorksheetStatus;
  window.renderCrossPageRealMediaWorksheet = renderCrossPageRealMediaWorksheet;
  window.sampleValidationCutoverRows = sampleValidationCutoverRows;
  window.sampleValidationGapPayload = sampleValidationGapPayload;
  window.sampleValidationGapSummaryLines = sampleValidationGapSummaryLines;
  window.sampleValidationRunbookPayload = sampleValidationRunbookPayload;
  window.sampleValidationRunbookSummaryLines = sampleValidationRunbookSummaryLines;
  window.sampleValidationRunbookMarkdownLines = sampleValidationRunbookMarkdownLines;
  window.sampleValidationSampleSetRows = sampleValidationSampleSetRows;
  window.sampleValidationSampleSetCoverageLine = sampleValidationSampleSetCoverageLine;
  window.sampleValidationSampleSetKey = sampleValidationSampleSetKey;
  window.sampleValidationExecutionRows = sampleValidationExecutionRows;
  window.sampleValidationWorksheetRows = sampleValidationWorksheetRows;
  window.sampleValidationWorksheetRunMatchesSample = sampleValidationWorksheetRunMatchesSample;
  window.sampleValidationWorksheetSummaryLines = sampleValidationWorksheetSummaryLines;
  window.sampleValidationWorksheetDetailLines = sampleValidationWorksheetDetailLines;
  window.sampleValidationRecordRows = sampleValidationRecordRows;
  window.sampleValidationReconciliationRows = sampleValidationReconciliationRows;
  window.sampleValidationReconciliationForRecord = sampleValidationReconciliationForRecord;
  window.sampleValidationRecordMatchesSample = sampleValidationRecordMatchesSample;
  window.sampleValidationRecordComparisonRowsForPaths = sampleValidationRecordComparisonRowsForPaths;
  window.sampleValidationRecordsMatchingSample = sampleValidationRecordsMatchingSample;
  window.sampleValidationRecordLines = sampleValidationRecordLines;
  window.sampleValidationCompletedPolicyReconciliationRow = sampleValidationCompletedPolicyReconciliationRow;
  window.sampleValidationCompletedPolicyReconciliationStatus = sampleValidationCompletedPolicyReconciliationStatus;
  window.sampleValidationCompletedPacketMarkdownLines = sampleValidationCompletedPacketMarkdownLines;
  window.sampleValidationShellSurface = sampleValidationShellSurface;
  window.initSampleValidationViewEvents = initSampleValidationViewEvents;
})();
