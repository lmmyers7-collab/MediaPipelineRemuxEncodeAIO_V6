/* global commandHistoryCompactEvidenceLine, getCommandHistory */
(function () {
  function createMaintenanceDryRunReadiness(deps) {
    const {
      state,
      commandHistoryView,
      changeLedgerRowLimit: CHANGE_LEDGER_ROW_LIMIT,
      changeLedgerRefreshTimeoutMs: CHANGE_LEDGER_REFRESH_TIMEOUT_MS,
      setMaintenanceStatusText,
      renderChangeLedger,
      renderChangeLedgerDetail,
      renderMaintenance,
      maintenanceHealthErrorProgress,
      renderMaintenanceHealthProgress,
      renderMaintenanceReadinessError,
      renderDryRunProgressStart,
      stopMaintenanceProgressPolling,
      maintenanceReadinessStatus,
      maintenanceRequiredMissingRows,
      maintenanceOptionalWarningRows,
      maintenanceActiveRows,
      maintenanceRealMediaBoundaryLines,
      getReleaseDryRunRequest,
      getReleasePreviewMatchesCreate,
    } = deps;
  function isMaintenanceDryRunCommand(item) {
    const command = String(item?.command || "").toLowerCase();
    return command === "maintenance.release_dry_run" || command === "maintenance.release_build" || command === "maintenance.completed_backfill_dry_run" || command === "maintenance.dependency_atlas";
  }

  function maintenanceDryRunLabel(command) {
    if (command === "maintenance.release_dry_run") return "Release dry run";
    if (command === "maintenance.release_build") return "Deployment build";
    if (command === "maintenance.completed_backfill_dry_run") return "Completed manifest backfill dry run";
    if (command === "maintenance.dependency_atlas") return "Dependency atlas";
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
    if (data.manifest_created !== undefined) bits.push(`manifest created ${data.manifest_created === true ? "yes" : "no"}`);
    if (data.manifest_changed !== undefined) bits.push(`manifest changed ${data.manifest_changed === true ? "yes" : "no"}`);
    if (data.zip_created !== undefined) bits.push(`zip created ${data.zip_created === true ? "yes" : "no"}`);
    if (data.zip_changed !== undefined) bits.push(`zip changed ${data.zip_changed === true ? "yes" : "no"}`);
    if (data.sidecars_ingested !== undefined) bits.push(`${data.sidecars_ingested} sidecar(s)`);
    if (data.skipped_bad_json !== undefined) bits.push(`${data.skipped_bad_json} bad JSON skipped`);
    if (data.modules !== undefined) bits.push(`${data.modules} module(s)`);
    if (data.detail_diagrams !== undefined) bits.push(`${data.detail_diagrams} diagram(s)`);
    if (data.html_links_checked !== undefined) bits.push(`${data.html_links_checked} link(s) checked`);
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
    if (typeof commandHistoryView.renderCompactCommandHistoryBlock === "function") {
      commandHistoryView.renderCompactCommandHistoryBlock({
        history,
        filter: isMaintenanceDryRunCommand,
        limit: 5,
        targetId: "maintenance-dry-run-history",
        statusId: "maintenance-dry-run-history-status",
        statusText: (entries) => `${entries.length} run${entries.length === 1 ? "" : "s"}`,
        itemLabel: "maintenance command",
        emptyHistoryText: "No maintenance commands recorded yet. Run Preview Deployment, Create Deployment, Backfill Dry Run, or Update Atlas to see backend command results here.",
        emptyMatchText: "No maintenance commands recorded yet. Run Preview Deployment, Create Deployment, Backfill Dry Run, or Update Atlas to see backend command results here.",
        lineFor: formatMaintenanceDryRunHistoryLine,
        header: false,
      });
      renderMaintenanceDryRunConfidence(history);
      return;
    }
    const entries = Array.isArray(history) ? history.filter(isMaintenanceDryRunCommand).slice(0, 5) : [];
    setText(
      "maintenance-dry-run-history-status",
      `${entries.length} run${entries.length === 1 ? "" : "s"}`
    );
    if (!entries.length) {
      setText(
        "maintenance-dry-run-history",
        "No maintenance commands recorded yet. Run Preview Deployment, Create Deployment, Backfill Dry Run, or Update Atlas to see backend command results here."
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
    const rows = Array.isArray(state.lastMaintenance?.rows) ? state.lastMaintenance.rows : [];
    const readiness = maintenanceReadinessStatus(state.lastMaintenance || {}, rows);
    if (readiness === "Unavailable" || readiness === "Blocked") return readiness;
    const latest = maintenanceLatestDryRun(history);
    if (latest && latest.ok === false) return "Dry-run failed";
    if (latest && latest.ok === true && readiness === "Ready") return "Ready";
    if (latest && latest.ok === true) return "Review";
    if (readiness === "Ready") return "Ready for dry run";
    if (readiness === "Active") return "Active";
    if (readiness === "Warnings") return "Review";
    return "Not checked";
  }

  function maintenanceReleaseOptionReviewLines() {
    const request = getReleaseDryRunRequest();
    const previewMatches = getReleasePreviewMatchesCreate(request);
    const lines = [
      "Deployment option review:",
      `- Destination: ${request.destination_root || "blank; backend should use timestamped default"}`,
      `- Zip package: ${request.zip_package ? "yes; preview reports the zip plan, Create writes it" : "no"}`,
      `- Verify package: ${request.verify ? "yes" : "no"}`,
      `- Include tests: ${request.include_tests ? "yes" : "no"}`,
      `- Include dev docs: ${request.include_dev_docs ? "yes" : "no"}`,
      `- Include optional tools: ${request.include_optional_tools ? "yes" : "no"}`,
      `- Include bundled tool docs: ${request.include_tool_docs ? "yes" : "no"}`,
      `- Include Tauri launcher: ${request.include_tauri_preview_binary ? "yes; required for package-mode launch" : "no"}`,
      `- Keep personal config: ${request.keep_personal_config ? "yes; review before sharing package output" : "no"}`,
      `- Replace existing destination on create: ${request.force ? "yes; preview and create use the same force option" : "no"}`,
      `- Latest matching preview: ${previewMatches ? "yes; same destination/options completed successfully" : state.lastReleasePreviewSignature ? "no; current destination/options changed or latest preview failed" : "no successful preview recorded in this shell"}`,
    ];
    if (!request.verify) {
      lines.push("- Warning: verify is disabled, so dry-run package confidence is weaker.");
    }
    if (request.keep_personal_config) {
      lines.push("- Warning: keeping personal config is useful for local migration checks but risky for shareable packages.");
    }
    if (!request.include_tauri_preview_binary) {
      lines.push("- Warning: Tauri launcher is disabled, so the deployment folder will need an alternate launcher path.");
    }
    if (request.include_optional_tools || request.include_tool_docs) {
      lines.push("- Note: optional payloads increase package surface; compare against release manifest before distribution.");
    }
    if (!previewMatches) {
      lines.push("- Warning: run Preview Deployment with these exact options before Create Deployment, or the create confirmation will call out the mismatch.");
    }
    return lines;
  }

  function maintenanceDryRunConfidenceLines(history = []) {
    const rows = Array.isArray(state.lastMaintenance?.rows) ? state.lastMaintenance.rows : [];
    const readiness = maintenanceReadinessStatus(state.lastMaintenance || {}, rows);
    const requiredMissing = maintenanceRequiredMissingRows(rows);
    const optionalWarnings = maintenanceOptionalWarningRows(rows);
    const activeRows = maintenanceActiveRows(rows);
    const latest = maintenanceLatestDryRun(history);
    const lines = [
      "Maintenance dry-run confidence:",
      `Health readiness: ${readiness}`,
      `Checks loaded: ${rows.length}`,
      `Required missing/blocking: ${requiredMissing.length || state.lastMaintenance?.missing_count || 0}`,
      `Active process guard rows: ${activeRows.length}`,
      `Optional warnings: ${optionalWarnings.length || state.lastMaintenance?.warning_count || 0}`,
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
    } else if (readiness === "Active") {
      lines.push("- Active backend work is running. Let it finish, or inspect Home progress, Diagnostics ActiveJobs, and Run Logs before maintenance dry-run decisions.");
    } else if (readiness === "Warnings") {
      lines.push("- Dry runs can still be useful, but review optional warning rows and diagnostics handoff first.");
    } else if (latest && latest.ok === false) {
      lines.push("- The latest dry run failed. Read the command detail, stderr/stdout, and Diagnostics before packaging decisions.");
    } else if (latest && latest.ok === true) {
      lines.push("- Latest maintenance command completed. Review output paths, manifest/zip status, and diagnostics before relying on deployment artifacts.");
    } else {
      lines.push("- Health looks ready for a deployment preview. Run Preview Deployment before Create Deployment unless you already know the destination/options are correct.");
    }
    lines.push("", ...maintenanceRealMediaBoundaryLines());
    lines.push("Mutation guardrail: Create Deployment may write a release folder/manifest/zip through the backend release builder only. Backfill remains dry-run; Maintenance must not repair files, rewrite completed manifests, or mutate media.");
    return lines;
  }

  function renderMaintenanceDryRunConfidence(history = null) {
    const entries = Array.isArray(history) ? history : typeof getCommandHistory === "function" ? getCommandHistory() : [];
    setMaintenanceStatusText("maintenance-dry-run-confidence-status", maintenanceDryRunConfidenceStatus(entries));
    setText("maintenance-dry-run-confidence", maintenanceDryRunConfidenceLines(entries).join("\n"));
  }

  async function refreshChangeLedger() {
    if (state.changeLedgerRefreshInFlight) return;
    state.changeLedgerRefreshInFlight = true;
    const button = byId("maintenance-change-ledger-refresh-button");
    if (button) button.disabled = true;
    setMaintenanceStatusText("maintenance-change-ledger-status", "Loading...", "running");
    try {
      renderChangeLedger(await apiGet(`/api/maintenance/change-ledger?limit=${CHANGE_LEDGER_ROW_LIMIT}`, {
        timeoutMs: CHANGE_LEDGER_REFRESH_TIMEOUT_MS,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setMaintenanceStatusText("maintenance-change-ledger-status", "Error", "blocked");
      setText("maintenance-change-ledger-summary", `Change ledger unavailable: ${message}`);
      clearRows(byId("maintenance-change-ledger-rows"), 6, message);
      setMaintenanceStatusText("maintenance-change-ledger-table-status", "Error", "blocked");
      setMaintenanceStatusText("maintenance-change-ledger-hygiene-status", "Unavailable", "blocked");
      setText("maintenance-change-ledger-hygiene", `Change ledger hygiene unavailable: ${message}`);
      renderChangeLedgerDetail(null);
    } finally {
      state.changeLedgerRefreshInFlight = false;
      if (button) button.disabled = false;
    }
  }

  async function refreshMaintenance() {
    if (state.maintenanceRefreshInFlight) {
      state.maintenanceRefreshQueued = true;
      return;
    }
    state.maintenanceRefreshInFlight = true;
    const button = byId("maintenance-refresh-button");
    if (button) button.disabled = true;
    setMaintenanceStatusText("maintenance-status", "Checking...", "running");
    setMaintenanceStatusText("maintenance-progress-status", "Active", "running");
    setText("maintenance-progress-steps", "Starting backend Maintenance health check. Progress will update from /api/maintenance/progress while probes run.");
    renderDryRunProgressStart();
    try {
      renderMaintenance(await apiGet("/api/maintenance"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.lastMaintenance = {
        error: message,
        rows: [],
        warnings: [`Maintenance health check failed: ${message}`],
        health_progress: maintenanceHealthErrorProgress(message),
      };
      setText("maintenance-ok-count", "0");
      setText("maintenance-missing-count", "0");
      setText("maintenance-warning-count", "1");
      setText("maintenance-total-count", "0");
      setMaintenanceStatusText("maintenance-status", "Error", "blocked");
      renderMaintenanceHealthProgress(state.lastMaintenance.health_progress);
      renderMaintenanceReadinessError(message);
      setText("maintenance-warnings", `Maintenance health check failed: ${message}`);
      clearRows(byId("maintenance-rows"), 5, message);
      renderMaintenanceDryRunConfidence();
    } finally {
      stopMaintenanceProgressPolling();
      state.maintenanceRefreshInFlight = false;
      if (button) button.disabled = false;
      if (state.maintenanceRefreshQueued) {
        state.maintenanceRefreshQueued = false;
        window.setTimeout(refreshMaintenance, 0);
      }
    }
  }

    return {
      isMaintenanceDryRunCommand,
      maintenanceDryRunLabel,
      maintenanceDryRunDetailLine,
      formatMaintenanceDryRunHistoryLine,
      renderMaintenanceDryRunHistory,
      maintenanceLatestDryRun,
      maintenanceDryRunConfidenceStatus,
      maintenanceReleaseOptionReviewLines,
      maintenanceDryRunConfidenceLines,
      renderMaintenanceDryRunConfidence,
      refreshChangeLedger,
      refreshMaintenance,
    };
  }

  window.__maintenanceDryRunReadinessModule = { createMaintenanceDryRunReadiness };
})();
