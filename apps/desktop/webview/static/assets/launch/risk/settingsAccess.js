(function () {
  function createLaunchRiskSettingsAccessModule(deps = {}) {
    const {
      getLastSettings = function () { return {}; },
    } = deps;

  function launchSettingsWorkspace() {
    try {
      if (typeof getLastSettings === "function") return getLastSettings() || {};
    } catch {
      return {};
    }
    return {};
  }

  function launchSettingsConfigValue(config, key) {
    if (!config || typeof config !== "object") return undefined;
    if (Object.prototype.hasOwnProperty.call(config, key)) return config[key];
    const match = Object.keys(config).find((item) => item.toLowerCase() === String(key).toLowerCase());
    return match ? config[match] : undefined;
  }

    return {
      launchSettingsWorkspace,
      launchSettingsConfigValue,
    };
  }

  window.__launchRiskSettingsAccessModule = {
    createLaunchRiskSettingsAccessModule,
  };
})();
