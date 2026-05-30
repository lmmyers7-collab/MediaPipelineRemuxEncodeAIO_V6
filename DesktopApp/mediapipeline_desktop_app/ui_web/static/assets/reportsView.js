(function () {
  const commandHistoryView = window.mediaPipelineCommandHistory || {};
  let lastReportSnapshot = {};
  let lastReportSettings = {};
  let lastFailurePreviewPayload = {};
  let lastFailureRows = [];
  let selectedFailureRowKey = "";
  let selectedFailureRowKeys = new Set();
  let lastAuditPreviewPayload = {};
  let lastAuditRows = [];
  let selectedAuditRowKey = "";
  let lastFailureEmptyMessage = "No failure rows available.";
  let lastAuditEmptyMessage = "No audit rows available.";
  const REPORTS_TAB_STORAGE_KEY = "mediapipeline-reports-tab";

  function reportsTabIds() {
    return ["overview", "failures", "audit", "files"];
  }

  function activateReportsTab(tabId) {
    const page = document.querySelector('[data-page-panel="reports"]');
    if (!page) return;
    const selected = reportsTabIds().includes(tabId) ? tabId : "overview";
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-reports-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .reports-tab-panel[data-reports-tab-panel]"));
    buttons.forEach((button) => {
      const active = button.dataset.reportsTab === selected;
      button.setAttribute("aria-selected", String(active));
    });
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.reportsTabPanel === selected);
    });
    try { localStorage.setItem(REPORTS_TAB_STORAGE_KEY, selected); } catch (_) {}
    if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
  }

  function initReportsTabNav() {
    const page = document.querySelector('[data-page-panel="reports"]');
    if (!page) return;
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-reports-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .reports-tab-panel[data-reports-tab-panel]"));
    if (!buttons.length || !panels.length) return;
    buttons.forEach((button) => {
      button.addEventListener("click", () => activateReportsTab(button.dataset.reportsTab || "overview"));
    });
    let stored = "overview";
    try { stored = localStorage.getItem(REPORTS_TAB_STORAGE_KEY) || "overview"; } catch (_) {}
    activateReportsTab(stored);
  }

  function reportLabel(key) {
    const labels = {
      latest_failure_report: "Latest Failure Report",
      latest_failure_json: "Latest Failure JSON",
      latest_audit_csv: "Latest Audit CSV",
      latest_priority_csv: "Latest Priority CSV",
      failed_reports: "Failure Reports",
      failed_markers: "Failure Markers",
      audit_reports: "Audit Reports",
      completed_manifest: "Completed Manifest",
      pending_push: "Pending Publish",
      queue_snapshot: "Queue Snapshot",
      active_jobs: "Active Jobs",
    };
    return labels[key] || key.replaceAll("_", " ");
  }

  function reportOpenTarget(key) {
    const targets = {
      latest_failure_report: "latest_failure_report",
      latest_failure_json: "latest_failure_json",
      latest_audit_csv: "latest_audit_csv",
      latest_priority_csv: "latest_priority_csv",
      failed_reports: "failed_reports",
      failed_markers: "failed_markers",
      audit_reports: "audit_reports",
      completed_manifest: "completed_manifest",
      pending_push: "pending_publish",
      queue_snapshot: "queue_snapshot",
      active_jobs: "active_jobs",
    };
    return targets[key] || "";
  }

  function reportOpenTargetValues() {
    return [
      "latest_failure_report",
      "latest_failure_json",
      "latest_audit_csv",
      "latest_priority_csv",
      "failed_reports",
      "failed_markers",
      "audit_reports",
      "completed_manifest",
      "pending_push",
      "queue_snapshot",
      "active_jobs",
    ].map(reportOpenTarget).filter(Boolean);
  }

  function reportOpenCommandTarget(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object"
      ? raw.request
      : raw.submitted_request && typeof raw.submitted_request === "object"
        ? raw.submitted_request
        : {};
    return String(data.target || request.target || "").toLowerCase();
  }

  function isReportOpenCommand(entry) {
    if (String(entry?.command || "").toLowerCase() !== "diagnostics.open") return false;
    return reportOpenTargetValues().includes(reportOpenCommandTarget(entry));
  }

  function reportOpenHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object"
      ? raw.request
      : raw.submitted_request && typeof raw.submitted_request === "object"
        ? raw.submitted_request
        : {};
    const bits = [];
    if (data.target || request.target) bits.push(`target=${data.target || request.target}`);
    if (data.opened_path) bits.push(`opened=${data.opened_path}`);
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: "diagnostics.open",
        detail: bits.length ? ` (${bits.join("; ")})` : "",
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} diagnostics.open [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
  }

  function renderReportOpenHistory(history = []) {
    if (typeof commandHistoryView.renderCompactCommandHistoryBlock === "function") {
      commandHistoryView.renderCompactCommandHistoryBlock({
        history,
        filter: isReportOpenCommand,
        limit: 6,
        targetId: "report-open-history",
        statusId: "report-open-history-status",
        statusText: (entries) => entries.length ? `${entries.length} recent` : "No opens",
        itemLabel: "report open command",
        emptyHistoryText: "No report open command history loaded. Open a report path or report root to see backend results here after refresh.",
        emptyMatchText: "No report-related open commands found in recent command history.",
        lineFor: reportOpenHistoryLine,
        footer: "Backend diagnostics target allowlists remain the source of truth.",
      });
      return;
    }
    const entries = Array.isArray(history) ? history.filter(isReportOpenCommand).slice(0, 6) : [];
    setText("report-open-history-status", entries.length ? `${entries.length} recent` : "No opens");
    if (!Array.isArray(history) || !history.length) {
      setText("report-open-history", "No report open command history loaded. Open a report path or report root to see backend results here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("report-open-history", "No report-related open commands found in recent command history.");
      return;
    }
    setText("report-open-history", [
      `Last ${entries.length} report open command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(reportOpenHistoryLine),
      "Backend diagnostics target allowlists remain the source of truth.",
    ].join("\n"));
  }

  function renderKeyPathRows(tbodyId, statusId, rows, emptyMessage) {
    const tbody = byId(tbodyId);
    const entries = rows.filter((item) => item.path);
    setText(statusId, entries.length ? `${entries.length} path${entries.length === 1 ? "" : "s"}` : "No paths");
    if (!tbody) return;
    if (!entries.length) {
      clearRows(tbody, 3, emptyMessage);
      return;
    }
    tbody.replaceChildren();
    entries.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [item.label, item.path]);
      const action = document.createElement("td");
      const target = reportOpenTarget(item.key);
      if (target) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.textContent = "Open";
        button.dataset.openDiagnostics = target;
        button.addEventListener("click", () => requestDiagnosticsOpen(target));
        action.appendChild(button);
      }
      row.appendChild(action);
      tbody.appendChild(row);
    });
  }

  function renderReports(snapshot, settings) {
    const snapshotPayload = snapshot || {};
    const settingsPayload = settings || {};
    lastReportSnapshot = snapshotPayload;
    lastReportSettings = settingsPayload;
    const latestPaths = snapshotPayload.latest_paths || {};
    const workspacePaths = settingsPayload.paths || {};
    setText("report-failure-json-state", latestPaths.latest_failure_json ? "Present" : "Missing");
    setText("report-audit-csv-state", latestPaths.latest_audit_csv ? "Present" : "Missing");
    setText("report-priority-csv-state", latestPaths.latest_priority_csv ? "Present" : "Missing");
    if (typeof renderAuditProgressInto === "function") {
      renderAuditProgressInto({
        containerId: "report-progress-bars",
        statusId: "report-progress-status",
        summaryId: "report-progress-summary",
        snapshot: snapshotPayload,
        emptyText: "No audit report progress loaded.",
      });
    }
    const warnings = Array.isArray(snapshotPayload.warnings) ? snapshotPayload.warnings : [];
    setText("report-warning-count", String(warnings.length));
    const latestRows = ["latest_failure_report", "latest_failure_json", "latest_audit_csv", "latest_priority_csv"].map((key) => ({
      key,
      label: reportLabel(key),
      path: latestPaths[key] || "",
    }));
    renderKeyPathRows("report-path-rows", "report-path-status", latestRows, "No latest reports loaded.");
    const rootRows = ["failed_reports", "failed_markers", "audit_reports", "completed_manifest", "pending_push", "queue_snapshot", "active_jobs"].map((key) => ({
      key,
      label: reportLabel(key),
      path: workspacePaths[key] || "",
    }));
    renderKeyPathRows("report-root-rows", "report-root-status", rootRows, "No report roots loaded.");
    setText("report-warnings", warnings.join("\n") || "No snapshot warnings.");
    renderReportTriage();
    if (typeof getCommandHistory === "function") renderReportOpenHistory(getCommandHistory());
  }

  function renderFailurePreview(failures) {
    lastFailurePreviewPayload = failures || {};
    const rows = Array.isArray(failures.rows) ? failures.rows : [];
    lastFailureRows = rows;
    if (selectedFailureRowKey && !rows.some((row) => failureRowKey(row) === selectedFailureRowKey)) {
      selectedFailureRowKey = "";
    }
    const availableKeys = new Set(rows.map((row) => failureRowKey(row)).filter(Boolean));
    selectedFailureRowKeys = new Set(Array.from(selectedFailureRowKeys).filter((key) => availableKeys.has(key)));
    lastFailureEmptyMessage = failureEmptyStateMessage(failures, rows);
    const summary = [
      failures.source ? `Source: ${failures.source}` : "",
      `Source type: ${failures.source_kind || "latest_json"}`,
      `Rows: ${failures.count || rows.length || 0}`,
      `Operator required: ${failures.operator_required_count || 0}`,
      `Permanent: ${failures.permanent_count || 0}`,
      `Transient: ${failures.transient_count || 0}`,
      failureRetryPreviewSummaryLine(failures),
      ...(failures.warnings || []),
      !rows.length ? failureEmptyStateMessage(failures, rows) : "",
    ].filter(Boolean);
    setText("failure-summary", summary.join("\n") || "No failure preview loaded.");
    renderFailureDetail(getSelectedFailureRow());
    renderFailureRows();
    renderReportTriage();
  }

  function failureEmptyStateMessage(failures, rows) {
    if (failures.error) {
      return `Failure preview unavailable: ${failures.error}. Open Diagnostics > Failure Reports or Failure Markers.`;
    }
    const warnings = Array.isArray(failures.warnings) ? failures.warnings.filter(Boolean) : [];
    if (warnings.length) {
      return `Failure preview loaded with warning: ${warnings.join(" | ")}`;
    }
    if (!rows.length) {
      return "No failure rows found for the selected source. If a job failed recently, check marker source mode and Run Logs.";
    }
    return "No failure rows available.";
  }

  function failureRowKey(item) {
    return [
      item?.source_json || "",
      item?.source_path || "",
      item?.stage || "",
      item?.error_code || "",
      item?.recorded_at || "",
    ].join("\u001f").toLocaleLowerCase();
  }

  function failureDisplayValue(value, fallback) {
    const text = String(value || "").trim();
    return text || fallback;
  }

  function failureClassificationText(item) {
    return failureDisplayValue(item?.classification || item?.class, "review");
  }

  function failureStageText(item) {
    return failureDisplayValue(item?.stage || item?.failure_stage || item?.error_stage, "review");
  }

  function failureReasonText(item) {
    return failureDisplayValue(item?.reason || item?.message || item?.error_message || item?.error, "Review failure evidence.");
  }

  function failureSuggestedActionText(item) {
    const explicit = failureDisplayValue(item?.suggested_action || item?.recommended_action || item?.next_step, "");
    if (explicit) return explicit;
    const classification = String(item?.classification || "").toLowerCase();
    if (classification === "transient") return "Preview marker clear, then rerun after confirming logs.";
    if (classification === "operator_required" || classification === "permanent") return "Open diagnostics and review the source before retry.";
    return "Review diagnostics before retry.";
  }

  function failureRetryStatePayload(failures = lastFailurePreviewPayload) {
    const payload = failures && typeof failures === "object" ? failures.retry_state : null;
    if (payload && typeof payload === "object" && payload.schema_version === "desktop_retry_state.v1") {
      return payload;
    }
    const rows = Array.isArray(failures?.rows) ? failures.rows : lastFailureRows;
    const retryRows = (Array.isArray(rows) ? rows : []).map((row) => failureRetryStateFromRow(row));
    const retryable = retryRows.filter((row) => row.retry_allowed).length;
    const blocked = retryRows.filter((row) => row.status_state === "blocked").length;
    return {
      schema_version: "desktop_retry_state.v1",
      read_only: true,
      status_state: retryable ? "retrying" : blocked ? "blocked" : retryRows.length ? "warning" : "idle",
      row_count: retryRows.length,
      retryable_count: retryable,
      blocked_count: blocked,
      warning_count: retryRows.filter((row) => row.status_state === "warning").length,
      unavailable_count: retryRows.filter((row) => row.unavailable_reason).length,
      rows: retryRows,
      operator_guidance: "Retry state was derived from loaded failure rows because the backend retry_state payload was absent.",
    };
  }

  function failureRetryRows(failures = lastFailurePreviewPayload) {
    const retry = failureRetryStatePayload(failures);
    return Array.isArray(retry.rows) ? retry.rows : [];
  }

  function failureRetryStateFromRow(item) {
    const classification = String(item?.classification || item?.class || "").toLowerCase();
    const attempt = Number(item?.retry_count || item?.RetryCount || 0) || 0;
    const maxAttempts = Number(item?.retry_limit || item?.RetryLimit || 0) || 0;
    const exhausted = maxAttempts > 0 && attempt >= maxAttempts;
    const retryable = item?.retryable === false || String(item?.retryable || "").toLowerCase() === "false" ? false : classification === "transient";
    const retryAllowed = Boolean(classification === "transient" && retryable && !exhausted);
    const status = retryAllowed ? (maxAttempts > 0 ? "retrying" : "warning") : (classification === "operator_required" || classification === "permanent" || exhausted || retryable === false) ? "blocked" : "warning";
    return {
      schema_version: "desktop_retry_state.v1",
      job_id: item?.job_id || item?.JobId || "",
      source_path: item?.source_path || "",
      source_json: item?.source_json || "",
      stage: item?.stage || "",
      error_code: item?.error_code || "",
      classification,
      attempt,
      max_attempts: maxAttempts,
      last_failure_reason: failureReasonText(item),
      retry_allowed: retryAllowed,
      retry_route_or_command: retryAllowed ? "automatic_next_queue_pass" : "none_exposed",
      safe_next_action: item?.retry_safe_next_action || failureSuggestedActionText(item),
      status_state: item?.retry_status_state || status,
      unavailable_reason: retryAllowed && maxAttempts === 0 ? "Retry limit was not reported." : "",
      read_only: true,
    };
  }

  function failureRetryStateForRow(item) {
    if (!item) return null;
    const itemKey = failureRowKey(item);
    const rows = failureRetryRows();
    const matched = rows.find((row) => {
      const candidate = {
        source_json: row.source_json || item.source_json || "",
        source_path: row.source_path || "",
        stage: row.stage || "",
        error_code: row.error_code || "",
        recorded_at: item.recorded_at || "",
      };
      return failureRowKey(candidate) === itemKey
        || (
          (!row.source_json || row.source_json === item.source_json)
          && (!row.source_path || row.source_path === item.source_path)
          && (!row.stage || row.stage === item.stage)
          && (!row.error_code || row.error_code === item.error_code)
        );
    });
    return matched || failureRetryStateFromRow(item);
  }

  function failureRetryPreviewSummaryLine(failures = lastFailurePreviewPayload) {
    const retry = failureRetryStatePayload(failures);
    if (!retry || retry.status_state === "idle") return "Retry state: no failure rows.";
    return `Retry state: ${retry.status_state || "unknown"}; retryable=${retry.retryable_count || 0}; blocked=${retry.blocked_count || 0}; warning=${retry.warning_count || 0}.`;
  }

  function failureRetrySummaryText(item) {
    const retry = failureRetryStateForRow(item);
    if (!retry) return "No retry evidence";
    const attempt = Number(retry.attempt || 0);
    const maxAttempts = Number(retry.max_attempts || 0);
    const attemptText = maxAttempts > 0 ? `${attempt}/${maxAttempts}` : attempt > 0 ? `${attempt}/limit unknown` : "limit unknown";
    if (retry.retry_allowed) return `Auto retry (${attemptText})`;
    if (retry.status_state === "blocked") return `Blocked (${attemptText})`;
    return retry.unavailable_reason ? `Review (${retry.unavailable_reason})` : `Review (${attemptText})`;
  }

  function failureRetryDetailLines(item) {
    const retry = failureRetryStateForRow(item);
    if (!retry) {
      return [
        "Retry status: unavailable",
        "Retry evidence: no backend retry_state row matched this failure.",
      ];
    }
    return [
      `Retry status: ${retry.status_state || "unknown"}`,
      `Retry allowed: ${retry.retry_allowed ? "yes" : "no"}`,
      `Retry attempts: ${Number(retry.attempt || 0)}/${Number(retry.max_attempts || 0) || "limit unknown"}`,
      `Retry route/command: ${retry.retry_route_or_command || "none_exposed"}`,
      retry.job_id ? `Job ID: ${retry.job_id}` : "",
      retry.unavailable_reason ? `Retry evidence gap: ${retry.unavailable_reason}` : "",
      `Retry next action: ${retry.safe_next_action || failureSuggestedActionText(item)}`,
    ].filter(Boolean);
  }

  function failureRecordedText(value) {
    const raw = String(value || "").trim();
    if (!raw) return "not recorded";
    const match = raw.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
    if (match) return `${match[1]} ${match[2]}`;
    return raw.length > 22 ? raw.slice(0, 19).replace("T", " ") : raw;
  }

  function getSelectedFailureRow() {
    if (!selectedFailureRowKey) return null;
    return lastFailureRows.find((row) => failureRowKey(row) === selectedFailureRowKey) || null;
  }

  function getSelectedFailureRows() {
    if (!selectedFailureRowKeys.size) {
      const single = getSelectedFailureRow();
      return single ? [single] : [];
    }
    return lastFailureRows.filter((row) => selectedFailureRowKeys.has(failureRowKey(row)));
  }

  function reportAddDiagnosticsAction(actions, kind, target, label, reason) {
    if (!target || actions.some((item) => item.kind === kind && item.target === target)) return;
    actions.push({ kind, target, label, reason });
  }

  function failureDiagnosticsActionsForRow(item) {
    const actions = [];
    reportAddDiagnosticsAction(actions, "tail", "latest_failure_report", "Read Latest Failure", "Read the backend failure report before rerun or cleanup decisions.");
    reportAddDiagnosticsAction(actions, "open", "latest_failure_json", "Open Failure JSON", "Inspect the structured failure payload behind this report row.");
    reportAddDiagnosticsAction(actions, "open", "failed_reports", "Open Failure Reports", "Open the backend-selected failure report folder.");
    reportAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Compare the failure row with pipeline logs before retrying.");
    if (!item) return actions;
    const classification = String(item.classification || "").toLowerCase();
    if (classification === "operator_required" || classification === "permanent") {
      reportAddDiagnosticsAction(actions, "open", "failed_markers", "Open Failure Markers", "Inspect source-level failure markers before rerun.");
    }
    if (String(item.stage || "").toLowerCase().includes("publish")) {
      reportAddDiagnosticsAction(actions, "open", "pending_publish", "Open Pending Publish", "Compare failure state with parked output state.");
    }
    if (String(item.stage || "").toLowerCase().includes("queue")) {
      reportAddDiagnosticsAction(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Compare the failure with the latest queue snapshot.");
    }
    return actions;
  }

  function failureMarkerModeActive() {
    return String(lastFailurePreviewPayload.source_kind || "").toLowerCase() === "markers";
  }

  function visibleFailureRows() {
    const filterText = byId("failure-filter")?.value || "";
    return filterRows(lastFailureRows, filterText, [
      "classification",
      "error_code",
      "stage",
      "media_type",
      "lookup_title",
      "source_path",
      "reason",
      "suggested_action",
    ]);
  }

  function failureMarkerPath(item) {
    return String(item?.source_json || "").trim();
  }

  function selectedFailureMarkerPaths() {
    const seen = new Set();
    const paths = [];
    getSelectedFailureRows().forEach((item) => {
      const markerPath = failureMarkerPath(item);
      const key = markerPath.toLowerCase();
      if (markerPath && !seen.has(key)) {
        seen.add(key);
        paths.push(markerPath);
      }
    });
    return paths;
  }

  function visibleFailureMarkerPaths() {
    const seen = new Set();
    const paths = [];
    visibleFailureRows().forEach((item) => {
      const markerPath = failureMarkerPath(item);
      const key = markerPath.toLowerCase();
      if (markerPath && !seen.has(key)) {
        seen.add(key);
        paths.push(markerPath);
      }
    });
    return paths;
  }

  function allFailureMarkerPaths() {
    const seen = new Set();
    const paths = [];
    lastFailureRows.forEach((item) => {
      const markerPath = failureMarkerPath(item);
      const key = markerPath.toLowerCase();
      if (markerPath && !seen.has(key)) {
        seen.add(key);
        paths.push(markerPath);
      }
    });
    return paths;
  }

  function failureClearRequest(scope, dryRun) {
    if (!failureMarkerModeActive()) {
      return { error: "Switch on Use failure markers first. Latest failure reports are evidence, not retry-blocker state." };
    }
    const markerPaths = scope === "all" ? allFailureMarkerPaths() : scope === "visible" ? visibleFailureMarkerPaths() : selectedFailureMarkerPaths();
    if (!markerPaths.length) {
      return { error: scope === "all" ? "No marker rows are loaded." : scope === "visible" ? "No visible marker rows are loaded." : "Select one or more failure marker rows first." };
    }
    return { scope, marker_paths: markerPaths, dry_run: dryRun, confirm_clear: !dryRun };
  }

  function renderFailureClearResult(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const planned = Array.isArray(data.planned) ? data.planned : [];
    const skipped = Array.isArray(data.skipped) ? data.skipped : [];
    const errors = Array.isArray(result?.errors) ? result.errors : Array.isArray(data.errors) ? data.errors : [];
    const lines = [
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run ? "yes" : "no"}`,
      `Scope: ${data.scope || ""}`,
      `Planned marker clears: ${planned.length}`,
      `Moved markers: ${data.markers || 0}`,
      `Writes active marker folder: ${data.writes_failure_markers ? "yes" : "no"}`,
      `Touches media: ${data.touches_media ? "unexpected yes" : "no"}`,
      data.manifest_path ? `Clear manifest: ${data.manifest_path}` : "",
      data.archive_dir ? `Cleared marker archive: ${data.archive_dir}` : "",
      `Safe next action: ${data.safe_next_action || "Review marker rows before confirming."}`,
      "Guardrail: this command moves marker JSON out of State\\Failures\\Markers only; it does not delete media, reports, completed manifests, pending publish state, or source/output files.",
      "",
      result?.message || "",
    ].filter((line) => line !== "");
    if (errors.length) {
      lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
    }
    if (skipped.length) {
      lines.push("", "Skipped:", ...skipped.slice(0, 8).map((item) => `- ${item.path || ""}: ${item.reason || "skipped"}`));
    }
    if (planned.length) {
      lines.push("", "Planned markers:", ...planned.slice(0, 8).map((item) => `- ${item.path || ""}`));
      if (planned.length > 8) lines.push(`- ... ${planned.length - 8} more`);
    }
    setText("failure-clear-status", result?.ok ? (data.dry_run ? "Preview ready" : "Cleared") : "Blocked");
    setText("failure-clear-summary", lines.join("\n"));
  }

  async function requestFailureMarkerClear(scope, dryRun) {
    const request = failureClearRequest(scope, dryRun);
    if (request.error) {
      setText("failure-clear-status", "Blocked");
      setText("failure-clear-summary", request.error);
      return;
    }
    if (!dryRun) {
      const count = Array.isArray(request.marker_paths) ? request.marker_paths.length : 0;
      const message = `Clear ${count} failure marker${count === 1 ? "" : "s"}?\n\nThis moves marker JSON out of the active marker folder so the pipeline can retry those source files. It does not touch media files or failure reports.`;
      if (!window.confirm(message)) return;
    }
    setText("failure-clear-status", dryRun ? "Previewing..." : "Clearing...");
    setText("failure-clear-summary", dryRun ? "Previewing backend marker clear. No marker files will move." : "Clearing backend marker files after confirmation.");
    try {
      const result = await apiPost("/api/failures/clear", {
        scope,
        marker_paths: request.marker_paths,
        dry_run: dryRun,
        confirm_clear: !dryRun,
      });
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      renderFailureClearResult(result);
      if (!dryRun && result?.ok) {
        selectedFailureRowKey = "";
        selectedFailureRowKeys.clear();
        if (typeof refreshAll === "function") await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "failures.clear",
        ok: false,
        severity: "error",
        message,
        errors: [message],
      };
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      renderFailureClearResult(result);
    }
  }

  function auditDiagnosticsActionsForRow(item) {
    const actions = [];
    reportAddDiagnosticsAction(actions, "tail", "latest_audit_csv", "Read Latest Audit CSV", "Read the bounded latest audit CSV tail.");
    reportAddDiagnosticsAction(actions, "open", "audit_reports", "Open Audit Reports", "Open the backend-selected audit report folder.");
    reportAddDiagnosticsAction(actions, "open", "completed_manifest", "Open Completed Manifest", "Compare audit row state with completed history.");
    reportAddDiagnosticsAction(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Compare audit row state with current queue visibility.");
    if (!item) return actions;
    const bucket = String(item.effective_bucket || "").toUpperCase();
    if (bucket === "REDOWNLOAD_CANDIDATE") {
      reportAddDiagnosticsAction(actions, "open", "failed_reports", "Open Failure Reports", "Check whether prior failures explain the redownload recommendation.");
    }
    if (bucket === "RERUN_PIPELINE") {
      reportAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Compare rerun recommendation with recent runtime evidence.");
    }
    return actions;
  }

  function renderReportDiagnosticsActions(containerId, actions, sourceLabel) {
    const container = byId(containerId);
    if (!container) return;
    container.replaceChildren();
    diagnosticsBridgeActions(actions).forEach((action) => {
      const button = document.createElement("button");
      button.className = "secondary-button";
      button.type = "button";
      button.textContent = diagnosticsBridgeActionLabel(action);
      button.title = action.reason || "";
      button.dataset.reportDiagnosticsAction = action.kind;
      button.dataset.reportDiagnosticsTarget = action.target;
      if (action.kind === "tail") {
        button.addEventListener("click", () => {
          if (typeof requestDiagnosticsTail === "function") requestDiagnosticsTail(action.target);
        });
      } else {
        button.addEventListener("click", () => requestDiagnosticsOpen(action.target));
      }
      container.appendChild(button);
    });
    if (typeof appendDiagnosticsBridgeButton === "function") {
      appendDiagnosticsBridgeButton(container, actions, sourceLabel);
    }
  }

  function selectFailureRow(item) {
    selectedFailureRowKey = failureRowKey(item);
    renderFailureDetail(item || null);
    renderFailureRows();
  }

  function toggleFailureRowSelection(item, checked) {
    const key = failureRowKey(item);
    if (!key) return;
    if (checked) {
      selectedFailureRowKeys.add(key);
      selectedFailureRowKey = key;
    } else {
      selectedFailureRowKeys.delete(key);
      if (selectedFailureRowKey === key) {
        selectedFailureRowKey = Array.from(selectedFailureRowKeys)[0] || "";
      }
    }
    renderFailureDetail(getSelectedFailureRow());
    renderFailureRows();
  }

  function renderFailureDetail(item) {
    if (!item) {
      setText("failure-detail", "No failure row selected. Select a row to inspect classification, error code, stage, suggested action, backend-authored retry state, and repro path.");
      renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForRow(null), "Reports failure page");
      return;
    }
    const handoffLines = typeof diagnosticsBridgeHandoffLines === "function"
      ? diagnosticsBridgeHandoffLines("Reports failure selected row", failureDiagnosticsActionsForRow(item), {
        evidence: [
          item.classification ? `classification=${item.classification}` : "",
          item.error_code ? `code=${item.error_code}` : "",
          item.stage ? `stage=${item.stage}` : "",
          item.source_path ? `source=${item.source_path}` : "",
        ],
        safeAction: "compare Latest Failure, Failure JSON, Failure Markers, Run Logs, and related queue/pending state before rerun.",
      })
      : [];
    const detail = [
      ...handoffLines,
      "",
      `Title: ${item.lookup_title || ""}`,
      `Media: ${item.media_type || ""}`,
      `Class: ${failureClassificationText(item)}`,
      `Code: ${item.error_code || ""}`,
      `Stage: ${failureStageText(item)}`,
      `Reason: ${failureReasonText(item)}`,
      `Suggested action: ${failureSuggestedActionText(item)}`,
      `Suggested rename: ${item.suggested_rename || ""}`,
      `Retry: ${item.retry_count || 0}/${item.retry_limit || 0}`,
      ...failureRetryDetailLines(item),
      `Escalated: ${item.escalated ? "yes" : "no"}`,
      `Recorded: ${failureRecordedText(item.recorded_at)}`,
      `Source: ${item.source_path || ""}`,
      `Artifact: ${item.artifact_path || ""}`,
      `Repro: ${item.repro_path || ""}`,
      `Record file: ${item.source_json || ""}`,
    ];
    setText("failure-detail", detail.join("\n"));
    renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForRow(item), "Reports failure selected row");
  }

  function renderFailureRows() {
    const rows = visibleFailureRows();
    setText("failure-status", `${rows.length} / ${lastFailureRows.length} row${lastFailureRows.length === 1 ? "" : "s"}`);
    const tbody = byId("failure-rows");
    if (!rows.length) {
      clearRows(tbody, 10, lastFailureRows.length ? "No failure rows match the filter." : lastFailureEmptyMessage);
      updateTableStatusLegend("failure-table-legend", tbody, "Failure rows");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 250).forEach((item) => {
      const row = document.createElement("tr");
      const classification = String(failureClassificationText(item)).toLowerCase();
      const retryState = failureRetryStateForRow(item);
      row.dataset.status = retryState?.status_state || (classification === "operator_required" || classification === "permanent" ? "blocked" : classification === "transient" ? "warning" : "");
      const key = failureRowKey(item);
      row.dataset.rowKey = key;
      const selectCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(key && selectedFailureRowKeys.has(key));
      checkbox.setAttribute("aria-label", `Select failure ${item.lookup_title || item.source_path || item.error_code || ""}`);
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => toggleFailureRowSelection(item, checkbox.checked));
      selectCell.appendChild(checkbox);
      row.appendChild(selectCell);
      appendCells(row, [
        failureClassificationText(item),
        item.error_code || "",
        failureStageText(item),
        item.media_type || "",
        item.lookup_title || item.source_path || "",
        failureReasonText(item),
        failureSuggestedActionText(item),
        failureRetrySummaryText(item),
        failureRecordedText(item.recorded_at),
      ]);
      makeRowSelectable(row, () => selectFailureRow(item), {
        selected: Boolean(key && key === selectedFailureRowKey),
        label: `Failure row ${item.lookup_title || item.source_path || item.error_code || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("failure-table-legend", tbody, "Failure rows");
  }

  function renderAuditPreview(audit) {
    lastAuditPreviewPayload = audit || {};
    const rows = Array.isArray(audit.rows) ? audit.rows : [];
    lastAuditRows = rows;
    if (selectedAuditRowKey && !rows.some((row) => auditRowKey(row) === selectedAuditRowKey)) {
      selectedAuditRowKey = "";
    }
    lastAuditEmptyMessage = auditEmptyStateMessage(audit, rows);
    const summary = [
      audit.source ? `Source: ${audit.source}` : "",
      `Priority CSV mode: ${audit.priority_only ? "yes" : "no"}`,
      `Rows: ${audit.count || rows.length || 0}`,
      `High priority: ${audit.high_priority_count || 0}`,
      `Rerun: ${audit.rerun_count || 0}`,
      `Redownload: ${audit.redownload_count || 0}`,
      `Review: ${audit.review_count || 0}`,
      `Duplicate groups: ${audit.duplicate_group_count || 0}`,
      ...(audit.warnings || []),
      !rows.length ? auditEmptyStateMessage(audit, rows) : "",
    ].filter(Boolean);
    setText("audit-preview-summary", summary.join("\n") || "No audit preview loaded.");
    renderAuditDetail(getSelectedAuditRow());
    renderAuditRows();
    renderReportTriage();
  }

  function reportNumber(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : 0;
  }

  function reportPreviewLoaded(payload, rows) {
    const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
    return Boolean(
      payload?.source ||
      payload?.source_kind ||
      payload?.count !== undefined ||
      payload?.error ||
      warnings.length ||
      (Array.isArray(rows) && rows.length)
    );
  }

  function reportCountBy(rows, keys, fallback = "unknown") {
    const keyList = Array.isArray(keys) ? keys : [keys];
    const counts = {};
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      let value = "";
      keyList.some((key) => {
        value = String(row?.[key] || "").trim();
        return Boolean(value);
      });
      const normalized = value || fallback;
      counts[normalized] = (counts[normalized] || 0) + 1;
    });
    return counts;
  }

  function reportFormatCounts(counts, limit = 6) {
    const entries = Object.entries(counts || {})
      .sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0) || String(left[0]).localeCompare(String(right[0])))
      .slice(0, limit);
    return entries.length ? entries.map(([key, value]) => `${key}: ${value}`).join(", ") : "none";
  }

  function failureReviewStatus() {
    const failures = lastFailurePreviewPayload || {};
    if (failures.error) return "Unavailable";
    if (!reportPreviewLoaded(failures, lastFailureRows)) return "Not loaded";
    if (reportNumber(failures.operator_required_count) > 0 || reportNumber(failures.permanent_count) > 0) return "Action needed";
    if (reportNumber(failures.transient_count) > 0) return "Retry review";
    if (lastFailureRows.length) return "Loaded";
    return "No rows";
  }

  function failureReviewBoardLines() {
    const failures = lastFailurePreviewPayload || {};
    const rows = Array.isArray(lastFailureRows) ? lastFailureRows : [];
    const warnings = Array.isArray(failures.warnings) ? failures.warnings.filter(Boolean) : [];
    if (failures.error) {
      return [
        "Failure review board: unavailable.",
        `Error: ${failures.error}`,
        "First action: open Latest Failure, Failure Reports, and Run Logs from Diagnostics before deciding whether a rerun is safe.",
        "Mutation guardrail: Reports remains read-only; rerun and cleanup decisions must use backend-owned workflows.",
      ];
    }
    if (!reportPreviewLoaded(failures, rows)) {
      return [
        "Failure review board: no failure preview has loaded yet.",
        "First action: refresh Reports or open Failure Reports if you expected recent failures.",
        "Mutation guardrail: Reports remains read-only; it does not create, clear, or rerun failure records.",
      ];
    }
    const operatorRows = rows.filter((row) => ["operator_required", "permanent"].includes(String(row.classification || "").toLowerCase()));
    const transientRows = rows.filter((row) => String(row.classification || "").toLowerCase() === "transient");
    const retryState = failureRetryStatePayload(failures);
    const reviewRows = [...operatorRows, ...transientRows, ...rows.filter((row) => !operatorRows.includes(row) && !transientRows.includes(row))];
    const lines = [
      "Failure review board:",
      `Rows: ${reportNumber(failures.count || rows.length)}`,
      `Classification counts: ${reportFormatCounts(reportCountBy(rows, "classification"))}`,
      `Stage counts: ${reportFormatCounts(reportCountBy(rows, "stage"))}`,
      `Error-code counts: ${reportFormatCounts(reportCountBy(rows, "error_code"))}`,
      `Media counts: ${reportFormatCounts(reportCountBy(rows, "media_type"))}`,
      `Operator/permanent rows: ${operatorRows.length}`,
      `Transient retry rows: ${transientRows.length}`,
      `Retry state: ${retryState.status_state || "unknown"}; retryable=${retryState.retryable_count || 0}; blocked=${retryState.blocked_count || 0}; warning=${retryState.warning_count || 0}.`,
    ];
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    if (reviewRows.length) {
      lines.push("", "First rows to inspect:");
      reviewRows.slice(0, 6).forEach((row) => {
        const title = row.lookup_title || row.source_path || row.source_json || "unknown source";
        const classification = row.classification || "unknown";
        const code = row.error_code || "no-code";
        const stage = row.stage || "unknown-stage";
        const action = row.suggested_action || row.reason || "review failure record";
        lines.push(`- ${classification} / ${stage} / ${code}: ${title} -> ${action}`);
      });
    }
    lines.push("");
    if (operatorRows.length) {
      lines.push("Next step: inspect operator/permanent rows before rerun; they may require rename, source replacement, manual subtitle review, or config changes.");
    } else if (transientRows.length) {
      lines.push("Next step: compare transient rows with Run Logs and pending/queue state before retrying.");
    } else if (rows.length) {
      lines.push("Next step: select a row to confirm classification, proof paths, and Diagnostics handoff.");
    } else {
      lines.push("Next step: no failure rows are present; use Audit rows or Diagnostics if you expected a recent failure.");
    }
    lines.push("Mutation guardrail: Reports remains read-only; rerun/export/repair actions must stay backend-owned.");
    return lines;
  }

  function renderFailureReviewBoard() {
    setText("failure-review-status", failureReviewStatus());
    setText("failure-review-board", failureReviewBoardLines().join("\n"));
  }

  function auditReviewStatus() {
    const audit = lastAuditPreviewPayload || {};
    if (audit.error) return "Unavailable";
    if (!reportPreviewLoaded(audit, lastAuditRows)) return "Not loaded";
    if (reportNumber(audit.redownload_count) > 0) return "Redownload review";
    if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) return "Rerun review";
    if (reportNumber(audit.review_count) > 0 || reportNumber(audit.duplicate_group_count) > 0) return "Review";
    if (lastAuditRows.length) return "Loaded";
    return "No rows";
  }

  function auditReviewBoardLines() {
    const audit = lastAuditPreviewPayload || {};
    const rows = Array.isArray(lastAuditRows) ? lastAuditRows : [];
    const warnings = Array.isArray(audit.warnings) ? audit.warnings.filter(Boolean) : [];
    if (audit.error) {
      return [
        "Audit review board: unavailable.",
        `Error: ${audit.error}`,
        "First action: open Latest Audit CSV and Audit Reports, then run a fresh Audit if the CSV cannot be parsed.",
        "Mutation guardrail: Reports remains read-only; CSV rerun must be launched through backend-owned Launch controls.",
      ];
    }
    if (!reportPreviewLoaded(audit, rows)) {
      return [
        "Audit review board: no audit preview has loaded yet.",
        "First action: refresh Reports, run Audit from Launch, or turn off priority-only mode if needed.",
        "Mutation guardrail: Reports remains read-only; it does not write CSVs, rerun rows, or change library files.",
      ];
    }
    const redownloadRows = rows.filter((row) => String(row.effective_bucket || "").toUpperCase() === "REDOWNLOAD_CANDIDATE");
    const rerunRows = rows.filter((row) => String(row.effective_bucket || "").toUpperCase() === "RERUN_PIPELINE");
    const highRows = rows.filter((row) => String(row.priority_fix_level || "").toUpperCase() === "HIGH");
    const reviewRows = [...redownloadRows, ...rerunRows, ...highRows.filter((row) => !redownloadRows.includes(row) && !rerunRows.includes(row)), ...rows.filter((row) => !redownloadRows.includes(row) && !rerunRows.includes(row) && !highRows.includes(row))];
    const lines = [
      "Audit review board:",
      `Rows: ${reportNumber(audit.count || rows.length)}`,
      `Priority CSV mode: ${audit.priority_only ? "yes" : "no"}`,
      `Bucket counts: ${reportFormatCounts(reportCountBy(rows, "effective_bucket"))}`,
      `Priority counts: ${reportFormatCounts(reportCountBy(rows, "priority_fix_level"))}`,
      `Issue-code counts: ${reportFormatCounts(reportCountBy(rows, "primary_issue_code"))}`,
      `Media counts: ${reportFormatCounts(reportCountBy(rows, "media_type"))}`,
      `Redownload rows: ${redownloadRows.length}`,
      `Rerun rows: ${rerunRows.length}`,
      `High-priority rows: ${highRows.length}`,
      `Duplicate groups: ${reportNumber(audit.duplicate_group_count)}`,
    ];
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    if (reviewRows.length) {
      lines.push("", "First rows to inspect:");
      reviewRows.slice(0, 6).forEach((row) => {
        const title = row.lookup_title || row.relative_path || row.path || "unknown source";
        const bucket = row.effective_bucket || "unknown";
        const priority = row.priority_fix_level || row.priority_score || "no-priority";
        const issue = row.primary_issue_code || row.issue_messages || "no-issue-code";
        const action = row.primary_suggested_action || "review audit row";
        lines.push(`- ${bucket} / ${priority} / ${issue}: ${title} -> ${action}`);
      });
    }
    lines.push("");
    if (redownloadRows.length) {
      lines.push("Next step: redownload candidates should be checked manually; WebView does not auto-redownload or delete media.");
    } else if (rerunRows.length || highRows.length) {
      lines.push("Next step: inspect rows, then use backend-owned Launch > CSV Rerun with the intended CSV path.");
    } else if (rows.length) {
      lines.push("Next step: select a row to verify the bucket, issue proof, and Diagnostics handoff.");
    } else {
      lines.push("Next step: no audit rows are present; run Audit from Launch if you expected recommendations.");
    }
    lines.push("Mutation guardrail: Reports remains read-only; CSV rerun/export decisions must stay backend-owned.");
    return lines;
  }

  function renderAuditReviewBoard() {
    setText("audit-review-status", auditReviewStatus());
    setText("audit-review-board", auditReviewBoardLines().join("\n"));
  }

  function reportTriageStatus() {
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    const snapshotWarnings = Array.isArray(lastReportSnapshot?.warnings) ? lastReportSnapshot.warnings : [];
    if (failures.error || audit.error || snapshotWarnings.length) return "Review needed";
    if (
      reportNumber(failures.operator_required_count) > 0 ||
      reportNumber(failures.permanent_count) > 0 ||
      reportNumber(audit.redownload_count) > 0 ||
      reportNumber(audit.rerun_count) > 0 ||
      reportNumber(audit.high_priority_count) > 0
    ) {
      return "Action needed";
    }
    if (lastFailureRows.length || lastAuditRows.length) return "Loaded";
    const latestPaths = lastReportSnapshot?.latest_paths || {};
    if (latestPaths.latest_failure_json || latestPaths.latest_audit_csv || latestPaths.latest_priority_csv) return "No action rows";
    return "Waiting";
  }

  function reportTriageNextStep() {
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    if (failures.error) return "Open Diagnostics > Failure Reports or Run Logs before deciding whether to rerun anything.";
    if (audit.error) return "Open Diagnostics > Audit Reports and run a fresh audit if the latest CSV cannot be read.";
    if (reportNumber(failures.operator_required_count) > 0 || reportNumber(failures.permanent_count) > 0) {
      return "Inspect Recent Failures first; permanent/operator-required rows should not be blindly rerun.";
    }
    if (reportNumber(audit.redownload_count) > 0) {
      return "Review redownload candidates before rerun; the WebView intentionally does not auto-redownload.";
    }
    if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) {
      return "Review priority/audit rows, then use backend-owned Launch > CSV Rerun with the intended CSV path.";
    }
    if (!lastFailureRows.length && !lastAuditRows.length) {
      return "Run Audit from Launch or open report roots if you expected recent failure/audit rows.";
    }
    return "No immediate failure/audit action is indicated by the loaded previews.";
  }

  function reportTriageLines() {
    const latestPaths = lastReportSnapshot?.latest_paths || {};
    const snapshotWarnings = Array.isArray(lastReportSnapshot?.warnings) ? lastReportSnapshot.warnings : [];
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    const lines = [
      `Failure JSON: ${latestPaths.latest_failure_json ? "present" : "missing"}`,
      `Audit CSV: ${latestPaths.latest_audit_csv ? "present" : "missing"}`,
      `Priority CSV: ${latestPaths.latest_priority_csv ? "present" : "missing"}`,
      `Snapshot warnings: ${snapshotWarnings.length}`,
      `Failure rows: ${reportNumber(failures.count || lastFailureRows.length)} (operator=${reportNumber(failures.operator_required_count)}, permanent=${reportNumber(failures.permanent_count)}, transient=${reportNumber(failures.transient_count)})`,
      `Audit rows: ${reportNumber(audit.count || lastAuditRows.length)} (high=${reportNumber(audit.high_priority_count)}, rerun=${reportNumber(audit.rerun_count)}, redownload=${reportNumber(audit.redownload_count)}, review=${reportNumber(audit.review_count)})`,
      `Duplicate groups: ${reportNumber(audit.duplicate_group_count)}`,
    ];
    const failureWarnings = Array.isArray(failures.warnings) ? failures.warnings.filter(Boolean) : [];
    const auditWarnings = Array.isArray(audit.warnings) ? audit.warnings.filter(Boolean) : [];
    if (failures.error) lines.push(`Failure preview error: ${failures.error}`);
    if (audit.error) lines.push(`Audit preview error: ${audit.error}`);
    if (snapshotWarnings.length || failureWarnings.length || auditWarnings.length) {
      lines.push("", "Warning(s):");
      [...snapshotWarnings, ...failureWarnings, ...auditWarnings].slice(0, 8).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("", `Next step: ${reportTriageNextStep()}`);
    lines.push("Mutation guardrail: rerun/export/repair actions must remain backend-owned commands; this panel is triage only.");
    return lines;
  }

  function renderReportTriage() {
    setText("report-triage-status", reportTriageStatus());
    setText("report-triage", reportTriageLines().join("\n"));
    renderReportInvestigation();
    renderFailureReviewBoard();
    renderAuditReviewBoard();
  }

  function reportInvestigationStatus() {
    const triage = reportTriageStatus();
    if (triage === "Action needed") return "Action needed";
    if (triage === "Review needed") return "Review";
    if (failureReviewStatus() === "Unavailable" || auditReviewStatus() === "Unavailable") return "Review";
    if (failureReviewStatus() === "Action needed" || auditReviewStatus().includes("review")) return "Review rows";
    if (triage === "Loaded" || triage === "No action rows") return "Ready";
    return "Waiting";
  }

  function reportInvestigationChecklistLines() {
    const latestPaths = lastReportSnapshot?.latest_paths || {};
    const workspacePaths = lastReportSettings?.paths || {};
    const snapshotWarnings = Array.isArray(lastReportSnapshot?.warnings) ? lastReportSnapshot.warnings : [];
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    const failureLoaded = reportPreviewLoaded(failures, lastFailureRows);
    const auditLoaded = reportPreviewLoaded(audit, lastAuditRows);
    const lines = [
      "Reports investigation checklist:",
      `Latest Failure JSON: ${latestPaths.latest_failure_json ? "present" : "missing"}`,
      `Latest Failure report: ${latestPaths.latest_failure_report ? "present" : "missing"}`,
      `Latest Audit CSV: ${latestPaths.latest_audit_csv ? "present" : "missing"}`,
      `Latest Priority CSV: ${latestPaths.latest_priority_csv ? "present" : "missing"}`,
      `Failure preview loaded: ${failureLoaded ? "yes" : "no"}`,
      `Audit preview loaded: ${auditLoaded ? "yes" : "no"}`,
      `Failure rows needing operator/permanent review: ${reportNumber(failures.operator_required_count) + reportNumber(failures.permanent_count)}`,
      `Audit rerun/redownload candidates: ${reportNumber(audit.rerun_count) + reportNumber(audit.redownload_count)}`,
      `Snapshot warnings: ${snapshotWarnings.length}`,
      `Failure report root configured: ${workspacePaths.failed_reports ? "yes" : "no"}`,
      `Audit report root configured: ${workspacePaths.audit_reports ? "yes" : "no"}`,
      "",
      "Suggested investigation order:",
    ];
    if (failures.error || reportNumber(failures.operator_required_count) || reportNumber(failures.permanent_count)) {
      lines.push("1. Recent Failures: select operator/permanent rows and read Latest Failure + Failure JSON.");
      lines.push("2. Diagnostics: compare Failure Markers and Run Logs before rerun or cleanup.");
      lines.push("3. Queue/Pending: confirm the source is not still blocked or parked.");
    } else if (audit.error || reportNumber(audit.redownload_count) || reportNumber(audit.rerun_count) || reportNumber(audit.high_priority_count)) {
      lines.push("1. Latest Audit Rows: inspect redownload/rerun/high-priority rows.");
      lines.push("2. Diagnostics: compare Latest Audit CSV, Completed Manifest, Queue Snapshot, and Run Logs.");
      lines.push("3. Launch: use CSV Rerun only after the chosen CSV/path is verified.");
    } else if (snapshotWarnings.length) {
      lines.push("1. Snapshot Warnings: read warnings and open Diagnostics state/log targets.");
      lines.push("2. Failure/Audit tables: confirm whether warnings match recent rows.");
      lines.push("3. Refresh: rerun Reports after addressing missing state artifacts.");
    } else if (!failureLoaded && !auditLoaded) {
      lines.push("1. Refresh Reports to load failure and audit previews.");
      lines.push("2. Run Audit from Launch if no current CSV exists.");
      lines.push("3. Open report roots only through backend Diagnostics allowlists.");
    } else {
      lines.push("1. Select any visible failure/audit row that looks suspicious.");
      lines.push("2. Use the row Diagnostics handoff before rerun, cleanup, or manual library edits.");
      lines.push("3. No report-driven action is indicated if both review boards are clean.");
    }
    lines.push("");
    lines.push("Mutation guardrail: Reports remains read-only; rerun, export, repair, delete, and filesystem mutation must stay behind backend-owned commands.");
    return lines;
  }

  function renderReportInvestigation() {
    setText("report-investigation-status", reportInvestigationStatus());
    setText("report-investigation-checklist", reportInvestigationChecklistLines().join("\n"));
    renderReportLaunchHandoff();
  }

  function reportLaunchCandidateCsvRows() {
    const latestPaths = lastReportSnapshot?.latest_paths || {};
    return [
      {
        label: "Latest Priority CSV",
        path: latestPaths.latest_priority_csv || "",
        purpose: "CSV Rerun candidate when priority-only audit rows were generated.",
      },
      {
        label: "Latest Audit CSV",
        path: latestPaths.latest_audit_csv || "",
        purpose: "CSV Rerun candidate when full audit rows include rerun recommendations.",
      },
    ].filter((item) => item.path);
  }

  function reportLaunchHandoffStatus() {
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    const candidateCsvs = reportLaunchCandidateCsvRows();
    if (failures.error || audit.error) return "Diagnostics first";
    if (reportNumber(failures.operator_required_count) > 0 || reportNumber(failures.permanent_count) > 0) return "Failure review first";
    if (reportNumber(audit.redownload_count) > 0) return "Manual review first";
    if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) {
      return candidateCsvs.length ? "CSV rerun candidate" : "CSV missing";
    }
    if (!reportPreviewLoaded(audit, lastAuditRows) && !candidateCsvs.length) return "Run audit first";
    if (candidateCsvs.length) return "CSV available";
    return "No handoff";
  }

  function selectedAuditLaunchHint() {
    const item = getSelectedAuditRow();
    if (!item) return "Selected audit row: none.";
    return [
      "Selected audit row:",
      `- Bucket: ${item.effective_bucket || "unknown"}`,
      `- Priority: ${item.priority_fix_level || ""} ${item.priority_score || ""}`.trim(),
      `- Issue: ${item.primary_issue_code || item.issue_messages || "unknown"}`,
      `- Suggested action: ${item.primary_suggested_action || "review before rerun"}`,
      `- Path: ${item.path || item.relative_path || "not reported"}`,
    ].join("\n");
  }

  function reportLaunchHandoffLines() {
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    const candidateCsvs = reportLaunchCandidateCsvRows();
    const lines = [
      "Reports to Launch handoff:",
      `Status: ${reportLaunchHandoffStatus()}`,
      `Audit rerun rows: ${reportNumber(audit.rerun_count)}`,
      `Audit high-priority rows: ${reportNumber(audit.high_priority_count)}`,
      `Audit redownload rows: ${reportNumber(audit.redownload_count)}`,
      `Failure operator/permanent rows: ${reportNumber(failures.operator_required_count) + reportNumber(failures.permanent_count)}`,
      `Candidate CSV paths: ${candidateCsvs.length}`,
    ];
    if (candidateCsvs.length) {
      lines.push("", "Candidate CSV path(s) to verify manually:");
      candidateCsvs.forEach((item) => {
        lines.push(`- ${item.label}: ${item.path}`);
        lines.push(`  ${item.purpose}`);
      });
    } else {
      lines.push("", "No candidate CSV path is currently reported by the backend snapshot.");
    }
    lines.push("", selectedAuditLaunchHint());
    lines.push("", "Safe handoff:");
    if (failures.error || audit.error) {
      lines.push("- Open Diagnostics first because a report preview could not be read.");
    } else if (reportNumber(failures.operator_required_count) > 0 || reportNumber(failures.permanent_count) > 0) {
      lines.push("- Inspect operator/permanent failure rows before using CSV Rerun; these rows may need manual action.");
    } else if (reportNumber(audit.redownload_count) > 0) {
      lines.push("- Redownload candidates should be manually reviewed; WebView does not auto-redownload or delete media.");
    } else if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) {
      lines.push("- Use Go To CSV Rerun, then manually paste the verified CSV path into Launch > CSV Path.");
      lines.push("- Confirm Launch preflight still says copy / keep / park before starting.");
    } else if (!reportPreviewLoaded(audit, lastAuditRows)) {
      lines.push("- Use Go To Audit Launch if no current audit CSV exists and you need fresh recommendations.");
    } else {
      lines.push("- No report-driven Launch action is currently indicated.");
    }
    lines.push("");
    lines.push("Mutation guardrail: this panel only navigates and explains context. It never fills CSV Path, starts CSV Rerun, runs Audit, exports reports, or mutates files.");
    return lines;
  }

  function renderReportLaunchHandoff() {
    setText("report-launch-handoff-status", reportLaunchHandoffStatus());
    setText("report-launch-handoff", reportLaunchHandoffLines().join("\n"));
  }

  function reportNavigateToLaunchTarget(targetId, statusMessage) {
    if (typeof showPage === "function") {
      showPage("launch");
    }
    const tabByTarget = {
      "audit-start-library-root": "audit",
      "rerun-start-csv-path": "rerun",
    };
    const targetTab = tabByTarget[targetId] || "";
    if (targetTab) window.mediaPipelineLaunchView?.activateLaunchTab?.(targetTab);
    const target = byId(targetId);
    if (target) {
      target.scrollIntoView({ block: "center" });
      target.focus({ preventScroll: true });
    }
    setText("report-launch-handoff-action-status", statusMessage);
  }

  function reportGoToCsvRerun() {
    reportNavigateToLaunchTarget(
      "rerun-start-csv-path",
      "Opened Launch > CSV Rerun. Paste the verified CSV path manually; Reports did not fill or submit it."
    );
  }

  function reportGoToAuditLaunch() {
    reportNavigateToLaunchTarget(
      "audit-start-library-root",
      "Opened Launch > Audit. Review the library root manually; Reports did not fill or submit it."
    );
    if (typeof renderLaunchAuditProgress === "function") {
      renderLaunchAuditProgress(lastReportSnapshot);
    }
  }

  function reportGoToDiagnostics() {
    if (typeof showPage === "function") {
      showPage("diagnostics");
    }
    setText("report-launch-handoff-action-status", "Opened Diagnostics for read-only evidence review before rerun or audit decisions.");
  }

  function initReportsViewEvents() {
    initReportsTabNav();
    const rerunButton = byId("report-go-rerun-button");
    if (rerunButton) rerunButton.addEventListener("click", reportGoToCsvRerun);
    const auditButton = byId("report-go-audit-button");
    if (auditButton) auditButton.addEventListener("click", reportGoToAuditLaunch);
    const diagnosticsButton = byId("report-go-diagnostics-button");
    if (diagnosticsButton) diagnosticsButton.addEventListener("click", reportGoToDiagnostics);
    const previewSelectedClearButton = byId("failure-preview-selected-clear-button");
    if (previewSelectedClearButton) previewSelectedClearButton.addEventListener("click", () => requestFailureMarkerClear("selected", true));
    const clearSelectedButton = byId("failure-clear-selected-button");
    if (clearSelectedButton) clearSelectedButton.addEventListener("click", () => requestFailureMarkerClear("selected", false));
    const previewVisibleClearButton = byId("failure-preview-visible-clear-button");
    if (previewVisibleClearButton) previewVisibleClearButton.addEventListener("click", () => requestFailureMarkerClear("visible", true));
    const clearVisibleButton = byId("failure-clear-visible-button");
    if (clearVisibleButton) clearVisibleButton.addEventListener("click", () => requestFailureMarkerClear("visible", false));
    const previewAllClearButton = byId("failure-preview-all-clear-button");
    if (previewAllClearButton) previewAllClearButton.addEventListener("click", () => requestFailureMarkerClear("all", true));
    const clearAllButton = byId("failure-clear-all-button");
    if (clearAllButton) clearAllButton.addEventListener("click", () => requestFailureMarkerClear("all", false));
  }

  function auditEmptyStateMessage(audit, rows) {
    if (audit.error) {
      return `Audit preview unavailable: ${audit.error}. Open Diagnostics > Audit Reports and run a new audit if needed.`;
    }
    const warnings = Array.isArray(audit.warnings) ? audit.warnings.filter(Boolean) : [];
    if (warnings.length) {
      return `Audit preview loaded with warning: ${warnings.join(" | ")}`;
    }
    if (!rows.length) {
      return "No audit rows found. Run Audit from Launch, or disable priority-only mode if you expected non-priority rows.";
    }
    return "No audit rows available.";
  }

  function auditRowKey(item) {
    return [
      item?.source_csv || "",
      item?.path || "",
      item?.relative_path || "",
      item?.primary_issue_code || "",
      item?.priority_score || "",
    ].join("\u001f").toLocaleLowerCase();
  }

  function getSelectedAuditRow() {
    if (!selectedAuditRowKey) return null;
    return lastAuditRows.find((row) => auditRowKey(row) === selectedAuditRowKey) || null;
  }

  function selectAuditRow(item) {
    selectedAuditRowKey = auditRowKey(item);
    renderAuditDetail(item || null);
    renderAuditRows();
    renderReportLaunchHandoff();
  }

  function renderAuditDetail(item) {
    if (!item) {
      setText("audit-preview-detail", "No audit row selected. Select a row to inspect priority score, issue bucket, suggested action, and source CSV.");
      renderReportDiagnosticsActions("audit-preview-diagnostics-actions", auditDiagnosticsActionsForRow(null), "Reports audit page");
      return;
    }
    const handoffLines = typeof diagnosticsBridgeHandoffLines === "function"
      ? diagnosticsBridgeHandoffLines("Reports audit selected row", auditDiagnosticsActionsForRow(item), {
        evidence: [
          item.effective_bucket ? `bucket=${item.effective_bucket}` : "",
          item.priority_fix_level || item.priority_score ? `priority=${item.priority_fix_level || ""} ${item.priority_score || ""}`.trim() : "",
          item.primary_issue_code ? `issue=${item.primary_issue_code}` : "",
          item.path ? `path=${item.path}` : "",
        ],
        safeAction: "compare Latest Audit CSV, Completed Manifest, Queue Snapshot, and Run Logs before CSV rerun or library decisions.",
      })
      : [];
    const detail = [
      ...handoffLines,
      "",
      `Title: ${item.lookup_title || ""}`,
      `Media: ${item.media_type || ""}`,
      `Bucket: ${item.effective_bucket || ""}`,
      `Priority: ${item.priority_fix_level || ""} (${item.priority_score || 0})`,
      `Issue: ${item.primary_issue_code || ""}`,
      `Suggested action: ${item.primary_suggested_action || ""}`,
      `Messages: ${item.issue_messages || ""}`,
      `Path: ${item.path || ""}`,
      `Relative: ${item.relative_path || ""}`,
      `Source CSV: ${item.source_csv || ""}`,
    ];
    setText("audit-preview-detail", detail.join("\n"));
    renderReportDiagnosticsActions("audit-preview-diagnostics-actions", auditDiagnosticsActionsForRow(item), "Reports audit selected row");
  }

  function renderAuditRows() {
    const filterText = byId("audit-preview-filter")?.value || "";
    const rows = filterRows(lastAuditRows, filterText, [
      "path",
      "relative_path",
      "lookup_title",
      "media_type",
      "effective_bucket",
      "priority_fix_level",
      "primary_issue_code",
      "primary_suggested_action",
      "issue_messages",
    ]);
    setText("audit-preview-status", `${rows.length} / ${lastAuditRows.length} row${lastAuditRows.length === 1 ? "" : "s"}`);
    const tbody = byId("audit-preview-rows");
    if (!rows.length) {
      clearRows(tbody, 6, lastAuditRows.length ? "No audit rows match the filter." : lastAuditEmptyMessage);
      updateTableStatusLegend("audit-preview-table-legend", tbody, "Audit rows");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 250).forEach((item) => {
      const row = document.createElement("tr");
      const bucket = String(item.effective_bucket || "").toUpperCase();
      const priority = String(item.priority_fix_level || "").toUpperCase();
      row.dataset.status = bucket === "REDOWNLOAD_CANDIDATE" ? "blocked" : bucket === "RERUN_PIPELINE" || priority === "HIGH" ? "warning" : bucket === "OK" ? "match" : "";
      const key = auditRowKey(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item.priority_score || "",
        item.priority_fix_level || "",
        item.effective_bucket || "",
        item.media_type || "",
        item.lookup_title || item.relative_path || item.path || "",
        item.primary_issue_code || item.issue_messages || item.primary_suggested_action || "",
      ], ["num", null, null, null, null, null]);
      makeRowSelectable(row, () => selectAuditRow(item), {
        selected: Boolean(key && key === selectedAuditRowKey),
        label: `Audit row ${item.lookup_title || item.relative_path || item.path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("audit-preview-table-legend", tbody, "Audit rows");
  }

  /**
   * Public namespace for the Reports page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineReportsView = {
    renderReports,
    renderReportTriage,
    renderReportInvestigation,
    reportInvestigationStatus,
    reportInvestigationChecklistLines,
    renderReportLaunchHandoff,
    reportLaunchHandoffStatus,
    reportLaunchHandoffLines,
    reportLaunchCandidateCsvRows,
    reportGoToCsvRerun,
    reportGoToAuditLaunch,
    reportGoToDiagnostics,
    initReportsViewEvents,
    reportTriageStatus,
    reportTriageLines,
    renderFailurePreview,
    renderFailureRows,
    renderFailureDetail,
    renderFailureReviewBoard,
    failureRetryStatePayload,
    failureRetryRows,
    failureRetryStateForRow,
    failureRetryPreviewSummaryLine,
    requestFailureMarkerClear,
    renderFailureClearResult,
    failureReviewStatus,
    failureReviewBoardLines,
    failureDiagnosticsActionsForRow,
    failureEmptyStateMessage,
    selectFailureRow,
    getSelectedFailureRow,
    failureRowKey,
    renderAuditPreview,
    renderAuditRows,
    renderAuditDetail,
    renderAuditReviewBoard,
    auditReviewStatus,
    auditReviewBoardLines,
    auditDiagnosticsActionsForRow,
    auditEmptyStateMessage,
    selectAuditRow,
    getSelectedAuditRow,
    auditRowKey,
    renderKeyPathRows,
    reportLabel,
    reportOpenTarget,
    reportOpenTargetValues,
    isReportOpenCommand,
    reportOpenHistoryLine,
    renderReportOpenHistory,
    renderReportDiagnosticsActions,
    activateReportsTab,
    initReportsTabNav,
  };
  window.initReportsViewEvents = initReportsViewEvents;
  window.renderFailureRows = renderFailureRows;
  window.renderAuditRows = renderAuditRows;
  window.renderReportOpenHistory = renderReportOpenHistory;
})();
