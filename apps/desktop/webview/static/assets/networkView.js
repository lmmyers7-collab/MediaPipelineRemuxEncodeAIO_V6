(function () {
  const fallbackNetworkKeys = [
    ["Mode", "NetworkRole", "Network Role", "How this workstation participates in network processing."],
    ["Coordinator", "CoordinatorPort", "Listen Port", "TCP port for the coordinator HTTP API."],
    ["Coordinator", "CoordinatorBindAddress", "Bind Address", "Local interface used by the coordinator API."],
    ["Coordinator", "CoordinatorAlsoEncodeLocally", "Encode Locally", "Whether the coordinator also claims local work."],
    ["Coordinator", "CoordinatorHeartbeatTimeoutMins", "Heartbeat Timeout", "Minutes before stale worker jobs are reclaimed."],
    ["Coordinator", "WorkerConfigOverrides", "Worker Overrides", "Per-worker encode setting overrides."],
    ["Worker", "WorkerCoordinatorUrl", "Coordinator URL", "Remote coordinator endpoint used by this worker."],
    ["Worker", "WorkerName", "Worker Name", "Display name shown on the coordinator worker board."],
    ["Worker", "WorkerPollIntervalSecs", "Poll Interval", "Maximum seconds between coordinator claim attempts."],
    ["Worker", "WorkerSourcePathMap", "Source Path Map", "Path rewrites from coordinator UNC roots to local worker roots."],
  ];
  let lastNetworkWorkerRows = [];
  let selectedNetworkWorkerKey = "";
  let selectedNetworkLifecycleKey = "";
  let selectedNetworkEvidenceKey = "";
  let selectedNetworkStateFileKey = "";
  let networkWorkerStatusFilter = "";
  let networkWorkerSearchText = "";
  let networkViewEventsInitialized = false;

  function settingsConfig(settings) {
    return settings && typeof settings === "object" && settings.config && typeof settings.config === "object"
      ? settings.config
      : {};
  }

  function rawConfigValue(config, key, fallback = "") {
    if (!config || typeof config !== "object") return fallback;
    if (Object.prototype.hasOwnProperty.call(config, key)) return config[key];
    const match = Object.keys(config).find((item) => item.toLowerCase() === String(key).toLowerCase());
    return match ? config[match] : fallback;
  }

  function isNetworkSecretSettingKey(key) {
    const normalized = String(key || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
    return normalized.includes("authtoken");
  }

  function displayConfigValue(config, key, fallback = "(not set)") {
    if (isNetworkSecretSettingKey(key)) return "(secret not displayed)";
    if (typeof configValue === "function") return configValue(config, key, fallback);
    const value = rawConfigValue(config, key, "");
    return value === "" || value === undefined || value === null ? fallback : String(value);
  }

  function networkSettingDefinitions(settings) {
    const definitions = Array.isArray(settings?.field_definitions) ? settings.field_definitions : [];
    const networkDefinitions = definitions
      .filter((field) => String(field?.page || "").toLowerCase() === "network")
      .filter((field) => !isNetworkSecretSettingKey(field?.key))
      .map((field) => [
        field.section || "Network",
        field.key || "",
        field.label || field.key || "",
        field.help || "",
      ])
      .filter((field) => field[1]);
    return networkDefinitions.length ? networkDefinitions : fallbackNetworkKeys;
  }

  function networkRows(settings) {
    const config = settingsConfig(settings);
    return networkSettingDefinitions(settings)
      .filter(([_section, key]) => !isNetworkSecretSettingKey(key))
      .map(([section, key, label, purpose]) => ({
        section,
        key,
        label,
        value: displayConfigValue(config, key),
        purpose,
      }));
  }

  function coordinatorTarget(config) {
    const role = String(rawConfigValue(config, "NetworkRole", "standalone") || "standalone").toLowerCase();
    if (role === "worker") {
      return displayConfigValue(config, "WorkerCoordinatorUrl", "not configured");
    }
    const bind = displayConfigValue(config, "CoordinatorBindAddress", "0.0.0.0");
    const port = displayConfigValue(config, "CoordinatorPort", "7830");
    return `${bind}:${port}`;
  }

  function networkGuidance(role) {
    if (role === "coordinator") {
      return [
        "Saved role: coordinator",
        "Saved coordinator config is controlled from Saved Worker Mode Settings on this tab.",
        "Runtime lifecycle command controls remain absent until backend routes and tests exist.",
        "Worker claim evidence is read from persisted worker state after the coordinator queue is populated.",
      ];
    }
    if (role === "worker") {
      return [
        "Saved role: worker",
        "This worker polls the configured coordinator URL and launches backend-owned single-file pipeline jobs.",
        "Worker URL, name, poll interval, path map, and overrides are controlled from Saved Worker Mode Settings on this tab.",
        "Use Diagnostics to inspect RunLogs and ActiveJobs when worker claims fail or are reclaimed.",
      ];
    }
    return [
      `Saved role: ${role || "standalone"}`,
      "Standalone mode keeps all processing local to this workstation.",
      "Use Saved Worker Mode Settings on this tab to stage role changes through backend settings Preview/Save.",
    ];
  }

  function networkModeModelLines(role) {
    return [
      `Current saved role: ${role || "standalone"}`,
      "Standalone: local queue work only on this workstation.",
      "Coordinator: owns queue claims and worker registry state.",
      "Worker: polls a coordinator and runs claimed single-file jobs.",
      "Runtime authority: WebView displays saved settings and read-only evidence; backend routes own lifecycle commands.",
    ];
  }

  function contractSummary(contract) {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    const guarded = routes.filter((route) => route.effect && route.effect !== "none");
    const tokenRoutes = routes.filter((route) => route.auth_required);
    return [
      `Routes: ${routes.length}`,
      `Guarded actions: ${guarded.length}`,
      `Token-protected routes: ${tokenRoutes.length}`,
      `Public routes: ${(contract?.auth?.public_routes || []).length || 0}`,
    ].join("\n");
  }

  function configFlagText(config, key, fallback = "not configured") {
    const raw = rawConfigValue(config, key, "");
    if (raw === "" || raw === undefined || raw === null) return fallback;
    if (typeof raw === "boolean") return raw ? "enabled" : "disabled";
    const normalized = String(raw).trim().toLowerCase();
    if (["true", "1", "yes", "on", "enabled"].includes(normalized)) return "enabled";
    if (["false", "0", "no", "off", "disabled"].includes(normalized)) return "disabled";
    return String(raw);
  }

  function configuredStatus(config, key) {
    const raw = rawConfigValue(config, key, "");
    if (raw === "" || raw === undefined || raw === null) return "not configured";
    const text = String(raw).trim();
    return text ? "configured" : "not configured";
  }

  function networkPathMapStatus(config) {
    const raw = rawConfigValue(config, "WorkerSourcePathMap", "");
    if (raw && typeof raw === "object") {
      return Object.keys(raw).length ? `${Object.keys(raw).length} mapping${Object.keys(raw).length === 1 ? "" : "s"} configured` : "not configured";
    }
    const text = String(raw || "").trim();
    if (!text) return "not configured";
    if (text.startsWith("{")) return "configured JSON map";
    return "configured";
  }

  function routeExists(contract, path, method = "GET") {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    return routes.some((route) => {
      const routePath = String(route?.path || "");
      const routeMethod = String(route?.method || "GET").toUpperCase();
      return routePath === path && routeMethod === String(method).toUpperCase();
    });
  }

  function networkLifecycleContracts(contract) {
    return Array.isArray(contract?.network_lifecycle_contracts) ? contract.network_lifecycle_contracts : [];
  }

  function networkLifecycleContractSummary(contract) {
    const contracts = networkLifecycleContracts(contract);
    const summary = contract?.network_lifecycle_summary || {};
    if (!contracts.length && !summary.schema_version) {
      return "Network lifecycle command contract: not published.";
    }
    return [
      `Network lifecycle command contract: ${summary.status || "design_only_no_lifecycle_routes"}`,
      `Design contracts: ${contracts.length}; mutation enabled=${summary.mutation_enabled ? "yes" : "no"}; frontend allowed=${summary.frontend_allowed ? "yes" : "no"}`,
      `Safe next step: ${summary.safe_next_step || "keep lifecycle controls out of WebView until backend routes, preconditions, command history, and tests exist"}`,
    ].join(" ");
  }

  function networkLifecycleMutationRouteCount(contract) {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    const networkRoutePrefix = ["/api", "network"].join("/") + "/";
    return routes.filter((route) => {
      const path = String(route?.path || "");
      const method = String(route?.method || "GET").toUpperCase();
      const effect = String(route?.effect || "").toLowerCase();
      const isReadOnly = method === "GET" && (!effect || effect === "none");
      return path.startsWith(networkRoutePrefix) && !isReadOnly;
    }).length;
  }

  function networkLifecycleBoundaryStatus({ closeReadiness, contract } = {}) {
    if (!contract?.schema_version) return "Not loaded";
    const unsafeClose = closeReadiness && typeof closeReadiness === "object" && closeReadiness.safe_to_close === false;
    if (unsafeClose) return "Blocked by active work";
    return "Read-only boundary";
  }

  function networkLifecycleBoundaryLines({ closeReadiness, contract, networkWorkers } = {}) {
    const lifecycleSummary = contract?.network_lifecycle_summary || {};
    const mutationRoutes = networkLifecycleMutationRouteCount(contract);
    const workerRouteLoaded = routeExists(contract, "/api/network/workers", "GET");
    const workerSource = networkWorkers?.source || "not loaded";
    const unsafeClose = closeReadiness && typeof closeReadiness === "object" && closeReadiness.safe_to_close === false;
    return [
      "Lifecycle owner: backend Network diagnostics / Python dispatcher.",
      closeReadinessLine(closeReadiness),
      `Persisted worker state source: ${workerSource}`,
      `Read-only worker route: ${workerRouteLoaded ? "available" : "missing"} (GET /api/network/workers, effect=none).`,
      `Lifecycle mutation routes: ${mutationRoutes ? `present (${mutationRoutes})` : "absent"}.`,
      `Design-only lifecycle contracts: ${networkLifecycleContracts(contract).length}; frontend allowed=${lifecycleSummary.frontend_allowed ? "yes" : "no"}.`,
      unsafeClose
        ? "Safe next step: leave network role/settings and lifecycle planning unchanged until close-readiness is safe."
        : "Safe next step: inspect persisted worker evidence and Diagnostics; runtime command controls stay outside this tab until backend routes, journal evidence, and no-mutation tests exist.",
    ];
  }

  function networkRouteSummaryStatus(contract) {
    if (!contract?.schema_version) return "Not loaded";
    const workerRouteLoaded = routeExists(contract, "/api/network/workers", "GET");
    const mutationRoutes = networkLifecycleMutationRouteCount(contract);
    if (workerRouteLoaded && mutationRoutes === 0) return "Read-only route";
    return "Review";
  }

  function networkRouteSummaryLines(contract) {
    const workerRouteLoaded = routeExists(contract, "/api/network/workers", "GET");
    const lifecycleContracts = networkLifecycleContracts(contract);
    const lifecycleSummary = contract?.network_lifecycle_summary || {};
    return [
      `Workers evidence route: ${workerRouteLoaded ? "GET /api/network/workers available with effect=none" : "GET /api/network/workers missing or not loaded"}.`,
      `Lifecycle mutation routes: ${networkLifecycleMutationRouteCount(contract) ? "present - review contract before showing controls" : "absent"}.`,
      `Lifecycle contract posture: ${lifecycleContracts.length ? "design-only lifecycle contracts only" : "not published"}; mutation enabled=${lifecycleSummary.mutation_enabled ? "yes" : "no"}.`,
      "Deep API contract detail remains in Advanced and Diagnostics/Contract surfaces.",
    ];
  }

  function networkOpenTargets() {
    return ["run_logs", "cluster_log", "active_jobs", "config", "state"];
  }

  function networkOpenCommandTarget(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object"
      ? raw.request
      : raw.submitted_request && typeof raw.submitted_request === "object"
        ? raw.submitted_request
        : {};
    return String(data.target || request.target || "").toLowerCase();
  }

  function networkSettingsPatchStatusText() {
    const raw = byId("settings-patch-status")?.textContent || "none";
    const text = String(raw || "none").trim();
    if (!text || text.toLowerCase() === "no patch") return "Staged Patch: none";
    return text.toLowerCase().startsWith("staged patch:") ? text : `Staged Patch: ${text}`;
  }

  function renderNetworkSettingsPatchHandoff(message = "") {
    const patchStatus = networkSettingsPatchStatusText();
    const patchText = byId("settings-patch-json")?.value || "{}";
    let patchKeys = [];
    try {
      const patch = JSON.parse(patchText);
      if (patch && typeof patch === "object" && !Array.isArray(patch)) {
        patchKeys = Object.keys(patch);
      }
    } catch (_error) {
      patchKeys = ["invalid JSON"];
    }
    setText("network-settings-control-status", patchStatus);
    setText("network-settings-patch-handoff", [
      message,
      `Saved settings patch status: ${patchStatus}`,
      `Staged keys: ${patchKeys.length ? patchKeys.join(", ") : "none"}`,
      "Preview Settings Patch calls the backend settings preview route and does not write the PSD1.",
      "Save Worker Settings calls the backend settings save route, asks for confirmation, and creates the normal config backup before writing.",
      "Runtime boundary: these controls only stage, preview, and save config. Coordinator/worker lifecycle command controls are not exposed on this tab.",
    ].filter(Boolean).join("\n"));
  }

  async function previewNetworkSettingsPatch() {
    const preview = window.mediaPipelineSettingsView?.previewSettingsPatch;
    if (typeof preview !== "function") {
      setText("network-settings-control-status", "Settings unavailable");
      renderNetworkSettingsPatchHandoff("Settings preview controls are not loaded.");
      return;
    }
    setText("network-settings-control-status", "Previewing...");
    renderNetworkSettingsPatchHandoff("Previewing staged Saved Worker Mode Settings through backend validation.");
    await preview();
    renderNetworkSettingsPatchHandoff("Saved Worker Mode Settings preview command finished.");
  }

  async function saveNetworkSettingsPatch() {
    const save = window.mediaPipelineSettingsView?.saveSettingsPatch;
    if (typeof save !== "function") {
      setText("network-settings-control-status", "Settings unavailable");
      renderNetworkSettingsPatchHandoff("Settings save controls are not loaded.");
      return;
    }
    setText("network-settings-control-status", "Saving...");
    renderNetworkSettingsPatchHandoff("Saving staged Saved Worker Mode Settings through the backend settings route.");
    await save();
    renderNetworkSettingsPatchHandoff("Saved Worker Mode Settings save command finished.");
  }

  function isNetworkOpenCommand(entry) {
    if (String(entry?.command || "").toLowerCase() !== "diagnostics.open") return false;
    return networkOpenTargets().includes(networkOpenCommandTarget(entry));
  }

  function networkOpenHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object"
      ? raw.request
      : raw.submitted_request && typeof raw.submitted_request === "object"
        ? raw.submitted_request
        : {};
    const bits = [];
    if (data.target || request.target) bits.push(`target=${data.target || request.target}`);
    if (data.opened_path) bits.push(`opened=${data.opened_path}`);
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: "diagnostics.open",
        detail: bits.length ? ` (${bits.join("; ")})` : "",
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} diagnostics.open [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
  }

  function renderNetworkOpenHistory(history = []) {
    const entries = Array.isArray(history) ? history.filter(isNetworkOpenCommand).slice(0, 6) : [];
    setText("network-open-history-status", entries.length ? `${entries.length} recent` : "No opens");
    if (!Array.isArray(history) || !history.length) {
      setText("network-open-history", "No network diagnostics open command history loaded. Open a network diagnostics location to see backend results here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("network-open-history", "No network diagnostics open commands found in recent command history.");
      return;
    }
    setText("network-open-history", [
      `Last ${entries.length} network diagnostics open command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(networkOpenHistoryLine),
      "Backend diagnostics target allowlists remain the source of truth.",
    ].join("\n"));
  }

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

  function networkReadinessLines({ role, config, closeReadiness, snapshot, contract }) {
    const lines = [
      `Saved role: ${role || "standalone"}`,
      closeReadinessLine(closeReadiness),
      snapshotStateLine(snapshot),
      "Lifecycle owner: backend Network diagnostics / Python dispatcher.",
      "WebView status: read-only settings, contract, logs, and diagnostic opens.",
    ];

    if (role === "coordinator") {
      lines.push(
        `Coordinator target: ${coordinatorTarget(config)}`,
        `Coordinator encodes locally: ${configFlagText(config, "CoordinatorAlsoEncodeLocally", "not configured")}`,
        `Heartbeat timeout: ${displayConfigValue(config, "CoordinatorHeartbeatTimeoutMins", "not configured")} minute(s)`,
        "Worker board source: persisted runtime state from /api/network/workers; live dispatcher lifecycle rows remain backend-owned.",
        "Next step: inspect persisted worker evidence and backend Network diagnostics before trusting coordinator health."
      );
    } else if (role === "worker") {
      lines.push(
        `Coordinator URL: ${displayConfigValue(config, "WorkerCoordinatorUrl", "not configured")}`,
        `Worker name: ${displayConfigValue(config, "WorkerName", "OS hostname fallback")}`,
        "Network auth: backend-owned secret, not displayed by WebView.",
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
    const problemRows = networkWorkerRowsNeedingReview(workerRows).filter((row) => networkWorkerStatusState(row) === "blocked");
    const activeRows = networkWorkerRowsNeedingReview(workerRows).filter((row) => networkWorkerStatusState(row) === "warning");
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
        : "Keep WebView lifecycle read-only until backend-owned start/stop contracts exist.",
      [
        closeReadinessLine(closeReadiness),
        snapshotStateLine(snapshot),
        "Current WebView boundary: settings and evidence display only; no coordinator/worker lifecycle commands.",
      ],
    ));

    rows.push(networkLifecycleGate(
      "role-config",
      "Role and configuration",
      roleText === "standalone" ? "ready" : "review",
      `role=${roleText}; coordinator=${coordinatorTarget(config)}; auth=backend-owned secret not displayed; path map=${networkPathMapStatus(config)}`,
      roleText === "worker"
        ? "Before trusting worker mode, verify coordinator URL, auth token, and source path map from Saved Worker Mode Settings and backend Network."
        : roleText === "coordinator"
          ? "Before trusting coordinator mode, verify bind/port/auth token and local-encode policy from Saved Worker Mode Settings and backend Network."
          : "Standalone role has no distributed lifecycle to promote.",
      [
        `NetworkRole: ${roleText}`,
        `Coordinator target: ${coordinatorTarget(config)}`,
        `Worker URL: ${displayConfigValue(config, "WorkerCoordinatorUrl", "not configured")}`,
        `Worker source path map: ${networkPathMapStatus(config)}`,
        "Network auth: backend-owned secret, not displayed by WebView.",
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
        "No WebView network start/stop/reclaim/release route is currently authorized.",
        networkLifecycleContractSummary(contract),
      ],
    ));

    rows.push(networkLifecycleGate(
      "promotion-boundary",
      "Promotion boundary",
      "ready",
      `WebView Network remains a read-only evidence surface; lifecycle design contracts=${lifecycleContracts.length}; mutation routes=0.`,
      "Keep coordinator/worker start, stop, retry, reclaim, release, and abort workflows out of the WebView until backend-owned lifecycle routes implement the published dry-run, cleanup, journal, and test gates.",
      [
        networkLifecycleContractSummary(contract),
        "Required before future lifecycle controls: duplicate-command guard, close-readiness integration, command journal records, cancellation cleanup, and browser/no-mutation smoke coverage.",
        "This handoff cannot start, stop, retry, reclaim, release, abort, drain, publish, rename, save settings, rewrite state, or touch media files.",
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
      "Decision rule: WebView Network can be trusted for read-only evidence only; lifecycle controls stay backend-owned until backend command ownership is designed and tested.",
    ];
    if (reviewRows.length) {
      lines.push("", "Gates needing attention:");
      reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.gate}: ${row.status}; ${row.action}`));
    } else {
      lines.push("", "No lifecycle handoff blockers are visible in the loaded read-only evidence.");
    }
    lines.push("", "Mutation guardrail: this panel cannot start, stop, reclaim, release, abort, retry, drain, publish, rename, save settings, rewrite state, or touch media files.");
    return lines;
  }

  function getSelectedNetworkLifecycleRow(rows) {
    if (!selectedNetworkLifecycleKey) return null;
    return rows.find((row) => row.key === selectedNetworkLifecycleKey) || null;
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
      selectedNetworkLifecycleKey = "";
      clearRows(tbody, 4, "No network lifecycle handoff rows loaded.");
      updateTableStatusLegend("network-lifecycle-legend", tbody, "Network lifecycle handoff rows");
      setText("network-lifecycle-detail", networkLifecycleDetailLines(null).join("\n"));
      return;
    }
    if (!rows.some((row) => row.key === selectedNetworkLifecycleKey)) {
      selectedNetworkLifecycleKey = rows[0].key;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.rowKey = item.key;
      row.dataset.status = networkLifecycleStatusState(item.status);
      appendCells(row, [item.gate, item.status, item.evidence, item.action]);
      makeRowSelectable(row, () => {
        selectedNetworkLifecycleKey = item.key;
        renderNetworkLifecycleHandoff(payload, role, config);
      }, {
        selected: item.key === selectedNetworkLifecycleKey,
        label: `Network lifecycle handoff ${item.gate}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("network-lifecycle-legend", tbody, "Network lifecycle handoff rows");
    setText("network-lifecycle-detail", networkLifecycleDetailLines(getSelectedNetworkLifecycleRow(rows)).join("\n"));
  }

  function networkEvidenceCount(value) {
    const number = Number(value || 0);
    return Number.isFinite(number) ? Math.max(0, Math.round(number)) : 0;
  }

  function networkEvidencePostureStatus(posture) {
    const value = String(posture || "").toLowerCase();
    if (value.includes("blocked") || value.includes("unsafe") || value.includes("failed") || value.includes("pending report")) return "blocked";
    if (value.includes("review") || value.includes("warning") || value.includes("unknown") || value.includes("stale") || value.includes("not loaded")) return "warning";
    return "match";
  }

  function networkEvidenceStatus(rows = []) {
    if (!rows.length) return "Not loaded";
    if (rows.some((row) => networkEvidencePostureStatus(row.posture) === "blocked")) return "Blocked review";
    if (rows.some((row) => networkEvidencePostureStatus(row.posture) === "warning")) return "Review";
    return "Ready";
  }

  function networkEvidenceWorkerCounts(rows = []) {
    return (Array.isArray(rows) ? rows : []).reduce((counts, row) => {
      const state = networkWorkerStatusState(row) || "unknown";
      counts[state] = (counts[state] || 0) + 1;
      return counts;
    }, {});
  }

  function networkEvidenceRow(key, checkpoint, posture, evidence, action, detail = []) {
    return { key, checkpoint, posture, evidence, action, detail };
  }

  function networkEvidenceRows({ role, config, closeReadiness, snapshot, contract, networkWorkers } = {}) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const workerState = payload.worker_state && typeof payload.worker_state === "object" ? payload.worker_state : {};
    const workerCounts = networkEvidenceWorkerCounts(rows);
    const hasWorkerRoute = routeExists(contract, "/api/network/workers", "GET");
    const hasDiagnosticsOpen = routeExists(contract, "/api/diagnostics/open", "POST");
    const lifecycleContracts = networkLifecycleContracts(contract);
    const roleText = role || "standalone";
    const closeLoaded = closeReadiness && typeof closeReadiness === "object";
    const closeBlocked = closeLoaded && closeReadiness.safe_to_close === false;
    const pendingDone = Boolean(workerState.pending_done_report);
    const problemRows = networkEvidenceCount(workerCounts.blocked);
    const activeRows = networkEvidenceCount(workerCounts.warning);
    const idleRows = networkEvidenceCount(workerCounts.match);
    const unknownRows = networkEvidenceCount(workerCounts.unknown);
    const hasNetworkMode = roleText === "coordinator" || roleText === "worker";
    const pathMap = networkPathMapStatus(config);
    const overrides = configuredStatus(config, "WorkerConfigOverrides");
    const evidence = [];

    evidence.push(networkEvidenceRow(
      "role-settings",
      "Role / settings",
      hasNetworkMode ? "review" : "ready",
      `role=${roleText}; target=${coordinatorTarget(config)}; worker poll=${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")}; path map=${pathMap}; overrides=${overrides}`,
      hasNetworkMode
        ? "Review Settings Network builder and backend Network diagnostics before trusting distributed work."
        : "Standalone mode has no worker lifecycle to start from WebView.",
      [
        `NetworkRole: ${roleText}`,
        `Coordinator target: ${coordinatorTarget(config)}`,
        `Coordinator local encode: ${configFlagText(config, "CoordinatorAlsoEncodeLocally", "not configured")}`,
        `Worker URL: ${displayConfigValue(config, "WorkerCoordinatorUrl", "not configured")}`,
        `Worker source path map: ${pathMap}`,
        `Per-worker overrides: ${overrides}`,
      ],
    ));

    evidence.push(networkEvidenceRow(
      "lifecycle-boundary",
      "Lifecycle boundary",
      !closeLoaded ? "unknown" : closeBlocked ? "blocked" : "ready",
      `close=${closeLoaded ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "not loaded"}; state=${snapshot?.pipeline_state || closeReadiness?.state || "unknown"}`,
      closeBlocked
        ? "Do not change NetworkRole or start/stop coordinator/worker work while close-readiness reports active work."
        : "Lifecycle controls remain backend-owned until backend command ownership is designed and tested.",
      [
        closeReadinessLine(closeReadiness),
        snapshotStateLine(snapshot),
        "WebView can inspect persisted state and logs only; it cannot start, stop, drain, reclaim, abort, or release network jobs.",
      ],
    ));

    evidence.push(networkEvidenceRow(
      "api-contract",
      "API contract",
      hasWorkerRoute && hasDiagnosticsOpen ? "ready" : "not loaded",
      `network workers route=${hasWorkerRoute ? "available" : "missing"}; diagnostics open=${hasDiagnosticsOpen ? "available" : "missing"}; routes=${Array.isArray(contract?.routes) ? contract.routes.length : 0}`,
      hasWorkerRoute
        ? "Use Network worker rows for persisted evidence; use Diagnostics opens/tails for logs and state."
        : "Refresh contract and Local API before trusting Network page state.",
      [
        "Route /api/network/workers is read-only and has effect=none in the backend contract.",
        networkLifecycleContractSummary(contract),
        "Diagnostics open actions use backend target allowlists, not frontend paths.",
      ],
    ));

    evidence.push(networkEvidenceRow(
      "persisted-worker-state",
      "Persisted worker state",
      payload.error ? "blocked" : problemRows ? "blocked" : warnings.length || (hasNetworkMode && !rows.length) || unknownRows ? "review" : "ready",
      `rows=${rows.length}; active=${activeRows}; idle=${idleRows}; problem=${problemRows}; unknown=${unknownRows}; warnings=${warnings.length}`,
      payload.error
        ? "Open Diagnostics and cluster.log before relying on network mode."
        : problemRows
          ? "Select problem worker rows, read Cluster Log / Last Stderr / ActiveJobs, and use backend lifecycle controls only after evidence agrees."
          : warnings.length || (hasNetworkMode && !rows.length)
            ? "Read warning text and compare backend Network diagnostics before starting distributed work."
            : "Persisted worker evidence has no visible blockers in this payload.",
      [
        `Source: ${payload.source || "runtime_state_files"}`,
        `Active/idle/session completed/session failed: ${payload.active_count || 0}/${payload.idle_count || 0}/${payload.session_completed || 0}/${payload.session_failed || 0}`,
        `Coordinator state file: ${payload.coordinator_inflight_path || "not resolved"}`,
        `Cluster log: ${payload.cluster_log_path || "not resolved"}`,
        ...networkStateFileCompactLines(payload.state_files || []),
        ...warnings.slice(0, 8).map((warning) => `Warning: ${warning}`),
      ],
    ));

    evidence.push(networkEvidenceRow(
      "local-worker-recovery",
      "Local worker recovery",
      pendingDone ? "pending report" : roleText === "worker" && !workerState.job_id && !workerState.source_file ? "review" : "ready",
      `job=${workerState.job_id || "none"}; file=${workerState.source_file || "none"}; pending done report=${pendingDone ? "yes" : "no"}`,
      pendingDone
        ? "Do not assume the last worker completion was accepted. Inspect worker_state, Cluster Log, and coordinator state from Diagnostics."
        : roleText === "worker" && !workerState.job_id && !workerState.source_file
          ? "Worker may be idle; compare with backend worker polling status and cluster.log before troubleshooting."
          : "No pending local worker recovery item is visible.",
      [
        `Worker state path: ${payload.worker_state_path || "not resolved"}`,
        `Job: ${workerState.job_id || "(none)"}`,
        `Source file: ${workerState.source_file || "(none)"}`,
        `Pending done report: ${pendingDone ? "yes" : "no"}`,
      ],
    ));

    evidence.push(networkEvidenceRow(
      "diagnostics-evidence",
      "Diagnostics evidence",
      hasDiagnosticsOpen ? "ready" : "review",
      `cluster log path=${payload.cluster_log_path || "not resolved"}; diagnostics open=${hasDiagnosticsOpen ? "available" : "missing"}`,
      hasDiagnosticsOpen
        ? "Read/open Cluster Log, Run Logs, ActiveJobs, and State before changing network role or retrying worker claims."
        : "Refresh Local API contract before using diagnostics actions.",
      [
        "Suggested read order: Cluster Log -> ActiveJobs -> Run Logs -> Last Stderr -> State Folder.",
        "Diagnostics target allowlists remain the source of truth for opening files/folders.",
      ],
    ));

    evidence.push(networkEvidenceRow(
      "mutation-boundary",
      "Mutation boundary",
      "ready",
      `Network page is read-only persisted evidence; lifecycle design contracts=${lifecycleContracts.length}; mutation routes=0.`,
      "Use backend Network diagnostics for coordinator/worker lifecycle until backend routes implement the published dry-run, close guard, command journal, and rollback semantics.",
      [
        "This checklist cannot start, stop, abort, reclaim, release, drain, publish, rename, save settings, rewrite state, or touch media files.",
        networkLifecycleContractSummary(contract),
        "Changing network settings still requires Settings Preview/Save through backend-owned config routes.",
      ],
    ));

    return evidence;
  }

  function networkEvidenceSummaryLines(rows = []) {
    const counts = rows.reduce((acc, row) => {
      const key = networkEvidencePostureStatus(row.posture);
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const reviewRows = rows.filter((row) => networkEvidencePostureStatus(row.posture) !== "match");
    const lines = [
      "Network evidence checklist:",
      `Status: ${networkEvidenceStatus(rows)}`,
      `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.warning || 0}; ready=${counts.match || 0}.`,
      "Boundary: persisted worker state is visible through /api/network/workers, but coordinator/worker lifecycle controls remain backend-owned.",
    ];
    if (reviewRows.length) {
      lines.push("", "Rows needing attention:");
      reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.posture}; ${row.action}`));
    } else {
      lines.push("", "No network evidence review rows are visible in the loaded payload.");
    }
    return lines;
  }

  function getSelectedNetworkEvidenceRow(rows) {
    if (!selectedNetworkEvidenceKey) return null;
    return rows.find((row) => row.key === selectedNetworkEvidenceKey) || null;
  }

  function renderNetworkEvidenceDetail(item) {
    if (!item) {
      setText("network-evidence-detail", "No network evidence row selected. Select a row to inspect role, persisted worker state, lifecycle boundary, diagnostics, and mutation guardrails.");
      return;
    }
    setText("network-evidence-detail", [
      `Checkpoint: ${item.checkpoint}`,
      `Posture: ${item.posture}`,
      `Evidence: ${item.evidence}`,
      `Safe next step: ${item.action}`,
      "",
      "Detail:",
      ...(Array.isArray(item.detail) && item.detail.length ? item.detail.map((line) => `- ${line}`) : ["- No additional detail."]),
    ].join("\n"));
  }

  function renderNetworkEvidenceChecklist(payload, role, config) {
    const rows = networkEvidenceRows({
      role,
      config,
      closeReadiness: payload.closeReadiness,
      snapshot: payload.snapshot,
      contract: payload.contract || {},
      networkWorkers: payload.networkWorkers || {},
    });
    setText("network-evidence-status", networkEvidenceStatus(rows));
    setText("network-evidence-summary", networkEvidenceSummaryLines(rows).join("\n"));
    const tbody = byId("network-evidence-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No network evidence rows loaded.");
      updateTableStatusLegend("network-evidence-legend", tbody, "Network evidence rows");
      renderNetworkEvidenceDetail(null);
      return;
    }
    if (!rows.some((row) => row.key === selectedNetworkEvidenceKey)) {
      selectedNetworkEvidenceKey = rows[0].key;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.rowKey = item.key;
      row.dataset.status = networkEvidencePostureStatus(item.posture);
      appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
      makeRowSelectable(row, () => {
        selectedNetworkEvidenceKey = item.key;
        renderNetworkEvidenceChecklist(payload, role, config);
      }, {
        selected: item.key === selectedNetworkEvidenceKey,
        label: `Network evidence ${item.checkpoint}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("network-evidence-legend", tbody, "Network evidence rows");
    renderNetworkEvidenceDetail(getSelectedNetworkEvidenceRow(rows));
  }

  function networkStateFileRows(networkWorkers) {
    return Array.isArray(networkWorkers?.state_files) ? networkWorkers.state_files : [];
  }

  function networkStateFileStatus(item) {
    const status = String(item?.status || "").toLowerCase();
    if (status.includes("unreadable")) return "blocked";
    if (status.includes("missing")) return "warning";
    if (status.includes("present")) return "match";
    return "warning";
  }

  function networkStateFileStatusText(rows = []) {
    if (!rows.length) return "Not loaded";
    if (rows.some((item) => networkStateFileStatus(item) === "blocked")) return "Blocked review";
    if (rows.some((item) => networkStateFileStatus(item) === "warning")) return "Review";
    return "Ready";
  }

  function networkStateFileKey(item) {
    return String(item?.key || item?.label || item?.path || "").toLowerCase();
  }

  function networkStateFileAgeText(item) {
    if (!item || item.exists === false || String(item.status || "").toLowerCase() === "missing") return "-";
    const age = item.age_seconds;
    if (age === null || age === undefined || age === "") return "unknown age";
    const numeric = Number(age);
    if (!Number.isFinite(numeric)) return "unknown age";
    if (numeric < 60) return `${Math.max(0, Math.round(numeric))}s old`;
    if (numeric < 3600) return `${Math.round(numeric / 60)}m old`;
    if (numeric < 86400) return `${Math.round(numeric / 3600)}h old`;
    return `${Math.round(numeric / 86400)}d old`;
  }

  function networkStateFileCompactLines(rows = []) {
    const files = Array.isArray(rows) ? rows : [];
    if (!files.length) return ["State files: not loaded"];
    return [
      `State files: ${files.length}; present=${files.filter((item) => networkStateFileStatus(item) === "match").length}; missing=${files.filter((item) => networkStateFileStatus(item) === "warning").length}; unreadable=${files.filter((item) => networkStateFileStatus(item) === "blocked").length}`,
      ...files.slice(0, 4).map((item) => `${item.label || item.key || "state file"}: ${item.status || "unknown"}; age=${networkStateFileAgeText(item)}`),
    ];
  }

  function networkStateFileSummaryLines(rows = []) {
    const files = Array.isArray(rows) ? rows : [];
    const present = files.filter((item) => networkStateFileStatus(item) === "match").length;
    const missing = files.filter((item) => networkStateFileStatus(item) === "warning").length;
    const unreadable = files.filter((item) => networkStateFileStatus(item) === "blocked").length;
    const lines = [
      "Network runtime state file evidence:",
      `Status: ${networkStateFileStatusText(files)}`,
      `Files: ${files.length}; present=${present}; missing=${missing}; unreadable=${unreadable}.`,
      "Read order: Cluster log -> Coordinator in-flight registry -> Local worker state -> ActiveJobs / Run Logs when a row is active or failed.",
      "Mutation guardrail: this panel only reads backend-authored state-file metadata; it cannot open arbitrary paths or start/stop network work.",
    ];
    if (!files.length) {
      lines.push("No state-file metadata is loaded from the backend network worker payload.");
    } else {
      const review = files.filter((item) => networkStateFileStatus(item) !== "match");
      if (review.length) {
        lines.push("", "Rows needing attention:");
        review.forEach((item) => lines.push(`- ${item.label || item.key || "state file"}: ${item.status || "unknown"}; ${item.path || "path not resolved"}`));
      } else {
        lines.push("", "All expected network runtime state files are present in the loaded payload.");
      }
    }
    return lines;
  }

  function getSelectedNetworkStateFileRow(rows) {
    if (!selectedNetworkStateFileKey) return null;
    return (Array.isArray(rows) ? rows : []).find((item) => networkStateFileKey(item) === selectedNetworkStateFileKey) || null;
  }

  function networkStateFileDetailLines(item) {
    if (!item) {
      return [
        "No network runtime state file selected.",
        "Select a state file row to inspect backend-resolved path, status, size, age, and safe read order.",
        "This detail is read-only metadata from /api/network/workers; Diagnostics remains responsible for backend-allowlisted opens and tails.",
      ];
    }
    const lines = [
      `File: ${item.label || item.key || "state file"}`,
      `Key: ${item.key || "(none)"}`,
      `Status: ${item.status || "unknown"}`,
      `Exists: ${item.exists === true ? "yes" : "no"}`,
      `Path: ${item.path || "not resolved"}`,
      `Size: ${item.size_bytes === undefined || item.size_bytes === null ? "-" : item.size_bytes} bytes`,
      `Modified: ${item.modified_at || "-"}`,
      `Age: ${networkStateFileAgeText(item)}`,
      `Purpose: ${item.purpose || "No purpose loaded."}`,
    ];
    if (item.error) lines.push(`Error: ${item.error}`);
    lines.push(
      "",
      "Safe next step: use Diagnostics allowlisted open/tail controls for cluster.log, ActiveJobs, Run Logs, or State before changing role, retrying worker claims, or trusting pending done reports.",
      "Mutation guardrail: this panel cannot start/stop coordinator or workers, reclaim jobs, rewrite state, save settings, or touch media files."
    );
    return lines;
  }

  function renderNetworkStateFileDetail(item) {
    setText("network-state-files-detail", networkStateFileDetailLines(item).join("\n"));
  }

  function renderNetworkStateFiles(networkWorkers) {
    const rows = networkStateFileRows(networkWorkers);
    setText("network-state-files-status", networkStateFileStatusText(rows));
    setText("network-state-files-summary", networkStateFileSummaryLines(rows).join("\n"));
    const tbody = byId("network-state-files-rows");
    if (!tbody) return;
    if (!rows.length) {
      selectedNetworkStateFileKey = "";
      clearRows(tbody, 4, "No network runtime state file evidence loaded.");
      updateTableStatusLegend("network-state-files-legend", tbody, "Network runtime state file rows");
      renderNetworkStateFileDetail(null);
      return;
    }
    if (!rows.some((item) => networkStateFileKey(item) === selectedNetworkStateFileKey)) {
      selectedNetworkStateFileKey = networkStateFileKey(rows[0]);
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const key = networkStateFileKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = networkStateFileStatus(item);
      row.title = item.path || "";
      appendCells(row, [
        item.label || item.key || "",
        item.status || "",
        networkStateFileAgeText(item),
        item.purpose || "",
      ], [null, null, "num", null]);
      makeRowSelectable(row, () => {
        selectedNetworkStateFileKey = key;
        renderNetworkStateFiles(networkWorkers);
      }, {
        selected: Boolean(key && key === selectedNetworkStateFileKey),
        label: `Network runtime state file ${item.label || item.key || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("network-state-files-legend", tbody, "Network runtime state file rows");
    renderNetworkStateFileDetail(getSelectedNetworkStateFileRow(rows));
  }

  function renderNetworkSettingsRows(settings) {
    const rows = networkRows(settings);
    setText("network-settings-status", `${rows.length} setting${rows.length === 1 ? "" : "s"}`);
    const tbody = byId("network-settings-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No network settings loaded.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.title = item.key;
      appendCells(row, [item.section, item.label, item.value, item.purpose]);
      tbody.appendChild(row);
    });
  }

  function workerDisplayValue(value, fallback = "-") {
    if (value === undefined || value === null || value === "") return fallback;
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch (error) {
        return fallback;
      }
    }
    return String(value);
  }

  function networkWorkerRowKey(item) {
    if (!item || typeof item !== "object") return "";
    const parts = [
      item.worker_id,
      item.worker_name,
      item.job_id,
      item.source_file,
      item.current_file,
      item.current_file_name,
    ].filter((value) => value !== undefined && value !== null && String(value).trim());
    return parts.join("\u001f").toLowerCase();
  }

  function getSelectedNetworkWorkerRow() {
    if (!selectedNetworkWorkerKey) return null;
    return lastNetworkWorkerRows.find((item) => networkWorkerRowKey(item) === selectedNetworkWorkerKey) || null;
  }

  function networkWorkerStatusState(item) {
    const status = String(item?.status || "").toLowerCase();
    const stage = String(item?.current_stage || "").toLowerCase();
    if (status.includes("fail") || status.includes("error") || status.includes("offline") || status.includes("stale") || stage.includes("fail")) return "blocked";
    if (status.includes("active") || status.includes("running") || status.includes("working") || status.includes("claimed") || status.includes("busy")) return "warning";
    if (status.includes("idle") || status.includes("done") || status.includes("complete") || status.includes("ready")) return "match";
    return "";
  }

  function networkWorkerFilterText(item) {
    if (!item || typeof item !== "object") return "";
    return Object.keys(item)
      .sort()
      .map((key) => `${key} ${workerDisplayValue(item[key], "")}`)
      .join(" ")
      .toLowerCase();
  }

  function networkWorkerMatchesStatusFilter(item) {
    const filter = networkWorkerStatusFilter;
    if (!filter) return true;
    const state = networkWorkerStatusState(item);
    if (filter === "active") return state === "warning";
    if (filter === "idle") return state === "match";
    if (filter === "problem") return state === "blocked";
    if (filter === "unknown") return !state;
    return true;
  }

  function filteredNetworkWorkerRows(rows) {
    const query = networkWorkerSearchText.trim().toLowerCase();
    return (Array.isArray(rows) ? rows : []).filter((item) => {
      if (!networkWorkerMatchesStatusFilter(item)) return false;
      return !query || networkWorkerFilterText(item).includes(query);
    });
  }

  function networkWorkerFilterLabel() {
    const parts = [];
    if (networkWorkerStatusFilter) parts.push(`status=${networkWorkerStatusFilter}`);
    if (networkWorkerSearchText.trim()) parts.push(`search="${networkWorkerSearchText.trim()}"`);
    return parts.length ? parts.join("; ") : "none";
  }

  function networkWorkerRowsNeedingReview(rows) {
    return (Array.isArray(rows) ? rows : []).filter((item) => {
      const state = networkWorkerStatusState(item);
      return state === "blocked" || state === "warning";
    });
  }

  function renderNetworkWorkerFilterSummary(rows, visibleRows) {
    const allRows = Array.isArray(rows) ? rows : [];
    const shownRows = Array.isArray(visibleRows) ? visibleRows : [];
    if (!allRows.length) {
      setText(
        "network-worker-filter-summary",
        "No persisted worker rows are loaded. Open Cluster Log, ActiveJobs, or State before troubleshooting worker lifecycle."
      );
      return;
    }
    const visibleKeys = new Set(shownRows.map(networkWorkerRowKey));
    const hiddenReviewRows = networkWorkerRowsNeedingReview(allRows)
      .filter((row) => !visibleKeys.has(networkWorkerRowKey(row)));
    const lines = [
      `Showing ${shownRows.length}/${allRows.length} persisted worker row${allRows.length === 1 ? "" : "s"}. Filter: ${networkWorkerFilterLabel()}.`,
    ];
    if (hiddenReviewRows.length) {
      lines.push(`${hiddenReviewRows.length} active/problem worker row${hiddenReviewRows.length === 1 ? " is" : "s are"} hidden by the current filter. Clear or change filters before lifecycle decisions.`);
    } else {
      lines.push("No active/problem worker rows are hidden by the current filter.");
    }
    lines.push("Mutation guardrail: filters only change this visible table; they do not start, stop, reclaim, release, or mutate network jobs.");
    setText("network-worker-filter-summary", lines.join("\n"));
  }

  function networkWorkerDetailLines(item) {
    if (!item || typeof item !== "object") {
      return [
        "No network worker row selected.",
        "Select a worker row to inspect persisted coordinator/worker state, current file, progress, heartbeat, and available row fields.",
        "Lifecycle controls remain backend-owned. This detail pane is read-only persisted state.",
      ];
    }
    const knownKeys = new Set([
      "worker_name",
      "worker_id",
      "status",
      "job_id",
      "current_file",
      "current_file_name",
      "source_file",
      "current_stage",
      "progress_percent",
      "heartbeat_age_seconds",
      "last_heartbeat",
      "files_completed",
      "total_gb_encoded",
      "avg_speed_gbh",
      "current_speed_gbh",
      "return_code",
      "error",
    ]);
    const lines = [
      `Worker: ${workerDisplayValue(item.worker_name || item.worker_id)}`,
      `Worker ID: ${workerDisplayValue(item.worker_id)}`,
      `Status: ${workerDisplayValue(item.status)}`,
      `Job: ${workerDisplayValue(item.job_id)}`,
      `Current file: ${workerDisplayValue(item.current_file_name || item.current_file)}`,
      `Source file: ${workerDisplayValue(item.source_file)}`,
      `Stage: ${workerDisplayValue(item.current_stage)}`,
      `Progress: ${workerProgressText(item)}`,
      `Heartbeat age: ${workerHeartbeatText(item)}`,
      `Last heartbeat: ${workerDisplayValue(item.last_heartbeat)}`,
      `Files completed: ${workerDisplayValue(item.files_completed)}`,
      `Total GB encoded: ${workerDisplayValue(item.total_gb_encoded)}`,
      `Average GB/h: ${workerDisplayValue(item.avg_speed_gbh)}`,
      `Current GB/h: ${workerDisplayValue(item.current_speed_gbh)}`,
      `Return code: ${workerDisplayValue(item.return_code)}`,
    ];
    if (item.error) lines.push(`Error: ${workerDisplayValue(item.error)}`);
    const extraKeys = Object.keys(item)
      .filter((key) => !knownKeys.has(key) && workerDisplayValue(item[key], "") !== "")
      .sort()
      .slice(0, 12);
    if (extraKeys.length) {
      lines.push("", "Additional row fields:");
      extraKeys.forEach((key) => lines.push(`- ${key}: ${workerDisplayValue(item[key])}`));
    }
    lines.push("", "Lifecycle controls remain backend-owned. This detail pane is read-only persisted state.");
    return lines;
  }

  function renderNetworkWorkerDetail(item) {
    setText("network-worker-detail", networkWorkerDetailLines(item).join("\n"));
  }

  function selectNetworkWorkerRow(item) {
    selectedNetworkWorkerKey = networkWorkerRowKey(item);
    renderNetworkWorkerDetail(item);
    renderNetworkWorkerRows({ rows: lastNetworkWorkerRows });
  }

  function workerHeartbeatText(row) {
    const age = row?.heartbeat_age_seconds;
    if (age === null || age === undefined || age === "") return row?.last_heartbeat ? "unknown age" : "-";
    const numeric = Number(age);
    if (!Number.isFinite(numeric)) return "unknown age";
    if (numeric < 60) return `${Math.max(0, Math.round(numeric))}s ago`;
    if (numeric < 3600) return `${Math.round(numeric / 60)}m ago`;
    return `${Math.round(numeric / 3600)}h ago`;
  }

  function workerProgressText(row) {
    const value = Number(row?.progress_percent || 0);
    return Number.isFinite(value) && value > 0 ? `${Math.round(value)}%` : "-";
  }

  function networkWorkerProgressStatus(progress) {
    const status = String(progress?.status || "").trim();
    if (!status) return "Not loaded";
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function networkWorkerProgressSummaryLines(progress) {
    const payload = progress && typeof progress === "object" ? progress : {};
    const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
      ? payload.summary_lines.map((line) => String(line || "")
        .replace(/^Worker progress:/, "Last reported worker progress:")
        .replace(
          /^Mutation guardrail: Network progress is read-only persisted runtime evidence;/,
          "Mutation guardrail: Last reported network progress is read-only persisted runtime evidence;"
        ))
      : [
        `Last reported worker progress: ${payload.status || "not loaded"}`,
        `Progress bars: ${payload.bar_count || 0}`,
        `Active worker bars: ${payload.active_count || 0}`,
      ];
    lines.push(
      "",
      "Safe interpretation:",
      "- Active bars reflect last reported persisted coordinator/worker runtime state, not a lifecycle command surface.",
      "- Stale or blocked bars should be cross-checked with Cluster Log, ActiveJobs, Run Logs, and Last Stderr before retries.",
      "Mutation guardrail: this panel does not start/stop workers, reclaim jobs, release claims, send done reports, mutate queue state, or touch media files."
    );
    return lines;
  }

  function renderNetworkWorkerProgress(networkWorkers) {
    const progress = networkWorkers?.worker_progress && typeof networkWorkers.worker_progress === "object"
      ? networkWorkers.worker_progress
      : { progress_bars: Array.isArray(networkWorkers?.progress_bars) ? networkWorkers.progress_bars : [] };
    const bars = Array.isArray(progress.progress_bars) ? progress.progress_bars : [];
    setText("network-worker-progress-status", networkWorkerProgressStatus(progress));
    if (typeof renderProgressBarsInto === "function") {
      renderProgressBarsInto("network-worker-progress-bars", bars, progress, "No last reported worker progress loaded.");
    } else {
      setText("network-worker-progress-bars", bars.length ? bars.map((bar) => `${bar.label || bar.id || "Worker"}: ${bar.status || "unknown"} ${bar.percent ?? ""}%`).join("\n") : "No last reported worker progress loaded.");
    }
    setText("network-worker-progress-summary", networkWorkerProgressSummaryLines(progress).join("\n"));
  }

  function renderNetworkWorkerRows(networkWorkers) {
    const rows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows : [];
    lastNetworkWorkerRows = rows;
    const visibleRows = filteredNetworkWorkerRows(rows);
    const tbody = byId("network-worker-rows");
    if (!tbody) return;
    renderNetworkWorkerFilterSummary(rows, visibleRows);
    if (!rows.length) {
      selectedNetworkWorkerKey = "";
      clearRows(tbody, 9, "No persisted worker rows. Inspect cluster.log, ActiveJobs, or state files before inferring worker lifecycle health.");
      updateTableStatusLegend("network-worker-table-legend", tbody, "Network worker rows");
      renderNetworkWorkerDetail(null);
      return;
    }
    setText(
      "network-worker-status",
      visibleRows.length === rows.length
        ? `${rows.length} worker row${rows.length === 1 ? "" : "s"}`
        : `${visibleRows.length}/${rows.length} worker rows`
    );
    const selectedVisible = visibleRows.some((item) => networkWorkerRowKey(item) === selectedNetworkWorkerKey);
    if (!selectedVisible) {
      selectedNetworkWorkerKey = visibleRows.length ? networkWorkerRowKey(visibleRows[0]) : "";
    }
    if (!visibleRows.length) {
      clearRows(tbody, 9, "No persisted worker rows match the current Network worker filters.");
      updateTableStatusLegend("network-worker-table-legend", tbody, "Network worker rows");
      renderNetworkWorkerDetail(null);
      return;
    }
    tbody.replaceChildren();
    visibleRows.forEach((item) => {
      const row = document.createElement("tr");
      const key = networkWorkerRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = networkWorkerStatusState(item);
      row.title = item.worker_id || item.current_file || "";
      appendCells(row, [
        item.worker_name || item.worker_id || "",
        item.status || "",
        item.current_file_name || item.current_file || "",
        workerProgressText(item),
        workerHeartbeatText(item),
        item.files_completed || "",
        item.total_gb_encoded || "",
        item.avg_speed_gbh || "",
        item.current_stage || "",
      ], [null, null, null, "num", "num", "num", "num", "num", null]);
      makeRowSelectable(row, () => selectNetworkWorkerRow(item), {
        selected: Boolean(key && key === selectedNetworkWorkerKey),
        label: `Network worker row ${item.worker_name || item.worker_id || item.current_file_name || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("network-worker-table-legend", tbody, "Network worker rows");
    renderNetworkWorkerDetail(getSelectedNetworkWorkerRow());
  }

  function initNetworkViewEvents() {
    if (networkViewEventsInitialized) return;
    networkViewEventsInitialized = true;
    const workerFilter = byId("network-worker-filter");
    if (workerFilter) {
      workerFilter.addEventListener("input", () => {
        networkWorkerSearchText = workerFilter.value || "";
        renderNetworkWorkerRows({ rows: lastNetworkWorkerRows });
      });
    }
    const statusFilter = byId("network-worker-status-filter");
    if (statusFilter) {
      statusFilter.addEventListener("change", () => {
        networkWorkerStatusFilter = statusFilter.value || "";
        renderNetworkWorkerRows({ rows: lastNetworkWorkerRows });
      });
    }
    const previewSettingsButton = byId("network-settings-preview-button");
    if (previewSettingsButton) previewSettingsButton.addEventListener("click", previewNetworkSettingsPatch);
    const saveSettingsButton = byId("network-settings-save-button");
    if (saveSettingsButton) saveSettingsButton.addEventListener("click", saveNetworkSettingsPatch);
  }

  function renderNetworkWorkers(networkWorkers) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const workerState = payload.worker_state && typeof payload.worker_state === "object" ? payload.worker_state : {};
    setText(
      "network-worker-status",
      payload.error
        ? "Unavailable"
        : `${rows.length} worker row${rows.length === 1 ? "" : "s"}`
    );
    const lines = [
      payload.error ? `Persisted worker state: unavailable (${payload.error})` : "Persisted worker state: loaded",
      `State source: ${payload.source || "runtime_state_files"}`,
      `Runtime evidence role: ${payload.role || "unknown"}`,
      `Last reported active workers: ${payload.active_count || 0}`,
      `Last reported idle workers: ${payload.idle_count || 0}`,
      `Session completed from persisted state: ${payload.session_completed || 0}`,
      `Session failed from persisted state: ${payload.session_failed || 0}`,
      `Coordinator state file: ${payload.coordinator_inflight_path || "not resolved"}`,
      `Worker state file: ${payload.worker_state_path || "not resolved"}`,
      `Cluster log file: ${payload.cluster_log_path || "not resolved"}`,
      ...networkStateFileCompactLines(payload.state_files || []),
      "Lifecycle controls remain backend-owned. This panel is read-only persisted state, not a live coordinator control surface.",
    ];
    if (workerState.job_id || workerState.source_file || workerState.pending_done_report) {
      lines.push(
        "",
        "Local worker state:",
        `- Job: ${workerState.job_id || "(none)"}`,
        `- File: ${workerState.source_file || "(none)"}`,
        `- Pending done report: ${workerState.pending_done_report ? "yes" : "no"}`
      );
    }
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 8).forEach((warning) => lines.push(`- ${warning}`));
    }
    setText("network-worker-summary", lines.join("\n"));
    renderNetworkWorkerProgress(payload);
    renderNetworkWorkerRows(payload);
  }

  function renderNetworkView(payload = {}) {
    initNetworkViewEvents();
    const settings = payload.settings || {};
    const contract = payload.contract || {};
    const config = settingsConfig(settings);
    const role = String(rawConfigValue(config, "NetworkRole", "standalone") || "standalone").toLowerCase();
    const pollInterval = displayConfigValue(config, "WorkerPollIntervalSecs", "not configured");
    const localApiState = contract?.schema_version ? "contract loaded" : "not loaded";
    const guidance = networkGuidance(role);

    setText("network-role", role || "standalone");
    setText("network-coordinator-target", coordinatorTarget(config));
    setText("network-worker-poll", pollInterval);
    setText("network-local-api", localApiState);
    setText("network-status", settings.error ? "Settings unavailable" : "Read-only");
    setText("network-summary", guidance.join("\n"));
    setText("network-mode-model", networkModeModelLines(role).join("\n"));
    setText("network-api-status", contract?.schema_version || "Not loaded");
    setText("network-api-summary", contractSummary(contract));
    renderNetworkReadiness(payload, role, config);
    renderNetworkLifecycleHandoff(payload, role, config);
    renderNetworkEvidenceChecklist(payload, role, config);
    renderNetworkStateFiles(payload.networkWorkers || {});
    renderNetworkSettingsRows(settings);
    renderNetworkSettingsPatchHandoff();
    renderNetworkWorkers(payload.networkWorkers || {});
    if (typeof getCommandHistory === "function") renderNetworkOpenHistory(getCommandHistory());
  }

  /**
   * Public namespace for the Workers page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineNetworkView = {
    networkRows,
    networkReadinessLines,
    networkLifecycleRows,
    networkLifecycleStatus,
    networkLifecycleSummaryLines,
    networkLifecycleDetailLines,
    renderNetworkLifecycleHandoff,
    networkEvidenceRows,
    networkEvidenceStatus,
    networkEvidenceSummaryLines,
    renderNetworkEvidenceChecklist,
    networkStateFileRows,
    networkStateFileStatus,
    networkStateFileSummaryLines,
    networkStateFileDetailLines,
    renderNetworkStateFiles,
    networkWorkerRowKey,
    networkWorkerFilterText,
    filteredNetworkWorkerRows,
    networkWorkerDetailLines,
    renderNetworkWorkerDetail,
    renderNetworkWorkerProgress,
    networkWorkerProgressStatus,
    networkWorkerProgressSummaryLines,
    selectNetworkWorkerRow,
    initNetworkViewEvents,
    renderNetworkWorkers,
    renderNetworkWorkerRows,
    networkOpenTargets,
    isNetworkOpenCommand,
    networkOpenHistoryLine,
    renderNetworkOpenHistory,
    renderNetworkSettingsPatchHandoff,
    previewNetworkSettingsPatch,
    saveNetworkSettingsPatch,
    renderNetworkView,
  };
  window.renderNetworkOpenHistory = renderNetworkOpenHistory;
  window.initNetworkViewEvents = initNetworkViewEvents;
})();
