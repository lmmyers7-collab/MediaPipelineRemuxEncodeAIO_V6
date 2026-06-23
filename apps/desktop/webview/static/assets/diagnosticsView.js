(function () {
  let diagnosticsOpenInFlight = false;
  let tdarrMatrixAuditInFlight = false;
  let tdarrMatrixBackgroundPollTimer = 0;
  const diagnosticsTailView = window.mediaPipelineDiagnosticsTailView || {};
  const selectedDiagnosticsTailTarget = diagnosticsTailView.selectedDiagnosticsTailTarget || window.selectedDiagnosticsTailTarget || function () { return ""; };
  const selectedDiagnosticsTailMaxBytes = diagnosticsTailView.selectedDiagnosticsTailMaxBytes || window.selectedDiagnosticsTailMaxBytes || function () { return "65536"; };
  const setDiagnosticsTailTarget = diagnosticsTailView.setDiagnosticsTailTarget || window.setDiagnosticsTailTarget || function () {};
  const setDiagnosticsTailStatus = diagnosticsTailView.setDiagnosticsTailStatus || window.setDiagnosticsTailStatus || function () {};
  const setDiagnosticsTailBusy = diagnosticsTailView.setDiagnosticsTailBusy || window.setDiagnosticsTailBusy || function () {};
  const renderDiagnosticsTail = diagnosticsTailView.renderDiagnosticsTail || window.renderDiagnosticsTail || function () {};
  const requestDiagnosticsTail = diagnosticsTailView.requestDiagnosticsTail || window.requestDiagnosticsTail || async function () {};
  const diagnosticsStateSummaryView = window.mediaPipelineDiagnosticsStateSummaryView || {};
  const diagnosticsStateOperatorStatus = diagnosticsStateSummaryView.diagnosticsStateOperatorStatus || function (item) {
    return item?.operator_status || item?.status || "";
  };
  const diagnosticsStateRecommendedFirstAction = diagnosticsStateSummaryView.diagnosticsStateRecommendedFirstAction || function () {
    return "inspect this state artifact.";
  };
  const commandHistoryView = window.mediaPipelineCommandHistory || {};

  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }

  let lastDiagnosticsLogRows = [];
  let selectedDiagnosticsFirstResponseKey = "";
  let tdarrMatrixConsoleState = {
    latestRunId: "",
    currentRun: {},
    runs: [],
    findings: [],
    bucketSummary: [],
    smokePackRows: [],
    proofPackRows: [],
    activePack: "proof-pack",
    selectedFindingKey: "",
    selectedFindingKeys: new Set(),
    successfulActions: {},
  };

  function setDiagnosticsPanelStatus(id, message, state) {
    if (typeof setPanelStatus === "function") {
      setPanelStatus(id, message, state);
    } else {
      setText(id, message);
    }
  }

  function setDiagnosticsOpenStatus(message, state) {
    setDiagnosticsPanelStatus("diagnostics-open-status", message, state);
    setDiagnosticsPanelStatus("home-runtime-open-status", message, state);
  }

  function setDiagnosticsOpenBusy(isBusy, sourceButton = null) {
    diagnosticsOpenInFlight = Boolean(isBusy);
    if (!sourceButton || typeof setActionBusy === "function") return;
    sourceButton.disabled = diagnosticsOpenInFlight;
    sourceButton.setAttribute("aria-busy", diagnosticsOpenInFlight ? "true" : "false");
  }

  function rejectDiagnosticsOpenWhileBusy() {
    if (!diagnosticsOpenInFlight) return false;
    const result = {
      command: "diagnostics.open",
      ok: false,
      severity: "warning",
      message: "Another diagnostics open command is already in progress.",
    };
    appendCommandResult(result);
    setDiagnosticsOpenStatus(result.message, "loading");
    return true;
  }

  function setTdarrMatrixAuditStatus(message, state) {
    setDiagnosticsPanelStatus("tdarr-matrix-audit-status", message, state);
  }

  function setTdarrMatrixAuditDetail(lines) {
    const text = Array.isArray(lines) ? lines.filter(Boolean).join("\n") : String(lines || "");
    setText("tdarr-matrix-audit-detail", text || "No Tdarr Matrix audit has been run from this shell.");
  }

  function setTdarrMatrixAuditBusy(isBusy) {
    tdarrMatrixAuditInFlight = Boolean(isBusy);
    updateTdarrMatrixActionGates();
    updateTdarrMatrixRerunButtons();
  }

  function stopTdarrMatrixBackgroundPoll() {
    if (!tdarrMatrixBackgroundPollTimer) return;
    window.clearInterval(tdarrMatrixBackgroundPollTimer);
    tdarrMatrixBackgroundPollTimer = 0;
  }

  function scheduleTdarrMatrixBackgroundPoll(runId) {
    const selectedRunId = String(runId || "").trim();
    if (!selectedRunId) return;
    stopTdarrMatrixBackgroundPoll();
    let attempts = 0;
    tdarrMatrixBackgroundPollTimer = window.setInterval(async () => {
      attempts += 1;
      await requestTdarrMatrixConsole(selectedRunId);
      const current = tdarrMatrixConsoleState.currentRun || {};
      if (current.run_id === selectedRunId && current.report_exists) {
        setTdarrMatrixAuditStatus("Complete", "ready");
        stopTdarrMatrixBackgroundPoll();
      } else if (attempts >= 240) {
        stopTdarrMatrixBackgroundPoll();
      }
    }, 15000);
  }

  function tdarrMatrixAuditActionLabel(action) {
    const labels = {
      "prepare-proof-pack": "Prepare Proof Pack",
      report: "Prepare Proof Pack Audit Report",
      "smoke-pack": "Smoke Pack",
      "proof-pack": "Proof Pack",
      "strict-report": "Strict Proof Gate",
      "cleanup-plan": "Cleanup Full Matrix",
      "cleanup-archive": "Archive Matrix Evidence",
      "cleanup-delete": "Delete Verified Full Matrix",
    };
    return labels[action] || action || "Tdarr Matrix audit";
  }

  function tdarrMatrixHasLatestEvidence() {
    return Boolean(
      tdarrMatrixConsoleState.latestRunId
      || tdarrMatrixConsoleState.currentRun?.run_id
      || tdarrMatrixConsoleState.findings.length
      || tdarrMatrixConsoleState.smokePackRows.length
      || tdarrMatrixConsoleState.proofPackRows.length
    );
  }

  function tdarrMatrixHasProofEvidence() {
    return Boolean(
      tdarrMatrixConsoleState.proofPackRows.length
      || tdarrMatrixConsoleState.smokePackRows.length
      || tdarrMatrixConsoleState.currentRun?.report_exists
    );
  }

  function tdarrMatrixDeleteConfirmReady() {
    return String(byId("tdarr-matrix-delete-confirm")?.value || "").trim() === "DELETE VERIFIED MATRIX";
  }

  function tdarrMatrixActionGate(action) {
    const normalized = String(action || "").trim();
    if (tdarrMatrixAuditInFlight) return { disabled: true, state: "loading", reason: "Another Tdarr proof action is running." };
    if (normalized === "prepare-proof-pack") return { disabled: false, state: "ready", reason: "Backend-owned proof-pack preparation can be started." };
    if (["smoke-pack", "proof-pack"].includes(normalized) && !tdarrMatrixHasLatestEvidence()) {
      return { disabled: true, state: "warning", reason: "Load latest Tdarr evidence before running pack tests." };
    }
    if (normalized === "strict-report" && !tdarrMatrixHasProofEvidence()) {
      return { disabled: true, state: "warning", reason: "Load or run proof evidence before the strict proof gate." };
    }
    if (normalized === "cleanup-plan" && !tdarrMatrixHasProofEvidence()) {
      return { disabled: true, state: "warning", reason: "Proof evidence is required before cleanup planning." };
    }
    if (normalized === "cleanup-archive" && !tdarrMatrixConsoleState.successfulActions["cleanup-plan"]) {
      return { disabled: true, state: "warning", reason: "Run a successful cleanup plan before archiving matrix evidence." };
    }
    if (normalized === "cleanup-delete") {
      if (!tdarrMatrixConsoleState.successfulActions["cleanup-archive"]) {
        return { disabled: true, state: "blocked", reason: "Archive verified matrix evidence before delete can be armed." };
      }
      if (!tdarrMatrixDeleteConfirmReady()) {
        return { disabled: true, state: "blocked", reason: "Type DELETE VERIFIED MATRIX to arm delete." };
      }
      return { disabled: false, state: "blocked", reason: "Delete is armed; backend will still verify proof and confirmation." };
    }
    return { disabled: false, state: "ready", reason: "Backend-owned proof action is available." };
  }

  function tdarrMatrixActionSeverity(action) {
    const normalized = String(action || "").trim();
    if (normalized === "cleanup-delete") return "danger";
    if (["strict-report", "cleanup-plan", "cleanup-archive"].includes(normalized)) return "warning";
    return "neutral";
  }

  function updateTdarrMatrixActionGates() {
    document.querySelectorAll("[data-tdarr-matrix-audit-action]").forEach((button) => {
      const action = button.dataset.tdarrMatrixAuditAction || "";
      const gate = tdarrMatrixActionGate(action);
      button.disabled = gate.disabled;
      button.title = gate.reason || "";
      button.dataset.gateState = gate.state || "unknown";
      const severity = tdarrMatrixActionSeverity(action);
      if (severity === "warning") {
        button.dataset.severity = "warning";
      } else {
        delete button.dataset.severity;
      }
      if (typeof setInlineActionStatus === "function" && action !== "prepare-proof-pack") {
        setInlineActionStatus(button, gate.reason, gate.state);
      }
    });
    const deleteConfirm = byId("tdarr-matrix-delete-confirm");
    if (deleteConfirm) {
      deleteConfirm.dataset.state = tdarrMatrixDeleteConfirmReady() ? "ready" : "error";
    }
  }

  function tdarrMatrixAuditDetailLines(result) {
    const data = result && result.data ? result.data : {};
    const selectedCount = data.selected_count ?? data.selected_count_hint ?? 0;
    const lines = [
      result?.message || "Tdarr Matrix audit command completed.",
      `Action: ${data.action || "unknown"}`,
      data.background_started ? `Run ID: ${data.run_id || "pending"}` : "",
      data.background_started ? `Background PID: ${data.pid || "pending"}` : "",
      data.background_started ? "Status: background run started; use the console refresh to follow preparation, worker results, and final findings." : "",
      `Findings: ${data.finding_count ?? 0}`,
      `Manifest rows: ${data.manifest_count ?? 0}`,
      `Selected samples: ${selectedCount}`,
    ];
    if (data.report_path) lines.push(`Report: ${data.report_path}`);
    if (data.run_root) lines.push(`Run root: ${data.run_root}`);
    if (data.library_root) lines.push(`Library root: ${data.library_root}`);
    if (data.returncode !== undefined) lines.push(`Exit code: ${data.returncode}`);
    return lines;
  }

  function appendTdarrMatrixAuditFindingCell(row, value, title) {
    const cell = document.createElement("td");
    const text = String(value || "").trim();
    cell.textContent = text || "-";
    if (title || text.length > 80) cell.title = String(title || text);
    row.appendChild(cell);
  }

  function tdarrMatrixSetSelectOptions(select, values, selectedValue) {
    if (!select) return;
    const current = String(selectedValue || select.value || "");
    select.replaceChildren();
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "All";
    select.appendChild(all);
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    select.value = values.includes(current) ? current : "";
  }

  function tdarrMatrixSetRunOptions(select, runs, selectedValue) {
    if (!select) return;
    const current = String(selectedValue || select.value || "");
    select.replaceChildren();
    if (!runs.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No Tdarr Matrix runs loaded";
      option.disabled = true;
      option.selected = true;
      select.appendChild(option);
      select.disabled = true;
      select.setAttribute("aria-disabled", "true");
      return;
    }
    select.disabled = false;
    select.removeAttribute("aria-disabled");
    runs.forEach((run) => {
      const option = document.createElement("option");
      option.value = String(run.run_id || "");
      const findings = Number(run.finding_count || 0);
      const selected = Number(run.selected_count || 0);
      option.textContent = `${run.run_id || "unknown"} (${selected} samples, ${findings} findings)`;
      select.appendChild(option);
    });
    if (current && Array.from(select.options).some((option) => option.value === current)) {
      select.value = current;
    }
  }

  function tdarrMatrixAuditFindingRoute(row) {
    return [row.route, row.route_reason_code].map((value) => String(value || "").trim()).filter(Boolean).join(" / ");
  }

  function tdarrMatrixAuditFindingMessage(row) {
    return [row.message, row.reason].map((value) => String(value || "").trim()).filter(Boolean).join(" - ");
  }

  function tdarrMatrixRowsFromResult(result) {
    const data = result && result.data ? result.data : result || {};
    if (Array.isArray(data.findings)) return data.findings;
    if (Array.isArray(data.findings_preview)) return data.findings_preview;
    return [];
  }

  function tdarrMatrixFindingSearchText(item) {
    return [
      item.severity,
      item.code,
      item.case_id,
      item.view,
      item.diagnostic_bucket,
      tdarrMatrixAuditFindingRoute(item),
      tdarrMatrixAuditFindingMessage(item),
      item.source_name,
      item.generated_path,
      item.source_path,
    ].map((value) => String(value || "").toLowerCase()).join(" ");
  }

  function tdarrMatrixFilteredFindings() {
    const filter = String(byId("tdarr-matrix-audit-filter")?.value || "").trim().toLowerCase();
    const severity = String(byId("tdarr-matrix-audit-severity-filter")?.value || "").trim().toLowerCase();
    const bucket = String(byId("tdarr-matrix-audit-bucket-filter")?.value || "").trim().toLowerCase();
    return tdarrMatrixConsoleState.findings.filter((item) => {
      if (severity && String(item.severity || "").toLowerCase() !== severity) return false;
      if (bucket && String(item.diagnostic_bucket || "").toLowerCase() !== bucket) return false;
      if (filter && !tdarrMatrixFindingSearchText(item).includes(filter)) return false;
      return true;
    });
  }

  function updateTdarrMatrixRerunButtons() {
    const selectedCount = tdarrMatrixConsoleState.selectedFindingKeys.size;
    const failureCount = tdarrMatrixConsoleState.findings.filter((item) => {
      const severity = String(item.severity || "").toLowerCase();
      const code = String(item.code || "").toLowerCase();
      return ["critical", "error", "warning"].includes(severity) || code.includes("failure");
    }).length;
    const selectedButton = byId("tdarr-matrix-audit-rerun-selected");
    if (selectedButton) selectedButton.disabled = tdarrMatrixAuditInFlight || selectedCount <= 0;
    const failuresButton = byId("tdarr-matrix-audit-rerun-failures");
    if (failuresButton) failuresButton.disabled = tdarrMatrixAuditInFlight || failureCount <= 0 || !tdarrMatrixConsoleState.latestRunId;
  }

  function renderTdarrMatrixEvidenceActions(finding) {
    const container = byId("tdarr-matrix-audit-evidence-actions");
    if (!container) return;
    container.replaceChildren();
    const targets = Array.isArray(finding?.available_evidence_targets) ? finding.available_evidence_targets : [];
    if (!finding) {
      setDiagnosticsPanelStatus("tdarr-matrix-audit-evidence-status", "No selection", "empty");
      setText("tdarr-matrix-audit-finding-detail", "Select a finding row to inspect available evidence.");
      return;
    }
    setDiagnosticsPanelStatus("tdarr-matrix-audit-evidence-status", targets.length ? `${targets.length} target(s)` : "No evidence targets", targets.length ? "ready" : "empty");
    setText(
      "tdarr-matrix-audit-finding-detail",
      [
        `Run: ${finding.run_id || tdarrMatrixConsoleState.latestRunId || "unknown"}`,
        `Finding: ${finding.finding_key || ""}`,
        `Severity: ${finding.severity || "-"}`,
        `Code: ${finding.code || "-"}`,
        `Case: ${finding.case_id || "-"} / ${finding.view || "-"}`,
        `Bucket: ${finding.diagnostic_bucket || "-"}`,
        `Route: ${tdarrMatrixAuditFindingRoute(finding) || "-"}`,
        `Message: ${tdarrMatrixAuditFindingMessage(finding) || "-"}`,
        `Evidence targets: ${targets.join(", ") || "none"}`,
      ].join("\n"),
    );
    targets.forEach((target) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button";
      button.dataset.tdarrMatrixEvidenceTarget = target;
      button.textContent = target.replace(/_/g, " ");
      button.addEventListener("click", () => requestTdarrMatrixEvidenceOpen(target));
      container.appendChild(button);
    });
  }

  function renderTdarrMatrixSelectedFinding() {
    const selected = tdarrMatrixConsoleState.findings.find((item) => item.finding_key === tdarrMatrixConsoleState.selectedFindingKey);
    renderTdarrMatrixEvidenceActions(selected || null);
  }

  function renderTdarrMatrixAuditFindings(result) {
    const body = byId("tdarr-matrix-audit-findings-rows");
    if (!body) return;
    const data = result && result.data ? result.data : {};
    if (Array.isArray((result || {}).findings)) {
      tdarrMatrixConsoleState.findings = tdarrMatrixRowsFromResult(result);
    } else if (Array.isArray(data.findings_preview)) {
      tdarrMatrixConsoleState.findings = tdarrMatrixRowsFromResult(result);
    }
    const rows = tdarrMatrixFilteredFindings();
    const findingCount = Number(data.finding_count ?? rows.length) || 0;
    const total = Number(data.findings_preview_total ?? tdarrMatrixConsoleState.findings.length) || 0;
    const truncated = Boolean(data.findings_preview_truncated);
    const previewError = String(data.findings_preview_error || "").trim();
    body.replaceChildren();
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 9;
      cell.textContent = previewError
        || (findingCount ? "Findings were reported, but no preview rows were returned. Open the report path for full detail." : "No findings in the latest Tdarr Matrix result.");
      row.appendChild(cell);
      body.appendChild(row);
      setDiagnosticsPanelStatus("tdarr-matrix-audit-findings-status", previewError || `${findingCount} finding(s).`, previewError ? "blocked" : findingCount ? "warning" : "empty");
      updateTdarrMatrixRerunButtons();
      renderTdarrMatrixSelectedFinding();
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.findingKey = item.finding_key || "";
      if (item.finding_key && item.finding_key === tdarrMatrixConsoleState.selectedFindingKey) {
        row.classList.add("is-selected");
      }
      const selectCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(item.finding_key && tdarrMatrixConsoleState.selectedFindingKeys.has(item.finding_key));
      selectCell.title = "Select this finding for targeted rerun.";
      const updateCheckboxSelection = () => {
        if (!item.finding_key) return;
        if (checkbox.checked) {
          tdarrMatrixConsoleState.selectedFindingKeys.add(item.finding_key);
        } else {
          tdarrMatrixConsoleState.selectedFindingKeys.delete(item.finding_key);
        }
        updateTdarrMatrixRerunButtons();
      };
      checkbox.addEventListener("click", (event) => {
        event.stopPropagation();
      });
      checkbox.addEventListener("change", (event) => {
        event.stopPropagation();
        updateCheckboxSelection();
      });
      selectCell.addEventListener("click", (event) => {
        event.stopPropagation();
        checkbox.checked = !checkbox.checked;
        updateCheckboxSelection();
      });
      selectCell.appendChild(checkbox);
      row.appendChild(selectCell);
      appendTdarrMatrixAuditFindingCell(row, item.severity);
      appendTdarrMatrixAuditFindingCell(row, item.code);
      appendTdarrMatrixAuditFindingCell(row, item.case_id);
      appendTdarrMatrixAuditFindingCell(row, item.view || item.media_kind);
      appendTdarrMatrixAuditFindingCell(row, item.diagnostic_bucket);
      appendTdarrMatrixAuditFindingCell(row, tdarrMatrixAuditFindingRoute(item));
      appendTdarrMatrixAuditFindingCell(row, tdarrMatrixAuditFindingMessage(item));
      appendTdarrMatrixAuditFindingCell(row, item.source_name || item.generated_path, item.generated_path || item.source_path);
      row.addEventListener("click", () => {
        tdarrMatrixConsoleState.selectedFindingKey = item.finding_key || "";
        renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings });
      });
      body.appendChild(row);
    });
    const shown = rows.length;
    const totalText = total && total !== shown ? `${shown} of ${total}` : String(shown);
    setDiagnosticsPanelStatus(
      "tdarr-matrix-audit-findings-status",
      `${totalText} finding row(s) shown.${truncated ? " Preview truncated; open the report path for all rows." : ""}`,
      truncated ? "warning" : "ready",
    );
    updateTdarrMatrixRerunButtons();
    renderTdarrMatrixSelectedFinding();
  }

  function renderTdarrMatrixBucketCoverage(payload) {
    const body = byId("tdarr-matrix-audit-bucket-rows");
    if (!body) return;
    const rows = Array.isArray(payload?.bucket_summary) ? payload.bucket_summary : [];
    body.replaceChildren();
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 10;
      cell.textContent = "No Tdarr Matrix bucket coverage loaded.";
      row.appendChild(cell);
      body.appendChild(row);
      setDiagnosticsPanelStatus("tdarr-matrix-audit-bucket-status", "No rows", "empty");
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const severityCounts = item.severity_counts || {};
      [
        item.diagnostic_bucket,
        item.selected_count,
        item.queued_count,
        item.passed_count,
        item.failed_count,
        severityCounts.critical || 0,
        severityCounts.error || 0,
        severityCounts.warning || 0,
        item.movie_count,
        item.tv_count,
      ].forEach((value) => appendTdarrMatrixAuditFindingCell(row, value));
      body.appendChild(row);
    });
    setDiagnosticsPanelStatus("tdarr-matrix-audit-bucket-status", `${rows.length} bucket(s)`, "ready");
  }

  function tdarrMatrixProofRowsForActivePack() {
    return tdarrMatrixConsoleState.activePack === "smoke-pack"
      ? tdarrMatrixConsoleState.smokePackRows
      : tdarrMatrixConsoleState.proofPackRows;
  }

  function tdarrMatrixProofRowSearchText(item) {
    return [
      item.case_key,
      item.case_id,
      item.pack,
      item.diagnostic_bucket,
      item.view,
      item.resolution,
      item.video_codec,
      item.audio_codec,
      item.container,
      item.status,
      item.last_passed_at,
      item.latest_run_id,
      item.primary_finding_code,
    ].map((value) => String(value || "").toLowerCase()).join(" ");
  }

  function tdarrMatrixFilteredProofRows() {
    const filter = String(byId("tdarr-matrix-audit-filter")?.value || "").trim().toLowerCase();
    const bucket = String(byId("tdarr-matrix-audit-bucket-filter")?.value || "").trim().toLowerCase();
    return tdarrMatrixProofRowsForActivePack().filter((item) => {
      if (bucket && String(item.diagnostic_bucket || "").toLowerCase() !== bucket) return false;
      if (filter && !tdarrMatrixProofRowSearchText(item).includes(filter)) return false;
      return true;
    });
  }

  function renderTdarrMatrixProofPackRows() {
    const body = byId("tdarr-matrix-proof-pack-rows");
    if (!body) return;
    document.querySelectorAll("[data-tdarr-proof-pack-view]").forEach((button) => {
      const active = button.dataset.tdarrProofPackView === tdarrMatrixConsoleState.activePack;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    const rows = tdarrMatrixFilteredProofRows();
    body.replaceChildren();
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 14;
      cell.textContent = "No Tdarr Proof Pack rows loaded.";
      row.appendChild(cell);
      body.appendChild(row);
      setDiagnosticsPanelStatus("tdarr-matrix-proof-pack-status", `${tdarrMatrixConsoleState.activePack}: no rows`, "empty");
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.caseKey = item.case_key || "";
      [
        item.case_key,
        item.pack,
        item.diagnostic_bucket,
        item.view,
        item.resolution,
        item.video_codec,
        item.audio_codec,
        item.container,
        item.status,
        item.last_passed_at,
        item.latest_run_id || item.last_passed_run_id,
        item.finding_count,
        item.primary_finding_code,
      ].forEach((value) => appendTdarrMatrixAuditFindingCell(row, value));
      const evidenceCell = document.createElement("td");
      const targets = Array.isArray(item.available_evidence_targets) ? item.available_evidence_targets : [];
      const findingKey = String(item.primary_finding_key || "");
      const runId = String(item.latest_run_id || "");
      if (findingKey && runId && targets.length) {
        targets.slice(0, 4).forEach((target) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "secondary-button compact-button";
          button.textContent = String(target).replace(/_/g, " ");
          button.addEventListener("click", () => requestTdarrMatrixEvidenceOpen(target, findingKey, runId));
          evidenceCell.appendChild(button);
        });
      } else {
        evidenceCell.textContent = "-";
      }
      row.appendChild(evidenceCell);
      body.appendChild(row);
    });
    const total = tdarrMatrixProofRowsForActivePack().length;
    const shown = rows.length;
    setDiagnosticsPanelStatus("tdarr-matrix-proof-pack-status", `${tdarrMatrixConsoleState.activePack}: ${shown} of ${total} test row(s)`, "ready");
  }

  function tdarrMatrixCompareExamples(items) {
    return (Array.isArray(items) ? items : [])
      .slice(0, 3)
      .map((item) => {
        const finding = item.left || item.right || item;
        return [finding.case_id, finding.view, finding.code].filter(Boolean).join(" / ");
      })
      .filter(Boolean)
      .join("; ") || "-";
  }

  function renderTdarrMatrixRunComparison(payload) {
    const body = byId("tdarr-matrix-run-compare-rows");
    if (!body) return;
    const counts = payload?.counts || {};
    const rows = [
      ["new", counts.new || 0, payload?.new],
      ["resolved", counts.resolved || 0, payload?.resolved],
      ["repeated", counts.repeated || 0, payload?.repeated],
      ["changed", counts.changed || 0, payload?.changed],
    ];
    body.replaceChildren();
    rows.forEach(([label, count, items]) => {
      const row = document.createElement("tr");
      appendTdarrMatrixAuditFindingCell(row, label);
      appendTdarrMatrixAuditFindingCell(row, count);
      appendTdarrMatrixAuditFindingCell(row, tdarrMatrixCompareExamples(items));
      body.appendChild(row);
    });
    const left = payload?.left_run_id || "";
    const right = payload?.right_run_id || "";
    setDiagnosticsPanelStatus("tdarr-matrix-run-compare-status", left && right ? `${left} vs ${right}` : "Need two runs", left && right ? "ready" : "warning");
  }

  function renderTdarrMatrixConsole(payload) {
    const data = payload || {};
    tdarrMatrixConsoleState.latestRunId = String(data.latest_run_id || data.run?.run_id || "");
    tdarrMatrixConsoleState.currentRun = data.run || {};
    tdarrMatrixConsoleState.runs = Array.isArray(data.runs) ? data.runs : [];
    tdarrMatrixConsoleState.findings = Array.isArray(data.findings) ? data.findings : [];
    tdarrMatrixConsoleState.bucketSummary = Array.isArray(data.bucket_summary) ? data.bucket_summary : [];
    tdarrMatrixConsoleState.smokePackRows = Array.isArray(data.smoke_pack_rows) ? data.smoke_pack_rows : [];
    tdarrMatrixConsoleState.proofPackRows = Array.isArray(data.proof_pack_rows) ? data.proof_pack_rows : [];
    tdarrMatrixConsoleState.selectedFindingKeys = new Set(
      Array.from(tdarrMatrixConsoleState.selectedFindingKeys).filter((key) => tdarrMatrixConsoleState.findings.some((item) => item.finding_key === key)),
    );
    if (!tdarrMatrixConsoleState.findings.some((item) => item.finding_key === tdarrMatrixConsoleState.selectedFindingKey)) {
      tdarrMatrixConsoleState.selectedFindingKey = "";
    }
    const severities = Array.from(new Set(tdarrMatrixConsoleState.findings.map((item) => String(item.severity || "").trim()).filter(Boolean))).sort();
    const buckets = Array.from(new Set(tdarrMatrixConsoleState.findings.map((item) => String(item.diagnostic_bucket || "").trim()).filter(Boolean))).sort();
    tdarrMatrixSetSelectOptions(byId("tdarr-matrix-audit-severity-filter"), severities);
    tdarrMatrixSetSelectOptions(byId("tdarr-matrix-audit-bucket-filter"), buckets);
    tdarrMatrixSetRunOptions(byId("tdarr-matrix-compare-left"), tdarrMatrixConsoleState.runs, tdarrMatrixConsoleState.runs[0]?.run_id || "");
    tdarrMatrixSetRunOptions(byId("tdarr-matrix-compare-right"), tdarrMatrixConsoleState.runs, tdarrMatrixConsoleState.runs[1]?.run_id || "");
    const compareRefresh = byId("tdarr-matrix-compare-refresh");
    if (compareRefresh) {
      compareRefresh.disabled = tdarrMatrixConsoleState.runs.length < 2;
      compareRefresh.title = tdarrMatrixConsoleState.runs.length < 2
        ? "Load at least two Tdarr Matrix runs before comparing."
        : "";
    }
    const sample = data.sample_summary || {};
    const severityCounts = data.severity_counts || {};
    const run = data.run || {};
    const completed = Number(run.worker_result_count || 0);
    const selected = Number(run.selected_count || sample.selected_count || 0);
    const progressLine = selected > 0
      ? `Progress: ${completed} / ${selected} (${Number(run.progress_percent || 0).toFixed(1)}%) at ${Number(run.completed_per_hour || 0).toFixed(1)} files/hour; ETA ${Number(run.estimated_remaining_hours || 0).toFixed(1)}h remaining`
      : "";
    setText(
      "tdarr-matrix-console-summary",
      [
        `Run: ${tdarrMatrixConsoleState.latestRunId || "none"}`,
        run.status ? `Status: ${run.status}` : "",
        progressLine,
        `Findings: ${data.finding_count ?? tdarrMatrixConsoleState.findings.length}`,
        `Selected samples: ${sample.selected_count ?? 0} (${sample.movie_count ?? 0} movies, ${sample.tv_count ?? 0} tv)`,
        `Severity: critical ${severityCounts.critical || 0}, error ${severityCounts.error || 0}, warning ${severityCounts.warning || 0}, info ${severityCounts.info || 0}`,
        data.report_path ? `Report: ${data.report_path}` : "",
      ].filter(Boolean).join("\n"),
    );
    setTdarrMatrixAuditStatus(tdarrMatrixHasLatestEvidence() ? "Latest loaded" : "No report loaded", tdarrMatrixHasLatestEvidence() ? "ready" : "empty");
    renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings });
    renderTdarrMatrixProofPackRows();
    renderTdarrMatrixBucketCoverage(data);
    updateTdarrMatrixActionGates();
  }

  function rejectTdarrMatrixAuditWhileBusy(action) {
    if (!tdarrMatrixAuditInFlight) return false;
    const result = {
      command: "diagnostics.tdarr_matrix_audit",
      ok: false,
      severity: "warning",
      message: `${tdarrMatrixAuditActionLabel(action)} blocked because another Tdarr Matrix audit is already running.`,
    };
    appendCommandResult(result);
    setTdarrMatrixAuditStatus("Busy", "loading");
    setTdarrMatrixAuditDetail([result.message]);
    return true;
  }

  function diagnosticsTextLines(value) {
    if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
    const text = String(value || "").trim();
    return text ? text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean) : [];
  }

  function diagnosticsSeverityForLine(line) {
    const text = String(line || "").toLowerCase();
    if (/\b(error|failed|failure|exception|traceback|unavailable|denied|blocked|corrupt|malformed|invalid|unreadable|locked)\b/.test(text)) {
      return "error";
    }
    if (/\b(warn|warning|stale|orphan|missing|retry|timeout|partial|unknown|skipped)\b/.test(text)) {
      return "warning";
    }
    if (/\b(active|running|processing|launching|publishing)\b/.test(text)) {
      return "active";
    }
    return "info";
  }

  function diagnosticsMalformedStateLines(lines) {
    return lines.filter((line) => /\b(corrupt|malformed|invalid|unreadable|locked|stale|orphan|pid|activejobs|progress)\b/i.test(line));
  }

  function boundedDiagnosticsText(value, maxChars = 1600) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.length <= maxChars ? text : `${text.slice(0, maxChars)}...`;
  }

  function diagnosticsRealMediaBoundaryLines() {
    return [
      "Real-media validation lens:",
      "- Diagnostics can prove only evidence that exists in backend logs, ActiveJobs, state artifacts, command history, manifests, sidecars, and pending-publish records.",
      "- A clean preview launch, build check, or release self-test is not proof of FFmpeg route correctness, subtitle OCR/SRT output, audio selection, Output Size Check behavior, source stability, or publish completion for a real media file.",
      "- Missing diagnostics evidence is not success. For first daily-driver validation, compare Last Stderr, Run Logs, Queue route fields, Completed output proof/size growth, and Pending Publish drain summary after a small known run.",
    ];
  }

  function diagnosticsActionLabel(action) {
    if (!action) return "";
    const bridge = diagnosticsBridgeApi();
    if (typeof bridge.diagnosticsBridgeActionLabel === "function") {
      return bridge.diagnosticsBridgeActionLabel(action);
    }
    const verb = action.kind === "tail" ? "Read" : "Open";
    return action.label || `${verb} ${String(action.target || "").replaceAll("_", " ")}`;
  }

  function diagnosticsOrderedActions(actions) {
    const candidates = Array.isArray(actions) ? actions.filter((action) => action && action.target) : [];
    const bridge = diagnosticsBridgeApi();
    if (typeof bridge.diagnosticsBridgeOrderedActions === "function") {
      return bridge.diagnosticsBridgeOrderedActions(candidates);
    }
    return candidates;
  }

  function diagnosticsActionGroups(actions) {
    const ordered = diagnosticsOrderedActions(actions);
    return {
      readFirst: ordered.filter((action) => action.kind === "tail"),
      openNext: ordered.filter((action) => action.kind !== "tail"),
    };
  }

  function diagnosticsActionGroupText(actions) {
    return actions.length ? actions.map(diagnosticsActionLabel).join(" -> ") : "none inferred";
  }

  function diagnosticsActionPlanLines(sourceLabel, actions, contextText = "") {
    const groups = diagnosticsActionGroups(actions);
    const lines = [
      "Diagnostics action plan:",
      `Source: ${sourceLabel || "selected diagnostics row"}`,
      `Read first: ${diagnosticsActionGroupText(groups.readFirst)}`,
      `Open next: ${diagnosticsActionGroupText(groups.openNext)}`,
    ];
    if (contextText) lines.push(`Why: ${contextText}`);
    lines.push("Order rationale: read bounded backend text first when available, then shell-open folders/files only when more context is needed.");
    lines.push("Guardrail: action targets are backend allowlist identifiers, not frontend filesystem paths.");
    return lines;
  }

  function appendDiagnosticsActionGroup(container, groupLabel, actions) {
    const actionRows = Array.isArray(actions) ? actions : [];
    if (!container || !actionRows.length) return;
    const key = String(groupLabel || "").toLowerCase().includes("read") ? "readFirst" : "openNext";
    const groups = { readFirst: [], openNext: [] };
    groups[key] = actionRows;
    window.mediaPipelineDom?.renderOpenTargetActionGroups?.(container, groups, {
      append: true,
      labelFor: diagnosticsActionLabel,
      groupDataset: "diagnosticsActionGroup",
      actionDataset: "diagnosticsLogAction",
      targetDataset: "diagnosticsLogTarget",
      onTail: (target, _action, button) => requestDiagnosticsTail(target, button),
      onOpen: (target, _action, button) => requestDiagnosticsOpen(target, button),
    });
    const groupValue = String(groupLabel || "").toLowerCase().replace(/\s+/g, "-");
    container.querySelectorAll("button[data-open-target-action-group]").forEach((button) => {
      if (button.dataset.openTargetActionGroup !== groupValue) return;
      if (button.dataset.openTargetAction === "tail") {
        button.dataset.readDiagnosticsTail = button.dataset.openTarget || "";
      } else {
        button.dataset.openDiagnostics = button.dataset.openTarget || "";
      }
    });
  }

  function diagnosticsArtifactsForLine(line) {
    const text = String(line || "");
    return diagnosticsArtifactTargets
      .filter((artifact) => artifact.patterns.some((pattern) => pattern.test(text)))
      .slice(0, 4);
  }

  function initDiagnosticsViewEvents() {
    const logFilter = byId("diagnostics-log-filter");
    if (logFilter) logFilter.addEventListener("input", () => renderDiagnosticsLogTable());
    const logSeverity = byId("diagnostics-log-severity");
    if (logSeverity) logSeverity.addEventListener("change", () => renderDiagnosticsLogTable());
    const tailButton = byId("diagnostics-tail-refresh-button");
    if (tailButton) tailButton.addEventListener("click", requestDiagnosticsTail);
    document.querySelectorAll("[data-read-diagnostics-tail]").forEach((button) => {
      if (button.dataset.diagnosticsTailBound === "true") return;
      button.dataset.diagnosticsTailBound = "true";
      button.addEventListener("click", () => requestDiagnosticsTail(button.dataset.readDiagnosticsTail || "", button));
    });
    document.querySelectorAll("[data-tdarr-matrix-audit-action]").forEach((button) => {
      button.addEventListener("click", () => requestTdarrMatrixAudit(button.dataset.tdarrMatrixAuditAction || ""));
    });
    const tdarrDeleteConfirm = byId("tdarr-matrix-delete-confirm");
    if (tdarrDeleteConfirm) tdarrDeleteConfirm.addEventListener("input", updateTdarrMatrixActionGates);
    document.querySelectorAll("[data-tdarr-proof-pack-view]").forEach((button) => {
      button.addEventListener("click", () => {
        tdarrMatrixConsoleState.activePack = button.dataset.tdarrProofPackView || "proof-pack";
        renderTdarrMatrixProofPackRows();
      });
    });
    const tdarrFilter = byId("tdarr-matrix-audit-filter");
    if (tdarrFilter) tdarrFilter.addEventListener("input", () => {
      renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings });
      renderTdarrMatrixProofPackRows();
    });
    const tdarrSeverity = byId("tdarr-matrix-audit-severity-filter");
    if (tdarrSeverity) tdarrSeverity.addEventListener("change", () => renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings }));
    const tdarrBucket = byId("tdarr-matrix-audit-bucket-filter");
    if (tdarrBucket) tdarrBucket.addEventListener("change", () => {
      renderTdarrMatrixAuditFindings({ findings: tdarrMatrixConsoleState.findings });
      renderTdarrMatrixProofPackRows();
    });
    const tdarrLoadLatest = byId("tdarr-matrix-audit-load-latest");
    if (tdarrLoadLatest) tdarrLoadLatest.addEventListener("click", () => requestTdarrMatrixConsole());
    const tdarrRerunSelected = byId("tdarr-matrix-audit-rerun-selected");
    if (tdarrRerunSelected) tdarrRerunSelected.addEventListener("click", () => requestTdarrMatrixRerun("selected"));
    const tdarrRerunFailures = byId("tdarr-matrix-audit-rerun-failures");
    if (tdarrRerunFailures) tdarrRerunFailures.addEventListener("click", () => requestTdarrMatrixRerun("latest_failures"));
    const compareRefresh = byId("tdarr-matrix-compare-refresh");
    if (compareRefresh) compareRefresh.addEventListener("click", requestTdarrMatrixRunComparison);
    updateTdarrMatrixActionGates();
  }

  const diagnosticsArtifactTargets = [
    {
      name: "BDPGS OCR settings evidence",
      target: "",
      patterns: [/\bbdpgs\b/i, /\bpgs(?:tosrt|[-_\s]to[-_\s]srt)?\b/i, /\bpgstosrt\b/i, /\btessdata\b/i, /\btesseract\b/i, /\bocr\b/i, /\bsubtitle(?:s)?\b.*\bsrt\b/i],
      hint: "Select the Diagnostics State Artifact Summary row 'settings_bdpgs_ocr_paths' and then review Settings > Media Output if saved OCR tool or tessdata path evidence is blocked. Diagnostics does not edit settings or run OCR.",
    },
    {
      name: "VobSub OCR settings evidence",
      target: "",
      patterns: [/\bvobsub\b/i, /\bdvd[_\s-]?subtitle\b/i, /\bs[_-]?vobsub\b/i, /\bseconv\b/i, /\btesseract\b/i, /\bidx\b/i, /\bsub\b/i, /\bocr\b/i, /\bsubtitle(?:s)?\b.*\bsrt\b/i],
      hint: "Select the Diagnostics State Artifact Summary row 'settings_vobsub_ocr_paths' and then review Settings > Media Output if saved Subtitle Edit or Tesseract evidence is blocked. Diagnostics does not edit settings or run OCR.",
    },
    {
      name: "ActiveJobs",
      target: "active_jobs",
      patterns: [/\bactivejobs\b/i, /\bactive job/i, /\borphan(?:ed)?\b/i, /\bpid\b/i, /\brunning\b/i, /\blaunching\b/i],
      hint: "Open Active Jobs and compare with Close Readiness before closing or clearing runtime state.",
    },
    {
      name: "Progress state",
      target: "state",
      patterns: [/\bprogress\b/i, /\bpipeline_progress\b/i, /\bcurrentstagepercent\b/i],
      hint: "Open State Folder and Run Logs; malformed progress can hide live work from the shell.",
    },
    {
      name: "Run logs",
      target: "run_logs",
      tailTarget: "last_stderr_log",
      tailName: "Last Stderr",
      patterns: [/\berror\b/i, /\bexception\b/i, /\btraceback\b/i, /\bffmpeg\b/i, /\bstderr\b/i, /\bfailed\b/i, /\bfailure\b/i],
      hint: "Open Run Logs and Last Stderr first, then check the newest failure or audit report if present.",
    },
    {
      name: "Launch logs",
      target: "last_stderr_log",
      tailTarget: "last_stderr_log",
      tailName: "Last Stderr",
      patterns: [/\blaunch\b/i, /\bstdout\b/i, /\bstderr\b/i, /\bstart(?:ed)?\b/i, /\bsubprocess\b/i],
      hint: "Open Last Stdout and Last Stderr to inspect the launcher boundary.",
    },
    {
      name: "Queue snapshot",
      target: "queue_snapshot",
      tailTarget: "queue_snapshot",
      tailName: "Queue Snapshot",
      patterns: [/\bqueue\b/i, /\bclaim\b/i, /\breclaim\b/i, /\bskipped\b/i, /\brunnable\b/i],
      hint: "Open Queue Snapshot when processing appears idle but rows should be runnable.",
    },
    {
      name: "Pending publish",
      target: "pending_publish",
      tailTarget: "last_stderr_log",
      tailName: "Last Stderr",
      patterns: [/\bpending publish\b/i, /\bpublish\b/i, /\bpark(?:ed)?\b/i, /\bdeferred\b/i, /\bdrain\b/i, /\borphan payload\b/i, /\bmissing sidecar\b/i, /\bunreadable manifest\b/i, /\binvalid manifest\b/i],
      hint: "Open Pending Publish and read Last Stderr before rerunning work that may already be parked, orphaned, or blocked by malformed manifests.",
    },
    {
      name: "Failure reports",
      target: "failed_reports",
      tailTarget: "latest_failure_report",
      tailName: "Latest Failure Report",
      patterns: [/\bfailure report\b/i, /\bfailed marker\b/i, /\bclassification\b/i, /\bremediation\b/i],
      hint: "Open Failure Reports and Failure Markers to confirm the last deterministic failure class.",
    },
    {
      name: "Cluster log",
      target: "cluster_log",
      tailTarget: "cluster_log",
      tailName: "Cluster Log",
      patterns: [/\bworker\b/i, /\bcoordinator\b/i, /\bcluster\b/i, /\bheartbeat\b/i, /\bnetwork\b/i],
      hint: "Open Cluster Log for coordinator/worker events. WebView network lifecycle remains read-only.",
    },
  ];

