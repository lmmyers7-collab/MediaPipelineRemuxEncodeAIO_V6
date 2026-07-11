(function () {
  function createLaunchPilotReadinessModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      collectPipelineStartRequest = function () { return {}; },
      getCommandHistory = function () { return []; },
      getLastLaunchBackendPreflightPayloads = function () { return []; },
      getLastLaunchBackendPreflightRefreshInfo = function () { return {}; },
      getLastQueuePayload = function () { return {}; },
      getLastQueueRows = function () { return []; },
      getLaunchRealMediaContext = function () { return {}; },
      getSelectedLaunchPilotReadinessKey = function () { return ""; },
      getSelectedQueueRow = function () { return null; },
      launchBackendPreflightOverallStatus = function () { return "Unknown"; },
      launchBackendPreflightRows = function () { return []; },
      launchBackendPreflightSummaryLines = function () { return []; },
      launchPolicyAlignmentQueueIntentEvidence = function () { return {}; },
      launchPolicyBoundaryRows = function () { return []; },
      launchPolicyBoundaryStatus = function () { return "Unknown"; },
      launchRealMediaProofRows = function () { return []; },
      launchRealMediaProofStatus = function () { return "Unknown"; },
      launchRealMediaProofSummaryLines = function () { return []; },
      launchRealMediaSample = function () { return {}; },
      launchSampleExecutionRows = function () { return []; },
      launchSampleExecutionStatus = function () { return "Unknown"; },
      launchSampleExecutionSummaryLines = function () { return []; },
      launchSampleSetCoverageEvidence = function () { return {}; },
      launchSettingsIntentPayload = function () { return {}; },
      launchSettingsIntentRows = function () { return []; },
      launchSettingsIntentStatus = function () { return "Unknown"; },
      launchSettingsTrustStatus = function () { return "Unknown"; },
      launchSettingsWorkspace = function () { return {}; },
      launchStartDecisionPostureFromStatus = function () { return "unknown"; },
      launchStartDecisionRank = function () { return 0; },
      launchStartDecisionRowStatus = function () { return "unknown"; },
      launchStartDecisionWorstPosture = function () { return "unknown"; },
      makeRowSelectable = function () {},
      queueLaunchDecisionRows = function () { return []; },
      queueLaunchDecisionStatus = function () { return "Evidence incomplete"; },
      setLaunchRealMediaContext = function () {},
      setSelectedLaunchPilotReadinessKey = function () {},
      setText = function () {},
      updateTableStatusLegend = function () {},
    } = deps;
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
      "Saved policy evidence should cover route, size, subtitle, audio, source/scratch, and pending-publish behavior for pilot proof.",
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
      `status=${backendStatus}; targets=${backendPayloads.length}; checks=${backendRows.length}; fetch failures=${getLastLaunchBackendPreflightRefreshInfo().fetch_failure_count || 0}.`,
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
    return source.find((row) => row.key === getSelectedLaunchPilotReadinessKey())
      || source.find((row) => row.posture === "blocked")
      || source.find((row) => row.posture === "review")
      || source.find((row) => row.posture === "unknown")
      || source[0]
      || null;
  }

  function selectLaunchPilotReadinessRow(row) {
    setSelectedLaunchPilotReadinessKey(row?.key || "");
    renderLaunchPilotRunReadiness();
  }

  function renderLaunchPilotRunReadiness(context = null) {
    if (context && typeof context === "object") setLaunchRealMediaContext(context);
    const rows = launchPilotRunReadinessRows(getLaunchRealMediaContext());
    if (getSelectedLaunchPilotReadinessKey() && !rows.some((row) => row.key === getSelectedLaunchPilotReadinessKey())) {
      setSelectedLaunchPilotReadinessKey("");
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
    };
  }

  window.__launchPilotReadinessModule = {
    createLaunchPilotReadinessModule,
  };
})();
