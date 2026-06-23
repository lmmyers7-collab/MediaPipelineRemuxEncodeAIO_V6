(function () {
  function diagnosticsBridgeActions(actions) {
    return Array.isArray(actions)
      ? actions.filter((action) => action && action.target)
      : [];
  }

  function diagnosticsBridgeTargetLabel(target) {
    const labels = {
      active_jobs: "Active Jobs",
      audit_reports: "Audit Reports",
      completed_manifest: "Completed Manifest",
      failed_markers: "Failure Markers",
      failed_reports: "Failure Reports",
      latest_audit_csv: "Latest Audit CSV",
      latest_failure_json: "Latest Failure JSON",
      latest_failure_report: "Latest Failure Report",
      last_stderr_log: "Last Stderr",
      last_stdout_log: "Last Stdout",
      pending_publish: "Pending Publish",
      queue_snapshot: "Queue Snapshot",
      run_logs: "Run Logs",
      state: "State Folder",
    };
    return labels[target] || String(target || "").replaceAll("_", " ");
  }

  function diagnosticsBridgeActionLabel(action) {
    if (!action) return "";
    const verb = action.kind === "tail" ? "Read" : "Open";
    return action.label || `${verb} ${diagnosticsBridgeTargetLabel(action.target)}`;
  }

  function diagnosticsBridgeOrderedActions(actions) {
    const candidates = diagnosticsBridgeActions(actions);
    const priority = [
      "last_stderr_log",
      "latest_failure_report",
      "latest_failure_json",
      "queue_snapshot",
      "completed_manifest",
      "pending_publish",
      "active_jobs",
      "run_logs",
      "state",
      "failed_reports",
      "audit_reports",
      "failed_markers",
    ];
    return candidates.slice().sort((a, b) => {
      const aIndex = priority.indexOf(a.target);
      const bIndex = priority.indexOf(b.target);
      const normalizedA = aIndex >= 0 ? aIndex : priority.length;
      const normalizedB = bIndex >= 0 ? bIndex : priority.length;
      return normalizedA - normalizedB;
    });
  }

  function diagnosticsBridgeActionGroups(actions) {
    const ordered = diagnosticsBridgeOrderedActions(actions);
    return {
      readFirst: ordered.filter((action) => action.kind === "tail"),
      openNext: ordered.filter((action) => action.kind !== "tail"),
    };
  }

  function diagnosticsBridgeActionGroupText(actions) {
    return actions.length ? actions.map(diagnosticsBridgeActionLabel).join(" -> ") : "none";
  }

  function diagnosticsBridgeRowTrustLines(sourceLabel = "selected row", actions = [], options = {}) {
    const groups = diagnosticsBridgeActionGroups(actions);
    const evidence = Array.isArray(options.evidence) ? options.evidence.filter(Boolean) : [];
    const lines = [
      "Operator trust summary:",
      `Source: ${sourceLabel || "selected row"}`,
      `Trust state: ${options.trustState || "review"}`,
      `Primary concern: ${options.primaryConcern || "compare row evidence with backend diagnostics before changing workflow state"}`,
      `Read first: ${diagnosticsBridgeActionGroupText(groups.readFirst)}`,
      `Open next: ${diagnosticsBridgeActionGroupText(groups.openNext)}`,
    ];
    if (evidence.length) {
      lines.push("Evidence to compare:");
      evidence.slice(0, 6).forEach((item) => lines.push(`- ${item}`));
    }
    if (options.safeAction) lines.push(`Safe next action: ${options.safeAction}`);
    if (options.unsafeAction) lines.push(`Do not do from this page: ${options.unsafeAction}`);
    if (options.owningPages) lines.push(`Owning pages: ${options.owningPages}`);
    lines.push("Guardrail: this trust summary is read-only; backend commands remain authoritative for launch, drain, rerun, repair, rename, and file movement.");
    return lines;
  }

  function appendDiagnosticsBridgeGroupedButtons(container, actions, options = {}) {
    if (!container) return 0;
    const groups = diagnosticsBridgeActionGroups(actions);
    const datasetPrefix = options.datasetPrefix || "diagnosticsBridge";
    const onAction = typeof options.onAction === "function" ? options.onAction : null;
    const result = window.mediaPipelineDom?.renderOpenTargetActionGroups?.(container, groups, {
      append: true,
      showEmpty: false,
      labelFor: diagnosticsBridgeActionLabel,
      titleFor: (action) => action.reason || action.hint || "",
      groupDataset: "diagnosticsActionGroup",
      actionDataset: `${datasetPrefix}Action`,
      targetDataset: `${datasetPrefix}Target`,
      onTail: (_target, action, button) => {
        if (onAction) onAction(action, button);
      },
      onOpen: (_target, action, button) => {
        if (onAction) onAction(action, button);
      },
    });
    return (result?.readFirst || 0) + (result?.openNext || 0);
  }

  function diagnosticsBridgeShowDiagnostics() {
    if (typeof window.showPage === "function") {
      window.showPage("diagnostics");
      return true;
    }
    const button = document.querySelector('.nav-button[data-page="diagnostics"]');
    if (button) {
      button.click();
      return true;
    }
    return false;
  }

  function diagnosticsBridgePrimaryAction(actions) {
    const candidates = diagnosticsBridgeOrderedActions(actions);
    if (candidates.length) return candidates[0];
    return candidates.find((action) => action.kind === "tail") || candidates[0] || null;
  }

  function diagnosticsBridgeSetTailTarget(target) {
    const setter = window.mediaPipelineDiagnosticsView?.setDiagnosticsTailTarget
      || window.mediaPipelineDiagnosticsTailView?.setDiagnosticsTailTarget
      || window.setDiagnosticsTailTarget;
    if (typeof setter !== "function") return false;
    setter(target);
    return true;
  }

  function diagnosticsBridgeHandoffLines(sourceLabel = "selected row", actions = [], options = {}) {
    const ordered = diagnosticsBridgeOrderedActions(actions);
    const primary = diagnosticsBridgePrimaryAction(ordered);
    const evidence = Array.isArray(options.evidence) ? options.evidence.filter(Boolean) : [];
    const lines = [
      "Diagnostics handoff:",
      `Source: ${sourceLabel || "selected row"}`,
      `Primary target: ${primary ? diagnosticsBridgeActionLabel(primary) : "none available"}`,
    ];
    if (ordered.length) {
      lines.push(`Suggested order: ${ordered.slice(0, 4).map(diagnosticsBridgeActionLabel).join(" -> ")}`);
    } else {
      lines.push("Suggested order: refresh this page, then open Diagnostics > Run Logs if the state still conflicts with disk.");
    }
    evidence.slice(0, 4).forEach((item) => lines.push(`Evidence: ${item}`));
    if (options.safeAction) lines.push(`Safe action: ${options.safeAction}`);
    lines.push("Guardrail: this handoff selects or invokes backend allowlisted diagnostics targets only; it does not mutate queue, rename, publish, report, or media files.");
    return lines;
  }

  function diagnosticsBridgeReviewAction(action, sourceLabel = "selected row") {
    const target = String(action?.target || "").trim();
    const kind = action?.kind === "tail" ? "tail" : "open";
    if (!target) return false;
    const pageShown = diagnosticsBridgeShowDiagnostics();
    const label = sourceLabel || "selected row";
    const message = `Diagnostics bridge selected ${target} from ${label}.`;
    if (kind === "tail") {
      diagnosticsBridgeSetTailTarget(target);
      if (typeof setPanelStatus === "function") {
        setPanelStatus("diagnostics-tail-status", message, "changed");
      } else {
        setText("diagnostics-tail-status", message);
      }
      setText("diagnostics-tail-detail", [
        `Bridge source: ${label}`,
        `Target: ${target}`,
        "Safe action: press Read Tail in Diagnostics, or use the originating row action to run the backend allowlisted tail command.",
        "Guardrail: bridge selection does not read files, open paths, mutate queue state, or publish outputs.",
      ].join("\n"));
    } else {
      if (typeof setPanelStatus === "function") {
        setPanelStatus("diagnostics-open-status", message, "changed");
      } else {
        setText("diagnostics-open-status", message);
      }
    }
    if (!pageShown) {
      if (typeof setPanelStatus === "function") {
        setPanelStatus("diagnostics-open-status", `${message} Diagnostics page navigation was not available.`, "warning");
      } else {
        setText("diagnostics-open-status", `${message} Diagnostics page navigation was not available.`);
      }
    }
    return true;
  }

  function appendDiagnosticsBridgeButton(container, actions, sourceLabel = "selected row") {
    if (!container) return null;
    const action = diagnosticsBridgePrimaryAction(actions);
    if (!action) return null;
    const button = document.createElement("button");
    button.className = "secondary-button";
    button.type = "button";
    button.textContent = "Review in Diagnostics";
    button.title = "Switch to Diagnostics and select the highest-priority allowlisted target without opening or reading it.";
    button.dataset.diagnosticsBridgeKind = action.kind || "open";
    button.dataset.diagnosticsBridgeTarget = action.target;
    button.addEventListener("click", () => diagnosticsBridgeReviewAction(action, sourceLabel));
    container.appendChild(button);
    return button;
  }

  /**
   * Public namespace for the diagnostics bridge module.
   * Consumers use this namespace directly; no flat window.* exports are published from this module.
   */
  window.mediaPipelineDiagnosticsBridge = {
    diagnosticsBridgeActions,
    diagnosticsBridgeTargetLabel,
    diagnosticsBridgeActionLabel,
    diagnosticsBridgeOrderedActions,
    diagnosticsBridgeActionGroups,
    diagnosticsBridgeActionGroupText,
    diagnosticsBridgeRowTrustLines,
    appendDiagnosticsBridgeGroupedButtons,
    diagnosticsBridgeShowDiagnostics,
    diagnosticsBridgePrimaryAction,
    diagnosticsBridgeHandoffLines,
    diagnosticsBridgeReviewAction,
    appendDiagnosticsBridgeButton,
  };
})();
