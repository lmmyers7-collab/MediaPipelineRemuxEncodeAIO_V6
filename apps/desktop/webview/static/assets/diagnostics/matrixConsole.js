(function () {
  function createDiagnosticsMatrixConsoleModule(deps = {}) {
    const {
      appendCells,
      appendCommandResult,
      apiGet,
      apiPost,
      byId,
      setDiagnosticsPanelStatus,
      setInlineActionStatus,
      setText,    } = deps;
    let tdarrMatrixAuditInFlight = false;
    let tdarrMatrixBackgroundPollTimer = 0;
    const tdarrMatrixConsoleState = {
      latestRunId: "", currentRun: {}, runs: [], findings: [], bucketSummary: [],
      smokePackRows: [], proofPackRows: [], activePack: "proof-pack", selectedFindingKey: "",
      selectedFindingKeys: new Set(), successfulActions: {},
    };

    function getTdarrMatrixConsoleState() { return tdarrMatrixConsoleState; }
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

    return {
      getTdarrMatrixConsoleState,
      setTdarrMatrixAuditStatus,
      setTdarrMatrixAuditDetail,
      setTdarrMatrixAuditBusy,
      stopTdarrMatrixBackgroundPoll,
      scheduleTdarrMatrixBackgroundPoll,
      tdarrMatrixAuditActionLabel,
      tdarrMatrixDeleteConfirmReady,
      tdarrMatrixActionGate,
      updateTdarrMatrixActionGates,
      updateTdarrMatrixRerunButtons,
      renderTdarrMatrixAuditFindings,
      renderTdarrMatrixBucketCoverage,
      renderTdarrMatrixProofPackRows,
      renderTdarrMatrixRunComparison,
      renderTdarrMatrixConsole,
      requestTdarrMatrixConsole,
      requestTdarrMatrixEvidenceOpen,
      requestTdarrMatrixRerun,
      requestTdarrMatrixRunComparison,
      requestTdarrMatrixAudit,    };
  }

  window.__diagnosticsMatrixConsoleModule = {
    createDiagnosticsMatrixConsoleModule,
  };
})();