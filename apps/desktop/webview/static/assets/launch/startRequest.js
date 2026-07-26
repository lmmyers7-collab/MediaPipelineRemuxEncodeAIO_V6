(function () {
  function createLaunchStartRequestModule(deps = {}) {
    const {
      byId = function () { return null; },
      getPipelineStartScope = function () { return "queue"; },
    } = deps;

  function launchRequestFieldValue(request, key) {
    const value = request && typeof request === "object" ? request[key] : undefined;
    if (value === undefined || value === null) return "";
    return String(value);
  }

  function launchPreflightRequestMatches(payload, request, keys) {
    if (!payload || typeof payload !== "object") return false;
    const payloadRequest = payload.request && typeof payload.request === "object" ? payload.request : {};
    return keys.every((key) => launchRequestFieldValue(payloadRequest, key) === launchRequestFieldValue(request, key));
  }

  function collectPipelineStartRequest() {
    const rawSleep = Number(byId("pipeline-start-sleep")?.value || 30);
    const mode = byId("pipeline-start-mode")?.value || "validate";
    const scheduleOverride = byId("pipeline-start-schedule-override")?.value || "";
    const singleFile = String(byId("pipeline-start-single-file")?.value || "").trim();
    const selectedScope = String(getPipelineStartScope() || "queue");
    const request = {
      mode,
      sleep_seconds: Number.isFinite(rawSleep) ? Math.max(1, Math.round(rawSleep)) : 30,
      show_config: Boolean(byId("pipeline-start-show-config")?.checked),
      show_console: Boolean(byId("pipeline-start-show-console")?.checked),
      schedule_override: scheduleOverride,
      queue_scope: selectedScope === "priority_export" ? "priority_export" : "backend_queue",
    };
    if (selectedScope === "priority_export") {
      const exportId = String(byId("pipeline-priority-export-id")?.value || "").trim();
      if (exportId) request.priority_export_id = exportId;
    }
    if (singleFile) request.single_file = singleFile;
    return request;
  }

    return {
      launchRequestFieldValue,
      launchPreflightRequestMatches,
      collectPipelineStartRequest,
    };
  }

  window.__launchStartRequestModule = {
    createLaunchStartRequestModule,
  };
})();