const diagnosticsActiveJobsModule = window.__diagnosticsActiveJobsModule || {};
delete window.__diagnosticsActiveJobsModule;
const diagnosticsActiveJobs = typeof diagnosticsActiveJobsModule.createDiagnosticsActiveJobsModule === "function"
  ? diagnosticsActiveJobsModule.createDiagnosticsActiveJobsModule({
    appendCells,
    appendDiagnosticsActionGroup,
    boundedDiagnosticsText,
    byId,
    clearRows,
    diagnosticsActionGroups,
    diagnosticsActionPlanLines,
    makeRowSelectable,
    setText,
    updateTableStatusLegend,
  })
  : {};
const activeJobRowKey = diagnosticsActiveJobs.activeJobRowKey || function () { return ""; };
const getSelectedActiveJobRow = diagnosticsActiveJobs.getSelectedActiveJobRow || function () { return null; };
const selectActiveJobRow = diagnosticsActiveJobs.selectActiveJobRow || function () {};
const activeJobDiagnosticsActions = diagnosticsActiveJobs.activeJobDiagnosticsActions || function () { return []; };
const activeJobRowPosture = diagnosticsActiveJobs.activeJobRowPosture || function () { return "review"; };
const activeJobRowsStatusText = diagnosticsActiveJobs.activeJobRowsStatusText || function () { return "No ActiveJobs rows"; };
const diagnosticsActiveJobRealMediaTraceLines = diagnosticsActiveJobs.diagnosticsActiveJobRealMediaTraceLines || function () { return []; };
const renderActiveJobDiagnosticsActions = diagnosticsActiveJobs.renderActiveJobDiagnosticsActions || function () {};
const renderActiveJobRows = diagnosticsActiveJobs.renderActiveJobRows || function () {};
const renderActiveJobDetail = diagnosticsActiveJobs.renderActiveJobDetail || function () {};

