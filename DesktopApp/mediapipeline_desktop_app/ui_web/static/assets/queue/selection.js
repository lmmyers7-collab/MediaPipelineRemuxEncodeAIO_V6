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
    setText,
  } = {}) {
    let selectedQueueRowKey = "";
    let selectedQueueExcludedRowKey = "";

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

    function getSelectedQueueExcludedRowKey() {
      return selectedQueueExcludedRowKey;
    }

    function getSelectedQueueRow() {
      if (!selectedQueueRowKey) return null;
      return safeRows().find((row) => queueRowKey(row) === selectedQueueRowKey) || null;
    }

    function getSelectedQueueExcludedRow() {
      if (!selectedQueueExcludedRowKey) return null;
      return safeExcludedRows().find((row) => queueExcludedRowKey(row) === selectedQueueExcludedRowKey) || null;
    }

    function syncSelectedQueueRows(rows, excludedRows) {
      const runnableRows = safeArray(rows);
      const filteredRows = safeArray(excludedRows);
      if (selectedQueueRowKey && !runnableRows.some((row) => queueRowKey(row) === selectedQueueRowKey)) {
        selectedQueueRowKey = "";
      }
      if (selectedQueueExcludedRowKey && !filteredRows.some((row) => queueExcludedRowKey(row) === selectedQueueExcludedRowKey)) {
        selectedQueueExcludedRowKey = "";
      }
    }

    function renderLaunchSelectionSurfaces(payload, rows) {
      if (typeof renderQueueBackendLaunchScopePreview === "function") {
        renderQueueBackendLaunchScopePreview(payload, rows, safeHistory());
      }
      if (typeof renderQueueLaunchDecisionChecklist === "function") {
        renderQueueLaunchDecisionChecklist(payload, rows, safeHistory());
      }
    }

    function selectQueueRow(item) {
      selectedQueueRowKey = queueRowKey(item);
      if (typeof renderQueueDetail === "function") renderQueueDetail(item || null);
      safeSetText("queue-open-status", "Selected queue row. Open commands use backend-selected paths from the queue snapshot.");
      const payload = safePayload();
      const rows = safeRows();
      if (typeof renderQueueReviewDigest === "function") renderQueueReviewDigest(payload, rows);
      renderLaunchSelectionSurfaces(payload, rows);
      if (typeof renderQueueRows === "function") renderQueueRows();
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
      getSelectedQueueRow,
      getSelectedQueueRowKey,
      queueExcludedRowKey,
      queueRowKey,
      selectQueueExcludedRow,
      selectQueueRow,
      syncSelectedQueueRows,
    };
  }

  window.__queueSelectionModule = { createQueueSelectionModule };
})();
