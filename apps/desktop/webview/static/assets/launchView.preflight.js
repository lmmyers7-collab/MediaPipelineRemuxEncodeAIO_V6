(function () {
  function createLaunchPreflightModule(deps = {}) {
    const {
      apiGet = async function () { throw new Error("apiGet unavailable"); },
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

    function getLaunchRealMediaContext() {
      return state.context && typeof state.context === "object" ? state.context : {};
    }

    function setLaunchRealMediaContext(value) {
      state.context = value && typeof value === "object" ? value : {};
    }

  function launchPilotReadinessContext(context = getLaunchRealMediaContext()) {
    const readinessPayload = launchSettingsIntentPayload();
    return {
      ...(readinessPayload && typeof readinessPayload === "object" ? readinessPayload : {}),
      ...(context && typeof context === "object" ? context : {}),
      settings: launchSettingsWorkspace(),
      schedule: readinessPayload?.schedule || context?.schedule || {},
      snapshot: readinessPayload?.snapshot || context?.snapshot || null,
      closeReadiness: readinessPayload?.closeReadiness || context?.closeReadiness || null,
      failures: context?.failures || readinessPayload?.failures || [],
    };
  }

  function launchPilotPathFromRow(row) {
    return row?.source_path || row?.path || row?.file || row?.input_path || "";
  }

  function launchPilotRowLabel(row) {
    return row?.display_name || row?.relative_path || row?.source_path || row?.path || row?.file || "";
  }

  function launchPilotPendingRows(context = getLaunchRealMediaContext()) {
    const pending = context?.pending && typeof context.pending === "object" ? context.pending : {};
    return Array.isArray(pending.rows) ? pending.rows : [];
  }

  function launchPilotPendingBlockedCount(pending = {}, rows = []) {
    const rowBlocks = rows.filter((row) => {
      const severity = String(row?.diagnostic_severity || row?.operator_severity || "").toLowerCase();
      const status = String(row?.diagnostic_status || row?.state || row?.status || "").toLowerCase();
      const recommendation = String(row?.drain_recommendation || row?.operator_guidance || row?.issue_summary || "").toLowerCase();
      return Boolean(row?.do_not_drain || row?.error || severity === "error" || ["missing", "invalid", "blocked", "do not drain"].some((token) => status.includes(token) || recommendation.includes(token)));
    }).length;
    return Math.max(rowBlocks, Number(pending.issue_count || 0) || 0);
  }

  function launchPilotSettingsStatusLabel() {
    const settingsStatus = launchSettingsTrustStatus(launchSettingsWorkspace());
    const intentRows = launchSettingsIntentRows(collectPipelineStartRequest(), launchSettingsIntentPayload());
    const policyRows = launchPolicyBoundaryRows();
    const settingsIntentStatus = launchSettingsIntentStatus(intentRows);
    const policyStatus = launchPolicyBoundaryStatus(policyRows);
    return { settingsStatus, settingsIntentStatus, policyStatus, intentRows, policyRows };
  }

  function launchPilotRunReadinessRows(context = getLaunchRealMediaContext()) {
    const merged = launchPilotReadinessContext(context);
    const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : (Array.isArray(merged.queue?.rows) ? merged.queue.rows : []);
    const queuePayload = typeof getLastQueuePayload === "function" ? getLastQueuePayload() : (merged.queue || {});
    const selectedQueue = typeof getSelectedQueueRow === "function" ? getSelectedQueueRow() : null;
    const selectedSample = launchRealMediaSample(merged);
    const selectedRow = selectedQueue || selectedSample?.seed?.row || queueRows[0] || null;
    const queueDecisionRows = typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows(queuePayload, queueRows, history) : [];
    const queueStatus = typeof queueLaunchDecisionStatus === "function" ? queueLaunchDecisionStatus(queuePayload, queueRows, history) : (queueRows.length ? "Ready-looking" : "Evidence incomplete");
    const proofRows = launchRealMediaProofRows(merged);
    const proofStatus = launchRealMediaProofStatus(proofRows);
    const sampleRows = launchSampleExecutionRows(merged);
    const sampleStatus = launchSampleExecutionStatus(sampleRows);
    const categoryCoverage = launchSampleSetCoverageEvidence(merged);
    const policyQueueIntent = launchPolicyAlignmentQueueIntentEvidence(merged);
    const backendPayloads = getLastLaunchBackendPreflightPayloads();
    const backendRows = launchBackendPreflightRows(backendPayloads);
    const backendStatus = launchBackendPreflightOverallStatus(backendPayloads);
    const settingsStatus = launchPilotSettingsStatusLabel();
    const pending = merged.pending && typeof merged.pending === "object" ? merged.pending : {};
    const pendingRows = launchPilotPendingRows(merged);
    const pendingBlocked = launchPilotPendingBlockedCount(pending, pendingRows);
    const pendingReady = Number(pending.ready_count || 0) || pendingRows.filter((row) => String(row?.diagnostic_status || row?.status || "").toLowerCase().includes("ready")).length;
    const sourcePath = launchPilotPathFromRow(selectedRow);
    const label = launchPilotRowLabel(selectedRow) || selectedSample?.seed?.display || "(no selected sample)";
    const rows = [];
    const add = (key, checkpoint, posture, evidence, action, detail = []) => rows.push({
      key,
      checkpoint,
      posture,
      evidence,
      action,
      detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
    });

    const queuePosture = queueRows.length
      ? launchStartDecisionPostureFromStatus(queueStatus)
      : "unknown";
    add(
      "selected-queue-sample",
      "Selected Queue sample",
      selectedRow ? queuePosture === "blocked" ? "blocked" : queuePosture === "unknown" ? "review" : queuePosture : "unknown",
      selectedRow
        ? `sample=${label}; source=${sourcePath || "not reported"}; queue rows=${queueRows.length}; queue decision=${queueStatus}.`
        : `no selected Queue row; queue rows=${queueRows.length}; queue decision=${queueStatus}.`,
      selectedRow
        ? "Use this as the intended pilot candidate, then compare route, source, output, and validation evidence after the run."
        : "Select or load a single known Queue row before treating the pilot as operator-proof.",
      [
        `Queue-to-Launch handoff rows: ${queueDecisionRows.length}`,
        `Queue source root: ${queuePayload?.source || "(not reported)"}`,
        `Display filters do not change backend launch scope.`,
        "Boundary: this row cannot select, reorder, launch, or mutate queue state.",
      ],
    );

    add(
      "saved-settings-policy",
      "Saved Settings policy",
      launchStartDecisionWorstPosture([
        launchStartDecisionPostureFromStatus(settingsStatus.settingsStatus),
        launchStartDecisionPostureFromStatus(settingsStatus.settingsIntentStatus),
        launchStartDecisionPostureFromStatus(settingsStatus.policyStatus),
      ]),
      `settings=${settingsStatus.settingsStatus}; intent=${settingsStatus.settingsIntentStatus}; active policy=${settingsStatus.policyStatus}.`,
      "Confirm saved policy covers route, size, subtitle, audio, source/scratch, and pending-publish behavior before the pilot run.",
      [
        `Launch-intent rows: ${settingsStatus.intentRows.length}`,
        `Active policy rows: ${settingsStatus.policyRows.length}`,
        "Staged Settings changes are not launch-active until Save Settings and refresh complete.",
        "Boundary: this row cannot save settings or change media policy.",
      ],
    );

    add(
      "saved-policy-queue-intent",
      "Saved policy vs Queue route",
      policyQueueIntent.pilotPosture,
      policyQueueIntent.evidence,
      policyQueueIntent.nextCheck,
      policyQueueIntent.detail,
    );

    add(
      "backend-preflight",
      "Backend preflight",
      launchStartDecisionPostureFromStatus(backendStatus),
      `status=${backendStatus}; targets=${backendPayloads.length}; checks=${backendRows.length}; fetch failures=${lastLaunchBackendPreflightRefreshInfo.fetch_failure_count || 0}.`,
      backendPayloads.length
        ? "Compare cached preflight with the final Start response; backend start still re-checks at submission time."
        : "Refresh Backend Preflight before trusting the pilot readiness summary.",
      [
        ...launchBackendPreflightSummaryLines(backendPayloads).slice(0, 10),
        "Boundary: this row is a read-only GET snapshot and cannot reserve launch locks.",
      ],
    );

    add(
      "pilot-category-coverage",
      "Pilot category coverage",
      categoryCoverage.posture === "match" ? "ready" : categoryCoverage.posture === "blocked" ? "blocked" : categoryCoverage.posture === "unknown" ? "unknown" : "review",
      categoryCoverage.evidence,
      categoryCoverage.nextCheck,
      categoryCoverage.detail,
    );

    add(
      "real-media-proof-plan",
      "Real-media proof plan",
      launchStartDecisionPostureFromStatus(proofStatus),
      `proof status=${proofStatus}; proof rows=${proofRows.length}; sample=${selectedSample?.seed?.display || label}.`,
      "Before pilot: understand unproven rows. After pilot: use Completed, Pending Publish, Diagnostics, playback, and Sample Validation to close them.",
      launchRealMediaProofSummaryLines(merged, proofRows),
    );

    add(
      "sample-execution-plan",
      "Sample execution checklist",
      launchStartDecisionPostureFromStatus(sampleStatus),
      `status=${sampleStatus}; rows=${sampleRows.length}; required=${sampleRows.filter((row) => row.required).length}.`,
      sampleStatus === "Checklist visible"
        ? "Use the before-launch rows now; complete post-run rows after a real backend run."
        : "Load Sample Validation pilot-plan evidence before a real-media pilot.",
      launchSampleExecutionSummaryLines(merged, sampleRows),
    );

    add(
      "pending-publish-posture",
      "Pending Publish posture",
      pendingBlocked ? "review" : pendingRows.length ? "review" : "ready",
      `pending rows=${pendingRows.length}; ready=${pendingReady}; issues=${pendingBlocked}; status=${pending.operator_status || pending.diagnostic_status || "not loaded"}.`,
      pendingBlocked
        ? "Resolve do-not-drain/missing/invalid parked-output evidence before broad launch or drain testing."
        : pendingRows.length
          ? "Expect parked outputs if deferred publish is enabled; verify Pending Publish and durable drain proof after the pilot."
          : "No pending-publish backlog is visible in the loaded payload; verify again after the pilot run.",
      [
        `Pending publish source: ${pending.source || pending.path || "(not reported)"}`,
        `Diagnostic statuses: ${pending.diagnostic_status_counts ? JSON.stringify(pending.diagnostic_status_counts) : "none loaded"}`,
        "Boundary: this row cannot drain, publish, delete, retry, or rewrite pending-publish manifests.",
      ],
    );

    add(
      "post-run-proof-plan",
      "Post-run proof plan",
      "review",
      "Finished-output trust requires route, output, sidecar, subtitle/audio, size, diagnostics, pending-publish/final destination, playback, and Sample Validation evidence after the backend run finishes.",
      "Run a small known sample first, then record proof before treating WebView as daily-driver ready.",
      [
        "Queue proves intended route and source only.",
        "Launch proves request/preflight intent only.",
        "Completed proves output, sidecar, route/size, and final output health.",
        "Pending Publish proves parked/final destination and drain posture when deferred publish is enabled.",
        "Diagnostics proves FFmpeg/PowerShell runtime evidence, stderr, logs, and active-job cleanup.",
        "Sample Validation records should be appended only after current backend proof exists.",
      ],
    );

    add(
      "mutation-boundary",
      "Mutation boundary",
      "ready",
      "This checklist is read-only and never starts work, changes launch scope, saves settings, drains, publishes, renames, deletes, or touches source/output/scratch media.",
      "Use backend-owned Start controls only after this read-only evidence and the backend Start response agree.",
      [
        "Frontend rows are operator trust aids, not launch authorization.",
        "Runtime state can change between render and button press; backend routes remain final authority.",
      ],
    );

    return rows.sort((left, right) => launchStartDecisionRank(left.posture) - launchStartDecisionRank(right.posture));
  }

  function launchPilotRunReadinessStatus(rows = launchPilotRunReadinessRows()) {
    if (!rows.length) return "Not evaluated";
    if (rows.some((row) => row.posture === "blocked")) return "Pilot blocked";
    if (rows.some((row) => row.posture === "review")) return "Pilot review";
    if (rows.some((row) => row.posture === "unknown")) return "Pilot evidence incomplete";
    return "Pilot ready-looking";
  }

  function launchPilotRunReadinessSummaryLines(rows = launchPilotRunReadinessRows()) {
    const counts = rows.reduce((acc, row) => {
      const key = row.posture || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const nonReady = rows.filter((row) => row.posture !== "ready");
    const lines = [
      "Launch pilot run readiness:",
      "Purpose: give the operator one compact read-only checklist for a real-media pilot using Queue, Settings, Sample Validation, Pending Publish, Diagnostics, and backend preflight evidence.",
      `Rows: ${rows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; blocked=${counts.blocked || 0}; unknown=${counts.unknown || 0}.`,
      "Decision rule: a pilot start is sensible only when selected Queue sample, saved Settings policy, backend preflight, pilot category, pending-publish posture, and post-run proof plan are understood.",
    ];
    if (nonReady.length) {
      lines.push("First action: select the highest-priority non-ready row below, then reconcile the owning page before a real-media pilot.");
      nonReady.slice(0, 8).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.posture}; ${row.action}`));
      if (nonReady.length > 8) lines.push(`- ${nonReady.length - 8} more pilot readiness row(s) need review.`);
    } else {
      lines.push("First action: no local pilot-readiness blocker is visible; backend Start and post-run evidence still decide trust.");
    }
    lines.push("Mutation guardrail: this pilot readiness panel is read-only and cannot launch, accept, publish, drain, save settings, rename, rewrite queue state, or touch media files.");
    return lines;
  }

  function launchPilotRunReadinessDetailLines(row) {
    if (!row) {
      return [
        "Launch pilot run readiness:",
        "No pilot readiness checkpoint is selected.",
        "Refresh backend payloads or select a row after Launch evidence loads.",
        "Mutation guardrail: this detail panel is read-only.",
      ];
    }
    const lines = [
      "Launch pilot run readiness:",
      `Checkpoint: ${row.checkpoint || "unknown"}`,
      `Posture: ${row.posture || "unknown"}`,
      "",
      "Evidence:",
      row.evidence || "(none)",
      "",
      "Operator action:",
      row.action || "Review owning pages before acting.",
    ];
    const detail = Array.isArray(row.detail) ? row.detail : [];
    if (detail.length) {
      lines.push("", "Detail:");
      detail.forEach((item) => lines.push(`- ${typeof item === "object" ? JSON.stringify(item) : String(item)}`));
    }
    lines.push("", "Guardrail: backend-owned launch, publish, settings, rename, and filesystem operations remain the only mutation paths.");
    return lines;
  }

  function selectedLaunchPilotReadinessRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === selectedLaunchPilotReadinessKey)
      || source.find((row) => row.posture === "blocked")
      || source.find((row) => row.posture === "review")
      || source.find((row) => row.posture === "unknown")
      || source[0]
      || null;
  }

  function selectLaunchPilotReadinessRow(row) {
    selectedLaunchPilotReadinessKey = row?.key || "";
    renderLaunchPilotRunReadiness();
  }

  function renderLaunchPilotRunReadiness(context = null) {
    if (context && typeof context === "object") setLaunchRealMediaContext(context);
    const rows = launchPilotRunReadinessRows(getLaunchRealMediaContext());
    if (selectedLaunchPilotReadinessKey && !rows.some((row) => row.key === selectedLaunchPilotReadinessKey)) {
      selectedLaunchPilotReadinessKey = "";
    }
    const selected = selectedLaunchPilotReadinessRow(rows);
    const status = launchPilotRunReadinessStatus(rows);
    setText("launch-pilot-readiness-status", status);
    const statusNode = byId("launch-pilot-readiness-status");
    if (statusNode) {
      statusNode.dataset.state = status === "Pilot blocked" ? "blocked" : status === "Pilot ready-looking" ? "ready" : status === "Pilot evidence incomplete" ? "unknown" : "warning";
    }
    setText("launch-pilot-readiness-summary", launchPilotRunReadinessSummaryLines(rows).join("\n"));
    setText("launch-pilot-readiness-detail", launchPilotRunReadinessDetailLines(selected).join("\n"));
    const tbody = byId("launch-pilot-readiness-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No Launch pilot run readiness rows loaded.");
      updateTableStatusLegend("launch-pilot-readiness-legend", tbody, "Launch pilot readiness rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchStartDecisionRowStatus(item.posture);
      appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchPilotReadinessRow(item), {
          selected: item.key === selected?.key,
          label: `Launch pilot readiness ${item.checkpoint} ${item.posture}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-pilot-readiness-legend", tbody, "Launch pilot readiness rows");
  }

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
      { key: "rerun-live", target: "rerun", label: "CSV Rerun Start", request: collectRerunStartRequest({ dry_run: false }) },
      { key: "rerun-preview", target: "rerun", label: "CSV Rerun Preview", request: collectRerunStartRequest({ dry_run: true }) },
      { key: "rerun-plan-only", target: "rerun", label: "CSV Rerun Plan Only", request: collectRerunStartRequest({ plan_only: true }) },
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

  function launchBackendPreflightPipelineBlockers(payloads = []) {
    return launchBackendPreflightRows(payloads).filter((row) => {
      const target = String(row?.target || row?.payload?.target || "").toLowerCase();
      const posture = String(row?.posture || "").toLowerCase();
      return target === "pipeline" && posture === "blocked";
    });
  }

  function renderLaunchBackendPreflightStartupAlert(payloads = []) {
    if (typeof document === "undefined" || typeof document.querySelector !== "function") return;
    const blockers = launchBackendPreflightPipelineBlockers(payloads);
    let node = document.querySelector(".launch-preflight-startup-alert");
    if (!blockers.length) {
      if (node && typeof node.remove === "function") node.remove();
      return;
    }
    const topbar = document.querySelector(".topbar");
    if (!node) {
      if (!topbar || typeof document.createElement !== "function") return;
      node = document.createElement("div");
      node.className = "launch-preflight-startup-alert";
      node.setAttribute("role", "alert");
      node.setAttribute("aria-live", "assertive");
      topbar.insertAdjacentElement("afterend", node);
    }
    node.dataset.state = "blocked";
    const first = blockers[0] || {};
    const title = document.createElement("strong");
    title.textContent = "Pipeline launch blocked by backend preflight";
    const detail = document.createElement("span");
    detail.textContent = `Backend preflight found ${blockers.length} launch-blocking check${blockers.length === 1 ? "" : "s"}. First blocker: ${first.check || "Backend check"} - ${first.evidence || "no evidence text supplied"}.`;
    const hint = document.createElement("span");
    hint.textContent = first.action
      ? `Open Launch > Readiness > Backend Preflight. Backend action: ${first.action}`
      : "Open Launch > Readiness > Backend Preflight before starting the media pipeline.";
    node.replaceChildren(title, detail, hint);
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
    if (stale && payloads.length) {
      lines.push("Form state changed after the last backend preflight. Action: Refresh Backend Preflight before using normal Start or CSV Rerun controls.");
    }
    const reviewRows = rows.filter((row) => row.posture !== "ready");
    if (reviewRows.length) {
      lines.push("First action: select blocked/review checks before pressing backend-owned start buttons.");
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
    renderLaunchBackendPreflightStartupAlert(items);
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

  async function refreshLaunchBackendPreflight() {
    const requestId = ++launchBackendPreflightRequestId;
    setText("launch-backend-preflight-status", "Loading");
    const statusNode = byId("launch-backend-preflight-status");
    if (statusNode) statusNode.dataset.state = "unknown";
    const candidateRequests = launchBackendPreflightCandidateRequests();
    const requests = candidateRequests.filter(launchBackendPreflightRequestIsActive);
    const skippedRequests = candidateRequests.filter((item) => !launchBackendPreflightRequestIsActive(item));
    const results = await Promise.allSettled(
      requests.map((item) => apiGet(launchBackendPreflightQuery(item.target, item.request), { timeoutMs: 15000 }))
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

  function rerunLaunchPreflightLines(request) {
    const csv = String(request.csv_path || "").trim();
    const lines = [
      `CSV path: ${csv || "missing"}`,
      `Stage mode: ${request.stage_mode}`,
      `Original mode: ${request.original_mode}`,
      `Return mode: ${request.return_mode}`,
      `Plan only: ${request.plan_only ? "yes - no manifest or media writes" : "no"}`,
      `Dry run: ${request.dry_run ? "yes - evidence-writing preview" : request.plan_only ? "no - plan-only request" : "no - live rerun start"}`,
    ];
    if (!csv) lines.push("Input warning: CSV path is required before CSV rerun can start.");
    lines.push(request.plan_only
      ? "Safety policy: plan-only stops before writing manifests, temp config, staging files, parked outputs, or source media."
      : request.dry_run
      ? "Safety policy: dry-run preview should produce backend evidence without staging, moving, publishing, or touching media."
      : "Safety policy: live rerun copies to scratch, keeps originals, and parks returned outputs."
    );
    if (request.show_console) lines.push("Console: visible rerun process window requested.");
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
    renderLaunchPreflight("rerun-launch-preflight", rerunLaunchPreflightLines(collectRerunStartRequest({ plan_only: true })));
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
    return String(entry?.command || "").toLowerCase().startsWith("pipeline.control.");
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
      setText("control-history", "No pipeline control command history loaded. Pause, rescan, and stop-after-current results will appear here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("control-history", "No pipeline control commands found in recent command history.");
      return;
    }
    setText("control-history", [
      `Last ${entries.length} pipeline control command${entries.length === 1 ? "" : "s"}:`,
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
      launchBackendPreflightPipelineBlockers,
      renderLaunchBackendPreflightStartupAlert,
      getLastLaunchBackendPreflightPayloads,
      launchBackendPreflightPayloadForTarget,
      getLastLaunchBackendPreflightRefreshInfo,
      launchBackendPreflightIsStale,
      launchBackendPreflightSummaryLines,
      launchBackendPreflightDetailLines,
      renderLaunchBackendPreflight,
      refreshLaunchBackendPreflight,
      pipelineLaunchPreflightLines,
      rerunLaunchPreflightLines,
      renderLaunchPreflight,
      renderAllLaunchPreflights,
      isPipelineControlCommand,
      pipelineControlHistoryLine,
      renderPipelineControlHistory,
    };
  }

  window.__launchViewPreflightModule = { createLaunchPreflightModule };
})();
