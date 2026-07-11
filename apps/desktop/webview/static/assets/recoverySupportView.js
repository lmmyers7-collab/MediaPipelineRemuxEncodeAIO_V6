(function () {
  "use strict";
  let initialized = false;
  function byId(id) { return document.getElementById(id); }
  function text(id, value) { const node = byId(id); if (node) node.textContent = String(value || ""); }
  function safe(value) { return String(value || "").replace(/(?:bearer\s+|token\s*[=:]\s*)[^\s,;]+/gi, "$1<redacted>").slice(0, 700); }
  function meaningfulRecovery(payload) {
    const classification = String(payload?.classification || "").toLowerCase();
    const status = String(payload?.status || "").toLowerCase();
    return ["recovered", "parked", "failed", "blocked", "warning", "unavailable", "unknown"].includes(classification)
      || ["blocked", "failed", "unavailable"].includes(status);
  }
  function renderRecoveryStatus(payload) {
    const data = payload && typeof payload === "object" ? payload : {};
    const classification = String(data.classification || "unknown");
    const status = String(data.status || "unknown");
    const action = safe(data.operator_action_required || "No backend recovery action is currently reported.");
    const items = Array.isArray(data.items) ? data.items : [];
    const banner = byId("home-recovery-banner");
    if (banner) {
      const show = meaningfulRecovery(data);
      banner.hidden = !show;
      banner.textContent = show ? `Startup recovery: ${classification}. ${action}` : "";
      banner.dataset.state = classification;
    }
    text("diagnostics-recovery-status", `${classification} (${status})`);
    text("diagnostics-recovery-detail", [
      "Backend lifecycle recovery evidence:",
      `Classification: ${classification}`,
      `Status: ${status}`,
      `Operator action: ${action}`,
      `Evidence items: ${items.length}`,
      ...items.slice(0, 12).map((item, index) => `- ${index + 1}. ${safe(item?.reason || item?.status || JSON.stringify(item))}`),
      "Guardrail: this display never resumes, repairs, clears, drains, or changes lifecycle state.",
    ].join("\n"));
  }
  function renderProductization(payload) {
    const data = payload && typeof payload === "object" ? payload : {};
    const available = data.error ? "unavailable" : "ready";
    text("maintenance-support-productization", data.error ? safe(data.error) : [
      `Release channel: ${data?.updater?.active_channel || "not reported"}`,
      `Installer target: ${data?.installer?.target || "not reported"}`,
      `AppData available: ${data?.runtime_roots?.appdata_available === true ? "yes" : "no"}`,
      "Support bundles are created and redacted by the backend.",
    ].join("\n"));
    const status = byId("maintenance-support-status");
    if (status && !status.dataset.busy) { status.textContent = available; status.dataset.state = available; }
  }
  async function createSupportBundle() {
    const status = byId("maintenance-support-status");
    if (status?.dataset.busy === "true") return;
    if (status) { status.dataset.busy = "true"; status.textContent = "Creating bundle…"; }
    const request = {
      reason: String(byId("maintenance-support-reason")?.value || "operator support").slice(0, 500),
      include_recent_logs: Boolean(byId("maintenance-support-include-logs")?.checked),
      max_log_bytes: Number(byId("maintenance-support-max-log-bytes")?.value || 32768),
    };
    try {
      const result = await window.apiPost("/api/maintenance/support-export", request);
      const data = result?.data || {};
      text("maintenance-support-result", [
        result?.message || "Support bundle request finished.",
        `Destination: ${safe(data.export_path || data.destination || "not reported")}`,
        `Secrets redacted: ${data?.redaction?.secrets_redacted === true ? "yes" : "not reported"}`,
        `Personal paths redacted: ${data?.redaction?.personal_paths_redacted === true ? "yes" : "not reported"}`,
        `Full configuration included: ${data?.redaction?.full_config_included === true ? "unexpected yes" : "no"}`,
        `Contents: ${safe(data.content_summary || data.contents_summary || "backend redaction summary returned with the bundle")}`,
      ].join("\n"));
      if (status) { status.textContent = result?.ok ? "Bundle created" : "Bundle needs review"; status.dataset.state = result?.ok ? "ready" : "warning"; }
    } catch (error) {
      text("maintenance-support-result", `Support bundle could not be created: ${safe(error instanceof Error ? error.message : error)}`);
      if (status) { status.textContent = "Bundle unavailable"; status.dataset.state = "warning"; }
    } finally { if (status) delete status.dataset.busy; }
  }
  function initRecoverySupportEvents() {
    if (initialized) return;
    initialized = true;
    byId("maintenance-support-create")?.addEventListener("click", () => void createSupportBundle());
  }
  /**
   * Public namespace for recovery and support rendering; flat window.* exports are intentionally absent.
   */
  window.mediaPipelineRecoverySupportView = { renderRecoveryStatus, renderProductization, initRecoverySupportEvents };
}());
