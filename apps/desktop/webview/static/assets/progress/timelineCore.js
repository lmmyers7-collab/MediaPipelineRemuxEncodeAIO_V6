(function () {
  function createProgressTimelineCoreModule({
    formatProgressValue,
    progressBarId,
    progressBarStatus,
    progressBarsForStableDisplay,
    progressBarsWithOperatorStop,
    progressBarsWithStaleDisplayHysteresis,
    csvRerunActivityEvidence,
  } = {}) {
      function timelineText(...values) {
        for (const value of values) {
          const text = String(formatProgressValue(value)).trim();
          if (text) return text;
        }
        return "";
      }

      function timelineHasMeaningfulText(value) {
        const text = String(value || "").trim().toLowerCase();
        return Boolean(text) && !["n/a", "none", "not reported", "unknown"].includes(text);
      }

      function timelineMeaningfulText(...values) {
        for (const value of values) {
          const text = timelineText(value);
          if (timelineHasMeaningfulText(text)) return text;
        }
        return "";
      }

      function timelineLooksIdleWaiting(value) {
        const text = String(value || "").trim().toLowerCase();
        return !text
          || /^idle\b/.test(text)
          || text.includes("waiting for next item")
          || text.includes("no active work");
      }

      function timelineBarById(bars = [], ...ids) {
        const wanted = new Set(ids.map((id) => String(id || "").toLowerCase()));
        return (Array.isArray(bars) ? bars : []).find((bar) => wanted.has(progressBarId(bar))) || null;
      }

      function timelineBarMatching(bars = [], predicate = () => false) {
        return (Array.isArray(bars) ? bars : []).find((bar) => predicate(bar)) || null;
      }

      function runTimelineBarStatus(bar) {
        if (!bar) return "";
        const status = progressBarStatus(bar);
        if (bar.stale) return "review";
        if (["blocked", "failed", "error"].includes(status)) return "blocked";
        if (["warning", "review", "stale"].includes(status)) return "review";
        if (["active", "running", "processing"].includes(status)) return "active";
        if (["complete", "completed", "ok", "success"].includes(status)) return "complete";
        if (["pending", "idle", "empty"].includes(status)) return "pending";
        return status || "unknown";
      }

      function normalizeRunTimelineStatus(status) {
        const value = String(status || "").toLowerCase();
        if (["blocked", "failed", "error"].includes(value)) return "blocked";
        if (["warning", "review", "stale", "unknown"].includes(value)) return "review";
        if (["active", "running", "processing"].includes(value)) return "active";
        if (["complete", "completed", "ok", "success"].includes(value)) return "complete";
        if (["skipped", "empty"].includes(value)) return "pending";
        return value || "pending";
      }

      function runTimelineItem({ id, label, status = "pending", detail = "", bar = null, source = "", evidence = "" }) {
        const normalized = normalizeRunTimelineStatus(status || runTimelineBarStatus(bar));
        return {
          id,
          label,
          status: normalized,
          detail: String(detail || "").trim(),
          bar,
          source: String(source || bar?.source || "").trim(),
          evidence: String(evidence || "").trim(),
          current: false,
          next: false,
        };
      }

      function runTimelineProgressContext(context = {}) {
        const source = context && typeof context === "object" && !Array.isArray(context) ? context : {};
        const snapshot = source.snapshot && typeof source.snapshot === "object"
          ? source.snapshot
          : (source.progress || Array.isArray(source.progress_bars) ? source : null);
        const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
        const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
        const rawBars = Array.isArray(source.bars)
          ? source.bars
          : (Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars : []);
        const bars = source.stableBars === true
          ? rawBars.filter(Boolean)
          : progressBarsForStableDisplay(
            progressBarsWithOperatorStop(progressBarsWithStaleDisplayHysteresis(rawBars, snapshot), snapshot),
            snapshot,
          );
        const csvRerun = csvRerunActivityEvidence({
          snapshot,
          diagnostics: source.diagnostics || null,
          closeReadiness: source.closeReadiness || null,
          stdoutTail: source.stdoutTail || null,
        });
        const stage = timelineText(currentWork.current_stage_label, currentWork.phase_label, progress.CurrentStage, progress.Status);
        const stageLower = stage.toLowerCase();
        const route = timelineText(progress.CurrentRoute, progress.Route, currentWork.route_label);
        const routeLower = route.toLowerCase();
        const file = timelineMeaningfulText(currentWork.item_label, progress.CurrentFileDisplay, progress.CurrentFile, progress.InputFile);
        const queueTotal = Number(progress.CurrentQueueTotal ?? snapshot?.counts?.queue_total ?? 0);
        const queueIndex = Number(progress.CurrentQueueIndex ?? snapshot?.counts?.queue_index ?? 0);
        const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
        const hasSnapshotEvidence = Boolean(
          (snapshot && Object.keys(snapshot).length)
          || bars.length
          || Object.keys(progress).length
          || csvRerun.hasEvidence
        );
        return {
          ...source,
          snapshot,
          progress,
          currentWork,
          bars,
          csvRerun,
          stage,
          stageLower,
          route,
          routeLower,
          file,
          queueIndex: Number.isFinite(queueIndex) ? queueIndex : 0,
          queueTotal: Number.isFinite(queueTotal) ? queueTotal : 0,
          events,
          hasSnapshotEvidence,
        };
      }

      function stageMentions(stageLower, ...needles) {
        return needles.some((needle) => stageLower.includes(String(needle).toLowerCase()));
      }

      function publishOrParkBar(bars = []) {
        return timelineBarMatching(bars, (bar) => {
          const id = progressBarId(bar);
          return id === "publish_copy" && runTimelineBarStatus(bar) === "active";
        })
          || timelineBarById(bars, "publish_output")
          || timelineBarById(bars, "publish_copy")
          || timelineBarById(bars, "pending_drain");
      }

      function runTimelinePublishStatus(bar, progress = {}) {
        if (!bar) {
          return timelineText(progress.PushState, progress.SidecarState) ? "active" : "pending";
        }
        const id = progressBarId(bar);
        const status = runTimelineBarStatus(bar);
        if (id === "pending_drain") return status === "blocked" ? "blocked" : "review";
        return status;
      }

      function runTimelineCompletionStatus({ progress = {}, events = [], runTotalBar = null, publishBar = null }) {
        const statusText = timelineText(progress.Status, progress.CurrentStage).toLowerCase();
        const failed = /\b(failed|error|aborted)\b/.test(statusText)
          || events.some((event) => /\b(failed|error|aborted)\b/i.test(timelineText(event?.status, event?.data?.completion_status, event?.data?.error_code)));
        if (failed) return "blocked";
        const stopped = /\b(stopped|stop requested)\b/.test(statusText)
          || events.some((event) => /\b(stopped|stop_requested)\b/i.test(timelineText(event?.status, event?.data?.completion_status, event?.data?.error_code)));
        if (stopped) return "review";
        const completedEvent = events.some((event) => String(event?.event_type || event?.type || "").toLowerCase() === "job_completed");
        if (completedEvent || runTimelineBarStatus(runTotalBar) === "complete" || runTimelineBarStatus(publishBar) === "complete") return "complete";
        return "pending";
      }

      function runTimelineMarkFocus(items = [], hasSnapshotEvidence = false) {
        items.forEach((item) => {
          item.current = false;
          item.next = false;
        });
        if (!hasSnapshotEvidence || !items.length || items.every((item) => item.status === "complete")) return items;
        const currentIndex = items.findIndex((item) => ["blocked", "review", "active"].includes(item.status));
        const fallbackIndex = items.findIndex((item) => item.status === "pending");
        const index = currentIndex >= 0 ? currentIndex : fallbackIndex;
        if (index < 0) return items;
        items[index].current = true;
        const nextIndex = items.findIndex((item, itemIndex) => itemIndex > index && item.status !== "complete");
        if (nextIndex >= 0) items[nextIndex].next = true;
        return items;
      }

      function csvRerunCompletionSummary(snapshot = null) {
        const summary = snapshot?.csv_rerun_summary;
        if (!summary || typeof summary !== "object" || Array.isArray(summary)) return null;
        if (summary.evidence_authority !== "backend_manifest" || summary.terminal !== true) return null;
        return summary;
      }

      function csvRerunCompletionTimelineItems(summary = {}) {
        const complete = summary.display_state === "ok";
        return [runTimelineItem({
          id: "csv_rerun_completion",
          label: String(summary.display_label || "CSV rerun complete"),
          status: complete ? "complete" : "review",
          detail: String(summary.detail || "Backend manifest reports this CSV rerun has reached a terminal state."),
          evidence: String(summary.historical_evidence_note || "Historical progress evidence is available for review."),
        })];
      }

    return {
      timelineText,
      timelineHasMeaningfulText,
      timelineMeaningfulText,
      timelineLooksIdleWaiting,
      timelineBarById,
      timelineBarMatching,
      runTimelineBarStatus,
      normalizeRunTimelineStatus,
      runTimelineItem,
      runTimelineProgressContext,
      stageMentions,
      publishOrParkBar,
      runTimelinePublishStatus,
      runTimelineCompletionStatus,
      runTimelineMarkFocus,
      csvRerunCompletionSummary,
      csvRerunCompletionTimelineItems,
    };
  }

  window.__progressTimelineCoreModule = { createProgressTimelineCoreModule };
})();
