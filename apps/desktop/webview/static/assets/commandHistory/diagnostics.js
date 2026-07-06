/* eslint-disable complexity, max-lines-per-function -- moved diagnostics helper logic during the command-history split without behavior changes. */
(function () {
  const helpers = window.__commandHistoryFormatters || {};
  const {
    commandHistoryCommandText,
    commandHistoryIssueEntries,
    commandHistoryIssueLevel,
    commandHistoryIsPendingPublishCommand,
    commandHistoryOwnerCounts,
    commandHistoryOwnerPage,
    commandHistoryPendingPublishSuggestedAction,
    commandHistoryRawData,
    commandHistoryRefreshTarget,
    commandHistoryRequestData,
    commandHistorySuggestedAction,
    commandResultList,
    formatCommandCountMap,
  } = helpers;

  function commandHistoryDiagnosticsDrilldownRows(entries = []) {
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


  function commandHistoryDiagnosticsDrilldownStatus(entries = []) {
    const items = Array.isArray(entries) ? entries : [];
    const issueRows = commandHistoryIssueEntries(items);
    if (!items.length) return "No commands";
    if (issueRows.length) return `${issueRows.length} issue command${issueRows.length === 1 ? "" : "s"}`;
    return "No command issues";
  }


  function commandHistoryDiagnosticsDrilldownSummaryLines(entries = []) {
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


  function commandHistoryOwnerImpactRows(entries = []) {
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


  function commandHistoryOwnerImpactStatus(entries = []) {
    const items = Array.isArray(entries) ? entries : [];
    if (!items.length) return "No commands";
    const rows = commandHistoryOwnerImpactRows(items);
    const issueRows = commandHistoryIssueEntries(items);
    if (issueRows.length) return `${rows.length} impacted owner${rows.length === 1 ? "" : "s"}`;
    return "No owner issues";
  }


  function commandHistoryOwnerImpactSummaryLines(entries = []) {
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


  function commandHistoryRowKey(item) {
    return [
      item?.at || "",
      item?.command || "",
      item?.result || "",
      item?.message || "",
      item?.local ? "local" : "journal",
    ].join("\u001f").toLocaleLowerCase();
  }


  function commandHistoryAddDiagnosticsAction(actions, kind, target, label, reason) {
    if (!target || actions.some((item) => item.kind === kind && item.target === target)) return;
    actions.push({ kind, target, label, reason });
  }


  function commandHistoryDiagnosticsTargetAllowed(target) {
    return [
      "active_jobs",
      "audit_reports",
      "cluster_log",
      "completed_manifest",
      "config",
      "config_folder",
      "failed_markers",
      "failed_reports",
      "latest_audit_csv",
      "latest_failure_json",
      "latest_failure_report",
      "latest_priority_csv",
      "last_stderr_log",
      "last_stdout_log",
      "pending_publish",
      "queue_snapshot",
      "run_logs",
      "sample_validation_log",
      "state",
      "workspace",
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
      commandHistoryAddDiagnosticsAction(actions, "open", "pending_publish", "Open Pending Folder", "Compare command result against parked output state.");
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


  window.__commandHistoryDiagnostics = {
    commandHistoryDiagnosticsDrilldownRows,
    commandHistoryDiagnosticsDrilldownStatus,
    commandHistoryDiagnosticsDrilldownSummaryLines,
    commandHistoryOwnerImpactRows,
    commandHistoryOwnerImpactStatus,
    commandHistoryOwnerImpactSummaryLines,
    commandHistoryRowKey,
    commandHistoryAddDiagnosticsAction,
    commandHistoryDiagnosticsTargetAllowed,
    commandHistoryDiagnosticsActions,
  };
})();
