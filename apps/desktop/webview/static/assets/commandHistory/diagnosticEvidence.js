(function () {
  /**
   * Derives read-only command, owner-state, and diagnostics evidence for a selected command.
   * It receives the façade's adapters explicitly and never performs a command, retry, or open action.
   */
  function createCommandHistoryDiagnosticEvidence(deps) {
    deps = deps || {};
    const boundedCommandText = deps.boundedCommandText || function (value) { return String(value || ""); };
    const commandHistoryCommandText = deps.commandHistoryCommandText || function (item) { return String(item?.command || ""); };
    const commandHistoryDiagnosticsActions = deps.commandHistoryDiagnosticsActions || function () { return []; };
    const commandHistoryFinalPlacementConflictLines = deps.commandHistoryFinalPlacementConflictLines || function () { return []; };
    const commandHistoryFinalPlacementConflictSummary = deps.commandHistoryFinalPlacementConflictSummary || function () { return { applies: false, rows: [] }; };
    const commandHistoryIsPendingPublishCommand = deps.commandHistoryIsPendingPublishCommand || function () { return false; };
    const commandHistoryIssueLevel = deps.commandHistoryIssueLevel || function () { return "unknown"; };
    const commandHistoryOwnerPage = deps.commandHistoryOwnerPage || function () { return "Unknown"; };
    const commandHistoryPendingPublishCommandKind = deps.commandHistoryPendingPublishCommandKind || function () { return "unknown"; };
    const commandHistoryPendingPublishIssueLevel = deps.commandHistoryPendingPublishIssueLevel || function () { return "unknown"; };
    const commandHistoryPendingPublishSuggestedAction = deps.commandHistoryPendingPublishSuggestedAction || function () { return "Review backend evidence."; };
    const commandHistoryRawData = deps.commandHistoryRawData || function () { return {}; };
    const commandHistoryRefreshTarget = deps.commandHistoryRefreshTarget || function () { return "Diagnostics"; };
    const commandHistoryRequestData = deps.commandHistoryRequestData || function () { return {}; };
    const commandHistorySuggestedAction = deps.commandHistorySuggestedAction || function () { return "Review backend evidence."; };
    const commandHistoryTraceLines = deps.commandHistoryTraceLines || function () { return []; };
    const commandResultList = deps.commandResultList || function () { return []; };
    const diagnosticsBridgeApi = deps.diagnosticsBridgeApi || function () { return {}; };

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
        "Owner action: use Backend Launch Preflight, Saved Settings vs Launch Intent, Queue-to-Launch Handoff, and Diagnostics to explain the backend result before retrying.",
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


    return {
      formatCommandDataBlock, commandHistoryFormatCounts, commandHistoryPendingPublishDataLines,
      commandHistoryEvidenceCandidates, commandHistoryOwnerLiveStateSummary, commandHistoryOwnerLiveStateLines,
      commandHistorySpecializedDetailLines, commandHistoryDetailLines, commandHistoryDiagnosticsDrilldownDetailLines,
      commandHistoryLogEvidenceRows, commandHistoryTargetEvidenceRows, commandHistoryDiagnosticsEvidenceRows,
      commandHistoryDiagnosticsEvidenceStatus, commandHistoryDiagnosticsEvidenceSummaryLines,
    };
  }

  window.__commandHistoryDiagnosticEvidenceModule = createCommandHistoryDiagnosticEvidence;
})();
