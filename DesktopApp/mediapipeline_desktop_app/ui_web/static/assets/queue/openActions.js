// queue/openActions.js
// Split child of queueView.js. Loaded before queueView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  function createQueueOpenActionsModule({
    apiPost: apiPostDependency,
    appendCommandResult,
    documentRef,
    getSelectedQueueExcludedRow,
    getSelectedQueueRow,
    queueExcludedRowKey,
    queueListText,
    queueRowKey,
    setText,
  } = {}) {
    let queueOpenInFlight = false;

    const safeAppendCommandResult = typeof appendCommandResult === "function" ? appendCommandResult : function () {};
    const apiPost = typeof apiPostDependency === "function" ? apiPostDependency : async function () { return { ok: false, message: "Queue open API is unavailable." }; };
    const safeDocument = documentRef || document;
    const safeQueueListText = typeof queueListText === "function" ? queueListText : function () { return ""; };
    const safeQueueRowKey = typeof queueRowKey === "function" ? queueRowKey : function () { return ""; };
    const safeQueueExcludedRowKey = typeof queueExcludedRowKey === "function" ? queueExcludedRowKey : function () { return ""; };
    const safeSetText = typeof setText === "function" ? setText : function () {};

    function setQueueOpenBusy(isBusy) {
      queueOpenInFlight = Boolean(isBusy);
      safeDocument.querySelectorAll("[data-open-queue], [data-open-queue-excluded]").forEach((button) => {
        button.disabled = queueOpenInFlight;
      });
    }

    function rejectQueueOpenWhileBusy() {
      if (!queueOpenInFlight) return false;
      const result = {
        command: "queue.open",
        ok: false,
        severity: "warning",
        message: "Another queue open command is already in progress.",
      };
      safeAppendCommandResult(result);
      safeSetText("queue-open-status", result.message);
      return true;
    }

    function queueSelectedOpenTargetLines(item) {
      if (!item) {
        return [
          "Backend selected open targets:",
          "Select a queue row to see which backend target keys are available for source inspection.",
        ];
      }
      return [
        "Backend selected open targets:",
        `Available open targets: ${safeQueueListText(item.available_open_targets)}`,
        `Row key: ${item.row_key || safeQueueRowKey(item) || ""}`,
        "Open boundary: Queue buttons send only row_key, row_scope, and target. The backend resolves source paths from the loaded queue snapshot.",
        "Mutation guardrail: opening a target does not launch, copy, rename, reorder, drop, rewrite, or mutate source/output files.",
      ];
    }

    async function requestQueueOpen(target, rowScope = "runnable") {
      if (rejectQueueOpenWhileBusy()) return;
      const isExcluded = String(rowScope || "").toLowerCase() === "excluded";
      const row = isExcluded
        ? (typeof getSelectedQueueExcludedRow === "function" ? getSelectedQueueExcludedRow() : null)
        : (typeof getSelectedQueueRow === "function" ? getSelectedQueueRow() : null);
      const statusTarget = isExcluded ? "queue-excluded-open-status" : "queue-open-status";
      if (!row) {
        const result = {
          command: "queue.open",
          ok: false,
          severity: "warning",
          message: isExcluded ? "Select an excluded source row first." : "Select a queue row first.",
        };
        safeAppendCommandResult(result);
        safeSetText(statusTarget, result.message);
        return;
      }
      setQueueOpenBusy(true);
      safeSetText(statusTarget, "Opening...");
      try {
        const result = await apiPost("/api/queue/open", {
          row_key: row.row_key || (isExcluded ? safeQueueExcludedRowKey(row) : safeQueueRowKey(row)),
          row_scope: isExcluded ? "excluded" : "runnable",
          target,
        });
        safeAppendCommandResult(result);
        safeSetText(statusTarget, result.message || "Open request sent.");
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        safeAppendCommandResult({
          command: "queue.open",
          ok: false,
          severity: "error",
          message,
        });
        safeSetText(statusTarget, `Open failed: ${message}`);
      } finally {
        setQueueOpenBusy(false);
      }
    }

    return {
      queueSelectedOpenTargetLines,
      rejectQueueOpenWhileBusy,
      requestQueueOpen,
      setQueueOpenBusy,
    };
  }

  window.__queueOpenActionsModule = { createQueueOpenActionsModule };
})();
