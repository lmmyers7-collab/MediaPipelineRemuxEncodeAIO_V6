(function () {
  const commandHistoryView = window.mediaPipelineCommandHistory || {};
  let selectedLaunchCommandReviewKey = "";

  function launchViewApi() {
    return window.mediaPipelineLaunchView || {};
  }

  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }

  function isLaunchCommand(entry) {
    const command = String(entry?.command || "").toLowerCase();
    return command === "pipeline.start";
  }

  function launchHistoryLabel(command) {
    if (command === "pipeline.start") return "Pipeline";
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

  function launchHistoryRawData(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    return raw.data && typeof raw.data === "object" ? raw.data : {};
  }

  function launchHistoryMode(entry) {
    const request = launchHistoryRequest(entry);
    const data = launchHistoryRawData(entry);
    return request.mode || data.mode || data.actual_mode || data.requested_mode || "";
  }

  function launchHistoryPid(entry) {
    const data = launchHistoryRawData(entry);
    return data.pid || data.process_id || "";
  }

  function launchHistoryJob(entry) {
    const data = launchHistoryRawData(entry);
    return data.active_job_id || data.job_id || "";
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

  function launchHistoryLegacyBlock(entries) {
    return [
      `Last ${entries.length} launch command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(launchHistoryLine),
      "Backend launch locking and validation remain the source of truth.",
    ].join("\n");
  }

  function launchHistoryIssueLevel(entry) {
    if (typeof commandHistoryView.commandHistoryIssueLevel === "function") return commandHistoryView.commandHistoryIssueLevel(entry);
    if (!entry) return "none";
    if (entry.ok) return String(entry.severity || "").toLowerCase() === "warning" ? "warning" : "ok";
    return String(entry.severity || "error").toLowerCase();
  }

  function launchHistoryOwner(entry) {
    if (typeof commandHistoryView.commandHistoryOwnerPage === "function") return commandHistoryView.commandHistoryOwnerPage(entry);
    return "Launch";
  }

  function launchHistoryStatusLabel(entry) {
    return String(entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown") || "unknown");
  }

  function launchHistoryStatusState(entry) {
    const issue = String(launchHistoryIssueLevel(entry) || "").toLowerCase();
    if (["error", "failed", "blocked"].includes(issue)) return "blocked";
    if (["warning", "review", "unknown"].includes(issue)) return "warning";
    if (["ok", "info"].includes(issue)) return "ok";
    return issue || "unknown";
  }

  function launchHistoryOverallPosture(entries) {
    const states = entries.map(launchHistoryStatusState);
    if (states.some((state) => state === "blocked")) return { label: "Needs review", state: "blocked" };
    if (states.some((state) => state === "warning")) return { label: "Review", state: "warning" };
    if (entries.length) return { label: "All OK", state: "ok" };
    return { label: "No launches", state: "empty" };
  }

  function launchHistoryElement(tagName, className = "", text = "") {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (text !== "") node.textContent = String(text);
    return node;
  }

  function launchHistoryAppendText(parent, tagName, className, text) {
    const node = launchHistoryElement(tagName, className, text);
    parent.appendChild(node);
    return node;
  }

  function launchHistoryStatusChip(label, status) {
    const maker = window.mediaPipelineDom?.makeStatusChip || window.makeStatusChip;
    if (typeof maker === "function") return maker(label, status);
    const chip = launchHistoryElement("span", "status-chip", label || status || "unknown");
    chip.dataset.status = status || "unknown";
    return chip;
  }

  function launchHistoryMetaChip(text, status = "") {
    const chip = launchHistoryElement("span", "launch-history-meta-chip", text);
    if (status) chip.dataset.status = status;
    return chip;
  }

  function launchHistorySummaryMetric(label, value, detail, status = "") {
    const node = launchHistoryElement("section", "launch-history-summary-card");
    if (status) node.dataset.status = status;
    launchHistoryAppendText(node, "span", "launch-history-summary-label", label);
    launchHistoryAppendText(node, "strong", "launch-history-summary-value", value);
    launchHistoryAppendText(node, "span", "launch-history-summary-detail", detail);
    return node;
  }

  function renderLaunchHistoryEmpty(target, text) {
    setText("launch-history", text);
    if (!target) return;
    target.className = "launch-command-history";
    target.replaceChildren(launchHistoryElement("p", "launch-history-empty", text));
  }

  function renderLaunchHistorySummary(entries, totalLaunches) {
    const posture = launchHistoryOverallPosture(entries);
    const summary = launchHistoryElement("div", "launch-history-summary-strip");
    summary.appendChild(launchHistorySummaryMetric(
      "Launches shown",
      String(entries.length),
      `${totalLaunches} launch command${totalLaunches === 1 ? "" : "s"} in recent history`,
      entries.length ? "ok" : "empty",
    ));
    summary.appendChild(launchHistorySummaryMetric(
      "Latest launch",
      entries[0]?.at || "Not loaded",
      entries[0] ? launchHistoryLabel(entries[0].command) : "No launch command loaded",
      entries[0] ? launchHistoryStatusState(entries[0]) : "empty",
    ));
    summary.appendChild(launchHistorySummaryMetric(
      "Posture",
      posture.label,
      "Backend command journal evidence",
      posture.state,
    ));
    return summary;
  }

  function renderLaunchHistoryRow(entry) {
    const row = launchHistoryElement("article", "launch-history-row");
    const command = String(entry?.command || "");
    const status = launchHistoryStatusState(entry);
    const source = entry?.local ? "local" : "journal";
    const issue = launchHistoryIssueLevel(entry);
    const owner = launchHistoryOwner(entry);
    const mode = launchHistoryMode(entry);
    const pid = launchHistoryPid(entry);
    const job = launchHistoryJob(entry);
    const rawLine = launchHistoryLine(entry);

    row.dataset.status = status;
    row.setAttribute("aria-label", `${launchHistoryLabel(command)} launch command ${launchHistoryStatusLabel(entry)}`);

    const header = launchHistoryElement("div", "launch-history-row-header");
    const titleBlock = launchHistoryElement("div", "launch-history-row-title");
    launchHistoryAppendText(titleBlock, "strong", "launch-history-row-name", launchHistoryLabel(command));
    launchHistoryAppendText(titleBlock, "span", "launch-history-row-time", entry?.at || "No timestamp");
    header.appendChild(titleBlock);
    header.appendChild(launchHistoryStatusChip(launchHistoryStatusLabel(entry), status));
    row.appendChild(header);

    launchHistoryAppendText(row, "p", "launch-history-message", entry?.message || "No command message recorded.");

    const meta = launchHistoryElement("div", "launch-history-meta");
    meta.appendChild(launchHistoryMetaChip(source, source === "journal" ? "ok" : "warning"));
    meta.appendChild(launchHistoryMetaChip(`owner=${owner}`, "ok"));
    meta.appendChild(launchHistoryMetaChip(`issue=${issue}`, status));
    if (mode) meta.appendChild(launchHistoryMetaChip(`mode=${mode}`, "running"));
    if (pid) meta.appendChild(launchHistoryMetaChip(`pid=${pid}`, "running"));
    if (job) meta.appendChild(launchHistoryMetaChip(`job=${job}`, "running"));
    row.appendChild(meta);

    const details = launchHistoryElement("details", "launch-history-raw");
    launchHistoryAppendText(details, "summary", "", "Raw evidence");
    launchHistoryAppendText(details, "pre", "launch-history-raw-text", rawLine);
    row.appendChild(details);
    return row;
  }

  function launchHistoryTarget(command) {
    const normalized = String(command || "").toLowerCase();
    if (normalized === "pipeline.start") return "pipeline";
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
    if (typeof commandHistoryView.commandHistorySuggestedAction === "function") return commandHistoryView.commandHistorySuggestedAction(entry);
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
    const base = typeof commandHistoryView.commandHistoryDiagnosticsActions === "function"
      ? commandHistoryView.commandHistoryDiagnosticsActions(entry)
      : [];
    const actions = Array.isArray(base) ? base.slice() : [];
    launchCommandDiagnosticsAdd(actions, "tail", "last_stderr_log", "Read Last Stderr", "Read the latest stderr context before retrying a launch failure.");
    launchCommandDiagnosticsAdd(actions, "open", "run_logs", "Open Run Logs", "Inspect backend launch and PowerShell process logs around the command time.");
    launchCommandDiagnosticsAdd(actions, "open", "active_jobs", "Open Active Jobs", "Compare the command result against process lifecycle and orphaned-job state.");
    if (target === "pipeline") {
      launchCommandDiagnosticsAdd(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Compare launch rejection against queue state, blocked rows, and stale snapshot context.");
      launchCommandDiagnosticsAdd(actions, "open", "state", "Open State Folder", "Inspect launch locks, control flags, progress, and runtime state artifacts if process state disagrees.");
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
        "Select a launch command row before retrying a failed pipeline start.",
        "Read-first order: command detail -> Last Stderr / Latest Failure -> Run Logs.",
        "Open-next order: Active Jobs -> Queue Snapshot -> State Folder when needed.",
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
    const bridge = diagnosticsBridgeApi();
    const actions = typeof bridge.diagnosticsBridgeActions === "function" ? bridge.diagnosticsBridgeActions(rawActions) : rawActions;
    if (typeof bridge.appendDiagnosticsBridgeGroupedButtons === "function") {
      bridge.appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "launchCommandDiagnostics",
        onAction: requestLaunchCommandDiagnosticsAction,
      });
    } else {
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.textContent = typeof bridge.diagnosticsBridgeActionLabel === "function"
          ? bridge.diagnosticsBridgeActionLabel(action)
          : `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
        button.title = action.reason || "";
        button.dataset.launchCommandDiagnosticsAction = action.kind;
        button.dataset.launchCommandDiagnosticsTarget = action.target;
        button.addEventListener("click", () => requestLaunchCommandDiagnosticsAction(action));
        container.appendChild(button);
      });
    }
    if (typeof bridge.appendDiagnosticsBridgeButton === "function") {
      bridge.appendDiagnosticsBridgeButton(container, rawActions, "Launch command review selected row");
    }
  }

  function launchCommandReviewRows(history = []) {
    const entries = Array.isArray(history) ? history.filter(isLaunchCommand).slice(0, 8) : [];
    return entries.map((entry, index) => {
      const issue = launchHistoryIssueLevel(entry);
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      const refresh = raw.refresh_hint || (typeof commandHistoryView.commandHistoryRefreshTarget === "function"
        ? commandHistoryView.commandHistoryRefreshTarget(entry)
        : "snapshot");
      return {
        key: typeof commandHistoryView.commandHistoryRowKey === "function" ? commandHistoryView.commandHistoryRowKey(entry) : `${entry?.command || "launch"}:${entry?.at || index}`,
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
      lines.push("- Next step: pipeline start history will appear here after command history refresh.");
    }
    lines.push("- Selection behavior: selecting a launch command review row selects that command in the global Command Results and Diagnostics drilldown.");
    lines.push("- Guardrail: this panel is read-only; pipeline launch, Queue CSV Rerun, drain, and control commands remain backend-owned.");
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
    if (item?.entry && typeof commandHistoryView.selectCommandEntry === "function") commandHistoryView.selectCommandEntry(item.entry);
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
      if (typeof makeRowSelectable === "function" && typeof commandHistoryView.selectCommandEntry === "function") {
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
    const target = byId("launch-history");
    const allLaunches = Array.isArray(history) ? history.filter(isLaunchCommand) : [];
    const entries = allLaunches.slice(0, 6);
    setText("launch-history-status", `${entries.length} launch${entries.length === 1 ? "" : "es"}`);
    if (!Array.isArray(history) || !history.length) {
      renderLaunchHistoryEmpty(target, "No command history loaded yet. Recent pipeline starts will appear here after refresh. CSV rerun command history is reviewed from Queue > CSV Rerun.");
      return;
    }
    if (!entries.length) {
      renderLaunchHistoryEmpty(target, "No pipeline start commands found in the recent command history. CSV rerun command history is reviewed from Queue > CSV Rerun; Pending Publish drain history remains on the Pending Publish page.");
      return;
    }
    setText("launch-history", launchHistoryLegacyBlock(entries));
    if (!target) return;
    target.className = "launch-command-history";
    const heading = launchHistoryElement("p", "launch-history-legacy-line visually-hidden", `Last ${entries.length} launch command${entries.length === 1 ? "" : "s"}:`);
    const list = launchHistoryElement("div", "launch-history-list");
    entries.forEach((entry) => {
      list.appendChild(renderLaunchHistoryRow(entry));
    });
    const footer = launchHistoryElement("p", "launch-history-footer", "Backend launch locking and validation remain the source of truth.");
    target.replaceChildren(
      heading,
      renderLaunchHistorySummary(entries, allLaunches.length),
      list,
      footer,
    );
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
