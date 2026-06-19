// dom/status.js
// Split child of domHelpers.js. Owns status normalization, chip rendering, and table legends.

/* eslint-disable complexity */
(function () {
  "use strict";

  function createDomStatusModule(deps = {}) {
    const setText = typeof deps.setText === "function" ? deps.setText : function () {};
    const byId = typeof deps.byId === "function" ? deps.byId : (id) => document.getElementById(id);

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
        loading: "loading",
        updating: "loading",
        requesting: "loading",
        stale: "warning",
        partial: "warning",
        canceled: "warning",
        cancelled: "warning",
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
        "loading",
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

    function normalizePanelStatusState(state, message) {
      const explicit = normalizeBackendStatusState(state);
      if (explicit) {
        if (explicit === "failed" || explicit === "unavailable") return "blocked";
        if (explicit === "match" || explicit === "completed") return "ready";
        return explicit;
      }
      const text = String(message || state || "").trim().toLowerCase();
      if (!text) return "empty";
      if (text === "idle" || text === "not loaded" || text === "no rows" || text === "none"
          || text.startsWith("no ")) return "empty";
      if (text.includes("loading") || text.includes("reading") || text.includes("opening")
          || text.includes("requesting") || text.includes("running") || text.includes("busy")) return "loading";
      if (text.includes("cancel")) return "warning";
      if (text.includes("stale") || text.includes("partial") || text.includes("warning")
          || text.includes("review") || text.includes("truncated") || text.includes("unavailable")) return "warning";
      if (text.includes("blocked") || text.includes("failed") || text.includes("error")
          || text.includes("missing") || text.includes("denied")) return "blocked";
      if (text.includes("loaded") || text.includes("complete") || text.includes("ready")
          || text.includes("safe") || text.includes("ok")) return "ready";
      return "unknown";
    }

    function setPanelStatus(id, message, state) {
      setText(id, message);
      const node = byId(id);
      if (!node) return "";
      const normalized = normalizePanelStatusState(state, message);
      node.dataset.state = normalized;
      node.setAttribute("role", "status");
      node.setAttribute("aria-live", "polite");
      return normalized;
    }

    let inlineActionStatusSequence = 0;

    function ensureInlineActionStatus(button) {
      if (!button || !button.insertAdjacentElement) return null;
      const describedBy = button.getAttribute("aria-describedby") || "";
      const existing = describedBy ? document.getElementById(describedBy) : null;
      if (existing?.classList?.contains("inline-action-status")) return existing;
      const next = button.nextElementSibling;
      if (next?.classList?.contains("inline-action-status")) return next;
      inlineActionStatusSequence += 1;
      const status = document.createElement("span");
      status.id = `inline-action-status-${inlineActionStatusSequence}`;
      status.className = "inline-action-status";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      button.setAttribute("aria-describedby", status.id);
      button.insertAdjacentElement("afterend", status);
      return status;
    }

    function setInlineActionStatus(button, message, state) {
      const status = ensureInlineActionStatus(button);
      if (!status) return "";
      const normalized = normalizePanelStatusState(state, message);
      status.textContent = String(message || "");
      status.dataset.state = normalized;
      if (button?.dataset) button.dataset.state = normalized;
      return normalized;
    }

    function setActionBusy(button, isBusy, message) {
      if (!button) return;
      const busy = Boolean(isBusy);
      button.disabled = busy;
      button.setAttribute("aria-busy", busy ? "true" : "false");
      if (message) setInlineActionStatus(button, message, busy ? "loading" : undefined);
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

    function reviewTileTone(tone) {
      const raw = normalizedTableStatus(tone);
      if (["danger", "error", "failed", "failure", "blocked", "critical"].includes(raw)) return "danger";
      if (["warning", "warn", "review", "stale", "partial", "changed", "validation-needed"].includes(raw)) return "warning";
      if (["success", "ok", "safe", "ready", "match", "completed", "complete", "healthy"].includes(raw)) return "success";
      if (["info", "running", "active", "loading", "queued", "publishing", "draining"].includes(raw)) return "info";
      return "muted";
    }

    function makeReviewTile(tile = {}) {
      const input = tile && typeof tile === "object" ? tile : {};
      const node = document.createElement("section");
      node.className = "review-tile";
      if (input.wide) node.classList.add("review-tile-wide");
      node.dataset.tone = reviewTileTone(input.tone);
      const label = document.createElement("span");
      label.className = "review-tile-label";
      label.textContent = String(input.label || "Status").trim() || "Status";
      const value = document.createElement("strong");
      value.className = "review-tile-value";
      value.textContent = String(input.value ?? "Not loaded").trim() || "Not loaded";
      const detail = document.createElement("span");
      detail.className = "review-tile-detail";
      detail.textContent = String(input.detail ?? "").trim();
      node.append(label, value, detail);
      node.title = [label.textContent, value.textContent, detail.textContent].filter(Boolean).join(": ");
      return node;
    }

    function renderReviewTileBoard(targetId, tiles, options = {}) {
      const target = typeof targetId === "string" ? byId(targetId) : targetId;
      if (!target) return 0;
      const rows = Array.isArray(tiles) ? tiles.filter(Boolean) : [];
      const emptyTile = options && options.emptyTile;
      const renderedTiles = rows.length ? rows : (emptyTile ? [emptyTile] : []);
      target.replaceChildren(...renderedTiles.map((tile) => makeReviewTile(tile)));
      return renderedTiles.length;
    }

    return {
      normalizedTableStatus,
      normalizeBackendStatusState,
      backendRowStatusState,
      statusChipState,
      normalizePanelStatusState,
      setPanelStatus,
      setInlineActionStatus,
      setActionBusy,
      makeStatusChip,
      setCellStatusChip,
      tableStatusLegendText,
      updateTableStatusLegend,
      reviewTileTone,
      makeReviewTile,
      renderReviewTileBoard,
    };
  }

  window.__domStatusModule = {
    createDomStatusModule,
  };
})();
