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

    const settingsFinalLibraryPromotionModule = window.__settingsFinalLibraryPromotionModule || {};
    delete window.__settingsFinalLibraryPromotionModule;
    const settingsFinalLibraryPromotion = typeof settingsFinalLibraryPromotionModule.createSettingsFinalLibraryPromotionModule === "function"
      ? settingsFinalLibraryPromotionModule.createSettingsFinalLibraryPromotionModule({
        browseFinalLibraryPromotionRulePath,
        byId,
        clearRows,
        documentRef: document,
        finalLibraryPromotionSettingsBuilderState,
        setText,
        settingsBoolValue,
        settingsBuilderConfigValue,
        settingsPersistedKeyDisplayList: (...args) => settingsPersistedKeyDisplayList(...args),
      })
      : {};
    const {
      finalLibraryPromotionRulesFromValue = function () { return []; },
      finalLibraryPromotionCurrentRules = function () { return []; },
      finalLibraryPromotionConfigBool = function (_key, fallback = false) { return fallback; },
      finalLibraryPromotionRuleRows = function () { return []; },
      setFinalLibraryPromotionStatus = function () {},
      finalLibraryPromotionBrowseDetailLines = function () { return []; },
      renderFinalLibraryPromotionRules = function () {},
      addFinalLibraryPromotionRule = function () {},
      syncFinalLibraryPromotionSettingsBuilderFromConfig = function () {},
      markFinalLibraryPromotionSettingsBuilderDirty = function () {},
      collectFinalLibraryPromotionSettingsPatch = function () { return {}; },
      renderFinalLibraryPromotionSettingsGuidance = function () {},
      finalLibraryPromotionSettingsResultLines = function () { return []; },
    } = settingsFinalLibraryPromotion;

    const settingsPatchOverviewModule = window.__settingsPatchOverviewModule || {};
    delete window.__settingsPatchOverviewModule;
    const settingsPatchOverview = typeof settingsPatchOverviewModule.createSettingsPatchOverviewModule === "function"
      ? settingsPatchOverviewModule.createSettingsPatchOverviewModule({
        appendCells,
        byId,
        clearRows,
        formatConfigValue,
        formatSettingsChoiceLabel,
        getLastSettings,
        renderSettingsBackendResultForError,
        renderSettingsBackendResultFromEntries,
        renderSettingsEffectivePolicyTrustForError,
        renderSettingsEffectivePolicyTrustFromEntries,
        renderSettingsLaunchImpactHandoffForError,
        renderSettingsLaunchImpactHandoffFromEntries,
        renderSettingsPatchImpactSummaryForError,
        renderSettingsPatchImpactSummaryFromEntries,
        renderSettingsPolicyDeltaForError,
        renderSettingsPolicyDeltaFromEntries,
        routeHeightToleranceBoundariesFromConfigValues,
        setText,
        settingsBuilderFields,
        settingsBuilderInputValue,
        settingsDisplayLabels,
        settingsFieldDefinition,
        settingsPatchImpactEntries,
        settingsRawConfigValue,
        settingsValuesEqual,
        parseSettingsPatchJson,
        renderSettingsPatchSaveReadinessForError: (...args) => renderSettingsPatchSaveReadinessForError(...args),
        renderSettingsPatchSaveReadinessFromEntries: (...args) => renderSettingsPatchSaveReadinessFromEntries(...args),
        renderSettingsSaveReviewFromEntries: (...args) => renderSettingsSaveReviewFromEntries(...args),
      })
      : {};
    const {
      renderSettingsPatchSummary = function () {},
      renderSettingsBuilderGuidance = function () {},
      renderSettingsEffectiveIntentSummary = function () {},
      renderHandbrakePreviewSummary = function () {},
      settingsDisplayLabel = function (key, fallback) { return fallback || key; },
      settingsProfileSummaryLines = function () { return "No profiles found."; },
      settingsPersistedKeyDisplayList = function () { return ""; },
    } = settingsPatchOverview;

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

    function settingsBuilderOwnedPatchKeys(fields) {
      const canonicalKeys = new Set();
      (Array.isArray(fields) ? fields : []).forEach(([key]) => {
        const canonical = String(key || "").trim();
        if (!canonical) return;
        canonicalKeys.add(canonical.toLowerCase());
        const persisted = String(settingsFieldDefinition(canonical)?.persisted_key || "").trim();
        if (persisted) canonicalKeys.add(persisted.toLowerCase());
      });
      Object.entries(settingsFriendlyPersistedKeyAliases).forEach(([alias, canonical]) => {
        if (canonicalKeys.has(String(canonical || "").toLowerCase())) {
          canonicalKeys.add(String(alias || "").toLowerCase());
        }
      });
      return canonicalKeys;
    }

    function resetSettingsBuilderFromConfig(fields, syncFromConfig) {
      const textarea = byId("settings-patch-json");
      if (!textarea) return false;
      let current;
      try {
        current = parseSettingsPatchJson();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-patch-status", "Reset blocked");
        setText("settings-patch-detail", `Changes JSON is invalid. Fix it before resetting builder controls. ${message}`);
        renderSettingsPatchSummary();
        renderAllLaunchPreflights();
        return false;
      }

      const ownedKeys = settingsBuilderOwnedPatchKeys(fields);
      const retained = {};
      let removed = 0;
      Object.entries(current).forEach(([key, value]) => {
        if (ownedKeys.has(String(key).toLowerCase())) {
          removed += 1;
        } else {
          retained[key] = value;
        }
      });
      if (typeof syncFromConfig === "function") syncFromConfig();
      if (removed) {
        textarea.value = JSON.stringify(retained, null, 2);
        markSettingsPatchTouched();
      }
      setText("settings-patch-status", removed ? "Changes reset" : "No builder changes to reset");
      setText(
        "settings-patch-detail",
        removed
          ? `Reset From Current removed ${removed} builder-owned key(s) from Changes JSON and preserved unrelated staged changes.`
          : "Reset From Current reloaded this builder from current settings; Changes JSON contained no keys owned by this builder."
      );
      renderSettingsPatchSummary();
      renderAllLaunchPreflights();
      return true;
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

    const settingsPatchInteractionsModule = window.__settingsPatchInteractionsModule || {};
    delete window.__settingsPatchInteractionsModule;
    const settingsPatchInteractions = typeof settingsPatchInteractionsModule.createSettingsPatchInteractionsModule === "function"
      ? settingsPatchInteractionsModule.createSettingsPatchInteractionsModule({
        addSettingsEventHandlers,
        applyRouteRailBoundaryHeight,
        applyRouteRailBoundaryInput,
        audioSettingsBuilderFields,
        byId,
        fileSafetySettingsBuilderFields,
        markSettingsBuilderDirty,
        networkSettingsBuilderFields,
        pendingPublishSettingsBuilderFields,
        qualityDetailSettingsBuilderFields,
        queueSettingsBuilderFields,
        renderAllLaunchPreflights,
        renderSettingsPatchSummary,
        renderSettingsRows,
        resetSettingsBuilderFromConfig,
        routeClamp,
        routeRailBoundaryConfig,
        routeRailCurrentBoundaryHeight,
        runtimeSettingsBuilderFields,
        settingsBuilderFields,
        subtitleSettingsBuilderFields,
        videoDetailSettingsBuilderFields,
      })
      : {};
    const {
      initSettingsViewEvents = function () {},
    } = settingsPatchInteractions;

    const settingsPatchReadinessModule = window.__settingsPatchReadinessModule || {};
    delete window.__settingsPatchReadinessModule;
    const settingsPatchReadiness = typeof settingsPatchReadinessModule.createSettingsPatchReadinessModule === "function"
      ? settingsPatchReadinessModule.createSettingsPatchReadinessModule({
        appendCells,
        byId,
        clearRows,
        formatConfigValue,
        getCommandHistory,
        getSelectedSettingsSaveReviewKey,
        isSettingsCommand,
        makeRowSelectable,
        setSelectedSettingsSaveReviewKey,
        setText,
        settingsBoolValue,
        settingsBuilderConfigValue,
        settingsCommandHistoryLine,
        settingsFieldAllowedValues,
        settingsFieldDefinition,
        settingsFriendlyPersistedKeyAliases,
        settingsHasBackendFieldDefinitions,
        settingsPatchCandidateValue,
        settingsPatchComplexBackendKeys,
        settingsPatchEffectiveChangedEntries,
        settingsPatchListValue,
        settingsRawConfigValue,
        settingsValuesEqual,
        updateTableStatusLegend,
      })
      : {};
    const {
      settingsPatchLocalValidationHintsForKey = function () { return []; },
      settingsPatchLibraryOverrideValidationHints = function () { return []; },
      settingsPatchLocalValidationHints = function () { return []; },
      settingsPatchLocalValidationHintLines = function () { return []; },
      settingsReadinessIssue = function (severity, message) { return { severity, message }; },
      settingsPatchSaveReadinessIssues = function () { return []; },
      settingsPatchSaveReadinessStatus = function () { return "No changes"; },
      settingsSaveReviewPostureStatus = function () { return "match"; },
      settingsSaveReviewLatestCommand = function () { return null; },
      settingsSaveReviewRows = function () { return []; },
      settingsSaveReviewStatus = function () { return "No review"; },
      settingsSaveReviewDetailLines = function () { return []; },
      selectedSettingsSaveReviewRow = function () { return null; },
      renderSettingsSaveReviewFromEntries = function () {},
      renderSettingsPatchSaveReadinessFromEntries = function () {},
      renderSettingsPatchSaveReadinessForError = function () {},
    } = settingsPatchReadiness;

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
      settingsBuilderOwnedPatchKeys,
      resetSettingsBuilderFromConfig,
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
