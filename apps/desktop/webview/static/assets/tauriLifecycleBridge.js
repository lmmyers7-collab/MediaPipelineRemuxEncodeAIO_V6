(() => {
  const TAURI_BACKEND_LIFECYCLE_EVENT = "mediapipeline://backend-lifecycle";
  const TAURI_DRAG_ENTER_EVENT = "tauri://drag-enter";
  const TAURI_DRAG_OVER_EVENT = "tauri://drag-over";
  const TAURI_DRAG_DROP_EVENT = "tauri://drag-drop";
  const TAURI_DRAG_LEAVE_EVENT = "tauri://drag-leave";
  const WEBVIEW_BACKEND_LIFECYCLE_EVENT = "mediapipeline:backend-lifecycle";
  const WEBVIEW_FILE_DROP_EVENT = "mediapipeline:file-drop";
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

  function dragPayload(event) {
    return event && typeof event === "object" && event.payload && typeof event.payload === "object"
      ? event.payload
      : {};
  }

  function dragPayloadItems(event) {
    return (Array.isArray(dragPayload(event).paths) ? dragPayload(event).paths : [])
      .map((item) => String(item || "").trim())
      .filter(Boolean);
  }

  function dragEventDetail(kind, source, event) {
    const payload = dragPayload(event);
    return {
      source,
      kind,
      paths: dragPayloadItems(event),
      position: payload.position || null,
      payload,
    };
  }

  function dispatchBackendLifecycleEvent(detail) {
    latestBackendLifecycleDetail = detail;
    window.dispatchEvent(new CustomEvent(WEBVIEW_BACKEND_LIFECYCLE_EVENT, { detail }));
  }

  function dispatchFileDropEvent(detail) {
    window.dispatchEvent(new CustomEvent(WEBVIEW_FILE_DROP_EVENT, { detail }));
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
    fileDropEventName: WEBVIEW_FILE_DROP_EVENT,
    replayLatestBackendLifecycleEvent,
  });

  async function listenForTauriEvent(eventApi, name, callback, unlisteners) {
    try {
      const unlisten = await eventApi.listen(name, callback);
      if (typeof unlisten === "function") unlisteners.push(unlisten);
    } catch (error) {
      console.warn("Tauri event listener was not registered.", name, error);
    }
  }

  async function startTauriLifecycleBridge() {
    const eventApi = tauriEventApi();
    if (!eventApi) return;
    const unlisteners = [];
    await listenForTauriEvent(eventApi, TAURI_BACKEND_LIFECYCLE_EVENT, (event) => {
      dispatchBackendLifecycleEvent(backendLifecycleDetail(event));
    }, unlisteners);
    await listenForTauriEvent(eventApi, TAURI_DRAG_ENTER_EVENT, (event) => {
      dispatchFileDropEvent(dragEventDetail("enter", TAURI_DRAG_ENTER_EVENT, event));
    }, unlisteners);
    await listenForTauriEvent(eventApi, TAURI_DRAG_OVER_EVENT, (event) => {
      dispatchFileDropEvent(dragEventDetail("over", TAURI_DRAG_OVER_EVENT, event));
    }, unlisteners);
    await listenForTauriEvent(eventApi, TAURI_DRAG_DROP_EVENT, (event) => {
      dispatchFileDropEvent(dragEventDetail("drop", TAURI_DRAG_DROP_EVENT, event));
    }, unlisteners);
    await listenForTauriEvent(eventApi, TAURI_DRAG_LEAVE_EVENT, (event) => {
      dispatchFileDropEvent(dragEventDetail("leave", TAURI_DRAG_LEAVE_EVENT, event));
    }, unlisteners);
    window.addEventListener("beforeunload", () => {
      unlisteners.forEach((unlisten) => unlisten());
    }, { once: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startTauriLifecycleBridge, { once: true });
  } else {
    startTauriLifecycleBridge();
  }
})();
