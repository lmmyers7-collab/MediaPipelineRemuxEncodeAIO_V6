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
      setSubtitleBuilderControl("settings-subtitle-merge-threshold", "MergeThresholdMs", "number", 150);
      setSubtitleBuilderControl("settings-subtitle-extract-timeout", "SubtitleExtractTimeoutSeconds", "number", 180);
      setSubtitleBuilderControl("settings-subtitle-probe-timeout", "SubtitleProbeTimeoutSeconds", "number", 30);
      setSubtitleBuilderControl("settings-subtitle-bdpgs-timeout", "BdpgsOcrTimeoutSeconds", "number", 1800);
      setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tool-path", "BdpgsOcrToolPath", "text", "Tools\\PgsToSrt\\PgsToSrt.exe");
      setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tessdata-path", "BdpgsOcrTessdataPath", "text", "Tools\\PgsToSrt\\tessdata");
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
      setSubtitleBuilderControl("settings-subtitle-drop-ass", "DropAssAfterConversion", "bool", false);
      setSubtitleBuilderControl("settings-subtitle-remove-karaoke", "RemoveKaraoke", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-strip-formatting", "StripFormatting", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-merge-adjacent", "MergeAdjacent", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-keep-signs", "KeepSignsAndSongs", "bool", true);
      setSubtitleBuilderControl("settings-subtitle-ass-signs-forced", "TreatAssSignsSongsAsForced", "bool", false);
      subtitleSettingsBuilderState.initialized = true;
      subtitleSettingsBuilderState.dirty = false;
      setText("settings-subtitle-builder-status", "Loaded current values");
      renderSubtitleSettingsBuilderGuidance();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markSubtitleSettingsBuilderDirty() {
      subtitleSettingsBuilderState.initialized = true;
      subtitleSettingsBuilderState.dirty = true;
      setText("settings-subtitle-builder-status", "Editing subtitle values");
      renderSubtitleSettingsBuilderGuidance();
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
        setText("settings-subtitle-builder-status", "Invalid subtitle value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return;
      }
      writeSettingsPatchJson(patch, "Subtitle builder merged subtitle policy keys into Changes JSON. Preview or Save still uses backend validation.");
      subtitleSettingsBuilderState.initialized = true;
      subtitleSettingsBuilderState.dirty = true;
      setText("settings-subtitle-builder-status", `${Object.keys(patch).length} subtitle patch keys ready`);
      renderSubtitleSettingsBuilderGuidance();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
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
      lines.push("Mutation guardrail: saved path evidence is read-only; path edits are staged by the Subtitle builder or raw JSON and still go through backend Preview/Save.");
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

    function renderSubtitleSettingsBuilderGuidance() {
      const keepLanguages = parseSettingsListText(byId("settings-subtitle-languages")?.value || "");
      const convertTx3g = byId("settings-subtitle-convert-tx3g")?.checked === true;
      const dropTx3g = byId("settings-subtitle-drop-tx3g")?.checked === true;
      const convertBdpgs = byId("settings-subtitle-convert-bdpgs")?.checked === true;
      const dropBdpgs = byId("settings-subtitle-drop-bdpgs")?.checked === true;
      const dropAss = byId("settings-subtitle-drop-ass")?.checked === true;
      const bdpgsPathEvidence = settingsBdpgsOcrPathEvidence();
      const lines = [
        "Guardrail: subtitle settings only stage config keys; extraction, OCR, muxing, and drop behavior remain backend-owned.",
        "Default policy: original subtitle tracks are preserved unless a matching Drop*AfterConversion toggle is enabled.",
        "Preferred language controls which subtitle tracks are considered for SRT generation.",
        `Subtitle routing summary: keep languages=${keepLanguages.join(", ") || "(empty)"}; TX3G SRT=${convertTx3g ? "on" : "off"}; BDPGS OCR=${convertBdpgs ? "on" : "off"}; drop originals=${[dropTx3g ? "TX3G" : "", dropBdpgs ? "BDPGS" : "", dropAss ? "ASS" : ""].filter(Boolean).join(", ") || "none"}.`,
        `Saved BDPGS OCR path evidence: ${settingsBdpgsOcrPathEvidenceStatus(bdpgsPathEvidence)}.`,
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
        if (key === "DropAssAfterConversion" && byId(id)?.checked) {
          lines.push("  Warning: ASS/SSA originals will be removed after conversion; keep disabled to preserve styling.");
        }
        if (key === "ConvertBdpgsToSrt" && !byId(id)?.checked) {
          lines.push("  Review: preferred-language PGS subtitles will not generate SRT without OCR enabled.");
        }
        if (key === "BdpgsOcrToolPath" && convertBdpgs && !settingsBuilderInputValue(id)) {
          lines.push("  Warning: BDPGS OCR is enabled but the OCR tool path is blank. Backend validation and path evidence must be reviewed before real runs.");
        }
        if (key === "BdpgsOcrToolPath") {
          lines.push("  Boundary: this field stages a config value only; the WebView does not browse arbitrary paths, resolve paths, or run OCR.");
        }
        if (key === "BdpgsOcrTessdataPath") {
          lines.push("  Boundary: tessdata path evidence is backend-authored after Preview/Save and reload.");
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
      setText("settings-subtitle-guidance", lines.join("\n") || "No subtitle guidance loaded.");
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
      renderSubtitleSettingsBuilderGuidance,
    };
  }

  window.__settingsViewSubtitleBuilderModule = {
    createSubtitleSettingsBuilder,
  };
})();
