(function () {
  const fallbackNetworkKeys = [
    ["Mode", "NetworkRole", "Network Role", "How this workstation participates in network processing."],
    ["Coordinator", "CoordinatorPort", "Listen Port", "TCP port for the coordinator HTTP API."],
    ["Coordinator", "CoordinatorBindAddress", "Bind Address", "Local interface used by the coordinator API."],
    ["Coordinator", "CoordinatorAlsoEncodeLocally", "Encode Locally", "Whether the coordinator also claims local work."],
    ["Coordinator", "CoordinatorHeartbeatTimeoutMins", "Heartbeat Timeout", "Minutes before stale worker jobs are reclaimed."],
    ["Coordinator", "CoordinatorMaxJobRetries", "Max Same-Reason Retries", "Repeated same-reason worker/source failures before the coordinator suppresses redispatch to that worker."],
    ["Coordinator", "WorkerConfigOverrides", "Worker Overrides", "Disabled by backend policy; retained only for config compatibility."],
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
  let lastNetworkLifecyclePayload = {};
  const networkTabStorageKey = "mediapipeline-network-tab";
  let activeNetworkTab = "";

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

  function isNetworkUrlSettingKey(key) {
    return String(key || "").toLowerCase().replace(/[^a-z0-9]+/g, "") === "workercoordinatorurl";
  }

  function redactedNetworkUrl(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    try {
      const parsed = new URL(text);
      parsed.username = "";
      parsed.password = "";
      parsed.search = "";
      parsed.hash = "";
      return parsed.toString().replace(/\/$/, "");
    } catch (_error) {
      const clipped = text.split(/[?#]/)[0].trim();
      return clipped || "present redacted";
    }
  }

  function displayConfigValue(config, key, fallback = "(not set)") {
    if (isNetworkSecretSettingKey(key)) return "(secret not displayed)";
    const value = rawConfigValue(config, key, "");
    if (isNetworkUrlSettingKey(key)) {
      return value === "" || value === undefined || value === null ? fallback : redactedNetworkUrl(value);
    }
    if (typeof configValue === "function") return configValue(config, key, fallback);
    if (value === "" || value === undefined || value === null) return fallback;
    return String(value);
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

  function networkCoordinatorConnectivity(networkWorkers) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    return payload.coordinator_connectivity && typeof payload.coordinator_connectivity === "object"
      ? payload.coordinator_connectivity
      : {};
  }

  function networkCoordinatorConnectivityLines(networkWorkers) {
    const connectivity = networkCoordinatorConnectivity(networkWorkers);
    return Array.isArray(connectivity.summary_lines)
      ? connectivity.summary_lines.map((line) => String(line || "").trim()).filter(Boolean)
      : [];
  }

  function networkCoordinatorBindEndpoint(config, networkWorkers) {
    const connectivity = networkCoordinatorConnectivity(networkWorkers);
    if (connectivity.bind_endpoint) return String(connectivity.bind_endpoint);
    const bind = displayConfigValue(config, "CoordinatorBindAddress", "0.0.0.0");
    const port = displayConfigValue(config, "CoordinatorPort", "7830");
    return `${bind}:${port}`;
  }

  function coordinatorTarget(config, networkWorkers, { raw = false } = {}) {
    const role = String(rawConfigValue(config, "NetworkRole", "") || "").toLowerCase();
    const connectivity = networkCoordinatorConnectivity(networkWorkers);
    if (role === "worker") {
      const savedTarget = rawConfigValue(config, "WorkerCoordinatorUrl", "");
      const target = savedTarget || connectivity.worker_coordinator_url || "not configured";
      return raw ? String(target) : redactedNetworkUrl(target);
    }
    if (connectivity.worker_coordinator_url) {
      return String(connectivity.worker_coordinator_url);
    }
    const bind = displayConfigValue(config, "CoordinatorBindAddress", "0.0.0.0");
    const port = displayConfigValue(config, "CoordinatorPort", "7830");
    return `${bind}:${port}`;
  }

  function visibleNetworkMode(config) {
    const role = String(rawConfigValue(config, "NetworkRole", "") || "").toLowerCase();
    const localEncode = rawConfigValue(config, "CoordinatorAlsoEncodeLocally", false);
    const localEnabled = localEncode === true;
    return role === "coordinator" && localEnabled ? "coordinator_local" : role;
  }

  function visibleNetworkModeLabel(config) {
    const mode = visibleNetworkMode(config);
    if (mode === "coordinator_local") return "Coordinator + local worker";
    if (mode === "coordinator") return "Coordinator only";
    if (mode === "worker") return "Worker only";
    if (mode === "standalone") return "Standalone";
    return `Unknown (${mode || "missing"})`;
  }

  function networkLifecycleStatePayload(networkWorkers) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    return payload.lifecycle_state && typeof payload.lifecycle_state === "object"
      ? payload.lifecycle_state
      : {};
  }

  function networkLifecycleStateFor(networkWorkers, role) {
    const state = networkLifecycleStatePayload(networkWorkers);
    const roleState = state[role] && typeof state[role] === "object" ? state[role] : {};
    return {
      role,
      status: String(roleState.status || "unknown").toLowerCase(),
      raw: roleState,
    };
  }

  function networkRuntimeStatus(networkWorkers, config) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const label = String(payload.runtime_status_label || "").trim();
    const severity = String(payload.runtime_status_severity || "").trim().toLowerCase();
    if (label) return { label, severity: severity || "unknown" };
    const mode = visibleNetworkMode(config);
    if (mode === "standalone") return { label: "Standalone", severity: "match" };
    const role = mode === "worker" ? "worker" : "coordinator";
    const state = networkLifecycleStateFor(networkWorkers, role);
    if (state.status === "running") return { label: "Running", severity: "match" };
    if (state.status === "stopped") return { label: "Stopped", severity: "match" };
    if (state.status === "blocked" || state.status === "failed" || state.status === "error") {
      return { label: "Blocked", severity: "blocked" };
    }
    return { label: state.status === "unknown" ? "Unknown" : state.status, severity: "warning" };
  }

  function networkTokenPostureLines(networkWorkers) {
    const posture = networkWorkers?.token_posture && typeof networkWorkers.token_posture === "object"
      ? networkWorkers.token_posture
      : {};
    if (Array.isArray(posture.summary_lines)) {
      return posture.summary_lines.map((line) => String(line || "").trim()).filter(Boolean);
    }
    return ["Coordinator token: unknown, hidden.", "Worker token: unknown, hidden."];
  }

  function networkDiagnosticLayers(networkWorkers) {
    const payload = networkWorkers?.diagnostic_layers;
    return payload && typeof payload === "object" ? payload : {};
  }

  function networkDiagnosticLayerLines(networkWorkers) {
    const diagnostic = networkDiagnosticLayers(networkWorkers);
    const layers = Array.isArray(diagnostic.layers) ? diagnostic.layers : [];
    if (layers.length) {
      return layers.map((layer) => `${layer.key || layer.label || "layer"}: ${layer.status || "unknown"} - ${layer.detail || ""}`);
    }
    return [
      `url_reachable: ${diagnostic.url_reachable || "unknown"}`,
      `auth_ok: ${diagnostic.auth_ok || "unknown"}`,
      `paths_ok: ${diagnostic.paths_ok || "unknown"}`,
      `queue_fresh: ${diagnostic.queue_fresh || "unknown"}`,
      `last_claim_result: ${diagnostic.last_claim_result || "unknown"}`,
    ];
  }

  function networkDiagnosticLayerPosture(networkWorkers) {
    const layers = Array.isArray(networkDiagnosticLayers(networkWorkers).layers)
      ? networkDiagnosticLayers(networkWorkers).layers
      : [];
    const statuses = layers.map((layer) => String(layer.status || "").toLowerCase());
    if (statuses.some((status) => status === "blocked")) return "blocked";
    if (statuses.some((status) => status === "review" || status === "warning")) return "review";
    if (statuses.length && statuses.every((status) => status === "ready" || status === "not_applicable")) return "ready";
    return "unknown";
  }

  function networkWorkerDriftPayload(networkWorkers) {
    const drift = networkWorkers?.running_vs_saved;
    return drift && typeof drift === "object" ? drift : {};
  }

  function networkWorkerDriftFieldText(drift) {
    const labels = Array.isArray(drift?.drift_field_labels) ? drift.drift_field_labels : [];
    const fields = Array.isArray(drift?.drift_fields) ? drift.drift_fields : [];
    const values = (labels.length ? labels : fields)
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return values.length ? values.join(", ") : "none";
  }

  function networkWorkerDriftStatusText(drift) {
    const status = String(drift?.status || "").trim().toLowerCase();
    if (status === "drift") return `Drift (${networkWorkerDriftFieldText(drift)})`;
    if (status === "match") return "Matches saved settings";
    if (status === "not_running") return "Worker not running";
    if (status === "unknown") return "Unknown";
    return status || "Not loaded";
  }

  function networkWorkerDriftSummaryLines(drift) {
    if (Array.isArray(drift?.summary_lines) && drift.summary_lines.length) {
      return drift.summary_lines.map((line) => String(line || "").trim()).filter(Boolean);
    }
    return [networkWorkerDriftStatusText(drift)];
  }

  function renderNetworkStatusBanner(payload = {}, config = {}) {
    const networkWorkers = payload.networkWorkers || {};
    const runtime = networkRuntimeStatus(networkWorkers, config);
    const drift = networkWorkerDriftPayload(networkWorkers);
    const driftActive = String(drift.status || "").toLowerCase() === "drift";
    const modeLabel = visibleNetworkModeLabel(config);
    const target = coordinatorTarget(config, networkWorkers);
    const mode = visibleNetworkMode(config);
    const launchReason = mode === "standalone"
      ? "Normal Launch available"
      : "Normal Launch blocked; use Network Lifecycle";
    const banner = byId("network-status-banner");
    if (banner) banner.dataset.status = driftActive ? "warning" : (runtime.severity || "unknown");
    setText("network-status-banner-title", `${modeLabel} - ${driftActive ? "Running settings drift" : runtime.label}`);
    setText(
      "network-status-banner-detail",
      driftActive
        ? `${launchReason}. Running worker differs from saved: ${networkWorkerDriftFieldText(drift)}.`
        : `${launchReason}. Coordinator target: ${target || "not configured"}.`
    );
    const summaryLines = Array.isArray(networkWorkers.operator_summary_lines)
      ? networkWorkers.operator_summary_lines.map((line) => String(line || "").trim()).filter(Boolean)
      : [
          `Mode: ${modeLabel}.`,
          `Runtime: ${runtime.label}.`,
          `${launchReason}.`,
          `Coordinator target: ${target || "not configured"}.`,
        ];
    if (driftActive && !summaryLines.some((line) => line.toLowerCase().includes("worker settings drift"))) {
      summaryLines.push(...networkWorkerDriftSummaryLines(drift));
    }
    setText("network-status-banner-lines", summaryLines.join("\n"));
  }

  function obviousWorkerCoordinatorUrlIssue(value, { required = true } = {}) {
    const text = String(value || "").trim();
    if (!text) return required ? "Worker coordinator URL is required in Worker mode." : "";
    let parsed;
    try {
      parsed = new URL(text);
    } catch (_error) {
      return "Worker coordinator URL must include http:// or https:// and a reachable coordinator host.";
    }
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return "Worker coordinator URL must start with http:// or https://.";
    }
    const host = String(parsed.hostname || "").replace(/^\[|\]$/g, "").toLowerCase();
    if (!host) return "Worker coordinator URL must include a coordinator host.";
    if (host === "0.0.0.0" || host === "::") {
      return "Use the coordinator machine name or LAN IP. 0.0.0.0 and :: are listen addresses, not worker targets.";
    }
    if (!parsed.port) {
      return "Worker coordinator URL must include the coordinator TCP port, for example http://coordinator-host:7830.";
    }
    const port = Number(parsed.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      return "Worker coordinator URL port must be in 1..65535.";
    }
    if (parsed.pathname && parsed.pathname !== "/") {
      return "Worker coordinator URL must be the coordinator base URL only, without a path.";
    }
    if (parsed.search || parsed.hash) {
      return "Worker coordinator URL must not include query strings or fragments.";
    }
    if (parsed.username || parsed.password) {
      return "Worker coordinator URL must not embed userinfo; use the shared worker token instead.";
    }
    return "";
  }

  function networkGuidance(role, networkWorkers) {
    if (role === "coordinator") {
      return [
        "Saved role: coordinator",
        ...networkCoordinatorConnectivityLines(networkWorkers).slice(0, 3),
        "Saved coordinator config is controlled from Saved Distributed Mode Settings on this tab.",
        "Runtime lifecycle commands must be started from Network Lifecycle controls, not normal Launch.",
        "Worker claim evidence is read from persisted worker state after the coordinator queue is populated.",
      ];
    }
    if (role === "worker") {
      return [
        "Saved role: worker",
        "This worker polls the configured coordinator URL and launches backend-owned single-file pipeline jobs.",
        "Worker URL, name, poll interval, and path map are controlled from Saved Distributed Mode Settings on this tab; worker config overrides are backend-disabled.",
        "Use Diagnostics to inspect RunLogs and ActiveJobs when worker claims fail or are reclaimed.",
      ];
    }
    return [
      `Saved role: ${role || "standalone"}`,
      "Standalone mode keeps all processing local to this workstation.",
      "Use Saved Distributed Mode Settings on this tab to stage role changes through backend settings Preview/Save.",
    ];
  }

  function networkModeModelLines(role) {
    return [
      `Current saved role: ${role || "standalone"}`,
      "Standalone: local queue work only on this workstation.",
      "Coordinator only: owns queue claims and worker registry state but does not process local files.",
      "Worker only: polls a coordinator and runs one claimed file at a time.",
      "Coordinator + local worker: coordinator mode with local worker processing enabled through Network lifecycle only.",
      "Runtime authority: backend routes own lifecycle commands; normal Launch is blocked in network modes.",
    ];
  }

  function renderNetworkSummaryRows(elementId, lines) {
    const target = document.getElementById(elementId);
    if (!target) return;
    target.textContent = "";
    const normalizedLines = (Array.isArray(lines) ? lines : [lines])
      .map((line) => String(line || "").trim())
      .filter(Boolean);
    const displayLines = normalizedLines.length ? normalizedLines : ["No network summary loaded."];
    displayLines.forEach((line) => {
      const row = document.createElement("div");
      row.className = "network-summary-row";
      row.setAttribute("role", "listitem");
      const separatorIndex = line.indexOf(":");
      if (separatorIndex > 0 && separatorIndex <= 36) {
        if (separatorIndex === line.length - 1) {
          const section = document.createElement("span");
          section.className = "network-summary-row-section";
          section.textContent = line;
          row.appendChild(section);
          target.appendChild(row);
          return;
        }
        const label = document.createElement("span");
        label.className = "network-summary-row-label";
        label.textContent = `${line.slice(0, separatorIndex)}: `;
        const value = document.createElement("span");
        value.className = "network-summary-row-value";
        value.textContent = line.slice(separatorIndex + 1).trim();
        row.append(label, value);
      } else {
        const body = document.createElement("span");
        body.className = "network-summary-row-body";
        body.textContent = line;
        row.appendChild(body);
      }
      target.appendChild(row);
    });
  }

  function networkTabIds() {
    return ["coordinator", "worker"];
  }

  function networkStoredTab() {
    try {
      return String(window.localStorage?.getItem(networkTabStorageKey) || "");
    } catch (_error) {
      return "";
    }
  }

  function networkDefaultTab(config) {
    return visibleNetworkMode(config) === "worker" ? "worker" : "coordinator";
  }

  function activateNetworkTab(tabId, options = {}) {
    const normalized = networkTabIds().includes(String(tabId || "")) ? String(tabId) : "coordinator";
    const persist = options.persist !== false;
    activeNetworkTab = normalized;
    document.querySelectorAll("[data-network-tab]").forEach((button) => {
      const selected = button.dataset.networkTab === normalized;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-selected", selected ? "true" : "false");
    });
    document.querySelectorAll("[data-network-tab-panel]").forEach((panel) => {
      const selected = panel.dataset.networkTabPanel === normalized;
      panel.classList.toggle("is-active", selected);
      panel.hidden = !selected;
    });
    if (persist) {
      try {
        window.localStorage?.setItem(networkTabStorageKey, normalized);
      } catch (_error) {
        // localStorage can be unavailable in some WebView test shells.
      }
    }
    if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
  }

  function syncNetworkTabs(config) {
    const fallback = networkDefaultTab(config);
    const stored = networkStoredTab();
    activateNetworkTab(networkTabIds().includes(stored) ? stored : fallback, { persist: Boolean(stored) });
  }

  function networkDisplayValue(value, fallback = "-") {
    if (value === undefined || value === null || value === "") return fallback;
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch (_error) {
        return fallback;
      }
    }
    return String(value);
  }

  function networkNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function networkNormalizePathKey(value) {
    return String(value || "")
      .trim()
      .replace(/\\/g, "/")
      .replace(/\/+/g, "/")
      .toLowerCase();
  }

  function networkBasename(value) {
    const normalized = String(value || "").trim().replace(/\\/g, "/");
    const parts = normalized.split("/").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : normalized;
  }

  function networkAddSourceKey(keys, value) {
    const normalized = networkNormalizePathKey(value);
    if (!normalized) return;
    keys.add(normalized);
    const leaf = networkNormalizePathKey(networkBasename(normalized));
    if (leaf) keys.add(leaf);
  }

  function networkSourceKeysFromRow(row) {
    const keys = new Set();
    if (!row || typeof row !== "object") return keys;
    [
      row.source_path,
      row.source_file,
      row.source,
      row.current_file,
      row.current_file_name,
      row.file,
      row.file_name,
      row.path,
      row.display_name,
      row.name,
      row.input_path,
      row.media_path,
    ].forEach((value) => networkAddSourceKey(keys, value));
    return keys;
  }

  function networkSourcePathKeysFromRow(row) {
    const keys = new Set();
    if (!row || typeof row !== "object") return keys;
    [
      row.source_path,
      row.source_file,
      row.source,
      row.current_file,
      row.path,
      row.input_path,
      row.media_path,
    ].forEach((value) => {
      const normalized = networkNormalizePathKey(value);
      if (normalized && normalized.includes("/")) keys.add(normalized);
    });
    return keys;
  }

  function networkQueueRows(queue) {
    if (Array.isArray(queue?.rows)) return queue.rows;
    if (Array.isArray(queue?.queue_rows)) return queue.queue_rows;
    if (Array.isArray(queue?.items)) return queue.items;
    return [];
  }

  function networkQueueMatchMaps(queueRows) {
    const byPath = new Map();
    (Array.isArray(queueRows) ? queueRows : []).forEach((row) => {
      networkSourcePathKeysFromRow(row).forEach((key) => {
        if (!key) return;
        if (!byPath.has(key)) byPath.set(key, row);
      });
    });
    return { byPath };
  }

  function networkMatchedQueueRow(row, maps) {
    if (!row || !maps) return null;
    const keys = Array.from(networkSourcePathKeysFromRow(row));
    for (const key of keys) {
      if (key.includes("/") && maps.byPath?.has(key)) return maps.byPath.get(key);
    }
    return null;
  }

  function networkQueueFileLabel(row) {
    return networkDisplayValue(
      row?.display_name || row?.current_file_name || row?.file_name || networkBasename(row?.source_path || row?.source_file || row?.current_file || row?.path || row?.name),
      "Unknown file"
    );
  }

  function networkRouteName(row) {
    const route = row?.route_name || row?.route || row?.route_action || row?.action || row?.decision || row?.operation;
    return String(route || "").trim();
  }

  function networkRouteLabel(row) {
    const route = networkRouteName(row);
    if (!route) return "";
    return route.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function networkRouteTone(row) {
    const route = networkRouteName(row).toLowerCase();
    if (route.includes("remux")) return "remux";
    if (route.includes("encode") || route.includes("transcode")) return "encode";
    if (route.includes("skip") || route.includes("copy")) return "skip";
    return "review";
  }

  function networkRouteEvidence(row) {
    return networkDisplayValue(row?.route_reason_code || row?.route_decision_summary || row?.reason || row?.decision_reason || row?.operator_status, "queue row");
  }

  function networkPriorityText(row) {
    if (row?.manifest_priority_level !== undefined && row.manifest_priority_level !== null && row.manifest_priority_level !== "") return String(row.manifest_priority_level);
    if (row?.priority !== undefined && row.priority !== null && row.priority !== "") return String(row.priority);
    if (row?.manual_order !== undefined && row.manual_order !== null && row.manual_order !== "") return `manual ${row.manual_order}`;
    if (row?.is_priority === true || row?.priority_flag === true) return "priority";
    return "normal";
  }

  function networkSizeText(row) {
    const gb = Number(row?.size_gb ?? row?.source_size_gb ?? row?.file_size_gb);
    if (Number.isFinite(gb) && gb > 0) return `${gb.toFixed(gb >= 10 ? 1 : 2)} GB`;
    const bytes = Number(row?.size_bytes ?? row?.source_size_bytes ?? row?.file_size_bytes);
    if (Number.isFinite(bytes) && bytes > 0) return `${(bytes / (1024 ** 3)).toFixed(2)} GB`;
    return "-";
  }

  function networkQueueOrder(row, index) {
    const value = row?.global_order ?? row?.queue_index ?? row?.order ?? row?.index;
    const numeric = Number(value);
    return Number.isFinite(numeric) && numeric > 0 ? Math.round(numeric) : index + 1;
  }

  function networkQueueStatus(queue, queueRows) {
    const status = String(queue?.produced_freshness_status || queue?.snapshot_file_freshness_status || queue?.freshness_status || queue?.status || "").trim();
    if (status) return status.charAt(0).toUpperCase() + status.slice(1);
    return queueRows.length ? "Loaded" : "Not loaded";
  }

  function networkClaimIsActive(row) {
    const state = networkWorkerStatusState(row);
    if (state === "warning" || state === "blocked") return true;
    if (!row || typeof row !== "object") return false;
    return Boolean(row.job_id || row.current_file || row.current_file_name || row.source_file || row.source_path);
  }

  function networkClaimedKeySet(networkWorkers) {
    const keys = new Set();
    const rows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows : [];
    rows.filter(networkClaimIsActive).forEach((row) => {
      networkSourcePathKeysFromRow(row).forEach((key) => keys.add(key));
    });
    const workerState = networkWorkers?.worker_state && typeof networkWorkers.worker_state === "object" ? networkWorkers.worker_state : {};
    if (workerState.job_id || workerState.source_file || workerState.source_path || workerState.current_file || workerState.pending_done_report) {
      networkSourcePathKeysFromRow(workerState).forEach((key) => keys.add(key));
    }
    return keys;
  }

  function networkQueueRowClaimed(row, claimedKeys) {
    for (const key of networkSourcePathKeysFromRow(row)) {
      if (claimedKeys.has(key)) return true;
    }
    return false;
  }

  function networkReviewTile(label, value, detail = "", tone = "") {
    return { label, value, detail, tone };
  }

  function networkCoordinatorOverviewModel({ queue, networkWorkers } = {}) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const queueRows = networkQueueRows(queue);
    const queueMaps = networkQueueMatchMaps(queueRows);
    const activeRows = rows.filter(networkClaimIsActive).map((row) => {
      const queueRow = networkMatchedQueueRow(row, queueMaps);
      return {
        row,
        worker: row.worker_name || row.worker_id || "worker",
        file: row.current_file_name || row.current_file || row.source_file || networkQueueFileLabel(queueRow || row),
        route: queueRow ? networkRouteLabel(queueRow) : "",
        routeTone: queueRow ? networkRouteTone(queueRow) : "warning",
        routeEvidence: queueRow ? networkRouteEvidence(queueRow) : "backend evidence missing",
        stage: row.current_stage || row.status || "unknown",
        progress: workerProgressText(row),
        heartbeat: workerHeartbeatText(row),
        status: networkWorkerStatusState(row) || "warning",
      };
    });
    const claimedKeys = networkClaimedKeySet(payload);
    const onDeckRows = queueRows
      .filter((row) => !networkQueueRowClaimed(row, claimedKeys))
      .map((row, index) => ({
        row,
        order: networkQueueOrder(row, index),
        file: networkQueueFileLabel(row),
        route: networkRouteLabel(row) || "Unknown",
        routeTone: networkRouteTone(row),
        priority: networkPriorityText(row),
        size: networkSizeText(row),
        evidence: networkRouteEvidence(row),
      }))
      .sort((left, right) => left.order - right.order)
      .slice(0, 10);
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const blockedCount = activeRows.filter((row) => row.status === "blocked").length;
    const issueCount = warnings.length + blockedCount;
    const runnableCount = networkNumber(queue?.runnable_count ?? queue?.queue_depth ?? queueRows.length, queueRows.length);
    const priorityCount = networkNumber(queue?.priority_count ?? queueRows.filter((row) => networkPriorityText(row).toLowerCase() !== "normal").length, 0);
    const status = blockedCount ? "Blocked review" : activeRows.length ? "Active" : onDeckRows.length ? "Queued" : issueCount ? "Review" : "Idle";
    return {
      status,
      activeRows,
      onDeckRows,
      tiles: [
        networkReviewTile("Active Claims", String(activeRows.length), `${blockedCount} need review`, blockedCount ? "blocked" : activeRows.length ? "warning" : "match"),
        networkReviewTile("Queue On Deck", String(onDeckRows.length), `${runnableCount} runnable in queue payload`, onDeckRows.length ? "warning" : "match"),
        networkReviewTile("Priority", String(priorityCount), "from queue evidence", priorityCount ? "warning" : "match"),
        networkReviewTile("Session Done", String(payload.session_completed || 0), `${payload.session_failed || 0} failed`, payload.session_failed ? "blocked" : "match"),
        networkReviewTile("Freshness", networkQueueStatus(queue, queueRows), "queue and state-file evidence", String(networkQueueStatus(queue, queueRows)).toLowerCase().includes("stale") ? "warning" : "match"),
        networkReviewTile("Issues", String(issueCount), "worker warnings or blocked claims", issueCount ? "blocked" : "match"),
      ],
      summaryLines: [
        "Coordinator overview:",
        `Active claimed work: ${activeRows.length}; blocked=${blockedCount}; worker warnings=${warnings.length}.`,
        `Queue on deck: ${onDeckRows.length}; total queue rows=${queueRows.length}; runnable=${runnableCount}; priority=${priorityCount}.`,
        `Session completed/failed: ${payload.session_completed || 0}/${payload.session_failed || 0}.`,
        `State freshness: workers=${payload.source || "runtime_state_files"}; queue=${networkQueueStatus(queue, queueRows)}.`,
        "Mutation guardrail: this dashboard reads queue and worker evidence only; it cannot claim, reclaim, release, retry, drain, publish, rename, save settings, or touch media files.",
      ],
    };
  }

  function networkLifecycleRouteSummary(contract, role) {
    if (!role) return "not applicable";
    const dryRunReady = ["start", "stop"].every((action) => networkLifecycleRouteAvailable(contract, role, action, true));
    const confirmedReady = ["start", "stop"].every((action) => networkLifecycleRouteAvailable(contract, role, action, false));
    if (dryRunReady && confirmedReady) return "dry-run and confirmed routes available";
    if (dryRunReady) return "dry-run routes available";
    return "routes missing";
  }

  function networkWorkerCurrentFile(workerState) {
    return workerState?.source_file || workerState?.source_path || workerState?.current_file || workerState?.current_file_name || "";
  }

  function networkWorkerOverviewModel({ config, contract, networkWorkers, queue } = {}) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const workerState = payload.worker_state && typeof payload.worker_state === "object" ? payload.worker_state : {};
    const progress = payload.worker_progress && typeof payload.worker_progress === "object" ? payload.worker_progress : {};
    const drift = networkWorkerDriftPayload(payload);
    const driftActive = String(drift.status || "").toLowerCase() === "drift";
    const queueMaps = networkQueueMatchMaps(networkQueueRows(queue));
    const routeRow = networkMatchedQueueRow(workerState, queueMaps);
    const currentFile = networkWorkerCurrentFile(workerState);
    const pendingDone = Boolean(workerState.pending_done_report);
    const hasClaim = Boolean(workerState.job_id || currentFile || pendingDone);
    const role = String(rawConfigValue(config, "NetworkRole", "standalone") || "standalone").toLowerCase();
    const routeStatus = networkLifecycleRouteSummary(contract || {}, role === "coordinator" ? "coordinator" : "worker");
    const blockedProgress = String(progress.status || "").toLowerCase().includes("block") || pendingDone;
    const status = pendingDone ? "Pending done report" : blockedProgress ? "Blocked review" : hasClaim ? "Active" : role === "worker" ? "Idle" : "Coordinator view";
    const stateFiles = Array.isArray(payload.state_files) ? payload.state_files : [];
    const presentFiles = stateFiles.filter((item) => networkStateFileStatus(item) === "match").length;
    const problemFiles = stateFiles.filter((item) => networkStateFileStatus(item) !== "match").length;
    const claimRows = [
      ["Worker role", visibleNetworkModeLabel(config)],
      ["Worker coordinator URL", coordinatorTarget(config, payload)],
      ["Running vs saved", networkWorkerDriftStatusText(drift)],
      ["Drift fields", networkWorkerDriftFieldText(drift)],
      ["Poll interval", `${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")} second(s)`],
      ["Lifecycle routes", routeStatus],
      ["Current job", workerState.job_id || "(none)"],
      ["Current file", currentFile ? networkBasename(currentFile) : "(none)"],
      ["Route", routeRow ? networkRouteLabel(routeRow) : "unknown/backend evidence missing"],
      ["Route evidence", routeRow ? networkRouteEvidence(routeRow) : "no normalized queue-row match"],
      ["Progress", progress.status ? `${networkWorkerProgressStatus(progress)}; active=${progress.active_count || 0}; blocked=${progress.blocked_count || 0}` : "not loaded"],
      ["Pending done report", pendingDone ? "yes" : "no"],
      ["Worker state file", payload.worker_state_path || "not resolved"],
    ];
    return {
      status,
      claimRows,
      routeRow,
      pendingDone,
      tiles: [
        networkReviewTile("Local Claim", hasClaim ? "Active" : "Idle", currentFile ? networkBasename(currentFile) : "no local claim", pendingDone ? "blocked" : hasClaim ? "warning" : "match"),
        networkReviewTile("Pending Done", pendingDone ? "Yes" : "No", "from worker_state", pendingDone ? "blocked" : "match"),
        networkReviewTile("Coordinator", coordinatorTarget(config, payload), "backend/saved target evidence", role === "worker" ? "warning" : "match"),
        networkReviewTile("Settings Drift", driftActive ? "Drift" : "OK", networkWorkerDriftFieldText(drift), driftActive ? "warning" : "match"),
        networkReviewTile("Poll", `${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")}s`, "saved worker interval", "match"),
        networkReviewTile("Lifecycle", routeStatus, "contract evidence", routeStatus.includes("missing") ? "warning" : "match"),
        networkReviewTile("State Files", `${presentFiles}/${stateFiles.length}`, problemFiles ? `${problemFiles} review` : "present", problemFiles ? "warning" : "match"),
      ],
      summaryLines: [
        "Worker overview:",
        `Local claim: ${hasClaim ? "present" : "none"}; pending done report=${pendingDone ? "yes" : "no"}; file=${currentFile ? networkBasename(currentFile) : "none"}.`,
        `Worker coordinator URL: ${coordinatorTarget(config, payload)}; poll interval=${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")} second(s).`,
        `Running vs saved: ${networkWorkerDriftStatusText(drift)}.`,
        `Lifecycle route status: ${routeStatus}; state-file evidence=${presentFiles}/${stateFiles.length} present.`,
        "Remote coordinator queue: Phase 2. Worker-side full coordinator queue visibility requires a read-only backend coordinator queue contract and is not inferred by this WebView.",
        "Mutation guardrail: this dashboard does not start/stop workers, send done reports, mutate queue state, rewrite state files, or touch media files.",
      ],
      remoteQueueSummary: [
        "Phase 2 placeholder:",
        "Remote coordinator queue rows are intentionally not displayed from worker mode in Phase 1.",
        "Requirement: add a backend-owned, read-only coordinator queue reporting contract before the worker tab can show remote queued files.",
        "Current evidence: local worker_state, worker_progress, saved coordinator target, lifecycle contract, and state-file metadata only.",
      ].join("\n"),
    };
  }

  function renderOverviewTiles(elementId, tiles) {
    const target = byId(elementId);
    if (!target) return;
    target.replaceChildren();
    (Array.isArray(tiles) ? tiles : []).forEach((tile) => {
      const item = document.createElement("div");
      item.className = "review-tile";
      if (tile.tone) item.dataset.tone = networkTileTone(tile.tone);
      const label = document.createElement("span");
      label.className = "review-tile-label";
      label.textContent = tile.label || "";
      const value = document.createElement("strong");
      value.className = "review-tile-value";
      value.textContent = tile.value || "";
      const detail = document.createElement("span");
      detail.className = "review-tile-detail";
      detail.textContent = tile.detail || "";
      item.append(label, value, detail);
      target.appendChild(item);
    });
  }

  function networkTileTone(tone) {
    const value = String(tone || "").toLowerCase();
    if (value === "blocked" || value === "failed" || value === "danger") return "danger";
    if (value === "warning" || value === "review" || value === "active") return "warning";
    if (value === "match" || value === "ready" || value === "success") return "success";
    if (value === "info") return "info";
    return "muted";
  }

  function networkStatusChip(text, state = "") {
    const chip = document.createElement("span");
    chip.className = "status-chip";
    chip.textContent = text || "-";
    if (state) chip.dataset.status = state;
    return chip;
  }

  function networkRouteChip(text, state = "") {
    const chip = document.createElement("span");
    chip.className = "route-chip";
    chip.textContent = text || "Unknown";
    if (state) chip.dataset.route = state;
    return chip;
  }

  function networkAppendCell(row, content, className = "") {
    const cell = document.createElement("td");
    if (className) cell.className = className;
    if (content instanceof Node) {
      cell.appendChild(content);
    } else {
      cell.textContent = content === undefined || content === null ? "" : String(content);
    }
    row.appendChild(cell);
    return cell;
  }

  function renderCoordinatorActiveRows(model) {
    const tbody = byId("network-coordinator-active-rows");
    if (!tbody) return;
    setText("network-coordinator-active-status", model.activeRows.length ? `${model.activeRows.length} active` : "No active claims");
    if (!model.activeRows.length) {
      clearRows(tbody, 6, "No active claimed worker files are visible in the loaded persisted state.");
      return;
    }
    tbody.replaceChildren();
    model.activeRows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.status;
      networkAppendCell(row, item.worker);
      networkAppendCell(row, item.file, "network-overview-table-file");
      if (item.route) {
        networkAppendCell(row, networkRouteChip(item.route, item.routeTone));
      } else {
        const missing = document.createElement("span");
        missing.className = "network-overview-route-missing";
        missing.textContent = "unknown/backend evidence missing";
        missing.title = "No normalized queue-row match exists for this active worker claim.";
        networkAppendCell(row, missing);
      }
      networkAppendCell(row, networkStatusChip(item.stage, item.status));
      networkAppendCell(row, item.progress, "num");
      networkAppendCell(row, item.heartbeat, "num");
      tbody.appendChild(row);
    });
  }

  function renderCoordinatorQueueRows(model) {
    const tbody = byId("network-coordinator-queue-rows");
    if (!tbody) return;
    setText("network-coordinator-queue-status", model.onDeckRows.length ? `${model.onDeckRows.length} on deck` : "No on-deck rows");
    if (!model.onDeckRows.length) {
      clearRows(tbody, 6, "No unclaimed queue/on-deck files are visible in the loaded queue payload.");
      return;
    }
    tbody.replaceChildren();
    model.onDeckRows.forEach((item) => {
      const row = document.createElement("tr");
      networkAppendCell(row, item.order, "num");
      networkAppendCell(row, item.file, "network-overview-table-file");
      networkAppendCell(row, networkRouteChip(item.route, item.routeTone));
      networkAppendCell(row, item.priority);
      networkAppendCell(row, item.size, "num");
      networkAppendCell(row, item.evidence);
      tbody.appendChild(row);
    });
  }

  function renderWorkerClaimRows(model) {
    const tbody = byId("network-worker-claim-rows");
    if (!tbody) return;
    setText("network-worker-claim-status", model.pendingDone ? "Pending done report" : model.status);
    tbody.replaceChildren();
    model.claimRows.forEach(([field, evidence]) => {
      const row = document.createElement("tr");
      networkAppendCell(row, field);
      networkAppendCell(row, evidence);
      tbody.appendChild(row);
    });
  }

  function renderNetworkRoleDashboards({ queue, networkWorkers, config, contract } = {}) {
    const coordinatorModel = networkCoordinatorOverviewModel({ queue, networkWorkers });
    setText("network-coordinator-overview-status", coordinatorModel.status);
    setText("network-coordinator-overview-summary", coordinatorModel.summaryLines.join("\n"));
    renderOverviewTiles("network-coordinator-overview-tiles", coordinatorModel.tiles);
    renderCoordinatorActiveRows(coordinatorModel);
    renderCoordinatorQueueRows(coordinatorModel);

    const workerModel = networkWorkerOverviewModel({ config: config || {}, contract: contract || {}, networkWorkers, queue });
    setText("network-worker-overview-status", workerModel.status);
    setText("network-worker-overview-summary", workerModel.summaryLines.join("\n"));
    setText("network-worker-remote-queue-status", "Phase 2");
    setText("network-worker-remote-queue-summary", workerModel.remoteQueueSummary);
    renderOverviewTiles("network-worker-overview-tiles", workerModel.tiles);
    renderWorkerClaimRows(workerModel);
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
      `Network lifecycle command contract: ${summary.status || "backend_lifecycle_routes_available_provider_guarded"}`,
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
      return path.startsWith(networkRoutePrefix) && method === "POST" && effect !== "none";
    }).length;
  }

  function networkLifecycleRouteRow(contract, role, action, dryRun) {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    return routes.find((route) => {
      const lifecycle = route?.network_lifecycle || {};
      return String(route?.method || "").toUpperCase() === "POST"
        && String(lifecycle.role || "") === role
        && String(lifecycle.action || "") === action
        && Boolean(lifecycle.dry_run) === Boolean(dryRun);
    }) || null;
  }

  function networkLifecycleBoundaryStatus({ closeReadiness, contract } = {}) {
    if (!contract?.schema_version) return "Not loaded";
    const unsafeClose = closeReadiness && typeof closeReadiness === "object" && closeReadiness.safe_to_close === false;
    if (unsafeClose) return "Blocked by active work";
    return networkLifecycleMutationRouteCount(contract) ? "Backend lifecycle routes" : "Read-only boundary";
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
      `Lifecycle contracts: ${networkLifecycleContracts(contract).length}; frontend allowed=${lifecycleSummary.frontend_allowed ? "yes" : "no"}.`,
      unsafeClose
        ? "Safe next step: leave network role/settings and lifecycle planning unchanged until close-readiness is safe."
        : "Safe next step: run the backend dry-run route before any confirmed network lifecycle command.",
    ];
  }

  function networkRouteSummaryStatus(contract) {
    if (!contract?.schema_version) return "Not loaded";
    const workerRouteLoaded = routeExists(contract, "/api/network/workers", "GET");
    const mutationRoutes = networkLifecycleMutationRouteCount(contract);
    if (workerRouteLoaded && mutationRoutes > 0) return "Lifecycle routes";
    if (workerRouteLoaded && mutationRoutes === 0) return "Read-only route";
    return "Review";
  }

  function networkRouteSummaryLines(contract) {
    const workerRouteLoaded = routeExists(contract, "/api/network/workers", "GET");
    const lifecycleContracts = networkLifecycleContracts(contract);
    const lifecycleSummary = contract?.network_lifecycle_summary || {};
    const testConnectionRoute = networkWorkerTestConnectionRoute(contract);
    const discoveryRoute = networkWorkerDiscoverCoordinatorsRoute(contract);
    const joinBlobRoute = networkCoordinatorJoinBlobRoute(contract);
    const joinClusterRoute = networkWorkerJoinClusterRoute(contract);
    return [
      `Workers evidence route: ${workerRouteLoaded ? "GET /api/network/workers available with effect=none" : "GET /api/network/workers missing or not loaded"}.`,
      `Worker test-connection route: ${testConnectionRoute ? "available with effect=none" : "missing or not loaded"}.`,
      `Worker mDNS discovery route: ${discoveryRoute ? "available with effect=none" : "missing or not loaded"}.`,
      `Coordinator join blob route: ${joinBlobRoute ? "available and unjournaled" : "missing or not loaded"}.`,
      `Worker join cluster route: ${joinClusterRoute ? "available and unjournaled" : "missing or not loaded"}.`,
      `Lifecycle mutation routes: ${networkLifecycleMutationRouteCount(contract) ? "present" : "absent"}.`,
      `Lifecycle contract posture: ${lifecycleContracts.length ? "published lifecycle contracts" : "not published"}; mutation enabled=${lifecycleSummary.mutation_enabled ? "yes" : "no"}.`,
      "Deep API contract detail remains in Advanced and Diagnostics/Contract surfaces.",
    ];
  }

  function networkLifecycleRoutePath(contract, role, action, dryRun) {
    const row = networkLifecycleRouteRow(contract, role, action, dryRun);
    return row ? String(row.path || "") : "";
  }

  function networkLifecycleRouteAvailable(contract, role, action, dryRun) {
    const row = networkLifecycleRouteRow(contract, role, action, dryRun);
    return Boolean(row?.path);
  }

  function networkWorkerTestConnectionRoute(contract) {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    const row = routes.find((item) => (
      String(item?.method || "").toUpperCase() === "POST"
      && item?.data_schema === "desktop_network_worker_test_connection.v1"
      && item?.effect === "none"
      && item?.frontend_exposed === true
    ));
    return row ? String(row.path || "") : "";
  }

  function networkCommandRouteByDataSchema(contract, dataSchema) {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    const row = routes.find((item) => (
      String(item?.method || "").toUpperCase() === "POST"
      && item?.data_schema === dataSchema
      && item?.frontend_exposed === true
    ));
    return row ? String(row.path || "") : "";
  }

  function networkCoordinatorJoinBlobRoute(contract) {
    return networkCommandRouteByDataSchema(contract, "desktop_network_join_blob_result.v1");
  }

  function networkWorkerJoinClusterRoute(contract) {
    return networkCommandRouteByDataSchema(contract, "desktop_network_join_import_result.v1");
  }

  function networkWorkerDiscoverCoordinatorsRoute(contract) {
    return networkCommandRouteByDataSchema(contract, "desktop_network_coordinator_discovery.v1");
  }

  function networkLifecycleRelevantRole(config) {
    const mode = visibleNetworkMode(config);
    if (mode === "coordinator" || mode === "coordinator_local") return "coordinator";
    if (mode === "worker") return "worker";
    return "";
  }

  function networkLifecycleControlLines(payload = {}, config = {}) {
    const contract = payload.contract || {};
    const networkWorkers = payload.networkWorkers || {};
    const relevantRole = networkLifecycleRelevantRole(config);
    const modeLabel = visibleNetworkModeLabel(config);
    const runtime = networkRuntimeStatus(networkWorkers, config);
    if (!relevantRole) {
      return [
        `Mode: ${modeLabel}`,
        `Runtime: ${runtime.label}`,
        "Network lifecycle is inactive in Standalone mode.",
        "Normal Launch is available only in Standalone mode.",
      ];
    }
    const roleState = networkLifecycleStateFor(networkWorkers, relevantRole);
    const workerUrlIssue = relevantRole === "worker"
      ? obviousWorkerCoordinatorUrlIssue(coordinatorTarget(config, networkWorkers, { raw: true }), { required: true })
      : "";
    const routeLines = ["start", "stop"].flatMap((action) => [
      `${relevantRole} ${action} dry-run route: ${networkLifecycleRouteAvailable(contract, relevantRole, action, true) ? "available" : "missing"}`,
      `${relevantRole} ${action} route: ${networkLifecycleRouteAvailable(contract, relevantRole, action, false) ? "available" : "missing"}`,
    ]);
    const lines = [
      `Mode: ${modeLabel}`,
      `Runtime: ${runtime.label}; lifecycle state=${roleState.status}.`,
      "Normal Launch is blocked in this network mode; use these backend lifecycle controls.",
      "Dry-runs check backend preconditions only: effect=none.",
      "Dry-run no-touch rule: No files, queue, scratch, output, pending publish, or lifecycle state changed.",
      "Confirmed start/stop commands require backend confirmation fields and command-journal records.",
      ...routeLines,
      ...networkTokenPostureLines(networkWorkers),
      "Drain, Disable New Work, Pause, Abort Current, Reclaim Job, and Quarantine Worker remain disabled until backend routes exist.",
    ];
    if (workerUrlIssue) lines.splice(3, 0, `Worker URL blocked: ${workerUrlIssue}`);
    return lines;
  }

  function renderNetworkJoinControls(payload = {}, config = {}) {
    const contract = payload.contract || {};
    const networkWorkers = payload.networkWorkers || {};
    const coordinatorRoute = networkCoordinatorJoinBlobRoute(contract);
    const workerRoute = networkWorkerJoinClusterRoute(contract);
    const discoveryRoute = networkWorkerDiscoverCoordinatorsRoute(contract);
    const coordinatorUrlInput = byId("network-coordinator-join-url");
    const coordinatorButton = byId("network-coordinator-join-create");
    const copyButton = byId("network-coordinator-join-copy");
    const workerBlob = byId("network-worker-join-blob");
    const workerButton = byId("network-worker-join-import");
    const discoverButton = byId("network-worker-discover");
    const target = coordinatorTarget(config, networkWorkers, { raw: true });
    if (coordinatorUrlInput && !coordinatorUrlInput.value) {
      coordinatorUrlInput.placeholder = target || "http://coordinator-host:7830";
    }
    if (coordinatorButton) {
      coordinatorButton.disabled = !coordinatorRoute;
      coordinatorButton.title = coordinatorRoute
        ? "Create an unjournaled backend join blob response for worker setup."
        : "Backend coordinator join blob route is not available in the loaded contract.";
    }
    if (copyButton) {
      const hasBlob = Boolean(String(byId("network-coordinator-join-output")?.value || "").trim());
      copyButton.disabled = !hasBlob;
      copyButton.title = hasBlob ? "Copy the current join blob." : "Create a join blob before copying.";
    }
    if (workerButton) {
      workerButton.disabled = !workerRoute || !String(workerBlob?.value || "").trim();
      workerButton.title = workerRoute
        ? "Import a join blob through backend settings save and test connection."
        : "Backend worker join cluster route is not available in the loaded contract.";
    }
    if (discoverButton) {
      discoverButton.disabled = !discoveryRoute;
      discoverButton.title = discoveryRoute
        ? "Scan the LAN for mDNS-advertised coordinators through the backend."
        : "Backend worker mDNS discovery route is not available in the loaded contract.";
    }
    const coordinatorStatus = byId("network-coordinator-join-status");
    if (coordinatorStatus && coordinatorStatus.textContent === "Not loaded") {
      coordinatorStatus.textContent = coordinatorRoute ? "Route ready" : "Route missing";
    }
    const workerStatus = byId("network-worker-join-status");
    if (workerStatus && workerStatus.textContent === "Not loaded") {
      workerStatus.textContent = workerRoute ? "Route ready" : "Route missing";
    }
    const discoveryStatus = byId("network-worker-discovery-status");
    if (discoveryStatus && discoveryStatus.textContent === "Not loaded") {
      discoveryStatus.textContent = discoveryRoute ? "Route ready" : "Route missing";
    }
  }

  function renderNetworkLifecycleControls(payload = {}, role = "standalone", config = {}) {
    lastNetworkLifecyclePayload = payload && typeof payload === "object" ? payload : {};
    const contract = payload.contract || {};
    const networkWorkers = payload.networkWorkers || {};
    const relevantRole = networkLifecycleRelevantRole(config);
    const modeLabel = visibleNetworkModeLabel(config);
    const runtime = networkRuntimeStatus(networkWorkers, config);
    const roleState = relevantRole ? networkLifecycleStateFor(networkWorkers, relevantRole) : { status: "standalone" };
    const workerUrlIssue = relevantRole === "worker"
      ? obviousWorkerCoordinatorUrlIssue(coordinatorTarget(config, networkWorkers, { raw: true }), { required: true })
      : "";
    document.querySelectorAll("[data-network-lifecycle-role]").forEach((button) => {
      const buttonRole = button.dataset.networkLifecycleRole || "";
      const action = button.dataset.networkLifecycleAction || "";
      const dryRun = button.dataset.networkLifecycleDryRun === "true";
      const roleApplies = buttonRole === relevantRole;
      const routeAvailable = networkLifecycleRouteAvailable(contract, buttonRole, action, dryRun);
      const stateAllowsConfirmed = dryRun
        ? true
        : runtime.severity === "blocked"
          ? false
          : action === "start"
            ? roleState.status === "stopped"
            : roleState.status === "running";
      const urlAllows = !workerUrlIssue || buttonRole !== "worker";
      const available = roleApplies && routeAvailable && urlAllows && stateAllowsConfirmed;
      button.hidden = !roleApplies;
      button.disabled = !available;
      if (available) {
        button.title = dryRun
          ? `${modeLabel}: check ${buttonRole} ${action}; effect=none.`
          : action === "stop"
            ? `${modeLabel}: stop through backend lifecycle route. Stopping may abort active worker work.`
            : `${modeLabel}: start through backend lifecycle route.`;
      } else if (!roleApplies) {
        button.title = "This lifecycle control does not apply to the saved network mode.";
      } else if (!routeAvailable) {
        button.title = "Backend lifecycle route is not available in the loaded contract.";
      } else if (!urlAllows) {
        button.title = workerUrlIssue;
      } else {
        button.title = action === "start"
          ? `Start is available only while ${buttonRole} lifecycle state is stopped.`
          : `Stop is available only while ${buttonRole} lifecycle state is running.`;
      }
    });
    document.querySelectorAll("[data-network-future-control]").forEach((button) => {
      button.disabled = true;
      button.title = "Backend route not implemented yet.";
    });
    document.querySelectorAll("[data-network-test-connection]").forEach((button) => {
      const routeAvailable = Boolean(networkWorkerTestConnectionRoute(contract));
      const roleApplies = relevantRole === "worker";
      button.hidden = !roleApplies;
      button.disabled = !roleApplies || !routeAvailable;
      button.title = routeAvailable
        ? "Run backend-owned read-only TCP/auth/path preflight for this worker."
        : "Backend worker test-connection route is not available in the loaded contract.";
    });
    setText(
      "network-lifecycle-control-status",
      relevantRole ? runtime.label : "Standalone"
    );
    setText("network-lifecycle-control-summary", networkLifecycleControlLines(payload, config).join("\n"));
    renderNetworkJoinControls(payload, config);
  }

  function networkLifecycleCommandResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const preconditions = Array.isArray(data.precondition_results) ? data.precondition_results : [];
    const blocked = preconditions.filter((row) => String(row?.status || "").toLowerCase() === "blocked");
    const passed = preconditions.filter((row) => String(row?.status || "").toLowerCase() === "pass");
    const isDryRun = data.dry_run_only === true;
    const lines = isDryRun
      ? [
          "Check complete. This was a dry-run only.",
          "Effect: none.",
          "No files, queue, scratch, output, pending publish, or lifecycle state changed.",
        ]
      : [
          result?.ok
            ? "Confirmed command completed. Backend command journal evidence was required before runtime state changed."
            : "Confirmed command was blocked or failed. No fallback to normal Launch was attempted.",
        ];
    lines.push(
      `Command: ${result?.command || "network lifecycle"}`,
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
    );
    if (typeof data.safe_to_apply === "boolean") lines.push(`Safe to apply: ${data.safe_to_apply ? "yes" : "no"}`);
    if (data.effect) lines.push(`Backend effect: ${data.effect}`);
    if (data.schema_version) lines.push(`Data schema: ${data.schema_version}`);
    if (data.command_id) lines.push(`Command ID: ${data.command_id}`);
    if (passed.length) {
      lines.push("", "Passed preconditions:");
      passed.slice(0, 8).forEach((row) => lines.push(`- ${row.key || "precondition"}: ${row.evidence || ""}`));
    }
    if (blocked.length) {
      lines.push("", "Blocked preconditions:");
      blocked.slice(0, 8).forEach((row) => lines.push(`- ${row.key || "precondition"}: ${row.evidence || ""}`));
    }
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    const noTouch = data.would_not_touch && typeof data.would_not_touch === "object" ? data.would_not_touch : {};
    const noTouchKeys = Object.keys(noTouch);
    if (noTouchKeys.length) {
      lines.push("", "Would not touch:");
      noTouchKeys.slice(0, 8).forEach((key) => lines.push(`- ${key}: ${noTouch[key]}`));
    }
    const redactedConfig = data.redacted_config_evidence && typeof data.redacted_config_evidence === "object"
      ? data.redacted_config_evidence
      : {};
    const configKeys = Object.keys(redactedConfig);
    if (configKeys.length) {
      lines.push("", "Redacted config evidence:");
      configKeys.slice(0, 10).forEach((key) => {
        const normalized = String(key).toLowerCase();
        const label = normalized.includes("authtoken")
          ? normalized.includes("worker") ? "Worker token" : "Coordinator token"
          : key;
        const rawValue = redactedConfig[key];
        const value = normalized.includes("authtoken")
          ? String(rawValue || "").replace("present_redacted", "present, hidden").replace("will_generate_on_start", "blank; coordinator can generate").replace("missing", "missing")
          : rawValue;
        lines.push(`- ${label}: ${value}`);
      });
    }
    if (data.state_before || data.state_after) {
      lines.push("", "Lifecycle state:");
      if (data.state_before) lines.push(`- Before: ${JSON.stringify(data.state_before)}`);
      if (data.state_after) lines.push(`- After: ${JSON.stringify(data.state_after)}`);
    }
    lines.push(
      "",
      result?.ok
        ? "Next action: refresh Network status and verify worker heartbeat/claim evidence before changing roles or running another lifecycle command."
        : "Next action: fix blocked preconditions, run the dry-run again, then use confirmed controls only when the backend reports safe_to_apply."
    );
    return lines;
  }

  function networkTestConnectionResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const layers = data.layers && typeof data.layers === "object" ? data.layers : {};
    const lines = [
      "Worker test-connection complete.",
      "Effect: none.",
      "No files, queue, scratch, output, pending publish, lifecycle state, or media policy changed.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Coordinator URL: ${data.coordinator_url || "not configured"}`,
      `Data schema: ${data.schema_version || "unknown"}`,
    ];
    ["l1_tcp", "l2_auth", "l3_paths"].forEach((key) => {
      const layer = layers[key] && typeof layers[key] === "object" ? layers[key] : {};
      if (!Object.keys(layer).length) return;
      lines.push(
        "",
        `${layer.label || key}: ${layer.status || "unknown"}`,
        `- Detail: ${layer.detail || "(none)"}`
      );
      if (layer.status_code) lines.push(`- HTTP status: ${layer.status_code}`);
      if (key === "l3_paths" && Array.isArray(layer.paths)) {
        lines.push("- Paths:");
        layer.paths.slice(0, 12).forEach((row) => {
          lines.push(`  - ${row.library_id || "library"} ${row.path_kind || "path"}: ${row.status || "unknown"} (${row.path || ""})`);
        });
      }
    });
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Blocked layer(s):");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    const noTouch = data.would_not_touch && typeof data.would_not_touch === "object" ? data.would_not_touch : {};
    const keys = Object.keys(noTouch);
    if (keys.length) {
      lines.push("", "Would not touch:");
      keys.slice(0, 10).forEach((key) => lines.push(`- ${key}: ${noTouch[key]}`));
    }
    lines.push(
      "",
      result?.ok
        ? "Next action: start or restart worker polling only after the Network status still matches saved settings."
        : "Next action: fix the failed TCP, auth, or path layer, then run Test worker connection again before starting worker polling."
    );
    return lines;
  }

  function networkCoordinatorDiscoveryResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const coordinators = Array.isArray(data.coordinators) ? data.coordinators : [];
    const lines = [
      "mDNS coordinator discovery complete.",
      "Effect: none.",
      "No files, queue, scratch, output, pending publish, lifecycle state, settings, or media policy changed.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Selectable coordinators: ${coordinators.length}`,
      `Zeroconf available: ${data.zeroconf_available === false ? "no" : "yes"}`,
      `Data schema: ${data.schema_version || "unknown"}`,
    ];
    coordinators.slice(0, 8).forEach((row, index) => {
      lines.push(`- ${index + 1}. ${row.url || "unknown"} (${row.host || "host unknown"}:${row.port || "port unknown"})`);
    });
    const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
    if (warnings.length) {
      lines.push("", "Warnings:");
      warnings.slice(0, 8).forEach((warning) => lines.push(`- ${warning}`));
    }
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    lines.push(
      "",
      coordinators.length
        ? "Next action: choose Use for the intended coordinator, then preview/save Distributed Settings before starting worker polling."
        : "Next action: verify the coordinator is running on the LAN, firewall/mDNS is allowed, or use a join blob/manual WorkerCoordinatorUrl."
    );
    return lines;
  }

  function renderNetworkCoordinatorDiscoveryList(result) {
    const container = byId("network-worker-discovery-list");
    if (!container) return;
    container.textContent = "";
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const coordinators = Array.isArray(data.coordinators) ? data.coordinators : [];
    if (!coordinators.length) {
      const empty = document.createElement("p");
      empty.className = "note";
      empty.textContent = "No mDNS coordinators discovered.";
      container.appendChild(empty);
      return;
    }
    coordinators.forEach((row) => {
      const url = String(row?.url || "").trim();
      if (!url) return;
      const item = document.createElement("div");
      item.className = "network-discovery-row";
      item.setAttribute("role", "listitem");
      const detail = document.createElement("div");
      detail.className = "network-discovery-url";
      detail.textContent = url;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button";
      button.textContent = "Use";
      button.dataset.networkDiscoveryUrl = url;
      button.title = "Stage this discovered coordinator URL for WorkerCoordinatorUrl.";
      item.append(detail, button);
      container.appendChild(item);
    });
  }

  function stageDiscoveredCoordinatorUrl(url) {
    const text = String(url || "").trim();
    if (!text) return false;
    const roleSelect = byId("settings-network-role");
    if (roleSelect) {
      roleSelect.value = "worker";
      roleSelect.dispatchEvent(new Event("input", { bubbles: true }));
    }
    ["settings-network-worker-url", "network-role-setup-worker-url"].forEach((id) => {
      const input = byId(id);
      if (!input) return;
      input.value = text;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const settingsView = window.mediaPipelineSettingsView || {};
    settingsView.markNetworkSettingsBuilderDirty?.();
    const staged = settingsView.applyNetworkSettingsBuilderToPatch?.() !== false;
    setText("network-worker-discovery-status", staged ? "Coordinator staged" : "Review staged URL");
    setText(
      "network-worker-discovery-result",
      [
        `Selected coordinator: ${text}`,
        staged
          ? "WorkerCoordinatorUrl was staged into the Settings patch JSON."
          : "WorkerCoordinatorUrl was filled, but the network settings patch could not be staged.",
        "Preview/save Distributed Settings before starting worker polling.",
      ].join("\n")
    );
    renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
    return staged;
  }

  function networkJoinBlobResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const lines = [
      "Coordinator join blob created.",
      "The blob contains a worker auth secret and is intentionally not written to command history.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Coordinator URL: ${data.coordinator_url || "not configured"}`,
      `Token fingerprint: ${data.token_fingerprint || "hidden"}`,
      `Token source: ${data.token_source || "unknown"}`,
      `Libraries: ${data.library_count ?? 0}`,
      `Data schema: ${data.schema_version || "unknown"}`,
    ];
    const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
    if (warnings.length) {
      lines.push("", "Warnings:");
      warnings.slice(0, 6).forEach((warning) => lines.push(`- ${warning}`));
    }
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 6).forEach((error) => lines.push(`- ${error}`));
    }
    lines.push("", "Next action: transfer the blob to the worker Join Cluster box, then import and verify test-connection.");
    return lines;
  }

  function networkJoinImportResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const settingsSave = data.settings_save && typeof data.settings_save === "object" ? data.settings_save : {};
    const joinPlan = data.join_plan && typeof data.join_plan === "object" ? data.join_plan : {};
    const testResult = data.test_connection && typeof data.test_connection === "object" ? data.test_connection : {};
    const lines = [
      "Worker join import complete.",
      "The request blob contains a worker auth secret and is intentionally not written to command history.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Coordinator URL: ${data.coordinator_url || "not configured"}`,
      `Token fingerprint: ${data.token_fingerprint || "hidden"}`,
      `Settings save: ${settingsSave.status || (settingsSave.ok ? "saved" : "blocked")}`,
      `Changed keys: ${Array.isArray(settingsSave.changed_keys) && settingsSave.changed_keys.length ? settingsSave.changed_keys.join(", ") : "none"}`,
      `Libraries advertised: ${data.library_count ?? joinPlan.library_count ?? 0}`,
      `Auto path-map entries: ${joinPlan.auto_path_map_entries ?? 0}`,
      `Effective path-map entries: ${joinPlan.effective_path_map_entries ?? 0}`,
      `Test connection: ${testResult.ok ? "passed" : "review"}`,
    ];
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    if (testResult.data) {
      lines.push("", ...networkTestConnectionResultLines(testResult).slice(0, 18));
    }
    lines.push(
      "",
      result?.ok
        ? "Next action: refresh Network status, then start worker polling only after saved/running settings still match."
        : "Next action: fix the blocked settings, TCP, auth, or path layer before starting worker polling."
    );
    return lines;
  }

  async function createNetworkJoinBlob() {
    const contract = lastNetworkLifecyclePayload.contract || {};
    const route = networkCoordinatorJoinBlobRoute(contract);
    const output = byId("network-coordinator-join-output");
    if (!route) {
      setText("network-coordinator-join-status", "Route missing");
      setText("network-coordinator-join-result", "Backend coordinator join blob route is not available in the loaded contract.");
      return null;
    }
    const coordinatorUrl = String(byId("network-coordinator-join-url")?.value || "").trim();
    const rotate = Boolean(byId("network-coordinator-join-rotate")?.checked);
    const request = {
      confirm_create: true,
      rotate_token: rotate,
    };
    if (coordinatorUrl) request.coordinator_url = coordinatorUrl;
    if (rotate) request.confirm_rotate = true;
    setText("network-coordinator-join-status", "Creating");
    setText("network-coordinator-join-result", `Submitting ${route}...`);
    try {
      const result = await apiPost(route, request);
      if (output) output.value = result?.ok ? String(result?.data?.join_blob || "") : "";
      setText("network-coordinator-join-status", result.ok ? "Blob ready" : "Blocked");
      setText("network-coordinator-join-result", networkJoinBlobResultLines(result).join("\n"));
      renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (output) output.value = "";
      setText("network-coordinator-join-status", "Failed");
      setText("network-coordinator-join-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      return null;
    }
  }

  async function copyNetworkJoinBlob() {
    const blob = String(byId("network-coordinator-join-output")?.value || "").trim();
    if (!blob) {
      setText("network-coordinator-join-status", "Nothing to copy");
      return false;
    }
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(blob);
      setText("network-coordinator-join-status", "Copied");
      return true;
    } catch (_error) {
      byId("network-coordinator-join-output")?.select?.();
      setText("network-coordinator-join-status", "Select blob");
      return false;
    }
  }

  async function importNetworkJoinBlob() {
    const contract = lastNetworkLifecyclePayload.contract || {};
    const route = networkWorkerJoinClusterRoute(contract);
    const blob = String(byId("network-worker-join-blob")?.value || "").trim();
    if (!route) {
      setText("network-worker-join-status", "Route missing");
      setText("network-worker-join-result", "Backend worker join cluster route is not available in the loaded contract.");
      return null;
    }
    if (!blob) {
      setText("network-worker-join-status", "Blob required");
      setText("network-worker-join-result", "Paste a coordinator join blob before importing.");
      renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      return null;
    }
    setText("network-worker-join-status", "Importing");
    setText("network-worker-join-result", `Submitting ${route}...`);
    try {
      const result = await apiPost(route, {
        join_blob: blob,
        confirm_import: true,
      });
      setText("network-worker-join-status", result.ok ? "Joined" : "Review");
      setText("network-worker-join-result", networkJoinImportResultLines(result).join("\n"));
      renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      if (typeof refreshAll === "function") refreshAll({ automatic: false });
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("network-worker-join-status", "Failed");
      setText("network-worker-join-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      return null;
    }
  }

  async function discoverNetworkCoordinators() {
    const contract = lastNetworkLifecyclePayload.contract || {};
    const route = networkWorkerDiscoverCoordinatorsRoute(contract);
    if (!route) {
      setText("network-worker-discovery-status", "Route missing");
      setText("network-worker-discovery-result", "Backend worker mDNS discovery route is not available in the loaded contract.");
      renderNetworkCoordinatorDiscoveryList(null);
      return null;
    }
    setText("network-worker-discovery-status", "Discovering");
    setText("network-worker-discovery-result", `Submitting ${route}...`);
    renderNetworkCoordinatorDiscoveryList(null);
    try {
      const result = await apiPost(route, { timeout_seconds: 2 });
      setText("network-worker-discovery-status", result.ok ? "Discovery complete" : "Review");
      setText("network-worker-discovery-result", networkCoordinatorDiscoveryResultLines(result).join("\n"));
      renderNetworkCoordinatorDiscoveryList(result);
      renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("network-worker-discovery-status", "Failed");
      setText("network-worker-discovery-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      renderNetworkCoordinatorDiscoveryList(null);
      renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      return null;
    }
  }

  function networkLifecycleConfirmationLines({ role, action, route, payload, config }) {
    const networkWorkers = payload.networkWorkers || {};
    const roleState = networkLifecycleStateFor(networkWorkers, role);
    const workerState = networkWorkers.worker_state && typeof networkWorkers.worker_state === "object"
      ? networkWorkers.worker_state
      : {};
    const currentClaim = workerState.job_id || workerState.source_file || "none";
    const lastDryRun = byId("network-lifecycle-command-result")?.textContent || "No recent dry-run result on this page.";
    const stopImpact = action === "stop"
      ? "Stopping may abort active worker work. Verify active claims before confirming."
      : "Starting begins backend-owned coordinator or worker lifecycle work.";
    return [
      `Role: ${role}`,
      `Action: ${action}`,
      `Route: ${route}`,
      `Saved mode: ${visibleNetworkModeLabel(config)}`,
      `Current lifecycle state: ${roleState.status}`,
      `Coordinator URL: ${coordinatorTarget(config, networkWorkers) || "not configured"}`,
      ...networkTokenPostureLines(networkWorkers),
      `Active claim impact: ${currentClaim}`,
      `Impact: ${stopImpact}`,
      "No-touch summary: this dialog only sets the backend confirmation field. The backend still owns provider checks, lifecycle lock, command journal, and preconditions.",
      "",
      "Recent dry-run/status:",
      lastDryRun.trim().slice(0, 1200) || "No recent dry-run result on this page.",
    ];
  }

  function confirmNetworkLifecycleCommand({ role, action, route, payload, config }) {
    const dialog = byId("network-lifecycle-confirm-dialog");
    const submit = byId("network-lifecycle-confirm-submit");
    const cancel = byId("network-lifecycle-confirm-cancel");
    if (!dialog || !submit || !cancel) return Promise.resolve(false);
    setText("network-lifecycle-confirm-designation", `${role} ${action}`);
    setText("network-lifecycle-confirm-summary", "Confirmed lifecycle commands are backend-owned, confirmation-gated, provider-guarded, and command-journaled.");
    setText("network-lifecycle-confirm-detail", networkLifecycleConfirmationLines({ role, action, route, payload, config }).join("\n"));
    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        submit.onclick = null;
        cancel.onclick = null;
        dialog.oncancel = null;
        if (dialog.open && dialog.close) dialog.close();
        else dialog.removeAttribute("open");
        resolve(value);
      };
      submit.onclick = () => finish(true);
      cancel.onclick = () => finish(false);
      dialog.oncancel = (event) => {
        event.preventDefault();
        finish(false);
      };
      if (dialog.showModal && !dialog.open) dialog.showModal();
      else if (!dialog.open) dialog.setAttribute("open", "open");
      cancel.focus?.();
    });
  }

  async function postNetworkLifecycleRoute(contract, role, action, dryRun, request) {
    const route = networkLifecycleRoutePath(contract, role, action, dryRun);
    if (route) return apiPost(route, request);
    throw new Error("Unsupported Network lifecycle route.");
  }

  async function runNetworkLifecycleCommand(button) {
    const role = button?.dataset?.networkLifecycleRole || "";
    const action = button?.dataset?.networkLifecycleAction || "";
    const dryRun = button?.dataset?.networkLifecycleDryRun === "true";
    const contract = lastNetworkLifecyclePayload.contract || {};
    const config = settingsConfig(lastNetworkLifecyclePayload.settings || {});
    const networkWorkers = lastNetworkLifecyclePayload.networkWorkers || {};
    const route = networkLifecycleRoutePath(contract, role, action, dryRun);
    if (!route) {
      setText("network-lifecycle-control-status", "Route missing");
      setText("network-lifecycle-command-result", "Backend lifecycle route is not available in the loaded contract.");
      return;
    }
    const urlIssue = role === "worker"
      ? obviousWorkerCoordinatorUrlIssue(coordinatorTarget(config, networkWorkers, { raw: true }), { required: true })
      : "";
    if (urlIssue) {
      setText("network-lifecycle-control-status", "Blocked");
      setText("network-lifecycle-command-result", `Worker coordinator URL is blocked before lifecycle command submission: ${urlIssue}`);
      return;
    }
    if (!dryRun) {
      const confirmed = await confirmNetworkLifecycleCommand({
        role,
        action,
        route,
        payload: lastNetworkLifecyclePayload,
        config,
      });
      if (!confirmed) {
        setText("network-lifecycle-control-status", "Cancelled");
        setText("network-lifecycle-command-result", "Confirmed lifecycle command was cancelled before the backend confirmation field was sent.");
        return;
      }
    }
    const request = {
      reason: dryRun ? "webview_network_lifecycle_dry_run" : "webview_network_lifecycle_confirmed",
    };
    if (!dryRun) request[action === "start" ? "confirm_start" : "confirm_stop"] = true;
    setText("network-lifecycle-control-status", dryRun ? "Dry-running" : "Running");
    setText("network-lifecycle-command-result", `Submitting ${route}...`);
    try {
      const result = await postNetworkLifecycleRoute(contract, role, action, dryRun, request);
      setText("network-lifecycle-command-result", networkLifecycleCommandResultLines(result).join("\n"));
      setText("network-lifecycle-control-status", result.ok ? "Command returned" : "Command blocked");
      if (typeof refreshAll === "function") refreshAll({ automatic: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("network-lifecycle-control-status", "Command failed");
      setText("network-lifecycle-command-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
    }
  }

  async function runNetworkWorkerTestConnection(options = {}) {
    const render = options.render !== false;
    const contract = lastNetworkLifecyclePayload.contract || {};
    const route = networkWorkerTestConnectionRoute(contract);
    if (!route) {
      const result = {
        ok: false,
        severity: "warning",
        message: "Backend worker test-connection route is not available in the loaded contract.",
        data: {},
      };
      if (render) {
        setText("network-lifecycle-control-status", "Route missing");
        setText("network-lifecycle-command-result", result.message);
      }
      return result;
    }
    if (render) {
      setText("network-lifecycle-control-status", "Testing");
      setText("network-lifecycle-command-result", "Submitting worker test-connection preflight...");
    }
    try {
      const result = await apiPost(route, {});
      if (render) {
        setText("network-lifecycle-command-result", networkTestConnectionResultLines(result).join("\n"));
        setText("network-lifecycle-control-status", result.ok ? "Connection passed" : "Connection review");
        if (typeof refreshAll === "function") refreshAll({ automatic: false });
      }
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        ok: false,
        severity: "error",
        message,
        data: {},
      };
      if (render) {
        setText("network-lifecycle-control-status", "Test failed");
        setText("network-lifecycle-command-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      }
      return result;
    }
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
      "Save Distributed Settings calls the backend settings save route, asks for confirmation, and creates the normal config backup before writing.",
      "Runtime boundary: settings controls only stage, preview, and save config. Start/Stop must use the backend Network Lifecycle controls.",
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
    renderNetworkSettingsPatchHandoff("Previewing staged Saved Distributed Mode Settings through backend validation.");
    await preview();
    renderNetworkSettingsPatchHandoff("Saved Distributed Mode Settings preview command finished.");
  }

  async function saveNetworkSettingsPatch() {
    const save = window.mediaPipelineSettingsView?.saveSettingsPatch;
    if (typeof save !== "function") {
      setText("network-settings-control-status", "Settings unavailable");
      renderNetworkSettingsPatchHandoff("Settings save controls are not loaded.");
      return;
    }
    setText("network-settings-control-status", "Saving...");
    renderNetworkSettingsPatchHandoff("Saving staged Saved Distributed Mode Settings through the backend settings route.");
    await save();
    renderNetworkSettingsPatchHandoff("Saved Distributed Mode Settings save command finished.");
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
      `WebView Network exposes backend-owned lifecycle controls; lifecycle contracts=${lifecycleContracts.length}; confirmed mutation routes=${networkLifecycleMutationRouteCount(contract)}.`,
      "Use dry-runs before coordinator/worker start or stop. Retry, reclaim, release, and abort workflows stay disabled until their backend routes and tests exist.",
      [
        networkLifecycleContractSummary(contract),
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
      `role=${roleText}; target=${coordinatorTarget(config, payload)}; worker poll=${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")}; path map=${pathMap}; overrides=${overrides}`,
      hasNetworkMode
        ? "Review Settings Network builder and backend Network diagnostics before trusting distributed work."
        : "Standalone mode has no worker lifecycle to start from WebView.",
      [
        `NetworkRole: ${roleText}`,
        `Worker coordinator URL: ${coordinatorTarget(config, payload)}`,
        `Coordinator bind endpoint: ${networkCoordinatorBindEndpoint(config, payload)}`,
        `Coordinator local encode: ${configFlagText(config, "CoordinatorAlsoEncodeLocally", "not configured")}`,
        `Worker URL: ${displayConfigValue(config, "WorkerCoordinatorUrl", "not configured")}`,
        `Worker source path map: ${pathMap}`,
        `Per-worker overrides: ${overrides} (backend-disabled)`,
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

    const diagnosticPosture = networkDiagnosticLayerPosture(payload);
    evidence.push(networkEvidenceRow(
      "diagnostic-layers",
      "Layer status",
      diagnosticPosture === "blocked" ? "blocked" : diagnosticPosture === "ready" ? "ready" : "review",
      networkDiagnosticLayerLines(payload).slice(0, 5).join("; "),
      diagnosticPosture === "blocked"
        ? "Resolve the blocked network layer before retrying distributed work."
        : "Use Test connection, Cluster Log, and worker row failure reasons to confirm layer evidence.",
      [
        ...networkDiagnosticLayerLines(payload),
        "Layer names are backend-owned evidence: url_reachable, auth_ok, paths_ok, queue_fresh, last_claim_result.",
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
        `Network page uses backend-owned lifecycle routes; lifecycle contracts=${lifecycleContracts.length}; confirmed mutation routes=${networkLifecycleMutationRouteCount(contract)}.`,
        "Use Network Lifecycle dry-runs before any confirmed coordinator/worker start or stop command.",
      [
        "This checklist cannot abort, reclaim, release, drain, publish, rename, save settings, rewrite state, or touch media files.",
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
      "Boundary: persisted worker state is visible through /api/network/workers; coordinator/worker lifecycle controls use backend-owned routes.",
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
    if (item?.worker_misconfigured_reason_code) return "blocked";
    if (item?.last_failure_reason_code || item?.last_failure_reason) return "warning";
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
      "last_failure_reason_code",
      "last_failure_reason",
      "last_failure_job_id",
      "last_failure_source_path",
      "last_failure_at",
      "failure_streak_reason_code",
      "failure_streak_count",
      "worker_misconfigured_reason_code",
      "worker_misconfigured_at",
      "accessible_library_ids",
    ]);
    const lines = [
      `Worker: ${workerDisplayValue(item.worker_name || item.worker_id)}`,
      `Worker ID: ${workerDisplayValue(item.worker_id)}`,
      `Status: ${workerDisplayValue(item.status)}`,
      `Accessible libraries: ${workerLibraryCapabilityText(item)}`,
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
      `Last failure code: ${workerDisplayValue(item.last_failure_reason_code)}`,
      `Last failure reason: ${workerDisplayValue(item.last_failure_reason)}`,
      `Last failure job: ${workerDisplayValue(item.last_failure_job_id)}`,
      `Last failure source: ${workerDisplayValue(item.last_failure_source_path)}`,
      `Last failure at: ${workerDisplayValue(item.last_failure_at)}`,
      `Failure streak: ${workerDisplayValue(item.failure_streak_count)} ${workerDisplayValue(item.failure_streak_reason_code)}`,
      `Worker misconfigured code: ${workerDisplayValue(item.worker_misconfigured_reason_code)}`,
      `Worker misconfigured at: ${workerDisplayValue(item.worker_misconfigured_at)}`,
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

  function workerLibraryCapabilityText(item) {
    const ids = Array.isArray(item?.accessible_library_ids)
      ? item.accessible_library_ids
        .map((value) => String(value || "").trim())
        .filter(Boolean)
      : [];
    return ids.length ? ids.join(", ") : "unknown/not reported";
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
    document.querySelectorAll("[data-network-tab]").forEach((button) => {
      button.addEventListener("click", () => activateNetworkTab(button.dataset.networkTab || ""));
    });
    const previewSettingsButton = byId("network-settings-preview-button");
    if (previewSettingsButton) previewSettingsButton.addEventListener("click", previewNetworkSettingsPatch);
    const saveSettingsButton = byId("network-settings-save-button");
    if (saveSettingsButton) saveSettingsButton.addEventListener("click", saveNetworkSettingsPatch);
    document.querySelectorAll("[data-network-lifecycle-role]").forEach((button) => {
      button.addEventListener("click", () => runNetworkLifecycleCommand(button));
    });
    document.querySelectorAll("[data-network-test-connection]").forEach((button) => {
      button.addEventListener("click", () => runNetworkWorkerTestConnection());
    });
    const createJoinButton = byId("network-coordinator-join-create");
    if (createJoinButton) createJoinButton.addEventListener("click", () => createNetworkJoinBlob());
    const copyJoinButton = byId("network-coordinator-join-copy");
    if (copyJoinButton) copyJoinButton.addEventListener("click", () => copyNetworkJoinBlob());
    const importJoinButton = byId("network-worker-join-import");
    if (importJoinButton) importJoinButton.addEventListener("click", () => importNetworkJoinBlob());
    const discoverButton = byId("network-worker-discover");
    if (discoverButton) discoverButton.addEventListener("click", () => discoverNetworkCoordinators());
    const discoveryList = byId("network-worker-discovery-list");
    if (discoveryList) {
      discoveryList.addEventListener("click", (event) => {
        const button = event.target?.closest?.("[data-network-discovery-url]");
        if (!button) return;
        stageDiscoveredCoordinatorUrl(button.dataset.networkDiscoveryUrl || "");
      });
    }
    const workerJoinBlob = byId("network-worker-join-blob");
    if (workerJoinBlob) {
      workerJoinBlob.addEventListener("input", () => {
        renderNetworkJoinControls(lastNetworkLifecyclePayload, settingsConfig(lastNetworkLifecyclePayload.settings || {}));
      });
    }
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
      payload.role === "worker"
        ? "Worker mode note: the coordinator worker list is persisted on the coordinator host, not in this worker state folder."
        : "",
      ...networkDiagnosticLayerLines(payload).slice(0, 5),
      ...networkStateFileCompactLines(payload.state_files || []),
      "Lifecycle controls remain backend-owned. This panel is read-only persisted state, not a live coordinator control surface.",
    ].filter(Boolean);
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
    renderNetworkSummaryRows("network-worker-summary", lines);
    renderNetworkWorkerProgress(payload);
    renderNetworkWorkerRows(payload);
  }

  function renderNetworkView(payload = {}) {
    initNetworkViewEvents();
    const settings = payload.settings || {};
    const contract = payload.contract || {};
    const queue = payload.queue || {};
    const networkWorkers = payload.networkWorkers || {};
    const config = settingsConfig(settings);
    const role = String(rawConfigValue(config, "NetworkRole", "standalone") || "standalone").toLowerCase();
    const visibleRole = visibleNetworkMode(config);
    const pollInterval = displayConfigValue(config, "WorkerPollIntervalSecs", "not configured");
    const localApiState = contract?.schema_version ? "contract loaded" : "not loaded";
    const guidance = networkGuidance(visibleRole === "coordinator_local" ? "coordinator" : role, networkWorkers);

    setText("network-role", visibleNetworkModeLabel(config));
    setText("network-coordinator-target", coordinatorTarget(config, networkWorkers));
    setText("network-worker-poll", pollInterval);
    setText("network-local-api", localApiState);
    setText("network-status", settings.error ? "Settings unavailable" : "Backend lifecycle controls");
    renderNetworkStatusBanner(payload, config);
    syncNetworkTabs(config);
    renderNetworkRoleDashboards({ queue, networkWorkers, config, contract });
    renderNetworkSummaryRows("network-summary", guidance);
    renderNetworkSummaryRows("network-mode-model", networkModeModelLines(visibleRole));
    setText("network-api-status", contract?.schema_version || "Not loaded");
    setText("network-api-summary", contractSummary(contract));
    renderNetworkReadiness(payload, role, config);
    renderNetworkLifecycleControls(payload, role, config);
    renderNetworkLifecycleHandoff(payload, role, config);
    renderNetworkEvidenceChecklist(payload, role, config);
    renderNetworkStateFiles(networkWorkers);
    renderNetworkSettingsRows(settings);
    renderNetworkSettingsPatchHandoff();
    renderNetworkWorkers(networkWorkers);
    if (typeof getCommandHistory === "function") renderNetworkOpenHistory(getCommandHistory());
  }

  /**
   * Public namespace for the Workers page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineNetworkView = {
    networkRows,
    activateNetworkTab,
    networkCoordinatorOverviewModel,
    networkWorkerOverviewModel,
    renderNetworkRoleDashboards,
    renderCoordinatorActiveRows,
    renderCoordinatorQueueRows,
    renderWorkerClaimRows,
    visibleNetworkMode,
    visibleNetworkModeLabel,
    networkReadinessLines,
    networkRuntimeStatus,
    networkWorkerDriftPayload,
    networkWorkerDriftFieldText,
    networkWorkerDriftStatusText,
    networkWorkerDriftSummaryLines,
    renderNetworkStatusBanner,
    obviousWorkerCoordinatorUrlIssue,
    networkLifecycleMutationRouteCount,
    networkLifecycleRouteRow,
    networkLifecycleRoutePath,
    networkLifecycleRouteAvailable,
    networkWorkerTestConnectionRoute,
    networkWorkerDiscoverCoordinatorsRoute,
    networkCoordinatorJoinBlobRoute,
    networkWorkerJoinClusterRoute,
    networkLifecycleRelevantRole,
    networkLifecycleControlLines,
    networkLifecycleCommandResultLines,
    networkTestConnectionResultLines,
    networkCoordinatorDiscoveryResultLines,
    renderNetworkCoordinatorDiscoveryList,
    discoverNetworkCoordinators,
    stageDiscoveredCoordinatorUrl,
    networkJoinBlobResultLines,
    networkJoinImportResultLines,
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
    renderNetworkLifecycleControls,
    runNetworkLifecycleCommand,
    runNetworkWorkerTestConnection,
    createNetworkJoinBlob,
    copyNetworkJoinBlob,
    importNetworkJoinBlob,
    previewNetworkSettingsPatch,
    saveNetworkSettingsPatch,
    renderNetworkView,
  };
  window.renderNetworkOpenHistory = renderNetworkOpenHistory;
  window.initNetworkViewEvents = initNetworkViewEvents;
})();
