// Read-only Network lifecycle contract and route projection. Loaded before networkView.js.
(function () {
  function createNetworkLifecycleContractModule(deps = {}) {
    const { rawConfigValue, closeReadinessLine, networkWorkerTestConnectionRoute, networkWorkerDiscoverCoordinatorsRoute, networkCoordinatorJoinBlobRoute, networkWorkerJoinClusterRoute } = deps;

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
    return routes.filter((route) => {
      const lifecycle = route?.network_lifecycle || {};
      const method = String(route?.method || "GET").toUpperCase();
      return method === "POST" && lifecycle.role && lifecycle.action && lifecycle.dry_run === false;
    }).length;
  }

  function networkLifecycleDryRunRouteCount(contract) {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    return routes.filter((route) => {
      const lifecycle = route?.network_lifecycle || {};
      const method = String(route?.method || "GET").toUpperCase();
      return method === "POST" && lifecycle.role && lifecycle.action && lifecycle.dry_run === true;
    }).length;
  }

  function networkSetupMutationRouteRows(contract) {
    const routes = Array.isArray(contract?.routes) ? contract.routes : [];
    const networkRoutePrefix = ["/api", "network"].join("/") + "/";
    return routes.filter((route) => {
      const path = String(route?.path || "");
      const method = String(route?.method || "GET").toUpperCase();
      const effect = String(route?.effect || "").toLowerCase();
      return path.startsWith(networkRoutePrefix)
        && method === "POST"
        && effect !== "none"
        && !route?.network_lifecycle;
    });
  }

  function networkSetupMutationRouteSummary(contract) {
    const rows = networkSetupMutationRouteRows(contract);
    if (!rows.length) return "none";
    return rows
      .map((route) => `${route.path || "setup route"}=${route.effect || "unknown"}`)
      .join("; ");
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
    const confirmedLifecycleRoutes = networkLifecycleMutationRouteCount(contract);
    const dryRunLifecycleRoutes = networkLifecycleDryRunRouteCount(contract);
    const setupRoutes = networkSetupMutationRouteRows(contract);
    const workerRouteLoaded = routeExists(contract, "/api/network/workers", "GET");
    const workerSource = networkWorkers?.source || "not loaded";
    const unsafeClose = closeReadiness && typeof closeReadiness === "object" && closeReadiness.safe_to_close === false;
    return [
      "Lifecycle owner: backend Network diagnostics / Python dispatcher.",
      closeReadinessLine(closeReadiness),
      `Persisted worker state source: ${workerSource}`,
      `Read-only worker route: ${workerRouteLoaded ? "available" : "missing"} (GET /api/network/workers, effect=none).`,
      `Lifecycle dry-run routes: ${dryRunLifecycleRoutes ? `present (${dryRunLifecycleRoutes})` : "absent"}; confirmed lifecycle routes: ${confirmedLifecycleRoutes ? `present (${confirmedLifecycleRoutes})` : "absent"}.`,
      `Setup write/secret routes: ${setupRoutes.length ? networkSetupMutationRouteSummary(contract) : "none"}.`,
      `Lifecycle contracts: ${networkLifecycleContracts(contract).length}; frontend allowed=${lifecycleSummary.frontend_allowed ? "yes" : "no"}.`,
      unsafeClose
        ? "Safe next step: leave network role/settings and lifecycle planning unchanged until close-readiness is safe."
        : "Safe next step: run the backend dry-run route before any confirmed network lifecycle command.",
    ];
  }

  function networkRouteSummaryStatus(contract) {
    if (!contract?.schema_version) return "Not loaded";
    const workerRouteLoaded = routeExists(contract, "/api/network/workers", "GET");
    const confirmedLifecycleRoutes = networkLifecycleMutationRouteCount(contract);
    if (workerRouteLoaded && confirmedLifecycleRoutes > 0) return "Lifecycle routes";
    if (workerRouteLoaded && confirmedLifecycleRoutes === 0) return "Read-only route";
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
      `Coordinator join blob route: ${joinBlobRoute ? "available; setup secret-transfer, unjournaled because it returns a secret" : "missing or not loaded"}.`,
      `Worker join cluster route: ${joinClusterRoute ? "available; setup config-write, unjournaled because the request contains a secret" : "missing or not loaded"}.`,
      `Lifecycle dry-run routes: ${networkLifecycleDryRunRouteCount(contract)}; confirmed lifecycle start/stop routes: ${networkLifecycleMutationRouteCount(contract)}.`,
      `Setup write/secret routes: ${networkSetupMutationRouteSummary(contract)}.`,
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


    return { contractSummary, configFlagText, configuredStatus, networkPathMapStatus, routeExists, networkLifecycleContracts, networkLifecycleContractSummary, networkLifecycleMutationRouteCount, networkLifecycleDryRunRouteCount, networkSetupMutationRouteRows, networkSetupMutationRouteSummary, networkLifecycleRouteRow, networkLifecycleBoundaryStatus, networkLifecycleBoundaryLines, networkRouteSummaryStatus, networkRouteSummaryLines, networkLifecycleRoutePath, networkLifecycleRouteAvailable };
  }
  window.__networkLifecycleContractModule = { createNetworkLifecycleContractModule };
})();
