(function () {
  function createPendingPublishFiltersModule(deps = {}) {
    const {
      backendRowStatusState = null,
      byId = function () { return null; },
      filterRows = function (rows) { return Array.isArray(rows) ? rows : []; },
      pendingFilterFields = [],
      pendingReviewRowReasons = function () { return []; },
      tableStatusFilterLabel = function (value) { return String(value || "all"); },
      tableStatusMatchesFilter = function () { return true; },
    } = deps;

function pendingTableRowStatus(item) {
    const severity = String(item?.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item?.drain_recommendation || "").toLowerCase();
    const state = String(item?.state || item?.diagnostic_status || "").toLowerCase();
    if (recommendation === "do_not_drain" || item?.local_exists === false) return "blocked";
    if (severity === "error" || item?.error) return "failed";
    if (
      severity === "warning"
      || item?.ready_to_drain === false
      || Number(item?.missing_sidecar_count || 0) > 0
      || state.includes("orphan_payload")
      || pendingReviewRowReasons(item).length
    ) return "warning";
    const backendState = typeof backendRowStatusState === "function" ? backendRowStatusState(item) : "";
    if (backendState) return backendState;
    return "match";
  }

function pendingInvestigationFilterLabel(value) {
    const normalized = String(value || "all").trim().toLowerCase();
    const labels = {
      all: "all signals",
      do_not_drain: "do not drain",
      missing_payload: "missing payload",
      invalid_manifest: "invalid manifest",
      missing_sidecars: "missing sidecars",
      evidence_missing: "evidence missing",
      orphan_payload: "orphan payload",
      ready_to_drain: "ready to drain",
      drained: "drained",
      failed: "failed",
    };
    return labels[normalized] || normalized.replace(/_/g, " ");
  }

function pendingMatchesInvestigationFilter(item, filter) {
    const normalized = String(filter || "all").trim().toLowerCase();
    const state = String(item?.state || item?.diagnostic_status || "").toLowerCase();
    const recommendation = String(item?.drain_recommendation || "").toLowerCase();
    const severity = String(item?.diagnostic_severity || "").toLowerCase();
    if (!normalized || normalized === "all") return true;
    if (normalized === "do_not_drain") return recommendation === "do_not_drain" || pendingTableRowStatus(item) === "blocked";
    if (normalized === "missing_payload") return item?.local_exists === false || Number(item?.missing_local_count || 0) > 0 || state.includes("missing");
    if (normalized === "invalid_manifest") return state.includes("invalid_manifest") || state.includes("unreadable_manifest") || String(item?.error || "").toLowerCase().includes("manifest");
    if (normalized === "missing_sidecars") return Number(item?.missing_sidecar_count || 0) > 0;
    if (normalized === "evidence_missing") {
      return item?.local_exists === false
        || Number(item?.missing_local_count || 0) > 0
        || Number(item?.missing_sidecar_count || 0) > 0
        || state.includes("invalid_manifest")
        || state.includes("unreadable_manifest")
        || String(item?.error || "").toLowerCase().includes("manifest");
    }
    if (normalized === "orphan_payload") return state.includes("orphan_payload");
    if (normalized === "ready_to_drain") {
      const rowStatus = pendingTableRowStatus(item);
      return item?.ready_to_drain !== false && recommendation !== "do_not_drain" && ["match", "ready"].includes(rowStatus);
    }
    if (normalized === "drained") {
      const rowStatus = pendingTableRowStatus(item);
      return rowStatus === "completed" || ["completed", "published", "succeeded", "already_published"].some((value) => state.includes(value));
    }
    if (normalized === "failed") {
      return pendingTableRowStatus(item) === "failed" || severity === "error" || Boolean(item?.error);
    }
    return true;
  }

function pendingFocusedInvestigationLabels(item) {
    const filters = ["do_not_drain", "failed", "missing_payload", "invalid_manifest", "missing_sidecars", "orphan_payload", "evidence_missing", "ready_to_drain", "drained"];
    return filters.filter((filter) => pendingMatchesInvestigationFilter(item, filter)).map(pendingInvestigationFilterLabel);
  }

function pendingFilterVisibilityLines(item) {
    if (!item) return [];
    const filterText = byId("pending-filter")?.value || "";
    const statusFilter = byId("pending-status-filter")?.value || "all";
    const investigationFilter = byId("pending-investigation-filter")?.value || "all";
    const textMatches = typeof filterRows === "function" ? filterRows([item], filterText, pendingFilterFields).length > 0 : true;
    const status = pendingTableRowStatus(item);
    const statusMatches = typeof tableStatusMatchesFilter === "function" ? tableStatusMatchesFilter(status, statusFilter) : true;
    const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
    const investigationMatches = !normalizedInvestigation || normalizedInvestigation === "all" || pendingMatchesInvestigationFilter(item, normalizedInvestigation);
    const activeFilters = Boolean(String(filterText || "").trim()) || String(statusFilter || "all").toLowerCase() !== "all" || normalizedInvestigation !== "all";
    const reasons = [];
    if (!textMatches) reasons.push(`text filter="${String(filterText || "").trim()}"`);
    if (!statusMatches) reasons.push(`status filter=${typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter}`);
    if (!investigationMatches) reasons.push(`investigation view=${pendingInvestigationFilterLabel(investigationFilter)}`);
    const lines = [
      "Current filter visibility:",
      `Selected row visible in table: ${textMatches && statusMatches && investigationMatches ? "yes" : "no"}`,
      `Active filters: ${activeFilters ? `text=${String(filterText || "").trim() || "none"}; status=${typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter}; view=${pendingInvestigationFilterLabel(investigationFilter)}` : "none"}`,
    ];
    if (reasons.length) {
      lines.push(`Hidden by current filters: ${reasons.join("; ")}.`);
      lines.push("Operator note: selected-row detail remains visible for review, but the table is currently hiding this row.");
    } else if (activeFilters) {
      lines.push("Operator note: this selected row is still visible under the active display filters.");
    } else {
      lines.push("Operator note: no Pending Publish display filter is hiding this selected row.");
    }
    return lines;
  }

function pendingSelectedQuickSignalLines(item) {
    if (!item) {
      return [
        "Selected pending-row quick signal:",
        "Select a pending publish row to see status, focused investigation views, and current-filter visibility.",
      ];
    }
    const focusedViews = pendingFocusedInvestigationLabels(item);
    const primaryConcern = item.primary_concern
      || item.issue_summary
      || item.error
      || item.operator_guidance
      || item.drain_recommendation
      || "no focused pending-publish blocker reported";
    return [
      "Selected pending-row quick signal:",
      `Table status: ${pendingTableRowStatus(item)}`,
      `Focused views: ${focusedViews.length ? focusedViews.join(", ") : "none beyond all signals"}`,
      `Primary concern: ${primaryConcern}`,
      ...pendingFilterVisibilityLines(item),
    ];
  }

function pendingInvestigationSignalLines(item) {
    if (!item) {
      return [
        "Investigation view matches:",
        "- Select a pending publish row to see which Pending Publish investigation views would include it.",
      ];
    }
    const state = String(item.state || item.diagnostic_status || "").trim();
    const signals = [];
    if (pendingMatchesInvestigationFilter(item, "do_not_drain")) {
      signals.push(`- do not drain: ${item.drain_recommendation || item.diagnostic_severity || item.error || "backend marked row unsafe to drain"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "missing_payload")) {
      signals.push(`- missing payload: ${item.local_file || item.issue_summary || "local parked payload is missing"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "invalid_manifest")) {
      signals.push(`- invalid manifest: ${item.manifest_path || item.error || state || "manifest is invalid or unreadable"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "missing_sidecars")) {
      signals.push(`- missing sidecars: ${item.missing_sidecar_count || "reported by pending scan"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "orphan_payload")) {
      signals.push(`- orphan payload: ${item.local_file || state || "payload exists without a valid manifest"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "failed")) {
      signals.push(`- failed: ${item.error || item.diagnostic_severity || item.diagnostic_status || "backend reported a failed pending-publish signal"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "ready_to_drain")) {
      signals.push(`- ready to drain: ${item.drain_recommendation || "row has no focused blocker in the loaded pending scan"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "drained")) {
      signals.push(`- drained: ${item.diagnostic_status || item.state || "backend reported completed publish evidence"}`);
    }
    if (!signals.length) {
      signals.push("- none beyond all signals: this row is not currently included by a focused Pending Publish investigation view.");
    }
    signals.push("Operator note: investigation views are display filters only and do not change backend drain scope.");
    return ["Investigation view matches:", ...signals];
  }

    return {
      pendingTableRowStatus,
      pendingInvestigationFilterLabel,
      pendingMatchesInvestigationFilter,
      pendingFocusedInvestigationLabels,
      pendingFilterVisibilityLines,
      pendingSelectedQuickSignalLines,
      pendingInvestigationSignalLines,
    };
  }

  window.__pendingPublishFiltersModule = {
    createPendingPublishFiltersModule,
  };
})();
