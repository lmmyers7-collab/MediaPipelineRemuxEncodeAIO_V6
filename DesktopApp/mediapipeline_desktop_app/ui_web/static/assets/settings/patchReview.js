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
    const settingsFieldDefinition = dep("settingsFieldDefinition", function () { return null; });
    const settingsPatchImpactEntries = dep("settingsPatchImpactEntries", function () { return []; });
    const settingsValuesEqual = dep("settingsValuesEqual", function (left, right) { return JSON.stringify(left) === JSON.stringify(right); });
    const addSettingsEventHandlers = dep("addSettingsEventHandlers", {});
    const audioSettingsBuilderState = dep("audioSettingsBuilderState", {});
    const audioSettingsBuilderFields = dep("audioSettingsBuilderFields", []);
    const fileSafetySettingsBuilderState = dep("fileSafetySettingsBuilderState", {});
    const fileSafetySettingsBuilderFields = dep("fileSafetySettingsBuilderFields", []);
    const finalLibraryPromotionSettingsBuilderFields = dep("finalLibraryPromotionSettingsBuilderFields", []);
    const getSettingsBuilderState = dep("getSettingsBuilderState", function () { return {}; });
    const getLastSettingsValues = dep("getLastSettingsValues", function () { return {}; });
    const getSettingsPatchTouched = dep("getSettingsPatchTouched", function () { return false; });
    const networkSettingsBuilderState = dep("networkSettingsBuilderState", {});
    const networkSettingsBuilderFields = dep("networkSettingsBuilderFields", []);
    const pendingPublishSettingsBuilderState = dep("pendingPublishSettingsBuilderState", {});
    const pendingPublishSettingsBuilderFields = dep("pendingPublishSettingsBuilderFields", []);
    const queueSettingsBuilderState = dep("queueSettingsBuilderState", {});
    const queueSettingsBuilderFields = dep("queueSettingsBuilderFields", []);
    const refreshAudioSettingsBuilderChoices = dep("refreshAudioSettingsBuilderChoices", function () {});
    const refreshSettingsBuilderChoices = dep("refreshSettingsBuilderChoices", function () {});
    const refreshSettingsSelectChoices = dep("refreshSettingsSelectChoices", function () {});
    const renderAllLaunchPreflights = dep("renderAllLaunchPreflights", function () {});
    const renderSettingsActiveMediaPolicyHandoff = dep("renderSettingsActiveMediaPolicyHandoff", function () {});
    const renderSettingsBackendMediaPolicyReadiness = dep("renderSettingsBackendMediaPolicyReadiness", function () {});
    const renderSettingsBdpgsOcrPathEvidence = dep("renderSettingsBdpgsOcrPathEvidence", function () {});
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
      sourceWrap.className = "settings-path-control";
      const source = document.createElement("input");
      source.type = "text";
      source.className = "settings-rule-path-input";
      source.value = rule.source_root || "";
      source.dataset.finalLibraryRuleSource = "true";
      source.autocomplete = "off";
      source.spellcheck = false;
      source.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      const sourceBrowse = document.createElement("button");
      sourceBrowse.type = "button";
      sourceBrowse.className = "tertiary-button settings-path-browse-button";
      sourceBrowse.textContent = "Browse";
      sourceBrowse.addEventListener("click", () => browseFinalLibraryPromotionRulePath(source, "FinalLibraryPromotionRuleSourceRoot", "promotion source root"));
      sourceWrap.append(source, sourceBrowse);
      sourceCell.appendChild(sourceWrap);

      const destinationCell = document.createElement("td");
      const destinationWrap = document.createElement("span");
      destinationWrap.className = "settings-path-control";
      const destination = document.createElement("input");
      destination.type = "text";
      destination.className = "settings-rule-path-input";
      destination.value = rule.destination_root || "";
      destination.dataset.finalLibraryRuleDestination = "true";
      destination.autocomplete = "off";
      destination.spellcheck = false;
      destination.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      const destinationBrowse = document.createElement("button");
      destinationBrowse.type = "button";
      destinationBrowse.className = "tertiary-button settings-path-browse-button";
      destinationBrowse.textContent = "Browse";
      destinationBrowse.addEventListener("click", () => browseFinalLibraryPromotionRulePath(destination, "FinalLibraryPromotionRuleDestinationRoot", "promotion destination root"));
      destinationWrap.append(destination, destinationBrowse);
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
        `Changed keys: ${changedKeys.join(", ") || "none"}`,
        `Writes config: ${data.writes_config === true ? "yes" : data.writes_config === false ? "no" : "n/a"}`,
      ];
      const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
      const errors = Array.isArray(result?.errors) ? result.errors : [];
      if (warnings.length) lines.push("", "Warnings:", ...warnings.map((item) => `- ${item}`));
      if (errors.length) lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
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
        setText("settings-patch-summary-status", "Patch summary unavailable because Changes JSON is invalid.");
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
        clearRows(tbody, 5, "No patch keys staged.");
        setText("settings-patch-summary-status", "No staged settings changes.");
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
          field?.label || key,
          current === undefined ? "(not set)" : formatConfigValue(current),
          formatConfigValue(staged),
          status,
        ]);
        tbody.appendChild(row);
      });
      if (!visibleCount) {
        clearRows(tbody, 5, "No changed or unknown patch keys to show.");
      }
      setText(
        "settings-patch-summary-status",
        `${keys.length} staged key${keys.length === 1 ? "" : "s"}: ${changedCount} changed, ${unchangedCount} unchanged, ${unknownCount} unknown, ${visibleCount} shown. Backend preview remains the source of truth.`
      );
    }

    function renderSettingsBuilderGuidance() {
      const lines = [];
      settingsBuilderFields.forEach(([key, id]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
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

    function syncSettingsBuilderFromConfig() {
      refreshSettingsBuilderChoices();
      setSettingsBuilderControl("settings-builder-routing-profile", settingsBuilderConfigValue("RoutingProfile", "plex_direct_stream"));
      setSettingsBuilderControl("settings-builder-route-threshold-mode", settingsBuilderConfigValue("RouteThresholdMode", "compatibility_advisory"));
      setSettingsBuilderControl("settings-builder-size-guard", settingsBuilderConfigValue("SizeGuardMode", "advisory"));
      setSettingsBuilderControl("settings-builder-encode-tuning", settingsBuilderConfigValue("EncodeTuningPreset", "balanced_nvenc"));
      setSettingsBuilderControl("settings-builder-encode-ladder", settingsBuilderConfigValue("EncodeLadder", "auto"));
      setSettingsBuilderControl("settings-builder-video-codec", settingsBuilderConfigValue("VideoCodec", "hevc_nvenc"));
      setSettingsBuilderControl("settings-builder-output-container", settingsBuilderConfigValue("OutputContainer", "mkv"));
      setSettingsBuilderControl("settings-builder-max-growth", settingsBuilderConfigValue("MaxEncodeGrowthPercent", 5));
      setSettingsBuilderControl("settings-builder-compat-growth", settingsBuilderConfigValue("CompatibilityEncodeGrowthPercent", 15));
      setSettingsBuilderControl("settings-builder-movie-threshold", settingsBuilderConfigValue("EncodeThresholdGB", 8));
      setSettingsBuilderControl("settings-builder-tv-threshold", settingsBuilderConfigValue("TVEncodeThresholdGB", 3));
      setSettingsBuilderControl("settings-builder-movie-route-bitrate", settingsBuilderConfigValue("MovieRouteMaxVideoBitrateMbps", 35));
      setSettingsBuilderControl("settings-builder-tv-route-bitrate", settingsBuilderConfigValue("TVRouteMaxVideoBitrateMbps", 18));
      setSettingsBuilderState(true, false);
      setText("settings-builder-status", "Loaded current values");
      renderSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markSettingsBuilderDirty() {
      setSettingsBuilderState(true, true);
      setText("settings-builder-status", "Editing builder values");
      renderSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function settingsBuilderInputValue(id) {
      return String(byId(id)?.value ?? "").trim();
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
      setText("settings-patch-status", "Patch built");
      setText("settings-patch-detail", detail || "Builder updated Changes JSON. Preview or Save still uses backend validation.");
      renderSettingsPatchSummary();
      renderAllLaunchPreflights();
    }

    function collectSettingsBuilderPatch() {
      const patch = {
        RoutingProfile: settingsBuilderInputValue("settings-builder-routing-profile"),
        RouteThresholdMode: settingsBuilderInputValue("settings-builder-route-threshold-mode"),
        SizeGuardMode: settingsBuilderInputValue("settings-builder-size-guard"),
        EncodeTuningPreset: settingsBuilderInputValue("settings-builder-encode-tuning"),
        EncodeLadder: settingsBuilderInputValue("settings-builder-encode-ladder"),
        VideoCodec: settingsBuilderInputValue("settings-builder-video-codec"),
        OutputContainer: settingsBuilderInputValue("settings-builder-output-container"),
        MaxEncodeGrowthPercent: readSettingsBuilderNumber("settings-builder-max-growth", "Normal growth percent"),
        CompatibilityEncodeGrowthPercent: readSettingsBuilderNumber("settings-builder-compat-growth", "Compatibility growth percent"),
        EncodeThresholdGB: readSettingsBuilderNumber("settings-builder-movie-threshold", "Movie threshold GB"),
        TVEncodeThresholdGB: readSettingsBuilderNumber("settings-builder-tv-threshold", "TV threshold GB"),
        MovieRouteMaxVideoBitrateMbps: readSettingsBuilderNumber("settings-builder-movie-route-bitrate", "Movie route max video bitrate Mbps"),
        TVRouteMaxVideoBitrateMbps: readSettingsBuilderNumber("settings-builder-tv-route-bitrate", "TV route max video bitrate Mbps"),
      };
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
        return;
      }
      writeSettingsPatchJson(patch, "Structured builder merged routing, size, and encoder keys into Changes JSON. Preview or Save still uses backend validation.");
      setSettingsBuilderState(true, true);
      setText("settings-builder-status", `${Object.keys(patch).length} patch keys ready`);
      renderSettingsBuilderGuidance();
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
      const auditRootInput = byId("audit-start-library-root");
      if (auditRootInput && !auditRootInput.value && (settings?.paths || {}).outsource) {
        auditRootInput.value = settings.paths.outsource;
      }
      setText("settings-profiles", settingsProfileSummaryLines(settings));
      setText("settings-validation", warnings.join("\n") || "No validation warnings.");
      renderSettingsOverview(config);
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
      if (!finalLibraryPromotionSettingsBuilderState.initialized || !finalLibraryPromotionSettingsBuilderState.dirty) {
        addSettingsEventHandlers.syncFinalLibraryPromotionSettingsBuilderFromConfig();
      } else {
        renderFinalLibraryPromotionSettingsGuidance();
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
      renderSettingsPatchSummary();
      renderSettingsSafetyLocks();
      renderSettingsRawTriage();
      renderSettingsRawActionPlan();
      renderSettingsRows();
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
      bindSettingsClick("settings-preview-patch-button", addSettingsEventHandlers.previewSettingsPatch);
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
      bindSettingsClick("settings-video-apply-button", addSettingsEventHandlers.applyVideoDetailSettingsBuilderToPatch);
      bindSettingsClick("settings-video-reset-button", addSettingsEventHandlers.syncVideoDetailSettingsBuilderFromConfig);
      bindSettingsControls(videoDetailSettingsBuilderFields, addSettingsEventHandlers.markVideoDetailSettingsBuilderDirty);
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
      bindSettingsClick("settings-final-library-add-rule-button", addSettingsEventHandlers.addFinalLibraryPromotionRule);
      bindSettingsClick("settings-final-library-preview-button", addSettingsEventHandlers.previewFinalLibraryPromotionSettings);
      bindSettingsClick("settings-final-library-save-button", addSettingsEventHandlers.saveFinalLibraryPromotionSettings);
      bindSettingsClick("settings-final-library-reset-button", addSettingsEventHandlers.syncFinalLibraryPromotionSettingsBuilderFromConfig);
      bindSettingsControls(
        finalLibraryPromotionSettingsBuilderFields.filter(([, id]) => id !== "settings-final-library-rules-rows"),
        addSettingsEventHandlers.markFinalLibraryPromotionSettingsBuilderDirty
      );
      bindSettingsClick("settings-subtitle-apply-button", addSettingsEventHandlers.applySubtitleSettingsBuilderToPatch);
      bindSettingsClick("settings-subtitle-reset-button", addSettingsEventHandlers.syncSubtitleSettingsBuilderFromConfig);
      bindSettingsControls(subtitleSettingsBuilderFields, addSettingsEventHandlers.markSubtitleSettingsBuilderDirty);
      bindSettingsClick("settings-audio-apply-button", addSettingsEventHandlers.applyAudioSettingsBuilderToPatch);
      bindSettingsClick("settings-audio-reset-button", addSettingsEventHandlers.syncAudioSettingsBuilderFromConfig);
      bindSettingsControls(audioSettingsBuilderFields, addSettingsEventHandlers.markAudioSettingsBuilderDirty);
      const settingsFilter = byId("settings-filter");
      if (settingsFilter) settingsFilter.addEventListener("input", renderSettingsRows);
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
        issues.push(settingsReadinessIssue("high", `Unknown key '${entry.key}' is not in the WebView schema; backend preview must validate it before save.`));
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
      if (changedKey("DropAssAfterConversion") && boolValue("DropAssAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "ASS/SSA originals will be dropped after conversion. Keep disabled to preserve styling."));
      }
      if ((changedKey("DropTx3gAfterConversion") || changedKey("ConvertTx3gToSrt")) && boolValue("DropTx3gAfterConversion") === true && boolValue("ConvertTx3gToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop TX3G is enabled while TX3G conversion is disabled."));
      }
      if ((changedKey("DropBdpgsAfterConversion") || changedKey("ConvertBdpgsToSrt")) && boolValue("DropBdpgsAfterConversion") === true && boolValue("ConvertBdpgsToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop BDPGS is enabled while BDPGS OCR is disabled."));
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
      if (!entries.length) return "No patch";
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
        checkpoint: "Patch state",
        posture: changedEntries.length ? "staged" : entries.length ? "unchanged" : "idle",
        evidence: `${entries.length} staged key(s); ${changedEntries.length} effective change(s); ${unknownEntries.length} unknown key(s).`,
        action: changedEntries.length
          ? "Run backend Preview Patch before Save Patch; do not assume local review is complete."
          : entries.length
            ? "No effective save is needed unless the JSON is being edited for a future patch."
            : "Stage Changes JSON with a builder or manual edit before preview/save.",
        detail: [
          `Readiness status: ${readinessStatus}`,
          groups.length ? `Impacted groups: ${groups.join(", ")}` : "Impacted groups: none",
          "Backend preview/save remains authoritative for schema validation, PSD1 serialization, backups, and reload.",
        ],
      });

      rows.push({
        key: "schema-coverage",
        checkpoint: "Schema coverage",
        posture: unknownEntries.length ? "blocked review" : "known keys",
        evidence: unknownEntries.length
          ? unknownEntries.slice(0, 8).map((entry) => entry.key).join(", ") + (unknownEntries.length > 8 ? `, +${unknownEntries.length - 8} more` : "")
          : "Every staged key is present in the backend field definitions loaded by the WebView.",
        action: unknownEntries.length
          ? "Treat unknown keys as schema drift. Preview Patch must explain them before Save Patch."
          : "Use structured builders for routine edits; backend Preview Patch still validates known keys.",
        detail: unknownEntries.length
          ? unknownEntries.map((entry) => `${entry.key}: staged=${formatConfigValue(entry.staged)}`)
          : ["No staged schema-drift keys were detected locally."],
      });

      rows.push({
        key: "safety-blockers",
        checkpoint: "Safety blockers",
        posture: criticalIssues.length ? "critical blocked" : highIssues.length ? "high review" : "clear",
        evidence: criticalIssues.concat(highIssues).slice(0, 4).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") || "No critical/high local safety blocker detected.",
        action: criticalIssues.length
          ? "Do not save until critical source-safety or policy conflicts are deliberately resolved."
          : highIssues.length
            ? "Review each high-risk item and run backend Preview Patch before Save Patch."
            : "Continue to medium review and backend preview.",
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
          ? "Confirm these are intentional before unattended processing; backend preview may add stricter warnings."
          : "No local policy-review item detected; backend preview is still required before saving meaningful changes.",
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
          evidence: "No recent settings validate/reload/preview/save command is available.",
          action: "Use Preview Patch first, then Save Patch only after the backend response is clean.",
          detail: [
            "No backend command evidence is visible in recent command history.",
            "This panel never writes the PSD1; Save Patch remains the backend-owned persistence command.",
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
              ? "Preview does not persist settings. Save Patch must succeed before Launch uses the staged config."
              : "Resolve backend command warning/error before saving or launching with this patch.",
          detail: [
            `Command: ${command || "unknown"}`,
            `Result: ${latestCommand.result || (ok ? "ok" : latestCommand.severity || "unknown")}`,
            latestCommand.message ? `Message: ${latestCommand.message}` : "Message: none",
            "Use Settings Command History and Home/Diagnostics command drilldown for full backend result data.",
          ],
        });
      }

      rows.push({
        key: "mutation-boundary",
        checkpoint: "Mutation boundary",
        posture: "backend-owned",
        evidence: "Local review is display-only; Preview Patch and Save Patch remain backend-owned commands.",
        action: "Do not treat this table as persistence proof. Confirm backend result and saved trust summary after saving.",
        detail: [
          "This review table does not save settings, launch work, mutate queue state, rewrite PSD1 files, or touch media.",
          "Backend preview/save owns validation, redacted diffs, backups, PSD1 serialization, reload, and command journaling.",
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
          "Select a row to inspect why a staged patch is blocked, review-needed, preview-only, or safe to continue.",
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
      lines.push("", "Mutation guardrail: Settings Preview/Save remains backend-owned; this row only explains local review posture.");
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
        `Patch keys: ${entries.length}; effective changes: ${changedEntries.length}; unknown keys: ${entries.filter((entry) => !entry.field).length}.`,
        "Required operator action: use Preview Patch before Save Patch for any non-trivial change.",
        "Backend preview/save remains the source of truth for schema validation, risk policy, PSD1 serialization, backup creation, and config reload.",
      ];
      if (!entries.length) {
        lines.push("", "No patch keys are staged.");
      } else if (!changedEntries.length) {
        lines.push("", "No effective staged changes were detected.");
      }
      const changedGroups = Array.from(new Set(changedEntries.map((entry) => entry.group?.name || "Unknown / custom")));
      if (changedGroups.length) lines.push("", `Impacted group(s): ${changedGroups.join(", ")}.`);
      if (issues.length) {
        lines.push("", "Review item(s):");
        issues.forEach((issue) => lines.push(`- [${issue.severity}] ${issue.message}`));
      } else if (changedEntries.length) {
        lines.push("", "No local blocker detected. Run backend Preview Patch before saving.");
      }
      lines.push("", "Mutation guardrail: this checklist does not save settings, launch work, mutate queue state, or touch media files.");
      setText("settings-save-readiness", lines.join("\n"));
    }

    function renderSettingsPatchSaveReadinessForError(message) {
      setText("settings-save-readiness-status", "Invalid JSON");
      setText(
        "settings-save-readiness",
        `Local save readiness unavailable because Changes JSON is invalid.\n${message}\nBackend preview/save cannot run until this is valid JSON.`
      );
      clearRows(byId("settings-save-review-rows"), 4, "Settings save review unavailable because Changes JSON is invalid.");
      setText("settings-save-review-legend", "Settings save review rows: no selectable rows.");
      setText(
        "settings-save-review-detail",
        [
          "Settings save review unavailable because Changes JSON is invalid.",
          message,
          "Backend preview/save cannot run until this is valid JSON.",
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
