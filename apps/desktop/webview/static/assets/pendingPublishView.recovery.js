(function () {
  function createPendingPublishRecoveryModule(deps = {}) {
    const {
      apiPost = async function () { throw new Error("apiPost unavailable"); },
      appendCells = function () {},
      appendCommandResult = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      commandHistoryCompactEvidenceLine = null,
      getCommandHistory = function () { return []; },
      getCurrentPendingRecoveryPlanSignature = function () { return ""; },
      getLastPendingPayload = function () { return {}; },
      getLastPendingRows = function () { return []; },
      getLastPendingSnapshot = function () { return {}; },
      getSelectedPendingRow = function () { return null; },
      makeRowSelectable = function () {},
      pendingFormatCounts = function () { return "none"; },
      pendingRowKey = function (row) { return row?.row_key || ""; },
      renderCompactCommandHistoryBlock = null,
      renderPendingBackendDrainScopePreview = function () {},
      renderPendingDrainActionConfidence = function () {},
      renderPendingDrainDecisionChecklist = function () {},
      renderPendingDrainGuard = function () {},
      renderPendingDrainOverview = function () {},
      setText = function () {},
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;
    const PENDING_READ_ONLY_BOUNDARY = "Mutation guardrail: read-only evidence; backend routes own pending-publish changes.";

    function getLastPendingRecoveryPlanRows() {
      return Array.isArray(state.lastPendingRecoveryPlanRows) ? state.lastPendingRecoveryPlanRows : [];
    }

    function getLastPendingRecoveryPlanSignature() {
      return String(state.lastPendingRecoveryPlanSignature || "");
    }

    function setLastPendingRecoveryPlanRows(rows, signature = getCurrentPendingRecoveryPlanSignature()) {
      const rowList = Array.isArray(rows) ? rows : [];
      state.lastPendingRecoveryPlanRows = rowList;
      state.lastPendingRecoveryPlanSignature = rowList.length ? String(signature || "") : "";
    }

    function getSelectedPendingRecoveryPlanKey() {
      return state.selectedPendingRecoveryPlanKey || "";
    }

    function setSelectedPendingRecoveryPlanKey(value) {
      state.selectedPendingRecoveryPlanKey = value || "";
    }

    function getPendingRecoveryPlanInFlight() {
      return Boolean(state.pendingRecoveryPlanInFlight);
    }

    function setPendingRecoveryPlanInFlight(value) {
      state.pendingRecoveryPlanInFlight = Boolean(value);
    }

  function setPendingRecoveryPlanBusy(isBusy) {
    setPendingRecoveryPlanInFlight(isBusy);
    ["pending-recovery-plan-selected-button", "pending-recovery-plan-all-button"].forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = getPendingRecoveryPlanInFlight();
    });
  }

  function rejectPendingRecoveryPlanWhileBusy() {
    if (!getPendingRecoveryPlanInFlight()) return false;
    const result = {
      command: "pending_publish.recovery_plan_dry_run",
      ok: false,
      severity: "warning",
      message: "Another pending publish recovery plan is already in progress.",
    };
    appendCommandResult(result);
    setText("pending-recovery-plan-status", result.message);
    return true;
  }

  function isPendingRecoveryPlanCommand(entry) {
    return String(entry?.command || "").toLowerCase() === "pending_publish.recovery_plan_dry_run";
  }

  function pendingRecoveryPlanResultData(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    return data.schema_version === "pending_publish_recovery_plan.v1" ? data : data;
  }

  function pendingRecoveryPlanRowLabel(row) {
    const leaf = String(row?.local_file || row?.manifest_path || row?.server_out || row?.row_key || "(row)")
      .split(/[\\/]/)
      .filter(Boolean)
      .pop();
    return `${leaf || "(row)"}: ${row?.planned_action || "manual_review_with_pending_diagnostics"} (${row?.operator_trust_state || row?.diagnostic_status || "review"})`;
  }

  function pendingRecoveryPlanRowKey(row, index = 0) {
    return String(row?.row_key || row?.manifest_path || row?.local_file || row?.server_out || row?.source_path || `plan-row-${index}`).trim();
  }

  function pendingRecoveryPlanRowStatus(row) {
    const severity = String(row?.diagnostic_severity || "").toLowerCase();
    const recommendation = String(row?.drain_recommendation || "").toLowerCase();
    const recoveryClass = String(row?.recovery_class || "").toLowerCase();
    const action = String(row?.planned_action || "").toLowerCase();
    if (row?.would_mutate || severity === "error" || recommendation.includes("do_not") || action.includes("locate_payload")) {
      return "blocked";
    }
    if (recoveryClass === "ready" || action === "validate_with_backend_drain") {
      return "match";
    }
    return "warning";
  }

  function pendingRecoveryPlanEvidenceText(row) {
    const evidence = Array.isArray(row?.evidence_fields) ? row.evidence_fields.filter(Boolean) : [];
    const proof = Array.isArray(row?.proof_summary) ? row.proof_summary.filter(Boolean) : [];
    return [
      row?.primary_concern || row?.issue_summary || "",
      evidence.length ? `fields=${evidence.slice(0, 3).join(", ")}` : "",
      proof.length ? proof.slice(0, 2).join("; ") : "",
    ].filter(Boolean).join("; ") || "No explicit evidence fields reported.";
  }

  function pendingRecoveryPlanActionText(row) {
    return row?.safe_next_action || row?.planned_action || "Review pending publish diagnostics before drain.";
  }

  function pendingRecoveryPlanRowDetailLines(row) {
    if (!row) {
      return [
        "No recovery-plan row selected.",
        "Build a selected-row or all-rows dry-run plan, then select a planned row to inspect backend-authored evidence.",
      ];
    }
    const openTargets = Array.isArray(row.recommended_open_targets) ? row.recommended_open_targets.filter(Boolean) : [];
    const diagnosticsTargets = Array.isArray(row.recommended_diagnostics_targets) ? row.recommended_diagnostics_targets.filter(Boolean) : [];
    const proof = Array.isArray(row.proof_summary) ? row.proof_summary.filter(Boolean) : [];
    const evidence = Array.isArray(row.evidence_fields) ? row.evidence_fields.filter(Boolean) : [];
    const lines = [
      "Selected recovery-plan row:",
      `Row key: ${row.row_key || "(not reported)"}`,
      `State: ${row.state || "unknown"}`,
      `Diagnostic: ${row.diagnostic_status || "unknown"} (${row.diagnostic_severity || "unknown"})`,
      `Drain recommendation: ${row.drain_recommendation || "review"}`,
      `Trust state: ${row.operator_trust_state || "review-before-drain"}`,
      `Recovery class: ${row.recovery_class || "manual_review"}`,
      `Planned action: ${row.planned_action || "manual_review_with_pending_diagnostics"}`,
      `Dry run only: ${row.dry_run_only === false ? "no" : "yes"}`,
      `Would mutate files: ${row.would_mutate ? "yes" : "no"}`,
      `Safe next action: ${pendingRecoveryPlanActionText(row)}`,
      `Unsafe if ignored: ${row.unsafe_if_ignored || "Running drain without evidence review can strand payloads or publish the wrong target."}`,
      `Primary concern: ${row.primary_concern || row.issue_summary || "not reported"}`,
      `Recommended open targets: ${openTargets.join(", ") || "none reported"}`,
      `Recommended diagnostics targets: ${diagnosticsTargets.join(", ") || "none reported"}`,
      "",
      "Paths:",
      `- Local payload: ${row.local_file || "(not reported)"}`,
      `- Manifest: ${row.manifest_path || "(not reported)"}`,
      `- Destination: ${row.server_out || "(not reported)"}`,
      `- Source: ${row.source_path || "(not reported)"}`,
    ];
    if (evidence.length) lines.push("", "Evidence field(s):", ...evidence.slice(0, 8).map((item) => `- ${item}`));
    if (proof.length) lines.push("", "Proof:", ...proof.slice(0, 8).map((item) => `- ${item}`));
    lines.push("", PENDING_READ_ONLY_BOUNDARY);
    return lines;
  }

  function renderPendingRecoveryPlanRowDetail(row) {
    setText("pending-recovery-plan-row-detail", pendingRecoveryPlanRowDetailLines(row).join("\n"));
  }

  function capturePendingRecoverySelectionScroll() {
    return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
  }

  function restorePendingRecoverySelectionScroll(snapshot) {
    if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
  }

  function selectPendingRecoveryPlanRow(row, index = 0) {
    const scrollSnapshot = capturePendingRecoverySelectionScroll();
    setSelectedPendingRecoveryPlanKey(pendingRecoveryPlanRowKey(row, index));
    renderPendingRecoveryPlanRows(getLastPendingRecoveryPlanRows());
    renderPendingRecoveryPlanRowDetail(row);
    restorePendingRecoverySelectionScroll(scrollSnapshot);
  }

  function renderPendingRecoveryPlanRows(rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    const tbody = byId("pending-recovery-plan-rows");
    if (!rowList.length) {
      clearRows(tbody, 5, "No pending publish recovery plan rows loaded.");
      setText("pending-recovery-plan-legend", "Pending recovery-plan rows: no selectable rows.");
      renderPendingRecoveryPlanRowDetail(null);
      return;
    }
    tbody.replaceChildren();
    rowList.slice(0, 250).forEach((item, index) => {
      const row = document.createElement("tr");
      const key = pendingRecoveryPlanRowKey(item, index);
      row.dataset.rowKey = key;
      row.dataset.status = pendingRecoveryPlanRowStatus(item);
      appendCells(row, [
        item.recovery_class || item.operator_trust_state || "review",
        item.planned_action || "manual_review_with_pending_diagnostics",
        pendingRecoveryPlanEvidenceText(item),
        item.local_file || item.server_out || item.manifest_path || item.source_path || item.row_key || "",
        pendingRecoveryPlanActionText(item),
      ]);
      makeRowSelectable(row, () => selectPendingRecoveryPlanRow(item, index), {
        selected: Boolean(key && key === getSelectedPendingRecoveryPlanKey()),
        label: `Pending publish recovery-plan row ${item.local_file || item.server_out || item.manifest_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-recovery-plan-legend", tbody, "Pending recovery-plan rows");
    const selected = rowList.find((item, index) => pendingRecoveryPlanRowKey(item, index) === getSelectedPendingRecoveryPlanKey());
    renderPendingRecoveryPlanRowDetail(selected || rowList[0]);
  }

  function pendingRecoveryPlanResultLines(result) {
    const data = pendingRecoveryPlanResultData(result || {});
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const summary = Array.isArray(data.summary_lines) ? data.summary_lines.filter(Boolean) : [];
    const lines = [
      result?.message || "No pending publish recovery plan result.",
      `Schema: ${data.schema_version || "not reported"}`,
      `Scope: ${data.scope || "unknown"}`,
      `Rows planned: ${data.row_count || rows.length || 0}`,
      `Blockers/review/ready: ${data.blocker_count || 0} / ${data.review_count || 0} / ${data.ready_count || 0}`,
      `Actions: ${pendingFormatCounts(data.action_counts)}`,
      `Dry run only: ${data.dry_run_only === false ? "no" : "yes"}`,
      `Would mutate files: ${data.would_mutate ? "yes" : "no"}`,
      data.mutation_guardrail || PENDING_READ_ONLY_BOUNDARY,
    ];
    if (summary.length) {
      lines.push("", "Backend plan summary:");
      summary.slice(0, 8).forEach((line) => lines.push(`- ${line}`));
    }
    if (rows.length) {
      lines.push("", "Planned row actions:");
      rows.slice(0, 10).forEach((row) => lines.push(`- ${pendingRecoveryPlanRowLabel(row)}`));
      if (rows.length > 10) lines.push(`- ${rows.length - 10} more row(s) not shown.`);
    } else {
      lines.push("", "No pending publish rows were included in this dry-run plan.");
    }
    const warnings = Array.isArray(result?.warnings) ? result.warnings.filter(Boolean) : [];
    const errors = Array.isArray(result?.errors) ? result.errors.filter(Boolean) : [];
    if (warnings.length) lines.push("", "Warning(s):", ...warnings.slice(0, 5).map((warning) => `- ${warning}`));
    if (errors.length) lines.push("", "Error(s):", ...errors.slice(0, 5).map((error) => `- ${error}`));
    lines.push("", "Recovery plan is dry-run only. Drain Parked Outputs remains the only backend-owned drain command.");
    return lines;
  }

  function renderPendingRecoveryPlanResult(result) {
    const data = pendingRecoveryPlanResultData(result || {});
    const rows = Array.isArray(data.rows) ? data.rows : [];
    setLastPendingRecoveryPlanRows(rows, getCurrentPendingRecoveryPlanSignature());
    if (getSelectedPendingRecoveryPlanKey() && !rows.some((row, index) => pendingRecoveryPlanRowKey(row, index) === getSelectedPendingRecoveryPlanKey())) {
      setSelectedPendingRecoveryPlanKey("");
    }
    if (!getSelectedPendingRecoveryPlanKey() && rows.length) {
      setSelectedPendingRecoveryPlanKey(pendingRecoveryPlanRowKey(rows[0], 0));
    }
    setText("pending-recovery-plan-status", result?.message || "No recovery plan result.");
    setText("pending-recovery-plan-detail", pendingRecoveryPlanResultLines(result || {}).join("\n"));
    renderPendingRecoveryPlanRows(rows);
    renderPendingDrainActionConfidence(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), getCommandHistory());
    renderPendingBackendDrainScopePreview(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), getCommandHistory());
    renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), getCommandHistory());
    renderPendingDrainOverview(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), getCommandHistory());
    renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), getCommandHistory());
  }

  function pendingRecoveryPlanHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const counts = [
      `scope=${data.scope || raw.request?.scope || "unknown"}`,
      `rows=${data.row_count || 0}`,
      `blockers=${data.blocker_count || 0}`,
      `review=${data.review_count || 0}`,
    ];
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: "pending_publish.recovery_plan_dry_run",
        detail: ` (${counts.join("; ")})`,
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} pending_publish.recovery_plan_dry_run [${status}; ${local}] ${entry?.message || ""} (${counts.join("; ")})`.trim();
  }

  function renderPendingRecoveryPlanHistory(entries) {
    if (typeof renderCompactCommandHistoryBlock === "function") {
      renderCompactCommandHistoryBlock({
        history: entries,
        filter: isPendingRecoveryPlanCommand,
        limit: 5,
        targetId: "pending-recovery-plan-history",
        itemLabel: "pending publish recovery plan",
        emptyHistoryText: "No pending publish recovery plan history loaded. Build a dry-run plan before draining suspicious parked outputs.",
        emptyMatchText: "No pending publish recovery plans found in command history. Build a dry-run plan for all rows or the selected row before risky drain decisions.",
        lineFor: pendingRecoveryPlanHistoryLine,
        footer: "Plans are backend-authored dry runs; they do not repair, drain, rewrite, move, delete, or publish files.",
      });
      return;
    }
    const history = Array.isArray(entries) ? entries.filter(isPendingRecoveryPlanCommand).slice(0, 5) : [];
    if (!Array.isArray(entries) || !entries.length) {
      setText(
        "pending-recovery-plan-history",
        "No pending publish recovery plan history loaded. Build a dry-run plan before draining suspicious parked outputs.",
      );
      return;
    }
    if (!history.length) {
      setText(
        "pending-recovery-plan-history",
        "No pending publish recovery plans found in command history. Build a dry-run plan for all rows or the selected row before risky drain decisions.",
      );
      return;
    }
    setText("pending-recovery-plan-history", [
      `Last ${history.length} pending publish recovery plan${history.length === 1 ? "" : "s"}:`,
      ...history.map(pendingRecoveryPlanHistoryLine),
      "Plans are backend-authored dry runs; they do not repair, drain, rewrite, move, delete, or publish files.",
    ].join("\n"));
  }

  async function requestPendingRecoveryPlan(scope = "all") {
    if (rejectPendingRecoveryPlanWhileBusy()) return;
    const normalized = String(scope || "").trim().toLowerCase() === "selected" ? "selected" : "all";
    const row = getSelectedPendingRow();
    if (normalized === "selected" && !row) {
      const result = {
        command: "pending_publish.recovery_plan_dry_run",
        ok: false,
        severity: "warning",
        message: "Select a pending publish row first, or build an all-rows dry-run plan.",
        data: { scope: "selected", dry_run_only: true, would_mutate: false },
      };
      appendCommandResult(result);
      renderPendingRecoveryPlanResult(result);
      return;
    }
    const request = {
      scope: normalized,
      row_key: normalized === "selected" && row ? row.row_key || pendingRowKey(row) : "",
    };
    setPendingRecoveryPlanBusy(true);
    setText("pending-recovery-plan-status", normalized === "selected" ? "Building selected-row dry-run plan..." : "Building all-rows dry-run plan...");
    try {
      const result = await apiPost("/api/pending-publish/recovery-plan", request);
      appendCommandResult(result);
      renderPendingRecoveryPlanResult(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "pending_publish.recovery_plan_dry_run",
        ok: false,
        severity: "error",
        message,
        data: { scope: normalized, dry_run_only: true, would_mutate: false },
      };
      appendCommandResult(result);
      renderPendingRecoveryPlanResult(result);
    } finally {
      setPendingRecoveryPlanBusy(false);
    }
  }

    return {
      setPendingRecoveryPlanBusy,
      rejectPendingRecoveryPlanWhileBusy,
      requestPendingRecoveryPlan,
      renderPendingRecoveryPlanResult,
      pendingRecoveryPlanResultLines,
      pendingRecoveryPlanRowKey,
      pendingRecoveryPlanRowStatus,
      pendingRecoveryPlanEvidenceText,
      pendingRecoveryPlanActionText,
      pendingRecoveryPlanRowDetailLines,
      renderPendingRecoveryPlanRows,
      selectPendingRecoveryPlanRow,
      renderPendingRecoveryPlanRowDetail,
      renderPendingRecoveryPlanHistory,
      isPendingRecoveryPlanCommand,
      pendingRecoveryPlanHistoryLine,
      pendingRecoveryPlanResultData,
      pendingRecoveryPlanRowLabel,
      getLastPendingRecoveryPlanSignature,
    };
  }

  window.__pendingPublishRecoveryModule = { createPendingPublishRecoveryModule };
})();
