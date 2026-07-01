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

  function concreteRerunPolicyValue(value, fallback) {
    const text = String(value || "").trim();
    return text && text !== "auto" ? text : fallback;
  }

  function resolveAutoRerunDestination(rawDestinationMode, rawCollisionPolicy, rawOriginalPolicy) {
    if (rawDestinationMode && rawDestinationMode !== "auto") return rawDestinationMode;
    if (rawCollisionPolicy === "replace_final") return "pending_publish";
    if (rawOriginalPolicy && rawOriginalPolicy !== "auto" && rawOriginalPolicy !== "keep") return "pending_publish";
    return "review_workspace";
  }

  function resolveAutoRerunCollision(rawCollisionPolicy, destinationMode) {
    if (rawCollisionPolicy && rawCollisionPolicy !== "auto") return rawCollisionPolicy;
    return destinationMode === "publish_replace_final" ? "replace_final" : "suffix";
  }

  function resolveAutoRerunOriginal(rawOriginalPolicy, destinationMode, collisionPolicy) {
    if (rawOriginalPolicy && rawOriginalPolicy !== "auto") return rawOriginalPolicy;
    return destinationMode === "publish_replace_final" || collisionPolicy === "replace_final"
      ? "move_to_hold_after_publish"
      : "keep";
  }

  function resolveRerunPolicySelection(raw = {}) {
    const destinationMode = resolveAutoRerunDestination(
      raw.destination_mode,
      raw.collision_policy,
      raw.original_policy,
    );
    const collisionPolicy = resolveAutoRerunCollision(raw.collision_policy, destinationMode);
    const originalPolicy = resolveAutoRerunOriginal(raw.original_policy, destinationMode, collisionPolicy);
    return {
      destination_mode: concreteRerunPolicyValue(destinationMode, "review_workspace"),
      collision_policy: concreteRerunPolicyValue(collisionPolicy, "suffix"),
      original_policy: concreteRerunPolicyValue(originalPolicy, "keep"),
    };
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
    const windowSize = Number(byId("rerun-start-window-size")?.value || 1);
    const rawPolicy = {
      destination_mode: byId("rerun-start-destination-mode")?.value || "review_workspace",
      original_policy: byId("rerun-start-original-policy")?.value || "keep",
      collision_policy: byId("rerun-start-collision-policy")?.value || "suffix",
    };
    const { destination_mode: destinationMode, original_policy: originalPolicy, collision_policy: collisionPolicy } = resolveRerunPolicySelection(rawPolicy);
    return {
      csv_path: byId("rerun-start-csv-path")?.value || "",
      dry_run: dryRun,
      plan_only: planOnly,
      execution_mode: byId("rerun-start-execution-mode")?.value || "one_at_a_time",
      destination_mode: destinationMode,
      original_policy: originalPolicy,
      collision_policy: collisionPolicy,
      window_size: Number.isFinite(windowSize) ? Math.max(1, Math.round(windowSize)) : 1,
      confirm_replace_final: destinationMode === "publish_replace_final" || collisionPolicy === "replace_final",
      confirm_original_policy: originalPolicy !== "keep",
      confirm_delete_original: originalPolicy === "hold_then_delete_after_publish",
      scope,
    };
  }

  function selectedValues(id) {
    const element = byId(id);
    if (!element || !element.options) return [];
    return Array.from(element.options)
      .filter((option) => option.selected)
      .map((option) => option.value)
      .filter(Boolean);
  }

  function collectRerunScopeRequest() {
    const firstN = Number(byId("rerun-scope-first-n")?.value || 0);
    const previewLimit = Number(byId("rerun-preview-limit")?.value || 50);
    return {
      enabled_only: byId("rerun-scope-enabled-only") ? Boolean(byId("rerun-scope-enabled-only")?.checked) : true,
      skip_blocked: Boolean(byId("rerun-scope-skip-blocked")?.checked),
      skip_warning_rows: Boolean(byId("rerun-scope-skip-warning-rows")?.checked),
      first_n: Number.isFinite(firstN) ? Math.max(0, Math.round(firstN)) : 0,
      issue_filters: selectedValues("rerun-scope-issue-filter"),
      bucket_filters: selectedValues("rerun-scope-bucket-filter"),
      preview_limit: Number.isFinite(previewLimit) ? Math.max(1, Math.round(previewLimit)) : 50,
    };
  }

  function collectRerunPreviewRequest() {
    const request = collectRerunStartRequest({ plan_only: true });
    delete request.dry_run;
    delete request.plan_only;
    return request;
  }

    return {
      launchRequestFieldValue,
      launchPreflightRequestMatches,
      collectPipelineStartRequest,
      collectRerunPreviewRequest,
      collectRerunScopeRequest,
      collectRerunStartRequest,
      resolveRerunPolicySelection,
    };
  }

  window.__launchStartRequestModule = {
    createLaunchStartRequestModule,
  };
})();
