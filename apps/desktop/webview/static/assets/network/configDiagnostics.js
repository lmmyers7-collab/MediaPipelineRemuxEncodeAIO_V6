// Read-only Network configuration projection and diagnostic rail. Loaded before networkView.js.
(function () {
  "use strict";

  function createNetworkConfigDiagnosticsModule(deps = {}) {
    const fallbackNetworkKeys = Array.isArray(deps.fallbackNetworkKeys) ? deps.fallbackNetworkKeys : [];
    const configValue = typeof deps.configValue === "function" ? deps.configValue : null;
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    function networkStateFileRows(networkWorkers) {
      return Array.isArray(networkWorkers?.state_files) ? networkWorkers.state_files : [];
    }
    function networkStateFileStatus(item) {
      const status = String(item?.status || "").toLowerCase();
      if (status.includes("unreadable")) return "blocked";
      if (status.includes("missing")) return "warning";
      return status.includes("present") ? "match" : "warning";
    }
    function networkStateFileCompactLines(rows = []) {
      const files = Array.isArray(rows) ? rows : [];
      if (!files.length) return ["State files: not loaded"];
      return [`State files: ${files.length}; present=${files.filter((item) => networkStateFileStatus(item) === "match").length}; missing=${files.filter((item) => networkStateFileStatus(item) === "warning").length}; unreadable=${files.filter((item) => networkStateFileStatus(item) === "blocked").length}`];
    }

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

  function networkStatusTone(status) {
    const value = String(status || "").trim().toLowerCase();
    if (["ready", "match", "pass", "passed", "present", "running", "active", "encoding", "success"].includes(value)) return "match";
    if (["review", "warning", "missing", "stale", "not_running", "not_applicable"].includes(value)) return "warning";
    if (["blocked", "error", "failed", "unreadable", "fatal"].includes(value)) return "blocked";
    return "unknown";
  }

  function networkDiagnosticLayerByKey(networkWorkers, key) {
    const diagnostic = networkDiagnosticLayers(networkWorkers);
    const layers = Array.isArray(diagnostic.layers) ? diagnostic.layers : [];
    const requested = String(key || "").trim().toLowerCase();
    const row = layers.find((layer) => String(layer?.key || "").trim().toLowerCase() === requested);
    if (row) return row;
    const status = diagnostic[requested];
    return status ? { key: requested, label: requested, status } : null;
  }

  function networkStateFilesDiagnosticStatus(networkWorkers) {
    const rows = networkStateFileRows(networkWorkers);
    if (!rows.length) return "unknown";
    const statuses = rows.map((row) => networkStateFileStatus(row));
    if (statuses.some((status) => status === "blocked")) return "blocked";
    if (statuses.some((status) => status === "warning")) return "review";
    if (statuses.every((status) => status === "match")) return "ready";
    return "unknown";
  }

  function setNetworkDiagnosticChip(id, label, status, detail = "") {
    const node = byId(id);
    if (!node) return;
    const value = String(status || "").trim() || "unknown";
    node.textContent = `${label}: ${value}`;
    node.dataset.status = networkStatusTone(value);
    node.title = detail || `${label} diagnostic status: ${value}`;
  }

  function renderNetworkDiagnosticRail(networkWorkers = {}) {
    const layers = {
      tcp: networkDiagnosticLayerByKey(networkWorkers, "url_reachable"),
      auth: networkDiagnosticLayerByKey(networkWorkers, "auth_ok"),
      paths: networkDiagnosticLayerByKey(networkWorkers, "paths_ok"),
      queue: networkDiagnosticLayerByKey(networkWorkers, "queue_fresh"),
      claim: networkDiagnosticLayerByKey(networkWorkers, "last_claim_result"),
    };
    setNetworkDiagnosticChip("network-diagnostic-tcp", "TCP", layers.tcp?.status, layers.tcp?.detail);
    setNetworkDiagnosticChip("network-diagnostic-auth", "Auth", layers.auth?.status, layers.auth?.detail);
    setNetworkDiagnosticChip("network-diagnostic-paths", "Paths", layers.paths?.status, layers.paths?.detail);
    setNetworkDiagnosticChip("network-diagnostic-queue", "Queue", layers.queue?.status, layers.queue?.detail);
    setNetworkDiagnosticChip("network-diagnostic-claim", "Claim", layers.claim?.status, layers.claim?.detail);
    setNetworkDiagnosticChip(
      "network-diagnostic-state-files",
      "State files",
      networkStateFilesDiagnosticStatus(networkWorkers),
      networkStateFileCompactLines(networkStateFileRows(networkWorkers)).join("\n")
    );
  }


    return {
      settingsConfig, rawConfigValue, isNetworkSecretSettingKey, isNetworkUrlSettingKey,
      redactedNetworkUrl, displayConfigValue, networkSettingDefinitions, networkRows,
      networkCoordinatorConnectivity, networkCoordinatorConnectivityLines, networkCoordinatorBindEndpoint,
      coordinatorTarget, visibleNetworkMode, visibleNetworkModeLabel, networkLifecycleStatePayload,
      networkLifecycleStateFor, networkRuntimeStatus, networkTokenPostureLines, networkDiagnosticLayers,
      networkDiagnosticLayerLines, networkDiagnosticLayerPosture, networkStatusTone,
      networkDiagnosticLayerByKey, networkStateFilesDiagnosticStatus, renderNetworkDiagnosticRail,
    };
  }

  window.__networkConfigDiagnosticsModule = { createNetworkConfigDiagnosticsModule };
})();
