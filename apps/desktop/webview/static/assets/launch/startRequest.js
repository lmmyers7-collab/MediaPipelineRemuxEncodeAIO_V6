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
    const scope = collectRerunScopeRequest();
    return {
      csv_path: byId("rerun-start-csv-path")?.value || "",
      dry_run: dryRun,
      plan_only: planOnly,
      stage_mode: byId("rerun-start-stage-mode")?.value || "copy",
      original_mode: byId("rerun-start-original-mode")?.value || "keep",
      return_mode: byId("rerun-start-return-mode")?.value || "park",
      scope,
      show_console: Boolean(byId("rerun-start-show-console")?.checked),
    };
  }

  function collectRerunScopeRequest() {
    const firstN = Number(byId("rerun-scope-first-n")?.value || 0);
    const previewLimit = Number(byId("rerun-preview-limit")?.value || 50);
    return {
      enabled_only: byId("rerun-scope-enabled-only") ? Boolean(byId("rerun-scope-enabled-only")?.checked) : true,
      skip_blocked: Boolean(byId("rerun-scope-skip-blocked")?.checked),
      skip_warning_rows: Boolean(byId("rerun-scope-skip-warning-rows")?.checked),
      first_n: Number.isFinite(firstN) ? Math.max(0, Math.round(firstN)) : 0,
      issue_filter: byId("rerun-scope-issue-filter")?.value || "",
      bucket_filter: byId("rerun-scope-bucket-filter")?.value || "",
      preview_limit: Number.isFinite(previewLimit) ? Math.max(1, Math.round(previewLimit)) : 50,
    };
  }

  function collectRerunPreviewRequest() {
    const request = collectRerunStartRequest({ plan_only: true });
    delete request.dry_run;
    delete request.plan_only;
    delete request.show_console;
    return request;
  }

    return {
      launchRequestFieldValue,
      launchPreflightRequestMatches,
      collectPipelineStartRequest,
      collectRerunPreviewRequest,
      collectRerunScopeRequest,
      collectRerunStartRequest,
    };
  }

  window.__launchStartRequestModule = {
    createLaunchStartRequestModule,
  };
})();
