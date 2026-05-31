// crossPageContextView.settings.js
// Split child of crossPageContextView.js — owns cross-page settings-policy
// evidence: reading the settings workspace payload, extracting media-policy
// config keys, and producing the status/summary evidence object.
// No mutation, no API calls, no DOM access.
//
// Loaded by index.html immediately BEFORE crossPageContextView.js so the parent
// IIFE can read window.__crossPageSettingsModule, call the factory, then delete
// the stash.  After load, zero extra globals remain.
//
// Only crossPageCount is injected; everything else is self-contained.

(function () {
  "use strict";

  function createCrossPageSettingsModule({ crossPageCount }) {

    // -------------------------------------------------------------------------
    // Settings payload accessors
    // -------------------------------------------------------------------------

    function crossPageSettingsPayload(context = {}) {
      if (context.settings && typeof context.settings === "object") return context.settings;
      try {
        if (typeof window.getLastSettings === "function") return window.getLastSettings() || {};
      } catch {
        return {};
      }
      return {};
    }

    function crossPageSettingsConfig(context = {}) {
      const settings = crossPageSettingsPayload(context);
      return settings.config && typeof settings.config === "object" ? settings.config : {};
    }

    function crossPageConfigValue(config, keys) {
      for (const key of keys) {
        if (config?.[key] !== undefined && config?.[key] !== null && String(config[key]).trim() !== "") {
          return config[key];
        }
      }
      return undefined;
    }

    function crossPageFormatConfigValue(value) {
      if (Array.isArray(value)) return value.length ? value.join(", ") : "(empty)";
      if (value && typeof value === "object") return JSON.stringify(value);
      if (value === true) return "true";
      if (value === false) return "false";
      return String(value ?? "(not set)");
    }

    // -------------------------------------------------------------------------
    // Settings policy evidence
    // -------------------------------------------------------------------------

    function crossPageSettingsPolicyEvidence(context = {}) {
      const settings = crossPageSettingsPayload(context);
      const config = crossPageSettingsConfig(context);
      const configKeys = Object.keys(config || {});
      if (!configKeys.length) {
        return {
          status: "warning",
          summary: "settings workspace not loaded",
          lines: [
            "Settings workspace not loaded into the WebView refresh payload.",
            "Operator check: refresh Settings and compare saved route, size, subtitle, audio, and pending-publish policy before accepting a real sample.",
          ],
        };
      }

      const lines = [];
      const addEvidence = (label, keys) => {
        const value = crossPageConfigValue(config, keys);
        if (value !== undefined) lines.push(`${label}: ${crossPageFormatConfigValue(value)}`);
      };
      addEvidence("Routing/profile", ["RoutingProfile", "RouteProfile", "EncodeRoutingProfile", "CompatibilityProfile", "PlexCompatibilityProfile", "EncodeLadder"]);
      addEvidence("Video codec", ["VideoCodec", "PreferredVideoCodec", "Encoder"]);
      addEvidence("Output container", ["OutputContainer", "Container"]);
      addEvidence("H.264 copy/remux", ["AllowH264RemuxIfPlexCompatible", "H264RemuxMaxBitrateMbps", "H264RemuxMaxHeight"]);
      addEvidence("Size-growth guard", ["MaxEncodeGrowthPercent", "ForcedEncodeMaxGrowthPercent", "StrictEncodeGrowthLimit", "EnforceEncodeGrowthLimit"]);
      addEvidence("Preferred subtitle languages", ["SubKeepLanguages", "PreferredSubtitleLanguages", "Tx3gExtractLanguages", "BdpgsExtractLanguages", "VobSubExtractLanguages"]);
      addEvidence("TX3G SRT/original policy", ["ConvertTx3gToSrt", "DropTx3gAfterConversion"]);
      addEvidence("BDPGS SRT/original policy", ["ConvertBdpgsToSrt", "DropBdpgsAfterConversion"]);
      addEvidence("VobSub SRT/original policy", ["ConvertVobSubToSrt", "DropVobSubAfterConversion"]);
      addEvidence("ASS original policy", ["ConvertAssToSrt", "DropAssAfterConversion", "AssConversionMode"]);
      addEvidence("Audio policy", ["AudioPassthroughProfile", "CompatibleAudioCodecs", "PreferredDefaultAudioLanguages", "AudioTranscodeCodec", "AudioMaxChannels", "AllowNoAudio"]);
      addEvidence("Pending publish policy", ["EnableDeferredPublish", "DeferredPublish", "PendingPublishEnabled", "CleanupRemoteStagingAfterPublish", "TransientPublishRetries"]);

      const errors = Array.isArray(settings.errors) ? settings.errors : [];
      const warnings = Array.isArray(settings.warnings) ? settings.warnings : [];
      const highest = String(settings.risk_summary?.highest_severity || "").toLowerCase();
      const riskCount = crossPageCount(settings.risk_summary?.total_count);
      const mediaReadiness = settings.media_policy_readiness || {};
      const mediaReadinessStatus = String(mediaReadiness.operator_status || "").toLowerCase();
      const mediaCounts = mediaReadiness.counts || {};
      if (mediaReadiness.schema_version) {
        lines.push(`Backend media-policy readiness: ${mediaReadiness.operator_status || "unknown"}; coherent=${mediaCounts.coherent || 0}; review=${mediaCounts.review || 0}; blocked=${mediaCounts.blocked || 0}`);
      }
      let status = "match";
      if (errors.length || highest === "critical" || mediaReadinessStatus.includes("blocked")) status = "blocked";
      else if (highest === "high" || warnings.length || riskCount || mediaReadinessStatus.includes("review")) status = "warning";

      return {
        status,
        summary: `settings schema=${settings.schema_version || "unknown"}; highest risk=${settings.risk_summary?.highest_severity || "none"}; media readiness=${mediaReadiness.operator_status || "unknown"}; warnings=${warnings.length}; errors=${errors.length}`,
        lines: lines.length ? lines : ["Settings config loaded, but no known media-policy keys were visible in the payload."],
      };
    }

    // -------------------------------------------------------------------------
    // Factory return
    // -------------------------------------------------------------------------

    return {
      crossPageSettingsPolicyEvidence,
    };
  }

  window.__crossPageSettingsModule = { createCrossPageSettingsModule };
})();
