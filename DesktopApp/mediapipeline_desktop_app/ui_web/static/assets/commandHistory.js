(function () {
  let commandHistory = [];
  let selectedCommandKey = "";
  let selectedCommandResolutionKey = "";
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
    if (command.startsWith("pipeline.control.")) return "Launch";
    if (command === "pipeline.start") {
      const mode = String(item?.raw?.request?.mode || item?.raw?.data?.mode || item?.raw?.data?.requested_mode || "").toLowerCase();
      if (mode === "drain_pending_pushes") return "Pending Publish";
      return "Launch";
    }
    if (command === "audit.start" || command === "rerun.start") return "Launch";
    if (refresh === "pending_publish") return "Pending Publish";
    if (refresh === "queue") return "Queue";
    if (refresh === "completed") return "Completed";
    if (refresh === "settings") return "Settings";
    if (refresh === "schedule") return "Schedule";
    if (refresh === "snapshot") return "Dashboard / Launch";
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
      if (level === "review") return "Review the planned row actions and evidence before using backend-owned Publish Parked Outputs.";
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

  function commandHistoryOwnerCounts(entries = commandHistory) {
    const counts = {};
    entries.forEach((entry) => {
      const owner = commandHistoryOwnerPage(entry);
      counts[owner] = (counts[owner] || 0) + 1;
    });
    return counts;
  }

  function commandHistoryIssueEntries(entries = commandHistory) {
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

  function commandHistoryIssueDigestLines(entries = commandHistory) {
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

  function commandHistoryPendingPublishEntries(entries = commandHistory) {
    return (Array.isArray(entries) ? entries : []).filter(commandHistoryIsPendingPublishCommand);
  }

  function commandHistoryPendingPublishDigestLines(entries = commandHistory) {
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
    const cached = typeof getLastCompletedPendingProofRows === "function" ? getLastCompletedPendingProofRows() : [];
    if (Array.isArray(cached) && cached.length) return cached.slice();
    if (
      typeof completedPendingProofRows === "function"
      && typeof getLastCompletedPayload === "function"
      && typeof getLastCompletedRows === "function"
    ) {
      const completed = getLastCompletedPayload() || {};
      const completedRows = getLastCompletedRows() || [];
      const pending = typeof getLastPendingPublishPayload === "function" ? getLastPendingPublishPayload() || {} : {};
      return completedPendingProofRows(completed, completedRows, pending);
    }
    return [];
  }

  function commandHistoryFinalPlacementConflictCounts(rows) {
    const source = Array.isArray(rows) ? rows : [];
    return source.reduce((acc, row) => {
      const signal = String(row?.signal || "");
      const status = String(row?.status || "").toLowerCase();
      acc.total += 1;
      if (signal === "completed-missing-output-still-pending") acc.stillPending += 1;
      if (signal === "completed-missing-output-with-drain-proof") acc.drainProof += 1;
      if (signal === "completed-missing-output-no-pending-proof") acc.noProof += 1;
      if (typeof completedPendingProofIsFinalPlacementReviewSignal === "function" && completedPendingProofIsFinalPlacementReviewSignal(signal)) {
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
      lines.push("Representative proof:");
      summary.rows.slice(0, 3).forEach((row) => {
        const signal = typeof completedPendingProofSignalLabel === "function" ? completedPendingProofSignalLabel(row.signal) : row.signal || "proof";
        const detail = typeof completedPendingProofEvidenceText === "function" ? completedPendingProofEvidenceText(row) : row.match_path || "";
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

  function commandHistoryDiagnosticsDrilldownRows(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const issues = commandHistoryIssueEntries(items);
    const rows = issues.length ? issues : items.slice(0, 8);
    return rows.map((item, index) => ({
      item,
      index,
      key: commandHistoryRowKey(item),
      owner: commandHistoryOwnerPage(item),
      issue: commandHistoryIssueLevel(item),
      refresh: commandHistoryRefreshTarget(item),
      command: commandHistoryCommandText(item) || item?.command || "unknown",
      nextAction: commandHistorySuggestedAction(item),
      diagnosticsTargets: commandHistoryDiagnosticsActions(item).map((action) => `${action.kind}:${action.target}`).join(", ") || "run_logs",
    }));
  }

  function commandHistoryDiagnosticsDrilldownStatus(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const issueRows = commandHistoryIssueEntries(items);
    if (!items.length) return "No commands";
    if (issueRows.length) return `${issueRows.length} issue command${issueRows.length === 1 ? "" : "s"}`;
    return "No command issues";
  }

  function commandHistoryDiagnosticsDrilldownSummaryLines(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const rows = commandHistoryDiagnosticsDrilldownRows(items);
    const issueRows = commandHistoryIssueEntries(items);
    const severityCounts = {};
    const refreshCounts = {};
    issueRows.forEach((entry) => {
      const level = commandHistoryIssueLevel(entry);
      const refresh = commandHistoryRefreshTarget(entry);
      severityCounts[level] = (severityCounts[level] || 0) + 1;
      refreshCounts[refresh] = (refreshCounts[refresh] || 0) + 1;
    });
    const lines = [
      "Diagnostics command-result drilldown:",
      `Commands loaded: ${items.length}`,
      `Issue commands: ${issueRows.length}`,
      `Issue severities: ${formatCommandCountMap(severityCounts)}`,
      `Owner pages with issues: ${formatCommandCountMap(commandHistoryOwnerCounts(issueRows))}`,
      `Refresh targets with issues: ${formatCommandCountMap(refreshCounts)}`,
    ];
    if (!items.length) {
      lines.push("Next action: run or refresh backend-owned commands to populate the command journal.");
    } else if (issueRows.length) {
      const latest = issueRows[0];
      lines.push(`Latest issue: ${latest.command || "unknown"} (${commandHistoryOwnerPage(latest)}; ${commandHistoryIssueLevel(latest)})`);
      lines.push(`Next action: ${commandHistorySuggestedAction(latest)}`);
    } else {
      lines.push("Next action: no backend command warnings or errors are visible. Use this panel only if a page state did not refresh as expected.");
    }
    if (rows.length) {
      lines.push("Displayed rows prioritize warning/error commands; recent successful commands appear only when no issues are loaded.");
    }
    lines.push("Read-first order: command detail -> Last Stderr / Latest Failure -> owning page state.");
    lines.push("Mutation guardrail: Diagnostics drilldown is read-only and never retries, launches, drains, saves, renames, repairs, deletes, publishes, or opens arbitrary paths.");
    return lines;
  }

  function commandHistoryOwnerImpactRows(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const sourceRows = commandHistoryIssueEntries(items);
    const rows = sourceRows.length ? sourceRows : items.slice(0, 8);
    const byOwner = new Map();
    rows.forEach((item, index) => {
      const owner = commandHistoryOwnerPage(item);
      const current = byOwner.get(owner) || {
        owner,
        entries: [],
        issueCounts: {},
        refreshCounts: {},
        latest: item,
        firstIndex: index,
      };
      current.entries.push(item);
      const level = commandHistoryIssueLevel(item);
      const refresh = commandHistoryRefreshTarget(item);
      current.issueCounts[level] = (current.issueCounts[level] || 0) + 1;
      current.refreshCounts[refresh] = (current.refreshCounts[refresh] || 0) + 1;
      if (!current.latest) current.latest = item;
      byOwner.set(owner, current);
    });
    return Array.from(byOwner.values()).sort((left, right) => {
      const rank = (row) => {
        if ((row.issueCounts.error || 0) || (row.issueCounts.blocked || 0)) return 0;
        if (row.issueCounts.warning || 0) return 1;
        if (row.issueCounts.info || 0) return 2;
        return 3;
      };
      return rank(left) - rank(right) || left.firstIndex - right.firstIndex;
    }).map((row) => ({
      ...row,
      key: `owner:${row.owner}`.toLocaleLowerCase(),
      latestCommand: commandHistoryCommandText(row.latest) || row.latest?.command || "unknown",
      latestIssue: commandHistoryIssueLevel(row.latest),
      latestRefresh: commandHistoryRefreshTarget(row.latest),
      latestAction: commandHistorySuggestedAction(row.latest),
    }));
  }

  function commandHistoryOwnerImpactStatus(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    if (!items.length) return "No commands";
    const rows = commandHistoryOwnerImpactRows(items);
    const issueRows = commandHistoryIssueEntries(items);
    if (issueRows.length) return `${rows.length} impacted owner${rows.length === 1 ? "" : "s"}`;
    return "No owner issues";
  }

  function commandHistoryOwnerImpactSummaryLines(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const rows = commandHistoryOwnerImpactRows(items);
    const issueRows = commandHistoryIssueEntries(items);
    const lines = [
      "Command owner impact:",
      `Commands loaded: ${items.length}`,
      `Issue commands: ${issueRows.length}`,
      `Owner rows: ${rows.length}`,
    ];
    if (!items.length) {
      lines.push("Next action: run or refresh backend-owned commands to populate owner impact.");
    } else if (issueRows.length) {
      const first = rows[0];
      lines.push(`First owner to inspect: ${first.owner} (${formatCommandCountMap(first.issueCounts)})`);
      lines.push(`Latest command: ${first.latestCommand} -> ${first.latestAction}`);
    } else {
      lines.push("Next action: no warning/error owners are visible. Owner rows show recent successful command ownership only when there are no issues.");
    }
    lines.push("Selection behavior: selecting an owner row selects its latest command and refreshes Command Result Drilldown plus Related Diagnostics Evidence.");
    lines.push("Guardrail: owner impact is read-only; repeat actions only from the owning page after backend evidence is understood.");
    return lines;
  }

  function renderDiagnosticsCommandOwnerImpact(entries = commandHistory) {
    const items = Array.isArray(entries) ? entries : [];
    const rows = commandHistoryOwnerImpactRows(items);
    setText("diagnostics-command-owner-status", commandHistoryOwnerImpactStatus(items));
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
    setText("diagnostics-command-resolution-status", status);
    const statusNode = byId("diagnostics-command-resolution-status");
    if (statusNode) statusNode.dataset.state = commandHistoryResolutionStatusState(status);
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

  function commandHistorySignature(item) {
    return [
      item?.command || "",
      item?.result || "",
      item?.message || "",
    ].join("\u001f");
  }

  function mergeCommandHistory(localEntries, remoteEntries) {
    const seen = new Set(remoteEntries.map((entry) => commandHistorySignature(entry)));
    const merged = [];
    localEntries.forEach((entry) => {
      const signature = commandHistorySignature(entry);
      if (seen.has(signature)) return;
      seen.add(signature);
      merged.push(entry);
    });
    remoteEntries.forEach((entry) => merged.push(entry));
    return merged.slice(0, 20);
  }

  function commandHistoryRowKey(item) {
    return [
      item?.at || "",
      item?.command || "",
      item?.result || "",
      item?.message || "",
      item?.local ? "local" : "journal",
    ].join("\u001f").toLocaleLowerCase();
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

    if (owner === "Completed" && typeof getLastCompletedRows === "function") {
      const rows = getLastCompletedRows();
      const payload = typeof getLastCompletedPayload === "function" ? getLastCompletedPayload() : {};
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
        guard ? `Publish Button Guard: ${guard.status || "unknown"}; ${guard.action || guard.message || ""}` : "Publish Button Guard: unavailable in this command context.",
        "Owner action: inspect Pending Publish recovery/drain evidence before another publish attempt.",
        ...commandHistoryFinalPlacementConflictLines(item),
      ]);
    }

    if (owner === "Launch") {
      const preflightPayloads = typeof getLastLaunchBackendPreflightPayloads === "function" ? getLastLaunchBackendPreflightPayloads() : [];
      const pipelinePreflight = Array.isArray(preflightPayloads) ? preflightPayloads.find((payload) => String(payload?.target || "").toLowerCase() === "pipeline") : null;
      const launchIntent = typeof launchSettingsIntentStatus === "function" ? launchSettingsIntentStatus() : "unavailable";
      const queueDecision = typeof queueLaunchDecisionStatus === "function" ? queueLaunchDecisionStatus() : "unavailable";
      return finish(true, `Launch cached evidence: preflight=${pipelinePreflight?.status || "missing"}; launch intent=${launchIntent}; queue decision=${queueDecision}.`, [], [
        "Owner action: compare Backend Launch Preflight, Saved Settings vs Launch Intent, Queue Launch Decision, and Diagnostics before pressing Start again.",
      ]);
    }

    if (owner === "Settings") {
      const unsaved = typeof settingsPatchHasUnsavedChanges === "function" ? settingsPatchHasUnsavedChanges() : null;
      const workspace = typeof getLastSettings === "function" ? getLastSettings() : null;
      return finish(Boolean(workspace || unsaved !== null), `Settings cached evidence: workspace=${workspace ? "loaded" : "unavailable"}; unsaved staged patch=${unsaved === null ? "unknown" : unsaved ? "yes" : "no"}.`, [], [
        "Owner action: use Preview Patch / Save Patch result panels before trusting settings persistence.",
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
    if (typeof diagnosticsBridgeHandoffLines === "function") {
      lines.push("", ...diagnosticsBridgeHandoffLines("Command result selected row", commandHistoryDiagnosticsActions(item), {
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

  function commandHistoryAddDiagnosticsAction(actions, kind, target, label, reason) {
    if (!target || actions.some((item) => item.kind === kind && item.target === target)) return;
    actions.push({ kind, target, label, reason });
  }

  function commandHistoryDiagnosticsTargetAllowed(target) {
    return [
      "active_jobs",
      "audit_reports",
      "completed_manifest",
      "config",
      "failed_markers",
      "failed_reports",
      "latest_audit_csv",
      "latest_failure_json",
      "latest_failure_report",
      "last_stderr_log",
      "last_stdout_log",
      "pending_publish",
      "queue_snapshot",
      "run_logs",
      "state",
    ].includes(String(target || "").trim());
  }

  function commandHistoryDiagnosticsActions(item) {
    const actions = [];
    const command = String(item?.command || "").toLowerCase();
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    const request = commandHistoryRequestData(item);
    const data = commandHistoryRawData(item);
    const requestedTarget = String(data.target || request.target || "").trim();
    commandHistoryAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Inspect backend logs around this command.");
    if (commandHistoryDiagnosticsTargetAllowed(requestedTarget)) {
      commandHistoryAddDiagnosticsAction(actions, "open", requestedTarget, `Open ${requestedTarget.replaceAll("_", " ")}`, "Open the exact backend allowlisted target referenced by this command.");
    }
    if (!item?.ok || item?.severity === "warning" || commandResultList(item?.errors || raw.errors).length) {
      commandHistoryAddDiagnosticsAction(actions, "tail", "last_stderr_log", "Read Last Stderr", "Read stderr context before retrying a blocked or warning command.");
    }
    if (command.includes("queue")) {
      commandHistoryAddDiagnosticsAction(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Compare command result against the current queue snapshot.");
    }
    if (command.includes("completed")) {
      commandHistoryAddDiagnosticsAction(actions, "open", "completed_manifest", "Open Completed Manifest", "Compare command result against completed history.");
    }
    if (commandHistoryIsPendingPublishCommand(item) || command.includes("drain")) {
      commandHistoryAddDiagnosticsAction(actions, "tail", "last_stderr_log", "Read Last Stderr", "Read the newest stderr context before retrying a pending publish command.");
      commandHistoryAddDiagnosticsAction(actions, "tail", "latest_failure_report", "Read Latest Failure", "Review the newest failure report for publish/copy/manifest errors.");
      commandHistoryAddDiagnosticsAction(actions, "open", "pending_publish", "Open Pending Publish", "Compare command result against parked output state.");
      if (Number(data.blocker_count || data.error_count || 0) > 0 || data.stopped || data.deferred) {
        commandHistoryAddDiagnosticsAction(actions, "open", "state", "Open State Folder", "Inspect pending state and drain summary artifacts after blocked or incomplete publish commands.");
      }
    }
    if (command.includes("failure") || command.includes("audit") || command.includes("rerun")) {
      commandHistoryAddDiagnosticsAction(actions, "tail", "latest_failure_report", "Read Latest Failure", "Review failure context before rerun.");
      commandHistoryAddDiagnosticsAction(actions, "open", "audit_reports", "Open Audit Reports", "Inspect audit outputs before CSV rerun decisions.");
    }
    if (command.includes("pipeline") || command.includes("launch") || command.includes("control")) {
      commandHistoryAddDiagnosticsAction(actions, "open", "active_jobs", "Open Active Jobs", "Compare command result against process lifecycle state.");
    }
    if (command.includes("settings")) {
      commandHistoryAddDiagnosticsAction(actions, "open", "config", "Open Config", "Inspect saved settings after backend validation/save commands.");
    }
    if (command.includes("sample_validation")) {
      commandHistoryAddDiagnosticsAction(actions, "tail", "sample_validation_log", "Read Validation Log", "Review backend-owned sample validation evidence records.");
      commandHistoryAddDiagnosticsAction(actions, "open", "sample_validation_log", "Open Validation Log", "Open the backend-owned sample validation log.");
    }
    return actions.slice(0, 8);
  }

  function requestCommandDiagnosticsAction(action) {
    const target = String(action?.target || "").trim();
    if (!target) return;
    if (action.kind === "tail") {
      if (typeof requestDiagnosticsTail === "function") requestDiagnosticsTail(target);
      return;
    }
    if (typeof requestDiagnosticsOpen === "function") requestDiagnosticsOpen(target);
  }

  function renderCommandDiagnosticsActions(item) {
    const container = byId("command-diagnostics-actions");
    if (!container) return;
    container.replaceChildren();
    if (!item) return;
    const actions = typeof diagnosticsBridgeActions === "function"
      ? diagnosticsBridgeActions(commandHistoryDiagnosticsActions(item))
      : commandHistoryDiagnosticsActions(item);
    if (typeof appendDiagnosticsBridgeGroupedButtons === "function") {
      appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "commandDiagnostics",
        onAction: requestCommandDiagnosticsAction,
      });
    } else {
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.textContent = typeof diagnosticsBridgeActionLabel === "function"
          ? diagnosticsBridgeActionLabel(action)
          : `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
        button.title = action.reason || "";
        button.dataset.commandDiagnosticsAction = action.kind;
        button.dataset.commandDiagnosticsTarget = action.target;
        button.addEventListener("click", () => requestCommandDiagnosticsAction(action));
        container.appendChild(button);
      });
    }
    if (typeof appendDiagnosticsBridgeButton === "function") {
      appendDiagnosticsBridgeButton(container, actions, "Command result selected row");
    }
  }

  function renderDiagnosticsCommandDrilldownActions(item) {
    const container = byId("diagnostics-command-drilldown-actions");
    if (!container) return;
    container.replaceChildren();
    if (!item) return;
    const actions = typeof diagnosticsBridgeActions === "function"
      ? diagnosticsBridgeActions(commandHistoryDiagnosticsActions(item))
      : commandHistoryDiagnosticsActions(item);
    if (typeof appendDiagnosticsBridgeGroupedButtons === "function") {
      appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "diagnosticsCommandDrilldown",
        onAction: requestCommandDiagnosticsAction,
      });
      return;
    }
    actions.forEach((action) => {
      const button = document.createElement("button");
      button.className = "secondary-button";
      button.type = "button";
      button.textContent = typeof diagnosticsBridgeActionLabel === "function"
        ? diagnosticsBridgeActionLabel(action)
        : `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
      button.title = action.reason || "";
      button.dataset.diagnosticsCommandDrilldownAction = action.kind;
      button.dataset.diagnosticsCommandDrilldownTarget = action.target;
      button.addEventListener("click", () => requestCommandDiagnosticsAction(action));
      container.appendChild(button);
    });
  }

  function renderCommandDiagnosticsEvidence(item) {
    const payload = item || null;
    const rows = commandHistoryDiagnosticsEvidenceRows(payload);
    setText("diagnostics-command-evidence-status", commandHistoryDiagnosticsEvidenceStatus(payload));
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
    setText("diagnostics-command-drilldown-status", commandHistoryDiagnosticsDrilldownStatus(items));
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

  function renderCommandHistory() {
    if (selectedCommandKey && !commandHistory.some((entry) => commandHistoryRowKey(entry) === selectedCommandKey)) {
      selectedCommandKey = "";
    }
    setText("command-status", `${commandHistory.length} result${commandHistory.length === 1 ? "" : "s"}`);
    setText("diagnostics-command-status", `${commandHistory.length} result${commandHistory.length === 1 ? "" : "s"}`);
    setText("diagnostics-command-history", formatCommandHistoryLines());
    renderCommandSummary();
    renderCommandDetail(getSelectedCommandEntry());
    renderDiagnosticsCommandDrilldown(commandHistory);
    if (typeof renderLaunchCommandHistory === "function") renderLaunchCommandHistory(commandHistory);
    if (typeof renderLaunchSettingsIntentChecklist === "function") renderLaunchSettingsIntentChecklist();
    if (typeof renderPendingDrainHistory === "function") renderPendingDrainHistory(commandHistory);
    if (typeof renderPendingRecoveryPlanHistory === "function") renderPendingRecoveryPlanHistory(commandHistory);
    if (typeof renderPendingDrainDecisionChecklist === "function") renderPendingDrainDecisionChecklist(undefined, undefined, undefined, commandHistory);
    if (typeof renderPendingDrainGuard === "function") renderPendingDrainGuard(undefined, undefined, undefined, commandHistory);
    if (typeof renderMaintenanceDryRunHistory === "function") renderMaintenanceDryRunHistory(commandHistory);
    if (typeof renderSettingsCommandHistory === "function") renderSettingsCommandHistory(commandHistory);
    if (typeof renderQueueOpenHistory === "function") renderQueueOpenHistory(commandHistory);
    if (typeof renderQueueLaunchDecisionChecklist === "function") renderQueueLaunchDecisionChecklist(undefined, undefined, commandHistory);
    if (typeof renderCompletedOpenHistory === "function") renderCompletedOpenHistory(commandHistory);
    if (typeof renderCompletedOutputAcceptance === "function") renderCompletedOutputAcceptance(undefined, undefined, undefined, commandHistory);
    if (typeof renderCompletedFinalTrust === "function") renderCompletedFinalTrust(undefined, undefined, undefined, undefined, commandHistory);
    if (typeof renderCompletedPilotEvidencePacket === "function") renderCompletedPilotEvidencePacket(undefined, undefined, undefined, undefined, commandHistory);
    if (typeof renderPendingOpenHistory === "function") renderPendingOpenHistory(commandHistory);
    if (typeof renderDiagnosticsOpenHistory === "function") renderDiagnosticsOpenHistory(commandHistory);
    if (typeof renderRenameApplyHistory === "function") renderRenameApplyHistory(commandHistory);
    if (typeof renderPipelineControlHistory === "function") renderPipelineControlHistory(commandHistory);
    if (typeof renderReportOpenHistory === "function") renderReportOpenHistory(commandHistory);
    if (typeof renderNetworkOpenHistory === "function") renderNetworkOpenHistory(commandHistory);
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

  function formatCommandHistoryLines() {
    if (!commandHistory.length) return "No backend command history loaded.";
    return commandHistory
      .map((item) => {
        const owner = commandHistoryOwnerPage(item);
        const issue = commandHistoryIssueLevel(item);
        return `${item.at || ""} ${item.command || "unknown"} [${item.result || ""}; ${owner}; issue=${issue}] ${item.message || ""}`.trim();
      })
      .join("\n");
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
  window.commandHistoryRowKey = commandHistoryRowKey;
  window.selectCommandEntry = selectCommandEntry;
  window.getSelectedCommandEntry = getSelectedCommandEntry;
  window.commandHistoryCommandText = commandHistoryCommandText;
  window.commandHistoryCompactEvidenceLine = commandHistoryCompactEvidenceLine;
  window.commandHistoryOwnerPage = commandHistoryOwnerPage;
  window.commandHistoryIssueLevel = commandHistoryIssueLevel;
  window.commandHistoryRefreshTarget = commandHistoryRefreshTarget;
  window.commandHistorySuggestedAction = commandHistorySuggestedAction;
  window.commandHistoryIssueEntries = commandHistoryIssueEntries;
  window.commandHistoryDiagnosticsActions = commandHistoryDiagnosticsActions;
  window.renderCommandDiagnosticsEvidence = renderCommandDiagnosticsEvidence;
})();
