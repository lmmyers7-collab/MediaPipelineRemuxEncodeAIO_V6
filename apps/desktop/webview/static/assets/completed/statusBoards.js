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

    function completedProofNormalizePath(value) {
      return String(value || "").replace(/\\/g, "/").replace(/\/+/g, "/").trim().toLowerCase();
    }

    function completedProofRowKey(row) {
      return String(row?.row_key || row?.completed_row_key || row?.manifest_key || "").trim().toLowerCase();
    }

    function completedProofOutputPath(row) {
      return row?.output_path || row?.manifest_output_path || row?.runtime_outcome_output_path || row?.final_library_source_path || row?.completed_output || row?.completed_output_path || "";
    }

    function completedProofSourcePath(row) {
      return row?.source_path || row?.input_path || row?.original_source_path || row?.completed_source || row?.completed_source_path || "";
    }

    function completedProofRowsForItem(item, proofRows = ctx.state.lastCompletedPendingProofRows) {
      if (!item) return [];
      const itemKey = completedProofRowKey(item);
      const itemOutput = completedProofNormalizePath(completedProofOutputPath(item));
      const itemSource = completedProofNormalizePath(completedProofSourcePath(item));
      return (Array.isArray(proofRows) ? proofRows : []).filter((proof) => {
        const candidates = [proof?.completed, proof?.completed_row, proof].filter((candidate) => candidate && typeof candidate === "object");
        return candidates.some((completed) => {
          const completedKey = completedProofRowKey(completed);
          const completedOutput = completedProofNormalizePath(completedProofOutputPath(completed));
          const completedSource = completedProofNormalizePath(completedProofSourcePath(completed));
          return (
            (itemKey && completedKey && itemKey === completedKey) ||
            (itemOutput && completedOutput && itemOutput === completedOutput) ||
            (itemSource && completedSource && itemSource === completedSource)
          );
        });
      });
    }

    function completedOutputPlacement(item, proofRows = ctx.state.lastCompletedPendingProofRows) {
      const outputHealth = String(item?.output_health || "").toLowerCase();
      const missing = item?.output_exists === false
        || item?.missing_output === true
        || ["missing", "not_found", "not found", "deleted", "unavailable"].some((token) => outputHealth.includes(token));
      if (!missing) return { label: "Current", state: "ok", key: "current" };
      const matches = completedProofRowsForItem(item, proofRows);
      const signals = matches.map((row) => String(row?.signal || "").toLowerCase());
      const hasDrainProof = signals.some((signal) => (
        signal === "completed-missing-output-with-drain-proof"
        || signal === "missing_output_with_drain_proof"
        || signal === "drain-summary-output-proof"
        || signal === "drain-summary-source-proof"
        || signal === "drain_summary_output_proof"
        || signal === "drain_summary_source_proof"
      ));
      const hasPendingProof = signals.some((signal) => (
        signal === "completed-missing-output-still-pending"
        || signal === "missing_output_still_pending"
        || signal === "pending-destination-overlap"
        || signal === "completed-source-still-pending"
        || signal === "pending_destination_overlap"
        || signal === "completed_source_still_pending"
      ));
      if (hasDrainProof) return { label: "Missing: drain proof", state: "warning", key: "missing_drain_proof" };
      if (hasPendingProof) return { label: "Missing: pending proof", state: "warning", key: "missing_pending_proof" };
      if (completedProofOutputPath(item) || completedProofSourcePath(item)) return { label: "Missing: no proof", state: "blocked", key: "missing_no_proof" };
      return { label: "Moved/offline unknown", state: "warning", key: "moved_offline_unknown" };
    }

    function completedPlacementCounts(rows = ctx.state.lastCompletedRows, proofRows = ctx.state.lastCompletedPendingProofRows) {
      return (Array.isArray(rows) ? rows : []).reduce((counts, row) => {
        const placement = completedOutputPlacement(row, proofRows);
        counts[placement.key] = (counts[placement.key] || 0) + 1;
        return counts;
      }, {});
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
      completedProofRowsForItem,
      completedOutputPlacement,
      completedPlacementCounts,
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
