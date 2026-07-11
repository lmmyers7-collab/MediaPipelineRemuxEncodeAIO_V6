(function () {
  /**
   * Builds and projects Settings Wizard library rows without owning settings commands.
   * The facade supplies all DOM and draft-state dependencies explicitly.
   */
  function createSettingsWizardLibraryEditor(deps) {
    const byId = deps.byId;
    const textValue = deps.textValue;
    const setValue = deps.setValue;
    const markDirty = deps.markDirty;
    const profileChoices = deps.profileChoices;
    const designations = deps.designations;
    const defaultSourceRoles = deps.defaultSourceRoles;

    function optionNode(value, label, selected) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      option.selected = Boolean(selected);
      return option;
    }

    function safeJson(value) {
      try { return JSON.stringify(value || {}); } catch (_error) { return "{}"; }
    }

    function readRowJson(row, key, fallback) {
      try {
        const value = JSON.parse(row.dataset[key] || "");
        return value && typeof value === "object" ? value : fallback;
      } catch (_error) {
        return fallback;
      }
    }

    function renderToolCandidates(candidates) {
      const firstExisting = (rows) => (Array.isArray(rows) ? rows.find((row) => row.exists)?.path || "" : "");
      if (!textValue("wizard-ffmpeg-path")) setValue("wizard-ffmpeg-path", firstExisting(candidates.ffmpeg));
      if (!textValue("wizard-ffprobe-path")) setValue("wizard-ffprobe-path", firstExisting(candidates.ffprobe));
    }

    function libraryPathField(label, field, targetKey) {
      return `
        <label data-path-picker-scope="true">
          <span class="path-picker-label-row">
            <span class="path-picker-label-text">${label}</span>
            <button type="button" class="path-picker-badge" data-path-picker-target="${targetKey}" data-path-picker-input='[data-library-field="${field}"]' data-path-picker-mode="folder" data-path-picker-status="settings-wizard-status-detail" title="Open a backend-owned Windows folder picker for ${label.toLowerCase()}.">Browse</button>
          </span>
          <input type="text" data-library-field="${field}" autocomplete="off">
        </label>`;
    }

    function createLibraryRow(library, index) {
      const section = document.createElement("section");
      section.className = "settings-wizard-library-row";
      section.dataset.libraryIndex = String(index);
      section.dataset.libraryId = library.id || library.library_id || "";
      section.dataset.defaultTracking = safeJson(library.default_tracking);
      section.dataset.overrides = safeJson(library.overrides);
      const protectedDefault = ["movies", "tv"].includes(String(section.dataset.libraryId || "").toLowerCase());
      section.innerHTML = `
      <div class="settings-wizard-library-title">
        <label><input type="checkbox" data-library-field="enabled" ${protectedDefault ? "disabled" : ""}> Enabled</label>
        <button type="button" class="secondary-button" data-library-remove ${protectedDefault ? "disabled" : ""}>Remove</button>
      </div>
      <div class="form-grid form-grid-dense">
        <label>Friendly name *<input type="text" data-library-field="name" autocomplete="off"></label>
        <label>Category<input type="text" data-library-field="category" list="wizard-library-category-list" autocomplete="off"></label>
        <label>Designation<select data-library-field="designation"></select></label>
        <label>Default root role<select data-library-field="default_source_role"></select></label>
        ${libraryPathField("Source path *", "source_path", "settings.wizard.library_source_path")}
        ${libraryPathField("Output destination", "output_path", "settings.wizard.library_output_path")}
        ${libraryPathField("Promotion destination", "promotion_destination", "settings.wizard.library_promotion_destination")}
        <label>Processing profile<select data-library-field="profile"></select></label>
      </div>
      <label class="settings-wizard-library-promotion"><input type="checkbox" data-library-field="promotion_enabled"> Enable promotion for this library</label>
    `;
      section.querySelector('[data-library-field="enabled"]').checked = library.enabled !== false;
      section.querySelector('[data-library-field="name"]').value = library.name || `Library ${index + 1}`;
      section.querySelector('[data-library-field="source_path"]').value = library.source_path || "";
      section.querySelector('[data-library-field="output_path"]').value = library.output_path || "";
      section.querySelector('[data-library-field="promotion_destination"]').value = library.promotion_destination || "";
      section.querySelector('[data-library-field="promotion_enabled"]').checked = library.promotion_enabled === true;
      section.querySelector('[data-library-field="category"]').value = library.category || "other";
      const roleSelect = section.querySelector('[data-library-field="default_source_role"]');
      defaultSourceRoles.forEach(([value, label]) => roleSelect.appendChild(optionNode(value, label, value === (library.default_source_role || "auto"))));
      const designationSelect = section.querySelector('[data-library-field="designation"]');
      designations.forEach(([value, label]) => designationSelect.appendChild(optionNode(value, label, value === (library.designation || library.media_kind || "auto"))));
      const profileSelect = section.querySelector('[data-library-field="profile"]');
      profileChoices.forEach(([value, label]) => profileSelect.appendChild(optionNode(value, label, value === (library.profile || "general_plex_direct_play"))));
      section.querySelectorAll("input, select").forEach((node) => {
        node.addEventListener("input", markDirty);
        node.addEventListener("change", markDirty);
      });
      section.querySelector("[data-library-remove]").addEventListener("click", () => {
        if (protectedDefault) return;
        section.remove();
        markDirty();
      });
      return section;
    }

    function renderLibraryRows(libraries) {
      const container = byId("settings-wizard-library-list");
      if (!container) return;
      container.textContent = "";
      const rows = libraries.length ? libraries : [
        { id: "movies", name: "Movies", designation: "movie", category: "movies", default_source_role: "source_movies", source_path: "", enabled: true, profile: "general_plex_direct_play" },
        { id: "tv", name: "TV", designation: "tv", category: "tv", default_source_role: "source_tv", source_path: "", enabled: true, profile: "general_plex_direct_play" },
      ];
      rows.forEach((library, index) => container.appendChild(createLibraryRow(library, index)));
    }

    function addLibraryRow() {
      const container = byId("settings-wizard-library-list");
      if (!container) return;
      const index = container.querySelectorAll(".settings-wizard-library-row").length;
      container.appendChild(createLibraryRow({
        name: `Library ${index + 1}`,
        media_kind: "auto",
        category: "other",
        default_source_role: "additional",
        output_path: textValue("wizard-output-root"),
        promotion_enabled: false,
        promotion_destination: "",
        enabled: true,
        profile: "general_plex_direct_play",
      }, index));
      markDirty();
    }

    function collectLibraries() {
      return Array.from(document.querySelectorAll(".settings-wizard-library-row")).map((row, index) => {
        const fallbackId = `library_${index + 1}`;
        return {
          id: String(row.dataset.libraryId || fallbackId).trim() || fallbackId,
          enabled: row.querySelector('[data-library-field="enabled"]')?.checked === true,
          name: String(row.querySelector('[data-library-field="name"]')?.value || "").trim(),
          category: String(row.querySelector('[data-library-field="category"]')?.value || "other").trim(),
          designation: String(row.querySelector('[data-library-field="designation"]')?.value || "auto").trim(),
          default_source_role: String(row.querySelector('[data-library-field="default_source_role"]')?.value || "auto").trim(),
          source_path: String(row.querySelector('[data-library-field="source_path"]')?.value || "").trim(),
          output_path: String(row.querySelector('[data-library-field="output_path"]')?.value || "").trim(),
          promotion_enabled: row.querySelector('[data-library-field="promotion_enabled"]')?.checked === true,
          promotion_destination: String(row.querySelector('[data-library-field="promotion_destination"]')?.value || "").trim(),
          profile: String(row.querySelector('[data-library-field="profile"]')?.value || "general_plex_direct_play").trim(),
          overrides: readRowJson(row, "overrides", {}),
          default_tracking: readRowJson(row, "defaultTracking", {}),
        };
      });
    }

    return { addLibraryRow, collectLibraries, renderLibraryRows, renderToolCandidates };
  }

  window.__settingsWizardLibraryEditorModule = createSettingsWizardLibraryEditor;
})();
