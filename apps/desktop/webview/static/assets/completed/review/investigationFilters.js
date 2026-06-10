/* eslint-disable complexity */
// completed/review/investigationFilters.js
// Split child of completedView.review.js. Owns completed investigation labels, matching, and filter visibility lines.

(function () {
  "use strict";

  function createCompletedReviewInvestigationFiltersModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const completedFilterFields = Array.isArray(deps.completedFilterFields) ? deps.completedFilterFields : [];
    const completedLibraryFilterLabel = typeof deps.completedLibraryFilterLabel === "function" ? deps.completedLibraryFilterLabel : () => "all libraries";
    const completedLibraryMatchesFilter = typeof deps.completedLibraryMatchesFilter === "function" ? deps.completedLibraryMatchesFilter : () => true;
    const completedSizeDeltaPercent = typeof deps.completedSizeDeltaPercent === "function" ? deps.completedSizeDeltaPercent : () => Number.NaN;
    const completedTableRowStatus = typeof deps.completedTableRowStatus === "function" ? deps.completedTableRowStatus : () => "unknown";
    const filterRows = typeof deps.filterRows === "function" ? deps.filterRows : null;
    const tableStatusMatchesFilter = typeof deps.tableStatusMatchesFilter === "function" ? deps.tableStatusMatchesFilter : null;
    const tableStatusFilterLabel = typeof deps.tableStatusFilterLabel === "function" ? deps.tableStatusFilterLabel : null;

    function completedInvestigationFilterLabel(value) {
      const normalized = String(value || "all").trim().toLowerCase();
      const labels = {
        all: "all signals",
        missing_output: "missing output",
        size_growth: "size growth",
        sidecar_issues: "sidecar issues",
        runtime_failed: "runtime failed",
        encode: "encode routes",
        remux: "remux routes",
        route_review: "route review",
      };
      return labels[normalized] || normalized.replace(/_/g, " ");
    }

    function completedMatchesInvestigationFilter(item, filter) {
      const normalized = String(filter || "all").trim().toLowerCase();
      const route = String(item?.route || item?.route_label || "").toLowerCase();
      const runtime = String(item?.runtime_outcome_status || "").toLowerCase();
      const runtimeError = String(item?.runtime_outcome_error_code || item?.runtime_outcome_reason || "").toLowerCase();
      const consistency = String(item?.consistency_status || item?.consistency_guidance || "").toLowerCase();
      const routeReview = String(item?.route_decision_summary || item?.route_reason || item?.route_reason_code || "").toLowerCase();
      if (!normalized || normalized === "all") return true;
      if (normalized === "missing_output") return item?.output_exists === false || String(item?.output_health || "").toLowerCase().includes("missing");
      if (normalized === "size_growth") {
        const delta = completedSizeDeltaPercent(item);
        return Boolean(
          item?.size_policy_exceeded
          || item?.size_growth_over_5
          || (Number.isFinite(delta) && delta > 1)
        );
      }
      if (normalized === "sidecar_issues") {
        return item?.sidecar_exists === false
          || Number(item?.missing_sidecar_count || 0) > 0
          || Array.isArray(item?.consistency_issues) && item.consistency_issues.some((issue) => String(issue || "").toLowerCase().includes("sidecar"))
          || consistency.includes("sidecar");
      }
      if (normalized === "runtime_failed") return ["failed", "error", "skipped", "stopped"].some((value) => runtime.includes(value) || runtimeError.includes(value));
      if (normalized === "encode") return route.includes("encode");
      if (normalized === "remux") return route.includes("remux");
      if (normalized === "route_review") return routeReview.includes("mismatch") || routeReview.includes("review") || routeReview.includes("unknown");
      return true;
    }

    function completedFocusedInvestigationLabels(item) {
      const filters = ["missing_output", "size_growth", "sidecar_issues", "runtime_failed", "encode", "remux", "route_review"];
      return filters.filter((filter) => completedMatchesInvestigationFilter(item, filter)).map(completedInvestigationFilterLabel);
    }

    function completedFilterVisibilityLines(item) {
      if (!item) return [];
      const filterText = byId("completed-filter")?.value || "";
      const statusFilter = byId("completed-status-filter")?.value || "all";
      const investigationFilter = byId("completed-investigation-filter")?.value || "all";
      const libraryFilter = byId("completed-library-filter")?.value || "all";
      const textMatches = filterRows ? filterRows([item], filterText, completedFilterFields).length > 0 : true;
      const status = completedTableRowStatus(item);
      const statusMatches = tableStatusMatchesFilter ? tableStatusMatchesFilter(status, statusFilter) : true;
      const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
      const normalizedLibrary = String(libraryFilter || "all").trim().toLowerCase();
      const investigationMatches = !normalizedInvestigation || normalizedInvestigation === "all" || completedMatchesInvestigationFilter(item, normalizedInvestigation);
      const libraryMatches = !normalizedLibrary || normalizedLibrary === "all" || completedLibraryMatchesFilter(item, normalizedLibrary);
      const activeFilters = Boolean(String(filterText || "").trim()) || String(statusFilter || "all").toLowerCase() !== "all" || normalizedInvestigation !== "all" || normalizedLibrary !== "all";
      const currentOutputPresent = item?.output_exists !== false;
      const reasons = [];
      if (!currentOutputPresent) reasons.push("not present in Current Output Status table");
      if (!textMatches) reasons.push(`text filter="${String(filterText || "").trim()}"`);
      if (!statusMatches) reasons.push(`status filter=${tableStatusFilterLabel ? tableStatusFilterLabel(statusFilter) : statusFilter}`);
      if (!investigationMatches) reasons.push(`investigation view=${completedInvestigationFilterLabel(investigationFilter)}`);
      if (!libraryMatches) reasons.push(`library=${completedLibraryFilterLabel(libraryFilter)}`);
      const lines = [
        "Current filter visibility:",
        `Selected row visible in table: ${currentOutputPresent && textMatches && statusMatches && investigationMatches && libraryMatches ? "yes" : "no"}`,
        `Active filters: ${activeFilters ? `text=${String(filterText || "").trim() || "none"}; status=${tableStatusFilterLabel ? tableStatusFilterLabel(statusFilter) : statusFilter}; view=${completedInvestigationFilterLabel(investigationFilter)}; library=${completedLibraryFilterLabel(libraryFilter)}` : "none"}`,
      ];
      if (reasons.length) {
        lines.push(`Hidden by current filters: ${reasons.join("; ")}.`);
        lines.push("Operator note: selected-row detail remains visible for review, but the table is currently hiding this row.");
      } else if (activeFilters) {
        lines.push("Operator note: this selected row is still visible under the active display filters.");
      } else {
        lines.push("Operator note: no Current Output display filter is hiding this selected row.");
      }
      return lines;
    }

    function completedSelectedQuickSignalLines(item) {
      if (!item) {
        return [
          "Selected completed-row quick signal:",
          "Select a completed row to see status, focused investigation views, and current-filter visibility.",
        ];
      }
      const focusedViews = completedFocusedInvestigationLabels(item);
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean).join(", ") : "";
      const primaryConcern = item.primary_concern
        || item.output_health
        || consistencyIssues
        || item.operator_guidance
        || item.route_decision_summary
        || "no focused output blocker reported";
      return [
        "Selected completed-row quick signal:",
        `Table status: ${completedTableRowStatus(item)}`,
        `Focused views: ${focusedViews.length ? focusedViews.join(", ") : "none beyond all signals"}`,
        `Primary concern: ${primaryConcern}`,
        ...completedFilterVisibilityLines(item),
      ];
    }

    function completedInvestigationSignalLines(item) {
      if (!item) {
        return [
          "Investigation view matches:",
          "- Select a completed row to see which Completed investigation views would include it.",
        ];
      }
      const route = String(item.route || item.route_label || "").trim();
      const runtimeProof = [item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason]
        .filter(Boolean)
        .join(" - ");
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const routeProof = [item.route_decision_summary, item.route_reason_code, item.route_reason].filter(Boolean).join(" - ");
      const signals = [];
      if (completedMatchesInvestigationFilter(item, "missing_output")) {
        signals.push(`- missing output: ${item.output_health || "completed manifest output is missing or unhealthy"}`);
      }
      if (completedMatchesInvestigationFilter(item, "size_growth")) {
        signals.push(`- size growth: ${item.size_delta_label || item.size_reduction_text || "output size increased"}`);
      }
      if (completedMatchesInvestigationFilter(item, "sidecar_issues")) {
        signals.push(`- sidecar issues: ${consistencyIssues.join(", ") || item.consistency_status || "sidecar is missing or inconsistent"}`);
      }
      if (completedMatchesInvestigationFilter(item, "runtime_failed")) {
        signals.push(`- runtime failed: ${runtimeProof || "runtime status/error indicates failure"}`);
      }
      if (completedMatchesInvestigationFilter(item, "encode")) {
        signals.push(`- encode routes: ${route || item.route_decision_summary || "route includes encode"}`);
      }
      if (completedMatchesInvestigationFilter(item, "remux")) {
        signals.push(`- remux routes: ${route || item.route_decision_summary || "route includes remux"}`);
      }
      if (completedMatchesInvestigationFilter(item, "route_review")) {
        signals.push(`- route review: ${routeProof || "route evidence needs operator review"}`);
      }
      if (!signals.length) {
        signals.push("- none beyond all signals: this row is not currently included by a focused Completed investigation view.");
      }
      signals.push("Operator note: investigation views are display filters only and do not repair manifests, accept outputs, rerun jobs, or delete files.");
      return ["Investigation view matches:", ...signals];
    }

    return {
      completedInvestigationFilterLabel,
      completedMatchesInvestigationFilter,
      completedFocusedInvestigationLabels,
      completedFilterVisibilityLines,
      completedSelectedQuickSignalLines,
      completedInvestigationSignalLines,
    };
  }

  window.__completedViewReviewInvestigationFiltersModule = {
    createCompletedReviewInvestigationFiltersModule,
  };
})();
