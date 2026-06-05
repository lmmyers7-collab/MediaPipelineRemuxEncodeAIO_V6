(function () {
  function createLaunchRiskMediaPolicyValuesModule(deps = {}) {
    const {
      formatSettingsChoiceLabel = null,
      launchSettingsConfigValue = function () { return undefined; },
    } = deps;

  function launchSettingsBool(value, fallback = false) {
    if (typeof value === "boolean") return value;
    if (value === undefined || value === null || value === "") return fallback;
    return ["1", "true", "yes", "on", "enabled"].includes(String(value).trim().toLowerCase());
  }

  function launchSettingsNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function launchRouteMaxHeightFromUpperTolerance(baseHeight, tolerancePercent) {
    return Math.round(Number(baseHeight) * (1 + (Number(tolerancePercent) / 100)));
  }

  function launchRouteMinHeightFromLowerTolerance(baseHeight, tolerancePercent) {
    return Math.round(Number(baseHeight) * (1 - (Number(tolerancePercent) / 100)));
  }

  function launchRouteHeightBoundaries(config) {
    const percentKeys = [
      "Route1080pUpperHeightTolerancePercent",
      "Route1440pLowerHeightTolerancePercent",
      "Route1440pUpperHeightTolerancePercent",
      "Route4KLowerHeightTolerancePercent",
    ];
    const hasPercentKeys = percentKeys.some((key) => {
      const value = launchSettingsConfigValue(config, key);
      return value !== undefined && value !== null && String(value).trim() !== "";
    });
    if (!hasPercentKeys) {
      const route1080pMaxHeight = Math.round(launchSettingsNumber(launchSettingsConfigValue(config, "Route1080pBucketMaxHeight"), 1200));
      const route4kMinHeight = Math.round(launchSettingsNumber(launchSettingsConfigValue(config, "Route4KBucketMinHeight"), 1800));
      return {
        route1080pMaxHeight,
        route1440pMinHeight: route1080pMaxHeight + 1,
        route1440pMaxHeight: route4kMinHeight - 1,
        route4kMinHeight,
      };
    }
    return {
      route1080pMaxHeight: launchRouteMaxHeightFromUpperTolerance(
        1080,
        launchSettingsNumber(launchSettingsConfigValue(config, "Route1080pUpperHeightTolerancePercent"), 11.111111)
      ),
      route1440pMinHeight: launchRouteMinHeightFromLowerTolerance(
        1440,
        launchSettingsNumber(launchSettingsConfigValue(config, "Route1440pLowerHeightTolerancePercent"), 16.597222)
      ),
      route1440pMaxHeight: launchRouteMaxHeightFromUpperTolerance(
        1440,
        launchSettingsNumber(launchSettingsConfigValue(config, "Route1440pUpperHeightTolerancePercent"), 24.930556)
      ),
      route4kMinHeight: launchRouteMinHeightFromLowerTolerance(
        2160,
        launchSettingsNumber(launchSettingsConfigValue(config, "Route4KLowerHeightTolerancePercent"), 16.666667)
      ),
    };
  }

  function launchSettingsList(value, fallback = []) {
    if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
    if (value === undefined || value === null || value === "") return Array.isArray(fallback) ? fallback : [];
    return String(value).split(/[,;]/).map((item) => item.trim()).filter(Boolean);
  }

  function launchPolicyChoiceLabel(value) {
    if (typeof formatSettingsChoiceLabel === "function") return formatSettingsChoiceLabel(value);
    return String(value || "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim() || "(not set)";
  }

  function launchPolicyBoolText(value) {
    return launchSettingsBool(value, false) ? "on" : "off";
  }

    return {
      launchSettingsBool,
      launchSettingsNumber,
      launchRouteMaxHeightFromUpperTolerance,
      launchRouteMinHeightFromLowerTolerance,
      launchRouteHeightBoundaries,
      launchSettingsList,
      launchPolicyChoiceLabel,
      launchPolicyBoolText,
    };
  }

  window.__launchRiskMediaPolicyValuesModule = {
    createLaunchRiskMediaPolicyValuesModule,
  };
})();
