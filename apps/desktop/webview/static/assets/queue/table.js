// queue/table.js
// Split child of queueView.js. Loaded before queueView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  function fallbackString(value) {
    return String(value || "");
  }

  function splitRouteName(routeName) {
    const raw = String(routeName || "").trim();
    const match = raw.match(/^([^()]+?)\s*\(([^)]+)\)$/);
    return {
      raw,
      label: match ? match[1].trim() : raw,
      evidence: match ? match[2].trim() : "",
    };
  }

  function formatQueueEvidenceText(value) {
    return String(value || "")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function queueSubtitleQaEvidence(item) {
    const qa = item && typeof item.subtitle_qa === "object" ? item.subtitle_qa : null;
    if (!qa) return "";
    const posture = String(qa.posture || "").toLowerCase();
    if (posture === "blocked") return "Subtitle QA blocked";
    if (posture === "review") return "Subtitle QA review";
    if (posture === "unknown") return "Subtitle QA unknown";
    return "";
  }

  function queueLaunchCheckEvidenceText(item, routeParts, short) {
    const candidates = short
      ? [routeParts?.evidence, item?.route_reason_code, item?.route_decision_summary, item?.route_reason, item?.operator_status]
      : [routeParts?.evidence, item?.route_reason, item?.route_decision_summary, item?.route_reason_code, item?.operator_status];
    const evidence = candidates.map(formatQueueEvidenceText).find(Boolean) || "Ready";
    return evidence.toLowerCase().includes("checks at launch") ? evidence : `${evidence}; checks at launch`;
  }

  function queueEvidenceText(item, routeParts, queueTableRowStatus) {
    const status = queueTableRowStatus(item);
    if (status === "launch-check") return queueLaunchCheckEvidenceText(item, routeParts, false);
    const candidates = [];
    if (status === "blocked" || status === "failed") {
      candidates.push(item.blocked_reason_code, item.blocked_reason, item.operator_status);
    }
    if (queueRuntimeStoppedByRequest(item)) {
      candidates.push(item.operator_status, item.runtime_outcome_reason, item.runtime_outcome_error_code);
    }
    candidates.push(
      queueSubtitleQaEvidence(item),
      routeParts?.evidence,
      item.route_reason_code,
      item.route_decision_summary,
      item.route_reason,
      item.operator_status,
      item.safe_next_action
    );
    const evidence = candidates.map(formatQueueEvidenceText).find(Boolean);
    return evidence || "Ready";
  }

  function queueShortEvidenceText(item, routeParts, queueTableRowStatus) {
    const status = queueTableRowStatus(item);
    if (status === "launch-check") return queueLaunchCheckEvidenceText(item, routeParts, true);
    const evidence = queueEvidenceText(item, routeParts, queueTableRowStatus);
    const normalized = evidence.toLowerCase();
    if (normalized.includes("codec check pending")) return "Codec pending";
    if (normalized.includes("codec probe still required")) return "Codec pending";
    if (normalized === "size within threshold") return "Size ok";
    return evidence;
  }

  function queueIsRunnableWarning(item, status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized !== "warning") return false;
    if (String(item?.operator_severity || "").toLowerCase() !== "ok") return false;
    return String(item?.operator_status || "").toLowerCase() === "ready"
      || String(item?.operator_trust_state || "").toLowerCase() === "launch-check-needed"
      || Boolean(item?.runtime_checks_deferred);
  }

  function queueRuntimeStoppedByRequest(item) {
    const runtimeStatus = String(item?.runtime_outcome_status || "").toLowerCase();
    const runtimeError = String(item?.runtime_outcome_error_code || "").toLowerCase();
    const runtimeReason = String(item?.runtime_outcome_reason || "").toLowerCase();
    return runtimeStatus === "stopped" && (runtimeError === "stop_requested" || (runtimeReason.includes("stop") && runtimeReason.includes("operator")));
  }

  function queueDisplayRowStatus(item, queueTableRowStatus) {
    const status = queueTableRowStatus(item);
    if (String(status || "").toLowerCase() === "launch-check") return "launch-check";
    return queueIsRunnableWarning(item, status) ? "ready" : status;
  }

  function queueStateFromItem(item, status) {
    const normalized = String(status || "").toLowerCase();
    const normalizedState = normalized.replace(/[_\s]+/g, "-");
    if (item?.blocked_reason || item?.blocked_reason_code) return { label: "Blocked", state: "blocked" };
    if (normalizedState === "blocked" || normalizedState === "failed") return { label: "Blocked", state: "blocked" };
    if (normalizedState === "completed" || normalizedState === "skipped") return { label: "Done", state: "done" };
    if (normalizedState === "pending-publish") return { label: "Pending Publish", state: "parked" };
    if (normalizedState === "parked" || normalizedState === "review-workspace") return { label: "Parked", state: "parked" };
    if (normalizedState === "launch-check") return { label: "Launch Check", state: "launch-check" };
    if (queueIsRunnableWarning(item, normalized)) return { label: "Review", state: "review" };
    if (["warning", "review", "changed", "validation-needed", "health-check", "paused", "retrying", "unknown", "empty"].includes(normalizedState)) {
      return { label: "Review", state: "review" };
    }
    return { label: "Queued", state: "queued" };
  }

  function makeQueueStateChip(item, status) {
    const state = queueStateFromItem(item, status);
    const span = document.createElement("span");
    span.className = "queue-state-chip";
    span.dataset.state = state.state;
    span.textContent = state.label;
    return span;
  }

  function queueNormalizePathKey(value) {
    return String(value || "")
      .replace(/\\/g, "/")
      .replace(/\/+/g, "/")
      .trim()
      .toLowerCase();
  }

  function queueBasenameKey(value) {
    const normalized = queueNormalizePathKey(value);
    return normalized.split("/").filter(Boolean).pop() || normalized;
  }

  function queueIsOverrideArtifactRow(item) {
    const values = [item?.source_path, item?.relative_path, item?.display_name, item?.name].map(queueNormalizePathKey);
    return values.some((value) => /\.override\.json$/i.test(value) || /(^|\/)override\.json$/i.test(value));
  }

  function queueStripOverrideSuffix(value) {
    return queueNormalizePathKey(value)
      .replace(/\.mediapipeline\.override\.json$/i, "")
      .replace(/\.override\.json$/i, "")
      .replace(/(^|\/)override\.json$/i, "");
  }

  function queueOverrideTargetKeys(rows) {
    const keys = new Set();
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      [row?.source_path, row?.relative_path, row?.display_name, row?.name].forEach((value) => {
        const target = queueStripOverrideSuffix(value);
        if (!target) return;
        keys.add(target);
        keys.add(queueBasenameKey(target));
      });
    });
    return keys;
  }

  function queueRowCandidateKeys(item) {
    const keys = new Set();
    [item?.source_path, item?.relative_path, item?.display_name, item?.name].forEach((value) => {
      const key = queueNormalizePathKey(value);
      if (!key) return;
      keys.add(key);
      keys.add(queueBasenameKey(key));
    });
    return keys;
  }

  function queueRowHasOverride(item, overrideTargetKeys) {
    if (item?.has_override || item?.has_file_override || item?.file_override || item?.file_override_path) return true;
    if (!overrideTargetKeys || typeof overrideTargetKeys.has !== "function") return false;
    const candidates = queueRowCandidateKeys(item);
    return Array.from(candidates).some((key) => overrideTargetKeys.has(key));
  }

  function queueRowWithOverrideMarker(item, overrideTargetKeys) {
    if (!item || typeof item !== "object") return item;
    if (!queueRowHasOverride(item, overrideTargetKeys)) return item;
    return { ...item, __queue_has_override: true };
  }

  function makeOverrideChip(item) {
    const span = document.createElement("span");
    span.className = "queue-override-chip";
    if (item?.__queue_has_override || item?.has_override || item?.has_file_override || item?.file_override || item?.file_override_path) {
      span.dataset.state = "active";
      span.textContent = "Override";
      span.title = "Per-file override is present for this media row.";
    } else {
      span.dataset.state = "none";
      span.textContent = "";
      span.title = "No per-file override marker found.";
    }
    return span;
  }

  function makeRouteChip(routeName) {
    const span = document.createElement("span");
    const normalized = String(routeName || "").toLowerCase();
    const routeParts = splitRouteName(routeName);
    let category = "";
    if (normalized.includes("remux")) category = "remux";
    else if (normalized.includes("encode") || normalized.includes("transcode")) category = "encode";
    else if (normalized === "skip" || normalized.includes("skip")) category = "skip";
    else if (normalized.includes("review") || normalized.includes("blocked")) category = "review";
    span.className = "route-chip";
    if (category) span.dataset.route = category;
    span.textContent = routeParts.label || "Pending";
    if (routeParts.raw) span.title = routeParts.raw;
    return span;
  }

  function queueEffectivePriorityLevel(item) {
    const manifestLevel = String(item.manifest_priority_level || "normal").toLowerCase();
    return Boolean(item.is_priority) && manifestLevel === "normal" ? "fs" : manifestLevel;
  }

  function queueRowNameParts(item, shortenPath) {
    const raw = item.display_name || item.relative_path || item.source_path || "";
    const metaRaw = item.relative_path && item.relative_path !== raw ? item.relative_path : item.source_path || "";
    return {
      raw,
      display: shortenPath(raw, 40),
      meta: shortenPath(metaRaw, 56),
    };
  }

  function appendQueueTitleCell(cell, nameParts) {
    if (!cell) return;
    cell.textContent = "";
    const title = document.createElement("span");
    title.className = "queue-title-main";
    title.textContent = nameParts.display || "(untitled)";
    cell.appendChild(title);
    if (nameParts.meta && nameParts.meta !== nameParts.display) {
      const meta = document.createElement("span");
      meta.className = "queue-title-meta";
      meta.textContent = nameParts.meta;
      cell.appendChild(meta);
    }
    if (nameParts.raw) cell.title = nameParts.raw;
  }

  function appendQueuePriorityBadge(cell, level) {
    if (!cell || level === "normal") return;
    const badge = document.createElement("span");
    badge.className = "priority-badge";
    badge.dataset.level = level;
    const labels = { high: "High", low: "Low", hold: "Hold", fs: "FS" };
    badge.textContent = labels[level] || level.toUpperCase();
    cell.appendChild(badge);
  }

  function createQueueFileSettingsButton(item) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "fo-open-btn queue-row-action-button";
    button.textContent = "⚙";
    button.title = "File settings";
    button.setAttribute("aria-label", `Open file settings for ${item.display_name || item.relative_path || item.source_path || "queue row"}`);
    if (item.__queue_has_override || item.has_override || item.has_file_override || item.file_override || item.file_override_path) {
      button.dataset.hasOverride = "true";
    }
    const sourcePath = item.source_path || "";
    if (sourcePath) button.dataset.sourcePath = sourcePath;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openFileSettingsDrawer(item, { trigger: button });
    });
    return button;
  }

  function appendQueueFileSettingsButton(cell, item) {
    if (cell) cell.appendChild(createQueueFileSettingsButton(item));
  }

  function appendQueueRowCells(row, item, visibleIndex, context) {
    const level = queueEffectivePriorityLevel(item);
    const routeParts = splitRouteName(item.route_name || "");
    appendCells(row, [
      visibleIndex + 1,
      "",
      "",
      item.media_type || "",
      "",
      queueShortEvidenceText(item, routeParts, context.queueTableRowStatus),
      "",
      "",
      "",
    ], ["num", "queue-state-cell", "queue-title-cell", null, "queue-route-cell", "queue-evidence-cell", "queue-priority-cell", "queue-override-cell", "settings-col"]);
    return { cells: row.querySelectorAll("td"), level, routeParts };
  }

  function decorateQueueRowCells(cells, item, level, routeParts, context) {
    const backendOrder = item.global_order || item.queue_index || "";
    if (cells[0] && backendOrder) cells[0].title = `Backend queue order: ${backendOrder}`;
    if (cells[1]) cells[1].appendChild(makeQueueStateChip(item, context.queueTableRowStatus(item)));
    appendQueueTitleCell(cells[2], queueRowNameParts(item, context.shortenPath));
    if (cells[4]) cells[4].appendChild(makeRouteChip(item.route_name || ""));
    if (cells[5]) cells[5].title = queueEvidenceText(item, routeParts, context.queueTableRowStatus);
    appendQueuePriorityBadge(cells[6], level);
    if (cells[7]) cells[7].appendChild(makeOverrideChip(item));
    appendQueueFileSettingsButton(cells[8], item);
  }

  function renderQueueTableRow(item, visibleIndex, context) {
    const row = document.createElement("tr");
    const key = context.queueRowKey(item);
    const level = queueEffectivePriorityLevel(item);
    const selectedKeys = context.selectedQueuePriorityRowKeys instanceof Set
      ? context.selectedQueuePriorityRowKeys
      : new Set(Array.isArray(context.selectedQueuePriorityRowKeys) ? context.selectedQueuePriorityRowKeys : []);
    const selected = selectedKeys.size
      ? Boolean(key && selectedKeys.has(key))
      : Boolean(key && key === context.selectedQueueRowKey);
    row.dataset.rowKey = key;
    row.dataset.status = String(context.queueTableRowStatus(item) || "queued");
    row.dataset.filterStatus = queueDisplayRowStatus(item, context.queueTableRowStatus);
    if (level !== "normal") row.dataset.priorityLevel = level;
    if (selected) row.dataset.prioritySelected = "true";
    if (context.manualOrderEnabled) row.dataset.manualOrderDraggable = "true";
    const rendered = appendQueueRowCells(row, item, visibleIndex, context);
    decorateQueueRowCells(rendered.cells, item, rendered.level, rendered.routeParts, context);
    context.makeRowSelectable(row, (event) => context.selectQueueRow(item, event), {
      selected,
      label: `Queue row ${item.display_name || item.relative_path || item.source_path || ""}`,
    });
    if (typeof context.wireManualOrderRow === "function") context.wireManualOrderRow(row, item);
    context.tbody.appendChild(row);
  }

  function renderQueueTableRows(context) {
    if (!context?.tbody) return;
    const rows = Array.isArray(context.rows) ? context.rows : [];
    rows.forEach((item, index) => renderQueueTableRow(item, index, context));
  }

  function createQueueTableModule({
    appendCells: appendCellsDependency,
    makeRowSelectable,
    queueRowKey,
    queueTableRowStatus,
    selectQueueRow,
    shortenPath,
    wireManualOrderRow,
  } = {}) {
    appendCells = typeof appendCellsDependency === "function" ? appendCellsDependency : function () {};
    makeRowSelectable = typeof makeRowSelectable === "function" ? makeRowSelectable : function () {};
    queueRowKey = typeof queueRowKey === "function" ? queueRowKey : function () { return ""; };
    queueTableRowStatus = typeof queueTableRowStatus === "function" ? queueTableRowStatus : function () { return "queued"; };
    selectQueueRow = typeof selectQueueRow === "function" ? selectQueueRow : function () {};
    shortenPath = typeof shortenPath === "function" ? shortenPath : fallbackString;
    wireManualOrderRow = typeof wireManualOrderRow === "function" ? wireManualOrderRow : function () {};

    return {
      splitRouteName,
      formatQueueEvidenceText,
      queueEvidenceText: (item, routeParts) => queueEvidenceText(item, routeParts, queueTableRowStatus),
      queueShortEvidenceText: (item, routeParts) => queueShortEvidenceText(item, routeParts, queueTableRowStatus),
      queueIsRunnableWarning,
      queueDisplayRowStatus: (item) => queueDisplayRowStatus(item, queueTableRowStatus),
      makeQueueStateChip,
      queueNormalizePathKey,
      queueBasenameKey,
      queueIsOverrideArtifactRow,
      queueOverrideTargetKeys,
      queueRowWithOverrideMarker,
      makeOverrideChip,
      makeRouteChip,
      setOpenFileSettingsDrawer: (handler) => {
        openFileSettingsDrawer = typeof handler === "function" ? handler : function () {};
      },
      renderQueueTableRows: (context = {}) => renderQueueTableRows({
        ...context,
        appendCells,
        makeRowSelectable,
        queueRowKey,
        queueTableRowStatus,
        selectQueueRow,
        shortenPath,
        wireManualOrderRow,
      }),
    };
  }

  let appendCells = function () {};
  let openFileSettingsDrawer = function () {};

  window.__queueTableModule = { createQueueTableModule };
})();
