// completed/review/sizeReview.js
// Split child of completedView.review.js. Owns completed size delta and size-growth review helpers.

(function () {
  "use strict";

  function noop() { return []; }

  function createCompletedReviewSizeReviewModule(deps = {}) {
    const completedRowHasIntegrityIssue = typeof deps.completedRowHasIntegrityIssue === "function" ? deps.completedRowHasIntegrityIssue : () => false;
    const completedReviewRowReasons = typeof deps.completedReviewRowReasons === "function" ? deps.completedReviewRowReasons : noop;

    function completedSizeDeltaPercent(item) {
      if (typeof item?.size_delta_percent === "number") return Number(item.size_delta_percent);
      return Number.parseFloat(String(item?.size_delta_label || "").replace("%", ""));
    }

    function completedHasSmallHealthySizeDelta(item) {
      const delta = completedSizeDeltaPercent(item);
      if (!Number.isFinite(delta) || Math.abs(delta) > 1) return false;
      const severity = String(item?.operator_severity || "").toLowerCase();
      return item?.output_exists !== false
        && severity !== "warning"
        && severity !== "error"
        && !item?.size_growth_over_5
        && !item?.size_policy_exceeded
        && !completedRowHasIntegrityIssue(item)
        && completedReviewRowReasons(item).length === 0;
    }

    function completedSizeReviewRows(rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      return rowList
        .map((row, index) => ({ row, index }))
        .filter(({ row }) => {
          const delta = completedSizeDeltaPercent(row);
          return row?.size_policy_exceeded
            || row?.size_growth_over_5
            || (Number.isFinite(delta) && delta > 0 && !completedHasSmallHealthySizeDelta(row))
            || !Number.isFinite(delta);
        })
        .sort((left, right) => {
          const delta = (entry) => Number.isFinite(completedSizeDeltaPercent(entry.row)) ? completedSizeDeltaPercent(entry.row) : -Infinity;
          const rank = (entry) => entry.row?.size_policy_exceeded ? 0 : entry.row?.size_growth_over_5 && !entry.row?.size_policy_available ? 1 : Number.isFinite(completedSizeDeltaPercent(entry.row)) && completedSizeDeltaPercent(entry.row) > 0 ? 2 : 3;
          return rank(left) - rank(right) || delta(right) - delta(left) || left.index - right.index;
        });
    }

    function completedSizeReviewStatus(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      if (payload.error) return "Diagnostics first";
      if (!rowList.length) return "No history";
      if (Number(payload.size_policy_blocked_count || 0) > 0) return "Policy blocked";
      if (Number(payload.size_policy_exceeded_count || 0) > 0) return "Policy exceeded";
      if (Number(payload.size_policy_within_limit_count || 0) > 0 && Number(payload.size_growth_count || 0) > 0) return "Within size policy";
      if (Number(payload.size_growth_over_5_count || 0) > 0) return "Legacy growth >+5%";
      if (!completedSizeReviewRows(rowList).length && rowList.some(completedHasSmallHealthySizeDelta)) return "Neutral +/-1%";
      if (Number(payload.size_growth_count || 0) > 0) return "Growth under +5%";
      if (Number(payload.size_unknown_count || 0) > 0) return "Unknown size";
      return "No growth";
    }

    function completedSizeReviewAction(row) {
      if (!row) return "Select a completed row before using backend-selected open actions.";
      if (row.size_policy_exceeded) {
        return row.safe_next_action || "Compare sidecar size_policy, route metadata, encoder choice, Run Logs, and Last Stderr before accepting this output.";
      }
      if (row.size_policy_available && typeof row.size_delta_percent === "number" && row.size_delta_percent > 0) {
        return "Output grew but stayed within the recorded backend size_policy. Compare route reason if the growth is surprising.";
      }
      if (row.size_growth_over_5) {
        return row.safe_next_action || "Compare source/output size, route metadata, encoder choice, Run Logs, and Last Stderr before accepting this output; no backend size_policy was recorded.";
      }
      if (Number.isFinite(completedSizeDeltaPercent(row)) && completedSizeDeltaPercent(row) > 0) {
        return "Small growth can be normal for compatibility, subtitles, or audio normalization; compare route reason before rerun.";
      }
      return "Size comparison is missing. Open Completed Manifest and Run Logs before trusting this row as shrink/remux proof.";
    }

    function completedSizeReviewLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = completedSizeReviewRows(rowList);
      const policyExceeded = reviewRows.filter(({ row }) => row?.size_policy_exceeded).length;
      const policyAllowed = reviewRows.filter(({ row }) => row?.size_policy_available && !row?.size_policy_exceeded && Number.isFinite(completedSizeDeltaPercent(row)) && completedSizeDeltaPercent(row) > 0).length;
      const legacyOverFive = reviewRows.filter(({ row }) => row?.size_growth_over_5 && !row?.size_policy_available).length;
      const positive = reviewRows.filter(({ row }) => Number.isFinite(completedSizeDeltaPercent(row)) && completedSizeDeltaPercent(row) > 0 && !row.size_policy_exceeded && !row.size_growth_over_5).length;
      const unknown = reviewRows.filter(({ row }) => !Number.isFinite(completedSizeDeltaPercent(row))).length;
      const neutralSmall = rowList.filter(completedHasSmallHealthySizeDelta).length;
      const lines = [
        "Size growth review board:",
        `Rows loaded: ${payload.count || rowList.length || 0}`,
        `Recorded size policy exceeded: ${policyExceeded}`,
        `Growth within recorded size policy: ${policyAllowed}`,
        `Legacy growth over +5% without size_policy: ${legacyOverFive}`,
        `Growth 0..5% or unclassified growth: ${positive}`,
        `Healthy +/-1% deltas treated as neutral: ${neutralSmall}`,
        `Unknown source/output comparison: ${unknown}`,
        `Size policy modes: ${typeof window.formatStatusCounts === "function" ? window.formatStatusCounts(payload.size_policy_mode_counts) : "none"}`,
      ];
      if (payload.error) {
        lines.push("First action: open Diagnostics > Completed Manifest and Run Logs; completed size history is unavailable.");
      } else if (!rowList.length) {
        lines.push("First action: no completed rows are loaded. This is normal before the first successful job.");
      } else if (policyExceeded > 0) {
        lines.push("First action: select rows that exceeded recorded size_policy and compare route reason, encoder, output, Run Logs, and Last Stderr before accepting the result.");
      } else if (legacyOverFive > 0) {
        lines.push("First action: select legacy +5% growth rows; no recorded size_policy was available, so compare route/log evidence before acceptance.");
      } else if (policyAllowed > 0) {
        lines.push("First action: growth rows stayed within backend size_policy; verify route reason only if the size increase is surprising.");
      } else if (positive > 0) {
        lines.push("First action: small growth rows are listed for review; confirm compatibility or subtitle/audio changes explain the delta.");
      } else if (unknown > 0) {
        lines.push("First action: size fields are missing for some rows; inspect manifest/schema before using size as proof of success.");
      } else {
        lines.push("First action: no loaded completed rows report output growth.");
      }
      lines.push("Mutation guardrail: this board is read-only; rerun, repair, delete, and manifest reconciliation remain backend-owned.");
      return lines;
    }

    return {
      completedSizeDeltaPercent,
      completedHasSmallHealthySizeDelta,
      completedSizeReviewRows,
      completedSizeReviewStatus,
      completedSizeReviewAction,
      completedSizeReviewLines,
    };
  }

  window.__completedViewReviewSizeReviewModule = {
    createCompletedReviewSizeReviewModule,
  };
})();
