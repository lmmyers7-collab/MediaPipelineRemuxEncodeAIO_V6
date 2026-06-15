(() => {
  const TAURI_BACKEND_LIFECYCLE_EVENT = "mediapipeline://backend-lifecycle";
  const WEBVIEW_BACKEND_LIFECYCLE_EVENT = "mediapipeline:backend-lifecycle";
  let latestBackendLifecycleDetail = null;

  function tauriEventApi() {
    const tauri = window.__TAURI__;
    return tauri && tauri.event && typeof tauri.event.listen === "function"
      ? tauri.event
      : null;
  }

  function backendLifecycleDetail(event) {
    return {
      source: TAURI_BACKEND_LIFECYCLE_EVENT,
      payload: event && typeof event === "object" ? event.payload : null,
    };
  }

  function dispatchBackendLifecycleEvent(detail) {
    latestBackendLifecycleDetail = detail;
    window.dispatchEvent(new CustomEvent(WEBVIEW_BACKEND_LIFECYCLE_EVENT, { detail }));
  }

  function replayLatestBackendLifecycleEvent() {
    if (!latestBackendLifecycleDetail) return false;
    window.dispatchEvent(new CustomEvent(WEBVIEW_BACKEND_LIFECYCLE_EVENT, {
      detail: latestBackendLifecycleDetail,
    }));
    return true;
  }

  window.mediaPipelineTauriLifecycleBridge = Object.freeze({
    eventName: WEBVIEW_BACKEND_LIFECYCLE_EVENT,
    replayLatestBackendLifecycleEvent,
  });

  async function startTauriLifecycleBridge() {
    const eventApi = tauriEventApi();
    if (!eventApi) return;
    try {
      const unlisten = await eventApi.listen(TAURI_BACKEND_LIFECYCLE_EVENT, (event) => {
        dispatchBackendLifecycleEvent(backendLifecycleDetail(event));
      });
      window.addEventListener("beforeunload", () => {
        if (typeof unlisten === "function") unlisten();
      }, { once: true });
    } catch (error) {
      console.warn("Tauri backend lifecycle listener was not registered.", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startTauriLifecycleBridge, { once: true });
  } else {
    startTauriLifecycleBridge();
  }
})();
