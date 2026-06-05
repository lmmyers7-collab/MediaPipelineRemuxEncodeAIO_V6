// completed/evidence/filterScope.js
// Split child of completedView.evidence.js. Computes display-filter scope evidence only.

(function () {
  "use strict";

  function createCompletedEvidenceFilterScopeModule(deps = {}) {
    const byId = deps.byId;
    const completedCurrentRows = deps.completedCurrentRows;
    const completedFilterFields = deps.completedFilterFields;
    const completedInvestigationFilterLabel = deps.completedInvestigationFilterLabel;
    const completedMatchesInvestigationFilter = deps.completedMatchesInvestigationFilter;
    const completedReviewRowReasons = deps.completedReviewRowReasons;
    const completedTableRowStatus = deps.completedTableRowStatus;
    const filterRows = deps.filterRows;
    const filterRowsByInvestigation = deps.filterRowsByInvestigation;
    const filterRowsByStatus = deps.filterRowsByStatus;
    const state = deps.state || {};
    const tableStatusFilterLabel = deps.tableStatusFilterLabel;

    function completedCurrentFilterScope(rows = state.lastCompletedRows) {
      const currentRows = typeof completedCurrentRows === "function"
        ? completedCurrentRows(rows)
        : (Array.isArray(rows) ? rows : []).filter((row) => row?.output_exists !== false);
      const allRows = Array.isArray(currentRows) ? currentRows : [];
      const filterText = byId("completed-filter")?.value || "";
      const statusFilter = byId("completed-status-filter")?.value || "all";
      const investigationFilter = byId("completed-investigation-filter")?.value || "all";
      const normalizedStatus = String(statusFilter || "all").trim().toLowerCase();
      const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
      const textRows = typeof filterRows === "function" ? filterRows(allRows, filterText, completedFilterFields) : allRows;
      const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, completedTableRowStatus) : textRows;
      const visibleRows = typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, completedMatchesInvestigationFilter) : statusRows;
      const visibleSet = new Set(visibleRows);
      const hiddenRows = allRows.filter((row) => !visibleSet.has(row));
      const hiddenBlocked = hiddenRows.filter((row) => completedTableRowStatus(row) === "blocked").length;
      const hiddenWarning = hiddenRows.filter((row) => completedTableRowStatus(row) === "warning").length;
      const hiddenReview = hiddenRows.filter((row) => completedReviewRowReasons(row).length || ["blocked", "warning"].includes(completedTableRowStatus(row))).length;
      const active = Boolean(String(filterText || "").trim())
        || (normalizedStatus && normalizedStatus !== "all")
        || (normalizedInvestigation && normalizedInvestigation !== "all");
      return {
        active,
        filterText: String(filterText || "").trim(),
        statusFilter: normalizedStatus || "all",
        statusLabel: typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter,
        investigationFilter: normalizedInvestigation || "all",
        investigationLabel: completedInvestigationFilterLabel(investigationFilter),
        totalRows: allRows.length,
        visibleRows: visibleRows.length,
        hiddenRows: hiddenRows.length,
        hiddenBlocked,
        hiddenWarning,
        hiddenReview,
        renderLimit: 250,
      };
    }

    function completedFilterScopePosture(scope) {
      if (!scope?.active) return "Read-only";
      if (scope.hiddenBlocked || scope.hiddenReview) return "Review";
      if (scope.visibleRows === 0 && scope.totalRows > 0) return "Read-first";
      return "Read-first";
    }

    function completedFilterScopeEvidence(scope) {
      return `Filters=${scope.active ? "active" : "inactive"}; visible=${scope.visibleRows}/${scope.totalRows}; hidden=${scope.hiddenRows}; hidden blocked=${scope.hiddenBlocked}; hidden review=${scope.hiddenReview}.`;
    }

    function completedFilterScopeAction(scope) {
      if (!scope.active) {
        return "No local Current Output filter is narrowing the table, but backend manifests and rerun/cleanup decisions still use backend-owned evidence.";
      }
      if (scope.hiddenBlocked || scope.hiddenReview) {
        return "Clear Current Output filters or inspect hidden review rows before accepting outputs, rerunning sources, deleting files, or cleaning up state.";
      }
      return "Treat filters as display-only search. Backend-owned actions do not receive Current Output filter state or visible-row subsets.";
    }

    function completedFilterScopeDetailLines(scope) {
      const lines = [
        "Current Output display filter / backend action scope:",
        `Text filter: ${scope.filterText || "none"}`,
        `Status filter: ${scope.statusLabel || scope.statusFilter || "all"}`,
        `Investigation view: ${scope.investigationLabel || scope.investigationFilter || "all"}`,
        `Visible rows after filters: ${scope.visibleRows} of ${scope.totalRows}`,
        `Hidden rows: ${scope.hiddenRows}; hidden blocked rows: ${scope.hiddenBlocked}; hidden warning rows: ${scope.hiddenWarning}; hidden review rows: ${scope.hiddenReview}`,
        `Render cap: first ${scope.renderLimit} visible rows are rendered when a large filtered set remains.`,
        "Backend action scope: unchanged. Current Output filters do not narrow rerun, cleanup, reconciliation, diagnostics, or manifest authority.",
        "Mutation guardrail: Current Output filters never accept outputs, suppress reruns, delete files, rewrite manifests, repair sidecars, drain pending publish, or change media policy.",
      ];
      if (scope.active && (scope.hiddenBlocked || scope.hiddenReview)) {
        lines.push("Operator warning: the current filters hide completed rows that need review, so the visible table can look safer than the backend manifest evidence.");
      } else if (scope.active) {
        lines.push("Operator note: the current filters are active for visual search only.");
      } else {
        lines.push("Operator note: no Current Output display filter is active.");
      }
      return lines;
    }

    return {
      completedCurrentFilterScope,
      completedFilterScopePosture,
      completedFilterScopeEvidence,
      completedFilterScopeAction,
      completedFilterScopeDetailLines,
    };
  }

  window.__completedViewEvidenceFilterScopeModule = {
    createCompletedEvidenceFilterScopeModule,
  };
})();
