(function () {
  /**
   * Projects live command history into a read-only failure-resolution checklist.
   * Selection is injected as getters/setters so the parent remains the state authority.
   */
  function createCommandHistoryResolutionChecklist(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const makeRowSelectable = deps.makeRowSelectable || function (row, handler) { if (row) row.addEventListener("click", handler); };
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const setPanelStatus = deps.setPanelStatus || null;
    const getHistory = deps.getHistory || function () { return []; };
    const getSelectedCommandEntry = deps.getSelectedCommandEntry || function () { return null; };
    const getSelectedCommandKey = deps.getSelectedCommandKey || function () { return ""; };
    const setSelectedCommandKey = deps.setSelectedCommandKey || function () {};
    const getSelectedResolutionKey = deps.getSelectedResolutionKey || function () { return ""; };
    const setSelectedResolutionKey = deps.setSelectedResolutionKey || function () {};
    const renderCommandHistory = deps.renderCommandHistory || function () {};
    const commandHistoryIssueEntries = deps.commandHistoryIssueEntries || function () { return []; };
    const commandHistoryDiagnosticsActions = deps.commandHistoryDiagnosticsActions || function () { return []; };
    const commandHistoryDiagnosticsEvidenceSummaryLines = deps.commandHistoryDiagnosticsEvidenceSummaryLines || function () { return []; };
    const commandHistoryLogEvidenceRows = deps.commandHistoryLogEvidenceRows || function () { return []; };
    const commandHistoryTargetEvidenceRows = deps.commandHistoryTargetEvidenceRows || function () { return []; };
    const commandHistoryOwnerImpactRows = deps.commandHistoryOwnerImpactRows || function () { return []; };
    const commandHistoryOwnerImpactSummaryLines = deps.commandHistoryOwnerImpactSummaryLines || function () { return []; };
    const commandHistoryOwnerLiveStateSummary = deps.commandHistoryOwnerLiveStateSummary || function () { return { posture: "unknown", evidence: "", lines: [] }; };
    const commandHistoryFinalPlacementConflictSummary = deps.commandHistoryFinalPlacementConflictSummary || function () { return { applies: false }; };
    const commandHistoryFinalPlacementConflictLines = deps.commandHistoryFinalPlacementConflictLines || function () { return []; };
    const commandHistoryIssueLevel = deps.commandHistoryIssueLevel || function () { return "unknown"; };
    const commandHistoryOwnerPage = deps.commandHistoryOwnerPage || function () { return "Unknown"; };
    const commandHistorySuggestedAction = deps.commandHistorySuggestedAction || function () { return "Review backend evidence."; };
    const commandHistoryDetailLines = deps.commandHistoryDetailLines || function () { return []; };
    const commandHistoryIssueDigestLines = deps.commandHistoryIssueDigestLines || function () { return []; };
    const commandHistoryRefreshTarget = deps.commandHistoryRefreshTarget || function () { return "Diagnostics"; };
    const commandHistoryRowKey = deps.commandHistoryRowKey || function () { return ""; };
    const commandHistoryTraceLines = deps.commandHistoryTraceLines || function () { return []; };
    const commandHistoryIsPendingPublishCommand = deps.commandHistoryIsPendingPublishCommand || function () { return false; };
    const commandHistoryPendingPublishIssueLevel = deps.commandHistoryPendingPublishIssueLevel || function () { return "unknown"; };
    const commandHistoryPendingPublishCommandKind = deps.commandHistoryPendingPublishCommandKind || function () { return "unknown"; };
    const commandHistoryPendingPublishSuggestedAction = deps.commandHistoryPendingPublishSuggestedAction || function () { return "Review backend evidence."; };
    const commandHistoryPendingPublishDataLines = deps.commandHistoryPendingPublishDataLines || function () { return []; };

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

  function commandHistoryResolutionRows(entries = getHistory()) {
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

  function commandHistoryResolutionStatus(entries = getHistory()) {
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

  function commandHistoryResolutionSummaryLines(entries = getHistory()) {
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
    return source.find((row) => row.key === getSelectedResolutionKey()) || source[0] || null;
  }

  function selectCommandResolutionRow(row) {
    setSelectedResolutionKey(row?.key || "");
    if (row?.item) setSelectedCommandKey(commandHistoryRowKey(row.item));
    renderCommandHistory();
  }

  function renderCommandResolutionChecklist(entries = getHistory()) {
    const items = Array.isArray(entries) ? entries : [];
    const rows = commandHistoryResolutionRows(items);
    if (getSelectedResolutionKey() && !rows.some((row) => row.key === getSelectedResolutionKey())) {
      setSelectedResolutionKey("");
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
        selected: item.key === getSelectedResolutionKey(),
        label: `Command failure resolution checkpoint ${item.checkpoint || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-command-resolution-legend", tbody, "Command failure resolution rows");
  }


    return {
      commandHistoryResolutionRows, commandHistoryResolutionStatus, commandHistoryResolutionStatusState,
      commandHistoryResolutionSummaryLines, commandHistoryResolutionDetailLines, commandHistoryResolutionPostureStatus,
      renderCommandResolutionChecklist, selectedCommandResolutionRow, selectCommandResolutionRow,
    };
  }

  window.__commandHistoryResolutionChecklistModule = createCommandHistoryResolutionChecklist;
})();
