(function () {
  function createDiagnosticsFirstResponseModule(deps = {}) {
    const {
      appendCells,
      appendDiagnosticsActionGroup,
      byId,
      clearRows,
      commandHistoryView,
      diagnosticsActionGroups,
      diagnosticsConflictSignalLabel,
      diagnosticsFirstResponseAdd,
      diagnosticsFormatCounts,
      diagnosticsLogRows,
      diagnosticsMalformedStateLines,
      diagnosticsRealMediaBoundaryLines,
      diagnosticsStateOperatorStatus,
      diagnosticsStateRecommendedFirstAction,
      diagnosticsTextLines,
      makeRowSelectable,
      setDiagnosticsPanelStatus,
      setText,
      updateTableStatusLegend,    } = deps;
    let selectedDiagnosticsFirstResponseKey = "";

  function diagnosticsFirstResponsePostureStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized.includes("blocked") || normalized.includes("do not")) return "blocked";
    if (normalized.includes("review") || normalized.includes("warning")) return "warning";
    if (normalized.includes("read") || normalized.includes("stale") || normalized.includes("unknown")) return "changed";
    if (normalized.includes("ready")) return "match";
    return "unknown";
  }

  function diagnosticsSamplePolicyReconciliation(context = {}) {
    const log = context.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
    const policy = log.policy_alignment && typeof log.policy_alignment === "object" ? log.policy_alignment : {};
    const policyRows = Array.isArray(policy.rows) ? policy.rows : [];
    const completedPolicyRow = typeof window.sampleValidationCompletedPolicyReconciliationRow === "function"
      ? window.sampleValidationCompletedPolicyReconciliationRow(context || {})
      : null;
    const completedPolicyStatus = typeof window.sampleValidationCompletedPolicyReconciliationStatus === "function"
      ? window.sampleValidationCompletedPolicyReconciliationStatus(context || {})
      : (completedPolicyRow ? "Review" : "No saved-policy row");
    const completedPosture = typeof window.sampleValidationCompletedPacketPostureStatus === "function"
      ? window.sampleValidationCompletedPacketPostureStatus(completedPolicyRow)
      : String(completedPolicyRow?.posture || "").toLowerCase();
    const normalizedPolicyStatus = String(policy.operator_status || "").toLowerCase();
    const blockedPolicy = Number(policy.blocked_count || 0) > 0
      || ["blocked", "missing", "not-ready"].includes(normalizedPolicyStatus)
      || completedPosture === "blocked";
    const reviewPolicy = Number(policy.review_count || 0) > 0
      || Number(policy.missing_count || 0) > 0
      || !policyRows.length
      || !completedPolicyRow
      || ["warning", "changed", "unknown"].includes(completedPosture)
      || String(completedPolicyStatus || "").toLowerCase().includes("review")
      || String(completedPolicyStatus || "").toLowerCase().includes("no saved-policy");
    const posture = blockedPolicy ? "Blocked review" : reviewPolicy ? "Review" : "Ready";
    const evidence = [
      `saved policy=${policy.operator_status || "not loaded"}`,
      `required=${policy.required_ready_count || 0}/${policy.required_count || policyRows.filter((row) => row.required !== false).length}`,
      `policy rows=${policyRows.length}`,
      `completed reconciliation=${completedPolicyStatus}`,
      `completed evidence=${completedPolicyRow?.evidence || "not loaded"}`,
    ].join("; ");
    const action = blockedPolicy
      ? "Open Settings policy evidence, then Completed > Selected Pilot Evidence Packet > Saved policy reconciliation before accepting or rerunning."
      : reviewPolicy
        ? "Use Home > Sample Validation and Completed > Saved policy reconciliation to decide whether missing category proof is acceptable review evidence."
        : "Use policy reconciliation as supporting evidence only; playback, subtitle, audio, size, and final-placement proof still decide acceptance.";
    return {
      posture,
      evidence,
      action,
      policy,
      policyRows,
      completedPolicyRow,
      completedPolicyStatus,
      completedPosture,
    };
  }

  function diagnosticsFirstResponseRows(context = {}) {
    const payload = context || {};
    const diagnostics = payload.diagnostics || {};
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const failures = Array.isArray(payload.failures) ? payload.failures : [];
    const requiredFailures = failures.filter((failure) => failure.required);
    const activeRows = Array.isArray(diagnostics.active_job_rows) ? diagnostics.active_job_rows : [];
    const activeJobBlocked = activeRows.filter((row) => activeJobRowPosture(row) === "blocked").length;
    const activeJobReview = activeRows.filter((row) => activeJobRowPosture(row) === "warning").length;
    const allLines = [
      ...diagnosticsTextLines(diagnostics.recent_errors),
      ...diagnosticsTextLines(diagnostics.warnings),
      ...diagnosticsTextLines(diagnostics.active_jobs),
      ...diagnosticsTextLines(diagnostics.log_tail).slice(-20),
      ...diagnosticsTextLines(diagnostics.launch_logs).slice(-20),
    ];
    const malformedLines = diagnosticsMalformedStateLines(allLines);
    const severityCounts = diagnosticsLogRows(diagnostics).reduce((acc, row) => {
      const key = row.severity || "info";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const closeState = String(payload.closeReadiness?.state || payload.closeReadiness?.status || "").trim().toLowerCase();
    const closeSafe = payload.closeReadiness && payload.closeReadiness.safe_to_close === true;
    const closeBlocked = payload.closeReadiness && payload.closeReadiness.safe_to_close === false;
    const snapshotState = String(payload.snapshot?.pipeline_state || payload.closeReadiness?.state || "unknown").trim();
    const reviewRows = queueReviews.length + completedReviews.length + pendingReviews.length;
    const rows = [];

    diagnosticsFirstResponseAdd(
      rows,
      "refresh-health",
      "Refresh payload health",
      requiredFailures.length ? "Blocked" : failures.length ? "Review" : "Ready",
      `required failures=${requiredFailures.length}; supporting failures=${Math.max(0, failures.length - requiredFailures.length)}`,
      requiredFailures.length
        ? "Refresh again, then inspect failed backend read(s) before trusting any WebView panel."
        : failures.length
          ? "Use the failed panel names as read-first context before unattended work."
          : "All loaded refresh payloads needed by Diagnostics are available.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "close-active-work",
      "Close readiness / active work",
      closeBlocked ? "Review" : closeSafe ? "Ready" : "Read evidence",
      `close=${payload.closeReadiness ? (closeSafe ? "safe" : "not safe") : "unknown"}; state=${snapshotState}; reason=${payload.closeReadiness?.reason || "none"}`,
      closeBlocked
        ? "Do not close or start competing work until progress, Last Stderr, and Run Logs agree."
        : closeSafe
          ? "Close-readiness is not blocking; continue with state/log checks if another page looks wrong."
          : "Wait for close-readiness or inspect runtime logs before treating the session as idle.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "activejobs-progress",
      "ActiveJobs / progress",
      activeJobBlocked ? "Review" : activeJobReview ? "Review" : activeRows.length ? "Read evidence" : "Ready",
      `active-job rows=${activeRows.length}; review=${activeJobBlocked + activeJobReview}; pipeline state=${snapshotState}`,
      activeJobBlocked
        ? "Select the malformed/orphaned ActiveJobs row, then read Last Stderr and Run Logs for lifecycle evidence."
        : activeJobReview
          ? "Inspect ActiveJobs detail as passive diagnostics and use progress freshness for lifecycle decisions."
          : activeRows.length
            ? "Use ActiveJobs as passive launch diagnostics only; Completed/Pending still prove output state."
            : "No structured ActiveJobs rows are loaded.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "state-artifacts",
      "State artifacts / read order",
      stateIssues.some((item) => String(diagnosticsStateOperatorStatus(item)).toLowerCase() === "blocked") ? "Blocked review" : stateIssues.length ? "Review" : "Ready",
      `state artifact issues=${stateIssues.length}; read-order rows=${Array.isArray(payload.stateSummary?.triage) ? payload.stateSummary.triage.length : 0}`,
      stateIssues.length
        ? "Use State Artifact Summary and Backend Read Order before rerun, drain, cleanup, or shutdown decisions."
        : "No state artifact blocker is visible; keep using page-specific evidence for workflow decisions.",
    );

    const dependencyContext = {
      settings: payload.settings || {},
      stateSummary: payload.stateSummary || {},
      maintenance: payload.maintenance || window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
    };
    const dependencyStatus = typeof window.externalDependencyOverallStatus === "function"
      ? window.externalDependencyOverallStatus(dependencyContext)
      : (stateIssues.length ? "review" : "unknown");
    const dependencyEvidence = typeof window.externalDependencyEvidenceText === "function"
      ? window.externalDependencyEvidenceText(dependencyContext)
      : `settings dependency issue rows=${stateIssues.length}; maintenance evidence=not loaded`;
    diagnosticsFirstResponseAdd(
      rows,
      "external-dependencies",
      "External dependency readiness",
      dependencyStatus === "blocked" ? "Blocked review" : dependencyStatus === "ready" ? "Ready" : "Review",
      dependencyEvidence,
      dependencyStatus === "blocked"
        ? "Resolve blocked Settings OCR or Maintenance toolchain evidence before rerun, launch, package, or manual-review decisions."
        : dependencyStatus === "ready"
          ? "Loaded Settings OCR and Maintenance toolchain evidence has no visible blocker; still validate real media output separately."
          : "Open Settings > Media Output for OCR evidence or Maintenance > Environment Health for toolchain evidence before long unattended processing.",
    );

    const policyHandoff = diagnosticsSamplePolicyReconciliation(payload);
    diagnosticsFirstResponseAdd(
      rows,
      "sample-policy-reconciliation",
      "Sample Validation policy reconciliation",
      policyHandoff.posture,
      policyHandoff.evidence,
      policyHandoff.action,
    );

    diagnosticsFirstResponseAdd(
      rows,
      "command-issues",
      "Recent command issues",
      commandIssues.length ? "Review" : "Ready",
      `warning/error command rows=${commandIssues.length}`,
      commandIssues.length
        ? "Open Command Result Drilldown and Command Failure Resolution before repeating the owning command."
        : "No warning/error command result is visible in the loaded command history.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "owning-pages",
      "Owning page handoff",
      crossPageConflicts.some((row) => row.severity === "blocked") ? "Blocked review" : crossPageConflicts.length || reviewRows ? "Review" : "Ready",
      `Queue=${queueReviews.length}; Completed=${completedReviews.length}; Pending=${pendingReviews.length}; cross-page conflicts=${crossPageConflicts.length}`,
      crossPageConflicts.length || reviewRows
        ? "Use Owning Page Evidence Handoff, then return to Queue/Completed/Pending before launch, rerun, drain, cleanup, or acceptance."
        : "No owning-page review rows are visible in the loaded Queue/Completed/Pending payloads.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "logs-malformed",
      "Logs and malformed-state clues",
      severityCounts.error || malformedLines.length ? "Review" : severityCounts.warning ? "Read evidence" : "Ready",
      `log severity=${diagnosticsFormatCounts(severityCounts)}; malformed/stale clues=${malformedLines.length}`,
      severityCounts.error || malformedLines.length
        ? "Read bounded Last Stderr or the matching artifact before trusting idle/ready-looking UI state."
        : severityCounts.warning
          ? "Read the warning log row if it relates to the workflow you are about to repeat."
          : "No warning/error log clue is visible in the loaded diagnostics text.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "decision-boundary",
      "Decision boundary",
      "Ready - read-only",
      "Diagnostics first response is evidence only.",
      "Return to the owning page for backend-owned launch, drain, rename, save, rerun, cleanup, or publish actions.",
    );

    return rows;
  }

  function diagnosticsFirstResponseStatus(context = {}) {
    const rows = diagnosticsFirstResponseRows(context);
    if (rows.some((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "blocked")) return "Do not proceed";
    if (rows.some((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "warning")) return "Review first";
    if (rows.some((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "changed")) return "Read evidence";
    return rows.length ? "Ready-looking" : "Not loaded";
  }

  function diagnosticsFirstResponseSummaryLines(context = {}) {
    const rows = diagnosticsFirstResponseRows(context);
    const counts = rows.reduce((acc, row) => {
      const status = diagnosticsFirstResponsePostureStatus(row.posture);
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});
    const first = rows.find((row) => ["blocked", "warning"].includes(diagnosticsFirstResponsePostureStatus(row.posture)))
      || rows.find((row) => diagnosticsFirstResponsePostureStatus(row.posture) === "changed")
      || rows[0];
    const lines = [
      "Diagnostics first-response checklist:",
      `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.warning || 0}; read-first=${counts.changed || 0}; ready=${counts.match || 0}.`,
      "Purpose: pick the first evidence surface to inspect before launch, drain, rerun, cleanup, shutdown, rename, settings save, or publish decisions.",
    ];
    if (first) {
      lines.push(`First action: ${first.step} - ${first.action}`);
    } else {
      lines.push("First action: refresh Diagnostics; no first-response evidence is loaded.");
    }
    lines.push("Read order: bounded text first, backend-selected artifact opens next, owning page before any mutation command.");
    lines.push("Mutation guardrail: this checklist cannot launch, drain, save, rename, repair, delete, publish, clear state, or touch files.");
    return lines;
  }

  function selectedDiagnosticsFirstResponseRow(rows = []) {
    if (!selectedDiagnosticsFirstResponseKey) return null;
    return (Array.isArray(rows) ? rows : []).find((row) => row.key === selectedDiagnosticsFirstResponseKey) || null;
  }

  function diagnosticsFirstResponseDetailLines(row, context = {}) {
    if (!row) {
      return [
        "No diagnostics first-response row selected.",
        "Select a row to inspect the evidence, the owning surface, and the safe next step before repeating any command.",
        "Mutation guardrail: first-response detail is read-only and cannot launch, drain, save, rename, repair, publish, clear state, or touch media.",
      ];
    }
    const payload = context || {};
    const diagnostics = payload.diagnostics || {};
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const failures = Array.isArray(payload.failures) ? payload.failures : [];
    const activeRows = Array.isArray(diagnostics.active_job_rows) ? diagnostics.active_job_rows : [];
    const malformedLines = diagnosticsMalformedStateLines([
      ...diagnosticsTextLines(diagnostics.recent_errors),
      ...diagnosticsTextLines(diagnostics.warnings),
      ...diagnosticsTextLines(diagnostics.active_jobs),
      ...diagnosticsTextLines(diagnostics.log_tail).slice(-20),
      ...diagnosticsTextLines(diagnostics.launch_logs).slice(-20),
    ]);
    const severityCounts = diagnosticsLogRows(diagnostics).reduce((acc, item) => {
      const key = item.severity || "info";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const lines = [
      `First-response step: ${row.step}`,
      `Posture: ${row.posture}`,
      `Evidence: ${row.evidence}`,
      `Safe next step: ${row.action}`,
      "",
    ];

    if (row.key === "refresh-health") {
      const requiredFailures = failures.filter((failure) => failure.required);
      lines.push(
        "Why this gate matters: every downstream Diagnostics row depends on the refresh payload being coherent.",
        `Required refresh failures: ${requiredFailures.length}`,
        `Supporting refresh failures: ${Math.max(0, failures.length - requiredFailures.length)}`,
      );
      if (failures.length) {
        lines.push("Refresh failure sample:");
        failures.slice(0, 6).forEach((failure) => lines.push(`- ${failure.name || "refresh"}: ${failure.message || "failed"}${failure.required ? " (required)" : ""}`));
      }
    } else if (row.key === "close-active-work") {
      lines.push(
        "Why this gate matters: close-readiness owns process lifecycle safety before shutdown, relaunch, role changes, or competing work.",
        `Close readiness safe: ${payload.closeReadiness?.safe_to_close === true ? "yes" : payload.closeReadiness?.safe_to_close === false ? "no" : "unknown"}`,
        `Close reason: ${payload.closeReadiness?.reason || payload.closeReadiness?.state || "not loaded"}`,
        `Snapshot state: ${payload.snapshot?.pipeline_state || payload.snapshot?.state || "not loaded"}`,
      );
    } else if (row.key === "activejobs-progress") {
      const blocked = activeRows.filter((item) => activeJobRowPosture(item) === "blocked").length;
      const review = activeRows.filter((item) => activeJobRowPosture(item) === "warning").length;
      lines.push(
        "Why this gate matters: ActiveJobs and progress prove process lifecycle only; they do not prove output correctness.",
        `ActiveJob rows: ${activeRows.length}`,
        `Blocked rows: ${blocked}`,
        `Active/review rows: ${review}`,
      );
      activeRows.slice(0, 5).forEach((item) => lines.push(`- ${item.record_file || item.launch_id || "active job"}: ${item.status || "unknown"}; ${item.issue || item.current_stage || item.job_kind || "no issue text"}`));
    } else if (row.key === "state-artifacts") {
      lines.push(
        "Why this gate matters: malformed, stale, or missing state can make ready-looking tables lie.",
        `State artifact issue rows: ${stateIssues.length}`,
        `Backend read-order rows: ${Array.isArray(payload.stateSummary?.triage) ? payload.stateSummary.triage.length : 0}`,
      );
      stateIssues.slice(0, 6).forEach((item) => {
        const status = diagnosticsStateOperatorStatus(item) || "review";
        lines.push(`- ${item.label || item.target || "artifact"}: ${status}; ${item.operator_guidance || item.error || item.warning || "review required"}`);
      });
    } else if (row.key === "external-dependencies") {
      lines.push(
        "Why this gate matters: OCR/toolchain/raw-key blockers can make reruns fail even when queue and output state look coherent.",
        "Primary owner: Settings for saved OCR/raw-key evidence; Maintenance for runtime toolchain evidence.",
      );
      if (typeof window.externalDependencySummaryLines === "function") {
        lines.push(...window.externalDependencySummaryLines({
          settings: payload.settings || {},
          stateSummary: payload.stateSummary || {},
          maintenance: payload.maintenance || window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
        }).slice(0, 10));
      } else {
        lines.push("External dependency digest helper is not loaded; open Settings and Maintenance for current evidence.");
      }
    } else if (row.key === "sample-policy-reconciliation") {
      const handoff = diagnosticsSamplePolicyReconciliation(payload);
      lines.push(
        "Why this gate matters: accepted Sample Validation evidence should not look current when saved route/size/subtitle/audio/publish policy is missing, blocked, or not visibly reconciled with the selected Completed output.",
        `Saved policy alignment: ${handoff.policy.operator_status || "not loaded"}`,
        `Policy rows loaded: ${handoff.policyRows.length}`,
        `Completed saved-policy reconciliation: ${handoff.completedPolicyStatus}`,
        `Completed reconciliation posture: ${handoff.completedPolicyRow?.posture || "not loaded"}`,
        `Completed reconciliation evidence: ${handoff.completedPolicyRow?.evidence || "not loaded"}`,
        "Read order: Home > Sample Validation Completed Evidence Handoff -> Completed > Selected Pilot Evidence Packet > Saved policy reconciliation -> Settings media policy -> manual playback/subtitle/audio/size checks.",
        "Owner pages: Home owns Preview/Append evidence; Completed owns post-run output proof; Settings owns saved policy."
      );
      if (Array.isArray(handoff.completedPolicyRow?.detail) && handoff.completedPolicyRow.detail.length) {
        lines.push("Saved-policy reconciliation detail sample:");
        handoff.completedPolicyRow.detail.slice(0, 8).forEach((line) => lines.push(`- ${line}`));
      }
    } else if (row.key === "command-issues") {
      lines.push(
        "Why this gate matters: repeating a failed command without owner-page context can duplicate work or hide the real blocker.",
        `Warning/error command rows: ${commandIssues.length}`,
      );
      commandIssues.slice(0, 6).forEach((entry) => {
        const owner = typeof commandHistoryView.commandHistoryOwnerPage === "function" ? commandHistoryView.commandHistoryOwnerPage(entry) : "Diagnostics";
        const issue = typeof commandHistoryView.commandHistoryIssueLevel === "function" ? commandHistoryView.commandHistoryIssueLevel(entry) : entry.severity || "review";
        lines.push(`- ${owner}: ${entry.command || "command"}; issue=${issue}; ${entry.message || ""}`);
      });
    } else if (row.key === "owning-pages") {
      lines.push(
        "Why this gate matters: Diagnostics should route decisions back to the owning page instead of becoming a repair surface.",
        `Queue review rows: ${queueReviews.length}`,
        `Completed review rows: ${completedReviews.length}`,
        `Pending Publish review rows: ${pendingReviews.length}`,
        `Cross-page conflicts: ${crossPageConflicts.length}`,
      );
      crossPageConflicts.slice(0, 5).forEach((item) => lines.push(`- ${item.owner || item.page || "owner"}: ${item.reason || item.signal || item.severity || "review"}`));
    } else if (row.key === "logs-malformed") {
      lines.push(
        "Why this gate matters: stderr/log/state text often contains the fastest explanation for subprocess, ffprobe, publish, lock, and malformed-state failures.",
        `Log severity counts: ${diagnosticsFormatCounts(severityCounts)}`,
        `Malformed/stale clue count: ${malformedLines.length}`,
      );
      malformedLines.slice(0, 8).forEach((line) => lines.push(`- ${line}`));
    } else if (row.key === "decision-boundary") {
      lines.push(
        "Why this gate matters: Diagnostics is evidence and navigation, not workflow ownership.",
        "Return to Queue for launch scope, Completed for output trust/rerun decisions, Pending Publish for drain posture, Settings for config persistence, Rename for file rename transactions, and Maintenance for dry-run package/backfill checks.",
      );
    }

    lines.push(
      "",
      "Read order: bounded text first, backend-selected artifact opens next, owning page before any mutation command.",
      "Mutation guardrail: this detail cannot launch, drain, save, rename, repair, delete, publish, clear state, open arbitrary paths, rewrite manifests, or touch source/output/scratch media.",
    );
    return lines;
  }

  function renderDiagnosticsFirstResponse(context = {}) {
    const payload = context || {};
    const rows = diagnosticsFirstResponseRows(payload);
    const status = diagnosticsFirstResponseStatus(payload);
    const state = status === "Do not proceed"
      ? "blocked"
      : status === "Review first"
        ? "warning"
        : status === "Read evidence"
          ? "changed"
          : status === "Ready-looking"
            ? "ready"
            : "unknown";
    setDiagnosticsPanelStatus("diagnostics-first-response-status", status, state);
    setText("diagnostics-first-response-summary", diagnosticsFirstResponseSummaryLines(payload).join("\n"));
    const tbody = byId("diagnostics-first-response-rows");
    if (!tbody) return;
    if (!rows.length) {
      selectedDiagnosticsFirstResponseKey = "";
      clearRows(tbody, 4, "No diagnostics first-response rows loaded.");
      updateTableStatusLegend("diagnostics-first-response-legend", tbody, "Diagnostics first-response rows");
      setText("diagnostics-first-response-detail", diagnosticsFirstResponseDetailLines(null, payload).join("\n"));
      return;
    }
    if (!rows.some((row) => row.key === selectedDiagnosticsFirstResponseKey)) {
      selectedDiagnosticsFirstResponseKey = rows[0].key;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.rowKey = item.key;
      row.dataset.status = diagnosticsFirstResponsePostureStatus(item.posture);
      appendCells(row, [item.step || "", item.posture || "", item.evidence || "", item.action || ""]);
      makeRowSelectable(row, () => {
        selectedDiagnosticsFirstResponseKey = item.key;
        renderDiagnosticsFirstResponse(payload);
      }, {
        selected: item.key === selectedDiagnosticsFirstResponseKey,
        label: `Diagnostics first-response ${item.step || item.key}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-first-response-legend", tbody, "Diagnostics first-response rows");
    setText("diagnostics-first-response-detail", diagnosticsFirstResponseDetailLines(selectedDiagnosticsFirstResponseRow(rows), payload).join("\n"));
  }

  function diagnosticsInvestigationTrailLines(context) {
    const payload = context || {};
    const diagnostics = payload.diagnostics || {};
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const failures = Array.isArray(payload.failures) ? payload.failures : [];
    const allLines = [
      ...diagnosticsTextLines(diagnostics.recent_errors),
      ...diagnosticsTextLines(diagnostics.warnings),
      ...diagnosticsTextLines(diagnostics.active_jobs),
      ...diagnosticsTextLines(diagnostics.log_tail).slice(-20),
      ...diagnosticsTextLines(diagnostics.launch_logs).slice(-20),
    ];
    const malformedLines = diagnosticsMalformedStateLines(allLines).slice(0, 5);
    const closeState = String(payload.closeReadiness?.state || "").trim() || "unknown";
    const lines = [
      "Diagnostics investigation trail:",
      `Overall status: ${diagnosticsInvestigationStatus(payload)}`,
      `Close readiness: ${closeState}${payload.closeReadiness?.reason ? ` - ${payload.closeReadiness.reason}` : ""}`,
      `Refresh failures: ${failures.length}${failures.some((failure) => failure.required) ? " (required failure present)" : ""}`,
      `State artifact issues: ${stateIssues.length}`,
      `Recent command issues: ${commandIssues.length}`,
      `Cross-page conflict rows: ${crossPageConflicts.length}`,
      `Page review rows: queue=${queueReviews.length}; completed=${completedReviews.length}; pending=${pendingReviews.length}`,
      `Diagnostics severity groups: ${diagnosticsFormatCounts((diagnosticsLogRows(diagnostics) || []).reduce((acc, row) => {
        const key = row.severity || "info";
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {}))}`,
    ];
    lines.push("", ...diagnosticsRealMediaBoundaryLines());
    lines.push("");
    if (failures.length) {
      lines.push("Refresh/API issue(s):");
      failures.slice(0, 5).forEach((failure) => lines.push(`- ${failure.name || "refresh"}: ${failure.message || "failed"}${failure.required ? " (required)" : ""}`));
    }
    if (stateIssues.length) {
      lines.push("", "State artifact issue(s) to inspect first:");
      stateIssues.slice(0, 5).forEach((item) => {
        const status = diagnosticsStateOperatorStatus(item) || "review";
        const action = diagnosticsStateRecommendedFirstAction(item);
        lines.push(`- ${item.label || item.target || "artifact"}: ${status}; ${item.operator_guidance || item.error || item.warning || "review required"}; first action: ${action}`);
      });
    }
    if (commandIssues.length) {
      lines.push("", "Recent command issue(s):");
      commandIssues.slice(0, 5).forEach((entry) => {
        const owner = typeof commandHistoryView.commandHistoryOwnerPage === "function" ? commandHistoryView.commandHistoryOwnerPage(entry) : "Diagnostics";
        const action = typeof commandHistoryView.commandHistorySuggestedAction === "function" ? commandHistoryView.commandHistorySuggestedAction(entry) : "inspect command details and diagnostics.";
        lines.push(`- ${entry.command || entry.raw?.command || "command"} (${owner}): ${entry.message || entry.result || "issue"}; next: ${action}`);
      });
    }
    if (pendingReviews.length || queueReviews.length || completedReviews.length) {
      lines.push("", "Cross-page row review(s):");
      pendingReviews.slice(0, 3).forEach(({ row, reasons }) => lines.push(`- Pending: ${row.local_file || row.server_out || row.manifest_path || "row"} - ${(reasons || []).slice(0, 2).join("; ") || "review"}; ${row.safe_next_action || row.operator_guidance || "build a recovery dry-run before drain."}`));
      queueReviews.slice(0, 3).forEach(({ row, reasons }) => lines.push(`- Queue: ${row.display_name || row.relative_path || row.source_path || "row"} - ${(reasons || []).slice(0, 2).join("; ") || "review"}; ${row.safe_next_action || row.operator_guidance || "use queue diagnostics before launch."}`));
      completedReviews.slice(0, 3).forEach(({ row, reasons }) => lines.push(`- Completed: ${row.lookup_title || row.output_file || row.output_path || "row"} - ${(reasons || []).slice(0, 2).join("; ") || "review"}; ${row.safe_next_action || row.operator_guidance || "compare manifest/output proof before rerun."}`));
    }
    if (crossPageConflicts.length) {
      lines.push("", "Cross-page conflict handoff(s):");
      crossPageConflicts.slice(0, 5).forEach((item) => {
        const confidence = item.confidence === "same-leaf-review" ? "advisory filename-only" : "exact path";
        lines.push(`- ${diagnosticsConflictSignalLabel(item)} (${confidence}; ${item.severity || "review"}): ${item.evidence || "review loaded Queue/Completed/Pending payloads"}; ${item.action || "review owning pages before action."}`);
      });
    }
    if (malformedLines.length) {
      lines.push("", "Malformed/stale clue(s):");
      malformedLines.forEach((line) => lines.push(`- ${line}`));
    }
    lines.push("");
    if (stateIssues.length || commandIssues.length || crossPageConflicts.length || pendingReviews.length || queueReviews.length || completedReviews.length || malformedLines.length || failures.length) {
      lines.push("Recommended order: read bounded text first, inspect backend-selected artifacts next, then return to the owning page before any launch, drain, rerun, cleanup, or close decision.");
    } else {
      lines.push("Recommended order: no immediate blockers are visible. If pages still disagree, start with State Artifact Summary, then Run Logs, then the owning page.");
    }
    lines.push("Mutation guardrail: this trail is read-only; it does not repair, clear, drain, launch, rerun, delete, rewrite, move, or publish files.");
    return lines;
  }

  function renderDiagnosticsInvestigationActions(context) {
    const container = byId("diagnostics-investigation-actions");
    if (!container) return;
    container.replaceChildren();
    const groups = diagnosticsActionGroups(diagnosticsInvestigationActions(context || {}));
    appendDiagnosticsActionGroup(container, "Read first", groups.readFirst);
    appendDiagnosticsActionGroup(container, "Open next", groups.openNext);
  }

  function renderDiagnosticsInvestigationTrail(context = {}) {
    const status = diagnosticsInvestigationStatus(context || {});
    setDiagnosticsPanelStatus("diagnostics-investigation-status", status);
    setText("diagnostics-investigation-trail", diagnosticsInvestigationTrailLines(context || {}).join("\n"));
    renderDiagnosticsInvestigationActions(context || {});
  }

    return {
      diagnosticsFirstResponsePostureStatus,
      diagnosticsSamplePolicyReconciliation,
      diagnosticsFirstResponseRows,
      diagnosticsFirstResponseStatus,
      diagnosticsFirstResponseSummaryLines,
      selectedDiagnosticsFirstResponseRow,
      diagnosticsFirstResponseDetailLines,
      renderDiagnosticsFirstResponse,
      diagnosticsInvestigationTrailLines,
      renderDiagnosticsInvestigationActions,
      renderDiagnosticsInvestigationTrail,    };
  }

  window.__diagnosticsFirstResponseModule = {
    createDiagnosticsFirstResponseModule,
  };
})();