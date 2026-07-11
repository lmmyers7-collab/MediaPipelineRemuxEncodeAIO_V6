// Network lifecycle dry-run evidence, control enablement, and route presentation.
(function () {
  "use strict";

  function createNetworkLifecycleViewModule(deps = {}) {
    const {
      byId = () => null,
      coordinatorTarget = () => "",
      networkLifecycleRouteAvailable = () => false,
      networkLifecycleRoutePath = () => "",
      networkLifecycleStateFor = () => ({ status: "unknown" }),
      networkRuntimeStatus = () => ({ label: "Not loaded" }),
      networkTokenPostureLines = () => [],
      obviousWorkerCoordinatorUrlIssue = () => "",
      renderNetworkDiagnosticRail = () => {},
      setText = () => {},
      state = {},
      visibleNetworkMode = () => "",
      visibleNetworkModeLabel = () => "",
    } = deps;
    const documentRef = deps.documentRef || document;

  function networkLifecycleDryRunKey(role, action) {
    return `${role || ""}:${action || ""}`;
  }

  function closeReadinessIsSafe(closeReadiness) {
    return Boolean(closeReadiness && typeof closeReadiness === "object" && (closeReadiness.safe_to_close === true || closeReadiness.ready === true));
  }

  function networkLifecycleFingerprint(payload = {}, config = {}, role = "", action = "") {
    const contract = payload.contract || {};
    const networkWorkers = payload.networkWorkers || {};
    const closeReadiness = payload.closeReadiness || {};
    const roleState = networkLifecycleStateFor(networkWorkers, role);
    return JSON.stringify({
      role,
      action,
      mode: visibleNetworkMode(config),
      dry_run_route: networkLifecycleRoutePath(contract, role, action, true),
      confirmed_route: networkLifecycleRoutePath(contract, role, action, false),
      lifecycle_state: roleState.status,
      coordinator_target: coordinatorTarget(config, networkWorkers, { raw: true }) || "",
      close_readiness_safe: closeReadinessIsSafe(closeReadiness),
      close_readiness_reason: closeReadiness.reason || closeReadiness.state || closeReadiness.message || "",
    });
  }

  function networkLifecycleDryRunRecord(role, action) {
    return state.dryRunEvidence.get(networkLifecycleDryRunKey(role, action)) || null;
  }

  function pruneNetworkLifecycleDryRunEvidence(payload = {}, config = {}) {
    Array.from(state.dryRunEvidence.entries()).forEach(([key, record]) => {
      const [role, action] = key.split(":");
      const currentFingerprint = networkLifecycleFingerprint(payload, config, role, action);
      if (!record || record.fingerprint !== currentFingerprint || !closeReadinessIsSafe(payload.closeReadiness)) {
        state.dryRunEvidence.delete(key);
      }
    });
  }

  function networkLifecycleDryRunAllowsConfirmed(payload = {}, config = {}, role = "", action = "") {
    const record = networkLifecycleDryRunRecord(role, action);
    if (!record || record.safeToApply !== true) return false;
    return record.fingerprint === networkLifecycleFingerprint(payload, config, role, action)
      && closeReadinessIsSafe(payload.closeReadiness);
  }

  function networkLifecycleDryRunRequirementLine(payload = {}, config = {}, role = "", action = "") {
    const record = networkLifecycleDryRunRecord(role, action);
    if (!closeReadinessIsSafe(payload.closeReadiness)) {
      return "Matching dry-run required: close-readiness is not safe or not loaded.";
    }
    if (!record) return `Matching dry-run required: run Check ${role} ${action} first.`;
    if (record.fingerprint !== networkLifecycleFingerprint(payload, config, role, action)) {
      return `Matching dry-run required: previous Check ${role} ${action} is stale after state/settings/route changes.`;
    }
    if (record.safeToApply !== true) return `Matching dry-run required: latest Check ${role} ${action} did not report safe_to_apply.`;
    return `Matching dry-run accepted: Check ${role} ${action} reported safe_to_apply at ${record.capturedAt}.`;
  }

  function rememberNetworkLifecycleDryRun(payload = {}, config = {}, role = "", action = "", result = {}) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    state.dryRunEvidence.set(networkLifecycleDryRunKey(role, action), {
      role,
      action,
      ok: result?.ok === true,
      safeToApply: data.safe_to_apply === true,
      message: result?.message || "",
      command: result?.command || "",
      fingerprint: networkLifecycleFingerprint(payload, config, role, action),
      capturedAt: new Date().toISOString(),
    });
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

  function networkLifecycleRelevantRoles(config) {
    const mode = visibleNetworkMode(config);
    if (mode === "coordinator_local") return ["coordinator", "worker"];
    if (mode === "coordinator") return ["coordinator"];
    if (mode === "worker") return ["worker"];
    return [];
  }

  function networkLifecycleControlLines(payload = {}, config = {}) {
    const contract = payload.contract || {};
    const networkWorkers = payload.networkWorkers || {};
    const relevantRoles = networkLifecycleRelevantRoles(config);
    const modeLabel = visibleNetworkModeLabel(config);
    const runtime = networkRuntimeStatus(networkWorkers, config);
    if (!relevantRoles.length) {
      return [
        `Mode: ${modeLabel}`,
        `Runtime: ${runtime.label}`,
        "Network lifecycle is inactive in Standalone mode.",
        "Normal Launch is available only in Standalone mode.",
      ];
    }
    const workerUrlIssue = relevantRoles.includes("worker")
      ? obviousWorkerCoordinatorUrlIssue(coordinatorTarget(config, networkWorkers, { raw: true }), { required: true })
      : "";
    const routeLines = relevantRoles.flatMap((roleName) => ["start", "stop"].flatMap((action) => [
      `${roleName} ${action} dry-run route: ${networkLifecycleRouteAvailable(contract, roleName, action, true) ? "available" : "missing"}`,
      `${roleName} ${action} route: ${networkLifecycleRouteAvailable(contract, roleName, action, false) ? "available" : "missing"}`,
    ]));
    const stateLines = relevantRoles.map((roleName) => {
      const roleState = networkLifecycleStateFor(networkWorkers, roleName);
      return `${roleName} state=${roleState.status}; confirmed start=${networkLifecycleDryRunRequirementLine(payload, config, roleName, "start")}; confirmed stop=${networkLifecycleDryRunRequirementLine(payload, config, roleName, "stop")}`;
    });
    const lines = [
      `Mode: ${modeLabel}`,
      `Runtime: ${runtime.label}.`,
      "Normal Launch is blocked in this network mode; use these backend lifecycle controls.",
      "Guided actions run the backend dry-run route first; confirmation opens only after safe_to_apply evidence is current.",
      "Confirmed start/stop commands still require backend confirmation fields and command-journal records.",
      ...stateLines,
      ...routeLines,
      ...networkTokenPostureLines(networkWorkers),
      "Drain, Disable New Work, Pause, Abort Current, Reclaim Job, and Quarantine Worker remain disabled until backend routes exist.",
    ];
    if (workerUrlIssue) lines.splice(3, 0, `Worker URL blocked: ${workerUrlIssue}`);
    return lines;
  }

  function setNetworkSetupRouteStatus(elementId, route, readyText) {
    const node = byId(elementId);
    if (!node) return;
    const current = String(node.textContent || "").trim();
    const routeOnlyStatuses = new Set(["", "Not loaded", "Route ready", "Route missing"]);
    if (!route) {
      node.textContent = "Route missing";
      return;
    }
    if (routeOnlyStatuses.has(current)) {
      node.textContent = readyText;
    }
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
    setNetworkSetupRouteStatus("network-coordinator-join-status", coordinatorRoute, "Route ready");
    setNetworkSetupRouteStatus("network-worker-join-status", workerRoute, "Route ready");
    setNetworkSetupRouteStatus("network-worker-discovery-status", discoveryRoute, "Route ready");
  }

  function renderNetworkLifecycleControls(payload = {}, role = "standalone", config = {}) {
    state.lifecyclePayload = payload && typeof payload === "object" ? payload : {};
    const contract = payload.contract || {};
    const networkWorkers = payload.networkWorkers || {};
    const relevantRoles = networkLifecycleRelevantRoles(config);
    const modeLabel = visibleNetworkModeLabel(config);
    const runtime = networkRuntimeStatus(networkWorkers, config);
    const roleStates = relevantRoles.map((roleName) => {
      const state = networkLifecycleStateFor(networkWorkers, roleName);
      return `${roleName} ${state.status}`;
    });
    const workerUrlIssue = relevantRoles.includes("worker")
      ? obviousWorkerCoordinatorUrlIssue(coordinatorTarget(config, networkWorkers, { raw: true }), { required: true })
      : "";
    pruneNetworkLifecycleDryRunEvidence(payload, config);
    documentRef.querySelectorAll("[data-network-action-group]").forEach((group) => {
      const groupRole = group.dataset.networkActionGroup || "";
      const visible = groupRole === "standalone"
        ? relevantRoles.length === 0
        : relevantRoles.includes(groupRole);
      group.hidden = !visible;
    });
    documentRef.querySelectorAll("[data-network-lifecycle-role]").forEach((button) => {
      const buttonRole = button.dataset.networkLifecycleRole || "";
      const action = button.dataset.networkLifecycleAction || "";
      const dryRun = button.dataset.networkLifecycleDryRun === "true";
      const guided = button.dataset.networkLifecycleGuided === "true";
      const usesDryRunRoute = dryRun || guided;
      const roleApplies = relevantRoles.includes(buttonRole);
      const routeAvailable = networkLifecycleRouteAvailable(contract, buttonRole, action, usesDryRunRoute);
      const roleState = networkLifecycleStateFor(networkWorkers, buttonRole);
      const stateAllowsAction = dryRun && !guided
        ? true
        : action === "start"
          ? roleState.status === "stopped"
          : roleState.status === "running";
      const dryRunAllowsConfirmed = dryRun || guided || networkLifecycleDryRunAllowsConfirmed(payload, config, buttonRole, action);
      const urlAllows = !workerUrlIssue || buttonRole !== "worker";
      const available = roleApplies && routeAvailable && urlAllows && stateAllowsAction && dryRunAllowsConfirmed;
      button.hidden = !roleApplies;
      button.disabled = !available;
      if (available) {
        button.title = guided
          ? `${modeLabel}: run backend dry-run for ${buttonRole} ${action}; confirmation opens only when safe_to_apply is current.`
          : dryRun
            ? `${modeLabel}: check ${buttonRole} ${action}; effect=none.`
            : action === "stop"
            ? `${modeLabel}: stop polling/new claims through backend lifecycle route; active work is preserved for done reporting.`
            : `${modeLabel}: start through backend lifecycle route.`;
      } else if (!roleApplies) {
        button.title = "This lifecycle control does not apply to the saved network mode.";
      } else if (!routeAvailable) {
        button.title = usesDryRunRoute
          ? "Backend lifecycle dry-run route is not available in the loaded contract."
          : "Backend lifecycle route is not available in the loaded contract.";
      } else if (!urlAllows) {
        button.title = workerUrlIssue;
      } else if (!dryRunAllowsConfirmed) {
        button.title = networkLifecycleDryRunRequirementLine(payload, config, buttonRole, action);
      } else {
        button.title = action === "start"
          ? `Start is available only while ${buttonRole} lifecycle state is stopped.`
          : `Stop is available only while ${buttonRole} lifecycle state is running.`;
      }
    });
    documentRef.querySelectorAll("[data-network-future-control]").forEach((button) => {
      button.disabled = true;
      button.title = "Backend route not implemented yet.";
    });
    documentRef.querySelectorAll("[data-network-test-connection]").forEach((button) => {
      const routeAvailable = Boolean(networkWorkerTestConnectionRoute(contract));
      const roleApplies = relevantRoles.includes("worker");
      button.hidden = !roleApplies;
      button.disabled = !roleApplies || !routeAvailable;
      button.title = routeAvailable
        ? "Run backend-owned read-only TCP/auth/path preflight for this worker."
        : "Backend worker test-connection route is not available in the loaded contract.";
    });
    setText(
      "network-lifecycle-control-status",
      relevantRoles.length ? `${runtime.label}: ${roleStates.join(", ")}` : "Standalone"
    );
    setText("network-lifecycle-control-summary", networkLifecycleControlLines(payload, config).join("\n"));
    renderNetworkDiagnosticRail(networkWorkers);
    renderNetworkJoinControls(payload, config);
  }
    return {
      networkLifecycleDryRunKey,
      closeReadinessIsSafe,
      networkLifecycleFingerprint,
      networkLifecycleDryRunRecord,
      pruneNetworkLifecycleDryRunEvidence,
      networkLifecycleDryRunAllowsConfirmed,
      networkLifecycleDryRunRequirementLine,
      rememberNetworkLifecycleDryRun,
      networkWorkerTestConnectionRoute,
      networkCommandRouteByDataSchema,
      networkCoordinatorJoinBlobRoute,
      networkWorkerJoinClusterRoute,
      networkWorkerDiscoverCoordinatorsRoute,
      networkLifecycleRelevantRole,
      networkLifecycleRelevantRoles,
      networkLifecycleControlLines,
      setNetworkSetupRouteStatus,
      renderNetworkJoinControls,
      renderNetworkLifecycleControls,
    };
  }

  window.__networkLifecycleViewModule = { createNetworkLifecycleViewModule };
})();
