(function () {
  const RERUN_PREVIEW_ROUTE = "/api/rerun/preview";
  const RERUN_NETWORK_PREVIEW_ROUTE = "/api/rerun/network-preview";
  const RERUN_NETWORK_START_DRY_RUN_ROUTE = "/api/rerun/network/start-dry-run";
  const RERUN_NETWORK_START_ROUTE = "/api/rerun/network/start";
  const RERUN_START_ROUTE = "/api/rerun/start";
  const RERUN_RESULTS_ROUTE = "/api/rerun/results?limit=24";
  const RERUN_CONTROL_ROUTE = "/api/rerun/control";
  const RERUN_CONTINUE_ROUTE = "/api/rerun/continue";
  const RERUN_OPEN_ROUTE = "/api/rerun/open";
  const RERUN_PROMOTE_DRY_RUN_ROUTE = "/api/rerun/promote-dry-run";
  const RERUN_PROMOTE_ROUTE = "/api/rerun/promote";
  const DIAGNOSTICS_OPEN_ROUTE = "/api/diagnostics/open";
  const COMMAND_HISTORY_ROUTE = "/api/commands?limit=20";
  const RERUN_DIAGNOSTICS_TARGETS = new Set(["run_logs", "last_stdout_log", "last_stderr_log", "active_jobs"]);

  function createQueueRerunApiModule(deps = {}) {
    const configuredApiGet = typeof deps.apiGet === "function" ? deps.apiGet : window.apiGet;
    const configuredApiPost = typeof deps.apiPost === "function" ? deps.apiPost : window.apiPost;

    function currentApiPost() {
      return typeof window.apiPost === "function" ? window.apiPost : configuredApiPost;
    }

    function currentApiGet() {
      return typeof window.apiGet === "function" ? window.apiGet : configuredApiGet;
    }

    function requireApiPost(routeName) {
      const post = currentApiPost();
      if (typeof post === "function") return post;
      throw new Error(`CSV rerun backend route dispatcher is unavailable for ${routeName}.`);
    }

    function requireApiGet(routeName) {
      const get = currentApiGet();
      if (typeof get === "function") return get;
      throw new Error(`CSV rerun backend route dispatcher is unavailable for ${routeName}.`);
    }

    async function postRerunPreview(request) {
      return requireApiPost(RERUN_PREVIEW_ROUTE)("/api/rerun/preview", request);
    }

    async function postRerunNetworkPreview(request) {
      return requireApiPost(RERUN_NETWORK_PREVIEW_ROUTE)("/api/rerun/network-preview", request);
    }

    async function postRerunNetworkStartDryRun(request) {
      return requireApiPost(RERUN_NETWORK_START_DRY_RUN_ROUTE)("/api/rerun/network/start-dry-run", request);
    }

    async function postRerunNetworkStart(request) {
      return requireApiPost(RERUN_NETWORK_START_ROUTE)("/api/rerun/network/start", request);
    }

    async function postRerunStart(request) {
      return requireApiPost(RERUN_START_ROUTE)("/api/rerun/start", request);
    }

    async function postRerunControlStopAfterCurrent() {
      return requireApiPost(RERUN_CONTROL_ROUTE)("/api/rerun/control", { action: "stop_after_current", confirm_stop: true });
    }

    async function postRerunControlPause() {
      return requireApiPost(RERUN_CONTROL_ROUTE)("/api/rerun/control", { action: "pause", confirm_pause: true });
    }

    async function postRerunContinue(request) {
      return requireApiPost(RERUN_CONTINUE_ROUTE)("/api/rerun/continue", request);
    }

    async function postRerunOpen(request) {
      return requireApiPost(RERUN_OPEN_ROUTE)("/api/rerun/open", request);
    }

    async function postDiagnosticsOpen(target) {
      return requireApiPost(DIAGNOSTICS_OPEN_ROUTE)("/api/diagnostics/open", { target });
    }

    async function postRerunPromoteDryRun(rowKey) {
      return requireApiPost(RERUN_PROMOTE_DRY_RUN_ROUTE)("/api/rerun/promote-dry-run", { row_key: rowKey });
    }

    async function postRerunPromote(request) {
      return requireApiPost(RERUN_PROMOTE_ROUTE)("/api/rerun/promote", request);
    }

    async function getRerunResults() {
      return requireApiGet(RERUN_RESULTS_ROUTE)("/api/rerun/results?limit=24", { timeoutMs: 15000 });
    }

    async function getCommandHistory() {
      return requireApiGet(COMMAND_HISTORY_ROUTE)("/api/commands?limit=20", { timeoutMs: 15000 });
    }

    return {
      RERUN_PREVIEW_ROUTE,
      RERUN_NETWORK_PREVIEW_ROUTE,
      RERUN_NETWORK_START_DRY_RUN_ROUTE,
      RERUN_NETWORK_START_ROUTE,
      RERUN_START_ROUTE,
      RERUN_RESULTS_ROUTE,
      RERUN_CONTROL_ROUTE,
      RERUN_CONTINUE_ROUTE,
      RERUN_OPEN_ROUTE,
      RERUN_PROMOTE_DRY_RUN_ROUTE,
      RERUN_PROMOTE_ROUTE,
      DIAGNOSTICS_OPEN_ROUTE,
      COMMAND_HISTORY_ROUTE,
      RERUN_DIAGNOSTICS_TARGETS,
      currentApiPost,
      currentApiGet,
      requireApiPost,
      requireApiGet,
      postRerunPreview,
      postRerunNetworkPreview,
      postRerunNetworkStartDryRun,
      postRerunNetworkStart,
      postRerunStart,
      postRerunControlStopAfterCurrent,
      postRerunControlPause,
      postRerunContinue,
      postRerunOpen,
      postDiagnosticsOpen,
      postRerunPromoteDryRun,
      postRerunPromote,
      getRerunResults,
      getCommandHistory,
    };
  }

  window.__queueRerunApiModule = {
    createQueueRerunApiModule,
  };
})();
