(function () {
  function createSettingsLibrariesSummaryModule(deps = {}) {
    const {
      byId,
      captureOpenOverrideSections,
      escapeHtml,
      localStorage,
      renderCard,
      renderLibraryStateStrip,
      renderLibraryWarningSummary,
      setText,
      slug,
      state,
      text,
    } = deps;

    function libraryPaneId(profileId) {
      return `settings-library-pane-${slug(profileId, "library")}`;
    }
  
    function storedLibraryTabId(validIds) {
      try {
        const stored = localStorage.getItem("mediapipeline-library-profile") || localStorage.getItem("mediapipeline-library-tab") || "";
        if (validIds.includes(stored)) return stored;
      } catch (_error) {}
      if (validIds.includes(state.activeLibraryTabId)) return state.activeLibraryTabId;
      if (validIds.includes("movies")) return "movies";
      return validIds[0] || "";
    }
  
    function activateLibraryTab(libraryId, options = {}) {
      const tabBar = byId("settings-library-profile-nav");
      const list = byId("settings-library-profile-list");
      if (!tabBar || !list) return;
      const tabs = Array.from(tabBar.querySelectorAll("[data-library-profile-nav]"));
      const panes = Array.from(list.querySelectorAll("[data-library-profile-pane]"));
      const validIds = panes.map((pane) => pane.getAttribute("data-library-profile-pane") || "").filter(Boolean);
      const activeId = validIds.includes(libraryId) ? libraryId : storedLibraryTabId(validIds);
      const previousActiveId = state.activeLibraryTabId;
      state.activeLibraryTabId = activeId;
      tabs.forEach((tab) => {
        const active = tab.getAttribute("data-library-profile-nav") === activeId;
        if (active) tab.setAttribute("aria-current", "location");
        else tab.removeAttribute("aria-current");
      });
      panes.forEach((pane) => {
        pane.classList.toggle("is-active", pane.getAttribute("data-library-profile-pane") === activeId);
      });
      if (activeId !== previousActiveId) closeOverrideSections(activeId);
      try { localStorage.setItem("mediapipeline-library-profile", activeId); } catch (_error) {}
      renderActiveLibraryCommandState();
      updateLibrarySummarySelection();
      if (options.source !== "route-map") {
        window.mediaPipelineLibraryRouteMap?.selectProfile?.(activeId, { source: "library-editor" });
      }
      if (typeof window.updatePagePanelEmptyStates === "function") window.updatePagePanelEmptyStates();
    }
  
    function activateLibraryProfile(libraryId, options = {}) {
      activateLibraryTab(libraryId, options);
    }
  
    function closeOverrideSections(profileId) {
      if (profileId) state.openOverrideSectionsByLibrary.set(profileId, new Set());
      const pane = byId(libraryPaneId(profileId));
      if (!pane) return;
      pane.querySelectorAll("details[data-library-override-section]").forEach((section) => {
        section.open = false;
      });
    }
  
    function activeLibraryCard() {
      const activePane = byId("settings-library-profile-list")?.querySelector(".settings-library-profile-pane.is-active");
      return activePane?.querySelector(".settings-library-card") || null;
    }
  
    function activeLibraryProfileId(card = activeLibraryCard()) {
      return card?.dataset.libraryId || state.activeLibraryTabId || "";
    }
  
    function activeLibraryName(card = activeLibraryCard()) {
      const input = card?.querySelector('[data-library-field="name"]');
      const id = activeLibraryProfileId(card);
      return text(input?.value) || (id === "tv" ? "TV" : id === "movies" ? "Movies" : "Library");
    }
  
    function activeLibraryCanDelete(card = activeLibraryCard()) {
      const id = activeLibraryProfileId(card);
      return Boolean(id && id !== "movies" && id !== "tv");
    }
  
    function librarySummaryRows(payload = state.lastLibrarySummary) {
      return Array.isArray(payload?.rows) ? payload.rows : [];
    }
  
    function librarySummaryTotals(payload = state.lastLibrarySummary) {
      const totals = payload?.totals;
      return totals && typeof totals === "object" && !Array.isArray(totals) ? totals : {};
    }
  
    function librarySummaryCount(value) {
      if (value === null || value === undefined || value === "") return "-";
      const number = Number(value);
      if (!Number.isFinite(number)) return "-";
      return number.toLocaleString();
    }
  
    function librarySummaryStatusLabel(value) {
      const status = text(value || "not_scanned").toLowerCase();
      const labels = {
        complete: "Complete",
        partial: "Partial",
        scanning: "Scanning",
        not_scanned: "Not scanned",
        error: "Error",
        unavailable: "Unavailable",
      };
      return labels[status] || status.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }
  
    function librarySummaryTone(value) {
      const status = text(value || "not_scanned").toLowerCase();
      if (status === "complete") return "complete";
      if (status === "error" || status === "unavailable") return "error";
      if (status === "scanning") return "scanning";
      if (status === "partial") return "partial";
      return "not_scanned";
    }
  
    function librarySummaryStripItem(label, value, state = "ready") {
      return `<span data-state="${escapeHtml(state)}">${escapeHtml(label)}: ${escapeHtml(librarySummaryCount(value))}</span>`;
    }
  
    function librarySummaryDesignationLabel(value) {
      const designation = text(value || "auto").toLowerCase();
      const labels = {
        movie: "Movie",
        movies: "Movie",
        tv: "TV",
        television: "TV",
        auto: "Auto",
      };
      return labels[designation] || text(value || "Auto").replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }
  
    function librarySummaryStatusSymbol(value) {
      const tone = librarySummaryTone(value);
      if (tone === "complete") return "OK";
      if (tone === "error") return "!";
      if (tone === "scanning") return "...";
      if (tone === "partial") return "~";
      return "?";
    }
  
    function renderLibrarySummaryInspect(row, warnings, statusValue) {
      const statusLabel = librarySummaryStatusLabel(row.scan_status);
      const libraryName = text(row.name || row.library_id || "Library");
      const warningItems = warnings.length
        ? `<ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
        : '<p class="muted">No scan warnings reported.</p>';
      const partialNote = row.counts_truncated ? '<p class="muted">Counts are partial.</p>' : "";
      return `
        <details class="settings-library-summary-inspect" data-library-summary-inspect>
          <summary title="Inspect ${escapeHtml(libraryName)} status" aria-label="${escapeHtml(`${libraryName} status: ${statusLabel}. Activate to inspect.`)}">
            <span class="settings-library-status-symbol" data-state="${escapeHtml(statusValue)}" aria-hidden="true">${escapeHtml(librarySummaryStatusSymbol(row.scan_status))}</span>
            <span class="visually-hidden">${escapeHtml(statusLabel)}</span>
          </summary>
          <div class="settings-library-summary-inspect-body">
            <strong>${escapeHtml(statusLabel)}</strong>
            ${warningItems}
            ${partialNote}
            <dl>
              <div><dt>Last scan</dt><dd>${escapeHtml(formatLibrarySummaryTimestamp(row.last_scan_utc))}</dd></div>
              <div><dt>Sidecars</dt><dd>${escapeHtml(librarySummaryCount(row.sidecar_file_count))}</dd></div>
            </dl>
          </div>
        </details>`;
    }
  
    function formatLibrarySummaryTimestamp(value) {
      const raw = text(value);
      if (!raw) return "-";
      const parsed = new Date(raw);
      if (Number.isNaN(parsed.getTime())) return raw;
      return parsed.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      });
    }
  
    function setLibrarySummaryWarning(message) {
      const warning = byId("settings-library-summary-warning");
      if (!warning) return;
      const value = text(message);
      warning.textContent = value;
      warning.hidden = !value;
    }
  
    function updateLibrarySummarySelection() {
      const rows = Array.from(byId("settings-library-summary-rows")?.querySelectorAll("[data-library-summary-row]") || []);
      rows.forEach((row) => {
        const selected = row.getAttribute("data-library-summary-row") === state.activeLibraryTabId;
        row.classList.toggle("is-active", selected);
        row.setAttribute("aria-selected", selected ? "true" : "false");
      });
    }
  
    function renderLibrarySummary(payload = state.lastLibrarySummary) {
      if (payload && typeof payload === "object") state.lastLibrarySummary = payload;
      const effectivePayload = state.lastLibrarySummary;
      const container = byId("settings-library-summary-rows");
      if (!container) return;
      const rows = librarySummaryRows(effectivePayload);
      const totals = librarySummaryTotals(effectivePayload);
      const status = byId("settings-library-summary-status");
      const strip = byId("settings-library-summary-strip");
      const detail = byId("settings-library-summary-detail");
      const payloadError = text(effectivePayload?.error);
      const statusTone = payloadError ? "error" : rows.some((row) => librarySummaryTone(row.scan_status) === "scanning")
        ? "scanning"
        : totals.counts_truncated
          ? "partial"
          : rows.length
            ? "complete"
            : "not_scanned";
  
      if (status) {
        status.textContent = payloadError ? "Summary error" : rows.length ? `${rows.length} saved librar${rows.length === 1 ? "y" : "ies"}` : "No libraries loaded";
        status.dataset.state = statusTone;
      }
      if (strip) {
        strip.innerHTML = [
          librarySummaryStripItem("Libraries", totals.library_count ?? rows.length, rows.length ? "ready" : "empty"),
          librarySummaryStripItem("Enabled", totals.enabled_count ?? rows.filter((row) => row.enabled !== false).length, "ready"),
          librarySummaryStripItem("Media", totals.media_file_count, totals.counts_truncated ? "warning" : "ready"),
          librarySummaryStripItem("Sidecars", totals.sidecar_file_count, totals.counts_truncated ? "warning" : "ready"),
          librarySummaryStripItem("Unknown scans", totals.stale_or_unknown_scan_count, totals.stale_or_unknown_scan_count ? "warning" : "ready"),
        ].join("");
      }
      if (detail) {
        const sourceStatus = text(effectivePayload?.source_inventory_status || "not_loaded").replace(/[_-]+/g, " ");
        const scanStatus = text(effectivePayload?.queue_scan_status?.status || "idle").replace(/[_-]+/g, " ");
        detail.textContent = payloadError
          ? payloadError
          : `Scan evidence: ${scanStatus}; source inventory: ${sourceStatus}. Counts are backend-authored queue source inventory aggregates.`;
      }
  
      if (payloadError) {
        container.innerHTML = `<div class="settings-library-summary-empty" role="status">${escapeHtml(payloadError)}</div>`;
        setLibrarySummaryWarning(payloadError);
        return;
      }
      if (!rows.length) {
        container.innerHTML = '<div class="settings-library-summary-empty" role="status">No saved LibraryProfiles loaded. Add Library remains available in the editor controls.</div>';
        setLibrarySummaryWarning("");
        return;
      }
  
      container.innerHTML = rows.map((row) => {
        const libraryId = text(row.library_id);
        const statusValue = librarySummaryTone(row.scan_status);
        const warnings = Array.isArray(row.warnings) ? row.warnings.map((item) => text(item)).filter(Boolean) : [];
        const countSuffix = row.counts_truncated ? " (partial)" : "";
        const enabledLabel = row.enabled === false ? "Disabled" : "Enabled";
        const libraryName = row.name || libraryId || "Library";
        return `
          <article class="settings-library-summary-tile${libraryId === state.activeLibraryTabId ? " is-active" : ""}" data-library-summary-row="${escapeHtml(libraryId)}" data-state="${escapeHtml(statusValue)}" tabindex="0" role="listitem" aria-selected="${libraryId === state.activeLibraryTabId ? "true" : "false"}" aria-label="${escapeHtml(`${libraryName}, ${enabledLabel}, ${librarySummaryCount(row.media_file_count)} media files`)}">
            <div class="settings-library-summary-tile-heading">
              <span class="settings-library-summary-type">${escapeHtml(librarySummaryDesignationLabel(row.designation))}</span>
              ${renderLibrarySummaryInspect(row, warnings, statusValue)}
            </div>
            <strong class="settings-library-summary-name">${escapeHtml(libraryName)}</strong>
            <span class="settings-library-summary-enabled">${escapeHtml(enabledLabel)}</span>
            <div class="settings-library-summary-counts">
              <div>
                <strong>${escapeHtml(librarySummaryCount(row.media_file_count))}</strong>
                <span>Media files${escapeHtml(countSuffix)}</span>
              </div>
              <div>
                <strong>${escapeHtml(librarySummaryCount(row.sidecar_file_count))}</strong>
                <span>Sidecars${escapeHtml(countSuffix)}</span>
              </div>
            </div>
          </article>`;
      }).join("");
      setLibrarySummaryWarning((Array.isArray(effectivePayload?.warnings) ? effectivePayload.warnings : []).join("\n"));
      updateLibrarySummarySelection();
    }
  
    async function requestLibrarySummaryScan() {
      const scan = window.mediaPipelineQueueView?.requestQueueScan;
      if (typeof scan !== "function") {
        setText("settings-library-summary-status", "Queue scan unavailable");
        setLibrarySummaryWarning("Queue source scan controls are not loaded.");
        return;
      }
      const button = byId("settings-library-scan-sources-button");
      if (button) button.disabled = true;
      setText("settings-library-summary-status", "Scanning...");
      setLibrarySummaryWarning("");
      try {
        await scan();
        setText("settings-library-summary-status", "Scan requested");
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-library-summary-status", "Scan request failed");
        setLibrarySummaryWarning(`Queue source scan request failed: ${message}`);
      } finally {
        if (button) button.disabled = false;
      }
    }
  
    function renderActiveLibraryCommandState() {
      const card = activeLibraryCard();
      const name = activeLibraryName(card);
      const canDelete = activeLibraryCanDelete(card);
      setText("settings-library-active-title", `Selected library: ${name}`);
      setText("settings-library-editor-status", `Editing ${name}`);
      setText(
        "settings-library-active-detail",
        canDelete
          ? "Delete removes this profile from the staged LibraryProfiles patch; Save Library Profile persists after backend validation."
          : "Movie and TV are default state.profiles. They can be edited and saved, but they cannot be deleted."
      );
      const deleteButton = byId("settings-library-delete-button");
      if (deleteButton) {
        deleteButton.disabled = !canDelete;
        deleteButton.title = canDelete
          ? `Delete ${name} from the staged library state.profiles.`
          : "Movie and TV default state.profiles cannot be deleted.";
      }
      const defaultsButton = byId("settings-library-defaults-button");
      if (defaultsButton) {
        defaultsButton.disabled = !activeLibraryProfileId(card);
        defaultsButton.title = "Reset all explicit library overrides to inherited/default values in the editor. Stage Patch, Preview, and Save are still required.";
      }
      renderLibraryStateStrip();
    }
  
    function renderProfileCards(options = {}) {
      const list = byId("settings-library-profile-list");
      const tabBar = byId("settings-library-profile-nav");
      if (!list) return;
      captureOpenOverrideSections();
      if (tabBar) tabBar.replaceChildren();
      list.replaceChildren();
      state.profiles.forEach((profile) => {
        if (tabBar) {
          const tab = document.createElement("button");
          tab.type = "button";
          tab.className = "profile-nav-btn";
          tab.setAttribute("aria-controls", libraryPaneId(profile.id));
          tab.setAttribute("data-library-profile-nav", profile.id);
          tab.textContent = profile.name;
          tab.addEventListener("click", () => activateLibraryTab(profile.id));
          tabBar.appendChild(tab);
        }
        const pane = document.createElement("div");
        pane.id = libraryPaneId(profile.id);
        pane.className = "settings-tab-pane settings-library-profile-pane";
        pane.setAttribute("role", "region");
        pane.setAttribute("aria-label", `${profile.name} library profile`);
        pane.setAttribute("data-library-profile-pane", profile.id);
        pane.appendChild(renderCard(profile));
        list.appendChild(pane);
      });
      setText("settings-libraries-status", `${state.profiles.length} library profile(s) loaded`);
      const profileIds = state.profiles.map((profile) => profile.id);
      const preferredActiveId = text(options.activeProfileId);
      activateLibraryTab(profileIds.includes(preferredActiveId) ? preferredActiveId : storedLibraryTabId(profileIds));
      renderLibrarySummary();
      renderLibraryWarningSummary();
    }
  

    return {
      libraryPaneId,
      storedLibraryTabId,
      activateLibraryTab,
      activateLibraryProfile,
      closeOverrideSections,
      activeLibraryCard,
      activeLibraryProfileId,
      activeLibraryName,
      activeLibraryCanDelete,
      librarySummaryRows,
      librarySummaryTotals,
      librarySummaryCount,
      librarySummaryStatusLabel,
      librarySummaryTone,
      librarySummaryStripItem,
      librarySummaryDesignationLabel,
      librarySummaryStatusSymbol,
      renderLibrarySummaryInspect,
      formatLibrarySummaryTimestamp,
      setLibrarySummaryWarning,
      updateLibrarySummarySelection,
      renderLibrarySummary,
      requestLibrarySummaryScan,
      renderActiveLibraryCommandState,
      renderProfileCards,
    };
  }

  window.__settingsLibrariesSummaryModule = { createSettingsLibrariesSummaryModule };
})();
