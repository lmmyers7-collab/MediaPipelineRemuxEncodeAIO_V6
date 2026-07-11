(function () {
  function createSettingsViewFacade(base = {}, state = {}) {
    const modules = {};
    const resolve = (name) => {
      if (Object.prototype.hasOwnProperty.call(base, name)) return base[name];
      for (const module of Object.values(modules)) {
        if (module && Object.prototype.hasOwnProperty.call(module, name)) return module[name];
      }
      return undefined;
    };
    const scope = new Proxy({ ...base, state }, {
      get(target, name) {
        if (Reflect.has(target, name)) return Reflect.get(target, name);
        const value = resolve(name);
        if (value !== undefined) return value;
        return (...args) => {
          const deferred = resolve(name);
          if (typeof deferred !== "function") throw new Error(`Settings View dependency is unavailable: ${String(name)}`);
          return deferred(...args);
        };
      },
    });
    const factories = [
      ["builder", "__settingsViewBuilderModule", "createSettingsViewBuilderModule"],
      ["impact", "__settingsViewImpactModule", "createSettingsViewImpactModule"],
      ["review", "__settingsViewReviewModule", "createSettingsViewReviewModule"],
      ["commands", "__settingsViewCommandsModule", "createSettingsViewCommandsModule"],
      ["lifecycle", "__settingsViewLifecycleModule", "createSettingsViewLifecycleModule"],
    ];
    for (const [key, slot, factoryName] of factories) {
      const holder = window[slot] || {};
      delete window[slot];
      if (typeof holder[factoryName] !== "function") throw new Error(`Missing Settings View module: ${key}`);
      modules[key] = holder[factoryName](scope);
    }
    return Object.assign({}, ...Object.values(modules));
  }

  window.__settingsViewFacade = { createSettingsViewFacade };
})();
