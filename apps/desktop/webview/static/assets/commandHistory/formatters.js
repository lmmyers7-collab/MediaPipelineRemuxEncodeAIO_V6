/* eslint-disable complexity, max-lines-per-function -- moved formatter logic during the command-history split without behavior changes. */
(function () {
  const COMMAND_RESULT_LIST_LIMIT = 5;
  const COMMAND_RESULT_ITEM_CHARS = 240;

  function commandResultLabel(result) {
    if (!result || typeof result !== "object") return "unknown";
    if (result.ok) return result.severity === "warning" ? "ok with warning" : "ok";
    return result.severity || "error";
  }


  function boundedCommandText(value, maxChars = COMMAND_RESULT_ITEM_CHARS) {
    const text = String(value || "").trim();
    if (!text) return "";
    if (text.length <= maxChars) return text;
    return `${text.slice(0, maxChars)}...`;
  }


  function commandResultList(value) {
    if (!Array.isArray(value)) return [];
    return value
      .map((item) => boundedCommandText(item))
      .filter(Boolean)
      .slice(0, COMMAND_RESULT_LIST_LIMIT);
  }

  function completedViewApi() {
    return window.mediaPipelineCompletedView || {};
  }


  function commandResultFeedbackLines(result) {
    const errors = commandResultList(result?.errors);
    const warnings = commandResultList(result?.warnings);
    const lines = [];
    if (errors.length) lines.push(`Errors: ${errors.join(" | ")}`);
    if (warnings.length) lines.push(`Warnings: ${warnings.join(" | ")}`);
    return lines;
  }


  function commandResultDisplayMessage(result) {
    const lines = [];
    const message = boundedCommandText(result?.message, 500);
    if (message) lines.push(message);
    lines.push(...commandResultFeedbackLines(result));
    return lines.join("\n");
  }


  function commandHistoryCommandText(item) {
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    return String(item?.command || raw.command || "").trim().toLowerCase();
  }


  function commandHistoryCompactEvidenceLine(item, options = {}) {
    if (!item) return String(options.emptyText || "none recorded");
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    const command = commandHistoryCommandText(item) || String(item?.command || raw.command || "unknown").trim();
    const label = typeof options.label === "function"
      ? options.label(command, item)
      : String(options.label || command || "unknown");
    const status = item?.result || commandResultLabel(raw.command ? raw : item);
    const source = item?.local ? "local" : "journal";
    const parts = [status, source];
    if (options.includeOwner !== false) parts.push(`owner=${commandHistoryOwnerPage(item)}`);
    if (options.includeIssue !== false) parts.push(`issue=${commandHistoryIssueLevel(item)}`);
    const message = boundedCommandText(item?.message || raw.message || "", options.messageChars || 180);
    const detail = typeof options.detail === "function"
      ? String(options.detail(item) || "")
      : String(options.detail || "");
    const time = options.includeTime === false ? "" : `${item?.at || ""} `;
    return `${time}${label} [${parts.join("; ")}] ${message}${detail}`.trim();
  }


  function compactCommandHistoryEntries(history = [], filter = null, limit = 6) {
    const source = Array.isArray(history) ? history : [];
    const predicate = typeof filter === "function" ? filter : () => true;
    return source.filter(predicate).slice(0, limit);
  }


  function compactCommandHistoryBlockText(options = {}) {
    const history = Array.isArray(options.history) ? options.history : [];
    const entries = Array.isArray(options.entries)
      ? options.entries
      : compactCommandHistoryEntries(history, options.filter, options.limit || 6);
    if (!history.length) return options.emptyHistoryText || "No command history loaded yet.";
    if (!entries.length) return options.emptyMatchText || "No matching commands found in the recent command history.";
    const label = options.itemLabel || "command";
    const lineFor = typeof options.lineFor === "function"
      ? options.lineFor
      : (entry) => commandHistoryCompactEvidenceLine(entry);
    const lines = [];
    if (options.header !== false) {
      lines.push(options.header || `Last ${entries.length} ${label}${entries.length === 1 ? "" : "s"}:`);
    }
    lines.push(...entries.map(lineFor));
    if (options.footer) lines.push(options.footer);
    return lines.join("\n");
  }


  function renderCompactCommandHistoryBlock(options = {}) {
    const history = Array.isArray(options.history) ? options.history : [];
    const entries = Array.isArray(options.entries)
      ? options.entries
      : compactCommandHistoryEntries(history, options.filter, options.limit || 6);
    if (options.statusId) {
      const status = typeof options.statusText === "function"
        ? options.statusText(entries, history)
        : options.statusText || `${entries.length} command${entries.length === 1 ? "" : "s"}`;
      setText(options.statusId, status);
    }
    if (options.targetId) {
      setText(options.targetId, compactCommandHistoryBlockText({ ...options, history, entries }));
    }
    return entries;
  }


  function commandHistoryOwnerPage(item) {
    const command = commandHistoryCommandText(item);
    const refresh = String(item?.raw?.refresh_hint || "").trim().toLowerCase();
    if (command.startsWith("settings.")) return "Settings";
    if (command.startsWith("schedule.")) return "Schedule";
    if (command.startsWith("rename.")) return "Rename";
    if (command.startsWith("queue.")) return "Queue";
    if (command.startsWith("completed.")) return "Completed";
    if (command.startsWith("pending_publish.")) return "Pending Publish";
    if (command.startsWith("diagnostics.")) return "Diagnostics";
    if (command.startsWith("report.") || command.includes("report")) return "Audit / Reports";
    if (command.startsWith("maintenance.")) return "Maintenance";
    if (command.startsWith("network.")) return "Network";
    if (command.startsWith("sample_validation.")) return "Home / Validation";
    if (command === "backend.shutdown") return "Diagnostics";
    if (command.startsWith("rerun.")) return "Queue";
    if (command.startsWith("pipeline.control.")) return "Launch";
    if (command === "pipeline.start") {
      const mode = String(item?.raw?.request?.mode || item?.raw?.data?.mode || item?.raw?.data?.requested_mode || "").toLowerCase();
      if (mode === "drain_pending_pushes") return "Pending Publish";
      return "Launch";
    }
    if (command === "audit.start") return "Launch";
    if (refresh === "pending_publish") return "Pending Publish";
    if (refresh === "queue") return "Queue";
    if (refresh === "completed") return "Completed";
    if (refresh === "settings") return "Settings";
    if (refresh === "schedule") return "Schedule";
    if (refresh === "snapshot") return "Home / Launch";
    return "Diagnostics";
  }


  function commandHistoryIssueLevel(item) {
    if (!item) return "none";
    const severity = String(item.severity || item.raw?.severity || "").toLowerCase();
    const result = String(item.result || "").toLowerCase();
    if (!item.ok && severity !== "info") return severity || "error";
    if (severity === "warning" || result.includes("warning") || (item.warnings || []).length) return "warning";
    if (severity === "info") return "info";
    return "ok";
  }


  function commandHistoryRefreshTarget(item) {
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    const refresh = String(raw.refresh_hint || "").trim();
    if (refresh) return refresh;
    return commandHistoryOwnerPage(item);
  }


  function commandHistoryRawData(item) {
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    return raw.data && typeof raw.data === "object" ? raw.data : {};
  }


  function commandHistoryRequestData(item) {
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    if (raw.request && typeof raw.request === "object") return raw.request;
    if (raw.submitted_request && typeof raw.submitted_request === "object") return raw.submitted_request;
    return {};
  }


  function commandHistoryIsPendingPublishCommand(item) {
    const command = commandHistoryCommandText(item);
    const data = commandHistoryRawData(item);
    const request = commandHistoryRequestData(item);
    const mode = String(data.mode || data.requested_mode || data.actual_mode || request.mode || "").toLowerCase();
    const refresh = String(item?.raw?.refresh_hint || "").toLowerCase();
    return (
      command.startsWith("pending_publish.") ||
      command.includes("pending-publish") ||
      command.includes("pending_publish") ||
      mode === "drain_pending_pushes" ||
      refresh === "pending_publish"
    );
  }


  function commandHistoryPendingPublishCommandKind(item) {
    const command = commandHistoryCommandText(item);
    const data = commandHistoryRawData(item);
    const request = commandHistoryRequestData(item);
    const mode = String(data.mode || data.requested_mode || data.actual_mode || request.mode || "").toLowerCase();
    if (command.includes("recovery_plan")) return "recovery dry-run";
    if (command.includes(".open")) return "backend-selected open";
    if (command.includes(".drain") || mode === "drain_pending_pushes") return "publish drain";
    return "pending publish command";
  }


  function commandHistoryPendingPublishIssueLevel(item) {
    const data = commandHistoryRawData(item);
    if (!item?.ok) return "blocked";
    if (Number(data.blocker_count || 0) > 0 || Number(data.error_count || 0) > 0) return "blocked";
    if (
      item?.severity === "warning" ||
      Number(data.review_count || 0) > 0 ||
      Number(data.skipped_count || 0) > 0 ||
      Number(data.remaining_count || 0) > 0 ||
      data.stopped ||
      data.deferred
    ) {
      return "review";
    }
    return "ok";
  }


  function commandHistoryPendingPublishSuggestedAction(item) {
    const kind = commandHistoryPendingPublishCommandKind(item);
    const level = commandHistoryPendingPublishIssueLevel(item);
    if (kind === "recovery dry-run") {
      if (level === "blocked") return "Do not drain yet. Inspect blocker rows in Pending Publish, then read Last Stderr and Run Logs before any publish retry.";
      if (level === "review") return "Review the planned row actions and evidence before using backend-owned Drain Parked Outputs.";
      return "No blocker was reported by the dry-run plan; refresh Pending Publish before deciding whether to drain.";
    }
    if (kind === "publish drain") {
      if (level === "blocked") return "Treat the drain as failed or incomplete. Refresh Pending Publish, read Last Stderr, inspect Last Drain Summary, then check destination/output proof before rerun.";
      if (level === "review") return "Compare remaining/skipped/deferred counts against Pending Publish and Completed before another drain attempt.";
      return "Refresh Pending Publish and Completed to confirm parked rows moved and outputs are visible.";
    }
    if (kind === "backend-selected open") {
      if (level === "blocked") return "Refresh Pending Publish and select the row again; do not paste paths manually or bypass backend row-key targeting.";
      return "Use the opened backend-selected path only as evidence; publish/repair decisions still belong to Pending Publish workflow.";
    }
    return "Use Pending Publish, Last Stderr, and Run Logs to reconcile this command with current parked output state.";
  }


  function commandHistorySuggestedAction(item) {
    if (!item) return "Select a command row to see the safest next action.";
    if (commandHistoryIsPendingPublishCommand(item)) {
      return commandHistoryPendingPublishSuggestedAction(item);
    }
    const level = commandHistoryIssueLevel(item);
    const owner = commandHistoryOwnerPage(item);
    const refresh = commandHistoryRefreshTarget(item);
    if (commandHistoryCommandText(item) === "backend.shutdown") {
      const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
      const data = raw.data && typeof raw.data === "object" ? raw.data : {};
      const watcher = data.continuous_watcher && typeof data.continuous_watcher === "object" ? data.continuous_watcher : {};
      const reasonText = String(data.reason || item?.message || raw.message || "").toLowerCase();
      if (String(watcher.status || "").toLowerCase() === "armed" || reasonText.includes("schedule-stop watcher")) {
        return "Do not retry shutdown blindly. Keep the backend alive until the schedule-stop watcher requests Stop, or use backend-owned Stop After Current before shutting down.";
      }
      if (level === "ok" || level === "warning") {
        return "Backend shutdown was requested. If the WebView remains open, wait for the shell lifecycle to finish or restart the preview backend.";
      }
      return "Check Close Readiness, ActiveJobs, Run Logs, and Last Stderr before retrying backend shutdown.";
    }
    if (level === "ok") {
      return `Refresh or inspect ${owner} only if the expected state did not update.`;
    }
    if (level === "info") {
      return `No recovery action is required unless ${owner} still disagrees with backend state.`;
    }
    if (level === "warning") {
      return `Review ${owner} and refresh ${refresh}; inspect Diagnostics if the warning affects launch, drain, rename, or settings confidence.`;
    }
    if (owner === "Diagnostics") {
      return "Use the diagnostics detail, allowlisted tail reader, and state artifact summary before retrying the command.";
    }
    return `Open ${owner}, inspect this command detail, then use Diagnostics > Run Logs / Last Stderr if the backend rejection is not self-explanatory.`;
  }


  function commandHistoryOwnerCounts(entries = []) {
    const counts = {};
    entries.forEach((entry) => {
      const owner = commandHistoryOwnerPage(entry);
      counts[owner] = (counts[owner] || 0) + 1;
    });
    return counts;
  }


  function commandHistoryIssueEntries(entries = []) {
    return entries.filter((entry) => {
      const level = commandHistoryIssueLevel(entry);
      return !["ok", "info", "none"].includes(level);
    });
  }


  function formatCommandCountMap(counts) {
    const entries = counts && typeof counts === "object" ? Object.entries(counts) : [];
    if (!entries.length) return "none";
    return entries
      .sort(([left], [right]) => String(left).localeCompare(String(right)))
      .map(([key, value]) => `${key || "unknown"}=${value}`)
      .join(", ");
  }


  function commandHistoryIssueDigestLines(entries = []) {
    const items = Array.isArray(entries) ? entries : [];
    const issues = commandHistoryIssueEntries(items);
    const severityCounts = {};
    issues.forEach((entry) => {
      const level = commandHistoryIssueLevel(entry);
      severityCounts[level] = (severityCounts[level] || 0) + 1;
    });
    const lines = [
      "Command issue digest:",
      `- Issue commands: ${issues.length}`,
      `- Issue severities: ${formatCommandCountMap(severityCounts)}`,
      `- Owner pages: ${formatCommandCountMap(commandHistoryOwnerCounts(issues))}`,
    ];
    if (issues.length) {
      const latest = issues[0];
      lines.push(`- Latest issue: ${latest.command || "unknown"} (${commandHistoryOwnerPage(latest)}; ${commandHistoryIssueLevel(latest)})`);
      lines.push(`- Next action: ${commandHistorySuggestedAction(latest)}`);
    } else {
      lines.push("- Next action: no backend command warnings or errors are visible in the current command stream.");
    }
    lines.push("- Guardrail: command history is read-only; retry, drain, rename, save, and launch actions remain page-specific backend-owned commands.");
    return lines;
  }


  function commandHistoryPendingPublishEntries(entries = []) {
    return (Array.isArray(entries) ? entries : []).filter(commandHistoryIsPendingPublishCommand);
  }


  function commandHistoryPendingPublishDigestLines(entries = []) {
    const pendingEntries = commandHistoryPendingPublishEntries(entries);
    if (!pendingEntries.length) {
      return [
        "Pending Publish command digest:",
        "- Commands: 0",
        "- Next action: no pending-publish command results are visible in the current command stream.",
      ];
    }
    const kindCounts = {};
    const levelCounts = {};
    pendingEntries.forEach((entry) => {
      const kind = commandHistoryPendingPublishCommandKind(entry);
      const level = commandHistoryPendingPublishIssueLevel(entry);
      kindCounts[kind] = (kindCounts[kind] || 0) + 1;
      levelCounts[level] = (levelCounts[level] || 0) + 1;
    });
    const latest = pendingEntries[0];
    const lines = [
      "Pending Publish command digest:",
      `- Commands: ${pendingEntries.length}`,
      `- Kinds: ${formatCommandCountMap(kindCounts)}`,
      `- Levels: ${formatCommandCountMap(levelCounts)}`,
      `- Latest: ${latest.command || "unknown"} (${commandHistoryPendingPublishCommandKind(latest)}; ${commandHistoryPendingPublishIssueLevel(latest)})`,
      `- Next action: ${commandHistoryPendingPublishSuggestedAction(latest)}`,
      "- Guardrail: this digest is read-only; repair, drain, cleanup, and publish remain explicit backend-owned workflows.",
    ];
    const finalPlacement = commandHistoryFinalPlacementConflictSummary(latest);
    if (finalPlacement.applies) {
      lines.push(`- Final-placement proof: ${finalPlacement.evidence}`);
      lines.push(`- Final-placement next: ${finalPlacement.action}`);
    }
    return lines;
  }


  function commandHistoryFinalPlacementApplies(item) {
    if (!item) return false;
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    const data = commandHistoryRawData(item);
    const request = commandHistoryRequestData(item);
    const combined = [
      item.command,
      item.message,
      raw.refresh_hint,
      data.mode,
      request.mode,
      data.target,
      request.target,
      data.issue,
      data.issue_summary,
      data.output_health,
      ...(Array.isArray(item.errors) ? item.errors : []),
      ...(Array.isArray(item.warnings) ? item.warnings : []),
      ...(Array.isArray(raw.errors) ? raw.errors : []),
      ...(Array.isArray(raw.warnings) ? raw.warnings : []),
    ].map((value) => String(value || "").toLowerCase()).join(" ");
    return (
      commandHistoryIsPendingPublishCommand(item)
      || commandHistoryOwnerPage(item) === "Completed"
      || /\b(publish_missing_output|missing[_ -]?output|final[_ -]?placement|pending[_ -]?publish|drain|publish)\b/.test(combined)
    );
  }


  function commandHistoryFinalPlacementProofRows(item) {
    if (!commandHistoryFinalPlacementApplies(item)) return [];
    const completedView = window.mediaPipelineCompletedView || {};
    const cached = typeof completedView.getLastCompletedPendingProofRows === "function" ? completedView.getLastCompletedPendingProofRows() : [];
    if (Array.isArray(cached) && cached.length) return cached.slice();
    if (
      typeof completedView.completedPendingProofRows === "function"
      && typeof completedView.getLastCompletedPayload === "function"
      && typeof completedView.getLastCompletedRows === "function"
    ) {
      const completed = completedView.getLastCompletedPayload() || {};
      const completedRows = completedView.getLastCompletedRows() || [];
      const pending = typeof getLastPendingPublishPayload === "function" ? getLastPendingPublishPayload() || {} : {};
      return completedView.completedPendingProofRows(completed, completedRows, pending);
    }
    return [];
  }


  function commandHistoryFinalPlacementConflictCounts(rows) {
    const source = Array.isArray(rows) ? rows : [];
    const completedView = completedViewApi();
    const isFinalPlacementReviewSignal = completedView.completedPendingProofIsFinalPlacementReviewSignal;
    return source.reduce((acc, row) => {
      const signal = String(row?.signal || "");
      const status = String(row?.status || "").toLowerCase();
      acc.total += 1;
      if (signal === "completed-missing-output-still-pending") acc.stillPending += 1;
      if (signal === "completed-missing-output-with-drain-proof") acc.drainProof += 1;
      if (signal === "completed-missing-output-no-pending-proof") acc.noProof += 1;
      if (typeof isFinalPlacementReviewSignal === "function" && isFinalPlacementReviewSignal(signal)) {
        acc.finalPlacement += 1;
      }
      if (status === "blocked") acc.blocked += 1;
      if (status === "warning" || status === "review") acc.review += 1;
      return acc;
    }, {
      total: 0,
      stillPending: 0,
      drainProof: 0,
      noProof: 0,
      finalPlacement: 0,
      blocked: 0,
      review: 0,
    });
  }


  function commandHistoryFinalPlacementConflictSummary(item) {
    const applies = commandHistoryFinalPlacementApplies(item);
    const rows = commandHistoryFinalPlacementProofRows(item);
    const counts = commandHistoryFinalPlacementConflictCounts(rows);
    if (!applies) {
      return {
        applies,
        rows,
        counts,
        posture: "read",
        evidence: "No publish/final-placement command context detected.",
        action: "Use the owning page and diagnostics evidence for this command.",
      };
    }
    if (!rows.length) {
      return {
        applies,
        rows,
        counts,
        posture: "unknown",
        evidence: "No cached Completed/Pending proof rows loaded.",
        action: "Refresh Completed and Pending Publish before deciding whether a publish/drain command really lost output.",
      };
    }
    const evidence = `proof rows=${counts.total}; still-pending=${counts.stillPending}; drain-proof=${counts.drainProof}; no-proof=${counts.noProof}; blocked=${counts.blocked}; review=${counts.review}.`;
    if (counts.noProof > 0) {
      return {
        applies,
        rows,
        counts,
        posture: "blocked",
        evidence,
        action: "Treat missing completed outputs without pending/drain proof as blocked; read Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup.",
      };
    }
    if (counts.stillPending > 0 || counts.drainProof > 0 || counts.finalPlacement > 0) {
      return {
        applies,
        rows,
        counts,
        posture: "review",
        evidence,
        action: "Treat as final-placement conflict; compare Completed > Completed-to-Pending output proof, Pending Publish, durable drain summary, Run Logs, and Last Stderr before another drain/rerun.",
      };
    }
    if (counts.blocked > 0) {
      return {
        applies,
        rows,
        counts,
        posture: "blocked",
        evidence,
        action: "Resolve blocked Completed/Pending proof before repeating the command.",
      };
    }
    return {
      applies,
      rows,
      counts,
      posture: counts.review > 0 ? "review" : "read",
      evidence,
      action: "Use Completed/Pending proof as supporting evidence only; command history remains read-only.",
    };
  }


  function commandHistoryFinalPlacementConflictLines(item) {
    const summary = commandHistoryFinalPlacementConflictSummary(item);
    if (!summary.applies) return [];
    const lines = [
      "Completed/Pending final-placement handoff:",
      `Evidence: ${summary.evidence}`,
      `Safe next step: ${summary.action}`,
      "Read-first order: Completed > Completed-to-Pending output proof -> Pending Publish drain/recovery evidence -> Run Logs / Last Stderr.",
      "Mutation guardrail: this handoff is read-only and cannot drain, rerun, cleanup, delete, publish, rewrite manifests, or touch media files.",
    ];
    if (summary.rows.length) {
      const completedView = completedViewApi();
      const signalLabel = completedView.completedPendingProofSignalLabel;
      const evidenceText = completedView.completedPendingProofEvidenceText;
      lines.push("Representative proof:");
      summary.rows.slice(0, 3).forEach((row) => {
        const signal = typeof signalLabel === "function" ? signalLabel(row.signal) : row.signal || "proof";
        const detail = typeof evidenceText === "function" ? evidenceText(row) : row.match_path || "";
        lines.push(`- ${signal}: ${boundedCommandText(detail, 220)}`);
      });
    } else {
      lines.push("Representative proof: none cached; refresh Completed and Pending Publish first.");
    }
    return lines;
  }


  function commandHistoryTraceLines(item) {
    if (!item) return [];
    return [
      "Command trace:",
      `Owner page: ${commandHistoryOwnerPage(item)}`,
      `Issue level: ${commandHistoryIssueLevel(item)}`,
      `Refresh target: ${commandHistoryRefreshTarget(item)}`,
      `Suggested next action: ${commandHistorySuggestedAction(item)}`,
      "Diagnostics handoff: use Diagnostics > Run Logs, Last Stderr, ActiveJobs, or State Artifact Summary when the command detail does not explain the backend result.",
      "Mutation guardrail: this trace does not retry, repair, drain, rename, save, launch, or open arbitrary paths.",
    ];
  }


  window.__commandHistoryFormatters = {
    commandResultLabel,
    boundedCommandText,
    commandResultList,
    commandResultFeedbackLines,
    commandResultDisplayMessage,
    commandHistoryCommandText,
    commandHistoryCompactEvidenceLine,
    compactCommandHistoryEntries,
    compactCommandHistoryBlockText,
    renderCompactCommandHistoryBlock,
    commandHistoryOwnerPage,
    commandHistoryIssueLevel,
    commandHistoryRefreshTarget,
    commandHistoryRawData,
    commandHistoryRequestData,
    commandHistoryIsPendingPublishCommand,
    commandHistoryPendingPublishCommandKind,
    commandHistoryPendingPublishIssueLevel,
    commandHistoryPendingPublishSuggestedAction,
    commandHistorySuggestedAction,
    commandHistoryOwnerCounts,
    commandHistoryIssueEntries,
    formatCommandCountMap,
    commandHistoryIssueDigestLines,
    commandHistoryPendingPublishEntries,
    commandHistoryPendingPublishDigestLines,
    commandHistoryFinalPlacementApplies,
    commandHistoryFinalPlacementProofRows,
    commandHistoryFinalPlacementConflictCounts,
    commandHistoryFinalPlacementConflictSummary,
    commandHistoryFinalPlacementConflictLines,
    commandHistoryTraceLines,
  };
})();
