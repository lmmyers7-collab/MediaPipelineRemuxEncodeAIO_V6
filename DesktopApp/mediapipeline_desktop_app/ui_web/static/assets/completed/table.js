// completed/table.js
// Split child of completedView.js. Loaded before completedView.js; the parent
// owns state and wires these table renderers through a temporary stash global.

(function () {
  "use strict";

  function noop() {}

  function normalizeDeps(deps = {}) {
    return {
      appendCells: typeof deps.appendCells === "function" ? deps.appendCells : noop,
      byId: typeof deps.byId === "function" ? deps.byId : function () { return null; },
      clearRows: typeof deps.clearRows === "function" ? deps.clearRows : noop,
      completedCurrentRows: typeof deps.completedCurrentRows === "function" ? deps.completedCurrentRows : function (rows) { return Array.isArray(rows) ? rows : []; },
      completedDisplayRowStatus: typeof deps.completedDisplayRowStatus === "function" ? deps.completedDisplayRowStatus : function () { return "normal"; },
      completedFilteredRows: typeof deps.completedFilteredRows === "function" ? deps.completedFilteredRows : function (rows) { return Array.isArray(rows) ? rows : []; },
      completedInvestigationFilterLabel: typeof deps.completedInvestigationFilterLabel === "function" ? deps.completedInvestigationFilterLabel : function () { return ""; },
      completedRiskStatusLine: typeof deps.completedRiskStatusLine === "function" ? deps.completedRiskStatusLine : function () { return "No current output blockers"; },
      completedRowsStatusLine: typeof deps.completedRowsStatusLine === "function" ? deps.completedRowsStatusLine : function (visibleRows, renderedRows, totalRows) {
        return `${visibleRows || renderedRows || 0} / ${totalRows || 0} rows`;
      },
      filterResultSummaryLines: deps.filterResultSummaryLines,
      finalLibraryPromotionChipState: typeof deps.finalLibraryPromotionChipState === "function" ? deps.finalLibraryPromotionChipState : function () { return "unknown"; },
      finalLibraryPromotionStatusText: typeof deps.finalLibraryPromotionStatusText === "function" ? deps.finalLibraryPromotionStatusText : function () { return ""; },
      getSelectedCompletedRow: typeof deps.getSelectedCompletedRow === "function" ? deps.getSelectedCompletedRow : function () { return null; },
      makeRowSelectable: typeof deps.makeRowSelectable === "function" ? deps.makeRowSelectable : noop,
      renderCompletedDetail: typeof deps.renderCompletedDetail === "function" ? deps.renderCompletedDetail : noop,
      renderCompletedFinalTrust: typeof deps.renderCompletedFinalTrust === "function" ? deps.renderCompletedFinalTrust : noop,
      renderCompletedOutputAcceptance: typeof deps.renderCompletedOutputAcceptance === "function" ? deps.renderCompletedOutputAcceptance : noop,
      renderCompletedPilotEvidencePacket: typeof deps.renderCompletedPilotEvidencePacket === "function" ? deps.renderCompletedPilotEvidencePacket : noop,
      selectCompletedRow: typeof deps.selectCompletedRow === "function" ? deps.selectCompletedRow : noop,
      setCellStatusChip: deps.setCellStatusChip,
      setText: typeof deps.setText === "function" ? deps.setText : noop,
      state: deps.state && typeof deps.state === "object" ? deps.state : {},
      updateTableStatusLegend: typeof deps.updateTableStatusLegend === "function" ? deps.updateTableStatusLegend : noop,
    };
  }

  function completedStateFromItem(item, status) {
    const normalized = String(status || "").toLowerCase();
    if (item?.output_exists === false) return { label: "Missing", state: "blocked" };
    if (normalized === "blocked" || normalized === "failed") return { label: "Blocked", state: "blocked" };
    if (["warning", "validation-needed", "health-check", "parked", "paused", "retrying", "unknown", "empty"].includes(normalized)) {
      return { label: "Review", state: "review" };
    }
    if (["running", "publishing"].includes(normalized)) return { label: "Active", state: "active" };
    return { label: "Healthy", state: "healthy" };
  }

  function makeCompletedStateChip(item, status) {
    const stateValue = completedStateFromItem(item, status);
    const span = document.createElement("span");
    span.className = "completed-state-chip";
    span.dataset.state = stateValue.state;
    span.textContent = stateValue.label;
    return span;
  }

  function completedRouteCategory(routeText) {
    const normalized = String(routeText || "").toLowerCase();
    if (normalized.includes("remux")) return "remux";
    if (normalized.includes("encode") || normalized.includes("transcode")) return "encode";
    if (normalized.includes("skip")) return "skip";
    if (normalized.includes("review") || normalized.includes("blocked")) return "review";
    return "";
  }

  function makeCompletedRouteChip(item) {
    const routeText = item?.route_label || item?.route || "";
    const span = document.createElement("span");
    span.className = "route-chip";
    const category = completedRouteCategory(routeText);
    if (category) span.dataset.route = category;
    span.textContent = routeText || "Pending";
    span.title = routeText || "Route pending";
    return span;
  }

  function completedShortPath(value, maxChars = 72) {
    const text = String(value || "").trim();
    if (!text || text.length <= maxChars) return text;
    const normalized = text.replace(/\\/g, "/");
    const parts = normalized.split("/").filter(Boolean);
    const last = parts.pop() || text;
    if (last.length >= maxChars - 4) return `...${last.slice(-(maxChars - 3))}`;
    return `.../${last}`;
  }

  function completedEvidenceText(item) {
    if (item?.output_exists === false) return "Output missing";
    if (item?.size_growth_over_5 || item?.size_policy_exceeded) return "Size review";
    if (item?.sidecar_exists === false) return "Sidecar missing";
    if (Array.isArray(item?.consistency_issues) && item.consistency_issues.length) {
      return String(item.consistency_issues[0] || "Consistency issue");
    }
    const consistency = String(item?.consistency_status || "").trim();
    if (consistency && !["ok", "healthy", "consistent", "consistent-looking"].includes(consistency.toLowerCase())) return consistency;
    const runtimeStatus = String(item?.runtime_outcome_status || "").trim();
    const runtimeError = String(item?.runtime_outcome_error_code || item?.runtime_outcome_reason || "").trim();
    if (runtimeStatus && ["failed", "error", "skipped", "stopped"].some((value) => runtimeStatus.toLowerCase().includes(value))) return runtimeStatus;
    if (runtimeError.toLowerCase() === "already_processed" && runtimeStatus.toLowerCase().includes("succeed")) return "Already processed";
    if (consistency) return consistency;
    if (item?.publish) return item.publish;
    return item?.output_health || "Present";
  }

  function completedRowModel(item) {
    const titleRaw = item.lookup_title || item.output_file || item.output_path || "";
    return {
      healthText: item.consistency_status || item.operator_status || item.output_health || (item.output_exists === false ? "missing output" : "ok"),
      metaDisplay: completedShortPath(item.output_file && item.output_file !== titleRaw ? item.output_file : item.output_path || item.source_path || ""),
      titleDisplay: titleRaw || "(untitled output)",
      titleRaw,
    };
  }

  function appendCompletedTableCells(ctx, row, item, model) {
    ctx.appendCells(row, [
      item.completed_at || "",
      "",
      "",
      item.media_type || "",
      "",
      completedEvidenceText(item),
      item.size_reduction_text || item.output_size_text || "",
      item.publish || "",
      ctx.finalLibraryPromotionStatusText(item),
      model.healthText,
    ], [null, "completed-state-cell", "completed-title-cell", null, "completed-route-cell", "completed-evidence-cell", "num", null, null, null]);
  }

  function renderCompletedTitleCell(cell, item, model) {
    if (!cell) return;
    cell.textContent = "";
    const title = document.createElement("span");
    title.className = "completed-title-main";
    title.textContent = model.titleDisplay;
    cell.appendChild(title);
    if (model.metaDisplay && model.metaDisplay !== model.titleDisplay) {
      const meta = document.createElement("span");
      meta.className = "completed-title-meta";
      meta.textContent = model.metaDisplay;
      cell.appendChild(meta);
    }
    if (item.output_path || item.source_path || model.titleRaw) cell.title = item.output_path || item.source_path || model.titleRaw;
  }

  function completedEvidenceCellTitle(item) {
    return [
      item.primary_concern ? `Primary concern: ${item.primary_concern}` : "",
      Array.isArray(item.review_flags) && item.review_flags.length ? `Review flags: ${item.review_flags.join(", ")}` : "",
      item.consistency_guidance ? `Consistency: ${item.consistency_guidance}` : "",
      item.runtime_outcome_status ? `Runtime: ${item.runtime_outcome_status}` : "",
    ].filter(Boolean).join("\n");
  }

  function renderCompletedRow(ctx, item, rowLabel) {
    const row = document.createElement("tr");
    const model = completedRowModel(item);
    row.dataset.status = ctx.completedDisplayRowStatus(item);
    row.dataset.rowKey = item.row_key || "";
    appendCompletedTableCells(ctx, row, item, model);

    const cells = row.querySelectorAll("td");
    const stateCell = cells[1] || row.children?.[1];
    const titleCell = cells[2] || row.children?.[2];
    const routeCell = cells[4] || row.children?.[4];
    const evidenceCell = cells[5] || row.children?.[5];
    const promotionCell = cells[8] || row.children?.[8];
    const healthCell = cells[9] || row.children?.[9];
    if (stateCell) stateCell.appendChild(makeCompletedStateChip(item, row.dataset.status));
    renderCompletedTitleCell(titleCell, item, model);
    if (routeCell) routeCell.appendChild(makeCompletedRouteChip(item));
    if (evidenceCell) evidenceCell.title = completedEvidenceCellTitle(item);
    if (typeof ctx.setCellStatusChip === "function" && ctx.finalLibraryPromotionStatusText(item)) {
      ctx.setCellStatusChip(promotionCell, ctx.finalLibraryPromotionStatusText(item), ctx.finalLibraryPromotionChipState(item));
    }
    if (typeof ctx.setCellStatusChip === "function") ctx.setCellStatusChip(healthCell, model.healthText, row.dataset.status);
    ctx.makeRowSelectable(row, () => ctx.selectCompletedRow(item), {
      selected: Boolean(item.row_key && item.row_key === ctx.state.selectedCompletedRowKey),
      label: `${rowLabel} ${item.lookup_title || item.output_file || item.output_path || ""}`,
    });
    return row;
  }

  function renderCompletedTableRows(ctx, { tbodyId, legendId, rows, sourceRows, emptyMessage, legendLabel, rowLabel, renderLimit = 250 }) {
    const tbody = ctx.byId(tbodyId);
    const rowList = Array.isArray(rows) ? rows : [];
    const sourceList = Array.isArray(sourceRows) ? sourceRows : [];
    if (!rowList.length) {
      ctx.clearRows(tbody, 10, sourceList.length ? "No completed rows match the filter." : emptyMessage);
      ctx.updateTableStatusLegend(legendId, tbody, legendLabel);
      return;
    }
    tbody.replaceChildren();
    rowList.slice(0, renderLimit).forEach((item) => {
      tbody.appendChild(renderCompletedRow(ctx, item, rowLabel));
    });
    ctx.updateTableStatusLegend(legendId, tbody, legendLabel);
  }

  function renderCurrentFilterSummary(ctx, currentRows, rows, filterText, statusFilter, investigationFilter) {
    if (typeof ctx.filterResultSummaryLines !== "function") return;
    ctx.setText("completed-filter-summary", ctx.filterResultSummaryLines({
      label: "Current output filter",
      allRows: currentRows,
      visibleRows: rows,
      filterText,
      statusFilter,
      investigationFilter,
      investigationLabel: ctx.completedInvestigationFilterLabel(investigationFilter),
      statusOf: ctx.completedDisplayRowStatus,
      limit: 250,
      decisionName: "rerun, cleanup, or library",
      guardrail: "Mutation guardrail: filtering Current Output Status does not mark outputs accepted, reconcile sidecars, rerun files, delete files, or change backend manifests.",
    }).join("\n"));
  }

  function renderHistoryFilterSummary(ctx, lastCompletedRows, rows, filterText, statusFilter, investigationFilter) {
    if (typeof ctx.filterResultSummaryLines !== "function") return;
    ctx.setText("completed-history-filter-summary", ctx.filterResultSummaryLines({
      label: "Completed history filter",
      allRows: lastCompletedRows,
      visibleRows: rows,
      filterText,
      statusFilter,
      investigationFilter,
      investigationLabel: ctx.completedInvestigationFilterLabel(investigationFilter),
      statusOf: ctx.completedDisplayRowStatus,
      limit: 250,
      decisionName: "rerun, cleanup, or library",
      guardrail: "Mutation guardrail: filtering Completed history does not mark outputs accepted, reconcile sidecars, rerun files, delete files, or change backend manifests.",
    }).join("\n"));
  }

  function renderCompletedRowsImpl(ctx) {
    const lastCompletedRows = Array.isArray(ctx.state.lastCompletedRows) ? ctx.state.lastCompletedRows : [];
    const currentRows = ctx.completedCurrentRows(lastCompletedRows);
    const filterText = ctx.byId("completed-filter")?.value || "";
    const statusFilter = ctx.byId("completed-status-filter")?.value || "all";
    const investigationFilter = ctx.byId("completed-investigation-filter")?.value || "all";
    const rows = ctx.completedFilteredRows(currentRows, filterText, statusFilter, investigationFilter);
    const renderLimit = 250;
    const renderedCount = Math.min(rows.length, renderLimit);
    const riskStatus = ctx.completedRiskStatusLine(ctx.state.lastCompletedPayload, lastCompletedRows);
    const rowsStatus = ctx.completedRowsStatusLine(rows.length, renderedCount, currentRows.length, renderLimit);
    ctx.setText("completed-status", `${riskStatus} / ${rowsStatus}`);
    ctx.setText("completed-current-status", rowsStatus);
    renderCurrentFilterSummary(ctx, currentRows, rows, filterText, statusFilter, investigationFilter);
    renderCompletedTableRows(ctx, {
      tbodyId: "completed-rows",
      legendId: "completed-table-legend",
      rows,
      sourceRows: currentRows,
      emptyMessage: lastCompletedRows.length
        ? "No current outputs are present at their expected destination. Check Completed History before rerun, cleanup, drain, deletion, or library decisions."
        : ctx.state.lastCompletedEmptyMessage,
      legendLabel: "Current output rows",
      rowLabel: "Current output row",
      renderLimit,
    });
    renderCompletedHistoryRowsImpl(ctx);
    if (ctx.state.selectedCompletedRowKey) ctx.renderCompletedDetail(ctx.getSelectedCompletedRow());
    ctx.renderCompletedOutputAcceptance(ctx.state.lastCompletedPayload, lastCompletedRows, ctx.state.lastCompletedPendingProofRows);
    ctx.renderCompletedFinalTrust(ctx.state.lastCompletedPayload, lastCompletedRows, ctx.state.lastCompletedPendingProofRows, ctx.state.lastCompletedPendingPayload);
    ctx.renderCompletedPilotEvidencePacket(ctx.state.lastCompletedPayload, lastCompletedRows, ctx.state.lastCompletedPendingProofRows, ctx.state.lastCompletedPendingPayload);
  }

  function renderCompletedHistoryRowsImpl(ctx) {
    const lastCompletedRows = Array.isArray(ctx.state.lastCompletedRows) ? ctx.state.lastCompletedRows : [];
    const filterText = ctx.byId("completed-history-filter")?.value || "";
    const statusFilter = ctx.byId("completed-history-status-filter")?.value || "all";
    const investigationFilter = ctx.byId("completed-history-investigation-filter")?.value || "all";
    const rows = ctx.completedFilteredRows(lastCompletedRows, filterText, statusFilter, investigationFilter);
    const renderLimit = 250;
    const renderedCount = Math.min(rows.length, renderLimit);
    const rowsStatus = ctx.completedRowsStatusLine(rows.length, renderedCount, lastCompletedRows.length, renderLimit);
    ctx.setText("completed-history-status", rowsStatus);
    renderHistoryFilterSummary(ctx, lastCompletedRows, rows, filterText, statusFilter, investigationFilter);
    renderCompletedTableRows(ctx, {
      tbodyId: "completed-history-rows",
      legendId: "completed-history-table-legend",
      rows,
      sourceRows: lastCompletedRows,
      emptyMessage: ctx.state.lastCompletedEmptyMessage,
      legendLabel: "Completed history rows",
      rowLabel: "Completed history row",
      renderLimit,
    });
  }

  function createCompletedTableModule(deps = {}) {
    const ctx = normalizeDeps(deps);
    return {
      renderCompletedRows: () => renderCompletedRowsImpl(ctx),
      renderCompletedHistoryRows: () => renderCompletedHistoryRowsImpl(ctx),
      renderCompletedTableRows: (options) => renderCompletedTableRows(ctx, options),
      completedStateFromItem,
      makeCompletedStateChip,
      completedRouteCategory,
      makeCompletedRouteChip,
      completedShortPath,
      completedEvidenceText,
    };
  }

  window.__completedViewTableModule = {
    createCompletedTableModule,
  };
})();
