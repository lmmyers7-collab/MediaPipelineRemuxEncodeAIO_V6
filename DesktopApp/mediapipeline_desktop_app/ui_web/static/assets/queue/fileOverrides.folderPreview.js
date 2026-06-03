// queue/fileOverrides.folderPreview.js
// Split child of queue/fileOverrides.drawer.js. Loaded before the drawer;
// the drawer consumes this temporary stash global and deletes it immediately.
/* eslint-disable max-lines-per-function -- moved folder-preview logic during the queue-view split without behavior changes. */

(function () {
  "use strict";

  function createFileOverridesFolderPreviewModule({
    apiGet: apiGetDependency,
    apiPost: apiPostDependency,
    appendCommandResult: appendCommandResultDependency,
    backendErrorMessage: backendErrorMessageDependency,
    byId: byIdDependency,
    clearElementChildren: clearElementChildrenDependency,
    closeFileSettingsDrawer: closeFileSettingsDrawerDependency,
    currentItem: currentItemDependency,
    currentPath: currentPathDependency,
    documentRef,
    exactSelectorForTrack: exactSelectorForTrackDependency,
    fileOverridesRoute: fileOverridesRouteDependency,
    hasOwnValue: hasOwnValueDependency,
    isPlainObject: isPlainObjectDependency,
    langCodesToRules: langCodesToRulesDependency,
    loadFileOverrideEffectiveForPath: loadFileOverrideEffectiveForPathDependency,
    parseLangList: parseLangListDependency,
    refreshAll: refreshAllDependency,
    setStatus: setStatusDependency,
    setTrackText: setTrackTextDependency,
  } = {}) {
    const apiGet = typeof apiGetDependency === "function" ? apiGetDependency : window.apiGet;
    const apiPost = typeof apiPostDependency === "function" ? apiPostDependency : window.apiPost;
    const appendCommandResult = typeof appendCommandResultDependency === "function" ? appendCommandResultDependency : function () {};
    const backendErrorMessage = typeof backendErrorMessageDependency === "function" ? backendErrorMessageDependency : function (result, fallback = "Unknown error.") { return String(result?.message || fallback); };
    const byId = typeof byIdDependency === "function" ? byIdDependency : function (id) { return document.getElementById(id); };
    const clearElementChildren = typeof clearElementChildrenDependency === "function" ? clearElementChildrenDependency : function (id) { const el = byId(id); if (el) el.replaceChildren(); };
    const closeDrawer = typeof closeFileSettingsDrawerDependency === "function" ? closeFileSettingsDrawerDependency : function () {};
    const currentItem = typeof currentItemDependency === "function" ? currentItemDependency : function () { return null; };
    const currentPath = typeof currentPathDependency === "function" ? currentPathDependency : function () { return ""; };
    const document = documentRef || window.document;
    const exactSelectorForTrack = typeof exactSelectorForTrackDependency === "function" ? exactSelectorForTrackDependency : function () { return null; };
    const fileOverridesRoute = String(fileOverridesRouteDependency || "/api/queue/file-overrides");
    const hasOwnValue = typeof hasOwnValueDependency === "function" ? hasOwnValueDependency : function (source, key) { return source && typeof source === "object" && Object.prototype.hasOwnProperty.call(source, key); };
    const isPlainObject = typeof isPlainObjectDependency === "function" ? isPlainObjectDependency : function (value) { return value && typeof value === "object" && !Array.isArray(value); };
    const langCodesToRules = typeof langCodesToRulesDependency === "function" ? langCodesToRulesDependency : function (langs) { return (Array.isArray(langs) ? langs : []).map((lang) => ({ language: lang })); };
    const loadEffectiveForPath = typeof loadFileOverrideEffectiveForPathDependency === "function" ? loadFileOverrideEffectiveForPathDependency : async function () { return false; };
    const parseLangList = typeof parseLangListDependency === "function" ? parseLangListDependency : function (text) { return String(text || "").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean); };
    const refreshAll = typeof refreshAllDependency === "function" ? refreshAllDependency : null;
    const setStatus = typeof setStatusDependency === "function" ? setStatusDependency : function () {};
    const setTrackText = typeof setTrackTextDependency === "function" ? setTrackTextDependency : function (id, text) { const el = byId(id); if (el) el.textContent = text; };
    const FOLDER_RULE_FILE_SUFFIXES = new Set([".mkv", ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts", ".webm"]);
    let foLastFolderPreviewPayload = null;
    let foLastFolderPreviewRequest = null;
    let foFolderRules = [];

  function normalizedFolderPreviewPath(value) {
    return String(value || "").trim().replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
  }

  function folderPreviewParentPath(value) {
    const text = String(value || "").trim().replace(/[\\/]+$/, "");
    if (!text) return "";
    const slash = Math.max(text.lastIndexOf("\\"), text.lastIndexOf("/"));
    if (slash < 0) return "";
    if (slash === 0) return text.slice(0, 1);
    if (slash === 2 && /^[A-Za-z]:/.test(text)) return text.slice(0, 3);
    return text.slice(0, slash);
  }

  function folderPreviewLeaf(value) {
    const text = String(value || "").trim().replace(/[\\/]+$/, "");
    if (!text) return "";
    return text.split(/[\\/]/).filter(Boolean).pop() || text;
  }

  function folderPreviewScopeLabel(folderPath, payload) {
    const scope = isPlainObject(payload?.scope) ? payload.scope : {};
    if (scope.is_library_root) return "Library root";
    const folderKey = normalizedFolderPreviewPath(folderPath);
    const sourceRootKey = normalizedFolderPreviewPath(currentItem()?.library_source_root || currentItem()?.source_root || "");
    if (sourceRootKey && folderKey === sourceRootKey) return "Library root";

    const leaf = folderPreviewLeaf(folderPath).toLowerCase();
    const seasonFolder = String(currentItem()?.season_folder || "").trim().toLowerCase();
    if ((seasonFolder && leaf === seasonFolder) || /^s\d{1,2}$/.test(leaf) || /^season\s+\d{1,2}$/.test(leaf)) {
      return "Season folder";
    }

    const showFolder = String(currentItem()?.show_folder || "").trim().toLowerCase();
    if (showFolder && leaf === showFolder) {
      return "Show folder";
    }

    const relativeParent = folderPreviewParentPath(currentItem()?.relative_path || "");
    const relativeParentLeaf = folderPreviewLeaf(relativeParent).toLowerCase();
    const relativeGrandparent = folderPreviewParentPath(relativeParent);
    const mediaType = String(currentItem()?.media_type || currentItem()?.type || "").toLowerCase();
    if (relativeParentLeaf && leaf === relativeParentLeaf && !relativeGrandparent && mediaType.includes("tv")) {
      return "Show folder";
    }
    return "File folder";
  }

  function folderPreviewLibraryRootPath(payload) {
    const scope = isPlainObject(payload?.scope) ? payload.scope : {};
    return String(scope.library_source_path || currentItem()?.library_source_root || currentItem()?.source_root || "").trim();
  }

  function folderPreviewPathSegments(path) {
    return normalizedFolderPreviewPath(path).split("/").filter(Boolean);
  }

  function folderPreviewSegmentsUnderLibraryRoot(folderPath, payload) {
    const rootKey = normalizedFolderPreviewPath(folderPreviewLibraryRootPath(payload));
    const folderKey = normalizedFolderPreviewPath(folderPath);
    if (!rootKey || !folderKey || folderKey === rootKey) return [];
    if (!folderKey.startsWith(rootKey + "/")) return [];
    const rootSegments = folderPreviewPathSegments(rootKey);
    const folderSegments = folderPreviewPathSegments(folderKey);
    return folderSegments.slice(rootSegments.length);
  }

  function folderPreviewIsNarrowShowOrSeasonScope(folderPath, payload) {
    const label = folderPreviewScopeLabel(folderPath, payload);
    return label === "Season folder" || label === "Show folder";
  }

  function folderPreviewIsLibraryRoot(folderPath, payload) {
    const scope = isPlainObject(payload?.scope) ? payload.scope : {};
    if (scope.is_library_root) return true;
    const folderKey = normalizedFolderPreviewPath(folderPath);
    const sourceRootKey = normalizedFolderPreviewPath(folderPreviewLibraryRootPath(payload));
    return Boolean(sourceRootKey && folderKey === sourceRootKey);
  }

  function folderPreviewIsNearLibraryRoot(folderPath, payload) {
    if (folderPreviewIsLibraryRoot(folderPath, payload)) return true;
    const segments = folderPreviewSegmentsUnderLibraryRoot(folderPath, payload);
    return Boolean(segments.length === 1 && !folderPreviewIsNarrowShowOrSeasonScope(folderPath, payload));
  }

  function folderPreviewLooksBroadLibraryPolicy(folderPath, payload) {
    if (folderPreviewIsLibraryRoot(folderPath, payload)) return true;
    if (!folderPreviewIsNearLibraryRoot(folderPath, payload)) return false;
    const impact = isPlainObject(payload?.impact) ? payload.impact : {};
    const knownCount = Number(impact.known_file_count || 0);
    const previewedCount = Number(impact.previewed_file_count || 0);
    return Boolean(knownCount > 1 || previewedCount > 1 || impact.partial);
  }

  function folderPreviewLibraryRootSaveApproved(payload) {
    return payload?.allow_library_root_folder_rule === true;
  }

  function folderPreviewSaveBlockedByLibraryRoot(folderPath, payload) {
    return folderPreviewIsLibraryRoot(folderPath, payload) && !folderPreviewLibraryRootSaveApproved(payload);
  }

  function folderPreviewLibraryHandoffMessage(folderPath, payload) {
    if (!folderPreviewLooksBroadLibraryPolicy(folderPath, payload)) return "";
    return "This looks like a broad library-level policy. Use Library settings for stable defaults.";
  }

  function setFolderPreviewLibraryHandoff(folderPath, payload) {
    const message = folderPreviewLibraryHandoffMessage(folderPath, payload);
    setTrackText("fo-folder-preview-library-note", message);
    const button = byId("fo-folder-preview-library-settings");
    if (button) button.hidden = !message;
    return message;
  }

  function folderPreviewAddScopeCandidate(candidates, seen, label, path) {
    const cleanPath = String(path || "").trim().replace(/[\\/]+$/, "");
    const key = normalizedFolderPreviewPath(cleanPath);
    if (!cleanPath || !key || seen.has(key)) return;
    const sourceRootKey = normalizedFolderPreviewPath(currentItem()?.library_source_root || currentItem()?.source_root || "");
    if (sourceRootKey && key === sourceRootKey) return;
    seen.add(key);
    candidates.push({ label: label || "Folder", path: cleanPath });
  }

  function folderPreviewScopeCandidates() {
    const candidates = [];
    const seen = new Set();
    const fileFolder = folderPreviewParentPath(currentPath());
    folderPreviewAddScopeCandidate(candidates, seen, folderPreviewScopeLabel(fileFolder, {}), fileFolder);

    const parent = folderPreviewParentPath(fileFolder);
    if (parent) {
      const currentLabel = folderPreviewScopeLabel(fileFolder, {});
      folderPreviewAddScopeCandidate(
        candidates,
        seen,
        currentLabel === "Season folder" ? "Show folder" : "Parent folder",
        parent,
      );
    }
    return candidates;
  }

  function renderFolderPreviewScopeOptions() {
    const select = byId("fo-folder-preview-scope-select");
    const candidates = folderPreviewScopeCandidates();
    if (!select) return candidates[0]?.path || "";

    const previous = String(select.value || "").trim();
    select.replaceChildren();
    candidates.forEach((candidate) => {
      const option = document.createElement("option");
      option.value = candidate.path;
      option.textContent = `${candidate.label}: ${candidate.path}`;
      select.appendChild(option);
    });
    if (previous && candidates.some((candidate) => candidate.path === previous)) {
      select.value = previous;
    }
    select.disabled = candidates.length <= 1;
    return String(select.value || candidates[0]?.path || "").trim();
  }

  function selectedFolderPreviewPath() {
    const selected = String(byId("fo-folder-preview-scope-select")?.value || "").trim();
    return selected || renderFolderPreviewScopeOptions() || folderPreviewParentPath(currentPath());
  }

  function folderPreviewSelectorFromTrack(track, kind) {
    const exact = exactSelectorForTrack(track, kind);
    if (!exact) return null;
    const selector = {};
    ["language", "codec", "title"].forEach((key) => {
      const value = String(exact[key] || "").trim();
      if (value) selector[key] = value;
    });
    if (kind === "audio" && hasOwnValue(exact, "channels")) selector.channels = exact.channels;
    if (kind === "subtitle" && hasOwnValue(exact, "forced")) selector.forced = Boolean(exact.forced);
    return Object.keys(selector).length ? selector : null;
  }

  function folderPreviewAppendRules(section, key, rules) {
    const cleanRules = (Array.isArray(rules) ? rules : []).filter((rule) => isPlainObject(rule) && Object.keys(rule).length);
    if (!cleanRules.length) return;
    section[key] = Array.isArray(section[key]) ? section[key].concat(cleanRules) : cleanRules.slice();
  }

  function buildFolderPreviewProposal() {
    const audio = {};
    const subtitles = {};
    const stripAll = Boolean(byId("fo-sub-strip-all")?.checked);
    folderPreviewAppendRules(audio, "keepTracks", langCodesToRules(parseLangList(byId("fo-audio-keep-langs")?.value)));
    folderPreviewAppendRules(audio, "dropTracks", langCodesToRules(parseLangList(byId("fo-audio-drop-langs")?.value)));
    if (!stripAll) {
      folderPreviewAppendRules(subtitles, "keepTracks", langCodesToRules(parseLangList(byId("fo-sub-keep-langs")?.value)));
      folderPreviewAppendRules(subtitles, "dropTracks", langCodesToRules(parseLangList(byId("fo-sub-drop-langs")?.value)));
    }

    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      if (control.disabled) return;
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop") return;
      const kind = control.dataset.foTrackKind || "";
      if (stripAll && kind === "subtitle") return;
      let track = null;
      try { track = JSON.parse(control.dataset.foTrackJson || ""); } catch (_err) { track = null; }
      const selector = folderPreviewSelectorFromTrack(track, kind);
      if (!selector) return;
      if (kind === "audio") folderPreviewAppendRules(audio, action === "keep" ? "keepTracks" : "dropTracks", [selector]);
      if (kind === "subtitle") folderPreviewAppendRules(subtitles, action === "keep" ? "keepTracks" : "dropTracks", [selector]);
    });

    const proposed = {};
    if (Object.keys(audio).length) proposed.audio = audio;
    if (Object.keys(subtitles).length) proposed.subtitles = subtitles;
    return proposed;
  }

  function folderPreviewWarningText(warning) {
    if (!isPlainObject(warning)) return String(warning || "").trim();
    const field = String(warning.field || "").trim();
    const message = String(warning.message || "").trim();
    if (!message) return "";
    return field ? `${field}: ${message}` : message;
  }

  function folderPreviewSelectorText(selector) {
    if (!isPlainObject(selector)) return "";
    const parts = [];
    ["language", "codec", "title", "channels", "forced"].forEach((key) => {
      if (!hasOwnValue(selector, key)) return;
      const value = selector[key];
      if (value === null || value === undefined || String(value).trim() === "") return;
      parts.push(`${key}=${value}`);
    });
    return parts.join(", ");
  }

  function appendFolderPreviewListItems(list, items, formatter) {
    if (!list) return;
    const values = (Array.isArray(items) ? items : []).map(formatter).filter(Boolean);
    if (!values.length) {
      const item = document.createElement("li");
      item.className = "fo-folder-preview-empty";
      item.textContent = "None reported.";
      list.appendChild(item);
      return;
    }
    values.forEach((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      list.appendChild(item);
    });
  }

  function renderFolderPreviewSelectors(proposed) {
    const list = byId("fo-folder-preview-selectors");
    if (!list) return;
    list.replaceChildren();
    const rows = [];
    [
      ["audio.keepTracks", proposed?.audio?.keepTracks],
      ["audio.dropTracks", proposed?.audio?.dropTracks],
      ["subtitles.keepTracks", proposed?.subtitles?.keepTracks],
      ["subtitles.dropTracks", proposed?.subtitles?.dropTracks],
    ].forEach(([field, rules]) => {
      (Array.isArray(rules) ? rules : []).forEach((rule) => {
        const text = folderPreviewSelectorText(rule);
        if (text) rows.push(`${field}: ${text}`);
      });
    });
    if (!rows.length) {
      const item = document.createElement("li");
      item.className = "fo-folder-preview-empty";
      item.textContent = "No language or signature selectors are set; preview will show folder coverage only.";
      list.appendChild(item);
      return;
    }
    rows.forEach((row) => {
      const item = document.createElement("li");
      item.textContent = row;
      list.appendChild(item);
    });
  }

  function folderPreviewProposalHasRules(proposed) {
    return Boolean(
      isPlainObject(proposed)
        && (
          Object.keys(isPlainObject(proposed.audio) ? proposed.audio : {}).length
          || Object.keys(isPlainObject(proposed.subtitles) ? proposed.subtitles : {}).length
        ),
    );
  }

  function setFolderPreviewConfirmationsChecked(checked) {
    [
      "fo-folder-confirm-future-files",
      "fo-folder-confirm-file-overrides",
      "fo-folder-confirm-no-stream-index",
    ].forEach((id) => {
      const input = byId(id);
      if (input) input.checked = Boolean(checked);
    });
  }

  function folderPreviewConfirmationsSatisfied() {
    return [
      "fo-folder-confirm-future-files",
      "fo-folder-confirm-file-overrides",
      "fo-folder-confirm-no-stream-index",
    ].every((id) => Boolean(byId(id)?.checked));
  }

  function setFolderPreviewSaveDisabled(disabled) {
    const saveButton = byId("fo-folder-preview-save");
    if (saveButton) saveButton.disabled = Boolean(disabled);
  }

  function folderPreviewSaveCanSubmit() {
    const payload = foLastFolderPreviewPayload;
    const request = foLastFolderPreviewRequest;
    return Boolean(
      payload
        && payload.ok !== false
        && payload.can_save_folder_rule !== false
        && request
        && request.folderPath
        && folderPreviewProposalHasRules(request.proposedOverride)
        && !folderPreviewSaveBlockedByLibraryRoot(request.folderPath, payload)
        && folderPreviewConfirmationsSatisfied(),
    );
  }

  function syncFolderPreviewSaveState() {
    setFolderPreviewSaveDisabled(!folderPreviewSaveCanSubmit());
  }

  function resetFolderPreviewResult(message = "") {
    foLastFolderPreviewPayload = null;
    foLastFolderPreviewRequest = null;
    setFolderPreviewSaveDisabled(true);
    if (message) setTrackText("fo-folder-preview-status", message);
  }

  function invalidateFolderPreviewAfterRuleChange() {
    const panel = byId("fo-folder-preview-panel");
    if (!panel || panel.hidden || (!foLastFolderPreviewPayload && !foLastFolderPreviewRequest)) return;
    resetFolderPreviewResult("Folder selectors changed. Run preview again before saving.");
  }

  function handleFolderPreviewScopeChange() {
    const folderPath = selectedFolderPreviewPath();
    resetFolderPreviewResult("Folder scope changed. Run preview before saving.");
    setFolderPreviewConfirmationsChecked(false);
    setTrackText("fo-folder-preview-path", folderPath || "Folder unavailable");
    setTrackText("fo-folder-preview-scope", folderPath ? `Appears to be: ${folderPreviewScopeLabel(folderPath, {})}.` : "");
    setTrackText("fo-folder-preview-counts", "");
    setTrackText("fo-folder-preview-library-note", "");
    const libraryButton = byId("fo-folder-preview-library-settings");
    if (libraryButton) libraryButton.hidden = true;
    renderFolderPreviewSelectors(buildFolderPreviewProposal());
    ["fo-folder-preview-conflicts", "fo-folder-preview-warnings", "fo-folder-preview-samples"].forEach(clearElementChildren);
  }

  function clearFolderRulePreviewPanel() {
    const panel = byId("fo-folder-preview-panel");
    if (panel) panel.hidden = true;
    foLastFolderPreviewPayload = null;
    foLastFolderPreviewRequest = null;
    setFolderPreviewConfirmationsChecked(false);
    setFolderPreviewSaveDisabled(true);
    [
      "fo-folder-preview-path",
      "fo-folder-preview-scope",
      "fo-folder-preview-counts",
      "fo-folder-preview-status",
      "fo-folder-preview-library-note",
    ].forEach((id) => {
      const el = byId(id);
      if (el) el.textContent = "";
    });
    ["fo-folder-preview-selectors", "fo-folder-preview-conflicts", "fo-folder-preview-warnings", "fo-folder-preview-samples"].forEach(clearElementChildren);
    const scopeSelect = byId("fo-folder-preview-scope-select");
    if (scopeSelect) scopeSelect.replaceChildren();
    const libraryButton = byId("fo-folder-preview-library-settings");
    if (libraryButton) libraryButton.hidden = true;
  }

  function renderFolderPreviewPayload(payload, folderPath, proposedOverride) {
    const panel = byId("fo-folder-preview-panel");
    if (panel) panel.hidden = false;
    const impact = isPlainObject(payload?.impact) ? payload.impact : {};
    const knownCount = Number(impact.known_file_count || 0);
    const previewedCount = Number(impact.previewed_file_count || 0);
    const partial = Boolean(impact.partial);
    const blockedByLibraryRoot = folderPreviewSaveBlockedByLibraryRoot(folderPath, payload);
    const canSavePreview = payload?.can_save_folder_rule !== false && !blockedByLibraryRoot;
    const hasRules = folderPreviewProposalHasRules(proposedOverride);
    const handoffMessage = folderPreviewLibraryHandoffMessage(folderPath, payload);
    setTrackText("fo-folder-preview-path", folderPath || "Folder unavailable");
    setTrackText("fo-folder-preview-scope", `Appears to be: ${folderPreviewScopeLabel(folderPath, payload)}.`);
    setTrackText("fo-folder-preview-counts", `Known files: ${knownCount}. Previewed samples: ${previewedCount}. Partial preview: ${partial ? "yes" : "no"}.`);
    setTrackText(
      "fo-folder-preview-status",
      !hasRules
        ? "Preview succeeded, but no language or signature selectors are set. Add selectors and preview again before saving."
        : canSavePreview
        ? "Preview succeeded. Confirm the folder-rule acknowledgements before saving. Future files under this folder may be affected."
        : blockedByLibraryRoot
        ? `${handoffMessage} Folder-rule save is blocked for library-root scope.`
        : "Preview succeeded, but this folder scope cannot be saved here.",
    );
    setFolderPreviewLibraryHandoff(folderPath, payload);
    renderFolderPreviewSelectors(proposedOverride);

    const conflicts = byId("fo-folder-preview-conflicts");
    if (conflicts) {
      conflicts.replaceChildren();
      appendFolderPreviewListItems(conflicts, payload?.conflicts, (conflict) => {
        if (!isPlainObject(conflict)) return "";
        const path = String(conflict.path || "").trim();
        const reason = String(conflict.reason || "").replace(/_/g, " ").trim();
        return [path, reason || "override conflict"].filter(Boolean).join(" — ");
      });
    }

    const warnings = byId("fo-folder-preview-warnings");
    if (warnings) {
      warnings.replaceChildren();
      const aggregateWarnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
      const sampleWarnings = [];
      (Array.isArray(payload?.sample_rows) ? payload.sample_rows : []).forEach((sample) => {
        (Array.isArray(sample?.warnings) ? sample.warnings : []).forEach((warning) => sampleWarnings.push(warning));
      });
      appendFolderPreviewListItems(warnings, aggregateWarnings.concat(sampleWarnings), folderPreviewWarningText);
    }

    const samples = byId("fo-folder-preview-samples");
    if (samples) {
      samples.replaceChildren();
      appendFolderPreviewListItems(samples, payload?.sample_rows, (sample) => {
        if (!isPlainObject(sample)) return "";
        const path = String(sample.path || "").trim();
        const audioCount = Number(sample.audio_track_count || 0);
        const subtitleCount = Number(sample.subtitle_track_count || 0);
        const audioMatches = Array.isArray(sample.matched_audio_tracks) ? sample.matched_audio_tracks.length : 0;
        const subtitleMatches = Array.isArray(sample.matched_subtitle_tracks) ? sample.matched_subtitle_tracks.length : 0;
        return `${path || "Sample row"} — audio ${audioCount}, subtitles ${subtitleCount}, matched audio ${audioMatches}, matched subtitles ${subtitleMatches}`;
      });
    }
    syncFolderPreviewSaveState();
  }

  async function openFolderRulePreviewPanel() {
    if (!currentPath()) {
      setStatus("No file selected for folder preview.");
      return;
    }
    const panel = byId("fo-folder-preview-panel");
    if (panel) panel.hidden = false;
    renderFolderPreviewScopeOptions();
    const folderPath = selectedFolderPreviewPath();
    if (!folderPath) {
      setStatus("Cannot derive a folder path from this file.");
      return;
    }
    resetFolderPreviewResult("");
    setFolderPreviewConfirmationsChecked(false);
    const proposedOverride = buildFolderPreviewProposal();
    setTrackText("fo-folder-preview-path", folderPath);
    setTrackText("fo-folder-preview-scope", "Checking folder scope...");
    setTrackText("fo-folder-preview-counts", "");
    setTrackText("fo-folder-preview-status", "Loading folder impact preview...");
    renderFolderPreviewSelectors(proposedOverride);
    ["fo-folder-preview-conflicts", "fo-folder-preview-warnings", "fo-folder-preview-samples"].forEach(clearElementChildren);

    try {
      const result = await apiPost("/api/queue/file-overrides/folder-preview", {
        folder_path: folderPath,
        proposed_override: proposedOverride,
        options: {
          sample_limit: 25,
          use_cached_track_metadata_only: true,
        },
      });
      if (!result || result.ok === false) {
        setTrackText("fo-folder-preview-status", "Folder preview failed: " + backendErrorMessage(result, "Folder preview failed."));
        return;
      }
      foLastFolderPreviewPayload = result;
      foLastFolderPreviewRequest = { folderPath, proposedOverride };
      renderFolderPreviewPayload(result, folderPath, proposedOverride);
    } catch (err) {
      setTrackText("fo-folder-preview-status", "Folder preview failed: " + (err.message || err));
    }
  }

  async function saveFolderRuleForPreview() {
    if (!foLastFolderPreviewPayload || !foLastFolderPreviewRequest) {
      setTrackText("fo-folder-preview-status", "Run a successful folder preview before saving.");
      syncFolderPreviewSaveState();
      return;
    }
    if (!folderPreviewProposalHasRules(foLastFolderPreviewRequest.proposedOverride)) {
      setTrackText("fo-folder-preview-status", "Add at least one language or signature selector before saving a folder rule.");
      syncFolderPreviewSaveState();
      return;
    }
    if (!folderPreviewConfirmationsSatisfied()) {
      setTrackText("fo-folder-preview-status", "Confirm all folder-rule acknowledgements before saving.");
      syncFolderPreviewSaveState();
      return;
    }
    if (!folderPreviewSaveCanSubmit()) {
      setTrackText("fo-folder-preview-status", "This folder preview cannot be saved.");
      syncFolderPreviewSaveState();
      return;
    }

    setFolderPreviewSaveDisabled(true);
    setTrackText("fo-folder-preview-status", "Saving folder rule...");
    try {
      const result = await apiPost("/api/queue/file-overrides/folder-rule", {
        folder_path: foLastFolderPreviewRequest.folderPath,
        override: foLastFolderPreviewRequest.proposedOverride,
        confirmation: {
          acknowledged_future_files: true,
          acknowledged_file_overrides_win: true,
        },
      });
      if (!result || result.ok === false) {
        setTrackText("fo-folder-preview-status", "Folder rule save failed: " + backendErrorMessage(result, "Folder rule save failed."));
        syncFolderPreviewSaveState();
        return;
      }
      await loadEffectiveForPath(currentPath(), currentItem());
      setTrackText("fo-folder-preview-status", "Folder rule saved. Effective settings and queue state refreshed when available.");
      setStatus("Folder rule saved. Takes effect on next pipeline round.");
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      if (typeof refreshAll === "function") await refreshAll();
      if (!byId("fo-folder-rules-panel")?.hidden) await loadFolderRulesForDrawer();
      foLastFolderPreviewPayload = null;
      foLastFolderPreviewRequest = null;
      setFolderPreviewConfirmationsChecked(false);
      setFolderPreviewSaveDisabled(true);
    } catch (err) {
      setTrackText("fo-folder-preview-status", "Folder rule save failed: " + (err.message || err));
      syncFolderPreviewSaveState();
    }
  }

  function folderRulePathLooksFile(path) {
    const text = String(path || "").trim();
    if (!text || /[\\/]$/.test(text)) return false;
    const leaf = folderPreviewLeaf(text).toLowerCase();
    return Array.from(FOLDER_RULE_FILE_SUFFIXES).some((suffix) => leaf.endsWith(suffix));
  }

  function folderRuleEntriesFromManifestPayload(payload) {
    const entries = isPlainObject(payload?.entries) ? payload.entries : {};
    return Object.entries(entries)
      .filter(([path, entry]) => String(path || "").trim() && isPlainObject(entry) && !folderRulePathLooksFile(path))
      .map(([path, entry]) => ({ path, entry }))
      .sort((left, right) => left.path.localeCompare(right.path));
  }

  function folderRuleOverrideForPreview(entry) {
    const proposed = {};
    if (isPlainObject(entry?.audio)) proposed.audio = entry.audio;
    if (isPlainObject(entry?.subtitles)) proposed.subtitles = entry.subtitles;
    return proposed;
  }

  function folderRuleSelectorSummary(rule) {
    if (typeof rule === "string") {
      const language = rule.trim();
      return language ? `language=${language}` : "";
    }
    return folderPreviewSelectorText(rule);
  }

  function folderRuleSummary(entry) {
    const rows = [];
    [
      ["audio.keepTracks", entry?.audio?.keepTracks],
      ["audio.dropTracks", entry?.audio?.dropTracks],
      ["subtitles.keepTracks", entry?.subtitles?.keepTracks],
      ["subtitles.dropTracks", entry?.subtitles?.dropTracks],
    ].forEach(([field, rules]) => {
      (Array.isArray(rules) ? rules : []).forEach((rule) => {
        const text = folderRuleSelectorSummary(rule);
        if (text) rows.push(`${field}: ${text}`);
      });
    });
    if (hasOwnValue(entry?.subtitles, "stripAll")) {
      rows.push(`subtitles.stripAll=${Boolean(entry.subtitles.stripAll)}`);
    }
    if (rows.length) return rows.join("; ");
    if (isPlainObject(entry?.routing) || isPlainObject(entry?.video)) {
      return "Contains processing settings; use Library settings for broad stable defaults.";
    }
    return "No folder-safe audio/subtitle selectors in this entry.";
  }

  function folderRuleNode(index) {
    return document.querySelector(`[data-fo-folder-rule-index="${index}"]`);
  }

  function folderRuleConflictText(conflict) {
    if (!isPlainObject(conflict)) return String(conflict || "").trim();
    const path = String(conflict.path || "").trim();
    const reason = String(conflict.reason || "override conflict").replace(/_/g, " ").trim();
    return [path, reason].filter(Boolean).join(" — ");
  }

  function renderFolderRuleConflicts(list, conflicts) {
    if (!list) return;
    list.replaceChildren();
    appendFolderPreviewListItems(list, conflicts, folderRuleConflictText);
  }

  function clearFolderRuleManagementPanel() {
    const panel = byId("fo-folder-rules-panel");
    if (panel) panel.hidden = true;
    foFolderRules = [];
    clearElementChildren("fo-folder-rules-list");
    setTrackText("fo-folder-rules-status", "");
  }

  function renderFolderRules(rules) {
    const panel = byId("fo-folder-rules-panel");
    const list = byId("fo-folder-rules-list");
    if (panel) panel.hidden = false;
    foFolderRules = Array.isArray(rules) ? rules : [];
    if (!list) return;
    list.replaceChildren();

    if (!foFolderRules.length) {
      const empty = document.createElement("li");
      empty.className = "fo-folder-rule-item";
      empty.textContent = "No folder-prefix rules are saved.";
      list.appendChild(empty);
      return;
    }

    foFolderRules.forEach((rule, index) => {
      const item = document.createElement("li");
      item.className = "fo-folder-rule-item";
      item.dataset.foFolderRuleIndex = String(index);

      const path = document.createElement("p");
      path.className = "fo-folder-rule-path";
      path.textContent = rule.path;
      item.appendChild(path);

      const summary = document.createElement("p");
      summary.className = "fo-folder-rule-summary";
      summary.textContent = folderRuleSummary(rule.entry);
      item.appendChild(summary);

      const meta = document.createElement("p");
      meta.className = "fo-folder-rule-meta";
      meta.dataset.foFolderRuleMeta = "";
      meta.textContent = "Affected count not previewed yet.";
      item.appendChild(meta);

      const libraryNote = document.createElement("p");
      libraryNote.className = "fo-folder-rule-library-note";
      libraryNote.dataset.foFolderRuleLibraryNote = "";
      item.appendChild(libraryNote);

      const conflicts = document.createElement("ul");
      conflicts.className = "fo-folder-rule-conflicts";
      conflicts.dataset.foFolderRuleConflicts = "";
      renderFolderRuleConflicts(conflicts, []);
      item.appendChild(conflicts);

      const actions = document.createElement("div");
      actions.className = "fo-folder-rule-actions";
      const preview = document.createElement("button");
      preview.type = "button";
      preview.className = "secondary-button";
      preview.dataset.foFolderRulePreview = String(index);
      preview.textContent = "Re-preview";
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "secondary-button";
      clear.dataset.foFolderRuleClear = String(index);
      clear.textContent = "Clear folder rule";
      actions.append(preview, clear);
      item.appendChild(actions);

      list.appendChild(item);
    });
  }

  function renderFolderRulePreviewResult(rule, index, payload) {
    const item = folderRuleNode(index);
    if (!item) return;
    const meta = item.querySelector("[data-fo-folder-rule-meta]");
    const libraryNote = item.querySelector("[data-fo-folder-rule-library-note]");
    const conflicts = item.querySelector("[data-fo-folder-rule-conflicts]");
    const impact = isPlainObject(payload?.impact) ? payload.impact : {};
    const knownCount = Number(impact.known_file_count || 0);
    const previewedCount = Number(impact.previewed_file_count || 0);
    const partial = Boolean(impact.partial);
    if (meta) {
      meta.textContent = `Known files: ${knownCount}. Previewed samples: ${previewedCount}. Partial preview: ${partial ? "yes" : "no"}.`;
    }
    if (libraryNote) {
      libraryNote.textContent = folderPreviewLibraryHandoffMessage(rule.path, payload);
    }
    renderFolderRuleConflicts(conflicts, payload?.conflicts);
  }

  async function previewFolderRuleForManagement(rule, index, options = {}) {
    if (!rule || !rule.path) return;
    const item = folderRuleNode(index);
    const meta = item?.querySelector?.("[data-fo-folder-rule-meta]");
    if (meta) meta.textContent = "Loading cached preview...";
    if (!options.silent) setTrackText("fo-folder-rules-status", "Loading folder rule preview...");

    try {
      const result = await apiPost("/api/queue/file-overrides/folder-preview", {
        folder_path: rule.path,
        proposed_override: folderRuleOverrideForPreview(rule.entry),
        options: {
          sample_limit: 25,
          use_cached_track_metadata_only: true,
        },
      });
      if (!result || result.ok === false) {
        const message = "Folder rule preview failed: " + backendErrorMessage(result, "Folder rule preview failed.");
        if (meta) meta.textContent = message;
        if (!options.silent) setTrackText("fo-folder-rules-status", message);
        return;
      }
      renderFolderRulePreviewResult(rule, index, result);
      if (!options.silent) setTrackText("fo-folder-rules-status", "Folder rule preview refreshed.");
    } catch (err) {
      const message = "Folder rule preview failed: " + (err.message || err);
      if (meta) meta.textContent = message;
      if (!options.silent) setTrackText("fo-folder-rules-status", message);
    }
  }

  async function loadFolderRulesForDrawer() {
    const panel = byId("fo-folder-rules-panel");
    if (panel) panel.hidden = false;
    setTrackText("fo-folder-rules-status", "Loading folder rules...");
    try {
      const result = await apiGet(fileOverridesRoute);
      const rules = folderRuleEntriesFromManifestPayload(result);
      renderFolderRules(rules);
      setTrackText(
        "fo-folder-rules-status",
        rules.length
          ? `${rules.length} folder rule(s) loaded. Re-preview uses cached track metadata only. File-level overrides remain when a folder rule is cleared.`
          : "No folder-prefix rules are saved.",
      );
      await Promise.allSettled(rules.map((rule, index) => previewFolderRuleForManagement(rule, index, { silent: true })));
    } catch (err) {
      renderFolderRules([]);
      setTrackText("fo-folder-rules-status", "Error loading folder rules: " + (err.message || err));
    }
  }

  async function clearFolderRuleFromManagement(rule, index) {
    if (!rule || !rule.path) return;
    const confirmed = typeof window.confirm !== "function"
      || window.confirm(`Clear folder rule for ${rule.path}? File-level overrides remain.`);
    if (!confirmed) return;

    const item = folderRuleNode(index);
    const meta = item?.querySelector?.("[data-fo-folder-rule-meta]");
    if (meta) meta.textContent = "Clearing folder rule...";
    setTrackText("fo-folder-rules-status", "Clearing folder rule...");
    try {
      const result = await apiPost("/api/queue/file-overrides/folder-rule", {
        folder_path: rule.path,
        clear: true,
      });
      if (!result || result.ok === false) {
        setTrackText("fo-folder-rules-status", "Folder rule clear failed: " + backendErrorMessage(result, "Folder rule clear failed."));
        return;
      }
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      if (currentPath()) await loadEffectiveForPath(currentPath(), currentItem());
      if (typeof refreshAll === "function") await refreshAll();
      await loadFolderRulesForDrawer();
      setStatus("Folder rule cleared. File-level overrides remain.");
      setTrackText("fo-folder-rules-status", "Folder rule cleared. File-level overrides remain.");
    } catch (err) {
      setTrackText("fo-folder-rules-status", "Folder rule clear failed: " + (err.message || err));
    }
  }

  function handleFolderRuleManagementClick(event) {
    const previewButton = event.target?.closest?.("[data-fo-folder-rule-preview]");
    if (previewButton) {
      const index = Number(previewButton.dataset.foFolderRulePreview);
      const rule = foFolderRules[index];
      if (rule) previewFolderRuleForManagement(rule, index);
      return;
    }
    const clearButton = event.target?.closest?.("[data-fo-folder-rule-clear]");
    if (clearButton) {
      const index = Number(clearButton.dataset.foFolderRuleClear);
      const rule = foFolderRules[index];
      if (rule) clearFolderRuleFromManagement(rule, index);
    }
  }

  function openLibrarySettingsFromFolderHandoff() {
    closeDrawer();
    if (typeof window.showPage === "function") {
      window.showPage("libraries");
    } else {
      setStatus("Open the Libraries page to change broad stable defaults.");
    }
  }

    return {
      clearFolderRuleManagementPanel,
      clearFolderRulePreviewPanel,
      handleFolderPreviewScopeChange,
      handleFolderRuleManagementClick,
      invalidateFolderPreviewAfterRuleChange,
      loadFolderRulesForDrawer,
      openFolderRulePreviewPanel,
      openLibrarySettingsFromFolderHandoff,
      saveFolderRuleForPreview,
      syncFolderPreviewSaveState,
    };
  }

  window.__queueFileOverridesFolderPreviewModule = { createFileOverridesFolderPreviewModule };
})();
