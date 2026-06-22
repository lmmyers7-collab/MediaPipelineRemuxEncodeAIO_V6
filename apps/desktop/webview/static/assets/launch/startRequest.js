(function () {
  function createLaunchStartRequestModule(deps = {}) {
    const {
      byId = function () { return null; },
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
    const request = {
      mode,
      sleep_seconds: Number.isFinite(rawSleep) ? Math.max(1, Math.round(rawSleep)) : 30,
      show_config: Boolean(byId("pipeline-start-show-config")?.checked),
      show_console: Boolean(byId("pipeline-start-show-console")?.checked),
      schedule_override: scheduleOverride,
    };
    if (singleFile) request.single_file = singleFile;
    return request;
  }

  function collectRerunStartRequest(options = {}) {
    const planOnly = typeof options === "object" && Boolean(options.plan_only);
    const dryRun = planOnly ? false : typeof options === "boolean" ? options : Boolean(options.dry_run);
    return {
      csv_path: byId("rerun-start-csv-path")?.value || "",
      dry_run: dryRun,
      plan_only: planOnly,
      stage_mode: "copy",
      original_mode: "keep",
      return_mode: "park",
      show_console: Boolean(byId("rerun-start-show-console")?.checked),
    };
  }

    return {
      launchRequestFieldValue,
      launchPreflightRequestMatches,
      collectPipelineStartRequest,
      collectRerunStartRequest,
    };
  }

  window.__launchStartRequestModule = {
    createLaunchStartRequestModule,
  };
})();
