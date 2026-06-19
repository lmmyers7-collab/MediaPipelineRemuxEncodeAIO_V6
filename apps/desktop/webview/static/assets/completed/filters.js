// completed/filters.js
// Split child of completedView.js. Loaded before completedView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  const COMPLETED_LIBRARY_UNKNOWN_VALUE = "__unknown__";

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

    function completedNormalizeLibraryFilter(value) {
      return String(value || "all").trim().toLowerCase() || "all";
    }

    function completedLibraryProfile(item) {
      return item?.library_profile && typeof item.library_profile === "object" ? item.library_profile : {};
    }

    function completedLibraryKindLabel(value) {
      const raw = String(value || "").trim();
      const normalized = raw.toLowerCase();
      if (!normalized || ["all", "auto", "unknown", "n/a", "none", "null"].includes(normalized)) return "";
      if (["movie", "movies", "film", "films"].includes(normalized)) return "Movie";
      if (["tv", "episode", "episodes", "show", "shows", "series"].includes(normalized)) return "TV";
      return raw;
    }

    function completedLibraryKindCandidates(item) {
      const profile = completedLibraryProfile(item);
      return [
        item?.library_designation,
        profile.designation,
        item?.media_kind,
        item?.media_type,
        profile.media_kind,
        profile.media_type,
      ].map(completedLibraryKindLabel).filter(Boolean);
    }

    function completedLibraryTextCandidates(item) {
      const profile = completedLibraryProfile(item);
      return [
        item?.library_id,
        item?.library_name,
        profile.library_id,
        profile.id,
        profile.library_name,
        profile.name,
        ...completedLibraryKindCandidates(item),
        item?.library_source_root,
        item?.library_output_root,
        profile.source_root,
        profile.output_root,
      ].map((value) => String(value || "").trim()).filter(Boolean);
    }

    function completedLibraryOptionKey(item) {
      const candidate = completedLibraryTextCandidates(item)[0] || "";
      return candidate ? completedNormalizeLibraryFilter(candidate) : COMPLETED_LIBRARY_UNKNOWN_VALUE;
    }

    function completedLibraryDisplayLabel(item) {
      const profile = completedLibraryProfile(item);
      return [
        item?.library_name,
        profile.library_name,
        profile.name,
        item?.library_id,
        profile.library_id,
        profile.id,
        ...completedLibraryKindCandidates(item),
      ].map((value) => String(value || "").trim()).find(Boolean) || "Unknown library";
    }

    function completedLibraryOptions(rows) {
      const optionsByValue = new Map();
      (Array.isArray(rows) ? rows : []).forEach((row) => {
        const value = completedLibraryOptionKey(row);
        if (!optionsByValue.has(value)) {
          optionsByValue.set(value, {
            label: completedLibraryDisplayLabel(row),
            value,
          });
        }
      });
      return Array.from(optionsByValue.values()).sort((left, right) => {
        if (left.value === COMPLETED_LIBRARY_UNKNOWN_VALUE) return 1;
        if (right.value === COMPLETED_LIBRARY_UNKNOWN_VALUE) return -1;
        return left.label.localeCompare(right.label);
      });
    }

    function completedLibraryMatchesFilter(item, libraryFilter) {
      const normalized = completedNormalizeLibraryFilter(libraryFilter);
      if (!normalized || normalized === "all") return true;
      return completedLibraryOptionKey(item) === normalized;
    }

    function completedLibraryFilterLabel(libraryFilter) {
      const normalized = completedNormalizeLibraryFilter(libraryFilter);
      if (!normalized || normalized === "all") return "all libraries";
      const select = byId("completed-library-filter");
      const options = select ? Array.from(select.children || []) : [];
      const option = options.find((candidate) => completedNormalizeLibraryFilter(candidate?.value) === normalized);
      return String(option?.textContent || "").trim() || (normalized === COMPLETED_LIBRARY_UNKNOWN_VALUE ? "Unknown library" : normalized);
    }

    function syncCompletedLibraryFilterOptions(rows) {
      const select = byId("completed-library-filter");
      if (!select) return "all";
      const previousValue = completedNormalizeLibraryFilter(select.value);
      const doc = select.ownerDocument || document;
      const allOption = doc.createElement("option");
      allOption.value = "all";
      allOption.textContent = "All libraries";
      const options = completedLibraryOptions(rows).map((item) => {
        const option = doc.createElement("option");
        option.value = item.value;
        option.textContent = item.label;
        return option;
      });
      select.replaceChildren(allOption, ...options);
      const availableValues = new Set(["all", ...options.map((option) => completedNormalizeLibraryFilter(option.value))]);
      select.value = availableValues.has(previousValue) ? previousValue : "all";
      return completedNormalizeLibraryFilter(select.value);
    }

    function completedFilteredRows(baseRows, filterText, statusFilter, investigationFilter, libraryFilter) {
      const sourceRows = Array.isArray(baseRows) ? baseRows : [];
      const textRows = typeof filterRows === "function" ? filterRows(sourceRows, filterText, completedFilterFields) : sourceRows;
      const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, completedDisplayRowStatus) : textRows;
      const investigationRows = typeof filterRowsByInvestigation === "function"
        ? filterRowsByInvestigation(statusRows, investigationFilter, completedMatchesInvestigationFilter)
        : statusRows;
      return investigationRows.filter((row) => completedLibraryMatchesFilter(row, libraryFilter));
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
      if (payload.stale) return false;
      if (["not_loaded", "loading", "error", "stale"].includes(status)) return false;
      return Boolean(status) || Array.isArray(payload.rows);
    }

    function renderCompletedReconciliationHint(payload, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const missingRows = completedMissingRows(rowList);
      const currentRows = completedCurrentRows(rowList);
      const missingCount = Array.isArray(missingRows) ? missingRows.length : 0;
      const reviewCount = completedReviewCount(payload, Array.isArray(currentRows) ? currentRows : []);
      const loaded = completedPublishReconciliationLoaded();
      const reconciliationPayload = state.lastPublishReconciliationPayload && typeof state.lastPublishReconciliationPayload === "object"
        ? state.lastPublishReconciliationPayload
        : {};
      const reconciliationStatus = String(reconciliationPayload.status || "").trim().toLowerCase();
      const stale = Boolean(reconciliationPayload.stale) || reconciliationStatus === "stale";
      const unloadedLabel = stale ? "stale" : "not loaded";
      if ((missingCount > 0 || reviewCount > 0) && !loaded) {
        setText("completed-reconciliation-hint", [
          `Backend publish reconciliation: ${unloadedLabel}.`,
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
        `Backend publish reconciliation: ${unloadedLabel}.`,
        "No Output blockers are visible in the loaded Completed rows. Use Advanced when final placement or Pending Publish proof matters.",
      ].join("\n"));
    }

    function resetCompletedFilters() {
      const filter = byId("completed-filter");
      const status = byId("completed-status-filter");
      const investigation = byId("completed-investigation-filter");
      const library = byId("completed-library-filter");
      if (filter) filter.value = "";
      if (status) status.value = "all";
      if (investigation) investigation.value = "all";
      if (library) library.value = "all";
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
      completedLibraryFilterLabel,
      completedLibraryMatchesFilter,
      completedReviewCount,
      completedRiskStatusLine,
      completedRowsStatusLine,
      completedPublishReconciliationLoaded,
      renderCompletedReconciliationHint,
      resetCompletedFilters,
      resetCompletedHistoryFilters,
      syncCompletedLibraryFilterOptions,
    };
  }

  window.__completedViewFiltersModule = {
    createCompletedFiltersModule,
  };
})();
