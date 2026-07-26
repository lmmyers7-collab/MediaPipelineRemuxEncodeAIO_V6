(function () {
  function createProgressTimelineViewModule({
    formatProgressValue,
    progressBarId,
    progressBarPercent,
    progressBarStatusLabel,
    progressBarDisplayLabel,
    progressBarDisplayStatusLabel,
    progressBarsForStableDisplay,
    progressBarsWithOperatorStop,
    progressBarsWithStaleDisplayHysteresis,
    progressBarDetailPieces,
    progressStepItems,
    createProgressTrack,
    createProgressStepList,
    progressTimelineTokens,
    setProgressPanelStatus,
    byId,
    csvRerunCompletionSummary,
    csvRerunCompletionTimelineItems,
    csvRerunTerminalLine,
    csvRerunTimelineDetail,
    csvRerunTimelineEvidenceLine,
    timelineText,
    timelineHasMeaningfulText,
    timelineLooksIdleWaiting,
    timelineBarById,
    timelineBarMatching,
    runTimelineBarStatus,
    runTimelineItem,
    runTimelineProgressContext,
    stageMentions,
    publishOrParkBar,
    runTimelinePublishStatus,
    runTimelineCompletionStatus,
    runTimelineMarkFocus,
    latestEventLine,
  } = {}) {
      function runTimelineItems(context = {}) {
        const completion = csvRerunCompletionSummary(context?.snapshot);
        if (completion) return csvRerunCompletionTimelineItems(completion);
        const source = runTimelineProgressContext(context);
        const {
          bars,
          progress,
          csvRerun,
          stage,
          stageLower,
          route,
          file,
          queueIndex,
          queueTotal,
          events,
          currentWork,
        } = source;
        const currentStageBar = timelineBarById(bars, "current_stage");
        const runTotalBar = timelineBarById(bars, "run_total");
        const audioBar = timelineBarById(bars, "audio_track") || timelineBarMatching(bars, (bar) => String(bar?.label || "").toLowerCase().includes("audio"));
        const subtitleBar = timelineBarById(bars, "subtitle_track") || timelineBarMatching(bars, (bar) => {
          const id = progressBarId(bar);
          const label = String(bar?.label || "").toLowerCase();
          return id.startsWith("subtitle") || label.includes("subtitle");
        });
        const publishBar = publishOrParkBar(bars);
        const explicitTranscodeStages = new Set([
          "encode", "encoding", "encode_cpu", "encode cpu", "remux", "remux_av", "remux av", "transcode", "transcoding",
        ]);
        const encodeActive = explicitTranscodeStages.has(stageLower);
        const hasRoute = timelineHasMeaningfulText(route);
        const hasFile = timelineHasMeaningfulText(file);
        const backendWorkSummary = timelineText(currentWork.summary_label, currentWork.latest_evidence_label, currentWork.current_stage_label);
        const backendWorkEvidence = timelineText(currentWork.latest_evidence_label, currentWork.missing_evidence_label);
        const backendWorkLower = backendWorkSummary.toLowerCase();
        const backendSpecificNonCsvWork = Boolean(backendWorkSummary)
          && !backendWorkLower.includes("csv")
          && !timelineLooksIdleWaiting(backendWorkSummary);
        const routeDisplay = hasRoute ? formatProgressValue(route) : "";
        const routeDecisionLabel = hasRoute ? `Route selected: ${routeDisplay}` : "Route decision pending";
        const routeDecisionDetail = hasRoute
          ? `${routeDisplay} route${progress.RouteReason ? ` | ${formatProgressValue(progress.RouteReason)}` : ""}`
          : "No backend route is selected yet; waiting for encode/remux decision evidence.";
        const routeLabel = "Encode or remux";
        const queueDetail = queueTotal > 0
          ? `Item ${Math.max(0, queueIndex)} of ${queueTotal}${file ? `: ${file}` : ""}`
          : (file ? `Current item: ${file}` : "Waiting for backend queue evidence.");

        const items = [];
        if (csvRerun.hasEvidence) {
          items.push(runTimelineItem({
            id: "csv_import",
            label: "CSV import",
            status: backendSpecificNonCsvWork
              ? "complete"
              : csvRerun.isActive || csvRerun.currentImport ? "active" : csvRerun.latestLine && csvRerunTerminalLine(csvRerun.latestLine) ? "complete" : "review",
            detail: csvRerunTimelineDetail(csvRerun, backendWorkEvidence),
            evidence: csvRerunTimelineEvidenceLine(csvRerun, backendWorkEvidence),
          }));
        }
        items.push(
          runTimelineItem({
            id: "queue_item",
            label: "Queue item",
            status: hasFile || queueTotal > 0 || runTimelineBarStatus(runTotalBar) === "complete" ? "complete" : runTimelineBarStatus(runTotalBar) || "pending",
            detail: queueDetail,
            bar: runTotalBar,
          }),
          runTimelineItem({
            id: "copy_to_scratch",
            label: "Copy to scratch",
            status: csvRerun.currentImport || stageMentions(stageLower, "copy", "scratch", "stage copy", "staged")
              ? "active"
              : "unknown",
            detail: csvRerun.currentImport
              ? `Copying staged CSV source ${csvRerun.currentImport} to scratch; source media remains unchanged.`
              : "Scratch-copy state is unknown until explicit backend copy evidence is available.",
          }),
          runTimelineItem({
            id: "route_selected",
            label: routeDecisionLabel,
            status: hasRoute ? "complete" : hasFile ? "active" : "pending",
            detail: routeDecisionDetail,
          }),
          runTimelineItem({
            id: "audio_policy",
            label: "Audio policy",
            status: audioBar ? runTimelineBarStatus(audioBar) : "unknown",
            detail: audioBar?.detail || "Audio evidence unknown; no pending state is inferred.",
            bar: audioBar,
          }),
          runTimelineItem({
            id: "subtitle_work",
            label: "Subtitle work",
            status: subtitleBar ? runTimelineBarStatus(subtitleBar) : backendWorkLower.includes("subtitle") ? "active" : "unknown",
            detail: backendWorkLower.includes("subtitle") ? backendWorkSummary : subtitleBar?.detail || "Subtitle evidence unknown; no pending state is inferred.",
            bar: subtitleBar,
            evidence: backendWorkLower.includes("subtitle") ? backendWorkEvidence : "",
          }),
          runTimelineItem({
            id: "encode_remux",
            label: routeLabel,
            status: encodeActive ? "active" : "unknown",
            detail: encodeActive
              ? [stage || routeLabel, progress.CurrentStagePercent !== undefined && progress.CurrentStagePercent !== null ? `${formatProgressValue(progress.CurrentStagePercent)}%` : ""].filter(Boolean).join(" | ")
              : "Encode/remux state is unknown until the backend explicitly reports that stage; route text is not stage authority.",
            bar: encodeActive ? currentStageBar : null,
          }),
          runTimelineItem({
            id: "publish_or_park",
            label: "Publish or park",
            status: runTimelinePublishStatus(publishBar, progress),
            detail: publishBar?.detail || timelineText(progress.PushState, progress.SidecarState) || "Waiting for publish, park, or pending-drain evidence.",
            bar: publishBar,
          }),
          runTimelineItem({
            id: "run_evidence",
            label: "Run evidence",
            status: runTimelineCompletionStatus({ progress, events, runTotalBar, publishBar }),
            detail: events.length
              ? latestEventLine(null, { recent_events: events })
              : "Waiting for backend completion, review, or close-readiness evidence.",
          }),
        );
        return runTimelineMarkFocus(items, source.hasSnapshotEvidence);
      }

      function runTimelinePanelStatus(items = [], context = {}) {
        const source = runTimelineProgressContext(context);
        if (!source.hasSnapshotEvidence) return { message: "Waiting for backend snapshot", state: "empty" };
        if (!items.length) return { message: "Waiting for backend snapshot", state: "empty" };
        if (items.every((item) => item.status === "complete")) return { message: "Complete", state: "ready" };
        const current = items.find((item) => item.current) || items.find((item) => ["blocked", "review", "active"].includes(item.status));
        if (!current) return { message: "Waiting for backend snapshot", state: "empty" };
        if (current.status === "blocked") return { message: `Review: ${current.label}`, state: "blocked" };
        if (current.status === "review") return { message: `Review: ${current.label}`, state: "warning" };
        const next = items.find((item) => item.next);
        return { message: `Current: ${current.label}${next ? ` · Next: ${next.label}` : ""}`, state: "running" };
      }

      function createRunTimelineMeta(item, snapshot = null, diagnostics = null) {
        const metadata = document.createElement("div");
        metadata.className = "run-timeline-meta";
        const tokens = item.bar ? progressTimelineTokens(item.bar, snapshot, diagnostics) : [];
        if (item.evidence) tokens.push({ kind: "source", text: item.evidence });
        tokens.slice(0, item.current ? 6 : 3).forEach((token) => {
          const node = document.createElement("span");
          node.className = `run-timeline-token run-timeline-token-${token.kind || "detail"}`;
          node.textContent = token.text;
          if (token.title) node.title = token.title;
          metadata.appendChild(node);
        });
        return metadata;
      }

      function renderRunTimelineItem(item, index, context = {}) {
        const row = document.createElement("li");
        row.className = "run-timeline-item";
        row.dataset.status = item.status;
        row.dataset.current = item.current ? "true" : "false";
        row.dataset.next = item.next ? "true" : "false";
        if (item.current) row.setAttribute("aria-current", "step");

        const rail = document.createElement("span");
        rail.className = "run-timeline-rail";
        rail.setAttribute("aria-hidden", "true");
        const dot = document.createElement("span");
        dot.className = "run-timeline-dot";
        rail.appendChild(dot);

        const card = document.createElement("div");
        card.className = "run-timeline-card";
        const header = document.createElement("div");
        header.className = "run-timeline-header";
        const title = document.createElement("span");
        title.className = "run-timeline-title";
        title.textContent = item.label;
        const state = document.createElement("span");
        state.className = "run-timeline-state";
        state.textContent = item.current ? "current" : item.next ? "next" : item.status;
        header.append(title, state);

        const detail = document.createElement("p");
        detail.className = "run-timeline-detail";
        detail.textContent = item.detail || (item.current ? "Backend evidence is loading for this step." : "Waiting for backend evidence.");
        card.append(header, detail);
        if (item.current && item.bar) {
          card.appendChild(createProgressTrack(item.bar));
          const steps = createProgressStepList(item.bar);
          if (steps) card.appendChild(steps);
        }
        const meta = createRunTimelineMeta(item, context.snapshot, context.diagnostics);
        if (meta.children.length) card.appendChild(meta);
        row.append(rail, card);
        if (typeof row.style?.setProperty === "function") {
          row.style.setProperty("--run-timeline-index", String(index + 1));
        }
        return row;
      }

      function renderRunTimelineEvidence(bars = [], snapshot = null) {
        const details = document.createElement("details");
        details.className = "run-timeline-evidence";
        const summary = document.createElement("summary");
        summary.textContent = `Raw backend progress (${bars.length} ${bars.length === 1 ? "bar" : "bars"})`;
        const body = document.createElement("div");
        body.className = "run-timeline-evidence-body";
        details.append(summary, body);
        renderProgressBarsInto(body, bars, snapshot, "No raw backend progress bars loaded.");
        return details;
      }

      function renderHomeProgressTimeline(bars = [], snapshot = null, context = {}) {
        const container = byId("progress-bar-list");
        if (!container) return;
        const stableBars = progressBarsForStableDisplay(
          progressBarsWithOperatorStop(progressBarsWithStaleDisplayHysteresis(bars, snapshot), snapshot),
          snapshot,
        );
        container.classList.add("progress-timeline-list");
        container.classList.add("run-timeline-list");
        container.replaceChildren();
        const timelineContext = { ...context, bars: stableBars, snapshot, stableBars: true };
        const timelineItems = runTimelineItems(timelineContext);
        const status = runTimelinePanelStatus(timelineItems, timelineContext);
        setProgressPanelStatus("progress-detail-status", status.message, status.state);
        const list = document.createElement("ol");
        list.className = "run-timeline";
        timelineItems.forEach((item, index) => list.appendChild(renderRunTimelineItem(item, index, timelineContext)));
        container.appendChild(list);
        container.appendChild(renderRunTimelineEvidence(stableBars, snapshot));
      }

      function renderProgressBarsInto(containerOrId, bars = [], snapshot = null, emptyText = "", options = {}) {
        const container = typeof containerOrId === "string" ? byId(containerOrId) : containerOrId;
        if (!container) return;
        const items = progressBarsForStableDisplay(Array.isArray(bars) ? bars.filter(Boolean) : [], snapshot);
        container.replaceChildren();
        if (!items.length) {
          const empty = document.createElement("p");
          empty.className = "note";
          empty.textContent = emptyText || (snapshot?.progress || snapshot?.audit_progress
            ? "No active run progress from backend yet."
            : "Waiting for backend progress snapshot.");
          container.appendChild(empty);
          return;
        }
        items.forEach((bar) => {
          const mode = String(bar.mode || "determinate").toLowerCase();
          const status = String(bar.status || "unknown").toLowerCase();
          const row = document.createElement("div");
          row.className = "progress-bar-row";
          row.dataset.status = status;
          row.dataset.mode = mode;

          const header = document.createElement("div");
          header.className = "progress-bar-header";
          const label = document.createElement("span");
          label.className = "progress-bar-label";
          label.textContent = progressBarDisplayLabel(bar, options);
          const value = document.createElement("span");
          value.className = "progress-bar-value";
          value.textContent = progressBarDisplayStatusLabel(bar, options);
          header.append(label, value);

          const track = document.createElement("div");
          track.className = "progress-track";
          track.setAttribute("role", "progressbar");
          track.setAttribute("aria-label", progressBarDisplayLabel(bar, options));
          track.setAttribute("aria-valuetext", progressBarStatusLabel(bar));
          if (mode === "determinate" || mode === "stepped") {
            const percent = progressBarPercent(bar);
            track.setAttribute("aria-valuemin", "0");
            track.setAttribute("aria-valuemax", "100");
            track.setAttribute("aria-valuenow", String(Math.round(percent)));
          }
          const fill = document.createElement("div");
          fill.className = "progress-fill";
          if (mode !== "indeterminate") fill.style.width = `${progressBarPercent(bar)}%`;
          track.appendChild(fill);

          const detail = document.createElement("div");
          detail.className = "progress-bar-detail";
          const pieces = progressBarDetailPieces(bar, snapshot, null, options);
          detail.textContent = pieces.join(" · ") || "No progress detail reported.";

          const steps = createProgressStepList(bar, options);
          row.append(header, track);
          if (steps) row.appendChild(steps);
          row.appendChild(detail);
          container.appendChild(row);
        });
      }

    function renderProgressBars(bars = [], snapshot = null, context = {}) {
      renderHomeProgressTimeline(bars, snapshot, context);
    }

    return {
      runTimelineItems,
      runTimelinePanelStatus,
      renderHomeProgressTimeline,
      renderProgressBarsInto,
      renderProgressBars,
    };
  }

  window.__progressTimelineViewModule = { createProgressTimelineViewModule };
})();
