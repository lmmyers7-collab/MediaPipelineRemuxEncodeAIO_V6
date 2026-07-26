(function () {
  function createLaunchScopeControlsModule(deps = {}) {
    const {
      byId = function () { return null; },
      apiGet = async function () { return {}; },
      onControlsChanged = function () {},
      renderAllLaunchPreflights = function () {},
      setPipelineSingleFileBrowseStatus = function () {},
      state = {
        launchCommandInFlight: false,
        pipelineFileBrowseInFlight: false,
        pipelineStartScope: "queue",
      },
    } = deps;

  function pipelineSingleFileValue() {
    return String(byId("pipeline-start-single-file")?.value || "").trim();
  }

  function pipelineModeLabel(mode) {
    const labels = {
      validate: "Validate",
      once: "Run Once",
      continuous: "Continuous",
      drain_pending_pushes: "Publish Parked",
    };
    return labels[mode] || mode || "Pipeline";
  }

  function pipelineModeStartLabel(mode) {
    return `Start ${pipelineModeLabel(mode)}`;
  }

  function syncPipelineScopeControls() {
    const singleFile = pipelineSingleFileValue();
    if (singleFile) state.pipelineStartScope = "single_file";
    const selectedScope = ["queue", "priority_export", "single_file"].includes(state.pipelineStartScope)
      ? state.pipelineStartScope
      : "queue";
    document.querySelectorAll("[data-pipeline-scope-preset]").forEach((button) => {
      const active = String(button.dataset.pipelineScopePreset || "") === selectedScope;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const singleFileContainer = document.querySelector("[data-pipeline-single-file-container]");
    if (singleFileContainer) {
      const show = selectedScope === "single_file" || Boolean(singleFile);
      singleFileContainer.hidden = !show;
      singleFileContainer.setAttribute("aria-hidden", show ? "false" : "true");
    }
    const priorityExportContainer = document.querySelector("[data-pipeline-priority-export-container]");
    if (priorityExportContainer) {
      const show = selectedScope === "priority_export";
      priorityExportContainer.hidden = !show;
      priorityExportContainer.setAttribute("aria-hidden", show ? "false" : "true");
    }
    document.querySelectorAll("[data-pipeline-mode-preset]").forEach((button) => {
      button.disabled = selectedScope === "priority_export" && String(button.dataset.pipelineModePreset || "") !== "once";
    });
    const status = byId("pipeline-single-file-browse-status");
    if (status && !singleFile && selectedScope === "queue" && !state.pipelineFileBrowseInFlight) {
      status.textContent = "Backend queue scope selected. This uses backend queue, schedule, and settings scope, not Queue tab visible or selected rows. Use Single File to stage one path.";
    }
  }

  async function loadPriorityExportStatus() {
    const status = byId("pipeline-priority-export-status");
    const idInput = byId("pipeline-priority-export-id");
    if (status) status.textContent = "Loading the latest backend-owned priority export...";
    if (idInput) {
      idInput.value = "";
      idInput.dataset.exportCount = "0";
    }
    try {
      const payload = await apiGet("/api/queue/priority-export");
      const ready = Boolean(payload?.ready) && String(payload?.status || "").toLowerCase() === "ready";
      const count = Number(payload?.count || 0);
      const exportId = String(payload?.export_id || "");
      if (ready && exportId) {
        if (idInput) {
          idInput.value = exportId;
          idInput.dataset.exportCount = String(count);
        }
        if (status) status.textContent = `Ready: ${count} exported item${count === 1 ? "" : "s"}. Run Once will submit export ID ${exportId}; browser rows are not submitted.`;
      } else if (status) {
        status.textContent = payload?.message || "No ready priority export exists. Prepare one from Queue first.";
      }
    } catch (error) {
      if (status) status.textContent = `Priority export status failed to load: ${error}`;
    }
    renderAllLaunchPreflights();
    onControlsChanged();
  }

  function selectPipelineScopePreset(scope) {
    const requestedScope = String(scope || "").trim();
    const selectedScope = ["queue", "priority_export", "single_file"].includes(requestedScope) ? requestedScope : "queue";
    state.pipelineStartScope = selectedScope;
    if (selectedScope !== "single_file") {
      const input = byId("pipeline-start-single-file");
      if (input && input.value) {
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
    if (selectedScope === "priority_export") {
      const modeSelect = byId("pipeline-start-mode");
      if (modeSelect && modeSelect.value !== "once") {
        modeSelect.value = "once";
        modeSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
      void loadPriorityExportStatus();
    }
    syncPipelineScopeControls();
    renderAllLaunchPreflights();
    onControlsChanged();
  }

  function syncPipelineModeControls() {
    const selectedMode = byId("pipeline-start-mode")?.value || "validate";
    document.querySelectorAll("[data-pipeline-mode-preset]").forEach((button) => {
      const active = String(button.dataset.pipelineModePreset || "") === selectedMode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const startButton = byId("pipeline-start-button");
    if (startButton && !state.launchCommandInFlight) {
      startButton.textContent = pipelineModeStartLabel(selectedMode);
    }
    syncPipelineScopeControls();
  }

  function selectPipelineModePreset(mode) {
    const selectedMode = String(mode || "").trim();
    const modeSelect = byId("pipeline-start-mode");
    if (!selectedMode || !modeSelect) return;
    modeSelect.value = selectedMode;
    syncPipelineModeControls();
    modeSelect.dispatchEvent(new Event("change", { bubbles: true }));
  }

    return {
      pipelineSingleFileValue,
      pipelineModeLabel,
      pipelineModeStartLabel,
      loadPriorityExportStatus,
      syncPipelineScopeControls,
      selectPipelineScopePreset,
      syncPipelineModeControls,
      selectPipelineModePreset,
    };
  }

  window.__launchScopeControlsModule = {
    createLaunchScopeControlsModule,
  };
})();