const diagnosticsLogModule = window.__diagnosticsLogModule || {};
delete window.__diagnosticsLogModule;
const diagnosticsLog = typeof diagnosticsLogModule.createDiagnosticsLogModule === "function"
  ? diagnosticsLogModule.createDiagnosticsLogModule({
    appendCells,
    appendDiagnosticsActionGroup,
    boundedDiagnosticsText,
    byId,
    clearRows,
    diagnosticsActionGroups,
    diagnosticsActionPlanLines,
    diagnosticsArtifactsForLine,
    diagnosticsSeverityForLine,
    diagnosticsSourceLines,
    makeRowSelectable,
    readLastDiagnosticsLogRows: () => lastDiagnosticsLogRows,
    setText,
    updateTableStatusLegend,
    writeLastDiagnosticsLogRows: (rows) => { lastDiagnosticsLogRows = Array.isArray(rows) ? rows : []; },
  })
  : {};
const diagnosticsLineTimestamp = diagnosticsLog.diagnosticsLineTimestamp || function () { return ""; };
const diagnosticsLogRows = diagnosticsLog.diagnosticsLogRows || function () { return []; };
const diagnosticsLogRowKey = diagnosticsLog.diagnosticsLogRowKey || function () { return ""; };
const diagnosticsLogRowActions = diagnosticsLog.diagnosticsLogRowActions || function () { return []; };
const diagnosticsLogRowNextStep = diagnosticsLog.diagnosticsLogRowNextStep || function () { return ""; };
const diagnosticsLogRealMediaTraceLines = diagnosticsLog.diagnosticsLogRealMediaTraceLines || function () { return []; };
const diagnosticsLogGuidanceLines = diagnosticsLog.diagnosticsLogGuidanceLines || function () { return []; };
const renderDiagnosticsLogActions = diagnosticsLog.renderDiagnosticsLogActions || function () {};
const filteredDiagnosticsLogRows = diagnosticsLog.filteredDiagnosticsLogRows || function () { return []; };
const getLastDiagnosticsLogRows = diagnosticsLog.getLastDiagnosticsLogRows || function () { return lastDiagnosticsLogRows.slice(); };
const selectDiagnosticsLogRow = diagnosticsLog.selectDiagnosticsLogRow || function () {};
const getSelectedDiagnosticsLogRow = diagnosticsLog.getSelectedDiagnosticsLogRow || function () { return null; };
const renderDiagnosticsLogRows = diagnosticsLog.renderDiagnosticsLogRows || function () {};
const renderDiagnosticsLogDetail = diagnosticsLog.renderDiagnosticsLogDetail || function () {};
const renderDiagnosticsLogTable = diagnosticsLog.renderDiagnosticsLogTable || function () {};

