(function () {
  function createSettingsPatchOverviewModule(deps) {
    deps = deps || {};
    const appendCells = deps.appendCells || function () {};
    const byId = deps.byId || function () { return null; };
    const clearRows = deps.clearRows || function () {};
    const formatConfigValue = deps.formatConfigValue || function (value) { return String(value ?? ""); };
    const formatSettingsChoiceLabel = deps.formatSettingsChoiceLabel || function (value) { return String(value ?? ""); };
    const getLastSettings = deps.getLastSettings || function () { return {}; };
    const parseSettingsPatchJson = deps.parseSettingsPatchJson || function () { return {}; };
    const renderSettingsBackendResultForError = deps.renderSettingsBackendResultForError || function () {};
    const renderSettingsBackendResultFromEntries = deps.renderSettingsBackendResultFromEntries || function () {};
    const renderSettingsEffectivePolicyTrustForError = deps.renderSettingsEffectivePolicyTrustForError || function () {};
    const renderSettingsEffectivePolicyTrustFromEntries = deps.renderSettingsEffectivePolicyTrustFromEntries || function () {};
    const renderSettingsLaunchImpactHandoffForError = deps.renderSettingsLaunchImpactHandoffForError || function () {};
    const renderSettingsLaunchImpactHandoffFromEntries = deps.renderSettingsLaunchImpactHandoffFromEntries || function () {};
    const renderSettingsPatchImpactSummaryForError = deps.renderSettingsPatchImpactSummaryForError || function () {};
    const renderSettingsPatchImpactSummaryFromEntries = deps.renderSettingsPatchImpactSummaryFromEntries || function () {};
    const renderSettingsPatchSaveReadinessForError = deps.renderSettingsPatchSaveReadinessForError || function () {};
    const renderSettingsPatchSaveReadinessFromEntries = deps.renderSettingsPatchSaveReadinessFromEntries || function () {};
    const renderSettingsPolicyDeltaForError = deps.renderSettingsPolicyDeltaForError || function () {};
    const renderSettingsPolicyDeltaFromEntries = deps.renderSettingsPolicyDeltaFromEntries || function () {};
    const renderSettingsSaveReviewFromEntries = deps.renderSettingsSaveReviewFromEntries || function () {};
    const routeHeightToleranceBoundariesFromConfigValues = deps.routeHeightToleranceBoundariesFromConfigValues || function () { return {}; };
    const setText = deps.setText || function () {};
    const settingsBuilderFields = deps.settingsBuilderFields || [];
    const settingsBuilderInputValue = deps.settingsBuilderInputValue || function () { return ""; };
    const settingsDisplayLabels = deps.settingsDisplayLabels || {};
    const settingsFieldDefinition = deps.settingsFieldDefinition || function () { return null; };
    const settingsPatchImpactEntries = deps.settingsPatchImpactEntries || function () { return []; };
    const settingsRawConfigValue = deps.settingsRawConfigValue || function () { return undefined; };
    const settingsValuesEqual = deps.settingsValuesEqual || function (left, right) { return JSON.stringify(left) === JSON.stringify(right); };

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


    return {
      renderSettingsPatchSummary,
      renderSettingsBuilderGuidance,
      settingsDisplayLabel,
      settingsPersistedKeyDisplayList,
      renderSettingsEffectiveIntentSummary,
      renderHandbrakePreviewSummary,
      settingsProfileSummaryLines,
    };
  }

  window.__settingsPatchOverviewModule = {
    createSettingsPatchOverviewModule,
  };
}());
