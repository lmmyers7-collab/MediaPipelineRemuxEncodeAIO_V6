// queue/selection.js
// Split child of queueView.js. Loaded before queueView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  function createQueueSelectionModule({
    getCommandHistory,
    getLastQueueExcludedRows,
    getLastQueuePayload,
    getLastQueueRows,
    renderQueueBackendLaunchScopePreview,
    renderQueueDetail,
    renderQueueExcluded,
    renderQueueExcludedDetail,
    renderQueueLaunchDecisionChecklist,
    renderQueueReviewDigest,
    renderQueueRows,
    updateQueueSelectionVisuals,
    setText,
  } = {}) {
    let selectedQueueRowKey = "";
    let selectedQueueExcludedRowKey = "";
    let selectedQueuePriorityRowKeys = new Set();
    let selectedQueuePriorityAnchorKey = "";
    let lastRenderedQueueRows = [];

    const safeArray = (value) => Array.isArray(value) ? value : [];
    const safePayload = () => {
      const payload = typeof getLastQueuePayload === "function" ? getLastQueuePayload() : {};
      return payload && typeof payload === "object" ? payload : {};
    };
    const safeRows = () => safeArray(typeof getLastQueueRows === "function" ? getLastQueueRows() : []);
    const safeExcludedRows = () => safeArray(typeof getLastQueueExcludedRows === "function" ? getLastQueueExcludedRows() : []);
    const safeHistory = () => safeArray(typeof getCommandHistory === "function" ? getCommandHistory() : []);
    const safeSetText = typeof setText === "function" ? setText : function () {};

    function queueRowKey(item) {
      if (item?.row_key) return String(item.row_key).toLocaleLowerCase();
      return [
        item?.source_path || "",
        item?.global_order || "",
        item?.queue_index || "",
        item?.route_name || "",
      ].join("\u001f").toLocaleLowerCase();
    }

    function queueExcludedRowKey(item) {
      if (item?.row_key) return String(item.row_key).toLocaleLowerCase();
      return [
        item?.source_path || "",
        item?.source_order || "",
        item?.reason_code || "",
      ].join("\u001f").toLocaleLowerCase();
    }

    function getSelectedQueueRowKey() {
      return selectedQueueRowKey;
    }

    function getSelectedQueuePriorityRowKeys() {
      return Array.from(selectedQueuePriorityRowKeys);
    }

    function getSelectedQueueExcludedRowKey() {
      return selectedQueueExcludedRowKey;
    }

    function getSelectedQueueRow() {
      if (!selectedQueueRowKey) return null;
      return safeRows().find((row) => queueRowKey(row) === selectedQueueRowKey) || null;
    }

    function getSelectedQueuePriorityRows() {
      if (!selectedQueuePriorityRowKeys.size) return [];
      return safeRows().filter((row) => selectedQueuePriorityRowKeys.has(queueRowKey(row)));
    }

    function getSelectedQueueExcludedRow() {
      if (!selectedQueueExcludedRowKey) return null;
      return safeExcludedRows().find((row) => queueExcludedRowKey(row) === selectedQueueExcludedRowKey) || null;
    }

    function syncSelectedQueueRows(rows, excludedRows) {
      const runnableRows = safeArray(rows);
      const filteredRows = safeArray(excludedRows);
      const runnableKeys = new Set(runnableRows.map(queueRowKey).filter(Boolean));
      if (selectedQueueRowKey && !runnableRows.some((row) => queueRowKey(row) === selectedQueueRowKey)) {
        selectedQueueRowKey = "";
      }
      selectedQueuePriorityRowKeys = new Set(
        Array.from(selectedQueuePriorityRowKeys).filter((key) => runnableKeys.has(key))
      );
      if (!selectedQueueRowKey && selectedQueuePriorityRowKeys.size) {
        const selectedRow = runnableRows.find((row) => selectedQueuePriorityRowKeys.has(queueRowKey(row)));
        selectedQueueRowKey = selectedRow ? queueRowKey(selectedRow) : "";
      }
      if (selectedQueueRowKey && !selectedQueuePriorityRowKeys.size) {
        selectedQueuePriorityRowKeys.add(selectedQueueRowKey);
      }
      if (selectedQueuePriorityAnchorKey && !runnableKeys.has(selectedQueuePriorityAnchorKey)) {
        selectedQueuePriorityAnchorKey = selectedQueueRowKey;
      }
      lastRenderedQueueRows = lastRenderedQueueRows.filter((row) => runnableKeys.has(queueRowKey(row)));
      if (selectedQueueExcludedRowKey && !filteredRows.some((row) => queueExcludedRowKey(row) === selectedQueueExcludedRowKey)) {
        selectedQueueExcludedRowKey = "";
      }
    }

    function setRenderedQueueRows(rows) {
      lastRenderedQueueRows = safeArray(rows).slice();
    }

    function queuePrioritySelectionMode(event) {
      if (!event || typeof event !== "object") return "replace";
      if (event.shiftKey) return "range";
      if (event.ctrlKey || event.metaKey || event.key === " ") return "toggle";
      return "replace";
    }

    function queuePriorityRangeKeys(targetKey) {
      if (!targetKey) return [];
      const renderedRows = lastRenderedQueueRows.length ? lastRenderedQueueRows : safeRows();
      const anchorKey = selectedQueuePriorityAnchorKey || selectedQueueRowKey || targetKey;
      const anchorIndex = renderedRows.findIndex((row) => queueRowKey(row) === anchorKey);
      const targetIndex = renderedRows.findIndex((row) => queueRowKey(row) === targetKey);
      if (anchorIndex < 0 || targetIndex < 0) return [targetKey];
      const start = Math.min(anchorIndex, targetIndex);
      const end = Math.max(anchorIndex, targetIndex);
      return renderedRows.slice(start, end + 1).map(queueRowKey).filter(Boolean);
    }

    function firstSelectedQueuePriorityKey() {
      const rows = safeRows();
      const selected = rows.find((row) => selectedQueuePriorityRowKeys.has(queueRowKey(row)));
      return selected ? queueRowKey(selected) : "";
    }

    function updateQueuePrioritySelection(item, event) {
      if (!item) return;
      const key = queueRowKey(item);
      if (!key) return;
      const mode = queuePrioritySelectionMode(event);
      if (mode === "range") {
        queuePriorityRangeKeys(key).forEach((rowKey) => selectedQueuePriorityRowKeys.add(rowKey));
        if (!selectedQueuePriorityAnchorKey) selectedQueuePriorityAnchorKey = key;
      } else if (mode === "toggle") {
        if (selectedQueuePriorityRowKeys.has(key) && selectedQueuePriorityRowKeys.size > 1) {
          selectedQueuePriorityRowKeys.delete(key);
        } else {
          selectedQueuePriorityRowKeys.add(key);
        }
        selectedQueuePriorityAnchorKey = key;
      } else {
        selectedQueuePriorityRowKeys = new Set([key]);
        selectedQueuePriorityAnchorKey = key;
      }
      selectedQueueRowKey = selectedQueuePriorityRowKeys.has(key) ? key : firstSelectedQueuePriorityKey() || key;
    }

    function renderLaunchSelectionSurfaces(payload, rows) {
      if (typeof renderQueueBackendLaunchScopePreview === "function") {
        renderQueueBackendLaunchScopePreview(payload, rows, safeHistory());
      }
      if (typeof renderQueueLaunchDecisionChecklist === "function") {
        renderQueueLaunchDecisionChecklist(payload, rows, safeHistory());
      }
    }

    function selectQueueRow(item, event) {
      updateQueuePrioritySelection(item, event);
      if (typeof renderQueueDetail === "function") renderQueueDetail(getSelectedQueueRow() || item || null);
      safeSetText("queue-open-status", "Selected queue row. Open commands use backend-selected paths from the queue snapshot.");
      const payload = safePayload();
      const rows = safeRows();
      if (typeof renderQueueReviewDigest === "function") renderQueueReviewDigest(payload, rows);
      renderLaunchSelectionSurfaces(payload, rows);
      if (typeof updateQueueSelectionVisuals === "function") {
        updateQueueSelectionVisuals();
      } else if (typeof renderQueueRows === "function") {
        renderQueueRows();
      }
    }

    function selectQueueExcludedRow(item) {
      selectedQueueExcludedRowKey = queueExcludedRowKey(item);
      if (typeof renderQueueExcludedDetail === "function") renderQueueExcludedDetail(item || null);
      safeSetText("queue-excluded-open-status", "Selected excluded source row. Open commands use backend-selected paths from the queue snapshot.");
      if (typeof renderQueueExcluded === "function") renderQueueExcluded(safePayload());
    }

    return {
      getLastQueuePayload: safePayload,
      getLastQueueRows: () => safeRows().slice(),
      getSelectedQueueExcludedRow,
      getSelectedQueueExcludedRowKey,
      getSelectedQueuePriorityRowKeys,
      getSelectedQueuePriorityRows,
      getSelectedQueueRow,
      getSelectedQueueRowKey,
      queueExcludedRowKey,
      queueRowKey,
      selectQueueExcludedRow,
      selectQueueRow,
      setRenderedQueueRows,
      syncSelectedQueueRows,
    };
  }

  window.__queueSelectionModule = { createQueueSelectionModule };
})();
