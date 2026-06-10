// dom/status.js
// Split child of domHelpers.js. Owns status normalization, chip rendering, and table legends.

/* eslint-disable complexity */
(function () {
  "use strict";

  function createDomStatusModule(deps = {}) {
    const setText = typeof deps.setText === "function" ? deps.setText : function () {};

    function normalizedTableStatus(value) {
      return String(value || "").trim().toLowerCase() || "normal";
    }

    function normalizeBackendStatusState(value) {
      const raw = normalizedTableStatus(value);
      const aliases = {
        error: "failed",
        failure: "failed",
        healthy: "match",
        ok: "match",
        complete: "completed",
        done: "completed",
        published: "completed",
        pending_publish: "parked",
        "pending publish": "parked",
        drain_pending: "queued",
        "drain pending": "queued",
        pending: "unknown",
        queued: "queued",
        queue: "queued",
        validation_needed: "validation-needed",
        health_check: "health-check",
        do_not_drain: "blocked",
        do_not_launch: "blocked",
        review: "warning",
        active: "running",
        unavailable: "unavailable",
        "not available": "unavailable",
        not_available: "unavailable",
      };
      const normalized = aliases[raw] || raw;
      return [
        "blocked",
        "failed",
        "warning",
        "ready",
        "match",
        "completed",
        "skipped",
        "parked",
        "publishing",
        "queued",
        "validation-needed",
        "health-check",
        "running",
        "paused",
        "retrying",
        "changed",
        "unavailable",
        "unknown",
        "empty",
        "normal",
      ].includes(normalized) ? normalized : "";
    }

    function backendRowStatusState(row, fallback) {
      const input = row && typeof row === "object" ? row : {};
      const operatorSeverity = normalizedTableStatus(input.operator_severity || "");
      const diagnosticSeverity = normalizedTableStatus(input.diagnostic_severity || "");
      const drainRecommendation = normalizedTableStatus(input.drain_recommendation || "");
      if (drainRecommendation === "do_not_drain" || input.local_exists === false) return "blocked";
      if (diagnosticSeverity === "error" || diagnosticSeverity === "critical") return "failed";
      if (operatorSeverity === "error" || operatorSeverity === "critical" || input.output_exists === false || input.blocked_reason || input.blocked_reason_code) return "blocked";
      const candidates = [
        input.operator_status_state,
        input.diagnostic_status_state,
        input.status_state,
        input.table_status_state,
        input.ui_status_state,
        fallback,
      ];
      for (const candidate of candidates) {
        const state = normalizeBackendStatusState(candidate);
        if ((state === "match" || state === "ready") && (operatorSeverity === "warning" || diagnosticSeverity === "warning")) return "warning";
        if (state && state !== "normal") return state;
      }
      return "";
    }

    function statusChipState(status, label) {
      const raw = normalizedTableStatus(status || label);
      if (["ok", "safe", "healthy", "match", "new"].includes(raw)) return "ok";
      if (["ready"].includes(raw)) return "ready";
      if (["completed", "complete", "done", "published"].includes(raw)) return "completed";
      if (["skipped", "skip", "excluded"].includes(raw)) return "skipped";
      if (["parked", "park", "pending_publish", "pending publish"].includes(raw)) return "parked";
      if (["queue_pending", "queue pending"].includes(raw)) return "queued";
      if (["drain_pending", "drain pending"].includes(raw)) return "queued";
      if (["health-check", "health_check", "health check"].includes(raw)) return "health-check";
      if (["failed", "failure", "error"].includes(raw)) return "failed";
      if (["blocked", "missing", "do_not_drain"].includes(raw)) return "blocked";
      if (["validation_needed", "validation-needed", "needs_validation"].includes(raw)) return "validation-needed";
      if (["unavailable", "not_available", "not available"].includes(raw)) return "unavailable";
      if (["unknown"].includes(raw)) return "unknown";
      if (["warning", "review", "limited", "hold", "held"].includes(raw)) return "warning";
      if (["changed"].includes(raw)) return "changed";
      if (["queued", "queue"].includes(raw)) return "queued";
      if (["pending"].includes(raw)) return "unknown";
      if (["active", "processing", "running", "encoding", "remuxing", "copying", "scanning", "validating"].includes(raw)) return "running";
      if (["paused", "pause_pending", "paused_pending"].includes(raw)) return "paused";
      if (["retrying", "retry"].includes(raw)) return "retrying";
      if (["publishing", "draining"].includes(raw)) return "publishing";
      if (raw.includes("fail") || raw.includes("error")) return "failed";
      if (raw.includes("block") || raw.includes("missing")) return "blocked";
      if (raw.includes("unavailable") || raw.includes("not available")) return "unavailable";
      if (raw.includes("unknown")) return "unknown";
      if (raw.includes("health-check") || raw.includes("health check")) return "health-check";
      if (raw.includes("warning") || raw.includes("review")) return "warning";
      if (raw.includes("validation")) return "validation-needed";
      if (raw.includes("retry")) return "retrying";
      if (raw.includes("publish") || raw.includes("drain")) return "publishing";
      if (raw.includes("queue")) return "queued";
      if (raw.includes("pause")) return "paused";
      if (raw.includes("running") || raw.includes("processing") || raw.includes("active")) return "running";
      if (raw.includes("skip") || raw.includes("exclude")) return "skipped";
      if (raw.includes("complete") || raw.includes("done")) return "completed";
      if (raw.includes("ready") || raw.includes("healthy") || raw.includes("ok")) return "ok";
      return "normal";
    }

    function makeStatusChip(label, status) {
      const span = document.createElement("span");
      const text = String(label || status || "unknown").trim() || "unknown";
      span.className = "status-chip";
      span.dataset.status = statusChipState(status, text);
      span.textContent = text;
      span.title = `Status: ${text}. Visual tone: ${span.dataset.status}.`;
      span.setAttribute("aria-label", span.title);
      return span;
    }

    function setCellStatusChip(cell, label, status) {
      if (!cell) return;
      const text = String(label || status || "unknown").trim() || "unknown";
      cell.textContent = text;
      cell.replaceChildren(makeStatusChip(text, status));
    }

    function tableStatusLegendText(tbody, label = "Table") {
      const rows = tbody ? Array.from(tbody.querySelectorAll('tr[data-selectable-row="true"]')) : [];
      if (!rows.length) return `${label}: no selectable rows.`;
      const counts = {};
      rows.forEach((row) => {
        const status = normalizedTableStatus(row.dataset.status);
        counts[status] = (counts[status] || 0) + 1;
      });
      const selectedCount = rows.filter((row) => row.classList.contains("is-selected")).length;
      const statusText = Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ");
      return `${label}: ${rows.length} selectable row${rows.length === 1 ? "" : "s"}, ${selectedCount} selected. Status mix: ${statusText}. Keyboard: Enter/Space selects focused row; Up/Down moves selection.`;
    }

    function updateTableStatusLegend(id, tbody, label = "Table") {
      setText(id, tableStatusLegendText(tbody, label));
    }

    return {
      normalizedTableStatus,
      normalizeBackendStatusState,
      backendRowStatusState,
      statusChipState,
      makeStatusChip,
      setCellStatusChip,
      tableStatusLegendText,
      updateTableStatusLegend,
    };
  }

  window.__domStatusModule = {
    createDomStatusModule,
  };
})();
