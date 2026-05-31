(function () {
  function createSettingsRawTriageModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const filterRows = deps.filterRows || function (rows) { return Array.isArray(rows) ? rows : []; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const makeRowSelectable = deps.makeRowSelectable || function () {};
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const formatConfigValue = deps.formatConfigValue || function (value) { return String(value ?? ""); };
    const settingsBuilderCoveredKeys = deps.settingsBuilderCoveredKeys || function () { return new Set(); };
    const settingsImpactGroupForKey = deps.settingsImpactGroupForKey || function () { return null; };
    const settingsSpecificImpactHints = deps.settingsSpecificImpactHints || {};
    const settingsFieldDefinition = deps.settingsFieldDefinition || function () { return null; };
    const settingsBdpgsOcrPathEvidenceStatus = deps.settingsBdpgsOcrPathEvidenceStatus || function () { return "Not loaded"; };
    const settingsBdpgsOcrPathEvidenceLines = deps.settingsBdpgsOcrPathEvidenceLines || function () { return []; };
    const settingsVobSubOcrPathEvidenceStatus = deps.settingsVobSubOcrPathEvidenceStatus || function () { return "Not loaded"; };
    const settingsVobSubOcrPathEvidenceLines = deps.settingsVobSubOcrPathEvidenceLines || function () { return []; };
    const getLastSettingsValues = deps.getLastSettingsValues || function () { return {}; };
    const getLastSettingsFieldDefinitions = deps.getLastSettingsFieldDefinitions || function () { return []; };

    let lastSettingsEntries = [];
    let lastSettingsEmptyMessage = "No config values loaded.";
    let selectedSettingsRawTriageKey = "";
    let selectedSettingsRawActionPlanKey = "";

  function setSettingsRows(entries, emptyMessage) {
    lastSettingsEntries = Array.isArray(entries) ? entries : [];
    lastSettingsEmptyMessage = emptyMessage || "No config values loaded.";
  }

  function renderSettingsRows() {
    const filterText = byId("settings-filter")?.value || "";
    const rows = filterRows(lastSettingsEntries, filterText, ["key", "value"]);
    setText("settings-count", `${rows.length} / ${lastSettingsEntries.length} key${lastSettingsEntries.length === 1 ? "" : "s"}`);
    const tbody = byId("settings-rows");
    if (!rows.length) {
      clearRows(tbody, 2, lastSettingsEntries.length ? "No config values match the filter." : lastSettingsEmptyMessage);
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [item.key, item.value]);
      tbody.appendChild(row);
    });
  }

  function settingsKnownFieldKeys() {
    return new Set((Array.isArray(getLastSettingsFieldDefinitions()) ? getLastSettingsFieldDefinitions() : [])
      .map((field) => String(field?.key || ""))
      .filter(Boolean));
  }

  function settingsRawKeyCoverage(key, builderKeys = settingsBuilderCoveredKeys(), knownKeys = settingsKnownFieldKeys()) {
    if (builderKeys.has(key)) return "structured builder";
    if (!knownKeys.has(key)) return "unknown raw key";
    const group = settingsImpactGroupForKey(key);
    if (group) return "advanced raw";
    return "known raw";
  }

  function settingsRawKeyImpact(key) {
    const group = settingsImpactGroupForKey(key);
    if (group) return `${group.severity || "review"} / ${group.name || "configured"}`;
    if (!settingsKnownFieldKeys().has(key)) return "unknown / schema";
    return "low / ungrouped";
  }

  function settingsRawKeyReviewNote(key, coverage) {
    if (settingsSpecificImpactHints[key]) return settingsSpecificImpactHints[key];
    const group = settingsImpactGroupForKey(key);
    if (coverage === "unknown raw key") {
      return "Not present in the backend field definitions. Use Preview Patch before saving any edits involving this key.";
    }
    if (coverage === "structured builder") {
      return `Covered by structured settings UI. ${group?.note || "Prefer builder controls over raw JSON edits."}`;
    }
    if (group?.note) return group.note;
    return "Known config key without a dedicated builder; treat raw edits as advanced and verify with backend preview.";
  }

  function settingsRawTriageRows() {
    const builderKeys = settingsBuilderCoveredKeys();
    const knownKeys = settingsKnownFieldKeys();
    return Object.keys(getLastSettingsValues() || {})
      .sort((left, right) => left.localeCompare(right))
      .map((key) => {
        const coverage = settingsRawKeyCoverage(key, builderKeys, knownKeys);
        return {
          key,
          coverage,
          impact: settingsRawKeyImpact(key),
          note: settingsRawKeyReviewNote(key, coverage),
          group: settingsImpactGroupForKey(key),
        };
      });
  }

  function settingsRawTriageStatus(rows = settingsRawTriageRows()) {
    if (!rows.length) return "No config";
    if (rows.some((row) => row.coverage === "unknown raw key")) return "Unknown keys";
    if (rows.some((row) => row.coverage === "advanced raw" && String(row.group?.severity || "").toLowerCase() === "high")) return "High-impact raw";
    if (rows.some((row) => row.coverage === "advanced raw")) return "Advanced raw";
    return "Structured";
  }

  function settingsRawTriageSummaryLines(rows = settingsRawTriageRows()) {
    const structured = rows.filter((row) => row.coverage === "structured builder");
    const advanced = rows.filter((row) => row.coverage === "advanced raw");
    const knownRaw = rows.filter((row) => row.coverage === "known raw");
    const unknown = rows.filter((row) => row.coverage === "unknown raw key");
    const highAdvanced = advanced.filter((row) => String(row.group?.severity || "").toLowerCase() === "high");
    const lines = [
      "Settings raw-key triage:",
      `Loaded config keys: ${rows.length}`,
      `Structured-builder keys: ${structured.length}`,
      `Advanced raw keys: ${advanced.length}`,
      `Known ungrouped raw keys: ${knownRaw.length}`,
      `Unknown raw keys: ${unknown.length}`,
      `High-impact raw keys: ${highAdvanced.length}`,
    ];
    const reviewRows = [...unknown, ...highAdvanced, ...advanced.filter((row) => !highAdvanced.includes(row)), ...knownRaw].slice(0, 8);
    if (reviewRows.length) {
      lines.push("", "First keys to review:");
      reviewRows.forEach((row) => lines.push(`- ${row.key}: ${row.coverage}; ${row.impact}`));
    }
    lines.push("");
    if (unknown.length) {
      lines.push("Next step: unknown raw keys should be treated as schema drift. Run Settings > Preview Patch before any save touching them.");
    } else if (highAdvanced.length) {
      lines.push("Next step: high-impact raw keys are valid but not covered by a dedicated builder; review their notes before unattended processing.");
    } else if (advanced.length || knownRaw.length) {
      lines.push("Next step: advanced raw keys are visible below; prefer structured builders for routine changes and backend preview for raw edits.");
    } else {
      lines.push("Next step: all loaded keys are covered by structured settings builders.");
    }
    lines.push("Mutation guardrail: this triage is read-only. Settings Preview/Save remains backend-owned and PSD1 serialization is unchanged.");
    return lines;
  }

  function boundedSettingsValueText(value) {
    const text = formatConfigValue(value);
    if (!text) return "(empty)";
    return text.length > 600 ? `${text.slice(0, 600)}...` : text;
  }

  function selectedSettingsRawTriageRow(rows) {
    if (!selectedSettingsRawTriageKey) return null;
    return rows.find((row) => row.key === selectedSettingsRawTriageKey) || null;
  }

  function settingsRawTriageDetailLines(row) {
    if (!row) {
      return [
        "No raw-key row selected.",
        "Select a row to inspect current value, schema section, backend field help, and recommended next step.",
        "Mutation guardrail: this detail view is read-only. Use Settings Preview/Save for backend-owned validation and persistence.",
      ];
    }
    const field = settingsFieldDefinition(row.key);
    const current = getLastSettingsValues() ? getLastSettingsValues()[row.key] : undefined;
    const lines = [
      `Key: ${row.key}`,
      `Coverage: ${row.coverage}`,
      `Impact: ${row.impact}`,
      `Current value: ${current === undefined ? "(not set)" : boundedSettingsValueText(current)}`,
    ];
    if (field) {
      lines.push(`Schema: ${field.page || "Unknown page"} / ${field.section || "Unknown section"} / ${field.kind || "unknown kind"}`);
      if (field.label) lines.push(`Label: ${field.label}`);
      if (field.help) lines.push(`Help: ${field.help}`);
    } else {
      lines.push("Schema: not found in backend field definitions.");
    }
    if (row.note) lines.push(`Review note: ${row.note}`);
    if (row.coverage === "unknown raw key") {
      lines.push("Recommended next step: treat this as schema drift. Do not save a patch touching this key until backend Preview Patch explains it.");
    } else if (row.coverage === "advanced raw") {
      lines.push("Recommended next step: valid key, but advanced. Prefer an existing builder when possible and run backend Preview Patch before Save.");
    } else if (row.coverage === "known raw") {
      lines.push("Recommended next step: known backend field without impact grouping. Raw edits are possible, but Preview Patch remains authoritative.");
    } else {
      lines.push("Recommended next step: use the structured builder for routine edits instead of raw JSON.");
    }
    lines.push("Mutation guardrail: this detail view does not stage, save, or rewrite config.");
    return lines;
  }

  function renderSettingsRawTriage() {
    const rows = settingsRawTriageRows();
    setText("settings-raw-triage-status", settingsRawTriageStatus(rows));
    setText("settings-raw-triage", settingsRawTriageSummaryLines(rows).join("\n"));
    const tbody = byId("settings-raw-triage-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No config values loaded.");
      setText("settings-raw-triage-legend", "Settings raw-key triage: no selectable rows.");
      setText("settings-raw-triage-detail", settingsRawTriageDetailLines(null).join("\n"));
      return;
    }
    const reviewRows = rows.filter((row) => row.coverage !== "structured builder");
    const visibleRows = (reviewRows.length ? reviewRows : rows).slice(0, 80);
    if (selectedSettingsRawTriageKey && !visibleRows.some((row) => row.key === selectedSettingsRawTriageKey)) {
      selectedSettingsRawTriageKey = "";
    }
    tbody.replaceChildren();
    visibleRows.forEach((item) => {
      const row = document.createElement("tr");
      if (item.coverage === "unknown raw key") row.dataset.status = "blocked";
      else if (item.coverage === "advanced raw") row.dataset.status = "warning";
      else if (item.coverage === "structured builder") row.dataset.status = "match";
      appendCells(row, [item.key, item.coverage, item.impact, item.note]);
      makeRowSelectable(row, () => {
        selectedSettingsRawTriageKey = item.key;
        renderSettingsRawTriage();
      }, {
        selected: selectedSettingsRawTriageKey === item.key,
        label: `Inspect settings key ${item.key}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("settings-raw-triage-legend", tbody, "Settings raw-key triage");
    setText("settings-raw-triage-detail", settingsRawTriageDetailLines(selectedSettingsRawTriageRow(visibleRows)).join("\n"));
  }

  function settingsRawActionPlanStatus(rows = settingsRawActionPlanRows()) {
    if (!rows.length) return "No config";
    if (rows.some((row) => String(row.posture || "").toLowerCase().includes("blocked"))) return "Blocked review";
    if (rows.some((row) => String(row.posture || "").toLowerCase().includes("high"))) return "High review";
    if (rows.some((row) => String(row.posture || "").toLowerCase().includes("review"))) return "Review";
    return "Covered";
  }

  function settingsRawActionPlanRows(rawRows = settingsRawTriageRows()) {
    const byKey = Object.fromEntries(rawRows.map((row) => [row.key, row]));
    const unknownRows = rawRows.filter((row) => row.coverage === "unknown raw key");
    const advancedRows = rawRows.filter((row) => row.coverage === "advanced raw");
    const structuredRows = rawRows.filter((row) => row.coverage === "structured builder");
    const knownRawRows = rawRows.filter((row) => row.coverage === "known raw");
    const rows = [];

    rows.push({
      key: "schema-drift",
      area: "Schema drift",
      posture: unknownRows.length ? "blocked review" : "clear",
      evidence: unknownRows.length
        ? `${unknownRows.length} unknown key(s): ${unknownRows.slice(0, 6).map((row) => row.key).join(", ")}${unknownRows.length > 6 ? `, +${unknownRows.length - 6} more` : ""}`
        : "No unknown keys were present in the redacted backend settings workspace.",
      action: unknownRows.length
        ? "Do not save patches touching unknown keys until backend Preview Patch explains them."
        : "No schema-drift action needed.",
      detail: unknownRows.length
        ? unknownRows.map((row) => `${row.key}: ${row.note}`)
        : ["Backend field definitions cover every loaded key."],
    });

    const bdpgsRows = ["BdpgsOcrToolPath", "BdpgsOcrTessdataPath"].map((key) => byKey[key]).filter(Boolean);
    const bdpgsKeys = bdpgsRows.map((row) => row.key);
    const bdpgsRawKeys = bdpgsRows.filter((row) => row.coverage !== "structured builder").map((row) => row.key);
    const bdpgsStructuredKeys = bdpgsRows.filter((row) => row.coverage === "structured builder").map((row) => row.key);
    const bdpgsStatus = settingsBdpgsOcrPathEvidenceStatus();
    rows.push({
      key: "bdpgs-ocr-paths",
      area: "BDPGS OCR path evidence",
      posture: bdpgsKeys.length ? (bdpgsStatus.toLowerCase().includes("blocked") ? "blocked review" : bdpgsStatus.toLowerCase().includes("review") ? "high review" : "evidence available") : "not configured",
      evidence: bdpgsKeys.length
        ? bdpgsRawKeys.length
          ? `${bdpgsRawKeys.join(", ")} remain raw-only path key(s); saved backend evidence reports ${bdpgsStatus}.`
          : `${bdpgsStructuredKeys.join(", ")} are covered by the Subtitle builder; saved backend evidence reports ${bdpgsStatus}.`
        : "No BDPGS OCR path keys were present in the loaded config.",
      action: bdpgsKeys.length
        ? "Use the Subtitle builder or raw JSON to stage OCR path changes, then backend Preview/Save and re-check saved path evidence; do not add a frontend-owned path picker."
        : "If BDPGS OCR is enabled later, require backend path evidence before real-media validation.",
      detail: [
        ...settingsBdpgsOcrPathEvidenceLines().slice(0, 12),
        "Path policy: WebView can stage configured path text, but backend Preview/Save and saved path evidence remain authoritative; WebView does not browse arbitrary paths or resolve paths. Any folder picker must be backend-owned and allowlisted.",
      ],
    });

    const vobSubRows = ["VobSubOcrToolPath"].map((key) => byKey[key]).filter(Boolean);
    const vobSubKeys = vobSubRows.map((row) => row.key);
    const vobSubRawKeys = vobSubRows.filter((row) => row.coverage !== "structured builder").map((row) => row.key);
    const vobSubStructuredKeys = vobSubRows.filter((row) => row.coverage === "structured builder").map((row) => row.key);
    const vobSubStatus = settingsVobSubOcrPathEvidenceStatus();
    rows.push({
      key: "vobsub-ocr-paths",
      area: "VobSub OCR path evidence",
      posture: vobSubKeys.length ? (vobSubStatus.toLowerCase().includes("blocked") ? "blocked review" : vobSubStatus.toLowerCase().includes("review") ? "high review" : "evidence available") : "not configured",
      evidence: vobSubKeys.length
        ? vobSubRawKeys.length
          ? `${vobSubRawKeys.join(", ")} remain raw-only path key(s); saved backend evidence reports ${vobSubStatus}.`
          : `${vobSubStructuredKeys.join(", ")} are covered by the Subtitle builder; saved backend evidence reports ${vobSubStatus}.`
        : "No VobSub OCR path keys were present in the loaded config.",
      action: vobSubKeys.length
        ? "Use the Subtitle builder or raw JSON to stage OCR path changes, then backend Preview/Save and re-check saved path evidence; do not add a frontend-owned path picker."
        : "If VobSub OCR is enabled later, require backend path evidence before real-media validation.",
      detail: [
        ...settingsVobSubOcrPathEvidenceLines().slice(0, 12),
        "Path policy: WebView can stage configured path text, but backend Preview/Save and saved path evidence remain authoritative; WebView does not browse arbitrary paths or resolve paths.",
      ],
    });

    const keywordRows = ["SubSDHTitleKeywords", "SubSupplementalKeywords"].map((key) => byKey[key]).filter(Boolean);
    const keywordKeys = keywordRows.map((row) => row.key);
    const keywordRawKeys = keywordRows.filter((row) => row.coverage !== "structured builder").map((row) => row.key);
    const keywordStructuredKeys = keywordRows.filter((row) => row.coverage === "structured builder").map((row) => row.key);
    rows.push({
      key: "subtitle-keywords",
      area: "Subtitle keyword lists",
      posture: keywordRawKeys.length ? "low review" : keywordStructuredKeys.length ? "structured coverage" : "not present",
      evidence: keywordKeys.length
        ? keywordRawKeys.length
          ? `${keywordRawKeys.join(", ")} remain advanced raw keyword list(s); ${keywordStructuredKeys.length} keyword key(s) are structured.`
          : `${keywordStructuredKeys.join(", ")} are covered by the Subtitle builder.`
        : "No SDH/supplemental subtitle keyword keys were present in the loaded config.",
      action: keywordKeys.length
        ? keywordRawKeys.length
          ? "Keep remaining raw keyword keys advanced unless operator demand justifies a dedicated list editor; backend preview must validate array/list shape."
          : "Use the Subtitle builder to stage keyword list changes, then backend Preview/Save; backend subtitle classification remains authoritative."
        : "No keyword-list action needed.",
      detail: keywordKeys.length
        ? [
          ...keywordRows.map((row) => `${row.key}: ${row.coverage}; ${row.note || "Subtitle keyword list."}`),
          "Mutation boundary: WebView only stages list text for backend Preview/Save; SDH and supplemental classification remain backend-authored.",
        ]
        : ["Subtitle keyword keys are absent from this redacted config snapshot."],
    });

    const secretKeys = ["CoordinatorAuthToken", "WorkerAuthToken"].filter((key) => byKey[key] || settingsFieldDefinition(key));
    rows.push({
      key: "network-secrets",
      area: "Network auth secrets",
      posture: secretKeys.length ? "intentional exclusion" : "not present",
      evidence: secretKeys.length
        ? `${secretKeys.join(", ")} are intentionally not builder-owned; backend redaction must prevent secret display.`
        : "No network auth secret field was present in this workspace payload.",
      action: secretKeys.length
        ? "Do not add WebView token editors without a separate secret-handling design. Raw preview/save must keep redacted placeholders rejected."
        : "No token action needed.",
      detail: [
        "Secrets can leak through browser memory, dev tools, logs, screenshots, and command history if exposed casually.",
        "Backend settings workspace redacts token values; Save Patch rejects '<redacted>' placeholders for sensitive keys.",
        "Network lifecycle controls remain read-only during the Tauri/WebView transition.",
      ],
    });

    const remainingAdvanced = advancedRows.filter((row) => !["BdpgsOcrToolPath", "BdpgsOcrTessdataPath", "SubSDHTitleKeywords", "SubSupplementalKeywords", "CoordinatorAuthToken", "WorkerAuthToken"].includes(row.key));
    rows.push({
      key: "remaining-advanced",
      area: "Remaining advanced raw",
      posture: remainingAdvanced.length || knownRawRows.length ? "review" : "none",
      evidence: `${remainingAdvanced.length} advanced raw key(s), ${knownRawRows.length} known ungrouped raw key(s), ${structuredRows.length} structured key(s).`,
      action: remainingAdvanced.length || knownRawRows.length
        ? "Treat these as advanced edits; prefer existing builders and backend Preview Patch before Save."
        : "All non-secret/non-path keys are structured or intentionally absent.",
      detail: remainingAdvanced.concat(knownRawRows).length
        ? remainingAdvanced.concat(knownRawRows).slice(0, 12).map((row) => `${row.key}: ${row.coverage}; ${row.impact}; ${row.note}`)
        : ["No remaining advanced raw keys need operator triage."],
    });

    rows.push({
      key: "mutation-boundary",
      area: "Mutation boundary",
      posture: "backend-owned",
      evidence: "Raw-key action plan is derived from redacted settings workspace data and local schema metadata only.",
      action: "This panel cannot stage JSON, save config, launch work, run FFmpeg/OCR, edit PATH, drain publish, rename, or touch media.",
      detail: [
        "Use structured builders for routine changes.",
        "Use Preview Patch for backend validation, redacted diff, risk summary, and PSD1 serialization proof.",
        "Use Save Patch only after preview evidence and explicit browser confirmation.",
      ],
    });

    return rows;
  }

  function settingsRawActionPlanSummaryLines(rows = settingsRawActionPlanRows()) {
    const status = settingsRawActionPlanStatus(rows);
    const blocked = rows.filter((row) => String(row.posture || "").toLowerCase().includes("blocked")).length;
    const review = rows.filter((row) => String(row.posture || "").toLowerCase().includes("review") || String(row.posture || "").toLowerCase().includes("exclusion")).length;
    const lines = [
      "Settings raw-key action plan:",
      `Status: ${status}; rows=${rows.length}; blocked=${blocked}; review/exclusion=${review}.`,
      "Purpose: separate schema drift, OCR path evidence, subtitle keyword builder coverage, intentionally excluded auth secrets, and ordinary structured-builder coverage.",
    ];
    const attentionRows = rows.filter((row) => {
      const posture = String(row.posture || "").toLowerCase();
      return posture.includes("blocked") || posture.includes("review") || posture.includes("exclusion");
    });
    if (attentionRows.length) {
      lines.push("", "Rows needing operator attention:");
      attentionRows.slice(0, 6).forEach((row) => lines.push(`- ${row.area}: ${row.posture}; ${row.action}`));
    }
    lines.push("", "Mutation guardrail: this action plan is read-only and cannot stage, save, validate, launch, publish, drain, rename, or touch files.");
    return lines;
  }

  function selectedSettingsRawActionPlanRow(rows) {
    if (!selectedSettingsRawActionPlanKey) return null;
    return rows.find((row) => row.key === selectedSettingsRawActionPlanKey) || null;
  }

  function settingsRawActionPlanDetailLines(row) {
    if (!row) {
      return [
        "No raw-key action-plan row selected.",
        "Select a row to inspect evidence, recommended operator action, and the no-mutation boundary.",
        "Mutation guardrail: this detail view cannot stage, save, validate, launch, publish, drain, rename, or touch media.",
      ];
    }
    return [
      `Area: ${row.area || "Raw-key action"}`,
      `Posture: ${row.posture || "unknown"}`,
      `Evidence: ${row.evidence || "No evidence text available."}`,
      `Recommended action: ${row.action || "Review with backend Preview Patch before save."}`,
      "",
      "Detail:",
      ...(Array.isArray(row.detail) && row.detail.length ? row.detail : ["No additional detail available."]),
      "",
      "Mutation guardrail: this row is read-only and does not stage JSON, save settings, run OCR/FFmpeg, publish, rename, or touch files.",
    ];
  }

  function renderSettingsRawActionPlan() {
    const rows = settingsRawActionPlanRows();
    setText("settings-raw-action-plan-status", settingsRawActionPlanStatus(rows));
    setText("settings-raw-action-plan-summary", settingsRawActionPlanSummaryLines(rows).join("\n"));
    const tbody = byId("settings-raw-action-plan-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No raw-key action plan loaded.");
      setText("settings-raw-action-plan-legend", "Settings raw-key action plan: no selectable rows.");
      setText("settings-raw-action-plan-detail", settingsRawActionPlanDetailLines(null).join("\n"));
      return;
    }
    if (selectedSettingsRawActionPlanKey && !rows.some((row) => row.key === selectedSettingsRawActionPlanKey)) {
      selectedSettingsRawActionPlanKey = "";
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const posture = String(item.posture || "").toLowerCase();
      const row = document.createElement("tr");
      row.dataset.status = posture.includes("blocked")
        ? "blocked"
        : posture.includes("review") || posture.includes("exclusion")
          ? "warning"
          : "match";
      appendCells(row, [item.area, item.posture, item.evidence, item.action]);
      makeRowSelectable(row, () => {
        selectedSettingsRawActionPlanKey = item.key;
        renderSettingsRawActionPlan();
      }, {
        selected: selectedSettingsRawActionPlanKey === item.key,
        label: `Inspect raw-key action plan row ${item.area}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("settings-raw-action-plan-legend", tbody, "Settings raw-key action plan");
    setText("settings-raw-action-plan-detail", settingsRawActionPlanDetailLines(selectedSettingsRawActionPlanRow(rows)).join("\n"));
  }


    return {
      setSettingsRows,
      renderSettingsRows,
      settingsKnownFieldKeys,
      settingsRawKeyCoverage,
      settingsRawKeyImpact,
      settingsRawKeyReviewNote,
      settingsRawTriageRows,
      settingsRawTriageStatus,
      settingsRawTriageSummaryLines,
      boundedSettingsValueText,
      selectedSettingsRawTriageRow,
      settingsRawTriageDetailLines,
      renderSettingsRawTriage,
      settingsRawActionPlanStatus,
      settingsRawActionPlanRows,
      settingsRawActionPlanSummaryLines,
      selectedSettingsRawActionPlanRow,
      settingsRawActionPlanDetailLines,
      renderSettingsRawActionPlan,
    };
  }

  window.__settingsRawTriageModule = {
    createSettingsRawTriageModule,
  };
})();
