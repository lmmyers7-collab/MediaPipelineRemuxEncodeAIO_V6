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

  const WIZARD_TAB_ID = "guided-setup";
  const stepLabels = ["Start", "Paths", "Toolchain", "Policy", "Review & Save"];
  const riskAckRules = [
    { key: "AllowSystemTools", inputId: "wizard-danger-allow-system-tools" },
    { key: "AllowNoAudio", inputId: "wizard-danger-allow-no-audio" },
    { key: "CleanupRemoteStaging", inputId: "wizard-danger-cleanup-remote" },
    { key: "ReprocessAll", inputId: "wizard-danger-reprocess-all", selectValueId: "wizard-existing-policy", selectValue: "reprocess_all_once" },
  ];
  const profileChoices = [
    ["general_plex_direct_play", "General Plex Direct Play"],
    ["samsung_tv_plex", "Samsung TV Plex"],
    ["remux_only", "Remux Only"],
    ["manual_review", "Manual Review"],
  ];
  const designations = [["movie", "Movie"], ["tv", "TV"], ["auto", "Auto"]];
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
    lastPreviewSignature: "",
    commandBusy: false,
    pathValidation: null,
    pathValidationSignature: "",
    toolsValidation: null,
    toolsValidationSignature: "",
    hardwareProbe: null,
    hardwareProbeSignature: "",
    workerValidation: null,
    workerValidationSignature: "",
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
    if (node) {
      node.value = value == null ? "" : String(value);
      syncWizardChoiceGroup(node);
    }
  }

  const wizardChoiceGroupConfigs = {
    "wizard-mode": {
      descriptions: {
        first_run: "Start from bundled defaults and complete required operator paths.",
        reconfigure: "Keep existing settings visible while changing a smaller set of values.",
      },
    },
    "wizard-output-container": {
      descriptions: {
        mkv: "Best fit for multiple audio and subtitle tracks.",
        mp4: "Use only when the target playback environment needs MP4.",
      },
    },
    "wizard-publish-mode": {
      descriptions: {
        staged_pending: "Park unsafe final writes until the backend can drain them with manifest evidence.",
        immediate: "Publish directly when the final root passes backend safety checks.",
        review_required: "Require operator review before publishing completed outputs.",
      },
    },
    "wizard-existing-policy": {
      descriptions: {
        skip_existing: "Leave already processed titles alone.",
        review_existing: "Stop for review when a matching output is already present.",
        reprocess_all_once: "Force one pass through existing titles.",
      },
    },
    "wizard-video-strategy": {
      descriptions: {
        remux_when_possible: "Prefer copy/remux paths and encode only when policy requires it.",
        prefer_nvenc_cpu_fallback: "Use NVENC first, then CPU if hardware is unavailable.",
        cpu_fallback: "Use CPU encoding as the primary fallback path.",
        manual_review_missing_hardware: "Route missing hardware cases to review instead of guessing.",
      },
    },
    "wizard-audio-policy": {
      descriptions: {
        preserve_compatible_convert_incompatible: "Keep compatible audio and normalize tracks that need conversion.",
        keep_all_audio: "Preserve every source audio track when possible.",
        review_unusual_audio: "Send unusual audio layouts to review.",
      },
    },
    "wizard-subtitle-policy": {
      descriptions: {
        keep_english_convert_supported: "Keep configured languages and add supported text conversions.",
        review_uncertain_subtitles: "Route uncertain subtitle handling to review.",
      },
    },
  };

  function wizardChoiceSafeId(value) {
    return String(value || "blank").replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "") || "blank";
  }

  function wizardChoiceLabelText(select) {
    const wrapper = select.closest("label");
    const raw = wrapper ? Array.from(wrapper.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent)
      .join(" ") : "";
    return String(raw || select.getAttribute("aria-label") || "Choice").trim();
  }

  function syncWizardChoiceGroup(select) {
    if (!select?.id) return;
    const group = document.querySelector(`[data-enhanced-choice-for="${select.id}"]`);
    if (!group) return;
    group.querySelectorAll("input[type='radio']").forEach((radio) => {
      const checked = String(radio.value || "") === String(select.value || "");
      radio.checked = checked;
      radio.closest(".enhanced-choice-card")?.classList.toggle("is-selected", checked);
    });
  }

  function enhanceWizardChoiceSelect(selectId) {
    const select = byIdLocal(selectId);
    if (!select || document.querySelector(`[data-enhanced-choice-for="${selectId}"]`)) {
      syncWizardChoiceGroup(select);
      return;
    }
    const config = wizardChoiceGroupConfigs[selectId] || {};
    const wrapper = select.closest("label");
    const group = document.createElement("fieldset");
    group.className = "enhanced-choice-group settings-wizard-choice-group";
    group.dataset.enhancedChoiceFor = selectId;

    const legend = document.createElement("legend");
    legend.textContent = wizardChoiceLabelText(select);
    group.appendChild(legend);

    const grid = document.createElement("div");
    grid.className = "enhanced-choice-grid";
    Array.from(select.options || []).forEach((option) => {
      const value = String(option.value || "");
      const optionId = `${selectId}-choice-${wizardChoiceSafeId(value)}`;
      const card = document.createElement("label");
      card.className = "enhanced-choice-card";
      card.htmlFor = optionId;

      const input = document.createElement("input");
      input.type = "radio";
      input.id = optionId;
      input.name = `${selectId}-choice`;
      input.value = value;
      input.checked = value === String(select.value || "");
      input.addEventListener("change", () => {
        if (!input.checked) return;
        select.value = value;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncWizardChoiceGroup(select);
      });

      const title = document.createElement("span");
      title.className = "enhanced-choice-card-title";
      title.textContent = String(option.textContent || value).trim();

      const detailText = String(config.descriptions?.[value] || "").trim();
      if (detailText) {
        const detail = document.createElement("span");
        detail.className = "enhanced-choice-card-detail";
        detail.textContent = detailText;
        card.append(input, title, detail);
      } else {
        card.append(input, title);
      }
      grid.appendChild(card);
    });
    group.appendChild(grid);

    select.addEventListener("input", () => syncWizardChoiceGroup(select));
    select.addEventListener("change", () => syncWizardChoiceGroup(select));
    select.classList.add("enhanced-choice-source");
    if (wrapper) {
      wrapper.classList.add("enhanced-choice-source-label");
      wrapper.insertAdjacentElement("afterend", group);
    } else {
      select.insertAdjacentElement("afterend", group);
    }
    syncWizardChoiceGroup(select);
  }

  function initWizardChoiceGroups() {
    Object.keys(wizardChoiceGroupConfigs).forEach((selectId) => enhanceWizardChoiceSelect(selectId));
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

  function safeJson(value) {
    try { return JSON.stringify(value || {}); } catch (_error) { return "{}"; }
  }

  function readRowJson(row, key, fallback) {
    try {
      const value = JSON.parse(row.dataset[key] || "");
      return value && typeof value === "object" ? value : fallback;
    } catch (_error) {
      return fallback;
    }
  }

  function wizardResultData(result) {
    return result?.data && typeof result.data === "object" ? result.data : (result || {});
  }

  function wizardPayloadSignature() {
    try { return JSON.stringify(collectWizardPayload()); } catch (_error) { return ""; }
  }

  function setStatusChip(id, text, stateName) {
    const node = byIdLocal(id);
    if (!node) return;
    node.textContent = text;
    node.dataset.state = stateName || text.toLowerCase().replace(/\s+/g, "-");
  }

  function activeRiskAckRules() {
    return riskAckRules.filter((rule) => {
      if (boolValue(rule.inputId)) return true;
      return Boolean(rule.selectValueId && textValue(rule.selectValueId) === rule.selectValue);
    });
  }

  function syncRiskAckRows() {
    const active = new Set(activeRiskAckRules().map((rule) => rule.key));
    document.querySelectorAll("[data-risk-ack-row]").forEach((row) => {
      const key = row.dataset.riskAckRow || "";
      const isActive = active.has(key);
      row.hidden = !isActive;
      if (!isActive) {
        const input = row.querySelector("input");
        if (input) input.checked = false;
      }
    });
  }

  function activeRiskAckMissing() {
    return activeRiskAckRules()
      .map((rule) => rule.key)
      .filter((key) => !boolValue(`wizard-ack-${key}`));
  }

  function collectErrorsAndWarnings(...payloads) {
    const errors = [];
    const warnings = [];
    payloads.forEach((payload) => {
      if (!payload || typeof payload !== "object") return;
      errors.push(...(Array.isArray(payload.errors) ? payload.errors : []));
      warnings.push(...(Array.isArray(payload.warnings) ? payload.warnings : []));
    });
    return { errors, warnings };
  }

  function resultStatus(payload, signature, freshRequired = true) {
    if (!payload) return "Not started";
    if (freshRequired && signature && signature !== wizardPayloadSignature()) return "Stale";
    if ((payload.errors || []).length) return "Blocked";
    if ((payload.warnings || []).length || payload.ok === false) return "Warning";
    return "Ready";
  }

  function previewPayload() {
    const data = wizardResultData(state.lastPreview);
    return data.wizard || data;
  }

  function previewStatus() {
    if (!state.lastPreview) return "Not run";
    if (state.lastPreviewSignature !== wizardPayloadSignature()) return "Stale";
    const payload = previewPayload();
    if ((state.lastPreview.errors || payload.errors || []).length || state.lastPreview.ok === false) return "Blocked";
    if ((state.lastPreview.warnings || payload.warnings || []).length) return "Warning";
    return "Ready";
  }

  function settingsWizardSaveReadinessIssues() {
    const issues = [];
    if (state.commandBusy) issues.push("A Settings command is still running.");
    if (!state.lastPreview) {
      issues.push("Run Preview Config before saving.");
    } else if (state.lastPreviewSignature !== wizardPayloadSignature()) {
      issues.push("Wizard draft changed after the last preview. Preview Config again before saving.");
    } else if (state.lastPreview.ok === false) {
      issues.push("Backend preview has blockers. Resolve them before saving.");
    }
    activeRiskAckMissing().forEach((key) => {
      issues.push(`${key} acknowledgement is required before Save & Reload.`);
    });
    return issues;
  }

  function phaseStatuses() {
    const startReady = textValue("wizard-mode") && textValue("wizard-output-container");
    const pathStatus = resultStatus(state.pathValidation, state.pathValidationSignature);
    const toolPayloads = [state.toolsValidation, state.hardwareProbe, state.workerValidation].filter(Boolean);
    const toolIssues = collectErrorsAndWarnings(...toolPayloads);
    let toolchainStatus = "Not started";
    if (toolPayloads.length) {
      const signatures = [state.toolsValidationSignature, state.hardwareProbeSignature, state.workerValidationSignature].filter(Boolean);
      if (signatures.some((signature) => signature !== wizardPayloadSignature())) toolchainStatus = "Stale";
      else if (toolIssues.errors.length) toolchainStatus = "Blocked";
      else if (toolIssues.warnings.length || toolPayloads.some((payload) => payload.ok === false)) toolchainStatus = "Warning";
      else if (toolPayloads.length < 3) toolchainStatus = "Needs input";
      else toolchainStatus = "Ready";
    }
    const policyStatus = activeRiskAckRules().length ? "Warning" : "Ready";
    return [
      startReady ? "Ready" : "Needs input",
      pathStatus,
      toolchainStatus,
      policyStatus,
      previewStatus(),
    ];
  }

  function footerActionLabel() {
    const statuses = phaseStatuses();
    if (state.currentStep === 0) return "Validate Paths";
    if (state.currentStep === 1) return statuses[1] === "Ready" || statuses[1] === "Warning" ? "Detect Tools" : "Validate Paths";
    if (state.currentStep === 2) {
      if (!state.toolsValidation || state.toolsValidationSignature !== wizardPayloadSignature()) return "Detect Tools";
      if ((state.toolsValidation.errors || []).length || state.toolsValidation.ok === false) return "Detect Tools";
      if (!state.hardwareProbe || state.hardwareProbeSignature !== wizardPayloadSignature()) return "Probe Encoders";
      if ((state.hardwareProbe.errors || []).length || state.hardwareProbe.ok === false) return "Probe Encoders";
      if (!state.workerValidation || state.workerValidationSignature !== wizardPayloadSignature()) return "Validate Workers";
      if ((state.workerValidation.errors || []).length || state.workerValidation.ok === false) return "Validate Workers";
      return "Preview Config";
    }
    if (state.currentStep === 3) return "Preview Config";
    return settingsWizardSaveReadinessIssues().length ? "Preview Config" : "Save & Reload";
  }

  function updateWizardReadiness() {
    const currentSignature = wizardPayloadSignature();
    const preview = previewPayload();
    const resultIssues = collectErrorsAndWarnings(
      state.pathValidation,
      state.toolsValidation,
      state.hardwareProbe,
      state.workerValidation,
      preview
    );
    const previewErrors = state.lastPreview?.errors || [];
    const previewWarnings = state.lastPreview?.warnings || [];
    const blockers = new Set([...resultIssues.errors, ...previewErrors]);
    const warnings = new Set([...resultIssues.warnings, ...previewWarnings, ...activeRiskAckMissing()]);
    const changedKeys = preview?.changed_keys || wizardResultData(state.lastPreview).changed_keys || [];
    const validationStale = [
      state.pathValidationSignature,
      state.toolsValidationSignature,
      state.hardwareProbeSignature,
      state.workerValidationSignature,
    ].filter(Boolean).some((signature) => signature !== currentSignature);
    setStatusChip("settings-wizard-readiness-blockers", String(blockers.size), blockers.size ? "blocked" : "ready");
    setStatusChip("settings-wizard-readiness-warnings", String(warnings.size), warnings.size ? "warning" : "ready");
    setStatusChip("settings-wizard-readiness-changed", String(changedKeys.length || 0), changedKeys.length ? "warning" : "ready");
    setStatusChip("settings-wizard-readiness-validation", validationStale ? "Stale" : blockers.size ? "Blocked" : "Current", validationStale ? "stale" : blockers.size ? "blocked" : "ready");
    setStatusChip("settings-wizard-readiness-preview", previewStatus(), previewStatus().toLowerCase().replace(/\s+/g, "-"));
    setStatusChip("settings-wizard-readiness-draft", state.dirty ? "Unsaved" : "Clean", state.dirty ? "warning" : "ready");
    phaseStatuses().forEach((status, index) => {
      setStatusChip(`settings-wizard-phase-${index}-status`, status, status.toLowerCase().replace(/\s+/g, "-"));
    });
    const next = byIdLocal("settings-wizard-next-button");
    if (next) {
      next.textContent = footerActionLabel();
      next.disabled = state.commandBusy || (state.currentStep >= stepLabels.length - 1 && footerActionLabel() === "Save & Reload" && settingsWizardSaveReadinessIssues().length > 0);
    }
    const save = byIdLocal("settings-wizard-save-button");
    if (save) {
      const saveIssues = settingsWizardSaveReadinessIssues();
      save.disabled = saveIssues.length > 0;
      save.title = saveIssues.join("\n");
    }
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
    if (back) back.disabled = bounded <= 0;
    setTextLocal("settings-wizard-status", stepLabels[bounded]);
    updateWizardReadiness();
  }

  function markDirty() {
    state.dirty = true;
    syncRiskAckRows();
    updateWizardReadiness();
  }

  function activateWizardTab() {
    const page = document.querySelector('[data-page-panel="settings"]');
    if (!page) return;
    page.querySelectorAll(".settings-section-nav-btn[data-settings-tab]").forEach((button) => {
      const active = button.dataset.settingsTab === WIZARD_TAB_ID;
      if (active) button.setAttribute("aria-current", "location");
      else button.removeAttribute("aria-current");
    });
    page.querySelectorAll(".settings-tab-pane[data-settings-tab]").forEach((pane) => {
      pane.classList.toggle("is-active", pane.dataset.settingsTab === WIZARD_TAB_ID);
    });
    try { localStorage.setItem("mediapipeline-settings-section", WIZARD_TAB_ID); } catch (_error) {}
    if (typeof window.updatePagePanelEmptyStates === "function") window.updatePagePanelEmptyStates();
  }

  async function openWizard() {
    activateWizardTab();
    setCurrentStep(0);
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
      state.pathValidation = null;
      state.pathValidationSignature = "";
      state.toolsValidation = null;
      state.toolsValidationSignature = "";
      state.hardwareProbe = null;
      state.hardwareProbeSignature = "";
      state.workerValidation = null;
      state.workerValidationSignature = "";
      state.lastPreview = null;
      state.lastPreviewSignature = "";
      const pathRows = byIdLocal("settings-wizard-path-rows");
      if (pathRows) clearRowsLocal(pathRows, 4, "Path validation has not run.");
      updateWizardReadiness();
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
    syncRiskAckRows();
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
    section.dataset.libraryId = library.id || library.library_id || "";
    section.dataset.defaultTracking = safeJson(library.default_tracking);
    section.dataset.overrides = safeJson(library.overrides);
    const protectedDefault = ["movies", "tv"].includes(String(section.dataset.libraryId || "").toLowerCase());
    section.innerHTML = `
      <div class="settings-wizard-library-title">
        <label><input type="checkbox" data-library-field="enabled" ${protectedDefault ? "disabled" : ""}> Enabled</label>
        <button type="button" class="secondary-button" data-library-remove ${protectedDefault ? "disabled" : ""}>Remove</button>
      </div>
      <div class="form-grid form-grid-dense">
        <label>Friendly name *<input type="text" data-library-field="name" autocomplete="off"></label>
        <label>Category<input type="text" data-library-field="category" list="wizard-library-category-list" autocomplete="off"></label>
        <label>Designation<select data-library-field="designation"></select></label>
        <label>Default root role<select data-library-field="default_source_role"></select></label>
        <label>Source path *<input type="text" data-library-field="source_path" autocomplete="off"></label>
        <label>Output destination<input type="text" data-library-field="output_path" autocomplete="off"></label>
        <label>Promotion destination<input type="text" data-library-field="promotion_destination" autocomplete="off"></label>
        <label>Processing profile<select data-library-field="profile"></select></label>
      </div>
      <label class="settings-wizard-library-promotion"><input type="checkbox" data-library-field="promotion_enabled"> Enable promotion for this library</label>
    `;
    section.querySelector('[data-library-field="enabled"]').checked = library.enabled !== false;
    section.querySelector('[data-library-field="name"]').value = library.name || `Library ${index + 1}`;
    section.querySelector('[data-library-field="source_path"]').value = library.source_path || "";
    section.querySelector('[data-library-field="output_path"]').value = library.output_path || "";
    section.querySelector('[data-library-field="promotion_destination"]').value = library.promotion_destination || "";
    section.querySelector('[data-library-field="promotion_enabled"]').checked = library.promotion_enabled === true;
    section.querySelector('[data-library-field="category"]').value = library.category || "other";
    const roleSelect = section.querySelector('[data-library-field="default_source_role"]');
    defaultSourceRoles.forEach(([value, label]) => roleSelect.appendChild(optionNode(value, label, value === (library.default_source_role || "auto"))));
    const designationSelect = section.querySelector('[data-library-field="designation"]');
    designations.forEach(([value, label]) => designationSelect.appendChild(optionNode(value, label, value === (library.designation || library.media_kind || "auto"))));
    const profileSelect = section.querySelector('[data-library-field="profile"]');
    profileChoices.forEach(([value, label]) => profileSelect.appendChild(optionNode(value, label, value === (library.profile || "general_plex_direct_play"))));
    section.querySelectorAll("input, select").forEach((node) => {
      node.addEventListener("input", markDirty);
      node.addEventListener("change", markDirty);
    });
    section.querySelector("[data-library-remove]").addEventListener("click", () => {
      if (protectedDefault) return;
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
      { id: "movies", name: "Movies", designation: "movie", category: "movies", default_source_role: "source_movies", source_path: "", enabled: true, profile: "general_plex_direct_play" },
      { id: "tv", name: "TV", designation: "tv", category: "tv", default_source_role: "source_tv", source_path: "", enabled: true, profile: "general_plex_direct_play" },
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
      output_path: textValue("wizard-output-root"),
      promotion_enabled: false,
      promotion_destination: "",
      enabled: true,
      profile: "general_plex_direct_play",
    }, index));
    markDirty();
  }

  function collectLibraries() {
    return Array.from(document.querySelectorAll(".settings-wizard-library-row")).map((row, index) => {
      const fallbackId = `library_${index + 1}`;
      return {
        id: String(row.dataset.libraryId || fallbackId).trim() || fallbackId,
        enabled: row.querySelector('[data-library-field="enabled"]')?.checked === true,
        name: String(row.querySelector('[data-library-field="name"]')?.value || "").trim(),
        category: String(row.querySelector('[data-library-field="category"]')?.value || "other").trim(),
        designation: String(row.querySelector('[data-library-field="designation"]')?.value || "auto").trim(),
        default_source_role: String(row.querySelector('[data-library-field="default_source_role"]')?.value || "auto").trim(),
        source_path: String(row.querySelector('[data-library-field="source_path"]')?.value || "").trim(),
        output_path: String(row.querySelector('[data-library-field="output_path"]')?.value || "").trim(),
        promotion_enabled: row.querySelector('[data-library-field="promotion_enabled"]')?.checked === true,
        promotion_destination: String(row.querySelector('[data-library-field="promotion_destination"]')?.value || "").trim(),
        profile: String(row.querySelector('[data-library-field="profile"]')?.value || "general_plex_direct_play").trim(),
        overrides: readRowJson(row, "overrides", {}),
        default_tracking: readRowJson(row, "defaultTracking", {}),
      };
    });
  }

  function collectDangerAck() {
    const active = new Set(activeRiskAckRules().map((rule) => rule.key));
    return ["AllowSystemTools", "AllowNoAudio", "CleanupRemoteStaging", "ReprocessAll"]
      .filter((key) => active.has(key))
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
    state.commandBusy = true;
    updateWizardReadiness();
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
      state.commandBusy = false;
      if (state.deps.setSettingsCommandBusy) state.deps.setSettingsCommandBusy(false);
      updateWizardReadiness();
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

  function renderPathRows(rows) {
    const tbody = byIdLocal("settings-wizard-path-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRowsLocal(tbody, 4, "Path validation has not run.");
      return;
    }
    tbody.textContent = "";
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCellsLocal(row, [
        item.label || "",
        item.status || "",
        `${item.path || "not configured"}${item.exists ? " (exists)" : ""}${item.is_dir ? " (folder)" : ""}`,
      ]);
      const actionCell = document.createElement("td");
      if (item.target) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.dataset.wizardFocusTarget = item.target;
        button.textContent = "Focus";
        actionCell.appendChild(button);
      } else {
        actionCell.textContent = "";
      }
      row.appendChild(actionCell);
      tbody.appendChild(row);
    });
  }

  function renderResultList(id, items) {
    const node = byIdLocal(id);
    if (!node) return;
    node.textContent = "";
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      node.textContent = "No result loaded.";
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("div");
      row.className = "settings-wizard-result-row";
      if (typeof item === "string") {
        row.textContent = item;
      } else {
        row.dataset.state = String(item.state || item.status || "").toLowerCase();
        const label = document.createElement("strong");
        label.textContent = item.label || "";
        const status = document.createElement("span");
        status.textContent = item.status || "";
        const detail = document.createElement("span");
        detail.textContent = item.detail || "";
        row.append(label, status, detail);
      }
      node.appendChild(row);
    });
  }

  function focusWizardTarget(target) {
    let node = null;
    const text = String(target || "");
    if (text.startsWith("library:")) {
      const [, indexText, field] = text.split(":");
      const index = Number.parseInt(indexText, 10) - 1;
      node = document.querySelector(`.settings-wizard-library-row[data-library-index="${index}"] [data-library-field="${field}"]`);
    } else if (text.startsWith("#") || text.startsWith(".")) {
      node = document.querySelector(text);
    }
    if (node) {
      node.focus();
      node.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  async function validatePaths() {
    const signature = wizardPayloadSignature();
    const result = await runWizardCommand("settings.wizard.validate_paths", "settings-wizard-status-detail", () => (
      apiPostLocal("/api/settings/wizard/validate-paths", { wizard: collectWizardPayload() })
    ));
    if (result) {
      const data = wizardResultData(result);
      state.pathValidation = data;
      state.pathValidationSignature = signature;
      renderPathRows(data.path_validation?.rows || data.rows || []);
      setTextLocal("settings-wizard-validation-summary", validationText(data));
      setTextLocal("settings-wizard-status-detail", result.message || "Path validation completed.");
      updateWizardReadiness();
    }
  }

  async function detectTools() {
    const signature = wizardPayloadSignature();
    const result = await runWizardCommand("settings.wizard.validate_tools", "settings-wizard-tools-result", () => (
      apiPostLocal("/api/settings/wizard/validate-tools", { wizard: collectWizardPayload() })
    ));
    if (result) {
      const data = wizardResultData(result);
      state.toolsValidation = data;
      state.toolsValidationSignature = signature;
      renderResultList("settings-wizard-tools-result", [
        { label: "FFmpeg", status: data.ffmpeg?.ok ? "Ready" : "Blocked", detail: data.ffmpeg?.path || "not configured", state: data.ffmpeg?.ok ? "ready" : "blocked" },
        { label: "FFprobe", status: data.ffprobe?.ok ? "Ready" : "Blocked", detail: data.ffprobe?.path || "not configured", state: data.ffprobe?.ok ? "ready" : "blocked" },
        ...(data.warnings || []).map((item) => ({ label: "Warning", status: "Warning", detail: item, state: "warning" })),
        ...(data.errors || []).map((item) => ({ label: "Error", status: "Blocked", detail: item, state: "blocked" })),
      ]);
      updateWizardReadiness();
    }
  }

  async function probeHardware() {
    const signature = wizardPayloadSignature();
    const result = await runWizardCommand("settings.wizard.probe_hardware", "settings-wizard-hardware-result", () => (
      apiPostLocal("/api/settings/wizard/probe-hardware", { wizard: collectWizardPayload() })
    ));
    if (result) {
      const data = wizardResultData(result);
      state.hardwareProbe = data;
      state.hardwareProbeSignature = signature;
      renderResultList("settings-wizard-hardware-result", [
        { label: "Detected encoders", status: data.ok ? "Ready" : "Blocked", detail: (data.detected_encoders || []).join(", ") || "none", state: data.ok ? "ready" : "blocked" },
        ...(data.warnings || []).map((item) => ({ label: "Warning", status: "Warning", detail: item, state: "warning" })),
        ...(data.errors || []).map((item) => ({ label: "Error", status: "Blocked", detail: item, state: "blocked" })),
      ]);
      updateWizardReadiness();
    }
  }

  async function validateWorkers() {
    const signature = wizardPayloadSignature();
    const result = await runWizardCommand("settings.wizard.validate_workers", "settings-wizard-workers-result", () => (
      apiPostLocal("/api/settings/wizard/validate-workers", { wizard: collectWizardPayload() })
    ));
    if (result) {
      const data = wizardResultData(result);
      state.workerValidation = data;
      state.workerValidationSignature = signature;
      renderResultList("settings-wizard-workers-result", [
        { label: "Mode", status: data.ok ? "Ready" : "Blocked", detail: data.parallel_encode_mode || "single", state: data.ok ? "ready" : "blocked" },
        { label: "Max encodes", status: data.ok ? "Ready" : "Blocked", detail: String(data.max_parallel_encodes || 1), state: data.ok ? "ready" : "blocked" },
        ...(data.warnings || []).map((item) => ({ label: "Warning", status: "Warning", detail: item, state: "warning" })),
        ...(data.errors || []).map((item) => ({ label: "Error", status: "Blocked", detail: item, state: "blocked" })),
      ]);
      updateWizardReadiness();
    }
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
    updateWizardReadiness();
  }

  async function previewWizard() {
    const signature = wizardPayloadSignature();
    const result = await runWizardCommand("settings.wizard.preview", "settings-wizard-review-summary", () => (
      apiPostLocal("/api/settings/wizard/preview", { wizard: collectWizardPayload() })
    ));
    if (result) {
      state.lastPreview = result;
      state.lastPreviewSignature = signature;
      renderPreview(result);
    }
  }

  async function saveWizard() {
    const saveIssues = settingsWizardSaveReadinessIssues();
    if (saveIssues.length) {
      setCurrentStep(4);
      setTextLocal("settings-wizard-save-result", [
        "Save & Reload is blocked.",
        ...saveIssues.map((item) => `- ${item}`),
      ].join("\n"));
      updateWizardReadiness();
      return;
    }
    const runtimeNote = window.mediaPipelineSettingsView?.settingsRuntimeRestartConfirmationLine?.()
      || "Runtime note: restarting Tauri is not required after a successful reload; future launches use the saved settings.";
    const confirmed = typeof window.confirm === "function"
      ? window.confirm(`Save Settings Wizard config to the active PSD1? A backup will be created first.\n\n${runtimeNote}`)
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
      const lines = [
        result.message || "Save completed.",
        `Writes config: ${data.writes_config ? "yes" : "no"}`,
        `Backup: ${data.backup_path || "none"}`,
        `Reloaded: ${data.reloaded === false ? "no" : "yes or not needed"}`,
        ...(result.warnings || []),
        ...(result.errors || []),
      ];
      if (result.ok && typeof window.mediaPipelineSettingsView?.settingsRuntimeRestartNoticeLines === "function") {
        lines.push("", ...window.mediaPipelineSettingsView.settingsRuntimeRestartNoticeLines(result));
      }
      setTextLocal("settings-wizard-save-result", lines.filter(Boolean).join("\n"));
      if (result.ok) {
        window.mediaPipelineSettingsView?.maybeShowSettingsRuntimeRestartNotice?.(result);
        state.dirty = false;
        state.lastPreview = result;
        state.lastPreviewSignature = wizardPayloadSignature();
        if (typeof state.deps.refreshAll === "function") state.deps.refreshAll();
      }
      updateWizardReadiness();
    }
  }

  async function handlePrimaryWizardAction() {
    const label = footerActionLabel();
    if (label === "Validate Paths") {
      setCurrentStep(1);
      await validatePaths();
    } else if (label === "Detect Tools") {
      setCurrentStep(2);
      await detectTools();
    } else if (label === "Probe Encoders") {
      setCurrentStep(2);
      await probeHardware();
    } else if (label === "Validate Workers") {
      setCurrentStep(2);
      await validateWorkers();
    } else if (label === "Save & Reload") {
      await saveWizard();
    } else {
      setCurrentStep(4);
      await previewWizard();
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
    byIdLocal("settings-wizard-next-button")?.addEventListener("click", handlePrimaryWizardAction);
    byIdLocal("settings-open-wizard-button")?.addEventListener("click", openWizard);
    byIdLocal("settings-wizard-add-library-button")?.addEventListener("click", addLibraryRow);
    byIdLocal("settings-wizard-validate-paths-button")?.addEventListener("click", validatePaths);
    byIdLocal("settings-wizard-detect-tools-button")?.addEventListener("click", detectTools);
    byIdLocal("settings-wizard-probe-hardware-button")?.addEventListener("click", probeHardware);
    byIdLocal("settings-wizard-validate-workers-button")?.addEventListener("click", validateWorkers);
    byIdLocal("settings-wizard-preview-button")?.addEventListener("click", previewWizard);
    byIdLocal("settings-wizard-save-button")?.addEventListener("click", saveWizard);
    byIdLocal("settings-wizard-copy-diagnostics-button")?.addEventListener("click", copyDiagnostics);
    initWizardChoiceGroups();
    document.querySelectorAll(".settings-wizard-panel input, .settings-wizard-panel select").forEach((node) => {
      node.addEventListener("input", markDirty);
      node.addEventListener("change", markDirty);
    });
    document.addEventListener("click", (event) => {
      const button = event.target?.closest?.("[data-wizard-focus-target]");
      if (!button) return;
      event.preventDefault();
      focusWizardTarget(button.dataset.wizardFocusTarget);
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
