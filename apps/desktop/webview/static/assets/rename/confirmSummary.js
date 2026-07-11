// Rename confirmation summary renderer. Loaded before renameView.js.
(function () {
  "use strict";

  function createRenameConfirmSummaryModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const renameDuplicateTargets = typeof deps.renameDuplicateTargets === "function" ? deps.renameDuplicateTargets : function () { return []; };
    const renameLastApplyUndoCounts = typeof deps.renameLastApplyUndoCounts === "function" ? deps.renameLastApplyUndoCounts : function () { return { media: 0, sidecars: 0, totalOps: 0, manifestName: "" }; };

  function renameDialogById(id) {
    const el = byId(id);
    return el && typeof el.showModal === "function" ? el : null;
  }

  function renameConfirmBasename(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const normalized = text.replace(/\\/g, "/");
    return normalized.split("/").filter(Boolean).pop() || text;
  }

  function renameConfirmSourceName(item) {
    return String(item?.source_name || "").trim() || renameConfirmBasename(item?.source_path || item?.source);
  }

  function renameConfirmTargetName(item) {
    return String(item?.target_name || item?.final_name || item?.pipeline_guess || "").trim()
      || renameConfirmBasename(item?.destination || item?.target_path);
  }

  function renameConfirmSidecarCount(item) {
    const explicit = Number(item?.sidecar_count ?? item?.sidecars);
    if (Number.isFinite(explicit)) return Math.max(0, explicit);
    return Array.isArray(item?.sidecar_moves) ? item.sidecar_moves.length : 0;
  }

  function renameConfirmRowState(item) {
    const status = String(item?.status || "").trim().toLowerCase();
    const hasErrors = Array.isArray(item?.errors) && item.errors.length > 0;
    if (hasErrors || ["blocked", "failed", "error", "duplicate"].includes(status)) return "blocked";
    if (["warning", "review"].includes(status) || (Array.isArray(item?.warnings) && item.warnings.length > 0)) return "review";
    if (status === "match") return "match";
    return "ready";
  }

  function renameConfirmStatusToken(state) {
    if (state === "blocked") return { symbol: "×", label: "Blocked" };
    if (state === "review") return { symbol: "!", label: "Review" };
    if (state === "match") return { symbol: "=", label: "Match" };
    return { symbol: "✓", label: "Ready" };
  }

  function renameConfirmSequenceText(rows) {
    if (!rows.length) return "No rename rows selected";
    const first = renameConfirmTargetName(rows[0]);
    const last = renameConfirmTargetName(rows[rows.length - 1]);
    if (!first && !last) return "No target names reported";
    if (!last || first === last) return first || last;
    return `${first} -> ${last}`;
  }

  function renameConfirmCounts(rows) {
    const duplicateTargets = typeof renameDuplicateTargets === "function" ? renameDuplicateTargets(rows) : [];
    const existingDestinations = rows.filter((row) => Boolean(row?.destination_exists) && !row?.matches_target).length;
    return rows.reduce((acc, row) => {
      const state = renameConfirmRowState(row);
      acc[state] = (acc[state] || 0) + 1;
      acc.sidecars += renameConfirmSidecarCount(row);
      return acc;
    }, {
      ready: 0,
      match: 0,
      review: 0,
      blocked: 0,
      sidecars: 0,
      conflicts: duplicateTargets.length,
      existingDestinations,
    });
  }

  function renameConfirmAppendText(parent, className, text) {
    const node = document.createElement("span");
    node.className = className;
    node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function renameConfirmStatusBadge(state) {
    const token = renameConfirmStatusToken(state);
    const badge = document.createElement("span");
    badge.className = `rename-confirm-status-badge rename-confirm-status-${state}`;
    badge.title = token.label;
    badge.setAttribute("aria-label", token.label);
    badge.textContent = token.symbol;
    return badge;
  }

  function renderRenameConfirmSummary(listEl, rowsToApply, outsideRootRows) {
    if (!listEl) return;
    if (typeof listEl.replaceChildren === "function") listEl.replaceChildren();
    else listEl.innerHTML = "";
    const counts = renameConfirmCounts(rowsToApply);
    const primaryState = counts.blocked ? "blocked" : counts.review ? "review" : "ready";

    const summary = document.createElement("div");
    summary.className = "rename-confirm-summary";

    const metrics = document.createElement("div");
    metrics.className = "rename-confirm-metrics";
    [
      [`${rowsToApply.length} media file${rowsToApply.length === 1 ? "" : "s"} ready`, "Media"],
      [`${counts.sidecars} matching sidecar${counts.sidecars === 1 ? "" : "s"} will move`, "Sidecars"],
    ].forEach(([value, label]) => {
      const metric = document.createElement("div");
      metric.className = "rename-confirm-metric";
      renameConfirmAppendText(metric, "rename-confirm-metric-value", value);
      renameConfirmAppendText(metric, "rename-confirm-metric-label", label);
      metrics.appendChild(metric);
    });
    summary.appendChild(metrics);

    const sequence = document.createElement("div");
    sequence.className = "rename-confirm-sequence";
    renameConfirmAppendText(sequence, "rename-confirm-label", "Sequence");
    renameConfirmAppendText(sequence, "rename-confirm-sequence-value", renameConfirmSequenceText(rowsToApply));
    summary.appendChild(sequence);

    const health = document.createElement("div");
    health.className = "rename-confirm-health";
    const batchBadge = renameConfirmStatusBadge(primaryState);
    health.appendChild(batchBadge);
    renameConfirmAppendText(health, "rename-confirm-health-label", renameConfirmStatusToken(primaryState).label);
    [
      `${counts.blocked} blocked`,
      `${counts.conflicts} conflicts`,
      `${counts.existingDestinations} existing destinations`,
    ].forEach((label) => renameConfirmAppendText(health, "rename-confirm-health-chip", label));
    summary.appendChild(health);
    listEl.appendChild(summary);

    const details = document.createElement("details");
    details.className = "rename-confirm-details";
    const detailsSummary = document.createElement("summary");
    detailsSummary.textContent = "Show details";
    details.appendChild(detailsSummary);
    const table = document.createElement("div");
    table.className = "rename-confirm-detail-table";
    table.setAttribute("role", "table");
    const header = document.createElement("div");
    header.className = "rename-confirm-detail-row rename-confirm-detail-header";
    header.setAttribute("role", "row");
    ["Status", "Original", "New name", "Sidecars"].forEach((label) => {
      const cell = document.createElement("span");
      cell.setAttribute("role", "columnheader");
      cell.textContent = label;
      header.appendChild(cell);
    });
    table.appendChild(header);
    rowsToApply.forEach((item) => {
      const state = renameConfirmRowState(item);
      const row = document.createElement("div");
      row.className = `rename-confirm-detail-row rename-confirm-detail-row-${state}`;
      row.setAttribute("role", "row");
      const statusCell = document.createElement("span");
      statusCell.setAttribute("role", "cell");
      statusCell.appendChild(renameConfirmStatusBadge(state));
      row.appendChild(statusCell);
      [renameConfirmSourceName(item), renameConfirmTargetName(item), String(renameConfirmSidecarCount(item))].forEach((value) => {
        const cell = document.createElement("span");
        cell.setAttribute("role", "cell");
        cell.textContent = value;
        row.appendChild(cell);
      });
      table.appendChild(row);
      if (state === "review" || state === "blocked") {
        const evidence = document.createElement("div");
        evidence.className = "rename-confirm-detail-row rename-confirm-detail-evidence";
        evidence.setAttribute("role", "row");
        evidence.textContent = [
          ...(Array.isArray(item.warnings) ? item.warnings : []),
          ...(Array.isArray(item.errors) ? item.errors : []),
          item.destination_exists && !item.matches_target ? `Destination exists: ${item.destination || item.target_path || renameConfirmTargetName(item)}` : "",
          Array.isArray(outsideRootRows) && outsideRootRows.includes(item) && state === "blocked" ? `Path evidence: ${item.source || item.source_path || renameConfirmSourceName(item)}` : "",
        ].filter(Boolean).join(" ");
        if (evidence.textContent) table.appendChild(evidence);
      }
    });
    details.appendChild(table);
    listEl.appendChild(details);
  }

  function renderRenameUndoConfirmSummary(listEl) {
    if (!listEl) return;
    if (typeof listEl.replaceChildren === "function") listEl.replaceChildren();
    else listEl.innerHTML = "";
    const counts = renameLastApplyUndoCounts();

    const summary = document.createElement("div");
    summary.className = "rename-confirm-summary";

    const metrics = document.createElement("div");
    metrics.className = "rename-confirm-metrics";
    [
      [`${counts.media} media file${counts.media === 1 ? "" : "s"} will restore`, "Media"],
      [`${counts.sidecars} matching sidecar${counts.sidecars === 1 ? "" : "s"} will move back`, "Sidecars"],
      [`${counts.totalOps} total operation${counts.totalOps === 1 ? "" : "s"}`, "Scope"],
    ].forEach(([value, label]) => {
      const metric = document.createElement("div");
      metric.className = "rename-confirm-metric";
      renameConfirmAppendText(metric, "rename-confirm-metric-value", value);
      renameConfirmAppendText(metric, "rename-confirm-metric-label", label);
      metrics.appendChild(metric);
    });
    summary.appendChild(metrics);

    const manifest = document.createElement("div");
    manifest.className = "rename-confirm-sequence";
    renameConfirmAppendText(manifest, "rename-confirm-label", "Undo manifest");
    renameConfirmAppendText(manifest, "rename-confirm-sequence-value", counts.manifestName);
    summary.appendChild(manifest);

    const health = document.createElement("div");
    health.className = "rename-confirm-health";
    health.appendChild(renameConfirmStatusBadge("review"));
    renameConfirmAppendText(health, "rename-confirm-health-label", "Confirm restore");
    renameConfirmAppendText(health, "rename-confirm-health-chip", "last apply only");
    renameConfirmAppendText(health, "rename-confirm-health-chip", "backend undo");
    summary.appendChild(health);
    listEl.appendChild(summary);
  }


    return {
      renameConfirmBasename, renameDialogById, renderRenameConfirmSummary, renderRenameUndoConfirmSummary,
    };
  }

  window.__renameConfirmSummaryModule = { createRenameConfirmSummaryModule };
})();
