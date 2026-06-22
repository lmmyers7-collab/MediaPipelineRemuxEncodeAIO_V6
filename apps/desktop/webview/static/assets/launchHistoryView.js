(function () {
  const commandHistoryView = window.mediaPipelineCommandHistory || {};
  let selectedLaunchCommandReviewKey = "";

  function launchViewApi() {
    return window.mediaPipelineLaunchView || {};
  }

  function isLaunchCommand(entry) {
    const command = String(entry?.command || "").toLowerCase();
    return command === "pipeline.start" || command === "rerun.start";
  }

  function launchHistoryLabel(command) {
    if (command === "pipeline.start") return "Pipeline";
    if (command === "rerun.start") return "CSV rerun";
    return command || "Launch";
  }

  function launchHistoryDetail(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object" ? raw.request : {};
    const parts = [];
    if (request.mode || data.mode || data.actual_mode) parts.push(`mode=${request.mode || data.mode || data.actual_mode}`);
    if (request.schedule_override || data.schedule_override) parts.push(`schedule=${request.schedule_override || data.schedule_override}`);
    if (request.csv_path) parts.push(`csv=${request.csv_path}`);
    if (request.library_root) parts.push(`root=${request.library_root}`);
    if (data.pid) parts.push(`pid=${data.pid}`);
    if (data.active_job_id) parts.push(`job=${data.active_job_id}`);
    return parts.length ? ` (${parts.join("; ")})` : "";
  }

  function launchHistoryLine(entry) {
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: (command) => launchHistoryLabel(command),
        detail: launchHistoryDetail,
      });
    }
    const command = String(entry?.command || "");
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} ${launchHistoryLabel(command)} [${status}; ${local}] ${entry?.message || ""}${launchHistoryDetail(entry)}`.trim();
  }

  function launchHistoryIssueLevel(entry) {
    if (typeof commandHistoryIssueLevel === "function") return commandHistoryIssueLevel(entry);
    if (!entry) return "none";
    if (entry.ok) return String(entry.severity || "").toLowerCase() === "warning" ? "warning" : "ok";
    return String(entry.severity || "error").toLowerCase();
  }

  function launchHistoryTarget(command) {
    const normalized = String(command || "").toLowerCase();
    if (normalized === "pipeline.start") return "pipeline";
    if (normalized === "rerun.start") return "rerun";
    return "";
  }

  function launchHistoryRequest(entry) {
    if (typeof commandHistoryRequestData === "function") return commandHistoryRequestData(entry);
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    if (raw.request && typeof raw.request === "object") return raw.request;
    if (raw.submitted_request && typeof raw.submitted_request === "object") return raw.submitted_request;
    return {};
  }

  function launchHistoryNextAction(entry) {
    if (typeof commandHistorySuggestedAction === "function") return commandHistorySuggestedAction(entry);
    const issue = launchHistoryIssueLevel(entry);
    if (issue === "ok" || issue === "info") return "Refresh Home and Launch only if the expected process state did not update.";
    if (issue === "warning") return "Review the launch detail, refresh Home, then inspect Diagnostics if active work or schedule state looks wrong.";
    return "Do not retry blindly. Inspect Launch detail, ActiveJobs, Run Logs, and Last Stderr before another start attempt.";
  }

  function launchCommandCorrelationRow(source, checkpoint, posture, evidence, action, detail = []) {
    const normalized = String(posture || "").toLowerCase();
    return {
      source,
      checkpoint,
      posture,
      evidence,
      action,
      detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
      status: normalized.includes("block") || normalized.includes("error") ? "blocked"
        : normalized.includes("review") || normalized.includes("warning") || normalized.includes("high") ? "warning"
          : normalized.includes("unknown") || normalized.includes("incomplete") ? "unknown"
            : "match",
    };
  }

  function launchCommandBackendCorrelationRows(entry) {
    const target = launchHistoryTarget(entry?.command);
    if (!target) return [];
    const launchView = launchViewApi();
    if (typeof launchView.launchBackendPreflightPayloadForTarget !== "function") {
      return [launchCommandCorrelationRow(
        "Backend preflight",
        "Cached preflight unavailable",
        "unknown",
        "Launch backend preflight helpers are not loaded.",
        "Refresh Launch and inspect Diagnostics before retrying a failed start.",
      )];
    }
    const payload = launchView.launchBackendPreflightPayloadForTarget(target);
    if (!payload) {
      return [launchCommandCorrelationRow(
        "Backend preflight",
        "No cached target preflight",
        "unknown",
        `No cached backend preflight payload for ${target}.`,
        "Refresh Backend Launch Preflight before comparing this command result.",
      )];
    }
    const rows = typeof launchView.launchBackendPreflightRows === "function"
      ? launchView.launchBackendPreflightRows([payload])
      : (Array.isArray(payload.checks) ? payload.checks.map((check) => ({
        check: check.label || check.key || "Check",
        posture: check.status || "unknown",
        evidence: check.evidence || "",
        action: check.action || "",
        detail: Array.isArray(check.detail) ? check.detail : [],
      })) : []);
    const nonReady = rows.filter((row) => String(row.posture || "").toLowerCase() !== "ready");
    if (nonReady.length) {
      return nonReady.slice(0, 6).map((row) => launchCommandCorrelationRow(
        "Backend preflight",
        row.check || "Preflight check",
        row.posture || "unknown",
        row.evidence || "",
        row.action || "Review backend preflight before retry.",
        row.detail,
      ));
    }
    return [launchCommandCorrelationRow(
      "Backend preflight",
      "Cached target preflight",
      payload.status || "ready",
      `Cached ${target} backend preflight has ${rows.length} ready-looking check(s).`,
      "If the command failed anyway, refresh backend preflight and inspect Diagnostics because runtime state changed after the cached read.",
    )];
  }

  function launchCommandIntentCorrelationRows(entry) {
    const launchView = launchViewApi();
    if (launchHistoryTarget(entry?.command) !== "pipeline" || typeof launchView.launchSettingsIntentRows !== "function") return [];
    const request = launchHistoryRequest(entry);
    let rows = [];
    try {
      rows = launchView.launchSettingsIntentRows(request);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return [launchCommandCorrelationRow(
        "Launch intent",
        "Intent helper failed",
        "unknown",
        message,
        "Use Backend Launch Preflight and Diagnostics before retrying.",
      )];
    }
    const nonReady = rows.filter((row) => String(row.posture || "").toLowerCase() !== "ready");
    if (!nonReady.length) {
      return [launchCommandCorrelationRow(
        "Launch intent",
        "Saved settings vs intent",
        "ready",
        `No non-ready Launch intent rows for submitted mode ${request.mode || "unknown"}.`,
        "If the command failed, compare Backend Preflight and Diagnostics; this frontend checklist did not predict the block.",
      )];
    }
    return nonReady.slice(0, 5).map((row) => launchCommandCorrelationRow(
      "Launch intent",
      row.checkpoint || row.key || "Intent check",
      row.posture || "unknown",
      row.evidence || "",
      row.action || "Review Launch intent before retry.",
      row.detail,
    ));
  }

  function launchCommandQueueCorrelationRows(entry) {
    if (launchHistoryTarget(entry?.command) !== "pipeline" || typeof queueLaunchDecisionRows !== "function") return [];
    let rows = [];
    try {
      const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
      rows = queueLaunchDecisionRows(undefined, undefined, history);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return [launchCommandCorrelationRow(
        "Queue-to-Launch handoff",
        "Queue-to-Launch handoff helper failed",
        "unknown",
        message,
        "Use Queue and Diagnostics before retrying.",
      )];
    }
    const nonReady = rows.filter((row) => {
      const status = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row.posture)
        : String(row.posture || "").toLowerCase();
      return status !== "ready" && status !== "normal";
    });
    if (!nonReady.length) {
      return [launchCommandCorrelationRow(
        "Queue-to-Launch handoff",
        "Queue-to-Launch handoff",
        "ready",
        "No non-ready Queue-to-Launch Handoff rows are visible in the current snapshot.",
        "If the command failed, refresh Queue and Diagnostics; cached queue context did not predict the block.",
      )];
    }
    return nonReady.slice(0, 5).map((row) => launchCommandCorrelationRow(
      "Queue-to-Launch handoff",
      row.checkpoint || row.key || "Queue check",
      row.posture || "unknown",
      row.evidence || "",
      row.action || "Review Queue-to-Launch Handoff before retry.",
      row.detail,
    ));
  }

  function launchCommandCorrelationRows(entry) {
    if (!entry) return [];
    return [
      ...launchCommandBackendCorrelationRows(entry),
      ...launchCommandIntentCorrelationRows(entry),
      ...launchCommandQueueCorrelationRows(entry),
    ];
  }

  function launchCommandCorrelationStatus(entry) {
    const issue = launchHistoryIssueLevel(entry);
    const rows = launchCommandCorrelationRows(entry);
    const blockers = rows.filter((row) => row.status === "blocked").length;
    const review = rows.filter((row) => row.status === "warning").length;
    const unknown = rows.filter((row) => row.status === "unknown").length;
    if (["ok", "info", "none"].includes(issue)) {
      return blockers || review || unknown ? "Command accepted; advisory context" : "No visible mismatch";
    }
    if (blockers || review) return "Predicted by checklist";
    if (unknown) return "Context incomplete";
    return "Not predicted by cached checks";
  }

  function launchCommandCorrelationSummary(entry) {
    const rows = launchCommandCorrelationRows(entry);
    const status = launchCommandCorrelationStatus(entry);
    const firstNonReady = rows.find((row) => row.status !== "match");
    if (firstNonReady) {
      return `${status}: ${firstNonReady.source} / ${firstNonReady.checkpoint}`;
    }
    return status;
  }

  function launchCommandDiagnosticsAdd(actions, kind, target, label, reason) {
    if (!target || actions.some((item) => item.kind === kind && item.target === target)) return;
    actions.push({ kind, target, label, reason });
  }

  function launchCommandDiagnosticsActions(entry) {
    if (!entry) return [];
    const command = String(entry.command || "").toLowerCase();
    const target = launchHistoryTarget(command);
    const base = typeof commandHistoryDiagnosticsActions === "function" ? commandHistoryDiagnosticsActions(entry) : [];
    const actions = Array.isArray(base) ? base.slice() : [];
    launchCommandDiagnosticsAdd(actions, "tail", "last_stderr_log", "Read Last Stderr", "Read the latest stderr context before retrying a launch failure.");
    launchCommandDiagnosticsAdd(actions, "open", "run_logs", "Open Run Logs", "Inspect backend launch and PowerShell process logs around the command time.");
    launchCommandDiagnosticsAdd(actions, "open", "active_jobs", "Open Active Jobs", "Compare the command result against process lifecycle and orphaned-job state.");
    if (target === "pipeline") {
      launchCommandDiagnosticsAdd(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Compare launch rejection against queue state, blocked rows, and stale snapshot context.");
      launchCommandDiagnosticsAdd(actions, "open", "state", "Open State Folder", "Inspect launch locks, control flags, progress, and runtime state artifacts if process state disagrees.");
    } else if (target === "rerun") {
      launchCommandDiagnosticsAdd(actions, "tail", "latest_failure_report", "Read Latest Failure", "Review latest failure context before retrying CSV rerun.");
      launchCommandDiagnosticsAdd(actions, "open", "audit_reports", "Open Audit Reports", "Inspect source CSV/report context before retrying CSV rerun.");
      launchCommandDiagnosticsAdd(actions, "open", "failed_reports", "Open Failed Reports", "Compare CSV rerun intent against failure-report context.");
    }
    return actions.slice(0, 10);
  }

  function requestLaunchCommandDiagnosticsAction(action) {
    if (typeof requestCommandDiagnosticsAction === "function") {
      requestCommandDiagnosticsAction(action);
      return;
    }
    const target = String(action?.target || "").trim();
    if (!target) return;
    if (action.kind === "tail") {
      if (typeof requestDiagnosticsTail === "function") requestDiagnosticsTail(target);
      return;
    }
    if (typeof requestDiagnosticsOpen === "function") requestDiagnosticsOpen(target);
  }

  function launchCommandDiagnosticsGuidanceLines(item) {
    if (!item) {
      return [
        "Launch diagnostics retry guidance:",
        "Select a launch command row before retrying a failed pipeline or CSV rerun start.",
        "Read-first order: command detail -> Last Stderr / Latest Failure -> Run Logs.",
        "Open-next order: Active Jobs -> Queue Snapshot / Audit Reports / Failed Reports -> State Folder when needed.",
        "Guardrail: these actions use backend allowlisted diagnostics targets only.",
      ];
    }
    const actions = launchCommandDiagnosticsActions(item.entry);
    const readTargets = actions.filter((action) => action.kind === "tail").map((action) => action.target).join(", ") || "none";
    const openTargets = actions.filter((action) => action.kind !== "tail").map((action) => action.target).join(", ") || "none";
    const issue = item.issue || launchHistoryIssueLevel(item.entry);
    const lines = [
      "Launch diagnostics retry guidance:",
      `Selected command: ${item.latestCommand} (${item.flow}; issue=${issue})`,
      `Checklist correlation: ${item.correlation}`,
      `Read-first targets: ${readTargets}`,
      `Open-next targets: ${openTargets}`,
    ];
    if (!["ok", "info", "none"].includes(issue)) {
      lines.push("Retry rule: do not press Start again until command detail, correlated checklist context, and diagnostics targets agree on the cause.");
    } else {
      lines.push("Post-success rule: use diagnostics only if Home/Launch process state did not update as expected.");
    }
    lines.push("Mutation guardrail: Diagnostics buttons read bounded tails or open backend-allowlisted locations; they do not retry, kill, launch, rewrite queue state, or touch media.");
    return lines;
  }

  function renderLaunchCommandDiagnosticsActions(item) {
    const container = byId("launch-command-diagnostics-actions");
    if (!container) return;
    container.replaceChildren();
    if (!item) return;
    const rawActions = launchCommandDiagnosticsActions(item.entry);
    const actions = typeof diagnosticsBridgeActions === "function" ? diagnosticsBridgeActions(rawActions) : rawActions;
    if (typeof appendDiagnosticsBridgeGroupedButtons === "function") {
      appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "launchCommandDiagnostics",
        onAction: requestLaunchCommandDiagnosticsAction,
      });
    } else {
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.textContent = typeof diagnosticsBridgeActionLabel === "function"
          ? diagnosticsBridgeActionLabel(action)
          : `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
        button.title = action.reason || "";
        button.dataset.launchCommandDiagnosticsAction = action.kind;
        button.dataset.launchCommandDiagnosticsTarget = action.target;
        button.addEventListener("click", () => requestLaunchCommandDiagnosticsAction(action));
        container.appendChild(button);
      });
    }
    if (typeof appendDiagnosticsBridgeButton === "function") {
      appendDiagnosticsBridgeButton(container, rawActions, "Launch command review selected row");
    }
  }

  function launchCommandReviewRows(history = []) {
    const entries = Array.isArray(history) ? history.filter(isLaunchCommand).slice(0, 8) : [];
    return entries.map((entry, index) => {
      const issue = launchHistoryIssueLevel(entry);
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      const refresh = raw.refresh_hint || (typeof commandHistoryRefreshTarget === "function" ? commandHistoryRefreshTarget(entry) : "snapshot");
      return {
        key: typeof commandHistoryRowKey === "function" ? commandHistoryRowKey(entry) : `${entry?.command || "launch"}:${entry?.at || index}`,
        entry,
        flow: launchHistoryLabel(String(entry?.command || "")),
        issue,
        latestCommand: String(entry?.command || "unknown"),
        handoff: refresh || "snapshot",
        correlation: launchCommandCorrelationSummary(entry),
        nextStep: launchHistoryNextAction(entry),
      };
    });
  }

  function launchCommandReviewStatus(history = []) {
    const rows = launchCommandReviewRows(history);
    if (!Array.isArray(history) || !history.length) return "No command history";
    if (!rows.length) return "No launch commands";
    const issueCount = rows.filter((row) => !["ok", "info", "none"].includes(row.issue)).length;
    if (issueCount) return `${issueCount} launch issue${issueCount === 1 ? "" : "s"}`;
    return `${rows.length} reviewed`;
  }

  function launchCommandReviewSummaryLines(history = []) {
    const rows = launchCommandReviewRows(history);
    const issueRows = rows.filter((row) => !["ok", "info", "none"].includes(row.issue));
    const lines = [
      "Launch command review:",
      `- Launch commands loaded: ${rows.length}`,
      `- Launch commands needing review: ${issueRows.length}`,
    ];
    if (issueRows.length) {
      lines.push(`- First issue: ${issueRows[0].latestCommand} (${issueRows[0].flow}; ${issueRows[0].issue})`);
      lines.push(`- Checklist correlation: ${issueRows[0].correlation}`);
      lines.push(`- Next step: ${issueRows[0].nextStep}`);
    } else if (rows.length) {
      lines.push("- Next step: recent launch commands have no visible warning/error result.");
    } else {
      lines.push("- Next step: start history will appear here after pipeline or CSV rerun commands refresh.");
    }
    lines.push("- Selection behavior: selecting a launch command review row selects that command in the global Command Results and Diagnostics drilldown.");
    lines.push("- Guardrail: this panel is read-only; launch, CSV rerun, drain, and control commands remain backend-owned.");
    return lines;
  }

  function selectedLaunchCommandReviewRow(rows) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === selectedLaunchCommandReviewKey) || source.find((row) => !["ok", "info", "none"].includes(row.issue)) || source[0] || null;
  }

  function launchCommandReviewDetailLines(item) {
    if (!item) {
      return [
        "Launch command review detail:",
        "Select a launch command row to compare command result against cached Backend Preflight, Launch intent, and Queue-to-Launch handoff context.",
        "Guardrail: this panel is read-only and cannot retry or launch work.",
      ];
    }
    const lines = [
      "Launch command review detail:",
      `Flow: ${item.flow}`,
      `Command: ${item.latestCommand}`,
      `Issue: ${item.issue}`,
      `Result: ${item.entry?.result || (item.entry?.ok ? "ok" : item.entry?.severity || "unknown")}`,
      `Message: ${item.entry?.message || ""}`,
      `Refresh handoff: ${item.handoff}`,
      `Checklist correlation: ${item.correlation}`,
      `Safe next step: ${item.nextStep}`,
      "",
      "Submitted request:",
      JSON.stringify(launchHistoryRequest(item.entry), null, 2),
      "",
      "Correlated checklist/preflight context:",
    ];
    const rows = launchCommandCorrelationRows(item.entry);
    if (!rows.length) {
      lines.push("- No correlated checklist/preflight rows were available.");
    } else {
      rows.forEach((row) => {
        lines.push(`- ${row.source} / ${row.checkpoint}: ${row.posture}; ${row.evidence || "no context"}; ${row.action || "review before retry"}`);
        row.detail.slice(0, 3).forEach((detail) => lines.push(`  ${typeof detail === "object" ? JSON.stringify(detail) : String(detail)}`));
      });
    }
    lines.push("");
    lines.push(...launchCommandDiagnosticsGuidanceLines(item));
    lines.push("");
    lines.push("Guardrail: backend start routes re-check this state at submission time; cached checklist context is explanatory, not authority.");
    return lines;
  }

  function selectLaunchCommandReviewRow(item, history = []) {
    selectedLaunchCommandReviewKey = item?.key || "";
    if (item?.entry && typeof selectCommandEntry === "function") selectCommandEntry(item.entry);
    renderLaunchCommandReview(history);
  }

  function renderLaunchCommandReview(history = []) {
    setText("launch-command-review-status", launchCommandReviewStatus(history));
    setText("launch-command-review-summary", launchCommandReviewSummaryLines(history).join("\n"));
    const rows = launchCommandReviewRows(history);
    if (selectedLaunchCommandReviewKey && !rows.some((row) => row.key === selectedLaunchCommandReviewKey)) {
      selectedLaunchCommandReviewKey = "";
    }
    const selected = selectedLaunchCommandReviewRow(rows);
    setText("launch-command-review-detail", launchCommandReviewDetailLines(selected).join("\n"));
    setText("launch-command-diagnostics-guidance", launchCommandDiagnosticsGuidanceLines(selected).join("\n"));
    renderLaunchCommandDiagnosticsActions(selected);
    const tbody = byId("launch-command-review-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No launch command review rows loaded.");
      updateTableStatusLegend("launch-command-review-legend", tbody, "Launch command review rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = ["error", "blocked"].includes(item.issue) ? "blocked" : item.issue === "warning" ? "warning" : "match";
      appendCells(row, [
        item.flow,
        item.issue,
        item.latestCommand,
        item.correlation,
        item.nextStep,
      ]);
      if (typeof makeRowSelectable === "function" && typeof selectCommandEntry === "function") {
        makeRowSelectable(row, () => selectLaunchCommandReviewRow(item, history), {
          selected: Boolean(item.key && item.key === selectedLaunchCommandReviewKey),
          label: `Launch command review ${item.latestCommand} ${item.issue}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-command-review-legend", tbody, "Launch command review rows");
  }

  function renderLaunchCommandHistory(history = []) {
    renderLaunchCommandReview(history);
    if (typeof commandHistoryView.renderCompactCommandHistoryBlock === "function") {
      commandHistoryView.renderCompactCommandHistoryBlock({
        history,
        filter: isLaunchCommand,
        limit: 6,
        targetId: "launch-history",
        statusId: "launch-history-status",
        statusText: (entries) => `${entries.length} launch${entries.length === 1 ? "" : "es"}`,
        itemLabel: "launch command",
        emptyHistoryText: "No command history loaded yet. Recent pipeline and CSV rerun starts will appear here after refresh.",
        emptyMatchText: "No pipeline or CSV rerun start commands found in the recent command history. Pending publish drain history remains on the Pending Publish page.",
        lineFor: launchHistoryLine,
        footer: "Backend launch locking and validation remain the source of truth.",
      });
      return;
    }
    const entries = Array.isArray(history) ? history.filter(isLaunchCommand).slice(0, 6) : [];
    setText("launch-history-status", `${entries.length} launch${entries.length === 1 ? "" : "es"}`);
    if (!Array.isArray(history) || !history.length) {
      setText("launch-history", "No command history loaded yet. Recent pipeline and CSV rerun starts will appear here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("launch-history", "No pipeline or CSV rerun start commands found in the recent command history. Pending publish drain history remains on the Pending Publish page.");
      return;
    }
    const lines = [
      `Last ${entries.length} launch command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(launchHistoryLine),
      "Backend launch locking and validation remain the source of truth.",
    ];
    setText("launch-history", lines.join("\n"));
  }

  /**
   * Public namespace for the launch history module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineLaunchHistoryView = {
    isLaunchCommand,
    launchHistoryLabel,
    launchHistoryDetail,
    launchHistoryLine,
    launchHistoryIssueLevel,
    launchHistoryTarget,
    launchHistoryRequest,
    launchHistoryNextAction,
    launchCommandCorrelationRows,
    launchCommandCorrelationStatus,
    launchCommandCorrelationSummary,
    launchCommandDiagnosticsActions,
    launchCommandDiagnosticsGuidanceLines,
    renderLaunchCommandDiagnosticsActions,
    launchCommandReviewRows,
    launchCommandReviewStatus,
    launchCommandReviewSummaryLines,
    launchCommandReviewDetailLines,
    renderLaunchCommandReview,
    renderLaunchCommandHistory,
  };
})();
