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
  let selectedAuditRowKeys = new Set();
  let lastAuditControls = {};
  let lastFailureEmptyMessage = "No failure rows available.";
  let lastAuditEmptyMessage = "No audit rows available.";
  let activeFailureFilterChip = "all";
  let activeAuditFilterChip = "all";
  let reportsTabNavInitialized = false;
  let reportsViewEventsInitialized = false;
  const REPORTS_TAB_STORAGE_KEY = "mediapipeline-reports-tab";
  const reportAuditScoreFieldIds = {
    redownload_bucket: "report-audit-score-redownload-bucket",
    high_issue: "report-audit-score-high-issue",
    rerun_bucket: "report-audit-score-rerun-bucket",
    medium_issue: "report-audit-score-medium-issue",
    review_bucket: "report-audit-score-review-bucket",
    fallback_issue: "report-audit-score-fallback-issue",
    redownload_bonus: "report-audit-score-redownload-bonus",
    rerun_bonus: "report-audit-score-rerun-bonus",
  };
  const reportAuditScoreGroupDefaultKeys = { high: "high_issue", medium: "medium_issue" };

  function reportsTabIds() {
    return ["failures", "audit", "files"];
  }

  function activateReportsTab(tabId) {
    const page = document.querySelector('[data-page-panel="reports"]');
    if (!page) return;
    const selected = reportsTabIds().includes(tabId) ? tabId : "failures";
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
    if (!reportsTabNavInitialized) {
      buttons.forEach((button) => {
        button.addEventListener("click", () => activateReportsTab(button.dataset.reportsTab || "failures"));
      });
      reportsTabNavInitialized = true;
    }
    let stored = "failures";
    try { stored = localStorage.getItem(REPORTS_TAB_STORAGE_KEY) || "failures"; } catch (_) {}
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

  function reportCompactPath(path) {
    const text = String(path || "").trim();
    if (text.length <= 96) return text;
    return `${text.slice(0, 42)}...${text.slice(-45)}`;
  }

  function reportCountLabel(count, singular, plural = `${singular}s`) {
    const numeric = Number(count || 0) || 0;
    return `${numeric} ${numeric === 1 ? singular : plural}`;
  }

  function reportLatestState(latestPaths = {}) {
    const names = [];
    if (latestPaths.latest_failure_json) names.push("failure JSON");
    if (latestPaths.latest_audit_csv) names.push("audit CSV");
    if (latestPaths.latest_priority_csv) names.push("priority CSV");
    return names.length ? names.join(", ") : "No latest reports";
  }

  function reportOwnerFromText(text) {
    const value = String(text || "").toLowerCase();
    if (value.includes("publish") || value.includes("pending")) return "Pending Publish";
    if (value.includes("queue")) return "Queue";
    if (value.includes("completed") || value.includes("manifest") || value.includes("output")) return "Completed";
    if (value.includes("setting") || value.includes("policy") || value.includes("config")) return "Settings";
    if (value.includes("audit") || value.includes("rerun") || value.includes("launch")) return "Launch";
    if (value.includes("failure") || value.includes("marker") || value.includes("log") || value.includes("path")) return "Diagnostics";
    return "Reports";
  }

  function renderReportOpenHistory(history = []) {
    const disclosure = byId("report-open-history-disclosure");
    if (typeof commandHistoryView.renderCompactCommandHistoryBlock === "function") {
      const entries = Array.isArray(history) ? history.filter(isReportOpenCommand).slice(0, 6) : [];
      if (disclosure) disclosure.open = entries.length > 0;
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
    if (disclosure) disclosure.open = entries.length > 0;
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
      appendCells(row, [item.label, reportCompactPath(item.path)]);
      const pathCell = row.children[1];
      if (pathCell) pathCell.title = item.path;
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

  function reportWarningMessage(warning) {
    if (warning && typeof warning === "object") {
      return String(warning.message || warning.warning || warning.detail || warning.reason || "").trim()
        || reportAuditJsonDetail("Warning JSON", warning, "Warning payload.");
    }
    return String(warning || "").trim();
  }

  function reportWarningSeverity(warning, message) {
    const explicit = warning && typeof warning === "object" ? String(warning.severity || warning.status || "").trim() : "";
    if (explicit) return explicit;
    const lower = String(message || "").toLowerCase();
    if (lower.includes("error") || lower.includes("blocked") || lower.includes("unavailable")) return "Blocked";
    if (lower.includes("missing") || lower.includes("stale") || lower.includes("failed")) return "Review";
    return "Notice";
  }

  function reportWarningOwner(warning, message) {
    const explicit = warning && typeof warning === "object"
      ? String(warning.owner || warning.owner_page || warning.page || "").trim()
      : "";
    return explicit || reportOwnerFromText(message);
  }

  function reportWarningAction(warning, message, owner) {
    const explicit = warning && typeof warning === "object"
      ? String(warning.next_action || warning.action || warning.safe_next_action || "").trim()
      : "";
    if (explicit) return explicit;
    const lower = String(message || "").toLowerCase();
    if (owner === "Launch") return "Verify the CSV path, then use backend-owned Launch controls.";
    if (owner === "Pending Publish") return "Compare parked output evidence before drain or rerun decisions.";
    if (owner === "Queue") return "Compare current queue snapshot before launch or rerun decisions.";
    if (owner === "Completed") return "Compare completed manifest/output evidence before accepting or rerunning.";
    if (owner === "Settings") return "Review saved policy before launch, rerun, or manual correction.";
    if (lower.includes("path") || lower.includes("missing")) return "Open the allowlisted Diagnostics target or report location.";
    return "Review row evidence and Diagnostics targets before taking action.";
  }

  function collectReportWarnings() {
    const warnings = [];
    const addWarning = (source, warning) => {
      const message = reportWarningMessage(warning);
      if (!message) return;
      const owner = reportWarningOwner(warning, message);
      warnings.push({
        source,
        severity: reportWarningSeverity(warning, message),
        message,
        owner,
        nextAction: reportWarningAction(warning, message, owner),
      });
    };
    (Array.isArray(lastReportSnapshot?.warnings) ? lastReportSnapshot.warnings : []).forEach((warning) => addWarning("Snapshot", warning));
    (Array.isArray(lastFailurePreviewPayload?.warnings) ? lastFailurePreviewPayload.warnings : []).forEach((warning) => addWarning("Failures", warning));
    (Array.isArray(lastAuditPreviewPayload?.warnings) ? lastAuditPreviewPayload.warnings : []).forEach((warning) => addWarning("Audit", warning));
    const seen = new Set();
    return warnings.filter((warning) => {
      const key = `${warning.severity}\u001f${warning.message}\u001f${warning.owner}`.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function renderReportWarnings() {
    const rows = collectReportWarnings();
    setText("report-warning-count", String(rows.length));
    setText("report-triage-warning-count", String(rows.length));
    setText("report-warning-status", rows.length ? reportCountLabel(rows.length, "warning") : "No warnings");
    const tbody = byId("report-warning-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No snapshot warnings.");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 12).forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = String(item.severity || "").toLowerCase() === "blocked" ? "blocked" : "warning";
      appendCells(row, [
        item.severity,
        `${item.source}: ${item.message}`,
        item.owner,
        item.nextAction,
      ]);
      tbody.appendChild(row);
    });
  }

  function reportFailureReviewCount() {
    return reportNumber(lastFailurePreviewPayload?.operator_required_count)
      + reportNumber(lastFailurePreviewPayload?.permanent_count);
  }

  function reportAuditReviewCount() {
    return reportNumber(lastAuditPreviewPayload?.redownload_count)
      + reportNumber(lastAuditPreviewPayload?.rerun_count)
      + reportNumber(lastAuditPreviewPayload?.high_priority_count);
  }

  function reportTriageActionOwner() {
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    if (failures.error || audit.error) return "Diagnostics";
    if (reportFailureReviewCount() > 0) return "Failures";
    if (reportNumber(audit.redownload_count) > 0) return "Manual source review";
    if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) return "Launch";
    const warningRows = collectReportWarnings();
    if (warningRows.length) return warningRows[0].owner || "Diagnostics";
    return "Reports";
  }

  function reportTriageBandNextAction() {
    const owner = reportTriageActionOwner();
    const latestPaths = lastReportSnapshot?.latest_paths || {};
    if (
      owner === "Reports"
      && !lastFailureRows.length
      && !lastAuditRows.length
      && !latestPaths.latest_failure_json
      && !latestPaths.latest_audit_csv
      && !latestPaths.latest_priority_csv
    ) {
      return "Load reports";
    }
    if (owner === "Failures") return "Inspect failure rows";
    if (owner === "Manual source review") return "Review redownload candidates";
    if (owner === "Launch") return "Verify CSV rerun";
    if (owner === "Diagnostics") return "Open diagnostics evidence";
    if (owner === "Reports") return "No report action";
    return `Review ${owner}`;
  }

  function renderReportTriageBand() {
    const latestPaths = lastReportSnapshot?.latest_paths || {};
    const failureCount = reportFailureReviewCount();
    const auditCount = reportAuditReviewCount();
    const warningCount = collectReportWarnings().length;
    const owner = reportTriageActionOwner();
    const nextAction = reportTriageBandNextAction();
    const status = reportTriageStatus();
    setText("report-triage-band-status", status);
    setText("report-triage-next-action", nextAction);
    setText("report-triage-action-owner", owner);
    setText("report-triage-failure-count", String(failureCount));
    setText("report-triage-audit-count", String(auditCount));
    setText("report-triage-warning-count", String(warningCount));
    setText("report-triage-report-state", reportLatestState(latestPaths));
    setText("report-triage-band-detail", [
      `Next action: ${nextAction}`,
      `Action owner: ${owner}`,
      `Failure rows needing operator/permanent review: ${failureCount}`,
      `Audit rerun/redownload/high-priority candidates: ${auditCount}`,
      `Warnings needing review: ${warningCount}`,
      `Latest reports: ${reportLatestState(latestPaths)}`,
      "Boundary: Reports points to evidence and owner pages; backend commands remain authoritative for launch, rerun, publish/drain, repair, rename, settings save, and file movement.",
    ].join("\n"));
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
    renderReportWarnings();
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
    ].join("\u001f").toLowerCase();
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
    const triageFix = failureDisplayValue(item?.triage?.suggested_fix, "");
    if (triageFix) return triageFix;
    const explicit = failureDisplayValue(item?.suggested_action || item?.recommended_action || item?.next_step, "");
    if (explicit) return explicit;
    const classification = String(item?.classification || "").toLowerCase();
    if (classification === "transient") return "Preview marker clear, then rerun after confirming logs.";
    if (classification === "operator_required" || classification === "permanent") return "Open diagnostics and review the source before retry.";
    return "Review diagnostics before retry.";
  }

  function failureTriage(item) {
    return item?.triage && typeof item.triage === "object" ? item.triage : {};
  }

  function failureClearError(item) {
    return item?.clear_error && typeof item.clear_error === "object" ? item.clear_error : {};
  }

  function failureStatusLabel(item) {
    const triage = failureTriage(item);
    const label = failureDisplayValue(triage.status_label, "");
    if (label) return label;
    const retryState = failureRetryStateForRow(item);
    const classification = String(item?.classification || "").toLowerCase();
    if (retryState?.status_state === "blocked" || classification === "operator_required" || classification === "permanent") return "Needs operator";
    if (retryState?.retry_allowed) return "Will retry";
    if (item?.reason || item?.error_code) return "Review";
    return "Recorded";
  }

  function failureSeverity(item) {
    const triage = failureTriage(item);
    const severity = String(triage.severity || "").toLowerCase();
    if (severity) return severity;
    const retryState = failureRetryStateForRow(item);
    if (retryState?.status_state === "blocked") return "blocked";
    if (retryState?.retry_allowed || item?.reason || item?.error_code) return "warning";
    return "info";
  }

  function failurePlainSummaryText(item) {
    return failureDisplayValue(failureTriage(item).plain_summary, failureReasonText(item));
  }

  function failureFileText(item) {
    return failureDisplayValue(item?.lookup_title || item?.source_path, "Unknown file");
  }

  function normalizeFailureMarkerPaths(paths) {
    const seen = new Set();
    const result = [];
    (Array.isArray(paths) ? paths : []).forEach((path) => {
      const markerPath = String(path || "").trim();
      const key = markerPath.toLowerCase();
      if (markerPath && !seen.has(key)) {
        seen.add(key);
        result.push(markerPath);
      }
    });
    return result;
  }

  function failureClearMarkerPathsForRow(item) {
    const clear = failureClearError(item);
    const markerPaths = normalizeFailureMarkerPaths([
      ...(Array.isArray(clear.marker_paths) ? clear.marker_paths : []),
      clear.marker_path,
    ]);
    if (markerPaths.length) return markerPaths;
    if (failureMarkerModeActive()) return normalizeFailureMarkerPaths([failureMarkerPath(item)]);
    return [];
  }

  function failureClearMarkerPath(item) {
    return failureClearMarkerPathsForRow(item)[0] || "";
  }

  function failureClearUnavailableReason(item) {
    return failureDisplayValue(
      failureClearError(item).unavailable_reason,
      "No active failure marker is available for this row."
    );
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

  function failureRowSearchText(item) {
    return [
      item?.stage,
      item?.error_code,
      item?.classification,
      item?.reason,
      item?.suggested_action,
      item?.retry_safe_next_action,
      item?.lookup_title,
      item?.source_path,
      item?.media_type,
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function failureActionOwner(item) {
    const text = failureRowSearchText(item);
    const classification = String(item?.classification || "").toLowerCase();
    if (text.includes("publish") || text.includes("pending")) return "Pending Publish";
    if (text.includes("queue")) return "Queue";
    if (text.includes("subtitle") || text.includes("bdpgs") || text.includes("tx3g") || text.includes("vobsub") || text.includes("ocr")) return "Settings";
    if (text.includes("audio") || text.includes("commentary") || text.includes("language")) return "Settings";
    if (text.includes("completed") || text.includes("output") || text.includes("manifest")) return "Completed";
    if (classification === "transient" || failureRetryStateForRow(item)?.retry_allowed) return "Launch";
    if (classification === "operator_required" || classification === "permanent") return "Manual review";
    return "Diagnostics";
  }

  function failureTableEvidenceText(item) {
    return [
      `Stage: ${failureStageText(item)}`,
      `Code: ${item?.error_code || "no-code"}`,
      `Class: ${failureClassificationText(item)}`,
      `Retry: ${failureRetrySummaryText(item)}`,
      `Marker: ${failureClearMarkerPathsForRow(item).length ? "available" : "not active"}`,
    ].join("\n");
  }

  function failureMatchesChip(item, chip) {
    const selected = String(chip || "all");
    if (selected === "all") return true;
    const text = failureRowSearchText(item);
    const retry = failureRetryStateForRow(item);
    const classification = String(item?.classification || "").toLowerCase();
    if (selected === "needs_operator") return ["operator_required", "permanent"].includes(classification);
    if (selected === "will_retry") return Boolean(retry?.retry_allowed);
    if (selected === "blocked") return retry?.status_state === "blocked" || ["operator_required", "permanent"].includes(classification);
    if (selected === "warnings") return failureSeverity(item) === "warning" || retry?.status_state === "warning";
    return text.includes(selected);
  }

  function setReportChipPressed(selector, activeValue) {
    document.querySelectorAll(selector).forEach((button) => {
      const value = button.dataset.failureFilterChip || button.dataset.auditFilterChip || "all";
      button.setAttribute("aria-pressed", String(value === activeValue));
    });
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

  function setFailureMarkerSourceMode(enabled) {
    const checkbox = byId("failure-source-markers");
    if (!checkbox) return false;
    checkbox.checked = Boolean(enabled);
    return true;
  }

  function visibleFailureRows() {
    const filterText = byId("failure-filter")?.value || "";
    const textRows = filterRows(lastFailureRows, filterText, [
      "classification",
      "error_code",
      "stage",
      "media_type",
      "lookup_title",
      "source_path",
      "reason",
      "suggested_action",
      "retry_safe_next_action",
    ]);
    return textRows.filter((row) => failureMatchesChip(row, activeFailureFilterChip));
  }

  function failureMarkerPath(item) {
    return String(item?.source_json || "").trim();
  }

  function selectedFailureMarkerPaths() {
    const seen = new Set();
    const paths = [];
    getSelectedFailureRows().forEach((item) => {
      failureClearMarkerPathsForRow(item).forEach((markerPath) => {
        const key = markerPath.toLowerCase();
        if (markerPath && !seen.has(key)) {
          seen.add(key);
          paths.push(markerPath);
        }
      });
    });
    return paths;
  }

  function visibleFailureMarkerPaths() {
    const seen = new Set();
    const paths = [];
    visibleFailureRows().forEach((item) => {
      failureClearMarkerPathsForRow(item).forEach((markerPath) => {
        const key = markerPath.toLowerCase();
        if (markerPath && !seen.has(key)) {
          seen.add(key);
          paths.push(markerPath);
        }
      });
    });
    return paths;
  }

  function allFailureMarkerPaths() {
    const seen = new Set();
    const paths = [];
    lastFailureRows.forEach((item) => {
      failureClearMarkerPathsForRow(item).forEach((markerPath) => {
        const key = markerPath.toLowerCase();
        if (markerPath && !seen.has(key)) {
          seen.add(key);
          paths.push(markerPath);
        }
      });
    });
    return paths;
  }

  function failureClearRequest(scope, dryRun) {
    const clearAll = scope === "all" || scope === "all_markers";
    const apiScope = scope === "all" ? "all_markers" : scope;
    const markerPaths = clearAll ? [] : scope === "visible" ? visibleFailureMarkerPaths() : selectedFailureMarkerPaths();
    if (clearAll) {
      const markerCount = reportNumber(lastFailurePreviewPayload.count || lastFailureRows.length);
      if (!markerCount && !lastFailureRows.length) {
        return { error: "No marker rows are loaded." };
      }
      return { scope: "all_markers", marker_paths: [], dry_run: dryRun, confirm_clear: !dryRun, all_markers: true, marker_count: markerCount };
    }
    if (!markerPaths.length) {
      return { error: clearAll ? "No marker rows are loaded." : scope === "visible" ? "No visible marker rows are loaded." : "Select one or more failure marker rows first." };
    }
    return { scope: apiScope, marker_paths: markerPaths, dry_run: dryRun, confirm_clear: !dryRun, all_markers: false, marker_count: markerPaths.length };
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
      "Guardrail: this command moves marker JSON out of State\\Failures\\Markers only; it does not delete media, logs, reports, completed manifests, pending publish state, or source/output files.",
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
      const count = request.all_markers
        ? reportNumber(request.marker_count)
        : Array.isArray(request.marker_paths) ? request.marker_paths.length : 0;
      const targetText = request.all_markers
        ? "all backend failure markers"
        : `${count} failure error${count === 1 ? "" : "s"}`;
      const message = request.all_markers
        ? `Clear ${targetText}?\n\nThis moves marker JSON out of the active marker folder so the pipeline can retry those source files. It does not delete media files, logs, reports, manifests, source files, or output files.`
        : "Clear this error?\n\nThis moves the active failure marker out of the blocking folder so the file can be retried later. It does not delete media files, logs, reports, manifests, source files, or output files.";
      if (!window.confirm(message)) return;
    }
    setText("failure-clear-status", dryRun ? "Previewing..." : "Clearing...");
    setText("failure-clear-summary", dryRun ? "Previewing backend marker clear. No marker files will move." : "Clearing backend marker files after confirmation.");
    try {
      const payload = {
        scope: request.scope,
        dry_run: dryRun,
        confirm_clear: !dryRun,
      };
      if (!request.all_markers) payload.marker_paths = request.marker_paths;
      const result = await apiPost("/api/failures/clear", payload);
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      renderFailureClearResult(result);
      if (!dryRun && result?.ok) {
        const movedMarkers = Number(result?.data?.markers || 0) || 0;
        if (movedMarkers > 0 || request.all_markers) {
          setFailureMarkerSourceMode(true);
        }
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

  async function requestFailureRowClear(item) {
    const markerPaths = failureClearMarkerPathsForRow(item);
    if (!markerPaths.length) {
      setText("failure-clear-status", "Blocked");
      setText("failure-clear-summary", failureClearUnavailableReason(item));
      return;
    }
    selectedFailureRowKey = failureRowKey(item);
    selectedFailureRowKeys = new Set([selectedFailureRowKey].filter(Boolean));
    renderFailureRows();
    await requestFailureMarkerClear("selected", false);
  }

  function auditRowSearchText(item) {
    return [
      item?.effective_bucket,
      item?.priority_fix_level,
      item?.primary_issue_code,
      item?.primary_suggested_action,
      item?.issue_messages,
      item?.lookup_title,
      item?.relative_path,
      item?.path,
      item?.media_type,
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function auditActionOwner(item) {
    const bucket = String(item?.effective_bucket || "").toUpperCase();
    const text = auditRowSearchText(item);
    if (bucket === "REDOWNLOAD_CANDIDATE") return "Manual source review";
    if (bucket === "RERUN_PIPELINE") return "Launch CSV Rerun";
    if (text.includes("subtitle") || text.includes("bdpgs") || text.includes("tx3g") || text.includes("vobsub") || text.includes("ocr")) return "Settings policy review";
    if (text.includes("audio") || text.includes("commentary") || text.includes("language")) return "Settings policy review";
    if (text.includes("completed") || text.includes("manifest") || text.includes("output")) return "Completed evidence review";
    if (bucket === "OK") return "No action";
    return "Completed evidence review";
  }

  function auditMatchesChip(item, chip) {
    const selected = String(chip || "all");
    if (selected === "all") return true;
    const bucket = String(item?.effective_bucket || "").toUpperCase();
    const priority = String(item?.priority_fix_level || "").toUpperCase();
    const text = auditRowSearchText(item);
    if (selected === "rerun") return bucket === "RERUN_PIPELINE";
    if (selected === "redownload") return bucket === "REDOWNLOAD_CANDIDATE";
    if (selected === "review") return bucket === "REVIEW" || text.includes("review");
    if (selected === "high") return priority === "HIGH" || Number(item?.priority_score || 0) >= 80;
    if (selected === "duplicates") return text.includes("duplicate") || Boolean(item?.duplicate_group || item?.duplicate_group_key || item?.duplicate_group_size);
    return text.includes(selected);
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
      setText("failure-detail", "No failure row selected. Select a row or use Open details to inspect the full error log.");
      renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForRow(null), "Reports failure page");
      return;
    }
    const clearMarkerPaths = failureClearMarkerPathsForRow(item);
    const clearAvailable = clearMarkerPaths.length > 0;
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
      "What happened",
      `Status: ${failureStatusLabel(item)}`,
      `Summary: ${failurePlainSummaryText(item)}`,
      `Reason: ${failureReasonText(item)}`,
      `Stage: ${failureStageText(item)}`,
      `Code: ${item.error_code || ""}`,
      `Class: ${failureClassificationText(item)}`,
      "",
      "Suggested fix",
      `Suggested action: ${failureSuggestedActionText(item)}`,
      `Suggested rename: ${item.suggested_rename || ""}`,
      "",
      "Retry state",
      `Retry: ${item.retry_count || 0}/${item.retry_limit || 0}`,
      ...failureRetryDetailLines(item),
      `Safe next action: ${item.retry_safe_next_action || failureSuggestedActionText(item)}`,
      "",
      "Owner routing",
      "Evidence owner: Diagnostics",
      `Action owner: ${failureActionOwner(item)}`,
      "",
      "Evidence",
      `Title: ${item.lookup_title || ""}`,
      `Media: ${item.media_type || ""}`,
      `Escalated: ${item.escalated ? "yes" : "no"}`,
      `Recorded: ${failureRecordedText(item.recorded_at)}`,
      `Source: ${item.source_path || ""}`,
      `Artifact: ${item.artifact_path || ""}`,
      `Repro: ${item.repro_path || ""}`,
      `Record file: ${item.source_json || ""}`,
      `Clear error: ${clearAvailable ? `available (${clearMarkerPaths.length} marker${clearMarkerPaths.length === 1 ? "" : "s"})` : failureClearUnavailableReason(item)}`,
    ];
    setText("failure-detail", detail.join("\n"));
    renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForRow(item), "Reports failure selected row");
  }

  function renderFailureRows() {
    setReportChipPressed("[data-failure-filter-chip]", activeFailureFilterChip);
    const rows = visibleFailureRows();
    setText("failure-status", `${rows.length} / ${lastFailureRows.length} row${lastFailureRows.length === 1 ? "" : "s"}`);
    const tbody = byId("failure-rows");
    if (!rows.length) {
      clearRows(tbody, 7, lastFailureRows.length ? "No failure rows match the filter." : lastFailureEmptyMessage);
      updateTableStatusLegend("failure-table-legend", tbody, "Failure rows");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 250).forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = failureSeverity(item);
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
        failureStatusLabel(item),
        failureFileText(item),
        failureTableEvidenceText(item),
        failureSuggestedActionText(item),
        failureActionOwner(item),
      ]);
      const actionCell = document.createElement("td");
      const actions = document.createElement("div");
      actions.className = "action-row action-row-left wrap-actions";
      const detailsButton = document.createElement("button");
      detailsButton.type = "button";
      detailsButton.className = "secondary-button";
      detailsButton.textContent = "Open details";
      detailsButton.addEventListener("click", (event) => {
        event.stopPropagation();
        selectFailureRow(item);
      });
      actions.appendChild(detailsButton);
      const markerPaths = failureClearMarkerPathsForRow(item);
      const clearAvailable = markerPaths.length > 0;
      const clearButton = document.createElement("button");
      clearButton.type = "button";
      clearButton.className = clearAvailable ? "danger-button" : "secondary-button";
      clearButton.textContent = "Clear error";
      clearButton.disabled = !clearAvailable;
      clearButton.title = clearAvailable
        ? `Clear ${markerPaths.length === 1 ? "this active failure marker" : `${markerPaths.length} active failure markers`} without deleting media or logs.`
        : failureClearUnavailableReason(item);
      clearButton.addEventListener("click", (event) => {
        event.stopPropagation();
        requestFailureRowClear(item);
      });
      actions.appendChild(clearButton);
      actionCell.appendChild(actions);
      row.appendChild(actionCell);
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
    const availableKeys = new Set(rows.map((row) => auditRowKey(row)).filter(Boolean));
    selectedAuditRowKeys = new Set(Array.from(selectedAuditRowKeys).filter((key) => availableKeys.has(key)));
    lastAuditEmptyMessage = auditEmptyStateMessage(audit, rows);
    const summary = [
      audit.source ? `Source: ${audit.source}` : "",
      `Priority CSV mode: ${audit.priority_only ? "yes" : "no"}`,
      `Rows: ${audit.count || rows.length || 0}`,
      `Ignored rows hidden: ${audit.ignored_count || 0}`,
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
        "Mutation guardrail: Reports uses backend-owned commands only; rerun and cleanup decisions must use backend-owned workflows.",
      ];
    }
    if (!reportPreviewLoaded(failures, rows)) {
      return [
        "Failure review board: no failure preview has loaded yet.",
        "First action: refresh Reports or open Failure Reports if you expected recent failures.",
        "Mutation guardrail: Reports triage is read-only except Marker Cleanup, which only moves marker JSON through the backend command.",
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
    lines.push("Mutation guardrail: Reports triage is read-only; marker cleanup, rerun/export/repair actions must stay backend-owned.");
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
        "Mutation guardrail: Reports triage is read-only; CSV rerun must be launched through backend-owned Launch controls.",
      ];
    }
    if (!reportPreviewLoaded(audit, rows)) {
      return [
        "Audit review board: no audit preview has loaded yet.",
        "First action: refresh Reports, run Audit from Launch, or turn off priority-only mode if needed.",
        "Mutation guardrail: Reports triage is read-only; it does not write CSVs, rerun rows, or change library files.",
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
    lines.push("Mutation guardrail: Reports triage is read-only; CSV rerun/export decisions must stay backend-owned.");
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
    const warningRows = collectReportWarnings();
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    const lines = [
      `Failure JSON: ${latestPaths.latest_failure_json ? "present" : "missing"}`,
      `Audit CSV: ${latestPaths.latest_audit_csv ? "present" : "missing"}`,
      `Priority CSV: ${latestPaths.latest_priority_csv ? "present" : "missing"}`,
      `Actionable warnings: ${warningRows.length}`,
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
    renderReportWarnings();
    renderReportTriageBand();
    renderReportInvestigation();
    renderFailureReviewBoard();
    renderAuditReviewBoard();
  }

  function reportInvestigationStatus() {
    const triage = reportTriageStatus();
    const auditStatus = auditReviewStatus();
    if (triage === "Action needed") return "Action needed";
    if (triage === "Review needed") return "Review";
    if (failureReviewStatus() === "Unavailable" || auditStatus === "Unavailable") return "Review";
    if (failureReviewStatus() === "Action needed" || auditStatus.toLowerCase().includes("review")) return "Review rows";
    if (triage === "Loaded" || triage === "No action rows") return "Ready";
    return "Waiting";
  }

  function reportInvestigationChecklistLines() {
    const latestPaths = lastReportSnapshot?.latest_paths || {};
    const workspacePaths = lastReportSettings?.paths || {};
    const warningRows = collectReportWarnings();
    const failures = lastFailurePreviewPayload || {};
    const audit = lastAuditPreviewPayload || {};
    const failureLoaded = reportPreviewLoaded(failures, lastFailureRows);
    const auditLoaded = reportPreviewLoaded(audit, lastAuditRows);
    const failureReviewCount = reportNumber(failures.operator_required_count) + reportNumber(failures.permanent_count);
    const auditReviewCount = reportNumber(audit.rerun_count) + reportNumber(audit.redownload_count) + reportNumber(audit.high_priority_count);
    const lines = [
      "Reports investigation checklist:",
      `Latest Failure JSON | ${latestPaths.latest_failure_json ? "Ready" : "Missing"} | Diagnostics | evidence only`,
      `Latest Failure report | ${latestPaths.latest_failure_report ? "Ready" : "Missing"} | Diagnostics | evidence only`,
      `Latest Audit CSV | ${latestPaths.latest_audit_csv ? "Ready" : "Missing"} | Diagnostics | evidence only`,
      `Latest Priority CSV | ${latestPaths.latest_priority_csv ? "Ready" : "Missing"} | Launch | verify before CSV rerun`,
      `Failure preview | ${failureLoaded ? "Loaded" : "Not loaded"} | Failures | row triage only`,
      `Audit preview | ${auditLoaded ? "Loaded" : "Not loaded"} | Audit | row triage/export only`,
      `Failure review rows | ${failureReviewCount ? "Needs review" : "Ready"} | Failures | ${failureReviewCount} row(s)`,
      `Audit rerun/redownload rows | ${auditReviewCount ? "Needs review" : "Ready"} | Audit/Launch | ${auditReviewCount} row(s)`,
      `Warnings | ${warningRows.length ? "Review" : "Ready"} | ${warningRows[0]?.owner || "Reports"} | ${warningRows.length} warning(s)`,
      `Failure report root | ${workspacePaths.failed_reports ? "Configured" : "Missing"} | Locations | open through allowlist`,
      `Audit report root | ${workspacePaths.audit_reports ? "Configured" : "Missing"} | Locations | open through allowlist`,
      "",
      "Suggested investigation order:",
    ];
    if (failures.error || failureReviewCount) {
      lines.push("1. Needs review | Failures | select operator/permanent rows and read Latest Failure + Failure JSON.");
      lines.push("2. Evidence only | Diagnostics | compare Failure Markers and Run Logs before rerun or cleanup.");
      lines.push("3. Action owner | Queue/Pending Publish | confirm the source is not still blocked or parked.");
    } else if (audit.error || auditReviewCount) {
      lines.push("1. Needs review | Audit | inspect redownload/rerun/high-priority rows.");
      lines.push("2. Evidence only | Diagnostics | compare Latest Audit CSV, Completed Manifest, Queue Snapshot, and Run Logs.");
      lines.push("3. Action owner | Launch | use CSV Rerun only after the chosen CSV/path is verified.");
    } else if (warningRows.length) {
      lines.push("1. Review | Warnings | read actionable warning rows and owner pages.");
      lines.push("2. Evidence only | Diagnostics/Locations | open state/log targets through backend allowlists.");
      lines.push("3. Refresh | Reports | rerender after addressing missing state artifacts.");
    } else if (!failureLoaded && !auditLoaded) {
      lines.push("1. Not loaded | Reports | refresh to load failure and audit previews.");
      lines.push("2. Action owner | Launch | run Audit only if no current CSV exists.");
      lines.push("3. Evidence only | Locations/Diagnostics | open report roots through backend allowlists.");
    } else {
      lines.push("1. Ready | Reports | select any visible failure/audit row that looks suspicious.");
      lines.push("2. Evidence only | Diagnostics | use row handoff before rerun, cleanup, or manual library edits.");
      lines.push("3. Ready | Reports | no report-driven action is indicated if review boards are clean.");
    }
    lines.push("");
    lines.push("Mutation guardrail: Reports triage is read-only; marker cleanup, rerun, export, repair, delete, and filesystem mutation must stay behind backend-owned commands.");
    return lines;
  }

  function renderReportInvestigation() {
    setText("report-investigation-status", reportInvestigationStatus());
    setText("report-investigation-checklist", reportInvestigationChecklistLines().join("\n"));
  }

  function selectedAuditRowKeysList() {
    return Array.from(selectedAuditRowKeys).filter(Boolean);
  }

  function collectReportAuditScorePolicyForm() {
    const policy = {};
    Object.entries(reportAuditScoreFieldIds).forEach(([key, id]) => {
      const raw = Number(byId(id)?.value);
      policy[key] = Number.isFinite(raw) ? Math.max(0, Math.min(1000, Math.round(raw))) : 0;
    });
    policy.issue_code_weights = {};
    const details = byId("report-audit-score-redownload-bucket")?.closest("details");
    const issueInputs = details ? Array.from(details.querySelectorAll("[data-audit-score-issue-code]")) : [];
    issueInputs.forEach((input) => {
      const code = String(input.dataset.auditScoreIssueCode || "").trim();
      if (!code) return;
      const raw = Number(input.value);
      policy.issue_code_weights[code] = Number.isFinite(raw) ? Math.max(0, Math.min(1000, Math.round(raw))) : 0;
    });
    return policy;
  }

  function reportAuditScoreInputId(code) {
    return `report-audit-score-issue-${String(code || "").replace(/[^A-Za-z0-9_-]/g, "-")}`;
  }

  function reportAuditScoreValue(policy, defaults, key) {
    return policy[key] ?? defaults[key] ?? 0;
  }

  function reportAuditScoreIssueValue(policy, defaults, marker) {
    const code = String(marker?.code || "");
    const groupKey = reportAuditScoreGroupDefaultKeys[String(marker?.group || "")] || "";
    return policy.issue_code_weights?.[code]
      ?? defaults.issue_code_weights?.[code]
      ?? (groupKey ? reportAuditScoreValue(policy, defaults, groupKey) : 0);
  }

  function reportSyncAuditScoreIssueDefaults(group) {
    const groupKey = reportAuditScoreGroupDefaultKeys[group];
    if (!groupKey) return;
    const source = byId(reportAuditScoreFieldIds[groupKey]);
    if (!source) return;
    const raw = Number(source.value);
    const value = Number.isFinite(raw) ? Math.max(0, Math.min(1000, Math.round(raw))) : 0;
    const details = byId("report-audit-score-redownload-bucket")?.closest("details");
    if (!details) return;
    details.querySelectorAll(`[data-audit-score-issue-group="${group}"]`).forEach((input) => {
      if (input.dataset.auditScoreDirty === "true") return;
      input.value = String(value);
    });
  }

  function bindReportAuditScoreGroupInputs() {
    Object.entries(reportAuditScoreGroupDefaultKeys).forEach(([group, key]) => {
      const input = byId(reportAuditScoreFieldIds[key]);
      if (!input || input.dataset.auditScoreGroupBound === "true") return;
      input.dataset.auditScoreGroupBound = "true";
      input.addEventListener("input", () => reportSyncAuditScoreIssueDefaults(group));
    });
  }

  function renderReportAuditIssueRows(score, group, beforeKey) {
    const details = byId("report-audit-score-redownload-bucket")?.closest("details");
    const anchor = byId(reportAuditScoreFieldIds[beforeKey])?.closest("tr");
    if (!details || !anchor || !anchor.parentNode) return;
    details.querySelectorAll(`[data-audit-score-policy-dynamic-row="${group}"]`).forEach((row) => row.remove());
    const policy = score.policy && typeof score.policy === "object" ? score.policy : {};
    const defaults = score.defaults && typeof score.defaults === "object" ? score.defaults : {};
    const markers = Array.isArray(score.markers) ? score.markers : [];
    markers
      .filter((marker) => marker?.type === "issue_code" && marker?.group === group)
      .forEach((marker) => {
        const code = String(marker.code || "");
        if (!code) return;
        const row = document.createElement("tr");
        row.dataset.auditScorePolicyDynamicRow = group;

        const issueCell = document.createElement("td");
        const label = document.createElement("label");
        label.setAttribute("for", reportAuditScoreInputId(code));
        label.append(`${group === "high" ? "High" : "Medium"} issue: `);
        const codeNode = document.createElement("code");
        codeNode.textContent = code;
        label.appendChild(codeNode);
        issueCell.appendChild(label);

        const pointsCell = document.createElement("td");
        pointsCell.className = "num";
        const input = document.createElement("input");
        input.id = reportAuditScoreInputId(code);
        input.type = "number";
        input.min = "0";
        input.max = "1000";
        input.step = "1";
        const issueValue = reportAuditScoreIssueValue(policy, defaults, marker);
        const groupKey = reportAuditScoreGroupDefaultKeys[group] || "";
        const groupValue = groupKey ? reportAuditScoreValue(policy, defaults, groupKey) : issueValue;
        input.value = String(issueValue);
        input.dataset.auditScoreIssueCode = code;
        input.dataset.auditScoreIssueGroup = group;
        input.dataset.auditScoreDirty = issueValue === groupValue ? "false" : "true";
        input.addEventListener("input", () => { input.dataset.auditScoreDirty = "true"; });
        pointsCell.appendChild(input);

        const appliesCell = document.createElement("td");
        appliesCell.textContent = marker.applies_when || "";

        row.append(issueCell, pointsCell, appliesCell);
        anchor.parentNode.insertBefore(row, anchor);
      });
  }

  function renderAuditControls(payload) {
    lastAuditControls = payload && typeof payload === "object" ? payload : {};
    const score = lastAuditControls.score_policy && typeof lastAuditControls.score_policy === "object"
      ? lastAuditControls.score_policy
      : {};
    const policy = score.policy && typeof score.policy === "object" ? score.policy : {};
    const defaults = score.defaults && typeof score.defaults === "object" ? score.defaults : {};
    Object.entries(reportAuditScoreFieldIds).forEach(([key, id]) => {
      const input = byId(id);
      if (!input) return;
      input.value = String(policy[key] ?? defaults[key] ?? 0);
    });
    bindReportAuditScoreGroupInputs();
    renderReportAuditIssueRows(score, "high", "rerun_bucket");
    renderReportAuditIssueRows(score, "medium", "review_bucket");
    const ignoredCount = Number(lastAuditControls.ignore_manifest?.entry_count || 0);
    setText("report-audit-score-policy-status", score.persisted ? "Saved" : "Defaults");
    setText("report-audit-score-policy-summary", [
      `Score policy source: ${score.persisted ? "saved state" : "defaults"}`,
      `Audit ignore entries: ${ignoredCount}`,
      `Policy path: ${score.path || "not configured"}`,
      "Advanced score controls: enable Advanced mode, then open Advanced score controls to edit point issues.",
      "Boundary: score and ignore controls affect audit reporting/export only; they do not write queue priority, file overrides, settings, or media files.",
    ].join("\n"));
  }

  async function refreshReportsAuditData() {
    const refresh = window.refreshAll;
    if (typeof refresh === "function") {
      await refresh();
    }
  }

  function reportAuditSelectionRequest() {
    return {
      row_keys: selectedAuditRowKeysList(),
      priority_only: Boolean(lastAuditPreviewPayload.priority_only),
      limit: 100,
    };
  }

  function appendReportAuditCommandResult(result) {
    if (typeof appendCommandResult === "function") appendCommandResult(result);
  }

  function reportAuditJsonDetail(label, value, intro) {
    if (typeof jsonDetailText === "function") {
      return jsonDetailText({ label, value, intro });
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value || "");
    }
  }

  function formatReportAuditCommandDetail(result, request = null) {
    const payload = result && typeof result === "object" ? result : {
      ok: false,
      severity: "error",
      message: String(result || "Unknown command result."),
    };
    const lines = [
      `Command: ${payload.command || "unknown"}`,
      `Result: ${payload.ok ? "ok" : "blocked"}${payload.severity ? ` (${payload.severity})` : ""}`,
    ];
    const displayFormatter = window.commandResultDisplayMessage;
    const displayMessage = typeof displayFormatter === "function"
      ? displayFormatter(payload)
      : String(payload.message || "");
    if (displayMessage) {
      lines.push("", displayMessage);
    }
    if (payload.refresh_hint) {
      lines.push("", `Refresh hint: ${payload.refresh_hint}`);
    }
    if (payload.data && Object.keys(payload.data).length) {
      lines.push("", "Backend data:", reportAuditJsonDetail(
        "Backend data JSON",
        payload.data,
        "Read-only backend command result data."
      ));
    }
    if (request) {
      lines.push("", "Submitted request:", reportAuditJsonDetail(
        "Submitted request JSON",
        request,
        "Read-only request payload submitted to the backend command route."
      ));
    }
    return lines.join("\n");
  }

  async function saveReportAuditScorePolicy(reset = false) {
    const request = reset ? { reset: true } : { policy: collectReportAuditScorePolicyForm() };
    const message = reset ? "Reset audit score policy to defaults?" : "Save audit score policy for future audit runs?";
    if (!window.confirm(message)) return;
    setText("report-audit-score-policy-status", reset ? "Resetting..." : "Saving...");
    setText("report-audit-score-policy-detail", reset ? "Resetting audit score policy..." : "Saving audit score policy...");
    try {
      const result = await apiPost("/api/audit/score-policy", request);
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result, request));
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.score_policy", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-status", "Error");
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result, request));
    }
  }

  async function ignoreSelectedAuditRows() {
    const rowKeys = selectedAuditRowKeysList();
    if (!rowKeys.length) {
      setText("report-audit-export-status", "Select rows");
      setText("report-audit-export-detail", "Select one or more audit rows before setting audit ignore.");
      return;
    }
    if (!window.confirm(`Ignore ${rowKeys.length} selected audit row(s) from audit triage/export?`)) return;
    const request = {
      ...reportAuditSelectionRequest(),
      action: "add",
      reason: "Ignored from audit triage by operator.",
    };
    setText("report-audit-export-status", "Ignoring...");
    setText("report-audit-export-detail", "Saving audit ignore entries...");
    try {
      const result = await apiPost("/api/audit/ignore", request);
      appendReportAuditCommandResult(result);
      selectedAuditRowKeys = new Set();
      selectedAuditRowKey = "";
      setText("report-audit-export-status", result.ok ? "Ignored" : "Blocked");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.ignore", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Error");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
    }
  }

  async function exportAuditRerunCsv() {
    const request = reportAuditSelectionRequest();
    const scope = request.row_keys.length ? `${request.row_keys.length} selected row(s)` : "all loaded non-ignored rows";
    if (!window.confirm(`Export rerun CSV for ${scope}?`)) return;
    setText("report-audit-export-status", "Exporting...");
    setText("report-audit-export-detail", "Exporting backend-owned rerun CSV...");
    try {
      const result = await apiPost("/api/audit/export-rerun-csv", request);
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", result.ok ? "Exported" : "Blocked");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.export_rerun_csv", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Error");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
    }
  }

  function initReportsViewEvents() {
    initReportsTabNav();
    if (reportsViewEventsInitialized) return;
    reportsViewEventsInitialized = true;
    document.querySelectorAll("[data-failure-filter-chip]").forEach((button) => {
      button.addEventListener("click", () => {
        activeFailureFilterChip = button.dataset.failureFilterChip || "all";
        setReportChipPressed("[data-failure-filter-chip]", activeFailureFilterChip);
        renderFailureRows();
      });
    });
    document.querySelectorAll("[data-audit-filter-chip]").forEach((button) => {
      button.addEventListener("click", () => {
        activeAuditFilterChip = button.dataset.auditFilterChip || "all";
        setReportChipPressed("[data-audit-filter-chip]", activeAuditFilterChip);
        renderAuditRows();
      });
    });
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
    const saveAuditScorePolicyButton = byId("report-audit-score-policy-save-button");
    if (saveAuditScorePolicyButton) saveAuditScorePolicyButton.addEventListener("click", () => saveReportAuditScorePolicy(false));
    const resetAuditScorePolicyButton = byId("report-audit-score-policy-reset-button");
    if (resetAuditScorePolicyButton) resetAuditScorePolicyButton.addEventListener("click", () => saveReportAuditScorePolicy(true));
    const ignoreAuditRowsButton = byId("report-audit-ignore-selected-button");
    if (ignoreAuditRowsButton) ignoreAuditRowsButton.addEventListener("click", () => ignoreSelectedAuditRows());
    const exportAuditRowsButton = byId("report-audit-export-rerun-csv-button");
    if (exportAuditRowsButton) exportAuditRowsButton.addEventListener("click", () => exportAuditRerunCsv());
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
    if (item?.row_key) return String(item.row_key);
    return [
      item?.source_csv || "",
      item?.path || "",
      item?.relative_path || "",
      item?.primary_issue_code || "",
      item?.priority_score || "",
    ].join("\u001f").toLowerCase();
  }

  function getSelectedAuditRow() {
    if (!selectedAuditRowKey) return null;
    return lastAuditRows.find((row) => auditRowKey(row) === selectedAuditRowKey) || null;
  }

  function selectAuditRow(item) {
    selectedAuditRowKey = auditRowKey(item);
    renderAuditDetail(item || null);
    renderAuditRows();
  }

  function toggleAuditRowSelection(item, checked) {
    const key = auditRowKey(item);
    if (!key) return;
    if (checked) {
      selectedAuditRowKeys.add(key);
      selectedAuditRowKey = key;
    } else {
      selectedAuditRowKeys.delete(key);
      if (selectedAuditRowKey === key) {
        selectedAuditRowKey = Array.from(selectedAuditRowKeys)[0] || "";
      }
    }
    renderAuditDetail(getSelectedAuditRow());
    renderAuditRows();
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
      "",
      "Owner routing",
      "Evidence owner: Diagnostics",
      `Action owner: ${auditActionOwner(item)}`,
      "",
      `Path: ${item.path || ""}`,
      `Relative: ${item.relative_path || ""}`,
      `Source CSV: ${item.source_csv || ""}`,
      `Row key: ${auditRowKey(item)}`,
      `Ignored: ${item.ignored ? "yes" : "no"}`,
    ];
    setText("audit-preview-detail", detail.join("\n"));
    renderReportDiagnosticsActions("audit-preview-diagnostics-actions", auditDiagnosticsActionsForRow(item), "Reports audit selected row");
  }

  function renderAuditRows() {
    setReportChipPressed("[data-audit-filter-chip]", activeAuditFilterChip);
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
    ]).filter((row) => auditMatchesChip(row, activeAuditFilterChip));
    const selectedCount = selectedAuditRowKeys.size;
    setText("audit-preview-status", `${rows.length} / ${lastAuditRows.length} row${lastAuditRows.length === 1 ? "" : "s"}${selectedCount ? `, ${selectedCount} selected` : ""}`);
    setText("report-audit-export-status", selectedCount ? `${selectedCount} selected` : "All loaded");
    const tbody = byId("audit-preview-rows");
    if (!rows.length) {
      clearRows(tbody, 8, lastAuditRows.length ? "No audit rows match the filter." : lastAuditEmptyMessage);
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
      const selectCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(key && selectedAuditRowKeys.has(key));
      checkbox.setAttribute("aria-label", `Select audit row ${item.lookup_title || item.relative_path || item.path || ""}`);
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => toggleAuditRowSelection(item, checkbox.checked));
      selectCell.appendChild(checkbox);
      row.appendChild(selectCell);
      appendCells(row, [
        item.priority_score || "",
        item.priority_fix_level || "",
        item.effective_bucket || "",
        item.media_type || "",
        item.lookup_title || item.relative_path || item.path || "",
        item.primary_issue_code || item.issue_messages || item.primary_suggested_action || "",
        auditActionOwner(item),
      ], ["num", null, null, null, null, null, null]);
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
    renderAuditControls,
    renderAuditRows,
    renderAuditDetail,
    renderAuditReviewBoard,
    saveReportAuditScorePolicy,
    ignoreSelectedAuditRows,
    exportAuditRerunCsv,
    selectedAuditRowKeysList,
    auditReviewStatus,
    auditReviewBoardLines,
    auditDiagnosticsActionsForRow,
    auditEmptyStateMessage,
    selectAuditRow,
    toggleAuditRowSelection,
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
  window.renderAuditControls = renderAuditControls;
  window.renderReportOpenHistory = renderReportOpenHistory;
})();
