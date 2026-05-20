(function () {
  function createPendingPublishDrainModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      commandHistoryCompactEvidenceLine = null,
      filterRows = function (rows) { return Array.isArray(rows) ? rows : []; },
      filterRowsByInvestigation = function (rows) { return Array.isArray(rows) ? rows : []; },
      filterRowsByStatus = function (rows) { return Array.isArray(rows) ? rows : []; },
      getLastPendingPayload = function () { return {}; },
      getLastPendingRecoveryPlanRows = function () { return []; },
      getLastPendingRows = function () { return []; },
      getLastPendingSnapshot = function () { return {}; },
      getSelectedPendingRow = function () { return null; },
      getSelectedPendingRowKey = function () { return ""; },
      makeRowSelectable = function () {},
      pendingDrainDecisionStatusState = function () { return "unknown"; },
      pendingFilterFields = [],
      pendingFormatCounts = function () { return "none"; },
      pendingInvestigationFilterLabel = function () { return "all signals"; },
      pendingMatchesInvestigationFilter = function () { return true; },
      pendingRecoveryPlanRowStatus = function () { return "warning"; },
      pendingRowHasHealthIssue = function () { return false; },
      pendingRowKey = function (row) { return row?.row_key || ""; },
      pendingTableRowStatus = function () { return "changed"; },
      renderPendingDrainActionConfidence = function () {},
      renderPendingDrainDecisionChecklist = function () {},
      renderPendingDrainGuard = function () {},
      renderPendingPostDrainTrust = function () {},
      selectPendingRow = function () {},
      setText = function () {},
      tableStatusFilterLabel = function (value) { return String(value || "all"); },
      updateTableStatusLegend = function () {},
    } = deps;

  function pendingCurrentFilterScope(rows = getLastPendingRows()) {
    const rowList = Array.isArray(rows) ? rows : [];
    const filterText = byId("pending-filter")?.value || "";
    const statusFilter = byId("pending-status-filter")?.value || "all";
    const investigationFilter = byId("pending-investigation-filter")?.value || "all";
    const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
    const active = Boolean(String(filterText || "").trim()) || String(statusFilter || "all").toLowerCase() !== "all" || normalizedInvestigation !== "all";
    const textRows = typeof filterRows === "function" ? filterRows(rowList, filterText, pendingFilterFields) : rowList;
    const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, pendingTableRowStatus) : textRows;
    const visibleRows = typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, pendingMatchesInvestigationFilter) : statusRows;
    const visibleKeys = new Set(visibleRows.map(pendingRowKey));
    const hiddenRows = rowList.filter((row) => !visibleKeys.has(pendingRowKey(row)));
    const hiddenBlockedRows = hiddenRows.filter((row) => pendingTableRowStatus(row) === "failed" || pendingEvidenceClass(row) === "do-not-drain" || pendingEvidenceClass(row) === "diagnostic-error" || pendingEvidenceClass(row) === "missing-payload" || pendingEvidenceClass(row) === "manifest-invalid");
    const hiddenReviewRows = hiddenRows.filter((row) => pendingTableRowStatus(row) !== "match" || pendingEvidenceClass(row) !== "ready-evidence");
    return {
      active,
      filterText: String(filterText || "").trim(),
      statusFilter,
      statusLabel: typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : String(statusFilter || "all"),
      investigationFilter,
      investigationLabel: pendingInvestigationFilterLabel(investigationFilter),
      totalCount: rowList.length,
      visibleCount: visibleRows.length,
      hiddenCount: hiddenRows.length,
      hiddenBlockedCount: hiddenBlockedRows.length,
      hiddenReviewCount: hiddenReviewRows.length,
    };
  }
  function pendingCurrentFilterScopeEvidence(scope = pendingCurrentFilterScope()) {
    const current = scope || {};
    return `filters=${current.active ? "active" : "inactive"}; visible=${current.visibleCount || 0}/${current.totalCount || 0}; hidden=${current.hiddenCount || 0}; hidden blocked=${current.hiddenBlockedCount || 0}; hidden review=${current.hiddenReviewCount || 0}; text=${current.filterText || "none"}; status=${current.statusLabel || "all"}; view=${current.investigationLabel || "all signals"}`;
  }
  function pendingCurrentFilterScopeAction(scope = pendingCurrentFilterScope()) {
    const current = scope || {};
    if (!current.active) return "No display filter is active; visible table scope matches loaded Pending Publish rows.";
    if (current.hiddenBlockedCount) return "Clear or change filters before drain. Blocked rows are hidden, but backend Publish Parked Outputs still sees all parked rows.";
    if (current.hiddenReviewCount) return "Review hidden warning rows or clear filters before drain; display filters do not narrow backend drain scope.";
    if (current.hiddenCount) return "Confirm the hidden ready-looking rows are intentionally out of view; backend drain scope is still all loaded parked rows.";
    return "Filters are active but no loaded rows are hidden.";
  }
  function pendingBackendDrainScopeRows(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : [];
    const filterScope = pendingCurrentFilterScope(rowList);
    const selected = getSelectedPendingRow();
    const latest = pendingDrainLatestCommand(entryList);
    const commandLevel = pendingDrainCommandIssueLevel(latest);
    const summary = pendingDrainSummaryPayload(payload);
    const summaryLevel = pendingDrainSummaryIssueLevel(summary);
    const recoveryRows = Array.isArray(getLastPendingRecoveryPlanRows()) ? getLastPendingRecoveryPlanRows() : [];
    const recoveryBlocked = recoveryRows.filter((row) => pendingRecoveryPlanRowStatus(row) === "blocked").length;
    const recoveryReview = recoveryRows.filter((row) => pendingRecoveryPlanRowStatus(row) === "warning").length;
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    return [
      {
        signal: "Backend drain authority",
        evidence: "/api/pipeline/start with mode=drain_pending_pushes owns Publish Parked Outputs.",
        meaning: "The backend validates manifests, payloads, destinations, and movement safety before publishing.",
        boundary: "WebView filters, selected rows, recovery-plan rows, and tables do not publish files.",
        status: "ready",
      },
      {
        signal: "Loaded parked rows",
        evidence: `rows=${payload.count || rowList.length || 0}; ready=${payload.ready_count || 0}; issues=${payload.issue_count || 0}; missing payloads=${payload.missing_local_count || 0}`,
        meaning: payload.error ? `Pending scan error must be resolved: ${payload.error}` : rowList.length ? "Backend drain can still reject rows after validation." : "No parked rows are loaded; confirm Completed/drain-summary evidence before assuming publish success.",
        boundary: "The pending table is evidence, not a manifest rewrite or drain operation.",
        status: payload.error || Number(payload.issue_count || 0) || Number(payload.missing_local_count || 0) ? "warning" : rowList.length ? "ready" : "changed",
      },
      {
        signal: "Display filter vs drain scope",
        evidence: pendingCurrentFilterScopeEvidence(filterScope),
        meaning: pendingCurrentFilterScopeAction(filterScope),
        boundary: "Filters are table search only; backend drain scope remains current parked payloads/manifests.",
        status: filterScope.hiddenBlockedCount || filterScope.hiddenReviewCount ? "warning" : filterScope.active ? "changed" : "ready",
      },
      {
        signal: "Selected row",
        evidence: selected ? selected.local_file || selected.server_out || selected.state || "selected pending row" : "none selected",
        meaning: selected ? "Selection drives details, diagnostics, open targets, and selected recovery dry-run context only." : "No row sample selected for focused inspection.",
        boundary: "Selecting a row cannot make Publish Parked Outputs drain only that row.",
        status: selected ? "ready" : "changed",
      },
      {
        signal: "Recovery dry-run evidence",
        evidence: recoveryRows.length ? `planned=${recoveryRows.length}; blocked=${recoveryBlocked}; review=${recoveryReview}` : "no recovery dry-run loaded",
        meaning: recoveryRows.length ? "Use the dry-run rows to explain risky parked outputs before drain." : "Build a selected or all-rows dry-run plan before risky drains.",
        boundary: "Recovery plans are backend-authored dry runs; they do not move, repair, delete, rewrite, or publish files.",
        status: recoveryBlocked ? "warning" : recoveryReview ? "changed" : recoveryRows.length ? "ready" : rowList.length ? "changed" : "ready",
      },
      {
        signal: "Drain result evidence",
        evidence: `latest=${latest ? `${latest.command || "pending_publish.drain"} [${pendingDrainCommandResultText(latest)}]` : "none"}; durable summary=${pendingDrainSummaryStatus(payload)}; recent events=${events.length}`,
        meaning: latest || summaryLevel !== "none" || events.length ? "Compare command result, durable summary, events, and current parked rows before another drain." : "No prior drain evidence is loaded in this WebView session.",
        boundary: "History display cannot retry, drain, repair, delete, rewrite, or mark outputs published.",
        status: commandLevel === "blocked" || summaryLevel === "blocked" ? "warning" : commandLevel === "review" || summaryLevel === "review" ? "changed" : latest || events.length ? "ready" : "changed",
      },
    ];
  }
  function pendingBackendDrainScopeStatus(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const rowsOut = pendingBackendDrainScopeRows(pending, rows, snapshot, entries);
    if (rowsOut.some((row) => row.status === "blocked")) return "Do not drain";
    if (rowsOut.some((row) => row.status === "warning")) return "Review first";
    if (rowsOut.some((row) => row.status === "changed" || row.status === "unknown")) return "Read evidence";
    return rowsOut.length ? "Ready-looking" : "Not evaluated";
  }
  function pendingBackendDrainScopeSummaryLines(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const scope = pendingCurrentFilterScope(rowList);
    const selected = getSelectedPendingRow();
    const latest = pendingDrainLatestCommand(Array.isArray(entries) ? entries : []);
    const summary = pendingDrainSummaryPayload(payload);
    const lines = [
      "Backend drain scope preview:",
      `Loaded parked rows: ${payload.count || rowList.length || 0}; visible after filters: ${scope.visibleCount}/${scope.totalCount}; selected row: ${selected ? "detail/open/recovery context only" : "none"}.`,
      `Active filters: ${scope.active ? "yes" : "no"}; hidden blocked/review rows: ${scope.hiddenBlockedCount}/${scope.hiddenReviewCount}.`,
      "Backend drain route: /api/pipeline/start with mode=drain_pending_pushes; Pending filters, selected row keys, and rendered table caps are not submitted as publish scope.",
      `Durable drain summary: attempted=${summary.attempted_count || 0}; succeeded=${summary.succeeded_count || 0}; errors=${summary.error_count || 0}; remaining=${summary.remaining_count || 0}.`,
      `Latest backend drain evidence: ${latest ? latest.message || pendingDrainCommandResultText(latest) || "loaded" : "none loaded"}.`,
    ];
    if (payload.error) {
      lines.push(`First action: do not drain until Pending Publish scan error is resolved: ${payload.error}`);
    } else if (scope.hiddenBlockedCount || scope.hiddenReviewCount) {
      lines.push("First action: clear filters or inspect hidden review rows before drain; backend validation still sees parked rows hidden by the table.");
    } else if (Number(payload.issue_count || 0) || Number(payload.missing_local_count || 0)) {
      lines.push("First action: inspect issue rows and build a dry-run recovery plan before Publish Parked Outputs.");
    } else {
      lines.push("First action: compare this scope preview with the drain decision checklist and button guard before pressing Publish Parked Outputs.");
    }
    lines.push("Mutation guardrail: this preview cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.");
    return lines;
  }
  function renderPendingBackendDrainScopePreview(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const snapshotPayload = snapshot || {};
    const entryList = Array.isArray(entries) ? entries : [];
    const scopeRows = pendingBackendDrainScopeRows(payload, rowList, snapshotPayload, entryList);
    const status = pendingBackendDrainScopeStatus(payload, rowList, snapshotPayload, entryList);
    setText("pending-backend-scope-status", status);
    const statusNode = byId("pending-backend-scope-status");
    if (statusNode) statusNode.dataset.state = pendingDrainDecisionStatusState(status);
    setText("pending-backend-scope-summary", pendingBackendDrainScopeSummaryLines(payload, rowList, snapshotPayload, entryList).join("\n"));
    const tbody = byId("pending-backend-scope-rows");
    if (!tbody) return;
    if (!scopeRows.length) {
      clearRows(tbody, 4, "No backend drain scope rows loaded.");
      updateTableStatusLegend("pending-backend-scope-legend", tbody, "Backend drain scope rows");
      return;
    }
    tbody.replaceChildren();
    scopeRows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.status === "blocked" ? "blocked" : item.status === "warning" ? "warning" : item.status === "changed" ? "changed" : "match";
      appendCells(row, [item.signal || "", item.evidence || "", item.meaning || "", item.boundary || ""]);
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-backend-scope-legend", tbody, "Backend drain scope rows");
  }
  function pendingEvidenceClass(row) {
    const recommendation = String(row?.drain_recommendation || "").toLowerCase();
    const severity = String(row?.diagnostic_severity || "").toLowerCase();
    const status = String(row?.diagnostic_status || "").toLowerCase();
    const state = String(row?.state || "").toLowerCase();
    if (recommendation === "do_not_drain") return "do-not-drain";
    if (severity === "error") return "diagnostic-error";
    if (row?.local_exists === false || status === "missing_payload") return "missing-payload";
    if (["invalid_manifest", "unreadable_manifest"].includes(status) || ["invalid_manifest", "unreadable_manifest", "invalid_contract", "unreadable"].includes(state)) return "manifest-invalid";
    if (state === "orphan_payload" || status === "orphan_payload") return "orphan-payload";
    if (Number(row?.missing_sidecar_count || 0) > 0 || status === "missing_sidecar") return "missing-sidecar";
    if (severity === "warning" || recommendation === "review_before_drain" || row?.ready_to_drain === false) return "review";
    return "ready-evidence";
  }
  function pendingEvidenceRank(row) {
    const evidenceClass = pendingEvidenceClass(row);
    const ranks = {
      "do-not-drain": 0,
      "diagnostic-error": 1,
      "missing-payload": 2,
      "manifest-invalid": 3,
      "orphan-payload": 4,
      "missing-sidecar": 5,
      review: 6,
      "ready-evidence": 7,
    };
    return ranks[evidenceClass] ?? 99;
  }
  function pendingEvidenceRows(rows, includeReady = false) {
    const rowList = Array.isArray(rows) ? rows : [];
    return rowList
      .map((row, index) => ({ row, index, evidenceClass: pendingEvidenceClass(row) }))
      .filter((entry) => includeReady || entry.evidenceClass !== "ready-evidence")
      .sort((a, b) => pendingEvidenceRank(a.row) - pendingEvidenceRank(b.row) || a.index - b.index);
  }
  function pendingEvidenceStatus(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) return "Diagnostics first";
    if (payload.exists === false) return "No pending root";
    if (!rowList.length) return "No parked rows";
    const evidenceRows = pendingEvidenceRows(rowList);
    if (evidenceRows.some((entry) => ["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass))) return "Blocked evidence";
    if (evidenceRows.length) return "Review evidence";
    return "No blockers";
  }
  function pendingEvidenceLabel(row) {
    return row?.local_file || row?.manifest_path || row?.server_out || row?.source_path || row?.row_key || "(pending row)";
  }
  function pendingEvidenceText(row) {
    const fields = Array.isArray(row?.evidence_fields) ? row.evidence_fields.filter(Boolean) : [];
    const proof = Array.isArray(row?.proof_summary) ? row.proof_summary.filter(Boolean) : [];
    const evidence = [
      row?.diagnostic_status ? `status=${row.diagnostic_status}` : "",
      row?.diagnostic_severity ? `severity=${row.diagnostic_severity}` : "",
      row?.recovery_class ? `recovery=${row.recovery_class}` : "",
      fields.length ? `fields=${fields.slice(0, 3).join(", ")}` : "",
      proof.length ? proof.slice(0, 2).join("; ") : "",
    ].filter(Boolean).join("; ");
    return evidence || row?.issue_summary || row?.error || "no explicit evidence fields reported";
  }
  function pendingEvidenceAction(row) {
    if (!row) return "Select a row and inspect backend-selected targets before drain.";
    if (row.safe_next_action) return row.safe_next_action;
    if (row.recovery_action) return row.recovery_action;
    const evidenceClass = pendingEvidenceClass(row);
    if (["do-not-drain", "diagnostic-error", "manifest-invalid"].includes(evidenceClass)) {
      return "Do not drain. Open manifest/payload evidence and read Last Stderr before another publish attempt.";
    }
    if (evidenceClass === "missing-payload") return "Open the manifest and source/output folders; confirm whether payload copy or parking failed.";
    if (evidenceClass === "orphan-payload") return "Classify the orphan payload with Run Logs before cleanup, rerun, or manual move.";
    if (evidenceClass === "missing-sidecar") return "Compare manifest sidecar paths against disk before publishing or cleanup.";
    if (evidenceClass === "review") return "Build a selected-row recovery dry-run plan and inspect recommended open targets.";
    return "Row looks ready, but only backend Publish Parked Outputs may move files.";
  }
  function pendingDrainEvidenceLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const evidenceRows = pendingEvidenceRows(rowList);
    const counts = evidenceRows.reduce((acc, entry) => {
      acc[entry.evidenceClass] = (acc[entry.evidenceClass] || 0) + 1;
      return acc;
    }, {});
    const lines = [
      "Pending drain evidence board:",
      `Rows loaded: ${payload.count || rowList.length || 0}`,
      `Do-not-drain=${counts["do-not-drain"] || 0}; diagnostic-error=${counts["diagnostic-error"] || 0}; missing-payload=${counts["missing-payload"] || 0}; manifest-invalid=${counts["manifest-invalid"] || 0}.`,
      `Orphan-payload=${counts["orphan-payload"] || 0}; missing-sidecar=${counts["missing-sidecar"] || 0}; review=${counts.review || 0}.`,
    ];
    if (payload.error) {
      lines.push("First action: open Diagnostics > Pending Publish and Run Logs because the pending payload is unavailable.");
    } else if (payload.exists === false) {
      lines.push("First action: no pending root exists. Check Completed and Run Logs before reprocessing an expected output.");
    } else if (!rowList.length) {
      lines.push("First action: no parked rows are waiting. This board is empty by design.");
    } else if (evidenceRows.length) {
      lines.push("First action: select the highest-risk evidence row below, inspect backend-selected row targets, then build a selected-row recovery dry-run plan if needed.");
    } else {
      lines.push("First action: no loaded pending rows expose drain blockers. Publish Parked Outputs remains the backend-owned validation and movement path.");
    }
    lines.push("Mutation guardrail: this board is read-only. It cannot drain, repair, rewrite, move, delete, or publish files.");
    return lines;
  }
  function renderPendingDrainEvidence(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const evidenceRows = pendingEvidenceRows(rowList);
    setText("pending-evidence-status", pendingEvidenceStatus(payload, rowList));
    setText("pending-evidence-summary", pendingDrainEvidenceLines(payload, rowList).join("\n"));
    const tbody = byId("pending-evidence-rows");
    if (!tbody) return;
    if (!evidenceRows.length) {
      clearRows(tbody, 5, rowList.length ? "No pending rows with drain blockers or review evidence." : "No pending rows loaded.");
      updateTableStatusLegend("pending-evidence-legend", tbody, "Pending evidence rows");
      return;
    }
    tbody.replaceChildren();
    evidenceRows.slice(0, 30).forEach(({ row: item, evidenceClass }) => {
      const row = document.createElement("tr");
      if (["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(evidenceClass)) row.dataset.status = "blocked";
      else if (evidenceClass === "ready-evidence") row.dataset.status = "match";
      else row.dataset.status = "warning";
      appendCells(row, [
        evidenceClass,
        item.drain_recommendation || "review",
        pendingEvidenceText(item),
        pendingEvidenceLabel(item),
        pendingEvidenceAction(item),
      ]);
      makeRowSelectable(row, () => selectPendingRow(item), {
        selected: Boolean(pendingRowKey(item) && pendingRowKey(item) === getSelectedPendingRowKey()),
        label: `Review pending evidence ${pendingEvidenceLabel(item)}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-evidence-legend", tbody, "Pending evidence rows");
  }
  function pendingDrainSearchText(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const rawData = raw.data && typeof raw.data === "object" ? raw.data : {};
    const parts = [
      entry?.command,
      entry?.message,
      entry?.result,
      raw.command,
      raw.message,
      rawData.mode,
      rawData.requested_mode,
      rawData.actual_mode,
      rawData.refresh_hint,
    ];
    return parts.filter(Boolean).join(" ").toLocaleLowerCase();
  }
  function isPendingDrainCommand(entry) {
    const text = pendingDrainSearchText(entry);
    return (
      text.includes("pending_publish.drain") ||
      text.includes("drain_pending_pushes") ||
      text.includes("publish parked") ||
      text.includes("pending publish drain")
    );
  }
  function pendingDrainHistoryLine(entry) {
    const data = pendingDrainCommandData(entry);
    const request = pendingDrainCommandRequest(entry);
    const bits = [];
    const mode = data.mode || data.requested_mode || data.actual_mode || request.mode;
    if (mode) bits.push(`mode=${mode}`);
    if (data.attempted_count !== undefined) bits.push(`attempted=${data.attempted_count}`);
    if (data.succeeded_count !== undefined) bits.push(`succeeded=${data.succeeded_count}`);
    if (data.already_published_count !== undefined) bits.push(`already=${data.already_published_count}`);
    if (data.error_count !== undefined) bits.push(`errors=${data.error_count}`);
    if (data.remaining_count !== undefined) bits.push(`remaining=${data.remaining_count}`);
    if (data.frontend_guard) bits.push("frontend_guard=true");
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: entry?.command || "pending publish drain",
        detail: bits.length ? ` (${bits.join("; ")})` : "",
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} ${entry?.command || "unknown"} [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
  }
  function renderPendingDrainHistory(entries) {
    const history = Array.isArray(entries) ? entries.filter(isPendingDrainCommand).slice(0, 5) : [];
    if (!Array.isArray(entries) || !entries.length) {
      setText(
        "pending-drain-history",
        "No pending publish drain history loaded. Refresh command history after running Publish Parked Outputs.",
      );
      renderPendingDrainCorrelation(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingPostDrainTrust(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingDrainActionConfidence(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      return;
    }
    if (!history.length) {
      setText(
        "pending-drain-history",
        "No pending publish drain commands found in command history. Use Publish Parked Outputs to start a backend-owned drain.",
      );
      renderPendingDrainCorrelation(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingPostDrainTrust(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingDrainActionConfidence(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
      return;
    }
    const lines = [
      `Last ${history.length} pending publish drain command${history.length === 1 ? "" : "s"}:`,
      ...history.map(pendingDrainHistoryLine),
      "Open Run Logs from Diagnostics when a drain reports warnings, errors, or no payload movement.",
    ];
    setText("pending-drain-history", lines.join("\n"));
    renderPendingDrainCorrelation(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
    renderPendingPostDrainTrust(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
    renderPendingDrainActionConfidence(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
    renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
    renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), entries);
  }
  function pendingDrainEventData(event) {
    if (!event || typeof event !== "object") return {};
    const data = event.data && typeof event.data === "object" ? event.data : {};
    return { ...data, ...event };
  }
  function pendingDrainEventsFromSnapshot(snapshot) {
    const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
    return events.filter((event) => {
      const data = pendingDrainEventData(event);
      const type = String(data.event_type || "").toLowerCase();
      const stage = String(data.stage || "").toLowerCase();
      return type === "publish_drained" || (stage === "retry_pending_push" && type.includes("publish"));
    });
  }
  function pendingDrainEventStatus(event) {
    const data = pendingDrainEventData(event);
    return String(data.status || data.Status || "unknown").trim() || "unknown";
  }
  function pendingDrainEventRoute(event) {
    const data = pendingDrainEventData(event);
    return String(data.route || data.Route || "unknown").trim() || "unknown";
  }
  function pendingDrainEventSidecarCount(event) {
    const data = pendingDrainEventData(event);
    const value = Number(data.sidecar_count || data.SidecarCount || 0);
    return Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0;
  }
  function pendingDrainEventLeaf(event) {
    const data = pendingDrainEventData(event);
    const path = String(data.server_out || data.local_file || data.source_path || data.SourcePath || data.manifest_path || "").trim();
    if (!path) return "(unknown output)";
    return path.split(/[\\/]/).filter(Boolean).pop() || path;
  }
  function pendingDrainEventCounts(events, selector) {
    const counts = {};
    events.forEach((event) => {
      const key = String(selector(event) || "unknown").trim() || "unknown";
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ") || "none";
  }
  function pendingDrainEventsStatus(snapshot) {
    const events = pendingDrainEventsFromSnapshot(snapshot);
    if (!Array.isArray(snapshot?.recent_events)) return "No snapshot";
    if (!events.length) return "No recent drains";
    const failed = events.some((event) => !["succeeded", "already_published"].includes(pendingDrainEventStatus(event).toLowerCase()));
    return failed ? "Review events" : "Recent drains";
  }
  function pendingDrainEventsLines(snapshot) {
    const events = pendingDrainEventsFromSnapshot(snapshot);
    if (!Array.isArray(snapshot?.recent_events)) {
      return [
        "No snapshot events are loaded.",
        "Refresh the WebView after running Publish Parked Outputs to see backend-authored drain events here.",
      ];
    }
    if (!events.length) {
      return [
        "No recent publish_drained events found in the backend snapshot.",
        "After a successful Publish Parked Outputs run, pipeline_events.jsonl should contain backend-authored publish_drained records.",
        "Open Diagnostics > Pipeline Events or Run Logs if a drain command reported success but no events appear.",
      ];
    }
    const sidecars = events.reduce((total, event) => total + pendingDrainEventSidecarCount(event), 0);
    const lines = [
      `Recent drain event rows: ${events.length}`,
      `Statuses: ${pendingDrainEventCounts(events, pendingDrainEventStatus)}`,
      `Routes: ${pendingDrainEventCounts(events, pendingDrainEventRoute)}`,
      `Sidecars included in recent events: ${sidecars}`,
      "",
      "Latest backend-authored drain events:",
    ];
    events.slice(-8).reverse().forEach((event) => {
      const data = pendingDrainEventData(event);
      const when = data.timestamp || data.created_at || "";
      const status = pendingDrainEventStatus(event);
      const route = pendingDrainEventRoute(event);
      const leaf = pendingDrainEventLeaf(event);
      const sidecarCount = pendingDrainEventSidecarCount(event);
      lines.push(`- ${when} [${status}; ${route}] ${leaf}${sidecarCount ? ` (${sidecarCount} sidecar${sidecarCount === 1 ? "" : "s"})` : ""}`);
    });
    lines.push("");
    lines.push("Operator note: this panel only reflects recent backend pipeline events. The pending table remains the current source of truth for what is still parked.");
    return lines;
  }
  function renderPendingDrainEvents(snapshot) {
    setText("pending-drain-events-status", pendingDrainEventsStatus(snapshot || {}));
    setText("pending-drain-events", pendingDrainEventsLines(snapshot || {}).join("\n"));
  }
  function pendingDrainSummaryPayload(pending) {
    const summary = pending?.drain_summary;
    return summary && typeof summary === "object" ? summary : {};
  }
  function pendingDrainSummaryItems(summary) {
    return Array.isArray(summary?.items) ? summary.items : [];
  }
  function pendingDrainSummaryStatus(pending) {
    const summary = pendingDrainSummaryPayload(pending);
    if (summary.read_error) return "Unreadable summary";
    if (summary.exists === false) return "No summary";
    if (!summary.started_at && !summary.completed_at) return "No summary";
    if (summary.deferred) return "Deferred";
    if (summary.stopped) return "Stopped";
    if (Number(summary.error_count || 0) > 0) return "Review drain";
    if (Number(summary.succeeded_count || 0) > 0 || Number(summary.already_published_count || 0) > 0) return "Last drain complete";
    if (Number(summary.attempted_count || 0) === 0) return "No attempts";
    return "Last drain recorded";
  }
  function pendingDrainSummaryLeaf(item) {
    const path = String(item?.server_out || item?.local_file || item?.source_path || item?.manifest_path || "").trim();
    if (!path) return "(unknown output)";
    return path.split(/[\\/]/).filter(Boolean).pop() || path;
  }
  function pendingDrainSummaryLines(pending) {
    const summary = pendingDrainSummaryPayload(pending);
    if (summary.read_error) {
      return [
        "Pending drain summary exists but could not be read.",
        `Path: ${summary.path || "not reported"}`,
        `Error: ${summary.read_error}`,
        "Safe action: open Diagnostics > State or Run Logs before running another drain.",
      ];
    }
    if (summary.exists === false || (!summary.started_at && !summary.completed_at)) {
      return [
        "No durable pending-publish drain summary has been written yet.",
        `Expected path: ${summary.path || "not resolved"}`,
        "Run Publish Parked Outputs or let the backend encounter deferred parked outputs to create this summary.",
      ];
    }

    const items = pendingDrainSummaryItems(summary);
    const lines = [
      `Schema: ${summary.schema_version || "pending_drain_summary.v1"}`,
      `Started: ${summary.started_at || ""}`,
      `Completed: ${summary.completed_at || ""}`,
      `Force drain: ${summary.force ? "yes" : "no"}`,
      `Deferred without drain: ${summary.deferred ? "yes" : "no"}`,
      `Stopped early: ${summary.stopped ? "yes" : "no"}`,
      `Pending root: ${summary.pending_root || pending?.pending_root || "not reported"}`,
      `Manifest count at start: ${summary.manifest_count_at_start || 0}`,
      `Attempted: ${summary.attempted_count || 0}`,
      `Recovered/published: ${summary.recovered_count || 0}`,
      `Succeeded: ${summary.succeeded_count || 0}`,
      `Already published: ${summary.already_published_count || 0}`,
      `Errors: ${summary.error_count || 0}`,
      `Skipped: ${summary.skipped_count || 0}`,
      `Remaining manifests after refresh: ${summary.remaining_count || 0}`,
      `Status counts: ${pendingFormatCounts(summary.status_counts)}`,
      `Route counts: ${pendingFormatCounts(summary.route_counts)}`,
    ];
    const warnings = Array.isArray(summary.warnings) ? summary.warnings.filter(Boolean) : [];
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    if (items.length) {
      lines.push("", "Latest summary items:");
      items.slice(-8).reverse().forEach((item) => {
        const status = String(item?.status || "unknown").trim() || "unknown";
        const route = String(item?.route || "unknown").trim() || "unknown";
        const sidecars = Number(item?.sidecar_count || 0);
        const error = String(item?.error || "").trim();
        lines.push(`- [${status}; ${route}] ${pendingDrainSummaryLeaf(item)}${sidecars ? ` (${sidecars} sidecar${sidecars === 1 ? "" : "s"})` : ""}${error ? ` - ${error}` : ""}`);
      });
    }
    lines.push("");
    lines.push("Operator note: this durable summary records the last backend drain attempt. The pending table remains the source of truth for what is still parked.");
    return lines;
  }
  function renderPendingDrainSummary(pending) {
    setText("pending-drain-summary-status", pendingDrainSummaryStatus(pending || {}));
    setText("pending-drain-summary", pendingDrainSummaryLines(pending || {}).join("\n"));
  }
  function pendingDrainLatestCommand(entries) {
    const history = Array.isArray(entries) ? entries.filter(isPendingDrainCommand) : [];
    return history.length ? history[0] : null;
  }
  function pendingDrainCommandData(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    return raw.data && typeof raw.data === "object" ? raw.data : {};
  }
  function pendingDrainCommandRequest(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    if (raw.request && typeof raw.request === "object") return raw.request;
    if (raw.submitted_request && typeof raw.submitted_request === "object") return raw.submitted_request;
    return {};
  }
  function pendingDrainCommandResultText(entry) {
    if (!entry) return "no recent drain command";
    return entry.result || (entry.ok ? "ok" : entry.severity || "unknown");
  }
  function pendingDrainCommandIssueLevel(entry) {
    if (!entry) return "none";
    const data = pendingDrainCommandData(entry);
    const result = String(pendingDrainCommandResultText(entry)).toLowerCase();
    if (!entry.ok || ["error", "failed", "blocked"].includes(result)) return "blocked";
    if (
      entry.severity === "warning" ||
      Number(data.error_count || 0) > 0 ||
      Number(data.blocker_count || 0) > 0 ||
      data.stopped ||
      data.deferred
    ) {
      return "review";
    }
    return "ok";
  }
  function pendingDrainSummaryIssueLevel(summary) {
    if (summary?.read_error) return "blocked";
    if (summary?.exists === false || (!summary?.started_at && !summary?.completed_at)) return "none";
    if (summary?.stopped || Number(summary?.error_count || 0) > 0) return "blocked";
    if (summary?.deferred || Number(summary?.skipped_count || 0) > 0 || Number(summary?.remaining_count || 0) > 0) return "review";
    return "ok";
  }
  function pendingDrainCorrelationStatus(pending, rows, snapshot, entries) {
    const rowList = Array.isArray(rows) ? rows : [];
    const summary = pendingDrainSummaryPayload(pending || {});
    const latest = pendingDrainLatestCommand(entries);
    const commandLevel = pendingDrainCommandIssueLevel(latest);
    const summaryLevel = pendingDrainSummaryIssueLevel(summary);
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const blockers = pendingEvidenceRows(rowList).filter((entry) => ["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    if ((pending || {}).error || commandLevel === "blocked" || summaryLevel === "blocked" || blockers.length) return "Do not drain";
    if (issueRows.length || commandLevel === "review" || summaryLevel === "review") return "Review first";
    if (!rowList.length && (Number(summary.succeeded_count || 0) > 0 || Number(summary.already_published_count || 0) > 0 || events.length)) return "Likely drained";
    if (!rowList.length) return "No parked rows";
    if (latest || summaryLevel === "ok" || events.length) return "Correlated";
    return "No drain evidence";
  }
  function pendingDrainCorrelationLines(pending, rows, snapshot, entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entriesList = Array.isArray(entries) ? entries : [];
    const summary = pendingDrainSummaryPayload(payload);
    const latest = pendingDrainLatestCommand(entriesList);
    const commandData = pendingDrainCommandData(latest);
    const commandRequest = pendingDrainCommandRequest(latest);
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const evidenceRows = pendingEvidenceRows(rowList, false);
    const doNotDrainRows = evidenceRows.filter((entry) => ["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    const readyRows = rowList.filter((row) => pendingEvidenceClass(row) === "ready-evidence" || row?.ready_to_drain === true);
    const lines = [
      "Pending Publish drain correlation:",
      `Current parked rows: ${payload.count || rowList.length || 0}`,
      `Ready/review/do-not-drain rows: ${readyRows.length} / ${Math.max(0, issueRows.length - doNotDrainRows.length)} / ${doNotDrainRows.length}`,
      `Latest drain command: ${latest ? `${latest.at || ""} ${latest.command || "unknown"} [${pendingDrainCommandResultText(latest)}] ${latest.message || ""}`.trim() : "none in loaded command history"}`,
      `Command mode/request: ${commandData.mode || commandData.requested_mode || commandData.actual_mode || commandRequest.mode || "not reported"}`,
      `Durable summary status: ${pendingDrainSummaryStatus(payload)}`,
      `Summary attempted/succeeded/already/errors/skipped/remaining: ${summary.attempted_count || 0} / ${summary.succeeded_count || 0} / ${summary.already_published_count || 0} / ${summary.error_count || 0} / ${summary.skipped_count || 0} / ${summary.remaining_count || 0}`,
      `Recent drain events: ${events.length}${events.length ? ` (${pendingDrainEventCounts(events, pendingDrainEventStatus)})` : ""}`,
      "",
    ];
    if (payload.error) {
      lines.push("Correlation: pending publish scan is unavailable. Do not drain until Diagnostics, Pending Publish state, Run Logs, and Last Stderr are readable.");
    } else if (doNotDrainRows.length) {
      lines.push("Correlation: current rows include do-not-drain evidence. Select the highest-risk evidence row and build a recovery dry-run before another drain attempt.");
    } else if (latest && pendingDrainCommandIssueLevel(latest) === "blocked") {
      lines.push("Correlation: latest drain command failed or was blocked. Treat any partial output movement as untrusted until Last Drain Summary and Completed output proof agree.");
    } else if (summary.read_error) {
      lines.push("Correlation: the durable drain summary is unreadable. Open Diagnostics > State and Run Logs before retrying Publish Parked Outputs.");
    } else if (summary.stopped || Number(summary.error_count || 0) > 0) {
      lines.push("Correlation: the durable summary reports stopped/error state. Inspect summary items, Last Stderr, and remaining pending rows before rerun or drain.");
    } else if (Number(summary.remaining_count || 0) > 0 || rowList.length > 0) {
      lines.push("Correlation: parked rows still exist after the latest known drain context. Review blockers/warnings first; another drain may be valid only after backend evidence is coherent.");
    } else if (!rowList.length && (Number(summary.succeeded_count || 0) > 0 || Number(summary.already_published_count || 0) > 0 || events.length)) {
      lines.push("Correlation: current pending rows are empty and backend drain evidence exists. Check Completed/output proof if an expected file is still missing.");
    } else if (!latest && summary.exists === false) {
      lines.push("Correlation: no drain command or durable summary is loaded. This is expected before the first Publish Parked Outputs run.");
    } else if (!rowList.length) {
      lines.push("Correlation: no parked rows are loaded. Do not rerun sources solely because Pending Publish is empty; compare Completed, Queue, and Run Logs first.");
    } else {
      lines.push("Correlation: loaded rows do not expose blockers, but Publish Parked Outputs remains the only backend-owned movement path.");
    }
    lines.push("Mutation guardrail: this correlation is read-only. It cannot repair, drain, rewrite, move, delete, publish, or bypass backend validation.");
    return lines;
  }
  function renderPendingDrainCorrelation(pending, rows, snapshot, entries) {
    setText("pending-drain-correlation-status", pendingDrainCorrelationStatus(pending || {}, rows || [], snapshot || {}, entries || []));
    setText("pending-drain-correlation", pendingDrainCorrelationLines(pending || {}, rows || [], snapshot || {}, entries || []).join("\n"));
  }

    return {
      isPendingDrainCommand,
      pendingBackendDrainScopeRows,
      pendingBackendDrainScopeStatus,
      pendingBackendDrainScopeSummaryLines,
      pendingCurrentFilterScope,
      pendingCurrentFilterScopeAction,
      pendingCurrentFilterScopeEvidence,
      pendingDrainCommandData,
      pendingDrainCommandIssueLevel,
      pendingDrainCommandRequest,
      pendingDrainCommandResultText,
      pendingDrainCorrelationLines,
      pendingDrainCorrelationStatus,
      pendingDrainEventCounts,
      pendingDrainEventLeaf,
      pendingDrainEventRoute,
      pendingDrainEventStatus,
      pendingDrainEventsFromSnapshot,
      pendingDrainEventsLines,
      pendingDrainEventsStatus,
      pendingDrainEvidenceLines,
      pendingDrainHistoryLine,
      pendingDrainLatestCommand,
      pendingDrainSearchText,
      pendingDrainSummaryIssueLevel,
      pendingDrainSummaryItems,
      pendingDrainSummaryLeaf,
      pendingDrainSummaryLines,
      pendingDrainSummaryPayload,
      pendingDrainSummaryStatus,
      pendingEvidenceAction,
      pendingEvidenceClass,
      pendingEvidenceRows,
      pendingEvidenceStatus,
      pendingEvidenceText,
      renderPendingBackendDrainScopePreview,
      renderPendingDrainCorrelation,
      renderPendingDrainEvents,
      renderPendingDrainEvidence,
      renderPendingDrainHistory,
      renderPendingDrainSummary,
    };
  }

  window.__pendingPublishDrainModule = { createPendingPublishDrainModule };
})();
