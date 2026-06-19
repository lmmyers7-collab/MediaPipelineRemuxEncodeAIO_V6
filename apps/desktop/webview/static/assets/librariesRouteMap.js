(function () {
  const state = {
    routeMap: null,
    trace: null,
    compare: null,
    validation: null,
    evidenceRows: [],
    activeProfileId: "",
    initialized: false,
    traceRequestId: 0,
    compareRequestId: 0,
    validationRequestId: 0,
    editorState: {
      activeProfileId: "",
      dirty: false,
      patchState: "none",
      patchCurrent: false,
    },
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

  function setStateText(id, value, stateValue = "") {
    const node = byId(id);
    if (!node) return;
    node.textContent = text(value);
    if (stateValue) node.dataset.state = stateValue;
    else delete node.dataset.state;
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

  function stateTone(value) {
    const stateValue = statusText(value).toLowerCase();
    if (["current", "ok", "ready", "saved", "valid", "complete", "completed"].includes(stateValue)) return "ready";
    if (["blocked", "failed", "error", "invalid"].includes(stateValue)) return "blocked";
    if (["review", "warning", "missing", "stale", "unknown"].includes(stateValue)) return "warning";
    if (["changed", "active", "pending", "loading"].includes(stateValue)) return stateValue;
    return "unknown";
  }

  function errorMessage(error) {
    if (error instanceof Error) return error.message;
    return text(error) || "Unknown error";
  }

  function compareValueStateTone(value) {
    const stateValue = statusText(value).toLowerCase();
    if (["explicit", "override", "custom", "library_override"].includes(stateValue)) return "explicit";
    if (["inherited", "default", "defaulted", "synthesized_builtin_default", "builtin_default"].includes(stateValue)) return "inherited";
    if (["missing", "not_configured", "not reported", "unknown"].includes(stateValue)) return "missing";
    if (["conflict", "warning", "stale"].includes(stateValue)) return "conflict";
    if (["invalid", "invalid_unresolved", "blocked", "failed", "error"].includes(stateValue)) return "invalid";
    if (["current", "ok", "ready", "saved", "valid", "complete", "completed"].includes(stateValue)) return "valid";
    if (["changed", "different"].includes(stateValue)) return "changed";
    if (["same", "unchanged", "matched"].includes(stateValue)) return "same";
    return "unknown";
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
    if (selected) state.activeProfileId = selected;

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

  function warningLinesForPayload(label, payload) {
    const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
    return warnings.map((line) => `${label}: ${text(line)}`).filter((line) => line.trim() !== `${label}:`);
  }

  function renderRouteContext(profile) {
    const profileName = profileLabel(profile);
    const routeStatus = statusText(profile?.profile_status);
    const profileCount = routeProfiles().length;
    const editorProfile = text(state.editorState.activeProfileId);
    const editorMatchesRoute = !editorProfile || editorProfile === text(profile?.library_id);
    const contextLines = [];
    if (state.routeMap?.schema_version) {
      contextLines.push(`Active route-map profile: ${profileName} (${routeStatus}).`);
      contextLines.push(`Evidence authority: ${text(state.routeMap.evidence_authority) || "backend"} saved config and Library Profile state.`);
      contextLines.push(state.routeMap.guardrail || "Evidence only; no settings save, launch, queue, or filesystem mutation is performed.");
    } else {
      contextLines.push("Saved backend route-map evidence has not loaded.");
    }
    if (state.editorState.dirty) {
      const scope = editorMatchesRoute ? "this selected library" : "another selected editor library";
      const patchLabel = state.editorState.patchCurrent
        ? "a LibraryProfiles patch is staged"
        : state.editorState.patchState === "stale"
          ? "the existing LibraryProfiles patch is stale"
          : "no current LibraryProfiles patch is staged";
      contextLines.push(`Editor scope: ${scope} has unsaved editor state; ${patchLabel}. Route-map rows still show saved backend evidence until backend Save/refresh.`);
    } else if (state.editorState.patchState === "staged") {
      contextLines.push("Editor scope: LibraryProfiles is staged in Changes JSON but not saved. Route-map rows still show saved backend evidence.");
    }
    setStateText(
      "library-route-map-status",
      state.routeMap?.schema_version ? `${profileCount} profile(s) · ${profileName}` : "Not loaded",
      state.routeMap?.schema_version ? stateTone(routeStatus) : "unknown"
    );
    setText("library-route-map-context", contextLines.join(" "));
    const warnings = [
      ...(Array.isArray(state.routeMap?.warnings) ? state.routeMap.warnings.map((line) => `Route map: ${text(line)}`) : []),
      ...warningLinesForPayload("Trace", state.trace),
      ...warningLinesForPayload("Compare", state.compare),
      ...warningLinesForPayload("Validation", state.validation),
    ];
    if (state.editorState.dirty) {
      warnings.unshift("Editor: staged or dirty profile edits are not reflected in saved backend route-map evidence yet.");
    }
    const warningNode = byId("library-route-map-warning-summary");
    if (warningNode) {
      warningNode.textContent = warnings.filter(Boolean).join("\n");
      warningNode.hidden = !warnings.length;
    }
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
    const decisionRows = Array.isArray(profile?.decision_matrix) ? profile.decision_matrix : [];
    container.innerHTML = `
      <div class="settings-library-route-map-node" data-state="${decisionRows.length ? "current" : "review"}">
        <span>evidence</span>
        <strong>Decision matrix</strong>
        <em>${decisionRows.length} row${decisionRows.length === 1 ? "" : "s"}</em>
      </div>
    ` + nodes.map((node, index) => `
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
    body.innerHTML = rows.map((row) => {
      const leftState = statusText(row.left?.state || row.left?.status);
      const rightState = statusText(row.right?.state || row.right?.status);
      const rowState = statusText(row.status || (row.changed ? "changed" : "same"));
      return `
        <tr class="${row.changed ? "is-selected" : ""}">
          <td>${escapeHtml(row.label || row.field)}</td>
          <td data-state="${escapeHtml(compareValueStateTone(leftState))}">${escapeHtml(valueText(row.left?.effective_value))} <span class="muted">${escapeHtml(leftState)}</span></td>
          <td data-state="${escapeHtml(compareValueStateTone(rightState))}">${escapeHtml(valueText(row.right?.effective_value))} <span class="muted">${escapeHtml(rightState)}</span></td>
          <td data-state="${escapeHtml(compareValueStateTone(rowState))}">${escapeHtml(rowState)}</td>
        </tr>
      `;
    }).join("");
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
    const sectionRows = sections.map((section) => `
      <tr>
        <td>${escapeHtml(section.label || section.proof_type)}</td>
        <td data-state="${escapeHtml(statusText(section.status))}">${escapeHtml(statusText(section.status))}</td>
        <td>${escapeHtml(section.row_count ?? 0)}</td>
        <td>${escapeHtml([section.source_schema, ...(section.source_warnings || [])].filter(Boolean).join("; ") || "not reported")}</td>
      </tr>
    `);
    const proofRows = (Array.isArray(validation?.proof_rows) ? validation.proof_rows : []).slice(0, 8).map((row) => {
      const rowLabel = text(row.record_id || row.row_key || row.command || row.recorded_at || row.sample_category || row.route || "proof row");
      const context = [
        row.source_path ? `source: ${row.source_path}` : "",
        row.output_path ? `output: ${row.output_path}` : "",
        row.message ? `message: ${row.message}` : "",
        row.ready_to_drain === true ? "ready to drain" : "",
      ].filter(Boolean).join("; ");
      return `
        <tr class="settings-library-route-proof-row">
          <td>${escapeHtml(row.proof_type || "proof row")}</td>
          <td data-state="${escapeHtml(statusText(row.status))}">${escapeHtml(statusText(row.status))}</td>
          <td>${escapeHtml(rowLabel)}</td>
          <td>${escapeHtml(context || "not reported")}</td>
        </tr>
      `;
    });
    body.innerHTML = [...sectionRows, ...proofRows].join("");
  }

  function renderAll() {
    const profile = activeProfile();
    renderProfileSelectors();
    renderTraceSelector();
    renderRouteGraph(profile);
    renderDecisionMatrix(profile);
    renderNodeEvidence(profile);
    renderTraceRows(state.trace);
    renderCompareRows(state.compare);
    renderNavigationRows(profile);
    renderValidationRows(state.validation);
    renderRouteContext(profile);
  }

  async function refreshTrace() {
    const query = selectedTraceQuery();
    const path = `/api/libraries/route-map/trace${query ? `?${query}` : ""}`;
    const requestId = ++state.traceRequestId;
    emptyRows("library-route-trace-rows", "Loading selected-file trace...", 4);
    try {
      const trace = await apiGetLocal(path);
      if (requestId !== state.traceRequestId) return;
      state.trace = trace;
      renderTraceRows(state.trace);
    } catch (error) {
      if (requestId !== state.traceRequestId) return;
      const message = errorMessage(error);
      state.trace = {
        warnings: [`Trace request failed: ${message}`],
        trace_steps: [{
          step: "request",
          status: "error",
          summary: `Trace request failed: ${message}`,
          gaps: [],
        }],
      };
      renderTraceRows(state.trace);
    } finally {
      if (requestId === state.traceRequestId) renderRouteContext(activeProfile());
    }
  }

  async function refreshCompare() {
    const left = byId("library-route-compare-left")?.value || "";
    const right = byId("library-route-compare-right")?.value || "";
    const params = new URLSearchParams();
    if (left) params.set("left_id", left);
    if (right) params.set("right_id", right);
    const requestId = ++state.compareRequestId;
    emptyRows("library-route-compare-rows", "Loading profile comparison...", 4);
    try {
      const compare = await apiGetLocal(`/api/libraries/route-map/compare?${params.toString()}`);
      if (requestId !== state.compareRequestId) return;
      state.compare = compare;
      renderCompareRows(state.compare);
    } catch (error) {
      if (requestId !== state.compareRequestId) return;
      const message = errorMessage(error);
      state.compare = {
        warnings: [`Compare request failed: ${message}`],
        rows: [{
          label: "Profile compare request",
          left: { effective_value: "compare endpoint", state: "error" },
          right: { effective_value: message, state: "error" },
          status: "error",
          changed: true,
        }],
      };
      renderCompareRows(state.compare);
    } finally {
      if (requestId === state.compareRequestId) renderRouteContext(activeProfile());
    }
  }

  async function refreshValidation() {
    const requestId = ++state.validationRequestId;
    emptyRows("library-route-validation-rows", "Loading validation handoff...", 4);
    try {
      const validation = await apiGetLocal("/api/libraries/route-map/validation?limit=20");
      if (requestId !== state.validationRequestId) return;
      state.validation = validation;
      renderValidationRows(state.validation);
    } catch (error) {
      if (requestId !== state.validationRequestId) return;
      const message = errorMessage(error);
      state.validation = {
        warnings: [`Validation request failed: ${message}`],
        proof_sections: [{
          label: "Validation request",
          proof_type: "request",
          status: "error",
          row_count: 0,
          source_warnings: [message],
        }],
        proof_rows: [],
      };
      renderValidationRows(state.validation);
    } finally {
      if (requestId === state.validationRequestId) renderRouteContext(activeProfile());
    }
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

  function selectProfile(libraryId, options = {}) {
    const nextId = text(libraryId);
    if (!nextId) return;
    state.activeProfileId = nextId;
    renderAll();
    if (options.source !== "library-editor") {
      window.mediaPipelineSettingsLibraries?.activateLibraryProfile?.(nextId, { source: "route-map" });
    }
  }

  function setEditorState(editorState = {}) {
    state.editorState = {
      ...state.editorState,
      ...editorState,
      activeProfileId: text(editorState.activeProfileId || state.editorState.activeProfileId),
      patchState: text(editorState.patchState || state.editorState.patchState || "none"),
      dirty: editorState.dirty === true,
      patchCurrent: editorState.patchCurrent === true,
    };
    if (state.editorState.activeProfileId) state.activeProfileId = state.editorState.activeProfileId;
    renderAll();
  }

  function focusLibraryControl(libraryId, selector) {
    selectProfile(libraryId, { source: "navigation" });
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
      selectProfile(event.target?.value || "", { source: "route-map" });
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
    selectProfile,
    setEditorState,
  };
})();
