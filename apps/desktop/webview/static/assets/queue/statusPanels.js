(function () {
  function createQueueStatusPanelsModule(deps = {}) {
    const {
      appendCells = () => {},
      byId = () => null,
      clearRows = () => {},
      documentRef = document,
      getSelectedQueueExcludedRowKey = () => "",
      makeRowSelectable = () => {},
      queueFormatCounts = () => "",
      queueExcludedRowKey = () => "",
      queueFreshnessLine = () => "",
      queueHiddenSidecarLine = () => "",
      queueSnapshotIsStale = () => false,
      readOnlyBoundary = "",
      selectQueueExcludedRow = () => {},
      setText = () => {},
      updateTableStatusLegend = () => {},
    } = deps;
    const _queueNoop = () => {};

    function queuePayloadNumber(payload, key, fallback = 0) {
      if (payload && Object.prototype.hasOwnProperty.call(payload, key)) {
        const value = Number(payload[key]);
        return Number.isFinite(value) ? Math.max(0, value) : 0;
      }
      const fallbackValue = Number(fallback);
      return Number.isFinite(fallbackValue) ? Math.max(0, fallbackValue) : 0;
    }

    function queuePayloadRunnableCount(payload, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      return queuePayloadNumber(payload, "runnable_count", rowList.length);
    }

    function queueBreakdownStatus(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      if (queue?.error) return "Unavailable";
      if (!rowList.length) return "No rows";
      if (Number(queue?.invalid_row_count || 0) > 0 || rowList.some((row) => String(row?.status || "").toLowerCase() === "invalid")) return "Snapshot review";
      if (Number(queue?.priority_visible_count || 0) > 0) return "Priority visible";
      return "Loaded";
    }

    function queueBreakdownLines(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const lines = [
        `Rows loaded: ${rowList.length}`,
        queueHiddenSidecarLine(payload),
        queueFreshnessLine("Snapshot file age", payload.snapshot_file_age_text, payload.snapshot_file_freshness_status, payload.snapshot_file_mtime_utc),
        queueFreshnessLine("Produced age", payload.produced_age_text, payload.produced_freshness_status),
        `Runnable rows: ${queuePayloadRunnableCount(payload, rowList)}`,
        `Visible size: ${payload.total_visible_size_text || "0.00 GB"}`,
        `Invalid snapshot rows: ${payload.invalid_row_count || 0}`,
        `Visible priority rows: ${payload.priority_visible_count || 0}`,
        `Snapshot priority count: ${payload.priority_count || 0}`,
        `Routes: ${queueFormatCounts(payload.route_counts)}`,
        `Route reasons: ${queueFormatCounts(payload.route_reason_counts)}`,
        `Operator statuses: ${queueFormatCounts(payload.operator_status_counts)}`,
        `Operator severities: ${queueFormatCounts(payload.operator_severity_counts)}`,
        `Phases: ${queueFormatCounts(payload.phase_counts)}`,
        `Media types: ${queueFormatCounts(payload.media_type_counts)}`,
        `Seasons: ${queueFormatCounts(payload.season_counts)}`,
        `Priority reasons: ${queueFormatCounts(payload.priority_reason_counts)}`,
        `Source roots: ${queueFormatCounts(payload.source_root_counts)}`,
        `Visible blocked reason codes: ${queueFormatCounts(payload.blocked_reason_code_counts)}`,
        `Visible blocked reasons: ${queueFormatCounts(payload.blocked_reason_counts)}`,
        `Runtime deferred checks: ${queueFormatCounts(payload.runtime_check_code_counts)}`,
        `Runtime outcomes: ${queueFormatCounts(payload.runtime_outcome_status_counts)}`,
        `Runtime outcome errors: ${queueFormatCounts(payload.runtime_outcome_error_code_counts)}`,
        `Runtime outcome freshness: ${queueFormatCounts(payload.runtime_outcome_freshness_counts)}`,
        `Excluded reasons: ${queueFormatCounts(payload.excluded_reason_counts)}`,
        `Excluded media types: ${queueFormatCounts(payload.excluded_media_type_counts)}`,
      ];
      if (payload.invalid_row_count) {
        lines.push("", "Operator note: invalid snapshot rows are ignored by processing until the backend can parse them. Refresh the queue preview before launching unattended work.");
      } else {
        lines.push("", "Operator note: this is a read-only snapshot breakdown. Launch and queue mutation remain backend-owned.");
      }
      return lines;
    }

    function renderQueueBreakdown(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("queue-breakdown-status", queueBreakdownStatus(queue || {}, rowList));
      setText("queue-breakdown", queueBreakdownLines(queue || {}, rowList).join("\n"));
    }

    function queueRuntimeStatus(queue, rows) {
      const payload = queue || {};
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

    function queueRuntimeLines(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const lines = [
        `Pipeline event source: ${payload.runtime_outcome_source || "(not configured)"}`,
        `Recent events read: ${payload.runtime_outcome_event_count || 0}`,
        `Visible queue rows: ${rowList.length}`,
        `Rows with exact source-path runtime history: ${payload.runtime_outcome_match_count || 0}`,
        `Outcome statuses: ${queueFormatCounts(payload.runtime_outcome_status_counts)}`,
        `Outcome event types: ${queueFormatCounts(payload.runtime_outcome_event_type_counts)}`,
        `Outcome error codes: ${queueFormatCounts(payload.runtime_outcome_error_code_counts)}`,
        `Outcome freshness: ${queueFormatCounts(payload.runtime_outcome_freshness_counts)}`,
      ];
      if (payload.runtime_outcome_warning) {
        lines.push("", `Warning: ${payload.runtime_outcome_warning}`);
      }
      const stale = Number((payload.runtime_outcome_freshness_counts || {}).stale || 0);
      if (stale > 0) {
        lines.push("", "Stale history is shown only as context. Refresh Queue and inspect recent run logs before acting on old outcomes.");
      }
      if (!Number(payload.runtime_outcome_event_count || 0)) {
        lines.push("", "No recent pipeline completion/failure events were available in the bounded event tail.");
      } else if (!Number(payload.runtime_outcome_match_count || 0)) {
        lines.push("", "No visible row matched recent runtime history. Matching is exact source-path identity only to avoid misleading fuzzy correlations.");
      } else {
        lines.push("", "Select a queue row to inspect the matching runtime status, error code, reason, publish state, and output path.");
      }
      lines.push(readOnlyBoundary);
      return lines;
    }

    function renderQueueRuntime(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("queue-runtime-status", queueRuntimeStatus(queue || {}, rowList));
      setText("queue-runtime", queueRuntimeLines(queue || {}, rowList).join("\n"));
    }

    function queueValidationStatus(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      if (payload.error) return "Unavailable";
      if (Number(payload.invalid_row_count || 0) > 0 || Number(payload.blocked_row_count || 0) > 0) return "Review rows";
      if (payload.runtime_outcome_warning) return "History warning";
      if (Number((payload.runtime_outcome_freshness_counts || {}).stale || 0) > 0) return "Trustworthy - history advisory";
      if (!rowList.length && Number(payload.excluded_row_count || 0) > 0) return "Filtered";
      if (!rowList.length) return "Empty";
      return queueSnapshotIsStale(payload) ? "Trustworthy - refresh advised" : "Trustworthy";
    }

    function queueValidationChecklistLines(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      if (payload.error) {
        return [
          "Validation state: queue payload is unavailable.",
          `Error: ${payload.error}`,
          "Operator action: open Diagnostics > Queue Snapshot, Run Logs, and Last Stderr before launching or reprocessing.",
          readOnlyBoundary,
        ];
      }
      const staleSnapshot = queueSnapshotIsStale(payload);
      const runtimeFreshness = payload.runtime_outcome_freshness_counts || {};
      const runtimeErrors = payload.runtime_outcome_error_code_counts || {};
      const lines = [
        "Real-media validation checklist:",
        `Queue snapshot fresh enough: ${staleSnapshot ? "no - refresh before launch" : "yes"}`,
        `Runnable rows visible: ${rowList.length}`,
        queueHiddenSidecarLine(payload),
        `Excluded source rows: ${payload.excluded_row_count || 0}${payload.excluded_rows_truncated ? " (truncated)" : ""}`,
        `Completed/blocked exclusions: ${payload.completed_excluded_count || 0}`,
        `Visible blocked rows: ${payload.blocked_row_count || 0}`,
        `Invalid snapshot rows: ${payload.invalid_row_count || 0}`,
        `Runtime checks deferred: ${payload.runtime_check_deferred_count || 0}`,
        `Runtime history matched rows: ${payload.runtime_outcome_match_count || 0}`,
        `Runtime freshness: ${queueFormatCounts(runtimeFreshness)}`,
        `Runtime error codes: ${queueFormatCounts(runtimeErrors)}`,
        `Warnings: ${warnings.length}`,
      ];
      lines.push("");
      if (Number(payload.invalid_row_count || 0) > 0 || Number(payload.blocked_row_count || 0) > 0) {
        lines.push("Operator action: filter for blocked/invalid rows, select them, and inspect route evidence before launching a broad batch.");
      } else if (staleSnapshot) {
        lines.push("Advisory: refresh queue preview before launch. Snapshot age does not outrank blocked or failed row evidence.");
      } else if (!rowList.length && Number(payload.excluded_row_count || 0) > 0) {
        lines.push("Operator action: inspect Excluded Source Rows. Empty queue with exclusions usually means completed history, failure markers, or processed-state filtering is active.");
      } else if (payload.runtime_outcome_warning || Number(runtimeFreshness.stale || 0) > 0) {
        lines.push("Operator action: treat runtime history as context only. Open Run Logs before trusting stale or warning outcome data.");
      } else if (!rowList.length) {
        lines.push("Operator action: verify source roots, file extensions, completed exclusions, and source stability before assuming media was missed.");
      } else if (warnings.length) {
        lines.push("Operator action: review warning text and selected-row guidance before Launch.");
      } else {
        lines.push("Operator action: queue preview is internally consistent. Launch remains schedule-gated and backend-owned.");
      }
      lines.push(readOnlyBoundary);
      return lines;
    }

    function renderQueueValidation(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("queue-validation-status", queueValidationStatus(queue || {}, rowList));
      setText("queue-validation", queueValidationChecklistLines(queue || {}, rowList).join("\n"));
    }

    function queueCollisionStatus(queue, rows) {
      const payload = queue || {};
      if (payload.error) return "Unavailable";
      return payload.completed_collision_status || (Array.isArray(rows) && rows.length ? "Loaded" : "No rows");
    }

    function queueCollisionLines(queue, rows) {
      const payload = queue || {};
      const lines = Array.isArray(payload.completed_collision_lines) ? [...payload.completed_collision_lines] : [];
      if (!lines.length) {
        const rowList = Array.isArray(rows) ? rows : [];
        lines.push(
          `Source candidates: ${payload.source_count_total || 0}`,
          `Runnable rows: ${queuePayloadRunnableCount(payload, rowList)}`,
          `Completed/blocked exclusions: ${payload.completed_excluded_count || 0}`,
          "Row-level excluded-file detail: unavailable in the current queue snapshot contract."
        );
      }
      const flags = Array.isArray(payload.completed_collision_flags) ? payload.completed_collision_flags.join(", ") : "";
      return [
        `Status: ${payload.completed_collision_status || "unknown"}`,
        `Severity: ${payload.completed_collision_severity || "unknown"}`,
        payload.completed_collision_guidance ? `Next step: ${payload.completed_collision_guidance}` : "",
        flags ? `Risk flags: ${flags}` : "",
        "",
        ...lines,
      ].filter((line) => line !== "");
    }

    function renderQueueCollision(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("queue-collision-status", queueCollisionStatus(queue || {}, rowList));
      setText("queue-collision", queueCollisionLines(queue || {}, rowList).join("\n"));
    }

    function queueExcludedStatus(queue) {
      const payload = queue || {};
      if (payload.error) return "Unavailable";
      if (!payload.completed_collision_row_level_available) return "Unavailable";
      const total = Number(payload.excluded_row_count || 0);
      if (!total) return "No excluded rows";
      return payload.excluded_rows_truncated ? "Truncated detail" : "Loaded";
    }

    function queueExcludedSummaryLines(queue) {
      const payload = queue || {};
      const rows = Array.isArray(payload.excluded_rows) ? payload.excluded_rows : [];
      if (!payload.completed_collision_row_level_available) {
        return [
          "Row-level excluded source detail is not available in this queue snapshot.",
          "Next step: refresh Queue after the updated backend has emitted a new snapshot.",
          readOnlyBoundary,
        ];
      }
      const lines = [
        `Excluded rows reported: ${payload.excluded_row_count || rows.length || 0}`,
        `Rows shown: ${rows.length}`,
        `Snapshot row limit: ${payload.excluded_row_limit || "not reported"}`,
        `Truncated: ${payload.excluded_rows_truncated ? "yes" : "no"}`,
        `Reasons: ${queueFormatCounts(payload.excluded_reason_counts)}`,
        `Media types: ${queueFormatCounts(payload.excluded_media_type_counts)}`,
      ];
      if (!rows.length) {
        lines.push("", "No excluded source rows were reported. If runnable rows are missing, inspect source filters, schedule state, and recent run logs.");
      } else {
        lines.push("", "These rows were filtered before the runnable queue. Already-processed rows usually mean completed history, sidecar state, or pending-publish state matched the source.");
      }
      if (payload.excluded_rows_truncated) {
        lines.push("Refresh after narrowing the source folder if you need exact detail beyond the bounded snapshot limit.");
      }
      lines.push(readOnlyBoundary);
      return lines;
    }

    const __queueExcludedMod = window.__queueExcludedModule || {};
    delete window.__queueExcludedModule;
    const _queueExcluded = typeof __queueExcludedMod.createQueueExcludedModule === "function"
      ? __queueExcludedMod.createQueueExcludedModule({
        appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
        byId: typeof byId === "function" ? byId : window.byId,
        clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
        documentRef: document,
        getSelectedQueueExcludedRowKey,
        makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
        queueExcludedRowKey,
        queueExcludedStatus,
        queueExcludedSummaryLines,
        selectQueueExcludedRow,
        setText: typeof setText === "function" ? setText : window.setText,
        updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
      })
      : {};
    const { renderQueueExcluded = _queueNoop } = _queueExcluded;

    return {
      queueBreakdownStatus, queueBreakdownLines, renderQueueBreakdown,
      queueRuntimeStatus, queueRuntimeLines, renderQueueRuntime,
      queueValidationStatus, queueValidationChecklistLines, renderQueueValidation,
      queueCollisionStatus, queueCollisionLines, renderQueueCollision,
      queueExcludedStatus, queueExcludedSummaryLines, renderQueueExcluded,
    };
  }

  window.__queueStatusPanelsModule = { createQueueStatusPanelsModule };
})();