const diagnosticsInvestigationModule = window.__diagnosticsInvestigationModule || {};
delete window.__diagnosticsInvestigationModule;
const diagnosticsInvestigation = typeof diagnosticsInvestigationModule.createDiagnosticsInvestigationModule === "function"
  ? diagnosticsInvestigationModule.createDiagnosticsInvestigationModule({
    appendCells,
    appendDiagnosticsActionGroup,
    byId,
    clearRows,
    diagnosticsActionGroups,
    diagnosticsMalformedStateLines,
    diagnosticsOrderedActions,
    diagnosticsSafeRows,
    diagnosticsSamplePolicyReconciliation,
    diagnosticsTextLines,
    makeRowSelectable,
    setText,
    updateTableStatusLegend,
  })
  : {};
const diagnosticsStateIssueRows = diagnosticsInvestigation.diagnosticsStateIssueRows || function () { return []; };
const diagnosticsPageReviewRows = diagnosticsInvestigation.diagnosticsPageReviewRows || function () { return []; };
const diagnosticsCrossPageConflictRows = diagnosticsInvestigation.diagnosticsCrossPageConflictRows || function () { return []; };
const diagnosticsConflictSignalLabel = diagnosticsInvestigation.diagnosticsConflictSignalLabel || function (item) { return String(item || "cross-page conflict"); };
const diagnosticsCommandIssueRows = diagnosticsInvestigation.diagnosticsCommandIssueRows || function () { return []; };
const diagnosticsInvestigationAddAction = diagnosticsInvestigation.diagnosticsInvestigationAddAction || function () {};
const diagnosticsInvestigationActions = diagnosticsInvestigation.diagnosticsInvestigationActions || function () { return []; };
const diagnosticsInvestigationStatus = diagnosticsInvestigation.diagnosticsInvestigationStatus || function () { return "No blockers"; };
const diagnosticsListText = diagnosticsInvestigation.diagnosticsListText || function (value) { return Array.isArray(value) && value.length ? value.join(", ") : "none"; };
const diagnosticsRowLabel = diagnosticsInvestigation.diagnosticsRowLabel || function () { return "Diagnostics row"; };
const diagnosticsOwnerDefaultAction = diagnosticsInvestigation.diagnosticsOwnerDefaultAction || function () { return "Review owning page."; };
const diagnosticsOwnerRowSeverity = diagnosticsInvestigation.diagnosticsOwnerRowSeverity || function () { return "review"; };
const diagnosticsOwnerHandoffRowKey = diagnosticsInvestigation.diagnosticsOwnerHandoffRowKey || function () { return ""; };
const diagnosticsCompletedFinalTrustStepForRow = diagnosticsInvestigation.diagnosticsCompletedFinalTrustStepForRow || function () { return {}; };
const diagnosticsCompletedFinalTrustLines = diagnosticsInvestigation.diagnosticsCompletedFinalTrustLines || function () { return []; };
const diagnosticsCompletedPolicyReconciliationLines = diagnosticsInvestigation.diagnosticsCompletedPolicyReconciliationLines || function () { return []; };
const diagnosticsOwnerHandoffRows = diagnosticsInvestigation.diagnosticsOwnerHandoffRows || function () { return []; };
const diagnosticsOwnerHandoffStatus = diagnosticsInvestigation.diagnosticsOwnerHandoffStatus || function () { return "No flagged rows"; };
const diagnosticsOwnerHandoffSummaryLines = diagnosticsInvestigation.diagnosticsOwnerHandoffSummaryLines || function () { return []; };
const diagnosticsOwnerHandoffActions = diagnosticsInvestigation.diagnosticsOwnerHandoffActions || function () { return []; };
const diagnosticsOwnerPageId = diagnosticsInvestigation.diagnosticsOwnerPageId || function () { return ""; };
const diagnosticsOwnerSelectFunction = diagnosticsInvestigation.diagnosticsOwnerSelectFunction || function () { return null; };
const diagnosticsOwnerNavigationLabel = diagnosticsInvestigation.diagnosticsOwnerNavigationLabel || function () { return "Go To Owner Row"; };
const setDiagnosticsOwnerHandoffNavStatus = diagnosticsInvestigation.setDiagnosticsOwnerHandoffNavStatus || function () {};
const navigateDiagnosticsOwnerHandoffRow = diagnosticsInvestigation.navigateDiagnosticsOwnerHandoffRow || function () { return false; };
const getSelectedDiagnosticsOwnerHandoffRow = diagnosticsInvestigation.getSelectedDiagnosticsOwnerHandoffRow || function () { return null; };
const selectDiagnosticsOwnerHandoffRow = diagnosticsInvestigation.selectDiagnosticsOwnerHandoffRow || function () {};
const renderDiagnosticsOwnerHandoffActions = diagnosticsInvestigation.renderDiagnosticsOwnerHandoffActions || function () {};
const diagnosticsSampleValidationComparisonLines = diagnosticsInvestigation.diagnosticsSampleValidationComparisonLines || function () { return []; };
const renderDiagnosticsOwnerHandoffDetail = diagnosticsInvestigation.renderDiagnosticsOwnerHandoffDetail || function () {};
const renderDiagnosticsOwnerHandoffTable = diagnosticsInvestigation.renderDiagnosticsOwnerHandoffTable || function () {};
const renderDiagnosticsOwnerHandoff = diagnosticsInvestigation.renderDiagnosticsOwnerHandoff || function () {};
const isDiagnosticsOpenCommand = diagnosticsInvestigation.isDiagnosticsOpenCommand || function () { return false; };
const diagnosticsOpenHistoryLine = diagnosticsInvestigation.diagnosticsOpenHistoryLine || function () { return ""; };
const renderDiagnosticsOpenHistory = diagnosticsInvestigation.renderDiagnosticsOpenHistory || function () {};
  function diagnosticsSourceLines(diagnostics) {
    const groups = [
      ["Recent errors", diagnostics?.recent_errors],
      ["Recent events", diagnostics?.recent_events],
      ["ActiveJobs", diagnostics?.active_jobs],
      ["Warnings", diagnostics?.warnings],
      ["Pipeline log tail", diagnostics?.log_tail],
      ["Launch logs", diagnostics?.launch_logs],
    ];
    const entries = [];
    groups.forEach(([source, value]) => {
      diagnosticsTextLines(value).slice(-50).forEach((line) => {
        entries.push({ source, line });
      });
    });
    return entries;
  }

  function diagnosticsArtifactMatches(diagnostics) {
    const entries = diagnosticsSourceLines(diagnostics || {});
    return diagnosticsArtifactTargets
      .map((artifact) => {
        const samples = [];
        let count = 0;
        entries.forEach((entry) => {
          if (!artifact.patterns.some((pattern) => pattern.test(entry.line))) return;
          count += 1;
          if (samples.length < 3) {
            samples.push(`${entry.source}: ${entry.line}`);
          }
        });
        return {
          ...artifact,
          count,
          samples,
        };
      })
      .filter((artifact) => artifact.count > 0)
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
  }

  function renderDiagnosticsDrilldownActions(matches) {
    const actions = byId("diagnostics-drilldown-actions");
    if (!actions) return;
    actions.replaceChildren();
    matches.slice(0, 6).forEach((artifact) => {
      const openTarget = String(artifact.target || "").trim();
      if (openTarget) {
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.dataset.openDiagnostics = openTarget;
        button.textContent = `Open ${artifact.name}`;
        button.addEventListener("click", () => requestDiagnosticsOpen(openTarget, button));
        actions.appendChild(button);
      }
      if (artifact.tailTarget) {
        const tailButton = document.createElement("button");
        tailButton.className = "secondary-button";
        tailButton.type = "button";
        tailButton.dataset.readDiagnosticsTail = artifact.tailTarget;
        tailButton.textContent = `Read ${artifact.tailName || artifact.name}`;
        tailButton.addEventListener("click", () => requestDiagnosticsTail(artifact.tailTarget, tailButton));
        actions.appendChild(tailButton);
      }
    });
  }

  function renderDiagnosticsDrilldown(diagnostics) {
    const matches = diagnosticsArtifactMatches(diagnostics || {});
    renderDiagnosticsDrilldownActions(matches);
    const status = matches.length ? `${matches.length} artifact hint(s)` : "No artifacts";
    setDiagnosticsPanelStatus("diagnostics-drilldown-status", status, matches.length ? "warning" : "empty");
    const lines = [
      "Artifact drilldown is read-only. Open and Read buttons below use backend allowlists; the frontend never sends arbitrary paths.",
    ];
    if (!matches.length) {
      lines.push("No artifact-specific clues were found in the current diagnostics payload.");
      lines.push("Close Readiness remains the first stop before clearing state, closing the app, or deleting runtime files.");
      setText("diagnostics-drilldown-summary", lines.join("\n"));
      return;
    }
    matches.forEach((artifact) => {
      const openTarget = artifact.target || "none; use row guidance";
      lines.push("", `${artifact.name} (${artifact.count} clue${artifact.count === 1 ? "" : "s"}; open target: ${openTarget})`);
      lines.push(`Next step: ${artifact.hint}`);
      artifact.samples.forEach((sample) => lines.push(`- ${sample}`));
    });
    lines.push("", "Close Readiness remains the first stop before clearing state, closing the app, or deleting runtime files.");
    setText("diagnostics-drilldown-summary", lines.join("\n"));
  }

  function renderDiagnosticsTriage(diagnostics) {
    const recentErrors = diagnosticsTextLines(diagnostics?.recent_errors);
    const recentEvents = diagnosticsTextLines(diagnostics?.recent_events);
    const activeJobs = diagnosticsTextLines(diagnostics?.active_jobs);
    const warnings = diagnosticsTextLines(diagnostics?.warnings);
    const logLines = diagnosticsTextLines(diagnostics?.log_tail).slice(-20);
    const launchLines = diagnosticsTextLines(diagnostics?.launch_logs).slice(-20);
    const allLines = [
      ...recentErrors,
      ...recentEvents,
      ...activeJobs,
      ...warnings,
      ...logLines,
      ...launchLines,
    ];
    const counts = allLines.reduce((acc, line) => {
      const severity = diagnosticsSeverityForLine(line);
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});
    const malformedLines = diagnosticsMalformedStateLines(allLines).slice(0, 8);
    const status = counts.error
      ? "Errors"
      : counts.warning
        ? "Warnings"
        : counts.active
          ? "Active"
          : allLines.length
            ? "Informational"
            : "No issues";
    setDiagnosticsPanelStatus(
      "diagnostics-triage-status",
      status,
      counts.error ? "blocked" : counts.warning ? "warning" : counts.active ? "running" : allLines.length ? "ready" : "empty",
    );
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload: diagnostics,
        label: "Diagnostics",
        rowCount: allLines.length,
        artifactLine: `Readable lines: errors ${recentErrors.length}; events ${recentEvents.length}; ActiveJobs ${activeJobs.length}; warnings ${warnings.length}.`,
        refreshAction: "Use Refresh Diagnostics or topbar Refresh. This re-reads logs/state only and does not repair, clear, delete, rerun, publish, or move files.",
      })
      : [];
    const lines = [
      ...freshnessLines,
      `Recent errors: ${recentErrors.length}`,
      `Recent events: ${recentEvents.length}`,
      `ActiveJobs lines: ${activeJobs.length}`,
      `Warnings: ${warnings.length}`,
      `Severity groups: error ${counts.error || 0}; warning ${counts.warning || 0}; active ${counts.active || 0}; info ${counts.info || 0}`,
    ];
    if (malformedLines.length) {
      lines.push("", "Malformed/stale runtime-state hint(s):");
      malformedLines.forEach((line) => lines.push(`- ${line}`));
      lines.push("Next step: Check Close Readiness first. If it is blocked, inspect ActiveJobs, progress files, Run Logs, and State Folder before closing or clearing runtime files.");
    } else if (counts.error) {
      lines.push("", "Next step: Open Run Logs and Last Stderr, then review the newest failure/audit report if one exists.");
    } else if (counts.warning) {
      lines.push("", "Next step: Review warnings and refresh once; if the same warning persists, open the relevant state/log location below.");
    } else if (counts.active) {
      lines.push("", "Next step: Active work appears to be present. Use Close Readiness and ActiveJobs before exiting.");
    } else {
      lines.push("", "Next step: No diagnostics issues are currently visible from the backend snapshot.");
    }
    setText("diagnostics-triage-summary", lines.join("\n"));
  }

  function diagnosticsFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries
      .sort(([left], [right]) => String(left).localeCompare(String(right)))
      .map(([key, count]) => `${key || "unknown"}=${count}`)
      .join(", ");
  }

  function diagnosticsSafeRows(payload) {
    return Array.isArray(payload?.rows) ? payload.rows : [];
  }

  function diagnosticsFirstResponseAdd(rows, key, step, posture, evidence, action) {
    rows.push({ key, step, posture, evidence, action });
  }

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
        ? "Do not close or start competing work until ActiveJobs, Progress, Last Stderr, and Run Logs agree."
        : closeSafe
          ? "Close-readiness is not blocking; continue with state/log checks if another page looks wrong."
          : "Wait for close-readiness or inspect ActiveJobs before treating the session as idle.",
    );

    diagnosticsFirstResponseAdd(
      rows,
      "activejobs-progress",
      "ActiveJobs / progress",
      activeJobBlocked ? "Blocked review" : activeJobReview ? "Review" : activeRows.length ? "Read evidence" : "Ready",
      `active-job rows=${activeRows.length}; blocked=${activeJobBlocked}; review=${activeJobReview}; pipeline state=${snapshotState}`,
      activeJobBlocked
        ? "Select the malformed/orphaned ActiveJobs row, read Last Stderr, then compare Close Readiness before clearing or rerunning."
        : activeJobReview
          ? "Inspect ActiveJobs detail and progress freshness before closing or starting more work."
          : activeRows.length
            ? "Use ActiveJobs as process-lifecycle evidence only; Completed/Pending still prove output state."
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

  function diagnosticsPayloadFirstString(payload, keys) {
    for (const key of keys || []) {
      const value = payload?.[key];
      if (value === undefined || value === null || value === false) continue;
      const text = Array.isArray(value) ? value.join("; ") : String(value);
      if (text.trim()) return text.trim();
    }
    return "";
  }

  function diagnosticsPayloadFlag(payload, keys) {
    return (keys || []).some((key) => Boolean(payload?.[key]));
  }

  function diagnosticsLogPanelStatus(value, payload, options = {}) {
    const textValue = String(value || "");
    const metadata = diagnosticsPayloadFirstString(payload, options.stateKeys || []);
    const lowerMetadata = metadata.toLowerCase();
    const errorText = diagnosticsPayloadFirstString(payload, options.errorKeys || []);
    const label = options.label || "Diagnostics log";
    if (errorText || /\b(?:error|failed|failure|exception|read[_ -]?error)\b/.test(lowerMetadata)) {
      return {
        label: "Read error",
        state: "blocked",
        fallback: `${label} read error. ${errorText || metadata || "Backend diagnostics payload reported a read error."}`,
      };
    }
    if (diagnosticsPayloadFlag(payload, options.unavailableKeys || []) || /\bunavailable\b/.test(lowerMetadata)) {
      return {
        label: "Unavailable",
        state: "warning",
        fallback: `${label} unavailable. Refresh diagnostics after confirming Local API and backend state.`,
      };
    }
    if (diagnosticsPayloadFlag(payload, options.missingKeys || []) || /\b(?:missing|not found|not_found)\b/.test(lowerMetadata)) {
      return {
        label: "Missing",
        state: "warning",
        fallback: `${label} missing. Use File Log bounded tail or State Summary before acting on this absence.`,
      };
    }
    if (diagnosticsPayloadFlag(payload, options.truncatedKeys || []) || /\b(?:truncated|partial)\b/.test(lowerMetadata)) {
      return {
        label: "Loaded truncated",
        state: "warning",
        fallback: textValue || `${label} loaded with a truncation or partial-read marker.`,
      };
    }
    if (textValue.trim()) {
      return { label: "Loaded", state: "ready", fallback: textValue };
    }
    return {
      label: "Empty",
      state: "empty",
      fallback: options.emptyText || `No ${label.toLowerCase()} loaded.`,
    };
  }

  function renderDiagnostics(diagnostics) {
    const payload = diagnostics || {};
    renderDiagnosticsTriage(payload);
    renderDiagnosticsDrilldown(payload);
    renderDiagnosticsLogRows(payload);
    setText("recent-errors", (payload.recent_errors || []).join("\n") || "No recent errors.");
    setText("recent-events", (payload.recent_events || []).join("\n") || "No recent events.");
    setText("active-jobs", (payload.active_jobs || []).join("\n") || "No ActiveJobs records.");
    renderActiveJobRows(payload.active_job_rows || []);
    const pipelineLog = String(payload.log_tail || "");
    const launchLog = String(payload.launch_logs || "");
    const pipelineStatus = diagnosticsLogPanelStatus(pipelineLog, payload, {
      label: "Pipeline log tail",
      stateKeys: ["log_tail_state", "log_tail_status", "pipeline_log_state", "pipeline_log_status"],
      errorKeys: ["log_tail_error", "pipeline_log_error", "log_tail_read_error"],
      unavailableKeys: ["log_tail_unavailable", "pipeline_log_unavailable"],
      missingKeys: ["log_tail_missing", "pipeline_log_missing"],
      truncatedKeys: ["log_tail_truncated", "pipeline_log_truncated"],
      emptyText: "No pipeline log tail loaded.",
    });
    const launchStatus = diagnosticsLogPanelStatus(launchLog, payload, {
      label: "Launch log",
      stateKeys: ["launch_logs_state", "launch_log_state", "launch_logs_status", "launch_log_status"],
      errorKeys: ["launch_logs_error", "launch_log_error", "launch_logs_read_error"],
      unavailableKeys: ["launch_logs_unavailable", "launch_log_unavailable"],
      missingKeys: ["launch_logs_missing", "launch_log_missing"],
      truncatedKeys: ["launch_logs_truncated", "launch_log_truncated"],
      emptyText: "No launch logs loaded.",
    });
    setDiagnosticsPanelStatus("diagnostics-pipeline-log-status", pipelineStatus.label, pipelineStatus.state);
    setDiagnosticsPanelStatus("diagnostics-launch-log-status", launchStatus.label, launchStatus.state);
    setText("log-tail", pipelineLog || pipelineStatus.fallback);
    setText("launch-logs", launchLog || launchStatus.fallback);
  }

  function diagnosticsFailureMessage(failure) {
    const message = failure?.message || failure?.reason || "request failed";
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    return `Refresh failed at ${time}; showing stale data if previously loaded. ${message}`;
  }

  function renderDiagnosticsRefreshFailures(failures = []) {
    const items = Array.isArray(failures) ? failures : [];
    const byName = (name) => items.find((item) => String(item?.name || "").toLowerCase() === name);
    const diagnosticsFailure = byName("diagnostics");
    if (diagnosticsFailure) {
      const message = diagnosticsFailureMessage(diagnosticsFailure);
      [
        "diagnostics-triage-status",
        "diagnostics-drilldown-status",
        "diagnostics-log-status",
        "diagnostics-pipeline-log-status",
        "diagnostics-launch-log-status",
        "active-job-detail-status",
      ].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
    const stateFailure = byName("diagnostics state summary");
    if (stateFailure) {
      const message = diagnosticsFailureMessage(stateFailure);
      [
        "diagnostics-state-summary-status",
        "diagnostics-state-recovery-status",
        "diagnostics-state-triage-status",
      ].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
    const commandsFailure = byName("commands");
    if (commandsFailure) {
      const message = diagnosticsFailureMessage(commandsFailure);
      [
        "diagnostics-command-status",
        "diagnostics-command-drilldown-status",
        "diagnostics-command-owner-status",
        "diagnostics-command-evidence-status",
        "diagnostics-command-resolution-status",
      ].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
    const contractFailure = byName("contract");
    if (contractFailure) {
      const message = diagnosticsFailureMessage(contractFailure);
      ["api-contract-status", "api-contract-safety-status"].forEach((id) => setDiagnosticsPanelStatus(id, message, "warning"));
    }
  }

  async function requestTdarrMatrixConsole(runId = "") {
    const query = new URLSearchParams();
    const selectedRun = String(runId || "").trim();
    if (selectedRun) query.set("run_id", selectedRun);
    query.set("finding_limit", "250");
    setTdarrMatrixAuditStatus("Loading latest...", "loading");
    try {
      const payload = await apiGet(`/api/diagnostics/tdarr-matrix/latest?${query.toString()}`, { timeoutMs: 15000 });
      renderTdarrMatrixConsole(payload);
      if (tdarrMatrixConsoleState.runs.length >= 2) {
        await requestTdarrMatrixRunComparison();
      } else {
        renderTdarrMatrixRunComparison({ counts: { new: 0, resolved: 0, repeated: 0, changed: 0 } });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setTdarrMatrixAuditStatus("Load error", "blocked");
      setText("tdarr-matrix-console-summary", message);
      renderTdarrMatrixAuditFindings({ findings: [] });
      tdarrMatrixConsoleState.smokePackRows = [];
      tdarrMatrixConsoleState.proofPackRows = [];
      renderTdarrMatrixProofPackRows();
      renderTdarrMatrixBucketCoverage({ bucket_summary: [] });
      updateTdarrMatrixActionGates();
    }
  }

  async function requestTdarrMatrixRunComparison() {
    const left = String(byId("tdarr-matrix-compare-left")?.value || "").trim();
    const right = String(byId("tdarr-matrix-compare-right")?.value || "").trim();
    const query = new URLSearchParams();
    if (left) query.set("left_run_id", left);
    if (right) query.set("right_run_id", right);
    try {
      const payload = await apiGet(`/api/diagnostics/tdarr-matrix/compare?${query.toString()}`, { timeoutMs: 15000 });
      renderTdarrMatrixRunComparison(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setDiagnosticsPanelStatus("tdarr-matrix-run-compare-status", message, "blocked");
      renderTdarrMatrixRunComparison({ counts: { new: 0, resolved: 0, repeated: 0, changed: 0 } });
    }
  }

  async function requestTdarrMatrixEvidenceOpen(target, findingKey = "", runId = "") {
    const requestedKey = String(findingKey || "").trim();
    const selected = requestedKey
      ? tdarrMatrixConsoleState.findings.find((item) => item.finding_key === requestedKey)
      : tdarrMatrixConsoleState.findings.find((item) => item.finding_key === tdarrMatrixConsoleState.selectedFindingKey);
    const normalized = String(target || "").trim();
    const effectiveFindingKey = requestedKey || selected?.finding_key || "";
    const effectiveRunId = String(runId || selected?.run_id || tdarrMatrixConsoleState.latestRunId || "").trim();
    if (!effectiveFindingKey || !effectiveRunId || !normalized) return;
    try {
      const result = await apiPost("/api/diagnostics/tdarr-matrix/evidence/open", {
        run_id: effectiveRunId,
        finding_key: effectiveFindingKey,
        target: normalized,
      });
      appendCommandResult(result);
      setDiagnosticsPanelStatus("tdarr-matrix-audit-evidence-status", result.message || "Evidence open request sent.", result.ok === false ? "blocked" : "ready");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "diagnostics.tdarr_matrix.evidence_open",
        ok: false,
        severity: "error",
        message,
      });
      setDiagnosticsPanelStatus("tdarr-matrix-audit-evidence-status", message, "blocked");
    }
  }

  async function requestTdarrMatrixRerun(selection) {
    if (rejectTdarrMatrixAuditWhileBusy(selection)) return;
    const normalized = String(selection || "selected").trim();
    const keys = normalized === "latest_failures" ? [] : Array.from(tdarrMatrixConsoleState.selectedFindingKeys);
    setTdarrMatrixAuditBusy(true);
    setTdarrMatrixAuditStatus("Running...", "loading");
    setTdarrMatrixAuditDetail([normalized === "latest_failures" ? "Rerunning latest failure cases in a new Tdarr Proof Pack run root." : "Rerunning selected Tdarr Proof Pack cases in a new run root."]);
    try {
      const result = await apiPost("/api/diagnostics/tdarr-matrix/rerun", {
        source_run_id: tdarrMatrixConsoleState.latestRunId,
        selection: normalized,
        finding_keys: keys,
      });
      appendCommandResult(result);
      setTdarrMatrixAuditStatus(result.ok ? "Complete" : result.severity || "Failed", result.ok ? "ready" : "blocked");
      setTdarrMatrixAuditDetail(tdarrMatrixAuditDetailLines(result));
      renderTdarrMatrixAuditFindings(result);
      await requestTdarrMatrixConsole();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "diagnostics.tdarr_matrix.rerun",
        ok: false,
        severity: "error",
        message,
      });
      setTdarrMatrixAuditStatus("Error", "blocked");
      setTdarrMatrixAuditDetail([message]);
    } finally {
      setTdarrMatrixAuditBusy(false);
    }
  }

  async function requestTdarrMatrixAudit(action) {
    const normalized = String(action || "").trim();
    if (rejectTdarrMatrixAuditWhileBusy(normalized)) return;
    if (!normalized) {
      const result = {
        command: "diagnostics.tdarr_matrix_audit",
        ok: false,
        severity: "error",
        message: "No Tdarr Matrix audit action was selected.",
      };
      appendCommandResult(result);
      setTdarrMatrixAuditStatus("Error", "blocked");
      setTdarrMatrixAuditDetail([result.message]);
      renderTdarrMatrixAuditFindings(result);
      return;
    }
    const gate = tdarrMatrixActionGate(normalized);
    if (gate.disabled) {
      const result = {
        command: "diagnostics.tdarr_matrix_audit",
        ok: false,
        severity: "warning",
        message: `${tdarrMatrixAuditActionLabel(normalized)} is gated: ${gate.reason}`,
      };
      appendCommandResult(result);
      setTdarrMatrixAuditStatus("Gated", gate.state || "warning");
      setTdarrMatrixAuditDetail([
        result.message,
        "Diagnostics keeps advanced proof and cleanup actions gated so the panel remains evidence-oriented.",
      ]);
      updateTdarrMatrixActionGates();
      return;
    }
    if (normalized === "smoke-pack" || normalized === "proof-pack") {
      tdarrMatrixConsoleState.activePack = normalized;
      renderTdarrMatrixProofPackRows();
    }
    const payload = { action: normalized };
    if (normalized === "cleanup-delete") {
      if (!tdarrMatrixDeleteConfirmReady()) {
        setTdarrMatrixAuditStatus("Gated", "blocked");
        setTdarrMatrixAuditDetail(["Type DELETE VERIFIED MATRIX before delete can be armed."]);
        updateTdarrMatrixActionGates();
        return;
      }
      const confirmed = window.confirm(
        "Delete the verified legacy Tdarr full matrix after the backend confirms proof-pack verification and archived evidence?",
      );
      if (!confirmed) {
        setTdarrMatrixAuditStatus("Cancelled", "warning");
        setTdarrMatrixAuditDetail(["Delete Verified Full Matrix was cancelled before any backend request was sent."]);
        return;
      }
      payload.confirm_delete_full_matrix = true;
    }
    setTdarrMatrixAuditBusy(true);
    setTdarrMatrixAuditStatus("Running...", "loading");
    setTdarrMatrixAuditDetail([`${tdarrMatrixAuditActionLabel(normalized)} is running through the backend command route.`]);
    renderTdarrMatrixAuditFindings({ data: { finding_count: 0, findings_preview: [] } });
    try {
      const result = await apiPost("/api/diagnostics/tdarr-matrix-audit", payload);
      appendCommandResult(result);
      const resultOk = Boolean(result?.ok);
      if (resultOk) tdarrMatrixConsoleState.successfulActions[normalized] = true;
      const backgroundStarted = Boolean(result?.data?.background_started);
      setTdarrMatrixAuditStatus(backgroundStarted ? "Running..." : resultOk ? "Complete" : result.severity || "Failed", backgroundStarted ? "loading" : resultOk ? "ready" : "blocked");
      setTdarrMatrixAuditDetail(tdarrMatrixAuditDetailLines(result));
      renderTdarrMatrixAuditFindings(result);
      if (resultOk) {
        await requestTdarrMatrixConsole(result?.data?.run_id || "");
        if (backgroundStarted) scheduleTdarrMatrixBackgroundPoll(result?.data?.run_id || "");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "diagnostics.tdarr_matrix_audit",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      setTdarrMatrixAuditStatus("Error", "blocked");
      setTdarrMatrixAuditDetail([message]);
      renderTdarrMatrixAuditFindings(result);
    } finally {
      setTdarrMatrixAuditBusy(false);
    }
  }

  async function requestDiagnosticsOpen(target, sourceButton = null) {
    if (rejectDiagnosticsOpenWhileBusy()) {
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, "Open already in progress.", "warning");
      }
      return;
    }
    const normalized = String(target || "").trim();
    if (!normalized) {
      const result = {
        command: "diagnostics.open",
        ok: false,
        severity: "error",
        message: "No diagnostics target was selected.",
      };
      appendCommandResult(result);
      setDiagnosticsOpenStatus(result.message, "warning");
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, result.message, "warning");
      }
      return;
    }
    setDiagnosticsOpenBusy(true, sourceButton);
    if (sourceButton && typeof setActionBusy === "function") {
      setActionBusy(sourceButton, true, `Opening ${normalized}...`);
    }
    setDiagnosticsOpenStatus(`Opening ${normalized}...`, "loading");
    try {
      const result = await apiPost("/api/diagnostics/open", { target: normalized });
      appendCommandResult(result);
      setDiagnosticsOpenStatus(result.message || "Open request sent.", result.ok === false ? "blocked" : "ready");
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, result.message || "Open request sent.", result.ok === false ? "blocked" : "ready");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "diagnostics.open",
        ok: false,
        severity: "error",
        message,
      });
      setDiagnosticsOpenStatus(`Open failed: ${message}`, "blocked");
      if (sourceButton && typeof setInlineActionStatus === "function") {
        setInlineActionStatus(sourceButton, `Open failed: ${message}`, "blocked");
      }
    } finally {
      if (sourceButton && typeof setActionBusy === "function") {
        setActionBusy(sourceButton, false);
      }
      setDiagnosticsOpenBusy(false, sourceButton);
    }
  }

  /**
   * Public namespace for the Diagnostics page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineDiagnosticsView = {
    renderDiagnostics,
    renderDiagnosticsRefreshFailures,
    renderDiagnosticsTriage,
    renderDiagnosticsDrilldown,
    diagnosticsTextLines,
    diagnosticsSeverityForLine,
    diagnosticsMalformedStateLines,
    diagnosticsRealMediaBoundaryLines,
    diagnosticsArtifactMatches,
    diagnosticsSourceLines,
    diagnosticsArtifactTargets,
    diagnosticsActionLabel,
    diagnosticsActionGroups,
    diagnosticsActionPlanLines,
    diagnosticsFormatCounts,
    diagnosticsStateIssueRows,
    diagnosticsPageReviewRows,
    diagnosticsCrossPageConflictRows,
    diagnosticsConflictSignalLabel,
    diagnosticsCommandIssueRows,
    diagnosticsInvestigationActions,
    diagnosticsInvestigationStatus,
    diagnosticsSamplePolicyReconciliation,
    diagnosticsFirstResponseRows,
    diagnosticsFirstResponseStatus,
    diagnosticsFirstResponseSummaryLines,
    diagnosticsFirstResponsePostureStatus,
    selectedDiagnosticsFirstResponseRow,
    diagnosticsFirstResponseDetailLines,
    renderDiagnosticsFirstResponse,
    diagnosticsInvestigationTrailLines,
    renderDiagnosticsInvestigationActions,
    renderDiagnosticsInvestigationTrail,
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
    appendDiagnosticsActionGroup,
    activeJobRowKey,
    selectActiveJobRow,
    getSelectedActiveJobRow,
    activeJobDiagnosticsActions,
    diagnosticsActiveJobRealMediaTraceLines,
    renderActiveJobDiagnosticsActions,
    renderActiveJobRows,
    renderActiveJobDetail,
    diagnosticsLineTimestamp,
    diagnosticsLogRows,
    diagnosticsLogRowKey,
    diagnosticsArtifactsForLine,
    diagnosticsLogRowActions,
    diagnosticsLogRowNextStep,
    diagnosticsLogRealMediaTraceLines,
    diagnosticsLogGuidanceLines,
    renderDiagnosticsLogActions,
    filteredDiagnosticsLogRows,
    getLastDiagnosticsLogRows,
    selectDiagnosticsLogRow,
    getSelectedDiagnosticsLogRow,
    renderDiagnosticsLogRows,
    renderDiagnosticsLogDetail,
    selectedDiagnosticsTailTarget,
    selectedDiagnosticsTailMaxBytes,
    setDiagnosticsTailTarget,
    setDiagnosticsTailStatus,
    setDiagnosticsTailBusy,
    renderDiagnosticsTail,
    requestDiagnosticsTail,
    initDiagnosticsViewEvents,
    renderDiagnosticsDrilldownActions,
    requestTdarrMatrixAudit,
    renderTdarrMatrixAuditFindings,
    renderTdarrMatrixBucketCoverage,
    renderTdarrMatrixRunComparison,
    renderTdarrMatrixConsole,
    requestTdarrMatrixConsole,
    requestTdarrMatrixEvidenceOpen,
    requestTdarrMatrixRerun,
    requestTdarrMatrixRunComparison,
    setDiagnosticsOpenStatus,
    setDiagnosticsOpenBusy,
    rejectDiagnosticsOpenWhileBusy,
    requestDiagnosticsOpen,
    isDiagnosticsOpenCommand,
    diagnosticsOpenHistoryLine,
    renderDiagnosticsOpenHistory,
  };
  window.renderDiagnostics = renderDiagnostics;
  window.renderDiagnosticsRefreshFailures = renderDiagnosticsRefreshFailures;
  window.diagnosticsTextLines = diagnosticsTextLines;
  window.diagnosticsSeverityForLine = diagnosticsSeverityForLine;
  window.diagnosticsMalformedStateLines = diagnosticsMalformedStateLines;
  window.diagnosticsSourceLines = diagnosticsSourceLines;
  window.diagnosticsActionGroups = diagnosticsActionGroups;
  window.diagnosticsActionPlanLines = diagnosticsActionPlanLines;
  window.diagnosticsStateIssueRows = diagnosticsStateIssueRows;
  window.diagnosticsPageReviewRows = diagnosticsPageReviewRows;
  window.diagnosticsCrossPageConflictRows = diagnosticsCrossPageConflictRows;
  window.diagnosticsConflictSignalLabel = diagnosticsConflictSignalLabel;
  window.diagnosticsCommandIssueRows = diagnosticsCommandIssueRows;
  window.diagnosticsInvestigationActions = diagnosticsInvestigationActions;
  window.diagnosticsInvestigationStatus = diagnosticsInvestigationStatus;
  window.diagnosticsSamplePolicyReconciliation = diagnosticsSamplePolicyReconciliation;
  window.renderDiagnosticsInvestigationTrail = renderDiagnosticsInvestigationTrail;
  window.diagnosticsListText = diagnosticsListText;
  window.diagnosticsRowLabel = diagnosticsRowLabel;
  window.diagnosticsOwnerDefaultAction = diagnosticsOwnerDefaultAction;
  window.diagnosticsOwnerRowSeverity = diagnosticsOwnerRowSeverity;
  window.diagnosticsOwnerHandoffRowKey = diagnosticsOwnerHandoffRowKey;
  window.diagnosticsCompletedFinalTrustStepForRow = diagnosticsCompletedFinalTrustStepForRow;
  window.diagnosticsCompletedFinalTrustLines = diagnosticsCompletedFinalTrustLines;
  window.diagnosticsCompletedPolicyReconciliationLines = diagnosticsCompletedPolicyReconciliationLines;
  window.diagnosticsOwnerHandoffRows = diagnosticsOwnerHandoffRows;
  window.diagnosticsOwnerHandoffStatus = diagnosticsOwnerHandoffStatus;
  window.diagnosticsOwnerHandoffSummaryLines = diagnosticsOwnerHandoffSummaryLines;
  window.diagnosticsOwnerHandoffActions = diagnosticsOwnerHandoffActions;
  window.diagnosticsOwnerPageId = diagnosticsOwnerPageId;
  window.diagnosticsOwnerSelectFunction = diagnosticsOwnerSelectFunction;
  window.diagnosticsOwnerNavigationLabel = diagnosticsOwnerNavigationLabel;
  window.setDiagnosticsOwnerHandoffNavStatus = setDiagnosticsOwnerHandoffNavStatus;
  window.getSelectedDiagnosticsOwnerHandoffRow = getSelectedDiagnosticsOwnerHandoffRow;
  window.selectDiagnosticsOwnerHandoffRow = selectDiagnosticsOwnerHandoffRow;
  window.renderDiagnosticsOwnerHandoffActions = renderDiagnosticsOwnerHandoffActions;
  window.diagnosticsSampleValidationComparisonLines = diagnosticsSampleValidationComparisonLines;
  window.renderDiagnosticsOwnerHandoffDetail = renderDiagnosticsOwnerHandoffDetail;
  window.renderDiagnosticsOwnerHandoffTable = renderDiagnosticsOwnerHandoffTable;
  window.appendDiagnosticsActionGroup = appendDiagnosticsActionGroup;
  window.activeJobRowKey = activeJobRowKey;
  window.selectActiveJobRow = selectActiveJobRow;
  window.getSelectedActiveJobRow = getSelectedActiveJobRow;
  window.activeJobDiagnosticsActions = activeJobDiagnosticsActions;
  window.diagnosticsActiveJobRealMediaTraceLines = diagnosticsActiveJobRealMediaTraceLines;
  window.renderActiveJobDiagnosticsActions = renderActiveJobDiagnosticsActions;
  window.renderActiveJobRows = renderActiveJobRows;
  window.renderActiveJobDetail = renderActiveJobDetail;
  window.diagnosticsLineTimestamp = diagnosticsLineTimestamp;
  window.diagnosticsLogRows = diagnosticsLogRows;
  window.diagnosticsLogRowKey = diagnosticsLogRowKey;
  window.diagnosticsArtifactsForLine = diagnosticsArtifactsForLine;
  window.diagnosticsLogRowActions = diagnosticsLogRowActions;
  window.renderDiagnosticsLogActions = renderDiagnosticsLogActions;
  window.filteredDiagnosticsLogRows = filteredDiagnosticsLogRows;
  window.getLastDiagnosticsLogRows = getLastDiagnosticsLogRows;
  window.selectDiagnosticsLogRow = selectDiagnosticsLogRow;
  window.getSelectedDiagnosticsLogRow = getSelectedDiagnosticsLogRow;
  window.renderDiagnosticsLogRows = renderDiagnosticsLogRows;
  window.renderDiagnosticsLogDetail = renderDiagnosticsLogDetail;
  window.requestDiagnosticsTail = requestDiagnosticsTail;
  window.requestDiagnosticsOpen = requestDiagnosticsOpen;
})();
