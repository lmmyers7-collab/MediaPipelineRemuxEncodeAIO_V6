(function () {
  "use strict";
  function byId(id) { return document.getElementById(id); }
  function text(id, value) { const node = byId(id); if (node) node.textContent = String(value || ""); }
  function valueLines(values) {
    if (!values || typeof values !== "object") return ["No operator-meaningful values were reported."];
    const labels = { VideoCodec: "Encoder / codec", VideoQuality: "Quality", VideoPreset: "Preset", AudioPolicy: "Audio policy", SubtitlePolicy: "Subtitle policy", RoutingProfile: "Library/profile route" };
    return Object.entries(values).slice(0, 12).map(([key, entry]) => {
      const value = entry && typeof entry === "object" && "value" in entry ? entry.value : entry;
      const source = entry && typeof entry === "object" ? entry.source_layer : "library";
      return `${labels[key] || key}: ${String(value)}${source ? ` (${source})` : ""}`;
    });
  }
  function queueProvenance(row) {
    if (!row) return ["Select a Queue row to view its backend profile-effective settings and staged overrides."];
    const effective = row.library_effective_settings && typeof row.library_effective_settings === "object" ? row.library_effective_settings : {};
    const overrides = row.file_override || row.file_overrides || {};
    return [
      "Queue provenance (backend-owned):",
      "State: profile-effective, not final job-resolved settings.",
      `Library/profile: ${row.library_name || row.library_id || "not reported"}`,
      `Override source: ${Object.keys(overrides).length ? "queue/per-file override staged" : "none staged"}`,
      ...valueLines(effective),
      `Final job evidence: ${row.runtime_effective_settings_available === true ? "available" : "unavailable until runtime evidence exists"}`,
    ];
  }
  function completedProvenance(row) {
    if (!row) return ["Select a Completed row to view final job-resolved settings evidence."];
    const runtime = row.runtime_effective_settings && typeof row.runtime_effective_settings === "object" ? row.runtime_effective_settings : {};
    const values = runtime.effective_values || row.effective_settings || {};
    return [
      "Completed provenance (backend-owned):",
      `Evidence source: ${runtime.schema || row.runtime_evidence_source || "legacy or unavailable evidence"}`,
      `State: ${Object.keys(runtime).length ? "final job-resolved diagnostics" : "legacy/unavailable"}`,
      `Override source/reason: ${row.override_source || row.runtime_outcome_reason || "not reported"}`,
      ...valueLines(values),
      `Audio policy: ${row.audio_policy || "not reported"}`,
      `Subtitle policy: ${row.subtitle_policy || "not reported"}`,
    ];
  }
  function renderQueueProvenance(row) { text("queue-provenance-detail", queueProvenance(row).join("\n")); }
  function renderCompletedProvenance(row) { text("completed-provenance-detail", completedProvenance(row).join("\n")); }
  function renderDiagnosticsProvenance(context) {
    const queue = Array.isArray(context?.queue?.rows) ? context.queue.rows[0] : null;
    const completed = Array.isArray(context?.completed?.rows) ? context.completed.rows[0] : null;
    text("diagnostics-provenance-detail", [
      "Normalized effective-settings provenance contract: runtime_effective_settings.v1.",
      "Saved settings → library/profile-effective settings → per-file or queue overrides → final job-resolved settings.",
      "Unavailable or legacy evidence is explicitly labeled and is never used to make media-policy decisions in this view.",
      "",
      ...queueProvenance(queue), "", ...completedProvenance(completed),
    ].join("\n"));
  }
  document.addEventListener("click", (event) => {
    const row = event.target?.closest?.("#queue-rows tr, #completed-rows tr, #completed-history-rows tr");
    if (!row) return;
    window.setTimeout(() => {
      if (row.closest("[data-page-panel=queue]")) renderQueueProvenance(window.mediaPipelineQueueView?.getSelectedQueueRow?.());
      else renderCompletedProvenance(window.mediaPipelineCompletedView?.getSelectedCompletedRow?.());
    }, 0);
  });
  /**
   * Public namespace for provenance rendering; flat window.* exports are intentionally absent.
   */
  window.mediaPipelineProvenanceView = { renderQueueProvenance, renderCompletedProvenance, renderDiagnosticsProvenance };
}());
