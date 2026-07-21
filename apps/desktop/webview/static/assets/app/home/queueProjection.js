(function () {
  function createHomeQueueProjectionModule(deps = {}) {
    const {
      byId, formatProgressValue, selectHomeListItem,
      setHomePanelStatus, setText, shortenPath,
    } = deps;
  function homeProgressPercent(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "";
    const bounded = Math.max(0, Math.min(100, number));
    return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
  }

  function homeCompactShortValue(value, maxChars = 64) {
    const text = formatProgressValue(value || "");
    if (!text) return "";
    if (typeof shortenPath === "function") return shortenPath(text, maxChars);
    return text.length > maxChars ? `...${text.slice(-(maxChars - 3))}` : text;
  }

  function homeQueueLeaf(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const parts = text.split(/[\\/]+/);
    return parts[parts.length - 1] || text;
  }

  function homeQueuePathSegments(value) {
    return String(value || "")
      .replace(/\\/g, "/")
      .split("/")
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function homeQueueStem(value) {
    return String(value || "").trim().replace(/\.[A-Za-z0-9]{2,5}$/, "").trim();
  }

  function homeQueueNumberToken(value) {
    const match = String(value ?? "").match(/\d{1,3}/);
    return match ? Number(match[0]) : 0;
  }

  function homeQueueSeasonEpisodeFromText(value) {
    const match = homeQueueStem(value).match(/\bS(?<season>\d{1,2})E(?<episode>\d{1,3})(?:[-_]?E\d{1,3})?\b/i);
    if (!match?.groups) return "";
    const season = Number(match.groups.season);
    const episode = Number(match.groups.episode);
    if (!Number.isFinite(season) || !Number.isFinite(episode) || episode <= 0) return "";
    return `S${String(season).padStart(2, "0")}E${String(episode).padStart(2, "0")}`;
  }

  function homeQueueSeasonEpisodeCode(item = {}) {
    const seasonValue = item.season_number ?? item.season ?? item.season_value;
    const episodeValue = item.episode_number ?? item.episode ?? item.start_episode ?? item.start_episode_value;
    const hasSeasonValue = seasonValue !== undefined && seasonValue !== null && String(seasonValue).trim() !== "";
    const hasEpisodeValue = episodeValue !== undefined && episodeValue !== null && String(episodeValue).trim() !== "";
    const season = homeQueueNumberToken(seasonValue);
    const episode = homeQueueNumberToken(episodeValue);
    if (hasSeasonValue && hasEpisodeValue && Number.isFinite(season) && Number.isFinite(episode) && episode > 0) {
      return `S${String(season).padStart(2, "0")}E${String(episode).padStart(2, "0")}`;
    }
    return [
      item.display_name,
      item.lookup_title,
      item.title,
      item.relative_path,
      item.source_path,
      item.source_file_name,
      item.source_file,
      item.path,
      item.input_path,
      item.file,
    ].map(homeQueueSeasonEpisodeFromText).find(Boolean) || "";
  }

  function homeQueueLooksTv(item = {}) {
    const mediaType = String(item.media_type || item.media_kind || item.phase || "").trim().toLowerCase();
    const haystack = [
      item.display_name,
      item.lookup_title,
      item.title,
      item.relative_path,
      item.source_path,
      item.source_file_name,
      item.source_file,
      item.path,
      item.input_path,
      item.file,
    ].join(" ");
    return mediaType.includes("tv")
      || mediaType.includes("show")
      || mediaType.includes("episode")
      || Boolean(homeQueueSeasonEpisodeCode(item))
      || /(?:^|[\\/])season\s*\d{1,2}(?:[\\/]|$)/i.test(haystack);
  }

  function homeQueueRejectSeriesLabel(value) {
    const text = String(value || "").trim();
    return !text
      || /^(?:tv|tv safe|shows?|episodes?|movies?|source|sources|outsource|videos?|media|season\s*\d{1,2}|s\d{1,2})$/i.test(text);
  }

  function homeQueueSeriesCandidateFromText(value) {
    let text = homeQueueStem(value).replace(/[._]+/g, " ").replace(/\s+/g, " ").trim();
    if (!text) return "";
    const episodeMatch = text.match(/\bS\d{1,2}E\d{1,3}(?:[-_]?E\d{1,3})?\b/i);
    if (episodeMatch) text = text.slice(0, episodeMatch.index).replace(/[\s._-]+$/g, "").trim();
    text = text.replace(/\s*\((?:season\s*|s)\d{1,2}\)\s*$/i, "").trim();
    return homeQueueRejectSeriesLabel(text) ? "" : text;
  }

  function homeQueueSeriesCandidateFromPath(value) {
    const parts = homeQueuePathSegments(value).filter((part) => !/^[A-Za-z]:$/.test(part));
    if (parts.length < 2) return "";
    for (let index = parts.length - 2; index >= 1; index -= 1) {
      if (/^(?:season\s*\d{1,2}|s\d{1,2})$/i.test(parts[index])) {
        const candidate = homeQueueSeriesCandidateFromText(parts[index - 1]);
        if (candidate) return candidate;
      }
    }
    const parent = homeQueueSeriesCandidateFromText(parts[parts.length - 2]);
    return parent || "";
  }

  // Release-style movie filenames ("Hoppers.2026.2160p.WEB-DL...") collapse to
  // "Title (Year)". Picks the release year (a 1900-2099 token that is
  // parenthesized, last, or immediately followed by a quality/source tag) so a
  // year inside the title (e.g. "Blade Runner 2049 2017") is not mistaken for it.
  function homeMovieTitleYear(value) {
    let text = String(value || "").trim();
    if (!text) return "";
    text = text.replace(/\.(mkv|mp4|m4v|avi|mov|ts|webm)$/i, "");
    const spaced = text.replace(/[._]+/g, " ").replace(/\s+/g, " ").trim();
    const junk = /^(480p|576p|720p|1080p|2160p|4k|uhd|web|webdl|web-dl|webrip|web-rip|bluray|blu-ray|brrip|bdrip|hdrip|dvdrip|remux|remaster|remastered|unrated|extended|proper|repack|imax|hdr|hdr10|dv|dovi|hevc|avc|x264|x265|h264|h265|10bit|8bit|aac|ac3|eac3|dd5|ddp5|dts|atmos|truehd|flac|dual|multi)$/i;
    const tokens = spaced.split(" ");
    const yearRe = /^\(?((?:19|20)\d{2})\)?$/;
    for (let i = 0; i < tokens.length; i += 1) {
      const match = tokens[i].match(yearRe);
      if (!match) continue;
      const parenthesized = /^\(.*\)$/.test(tokens[i]);
      const next = (tokens[i + 1] || "").replace(/[()]/g, "");
      if (parenthesized || i === tokens.length - 1 || junk.test(next)) {
        const title = tokens.slice(0, i).join(" ").replace(/[\s-]+$/g, "").trim();
        if (title) return `${title} (${match[1]})`;
        break;
      }
    }
    return spaced;
  }

  function homeNormalizeQueueTitle(rawValue, item = {}) {
    const raw = String(rawValue || "").trim();
    if (!raw) return "";
    const mediaType = String(item.media_type || item.media_kind || "").trim().toLowerCase();
    if (mediaType === "movie" || mediaType === "movies") {
      const leaf = homeQueueLeaf(raw);
      return homeMovieTitleYear(leaf) || leaf;
    }
    return raw;
  }

  function homeQueueTitle(item = {}) {
    const raw = item.lookup_title
      || item.display_name
      || item.title
      || item.source_file_name
      || item.source_file
      || item.source_path
      || item.path
      || item.input_path
      || item.file
      || "";
    return homeNormalizeQueueTitle(raw, item);
  }

  function homeQueueDisplayLabel(item = {}) {
    const rawTitle = homeQueueTitle(item);
    if (!homeQueueLooksTv(item)) {
      return {
        main: rawTitle || "Untitled queue item",
        episode: "",
        accessibleText: rawTitle || "Untitled queue item",
      };
    }
    const episode = homeQueueSeasonEpisodeCode(item);
    const series = [
      item.show_name,
      item.series_name,
      item.series_title,
      item.show_title,
      homeQueueSeriesCandidateFromPath(item.relative_path),
      homeQueueSeriesCandidateFromPath(item.source_path),
      homeQueueSeriesCandidateFromPath(item.path),
      homeQueueSeriesCandidateFromText(item.lookup_title),
      homeQueueSeriesCandidateFromText(item.display_name),
      homeQueueSeriesCandidateFromText(item.title),
      homeQueueSeriesCandidateFromText(item.source_file_name),
      homeQueueSeriesCandidateFromText(item.source_file),
      homeQueueSeriesCandidateFromText(rawTitle),
    ].map((value) => homeQueueSeriesCandidateFromText(value)).find(Boolean);
    const main = series || "TV series";
    return {
      main,
      episode,
      accessibleText: [main, episode].filter(Boolean).join(" "),
    };
  }

  function homeQueueRoute(item = {}) {
    const route = formatProgressValue(item.route_name || item.route || item.mode || "");
    if (/remux/i.test(route) && /codec check pending/i.test(route)) return "REMUX";
    return /^[a-z_]+$/.test(route) ? route.replace(/_/g, " ").toUpperCase() : route;
  }

  function homeQueueMeta(item = {}) {
    return [
      homeQueueRoute(item),
      item.operator_status || item.status || item.decision || "",
      item.queue_position || (item.queue_index || item.queue_total ? `${item.queue_index || "?"}/${item.queue_total || "?"}` : ""),
    ].filter(Boolean).map(formatProgressValue).join(" · ");
  }

  function homeQueuePosition(item = {}) {
    return formatProgressValue(
      item.queue_position || (item.queue_index || item.queue_total ? `${item.queue_index || "?"}/${item.queue_total || "?"}` : "")
    );
  }

  function homeQueueSourceLocation(item = {}) {
    const source = item.source_path || item.path || item.input_path || item.file || item.relative_path || "";
    const segments = homeQueuePathSegments(source);
    if (segments.length >= 2) return segments[segments.length - 2];
    return homeQueueLeaf(source);
  }

  function homeQueueOutputEvidence(item = {}) {
    const output = item.output_path || item.destination_path || "";
    if (output) return homeCompactShortValue(homeQueueLeaf(output), 36);
    if (item.library_output_root) return "Root loaded";
    return "Not loaded";
  }

  function homeQueueDetailItems(item = {}, options = {}) {
    const items = [];
    if (options.csvRerunQueue) {
      items.push({ label: "Workflow", value: "CSV rerun queue", state: "source" });
    }
    const activeWork = options.activeWork && typeof options.activeWork === "object" ? options.activeWork : {};
    if (activeWork.current_stage_label) {
      items.push({ label: "Current stage", value: formatProgressValue(activeWork.current_stage_label), state: "running" });
    }
    if (activeWork.latest_evidence_label) {
      items.push({ label: "Evidence", value: formatProgressValue(activeWork.latest_evidence_label), state: "running" });
    } else if (activeWork.missing_evidence_label) {
      items.push({ label: "Evidence", value: formatProgressValue(activeWork.missing_evidence_label), state: "warning" });
    }
    if (activeWork.next_stage_label) {
      items.push({ label: "Next", value: formatProgressValue(activeWork.next_stage_label), state: "queue" });
    }
    items.push(
      { label: "Route", value: homeQueueRoute(item) || "Not reported", state: "route" },
      { label: "Status", value: formatProgressValue(item.operator_status || item.status || item.decision || "Unknown"), state: "status" },
      { label: "Queue", value: homeQueuePosition(item) || "Unknown", state: "queue" },
      { label: "Source", value: homeQueueSourceLocation(item) || "Not loaded", state: "source" },
      { label: "Output", value: homeQueueOutputEvidence(item), state: "output" },
    );
    return items;
  }

  function renderHomeQueueDetail(item = {}, options = {}) {
    const container = byId("home-next-queue-detail");
    if (!container) return;
    const label = homeQueueDisplayLabel(item);
    const items = homeQueueDetailItems(item, options);
    container.classList.add("home-next-queue-detail");
    container.setAttribute(
      "aria-label",
      [
        `Selected queue item: ${label.accessibleText || "Untitled queue item"}.`,
        items.map((entry) => `${entry.label}: ${entry.value}`).join(". "),
        "Open Queue for full backend-owned row evidence before launch or rerun.",
      ].join(" ")
    );
    const strip = document.createElement("span");
    strip.className = "home-next-queue-detail-strip";
    items.forEach((entry) => {
      const chip = document.createElement("span");
      chip.className = "home-next-queue-detail-chip";
      chip.dataset.detail = entry.state || "";
      chip.title = `${entry.label}: ${entry.value}`;
      const chipLabel = document.createElement("span");
      chipLabel.className = "home-next-queue-detail-label";
      chipLabel.textContent = `${entry.label}:`;
      const chipValue = document.createElement("strong");
      chipValue.className = "home-next-queue-detail-value";
      chipValue.textContent = entry.value;
      chip.append(chipLabel, chipValue);
      strip.appendChild(chip);
    });
    const handoff = document.createElement("span");
    handoff.className = "home-next-queue-detail-handoff";
    handoff.textContent = options.csvRerunQueue
      ? "This is the active CSV rerun queue; Open Queue for full backend-owned row evidence."
      : "Open Queue for full row evidence before launch or rerun.";
    container.replaceChildren(strip, handoff);
  }

  function renderHomeQueueDetailMessage(message) {
    const container = byId("home-next-queue-detail");
    if (!container) {
      setText("home-next-queue-detail", message);
      return;
    }
    container.classList.add("home-next-queue-detail");
    container.setAttribute("aria-label", message);
    container.textContent = message;
  }

  function homeCsvRerunEvidence(context = {}) {
    const activityReader = window.mediaPipelineProgressView?.csvRerunActivityEvidence;
    if (typeof activityReader === "function") return activityReader(context);
    const tailReader = window.mediaPipelineProgressView?.csvRerunTailEvidence;
    return typeof tailReader === "function" ? tailReader(context.stdoutTail) : { hasEvidence: false };
  }

  function homeCsvRerunActive(context = {}, evidence = homeCsvRerunEvidence(context)) {
    if (!evidence?.hasEvidence) return false;
    if (context?.closeReadiness?.safe_to_close === true) return false;
    if (evidence.isActive === true || evidence.workerActive === true) return true;
    return !/PIPELINE SHUTDOWN CLEANLY|ROUND COMPLETE|Single-pass mode complete/i.test(String(evidence.latestLine || ""));
  }

  function homeCsvRerunText(value) {
    if (value == null) return "";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
    if (Array.isArray(value)) return value.map(homeCsvRerunText).filter(Boolean).join(" ");
    if (typeof value === "object") return Object.values(value).map(homeCsvRerunText).filter(Boolean).join(" ");
    return "";
  }

  function homeQueueRowLooksCsvRerun(item = {}) {
    const metadata = item?.metadata && typeof item.metadata === "object" ? item.metadata : {};
    const text = [
      item.queue_source,
      item.queue_phase,
      item.rerun_batch_id,
      item.batch_id,
      item.source_path,
      item.path,
      item.input_path,
      item.file,
      item.relative_path,
      item.stage_path,
      item.planned_output_path,
      metadata.queue_source,
      metadata.queue_phase,
      metadata.stage_path,
      metadata.planned_output_path,
      metadata.rerun_batch_id,
      metadata.batch_id,
    ].map(homeCsvRerunText).filter(Boolean).join(" ");
    return /\bcsv[_\s-]*rerun\b|RerunQueue|RerunWorkspace|RerunParked|\\rerun_\d{8}_|\/rerun_\d{8}_/i.test(text);
  }

  function homeCsvRerunWorkerRows(context = {}) {
    const rows = [];
    [
      context?.snapshot?.worker_progress?.rows,
      context?.diagnostics?.worker_progress?.rows,
      context?.snapshot?.workers,
      context?.diagnostics?.workers,
    ].forEach((source) => {
      if (Array.isArray(source)) rows.push(...source.filter(Boolean));
    });
    return rows;
  }

  function homeWorkerLooksCsvRerun(row = {}) {
    const kind = String(row.job_kind || row.kind || "").trim().toLowerCase();
    const label = String(row.worker_label || "").trim().toLowerCase();
    if (kind === "rerun_csv" || kind === "csv_rerun") return true;
    if (kind === "pipeline" || label === "local pipeline") return false;
    const text = [
      row.job_kind,
      row.worker_label,
      row.worker_id,
      row.stage,
      row.status,
      row.status_state,
      row.source,
      row.last_log_line,
    ].map(homeCsvRerunText).filter(Boolean).join(" ");
    return /\bcsv\b.*\brerun\b|\brerun\b.*\bcsv\b|RerunQueue|RerunWorkspace|RerunParked|\\rerun_\d{8}_|\/rerun_\d{8}_/i.test(text);
  }

  function homeCsvRerunQueueContext(context = {}, queue = {}, visibleRows = []) {
    const queueRows = Array.isArray(queue?.rows) ? queue.rows.filter(Boolean) : [];
    const hasQueueEvidence = queueRows.some(homeQueueRowLooksCsvRerun) || visibleRows.some(homeQueueRowLooksCsvRerun);
    const hasWorkerEvidence = homeCsvRerunWorkerRows(context).some(homeWorkerLooksCsvRerun);
    const progressEvidence = homeCsvRerunEvidence(context);
    const hasProgressEvidence = Boolean(progressEvidence?.hasWorkerEvidence && progressEvidence?.hasEvidence);
    return {
      csvRerunQueue: Boolean(hasQueueEvidence || hasWorkerEvidence || hasProgressEvidence),
      source: hasQueueEvidence ? "queue_source=csv_rerun" : hasWorkerEvidence ? "worker=Local rerun csv" : hasProgressEvidence ? "progress=csv rerun worker" : "",
    };
  }

  function homeCsvRerunRows(evidence = {}, activeWork = {}) {
    const rows = [];
    const activeLine = homeActiveWorkLine(activeWork);
    if (activeLine) {
      rows.push({
        label: "Now",
        value: activeLine,
        meta: [activeWork.item_label, activeWork.next_stage_label ? `Next: ${activeWork.next_stage_label}` : ""].filter(Boolean).join(" · ") || "Backend active-work evidence",
        state: activeWork.evidence_status === "waiting" ? "warning" : "running",
      });
    }
    rows.push(
      {
        label: "Importing",
        value: evidence.currentImport || activeWork.latest_evidence_label || activeWork.missing_evidence_label || "Waiting for next copy",
        meta: "Current CSV staging/import",
        state: evidence.currentImport || activeWork.latest_evidence_label ? "running" : "warning",
      },
      {
        label: "Last imported",
        value: evidence.lastImported || "No staged copy yet",
        meta: "Most recent completed copy",
        state: evidence.lastImported ? "ready" : "empty",
      },
      {
        label: "Processing",
        value: evidence.processing || "Waiting for processing evidence",
        meta: "Starts after staging",
        state: evidence.processing && !String(evidence.processing).startsWith("Not processing yet") ? "running" : "warning",
      },
      {
        label: "CSV rows",
        value: evidence.plannedRows || "Rows loaded",
        meta: "From stdout tail",
        state: evidence.plannedRows ? "ready" : "unknown",
      },
    );
    return rows;
  }

  function renderHomeCsvRerunDetail(evidence = {}, activeWork = {}) {
    const container = byId("home-next-queue-detail");
    if (!container) return;
    const rows = homeCsvRerunRows(evidence, activeWork);
    container.classList.add("home-next-queue-detail");
    container.setAttribute(
      "aria-label",
      rows.map((entry) => `${entry.label}: ${entry.value}`).join(". ")
    );
    const strip = document.createElement("span");
    strip.className = "home-next-queue-detail-strip";
    rows.forEach((entry) => {
      const chip = document.createElement("span");
      chip.className = "home-next-queue-detail-chip";
      chip.dataset.detail = entry.state || "";
      chip.title = `${entry.label}: ${entry.value}`;
      const chipLabel = document.createElement("span");
      chipLabel.className = "home-next-queue-detail-label";
      chipLabel.textContent = `${entry.label}:`;
      const chipValue = document.createElement("strong");
      chipValue.className = "home-next-queue-detail-value";
      chipValue.textContent = entry.value;
      chip.append(chipLabel, chipValue);
      strip.appendChild(chip);
    });
    const handoff = document.createElement("span");
    handoff.className = "home-next-queue-detail-handoff";
    handoff.textContent = evidence.processing && !String(evidence.processing).startsWith("Not processing yet")
      ? "CSV rerun is processing; keep monitoring Home and close-readiness."
      : "CSV rerun is still importing staged files before processing starts.";
    container.replaceChildren(strip, handoff);
  }

  function renderHomeCsvRerunQueue(context = {}) {
    const evidence = homeCsvRerunEvidence(context);
    if (!homeCsvRerunActive(context, evidence)) return false;
    const activeWork = homeActiveWork(context);
    const list = byId("home-next-queue-list");
    if (!list) return false;
    list.setAttribute("role", "listbox");
    list.replaceChildren();
    setHomePanelStatus("home-next-queue-status", "CSV rerun active", "running");
    homeCsvRerunRows(evidence, activeWork).forEach((entry, index) => {
      const li = document.createElement("li");
      li.tabIndex = 0;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", index === 0 ? "true" : "false");
      li.classList.toggle("is-selected", index === 0);
      if (entry.label === "Now") li.dataset.current = "true";
      li.dataset.status = entry.state || "";
      li.setAttribute("aria-label", `${entry.label}: ${entry.value}`);
      const title = document.createElement("span");
      title.className = "home-next-queue-title";
      const titleMain = document.createElement("span");
      titleMain.className = "home-next-queue-title-main";
      titleMain.textContent = `${entry.label}: ${entry.value}`;
      title.appendChild(titleMain);
      const meta = document.createElement("span");
      meta.className = "home-next-queue-meta";
      meta.textContent = entry.meta;
      li.append(title, meta);
      const activate = () => {
        selectHomeListItem(li);
        renderHomeCsvRerunDetail(evidence, activeWork);
      };
      li.addEventListener("click", activate);
      li.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
      list.appendChild(li);
    });
    renderHomeCsvRerunDetail(evidence, activeWork);
    return true;
  }

  function renderHomeCsvRerunCompletion(context = {}) {
    const summary = window.mediaPipelineProgressView?.csvRerunCompletionSummary?.(context?.snapshot);
    if (!summary) return false;
    const list = byId("home-next-queue-list");
    if (!list) return false;
    const label = summary.display_label || "CSV rerun complete";
    const detail = summary.detail || "Backend manifest terminal state.";
    list.setAttribute("role", "listbox");
    list.replaceChildren();
    setHomePanelStatus("home-next-queue-status", label, summary.display_state || "ok");
    const item = document.createElement("li");
    item.tabIndex = 0;
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", "true");
    item.classList.add("is-selected");
    item.dataset.status = summary.display_state || "ok";
    item.setAttribute("aria-label", `${label}: ${detail}`);
    const title = document.createElement("span");
    title.className = "home-next-queue-title";
    title.textContent = summary.csv_name || summary.batch_id || "Current CSV";
    const meta = document.createElement("span");
    meta.className = "home-next-queue-meta";
    meta.textContent = detail;
    item.append(title, meta);
    const detailMessage = `${detail}\n${summary.historical_evidence_note || "Historical progress evidence is available in Telemetry and Diagnostics."}`;
    const activate = () => {
      selectHomeListItem(item);
      renderHomeQueueDetailMessage(detailMessage);
    };
    item.addEventListener("click", activate);
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });
    list.appendChild(item);
    renderHomeQueueDetailMessage(detailMessage);
    return true;
  }

  function homeQueueRowIsRunnable(item = {}) {
    const status = String(item.operator_status || "").trim().toLowerCase();
    return status === "ready" || status === "priority ready";
  }

  function homeQueueRowVisibleInNextPanel(item = {}) {
    return homeQueueRowIsRunnable(item) || homeQueueRowLooksCsvRerun(item);
  }

  function homeActiveWork(context = {}) {
    const payload = context?.snapshot?.current_work;
    return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  }

  function homeActiveWorkLine(activeWork = {}) {
    return activeWork.latest_evidence_label
      || activeWork.current_stage_label
      || activeWork.summary_label
      || activeWork.missing_evidence_label
      || "";
  }

  function homeQueuePreviewRows(queue = {}) {
    const rows = Array.isArray(queue.rows) ? queue.rows.filter(Boolean) : [];
    return rows.filter(homeQueueRowVisibleInNextPanel).slice(0, 5);
  }

    return {
      homeProgressPercent, homeCompactShortValue, homeQueueLeaf, homeQueuePathSegments,
      homeQueueStem, homeQueueNumberToken, homeQueueSeasonEpisodeFromText, homeQueueSeasonEpisodeCode,
      homeQueueLooksTv, homeQueueRejectSeriesLabel, homeQueueSeriesCandidateFromText,
      homeQueueSeriesCandidateFromPath, homeMovieTitleYear, homeNormalizeQueueTitle,
      homeQueueTitle, homeQueueDisplayLabel, homeQueueRoute, homeQueueMeta, homeQueuePosition,
      homeQueueSourceLocation, homeQueueOutputEvidence, homeQueueDetailItems, renderHomeQueueDetail,
      renderHomeQueueDetailMessage, homeCsvRerunEvidence, homeCsvRerunActive, homeCsvRerunText,
      homeQueueRowLooksCsvRerun, homeCsvRerunWorkerRows, homeWorkerLooksCsvRerun,
      homeCsvRerunQueueContext, homeCsvRerunRows, renderHomeCsvRerunDetail,
      renderHomeCsvRerunQueue, renderHomeCsvRerunCompletion, homeQueueRowIsRunnable,
      homeQueueRowVisibleInNextPanel, homeActiveWork, homeActiveWorkLine, homeQueuePreviewRows,
    };
  }
  window.__homeQueueProjectionModule = { createHomeQueueProjectionModule };
})();
