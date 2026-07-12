(function () {
  function createMaintenanceReleaseCommands(deps) {
    const {
      state,
      renderProgressBarsInto,
      setMaintenanceStatusText,
      releasePackageChipStatus,
      setMaintenanceDryRunBusy,
      rejectMaintenanceDryRunWhileBusy,
      setDependencyAtlasOpenBusy,
      refreshMaintenance,
      refreshChangeLedger,
      renderChangeLedgerRows,
      renderDryRunConfidence,
    } = deps;
  function releaseRequestSignature(request) {
    const payload = request || {};
    const optionKeys = [
      "destination_root",
      "zip_package",
      "verify",
      "include_tests",
      "include_dev_docs",
      "include_optional_tools",
      "include_tool_docs",
      "include_tauri_preview_binary",
      "keep_personal_config",
      "force",
    ];
    const normalized = {};
    optionKeys.forEach((key) => {
      normalized[key] = key === "destination_root"
        ? String(payload[key] || "").trim()
        : Boolean(payload[key]);
    });
    return JSON.stringify(normalized);
  }

  function recordReleasePreviewResult(request, result) {
    state.lastReleasePreviewSignature = releaseRequestSignature(request || {});
    state.lastReleasePreviewOk = Boolean(result?.ok);
    state.lastReleasePreviewMessage = String(result?.message || (result?.ok ? "Preview completed." : "Preview failed."));
  }

  function releasePreviewMatchesCreate(request) {
    return Boolean(state.lastReleasePreviewOk && state.lastReleasePreviewSignature && state.lastReleasePreviewSignature === releaseRequestSignature(request || {}));
  }

  function releaseBuildConfirmMessage(request) {
    const destination = request.destination_root || "a timestamped folder next to this bundle";
    const zipText = request.zip_package ? "and zip" : "without zip";
    const previewMatches = releasePreviewMatchesCreate(request);
    const lines = [
      `Create deployment package at ${destination} ${zipText}?`,
      "",
      `Latest matching preview: ${previewMatches ? "yes, same destination/options completed successfully." : "NO matching successful Preview Deployment is recorded for these options."}`,
      state.lastReleasePreviewMessage ? `Latest preview result: ${state.lastReleasePreviewMessage}` : "Latest preview result: none recorded in this shell.",
      `Replace existing destination: ${request.force ? "yes" : "no"}`,
      `Keep personal config: ${request.keep_personal_config ? "yes; review before sharing package output" : "no"}`,
      `Include Tauri launcher: ${request.include_tauri_preview_binary ? "yes" : "no"}`,
      "",
      "Create Deployment writes a release folder, manifest, optional zip, and selected launcher payload through the backend release builder.",
      "Rollback/readiness implication: if this package is wrong, remove the generated deployment folder/zip and rerun Preview Deployment; this action does not validate media processing, subtitles, audio, publish, or pending-drain behavior.",
    ];
    if (!previewMatches) {
      lines.push("", "Recommendation: cancel and run Preview Deployment with these exact options first unless you intentionally accept the mismatch.");
    }
    return lines.join("\n");
  }

  function collectReleaseDryRunRequest() {
    return {
      destination_root: byId("release-dry-run-destination")?.value || "",
      zip_package: Boolean(byId("release-dry-run-zip")?.checked),
      verify: Boolean(byId("release-dry-run-verify")?.checked),
      include_tests: Boolean(byId("release-dry-run-tests")?.checked),
      include_dev_docs: Boolean(byId("release-dry-run-dev-docs")?.checked),
      include_optional_tools: Boolean(byId("release-dry-run-optional-tools")?.checked),
      include_tool_docs: Boolean(byId("release-dry-run-tool-docs")?.checked),
      include_tauri_preview_binary: Boolean(byId("release-dry-run-tauri-binary")?.checked),
      keep_personal_config: Boolean(byId("release-dry-run-keep-config")?.checked),
      force: Boolean(byId("release-build-force")?.checked),
      timeout_seconds: 900,
    };
  }

  function collectReleaseBuildRequest() {
    return {
      ...collectReleaseDryRunRequest(),
      force: Boolean(byId("release-build-force")?.checked),
      confirm_create: true,
      timeout_seconds: 7200,
    };
  }

  function releasePackageKindForCommand(command) {
    const value = String(command || "");
    if (value === "maintenance.release_build") return "build";
    if (value === "maintenance.release_dry_run") return "dry-run";
    return "";
  }

  function setReleasePackageStatus(kind, status, value, hint) {
    const prefix = kind === "build" ? "release-build" : "release-dry-run";
    const chip = byId(`${prefix}-state-chip`);
    const cleanStatus = String(status || "unknown").trim().toLowerCase() || "unknown";
    const cleanValue = String(value || cleanStatus).trim();
    const cleanHint = String(hint || "").trim();
    if (chip) {
      chip.dataset.status = releasePackageChipStatus(cleanStatus);
      chip.title = cleanHint || cleanValue;
    }
    setText(`${prefix}-state-value`, cleanValue);
    if (cleanHint) setText(`${prefix}-state-hint`, cleanHint);
  }

  function releasePackageResultHint(result, fallback) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const pieces = [];
    if (result?.message) pieces.push(String(result.message));
    if (data.destination_root) pieces.push(`Destination: ${data.destination_root}`);
    const elapsed = Number(data.elapsed_seconds || 0);
    if (Number.isFinite(elapsed) && elapsed > 0) pieces.push(`Elapsed: ${elapsed.toFixed(1)}s`);
    return pieces.join(" ") || fallback;
  }

  function releasePackageResultStatus(result, completeValue) {
    const warnings = Array.isArray(result?.warnings) ? result.warnings.filter(Boolean) : [];
    if (result?.ok) {
      return {
        status: warnings.length ? "warning" : "complete",
        value: warnings.length ? `${completeValue} with warnings` : completeValue,
        hint: releasePackageResultHint(
          result,
          warnings.length ? "Finished with warnings; review the details below." : "Finished; review the details below."
        ),
      };
    }
    const severity = String(result?.severity || "").trim().toLowerCase();
    const warningState = ["warning", "review", "unknown"].includes(severity);
    return {
      status: warningState ? "warning" : "failed",
      value: severity ? severity.charAt(0).toUpperCase() + severity.slice(1) : "Failed",
      hint: releasePackageResultHint(result, "Command did not complete successfully. Review the details below."),
    };
  }

  function renderReleasePackageInFlightProgress(targetId, label, detail, source) {
    const bar = {
      id: targetId.replace(/-progress-bars$/, ""),
      label,
      mode: "indeterminate",
      status: "active",
      detail,
      source,
      stale: false,
    };
    const snapshot = {
      status: "running",
      detail,
      progress_bars: [bar],
    };
    if (typeof renderProgressBarsInto === "function") {
      renderProgressBarsInto(targetId, [bar], snapshot, detail);
    } else {
      setText(targetId, `${label}: running. ${detail}`);
    }
  }

  function initMaintenanceViewEvents() {
    const changeLedgerRefreshButton = byId("maintenance-change-ledger-refresh-button");
    if (changeLedgerRefreshButton) changeLedgerRefreshButton.addEventListener("click", refreshChangeLedger);
    [
      "maintenance-change-ledger-status-filter",
      "maintenance-change-ledger-type-filter",
      "maintenance-change-ledger-risk-filter",
      "maintenance-change-ledger-search",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", () => renderChangeLedgerRows());
      element.addEventListener("change", () => renderChangeLedgerRows());
    });
    [
      "release-dry-run-destination",
      "release-dry-run-zip",
      "release-dry-run-verify",
      "release-dry-run-tests",
      "release-dry-run-dev-docs",
      "release-dry-run-optional-tools",
      "release-dry-run-tool-docs",
      "release-dry-run-tauri-binary",
      "release-dry-run-keep-config",
      "release-build-force",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", () => renderDryRunConfidence());
      element.addEventListener("change", () => renderDryRunConfidence());
    });
    renderDryRunConfidence();
    refreshChangeLedger();
  }

  function renderReleaseDryRunResult(result) {
    const data = result?.data || {};
    const options = data.options && typeof data.options === "object" ? data.options : {};
    const state = releasePackageResultStatus(result, "Preview done");
    setReleasePackageStatus("dry-run", state.status, state.value, `${state.hint} Preview only; no release folder, manifest, or zip was written.`);
    renderReleasePackageProgress(result);
    const lines = [
      "Dry-run trust summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run === true ? "yes" : "unknown"}`,
      `Writes manifest: ${data.manifest_created === true ? "unexpected yes" : "no"}`,
      `Changes manifest: ${data.manifest_changed === true ? "unexpected yes" : "no"}`,
      `Writes zip: ${data.zip_created === true ? "unexpected yes" : "no; preview is dry-run only"}`,
      `Changes zip: ${data.zip_changed === true ? "unexpected yes" : "no; preview is dry-run only"}`,
      `Replace existing destination option: ${options.force === true ? "yes" : options.force === false ? "no" : "unknown"}`,
      `Safe next action: ${result?.ok ? "Review planned copy counts/options, destination, and package options before Create Deployment." : "Read errors and Diagnostics before trusting release packaging."}`,
      "Guardrail: Preview Deployment is a backend dry-run command; it reports zip intent but must not create release folders, zips, manifests, or copy payloads.",
      "Real-media boundary: release dry-run output does not validate FFmpeg, subtitle OCR/SRT, audio routing, output size, completed sidecars, or pending-publish behavior on media files.",
      "",
      result?.message || "Release dry run completed.",
      "",
      `Destination: ${data.destination_root || ""}`,
      `Return code: ${data.returncode ?? ""}`,
      `Elapsed: ${Number(data.elapsed_seconds || 0).toFixed(1)}s`,
      `Manifest exists after: ${data.manifest_exists === true ? "yes" : "no"}`,
      `Manifest preexisting: ${data.manifest_preexisting === true ? "yes" : "no"}`,
      `Manifest created by command: ${data.manifest_created === true ? "yes" : "no"}`,
      `Manifest changed by command: ${data.manifest_changed === true ? "yes" : "no"}`,
      `Zip exists after: ${data.zip_exists === true ? "yes" : "no"}`,
      `Zip preexisting: ${data.zip_preexisting === true ? "yes" : "no"}`,
      `Zip created by command: ${data.zip_created === true ? "yes" : "no"}`,
      `Zip changed by command: ${data.zip_changed === true ? "yes" : "no"}`,
      `Command: ${data.command || ""}`,
    ];
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    if (data.stdout) {
      lines.push("", "STDOUT", data.stdout);
    }
    if (data.stderr) {
      lines.push("", "STDERR", data.stderr);
    }
    setText("release-dry-run-detail", lines.join("\n"));
  }

  function releasePackageProgressBars(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.release_progress && typeof data.release_progress === "object" ? data.release_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
    return [];
  }

  function renderReleasePackageProgress(result, targetId = "release-dry-run-progress-bars") {
    if (typeof renderProgressBarsInto !== "function") return;
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.release_progress && typeof data.release_progress === "object" ? data.release_progress : {};
    renderProgressBarsInto(targetId, releasePackageProgressBars(result), progress, "No release package progress loaded.");
  }

  async function runReleaseDryRun() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.release_dry_run", "release-dry-run-status", "release-dry-run-detail")) return;
    const request = collectReleaseDryRunRequest();
    setMaintenanceDryRunBusy(true);
    setMaintenanceStatusText("release-dry-run-status", "Planning...", "running");
    setReleasePackageStatus(
      "dry-run",
      "running",
      "Planning",
      "Deployment package plan is running through the backend release builder."
    );
    renderReleasePackageInFlightProgress(
      "release-dry-run-progress-bars",
      "Release package plan",
      "Dry-run preview is still running; no release folder, manifest, or zip is being written.",
      "maintenance.release_dry_run"
    );
    setText("release-dry-run-detail", "Previewing deployment through the release builder with -DryRun. No release folder, zip, or manifest will be written.");
    try {
      const result = await apiPost("/api/maintenance/release-dry-run", request);
      appendCommandResult(result);
      recordReleasePreviewResult(request, result);
      setMaintenanceStatusText("release-dry-run-status", result.ok ? "Complete" : result.severity || "Failed");
      renderReleaseDryRunResult(result);
      renderDryRunConfidence();
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.release_dry_run",
        ok: false,
        severity: "error",
        message,
      });
      recordReleasePreviewResult(request, { ok: false, message });
      setMaintenanceStatusText("release-dry-run-status", "Error", "blocked");
      setReleasePackageStatus("dry-run", "failed", "Error", message);
      setText("release-dry-run-detail", message);
      renderDryRunConfidence();
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  function renderReleaseBuildResult(result) {
    const data = result?.data || {};
    const options = data.options && typeof data.options === "object" ? data.options : {};
    const state = releasePackageResultStatus(result, "Build done");
    setReleasePackageStatus("build", state.status, state.value, state.hint);
    renderReleasePackageProgress(result, "release-build-progress-bars");
    const lines = [
      "Deployment build summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run === false ? "no" : "unexpected/unknown"}`,
      `Writes release package: ${data.writes_release_package === true ? "yes" : "no"}`,
      `Manifest written: ${data.manifest_exists === true ? "yes" : "no"}`,
      `Zip written: ${data.zip_exists === true ? "yes" : "no"}`,
      `Tauri launcher requested: ${data.options?.include_tauri_preview_binary === true ? "yes" : "no"}`,
      `Replace existing destination: ${options.force === true ? "yes" : options.force === false ? "no" : "unknown"}`,
      `Safe next action: ${result?.ok ? "Open the destination, review release_manifest.json, then run package-mode validation before distribution." : "Read errors, stderr/stdout, and Diagnostics before retrying deployment."}`,
      "Guardrail: Create Deployment is backend-owned. The WebView submits options only; it does not copy files, zip folders, write manifests, or delete destinations itself.",
      "Real-media boundary: deployment packaging does not validate FFmpeg routing, subtitle OCR/SRT, audio routing, output size, completed sidecars, or pending-publish behavior on media files.",
      "",
      result?.message || "Deployment build completed.",
      "",
      `Destination: ${data.destination_root || ""}`,
      `Manifest: ${data.manifest_path || ""}`,
      `Zip: ${data.zip_path || ""}`,
      `Return code: ${data.returncode ?? ""}`,
      `Elapsed: ${Number(data.elapsed_seconds || 0).toFixed(1)}s`,
      `Command: ${data.command || ""}`,
    ];
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    if (data.stdout) {
      lines.push("", "STDOUT", data.stdout);
    }
    if (data.stderr) {
      lines.push("", "STDERR", data.stderr);
    }
    setText("release-build-detail", lines.join("\n"));
  }

  async function runReleaseBuild() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.release_build", "release-build-status", "release-build-detail")) return;
    const request = collectReleaseBuildRequest();
    if (!window.confirm(releaseBuildConfirmMessage(request))) return;
    setMaintenanceDryRunBusy(true);
    setMaintenanceStatusText("release-build-status", "Building...", "running");
    setReleasePackageStatus(
      "build",
      "running",
      "Building",
      "Deployment package is being created through the backend release builder."
    );
    renderReleasePackageInFlightProgress(
      "release-build-progress-bars",
      "Deployment package build",
      "Build is still running; controls re-enable when the backend returns.",
      "maintenance.release_build"
    );
    setText("release-build-detail", "Creating deployment package through the backend release builder. This may write a release folder, manifest, and optional zip.");
    try {
      const result = await apiPost("/api/maintenance/release-build", request);
      appendCommandResult(result);
      setMaintenanceStatusText("release-build-status", result.ok ? "Complete" : result.severity || "Failed");
      renderReleaseBuildResult(result);
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.release_build",
        ok: false,
        severity: "error",
        message,
      });
      setMaintenanceStatusText("release-build-status", "Error", "blocked");
      setReleasePackageStatus("build", "failed", "Error", message);
      setText("release-build-detail", message);
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  function renderBackfillDryRunResult(result) {
    const data = result?.data || {};
    const progress = data.backfill_progress && typeof data.backfill_progress === "object" ? data.backfill_progress : {};
    const recordsScanned = data.records_scanned ?? progress.records_scanned ?? "";
    const recordsWouldWrite = data.records_would_write ?? progress.records_would_write ?? data.sidecars_ingested ?? "";
    const recordsWritten = data.records_written ?? progress.records_written ?? 0;
    renderBackfillProgress(result);
    const lines = [
      "Dry-run trust summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Dry run: ${data.dry_run === true ? "yes" : "unknown"}`,
      `Writes completed manifest: ${data.writes_manifest === true ? "unexpected yes" : "no"}`,
      `Safe next action: ${result?.ok ? "Review sidecar and bad-JSON counts before deciding whether a backend-owned real backfill is needed." : "Read errors and Diagnostics before trusting completed-manifest state."}`,
      "Guardrail: this WebView action must remain a backend dry-run command; it must not rewrite completed manifests or checkpoints.",
      "Real-media boundary: completed-manifest backfill dry-run output does not prove media processing, subtitle conversion, audio selection, size policy, or publish completion for new work.",
      "",
      result?.message || "Completed manifest backfill dry run completed.",
      "",
      `Records scanned: ${recordsScanned}`,
      `Records would write: ${recordsWouldWrite}`,
      `Records written: ${recordsWritten}`,
      `Sidecars ingested: ${data.sidecars_ingested || ""}`,
      `Skipped bad JSON: ${data.skipped_bad_json || "0"}`,
      `Manifest: ${data.manifest_path || ""}`,
      `Checkpoint: ${data.checkpoint_path || ""}`,
      `Writes manifest: ${data.writes_manifest === true ? "yes" : "no"}`,
    ];
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    if (data.stdout) {
      lines.push("", "STDOUT", data.stdout);
    }
    setText("backfill-dry-run-detail", lines.join("\n"));
  }

  function backfillProgressBars(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.backfill_progress && typeof data.backfill_progress === "object" ? data.backfill_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
    return [];
  }

  function renderBackfillProgress(result) {
    if (typeof renderProgressBarsInto !== "function") return;
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.backfill_progress && typeof data.backfill_progress === "object" ? data.backfill_progress : {};
    renderProgressBarsInto("backfill-dry-run-progress-bars", backfillProgressBars(result), progress, "No maintenance backfill progress loaded.");
  }

  async function runBackfillDryRun() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.completed_backfill_dry_run", "backfill-dry-run-status", "backfill-dry-run-detail")) return;
    setMaintenanceDryRunBusy(true);
    setMaintenanceStatusText("backfill-dry-run-status", "Running...", "running");
    setText("backfill-dry-run-detail", "Scanning outsource sidecars with -DryRun. The completed manifest will not be rewritten.");
    try {
      const result = await apiPost("/api/maintenance/completed-backfill-dry-run", { timeout_seconds: 600 });
      appendCommandResult(result);
      setMaintenanceStatusText("backfill-dry-run-status", result.ok ? "Complete" : result.severity || "Failed");
      renderBackfillDryRunResult(result);
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.completed_backfill_dry_run",
        ok: false,
        severity: "error",
        message,
      });
      setMaintenanceStatusText("backfill-dry-run-status", "Error", "blocked");
      setText("backfill-dry-run-detail", message);
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  function dependencyAtlasProgressBars(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.dependency_atlas_progress && typeof data.dependency_atlas_progress === "object" ? data.dependency_atlas_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
    return [];
  }

  function renderDependencyAtlasProgress(result) {
    if (typeof renderProgressBarsInto !== "function") return;
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const progress = data.dependency_atlas_progress && typeof data.dependency_atlas_progress === "object" ? data.dependency_atlas_progress : {};
    renderProgressBarsInto("dependency-atlas-progress-bars", dependencyAtlasProgressBars(result), progress, "No dependency atlas progress loaded.");
  }

  function renderDependencyAtlasResult(result) {
    const data = result?.data || {};
    const atlasStale = data.stale === true || dependencyAtlasProgressBars(result).some((bar) => bar?.stale === true);
    const statusText = atlasStale ? "Stale" : result?.ok ? "Complete" : result?.severity || "Failed";
    setMaintenanceStatusText("dependency-atlas-status", statusText, atlasStale ? "stale" : statusText);
    renderDependencyAtlasProgress(result);
    const htmlPath = data.atlas_html || "docs/generated/dependency-atlas/dependency-atlas.html";
    const pngPath = data.atlas_png || "docs/generated/dependency-atlas/dependency-atlas.png";
    const lines = [
      "Dependency atlas update summary:",
      `Command accepted: ${result?.ok ? "yes" : "no"}`,
      `Writes dependency atlas artifacts: ${data.writes_dependency_atlas === true ? "yes" : "no"}`,
      `Writes media or pipeline state: ${data.writes_media === true ? "unexpected yes" : "no"}`,
      `Stale state: ${atlasStale ? "yes; rerun Update Atlas before relying on these files" : "no"}`,
      `Safe next action: ${result?.ok ? `Open ${htmlPath} or ${pngPath} from the repository root.` : "Read errors and Diagnostics before trusting the atlas files."}`,
      "Guardrail: this WebView action only asks the backend to run ops/scripts/dev/generate_dependency_atlas.py. It must not mutate media, queue state, settings, completed manifests, pending publish state, or pipeline execution.",
      "",
      result?.message || "Dependency atlas generation finished.",
      "",
      `HTML: ${data.atlas_html || ""}`,
      `PNG: ${data.atlas_png || ""}`,
      `SVG: ${data.atlas_svg || ""}`,
      `Assets: ${data.assets_dir || ""}`,
      `Summary CSV: ${data.summary_csv || ""}`,
      `Module edges CSV: ${data.module_edges_csv || ""}`,
      `Modules: ${data.modules || ""}`,
      `Domain edges: ${data.domain_edges || ""}`,
      `Detail diagrams: ${data.detail_diagrams || ""}`,
      `HTML links checked: ${data.html_links_checked || ""}`,
      `Return code: ${data.returncode ?? ""}`,
      `Elapsed: ${Number(data.elapsed_seconds || 0).toFixed(1)}s`,
      `Command: ${data.command || ""}`,
    ];
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    if (data.stdout) {
      lines.push("", "STDOUT", data.stdout);
    }
    if (data.stderr) {
      lines.push("", "STDERR", data.stderr);
    }
    setText("dependency-atlas-detail", lines.join("\n"));
  }

  async function runDependencyAtlas() {
    if (rejectMaintenanceDryRunWhileBusy("maintenance.dependency_atlas", "dependency-atlas-status", "dependency-atlas-detail")) return;
    setMaintenanceDryRunBusy(true);
    setMaintenanceStatusText("dependency-atlas-status", "Running...", "running");
    setText("dependency-atlas-detail", "Generating dependency atlas artifacts through backend tooling. This updates files under docs/generated/dependency-atlas only.");
    try {
      const result = await apiPost("/api/maintenance/dependency-atlas", {
        timeout_seconds: 600,
        min_overview_edge_count: 4,
        min_overview_files: 2,
      });
      appendCommandResult(result);
      renderDependencyAtlasResult(result);
      if ((result.refresh_hint || "") === "maintenance") {
        await refreshMaintenance();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.dependency_atlas",
        ok: false,
        severity: "error",
        message,
      });
      setMaintenanceStatusText("dependency-atlas-status", "Error", "blocked");
      setText("dependency-atlas-detail", message);
    } finally {
      setMaintenanceDryRunBusy(false);
    }
  }

  async function openDependencyAtlasFolder() {
    if (dependencyAtlasOpenInFlight) return;
    setDependencyAtlasOpenBusy(true);
    const previousDetail = byId("dependency-atlas-detail")?.textContent || "";
    setMaintenanceStatusText("dependency-atlas-status", "Opening...", "running");
    setText("dependency-atlas-detail", ["Opening dependency atlas folder through the backend allowlist.", "", previousDetail].filter(Boolean).join("\n"));
    try {
      const result = await apiPost("/api/maintenance/dependency-atlas/open-folder", {});
      appendCommandResult(result);
      if (!result.ok) {
        setMaintenanceStatusText("dependency-atlas-status", result.severity || "Open failed");
        setText("dependency-atlas-detail", result.message || "Dependency atlas folder could not be opened.");
      } else {
        setMaintenanceStatusText("dependency-atlas-status", "Opened", "ok");
        setText(
          "dependency-atlas-detail",
          [
            result.message || "Dependency atlas folder open request completed through the backend allowlist.",
            "",
            previousDetail,
          ].filter(Boolean).join("\n")
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "maintenance.dependency_atlas_open_folder",
        ok: false,
        severity: "error",
        message,
      });
      setMaintenanceStatusText("dependency-atlas-status", "Error", "blocked");
      setText("dependency-atlas-detail", message);
    } finally {
      setDependencyAtlasOpenBusy(false);
    }
  }
    return {
      releaseRequestSignature,
      recordReleasePreviewResult,
      releasePreviewMatchesCreate,
      releaseBuildConfirmMessage,
      collectReleaseDryRunRequest,
      collectReleaseBuildRequest,
      releasePackageKindForCommand,
      setReleasePackageStatus,
      releasePackageResultHint,
      releasePackageResultStatus,
      renderReleasePackageInFlightProgress,
      initMaintenanceViewEvents,
      renderReleaseDryRunResult,
      releasePackageProgressBars,
      renderReleasePackageProgress,
      runReleaseDryRun,
      renderReleaseBuildResult,
      runReleaseBuild,
      renderBackfillDryRunResult,
      backfillProgressBars,
      renderBackfillProgress,
      runBackfillDryRun,
      dependencyAtlasProgressBars,
      renderDependencyAtlasProgress,
      renderDependencyAtlasResult,
      runDependencyAtlas,
      openDependencyAtlasFolder,
    };
  }

  window.__maintenanceReleaseCommandsModule = { createMaintenanceReleaseCommands };
})();
