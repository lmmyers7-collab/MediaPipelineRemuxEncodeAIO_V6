(function () {
  const byIdLocal = window.byId || function (id) { return document.getElementById(id); };
  const setTextLocal = window.setText || function (id, text) {
    const node = byIdLocal(id);
    if (node) node.textContent = String(text == null ? "" : text);
  };
  const clearRowsLocal = window.clearRows || function (tbody, colspan, message) {
    if (!tbody) return;
    tbody.textContent = "";
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = colspan;
    cell.textContent = message;
    row.appendChild(cell);
    tbody.appendChild(row);
  };
  const appendCellsLocal = window.appendCells || function (row, values) {
    values.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value == null ? "" : value);
      row.appendChild(cell);
    });
  };
  const appendCommandResultLocal = window.appendCommandResult || function () {};

  const stepLabels = [
    "Welcome / Mode Selection",
    "Media Libraries",
    "Output and Publish",
    "Local Scratch",
    "FFmpeg / FFprobe Detection",
    "Hardware and Encoding",
    "Audio Policy",
    "Subtitle Policy",
    "Worker / Parallel Processing",
    "Safety and Recovery",
    "Review Summary",
    "Save",
  ];
  const profileChoices = [
    ["general_plex_direct_play", "General Plex Direct Play"],
    ["samsung_tv_plex", "Samsung TV Plex"],
    ["remux_only", "Remux Only"],
    ["manual_review", "Manual Review"],
  ];
  const mediaKinds = [["movie", "Movie"], ["tv", "TV"], ["auto", "Auto"]];
  const defaultSourceRoles = [
    ["auto", "Auto"],
    ["source_movies", "Use as SourceMovies default"],
    ["source_tv", "Use as SourceTV default"],
    ["additional", "Additional category folder"],
  ];
  const state = {
    initialized: false,
    dirty: false,
    currentStep: 0,
    defaultsLoaded: false,
    firstRunPrompted: false,
    lastPreview: null,
    deps: {},
  };

  function apiGetLocal(path) {
    return (typeof apiGet === "function" ? apiGet : window.apiGet)(path);
  }

  function apiPostLocal(path, payload) {
    return (typeof apiPost === "function" ? apiPost : window.apiPost)(path, payload);
  }

  function textValue(id) {
    return String(byIdLocal(id)?.value || "").trim();
  }

  function setValue(id, value) {
    const node = byIdLocal(id);
    if (node) node.value = value == null ? "" : String(value);
  }

  function boolValue(id) {
    return byIdLocal(id)?.checked === true;
  }

  function setChecked(id, value) {
    const node = byIdLocal(id);
    if (node) node.checked = Boolean(value);
  }

  function numberValue(id, fallback) {
    const parsed = Number.parseInt(textValue(id), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function parseListText(text) {
    return String(text || "").split(/[,;\s]+/).map((item) => item.trim()).filter(Boolean);
  }

  function optionNode(value, label, selected) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    option.selected = Boolean(selected);
    return option;
  }

  function setCurrentStep(index) {
    const bounded = Math.max(0, Math.min(stepLabels.length - 1, Number(index) || 0));
    state.currentStep = bounded;
    document.querySelectorAll("[data-wizard-step]").forEach((node) => {
      node.classList.toggle("is-active", Number(node.dataset.wizardStep) === bounded);
    });
    document.querySelectorAll("[data-wizard-step-button]").forEach((node) => {
      const active = Number(node.dataset.wizardStepButton) === bounded;
      node.setAttribute("aria-current", active ? "step" : "false");
    });
    const back = byIdLocal("settings-wizard-back-button");
    const next = byIdLocal("settings-wizard-next-button");
    if (back) back.disabled = bounded <= 0;
    if (next) next.disabled = bounded >= stepLabels.length - 1;
    setTextLocal("settings-wizard-status", stepLabels[bounded]);
  }

  function markDirty() {
    state.dirty = true;
    state.lastPreview = null;
  }

  function activateWizardTab() {
    const page = document.querySelector('[data-page-panel="settings"]');
    if (!page) return;
    page.querySelectorAll(".settings-tab-btn[data-settings-tab]").forEach((button) => {
      const active = button.dataset.settingsTab === "wizard";
      button.setAttribute("aria-selected", String(active));
    });
    page.querySelectorAll(".settings-tab-pane[data-settings-tab]").forEach((pane) => {
      pane.classList.toggle("is-active", pane.dataset.settingsTab === "wizard");
    });
    try { localStorage.setItem("mediapipeline-settings-tab", "wizard"); } catch (_error) {}
    if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
  }

  async function openWizard() {
    activateWizardTab();
    if (!state.defaultsLoaded || !state.dirty) await loadWizardDefaults();
  }

  async function loadWizardDefaults() {
    try {
      const payload = await apiGetLocal("/api/settings/wizard/defaults");
      state.defaultsLoaded = true;
      applyWizardDefaults(payload.wizard || {});
      renderToolCandidates(payload.tool_candidates || {});
      renderSettingsWizardStatus(payload.status || {});
      state.dirty = false;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setTextLocal("settings-wizard-status-detail", `Wizard defaults failed to load: ${message}`);
    }
  }

  async function loadWizardStatus() {
    try {
      const payload = await apiGetLocal("/api/settings/wizard/status");
      renderSettingsWizardStatus(payload.status || payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setTextLocal("settings-wizard-status-detail", `Wizard status failed to load: ${message}`);
    }
  }

  function applyWizardDefaults(wizard) {
    setValue("wizard-mode", wizard.mode || "first_run");
    setValue("wizard-output-container", wizard.output_container || "mkv");
    renderLibraryRows(Array.isArray(wizard.libraries) ? wizard.libraries : []);
    const output = wizard.output || {};
    setValue("wizard-output-root", output.root || "");
    setValue("wizard-publish-mode", output.publish_mode || "staged_pending");
    setValue("wizard-existing-policy", output.existing_policy || "skip_existing");
    const scratch = wizard.scratch || {};
    setValue("wizard-scratch-path", scratch.path || "");
    setValue("wizard-min-free-space-gb", wizard.min_free_space_gb || 50);
    setValue("wizard-outsource-min-free-space-gb", wizard.outsource_min_free_space_gb || 50);
    const tools = wizard.tools || {};
    setValue("wizard-ffmpeg-path", tools.ffmpeg_path || "");
    setValue("wizard-ffprobe-path", tools.ffprobe_path || "");
    const hardware = wizard.hardware || {};
    setValue("wizard-video-strategy", hardware.strategy || "remux_when_possible");
    setValue("wizard-preferred-codec", hardware.preferred_codec || "hevc_nvenc");
    setValue("wizard-video-quality", hardware.video_quality || 22);
    setValue("wizard-video-preset", hardware.video_preset || "p5");
    const audio = wizard.audio || {};
    setValue("wizard-audio-policy", audio.policy || "preserve_compatible_convert_incompatible");
    setValue("wizard-audio-codec", audio.transcode_codec || "eac3");
    setChecked("wizard-keep-all-audio", audio.keep_all_audio_tracks === true);
    const subtitles = wizard.subtitles || {};
    setValue("wizard-subtitle-policy", subtitles.policy || "keep_english_convert_supported");
    setValue("wizard-subtitle-languages", subtitles.language_text || (Array.isArray(subtitles.languages) ? subtitles.languages.join(", ") : "eng, en, english, und"));
    setChecked("wizard-keep-unknown-subtitles", subtitles.keep_unknown !== false);
    setChecked("wizard-preserve-forced-subtitles", subtitles.preserve_forced !== false);
    setValue("wizard-max-parallel-encodes", wizard.workers?.max_parallel_encodes || 1);
    setValue("wizard-parallel-encode-mode", wizard.workers?.parallel_encode_mode || "single");
    const safety = wizard.safety || {};
    setChecked("wizard-safety-integrity", safety.integrity_check !== false);
    setChecked("wizard-safety-stability", safety.file_stability_checks !== false);
    setChecked("wizard-safety-pending", safety.pending_publish !== false);
    setChecked("wizard-safety-skip-processed", safety.skip_already_processed !== false);
    setValue("wizard-retry-limit", safety.retry_limit || 3);
    setChecked("wizard-danger-allow-system-tools", safety.allow_system_tools === true);
    setChecked("wizard-danger-allow-no-audio", safety.allow_no_audio === true);
    setChecked("wizard-danger-cleanup-remote", safety.cleanup_remote_staging === true);
    setChecked("wizard-danger-reprocess-all", output.existing_policy === "reprocess_all_once");
    ["AllowSystemTools", "AllowNoAudio", "CleanupRemoteStaging", "ReprocessAll"].forEach((key) => {
      setChecked(`wizard-ack-${key}`, false);
    });
  }

  function renderToolCandidates(candidates) {
    const firstExisting = (rows) => (Array.isArray(rows) ? rows.find((row) => row.exists)?.path || "" : "");
    if (!textValue("wizard-ffmpeg-path")) setValue("wizard-ffmpeg-path", firstExisting(candidates.ffmpeg));
    if (!textValue("wizard-ffprobe-path")) setValue("wizard-ffprobe-path", firstExisting(candidates.ffprobe));
  }

  function createLibraryRow(library, index) {
    const section = document.createElement("section");
    section.className = "settings-wizard-library-row";
    section.dataset.libraryIndex = String(index);
    section.innerHTML = `
      <div class="settings-wizard-library-title">
        <label><input type="checkbox" data-library-field="enabled"> Enabled</label>
        <button type="button" class="secondary-button" data-library-remove>Remove</button>
      </div>
      <div class="form-grid form-grid-dense">
        <label>Friendly name *<input type="text" data-library-field="name" autocomplete="off"></label>
        <label>Category<input type="text" data-library-field="category" list="wizard-library-category-list" autocomplete="off"></label>
        <label>Media kind<select data-library-field="media_kind"></select></label>
        <label>Default root role<select data-library-field="default_source_role"></select></label>
        <label>Source path *<input type="text" data-library-field="source_path" autocomplete="off"></label>
        <label>Processing profile<select data-library-field="profile"></select></label>
      </div>
    `;
    section.querySelector('[data-library-field="enabled"]').checked = library.enabled !== false;
    section.querySelector('[data-library-field="name"]').value = library.name || `Library ${index + 1}`;
    section.querySelector('[data-library-field="source_path"]').value = library.source_path || "";
    section.querySelector('[data-library-field="category"]').value = library.category || "other";
    const roleSelect = section.querySelector('[data-library-field="default_source_role"]');
    defaultSourceRoles.forEach(([value, label]) => roleSelect.appendChild(optionNode(value, label, value === (library.default_source_role || "auto"))));
    const kindSelect = section.querySelector('[data-library-field="media_kind"]');
    mediaKinds.forEach(([value, label]) => kindSelect.appendChild(optionNode(value, label, value === (library.media_kind || "auto"))));
    const profileSelect = section.querySelector('[data-library-field="profile"]');
    profileChoices.forEach(([value, label]) => profileSelect.appendChild(optionNode(value, label, value === (library.profile || "general_plex_direct_play"))));
    section.querySelectorAll("input, select").forEach((node) => {
      node.addEventListener("input", markDirty);
      node.addEventListener("change", markDirty);
    });
    section.querySelector("[data-library-remove]").addEventListener("click", () => {
      section.remove();
      markDirty();
    });
    return section;
  }

  function renderLibraryRows(libraries) {
    const container = byIdLocal("settings-wizard-library-list");
    if (!container) return;
    container.textContent = "";
    const rows = libraries.length ? libraries : [
      { name: "Movies", media_kind: "movie", category: "movies", default_source_role: "source_movies", source_path: "", enabled: true, profile: "general_plex_direct_play" },
      { name: "TV", media_kind: "tv", category: "tv", default_source_role: "source_tv", source_path: "", enabled: true, profile: "general_plex_direct_play" },
    ];
    rows.forEach((library, index) => container.appendChild(createLibraryRow(library, index)));
  }

  function addLibraryRow() {
    const container = byIdLocal("settings-wizard-library-list");
    if (!container) return;
    const index = container.querySelectorAll(".settings-wizard-library-row").length;
    container.appendChild(createLibraryRow({
      name: `Library ${index + 1}`,
      media_kind: "auto",
      category: "other",
      default_source_role: "additional",
      enabled: true,
      profile: "general_plex_direct_play",
    }, index));
    markDirty();
  }

  function collectLibraries() {
    return Array.from(document.querySelectorAll(".settings-wizard-library-row")).map((row, index) => ({
      id: `library_${index + 1}`,
      enabled: row.querySelector('[data-library-field="enabled"]')?.checked === true,
      name: String(row.querySelector('[data-library-field="name"]')?.value || "").trim(),
      category: String(row.querySelector('[data-library-field="category"]')?.value || "other").trim(),
      media_kind: String(row.querySelector('[data-library-field="media_kind"]')?.value || "auto").trim(),
      default_source_role: String(row.querySelector('[data-library-field="default_source_role"]')?.value || "auto").trim(),
      source_path: String(row.querySelector('[data-library-field="source_path"]')?.value || "").trim(),
      profile: String(row.querySelector('[data-library-field="profile"]')?.value || "general_plex_direct_play").trim(),
    }));
  }

  function collectDangerAck() {
    return ["AllowSystemTools", "AllowNoAudio", "CleanupRemoteStaging", "ReprocessAll"]
      .filter((key) => boolValue(`wizard-ack-${key}`));
  }

  function collectWizardPayload() {
    const existingPolicy = boolValue("wizard-danger-reprocess-all") ? "reprocess_all_once" : textValue("wizard-existing-policy");
    return {
      mode: textValue("wizard-mode") || "first_run",
      output_container: textValue("wizard-output-container") || "mkv",
      libraries: collectLibraries(),
      output: {
        root: textValue("wizard-output-root"),
        publish_mode: textValue("wizard-publish-mode") || "staged_pending",
        existing_policy: existingPolicy || "skip_existing",
      },
      scratch: { path: textValue("wizard-scratch-path") },
      tools: { ffmpeg_path: textValue("wizard-ffmpeg-path"), ffprobe_path: textValue("wizard-ffprobe-path") },
      hardware: {
        strategy: textValue("wizard-video-strategy") || "remux_when_possible",
        preferred_codec: textValue("wizard-preferred-codec") || "hevc_nvenc",
        video_quality: numberValue("wizard-video-quality", 22),
        video_preset: textValue("wizard-video-preset") || "p5",
      },
      audio: {
        policy: textValue("wizard-audio-policy") || "preserve_compatible_convert_incompatible",
        transcode_codec: textValue("wizard-audio-codec") || "eac3",
        keep_all_audio_tracks: boolValue("wizard-keep-all-audio"),
      },
      subtitles: {
        policy: textValue("wizard-subtitle-policy") || "keep_english_convert_supported",
        languages: parseListText(textValue("wizard-subtitle-languages")),
        language_text: textValue("wizard-subtitle-languages"),
        keep_unknown: boolValue("wizard-keep-unknown-subtitles"),
        preserve_forced: boolValue("wizard-preserve-forced-subtitles"),
      },
      workers: {
        max_parallel_encodes: numberValue("wizard-max-parallel-encodes", 1),
        parallel_encode_mode: textValue("wizard-parallel-encode-mode") || "single",
      },
      safety: {
        integrity_check: boolValue("wizard-safety-integrity"),
        file_stability_checks: boolValue("wizard-safety-stability"),
        pending_publish: boolValue("wizard-safety-pending"),
        skip_already_processed: boolValue("wizard-safety-skip-processed"),
        retry_limit: numberValue("wizard-retry-limit", 3),
        allow_system_tools: boolValue("wizard-danger-allow-system-tools"),
        allow_no_audio: boolValue("wizard-danger-allow-no-audio"),
        cleanup_remote_staging: boolValue("wizard-danger-cleanup-remote"),
        danger_ack: collectDangerAck(),
      },
      min_free_space_gb: numberValue("wizard-min-free-space-gb", 50),
      outsource_min_free_space_gb: numberValue("wizard-outsource-min-free-space-gb", 50),
    };
  }

  async function runWizardCommand(command, statusId, fn) {
    if (state.deps.rejectSettingsCommandWhileBusy && state.deps.rejectSettingsCommandWhileBusy(command, statusId, "")) return null;
    if (state.deps.setSettingsCommandBusy) state.deps.setSettingsCommandBusy(true);
    try {
      const result = await fn();
      appendCommandResultLocal(result);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = { command, ok: false, severity: "error", message };
      appendCommandResultLocal(result);
      setTextLocal(statusId, message);
      return result;
    } finally {
      if (state.deps.setSettingsCommandBusy) state.deps.setSettingsCommandBusy(false);
    }
  }

  function validationText(data) {
    const errors = data.errors || [];
    const warnings = data.warnings || [];
    const lines = [
      errors.length ? `Blocked: ${errors.length} issue(s)` : "No hard blockers.",
      ...errors.map((item) => `- ${item}`),
      warnings.length ? `Warnings: ${warnings.length}` : "No warnings.",
      ...warnings.map((item) => `- ${item}`),
    ];
    if (data.path_validation?.rows) lines.push("", `Paths checked: ${data.path_validation.rows.length}`);
    return lines.join("\n");
  }

  async function validatePaths() {
    const result = await runWizardCommand("settings.wizard.validate_paths", "settings-wizard-status-detail", () => (
      apiPostLocal("/api/settings/wizard/validate-paths", { wizard: collectWizardPayload() })
    ));
    if (result) {
      setTextLocal("settings-wizard-validation-summary", validationText(result.data || result));
      setTextLocal("settings-wizard-status-detail", result.message || "Path validation completed.");
    }
  }

  async function detectTools() {
    const result = await runWizardCommand("settings.wizard.validate_tools", "settings-wizard-tools-result", () => (
      apiPostLocal("/api/settings/wizard/validate-tools", { wizard: collectWizardPayload() })
    ));
    if (result) {
      const data = result.data || {};
      setTextLocal("settings-wizard-tools-result", [
        result.message || "Tool validation completed.",
        `FFmpeg: ${data.ffmpeg?.ok ? "PASS" : "WARN"} ${data.ffmpeg?.path || ""}`,
        `FFprobe: ${data.ffprobe?.ok ? "PASS" : "WARN"} ${data.ffprobe?.path || ""}`,
        ...(data.warnings || []),
      ].filter(Boolean).join("\n"));
    }
  }

  async function probeHardware() {
    const result = await runWizardCommand("settings.wizard.probe_hardware", "settings-wizard-hardware-result", () => (
      apiPostLocal("/api/settings/wizard/probe-hardware", { wizard: collectWizardPayload() })
    ));
    if (result) {
      const data = result.data || {};
      setTextLocal("settings-wizard-hardware-result", [
        result.message || "Encoder probe completed.",
        `Detected encoders: ${(data.detected_encoders || []).join(", ") || "none"}`,
        ...(data.warnings || []),
        ...(data.errors || []),
      ].filter(Boolean).join("\n"));
    }
  }

  async function validateWorkers() {
    const result = await runWizardCommand("settings.wizard.validate_workers", "settings-wizard-workers-result", () => (
      apiPostLocal("/api/settings/wizard/validate-workers", { wizard: collectWizardPayload() })
    ));
    if (result) setTextLocal("settings-wizard-workers-result", validationText(result.data || result));
  }

  function renderSummaryRows(rows) {
    const tbody = byIdLocal("settings-wizard-summary-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRowsLocal(tbody, 3, "No summary loaded.");
      return;
    }
    tbody.textContent = "";
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCellsLocal(row, [item.category || "", item.status || "", item.detail || ""]);
      tbody.appendChild(row);
    });
  }

  function renderPreview(result) {
    const data = result.data || {};
    const wizard = data.wizard || data;
    const changedKeys = data.changed_keys || wizard.changed_keys || Object.keys(wizard.changes || {});
    setTextLocal("settings-wizard-review-summary", [
      result.message || "Preview completed.",
      `Changed keys: ${changedKeys.join(", ") || "none"}`,
      "",
      "Warnings:",
      ...((result.warnings || wizard.warnings || []).length ? (result.warnings || wizard.warnings || []) : ["none"]),
      "",
      "Errors:",
      ...((result.errors || wizard.errors || []).length ? (result.errors || wizard.errors || []) : ["none"]),
    ].join("\n"));
    renderSummaryRows(wizard.summary?.categories || []);
    setTextLocal("settings-wizard-validation-summary", validationText(wizard));
  }

  async function previewWizard() {
    const result = await runWizardCommand("settings.wizard.preview", "settings-wizard-review-summary", () => (
      apiPostLocal("/api/settings/wizard/preview", { wizard: collectWizardPayload() })
    ));
    if (result) {
      state.lastPreview = result;
      renderPreview(result);
    }
  }

  async function saveWizard() {
    const confirmed = typeof window.confirm === "function"
      ? window.confirm("Save Settings Wizard config to the active PSD1? A backup will be created first.")
      : true;
    if (!confirmed) {
      setTextLocal("settings-wizard-save-result", "Save cancelled.");
      return;
    }
    const result = await runWizardCommand("settings.wizard.save", "settings-wizard-save-result", () => (
      apiPostLocal("/api/settings/wizard/save", { wizard: collectWizardPayload(), confirm_save: true })
    ));
    if (result) {
      const data = result.data || {};
      setTextLocal("settings-wizard-save-result", [
        result.message || "Save completed.",
        `Writes config: ${data.writes_config ? "yes" : "no"}`,
        `Backup: ${data.backup_path || "none"}`,
        `Reloaded: ${data.reloaded === false ? "no" : "yes or not needed"}`,
        ...(result.warnings || []),
        ...(result.errors || []),
      ].filter(Boolean).join("\n"));
      if (result.ok) {
        state.dirty = false;
        if (typeof state.deps.refreshAll === "function") state.deps.refreshAll();
      }
    }
  }

  async function copyDiagnostics() {
    const text = [
      "Settings Wizard Diagnostic Summary",
      `Step: ${stepLabels[state.currentStep]}`,
      "",
      byIdLocal("settings-wizard-review-summary")?.textContent || "",
      "",
      byIdLocal("settings-wizard-validation-summary")?.textContent || "",
      "",
      byIdLocal("settings-wizard-tools-result")?.textContent || "",
      "",
      byIdLocal("settings-wizard-hardware-result")?.textContent || "",
      "",
      byIdLocal("settings-wizard-workers-result")?.textContent || "",
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setTextLocal("settings-wizard-status-detail", "Diagnostic summary copied.");
    } catch (_error) {
      setTextLocal("settings-wizard-status-detail", text);
    }
  }

  function renderSettingsWizardStatus(status) {
    if (!status || typeof status !== "object") return;
    setTextLocal("settings-wizard-status-detail", status.message || "Settings Wizard is available.");
    if (!state.dirty && status.status) setTextLocal("settings-wizard-status", status.status);
    if (status.should_open_wizard && !state.firstRunPrompted) {
      state.firstRunPrompted = true;
      try {
        if (sessionStorage.getItem("mediapipeline-settings-wizard-first-run-opened")) return;
        sessionStorage.setItem("mediapipeline-settings-wizard-first-run-opened", "1");
      } catch (_error) {}
      openWizard();
    }
  }

  function initSettingsWizardEvents(deps) {
    if (state.initialized) return;
    state.initialized = true;
    state.deps = deps || {};
    document.querySelectorAll("[data-wizard-step-button]").forEach((button) => {
      button.addEventListener("click", () => setCurrentStep(button.dataset.wizardStepButton));
    });
    byIdLocal("settings-wizard-back-button")?.addEventListener("click", () => setCurrentStep(state.currentStep - 1));
    byIdLocal("settings-wizard-next-button")?.addEventListener("click", () => setCurrentStep(state.currentStep + 1));
    byIdLocal("settings-open-wizard-button")?.addEventListener("click", openWizard);
    byIdLocal("settings-wizard-add-library-button")?.addEventListener("click", addLibraryRow);
    byIdLocal("settings-wizard-validate-paths-button")?.addEventListener("click", validatePaths);
    byIdLocal("settings-wizard-detect-tools-button")?.addEventListener("click", detectTools);
    byIdLocal("settings-wizard-probe-hardware-button")?.addEventListener("click", probeHardware);
    byIdLocal("settings-wizard-validate-workers-button")?.addEventListener("click", validateWorkers);
    byIdLocal("settings-wizard-preview-button")?.addEventListener("click", previewWizard);
    byIdLocal("settings-wizard-save-button")?.addEventListener("click", saveWizard);
    byIdLocal("settings-wizard-copy-diagnostics-button")?.addEventListener("click", copyDiagnostics);
    document.querySelectorAll(".settings-wizard-panel input, .settings-wizard-panel select").forEach((node) => {
      node.addEventListener("input", markDirty);
      node.addEventListener("change", markDirty);
    });
    setCurrentStep(0);
    loadWizardStatus();
    loadWizardDefaults();
  }

  /**
   * Public namespace for the Settings wizard surface; flat window.* exports remain compatibility-only.
   */
  window.mediaPipelineSettingsWizard = {
    collectWizardPayload,
    initSettingsWizardEvents,
    loadWizardDefaults,
    loadWizardStatus,
    openWizard,
    renderSettingsWizardStatus,
    setCurrentStep,
  };
})();
