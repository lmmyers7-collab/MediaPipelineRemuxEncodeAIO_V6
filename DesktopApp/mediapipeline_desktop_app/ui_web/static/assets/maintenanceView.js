(function () {
  let lastMaintenance = null;
  let selectedMaintenanceRowKey = "";
  let maintenanceRefreshInFlight = false;
  let maintenanceRefreshQueued = false;
  let maintenanceProgressPollTimer = null;
  const maintenanceDryRunButtonIds = [
    "release-dry-run-button",
    "release-build-button",
    "backfill-dry-run-button",
  ];
  let maintenanceDryRunInFlight = false;

  function setMaintenanceDryRunBusy(isBusy) {
    maintenanceDryRunInFlight = Boolean(isBusy);
    maintenanceDryRunButtonIds.forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = maintenanceDryRunInFlight;
    });
  }

  function rejectMaintenanceDryRunWhileBusy(command, statusId, detailId) {
    if (!maintenanceDryRunInFlight) return false;
    const result = {
      command,
      ok: false,
      severity: "warning",
      message: "Another maintenance command is already in progress.",
    };
    appendCommandResult(result);
    setText(statusId, "Busy");
    if (detailId) setText(detailId, result.message);
    return true;
  }

  function hasMaintenanceLoaded() {
    return lastMaintenance !== null;
  }

  function getLastMaintenance() {
    return lastMaintenance || {};
  }

  function maintenanceRowKey(item) {
    return String(item?.row_key || item?.name || "").trim();
  }

  function getSelectedMaintenanceRow() {
    const rows = Array.isArray(lastMaintenance?.rows) ? lastMaintenance.rows : [];
    return rows.find((item) => maintenanceRowKey(item) === selectedMaintenanceRowKey) || null;
  }

  function selectMaintenanceRow(item) {
    selectedMaintenanceRowKey = maintenanceRowKey(item);
    renderMaintenanceDetail(item || null);
    renderMaintenanceRows(Array.isArray(lastMaintenance?.rows) ? lastMaintenance.rows : []);
  }

  function renderMaintenance(maintenance) {
    lastMaintenance = maintenance || {};
    const rows = Array.isArray(lastMaintenance.rows) ? lastMaintenance.rows : [];
    const warnings = Array.isArray(lastMaintenance.warnings) ? lastMaintenance.warnings : [];
    setText("maintenance-ok-count", String(lastMaintenance.ok_count || 0));
    setText("maintenance-missing-count", String(lastMaintenance.missing_count || 0));
    setText("maintenance-warning-count", String(lastMaintenance.warning_count || warnings.length || 0));
    setText("maintenance-total-count", String(rows.length));
    setText("maintenance-status", rows.length ? `${rows.length} check${rows.length === 1 ? "" : "s"}` : "No rows");
    renderMaintenanceHealthProgress(lastMaintenance.health_progress || { progress_bars: lastMaintenance.progress_bars || [] });
    renderMaintenanceReadiness(lastMaintenance, rows);
    renderMaintenanceToolchain(lastMaintenance.toolchain_evidence || {});
    setText("maintenance-warnings", warnings.join("\n") || "No maintenance warnings.");
    renderMaintenanceDetail(getSelectedMaintenanceRow());
    renderMaintenanceRows(rows);
    renderMaintenanceDryRunConfidence();
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

  function renderMaintenanceHealthProgress(progress) {
    const payload = progress || {};
    const bars = Array.isArray(payload.progress_bars) ? payload.progress_bars : [];
    setText("maintenance-progress-status", maintenanceProgressStatus(payload));
    if (typeof renderProgressBarsInto === "function") {
      renderProgressBarsInto("maintenance-progress-bars", bars, payload, "No maintenance health progress loaded.");
    } else {
      setText("maintenance-progress-bars", bars.length ? bars.map((bar) => `${bar.label || bar.id || "Progress"}: ${bar.status || "unknown"} ${bar.percent ?? ""}%`).join("\n") : "No maintenance health progress loaded.");
    }
    setText("maintenance-progress-steps", maintenanceProgressStepLines(payload).join("\n"));
  }

  function stopMaintenanceProgressPolling() {
    if (maintenanceProgressPollTimer !== null) {
      window.clearInterval(maintenanceProgressPollTimer);
      maintenanceProgressPollTimer = null;
    }
  }

  async function pollMaintenanceProgress() {
    try {
      renderMaintenanceHealthProgress(await apiGet("/api/maintenance/progress"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("maintenance-progress-status", "Unavailable");
      setText("maintenance-progress-steps", `Maintenance health progress unavailable: ${message}`);
    }
  }

  function startMaintenanceProgressPolling() {
    stopMaintenanceProgressPolling();
    pollMaintenanceProgress();
    maintenanceProgressPollTimer = window.setInterval(pollMaintenanceProgress, 750);
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
    if (typeof appendDiagnosticsBridgeGroupedButtons === "function") {
      appendDiagnosticsBridgeGroupedButtons(container, actions, {
        datasetPrefix: "maintenanceDiagnostics",
        onAction: requestMaintenanceDiagnosticsAction,
      });
      appendDiagnosticsBridgeButton(container, actions, `Maintenance check ${item.name || ""}`);
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
    if (typeof diagnosticsBridgeRowTrustLines === "function") {
      lines.push(...diagnosticsBridgeRowTrustLines(`Maintenance check ${item.name || ""}`, actions, {
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
    setText("maintenance-detail-status", item ? (item.operator_status || item.status || "selected") : "No selection");
    setText("maintenance-detail", maintenanceDetailLines(item || null).join("\n"));
  }

  function renderMaintenanceRows(rows) {
    const tbody = byId("maintenance-rows");
    if (!tbody) return;
    if (!rows.length) {
      const warnings = Array.isArray(lastMaintenance?.warnings) ? lastMaintenance.warnings : [];
      clearRows(tbody, 3, warnings.join(" | ") || "No maintenance checks loaded.");
      updateTableStatusLegend("maintenance-table-legend", tbody, "Maintenance rows");
      renderMaintenanceDetail(null);
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.status === "ok" ? "match" : item.status === "warning" ? "warning" : "blocked";
      appendCells(row, [
        item.status || "",
        item.name || "",
        item.detail || "",
      ]);
      makeRowSelectable(row, () => selectMaintenanceRow(item), {
        selected: Boolean(maintenanceRowKey(item) && maintenanceRowKey(item) === selectedMaintenanceRowKey),
        label: `Maintenance check ${item.name || item.status || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("maintenance-table-legend", tbody, "Maintenance rows");
  }

  function maintenanceRequiredMissingRows(rows) {
    return rows.filter((item) => item?.status !== "ok" && item?.optional !== true);
  }

  function maintenanceOptionalWarningRows(rows) {
    return rows.filter((item) => item?.status !== "ok" && item?.optional === true);
  }

  function maintenanceReadinessStatus(maintenance, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (maintenance?.error) return "Unavailable";
    if (!rowList.length) return "Not checked";
    if (maintenanceRequiredMissingRows(rowList).length || Number(maintenance?.missing_count || 0) > 0) return "Blocked";
    const warnings = Array.isArray(maintenance?.warnings) ? maintenance.warnings.filter(Boolean) : [];
    if (maintenanceOptionalWarningRows(rowList).length || Number(maintenance?.warning_count || 0) > 0 || warnings.length) return "Warnings";
    return "Ready";
  }

  function maintenanceRealMediaBoundaryLines() {
    return [
      "Real-media validation boundary:",
      "- Maintenance health and dry-run commands prove packaging/backfill environment posture only.",
      "- They do not prove FFmpeg route correctness, subtitle OCR/SRT output, audio selection, source stability, copy-to-scratch behavior, size guard results, completed sidecars, or pending-publish completion for real media.",
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
    lines.push("", "Real-media boundary: toolchain readiness does not prove FFmpeg route correctness, subtitle/audio output, size guard behavior, Completed sidecars, or Pending Publish completion for a real media file.");
    lines.push("Mutation guardrail: WebView does not resolve arbitrary tools, edit PATH, install dependencies, launch media jobs, or mutate files from this panel.");
    return lines;
  }

  function renderMaintenanceToolchain(evidence) {
    setText("maintenance-toolchain-status", maintenanceToolchainStatus(evidence || {}));
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
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const lines = [
      `Checks loaded: ${rowList.length}`,
      `OK: ${payload.ok_count || 0}`,
      `Required missing/blocking: ${requiredMissing.length || payload.missing_count || 0}`,
      `Optional warnings: ${optionalWarnings.length || payload.warning_count || warnings.length || 0}`,
    ];
    if (requiredMissing.length) {
      lines.push("", "Blocking check(s):");
      requiredMissing.slice(0, 6).forEach((item) => lines.push(`- ${item.name || "unknown"}: ${item.detail || item.status || ""}`));
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
    } else if (optionalWarnings.length || Number(payload.warning_count || 0) > 0 || warnings.length) {
      lines.push("Next step: deployment plans can still be useful, but review optional warning rows before packaging.");
    } else {
      lines.push("Next step: maintenance health looks ready for Plan Deployment or Create Deployment.");
    }
    lines.push("", ...maintenanceRealMediaBoundaryLines());
    lines.push("Mutation guardrail: Create Deployment may write only deployment artifacts through the backend release builder. Backfill remains dry-run from this shell.");
    return lines;
  }

  function renderMaintenanceReadiness(maintenance, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("maintenance-readiness-status", maintenanceReadinessStatus(maintenance || {}, rowList));
    setText("maintenance-readiness", maintenanceReadinessLines(maintenance || {}, rowList).join("\n"));
  }

  function renderMaintenanceReadinessError(message) {
    setText("maintenance-readiness-status", "Unavailable");
    setText(
      "maintenance-readiness",
      [
        "Status: unavailable",
        `Error: ${message || "Maintenance health check failed."}`,
        "Next step: open Diagnostics and Run Logs before trusting release or backfill dry-run results.",
      ].join("\n")
    );
    renderMaintenanceDryRunConfidence();
  }

  function isMaintenanceDryRunCommand(item) {
    const command = String(item?.command || "").toLowerCase();
    return command === "maintenance.release_dry_run" || command === "maintenance.release_build" || command === "maintenance.completed_backfill_dry_run";
  }

  function maintenanceDryRunLabel(command) {
    if (command === "maintenance.release_dry_run") return "Release dry run";
    if (command === "maintenance.release_build") return "Deployment build";
    if (command === "maintenance.completed_backfill_dry_run") return "Completed manifest backfill dry run";
    return command || "Maintenance dry run";
  }

  function maintenanceDryRunDetailLine(item) {
    const raw = item?.raw && typeof item.raw === "object" ? item.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const bits = [];
    if (data.returncode !== undefined) bits.push(`return ${data.returncode}`);
    if (data.elapsed_seconds !== undefined) bits.push(`${Number(data.elapsed_seconds || 0).toFixed(1)}s`);
    if (data.manifest_exists !== undefined) bits.push(`manifest ${data.manifest_exists === true ? "yes" : "no"}`);
    if (data.zip_exists !== undefined) bits.push(`zip ${data.zip_exists === true ? "yes" : "no"}`);
    if (data.sidecars_ingested !== undefined) bits.push(`${data.sidecars_ingested} sidecar(s)`);
    if (data.skipped_bad_json !== undefined) bits.push(`${data.skipped_bad_json} bad JSON skipped`);
    return bits.length ? ` (${bits.join("; ")})` : "";
  }

  function formatMaintenanceDryRunHistoryLine(item) {
    const command = String(item?.command || "");
    const detail = maintenanceDryRunDetailLine(item);
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(item, {
        label: (value) => maintenanceDryRunLabel(value),
        detail,
      });
    }
    const status = item?.result || (item?.ok ? "OK" : item?.severity || "Result");
    const message = item?.message || "";
    return `${item?.at || ""} ${maintenanceDryRunLabel(command)} [${status}] ${message}${detail}`.trim();
  }

  function renderMaintenanceDryRunHistory(history = []) {
    const entries = Array.isArray(history) ? history.filter(isMaintenanceDryRunCommand).slice(0, 5) : [];
    setText(
      "maintenance-dry-run-history-status",
      `${entries.length} run${entries.length === 1 ? "" : "s"}`
    );
    if (!entries.length) {
      setText(
        "maintenance-dry-run-history",
        "No maintenance commands recorded yet. Run Plan Deployment, Create Deployment, or Backfill Dry Run to see backend command results here."
      );
      renderMaintenanceDryRunConfidence(history);
      return;
    }
    setText("maintenance-dry-run-history", entries.map(formatMaintenanceDryRunHistoryLine).join("\n"));
    renderMaintenanceDryRunConfidence(history);
  }

  function maintenanceLatestDryRun(history = []) {
    const entries = Array.isArray(history) ? history.filter(isMaintenanceDryRunCommand) : [];
    return entries.length ? entries[0] : null;
  }

  function maintenanceDryRunConfidenceStatus(history = []) {
    const rows = Array.isArray(lastMaintenance?.rows) ? lastMaintenance.rows : [];
    const readiness = maintenanceReadinessStatus(lastMaintenance || {}, rows);
    if (readiness === "Unavailable" || readiness === "Blocked") return readiness;
    const latest = maintenanceLatestDryRun(history);
    if (latest && latest.ok === false) return "Dry-run failed";
    if (latest && latest.ok === true && readiness === "Ready") return "Ready";
    if (latest && latest.ok === true) return "Review";
    if (readiness === "Ready") return "Ready for dry run";
    if (readiness === "Warnings") return "Review";
    return "Not checked";
  }

  function maintenanceReleaseOptionReviewLines() {
    const request = collectReleaseDryRunRequest();
    const lines = [
      "Deployment option review:",
      `- Destination: ${request.destination_root || "blank; backend should use timestamped default"}`,
      `- Plan zip: ${request.zip_package ? "yes" : "no"}`,
      `- Plan verify: ${request.verify ? "yes" : "no"}`,
      `- Include tests: ${request.include_tests ? "yes" : "no"}`,
      `- Include dev docs: ${request.include_dev_docs ? "yes" : "no"}`,
      `- Include optional tools: ${request.include_optional_tools ? "yes" : "no"}`,
      `- Include bundled tool docs: ${request.include_tool_docs ? "yes" : "no"}`,
      `- Keep personal config: ${request.keep_personal_config ? "yes; review before sharing package output" : "no"}`,
      `- Replace existing destination on create: ${Boolean(byId("release-build-force")?.checked) ? "yes" : "no"}`,
    ];
    if (!request.verify) {
      lines.push("- Warning: verify is disabled, so dry-run package confidence is weaker.");
    }
    if (request.keep_personal_config) {
      lines.push("- Warning: keeping personal config is useful for local migration checks but risky for shareable packages.");
    }
    if (request.include_optional_tools || request.include_tool_docs) {
      lines.push("- Note: optional payloads increase package surface; compare against release manifest before distribution.");
    }
    return lines;
  }

  function maintenanceDryRunConfidenceLines(history = []) {
    const rows = Array.isArray(lastMaintenance?.rows) ? lastMaintenance.rows : [];
    const readiness = maintenanceReadinessStatus(lastMaintenance || {}, rows);
    const requiredMissing = maintenanceRequiredMissingRows(rows);
    const optionalWarnings = maintenanceOptionalWarningRows(rows);
    const latest = maintenanceLatestDryRun(history);
    const lines = [
      "Maintenance dry-run confidence:",
      `Health readiness: ${readiness}`,
      `Checks loaded: ${rows.length}`,
      `Required missing/blocking: ${requiredMissing.length || lastMaintenance?.missing_count || 0}`,
      `Optional warnings: ${optionalWarnings.length || lastMaintenance?.warning_count || 0}`,
      `Latest dry run: ${latest ? formatMaintenanceDryRunHistoryLine(latest) : "none recorded in current command history"}`,
      "",
      ...maintenanceReleaseOptionReviewLines(),
      "",
      "Safe interpretation:",
    ];
    if (readiness === "Unavailable") {
      lines.push("- Maintenance health is unavailable. Open Diagnostics and Run Logs before trusting dry-run output.");
    } else if (readiness === "Blocked") {
      lines.push("- Required health checks are missing. Dry-run output may be incomplete or misleading.");
    } else if (readiness === "Warnings") {
      lines.push("- Dry runs can still be useful, but review optional warning rows and diagnostics handoff first.");
    } else if (latest && latest.ok === false) {
      lines.push("- The latest dry run failed. Read the command detail, stderr/stdout, and Diagnostics before packaging decisions.");
    } else if (latest && latest.ok === true) {
      lines.push("- Latest maintenance command completed. Review output paths, manifest/zip status, and diagnostics before relying on deployment artifacts.");
    } else {
      lines.push("- Health looks ready for a deployment plan. Run Plan Deployment before Create Deployment unless you already know the destination/options are correct.");
    }
    lines.push("", ...maintenanceRealMediaBoundaryLines());
    lines.push("Mutation guardrail: Create Deployment may write a release folder/manifest/zip through the backend release builder only. Backfill remains dry-run; Maintenance must not repair files, rewrite completed manifests, or mutate media.");
    return lines;
  }

  function renderMaintenanceDryRunConfidence(history = []) {
    setText("maintenance-dry-run-confidence-status", maintenanceDryRunConfidenceStatus(history));
    setText("maintenance-dry-run-confidence", maintenanceDryRunConfidenceLines(history).join("\n"));
  }

  async function refreshMaintenance() {
    if (maintenanceRefreshInFlight) {
      maintenanceRefreshQueued = true;
      return;
    }
    maintenanceRefreshInFlight = true;
    const button = byId("maintenance-refresh-button");
    if (button) button.disabled = true;
    setText("maintenance-status", "Checking...");
    setText("maintenance-progress-status", "Active");
    setText("maintenance-progress-steps", "Starting backend Maintenance health check. Progress will update from /api/maintenance/progress while probes run.");
    startMaintenanceProgressPolling();
    try {
      renderMaintenance(await apiGet("/api/maintenance"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("maintenance-status", "Error");
      renderMaintenanceReadinessError(message);
      setText("maintenance-warnings", `Maintenance health check failed: ${message}`);
      clearRows(byId("maintenance-rows"), 3, message);
      renderMaintenanceDryRunConfidence();
    } finally {
      stopMaintenanceProgressPolling();
      maintenanceRefreshInFlight = false;
      if (button) button.disabled = false;
      if (maintenanceRefreshQueued) {
        maintenanceRefreshQueued = false;
        window.setTimeout(refreshMaintenance, 0);
      }
    }
  }

  function collectReleaseDryRunRequest() {
    return {
      destination_root: byId("release-dry-run-destination")?.value || "",
      zip_package: Boolean(byId("release-dry-run-zip")?.checked),
      verify: Boolean(byId("release-dry-run-verify")?.checked),
      include_tests: Boolean(byId("release-dry-run-tests")?.checked),
      include_dev_docs: Boolean(byId("release-dry-run-dev-docs")?.checked),
      include_optional_tools: Boolean(byId("release-dry-run-optional-tools")?.checked),
      include_tool_docs: Boolean(byId("release-dry-run-tool-docs")?.checked),
      keep_personal_config: Boolean(byId("release-dry-run-keep-config")?.checked),
      timeout_seconds: 900,
    };
  }

  function collectReleaseBuildRequest() {
    return {
      ...collectReleaseDryRunRequest(),
      force: Boolean(byId("release-build-force")?.checked),
      confirm_create: true,
      timeout_seconds: 7200,
    };
  }

  function initMaintenanceViewEvents() {
    [
      "release-dry-run-destination",
      "release-dry-run-zip",
      "release-dry-run-verify",
      "release-dry-run-tests",
      "release-dry-run-dev-docs",
      "release-dry-run-optional-tools",
      "release-dry-run-tool-docs",
      "release-dry-run-keep-config",
      "release-build-force",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", () => renderMaintenanceDryRunConfidence());
      element.addEventListener("change", () => renderMaintenanceDryRunConfidence());
    });
    renderMaintenanceDryRunConfidence();
  }

  function renderReleaseDryRunResult(result) {
    const data = result?.data || {};
    renderReleasePackageProgress(result);
    const lines = [
      "Dry-run trust summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run === true ? "yes" : "unknown"}`,
      `Writes manifest: ${data.manifest_exists === true ? "unexpected yes" : "no"}`,
      `Writes zip: ${data.zip_exists === true ? "unexpected yes" : "no"}`,
      `Safe next action: ${result?.ok ? "Review planned copy counts/options, destination, and package options before Create Deployment." : "Read errors and Diagnostics before trusting release packaging."}`,
      "Guardrail: this WebView action must remain a backend dry-run command; it must not create release folders, zips, manifests, or copy payloads.",
      "Real-media boundary: release dry-run output does not validate FFmpeg, subtitle OCR/SRT, audio routing, output size, completed sidecars, or pending-publish behavior on media files.",
      "",
      result?.message || "Release dry run completed.",
      "",
      `Destination: ${data.destination_root || ""}`,
      `Return code: ${data.returncode ?? ""}`,
      `Elapsed: ${Number(data.elapsed_seconds || 0).toFixed(1)}s`,
      `Manifest written: ${data.manifest_exists === true ? "yes" : "no"}`,
      `Zip written: ${data.zip_exists === true ? "yes" : "no"}`,
      `Command: ${data.command || ""}`,
    ];
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    if (data.stdout) {
      lines.push("", "STDOUT", data.stdout);
    }
    if (data.stderr) {
      lines.push("", "STDERR", data.stderr);
    }
    setText("release-dry-run-detail", lines.join("\n"));
  }

  function releasePackageProgressBars(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.release_progress && typeof data.release_progress === "object" ? data.release_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
    return [];
  }

  function renderReleasePackageProgress(result, targetId = "release-dry-run-progress-bars") {
    if (typeof renderProgressBarsInto !== "function") return;
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.release_progress && typeof data.release_progress === "object" ? data.release_progress : {};
    renderProgressBarsInto(targetId, releasePackageProgressBars(result), progress, "No release package progress loaded.");
  }

  async function runReleaseDryRun() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.release_dry_run", "release-dry-run-status", "release-dry-run-detail")) return;
    const request = collectReleaseDryRunRequest();
    setMaintenanceDryRunBusy(true);
    setText("release-dry-run-status", "Running...");
    setText("release-dry-run-detail", "Running release builder with -DryRun. No release folder, zip, or manifest will be written.");
    try {
      const result = await apiPost("/api/maintenance/release-dry-run", request);
      appendCommandResult(result);
      setText("release-dry-run-status", result.ok ? "Complete" : result.severity || "Failed");
      renderReleaseDryRunResult(result);
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.release_dry_run",
        ok: false,
        severity: "error",
        message,
      });
      setText("release-dry-run-status", "Error");
      setText("release-dry-run-detail", message);
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  function renderReleaseBuildResult(result) {
    const data = result?.data || {};
    renderReleasePackageProgress(result, "release-build-progress-bars");
    const lines = [
      "Deployment build summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run === false ? "no" : "unexpected/unknown"}`,
      `Writes release package: ${data.writes_release_package === true ? "yes" : "no"}`,
      `Manifest written: ${data.manifest_exists === true ? "yes" : "no"}`,
      `Zip written: ${data.zip_exists === true ? "yes" : "no"}`,
      `Safe next action: ${result?.ok ? "Open the destination, review release_manifest.json, then run package-mode validation before distribution." : "Read errors, stderr/stdout, and Diagnostics before retrying deployment."}`,
      "Guardrail: Create Deployment is backend-owned. The WebView submits options only; it does not copy files, zip folders, write manifests, or delete destinations itself.",
      "Real-media boundary: deployment packaging does not validate FFmpeg routing, subtitle OCR/SRT, audio routing, output size, completed sidecars, or pending-publish behavior on media files.",
      "",
      result?.message || "Deployment build completed.",
      "",
      `Destination: ${data.destination_root || ""}`,
      `Manifest: ${data.manifest_path || ""}`,
      `Zip: ${data.zip_path || ""}`,
      `Return code: ${data.returncode ?? ""}`,
      `Elapsed: ${Number(data.elapsed_seconds || 0).toFixed(1)}s`,
      `Command: ${data.command || ""}`,
    ];
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    if (data.stdout) {
      lines.push("", "STDOUT", data.stdout);
    }
    if (data.stderr) {
      lines.push("", "STDERR", data.stderr);
    }
    setText("release-build-detail", lines.join("\n"));
  }

  async function runReleaseBuild() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.release_build", "release-build-status", "release-build-detail")) return;
    const request = collectReleaseBuildRequest();
    const destination = request.destination_root || "a timestamped folder next to this bundle";
    const zipText = request.zip_package ? "and zip" : "without zip";
    if (!window.confirm(`Create deployment package at ${destination} ${zipText}?\n\nThis will write release files through the backend release builder.`)) return;
    setMaintenanceDryRunBusy(true);
    setText("release-build-status", "Running...");
    setText("release-build-detail", "Creating deployment package through the backend release builder. This may write a release folder, manifest, and optional zip.");
    try {
      const result = await apiPost("/api/maintenance/release-build", request);
      appendCommandResult(result);
      setText("release-build-status", result.ok ? "Complete" : result.severity || "Failed");
      renderReleaseBuildResult(result);
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.release_build",
        ok: false,
        severity: "error",
        message,
      });
      setText("release-build-status", "Error");
      setText("release-build-detail", message);
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  function renderBackfillDryRunResult(result) {
    const data = result?.data || {};
    renderBackfillProgress(result);
    const lines = [
      "Dry-run trust summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run === true ? "yes" : "unknown"}`,
      `Writes completed manifest: ${data.writes_manifest === true ? "unexpected yes" : "no"}`,
      `Safe next action: ${result?.ok ? "Review sidecar and bad-JSON counts before deciding whether a backend-owned real backfill is needed." : "Read errors and Diagnostics before trusting completed-manifest state."}`,
      "Guardrail: this WebView action must remain a backend dry-run command; it must not rewrite completed manifests or checkpoints.",
      "Real-media boundary: completed-manifest backfill dry-run output does not prove media processing, subtitle conversion, audio selection, size policy, or publish completion for new work.",
      "",
      result?.message || "Completed manifest backfill dry run completed.",
      "",
      `Sidecars ingested: ${data.sidecars_ingested || ""}`,
      `Skipped bad JSON: ${data.skipped_bad_json || "0"}`,
      `Manifest: ${data.manifest_path || ""}`,
      `Checkpoint: ${data.checkpoint_path || ""}`,
      `Writes manifest: ${data.writes_manifest === true ? "yes" : "no"}`,
    ];
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    if (data.stdout) {
      lines.push("", "STDOUT", data.stdout);
    }
    setText("backfill-dry-run-detail", lines.join("\n"));
  }

  function backfillProgressBars(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.backfill_progress && typeof data.backfill_progress === "object" ? data.backfill_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
    return [];
  }

  function renderBackfillProgress(result) {
    if (typeof renderProgressBarsInto !== "function") return;
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.backfill_progress && typeof data.backfill_progress === "object" ? data.backfill_progress : {};
    renderProgressBarsInto("backfill-dry-run-progress-bars", backfillProgressBars(result), progress, "No maintenance backfill progress loaded.");
  }

  async function runBackfillDryRun() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.completed_backfill_dry_run", "backfill-dry-run-status", "backfill-dry-run-detail")) return;
    setMaintenanceDryRunBusy(true);
    setText("backfill-dry-run-status", "Running...");
    setText("backfill-dry-run-detail", "Scanning outsource sidecars with -DryRun. The completed manifest will not be rewritten.");
    try {
      const result = await apiPost("/api/maintenance/completed-backfill-dry-run", { timeout_seconds: 600 });
      appendCommandResult(result);
      setText("backfill-dry-run-status", result.ok ? "Complete" : result.severity || "Failed");
      renderBackfillDryRunResult(result);
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.completed_backfill_dry_run",
        ok: false,
        severity: "error",
        message,
      });
      setText("backfill-dry-run-status", "Error");
      setText("backfill-dry-run-detail", message);
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  /**
   * Public namespace for the Maintenance page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineMaintenanceView = {
    hasMaintenanceLoaded,
    getLastMaintenance,
    renderMaintenance,
    renderMaintenanceRows,
    renderMaintenanceDetail,
    renderMaintenanceHealthProgress,
    maintenanceProgressStatus,
    maintenanceProgressStepLines,
    pollMaintenanceProgress,
    startMaintenanceProgressPolling,
    stopMaintenanceProgressPolling,
    maintenanceDetailLines,
    selectMaintenanceRow,
    getSelectedMaintenanceRow,
    maintenanceDiagnosticsActionsForRow,
    renderMaintenanceDiagnosticsActions,
    renderMaintenanceReadiness,
    renderMaintenanceToolchain,
    renderMaintenanceReadinessError,
    maintenanceReadinessStatus,
    maintenanceToolchainStatus,
    maintenanceToolchainLines,
    maintenanceRealMediaBoundaryLines,
    maintenanceReadinessLines,
    maintenanceDryRunConfidenceStatus,
    maintenanceDryRunConfidenceLines,
    renderMaintenanceDryRunConfidence,
    maintenanceReleaseOptionReviewLines,
    refreshMaintenance,
    setMaintenanceDryRunBusy,
    rejectMaintenanceDryRunWhileBusy,
    collectReleaseDryRunRequest,
    collectReleaseBuildRequest,
    initMaintenanceViewEvents,
    renderReleaseDryRunResult,
    renderReleaseBuildResult,
    renderReleasePackageProgress,
    releasePackageProgressBars,
    runReleaseDryRun,
    runReleaseBuild,
    renderBackfillDryRunResult,
    renderBackfillProgress,
    backfillProgressBars,
    isMaintenanceDryRunCommand,
    renderMaintenanceDryRunHistory,
    runBackfillDryRun,
  };
  window.hasMaintenanceLoaded = hasMaintenanceLoaded;
  window.getLastMaintenance = getLastMaintenance;
  window.refreshMaintenance = refreshMaintenance;
  window.initMaintenanceViewEvents = initMaintenanceViewEvents;
  window.runReleaseDryRun = runReleaseDryRun;
  window.runReleaseBuild = runReleaseBuild;
  window.runBackfillDryRun = runBackfillDryRun;
})();
