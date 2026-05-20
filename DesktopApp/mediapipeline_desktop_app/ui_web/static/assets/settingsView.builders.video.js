(function () {
  function createVideoDetailSettingsBuilder(deps) {
    const {
      byId,
      formatSettingsChoiceLabel,
      formatSettingsListValue,
      parseSettingsListText,
      readSettingsBuilderNumber,
      refreshSettingsSelectChoices,
      renderSettingsActiveMediaPolicyHandoff,
      setSettingsBuilderControl,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      videoDetailSettingsBuilderFields,
      videoDetailSettingsBuilderState,
      writeSettingsPatchJson,
    } = deps;

    function setVideoDetailBuilderControl(id, key, kind, fallback) {
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
      setSettingsBuilderControl(id, value);
    }

    function syncVideoDetailSettingsBuilderFromConfig() {
      refreshSettingsSelectChoices(videoDetailSettingsBuilderFields);
      setVideoDetailBuilderControl("settings-video-preset", "VideoPreset", "select", "p5");
      setVideoDetailBuilderControl("settings-video-quality", "VideoQuality", "number_select", 22);
      setVideoDetailBuilderControl("settings-video-h264-remux", "AllowH264RemuxIfPlexCompatible", "bool", true);
      setVideoDetailBuilderControl("settings-video-h264-max-bitrate", "H264RemuxMaxBitrateMbps", "number_positive", 35);
      setVideoDetailBuilderControl("settings-video-h264-max-height", "H264RemuxMaxHeight", "number_select", 1080);
      setVideoDetailBuilderControl("settings-video-remux-safe-codecs", "RemuxSafeVideoCodecs", "list", ["hevc", "h265", "h264", "avc"]);
      setVideoDetailBuilderControl("settings-video-cpu-quality", "FallbackCpuQuality", "cpu_quality", 20);
      setVideoDetailBuilderControl("settings-video-cpu-preset", "CpuEncodePreset", "select", "medium");
      setVideoDetailBuilderControl("settings-video-cpu-priority", "CpuEncodeProcessPriority", "select", "belownormal");
      setVideoDetailBuilderControl("settings-video-cpu-threads", "CpuEncodeMaxThreads", "number", 0);
      setVideoDetailBuilderControl("settings-video-extra-flags", "ExtraVideoFlags", "list", []);
      videoDetailSettingsBuilderState.initialized = true;
      videoDetailSettingsBuilderState.dirty = false;
      setText("settings-video-builder-status", "Loaded current values");
      renderVideoDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markVideoDetailSettingsBuilderDirty() {
      videoDetailSettingsBuilderState.initialized = true;
      videoDetailSettingsBuilderState.dirty = true;
      setText("settings-video-builder-status", "Editing video detail values");
      renderVideoDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function readVideoDetailBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : kind === "list" ? [] : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(element.value);
      if (kind === "number" || kind === "number_select") return readSettingsBuilderNumber(id, label);
      if (kind === "number_positive") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 1) throw new Error(`${label} must be one or higher.`);
        return value;
      }
      if (kind === "cpu_quality") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 14 || value > 28) throw new Error(`${label} must be between 14 and 28.`);
        return value;
      }
      return settingsBuilderInputValue(id);
    }

    function collectVideoDetailSettingsBuilderPatch() {
      const patch = {};
      videoDetailSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readVideoDetailBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyVideoDetailSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectVideoDetailSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-video-builder-status", "Invalid video detail value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return;
      }
      writeSettingsPatchJson(patch, "Video detail builder merged remux, H.264 copy, CPU fallback, and legacy flag keys into Changes JSON. Preview or Save still uses backend validation.");
      videoDetailSettingsBuilderState.initialized = true;
      videoDetailSettingsBuilderState.dirty = true;
      setText("settings-video-builder-status", `${Object.keys(patch).length} video detail patch keys ready`);
      renderVideoDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function renderVideoDetailSettingsBuilderGuidance() {
      const lines = [
        "Guardrail: these values influence remux-vs-encode precision and fallback behavior; they do not change any files until backend save and a later backend-owned run.",
      ];
      videoDetailSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        let valueText = "";
        if (kind === "bool") {
          valueText = byId(id)?.checked ? "enabled" : "disabled";
        } else if (kind === "list") {
          valueText = parseSettingsListText(byId(id)?.value || "").join(", ") || "(empty)";
        } else {
          valueText = formatSettingsChoiceLabel(settingsBuilderInputValue(id) || "");
        }
        lines.push(`${label}: ${valueText || "(not set)"}`);
        const choiceHelp = field?.choice_help && settingsBuilderInputValue(id) ? field.choice_help[settingsBuilderInputValue(id)] : "";
        if (choiceHelp) {
          lines.push(`  ${choiceHelp}`);
        } else if (field?.help) {
          lines.push(`  ${field.help}`);
        }
        const hint = settingsSpecificImpactHints[key];
        if (hint) lines.push(`  ${hint}`);
        if (key === "AllowH264RemuxIfPlexCompatible" && !byId(id)?.checked) {
          lines.push("  Warning: compatible H.264 sources may encode instead of copying video.");
        }
        if (key === "FallbackCpuQuality" && Number(settingsBuilderInputValue(id)) < 18) {
          lines.push("  Warning: low CPU CRF values can grow outputs and extend fallback runs substantially.");
        }
        if (key === "ExtraVideoFlags" && parseSettingsListText(byId(id)?.value || "").length) {
          lines.push("  Warning: legacy raw FFmpeg flags should normally stay empty unless EncodeTuningPreset is custom_legacy_flags.");
        }
      });
      setText("settings-video-guidance", lines.join("\n") || "No video detail guidance loaded.");
    }

    return {
      syncVideoDetailSettingsBuilderFromConfig,
      markVideoDetailSettingsBuilderDirty,
      collectVideoDetailSettingsBuilderPatch,
      applyVideoDetailSettingsBuilderToPatch,
      renderVideoDetailSettingsBuilderGuidance,
    };
  }

  window.__settingsViewVideoBuilderModule = {
    createVideoDetailSettingsBuilder,
  };
})();
