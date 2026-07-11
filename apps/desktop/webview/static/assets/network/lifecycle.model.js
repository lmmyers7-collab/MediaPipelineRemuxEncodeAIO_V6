// Network lifecycle handoff model and read-only gate-table rendering.
(function () {
  "use strict";

  function createNetworkLifecycleModelModule(deps = {}) {
    const {
      appendCells = () => {},
      byId = () => null,
      clearRows = () => {},
      closeReadinessLine = () => "",
      coordinatorTarget = () => "",
      displayConfigValue = () => "",
      makeRowSelectable = () => {},
      networkCoordinatorBindEndpoint = () => "",
      networkLifecycleContractSummary = () => "",
      networkLifecycleContracts = () => [],
      networkLifecycleDryRunRouteCount = () => 0,
      networkLifecycleMutationRouteCount = () => 0,
      networkPathMapStatus = () => "",
      networkSetupMutationRouteRows = () => [],
      networkSetupMutationRouteSummary = () => "",
      networkStateFileCompactLines = () => [],
      networkStateFileStatus = () => "",
      networkWorkerRowsNeedingReview = () => [],
      networkWorkerStatusState = () => "unknown",
      routeExists = () => false,
      setText = () => {},
      snapshotStateLine = () => "",
      state = {},
      updateTableStatusLegend = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;

  function networkLifecycleStatusState(status) {
    const value = String(status || "").toLowerCase();
    if (value.includes("block") || value.includes("unsafe") || value.includes("failed") || value.includes("pending report")) return "blocked";
    if (value.includes("review") || value.includes("warning") || value.includes("active") || value.includes("unknown") || value.includes("stale") || value.includes("missing")) return "warning";
    return "match";
  }

  function networkLifecycleGate(key, gate, status, evidence, action, detail = []) {
    return { key, gate, status, evidence, action, detail };
  }

  function networkLifecycleRows({ role, config, closeReadiness, snapshot, contract, networkWorkers } = {}) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const workerRows = Array.isArray(payload.rows) ? payload.rows : [];
    const stateFiles = Array.isArray(payload.state_files) ? payload.state_files : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const workerState = payload.worker_state && typeof payload.worker_state === "object" ? payload.worker_state : {};
    const roleText = String(role || "standalone").toLowerCase();
    const closeLoaded = closeReadiness && typeof closeReadiness === "object";
    const closeBlocked = closeLoaded && closeReadiness.safe_to_close === false;
    const pendingDone = Boolean(workerState.pending_done_report);
    const problemRows = networkWorkerRowsNeedingReview(workerRows).filter((row) => ["blocked", "warning"].includes(networkWorkerStatusState(row)));
    const activeRows = networkWorkerRowsNeedingReview(workerRows).filter((row) => networkWorkerStatusState(row) === "running");
    const unreadableStateFiles = stateFiles.filter((item) => networkStateFileStatus(item) === "blocked");
    const missingStateFiles = stateFiles.filter((item) => networkStateFileStatus(item) === "warning");
    const presentStateFiles = stateFiles.filter((item) => networkStateFileStatus(item) === "match");
    const heartbeatTimeoutMins = displayConfigValue(config, "CoordinatorHeartbeatTimeoutMins", "not configured");
    const hasWorkerRoute = routeExists(contract, "/api/network/workers", "GET");
    const hasDiagnosticsOpen = routeExists(contract, "/api/diagnostics/open", "POST");
    const lifecycleContracts = networkLifecycleContracts(contract);
    const rows = [];

    rows.push(networkLifecycleGate(
      "lifecycle-owner",
      "Lifecycle owner",
      closeBlocked ? "blocked" : !closeLoaded ? "review" : "ready",
      `owner=Python dispatcher; close=${closeLoaded ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "not loaded"}; pipeline=${snapshot?.pipeline_state || snapshot?.state || "unknown"}`,
      closeBlocked
        ? "Do not move, retry, or change network lifecycle while close-readiness reports active work."
        : "Use backend-owned Network lifecycle controls only; run dry-runs before confirmed start/stop.",
      [
        closeReadinessLine(closeReadiness),
        snapshotStateLine(snapshot),
        "Current WebView boundary: coordinator/worker lifecycle commands are backend-owned route submissions with confirmation and command-journal evidence.",
      ],
    ));

    rows.push(networkLifecycleGate(
      "role-config",
      "Role and configuration",
      roleText === "standalone" ? "ready" : "review",
      `role=${roleText}; coordinator=${coordinatorTarget(config, payload)}; auth=hidden token posture; path map=${networkPathMapStatus(config)}`,
      roleText === "worker"
        ? "Before trusting worker mode, verify coordinator URL, auth token, and source path map from Saved Distributed Mode Settings and backend Network."
        : roleText === "coordinator"
          ? "Before trusting coordinator mode, verify bind/port/auth token and local-encode policy from Saved Distributed Mode Settings and backend Network."
          : "Standalone role has no distributed lifecycle to promote.",
      [
        `NetworkRole: ${roleText}`,
        `Worker coordinator URL: ${coordinatorTarget(config, payload)}`,
        `Coordinator bind endpoint: ${networkCoordinatorBindEndpoint(config, payload)}`,
        `Worker URL: ${displayConfigValue(config, "WorkerCoordinatorUrl", "not configured")}`,
        `Worker source path map: ${networkPathMapStatus(config)}`,
        "Network auth: token values are hidden; coordinator can generate a token when blank, and workers must match it.",
      ],
    ));

    rows.push(networkLifecycleGate(
      "claim-health",
      "Claim and worker health",
      pendingDone || problemRows.length ? "blocked" : activeRows.length || warnings.length ? "review" : "ready",
      `workers=${workerRows.length}; active=${activeRows.length}; problem=${problemRows.length}; pending done=${pendingDone ? "yes" : "no"}; warnings=${warnings.length}`,
      pendingDone
        ? "Resolve or verify the pending done report from worker_state before assuming a worker result was accepted."
          : problemRows.length
            ? "Select failed/stale workers and inspect Cluster Log, ActiveJobs, Run Logs, and Last Stderr before retrying work."
          : activeRows.length
            ? "Treat active claims as in-flight; do not close or change role until they finish or are deliberately stopped through backend-owned controls."
            : "No active/problem worker claim is visible in the loaded persisted state.",
      [
        `Worker rows: ${workerRows.length}`,
        `Active/claimed rows: ${activeRows.length}`,
        `Failed/stale/offline rows: ${problemRows.length}`,
        `Pending done report: ${pendingDone ? "yes" : "no"}`,
        ...warnings.slice(0, 6).map((warning) => `Warning: ${warning}`),
      ],
    ));

    rows.push(networkLifecycleGate(
      "state-files",
      "Runtime state files",
      unreadableStateFiles.length ? "blocked" : missingStateFiles.length || !stateFiles.length ? "review" : "ready",
      `files=${stateFiles.length}; present=${presentStateFiles.length}; missing=${missingStateFiles.length}; unreadable=${unreadableStateFiles.length}; heartbeat timeout=${heartbeatTimeoutMins} minute(s)`,
      unreadableStateFiles.length
        ? "Use Diagnostics to inspect state read failures before trusting persisted worker/coordinator evidence."
        : missingStateFiles.length || !stateFiles.length
          ? "Use Cluster Log and State Folder evidence before assuming network mode is idle or healthy."
          : "State file metadata is present; compare ages with heartbeat timeout when diagnosing stale claims.",
      [
        ...networkStateFileCompactLines(stateFiles),
        `Heartbeat timeout setting: ${heartbeatTimeoutMins} minute(s)`,
        `Coordinator state file: ${payload.coordinator_inflight_path || "not resolved"}`,
        `Local worker state file: ${payload.worker_state_path || "not resolved"}`,
        `Cluster log: ${payload.cluster_log_path || "not resolved"}`,
      ],
    ));

    rows.push(networkLifecycleGate(
      "route-boundary",
      "Route and diagnostics boundary",
      hasWorkerRoute && hasDiagnosticsOpen ? "ready" : "review",
      `network workers route=${hasWorkerRoute ? "available" : "missing"}; diagnostics open=${hasDiagnosticsOpen ? "available" : "missing"}; routes=${Array.isArray(contract?.routes) ? contract.routes.length : 0}`,
      hasWorkerRoute && hasDiagnosticsOpen
        ? "Use read-only worker/state routes and allowlisted Diagnostics opens before escalating to backend lifecycle controls."
        : "Refresh Local API contract before relying on Network WebView evidence.",
      [
        "Expected read-only route: GET /api/network/workers effect=none.",
        "Expected diagnostics route: POST /api/diagnostics/open with backend target allowlist.",
        "Authorized lifecycle commands are limited to backend-owned coordinator/worker start/stop dry-runs and confirmed start/stop routes.",
        networkLifecycleContractSummary(contract),
      ],
    ));

    rows.push(networkLifecycleGate(
      "promotion-boundary",
      "Promotion boundary",
      "ready",
      `WebView Network exposes backend-owned lifecycle controls; lifecycle contracts=${lifecycleContracts.length}; dry-run routes=${networkLifecycleDryRunRouteCount(contract)}; confirmed lifecycle routes=${networkLifecycleMutationRouteCount(contract)}; setup write/secret routes=${networkSetupMutationRouteRows(contract).length}.`,
      "Use dry-runs before coordinator/worker start or stop. Retry, reclaim, release, and abort workflows stay disabled until their backend routes and tests exist.",
      [
        networkLifecycleContractSummary(contract),
        `Setup routes: ${networkSetupMutationRouteSummary(contract)}.`,
        "Confirmed lifecycle commands remain confirmation-gated and provider-guarded.",
        "This handoff cannot retry, reclaim, release, abort, drain, publish, rename, save settings, rewrite state, or touch media files.",
      ],
    ));

    return rows;
  }

  function networkLifecycleStatus(rows = []) {
    if (!rows.length) return "Not loaded";
    if (rows.some((row) => networkLifecycleStatusState(row.status) === "blocked")) return "Blocked review";
    if (rows.some((row) => networkLifecycleStatusState(row.status) === "warning")) return "Review";
    return "Ready";
  }

  function networkLifecycleSummaryLines(rows = []) {
    const counts = rows.reduce((acc, row) => {
      const state = networkLifecycleStatusState(row.status);
      acc[state] = (acc[state] || 0) + 1;
      return acc;
    }, {});
    const reviewRows = rows.filter((row) => networkLifecycleStatusState(row.status) !== "match");
    const lines = [
      "Network lifecycle handoff:",
      `Status: ${networkLifecycleStatus(rows)}`,
      `Gates: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.warning || 0}; ready=${counts.match || 0}.`,
      "Decision rule: trust only backend-owned Network evidence and lifecycle routes; normal Launch remains blocked in network modes.",
    ];
    if (reviewRows.length) {
      lines.push("", "Gates needing attention:");
      reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.gate}: ${row.status}; ${row.action}`));
    } else {
      lines.push("", "No lifecycle handoff blockers are visible in the loaded read-only evidence.");
    }
    lines.push("", "Mutation guardrail: this panel cannot reclaim, release, abort, retry, drain, publish, rename, save settings, rewrite state, or touch media files.");
    return lines;
  }

  function getSelectedNetworkLifecycleRow(rows) {
    if (!state.selectedLifecycleKey) return null;
    return rows.find((row) => row.key === state.selectedLifecycleKey) || null;
  }

  function networkLifecycleDetailLines(row) {
    if (!row) {
      return [
        "No network lifecycle handoff row selected.",
        "Select a row to inspect lifecycle owner, role config, claim health, runtime state files, route boundary, or promotion requirements.",
        "Network lifecycle mutation remains outside WebView.",
      ];
    }
    return [
      `Gate: ${row.gate}`,
      `Status: ${row.status}`,
      `Evidence: ${row.evidence}`,
      `Safe next step: ${row.action}`,
      "",
      "Detail:",
      ...(Array.isArray(row.detail) && row.detail.length ? row.detail.map((line) => `- ${line}`) : ["- No additional detail."]),
      "",
      "Mutation guardrail: this handoff is read-only and cannot change coordinator, worker, queue, publish, settings, state, or media files.",
    ];
  }

  function renderNetworkLifecycleHandoff(payload, role, config) {
    const rows = networkLifecycleRows({
      role,
      config,
      closeReadiness: payload.closeReadiness,
      snapshot: payload.snapshot,
      contract: payload.contract || {},
      networkWorkers: payload.networkWorkers || {},
    });
    setText("network-lifecycle-status", networkLifecycleStatus(rows));
    setText("network-lifecycle-summary", networkLifecycleSummaryLines(rows).join("\n"));
    const tbody = byId("network-lifecycle-rows");
    if (!tbody) return;
    if (!rows.length) {
      state.selectedLifecycleKey = "";
      clearRows(tbody, 4, "No network lifecycle handoff rows loaded.");
      updateTableStatusLegend("network-lifecycle-legend", tbody, "Network lifecycle handoff rows");
      setText("network-lifecycle-detail", networkLifecycleDetailLines(null).join("\n"));
      return;
    }
    if (!rows.some((row) => row.key === state.selectedLifecycleKey)) {
      state.selectedLifecycleKey = rows[0].key;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = documentRef.createElement("tr");
      row.dataset.rowKey = item.key;
      row.dataset.status = networkLifecycleStatusState(item.status);
      appendCells(row, [item.gate, item.status, item.evidence, item.action]);
      makeRowSelectable(row, () => {
        state.selectedLifecycleKey = item.key;
        renderNetworkLifecycleHandoff(payload, role, config);
      }, {
        selected: item.key === state.selectedLifecycleKey,
        label: `Network lifecycle handoff ${item.gate}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("network-lifecycle-legend", tbody, "Network lifecycle handoff rows");
    setText("network-lifecycle-detail", networkLifecycleDetailLines(getSelectedNetworkLifecycleRow(rows)).join("\n"));
  }
    return {
      networkLifecycleStatusState,
      networkLifecycleGate,
      networkLifecycleRows,
      networkLifecycleStatus,
      networkLifecycleSummaryLines,
      getSelectedNetworkLifecycleRow,
      networkLifecycleDetailLines,
      renderNetworkLifecycleHandoff,
    };
  }

  window.__networkLifecycleModelModule = { createNetworkLifecycleModelModule };
})();

