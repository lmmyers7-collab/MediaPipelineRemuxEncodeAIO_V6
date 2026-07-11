/* Pending Publish table selection, action-center projection, filters, and event binding. */
(function () {
  function createPendingPublishActionCenterModule(deps = {}) {
    const {
      byId, clearRows, appendCells, setCellStatusChip, makeRowSelectable, updateTableStatusLegend,
      filterRows, filterRowsByStatus, filterRowsByInvestigation, filterResultSummaryLines,
      tableScrollSnapshot, deferTableScrollRestore, pendingFilterFields, readOnlyBoundary,
      getLastPendingEmptyMessage,
      setText,
      shortenPath,
      getLastPendingPayload,
      getLastPendingRows,
      getLastPendingSnapshot,
      getSelectedPendingRowKey,
      setSelectedPendingRowKey,
      pendingTableRowStatus,
      pendingEvidenceClass,
      pendingDrainSummaryPayload,
      pendingDrainSummaryItems,
      pendingDrainDecisionStatus,
      pendingValidationStatus,
      pendingCurrentFilterScope,
      pendingDrainGuardState,
      pendingInvestigationFilterLabel,
      pendingMatchesInvestigationFilter,
      renderPendingDetail,
      renderPendingReviewDigest,
      renderPendingDrainEvidence,
      renderPendingBackendDrainScopePreview,
      renderPendingDrainDecisionChecklist,
      renderPendingDrainActionConfidence,
      renderPendingDrainGuard,

      renderPendingRepairManifestControls,
      renderPendingRepairOrphanControls,
      getCommandHistory,
    } = deps;
    let eventsInitialized = false;
function pendingListText(value) {
    return Array.isArray(value) && value.length ? value.join(", ") : "none";
  }

  function pendingRowKey(item) {
    if (item?.row_key) return String(item.row_key).toLocaleLowerCase();
    return [
      item?.manifest_path || "",
      item?.local_file || "",
      item?.server_out || "",
      item?.state || "",
    ].join("\u001f").toLocaleLowerCase();
  }

  function getSelectedPendingRow() {
    const selectedKey = getSelectedPendingRowKey();
    if (!selectedKey) return null;
    return getLastPendingRows().find((row) => pendingRowKey(row) === selectedKey) || null;
  }

  function capturePendingSelectionScroll() {
    return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
  }

  function restorePendingSelectionScroll(snapshot) {
    if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
  }

  function selectPendingRow(item) {
    const scrollSnapshot = capturePendingSelectionScroll();
    setSelectedPendingRowKey(pendingRowKey(item));
    renderPendingDetail(item || null);
    renderPendingReviewDigest(getLastPendingPayload(), getLastPendingRows());
    renderPendingDrainEvidence(getLastPendingPayload(), getLastPendingRows());
    renderPendingBackendDrainScopePreview(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingRows();
    renderPendingRepairManifestControls();
    renderPendingRepairOrphanControls();
    restorePendingSelectionScroll(scrollSnapshot);
  }

  function pendingDrainOverviewState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("do not") || normalized.includes("blocked")) return "blocked";
    if (normalized.includes("incomplete") || normalized.includes("not evaluated")) return "validation-needed";
    if (normalized.includes("review")) return "warning";
    if (normalized.includes("ready")) return "ok";
    return "unknown";
  }

  function pendingRowPresentationStatus(item) {
    const tableStatus = pendingTableRowStatus(item);
    const evidenceClass = pendingEvidenceClass(item);
    const severity = String(item?.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item?.drain_recommendation || "").toLowerCase();
    if (["completed", "skipped", "running", "publishing", "queued"].includes(tableStatus)) return tableStatus;
    if (tableStatus === "failed" || severity === "error" || item?.error) return "failed";
    if (
      tableStatus === "blocked"
      || recommendation === "do_not_drain"
      || ["do-not-drain", "diagnostic-error", "manifest-invalid", "missing-payload"].includes(evidenceClass)
    ) {
      return "blocked";
    }
    if (["missing-sidecar", "orphan-payload"].includes(evidenceClass)) return "validation-needed";
    if (tableStatus === "warning" || evidenceClass === "review" || item?.ready_to_drain === false) return "warning";
    if (["ready", "match"].includes(tableStatus) || item?.ready_to_drain === true || evidenceClass === "ready-evidence") return "ready";
    return tableStatus || "unknown";
  }

  function pendingRowPresentationLabel(item) {
    const status = pendingRowPresentationStatus(item);
    if (status === "completed") return "Drained";
    if (["running", "publishing", "queued"].includes(status)) return "Draining";
    if (status === "skipped") return "Skipped";
    if (status === "failed") return "Failed";
    if (status === "blocked") return "Blocked";
    if (status === "validation-needed") return "Evidence missing";
    if (status === "warning") return "Needs review";
    if (["ready", "match"].includes(status)) return "Ready";
    if (status === "unavailable") return "Unavailable";
    if (status === "empty") return "No row";
    return "Unknown";
  }

  function pendingRowReasonText(item) {
    const candidates = [
      item?.issue_summary,
      item?.primary_concern,
      item?.error,
      item?.operator_guidance,
      item?.safe_next_action,
      item?.drain_recommendation,
      item?.diagnostic_status,
    ];
    const reason = candidates.map((value) => String(value || "").trim()).find(Boolean);
    if (reason) return reason;
    if (item?.ready_to_drain === true) return "No focused blocker in the loaded backend scan.";
    return "";
  }

  function pendingRowUpdatedText(item) {
    return String(
      item?.updated_at
      || item?.modified_at
      || item?.last_seen_at
      || item?.parked_at_display
      || item?.parked_at
      || item?.age_text
      || ""
    );
  }

  function pendingPathDisplay(path, limit = 44) {
    const value = String(path || "");
    return typeof shortenPath === "function" ? shortenPath(value, limit) : value;
  }

  function pendingDrainSummaryCounts(payload) {
    const summary = pendingDrainSummaryPayload(payload || {});
    const items = pendingDrainSummaryItems(summary);
    const counts = {
      drained: Number(summary.succeeded_count || 0) + Number(summary.already_published_count || 0),
      failed: Number(summary.error_count || 0),
      skipped: Number(summary.skipped_count || 0),
    };
    if (!items.length) return counts;
    const itemCounts = items.reduce((acc, item) => {
      const status = String(item?.status || item?.result || "").trim().toLowerCase();
      if (["succeeded", "success", "already_published", "published", "completed"].includes(status)) acc.drained += 1;
      else if (["skipped", "deferred"].includes(status)) acc.skipped += 1;
      else if (status || item?.error) acc.failed += 1;
      return acc;
    }, { drained: 0, failed: 0, skipped: 0 });
function renderPendingRows() {
    const filterText = byId("pending-filter")?.value || "";
    const statusFilter = byId("pending-status-filter")?.value || "all";
    const investigationFilter = byId("pending-investigation-filter")?.value || "all";
    const textRows = filterRows(getLastPendingRows(), filterText, pendingFilterFields);
    const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, pendingRowPresentationStatus) : textRows;
    const rows = typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, pendingMatchesInvestigationFilter) : statusRows;
    const renderLimit = 250;
    const renderedCount = Math.min(rows.length, renderLimit);
    setText(
      "pending-status",
      rows.length > renderLimit
        ? `${renderedCount} shown / ${rows.length} filtered / ${getLastPendingRows().length} rows`
        : `${rows.length} / ${getLastPendingRows().length} row${getLastPendingRows().length === 1 ? "" : "s"}`
    );
    if (typeof filterResultSummaryLines === "function") {
      setText("pending-filter-summary", filterResultSummaryLines({
        label: "Pending publish filter",
        allRows: getLastPendingRows(),
        visibleRows: rows,
        filterText,
        statusFilter,
        investigationFilter,
        investigationLabel: pendingInvestigationFilterLabel(investigationFilter),
        statusOf: pendingRowPresentationStatus,
        limit: 250,
        decisionName: "publish/drain",
        guardrail: readOnlyBoundary,
      }).join("\n"));
    }
    const tbody = byId("pending-rows");
    const scrollSnapshot = tableScrollSnapshot(tbody);
    if (!rows.length) {
      clearRows(tbody, 7, getLastPendingRows().length ? "No pending publish rows match the filter." : getLastPendingEmptyMessage());
      updateTableStatusLegend("pending-table-legend", tbody, "Pending publish rows");
      if (getSelectedPendingRowKey()) renderPendingDetail(getSelectedPendingRow());
      renderPendingDrainActionConfidence(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingBackendDrainScopePreview(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainOverview(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingRepairManifestControls();
      renderPendingRepairOrphanControls();
      deferTableScrollRestore(scrollSnapshot);
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, renderLimit).forEach((item) => {
      const row = document.createElement("tr");
      const key = pendingRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = pendingRowPresentationStatus(item);
      const localFileDisplay = pendingPathDisplay(item.local_file || item.source_path || "", 42);
      const manifestDisplay = pendingPathDisplay(item.manifest_path || item.row_key || "", 34);
      const serverOutDisplay = pendingPathDisplay(item.server_out || "", 42);
      const statusText = pendingRowPresentationLabel(item);
      appendCells(row, [
        statusText,
        localFileDisplay,
        manifestDisplay,
        serverOutDisplay,
        item.size_text || "",
        pendingRowUpdatedText(item),
        pendingRowReasonText(item),
      ], [null, "path-cell", "path-cell", "path-cell", "num", null, null]);
      const pendingCells = row.querySelectorAll("td");
      const stateCell = pendingCells[0] || row.children?.[0];
      if (typeof setCellStatusChip === "function") setCellStatusChip(stateCell, statusText, row.dataset.status);
      if (pendingCells[1] && (item.local_file || item.source_path)) pendingCells[1].title = item.local_file || item.source_path;
      if (pendingCells[2] && item.manifest_path) pendingCells[2].title = item.manifest_path;
      if (pendingCells[3] && item.server_out) pendingCells[3].title = item.server_out;
      makeRowSelectable(row, () => selectPendingRow(item), {
        selected: Boolean(key && key === getSelectedPendingRowKey()),
        label: `Pending publish row ${item.local_file || item.server_out || item.manifest_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-table-legend", tbody, "Pending publish rows");
    if (getSelectedPendingRowKey()) renderPendingDetail(getSelectedPendingRow());
    renderPendingDrainActionConfidence(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingBackendDrainScopePreview(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainOverview(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingRepairManifestControls();
    renderPendingRepairOrphanControls();
    deferTableScrollRestore(scrollSnapshot);
  }

  function resetPendingFilters() {
    const filter = byId("pending-filter");
    const status = byId("pending-status-filter");
    const investigation = byId("pending-investigation-filter");
    if (filter) filter.value = "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    renderPendingRows();
    setText("pending-open-status", "Pending Publish display filters cleared. Backend drain scope, recovery plans, manifests, and payloads are unchanged.");
  }

    return {
      drained: counts.drained || itemCounts.drained,
      failed: counts.failed || itemCounts.failed,
      skipped: counts.skipped || itemCounts.skipped,
    };
  }

  function pendingActionCenterTriage(rows, payload = getLastPendingPayload()) {
    const rowList = Array.isArray(rows) ? rows : [];
    const counts = rowList.reduce((acc, row) => {
      const status = pendingRowPresentationStatus(row);
      if (status === "completed") {
        acc.drained += 1;
      } else if (status === "skipped") {
        acc.skipped += 1;
      } else if (["running", "publishing", "queued"].includes(status)) {
        acc.draining += 1;
      } else if (status === "failed") {
        acc.failed += 1;
      } else if (status === "blocked") {
        acc.blocked += 1;
      } else if (status === "validation-needed") {
        acc.evidence += 1;
      } else if (["warning", "unknown", "unavailable", "empty"].includes(status)) {
        acc.review += 1;
      } else {
        acc.ready += 1;
      }
      return acc;
    }, { ready: 0, review: 0, evidence: 0, blocked: 0, failed: 0, drained: 0, skipped: 0, draining: 0 });
    const summaryCounts = pendingDrainSummaryCounts(payload || {});
    counts.drained += summaryCounts.drained;
    counts.failed += summaryCounts.failed;
    counts.skipped += summaryCounts.skipped;
    return counts;
  }

  function pendingActionCenterOutcome(payload, rowList, decisionStatus, validationStatus, guard, triage) {
    const rows = Array.isArray(rowList) ? rowList : [];
    const counts = triage || pendingActionCenterTriage(rows, payload);
    const normalizedDecision = String(decisionStatus || "").toLowerCase();
    const warnings = Array.isArray(payload?.warnings) ? payload.warnings.filter(Boolean) : [];
    if (payload?.error) {
      return {
        action: "Open Diagnostics first",
        reason: `Pending Publish scan is unavailable: ${payload.error}`,
        detail: "Do not drain until backend state, Run Logs, and Last Stderr explain the scan failure.",
        state: "blocked",
      };
    }
    if (payload?.exists === false) {
      return {
        action: "No drain needed",
        reason: "No pending-publish folder exists yet.",
        detail: "Check Completed and Run Logs before reprocessing if an expected output is missing.",
        state: "empty",
      };
    }
    if (!rows.length) {
      if (counts.drained) {
        return {
          action: `Review ${counts.drained} drained file${counts.drained === 1 ? "" : "s"}`,
          reason: "No current parked rows are loaded; the latest drain summary has completed evidence.",
          detail: "Compare Last Drain and Completed proof before assuming final placement for a specific title.",
          state: "empty",
        };
      }
      return {
        action: "No parked outputs",
        reason: "Pending Publish has no parked rows loaded.",
        detail: "An empty pending view is not proof of publish; compare Completed and drain-summary evidence when an output is missing.",
        state: "empty",
      };
    }
    if (counts.failed) {
      return {
        action: `Investigate ${counts.failed} failed file${counts.failed === 1 ? "" : "s"}`,
        reason: `${counts.failed} failed drain or row error signal${counts.failed === 1 ? "" : "s"} loaded.`,
        detail: "Open the failed row, Last Drain, Run Logs, and Last Stderr before another drain attempt.",
        state: "blocked",
      };
    }
    if (counts.blocked || normalizedDecision.includes("do not")) {
      return {
        action: "Resolve blockers before drain",
        reason: counts.blocked
          ? `${counts.blocked} blocked row${counts.blocked === 1 ? "" : "s"} or do-not-drain checkpoint found.`
          : "A do-not-drain checkpoint is active in the drain decision checklist.",
        detail: "Show blockers, select the highest-risk row, and inspect backend-selected diagnostics in Advanced before another drain attempt.",
        state: "blocked",
      };
    }
    if (counts.evidence || normalizedDecision.includes("incomplete") || normalizedDecision.includes("not evaluated")) {
      return {
        action: "Review evidence gaps",
        reason: counts.evidence
          ? `${counts.evidence} row${counts.evidence === 1 ? "" : "s"} have payload, sidecar, or parked-output evidence gaps.`
          : "Drain evidence is incomplete or has not been evaluated.",
        detail: "Show evidence gaps, then use Advanced recovery or diagnostics only when the row evidence explains a concrete problem.",
        state: "validation-needed",
      };
    }
    if (counts.review || validationStatus === "Review" || warnings.length || guard?.review_required) {
      return {
        action: "Review before drain",
        reason: counts.review
          ? `${counts.review} row${counts.review === 1 ? "" : "s"} or checklist signal require read-first review.`
          : "The drain guard requires explicit read-first review before submission.",
        detail: "Use the review filter and selected-row detail first; open Advanced diagnostics only when a row needs deeper evidence.",
        state: "warning",
      };
    }
    return {
      action: `Drain ${rows.length} parked file${rows.length === 1 ? "" : "s"}`,
      reason: `${counts.ready} row${counts.ready === 1 ? " has" : "s have"} no focused blocker in the loaded backend scan.`,
      detail: "Submit the backend-owned drain when the current parked rows show no local blockers; the backend still validates the full parked scope.",
      state: "ok",
    };
  }

  function setPendingActionCount(id, count, state, label) {
    const node = byId(id);
    if (!node) return;
    node.textContent = String(count || 0);
    const button = node.closest("button");
    if (button) {
      button.dataset.state = state || "empty";
      button.title = `${label}: ${count || 0}`;
      button.setAttribute("aria-label", `Show ${label.toLowerCase()}: ${count || 0}`);
    }
  }

  function renderPendingActionCenter(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries, overview = {}) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : (typeof getCommandHistory === "function" ? getCommandHistory() : []);
    const decisionStatus = overview.decisionStatus || pendingDrainDecisionStatus(payload, rowList, snapshot || {}, entryList);
    const validationStatus = overview.validationStatus || pendingValidationStatus(payload, rowList);
    const filterScope = overview.filterScope || pendingCurrentFilterScope(rowList);
    const guard = overview.guard || pendingDrainGuardState(payload, rowList, snapshot || {}, entryList);
    const triage = pendingActionCenterTriage(rowList, payload);
    const outcome = pendingActionCenterOutcome(payload, rowList, decisionStatus, validationStatus, guard, triage);
    const state = pendingDrainOverviewState(decisionStatus) === "unknown" ? outcome.state : pendingDrainOverviewState(decisionStatus);

    setText("pending-action-status", decisionStatus || "Not loaded");
    const statusNode = byId("pending-action-status");
    if (statusNode) statusNode.dataset.state = state;
    setText("pending-action-subtitle", `Rows loaded: ${rowList.length}; visible after filters: ${filterScope.visibleCount ?? rowList.length}/${filterScope.totalCount ?? rowList.length}; backend drain scope is not narrowed by display filters.`);
    setText("pending-action-primary", outcome.action);
    setText("pending-action-reason", outcome.reason);
    setPendingActionCount("pending-action-ready-count", triage.ready, triage.ready ? "ok" : "empty", "Ready to drain rows");
    setPendingActionCount("pending-action-review-count", triage.review, triage.review ? "warning" : "empty", "Rows needing review");
    setPendingActionCount("pending-action-evidence-count", triage.evidence, triage.evidence ? "validation-needed" : "empty", "Rows with missing evidence");
    setPendingActionCount("pending-action-blocked-count", triage.blocked, triage.blocked ? "blocked" : "empty", "Blocked rows");
    setPendingActionCount("pending-action-failed-count", triage.failed, triage.failed ? "blocked" : "empty", "Failed rows");
    setPendingActionCount("pending-action-drained-count", triage.drained, triage.drained ? "completed" : "empty", "Drained rows in latest summary");

    const drainButton = byId("pending-action-drain-button");
    if (drainButton) {
      const drainLabel = rowList.length
        ? `Drain ${rowList.length} parked file${rowList.length === 1 ? "" : "s"}`
        : "Drain Parked Outputs";
      drainButton.disabled = !guard?.allowed;
      drainButton.textContent = guard?.allowed
        ? guard.review_required && rowList.length ? `Drain after review (${rowList.length})` : drainLabel
        : "Drain Blocked";
      drainButton.title = guard?.allowed ? guard.confirm_message || outcome.detail : guard?.message || outcome.detail;
      drainButton.dataset.state = guard?.allowed ? guard.review_required ? "warning" : "ok" : "blocked";
    }

    setText("pending-action-detail", [
      "Pending Publish action center:",
      `Next action: ${outcome.action}`,
      `Why: ${outcome.reason}`,
      `Drain decision: ${decisionStatus || "not loaded"}; checklist: ${validationStatus || "not loaded"}; backend button guard: ${guard?.allowed ? guard.review_required ? "review confirmation required" : "allowed" : "blocked"}.`,
      `Triage filters: ready=${triage.ready}; review=${triage.review}; evidence missing=${triage.evidence}; blocked=${triage.blocked}; failed=${triage.failed}; drained summary=${triage.drained}.`,
      `Visible table scope: ${filterScope.visibleCount ?? rowList.length}/${filterScope.totalCount ?? rowList.length}; hidden blocked/review=${filterScope.hiddenBlockedCount || 0}/${filterScope.hiddenReviewCount || 0}.`,
      outcome.detail,
      "Boundary: this action center can only update local filters, refresh backend evidence, or submit the backend-owned drain command.",
    ].join("\n"));
  }

  function renderPendingDrainOverview(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : (typeof getCommandHistory === "function" ? getCommandHistory() : []);
    const decisionStatus = pendingDrainDecisionStatus(payload, rowList, snapshot || {}, entryList);
    const validationStatus = pendingValidationStatus(payload, rowList);
    const filterScope = pendingCurrentFilterScope(rowList);
    const guard = pendingDrainGuardState(payload, rowList, snapshot || {}, entryList);
    const chips = byId("pending-drain-decision-chips");
    if (chips && window.mediaPipelineDom?.makeStatusChip) {
      chips.replaceChildren(
        window.mediaPipelineDom.makeStatusChip("Blocked", decisionStatus === "Do not drain" ? "blocked" : "normal"),
        window.mediaPipelineDom.makeStatusChip("Review", decisionStatus === "Review first" ? "warning" : "normal"),
        window.mediaPipelineDom.makeStatusChip("Need evidence", decisionStatus === "Evidence incomplete" || decisionStatus === "Not evaluated" ? "validation-needed" : "normal"),
        window.mediaPipelineDom.makeStatusChip("Ready", decisionStatus === "Ready-looking" ? "ok" : "normal"),
      );
    }
    setText("pending-drain-overview", [
      "Pending Publish drain decision:",
      `Operator outcome: ${decisionStatus}.`,
      `Publish checklist: ${validationStatus}.`,
      `Rows loaded: ${rowList.length}; visible table scope: ${filterScope.visibleCount ?? rowList.length}/${filterScope.totalCount ?? rowList.length}; hidden blocked=${filterScope.hiddenBlockedCount || 0}; hidden review=${filterScope.hiddenReviewCount || 0}.`,
      `Button guard: ${guard.allowed ? (guard.review_required ? "review confirmation required" : "allowed by local evidence") : "blocked by local evidence"}.`,
      "Command boundary: Drain Parked Outputs remains the backend-owned validation and movement path; this overview cannot move, publish, repair, delete, rewrite, or mark outputs complete.",
    ].join("\n"));
    const overviewNode = byId("pending-drain-overview");
    if (overviewNode) overviewNode.dataset.state = pendingDrainOverviewState(decisionStatus);
    renderPendingActionCenter(payload, rowList, snapshot || {}, entryList, { decisionStatus, validationStatus, filterScope, guard });
  }

  function applyPendingActionFilter(kind) {
    const normalized = String(kind || "all").trim().toLowerCase();
    const filter = byId("pending-filter");
    const status = byId("pending-status-filter");
    const investigation = byId("pending-investigation-filter");
    if (filter) filter.value = "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    if (normalized === "ready") {
      if (status) status.value = "ready";
      if (investigation) investigation.value = "ready_to_drain";
    } else if (normalized === "review") {
      if (status) status.value = "warning";
    } else if (normalized === "evidence") {
      if (investigation) investigation.value = "evidence_missing";
    } else if (normalized === "blocked") {
      if (status) status.value = "blocked";
      if (investigation) investigation.value = "do_not_drain";
    } else if (normalized === "failed") {
      if (status) status.value = "failed";
      if (investigation) investigation.value = "failed";
    } else if (normalized === "drained") {
      if (status) status.value = "completed";
      if (investigation) investigation.value = "drained";
    } else if (normalized === "payloads") {
      if (filter) filter.value = "payload";
    }
    renderPendingRows();
    const labels = {
      ready: "Showing ready-looking pending rows. Backend drain scope is unchanged.",
      review: "Showing pending rows that need review. Backend drain scope is unchanged.",
      evidence: "Showing pending rows with missing payload, sidecar, or manifest evidence. Backend drain scope is unchanged.",
      blocked: "Showing do-not-drain or blocked pending rows. Backend drain scope is unchanged.",
      failed: "Showing failed pending rows and failed latest-summary entries when present. Backend drain scope is unchanged.",
      drained: "Showing rows with drained/completed evidence when present. Current pending rows remain the backend source of truth.",
      payloads: "Showing rows matching payload evidence. Backend drain scope is unchanged.",
    };
    setText("pending-action-feedback", labels[normalized] || "Pending Publish filters cleared. Backend drain scope is unchanged.");
  }

  function triggerPendingActionDrain() {
    const drainButton = byId("pending-drain-button");
    if (!drainButton) {
      setText("pending-action-feedback", "The backend drain button is not available on this page.");
      return;
    }
    if (drainButton.disabled) {
      setText("pending-action-feedback", "Drain is currently busy or unavailable. Wait for the active command to finish, then refresh evidence.");
      return;
    }
    setText("pending-action-feedback", "Opening the existing backend-owned Drain Parked Outputs confirmation.");
    drainButton.click();
  }

  function focusPendingQuickLinkTarget(selector) {
    const target = selector ? document.querySelector(selector) : null;
    if (!target) return false;
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    if (!target.matches?.("a[href], button, input, select, textarea, summary, [tabindex]")) {
      target.setAttribute("tabindex", "-1");
    }
    target.focus?.({ preventScroll: true });
    return true;
  }

  function setPendingTextFilter(text) {
    const filter = byId("pending-filter");
    const status = byId("pending-status-filter");
    const investigation = byId("pending-investigation-filter");
    if (filter) filter.value = text || "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    renderPendingRows();
    setText("pending-action-feedback", `Showing Pending Publish rows matching "${text}". Backend drain scope is unchanged.`);
  }

  function activateQuickLink(action) {
    const normalized = String(action || "").trim().toLowerCase();
    if (normalized === "manifests") {
      setPendingTextFilter("manifest");
      return focusPendingQuickLinkTarget("#pending-rows");
    }
    if (normalized === "payloads") {
      setPendingTextFilter("payload");
      return focusPendingQuickLinkTarget("#pending-rows");
    }
    if (normalized === "review" || normalized === "health") {
      applyPendingActionFilter("review");
      return focusPendingQuickLinkTarget("#pending-rows");
    }
    if (normalized === "summary" || normalized === "size") {
      return focusPendingQuickLinkTarget("#pending-summary");
    }
    if (normalized === "action") {
      return focusPendingQuickLinkTarget(".pending-action-center");
    }
    return true;
  }

  function triggerPendingActionRefresh() {
    const refreshButton = document.querySelector('[data-page-refresh-button="pending"]');
    if (refreshButton && typeof refreshButton.click === "function") {
      setText("pending-action-feedback", "Refreshing backend Pending Publish evidence.");
      refreshButton.click();
      return;
    }
    if (typeof window.refreshAllNow === "function") {
      setText("pending-action-feedback", "Refreshing backend evidence from the app refresh command.");
      window.refreshAllNow();
      return;
    }
    setText("pending-action-feedback", "Refresh command is not available yet.");
  }

  function initPendingActionCenterEvents() {
    if (eventsInitialized) return;
    if (typeof document === "undefined" || typeof document.querySelectorAll !== "function") return;
    document.querySelectorAll("[data-pending-action-filter]").forEach((button) => {
      button.addEventListener("click", () => applyPendingActionFilter(button.dataset.pendingActionFilter || "all"));
    });
    const drainButton = byId("pending-action-drain-button");
    if (drainButton) drainButton.addEventListener("click", triggerPendingActionDrain);
    const refreshButton = byId("pending-action-refresh-button");
    if (refreshButton) refreshButton.addEventListener("click", triggerPendingActionRefresh);
    const blockersButton = byId("pending-action-blockers-button");
    if (blockersButton) blockersButton.addEventListener("click", () => applyPendingActionFilter("blocked"));
    eventsInitialized = true;
  }
    return {
      pendingListText,
      pendingRowKey,
      getSelectedPendingRow,
      capturePendingSelectionScroll,
      restorePendingSelectionScroll,
      selectPendingRow,
      pendingDrainOverviewState,
      pendingRowPresentationStatus,
      pendingRowPresentationLabel,
      pendingRowReasonText,
      pendingRowUpdatedText,
      pendingPathDisplay,
      pendingDrainSummaryCounts,
      pendingActionCenterTriage,
      pendingActionCenterOutcome,
      setPendingActionCount,
      renderPendingActionCenter,
      renderPendingDrainOverview,
      applyPendingActionFilter,
      triggerPendingActionDrain,
      focusPendingQuickLinkTarget,
      setPendingTextFilter,
      activateQuickLink,
      triggerPendingActionRefresh,
      initPendingActionCenterEvents,
    };
  }

  window.__pendingPublishActionCenterModule = { createPendingPublishActionCenterModule };
})();
