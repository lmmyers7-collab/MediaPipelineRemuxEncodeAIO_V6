(function () {
  const domHelpers = window.mediaPipelineDom || {};
  const jsonDetailText = domHelpers.jsonDetailText || function (options = {}) {
    const label = options.label || "JSON detail";
    try {
      return `${label}:\n${JSON.stringify(options.value, null, 2)}`;
    } catch (error) {
      return `${label}:\nJSON render error: ${error instanceof Error ? error.message : String(error)}`;
    }
  };
  let lastDiagnosticsStateSummaryRows = [];
  let selectedDiagnosticsStateSummaryKey = "";
  let lastDiagnosticsStateTriageRows = [];
  let selectedDiagnosticsStateTriageKey = "";

  function diagnosticsStateSummaryRowKey(item) {
    return [
      item?.target || "",
      item?.path || "",
      item?.status || "",
      item?.modified_at || "",
    ].join("\u001f").toLowerCase();
  }

  function diagnosticsStateSummaryStatusText(payload) {
    const rows = Array.isArray(payload?.targets) ? payload.targets : [];
    if (!rows.length) return "No artifacts";
    const counts = rows.reduce((acc, item) => {
      const status = String(item?.status || "unknown").toLowerCase();
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});
    return [
      `${rows.length} artifact${rows.length === 1 ? "" : "s"}`,
      `${counts.error || 0} error`,
      `${counts.warning || 0} warning`,
      `${counts.missing || 0} missing`,
    ].join("; ");
  }

  function diagnosticsStateOperatorStatus(item) {
    const value = String(item?.operator_status || "").trim();
    if (value) return value;
    const status = String(item?.status || "unknown").toLowerCase();
    if (status === "error") return "blocked";
    if (status === "warning" || status === "missing") return "review";
    if (status === "ok") return "ready";
    return "unknown";
  }

  function diagnosticsStateRowStatusState(item) {
    const fallback = diagnosticsStateOperatorStatus(item);
    const state = typeof backendRowStatusState === "function" ? backendRowStatusState(item, fallback) : "";
    if (state) return state;
    if (fallback === "blocked") return "blocked";
    if (fallback === "review") return "warning";
    if (fallback === "ready") return "ready";
    return fallback === "unknown" ? "unknown" : "";
  }

  function diagnosticsStateRecoveryStatus(rows) {
    const items = Array.isArray(rows) ? rows : [];
    if (!items.length) return "No artifacts";
    const statuses = items.map(diagnosticsStateOperatorStatus);
    if (statuses.includes("blocked")) return "Blocked";
    if (statuses.includes("review")) return "Review";
    if (statuses.includes("unknown")) return "Unknown";
    return "Ready";
  }

  function diagnosticsStateSummaryIssueRows(rows) {
    return (Array.isArray(rows) ? rows : []).filter((item) => {
      const status = diagnosticsStateOperatorStatus(item);
      return status === "blocked" || status === "review" || status === "unknown";
    });
  }

  function diagnosticsStateSettingsToolPathLines(payload) {
    const issues = Array.isArray(payload?.settings_tool_path_issues) ? payload.settings_tool_path_issues : [];
    if (!issues.length) return [];
    const lines = ["Settings tool-path handoff:"];
    issues.slice(0, 4).forEach((item) => {
      lines.push(`- ${item?.label || item?.target || "Settings tool path"}: ${diagnosticsStateOperatorStatus(item)}; ${item?.operator_guidance || "Open Settings and review saved tool paths."}`);
    });
    if (issues.length > 4) lines.push(`- ${issues.length - 4} more Settings tool-path issue(s).`);
    lines.push("Guardrail: Diagnostics shows saved backend config evidence only; path edits stay in Settings.");
    return lines;
  }

  function formatArtifactSize(value) {
    const size = Number(value);
    if (!Number.isFinite(size) || size < 0) return "";
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }

  function diagnosticsStateSummaryLineList(label, values) {
    const items = Array.isArray(values) ? values.map((item) => String(item || "").trim()).filter(Boolean) : [];
    if (!items.length) return [];
    return [label, ...items.map((item) => `- ${item}`)];
  }

  function diagnosticsStateActionLabel(action) {
    if (!action) return "";
    if (typeof window.diagnosticsBridgeActionLabel === "function") {
      return window.diagnosticsBridgeActionLabel(action);
    }
    const verb = action.kind === "tail" ? "Read" : "Open";
    return action.label || `${verb} ${String(action.target || "").replaceAll("_", " ")}`;
  }

  function diagnosticsStateActionGroups(actions) {
    const candidates = Array.isArray(actions) ? actions.filter((action) => action && action.target) : [];
    const ordered = typeof window.diagnosticsBridgeOrderedActions === "function"
      ? window.diagnosticsBridgeOrderedActions(candidates)
      : candidates;
    return {
      readFirst: ordered.filter((action) => action.kind === "tail"),
      openNext: ordered.filter((action) => action.kind !== "tail"),
    };
  }

  function diagnosticsStateActionGroupText(actions) {
    return actions.length ? actions.map(diagnosticsStateActionLabel).join(" -> ") : "none inferred";
  }

  function diagnosticsStateTriageRowKey(item) {
    return [
      item?.priority || "",
      item?.target || "",
      item?.status || "",
      item?.read_first_target || "",
      item?.open_next_target || "",
    ].join("\u001f").toLowerCase();
  }

  function diagnosticsStateTriageStatusText(payload) {
    const rows = Array.isArray(payload?.triage) ? payload.triage : [];
    const posture = String(payload?.operator_status || "unknown").trim() || "unknown";
    if (!rows.length) return `${posture}; no triage rows`;
    return `${posture}; ${rows.length} read-order row${rows.length === 1 ? "" : "s"}`;
  }

  function diagnosticsStateTriageActionsForItem(item) {
    if (!item) return [];
    const actions = [];
    if (item.read_first_target) {
      actions.push({
        kind: "tail",
        target: item.read_first_target,
        label: `Read ${item.read_first_target.replaceAll("_", " ")}`,
        hint: "Read bounded backend text before shell-opening diagnostics locations.",
      });
    }
    if (item.open_next_target) {
      actions.push({
        kind: "open",
        target: item.open_next_target,
        label: `Open ${item.open_next_target.replaceAll("_", " ")}`,
        hint: "Open backend-allowlisted diagnostics location only after bounded text/facts are not enough.",
      });
    }
    return actions;
  }

  function diagnosticsStateTriageFirstActionText(item) {
    if (!item) return "";
    if (item.read_first_target) return `Read ${item.read_first_target}`;
    if (item.open_next_target) return `Open ${item.open_next_target}`;
    return "Review detail";
  }

  function diagnosticsStateSummaryActionsForItem(item) {
    if (!item) return [];
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
    addAction(
      "tail",
      item.recommended_tail_target,
      `Read ${item.label || item.target || "Target"} Tail`,
      "Read bounded backend text before opening a folder or file in the OS shell."
    );
    addAction(
      "open",
      item.recommended_open_target,
      `Open ${item.label || item.target || "Target"}`,
      "Open this backend-selected target only after the summary facts do not explain the issue."
    );
    return actions;
  }

  function diagnosticsStateArtifactRiskLines(item) {
    const status = String(item?.status || "").toLowerCase();
    const operatorStatus = diagnosticsStateOperatorStatus(item);
    const lines = [
      "Operational interpretation:",
    ];
    if (operatorStatus === "blocked" || status === "error") {
      lines.push("- Treat this as blocking evidence until the owning artifact is inspected. Do not close, clear, drain, or rerun based on another page alone.");
    } else if (operatorStatus === "review" || status === "warning" || status === "missing") {
      lines.push("- Treat this as review evidence. Refresh once, then compare row facts with Close Readiness and the owning page before changing workflow state.");
    } else if (status === "ok") {
      lines.push("- This artifact currently parses as usable evidence, but it is still only one source. Compare it with row details when pages disagree.");
    } else {
      lines.push("- Status is not definitive. Use the action plan below to gather bounded evidence before changing workflow state.");
    }
    lines.push("- Malformed, missing, stale, or unreadable artifacts can make the WebView look healthier or more broken than the backend state actually is.");
    return lines;
  }

  function diagnosticsStateActionPlanLines(item) {
    const groups = diagnosticsStateActionGroups(diagnosticsStateSummaryActionsForItem(item));
    return [
      "Diagnostics action plan:",
      `Read first: ${diagnosticsStateActionGroupText(groups.readFirst)}`,
      `Open next: ${diagnosticsStateActionGroupText(groups.openNext)}`,
      "Order rationale: read bounded backend text first when available, then shell-open allowlisted locations only when more context is needed.",
      "Guardrail: this row exposes backend allowlist targets only; it does not send arbitrary filesystem paths.",
    ];
  }

  function diagnosticsStateSummaryRecentLines(item) {
    const entries = Array.isArray(item?.recent_entries) ? item.recent_entries : [];
    if (!entries.length) return [];
    const lines = ["Recent entries:"];
    entries.slice(0, 10).forEach((entry) => {
      const bits = [
        entry?.kind || "",
        entry?.size_bytes === null || entry?.size_bytes === undefined ? "" : formatArtifactSize(entry.size_bytes),
        entry?.modified_at || "",
      ].filter(Boolean);
      lines.push(`- ${entry?.name || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`);
    });
    return lines;
  }

  function diagnosticsStateArtifactMeaning(item) {
    const target = String(item?.target || "").toLowerCase();
    const kind = String(item?.kind || "").toLowerCase();
    if (target === "settings_bdpgs_ocr_paths") {
      return "Subtitle OCR settings evidence. BDPGS OCR to SRT can fail before FFmpeg route proof if the saved OCR tool or tessdata path is blocked.";
    }
    if (target === "active_jobs" || target.includes("active")) {
      return "Process lifecycle evidence. Compare with Close Readiness before closing, clearing runtime state, or assuming a process is orphaned.";
    }
    if (target === "queue_snapshot" || target.includes("queue")) {
      return "Queue source/route evidence. Stale or malformed queue state can hide runnable work or make a launch look idle.";
    }
    if (target === "completed_manifest" || target.includes("completed")) {
      return "Completed-output proof. Missing or malformed completed state can make rerun, audit, and duplicate-output decisions unreliable.";
    }
    if (target === "pending_publish" || target.includes("pending")) {
      return "Deferred publish truth. Review this before draining, rerunning, or judging whether scratch/output movement finished.";
    }
    if (target.includes("failure")) {
      return "Failure classification evidence. Use it to distinguish media defects, tool exits, file locks, and retryable runtime problems.";
    }
    if (target.includes("stderr") || target.includes("run_log") || kind === "log" || kind === "text") {
      return "Newest tool/runtime clue. Read the tail when a command failed, timed out, or produced unexpected media output.";
    }
    if (target === "state" || kind === "directory") {
      return "Runtime state container. Inspect it when multiple pages disagree about active work, progress, queue, or publish state.";
    }
    return "Backend-selected diagnostics artifact. Inspect it when this row disagrees with queue, completed, pending publish, or launch state.";
  }

  function diagnosticsStateRecommendedFirstAction(item) {
    const target = String(item?.target || "").toLowerCase();
    if (target === "settings_bdpgs_ocr_paths") {
      return "Open Settings > Subtitles, verify the saved BDPGS OCR tool/tessdata evidence, save if needed, then refresh Diagnostics before rerunning OCR work.";
    }
    const openTarget = String(item?.recommended_open_target || "").trim();
    const tailTarget = String(item?.recommended_tail_target || "").trim();
    if (tailTarget) return `Read Tail (${tailTarget}) to inspect the newest bounded text evidence.`;
    if (openTarget) return `Open ${openTarget} through the backend allowlist, then compare with Close Readiness.`;
    return "Review the facts/warnings/errors below, then compare with Close Readiness and the owning page before changing workflow state.";
  }

  function renderDiagnosticsStateSummaryDetail(item) {
    renderDiagnosticsStateSummaryActions(item || null);
    if (!item) {
      setText("diagnostics-state-summary-detail", "No state artifact row selected. Select a row to inspect backend path, parse facts, warnings, errors, and recent entries.");
      return;
    }
    const lines = [
      `Target: ${item.target || ""}`,
      `Label: ${item.label || ""}`,
      `Status: ${item.status || ""}`,
      `Operator status: ${diagnosticsStateOperatorStatus(item)}`,
      `Operator guidance: ${item.operator_guidance || "Review this backend-selected diagnostics artifact when investigating runtime state."}`,
      `Recovery stage: ${item.recovery_stage || "diagnostics_artifact"}`,
      `Unsafe if ignored: ${item.unsafe_if_ignored || "Related WebView pages may look healthier than backend state actually is."}`,
      `Meaning: ${diagnosticsStateArtifactMeaning(item)}`,
      `Recommended first action: ${diagnosticsStateRecommendedFirstAction(item)}`,
      "",
      ...diagnosticsStateArtifactRiskLines(item),
      "",
      ...diagnosticsStateActionPlanLines(item),
      `Kind: ${item.kind || ""}`,
      `Exists: ${item.exists ? "yes" : "no"}`,
      `Path: ${item.path || ""}`,
      `Size: ${formatArtifactSize(item.size_bytes)}`,
      `Modified: ${item.modified_at || ""}`,
      "",
      ...diagnosticsStateSummaryLineList("Facts:", item.facts),
      ...diagnosticsStateSummaryLineList("Warnings:", item.warnings),
      ...diagnosticsStateSummaryLineList("Errors:", item.errors),
      ...diagnosticsStateSummaryRecentLines(item),
      "",
      `Recommended open target: ${item.recommended_open_target || "(none)"}`,
      `Recommended tail target: ${item.recommended_tail_target || "(none)"}`,
      "",
      "Guardrail: this view is read-only and only summarizes backend-selected diagnostics targets.",
      "",
      jsonDetailText({
        label: "Diagnostics artifact JSON",
        value: item,
        intro: "Read-only diagnostics artifact payload from the backend state summary. Select this block to copy it for troubleshooting.",
        guardrail: "Mutation guardrail: this detail view formats already-loaded diagnostics state only and cannot repair, delete, drain, rerun, clear state, open arbitrary paths, or touch media.",
      }),
    ].filter((line, index, array) => line !== "" || array[index - 1] !== "");
    setText("diagnostics-state-summary-detail", lines.join("\n"));
  }

  function renderDiagnosticsStateSummaryActions(item) {
    const actions = byId("diagnostics-state-summary-actions");
    if (!actions) return;
    actions.replaceChildren();
    if (!item) return;
    const groups = diagnosticsStateActionGroups(diagnosticsStateSummaryActionsForItem(item));
    window.mediaPipelineDom?.renderOpenTargetActionGroups?.(actions, groups, {
      labelFor: diagnosticsStateActionLabel,
      groupDataset: "diagnosticsStateActionGroup",
      actionDataset: "diagnosticsStateAction",
      targetDataset: "diagnosticsStateTarget",
      onTail: (target) => {
        if (typeof window.requestDiagnosticsTail === "function") window.requestDiagnosticsTail(target);
      },
      onOpen: (target) => {
        if (typeof window.requestDiagnosticsOpen === "function") window.requestDiagnosticsOpen(target);
      },
    });
  }

  function renderDiagnosticsStateTriageActions(item) {
    const actions = byId("diagnostics-state-triage-actions");
    if (!actions) return;
    actions.replaceChildren();
    if (!item) return;
    const groups = diagnosticsStateActionGroups(diagnosticsStateTriageActionsForItem(item));
    window.mediaPipelineDom?.renderOpenTargetActionGroups?.(actions, groups, {
      labelFor: diagnosticsStateActionLabel,
      groupDataset: "diagnosticsStateTriageActionGroup",
      actionDataset: "diagnosticsStateTriageAction",
      targetDataset: "diagnosticsStateTriageTarget",
      onTail: (target) => {
        if (typeof window.requestDiagnosticsTail === "function") window.requestDiagnosticsTail(target);
      },
      onOpen: (target) => {
        if (typeof window.requestDiagnosticsOpen === "function") window.requestDiagnosticsOpen(target);
      },
    });
  }

  function renderDiagnosticsStateTriageDetail(item) {
    renderDiagnosticsStateTriageActions(item || null);
    if (!item) {
      setText("diagnostics-state-triage-detail", "No backend state triage row selected. Select a row to inspect read order, reason, safe next action, and backend allowlisted diagnostics actions.");
      return;
    }
    const groups = diagnosticsStateActionGroups(diagnosticsStateTriageActionsForItem(item));
    const lines = [
      "Backend read-order detail:",
      `Priority: ${item.priority || ""}`,
      `Target: ${item.target || ""}`,
      `Label: ${item.label || ""}`,
      `Status: ${item.status || ""}`,
      `Operator status: ${item.operator_status || ""}`,
      `Recovery stage: ${item.recovery_stage || ""}`,
      `Reason: ${item.reason || ""}`,
      `Read first: ${diagnosticsStateActionGroupText(groups.readFirst)}`,
      `Open next: ${diagnosticsStateActionGroupText(groups.openNext)}`,
      `Safe next action: ${item.safe_next_action || "Review owning page and diagnostics before changing workflow state."}`,
      `Unsafe if ignored: ${item.unsafe_if_ignored || "Related WebView pages may look healthier than backend state actually is."}`,
      "",
      "Mutation guardrail: this read-order detail cannot repair, delete, drain, rerun, clear state, or mark work complete.",
      "",
      jsonDetailText({
        label: "Diagnostics triage JSON",
        value: item,
        intro: "Read-only diagnostics read-order payload from the backend state summary. Select this block to copy it for troubleshooting.",
        guardrail: "Mutation guardrail: this triage detail formats already-loaded diagnostics state only and cannot repair, delete, drain, rerun, clear state, open arbitrary paths, or touch media.",
      }),
    ];
    setText("diagnostics-state-triage-detail", lines.join("\n"));
  }

  function getSelectedDiagnosticsStateTriageRow() {
    if (!selectedDiagnosticsStateTriageKey) return null;
    return lastDiagnosticsStateTriageRows.find((row) => diagnosticsStateTriageRowKey(row) === selectedDiagnosticsStateTriageKey) || null;
  }

  function selectDiagnosticsStateTriageRow(item) {
    selectedDiagnosticsStateTriageKey = diagnosticsStateTriageRowKey(item);
    renderDiagnosticsStateTriageDetail(item || null);
    renderDiagnosticsStateTriageRows(lastDiagnosticsStateTriageRows);
  }

  function renderDiagnosticsStateTriageRows(rows = []) {
    lastDiagnosticsStateTriageRows = Array.isArray(rows) ? rows : [];
    if (
      selectedDiagnosticsStateTriageKey &&
      !lastDiagnosticsStateTriageRows.some((row) => diagnosticsStateTriageRowKey(row) === selectedDiagnosticsStateTriageKey)
    ) {
      selectedDiagnosticsStateTriageKey = "";
    }
    const tbody = byId("diagnostics-state-triage-rows");
    if (!tbody) return;
    if (!lastDiagnosticsStateTriageRows.length) {
      clearRows(tbody, 5, "No backend state triage rows loaded.");
      updateTableStatusLegend("diagnostics-state-triage-legend", tbody, "Backend state triage rows");
      renderDiagnosticsStateTriageDetail(null);
      return;
    }
    tbody.replaceChildren();
    lastDiagnosticsStateTriageRows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = diagnosticsStateRowStatusState(item);
      const key = diagnosticsStateTriageRowKey(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item?.priority || "",
        item?.target || "",
        item?.operator_status || item?.status || "",
        item?.recovery_stage || "",
        diagnosticsStateTriageFirstActionText(item),
      ]);
      makeRowSelectable(row, () => selectDiagnosticsStateTriageRow(item), {
        selected: Boolean(key && key === selectedDiagnosticsStateTriageKey),
        label: `Backend state triage row ${item?.target || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-state-triage-legend", tbody, "Backend state triage rows");
    renderDiagnosticsStateTriageDetail(getSelectedDiagnosticsStateTriageRow());
  }

  function renderDiagnosticsStateTriage(payload) {
    const rows = Array.isArray(payload?.triage) ? payload.triage : [];
    setText("diagnostics-state-triage-status", diagnosticsStateTriageStatusText(payload || {}));
    const lines = [
      "Backend read order:",
      ...(Array.isArray(payload?.operator_summary) && payload.operator_summary.length
        ? payload.operator_summary
        : ["No backend state operator summary loaded."]),
      "Read first means bounded backend tail/read evidence; Open next means backend-allowlisted shell-open locations.",
      "Guardrail: the frontend receives target keys only, not arbitrary filesystem paths.",
    ];
    setText("diagnostics-state-triage-summary", lines.join("\n"));
    renderDiagnosticsStateTriageRows(rows);
  }

  function renderDiagnosticsStateRecovery(payload) {
    const rows = Array.isArray(payload?.targets) ? payload.targets : [];
    const issues = diagnosticsStateSummaryIssueRows(rows);
    const status = diagnosticsStateRecoveryStatus(rows);
    setText("diagnostics-state-recovery-status", status);
    const counts = rows.reduce((acc, item) => {
      const operatorStatus = diagnosticsStateOperatorStatus(item);
      acc[operatorStatus] = (acc[operatorStatus] || 0) + 1;
      return acc;
    }, {});
    const lines = [
      "State artifact recovery checklist:",
      `Operator status counts: ready ${counts.ready || 0}; review ${counts.review || 0}; blocked ${counts.blocked || 0}; unavailable ${counts["not available"] || 0}; unknown ${counts.unknown || 0}.`,
      "Close Readiness is the authority for whether it is safe to exit; do not clear runtime files just because an artifact looks stale.",
      "Recovery stage and unsafe-if-ignored fields explain why an artifact matters before rerun, drain, cleanup, or shutdown decisions.",
      "Use row-level Open/Tail buttons to inspect backend-allowlisted targets. The WebView does not send filesystem paths.",
    ];
    if (!rows.length) {
      lines.push("", "No backend state artifacts were returned. Refresh, then check Diagnostics and backend availability.");
    } else if (issues.length) {
      lines.push("", "Review/blocked artifact(s):");
      issues.slice(0, 8).forEach((item) => {
        lines.push(`- ${item.label || item.target || "artifact"}: ${diagnosticsStateOperatorStatus(item)}; stage=${item.recovery_stage || "diagnostics_artifact"}; ${item.operator_guidance || "Review artifact detail."}`);
      });
      if (issues.length > 8) lines.push(`- ${issues.length - 8} more artifact(s) require review.`);
    } else {
      lines.push("", "No state artifact blockers are visible. If the UI still looks wrong, compare Queue, Completed, Pending Publish, Run Logs, and ActiveJobs before rerunning media.");
    }
    const settingsLines = diagnosticsStateSettingsToolPathLines(payload);
    if (settingsLines.length) lines.push("", ...settingsLines);
    lines.push("", "Mutation guardrail: this checklist does not repair, delete, rewrite, drain, rerun, or clear state.");
    setText("diagnostics-state-recovery", lines.join("\n"));
  }

  function getSelectedDiagnosticsStateSummaryRow() {
    if (!selectedDiagnosticsStateSummaryKey) return null;
    return lastDiagnosticsStateSummaryRows.find((row) => diagnosticsStateSummaryRowKey(row) === selectedDiagnosticsStateSummaryKey) || null;
  }

  function selectDiagnosticsStateSummaryRow(item) {
    selectedDiagnosticsStateSummaryKey = diagnosticsStateSummaryRowKey(item);
    renderDiagnosticsStateSummaryDetail(item || null);
    renderDiagnosticsStateSummaryRows(lastDiagnosticsStateSummaryRows);
  }

  function renderDiagnosticsStateSummaryRows(rows = []) {
    lastDiagnosticsStateSummaryRows = Array.isArray(rows) ? rows : [];
    if (
      selectedDiagnosticsStateSummaryKey &&
      !lastDiagnosticsStateSummaryRows.some((row) => diagnosticsStateSummaryRowKey(row) === selectedDiagnosticsStateSummaryKey)
    ) {
      selectedDiagnosticsStateSummaryKey = "";
    }
    const tbody = byId("diagnostics-state-summary-rows");
    if (!tbody) return;
    if (!lastDiagnosticsStateSummaryRows.length) {
      clearRows(tbody, 5, "No backend state artifact rows loaded.");
      updateTableStatusLegend("diagnostics-state-summary-table-legend", tbody, "State artifact rows");
      renderDiagnosticsStateSummaryDetail(null);
      return;
    }
    tbody.replaceChildren();
    lastDiagnosticsStateSummaryRows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = diagnosticsStateRowStatusState(item);
      const key = diagnosticsStateSummaryRowKey(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item?.target || "",
        item?.operator_status || item?.status || "",
        item?.kind || "",
        formatArtifactSize(item?.size_bytes),
        item?.modified_at || "",
      ], [null, null, null, "num", "num"]);
      makeRowSelectable(row, () => selectDiagnosticsStateSummaryRow(item), {
        selected: Boolean(key && key === selectedDiagnosticsStateSummaryKey),
        label: `State artifact row ${item?.target || item?.kind || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("diagnostics-state-summary-table-legend", tbody, "State artifact rows");
    renderDiagnosticsStateSummaryDetail(getSelectedDiagnosticsStateSummaryRow());
  }

  function renderDiagnosticsStateSummary(payload) {
    const rows = Array.isArray(payload?.targets) ? payload.targets : [];
    setText("diagnostics-state-summary-status", diagnosticsStateSummaryStatusText(payload || {}));
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload,
        label: "Diagnostics State",
        rowCount: rows.length,
        artifactLine: `State artifacts: ${rows.length}; operator status=${payload?.operator_status || "unknown"}.`,
        readError: Array.isArray(payload?.errors) && payload.errors.length ? payload.errors.join(" | ") : "",
        refreshAction: "Use Refresh Diagnostics or topbar Refresh. This re-reads backend diagnostics only and does not repair, clear, delete, rerun, publish, or move files.",
      })
      : [];
    const lines = [
      ...freshnessLines,
      payload?.guardrail || "Read-only backend state summary.",
      `Schema: ${payload?.schema_version || "unknown"}`,
      `Status: ${payload?.ok === false ? "issues detected" : "ok"}`,
      `Operator status: ${payload?.operator_status || "unknown"}`,
    ];
    const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
    const errors = Array.isArray(payload?.errors) ? payload.errors : [];
    if (warnings.length) lines.push(`Warnings: ${warnings.length}`);
    if (errors.length) lines.push(`Errors: ${errors.length}`);
    const settingsLines = diagnosticsStateSettingsToolPathLines(payload);
    if (settingsLines.length) lines.push("", ...settingsLines);
    lines.push("Next step: select a row for details, or use the allowlisted Open/Tail controls below for the owning artifact.");
    setText("diagnostics-state-summary", lines.join("\n"));
    renderDiagnosticsStateRecovery(payload || {});
    renderDiagnosticsStateTriage(payload || {});
    renderDiagnosticsStateSummaryRows(rows);
  }

  /**
   * Public namespace for the diagnostics state-summary module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineDiagnosticsStateSummaryView = {
    renderDiagnosticsStateSummary,
    renderDiagnosticsStateSummaryRows,
    renderDiagnosticsStateSummaryDetail,
    renderDiagnosticsStateSummaryActions,
    renderDiagnosticsStateRecovery,
    renderDiagnosticsStateTriage,
    renderDiagnosticsStateTriageRows,
    renderDiagnosticsStateTriageDetail,
    renderDiagnosticsStateTriageActions,
    diagnosticsStateArtifactMeaning,
    diagnosticsStateRecommendedFirstAction,
    diagnosticsStateTriageRowKey,
    diagnosticsStateTriageStatusText,
    diagnosticsStateTriageActionsForItem,
    diagnosticsStateSummaryRowKey,
    diagnosticsStateSummaryStatusText,
    diagnosticsStateOperatorStatus,
    diagnosticsStateRowStatusState,
    diagnosticsStateRecoveryStatus,
    diagnosticsStateSettingsToolPathLines,
    diagnosticsStateSummaryActionsForItem,
    diagnosticsStateArtifactRiskLines,
    diagnosticsStateActionPlanLines,
    formatArtifactSize,
  };
  window.diagnosticsStateRecommendedFirstAction = diagnosticsStateRecommendedFirstAction;
  window.diagnosticsStateOperatorStatus = diagnosticsStateOperatorStatus;
  window.diagnosticsStateRowStatusState = diagnosticsStateRowStatusState;
})();
