(function () {
  "use strict";

  const TOAST_REGION_ID = "operator-toast-region";
  const FAILURE_ARTIFACT_SESSION_KEY = "mediapipeline.failureArtifactWarningToastShown";

  function ensureToastRegion() {
    let region = document.getElementById(TOAST_REGION_ID);
    if (region) return region;
    region = document.createElement("div");
    region.id = TOAST_REGION_ID;
    region.className = "operator-toast-region";
    region.setAttribute("aria-live", "polite");
    region.setAttribute("aria-atomic", "false");
    document.body.appendChild(region);
    return region;
  }

  function removeToast(toast) {
    if (!toast || !toast.parentElement) return;
    toast.parentElement.removeChild(toast);
  }

  function sessionValue(key) {
    try {
      return window.sessionStorage?.getItem(key) || "";
    } catch {
      return "";
    }
  }

  function setSessionValue(key, value) {
    try {
      window.sessionStorage?.setItem(key, value);
    } catch {
      // Storage can be unavailable in locked-down WebView modes; the toast still works.
    }
  }

  function showToast({
    id = "",
    severity = "warning",
    title = "Notice",
    message = "",
    actionLabel = "",
    onAction = null,
    closeLabel = "Dismiss",
    timeoutMs = 12000,
  } = {}) {
    const region = ensureToastRegion();
    const toastId = String(id || `toast-${Date.now()}`);
    Array.from(region.querySelectorAll("[data-toast-id]"))
      .filter((item) => item.dataset.toastId === toastId)
      .forEach(removeToast);

    const toast = document.createElement("section");
    toast.className = "operator-toast";
    toast.dataset.toastId = toastId;
    toast.dataset.severity = severity || "warning";
    toast.setAttribute("role", "status");

    const content = document.createElement("div");
    content.className = "operator-toast-content";
    const heading = document.createElement("strong");
    heading.className = "operator-toast-title";
    heading.textContent = title || "Notice";
    const body = document.createElement("p");
    body.className = "operator-toast-message";
    body.textContent = message || "";
    content.append(heading, body);

    const actions = document.createElement("div");
    actions.className = "operator-toast-actions";
    if (actionLabel && typeof onAction === "function") {
      const action = document.createElement("button");
      action.type = "button";
      action.className = "secondary-button operator-toast-action";
      action.textContent = actionLabel;
      action.addEventListener("click", () => {
        removeToast(toast);
        onAction();
      });
      actions.appendChild(action);
    }
    const close = document.createElement("button");
    close.type = "button";
    close.className = "tertiary-button operator-toast-close";
    close.textContent = closeLabel || "Dismiss";
    close.setAttribute("aria-label", "Dismiss notice");
    close.addEventListener("click", () => removeToast(toast));
    actions.appendChild(close);

    toast.append(content, actions);
    region.appendChild(toast);
    if (Number.isFinite(timeoutMs) && timeoutMs > 0) {
      window.setTimeout(() => removeToast(toast), timeoutMs);
    }
    return toast;
  }

  function focusFailureArtifactPanel() {
    window.setTimeout(() => {
      const panel = document.getElementById("failure-artifact-summary-panel");
      if (!panel) return;
      if (!panel.hasAttribute("tabindex")) panel.setAttribute("tabindex", "-1");
      panel.focus({ preventScroll: false });
      panel.scrollIntoView({ block: "start", behavior: "smooth" });
    }, 75);
  }

  function showFailureArtifactWarning(summary = {}) {
    if (!summary || typeof summary !== "object" || summary.warning !== true) return false;
    const threshold = Number(summary.threshold_gb);
    if (!Number.isFinite(threshold) || threshold <= 0) return false;
    if (sessionValue(FAILURE_ARTIFACT_SESSION_KEY)) return false;
    setSessionValue(FAILURE_ARTIFACT_SESSION_KEY, "1");
    const total = summary.total_size_text || `${Number(summary.total_gb || 0).toFixed(1)} GB`;
    const message = summary.warning_message
      || `Failure artifacts are using ${total}, at or above the configured ${threshold} GB warning threshold.`;
    showToast({
      id: "failure-artifact-warning",
      severity: "warning",
      title: "Failure artifacts need review",
      message,
      actionLabel: "Open Reports",
      onAction: () => {
        if (typeof window.showPage === "function") window.showPage("reports");
        window.mediaPipelineReportsView?.activateQuickLink?.("failure-all");
        focusFailureArtifactPanel();
      },
    });
    return true;
  }

  /**
   * Public namespace for app-wide operator toasts.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineOperatorToast = {
    showToast,
    showFailureArtifactWarning,
  };
})();
