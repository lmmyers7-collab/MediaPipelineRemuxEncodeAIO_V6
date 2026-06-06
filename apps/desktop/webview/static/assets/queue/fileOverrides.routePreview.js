// queue/fileOverrides.routePreview.js
// Split child of queue/fileOverrides.drawer.js. Loaded before the drawer;
// the drawer consumes this temporary stash global and deletes it immediately.
/* eslint-disable max-lines-per-function -- moved route-preview logic during the queue-view split without behavior changes. */

(function () {
  "use strict";

  function createFileOverridesRoutePreviewModule({
    apiPost: apiPostDependency,
    backendErrorMessage,
    buildOverridePayload,
    byId,
    documentRef,
    getCurrentPath,
    isPlainObject,
    normalizeRouteChoiceOptions,
    populateRouteSelectOptions,
    routeFieldConfig,
    routeFieldKeys,
    routeForceValues,
    setStatus,
  } = {}) {
    let routePreviewTimer = null;
    const apiPost = typeof apiPostDependency === "function" ? apiPostDependency : async function () { return { ok: false, message: "Route preview API is unavailable." }; };
    const safeBackendErrorMessage = typeof backendErrorMessage === "function" ? backendErrorMessage : function (result, fallback = "Unknown error.") { return String(result?.message || fallback); };
    const safeBuildOverridePayload = typeof buildOverridePayload === "function" ? buildOverridePayload : function () { return null; };
    const safeById = typeof byId === "function" ? byId : function (id) { return document.getElementById(id); };
    const safeDocument = documentRef || document;
    const safeGetCurrentPath = typeof getCurrentPath === "function" ? getCurrentPath : function () { return ""; };
    const safeIsPlainObject = typeof isPlainObject === "function" ? isPlainObject : function (value) { return value && typeof value === "object" && !Array.isArray(value); };
    const safeNormalizeRouteChoiceOptions = typeof normalizeRouteChoiceOptions === "function" ? normalizeRouteChoiceOptions : function () { return []; };
    const safePopulateRouteSelectOptions = typeof populateRouteSelectOptions === "function" ? populateRouteSelectOptions : function () {};
    const safeSetStatus = typeof setStatus === "function" ? setStatus : function () {};
    const fieldConfig = routeFieldConfig && typeof routeFieldConfig === "object" ? routeFieldConfig : {};
    const fieldKeys = Array.isArray(routeFieldKeys) ? routeFieldKeys : Object.keys(fieldConfig);
    const forceValues = routeForceValues instanceof Set ? routeForceValues : new Set(["auto", "encode", "remux", "transcode"]);

    function routeControlElement(fieldKey) {
      const id = fieldConfig[fieldKey]?.controlId;
      return id ? safeById(id) : null;
    }

    function clearRoutePreviewStatus() {
      const status = safeById("fo-route-preview-status");
      if (status) {
        status.hidden = true;
        status.textContent = "";
        delete status.dataset.risk;
        status.replaceChildren();
      }
      const advisory = safeById("fo-route-encode-advisory");
      if (advisory) {
        advisory.hidden = true;
        advisory.textContent = "";
        advisory.dataset.tone = "info";
      }
    }

    function clearProcessingRouteControls() {
      if (routePreviewTimer) {
        clearTimeout(routePreviewTimer);
        routePreviewTimer = null;
      }
      fieldKeys.forEach((fieldKey) => {
        const field = safeDocument.querySelector(`[data-fo-field="${fieldKey}"]`);
        const control = routeControlElement(fieldKey);
        if (control) control.value = "";
        if (field) field.hidden = true;
      });
      const section = safeById("fo-processing-route-section");
      if (section) section.hidden = true;
      clearRoutePreviewStatus();
    }

    function renderProcessingRouteControls(payload) {
      const routeFields = safeIsPlainObject(payload?.route_video_effective_fields)
        ? payload.route_video_effective_fields
        : {};
      let supportedCount = 0;
      fieldKeys.forEach((fieldKey) => {
        const field = safeDocument.querySelector(`[data-fo-field="${fieldKey}"]`);
        const control = routeControlElement(fieldKey);
        const metadata = safeIsPlainObject(routeFields[fieldKey]) ? routeFields[fieldKey] : {};
        const choices = safeNormalizeRouteChoiceOptions(metadata);
        const supported = choices.length > 0;
        if (control && supported) safePopulateRouteSelectOptions(control, choices);
        if (field) field.hidden = !supported;
        if (supported) supportedCount += 1;
      });
      const section = safeById("fo-processing-route-section");
      if (section) section.hidden = supportedCount === 0;
      if (!supportedCount) clearRoutePreviewStatus();
    }

    function payloadHasRouteVideoOverride(payload) {
      return Boolean(
        payload
        && (
          safeIsPlainObject(payload.routing)
          || safeIsPlainObject(payload.video)
          || safeIsPlainObject(payload.subtitles?.burnTrack)
        )
      );
    }

    function routePreviewProposalFromPayload(payload) {
      const proposed = {};
      const routing = safeIsPlainObject(payload?.routing) ? payload.routing : {};
      const video = safeIsPlainObject(payload?.video) ? payload.video : {};
      const proposedRouting = {};
      const profile = String(routing.profile || "").trim();
      if (profile) {
        if (forceValues.has(profile.toLowerCase())) proposedRouting.forceRoute = profile;
        else proposedRouting.routingProfile = profile;
      }
      if (routing.routeThresholdMode) proposedRouting.routeThresholdMode = routing.routeThresholdMode;
      if (Object.keys(proposedRouting).length) proposed.routing = proposedRouting;

      const proposedVideo = {};
      if (video.codec) proposedVideo.codec = video.codec;
      if (video.container) proposedVideo.container = video.container;
      if (video.encodePreset) proposedVideo.encodePreset = video.encodePreset;
      if (video.encodeLadder) proposedVideo.encodeLadder = video.encodeLadder;
      if (Object.keys(proposedVideo).length) proposed.video = proposedVideo;
      if (safeIsPlainObject(payload?.subtitles?.burnTrack)) {
        proposed.subtitles = { burnTrack: payload.subtitles.burnTrack };
      }
      return proposed;
    }

    function routePreviewWarningMessages(result) {
      const warnings = [];
      if (Array.isArray(result?.warnings)) {
        result.warnings.forEach((warning) => {
          const message = String(safeIsPlainObject(warning) ? warning.message : warning || "").trim();
          if (message) warnings.push(message);
        });
      }
      if (Array.isArray(result?.route_video_processing?.warnings)) {
        result.route_video_processing.warnings.forEach((warning) => {
          const message = String(warning || "").trim();
          if (message) warnings.push(message);
        });
      }
      return Array.from(new Set(warnings));
    }

    function routeTextForAdvisory(value) {
      return String(value || "").trim().toLowerCase();
    }

    function routeTextIsEncode(value) {
      const route = routeTextForAdvisory(value);
      return route === "encode" || route === "transcode";
    }

    function warningMentionsForcedEncode(message) {
      const text = String(message || "").toLowerCase();
      return (
        /(force|forces|forced|may force).*(encode|transcode)/.test(text)
        || /(encode|transcode).*(force|forces|forced)/.test(text)
      );
    }

    function setRouteEncodeAdvisory(text, tone = "info") {
      const advisory = safeById("fo-route-encode-advisory");
      if (!advisory) return;
      const message = String(text || "").trim();
      advisory.textContent = message;
      advisory.hidden = !message;
      advisory.dataset.tone = tone;
    }

    function routePreviewEncodeAdvisory(result) {
      if (result?.ok === false) {
        return {
          tone: "warning",
          text: "May encode: not checked. Route preview failed; read the preview error before saving.",
        };
      }
      const impact = safeIsPlainObject(result?.impact) ? result.impact : {};
      const proposed = safeIsPlainObject(result?.proposed) ? result.proposed : {};
      const processing = safeIsPlainObject(result?.route_video_processing) ? result.route_video_processing : {};
      const proposedRoute = routeTextForAdvisory(proposed.route || processing.route);
      const warnings = routePreviewWarningMessages(result);
      const forcedByWarning = warnings.some(warningMentionsForcedEncode);
      const willForceEncode = Boolean(
        impact.will_force_transcode
        || processing.will_force_transcode
        || routeTextIsEncode(proposedRoute)
        || forcedByWarning
      );
      if (willForceEncode) {
        return {
          tone: "warning",
          text: "Force encode: backend preview says these settings can route this file to a full video encode/transcode.",
        };
      }
      if (proposedRoute === "remux" || proposedRoute === "copy") {
        return {
          tone: "safe",
          text: "Will Remux: backend preview keeps this file on remux/copy; review any route warnings before saving.",
        };
      }
      const risk = String(impact.estimated_risk || "").trim().toLowerCase();
      if (impact.requires_confirmation || risk === "medium" || risk === "high") {
        return {
          tone: "warning",
          text: "May encode: possible. These settings can change remux-vs-encode routing; backend preview did not prove a forced encode.",
        };
      }
      return {
        tone: "safe",
        text: "Will Remux: backend preview did not report an encode requirement for this override.",
      };
    }

    function renderRouteEncodeAdvisory(result) {
      const advisory = routePreviewEncodeAdvisory(result);
      setRouteEncodeAdvisory(advisory.text, advisory.tone);
    }

    function renderRoutePreviewPayload(result) {
      const status = safeById("fo-route-preview-status");
      if (!status) return;
      status.replaceChildren();
      status.hidden = false;
      delete status.dataset.risk;

      const impact = safeIsPlainObject(result?.impact) ? result.impact : {};
      const risk = String(impact.estimated_risk || "").trim();
      if (risk) status.dataset.risk = risk;
      const current = safeIsPlainObject(result?.current) ? result.current : {};
      const proposed = safeIsPlainObject(result?.proposed) ? result.proposed : {};
      const processing = safeIsPlainObject(result?.route_video_processing) ? result.route_video_processing : {};

      const summary = safeDocument.createElement("p");
      summary.className = "fo-route-preview-summary";
      const currentRoute = String(current.route || "").trim();
      const proposedRoute = String(proposed.route || processing.route || "").trim();
      if (currentRoute || proposedRoute) {
        summary.textContent = `Route preview: ${currentRoute || "current route"} -> ${proposedRoute || "inherited route"}.`;
      } else if (result?.ok === false) {
        summary.textContent = safeBackendErrorMessage(result, "Route preview failed.");
      } else {
        summary.textContent = "Route preview available for selected processing overrides.";
      }
      status.appendChild(summary);

      const warnings = routePreviewWarningMessages(result);
      if (warnings.length) {
        const list = safeDocument.createElement("ul");
        list.className = "fo-route-preview-list";
        warnings.forEach((message) => {
          const item = safeDocument.createElement("li");
          item.textContent = message;
          list.appendChild(item);
        });
        status.appendChild(list);
      }
      renderRouteEncodeAdvisory(result);
    }

    function renderRoutePreviewFromEffectivePayload(payload) {
      const entry = safeIsPlainObject(payload?.file_override) ? payload.file_override : {};
      const hasBurn = safeIsPlainObject(entry.subtitles?.burnTrack);
      if (!entry.routing && !entry.video && !hasBurn) {
        clearRoutePreviewStatus();
        return;
      }
      const processing = safeIsPlainObject(payload?.route_video_processing) ? payload.route_video_processing : {};
      const warnings = Array.isArray(processing.warnings) ? processing.warnings : [];
      if (!warnings.length) {
        clearRoutePreviewStatus();
        return;
      }
      renderRoutePreviewPayload({
        ok: true,
        proposed: { route: processing.route || "" },
        route_video_processing: processing,
        impact: {
          estimated_risk: processing.will_force_transcode ? "high" : "medium",
          will_force_transcode: Boolean(processing.will_force_transcode),
          requires_confirmation: false,
        },
        warnings,
      });
    }

    async function loadRoutePreviewForPayload(payload) {
      const proposed = routePreviewProposalFromPayload(payload);
      const currentPath = String(safeGetCurrentPath() || "").trim();
      if (!currentPath || !Object.keys(proposed).length) {
        clearRoutePreviewStatus();
        return { ok: true, impact: { requires_confirmation: false }, warnings: [] };
      }
      const status = safeById("fo-route-preview-status");
      if (status) {
        status.hidden = false;
        status.textContent = "Checking route impact...";
        delete status.dataset.risk;
      }
      setRouteEncodeAdvisory("May encode: checking backend route impact...", "info");
      const result = await apiPost("/api/queue/file-overrides/route-preview", {
        path: currentPath,
        proposed_override: proposed,
      });
      renderRoutePreviewPayload(result);
      return result;
    }

    async function ensureRoutePreviewAllowsSave(payload) {
      if (!payloadHasRouteVideoOverride(payload)) return true;
      let result;
      try {
        result = await loadRoutePreviewForPayload(payload);
      } catch (err) {
        safeSetStatus("Error previewing route impact: " + (err.message || err));
        return false;
      }
      if (!result || result.ok === false) {
        safeSetStatus("Error: " + safeBackendErrorMessage(result, "Route preview failed."));
        return false;
      }
      return true;
    }

    async function refreshRoutePreviewFromCurrentForm() {
      if (!String(safeGetCurrentPath() || "").trim()) return;
      const payload = safeBuildOverridePayload();
      if (!payloadHasRouteVideoOverride(payload)) {
        clearRoutePreviewStatus();
        return;
      }
      try {
        await loadRoutePreviewForPayload(payload);
      } catch (err) {
        const status = safeById("fo-route-preview-status");
        if (status) {
          status.hidden = false;
          status.textContent = "Route preview failed: " + (err.message || err);
          status.dataset.risk = "high";
        }
      }
    }

    function scheduleRoutePreviewFromCurrentForm() {
      if (routePreviewTimer) clearTimeout(routePreviewTimer);
      routePreviewTimer = setTimeout(() => {
        routePreviewTimer = null;
        refreshRoutePreviewFromCurrentForm();
      }, 250);
    }

    return {
      clearProcessingRouteControls,
      clearRoutePreviewStatus,
      ensureRoutePreviewAllowsSave,
      loadRoutePreviewForPayload,
      payloadHasRouteVideoOverride,
      refreshRoutePreviewFromCurrentForm,
      renderProcessingRouteControls,
      renderRoutePreviewFromEffectivePayload,
      routeControlElement,
      scheduleRoutePreviewFromCurrentForm,
    };
  }

  window.__queueFileOverridesRoutePreviewModule = { createFileOverridesRoutePreviewModule };
})();
