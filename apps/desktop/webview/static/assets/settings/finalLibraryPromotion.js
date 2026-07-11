(function () {
  function createSettingsFinalLibraryPromotionModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const clearRows = deps.clearRows || function () {};
    const documentRef = deps.documentRef || document;
    const browseFinalLibraryPromotionRulePath = deps.browseFinalLibraryPromotionRulePath || function () {};
    const finalLibraryPromotionSettingsBuilderState = deps.finalLibraryPromotionSettingsBuilderState || { initialized: false, dirty: false };
    const setText = deps.setText || function () {};
    const settingsBoolValue = deps.settingsBoolValue || function (value) { return value === true || String(value).toLowerCase() === "true"; };
    const settingsBuilderConfigValue = deps.settingsBuilderConfigValue || function (_key, fallback) { return fallback; };
    const settingsPersistedKeyDisplayList = deps.settingsPersistedKeyDisplayList || function (keys) { return (keys || []).join(", "); };

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
      return Array.from(documentRef.querySelectorAll("#settings-final-library-rules-rows tr[data-final-library-rule-row]"));
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
      const row = documentRef.createElement("tr");
      row.dataset.finalLibraryRuleRow = "true";
      row.dataset.ruleId = String(rule.id || "");

      const enabledCell = documentRef.createElement("td");
      enabledCell.className = "settings-rule-enabled-cell";
      const enabled = documentRef.createElement("input");
      enabled.type = "checkbox";
      enabled.checked = rule.enabled !== false;
      enabled.dataset.finalLibraryRuleEnabled = "true";
      enabled.setAttribute("aria-label", `Enable final library promotion rule ${index + 1}`);
      enabled.addEventListener("change", markFinalLibraryPromotionSettingsBuilderDirty);
      enabledCell.appendChild(enabled);

      const labelCell = documentRef.createElement("td");
      const label = documentRef.createElement("input");
      label.type = "text";
      label.className = "settings-rule-label-input";
      label.value = rule.label || `Rule ${index + 1}`;
      label.dataset.finalLibraryRuleLabel = "true";
      label.autocomplete = "off";
      label.spellcheck = false;
      label.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      labelCell.appendChild(label);

      const sourceCell = documentRef.createElement("td");
      const sourceWrap = documentRef.createElement("span");
      sourceWrap.className = "settings-path-control settings-path-control-with-badge";
      sourceWrap.dataset.pathPickerScope = "true";
      const source = documentRef.createElement("input");
      source.type = "text";
      source.className = "settings-rule-path-input";
      source.value = rule.source_root || "";
      source.dataset.finalLibraryRuleSource = "true";
      source.autocomplete = "off";
      source.spellcheck = false;
      source.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      const sourceBadge = documentRef.createElement("button");
      sourceBadge.type = "button";
      sourceBadge.className = "path-picker-badge";
      sourceBadge.textContent = "Browse";
      sourceBadge.dataset.pathPickerTarget = "settings.final_library_promotion.source_root";
      sourceBadge.dataset.pathPickerInput = '[data-final-library-rule-source="true"]';
      sourceBadge.dataset.pathPickerMode = "folder";
      sourceBadge.dataset.pathPickerStatus = "settings-final-library-status";
      sourceBadge.title = "Open a backend-owned Windows folder picker for this promotion source root.";
      const sourceBrowse = documentRef.createElement("button");
      sourceBrowse.type = "button";
      sourceBrowse.className = "tertiary-button settings-path-browse-button";
      sourceBrowse.textContent = "Browse";
      sourceBrowse.addEventListener("click", () => browseFinalLibraryPromotionRulePath(source, "FinalLibraryPromotionRuleSourceRoot", "promotion source root"));
      sourceWrap.append(source, sourceBadge, sourceBrowse);
      sourceCell.appendChild(sourceWrap);

      const destinationCell = documentRef.createElement("td");
      const destinationWrap = documentRef.createElement("span");
      destinationWrap.className = "settings-path-control settings-path-control-with-badge";
      destinationWrap.dataset.pathPickerScope = "true";
      const destination = documentRef.createElement("input");
      destination.type = "text";
      destination.className = "settings-rule-path-input";
      destination.value = rule.destination_root || "";
      destination.dataset.finalLibraryRuleDestination = "true";
      destination.autocomplete = "off";
      destination.spellcheck = false;
      destination.addEventListener("input", markFinalLibraryPromotionSettingsBuilderDirty);
      const destinationBadge = documentRef.createElement("button");
      destinationBadge.type = "button";
      destinationBadge.className = "path-picker-badge";
      destinationBadge.textContent = "Browse";
      destinationBadge.dataset.pathPickerTarget = "settings.final_library_promotion.destination_root";
      destinationBadge.dataset.pathPickerInput = '[data-final-library-rule-destination="true"]';
      destinationBadge.dataset.pathPickerMode = "folder";
      destinationBadge.dataset.pathPickerStatus = "settings-final-library-status";
      destinationBadge.title = "Open a backend-owned Windows folder picker for this promotion destination root.";
      const destinationBrowse = documentRef.createElement("button");
      destinationBrowse.type = "button";
      destinationBrowse.className = "tertiary-button settings-path-browse-button";
      destinationBrowse.textContent = "Browse";
      destinationBrowse.addEventListener("click", () => browseFinalLibraryPromotionRulePath(destination, "FinalLibraryPromotionRuleDestinationRoot", "promotion destination root"));
      destinationWrap.append(destination, destinationBadge, destinationBrowse);
      destinationCell.appendChild(destinationWrap);

      const actionCell = documentRef.createElement("td");
      actionCell.className = "settings-rule-action-cell";
      const remove = documentRef.createElement("button");
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
    };
  }

  window.__settingsFinalLibraryPromotionModule = {
    createSettingsFinalLibraryPromotionModule,
  };
})();
