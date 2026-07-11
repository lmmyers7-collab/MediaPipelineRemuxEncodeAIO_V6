/* global byId, clearRows, setText */
(function () {
  function createMaintenanceHealth(deps) {
    const {
      state,
      renderProgressBarsInto,
      diagnosticsBridgeApi,
      setMaintenanceStatusText,
      maintenanceTableRowStatus,
      maintenanceRowKey,
      getSelectedMaintenanceRow,
      renderDryRunConfidence,
    } = deps;
  function selectMaintenanceRow(item) {
    state.selectedMaintenanceRowKey = maintenanceRowKey(item);
    renderMaintenanceDetail(item || null);
    renderMaintenanceRows(Array.isArray(state.lastMaintenance?.rows) ? state.lastMaintenance.rows : []);
  }

  function renderMaintenance(maintenance) {
    state.lastMaintenance = maintenance || {};
    const rows = Array.isArray(state.lastMaintenance.rows) ? state.lastMaintenance.rows : [];
    const warnings = Array.isArray(state.lastMaintenance.warnings) ? state.lastMaintenance.warnings : [];
    setText("maintenance-ok-count", String(state.lastMaintenance.ok_count || 0));
    setText("maintenance-missing-count", String(state.lastMaintenance.missing_count || 0));
    setText("maintenance-warning-count", String(state.lastMaintenance.warning_count || warnings.length || 0));
    setText("maintenance-total-count", String(rows.length));
    setMaintenanceStatusText("maintenance-status", rows.length ? `${rows.length} check${rows.length === 1 ? "" : "s"}` : "No rows", maintenanceReadinessStatus(state.lastMaintenance, rows));
    renderMaintenanceHealthProgress(state.lastMaintenance.health_progress || { progress_bars: state.lastMaintenance.progress_bars || [] });
    renderMaintenanceReadiness(state.lastMaintenance, rows);
    renderMaintenanceToolchain(state.lastMaintenance.toolchain_evidence || {});
    setText("maintenance-warnings", warnings.join("\n") || "No maintenance warnings.");
    renderMaintenanceDetail(getSelectedMaintenanceRow());
    renderMaintenanceRows(rows);
    renderDryRunConfidence();
  }


  function maintenanceProgressStatus(progress) {
    const status = String(progress?.status || "").trim();
    if (!status) return "Not loaded";
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function maintenanceProgressStepLines(progress) {
    const payload = progress || {};
    const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
      ? payload.summary_lines.map((line) => String(line || ""))
      : [
        `Health progress: ${payload.status || "not loaded"}`,
        `Steps checked: ${payload.checked_count || 0}/${payload.total_steps || 0}`,
      ];
    const steps = Array.isArray(payload.steps) ? payload.steps : [];
    if (steps.length) {
      lines.push("", "Health steps:");
      steps.forEach((step) => {
        const marker = step.status || "pending";
        const required = step.required === false ? "optional" : "required";
        const detail = step.detail ? ` - ${step.detail}` : "";
        lines.push(`- ${step.label || step.id || "step"}: ${marker}; ${required}${detail}`);
      });
    } else {
      lines.push("", "No backend health progress steps loaded yet.");
    }
    lines.push("", "Mutation guardrail: WebView renders Maintenance health progress but does not repair paths, install tools, launch media work, drain pending publish, or mutate files.");
    return lines;
  }

  function maintenanceHealthErrorProgress(message) {
    const detail = String(message || "Maintenance health check failed.");
    return {
      schema_version: "desktop_maintenance_health_progress.v1",
      status: "error",
      mode: "determinate",
      checked_count: 0,
      total_steps: 1,
      summary_lines: [
        "Health progress: error",
        `Failure detail: ${detail}`,
        "Final result: health check failed before a trustworthy readiness snapshot was loaded.",
      ],
      steps: [
        {
          id: "maintenance_health_refresh",
          label: "Health refresh",
          status: "error",
          required: true,
          detail,
        },
      ],
      progress_bars: [
        {
          id: "maintenance_health",
          label: "Maintenance health",
          mode: "determinate",
          percent: 100,
          status: "error",
          detail,
          source: "/api/maintenance",
          stale: false,
        },
      ],
    };
  }

  function renderMaintenanceHealthProgress(progress) {
    const payload = progress || {};
    const bars = Array.isArray(payload.progress_bars) ? payload.progress_bars : [];
    setMaintenanceStatusText("maintenance-progress-status", maintenanceProgressStatus(payload));
    if (typeof renderProgressBarsInto === "function") {
      renderProgressBarsInto("maintenance-progress-bars", bars, payload, "No maintenance health progress loaded.");
    } else {
      setText("maintenance-progress-bars", bars.length ? bars.map((bar) => `${bar.label || bar.id || "Progress"}: ${bar.status || "unknown"} ${bar.percent ?? ""}%`).join("\n") : "No maintenance health progress loaded.");
    }
    setText("maintenance-progress-steps", maintenanceProgressStepLines(payload).join("\n"));
  }

  function stopMaintenanceProgressPolling() {
    if (state.maintenanceProgressPollTimer !== null) {
      window.clearInterval(state.maintenanceProgressPollTimer);
      state.maintenanceProgressPollTimer = null;
    }
  }

  async function pollMaintenanceProgress() {
    try {
      renderMaintenanceHealthProgress(await apiGet("/api/maintenance/progress"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      renderMaintenanceHealthProgress({
        ...maintenanceHealthErrorProgress(message),
        status: "unavailable",
        summary_lines: [
          "Health progress: unavailable",
          `Failure detail: ${message}`,
          "Polling could not load health-progress details. The main health check result remains authoritative.",
        ],
      });
    }
  }

  function startMaintenanceProgressPolling() {
    stopMaintenanceProgressPolling();
    pollMaintenanceProgress();
    state.maintenanceProgressPollTimer = window.setInterval(pollMaintenanceProgress, 750);
  }

  function maintenanceDiagnosticsActionsForRow(item) {
    const actions = Array.isArray(item?.recommended_diagnostics_actions)
      ? item.recommended_diagnostics_actions
      : [];
    if (actions.length) return actions;
    return [
      { kind: "tail", target: "last_stderr_log", label: "Read Last Stderr" },
      { kind: "open", target: "run_logs", label: "Open Run Logs" },
    ];
  }

  function requestMaintenanceDiagnosticsAction(action) {
    const target = String(action?.target || "").trim();
    if (!target) {
      setText("maintenance-diagnostics-status", "No diagnostics target available.");
      return;
    }
    if (action?.kind === "tail") {
      if (typeof requestDiagnosticsTail === "function") {
        requestDiagnosticsTail(target);
        setText("maintenance-diagnostics-status", `Read requested: ${target}`);
      } else {
        setText("maintenance-diagnostics-status", "Diagnostics tail reader is not loaded.");
      }
      return;
    }
    if (typeof requestDiagnosticsOpen === "function") {
      requestDiagnosticsOpen(target);
      setText("maintenance-diagnostics-status", `Open requested: ${target}`);
    } else {
      setText("maintenance-diagnostics-status", "Diagnostics open action is not loaded.");
    }
  }

  function renderMaintenanceDiagnosticsActions(item) {
    const container = byId("maintenance-diagnostics-actions");
    if (!container) return;
    container.replaceChildren();
    if (!item) {
      setText("maintenance-diagnostics-status", "Select a maintenance row to see diagnostics actions.");
      return;
    }
    const actions = maintenanceDiagnosticsActionsForRow(item);
    const bridge = diagnosticsBridgeApi();
    if (typeof bridge.appendDiagnosticsBridgeGroupedButtons === "function") {
      bridge.appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "maintenanceDiagnostics",
        onAction: requestMaintenanceDiagnosticsAction,
      });
      if (typeof bridge.appendDiagnosticsBridgeButton === "function") {
        bridge.appendDiagnosticsBridgeButton(container, actions, `Maintenance check ${item.name || ""}`);
      }
    } else {
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.textContent = action.label || `${action.kind || "open"} ${action.target}`;
        button.addEventListener("click", () => requestMaintenanceDiagnosticsAction(action));
        container.appendChild(button);
      });
    }
    setText("maintenance-diagnostics-status", `${actions.length} diagnostics action${actions.length === 1 ? "" : "s"} available.`);
  }

  function maintenanceDetailLines(item) {
    if (!item) {
      return [
        "No maintenance row selected.",
        "Select a health row to inspect dry-run impact, required/optional status, operator guidance, and Diagnostics handoff.",
        "Guardrail: selecting a row does not run release packaging, rewrite manifests, repair files, or mutate media.",
      ];
    }
    const actions = maintenanceDiagnosticsActionsForRow(item);
    const lines = [];
    const bridge = diagnosticsBridgeApi();
    if (typeof bridge.diagnosticsBridgeRowTrustLines === "function") {
      lines.push(...bridge.diagnosticsBridgeRowTrustLines(`Maintenance check ${item.name || ""}`, actions, {
        trustState: item.operator_status || item.status || "review",
        primaryConcern: item.operator_guidance || "verify maintenance health before trusting dry-run commands",
        evidence: [
          `Status: ${item.status || ""}`,
          `Required: ${item.required === false ? "no" : "yes"}`,
          `Detail: ${item.detail || ""}`,
          `Dry-run impact: ${item.dry_run_impact || ""}`,
        ],
        safeAction: item.safe_next_action || "Rerun Environment Health before acting on maintenance output.",
        unsafeAction: "Do not treat dry-run output as proof if required health checks are missing.",
        owningPages: "Maintenance for dry-run commands; Diagnostics for logs/state evidence.",
      }));
      lines.push("");
    }
    lines.push(
      `Check: ${item.name || ""}`,
      `Status: ${item.status || ""}`,
      `Required: ${item.required === false ? "no" : "yes"}`,
      `Optional: ${item.optional === true ? "yes" : "no"}`,
      `Dry-run impact: ${item.dry_run_impact || ""}`,
      `Tool kind: ${item.tool_kind || ""}`,
      `Tool source: ${item.tool_source || ""}`,
      `Capability: ${item.capability || ""}`,
      `Failure scope: ${item.failure_scope || ""}`,
      `Detail: ${item.detail || ""}`,
      "",
      `Operator guidance: ${item.operator_guidance || ""}`,
      `Safe next action: ${item.safe_next_action || ""}`,
      `Unsafe if ignored: ${item.unsafe_if_ignored || ""}`
    );
    return lines;
  }

  function renderMaintenanceDetail(item) {
    renderMaintenanceDiagnosticsActions(item || null);
    setMaintenanceStatusText("maintenance-detail-status", item ? (item.operator_status || item.status || "selected") : "No selection");
    setText("maintenance-detail", maintenanceDetailLines(item || null).join("\n"));
  }

  function renderMaintenanceRows(rows) {
    const tbody = byId("maintenance-rows");
    if (!tbody) return;
    if (!rows.length) {
      const warnings = Array.isArray(state.lastMaintenance?.warnings) ? state.lastMaintenance.warnings : [];
      clearRows(tbody, 5, warnings.join(" | ") || "No maintenance checks loaded.");
      updateTableStatusLegend("maintenance-table-legend", tbody, "Maintenance rows");
      renderMaintenanceDetail(null);
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = maintenanceTableRowStatus(item.operator_status || item.status);
      appendCells(row, [
        item.status || "",
        item.name || "",
        item.required === false ? "Optional" : "Required",
        item.dry_run_impact || item.failure_scope || item.operator_guidance || "",
        item.detail || "",
      ]);
      makeRowSelectable(row, () => selectMaintenanceRow(item), {
        selected: Boolean(maintenanceRowKey(item) && maintenanceRowKey(item) === state.selectedMaintenanceRowKey),
        label: `Maintenance check ${item.name || item.status || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("maintenance-table-legend", tbody, "Maintenance rows");
  }

  function maintenanceRequiredMissingRows(rows) {
    return rows.filter((item) => item?.status !== "ok" && item?.status !== "running" && item?.optional !== true);
  }

  function maintenanceOptionalWarningRows(rows) {
    return rows.filter((item) => item?.status !== "ok" && item?.optional === true);
  }

  function maintenanceActiveRows(rows) {
    return rows.filter((item) => item?.status === "running");
  }

  function maintenanceReadinessStatus(maintenance, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (maintenance?.error) return "Unavailable";
    if (!rowList.length) return "Not checked";
    if (maintenanceRequiredMissingRows(rowList).length || Number(maintenance?.missing_count || 0) > 0) return "Blocked";
    if (maintenanceActiveRows(rowList).length) return "Active";
    const warnings = Array.isArray(maintenance?.warnings) ? maintenance.warnings.filter(Boolean) : [];
    if (maintenanceOptionalWarningRows(rowList).length || Number(maintenance?.warning_count || 0) > 0 || warnings.length) return "Warnings";
    return "Ready";
  }

  function focusMaintenanceQuickLinkTarget(selector) {
    const target = selector ? document.querySelector(selector) : null;
    if (!target) return false;
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    if (!target.matches?.("a[href], button, input, select, textarea, summary, [tabindex]")) {
      target.setAttribute("tabindex", "-1");
    }
    target.focus?.({ preventScroll: true });
    return true;
  }

  function activateQuickLink(action) {
    const normalized = String(action || "").trim().toLowerCase();
    const rows = Array.isArray(state.lastMaintenance?.rows) ? state.lastMaintenance.rows : [];
    if (normalized === "missing") {
      const item = maintenanceRequiredMissingRows(rows)[0];
      if (item) {
        selectMaintenanceRow(item);
        return focusMaintenanceQuickLinkTarget("#maintenance-detail");
      }
      return focusMaintenanceQuickLinkTarget("#maintenance-rows");
    }
    if (normalized === "warnings") {
      const item = maintenanceOptionalWarningRows(rows)[0];
      if (item) {
        selectMaintenanceRow(item);
        return focusMaintenanceQuickLinkTarget("#maintenance-detail");
      }
      return focusMaintenanceQuickLinkTarget("#maintenance-warnings") || focusMaintenanceQuickLinkTarget("#maintenance-toolchain");
    }
    return true;
  }

  function maintenanceRealMediaBoundaryLines() {
    return [
      "Real-media validation boundary:",
      "- Maintenance health and dry-run commands prove packaging/backfill environment posture only.",
      "- They do not prove FFmpeg route correctness, subtitle OCR/SRT output, audio selection, source stability, copy-to-scratch behavior, Output Size Check results, completed sidecars, or pending-publish completion for real media.",
      "- Daily-driver confidence still requires a small known processing run and comparison across Queue evidence, Diagnostics logs, Completed output proof, and Pending Publish drain summary.",
    ];
  }

  function maintenanceToolchainStatus(evidence) {
    const status = String(evidence?.operator_status || "").trim();
    if (status) return status.charAt(0).toUpperCase() + status.slice(1);
    return "Unknown";
  }

  function maintenanceToolchainLines(evidence) {
    const payload = evidence || {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
      ? payload.summary_lines.map((line) => String(line || ""))
      : [
        `Toolchain readiness: ${maintenanceToolchainStatus(payload).toLowerCase()}`,
        `Required missing/blocking: ${payload.required_missing_count || 0}`,
        `Optional warning/review: ${payload.optional_review_count || 0}`,
      ];
    if (rows.length) {
      lines.push("", "Tool capability rows:");
      rows.slice(0, 8).forEach((row) => {
        lines.push(`- ${row.name || row.tool_kind || "tool"}: ${row.operator_status || row.status || "unknown"}; source=${row.source || ""}; ${row.capability || ""}`);
        if (row.status !== "ok" && row.failure_scope) lines.push(`  Impact: ${row.failure_scope}`);
      });
      if (rows.length > 8) lines.push(`- ${rows.length - 8} more tool row(s).`);
    } else {
      lines.push("", "No backend tool rows were returned. Run Environment Health before trusting maintenance dry-run output.");
    }
    lines.push("", "Real-media boundary: toolchain readiness does not prove FFmpeg route correctness, subtitle/audio output, Output Size Check behavior, Completed sidecars, or Pending Publish completion for a real media file.");
    lines.push("Mutation guardrail: WebView does not resolve arbitrary tools, edit PATH, install dependencies, launch media jobs, or mutate files from this panel.");
    return lines;
  }

  function renderMaintenanceToolchain(evidence) {
    setMaintenanceStatusText("maintenance-toolchain-status", maintenanceToolchainStatus(evidence || {}));
    setText("maintenance-toolchain", maintenanceToolchainLines(evidence || {}).join("\n"));
  }

  function maintenanceReadinessLines(maintenance, rows) {
    const payload = maintenance || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) {
      return [
        "Status: unavailable",
        `Error: ${payload.error}`,
        "Next step: open Diagnostics and Run Logs before trusting release or backfill dry-run results.",
      ];
    }
    const requiredMissing = maintenanceRequiredMissingRows(rowList);
    const optionalWarnings = maintenanceOptionalWarningRows(rowList);
    const activeRows = maintenanceActiveRows(rowList);
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const lines = [
      `Checks loaded: ${rowList.length}`,
      `OK: ${payload.ok_count || 0}`,
      `Required missing/blocking: ${requiredMissing.length || payload.missing_count || 0}`,
      `Active process guard rows: ${activeRows.length}`,
      `Optional warnings: ${optionalWarnings.length || payload.warning_count || warnings.length || 0}`,
    ];
    if (requiredMissing.length) {
      lines.push("", "Blocking check(s):");
      requiredMissing.slice(0, 6).forEach((item) => lines.push(`- ${item.name || "unknown"}: ${item.detail || item.status || ""}`));
    }
    if (activeRows.length) {
      lines.push("", "Active check(s):");
      activeRows.slice(0, 6).forEach((item) => lines.push(`- ${item.name || "unknown"}: ${item.detail || item.status || ""}`));
    }
    if (optionalWarnings.length || warnings.length) {
      lines.push("", "Warning check(s):");
      optionalWarnings.slice(0, 6).forEach((item) => lines.push(`- ${item.name || "unknown"}: ${item.detail || item.status || ""}`));
      warnings.slice(0, 4).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("");
    if (!rowList.length) {
      lines.push("Next step: run a health check before planning or creating a deployment package.");
    } else if (requiredMissing.length || Number(payload.missing_count || 0) > 0) {
      lines.push("Next step: fix required missing tools/paths before trusting deployment or backfill output.");
    } else if (activeRows.length) {
      lines.push("Next step: let active backend work finish, or inspect Home progress, Diagnostics ActiveJobs, and Run Logs before closing or starting maintenance dry-run work.");
    } else if (optionalWarnings.length || Number(payload.warning_count || 0) > 0 || warnings.length) {
      lines.push("Next step: deployment plans can still be useful, but review optional warning rows before packaging.");
    } else {
      lines.push("Next step: maintenance health looks ready for Preview Deployment or Create Deployment.");
    }
    lines.push("", ...maintenanceRealMediaBoundaryLines());
    lines.push("Mutation guardrail: Create Deployment may write only deployment artifacts through the backend release builder. Backfill remains dry-run from this shell.");
    return lines;
  }

  function renderMaintenanceReadiness(maintenance, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setMaintenanceStatusText("maintenance-readiness-status", maintenanceReadinessStatus(maintenance || {}, rowList));
    setText("maintenance-readiness", maintenanceReadinessLines(maintenance || {}, rowList).join("\n"));
  }

  function renderMaintenanceReadinessError(message) {
    setMaintenanceStatusText("maintenance-readiness-status", "Unavailable", "blocked");
    setText(
      "maintenance-readiness",
      [
        "Status: unavailable",
        `Error: ${message || "Maintenance health check failed."}`,
        "Next step: open Diagnostics and Run Logs before trusting release or backfill dry-run results.",
      ].join("\n")
    );
    renderDryRunConfidence();
  }

    return {
      selectMaintenanceRow,
      renderMaintenance,
      maintenanceProgressStatus,
      maintenanceProgressStepLines,
      maintenanceHealthErrorProgress,
      renderMaintenanceHealthProgress,
      pollMaintenanceProgress,
      startMaintenanceProgressPolling,
      stopMaintenanceProgressPolling,
      maintenanceDiagnosticsActionsForRow,
      renderMaintenanceDiagnosticsActions,
      maintenanceDetailLines,
      renderMaintenanceDetail,
      renderMaintenanceRows,
      maintenanceRequiredMissingRows,
      maintenanceOptionalWarningRows,
      maintenanceActiveRows,
      maintenanceReadinessStatus,
      activateQuickLink,
      maintenanceRealMediaBoundaryLines,
      maintenanceToolchainStatus,
      maintenanceToolchainLines,
      renderMaintenanceToolchain,
      maintenanceReadinessLines,
      renderMaintenanceReadiness,
      renderMaintenanceReadinessError,
    };
  }

  window.__maintenanceHealthModule = { createMaintenanceHealth };
})();