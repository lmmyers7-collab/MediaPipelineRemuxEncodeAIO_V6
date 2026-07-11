(function () {
  function createProgressActiveWorkModule(deps) {
    const formatProgressValue = deps?.formatProgressValue || ((value) => String(value ?? ""));

    function activeWorkProgressLine(progress) {
      const stage = progress?.CurrentStage || progress?.Status || "";
      const percent = progress?.CurrentStagePercent;
      const file = progress?.CurrentFileDisplay || progress?.CurrentFile || progress?.InputFile || "";
      const parts = [];
      if (stage) parts.push(`Stage: ${formatProgressValue(stage)}`);
      if (percent !== undefined && percent !== null && percent !== "") parts.push(`Stage percent: ${formatProgressValue(percent)}`);
      if (file) parts.push(`File: ${formatProgressValue(file)}`);
      return parts.join(" | ");
    }

    function activeWorkRouteLine(progress) {
      const route = progress?.CurrentRoute || progress?.Route || "";
      const reason = progress?.RouteReason || progress?.CurrentRouteReason || "";
      if (!route && !reason) return "";
      return `Route: ${formatProgressValue(route || "unknown")}${reason ? ` | Reason: ${formatProgressValue(reason)}` : ""}`;
    }

    function activeWorkQueueLine(progress) {
      const index = progress?.CurrentQueueIndex;
      const total = progress?.CurrentQueueTotal;
      if ((index === undefined || index === null || index === "") && (total === undefined || total === null || total === "")) return "";
      return `Queue position: ${formatProgressValue(index || 0)} / ${formatProgressValue(total || 0)}`;
    }

    function activeWorkControlLine(progress) {
      const flags = [];
      if (progress?.PauseRequested !== undefined) flags.push(`Pause requested: ${progress.PauseRequested ? "yes" : "no"}`);
      if (progress?.StopRequested !== undefined) flags.push(`Stop requested: ${progress.StopRequested ? "yes" : "no"}`);
      return flags.join(" | ");
    }

    return { activeWorkProgressLine, activeWorkRouteLine, activeWorkQueueLine, activeWorkControlLine };
  }

  window.__progressActiveWorkModule = { createProgressActiveWorkModule };
}());
