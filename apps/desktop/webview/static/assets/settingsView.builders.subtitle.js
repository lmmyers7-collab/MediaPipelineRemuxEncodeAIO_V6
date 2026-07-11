(function () {
  function createSubtitleSettingsBuilder(deps) {
    const {
      byId,
      formatSettingsListValue,
      getLastSettings,
      parseSettingsListText,
      readSettingsBuilderNumber,
      renderSettingsActiveMediaPolicyHandoff,
      renderSettingsMediaPolicyCrossCheck,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      subtitleSettingsBuilderFields,
      subtitleSettingsBuilderState,
      writeSettingsPatchJson,
    } = deps;

    const subtitleLanguageFields = [
      { id: "settings-subtitle-languages", key: "SubKeepLanguages", fallback: ["eng", "und"] },
      { id: "settings-subtitle-tx3g-languages", key: "Tx3gExtractLanguages", fallback: ["eng", "und"] },
      { id: "settings-subtitle-bdpgs-languages", key: "BdpgsExtractLanguages", fallback: ["eng", "und"] },
      { id: "settings-subtitle-vobsub-languages", key: "VobSubExtractLanguages", fallback: ["eng", "en", "und"] },
    ];

    const subtitleFieldFallbacks = {
      SubKeepLanguages: ["eng", "und"],
      Tx3gExtractLanguages: ["eng", "und"],
      BdpgsExtractLanguages: ["eng", "und"],
      VobSubExtractLanguages: ["eng", "en", "und"],
      MergeThresholdMs: 150,
      SubtitleExtractTimeoutSeconds: 180,
      SubtitleProbeTimeoutSeconds: 30,
      BdpgsOcrTimeoutSeconds: 1800,
      VobSubOcrTimeoutSeconds: 1800,
      BdpgsOcrToolPath: "tools\\PgsToSrt\\PgsToSrt.exe",
      BdpgsOcrTessdataPath: "tools\\PgsToSrt\\tessdata",
      VobSubOcrToolPath: "tools\\SubtitleEditLegacy\\SubtitleEdit.exe",
      SubSDHTitleKeywords: ["sdh", "hearing impaired", "hearing-impaired", "cc", "closed caption", "closedcaption", "captions", "subs for deaf", "deaf", "hoh", "hi", "descriptive"],
      SubSupplementalKeywords: ["sign", "signs", "song", "songs", "karaoke", "chapter", "opening", "ending", "op", "ed", "credits", "lyrics"],
      ExcludeSubtitleStyles: [],
      IncludeSubtitleStyles: [],
      ConvertTx3gToSrt: true,
      DropTx3gAfterConversion: false,
      CreateExternalTx3gSrtSidecars: false,
      Tx3gPreserveExistingSrt: true,
      Tx3gTreatForcedAsSeparate: true,
      TreatTx3gSignsSongsAsForced: false,
      ConvertBdpgsToSrt: true,
      DropBdpgsAfterConversion: false,
      TreatBdpgsSignsSongsAsForced: false,
      ConvertVobSubToSrt: false,
      DropVobSubAfterConversion: false,
      TreatVobSubSignsSongsAsForced: false,
      DropAssAfterConversion: false,
      RemoveKaraoke: true,
      StripFormatting: true,
      MergeAdjacent: true,
      KeepSignsAndSongs: true,
      TreatAssSignsSongsAsForced: false,
    };

    const subtitlePolicyGroups = [
      {
        selector: '[data-subtitle-policy-row="tx3g"]',
        keys: ["ConvertTx3gToSrt", "CreateExternalTx3gSrtSidecars", "Tx3gPreserveExistingSrt", "Tx3gTreatForcedAsSeparate", "TreatTx3gSignsSongsAsForced"],
      },
      {
        selector: '[data-subtitle-policy-row="bdpgs"]',
        keys: ["ConvertBdpgsToSrt", "TreatBdpgsSignsSongsAsForced"],
      },
      {
        selector: '[data-subtitle-policy-row="vobsub"]',
        keys: ["ConvertVobSubToSrt", "TreatVobSubSignsSongsAsForced"],
      },
      {
        selector: '[data-subtitle-policy-row="ass"]',
        keys: ["RemoveKaraoke", "StripFormatting", "MergeAdjacent", "KeepSignsAndSongs", "TreatAssSignsSongsAsForced"],
      },
      {
        selector: ".subtitle-cleanup-disclosure",
        keys: ["DropTx3gAfterConversion", "DropBdpgsAfterConversion", "DropVobSubAfterConversion", "DropAssAfterConversion"],
      },
      {
        selector: ".subtitle-advanced-disclosure",
        keys: ["MergeThresholdMs", "SubtitleExtractTimeoutSeconds", "SubtitleProbeTimeoutSeconds", "BdpgsOcrTimeoutSeconds", "VobSubOcrTimeoutSeconds", "BdpgsOcrToolPath", "BdpgsOcrTessdataPath", "VobSubOcrToolPath", "SubSDHTitleKeywords", "SubSupplementalKeywords", "ExcludeSubtitleStyles", "IncludeSubtitleStyles"],
      },
    ];

    function setSubtitleBuilderStatus(text, state) {
      setText("settings-subtitle-builder-status", text);
      const statusNode = byId("settings-subtitle-builder-status");
      if (statusNode) statusNode.dataset.state = state || "unknown";
    }

    function subtitleFallback(key) {
      return Object.prototype.hasOwnProperty.call(subtitleFieldFallbacks, key) ? subtitleFieldFallbacks[key] : undefined;
    }

    function subtitleFieldEntry(key) {
      return subtitleSettingsBuilderFields.find(([fieldKey]) => fieldKey === key) || null;
    }

    function normalizedListFromValue(value) {
      return parseSettingsListText(formatSettingsListValue(value)).map((item) => String(item || "").trim().toLowerCase()).filter(Boolean);
    }

    function subtitleCurrentValue(key, id, kind) {
      const element = byId(id);
      if (!element) return undefined;
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(element.value).map((item) => String(item || "").trim().toLowerCase()).filter(Boolean);
      if (kind === "text") return String(element.value || "").trim();
      const numberValue = Number(element.value);
      return Number.isFinite(numberValue) ? numberValue : element.value;
    }

    function subtitleSavedValue(key, kind) {
      const saved = settingsBuilderConfigValue(key, subtitleFallback(key));
      if (kind === "bool") return saved === true || String(saved).toLowerCase() === "true";
      if (kind === "list") return normalizedListFromValue(saved);
      if (kind === "text") return String(saved ?? "").trim();
      const numberValue = Number(saved);
      return Number.isFinite(numberValue) ? numberValue : saved;
    }

    function subtitleValuesEqual(current, saved, kind) {
      if (kind === "list") {
        if (!Array.isArray(current) || !Array.isArray(saved) || current.length !== saved.length) return false;
        return current.every((value, index) => value === saved[index]);
      }
      return current === saved;
    }

    function subtitleKeyChanged(key) {
      const entry = subtitleFieldEntry(key);
      if (!entry) return false;
      const [, id, kind] = entry;
      return !subtitleValuesEqual(subtitleCurrentValue(key, id, kind), subtitleSavedValue(key, kind), kind);
    }

    function subtitleDocumentNode() {
      return byId("settings-subtitle-builder-status")?.ownerDocument || (typeof document !== "undefined" ? document : null);
    }

    function renderSubtitleLanguagePreviews() {
      subtitleLanguageFields.forEach(({ id, key }) => {
        const input = byId(id);
        const field = input?.closest?.("[data-subtitle-language-field]");
        const warning = field?.querySelector?.("[data-subtitle-language-warning]");
        const tokens = parseSettingsListText(input?.value || "");
        const unusual = tokens.filter((token) => !/^[a-z]{2,3}$/i.test(String(token || "").trim()));
        if (field) field.dataset.state = subtitleKeyChanged(key || "") ? "changed" : "current";
        if (warning) {
          warning.textContent = !tokens.length
            ? "Advisory: empty language lists can make subtitle routing unpredictable."
            : unusual.length
              ? `Advisory: unusual language token(s): ${unusual.join(", ")}. Backend Save remains authoritative.`
              : "Preview only; backend Save validates the final settings.";
          warning.dataset.state = !tokens.length || unusual.length ? "warning" : "current";
        }
      });
    }

    function renderSubtitleGroupedStates() {
      const doc = subtitleDocumentNode();
      subtitlePolicyGroups.forEach((group) => {
        const node = doc?.querySelector?.(group.selector);
        if (!node) return;
        const changed = group.keys.some((key) => subtitleKeyChanged(key));
        node.dataset.state = changed ? "changed" : "current";
        const indicator = node.querySelector?.("[data-subtitle-change-indicator]");
        if (indicator) indicator.textContent = changed ? "Changed" : "Current";
      });
      const cleanup = doc?.querySelector?.(".subtitle-cleanup-disclosure");
      const dropEnabled = ["settings-subtitle-drop-tx3g", "settings-subtitle-drop-bdpgs", "settings-subtitle-drop-vobsub", "settings-subtitle-drop-ass"]
        .some((id) => byId(id)?.checked === true);
      if (cleanup) {
        cleanup.dataset.cleanup = dropEnabled ? "enabled" : "preserved";
        if (dropEnabled) cleanup.open = true;
      }
    }

    function renderSubtitlePolicyEditorState() {
      renderSubtitleLanguagePreviews();
      renderSubtitleGroupedStates();
    }

    function setSubtitleBuilderControl(id, key, kind, fallback) {
      const element = byId(id);
      if (!element) return;
      const value = settingsBuilderConfigValue(key, fallback);
      if (kind === "bool") {
        element.checked = value === true || String(value).toLowerCase() === "true";
        return;
      }
      if (kind === "list") {
        element.value = formatSettingsListValue(value);
        return;
      }
      element.value = String(value ?? "");
    }

    function syncSubtitleSettingsBuilderFromConfig() {
      setSubtitleBuilderControl("settings-subtitle-languages", "SubKeepLanguages", "list", ["eng", "und"]);
      setSubtitleBuilderControl("settings-subtitle-tx3g-languages", "Tx3gExtractLanguages", "list", ["eng", "und"]);
      setSubtitleBuilderControl("settings-subtitle-bdpgs-languages", "BdpgsExtractLanguages", "list", ["eng", "und"]);
      setSubtitleBuilderControl("settings-subtitle-vobsub-languages", "VobSubExtractLanguages", "list", ["eng", "en", "und"]);
      setSubtitleBuilderControl("settings-subtitle-merge-threshold", "MergeThresholdMs", "number", 150);
      setSubtitleBuilderControl("settings-subtitle-extract-timeout", "SubtitleExtractTimeoutSeconds", "number", 180);
      setSubtitleBuilderControl("settings-subtitle-probe-timeout", "SubtitleProbeTimeoutSeconds", "number", 30);
      setSubtitleBuilderControl("settings-subtitle-bdpgs-timeout", "BdpgsOcrTimeoutSeconds", "number", 1800);
      setSubtitleBuilderControl("settings-subtitle-vobsub-timeout", "VobSubOcrTimeoutSeconds", "number", 1800);
      setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tool-path", "BdpgsOcrToolPath", "text", "tools\\PgsToSrt\\PgsToSrt.exe");
      setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tessdata-path", "BdpgsOcrTessdataPath", "text", "tools\\PgsToSrt\\tessdata");
      setSubtitleBuilderControl("settings-subtitle-vobsub-ocr-tool-path", "VobSubOcrToolPath", "text", "tools\\SubtitleEditLegacy\\SubtitleEdit.exe");
      setSubtitleBuilderControl("settings-subtitle-sdh-keywords", "SubSDHTitleKeywords", "list", ["sdh", "hearing impaired", "hearing-impaired", "cc", "closed caption", "closedcaption", "captions", "subs for deaf", "deaf", "hoh", "hi", "descriptive"]);
      setSubtitleBuilderControl("settings-subtitle-supplemental-keywords", "SubSupplementalKeywords", "list", ["sign", "signs", "song", "songs", "karaoke", "chapter", "opening", "ending", "op", "ed", "credits", "lyrics"]);
      setSubtitleBuilderControl("settings-subtitle-exclude-styles", "ExcludeSubtitleStyles", "list", []);
      setSubtitleBuilderControl("settings-subtitle-include-styles", "IncludeSubtitleStyles", "list", []);
      setSubtitleBuilderControl("settings-subtitle-convert-tx3g", "ConvertTx3gToSrt", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-drop-tx3g", "DropTx3gAfterConversion", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-sidecar-tx3g", "CreateExternalTx3gSrtSidecars", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-preserve-tx3g-srt", "Tx3gPreserveExistingSrt", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-forced-tx3g", "Tx3gTreatForcedAsSeparate", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-tx3g-signs-forced", "TreatTx3gSignsSongsAsForced", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-convert-bdpgs", "ConvertBdpgsToSrt", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-drop-bdpgs", "DropBdpgsAfterConversion", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-bdpgs-signs-forced", "TreatBdpgsSignsSongsAsForced", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-convert-vobsub", "ConvertVobSubToSrt", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-drop-vobsub", "DropVobSubAfterConversion", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-vobsub-signs-forced", "TreatVobSubSignsSongsAsForced", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-drop-ass", "DropAssAfterConversion", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-remove-karaoke", "RemoveKaraoke", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-strip-formatting", "StripFormatting", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-merge-adjacent", "MergeAdjacent", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-keep-signs", "KeepSignsAndSongs", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-ass-signs-forced", "TreatAssSignsSongsAsForced", "bool", false);
      subtitleSettingsBuilderState.initialized = true;
      subtitleSettingsBuilderState.dirty = false;
      setSubtitleBuilderStatus("Loaded current values", "loaded");
      renderSubtitleSettingsBuilderGuidance();
      renderSubtitlePolicyEditorState();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markSubtitleSettingsBuilderDirty() {
      subtitleSettingsBuilderState.initialized = true;
      subtitleSettingsBuilderState.dirty = true;
      setSubtitleBuilderStatus("Editing subtitle values", "editing");
      renderSubtitleSettingsBuilderGuidance();
      renderSubtitlePolicyEditorState();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function readSubtitleBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : kind === "list" ? [] : kind === "text" ? "" : 0;
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(element.value);
      if (kind === "text") return String(element.value || "").trim();
      return readSettingsBuilderNumber(id, label);
    }

    function collectSubtitleSettingsBuilderPatch() {
      const patch = {};
      subtitleSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readSubtitleBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applySubtitleSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectSubtitleSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setSubtitleBuilderStatus("Invalid subtitle value", "invalid");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return false;
      }
      writeSettingsPatchJson(patch, "Subtitle builder prepared subtitle policy keys for Save Settings. Backend Save still validates before writing.");
      subtitleSettingsBuilderState.initialized = true;
      subtitleSettingsBuilderState.dirty = true;
      setSubtitleBuilderStatus(`${Object.keys(patch).length} subtitle change keys ready`, "ready");
      renderSubtitleSettingsBuilderGuidance();
      renderSubtitlePolicyEditorState();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
      return true;
    }

    function settingsBdpgsOcrPathEvidence(settings = getLastSettings()) {
      const evidence = settings?.tool_path_evidence?.bdpgs_ocr;
      return evidence && typeof evidence === "object" ? evidence : {};
    }

    function settingsBdpgsOcrPathEvidenceStatus(evidence = settingsBdpgsOcrPathEvidence()) {
      const status = String(evidence?.operator_status || "").trim();
      return status || "Not loaded";
    }

    function settingsBdpgsOcrPathEvidenceLines(evidence = settingsBdpgsOcrPathEvidence()) {
      if (!evidence || !Object.keys(evidence).length) {
        return [
          "No BDPGS OCR path evidence loaded.",
          "Backend settings workspace has not returned saved-config OCR path status yet.",
          "Mutation guardrail: WebView does not resolve arbitrary paths or run OCR.",
        ];
      }
      const lines = Array.isArray(evidence.summary_lines) ? evidence.summary_lines.slice() : [];
      const rows = Array.isArray(evidence.rows) ? evidence.rows : [];
      rows.forEach((row) => {
        lines.push("");
        lines.push(`${row.label || row.key || "Path"}: ${row.status || "unknown"}`);
        lines.push(`Configured: ${row.configured || "(not set)"}`);
        lines.push(`Resolved: ${row.resolved || "(not resolved)"}`);
        lines.push(`Type: ${row.path_type || "unknown"}; exists=${row.exists ? "yes" : "no"}; expected=${row.required_kind || "unknown"}`);
        if (row.message) lines.push(`Message: ${row.message}`);
      });
      lines.push("");
      lines.push("Operator rule: fix missing OCR tool/tessdata paths in backend settings before trusting BDPGS-to-SRT runs.");
      lines.push("Mutation guardrail: saved path evidence is read-only; path edits are staged by the Subtitle builder or backend-owned picker and still go through backend Save.");
      lines.push("WebView does not browse arbitrary paths, resolve paths, or run OCR.");
      return lines;
    }

    function renderSettingsBdpgsOcrPathEvidence(settings = getLastSettings()) {
      const evidence = settingsBdpgsOcrPathEvidence(settings);
      const status = settingsBdpgsOcrPathEvidenceStatus(evidence);
      setText("settings-subtitle-bdpgs-path-status", status);
      const statusNode = byId("settings-subtitle-bdpgs-path-status");
      if (statusNode) {
        const normalized = status.toLowerCase();
        statusNode.dataset.state = normalized.includes("blocked") ? "blocked" : normalized.includes("review") ? "warning" : normalized.includes("ready") ? "ready" : "unknown";
      }
      setText("settings-subtitle-bdpgs-path-evidence", settingsBdpgsOcrPathEvidenceLines(evidence).join("\n"));
    }

    function settingsVobSubOcrPathEvidence(settings = getLastSettings()) {
      const evidence = settings?.tool_path_evidence?.vobsub_ocr;
      return evidence && typeof evidence === "object" ? evidence : {};
    }

    function settingsVobSubOcrPathEvidenceStatus(evidence = settingsVobSubOcrPathEvidence()) {
      const status = String(evidence?.operator_status || "").trim();
      return status || "Not loaded";
    }

    function settingsVobSubOcrPathEvidenceLines(evidence = settingsVobSubOcrPathEvidence()) {
      if (!evidence || !Object.keys(evidence).length) {
        return [
          "No VobSub OCR path evidence loaded.",
          "Backend settings workspace has not returned saved-config OCR path status yet.",
          "Mutation guardrail: WebView does not resolve arbitrary paths or run OCR.",
        ];
      }
      const lines = Array.isArray(evidence.summary_lines) ? evidence.summary_lines.slice() : [];
      const rows = Array.isArray(evidence.rows) ? evidence.rows : [];
      rows.forEach((row) => {
        lines.push("");
        lines.push(`${row.label || row.key || "Path"}: ${row.status || "unknown"}`);
        lines.push(`Configured: ${row.configured || "(not set)"}`);
        lines.push(`Resolved: ${row.resolved || "(not resolved)"}`);
        lines.push(`Type: ${row.path_type || "unknown"}; exists=${row.exists ? "yes" : "no"}; expected=${row.required_kind || "unknown"}`);
        if (row.message) lines.push(`Message: ${row.message}`);
      });
      lines.push("");
      lines.push("Operator rule: configure Subtitle Edit 4.x SubtitleEdit.exe and Tesseract before trusting VobSub-to-SRT runs.");
      lines.push("Mutation guardrail: saved path evidence is read-only; path edits are staged by the Subtitle builder or raw JSON and still go through backend Save.");
      return lines;
    }

    function renderSettingsVobSubOcrPathEvidence(settings = getLastSettings()) {
      const evidence = settingsVobSubOcrPathEvidence(settings);
      const status = settingsVobSubOcrPathEvidenceStatus(evidence);
      setText("settings-subtitle-vobsub-path-status", status);
      const statusNode = byId("settings-subtitle-vobsub-path-status");
      if (statusNode) {
        const normalized = status.toLowerCase();
        statusNode.dataset.state = normalized.includes("blocked") ? "blocked" : normalized.includes("review") ? "warning" : normalized.includes("ready") ? "ready" : "unknown";
      }
      setText("settings-subtitle-vobsub-path-evidence", settingsVobSubOcrPathEvidenceLines(evidence).join("\n"));
    }

    function renderSubtitleSettingsBuilderGuidance() {
      const keepLanguages = parseSettingsListText(byId("settings-subtitle-languages")?.value || "");
      const convertTx3g = byId("settings-subtitle-convert-tx3g")?.checked === true;
      const dropTx3g = byId("settings-subtitle-drop-tx3g")?.checked === true;
      const convertBdpgs = byId("settings-subtitle-convert-bdpgs")?.checked === true;
      const dropBdpgs = byId("settings-subtitle-drop-bdpgs")?.checked === true;
      const convertVobSub = byId("settings-subtitle-convert-vobsub")?.checked === true;
      const dropVobSub = byId("settings-subtitle-drop-vobsub")?.checked === true;
      const dropAss = byId("settings-subtitle-drop-ass")?.checked === true;
      const bdpgsPathEvidence = settingsBdpgsOcrPathEvidence();
      const vobSubPathEvidence = settingsVobSubOcrPathEvidence();
      const lines = [
        "Guardrail: subtitle settings only stage config keys; extraction, OCR, muxing, and drop behavior remain backend-owned.",
        "Default policy: original subtitle tracks are preserved unless a matching Drop*AfterConversion toggle is enabled.",
        "Preferred language controls which subtitle tracks are considered for SRT generation.",
        `Subtitle routing summary: keep languages=${keepLanguages.join(", ") || "(empty)"}; TX3G SRT=${convertTx3g ? "on" : "off"}; BDPGS OCR=${convertBdpgs ? "on" : "off"}; VobSub OCR=${convertVobSub ? "on" : "off"}; drop originals=${[dropTx3g ? "TX3G" : "", dropBdpgs ? "BDPGS" : "", dropVobSub ? "VobSub" : "", dropAss ? "ASS" : ""].filter(Boolean).join(", ") || "none"}.`,
        `Saved BDPGS OCR path evidence: ${settingsBdpgsOcrPathEvidenceStatus(bdpgsPathEvidence)}.`,
        `Saved VobSub OCR path evidence: ${settingsVobSubOcrPathEvidenceStatus(vobSubPathEvidence)}.`,
      ];
      subtitleSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        let valueText = "";
        if (kind === "bool") {
          valueText = byId(id)?.checked ? "enabled" : "disabled";
        } else if (kind === "list") {
          valueText = parseSettingsListText(byId(id)?.value || "").join(", ") || "(empty)";
        } else {
          valueText = settingsBuilderInputValue(id) || "(not set)";
        }
        lines.push(`${label}: ${valueText}`);
        if (field?.help) lines.push(`  ${field.help}`);
        const hint = settingsSpecificImpactHints[key];
        if (hint) lines.push(`  ${hint}`);
        if (key === "SubKeepLanguages" && !parseSettingsListText(byId(id)?.value || "").length) {
          lines.push("  Warning: empty keep languages can make preferred-language subtitle routing unpredictable.");
        }
        if (key === "DropTx3gAfterConversion" && byId(id)?.checked) {
          lines.push("  Warning: TX3G originals will be removed after successful conversion; keep disabled to preserve source subtitles.");
        }
        if (key === "DropBdpgsAfterConversion" && byId(id)?.checked) {
          lines.push("  Warning: BDPGS originals will be removed after OCR; keep disabled when preserving Blu-ray image subtitles matters.");
        }
        if (key === "DropVobSubAfterConversion" && byId(id)?.checked) {
          lines.push("  Warning: embedded VobSub originals will be removed after OCR; external .idx/.sub sidecars are never deleted.");
        }
        if (key === "DropAssAfterConversion" && byId(id)?.checked) {
          lines.push("  Warning: ASS/SSA originals will be removed after conversion; keep disabled to preserve styling.");
        }
        if (key === "ConvertBdpgsToSrt" && !byId(id)?.checked) {
          lines.push("  Review: preferred-language PGS subtitles will not generate SRT without OCR enabled.");
        }
        if (key === "ConvertVobSubToSrt" && !byId(id)?.checked) {
          lines.push("  Review: preferred-language VobSub subtitles will not generate SRT without OCR enabled.");
        }
        if (key === "BdpgsOcrToolPath" && convertBdpgs && !settingsBuilderInputValue(id)) {
          lines.push("  Warning: BDPGS OCR is enabled but the OCR tool path is blank. Backend validation and path evidence must be reviewed before real runs.");
        }
        if (key === "BdpgsOcrToolPath") {
          lines.push("  Boundary: this field stages a config value only; the WebView does not browse arbitrary paths, resolve paths, or run OCR.");
        }
        if (key === "VobSubOcrToolPath" && convertVobSub && !settingsBuilderInputValue(id)) {
          lines.push("  Warning: VobSub OCR is enabled but the OCR tool path is blank. Backend validation and path evidence must be reviewed before real runs.");
        }
        if (key === "VobSubOcrToolPath") {
          lines.push("  Boundary: this field stages a config value only; the WebView does not browse arbitrary paths, resolve paths, or run OCR.");
        }
        if (key === "BdpgsOcrTessdataPath") {
          lines.push("  Boundary: tessdata path evidence is backend-authored after Save and reload.");
        }
        if (key === "SubSDHTitleKeywords") {
          lines.push("  Boundary: keyword edits only stage backend SDH classification inputs; the WebView does not classify subtitle tracks.");
        }
        if (key === "SubSupplementalKeywords") {
          lines.push("  Boundary: keyword edits only stage backend supplemental-subtitle classification inputs; the WebView does not classify subtitle tracks.");
        }
        if (key === "ConvertTx3gToSrt" && !byId(id)?.checked) {
          lines.push("  Review: preferred-language TX3G/mov_text subtitles will not generate SRT without conversion enabled.");
        }
      });
      if (dropTx3g && !convertTx3g) lines.push("", "Conflict: Drop TX3G is enabled while Convert TX3G to SRT is disabled.");
      if (dropBdpgs && !convertBdpgs) lines.push("", "Conflict: Drop BDPGS is enabled while OCR BDPGS to SRT is disabled.");
      if (dropVobSub && !convertVobSub) lines.push("", "Conflict: Drop VobSub is enabled while OCR VobSub to SRT is disabled.");
      setText("settings-subtitle-guidance", lines.join("\n") || "No subtitle guidance loaded.");
      renderSubtitlePolicyEditorState();
    }

    return {
      syncSubtitleSettingsBuilderFromConfig,
      markSubtitleSettingsBuilderDirty,
      collectSubtitleSettingsBuilderPatch,
      applySubtitleSettingsBuilderToPatch,
      settingsBdpgsOcrPathEvidence,
      settingsBdpgsOcrPathEvidenceStatus,
      settingsBdpgsOcrPathEvidenceLines,
      renderSettingsBdpgsOcrPathEvidence,
      settingsVobSubOcrPathEvidence,
      settingsVobSubOcrPathEvidenceStatus,
      settingsVobSubOcrPathEvidenceLines,
      renderSettingsVobSubOcrPathEvidence,
      renderSubtitleSettingsBuilderGuidance,
    };
  }

  window.__settingsViewSubtitleBuilderModule = {
    createSubtitleSettingsBuilder,
  };
})();
