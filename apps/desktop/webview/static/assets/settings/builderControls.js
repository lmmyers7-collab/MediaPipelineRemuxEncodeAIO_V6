(function () {
  /* eslint-disable max-lines-per-function -- moved builder-control logic during the settings-view split without behavior changes. */
  function createSettingsBuilderControlsModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const settingsBuilderFields = deps.settingsBuilderFields || [];
    const videoDetailSettingsBuilderFields = deps.videoDetailSettingsBuilderFields || [];
    const qualityDetailSettingsBuilderFields = deps.qualityDetailSettingsBuilderFields || [];
    const subtitleSettingsBuilderFields = deps.subtitleSettingsBuilderFields || [];
    const audioSettingsBuilderFields = deps.audioSettingsBuilderFields || [];
    const fileSafetySettingsBuilderFields = deps.fileSafetySettingsBuilderFields || [];
    const runtimeSettingsBuilderFields = deps.runtimeSettingsBuilderFields || [];
    const pendingPublishSettingsBuilderFields = deps.pendingPublishSettingsBuilderFields || [];
    const queueSettingsBuilderFields = deps.queueSettingsBuilderFields || [];
    const networkSettingsBuilderFields = deps.networkSettingsBuilderFields || [];
    const finalLibraryPromotionSettingsBuilderFields = deps.finalLibraryPromotionSettingsBuilderFields || [];
    const settingsFieldDefinition = deps.settingsFieldDefinition || function () { return null; };
    const settingsFieldLabel = deps.settingsFieldLabel || function (key, fallback = "") { return fallback || key; };
    const settingsFieldHelpText = deps.settingsFieldHelpText || function () { return ""; };
    const settingsFieldIsAdvanced = deps.settingsFieldIsAdvanced || function () { return false; };
    const settingsFieldDefaultValue = deps.settingsFieldDefaultValue || function (_key, fallback) { return fallback; };
    const settingsMetadataValue = deps.settingsMetadataValue || function (value) { return String(value ?? ""); };
    const settingsFieldAllowedValues = deps.settingsFieldAllowedValues || function () { return []; };
    const formatSettingsChoiceLabel = deps.formatSettingsChoiceLabel || function (value) { return String(value || ""); };

    function updateSettingsLabelText(label, control, labelText) {
      if (!label || !control || !labelText) return;
      const childNodes = Array.from(label.childNodes || []);
      const controlIndex = childNodes.indexOf(control);
      const textNodes = childNodes.filter((node) => node.nodeType === Node.TEXT_NODE && String(node.nodeValue || "").trim());
      if (!textNodes.length) return;
      const target = label.classList.contains("check-row")
        ? textNodes.find((node) => childNodes.indexOf(node) > controlIndex) || textNodes[0]
        : textNodes.find((node) => childNodes.indexOf(node) < controlIndex) || textNodes[0];
      const original = String(target.nodeValue || "");
      const leading = original.match(/^\s*/)?.[0] || "";
      const trailing = original.match(/\s*$/)?.[0] || "";
      target.nodeValue = `${leading}${labelText}${trailing || " "}`;
    }

    // eslint-disable-next-line complexity -- metadata sync owns several independent control attributes.
    function applySettingsFieldMetadataToControl([key, id, fallbackKind]) {
      const field = settingsFieldDefinition(key);
      const element = byId(id);
      if (!field || !element) return;
      const label = element.closest?.("label") || null;
      const labelText = settingsFieldLabel(key);
      const valueType = String(field.value_type || field.kind || fallbackKind || "");
      const advancedVisibility = String(field.advanced_visibility || "standard");
      const isAdvanced = settingsFieldIsAdvanced(key, field);
      const advancedTarget = label || element;
      const persistedKey = String(field.persisted_key || key);
      element.dataset.settingsKey = key;
      element.dataset.settingsPersistedKey = persistedKey;
      element.dataset.settingsValueType = valueType;
      element.dataset.settingsAdvancedVisibility = advancedVisibility;
      element.dataset.settingsAdvancedControl = String(isAdvanced);
      if (field.short_label) element.dataset.settingsShortLabel = String(field.short_label);
      if (field.section) element.dataset.settingsSection = String(field.section);
      advancedTarget.classList.toggle("settings-advanced-field", isAdvanced);
      if (isAdvanced) {
        advancedTarget.dataset.settingsAdvancedControl = "true";
      } else {
        delete advancedTarget.dataset.settingsAdvancedControl;
        advancedTarget.hidden = false;
      }
      if (label) {
        label.dataset.settingsKey = key;
        label.dataset.settingsPersistedKey = persistedKey;
        label.dataset.settingsAdvancedVisibility = advancedVisibility;
        label.dataset.settingsAdvancedControl = String(isAdvanced);
        if (field.short_label) label.dataset.settingsShortLabel = String(field.short_label);
        if (field.section) label.dataset.settingsSection = String(field.section);
        updateSettingsLabelText(label, element, labelText);
      }
      const help = settingsFieldHelpText(field);
      if (help) {
        element.title = help;
        if (label) label.title = help;
      }
      const defaultValue = settingsFieldDefaultValue(key, undefined);
      if (defaultValue !== undefined) {
        element.dataset.settingsDefaultValue = settingsMetadataValue(defaultValue);
      }
      if (field.default_source) element.dataset.settingsDefaultSource = String(field.default_source);
      if (field.validation_owner) element.dataset.settingsValidationOwner = String(field.validation_owner);
      if (field.runtime_consumer) element.dataset.settingsRuntimeConsumer = String(field.runtime_consumer);
      const preserveInputType = element.dataset.settingsPreserveInputType === "true" || element.type === "hidden";
      if (element instanceof HTMLInputElement && element.type !== "checkbox") {
        if (["integer", "number"].includes(String(field.value_type || ""))) {
          if (!preserveInputType && element.type !== "range") element.type = "number";
        }
        const preserveRangeLimits = element.type === "range" && element.dataset.settingsPreserveRangeLimits === "true";
        if (!preserveRangeLimits && field.min !== null && field.min !== undefined) element.min = String(field.min);
        if (!preserveRangeLimits && field.max !== null && field.max !== undefined) element.max = String(field.max);
        if (!preserveRangeLimits && field.step !== null && field.step !== undefined) element.step = String(field.step);
      }
    }

    function settingsAdvancedFieldContainers(pane) {
      const seen = new Set();
      return Array.from(pane.querySelectorAll('[data-settings-advanced-control="true"]'))
        .map((node) => node.closest?.("label") || node)
        .filter((node) => node && !node.closest?.(".settings-advanced-disclosure"))
        .filter((node) => {
          if (seen.has(node)) return false;
          seen.add(node);
          return true;
        });
    }

    function ensureSettingsAdvancedToggle(pane) {
      let row = Array.from(pane.children || []).find((node) => node.matches?.("[data-settings-advanced-toggle-row]"));
      if (row) return row;
      row = document.createElement("div");
      row.className = "settings-advanced-toggle-row";
      row.dataset.settingsAdvancedToggleRow = "true";

      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button settings-advanced-toggle";
      button.dataset.settingsAdvancedToggle = "true";
      button.setAttribute("aria-expanded", "false");
      button.textContent = "Show advanced controls";

      const note = document.createElement("span");
      note.className = "settings-advanced-toggle-note";
      note.textContent = "Advanced controls are hidden by default. Revealing them does not change saved keys, defaults, or backend preview/save authority.";

      row.append(button, note);
      pane.insertBefore(row, pane.firstElementChild || null);
      return row;
    }

    function syncSettingsAdvancedPane(pane) {
      const fields = settingsAdvancedFieldContainers(pane);
      const row = pane.querySelector?.("[data-settings-advanced-toggle-row]");
      if (!fields.length) {
        if (row) row.remove();
        return;
      }
      const toggleRow = ensureSettingsAdvancedToggle(pane);
      const button = toggleRow.querySelector("[data-settings-advanced-toggle]");
      const expanded = pane.dataset.settingsAdvancedExpanded === "true";
      fields.forEach((node) => {
        node.hidden = !expanded;
        node.dataset.settingsAdvancedCollapsed = String(!expanded);
      });
      if (button) {
        button.setAttribute("aria-expanded", String(expanded));
        button.textContent = expanded ? "Hide advanced controls" : "Show advanced controls";
      }
    }

    function renderSettingsAdvancedControls() {
      document
        .querySelectorAll('[data-page-panel="settings"] .settings-tab-pane[data-settings-tab]')
        .forEach(syncSettingsAdvancedPane);
    }

    function toggleSettingsAdvancedPane(button) {
      const pane = button.closest?.(".settings-tab-pane[data-settings-tab]");
      if (!pane) return;
      pane.dataset.settingsAdvancedExpanded = pane.dataset.settingsAdvancedExpanded === "true" ? "false" : "true";
      syncSettingsAdvancedPane(pane);
    }

    function handleSettingsAdvancedToggleClick(event) {
      const button = event.target?.closest?.("[data-settings-advanced-toggle]");
      if (!button) return;
      event.preventDefault();
      toggleSettingsAdvancedPane(button);
    }

    function settingsBuilderFieldGroups() {
      return [
        settingsBuilderFields,
        videoDetailSettingsBuilderFields,
        qualityDetailSettingsBuilderFields,
        subtitleSettingsBuilderFields,
        audioSettingsBuilderFields,
        fileSafetySettingsBuilderFields,
        runtimeSettingsBuilderFields,
        pendingPublishSettingsBuilderFields,
        queueSettingsBuilderFields,
        networkSettingsBuilderFields,
        finalLibraryPromotionSettingsBuilderFields,
      ];
    }

    function settingsAllBuilderFields() {
      const seen = new Set();
      return settingsBuilderFieldGroups()
        .flat()
        .filter((field) => {
          const key = String(field?.[0] || "");
          const id = String(field?.[1] || "");
          const identity = `${key}|${id}`;
          if (!key || !id || seen.has(identity)) return false;
          seen.add(identity);
          return true;
        });
    }

    function applySettingsFieldMetadataToControls() {
      settingsAllBuilderFields().forEach(applySettingsFieldMetadataToControl);
    }

    function refreshSettingsSelectChoices(fields) {
      fields.forEach(([key, id]) => {
        const element = byId(id);
        const field = settingsFieldDefinition(key);
        const choices = settingsFieldAllowedValues(field);
        if (!element || element.tagName !== "SELECT" || !choices.length) return;
        const current = element.value;
        element.replaceChildren();
        choices.forEach((choice) => {
          const option = document.createElement("option");
          option.value = String(choice);
          option.textContent = formatSettingsChoiceLabel(choice);
          if (field.choice_help && field.choice_help[String(choice)]) {
            option.title = field.choice_help[String(choice)];
          }
          element.appendChild(option);
        });
        const choiceValues = choices.map((choice) => String(choice));
        const fallback = settingsFieldDefaultValue(key, choices[0] || "");
        element.value = choiceValues.includes(current) ? current : String(fallback || choices[0] || "");
      });
    }

    function refreshSettingsBuilderChoices() {
      refreshSettingsSelectChoices(settingsBuilderFields);
    }

    return {
      updateSettingsLabelText,
      applySettingsFieldMetadataToControl,
      settingsAdvancedFieldContainers,
      ensureSettingsAdvancedToggle,
      syncSettingsAdvancedPane,
      renderSettingsAdvancedControls,
      toggleSettingsAdvancedPane,
      handleSettingsAdvancedToggleClick,
      settingsBuilderFieldGroups,
      settingsAllBuilderFields,
      applySettingsFieldMetadataToControls,
      refreshSettingsSelectChoices,
      refreshSettingsBuilderChoices,
    };
  }

  window.__settingsBuilderControlsModule = {
    createSettingsBuilderControlsModule,
  };
})();
