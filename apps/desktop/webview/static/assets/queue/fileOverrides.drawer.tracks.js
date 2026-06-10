// queue/fileOverrides.drawer.tracks.js
// Exact-track selector and source/track metadata rendering for the Queue file override drawer.

(function initFileOverridesDrawerTracksModule() {
  // eslint-disable-next-line max-lines-per-function
  function createFileOverridesDrawerTracksModule(ctx) {
    const {
      documentRef: document,
      state,
      DRAWER_FIELD_PATHS,
      TRACK_ACTION_FIELD_PATHS,
      SOURCE_INFO_BASIS_LABELS,
      byId,
      isPlainObject,
      hasOwnValue,
      emptyExactSelectorState,
      selectorStreamIndex,
      isExactTrackSelector,
      currentFileOverridePathLooksFileLike,
      setStatus,
    } = ctx;

    function fileOverrideEffectiveSourceLabel(source) { return ctx.form.fileOverrideEffectiveSourceLabel(source); }
    function syncSubFilterFields() { return ctx.form.syncSubFilterFields(); }

  function trackActionBucket(kind, action) {
    if (kind === "audio" && action === "keep") return "audioKeep";
    if (kind === "audio" && action === "drop") return "audioDrop";
    if (kind === "subtitle" && action === "keep") return "subtitleKeep";
    if (kind === "subtitle" && action === "drop") return "subtitleDrop";
    if (kind === "subtitle" && action === "burn") return "subtitleBurn";
    return "";
  }

  function exactSelectorRules(entry, kind, action) {
    const sectionKey = kind === "audio" ? "audio" : "subtitles";
    const section = isPlainObject(entry?.[sectionKey]) ? entry[sectionKey] : {};
    if (kind === "subtitle" && action === "burn") {
      return isPlainObject(section.burnTrack) && isExactTrackSelector(section.burnTrack) ? [section.burnTrack] : [];
    }
    const fieldKey = action === "keep" ? "keepTracks" : "dropTracks";
    const rules = Array.isArray(section[fieldKey]) ? section[fieldKey] : [];
    return rules.filter((rule) => isPlainObject(rule) && isExactTrackSelector(rule));
  }

  function normalizedTrackLanguage(value) {
    const text = String(value ?? "").trim().toLowerCase();
    return text || "und";
  }

  function normalizedTrackCodec(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  function trackTitleValue(value) {
    return String(value ?? "").trim();
  }

  function globPatternMatches(value, pattern) {
    const text = String(value || "").toLowerCase();
    const rawPattern = String(pattern || "").toLowerCase();
    if (!rawPattern) return true;
    const escaped = rawPattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".");
    return new RegExp(`^${escaped}$`).test(text);
  }

  function exactSelectorMatchesTrack(selector, track, kind) {
    if (!isPlainObject(selector) || !isPlainObject(track)) return false;
    const selectorIndex = selectorStreamIndex(selector);
    if (selectorIndex === null || selectorIndex !== trackStreamIndex(track)) return false;
    if (hasOwnValue(selector, "language") && normalizedTrackLanguage(selector.language) !== normalizedTrackLanguage(track.language)) return false;
    if (hasOwnValue(selector, "codec") && normalizedTrackCodec(selector.codec) !== normalizedTrackCodec(track.codec)) return false;
    if (hasOwnValue(selector, "title") && !globPatternMatches(trackTitleValue(track.title), selector.title)) return false;
    if (kind === "audio" && hasOwnValue(selector, "channels")) {
      const selectorChannels = Number(selector.channels);
      const trackChannels = Number(track.channels);
      if (!Number.isFinite(selectorChannels) || !Number.isFinite(trackChannels) || selectorChannels !== trackChannels) return false;
    }
    if (kind === "subtitle" && hasOwnValue(selector, "forced") && Boolean(selector.forced) !== Boolean(track.forced)) return false;
    return true;
  }

  function exactSelectorForTrack(track, kind) {
    const streamIndex = trackStreamIndex(track);
    if (streamIndex === null) return null;
    const selector = { streamIndex };
    const language = normalizedTrackLanguage(track.language);
    if (language) selector.language = language;
    const codec = normalizedTrackCodec(track.codec);
    if (codec) selector.codec = codec;
    const title = trackTitleValue(track.title);
    if (title) selector.title = title;
    if (kind === "audio") {
      const channels = Number(track.channels);
      if (Number.isInteger(channels) && channels > 0) selector.channels = channels;
    } else if (typeof track.forced === "boolean") {
      selector.forced = Boolean(track.forced);
    }
    return selector;
  }

  function trackExactActionForTrack(track, kind) {
    const entry = state.foExactTrackOverrideEntry;
    if (!isPlainObject(entry)) return "";
    const keepRules = exactSelectorRules(entry, kind, "keep");
    const dropRules = exactSelectorRules(entry, kind, "drop");
    const burnRules = exactSelectorRules(entry, kind, "burn");
    const matchesKeep = keepRules.some((rule) => exactSelectorMatchesTrack(rule, track, kind));
    const matchesDrop = dropRules.some((rule) => exactSelectorMatchesTrack(rule, track, kind));
    const matchesBurn = burnRules.some((rule) => exactSelectorMatchesTrack(rule, track, kind));
    if (matchesBurn) return "burn";
    if (matchesDrop) return "drop";
    if (matchesKeep) return "keep";
    return "";
  }

  function computeExactTrackWarningsForMetadata(metadata) {
    const entry = state.foExactTrackOverrideEntry;
    state.foUnmatchedExactSelectors = emptyExactSelectorState();
    if (!isPlainObject(entry)) return [];
    const available = Boolean(metadata?.available || metadata?.probe_available);
    if (!available) {
      return ["Saved exact-track override cannot be displayed because track metadata is unavailable."];
    }
    const warnings = [];
    const groups = [
      { kind: "audio", action: "keep", tracks: Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [] },
      { kind: "audio", action: "drop", tracks: Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [] },
      { kind: "subtitle", action: "keep", tracks: Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [] },
      { kind: "subtitle", action: "drop", tracks: Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [] },
      { kind: "subtitle", action: "burn", tracks: Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [] },
    ];
    groups.forEach(({ kind, action, tracks }) => {
      exactSelectorRules(entry, kind, action).forEach((selector) => {
        const streamIndex = selectorStreamIndex(selector);
        const matched = tracks.some((track) => isPlainObject(track) && exactSelectorMatchesTrack(selector, track, kind));
        if (matched) return;
        const bucket = trackActionBucket(kind, action);
        if (bucket) state.foUnmatchedExactSelectors[bucket].push(selector);
        warnings.push(
          `Saved exact-track override no longer matches detected track metadata: ${TRACK_ACTION_FIELD_PATHS[kind][action]} stream ${streamIndex ?? "?"}.`
        );
      });
    });
    const seen = new Set();
    groups.forEach(({ kind, tracks }) => {
      tracks.forEach((track) => {
        if (!isPlainObject(track)) return;
        const streamIndex = trackStreamIndex(track);
        if (streamIndex === null) return;
        const key = `${kind}:${streamIndex}`;
        if (seen.has(key)) return;
        seen.add(key);
        const matchesKeep = exactSelectorRules(entry, kind, "keep").some((rule) => exactSelectorMatchesTrack(rule, track, kind));
        const matchesDrop = exactSelectorRules(entry, kind, "drop").some((rule) => exactSelectorMatchesTrack(rule, track, kind));
        const matchesBurn = exactSelectorRules(entry, kind, "burn").some((rule) => exactSelectorMatchesTrack(rule, track, kind));
        if ((matchesKeep && matchesDrop) || (matchesBurn && (matchesKeep || matchesDrop))) {
          warnings.push(`Stream ${streamIndex} has conflicting saved exact-track actions; destructive burn/drop actions win during processing.`);
        }
      });
    });
    return Array.from(new Set(warnings));
  }

  function resetExactTrackControls() {
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      control.value = "";
    });
  }

  function resetExactTrackActionsForField(fieldKey) {
      const targetPath = DRAWER_FIELD_PATHS[fieldKey];
      if (!targetPath) return;
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      const kind = control.dataset.foTrackKind || "";
      const action = control.dataset.foTrackActionKind || "";
      if (TRACK_ACTION_FIELD_PATHS[kind]?.[action] === targetPath) control.value = "";
    });
    const bucket = trackActionBucket(
      targetPath.startsWith("audio.") ? "audio" : "subtitle",
      targetPath.endsWith(".keepTracks") ? "keep" : targetPath.endsWith(".burnTrack") ? "burn" : "drop",
    );
    if (bucket) state.foUnmatchedExactSelectors[bucket] = [];
    state.foExactTrackWarnings = state.foExactTrackWarnings.filter((message) => !String(message || "").includes(targetPath));
  }

  function collectExactTrackSelectorsFromControls() {
    const selectors = emptyExactSelectorState();
    if (!currentFileOverridePathLooksFileLike()) return selectors;
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      if (control.disabled) return;
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop" && action !== "burn") return;
      const kind = control.dataset.foTrackKind || "";
      const trackData = control.dataset.foTrackJson || "";
      let track = null;
      try { track = JSON.parse(trackData); } catch (_err) { track = null; }
      const selector = exactSelectorForTrack(track, kind);
      const bucket = trackActionBucket(kind, action);
      if (bucket && selector) selectors[bucket].push(selector);
    });
    Object.keys(state.foUnmatchedExactSelectors).forEach((bucket) => {
      selectors[bucket].push(...state.foUnmatchedExactSelectors[bucket]);
    });
    return selectors;
  }

  function validateExactTrackSelectionsBeforeSave() {
    const selectedExactControl = Array.from(document.querySelectorAll("[data-fo-track-action]"))
      .some((control) => ["keep", "drop", "burn"].includes(String(control.value || "")));
    if (selectedExactControl && !currentFileOverridePathLooksFileLike()) {
      setStatus("Exact stream selectors can only be saved for a file path, not a folder or library scope.");
      return false;
    }
    if (state.foExactTrackWarnings.some((message) => message.includes("Saved exact-track override"))) {
      setStatus("Saved exact-track override cannot be safely resaved. Use saved policy for the affected field before saving.");
      return false;
    }
    const selected = new Map();
    let conflict = "";
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop" && action !== "burn") return;
      const kind = control.dataset.foTrackKind || "";
      const streamIndex = Number(control.dataset.foTrackStreamIndex);
      if (!kind || !Number.isInteger(streamIndex)) return;
      const key = `${kind}:${streamIndex}`;
      const previous = selected.get(key);
      if (previous && previous !== action) conflict = `${kind} stream ${streamIndex}`;
      selected.set(key, action);
    });
    if (conflict) {
      setStatus(`Choose either Keep or Drop for ${conflict}, not both.`);
      return false;
    }
    const burnCount = Array.from(document.querySelectorAll('[data-fo-track-action][data-fo-track-kind="subtitle"]'))
      .filter((control) => String(control.value || "") === "burn").length;
    if (burnCount > 1) {
      setStatus("Choose only one subtitle stream to burn into the video.");
      return false;
    }
    return true;
  }

  function confirmSubtitleBurnBeforeSave(payload) {
    const burnTrack = isPlainObject(payload?.subtitles?.burnTrack) ? payload.subtitles.burnTrack : null;
    if (!burnTrack) return true;
    const streamIndex = burnTrack.streamIndex ?? "?";
    const fileName = String(state.foCurrentPath || "").split(/[\\/]/).pop() || state.foCurrentPath || "selected file";
    const confirmed = window.confirm(
      `Burn subtitle stream ${streamIndex} into video for ${fileName}?\n\nThis forces encode and drops all selectable output subtitle tracks for this file.`,
    );
    if (!confirmed) {
      setStatus("Subtitle burn-in save cancelled.", "warning");
      return false;
    }
    return true;
  }

  function trackTextValue(value, fallback = "Not reported") {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function trackStreamIndex(track) {
    const raw = track?.stream_index ?? track?.index;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  function setTrackText(id, text) {
    const el = byId(id);
    if (el) el.textContent = text;
  }

  function clearElementChildren(id) {
    const el = byId(id);
    if (el) el.replaceChildren();
  }

  function setSourceInfoLoadingState(isLoading) {
    const section = byId("fo-source-info-section");
    if (!section) return;
    if (isLoading) section.dataset.loading = "true";
    else delete section.dataset.loading;
  }

  function clearDrawerSourceInfo(message = "File info unavailable for this file.") {
    setSourceInfoLoadingState(false);
    ["fo-source-info-grid", "fo-source-info-missing"].forEach(clearElementChildren);
    setTrackText("fo-source-info-status", message);
  }

  function showDrawerSourceInfoLoadingState(message = "Probing source for file info...") {
    setSourceInfoLoadingState(true);
    ["fo-source-info-grid", "fo-source-info-missing"].forEach(clearElementChildren);
    setTrackText("fo-source-info-status", message);
  }

  function setTrackGroupLoadingState(isLoading) {
    ["fo-audio-track-group", "fo-subtitle-track-group"].forEach((id) => {
      const group = byId(id);
      if (!group) return;
      if (isLoading) group.dataset.loading = "true";
      else delete group.dataset.loading;
    });
  }

  function clearDrawerTrackMetadata(message = "Track metadata unavailable for this file.") {
    setTrackGroupLoadingState(false);
    clearDrawerSourceInfo();
    ["fo-audio-track-list", "fo-subtitle-track-list", "fo-track-warning-list"].forEach(clearElementChildren);
    setTrackText("fo-audio-track-count", "Unavailable");
    setTrackText("fo-subtitle-track-count", "Unavailable");
    setTrackText("fo-audio-track-status", message);
    setTrackText("fo-subtitle-track-status", message);
    state.foExactTrackWarnings = [];
    state.foUnmatchedExactSelectors = emptyExactSelectorState();
  }

  function showDrawerTrackMetadataLoadingState(message = "Probing source for track metadata...") {
    setTrackGroupLoadingState(true);
    showDrawerSourceInfoLoadingState();
    ["fo-audio-track-list", "fo-subtitle-track-list", "fo-track-warning-list"].forEach(clearElementChildren);
    setTrackText("fo-audio-track-count", "Loading...");
    setTrackText("fo-subtitle-track-count", "Loading...");
    setTrackText("fo-audio-track-status", message);
    setTrackText("fo-subtitle-track-status", message);
    state.foExactTrackWarnings = [];
    state.foUnmatchedExactSelectors = emptyExactSelectorState();
  }

  function createTrackBadge(label, tone = "") {
    const badge = document.createElement("span");
    badge.className = "fo-track-badge";
    badge.textContent = label;
    if (tone) badge.dataset.tone = tone;
    return badge;
  }

  function appendTrackDetail(container, label, value) {
    const detail = document.createElement("span");
    detail.className = "fo-track-detail";
    detail.textContent = `${label}: ${trackTextValue(value)}`;
    container.appendChild(detail);
  }

  function appendSourceInfoFact(container, label, value) {
    const fact = document.createElement("div");
    fact.className = "fo-source-info-fact";
    const labelEl = document.createElement("span");
    labelEl.className = "fo-source-info-label";
    labelEl.textContent = label;
    const valueEl = document.createElement("strong");
    valueEl.className = "fo-source-info-value";
    valueEl.textContent = trackTextValue(value);
    fact.append(labelEl, valueEl);
    container.appendChild(fact);
  }

  function sourceInfoEstimatedBitrateText(sourceInfo) {
    const display = String(sourceInfo?.estimated_bitrate_display || "").trim();
    if (!display) return "";
    const basis = String(sourceInfo?.estimated_bitrate_basis || "").trim();
    const basisLabel = SOURCE_INFO_BASIS_LABELS[basis] || "";
    return basisLabel ? `${display} (${basisLabel})` : display;
  }

  function renderDrawerSourceInfo(sourceInfo) {
    setSourceInfoLoadingState(false);
    const info = isPlainObject(sourceInfo) ? sourceInfo : {};
    const grid = byId("fo-source-info-grid");
    const missingEl = byId("fo-source-info-missing");
    if (grid) grid.replaceChildren();
    if (missingEl) missingEl.replaceChildren();
    if (!info.available) {
      clearDrawerSourceInfo("File info unavailable for this file.");
      return;
    }

    const primary = isPlainObject(info.primary_video) ? info.primary_video : {};
    const facts = [
      ["Size", info.file_size_display],
      ["Duration", info.duration_display],
      ["Container", info.container],
      ["Estimated bitrate", sourceInfoEstimatedBitrateText(info)],
      ["Reported bitrate", info.overall_bitrate_display],
      ["Video codec", primary.available ? primary.codec : ""],
      ["Resolution", primary.available ? primary.resolution_display : ""],
      ["HDR", primary.available ? (primary.is_hdr ? trackTextValue(primary.hdr_format, "HDR") : "No") : ""],
      ["Video bitrate", primary.available ? primary.bitrate_display : ""],
    ];
    if (grid) facts.forEach(([label, value]) => appendSourceInfoFact(grid, label, value));

    const missingFacts = Array.isArray(info.missing_facts)
      ? info.missing_facts.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
    const source = trackTextValue(info.probe_source, "probe").replace(/[_-]+/g, " ");
    setTrackText(
      "fo-source-info-status",
      missingFacts.length ? `Partial file info loaded from ${source}.` : `File info loaded from ${source}.`,
    );
    if (missingEl && missingFacts.length) {
      const heading = document.createElement("strong");
      heading.textContent = "Missing facts";
      const body = document.createElement("span");
      body.textContent = missingFacts.join(", ");
      missingEl.append(heading, body);
    }
  }

  function trackSelectionMarkerLabel(marker) {
    if (!isPlainObject(marker)) return "";
    const sourceLabel = fileOverrideEffectiveSourceLabel(marker.source || "") || String(marker.source || "").trim();
    const field = String(marker.field || "").trim();
    if (sourceLabel && field) return `${sourceLabel} ${field}`;
    return sourceLabel || field;
  }

  function trackPreviewState(preview, streamIndex) {
    if (!isPlainObject(preview) || streamIndex === null) return null;
    const kept = Array.isArray(preview.kept_stream_indexes) ? preview.kept_stream_indexes.map(Number) : [];
    const dropped = Array.isArray(preview.dropped_stream_indexes) ? preview.dropped_stream_indexes.map(Number) : [];
    const burned = Array.isArray(preview.burned_stream_indexes) ? preview.burned_stream_indexes.map(Number) : [];
    const indexKey = String(streamIndex);
    if (burned.includes(streamIndex)) {
      return {
        label: "Burned into video",
        tone: "warning",
        marker: isPlainObject(preview.burned_stream_sources) ? preview.burned_stream_sources[indexKey] : null,
      };
    }
    if (dropped.includes(streamIndex)) {
      return {
        label: "Dropped",
        tone: "warning",
        marker: isPlainObject(preview.dropped_stream_sources) ? preview.dropped_stream_sources[indexKey] : null,
      };
    }
    if (kept.includes(streamIndex)) {
      return {
        label: "Kept",
        tone: "",
        marker: isPlainObject(preview.kept_stream_sources) ? preview.kept_stream_sources[indexKey] : null,
      };
    }
    return null;
  }

  function resolvedActionsByStream(section) {
    const rows = Array.isArray(section?.tracks) ? section.tracks : [];
    const map = new Map();
    rows.forEach((row) => {
      if (!isPlainObject(row)) return;
      const index = Number(row.stream_index);
      if (Number.isInteger(index)) map.set(index, row);
    });
    return map;
  }

  function resolvedActionForTrack(resolvedActions, track) {
    const streamIndex = trackStreamIndex(track);
    if (streamIndex === null || !(resolvedActions instanceof Map)) return null;
    return resolvedActions.get(streamIndex) || null;
  }

  function resolvedTrackActionTone(action) {
    const value = String(action || "").trim();
    if (value === "drop" || value === "burn" || value === "review") return "warning";
    return "";
  }

  function trackPipelineOptionText(resolvedAction) {
    if (!isPlainObject(resolvedAction)) return "Use pipeline policy";
    const source = String(resolvedAction.source || "");
    if (source === "file_override" || source === "folder_override") return "Use pipeline policy";
    const action = String(resolvedAction.action || "").trim();
    return action ? `Use pipeline policy: resolved ${action}` : "Use pipeline policy";
  }

  function appendTrackFlags(container, track, kind, previewState, resolvedAction) {
    if (isPlainObject(resolvedAction)) {
      const label = String(resolvedAction.label || "").trim() || "Resolved by backend policy";
      const badge = createTrackBadge(label, resolvedTrackActionTone(resolvedAction.action));
      const reason = String(resolvedAction.reason || "").trim();
      if (reason) badge.title = reason;
      container.appendChild(badge);
    } else if (previewState) {
      const markerLabel = trackSelectionMarkerLabel(previewState.marker);
      const label = markerLabel ? `${previewState.label} by ${markerLabel}` : previewState.label;
      container.appendChild(createTrackBadge(label, previewState.tone));
    }
    if (track.default) container.appendChild(createTrackBadge("Source default track"));
    if (track.forced) container.appendChild(createTrackBadge("Forced", "warning"));
    if (kind === "audio" && track.commentary) container.appendChild(createTrackBadge("Commentary", "warning"));
    if (track.hearing_impaired) container.appendChild(createTrackBadge("SDH"));
    if (kind === "subtitle" && track.image_based) container.appendChild(createTrackBadge("Image subtitle", "warning"));
    if (kind === "subtitle" && track.text_based) container.appendChild(createTrackBadge("Text subtitle"));
    if (
      kind === "subtitle"
      && (
        String(resolvedAction?.action || "") === "burn"
        || String(previewState?.marker?.field || "") === "subtitles.burnTrack"
      )
    ) {
      container.appendChild(createTrackBadge("Forces encode", "warning"));
      container.appendChild(createTrackBadge("Drops selectable subtitles", "warning"));
      container.appendChild(createTrackBadge("Destructive output change", "warning"));
    }
  }

  // Tracks without a stream index need a unique suffix so repeated
  // unknown-index rows do not produce duplicate reason-element ids.
  let trackActionReasonUnknownIdCounter = 0;

  function createTrackActionControl(track, kind, resolvedAction) {
    const streamIndex = trackStreamIndex(track);
    const wrapper = document.createElement("label");
    wrapper.className = "fo-track-action";
    const label = document.createElement("span");
    label.textContent = "File override";
    wrapper.appendChild(label);

    const select = document.createElement("select");
    select.className = "fo-track-action-select";
    select.dataset.foTrackAction = "true";
    select.dataset.foTrackKind = kind;
    select.dataset.foTrackStreamIndex = streamIndex === null ? "" : String(streamIndex);
    select.dataset.foTrackIndexAvailable = streamIndex === null ? "false" : "true";
    select.dataset.foTrackJson = JSON.stringify(track);
    select.setAttribute("aria-label", `Override action for ${kind === "audio" ? "audio" : "subtitle"} stream ${streamIndex ?? "unknown"}`);
    const options = [
      ["", trackPipelineOptionText(resolvedAction)],
      ["keep", kind === "audio" ? "Keep this audio track" : "Keep this subtitle track"],
      ["drop", kind === "audio" ? "Drop this audio track" : "Drop this subtitle track"],
    ];
    if (kind === "subtitle") {
      options.push(["burn", "Burn into video"]);
    }
    options.forEach(([value, text]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    });
    select.value = trackExactActionForTrack(track, kind);
    const reason = document.createElement("span");
    reason.className = "fo-track-action-reason";
    trackActionReasonUnknownIdCounter += 1;
    reason.id = `fo-track-action-reason-${kind}-${streamIndex === null ? `unknown-${trackActionReasonUnknownIdCounter}` : streamIndex}`;
    if (streamIndex === null) {
      select.disabled = true;
      reason.textContent = "Track stream index unavailable; exact-track override cannot be saved for this row.";
      select.title = reason.textContent;
      select.setAttribute("aria-describedby", reason.id);
    } else {
      reason.hidden = true;
    }
    wrapper.appendChild(select);
    wrapper.appendChild(reason);
    return wrapper;
  }

  function createTrackRow(track, kind, preview, resolvedActions) {
    const row = document.createElement("div");
    row.className = "fo-track-row";
    row.dataset.trackKind = kind;

    const streamIndex = trackStreamIndex(track);
    const previewState = trackPreviewState(preview, streamIndex);
    const resolvedAction = resolvedActionForTrack(resolvedActions, track);

    const summary = document.createElement("div");
    summary.className = "fo-track-summary";
    const title = document.createElement("strong");
    title.textContent = streamIndex === null ? "Stream ?" : `Stream ${streamIndex}`;
    summary.appendChild(title);
    const display = document.createElement("span");
    display.textContent = trackTextValue(track.display, `${trackTextValue(track.language, "und")} track`);
    summary.appendChild(display);
    row.appendChild(summary);

    const details = document.createElement("div");
    details.className = "fo-track-details";
    appendTrackDetail(details, "Language", trackTextValue(track.language, "und"));
    appendTrackDetail(details, "Title", track.title);
    appendTrackDetail(details, "Codec", track.codec);
    if (kind === "audio") {
      appendTrackDetail(details, "Channels", track.channels);
      appendTrackDetail(details, "Layout", track.channel_layout);
      if (String(track.bitrate_display || "").trim()) appendTrackDetail(details, "Bitrate", track.bitrate_display);
    }
    row.appendChild(details);

    const badges = document.createElement("div");
    badges.className = "fo-track-badges";
    appendTrackFlags(badges, track, kind, previewState, resolvedAction);
    row.appendChild(badges);
    row.appendChild(createTrackActionControl(track, kind, resolvedAction));
    return row;
  }

  function renderTrackGroup({ kind, tracks, preview, resolvedActions, listId, countId, statusId }) {
    const list = byId(listId);
    if (list) list.replaceChildren();
    const count = tracks.length;
    setTrackText(countId, `${count} ${count === 1 ? "track" : "tracks"}`);
    if (!count) {
      setTrackText(statusId, kind === "audio" ? "No detected audio tracks were reported." : "No detected subtitle tracks were reported.");
      return;
    }
    setTrackText(statusId, "");
    if (!list) return;
    tracks.forEach((track) => {
      if (isPlainObject(track)) list.appendChild(createTrackRow(track, kind, preview, resolvedActions));
    });
  }

  function trackWarningMessage(warning) {
    if (!isPlainObject(warning)) return String(warning || "").trim();
    const message = String(warning.message || "").trim();
    const field = String(warning.field || "").trim();
    if (!message) return "";
    return field ? `${field}: ${message}` : message;
  }

  function collectTrackWarnings(metadata, preview) {
    const warnings = [];
    const addWarning = (warning) => {
      const message = trackWarningMessage(warning);
      if (message) warnings.push(message);
    };
    (Array.isArray(metadata?.warnings) ? metadata.warnings : []).forEach(addWarning);
    (Array.isArray(preview?.audio?.warnings) ? preview.audio.warnings : []).forEach(addWarning);
    (Array.isArray(preview?.subtitles?.warnings) ? preview.subtitles.warnings : []).forEach(addWarning);
    (Array.isArray(metadata?.audio_tracks) ? metadata.audio_tracks : []).forEach((track) => {
      const index = trackStreamIndex(track);
      if (track?.commentary) warnings.push(`Audio stream ${index ?? "?"} appears to be commentary.`);
    });
    (Array.isArray(metadata?.subtitle_tracks) ? metadata.subtitle_tracks : []).forEach((track) => {
      const index = trackStreamIndex(track);
      if (track?.forced) warnings.push(`Subtitle stream ${index ?? "?"} is marked forced.`);
      if (track?.image_based) warnings.push(`Subtitle stream ${index ?? "?"} is image-based and may require OCR or burn-in review.`);
    });
    state.foExactTrackWarnings.forEach((message) => {
      const text = String(message || "").trim();
      if (text) warnings.push(text);
    });
    return Array.from(new Set(warnings));
  }

  function renderTrackWarnings(metadata, preview) {
    const list = byId("fo-track-warning-list");
    if (!list) return;
    list.replaceChildren();
    const warnings = collectTrackWarnings(metadata, preview);
    if (!warnings.length) return;
    const heading = document.createElement("p");
    heading.className = "fo-track-warning-heading";
    heading.textContent = "Track warnings";
    list.appendChild(heading);
    const warningList = document.createElement("ul");
    warnings.forEach((message) => {
      const item = document.createElement("li");
      item.className = "fo-track-warning";
      item.textContent = message;
      warningList.appendChild(item);
    });
    list.appendChild(warningList);
  }

  function renderDrawerTrackMetadata(payload) {
    setTrackGroupLoadingState(false);
    const metadata = isPlainObject(payload?.track_metadata) ? payload.track_metadata : {};
    const preview = isPlainObject(payload?.track_selection_preview) ? payload.track_selection_preview : {};
    const resolved = isPlainObject(payload?.resolved_track_actions) ? payload.resolved_track_actions : {};
    const available = Boolean(metadata.available || metadata.probe_available);
    renderDrawerSourceInfo(metadata.source_info);
    state.foExactTrackWarnings = computeExactTrackWarningsForMetadata(metadata);
    if (!available) {
      const message = trackWarningMessage((Array.isArray(metadata.warnings) ? metadata.warnings : [])[0])
        || "Track metadata unavailable for this file.";
      clearDrawerTrackMetadata(message);
      state.foExactTrackWarnings = computeExactTrackWarningsForMetadata(metadata);
      renderTrackWarnings(metadata, preview);
      return;
    }
    const audioTracks = Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [];
    const subtitleTracks = Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [];
    renderTrackGroup({
      kind: "audio",
      tracks: audioTracks,
      preview: isPlainObject(preview.audio) ? preview.audio : {},
      resolvedActions: resolvedActionsByStream(isPlainObject(resolved.audio) ? resolved.audio : {}),
      listId: "fo-audio-track-list",
      countId: "fo-audio-track-count",
      statusId: "fo-audio-track-status",
    });
    renderTrackGroup({
      kind: "subtitle",
      tracks: subtitleTracks,
      preview: isPlainObject(preview.subtitles) ? preview.subtitles : {},
      resolvedActions: resolvedActionsByStream(isPlainObject(resolved.subtitles) ? resolved.subtitles : {}),
      listId: "fo-subtitle-track-list",
      countId: "fo-subtitle-track-count",
      statusId: "fo-subtitle-track-status",
    });
    renderTrackWarnings(metadata, preview);
    syncSubFilterFields();
  }

  function trackMetadataFromTracksPayload(payload) {
    const available = Boolean(payload?.probe_available);
    const probeSource = String(payload?.probe_source || (available ? "tracks_endpoint" : "unavailable"));
    return {
      available,
      probe_available: available,
      probe_source: probeSource,
      source_info: isPlainObject(payload?.source_info)
        ? payload.source_info
        : { available: false, probe_source: probeSource },
      audio_tracks: available && Array.isArray(payload?.audio_tracks) ? payload.audio_tracks : [],
      subtitle_tracks: available && Array.isArray(payload?.subtitle_tracks) ? payload.subtitle_tracks : [],
      warnings: Array.isArray(payload?.warnings) ? payload.warnings : [],
    };
  }

    return {
      trackActionBucket,
      exactSelectorRules,
      exactSelectorMatchesTrack,
      exactSelectorForTrack,
      trackExactActionForTrack,
      computeExactTrackWarningsForMetadata,
      resetExactTrackControls,
      resetExactTrackActionsForField,
      collectExactTrackSelectorsFromControls,
      validateExactTrackSelectionsBeforeSave,
      confirmSubtitleBurnBeforeSave,
      trackStreamIndex,
      clearDrawerSourceInfo,
      showDrawerSourceInfoLoadingState,
      clearDrawerTrackMetadata,
      showDrawerTrackMetadataLoadingState,
      renderDrawerSourceInfo,
      renderDrawerTrackMetadata,
      trackMetadataFromTracksPayload,
    };
  }

  window.__queueFileOverridesDrawerTracksModule = { createFileOverridesDrawerTracksModule };
})();
