// Network join-blob and coordinator-discovery request workflows.
(function () {
  "use strict";

  function createNetworkSetupCommandsModule(deps = {}) {
    // Route adapters use networkCommandRouteByDataSchema before this module submits a request.
    const {
      byId = () => null,
      confirmNetworkSetupCommand = async () => false,
      networkCoordinatorDiscoveryResultLines = () => [],
      networkCoordinatorJoinBlobRoute = () => "",
      networkJoinBlobResultLines = () => [],
      networkJoinImportResultLines = () => [],
      networkWorkerDiscoverCoordinatorsRoute = () => "",
      networkWorkerJoinClusterRoute = () => "",
      postNetworkRoute = async () => ({}),
      refreshAll = () => {},
      renderNetworkCoordinatorDiscoveryList = () => {},
      renderNetworkJoinControls = () => {},
      setText = () => {},
      settingsConfig = () => ({}),
      state = {},
    } = deps;

  async function createNetworkJoinBlob() {
    const contract = state.lifecyclePayload.contract || {};
    const route = networkCoordinatorJoinBlobRoute(contract);
    const output = byId("network-coordinator-join-output");
    if (!route) {
      setText("network-coordinator-join-status", "Route missing");
      setText("network-coordinator-join-result", "Backend coordinator join blob route is not available in the loaded contract.");
      return null;
    }
    const coordinatorUrl = String(byId("network-coordinator-join-url")?.value || "").trim();
    const rotate = Boolean(byId("network-coordinator-join-rotate")?.checked);
    const confirmed = await confirmNetworkSetupCommand({
      designation: rotate ? "Rotate token + create blob" : "Create join blob",
      summary: rotate
        ? "This backend setup command can rotate the worker auth token before returning a secret join blob."
        : "This backend setup command returns a secret join blob for transfer to a worker.",
      detailLines: [
        `Route: ${route}`,
        "Effect: secret-transfer; response is intentionally unjournaled because it contains a secret.",
        coordinatorUrl ? `Coordinator URL override: ${coordinatorUrl}` : "Coordinator URL override: none; backend uses saved/coordinator evidence.",
        rotate
          ? "Token rotation: yes. Existing worker join blobs or saved worker tokens may need to be refreshed."
          : "Token rotation: no.",
        "No lifecycle start/stop, queue claim, publish, rename, or media/source mutation is performed by this WebView command.",
      ],
    });
    if (!confirmed) {
      setText("network-coordinator-join-status", "Cancelled");
      setText("network-coordinator-join-result", "Create Join Blob was cancelled before the backend confirmation field was sent.");
      return null;
    }
    const request = {
      confirm_create: true,
      rotate_token: rotate,
    };
    if (coordinatorUrl) request.coordinator_url = coordinatorUrl;
    if (rotate) request.confirm_rotate = true;
    setText("network-coordinator-join-status", "Creating");
    setText("network-coordinator-join-result", `Submitting ${route}...`);
    try {
      const result = await postNetworkRoute(route, request);
      if (output) output.value = result?.ok ? String(result?.data?.join_blob || "") : "";
      setText("network-coordinator-join-status", result.ok ? "Blob ready" : "Blocked");
      setText("network-coordinator-join-result", networkJoinBlobResultLines(result).join("\n"));
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (output) output.value = "";
      setText("network-coordinator-join-status", "Failed");
      setText("network-coordinator-join-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
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
    const contract = state.lifecyclePayload.contract || {};
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
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
      return null;
    }
    const confirmed = await confirmNetworkSetupCommand({
      designation: "Join Cluster",
      summary: "This backend setup command imports a secret join blob and saves worker network settings.",
      detailLines: [
        `Route: ${route}`,
        "Effect: config-write; backend settings save writes worker coordinator URL, worker auth secret, NetworkRole, and library-derived WorkerSourcePathMap evidence when valid.",
        "This is separate from staged Distributed Settings and does not use the Preview Settings Patch button.",
        "It does not start worker polling, claim work, mutate queue state, publish, rename, or touch media/source files.",
      ],
    });
    if (!confirmed) {
      setText("network-worker-join-status", "Cancelled");
      setText("network-worker-join-result", "Join Cluster was cancelled before the backend confirmation field was sent.");
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
      return null;
    }
    setText("network-worker-join-status", "Importing");
    setText("network-worker-join-result", `Submitting ${route}...`);
    try {
      const result = await postNetworkRoute(route, {
        join_blob: blob,
        confirm_import: true,
      });
      setText("network-worker-join-status", result.ok ? "Joined" : "Review");
      setText("network-worker-join-result", networkJoinImportResultLines(result).join("\n"));
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
      if (typeof refreshAll === "function") refreshAll({ automatic: false });
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("network-worker-join-status", "Failed");
      setText("network-worker-join-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
      return null;
    }
  }

  async function discoverNetworkCoordinators() {
    const contract = state.lifecyclePayload.contract || {};
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
      const result = await postNetworkRoute(route, { timeout_seconds: 2 });
      setText("network-worker-discovery-status", result.ok ? "Discovery complete" : "Review");
      setText("network-worker-discovery-result", networkCoordinatorDiscoveryResultLines(result).join("\n"));
      renderNetworkCoordinatorDiscoveryList(result);
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("network-worker-discovery-status", "Failed");
      setText("network-worker-discovery-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      renderNetworkCoordinatorDiscoveryList(null);
      renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
      return null;
    }
  }
    return {
      createNetworkJoinBlob,
      copyNetworkJoinBlob,
      importNetworkJoinBlob,
      discoverNetworkCoordinators,
    };
  }

  window.__networkSetupCommandsModule = { createNetworkSetupCommandsModule };
})();
