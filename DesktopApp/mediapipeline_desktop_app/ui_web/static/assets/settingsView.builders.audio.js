(function () {
  function createAudioSettingsBuilder(deps) {
    const {
      audioSettingsBuilderFields,
      audioSettingsBuilderState,
      byId,
      formatSettingsChoiceLabel,
      formatSettingsListValue,
      parseSettingsListText,
      readSettingsBuilderNumber,
      refreshSettingsSelectChoices,
      renderSettingsActiveMediaPolicyHandoff,
      renderSettingsMediaPolicyCrossCheck,
      setSettingsBuilderControl,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      writeSettingsPatchJson,
    } = deps;

    function refreshAudioSettingsBuilderChoices() {
      refreshSettingsSelectChoices(audioSettingsBuilderFields);
    }

    function setAudioBuilderControl(id, key, kind, fallback) {
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

    function syncAudioSettingsBuilderFromConfig() {
      refreshAudioSettingsBuilderChoices();
      setAudioBuilderControl("settings-audio-passthrough-profile", "AudioPassthroughProfile", "select", "plex_balanced");
      setAudioBuilderControl("settings-audio-compatible-codecs", "CompatibleAudioCodecs", "list", ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]);
      setAudioBuilderControl("settings-audio-preferred-languages", "PreferredDefaultAudioLanguages", "list", ["english"]);
      setAudioBuilderControl("settings-audio-transcode-codec", "AudioTranscodeCodec", "select", "eac3");
      setAudioBuilderControl("settings-audio-transcode-bitrate", "AudioTranscodeBitrate", "select", "640k");
      setAudioBuilderControl("settings-audio-auto-bitrate", "AudioTranscodeAutoBitrateByChannels", "bool", false);
      setAudioBuilderControl("settings-audio-downmix-mode", "AudioDownmixMode", "select", "max_channels");
      setAudioBuilderControl("settings-audio-max-channels", "AudioMaxChannels", "number_select", 6);
      setAudioBuilderControl("settings-audio-allow-no-audio", "AllowNoAudio", "bool", false);
      audioSettingsBuilderState.initialized = true;
      audioSettingsBuilderState.dirty = false;
      setText("settings-audio-builder-status", "Loaded current values");
      renderAudioSettingsBuilderGuidance();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markAudioSettingsBuilderDirty() {
      audioSettingsBuilderState.initialized = true;
      audioSettingsBuilderState.dirty = true;
      setText("settings-audio-builder-status", "Editing audio values");
      renderAudioSettingsBuilderGuidance();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function readAudioBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : kind === "list" ? [] : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(element.value);
      if (kind === "number_select") return readSettingsBuilderNumber(id, label);
      return settingsBuilderInputValue(id);
    }

    function collectAudioSettingsBuilderPatch() {
      const patch = {};
      audioSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readAudioBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyAudioSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectAudioSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-audio-builder-status", "Invalid audio value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return;
      }
      writeSettingsPatchJson(patch, "Audio builder merged audio policy keys into Changes JSON. Preview or Save still uses backend validation.");
      audioSettingsBuilderState.initialized = true;
      audioSettingsBuilderState.dirty = true;
      setText("settings-audio-builder-status", `${Object.keys(patch).length} audio patch keys ready`);
      renderAudioSettingsBuilderGuidance();
      renderSettingsMediaPolicyCrossCheck();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function renderAudioSettingsBuilderGuidance() {
      const passthroughProfile = settingsBuilderInputValue("settings-audio-passthrough-profile") || "plex_balanced";
      const defaultLanguages = parseSettingsListText(byId("settings-audio-preferred-languages")?.value || "");
      const transcodeCodec = settingsBuilderInputValue("settings-audio-transcode-codec") || "eac3";
      const transcodeBitrate = settingsBuilderInputValue("settings-audio-transcode-bitrate") || "640k";
      const autoBitrate = byId("settings-audio-auto-bitrate")?.checked === true;
      const downmixMode = settingsBuilderInputValue("settings-audio-downmix-mode") || "max_channels";
      const maxChannels = settingsBuilderInputValue("settings-audio-max-channels") || "6";
      const lines = [
        "Guardrail: audio settings only stage config keys; stream selection, transcode, passthrough, and default-track decisions remain backend-owned.",
        "Default policy: keep no-audio output disabled for normal Plex libraries unless manual review requires otherwise.",
        `Audio routing summary: passthrough=${formatSettingsChoiceLabel(passthroughProfile)}; default languages=${defaultLanguages.join(", ") || "(empty)"}; transcode=${formatSettingsChoiceLabel(transcodeCodec)} ${autoBitrate ? "auto bitrate by channels" : transcodeBitrate}; downmix=${formatSettingsChoiceLabel(downmixMode)}; max channels=${maxChannels}.`,
      ];
      audioSettingsBuilderFields.forEach(([key, id, kind]) => {
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
        if (key === "AllowNoAudio" && byId(id)?.checked) {
          lines.push("  Warning: no-audio outputs can publish files Plex users may treat as broken.");
        }
        if (key === "CompatibleAudioCodecs" && !parseSettingsListText(byId(id)?.value || "").length) {
          lines.push("  Warning: empty passthrough codec list can force unexpected audio transcodes.");
        }
        if (key === "PreferredDefaultAudioLanguages" && !parseSettingsListText(byId(id)?.value || "").length) {
          lines.push("  Review: no preferred default language means default-track choice depends on source metadata.");
        }
        if (key === "AudioTranscodeAutoBitrateByChannels" && byId(id)?.checked) {
          lines.push("  Note: static transcode bitrate becomes a fallback because channel count chooses the bitrate.");
        }
        if (key === "AudioDownmixMode" && settingsBuilderInputValue(id) === "stereo") {
          lines.push("  Review: forced stereo improves compatibility but discards surround channels.");
        }
        if (key === "AudioDownmixMode" && settingsBuilderInputValue(id) === "preserve") {
          lines.push("  Review: preserve keeps source channel layouts when transcoding, which can reduce predictable client compatibility.");
        }
        if (key === "AudioPassthroughProfile" && settingsBuilderInputValue(id) === "lossless_passthrough") {
          lines.push("  Review: lossless passthrough can preserve quality but may reduce Plex Direct Play compatibility on some clients.");
        }
        if (key === "AudioPassthroughProfile" && settingsBuilderInputValue(id) === "custom_codec_list") {
          lines.push("  Review: custom codec list makes copy-vs-transcode depend on the manual codec list.");
        }
        if (key === "AudioMaxChannels" && Number(settingsBuilderInputValue(id) || 0) > 0 && Number(settingsBuilderInputValue(id) || 0) < 6) {
          lines.push("  Review: max channels below 6 can downmix normal 5.1 tracks during normalization.");
        }
      });
      setText("settings-audio-guidance", lines.join("\n") || "No audio guidance loaded.");
    }

    return {
      refreshAudioSettingsBuilderChoices,
      syncAudioSettingsBuilderFromConfig,
      markAudioSettingsBuilderDirty,
      collectAudioSettingsBuilderPatch,
      applyAudioSettingsBuilderToPatch,
      renderAudioSettingsBuilderGuidance,
    };
  }

  window.__settingsViewAudioBuilderModule = {
    createAudioSettingsBuilder,
  };
})();
