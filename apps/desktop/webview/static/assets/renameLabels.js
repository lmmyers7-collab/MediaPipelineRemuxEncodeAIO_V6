(function () {
  function renameStatusExplanation(status) {
    switch (String(status || "").toLowerCase()) {
      case "ready":
        return "Ready: backend preview has no blockers or warnings.";
      case "match":
        return "Match: source already has the target filename.";
      case "warning":
        return "Warning: row can be applied, but review the listed warning first.";
      case "blocked":
        return "Blocked: backend will not apply this row until errors are fixed.";
      default:
        return "Unknown: refresh preview before applying.";
    }
  }

  function renamePreviewSourceLabel(value) {
    switch (String(value || "").toLowerCase()) {
      case "pipeline_tv_preview":
        return "Pipeline TV preview";
      case "pipeline_movie_preview":
        return "Pipeline movie preview";
      case "manual_tv_sequence":
        return "Manual TV sequence";
      case "manual_movie_template":
        return "Manual movie template";
      case "auto_tv_heuristic":
        return "Auto TV scrub";
      case "movie_scrub_heuristic":
        return "Movie scrub filters";
      case "error":
        return "Preview error";
      default:
        return value ? String(value) : "Not reported";
    }
  }

  function renameConfidenceExplanation(value) {
    switch (String(value || "").toLowerCase()) {
      case "high":
        return "High confidence: source came from pipeline preview or explicit operator fields.";
      case "medium":
        return "Medium confidence: source came from rename scrub heuristics; review show/title assumptions.";
      case "review":
        return "Review: backend found warnings that need operator attention.";
      case "blocked":
        return "Blocked: backend found errors and apply is disabled for this row.";
      default:
        return "Confidence not reported by backend.";
    }
  }

  function renameConfidenceLabel(item) {
    const confidence = item?.confidence || "";
    if (!confidence) return "";
    const source = renamePreviewSourceLabel(item?.preview_source || "");
    return `${confidence}${source ? ` (${source})` : ""}`;
  }

  /**
   * Public namespace for shared rename labels.
   * Rename label helpers are exposed here; callers should use this namespace
   * because this module no longer publishes flat window.* exports.
   */
  window.mediaPipelineRenameLabels = {
    renameStatusExplanation,
    renamePreviewSourceLabel,
    renameConfidenceExplanation,
    renameConfidenceLabel,
  };
})();
