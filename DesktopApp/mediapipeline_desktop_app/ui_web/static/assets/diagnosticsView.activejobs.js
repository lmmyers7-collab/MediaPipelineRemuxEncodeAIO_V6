(function () {
  function createDiagnosticsActiveJobsModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const makeRowSelectable = deps.makeRowSelectable || function () {};
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const boundedDiagnosticsText = deps.boundedDiagnosticsText || function (value) { return String(value || ""); };
    const diagnosticsActionGroups = deps.diagnosticsActionGroups || function () { return { readFirst: [], openNext: [] }; };
    const diagnosticsActionPlanLines = deps.diagnosticsActionPlanLines || function () { return []; };
    const appendDiagnosticsActionGroup = deps.appendDiagnosticsActionGroup || function () {};

    let lastActiveJobRows = [];
    let selectedActiveJobKey = "";

  function activeJobRowKey(item) {
    return [
      item?.record_path || "",
      item?.launch_id || "",
      item?.job_kind || "",
      item?.mode || "",
      item?.status || "",
      item?.launched_at || "",
    ].join("\u001f").toLowerCase();
  }

  function getSelectedActiveJobRow() {
    if (!selectedActiveJobKey) return null;
    return lastActiveJobRows.find((row) => activeJobRowKey(row) === selectedActiveJobKey) || null;
  }

  function selectActiveJobRow(item) {
    selectedActiveJobKey = activeJobRowKey(item);
    renderActiveJobDetail(item || null);
    renderActiveJobRows(lastActiveJobRows);
  }

  function activeJobDiagnosticsActions(item) {
    const actions = [];
    const seen = new Set();
    const addAction = (kind, target, label, hint) => {
      const normalizedTarget = String(target || "").trim();
      if (!normalizedTarget) return;
      const key = `${kind}:${normalizedTarget}`;
      if (seen.has(key)) return;
      seen.add(key);
      actions.push({ kind, target: normalizedTarget, label, hint: hint || "" });
    };
    if (!item) return actions;
    const statusText = [item.status, item.issue, item.record_file, item.source].map((value) => String(value || "")).join(" ").toLowerCase();
    addAction("open", "active_jobs", "Open ActiveJobs", "Inspect the backend ActiveJobs records before deciding a process is stale or orphaned.");
    if (item.stderr_log || /\b(error|failed|failure|killed|orphan|invalid|unreadable|locked|timeout|blocked)\b/.test(statusText)) {
      addAction("tail", "last_stderr_log", "Read Last Stderr", "Fastest bounded evidence for the most recent launcher, PowerShell, FFmpeg, copy, or validation failure.");
    }
    if (item.stdout_log || item.stderr_log || item.command_line || item.issue) {
      addAction("open", "run_logs", "Open Run Logs", "Open the run-log folder only after reading bounded text or when more launch context is required.");
    }
    if (/\b(orphan|invalid|unreadable|stale|blocked|pid|runtime)\b/.test(statusText)) {
      addAction("open", "state", "Open State Folder", "Compare runtime state only after ActiveJobs and Close Readiness disagree or report a stale process.");
    }
    return actions.slice(0, 5);
  }

  function activeJobRowPosture(item) {
    const status = String(item?.status || "").toLowerCase();
    const issue = String(item?.issue || "").toLowerCase();
    const source = String(item?.source || "").toLowerCase();
    const combined = `${status} ${issue} ${source}`;
    if (/\b(invalid|unreadable|failed|killed|orphan|blocked|malformed|corrupt)\b/.test(combined)) return "blocked";
    if (/\b(launching|active|running|stale|unknown|review)\b/.test(combined)) return "warning";
    if (/\b(completed|completed_immediate)\b/.test(status)) return "match";
    return "";
  }

  function activeJobRowsStatusText(rows = []) {
    const items = Array.isArray(rows) ? rows : [];
    if (!items.length) return "No rows";
    const counts = items.reduce((acc, item) => {
      const posture = activeJobRowPosture(item);
      if (posture === "blocked") acc.blocked += 1;
      else if (posture === "warning") acc.review += 1;
      else if (posture === "match") acc.completed += 1;
      else acc.unknown += 1;
      return acc;
    }, { blocked: 0, review: 0, completed: 0, unknown: 0 });
    return `${items.length} row${items.length === 1 ? "" : "s"}; blocked=${counts.blocked}; active/review=${counts.review}; completed=${counts.completed}; unknown=${counts.unknown}.`;
  }

  function renderActiveJobDiagnosticsActions(item) {
    const container = byId("active-job-diagnostics-actions");
    if (!container) return;
    container.replaceChildren();
    const groups = diagnosticsActionGroups(activeJobDiagnosticsActions(item));
    appendDiagnosticsActionGroup(container, "Read first", groups.readFirst);
    appendDiagnosticsActionGroup(container, "Open next", groups.openNext);
  }

  function diagnosticsActiveJobRealMediaTraceLines(item) {
    if (!item) return [];
    const active = ["launching", "active", "running"].some((value) => String(item.status || "").toLowerCase().includes(value));
    return [
      "Real-media sample trace: ActiveJobs",
      `Trace key: launch=${item.launch_id || "not reported"}; job=${item.job_kind || "not reported"}; pid=${item.pid ?? "not reported"}`,
      `Process proof: status=${item.status || "unknown"}; return=${item.return_code ?? "not reported"}; stdout=${item.stdout_log || "not reported"}; stderr=${item.stderr_log || "not reported"}`,
      "What this proves: the desktop/backend launch record can explain whether a process exists, finished, failed, or became orphaned.",
      "What remains unproven: output correctness, subtitle/audio result, sidecar consistency, size policy, and pending-publish completion.",
      active
        ? "Next evidence stop: while active, compare Close Readiness, Progress, Last Stderr, and Run Logs before closing or starting more work."
        : "Next evidence stop: after completion, compare the same source with Completed and Pending Publish before accepting the run.",
      "Mutation guardrail: this trace is read-only and cannot kill, relaunch, clear state, or mutate files.",
    ];
  }

  function renderActiveJobDetail(item) {
    renderActiveJobDiagnosticsActions(item || null);
    if (!item) {
      setText("active-job-detail", "No ActiveJob row selected. Select a row to inspect launch id, process ids, logs, working directory, command line, and contract issue.");
      return;
    }
    const actions = activeJobDiagnosticsActions(item);
    const lines = [
      `Record: ${item.record_file || ""}`,
      `Path: ${item.record_path || ""}`,
      `Source: ${item.source || ""}`,
      `Launch ID: ${item.launch_id || ""}`,
      `Job: ${item.job_kind || ""}`,
      `Mode: ${item.mode || ""}`,
      `Status: ${item.status || ""}`,
      `PID: ${item.pid ?? ""}`,
      `App PID: ${item.app_pid ?? ""}`,
      `Return code: ${item.return_code ?? ""}`,
      `Launched: ${item.launched_at || ""}`,
      `Last update: ${item.last_update || ""}`,
      `Completed: ${item.completed_at || ""}`,
      `Stdout: ${item.stdout_log || ""}`,
      `Stderr: ${item.stderr_log || ""}`,
      `CWD: ${item.cwd || ""}`,
      `Show console: ${item.show_console ? "yes" : "no"}`,
      `Args count: ${item.args_count ?? ""}`,
      `Issue: ${item.issue || ""}`,
      `Command: ${boundedDiagnosticsText(item.command_line, 1000)}`,
      "",
      ...diagnosticsActiveJobRealMediaTraceLines(item),
      "",
      ...diagnosticsActionPlanLines(
        "ActiveJobs selected row",
        actions,
        "ActiveJobs is process-lifecycle evidence. Compare it with Close Readiness before closing the app, clearing state, or rerunning media."
      ),
    ];
    setText("active-job-detail", lines.join("\n"));
  }

  function renderActiveJobRows(rows = []) {
    lastActiveJobRows = Array.isArray(rows) ? rows : [];
    if (selectedActiveJobKey && !lastActiveJobRows.some((row) => activeJobRowKey(row) === selectedActiveJobKey)) {
      selectedActiveJobKey = "";
    }
    setText("active-job-detail-status", activeJobRowsStatusText(lastActiveJobRows));
    const tbody = byId("active-job-detail-rows");
    if (!tbody) return;
    if (!lastActiveJobRows.length) {
      clearRows(tbody, 7, "No structured ActiveJobs rows loaded. Use the summary text above or open the ActiveJobs folder if close-readiness is blocked.");
      updateTableStatusLegend("active-job-table-legend", tbody, "ActiveJob rows");
      renderActiveJobDetail(null);
      return;
    }
    tbody.replaceChildren();
    lastActiveJobRows.slice(0, 50).forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = activeJobRowPosture(item);
      const key = activeJobRowKey(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item.record_file || "",
        item.job_kind || "",
        item.mode || "",
        item.status || "",
        item.pid ?? "",
        item.launched_at || "",
        item.issue || "",
      ]);
      makeRowSelectable(row, () => selectActiveJobRow(item), {
        selected: Boolean(key && key === selectedActiveJobKey),
        label: `ActiveJob row ${item.record_file || item.job_kind || item.launch_id || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("active-job-table-legend", tbody, "ActiveJob rows");
    renderActiveJobDetail(getSelectedActiveJobRow());
  }


    return {
      activeJobRowKey,
      getSelectedActiveJobRow,
      selectActiveJobRow,
      activeJobDiagnosticsActions,
      activeJobRowPosture,
      activeJobRowsStatusText,
      renderActiveJobDiagnosticsActions,
      diagnosticsActiveJobRealMediaTraceLines,
      renderActiveJobDetail,
      renderActiveJobRows,
    };
  }

  window.__diagnosticsActiveJobsModule = {
    createDiagnosticsActiveJobsModule,
  };
})();
