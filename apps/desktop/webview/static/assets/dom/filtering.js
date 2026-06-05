// dom/filtering.js
// Split child of domHelpers.js. Owns generic row filtering, status count formatting, and display-filter summaries.

(function () {
  "use strict";

  function createDomFilteringModule(deps = {}) {
    const normalizedTableStatus = typeof deps.normalizedTableStatus === "function"
      ? deps.normalizedTableStatus
      : (value) => String(value || "").trim().toLowerCase() || "normal";

    function filterRows(rows, filterText, fields) {
      const needle = String(filterText || "").trim().toLowerCase();
      if (!needle) return rows;
      return rows.filter((item) => fields.some((field) => String(item[field] || "").toLowerCase().includes(needle)));
    }

    function countRowsByStatus(rows, statusOf) {
      const counts = {};
      const rowList = Array.isArray(rows) ? rows : [];
      const resolve = typeof statusOf === "function" ? statusOf : (row) => row?.status;
      rowList.forEach((row) => {
        const status = normalizedTableStatus(resolve(row));
        counts[status] = (counts[status] || 0) + 1;
      });
      return counts;
    }

    function formatStatusCounts(counts) {
      const entries = counts && typeof counts === "object" ? Object.entries(counts) : [];
      if (!entries.length) return "none";
      return entries
        .sort(([left], [right]) => String(left).localeCompare(String(right)))
        .map(([status, count]) => `${status || "normal"}=${count}`)
        .join(", ");
    }

    function tableStatusFilterLabel(value) {
      const normalized = normalizedTableStatus(value);
      if (normalized === "review") return "review only";
      if (normalized === "blocked") return "blocked/failed";
      if (normalized === "warning") return "warning";
      if (normalized === "ready") return "ready/healthy";
      return "all";
    }

    function tableStatusMatchesFilter(status, filterValue) {
      const normalized = normalizedTableStatus(status);
      const filter = normalizedTableStatus(filterValue);
      if (!filter || filter === "all" || filter === "normal") return true;
      if (filter === "review") return ["blocked", "failed", "warning", "unknown"].includes(normalized);
      if (filter === "blocked") return ["blocked", "failed"].includes(normalized);
      if (filter === "ready") return ["ready", "match"].includes(normalized);
      return normalized === filter;
    }

    function filterRowsByStatus(rows, statusFilter, statusOf) {
      const rowList = Array.isArray(rows) ? rows : [];
      const resolve = typeof statusOf === "function" ? statusOf : (row) => row?.status;
      return rowList.filter((row) => tableStatusMatchesFilter(resolve(row), statusFilter));
    }

    function tableInvestigationFilterLabel(value) {
      const normalized = normalizedTableStatus(value);
      if (!normalized || normalized === "all" || normalized === "normal") return "all";
      return normalized.replace(/_/g, " ");
    }

    function filterRowsByInvestigation(rows, investigationFilter, matchesFilter) {
      const rowList = Array.isArray(rows) ? rows : [];
      const filter = normalizedTableStatus(investigationFilter);
      if (!filter || filter === "all" || typeof matchesFilter !== "function") return rowList;
      return rowList.filter((row) => matchesFilter(row, filter));
    }

    function filterResultSummaryLines(options = {}) {
      const label = options.label || "Filter";
      const allRows = Array.isArray(options.allRows) ? options.allRows : [];
      const visibleRows = Array.isArray(options.visibleRows) ? options.visibleRows : [];
      const filterText = String(options.filterText || "").trim();
      const statusFilter = String(options.statusFilter || "all").trim() || "all";
      const investigationFilter = String(options.investigationFilter || "all").trim() || "all";
      const investigationLabel = options.investigationLabel || tableInvestigationFilterLabel(investigationFilter);
      const statusOf = typeof options.statusOf === "function" ? options.statusOf : (row) => row?.status;
      const reviewStatuses = new Set(
        (Array.isArray(options.reviewStatuses) ? options.reviewStatuses : ["blocked", "failed", "warning"])
          .map((value) => normalizedTableStatus(value)),
      );
      const visibleSet = new Set(visibleRows);
      const hiddenReviewRows = allRows.filter((row) => {
        return !visibleSet.has(row) && reviewStatuses.has(normalizedTableStatus(statusOf(row)));
      }).length;
      const decisionName = options.decisionName || "operator";
      const lines = [
        `${label}: text=${filterText ? `"${filterText}"` : "none"}; status=${tableStatusFilterLabel(statusFilter)}; view=${investigationLabel}; showing ${visibleRows.length} of ${allRows.length} row${allRows.length === 1 ? "" : "s"}.`,
        `Visible status mix: ${formatStatusCounts(countRowsByStatus(visibleRows, statusOf))}.`,
      ];
      if (filterText || normalizedTableStatus(statusFilter) !== "all" || normalizedTableStatus(investigationFilter) !== "all") {
        lines.push(`Hidden review rows: ${hiddenReviewRows}.`);
        if (hiddenReviewRows > 0) {
          lines.push(`Operator note: clear or change this filter before ${decisionName} decisions; blocked/warning rows are currently hidden.`);
        } else {
          lines.push(`Operator note: this filter is not hiding blocked/warning rows in the loaded payload.`);
        }
      } else {
        lines.push("Operator note: no text filter is hiding rows.");
      }
      const limit = Number(options.limit || 0);
      if (limit > 0 && visibleRows.length > limit) {
        lines.push(`Display cap: only the first ${limit} filtered rows are rendered. Refine the filter or use backend diagnostics before acting on row counts.`);
      }
      lines.push(options.guardrail || "Mutation guardrail: filters are display-only and never change backend command scope.");
      return lines;
    }

    return {
      filterRows,
      countRowsByStatus,
      formatStatusCounts,
      tableStatusFilterLabel,
      tableStatusMatchesFilter,
      filterRowsByStatus,
      tableInvestigationFilterLabel,
      filterRowsByInvestigation,
      filterResultSummaryLines,
    };
  }

  window.__domFilteringModule = {
    createDomFilteringModule,
  };
})();
