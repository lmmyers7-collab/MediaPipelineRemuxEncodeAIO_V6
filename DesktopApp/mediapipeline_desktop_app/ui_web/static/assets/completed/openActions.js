// completed/openActions.js
// Split child of completedView.js. Completed opens delegate to /api/completed/open only.

(function () {
  "use strict";

  function noop() {}

  function normalizeDeps(deps = {}) {
    return {
      apiPost: typeof deps.apiPost === "function" ? deps.apiPost : async function () { throw new Error("apiPost is not available."); },
      appendCommandResult: typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : noop,
      byId: typeof deps.byId === "function" ? deps.byId : function () { return null; },
      commandHistoryCompactEvidenceLine: typeof deps.commandHistoryCompactEvidenceLine === "function" ? deps.commandHistoryCompactEvidenceLine : null,
      getSelectedCompletedRow: typeof deps.getSelectedCompletedRow === "function" ? deps.getSelectedCompletedRow : function () { return null; },
      setText: typeof deps.setText === "function" ? deps.setText : noop,
    };
  }

  function createCompletedOpenActionsModule(deps = {}) {
    const ctx = normalizeDeps(deps);
    const apiPost = ctx.apiPost;
    const appendCommandResult = ctx.appendCommandResult;
    let completedOpenInFlight = false;

    function setCompletedOpenBusy(isBusy) {
      completedOpenInFlight = Boolean(isBusy);
      document.querySelectorAll("[data-open-completed]").forEach((button) => {
        button.disabled = completedOpenInFlight;
      });
    }

    function rejectCompletedOpenWhileBusy() {
      if (!completedOpenInFlight) return false;
      const result = {
        command: "completed.open",
        ok: false,
        severity: "warning",
        message: "Another completed open command is already in progress.",
      };
      appendCommandResult(result);
      ctx.setText("completed-open-status", result.message);
      return true;
    }

    function completedSelectedOpenTargetLines(item) {
      if (!item) return ["Backend selected open targets: none.", "Open boundary: Completed buttons send only row_key and target."];
      const targets = Array.isArray(item.available_open_targets)
        ? item.available_open_targets.filter(Boolean)
        : item.available_open_targets && typeof item.available_open_targets === "object"
        ? Object.entries(item.available_open_targets)
          .filter(([, enabled]) => enabled !== false)
          .map(([key]) => key)
        : [];
      return [
        `Backend selected open targets: ${targets.length ? targets.join(", ") : "none reported"}.`,
        "Open boundary: Completed buttons send only row_key and target.",
        "The WebView never sends arbitrary filesystem paths for Completed opens.",
      ];
    }

    async function requestCompletedOpen(target) {
      if (rejectCompletedOpenWhileBusy()) return;
      const row = ctx.getSelectedCompletedRow();
      if (!row?.row_key) {
        ctx.setText("completed-open-status", "Select a completed row first.");
        return;
      }
      setCompletedOpenBusy(true);
      ctx.setText("completed-open-status", "Opening...");
      try {
        const result = await apiPost("/api/completed/open", { row_key: row.row_key, target });
        ctx.setText("completed-open-status", result.message || "Open request sent.");
        appendCommandResult(result);
      } catch (error) {
        const message = error?.message || String(error);
        ctx.setText("completed-open-status", `Open failed: ${message}`);
        appendCommandResult({
          command: "completed.open",
          ok: false,
          message,
          severity: "error",
        });
      } finally {
        setCompletedOpenBusy(false);
      }
    }

    function isCompletedOpenCommand(entry) {
      return String(entry?.command || "").toLowerCase() === "completed.open";
    }

    function completedOpenHistoryLine(entry) {
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      const data = raw.data && typeof raw.data === "object" ? raw.data : {};
      const request = raw.request && typeof raw.request === "object" ? raw.request : {};
      const bits = [];
      if (data.target || request.target) bits.push(`target=${data.target || request.target}`);
      if (data.row_key || request.row_key) bits.push(`row=${data.row_key || request.row_key}`);
      const openedPath = data.path || data.opened_path || "";
      if (openedPath) bits.push(`opened=${openedPath}`);
      if (ctx.commandHistoryCompactEvidenceLine) {
        return ctx.commandHistoryCompactEvidenceLine(entry, {
          label: "completed.open",
          detail: bits.length ? ` (${bits.join("; ")})` : "",
        });
      }
      const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
      const local = entry?.local ? "local" : "journal";
      return `${entry?.at || ""} completed.open [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
    }

    function renderCompletedOpenHistory(history = []) {
      const entries = Array.isArray(history) ? history.filter(isCompletedOpenCommand).slice(0, 5) : [];
      if (!Array.isArray(history) || !history.length) {
        ctx.setText("completed-open-history", "No completed open command history loaded. Open a selected row location to see backend results here after refresh.");
        return;
      }
      if (!entries.length) {
        ctx.setText("completed-open-history", "No completed open commands found in recent command history.");
        return;
      }
      ctx.setText("completed-open-history", [
        `Last ${entries.length} completed open command${entries.length === 1 ? "" : "s"}:`,
        ...entries.map(completedOpenHistoryLine),
        "Backend manifest row keys and target allowlists remain the source of truth.",
      ].join("\n"));
    }

    return {
      completedOpenHistoryLine,
      completedSelectedOpenTargetLines,
      isCompletedOpenCommand,
      rejectCompletedOpenWhileBusy,
      renderCompletedOpenHistory,
      requestCompletedOpen,
      setCompletedOpenBusy,
    };
  }

  window.__completedViewOpenActionsModule = {
    createCompletedOpenActionsModule,
  };
})();
