(function () {
  function createSettingsPatchReviewModule(deps) {
    deps = deps || {};
    const dep = (name, fallback) => Object.prototype.hasOwnProperty.call(deps, name) ? deps[name] : fallback;
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const makeRowSelectable = deps.makeRowSelectable || function () {};
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const formatConfigValue = deps.formatConfigValue || function (value) { return String(value ?? ""); };
    const getCommandHistory = deps.getCommandHistory || function () { return []; };
    const isSettingsCommand = deps.isSettingsCommand || function () { return false; };
    const settingsBoolValue = deps.settingsBoolValue || function (value) { return value === true || String(value).toLowerCase() === "true"; };
    const settingsCommandHistoryLine = deps.settingsCommandHistoryLine || function () { return ""; };
    const settingsPatchCandidateValue = deps.settingsPatchCandidateValue || function () { return undefined; };
    const settingsPatchListValue = deps.settingsPatchListValue || function () { return []; };
    const getSelectedSettingsSaveReviewKey = deps.getSelectedSettingsSaveReviewKey || function () { return ""; };
    const setSelectedSettingsSaveReviewKey = deps.setSelectedSettingsSaveReviewKey || function () {};
    const settingsBuilderConfigValue = deps.settingsBuilderConfigValue || function (_key, fallback) { return fallback; };
    const browseFinalLibraryPromotionRulePath = deps.browseFinalLibraryPromotionRulePath || function () {};
    const finalLibraryPromotionSettingsBuilderState = deps.finalLibraryPromotionSettingsBuilderState || { initialized: false, dirty: false };
    const formatSettingsChoiceLabel = dep("formatSettingsChoiceLabel", function (value) { return String(value || ""); });
    const renderSettingsBackendResultForError = dep("renderSettingsBackendResultForError", function () {});
    const renderSettingsBackendResultFromEntries = dep("renderSettingsBackendResultFromEntries", function () {});
    const renderSettingsEffectivePolicyTrustForError = dep("renderSettingsEffectivePolicyTrustForError", function () {});
    const renderSettingsEffectivePolicyTrustFromEntries = dep("renderSettingsEffectivePolicyTrustFromEntries", function () {});
    const renderSettingsLaunchImpactHandoffForError = dep("renderSettingsLaunchImpactHandoffForError", function () {});
    const renderSettingsLaunchImpactHandoffFromEntries = dep("renderSettingsLaunchImpactHandoffFromEntries", function () {});
    const renderSettingsPatchImpactSummaryForError = dep("renderSettingsPatchImpactSummaryForError", function () {});
    const renderSettingsPatchImpactSummaryFromEntries = dep("renderSettingsPatchImpactSummaryFromEntries", function () {});
    const renderSettingsPolicyDeltaForError = dep("renderSettingsPolicyDeltaForError", function () {});
    const renderSettingsPolicyDeltaFromEntries = dep("renderSettingsPolicyDeltaFromEntries", function () {});
    const settingsBuilderFields = dep("settingsBuilderFields", []);
    const settingsDisplayLabels = dep("settingsDisplayLabels", {});
    const settingsFieldAllowedValues = dep("settingsFieldAllowedValues", function (field) {
      if (Array.isArray(field?.allowed_values) && field.allowed_values.length) return field.allowed_values;
      if (Array.isArray(field?.choices) && field.choices.length) return field.choices;
      return [];
    });
    const settingsFieldDefinition = dep("settingsFieldDefinition", function () { return null; });
    const settingsFriendlyPersistedKeyAliases = dep("settingsFriendlyPersistedKeyAliases", {});
    const settingsHasBackendFieldDefinitions = dep("settingsHasBackendFieldDefinitions", function () { return false; });
    const settingsPatchComplexBackendKeys = dep("settingsPatchComplexBackendKeys", new Set());
    const settingsPatchImpactEntries = dep("settingsPatchImpactEntries", function () { return []; });
    const settingsValuesEqual = dep("settingsValuesEqual", function (left, right) { return JSON.stringify(left) === JSON.stringify(right); });
    const addSettingsEventHandlers = dep("addSettingsEventHandlers", {});
    const audioSettingsBuilderState = dep("audioSettingsBuilderState", {});
    const audioSettingsBuilderFields = dep("audioSettingsBuilderFields", []);
    const fileSafetySettingsBuilderState = dep("fileSafetySettingsBuilderState", {});
    const fileSafetySettingsBuilderFields = dep("fileSafetySettingsBuilderFields", []);
    const finalLibraryPromotionSettingsBuilderFields = dep("finalLibraryPromotionSettingsBuilderFields", []);
    const getLastSettings = dep("getLastSettings", function () { return null; });
    const getSettingsBuilderState = dep("getSettingsBuilderState", function () { return {}; });
    const getLastSettingsValues = dep("getLastSettingsValues", function () { return {}; });
    const getSettingsPatchTouched = dep("getSettingsPatchTouched", function () { return false; });
    const networkSettingsBuilderState = dep("networkSettingsBuilderState", {});
    const networkSettingsBuilderFields = dep("networkSettingsBuilderFields", []);
    const pendingPublishSettingsBuilderState = dep("pendingPublishSettingsBuilderState", {});
    const pendingPublishSettingsBuilderFields = dep("pendingPublishSettingsBuilderFields", []);
    const qualityDetailSettingsBuilderState = dep("qualityDetailSettingsBuilderState", {});
    const qualityDetailSettingsBuilderFields = dep("qualityDetailSettingsBuilderFields", []);
    const queueSettingsBuilderState = dep("queueSettingsBuilderState", {});
    const queueSettingsBuilderFields = dep("queueSettingsBuilderFields", []);
    const refreshAudioSettingsBuilderChoices = dep("refreshAudioSettingsBuilderChoices", function () {});
    const refreshSettingsBuilderChoices = dep("refreshSettingsBuilderChoices", function () {});
    const refreshSettingsSelectChoices = dep("refreshSettingsSelectChoices", function () {});
    const renderAllLaunchPreflights = dep("renderAllLaunchPreflights", function () {});
    const renderSettingsActiveMediaPolicyHandoff = dep("renderSettingsActiveMediaPolicyHandoff", function () {});
    const renderSettingsBackendMediaPolicyReadiness = dep("renderSettingsBackendMediaPolicyReadiness", function () {});
    const renderSettingsBdpgsOcrPathEvidence = dep("renderSettingsBdpgsOcrPathEvidence", function () {});
    const renderSettingsVobSubOcrPathEvidence = dep("renderSettingsVobSubOcrPathEvidence", function () {});
    const renderSettingsMediaPolicyCrossCheck = dep("renderSettingsMediaPolicyCrossCheck", function () {});
    const renderSettingsOperatorTrust = dep("renderSettingsOperatorTrust", function () {});
    const renderSettingsOverview = dep("renderSettingsOverview", function () {});
    const renderSettingsRawActionPlan = dep("renderSettingsRawActionPlan", function () {});
    const renderSettingsRawTriage = dep("renderSettingsRawTriage", function () {});
    const renderSettingsRows = dep("renderSettingsRows", function () {});
    const renderSettingsSafetyLocks = dep("renderSettingsSafetyLocks", function () {});
    const runtimeSettingsBuilderState = dep("runtimeSettingsBuilderState", {});
    const runtimeSettingsBuilderFields = dep("runtimeSettingsBuilderFields", []);
    const setSettingsBuilderState = dep("setSettingsBuilderState", function () {});
    const setSettingsRows = dep("setSettingsRows", function () {});
    const setSettingsPatchTouched = dep("setSettingsPatchTouched", function () {});
    const subtitleSettingsBuilderState = dep("subtitleSettingsBuilderState", {});
    const subtitleSettingsBuilderFields = dep("subtitleSettingsBuilderFields", []);
    const videoDetailSettingsBuilderState = dep("videoDetailSettingsBuilderState", {});
    const videoDetailSettingsBuilderFields = dep("videoDetailSettingsBuilderFields", []);

    function finalLibraryPromotionRulesFromValue(value) {
      let candidate = value;
      if (typeof candidate === "string") {
        const trimmed = candidate.trim();
        if (!trimmed) return [];
        try {
          candidate = JSON.parse(trimmed);
        } catch (_error) {
          return [];
        }
      }
      if (candidate && !Array.isArray(candidate) && typeof candidate === "object") {
        if (Array.isArray(candidate.rules)) candidate = candidate.rules;
        else candidate = Object.values(candidate);
      }
      if (!Array.isArray(candidate)) return [];
      return candidate
        .filter((item) => item && typeof item === "object")
        .map((item, index) => {
          const enabled = settingsBoolValue(item.enabled);
          return {
            id: String(item.id || item.rule_id || `rule-${index + 1}`).trim(),
            label: String(item.label || item.name || `Rule ${index + 1}`).trim(),
            enabled: enabled === null ? true : enabled,
            source_root: String(item.source_root || item.sourceRoot || item.source || "").trim(),
            destination_root: String(item.destination_root || item.destinationRoot || item.destination || "").trim(),
          };
        });
    }

    function finalLibraryPromotionCurrentRules() {
      return finalLibraryPromotionRulesFromValue(settingsBuilderConfigValue("FinalLibraryPromotionRules", []));
    }

    function finalLibraryPromotionSlug(text, fallback) {
      const slug = String(text || "")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      return slug || fallback;
    }

    function finalLibraryPromotionConfigBool(key, fallback = false) {
      const value = settingsBoolValue(settingsBuilderConfigValue(key, fallback));
      return value === null ? Boolean(fallback) : value;
    }

    function finalLibraryPromotionRuleRows() {
      return Array.from(document.querySelectorAll("#settings-final-library-rules-rows tr[data-final-library-rule-row]"));
    }

    function setFinalLibraryPromotionStatus(status, detail) {
      setText("settings-final-library-status", status || "Not loaded");
      if (detail !== undefined) setText("settings-final-library-guidance", detail);
    }

    function setFinalLibraryPromotionControl(id, value, kind = "text") {
      const element = byId(id);
      if (!element) return;
      if (kind === "bool") {
        element.checked = Boolean(value);
        return;
      }
      if (element.tagName === "SELECT") {
        const normalized = String(value || "");
        const optionValues = Array.from(element.options || []).map((option) => option.value);
        element.value = optionValues.includes(normalized) ? normalized : (optionValues[0] || "");
        return;
      }
      element.value = String(value ?? "");
    }

    function finalLibraryPromotionRuleInput(row, name) {
      return row.querySelector(`[data-final-library-rule-${name}]`);
    }

    function finalLibraryPromotionRuleValue(row, name) {
      return String(finalLibraryPromotionRuleInput(row, name)?.value || "").trim();
    }

    function finalLibraryPromotionRuleEnabled(row) {
      const input = finalLibraryPromotionRuleInput(row, "enabled");
      return input ? input.checked === true : true;
    }

    function finalLibraryPromotionBrowseDetailLines(result, label) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const validation = data.validation && typeof data.validation === "object" ? data.validation : {};
      const lines = [
        result?.message || `Folder browse returned for ${label}.`,
        validation.message ? `Validation: ${validation.message}` : "Validation: no selected-folder evidence returned.",
        "Writes config: no",
        "Stages only: yes",
        "Next step: Preview or Save Final Library Settings.",
        "Mutation guardrail: this route only opens a backend-owned Windows folder picker. It cannot save settings, promote files, overwrite, cleanup, launch work, rewrite queue state, or touch media files.",
      ];
      if (data.selected_path) lines.splice(1, 0, `Selected path: ${data.selected_path}`);
      return lines;
    }

    function createFinalLibraryPromotionRuleRow(rule, index) {
      const row = document.createElement("tr");
      row.dataset.finalLibraryRuleRow = "true";
      row.dataset.ruleId = String(rule.id || "");

      const enabledCell = document.createElement("td");
      enabledCell.className = "settings-rule-enabled-cell";
      const enabled = document.createElement("input");
      enabled.type = "checkbox";
      enabled.checked = rule.enabled !== false;
      enabled.dataset.finalLibraryRuleEnabled = "true";
      enabled.setAttribute("aria-label", `Enable final library promotion rule ${index + 1}`);
      enabled.addEventListener("change", markFinalLibraryPromotionSettingsBuilderDirty);
      enabledCell.appendChild(enabled);

      const labelCell = document.createElement("td");
      const label = document.createElement("input");
      label.type = "text";
      label.className = "settings-rule-label-input";
      label.value = rule.label || `Rule ${index + 1}`;
      label.dataset.finalLibraryRuleLabel = "true";
      label.autocomplete = "off";
      label.spellcheck = false;
      label.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      labelCell.appendChild(label);

      const sourceCell = document.createElement("td");
      const sourceWrap = document.createElement("span");
      sourceWrap.className = "settings-path-control settings-path-control-with-badge";
      sourceWrap.dataset.pathPickerScope = "true";
      const source = document.createElement("input");
      source.type = "text";
      source.className = "settings-rule-path-input";
      source.value = rule.source_root || "";
      source.dataset.finalLibraryRuleSource = "true";
      source.autocomplete = "off";
      source.spellcheck = false;
      source.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      const sourceBadge = document.createElement("button");
      sourceBadge.type = "button";
      sourceBadge.className = "path-picker-badge";
      sourceBadge.textContent = "Browse";
      sourceBadge.dataset.pathPickerTarget = "settings.final_library_promotion.source_root";
      sourceBadge.dataset.pathPickerInput = '[data-final-library-rule-source="true"]';
      sourceBadge.dataset.pathPickerMode = "folder";
      sourceBadge.dataset.pathPickerStatus = "settings-final-library-status";
      sourceBadge.title = "Open a backend-owned Windows folder picker for this promotion source root.";
      const sourceBrowse = document.createElement("button");
      sourceBrowse.type = "button";
      sourceBrowse.className = "tertiary-button settings-path-browse-button";
      sourceBrowse.textContent = "Browse";
      sourceBrowse.addEventListener("click", () => browseFinalLibraryPromotionRulePath(source, "FinalLibraryPromotionRuleSourceRoot", "promotion source root"));
      sourceWrap.append(source, sourceBadge, sourceBrowse);
      sourceCell.appendChild(sourceWrap);

      const destinationCell = document.createElement("td");
      const destinationWrap = document.createElement("span");
      destinationWrap.className = "settings-path-control settings-path-control-with-badge";
      destinationWrap.dataset.pathPickerScope = "true";
      const destination = document.createElement("input");
      destination.type = "text";
      destination.className = "settings-rule-path-input";
      destination.value = rule.destination_root || "";
      destination.dataset.finalLibraryRuleDestination = "true";
      destination.autocomplete = "off";
      destination.spellcheck = false;
      destination.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      const destinationBadge = document.createElement("button");
      destinationBadge.type = "button";
      destinationBadge.className = "path-picker-badge";
      destinationBadge.textContent = "Browse";
      destinationBadge.dataset.pathPickerTarget = "settings.final_library_promotion.destination_root";
      destinationBadge.dataset.pathPickerInput = '[data-final-library-rule-destination="true"]';
      destinationBadge.dataset.pathPickerMode = "folder";
      destinationBadge.dataset.pathPickerStatus = "settings-final-library-status";
      destinationBadge.title = "Open a backend-owned Windows folder picker for this promotion destination root.";
      const destinationBrowse = document.createElement("button");
      destinationBrowse.type = "button";
      destinationBrowse.className = "tertiary-button settings-path-browse-button";
      destinationBrowse.textContent = "Browse";
      destinationBrowse.addEventListener("click", () => browseFinalLibraryPromotionRulePath(destination, "FinalLibraryPromotionRuleDestinationRoot", "promotion destination root"));
      destinationWrap.append(destination, destinationBadge, destinationBrowse);
      destinationCell.appendChild(destinationWrap);

      const actionCell = document.createElement("td");
      actionCell.className = "settings-rule-action-cell";
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "tertiary-button";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        row.remove();
        markFinalLibraryPromotionSettingsBuilderDirty();
        renderFinalLibraryPromotionSettingsGuidance();
      });
      actionCell.appendChild(remove);

      row.append(enabledCell, labelCell, sourceCell, destinationCell, actionCell);
      return row;
    }

    function renderFinalLibraryPromotionRules(rules) {
      const tbody = byId("settings-final-library-rules-rows");
      if (!tbody) return;
      const normalized = Array.isArray(rules) ? rules : [];
      if (!normalized.length) {
        clearRows(tbody, 5, "No source-to-destination rules configured.");
        setText("settings-final-library-rule-count", "0 rules");
        return;
      }
      tbody.replaceChildren();
      normalized.forEach((rule, index) => tbody.appendChild(createFinalLibraryPromotionRuleRow(rule, index)));
      const enabledCount = normalized.filter((rule) => rule.enabled !== false).length;
      setText("settings-final-library-rule-count", `${enabledCount}/${normalized.length} enabled`);
    }

    function finalLibraryPromotionRulePayloadFromRow(row, index) {
      const label = finalLibraryPromotionRuleValue(row, "label") || `Rule ${index + 1}`;
      const sourceRoot = finalLibraryPromotionRuleValue(row, "source");
      const destinationRoot = finalLibraryPromotionRuleValue(row, "destination");
      const existingId = String(row?.dataset?.ruleId || "").trim();
      const id = finalLibraryPromotionSlug(existingId || label || sourceRoot || destinationRoot, `rule-${index + 1}`);
      return {
        id,
        label,
        enabled: finalLibraryPromotionRuleEnabled(row),
        source_root: sourceRoot,
        destination_root: destinationRoot,
      };
    }

    function addFinalLibraryPromotionRule() {
      const rules = finalLibraryPromotionRuleRows().map((row, index) => finalLibraryPromotionRulePayloadFromRow(row, index));
      rules.push({
        id: "",
        label: `Rule ${rules.length + 1}`,
        enabled: true,
        source_root: "",
        destination_root: "",
      });
      renderFinalLibraryPromotionRules(rules);
      markFinalLibraryPromotionSettingsBuilderDirty();
      const rows = finalLibraryPromotionRuleRows();
      const last = rows[rows.length - 1];
      finalLibraryPromotionRuleInput(last, "label")?.focus();
    }

    function syncFinalLibraryPromotionSettingsBuilderFromConfig() {
      setFinalLibraryPromotionControl(
        "settings-final-library-enabled",
        finalLibraryPromotionConfigBool("FinalLibraryPromotionEnabled", false),
        "bool"
      );
      setFinalLibraryPromotionControl(
        "settings-final-library-verification-mode",
        settingsBuilderConfigValue("FinalLibraryPromotionVerificationMode", "cautious")
      );
      setFinalLibraryPromotionControl(
        "settings-final-library-cleanup",
        finalLibraryPromotionConfigBool("FinalLibraryPromotionCleanupAfterVerified", false),
        "bool"
      );
      setFinalLibraryPromotionControl(
        "settings-final-library-overwrite",
        finalLibraryPromotionConfigBool("FinalLibraryPromotionOverwriteExisting", false),
        "bool"
      );
      renderFinalLibraryPromotionRules(finalLibraryPromotionCurrentRules());
      finalLibraryPromotionSettingsBuilderState.initialized = true;
      finalLibraryPromotionSettingsBuilderState.dirty = false;
      setText("settings-final-library-status", "Loaded current values");
      renderFinalLibraryPromotionSettingsGuidance();
    }

    function markFinalLibraryPromotionSettingsBuilderDirty() {
      finalLibraryPromotionSettingsBuilderState.initialized = true;
      finalLibraryPromotionSettingsBuilderState.dirty = true;
      setText("settings-final-library-status", "Editing final library settings");
      renderFinalLibraryPromotionSettingsGuidance();
    }

    function collectFinalLibraryPromotionSettingsPatch() {
      const enabled = byId("settings-final-library-enabled")?.checked === true;
      const verificationMode = String(byId("settings-final-library-verification-mode")?.value || "cautious").trim().toLowerCase();
      if (!["fast", "cautious"].includes(verificationMode)) {
        throw new Error("Verification must be Fast or Cautious.");
      }
      const rules = finalLibraryPromotionRuleRows()
        .map((row, index) => finalLibraryPromotionRulePayloadFromRow(row, index))
        .filter((rule) => rule.label || rule.source_root || rule.destination_root);
      const issues = [];
      rules.forEach((rule) => {
        if (!rule.enabled) return;
        if (!rule.source_root) issues.push(`${rule.label}: source root is required.`);
        if (!rule.destination_root) issues.push(`${rule.label}: destination root is required.`);
      });
      const enabledCompleteRules = rules.filter((rule) => rule.enabled && rule.source_root && rule.destination_root);
      if (enabled && !enabledCompleteRules.length) {
        issues.push("Enable at least one complete source-to-destination rule before enabling promotion.");
      }
      if (issues.length) throw new Error(issues.join("\n"));
      return {
        FinalLibraryPromotionEnabled: enabled,
        FinalLibraryPromotionRules: rules,
        FinalLibraryPromotionVerificationMode: verificationMode,
        FinalLibraryPromotionCleanupAfterVerified: byId("settings-final-library-cleanup")?.checked === true,
        FinalLibraryPromotionOverwriteExisting: byId("settings-final-library-overwrite")?.checked === true,
      };
    }

    function renderFinalLibraryPromotionSettingsGuidance() {
      const enabled = byId("settings-final-library-enabled")?.checked === true;
      const cleanup = byId("settings-final-library-cleanup")?.checked === true;
      const overwrite = byId("settings-final-library-overwrite")?.checked === true;
      const verificationMode = String(byId("settings-final-library-verification-mode")?.value || "cautious");
      const rules = finalLibraryPromotionRuleRows().map((row, index) => finalLibraryPromotionRulePayloadFromRow(row, index));
      const enabledRules = rules.filter((rule) => rule.enabled);
      const completeRules = enabledRules.filter((rule) => rule.source_root && rule.destination_root);
      const lines = [
        "Final library promotion settings:",
        `Enabled: ${enabled ? "yes" : "no"}`,
        `Verification: ${verificationMode === "fast" ? "fast size checks" : "cautious SHA-256 hash checks"}`,
        `Rules: ${completeRules.length}/${enabledRules.length} enabled rule(s) complete; ${rules.length} total`,
        `Cleanup after verified promotion: ${cleanup ? "yes" : "no"}`,
        `Overwrite existing final files: ${overwrite ? "yes, destructive delete-before-copy" : "no"}`,
        "",
        "Destination rules are matched from the completed row source path. The longest matching source root wins.",
        "The destination path is still computed by the backend from Outsource-relative publish output.",
      ];
      if (enabled && !completeRules.length) {
        lines.push("", "Blocked: add at least one enabled rule with both source and destination roots.");
      }
      if (overwrite) {
        lines.push("", "Destructive overwrite warning: existing final files are deleted immediately before the replacement copy starts.");
      }
      if (cleanup) {
        lines.push("", "Cleanup warning: after verification, promoted files are removed from publish output below Outsource.");
      }
      lines.push("", "Mutation guardrail: this panel only saves settings through the backend. It never promotes, overwrites, cleans up, or touches media files.");
      setText("settings-final-library-guidance", lines.join("\n"));
      setText("settings-final-library-rule-count", `${enabledRules.length}/${rules.length} enabled`);
    }

    function finalLibraryPromotionSettingsResultLines(action, result, changes) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const changedKeys = Array.isArray(data.changed_keys) ? data.changed_keys : Object.keys(changes || {});
      const lines = [
        `${action}: ${result?.message || "No backend message returned."}`,
        `OK: ${result?.ok === true ? "yes" : "no"}`,
        `Severity: ${result?.severity || "unknown"}`,
        `Changed keys: ${settingsPersistedKeyDisplayList(changedKeys) || "none"}`,
        `Writes config: ${data.writes_config === true ? "yes" : data.writes_config === false ? "no" : "n/a"}`,
        "Preview/save uses persisted keys. Friendly labels are display only and are not saved keys.",
      ];
      const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
      const errors = Array.isArray(result?.errors) ? result.errors : [];
      if (warnings.length) lines.push("", "Warnings:", ...warnings.map((item) => `- ${item}`));
      if (errors.length) {
        lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
        lines.push("Backend validation errors are authoritative; this WebView did not save or bypass them.");
      }
      lines.push("", "Promotion remains manual from the Completed/Output page.");
      return lines;
    }

    function renderSettingsPatchSummary() {
      const tbody = byId("settings-patch-summary-rows");
      if (!tbody) return;
      const changedOnly = byId("settings-patch-summary-changed-only")?.checked === true;
      let patch;
      try {
        patch = parseSettingsPatchJson();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        clearRows(tbody, 5, `Patch JSON is invalid: ${message}`);
        setText("settings-patch-summary-status", "Change summary unavailable because Changes JSON is invalid.");
        renderSettingsPatchImpactSummaryForError(message);
        renderSettingsPolicyDeltaForError(message);
        renderSettingsEffectivePolicyTrustForError(message);
        renderSettingsPatchSaveReadinessForError(message);
        renderSettingsLaunchImpactHandoffForError(message);
        renderSettingsBackendResultForError(message);
        return;
      }
      const impactEntries = settingsPatchImpactEntries(patch);
      renderSettingsPatchImpactSummaryFromEntries(impactEntries);
      renderSettingsPolicyDeltaFromEntries(impactEntries);
      renderSettingsEffectivePolicyTrustFromEntries(impactEntries);
      renderSettingsPatchSaveReadinessFromEntries(impactEntries);
      renderSettingsSaveReviewFromEntries(impactEntries);
      renderSettingsLaunchImpactHandoffFromEntries(impactEntries);
      renderSettingsBackendResultFromEntries(impactEntries);
      const keys = Object.keys(patch);
      if (!keys.length) {
        clearRows(tbody, 5, "No current change keys.");
        const presetInfo = settingsActivePresetInfo();
        setText(
          "settings-patch-summary-status",
          [
            `Active preset: ${presetInfo.name}`,
            `Preset scope: ${presetInfo.scope}`,
            "No current settings changes. Save uses persisted keys; friendly labels are display only.",
          ].join("\n")
        );
        return;
      }
      tbody.replaceChildren();
      let changedCount = 0;
      let unchangedCount = 0;
      let unknownCount = 0;
      let visibleCount = 0;
      keys.sort((a, b) => a.localeCompare(b)).forEach((key) => {
        const field = settingsFieldDefinition(key);
        const current = settingsRawConfigValue(key);
        const staged = patch[key];
        let status = "";
        let statusKey = "";
        if (!field) {
          unknownCount += 1;
          status = "unknown key";
          statusKey = "unknown";
        } else if (settingsValuesEqual(current, staged)) {
          unchangedCount += 1;
          status = "unchanged";
          statusKey = "unchanged";
        } else {
          changedCount += 1;
          status = current === undefined ? "new value" : "changed";
          statusKey = current === undefined ? "new" : "changed";
        }
        if (changedOnly && statusKey === "unchanged") return;
        visibleCount += 1;
        const row = document.createElement("tr");
        row.dataset.status = statusKey;
        appendCells(row, [
          key,
          settingsDisplayLabel(key, field?.label || key),
          current === undefined ? "(not set)" : formatConfigValue(current),
          formatConfigValue(staged),
          status,
        ]);
        tbody.appendChild(row);
      });
      if (!visibleCount) {
        clearRows(tbody, 5, "No changed or unknown keys to show.");
      }
      const changedPersistedKeys = impactEntries
        .filter((entry) => entry.changed)
        .map((entry) => settingsPersistedKeyDisplay(entry.key, entry.field));
      const unknownPersistedKeys = impactEntries
        .filter((entry) => !entry.field)
        .map((entry) => settingsPersistedKeyDisplay(entry.key, entry.field));
      const presetInfo = settingsActivePresetInfo();
      setText(
        "settings-patch-summary-status",
        [
          `Active preset: ${presetInfo.name}`,
          `Preset scope: ${presetInfo.scope}`,
          `${keys.length} candidate key${keys.length === 1 ? "" : "s"}: ${changedCount} changed, ${unchangedCount} unchanged, ${unknownCount} unknown, ${visibleCount} shown.`,
          `Changed persisted keys: ${changedPersistedKeys.join(", ") || "none"}.`,
          unknownPersistedKeys.length ? `Unknown persisted keys needing backend validation: ${unknownPersistedKeys.join(", ")}.` : "Unknown persisted keys needing backend validation: none.",
          "Save uses persisted keys. Friendly labels are display only and are not saved keys. Backend Save remains the source of truth.",
        ].join("\n")
      );
    }

    function renderSettingsBuilderGuidance() {
      const lines = [];
      settingsBuilderFields.forEach(([key, id]) => {
        const field = settingsFieldDefinition(key);
        const label = settingsDisplayLabel(key, field?.label || key);
        const value = settingsBuilderInputValue(id);
        const formattedValue = value ? formatSettingsChoiceLabel(value) : "(not set)";
        lines.push(`${label}: ${formattedValue}`);
        const choiceHelp = field?.choice_help && value ? field.choice_help[value] : "";
        if (choiceHelp) {
          lines.push(`  ${choiceHelp}`);
        } else if (field?.help) {
          lines.push(`  ${field.help}`);
        }
      });
      setText("settings-builder-guidance", lines.join("\n") || "No builder guidance loaded.");
    }

    function settingsDisplayLabel(key, fallback) {
      const field = settingsFieldDefinition(key);
      if (field?.label) return field.label;
      return settingsDisplayLabels && settingsDisplayLabels[key] ? settingsDisplayLabels[key] : (fallback || key);
    }

    function settingsPersistedKeyDisplay(key, field) {
      const persisted = String(key || "").trim();
      if (!persisted) return "";
      const label = settingsDisplayLabel(persisted, field?.label || persisted);
      return label && label !== persisted ? `${persisted} (${label})` : persisted;
    }

    function settingsPersistedKeyDisplayList(keys) {
      return (Array.isArray(keys) ? keys : [])
        .map((key) => settingsPersistedKeyDisplay(key, settingsFieldDefinition(key)))
        .filter(Boolean)
        .join(", ");
    }

    function settingsHumanStatus(value) {
      return String(value || "unknown").replace(/_/g, " ");
    }

    function settingsActivePresetInfo() {
      const settings = getLastSettings() || {};
      const summary = settings.profile_summary && typeof settings.profile_summary === "object"
        ? settings.profile_summary
        : {};
      const profileName = String(summary.default_profile_name || "Default").trim() || "Default";
      const status = settingsHumanStatus(summary.default_profile_status || "not loaded");
      const hasProfile = summary.default_profile_exists === true;
      if (!hasProfile) {
        return {
          name: "Saved settings",
          scope: "saved global config; profile save/load is not active in this WebView",
        };
      }
      return {
        name: `${profileName} (${status})`,
        scope: "Preset/profile comparison only; backend Save writes stable persisted keys.",
      };
    }

    function formatSettingsSummaryValue(key, fallback = "not loaded") {
      const value = settingsRawConfigValue(key);
      if (value === undefined || value === null || value === "") return fallback;
      return formatConfigValue(value);
    }

    function formatSettingsOutputSizeCheckMode(value) {
      const normalized = String(value || "").trim().toLowerCase();
      if (normalized === "advisory") return "Warn only";
      if (normalized === "strict") return "Fail job";
      if (normalized === "fallback_remux") return "Try remux fallback";
      if (normalized === "off") return "Disabled";
      return formatSettingsChoiceLabel(value);
    }

    function renderSettingsEffectiveIntentSummary(options = {}) {
      const routeSummary = options.routeSummary ? String(options.routeSummary).toUpperCase() : "";
      const planAuthority = options.planAuthority || "saved settings orientation only";
      const routingProfile = formatSettingsSummaryValue("RoutingProfile", "backend default");
      const routeMode = formatSettingsSummaryValue("RouteThresholdMode", "backend default");
      const outputContainer = options.outputContainer || formatSettingsSummaryValue("OutputContainer", "backend default");
      const videoCodec = formatSettingsSummaryValue("VideoCodec", "backend default");
      const videoPreset = formatSettingsSummaryValue("VideoPreset", "backend default");
      const videoQuality = formatSettingsSummaryValue("VideoQuality", "backend default");
      const sizeGuard = formatSettingsSummaryValue("SizeGuardMode", "backend default");
      const movie1080pTarget = formatSettingsSummaryValue("MovieRoute1080pTargetSizeGB", "8");
      const movie1440pTarget = formatSettingsSummaryValue("MovieRoute1440pTargetSizeGB", "8");
      const movie4kTarget = formatSettingsSummaryValue("MovieRoute4KTargetSizeGB", "8");
      const tv1080pTarget = formatSettingsSummaryValue("TVRoute1080pTargetSizeGB", "3");
      const tv1440pTarget = formatSettingsSummaryValue("TVRoute1440pTargetSizeGB", "3");
      const tv4kTarget = formatSettingsSummaryValue("TVRoute4KTargetSizeGB", "3");
      const routeBoundaries = routeHeightToleranceBoundariesFromConfigValues();
      const route1080pBitrate = formatSettingsSummaryValue("Route1080pMaxVideoBitrateMbps", "20");
      const route1440pBitrate = formatSettingsSummaryValue("Route1440pMaxVideoBitrateMbps", "35");
      const route4kBitrate = formatSettingsSummaryValue("Route4KMaxVideoBitrateMbps", "35");
      const maxGrowth = formatSettingsSummaryValue("MaxEncodeGrowthPercent", "backend default");
      const compatGrowth = formatSettingsSummaryValue("CompatibilityEncodeGrowthPercent", "backend default");
      const routeLine = routeSummary
        ? `Backend preview route: ${routeSummary}. Final runtime decision is resolved during queue/job processing.`
        : "Copy/remux-first intent is displayed from persisted RoutingProfile; the WebView does not compute final routing.";

      setText(
        "settings-summary-processing-strategy",
        `${formatSettingsChoiceLabel(routingProfile)} (persisted key RoutingProfile; enforcement ${formatSettingsChoiceLabel(routeMode)})`
      );
      setText("settings-summary-copy-remux-intent", routeLine);
      setText("settings-summary-output-container", `${formatSettingsChoiceLabel(outputContainer)} (persisted key OutputContainer)`);
      setText(
        "settings-summary-encode-if-required",
        `${formatSettingsChoiceLabel(videoCodec)}; preset ${formatSettingsChoiceLabel(videoPreset)}; quality ${videoQuality}. Applies only when encoding is required.`
      );
      setText(
        "settings-summary-size-bitrate-guards",
        `Size guard ${formatSettingsOutputSizeCheckMode(sizeGuard)}; targets by height: 1080p movie ${movie1080pTarget} GB / TV ${tv1080pTarget} GB, 1440p movie ${movie1440pTarget} GB / TV ${tv1440pTarget} GB, 4K movie ${movie4kTarget} GB / TV ${tv4kTarget} GB. Unknown height uses the 1080p targets. Direct-copy caps: 1080p <=${routeBoundaries.route1080pMaxHeight}p ${route1080pBitrate} Mbps, 1440p ${routeBoundaries.route1440pMinHeight}-${routeBoundaries.route1440pMaxHeight}p ${route1440pBitrate} Mbps, 4K >=${routeBoundaries.route4kMinHeight}p ${route4kBitrate} Mbps. Unknown height uses the 1080p cap; growth ${maxGrowth}% normal / ${compatGrowth}% compatibility.`
      );
      setText(
        "settings-summary-preview-scope",
        `Preview scope: ${planAuthority}. Saved global settings are shown here; library_effective_settings is library-only when shown in queue rows. Final runtime decision is resolved during queue/job processing.`
      );
    }

    function renderHandbrakePreviewSummary(settings) {
      const activePreset = settingsActivePresetInfo();
      const videoCodec = formatSettingsSummaryValue("VideoCodec", "backend default");
      const videoPreset = formatSettingsSummaryValue("VideoPreset", "backend default");
      const videoQuality = formatSettingsSummaryValue("VideoQuality", "backend default");
      const outputContainer = formatSettingsSummaryValue("OutputContainer", "backend default");
      const sizeGuard = formatSettingsSummaryValue("SizeGuardMode", "backend default");
      const maxGrowth = formatSettingsSummaryValue("MaxEncodeGrowthPercent", "backend default");
      const compatGrowth = formatSettingsSummaryValue("CompatibilityEncodeGrowthPercent", "backend default");
      const deferredPublish = settingsRawConfigValue("DeferredPublish");
      const publishText = deferredPublish === true || String(deferredPublish).toLowerCase() === "true"
        ? "Deferred publish enabled"
        : "Saved publish policy loaded";
      setText("settings-handbrake-active-preset", activePreset.name);
      setText("settings-handbrake-output-video", `${formatSettingsChoiceLabel(videoCodec)}; preset ${formatSettingsChoiceLabel(videoPreset)}; quality ${videoQuality}`);
      setText("settings-handbrake-output-container", formatSettingsChoiceLabel(outputContainer));
      setText("settings-handbrake-output-guards", `If encoded output is too large: ${formatSettingsOutputSizeCheckMode(sizeGuard)}; normal growth ${maxGrowth}%; compatibility growth ${compatGrowth}%`);
      setText("settings-handbrake-publish-requirements", publishText);
      renderSettingsEffectiveIntentSummary();
      setText("settings-container-size-container", `Output container: ${formatSettingsChoiceLabel(outputContainer)}.`);
      setText("settings-handbrake-preview-status", "Predicted pending cutover");
      setText("settings-handbrake-decision", "NOT EVALUATED");
      setText("settings-handbrake-preview-detail", [
        "The WebView does not compute copy/remux/encode routing.",
        "Loaded saved output policy is shown for orientation only:",
        `- video encoder: ${formatSettingsChoiceLabel(videoCodec)}`,
        `- output container: ${formatSettingsChoiceLabel(outputContainer)}`,
        `- If encoded output is too large: ${formatSettingsOutputSizeCheckMode(sizeGuard)}`,
        "Source-specific route previews are not exposed in Settings; final route decisions remain backend-owned during queue/job processing.",
        "Preview remains predicted until production cutover because legacy execution still owns production work.",
      ].join("\n"));
    }

    function settingsProfileSummaryLines(settings) {
      const summary = settings?.profile_summary && typeof settings.profile_summary === "object"
        ? settings.profile_summary
        : null;
      if (summary && Array.isArray(summary.summary_lines) && summary.summary_lines.length) {
        const lines = summary.summary_lines.map((line) => String(line));
        if (Array.isArray(summary.mismatch_keys) && summary.mismatch_keys.length) {
          const truncated = summary.mismatch_keys_truncated ? " (truncated)" : "";
          lines.push(`Different keys${truncated}: ${summary.mismatch_keys.join(", ")}`);
        }
        return lines.join("\n");
      }
      const profiles = Array.isArray(settings?.profiles) ? settings.profiles : [];
      return profiles.length ? profiles.join("\n") : "No profiles found.";
    }

    function setSettingsBuilderControl(id, value) {
      const element = byId(id);
      if (!element) return;
      const normalized = String(value ?? "");
      if (element.tagName === "SELECT") {
        const optionValues = Array.from(element.options || []).map((option) => option.value);
        element.value = optionValues.includes(normalized) ? normalized : (optionValues[0] || "");
        return;
      }
      element.value = normalized;
    }

    const routeHeightToleranceDefaults = {
      route1080pUpperPercent: 11.111111,
      route1440pLowerPercent: 16.597222,
      route1440pUpperPercent: 24.930556,
      route4kLowerPercent: 16.666667,
    };

    let routeRailDragState = null;

    function routeClamp(value, min, max) {
      const number = Number(value);
      if (!Number.isFinite(number)) return min;
      return Math.min(max, Math.max(min, number));
    }

    function routeFormatPercent(value) {
      const number = Number(value);
      if (!Number.isFinite(number)) return "";
      return number.toFixed(6).replace(/\.?0+$/, "");
    }

    function routeFormatDisplayPercent(value) {
      const number = Number(value);
      if (!Number.isFinite(number)) return "";
      return String(Math.round(number));
    }

    function routeFormatHeight(value) {
      const number = Number(value);
      if (!Number.isFinite(number)) return "";
      return String(Math.round(number));
    }

    function routeMaxHeightFromUpperTolerance(baseHeight, tolerancePercent) {
      return Math.round(Number(baseHeight) * (1 + (Number(tolerancePercent) / 100)));
    }

    function routeMinHeightFromLowerTolerance(baseHeight, tolerancePercent) {
      return Math.round(Number(baseHeight) * (1 - (Number(tolerancePercent) / 100)));
    }

    function routeUpperToleranceFromMaxHeight(baseHeight, maxHeight) {
      return ((Number(maxHeight) / Number(baseHeight)) - 1) * 100;
    }

    function routeLowerToleranceFromMinHeight(baseHeight, minHeight) {
      return (1 - (Number(minHeight) / Number(baseHeight))) * 100;
    }

    function setRouteToleranceControl(id, value) {
      const clamped = routeClamp(value, 0, 100);
      const preciseValue = routeFormatPercent(clamped);
      const displayValue = routeFormatDisplayPercent(clamped);
      setSettingsBuilderControl(id, displayValue);
      const element = byId(id);
      if (element) {
        element.dataset.routePreciseValue = preciseValue;
        element.dataset.routeDisplayValue = displayValue;
      }
    }

    function setRouteBoundaryControl(id, value) {
      setSettingsBuilderControl(id, routeFormatHeight(value));
    }

    function setRouteRailBoundaryInput(id, value) {
      setSettingsBuilderControl(id, routeFormatHeight(value));
    }

    function routeToleranceValue(id, fallback) {
      const parsed = Number(settingsBuilderPreciseInputValue(id));
      return Number.isFinite(parsed) ? routeClamp(parsed, 0, 100) : fallback;
    }

    function routeRailBoundaryConfig(boundary) {
      if (boundary === "first") {
        return {
          inputId: "settings-route-boundary-1080p-end-input",
          min: 1080,
          max: 1439,
          currentId: "settings-boundary-1080p-end",
        };
      }
      if (boundary === "second") {
        return {
          inputId: "settings-route-boundary-4k-start-input",
          min: 1441,
          max: 2160,
          currentId: "settings-boundary-4k-start",
        };
      }
      return null;
    }

    function routeRailCurrentBoundaryHeight(boundary) {
      const config = routeRailBoundaryConfig(boundary);
      if (!config) return null;
      const inputValue = Number(settingsBuilderInputValue(config.inputId));
      if (Number.isFinite(inputValue)) return routeClamp(Math.round(inputValue), config.min, config.max);
      const currentValue = Number(settingsBuilderInputValue(config.currentId));
      if (Number.isFinite(currentValue)) return routeClamp(Math.round(currentValue), config.min, config.max);
      return config.min;
    }

    function applyRouteRailBoundaryHeight(boundary, rawHeight) {
      const config = routeRailBoundaryConfig(boundary);
      const number = Number(rawHeight);
      if (!config || !Number.isFinite(number)) return;
      const height = Math.round(routeClamp(number, config.min, config.max));
      if (boundary === "first") {
        setRouteFirstBoundary(height + 1);
      } else {
        setRouteSecondBoundary(height);
      }
      renderRouteHeightTolerancePreview();
    }

    function applyRouteRailBoundaryInput(id) {
      const boundary = id === "settings-route-boundary-1080p-end-input" ? "first"
        : id === "settings-route-boundary-4k-start-input" ? "second"
          : "";
      if (!boundary) return;
      applyRouteRailBoundaryHeight(boundary, settingsBuilderInputValue(id));
      markSettingsBuilderDirty({ target: { id } });
    }

    function routeConfigNumber(key, fallback) {
      const raw = settingsRawConfigValue(key);
      const parsed = Number(raw);
      return Number.isFinite(parsed) ? parsed : fallback;
    }

    function routeHeightToleranceBoundariesFromConfigValues() {
      return {
        route1080pMaxHeight: routeMaxHeightFromUpperTolerance(
          1080,
          routeConfigNumber("Route1080pUpperHeightTolerancePercent", routeHeightToleranceDefaults.route1080pUpperPercent)
        ),
        route1440pMinHeight: routeMinHeightFromLowerTolerance(
          1440,
          routeConfigNumber("Route1440pLowerHeightTolerancePercent", routeHeightToleranceDefaults.route1440pLowerPercent)
        ),
        route1440pMaxHeight: routeMaxHeightFromUpperTolerance(
          1440,
          routeConfigNumber("Route1440pUpperHeightTolerancePercent", routeHeightToleranceDefaults.route1440pUpperPercent)
        ),
        route4kMinHeight: routeMinHeightFromLowerTolerance(
          2160,
          routeConfigNumber("Route4KLowerHeightTolerancePercent", routeHeightToleranceDefaults.route4kLowerPercent)
        ),
      };
    }

    function setRouteFirstBoundary(route1440pMinHeight) {
      const line = Math.round(routeClamp(route1440pMinHeight, 1081, 1440));
      setRouteToleranceControl(
        "settings-builder-1080p-upper-tolerance",
        routeUpperToleranceFromMaxHeight(1080, line - 1)
      );
      setRouteToleranceControl(
        "settings-builder-1440p-lower-tolerance",
        routeLowerToleranceFromMinHeight(1440, line)
      );
    }

    function setRouteSecondBoundary(route4kMinHeight) {
      const line = Math.round(routeClamp(route4kMinHeight, 1441, 2160));
      setRouteToleranceControl(
        "settings-builder-1440p-upper-tolerance",
        routeUpperToleranceFromMaxHeight(1440, line - 1)
      );
      setRouteToleranceControl(
        "settings-builder-4k-lower-tolerance",
        routeLowerToleranceFromMinHeight(2160, line)
      );
    }

    function routeHeightToleranceBoundariesFromControls() {
      const route1080pMaxHeight = routeMaxHeightFromUpperTolerance(
        1080,
        routeToleranceValue("settings-builder-1080p-upper-tolerance", routeHeightToleranceDefaults.route1080pUpperPercent)
      );
      const route1440pMinHeight = routeMinHeightFromLowerTolerance(
        1440,
        routeToleranceValue("settings-builder-1440p-lower-tolerance", routeHeightToleranceDefaults.route1440pLowerPercent)
      );
      const route1440pMaxHeight = routeMaxHeightFromUpperTolerance(
        1440,
        routeToleranceValue("settings-builder-1440p-upper-tolerance", routeHeightToleranceDefaults.route1440pUpperPercent)
      );
      const route4kMinHeight = routeMinHeightFromLowerTolerance(
        2160,
        routeToleranceValue("settings-builder-4k-lower-tolerance", routeHeightToleranceDefaults.route4kLowerPercent)
      );
      return {
        route1080pMaxHeight,
        route1440pMinHeight,
        route1440pMaxHeight,
        route4kMinHeight,
      };
    }

    function syncRouteBoundaryControls(boundaries) {
      setRouteBoundaryControl("settings-boundary-1080p-end", boundaries.route1080pMaxHeight);
      setRouteBoundaryControl("settings-boundary-1440p-start", boundaries.route1440pMinHeight);
      setRouteBoundaryControl("settings-boundary-1440p-end", boundaries.route1440pMaxHeight);
      setRouteBoundaryControl("settings-boundary-4k-start", boundaries.route4kMinHeight);
      setRouteRailBoundaryInput("settings-route-boundary-1080p-end-input", boundaries.route1080pMaxHeight);
      setRouteRailBoundaryInput("settings-route-boundary-4k-start-input", boundaries.route4kMinHeight);
      syncRouteSliderVisuals(boundaries);
      setText("settings-boundary-1080p-end-readout", `${routeFormatHeight(boundaries.route1080pMaxHeight)}p`);
      setText("settings-boundary-4k-start-readout", `${routeFormatHeight(boundaries.route4kMinHeight)}p`);
    }

    function syncRouteSliderVisuals(boundaries) {
      const rail = byId("settings-route-height-slider");
      if (!rail) return;
      const minHeight = 1080;
      const maxHeight = 2160;
      const heightSpan = maxHeight - minHeight;
      const firstPct = routeClamp(((Number(boundaries.route1080pMaxHeight) - minHeight) / heightSpan) * 100, 0, 100);
      const secondPct = routeClamp(((Number(boundaries.route4kMinHeight) - minHeight) / heightSpan) * 100, 0, 100);
      rail.style.setProperty("--route-first-pct", `${routeFormatPercent(firstPct)}%`);
      rail.style.setProperty("--route-second-pct", `${routeFormatPercent(secondPct)}%`);
    }

    function renderRoutePercentReadouts() {
      setText(
        "settings-builder-1080p-upper-tolerance-readout",
        `${routeFormatDisplayPercent(routeToleranceValue("settings-builder-1080p-upper-tolerance", routeHeightToleranceDefaults.route1080pUpperPercent))}%`
      );
      setText(
        "settings-builder-1440p-lower-tolerance-readout",
        `${routeFormatDisplayPercent(routeToleranceValue("settings-builder-1440p-lower-tolerance", routeHeightToleranceDefaults.route1440pLowerPercent))}%`
      );
      setText(
        "settings-builder-1440p-upper-tolerance-readout",
        `${routeFormatDisplayPercent(routeToleranceValue("settings-builder-1440p-upper-tolerance", routeHeightToleranceDefaults.route1440pUpperPercent))}%`
      );
      setText(
        "settings-builder-4k-lower-tolerance-readout",
        `${routeFormatDisplayPercent(routeToleranceValue("settings-builder-4k-lower-tolerance", routeHeightToleranceDefaults.route4kLowerPercent))}%`
      );
    }

    function settingsBuilderControlOrConfigValue(id, key, fallback) {
      return settingsBuilderInputValue(id) || formatSettingsSummaryValue(key, fallback);
    }

    function settingsBuilderSelectText(id, key, fallback) {
      const element = byId(id);
      const selected = element && element.selectedOptions && element.selectedOptions.length
        ? String(element.selectedOptions[0].textContent || "").trim()
        : "";
      if (selected) return selected;
      const value = settingsBuilderInputValue(id) || settingsBuilderConfigValue(key, fallback);
      return formatSettingsChoiceLabel(value);
    }

    function renderRouteTriggerSummary() {
      const mode = settingsBuilderInputValue("settings-builder-route-threshold-mode")
        || settingsBuilderConfigValue("RouteThresholdMode", "compatibility_advisory");
      const summaries = {
        compatibility_advisory: "Direct-copy bitrate over the cap forces encode. Output-size targets guide the encode budget, but size stays flexible before processing.",
        size: "Target output size can force encode. Direct-copy bitrate caps stay advisory.",
        bitrate: "Direct-copy bitrate over the cap forces encode. Target output size stays advisory.",
        size_or_bitrate: "Either target size or direct-copy bitrate can force encode.",
      };
      setText("settings-route-trigger-summary", summaries[mode] || "Routing trigger behavior follows the selected backend mode.");
    }

    function renderRouteConsequenceSummary(boundaries) {
      const movie1440pTarget = settingsBuilderControlOrConfigValue("settings-builder-movie-1440p-target", "MovieRoute1440pTargetSizeGB", "8");
      const tv1440pTarget = settingsBuilderControlOrConfigValue("settings-builder-tv-1440p-target", "TVRoute1440pTargetSizeGB", "3");
      const route1440pBitrate = settingsBuilderControlOrConfigValue("settings-builder-1440p-route-bitrate", "Route1440pMaxVideoBitrateMbps", "35");
      setText(
        "settings-route-consequence-summary",
        `A ${boundaries.route1440pMinHeight}p source routes as 1440p: Movie ${movie1440pTarget} GB / TV ${tv1440pTarget} GB, direct-copy cap ${route1440pBitrate} Mbps. A ${boundaries.route4kMinHeight}p source routes as 4K.`
      );
    }

    function renderRouteAdvancedSummary() {
      const movieFallbackSize = settingsBuilderControlOrConfigValue("settings-builder-movie-1080p-target", "MovieRoute1080pTargetSizeGB", "8");
      const tvFallbackSize = settingsBuilderControlOrConfigValue("settings-builder-tv-1080p-target", "TVRoute1080pTargetSizeGB", "3");
      const fallbackBitrate = settingsBuilderControlOrConfigValue("settings-builder-1080p-route-bitrate", "Route1080pMaxVideoBitrateMbps", "20");
      setText(
        "settings-advanced-routing-summary",
        `Unknown height uses 1080p: Movie ${movieFallbackSize} GB / TV ${tvFallbackSize} GB, cap ${fallbackBitrate} Mbps.`
      );
    }

    function renderRouteVideoReadouts() {
      setText("settings-routing-video-codec-readout", settingsBuilderSelectText("settings-builder-video-codec", "VideoCodec", "hevc_nvenc"));
      setText("settings-routing-output-container-readout", settingsBuilderSelectText("settings-builder-output-container", "OutputContainer", "mkv"));
      setText("settings-routing-video-preset-readout", formatSettingsChoiceLabel(settingsBuilderConfigValue("VideoPreset", "p5")));
      setText("settings-routing-video-quality-readout", formatConfigValue(settingsBuilderConfigValue("VideoQuality", 22)));
    }

    function routeEstimatedSizeGb(mbps, minutes) {
      const bitrate = Number(mbps);
      if (!Number.isFinite(bitrate) || bitrate <= 0) return null;
      return (bitrate * minutes * 60) / 8000;
    }

    function routeFormatEstimatedGb(value) {
      const number = Number(value);
      if (!Number.isFinite(number)) return "";
      return number.toFixed(1).replace(/\.0$/, "");
    }

    function renderRouteBitrateSizeEstimates() {
      [
        ["settings-builder-1080p-route-bitrate", "Route1080pMaxVideoBitrateMbps", 20, "settings-bitrate-estimate-1080p"],
        ["settings-builder-1440p-route-bitrate", "Route1440pMaxVideoBitrateMbps", 35, "settings-bitrate-estimate-1440p"],
        ["settings-builder-4k-route-bitrate", "Route4KMaxVideoBitrateMbps", 35, "settings-bitrate-estimate-4k"],
      ].forEach(([inputId, key, fallback, outputId]) => {
        const bitrate = Number(settingsBuilderControlOrConfigValue(inputId, key, fallback));
        const tvSize = routeEstimatedSizeGb(bitrate, 30);
        const movieSize = routeEstimatedSizeGb(bitrate, 120);
        if (tvSize === null || movieSize === null) {
          setText(outputId, "If constant: enter Mbps to estimate size");
          return;
        }
        setText(
          outputId,
          `If constant: 30m TV ~${routeFormatEstimatedGb(tvSize)} GB; 2h movie ~${routeFormatEstimatedGb(movieSize)} GB`
        );
      });
    }

    function renderRouteHeightTolerancePreview() {
      const boundaries = routeHeightToleranceBoundariesFromControls();
      syncRouteBoundaryControls(boundaries);
      renderRoutePercentReadouts();
      setText("settings-height-1080p-range", `<=${boundaries.route1080pMaxHeight}p`);
      setText("settings-height-1440p-range", `${boundaries.route1440pMinHeight}-${boundaries.route1440pMaxHeight}p`);
      setText("settings-height-4k-range", `>=${boundaries.route4kMinHeight}p`);
      setText("settings-route-card-range-1080p", `uses <=${boundaries.route1080pMaxHeight}p`);
      setText("settings-route-card-range-1440p", `uses ${boundaries.route1440pMinHeight}-${boundaries.route1440pMaxHeight}p`);
      setText("settings-route-card-range-4k", `uses >=${boundaries.route4kMinHeight}p`);
      setText(
        "settings-height-pixel-summary",
        `Derived direct-copy buckets: 1080p <=${boundaries.route1080pMaxHeight}p, 1440p ${boundaries.route1440pMinHeight}-${boundaries.route1440pMaxHeight}p, 4K >=${boundaries.route4kMinHeight}p. Boundary values route to the higher bucket.`
      );
      setSettingsBuilderControl("settings-builder-routing-profile-key-readout", settingsBuilderInputValue("settings-builder-routing-profile"));
      renderRouteTriggerSummary();
      renderRouteConsequenceSummary(boundaries);
      renderRouteAdvancedSummary();
      renderRouteVideoReadouts();
      renderRouteBitrateSizeEstimates();
      return boundaries;
    }

    function normalizeRouteHeightTolerancePair(changedId) {
      if (changedId === "settings-builder-1080p-upper-tolerance") {
        const nextLine = routeMaxHeightFromUpperTolerance(
          1080,
          routeToleranceValue(changedId, routeHeightToleranceDefaults.route1080pUpperPercent)
        ) + 1;
        setRouteFirstBoundary(nextLine);
      } else if (changedId === "settings-builder-1440p-lower-tolerance") {
        const nextLine = routeMinHeightFromLowerTolerance(
          1440,
          routeToleranceValue(changedId, routeHeightToleranceDefaults.route1440pLowerPercent)
        );
        setRouteFirstBoundary(nextLine);
      } else if (changedId === "settings-builder-1440p-upper-tolerance") {
        const nextLine = routeMaxHeightFromUpperTolerance(
          1440,
          routeToleranceValue(changedId, routeHeightToleranceDefaults.route1440pUpperPercent)
        ) + 1;
        setRouteSecondBoundary(nextLine);
      } else if (changedId === "settings-builder-4k-lower-tolerance") {
        const nextLine = routeMinHeightFromLowerTolerance(
          2160,
          routeToleranceValue(changedId, routeHeightToleranceDefaults.route4kLowerPercent)
        );
        setRouteSecondBoundary(nextLine);
      }
      renderRouteHeightTolerancePreview();
    }

    function syncSettingsBuilderFromConfig() {
      refreshSettingsBuilderChoices();
      setSettingsBuilderControl("settings-builder-routing-profile", settingsBuilderConfigValue("RoutingProfile", "plex_direct_stream"));
      setSettingsBuilderControl("settings-builder-route-threshold-mode", settingsBuilderConfigValue("RouteThresholdMode", "compatibility_advisory"));
      setSettingsBuilderControl("settings-builder-size-guard", settingsBuilderConfigValue("SizeGuardMode", "advisory"));
      setSettingsBuilderControl("settings-builder-max-growth", settingsBuilderConfigValue("MaxEncodeGrowthPercent", 5));
      setSettingsBuilderControl("settings-builder-compat-growth", settingsBuilderConfigValue("CompatibilityEncodeGrowthPercent", 15));
      setSettingsBuilderControl("settings-builder-movie-1080p-target", settingsBuilderConfigValue("MovieRoute1080pTargetSizeGB", 8));
      setSettingsBuilderControl("settings-builder-movie-1440p-target", settingsBuilderConfigValue("MovieRoute1440pTargetSizeGB", 8));
      setSettingsBuilderControl("settings-builder-movie-4k-target", settingsBuilderConfigValue("MovieRoute4KTargetSizeGB", 8));
      setSettingsBuilderControl("settings-builder-tv-1080p-target", settingsBuilderConfigValue("TVRoute1080pTargetSizeGB", 3));
      setSettingsBuilderControl("settings-builder-tv-1440p-target", settingsBuilderConfigValue("TVRoute1440pTargetSizeGB", 3));
      setSettingsBuilderControl("settings-builder-tv-4k-target", settingsBuilderConfigValue("TVRoute4KTargetSizeGB", 3));
      setSettingsBuilderControl("settings-builder-1080p-route-bitrate", settingsBuilderConfigValue("Route1080pMaxVideoBitrateMbps", 20));
      setSettingsBuilderControl("settings-builder-1440p-route-bitrate", settingsBuilderConfigValue("Route1440pMaxVideoBitrateMbps", 35));
      setSettingsBuilderControl("settings-builder-4k-route-bitrate", settingsBuilderConfigValue("Route4KMaxVideoBitrateMbps", 35));
      const routeBoundaries = routeHeightToleranceBoundariesFromConfigValues();
      setRouteFirstBoundary(routeBoundaries.route1080pMaxHeight + 1);
      setRouteSecondBoundary(routeBoundaries.route4kMinHeight);
      renderRouteHeightTolerancePreview();
      setSettingsBuilderState(true, false);
      setText("settings-builder-status", "Loaded current values");
      renderSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markSettingsBuilderDirty(event) {
      const changedId = event?.target?.id || "";
      normalizeRouteHeightTolerancePair(changedId);
      setSettingsBuilderState(true, true);
      setText("settings-builder-status", "Editing builder values");
      renderSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function settingsBuilderInputValue(id) {
      return String(byId(id)?.value ?? "").trim();
    }

    function settingsBuilderPreciseInputValue(id) {
      const element = byId(id);
      const value = String(element?.value ?? "").trim();
      if (!element) return value;
      const routeDisplayValue = String(element.dataset.routeDisplayValue || "").trim();
      const routePreciseValue = String(element.dataset.routePreciseValue || "").trim();
      if (routePreciseValue && value === routeDisplayValue) return routePreciseValue;
      return value;
    }

    function readSettingsBuilderNumber(id, label) {
      const raw = settingsBuilderInputValue(id);
      if (!raw) throw new Error(`${label} is required.`);
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0) throw new Error(`${label} must be zero or higher.`);
      return Math.round(value);
    }

    function readSettingsBuilderFloat(id, label) {
      const raw = settingsBuilderInputValue(id);
      if (!raw) throw new Error(`${label} is required.`);
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0) throw new Error(`${label} must be zero or higher.`);
      return value;
    }

    function readSettingsBuilderPercent(id, label) {
      const raw = settingsBuilderPreciseInputValue(id);
      if (!raw) throw new Error(`${label} is required.`);
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0) throw new Error(`${label} must be zero or higher.`);
      if (value > 100) throw new Error(`${label} must be 100 or lower.`);
      return Number(value.toFixed(6));
    }

    function settingsRawConfigValue(key) {
      const values = getLastSettingsValues() || {};
      if (Object.prototype.hasOwnProperty.call(values, key)) return values[key];
      const match = Object.keys(values).find((item) => item.toLowerCase() === String(key).toLowerCase());
      return match ? values[match] : undefined;
    }

    function parseSettingsPatchJson() {
      const raw = byId("settings-patch-json")?.value || "{}";
      const parsed = JSON.parse(raw);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("Patch JSON must be an object of config keys and values.");
      }
      return parsed;
    }

    function markSettingsPatchTouched() {
      setSettingsPatchTouched(true);
    }

    function settingsPatchIsTouched() {
      return getSettingsPatchTouched();
    }

    function settingsPatchEffectiveChangedEntries() {
      if (!settingsPatchIsTouched()) return [];
      return settingsPatchImpactEntries(parseSettingsPatchJson()).filter((entry) => entry.changed);
    }

    function settingsPatchHasUnsavedChanges() {
      return settingsPatchEffectiveChangedEntries().length > 0;
    }

    function readSettingsPatchJsonForMerge() {
      try {
        return parseSettingsPatchJson();
      } catch {
        return {};
      }
    }

    function writeSettingsPatchJson(patch, detail) {
      const textarea = byId("settings-patch-json");
      if (!textarea) return;
      const merged = { ...readSettingsPatchJsonForMerge(), ...patch };
      markSettingsPatchTouched();
      textarea.value = JSON.stringify(merged, null, 2);
      setText("settings-patch-status", "Changes ready");
      setText("settings-patch-detail", detail || "Builder updated the current save candidate. Save Settings still uses backend validation.");
      renderSettingsPatchSummary();
      renderAllLaunchPreflights();
    }

    function collectSettingsBuilderPatch() {
      normalizeRouteHeightTolerancePair("settings-builder-1080p-upper-tolerance");
      normalizeRouteHeightTolerancePair("settings-builder-4k-lower-tolerance");
      const patch = {
        RoutingProfile: settingsBuilderInputValue("settings-builder-routing-profile"),
        RouteThresholdMode: settingsBuilderInputValue("settings-builder-route-threshold-mode"),
        SizeGuardMode: settingsBuilderInputValue("settings-builder-size-guard"),
        MaxEncodeGrowthPercent: readSettingsBuilderNumber("settings-builder-max-growth", settingsDisplayLabel("MaxEncodeGrowthPercent", "Normal growth percent")),
        CompatibilityEncodeGrowthPercent: readSettingsBuilderNumber("settings-builder-compat-growth", settingsDisplayLabel("CompatibilityEncodeGrowthPercent", "Compatibility growth percent")),
        MovieRoute1080pTargetSizeGB: readSettingsBuilderNumber("settings-builder-movie-1080p-target", settingsDisplayLabel("MovieRoute1080pTargetSizeGB", "Movie 1080p target size GB")),
        MovieRoute1440pTargetSizeGB: readSettingsBuilderNumber("settings-builder-movie-1440p-target", settingsDisplayLabel("MovieRoute1440pTargetSizeGB", "Movie 1440p target size GB")),
        MovieRoute4KTargetSizeGB: readSettingsBuilderNumber("settings-builder-movie-4k-target", settingsDisplayLabel("MovieRoute4KTargetSizeGB", "Movie 4K target size GB")),
        TVRoute1080pTargetSizeGB: readSettingsBuilderNumber("settings-builder-tv-1080p-target", settingsDisplayLabel("TVRoute1080pTargetSizeGB", "TV 1080p target size GB")),
        TVRoute1440pTargetSizeGB: readSettingsBuilderNumber("settings-builder-tv-1440p-target", settingsDisplayLabel("TVRoute1440pTargetSizeGB", "TV 1440p target size GB")),
        TVRoute4KTargetSizeGB: readSettingsBuilderNumber("settings-builder-tv-4k-target", settingsDisplayLabel("TVRoute4KTargetSizeGB", "TV 4K target size GB")),
        Route1080pUpperHeightTolerancePercent: readSettingsBuilderPercent("settings-builder-1080p-upper-tolerance", settingsDisplayLabel("Route1080pUpperHeightTolerancePercent", "1080p upper height tolerance")),
        Route1080pMaxVideoBitrateMbps: readSettingsBuilderNumber("settings-builder-1080p-route-bitrate", settingsDisplayLabel("Route1080pMaxVideoBitrateMbps", "1080p max video bitrate Mbps")),
        Route1440pLowerHeightTolerancePercent: readSettingsBuilderPercent("settings-builder-1440p-lower-tolerance", settingsDisplayLabel("Route1440pLowerHeightTolerancePercent", "1440p lower height tolerance")),
        Route1440pUpperHeightTolerancePercent: readSettingsBuilderPercent("settings-builder-1440p-upper-tolerance", settingsDisplayLabel("Route1440pUpperHeightTolerancePercent", "1440p upper height tolerance")),
        Route1440pMaxVideoBitrateMbps: readSettingsBuilderNumber("settings-builder-1440p-route-bitrate", settingsDisplayLabel("Route1440pMaxVideoBitrateMbps", "1440p max video bitrate Mbps")),
        Route4KLowerHeightTolerancePercent: readSettingsBuilderPercent("settings-builder-4k-lower-tolerance", settingsDisplayLabel("Route4KLowerHeightTolerancePercent", "4K lower height tolerance")),
        Route4KMaxVideoBitrateMbps: readSettingsBuilderNumber("settings-builder-4k-route-bitrate", settingsDisplayLabel("Route4KMaxVideoBitrateMbps", "4K max video bitrate Mbps")),
      };
      const boundaries = routeHeightToleranceBoundariesFromControls();
      if (
        boundaries.route1440pMinHeight !== boundaries.route1080pMaxHeight + 1
        || boundaries.route4kMinHeight !== boundaries.route1440pMaxHeight + 1
      ) {
        throw new Error("Height tolerance buckets must be contiguous without overlap or gaps.");
      }
      Object.entries(patch).forEach(([key, value]) => {
        if (typeof value === "string" && !value.trim()) {
          throw new Error(`${key} must be selected.`);
        }
      });
      return patch;
    }

    function applySettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-builder-status", "Invalid builder value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return false;
      }
      writeSettingsPatchJson(patch, "Structured builder prepared routing, size, and encoder keys for Save Settings. Backend Save still validates before writing.");
      setSettingsBuilderState(true, true);
      setText("settings-builder-status", `${Object.keys(patch).length} change keys ready`);
      renderSettingsBuilderGuidance();
      return true;
    }

    function renderSettings(settings) {
      const config = settings?.config || {};
      const settingsEntries = Object.keys(config).sort((a, b) => a.localeCompare(b)).map((key) => ({
        key,
        value: formatConfigValue(config[key]),
      }));
      setSettingsRows(settingsEntries, settings?.error || "No config values loaded.");
      const warnings = (settings?.warnings || []).concat(settings?.errors || []);
      setText("settings-status", warnings.length ? `${warnings.length} warning${warnings.length === 1 ? "" : "s"}` : "Read-only");
      setText("settings-count", `${settings?.key_count || settingsEntries.length} keys`);
      const pathLines = Object.entries(settings?.paths || {}).map(([key, value]) => `${key}: ${value}`);
      setText("settings-paths", pathLines.join("\n") || settings?.error || "No settings paths loaded.");
      setText("settings-profiles", settingsProfileSummaryLines(settings));
      setText("settings-validation", warnings.join("\n") || "No validation warnings.");
      renderSettingsOverview(config);
      renderHandbrakePreviewSummary(settings);
      renderSettingsOperatorTrust(settings);
      renderSettingsBackendMediaPolicyReadiness(settings);
      const builderState = getSettingsBuilderState();
      if (!builderState.initialized || !builderState.dirty) {
        addSettingsEventHandlers.syncSettingsBuilderFromConfig();
      } else {
        refreshSettingsBuilderChoices();
        renderSettingsBuilderGuidance();
      }
      if (!videoDetailSettingsBuilderState.initialized || !videoDetailSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncVideoDetailSettingsBuilderFromConfig();
      } else {
        refreshSettingsSelectChoices(videoDetailSettingsBuilderFields);
        addSettingsEventHandlers.renderVideoDetailSettingsBuilderGuidance();
      }
      if (!qualityDetailSettingsBuilderState.initialized || !qualityDetailSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncQualityDetailSettingsBuilderFromConfig();
      } else {
        refreshSettingsSelectChoices(qualityDetailSettingsBuilderFields);
        addSettingsEventHandlers.renderQualityDetailSettingsBuilderGuidance();
      }
      if (!fileSafetySettingsBuilderState.initialized || !fileSafetySettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncFileSafetySettingsBuilderFromConfig();
      } else {
        addSettingsEventHandlers.renderFileSafetySettingsBuilderGuidance();
      }
      if (!networkSettingsBuilderState.initialized || !networkSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncNetworkSettingsBuilderFromConfig();
      } else {
        refreshSettingsSelectChoices(networkSettingsBuilderFields);
        addSettingsEventHandlers.renderNetworkSettingsBuilderGuidance();
      }
      if (!queueSettingsBuilderState.initialized || !queueSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncQueueSettingsBuilderFromConfig();
      } else {
        addSettingsEventHandlers.renderQueueSettingsBuilderGuidance();
      }
      if (!runtimeSettingsBuilderState.initialized || !runtimeSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncRuntimeSettingsBuilderFromConfig();
      } else {
        refreshSettingsSelectChoices(runtimeSettingsBuilderFields);
        addSettingsEventHandlers.renderRuntimeSettingsBuilderGuidance();
      }
      if (!pendingPublishSettingsBuilderState.initialized || !pendingPublishSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncPendingPublishSettingsBuilderFromConfig();
      } else {
        addSettingsEventHandlers.renderPendingPublishSettingsBuilderGuidance();
      }
      if (!subtitleSettingsBuilderState.initialized || !subtitleSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncSubtitleSettingsBuilderFromConfig();
      } else {
        addSettingsEventHandlers.renderSubtitleSettingsBuilderGuidance();
      }
      if (!audioSettingsBuilderState.initialized || !audioSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncAudioSettingsBuilderFromConfig();
      } else {
        refreshAudioSettingsBuilderChoices();
        addSettingsEventHandlers.renderAudioSettingsBuilderGuidance();
      }
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
      renderSettingsBdpgsOcrPathEvidence();
      renderSettingsVobSubOcrPathEvidence();
      renderSettingsPatchSummary();
      renderSettingsSafetyLocks();
      renderSettingsRawTriage();
      renderSettingsRawActionPlan();
      renderSettingsRows();
    }

    function routeRailBoundaryFromSegment(target, event) {
      const boundary = target?.dataset?.routeDragBoundary || "";
      if (boundary === "first" || boundary === "second") return boundary;
      if (boundary === "middle" && event) {
        const rect = target.getBoundingClientRect();
        return event.clientX < rect.left + (rect.width / 2) ? "first" : "second";
      }
      return "";
    }

    function routeRailTrackRect(rail) {
      const track = rail?.querySelector?.(".settings-route-slider-track");
      const trackRect = track?.getBoundingClientRect?.();
      if (trackRect && trackRect.width > 0) return trackRect;
      return rail?.getBoundingClientRect?.() || null;
    }

    function routeRailHeightFromPointer(boundary, event, rail) {
      const config = routeRailBoundaryConfig(boundary);
      const rect = routeRailTrackRect(rail);
      if (!config || !event || !rect) return null;
      const ratio = routeClamp((event.clientX - rect.left) / Math.max(rect.width, 1), 0, 1);
      const height = 1080 + (ratio * (2160 - 1080));
      return routeClamp(Math.round(height), config.min, config.max);
    }

    function routeRailApplyDrag(event) {
      if (!routeRailDragState) return;
      event.preventDefault();
      const config = routeRailBoundaryConfig(routeRailDragState.boundary);
      if (!config) return;
      const height = routeRailDragState.mode === "absolute"
        ? routeRailHeightFromPointer(routeRailDragState.boundary, event, routeRailDragState.rail)
        : routeRailDragState.startHeight + Math.round(
          (event.clientX - routeRailDragState.startX) * ((2160 - 1080) / Math.max(routeRailDragState.railWidth, 1))
        );
      if (height === null || height === undefined) return;
      applyRouteRailBoundaryHeight(routeRailDragState.boundary, height);
      markSettingsBuilderDirty({ target: { id: routeRailDragState.inputId } });
    }

    function routeRailEndDrag() {
      if (!routeRailDragState) return;
      routeRailDragState.target?.classList.remove("is-dragging");
      routeRailDragState = null;
      document.removeEventListener("pointermove", routeRailApplyDrag);
      document.removeEventListener("pointerup", routeRailEndDrag);
      document.removeEventListener("pointercancel", routeRailEndDrag);
    }

    function routeRailStartDrag(event) {
      if (event.button !== undefined && event.button !== 0) return;
      if (event.target?.closest?.("input, select, textarea, button")) return;
      const target = event.target?.closest?.("[data-route-drag-boundary]");
      if (!target) return;
      const boundary = routeRailBoundaryFromSegment(target, event);
      const config = routeRailBoundaryConfig(boundary);
      const rail = target.closest(".settings-route-range-rail");
      if (!config || !rail) return;
      event.preventDefault();
      routeRailEndDrag();
      const trackRect = routeRailTrackRect(rail);
      const mode = target.classList.contains("settings-route-slider-hit") ? "absolute" : "delta";
      if (mode === "absolute") {
        const height = routeRailHeightFromPointer(boundary, event, rail);
        if (height !== null && height !== undefined) {
          applyRouteRailBoundaryHeight(boundary, height);
          markSettingsBuilderDirty({ target: { id: config.inputId } });
        }
      }
      routeRailDragState = {
        boundary,
        inputId: config.inputId,
        mode,
        rail,
        railWidth: Math.max(trackRect?.width || rail.getBoundingClientRect().width, 1),
        startHeight: routeRailCurrentBoundaryHeight(boundary),
        startX: event.clientX,
        target,
      };
      target.classList.add("is-dragging");
      document.addEventListener("pointermove", routeRailApplyDrag);
      document.addEventListener("pointerup", routeRailEndDrag);
      document.addEventListener("pointercancel", routeRailEndDrag);
    }

    function bindRouteRangeRailControls() {
      const rail = byId("settings-route-boundary-1080p-end-input")?.closest?.(".settings-route-range-rail");
      if (!rail || rail.dataset.routeRailBound === "true") return;
      rail.dataset.routeRailBound = "true";
      rail.addEventListener("pointerdown", routeRailStartDrag);
      [
        "settings-route-boundary-1080p-end-input",
        "settings-route-boundary-4k-start-input",
      ].forEach((id) => {
        const input = byId(id);
        if (!input) return;
        input.addEventListener("change", () => applyRouteRailBoundaryInput(id));
        input.addEventListener("keydown", (event) => {
          if (event.key !== "Enter") return;
          event.preventDefault();
          applyRouteRailBoundaryInput(id);
          input.blur();
        });
      });
    }

    function bindSettingsControls(fields, handler) {
      if (typeof handler !== "function") return;
      fields.forEach(([, id]) => {
        const control = byId(id);
        if (control) control.addEventListener("input", handler);
        if (control) control.addEventListener("change", handler);
      });
    }

    function bindSettingsClick(id, handler) {
      const element = byId(id);
      if (element && typeof handler === "function") element.addEventListener("click", handler);
    }

    function initSettingsViewEvents() {
      bindSettingsClick("settings-validate-button", addSettingsEventHandlers.validateCurrentSettings);
      bindSettingsClick("settings-reload-button", addSettingsEventHandlers.reloadSettingsFromDisk);
      bindSettingsClick("settings-save-patch-button", addSettingsEventHandlers.saveSettingsPatch);
      bindSettingsClick("settings-summarize-patch-button", renderSettingsPatchSummary);
      const settingsPatchJson = byId("settings-patch-json");
      if (settingsPatchJson) settingsPatchJson.addEventListener("input", () => {
        if (typeof addSettingsEventHandlers.markSettingsPatchTouched === "function") addSettingsEventHandlers.markSettingsPatchTouched();
        renderSettingsPatchSummary();
        renderAllLaunchPreflights();
      });
      const changedOnly = byId("settings-patch-summary-changed-only");
      if (changedOnly) changedOnly.addEventListener("change", renderSettingsPatchSummary);
      bindSettingsClick("settings-builder-apply-button", addSettingsEventHandlers.applySettingsBuilderToPatch);
      bindSettingsClick("settings-builder-reset-button", addSettingsEventHandlers.syncSettingsBuilderFromConfig);
      bindSettingsControls(settingsBuilderFields, addSettingsEventHandlers.markSettingsBuilderDirty);
      bindRouteRangeRailControls();
      bindSettingsClick("settings-video-apply-button", addSettingsEventHandlers.applyVideoDetailSettingsBuilderToPatch);
      bindSettingsClick("settings-video-reset-button", addSettingsEventHandlers.syncVideoDetailSettingsBuilderFromConfig);
      bindSettingsControls(videoDetailSettingsBuilderFields, addSettingsEventHandlers.markVideoDetailSettingsBuilderDirty);
      bindSettingsClick("settings-quality-apply-button", addSettingsEventHandlers.applyQualityDetailSettingsBuilderToPatch);
      bindSettingsClick("settings-quality-reset-button", addSettingsEventHandlers.syncQualityDetailSettingsBuilderFromConfig);
      bindSettingsControls(qualityDetailSettingsBuilderFields, addSettingsEventHandlers.markQualityDetailSettingsBuilderDirty);
      bindSettingsClick("settings-file-safety-apply-button", addSettingsEventHandlers.applyFileSafetySettingsBuilderToPatch);
      bindSettingsClick("settings-file-safety-reset-button", addSettingsEventHandlers.syncFileSafetySettingsBuilderFromConfig);
      bindSettingsControls(fileSafetySettingsBuilderFields, addSettingsEventHandlers.markFileSafetySettingsBuilderDirty);
      document.querySelectorAll("[data-settings-path-browse-key]").forEach((button) => {
        button.addEventListener("click", () => {
          if (typeof addSettingsEventHandlers.browseSettingsPath === "function") {
            addSettingsEventHandlers.browseSettingsPath(button.dataset.settingsPathKey || "", button.dataset.settingsPathInput || "");
          }
        });
      });
      bindSettingsClick("settings-network-apply-button", addSettingsEventHandlers.applyNetworkSettingsBuilderToPatch);
      bindSettingsClick("settings-network-reset-button", addSettingsEventHandlers.syncNetworkSettingsBuilderFromConfig);
      bindSettingsControls(networkSettingsBuilderFields, addSettingsEventHandlers.markNetworkSettingsBuilderDirty);
      bindSettingsClick("settings-queue-apply-button", addSettingsEventHandlers.applyQueueSettingsBuilderToPatch);
      bindSettingsClick("settings-queue-reset-button", addSettingsEventHandlers.syncQueueSettingsBuilderFromConfig);
      bindSettingsControls(queueSettingsBuilderFields, addSettingsEventHandlers.markQueueSettingsBuilderDirty);
      bindSettingsClick("settings-runtime-apply-button", addSettingsEventHandlers.applyRuntimeSettingsBuilderToPatch);
      bindSettingsClick("settings-runtime-reset-button", addSettingsEventHandlers.syncRuntimeSettingsBuilderFromConfig);
      bindSettingsControls(runtimeSettingsBuilderFields, addSettingsEventHandlers.markRuntimeSettingsBuilderDirty);
      bindSettingsClick("settings-pending-apply-button", addSettingsEventHandlers.applyPendingPublishSettingsBuilderToPatch);
      bindSettingsClick("settings-pending-reset-button", addSettingsEventHandlers.syncPendingPublishSettingsBuilderFromConfig);
      bindSettingsControls(pendingPublishSettingsBuilderFields, addSettingsEventHandlers.markPendingPublishSettingsBuilderDirty);
      bindSettingsClick("settings-subtitle-apply-button", addSettingsEventHandlers.applySubtitleSettingsBuilderToPatch);
      bindSettingsClick("settings-subtitle-reset-button", addSettingsEventHandlers.syncSubtitleSettingsBuilderFromConfig);
      bindSettingsControls(subtitleSettingsBuilderFields, addSettingsEventHandlers.markSubtitleSettingsBuilderDirty);
      bindSettingsClick("settings-audio-apply-button", addSettingsEventHandlers.applyAudioSettingsBuilderToPatch);
      bindSettingsClick("settings-audio-reset-button", addSettingsEventHandlers.syncAudioSettingsBuilderFromConfig);
      bindSettingsControls(audioSettingsBuilderFields, addSettingsEventHandlers.markAudioSettingsBuilderDirty);
      const settingsFilter = byId("settings-filter");
      if (settingsFilter) settingsFilter.addEventListener("input", renderSettingsRows);
    }

    function settingsLocalValidationHint(severity, context, key, message) {
      return {
        severity,
        context,
        key,
        message,
      };
    }

    function settingsAllowedValueHint(field, key, value, context) {
      const allowedValues = settingsFieldAllowedValues(field);
      if (!allowedValues.length) return [];
      const allowedText = allowedValues.map((item) => String(item));
      const values = Array.isArray(value) ? value : [value];
      const badValues = values
        .filter((item) => item !== null && item !== undefined && item !== "")
        .map((item) => String(item))
        .filter((item) => !allowedText.includes(item));
      if (!badValues.length) return [];
      return [
        settingsLocalValidationHint(
          "warning",
          context,
          key,
          `${key} has value ${badValues.join(", ")} outside backend allowed_values (${allowedText.join(", ")}).`
        ),
      ];
    }

    function settingsNumericConstraintHints(field, key, value, context) {
      if (value === null || value === undefined || value === "" || Array.isArray(value) || typeof value === "object") return [];
      const valueType = String(field?.value_type || "");
      const kind = String(field?.kind || "");
      const numeric = ["integer", "number"].includes(valueType) || ["int", "optional_int", "combo_int", "optional_float"].includes(kind);
      if (!numeric) return [];
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        return [settingsLocalValidationHint("warning", context, key, `${key} should be numeric according to backend metadata.`)];
      }
      const hints = [];
      if (field.min !== null && field.min !== undefined && numberValue < Number(field.min)) {
        hints.push(settingsLocalValidationHint("warning", context, key, `${key} is below backend min ${field.min}.`));
      }
      if (field.max !== null && field.max !== undefined && numberValue > Number(field.max)) {
        hints.push(settingsLocalValidationHint("warning", context, key, `${key} is above backend max ${field.max}.`));
      }
      if (field.step !== null && field.step !== undefined && field.step !== "") {
        const step = Number(field.step);
        const base = Number.isFinite(Number(field.min)) ? Number(field.min) : 0;
        if (Number.isFinite(step) && step > 0) {
          const ratio = (numberValue - base) / step;
          if (Math.abs(ratio - Math.round(ratio)) > 1e-9) {
            hints.push(settingsLocalValidationHint("warning", context, key, `${key} does not align to backend step ${field.step}.`));
          }
        }
      }
      return hints;
    }

    function settingsPatchLocalValidationHintsForKey(key, value, context = "settings", options = {}) {
      const hints = [];
      const friendlyTarget = settingsFriendlyPersistedKeyAliases[key];
      if (friendlyTarget) {
        hints.push(settingsLocalValidationHint(
          "error",
          context,
          key,
          `${key} is a display label only; use persisted key ${friendlyTarget}.`
        ));
      }
      const field = settingsFieldDefinition(key);
      if (!field) {
        if (settingsHasBackendFieldDefinitions() && !settingsPatchComplexBackendKeys.has(key)) {
          hints.push(settingsLocalValidationHint(
            "warning",
            context,
            key,
            `${key} is not in backend field metadata loaded by this WebView. Backend Save remains authoritative.`
          ));
        }
        return hints;
      }
      if (options.libraryOverride === true) {
        const scope = String(field.scope || "");
        const overrideGroup = String(field.override_group || "");
        if (field.library_override_allowed !== true) {
          hints.push(settingsLocalValidationHint(
            "error",
            context,
            key,
            scope === "source_derived" || scope === "computed_only"
              ? `${key} is read-only source/effective metadata and cannot be saved as a library override.`
              : `${key} is global-only and cannot be saved as a library override.`
          ));
        } else if (options.overrideGroup && overrideGroup && overrideGroup !== options.overrideGroup) {
          hints.push(settingsLocalValidationHint(
            "error",
            context,
            key,
            `${key} belongs in overrides.${overrideGroup}, not overrides.${options.overrideGroup}.`
          ));
        }
      }
      hints.push(...settingsAllowedValueHint(field, key, value, context));
      hints.push(...settingsNumericConstraintHints(field, key, value, context));
      return hints;
    }

    function settingsPatchLibraryOverrideValidationHints(libraryProfiles) {
      if (!Array.isArray(libraryProfiles)) return [];
      const hints = [];
      libraryProfiles.forEach((profile, index) => {
        if (!profile || typeof profile !== "object") return;
        const profileLabel = String(profile.id || profile.name || `profile ${index + 1}`);
        const overrides = profile.overrides && typeof profile.overrides === "object" && !Array.isArray(profile.overrides)
          ? profile.overrides
          : {};
        ["editor", "video", "subtitles", "audio"].forEach((group) => {
          const groupValues = overrides[group];
          if (!groupValues || typeof groupValues !== "object" || Array.isArray(groupValues)) return;
          Object.entries(groupValues).forEach(([key, value]) => {
            hints.push(...settingsPatchLocalValidationHintsForKey(
              String(key),
              value,
              `LibraryProfiles.${profileLabel}.overrides.${group}`,
              { libraryOverride: true, overrideGroup: group }
            ));
          });
        });
        ["editor_overrides", "media_overrides"].forEach((legacyGroup) => {
          const groupValues = profile[legacyGroup];
          if (!groupValues || typeof groupValues !== "object" || Array.isArray(groupValues)) return;
          Object.entries(groupValues).forEach(([key, value]) => {
            hints.push(...settingsPatchLocalValidationHintsForKey(
              String(key),
              value,
              `LibraryProfiles.${profileLabel}.${legacyGroup}`,
              { libraryOverride: true }
            ));
          });
        });
      });
      return hints;
    }

    function settingsPatchLocalValidationHints(changes) {
      if (!changes || Array.isArray(changes) || typeof changes !== "object") return [];
      const hints = [];
      Object.entries(changes).forEach(([key, value]) => {
        hints.push(...settingsPatchLocalValidationHintsForKey(String(key), value, "settings"));
        if (key === "LibraryProfiles") {
          hints.push(...settingsPatchLibraryOverrideValidationHints(value));
        }
      });
      return hints;
    }

    function settingsPatchLocalValidationHintLines(changes) {
      const hints = settingsPatchLocalValidationHints(changes);
      if (!hints.length) return [];
      return [
        "Local validation hints (advisory only; backend Save remains authoritative):",
        ...hints.map((hint) => `- [${hint.severity}] ${hint.context}.${hint.key}: ${hint.message}`),
      ];
    }

    function settingsReadinessIssue(severity, message) {
      return { severity, message };
    }

    function settingsPatchSaveReadinessIssues(entries) {
      const changedEntries = entries.filter((entry) => entry.changed);
      const issues = [];
      const boolValue = (key) => settingsBoolValue(settingsPatchCandidateValue(entries, key));
      const listValue = (key) => settingsPatchListValue(settingsPatchCandidateValue(entries, key));
      const textValue = (key) => String(settingsPatchCandidateValue(entries, key) ?? "").trim();
      const changedKey = (key) => changedEntries.some((entry) => entry.key === key);

      entries.filter((entry) => !entry.field).forEach((entry) => {
        issues.push(settingsReadinessIssue("high", `Unknown key '${entry.key}' is not in the WebView schema; backend save validation must accept it before writing.`));
      });
      changedEntries.filter((entry) => entry.severity === "high" && entry.field).forEach((entry) => {
        issues.push(settingsReadinessIssue("review", `${entry.label} is a high-impact setting. Confirm the change before saving.`));
      });
      if (changedKey("DeleteSourceAfterProcessing") && boolValue("DeleteSourceAfterProcessing") === true) {
        issues.push(settingsReadinessIssue("critical", "DeleteSourceAfterProcessing would allow source deletion. This must stay an explicit, intentional source-safety decision."));
      }
      if (changedKey("SkipStabilityCheck") && boolValue("SkipStabilityCheck") === true) {
        issues.push(settingsReadinessIssue("high", "SkipStabilityCheck is enabled. Half-copied downloads, active torrents, and network-share writes can enter processing."));
      }
      if (changedKey("EnableIntegrityCheck") && boolValue("EnableIntegrityCheck") === false) {
        issues.push(settingsReadinessIssue("high", "EnableIntegrityCheck is disabled. Corrupt or partially-written sources may pass discovery."));
      }
      if (changedKey("AllowNoAudio") && boolValue("AllowNoAudio") === true) {
        issues.push(settingsReadinessIssue("high", "AllowNoAudio is enabled. Outputs without audio can be published and look broken in Plex."));
      }
      if (changedKey("ReprocessAll") && boolValue("ReprocessAll") === true) {
        issues.push(settingsReadinessIssue("medium", "ReprocessAll is enabled. A future run can reconsider already-completed outputs."));
      }
      if (changedKey("ExtraVideoFlags") && listValue("ExtraVideoFlags").length) {
        issues.push(settingsReadinessIssue("high", "ExtraVideoFlags contains legacy raw FFmpeg flags. Backend risk preview should review this before save."));
      }
      if (changedKey("ValidExtensions") && listValue("ValidExtensions").some((item) => !String(item).startsWith("."))) {
        issues.push(settingsReadinessIssue("medium", "ValidExtensions contains values without a leading dot. Backend preview should reject or normalize this."));
      }
      if (changedKey("ValidExtensions") && listValue("ValidExtensions").some((item) => [".part", ".tmp", ".crdownload", ".download"].includes(String(item).toLowerCase()))) {
        issues.push(settingsReadinessIssue("high", "ValidExtensions includes partial-download style extensions."));
      }
      if (changedKey("DropTx3gAfterConversion") && boolValue("DropTx3gAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "TX3G originals will be dropped after conversion. Keep disabled to preserve source subtitle tracks."));
      }
      if (changedKey("DropBdpgsAfterConversion") && boolValue("DropBdpgsAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "BDPGS originals will be dropped after OCR. Keep disabled when preserving image subtitle tracks matters."));
      }
      if (changedKey("DropVobSubAfterConversion") && boolValue("DropVobSubAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "Embedded VobSub originals will be dropped after OCR. External .idx/.sub source files are never deleted."));
      }
      if (changedKey("DropAssAfterConversion") && boolValue("DropAssAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "ASS/SSA originals will be dropped after conversion. Keep disabled to preserve styling."));
      }
      if ((changedKey("DropTx3gAfterConversion") || changedKey("ConvertTx3gToSrt")) && boolValue("DropTx3gAfterConversion") === true && boolValue("ConvertTx3gToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop TX3G is enabled while TX3G conversion is disabled."));
      }
      if ((changedKey("DropBdpgsAfterConversion") || changedKey("ConvertBdpgsToSrt")) && boolValue("DropBdpgsAfterConversion") === true && boolValue("ConvertBdpgsToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop BDPGS is enabled while BDPGS OCR is disabled."));
      }
      if ((changedKey("DropVobSubAfterConversion") || changedKey("ConvertVobSubToSrt")) && boolValue("DropVobSubAfterConversion") === true && boolValue("ConvertVobSubToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop VobSub is enabled while VobSub OCR is disabled."));
      }
      if (changedKey("SubKeepLanguages") && !listValue("SubKeepLanguages").length) {
        issues.push(settingsReadinessIssue("medium", "SubKeepLanguages is empty. Preferred-language subtitle routing may become unpredictable."));
      }
      if (changedKey("ConvertTx3gToSrt") && boolValue("ConvertTx3gToSrt") === false) {
        issues.push(settingsReadinessIssue("medium", "ConvertTx3gToSrt is disabled. Preferred-language TX3G/mov_text subtitles will not produce SRT copies."));
      }
      if (changedKey("ConvertBdpgsToSrt") && boolValue("ConvertBdpgsToSrt") === false) {
        issues.push(settingsReadinessIssue("medium", "ConvertBdpgsToSrt is disabled. Preferred-language PGS subtitles will not produce OCR SRT copies."));
      }
      if (changedKey("ConvertVobSubToSrt") && boolValue("ConvertVobSubToSrt") === false) {
        issues.push(settingsReadinessIssue("medium", "ConvertVobSubToSrt is disabled. Preferred-language VobSub subtitles will not produce OCR SRT copies."));
      }
      if (changedKey("PreferredDefaultAudioLanguages") && !listValue("PreferredDefaultAudioLanguages").length) {
        issues.push(settingsReadinessIssue("medium", "PreferredDefaultAudioLanguages is empty. Default audio selection will depend on source metadata."));
      }
      if ((changedKey("CompatibleAudioCodecs") || changedKey("AudioPassthroughProfile")) && !listValue("CompatibleAudioCodecs").length && textValue("AudioPassthroughProfile") === "custom_codec_list") {
        issues.push(settingsReadinessIssue("high", "AudioPassthroughProfile is custom_codec_list but CompatibleAudioCodecs is empty."));
      }
      if (changedKey("AudioPassthroughProfile") && textValue("AudioPassthroughProfile") === "custom_codec_list") {
        issues.push(settingsReadinessIssue("medium", "AudioPassthroughProfile uses a manual codec list. Preview should confirm copy-vs-transcode impact."));
      }
      if (changedKey("AudioPassthroughProfile") && textValue("AudioPassthroughProfile") === "lossless_passthrough") {
        issues.push(settingsReadinessIssue("medium", "AudioPassthroughProfile preserves lossless codecs. Some Plex clients may transcode those tracks."));
      }
      if (changedKey("AudioDownmixMode") && textValue("AudioDownmixMode") === "stereo") {
        issues.push(settingsReadinessIssue("medium", "AudioDownmixMode forces stereo. This improves compatibility but discards surround channels."));
      }
      if (changedKey("AudioMaxChannels") && Number(textValue("AudioMaxChannels") || 0) > 0 && Number(textValue("AudioMaxChannels") || 0) < 6) {
        issues.push(settingsReadinessIssue("medium", "AudioMaxChannels is below 6. Normal 5.1 tracks may be downmixed during normalization."));
      }
      if (changedKey("OutputContainer") && textValue("OutputContainer").toLowerCase() === "mp4") {
        issues.push(settingsReadinessIssue("medium", "OutputContainer is MP4. Verify subtitle and audio policies avoid muxing unsupported streams into MP4."));
      }
      if (changedKey("NetworkRole") && textValue("NetworkRole") && textValue("NetworkRole").toLowerCase() !== "standalone") {
        issues.push(settingsReadinessIssue("medium", "NetworkRole changes should be saved only when no local pipeline/coordinator/worker work is active."));
      }
      if (changedKey("DeferredPublish") && boolValue("DeferredPublish") === true) {
        issues.push(settingsReadinessIssue("review", "DeferredPublish is enabled. Pending Publish must be monitored and drained after output validation."));
      }
      if (changedKey("CleanupRemoteStaging") && boolValue("CleanupRemoteStaging") === true) {
        issues.push(settingsReadinessIssue("medium", "CleanupRemoteStaging is enabled. Remote staging cleanup should be reviewed against slow or unreliable publish shares."));
      }
      if (changedKey("TransientFailureRetryLimit") && Number(textValue("TransientFailureRetryLimit") || 0) > 8) {
        issues.push(settingsReadinessIssue("medium", "TransientFailureRetryLimit is high. Persistent publish or copy failures may wait too long for operator review."));
      }
      if (changedKey("RobocopyTimeoutSeconds")) {
        const timeoutSeconds = Number(textValue("RobocopyTimeoutSeconds") || 0);
        if (timeoutSeconds > 0 && timeoutSeconds < 300) {
          issues.push(settingsReadinessIssue("medium", "RobocopyTimeoutSeconds is below five minutes. Large media copies on slow disks or SMB shares may fail prematurely."));
        }
      }
      return issues;
    }

    function settingsPatchSaveReadinessStatus(entries) {
      if (!entries.length) return "No changes";
      const changedEntries = entries.filter((entry) => entry.changed);
      if (!changedEntries.length) return "No changes";
      const issues = settingsPatchSaveReadinessIssues(entries);
      if (issues.some((issue) => issue.severity === "critical")) return "Blocked";
      if (issues.some((issue) => issue.severity === "high")) return "High review";
      if (issues.some((issue) => issue.severity === "medium" || issue.severity === "review")) return "Review";
      return "Ready to preview";
    }

    function settingsSaveReviewPostureStatus(posture) {
      const value = String(posture || "").toLowerCase();
      if (value.includes("blocked") || value.includes("critical") || value.includes("high")) return "blocked";
      if (value.includes("review") || value.includes("staged") || value.includes("preview") || value.includes("medium") || value.includes("no history")) return "warning";
      return "match";
    }

    function settingsSaveReviewLatestCommand() {
      const history = getCommandHistory();
      if (!Array.isArray(history)) return null;
      return history.find(isSettingsCommand) || null;
    }

    function settingsSaveReviewRows(entries) {
      const rows = [];
      const changedEntries = entries.filter((entry) => entry.changed);
      const unknownEntries = entries.filter((entry) => !entry.field);
      const issues = settingsPatchSaveReadinessIssues(entries);
      const criticalIssues = issues.filter((issue) => issue.severity === "critical");
      const highIssues = issues.filter((issue) => issue.severity === "high");
      const reviewIssues = issues.filter((issue) => !["critical", "high"].includes(issue.severity));
      const groups = Array.from(new Set(changedEntries.map((entry) => entry.group?.name || "Unknown / custom")));
      const readinessStatus = settingsPatchSaveReadinessStatus(entries);

      rows.push({
        key: "patch-state",
        checkpoint: "Current changes",
        posture: changedEntries.length ? "ready for review" : entries.length ? "unchanged" : "idle",
        evidence: `${entries.length} candidate key(s); ${changedEntries.length} effective change(s); ${unknownEntries.length} unknown key(s).`,
        action: changedEntries.length
          ? "Use Save Settings to review these values before the backend writes the PSD1."
          : entries.length
            ? "No effective save is needed unless the JSON is being edited for a future change."
            : "Prepare Changes JSON with a builder or manual edit before saving.",
        detail: [
          `Readiness status: ${readinessStatus}`,
          groups.length ? `Impacted groups: ${groups.join(", ")}` : "Impacted groups: none",
          "Backend Save remains authoritative for schema validation, PSD1 serialization, backups, and reload.",
        ],
      });

      rows.push({
        key: "schema-coverage",
        checkpoint: "Schema coverage",
        posture: unknownEntries.length ? "blocked review" : "known keys",
        evidence: unknownEntries.length
          ? unknownEntries.slice(0, 8).map((entry) => entry.key).join(", ") + (unknownEntries.length > 8 ? `, +${unknownEntries.length - 8} more` : "")
          : "Every candidate key is present in the backend field definitions loaded by the WebView.",
        action: unknownEntries.length
          ? "Treat unknown keys as schema drift. Save Settings will send them through backend validation before any write."
          : "Use structured builders for routine edits; backend Save Settings still validates known keys.",
        detail: unknownEntries.length
          ? unknownEntries.map((entry) => `${entry.key}: staged=${formatConfigValue(entry.staged)}`)
          : ["No schema-drift keys were detected locally."],
      });

      rows.push({
        key: "safety-blockers",
        checkpoint: "Safety blockers",
        posture: criticalIssues.length ? "critical blocked" : highIssues.length ? "high review" : "clear",
        evidence: criticalIssues.concat(highIssues).slice(0, 4).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") || "No critical/high local safety blocker detected.",
        action: criticalIssues.length
          ? "Do not save until critical source-safety or policy conflicts are deliberately resolved."
          : highIssues.length
            ? "Review each high-risk item before Save Settings."
            : "Continue to medium review and Save Settings.",
        detail: criticalIssues.concat(highIssues).length
          ? criticalIssues.concat(highIssues).map((issue) => `[${issue.severity}] ${issue.message}`)
          : ["Critical/high checks were clear in local review."],
      });

      rows.push({
        key: "medium-review",
        checkpoint: "Policy review",
        posture: reviewIssues.length ? "review" : "clear",
        evidence: reviewIssues.slice(0, 5).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") || "No medium/review local issue detected.",
        action: reviewIssues.length
          ? "Confirm these are intentional before unattended processing; backend save validation may add stricter review items."
          : "No local policy-review item detected; Save Settings still runs backend validation before writing.",
        detail: reviewIssues.length
          ? reviewIssues.map((issue) => `[${issue.severity}] ${issue.message}`)
          : ["No medium/review local checks were triggered."],
      });

      const latestCommand = settingsSaveReviewLatestCommand();
      if (!latestCommand) {
        rows.push({
          key: "backend-command",
          checkpoint: "Backend evidence",
          posture: "no history",
          evidence: "No recent settings validate/reload/save command is available.",
          action: "Use Save Settings to review changes and send them through backend validation.",
          detail: [
            "No backend command evidence is visible in recent command history.",
            "This panel never writes the PSD1; Save Settings remains the backend-owned persistence command.",
          ],
        });
      } else {
        const command = String(latestCommand.command || latestCommand.raw?.command || "").toLowerCase();
        const ok = latestCommand.ok === true || latestCommand.result === "ok" || latestCommand.raw?.ok === true;
        const isSave = command === "settings.save_patch";
        const isPreview = command === "settings.preview_patch";
        rows.push({
          key: "backend-command",
          checkpoint: "Backend evidence",
          posture: ok && isSave ? "saved evidence" : ok && isPreview ? "preview only" : ok ? "ok" : "review",
          evidence: settingsCommandHistoryLine(latestCommand) || command || "settings command",
          action: ok && isSave
            ? "Refresh/reload and confirm Saved Settings Trust before relying on this config for Launch."
            : isPreview
              ? "Preview does not persist settings. Save Settings must succeed before Launch uses the candidate config."
              : "Resolve backend command review/error before saving or launching with these changes.",
          detail: [
            `Command: ${command || "unknown"}`,
            `Result: ${latestCommand.result || (ok ? "ok" : latestCommand.severity || "unknown")}`,
            latestCommand.message ? `Message: ${latestCommand.message}` : "Message: none",
            "Use Settings Commands Evidence and Home/Diagnostics command drilldown for full backend result data.",
          ],
        });
      }

      rows.push({
        key: "mutation-boundary",
        checkpoint: "Mutation boundary",
        posture: "backend-owned",
        evidence: "Local review is display-only; Save Settings remains the backend-owned command.",
        action: "Do not treat this table as persistence proof. Confirm backend result and saved trust summary after saving.",
        detail: [
          "This review table does not save settings, launch work, mutate queue state, rewrite PSD1 files, or touch media.",
          "Backend save owns validation, redacted diffs, backups, PSD1 serialization, reload, and command journaling.",
        ],
      });

      return rows;
    }

    function settingsSaveReviewStatus(rows = []) {
      if (!rows.length) return "No review";
      if (rows.some((row) => settingsSaveReviewPostureStatus(row.posture) === "blocked")) return "Blocked review";
      if (rows.some((row) => settingsSaveReviewPostureStatus(row.posture) === "warning")) return "Review";
      return "Ready";
    }

    function settingsSaveReviewDetailLines(row) {
      if (!row) {
        return [
          "No settings save review row selected.",
          "Select a row to inspect why current changes are blocked, need review, dry-run only, or safe to continue.",
          "Mutation guardrail: this detail view is read-only and cannot save settings, launch work, or touch media files.",
        ];
      }
      const lines = [
        `Checkpoint: ${row.checkpoint}`,
        `Posture: ${row.posture}`,
        `Evidence: ${row.evidence}`,
        `Safe next step: ${row.action}`,
      ];
      if (Array.isArray(row.detail) && row.detail.length) {
        lines.push("", "Detail:");
        row.detail.forEach((line) => lines.push(`- ${line}`));
      }
      lines.push("", "Mutation guardrail: Settings Save remains backend-owned; this row only explains local review posture.");
      return lines;
    }

    function selectedSettingsSaveReviewRow(rows) {
      const selectedKey = getSelectedSettingsSaveReviewKey();
      if (!selectedKey) return null;
      return rows.find((row) => row.key === selectedKey) || null;
    }

    function renderSettingsSaveReviewFromEntries(entries) {
      const rows = settingsSaveReviewRows(entries);
      const tbody = byId("settings-save-review-rows");
      if (!tbody) return;
      let selectedKey = getSelectedSettingsSaveReviewKey();
      if (selectedKey && !rows.some((row) => row.key === selectedKey)) {
        setSelectedSettingsSaveReviewKey("");
        selectedKey = "";
      }
      if (!rows.length) {
        clearRows(tbody, 4, "No settings save review rows loaded.");
        setText("settings-save-review-legend", "Settings save review rows: no selectable rows.");
        setText("settings-save-review-detail", settingsSaveReviewDetailLines(null).join("\n"));
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = settingsSaveReviewPostureStatus(item.posture);
        appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
        makeRowSelectable(row, () => {
          setSelectedSettingsSaveReviewKey(item.key);
          renderSettingsSaveReviewFromEntries(entries);
        }, {
          selected: selectedKey === item.key,
          label: `Settings save review ${item.checkpoint} ${item.posture}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("settings-save-review-legend", tbody, "Settings save review rows");
      setText("settings-save-review-detail", settingsSaveReviewDetailLines(selectedSettingsSaveReviewRow(rows)).join("\n"));
    }

    function renderSettingsPatchSaveReadinessFromEntries(entries) {
      const changedEntries = entries.filter((entry) => entry.changed);
      const status = settingsPatchSaveReadinessStatus(entries);
      const issues = settingsPatchSaveReadinessIssues(entries);
      setText("settings-save-readiness-status", status);
      const lines = [
        "Local save readiness checklist:",
        `Status: ${status}`,
        `Change keys: ${entries.length}; effective changes: ${changedEntries.length}; unknown keys: ${entries.filter((entry) => !entry.field).length}.`,
        "Required operator action: press Save Settings and review the change dialog before any non-trivial write.",
        "Backend save remains the source of truth for schema validation, risk policy, PSD1 serialization, backup creation, and config reload.",
      ];
      if (!entries.length) {
        lines.push("", "No change keys are ready.");
      } else if (!changedEntries.length) {
        lines.push("", "No effective changes were detected.");
      }
      const changedGroups = Array.from(new Set(changedEntries.map((entry) => entry.group?.name || "Unknown / custom")));
      if (changedGroups.length) lines.push("", `Impacted group(s): ${changedGroups.join(", ")}.`);
      if (issues.length) {
        lines.push("", "Review item(s):");
        issues.forEach((issue) => lines.push(`- [${issue.severity}] ${issue.message}`));
      } else if (changedEntries.length) {
        lines.push("", "No local blocker detected. Save Settings will run backend validation before writing.");
      }
      lines.push("", "Mutation guardrail: this checklist does not save settings, launch work, mutate queue state, or touch media files.");
      setText("settings-save-readiness", lines.join("\n"));
    }

    function renderSettingsPatchSaveReadinessForError(message) {
      setText("settings-save-readiness-status", "Invalid JSON");
      setText(
        "settings-save-readiness",
        `Local save readiness unavailable because Changes JSON is invalid.\n${message}\nSave Settings cannot run until this is valid JSON.`
      );
      clearRows(byId("settings-save-review-rows"), 4, "Settings save review unavailable because Changes JSON is invalid.");
      setText("settings-save-review-legend", "Settings save review rows: no selectable rows.");
      setText(
        "settings-save-review-detail",
        [
          "Settings save review unavailable because Changes JSON is invalid.",
          message,
          "Save Settings cannot run until this is valid JSON.",
          "Mutation guardrail: this detail view is read-only and cannot save settings, launch work, or touch media files.",
        ].join("\n")
      );
    }

    return {
      finalLibraryPromotionRulesFromValue,
      finalLibraryPromotionCurrentRules,
      finalLibraryPromotionConfigBool,
      finalLibraryPromotionRuleRows,
      setFinalLibraryPromotionStatus,
      finalLibraryPromotionBrowseDetailLines,
      renderFinalLibraryPromotionRules,
      addFinalLibraryPromotionRule,
      syncFinalLibraryPromotionSettingsBuilderFromConfig,
      markFinalLibraryPromotionSettingsBuilderDirty,
      collectFinalLibraryPromotionSettingsPatch,
      renderFinalLibraryPromotionSettingsGuidance,
      finalLibraryPromotionSettingsResultLines,
      renderSettingsPatchSummary,
      renderSettingsEffectiveIntentSummary,
      renderSettingsBuilderGuidance,
      settingsProfileSummaryLines,
      setSettingsBuilderControl,
      syncSettingsBuilderFromConfig,
      markSettingsBuilderDirty,
      settingsBuilderInputValue,
      readSettingsBuilderNumber,
      readSettingsBuilderFloat,
      settingsRawConfigValue,
      parseSettingsPatchJson,
      markSettingsPatchTouched,
      settingsPatchIsTouched,
      settingsPatchEffectiveChangedEntries,
      settingsPatchHasUnsavedChanges,
      writeSettingsPatchJson,
      collectSettingsBuilderPatch,
      applySettingsBuilderToPatch,
      renderSettings,
      initSettingsViewEvents,
      settingsPatchLocalValidationHintsForKey,
      settingsPatchLibraryOverrideValidationHints,
      settingsPatchLocalValidationHints,
      settingsPatchLocalValidationHintLines,
      settingsReadinessIssue,
      settingsPatchSaveReadinessIssues,
      settingsPatchSaveReadinessStatus,
      settingsSaveReviewPostureStatus,
      settingsSaveReviewLatestCommand,
      settingsSaveReviewRows,
      settingsSaveReviewStatus,
      settingsSaveReviewDetailLines,
      selectedSettingsSaveReviewRow,
      renderSettingsSaveReviewFromEntries,
      renderSettingsPatchSaveReadinessFromEntries,
      renderSettingsPatchSaveReadinessForError,
    };
  }

  window.__settingsPatchReviewModule = {
    createSettingsPatchReviewModule,
  };
})();
