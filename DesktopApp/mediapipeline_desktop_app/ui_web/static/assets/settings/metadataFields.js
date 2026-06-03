(function () {
  function createSettingsMetadataFieldsModule(deps) {
    deps = deps || {};
    const getLastSettingsFieldMap = deps.getLastSettingsFieldMap || function () { return {}; };
    const settingsChoiceLabels = deps.settingsChoiceLabels || {};
    const settingsAdvancedFallbackKeys = deps.settingsAdvancedFallbackKeys instanceof Set
      ? deps.settingsAdvancedFallbackKeys
      : new Set(deps.settingsAdvancedFallbackKeys || []);

    function settingsFieldDefinition(key) {
      const fieldMap = getLastSettingsFieldMap() || {};
      return fieldMap ? fieldMap[key] || null : null;
    }

    function settingsFieldDefaultValue(key, fallback) {
      const field = settingsFieldDefinition(key);
      if (field && Object.prototype.hasOwnProperty.call(field, "default_value") && field.default_value !== null && field.default_value !== undefined) {
        return field.default_value;
      }
      if (field && Object.prototype.hasOwnProperty.call(field, "default") && field.default !== null && field.default !== undefined) {
        return field.default;
      }
      return fallback;
    }

    function formatSettingsChoiceLabel(value) {
      const text = String(value || "");
      if (settingsChoiceLabels[text]) return settingsChoiceLabels[text];
      return text.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function settingsFieldAllowedValues(field) {
      if (Array.isArray(field?.allowed_values) && field.allowed_values.length) return field.allowed_values;
      if (Array.isArray(field?.choices) && field.choices.length) return field.choices;
      return [];
    }

    function settingsHasBackendFieldDefinitions() {
      const fieldMap = getLastSettingsFieldMap() || {};
      return Boolean(fieldMap && Object.keys(fieldMap).length);
    }

    function settingsFieldLabel(key, fallback = "") {
      const field = settingsFieldDefinition(key);
      return field?.label || fallback || key;
    }

    function settingsPersistedKeyDisplay(key, field = null) {
      const persisted = String(key || "").trim();
      if (!persisted) return "";
      const resolvedField = field || settingsFieldDefinition(persisted);
      const label = resolvedField?.label || settingsFieldLabel(persisted, persisted);
      return label && label !== persisted ? `${persisted} (${label})` : persisted;
    }

    function settingsPersistedKeyDisplayList(keys) {
      return (Array.isArray(keys) ? keys : [])
        .map((key) => settingsPersistedKeyDisplay(key))
        .filter(Boolean)
        .join(", ");
    }

    function settingsFieldHelpText(field) {
      return String(field?.help_text || field?.help || "").trim();
    }

    function settingsMetadataTags(value) {
      if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
      const text = String(value || "").trim();
      return text ? [text] : [];
    }

    function settingsFieldIsAdvanced(key, field) {
      const advancedVisibility = String(field?.advanced_visibility || "").trim().toLowerCase();
      const section = String(field?.section || "").trim().toLowerCase();
      const tags = [
        ...settingsMetadataTags(field?.rule_taxonomy),
        ...settingsMetadataTags(field?.strictness),
      ].map((value) => String(value || "").trim().toLowerCase());
      return advancedVisibility === "advanced"
        || section === "advanced"
        || tags.includes("advanced")
        || settingsAdvancedFallbackKeys.has(String(key || field?.key || ""));
    }

    function settingsMetadataValue(value) {
      if (value === undefined || value === null) return "";
      if (Array.isArray(value)) return value.join(", ");
      if (typeof value === "object") {
        try {
          return JSON.stringify(value);
        } catch (_error) {
          return String(value);
        }
      }
      return String(value);
    }

    return {
      settingsFieldDefaultValue,
      settingsFieldDefinition,
      formatSettingsChoiceLabel,
      settingsFieldAllowedValues,
      settingsHasBackendFieldDefinitions,
      settingsFieldLabel,
      settingsPersistedKeyDisplay,
      settingsPersistedKeyDisplayList,
      settingsFieldHelpText,
      settingsMetadataTags,
      settingsFieldIsAdvanced,
      settingsMetadataValue,
    };
  }

  window.__settingsMetadataFieldsModule = {
    createSettingsMetadataFieldsModule,
  };
})();
