(function () {
  function createPendingPublishDiagnosticsModule(deps = {}) {
    const {
      apiPost = async function () { throw new Error("apiPost unavailable"); },
      appendCommandResult = function () {},
      appendDiagnosticsBridgeGroupedButtons = null,
      byId = function () { return null; },
      commandHistoryCompactEvidenceLine = null,
      getSelectedPendingRow = function () { return null; },
      pendingListText = function (value) { return Array.isArray(value) && value.length ? value.join(", ") : "none"; },
      pendingRowKey = function (row) { return row?.row_key || ""; },
      requestDiagnosticsOpen = null,
      requestDiagnosticsTail = null,
      setText = function () {},
      state = {},
    } = deps;

    function getPendingOpenInFlight() {
      return Boolean(state.pendingOpenInFlight);
    }

    function setPendingOpenInFlight(value) {
      state.pendingOpenInFlight = Boolean(value);
    }

    function setPendingOpenBusy(isBusy) {
      setPendingOpenInFlight(isBusy);
      document.querySelectorAll("[data-open-pending]").forEach((button) => {
        button.disabled = getPendingOpenInFlight();
      });
    }

    function rejectPendingOpenWhileBusy() {
      if (!getPendingOpenInFlight()) return false;
      const result = {
        command: "pending_publish.open",
        ok: false,
        severity: "warning",
        message: "Another pending publish open command is already in progress.",
      };
      appendCommandResult(result);
      setText("pending-open-status", result.message);
      return true;
    }

    function pendingSelectedOpenTargetLines(item) {
      if (!item) {
        return [
          "Backend selected open targets:",
          "Select a pending publish row to see which backend target keys are available for manifest, payload, destination, and source inspection.",
        ];
      }
      return [
        "Backend selected open targets:",
        `Recommended open targets: ${pendingListText(item.recommended_open_targets)}`,
        `Available open targets: ${pendingListText(item.available_open_targets)}`,
        `Row key: ${item.row_key || pendingRowKey(item) || ""}`,
        "Open boundary: Pending Publish buttons send only row_key and target. The backend resolves parked payload, manifest, destination, and source paths from the current scan.",
        "Mutation guardrail: opening a target does not drain, repair, move, delete, rewrite, publish, or mutate pending payloads/manifests.",
      ];
    }

    function pendingAddDiagnosticsAction(actions, kind, target, label, reason) {
      if (!target) return;
      if (actions.some((item) => item.kind === kind && item.target === target)) return;
      actions.push({ kind, target, label, reason });
    }

    function pendingDiagnosticsActionsForRow(item) {
      const status = String(item?.diagnostic_status || "").toLowerCase();
      const actions = [];
      pendingAddDiagnosticsAction(actions, "open", "pending_publish", "Open Pending Folder", "Inspect backend-selected parked manifests and payloads.");
      if (!item) {
        pendingAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Inspect recent pipeline and publish logs.");
        pendingAddDiagnosticsAction(actions, "open", "state", "Open State Folder", "Inspect runtime state only after close-readiness is safe.");
        return actions;
      }
      if (["missing_payload", "missing_sidecar", "row_error", "duplicate_target"].includes(status)) {
        pendingAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Inspect publish/copy/sidecar errors before drain.");
        pendingAddDiagnosticsAction(actions, "tail", "latest_failure_report", "Read Latest Failure", "Review the newest failure report if one exists.");
      }
      if (["invalid_manifest", "unreadable_manifest"].includes(status)) {
        pendingAddDiagnosticsAction(actions, "open", "state", "Open State Folder", "Compare pending state with runtime artifacts.");
        pendingAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Find the writer that created the malformed manifest.");
      }
      if (status === "orphan_payload") {
        pendingAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Confirm whether the orphan was created by a failed park/drain cycle.");
      }
      return actions;
    }

    function pendingDiagnosticsGuidanceLines(item) {
      const status = String(item?.diagnostic_status || "none").toLowerCase();
      const lines = [
        "Diagnostics actions below use backend allowlists. The Pending page never sends arbitrary filesystem paths.",
        `Selected diagnostic status: ${status}`,
      ];
      if (!item) {
        lines.push("Select a row to tailor diagnostics actions to missing payloads, sidecars, unreadable manifests, orphan payloads, or duplicate targets.");
      } else {
        lines.push(`Drain recommendation: ${item.drain_recommendation || "review"}`);
        lines.push(`Operator guidance: ${item.operator_guidance || "Review this pending row before drain."}`);
        lines.push(`Recovery class: ${item.recovery_class || "manual_review"}`);
        lines.push(`Recovery action: ${item.recovery_action || "Review this row with Pending Publish diagnostics before drain."}`);
        lines.push(`Evidence fields: ${pendingListText(item.evidence_fields)}`);
        lines.push(`Recommended row open targets: ${pendingListText(item.recommended_open_targets)}`);
        if (["invalid_manifest", "unreadable_manifest"].includes(status)) {
          lines.push("Selected-row diagnostic order: open the row manifest, then open Run Logs before another drain attempt.");
        } else if (["missing_payload", "missing_sidecar"].includes(status)) {
          lines.push("Selected-row diagnostic order: open row payload/manifest targets first, then use Run Logs or Latest Failure to confirm whether the copy or sidecar write failed.");
        } else if (status === "orphan_payload") {
          lines.push("Selected-row diagnostic order: open the orphan payload, then inspect Run Logs before deleting or reprocessing.");
        } else if (status === "duplicate_target") {
          lines.push("Selected-row diagnostic order: inspect both pending manifests and destination folders before draining.");
        } else {
          lines.push("Selected-row diagnostic order: inspect backend-selected row targets first, then use Run Logs only when the row conflicts with disk state.");
        }
      }
      return lines;
    }

    function pendingDiagnosticsActionStatusText(actions) {
      const openCount = actions.filter((item) => item.kind === "open").length;
      const tailCount = actions.filter((item) => item.kind === "tail").length;
      return `${actions.length} action${actions.length === 1 ? "" : "s"} (${openCount} open, ${tailCount} read)`;
    }

    function pendingDiagnosticsActionLabel(action) {
      return action.label || `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
    }

    function renderPendingDiagnosticsLinks(item) {
      const actions = pendingDiagnosticsActionsForRow(item);
      setText("pending-diagnostics-status", pendingDiagnosticsActionStatusText(actions));
      setText("pending-diagnostics-guidance", pendingDiagnosticsGuidanceLines(item).join("\n"));
      const container = byId("pending-diagnostics-actions");
      if (!container) return;
      container.replaceChildren();
      if (typeof appendDiagnosticsBridgeGroupedButtons === "function") {
        appendDiagnosticsBridgeGroupedButtons(container, actions, {
          datasetPrefix: "pendingDiagnostics",
          onAction: requestPendingDiagnosticsAction,
        });
      } else {
        actions.forEach((action) => {
          const button = document.createElement("button");
          button.className = "secondary-button";
          button.type = "button";
          button.textContent = pendingDiagnosticsActionLabel(action);
          button.title = action.reason || "";
          button.dataset.pendingDiagnosticsAction = action.kind;
          button.dataset.pendingDiagnosticsTarget = action.target;
          button.addEventListener("click", () => requestPendingDiagnosticsAction(action));
          container.appendChild(button);
        });
      }
    }

    async function requestPendingDiagnosticsAction(action) {
      const target = String(action?.target || "").trim();
      if (!target) return;
      if (action.kind === "tail") {
        const tailRequester = typeof requestDiagnosticsTail === "function" ? requestDiagnosticsTail : window.requestDiagnosticsTail;
        if (typeof tailRequester === "function") {
          await tailRequester(target);
          setText("pending-diagnostics-status", `Read requested: ${target}`);
        } else {
          setText("pending-diagnostics-status", "Diagnostics tail reader is not loaded.");
        }
        return;
      }
      const openRequester = typeof requestDiagnosticsOpen === "function" ? requestDiagnosticsOpen : window.requestDiagnosticsOpen;
      if (typeof openRequester === "function") {
        await openRequester(target);
        setText("pending-diagnostics-status", `Open requested: ${target}`);
      } else {
        setText("pending-diagnostics-status", "Diagnostics open command is not loaded.");
      }
    }

    function isPendingOpenCommand(entry) {
      return String(entry?.command || "").toLowerCase() === "pending_publish.open";
    }

    function pendingOpenHistoryLine(entry) {
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      const data = raw.data && typeof raw.data === "object" ? raw.data : {};
      const request = raw.request && typeof raw.request === "object" ? raw.request : {};
      const bits = [];
      if (data.target || request.target) bits.push(`target=${data.target || request.target}`);
      if (data.row_key || request.row_key) bits.push(`row=${data.row_key || request.row_key}`);
      const openedPath = data.path || data.opened_path;
      if (openedPath) bits.push(`opened=${openedPath}`);
      if (typeof commandHistoryCompactEvidenceLine === "function") {
        return commandHistoryCompactEvidenceLine(entry, {
          label: "pending_publish.open",
          detail: bits.length ? ` (${bits.join("; ")})` : "",
        });
      }
      const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
      const local = entry?.local ? "local" : "journal";
      return `${entry?.at || ""} pending_publish.open [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
    }

    function renderPendingOpenHistory(entries) {
      const history = Array.isArray(entries) ? entries.filter(isPendingOpenCommand).slice(0, 5) : [];
      if (!Array.isArray(entries) || !entries.length) {
        setText("pending-open-history", "No pending publish open command history loaded. Open a selected pending row location to see backend results here after refresh.");
        return;
      }
      if (!history.length) {
        setText("pending-open-history", "No pending publish open commands found in recent command history.");
        return;
      }
      setText("pending-open-history", [
        `Last ${history.length} pending publish open command${history.length === 1 ? "" : "s"}:`,
        ...history.map(pendingOpenHistoryLine),
        "Backend pending row keys and target allowlists remain the source of truth.",
      ].join("\n"));
    }

    async function requestPendingPublishOpen(target) {
      if (rejectPendingOpenWhileBusy()) return;
      const normalized = String(target || "").trim();
      const row = getSelectedPendingRow();
      if (!row) {
        const result = {
          command: "pending_publish.open",
          ok: false,
          severity: "warning",
          message: "Select a pending publish row first.",
        };
        appendCommandResult(result);
        setText("pending-open-status", result.message);
        return;
      }
      setPendingOpenBusy(true);
      setText("pending-open-status", "Opening...");
      try {
        const result = await apiPost("/api/pending-publish/open", {
          row_key: row.row_key || pendingRowKey(row),
          target: normalized,
        });
        appendCommandResult(result);
        setText("pending-open-status", result.message || "Open request sent.");
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        appendCommandResult({
          command: "pending_publish.open",
          ok: false,
          severity: "error",
          message,
        });
        setText("pending-open-status", `Open failed: ${message}`);
      } finally {
        setPendingOpenBusy(false);
      }
    }

    return {
      isPendingOpenCommand,
      pendingDiagnosticsActionsForRow,
      pendingDiagnosticsGuidanceLines,
      pendingOpenHistoryLine,
      pendingSelectedOpenTargetLines,
      renderPendingDiagnosticsLinks,
      renderPendingOpenHistory,
      rejectPendingOpenWhileBusy,
      requestPendingDiagnosticsAction,
      requestPendingPublishOpen,
      setPendingOpenBusy,
    };
  }

  window.__pendingPublishDiagnosticsModule = { createPendingPublishDiagnosticsModule };
})();
