// completed/table.js
// Split child of completedView.js. Loaded before completedView.js; the parent
// owns state and wires these table renderers through a temporary stash global.

(function () {
  "use strict";

  function noop() {}

  const COMPLETED_TABLE_COLUMN_COUNT = 7;

  function normalizeDeps(deps = {}) {
    return {
      appendCells: typeof deps.appendCells === "function" ? deps.appendCells : noop,
      appendCompletedPromotionCellAction: typeof deps.appendCompletedPromotionCellAction === "function" ? deps.appendCompletedPromotionCellAction : noop,
      byId: typeof deps.byId === "function" ? deps.byId : function () { return null; },
      clearRows: typeof deps.clearRows === "function" ? deps.clearRows : noop,
      completedCurrentRows: typeof deps.completedCurrentRows === "function" ? deps.completedCurrentRows : function (rows) { return Array.isArray(rows) ? rows : []; },
      completedDisplayRowStatus: typeof deps.completedDisplayRowStatus === "function" ? deps.completedDisplayRowStatus : function () { return "normal"; },
      completedFilteredRows: typeof deps.completedFilteredRows === "function" ? deps.completedFilteredRows : function (rows) { return Array.isArray(rows) ? rows : []; },
      completedInvestigationFilterLabel: typeof deps.completedInvestigationFilterLabel === "function" ? deps.completedInvestigationFilterLabel : function () { return ""; },
      completedLibraryFilterLabel: typeof deps.completedLibraryFilterLabel === "function" ? deps.completedLibraryFilterLabel : function () { return "all libraries"; },
      completedOutputPlacement: typeof deps.completedOutputPlacement === "function" ? deps.completedOutputPlacement : function () { return { label: "Current", state: "ok", key: "current" }; },
      completedRiskStatusLine: typeof deps.completedRiskStatusLine === "function" ? deps.completedRiskStatusLine : function () { return "No current output blockers"; },
      completedRowsStatusLine: typeof deps.completedRowsStatusLine === "function" ? deps.completedRowsStatusLine : function (visibleRows, renderedRows, totalRows) {
        return `${visibleRows || renderedRows || 0} / ${totalRows || 0} rows`;
      },
      filterResultSummaryLines: deps.filterResultSummaryLines,
      finalLibraryPromotionChipState: typeof deps.finalLibraryPromotionChipState === "function" ? deps.finalLibraryPromotionChipState : function () { return "unknown"; },
      finalLibraryPromotionStatusText: typeof deps.finalLibraryPromotionStatusText === "function" ? deps.finalLibraryPromotionStatusText : function () { return ""; },
      getSelectedCompletedRow: typeof deps.getSelectedCompletedRow === "function" ? deps.getSelectedCompletedRow : function () { return null; },
      makeStatusChip: typeof deps.makeStatusChip === "function" ? deps.makeStatusChip : function (label) {
        const span = document.createElement("span");
        span.textContent = label || "";
        return span;
      },
      makeRowSelectable: typeof deps.makeRowSelectable === "function" ? deps.makeRowSelectable : noop,
      renderCompletedTrustDecision: typeof deps.renderCompletedTrustDecision === "function" ? deps.renderCompletedTrustDecision : noop,
      renderCompletedDetail: typeof deps.renderCompletedDetail === "function" ? deps.renderCompletedDetail : noop,
      renderCompletedActiveOutputContext: typeof deps.renderCompletedActiveOutputContext === "function" ? deps.renderCompletedActiveOutputContext : noop,
      renderCompletedEvidenceCopyState: typeof deps.renderCompletedEvidenceCopyState === "function" ? deps.renderCompletedEvidenceCopyState : noop,
      renderCompletedFinalTrust: typeof deps.renderCompletedFinalTrust === "function" ? deps.renderCompletedFinalTrust : noop,
      renderCompletedOutputAcceptance: typeof deps.renderCompletedOutputAcceptance === "function" ? deps.renderCompletedOutputAcceptance : noop,
      renderCompletedPilotEvidencePacket: typeof deps.renderCompletedPilotEvidencePacket === "function" ? deps.renderCompletedPilotEvidencePacket : noop,
      selectCompletedRow: typeof deps.selectCompletedRow === "function" ? deps.selectCompletedRow : noop,
      setCellStatusChip: deps.setCellStatusChip,
      setText: typeof deps.setText === "function" ? deps.setText : noop,
      state: deps.state && typeof deps.state === "object" ? deps.state : {},
      syncCompletedLibraryFilterOptions: typeof deps.syncCompletedLibraryFilterOptions === "function" ? deps.syncCompletedLibraryFilterOptions : function () { return "all"; },
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

  function completedRouteEvidenceText(item) {
    const evidenceLines = Array.isArray(item?.route_evidence_lines) ? item.route_evidence_lines : [];
    return [
      item?.route_reason_code,
      item?.route_reason,
      item?.route_decision_summary,
      item?.size_policy_route_reason_code,
      item?.size_policy_message,
      item?.runtime_outcome_reason,
      item?.runtime_outcome_error_code,
      ...evidenceLines,
    ].map((value) => String(value || "")).join(" ").toLowerCase();
  }

  function completedUsedOversizedEncodeRemuxFallback(item) {
    const evidence = completedRouteEvidenceText(item);
    return evidence.includes("oversized_encode_remux_fallback")
      || (evidence.includes("remux fallback") && evidence.includes("oversized encode"));
  }

  function completedRouteChipCategory(item, routeText) {
    const category = completedRouteCategory(routeText);
    if (category === "remux" && completedUsedOversizedEncodeRemuxFallback(item)) return "remux-fallback";
    return category;
  }

  function completedRouteChipTitle(item, routeText, category) {
    const label = routeText || "Pending";
    if (category !== "remux-fallback") return routeText || "Route pending";
    const reason = String(item?.route_reason || item?.route_decision_summary || "").trim();
    return [
      `Final route: ${label}.`,
      "Encode was attempted first and remux fallback was published after the encode exceeded size policy.",
      reason,
    ].filter(Boolean).join("\n");
  }

  function makeCompletedRouteChip(item) {
    const routeText = item?.route_label || item?.route || "";
    const span = document.createElement("span");
    span.className = "route-chip";
    const category = completedRouteChipCategory(item, routeText);
    if (category) span.dataset.route = category;
    span.textContent = routeText || "Pending";
    span.title = completedRouteChipTitle(item, routeText, category);
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

  function completedPathLeaf(value) {
    const normalized = String(value || "").replace(/\\/g, "/").trim();
    if (!normalized) return "";
    return normalized.split("/").filter(Boolean).pop() || normalized;
  }

  function completedFileStem(value) {
    return completedPathLeaf(value).replace(/\.[^.\\/]+$/, "").trim();
  }

  function completedComparableTitle(value) {
    return completedFileStem(value).toLowerCase();
  }

  function completedTvEpisodeTitle(item) {
    if (String(item?.media_type || "").toLowerCase() !== "tv") return "";
    const source = item?.relative_path || item?.source_path || item?.output_path || item?.output_file || "";
    const parts = String(source || "").replace(/\\/g, "/").split("/").filter(Boolean);
    const leafStem = completedFileStem(parts[parts.length - 1] || source);
    const seasonText = parts.find((part) => /\bseason\s*\d+\b/i.test(part)) || item?.lookup_title || "";
    const seasonMatch = String(seasonText).match(/\bseason\s*0*(\d+)\b/i) || leafStem.match(/\bS0*(\d{1,2})E\d{1,3}\b/i);
    const episodeMatch = leafStem.match(/\bS\d{1,2}E0*(\d{1,3})\b/i) || leafStem.match(/\bE0*(\d{1,3})\b/i);
    if (!seasonMatch || !episodeMatch) return "";
    const seasonIndex = parts.findIndex((part) => /\bseason\s*\d+\b/i.test(part));
    const series = seasonIndex > 0 ? parts[seasonIndex - 1] : String(item?.series_title || item?.show_title || "").trim();
    if (!series) return "";
    let episodeTitle = leafStem;
    if (episodeTitle.toLowerCase().startsWith(`${series.toLowerCase()} `)) {
      episodeTitle = episodeTitle.slice(series.length).trim();
    }
    episodeTitle = episodeTitle
      .replace(/\bS\d{1,2}E\d{1,3}\b/i, "")
      .replace(/\bE\d{1,3}\b/i, "")
      .replace(/^[\s._-]+|[\s._-]+$/g, "")
      .replace(/[\s._-]+/g, " ");
    const season = String(seasonMatch[1]).padStart(2, "0");
    const episode = String(episodeMatch[1]).padStart(2, "0");
    return `${series} - S${season}E${episode}${episodeTitle ? ` - ${episodeTitle}` : ""}`;
  }

  function completedEvidenceText(item) {
    const qa = item && typeof item.subtitle_qa === "object" ? item.subtitle_qa : null;
    const qaPosture = String(qa?.posture || "").toLowerCase();
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
    if (qaPosture === "blocked") return "Subtitle QA blocked";
    if (qaPosture === "review") return "Subtitle QA review";
    const outputHealth = String(item?.output_health || "").trim();
    if (outputHealth && !["ok", "healthy", "present", "consistent", "consistent-looking"].includes(outputHealth.toLowerCase())) {
      return outputHealth;
    }
    return "";
  }

  function completedColumnMode(ctx) {
    const mode = String(ctx?.state?.completedSizeColumnMode || "size").trim().toLowerCase();
    return mode === "bitrate" ? "bitrate" : "size";
  }

  function completedFormatMbps(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) return "";
    const precision = number >= 1 ? 1 : 2;
    return `${number.toFixed(precision).replace(/\.?0+$/, "")} Mbps`;
  }

  function completedSizeDisplay(item) {
    return item?.size_reduction_text || item?.output_size_text || "";
  }

  function completedBitrateDisplay(item) {
    return item?.bitrate_text || item?.output_bitrate_text || item?.source_bitrate_text || completedFormatMbps(item?.bitrate_mbps);
  }

  function completedMeasureDisplay(item, mode) {
    if (mode === "bitrate") return completedBitrateDisplay(item) || "n/a";
    return completedSizeDisplay(item);
  }

  function completedDurationText(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds <= 0) return "";
    const rounded = Math.round(seconds);
    const minutes = Math.floor(rounded / 60);
    const remainder = rounded % 60;
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const leftoverMinutes = minutes % 60;
      return `${hours}h ${String(leftoverMinutes).padStart(2, "0")}m`;
    }
    if (minutes > 0) return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
    return `${rounded}s`;
  }

  function completedMeasureTitle(item, mode) {
    if (mode === "bitrate") {
      const lines = [
        item?.output_bitrate_text ? `Output bitrate: ${item.output_bitrate_text}` : "",
        item?.source_bitrate_text ? `Source bitrate: ${item.source_bitrate_text}` : "",
        item?.bitrate_threshold_text ? `Threshold: ${item.bitrate_threshold_text}` : "",
        item?.bitrate_over_threshold !== null && item?.bitrate_over_threshold !== undefined
          ? `Over threshold: ${item.bitrate_over_threshold ? "yes" : "no"}`
          : "",
        completedDurationText(item?.duration_seconds) ? `Duration: ${completedDurationText(item.duration_seconds)}` : "",
        item?.bitrate_basis ? `Displayed from: ${String(item.bitrate_basis).replace(/_/g, " ")}` : "",
      ].filter(Boolean);
      return lines.join("\n") || "Bitrate evidence is not available for this completed row.";
    }
    const lines = [
      completedSizeDisplay(item) ? `Size: ${completedSizeDisplay(item)}` : "",
      item?.source_size_bytes ? `Source bytes: ${item.source_size_bytes}` : "",
      item?.output_size_bytes ? `Output bytes: ${item.output_size_bytes}` : "",
      item?.size_policy_limit_label ? `Policy limit: ${item.size_policy_limit_label}` : "",
      item?.size_policy_status ? `Policy status: ${item.size_policy_status}` : "",
    ].filter(Boolean);
    return lines.join("\n");
  }

  function completedRowModel(item) {
    const titleRaw = completedTvEpisodeTitle(item) || item.lookup_title || item.output_file || item.output_path || "";
    const outputFileIsDuplicate = completedComparableTitle(item.output_file)
      && (
        completedComparableTitle(item.output_file) === completedComparableTitle(titleRaw)
        || completedComparableTitle(item.output_file) === completedComparableTitle(item.lookup_title)
      );
    const metaSource = item.output_file
      ? (outputFileIsDuplicate ? "" : item.output_file)
      : (item.output_path && item.output_path !== titleRaw ? item.output_path : item.source_path || "");
    return {
      metaDisplay: completedShortPath(metaSource),
      titleDisplay: titleRaw || "(untitled output)",
      titleRaw,
    };
  }

  function appendCompletedTableCells(ctx, row, item, model) {
    const measureMode = completedColumnMode(ctx);
    ctx.appendCells(row, [
      item.completed_at || "",
      "",
      "",
      completedEvidenceText(item),
      completedMeasureDisplay(item, measureMode),
      item.publish || "",
      ctx.finalLibraryPromotionStatusText(item),
    ], [null, "completed-title-cell", "completed-route-cell", "completed-evidence-cell", "num", null, null]);
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
    const qa = item && typeof item.subtitle_qa === "object" ? item.subtitle_qa : null;
    return [
      item.primary_concern ? `Primary concern: ${item.primary_concern}` : "",
      Array.isArray(item.review_flags) && item.review_flags.length ? `Review flags: ${item.review_flags.join(", ")}` : "",
      qa ? `Subtitle QA: ${qa.posture || "unknown"} - ${qa.summary || "not reported"}` : "",
      qa?.safe_next_action ? `Subtitle QA action: ${qa.safe_next_action}` : "",
      item.consistency_guidance ? `Consistency: ${item.consistency_guidance}` : "",
      item.runtime_outcome_status ? `Runtime: ${item.runtime_outcome_status}` : "",
    ].filter(Boolean).join("\n");
  }

  function appendCompletedPlacementChip(ctx, cell, item) {
    if (!cell) return;
    const placement = ctx.completedOutputPlacement(item, ctx.state.lastCompletedPendingProofRows);
    const chip = ctx.makeStatusChip(placement.label, placement.state);
    chip.classList.add("completed-placement-chip");
    chip.title = `Placement: ${placement.label}. Durable evidence classification for completed history.`;
    if (String(cell.textContent || "").trim()) cell.appendChild(document.createElement("br"));
    cell.appendChild(chip);
  }

  function renderCompletedRow(ctx, item, rowLabel, options = {}) {
    const row = document.createElement("tr");
    const model = completedRowModel(item);
    row.dataset.status = ctx.completedDisplayRowStatus(item);
    row.dataset.rowKey = item.row_key || "";
    appendCompletedTableCells(ctx, row, item, model);

    const cells = row.querySelectorAll("td");
    const titleCell = cells[1] || row.children?.[1];
    const routeCell = cells[2] || row.children?.[2];
    const evidenceCell = cells[3] || row.children?.[3];
    const measureCell = cells[4] || row.children?.[4];
    const promotionCell = cells[6] || row.children?.[6];
    renderCompletedTitleCell(titleCell, item, model);
    if (routeCell) routeCell.appendChild(makeCompletedRouteChip(item));
    if (measureCell) {
      const measureMode = completedColumnMode(ctx);
      measureCell.dataset.measureMode = measureMode;
      measureCell.title = completedMeasureTitle(item, measureMode);
    }
    if (evidenceCell) {
      evidenceCell.title = completedEvidenceCellTitle(item);
      appendCompletedPlacementChip(ctx, evidenceCell, item);
    }
    if (typeof ctx.setCellStatusChip === "function" && ctx.finalLibraryPromotionStatusText(item)) {
      ctx.setCellStatusChip(promotionCell, ctx.finalLibraryPromotionStatusText(item), ctx.finalLibraryPromotionChipState(item));
    }
    if (options.allowPromotionAction) ctx.appendCompletedPromotionCellAction(promotionCell, item);
    ctx.makeRowSelectable(row, () => ctx.selectCompletedRow(item), {
      selected: Boolean(item.row_key && item.row_key === ctx.state.selectedCompletedRowKey),
      label: `${rowLabel} ${item.lookup_title || item.output_file || item.output_path || ""}`,
    });
    return row;
  }

  function completedRowsToRender(ctx, rows, renderLimit) {
    const rowList = Array.isArray(rows) ? rows : [];
    const limit = Number(renderLimit || 0);
    if (!limit || rowList.length <= limit) return rowList;
    const selectedKey = String(ctx.state.selectedCompletedRowKey || "");
    const selectedIndex = selectedKey
      ? rowList.findIndex((item) => String(item?.row_key || "") === selectedKey)
      : -1;
    if (selectedIndex < 0 || selectedIndex < limit) return rowList.slice(0, limit);
    return [...rowList.slice(0, Math.max(limit - 1, 0)), rowList[selectedIndex]];
  }

  function renderCompletedTableRows(ctx, { tbodyId, legendId, rows, sourceRows, emptyMessage, legendLabel, rowLabel, renderLimit = 250 }) {
    const tbody = ctx.byId(tbodyId);
    const rowList = Array.isArray(rows) ? rows : [];
    const sourceList = Array.isArray(sourceRows) ? sourceRows : [];
    if (!rowList.length) {
      ctx.clearRows(tbody, COMPLETED_TABLE_COLUMN_COUNT, sourceList.length ? "No completed rows match the filter." : emptyMessage);
      ctx.updateTableStatusLegend(legendId, tbody, legendLabel);
      return;
    }
    tbody.replaceChildren();
    const allowPromotionAction = tbodyId === "completed-rows";
    completedRowsToRender(ctx, rowList, renderLimit).forEach((item) => {
      tbody.appendChild(renderCompletedRow(ctx, item, rowLabel, { allowPromotionAction }));
    });
    ctx.updateTableStatusLegend(legendId, tbody, legendLabel);
  }

  function normalizedCompletedLibraryFilter(value) {
    return String(value || "all").trim().toLowerCase() || "all";
  }

  function completedHiddenReviewRows(ctx, allRows, visibleRows) {
    const visibleSet = new Set(Array.isArray(visibleRows) ? visibleRows : []);
    return (Array.isArray(allRows) ? allRows : []).filter((row) => {
      const status = String(ctx.completedDisplayRowStatus(row) || "").trim().toLowerCase();
      return !visibleSet.has(row) && ["blocked", "failed", "warning"].includes(status);
    }).length;
  }

  function completedSummaryLinesWithLibrary(ctx, options) {
    const lines = ctx.filterResultSummaryLines(options);
    const libraryFilter = normalizedCompletedLibraryFilter(options.libraryFilter);
    const libraryActive = libraryFilter !== "all";
    if (!libraryActive) return lines;
    const libraryLabel = ctx.completedLibraryFilterLabel(libraryFilter);
    lines[0] = String(lines[0] || "").replace("; showing ", `; library=${libraryLabel}; showing `);
    const textActive = Boolean(String(options.filterText || "").trim());
    const statusActive = String(options.statusFilter || "all").trim().toLowerCase() !== "all";
    const investigationActive = String(options.investigationFilter || "all").trim().toLowerCase() !== "all";
    if (textActive || statusActive || investigationActive) return lines;
    const noteIndex = lines.findIndex((line) => line === "Operator note: no text filter is hiding rows.");
    if (noteIndex < 0) return lines;
    const hiddenReviewRows = completedHiddenReviewRows(ctx, options.allRows, options.visibleRows);
    lines.splice(
      noteIndex,
      1,
      `Hidden review rows: ${hiddenReviewRows}.`,
      hiddenReviewRows > 0
        ? `Operator note: clear or change this filter before ${options.decisionName || "operator"} decisions; blocked/warning rows are currently hidden.`
        : "Operator note: this library filter is not hiding blocked/warning rows in the loaded payload.",
    );
    return lines;
  }

  function renderCurrentFilterSummary(ctx, currentRows, rows, filterText, statusFilter, investigationFilter, libraryFilter) {
    if (typeof ctx.filterResultSummaryLines !== "function") return;
    ctx.setText("completed-filter-summary", completedSummaryLinesWithLibrary(ctx, {
      label: "Current output filter",
      allRows: currentRows,
      visibleRows: rows,
      filterText,
      statusFilter,
      investigationFilter,
      libraryFilter,
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
    const currentRowsResult = ctx.completedCurrentRows(lastCompletedRows);
    const currentRows = Array.isArray(currentRowsResult) ? currentRowsResult : [];
    const filterText = ctx.byId("completed-filter")?.value || "";
    const statusFilter = ctx.byId("completed-status-filter")?.value || "all";
    const investigationFilter = ctx.byId("completed-investigation-filter")?.value || "all";
    const libraryFilter = ctx.syncCompletedLibraryFilterOptions(currentRows);
    const filteredRows = ctx.completedFilteredRows(currentRows, filterText, statusFilter, investigationFilter, libraryFilter);
    const rows = Array.isArray(filteredRows) ? filteredRows : [];
    const renderLimit = 250;
    const renderedCount = Math.min(rows.length, renderLimit);
    const riskStatus = ctx.completedRiskStatusLine(ctx.state.lastCompletedPayload, lastCompletedRows);
    const rowsStatus = ctx.completedRowsStatusLine(rows.length, renderedCount, currentRows.length, renderLimit);
    ctx.setText("completed-status", `${riskStatus} / ${rowsStatus}`);
    ctx.setText("completed-current-status", rowsStatus);
    renderCurrentFilterSummary(ctx, currentRows, rows, filterText, statusFilter, investigationFilter, libraryFilter);
    ctx.renderCompletedTrustDecision({
      payload: ctx.state.lastCompletedPayload,
      allRows: lastCompletedRows,
      currentRows,
      visibleRows: rows,
      proofRows: ctx.state.lastCompletedPendingProofRows,
    });
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
    ctx.renderCompletedActiveOutputContext(ctx.getSelectedCompletedRow());
    ctx.renderCompletedOutputAcceptance(ctx.state.lastCompletedPayload, lastCompletedRows, ctx.state.lastCompletedPendingProofRows);
    ctx.renderCompletedFinalTrust(ctx.state.lastCompletedPayload, lastCompletedRows, ctx.state.lastCompletedPendingProofRows, ctx.state.lastCompletedPendingPayload);
    ctx.renderCompletedPilotEvidencePacket(ctx.state.lastCompletedPayload, lastCompletedRows, ctx.state.lastCompletedPendingProofRows, ctx.state.lastCompletedPendingPayload);
    ctx.renderCompletedEvidenceCopyState();
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
      completedRouteChipCategory,
      makeCompletedRouteChip,
      completedShortPath,
      completedEvidenceText,
      completedSizeDisplay,
      completedBitrateDisplay,
      completedMeasureDisplay,
    };
  }

  window.__completedViewTableModule = {
    createCompletedTableModule,
  };
})();
