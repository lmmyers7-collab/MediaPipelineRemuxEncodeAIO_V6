(function () {
  function createQueueRerunRequestModule(deps = {}) {
    const {
      byId = function () { return null; },
    } = deps;

    function concreteRerunPolicyValue(value, fallback) {
      const text = String(value || "").trim();
      return text && text !== "auto" ? text : fallback;
    }

    function resolveAutoRerunDestination(rawDestinationMode, rawCollisionPolicy) {
      if (rawDestinationMode && rawDestinationMode !== "auto") return rawDestinationMode;
      if (rawCollisionPolicy === "replace_final") return "auto_replace_clean_else_pending_review";
      return "review_workspace";
    }

    function resolveAutoRerunCollision(rawCollisionPolicy, destinationMode) {
      if (rawCollisionPolicy && rawCollisionPolicy !== "auto") return rawCollisionPolicy;
      return ["auto_replace_clean_else_pending_review", "publish_replace_final"].includes(destinationMode) ? "replace_final" : "suffix";
    }

    function resolveRerunPolicySelection(raw = {}) {
      const destinationMode = resolveAutoRerunDestination(
        raw.destination_mode,
        raw.collision_policy,
      );
      const collisionPolicy = resolveAutoRerunCollision(raw.collision_policy, destinationMode);
      return {
        destination_mode: concreteRerunPolicyValue(destinationMode, "auto_replace_clean_else_pending_review"),
        collision_policy: concreteRerunPolicyValue(collisionPolicy, "suffix"),
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

    function collectRerunExecutionTarget() {
      const value = String(byId("rerun-start-target-mode")?.value || "local").trim().toLowerCase();
      return value === "network" ? "network" : "local";
    }

    function collectRerunMinimumWorkerCount() {
      const value = Number(byId("rerun-network-minimum-workers")?.value || 1);
      return Number.isFinite(value) ? Math.max(0, Math.round(value)) : 1;
    }

    function collectRerunStartRequest(options = {}) {
      const planOnly = typeof options === "object" && Boolean(options.plan_only);
      const dryRun = planOnly ? false : typeof options === "boolean" ? options : Boolean(options.dry_run);
      const scope = collectRerunScopeRequest();
      const windowSize = Number(byId("rerun-start-window-size")?.value || 1);
      const rawPolicy = {
        destination_mode: byId("rerun-start-destination-mode")?.value || "auto_replace_clean_else_pending_review",
        collision_policy: byId("rerun-start-collision-policy")?.value || "replace_final",
      };
      const { destination_mode: destinationMode, collision_policy: collisionPolicy } = resolveRerunPolicySelection(rawPolicy);
      const replaceFinalRequested = destinationMode === "auto_replace_clean_else_pending_review" || destinationMode === "publish_replace_final" || collisionPolicy === "replace_final";
      const sourceOverwriteConfirmed = Boolean(byId("rerun-start-confirm-source-overwrite")?.checked);
      return {
        csv_path: byId("rerun-start-csv-path")?.value || "",
        dry_run: dryRun,
        plan_only: planOnly,
        execution_mode: byId("rerun-start-execution-mode")?.value || "one_at_a_time",
        destination_mode: destinationMode,
        collision_policy: collisionPolicy,
        window_size: Number.isFinite(windowSize) ? Math.max(1, Math.round(windowSize)) : 1,
        confirm_replace_final: replaceFinalRequested,
        confirm_source_overwrite: replaceFinalRequested && sourceOverwriteConfirmed,
        scope,
      };
    }

    function collectRerunPreviewRequest() {
      const request = collectRerunStartRequest({ plan_only: true });
      delete request.dry_run;
      delete request.plan_only;
      return request;
    }

    function collectRerunNetworkStartDryRunRequest() {
      return {
        ...collectRerunPreviewRequest(),
        minimum_worker_count: collectRerunMinimumWorkerCount(),
        reason: "WebView Network CSV rerun operator review",
      };
    }

    function collectRerunNetworkStartRequest(dryRunResult = {}) {
      const data = dryRunResult && typeof dryRunResult.data === "object" ? dryRunResult.data : dryRunResult;
      const fingerprint = String(data?.dry_run_fingerprint || "").trim();
      return {
        ...collectRerunNetworkStartDryRunRequest(),
        dry_run_fingerprint: fingerprint,
        confirm_start: true,
      };
    }

    return {
      collectRerunExecutionTarget,
      collectRerunMinimumWorkerCount,
      collectRerunNetworkStartDryRunRequest,
      collectRerunNetworkStartRequest,
      collectRerunPreviewRequest,
      collectRerunScopeRequest,
      collectRerunStartRequest,
      resolveRerunPolicySelection,
    };
  }

  window.__queueRerunRequestModule = {
    createQueueRerunRequestModule,
  };
})();
