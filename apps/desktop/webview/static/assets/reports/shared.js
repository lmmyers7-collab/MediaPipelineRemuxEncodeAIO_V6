// reports/shared.js
// Shared pure helpers for reportsView.js. Loaded before reportsView.js; the
// parent consumes and deletes this temporary module stash during initialization.

(function () {
  "use strict";

  const DEFAULT_ROW_RENDER_LIMIT = 250;

  function createReportsSharedModule(deps = {}) {
    const rowRenderLimit = Number.isFinite(Number(deps.rowRenderLimit))
      ? Number(deps.rowRenderLimit)
      : DEFAULT_ROW_RENDER_LIMIT;

    function rowKeySet(rows, keyFn) {
      return new Set((Array.isArray(rows) ? rows : []).map((row) => keyFn(row)).filter(Boolean));
    }

    function hiddenSelectedCount(selectedKeys, visibleRows, keyFn) {
      const visibleKeys = rowKeySet(visibleRows, keyFn);
      return Array.from(selectedKeys || []).filter((key) => key && !visibleKeys.has(key)).length;
    }

    function reportTableStatusText(visibleCount, totalCount, selectedCount = 0, hiddenCount = 0) {
      const parts = [`${visibleCount} / ${totalCount} row${totalCount === 1 ? "" : "s"}`];
      if (selectedCount) parts.push(`${selectedCount} selected`);
      if (hiddenCount) parts.push(`${hiddenCount} selected hidden by filter`);
      if (visibleCount > rowRenderLimit) {
        parts.push(`showing first ${rowRenderLimit} of ${visibleCount}`);
      }
      return parts.join(", ");
    }

    function reportRenderedRows(rows) {
      return (Array.isArray(rows) ? rows : []).slice(0, rowRenderLimit);
    }

    function reportRenderedRowsNote(rows, label) {
      const count = Array.isArray(rows) ? rows.length : 0;
      return count > rowRenderLimit
        ? `Only the first ${rowRenderLimit} ${label} are rendered; this action still applies to all ${count} filtered-visible rows.`
        : "";
    }

    return {
      hiddenSelectedCount,
      reportRenderedRows,
      reportRenderedRowsNote,
      reportTableStatusText,
      rowKeySet,
    };
  }

  window.__reportsViewSharedModule = {
    createReportsSharedModule,
  };
})();
