(function () {
  "use strict";

  let library = { records: [] };
  let initialized = false;

  function byId(id) { return document.getElementById(id); }
  function text(id, value) { const node = byId(id); if (node) node.textContent = String(value || ""); }
  function setStatus(value, state) {
    const node = byId("settings-preset-library-status");
    if (!node) return;
    node.textContent = String(value || "Not loaded");
    node.dataset.state = state || "unknown";
  }
  function safeError(error) {
    const message = error instanceof Error ? error.message : String(error || "Unknown backend error.");
    return message.replace(/(?:bearer\s+|token\s*[=:]\s*)[^\s,;]+/gi, "$1<redacted>").slice(0, 600);
  }
  function records() { return Array.isArray(library.records) ? library.records : []; }
  function selectedId() { return String(byId("settings-preset-library-select")?.value || ""); }
  function selectedRecord() { return records().find((record) => String(record?.id || "") === selectedId()) || null; }
  function isStoredRecord(record) {
    return Boolean(record?.id && records().some((item) => String(item?.id || "") === String(record.id)));
  }
  function parseEditor() {
    const raw = String(byId("settings-preset-library-json")?.value || "").trim();
    if (!raw) return null;
    const value = JSON.parse(raw);
    return value && typeof value === "object" ? value : null;
  }
  function recordFromEditor() {
    const value = parseEditor();
    if (!value) return selectedRecord();
    if (value.preset_v2) return value;
    return { id: selectedId() || "", name: value.name || "", preset_v2: value };
  }
  function renderLibrary(payload) {
    library = payload && typeof payload === "object" ? payload : { records: [] };
    const select = byId("settings-preset-library-select");
    const compare = byId("settings-preset-library-compare-select");
    const prior = selectedId();
    [select, compare].forEach((node) => {
      if (!node) return;
      node.replaceChildren();
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = records().length ? "Select a stored preset" : "No stored presets";
      node.appendChild(empty);
      records().forEach((record) => {
        const option = document.createElement("option");
        option.value = String(record.id || "");
        option.textContent = `${record.name || record.id || "Unnamed preset"}${record.source ? ` (${record.source})` : ""}`;
        node.appendChild(option);
      });
    });
    if (select && records().some((record) => String(record.id || "") === prior)) select.value = prior;
    const available = library.error ? "unavailable" : records().length ? `${records().length} preset(s)` : "empty";
    setStatus(available, library.error ? "warning" : records().length ? "ready" : "empty");
    text("settings-preset-library-detail", library.error || library.path || "Preset records are backend-owned State JSON. Loading and previewing do not change active settings.");
  }
  function renderSelected() {
    const record = selectedRecord();
    const editor = byId("settings-preset-library-json");
    if (record && editor) editor.value = JSON.stringify(record, null, 2);
    text("settings-preset-library-detail", record
      ? `${record.name || record.id} is selected. Save updates the library only; Apply changes saved settings for future launches.`
      : "Select a stored preset or paste a PresetV2 record/document to validate before saving or applying.");
  }
  function renderResult(result, fallback) {
    const detail = result?.data && typeof result.data === "object" ? result.data : {};
    text("settings-preset-library-result", JSON.stringify({
      ok: result?.ok === true,
      message: result?.message || fallback,
      warnings: result?.warnings || [],
      errors: result?.errors || [],
      data: detail,
    }, null, 2));
    setStatus(result?.message || fallback, result?.ok === false ? "warning" : "ready");
  }
  async function postResult(request, label, refreshAfter) {
    try {
      const result = await request;
      renderResult(result, label);
      if (result?.ok && refreshAfter) window.refreshAll?.({ page: "settings" });
      return result;
    } catch (error) {
      renderResult({ ok: false, message: safeError(error), errors: [safeError(error)] }, label);
      return null;
    }
  }
  async function load() {
    try {
      const result = await window.apiGet("/api/settings/preset-library");
      const payload = result?.data && typeof result.data === "object" ? result.data : result;
      renderLibrary(payload);
      return payload;
    } catch (error) {
      renderLibrary({ records: [], error: safeError(error) });
      return null;
    }
  }
  function presetPayload(record) {
    if (!record?.preset_v2 || typeof record.preset_v2 !== "object") throw new Error("Provide a PresetV2 document or a record containing preset_v2.");
    return record;
  }
  async function validate() { const record = presetPayload(recordFromEditor()); return postResult(window.apiPost("/api/settings/preset-library/validate", { preset_v2: record.preset_v2 }), "Preset validation finished."); }
  async function compare() {
    const left = presetPayload(recordFromEditor());
    const rightId = String(byId("settings-preset-library-compare-select")?.value || "");
    const payload = isStoredRecord(left) ? { left_id: left.id } : { left_preset_v2: left.preset_v2 };
    if (rightId) payload.right_id = rightId;
    else payload.right_preset_v2 = presetPayload(selectedRecord() || left).preset_v2;
    return postResult(window.apiPost("/api/settings/preset-library/compare", payload), "Preset comparison finished.");
  }
  async function importPreview() {
    const value = parseEditor();
    const candidates = Array.isArray(value) ? value : Array.isArray(value?.records) ? value.records : value ? [value] : [];
    return postResult(window.apiPost("/api/settings/preset-library/import-preview", { records: candidates }), "Import preview finished. No preset was written.");
  }
  async function save() {
    const record = presetPayload(recordFromEditor());
    return postResult(window.apiPost("/api/settings/preset-library/save", { ...record, confirm_save: true }), "Preset save finished.", true);
  }
  async function exportPreset() {
    const record = recordFromEditor();
    const payload = isStoredRecord(record) ? { id: record.id } : { preset_v2: presetPayload(record).preset_v2 };
    const result = await postResult(window.apiPost("/api/settings/preset-library/export", payload), "Preset export finished.");
    const exported = result?.data?.record;
    if (exported && byId("settings-preset-library-json")) byId("settings-preset-library-json").value = JSON.stringify(exported, null, 2);
  }
  async function applyPreview() {
    const record = recordFromEditor();
    const payload = isStoredRecord(record) ? { id: record.id } : { preset_v2: presetPayload(record).preset_v2 };
    return postResult(window.apiPost("/api/settings/preset-library/apply-preview", payload), "Apply preview finished. Active work is unaffected.");
  }
  async function apply() {
    const record = recordFromEditor();
    const payload = isStoredRecord(record) ? { id: record.id, confirm_apply: true } : { preset_v2: presetPayload(record).preset_v2, confirm_apply: true };
    return postResult(window.apiPost("/api/settings/preset-library/apply", payload), "Preset apply finished. It affects future launches only.", true);
  }
  function initPresetLibraryEvents() {
    if (initialized) return;
    initialized = true;
    byId("settings-preset-library-select")?.addEventListener("change", renderSelected);
    [["settings-preset-library-load", load], ["settings-preset-library-validate", validate], ["settings-preset-library-compare", compare], ["settings-preset-library-import-preview", importPreview], ["settings-preset-library-save", save], ["settings-preset-library-export", exportPreset], ["settings-preset-library-apply-preview", applyPreview], ["settings-preset-library-apply", apply]].forEach(([id, handler]) => byId(id)?.addEventListener("click", () => {
      void Promise.resolve(handler()).catch((error) => renderResult({ ok: false, message: safeError(error), errors: [safeError(error)] }, "Preset operation failed."));
    }));
  }
  /**
   * Public namespace for preset-library rendering; flat window.* exports are intentionally absent.
   */
  window.mediaPipelinePresetLibraryView = { renderLibrary, initPresetLibraryEvents, loadPresetLibrary: load };
}());
