// completed/review/integrity.js
// Split child of completedView.review.js. Owns completed integrity status and evidence lines.

(function () {
  "use strict";

  function noop() {}

  function createCompletedReviewIntegrityModule(deps = {}) {
    const completedFreshnessLine = typeof deps.completedFreshnessLine === "function" ? deps.completedFreshnessLine : () => "";
    const completedFormatCounts = typeof deps.completedFormatCounts === "function" ? deps.completedFormatCounts : () => "none";
    const completedManifestIsAged = typeof deps.completedManifestIsAged === "function" ? deps.completedManifestIsAged : () => false;

    function completedRowHasIntegrityIssue(row) {
      const health = String(row?.output_health || "").trim().toLowerCase();
      return Boolean(
        row?.error ||
        row?.output_exists === false ||
        (health && !["ok", "present", "healthy"].includes(health))
      );
    }

    function completedIntegrityStatus(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      if (completed?.error) return "Unavailable";
      if (!rowList.length) return "No history";
      if (Number(completed?.size_growth_over_5_count || 0) > 0) return "Review growth";
      if (Number(completed?.missing_output_count || 0) > 0 || rowList.some(completedRowHasIntegrityIssue)) return "Review needed";
      const warnings = Array.isArray(completed?.warnings) ? completed.warnings.filter(Boolean) : [];
      if (warnings.length) return "Warnings";
      if (completedManifestIsAged(completed)) return "History aged";
      return "Healthy";
    }

    function completedIntegrityLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const issueRows = rowList.filter(completedRowHasIntegrityIssue);
      const audioDecisionTotal = rowList.reduce((total, row) => total + Number(row.audio_decision_count || 0), 0);
      const subtitleDecisionTotal = rowList.reduce((total, row) => total + Number(row.subtitle_decision_count || 0), 0);
      if (payload.error) {
        return [
          "Status: unavailable",
          `Error: ${payload.error}`,
          "Next step: open Diagnostics > Completed Manifest and Run Logs before trusting completed history.",
        ];
      }
      const lines = [
        `Manifest: ${payload.source || "not reported"}`,
        completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc),
        `Rows: ${payload.count || rowList.length || 0}`,
        `Encode/remux: ${payload.encode_count || 0} / ${payload.remux_count || 0}`,
        `Missing outputs: ${payload.missing_output_count || 0}`,
        `Size growth rows: ${payload.size_growth_count || 0}`,
        `Rows over +5% output growth: ${payload.size_growth_over_5_count || 0}`,
        `Rows without source/output size comparison: ${payload.size_unknown_count || 0}`,
        `Rows needing review: ${issueRows.length}`,
        `Operator statuses: ${completedFormatCounts(payload.operator_status_counts)}`,
        `Operator severities: ${completedFormatCounts(payload.operator_severity_counts)}`,
        `Backend open targets: ${completedFormatCounts(payload.available_open_target_counts)}`,
        `Runtime outcome matches: ${payload.runtime_outcome_match_count || 0}`,
        `Audio/subtitle decisions: ${audioDecisionTotal} / ${subtitleDecisionTotal}`,
        payload.total_output_size_text ? `Loaded output size: ${payload.total_output_size_text}` : "",
      ].filter(Boolean);
      if (warnings.length) {
        lines.push("", "Warning(s):");
        warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
      }
      lines.push("");
      if (!rowList.length) {
        lines.push("Next step: no completed-history rows are loaded. This is normal before the first successful job; otherwise open the completed manifest from Diagnostics.");
      } else if (Number(payload.size_growth_over_5_count || 0) > 0) {
        lines.push("Next step: inspect size-growth rows before using rerun results as proof of success. Growth may be expected for compatibility, but large growth needs operator review.");
      } else if (issueRows.length || Number(payload.missing_output_count || 0) > 0) {
        lines.push("Next step: inspect rows needing review before rerunning media. Use backend-selected open buttons for output folders, sidecars, and source folders.");
      } else if (warnings.length) {
        lines.push("Next step: review warnings, but loaded completed rows do not currently report missing outputs.");
      } else if (completedManifestIsAged(payload)) {
        lines.push("Next step: completed history is older than the freshness threshold. This can be normal when no jobs have run; if it conflicts with disk contents, open Completed Manifest and Run Logs before rerun.");
      } else {
        lines.push("Next step: completed outputs look healthy in the loaded manifest preview.");
      }
      lines.push("Mutation guardrail: repair, reconcile, and rerun actions must remain backend-owned commands.");
      return lines;
    }

    return {
      completedRowHasIntegrityIssue,
      completedIntegrityStatus,
      completedIntegrityLines,
    };
  }

  window.__completedViewReviewIntegrityModule = {
    createCompletedReviewIntegrityModule,
  };
})();
