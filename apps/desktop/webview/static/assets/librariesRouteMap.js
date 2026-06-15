(function () {
  const state = {
    routeMap: null,
    trace: null,
    compare: null,
    validation: null,
    evidenceRows: [],
    activeProfileId: "",
    initialized: false,
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function text(value) {
    return value === null || value === undefined ? "" : String(value).trim();
  }

  function escapeHtml(value) {
    return text(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = text(value);
  }

  function apiGetLocal(path) {
    const get = typeof apiGet === "function" ? apiGet : window.apiGet;
    if (typeof get !== "function") return Promise.resolve({});
    return get(path);
  }

  function routeProfiles() {
    return Array.isArray(state.routeMap?.profiles) ? state.routeMap.profiles : [];
  }

  function activeProfile() {
    const profiles = routeProfiles();
    return profiles.find((profile) => text(profile.library_id) === state.activeProfileId) || profiles[0] || null;
  }

  function profileLabel(profile) {
    return text(profile?.library_name) || text(profile?.library_id) || "Library";
  }

  function statusText(value) {
    return text(value) || "unknown";
  }

  function valueText(value) {
    if (value === null || value === undefined || value === "") return "not reported";
    if (Array.isArray(value)) return value.length ? value.map(text).join(", ") : "none";
    if (typeof value === "object") return JSON.stringify(value);
    return text(value);
  }

  function renderOptions(select, rows, currentValue, labelFn, emptyLabel = "No options loaded") {
    if (!select) return "";
    if (!rows.length) {
      select.disabled = true;
      select.setAttribute("aria-disabled", "true");
      select.innerHTML = `<option value="" disabled selected>${escapeHtml(emptyLabel)}</option>`;
      return "";
    }
    select.disabled = false;
    select.removeAttribute("aria-disabled");
    const selected = rows.some((row) => text(row.value) === currentValue) ? currentValue : text(rows[0]?.value);
    select.innerHTML = rows.map((row) => {
      const value = text(row.value);
      return `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(labelFn(row))}</option>`;
    }).join("");
    return selected;
  }

  function renderProfileSelectors() {
    const profiles = routeProfiles();
    const options = profiles.map((profile) => ({
      value: text(profile.library_id),
      profile,
    }));
    const selected = renderOptions(
      byId("library-route-map-profile-select"),
      options,
      state.activeProfileId,
      (row) => `${profileLabel(row.profile)} (${statusText(row.profile?.profile_status)})`,
      "No library profiles loaded"
    );
    state.activeProfileId = selected;

    const left = byId("library-route-compare-left");
    const right = byId("library-route-compare-right");
    const leftValue = renderOptions(left, options, left?.value || state.activeProfileId, (row) => profileLabel(row.profile), "No comparable profiles loaded");
    const fallbackRight = options.find((row) => row.value !== leftValue)?.value || leftValue;
    renderOptions(right, options, right?.value || fallbackRight, (row) => profileLabel(row.profile), "No comparable profiles loaded");
  }

  function rowKey(row, sourceName, index) {
    return [
      sourceName,
      text(row.row_key || row.record_id || row.id || index),
      text(row.source_path || row.source),
      text(row.output_path),
    ].join("\u001f");
  }

  function collectEvidenceRows(context = {}) {
    const sources = [
      ["queue", context.queue?.rows],
      ["completed", context.completed?.rows],
      ["sample_validation", context.sampleValidation?.records],
    ];
    return sources.flatMap(([sourceName, rows]) => {
      if (!Array.isArray(rows)) return [];
      return rows.slice(0, 50).filter((row) => row && typeof row === "object").map((row, index) => ({
        sourceName,
        row,
        key: rowKey(row, sourceName, index),
      }));
    });
  }

  function renderTraceSelector() {
    const select = byId("library-route-trace-selector");
    if (!select) return;
    const options = state.evidenceRows.map((item) => ({
      value: item.key,
      item,
    }));
    if (!options.length) {
      select.disabled = true;
      select.setAttribute("aria-disabled", "true");
      select.innerHTML = '<option value="" disabled selected>No loaded rows to trace</option>';
      return;
    }
    select.disabled = false;
    select.removeAttribute("aria-disabled");
    renderOptions(select, options, select.value, (row) => {
      const item = row.item;
      const source = item.sourceName.replace("_", " ");
      const label = text(item.row.display_name || item.row.lookup_title || item.row.source_path || item.row.output_path || item.row.record_id);
      return `${source}: ${label || "row"}`;
    });
  }

  function selectedTraceQuery() {
    const value = byId("library-route-trace-selector")?.value || "";
    const item = state.evidenceRows.find((candidate) => candidate.key === value);
    if (!item) return "";
    const row = item.row;
    const params = new URLSearchParams();
    if (row.row_key || row.record_id || row.id) params.set("row_key", text(row.row_key || row.record_id || row.id));
    if (row.source_path || row.source) params.set("source_path", text(row.source_path || row.source));
    if (row.output_path) params.set("output_path", text(row.output_path));
    return params.toString();
  }

  function renderRouteGraph(profile) {
    const container = byId("library-route-map-graph");
    if (!container) return;
    const nodes = Array.isArray(profile?.nodes) ? profile.nodes : [];
    if (!nodes.length) {
      container.innerHTML = '<p class="empty-state">No route nodes are available.</p>';
      return;
    }
    container.innerHTML = nodes.map((node, index) => `
      <div class="settings-library-route-map-node" data-state="${escapeHtml(statusText(node.status))}">
        <span>${escapeHtml(node.type || `node ${index + 1}`)}</span>
        <strong>${escapeHtml(node.label)}</strong>
        <em>${escapeHtml(statusText(node.status))}</em>
      </div>
    `).join("");
  }

  function emptyRows(id, message, colspan) {
    const body = byId(id);
    if (body) body.innerHTML = `<tr><td colspan="${colspan}" class="muted">${escapeHtml(message)}</td></tr>`;
  }

  function renderDecisionMatrix(profile) {
    const body = byId("library-route-decision-rows");
    if (!body) return;
    const rows = Array.isArray(profile?.decision_matrix) ? profile.decision_matrix : [];
    if (!rows.length) return emptyRows("library-route-decision-rows", "No decision-matrix rows.", 5);
    body.innerHTML = rows.map((row) => `
      <tr>
        <td>${escapeHtml(row.label || row.bucket)}</td>
        <td>${escapeHtml(row.height_rule)}</td>
        <td>${escapeHtml(Object.entries(row.target_values || {}).map(([key, value]) => `${key}: ${valueText(value)}`).join("; "))}</td>
        <td>${escapeHtml(row.direct_copy_bitrate_mbps ? `${row.direct_copy_bitrate_mbps} Mbps` : "not applicable")}</td>
        <td data-state="${escapeHtml(statusText(row.status))}">${escapeHtml(statusText(row.status))}</td>
      </tr>
    `).join("");
  }

  function navigationLink(action, label = "Focus control") {
    if (!action || typeof action !== "object") return "";
    return `<a href="#settings-library-profile-list" data-library-route-navigate data-library-id="${escapeHtml(action.library_id)}" data-library-route-selector="${escapeHtml(action.selector)}">${escapeHtml(label)}</a>`;
  }

  function renderNodeEvidence(profile) {
    const body = byId("library-route-node-rows");
    if (!body) return;
    const rows = Array.isArray(profile?.nodes) ? profile.nodes : [];
    if (!rows.length) return emptyRows("library-route-node-rows", "No node evidence.", 4);
    body.innerHTML = rows.map((node) => `
      <tr>
        <td>${escapeHtml(node.label || node.type)}</td>
        <td data-state="${escapeHtml(statusText(node.status))}">${escapeHtml(statusText(node.status))}</td>
        <td>${escapeHtml(valueText(node.evidence))}</td>
        <td>${navigationLink(node.navigation)}</td>
      </tr>
    `).join("");
  }

  function renderTraceRows(trace) {
    const body = byId("library-route-trace-rows");
    if (!body) return;
    const rows = Array.isArray(trace?.trace_steps) ? trace.trace_steps : [];
    if (!rows.length) return emptyRows("library-route-trace-rows", "No trace row selected.", 4);
    body.innerHTML = rows.map((row) => `
      <tr>
        <td>${escapeHtml(row.step)}</td>
        <td data-state="${escapeHtml(statusText(row.status))}">${escapeHtml(statusText(row.status))}</td>
        <td>${escapeHtml(row.summary)}</td>
        <td>${escapeHtml(valueText(row.gaps || row.candidates || ""))}</td>
      </tr>
    `).join("");
  }

  function renderCompareRows(compare) {
    const body = byId("library-route-compare-rows");
    if (!body) return;
    const rows = Array.isArray(compare?.rows) ? compare.rows.slice(0, 120) : [];
    if (!rows.length) return emptyRows("library-route-compare-rows", "No profile comparison loaded.", 4);
    body.innerHTML = rows.map((row) => `
      <tr class="${row.changed ? "is-selected" : ""}">
        <td>${escapeHtml(row.label || row.field)}</td>
        <td>${escapeHtml(valueText(row.left?.effective_value))} <span class="muted">${escapeHtml(statusText(row.left?.state || row.left?.status))}</span></td>
        <td>${escapeHtml(valueText(row.right?.effective_value))} <span class="muted">${escapeHtml(statusText(row.right?.state || row.right?.status))}</span></td>
        <td>${escapeHtml(row.changed ? "changed" : "same")}</td>
      </tr>
    `).join("");
  }

  function renderNavigationRows(profile) {
    const body = byId("library-route-navigation-rows");
    if (!body) return;
    const rows = Array.isArray(profile?.navigation_actions) ? profile.navigation_actions : [];
    if (!rows.length) return emptyRows("library-route-navigation-rows", "No navigation targets.", 4);
    body.innerHTML = rows.slice(0, 80).map((row) => `
      <tr>
        <td>${escapeHtml(profileLabel(profile))}</td>
        <td>${escapeHtml(row.label || row.key || row.path_field)}</td>
        <td>${escapeHtml(row.group || row.path_field || "profile")}</td>
        <td>${navigationLink(row, row.handoff || "Focus existing control")}</td>
      </tr>
    `).join("");
  }

  function renderValidationRows(validation) {
    const body = byId("library-route-validation-rows");
    if (!body) return;
    const sections = Array.isArray(validation?.proof_sections) ? validation.proof_sections : [];
    if (!sections.length) return emptyRows("library-route-validation-rows", "No validation handoff loaded.", 4);
    body.innerHTML = sections.map((section) => `
      <tr>
        <td>${escapeHtml(section.label || section.proof_type)}</td>
        <td data-state="${escapeHtml(statusText(section.status))}">${escapeHtml(statusText(section.status))}</td>
        <td>${escapeHtml(section.row_count ?? 0)}</td>
        <td>${escapeHtml([section.source_schema, ...(section.source_warnings || [])].filter(Boolean).join("; ") || "not reported")}</td>
      </tr>
    `).join("");
  }

  function renderAll() {
    const profile = activeProfile();
    setText("library-route-map-status", state.routeMap?.schema_version ? `${routeProfiles().length} profile(s)` : "Not loaded");
    renderProfileSelectors();
    renderTraceSelector();
    renderRouteGraph(profile);
    renderDecisionMatrix(profile);
    renderNodeEvidence(profile);
    renderTraceRows(state.trace);
    renderCompareRows(state.compare);
    renderNavigationRows(profile);
    renderValidationRows(state.validation);
  }

  async function refreshTrace() {
    const query = selectedTraceQuery();
    const path = `/api/libraries/route-map/trace${query ? `?${query}` : ""}`;
    state.trace = await apiGetLocal(path);
    renderTraceRows(state.trace);
  }

  async function refreshCompare() {
    const left = byId("library-route-compare-left")?.value || "";
    const right = byId("library-route-compare-right")?.value || "";
    const params = new URLSearchParams();
    if (left) params.set("left_id", left);
    if (right) params.set("right_id", right);
    state.compare = await apiGetLocal(`/api/libraries/route-map/compare?${params.toString()}`);
    renderCompareRows(state.compare);
  }

  async function refreshValidation() {
    state.validation = await apiGetLocal("/api/libraries/route-map/validation?limit=20");
    renderValidationRows(state.validation);
  }

  async function refreshReadOnlyDetails() {
    await Promise.allSettled([refreshTrace(), refreshCompare(), refreshValidation()]);
  }

  function renderRouteMap(payload, context = {}) {
    state.routeMap = payload || {};
    state.evidenceRows = collectEvidenceRows(context);
    if (!state.activeProfileId) state.activeProfileId = text(routeProfiles()[0]?.library_id);
    renderAll();
    refreshReadOnlyDetails();
  }

  async function refreshLibraryRouteMap() {
    state.routeMap = await apiGetLocal("/api/libraries/route-map");
    renderAll();
    await refreshReadOnlyDetails();
  }

  function focusLibraryControl(libraryId, selector) {
    const tab = Array.from(byId("settings-library-profile-nav")?.querySelectorAll("[data-library-profile-nav]") || [])
      .find((item) => item.getAttribute("data-library-profile-nav") === libraryId);
    tab?.click?.();
    const target = selector ? document.querySelector(selector) : null;
    const focusTarget = target?.matches?.("input, select, textarea, button, a") ? target : target?.querySelector?.("input, select, textarea, button, a");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("is-selected");
      window.setTimeout(() => target.classList.remove("is-selected"), 1600);
    }
    focusTarget?.focus?.({ preventScroll: true });
  }

  function initLibraryRouteMapEvents() {
    if (state.initialized) return;
    state.initialized = true;
    byId("library-route-map-profile-select")?.addEventListener("change", (event) => {
      state.activeProfileId = event.target?.value || "";
      renderAll();
    });
    byId("library-route-trace-selector")?.addEventListener("change", () => { refreshTrace(); });
    byId("library-route-compare-left")?.addEventListener("change", () => { refreshCompare(); });
    byId("library-route-compare-right")?.addEventListener("change", () => { refreshCompare(); });
    document.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target.closest("[data-library-route-navigate]") : null;
      if (!target) return;
      event.preventDefault();
      focusLibraryControl(target.getAttribute("data-library-id") || "", target.getAttribute("data-library-route-selector") || "");
    });
  }

  /**
   * Public namespace for the library route-map module.
   *
   * Keep this object limited to stable page integration hooks; flat window.* exports
   * remain compatibility-only.
   */
  window.mediaPipelineLibraryRouteMap = {
    renderRouteMap,
    refreshLibraryRouteMap,
    initLibraryRouteMapEvents,
  };
})();
