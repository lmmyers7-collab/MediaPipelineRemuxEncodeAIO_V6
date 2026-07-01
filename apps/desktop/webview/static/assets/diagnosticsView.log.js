(function () {
  function createDiagnosticsLogModule(deps) {
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
    const diagnosticsArtifactsForLine = deps.diagnosticsArtifactsForLine || function () { return []; };
    const diagnosticsSeverityForLine = deps.diagnosticsSeverityForLine || function () { return "info"; };
    const diagnosticsSourceLines = deps.diagnosticsSourceLines || function () { return []; };
    const readLastDiagnosticsLogRows = deps.readLastDiagnosticsLogRows || function () { return []; };
    const writeLastDiagnosticsLogRows = deps.writeLastDiagnosticsLogRows || function () {};

    let selectedDiagnosticsLogKey = "";

  function diagnosticsLineTimestamp(line) {
    const text = String(line || "");
    const iso = text.match(/\b\d{4}-\d{2}-\d{2}[T ][0-9:.+-Z]+\b/);
    if (iso) return iso[0];
    const clock = text.match(/\b\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\b/);
    return clock ? clock[0] : "";
  }

  function diagnosticsLogRows(diagnostics) {
    return diagnosticsSourceLines(diagnostics || {}).map((entry, index) => ({
      index,
      source: entry.source || "",
      severity: diagnosticsSeverityForLine(entry.line),
      timestamp: diagnosticsLineTimestamp(entry.line),
      line: entry.line || "",
    })).slice(-160);
  }

  function diagnosticsLogRowKey(item) {
    return [
      item?.index ?? "",
      item?.source || "",
      item?.severity || "",
      item?.timestamp || "",
      item?.line || "",
    ].join("\u001f").toLowerCase();
  }

  function diagnosticsLogFilterText() {
    return String(byId("diagnostics-log-filter")?.value || "").trim().toLowerCase();
  }

  function diagnosticsLogSeverityFilter() {
    return String(byId("diagnostics-log-severity")?.value || "").trim().toLowerCase();
  }

  function diagnosticsLogSearchText(item) {
    return [
      item?.source || "",
      item?.severity || "",
      item?.timestamp || "",
      item?.line || "",
    ].join(" ").toLowerCase();
  }

  function diagnosticsLogRowActions(item) {
    const artifacts = item ? diagnosticsArtifactsForLine(item.line) : [];
    const seen = new Set();
    const actions = [];
    const addAction = (kind, target, label, hint) => {
      const normalizedTarget = String(target || "").trim();
      if (!normalizedTarget) return;
      const key = `${kind}:${normalizedTarget}`;
      if (seen.has(key)) return;
      seen.add(key);
      actions.push({
        kind,
        target: normalizedTarget,
        label,
        hint: hint || "",
      });
    };
    artifacts.forEach((artifact) => {
      addAction("open", artifact.target, `Open ${artifact.name}`, artifact.hint);
      addAction("tail", artifact.tailTarget, `Read ${artifact.tailName || artifact.name}`, artifact.hint);
    });
    if (!actions.length && item) {
      const severity = String(item.severity || "info").toLowerCase();
      if (severity === "error") {
        addAction("open", "run_logs", "Open Run logs", "Fallback for an error line with no specific artifact match.");
        addAction("tail", "last_stderr_log", "Read Last Stderr", "Fallback for an error line with no specific artifact match.");
        addAction("tail", "latest_failure_report", "Read Latest Failure Report", "Fallback for an error line with no specific artifact match.");
      } else if (severity === "warning") {
        addAction("open", "state", "Open State Folder", "Fallback for a warning line with no specific artifact match.");
        addAction("tail", "last_stderr_log", "Read Last Stderr", "Fallback for a warning line with no specific artifact match.");
      } else if (severity === "active") {
        addAction("open", "active_jobs", "Open ActiveJobs", "Fallback for an active-work line with no specific artifact match.");
        addAction("open", "state", "Open State Folder", "Fallback for an active-work line with no specific artifact match.");
      }
    }
    return actions.slice(0, 6);
  }

  function diagnosticsLogRowNextStep(item) {
    if (!item) return "Select a diagnostics row to see the likely owning artifact and allowlisted next action.";
    const severity = String(item.severity || "info").toLowerCase();
    const artifacts = diagnosticsArtifactsForLine(item.line);
    const actions = diagnosticsLogRowActions(item);
    if (artifacts.length) {
      const first = artifacts[0];
      const firstAction = actions.length ? ` Use '${actions[0].label}' first.` : "";
      if (severity === "error") {
        return `Start with ${first.name}: ${first.hint}${firstAction}`;
      }
      if (severity === "warning") {
        return `Review ${first.name} if this warning persists after refresh: ${first.hint}${firstAction}`;
      }
      return `Likely owning artifact: ${first.name}. ${first.hint}${firstAction}`;
    }
    if (severity === "error") return "Start with Run Logs and Last Stderr; then check the newest failure report if present.";
    if (severity === "warning") return "Refresh once, then inspect Run Logs or State Folder if the same warning persists.";
    if (severity === "active") return "Compare ActiveJobs and Close Readiness before closing, clearing state, or assuming the UI is stale.";
    return "No specific artifact target was inferred from this line. Use the source label and Diagnostics open buttons if it conflicts with UI state.";
  }

  function diagnosticsLogRealMediaTraceLines(item) {
    if (!item) return [];
    const artifacts = diagnosticsArtifactsForLine(item.line);
    return [
      "Real-media sample trace: Diagnostics log",
      `Trace key: source=${item.source || "not reported"}; severity=${item.severity || "unknown"}; time=${item.timestamp || "not reported"}`,
      `Artifact proof: ${artifacts.length ? artifacts.map((artifact) => artifact.name).join(", ") : "none inferred from line text"}`,
      "What this proves: a bounded diagnostics payload contains this log/state clue.",
      "What remains unproven: a single log line is not completion, output, sidecar, size, subtitle/audio, or publish proof.",
      "Next evidence stop: compare this line with Queue route fields, Completed output proof, Pending Publish drain state, and Last Stderr/Run Logs for the same source.",
      "Mutation guardrail: this trace is read-only and uses backend diagnostics allowlists only.",
    ];
  }

  function filteredDiagnosticsLogRows(rows = readLastDiagnosticsLogRows()) {
    const query = diagnosticsLogFilterText();
    const severity = diagnosticsLogSeverityFilter();
    return (Array.isArray(rows) ? rows : []).filter((item) => {
      if (severity && String(item?.severity || "").toLowerCase() !== severity) return false;
      return !query || diagnosticsLogSearchText(item).includes(query);
    });
  }

  function getSelectedDiagnosticsLogRow() {
    if (!selectedDiagnosticsLogKey) return null;
    return readLastDiagnosticsLogRows().find((row) => diagnosticsLogRowKey(row) === selectedDiagnosticsLogKey) || null;
  }

  function selectDiagnosticsLogRow(item) {
    selectedDiagnosticsLogKey = diagnosticsLogRowKey(item);
    renderDiagnosticsLogDetail(item || null);
    renderDiagnosticsLogTable();
  }

  function renderDiagnosticsLogDetail(item) {
    renderDiagnosticsLogActions(item || null);
    if (!item) {
      setText("diagnostics-log-detail", "No diagnostics log row selected. Select a row to inspect full source, severity, timestamp, and message text.");
      return;
    }
    const artifacts = diagnosticsArtifactsForLine(item.line);
    const actions = diagnosticsLogRowActions(item);
    setText("diagnostics-log-detail", [
      `Source: ${item.source || ""}`,
      `Severity: ${item.severity || ""}`,
      `Time: ${item.timestamp || ""}`,
      `Line: ${boundedDiagnosticsText(item.line, 2400)}`,
      "",
      `Likely artifact(s): ${artifacts.length ? artifacts.map((artifact) => artifact.name).join(", ") : "none inferred"}`,
      `Next step: ${diagnosticsLogRowNextStep(item)}`,
      "",
      ...diagnosticsLogRealMediaTraceLines(item),
      "",
      ...diagnosticsActionPlanLines("Diagnostics log selected row", actions, "The selected line may be stale, partial, or only one side of the launch/pipeline boundary."),
      "Guardrail: selected-row actions use backend allowlists only; the frontend does not open arbitrary paths.",
    ].join("\n"));
  }

  function diagnosticsLogGuidanceLines(allRows, filteredRows) {
    const rows = Array.isArray(allRows) ? allRows : [];
    const visible = Array.isArray(filteredRows) ? filteredRows : [];
    const counts = rows.reduce((acc, item) => {
      const severity = String(item?.severity || "info").toLowerCase();
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});
    const visibleCounts = visible.reduce((acc, item) => {
      const severity = String(item?.severity || "info").toLowerCase();
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});
    const query = diagnosticsLogFilterText();
    const severity = diagnosticsLogSeverityFilter();
    const lines = [
      "Log triage guidance:",
      `Loaded lines: ${rows.length}; visible after filter: ${visible.length}`,
      `Loaded severity counts: error ${counts.error || 0}; warning ${counts.warning || 0}; active ${counts.active || 0}; info ${counts.info || 0}`,
      `Visible severity counts: error ${visibleCounts.error || 0}; warning ${visibleCounts.warning || 0}; active ${visibleCounts.active || 0}; info ${visibleCounts.info || 0}`,
      `Current filter: severity=${severity || "all"}; search=${query || "(none)"}`,
    ];
    if (!rows.length) {
      lines.push("Next step: refresh diagnostics. If the page is still empty while work is active, check Diagnostics > Overview > Shutdown Readiness and Active Jobs.");
    } else if (visibleCounts.error) {
      lines.push("Next step: select the newest visible error, then use the row action strip to open/read the inferred artifact.");
    } else if (visibleCounts.warning) {
      lines.push("Next step: select the newest warning and compare it with State Artifact Summary before changing queue or publish behavior.");
    } else if (visibleCounts.active) {
      lines.push("Next step: active lines should be cross-checked with ActiveJobs and Close Readiness before exiting.");
    } else if (!visible.length) {
      lines.push("Next step: broaden the filter; no loaded diagnostics line currently matches this view.");
    } else {
      lines.push("Next step: no visible error/warning lines. Use Artifact Drilldown or State Artifact Summary if another page still looks inconsistent.");
    }
    lines.push("Proof boundary: an empty or clean log view means no visible log evidence in this payload; it does not prove a real-media route, subtitle conversion, audio selection, Output Size Check, or publish path is safe.");
    lines.push("Mutation guardrail: log triage is read-only; open/read actions use backend allowlisted targets only.");
    return lines;
  }

  function renderDiagnosticsLogGuidance(filteredRows) {
    setText("diagnostics-log-guidance", diagnosticsLogGuidanceLines(readLastDiagnosticsLogRows(), filteredRows).join("\n"));
  }

  function renderDiagnosticsLogActions(item) {
    const container = byId("diagnostics-log-actions");
    if (!container) return;
    container.replaceChildren();
    const groups = diagnosticsActionGroups(diagnosticsLogRowActions(item));
    appendDiagnosticsActionGroup(container, "Read first", groups.readFirst);
    appendDiagnosticsActionGroup(container, "Open next", groups.openNext);
  }

  function renderDiagnosticsLogTable(rows = null) {
    if (Array.isArray(rows)) {
      writeLastDiagnosticsLogRows(rows);
    }
    if (selectedDiagnosticsLogKey && !readLastDiagnosticsLogRows().some((row) => diagnosticsLogRowKey(row) === selectedDiagnosticsLogKey)) {
      selectedDiagnosticsLogKey = "";
    }
    const filteredRows = filteredDiagnosticsLogRows(readLastDiagnosticsLogRows());
    const selectedVisible = !selectedDiagnosticsLogKey || filteredRows.some((row) => diagnosticsLogRowKey(row) === selectedDiagnosticsLogKey);
    const counts = filteredRows.reduce((acc, item) => {
      const severity = item.severity || "info";
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});
    const statusText = readLastDiagnosticsLogRows().length
      ? `${filteredRows.length} / ${readLastDiagnosticsLogRows().length} line${readLastDiagnosticsLogRows().length === 1 ? "" : "s"}; ${counts.error || 0} error; ${counts.warning || 0} warning`
      : "No lines";
    const statusState = counts.error ? "blocked" : counts.warning ? "warning" : readLastDiagnosticsLogRows().length ? "ready" : "empty";
    if (typeof setPanelStatus === "function") {
      setPanelStatus("diagnostics-log-status", statusText, statusState);
    } else {
      setText("diagnostics-log-status", statusText);
    }
    renderDiagnosticsLogGuidance(filteredRows);
    const tbody = byId("diagnostics-log-rows");
    if (!tbody) return;
    if (!filteredRows.length) {
      clearRows(tbody, 4, readLastDiagnosticsLogRows().length ? "No diagnostics log rows match the current filter." : "No diagnostics log rows loaded.");
      updateTableStatusLegend("diagnostics-log-table-legend", tbody, "Diagnostics log rows");
      renderDiagnosticsLogDetail(selectedVisible ? getSelectedDiagnosticsLogRow() : null);
      return;
    }
    tbody.replaceChildren();
    filteredRows.slice().reverse().forEach((item) => {
      const row = document.createElement("tr");
      const severity = String(item.severity || "info").toLowerCase();
      row.dataset.status = severity === "error" ? "blocked" : severity === "warning" || severity === "active" ? "warning" : "";
      const key = diagnosticsLogRowKey(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item.source || "",
        item.severity || "",
        item.timestamp || "",
        boundedDiagnosticsText(item.line, 220),
      ]);
      makeRowSelectable(row, () => selectDiagnosticsLogRow(item), {
        selected: Boolean(key && key === selectedDiagnosticsLogKey),
        label: `Diagnostics log row ${item.severity || "info"} ${item.timestamp || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-log-table-legend", tbody, "Diagnostics log rows");
    renderDiagnosticsLogDetail(selectedVisible ? getSelectedDiagnosticsLogRow() : null);
  }

  function renderDiagnosticsLogRows(diagnostics) {
    renderDiagnosticsLogTable(diagnosticsLogRows(diagnostics || {}));
    const commandHistoryView = window.mediaPipelineCommandHistory || {};
    if (typeof commandHistoryView.renderCommandDiagnosticsEvidence === "function") {
      const selectedCommand = typeof commandHistoryView.getSelectedCommandEntry === "function"
        ? commandHistoryView.getSelectedCommandEntry()
        : null;
      commandHistoryView.renderCommandDiagnosticsEvidence(selectedCommand);
    }
  }

  function getLastDiagnosticsLogRows() {
    return readLastDiagnosticsLogRows().slice();
  }


    return {
      diagnosticsLineTimestamp,
      diagnosticsLogRows,
      diagnosticsLogRowKey,
      diagnosticsLogFilterText,
      diagnosticsLogSeverityFilter,
      diagnosticsLogSearchText,
      diagnosticsLogRowActions,
      diagnosticsLogRowNextStep,
      diagnosticsLogRealMediaTraceLines,
      filteredDiagnosticsLogRows,
      getSelectedDiagnosticsLogRow,
      selectDiagnosticsLogRow,
      renderDiagnosticsLogDetail,
      diagnosticsLogGuidanceLines,
      renderDiagnosticsLogGuidance,
      renderDiagnosticsLogActions,
      renderDiagnosticsLogTable,
      renderDiagnosticsLogRows,
      getLastDiagnosticsLogRows,
    };
  }

  window.__diagnosticsLogModule = {
    createDiagnosticsLogModule,
  };
})();
