(function () {
  // eslint-disable-next-line max-lines-per-function -- video builder keeps one panel's controls and readouts together.
  function createVideoDetailSettingsBuilder(deps) {
    const {
      byId,
      clearRows,
      formatSettingsChoiceLabel,
      formatSettingsListValue,
      getLastSettings,
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
      setVideoDetailBuilderControl("settings-builder-encode-ladder", "EncodeLadder", "select", "auto");
      setVideoDetailBuilderControl("settings-builder-video-codec", "VideoCodec", "select", "hevc_nvenc");
      setVideoDetailBuilderControl("settings-builder-encoder-backend", "EncoderBackend", "select", "auto");
      setVideoDetailBuilderControl("settings-builder-output-container", "OutputContainer", "select", "mkv");
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
      setVideoDetailBuilderControl("settings-video-cpu-mutex-wait", "CpuEncodeMutexWaitSeconds", "number", 3600);
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

    function settingsEncoderCapabilityReport(settings = getLastSettings()) {
      const report = settings?.encoder_capability_report;
      return report && typeof report === "object" ? report : {};
    }

    function settingsEncoderCapabilityStatus(report = settingsEncoderCapabilityReport()) {
      return String(report.operator_status || "Not loaded");
    }

    function settingsEncoderCapabilityBackendCountsText(counts) {
      if (!counts || typeof counts !== "object") return "";
      return Object.entries(counts)
        .map(([backend, bucket]) => {
          const available = Number(bucket?.available || 0);
          const total = Number(bucket?.total || 0);
          return `${backend}: ${available}/${total} available`;
        })
        .join("; ");
    }

    function settingsEncoderCapabilityList(value) {
      return Array.isArray(value)
        ? value.map((item) => String(item || "").trim()).filter(Boolean)
        : [];
    }

    function settingsEncoderCapabilityActivationLines(report = settingsEncoderCapabilityReport()) {
      if (!report?.schema_version) return [];
      const active = settingsEncoderCapabilityList(report.active_encoders);
      const inactive = settingsEncoderCapabilityList(report.available_inactive_encoders);
      const unknown = settingsEncoderCapabilityList(report.activation_unknown_encoders);
      const lines = [
        `Descriptor activation: active=${active.length}; available inactive=${inactive.length}; activation unknown=${unknown.length}.`,
      ];
      if (active.length) lines.push(`Active descriptor-owned encoders: ${active.join(", ")}.`);
      if (inactive.length) lines.push(`Available but not active for descriptor-owned attempts: ${inactive.join(", ")}.`);
      if (unknown.length) lines.push(`Descriptor activation unknown: ${unknown.join(", ")}.`);
      return lines;
    }

    function settingsEncoderCapabilityHardwareRuntimeLines(report = settingsEncoderCapabilityReport()) {
      if (!report?.schema_version) return [];
      const verified = settingsEncoderCapabilityList(report.hardware_runtime_verified_encoders);
      const skipped = settingsEncoderCapabilityList(report.hardware_runtime_skipped_encoders);
      const activeUnverified = settingsEncoderCapabilityList(report.active_hardware_runtime_unverified_encoders);
      const lines = [
        `Hardware runtime proof: verified=${verified.length}${verified.length ? ` (${verified.join(", ")})` : ""}; runtime skipped=${skipped.length}${skipped.length ? ` (${skipped.join(", ")})` : ""}; active unverified=${activeUnverified.length}${activeUnverified.length ? ` (${activeUnverified.join(", ")})` : ""}.`,
      ];
      if (activeUnverified.length) {
        lines.push(`Active hardware descriptors without runtime proof remain review-only: ${activeUnverified.join(", ")}.`);
      }
      if (skipped.length) {
        lines.push(`Skipped hardware runtime probes need host-hardware validation before activation: ${skipped.join(", ")}.`);
      }
      return lines;
    }

    function settingsEncoderCapabilitySummaryLines(report = settingsEncoderCapabilityReport()) {
      if (!report?.schema_version) {
        return ["No encoder capability report is loaded."];
      }
      const lines = Array.isArray(report.summary_lines) && report.summary_lines.length
        ? report.summary_lines.map((line) => String(line))
        : [`Status: ${settingsEncoderCapabilityStatus(report)}.`];
      if (report.source_path) lines.push(`Evidence file: ${report.source_path}.`);
      if (report.generated_at) lines.push(`Generated: ${report.generated_at}.`);
      const counts = settingsEncoderCapabilityBackendCountsText(report.backend_counts);
      if (counts) lines.push(`Backend availability: ${counts}.`);
      settingsEncoderCapabilityActivationLines(report).forEach((line) => lines.push(line));
      settingsEncoderCapabilityHardwareRuntimeLines(report).forEach((line) => lines.push(line));
      const evidence = report.evidence && typeof report.evidence === "object" ? report.evidence : {};
      const metadataProof = String(evidence.metadata_proof_state || "not collected");
      const playbackProof = String(evidence.playback_proof_state || "not collected");
      lines.push(`Evidence scope: availability/activation/runtime probe only; metadata proof=${metadataProof}; playback proof=${playbackProof}.`);
      lines.push("An available encoder is not a safe-output or daily-driver claim; output metadata verification and named-client playback proof are separate backend evidence.");
      lines.push("Read-only annotation: dropdown choices stay visible; backend Save and encode planning remain authoritative.");
      return lines;
    }

    function settingsEncoderCapabilityRowEvidence(row) {
      const flags = [];
      if (row.encoder_list_match) flags.push("listed");
      if (row.runtime_ok) flags.push("runtime ok");
      if (row.runtime_probe_skipped) flags.push("runtime skipped");
      if (row.backend_invalidated) flags.push("backend invalidated");
      if (row.activation_known) {
        flags.push(row.descriptor_flags_active ? "descriptor flags active" : "descriptor flags inactive");
      } else if (row.available) {
        flags.push("descriptor activation unknown");
      }
      if (Array.isArray(row.activation)) {
        row.activation.forEach((item) => {
          if (!item || typeof item !== "object") return;
          const role = String(item.role || "attempt");
          const active = item.active ? "active" : "inactive";
          const reason = String(item.reason || "").trim();
          flags.push(`${role} ${active}${reason ? `: ${reason}` : ""}`);
        });
      }
      if (row.probed_at) flags.push(`probed ${row.probed_at}`);
      if (row.reason) flags.push(row.reason);
      return flags.join("; ") || "No row evidence.";
    }

    function appendEncoderCapabilityCell(row, value) {
      const cell = document.createElement("td");
      cell.textContent = value === null || value === undefined ? "" : String(value);
      row.appendChild(cell);
    }

    function renderSettingsEncoderCapabilityReport(settings = getLastSettings()) {
      const report = settingsEncoderCapabilityReport(settings);
      setText("settings-encoder-capability-status", settingsEncoderCapabilityStatus(report));
      setText("settings-encoder-capability-summary", settingsEncoderCapabilitySummaryLines(report).join("\n"));
      const tbody = byId("settings-encoder-capability-rows");
      if (!tbody) return;
      const rows = Array.isArray(report.encoders) ? report.encoders : [];
      if (!rows.length) {
        clearRows(tbody, 4, "No encoder capability rows are loaded.");
      } else {
        tbody.textContent = "";
        rows.forEach((item) => {
          const row = document.createElement("tr");
          const roles = Array.isArray(item.roles) ? item.roles.join(", ") : "";
          appendEncoderCapabilityCell(row, item.encoder_name || item.probe_encoder_name || "(unknown)");
          appendEncoderCapabilityCell(row, [item.backend, item.family, roles].filter(Boolean).join(" / "));
          appendEncoderCapabilityCell(row, item.available ? "Available" : "Unavailable");
          appendEncoderCapabilityCell(row, settingsEncoderCapabilityRowEvidence(item));
          tbody.appendChild(row);
        });
      }
      setText("settings-encoder-capability-legend", "Encoder capability rows are read-only availability, activation, and runtime-probe evidence; they do not certify metadata preservation or playback. Unavailable rows do not remove saved choices.");
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
        return false;
      }
      writeSettingsPatchJson(patch, "Video detail builder prepared remux, H.264 copy, CPU fallback, and legacy flag keys for Save Settings. Backend Save still validates before writing.");
      videoDetailSettingsBuilderState.initialized = true;
      videoDetailSettingsBuilderState.dirty = true;
      setText("settings-video-builder-status", `${Object.keys(patch).length} video detail change keys ready`);
      updateVideoDetailSliderReadouts();
      renderVideoDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
      return true;
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
      const capabilityReport = settingsEncoderCapabilityReport();
      lines.push("", `Encoder capability report: ${settingsEncoderCapabilityStatus(capabilityReport)}.`);
      settingsEncoderCapabilitySummaryLines(capabilityReport).slice(0, 4).forEach((line) => {
        lines.push(`  ${line}`);
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
      settingsEncoderCapabilityReport,
      settingsEncoderCapabilityStatus,
      settingsEncoderCapabilitySummaryLines,
      settingsEncoderCapabilityHardwareRuntimeLines,
      renderSettingsEncoderCapabilityReport,
    };
  }

  window.__settingsViewVideoBuilderModule = {
    createVideoDetailSettingsBuilder,
  };
})();
