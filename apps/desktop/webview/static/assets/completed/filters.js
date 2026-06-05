// completed/filters.js
// Split child of completedView.js. Loaded before completedView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  function createCompletedFiltersModule({
    byId,
    completedCurrentRows,
    completedFilterFields,
    completedInvestigationFilterLabel,
    completedMatchesInvestigationFilter,
    completedMissingRows,
    completedReviewRows,
    completedReviewRowReasons,
    completedTableRowStatus,
    filterRows,
    filterRowsByInvestigation,
    filterRowsByStatus,
    renderCompletedRows,
    setText,
    state,
  } = {}) {
    completedCurrentRows = typeof completedCurrentRows === "function" ? completedCurrentRows : function (rows) { return Array.isArray(rows) ? rows : []; };
    completedFilterFields = Array.isArray(completedFilterFields) ? completedFilterFields : [];
    completedInvestigationFilterLabel = typeof completedInvestigationFilterLabel === "function" ? completedInvestigationFilterLabel : function () { return ""; };
    completedMatchesInvestigationFilter = typeof completedMatchesInvestigationFilter === "function" ? completedMatchesInvestigationFilter : function () { return true; };
    completedMissingRows = typeof completedMissingRows === "function" ? completedMissingRows : function (rows) {
      return (Array.isArray(rows) ? rows : []).filter((row) => row?.output_exists === false && !row?.promoted_cleaned);
    };
    completedReviewRows = typeof completedReviewRows === "function" ? completedReviewRows : function () { return []; };
    completedReviewRowReasons = typeof completedReviewRowReasons === "function" ? completedReviewRowReasons : function () { return []; };
    completedTableRowStatus = typeof completedTableRowStatus === "function" ? completedTableRowStatus : function () { return "normal"; };
    renderCompletedRows = typeof renderCompletedRows === "function" ? renderCompletedRows : function () {};
    setText = typeof setText === "function" ? setText : function () {};
    state = state && typeof state === "object" ? state : {};

    function completedFilteredRows(baseRows, filterText, statusFilter, investigationFilter) {
      const sourceRows = Array.isArray(baseRows) ? baseRows : [];
      const textRows = typeof filterRows === "function" ? filterRows(sourceRows, filterText, completedFilterFields) : sourceRows;
      const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, completedDisplayRowStatus) : textRows;
      return typeof filterRowsByInvestigation === "function"
        ? filterRowsByInvestigation(statusRows, investigationFilter, completedMatchesInvestigationFilter)
        : statusRows;
    }

    function completedReviewReasonsForDisplay(item) {
      const reasons = completedReviewRowReasons(item);
      return Array.isArray(reasons) ? reasons.filter(Boolean) : [];
    }

    function completedDisplayRowStatus(item) {
      const status = String(completedTableRowStatus(item) || "normal").toLowerCase();
      const reasons = completedReviewReasonsForDisplay(item);
      if (item?.output_exists === false) return "blocked";
      if (["warning", "changed", "ready", "completed", "match", "normal"].includes(status) && !reasons.length) return "match";
      return status;
    }

    function completedReviewCount(payload, rows) {
      const reviewRows = completedReviewRows(payload || {}, Array.isArray(rows) ? rows : []);
      return Array.isArray(reviewRows) ? reviewRows.length : 0;
    }

    function completedRiskStatusLine(payload, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const missingRows = completedMissingRows(rowList);
      const currentRows = completedCurrentRows(rowList);
      const missingCount = Array.isArray(missingRows) ? missingRows.length : 0;
      const reviewCount = completedReviewCount(payload, Array.isArray(currentRows) ? currentRows : []);
      if (missingCount > 0) return `${missingCount} missing from expected destination`;
      if (reviewCount > 0) return `${reviewCount} current output${reviewCount === 1 ? "" : "s"} need review`;
      return "No current output blockers";
    }

    function completedRowsStatusLine(visibleRows, renderedRows, totalRows, renderLimit) {
      if (visibleRows > renderLimit) {
        return `${renderedRows} shown / ${visibleRows} filtered / ${totalRows} rows`;
      }
      return `${visibleRows} / ${totalRows} row${totalRows === 1 ? "" : "s"}`;
    }

    function completedPublishReconciliationLoaded() {
      const payload = state.lastPublishReconciliationPayload && typeof state.lastPublishReconciliationPayload === "object"
        ? state.lastPublishReconciliationPayload
        : {};
      const status = String(payload.status || "").trim().toLowerCase();
      return Boolean(status && status !== "not_loaded") || Array.isArray(payload.rows);
    }

    function renderCompletedReconciliationHint(payload, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const missingRows = completedMissingRows(rowList);
      const currentRows = completedCurrentRows(rowList);
      const missingCount = Array.isArray(missingRows) ? missingRows.length : 0;
      const reviewCount = completedReviewCount(payload, Array.isArray(currentRows) ? currentRows : []);
      const loaded = completedPublishReconciliationLoaded();
      if ((missingCount > 0 || reviewCount > 0) && !loaded) {
        setText("completed-reconciliation-hint", [
          "Backend publish reconciliation: not loaded.",
          `Output risk: ${completedRiskStatusLine(payload, rowList)}.`,
          "Safe next step: use Advanced -> Refresh Backend Reconciliation before rerun, cleanup, drain, deletion, or library decisions.",
          "Boundary: this hint is read-only and does not refresh, repair, publish, drain, rerun, rewrite manifests, or touch media.",
        ].join("\n"));
        return;
      }
      if (loaded) {
        const status = state.lastPublishReconciliationPayload?.status || "loaded";
        setText("completed-reconciliation-hint", [
          `Backend publish reconciliation: ${status}.`,
          "Use Advanced for Completed/Pending/drain-summary proof details before rerun, cleanup, or drain decisions.",
        ].join("\n"));
        return;
      }
      setText("completed-reconciliation-hint", [
        "Backend publish reconciliation: not loaded.",
        "No Output blockers are visible in the loaded Completed rows. Use Advanced when final placement or Pending Publish proof matters.",
      ].join("\n"));
    }

    function resetCompletedFilters() {
      const filter = byId("completed-filter");
      const status = byId("completed-status-filter");
      const investigation = byId("completed-investigation-filter");
      if (filter) filter.value = "";
      if (status) status.value = "all";
      if (investigation) investigation.value = "all";
      renderCompletedRows();
      setText("completed-open-status", "Current Output Status filters cleared. Backend manifest, rerun, cleanup, and reconcile scopes are unchanged.");
    }

    function resetCompletedHistoryFilters() {
      const filter = byId("completed-history-filter");
      const status = byId("completed-history-status-filter");
      const investigation = byId("completed-history-investigation-filter");
      if (filter) filter.value = "";
      if (status) status.value = "all";
      if (investigation) investigation.value = "all";
      renderCompletedRows();
      setText("completed-open-status", "Completed History filters cleared. Backend manifest, rerun, cleanup, and reconcile scopes are unchanged.");
    }

    return {
      completedDisplayRowStatus,
      completedFilteredRows,
      completedReviewCount,
      completedRiskStatusLine,
      completedRowsStatusLine,
      completedPublishReconciliationLoaded,
      renderCompletedReconciliationHint,
      resetCompletedFilters,
      resetCompletedHistoryFilters,
    };
  }

  window.__completedViewFiltersModule = {
    createCompletedFiltersModule,
  };
})();
