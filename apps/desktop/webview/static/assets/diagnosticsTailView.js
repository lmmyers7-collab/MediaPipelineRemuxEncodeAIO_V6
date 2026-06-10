(function () {
  let diagnosticsTailInFlight = false;
  const diagnosticsTailTargetGroups = [
    { label: "Logs", targets: ["last_stderr_log", "last_stdout_log", "cluster_log"] },
    { label: "State and manifests", targets: ["queue_snapshot", "completed_manifest", "active_jobs"] },
    { label: "Failures and audit", targets: ["latest_failure_report", "latest_failure_json", "latest_audit_csv", "latest_priority_csv"] },
    { label: "Validation", targets: ["sample_validation_log"] },
  ];

  const diagnosticsTailTargetDescriptions = {
    last_stderr_log: "Newest stderr evidence from the pipeline boundary.",
    last_stdout_log: "Newest stdout evidence from the pipeline boundary.",
    cluster_log: "Cluster-level worker coordination log.",
    queue_snapshot: "Current queue snapshot artifact.",
    completed_manifest: "Completed output manifest evidence.",
    active_jobs: "Runtime ActiveJobs state.",
    latest_failure_report: "Newest human-readable failure report.",
    latest_failure_json: "Newest structured failure marker.",
    latest_audit_csv: "Newest audit CSV artifact.",
    latest_priority_csv: "Newest priority manifest CSV.",
    sample_validation_log: "Representative validation run log.",
  };

  function selectedDiagnosticsTailTarget() {
    return String(byId("diagnostics-tail-target")?.value || "").trim();
  }

  function selectedDiagnosticsTailMaxBytes() {
    const raw = String(byId("diagnostics-tail-max-bytes")?.value || "65536").trim();
    return /^\d+$/.test(raw) ? raw : "65536";
  }

  function diagnosticsTailChoiceSafeId(value) {
    return String(value || "blank").replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "") || "blank";
  }

  function syncDiagnosticsTailTargetChoices() {
    const select = byId("diagnostics-tail-target");
    const group = byId("diagnostics-tail-target-choice-groups");
    if (!select || !group) return;
    group.querySelectorAll("input[type='radio']").forEach((radio) => {
      const selected = String(radio.value || "") === String(select.value || "");
      radio.checked = selected;
      radio.closest(".enhanced-choice-card")?.classList.toggle("is-selected", selected);
    });
  }

  function diagnosticsTailTargetOptionLabel(select, value) {
    const option = Array.from(select.options || []).find((item) => item.value === value);
    return String(option?.textContent || value).trim();
  }

  function initDiagnosticsTailTargetChoices() {
    const select = byId("diagnostics-tail-target");
    if (!select || byId("diagnostics-tail-target-choice-groups")) {
      syncDiagnosticsTailTargetChoices();
      return;
    }
    const wrapper = select.closest("label");
    const group = document.createElement("fieldset");
    group.id = "diagnostics-tail-target-choice-groups";
    group.className = "enhanced-choice-group diagnostics-tail-target-choice-groups";
    group.dataset.enhancedChoiceFor = "diagnostics-tail-target";

    const legend = document.createElement("legend");
    legend.textContent = "Target Key";
    group.appendChild(legend);

    diagnosticsTailTargetGroups.forEach((targetGroup) => {
      const section = document.createElement("div");
      section.className = "enhanced-choice-section";
      const heading = document.createElement("strong");
      heading.className = "enhanced-choice-section-title";
      heading.textContent = targetGroup.label;
      section.appendChild(heading);

      const grid = document.createElement("div");
      grid.className = "enhanced-choice-grid diagnostics-tail-target-choice-grid";
      targetGroup.targets.forEach((target) => {
        const optionId = `diagnostics-tail-target-choice-${diagnosticsTailChoiceSafeId(target)}`;
        const card = document.createElement("label");
        card.className = "enhanced-choice-card diagnostics-tail-target-choice";
        card.htmlFor = optionId;

        const radio = document.createElement("input");
        radio.type = "radio";
        radio.id = optionId;
        radio.name = "diagnostics-tail-target-choice";
        radio.value = target;
        radio.checked = target === String(select.value || "");
        radio.addEventListener("change", () => {
          if (!radio.checked) return;
          select.value = target;
          select.dispatchEvent(new Event("input", { bubbles: true }));
          select.dispatchEvent(new Event("change", { bubbles: true }));
          syncDiagnosticsTailTargetChoices();
        });

        const title = document.createElement("span");
        title.className = "enhanced-choice-card-title";
        title.textContent = diagnosticsTailTargetOptionLabel(select, target);
        const detail = document.createElement("span");
        detail.className = "enhanced-choice-card-detail";
        detail.textContent = diagnosticsTailTargetDescriptions[target] || "Backend allowlisted diagnostics tail target.";
        card.append(radio, title, detail);
        grid.appendChild(card);
      });
      section.appendChild(grid);
      group.appendChild(section);
    });

    select.classList.add("enhanced-choice-source");
    select.addEventListener("input", syncDiagnosticsTailTargetChoices);
    select.addEventListener("change", syncDiagnosticsTailTargetChoices);
    if (wrapper) {
      wrapper.classList.add("enhanced-choice-source-label");
      wrapper.insertAdjacentElement("afterend", group);
    } else {
      select.insertAdjacentElement("afterend", group);
    }
    syncDiagnosticsTailTargetChoices();
  }

  function setDiagnosticsTailStatus(message) {
    setText("diagnostics-tail-status", message);
  }

  function setDiagnosticsTailBusy(isBusy) {
    diagnosticsTailInFlight = Boolean(isBusy);
    const button = byId("diagnostics-tail-refresh-button");
    if (button) button.disabled = diagnosticsTailInFlight;
  }

  function diagnosticsTailLines(value) {
    return Array.isArray(value) ? value.map((item) => String(item || "")).filter(Boolean) : [];
  }

  function diagnosticsTailOperatorStatusState(status) {
    const state = typeof normalizeBackendStatusState === "function" ? normalizeBackendStatusState(status) : "";
    if (state) return state;
    const normalized = String(status || "").trim().toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "review") return "warning";
    if (normalized === "active") return "running";
    if (["ready", "empty", "unknown"].includes(normalized)) return normalized;
    return "unknown";
  }

  function diagnosticsTailLineHasNegatedError(line) {
    const text = String(line || "").toLowerCase();
    return /\b(?:no|without)\b(?:\s+[\w-]+){0,4}\s+errors?\b/.test(text)
      || /\b0\s+errors?\b/.test(text)
      || /\berrors?\s*[:=]\s*0\b/.test(text)
      || /\berror[_ -]?count\s*[:=]\s*0\b/.test(text);
  }

  function diagnosticsTailLineHasNegatedFailure(line) {
    const text = String(line || "").toLowerCase();
    return /\b(?:no|without)\b(?:\s+[\w-]+){0,4}\s+fail(?:ed|ures?|ure)?\b/.test(text)
      || /\b0\s+fail(?:ed|ures?|ure)?\b/.test(text)
      || /\bfail(?:ed|ures?|ure)?\s*[:=]\s*0\b/.test(text);
  }

  function diagnosticsTailLineContainsTerm(line, term) {
    const text = String(line || "").toLowerCase();
    const needle = String(term || "").toLowerCase();
    if (!needle) return false;
    if (needle === "error" && diagnosticsTailLineHasNegatedError(text)) return false;
    if ((needle === "failed" || needle === "failure") && diagnosticsTailLineHasNegatedFailure(text)) return false;
    return text.includes(needle);
  }

  function diagnosticsTailEvidence(payload) {
    const tail = payload && typeof payload === "object" ? payload : {};
    const evidence = tail.evidence && typeof tail.evidence === "object" ? tail.evidence : {};
    const lines = String(tail.text || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const hasEvidence = Object.keys(evidence).length > 0;
    if (hasEvidence) {
      const backendEvidence = Object.assign({ evidence_authority: "backend" }, evidence);
      backendEvidence.operator_status_state = evidence.operator_status_state || diagnosticsTailOperatorStatusState(evidence.operator_status);
      return backendEvidence;
    }
    const countMatching = (terms) => lines.filter((line) => terms.some((term) => diagnosticsTailLineContainsTerm(line, term))).length;
    const errors = diagnosticsTailLines(tail.errors);
    const warnings = diagnosticsTailLines(tail.warnings);
    const errorCount = errors.length + countMatching(["error", "failed", "failure", "exception", "traceback", "denied", "blocked", "corrupt", "malformed", "invalid", "unreadable", "locked", "fatal"]);
    const warningCount = warnings.length + countMatching(["warn", "warning", "stale", "orphan", "missing", "retry", "timeout", "partial", "unknown", "skipped"]);
    const activeCount = countMatching(["active", "running", "processing", "launching", "publishing", "ffmpeg", "ffprobe", "powershell"]);
    let operatorStatus = "unavailable";
    if (errorCount) operatorStatus = "blocked";
    else if (warningCount || tail.truncated) operatorStatus = "review";
    else if (activeCount) operatorStatus = "active";
    else if (tail.ok && tail.exists && tail.is_file && lines.length) operatorStatus = "ready";
    else if (tail.ok && tail.exists && tail.is_file) operatorStatus = "empty";
    return {
      evidence_authority: "frontend_advisory",
      operator_status: operatorStatus,
      operator_status_state: diagnosticsTailOperatorStatusState(operatorStatus),
      line_count: lines.length,
      error_count: errorCount,
      warning_count: warningCount,
      active_count: activeCount,
      state_count: countMatching(["activejobs", "queue", "completed", "pending", "manifest", "sidecar", "progress", "pid"]),
      truncated: Boolean(tail.truncated),
      issue_lines: [],
      warning_lines: [],
      active_lines: [],
      state_lines: [],
      safe_next_action: "Advisory only: compare this backend tail payload with Diagnostics State Artifact Summary and the owning page before taking action.",
      guardrail: "Diagnostics tail evidence is read-only; advisory WebView text scans cannot authorize launch, drain, rename, settings save, lifecycle commands, or file changes. Tail reads still use backend allowlisted targets only.",
    };
  }

  function diagnosticsTailEvidenceLines(payload) {
    const tail = payload && typeof payload === "object" ? payload : {};
    const evidence = diagnosticsTailEvidence(tail);
    const issueLines = diagnosticsTailLines(evidence.issue_lines);
    const warningLines = diagnosticsTailLines(evidence.warning_lines);
    const activeLines = diagnosticsTailLines(evidence.active_lines);
    const stateLines = diagnosticsTailLines(evidence.state_lines);
    const authority = String(evidence.evidence_authority || "backend").toLowerCase();
    const isFrontendAdvisory = authority === "frontend_advisory";
    const lines = [
      `${isFrontendAdvisory ? "Tail posture (advisory text scan)" : "Tail posture (backend)"}: ${evidence.operator_status || "unknown"}`,
      `Evidence authority: ${isFrontendAdvisory ? "frontend advisory only" : "backend"}`,
      [
        `lines=${evidence.line_count ?? 0}`,
        `errors=${evidence.error_count ?? 0}`,
        `warnings=${evidence.warning_count ?? 0}`,
        `active/process clues=${evidence.active_count ?? 0}`,
        `state-artifact clues=${evidence.state_count ?? 0}`,
        `truncated=${evidence.truncated ? "yes" : "no"}`,
      ].join("; "),
      `Safe next action: ${evidence.safe_next_action || "Compare this tail with the owning page before changing workflow state."}`,
      evidence.guardrail || "Diagnostics tail evidence is read-only and comes from backend allowlisted targets only.",
    ];
    if (issueLines.length) lines.push("", "Latest issue lines:", ...issueLines.map((line) => `- ${line}`));
    if (warningLines.length) lines.push("", "Latest warning lines:", ...warningLines.map((line) => `- ${line}`));
    if (activeLines.length) lines.push("", "Latest active/process clues:", ...activeLines.map((line) => `- ${line}`));
    if (stateLines.length) lines.push("", "Latest state-artifact clues:", ...stateLines.map((line) => `- ${line}`));
    if (!issueLines.length && !warningLines.length && !activeLines.length && !stateLines.length) {
      lines.push("", "No issue, warning, active-process, or state-artifact lines were highlighted in the returned window.");
    }
    return lines;
  }

  function renderDiagnosticsTail(payload) {
    const tail = payload && typeof payload === "object" ? payload : {};
    const warnings = diagnosticsTailLines(tail.warnings);
    const errors = diagnosticsTailLines(tail.errors);
    const status = tail.ok
      ? tail.truncated
        ? "Loaded truncated"
        : "Loaded"
      : errors.length
        ? "Error"
        : warnings.length
          ? "Unavailable"
          : "Not loaded";
    setDiagnosticsTailStatus(status);
    const lines = [
      `Target: ${tail.target || selectedDiagnosticsTailTarget() || ""}`,
      `Label: ${tail.label || ""}`,
      `Path: ${tail.path || ""}`,
      `Exists: ${tail.exists ? "yes" : "no"}`,
      `File: ${tail.is_file ? "yes" : "no"}`,
      `Size: ${tail.size_bytes ?? 0} byte(s)`,
      `Read limit: ${tail.max_bytes ?? selectedDiagnosticsTailMaxBytes()} byte(s)`,
      `Truncated: ${tail.truncated ? "yes" : "no"}`,
      "Backend diagnostics tail uses allowlisted targets only. The frontend sends a target key, never a filesystem path.",
    ];
    if (warnings.length) lines.push("", "Warnings:", ...warnings.map((item) => `- ${item}`));
    if (errors.length) lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
    setText("diagnostics-tail-detail", lines.join("\n"));
    setText("diagnostics-tail-evidence", diagnosticsTailEvidenceLines(tail).join("\n"));
    setText("diagnostics-tail-text", String(tail.text || "") || "No text was returned for this target.");
  }

  function setDiagnosticsTailTarget(target) {
    const normalized = String(target || "").trim();
    const select = byId("diagnostics-tail-target");
    if (!select || !normalized) return;
    const option = Array.from(select.options || []).find((item) => item.value === normalized);
    if (option) {
      select.value = normalized;
      syncDiagnosticsTailTargetChoices();
    }
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initDiagnosticsTailTargetChoices);
    } else {
      initDiagnosticsTailTargetChoices();
    }
  }

  async function requestDiagnosticsTail(target = "") {
    if (diagnosticsTailInFlight) {
      setDiagnosticsTailStatus("Read already in progress");
      return;
    }
    if (target) setDiagnosticsTailTarget(target);
    const normalized = selectedDiagnosticsTailTarget();
    if (!normalized) {
      setDiagnosticsTailStatus("No target");
      setText("diagnostics-tail-detail", "No diagnostics tail target was selected.");
      setText("diagnostics-tail-evidence", "No diagnostics tail target was selected.");
      return;
    }
    setDiagnosticsTailBusy(true);
    setDiagnosticsTailStatus("Reading...");
    try {
      const maxBytes = selectedDiagnosticsTailMaxBytes();
      const payload = await apiGet(`/api/diagnostics/tail?target=${encodeURIComponent(normalized)}&max_bytes=${encodeURIComponent(maxBytes)}`, { timeoutMs: 15000 });
      renderDiagnosticsTail(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setDiagnosticsTailStatus("Read failed");
      setText("diagnostics-tail-detail", `Diagnostics tail read failed: ${message}`);
      setText("diagnostics-tail-evidence", "Diagnostics tail request failed before backend evidence could be read. Check Local API status and Diagnostics State Artifact Summary.");
      setText("diagnostics-tail-text", "No text was returned.");
    } finally {
      setDiagnosticsTailBusy(false);
    }
  }

  /**
   * Public namespace for the diagnostics tail module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineDiagnosticsTailView = {
    selectedDiagnosticsTailTarget,
    selectedDiagnosticsTailMaxBytes,
    setDiagnosticsTailTarget,
    setDiagnosticsTailStatus,
    setDiagnosticsTailBusy,
    initDiagnosticsTailTargetChoices,
    syncDiagnosticsTailTargetChoices,
    renderDiagnosticsTail,
    requestDiagnosticsTail,
    diagnosticsTailOperatorStatusState,
    diagnosticsTailEvidence,
    diagnosticsTailEvidenceLines,
  };
  window.selectedDiagnosticsTailTarget = selectedDiagnosticsTailTarget;
  window.selectedDiagnosticsTailMaxBytes = selectedDiagnosticsTailMaxBytes;
  window.setDiagnosticsTailTarget = setDiagnosticsTailTarget;
  window.setDiagnosticsTailStatus = setDiagnosticsTailStatus;
  window.setDiagnosticsTailBusy = setDiagnosticsTailBusy;
  window.renderDiagnosticsTail = renderDiagnosticsTail;
  window.requestDiagnosticsTail = requestDiagnosticsTail;
})();
