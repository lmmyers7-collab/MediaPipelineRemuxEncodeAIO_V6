// Network worker table rendering, inspector, and persisted-progress presentation.
(function () {
  "use strict";

  function createNetworkWorkersViewModule(deps = {}) {
    const {
      byId = () => null,
      clearRows = () => {},
      filteredNetworkWorkerRows = (rows) => Array.isArray(rows) ? rows : [],
      getSelectedNetworkWorkerRow = () => null,
      makeRowSelectable = () => {},
      networkAppendCell = () => {},
      networkStatusTone = () => "",
      networkWorkerDetailLines = () => [],
      networkWorkerDriftPayload = () => ({}),
      networkWorkerDriftStatusText = () => "",
      networkWorkerFilterSummary = () => {},
      networkWorkerRowKey = () => "",
      networkWorkerStatusState = () => "unknown",
      renderNetworkWorkerFilterSummary = () => {},
      renderProgressBarsInto = null,
      setText = () => {},
      state = {},
      syncNetworkWorkerViewPresetButtons = () => {},
      updateTableStatusLegend = () => {},
      workerDisplayValue = (value, fallback = "-") => value ?? fallback,
      workerLastResultText = () => "-",
      workerPendingDoneReportText = () => "-",
      workerThroughputText = () => "-",
    } = deps;
    const documentRef = deps.documentRef || document;

  function appendNetworkInspectorRow(target, label, value, status = "") {
    const row = documentRef.createElement("div");
    row.className = "network-inspector-row";
    if (status) row.dataset.status = networkStatusTone(status);
    const labelNode = documentRef.createElement("span");
    labelNode.textContent = label;
    const valueNode = documentRef.createElement("strong");
    valueNode.textContent = workerDisplayValue(value);
    row.append(labelNode, valueNode);
    target.appendChild(row);
  }

  function renderNetworkWorkerDetail(item) {
    const target = byId("network-worker-detail");
    if (!target) return;
    target.replaceChildren();
    if (!item || typeof item !== "object") {
      const message = documentRef.createElement("p");
      message.className = "note";
      message.textContent = networkWorkerDetailLines(item).join(" ");
      target.appendChild(message);
      return;
    }
    const networkWorkers = state.lifecyclePayload.networkWorkers || {};
    const drift = networkWorkerDriftPayload(networkWorkers);
    const warnings = Array.isArray(networkWorkers.warnings) ? networkWorkers.warnings : [];
    appendNetworkInspectorRow(target, "Worker", item.worker_name || item.worker_id || "-");
    appendNetworkInspectorRow(target, "State", item.status || "-", networkWorkerStatusState(item));
    appendNetworkInspectorRow(target, "Current job", item.job_id || "-");
    appendNetworkInspectorRow(target, "Current file", item.current_file_name || item.current_file || item.source_file || "-");
    appendNetworkInspectorRow(target, "Stage", item.current_stage || "-");
    appendNetworkInspectorRow(target, "Progress", workerProgressText(item));
    appendNetworkInspectorRow(target, "Heartbeat", workerHeartbeatText(item));
    appendNetworkInspectorRow(target, "Pending done report", workerPendingDoneReportText(item));
    appendNetworkInspectorRow(target, "Last result", workerLastResultText(item), networkWorkerStatusState(item));
    appendNetworkInspectorRow(target, "Last failure reason", item.last_failure_reason || item.failure_streak_reason_code || "-");
    appendNetworkInspectorRow(target, "Drift", networkWorkerDriftStatusText(drift), drift.status || "unknown");
    appendNetworkInspectorRow(target, "Warnings", warnings.length ? `${warnings.length} warning(s)` : "0");
    appendNetworkInspectorRow(target, "Evidence links", "Cluster Log, ActiveJobs, Run Logs, State Files");
    const note = documentRef.createElement("p");
    note.className = "note";
    note.textContent = "Inspector facts are read-only persisted state. Lifecycle controls remain backend-owned.";
    target.appendChild(note);
  }

  function selectNetworkWorkerRow(item) {
    state.selectedWorkerKey = networkWorkerRowKey(item);
    renderNetworkWorkerDetail(item);
    renderNetworkWorkerRows(state.workersPayload);
  }

  function workerHeartbeatText(row) {
    const age = row?.heartbeat_age_seconds;
    if (age === null || age === undefined || age === "") return row?.last_heartbeat ? "unknown age" : "-";
    const numeric = Number(age);
    if (!Number.isFinite(numeric)) return "unknown age";
    if (numeric < 60) return `${Math.max(0, Math.round(numeric))}s ago`;
    if (numeric < 3600) return `${Math.round(numeric / 60)}m ago`;
    return `${Math.round(numeric / 3600)}h ago`;
  }

  function workerProgressText(row) {
    const value = Number(row?.progress_percent || 0);
    return Number.isFinite(value) && value > 0 ? `${Math.round(value)}%` : "-";
  }

  function networkWorkerProgressStatus(progress) {
    const status = String(progress?.status || "").trim();
    if (!status) return "Not loaded";
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function networkWorkerProgressSummaryLines(progress) {
    const payload = progress && typeof progress === "object" ? progress : {};
    const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
      ? payload.summary_lines.map((line) => String(line || "")
        .replace(/^Worker progress:/, "Last reported worker progress:")
        .replace(
          /^Mutation guardrail: Network progress is read-only persisted runtime evidence;/,
          "Mutation guardrail: Last reported network progress is read-only persisted runtime evidence;"
        ))
      : [
        `Last reported worker progress: ${payload.status || "not loaded"}`,
        `Progress bars: ${payload.bar_count || 0}`,
        `Active worker bars: ${payload.active_count || 0}`,
      ];
    lines.push(
      "",
      "Safe interpretation:",
      "- Active bars reflect last reported persisted coordinator/worker runtime state, not a lifecycle command surface.",
      "- Stale or blocked bars should be cross-checked with Cluster Log, Run Logs, and Last Stderr before retries; ActiveJobs is passive launch diagnostics only.",
      "Mutation guardrail: this panel uses backend-owned Network lifecycle routes only; it does not reclaim jobs, release claims, send done reports, mutate queue state, or touch media files."
    );
    return lines;
  }

  function renderNetworkWorkerProgress(networkWorkers) {
    const progress = networkWorkers?.worker_progress && typeof networkWorkers.worker_progress === "object"
      ? networkWorkers.worker_progress
      : { progress_bars: Array.isArray(networkWorkers?.progress_bars) ? networkWorkers.progress_bars : [] };
    const bars = Array.isArray(progress.progress_bars) ? progress.progress_bars : [];
    setText("network-worker-progress-status", networkWorkerProgressStatus(progress));
    if (typeof renderProgressBarsInto === "function") {
      renderProgressBarsInto("network-worker-progress-bars", bars, progress, "No last reported worker progress loaded.");
    } else {
      setText("network-worker-progress-bars", bars.length ? bars.map((bar) => `${bar.label || bar.id || "Worker"}: ${bar.status || "unknown"} ${bar.percent ?? ""}%`).join("\n") : "No last reported worker progress loaded.");
    }
    setText("network-worker-progress-summary", networkWorkerProgressSummaryLines(progress).join("\n"));
  }

  function renderNetworkWorkerRows(networkWorkers) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    state.workersPayload = payload;
    const rows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows : [];
    state.workerRows = rows;
    const visibleRows = filteredNetworkWorkerRows(rows);
    const tbody = byId("network-worker-rows");
    if (!tbody) return;
    syncNetworkWorkerViewPresetButtons();
    renderNetworkWorkerFilterSummary(rows, visibleRows);
    if (!rows.length) {
      state.selectedWorkerKey = "";
      clearRows(tbody, 9, "No persisted worker rows. Inspect cluster.log, ActiveJobs, or state files before inferring worker lifecycle health.");
      updateTableStatusLegend("network-worker-table-legend", tbody, "Network worker rows");
      renderNetworkWorkerDetail(null);
      return;
    }
    setText(
      "network-worker-status",
      visibleRows.length === rows.length
        ? `${rows.length} worker row${rows.length === 1 ? "" : "s"}`
        : `${visibleRows.length}/${rows.length} worker rows`
    );
    const selectedVisible = visibleRows.some((item) => networkWorkerRowKey(item) === state.selectedWorkerKey);
    if (!selectedVisible) {
      state.selectedWorkerKey = visibleRows.length ? networkWorkerRowKey(visibleRows[0]) : "";
    }
    if (!visibleRows.length) {
      clearRows(tbody, 9, "No persisted worker rows match the current Network worker filters.");
      updateTableStatusLegend("network-worker-table-legend", tbody, "Network worker rows");
      renderNetworkWorkerDetail(null);
      return;
    }
    tbody.replaceChildren();
    visibleRows.forEach((item) => {
      const row = documentRef.createElement("tr");
      const key = networkWorkerRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = networkWorkerStatusState(item);
      row.title = item.worker_id || item.current_file || "";
      networkAppendCell(row, item.worker_name || item.worker_id || "");
      networkAppendCell(row, item.status || "");
      networkAppendCell(row, item.current_file_name || item.current_file || "");
      networkAppendCell(row, item.current_stage || "");
      networkAppendCell(row, workerProgressText(item), "num");
      networkAppendCell(row, workerHeartbeatText(item), "num");
      networkAppendCell(row, workerLastResultText(item));
      networkAppendCell(row, workerThroughputText(item), "num");
      const inspectButton = documentRef.createElement("button");
      inspectButton.type = "button";
      inspectButton.className = "secondary-button network-inspect-button";
      inspectButton.textContent = "Inspect";
      inspectButton.addEventListener("click", (event) => {
        event.stopPropagation();
        selectNetworkWorkerRow(item);
      });
      networkAppendCell(row, inspectButton);
      makeRowSelectable(row, () => selectNetworkWorkerRow(item), {
        selected: Boolean(key && key === state.selectedWorkerKey),
        label: `Network worker row ${item.worker_name || item.worker_id || item.current_file_name || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("network-worker-table-legend", tbody, "Network worker rows");
    renderNetworkWorkerDetail(getSelectedNetworkWorkerRow());
  }
    return {
      appendNetworkInspectorRow,
      renderNetworkWorkerDetail,
      selectNetworkWorkerRow,
      workerHeartbeatText,
      workerProgressText,
      networkWorkerProgressStatus,
      networkWorkerProgressSummaryLines,
      renderNetworkWorkerProgress,
      renderNetworkWorkerRows,
    };
  }

  window.__networkWorkersViewModule = { createNetworkWorkersViewModule };
})();
