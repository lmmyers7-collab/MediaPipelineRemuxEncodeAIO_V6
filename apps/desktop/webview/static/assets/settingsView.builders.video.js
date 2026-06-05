(function () {
  // eslint-disable-next-line max-lines-per-function -- video builder keeps one panel's controls and readouts together.
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
      settingsDisplayLabels,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      videoDetailSettingsBuilderFields,
      videoDetailSettingsBuilderState,
      writeSettingsPatchJson,
    } = deps;

    const videoPresetSliderDetails = {
      p1: {
        value: "1",
        label: "P1 - fastest",
        help: "Shortest encode time, weakest compression efficiency, and usually larger files for the same quality target.",
      },
      p2: {
        value: "2",
        label: "P2 - very fast",
        help: "Prioritizes speed over compression. Useful for quick turnaround when output size matters less.",
      },
      p3: {
        value: "3",
        label: "P3 - fast",
        help: "Still speed-focused, with a modest compression improvement over the fastest presets.",
      },
      p4: {
        value: "4",
        label: "P4 - standard",
        help: "Middle-ground preset for routine encodes when speed matters more than squeezing file size.",
      },
      p5: {
        value: "5",
        label: "P5 - balanced",
        help: "Balanced speed and compression for normal unattended encodes.",
      },
      p6: {
        value: "6",
        label: "P6 - quality",
        help: "Slower encodes with better compression efficiency and less wasted output size.",
      },
      p7: {
        value: "7",
        label: "P7 - slowest",
        help: "Longest encode time, best compression efficiency. Use when smaller output is worth waiting for.",
      },
    };

    const videoQualitySliderDetails = {
      18: {
        label: "18 - very high quality",
        help: "Keeps the most detail and creates the largest outputs. Reserve for priority media.",
      },
      19: {
        label: "19 - high quality",
        help: "Detail-first target with larger files than the default.",
      },
      20: {
        label: "20 - high quality",
        help: "Good for difficult grain, animation, or favorite titles when size is secondary.",
      },
      21: {
        label: "21 - detail-first",
        help: "Slightly cleaner than the default, with a moderate size increase.",
      },
      22: {
        label: "22 - balanced default",
        help: "Default library target: balanced visual quality and output size.",
      },
      23: {
        label: "23 - balanced smaller",
        help: "Saves some space while staying close to the default quality target.",
      },
      24: {
        label: "24 - smaller",
        help: "Smaller output with more visible softness on demanding material.",
      },
      25: {
        label: "25 - space saver",
        help: "Prioritizes file size. Expect more softness or artifacts on complex scenes.",
      },
      26: {
        label: "26 - strong space saver",
        help: "Use for lower-priority media where reduced size matters more than detail.",
      },
      27: {
        label: "27 - very small",
        help: "Aggressive size reduction with higher risk of visible artifacts.",
      },
      28: {
        label: "28 - smallest",
        help: "Smallest visible target in this builder. Best reserved for low-priority material.",
      },
    };

    function clampedInteger(value, fallback, min, max) {
      const parsed = Number(value);
      const next = Number.isFinite(parsed) ? Math.round(parsed) : fallback;
      return Math.min(max, Math.max(min, next));
    }

    function videoPresetKeyFromSliderValue(value) {
      return `p${clampedInteger(value, 5, 1, 7)}`;
    }

    function videoPresetSliderValue(value) {
      const text = String(value ?? "").trim().toLowerCase();
      const match = text.match(/^p?([1-7])$/);
      return match ? match[1] : videoPresetSliderDetails.p5.value;
    }

    function videoQualitySliderValue(value) {
      return String(clampedInteger(value, 22, 18, 28));
    }

    function updateVideoDetailSliderReadouts() {
      const presetKey = videoPresetKeyFromSliderValue(settingsBuilderInputValue("settings-video-preset"));
      const preset = videoPresetSliderDetails[presetKey] || videoPresetSliderDetails.p5;
      setText("settings-video-preset-value", preset.label);
      setText("settings-video-preset-help", preset.help);

      const qualityKey = videoQualitySliderValue(settingsBuilderInputValue("settings-video-quality"));
      const quality = videoQualitySliderDetails[qualityKey] || videoQualitySliderDetails[22];
      setText("settings-video-quality-value", quality.label);
      setText("settings-video-quality-help", quality.help);
    }

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
      if (kind === "preset_slider") {
        setSettingsBuilderControl(id, videoPresetSliderValue(value));
        return;
      }
      if (kind === "quality_slider") {
        setSettingsBuilderControl(id, videoQualitySliderValue(value));
        return;
      }
      setSettingsBuilderControl(id, value);
    }

    function syncVideoDetailSettingsBuilderFromConfig() {
      refreshSettingsSelectChoices(videoDetailSettingsBuilderFields);
      setVideoDetailBuilderControl("settings-builder-encode-tuning", "EncodeTuningPreset", "select", "balanced_nvenc");
      setVideoDetailBuilderControl("settings-video-preset", "VideoPreset", "preset_slider", "p5");
      setVideoDetailBuilderControl("settings-video-quality", "VideoQuality", "quality_slider", 22);
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
      updateVideoDetailSliderReadouts();
      renderVideoDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markVideoDetailSettingsBuilderDirty() {
      videoDetailSettingsBuilderState.initialized = true;
      videoDetailSettingsBuilderState.dirty = true;
      setText("settings-video-builder-status", "Editing video detail values");
      updateVideoDetailSliderReadouts();
      renderVideoDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function readVideoDetailBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : kind === "list" ? [] : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(element.value);
      if (kind === "preset_slider") return videoPresetKeyFromSliderValue(settingsBuilderInputValue(id));
      if (kind === "quality_slider") return Number(videoQualitySliderValue(settingsBuilderInputValue(id)));
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

    function formatVideoDetailBuilderValue(key, id, kind) {
      if (kind === "bool") return byId(id)?.checked ? "enabled" : "disabled";
      if (kind === "list") return parseSettingsListText(byId(id)?.value || "").join(", ") || "(empty)";
      if (kind === "preset_slider") {
        const presetKey = videoPresetKeyFromSliderValue(settingsBuilderInputValue(id));
        return videoPresetSliderDetails[presetKey]?.label || presetKey.toUpperCase();
      }
      if (kind === "quality_slider") {
        const qualityKey = videoQualitySliderValue(settingsBuilderInputValue(id));
        return videoQualitySliderDetails[qualityKey]?.label || qualityKey;
      }
      return formatSettingsChoiceLabel(settingsBuilderInputValue(id) || "");
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
      updateVideoDetailSliderReadouts();
      renderVideoDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function renderVideoDetailSettingsBuilderGuidance() {
      const lines = [
        "Guardrail: these values influence remux-vs-encode precision and fallback behavior; they do not change any files until backend save and a later backend-owned run.",
      ];
      videoDetailSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = settingsDisplayLabels?.[key] || field?.label || key;
        const valueText = formatVideoDetailBuilderValue(key, id, kind);
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
      updateVideoDetailSliderReadouts();
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
