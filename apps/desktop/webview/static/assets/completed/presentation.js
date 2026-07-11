(function () {
  /**
   * Projects Completed state into trust, active-output, and evidence-copy presentation.
   * State is injected from the façade; no backend command or publish authority exists here.
   */
  function createCompletedPresentation(deps) {
    const {
      byId, setText, completedReviewRowReasons, completedCurrentRows, completedMissingRows,
      completedPlacementCounts, completedReviewRows, completedFilterVisibilityLines,
      getSelectedCompletedRow, completedSelectedAtAGlanceState, completedOutputPlacement,
      completedSelectedAtAGlanceStatus, renderCompletedRows, renderCompletedDetail,
      renderPublishReconciliation, renderCompletedReconciliationHint, resetCompletedFilters,
      completedMetricCounts, mergeFinalLibraryPromotionRows, renderCompletedRepairControls,
      renderCompletedRepairHistory, completedEmptyStateMessage, completedFreshnessLine,
      completedFormatCounts, renderCompletedInventoryProgress, renderCompletedIntegrity,
      renderCompletedBreakdown, renderCompletedRuntime, renderCompletedConsistency,
      renderCompletedValidation, renderCompletedWorkflow, renderCompletedReviewBoard,
      renderCompletedReviewDigest, renderCompletedPendingProof, renderCompletedSizeReview,
      renderCompletedSizeEvidence, renderCompletedOutputAcceptance, renderCompletedRouteAgreement,
      renderCompletedRealMediaProof, renderCompletedFinalTrust, renderCompletedPilotEvidencePacket,
      renderCompletedOpenHistory, COMPLETED_READ_ONLY_BOUNDARY,
    } = deps;
    const getCommandHistory = deps.getCommandHistory || function () { return []; };
    const completedDisplayRowStatus = deps.completedDisplayRowStatus || window.completedDisplayRowStatus || function () { return ""; };
    const getState = deps.getState || function () { return {}; };
    const setState = deps.setState || function () {};
    const state = new Proxy({}, {
      get(_target, key) { return getState()[key]; },
      set(_target, key, value) { setState(key, value); return true; },
    });
  function completedTrustDecisionState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("trust")) return "ok";
    if (normalized.includes("investigate")) return "blocked";
    if (normalized.includes("incomplete")) return "validation-needed";
    if (normalized.includes("review")) return "warning";
    return "unknown";
  }

  function completedTrustDecisionRowIdentity(row) {
    return String(row?.row_key || row?.output_path || row?.source_path || row?.output_file || "").trim().toLowerCase();
  }

  function completedTrustDecisionHiddenReviewCount(currentRows, visibleRows) {
    const visible = new Set((Array.isArray(visibleRows) ? visibleRows : []).map(completedTrustDecisionRowIdentity).filter(Boolean));
    return (Array.isArray(currentRows) ? currentRows : []).filter((row) => {
      const identity = completedTrustDecisionRowIdentity(row);
      if (identity && visible.has(identity)) return false;
      const status = String(completedDisplayRowStatus(row) || "").toLowerCase();
      const reasons = completedReviewRowReasons(row);
      return ["blocked", "warning", "failed", "validation-needed"].includes(status)
        || (Array.isArray(reasons) && reasons.length);
    }).length;
  }

  function completedPublishReconciliationPayloadLoaded(payload = state.lastPublishReconciliationPayload) {
    const data = payload && typeof payload === "object" ? payload : {};
    const status = String(data.status || "").trim().toLowerCase();
    if (data.stale) return false;
    if (["not_loaded", "loading", "error", "stale"].includes(status)) return false;
    return Boolean(status) || Array.isArray(data.rows);
  }

  function completedPublishReconciliationStateLabel(payload = state.lastPublishReconciliationPayload) {
    const data = payload && typeof payload === "object" ? payload : {};
    if (data.stale) return "stale";
    const status = String(data.status || "").trim();
    if (status === "not_loaded") return "not loaded";
    return status || (Array.isArray(data.rows) ? "loaded" : "not loaded");
  }

  function completedTrustDecisionReconciliationLoaded() {
    return completedPublishReconciliationPayloadLoaded(state.lastPublishReconciliationPayload);
  }

  function renderCompletedTrustDecision({
    payload = state.lastCompletedPayload,
    allRows = state.lastCompletedRows,
    currentRows = completedCurrentRows(allRows),
    visibleRows = currentRows,
    proofRows = state.lastCompletedPendingProofRows,
  } = {}) {
    const rowList = Array.isArray(allRows) ? allRows : [];
    const currentList = Array.isArray(currentRows) ? currentRows : [];
    const visibleList = Array.isArray(visibleRows) ? visibleRows : [];
    const proofList = Array.isArray(proofRows) ? proofRows : [];
    const missingRows = completedMissingRows(rowList);
    const missingList = Array.isArray(missingRows) ? missingRows : [];
    const placementCounts = completedPlacementCounts(rowList, proofList) || {};
    const currentReview = completedReviewRows(payload || {}, currentList);
    const currentReviewCount = Array.isArray(currentReview) ? currentReview.length : 0;
    const hiddenReviewCount = completedTrustDecisionHiddenReviewCount(currentList, visibleList);
    const reconciliationLoaded = completedTrustDecisionReconciliationLoaded();
    const pendingProofLoaded = Boolean(proofList.length || Object.keys(state.lastCompletedPendingPayload || {}).length);
    const missingNoProof = Number(placementCounts.missing_no_proof || 0);
    const movedUnknown = Number(placementCounts.moved_offline_unknown || 0);
    const pendingProofMissing = Number(placementCounts.missing_pending_proof || 0);
    const drainProofMissing = Number(placementCounts.missing_drain_proof || 0);
    const incompleteReasons = [];
    if (!rowList.length) incompleteReasons.push("no completed history rows loaded");
    if (!pendingProofLoaded) incompleteReasons.push("pending/drain proof not loaded");
    if (!reconciliationLoaded) incompleteReasons.push(`publish reconciliation ${completedPublishReconciliationStateLabel(state.lastPublishReconciliationPayload)}`);
    let status = "Trust ready";
    if (payload?.error || missingNoProof || movedUnknown) {
      status = "Investigate";
    } else if (currentReviewCount || hiddenReviewCount || pendingProofMissing || drainProofMissing || !reconciliationLoaded) {
      status = "Review first";
    } else if (incompleteReasons.length) {
      status = "Evidence incomplete";
    }
    const statusNode = byId("completed-trust-decision-status");
    setText("completed-trust-decision-status", status);
    if (statusNode) statusNode.dataset.state = completedTrustDecisionState(status);
    const chipContainer = byId("completed-trust-decision-chips");
    if (chipContainer && window.mediaPipelineDom?.makeStatusChip) {
      chipContainer.replaceChildren(
        window.mediaPipelineDom.makeStatusChip(`Trust ready${status === "Trust ready" ? "" : ` ${Math.max(currentList.length - currentReviewCount, 0)}`}`, status === "Trust ready" ? "ok" : "normal"),
        window.mediaPipelineDom.makeStatusChip(`Review first ${currentReviewCount + hiddenReviewCount + pendingProofMissing + drainProofMissing}`, status === "Review first" ? "warning" : "normal"),
        window.mediaPipelineDom.makeStatusChip(`Investigate ${missingNoProof + movedUnknown + (payload?.error ? 1 : 0)}`, status === "Investigate" ? "blocked" : "normal"),
        window.mediaPipelineDom.makeStatusChip(`Evidence incomplete ${incompleteReasons.length}`, status === "Evidence incomplete" ? "validation-needed" : "normal"),
      );
    }
    const lines = [
      "Output trust decision:",
      `Operator outcome: ${status}.`,
      `Current outputs present: ${currentList.length}; visible after filters: ${visibleList.length}.`,
      `Current rows needing review: ${currentReviewCount}; hidden review rows: ${hiddenReviewCount}.`,
      `Historical missing outputs: ${missingList.length}.`,
      `Placement evidence: Current=${placementCounts.current || 0}; Missing: pending proof=${pendingProofMissing}; Missing: drain proof=${drainProofMissing}; Missing: no proof=${missingNoProof}; Moved/offline unknown=${movedUnknown}.`,
      `Pending/drain proof: ${pendingProofLoaded ? "loaded or locally derived" : "not loaded"}.`,
      `Backend publish reconciliation: ${completedPublishReconciliationStateLabel(state.lastPublishReconciliationPayload)}.`,
    ];
    if (incompleteReasons.length) lines.push(`Evidence gaps: ${incompleteReasons.join("; ")}.`);
    if (status === "Investigate") {
      lines.push("First action: inspect missing/no-proof outputs in Completed History, Pending Publish, Diagnostics, Run Logs, and Last Stderr before rerun, cleanup, deletion, or manual movement.");
    } else if (status === "Review first") {
      lines.push("First action: read review rows and refresh backend reconciliation before trusting, rerunning, draining, or promoting output.");
    } else if (status === "Evidence incomplete") {
      lines.push("First action: load Completed, Pending Publish, and backend reconciliation evidence before making a trust decision.");
    } else {
      lines.push("First action: output appears trust-ready in the loaded evidence; acceptance remains an operator judgment and backend state remains authoritative.");
    }
    lines.push(COMPLETED_READ_ONLY_BOUNDARY);
    setText("completed-trust-decision-summary", lines.join("\n"));
  }

  function completedActiveOutputTitle(item) {
    if (!item) return "No completed row selected";
    return item.output_file || item.lookup_title || item.output_path || item.source_path || "(unnamed completed row)";
  }

  function completedActiveOutputPathsLine(item) {
    if (!item) return "Select a row to keep its output context visible across Completed subtabs.";
    return [
      item.output_path ? `Output: ${item.output_path}` : "Output: not reported",
      item.source_path ? `Source: ${item.source_path}` : "Source: not reported",
    ].join(" | ");
  }

  function completedRowIsRenderedInTable(rowKey, tableSelector) {
    if (!rowKey) return false;
    return Array.from(document.querySelectorAll(`${tableSelector} tr[data-row-key]`)).some((row) => String(row.dataset.rowKey || "") === rowKey);
  }

  function completedActiveOutputVisibility(item) {
    if (!item) return { label: "not evaluated", hidden: false };
    const lines = typeof completedFilterVisibilityLines === "function" ? completedFilterVisibilityLines(item) : [];
    const visibilityLine = lines.find((line) => /^Selected row visible in table:/.test(String(line || ""))) || "";
    const hiddenLine = lines.find((line) => /^Hidden by current filters:/.test(String(line || ""))) || "";
    const activeLine = lines.find((line) => /^Active filters:/.test(String(line || ""))) || "";
    const rowKey = String(item.row_key || "");
    const inCurrentTable = completedRowIsRenderedInTable(rowKey, "#completed-rows");
    const inHistoryTable = completedRowIsRenderedInTable(rowKey, "#completed-history-rows");
    if (inCurrentTable || inHistoryTable) {
      if (hiddenLine) {
        const renderedLabel = inCurrentTable ? "visible in rendered current table" : "visible in rendered history table";
        return { label: activeLine ? `${renderedLabel}. ${hiddenLine} ${activeLine}` : `${renderedLabel}. ${hiddenLine}`, hidden: true };
      }
      return { label: activeLine ? `${visibilityLine || "Selected row visible in table: yes"} ${activeLine}` : "visible in rendered table", hidden: false };
    }
    if (hiddenLine) {
      return { label: activeLine ? `${hiddenLine} ${activeLine}` : hiddenLine, hidden: true };
    }
    if (String(visibilityLine).toLowerCase().includes("yes")) {
      return {
        label: "visible after filters but outside the first rendered rows; Show Selected pins it into the displayed table window",
        hidden: true,
      };
    }
    return {
      label: hiddenLine || visibilityLine || "not visible in the rendered table",
      hidden: true,
    };
  }

  function renderCompletedActiveOutputContext(item = getSelectedCompletedRow()) {
    const context = byId("completed-active-output-context");
    if (!context) return;
    const selected = item || null;
    const state = selected && typeof completedSelectedAtAGlanceState === "function"
      ? completedSelectedAtAGlanceState(selected)
      : "unknown";
    const placement = selected && typeof completedOutputPlacement === "function"
      ? completedOutputPlacement(selected, state.lastCompletedPendingProofRows)
      : { label: "not checked", state: "unknown" };
    const visibility = completedActiveOutputVisibility(selected);
    context.dataset.state = state || "unknown";
    setText("completed-active-output-title", completedActiveOutputTitle(selected));
    setText("completed-active-output-paths", completedActiveOutputPathsLine(selected));
    setText("completed-active-output-trust", selected && typeof completedSelectedAtAGlanceStatus === "function"
      ? `${completedSelectedAtAGlanceStatus(selected)} / ${selected.operator_trust_state || selected.output_health || "local proof"}`
      : "not selected");
    setText("completed-active-output-placement", placement.label || "not checked");
    setText("completed-active-output-visibility", visibility.label || "not evaluated");
    const button = byId("completed-show-selected-button");
    if (button) {
      button.disabled = !selected;
      button.title = selected
        ? "Clear Completed display filters and pin the selected row into the rendered table window without backend mutation."
        : "Select a completed row first.";
    }
  }

  function showSelectedCompletedRow() {
    const item = getSelectedCompletedRow();
    if (!item) {
      setText("completed-open-status", "Select a completed row before using Show Selected.");
      renderCompletedActiveOutputContext(null);
      return;
    }
    ["completed-filter", "completed-history-filter"].forEach((id) => {
      const node = byId(id);
      if (node) node.value = "";
    });
    ["completed-status-filter", "completed-library-filter", "completed-investigation-filter", "completed-history-status-filter", "completed-history-investigation-filter"].forEach((id) => {
      const node = byId(id);
      if (node) node.value = "all";
    });
    state.selectedCompletedRowKey = item.row_key || state.selectedCompletedRowKey;
    renderCompletedRows();
    renderCompletedDetail(item);
    const rowKey = String(item.row_key || "");
    const renderedRow = Array.from(document.querySelectorAll("#completed-rows tr[data-row-key], #completed-history-rows tr[data-row-key]"))
      .find((row) => String(row.dataset.rowKey || "") === rowKey);
    if (renderedRow && typeof renderedRow.focus === "function") {
      renderedRow.focus({ preventScroll: true });
    }
    setText("completed-open-status", "Selected completed row shown locally. Filters were cleared; backend manifest, promotion, rerun, cleanup, and reconcile scopes are unchanged.");
    renderCompletedActiveOutputContext(item);
  }

  function completedEvidencePacketAvailable() {
    const text = completedEvidencePacketText();
    return Boolean(text && text !== "No copyable pilot evidence packet loaded.");
  }

  function renderCompletedEvidenceCopyState(message = "") {
    const available = completedEvidencePacketAvailable();
    const button = byId("completed-copy-evidence-button");
    const status = byId("completed-copy-evidence-status");
    if (button) {
      button.disabled = !available;
      button.title = available
        ? "Copy the rendered evidence packet text. This does not append evidence or mutate media."
        : "No copyable evidence packet is available for the selected output.";
    }
    if (status) {
      status.dataset.state = available ? "ready" : "blocked";
      if (message) {
        status.textContent = message;
      } else if (!available) {
        status.textContent = "No evidence packet text is available to copy.";
      } else if (!String(status.textContent || "").trim() || String(status.textContent || "").includes("No evidence packet")) {
        status.textContent = "Evidence packet text is ready to copy. Copy does not append evidence, publish, drain, rerun, rename, or touch media.";
      }
    }
  }

  function markPublishReconciliationStale(reason = "Completed output status was refreshed after the last backend reconciliation snapshot.") {
    const previous = state.lastPublishReconciliationPayload && typeof state.lastPublishReconciliationPayload === "object"
      ? state.lastPublishReconciliationPayload
      : {};
    const hadPrevious = Boolean(previous.status || Array.isArray(previous.rows));
    state.lastPublishReconciliationPayload = hadPrevious
      ? {
        ...previous,
        status: "stale",
        stale: true,
        stale_reason: reason,
        summary_lines: [
          `Backend publish reconciliation is stale: ${reason}`,
          "Use Refresh Backend Reconciliation for a current backend-owned Completed/Pending/drain-summary proof snapshot.",
        ],
      }
      : {
        status: "not_loaded",
        stale: false,
        rows: [],
        summary_lines: [
          "Backend publish reconciliation has not been loaded for this Completed snapshot.",
          "Use Refresh Backend Reconciliation for a backend-owned Completed/Pending/drain-summary proof snapshot.",
        ],
      };
    state.selectedPublishReconciliationKey = "";
    renderPublishReconciliation(state.lastPublishReconciliationPayload);
    renderCompletedTrustDecision();
    renderCompletedReconciliationHint(state.lastCompletedPayload, state.lastCompletedRows);
  }

  function focusCompletedQuickLinkTarget(selector) {
    const target = selector ? document.querySelector(selector) : null;
    if (!target) return false;
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    if (!target.matches?.("a[href], button, input, select, textarea, summary, [tabindex]")) {
      target.setAttribute("tabindex", "-1");
    }
    target.focus?.({ preventScroll: true });
    return true;
  }

  function setCompletedCurrentFilters({ text = "", status = "all", library = "all", investigation = "all" } = {}) {
    const filter = byId("completed-filter");
    const statusFilter = byId("completed-status-filter");
    const libraryFilter = byId("completed-library-filter");
    const investigationFilter = byId("completed-investigation-filter");
    if (filter) filter.value = text;
    if (statusFilter) statusFilter.value = status;
    if (libraryFilter) libraryFilter.value = library;
    if (investigationFilter) investigationFilter.value = investigation;
    renderCompletedRows();
  }

  function activateQuickLink(action) {
    const normalized = String(action || "").trim().toLowerCase();
    if (normalized === "clear") {
      resetCompletedFilters();
      return focusCompletedQuickLinkTarget("#completed-rows");
    }
    if (normalized === "encode") {
      setCompletedCurrentFilters({ investigation: "encode" });
      return focusCompletedQuickLinkTarget("#completed-rows");
    }
    if (normalized === "remux") {
      setCompletedCurrentFilters({ investigation: "remux" });
      return focusCompletedQuickLinkTarget("#completed-rows");
    }
    if (normalized === "missing") {
      setCompletedCurrentFilters({ text: "missing", status: "review" });
      return focusCompletedQuickLinkTarget("#completed-rows");
    }
    if (normalized === "review") {
      setCompletedCurrentFilters({ status: "review" });
      return focusCompletedQuickLinkTarget("#completed-rows");
    }
    if (normalized === "present") {
      setCompletedCurrentFilters({ status: "ready" });
      return focusCompletedQuickLinkTarget("#completed-rows");
    }
    if (normalized === "filters") {
      return focusCompletedQuickLinkTarget("#completed-filter");
    }
    return true;
  }

  function renderCompleted(completed = {}) {
    const payload = completed && typeof completed === "object" ? completed : {};
    let rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (payload.final_library_promotion && typeof payload.final_library_promotion === "object") {
      state.lastFinalLibraryPromotionStatus = payload.final_library_promotion;
      const mergedRows = mergeFinalLibraryPromotionRows(rows, payload.final_library_promotion);
      rows = Array.isArray(mergedRows) ? mergedRows : rows;
    }
    const currentRowsResult = completedCurrentRows(rows);
    const currentRows = Array.isArray(currentRowsResult) ? currentRowsResult : [];
    const metricCountsResult = completedMetricCounts(rows);
    const metricCounts = metricCountsResult && typeof metricCountsResult === "object"
      ? metricCountsResult
      : { current: rows.length, encoded: 0, remuxed: 0, missing: 0 };
    const commandEntries = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    state.lastCompletedPayload = payload;
    state.lastCompletedRows = rows;
    state.lastCompletedEmptyMessage = completedEmptyStateMessage(payload, rows);
    if (state.selectedCompletedRowKey && !rows.some((row) => row?.row_key === state.selectedCompletedRowKey)) {
      state.selectedCompletedRowKey = "";
    }
    if (!state.selectedCompletedRowKey && rows.length) {
      state.selectedCompletedRowKey = rows[0]?.row_key || "";
    }
    renderCompletedRepairControls();
    if (typeof getCommandHistory === "function") renderCompletedRepairHistory(getCommandHistory());
    setText("completed-count", String(metricCounts.current));
    setText("completed-encode-count", String(metricCounts.encoded));
    setText("completed-remux-count", String(metricCounts.remuxed));
    setText("completed-missing-count", String(metricCounts.missing));
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload,
        label: "Output",
        rowCount: payload.count || rows.length || 0,
        sourceLine: payload.source || payload.manifest_path ? `Manifest: ${payload.source || payload.manifest_path}` : "",
        artifactLine: completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc),
        readError: payload.manifest_error || payload.error || "",
        refreshAction: "Use Refresh Current Output Status to reread completed history and recheck destination file existence without accepting, deleting, or moving outputs.",
      })
      : [];
    const currentReviewCount = completedReviewRows(payload, currentRows).length;
    const summary = [
      ...freshnessLines,
      freshnessLines.length ? "" : (payload.source || payload.manifest_path ? `Manifest: ${payload.source || payload.manifest_path}` : ""),
      freshnessLines.length ? "" : completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc),
      `Completed history rows: ${payload.count || rows.length || 0}`,
      `Current outputs present: ${metricCounts.current}`,
      `Current encode/remux: ${metricCounts.encoded} / ${metricCounts.remuxed}`,
      `Historical outputs missing from expected destination: ${metricCounts.missing}`,
      `Rows needing review: ${completedReviewRows(payload, rows).length}`,
      `Rows over +5% output growth: ${payload.size_growth_over_5_count || 0}`,
      payload.operator_status_counts ? `Operator statuses: ${completedFormatCounts(payload.operator_status_counts)}` : "",
      payload.operator_severity_counts ? `Operator severities: ${completedFormatCounts(payload.operator_severity_counts)}` : "",
      payload.operator_trust_state_counts ? `Backend trust states: ${completedFormatCounts(payload.operator_trust_state_counts)}` : "",
      payload.available_open_target_counts ? `Backend open targets from available_open_target_counts: ${completedFormatCounts(payload.available_open_target_counts)}` : "",
      payload.total_output_size_text ? `Loaded output size: ${payload.total_output_size_text}` : "",
      ...warnings,
      !rows.length ? state.lastCompletedEmptyMessage : "",
    ].filter(Boolean);
    setText("completed-summary", summary.join("\n") || payload.error || "No completed history issues loaded.");
    setText("completed-current-summary", [
      `Current outputs present at expected destination: ${metricCounts.current}`,
      `Current encoded/remuxed: ${metricCounts.encoded} / ${metricCounts.remuxed}`,
      `Current rows needing review: ${currentReviewCount}`,
      `Completed history rows not currently present: ${metricCounts.missing}`,
      "Current table rule: a row appears here once per expected output path when the completed output is still present at that destination.",
      "Refresh Current Output Status rereads the completed manifest and rechecks output existence; it does not accept, delete, rerun, drain, publish, or move media.",
    ].join("\n"));
    renderCompletedReconciliationHint(payload, rows);
    renderCompletedInventoryProgress(payload);
    renderCompletedIntegrity(payload, rows);
    renderCompletedBreakdown(payload, rows);
    renderCompletedRuntime(payload, rows);
    renderCompletedConsistency(payload, rows);
    renderCompletedValidation(payload, rows);
    renderCompletedWorkflow(payload, rows);
    renderCompletedReviewBoard(payload, rows);
    renderCompletedReviewDigest(payload, rows);
    renderCompletedPendingProof(payload, rows, state.lastCompletedPendingPayload);
    renderCompletedSizeReview(payload, rows);
    renderCompletedSizeEvidence(payload, rows, state.lastCompletedPendingProofRows);
    renderCompletedOutputAcceptance(payload, rows, state.lastCompletedPendingProofRows, commandEntries);
    renderCompletedRouteAgreement(
      payload,
      rows,
      typeof window.getLastQueuePayload === "function" ? window.getLastQueuePayload() : {},
      typeof window.getLastQueueRows === "function" ? window.getLastQueueRows() : []
    );
    renderCompletedRealMediaProof(payload, rows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload, commandEntries);
    renderCompletedFinalTrust(payload, rows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload, commandEntries);
    renderCompletedPilotEvidencePacket(payload, rows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload, commandEntries);
    renderCompletedEvidenceCopyState();
    renderPublishReconciliation(state.lastPublishReconciliationPayload);
    renderCompletedDetail(getSelectedCompletedRow());
    renderCompletedActiveOutputContext(getSelectedCompletedRow());
    renderCompletedRows();
    renderCompletedOpenHistory(commandEntries);
  }

  function completedEvidencePacketText() {
    const node = byId("completed-pilot-evidence-markdown");
    return node ? String(node.textContent || "").trim() : "";
  }

  async function copyCompletedEvidencePacket() {
    const text = completedEvidencePacketText();
    if (!text || text === "No copyable pilot evidence packet loaded.") {
      renderCompletedEvidenceCopyState("No evidence packet text is available to copy.");
      return false;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "readonly");
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textarea);
        if (!copied) throw new Error("clipboard command returned false");
      }
      renderCompletedEvidenceCopyState("Copied evidence packet. This did not append evidence, save settings, publish, drain, rerun, rename, or touch media.");
      return true;
    } catch (error) {
      const message = error?.message || String(error);
      renderCompletedEvidenceCopyState(`Copy failed: ${message}. Select the packet text manually if needed.`);
      return false;
    }
  }
    return {
      completedTrustDecisionState, completedTrustDecisionRowIdentity, completedTrustDecisionHiddenReviewCount,
      completedPublishReconciliationPayloadLoaded, completedPublishReconciliationStateLabel,
      completedTrustDecisionReconciliationLoaded, renderCompletedTrustDecision,
      completedActiveOutputTitle, completedActiveOutputPathsLine, completedActiveOutputVisibility,
      renderCompletedActiveOutputContext, showSelectedCompletedRow, completedEvidencePacketAvailable,
      renderCompletedEvidenceCopyState, markPublishReconciliationStale, focusCompletedQuickLinkTarget,
      setCompletedCurrentFilters, activateQuickLink, renderCompleted, completedEvidencePacketText,
      copyCompletedEvidencePacket,
    };
  }
  window.__completedPresentationModule = createCompletedPresentation;
})();
