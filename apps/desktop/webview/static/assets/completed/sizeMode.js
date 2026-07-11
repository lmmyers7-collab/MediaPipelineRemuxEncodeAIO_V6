(function () {
  /** Maintains the local Completed size-column presentation preference only. */
  function createCompletedSizeMode(deps) {
    const byId = deps.byId || function () { return null; };
    const storageKey = deps.storageKey || "mediapipeline.completed.sizeColumnMode";
    function normalize(value) {
      return String(value || "").trim().toLowerCase() === "delta" ? "delta" : "output";
    }
    let mode;
    try { mode = normalize(window.localStorage?.getItem(storageKey)); } catch (_error) { mode = "output"; }
    function getMode() { return mode; }
    function sync() {
      const normalized = normalize(mode);
      document.querySelectorAll("[data-completed-size-column-mode]").forEach((button) => {
        const active = normalize(button.dataset.completedSizeColumnMode) === normalized;
        button.setAttribute("aria-pressed", active ? "true" : "false");
        button.classList.toggle("is-active", active);
      });
      document.querySelectorAll("[data-completed-size-column-label]").forEach((node) => {
        node.textContent = normalized === "delta" ? "Size delta" : "Output size";
      });
    }
    function setMode(value) {
      mode = normalize(value);
      try { window.localStorage?.setItem(storageKey, mode); } catch (_error) {}
      sync();
      return mode;
    }
    return { getMode, setMode, sync };
  }
  window.__completedSizeModeModule = createCompletedSizeMode;
})();
