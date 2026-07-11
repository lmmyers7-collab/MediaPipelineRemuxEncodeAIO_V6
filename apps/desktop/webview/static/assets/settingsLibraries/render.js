(function () {
  function createSettingsLibrariesRenderingModule(deps = {}) {
    const {
      advancedFallbackKeys,
      boolValue,
      byId,
      choiceLabels,
      collectProfilesFromDom,
      currentProfilesFromSettings,
      defaultSettingValue,
      designationValues,
      escapeHtml,
      fieldDefinition,
      formatValue,
      inapplicableOverrideKeys,
      inheritedSet,
      mp4CompatibilityPreset,
      normalizeOverrides,
      overrideFieldsForGroup,
      overrideGroupList,
      overrideLayouts,
      overrideStatus,
      pathCanReset,
      pathEvidence,
      pathIsInherited,
      pathPickerTargetForLibraryField,
      pathSourceText,
      pathState,
      pathStateClass,
      profileCardsFromDom,
      profilesEquivalent,
      profileState,
      readOverrideControlValue,
      renderActiveLibraryCommandState,
      renderProfileCards,
      routeBucketDefinitions,
      routeModel,
      routeSizeFields,
      routeToleranceKeys,
      setLibraryFeedback,
      setText,
      stableComparable,
      state,
      syncLibraryCompatibilityAvailability,
      syncLibraryRouteReadouts,
      syncLibraryWatchControlsFromConfig,
      text,
    } = deps;

    function choiceLabel(key) {
      const field = fieldDefinition(key);
      if (field?.label) return field.label;
      return choiceLabels[key] || key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }
  
    function fieldHelpText(field) {
      return String(field?.help_text || field?.help || "").trim();
    }
  
    function metadataTags(value) {
      if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
      const textValue = String(value || "").trim();
      return textValue ? [textValue] : [];
    }
  
    function fieldIsAdvanced(key, field) {
      const advancedVisibility = String(field?.advanced_visibility || "").trim().toLowerCase();
      const section = String(field?.section || "").trim().toLowerCase();
      const tags = [
        ...metadataTags(field?.rule_taxonomy),
        ...metadataTags(field?.strictness),
      ].map((value) => String(value || "").trim().toLowerCase());
      return advancedVisibility === "advanced"
        || section === "advanced"
        || tags.includes("advanced")
        || advancedFallbackKeys.has(String(key || field?.key || ""));
    }
  
    function choiceValueLabel(value) {
      const key = String(value ?? "");
      return choiceLabels[key] || key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }
  
    function inputTypeForField(field) {
      if (["integer", "number"].includes(field?.value_type)) return "number";
      if (field?.kind === "optional_float") return "number";
      if (["int", "optional_int", "combo_int"].includes(field?.kind)) return "number";
      return "text";
    }
  
    function fieldOwnValue(field, key) {
      if (!field || !Object.prototype.hasOwnProperty.call(field, key)) return undefined;
      const value = field[key];
      return value === null || value === undefined || value === "" ? undefined : value;
    }
  
    function buildOverrideControl(key, value, disabled = false) {
      const field = fieldDefinition(key);
      const kind = field?.kind || "";
      const disabledAttr = disabled ? " disabled" : "";
      if (kind === "bool") {
        return `<input type="checkbox"${disabledAttr} data-library-override-control data-library-override-key="${escapeHtml(key)}" ${boolValue(value) ? "checked" : ""}>`;
      }
      const allowedValues = Array.isArray(field?.allowed_values) && field.allowed_values.length ? field.allowed_values : field?.choices;
      if (Array.isArray(allowedValues) && allowedValues.length) {
        const choices = allowedValues.map((choice) => String(choice));
        const valueText = String(value ?? "");
        const hasCurrent = choices.includes(valueText);
        const options = allowedValues.map((choice) => {
          const optionValue = String(choice);
          const title = field.choice_help && field.choice_help[optionValue] ? ` title="${escapeHtml(field.choice_help[optionValue])}"` : "";
          return `<option value="${escapeHtml(optionValue)}"${optionValue === valueText ? " selected" : ""}${title}>${escapeHtml(choiceValueLabel(optionValue))}</option>`;
        });
        if (valueText && !hasCurrent) {
          options.unshift(`<option value="${escapeHtml(valueText)}" selected>${escapeHtml(valueText)}</option>`);
        }
        return `<select${disabledAttr} data-library-override-control data-library-override-key="${escapeHtml(key)}">${options.join("")}</select>`;
      }
      const inputType = inputTypeForField(field);
      const minValue = inputType === "number" ? fieldOwnValue(field, "min") : undefined;
      const maxValue = inputType === "number" ? fieldOwnValue(field, "max") : undefined;
      const stepValue = inputType === "number" ? (fieldOwnValue(field, "step") ?? (field?.kind === "optional_float" ? "any" : "")) : "";
      const unitValue = fieldOwnValue(field, "unit") ?? fieldOwnValue(field, "display_unit");
      const min = minValue !== undefined ? ` min="${escapeHtml(minValue)}"` : "";
      const max = maxValue !== undefined ? ` max="${escapeHtml(maxValue)}"` : "";
      const step = stepValue ? ` step="${escapeHtml(stepValue)}"` : "";
      const unit = unitValue !== undefined ? ` data-settings-unit="${escapeHtml(unitValue)}"` : "";
      const textAttrs = inputType === "text" ? ' autocomplete="off" spellcheck="false"' : "";
      return `<input type="${inputType}"${min}${max}${step}${unit}${textAttrs}${disabledAttr} data-library-override-control data-library-override-key="${escapeHtml(key)}" value="${escapeHtml(formatValue(value))}">`;
    }
  
    function effectiveOverrideValue(profile, groupKey, fieldKey) {
      const groupOverrides = profile.overrides?.[groupKey] || {};
      if (Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey)) {
        return groupOverrides[fieldKey];
      }
      return defaultSettingValue(fieldKey);
    }
  
    function settingOverrideEvidence(profile, groupKey, fieldKey) {
      const evidence = profileState(profile)?.setting_overrides?.[groupKey]?.[fieldKey];
      return evidence && typeof evidence === "object" && !Array.isArray(evidence) ? evidence : null;
    }
  
    function overrideValuesEqual(left, right) {
      return JSON.stringify(stableComparable(left)) === JSON.stringify(stableComparable(right));
    }
  
    function overrideStateText(isOverride, value, inheritedValue) {
      if (!isOverride) return "Inherited from global";
      if (overrideValuesEqual(value, inheritedValue)) return "Library override — currently same as global";
      return "Library override";
    }
  
    function renderUseDefaultButton(groupKey, fieldKey, isOverride) {
      return `<button type="button" class="tertiary-button settings-library-override-use-default" data-library-use-default-override data-library-override-group="${escapeHtml(groupKey)}" data-library-override-key="${escapeHtml(fieldKey)}" title="Reset to inherited removes the persisted library override key; it does not write the global value into this library."${isOverride ? "" : " hidden disabled"}>Reset to inherited</button>`;
    }
  
    function routeNumberValue(value, fallback = 0) {
      if (typeof routeModel.numberValue === "function") return routeModel.numberValue(value, fallback);
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    }
  
    function routeFormatPercent(value) {
      if (typeof routeModel.formatPercent === "function") return routeModel.formatPercent(value);
      const number = Number(value);
      if (!Number.isFinite(number)) return "";
      return number.toFixed(6).replace(/\.?0+$/, "");
    }
  
    function routeFormatHeight(value) {
      if (typeof routeModel.formatHeight === "function") return routeModel.formatHeight(value);
      const number = Number(value);
      return Number.isFinite(number) ? String(Math.round(number)) : "";
    }
  
    function routeSafeIdPart(value) {
      return String(value || "library").replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "library";
    }
  
    function routeElementId(profile, suffix) {
      return `settings-library-route-${routeSafeIdPart(profile?.id)}-${suffix}`;
    }
  
    function routeValueAvailable(value) {
      return value !== undefined && value !== null && String(value).trim() !== "";
    }
  
    function routeValueFromBackendSource(values, key) {
      if (values && Object.prototype.hasOwnProperty.call(values, key) && routeValueAvailable(values[key])) {
        return values[key];
      }
      return defaultSettingValue(key);
    }
  
    function routeMetadataMissingKeys(values) {
      return routeSizeFields.filter((key) => {
        const field = fieldDefinition(key);
        const hasMetadata = Boolean(field && Object.keys(field).length);
        return !hasMetadata || !routeValueAvailable(routeValueFromBackendSource(values, key));
      });
    }
  
    function routeSourceSummary(values) {
      const missing = routeMetadataMissingKeys(values);
      if (missing.length) {
        const visibleKeys = missing.slice(0, 5).join(", ");
        const suffix = missing.length > 5 ? `, and ${missing.length - 5} more` : "";
        return `Advisory only: backend route metadata/current values are missing for ${visibleKeys}${suffix}. Preview or save with the backend before treating these readouts as evidence.`;
      }
      return "Readouts use backend field metadata and current config values. Library controls stage overrides only; backend Save remains authoritative.";
    }
  
    function routeValuesFromObject(values) {
      return routeSizeFields.reduce((accumulator, key) => {
        accumulator[key] = routeValueFromBackendSource(values, key);
        return accumulator;
      }, {});
    }
  
    function routeBoundariesFromValues(values) {
      if (typeof routeModel.boundariesFromValues === "function") return routeModel.boundariesFromValues(values);
      const withDefaults = routeValuesFromObject(values);
      return {
        route1080pMaxHeight: Math.round(1080 * (1 + (routeNumberValue(withDefaults.Route1080pUpperHeightTolerancePercent, 0) / 100))),
        route1440pMinHeight: Math.round(1440 * (1 - (routeNumberValue(withDefaults.Route1440pLowerHeightTolerancePercent, 0) / 100))),
        route1440pMaxHeight: Math.round(1440 * (1 + (routeNumberValue(withDefaults.Route1440pUpperHeightTolerancePercent, 0) / 100))),
        route4kMinHeight: Math.round(2160 * (1 - (routeNumberValue(withDefaults.Route4KLowerHeightTolerancePercent, 0) / 100))),
      };
    }
  
    function routeRailPercentages(boundaries) {
      if (typeof routeModel.railPercentages === "function") return routeModel.railPercentages(boundaries);
      const minHeight = 1080;
      const maxHeight = 2160;
      const span = maxHeight - minHeight;
      const clamp = (value) => Math.min(100, Math.max(0, Number(value)));
      return {
        firstPct: clamp(((routeNumberValue(boundaries?.route1080pMaxHeight, minHeight) - minHeight) / span) * 100),
        secondPct: clamp(((routeNumberValue(boundaries?.route4kMinHeight, maxHeight) - minHeight) / span) * 100),
      };
    }
  
    function routeValuesFromProfile(profile) {
      return routeSizeFields.reduce((accumulator, key) => {
        accumulator[key] = effectiveLibraryOverrideValue(profile, "editor", key);
        return accumulator;
      }, {});
    }
  
    function routeValuesFromCard(card) {
      return routeSizeFields.reduce((accumulator, key) => {
        const control = card.querySelector(`[data-library-override-key="${key}"] [data-library-override-control]`);
        accumulator[key] = control ? readOverrideControlValue(control, key) : defaultSettingValue(key);
        return accumulator;
      }, {});
    }
  
    function effectiveLibraryOverrideValue(profile, groupKey, fieldKey) {
      const groupOverrides = profile.overrides?.[groupKey] || {};
      const evidence = settingOverrideEvidence(profile, groupKey, fieldKey);
      if (Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey)) return groupOverrides[fieldKey];
      if (evidence && Object.prototype.hasOwnProperty.call(evidence, "effective_value")) return evidence.effective_value;
      return defaultSettingValue(fieldKey);
    }
  
    function routeTriggerSummary(mode) {
      if (typeof routeModel.triggerSummary === "function") return routeModel.triggerSummary(mode);
      return "Routing trigger behavior follows the selected backend mode.";
    }
  
    function routeHeightPixelSummary(boundaries) {
      if (typeof routeModel.heightPixelSummary === "function") return routeModel.heightPixelSummary(boundaries);
      return `Derived direct-copy buckets: 1080p <=${routeFormatHeight(boundaries.route1080pMaxHeight)}p, 1440p ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p, 4K >=${routeFormatHeight(boundaries.route4kMinHeight)}p. Boundary values route to the higher bucket.`;
    }
  
    function routeConsequenceSummary(boundaries, values) {
      if (typeof routeModel.consequenceSummary === "function") return routeModel.consequenceSummary(boundaries, values);
      const withDefaults = routeValuesFromObject(values);
      return `A ${routeFormatHeight(boundaries.route1440pMinHeight)}p source routes as 1440p: Movie ${withDefaults.MovieRoute1440pTargetSizeGB} GB / TV ${withDefaults.TVRoute1440pTargetSizeGB} GB, direct-copy cap ${withDefaults.Route1440pMaxVideoBitrateMbps} Mbps. A ${routeFormatHeight(boundaries.route4kMinHeight)}p source routes as 4K.`;
    }
  
    function routeUnknownHeightSummary(values) {
      if (typeof routeModel.unknownHeightSummary === "function") return routeModel.unknownHeightSummary(values);
      return "Unknown-height routing remains backend-owned until ffprobe dimensions or backend fallback evidence is available.";
    }
  
    function routeEstimatedGb(value, minutes) {
      if (typeof routeModel.estimatedSizeGb === "function") return routeModel.estimatedSizeGb(value, minutes);
      const mbps = routeNumberValue(value, 0);
      return mbps > 0 ? (mbps * routeNumberValue(minutes, 0) * 60) / 8 / 1024 : 0;
    }
  
    function routeFormatEstimatedGb(value) {
      if (typeof routeModel.formatEstimatedGb === "function") return routeModel.formatEstimatedGb(value);
      const number = Number(value);
      if (!Number.isFinite(number) || number <= 0) return "0 GB";
      return number < 10 ? `${number.toFixed(1).replace(/\.0$/, "")} GB` : `${Math.round(number)} GB`;
    }
  
    function renderLibraryRouteOverrideField(profile, groupKey, fieldKey, options = {}) {
      const status = overrideStatus(groupKey, fieldKey, profile);
      if (!status.render) return "";
      const field = status.field;
      const editable = status.editable;
      const groupOverrides = profile.overrides?.[groupKey] || {};
      const evidence = settingOverrideEvidence(profile, groupKey, fieldKey);
      const hasLocalOverride = Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey);
      const isOverride = editable && (hasLocalOverride || evidence?.state === "explicit");
      const value = effectiveLibraryOverrideValue(profile, groupKey, fieldKey);
      const inheritedValue = evidence && Object.prototype.hasOwnProperty.call(evidence, "inherited_value")
        ? evidence.inherited_value
        : defaultSettingValue(fieldKey);
      const label = escapeHtml(options.label || choiceLabel(fieldKey));
      const unavailableReason = editable ? "" : status.reason || "not available for library overrides";
      const stateText = editable ? overrideStateText(isOverride, value, inheritedValue) : unavailableReason;
      const stateClass = editable ? (isOverride ? "is-custom" : "is-inherited") : "is-readonly";
      const state = `<span class="settings-library-state ${stateClass}" data-library-override-state-label>${escapeHtml(stateText)}</span>`;
      const titleText = [fieldHelpText(field), unavailableReason ? `Unavailable: ${unavailableReason}` : ""].filter(Boolean).join(" ");
      const title = titleText ? ` title="${escapeHtml(titleText)}"` : "";
      const advancedVisibility = field?.advanced_visibility || "standard";
      const persistedKey = String(field?.persisted_key || fieldKey);
      const section = String(field?.section || "");
      const scope = String(field?.scope || "");
      const baseClass = [
        "settings-library-override-row",
        "settings-library-route-override-row",
        options.hidden ? "settings-library-route-hidden-row" : "",
        options.inline ? "settings-library-route-inline-row" : "",
        fieldIsAdvanced(fieldKey, field) ? "is-advanced-field" : "",
        editable ? "" : "is-unavailable",
        isOverride ? "is-custom" : "is-inherited",
      ].filter(Boolean).join(" ");
      const advancedAttr = fieldIsAdvanced(fieldKey, field) ? " data-advanced" : "";
      const routeAttr = options.routeRole ? ` data-library-route-role="${escapeHtml(options.routeRole)}"` : "";
      const rowAttrs = `class="${baseClass}" data-library-override-row data-library-override-group="${escapeHtml(groupKey)}" data-library-override-key="${escapeHtml(fieldKey)}" data-library-persisted-key="${escapeHtml(persistedKey)}" data-library-override="${isOverride ? "true" : "false"}" data-library-override-eligible="${editable ? "true" : "false"}" data-library-section="${escapeHtml(section)}" data-library-scope="${escapeHtml(scope)}" data-library-advanced-visibility="${escapeHtml(advancedVisibility)}" data-library-unavailable-reason="${escapeHtml(unavailableReason)}"${routeAttr}${advancedAttr}${title}`;
      const control = buildOverrideControl(fieldKey, value, !editable);
      const controlMarkup = options.unit
        ? `<span class="settings-input-with-unit">${control}<span>${escapeHtml(options.unit)}</span></span>`
        : control;
      const button = editable ? renderUseDefaultButton(groupKey, fieldKey, isOverride) : "";
      const unavailable = unavailableReason ? `<span class="note settings-library-override-unavailable">${escapeHtml(unavailableReason)}</span>` : "";
      return `
        <label ${rowAttrs}>
          <span class="settings-library-override-field-heading">
            <span class="settings-library-override-label-text">${label}</span>
            ${state}
            ${button}
          </span>
          ${controlMarkup}
          ${unavailable}
        </label>
      `;
    }
  
    function renderLibraryRouteRail(boundaries) {
      const firstBoundary = routeFormatHeight(boundaries.route1080pMaxHeight);
      const secondBoundary = routeFormatHeight(boundaries.route4kMinHeight);
      const percentages = routeRailPercentages(boundaries);
      return `
        <div class="settings-route-range-rail settings-library-route-rail" data-library-route-rail style="--route-first-pct: ${routeFormatPercent(percentages.firstPct)}%; --route-second-pct: ${routeFormatPercent(percentages.secondPct)}%;">
          <div class="settings-route-slider-labels">
            <div class="settings-route-slider-bucket"><span>1080p</span><output data-library-route-readout="range-1080p">uses &lt;=${firstBoundary}p</output></div>
            <div class="settings-route-slider-bucket"><span>1440p</span><output data-library-route-readout="range-1440p">uses ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p</output></div>
            <div class="settings-route-slider-bucket"><span>4K</span><output data-library-route-readout="range-4k">uses &gt;=${secondBoundary}p</output></div>
          </div>
          <div class="settings-route-slider settings-library-route-visual" data-library-route-visual aria-hidden="true">
            <div class="settings-route-slider-track">
              <span class="settings-route-slider-fill settings-route-slider-fill-1080p"></span>
              <span class="settings-route-slider-fill settings-route-slider-fill-1440p"></span>
              <span class="settings-route-slider-fill settings-route-slider-fill-4k"></span>
            </div>
            <span class="settings-library-route-marker settings-library-route-marker-first"></span>
            <span class="settings-library-route-marker settings-library-route-marker-second"></span>
          </div>
        </div>
      `;
    }
  
    function renderLibraryRouteBoundaryControls(boundaries, describedBy) {
      const firstBoundary = routeFormatHeight(boundaries.route1080pMaxHeight);
      const secondBoundary = routeFormatHeight(boundaries.route4kMinHeight);
      const describedByAttr = describedBy ? ` aria-describedby="${escapeHtml(describedBy)}"` : "";
      return `
        <div class="settings-library-route-boundary-grid" data-library-route-boundary-controls>
          <label class="settings-library-route-boundary-field">
            <span>1080p maximum height</span>
            <span class="settings-route-range-control">
              <input type="number" min="1080" max="1439" step="1" value="${firstBoundary}" data-library-route-boundary-input="first" aria-label="1080p maximum height"${describedByAttr}>
              <span>p</span>
            </span>
          </label>
          <label class="settings-library-route-boundary-field">
            <span>4K minimum height</span>
            <span class="settings-route-range-control">
              <input type="number" min="1441" max="2160" step="1" value="${secondBoundary}" data-library-route-boundary-input="second" aria-label="4K minimum height"${describedByAttr}>
              <span>p</span>
            </span>
          </label>
        </div>
        <div class="settings-library-route-boundary-actions">
          <button type="button" class="tertiary-button" data-library-route-boundary-reset="first">Reset 1080p/1440p boundary</button>
          <button type="button" class="tertiary-button" data-library-route-boundary-reset="second">Reset 1440p/4K boundary</button>
        </div>
      `;
    }
  
    function renderLibraryRouteBucket(profile, bucket, boundaries) {
      const movieTarget = renderLibraryRouteOverrideField(profile, "editor", bucket.movieTargetKey, {
        label: `Movie ${bucket.targetLabel} target output size`,
        routeRole: "target-size",
        unit: "GB",
      });
      const tvTarget = renderLibraryRouteOverrideField(profile, "editor", bucket.tvTargetKey, {
        label: `TV ${bucket.targetLabel} target output size`,
        routeRole: "target-size",
        unit: "GB",
      });
      const bitrate = renderLibraryRouteOverrideField(profile, "editor", bucket.bitrateKey, {
        label: `${bucket.label} max bitrate for direct copy`,
        routeRole: "direct-copy-bitrate",
        unit: "Mbps",
      });
      const targetRows = [movieTarget, tvTarget].filter(Boolean).join("");
      const values = routeValuesFromProfile(profile);
      const bitrateValue = routeNumberValue(values[bucket.bitrateKey], 0);
      const tvEstimate = routeFormatEstimatedGb(routeEstimatedGb(bitrateValue, bucket.estimateMinutes.tv));
      const movieEstimate = routeFormatEstimatedGb(routeEstimatedGb(bitrateValue, bucket.estimateMinutes.movie));
      const rangeText = bucket.key === "1080p"
        ? `uses <=${routeFormatHeight(boundaries.route1080pMaxHeight)}p`
        : bucket.key === "1440p"
          ? `uses ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p`
          : `uses >=${routeFormatHeight(boundaries.route4kMinHeight)}p`;
      return `
        <section class="settings-route-bucket-card settings-library-route-bucket" data-library-route-bucket="${escapeHtml(bucket.key)}">
          <div class="settings-route-bucket-header">
            <div>
              <h4>${escapeHtml(bucket.label)}</h4>
              <p>Derived height range</p>
            </div>
            <span class="settings-route-range-ref" data-library-route-readout="bucket-${escapeHtml(bucket.key)}">${escapeHtml(rangeText)}</span>
          </div>
          <div class="settings-route-bucket-grid">
            ${targetRows ? `<div class="settings-route-bucket-group"><h5>Encoded output size (GB)</h5><div class="settings-route-target-stack">${targetRows}</div></div>` : ""}
            <div class="settings-route-bucket-group">
              <h5>Direct-copy limits</h5>
              <div class="settings-route-target-stack">${bitrate}</div>
              <p class="note" data-library-route-readout="estimate-${escapeHtml(bucket.key)}">If constant: 30m TV ~${escapeHtml(tvEstimate)}; 2h movie ~${escapeHtml(movieEstimate)}</p>
            </div>
          </div>
        </section>
      `;
    }
  
    function renderLibraryRouteSizeLayout(profile, groupKey, block) {
      const fields = new Set(block.fields || []);
      const values = routeValuesFromProfile(profile);
      const boundaries = routeBoundariesFromValues(values);
      const routeConsequenceId = routeElementId(profile, "bucket-consequences");
      const routeUnknownId = routeElementId(profile, "unknown-height");
      const routeSourceId = routeElementId(profile, "metadata-source");
      const routeBoundaryDescriptions = `${routeConsequenceId} ${routeUnknownId} ${routeSourceId}`;
      const hiddenToleranceRows = routeToleranceKeys
        .filter((key) => fields.has(key))
        .map((key) => renderLibraryRouteOverrideField(profile, groupKey, key, { hidden: true, routeRole: "height-tolerance" }))
        .join("");
      return `
        <div class="settings-library-route-editor" data-library-route-editor>
          <section class="settings-library-route-section">
            <h3>Library Goal</h3>
            ${renderLibraryRouteOverrideField(profile, groupKey, "RoutingProfile", { routeRole: "routing-profile" })}
          </section>
          <section class="settings-library-route-section">
            <h3>What Forces An Encode?</h3>
            ${renderLibraryRouteOverrideField(profile, groupKey, "RouteThresholdMode", { routeRole: "route-threshold" })}
            <p class="note settings-library-route-summary" data-library-route-summary="trigger">${escapeHtml(routeTriggerSummary(values.RouteThresholdMode))}</p>
          </section>
          <section class="settings-library-route-section">
            <h3>TV / Movie Targets By Height</h3>
            <p class="note">Target GB is the encoded output budget. Mbps is the source direct-copy/remux cap. Height chooses the bucket.</p>
            <p id="${escapeHtml(routeSourceId)}" class="note settings-library-route-summary" data-library-route-source-summary>${escapeHtml(routeSourceSummary(values))}</p>
            ${renderLibraryRouteRail(boundaries)}
            ${renderLibraryRouteBoundaryControls(boundaries, routeBoundaryDescriptions)}
            <div class="settings-route-target-editor settings-library-route-target-editor">
              ${routeBucketDefinitions.map((bucket) => renderLibraryRouteBucket(profile, bucket, boundaries)).join("")}
            </div>
            <p class="note settings-library-route-summary" data-library-route-summary="pixel">${escapeHtml(routeHeightPixelSummary(boundaries))}</p>
            <p id="${escapeHtml(routeConsequenceId)}" class="note settings-library-route-summary" data-library-route-summary="consequence">${escapeHtml(routeConsequenceSummary(boundaries, values))}</p>
            <p id="${escapeHtml(routeUnknownId)}" class="note settings-library-route-summary" data-library-route-summary="unknown">${escapeHtml(routeUnknownHeightSummary(values))}</p>
          </section>
          <section class="settings-library-route-section">
            <h3>If Encoded Output Is Too Large</h3>
            <div class="form-grid launch-form-grid settings-library-route-guard-grid">
              ${renderLibraryRouteOverrideField(profile, groupKey, "SizeGuardMode", { routeRole: "size-guard" })}
              ${renderLibraryRouteOverrideField(profile, groupKey, "MaxEncodeGrowthPercent", { routeRole: "size-guard", unit: "%" })}
              ${renderLibraryRouteOverrideField(profile, groupKey, "CompatibilityEncodeGrowthPercent", { routeRole: "size-guard", unit: "%" })}
            </div>
          </section>
          <div class="settings-library-route-hidden-fields" hidden>
            ${hiddenToleranceRows}
          </div>
        </div>
      `;
    }
  
    function renderOverrideField(profile, groupKey, fieldKey, variant = "grid") {
      const status = overrideStatus(groupKey, fieldKey, profile);
      if (!status.render) return "";
      const field = status.field;
      const editable = status.editable;
      const groupOverrides = profile.overrides?.[groupKey] || {};
      const evidence = settingOverrideEvidence(profile, groupKey, fieldKey);
      const hasLocalOverride = Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey);
      const isOverride = editable && (hasLocalOverride || evidence?.state === "explicit");
      const value = hasLocalOverride
        ? groupOverrides[fieldKey]
        : evidence && Object.prototype.hasOwnProperty.call(evidence, "effective_value")
          ? evidence.effective_value
          : effectiveOverrideValue(profile, groupKey, fieldKey);
      const inheritedValue = evidence && Object.prototype.hasOwnProperty.call(evidence, "inherited_value")
        ? evidence.inherited_value
        : defaultSettingValue(fieldKey);
      const label = escapeHtml(choiceLabel(fieldKey));
      const unavailableReason = editable ? "" : status.reason || "not available for library overrides";
      const stateText = editable ? overrideStateText(isOverride, value, inheritedValue) : unavailableReason;
      const stateClass = editable ? (isOverride ? "is-custom" : "is-inherited") : "is-readonly";
      const state = `<span class="settings-library-state ${stateClass}" data-library-override-state-label>${escapeHtml(stateText)}</span>`;
      const titleText = [fieldHelpText(field), unavailableReason ? `Unavailable: ${unavailableReason}` : ""].filter(Boolean).join(" ");
      const title = titleText ? ` title="${escapeHtml(titleText)}"` : "";
      const advancedVisibility = field?.advanced_visibility || "standard";
      const persistedKey = String(field?.persisted_key || fieldKey);
      const section = String(field?.section || "");
      const scope = String(field?.scope || "");
      const baseClass = [
        variant === "check" ? "check-row" : "",
        variant === "check-grid" ? "check-row launch-check-row" : "",
        variant === "full" ? "full-field" : "",
        "settings-library-override-row",
        fieldIsAdvanced(fieldKey, field) ? "is-advanced-field" : "",
        editable ? "" : "is-unavailable",
        isOverride ? "is-custom" : "is-inherited",
      ].filter(Boolean).join(" ");
      const advancedAttr = fieldIsAdvanced(fieldKey, field) ? " data-advanced" : "";
      const rowAttrs = `class="${baseClass}" data-library-override-row data-library-override-group="${escapeHtml(groupKey)}" data-library-override-key="${escapeHtml(fieldKey)}" data-library-persisted-key="${escapeHtml(persistedKey)}" data-library-override="${isOverride ? "true" : "false"}" data-library-override-eligible="${editable ? "true" : "false"}" data-library-section="${escapeHtml(section)}" data-library-scope="${escapeHtml(scope)}" data-library-advanced-visibility="${escapeHtml(advancedVisibility)}" data-library-unavailable-reason="${escapeHtml(unavailableReason)}"${advancedAttr}${title}`;
      const control = buildOverrideControl(fieldKey, value, !editable);
      const button = editable ? renderUseDefaultButton(groupKey, fieldKey, isOverride) : "";
      const unavailable = unavailableReason ? `<span class="note settings-library-override-unavailable">${escapeHtml(unavailableReason)}</span>` : "";
      if (field?.kind === "bool") {
        return `
          <label ${rowAttrs}>
            ${control}
            <span class="settings-library-override-label-text">${label}</span>
            ${state}
            ${button}
            ${unavailable}
          </label>
        `;
      }
      return `
        <label ${rowAttrs}>
          <span class="settings-library-override-field-heading">
            <span class="settings-library-override-label-text">${label}</span>
            ${state}
            ${button}
          </span>
          ${control}
          ${unavailable}
        </label>
      `;
    }
  
    function fieldsForGroup(profile, groupKey, fields) {
      return fields.filter((fieldKey) => overrideStatus(groupKey, fieldKey, profile).render);
    }
  
    function renderFieldGrid(profile, groupKey, fields) {
      const rows = fieldsForGroup(profile, groupKey, fields).map((fieldKey) => {
        const field = fieldDefinition(fieldKey);
        return renderOverrideField(profile, groupKey, fieldKey, field?.kind === "bool" ? "check-grid" : "grid");
      });
      if (!rows.length) return "";
      return `<div class="form-grid launch-form-grid">${rows.join("")}</div>`;
    }
  
    function renderOptionGrid(profile, groupKey, fields) {
      const rows = fieldsForGroup(profile, groupKey, fields).map((fieldKey) => renderOverrideField(profile, groupKey, fieldKey, "check"));
      if (!rows.length) return "";
      return `<div class="option-grid option-grid-compact">${rows.join("")}</div>`;
    }
  
    function renderFullFields(profile, groupKey, fields) {
      return fieldsForGroup(profile, groupKey, fields).map((fieldKey) => renderOverrideField(profile, groupKey, fieldKey, "full")).join("");
    }
  
    function renderNestedOptionPanel(profile, groupKey, block) {
      const optionGrid = renderOptionGrid(profile, groupKey, block.fields || []);
      const formGrid = renderFieldGrid(profile, groupKey, block.gridFields || []);
      if (!optionGrid && !formGrid) return "";
      return `
        <section class="option-panel">
          <div class="option-panel-heading">
            <strong>${escapeHtml(block.title || "")}</strong>
            <span>${escapeHtml(block.note || "")}</span>
          </div>
          ${optionGrid}
          ${formGrid}
        </section>
      `;
    }
  
    function renderAdvancedOverrideDisclosure(profile, groupKey, block) {
      const formGrid = renderFieldGrid(profile, groupKey, block.fields || []);
      if (!formGrid) return "";
      return `
        <details class="settings-library-advanced-disclosure" data-library-advanced-disclosure>
          <summary class="settings-library-advanced-summary">
            <span>${escapeHtml(block.title || "Advanced")}</span>
            ${block.note ? `<small>${escapeHtml(block.note)}</small>` : ""}
          </summary>
          <div class="settings-library-advanced-body">
            ${formGrid}
          </div>
        </details>
      `;
    }
  
    function renderOverrideLayout(profile, groupKey) {
      const blocks = overrideLayouts[groupKey] || [{ type: "grid", fields: overrideFieldsForGroup(groupKey) }];
      return blocks.map((block) => {
        if (block.type === "routeSize") return renderLibraryRouteSizeLayout(profile, groupKey, block);
        if (block.type === "grid") return renderFieldGrid(profile, groupKey, block.fields || []);
        if (block.type === "options") return renderOptionGrid(profile, groupKey, block.fields || []);
        if (block.type === "full") return renderFullFields(profile, groupKey, block.fields || []);
        if (block.type === "panel") return renderNestedOptionPanel(profile, groupKey, block);
        if (block.type === "advanced") return renderAdvancedOverrideDisclosure(profile, groupKey, block);
        if (block.type === "compatibility") return renderCompatibilityPresetEditorControl(profile);
        if (block.type === "note") return `<p class="note settings-library-panel-note">${escapeHtml(block.text || "")}</p>`;
        return "";
      }).join("");
    }
  
    function renderOverrideSection(profile, group) {
      const openSections = state.openOverrideSectionsByLibrary.get(profile.id);
      const isOpen = openSections instanceof Set && openSections.has(group.key);
      return `
        <details class="settings-library-override-section" data-library-override-section="${escapeHtml(group.key)}"${isOpen ? " open" : ""}>
          <summary class="settings-library-override-summary">
            <span>${escapeHtml(group.title)}</span>
          </summary>
          <div class="settings-library-override-body">
            ${renderOverrideLayout(profile, group.key)}
          </div>
        </details>
      `;
    }
  
    function profileMp4CompatibilityActive(profile) {
      const overrides = normalizeOverrides(profile || {});
      return String(overrides.editor?.OutputContainer || "").trim().toLowerCase() === "mp4";
    }
  
    function renderCompatibilityPresetEditorControl(profile) {
      const preset = mp4CompatibilityPreset();
      if (!preset) return "";
      const active = profileMp4CompatibilityActive(profile);
      return `
        <label class="settings-library-compatibility-field" data-library-compatibility-preset="${escapeHtml(preset.id)}" data-library-compatibility-active="${active ? "true" : "false"}">
          <span>Compatibility mode</span>
          <select data-library-compatibility-select>
            <option value=""${active ? "" : " selected"}>Standard library overrides</option>
            <option value="${escapeHtml(preset.id)}"${active ? " selected" : ""}>${escapeHtml(preset.label || "MP4 Compatibility")}</option>
          </select>
          <span class="note" data-library-compatibility-note>${escapeHtml(active ? (preset.warning || preset.summary || "") : "Optional lossy MP4 reset preset.")}</span>
        </label>
      `;
    }
  
    function captureOpenOverrideSections() {
      const list = byId("settings-library-profile-list");
      if (!list) return;
      list.querySelectorAll(".settings-library-card").forEach((card) => {
        const profileId = card.dataset.libraryId || "";
        if (!profileId) return;
        const openSections = new Set();
        card.querySelectorAll("details[data-library-override-section]").forEach((section) => {
          if (section.open) {
            const sectionKey = section.getAttribute("data-library-override-section") || "";
            if (sectionKey) openSections.add(sectionKey);
          }
        });
        state.openOverrideSectionsByLibrary.set(profileId, openSections);
      });
    }
  
    function renderCard(profile) {
      const nonDeletable = profile.id === "movies" || profile.id === "tv";
      const inherited = inheritedSet(profile);
      const card = document.createElement("article");
      card.className = "settings-library-card";
      card.dataset.libraryId = profile.id;
      card.dataset.localInheritedFields = JSON.stringify(Array.from(inherited));
      card.dataset.libraryPrunedOverrides = JSON.stringify(inapplicableOverrideKeys(profile));
      card.innerHTML = `
        <div class="settings-library-card-heading">
          <div>
            <h3>${escapeHtml(profile.name)}</h3>
            <p class="note">${escapeHtml(profile.id)} / ${escapeHtml(profile.designation)}</p>
          </div>
          <div class="settings-library-card-actions">
            <label class="settings-library-enabled"><input type="checkbox" data-library-field="enabled" ${profile.enabled ? "checked" : ""} ${nonDeletable ? "disabled" : ""}> Enabled</label>
          </div>
        </div>
        <div class="form-grid form-grid-dense settings-library-main-grid">
          <label>Library ID
            <input type="text" data-library-field="id" data-library-identity readonly value="${escapeHtml(profile.id)}">
          </label>
          <label>Name
            <input type="text" data-library-field="name" value="${escapeHtml(profile.name)}" ${nonDeletable ? "readonly" : ""}>
          </label>
          <label>Designation
            <select data-library-field="designation">
              ${designationValues.map((designation) => `<option value="${designation}" ${profile.designation === designation ? "selected" : ""}>${escapeHtml(choiceValueLabel(designation))}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="settings-library-path-grid"></div>
        <div class="settings-library-overrides">
          ${overrideGroupList().map((group) => renderOverrideSection(profile, group)).join("")}
        </div>
      `;
      const pathGrid = card.querySelector(".settings-library-path-grid");
      [
        ["source_path", "Source", profile.source_path],
        ["output_path", "Output destination", profile.output_path],
        ["promotion_destination", "Promotion destination", profile.promotion_destination],
      ].forEach(([field, label, value]) => {
        const row = document.createElement("label");
        const evidence = pathEvidence(profile, field);
        const state = pathState(profile, field);
        const sourceText = pathSourceText(evidence);
        const canReset = pathCanReset(profile, field, evidence);
        const isInherited = pathIsInherited(evidence);
        row.className = "settings-library-path-row";
        row.dataset.pathPickerScope = "true";
        row.dataset.libraryPathStateKind = String(evidence?.state || "");
        row.dataset.libraryPathSourceKey = text(evidence?.source_key);
        row.innerHTML = `
          <span class="path-picker-label-row">
            <span class="path-picker-label-text">${escapeHtml(label)} <span class="settings-library-state ${pathStateClass(state)}" data-library-path-state="${field}">${escapeHtml(state)}</span><span class="note settings-library-path-source" data-library-path-source="${field}">${escapeHtml(sourceText)}</span></span>
            <button type="button" class="path-picker-badge" data-path-picker-target="${pathPickerTargetForLibraryField(field)}" data-path-picker-input='[data-library-field="${field}"]' data-path-picker-mode="folder" data-path-picker-status="settings-library-editor-status" title="Open a backend-owned Windows folder picker for ${escapeHtml(label.toLowerCase())}.">Browse</button>
          </span>
          <div class="settings-library-path-control">
            <input type="text" data-library-field="${field}" data-inherited="${isInherited ? "true" : "false"}" value="${escapeHtml(value || "")}">
            <button type="button" class="tertiary-button" data-library-use-default="${field}" data-library-can-reset="${canReset ? "true" : "false"}" title="${canReset ? "Reset to inherited removes explicit path state; it does not write the global path into this library." : "This field does not support inherited reset."}"${canReset && !isInherited ? "" : " hidden disabled"}>Use global default</button>
          </div>
        `;
        pathGrid.appendChild(row);
      });
      const promotionRow = document.createElement("label");
      promotionRow.className = "settings-library-promotion-toggle";
      promotionRow.innerHTML = `<input type="checkbox" data-library-field="promotion_enabled" ${profile.promotion_enabled ? "checked" : ""}> Enable promotion for this library`;
      pathGrid.appendChild(promotionRow);
      syncLibraryRouteReadouts(card);
      syncLibraryCompatibilityAvailability(card);
      return card;
    }
  
    function libraryEditorHasActiveControl() {
      const active = document.activeElement;
      if (!(active instanceof Element) || active === document.body) return false;
      const containers = [
        byId("settings-library-profile-list"),
        byId("settings-library-profile-nav"),
        byId("settings-library-active-title")?.closest?.(".settings-library-actions-panel"),
      ].filter(Boolean);
      if (!containers.some((container) => container.contains(active))) return false;
      return Boolean(active.closest?.("select, input, textarea"));
    }
  
    function shouldDeferAutomaticLibraryRender(options = {}) {
      return Boolean(options?.automatic === true && profileCardsFromDom().length && libraryEditorHasActiveControl());
    }
  
    function renderSettingsLibraries(settings, options = {}) {
      const incomingProfiles = currentProfilesFromSettings(settings);
      syncLibraryWatchControlsFromConfig(settings, options);
      if (shouldDeferAutomaticLibraryRender(options)) return;
      if (state.libraryEditorDirty && profileCardsFromDom().length) {
        try {
          const stagedProfiles = collectProfilesFromDom();
          if (!profilesEquivalent(stagedProfiles, incomingProfiles)) {
            state.profiles = stagedProfiles;
            setText("settings-libraries-status", `${state.profiles.length} library profile(s) staged`);
            renderActiveLibraryCommandState();
            return;
          }
          state.libraryEditorDirty = false;
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          setText("settings-libraries-status", "Unsaved libraries kept");
          setLibraryFeedback(`Unsaved library edits were kept through refresh. ${message}`);
          return;
        }
      }
      state.profiles = incomingProfiles;
      renderProfileCards();
    }
  

    return {
      choiceLabel,
      fieldHelpText,
      metadataTags,
      fieldIsAdvanced,
      choiceValueLabel,
      inputTypeForField,
      fieldOwnValue,
      buildOverrideControl,
      effectiveOverrideValue,
      settingOverrideEvidence,
      overrideValuesEqual,
      overrideStateText,
      renderUseDefaultButton,
      routeNumberValue,
      routeFormatPercent,
      routeFormatHeight,
      routeSafeIdPart,
      routeElementId,
      routeValueAvailable,
      routeValueFromBackendSource,
      routeMetadataMissingKeys,
      routeSourceSummary,
      routeValuesFromObject,
      routeBoundariesFromValues,
      routeRailPercentages,
      routeValuesFromProfile,
      routeValuesFromCard,
      effectiveLibraryOverrideValue,
      routeTriggerSummary,
      routeHeightPixelSummary,
      routeConsequenceSummary,
      routeUnknownHeightSummary,
      routeEstimatedGb,
      routeFormatEstimatedGb,
      renderLibraryRouteOverrideField,
      renderLibraryRouteRail,
      renderLibraryRouteBoundaryControls,
      renderLibraryRouteBucket,
      renderLibraryRouteSizeLayout,
      renderOverrideField,
      fieldsForGroup,
      renderFieldGrid,
      renderOptionGrid,
      renderFullFields,
      renderNestedOptionPanel,
      renderAdvancedOverrideDisclosure,
      renderOverrideLayout,
      renderOverrideSection,
      profileMp4CompatibilityActive,
      renderCompatibilityPresetEditorControl,
      captureOpenOverrideSections,
      renderCard,
      libraryEditorHasActiveControl,
      shouldDeferAutomaticLibraryRender,
      renderSettingsLibraries,
    };
  }

  window.__settingsLibrariesRenderingModule = { createSettingsLibrariesRenderingModule };
})();
