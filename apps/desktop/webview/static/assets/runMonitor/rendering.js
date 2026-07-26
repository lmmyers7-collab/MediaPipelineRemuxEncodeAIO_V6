(function () {
  "use strict";

  let byId;
  let setText;
  let text;
  let array;
  let object;
  let humanize;
  let stageLabel;
  let formatTimestamp;
  let progressLabel;
  let evidenceLabel;
  let routeDisplay;
  let routeUnavailableLabel;
  let itemEvidenceAllowed;
  let collectionStateLabel;
  let trackTimelineLabel;
  let subtitleStepLabel;
  let subtitleCueLabel;

function appendTechnicalDetails(container, parts) {
    const values = parts.filter(Boolean);
    if (!values.length) return;
    const detail = document.createElement("div");
    detail.className = "run-monitor-technical-detail";
    detail.setAttribute("data-advanced", "");
    detail.textContent = values.join(" · ");
    container.appendChild(detail);
  }

function formatBytes(value) {
    if (value === null || value === undefined || value === "") return "";
    const bytes = Number(value);
    if (!Number.isFinite(bytes) || bytes < 0) return "";
    if (bytes < 1024) return `${bytes.toLocaleString()} bytes`;
    const units = ["KiB", "MiB", "GiB", "TiB"];
    let amount = bytes;
    let unit = "bytes";
    for (const candidate of units) {
      amount /= 1024;
      unit = candidate;
      if (amount < 1024 || candidate === units[units.length - 1]) break;
    }
    const digits = amount >= 100 ? 0 : amount >= 10 ? 1 : 2;
    return `${amount.toLocaleString([], { maximumFractionDigits: digits })} ${unit}`;
  }

function renderOutcome(item, freshnessState) {
    const container = byId("run-monitor-file-outcome");
    if (!container) return;
    container.replaceChildren();
    if (!text(item?.job_id)) {
      const heading = document.createElement("strong");
      heading.textContent = "No file selected";
      container.appendChild(heading);
      return;
    }
    if (!itemEvidenceAllowed(item, freshnessState)) {
      const heading = document.createElement("strong");
      heading.textContent = "Current outcome unavailable";
      const detail = document.createElement("span");
      detail.textContent = `Freshness is ${humanize(freshnessState).toLowerCase()}.`;
      container.append(heading, detail);
      return;
    }
    const output = object(item?.output);
    const outputState = text(output.state);
    const lifecycle = text(item?.lifecycle_state, "unknown");
    const primaryState = outputState && outputState !== "unknown" ? outputState : lifecycle;
    const heading = document.createElement("strong");
    heading.textContent = humanize(primaryState);
    const facts = [
      text(output.verification_state) && text(output.verification_state) !== "unknown"
        ? `Verification ${humanize(output.verification_state).toLowerCase()}`
        : "",
      formatBytes(output.size_bytes),
    ];
    const audioTracks = array(item?.audio?.tracks);
    const subtitleTracks = array(item?.subtitles?.tracks);
    if (audioTracks.length) facts.push(`Audio ${audioTracks.length} track${audioTracks.length === 1 ? "" : "s"}`);
    if (subtitleTracks.length) facts.push(`Subtitles ${subtitleTracks.length} track${subtitleTracks.length === 1 ? "" : "s"}`);
    container.appendChild(heading);
    facts.filter(Boolean).forEach((value) => {
      const fact = document.createElement("span");
      fact.textContent = value;
      container.appendChild(fact);
    });
  }

function renderRouteSummary(item, freshnessState) {
    const container = byId("run-monitor-route-summary");
    if (!container) return;
    container.replaceChildren();
    if (!text(item?.job_id)) {
      container.textContent = "Select a file to see its backend route decision.";
      return;
    }
    if (!itemEvidenceAllowed(item, freshnessState)) {
      container.textContent = `Route claims suppressed · ${humanize(freshnessState)}`;
      return;
    }
    const routes = [
      routeDisplay(item?.planned_route, "Planned", "Planned reason"),
      routeDisplay(item?.executed_route, "Executed", "Executed reason"),
      routeDisplay(item?.final_route, "Final", "Final reason"),
    ];
    const trail = document.createElement("div");
    trail.className = "run-monitor-route-trail";
    routes.forEach((route, index) => {
      const step = document.createElement("span");
      step.className = "run-monitor-route-step";
      step.dataset.state = route.state;
      const label = route.label.replace(/\s+route$/i, "");
      step.textContent = `${label} ${route.value ? humanize(route.value) : routeUnavailableLabel(route)}`;
      trail.appendChild(step);
      if (index < routes.length - 1) {
        const arrow = document.createElement("span");
        arrow.className = "run-monitor-route-arrow";
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "→";
        trail.appendChild(arrow);
      }
    });
    container.appendChild(trail);
    const [planned, executed, final] = routes;
    let explanation = "";
    if (planned.value && executed.value && planned.value.toLowerCase() !== executed.value.toLowerCase()) {
      explanation = executed.reason;
    } else if (executed.value && final.value && executed.value.toLowerCase() !== final.value.toLowerCase()) {
      explanation = final.reason;
    } else if (!executed.value && planned.value && final.value && planned.value.toLowerCase() !== final.value.toLowerCase()) {
      explanation = final.reason;
    }
    if (explanation) {
      const reason = document.createElement("p");
      reason.textContent = explanation;
      container.appendChild(reason);
    }
  }

function appendRouteCard(container, route) {
    const card = document.createElement("div");
    card.className = "run-monitor-route-card";
    card.dataset.state = route.state;
    const title = document.createElement("strong");
    title.textContent = route.label;
    const value = document.createElement("span");
    value.textContent = route.value || routeUnavailableLabel(route);
    const reasonTitle = document.createElement("span");
    reasonTitle.className = "run-monitor-route-reason-label";
    reasonTitle.textContent = route.reasonLabel;
    const reason = document.createElement("span");
    const reasonText = route.reason || (route.value ? "No reason reported" : routeUnavailableLabel(route));
    reason.textContent = route.reasonCode ? `${reasonText} (${route.reasonCode})` : reasonText;
    const evidence = document.createElement("small");
    evidence.textContent = evidenceLabel(route.evidence);
    card.append(title, value, reasonTitle, reason, evidence);
    container.appendChild(card);
  }

function renderRoutes(item, freshnessState) {
    const container = byId("run-monitor-routes");
    if (!container) return;
    container.replaceChildren();
    if (!itemEvidenceAllowed(item, freshnessState)) {
      const suppressed = document.createElement("p");
      suppressed.textContent = `Route claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}. Use “Last known — not current” for clearly separated historical evidence.`;
      container.appendChild(suppressed);
      return;
    }
    appendRouteCard(container, routeDisplay(item?.planned_route, "Planned route", "Planned reason"));
    appendRouteCard(container, routeDisplay(item?.executed_route, "Executed route", "Executed reason"));
    appendRouteCard(container, routeDisplay(item?.final_route, "Final route", "Final reason"));
  }

function renderStages(item, freshnessState) {
    const summary = byId("run-monitor-stage-summary");
    const container = byId("run-monitor-stage-list");
    if (!container || !summary) return;
    summary.replaceChildren();
    container.replaceChildren();
    if (!itemEvidenceAllowed(item, freshnessState)) {
      const summarySuppressed = document.createElement("li");
      summarySuppressed.textContent = `Current timeline is suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`;
      summary.appendChild(summarySuppressed);
      const suppressed = document.createElement("li");
      suppressed.textContent = `Current timeline is suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`;
      container.appendChild(suppressed);
      return;
    }
    const stages = array(item?.stages);
    if (!stages.length) {
      const summaryEmpty = document.createElement("li");
      summaryEmpty.textContent = "No backend stage ledger loaded.";
      summary.appendChild(summaryEmpty);
      const empty = document.createElement("li");
      empty.textContent = "No backend stage ledger loaded.";
      container.appendChild(empty);
      return;
    }
    const summaryStates = new Set(["active", "blocked", "review", "failed", "unknown"]);
    const planned = routeDisplay(item?.planned_route, "Planned route", "Planned reason");
    const executed = routeDisplay(item?.executed_route, "Executed route", "Executed reason");
    const routeChanged = Boolean(planned.value && executed.value && planned.value.toLowerCase() !== executed.value.toLowerCase());
    const summaryStages = stages.filter((stage) => {
      const state = text(stage.state, "unknown");
      const stageId = text(stage.stage_id);
      return summaryStates.has(state)
        || (stageId === "route_decision" && routeChanged)
        || (stageId === "final_evidence" && state !== "not_started");
    });
    if (!summaryStages.length) {
      const latest = [...stages].reverse().find((stage) => text(stage.state) !== "not_started") || stages[0];
      if (latest) summaryStages.push(latest);
    }
    summaryStages.forEach((stage) => {
      const li = document.createElement("li");
      li.className = "run-monitor-stage-summary-item";
      li.dataset.state = text(stage.state, "unknown");
      const heading = document.createElement("div");
      const label = document.createElement("strong");
      label.textContent = stageLabel(stage.stage_id);
      const state = document.createElement("span");
      state.textContent = humanize(stage.state);
      heading.append(label, state);
      li.appendChild(heading);
      const detailText = text(stage.detail, text(stage.reason_code));
      if (detailText) {
        const detail = document.createElement("p");
        detail.textContent = detailText;
        li.appendChild(detail);
      }
      summary.appendChild(li);
    });
    const summarized = new Set(summaryStages);
    const routineCount = stages.filter((stage) => !summarized.has(stage) && ["completed", "skipped", "not_applicable"].includes(text(stage.state))).length;
    if (routineCount) {
      const count = document.createElement("li");
      count.className = "run-monitor-stage-summary-count";
      count.textContent = `${routineCount} routine stage${routineCount === 1 ? "" : "s"} completed, skipped, or not applicable · full evidence in Advanced`;
      summary.appendChild(count);
    }
    stages.forEach((stage) => {
      const li = document.createElement("li");
      li.className = "run-monitor-stage";
      li.dataset.state = text(stage.state, "unknown");
      if (text(stage.state) === "active") li.setAttribute("aria-current", "step");
      const heading = document.createElement("div");
      heading.className = "run-monitor-stage-heading";
      const label = document.createElement("strong");
      label.textContent = stageLabel(stage.stage_id);
      const stageState = document.createElement("span");
      stageState.className = "run-monitor-stage-state";
      stageState.textContent = humanize(stage.state);
      heading.append(label, stageState);
      const detail = document.createElement("p");
      detail.textContent = text(stage.detail, text(stage.reason_code, "No additional backend detail."));
      const meta = document.createElement("small");
      const progress = progressLabel(stage.progress);
      meta.textContent = [
        progress,
        text(stage.started_at) ? `Started ${formatTimestamp(stage.started_at)}` : "",
        text(stage.updated_at) ? `Updated ${formatTimestamp(stage.updated_at)}` : "",
        text(stage.completed_at) ? `Completed ${formatTimestamp(stage.completed_at)}` : "",
        evidenceLabel(stage.evidence),
      ].filter(Boolean).join(" · ");
      li.append(heading, detail, meta);
      container.appendChild(li);
    });
  }

function collectionEmptyText(kind, collection) {
    const collectionState = text(collection?.state, "unknown");
    if (collectionState === "not_applicable") return `No ${kind} tracks · Not applicable`;
    if (collectionState === "awaiting_evidence") return `Awaiting backend ${kind} evidence`;
    if (collectionState === "unknown") return `${humanize(kind)} evidence unknown`;
    return `No per-track ${kind} evidence reported`;
  }

function appendEmptyTrackRow(body, message) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.dataset.label = "Track evidence";
    cell.textContent = message;
    row.appendChild(cell);
    body.appendChild(row);
  }

function renderAudio(item, freshnessState) {
    const collection = object(item?.audio);
    const tracks = array(collection.tracks);
    const body = byId("run-monitor-audio-body");
    if (!body) return;
    if (!itemEvidenceAllowed(item, freshnessState)) {
      setText("run-monitor-audio-state", `Evidence suppressed · ${humanize(freshnessState)}`);
      body.replaceChildren();
      appendEmptyTrackRow(body, `Current audio-track claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`);
      return;
    }
    setText("run-monitor-audio-state", collectionStateLabel(collection));
    body.replaceChildren();
    if (!tracks.length) {
      appendEmptyTrackRow(body, collectionEmptyText("audio", collection));
      return;
    }
    tracks.forEach((track) => {
      const row = document.createElement("tr");
      row.dataset.state = text(track.state, "unknown");
      const identity = document.createElement("td");
      identity.dataset.label = "Track";
      identity.textContent = [
        `Stream ${Number.isFinite(Number(track.stream_index)) ? track.stream_index : "unknown"}`,
        text(track.language, "language unknown"),
        track.is_default ? "default" : "",
      ].filter(Boolean).join(" · ");
      appendTechnicalDetails(identity, [text(track.track_id) ? `Track ID ${track.track_id}` : ""]);
      const source = document.createElement("td");
      source.dataset.label = "Source";
      source.textContent = [
        text(track.source_codec, "codec unknown"),
        Number(track.source_channels) > 0 ? `${track.source_channels} channels` : "channels unknown",
        text(track.source_layout),
      ].filter(Boolean).join(" · ");
      const outcome = document.createElement("td");
      outcome.dataset.label = "Outcome";
      outcome.textContent = [
        humanize(track.state),
        text(track.planned_action) ? `Plan: ${track.planned_action}` : "",
        text(track.current_action),
        text(track.output_codec) ? `Output ${track.output_codec}` : "",
        Number(track.output_channels) > 0 ? `${track.output_channels} channels` : "",
        text(track.output_layout),
        progressLabel(track.progress),
        text(track.result),
      ].filter(Boolean).join(" · ");
      appendTechnicalDetails(outcome, [
        trackTimelineLabel(track),
        text(track.reason),
        evidenceLabel(track.evidence),
      ]);
      row.append(identity, source, outcome);
      body.appendChild(row);
    });
  }

function subtitleActions(track) {
    const actions = [text(track.planned_action)];
    if (track.preserve === true) actions.push("Preserve original");
    if (track.extract === true) actions.push("Extract");
    if (track.convert === true) actions.push("Convert");
    if (track.ocr === true) actions.push("OCR");
    if (track.write_embedded === true) actions.push("Write embedded");
    if (track.write_sidecar === true) actions.push("Write external sidecar");
    return actions.filter(Boolean).join(" · ") || "Not reported";
  }

function renderSubtitles(item, freshnessState) {
    const collection = object(item?.subtitles);
    const tracks = array(collection.tracks);
    const body = byId("run-monitor-subtitle-body");
    if (!body) return;
    if (!itemEvidenceAllowed(item, freshnessState)) {
      setText("run-monitor-subtitle-state", `Evidence suppressed · ${humanize(freshnessState)}`);
      body.replaceChildren();
      appendEmptyTrackRow(body, `Current subtitle-track claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`);
      return;
    }
    setText("run-monitor-subtitle-state", collectionStateLabel(collection));
    body.replaceChildren();
    if (!tracks.length) {
      appendEmptyTrackRow(body, collectionEmptyText("subtitle", collection));
      return;
    }
    tracks.forEach((track) => {
      const row = document.createElement("tr");
      row.dataset.state = text(track.state, "unknown");
      const identity = document.createElement("td");
      identity.dataset.label = "Track";
      const index = track.stream_index === null || track.stream_index === undefined
        ? track.source_ordinal === null || track.source_ordinal === undefined ? "unknown" : `ordinal ${track.source_ordinal}`
        : `stream ${track.stream_index}`;
      identity.textContent = [index, text(track.language, "language unknown")].join(" · ");
      appendTechnicalDetails(identity, [text(track.track_id) ? `Track ID ${track.track_id}` : ""]);
      const source = document.createElement("td");
      source.dataset.label = "Source";
      source.textContent = [text(track.source_codec, "codec unknown"), humanize(track.source_type), humanize(track.source_kind)].join(" · ");
      const outcome = document.createElement("td");
      outcome.dataset.label = "Outcome";
      outcome.textContent = [
        humanize(track.state),
        text(track.planned_action) ? `Plan: ${track.planned_action}` : "",
        text(track.current_action),
        subtitleStepLabel(track),
        progressLabel(track.progress, track.progress_unit),
        subtitleCueLabel(track),
        text(track.output_codec) ? `Output ${track.output_codec}` : "",
        text(track.output_location) && track.output_location !== "unknown" ? humanize(track.output_location) : "",
        text(track.result),
      ].filter(Boolean).join(" · ");
      appendTechnicalDetails(outcome, [
        `Actions: ${subtitleActions(track)}`,
        trackTimelineLabel(track),
        text(track.output_path),
        text(track.parked_path),
        text(track.intended_final_path),
        text(track.reason),
        evidenceLabel(track.evidence),
      ]);
      row.append(identity, source, outcome);
      body.appendChild(row);
    });
  }

function appendFact(list, label, value) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value || "Not reported";
    row.append(term, detail);
    list.appendChild(row);
  }

  window.__runMonitorRenderingModule = function createRunMonitorRendering(deps) {
    ({
      byId, setText, text, array, object, humanize, stageLabel, formatTimestamp, progressLabel, evidenceLabel,
      routeDisplay, routeUnavailableLabel, itemEvidenceAllowed, collectionStateLabel, trackTimelineLabel,
      subtitleStepLabel, subtitleCueLabel,
    } = deps);
    return {
      appendRouteCard,
      appendTechnicalDetails,
      formatBytes,
      renderOutcome,
      renderRouteSummary,
      renderRoutes,
      renderStages,
      collectionEmptyText,
      appendEmptyTrackRow,
      renderAudio,
      subtitleActions,
      renderSubtitles,
      appendFact
    };
  };
})();
