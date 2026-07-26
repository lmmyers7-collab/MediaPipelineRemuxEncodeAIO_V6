(function () {
  "use strict";
  let initialized = false;
  let lifecycleReconcileBusy = false;
  let lifecycleReconcilePreview = null;
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
  function reconciliationReason() {
    return "Operator-reviewed terminal stale lifecycle recovery evidence";
  }
  function appendEvidence(result) {
    if (typeof window.appendCommandResult === "function") window.appendCommandResult(result);
  }
  function setReconcileControls({ previewDisabled, applyDisabled, status } = {}) {
    const previewButton = byId("diagnostics-recovery-preview-button");
    const reconcileButton = byId("diagnostics-recovery-reconcile-button");
    if (previewButton) previewButton.disabled = Boolean(previewDisabled);
    if (reconcileButton) reconcileButton.disabled = applyDisabled !== false;
    if (status !== undefined) text("diagnostics-recovery-action-status", status);
  }
  function renderReconcileResult(result, fallback) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const blockers = Array.isArray(data.blockers) ? data.blockers : [];
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    text("diagnostics-recovery-action-detail", [
      safe(result?.message || fallback),
      `Safe to apply: ${data.safe_to_apply === true ? "yes" : "no"}`,
      `Evidence records: ${Array.isArray(data.evidence_paths) ? data.evidence_paths.length : "not reported"}`,
      `Recorded PIDs checked: ${Array.isArray(data.pid_verdicts) ? data.pid_verdicts.length : "not reported"}`,
      ...blockers.map((item) => `Blocker: ${safe(item)}`),
      ...errors.map((item) => `Error: ${safe(item)}`),
    ].join("\n"));
  }
  async function previewLifecycleReconcile() {
    if (lifecycleReconcileBusy) return;
    lifecycleReconcileBusy = true;
    lifecycleReconcilePreview = null;
    setReconcileControls({ previewDisabled: true, applyDisabled: true, status: "Verifying lifecycle evidence…" });
    try {
      const result = await window.apiPost(
        "/api/backend/lifecycle/reconcile-dry-run",
        { reason: reconciliationReason() },
      );
      appendEvidence(result);
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const safeToApply = result?.ok === true
        && data.safe_to_apply === true
        && Boolean(String(data.dry_run_fingerprint || "").trim());
      lifecycleReconcilePreview = safeToApply ? {
        dry_run_fingerprint: String(data.dry_run_fingerprint),
      } : null;
      setReconcileControls({
        previewDisabled: false,
        applyDisabled: !safeToApply,
        status: safeToApply ? "Preview passed. Reconciliation is available." : "Preview blocked. Review the evidence below.",
      });
      renderReconcileResult(result, "Lifecycle reconciliation preview finished.");
    } catch (error) {
      const result = {
        command: "backend.lifecycle.reconcile_dry_run",
        ok: false,
        severity: "error",
        message: `Lifecycle reconciliation preview failed: ${safe(error instanceof Error ? error.message : error)}`,
        errors: [safe(error instanceof Error ? error.message : error)],
        data: { safe_to_apply: false },
      };
      appendEvidence(result);
      setReconcileControls({ previewDisabled: false, applyDisabled: true, status: "Preview unavailable." });
      renderReconcileResult(result, "Lifecycle reconciliation preview failed.");
    } finally {
      lifecycleReconcileBusy = false;
    }
  }
  async function applyLifecycleReconcile() {
    if (lifecycleReconcileBusy || !lifecycleReconcilePreview) return;
    const preview = lifecycleReconcilePreview;
    lifecycleReconcilePreview = null;
    lifecycleReconcileBusy = true;
    setReconcileControls({ previewDisabled: true, applyDisabled: true, status: "Archiving verified terminal lifecycle evidence…" });
    try {
      const result = await window.apiPost(
        "/api/backend/lifecycle/reconcile",
        {
          confirm_apply: true,
          dry_run_fingerprint: preview.dry_run_fingerprint,
          reason: reconciliationReason(),
        },
      );
      appendEvidence(result);
      setReconcileControls({
        previewDisabled: false,
        applyDisabled: true,
        status: result?.ok ? "Lifecycle evidence reconciled. Refreshing backend state…" : "Reconciliation was not applied.",
      });
      renderReconcileResult(result, "Lifecycle reconciliation finished.");
      if (result?.ok && typeof window.refreshAll === "function") await window.refreshAll();
    } catch (error) {
      const result = {
        command: "backend.lifecycle.reconcile",
        ok: false,
        severity: "error",
        message: `Lifecycle reconciliation failed: ${safe(error instanceof Error ? error.message : error)}`,
        errors: [safe(error instanceof Error ? error.message : error)],
        data: { applied: false },
      };
      appendEvidence(result);
      setReconcileControls({ previewDisabled: false, applyDisabled: true, status: "Reconciliation failed. Run a new preview before retrying." });
      renderReconcileResult(result, "Lifecycle reconciliation failed.");
    } finally {
      lifecycleReconcileBusy = false;
    }
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
    setReconcileControls({ previewDisabled: false, applyDisabled: true });
    byId("diagnostics-recovery-preview-button")?.addEventListener("click", () => void previewLifecycleReconcile());
    byId("diagnostics-recovery-reconcile-button")?.addEventListener("click", () => void applyLifecycleReconcile());
    byId("maintenance-support-create")?.addEventListener("click", () => void createSupportBundle());
  }
  /**
   * Public namespace for recovery and support rendering; flat window.* exports are intentionally absent.
   */
  window.mediaPipelineRecoverySupportView = { renderRecoveryStatus, renderProductization, initRecoverySupportEvents };
}());
