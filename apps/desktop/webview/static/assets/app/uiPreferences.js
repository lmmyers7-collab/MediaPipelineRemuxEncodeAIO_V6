/* Shared WebView/Tauri UI-preference synchronization. */
(function () {
  function createAppUiPreferences(deps = {}) {
    const apiGet = deps.apiGet || (async function () { return {}; });
    const postPreferences = deps.postPreferences || (async function () { return { ok: false }; });
    const applyRuntimeState = deps.applyRuntimeState || function () {};
    const documentRef = deps.documentRef || document;
    const windowRef = deps.windowRef || window;
    const storage = deps.storage || windowRef.localStorage;
    const keyPattern = /^mediapipeline[-.][A-Za-z0-9_.:-]{1,160}$/;
    const themeKey = "mediapipeline-theme";
    let installed = false;
    let syncTimer = null;
    let remoteRefreshTimer = null;
    let syncInFlight = false;
    let syncPending = false;
    let applyingRemote = false;
    let localDirty = false;
    let lastSerialized = "";
    let awaitingRemoteEchoSerialized = "";

    function isSharedKey(key) {
      const text = String(key || "");
      if (text === themeKey) return false;
      return keyPattern.test(text);
    }

    function collect() {
      const values = {};
      try {
        for (let index = 0; index < storage.length; index += 1) {
          const key = storage.key(index);
          if (!isSharedKey(key)) continue;
          const value = storage.getItem(key);
          if (value !== null) values[key] = String(value);
        }
      } catch (_) {}
      return Object.fromEntries(Object.entries(values).sort(([left], [right]) => left.localeCompare(right)));
    }

    function surface() {
      const bootstrap = windowRef.MEDIA_PIPELINE_BOOTSTRAP || {};
      return String(bootstrap.shellSurface || bootstrap.shell_surface || "webview").toLowerCase();
    }

    function readBoolean(key) {
      try { return storage.getItem(key) === "1"; } catch (_) { return false; }
    }

    function payload() {
      return { storage: collect(), source_surface: surface() };
    }

    async function persist(options = {}) {
      const force = options.force === true;
      if (applyingRemote) return;
      if (syncInFlight) {
        syncPending = true;
        localDirty = true;
        return;
      }
      if (syncTimer) {
        windowRef.clearTimeout(syncTimer);
        syncTimer = null;
      }
      const nextPayload = payload();
      const serialized = JSON.stringify(nextPayload.storage);
      if (serialized === lastSerialized && !force) {
        localDirty = false;
        return;
      }
      syncInFlight = true;
      try {
        const result = await postPreferences(nextPayload, { timeoutMs: 5000 });
        if (result && result.ok === false) throw new Error(result.message || "UI preference sync failed.");
        lastSerialized = serialized;
        awaitingRemoteEchoSerialized = serialized;
        localDirty = false;
      } catch (_) {
        // Preference sync must never block the operator surface.
      } finally {
        syncInFlight = false;
        if (syncPending) {
          syncPending = false;
          scheduleSync();
        }
      }
    }

    function applyStorage(remoteStorage) {
      const local = collect();
      const remoteEntries = Object.entries(remoteStorage || {}).filter(([key]) => isSharedKey(key));
      const remote = Object.fromEntries(remoteEntries);
      let changed = false;
      Object.keys(local).forEach((key) => {
        if (!Object.prototype.hasOwnProperty.call(remote, key)) {
          try { storage.removeItem(key); changed = true; } catch (_) {}
        }
      });
      remoteEntries.forEach(([key, value]) => {
        const text = String(value);
        let current = null;
        try { current = storage.getItem(key); } catch (_) {}
        if (current !== text) {
          try { storage.setItem(key, text); changed = true; } catch (_) {}
        }
      });
      return changed;
    }

    function hasPendingWrite() {
      return Boolean(localDirty || syncTimer || syncPending);
    }

    function scheduleSync() {
      if (!installed || applyingRemote) return;
      localDirty = true;
      if (syncTimer) windowRef.clearTimeout(syncTimer);
      syncTimer = windowRef.setTimeout(() => {
        syncTimer = null;
        persist();
      }, 400);
    }

    async function restore(options = {}) {
      const applyRuntime = options.applyRuntime === true;
      const seedWebview = options.seedWebview !== false;
      let remote = {};
      try {
        const response = await apiGet("/api/ui-preferences", { timeoutMs: 5000 });
        if (response && typeof response.storage === "object" && response.storage !== null) remote = response.storage;
      } catch (_) {
        return;
      }
      const local = collect();
      const localSerialized = JSON.stringify(local);
      const remoteEntries = Object.entries(remote).filter(([key]) => isSharedKey(key));
      const remoteStorage = Object.fromEntries(remoteEntries);
      const remoteSerialized = JSON.stringify(remoteStorage);
      if (awaitingRemoteEchoSerialized && remoteSerialized === localSerialized) awaitingRemoteEchoSerialized = "";
      if (surface() !== "tauri" && seedWebview && Object.keys(local).length && remoteSerialized !== localSerialized) {
        await persist();
        return;
      }
      if (installed && hasPendingWrite() && remoteSerialized !== localSerialized) {
        await persist();
        return;
      }
      if (installed && awaitingRemoteEchoSerialized === localSerialized && remoteSerialized !== localSerialized) {
        await persist({ force: true });
        return;
      }
      if (remoteEntries.length) {
        applyingRemote = true;
        try {
          const changed = applyStorage(remoteStorage);
          if (changed && applyRuntime) applyRuntimeState();
        } finally {
          applyingRemote = false;
        }
        lastSerialized = JSON.stringify(collect());
        awaitingRemoteEchoSerialized = "";
        localDirty = false;
        return;
      }
      if (surface() !== "tauri" && Object.keys(local).length) await persist();
    }

    function startRemoteRefresh() {
      if (surface() !== "tauri" || remoteRefreshTimer) return;
      const refresh = () => {
        if (syncInFlight || applyingRemote) return;
        restore({ applyRuntime: true, seedWebview: false });
      };
      windowRef.addEventListener("focus", refresh);
      documentRef.addEventListener("visibilitychange", () => {
        if (documentRef.visibilityState === "visible") refresh();
      });
      remoteRefreshTimer = windowRef.setInterval(refresh, 3000);
    }

    function installStorageSync() {
      if (installed || !windowRef.Storage?.prototype) return;
      installed = true;
      const originalSetItem = windowRef.Storage.prototype.setItem;
      const originalRemoveItem = windowRef.Storage.prototype.removeItem;
      windowRef.Storage.prototype.setItem = function setItemWithUiPreferenceSync(key, value) {
        const result = originalSetItem.call(this, key, value);
        if (this === windowRef.localStorage && isSharedKey(key)) scheduleSync();
        return result;
      };
      windowRef.Storage.prototype.removeItem = function removeItemWithUiPreferenceSync(key) {
        const result = originalRemoveItem.call(this, key);
        if (this === windowRef.localStorage && isSharedKey(key)) scheduleSync();
        return result;
      };
    }

    return {
      currentSurface: surface,
      installStorageSync,
      persist,
      readBoolean,
      restore,
      startRemoteRefresh,
    };
  }

  window.__appUiPreferencesModule = { createAppUiPreferences };
})();
