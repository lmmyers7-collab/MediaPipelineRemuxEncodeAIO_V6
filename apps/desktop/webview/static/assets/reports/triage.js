// reports/triage.js
// Cross-tab Reports triage and investigation helpers for reportsView.js.

(function () {
  "use strict";

  function noop() {}

  function createReportsTriageModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const auditReviewStatus = typeof deps.auditReviewStatus === "function" ? deps.auditReviewStatus : function () { return "Waiting"; };
    const collectReportWarnings = typeof deps.collectReportWarnings === "function" ? deps.collectReportWarnings : function () { return []; };
    const failureReviewStatus = typeof deps.failureReviewStatus === "function" ? deps.failureReviewStatus : function () { return "Waiting"; };
    const renderAuditReviewBoard = typeof deps.renderAuditReviewBoard === "function" ? deps.renderAuditReviewBoard : noop;
    const renderFailureReviewBoard = typeof deps.renderFailureReviewBoard === "function" ? deps.renderFailureReviewBoard : noop;
    const renderReportWarnings = typeof deps.renderReportWarnings === "function" ? deps.renderReportWarnings : noop;
    const reportAuditReviewCount = typeof deps.reportAuditReviewCount === "function" ? deps.reportAuditReviewCount : function () { return 0; };
    const reportFailureReviewCount = typeof deps.reportFailureReviewCount === "function" ? deps.reportFailureReviewCount : function () { return 0; };
    const reportLatestState = typeof deps.reportLatestState === "function" ? deps.reportLatestState : function () { return "Unknown"; };
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
    const reportPreviewLoaded = typeof deps.reportPreviewLoaded === "function" ? deps.reportPreviewLoaded : function (_payload, rows) { return Array.isArray(rows) && rows.length > 0; };
    const setText = typeof deps.setText === "function" ? deps.setText : noop;

  function reportTriageActionOwner() {
    const failures = reportsState.lastFailurePreviewPayload || {};
    const audit = reportsState.lastAuditPreviewPayload || {};
    if (failures.error || audit.error) return "Diagnostics";
    if (reportFailureReviewCount() > 0) return "Failures";
    if (reportNumber(audit.redownload_count) > 0) return "Manual source review";
    if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) return "Queue CSV Rerun";
    const warningRows = collectReportWarnings();
    if (warningRows.length) return warningRows[0].owner || "Diagnostics";
    return "Reports";
  }

  function reportTriageBandNextAction() {
    const owner = reportTriageActionOwner();
    const latestPaths = reportsState.lastReportSnapshot?.latest_paths || {};
    if (
      owner === "Reports"
      && !reportsState.lastFailureRows.length
      && !reportsState.lastAuditRows.length
      && !latestPaths.latest_failure_json
      && !latestPaths.latest_audit_csv
      && !latestPaths.latest_priority_csv
    ) {
      return "Load reports";
    }
    if (owner === "Failures") return "Inspect failure rows";
    if (owner === "Manual source review") return "Review redownload candidates";
    if (owner === "Queue CSV Rerun") return "Verify CSV rerun";
    if (owner === "Launch") return "Verify launch intent";
    if (owner === "Diagnostics") return "Open diagnostics evidence";
    if (owner === "Reports") return "No report action";
    return `Review ${owner}`;
  }

  function renderReportTriageBand() {
    const latestPaths = reportsState.lastReportSnapshot?.latest_paths || {};
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

  function reportTriageStatus() {
    const failures = reportsState.lastFailurePreviewPayload || {};
    const audit = reportsState.lastAuditPreviewPayload || {};
    const snapshotWarnings = Array.isArray(reportsState.lastReportSnapshot?.warnings) ? reportsState.lastReportSnapshot.warnings : [];
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
    if (reportsState.lastFailureRows.length || reportsState.lastAuditRows.length) return "Loaded";
    const latestPaths = reportsState.lastReportSnapshot?.latest_paths || {};
    if (latestPaths.latest_failure_json || latestPaths.latest_audit_csv || latestPaths.latest_priority_csv) return "No action rows";
    return "Waiting";
  }

  function reportTriageNextStep() {
    const failures = reportsState.lastFailurePreviewPayload || {};
    const audit = reportsState.lastAuditPreviewPayload || {};
    if (failures.error) return "Open Diagnostics > Failure Reports or Run Logs before deciding whether to rerun anything.";
    if (audit.error) return "Open Diagnostics > Audit Reports and run a fresh audit if the latest CSV cannot be read.";
    if (reportNumber(failures.operator_required_count) > 0 || reportNumber(failures.permanent_count) > 0) {
      return "Inspect Recent Failures first; permanent/operator-required rows should not be blindly rerun.";
    }
    if (reportNumber(audit.redownload_count) > 0) {
      return "Review redownload candidates before rerun; the WebView intentionally does not auto-redownload.";
    }
    if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) {
      return "Review priority/audit rows, then use backend-owned Queue > CSV Rerun with the intended CSV path.";
    }
    if (!reportsState.lastFailureRows.length && !reportsState.lastAuditRows.length) {
      return "Run Audit from Launch or open report roots if you expected recent failure/audit rows.";
    }
    return "No immediate failure/audit action is indicated by the loaded previews.";
  }

  function reportTriageLines() {
    const latestPaths = reportsState.lastReportSnapshot?.latest_paths || {};
    const snapshotWarnings = Array.isArray(reportsState.lastReportSnapshot?.warnings) ? reportsState.lastReportSnapshot.warnings : [];
    const warningRows = collectReportWarnings();
    const failures = reportsState.lastFailurePreviewPayload || {};
    const audit = reportsState.lastAuditPreviewPayload || {};
    const lines = [
      `Failure JSON: ${latestPaths.latest_failure_json ? "present" : "missing"}`,
      `Audit CSV: ${latestPaths.latest_audit_csv ? "present" : "missing"}`,
      `Priority CSV: ${latestPaths.latest_priority_csv ? "present" : "missing"}`,
      `Actionable warnings: ${warningRows.length}`,
      `Failure rows: ${reportNumber(failures.count || reportsState.lastFailureRows.length)} (operator=${reportNumber(failures.operator_required_count)}, permanent=${reportNumber(failures.permanent_count)}, transient=${reportNumber(failures.transient_count)})`,
      `Audit rows: ${reportNumber(audit.count || reportsState.lastAuditRows.length)} (high=${reportNumber(audit.high_priority_count)}, rerun=${reportNumber(audit.rerun_count)}, redownload=${reportNumber(audit.redownload_count)}, review=${reportNumber(audit.review_count)})`,
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
    const latestPaths = reportsState.lastReportSnapshot?.latest_paths || {};
    const workspacePaths = reportsState.lastReportSettings?.paths || {};
    const warningRows = collectReportWarnings();
    const failures = reportsState.lastFailurePreviewPayload || {};
    const audit = reportsState.lastAuditPreviewPayload || {};
    const failureLoaded = reportPreviewLoaded(failures, reportsState.lastFailureRows);
    const auditLoaded = reportPreviewLoaded(audit, reportsState.lastAuditRows);
    const failureReviewCount = reportNumber(failures.operator_required_count) + reportNumber(failures.permanent_count);
    const auditReviewCount = reportNumber(audit.rerun_count) + reportNumber(audit.redownload_count) + reportNumber(audit.high_priority_count);
    const lines = [
      "Reports investigation checklist:",
      `Latest Failure JSON | ${latestPaths.latest_failure_json ? "Ready" : "Missing"} | Diagnostics | evidence only`,
      `Latest Failure report | ${latestPaths.latest_failure_report ? "Ready" : "Missing"} | Diagnostics | evidence only`,
      `Latest Audit CSV | ${latestPaths.latest_audit_csv ? "Ready" : "Missing"} | Diagnostics | evidence only`,
      `Latest Priority CSV | ${latestPaths.latest_priority_csv ? "Ready" : "Missing"} | Queue | verify before CSV rerun`,
      `Failure preview | ${failureLoaded ? "Loaded" : "Not loaded"} | Failures | row triage only`,
      `Audit preview | ${auditLoaded ? "Loaded" : "Not loaded"} | Audit | row triage/export only`,
      `Failure review rows | ${failureReviewCount ? "Needs review" : "Ready"} | Failures | ${failureReviewCount} row(s)`,
      `Audit rerun/redownload rows | ${auditReviewCount ? "Needs review" : "Ready"} | Audit/Queue | ${auditReviewCount} row(s)`,
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
      lines.push("3. Action owner | Queue | use CSV Rerun only after the chosen CSV/path is verified.");
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
    lines.push("Mutation guardrail: Reports triage is read-only; error clearing, rerun, export, repair, delete, and filesystem mutation must stay behind backend-owned commands.");
    return lines;
  }

  function renderReportInvestigation() {
    setText("report-investigation-status", reportInvestigationStatus());
    setText("report-investigation-checklist", reportInvestigationChecklistLines().join("\n"));
  }


    return {
      renderReportInvestigation,
      renderReportTriage,
      renderReportTriageBand,
      reportInvestigationChecklistLines,
      reportInvestigationStatus,
      reportTriageActionOwner,
      reportTriageBandNextAction,
      reportTriageLines,
      reportTriageNextStep,
      reportTriageStatus,
    };
  }

  window.__reportsViewTriageModule = {
    createReportsTriageModule,
  };
})();
