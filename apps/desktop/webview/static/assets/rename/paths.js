// Rename path intake, browse, drag/drop expansion, and source-origin summaries.
(function () {
  "use strict";

  function createRenamePathsModule(deps = {}) {
    const {
      apiPost = null,
      appendCommandResult = () => {},
      byId = () => null,
      renamePathLines = () => [],
      renameSourceLabelFromRow = () => "",
      renameSourcePathFromRow = () => "",
      RENAME_MEDIA_EXTENSIONS = new Set(),
      RENAME_SIDECAR_SUFFIXES = [],
      setRenameStatusLine = () => {},
      setText = () => {},
      state = {},
      syncRenameCommandButtons = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;
    const windowRef = deps.windowRef || window;

  function renameCurrentPathValues() {
    return renamePathLines().map((line) => line.trim()).filter(Boolean);
  }

  function renamePathLeaf(value) {
    const parts = String(value || "").trim().split(/[\\/]+/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function renamePathExtension(value) {
    const leaf = renamePathLeaf(value);
    const index = leaf.lastIndexOf(".");
    return index >= 0 ? leaf.slice(index).toLowerCase() : "";
  }

  function renameIsSidecarPath(value) {
    const leaf = renamePathLeaf(value).toLowerCase();
    return RENAME_SIDECAR_SUFFIXES.some((suffix) => leaf.endsWith(suffix));
  }

  function classifyRenamePathValues(paths = renameCurrentPathValues()) {
    const seenMedia = new Set();
    const media = [];
    const sidecars = [];
    const nonMedia = [];
    const duplicates = [];
    paths.forEach((path) => {
      const text = String(path || "").trim();
      if (!text) return;
      if (RENAME_MEDIA_EXTENSIONS.has(renamePathExtension(text))) {
        const key = text.toLowerCase();
        if (seenMedia.has(key)) {
          duplicates.push(text);
          return;
        }
        seenMedia.add(key);
        media.push(text);
      } else if (renameIsSidecarPath(text)) {
        sidecars.push(text);
      } else {
        nonMedia.push(text);
      }
    });
    return {
      raw: paths.length,
      media,
      sidecars,
      nonMedia,
      duplicates,
      ignored: sidecars.length + nonMedia.length + duplicates.length,
    };
  }

  function renameLooksLikeAbsolutePath(value) {
    const text = String(value || "").trim();
    return Boolean(
      /^[a-zA-Z]:[\\/]/.test(text)
      || /^\\\\[^\\]+\\[^\\]+/.test(text)
      || /^\/[^/]/.test(text)
    );
  }

  function normalizeRenameDroppedPathValues(values) {
    const seen = new Set();
    const paths = [];
    (Array.isArray(values) ? values : []).forEach((value) => {
      const text = String(value || "").trim();
      const key = text.toLowerCase();
      if (!text || !renameLooksLikeAbsolutePath(text) || seen.has(key)) return;
      seen.add(key);
      paths.push(text);
    });
    return paths;
  }

  function renameDroppedPathFromFile(file) {
    if (!file || typeof file !== "object") return "";
    const candidates = [file.path, file.fullPath, file.webkitRelativePath];
    for (const candidate of candidates) {
      const text = String(candidate || "").trim();
      if (renameLooksLikeAbsolutePath(text)) return text;
    }
    return "";
  }

  function renameDroppedPathValuesFromDataTransfer(dataTransfer) {
    return normalizeRenameDroppedPathValues(
      Array.from(dataTransfer?.files || []).map(renameDroppedPathFromFile)
    );
  }

  function renameDroppedPathValuesFromBridgeDetail(detail) {
    if (!detail || typeof detail !== "object") return [];
    return normalizeRenameDroppedPathValues(Array.isArray(detail.paths) ? detail.paths : []);
  }

  async function handleRenameDroppedPaths(paths, sourceLabel = "Drag and drop") {
    const normalized = normalizeRenameDroppedPathValues(paths);
    if (!normalized.length) {
      renderRenameFileSourceSummary("Drop did not expose full filesystem paths. Use Browse Files / Add files from folder, or paste the full path manually.");
      return 0;
    }
    if (state.browseInFlight || state.previewInFlight || state.applyInFlight) {
      renderRenameFileSourceSummary("Rename path browser is busy. Wait for the current Rename command to finish.");
      return 0;
    }
    state.browseInFlight = true;
    syncRenameCommandButtons();
    renderRenameFileSourceSummary(`${sourceLabel || "Drag and drop"} resolving dropped files/folders...`);
    try {
      const result = await apiPost("/api/rename/browse", {
        selection_mode: "folder_files",
        paths: normalized,
        source: "drop",
      });
      appendCommandResult(result);
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const resolved = Array.isArray(data.paths) ? data.paths : [];
      if (!result?.ok) {
        renderRenameFileSourceSummary(result?.message || "Dropped path resolution failed.");
        return 0;
      }
      if (!resolved.length) {
        const suffix = renameIgnoredPathSuffix(data);
        renderRenameFileSourceSummary(`${sourceLabel || "Drag and drop"} found no media files to stage.${suffix ? ` ${suffix}` : ""}`);
        return 0;
      }
      return appendResolvedRenameBrowsePaths(data, sourceLabel, "drop");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "rename.browse",
        ok: false,
        severity: "error",
        message: `Dropped path resolution failed:\n${message}`,
      });
      const classified = classifyRenamePathValues(normalized);
      if (classified.media.length) {
        return appendRenamePaths(classified.media, sourceLabel, "drop", "Backend dropped-folder expansion failed; staged dropped media files only.");
      }
      renderRenameFileSourceSummary(`Dropped path resolution failed:\n${message}`);
      return 0;
    } finally {
      state.browseInFlight = false;
      syncRenameCommandButtons();
    }
  }

  function renameDropZoneIsVisible(zone) {
    const page = zone?.closest?.('[data-page-panel="rename"]');
    return !page || page.classList?.contains("is-visible");
  }

  function renamePathOriginKey(path) {
    return String(path || "").trim().toLowerCase();
  }

  function rememberRenamePathOrigins(paths, origin) {
    const label = String(origin || "").trim();
    if (!label) return;
    (Array.isArray(paths) ? paths : []).forEach((path) => {
      const key = renamePathOriginKey(path);
      if (key) state.pathOrigins[key] = label;
    });
  }

  function pruneRenamePathOrigins(paths = renameCurrentPathValues()) {
    const current = new Set(paths.map(renamePathOriginKey).filter(Boolean));
    Object.keys(state.pathOrigins).forEach((key) => {
      if (!current.has(key)) delete state.pathOrigins[key];
    });
  }

  function renamePathOriginCounts(paths = renameCurrentPathValues()) {
    const counts = {};
    paths.forEach((path) => {
      const origin = state.pathOrigins[renamePathOriginKey(path)] || "manual";
      counts[origin] = (counts[origin] || 0) + 1;
    });
    return counts;
  }

  function renamePathOriginSummary(paths = renameCurrentPathValues()) {
    const counts = renamePathOriginCounts(paths);
    const parts = Object.keys(counts)
      .sort()
      .map((origin) => `${origin}=${counts[origin]}`);
    return parts.length ? `Origins: ${parts.join(", ")}` : "";
  }

  function renderRenameFileSourceSummary(message = "") {
    const paths = renameCurrentPathValues();
    const classified = classifyRenamePathValues(paths);
    pruneRenamePathOrigins(paths);
    const queueRows = typeof windowRef.getLastQueueRows === "function"
      ? windowRef.getLastQueueRows()
      : (windowRef.mediaPipelineQueueView?.getLastQueueRows?.() || []);
    const selectedQueue = typeof windowRef.getSelectedQueueRow === "function"
      ? windowRef.getSelectedQueueRow()
      : (windowRef.mediaPipelineQueueView?.getSelectedQueueRow?.() || null);
    const selectedPath = renameSourcePathFromRow(selectedQueue);
    const mediaCount = classified.media.length;
    setRenameStatusLine(
      "rename-file-source-status",
      paths.length ? `${mediaCount} media / ${paths.length} path${paths.length === 1 ? "" : "s"}` : "No paths",
      mediaCount ? "ready" : paths.length ? "warning" : "empty"
    );
    setText("rename-file-source-summary", [
      message,
      paths.length ? `Source paths staged: ${paths.length}` : "No source paths staged.",
      paths.length ? `Media paths eligible for preview/apply: ${mediaCount}` : "",
      classified.ignored
        ? `Ignored by preview/apply: ${classified.ignored} (${classified.sidecars.length} sidecar, ${classified.nonMedia.length} non-media, ${classified.duplicates.length} duplicate media)`
        : "",
      paths.length ? renamePathOriginSummary(paths) : "",
      `Loaded Queue rows: ${Array.isArray(queueRows) ? queueRows.length : 0}`,
      `Selected Queue source: ${selectedPath || "(none)"}`,
      paths.length ? `First staged path: ${paths[0]}` : "",
      mediaCount ? `First media path: ${classified.media[0]}` : "",
    ].filter(Boolean).join("\n"));
  }

  function appendRenamePaths(paths, sourceLabel, origin = "", messageSuffix = "") {
    const input = byId("rename-paths");
    if (!input) return 0;
    const current = renameCurrentPathValues();
    const seen = new Set(current.map((line) => line.toLowerCase()));
    const additions = [];
    (Array.isArray(paths) ? paths : []).forEach((path) => {
      const text = String(path || "").trim();
      const key = text.toLowerCase();
      if (!text || seen.has(key)) return;
      seen.add(key);
      additions.push(text);
    });
    const suffix = messageSuffix ? ` ${messageSuffix}` : "";
    if (!additions.length) {
      renderRenameFileSourceSummary(`${sourceLabel || "Source"} added no new paths.${suffix}`);
      return 0;
    }
    input.value = [...current, ...additions].join("\n");
    rememberRenamePathOrigins(additions, origin || "manual");
    renderRenameFileSourceSummary(`${sourceLabel || "Source"} added ${additions.length} path${additions.length === 1 ? "" : "s"}.${suffix}`);
    syncRenameCommandButtons();
    return additions.length;
  }

  function renameIgnoredPathSuffix(data = {}) {
    const ignored = Number(data.ignored_path_count || 0);
    const ignoredSidecars = Number(data.ignored_sidecar_count || 0);
    if (!ignored) return "";
    return `Ignored ${ignored} non-media path${ignored === 1 ? "" : "s"}${ignoredSidecars ? ` including ${ignoredSidecars} sidecar path${ignoredSidecars === 1 ? "" : "s"}` : ""}.`;
  }

  function appendResolvedRenameBrowsePaths(data, sourceLabel, origin) {
    const paths = Array.isArray(data?.paths) ? data.paths : [];
    return appendRenamePaths(paths, sourceLabel, origin, renameIgnoredPathSuffix(data));
  }

  function addRenamePathFromInput() {
    const input = byId("rename-add-path-input");
    const path = String(input?.value || "").trim();
    if (!path) {
      renderRenameFileSourceSummary("Enter or paste a source path, then click Add manual path.");
      return 0;
    }
    const added = appendRenamePaths([path], "Manual path", "manual");
    if (added && input) input.value = "";
    syncRenameCommandButtons();
    return added;
  }

  async function browseRenamePaths(selectionMode = "files") {
    if (state.browseInFlight || state.previewInFlight || state.applyInFlight) {
      renderRenameFileSourceSummary("Rename path browser is busy. Wait for the current Rename command to finish.");
      return;
    }
    const rawMode = String(selectionMode || "").toLowerCase();
    const mode = rawMode === "folder" || rawMode === "folder_files" ? rawMode : "files";
    const currentPaths = renameCurrentPathValues();
    const typedPath = String(byId("rename-add-path-input")?.value || "").trim();
    const initialPath = currentPaths[0] || typedPath;
    state.browseInFlight = true;
    syncRenameCommandButtons();
    renderRenameFileSourceSummary(mode === "folder" ? "Opening Windows folder browser..." : "Opening Windows file browser...");
    try {
      const result = await apiPost("/api/rename/browse", { selection_mode: mode, initial_path: initialPath });
      appendCommandResult(result);
      const data = result.data && typeof result.data === "object" ? result.data : {};
      const paths = Array.isArray(data.paths) ? data.paths : [];
      if (!result.ok) {
        renderRenameFileSourceSummary(result.message || "Windows file browser failed.");
        return;
      }
      if (data.canceled || !paths.length) {
        renderRenameFileSourceSummary(result.message || "Windows file browser canceled.");
        return;
      }
      const folderMode = mode === "folder" || mode === "folder_files";
      appendResolvedRenameBrowsePaths(data, folderMode ? "Windows folder browser" : "Windows file browser", folderMode ? "folder" : "browse");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const routeMissing = String(message || "").trim().toLowerCase() === "not found";
      const displayMessage = routeMissing
        ? "Rename path browser route is not available in the running backend. Restart the Local API/Tauri shell, then open Rename again."
        : `Windows file browser failed:\n${message}`;
      appendCommandResult({
        command: "rename.browse",
        ok: false,
        severity: "error",
        message: displayMessage,
      });
      renderRenameFileSourceSummary(displayMessage);
    } finally {
      state.browseInFlight = false;
      syncRenameCommandButtons();
    }
  }


    return {
      renameCurrentPathValues,
      renamePathLeaf,
      renamePathExtension,
      renameIsSidecarPath,
      classifyRenamePathValues,
      renameLooksLikeAbsolutePath,
      normalizeRenameDroppedPathValues,
      renameDroppedPathFromFile,
      renameDroppedPathValuesFromDataTransfer,
      renameDroppedPathValuesFromBridgeDetail,
      handleRenameDroppedPaths,
      renameDropZoneIsVisible,
      renamePathOriginKey,
      rememberRenamePathOrigins,
      pruneRenamePathOrigins,
      renamePathOriginCounts,
      renamePathOriginSummary,
      renderRenameFileSourceSummary,
      appendRenamePaths,
      renameIgnoredPathSuffix,
      appendResolvedRenameBrowsePaths,
      addRenamePathFromInput,
      browseRenamePaths,
    };
  }

  window.__renamePathsModule = { createRenamePathsModule };
})();
