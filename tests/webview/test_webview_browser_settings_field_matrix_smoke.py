from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _get_json, _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _get_json, _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


def _browser_settings_field_matrix_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function settingsFieldMatrixScript(data) {
          return `
          (() => {
            const payload = ${JSON.stringify(data)};
            const expectedSettings = payload.settings;
            const expectedDefinitions = Array.isArray(expectedSettings.field_definitions)
              ? expectedSettings.field_definitions
              : [];
            const definitionsByKey = new Map(expectedDefinitions.map((field) => [String(field.key || ""), field]));
            const metadata = window.mediaPipelineSettingsMetadata || {};
            const byId = (id) => document.getElementById(id);
            const text = (id) => String(byId(id)?.textContent || "");
            const assert = (condition, message) => {
              if (!condition) throw new Error(message);
            };
            const markStage = (stage) => { window.__settingsFieldMatrixStage = stage; };
            const checkpoint = (stage) => { markStage(stage); };
            const waitFor = async (predicate, label, timeoutMs = 20000) => {
              const deadline = Date.now() + timeoutMs;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : ""));
            };
            const click = (id) => {
              const button = byId(id);
              assert(button, "missing button " + id);
              button.click();
            };
            const dispatchValue = (control, value) => {
              if (control.type === "checkbox") control.checked = Boolean(value);
              else control.value = String(value ?? "");
              control.dispatchEvent(new Event("input", { bubbles: true }));
              control.dispatchEvent(new Event("change", { bubbles: true }));
            };
            const setPatchJson = (value) => {
              const textarea = byId("settings-patch-json");
              assert(textarea, "missing Changes JSON textarea");
              textarea.value = typeof value === "string" ? value : JSON.stringify(value, null, 2);
              textarea.dispatchEvent(new Event("input", { bubbles: true }));
            };
            const groupSpecs = [
              ["settingsBuilderFields", "settings-builder-apply-button", "settings-builder-reset-button"],
              ["videoDetailSettingsBuilderFields", "settings-video-apply-button", "settings-video-reset-button"],
              ["qualityDetailSettingsBuilderFields", "settings-quality-apply-button", "settings-quality-reset-button"],
              ["fileSafetySettingsBuilderFields", "settings-file-safety-apply-button", "settings-file-safety-reset-button"],
              ["networkSettingsBuilderFields", "settings-network-apply-button", "settings-network-reset-button"],
              ["queueSettingsBuilderFields", "settings-queue-apply-button", "settings-queue-reset-button"],
              ["runtimeSettingsBuilderFields", "settings-runtime-apply-button", "settings-runtime-reset-button"],
              ["pendingPublishSettingsBuilderFields", "settings-pending-apply-button", "settings-pending-reset-button"],
              ["subtitleSettingsBuilderFields", "settings-subtitle-apply-button", "settings-subtitle-reset-button"],
              ["audioSettingsBuilderFields", "settings-audio-apply-button", "settings-audio-reset-button"],
            ].map(([property, applyId, resetId]) => ({ property, applyId, resetId, fields: metadata[property] || [] }));

            window.mediaPipelineSettingsView.initSettingsViewEvents();
            window.showPage("settings");
            window.mediaPipelineSettingsView.renderSettings(expectedSettings);
            checkpoint("metadata-contract");

            const expectedTabs = [
              "status", "guided-setup", "paths-safety", "routing-size", "media-output",
              "publish-recovery", "naming", "queue-runtime", "presets", "advanced-evidence",
            ];
            const actualTabs = Array.from(document.querySelectorAll('.settings-section-nav-btn[data-settings-tab]'))
              .map((button) => String(button.dataset.settingsTab || ""));
            assert(JSON.stringify(actualTabs) === JSON.stringify(expectedTabs), "Settings tab contract drift: " + JSON.stringify(actualTabs));
            expectedTabs.forEach((pane) => {
              const button = document.querySelector('.settings-section-nav-btn[data-settings-tab="' + pane + '"]');
              const paneNodes = Array.from(document.querySelectorAll('.settings-tab-pane[data-settings-tab="' + pane + '"]'));
              assert(button, "missing Settings tab button " + pane);
              assert(paneNodes.length > 0, "missing Settings pane content " + pane);
              button.click();
              assert(button.getAttribute("aria-current") === "location", "Settings tab did not activate " + pane);
              assert(paneNodes.every((node) => node.classList.contains("is-active")), "Settings pane did not activate " + pane);
            });

            assert(
              Array.isArray(metadata.finalLibraryPromotionSettingsBuilderFields)
                && metadata.finalLibraryPromotionSettingsBuilderFields.length === 0,
              "finalLibraryPromotionSettingsBuilderFields gained bindings; add an explicit field-matrix interaction owner",
            );

            const bindings = [];
            const bindingIdentities = new Set();
            const controlIds = new Set();
            const keyToGroup = new Map();
            groupSpecs.forEach((group) => {
              assert(group.fields.length > 0, "empty builder group " + group.property);
              group.fields.forEach((binding) => {
                const [key, id, fallbackKind = ""] = binding;
                const identity = String(key) + "|" + String(id);
                assert(!bindingIdentities.has(identity), "duplicate builder binding " + identity);
                assert(!controlIds.has(String(id)), "duplicate builder DOM id " + id);
                bindingIdentities.add(identity);
                controlIds.add(String(id));
                bindings.push({ key: String(key), id: String(id), fallbackKind: String(fallbackKind), group });
                if (!keyToGroup.has(String(key))) keyToGroup.set(String(key), group);
              });
            });

            const paneCounts = Object.fromEntries(expectedTabs.map((tab) => [tab, 0]));
            const externalBuilderKeys = new Set();
            const builderKeys = new Set();
            const gibBytes = 1024 ** 3;
            const displayConstraint = (field, fallbackKind, boundary) => {
              const raw = field[boundary];
              if (fallbackKind !== "bytes_gib" || String(field.unit || "").toLowerCase() !== "bytes") return String(raw);
              const gib = Number(raw) / gibBytes;
              return String(boundary === "max" ? Math.max(1, Math.floor(gib)) : Math.max(1, Math.ceil(gib)));
            };
            bindings.forEach(({ key, id, fallbackKind, group }) => {
              const field = definitionsByKey.get(key);
              const control = byId(id);
              assert(field, "builder key missing backend field definition: " + key);
              assert(control, "builder control missing: " + key + " -> " + id);
              builderKeys.add(key);
              assert(control.dataset.settingsKey === key, key + " data-settings-key mismatch");
              assert(control.dataset.settingsPersistedKey === String(field.persisted_key || key), key + " persisted key mismatch");
              assert(control.dataset.settingsValueType === String(field.value_type || field.kind || fallbackKind), key + " value type mismatch");
              assert(control.dataset.settingsUnit === String(field.unit || ""), key + " unit mismatch");
              assert(control.dataset.settingsSection === String(field.section || ""), key + " section mismatch");
              assert(control.dataset.settingsDefaultSource === String(field.default_source || ""), key + " default source mismatch");
              assert(control.dataset.settingsValidationOwner === String(field.validation_owner || ""), key + " validation owner mismatch");
              assert(control.dataset.settingsRuntimeConsumer === String(field.runtime_consumer || ""), key + " runtime consumer mismatch");
              if (field.help_text || field.help) assert(control.title.includes(String(field.help_text || field.help)), key + " help text missing");
              const pane = control.closest('.settings-tab-pane[data-settings-tab]');
              if (pane) {
                const paneId = String(pane.dataset.settingsTab || "");
                assert(Object.prototype.hasOwnProperty.call(paneCounts, paneId), key + " uses unknown Settings pane " + paneId);
                paneCounts[paneId] += 1;
              } else {
                const pageId = String(control.closest('[data-page-panel]')?.dataset.pagePanel || "");
                assert(group.property === "networkSettingsBuilderFields" && pageId === "network", key + " is outside its owned Settings/Network surface");
                externalBuilderKeys.add(key);
              }

              const allowedValues = Array.isArray(field.allowed_values) ? field.allowed_values.map(String) : [];
              if (control.tagName === "SELECT" && allowedValues.length) {
                const actualValues = Array.from(control.options).map((option) => option.value);
                allowedValues.forEach((value) => assert(actualValues.includes(value), key + " missing allowed option " + value));
              }
              const preserveRange = control.type === "range" && control.dataset.settingsPreserveRangeLimits === "true";
              if (control instanceof HTMLInputElement && control.type !== "checkbox" && !preserveRange) {
                ["min", "max", "step"].forEach((boundary) => {
                  if (field[boundary] === null || field[boundary] === undefined) return;
                  assert(control.getAttribute(boundary) === displayConstraint(field, fallbackKind, boundary), key + " " + boundary + " mismatch");
                });
              }
              const valueType = String(field.value_type || "");
              if (valueType === "boolean") assert(typeof control.checked === "boolean", key + " did not load as boolean");
              else if (["integer", "number"].includes(valueType) && control.value !== "") assert(Number.isFinite(Number(control.value)), key + " did not load as a number");
              else if (valueType === "list") assert(Array.isArray(String(control.value || "").split(",")), key + " did not load as list text");
              else if (valueType === "json" && String(control.value || "").trim()) {
                try { JSON.parse(control.value); } catch (error) { throw new Error(key + " did not load valid JSON: " + error.message); }
              }
              else assert(typeof control.value === "string", key + " did not load as string text");
            });
            expectedTabs.forEach((pane) => {
              assert(document.querySelector('.settings-tab-pane[data-settings-tab="' + pane + '"]'), "missing Settings pane " + pane);
              assert(Number.isInteger(paneCounts[pane]), "unaccounted Settings pane " + pane);
            });
            assert(
              Object.values(paneCounts).reduce((total, count) => total + count, 0) + externalBuilderKeys.size === bindings.length,
              "builder controls were omitted from Settings/Network surface accounting",
            );

            const profileOwnedKeys = expectedDefinitions
              .filter((field) => field.library_override_allowed === true && !builderKeys.has(String(field.key || "")))
              .map((field) => String(field.key || ""));
            const jsonOnlyKeys = expectedDefinitions
              .filter((field) => !builderKeys.has(String(field.key || "")) && !profileOwnedKeys.includes(String(field.key || "")))
              .map((field) => String(field.key || ""));
            assert(builderKeys.size + profileOwnedKeys.length + jsonOnlyKeys.length === expectedDefinitions.length, "field ownership classification omitted metadata keys");

            let stagedBindingCount = 0;
            const stageableBuilderKeys = new Set();
            checkpoint("builder-stage-reset");
            for (const group of groupSpecs) {
              checkpoint("builder-stage-" + group.property);
              const keys = Array.from(new Set(group.fields.map((binding) => String(binding[0]))));
              const stagedKeys = new Set();
              const stageCurrentGroup = () => {
                setPatchJson({});
                click(group.applyId);
                const staged = JSON.parse(byId("settings-patch-json").value || "{}");
                Object.keys(staged).forEach((key) => {
                  stagedKeys.add(key);
                  stageableBuilderKeys.add(key);
                });
              };
              if (group.property === "networkSettingsBuilderFields") {
                const role = byId("settings-network-role");
                assert(role, "missing Network role selector for conditional stage coverage");
                role.value = "standalone";
                stageCurrentGroup();
                role.value = "coordinator";
                stageCurrentGroup();
                role.value = "worker";
                byId("settings-network-worker-url").value = "http://127.0.0.1:7830";
                stageCurrentGroup();
              } else {
                stageCurrentGroup();
              }
              keys.forEach((key) => {
                if (stagedKeys.has(key)) return;
                const binding = group.fields.find((candidate) => String(candidate[0]) === key);
                const control = binding ? byId(String(binding[1])) : null;
                const container = control?.closest("label") || control;
                assert(container?.hidden === true, group.property + " did not stage visible key " + key);
              });
              stagedBindingCount += group.fields.length;

              const firstControl = byId(String(group.fields[0][1]));
              const beforeMalformedReset = firstControl.type === "checkbox" ? firstControl.checked : firstControl.value;
              setPatchJson("{ malformed");
              click(group.resetId);
              assert(byId("settings-patch-json").value === "{ malformed", group.property + " rewrote malformed Changes JSON");
              const afterMalformedReset = firstControl.type === "checkbox" ? firstControl.checked : firstControl.value;
              assert(afterMalformedReset === beforeMalformedReset, group.property + " reset controls after malformed JSON");
              assert(text("settings-patch-status").includes("Reset blocked"), group.property + " did not report blocked reset");

              const candidate = { MatrixUnrelatedSentinel: "keep" };
              keys.forEach((key) => {
                const field = definitionsByKey.get(key) || {};
                candidate[key] = "canonical";
                candidate[String(field.persisted_key || key).toUpperCase()] = "persisted-case";
              });
              Object.entries(metadata.settingsFriendlyPersistedKeyAliases || {}).forEach(([alias, canonical]) => {
                if (keys.includes(String(canonical))) candidate[alias] = "friendly-alias";
              });
              setPatchJson(candidate);
              click(group.resetId);
              const reset = JSON.parse(byId("settings-patch-json").value || "{}");
              assert(JSON.stringify(reset) === JSON.stringify({ MatrixUnrelatedSentinel: "keep" }), group.property + " reset pruning mismatch: " + JSON.stringify(reset));
              window.mediaPipelineSettingsView.renderSettings(expectedSettings);
            }

            const equivalenceClasses = new Set();
            checkpoint("builder-equivalence-classes");
            const representative = (predicate) => bindings.find((binding) => predicate(definitionsByKey.get(binding.key), byId(binding.id), binding));
            const exercise = (name, binding, values) => {
              assert(binding, "missing Settings equivalence class " + name);
              const control = byId(binding.id);
              values.forEach((value) => {
                dispatchValue(control, value);
                if (control.type !== "checkbox" && control.value !== "") assert(typeof control.value === "string", name + " control did not retain text value");
              });
              click(binding.group.resetId);
              equivalenceClasses.add(name);
            };
            const boolBinding = representative((field) => field?.value_type === "boolean");
            exercise("boolean", boolBinding, [!byId(boolBinding.id).checked, byId(boolBinding.id).checked]);
            const enumBinding = representative((field, control) => Array.isArray(field?.allowed_values) && field.allowed_values.length > 1 && control.tagName === "SELECT");
            exercise("enum", enumBinding, [enumBinding && definitionsByKey.get(enumBinding.key).allowed_values[0], enumBinding && definitionsByKey.get(enumBinding.key).allowed_values.at(-1)]);
            const numericBinding = representative((field, control) => ["integer", "number"].includes(String(field?.value_type || "")) && field.min !== null && field.max !== null && control.type !== "range");
            const numericField = definitionsByKey.get(numericBinding.key);
            const numericStep = Number(numericField.step || 1);
            exercise("numeric-bounds-step", numericBinding, [numericField.min, numericField.max, Math.min(Number(numericField.max), Number(numericField.min) + numericStep)]);
            exercise("list-blank-nonblank", representative((field) => field?.value_type === "list"), ["matrix-one, matrix-two", ""]);
            exercise("path-blank-nonblank", representative((field) => field?.value_type === "path"), ["C:/matrix/path", ""]);
            const isOptionalBinding = (field, binding) => (
              String(field?.kind || "").startsWith("optional_") || binding.fallbackKind.startsWith("optional_")
            );
            exercise("optional-blank-nonblank", representative((field, _control, binding) => isOptionalBinding(field, binding)), ["matrix-value", ""]);
            exercise("string-blank-nonblank", representative((field, _control, binding) => field?.value_type === "string" && !isOptionalBinding(field, binding)), ["matrix-value", ""]);
            const jsonBinding = bindings
              .filter((binding) => {
                const field = definitionsByKey.get(binding.key);
                return (field?.value_type === "json" || field?.kind === "json" || binding.fallbackKind.includes("json"))
                  && stageableBuilderKeys.has(binding.key);
              })
              .at(-1);
            exercise("json-valid-blank", jsonBinding, ['{"matrix":1}', ""]);
            setPatchJson({ MatrixUnrelatedSentinel: "keep" });
            if (jsonBinding.group.property === "networkSettingsBuilderFields") {
              byId("settings-network-role").value = "worker";
              byId("settings-network-worker-url").value = "http://127.0.0.1:7830";
            }
            dispatchValue(byId(jsonBinding.id), "{ malformed");
            click(jsonBinding.group.applyId);
            assert(text("settings-patch-status").toLowerCase().includes("invalid"), "malformed builder JSON was not rejected");
            assert(JSON.parse(byId("settings-patch-json").value).MatrixUnrelatedSentinel === "keep", "malformed JSON apply removed unrelated staged data");
            click(jsonBinding.group.resetId);
            equivalenceClasses.add("json-malformed");

            const matrixSettings = JSON.parse(JSON.stringify(expectedSettings));
            const matrixConfig = matrixSettings.config || (matrixSettings.config = {});
            const matrixProfile = {
              id: "matrix",
              name: "Matrix",
              enabled: true,
              designation: "auto",
              source_path: String(matrixConfig.SourceTV || ""),
              output_path: String(matrixConfig.Outsource || ""),
              promotion_enabled: false,
              promotion_destination: "",
              overrides: { editor: {}, video: {}, subtitles: {}, audio: {} },
            };
            matrixConfig.LibraryProfiles = [matrixProfile];
            matrixSettings.library_profile_state = [];
            const overrideDefinitions = expectedDefinitions.filter((field) => field.library_override_allowed === true);
            const nonDefaultGlobalField = overrideDefinitions.find((field) => String(field.key || "") === "VideoPreset")
              || overrideDefinitions.find((field) => Array.isArray(field.allowed_values) && field.allowed_values.length > 1);
            assert(nonDefaultGlobalField, "missing finite library override field for non-default inherited reset coverage");
            const nonDefaultGlobalValue = nonDefaultGlobalField.allowed_values
              .find((value) => JSON.stringify(value) !== JSON.stringify(nonDefaultGlobalField.default_value));
            assert(nonDefaultGlobalValue !== undefined, "missing non-default global value for " + nonDefaultGlobalField.key);
            matrixConfig[nonDefaultGlobalField.key] = nonDefaultGlobalValue;
            const coveredOverrides = new Set();
            const overrideKinds = new Set();
            let nonDefaultInheritedResetCovered = false;
            const overrideControlValue = (control, field) => {
              if (control.type === "checkbox") return Boolean(control.checked);
              if (field.value_type === "list") {
                return String(control.value || "").split(",").map((value) => value.trim()).filter(Boolean);
              }
              if (["integer", "number"].includes(String(field.value_type || ""))) {
                return String(control.value || "").trim() === "" ? "" : Number(control.value);
              }
              return String(control.value || "");
            };
            const inheritedControlValue = (field, value) => {
              if (field.value_type === "list") return Array.isArray(value) ? value.map(String) : [];
              if (["integer", "number"].includes(String(field.value_type || ""))) {
                return value === null || value === undefined || String(value).trim() === "" ? "" : Number(value);
              }
              if (field.value_type === "boolean") return Boolean(value);
              return String(value ?? "");
            };
            checkpoint("library-overrides");
            window.showPage("libraries");
            window.mediaPipelineSettingsLibraries.renderSettingsLibraries(matrixSettings);
            for (const designation of ["auto", "movies", "tv"]) {
              checkpoint("library-overrides-" + designation);
              matrixProfile.designation = designation;
              click("settings-library-reset-button");
              window.mediaPipelineSettingsLibraries.activateLibraryProfile("matrix", { source: "field-matrix" });
              assert(document.querySelector('[data-library-id="matrix"]'), "missing matrix Library Profile card for " + designation);
              const applicable = overrideDefinitions.filter((field) => {
                const designations = Array.isArray(field.library_profile_designations) ? field.library_profile_designations.map(String) : [];
                return !designations.length ? designation === "auto" : designations.includes(designation);
              });
              for (const field of applicable) {
                const key = String(field.key || "");
                if (coveredOverrides.has(key)) continue;
                checkpoint("library-override-" + key);
                const card = document.querySelector('[data-library-id="matrix"]');
                assert(card, "missing matrix Library Profile card for " + designation);
                const row = card.querySelector('[data-library-override-row][data-library-override-key="' + key + '"]');
                assert(row, "missing library override row " + key + " for " + designation);
                assert(row.dataset.libraryOverrideEligible === "true", key + " library override is not editable");
                assert(row.dataset.libraryPersistedKey === String(field.persisted_key || key), key + " library persisted-key mismatch");
                const control = row.querySelector("[data-library-override-control]");
                assert(control, "missing library override control " + key);
                const original = control.type === "checkbox" ? control.checked : control.value;
                dispatchValue(control, original);
                assert(row.dataset.libraryOverride === "false", key + " explicit-equals-inherited became an override: " + JSON.stringify({
                  kind: field.kind,
                  valueType: field.value_type,
                  original,
                  inherited: row.dataset.libraryInheritedValue,
                  persisted: row.dataset.libraryPersistedOverride,
                }));
                let alternate;
                if (control.type === "checkbox") {
                  alternate = !control.checked;
                  overrideKinds.add("boolean");
                } else if (control.tagName === "SELECT") {
                  const option = Array.from(control.options).find((item) => item.value !== control.value);
                  assert(option, key + " has no alternate select option");
                  alternate = option.value;
                  overrideKinds.add("select");
                } else if (control.type === "number") {
                  const min = control.min === "" ? 0 : Number(control.min);
                  const max = control.max === "" ? min + 1000 : Number(control.max);
                  const step = control.step === "" || control.step === "any" ? 1 : Number(control.step);
                  alternate = Number(original) === min ? Math.min(max, min + step) : min;
                  overrideKinds.add("numeric");
                } else {
                  alternate = String(original) === "matrix-value" ? "matrix-alternate" : "matrix-value";
                  overrideKinds.add(String(field.kind || field.value_type || "text"));
                }
                dispatchValue(control, alternate);
                assert(row.dataset.libraryOverride === "true", key + " did not become an explicit override");
                const resetButton = row.querySelector("[data-library-use-default-override]");
                assert(resetButton && !resetButton.disabled, key + " did not enable Reset to inherited");
                resetButton.click();
                assert(row.dataset.libraryOverride === "false", key + " did not reset to inherited");
                const inheritedValue = JSON.parse(row.dataset.libraryInheritedValue || "null");
                assert(
                  JSON.stringify(overrideControlValue(control, field)) === JSON.stringify(inheritedControlValue(field, inheritedValue)),
                  key + " reset control value did not match inherited value: " + JSON.stringify({
                    control: overrideControlValue(control, field),
                    inherited: inheritedControlValue(field, inheritedValue),
                  }),
                );
                if (key === String(nonDefaultGlobalField.key || "")) {
                  assert(
                    JSON.stringify(inheritedValue) !== JSON.stringify(nonDefaultGlobalField.default_value),
                    key + " non-default inherited reset fixture fell back to the schema default",
                  );
                  nonDefaultInheritedResetCovered = true;
                }
                coveredOverrides.add(key);
              }
            }
            const missingOverrides = overrideDefinitions.map((field) => String(field.key || "")).filter((key) => !coveredOverrides.has(key));
            assert(!missingOverrides.length, "uncovered library override fields: " + missingOverrides.join(", "));
            ["boolean", "select", "numeric"].forEach((kind) => assert(overrideKinds.has(kind), "library override type coverage missing " + kind));
            assert(nonDefaultInheritedResetCovered, "non-default inherited library reset was not covered");

            const emptyListField = overrideDefinitions.find((field) => field.value_type === "list" && (!field.library_profile_designations || !field.library_profile_designations.length));
            checkpoint("library-empty-overrides");
            assert(emptyListField, "missing global library list override for empty-state coverage");
            matrixProfile.designation = "auto";
            matrixConfig[emptyListField.key] = [];
            matrixProfile.overrides[emptyListField.override_group] = {};
            click("settings-library-reset-button");
            window.mediaPipelineSettingsLibraries.activateLibraryProfile("matrix", { source: "field-matrix-empty-inherited" });
            let emptyRow = document.querySelector('[data-library-id="matrix"] [data-library-override-key="' + emptyListField.key + '"]');
            dispatchValue(emptyRow.querySelector("[data-library-override-control]"), "matrix-value");
            dispatchValue(emptyRow.querySelector("[data-library-override-control]"), "");
            assert(emptyRow.dataset.libraryOverride === "false", "inherited empty list did not return to inheritance");
            checkpoint("library-empty-inherited-complete");
            matrixProfile.overrides[emptyListField.override_group][emptyListField.key] = [];
            click("settings-library-reset-button");
            window.mediaPipelineSettingsLibraries.activateLibraryProfile("matrix", { source: "field-matrix-empty-explicit" });
            emptyRow = document.querySelector('[data-library-id="matrix"] [data-library-override-key="' + emptyListField.key + '"]');
            assert(emptyRow.dataset.libraryOverride === "true", "persisted explicit-empty list did not render explicit");
            dispatchValue(emptyRow.querySelector("[data-library-override-control]"), "");
            assert(emptyRow.dataset.libraryOverride === "true", "persisted explicit-empty list lost explicit state");
            checkpoint("library-empty-explicit-complete");

            const debugCurrent = Boolean(expectedSettings.config?.DebugMode);
            const logField = definitionsByKey.get("ConsoleLogLevel");
            const logChoices = Array.isArray(logField?.allowed_values) ? logField.allowed_values.map(String) : [];
            const logCurrent = String(expectedSettings.config?.ConsoleLogLevel || logField?.default_value || "INFO");
            const logAlternate = logChoices.find((value) => value && value.toLowerCase() !== logCurrent.toLowerCase()) || "DEBUG";
            checkpoint("save-candidate-ready");

            window.__settingsFieldMatrixResult = {
              ok: true,
              backendFieldCount: expectedDefinitions.length,
              builderBindingCount: bindings.length,
              builderKeyCount: builderKeys.size,
              profileOwnedCount: profileOwnedKeys.length,
              jsonOnlyCount: jsonOnlyKeys.length,
              overrideFieldCount: overrideDefinitions.length,
              coveredOverrideCount: coveredOverrides.size,
              nonDefaultInheritedResetKey: String(nonDefaultGlobalField.key || ""),
              stagedBindingCount,
              panes: actualTabs,
              paneCounts,
              externalBuilderCount: externalBuilderKeys.size,
              equivalenceClasses: Array.from(equivalenceClasses).sort(),
              overrideKinds: Array.from(overrideKinds).sort(),
              saveCandidate: {
                debugExpected: !debugCurrent,
                logAlternate,
                stagedKeys: ["DebugMode", "ConsoleLogLevel"],
              },
            };
            markStage("matrix-complete");
            return true;
          })()
          `;
        }

        function runtimeEvaluationError(result, label) {
          const details = result?.exceptionDetails;
          if (!details) return null;
          const message = details.exception?.description || details.exception?.value || details.text || "browser evaluation failed";
          return new Error(`${label}: ${message}`);
        }

        async function evaluateRuntime(client, expression, label, options = {}) {
          const result = await client.send("Runtime.evaluate", {
            expression,
            awaitPromise: options.awaitPromise === true,
            returnByValue: true,
          });
          const error = runtimeEvaluationError(result, label);
          if (error) throw error;
          return result.result?.value;
        }

        async function freshRuntimeClient(currentClient, wsUrl) {
          if (currentClient) currentClient.close();
          const nextClient = createCdpClient(wsUrl);
          await nextClient.send("Runtime.enable");
          await nextClient.send("Log.enable");
          await nextClient.send("Page.enable");
          return nextClient;
        }

        async function waitForRuntimeCondition(client, expression, label, timeoutMs = 20000) {
          const deadline = Date.now() + timeoutMs;
          let lastValue;
          while (Date.now() < deadline) {
            lastValue = await evaluateRuntime(client, expression, label);
            if (lastValue === true) return;
            await sleep(100);
          }
          const diagnostic = await evaluateRuntime(client, `(() => ({
            patchStatus: String(document.getElementById("settings-patch-status")?.textContent || ""),
            settingsStatus: String(document.getElementById("settings-status")?.textContent || ""),
            detail: String(document.getElementById("settings-patch-detail")?.textContent || "").slice(0, 500),
            dialogOpen: Boolean(document.getElementById("settings-save-review-dialog")?.open),
            reloadDisabled: document.getElementById("settings-save-header-reload-button")?.disabled,
            debugMode: document.getElementById("settings-runtime-debug-mode")?.checked,
            consoleLog: String(document.getElementById("settings-runtime-console-log")?.value || ""),
            consoleOptions: Array.from(document.getElementById("settings-runtime-console-log")?.options || []).map((option) => option.value),
            loadedDebugMode: window.mediaPipelineSettingsView?.getLastSettings?.()?.config?.DebugMode,
            loadedConsoleLog: window.mediaPipelineSettingsView?.getLastSettings?.()?.config?.ConsoleLogLevel,
            loadedConsoleChoices: window.mediaPipelineSettingsView?.getLastSettings?.()?.field_definitions?.find((field) => field.key === "ConsoleLogLevel")?.allowed_values,
            commands: window.getCommandHistory?.().map((entry) => entry.command || entry.raw?.command),
          }))()`, `${label} diagnostics`).catch((error) => ({ diagnosticError: error.message }));
          throw new Error(`Timed out waiting for ${label}; last=${JSON.stringify(lastValue)} diagnostic=${JSON.stringify(diagnostic)}`);
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          const hardWatchdog = setTimeout(() => {
            try { if (!browser.killed) browser.kill(); } catch (_) {}
            console.error(`Settings field matrix hard timeout at ${String(globalThis.__settingsFieldMatrixLastStage || "startup")}`);
            process.exit(124);
          }, 110000);
          let client = null;
          let monitorClient = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            monitorClient = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await monitorClient.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.readyState === "complete" && document.getElementById("settings-patch-json") && window.mediaPipelineSettingsMetadata && typeof window.mediaPipelineSettingsView?.renderSettings === "function" && typeof window.mediaPipelineSettingsView?.initSettingsViewEvents === "function" && Array.isArray(window.mediaPipelineSettingsView?.getLastSettings?.()?.field_definitions) && typeof window.mediaPipelineSettingsLibraries?.renderSettingsLibraries === "function" && typeof window.getCommandHistory === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const finalReady = await evaluateRuntime(
              client,
              `Boolean(document.readyState === "complete" && document.getElementById("settings-patch-json") && window.mediaPipelineSettingsMetadata && typeof window.mediaPipelineSettingsView?.renderSettings === "function" && typeof window.mediaPipelineSettingsView?.initSettingsViewEvents === "function" && Array.isArray(window.mediaPipelineSettingsView?.getLastSettings?.()?.field_definitions) && typeof window.mediaPipelineSettingsLibraries?.renderSettingsLibraries === "function" && typeof window.getCommandHistory === "function")`,
              "Settings field matrix readiness",
            );
            if (finalReady !== true) throw new Error("Settings field matrix WebView globals or DOM nodes did not become ready.");
            let evaluationSettled = false;
            let lastStage = "startup";
            let resolveMatrixCompleted;
            const matrixCompleted = new Promise((resolve) => { resolveMatrixCompleted = resolve; });
            const monitor = (async () => {
              while (!evaluationSettled) {
                const probe = monitorClient.send("Runtime.evaluate", {
                  expression: `String(window.__settingsFieldMatrixStage || "startup")`,
                  returnByValue: true,
                }).catch(() => null);
                const observed = await Promise.race([probe, sleep(1000).then(() => null)]);
                if (observed?.result?.value) {
                  lastStage = String(observed.result.value);
                  globalThis.__settingsFieldMatrixLastStage = lastStage;
                  fs.writeFileSync(`${payload.tmpRoot.replace(/\\/g, "/")}/settings-field-matrix-stage.txt`, lastStage, "utf8");
                  if (lastStage === "matrix-complete") resolveMatrixCompleted(true);
                }
                await sleep(100);
              }
            })();
            const evaluation = client.send("Runtime.evaluate", {
              expression: settingsFieldMatrixScript({ settings: payload.settings }),
              awaitPromise: false,
              returnByValue: true,
            });
            const outcome = await Promise.race([
              evaluation.then((result) => ({ result })).catch((transportError) => ({ transportError })),
              matrixCompleted.then(() => ({ completedInPage: true })),
              sleep(90000).then(() => ({ timeout: true })),
            ]);
            evaluationSettled = true;
            await monitor;
            if (outcome.completedInPage) {
              const stalledClient = client;
              const completedMonitorClient = monitorClient;
              monitorClient = null;
              stalledClient.close();
              completedMonitorClient.close();
              client = createCdpClient(wsUrl);
              await client.send("Runtime.enable");
              await client.send("Log.enable");
              await client.send("Page.enable");
            } else {
              monitorClient.close();
              monitorClient = null;
            }
            if (outcome.timeout) {
              throw new Error("Settings field matrix timed out at " + lastStage);
            }
            if (outcome.transportError && !outcome.completedInPage) throw outcome.transportError;
            if (outcome.result) {
              const evaluationError = runtimeEvaluationError(outcome.result, "Settings field matrix");
              if (evaluationError) throw new Error(evaluationError.message + "\nBrowser events: " + client.exceptions.concat(client.consoleEvents).join("; "));
              if (outcome.result.result?.value !== true) throw new Error("Settings field matrix did not return completion evidence");
            }
            globalThis.__settingsFieldMatrixLastStage = "matrix-evidence-read";
            const browserResultJson = await evaluateRuntime(
              client,
              `JSON.stringify(window.__settingsFieldMatrixResult || null)`,
              "read Settings field matrix evidence",
            );
            const browserResult = JSON.parse(browserResultJson || "null") || {};
            globalThis.__settingsFieldMatrixLastStage = "matrix-evidence-read-complete";

            globalThis.__settingsFieldMatrixLastStage = "save-candidate-stage";
            await evaluateRuntime(client, `(() => {
              window.showPage("settings");
              window.__settingsFieldMatrixAlerts = [];
              window.__settingsFieldMatrixOriginalAlert = window.alert;
              window.alert = (message) => { window.__settingsFieldMatrixAlerts.push(String(message || "")); };
              const textarea = document.getElementById("settings-patch-json");
              if (!textarea) throw new Error("missing Changes JSON textarea");
              textarea.value = JSON.stringify({
                DebugMode: ${JSON.stringify(Boolean(browserResult.saveCandidate?.debugExpected))},
                ConsoleLogLevel: ${JSON.stringify(String(browserResult.saveCandidate?.logAlternate || ""))},
              }, null, 2);
              return true;
            })()`, "stage final Settings save candidate");
            globalThis.__settingsFieldMatrixLastStage = "save-review-open";
            await evaluateRuntime(client, `(() => {
              const button = document.getElementById("settings-save-patch-button");
              if (!button) throw new Error("missing Settings save button");
              button.click();
              return true;
            })()`, "open Settings save review");
            await waitForRuntimeCondition(
              client,
              `Boolean(document.getElementById("settings-save-review-dialog")?.open)`,
              "Settings save review dialog",
            );
            globalThis.__settingsFieldMatrixLastStage = "save-review-evidence";
            const reviewEvidence = await evaluateRuntime(client, `(() => ({
              submittedCount: Number(document.getElementById("settings-save-review-dialog-submitted")?.textContent || 0),
              submittedKeys: Object.keys(JSON.parse(document.getElementById("settings-patch-json")?.value || "{}")),
            }))()`, "Settings save review evidence");
            await evaluateRuntime(client, `(() => {
              const button = document.getElementById("settings-save-review-confirm-button");
              if (!button) throw new Error("missing Settings save confirmation button");
              button.click();
              return true;
            })()`, "confirm Settings save");
            client = await freshRuntimeClient(client, wsUrl);
            globalThis.__settingsFieldMatrixLastStage = "save-confirmed-wait";
            await waitForRuntimeCondition(
              client,
              `(() => {
                const history = window.getCommandHistory();
                const saveCount = history.filter((entry) => (entry.command || entry.raw?.command) === "settings.save_patch").length;
                return saveCount >= 1
                  && document.getElementById("settings-save-header-reload-button")?.disabled === false
                  && !document.getElementById("settings-save-review-dialog")?.open;
              })()`,
              "confirmed Settings save",
            );
            globalThis.__settingsFieldMatrixLastStage = "save-reload-click";
            await evaluateRuntime(client, `(() => {
              const button = document.getElementById("settings-save-header-reload-button");
              if (!button || button.disabled) throw new Error("Settings Reload From Disk button is not ready");
              button.click();
              return true;
            })()`, "click Settings Reload From Disk");
            client = await freshRuntimeClient(client, wsUrl);
            await waitForRuntimeCondition(
              client,
              `(() => {
                const history = window.getCommandHistory();
                const reloadCount = history.filter((entry) => (entry.command || entry.raw?.command) === "settings.reload").length;
                return reloadCount >= 1
                  && document.getElementById("settings-save-header-reload-button")?.disabled === false
                  && document.getElementById("settings-runtime-debug-mode")?.checked === ${JSON.stringify(Boolean(browserResult.saveCandidate?.debugExpected))}
                  && String(document.getElementById("settings-runtime-console-log")?.value || "") === ${JSON.stringify(String(browserResult.saveCandidate?.logAlternate || ""))};
              })()`,
              "saved Settings after Reload From Disk",
            );
            globalThis.__settingsFieldMatrixLastStage = "save-reload-complete";
            const reloadedEnum = await evaluateRuntime(
              client,
              `String(document.getElementById("settings-runtime-console-log")?.value || "")`,
              "saved enum after reload",
            );
            if (reloadedEnum !== browserResult.saveCandidate?.logAlternate) {
              throw new Error(`saved enum did not reload: ${JSON.stringify(reloadedEnum)}`);
            }
            const commandCounts = await evaluateRuntime(client, `(() => {
              const history = window.getCommandHistory();
              return {
                saveCount: history.filter((entry) => (entry.command || entry.raw?.command) === "settings.save_patch").length,
                reloadCount: history.filter((entry) => (entry.command || entry.raw?.command) === "settings.reload").length,
                alerts: Array.isArray(window.__settingsFieldMatrixAlerts) ? window.__settingsFieldMatrixAlerts.slice() : [],
              };
            })()`, "Settings command journal evidence");
            Object.assign(browserResult, reviewEvidence, commandCounts);
            if (browserResult.saveCount !== 1) throw new Error(`expected one Settings save command, found ${browserResult.saveCount}`);
            if (browserResult.reloadCount < 1) throw new Error("expected Settings reload command evidence");
            await evaluateRuntime(client, `(() => {
              if (typeof window.__settingsFieldMatrixOriginalAlert === "function") window.alert = window.__settingsFieldMatrixOriginalAlert;
              delete window.__settingsFieldMatrixOriginalAlert;
              return true;
            })()`, "restore Settings alert handler");

            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: browserResult }));
          } finally {
            clearTimeout(hardWatchdog);
            if (client) client.close();
            if (monitorClient) monitorClient.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_settings_field_matrix_smoke(
    *, browser_path: str, url: str, settings: dict[str, object]
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed Settings field matrix smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "browser-settings-field-matrix-payload.json"
        runner_path = tmp / "browser-settings-field-matrix-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": free_port(),
                    "tmpRoot": str(tmp),
                    "url": url,
                    "settings": settings,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_settings_field_matrix_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed Settings field matrix smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=120,
        )


class WebViewBrowserSettingsFieldMatrixSmoke(unittest.TestCase):
    def test_metadata_derived_builder_override_and_save_reload_matrix(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Settings field matrix smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            resolved.config_data.update(
                {
                    "SourceMovies": str(root / "Movies"),
                    "SourceTV": str(root / "TV"),
                    "Outsource": str(root / "Outsource"),
                    "LocalBase": str(root),
                    "DebugMode": False,
                    "ConsoleLogLevel": "INFO",
                }
            )
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            resolved.config_path.write_text(service.serialize_psd1_document(resolved.config_data), encoding="utf-8")

            def reload_resolved() -> object:
                if service.saved_config_calls:
                    saved_values = service.saved_config_calls[-1].get("config_values")
                    if isinstance(saved_values, dict):
                        resolved.config_data = dict(saved_values)
                return resolved

            facade = MediaPipelineApplicationFacade(service, app_version="v6-settings-field-matrix")
            server = LocalApiServer(
                facade,
                token="browser-settings-field-matrix-token",
                resolved_provider=lambda: resolved,
                resolved_reload=reload_resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                status, settings = _get_json(f"{server.url}/api/settings/workspace", token=server.token)
                self.assertEqual(status, 200)
                result = _run_browser_settings_field_matrix_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    settings=settings,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        expected_field_count = len(settings["field_definitions"])
        expected_override_count = sum(
            1 for field in settings["field_definitions"] if field.get("library_override_allowed") is True
        )
        self.assertEqual(browser_result["backendFieldCount"], expected_field_count)
        self.assertEqual(expected_field_count, 204)
        self.assertEqual(browser_result["builderBindingCount"], 155)
        self.assertEqual(browser_result["builderKeyCount"], 145)
        self.assertEqual(browser_result["profileOwnedCount"], 0)
        self.assertEqual(browser_result["jsonOnlyCount"], 59)
        self.assertEqual(
            browser_result["builderKeyCount"]
            + browser_result["profileOwnedCount"]
            + browser_result["jsonOnlyCount"],
            expected_field_count,
        )
        self.assertEqual(browser_result["overrideFieldCount"], expected_override_count)
        self.assertEqual(browser_result["coveredOverrideCount"], expected_override_count)
        self.assertEqual(browser_result["stagedBindingCount"], browser_result["builderBindingCount"])
        self.assertEqual(len(browser_result["panes"]), 10)
        self.assertGreater(browser_result["externalBuilderCount"], 0)
        self.assertEqual(
            set(browser_result["equivalenceClasses"]),
            {
                "boolean",
                "enum",
                "json-malformed",
                "json-valid-blank",
                "list-blank-nonblank",
                "numeric-bounds-step",
                "optional-blank-nonblank",
                "path-blank-nonblank",
                "string-blank-nonblank",
            },
        )
        self.assertEqual(browser_result["saveCount"], 1)
        self.assertGreaterEqual(browser_result["reloadCount"], 1)
        expected_submitted_keys = {
            "DebugMode",
            "ConsoleLogLevel",
            "RenameMovieFilterTerms",
            "RenameTVFilterTerms",
            "RenameMovieFilterOptions",
            "RenameTVFilterOptions",
            "RenameMovieRemoveTerms",
            "RenameTVRemoveTerms",
        }
        self.assertEqual(browser_result["submittedCount"], len(expected_submitted_keys))
        self.assertEqual(set(browser_result["submittedKeys"]), expected_submitted_keys)
        self.assertEqual(
            set(browser_result["saveCandidate"]["stagedKeys"]),
            {"DebugMode", "ConsoleLogLevel"},
        )
        for alert_text in browser_result["alerts"]:
            self.assertIn("Settings runtime note", alert_text)
        self.assertEqual(len(service.saved_config_calls), 1)


if __name__ == "__main__":
    unittest.main()
