(function () {
  function createDiagnosticsInvestigationModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const makeRowSelectable = deps.makeRowSelectable || function () {};
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const diagnosticsActionGroups = deps.diagnosticsActionGroups || function () { return { readFirst: [], openNext: [] }; };
    const diagnosticsMalformedStateLines = deps.diagnosticsMalformedStateLines || function () { return []; };
    const diagnosticsOrderedActions = deps.diagnosticsOrderedActions || function (actions) { return Array.isArray(actions) ? actions : []; };
    const diagnosticsSafeRows = deps.diagnosticsSafeRows || function () { return []; };
    const diagnosticsSamplePolicyReconciliation = deps.diagnosticsSamplePolicyReconciliation || function () { return {}; };
    const diagnosticsTextLines = deps.diagnosticsTextLines || function () { return []; };
    const appendDiagnosticsActionGroup = deps.appendDiagnosticsActionGroup || function () {};

    let lastDiagnosticsOwnerHandoffRows = [];
    let selectedDiagnosticsOwnerHandoffKey = "";

  function diagnosticsStateIssueRows(stateSummary) {
    const rows = diagnosticsSafeRows(stateSummary);
    const diagnosticsStateSummaryView = window.mediaPipelineDiagnosticsStateSummaryView || {};
    const diagnosticsStateOperatorStatus = diagnosticsStateSummaryView.diagnosticsStateOperatorStatus || function (item) {
      return String(item?.operator_status || item?.status || "");
    };
    return rows.filter((item) => {
      const status = diagnosticsStateOperatorStatus(item);
      const normalized = String(status || "").toLowerCase();
      const warnings = Array.isArray(item?.warnings) ? item.warnings.filter(Boolean) : [];
      const errors = Array.isArray(item?.errors) ? item.errors.filter(Boolean) : [];
      return (
        errors.length ||
        warnings.length ||
        ["blocked", "review", "unavailable", "unknown", "missing", "stale", "malformed", "unreadable"].some((token) => normalized.includes(token))
      );
    });
  }

  function diagnosticsPageReviewRows(name, payload) {
    const rows = diagnosticsSafeRows(payload);
    if (name === "queue" && typeof window.queueReviewRows === "function") return window.queueReviewRows(payload || {}, rows);
    if (name === "completed" && typeof window.completedReviewRows === "function") return window.completedReviewRows(payload || {}, rows);
    if (name === "pending" && typeof window.pendingReviewRows === "function") return window.pendingReviewRows(payload || {}, rows);
    return [];
  }

  function diagnosticsCrossPageConflictRows(context) {
    if (typeof window.crossPageConflictRows !== "function") return [];
    return window.crossPageConflictRows({
      queue: context?.queue || {},
      completed: context?.completed || {},
      pending: context?.pending || {},
      diagnostics: context?.diagnostics || {},
      failures: context?.failures || [],
    });
  }

  function diagnosticsConflictSignalLabel(item) {
    if (typeof window.crossPageConflictSignalLabel === "function") {
      return window.crossPageConflictSignalLabel(item?.signal);
    }
    return String(item?.signal || "cross-page conflict");
  }

  function diagnosticsCommandIssueRows(commandPayload) {
    const entries = Array.isArray(commandPayload?.entries) ? commandPayload.entries : (typeof getCommandHistory === "function" ? getCommandHistory() : []);
    if (typeof window.commandHistoryIssueEntries === "function") return window.commandHistoryIssueEntries(entries);
    return entries.filter((entry) => entry && entry.ok === false);
  }

  function diagnosticsInvestigationAddAction(actions, seen, kind, target, label, hint) {
    const normalizedTarget = String(target || "").trim();
    if (!normalizedTarget) return;
    const key = `${kind}:${normalizedTarget}`;
    if (seen.has(key)) return;
    seen.add(key);
    actions.push({ kind, target: normalizedTarget, label, hint: hint || "" });
  }

  function diagnosticsInvestigationActions(context) {
    const payload = context || {};
    const actions = [];
    const seen = new Set();
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const diagnostics = payload.diagnostics || {};
    const allLines = [
      ...diagnosticsTextLines(diagnostics.recent_errors),
      ...diagnosticsTextLines(diagnostics.warnings),
      ...diagnosticsTextLines(diagnostics.log_tail).slice(-20),
      ...diagnosticsTextLines(diagnostics.launch_logs).slice(-20),
    ];
    const malformedLines = diagnosticsMalformedStateLines(allLines);

    if (stateIssues.length) {
      stateIssues.slice(0, 3).forEach((item) => {
        diagnosticsInvestigationAddAction(actions, seen, "tail", item.recommended_tail_target, `Read ${String(item.recommended_tail_target || "").replaceAll("_", " ")}`, "State Artifact Summary recommends this bounded read.");
        diagnosticsInvestigationAddAction(actions, seen, "open", item.recommended_open_target, `Open ${String(item.recommended_open_target || "").replaceAll("_", " ")}`, "State Artifact Summary recommends this backend-selected open target.");
      });
    }
    if (pendingReviews.length) {
      diagnosticsInvestigationAddAction(actions, seen, "tail", "last_stderr_log", "Read Last Stderr", "Pending Publish review rows often need the latest drain/copy/process stderr first.");
      diagnosticsInvestigationAddAction(actions, seen, "open", "pending_publish", "Open Pending Publish", "Inspect parked manifests, payloads, sidecars, and recovery context.");
    }
    if (queueReviews.length) {
      diagnosticsInvestigationAddAction(actions, seen, "tail", "queue_snapshot", "Read Queue Snapshot", "Queue review rows should be compared against backend-authored queue state.");
      diagnosticsInvestigationAddAction(actions, seen, "open", "active_jobs", "Open ActiveJobs", "Check live/stale process records before launch or rerun decisions.");
    }
    if (completedReviews.length) {
      diagnosticsInvestigationAddAction(actions, seen, "tail", "latest_failure_report", "Read Latest Failure", "Completed review rows may need recent failure proof before rerun/cleanup.");
      diagnosticsInvestigationAddAction(actions, seen, "open", "completed_manifest", "Open Completed Manifest", "Compare completed manifest evidence with output/sidecar state.");
    }
    if (crossPageConflicts.length) {
      diagnosticsInvestigationAddAction(actions, seen, "tail", "last_stderr_log", "Read Last Stderr", "Cross-page conflicts should be compared against recent process stderr before action.");
      diagnosticsInvestigationAddAction(actions, seen, "tail", "queue_snapshot", "Read Queue Snapshot", "Cross-page conflicts include queue source evidence.");
      diagnosticsInvestigationAddAction(actions, seen, "open", "completed_manifest", "Open Completed Manifest", "Cross-page conflicts include completed manifest evidence.");
      diagnosticsInvestigationAddAction(actions, seen, "open", "pending_publish", "Open Pending Publish", "Cross-page conflicts include parked publish evidence.");
    }
    if (commandIssues.length || malformedLines.length) {
      diagnosticsInvestigationAddAction(actions, seen, "tail", "last_stderr_log", "Read Last Stderr", "Command failures or malformed-state clues usually have bounded stderr evidence.");
      diagnosticsInvestigationAddAction(actions, seen, "open", "run_logs", "Open Run Logs", "Open run logs only after reading bounded text or when additional launch context is needed.");
    }
    if (!actions.length) {
      diagnosticsInvestigationAddAction(actions, seen, "open", "state", "Open State Folder", "Fallback backend-selected state location for cross-page disagreements.");
      diagnosticsInvestigationAddAction(actions, seen, "open", "run_logs", "Open Run Logs", "Fallback backend-selected log location when no specific clue is available.");
    }
    return diagnosticsOrderedActions(actions).slice(0, 8);
  }

  function diagnosticsInvestigationStatus(context) {
    const payload = context || {};
    const stateIssues = diagnosticsStateIssueRows(payload.stateSummary);
    const commandIssues = diagnosticsCommandIssueRows(payload.commands);
    const pendingReviews = diagnosticsPageReviewRows("pending", payload.pending);
    const queueReviews = diagnosticsPageReviewRows("queue", payload.queue);
    const completedReviews = diagnosticsPageReviewRows("completed", payload.completed);
    const crossPageConflicts = diagnosticsCrossPageConflictRows(payload);
    const failures = Array.isArray(payload.failures) ? payload.failures : [];
    const closeState = String(payload.closeReadiness?.state || "").toLowerCase();
    if (failures.some((failure) => failure.required)) return "Refresh failure";
    if (closeState && closeState !== "safe") return "Close blocked";
    if (crossPageConflicts.some((row) => row.severity === "blocked")) return "Cross-page blocked";
    if (stateIssues.length) return `${stateIssues.length} artifact issue${stateIssues.length === 1 ? "" : "s"}`;
    if (commandIssues.length) return `${commandIssues.length} command issue${commandIssues.length === 1 ? "" : "s"}`;
    const reviewCount = pendingReviews.length + queueReviews.length + completedReviews.length;
    if (crossPageConflicts.length) return `${crossPageConflicts.length} cross-page conflict${crossPageConflicts.length === 1 ? "" : "s"}`;
    if (reviewCount) return `${reviewCount} page review row${reviewCount === 1 ? "" : "s"}`;
    return "No blockers";
  }

  function diagnosticsListText(value) {
    return Array.isArray(value) && value.length ? value.filter(Boolean).join(", ") : "none";
  }

  function diagnosticsRowLabel(owner, row, fallbackIndex = 0) {
    if (owner === "Queue") return row?.display_name || row?.relative_path || row?.source_path || `Queue row ${fallbackIndex + 1}`;
    if (owner === "Completed") return row?.lookup_title || row?.output_file || row?.output_path || `Completed row ${fallbackIndex + 1}`;
    if (owner === "Pending Publish") return row?.local_file || row?.server_out || row?.manifest_path || `Pending row ${fallbackIndex + 1}`;
    return row?.row_key || `row ${fallbackIndex + 1}`;
  }

  function diagnosticsOwnerDefaultAction(owner) {
    if (owner === "Queue") return "Go to Queue, select this row, read Queue detail, then use Queue Diagnostics Cross-Links before launch.";
    if (owner === "Completed") return "Go to Completed, select this row, compare manifest/output proof, then decide whether rerun or cleanup is safe.";
    if (owner === "Pending Publish") return "Go to Pending Publish, select this row, build recovery/drain evidence, then decide whether draining is safe.";
    return "Return to the owning page before taking action.";
  }

  function diagnosticsOwnerRowSeverity(owner, row, reasons) {
    const text = [
      row?.operator_severity,
      row?.diagnostic_severity,
      row?.drain_recommendation,
      row?.blocked_reason,
      row?.blocked_reason_code,
      ...(Array.isArray(reasons) ? reasons : []),
    ].join(" ").toLowerCase();
    if (/\b(error|blocked|do_not_drain|missing output|missing sidecar|invalid|failed|failure|locked)\b/.test(text)) return "blocked";
    if (/\b(warn|warning|review|deferred|stale|unknown|size growth|consistency)\b/.test(text)) return "warning";
    return "review";
  }

  function diagnosticsOwnerHandoffRowKey(item) {
    const row = item?.row || {};
    return [
      item?.owner || "",
      row.row_key || "",
      row.display_name || row.lookup_title || row.output_file || row.local_file || row.server_out || row.source_path || row.output_path || "",
      (item?.reasons || []).join("|"),
    ].join("\u001f").toLowerCase();
  }

  function diagnosticsCompletedFinalTrustStepForRow(row, reasons = []) {
    const issueText = [
      row?.operator_trust_state,
      row?.operator_severity,
      row?.diagnostic_severity,
      row?.output_health,
      row?.consistency_status,
      row?.runtime_outcome_status,
      row?.runtime_outcome_error_code,
      row?.runtime_outcome_reason,
      row?.publish_state,
      row?.route,
      row?.route_label,
      row?.route_decision_summary,
      row?.route_reason,
      row?.route_reason_code,
      row?.size_delta_label,
      row?.size_reduction_text,
      row?.size_policy_status,
      ...(Array.isArray(row?.consistency_issues) ? row.consistency_issues : []),
      ...(Array.isArray(reasons) ? reasons : []),
    ].join(" ").toLowerCase();
    const outputMissing = row?.output_exists === false
      || /\b(missing[_ -]?output|output missing|missing file|broken-output)\b/.test(issueText);
    const sidecarMissing = row?.sidecar_exists === false
      || /\b(missing[_ -]?sidecar|sidecar missing|sidecar-output-mismatch|stale sidecar)\b/.test(issueText);
    if (outputMissing || sidecarMissing) {
      return {
        step: "2. Output and sidecar on disk",
        reason: outputMissing && sidecarMissing
          ? "Completed reports missing output and sidecar proof."
          : outputMissing
            ? "Completed reports missing output proof."
            : "Completed reports sidecar proof that needs review.",
        readFirst: "Completed Manifest -> output folder -> sidecar -> Run Logs -> Last Stderr",
      };
    }
    if (/\b(pending|publish|published|server push|server_push|drain|deferred|do_not_drain|do-not-drain)\b/.test(issueText)) {
      return {
        step: "3. Pending/drain final placement",
        reason: "Completed evidence is tied to pending publish or drain placement.",
        readFirst: "Completed Manifest -> Pending Publish -> drain summary -> Last Stderr",
      };
    }
    if (
      row?.size_growth_over_5
      || /\b(size growth|size_policy|size policy|route|remux|encode|encoder|plex|audio|subtitle|compatibility|profile)\b/.test(issueText)
    ) {
      return {
        step: "4. Plex/media policy proof",
        reason: "Completed evidence needs route, size, media, audio, or subtitle policy review.",
        readFirst: "Completed Manifest -> route/size fields -> Settings policy -> Last Stderr",
      };
    }
    if (/\b(runtime|stderr|stdout|log|failure|failed|error|exception|latest_failure|traceback)\b/.test(issueText)) {
      return {
        step: "5. Diagnostics and logs",
        reason: "Completed evidence needs runtime or log correlation before action.",
        readFirst: "Completed Manifest -> Last Stderr -> Run Logs -> Latest Failure",
      };
    }
    if (/\b(sample|validation|acceptance|accepted|playback)\b/.test(issueText)) {
      return {
        step: "6. Sample Validation evidence",
        reason: "Completed evidence is about sample acceptance or manual validation.",
        readFirst: "Completed final trust -> Home Sample Validation preview -> manual playback notes",
      };
    }
    return {
      step: "5. Diagnostics and logs",
      reason: "Completed row needs evidence correlation before action.",
      readFirst: "Completed Manifest -> Last Stderr -> Run Logs",
    };
  }

  function diagnosticsCompletedFinalTrustLines(item) {
    if (item?.owner !== "Completed") return [];
    const step = diagnosticsCompletedFinalTrustStepForRow(item.row || {}, item.reasons || []);
    return [
      "Completed final trust handoff:",
      `Final trust step: ${step.step}`,
      `Why this step: ${step.reason}`,
      `Read first: ${step.readFirst}`,
      "After Go To Owner Row, read Completed > Final Output Trust Walkthrough and select the matching step.",
      "Boundary: Diagnostics points to the owning Completed proof step only; it does not accept, rerun, clean up, drain, rewrite manifests, publish, or touch media.",
    ];
  }

  function diagnosticsCompletedPolicyReconciliationLines(item) {
    if (item?.owner !== "Completed") return [];
    const context = window.mediaPipelineLastCrossPageContext || {};
    const handoff = diagnosticsSamplePolicyReconciliation(context);
    const lines = [
      "Completed saved-policy reconciliation handoff:",
      `Saved policy alignment: ${handoff.policy.operator_status || "not loaded"}`,
      `Completed reconciliation: ${handoff.completedPolicyStatus}`,
      `Completed evidence: ${handoff.completedPolicyRow?.evidence || "not loaded"}`,
      "Read first: Home Sample Validation Completed Evidence Handoff -> Completed Selected Pilot Evidence Packet -> Saved policy reconciliation -> Settings media policy.",
      "After Go To Owner Row, read Completed > Selected Pilot Evidence Packet > Saved policy reconciliation and Settings > media policy before accepting evidence.",
      "Boundary: Diagnostics points to policy evidence only; it does not save settings, append validation records, accept output, rerun, drain, rewrite manifests, publish, or touch media.",
    ];
    if (Array.isArray(handoff.completedPolicyRow?.detail) && handoff.completedPolicyRow.detail.length) {
      lines.push("Saved-policy detail sample:");
      handoff.completedPolicyRow.detail.slice(0, 6).forEach((line) => lines.push(`- ${line}`));
    }
    return lines;
  }

  function diagnosticsOwnerHandoffRows(context = {}) {
    const descriptors = [
      {
        owner: "Queue",
        payload: context.queue || {},
        rows: diagnosticsSafeRows(context.queue),
        getter: window.queueReviewRows,
      },
      {
        owner: "Completed",
        payload: context.completed || {},
        rows: diagnosticsSafeRows(context.completed),
        getter: window.completedReviewRows,
      },
      {
        owner: "Pending Publish",
        payload: context.pending || {},
        rows: diagnosticsSafeRows(context.pending),
        getter: window.pendingReviewRows,
      },
    ];
    return descriptors.flatMap((descriptor) => {
      const getter = typeof descriptor.getter === "function" ? descriptor.getter : null;
      const reviewRows = getter ? getter(descriptor.payload, descriptor.rows) : [];
      return reviewRows.map((entry, index) => {
        const row = entry?.row || {};
        const reasons = Array.isArray(entry?.reasons) ? entry.reasons.filter(Boolean) : [];
        const diagnosticsTargets = Array.isArray(row.recommended_diagnostics_targets) ? row.recommended_diagnostics_targets.filter(Boolean) : [];
        const openTargets = Array.isArray(row.available_open_targets) ? row.available_open_targets.filter(Boolean) : [];
        const safeNextAction = row.safe_next_action || row.operator_guidance || diagnosticsOwnerDefaultAction(descriptor.owner);
        const completedFinalTrust = descriptor.owner === "Completed"
          ? diagnosticsCompletedFinalTrustStepForRow(row, reasons)
          : null;
        return {
          owner: descriptor.owner,
          row,
          index: entry?.index ?? index,
          label: diagnosticsRowLabel(descriptor.owner, row, entry?.index ?? index),
          reasons,
          severity: diagnosticsOwnerRowSeverity(descriptor.owner, row, reasons),
          diagnosticsTargets,
          openTargets,
          safeNextAction,
          completedFinalTrust,
        };
      });
    }).sort((left, right) => {
      const rank = { blocked: 0, warning: 1, review: 2, ready: 3 };
      return (rank[left.severity] ?? 9) - (rank[right.severity] ?? 9)
        || left.owner.localeCompare(right.owner)
        || left.index - right.index;
    });
  }

  function diagnosticsOwnerHandoffStatus(rows = lastDiagnosticsOwnerHandoffRows) {
    const rowList = Array.isArray(rows) ? rows : [];
    const blocked = rowList.filter((item) => item.severity === "blocked").length;
    const warning = rowList.filter((item) => item.severity === "warning").length;
    if (!rowList.length) return "No flagged rows";
    return `${rowList.length} handoff row${rowList.length === 1 ? "" : "s"}; blocked=${blocked}; warning=${warning}`;
  }

  function diagnosticsOwnerHandoffSummaryLines(rows = lastDiagnosticsOwnerHandoffRows) {
    const rowList = Array.isArray(rows) ? rows : [];
    const counts = rowList.reduce((acc, item) => {
      acc[item.owner] = (acc[item.owner] || 0) + 1;
      return acc;
    }, {});
    const first = rowList.find((item) => item.severity === "blocked") || rowList[0];
    const lines = [
      "Owning-page evidence handoff:",
      `Rows: ${rowList.length}; Queue=${counts.Queue || 0}; Completed=${counts.Completed || 0}; Pending Publish=${counts["Pending Publish"] || 0}`,
      "Purpose: Diagnostics explains where evidence lives, but the owning page remains the place to inspect row state before launch, drain, rerun, cleanup, publish, or acceptance decisions.",
    ];
    if (!rowList.length) {
      lines.push("No Queue, Completed, or Pending Publish review rows are visible in the latest refresh payload.");
      lines.push("If another page still looks wrong, refresh once, then inspect State Artifact Summary and Log Triage.");
    } else {
      lines.push(`First handoff: ${first.owner} -> ${first.label}`);
      lines.push(`Reason: ${first.reasons.slice(0, 3).join("; ") || "review required"}`);
      lines.push(`Safe next action: ${first.safeNextAction}`);
      if (first.owner === "Completed" && first.completedFinalTrust?.step) {
        lines.push(`Completed final trust step: ${first.completedFinalTrust.step}`);
      }
    }
    lines.push("Read/open boundary: diagnostics targets are backend allowlist identifiers; row open targets must be triggered from the owning page using row_key plus target only.");
    lines.push("Navigation boundary: Go To Owner Row is local UI selection over the already-loaded payload. It does not POST, open files, or alter backend scope.");
    lines.push("Mutation guardrail: this panel is read-only; it does not launch, rerun, drain, repair, rewrite, move, delete, publish, or touch media files.");
    return lines;
  }

  function diagnosticsHandoffTailTargets() {
    return new Set([
      "last_stderr_log",
      "last_stdout_log",
      "queue_snapshot",
      "completed_manifest",
      "active_jobs",
      "latest_failure_report",
      "latest_failure_json",
      "latest_audit_csv",
      "latest_priority_csv",
      "sample_validation_log",
      "cluster_log",
    ]);
  }

  function diagnosticsOwnerHandoffActions(item) {
    const actions = [];
    const seen = new Set();
    const tailTargets = diagnosticsHandoffTailTargets();
    (Array.isArray(item?.diagnosticsTargets) ? item.diagnosticsTargets : []).forEach((target) => {
      const normalized = String(target || "").trim();
      if (!normalized) return;
      const kind = tailTargets.has(normalized) ? "tail" : "open";
      diagnosticsInvestigationAddAction(
        actions,
        seen,
        kind,
        normalized,
        `${kind === "tail" ? "Read" : "Open"} ${normalized.replaceAll("_", " ")}`,
        `${item.owner} selected-row diagnostics target.`
      );
    });
    if (!actions.length && item?.owner === "Queue") {
      diagnosticsInvestigationAddAction(actions, seen, "tail", "queue_snapshot", "Read Queue Snapshot", "Queue row fallback diagnostics target.");
      diagnosticsInvestigationAddAction(actions, seen, "tail", "last_stderr_log", "Read Last Stderr", "Queue row fallback diagnostics target.");
    } else if (!actions.length && item?.owner === "Completed") {
      diagnosticsInvestigationAddAction(actions, seen, "tail", "completed_manifest", "Read Completed Manifest", "Completed row fallback diagnostics target.");
      diagnosticsInvestigationAddAction(actions, seen, "tail", "last_stderr_log", "Read Last Stderr", "Completed row fallback diagnostics target.");
    } else if (!actions.length && item?.owner === "Pending Publish") {
      diagnosticsInvestigationAddAction(actions, seen, "open", "pending_publish", "Open Pending Publish", "Pending row fallback diagnostics target.");
      diagnosticsInvestigationAddAction(actions, seen, "tail", "last_stderr_log", "Read Last Stderr", "Pending row fallback diagnostics target.");
    }
    return diagnosticsOrderedActions(actions).slice(0, 5);
  }

  function diagnosticsOwnerPageId(owner) {
    if (owner === "Queue") return "queue";
    if (owner === "Completed") return "completed";
    if (owner === "Pending Publish") return "pending";
    return "";
  }

  function diagnosticsOwnerSelectFunction(owner) {
    if (owner === "Queue" && typeof window.selectQueueRow === "function") return window.selectQueueRow;
    if (owner === "Completed" && typeof window.selectCompletedRow === "function") return window.selectCompletedRow;
    if (owner === "Pending Publish" && typeof window.selectPendingRow === "function") return window.selectPendingRow;
    return null;
  }

  function diagnosticsOwnerNavigationLabel(item) {
    const owner = item?.owner || "owning page";
    return `Go To ${owner} Row`;
  }

  function setDiagnosticsOwnerHandoffNavStatus(message) {
    if (typeof setPanelStatus === "function") {
      setPanelStatus("diagnostics-owner-handoff-nav-status", message || "", message ? "changed" : "empty");
    } else {
      setText("diagnostics-owner-handoff-nav-status", message || "");
    }
  }

  function setDiagnosticsOwnerDestinationStatus(pageId, message) {
    const statusIds = {
      queue: "queue-diagnostics-status",
      completed: "completed-diagnostics-status",
      pending: "pending-diagnostics-status",
    };
    const id = statusIds[pageId] || "";
    if (!id) return;
    if (typeof setPanelStatus === "function") {
      setPanelStatus(id, message, "changed");
    } else {
      setText(id, message);
    }
  }

  function navigateDiagnosticsOwnerHandoffRow(item) {
    if (!item) {
      setDiagnosticsOwnerHandoffNavStatus("Select an owning-page handoff row before navigating.");
      return false;
    }
    const pageId = diagnosticsOwnerPageId(item.owner);
    const selectOwnerRow = diagnosticsOwnerSelectFunction(item.owner);
    if (!pageId || typeof window.showPage !== "function" || typeof selectOwnerRow !== "function") {
      setDiagnosticsOwnerHandoffNavStatus(`Cannot navigate to ${item.owner || "owner"} from this WebView session; owner page helpers are not loaded.`);
      return false;
    }
    window.showPage(pageId);
    selectOwnerRow(item.row || null);
    const completedFinalTrustSelected = item.owner === "Completed"
      && item.completedFinalTrust?.step
      && typeof window.selectCompletedFinalTrustStep === "function"
      ? window.selectCompletedFinalTrustStep(item.completedFinalTrust.step)
      : false;
    const completedFinalTrustSuffix = item.owner === "Completed" && item.completedFinalTrust?.step
      ? completedFinalTrustSelected
        ? ` Selected Completed > Final Output Trust Walkthrough step: ${item.completedFinalTrust.step}.`
        : " After navigation, read Completed > Final Output Trust Walkthrough for the mapped proof step."
      : "";
    const message = `Opened ${item.owner} and locally selected row_key=${item.row?.row_key || "not reported"}. No backend command was sent and no file paths were opened.${completedFinalTrustSuffix}`;
    setDiagnosticsOwnerHandoffNavStatus(message);
    setDiagnosticsOwnerDestinationStatus(pageId, `Diagnostics handoff selected this row locally. No backend command was sent.`);
    return true;
  }

  function getSelectedDiagnosticsOwnerHandoffRow() {
    if (!selectedDiagnosticsOwnerHandoffKey) return null;
    return lastDiagnosticsOwnerHandoffRows.find((row) => diagnosticsOwnerHandoffRowKey(row) === selectedDiagnosticsOwnerHandoffKey) || null;
  }

  function selectDiagnosticsOwnerHandoffRow(item) {
    selectedDiagnosticsOwnerHandoffKey = diagnosticsOwnerHandoffRowKey(item);
    renderDiagnosticsOwnerHandoffDetail(item || null);
    renderDiagnosticsOwnerHandoffTable();
  }

  function renderDiagnosticsOwnerHandoffActions(item) {
    const container = byId("diagnostics-owner-handoff-actions");
    if (!container) return;
    container.replaceChildren();
    if (item) {
      const ownerLabel = document.createElement("span");
      ownerLabel.className = "action-group-label";
      ownerLabel.textContent = "Owner page";
      container.appendChild(ownerLabel);
      const ownerButton = document.createElement("button");
      ownerButton.className = "secondary-button";
      ownerButton.type = "button";
      ownerButton.textContent = diagnosticsOwnerNavigationLabel(item);
      ownerButton.dataset.diagnosticsOwnerNavigate = diagnosticsOwnerPageId(item.owner);
      ownerButton.title = "Navigate to the owning page and select this already-loaded row locally. Does not send a backend command.";
      ownerButton.addEventListener("click", () => navigateDiagnosticsOwnerHandoffRow(item));
      container.appendChild(ownerButton);
    }
    const groups = diagnosticsActionGroups(diagnosticsOwnerHandoffActions(item || null));
    appendDiagnosticsActionGroup(container, "Read first", groups.readFirst);
    appendDiagnosticsActionGroup(container, "Open next", groups.openNext);
  }

  function diagnosticsSampleValidationComparisonLines(item) {
    const context = window.mediaPipelineLastCrossPageContext || {};
    const log = context.sampleValidation || {};
    const row = item?.row || {};
    const paths = [
      row.source_path,
      row.output_path,
      row.runtime_outcome_output_path,
      row.server_out,
      row.destination_path,
      row.local_file,
      row.payload_path,
      row.path,
      row.file,
    ].filter(Boolean);
    const matches = typeof window.sampleValidationRecordComparisonRowsForPaths === "function"
      ? window.sampleValidationRecordComparisonRowsForPaths(log, paths, item?.label || row.lookup_title || row.output_file || row.display_name || "")
      : [];
    const summary = log.summary && typeof log.summary === "object" ? log.summary : {};
    const reconciliation = log.reconciliation && typeof log.reconciliation === "object" ? log.reconciliation : {};
    const current = matches.filter((entry) => entry.current_status === "current").length;
    const stale = matches.filter((entry) => entry.current_status === "stale").length;
    const review = matches.filter((entry) => ["review", "not checked", "unknown"].includes(entry.current_status)).length;
    const lines = [
      "Sample Validation context for this Diagnostics handoff:",
      `Loaded records: ${log.record_count || summary.record_count || 0}; matching this owner row: ${matches.length}; current=${current}; stale=${stale}; review/not-checked=${review}.`,
      `Reconciliation: ${reconciliation.operator_status || "not loaded"}; Sample Validation log: ${log.exists === false ? "not started" : log.exists === true ? "loaded" : "not loaded"}.`,
    ];
    if (!matches.length) {
      lines.push("No matching Sample Validation record is loaded for the owning row paths.");
    } else {
      matches.slice(0, 3).forEach((entry) => {
        const gaps = Array.isArray(entry.missing_current_evidence) && entry.missing_current_evidence.length
          ? ` gaps=${entry.missing_current_evidence.join("; ")}`
          : " gaps=none";
        lines.push(`- ${entry.created_at || "unknown time"} ${entry.operator_decision || "unknown decision"} category=${entry.sample_category || "general"} match=${entry.match_strength} current=${entry.current_status || "not checked"}${gaps}`);
      });
    }
    lines.push(
      "Diagnostics next action: use the owning page row plus Home > Sample Validation Preview Record before accepting or rerunning a real-media pilot sample.",
      "Mutation guardrail: Diagnostics comparison is read-only and cannot append validation records, open arbitrary paths, launch, rerun, drain, publish, repair, rewrite, or touch media."
    );
    return lines;
  }

  function renderDiagnosticsOwnerHandoffDetail(item) {
    renderDiagnosticsOwnerHandoffActions(item || null);
    if (!item) {
      setText("diagnostics-owner-handoff-detail", "No owning-page handoff row selected. Select a row to see which owning page should be reviewed before acting.");
      return;
    }
    const row = item.row || {};
    const completedFinalTrustLines = diagnosticsCompletedFinalTrustLines(item);
    const completedPolicyLines = diagnosticsCompletedPolicyReconciliationLines(item);
    setText("diagnostics-owner-handoff-detail", [
      "Selected owning-page handoff:",
      `Owner page: ${item.owner}`,
      `Row key: ${row.row_key || "not reported"}`,
      `Label: ${item.label}`,
      `Severity: ${item.severity}`,
      `Reason(s): ${item.reasons.join("; ") || "review required"}`,
      `Diagnostics targets: ${diagnosticsListText(item.diagnosticsTargets)}`,
      `Backend selected open targets: ${diagnosticsListText(item.openTargets)}`,
      `Safe next action: ${item.safeNextAction}`,
      ...(completedFinalTrustLines.length ? ["", ...completedFinalTrustLines] : []),
      ...(completedPolicyLines.length ? ["", ...completedPolicyLines] : []),
      "",
      ...diagnosticsSampleValidationComparisonLines(item),
      "",
      "Operator path:",
      `1. Use Go To ${item.owner} Row for local UI navigation, or manually open ${item.owner}.`,
      "2. Inspect the owning-page row detail.",
      "3. Use Diagnostics read/open evidence only as supporting proof.",
      "4. Return to the owning page before any backend-owned mutation command.",
      "",
      "Boundary: Diagnostics can open/read backend allowlisted artifacts. Row file/folder opens belong to the owning page and require row_key plus target only.",
      "Navigation guardrail: Go To Owner Row is local UI selection over already-loaded data; it does not POST, open paths, or change backend launch/drain/rerun scope.",
      "Mutation guardrail: this detail view does not launch, rerun, drain, repair, rewrite, move, delete, publish, accept, or mutate media files.",
    ].join("\n"));
  }

  function renderDiagnosticsOwnerHandoffTable(rows = null) {
    if (Array.isArray(rows)) {
      lastDiagnosticsOwnerHandoffRows = rows;
    }
    if (selectedDiagnosticsOwnerHandoffKey && !lastDiagnosticsOwnerHandoffRows.some((row) => diagnosticsOwnerHandoffRowKey(row) === selectedDiagnosticsOwnerHandoffKey)) {
      selectedDiagnosticsOwnerHandoffKey = "";
    }
    const rowList = lastDiagnosticsOwnerHandoffRows;
    setText("diagnostics-owner-handoff-status", diagnosticsOwnerHandoffStatus(rowList));
    setText("diagnostics-owner-handoff", diagnosticsOwnerHandoffSummaryLines(rowList).join("\n"));
    const tbody = byId("diagnostics-owner-handoff-rows");
    if (!tbody) {
      renderDiagnosticsOwnerHandoffDetail(getSelectedDiagnosticsOwnerHandoffRow());
      return;
    }
    if (!rowList.length) {
      clearRows(tbody, 5, "No owning-page handoff rows loaded from Queue, Completed, or Pending Publish.");
      updateTableStatusLegend("diagnostics-owner-handoff-legend", tbody, "Diagnostics owning-page handoff rows");
      renderDiagnosticsOwnerHandoffDetail(null);
      return;
    }
    tbody.replaceChildren();
    rowList.slice(0, 40).forEach((item) => {
      const row = document.createElement("tr");
      const key = diagnosticsOwnerHandoffRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = item.severity === "blocked" ? "blocked" : item.severity === "warning" ? "warning" : "review";
      appendCells(row, [
        item.owner,
        item.label,
        item.severity,
        item.reasons.slice(0, 2).join("; ") || "review",
        item.safeNextAction,
      ]);
      makeRowSelectable(row, () => selectDiagnosticsOwnerHandoffRow(item), {
        selected: Boolean(key && key === selectedDiagnosticsOwnerHandoffKey),
        label: `Diagnostics handoff ${item.owner} ${item.label}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-owner-handoff-legend", tbody, "Diagnostics owning-page handoff rows");
    renderDiagnosticsOwnerHandoffDetail(getSelectedDiagnosticsOwnerHandoffRow());
  }

  function renderDiagnosticsOwnerHandoff(context = {}) {
    renderDiagnosticsOwnerHandoffTable(diagnosticsOwnerHandoffRows(context || {}));
  }

  function isDiagnosticsOpenCommand(entry) {
    return String(entry?.command || "").toLowerCase() === "diagnostics.open";
  }

  function diagnosticsOpenHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object" ? raw.request : {};
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

  function renderDiagnosticsOpenHistory(history = []) {
    const entries = Array.isArray(history) ? history.filter(isDiagnosticsOpenCommand).slice(0, 6) : [];
    if (!Array.isArray(history) || !history.length) {
      setText("diagnostics-open-history", "No diagnostics open command history loaded. Open a diagnostics location to see backend results here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("diagnostics-open-history", "No diagnostics open commands found in recent command history.");
      return;
    }
    setText("diagnostics-open-history", [
      `Last ${entries.length} diagnostics open command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(diagnosticsOpenHistoryLine),
      "Backend diagnostics target allowlists remain the source of truth.",
    ].join("\n"));
  }


    return {
      diagnosticsStateIssueRows,
      diagnosticsPageReviewRows,
      diagnosticsCrossPageConflictRows,
      diagnosticsConflictSignalLabel,
      diagnosticsCommandIssueRows,
      diagnosticsInvestigationAddAction,
      diagnosticsInvestigationActions,
      diagnosticsInvestigationStatus,
      diagnosticsListText,
      diagnosticsRowLabel,
      diagnosticsOwnerDefaultAction,
      diagnosticsOwnerRowSeverity,
      diagnosticsOwnerHandoffRowKey,
      diagnosticsCompletedFinalTrustStepForRow,
      diagnosticsCompletedFinalTrustLines,
      diagnosticsCompletedPolicyReconciliationLines,
      diagnosticsOwnerHandoffRows,
      diagnosticsOwnerHandoffStatus,
      diagnosticsOwnerHandoffSummaryLines,
      diagnosticsHandoffTailTargets,
      diagnosticsOwnerHandoffActions,
      diagnosticsOwnerPageId,
      diagnosticsOwnerSelectFunction,
      diagnosticsOwnerNavigationLabel,
      setDiagnosticsOwnerHandoffNavStatus,
      navigateDiagnosticsOwnerHandoffRow,
      getSelectedDiagnosticsOwnerHandoffRow,
      selectDiagnosticsOwnerHandoffRow,
      renderDiagnosticsOwnerHandoffActions,
      diagnosticsSampleValidationComparisonLines,
      renderDiagnosticsOwnerHandoffDetail,
      renderDiagnosticsOwnerHandoffTable,
      renderDiagnosticsOwnerHandoff,
      isDiagnosticsOpenCommand,
      diagnosticsOpenHistoryLine,
      renderDiagnosticsOpenHistory,
    };
  }

  window.__diagnosticsInvestigationModule = {
    createDiagnosticsInvestigationModule,
  };
})();
