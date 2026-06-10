(function () {
  const commandHistoryView = window.mediaPipelineCommandHistory || {};
  let lastMaintenance = null;
  let lastChangeLedger = null;
  let selectedMaintenanceRowKey = "";
  let selectedChangeLedgerRowKey = "";
  let maintenanceRefreshInFlight = false;
  let maintenanceRefreshQueued = false;
  let changeLedgerRefreshInFlight = false;
  let maintenanceProgressPollTimer = null;
  const maintenanceDryRunButtonIds = [
    "release-dry-run-button",
    "release-build-button",
    "backfill-dry-run-button",
    "dependency-atlas-button",
  ];
  let maintenanceDryRunInFlight = false;
  let dependencyAtlasOpenInFlight = false;

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

  function setDependencyAtlasOpenBusy(isBusy) {
    dependencyAtlasOpenInFlight = Boolean(isBusy);
    const button = byId("dependency-atlas-open-folder-button");
    if (button) button.disabled = dependencyAtlasOpenInFlight;
  }

  function hasMaintenanceLoaded() {
    return lastMaintenance !== null;
  }

  function getLastMaintenance() {
    return lastMaintenance || {};
  }

  function getLastChangeLedger() {
    return lastChangeLedger || {};
  }

  function changeLedgerRows() {
    return Array.isArray(lastChangeLedger?.rows) ? lastChangeLedger.rows : [];
  }

  function changeLedgerRowKey(item) {
    return String(item?.row_key || item?.id || "").trim();
  }

  function getSelectedChangeLedgerRow() {
    const rows = changeLedgerRows();
    return rows.find((item) => changeLedgerRowKey(item) === selectedChangeLedgerRowKey) || null;
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

  function changeLedgerCounts(ledger) {
    return ledger?.counts && typeof ledger.counts === "object" ? ledger.counts : {};
  }

  function changeLedgerSummaryLines(ledger) {
    const payload = ledger || {};
    const counts = changeLedgerCounts(payload);
    const coverage = changeLedgerCoverage(payload);
    const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
      ? payload.summary_lines.map((line) => String(line || ""))
      : [
        `Change ledger: ${counts.total || 0} packet(s)`,
        `Unreleased: ${counts.unreleased || 0}; released: ${counts.released || 0}`,
        `Open: ${(counts.planned || 0) + (counts.in_progress || 0)}; complete: ${counts.complete || 0}`,
        `High/critical risk: ${counts.high_or_critical_risk || 0}`,
      ];
    const impact = payload.python_impact && typeof payload.python_impact === "object" ? payload.python_impact : {};
    lines.push(
      "",
      `Coverage: ${coverage.uncovered_count || 0} unrecorded changed file(s) in ${coverage.scope || "worktree"} scope.`,
      "",
      `Affected Python scripts: ${impact.summary || "No Python impact loaded."}`,
      "",
      "Source boundary:",
      "- Root CHANGELOG.md remains the canonical human changelog.",
      "- Structured change packets under ops/ops/release/metadata/changes/ feed this Maintenance ledger and generated change-control docs.",
      "- This panel is read-only; agents update packet/changelog files during development, not from the WebView."
    );
    return lines;
  }

  function changeLedgerCoverage(ledger) {
    return ledger?.coverage && typeof ledger.coverage === "object" ? ledger.coverage : {};
  }

  function changeLedgerUnrecordedPaths(ledger) {
    const coverage = changeLedgerCoverage(ledger || {});
    const hygiene = ledger?.hygiene && typeof ledger.hygiene === "object" ? ledger.hygiene : {};
    if (Array.isArray(coverage.uncovered_paths)) return coverage.uncovered_paths;
    if (Array.isArray(hygiene.unrecorded_changes)) return hygiene.unrecorded_changes;
    if (Array.isArray(hygiene.unlogged_changes)) return hygiene.unlogged_changes;
    return [];
  }

  function renderChangeLedgerSummary(ledger) {
    const payload = ledger || {};
    const counts = changeLedgerCounts(payload);
    const hygiene = payload.hygiene && typeof payload.hygiene === "object" ? payload.hygiene : {};
    const coverage = changeLedgerCoverage(payload);
    const status = Number(coverage.uncovered_count || 0) > 0
      ? `Coverage review (${coverage.uncovered_count})`
      : hygiene.operator_status
      ? `${hygiene.operator_status} (${counts.total || 0})`
      : payload.schema_version ? `Loaded (${counts.total || 0})` : "Not loaded";
    setText("maintenance-change-ledger-status", status);
    setText("maintenance-change-ledger-summary", changeLedgerSummaryLines(payload).join("\n"));
  }

  function changeLedgerHygieneStatus(hygiene) {
    const status = String(hygiene?.operator_status || "").trim();
    if (!status) return "Not loaded";
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function changeLedgerHygieneLines(ledger) {
    const payload = ledger || {};
    const hygiene = payload.hygiene && typeof payload.hygiene === "object" ? payload.hygiene : {};
    const coverage = changeLedgerCoverage(payload);
    const unrecorded = changeLedgerUnrecordedPaths(payload);
    const lines = Array.isArray(hygiene.summary_lines) && hygiene.summary_lines.length
      ? hygiene.summary_lines.map((line) => String(line || ""))
      : [
        `Unrecorded changed files: ${coverage.uncovered_count || hygiene.unrecorded_change_count || hygiene.unlogged_change_count || 0}`,
        `Change ledger hygiene: ${hygiene.operator_status || "not loaded"}`,
        `Issues: ${hygiene.issue_count || 0}`,
      ];
    if (unrecorded.length) {
      lines.push("", "Unrecorded changed files:");
      unrecorded.slice(0, 25).forEach((path) => lines.push(`- ${path}`));
      if (unrecorded.length > 25) lines.push(`- ${unrecorded.length - 25} more file(s).`);
    }
    const sourcePaths = Array.isArray(payload.source_paths) ? payload.source_paths : [];
    if (sourcePaths.length) {
      lines.push("", "Canonical/generator source paths:");
      sourcePaths.forEach((item) => {
        lines.push(`- ${item.path || ""}: ${item.exists ? "present" : "missing"}${item.stale ? "; stale" : ""}`);
      });
    }
    const issues = Array.isArray(hygiene.issues) ? hygiene.issues : [];
    if (issues.length) {
      lines.push("", "Hygiene issues:");
      issues.slice(0, 12).forEach((issue) => {
        lines.push(`- ${issue.severity || "warning"} ${issue.source_path || ""}: ${issue.message || ""}`);
      });
      if (issues.length > 12) lines.push(`- ${issues.length - 12} more issue(s).`);
    } else {
      lines.push("", "No changelog hygiene issues reported.");
    }
    lines.push("", "Mutation guardrail: this panel never writes packets, regenerates changelogs, edits AGENTS.md, runs tests, or touches media.");
    return lines;
  }

  function renderChangeLedgerHygiene(ledger) {
    const hygiene = ledger?.hygiene && typeof ledger.hygiene === "object" ? ledger.hygiene : {};
    setText("maintenance-change-ledger-hygiene-status", changeLedgerHygieneStatus(hygiene));
    setText("maintenance-change-ledger-hygiene", changeLedgerHygieneLines(ledger || {}).join("\n"));
  }

  function changeLedgerFilterValue(id) {
    return String(byId(id)?.value || "").trim().toLowerCase();
  }

  function changeLedgerSearchText(row) {
    return [
      row?.id,
      row?.title,
      row?.status,
      row?.type,
      row?.risk_level,
      row?.summary,
      row?.reason,
      ...(Array.isArray(row?.affected_areas) ? row.affected_areas : []),
      ...(Array.isArray(row?.files_touched) ? row.files_touched : []),
      row?.python_impact?.summary,
    ].map((item) => String(item || "").toLowerCase()).join(" ");
  }

  function filteredChangeLedgerRows() {
    const status = changeLedgerFilterValue("maintenance-change-ledger-status-filter");
    const type = changeLedgerFilterValue("maintenance-change-ledger-type-filter");
    const risk = changeLedgerFilterValue("maintenance-change-ledger-risk-filter");
    const search = changeLedgerFilterValue("maintenance-change-ledger-search");
    return changeLedgerRows().filter((row) => {
      if (status && String(row?.status || "").toLowerCase() !== status) return false;
      if (type && String(row?.type || "").toLowerCase() !== type) return false;
      if (risk && String(row?.risk_level || "").toLowerCase() !== risk) return false;
      if (search && !changeLedgerSearchText(row).includes(search)) return false;
      return true;
    });
  }

  function changeLedgerTableStatus(rows) {
    const all = changeLedgerRows();
    if (!lastChangeLedger) return "Not loaded";
    if (!all.length) return "No packets";
    if (rows.length !== all.length) return `${rows.length}/${all.length} shown`;
    return `${all.length} packet${all.length === 1 ? "" : "s"}`;
  }

  function selectChangeLedgerRow(item) {
    selectedChangeLedgerRowKey = changeLedgerRowKey(item);
    renderChangeLedgerDetail(item || null);
    renderChangeLedgerRows();
  }

  function renderChangeLedgerRows() {
    const tbody = byId("maintenance-change-ledger-rows");
    if (!tbody) return;
    const rows = filteredChangeLedgerRows();
    setText("maintenance-change-ledger-table-status", changeLedgerTableStatus(rows));
    if (!rows.length) {
      clearRows(tbody, 6, lastChangeLedger ? "No change packets match the current filters." : "No change ledger loaded.");
      updateTableStatusLegend("maintenance-change-ledger-table-legend", tbody, "Change ledger rows");
      renderChangeLedgerDetail(getSelectedChangeLedgerRow());
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const risk = String(item?.risk_level || "").toLowerCase();
      const validation = String(item?.validation_status || "").toLowerCase();
      row.dataset.status = validation === "invalid" || risk === "critical" ? "blocked" : validation === "incomplete" || risk === "high" ? "warning" : "match";
      appendCells(row, [
        item.id || "",
        item.status || "",
        item.type || "",
        item.risk_level || "",
        item.title || "",
        item.python_impact?.file_count ? `${item.python_impact.file_count} file(s)` : "none",
      ]);
      makeRowSelectable(row, () => selectChangeLedgerRow(item), {
        selected: Boolean(changeLedgerRowKey(item) && changeLedgerRowKey(item) === selectedChangeLedgerRowKey),
        label: `Change ledger entry ${item.id || item.title || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("maintenance-change-ledger-table-legend", tbody, "Change ledger rows");
  }

  function changeLedgerDetailLines(item) {
    if (!item) {
      return [
        "No change selected.",
        "Select a ledger row to inspect the issue/feature summary, affected Python scripts, validation evidence, rollback plan, and notes.",
        "Guardrail: row selection is local/read-only and does not edit changelog packets or generated docs.",
      ];
    }
    const impact = item.python_impact && typeof item.python_impact === "object" ? item.python_impact : {};
    const groups = Array.isArray(impact.groups) ? impact.groups : [];
    const lines = [
      `Change: ${item.id || ""} - ${item.title || ""}`,
      `Status: ${item.status || ""}`,
      `Type: ${item.type || ""}`,
      `Risk: ${item.risk_level || ""}`,
      `Version target: ${item.version_target || ""}`,
      `Location: ${item.location || ""}${item.release_version ? ` (${item.release_version})` : ""}`,
      `Validation status: ${item.validation_status || ""}`,
      `Source packet: ${item.source_path || ""}`,
      "",
      `Summary: ${item.summary || ""}`,
      `Reason: ${item.reason || ""}`,
      "",
      `Affected areas: ${(item.affected_areas || []).join(", ") || "none listed"}`,
      `Affected Python scripts: ${impact.summary || "No Python scripts touched."}`,
    ];
    if (groups.length) {
      lines.push("Python groups:");
      groups.forEach((group) => {
        lines.push(`- ${group.summary || group.group || ""}`);
        (group.files || []).slice(0, 8).forEach((path) => lines.push(`  ${path}`));
      });
    }
    lines.push(
      "",
      `Behavior before: ${item.behavior_before || ""}`,
      `Behavior after: ${item.behavior_after || ""}`,
      "",
      "Files touched:",
      ...((item.files_touched || []).length ? item.files_touched.slice(0, 18).map((path) => `- ${path}`) : ["- none listed"])
    );
    if ((item.files_touched || []).length > 18) lines.push(`- ${(item.files_touched || []).length - 18} more file(s).`);
    lines.push(
      "",
      "Tests/manual validation:",
      ...((item.manual_validation || []).length ? item.manual_validation.map((line) => `- ${line}`) : ["- none listed"]),
      "",
      `Rollback plan: ${item.rollback_plan || ""}`,
      `Related changes: ${(item.related_changes || []).join(", ") || "none"}`,
      `Notes: ${item.notes || ""}`,
      "",
      "Mutation guardrail: Maintenance displays this packet only. Agents must update change packets and generated changelog outputs in the repository during implementation."
    );
    return lines;
  }

  function renderChangeLedgerDetail(item) {
    setText("maintenance-change-ledger-detail-status", item ? (item.validation_status || item.status || "selected") : "No selection");
    setText("maintenance-change-ledger-detail", changeLedgerDetailLines(item || null).join("\n"));
  }

  function renderChangeLedger(ledger) {
    lastChangeLedger = ledger || {};
    const rows = changeLedgerRows();
    if (!rows.some((item) => changeLedgerRowKey(item) === selectedChangeLedgerRowKey)) {
      selectedChangeLedgerRowKey = rows.length ? changeLedgerRowKey(rows[0]) : "";
    }
    renderChangeLedgerSummary(lastChangeLedger);
    renderChangeLedgerRows();
    renderChangeLedgerDetail(getSelectedChangeLedgerRow());
    renderChangeLedgerHygiene(lastChangeLedger);
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
      row.dataset.status = item.status === "ok" ? "match" : item.status === "warning" ? "warning" : item.status === "running" ? "running" : "blocked";
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
        emptyHistoryText: "No maintenance commands recorded yet. Run Plan Deployment, Create Deployment, Backfill Dry Run, or Update Atlas to see backend command results here.",
        emptyMatchText: "No maintenance commands recorded yet. Run Plan Deployment, Create Deployment, Backfill Dry Run, or Update Atlas to see backend command results here.",
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
        "No maintenance commands recorded yet. Run Plan Deployment, Create Deployment, Backfill Dry Run, or Update Atlas to see backend command results here."
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
    if (readiness === "Active") return "Active";
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
    const activeRows = maintenanceActiveRows(rows);
    const latest = maintenanceLatestDryRun(history);
    const lines = [
      "Maintenance dry-run confidence:",
      `Health readiness: ${readiness}`,
      `Checks loaded: ${rows.length}`,
      `Required missing/blocking: ${requiredMissing.length || lastMaintenance?.missing_count || 0}`,
      `Active process guard rows: ${activeRows.length}`,
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
    } else if (readiness === "Active") {
      lines.push("- Active backend work is running. Let it finish, or inspect Home progress, Diagnostics ActiveJobs, and Run Logs before maintenance dry-run decisions.");
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

  async function refreshChangeLedger() {
    if (changeLedgerRefreshInFlight) return;
    changeLedgerRefreshInFlight = true;
    const button = byId("maintenance-change-ledger-refresh-button");
    if (button) button.disabled = true;
    setText("maintenance-change-ledger-status", "Loading...");
    try {
      renderChangeLedger(await apiGet("/api/maintenance/change-ledger"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("maintenance-change-ledger-status", "Error");
      setText("maintenance-change-ledger-summary", `Change ledger unavailable: ${message}`);
      clearRows(byId("maintenance-change-ledger-rows"), 6, message);
      setText("maintenance-change-ledger-table-status", "Error");
      setText("maintenance-change-ledger-hygiene-status", "Unavailable");
      setText("maintenance-change-ledger-hygiene", `Change ledger hygiene unavailable: ${message}`);
      renderChangeLedgerDetail(null);
    } finally {
      changeLedgerRefreshInFlight = false;
      if (button) button.disabled = false;
    }
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
    const changeLedgerRefreshButton = byId("maintenance-change-ledger-refresh-button");
    if (changeLedgerRefreshButton) changeLedgerRefreshButton.addEventListener("click", refreshChangeLedger);
    [
      "maintenance-change-ledger-status-filter",
      "maintenance-change-ledger-type-filter",
      "maintenance-change-ledger-risk-filter",
      "maintenance-change-ledger-search",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", () => renderChangeLedgerRows());
      element.addEventListener("change", () => renderChangeLedgerRows());
    });
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
    refreshChangeLedger();
  }

  function renderReleaseDryRunResult(result) {
    const data = result?.data || {};
    renderReleasePackageProgress(result);
    const lines = [
      "Dry-run trust summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run === true ? "yes" : "unknown"}`,
      `Writes manifest: ${data.manifest_created === true ? "unexpected yes" : "no"}`,
      `Changes manifest: ${data.manifest_changed === true ? "unexpected yes" : "no"}`,
      `Writes zip: ${data.zip_created === true ? "unexpected yes" : "no"}`,
      `Changes zip: ${data.zip_changed === true ? "unexpected yes" : "no"}`,
      `Safe next action: ${result?.ok ? "Review planned copy counts/options, destination, and package options before Create Deployment." : "Read errors and Diagnostics before trusting release packaging."}`,
      "Guardrail: this WebView action must remain a backend dry-run command; it must not create release folders, zips, manifests, or copy payloads.",
      "Real-media boundary: release dry-run output does not validate FFmpeg, subtitle OCR/SRT, audio routing, output size, completed sidecars, or pending-publish behavior on media files.",
      "",
      result?.message || "Release dry run completed.",
      "",
      `Destination: ${data.destination_root || ""}`,
      `Return code: ${data.returncode ?? ""}`,
      `Elapsed: ${Number(data.elapsed_seconds || 0).toFixed(1)}s`,
      `Manifest exists after: ${data.manifest_exists === true ? "yes" : "no"}`,
      `Manifest preexisting: ${data.manifest_preexisting === true ? "yes" : "no"}`,
      `Manifest created by command: ${data.manifest_created === true ? "yes" : "no"}`,
      `Manifest changed by command: ${data.manifest_changed === true ? "yes" : "no"}`,
      `Zip exists after: ${data.zip_exists === true ? "yes" : "no"}`,
      `Zip preexisting: ${data.zip_preexisting === true ? "yes" : "no"}`,
      `Zip created by command: ${data.zip_created === true ? "yes" : "no"}`,
      `Zip changed by command: ${data.zip_changed === true ? "yes" : "no"}`,
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

  function dependencyAtlasProgressBars(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.dependency_atlas_progress && typeof data.dependency_atlas_progress === "object" ? data.dependency_atlas_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
    return [];
  }

  function renderDependencyAtlasProgress(result) {
    if (typeof renderProgressBarsInto !== "function") return;
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.dependency_atlas_progress && typeof data.dependency_atlas_progress === "object" ? data.dependency_atlas_progress : {};
    renderProgressBarsInto("dependency-atlas-progress-bars", dependencyAtlasProgressBars(result), progress, "No dependency atlas progress loaded.");
  }

  function renderDependencyAtlasResult(result) {
    const data = result?.data || {};
    renderDependencyAtlasProgress(result);
    const lines = [
      "Dependency atlas update summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Writes dependency atlas artifacts: ${data.writes_dependency_atlas === true ? "yes" : "no"}`,
      `Writes media or pipeline state: ${data.writes_media === true ? "unexpected yes" : "no"}`,
      `Safe next action: ${result?.ok ? "Open docs/generated/dependency-atlas/docs/generated/dependency-atlas.html or docs/generated/dependency-atlas/docs/generated/dependency-atlas.png from the repository root." : "Read errors and Diagnostics before trusting the atlas files."}`,
      "Guardrail: this WebView action only asks the backend to run ops/scripts/dev/generate_dependency_atlas.py. It must not mutate media, queue state, settings, completed manifests, pending publish state, or pipeline execution.",
      "",
      result?.message || "Dependency atlas generation finished.",
      "",
      `HTML: ${data.atlas_html || ""}`,
      `PNG: ${data.atlas_png || ""}`,
      `SVG: ${data.atlas_svg || ""}`,
      `Assets: ${data.assets_dir || ""}`,
      `Summary CSV: ${data.summary_csv || ""}`,
      `Module edges CSV: ${data.module_edges_csv || ""}`,
      `Modules: ${data.modules || ""}`,
      `Domain edges: ${data.domain_edges || ""}`,
      `Detail diagrams: ${data.detail_diagrams || ""}`,
      `HTML links checked: ${data.html_links_checked || ""}`,
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
    setText("dependency-atlas-detail", lines.join("\n"));
  }

  async function runDependencyAtlas() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.dependency_atlas", "dependency-atlas-status", "dependency-atlas-detail")) return;
    setMaintenanceDryRunBusy(true);
    setText("dependency-atlas-status", "Running...");
    setText("dependency-atlas-detail", "Generating dependency atlas artifacts through backend tooling. This updates files under docs/generated/dependency-atlas only.");
    try {
      const result = await apiPost("/api/maintenance/dependency-atlas", {
        timeout_seconds: 600,
        min_overview_edge_count: 4,
        min_overview_files: 2,
      });
      appendCommandResult(result);
      setText("dependency-atlas-status", result.ok ? "Complete" : result.severity || "Failed");
      renderDependencyAtlasResult(result);
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.dependency_atlas",
        ok: false,
        severity: "error",
        message,
      });
      setText("dependency-atlas-status", "Error");
      setText("dependency-atlas-detail", message);
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  async function openDependencyAtlasFolder() {
    if (dependencyAtlasOpenInFlight) return;
    setDependencyAtlasOpenBusy(true);
    try {
      const result = await apiPost("/api/maintenance/dependency-atlas/open-folder", {});
      appendCommandResult(result);
      if (!result.ok) {
        setText("dependency-atlas-status", result.severity || "Open failed");
        setText("dependency-atlas-detail", result.message || "Dependency atlas folder could not be opened.");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.dependency_atlas_open_folder",
        ok: false,
        severity: "error",
        message,
      });
      setText("dependency-atlas-status", "Error");
      setText("dependency-atlas-detail", message);
    } finally {
      setDependencyAtlasOpenBusy(false);
    }
  }

  /**
   * Public namespace for the Maintenance page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineMaintenanceView = {
    hasMaintenanceLoaded,
    getLastMaintenance,
    getLastChangeLedger,
    renderMaintenance,
    renderChangeLedger,
    renderChangeLedgerRows,
    renderChangeLedgerDetail,
    renderChangeLedgerSummary,
    renderChangeLedgerHygiene,
    changeLedgerSummaryLines,
    changeLedgerDetailLines,
    changeLedgerHygieneLines,
    changeLedgerCoverage,
    changeLedgerUnrecordedPaths,
    filteredChangeLedgerRows,
    refreshChangeLedger,
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
    renderDependencyAtlasResult,
    renderDependencyAtlasProgress,
    dependencyAtlasProgressBars,
    isMaintenanceDryRunCommand,
    renderMaintenanceDryRunHistory,
    runBackfillDryRun,
    runDependencyAtlas,
    openDependencyAtlasFolder,
  };
  window.hasMaintenanceLoaded = hasMaintenanceLoaded;
  window.getLastMaintenance = getLastMaintenance;
  window.refreshMaintenance = refreshMaintenance;
  window.initMaintenanceViewEvents = initMaintenanceViewEvents;
  window.runReleaseDryRun = runReleaseDryRun;
  window.runReleaseBuild = runReleaseBuild;
  window.runBackfillDryRun = runBackfillDryRun;
})();
