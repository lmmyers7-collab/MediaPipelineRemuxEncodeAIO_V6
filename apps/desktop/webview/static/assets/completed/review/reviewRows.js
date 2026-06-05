// completed/review/reviewRows.js
// Split child of completedView.review.js. Owns completed review row reasons, board lines, digest status, and table status.

(function () {
  "use strict";

  function noopRows() { return []; }

  function createCompletedReviewRowsModule(deps = {}) {
    const completedFormatCounts = typeof deps.completedFormatCounts === "function" ? deps.completedFormatCounts : () => "none";
    const completedManifestIsAged = typeof deps.completedManifestIsAged === "function" ? deps.completedManifestIsAged : () => false;
    const completedWorkflowStatus = typeof deps.completedWorkflowStatus === "function" ? deps.completedWorkflowStatus : () => "Unknown";
    const completedHasSmallHealthySizeDelta = typeof deps.completedHasSmallHealthySizeDelta === "function" ? deps.completedHasSmallHealthySizeDelta : () => false;
    const completedPrimaryConcernIsBenign = typeof deps.completedPrimaryConcernIsBenign === "function" ? deps.completedPrimaryConcernIsBenign : () => false;
    const completedReviewFlagIsBenign = typeof deps.completedReviewFlagIsBenign === "function" ? deps.completedReviewFlagIsBenign : () => false;
    const completedRowHasIntegrityIssue = typeof deps.completedRowHasIntegrityIssue === "function" ? deps.completedRowHasIntegrityIssue : () => false;
    const completedRowHasSmallHealthySizeGrowth = typeof deps.completedRowHasSmallHealthySizeGrowth === "function" ? deps.completedRowHasSmallHealthySizeGrowth : () => false;
    const completedRowLooksHealthy = typeof deps.completedRowLooksHealthy === "function" ? deps.completedRowLooksHealthy : () => false;
    const completedRowHasBenignAlreadyProcessedOutcome = typeof deps.completedRowHasBenignAlreadyProcessedOutcome === "function" ? deps.completedRowHasBenignAlreadyProcessedOutcome : () => false;

    function completedReviewRowReasons(row) {
      const reasons = [];
      const severity = String(row?.operator_severity || "").toLowerCase();
      const consistency = String(row?.consistency_status || "").toLowerCase();
      const runtimeStatus = String(row?.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(row?.runtime_outcome_freshness_status || "").toLowerCase();
      const reviewFlags = Array.isArray(row?.review_flags) ? row.review_flags.filter((flag) => !completedReviewFlagIsBenign(flag, row)) : [];
      if (severity === "error") reasons.push("backend error severity");
      if (severity === "warning" && !completedRowHasSmallHealthySizeGrowth(row)) reasons.push("backend warning severity");
      if (row?.output_exists === false) reasons.push("missing output");
      if (row?.size_growth_over_5) reasons.push("output grew more than 5%");
      if (consistency && !["ok", "healthy", "consistent", "consistent-looking"].includes(consistency)) reasons.push(`consistency: ${row.consistency_status}`);
      if (row?.sidecar_exists === false) reasons.push("missing sidecar");
      if (Array.isArray(row?.consistency_issues) && row.consistency_issues.length) reasons.push(`consistency issues: ${row.consistency_issues.slice(0, 2).join(", ")}`);
      if (runtimeFreshness === "fresh" && ["failed", "error", "skipped", "stopped"].some((value) => runtimeStatus.includes(value))) {
        reasons.push(`fresh runtime outcome: ${row.runtime_outcome_status}`);
      }
      if (reviewFlags.length) reasons.push(`review flags: ${reviewFlags.join(", ")}`);
      if (String(row?.operator_trust_state || "").toLowerCase().includes("review") && !completedRowLooksHealthy(row)) reasons.push(`trust state: ${row.operator_trust_state}`);
      if (row?.primary_concern && !completedPrimaryConcernIsBenign(row)) reasons.push(`primary concern: ${row.primary_concern}`);
      return reasons.filter(Boolean);
    }

    function completedReviewRows(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      return rowList
        .map((row, index) => ({ row, index, reasons: completedReviewRowReasons(row) }))
        .filter((entry) => entry.reasons.length)
        .sort((a, b) => {
          const rank = (entry) => String(entry.row?.operator_severity || "").toLowerCase() === "error" ? 0
            : entry.row?.output_exists === false ? 1
              : entry.row?.size_growth_over_5 ? 2
                : String(entry.row?.operator_severity || "").toLowerCase() === "warning" ? 3
                  : 4;
          return rank(a) - rank(b) || a.index - b.index;
        });
    }

    function completedReviewStatus(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      if (payload.error) return "Diagnostics first";
      const reviewRows = completedReviewRows(payload, rowList);
      if (reviewRows.length) return `${reviewRows.length} row${reviewRows.length === 1 ? "" : "s"} need review`;
      if (!rowList.length) return "No history";
      if (completedManifestIsAged(payload)) return "History aged";
      return "No flagged rows";
    }

    function completedReviewBoardLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = completedReviewRows(payload, rowList);
      const lines = [
        "Operator review board: Completed",
        `Page status: ${completedWorkflowStatus(payload, rowList)}`,
        `Rows loaded: ${payload.count || rowList.length || 0}`,
        `Flagged rows: ${reviewRows.length}`,
        `Backend trust states: ${completedFormatCounts(payload.operator_trust_state_counts)}`,
        `Operator severities: ${completedFormatCounts(payload.operator_severity_counts)}`,
        `Runtime freshness: ${completedFormatCounts(payload.runtime_outcome_freshness_counts)}`,
        `Size growth over +5%: ${payload.size_growth_over_5_count || 0}`,
      ];
      lines.push("");
      if (payload.error) {
        lines.push("First action: open Diagnostics > Completed Manifest, Run Logs, and Last Stderr. Do not use completed history for rerun/cleanup decisions while unavailable.");
      } else if (reviewRows.length) {
        lines.push("First rows to inspect:");
        reviewRows.slice(0, 6).forEach(({ row, reasons }, index) => {
          const label = row.lookup_title || row.output_file || row.output_path || `row ${index + 1}`;
          const action = row.safe_next_action || row.operator_guidance || "select the row and use Completed Diagnostics Cross-Links before rerun or cleanup.";
          lines.push(`- ${label}: ${reasons.slice(0, 3).join("; ")}. Safe action: ${action}`);
        });
        if (reviewRows.length > 6) lines.push(`- ${reviewRows.length - 6} more flagged row(s) not shown.`);
      } else if (!rowList.length) {
        lines.push("First action: no completed rows are loaded. This is normal before first success; otherwise inspect Completed Manifest from Diagnostics.");
      } else if (completedManifestIsAged(payload)) {
        lines.push("First action: completed rows are not locally flagged, but manifest history is aged. Compare disk state with Completed Manifest and Run Logs before cleanup or rerun.");
      } else {
        lines.push("First action: no completed rows are locally flagged. Use Queue for new work and Pending Publish before rerunning missing-output cases.");
      }
      lines.push("Mutation guardrail: this board is read-only; repair, reconcile, rerun, cleanup, and file deletion remain backend-owned.");
      return lines;
    }

    function completedReviewDigestStatus(entry) {
      const row = entry?.row || {};
      const severity = String(row.operator_severity || "").toLowerCase();
      if (severity === "error" || row.output_exists === false || String(row.output_health || "").toLowerCase().includes("missing")) return "blocked";
      if (severity === "warning" || row.size_growth_over_5 || entry?.reasons?.length) return "warning";
      return "match";
    }

    function completedReviewDigestAction(row) {
      return row?.safe_next_action
        || row?.operator_guidance
        || "Select this row, compare Completed detail with Diagnostics Cross-Links, then leave repair/rerun/reconcile decisions to backend-owned workflows.";
    }

    function completedTableRowStatus(item) {
      const backendState = typeof backendRowStatusState === "function" ? backendRowStatusState(item) : "";
      const benignAlreadyProcessed = completedRowHasBenignAlreadyProcessedOutcome(item);
      if (backendState === "changed" && completedHasSmallHealthySizeDelta(item)) return "match";
      if (completedRowLooksHealthy(item) && ["", "normal", "warning", "changed", "unknown"].includes(backendState)) return "match";
      if (benignAlreadyProcessed && ["", "normal", "warning", "changed", "unknown"].includes(backendState)) return "match";
      if (backendState) return backendState;
      const severity = String(item?.operator_severity || "").toLowerCase();
      if (severity === "error" || item?.output_exists === false || completedRowHasIntegrityIssue(item)) return "blocked";
      if (benignAlreadyProcessed) return "match";
      if (severity === "warning" || item?.size_growth_over_5 || completedReviewRowReasons(item).length) return "warning";
      return "match";
    }

    return {
      completedReviewRowReasons,
      completedReviewRows,
      completedReviewStatus,
      completedReviewBoardLines,
      completedReviewDigestStatus,
      completedReviewDigestAction,
      completedTableRowStatus,
    };
  }

  window.__completedViewReviewRowsModule = {
    createCompletedReviewRowsModule,
  };
})();
