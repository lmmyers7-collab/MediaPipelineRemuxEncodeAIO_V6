(function () {
  let commandHistory = [];
  let selectedCommandKey = "";
  let selectedCommandResolutionKey = "";
  let commandHistoryLocalSequence = 0;
  const COMMAND_RESULT_LIST_LIMIT = 5;
  const COMMAND_RESULT_ITEM_CHARS = 240;
  void COMMAND_RESULT_LIST_LIMIT;
  const commandHistoryFormatters = window.__commandHistoryFormatters || {};
  const commandHistoryDiagnostics = window.__commandHistoryDiagnostics || {};

  function commandHistoryDiagnostic(name) {
    const fn = commandHistoryDiagnostics[name];
    if (typeof fn !== "function") throw new Error(`commandHistory diagnostics slice missing ${name}`);
    return fn;
  }

  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }

  function commandHistoryFormatter(name) {
    const fn = commandHistoryFormatters[name];
    if (typeof fn !== "function") throw new Error(`commandHistory formatter slice missing ${name}`);
    return fn;
  }

  function commandResultLabel(result) {
    return commandHistoryFormatter("commandResultLabel")(result);
  }

  function boundedCommandText(value, maxChars = COMMAND_RESULT_ITEM_CHARS) {
    return commandHistoryFormatter("boundedCommandText")(value, maxChars);
  }

  function commandResultList(value) {
    return commandHistoryFormatter("commandResultList")(value);
  }

  function commandResultFeedbackLines(result) {
    return commandHistoryFormatter("commandResultFeedbackLines")(result);
  }

  function commandResultDisplayMessage(result) {
    return commandHistoryFormatter("commandResultDisplayMessage")(result);
  }

  function commandHistoryCommandText(item) {
    return commandHistoryFormatter("commandHistoryCommandText")(item);
  }

  function commandHistoryCompactEvidenceLine(item, options = {}) {
    return commandHistoryFormatter("commandHistoryCompactEvidenceLine")(item, options);
  }

  function compactCommandHistoryEntries(history = [], filter = null, limit = 6) {
    return commandHistoryFormatter("compactCommandHistoryEntries")(history, filter, limit);
  }

  function compactCommandHistoryBlockText(options = {}) {
    return commandHistoryFormatter("compactCommandHistoryBlockText")(options);
  }

  function renderCompactCommandHistoryBlock(options = {}) {
    return commandHistoryFormatter("renderCompactCommandHistoryBlock")(options);
  }

  function commandHistoryOwnerPage(item) {
    return commandHistoryFormatter("commandHistoryOwnerPage")(item);
  }

  function commandHistoryIssueLevel(item) {
    return commandHistoryFormatter("commandHistoryIssueLevel")(item);
  }

  function commandHistoryRefreshTarget(item) {
    return commandHistoryFormatter("commandHistoryRefreshTarget")(item);
  }

  function commandHistoryRawData(item) {
    return commandHistoryFormatter("commandHistoryRawData")(item);
  }

  function commandHistoryRequestData(item) {
    return commandHistoryFormatter("commandHistoryRequestData")(item);
  }

  function commandHistoryIsPendingPublishCommand(item) {
    return commandHistoryFormatter("commandHistoryIsPendingPublishCommand")(item);
  }

  function commandHistoryPendingPublishCommandKind(item) {
    return commandHistoryFormatter("commandHistoryPendingPublishCommandKind")(item);
  }

  function commandHistoryPendingPublishIssueLevel(item) {
    return commandHistoryFormatter("commandHistoryPendingPublishIssueLevel")(item);
  }

  function commandHistoryPendingPublishSuggestedAction(item) {
    return commandHistoryFormatter("commandHistoryPendingPublishSuggestedAction")(item);
  }

  function commandHistorySuggestedAction(item) {
    return commandHistoryFormatter("commandHistorySuggestedAction")(item);
  }

  function commandHistoryOwnerCounts(entries = commandHistory) {
    return commandHistoryFormatter("commandHistoryOwnerCounts")(entries);
  }

  function commandHistoryIssueEntries(entries = commandHistory) {
    return commandHistoryFormatter("commandHistoryIssueEntries")(entries);
  }

  function formatCommandCountMap(counts) {
    return commandHistoryFormatter("formatCommandCountMap")(counts);
  }

  function commandHistoryIssueDigestLines(entries = commandHistory) {
    return commandHistoryFormatter("commandHistoryIssueDigestLines")(entries);
  }

  function commandHistoryPendingPublishEntries(entries = commandHistory) {
    return commandHistoryFormatter("commandHistoryPendingPublishEntries")(entries);
  }

  function commandHistoryPendingPublishDigestLines(entries = commandHistory) {
    return commandHistoryFormatter("commandHistoryPendingPublishDigestLines")(entries);
  }

  function commandHistoryFinalPlacementApplies(item) {
    return commandHistoryFormatter("commandHistoryFinalPlacementApplies")(item);
  }

  function commandHistoryFinalPlacementProofRows(item) {
    return commandHistoryFormatter("commandHistoryFinalPlacementProofRows")(item);
  }

  function commandHistoryFinalPlacementConflictCounts(rows) {
    return commandHistoryFormatter("commandHistoryFinalPlacementConflictCounts")(rows);
  }

  function commandHistoryFinalPlacementConflictSummary(item) {
    return commandHistoryFormatter("commandHistoryFinalPlacementConflictSummary")(item);
  }

  function commandHistoryFinalPlacementConflictLines(item) {
    return commandHistoryFormatter("commandHistoryFinalPlacementConflictLines")(item);
  }

  function commandHistoryTraceLines(item) {
    return commandHistoryFormatter("commandHistoryTraceLines")(item);
  }


  function commandHistoryDiagnosticsDrilldownRows(entries = commandHistory) {
    return commandHistoryDiagnostic("commandHistoryDiagnosticsDrilldownRows")(entries);
  }

  function commandHistoryDiagnosticsDrilldownStatus(entries = commandHistory) {
    return commandHistoryDiagnostic("commandHistoryDiagnosticsDrilldownStatus")(entries);
  }

  function commandHistoryDiagnosticsDrilldownSummaryLines(entries = commandHistory) {
    return commandHistoryDiagnostic("commandHistoryDiagnosticsDrilldownSummaryLines")(entries);
  }

  function commandHistoryOwnerImpactRows(entries = commandHistory) {
    return commandHistoryDiagnostic("commandHistoryOwnerImpactRows")(entries);
  }

  function commandHistoryOwnerImpactStatus(entries = commandHistory) {
    return commandHistoryDiagnostic("commandHistoryOwnerImpactStatus")(entries);
  }

  function commandHistoryOwnerImpactSummaryLines(entries = commandHistory) {
    return commandHistoryDiagnostic("commandHistoryOwnerImpactSummaryLines")(entries);
  }

  function commandHistoryRowKey(item) {
    return commandHistoryDiagnostic("commandHistoryRowKey")(item);
  }

  function commandHistoryDiagnosticsActions(item) {
    return commandHistoryDiagnostic("commandHistoryDiagnosticsActions")(item);
  }
  function renderDiagnosticsCommandOwnerImpact(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const rows = commandHistoryOwnerImpactRows(items);
    const ownerStatus = commandHistoryOwnerImpactStatus(items);
    if (typeof setPanelStatus === "function") {
      setPanelStatus("diagnostics-command-owner-status", ownerStatus);
    } else {
      setText("diagnostics-command-owner-status", ownerStatus);
    }
    setText("diagnostics-command-owner-summary", commandHistoryOwnerImpactSummaryLines(items).join("\n"));
    const tbody = byId("diagnostics-command-owner-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No command owner impact rows loaded.");
      updateTableStatusLegend("diagnostics-command-owner-legend", tbody, "Command owner impact rows");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 12).forEach((entry) => {
      const row = document.createElement("tr");
      row.dataset.rowKey = entry.key;
      row.dataset.status = ["error", "blocked"].includes(entry.latestIssue) ? "blocked" : entry.latestIssue === "warning" ? "warning" : "match";
      appendCells(row, [
        entry.owner,
        formatCommandCountMap(entry.issueCounts),
        entry.latestCommand,
        entry.latestRefresh,
        entry.latestAction,
      ]);
      makeRowSelectable(row, () => selectCommandEntry(entry.latest), {
        selected: Boolean(entry.latest && commandHistoryRowKey(entry.latest) === selectedCommandKey),
        label: `Command owner impact ${entry.owner} ${entry.latestIssue}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-command-owner-legend", tbody, "Command owner impact rows");
  }

  function commandHistoryResolutionPostureStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized.includes("blocked") || normalized.includes("do not")) return "blocked";
    if (normalized.includes("review") || normalized.includes("warning")) return "warning";
    if (normalized.includes("read") || normalized.includes("refresh")) return "changed";
    if (normalized.includes("unknown") || normalized.includes("incomplete")) return "unknown";
    if (normalized.includes("ready")) return "ready";
    return "normal";
  }

  function commandHistoryResolutionAdd(rowsOut, key, checkpoint, posture, evidence, action, detail = [], item = null) {
    rowsOut.push({
      key,
      checkpoint,
      posture,
      evidence,
      action,
      detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
      item,
    });
  }

  function commandHistoryResolutionRows(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const issues = commandHistoryIssueEntries(items);
    const selected = getSelectedCommandEntry();
    const focus = selected || issues[0] || items[0] || null;
    const actions = commandHistoryDiagnosticsActions(focus);
    const logEvidence = commandHistoryLogEvidenceRows(focus);
    const targetEvidence = commandHistoryTargetEvidenceRows(focus);
    const ownerRows = commandHistoryOwnerImpactRows(items);
    const ownerLiveState = commandHistoryOwnerLiveStateSummary(focus);
    const finalPlacement = commandHistoryFinalPlacementConflictSummary(focus);
    const rows = [];

    commandHistoryResolutionAdd(
      rows,
      "command-stream",
      "Command stream",
      !items.length ? "Unknown" : issues.length ? "Review first" : "Ready",
      !items.length ? "No command results are loaded." : `${items.length} command result(s), ${issues.length} warning/error result(s).`,
      !items.length
        ? "Run or refresh backend-owned commands before using command history for triage."
        : issues.length
          ? "Resolve warning/error commands before repeating related operations."
          : "No command warning/error is visible; use owning page state if something still looks stale.",
      commandHistoryIssueDigestLines(items),
      focus,
    );

    commandHistoryResolutionAdd(
      rows,
      "latest-issue",
      "Latest issue",
      issues.length ? (["error", "blocked"].includes(commandHistoryIssueLevel(issues[0])) ? "Blocked" : "Review first") : "Ready",
      issues.length ? `${issues[0].command || "unknown"} (${commandHistoryOwnerPage(issues[0])}; ${commandHistoryIssueLevel(issues[0])})` : "No warning/error command is visible.",
      issues.length ? commandHistorySuggestedAction(issues[0]) : "Continue only if page state disagrees with backend state.",
      issues.length ? commandHistoryDetailLines(issues[0]).slice(0, 14) : ["No warning/error command detail loaded."],
      issues[0] || focus,
    );

    commandHistoryResolutionAdd(
      rows,
      "owner-impact",
      "Owner page handoff",
      ownerRows.some((row) => (row.issueCounts.error || 0) || (row.issueCounts.blocked || 0)) ? "Blocked"
        : ownerRows.some((row) => row.issueCounts.warning || 0) ? "Review first"
          : ownerRows.length ? "Ready" : "Unknown",
      ownerRows.length ? `Owners: ${ownerRows.map((row) => `${row.owner}=${row.entries.length}`).join(", ")}` : "No owner-impact rows loaded.",
      ownerRows.length ? "Open the owning page first; use Diagnostics only when command detail does not explain the backend result." : "Refresh command history after backend commands run.",
      commandHistoryOwnerImpactSummaryLines(items),
      ownerRows[0]?.latest || focus,
    );

    commandHistoryResolutionAdd(
      rows,
      "refresh-target",
      "Refresh target",
      focus ? commandHistoryIssueLevel(focus) === "ok" ? "Ready" : "Read evidence" : "Unknown",
      focus ? `Refresh target: ${commandHistoryRefreshTarget(focus)}; owner: ${commandHistoryOwnerPage(focus)}.` : "No selected or issue command.",
      focus ? "Refresh or inspect the owner page after reading diagnostics; do not infer success from command history alone." : "Select a command row first.",
      focus ? commandHistoryTraceLines(focus) : ["No command trace loaded."],
      focus,
    );

    commandHistoryResolutionAdd(
      rows,
      "owner-live-state",
      "Owner page live state",
      ownerLiveState.posture === "blocked" ? "Blocked" : ownerLiveState.posture === "review" ? "Review first" : ownerLiveState.posture === "unknown" ? "Unknown" : "Read evidence",
      ownerLiveState.evidence,
      ownerLiveState.loaded
        ? "Compare cached owner-page state with command detail before retrying from the owning page."
        : "Refresh the owning page before using command history as retry evidence.",
      ownerLiveState.lines,
      focus,
    );

    if (finalPlacement.applies) {
      commandHistoryResolutionAdd(
        rows,
        "completed-pending-final-placement",
        "Completed/Pending final placement",
        finalPlacement.posture === "blocked" ? "Blocked" : finalPlacement.posture === "review" ? "Review first" : finalPlacement.posture === "unknown" ? "Unknown" : "Read evidence",
        finalPlacement.evidence,
        finalPlacement.action,
        commandHistoryFinalPlacementConflictLines(focus),
        focus,
      );
    }

    commandHistoryResolutionAdd(
      rows,
      "diagnostics-targets",
      "Diagnostics targets",
      actions.some((action) => action.kind === "tail") ? "Read evidence" : actions.length ? "Review first" : "Unknown",
      actions.length ? actions.map((action) => `${action.kind}:${action.target}`).join(", ") : "No allowlisted diagnostics targets inferred.",
      actions.length ? "Read bounded tail targets before shell-opening folders or files." : "Use Diagnostics State Artifact Summary and Run Logs if the command remains unclear.",
      actions.map((action) => `${action.kind === "tail" ? "Read" : "Open"} ${action.target}: ${action.reason || "backend allowlisted investigation target"}`),
      focus,
    );

    commandHistoryResolutionAdd(
      rows,
      "visible-log-evidence",
      "Visible log correlation",
      logEvidence.some((row) => row.status === "blocked") ? "Blocked" : logEvidence.length ? "Review first" : "Read evidence",
      logEvidence.length ? `${logEvidence.length} possible visible diagnostics log match(es).` : "No visible diagnostics log row matched command tokens.",
      logEvidence.length ? "Compare timestamp/message text before retrying from the owning page." : "Use allowlisted Last Stderr / Latest Failure / Run Logs targets; absence of visible matches is not proof.",
      commandHistoryDiagnosticsEvidenceSummaryLines(focus),
      focus,
    );

    commandHistoryResolutionAdd(
      rows,
      "target-evidence",
      "Allowlisted evidence coverage",
      targetEvidence.length ? "Read evidence" : "Unknown",
      targetEvidence.length ? `${targetEvidence.length} backend allowlisted evidence target(s).` : "No target evidence available.",
      targetEvidence.length ? "Use the evidence buttons in Command Result Drilldown or Related Diagnostics Evidence." : "Fallback to Diagnostics Open Locations only through existing backend allowlists.",
      targetEvidence.map((row) => `${row.source}: ${row.action}`),
      focus,
    );

    if (focus && commandHistoryIsPendingPublishCommand(focus)) {
      commandHistoryResolutionAdd(
        rows,
        "pending-publish-special-case",
        "Pending publish special case",
        commandHistoryPendingPublishIssueLevel(focus) === "blocked" ? "Blocked" : commandHistoryPendingPublishIssueLevel(focus) === "review" ? "Review first" : "Ready",
        `${commandHistoryPendingPublishCommandKind(focus)}; level=${commandHistoryPendingPublishIssueLevel(focus)}.`,
        commandHistoryPendingPublishSuggestedAction(focus),
        commandHistoryPendingPublishDataLines(focus),
        focus,
      );
    }

    commandHistoryResolutionAdd(
      rows,
      "decision-boundary",
      "Decision boundary",
      "Ready - backend owned",
      "Command history explains what happened; it is not a retry, repair, launch, drain, save, rename, delete, or publish control.",
      "Repeat actions only from the owning page after command detail and diagnostics evidence agree.",
      [
        "Mutation guardrail: this checklist cannot retry, launch, drain, save, rename, repair, delete, publish, open arbitrary paths, or bypass backend validation.",
      ],
      focus,
    );

    return rows;
  }

  function commandHistoryResolutionStatus(entries = commandHistory) {
    const rows = commandHistoryResolutionRows(entries);
    if (!rows.length) return "No commands";
    if (rows.some((row) => commandHistoryResolutionPostureStatus(row.posture) === "blocked")) return "Blocked evidence";
    if (rows.some((row) => commandHistoryResolutionPostureStatus(row.posture) === "warning")) return "Review first";
    if (rows.some((row) => commandHistoryResolutionPostureStatus(row.posture) === "changed")) return "Read evidence";
    if (rows.some((row) => commandHistoryResolutionPostureStatus(row.posture) === "unknown")) return "Evidence incomplete";
    return "Ready-looking";
  }

  function commandHistoryResolutionStatusState(status) {
    const normalized = String(status || "").trim().toLowerCase();
    if (normalized === "blocked evidence") return "blocked";
    if (normalized === "review first") return "warning";
    if (normalized === "read evidence") return "changed";
    if (normalized === "evidence incomplete" || normalized === "no commands") return "unknown";
    if (normalized === "ready-looking") return "ready";
    return "unknown";
  }

  function commandHistoryResolutionSummaryLines(entries = commandHistory) {
    const rows = commandHistoryResolutionRows(entries);
    const blocked = rows.filter((row) => commandHistoryResolutionPostureStatus(row.posture) === "blocked").length;
    const review = rows.filter((row) => commandHistoryResolutionPostureStatus(row.posture) === "warning").length;
    const readFirst = rows.filter((row) => commandHistoryResolutionPostureStatus(row.posture) === "changed").length;
    const unknown = rows.filter((row) => commandHistoryResolutionPostureStatus(row.posture) === "unknown").length;
    const lines = [
      "Command failure resolution checklist:",
      `Checkpoints loaded: ${rows.length}`,
      `Blocked/review/read-first/unknown: ${blocked}/${review}/${readFirst}/${unknown}`,
      "Decision rule: retry or repeat only from the owning page after command detail, refresh target, diagnostics tails, and owner state agree.",
    ];
    if (blocked) {
      lines.push("First action: resolve blocked evidence before repeating the command from its owning page.");
    } else if (review || readFirst || unknown) {
      lines.push("First action: select review/read-first checkpoints, then use backend allowlisted Diagnostics before retrying from the owning page.");
    } else {
      lines.push("First action: no command issue is visible; investigate only if the owning page still disagrees with backend state.");
    }
    lines.push("Mutation guardrail: this checklist cannot retry, launch, drain, save, rename, repair, delete, publish, open arbitrary paths, or bypass backend validation.");
    return lines;
  }

  function commandHistoryResolutionDetailLines(row) {
    if (!row) {
      return [
        "Command failure resolution checklist:",
        "Select a checkpoint before retrying from an owning page.",
        "Mutation guardrail: this detail panel is read-only.",
      ];
    }
    const lines = [
      "Command failure resolution checklist:",
      `Checkpoint: ${row.checkpoint || "unknown"}`,
      `Posture: ${row.posture || "read-only"}`,
      `Evidence: ${row.evidence || ""}`,
      `Safe next step: ${row.action || ""}`,
    ];
    (Array.isArray(row.detail) ? row.detail : []).forEach((line) => lines.push(line));
    if (row.item) {
      lines.push("");
      lines.push("Associated command:");
      lines.push(`Command: ${row.item.command || "unknown"}`);
      lines.push(`Owner: ${commandHistoryOwnerPage(row.item)}`);
      lines.push(`Issue level: ${commandHistoryIssueLevel(row.item)}`);
      lines.push(`Refresh target: ${commandHistoryRefreshTarget(row.item)}`);
      lines.push(`Message: ${row.item.message || ""}`);
    }
    lines.push("");
    lines.push("Guardrail: repeat actions only from the owning page after evidence agrees.");
    return lines;
  }

  function selectedCommandResolutionRow(rows) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === selectedCommandResolutionKey) || source[0] || null;
  }

  function selectCommandResolutionRow(row) {
    selectedCommandResolutionKey = row?.key || "";
    if (row?.item) selectedCommandKey = commandHistoryRowKey(row.item);
    renderCommandHistory();
  }

  function renderCommandResolutionChecklist(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const rows = commandHistoryResolutionRows(items);
    if (selectedCommandResolutionKey && !rows.some((row) => row.key === selectedCommandResolutionKey)) {
      selectedCommandResolutionKey = "";
    }
    const selected = selectedCommandResolutionRow(rows);
    const status = commandHistoryResolutionStatus(items);
    if (typeof setPanelStatus === "function") {
      setPanelStatus("diagnostics-command-resolution-status", status, commandHistoryResolutionStatusState(status));
    } else {
      setText("diagnostics-command-resolution-status", status);
      const statusNode = byId("diagnostics-command-resolution-status");
      if (statusNode) statusNode.dataset.state = commandHistoryResolutionStatusState(status);
    }
    setText("diagnostics-command-resolution-summary", commandHistoryResolutionSummaryLines(items).join("\n"));
    setText("diagnostics-command-resolution-detail", commandHistoryResolutionDetailLines(selected).join("\n"));
    const tbody = byId("diagnostics-command-resolution-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No command failure resolution rows loaded.");
      updateTableStatusLegend("diagnostics-command-resolution-legend", tbody, "Command failure resolution rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = commandHistoryResolutionPostureStatus(item.posture);
      appendCells(row, [item.checkpoint || "", item.posture || "Read-only", item.evidence || "", item.action || ""]);
      makeRowSelectable(row, () => selectCommandResolutionRow(item), {
        selected: item.key === selectedCommandResolutionKey,
        label: `Command failure resolution checkpoint ${item.checkpoint || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-command-resolution-legend", tbody, "Command failure resolution rows");
  }

  function nextCommandHistoryLocalId() {
    commandHistoryLocalSequence += 1;
    return `local-${Date.now()}-${commandHistoryLocalSequence}`;
  }

  function appendCommandResult(result) {
    const payload = result && typeof result === "object" ? result : {
      command: "unknown",
      ok: false,
      severity: "error",
      message: String(result || "Unknown command result."),
    };
    commandHistory.unshift({
      at: new Date().toLocaleTimeString(),
      command: payload.command || "unknown",
      result: commandResultLabel(payload),
      message: commandResultDisplayMessage(payload),
      ok: Boolean(payload.ok),
      severity: payload.severity || "",
      warnings: commandResultList(payload.warnings),
      errors: commandResultList(payload.errors),
      local: true,
      local_id: nextCommandHistoryLocalId(),
      raw: payload,
    });
    while (commandHistory.length > 20) commandHistory.pop();
    renderCommandHistory();
  }

  function renderCommandHistoryPayload(payload) {
    const entries = Array.isArray(payload?.entries) ? payload.entries : [];
    const localEntries = commandHistory.filter((entry) => entry?.local === true);
    const remoteEntries = entries.map((entry) => ({
      at: formatCommandHistoryTime(entry.at),
      command: entry.command || "unknown",
      result: commandResultLabel(entry),
      message: commandResultDisplayMessage(entry),
      ok: Boolean(entry.ok),
      severity: entry.severity || "",
      warnings: commandResultList(entry.warnings),
      errors: commandResultList(entry.errors),
      local: false,
      raw: entry,
    }));
    commandHistory = mergeCommandHistory(localEntries, remoteEntries);
    renderCommandHistory();
  }

  function commandHistoryRemoteSignature(item) {
    return [
      item?.command || "",
      item?.result || "",
      item?.message || "",
    ].join("\u001f");
  }

  function commandHistorySignature(item) {
    if (item?.local === true) {
      return [
        "local",
        item?.local_id || "",
        item?.at || "",
        item?.command || "",
        item?.result || "",
        item?.message || "",
      ].join("\u001f");
    }
    return commandHistoryRemoteSignature(item);
  }

  function mergeCommandHistory(localEntries, remoteEntries) {
    const remoteSeen = new Set(remoteEntries.map((entry) => commandHistoryRemoteSignature(entry)));
    const localSeen = new Set();
    const merged = [];
    localEntries.forEach((entry) => {
      if (remoteSeen.has(commandHistoryRemoteSignature(entry))) return;
      const signature = commandHistorySignature(entry);
      if (localSeen.has(signature)) return;
      localSeen.add(signature);
      merged.push(entry);
    });
    remoteEntries.forEach((entry) => merged.push(entry));
    return merged.slice(0, 20);
  }

  function getSelectedCommandEntry() {
    if (!selectedCommandKey) return null;
    return commandHistory.find((entry) => commandHistoryRowKey(entry) === selectedCommandKey) || null;
  }

  function selectCommandEntry(item) {
    selectedCommandKey = commandHistoryRowKey(item);
    renderCommandHistory();
  }

  function formatCommandHistoryTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleTimeString();
  }

  function commandHistorySummaryLines() {
    if (!commandHistory.length) {
      return [
        "Results: 0",
        "Next step: run a backend command or refresh after launching work.",
      ];
    }
    const warningCount = commandHistory.filter((entry) => entry.severity === "warning" || entry.warnings?.length).length;
    const errorCount = commandHistory.filter((entry) => !entry.ok && entry.severity !== "info").length;
    const localCount = commandHistory.filter((entry) => entry.local).length;
    const latest = commandHistory[0] || {};
    const lines = [
      `Results: ${commandHistory.length}`,
      `Latest: ${latest.command || "unknown"} [${latest.result || "unknown"}]`,
      `Warnings: ${warningCount}`,
      `Errors/blocked: ${errorCount}`,
      `Local pending visibility: ${localCount}`,
      `Journal-backed: ${Math.max(0, commandHistory.length - localCount)}`,
    ];
    if (errorCount) {
      lines.push("Next step: select a failed command, then open Diagnostics/Run Logs if the detail does not explain the backend rejection.");
    } else if (warningCount) {
      lines.push("Next step: review warning command details before retrying or launching another related action.");
    } else {
      lines.push("Next step: recent backend commands are not reporting warnings or errors.");
    }
    lines.push("", ...commandHistoryIssueDigestLines(commandHistory));
    const pendingEntries = commandHistoryPendingPublishEntries(commandHistory);
    if (pendingEntries.length) {
      lines.push("", ...commandHistoryPendingPublishDigestLines(commandHistory));
    }
    return lines;
  }

  function formatCommandDataBlock(label, value) {
    if (!value || typeof value !== "object" || !Object.keys(value).length) return "";
    return `${label}:\n${boundedCommandText(JSON.stringify(value, null, 2), 1200)}`;
  }

  function commandHistoryFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries
      .sort(([left], [right]) => String(left).localeCompare(String(right)))
      .map(([key, count]) => `${key || "unknown"}=${count}`)
      .join(", ");
  }

  function commandHistoryPendingPublishRowLabel(row) {
    const path = String(row?.local_file || row?.manifest_path || row?.server_out || row?.row_key || "(row)").trim();
    const leaf = path.split(/[\\/]/).filter(Boolean).pop() || path || "(row)";
    const action = row?.planned_action || row?.recovery_action || row?.diagnostic_status || row?.state || "review";
    const trust = row?.operator_trust_state || row?.drain_recommendation || row?.diagnostic_severity || "review";
    return `${leaf}: ${action} (${trust})`;
  }

  function commandHistoryPendingPublishDataLines(item) {
    const data = commandHistoryRawData(item);
    const request = commandHistoryRequestData(item);
    const kind = commandHistoryPendingPublishCommandKind(item);
    const level = commandHistoryPendingPublishIssueLevel(item);
    const lines = [
      "Pending Publish command triage:",
      `Command kind: ${kind}`,
      `Issue level: ${level}`,
      `Submitted scope/mode: ${request.scope || request.mode || data.mode || data.requested_mode || data.actual_mode || "not reported"}`,
      `Rows planned/attempted: ${data.row_count ?? data.attempted_count ?? data.manifest_count_at_start ?? "not reported"}`,
      `Blockers/review/ready: ${data.blocker_count || 0} / ${data.review_count || 0} / ${data.ready_count || 0}`,
      `Succeeded/already/remaining: ${data.succeeded_count || 0} / ${data.already_published_count || 0} / ${data.remaining_count || 0}`,
      `Errors/skipped: ${data.error_count || 0} / ${data.skipped_count || 0}`,
      `Actions: ${commandHistoryFormatCounts(data.action_counts)}`,
      `Statuses: ${commandHistoryFormatCounts(data.status_counts)}`,
      data.mutation_guardrail || "Mutation guardrail: command history never repairs, drains, rewrites, moves, deletes, or publishes files by itself.",
      `Safe next action: ${commandHistoryPendingPublishSuggestedAction(item)}`,
    ];
    if (data.stopped) lines.push("Drain state: stopped before all pending rows could be resolved.");
    if (data.deferred) lines.push("Drain state: deferred without a full publish drain.");
    const summary = Array.isArray(data.summary_lines) ? data.summary_lines.filter(Boolean) : [];
    if (summary.length) {
      lines.push("", "Backend summary:");
      summary.slice(0, 6).forEach((line) => lines.push(`- ${line}`));
    }
    const rows = Array.isArray(data.rows) ? data.rows : Array.isArray(data.items) ? data.items : [];
    if (rows.length) {
      lines.push("", "Representative row evidence:");
      rows.slice(0, 5).forEach((row) => lines.push(`- ${commandHistoryPendingPublishRowLabel(row)}`));
      if (rows.length > 5) lines.push(`- ${rows.length - 5} more row(s) not shown.`);
    }
    const finalPlacementLines = commandHistoryFinalPlacementConflictLines(item);
    if (finalPlacementLines.length) lines.push("", ...finalPlacementLines);
    lines.push("Read-first order: Last Stderr -> Latest Failure Report -> Pending Publish state.");
    lines.push("Open-next order: Pending Publish -> Run Logs -> State Folder when manifests or drain summaries look malformed.");
    return lines;
  }

  function commandHistoryNormalizeEvidenceValue(value) {
    return String(value || "")
      .trim()
      .replace(/\//g, "\\")
      .replace(/\\+/g, "\\")
      .toLowerCase();
  }

  function commandHistoryEvidenceCandidates(item) {
    const data = commandHistoryRawData(item);
    const request = commandHistoryRequestData(item);
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    const values = [
      data.row_key,
      request.row_key,
      data.source_path,
      request.source_path,
      data.output_path,
      request.output_path,
      data.local_file,
      request.local_file,
      data.server_out,
      request.server_out,
      data.manifest_path,
      request.manifest_path,
      data.opened_path,
      request.opened_path,
      data.path,
      request.path,
      data.target_path,
      request.target_path,
      raw.row_key,
      raw.path,
    ];
    if (Array.isArray(request.selected_sources)) values.push(...request.selected_sources);
    if (Array.isArray(data.selected_sources)) values.push(...data.selected_sources);
    if (Array.isArray(data.rows)) {
      data.rows.slice(0, 5).forEach((row) => {
        values.push(row?.row_key, row?.source_path, row?.local_file, row?.server_out, row?.manifest_path);
      });
    }
    return values
      .map(commandHistoryNormalizeEvidenceValue)
      .filter((value, index, all) => value.length >= 3 && all.indexOf(value) === index);
  }

  function commandHistoryRowEvidenceValues(row, fields) {
    return (Array.isArray(fields) ? fields : [])
      .map((field) => commandHistoryNormalizeEvidenceValue(row?.[field]))
      .filter(Boolean);
  }

  function commandHistoryMatchingRows(candidates, rows, fields) {
    const source = Array.isArray(rows) ? rows : [];
    const needles = Array.isArray(candidates) ? candidates.filter(Boolean) : [];
    if (!source.length || !needles.length) return [];
    return source.filter((row) => {
      const values = commandHistoryRowEvidenceValues(row, fields);
      return values.some((value) => needles.some((candidate) => value === candidate || (candidate.length > 8 && value.includes(candidate)) || (value.length > 8 && candidate.includes(value))));
    });
  }

  function commandHistoryOwnerLiveStateSummary(item) {
    if (!item) return {
      owner: "Unknown",
      loaded: false,
      evidence: "No command selected.",
      posture: "unknown",
      lines: ["Owner page live state handoff:", "No command selected."],
    };
    const owner = commandHistoryOwnerPage(item);
    const candidates = commandHistoryEvidenceCandidates(item);
    const issue = commandHistoryIssueLevel(item);
    const summary = {
      owner,
      loaded: false,
      evidence: "No cached owner-page state was available.",
      posture: issue === "ok" ? "read" : "review",
      lines: [
        "Owner page live state handoff:",
        `Owner page: ${owner}`,
        `Command: ${item.command || "unknown"}`,
        `Issue level: ${issue}`,
        `Refresh target: ${commandHistoryRefreshTarget(item)}`,
      ],
    };
    const finish = (loaded, evidence, matches = [], extra = []) => {
      summary.loaded = loaded;
      summary.evidence = evidence;
      if (!loaded) {
        summary.posture = "unknown";
      } else if (["error", "blocked"].includes(issue)) {
        summary.posture = "blocked";
      } else if (issue === "warning" || matches.length === 0) {
        summary.posture = "review";
      } else {
        summary.posture = "read";
      }
      summary.lines.push(evidence);
      if (matches.length) {
        summary.lines.push(`Matched owner row(s): ${matches.length}`);
        matches.slice(0, 3).forEach((row) => {
          const label = row.display_name || row.lookup_title || row.output_file || row.local_file || row.server_out || row.source_path || row.row_key || "(row)";
          const state = row.operator_trust_state || row.operator_status || row.diagnostic_status || row.state || row.output_health || row.status || "state not reported";
          summary.lines.push(`- ${boundedCommandText(label, 180)} (${state})`);
        });
      } else if (loaded && candidates.length) {
        summary.lines.push("Matched owner row(s): 0");
      }
      extra.filter(Boolean).forEach((line) => summary.lines.push(line));
      summary.lines.push("Read-first order: command detail -> owner page cached state -> backend allowlisted diagnostics tails.");
      summary.lines.push("Mutation guardrail: owner-state handoff is read-only and cannot retry, launch, drain, save, rename, repair, delete, publish, rewrite manifests, or open arbitrary paths.");
      return summary;
    };

    if (owner === "Queue" && typeof getLastQueueRows === "function") {
      const rows = getLastQueueRows();
      const payload = typeof getLastQueuePayload === "function" ? getLastQueuePayload() : {};
      const matches = commandHistoryMatchingRows(candidates, rows, ["row_key", "source_path", "relative_path", "display_name"]);
      return finish(true, `Queue cached rows: ${rows.length}; snapshot=${payload?.produced_at || payload?.source || "loaded/unknown"}; row-key/path match=${matches.length ? "yes" : "no"}.`, matches, [
        "Owner action: inspect Queue selected-row proof and Launch Decision Checklist before starting work.",
      ]);
    }

    const completedView = window.mediaPipelineCompletedView || {};
    if (owner === "Completed" && typeof completedView.getLastCompletedRows === "function") {
      const rows = completedView.getLastCompletedRows();
      const payload = typeof completedView.getLastCompletedPayload === "function" ? completedView.getLastCompletedPayload() : {};
      const matches = commandHistoryMatchingRows(candidates, rows, ["row_key", "source_path", "output_path", "sidecar_path", "output_file", "lookup_title"]);
      return finish(true, `Completed cached rows: ${rows.length}; manifest=${payload?.source || "loaded/unknown"}; row-key/path match=${matches.length ? "yes" : "no"}.`, matches, [
        "Owner action: compare Completed Manifest, Output Acceptance, and Completed/Pending proof before rerun or cleanup decisions.",
        ...commandHistoryFinalPlacementConflictLines(item),
      ]);
    }

    if (owner === "Pending Publish" && typeof getLastPendingPublishPayload === "function") {
      const payload = getLastPendingPublishPayload() || {};
      const rows = Array.isArray(payload.rows) ? payload.rows : [];
      const matches = commandHistoryMatchingRows(candidates, rows, ["row_key", "local_file", "server_out", "destination_path", "source_path", "manifest_path"]);
      const guard = typeof pendingDrainGuardState === "function" ? pendingDrainGuardState() : null;
      return finish(true, `Pending cached rows: ${rows.length}; pending root=${payload.pending_root || payload.source || "loaded/unknown"}; row-key/path match=${matches.length ? "yes" : "no"}.`, matches, [
        guard ? `Drain Button Guard: ${guard.status || "unknown"}; ${guard.action || guard.message || ""}` : "Drain Button Guard: unavailable in this command context.",
        "Owner action: inspect Pending Publish recovery/drain evidence before another publish attempt.",
        ...commandHistoryFinalPlacementConflictLines(item),
      ]);
    }

    if (owner === "Launch") {
      const launchView = window.mediaPipelineLaunchView || {};
      const preflightPayloads = typeof launchView.getLastLaunchBackendPreflightPayloads === "function" ? launchView.getLastLaunchBackendPreflightPayloads() : [];
      const pipelinePreflight = Array.isArray(preflightPayloads) ? preflightPayloads.find((payload) => String(payload?.target || "").toLowerCase() === "pipeline") : null;
      const launchIntent = typeof launchView.launchSettingsIntentStatus === "function" ? launchView.launchSettingsIntentStatus() : "unavailable";
      const queueDecision = typeof queueLaunchDecisionStatus === "function" ? queueLaunchDecisionStatus() : "unavailable";
      return finish(true, `Launch cached evidence: preflight=${pipelinePreflight?.status || "missing"}; launch intent=${launchIntent}; queue decision=${queueDecision}.`, [], [
        "Owner action: compare Backend Launch Preflight, Saved Settings vs Launch Intent, Queue-to-Launch Handoff, and Diagnostics before pressing Start again.",
      ]);
    }

    if (owner === "Settings") {
      const unsaved = typeof settingsPatchHasUnsavedChanges === "function" ? settingsPatchHasUnsavedChanges() : null;
      const workspace = typeof getLastSettings === "function" ? getLastSettings() : null;
      return finish(Boolean(workspace || unsaved !== null), `Settings cached evidence: workspace=${workspace ? "loaded" : "unavailable"}; unsaved staged patch=${unsaved === null ? "unknown" : unsaved ? "yes" : "no"}.`, [], [
        "Owner action: use Save Settings result panels before trusting settings persistence.",
      ]);
    }

    if (owner === "Rename") {
      return finish(true, "Rename cached evidence: apply commands must be checked against Rename preview/readiness and backend apply result.", [], [
        "Owner action: inspect Rename Apply Readiness and apply history before repeating a batch rename.",
      ]);
    }

    if (owner === "Diagnostics") {
      return finish(true, "Diagnostics cached evidence: use State Artifact Summary, Command Result Drilldown, and allowlisted tails/opens.", [], [
        "Owner action: read bounded tails before shell-opening folders/files.",
      ]);
    }

    return finish(false, `No owner-state adapter is defined for ${owner}.`, [], [
      "Owner action: refresh the owning page and use Diagnostics allowlisted evidence before repeating the command.",
    ]);
  }

  function commandHistoryOwnerLiveStateLines(item) {
    return commandHistoryOwnerLiveStateSummary(item).lines;
  }

  function commandHistorySpecializedDetailLines(item) {
    if (commandHistoryIsPendingPublishCommand(item)) {
      return commandHistoryPendingPublishDataLines(item);
    }
    return [];
  }

  function commandHistoryDetailLines(item) {
    if (!item) {
      return [
        "No command row selected.",
        "Select a row to inspect backend message, warnings, errors, refresh hint, data, and submitted request when available.",
      ];
    }
    const raw = item.raw && typeof item.raw === "object" ? item.raw : {};
    const lines = [
      `Time: ${item.at || ""}`,
      `Command: ${item.command || "unknown"}`,
      `Result: ${item.result || "unknown"}`,
      `Source: ${item.local ? "local pending result" : "backend journal"}`,
      `Message: ${item.message || ""}`,
    ];
    lines.push("", ...commandHistoryTraceLines(item));
    lines.push("", ...commandHistoryOwnerLiveStateLines(item));
    const specialized = commandHistorySpecializedDetailLines(item);
    if (specialized.length) lines.push("", ...specialized);
    const bridge = diagnosticsBridgeApi();
    if (typeof bridge.diagnosticsBridgeHandoffLines === "function") {
      lines.push("", ...bridge.diagnosticsBridgeHandoffLines("Command result selected row", commandHistoryDiagnosticsActions(item), {
        evidence: [
          item.command ? `command=${item.command}` : "",
          item.result ? `result=${item.result}` : "",
          raw.refresh_hint ? `refresh=${raw.refresh_hint}` : "",
          item.message ? `message=${item.message}` : "",
        ],
        safeAction: "use command owner page, refresh hint, and Diagnostics targets before retrying blocked or warning commands.",
      }));
    }
    const warnings = commandResultList(item.warnings || raw.warnings);
    const errors = commandResultList(item.errors || raw.errors);
    if (warnings.length) lines.push(`Warnings: ${warnings.join(" | ")}`);
    if (errors.length) lines.push(`Errors: ${errors.join(" | ")}`);
    if (raw.refresh_hint) lines.push(`Refresh hint: ${raw.refresh_hint}`);
    const dataBlock = formatCommandDataBlock("Backend data", raw.data);
    const requestBlock = formatCommandDataBlock("Submitted request", raw.request || raw.submitted_request);
    if (dataBlock) lines.push("", dataBlock);
    if (requestBlock) lines.push("", requestBlock);
    return lines;
  }

  function commandHistoryDiagnosticsDrilldownDetailLines(item) {
    if (!item) {
      return [
        "No command drilldown row selected.",
        "Select a warning/error command to see owner page, refresh target, backend message, submitted request, and diagnostics handoff.",
      ];
    }
    const actions = commandHistoryDiagnosticsActions(item);
    const lines = [
      "Selected command diagnostic drilldown:",
      `Owner page: ${commandHistoryOwnerPage(item)}`,
      `Command: ${item.command || "unknown"}`,
      `Issue level: ${commandHistoryIssueLevel(item)}`,
      `Refresh target: ${commandHistoryRefreshTarget(item)}`,
      `Message: ${item.message || ""}`,
      `Suggested next action: ${commandHistorySuggestedAction(item)}`,
      `Diagnostics targets: ${actions.map((action) => `${action.kind}:${action.target}`).join(", ") || "none inferred"}`,
      "Read-first order: bounded tail targets before opening folders/files.",
      "Open-next order: backend-selected allowlist targets only.",
      "Unsafe action: do not retry, drain, launch, save, rename, repair, delete, publish, or bypass validation from command history alone.",
    ];
    const warnings = commandResultList(item.warnings || item.raw?.warnings);
    const errors = commandResultList(item.errors || item.raw?.errors);
    if (warnings.length) lines.push(`Warnings: ${warnings.join(" | ")}`);
    if (errors.length) lines.push(`Errors: ${errors.join(" | ")}`);
    const specialized = commandHistorySpecializedDetailLines(item);
    if (specialized.length) lines.push("", ...specialized);
    const dataBlock = formatCommandDataBlock("Backend data", item.raw?.data);
    const requestBlock = formatCommandDataBlock("Submitted request", item.raw?.request || item.raw?.submitted_request);
    if (dataBlock) lines.push("", dataBlock);
    if (requestBlock) lines.push("", requestBlock);
    return lines;
  }

  function commandHistoryEvidenceTokens(item) {
    if (!item) return [];
    const raw = item.raw && typeof item.raw === "object" ? item.raw : {};
    const data = commandHistoryRawData(item);
    const request = commandHistoryRequestData(item);
    return [
      item.command,
      commandHistoryCommandText(item),
      commandHistoryRefreshTarget(item),
      raw.refresh_hint,
      data.target,
      request.target,
      data.row_key,
      request.row_key,
      data.scope,
      request.scope,
      data.mode,
      request.mode,
    ]
      .map((value) => String(value || "").trim().toLowerCase())
      .filter((value, index, all) => value.length >= 3 && all.indexOf(value) === index);
  }

  function commandHistoryLogEvidenceRows(item) {
    if (!item || typeof getLastDiagnosticsLogRows !== "function") return [];
    const tokens = commandHistoryEvidenceTokens(item);
    if (!tokens.length) return [];
    return getLastDiagnosticsLogRows()
      .filter((row) => {
        const haystack = [
          row.source,
          row.severity,
          row.timestamp,
          row.line,
        ].map((value) => String(value || "").toLowerCase()).join(" ");
        return tokens.some((token) => haystack.includes(token));
      })
      .slice(0, 6)
      .map((row) => ({
        evidence: "Visible diagnostics log row",
        confidence: "possible related evidence",
        source: `${row.source || "diagnostics"} ${row.severity || "info"} ${row.timestamp || ""}: ${boundedCommandText(row.line, 180)}`.trim(),
        action: "Read the bounded log text and compare timestamps/message text before retrying from the owning page.",
        status: row.severity === "error" ? "blocked" : row.severity === "warning" ? "warning" : "match",
      }));
  }

  function commandHistoryTargetEvidenceRows(item) {
    if (!item) return [];
    return commandHistoryDiagnosticsActions(item).slice(0, 8).map((action) => ({
      evidence: action.kind === "tail" ? "Allowlisted bounded text target" : "Allowlisted open target",
      confidence: "operator evidence target",
      source: `${action.kind}:${action.target}`,
      action: action.reason || "Use this backend allowlist target for investigation before acting.",
      status: action.kind === "tail" ? "warning" : "",
    }));
  }

  function commandHistoryDiagnosticsEvidenceRows(item) {
    if (!item) return [];
    const ownerState = commandHistoryOwnerLiveStateSummary(item);
    const finalPlacement = commandHistoryFinalPlacementConflictSummary(item);
    const finalPlacementRow = finalPlacement.applies ? [{
      evidence: "Completed/Pending final-placement proof",
      confidence: finalPlacement.rows.length ? "cached Completed/Pending proof" : "proof not loaded",
      source: finalPlacement.evidence,
      action: finalPlacement.action,
      status: finalPlacement.posture === "blocked" ? "blocked" : finalPlacement.posture === "review" ? "warning" : finalPlacement.posture === "unknown" ? "unknown" : "match",
    }] : [];
    return [
      {
        evidence: "Owner page live state",
        confidence: ownerState.loaded ? "cached owner page state" : "owner page state unavailable",
        source: ownerState.evidence,
        action: ownerState.loaded ? "Compare owner-page cached state with command detail before retrying from that page." : "Refresh the owning page before retrying from command history.",
        status: ownerState.posture === "blocked" ? "blocked" : ownerState.posture === "review" ? "warning" : ownerState.posture === "unknown" ? "unknown" : "match",
      },
      ...finalPlacementRow,
      ...commandHistoryLogEvidenceRows(item),
      ...commandHistoryTargetEvidenceRows(item),
    ];
  }

  function commandHistoryDiagnosticsEvidenceStatus(item) {
    if (!item) return "No selection";
    const rows = commandHistoryDiagnosticsEvidenceRows(item);
    const logRows = rows.filter((row) => row.evidence === "Visible diagnostics log row");
    const finalPlacementRows = rows.filter((row) => row.evidence === "Completed/Pending final-placement proof");
    if (finalPlacementRows.some((row) => row.status === "blocked")) return "Final-placement blocked";
    if (finalPlacementRows.some((row) => row.status === "warning")) return "Final-placement review";
    if (logRows.some((row) => row.status === "blocked")) return "Possible error evidence";
    if (logRows.length) return "Possible log evidence";
    if (rows.length) return "Targets available";
    return "No evidence";
  }

  function commandHistoryDiagnosticsEvidenceSummaryLines(item) {
    if (!item) {
      return [
        "No command diagnostics evidence loaded.",
        "Select a command drilldown row to correlate it with visible diagnostics log rows and backend allowlist targets.",
      ];
    }
    const rows = commandHistoryDiagnosticsEvidenceRows(item);
    const logRows = rows.filter((row) => row.evidence === "Visible diagnostics log row");
    const ownerRows = rows.filter((row) => row.evidence === "Owner page live state");
    const finalPlacementRows = rows.filter((row) => row.evidence === "Completed/Pending final-placement proof");
    const targetRows = rows.filter((row) => ![
      "Visible diagnostics log row",
      "Owner page live state",
      "Completed/Pending final-placement proof",
    ].includes(row.evidence));
    const lines = [
      "Command / diagnostics evidence correlation:",
      `Selected command: ${item.command || "unknown"} (${commandHistoryOwnerPage(item)}; ${commandHistoryIssueLevel(item)})`,
      `Owner page live-state rows: ${ownerRows.length}`,
      `Completed/Pending final-placement proof rows: ${finalPlacementRows.length}`,
      `Possible visible log matches: ${logRows.length}`,
      `Backend allowlist evidence targets: ${targetRows.length}`,
      `Refresh target: ${commandHistoryRefreshTarget(item)}`,
    ];
    if (finalPlacementRows.some((row) => row.status === "blocked" || row.status === "warning")) {
      lines.push("Interpretation: final-placement proof is active. Compare Completed-to-Pending proof and durable drain summary before any rerun, cleanup, or publish retry.");
    }
    if (logRows.length) {
      lines.push("Interpretation: matching visible log rows are possible related evidence only; compare timestamp, command, target, and backend detail before acting.");
    } else {
      lines.push("Interpretation: no visible diagnostics log row matched the selected command tokens. Use the allowlisted targets below before retrying from the owning page.");
    }
    lines.push("Guardrail: this correlation cannot prove success/failure by itself and cannot retry, launch, drain, save, rename, repair, delete, publish, or open arbitrary paths.");
    return lines;
  }

  function requestCommandDiagnosticsAction(action, sourceButton = null) {
    const target = String(action?.target || "").trim();
    if (!target) return;
    if (action.kind === "tail") {
      if (typeof requestDiagnosticsTail === "function") requestDiagnosticsTail(target, sourceButton);
      return;
    }
    if (typeof requestDiagnosticsOpen === "function") requestDiagnosticsOpen(target, sourceButton);
  }

  function renderCommandDiagnosticsActions(item) {
    const container = byId("command-diagnostics-actions");
    if (!container) return;
    container.replaceChildren();
    if (!item) return;
    const bridge = diagnosticsBridgeApi();
    const actions = typeof bridge.diagnosticsBridgeActions === "function"
      ? bridge.diagnosticsBridgeActions(commandHistoryDiagnosticsActions(item))
      : commandHistoryDiagnosticsActions(item);
    if (typeof bridge.appendDiagnosticsBridgeGroupedButtons === "function") {
      bridge.appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "commandDiagnostics",
        onAction: requestCommandDiagnosticsAction,
      });
    } else {
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.textContent = typeof bridge.diagnosticsBridgeActionLabel === "function"
          ? bridge.diagnosticsBridgeActionLabel(action)
          : `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
        button.title = action.reason || "";
        button.dataset.commandDiagnosticsAction = action.kind;
        button.dataset.commandDiagnosticsTarget = action.target;
        button.addEventListener("click", () => requestCommandDiagnosticsAction(action, button));
        container.appendChild(button);
      });
    }
    if (typeof bridge.appendDiagnosticsBridgeButton === "function") {
      bridge.appendDiagnosticsBridgeButton(container, actions, "Command result selected row");
    }
  }

  function renderDiagnosticsCommandDrilldownActions(item) {
    const container = byId("diagnostics-command-drilldown-actions");
    if (!container) return;
    container.replaceChildren();
    if (!item) return;
    const bridge = diagnosticsBridgeApi();
    const actions = typeof bridge.diagnosticsBridgeActions === "function"
      ? bridge.diagnosticsBridgeActions(commandHistoryDiagnosticsActions(item))
      : commandHistoryDiagnosticsActions(item);
    if (typeof bridge.appendDiagnosticsBridgeGroupedButtons === "function") {
      bridge.appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "diagnosticsCommandDrilldown",
        onAction: requestCommandDiagnosticsAction,
      });
      return;
    }
    actions.forEach((action) => {
      const button = document.createElement("button");
      button.className = "secondary-button";
      button.type = "button";
      button.textContent = typeof bridge.diagnosticsBridgeActionLabel === "function"
        ? bridge.diagnosticsBridgeActionLabel(action)
        : `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
      button.title = action.reason || "";
      button.dataset.diagnosticsCommandDrilldownAction = action.kind;
      button.dataset.diagnosticsCommandDrilldownTarget = action.target;
      button.addEventListener("click", () => requestCommandDiagnosticsAction(action, button));
      container.appendChild(button);
    });
  }

  function renderCommandDiagnosticsEvidence(item) {
    const payload = item || null;
    const rows = commandHistoryDiagnosticsEvidenceRows(payload);
    const evidenceStatus = commandHistoryDiagnosticsEvidenceStatus(payload);
    if (typeof setPanelStatus === "function") {
      setPanelStatus("diagnostics-command-evidence-status", evidenceStatus);
    } else {
      setText("diagnostics-command-evidence-status", evidenceStatus);
    }
    setText("diagnostics-command-evidence-summary", commandHistoryDiagnosticsEvidenceSummaryLines(payload).join("\n"));
    const tbody = byId("diagnostics-command-evidence-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, payload ? "No command diagnostics evidence rows loaded." : "Select a command row to load diagnostics evidence.");
      updateTableStatusLegend("diagnostics-command-evidence-legend", tbody, "Command diagnostics evidence rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((itemRow) => {
      const row = document.createElement("tr");
      row.dataset.status = itemRow.status || "";
      appendCells(row, [
        itemRow.evidence,
        itemRow.confidence,
        itemRow.source,
        itemRow.action,
      ]);
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-command-evidence-legend", tbody, "Command diagnostics evidence rows");
  }

  function renderDiagnosticsCommandDrilldown(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const rows = commandHistoryDiagnosticsDrilldownRows(items);
    if (selectedCommandKey && !items.some((entry) => commandHistoryRowKey(entry) === selectedCommandKey)) {
      selectedCommandKey = "";
    }
    const selected = getSelectedCommandEntry();
    const drilldownStatus = commandHistoryDiagnosticsDrilldownStatus(items);
    if (typeof setPanelStatus === "function") {
      setPanelStatus("diagnostics-command-drilldown-status", drilldownStatus);
    } else {
      setText("diagnostics-command-drilldown-status", drilldownStatus);
    }
    setText("diagnostics-command-drilldown-summary", commandHistoryDiagnosticsDrilldownSummaryLines(items).join("\n"));
    setText("diagnostics-command-drilldown-detail", commandHistoryDiagnosticsDrilldownDetailLines(selected).join("\n"));
    renderDiagnosticsCommandDrilldownActions(selected);
    renderDiagnosticsCommandOwnerImpact(items);
    renderCommandDiagnosticsEvidence(selected);
    renderCommandResolutionChecklist(items);
    const tbody = byId("diagnostics-command-drilldown-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No command-result drilldown rows loaded.");
      updateTableStatusLegend("diagnostics-command-drilldown-legend", tbody, "Command drilldown rows");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 20).forEach((entry) => {
      const row = document.createElement("tr");
      row.dataset.status = ["error", "blocked"].includes(entry.issue) ? "blocked" : entry.issue === "warning" ? "warning" : "match";
      row.dataset.rowKey = entry.key;
      appendCells(row, [
        entry.owner,
        entry.command,
        entry.issue,
        entry.refresh,
        entry.nextAction,
      ]);
      makeRowSelectable(row, () => selectCommandEntry(entry.item), {
        selected: Boolean(entry.key && entry.key === selectedCommandKey),
        label: `Diagnostics command drilldown ${entry.command} ${entry.issue}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-command-drilldown-legend", tbody, "Command drilldown rows");
  }

  function renderCommandSummary() {
    setText("command-summary", commandHistorySummaryLines().join("\n"));
  }

  function renderCommandDetail(item) {
    setText("command-detail", commandHistoryDetailLines(item).join("\n"));
    renderCommandDiagnosticsActions(item || null);
  }

  function renderLaunchPipelineControlHistory(history) {
    const launchView = window.mediaPipelineLaunchView || {};
    if (typeof launchView.renderPipelineControlHistory === "function") {
      launchView.renderPipelineControlHistory(history);
    }
  }

  function renderCommandHistory() {
    if (selectedCommandKey && !commandHistory.some((entry) => commandHistoryRowKey(entry) === selectedCommandKey)) {
      selectedCommandKey = "";
    }
    setText("command-status", `${commandHistory.length} result${commandHistory.length === 1 ? "" : "s"}`);
    const rawStatus = `${commandHistory.length} result${commandHistory.length === 1 ? "" : "s"}`;
    if (typeof setPanelStatus === "function") {
      setPanelStatus("diagnostics-command-status", rawStatus, commandHistory.length ? "changed" : "empty");
    } else {
      setText("diagnostics-command-status", rawStatus);
    }
    setText("diagnostics-command-history", [
      "Structured command drilldown above is the primary operator scan path.",
      "Raw command log follows for copy/paste evidence only.",
      "",
      formatCommandHistoryLines(),
    ].join("\n"));
    renderCommandSummary();
    renderCommandDetail(getSelectedCommandEntry());
    renderDiagnosticsCommandDrilldown(commandHistory);
    const launchHistoryView = window.mediaPipelineLaunchHistoryView || {};
    const launchView = window.mediaPipelineLaunchView || {};
    const completedView = window.mediaPipelineCompletedView || {};
    if (typeof launchHistoryView.renderLaunchCommandHistory === "function") {
      launchHistoryView.renderLaunchCommandHistory(commandHistory);
    }
    launchView.renderLaunchSettingsIntentChecklist?.();
    if (typeof renderPendingDrainHistory === "function") renderPendingDrainHistory(commandHistory);
    if (typeof renderPendingRecoveryPlanHistory === "function") renderPendingRecoveryPlanHistory(commandHistory);
    if (typeof renderPendingDrainDecisionChecklist === "function") renderPendingDrainDecisionChecklist(undefined, undefined, undefined, commandHistory);
    if (typeof renderPendingDrainGuard === "function") renderPendingDrainGuard(undefined, undefined, undefined, commandHistory);
    if (typeof renderMaintenanceDryRunHistory === "function") renderMaintenanceDryRunHistory(commandHistory);
    window.mediaPipelineSettingsCommandHistory?.renderSettingsCommandHistory?.(commandHistory);
    if (typeof renderQueueOpenHistory === "function") renderQueueOpenHistory(commandHistory);
    if (typeof renderQueueLaunchDecisionChecklist === "function") renderQueueLaunchDecisionChecklist(undefined, undefined, commandHistory);
    completedView.renderCompletedOpenHistory?.(commandHistory);
    completedView.renderCompletedOutputAcceptance?.(undefined, undefined, undefined, commandHistory);
    if (typeof renderCompletedFinalTrust === "function") renderCompletedFinalTrust(undefined, undefined, undefined, undefined, commandHistory);
    completedView.renderCompletedPilotEvidencePacket?.(undefined, undefined, undefined, undefined, commandHistory);
    if (typeof renderPendingOpenHistory === "function") renderPendingOpenHistory(commandHistory);
    if (typeof renderDiagnosticsOpenHistory === "function") renderDiagnosticsOpenHistory(commandHistory);
    window.mediaPipelineRenameHistoryView?.renderRenameApplyHistory?.(commandHistory);
    renderLaunchPipelineControlHistory(commandHistory);
    window.mediaPipelineReportsView?.renderReportOpenHistory?.(commandHistory);
    window.mediaPipelineNetworkView?.renderNetworkOpenHistory?.(commandHistory);
    const tbody = byId("command-rows");
    if (!tbody) return;
    if (!commandHistory.length) {
      clearRows(tbody, 6, "No command results yet.");
      updateTableStatusLegend("command-table-legend", tbody, "Command result rows");
      return;
    }
    tbody.replaceChildren();
    commandHistory.forEach((item) => {
      const row = document.createElement("tr");
      const issue = commandHistoryIssueLevel(item);
      row.dataset.status = ["error", "blocked"].includes(issue) ? "blocked" : issue === "warning" ? "warning" : item.ok ? "match" : "blocked";
      const key = commandHistoryRowKey(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item.at,
        item.command,
        commandHistoryOwnerPage(item),
        issue,
        item.result,
        item.message,
      ]);
      makeRowSelectable(row, () => selectCommandEntry(item), {
        selected: Boolean(key && key === selectedCommandKey),
        label: `Command result ${item.command || "unknown"} ${item.result || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("command-table-legend", tbody, "Command result rows");
  }

  function commandHistoryDiagnosticLine(item) {
    const owner = commandHistoryOwnerPage(item);
    const issue = commandHistoryIssueLevel(item);
    return `${item?.at || ""} ${item?.command || "unknown"} [${item?.result || ""}; ${owner}; issue=${issue}] ${item?.message || ""}`.trim();
  }

  function formatCommandHistoryLines() {
    return compactCommandHistoryBlockText({
      history: commandHistory,
      limit: commandHistory.length || 1,
      itemLabel: "backend command",
      emptyHistoryText: "No backend command history loaded.",
      lineFor: commandHistoryDiagnosticLine,
      header: false,
    });
  }

  function getCommandHistory() {
    return commandHistory.map((entry) => ({ ...entry }));
  }

  /**
   * Public namespace for the command history module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineCommandHistory = {
    appendCommandResult,
    renderCommandHistoryPayload,
    renderCommandHistory,
    getCommandHistory,
    formatCommandHistoryLines,
    formatCommandHistoryTime,
    commandHistorySignature,
    commandHistoryRowKey,
    mergeCommandHistory,
    selectCommandEntry,
    getSelectedCommandEntry,
    renderCommandSummary,
    renderCommandDetail,
    commandHistorySummaryLines,
    commandHistoryDetailLines,
    commandHistoryCommandText,
    commandHistoryCompactEvidenceLine,
    commandHistoryDiagnosticLine,
    compactCommandHistoryEntries,
    compactCommandHistoryBlockText,
    renderCompactCommandHistoryBlock,
    commandHistoryOwnerPage,
    commandHistoryIssueLevel,
    commandHistoryRefreshTarget,
    commandHistorySuggestedAction,
    commandHistoryOwnerCounts,
    commandHistoryIssueEntries,
    commandHistoryIssueDigestLines,
    commandHistoryPendingPublishEntries,
    commandHistoryPendingPublishDigestLines,
    commandHistoryPendingPublishCommandKind,
    commandHistoryPendingPublishIssueLevel,
    commandHistoryPendingPublishSuggestedAction,
    commandHistoryPendingPublishDataLines,
    commandHistoryFinalPlacementApplies,
    commandHistoryFinalPlacementProofRows,
    commandHistoryFinalPlacementConflictCounts,
    commandHistoryFinalPlacementConflictSummary,
    commandHistoryFinalPlacementConflictLines,
    commandHistoryOwnerLiveStateSummary,
    commandHistoryOwnerLiveStateLines,
    commandHistoryEvidenceCandidates,
    commandHistoryTraceLines,
    commandHistoryDiagnosticsDrilldownRows,
    commandHistoryDiagnosticsDrilldownStatus,
    commandHistoryDiagnosticsDrilldownSummaryLines,
    commandHistoryDiagnosticsDrilldownDetailLines,
    commandHistoryOwnerImpactRows,
    commandHistoryOwnerImpactStatus,
    commandHistoryOwnerImpactSummaryLines,
    renderDiagnosticsCommandOwnerImpact,
    commandHistoryResolutionRows,
    commandHistoryResolutionStatus,
    commandHistoryResolutionStatusState,
    commandHistoryResolutionSummaryLines,
    commandHistoryResolutionDetailLines,
    commandHistoryResolutionPostureStatus,
    renderCommandResolutionChecklist,
    commandHistoryDiagnosticsEvidenceRows,
    commandHistoryDiagnosticsEvidenceStatus,
    commandHistoryDiagnosticsEvidenceSummaryLines,
    commandHistoryDiagnosticsActions,
    renderCommandDiagnosticsActions,
    renderDiagnosticsCommandDrilldown,
    renderDiagnosticsCommandDrilldownActions,
    renderCommandDiagnosticsEvidence,
    commandResultLabel,
    commandResultDisplayMessage,
    commandResultFeedbackLines,
  };
  window.appendCommandResult = appendCommandResult;
  window.getCommandHistory = getCommandHistory;
  window.commandHistoryCompactEvidenceLine = commandHistoryCompactEvidenceLine;
})();
