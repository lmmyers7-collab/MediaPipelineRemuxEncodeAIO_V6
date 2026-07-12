// Read-only Network readiness projection and evidence rendering.
(function () {
  "use strict";

  function createNetworkReadinessModule(deps = {}) {
    const {
      configFlagText = () => "",
      coordinatorTarget = () => "",
      displayConfigValue = () => "",
      networkCoordinatorBindEndpoint = () => "",
      networkLifecycleBoundaryLines = () => [],
      networkLifecycleBoundaryStatus = () => "",
      networkPathMapStatus = () => "",
      networkRouteSummaryLines = () => [],
      networkRouteSummaryStatus = () => "",
      networkTokenPostureLines = () => [],
      routeExists = () => false,
      setText = () => {},
    } = deps;

  function closeReadinessLine(closeReadiness) {
    if (!closeReadiness || typeof closeReadiness !== "object") return "Close readiness: not loaded";
    const safe = closeReadiness.safe_to_close === true || closeReadiness.ready === true;
    const reason = closeReadiness.reason || closeReadiness.state || closeReadiness.message || "";
    return `Close readiness: ${safe ? "safe" : "active or blocked"}${reason ? ` (${reason})` : ""}`;
  }

  function networkReadinessStatus(role, settings, closeReadiness) {
    if (settings?.error) return "Settings unavailable";
    const unsafeClose = closeReadiness && typeof closeReadiness === "object" && closeReadiness.safe_to_close === false;
    if (unsafeClose) return "Active work";
    if (role === "coordinator") return "Coordinator read-only";
    if (role === "worker") return "Worker read-only";
    return "Standalone";
  }

  function snapshotStateLine(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return "Pipeline state: not loaded";
    const pipelineState = snapshot.pipeline_state || snapshot.state || snapshot.status || "loaded";
    const queueDepth = snapshot.queue_depth ?? snapshot.queue_count ?? snapshot.pending_count;
    return queueDepth === undefined
      ? `Pipeline state: ${pipelineState}`
      : `Pipeline state: ${pipelineState}; queue depth: ${queueDepth}`;
  }

  function networkReadinessLines({ role, config, closeReadiness, snapshot, contract, networkWorkers }) {
    const lines = [
      `Saved role: ${role || "standalone"}`,
      closeReadinessLine(closeReadiness),
      snapshotStateLine(snapshot),
      "Lifecycle owner: backend Network diagnostics / Python dispatcher.",
      "WebView status: backend-owned lifecycle controls available through contract routes; settings and diagnostics evidence remain read-only until submitted to backend routes.",
      "Restart note: if backend Python files were updated while this app/API was already running, restart the app/API before using lifecycle controls.",
      ...networkTokenPostureLines(networkWorkers),
    ];

    if (role === "coordinator") {
      lines.push(
        `Worker coordinator URL: ${coordinatorTarget(config, networkWorkers)}`,
        `Coordinator bind endpoint: ${networkCoordinatorBindEndpoint(config, networkWorkers)}`,
        `Coordinator encodes locally: ${configFlagText(config, "CoordinatorAlsoEncodeLocally", "not configured")}`,
        `Heartbeat timeout: ${displayConfigValue(config, "CoordinatorHeartbeatTimeoutMins", "not configured")} minute(s)`,
        "Worker board source: persisted runtime state from /api/network/workers; live dispatcher lifecycle rows remain backend-owned.",
        "Next step: inspect persisted worker evidence and backend Network diagnostics before trusting coordinator health."
      );
    } else if (role === "worker") {
      lines.push(
        `Coordinator URL: ${displayConfigValue(config, "WorkerCoordinatorUrl", "not configured")}`,
        `Worker name: ${displayConfigValue(config, "WorkerName", "OS hostname fallback")}`,
        "Network auth: token values are hidden; the worker token must match the coordinator token.",
        `Poll interval: ${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")} second(s)`,
        `Source path map: ${networkPathMapStatus(config)}`,
        "Next step: use backend Network diagnostics for worker lifecycle evidence; use Diagnostics for RunLogs and ActiveJobs when claims fail or are reclaimed."
      );
    } else {
      lines.push(
        "Standalone processing keeps queue claims local to this workstation.",
        "Next step: switch NetworkRole in Settings only after confirming no active work is running."
      );
    }

    lines.push(
      `Diagnostics open route: ${routeExists(contract, "/api/diagnostics/open", "POST") ? "available" : "not loaded"}`,
      `Contract route count: ${Array.isArray(contract?.routes) ? contract.routes.length : 0}`
    );
    return lines;
  }

  function renderNetworkReadiness(payload, role, config) {
    setText("network-readiness-status", networkReadinessStatus(role, payload.settings || {}, payload.closeReadiness));
    setText(
      "network-readiness-summary",
      networkReadinessLines({
        role,
        config,
        closeReadiness: payload.closeReadiness,
        snapshot: payload.snapshot,
        contract: payload.contract || {},
        networkWorkers: payload.networkWorkers || {},
      }).join("\n")
    );
    const boundaryPayload = {
      closeReadiness: payload.closeReadiness,
      contract: payload.contract || {},
      networkWorkers: payload.networkWorkers || {},
    };
    setText("network-lifecycle-boundary-status", networkLifecycleBoundaryStatus(boundaryPayload));
    setText("network-lifecycle-boundary-summary", networkLifecycleBoundaryLines(boundaryPayload).join("\n"));
    setText("network-route-summary-status", networkRouteSummaryStatus(payload.contract || {}));
    setText("network-route-summary", networkRouteSummaryLines(payload.contract || {}).join("\n"));
  }
    return {
      closeReadinessLine,
      networkReadinessStatus,
      snapshotStateLine,
      networkReadinessLines,
      renderNetworkReadiness,
    };
  }

  window.__networkReadinessModule = { createNetworkReadinessModule };
})();
