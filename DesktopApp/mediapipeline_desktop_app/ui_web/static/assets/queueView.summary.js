// queueView.summary.js
// Split child of queueView.js. Loaded before queueView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  function createQueueSummaryModule({
    setText,
    queueHiddenSidecarExtensions,
    queueValidationStatus,
  }) {
    setText = typeof setText === "function" ? setText : function () {};
    queueValidationStatus = typeof queueValidationStatus === "function" ? queueValidationStatus : function () { return "unknown"; };
    const QUEUE_HIDDEN_SIDECAR_EXTENSIONS = queueHiddenSidecarExtensions instanceof Set ? queueHiddenSidecarExtensions : new Set();

    function queuePathExtension(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      const leaf = text.split(/[\\/]/).filter(Boolean).pop() || text;
      const match = leaf.match(/(\.[^.\\/.\s]+)$/);
      return match ? match[1].toLowerCase() : "";
    }


    function queueRowExtension(row) {
      return queuePathExtension(row?.source_path || row?.relative_path || row?.display_name || "");
    }


    function queueIsHiddenSidecarBlockedRow(row) {
      const extension = queueRowExtension(row);
      if (!QUEUE_HIDDEN_SIDECAR_EXTENSIONS.has(extension)) return false;
      const blockedCode = String(row?.blocked_reason_code || "").toLowerCase();
      const routeCode = String(row?.route_reason_code || "").toLowerCase();
      const blockedReason = String(row?.blocked_reason || row?.route_reason || "").toLowerCase();
      const trustState = String(row?.operator_trust_state || "").toLowerCase();
      const status = String(row?.operator_status || row?.status || "").toLowerCase();
      return blockedCode === "bad_extension"
        || blockedCode === "bad-extension"
        || routeCode === "bad_extension"
        || routeCode === "bad-extension"
        || blockedReason.includes("bad-extension")
        || blockedReason.includes("bad extension")
        || (trustState === "blocked" && status.includes("blocked"));
    }


    function queueIncrementCount(counts, key) {
      const normalized = String(key || "unknown").trim() || "unknown";
      counts[normalized] = (counts[normalized] || 0) + 1;
    }


    function queueCountRowsBy(rows, field, fallback = "unknown") {
      const counts = {};
      (Array.isArray(rows) ? rows : []).forEach((row) => {
        const value = row?.[field];
        if (Array.isArray(value)) {
          if (!value.length) queueIncrementCount(counts, fallback);
          value.forEach((item) => queueIncrementCount(counts, item || fallback));
        } else {
          queueIncrementCount(counts, value || fallback);
        }
      });
      return counts;
    }


    function queueCountRowsByExtension(rows) {
      const counts = {};
      (Array.isArray(rows) ? rows : []).forEach((row) => {
        queueIncrementCount(counts, queueRowExtension(row) || "unknown");
      });
      return counts;
    }


    function queueIsMovieRow(row) {
      return String(row?.media_type || row?.phase || "").toLowerCase().includes("movie");
    }


    function queueIsTvRow(row) {
      const text = String(row?.media_type || row?.phase || "").toLowerCase();
      return text.includes("tv") || text.includes("episode");
    }


    function queueBlockedRows(rows) {
      return (Array.isArray(rows) ? rows : []).filter((row) => row?.blocked_reason || row?.blocked_reason_code);
    }


    function queueVisibleRunnableCount(queue, visibleRows, hiddenRows, allRows) {
      const original = Number(queue?.runnable_count || 0);
      if (!original) return visibleRows.length;
      if (original >= allRows.length) return Math.max(0, original - hiddenRows.length);
      return Math.min(original, visibleRows.length);
    }


    function queueRowHasVisiblePriority(row) {
      const level = String(row?.manifest_priority_level || "normal").toLowerCase();
      return Boolean(row?.is_priority) || level === "high" || level === "low" || level === "hold";
    }


    function queueDisplayPayloadForVisibleRows(queue, visibleRows, hiddenSidecars, allRows) {
      const display = { ...(queue || {}) };
      if (queue?.__mediaPipelineRefreshMeta) {
        try {
          Object.defineProperty(display, "__mediaPipelineRefreshMeta", {
            value: queue.__mediaPipelineRefreshMeta,
            enumerable: false,
            configurable: true,
          });
        } catch (_) {}
      }
      const rows = Array.isArray(visibleRows) ? visibleRows : [];
      const hidden = Array.isArray(hiddenSidecars) ? hiddenSidecars : [];
      const rawRows = Array.isArray(allRows) ? allRows : rows;
      const blockedRows = queueBlockedRows(rows);
      const invalidRows = rows.filter((row) => String(row?.status || "").toLowerCase() === "invalid");
      const hiddenMovies = hidden.filter(queueIsMovieRow).length;
      const hiddenTv = hidden.filter(queueIsTvRow).length;
      const movieCount = Number(display.movie_count_total || 0);
      const tvCount = Number(display.tv_count_total || 0);
      const sourceCount = Number(display.source_count_total || movieCount + tvCount || rawRows.length || 0);

      display.rows = rows;
      display.ui_hidden_sidecar_count = hidden.length;
      display.ui_hidden_sidecar_extension_counts = queueCountRowsByExtension(hidden);
      display.movie_count_total = movieCount ? Math.max(0, movieCount - hiddenMovies) : movieCount;
      display.tv_count_total = tvCount ? Math.max(0, tvCount - hiddenTv) : tvCount;
      display.source_count_total = sourceCount ? Math.max(0, sourceCount - hidden.length) : rows.length;
      display.runnable_count = queueVisibleRunnableCount(display, rows, hidden, rawRows);
      display.blocked_row_count = blockedRows.length;
      display.invalid_row_count = invalidRows.length;
      display.priority_visible_count = rows.filter(queueRowHasVisiblePriority).length;
      display.operator_status_counts = queueCountRowsBy(rows, "operator_status");
      display.operator_severity_counts = queueCountRowsBy(rows, "operator_severity");
      display.operator_trust_state_counts = queueCountRowsBy(rows, "operator_trust_state");
      display.route_counts = queueCountRowsBy(rows, "route_name");
      display.route_reason_counts = queueCountRowsBy(rows, "route_reason_code");
      display.phase_counts = queueCountRowsBy(rows, "phase");
      display.media_type_counts = queueCountRowsBy(rows, "media_type");
      display.source_root_counts = queueCountRowsBy(rows, "source_root");
      display.blocked_reason_code_counts = queueCountRowsBy(blockedRows, "blocked_reason_code");
      display.blocked_reason_counts = queueCountRowsBy(blockedRows, "blocked_reason");
      display.queue_progress = queueDisplayProgressForVisibleRows(display, rows, hidden);
      return display;
    }


    function queueDisplayProgressForVisibleRows(queue, rows, hiddenSidecars) {
      const progress = queue?.queue_progress && typeof queue.queue_progress === "object" ? { ...queue.queue_progress } : queue?.queue_progress;
      if (!progress || typeof progress !== "object" || !hiddenSidecars.length) return progress;
      const sourceLine = `Source candidates: ${queue.source_count_total || rows.length} (${queue.movie_count_total || 0} movie / ${queue.tv_count_total || 0} TV)`;
      const runnableLine = `Runnable rows loaded: ${queue.runnable_count || rows.length}`;
      const displayedLine = `Rows displayed: ${rows.length}`;
      const hiddenLine = queueHiddenSidecarLine(queue);
      const summary = Array.isArray(progress.summary_lines) ? progress.summary_lines.map((line) => {
        const text = String(line || "");
        if (text.startsWith("Source candidates:")) return sourceLine;
        if (text.startsWith("Runnable rows loaded:")) return runnableLine;
        if (text.startsWith("Rows displayed:")) return displayedLine;
        return text;
      }) : [];
      if (summary.length && hiddenLine && !summary.includes(hiddenLine)) {
        const rowsIndex = summary.findIndex((line) => String(line || "").startsWith("Rows displayed:"));
        summary.splice(rowsIndex >= 0 ? rowsIndex + 1 : summary.length, 0, hiddenLine);
      }
      progress.summary_lines = summary;
      if (Array.isArray(progress.progress_bars)) {
        progress.progress_bars = progress.progress_bars.map((bar) => ({
          ...bar,
          detail: String(bar?.id || "") === "queue_source_scan"
            ? `${sourceLine} | runnable ${queue.runnable_count || rows.length}`
            : bar?.detail,
        }));
      }
      return progress;
    }


    function queueHiddenSidecarLine(queue) {
      const count = Number(queue?.ui_hidden_sidecar_count || 0);
      if (!count) return "";
      return `Hidden subtitle sidecars: ${count} (${queueFormatCounts(queue.ui_hidden_sidecar_extension_counts)}). These are not video queue rows.`;
    }


    function queueEmptyStateMessage(queue, rows) {
      if (queue.error) {
        return `Queue unavailable: ${queue.error}. Open Diagnostics > Run Logs and Queue Snapshot for details.`;
      }
      const warnings = Array.isArray(queue.warnings) ? queue.warnings.filter(Boolean) : [];
      if (warnings.length) {
        return `Queue loaded with warning: ${warnings.join(" | ")}`;
      }
      if (!rows.length) {
        return "No runnable queue rows. Check Source paths, completed-manifest exclusions, schedule state, or run a fresh queue preview from Launch.";
      }
      return "No queue rows available.";
    }


    function queueProgressPayload(queue) {
      return queue?.queue_progress && typeof queue.queue_progress === "object" ? queue.queue_progress : {};
    }


    function queueProgressBars(queue) {
      const progress = queueProgressPayload(queue);
      if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
      if (Array.isArray(queue?.progress_bars)) return queue.progress_bars.filter(Boolean);
      return [];
    }


    function queueProgressStatus(queue, bars = queueProgressBars(queue)) {
      const progressStatus = String(queueProgressPayload(queue).status || "").toLowerCase();
      const statuses = [progressStatus, ...bars.map((bar) => String(bar?.status || "").toLowerCase())].filter(Boolean);
      if (!statuses.length) return "Not loaded";
      if (statuses.includes("blocked")) return "Blocked";
      if (statuses.includes("warning")) return "Review";
      if (statuses.includes("active")) return "Running";
      if (statuses.includes("complete")) return "Complete";
      if (statuses.includes("idle")) return "Idle";
      return "Unknown";
    }


    function queueProgressSummaryLines(queue, bars = queueProgressBars(queue)) {
      const progress = queueProgressPayload(queue);
      if (Array.isArray(progress.summary_lines) && progress.summary_lines.length) {
        return progress.summary_lines.filter(Boolean).map((line) => String(line));
      }
      const warnings = Array.isArray(queue?.warnings) ? queue.warnings.filter(Boolean) : [];
      return [
        "Queue source scan progress:",
        bars.length ? `${bars.length} backend progress bar${bars.length === 1 ? "" : "s"} loaded.` : "No backend queue progress bars loaded.",
        queue?.source ? `Source: ${queue.source}` : "",
        queue?.snapshot_file_freshness_status ? queueFreshnessLine("Snapshot file age", queue.snapshot_file_age_text, queue.snapshot_file_freshness_status, queue.snapshot_file_mtime_utc) : "",
        queue?.produced_freshness_status ? queueFreshnessLine("Produced age", queue.produced_age_text, queue.produced_freshness_status) : "",
        "Progress mode: indeterminate until backend scanner telemetry emits a reliable candidate numerator and denominator.",
        "Guardrail: Queue progress is read-only evidence; the WebView cannot refresh, reorder, drop, or mutate queue state.",
        ...(warnings.length ? warnings.map((warning) => `Warning: ${warning}`) : []),
      ].filter(Boolean);
    }


    function renderQueueProgress(queue) {
      const bars = queueProgressBars(queue);
      setText("queue-progress-status", queueProgressStatus(queue, bars));
      setText("queue-progress-summary", queueProgressSummaryLines(queue, bars).join("\n"));
      const progressRenderer = window.renderProgressBarsInto;
      if (typeof progressRenderer === "function") {
        progressRenderer("queue-progress-bars", bars, queueProgressPayload(queue), "No queue source scan progress loaded.");
      }
    }


    function queueFreshnessLine(label, ageText, status, mtime) {
      const age = ageText || "unknown";
      const state = status || "unknown";
      const modified = mtime ? `; modified ${mtime}` : "";
      return `${label}: ${age} (${state})${modified}`;
    }


    function queueSnapshotIsStale(queue) {
      const snapshotStatus = String(queue?.snapshot_file_freshness_status || "").toLowerCase();
      const producedStatus = String(queue?.produced_freshness_status || "").toLowerCase();
      return snapshotStatus === "stale" || producedStatus === "stale";
    }


    function renderQueueSummary(queue, rows) {
      const priorityRows = rows.filter((row) => row?.is_priority).length;
      const encodeRows = rows.filter((row) => String(row?.route_name || "").toLowerCase().includes("encode")).length;
      const remuxRows = rows.filter((row) => String(row?.route_name || "").toLowerCase().includes("remux")).length;
      const movieCount = Number(queue.movie_count_total || 0);
      const tvCount = Number(queue.tv_count_total || 0);
      const sourceCount = Number(queue.source_count_total || movieCount + tvCount || 0);
      const completedExcluded = Number(queue.completed_excluded_count || 0);
      const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
        ? window.mediaPipelineDom.payloadFreshnessLines({
          payload: queue,
          label: "Queue",
          rowCount: rows.length,
          sourceLine: queue.source ? `Source: ${queue.source}` : "",
          artifactLine: queue.snapshot_file_freshness_status ? queueFreshnessLine("Snapshot file age", queue.snapshot_file_age_text, queue.snapshot_file_freshness_status, queue.snapshot_file_mtime_utc) : "",
          readError: queue.snapshot_file_error || queue.error || "",
          refreshAction: "Use Refresh Queue or topbar Refresh. This reloads backend snapshots only and does not change launch scope.",
        })
        : [];
      const lines = [
        ...freshnessLines,
        freshnessLines.length ? "" : (queue.source ? `Source: ${queue.source}` : ""),
        queue.produced_at ? `Produced: ${queue.produced_at}` : "",
        freshnessLines.length ? "" : (queue.snapshot_file_freshness_status ? queueFreshnessLine("Snapshot file age", queue.snapshot_file_age_text, queue.snapshot_file_freshness_status, queue.snapshot_file_mtime_utc) : ""),
        queue.produced_freshness_status ? queueFreshnessLine("Produced age", queue.produced_age_text, queue.produced_freshness_status) : "",
        queue.config_path ? `Config: ${queue.config_path}` : "",
        queue.local_base ? `Scratch: ${queue.local_base}` : "",
        queue.source_movies || queue.source_tv ? `Source roots: movies=${queue.source_movies || "(none)"}; tv=${queue.source_tv || "(none)"}` : "",
        queue.outsource ? `Output root: ${queue.outsource}` : "",
        `Rows: ${rows.length}`,
        queueHiddenSidecarLine(queue),
        sourceCount ? `Source candidates: ${sourceCount} (${movieCount} movie / ${tvCount} TV)` : "",
        `Runnable: ${queue.runnable_count || rows.length || 0}`,
        `Completed/blocked exclusions: ${completedExcluded}`,
        queue.excluded_row_count !== undefined ? `Excluded row detail: ${queue.excluded_row_count || 0}${queue.excluded_rows_truncated ? " (truncated)" : ""}` : "",
        `Visible blocked rows: ${queue.blocked_row_count || 0}`,
        `Runtime checks deferred: ${queue.runtime_check_deferred_count || 0}`,
        `Runtime outcome matches: ${queue.runtime_outcome_match_count || 0}`,
        queue.total_visible_size_text ? `Visible size: ${queue.total_visible_size_text}` : "",
        priorityRows ? `Priority: ${priorityRows}` : "Priority: 0",
        queue.priority_count !== undefined ? `Snapshot priority count: ${queue.priority_count || 0}` : "",
        encodeRows || remuxRows ? `Route mix: ${encodeRows} encode / ${remuxRows} remux` : "",
        queue.operator_status_counts ? `Operator statuses: ${queueFormatCounts(queue.operator_status_counts)}` : "",
        queue.operator_trust_state_counts ? `Backend trust states: ${queueFormatCounts(queue.operator_trust_state_counts)}` : "",
        queue.available_open_target_counts ? `Backend open targets: ${queueFormatCounts(queue.available_open_target_counts)}` : "",
        queue.completed_collision_status ? `Completed collision: ${queue.completed_collision_status}` : "",
        queue.invalid_row_count ? `Invalid snapshot rows: ${queue.invalid_row_count}` : "",
        ...(Array.isArray(queue.warnings) ? queue.warnings : []),
        !rows.length ? queueEmptyStateMessage(queue, rows) : "",
      ].filter(Boolean);
      setText("queue-summary", lines.join("\n") || "No queue preview loaded.");
    }


    function queueCounts(queue, rows) {
      const movieCount = Number(queue?.movie_count_total || 0);
      const tvCount = Number(queue?.tv_count_total || 0);
      const sourceCount = Number(queue?.source_count_total || movieCount + tvCount || 0);
      const runnable = Number(queue?.runnable_count || rows.length || 0);
      const completedExcluded = Number(queue?.completed_excluded_count || 0);
      const priorityRows = rows.filter((row) => row?.is_priority).length;
      const invalidRows = rows.filter((row) => String(row?.status || "").toLowerCase() === "invalid").length;
      const encodeRows = rows.filter((row) => String(row?.route_name || "").toLowerCase().includes("encode")).length;
      const remuxRows = rows.filter((row) => String(row?.route_name || "").toLowerCase().includes("remux")).length;
      return { movieCount, tvCount, sourceCount, runnable, completedExcluded, priorityRows, invalidRows, encodeRows, remuxRows };
    }


    function queueReadinessStatus(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(queue?.warnings) ? queue.warnings.filter(Boolean) : [];
      const counts = queueCounts(queue || {}, rowList);
      if (queue?.error) return "Unavailable";
      if (queueSnapshotIsStale(queue)) return "Snapshot stale";
      if (!counts.sourceCount && !rowList.length) return "No candidates";
      if (!rowList.length || counts.runnable <= 0) return "Empty";
      if (Number(queue?.invalid_row_count || 0) > 0 || counts.invalidRows > 0) return "Snapshot review";
      if (warnings.length) return "Warnings";
      if (counts.priorityRows) return "Priority ready";
      return "Ready";
    }


    function queueReadinessLines(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const counts = queueCounts(payload, rowList);
      if (payload.error) {
        return [
          "Status: unavailable",
          `Error: ${payload.error}`,
          "Next step: open Diagnostics > Queue Snapshot and Run Logs before launching work.",
        ];
      }
      const lines = [
        `Source roots: movies=${payload.source_movies || "(none)"}; tv=${payload.source_tv || "(none)"}`,
        queueFreshnessLine("Snapshot file age", payload.snapshot_file_age_text, payload.snapshot_file_freshness_status, payload.snapshot_file_mtime_utc),
        queueFreshnessLine("Produced age", payload.produced_age_text, payload.produced_freshness_status),
        `Scratch: ${payload.local_base || "(not reported)"}`,
        `Output root: ${payload.outsource || "(not reported)"}`,
        `Source candidates: ${counts.sourceCount} (${counts.movieCount} movie / ${counts.tvCount} TV)`,
        `Runnable rows: ${counts.runnable}`,
        `Visible rows: ${rowList.length}`,
        queueHiddenSidecarLine(payload),
        `Completed/blocked exclusions: ${counts.completedExcluded}`,
        `Excluded row detail: ${payload.excluded_row_count || 0}${payload.excluded_rows_truncated ? " (truncated)" : ""}`,
        `Visible blocked rows: ${payload.blocked_row_count || 0}`,
        `Runtime checks deferred: ${payload.runtime_check_deferred_count || 0}`,
        `Recent runtime outcome matches: ${payload.runtime_outcome_match_count || 0}`,
        `Priority rows: ${counts.priorityRows}`,
        `Invalid snapshot rows: ${payload.invalid_row_count || counts.invalidRows || 0}`,
        payload.total_visible_size_text ? `Visible size: ${payload.total_visible_size_text}` : "",
        `Route mix: ${counts.encodeRows} encode / ${counts.remuxRows} remux / ${Math.max(0, rowList.length - counts.encodeRows - counts.remuxRows)} other`,
        `Operator statuses: ${queueFormatCounts(payload.operator_status_counts)}`,
        `Operator severities: ${queueFormatCounts(payload.operator_severity_counts)}`,
        `Backend open targets: ${queueFormatCounts(payload.available_open_target_counts)}`,
      ];
      if (warnings.length) {
        lines.push("", "Warning(s):");
        warnings.slice(0, 6).forEach((warning) => lines.push(`- ${warning}`));
      }
      lines.push("");
      if (queueSnapshotIsStale(payload)) {
        lines.push("Next step: refresh queue preview before launch; stale snapshots can hide newly completed, moved, or half-copied files.");
      } else if (!counts.sourceCount && !rowList.length) {
        lines.push("Next step: verify Source roots/settings or run a fresh queue preview from Launch.");
      } else if (!rowList.length || counts.runnable <= 0) {
        lines.push("Next step: no runnable work is currently visible. Check completed exclusions, schedule state, source filters, and recent run logs before assuming files were missed.");
      } else if (Number(payload.invalid_row_count || 0) > 0 || counts.invalidRows > 0) {
        lines.push("Next step: refresh the queue preview and open Diagnostics > Queue Snapshot if invalid rows remain.");
      } else if (warnings.length) {
        lines.push("Next step: queue rows are visible, but review warnings before starting the pipeline.");
      } else if (counts.priorityRows) {
        lines.push("Next step: priority rows are ready. Launch remains backend-owned and schedule-gated.");
      } else {
        lines.push("Next step: queue preview has runnable rows. Use Launch to start backend-owned processing.");
      }
      lines.push("Mutation guardrail: queue mutation and processing start remain backend-owned commands; this page is read-only.");
      return lines;
    }


    function renderQueueReadiness(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("queue-readiness-status", queueReadinessStatus(queue || {}, rowList));
      setText("queue-readiness", queueReadinessLines(queue || {}, rowList).join("\n"));
    }


    function queueWorkflowStatus(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const counts = queueCounts(payload, rowList);
      if (payload.error) return "Diagnostics first";
      if (queueSnapshotIsStale(payload)) return "Refresh queue";
      if (Number(payload.invalid_row_count || 0) > 0 || Number(payload.blocked_row_count || 0) > 0 || counts.invalidRows > 0) return "Review rows";
      if (!rowList.length && (counts.completedExcluded > 0 || Number(payload.excluded_row_count || 0) > 0)) return "Check exclusions";
      if (!rowList.length || counts.runnable <= 0) return "No launch";
      if (warnings.length || payload.runtime_outcome_warning || Number((payload.runtime_outcome_freshness_counts || {}).stale || 0) > 0) return "Review context";
      return "Launch path clear";
    }


    function queueWorkflowLines(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const counts = queueCounts(payload, rowList);
      const staleHistory = Number((payload.runtime_outcome_freshness_counts || {}).stale || 0);
      const lines = [
        "Cross-page workflow: Queue",
        `Queue readiness: ${queueReadinessStatus(payload, rowList)}`,
        `Queue validation: ${queueValidationStatus(payload, rowList)}`,
        `Runnable rows: ${counts.runnable}`,
        `Completed/blocked exclusions: ${counts.completedExcluded}`,
        `Excluded source rows: ${payload.excluded_row_count || 0}`,
        `Blocked/invalid rows: ${payload.blocked_row_count || 0} / ${payload.invalid_row_count || counts.invalidRows || 0}`,
        queueHiddenSidecarLine(payload),
        `Recent runtime matches: ${payload.runtime_outcome_match_count || 0}`,
      ];
      lines.push("");
      if (payload.error) {
        lines.push("Next step: open Diagnostics > State Artifact Summary, Queue Snapshot, Run Logs, and Last Stderr before launching work.");
      } else if (queueSnapshotIsStale(payload)) {
        lines.push("Next step: refresh the queue preview from Launch before starting a run. Stale queue data can hide completed outputs, moved files, or half-copied sources.");
      } else if (Number(payload.invalid_row_count || 0) > 0 || counts.invalidRows > 0 || Number(payload.blocked_row_count || 0) > 0) {
        lines.push("Next step: select the affected row, read Queue Diagnostics Cross-Links, then use Diagnostics > Queue Snapshot / Last Stderr / Active Jobs.");
      } else if (!rowList.length && (counts.completedExcluded > 0 || Number(payload.excluded_row_count || 0) > 0)) {
        lines.push("Next step: check Completed for manifest exclusions and Excluded Source Rows before assuming source files were missed.");
      } else if (!rowList.length || counts.runnable <= 0) {
        lines.push("Next step: do not launch from an empty queue. Check Source settings, Completed, schedule state, and Run Logs first.");
      } else if (warnings.length || payload.runtime_outcome_warning || staleHistory > 0) {
        lines.push("Next step: review warnings and runtime-history context. If the selected row has a stale or failed outcome, use its diagnostics links before launch.");
      } else {
        lines.push("Next step: queue context is coherent. Use Launch for the backend-owned start command when schedule/readiness allows.");
      }
      lines.push("Owning pages: Queue for source readiness, Completed for skip/collision proof, Pending Publish for parked-output state, Diagnostics for artifacts/logs.");
      lines.push("Mutation guardrail: this workflow panel is read-only. Launch commands remain backend-owned.");
      return lines;
    }


    function renderQueueWorkflow(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("queue-workflow-status", queueWorkflowStatus(queue || {}, rowList));
      setText("queue-workflow", queueWorkflowLines(queue || {}, rowList).join("\n"));
    }


    function queueFormatCounts(value) {
      const entries = value && typeof value === "object" ? Object.entries(value) : [];
      if (!entries.length) return "none";
      return entries.map(([key, count]) => `${key || "unknown"}=${count}`).join(", ");
    }

    return {
      queuePathExtension,
      queueRowExtension,
      queueIsHiddenSidecarBlockedRow,
      queueIncrementCount,
      queueCountRowsBy,
      queueCountRowsByExtension,
      queueIsMovieRow,
      queueIsTvRow,
      queueBlockedRows,
      queueVisibleRunnableCount,
      queueDisplayPayloadForVisibleRows,
      queueDisplayProgressForVisibleRows,
      queueHiddenSidecarLine,
      queueEmptyStateMessage,
      queueProgressPayload,
      queueProgressBars,
      queueProgressStatus,
      queueProgressSummaryLines,
      renderQueueProgress,
      queueFreshnessLine,
      queueSnapshotIsStale,
      renderQueueSummary,
      queueCounts,
      queueReadinessStatus,
      queueReadinessLines,
      renderQueueReadiness,
      queueWorkflowStatus,
      queueWorkflowLines,
      renderQueueWorkflow,
      queueFormatCounts,
    };
  }

  window.__queueSummaryModule = { createQueueSummaryModule };
})();
