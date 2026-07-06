// reports/shell.js
// Reports shell helpers for reportsView.js. Loaded before reportsView.js; the
// parent owns state, backend command authority, and the public namespace.

(function () {
  "use strict";

  function noop() {}

  function createReportsShellModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const REPORTS_TAB_STORAGE_KEY = String(deps.tabStorageKey || "mediapipeline-reports-tab");
    const appendCells = typeof deps.appendCells === "function" ? deps.appendCells : noop;
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const clearRows = typeof deps.clearRows === "function" ? deps.clearRows : noop;
    const commandHistoryCompactEvidenceLine = typeof deps.commandHistoryCompactEvidenceLine === "function" ? deps.commandHistoryCompactEvidenceLine : null;
    const commandHistoryView = deps.commandHistoryView && typeof deps.commandHistoryView === "object" ? deps.commandHistoryView : {};
    const diagnosticsBridgeApi = typeof deps.diagnosticsBridgeApi === "function" ? deps.diagnosticsBridgeApi : function () { return {}; };
    const reportAuditJsonDetail = typeof deps.reportAuditJsonDetail === "function" ? deps.reportAuditJsonDetail : function (_label, _value, intro) { return intro || ""; };
    const reportsTabIds = typeof deps.reportsTabIds === "function" ? deps.reportsTabIds : function () { return ["failures", "audit", "files"]; };
    const requestDiagnosticsOpen = typeof deps.requestDiagnosticsOpen === "function" ? deps.requestDiagnosticsOpen : noop;
    const requestDiagnosticsTail = typeof deps.requestDiagnosticsTail === "function" ? deps.requestDiagnosticsTail : noop;
    const setText = typeof deps.setText === "function" ? deps.setText : noop;
    const updatePagePanelEmptyStates = typeof deps.updatePagePanelEmptyStates === "function" ? deps.updatePagePanelEmptyStates : null;

  function reportsTabButtons(page) {
      if (!page) return [];
      return Array.from(page.querySelectorAll(".settings-tab-btn[data-reports-tab]"));
    }

  function reportsTabPanels(page) {
      if (!page) return [];
      return Array.from(page.children).filter((node) => (
        node instanceof HTMLElement
        && node.matches(".reports-tab-panel[data-reports-tab-panel], .settings-tab-pane[data-reports-tab-panel]")
      ));
    }

  function activateReportsTab(tabId) {
      const page = document.querySelector('[data-page-panel="reports"]');
      if (!page) return;
      const selected = reportsTabIds().includes(tabId) ? tabId : "failures";
      const buttons = reportsTabButtons(page);
      const panels = reportsTabPanels(page);
      buttons.forEach((button) => {
        const active = button.dataset.reportsTab === selected;
        button.setAttribute("aria-selected", String(active));
        button.classList.toggle("is-active", active);
      });
      panels.forEach((panel) => {
        const active = panel.dataset.reportsTabPanel === selected;
        panel.classList.toggle("is-active", active);
        panel.hidden = !active;
      });
      try { localStorage.setItem(REPORTS_TAB_STORAGE_KEY, selected); } catch (_) {}
      if (typeof window.mediaPipelineAppLifecycle?.syncTabAccessibility === "function") window.mediaPipelineAppLifecycle.syncTabAccessibility();
      if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
    }

  function initReportsTabNav() {
      const page = document.querySelector('[data-page-panel="reports"]');
      if (!page) return;
      const buttons = reportsTabButtons(page);
      if (!buttons.length) return;
      if (!reportsState.reportsTabNavInitialized) {
        buttons.forEach((button) => {
          button.addEventListener("click", () => activateReportsTab(button.dataset.reportsTab || "failures"));
        });
        reportsState.reportsTabNavInitialized = true;
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
      if (value.includes("rerun")) return "Queue CSV Rerun";
      if (value.includes("audit") || value.includes("launch")) return "Launch";
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
          button.addEventListener("click", () => requestDiagnosticsOpen(target, button));
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
      if (owner === "Launch") return "Verify launch intent, then use backend-owned Launch controls.";
      if (owner === "Queue CSV Rerun") return "Verify the CSV path, then use backend-owned Queue CSV Rerun controls.";
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
      (Array.isArray(reportsState.lastReportSnapshot?.warnings) ? reportsState.lastReportSnapshot.warnings : []).forEach((warning) => addWarning("Snapshot", warning));
      (Array.isArray(reportsState.lastFailurePreviewPayload?.warnings) ? reportsState.lastFailurePreviewPayload.warnings : []).forEach((warning) => addWarning("Failures", warning));
      (Array.isArray(reportsState.lastAuditPreviewPayload?.warnings) ? reportsState.lastAuditPreviewPayload.warnings : []).forEach((warning) => addWarning("Audit", warning));
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

  function reportAddDiagnosticsAction(actions, kind, target, label, reason) {
      if (!target || actions.some((item) => item.kind === kind && item.target === target)) return;
      actions.push({ kind, target, label, reason });
    }

  function reportOwnerPage(owner) {
      const text = String(owner || "").toLowerCase();
      if (!text || text === "no action") return null;
      if (text.includes("pending publish")) return { page: "pending", label: "Pending Publish" };
      if (text.includes("queue")) return { page: "queue", label: "Queue" };
      if (text.includes("settings")) return { page: "settings", label: "Settings" };
      if (text.includes("completed")) return { page: "completed", label: "Completed" };
      if (text.includes("rerun")) return { page: "queue", label: "Queue" };
      if (text.includes("launch")) return { page: "launch", label: "Launch" };
      if (text.includes("diagnostics") || text.includes("manual")) return { page: "diagnostics", label: "Diagnostics" };
      if (text.includes("reports")) return { page: "reports", label: "Reports" };
      return null;
    }

  function appendReportOwnerNavigationButton(container, owner) {
      const target = reportOwnerPage(owner);
      if (!container || !target) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button";
      button.textContent = `Go to ${target.label}`;
      button.title = `Navigate locally to ${target.label}; Reports does not perform the owner action.`;
      button.dataset.reportOwnerNavigate = target.page;
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        if (typeof window.showPage === "function") window.showPage(target.page);
      });
      container.appendChild(button);
    }

  function renderReportDiagnosticsActions(containerId, actions, sourceLabel) {
      const container = byId(containerId);
      if (!container) return;
      container.replaceChildren();
      const bridge = diagnosticsBridgeApi();
      const bridgeActions = typeof bridge.diagnosticsBridgeActions === "function"
        ? bridge.diagnosticsBridgeActions(actions)
        : (Array.isArray(actions) ? actions : []);
      bridgeActions.forEach((action) => {
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.textContent = typeof bridge.diagnosticsBridgeActionLabel === "function"
          ? bridge.diagnosticsBridgeActionLabel(action)
          : action.label || `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
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
      if (typeof bridge.appendDiagnosticsBridgeButton === "function") {
        bridge.appendDiagnosticsBridgeButton(container, actions, sourceLabel);
      }
    }

    return {
      activateReportsTab,
      appendReportOwnerNavigationButton,
      collectReportWarnings,
      initReportsTabNav,
      isReportOpenCommand,
      renderKeyPathRows,
      renderReportDiagnosticsActions,
      renderReportOpenHistory,
      renderReportWarnings,
      reportAddDiagnosticsAction,
      reportCompactPath,
      reportCountLabel,
      reportLabel,
      reportLatestState,
      reportOpenHistoryLine,
      reportOpenTarget,
      reportOpenTargetValues,
      reportOwnerFromText,
      reportOwnerPage,
    };
  }

  window.__reportsViewShellModule = {
    createReportsShellModule,
  };
})();
