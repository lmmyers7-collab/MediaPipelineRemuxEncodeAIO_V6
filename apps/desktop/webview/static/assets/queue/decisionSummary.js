(function () {
  function createQueueDecisionModule(deps = {}) {
    const { byId, setText, queueCurrentFilterScope, queueLaunchDecisionStatus, queueLaunchDecisionSummaryLines, queueReviewDigestStatus, queueReviewDigestAction, queueReviewRows, queueListText, getLastQueuePayload, getLastQueueRows } = deps;
      function queueVisibleFilterScope(rows) {
        const rowList = Array.isArray(rows) ? rows : [];
        const scope = typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope(rowList) : null;
        if (scope && typeof scope === "object") {
          return {
            active: Boolean(scope.active),
            totalRows: Number(scope.totalRows || 0),
            visibleRows: Number(scope.visibleRows || 0),
            hiddenRows: Number(scope.hiddenRows || 0),
            hiddenBlocked: Number(scope.hiddenBlocked || 0),
            hiddenWarning: Number(scope.hiddenWarning || 0),
            hiddenReview: Number(scope.hiddenReview || 0),
            renderLimit: Number(scope.renderLimit || 250),
          };
        }
        return {
          active: false,
          totalRows: rowList.length,
          visibleRows: rowList.length,
          hiddenRows: 0,
          hiddenBlocked: 0,
          hiddenWarning: 0,
          hiddenReview: 0,
          renderLimit: 250,
        };
      }

      function queueDecisionOutcome(queue, rows, entries) {
        const rowList = Array.isArray(rows) ? rows : [];
        const scope = queueVisibleFilterScope(rowList);
        const rawStatus = typeof queueLaunchDecisionStatus === "function"
          ? queueLaunchDecisionStatus(queue || {}, rowList, Array.isArray(entries) ? entries : [])
          : "Read evidence";
        if (String(rawStatus || "").toLowerCase() === "ready-looking") {
          return scope.hiddenBlocked || scope.hiddenReview ? "Review first" : "Queue evidence OK";
        }
        if (String(rawStatus || "").toLowerCase() === "evidence incomplete" || String(rawStatus || "").toLowerCase() === "not evaluated") {
          return "Read evidence";
        }
        return rawStatus || "Read evidence";
      }

      function queueDecisionStatusState(status) {
        const normalized = String(status || "").trim().toLowerCase();
        if (normalized === "queue evidence ok") return "ready";
        return typeof queueLaunchDecisionStatusState === "function"
          ? queueLaunchDecisionStatusState(status)
          : normalized === "do not launch"
            ? "blocked"
            : normalized === "review first"
              ? "warning"
              : normalized === "read evidence"
                ? "changed"
                : "unknown";
      }

      function queueDecisionFirstAction(status, queue, rows, scope) {
        const payload = queue || {};
        const rowList = Array.isArray(rows) ? rows : [];
        if (String(status || "").toLowerCase() === "do not launch") {
          return "First action: stay in Queue and Diagnostics until blocked evidence is explained.";
        }
        if (scope.hiddenBlocked || scope.hiddenReview) {
          return "First action: clear display filters or inspect hidden blocked/review rows before using Launch.";
        }
        if (Number(payload.excluded_row_count || 0) > 0 || Number(payload.completed_excluded_count || 0) > 0) {
          return "First action: review backend-excluded source files and completed exclusions before assuming files were missed.";
        }
        if (!rowList.length) {
          return "First action: explain the empty backend queue evidence before opening Launch.";
        }
        if (String(status || "").toLowerCase() === "queue evidence ok") {
          return "First action: open Launch for backend preflight, scope controls, schedule checks, and final authorization.";
        }
        return "First action: read the Queue-to-Launch handoff and diagnostics evidence before opening Launch.";
      }

      function queueDecisionSummaryLines(queue, rows, entries) {
        const payload = queue || {};
        const rowList = Array.isArray(rows) ? rows : [];
        const history = Array.isArray(entries) ? entries : [];
        const scope = queueVisibleFilterScope(rowList);
        const outcome = queueDecisionOutcome(payload, rowList, history);
        const selectedCount = typeof getSelectedQueuePriorityRowKeys === "function" ? getSelectedQueuePriorityRowKeys().length : 0;
        return [
          "Queue decision header:",
          `Decision state: ${outcome}.`,
          `Loaded rows: ${rowList.length}.`,
          `Visible rows after display filters: ${scope.visibleRows}/${scope.totalRows}.`,
          `Selected for Queue actions: ${selectedCount}.`,
          `Hidden blocked/review rows: ${scope.hiddenBlocked}/${scope.hiddenReview}.`,
          `Backend-excluded source rows: ${payload.excluded_row_count || 0}${payload.excluded_rows_truncated ? " (truncated)" : ""}.`,
          `Collision posture: ${payload.completed_collision_status || "unknown"} (${payload.completed_collision_severity || "unknown"}).`,
          "Backend launch scope is owned by Launch; Queue filters, selected rows, and rendered row caps are not submitted as processing scope.",
          queueDecisionFirstAction(outcome, payload, rowList, scope),
        ];
      }

      function renderQueueDecisionHeader(queue = getLastQueuePayload(), rows = getLastQueueRows(), entries) {
        const payload = queue || {};
        const rowList = Array.isArray(rows) ? rows : [];
        const history = Array.isArray(entries) ? entries : [];
        const outcome = queueDecisionOutcome(payload, rowList, history);
        setText("queue-decision-status", outcome);
        const statusNode = byId("queue-decision-status");
        if (statusNode) statusNode.dataset.state = queueDecisionStatusState(outcome);
        setText("queue-decision-summary", queueDecisionSummaryLines(payload, rowList, history).join("\n"));
      }

      function queueAttentionStatus(queue, rows) {
        const payload = queue || {};
        const rowList = Array.isArray(rows) ? rows : [];
        const scope = queueVisibleFilterScope(rowList);
        const reviewRows = typeof queueReviewRows === "function" ? queueReviewRows(payload, rowList) : [];
        const collisionSeverity = String(payload.completed_collision_severity || "").toLowerCase();
        if (payload.error) return "Diagnostics first";
        if (queueSnapshotIsStale(payload)) return "Refresh first";
        if (scope.hiddenBlocked || scope.hiddenReview) return "Hidden review rows";
        if (Array.isArray(reviewRows) && reviewRows.length) return `${reviewRows.length} flagged`;
        if (Number(payload.blocked_row_count || 0) > 0 || Number(payload.invalid_row_count || 0) > 0) return "Review rows";
        if (collisionSeverity && collisionSeverity !== "ok" && collisionSeverity !== "none") return "Collision review";
        if (Number(payload.excluded_row_count || 0) > 0) return "Check exclusions";
        if (!rowList.length) return "Explain empty";
        return "No immediate blocker";
      }

      function queueAttentionSummaryLines(queue, rows) {
        const payload = queue || {};
        const rowList = Array.isArray(rows) ? rows : [];
        const scope = queueVisibleFilterScope(rowList);
        const reviewRows = typeof queueReviewRows === "function" ? queueReviewRows(payload, rowList) : [];
        const flaggedCount = Array.isArray(reviewRows) ? reviewRows.length : 0;
        const lines = [
          "Attention required:",
          `Readiness: ${typeof queueReadinessStatus === "function" ? queueReadinessStatus(payload, rowList) : "unknown"}.`,
          `Flagged items: ${flaggedCount}; blocked rows: ${payload.blocked_row_count || 0}; invalid rows: ${payload.invalid_row_count || 0}.`,
          `Hidden blocked/review rows behind display filters: ${scope.hiddenBlocked}/${scope.hiddenReview}.`,
          `Collision risk: ${payload.completed_collision_status || "unknown"} (${payload.completed_collision_severity || "unknown"}).`,
          `Backend-excluded source rows: ${payload.excluded_row_count || 0}${payload.excluded_rows_truncated ? " (truncated)" : ""}.`,
        ];
        if (payload.error) {
          lines.push(`First action: open Diagnostics before Launch because Queue payload is unavailable: ${payload.error}`);
        } else if (scope.hiddenBlocked || scope.hiddenReview) {
          lines.push("First action: clear display filters or use the review views; the visible table can look safer than the backend queue evidence.");
        } else if (flaggedCount) {
          lines.push("First action: inspect flagged rows, collision risk, and selected-row diagnostics before opening Launch.");
        } else if (Number(payload.excluded_row_count || 0) > 0) {
          lines.push("First action: review Backend-Excluded Source Files so completed/history exclusions are understood before rerun decisions.");
        } else if (!rowList.length) {
          lines.push("First action: verify source roots, exclusions, and recent history before treating an empty Queue as safe.");
        } else {
          lines.push("First action: continue to Queue-to-Launch Handoff, then use Launch for backend authorization.");
        }
        lines.push("Boundary: attention evidence is read-only; Queue does not start work or submit display state as processing scope.");
        return lines;
      }

      function renderQueueAttentionSummary(queue = getLastQueuePayload(), rows = getLastQueueRows()) {
        const payload = queue || {};
        const rowList = Array.isArray(rows) ? rows : [];
        const status = queueAttentionStatus(payload, rowList);
        setText("queue-attention-status", status);
        const statusNode = byId("queue-attention-status");
        if (statusNode) {
          const normalized = String(status || "").toLowerCase();
          statusNode.dataset.state = normalized.includes("first") || normalized.includes("review") || normalized.includes("flagged") || normalized.includes("collision") || normalized.includes("exclusion") || normalized.includes("empty")
            ? "warning"
            : normalized.includes("blocker")
              ? "ready"
              : "changed";
        }
        setText("queue-attention-summary", queueAttentionSummaryLines(payload, rowList).join("\n"));
      }

    return { renderQueueDecisionHeader, renderQueueAttentionSummary };
  }
  window.__queueDecisionModule = { createQueueDecisionModule };
})();
