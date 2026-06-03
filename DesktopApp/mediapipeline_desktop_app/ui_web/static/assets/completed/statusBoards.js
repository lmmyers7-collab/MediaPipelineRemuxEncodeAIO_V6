// completed/statusBoards.js
// Split child of completedView.js. Loaded before completedView.js; the parent
// owns payload state and wires these read-only helpers through a temporary stash global.

(function () {
  "use strict";

  function noop() {}

  function normalizeDeps(deps = {}) {
    return {
      renderProgressBarsInto: typeof deps.renderProgressBarsInto === "function" ? deps.renderProgressBarsInto : noop,
      state: deps.state && typeof deps.state === "object" ? deps.state : {},
    };
  }

  function createCompletedStatusBoardsModule(deps = {}) {
    const ctx = normalizeDeps(deps);

    function completedCurrentOutputIdentity(item) {
      const candidates = [
        item?.output_path,
        item?.manifest_output_path,
        item?.final_library_source_path,
      ];
      for (const candidate of candidates) {
        const text = String(candidate || "").trim();
        if (text) return text.replace(/\\/g, "/").replace(/\/+/g, "/").toLowerCase();
      }
      return "";
    }

    function completedCurrentRows(rows = ctx.state.lastCompletedRows) {
      const seen = new Set();
      const currentRows = [];
      (Array.isArray(rows) ? rows : []).forEach((row) => {
        if (row?.output_exists === false) return;
        const identity = completedCurrentOutputIdentity(row);
        if (identity) {
          if (seen.has(identity)) return;
          seen.add(identity);
        }
        currentRows.push(row);
      });
      return currentRows;
    }

    function completedMissingRows(rows = ctx.state.lastCompletedRows) {
      return (Array.isArray(rows) ? rows : []).filter((row) => row?.output_exists === false && !row?.promoted_cleaned);
    }

    function completedMetricCounts(rows = ctx.state.lastCompletedRows) {
      const currentRows = completedCurrentRows(rows);
      return {
        current: currentRows.length,
        encoded: currentRows.filter((row) => String(row?.route || "").startsWith("encode")).length,
        remuxed: currentRows.filter((row) => String(row?.route || "") === "remux").length,
        missing: completedMissingRows(rows).length,
      };
    }

    function completedInventoryProgressBars(completed) {
      const payload = completed && typeof completed === "object" ? completed : {};
      const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
      if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
      if (Array.isArray(payload.progress_bars)) return payload.progress_bars.filter(Boolean);
      return [];
    }

    function renderCompletedInventoryProgress(completed) {
      const payload = completed && typeof completed === "object" ? completed : {};
      const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
      ctx.renderProgressBarsInto("completed-inventory-progress-bars", completedInventoryProgressBars(payload), progress, "No completed inventory progress loaded.");
    }

    function completedEmptyStateMessage(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      if (completed?.error) {
        return `Completed history unavailable: ${completed.error}. Open Diagnostics > Completed Manifest and Run Logs.`;
      }
      const warnings = Array.isArray(completed?.warnings) ? completed.warnings.filter(Boolean) : [];
      if (warnings.length && !rowList.length) {
        return `No completed history rows. Warning: ${warnings[0]}`;
      }
      if (!completed?.manifest_exists && !completed?.source && !completed?.manifest_path) {
        return "No completed history rows. This is normal before the first successful job; otherwise open Diagnostics > Completed Manifest.";
      }
      if (!rowList.length) {
        return "No completed history rows. Check Run Logs and Completed Manifest before reprocessing anything that appears missing.";
      }
      return "No completed jobs available.";
    }

    function completedFreshnessLine(label, ageText, status, timestamp) {
      const parts = [];
      if (ageText) parts.push(ageText);
      if (status) parts.push(status);
      if (timestamp) parts.push(timestamp);
      return `${label}: ${parts.join(" / ") || "not reported"}`;
    }

    function completedManifestIsAged(completed) {
      const status = String(completed?.manifest_freshness_status || "").trim().toLowerCase();
      return Boolean(status && ["aged", "old", "stale"].some((token) => status.includes(token)));
    }

    function completedFormatCounts(value) {
      const entries = value && typeof value === "object" ? Object.entries(value) : [];
      if (!entries.length) return "none";
      return entries.map(([key, count]) => `${key || "unknown"}=${count}`).join(", ");
    }

    function completedListText(value) {
      if (Array.isArray(value)) return value.filter(Boolean).join(", ") || "none";
      return value ? String(value) : "none";
    }

    return {
      completedCurrentOutputIdentity,
      completedCurrentRows,
      completedMissingRows,
      completedMetricCounts,
      completedInventoryProgressBars,
      renderCompletedInventoryProgress,
      completedEmptyStateMessage,
      completedFreshnessLine,
      completedManifestIsAged,
      completedFormatCounts,
      completedListText,
    };
  }

  window.__completedViewStatusBoardsModule = {
    createCompletedStatusBoardsModule,
  };
})();
