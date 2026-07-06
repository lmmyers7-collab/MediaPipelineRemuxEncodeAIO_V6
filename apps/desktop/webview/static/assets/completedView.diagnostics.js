(function () {
  function createCompletedDiagnosticsModule(deps = {}) {
    const {
      appendDiagnosticsBridgeButton,
      appendDiagnosticsBridgeGroupedButtons,
      byId,
      requestDiagnosticsOpen,
      requestDiagnosticsTail,
      setText,
    } = deps;

    function completedAddDiagnosticsAction(actions, kind, target, label, reason) {
      if (!target || actions.some((item) => item.kind === kind && item.target === target)) return;
      actions.push({ kind, target, label, reason });
    }

    function completedDiagnosticsActionsForRow(item) {
      const actions = [];
      completedAddDiagnosticsAction(actions, "open", "completed_manifest", "Open Completed Manifest", "Inspect the backend-authored completed history that produced this row.");
      completedAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Inspect recent pipeline and publish logs before rerun or cleanup decisions.");
      completedAddDiagnosticsAction(actions, "tail", "last_stderr_log", "Read Last Stderr", "Read the newest bounded stderr tail for encode, remux, subtitle, copy, or publish failures.");
      if (!item) {
        completedAddDiagnosticsAction(actions, "open", "state", "Open State Folder", "Inspect runtime state only when close-readiness says it is safe.");
        return actions;
      }
      const hasRuntimeIssue = Boolean(item.runtime_outcome_error_code || item.runtime_outcome_reason || String(item.runtime_outcome_status || "").toLowerCase().includes("fail"));
      const hasConsistencyIssue = Array.isArray(item.consistency_issues) && item.consistency_issues.length > 0;
      if (item.output_exists === false || hasConsistencyIssue || item.size_growth_over_5 || hasRuntimeIssue) {
        completedAddDiagnosticsAction(actions, "tail", "latest_failure_report", "Read Latest Failure", "Review the newest failure report when completed history conflicts with disk state.");
      }
      if (item.output_exists === false || item.sidecar_exists === false) {
        completedAddDiagnosticsAction(actions, "open", "pending_publish", "Open Pending Folder", "Check whether the output was parked instead of published.");
      }
      return actions;
    }

    function completedDiagnosticsGuidanceLines(item) {
      const lines = [
        "Diagnostics actions below use backend allowlists. The Completed page never sends arbitrary filesystem paths.",
      ];
      if (!item) {
        lines.push("Select a row to tailor diagnostics actions to missing outputs, sidecar mismatches, size growth, or runtime conflicts.");
      } else {
        lines.push(`Selected output health: ${item.output_health || (item.output_exists === false ? "missing output" : "ok")}`);
        lines.push(`Selected consistency: ${item.consistency_status || "not reported"}`);
        lines.push(`Runtime outcome: ${item.runtime_outcome_status || "none"}${item.runtime_outcome_freshness_status ? ` (${item.runtime_outcome_freshness_status})` : ""}`);
        if (item.output_exists === false) {
          lines.push("Suggested order: open Completed Manifest, open Pending Publish, then read Last Stderr before rerun or cleanup.");
        } else if (item.sidecar_exists === false || (Array.isArray(item.consistency_issues) && item.consistency_issues.length)) {
          lines.push("Suggested order: open Completed Manifest and Run Logs, then inspect the backend-selected output/sidecar buttons above.");
        } else if (item.size_growth_over_5) {
          lines.push("Suggested order: open Completed Manifest, read Run Logs, and compare route/encoder evidence before accepting the output.");
        } else {
          lines.push("Suggested order: Completed Manifest first for row truth; Run Logs only if the row conflicts with disk state.");
        }
      }
      lines.push("Mutation guardrail: diagnostics cross-links open or read backend-selected artifacts only; they do not repair, reconcile, rerun, or delete files.");
      lines.push("Diagnostics bridge: Review in Diagnostics switches to the Diagnostics page and selects an allowlisted target without opening or reading it.");
      return lines;
    }

    function completedDiagnosticsActionStatusText(actions) {
      const openCount = actions.filter((item) => item.kind === "open").length;
      const tailCount = actions.filter((item) => item.kind === "tail").length;
      return `${actions.length} action${actions.length === 1 ? "" : "s"} (${openCount} open, ${tailCount} read)`;
    }

    async function requestCompletedDiagnosticsAction(action) {
      const target = String(action?.target || "").trim();
      if (!target) return;
      if (action.kind === "tail") {
        if (typeof requestDiagnosticsTail === "function") {
          await requestDiagnosticsTail(target);
          setText("completed-diagnostics-status", `Read requested: ${target}`);
        } else {
          setText("completed-diagnostics-status", "Diagnostics tail reader is not loaded.");
        }
        return;
      }
      if (typeof requestDiagnosticsOpen === "function") {
        await requestDiagnosticsOpen(target);
        setText("completed-diagnostics-status", `Open requested: ${target}`);
      } else {
        setText("completed-diagnostics-status", "Diagnostics open command is not loaded.");
      }
    }

    function renderCompletedDiagnosticsLinks(item) {
      const actions = completedDiagnosticsActionsForRow(item);
      setText("completed-diagnostics-status", completedDiagnosticsActionStatusText(actions));
      setText("completed-diagnostics-guidance", completedDiagnosticsGuidanceLines(item).join("\n"));
      const container = byId("completed-diagnostics-actions");
      if (!container) return;
      container.replaceChildren();
      if (typeof appendDiagnosticsBridgeGroupedButtons === "function") {
        appendDiagnosticsBridgeGroupedButtons(container, actions, {
          datasetPrefix: "completedDiagnostics",
          onAction: requestCompletedDiagnosticsAction,
        });
      } else {
        actions.forEach((action) => {
          const button = document.createElement("button");
          button.className = "secondary-button";
          button.type = "button";
          button.textContent = action.label || `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
          button.title = action.reason || "";
          button.dataset.completedDiagnosticsAction = action.kind;
          button.dataset.completedDiagnosticsTarget = action.target;
          button.addEventListener("click", () => requestCompletedDiagnosticsAction(action));
          container.appendChild(button);
        });
      }
      if (typeof appendDiagnosticsBridgeButton === "function") {
        appendDiagnosticsBridgeButton(container, actions, item ? "Completed selected row" : "Completed page");
      }
    }

    return {
      completedDiagnosticsActionsForRow,
      completedDiagnosticsGuidanceLines,
      renderCompletedDiagnosticsLinks,
      requestCompletedDiagnosticsAction,
    };
  }

  window.__completedViewDiagnosticsModule = {
    createCompletedDiagnosticsModule,
  };
})();
