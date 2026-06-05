(function () {
  function createLaunchScopeControlsModule(deps = {}) {
    const {
      byId = function () { return null; },
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
    const selectedScope = state.pipelineStartScope === "single_file" ? "single_file" : "queue";
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
    const status = byId("pipeline-single-file-browse-status");
    if (status && !singleFile && selectedScope === "queue" && !state.pipelineFileBrowseInFlight) {
      status.textContent = "Queue scope selected. Use Single File to stage one path.";
    }
  }

  function selectPipelineScopePreset(scope) {
    const selectedScope = String(scope || "").trim() === "single_file" ? "single_file" : "queue";
    state.pipelineStartScope = selectedScope;
    if (selectedScope === "queue") {
      const input = byId("pipeline-start-single-file");
      if (input && input.value) {
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
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
