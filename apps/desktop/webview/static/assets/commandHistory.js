(function () {
  const createCommandHistoryDiagnosticEvidence = window.__commandHistoryDiagnosticEvidenceModule;
  const createCommandHistoryResolutionChecklist = window.__commandHistoryResolutionChecklistModule;
  delete window.__commandHistoryDiagnosticEvidenceModule;
  delete window.__commandHistoryResolutionChecklistModule;
  if (typeof createCommandHistoryDiagnosticEvidence !== "function" || typeof createCommandHistoryResolutionChecklist !== "function") {
    throw new Error("Command History child modules must load before commandHistory.js");
  }

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

  function renderDiagnosticsOpenHistoryFromNamespace(history) {
    window.mediaPipelineDiagnosticsView?.renderDiagnosticsOpenHistory?.(history);
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
  const diagnosticEvidence = createCommandHistoryDiagnosticEvidence({
    boundedCommandText, commandHistoryCommandText, commandHistoryDiagnosticsActions, commandHistoryFinalPlacementConflictLines,
    commandHistoryFinalPlacementConflictSummary, commandHistoryIsPendingPublishCommand, commandHistoryIssueLevel,
    commandHistoryOwnerPage, commandHistoryPendingPublishCommandKind, commandHistoryPendingPublishIssueLevel,
    commandHistoryPendingPublishSuggestedAction, commandHistoryRawData, commandHistoryRefreshTarget, commandHistoryRequestData,
    commandHistorySuggestedAction, commandHistoryTraceLines, commandResultList, diagnosticsBridgeApi,
  });
  const {
    formatCommandDataBlock, commandHistoryFormatCounts, commandHistoryPendingPublishDataLines,
    commandHistoryEvidenceCandidates, commandHistoryOwnerLiveStateSummary, commandHistoryOwnerLiveStateLines,
    commandHistorySpecializedDetailLines, commandHistoryDetailLines, commandHistoryDiagnosticsDrilldownDetailLines,
    commandHistoryLogEvidenceRows, commandHistoryTargetEvidenceRows, commandHistoryDiagnosticsEvidenceRows,
    commandHistoryDiagnosticsEvidenceStatus, commandHistoryDiagnosticsEvidenceSummaryLines,
  } = diagnosticEvidence;
  const resolutionChecklist = createCommandHistoryResolutionChecklist({
    appendCells, byId, clearRows, commandHistoryDetailLines, commandHistoryDiagnosticsActions, commandHistoryDiagnosticsEvidenceSummaryLines, commandHistoryFinalPlacementConflictLines,
    commandHistoryFinalPlacementConflictSummary, commandHistoryIsPendingPublishCommand, commandHistoryIssueDigestLines,
    commandHistoryIssueEntries, commandHistoryIssueLevel, commandHistoryLogEvidenceRows, commandHistoryOwnerImpactRows,
    commandHistoryOwnerImpactSummaryLines, commandHistoryOwnerLiveStateSummary, commandHistoryOwnerPage,
    commandHistoryPendingPublishCommandKind, commandHistoryPendingPublishDataLines, commandHistoryPendingPublishIssueLevel,
    commandHistoryPendingPublishSuggestedAction, commandHistoryRefreshTarget, commandHistorySuggestedAction, commandHistoryTargetEvidenceRows,
    commandHistoryTraceLines, commandHistoryRowKey, getHistory: () => commandHistory, getSelectedCommandEntry, getSelectedCommandKey: () => selectedCommandKey,
    getSelectedResolutionKey: () => selectedCommandResolutionKey, makeRowSelectable, renderCommandHistory, setPanelStatus: typeof setPanelStatus === "function" ? setPanelStatus : null,
    setSelectedCommandKey: (key) => { selectedCommandKey = key; }, setSelectedResolutionKey: (key) => { selectedCommandResolutionKey = key; },
    setText, updateTableStatusLegend,
  });
  const {
    commandHistoryResolutionRows, commandHistoryResolutionStatus, commandHistoryResolutionStatusState,
    commandHistoryResolutionSummaryLines, commandHistoryResolutionDetailLines, commandHistoryResolutionPostureStatus,
    renderCommandResolutionChecklist, selectedCommandResolutionRow, selectCommandResolutionRow,
  } = resolutionChecklist;

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
    renderDiagnosticsOpenHistoryFromNamespace(commandHistory);
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
