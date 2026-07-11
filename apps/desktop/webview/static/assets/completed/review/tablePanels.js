(function () {
  function createCompletedReviewTablePanelsModule(deps = {}) {
    const {
      appendCells, byId, clearRows, completedFormatCounts, completedFreshnessLine,
      completedHasSmallHealthySizeDelta, completedManifestIsAged, completedReviewBoardLines,
      completedReviewDigestAction, completedReviewDigestStatus, completedReviewRows, completedReviewStatus,
      completedSizeDeltaPercent, completedSizeReviewAction, completedSizeReviewLines, completedSizeReviewRows,
      completedSizeReviewStatus, makeRowSelectable, renderCompletedProofStrip, selectCompletedRow,
      setText, state, updateTableStatusLegend,
      readOnlyBoundary = "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.",
    } = deps;
    const COMPLETED_READ_ONLY_BOUNDARY = readOnlyBoundary;
    function renderCompletedReviewDigest(completed, rows) {
      const tbody = byId("completed-review-rows");
      if (!tbody) return;
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = completedReviewRows(payload, rowList).slice(0, 12);
      if (!reviewRows.length) {
        clearRows(
          tbody,
          5,
          payload.error
            ? "Completed history is unavailable. Use Diagnostics > Completed Manifest, Run Logs, and Last Stderr before rerun or cleanup."
            : rowList.length
              ? "No completed rows are flagged by the loaded backend payload. Select rows in the main table to inspect output and sidecar proof."
              : "No completed rows loaded. This is normal before the first successful job; otherwise open Completed Manifest from Diagnostics.",
        );
        updateTableStatusLegend("completed-review-legend", tbody, "Completed review rows");
        return;
      }
      tbody.replaceChildren();
      reviewRows.forEach((entry) => {
        const item = entry.row || {};
        const row = document.createElement("tr");
        row.dataset.rowKey = item.row_key || "";
        row.dataset.status = completedReviewDigestStatus(entry);
        appendCells(row, [
          item.completed_at || item.manifest_recorded_at || "",
          item.operator_trust_state || item.consistency_status || item.output_health || row.dataset.status,
          item.lookup_title || item.output_file || item.output_path || "",
          entry.reasons.slice(0, 3).join("; "),
          completedReviewDigestAction(item),
        ]);
        makeRowSelectable(row, () => selectCompletedRow(item), {
          selected: Boolean(item.row_key && item.row_key === state.selectedCompletedRowKey),
          label: `Completed review row ${item.lookup_title || item.output_file || item.output_path || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-review-legend", tbody, "Completed review rows");
    }

    function renderCompletedReviewBoard(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-review-status", completedReviewStatus(completed || {}, rowList));
      setText("completed-review-board", completedReviewBoardLines(completed || {}, rowList).join("\n"));
      renderCompletedReviewDigest(completed || {}, rowList);
    }

    function renderCompletedSizeReview(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = completedSizeReviewRows(rowList).slice(0, 20);
      setText("completed-size-review-status", completedSizeReviewStatus(payload, rowList));
      setText("completed-size-review-summary", completedSizeReviewLines(payload, rowList).join("\n"));
      const tbody = byId("completed-size-review-rows");
      if (!tbody) return;
      if (!reviewRows.length) {
        clearRows(tbody, 5, rowList.length ? "No completed rows with output growth or unknown size comparison." : "No completed rows loaded.");
        updateTableStatusLegend("completed-size-review-legend", tbody, "Completed size-growth rows");
        return;
      }
      tbody.replaceChildren();
      reviewRows.forEach(({ row: item }) => {
        const row = document.createElement("tr");
        row.dataset.status = item.size_policy_exceeded
          ? "warning"
          : item.size_growth_over_5 && !item.size_policy_available
            ? "warning"
            : completedHasSmallHealthySizeDelta(item)
              ? "match"
              : Number.isFinite(completedSizeDeltaPercent(item)) && completedSizeDeltaPercent(item) > 0
                ? "changed"
                : "unknown";
        appendCells(row, [
          item.size_delta_label || "unknown",
          item.route_decision_summary || item.route_label || item.route || "",
          item.size_policy_limit_label || item.encoder || item.encoder_kind || "",
          item.lookup_title || item.output_file || item.output_path || "",
          completedSizeReviewAction(item),
        ], ["num", null, "num", null, null]);
        makeRowSelectable(row, () => selectCompletedRow(item), {
          selected: Boolean(item.row_key && item.row_key === state.selectedCompletedRowKey),
          label: `Review completed size row ${item.lookup_title || item.output_file || item.output_path || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-size-review-legend", tbody, "Completed size-growth rows");
    }

    function completedBreakdownStatus(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      if (!rowList.length) return "No rows";
      if (Number(completed?.size_growth_over_5_count || 0) > 0) return "Growth review";
      if (Number(completed?.missing_output_count || 0) > 0) return "Output review";
      if (completedManifestIsAged(completed)) return "History aged";
      return "Loaded";
    }

    function completedBreakdownLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const decisionTotals = payload.decision_totals && typeof payload.decision_totals === "object" ? payload.decision_totals : {};
      const lines = [
        `Rows loaded: ${payload.count || rowList.length || 0}`,
        completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc),
        `Routes: ${completedFormatCounts(payload.route_counts)}`,
        `Publish states: ${completedFormatCounts(payload.publish_counts)}`,
        `Output health: ${completedFormatCounts(payload.health_counts)}`,
        `Operator statuses: ${completedFormatCounts(payload.operator_status_counts)}`,
        `Operator severities: ${completedFormatCounts(payload.operator_severity_counts)}`,
        `Media types: ${completedFormatCounts(payload.media_type_counts)}`,
        `Runtime outcomes: ${completedFormatCounts(payload.runtime_outcome_status_counts)}`,
        `Runtime outcome errors: ${completedFormatCounts(payload.runtime_outcome_error_code_counts)}`,
        `Runtime outcome freshness: ${completedFormatCounts(payload.runtime_outcome_freshness_counts)}`,
        `Decision totals: audio ${decisionTotals.audio || 0}, subtitle ${decisionTotals.subtitle || 0}`,
        `Size growth: ${payload.size_growth_count || 0}; over +5%: ${payload.size_growth_over_5_count || 0}; unknown: ${payload.size_unknown_count || 0}`,
        "Operator note: completed history is a manifest preview. Use output-integrity and Diagnostics before rerunning or deleting outputs.",
      ];
      return lines;
    }

    function renderCompletedBreakdown(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const status = completedBreakdownStatus(completed || {}, rowList);
      const lines = completedBreakdownLines(completed || {}, rowList);
      setText("completed-breakdown-status", status);
      renderCompletedProofStrip("completed-breakdown-strip", status, lines);
      setText("completed-breakdown", lines.join("\n"));
    }

    function completedRuntimeStatus(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      if (payload.error) return "Unavailable";
      if (!payload.runtime_outcome_source) return "No event source";
      if (payload.runtime_outcome_warning) return "History warning";
      if (!Number(payload.runtime_outcome_event_count || 0)) return "No recent events";
      if (!Number(payload.runtime_outcome_match_count || 0)) return rowList.length ? "No row matches" : "No rows";
      const freshness = payload.runtime_outcome_freshness_counts || {};
      if (Number(freshness.stale || 0) > 0) return "Stale matches";
      const statuses = payload.runtime_outcome_status_counts || {};
      const failed = Object.entries(statuses).some(([key, count]) => {
        const text = String(key || "").toLowerCase();
        return Number(count || 0) > 0 && (text.includes("fail") || text === "skipped" || text === "stopped");
      });
      return failed ? "Review history" : "Matched";
    }

    function completedRuntimeLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const lines = [
        `Pipeline event source: ${payload.runtime_outcome_source || "(not configured)"}`,
        `Recent events read: ${payload.runtime_outcome_event_count || 0}`,
        `Completed rows loaded: ${rowList.length}`,
        `Rows with exact source/output runtime history: ${payload.runtime_outcome_match_count || 0}`,
        `Outcome statuses: ${completedFormatCounts(payload.runtime_outcome_status_counts)}`,
        `Outcome event types: ${completedFormatCounts(payload.runtime_outcome_event_type_counts)}`,
        `Outcome error codes: ${completedFormatCounts(payload.runtime_outcome_error_code_counts)}`,
        `Outcome freshness: ${completedFormatCounts(payload.runtime_outcome_freshness_counts)}`,
      ];
      if (payload.runtime_outcome_warning) {
        lines.push("", `Warning: ${payload.runtime_outcome_warning}`);
      }
      const stale = Number((payload.runtime_outcome_freshness_counts || {}).stale || 0);
      if (stale > 0) {
        lines.push("", "Stale history is shown only as context. Inspect recent run logs before treating old runtime events as current completed-state truth.");
      }
      if (!Number(payload.runtime_outcome_event_count || 0)) {
        lines.push("", "No recent pipeline completion/failure events were available in the bounded event tail.");
      } else if (!Number(payload.runtime_outcome_match_count || 0)) {
        lines.push("", "No completed row matched recent runtime history. Matching is exact source-path first, then exact output-path if event output data exists.");
      } else {
        lines.push("", "Select a completed row to inspect the matching runtime status, error code, reason, publish state, and output path.");
      }
      lines.push(COMPLETED_READ_ONLY_BOUNDARY);
      return lines;
    }

    function renderCompletedRuntime(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const status = completedRuntimeStatus(completed || {}, rowList);
      const lines = completedRuntimeLines(completed || {}, rowList);
      setText("completed-runtime-status", status);
      renderCompletedProofStrip("completed-runtime-strip", status, lines);
      setText("completed-runtime", lines.join("\n"));
    }

    function completedConsistencyStatus(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      if (completed?.error) return "Unavailable";
      if (!rowList.length) return "No rows";
      if (Number(completed?.missing_output_count || 0) > 0) return "Broken";
      if (Number(completed?.missing_sidecar_count || 0) > 0 || Number(completed?.output_sidecar_mismatch_count || 0) > 0 || Number(completed?.stale_sidecar_count || 0) > 0) return "Review";
      return "Consistent";
    }

    function completedConsistencyLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const lines = [
        `Rows loaded: ${payload.count || rowList.length || 0}`,
        `Consistency statuses: ${completedFormatCounts(payload.consistency_status_counts)}`,
        `Consistency severities: ${completedFormatCounts(payload.consistency_severity_counts)}`,
        `Size buckets: ${completedFormatCounts(payload.size_bucket_counts)}`,
        `Missing outputs: ${payload.missing_output_count || 0}`,
        `Missing sidecars: ${payload.missing_sidecar_count || 0}`,
        `Output/sidecar mismatches: ${payload.output_sidecar_mismatch_count || 0}`,
        `Sidecars older than output: ${payload.stale_sidecar_count || 0}`,
        `Manifest rows without output path/file: ${payload.missing_manifest_output_path_count || 0}`,
      ];
      lines.push("");
      if (!rowList.length) {
        lines.push("Next step: no completed rows are loaded. This is normal before the first successful job; otherwise open Completed Manifest from Diagnostics.");
      } else if (Number(payload.missing_output_count || 0) > 0) {
        lines.push("Next step: inspect broken rows before rerun or cleanup. A completed manifest row without output is not proof of success.");
      } else if (Number(payload.missing_sidecar_count || 0) > 0 || Number(payload.output_sidecar_mismatch_count || 0) > 0 || Number(payload.stale_sidecar_count || 0) > 0) {
        lines.push("Next step: inspect sidecar consistency before rerun or library cleanup. Open backend-selected output and sidecar locations from the selected row.");
      } else {
        lines.push("Next step: loaded completed rows have matching output/sidecar consistency checks.");
      }
      lines.push(COMPLETED_READ_ONLY_BOUNDARY);
      return lines;
    }

    function renderCompletedConsistency(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const status = completedConsistencyStatus(completed || {}, rowList);
      const lines = completedConsistencyLines(completed || {}, rowList);
      setText("completed-consistency-status", status);
      renderCompletedProofStrip("completed-consistency-strip", status, lines);
      setText("completed-consistency", lines.join("\n"));
    }

    return {
      renderCompletedReviewDigest, renderCompletedReviewBoard, renderCompletedSizeReview,
      completedBreakdownStatus, completedBreakdownLines, renderCompletedBreakdown,
      completedRuntimeStatus, completedRuntimeLines, renderCompletedRuntime,
      completedConsistencyStatus, completedConsistencyLines, renderCompletedConsistency,    };
  }

  window.__completedReviewTablePanelsModule = {
    createCompletedReviewTablePanelsModule,
  };
})();
