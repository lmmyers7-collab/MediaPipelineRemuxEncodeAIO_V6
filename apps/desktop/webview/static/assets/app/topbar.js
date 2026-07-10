(function () {
  const HOME_PIPELINE_STATE_LABELS = Object.freeze({
    idle: { main: "Idle", detail: "" },
    initializing: { main: "Initializing", detail: "" },
    scanning_sources: { main: "Scanning Sources", detail: "" },
    "scanning_sources_(dry_run)": { main: "Scanning Sources", detail: "(dry run)" },
    processing: { main: "Processing", detail: "" },
    processing_queue: { main: "Processing Queue", detail: "" },
    encoding_movie: { main: "Encoding Movie", detail: "" },
    encoding_tv: { main: "Encoding TV", detail: "" },
    "encoding_movie_(cpu_fallback)": { main: "Encoding Movie", detail: "(cpu fallback)" },
    "encoding_tv_(cpu_fallback)": { main: "Encoding TV", detail: "(cpu fallback)" },
    waiting_for_cpu_encode_slot: { main: "Waiting For CPU Encode Slot", detail: "" },
    remuxing_movie: { main: "Remuxing Movie", detail: "" },
    remuxing_tv: { main: "Remuxing TV", detail: "" },
    "waiting_for_cpu_slot_(audio_transcode)": { main: "Waiting For CPU Slot", detail: "(audio transcode)" },
    publishing_parked_outputs: { main: "Publishing Parked Outputs", detail: "" },
    retrying_pending_push: { main: "Retrying Pending Publish", detail: "" },
    paused: { main: "Paused", detail: "" },
    resumed: { main: "Resumed", detail: "" },
    stopped: { main: "Stopped", detail: "" },
    completed: { main: "Completed", detail: "" },
    csv_rerun_active: { main: "CSV Rerun", detail: "active" },
    csv_rerun_complete: { main: "CSV Rerun", detail: "complete" },
    no_new_sources: { main: "No New Sources", detail: "" },
    failed: { main: "Failed", detail: "" },
    error: { main: "Error", detail: "" },
    audit: { main: "Audit", detail: "" },
  });

  const HOME_PIPELINE_STATE_ACRONYMS = new Set(["api", "bdpgs", "cpu", "csv", "ffmpeg", "srt", "tv", "tx3g", "vobsub"]);

  function renderBrandVersion(snapshot = {}, bootstrap = window.MEDIA_PIPELINE_BOOTSTRAP || {}) {
    setText("app-version", bootstrap.appVersion || snapshot.app_version || "2026.06.04.001");
  }

  function titleCaseHomePipelineState(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim()
      .split(" ")
      .filter(Boolean)
      .map((word) => {
        const normalized = word.toLowerCase();
        if (HOME_PIPELINE_STATE_ACRONYMS.has(normalized)) return normalized.toUpperCase();
        return normalized.charAt(0).toUpperCase() + normalized.slice(1);
      })
      .join(" ");
  }

  function formatHomePipelineState(value) {
    const raw = String(value || "idle").trim() || "idle";
    const key = raw.toLowerCase();
    const known = HOME_PIPELINE_STATE_LABELS[key];
    if (known) {
      const label = known.detail ? `${known.main} ${known.detail}` : known.main;
      return { main: known.main, detail: known.detail, label };
    }
    const readable = raw.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
    const parenthetical = readable.match(/^(.*?)\s*(\([^)]*\))\s*$/);
    const mainText = parenthetical ? parenthetical[1] : readable;
    const detailText = parenthetical ? parenthetical[2].toLowerCase() : "";
    const main = titleCaseHomePipelineState(mainText || "idle");
    const label = detailText ? `${main} ${detailText}` : main;
    return { main, detail: detailText, label };
  }

  function renderHomePipelineState(value) {
    const node = byId("pipeline-state");
    if (!node) return;
    const formatted = formatHomePipelineState(value);
    const mainNode = node.querySelector(".pipeline-state-main");
    const detailNode = node.querySelector(".pipeline-state-detail");
    if (!mainNode || !detailNode) {
      node.textContent = formatted.label;
    } else {
      mainNode.textContent = formatted.main;
      detailNode.textContent = formatted.detail;
      detailNode.hidden = !formatted.detail;
    }
    node.setAttribute("aria-label", formatted.label);
    node.setAttribute("title", formatted.label);
  }

  function topbarStageContext(progress = {}) {
    return window.mediaPipelineAppLifecycle?.topbarStageContext?.(progress) || "";
  }

  function renderTopbarActivity(snapshot = {}) {
    return window.mediaPipelineAppLifecycle?.renderTopbarActivity?.(snapshot);
  }

  function renderTopbarEventTicker(snapshot = {}) {
    return window.mediaPipelineAppLifecycle?.renderTopbarEventTicker?.(snapshot);
  }

  function setTopbarPendingLaunch(payload = {}) {
    return window.mediaPipelineAppLifecycle?.setTopbarPendingLaunch?.(payload);
  }

  function clearTopbarPendingLaunch(snapshot = {}) {
    return window.mediaPipelineAppLifecycle?.clearTopbarPendingLaunch?.(snapshot);
  }

  window.mediaPipelineAppTopbar = {
    renderBrandVersion,
    titleCaseHomePipelineState,
    formatHomePipelineState,
    renderHomePipelineState,
    topbarStageContext,
    renderTopbarActivity,
    renderTopbarEventTicker,
    setTopbarPendingLaunch,
    clearTopbarPendingLaunch,
  };
})();
