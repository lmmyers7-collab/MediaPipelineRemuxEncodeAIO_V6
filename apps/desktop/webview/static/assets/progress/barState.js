(function () {
  function createProgressBarStateModule() {
    const STALE_DISPLAY_CONFIRMATION_COUNT = 2;
    const progressStaleDisplayCounts = new Map();
    let progressStaleDisplayItemKey = "";
    const progressDisplayPercentCache = new Map();
    let progressDisplayPercentItemKey = "";

      function setProgressPanelStatus(id, message, state) {
        if (typeof setPanelStatus === "function") return setPanelStatus(id, message, state);
        if (typeof setTextState === "function") {
          setTextState(id, message, state);
          return state || "";
        }
        if (typeof setText === "function") setText(id, message);
        return state || "";
      }

      function progressBarStatusLabel(bar) {
        const status = String(bar?.status || "unknown").trim();
        const mode = String(bar?.mode || "determinate").trim();
        const percent = bar?.percent;
        if (mode === "indeterminate") return status === "active" ? `${status} · running` : status;
        if (percent === undefined || percent === null || percent === "") return status;
        const value = Number(percent);
        if (!Number.isFinite(value)) return status;
        return `${status} · ${Math.max(0, Math.min(100, value)).toFixed(value % 1 ? 1 : 0)}%`;
      }

      function progressBarPercent(bar) {
        const value = Number(bar?.percent);
        if (!Number.isFinite(value)) return 0;
        return Math.max(0, Math.min(100, value));
      }

      function formatProgressUpdatedAt(value) {
        if (!value) return "";
        if (value instanceof Date && !Number.isNaN(value.getTime())) {
          const year = value.getFullYear();
          const month = String(value.getMonth() + 1).padStart(2, "0");
          const day = String(value.getDate()).padStart(2, "0");
          const hours = String(value.getHours()).padStart(2, "0");
          const minutes = String(value.getMinutes()).padStart(2, "0");
          const seconds = String(value.getSeconds()).padStart(2, "0");
          return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        }
        const text = String(value).trim();
        const match = text.match(/^(\d{4}-\d{2}-\d{2})[T\s]+(\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/i);
        if (match) return `${match[1]} ${match[2]}`;
        return text;
      }

      const homeProgressTimelineGroups = [
        { key: "primary", label: "Active work", ids: ["current_stage", "run_total"] },
        { key: "audio", label: "Audio", ids: ["audio_track"] },
        { key: "publish", label: "Publish", ids: ["publish_output", "publish_copy"] },
        { key: "subtitles", label: "Subtitles", ids: [] },
        { key: "completed", label: "Completed", ids: [] },
        { key: "other", label: "Other checks", ids: [] },
      ];

      function progressBarId(bar) {
        return String(bar?.id || "").toLowerCase();
      }

      function progressBarStatus(bar) {
        return String(bar?.status || "unknown").toLowerCase();
      }

      function progressBarMode(bar) {
        return String(bar?.mode || "determinate").toLowerCase();
      }

      const pendingDrainCompactLabels = {
        publish_output: "Publish",
        publish_copy: "Copy output",
        pending_drain: "Drain queue",
      };

      const pendingDrainCompactStepLabels = {
        "copy completed output": "Copy output",
        "write sidecars": "Sidecars",
        "reveal output": "Reveal",
        finalize: "Finish",
      };

      function progressUsePendingDrainCompactText(options = {}) {
        return Boolean(options && (options.compact === "pendingDrain" || options.compactPendingDrain));
      }

      function progressBarDisplayLabel(bar, options = {}) {
        const fallback = bar?.label || bar?.id || "Progress";
        if (!progressUsePendingDrainCompactText(options)) return fallback;
        return pendingDrainCompactLabels[progressBarId(bar)] || fallback;
      }

      function progressStepDisplayLabel(step, options = {}) {
        const label = String(step?.label || step?.id || "Step");
        if (!progressUsePendingDrainCompactText(options)) return label;
        return pendingDrainCompactStepLabels[label.toLowerCase()] || label;
      }

      function progressBarDisplayStatusLabel(bar, options = {}) {
        if (!progressUsePendingDrainCompactText(options)) return progressBarStatusLabel(bar);
        const value = Number(bar?.percent);
        if (Number.isFinite(value)) {
          const bounded = Math.max(0, Math.min(100, value));
          return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
        }
        const status = progressBarStatus(bar);
        if (progressBarMode(bar) === "indeterminate" && status === "active") return "running";
        if (status === "complete") return "done";
        return status;
      }

      function progressSnapshotItemKey(snapshot = null) {
        const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
        const file = progress.CurrentFilePath
          || progress.CurrentFileDisplay
          || progress.CurrentFile
          || progress.InputFile
          || "";
        return [
          file,
          progress.CurrentQueueIndex ?? "",
          progress.CurrentQueueTotal ?? "",
        ].map((part) => String(part || "").trim()).join("|");
      }

      function resetProgressStaleDisplayCountsForItem(snapshot = null) {
        const itemKey = progressSnapshotItemKey(snapshot);
        if (itemKey === progressStaleDisplayItemKey) return;
        progressStaleDisplayCounts.clear();
        progressStaleDisplayItemKey = itemKey;
      }

      function resetProgressDisplayPercentForItem(snapshot = null) {
        const itemKey = progressSnapshotItemKey(snapshot);
        if (itemKey === progressDisplayPercentItemKey) return;
        progressDisplayPercentCache.clear();
        progressDisplayPercentItemKey = itemKey;
      }

      function progressBarStaleDisplayKey(bar, snapshot = null) {
        return [
          progressSnapshotItemKey(snapshot),
          progressBarId(bar) || String(bar?.label || "progress").trim().toLowerCase(),
        ].join("|");
      }

      function progressBarWithStaleDisplayHysteresis(bar, snapshot = null) {
        if (!bar || typeof bar !== "object") return bar;
        const key = progressBarStaleDisplayKey(bar, snapshot);
        if (!bar.stale) {
          progressStaleDisplayCounts.delete(key);
          return bar;
        }
        const count = (progressStaleDisplayCounts.get(key) || 0) + 1;
        progressStaleDisplayCounts.set(key, count);
        if (count >= STALE_DISPLAY_CONFIRMATION_COUNT) return bar;
        const displayBar = { ...bar, stale: false };
        if (progressBarStatus(displayBar) === "warning") displayBar.status = "active";
        return displayBar;
      }

      function progressBarsWithStaleDisplayHysteresis(bars = [], snapshot = null) {
        resetProgressStaleDisplayCountsForItem(snapshot);
        const items = Array.isArray(bars) ? bars.filter(Boolean) : [];
        if (!items.length) {
          progressStaleDisplayCounts.clear();
          return items;
        }
        if (!items.some((bar) => Boolean(bar?.stale))) {
          progressStaleDisplayCounts.clear();
          return items;
        }
        const seenKeys = new Set(items.map((bar) => progressBarStaleDisplayKey(bar, snapshot)));
        for (const key of progressStaleDisplayCounts.keys()) {
          if (!seenKeys.has(key)) progressStaleDisplayCounts.delete(key);
        }
        return items.map((bar) => progressBarWithStaleDisplayHysteresis(bar, snapshot));
      }

      function progressDisplayPercentKey(bar, snapshot = null) {
        const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
        return [
          progressSnapshotItemKey(snapshot),
          progressBarId(bar) || String(bar?.label || "progress").trim().toLowerCase(),
          progress.CurrentStage || "",
          progress.CurrentRoute || progress.Route || "",
        ].map((part) => String(part || "").trim().toLowerCase()).join("|");
      }

      function progressBarForStableDisplay(bar, snapshot = null) {
        if (!bar || typeof bar !== "object") return bar;
        resetProgressDisplayPercentForItem(snapshot);
        const mode = progressBarMode(bar);
        if (mode === "indeterminate") return bar;
        const rawPercent = progressBarPercent(bar);
        const status = progressBarStatus(bar);
        const activeStatus = ["active", "running", "publishing", "warning", "unknown"].includes(status);
        const key = progressDisplayPercentKey(bar, snapshot);
        if (!activeStatus || status === "complete" || rawPercent >= 100) {
          progressDisplayPercentCache.set(key, rawPercent);
          return bar;
        }
        const previous = progressDisplayPercentCache.get(key);
        if (Number.isFinite(previous) && rawPercent + 0.05 < previous) {
          const held = { ...bar, percent: previous };
          const rawText = rawPercent % 1 === 0 ? `${rawPercent.toFixed(0)}%` : `${rawPercent.toFixed(1)}%`;
          const heldText = previous % 1 === 0 ? `${previous.toFixed(0)}%` : `${previous.toFixed(1)}%`;
          const detail = String(bar.detail || "").trim();
          held.detail = [
            detail,
            `backend percent now ${rawText}; display held at ${heldText} to avoid backward progress`,
          ].filter(Boolean).join(" | ");
          return held;
        }
        progressDisplayPercentCache.set(key, Math.max(rawPercent, Number.isFinite(previous) ? previous : rawPercent));
        return bar;
      }

      function progressBarsForStableDisplay(bars = [], snapshot = null) {
        const items = Array.isArray(bars) ? bars.filter(Boolean) : [];
        if (!items.length) {
          progressDisplayPercentCache.clear();
          return items;
        }
        return items.map((bar) => progressBarForStableDisplay(bar, snapshot));
      }

      function progressBarPercentLabel(bar) {
        const rawPercent = bar?.percent;
        const value = Number(rawPercent);
        if (Number.isFinite(value)) {
          const bounded = Math.max(0, Math.min(100, value));
          return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
        }
        const status = progressBarStatus(bar);
        if (progressBarMode(bar) === "indeterminate" && status === "active") return "running";
        return status;
      }

    return {
      setProgressPanelStatus,
      progressBarStatusLabel,
      progressBarPercent,
      formatProgressUpdatedAt,
      homeProgressTimelineGroups,
      progressBarId,
      progressBarStatus,
      progressBarMode,
      progressUsePendingDrainCompactText,
      progressBarDisplayLabel,
      progressStepDisplayLabel,
      progressBarDisplayStatusLabel,
      progressSnapshotItemKey,
      resetProgressStaleDisplayCountsForItem,
      resetProgressDisplayPercentForItem,
      progressBarWithStaleDisplayHysteresis,
      progressBarsWithStaleDisplayHysteresis,
      progressBarForStableDisplay,
      progressBarsForStableDisplay,
      progressBarPercentLabel,
    };
  }

  window.__progressBarStateModule = { createProgressBarStateModule };
})();
