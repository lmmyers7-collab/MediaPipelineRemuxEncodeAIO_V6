(function () {
  const launchPilotReadinessModule = window.__launchPilotReadinessModule || {};
  delete window.__launchPilotReadinessModule;
  if (typeof launchPilotReadinessModule.createLaunchPilotReadinessModule !== "function") {
    throw new Error("launch/preflight/pilotReadiness.js must load before launchView.preflight.js");
  }

  function createLaunchPreflightModule(deps = {}) {
    const {
      apiGet = async function () { throw new Error("apiGet unavailable"); },
      apiPost = async function () { throw new Error("apiPost unavailable"); },
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      collectPipelineStartRequest = function () { return {}; },
      collectRerunStartRequest = function () { return {}; },
      commandHistoryCompactEvidenceLine = null,
      getCommandHistory = function () { return []; },
      getLastQueuePayload = function () { return null; },
      getLastQueueRows = function () { return []; },
      getLastSnapshot: _getLastSnapshot = function () { return null; },
      getSelectedQueueRow = function () { return null; },
      launchPolicyAlignmentQueueIntentEvidence = function () { return {}; },
      launchPolicyBoundaryRows = function () { return []; },
      launchPolicyBoundaryStatus = function () { return "Unknown"; },
      launchRealMediaProofRows = function () { return []; },
      launchRealMediaProofStatus = function () { return "Unknown"; },
      launchRealMediaProofSummaryLines = function () { return []; },
      launchRealMediaReadinessLines = function () { return []; },
      launchRealMediaSample = function () { return {}; },
      launchSampleExecutionRows = function () { return []; },
      launchSampleExecutionStatus = function () { return "Unknown"; },
      launchSampleExecutionSummaryLines = function () { return []; },
      launchSampleSetCoverageEvidence = function () { return {}; },
      launchSettingsDecisionLines: _launchSettingsDecisionLines = function () { return []; },
      launchSettingsIntentPayload = function () { return {}; },
      launchSettingsIntentRows = function () { return []; },
      launchSettingsIntentStatus = function () { return "Unknown"; },
      launchSettingsRiskLines = function () { return []; },
      launchSettingsTrustStatus = function () { return "Unknown"; },
      launchSettingsWorkspace = function () { return {}; },
      launchPreflightRequestMatches = function () { return false; },
      launchStartDecisionPostureFromStatus = function () { return "unknown"; },
      launchStartDecisionRank = function () { return 0; },
      launchStartDecisionRowStatus = function () { return "unknown"; },
      launchStartDecisionWorstPosture = function () { return "unknown"; },
      launchUnsavedSettingsPatchLines: _launchUnsavedSettingsPatchLines = function () { return []; },
      makeRowSelectable = function () {},
      pipelineModeLabel = function (mode) { return mode || "Pipeline"; },
      queueLaunchDecisionRows = function () { return []; },
      queueLaunchDecisionStatus = function () { return "Evidence incomplete"; },
      renderLaunchPolicyBoundary = function () {},
      renderLaunchRealMediaProofHandoff = function () {},
      renderLaunchScopeReconciliation = function () {},
      renderLaunchSettingsIntentChecklist = function () {},
      renderLaunchSettingsRiskHandoff = function () {},
      renderLaunchStartDecisionSummary = function () {},
      renderLaunchTimingTrust = null,
      renderQueueLaunchDecisionChecklist = null,
      renderScheduleTimingTrust = null,
      setText = function () {},
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;

    let selectedLaunchPilotReadinessKey = "";
    let selectedLaunchBackendPreflightKey = "";
    let launchBackendPreflightRequestId = 0;
    let lastLaunchBackendPreflightPayloads = [];
    let lastLaunchBackendPreflightRefreshInfo = {
      loaded_at: "",
      request_count: 0,
      payload_count: 0,
      fetch_failure_count: 0,
    };
    const rerunPreflightLabels = {
      execution: {
        one_at_a_time: "One at a time",
        windowed: "Windowed",
        batch_stage_all: "Batch stage all",
      },
      destination: {
        auto_replace_clean_else_pending_review: "Auto replace clean, else Pending Publish",
        review_workspace: "Review workspace",
        pending_publish: "Pending publish",
        publish_non_overlap: "Publish with non-overlap name",
        publish_replace_final: "Publish and replace final output",
      },
      collision: {
        suffix: "Suffix when needed",
        fail: "Block on overlap",
        replace_final: "Replace final output",
      },
    };

    function rerunPreflightLabel(kind, value, fallback) {
      const key = String(value || fallback || "");
      return rerunPreflightLabels[kind]?.[key] || key || "Unknown";
    }

    function rerunFinalReplacementSelected(request) {
      return request?.destination_mode === "auto_replace_clean_else_pending_review" || request?.destination_mode === "publish_replace_final" || request?.collision_policy === "replace_final";
    }

    function rerunOutputPairingLine(request) {
      if (!rerunFinalReplacementSelected(request)) return "";
      return request && request.confirm_source_overwrite
        ? "Pairing note: final-output replacement may use the CSV source path as the destination when source-path overwrite is explicitly confirmed."
        : "Pairing note: final-output replacement keeps source files untouched unless source-path overwrite is explicitly confirmed.";
    }

    function getLaunchRealMediaContext() {
      return state.context && typeof state.context === "object" ? state.context : {};
    }

    function setLaunchRealMediaContext(value) {
      state.context = value && typeof value === "object" ? value : {};
    }

    const {
      launchPilotReadinessContext,
      launchPilotPathFromRow,
      launchPilotRowLabel,
      launchPilotPendingRows,
      launchPilotPendingBlockedCount,
      launchPilotSettingsStatusLabel,
      launchPilotRunReadinessRows,
      launchPilotRunReadinessStatus,
      launchPilotRunReadinessSummaryLines,
      launchPilotRunReadinessDetailLines,
      renderLaunchPilotRunReadiness,
    } = launchPilotReadinessModule.createLaunchPilotReadinessModule({
      appendCells,
      byId,
      clearRows,
      collectPipelineStartRequest,
      getCommandHistory,
      getLastLaunchBackendPreflightPayloads,
      getLastLaunchBackendPreflightRefreshInfo,
      getLastQueuePayload,
      getLastQueueRows,
      getLaunchRealMediaContext,
      getSelectedLaunchPilotReadinessKey: () => selectedLaunchPilotReadinessKey,
      getSelectedQueueRow,
      launchBackendPreflightOverallStatus,
      launchBackendPreflightRows,
      launchBackendPreflightSummaryLines,
      launchPolicyAlignmentQueueIntentEvidence,
      launchPolicyBoundaryRows,
      launchPolicyBoundaryStatus,
      launchRealMediaProofRows,
      launchRealMediaProofStatus,
      launchRealMediaProofSummaryLines,
      launchRealMediaSample,
      launchSampleExecutionRows,
      launchSampleExecutionStatus,
      launchSampleExecutionSummaryLines,
      launchSampleSetCoverageEvidence,
      launchSettingsIntentPayload,
      launchSettingsIntentRows,
      launchSettingsIntentStatus,
      launchSettingsTrustStatus,
      launchSettingsWorkspace,
      launchStartDecisionPostureFromStatus,
      launchStartDecisionRank,
      launchStartDecisionRowStatus,
      launchStartDecisionWorstPosture,
      makeRowSelectable,
      queueLaunchDecisionRows,
      queueLaunchDecisionStatus,
      setLaunchRealMediaContext,
      setSelectedLaunchPilotReadinessKey: (value) => { selectedLaunchPilotReadinessKey = value || ""; },
      setText,
      updateTableStatusLegend,
    });

  function launchBackendPreflightTargetLabel(target) {
    const normalized = String(target || "").toLowerCase();
    if (normalized === "pipeline") return "Pipeline";
    if (normalized === "rerun" || normalized === "csv") return "CSV Rerun";
    return target || "Launch";
  }

  function launchBackendPreflightRequestSignature(target, request = {}) {
    const normalizedTarget = String(target || "").toLowerCase();
    const normalizedRequest = {};
    Object.keys(request || {}).sort().forEach((key) => {
      const value = request[key];
      if (value === undefined || value === null) return;
      normalizedRequest[key] = String(value);
    });
    return JSON.stringify({ target: normalizedTarget, request: normalizedRequest });
  }

  function launchBackendPreflightRequestSetSignature(requests = launchBackendPreflightRequests()) {
    return (Array.isArray(requests) ? requests : [])
      .map((item) => launchBackendPreflightRequestSignature(item.target, item.request || {}))
      .join("|");
  }

  function launchBackendPreflightRequestActivity(item) {
    const target = String(item?.target || "").toLowerCase();
    if (target === "rerun" || target === "csv") {
      const csvPath = String(item?.request?.csv_path || "").trim();
      return {
        active: Boolean(csvPath),
        reason: csvPath ? "CSV path staged." : "CSV path is not staged.",
      };
    }
    return {
      active: true,
      reason: "Target is active for the current Launch readiness scope.",
    };
  }

  function launchBackendPreflightRequestIsActive(item) {
    return Boolean(launchBackendPreflightRequestActivity(item).active);
  }

  function launchBackendPreflightCandidateRequests() {
    return [
      { key: "pipeline", target: "pipeline", label: "Pipeline", request: collectPipelineStartRequest() },
    ].map((item) => {
      const activity = launchBackendPreflightRequestActivity(item);
      return {
        ...item,
        active: activity.active,
        inactive_reason: activity.active ? "" : activity.reason,
        scope_reason: activity.reason,
      };
    });
  }

  function launchBackendPreflightIncludedPayloads(payloads = []) {
    return (Array.isArray(payloads) ? payloads : []).filter((payload) => (
      payload?._frontend_preflight_active !== false
      && payload?._frontend_preflight_included !== false
    ));
  }

  function launchBackendPreflightScopeLabel(payloads = []) {
    const included = launchBackendPreflightIncludedPayloads(payloads);
    if (included.length === 1) {
      const label = included[0]?._frontend_target_label || launchBackendPreflightTargetLabel(included[0]?.target);
      return `${label} backend preflight`;
    }
    return "Launch backend preflight by active target";
  }

  function launchBackendPreflightQuery(target, request = {}) {
    const params = new URLSearchParams();
    params.set("target", target);
    Object.entries(request || {}).forEach(([key, value]) => {
      if (key === "target" || value === undefined || value === null) return;
      params.set(key, String(value));
    });
    return `/api/launch/preflight?${params.toString()}`;
  }

  function launchBackendPreflightStatusRank(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "high review") return 1;
    if (normalized === "review") return 2;
    if (normalized === "unknown") return 3;
    return 4;
  }

  function launchBackendPreflightRowStatus(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "high review" || normalized === "review") return "warning";
    if (normalized === "unknown") return "unknown";
    return "match";
  }

  function launchBackendPreflightOverallStatus(payloads = []) {
    const items = launchBackendPreflightIncludedPayloads(payloads);
    if (!items.length) return "Not loaded";
    const statuses = items.map((item) => String(item?.status || "unknown").toLowerCase());
    if (statuses.includes("blocked")) return "Blocked";
    if (statuses.includes("high review")) return "High review";
    if (statuses.includes("review")) return "Review";
    if (statuses.includes("unknown")) return "Evidence incomplete";
    return "Ready";
  }

  function launchBackendPreflightStatusState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "high review" || normalized === "review") return "warning";
    if (normalized === "stale") return "warning";
    if (normalized === "running" || normalized === "active") return "running";
    if (normalized === "stopped" || normalized === "idle") return "unknown";
    if (normalized === "forced") return "blocked";
    if (normalized === "evidence incomplete" || normalized === "not loaded" || normalized === "loading") return "unknown";
    if (normalized === "ready") return "ready";
    return "unknown";
  }

  function launchBackendPreflightRows(payloads = []) {
    const rows = [];
    launchBackendPreflightIncludedPayloads(payloads).forEach((payload) => {
      const target = payload?.target || "unknown";
      const checks = Array.isArray(payload?.checks) ? payload.checks : [];
      checks.forEach((check) => {
        rows.push({
          key: `${payload?._frontend_preflight_key || target}:${check.key || check.label || rows.length}`,
          target,
          targetLabel: payload?._frontend_target_label || launchBackendPreflightTargetLabel(target),
          checkKey: check.key || "",
          check: check.label || check.key || "Check",
          posture: check.status || "unknown",
          evidence: check.evidence || "",
          action: check.action || "",
          detail: Array.isArray(check.detail) ? check.detail : [],
          recoveryActions: Array.isArray(check.recovery_actions) ? check.recovery_actions : [],
          payload,
        });
      });
    });
    return rows.sort((left, right) => launchBackendPreflightStatusRank(left.posture) - launchBackendPreflightStatusRank(right.posture));
  }

  function launchBackendPreflightList(value) {
    return Array.isArray(value)
      ? value.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
  }

  function launchBackendPreflightEncoderCapabilityDetails(payloads = []) {
    const details = [];
    launchBackendPreflightIncludedPayloads(payloads).forEach((payload) => {
      const checks = Array.isArray(payload?.checks) ? payload.checks : [];
      checks.forEach((check) => {
        if (String(check?.key || "") !== "encoder_capability_report") return;
        (Array.isArray(check.detail) ? check.detail : []).forEach((item) => {
          if (item && typeof item === "object") details.push(item);
        });
      });
    });
    return details;
  }

  function launchBackendPreflightEncoderActivationLines(payloads = []) {
    const details = launchBackendPreflightEncoderCapabilityDetails(payloads);
    if (!details.length) return [];
    const active = new Set();
    const inactive = new Set();
    const unknown = new Set();
    details.forEach((detail) => {
      launchBackendPreflightList(detail.active_encoders).forEach((item) => active.add(item));
      launchBackendPreflightList(detail.available_inactive_encoders).forEach((item) => inactive.add(item));
      launchBackendPreflightList(detail.activation_unknown_encoders).forEach((item) => unknown.add(item));
    });
    const activeList = Array.from(active);
    const inactiveList = Array.from(inactive);
    const unknownList = Array.from(unknown);
    const lines = [
      `Encoder activation evidence: active=${activeList.length}${activeList.length ? ` (${activeList.join(", ")})` : ""}; available inactive=${inactiveList.length}${inactiveList.length ? ` (${inactiveList.join(", ")})` : ""}; activation unknown=${unknownList.length}${unknownList.length ? ` (${unknownList.join(", ")})` : ""}.`,
    ];
    if (inactiveList.length) {
      lines.push(`Inactive available encoders remain review-only until descriptor activation and validation: ${inactiveList.join(", ")}.`);
    }
    if (unknownList.length) {
      lines.push(`Activation-unknown encoders require fresh backend capability evidence: ${unknownList.join(", ")}.`);
    }
    lines.push("Encoder activation authority: backend encoder_capability_report detail; WebView does not enable hardware families or choose FFmpeg flags.");
    return lines;
  }

  function launchBackendPreflightEncoderHardwareRuntimeLines(payloads = []) {
    const details = launchBackendPreflightEncoderCapabilityDetails(payloads);
    if (!details.length) return [];
    const verified = new Set();
    const skipped = new Set();
    const activeUnverified = new Set();
    details.forEach((detail) => {
      launchBackendPreflightList(detail.hardware_runtime_verified_encoders).forEach((item) => verified.add(item));
      launchBackendPreflightList(detail.hardware_runtime_skipped_encoders).forEach((item) => skipped.add(item));
      launchBackendPreflightList(detail.active_hardware_runtime_unverified_encoders).forEach((item) => activeUnverified.add(item));
    });
    const verifiedList = Array.from(verified);
    const skippedList = Array.from(skipped);
    const activeUnverifiedList = Array.from(activeUnverified);
    const lines = [
      `Hardware runtime proof: verified=${verifiedList.length}${verifiedList.length ? ` (${verifiedList.join(", ")})` : ""}; skipped=${skippedList.length}${skippedList.length ? ` (${skippedList.join(", ")})` : ""}; active unverified=${activeUnverifiedList.length}${activeUnverifiedList.length ? ` (${activeUnverifiedList.join(", ")})` : ""}.`,
    ];
    if (activeUnverifiedList.length) {
      lines.push(`Active hardware encoders without runtime proof remain review-only: ${activeUnverifiedList.join(", ")}.`);
    }
    if (skippedList.length) {
      lines.push(`Skipped hardware runtime probes require host-hardware validation before activation: ${skippedList.join(", ")}.`);
    }
    return lines;
  }

  function getLastLaunchBackendPreflightPayloads() {
    return Array.isArray(lastLaunchBackendPreflightPayloads) ? lastLaunchBackendPreflightPayloads.slice() : [];
  }

  function launchBackendPreflightPayloadForTarget(target, payloads = lastLaunchBackendPreflightPayloads) {
    let options = {};
    let source = payloads;
    if (!Array.isArray(payloads) && payloads && typeof payloads === "object") {
      options = payloads;
      source = lastLaunchBackendPreflightPayloads;
    }
    const normalized = String(target || "").toLowerCase();
    const candidates = (Array.isArray(source) ? source : [])
      .filter((payload) => String(payload?.target || "").toLowerCase() === normalized);
    if (options.request && Array.isArray(options.matchKeys) && options.matchKeys.length) {
      return candidates.find((payload) => launchPreflightRequestMatches(payload, options.request, options.matchKeys)) || null;
    }
    return candidates[0] || null;
  }

  function getLastLaunchBackendPreflightRefreshInfo() {
    return { ...lastLaunchBackendPreflightRefreshInfo };
  }

  function launchBackendPreflightIsStale(requests = launchBackendPreflightRequests()) {
    const loadedSignature = String(lastLaunchBackendPreflightRefreshInfo.request_signature || "");
    return Boolean(loadedSignature) && loadedSignature !== launchBackendPreflightRequestSetSignature(requests);
  }

  function launchBackendPreflightSummaryLines(payloads = []) {
    const includedPayloads = launchBackendPreflightIncludedPayloads(payloads);
    const rows = launchBackendPreflightRows(payloads);
    const stale = launchBackendPreflightIsStale();
    const status = stale && includedPayloads.length ? "Stale" : launchBackendPreflightOverallStatus(payloads);
    const counts = rows.reduce((acc, row) => {
      const key = String(row.posture || "unknown");
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const skippedTargets = Array.isArray(lastLaunchBackendPreflightRefreshInfo.skipped_targets)
      ? lastLaunchBackendPreflightRefreshInfo.skipped_targets
      : [];
    const activeLabels = includedPayloads.map((payload) => payload?._frontend_target_label || launchBackendPreflightTargetLabel(payload?.target));
    const lines = [
      `${launchBackendPreflightScopeLabel(payloads)}:`,
      `Status: ${status}`,
      `Active targets: ${activeLabels.length ? activeLabels.join(", ") : "none"}; checks=${rows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; high review=${counts["high review"] || 0}; blocked=${counts.blocked || 0}; unknown=${counts.unknown || 0}.`,
      `Last refresh: ${lastLaunchBackendPreflightRefreshInfo.loaded_at || "not loaded"}; active requests=${lastLaunchBackendPreflightRefreshInfo.request_count || 0}; skipped inactive=${lastLaunchBackendPreflightRefreshInfo.skipped_request_count || 0}; payloads=${lastLaunchBackendPreflightRefreshInfo.payload_count || 0}; fetch failures=${lastLaunchBackendPreflightRefreshInfo.fetch_failure_count || 0}.`,
      "Source: GET /api/launch/preflight. This read route mirrors backend launch guards without journaling commands or mutating runtime state.",
      "Status scope: active targets only; inactive workflows are skipped before fetch and excluded from the overall status.",
    ];
    if (skippedTargets.length) {
      lines.push(`Inactive targets skipped: ${skippedTargets.map((item) => `${item.label}: ${item.reason}`).join("; ")}`);
    }
    launchBackendPreflightEncoderActivationLines(payloads).forEach((line) => lines.push(line));
    launchBackendPreflightEncoderHardwareRuntimeLines(payloads).forEach((line) => lines.push(line));
    if (stale && payloads.length) {
      lines.push("Form state changed after the last backend preflight. Action: refresh Backend Preflight for current evidence; routine Start still submits to backend guards.");
    }
    const reviewRows = rows.filter((row) => row.posture !== "ready");
    if (reviewRows.length) {
      lines.push("First action: select blocked/review checks for backend-authored evidence; blocked checks still disable matching start controls.");
      reviewRows.slice(0, 8).forEach((row) => lines.push(`- ${row.targetLabel} / ${row.check}: ${row.posture}; ${row.action}`));
      if (reviewRows.length > 8) lines.push(`- ${reviewRows.length - 8} more backend preflight check(s) need review.`);
    } else {
      lines.push("First action: no backend-authored preflight blockers are visible; the start route still re-checks everything at submission time.");
    }
    lines.push("Mutation guardrail: this panel cannot launch, reserve locks, clear flags, save settings, drain, rename, repair, delete, publish, or touch media files.");
    return lines;
  }

  function selectedLaunchBackendPreflightRow(rows) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === selectedLaunchBackendPreflightKey) || source.find((row) => row.posture !== "ready") || source[0] || null;
  }

  function launchBackendPreflightDetailLines(row) {
    if (!row) {
      return [
        "Launch backend preflight by active target:",
        "No backend preflight check selected.",
        "Mutation guardrail: this detail panel is read-only.",
      ];
    }
    const lines = [
      `${row.targetLabel} backend preflight:`,
      `Target: ${row.targetLabel}`,
      `Check: ${row.check}`,
      `Posture: ${row.posture}`,
      `Evidence: ${row.evidence}`,
      `Backend action: ${row.action}`,
    ];
    if (row.payload?.start_route) lines.push(`Start route: ${row.payload.start_route}`);
    if (row.payload?.final_authority) lines.push(`Authority: ${row.payload.final_authority}`);
    if (row.detail.length) {
      lines.push("", "Detail:");
      row.detail.forEach((item) => {
        if (item && typeof item === "object") {
          lines.push(JSON.stringify(item, null, 2));
        } else {
          lines.push(`- ${item}`);
        }
      });
    }
    if (row.recoveryActions.length) {
      lines.push("", "Backend-advertised recovery actions:");
      row.recoveryActions.forEach((action) => {
        const label = String(action?.label || action?.kind || "recovery action");
        const route = String(action?.route || "(no route)");
        lines.push(`- ${label}: ${route}`);
      });
    }
    if (row.payload?.request) {
      lines.push("", "Normalized request:", JSON.stringify(row.payload.request, null, 2));
    }
    lines.push("", "Guardrail: backend start routes re-check this state at submission time.");
    return lines;
  }

  function selectLaunchBackendPreflightRow(row, payloads) {
    selectedLaunchBackendPreflightKey = row?.key || "";
    renderLaunchBackendPreflight(payloads);
  }

  function renderLaunchBackendPreflight(payloads = []) {
    const items = Array.isArray(payloads) ? payloads : [];
    lastLaunchBackendPreflightPayloads = items.slice();
    const pipelineBackendPreflight = launchBackendPreflightPayloadForTarget("pipeline", items);
    const launchReadinessView = window.mediaPipelineLaunchReadinessView || {};
    if (typeof launchReadinessView.renderLaunchReadiness === "function") {
      const readinessPayload = typeof launchReadinessView.getLastLaunchReadinessPayload === "function"
        ? launchReadinessView.getLastLaunchReadinessPayload()
        : {};
      launchReadinessView.renderLaunchReadiness({
        ...(readinessPayload && typeof readinessPayload === "object" ? readinessPayload : {}),
        backendPreflight: pipelineBackendPreflight,
        backendReadiness: pipelineBackendPreflight?.operator_readiness || null,
      });
    }
    const rows = launchBackendPreflightRows(items);
    if (selectedLaunchBackendPreflightKey && !rows.some((row) => row.key === selectedLaunchBackendPreflightKey)) {
      selectedLaunchBackendPreflightKey = "";
    }
    const selected = selectedLaunchBackendPreflightRow(rows);
    const stale = launchBackendPreflightIsStale();
    const includedItems = launchBackendPreflightIncludedPayloads(items);
    const status = stale && includedItems.length ? "Stale" : launchBackendPreflightOverallStatus(items);
    setText("launch-backend-preflight-status", status);
    const statusNode = byId("launch-backend-preflight-status");
    if (statusNode) statusNode.dataset.state = launchBackendPreflightStatusState(status);
    setText("launch-backend-preflight-summary", launchBackendPreflightSummaryLines(items).join("\n"));
    setText("launch-backend-preflight-detail", launchBackendPreflightDetailLines(selected).join("\n"));
    const tbody = byId("launch-backend-preflight-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No backend launch preflight rows loaded.");
      updateTableStatusLegend("launch-backend-preflight-legend", tbody, "Backend launch preflight rows");
      renderLaunchStartDecisionSummary();
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchBackendPreflightRowStatus(item.posture);
      appendCells(row, [item.targetLabel, item.check, item.posture, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchBackendPreflightRow(item, items), {
          selected: item.key === selected?.key,
          label: `Backend launch preflight ${item.targetLabel} ${item.check} ${item.posture}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-backend-preflight-legend", tbody, "Backend launch preflight rows");
    renderLaunchStartDecisionSummary();
  }

  function launchBackendPreflightRequests() {
    return launchBackendPreflightCandidateRequests().filter(launchBackendPreflightRequestIsActive);
  }

  async function refreshLaunchBackendPreflight(options = {}) {
    const requestId = ++launchBackendPreflightRequestId;
    const refreshEncoderCapabilityReport = Boolean(options?.refreshEncoderCapabilityReport);
    setText("launch-backend-preflight-status", "Loading");
    const statusNode = byId("launch-backend-preflight-status");
    if (statusNode) statusNode.dataset.state = "unknown";
    const candidateRequests = launchBackendPreflightCandidateRequests();
    const requests = candidateRequests.filter(launchBackendPreflightRequestIsActive);
    const skippedRequests = candidateRequests.filter((item) => !launchBackendPreflightRequestIsActive(item));
    let encoderCapabilityRefresh = null;
    if (refreshEncoderCapabilityReport) {
      encoderCapabilityRefresh = await apiPost("/api/diagnostics/encoder-capabilities/refresh", {}, { timeoutMs: 65000 });
    }
    const results = await Promise.allSettled(
      requests.map((item) => {
        const request = {
          ...(item.request && typeof item.request === "object" ? item.request : {}),
        };
        return apiGet(launchBackendPreflightQuery(item.target, request), { timeoutMs: 15000 });
      })
    );
    if (requestId !== launchBackendPreflightRequestId) return;
    const payloads = [];
    results.forEach((result, index) => {
      const requestItem = requests[index] || {};
      const target = requestItem.target || "unknown";
      if (result.status === "fulfilled") {
        payloads.push({
          ...result.value,
          _frontend_preflight_key: requestItem.key || target,
          _frontend_target_label: requestItem.label || launchBackendPreflightTargetLabel(target),
          _frontend_preflight_active: true,
          _frontend_preflight_included: true,
          _frontend_scope_reason: requestItem.scope_reason || "Active launch target.",
          request: result.value?.request && typeof result.value.request === "object" ? result.value.request : (requestItem.request || {}),
        });
      } else {
        const message = result.reason instanceof Error ? result.reason.message : String(result.reason);
        payloads.push({
          schema_version: "desktop_launch_preflight.v1",
          target,
          _frontend_preflight_key: requestItem.key || target,
          _frontend_target_label: requestItem.label || launchBackendPreflightTargetLabel(target),
          _frontend_preflight_active: true,
          _frontend_preflight_included: true,
          _frontend_scope_reason: requestItem.scope_reason || "Active launch target.",
          start_route: "",
          status: "unknown",
          can_request_start: false,
          final_authority: "Backend start routes remain authoritative.",
          checks: [{
            key: "preflight_fetch",
            label: "Preflight fetch",
            status: "unknown",
            evidence: message,
            action: "Refresh the WebView or inspect Diagnostics if backend preflight cannot load.",
            detail: [message],
          }],
        });
      }
    });
    lastLaunchBackendPreflightRefreshInfo = {
      loaded_at: new Date().toISOString(),
      request_count: requests.length,
      payload_count: payloads.length,
      fetch_failure_count: results.filter((result) => result.status !== "fulfilled").length,
      refresh_encoder_capability_report_requested: refreshEncoderCapabilityReport,
      encoder_capability_refresh_command: encoderCapabilityRefresh,
      request_signature: launchBackendPreflightRequestSetSignature(requests),
      candidate_request_count: candidateRequests.length,
      skipped_request_count: skippedRequests.length,
      skipped_targets: skippedRequests.map((item) => ({
        key: item.key || "",
        target: item.target || "",
        label: item.label || launchBackendPreflightTargetLabel(item.target),
        reason: item.inactive_reason || item.scope_reason || "Inactive target.",
      })),
    };
    renderLaunchBackendPreflight(payloads);
    if (typeof renderQueueLaunchDecisionChecklist === "function") {
      renderQueueLaunchDecisionChecklist();
    }
    renderLaunchScopeReconciliation();
    renderLaunchStartDecisionSummary();
    return payloads;
  }

  async function refreshLaunchBackendPreflightEncoderCapability() {
    return refreshLaunchBackendPreflight({ refreshEncoderCapabilityReport: true });
  }

  function pipelineLaunchPreflightLines(request) {
    const lines = [
      `Mode: ${pipelineModeLabel(request.mode)}`,
      `Sleep seconds: ${request.sleep_seconds}`,
      `Schedule override: ${request.schedule_override || "none"}`,
      `Single file: ${request.single_file || "not requested"}`,
    ];
    if (request.mode === "continuous") {
      lines.push("Operator check: continuous mode keeps launching work until stopped or schedule/window policy blocks it.");
    } else if (request.mode === "once") {
      lines.push("Operator check: run-once processes the current queue window and then exits.");
    } else if (request.mode === "validate") {
      lines.push("Operator check: validate mode should inspect configuration without processing media.");
    } else if (request.mode === "drain_pending_pushes") {
      lines.push("Operator check: publish parked outputs only; media routing/encoding is not expected.");
    }
    if (request.schedule_override === "ignore") {
      lines.push("Schedule warning: ignore runs outside configured schedule windows.");
    } else if (request.schedule_override === "run_once") {
      lines.push("Schedule note: run-once override allows a single launch outside the normal window.");
    }
    if (request.show_console) lines.push("Console: visible process window requested.");
    if (request.show_config) lines.push("Config: backend will print the resolved config for this launch.");
    if (request.single_file) {
      lines.push("Single-file launch: WebView submits the path only; backend-owned pipeline validation, routing, logs, and ActiveJobs remain authoritative.");
    }
    lines.push("", ...launchSettingsRiskLines(request));
    lines.push(...launchRealMediaReadinessLines("pipeline"));
    lines.push("Backend validation and launch locking remain the source of truth.");
    return lines;
  }

  function rerunQueuePreflightLines(request) {
    const csv = String(request.csv_path || "").trim();
    const scope = request.scope && typeof request.scope === "object" ? request.scope : {};
    const issueFilters = Array.isArray(scope.issue_filters) ? scope.issue_filters.join(", ") : (scope.issue_filter || "");
    const bucketFilters = Array.isArray(scope.bucket_filters) ? scope.bucket_filters.join(", ") : (scope.bucket_filter || "");
    const lines = [
      `CSV path: ${csv || "missing"}`,
      `Execution: ${rerunPreflightLabel("execution", request.execution_mode, "one_at_a_time")}; window=${request.window_size || 1}`,
      `Destination handling: ${rerunPreflightLabel("destination", request.destination_mode, "auto_replace_clean_else_pending_review")}; collision=${rerunPreflightLabel("collision", request.collision_policy, "replace_final")}`,
      `Source handling: source overwrite ${request.confirm_source_overwrite ? "confirmed" : "not confirmed"}; confirmed source overwrite uses CSV source_path as the replacement destination.`,
      `Scope: enabled only ${scope.enabled_only !== false ? "yes" : "no"}; skip blocked ${scope.skip_blocked ? "yes" : "no"}; skip warnings ${scope.skip_warning_rows ? "yes" : "no"}; first rows ${scope.first_n || 0}; issue "${issueFilters}"; bucket "${bucketFilters}"`,
    ];
    const pairingLine = rerunOutputPairingLine(request);
    if (pairingLine) lines.push(pairingLine);
    if (!csv) lines.push("Input warning: CSV path is required before CSV rerun can start.");
    if (["auto_replace_clean_else_pending_review", "publish_replace_final"].includes(request.destination_mode) && request.confirm_replace_final !== true) {
      lines.push("Confirmation warning: replacing a final output requires confirm_replace_final=true.");
    }
    lines.push("Safety policy: live rerun stages bounded scratch input, verifies output, applies destination policy, and only overwrites a source path when explicitly confirmed.");
    lines.push("", ...launchSettingsRiskLines(request));
    lines.push(...launchRealMediaReadinessLines("CSV rerun"));
    lines.push("Backend validation and launch locking remain the source of truth.");
    return lines;
  }

  function renderLaunchPreflight(id, lines) {
    setText(id, (lines || []).join("\n"));
  }

  function renderAllLaunchPreflights(options = {}) {
    const pipelineRequest = collectPipelineStartRequest();
    renderLaunchPreflight("pipeline-launch-preflight", pipelineLaunchPreflightLines(pipelineRequest));
    renderLaunchPreflight("rerun-queue-preflight", rerunQueuePreflightLines(collectRerunStartRequest({ dry_run: false })));
    renderLaunchSettingsRiskHandoff(pipelineRequest);
    renderLaunchPolicyBoundary();
    renderLaunchSettingsIntentChecklist(pipelineRequest);
    renderLaunchScopeReconciliation(pipelineRequest);
    renderLaunchRealMediaProofHandoff();
    renderLaunchStartDecisionSummary(pipelineRequest);
    renderLaunchBackendPreflight(lastLaunchBackendPreflightPayloads);
    if (options && options.refreshBackend === true) refreshLaunchBackendPreflight();
    if (typeof renderLaunchTimingTrust === "function") renderLaunchTimingTrust();
    if (typeof renderScheduleTimingTrust === "function") renderScheduleTimingTrust();
  }

  function isPipelineControlCommand(entry) {
    const command = String(entry?.command || "").toLowerCase();
    return command.startsWith("pipeline.control.") || command.startsWith("rerun.control.");
  }

  function pipelineControlHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object" ? raw.request : {};
    const command = String(entry?.command || "");
    const action = data.action || request.action || command.split(".").pop() || "unknown";
    const bits = [`action=${action}`];
    if (data.flag_path) bits.push(`flag=${data.flag_path}`);
    if (data.force_stop_scope?.scope_label) bits.push(`scope=${data.force_stop_scope.scope_label}`);
    if (raw.refresh_hint) bits.push(`refresh=${raw.refresh_hint}`);
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: command || "pipeline.control",
        detail: ` (${bits.join("; ")})`,
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} ${command || "pipeline.control"} [${status}; ${local}] ${entry?.message || ""} (${bits.join("; ")})`.trim();
  }

  function renderPipelineControlHistory(history = []) {
    const entries = Array.isArray(history) ? history.filter(isPipelineControlCommand).slice(0, 5) : [];
    if (!Array.isArray(history) || !history.length) {
      setText("control-history", "No pipeline or CSV rerun control command history loaded. Pause, rescan, and stop-after-current results will appear here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("control-history", "No pipeline or CSV rerun control commands found in recent command history.");
      return;
    }
    setText("control-history", [
      `Last ${entries.length} pipeline/CSV rerun control command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(pipelineControlHistoryLine),
      "Backend control-flag writes and launch locks remain the source of truth.",
    ].join("\n"));
  }

    return {
      launchPilotReadinessContext,
      launchPilotPathFromRow,
      launchPilotRowLabel,
      launchPilotPendingRows,
      launchPilotPendingBlockedCount,
      launchPilotSettingsStatusLabel,
      launchPilotRunReadinessRows,
      launchPilotRunReadinessStatus,
      launchPilotRunReadinessSummaryLines,
      launchPilotRunReadinessDetailLines,
      renderLaunchPilotRunReadiness,
      launchBackendPreflightTargetLabel,
      launchBackendPreflightRequestActivity,
      launchBackendPreflightRequestIsActive,
      launchBackendPreflightCandidateRequests,
      launchBackendPreflightIncludedPayloads,
      launchBackendPreflightScopeLabel,
      launchBackendPreflightQuery,
      launchBackendPreflightStatusRank,
      launchBackendPreflightRowStatus,
      launchBackendPreflightOverallStatus,
      launchBackendPreflightStatusState,
      launchBackendPreflightRows,
      launchBackendPreflightEncoderHardwareRuntimeLines,
      getLastLaunchBackendPreflightPayloads,
      launchBackendPreflightPayloadForTarget,
      getLastLaunchBackendPreflightRefreshInfo,
      launchBackendPreflightIsStale,
      launchBackendPreflightSummaryLines,
      launchBackendPreflightDetailLines,
      renderLaunchBackendPreflight,
      refreshLaunchBackendPreflight,
      refreshLaunchBackendPreflightEncoderCapability,
      pipelineLaunchPreflightLines,
      rerunQueuePreflightLines,
      renderLaunchPreflight,
      renderAllLaunchPreflights,
      isPipelineControlCommand,
      pipelineControlHistoryLine,
      renderPipelineControlHistory,
    };
  }

  window.__launchViewPreflightModule = { createLaunchPreflightModule };
})();
