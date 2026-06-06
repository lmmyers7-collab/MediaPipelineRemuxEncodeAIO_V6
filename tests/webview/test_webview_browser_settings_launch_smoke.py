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
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _get_json, _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_settings_launch_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function settingsLaunchScript(data) {
          return `
          (async () => {
            const payload = ${JSON.stringify(data)};
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 10000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\nState:\\n" + [
                "patchStatus=" + text("settings-patch-status"),
                "saveReadiness=" + text("settings-save-readiness-status"),
                "backendResult=" + text("settings-backend-result-status"),
                "launchIntent=" + text("launch-settings-intent-status"),
                "patchDetail=" + text("settings-patch-detail"),
              ].join("\\n"));
            }
            function setTextarea(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing textarea " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function setInput(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function click(id) {
              const node = byId(id);
              if (!node) throw new Error("missing button " + id);
              node.click();
            }
            function clickSettingsTab(tabId) {
              const button = document.querySelector('.settings-tab-btn[data-settings-tab="' + tabId + '"]');
              if (!button) throw new Error("missing settings tab " + tabId);
              button.click();
            }
            function requireDefaultVisibleAssSsaCheckboxes() {
              clickSettingsTab("media-output");
              for (const id of [
                "settings-subtitle-drop-ass",
                "settings-subtitle-remove-karaoke",
                "settings-subtitle-strip-formatting",
                "settings-subtitle-merge-adjacent",
                "settings-subtitle-keep-signs",
                "settings-subtitle-ass-signs-forced",
              ]) {
                const node = byId(id);
                if (!node) throw new Error("missing ASS/SSA checkbox " + id);
                const row = node.closest("label") || node;
                if (row.hidden || node.hidden) throw new Error(id + " is hidden in the default Subtitles view");
                if (row.classList.contains("settings-advanced-field")) throw new Error(id + " is still classified as an advanced field");
                if (row.dataset.settingsAdvancedControl === "true" || node.dataset.settingsAdvancedControl === "true") {
                  throw new Error(id + " is still behind the advanced controls toggle");
                }
                const style = window.getComputedStyle(row);
                if (style.display === "none" || style.visibility === "hidden") {
                  throw new Error(id + " is not visible in the default Subtitles view");
                }
              }
              clickSettingsTab("status");
            }
            function requireLibraryProfileDesignationFiltering() {
              function libraryCard(id) {
                const card = document.querySelector('[data-library-id="' + id + '"]');
                if (!card) throw new Error("missing library card " + id);
                return card;
              }
              function overrideRow(card, key) {
                return card.querySelector('[data-library-override-key="' + key + '"]');
              }
              function requireRow(card, key) {
                const row = overrideRow(card, key);
                if (!row) throw new Error("missing override row " + key + " in " + (card.dataset.libraryId || "library"));
                return row;
              }
              function setLibraryDesignation(card, value) {
                const select = card.querySelector('[data-library-field="designation"]');
                if (!select) throw new Error("missing designation select for " + (card.dataset.libraryId || "library"));
                select.value = value;
                select.dispatchEvent(new Event("change", { bubbles: true }));
              }
              function setOverrideValue(row, value) {
                const control = row.querySelector("[data-library-override-control]");
                if (!control) throw new Error("missing override control for " + row.getAttribute("data-library-override-key"));
                control.value = value;
                control.dispatchEvent(new Event("input", { bubbles: true }));
                control.dispatchEvent(new Event("change", { bubbles: true }));
              }
              function requireFocusedLibrarySelectSurvivesAutomaticRefresh(card) {
                const select = card.querySelector('[data-library-field="designation"]');
                if (!select) throw new Error("missing designation select for refresh focus guard");
                select.focus({ preventScroll: true });
                if (document.activeElement !== select) throw new Error("designation select did not receive focus");
                window.mediaPipelineSettingsLibraries.renderSettingsLibraries(payload.settings, { automatic: true });
                const refreshedSelect = libraryCard(card.dataset.libraryId || "tv").querySelector('[data-library-field="designation"]');
                if (refreshedSelect !== select) {
                  throw new Error("automatic refresh replaced focused Library dropdown");
                }
                select.blur();
                window.mediaPipelineSettingsLibraries.renderSettingsLibraries(payload.settings, { automatic: true });
                const afterBlurSelect = libraryCard(card.dataset.libraryId || "tv").querySelector('[data-library-field="designation"]');
                if (afterBlurSelect === select) {
                  throw new Error("automatic Library refresh stayed deferred after dropdown blur");
                }
              }

              window.showPage("libraries");
              if (typeof window.mediaPipelineSettingsLibraries?.renderSettingsLibraries !== "function") {
                throw new Error("missing Library Profiles renderer");
              }
              window.mediaPipelineSettingsLibraries.renderSettingsLibraries(payload.settings);
              const movieCard = libraryCard("movies");
              requireFocusedLibrarySelectSurvivesAutomaticRefresh(movieCard);
              let tvCard = libraryCard("tv");
              if (overrideRow(tvCard, "MovieRoute1080pTargetSizeGB")) throw new Error("TV profile rendered Movie 1080p target output size");
              if (overrideRow(tvCard, "MovieRoute1440pTargetSizeGB")) throw new Error("TV profile rendered Movie 1440p target output size");
              if (overrideRow(tvCard, "MovieRoute4KTargetSizeGB")) throw new Error("TV profile rendered Movie 4K target output size");
              if (overrideRow(movieCard, "TVRoute1080pTargetSizeGB")) throw new Error("Movie profile rendered TV 1080p target output size");
              if (overrideRow(movieCard, "TVRoute1440pTargetSizeGB")) throw new Error("Movie profile rendered TV 1440p target output size");
              if (overrideRow(movieCard, "TVRoute4KTargetSizeGB")) throw new Error("Movie profile rendered TV 4K target output size");

              const directCopyRow = requireRow(tvCard, "Route1080pMaxVideoBitrateMbps");
              const directCopyControl = directCopyRow.querySelector("[data-library-override-control]");
              if (!directCopyControl || String(directCopyControl.value || "").trim() === "") {
                throw new Error("Inherited direct-copy value did not render for TV profile");
              }
              if (directCopyRow.dataset.libraryOverride !== "false") {
                throw new Error("Inherited direct-copy value rendered as a library override");
              }

              setLibraryDesignation(tvCard, "auto");
              tvCard = libraryCard("tv");
              const autoMovie1080pRow = requireRow(tvCard, "MovieRoute1080pTargetSizeGB");
              requireRow(tvCard, "TVRoute1080pTargetSizeGB");
              setOverrideValue(autoMovie1080pRow, "9");
              if (autoMovie1080pRow.dataset.libraryOverride !== "true") {
                throw new Error("Edited movie 1080p target did not become an explicit override while TV profile was Auto");
              }

              setLibraryDesignation(tvCard, "tv");
              tvCard = libraryCard("tv");
              if (overrideRow(tvCard, "MovieRoute1080pTargetSizeGB")) {
                throw new Error("TV profile kept Movie 1080p target visible after switching back from Auto");
              }
              const patch = window.mediaPipelineSettingsLibraries.buildPatchFromLibraries();
              const tvProfile = patch && Array.isArray(patch.LibraryProfiles)
                ? patch.LibraryProfiles.find((profile) => profile.id === "tv")
                : null;
              const tvEditorOverrides = tvProfile && tvProfile.overrides ? tvProfile.overrides.editor || {} : {};
              if (Object.prototype.hasOwnProperty.call(tvEditorOverrides, "MovieRoute1080pTargetSizeGB")) {
                throw new Error("TV LibraryProfiles patch kept hidden Movie 1080p override");
              }
              const warning = text("settings-library-warning-summary");
              if (!warning.includes("omitted designation-specific override")) {
                throw new Error("missing designation-prune warning after staging TV LibraryProfiles patch: " + warning);
              }
              window.showPage("settings");
            }
            function historyHasPreview() {
              const entries = typeof window.getCommandHistory === "function" ? window.getCommandHistory() : [];
              return entries.some((entry) => {
                const raw = entry.raw || {};
                return entry.command === "settings.preview_patch" || raw.command === "settings.preview_patch";
              });
            }
            [
              "showPage",
              "renderSettings",
              "renderSettingsPatchSummary",
              "settingsRawActionPlanRows",
              "renderSettingsRawActionPlan",
              "externalDependencyRows",
              "markSettingsPatchTouched",
              "settingsPatchHasUnsavedChanges",
              "settingsBackendResultDetailLines",
              "settingsCommandProgressBars",
              "renderSettingsSaveProgress",
              "renderQueue",
              "renderQueueRows",
              "renderAllLaunchPreflights",
              "getCommandHistory",
            ].forEach(requireFunction);

            window.renderQueue({
              ok: true,
              rows: [
                {
                  row_key: "launch-visible-ready",
                  display_name: "Launch Visible Ready",
                  source_path: "C:/Source/Launch Visible Ready.mkv",
                  route_name: "remux",
                  operator_status: "ready",
                  operator_trust_state: "ready",
                },
                {
                  row_key: "launch-hidden-blocked",
                  display_name: "Launch Hidden Blocked",
                  source_path: "C:/Source/Launch Hidden Blocked.mkv",
                  route_name: "encode",
                  operator_status: "blocked",
                  operator_trust_state: "blocked",
                  blocked_reason_code: "tv_parse_unreliable",
                  blocked_reason: "Episode/season parse was ambiguous.",
                  review_flags: ["blocked:tv_parse_unreliable"],
                },
              ],
            });
            setInput("queue-filter", "Launch Visible Ready");
            window.mediaPipelineQueueView.renderQueueRows();

            window.renderSettings(payload.settings);
            window.showPage("settings");
            requireDefaultVisibleAssSsaCheckboxes();
            requireLibraryProfileDesignationFiltering();
            requireText("settings-raw-action-plan-summary", [
              "Settings raw-key action plan:",
              "Purpose: separate schema drift, OCR path evidence, subtitle keyword builder coverage, intentionally excluded auth secrets",
              "Mutation guardrail",
            ]);
            requireText("settings-raw-action-plan-rows", [
              "BDPGS OCR path evidence",
              "Network auth secrets",
              "Mutation boundary",
            ]);
            const rawActionRows = Array.from(document.querySelectorAll("#settings-raw-action-plan-rows tr"));
            const bdpgsRawActionRow = rawActionRows.find((row) => row.textContent.includes("BDPGS OCR path evidence"));
            if (!bdpgsRawActionRow) throw new Error("missing BDPGS raw-key action-plan row");
            bdpgsRawActionRow.click();
            requireText("settings-raw-action-plan-detail", [
              "Area: BDPGS OCR path evidence",
              "Path policy: WebView can stage configured path text, but backend Preview/Save and saved path evidence remain authoritative",
              "WebView does not browse arbitrary paths or resolve paths",
              "backend-owned and allowlisted",
              "Mutation guardrail",
            ]);
            const secretRawActionRow = rawActionRows.find((row) => row.textContent.includes("Network auth secrets"));
            if (!secretRawActionRow) throw new Error("missing network secrets raw-key action-plan row");
            secretRawActionRow.click();
            requireText("settings-raw-action-plan-detail", [
              "Area: Network auth secrets",
              "Do not add WebView token editors",
              "Backend settings workspace redacts token values",
              "Network lifecycle controls remain read-only",
            ]);
            const dependencyRows = window.externalDependencyRows({ settings: payload.settings });
            const rawDependency = dependencyRows.find((row) => row.area === "Settings raw-key action plan");
            if (!rawDependency) throw new Error("missing Settings raw-key action-plan external dependency row");
            if (!String(rawDependency.evidence || "").includes("schema=") || !String(rawDependency.nextStep || "").includes("Raw-key action plan")) {
              throw new Error("raw-key action-plan dependency row did not carry schema/next-step evidence: " + JSON.stringify(rawDependency));
            }
            setTextarea("settings-patch-json", JSON.stringify(payload.patch, null, 2));
            window.mediaPipelineSettingsView.markSettingsPatchTouched();
            window.mediaPipelineSettingsView.renderSettingsPatchSummary();
            window.mediaPipelineLaunchView.renderAllLaunchPreflights();

            requireText("settings-patch-summary-status", ["7 staged keys", "7 changed", "Backend preview remains the source of truth"]);
            requireText("settings-save-readiness", ["Local save readiness checklist:", "Required operator action: use Preview Patch before Save Patch", "Mutation guardrail"]);
            requireText("settings-policy-delta-summary", ["Staged media-policy delta", "Mutation guardrail"]);
            requireText("settings-effective-policy-summary", ["Effective policy trust summary:", "Launch-active policy is the saved backend config", "WebView builder values and Changes JSON are candidates only"]);
            const stagedPolicyTrustRow = Array.from(document.querySelectorAll("#settings-effective-policy-rows tr"))
              .find((row) => row.textContent.includes("Staged WebView patch activity"));
            if (!stagedPolicyTrustRow) throw new Error("missing staged WebView patch activity effective-policy row");
            stagedPolicyTrustRow.click();
            requireText("settings-effective-policy-detail", ["Checkpoint: Staged WebView patch activity", "Effective changes: 7", "Run backend Preview Patch", "Mutation guardrail"]);
            requireText("settings-launch-impact-summary", ["Settings-to-launch handoff:", "Launch uses saved backend settings, not unsaved Changes JSON"]);
            requireText("settings-backend-result-summary", ["Backend preview/save handoff:", "Preview: missing", "Save: not saved"]);
            requireText("settings-backend-result-detail", ["Backend preview/save result detail:", "Signal: Backend preview", "Patch identity:", "Evidence matches current JSON: no"]);

            window.showPage("launch");
            window.mediaPipelineLaunchView.renderAllLaunchPreflights();
            requireText("launch-settings-risk-detail", [
              "Launch Risk Handoff detail:",
              "Proof chain:",
              "Mutation guardrail",
            ]);
            const sizeRiskRow = Array.from(document.querySelectorAll("#launch-settings-risk-rows tr"))
              .find((row) => row.textContent.includes("Remux / encode size posture"));
            if (!sizeRiskRow) throw new Error("missing remux/encode size launch risk row");
            sizeRiskRow.click();
            requireText("launch-settings-risk-detail", [
              "Area: Remux / encode size posture",
              "Proof source: saved routing profile",
              "Operator proof: compare Completed source/output size evidence",
              "Boundary: this is not a media-policy change",
              "Daily-driver rule:",
            ]);
            requireText("launch-policy-boundary-summary", [
              "Launch active media-policy boundary:",
              "Launch uses the active saved subtitle, audio, and pending-publish/source-safety policy",
              "Staged candidates are not launch-active until backend Save Patch succeeds",
              "Mutation guardrail",
            ]);
            requireText("launch-policy-boundary-detail", [
              "Launch active media-policy boundary:",
              "Area: Staged subtitle candidate",
              "Launch state: blocked",
              "Not launch-active until backend Preview Patch, Save Patch, and settings reload/refresh succeed.",
            ]);
            const audioBoundaryRow = Array.from(document.querySelectorAll("#launch-policy-boundary-rows tr"))
              .find((row) => row.textContent.includes("Staged audio candidate"));
            if (!audioBoundaryRow) throw new Error("missing staged audio candidate launch policy boundary row");
            audioBoundaryRow.click();
            requireText("launch-policy-boundary-detail", [
              "Area: Staged audio candidate",
              "Launch state: review",
              "downmix=stereo",
              "Launch will continue using the active saved audio policy above until the staged candidate is saved and reloaded.",
            ]);
            const publishBoundaryRow = Array.from(document.querySelectorAll("#launch-policy-boundary-rows tr"))
              .find((row) => row.textContent.includes("Staged publish/source candidate"));
            if (!publishBoundaryRow) throw new Error("missing staged publish/source candidate launch policy boundary row");
            publishBoundaryRow.click();
            requireText("launch-policy-boundary-detail", [
              "Area: Staged publish/source candidate",
              "Launch state: review",
              "cleanup remote=on",
              "Source deletion must remain explicit",
            ]);
            requireText("launch-settings-intent-summary", ["Staged Settings patch", "unsaved effective change(s)", "Save Patch must succeed"]);
            requireText("launch-settings-intent-summary", ["Launch uses saved backend settings", "staged Settings JSON does not count"]);
            requireText("launch-settings-intent-summary", ["Queue display scope", "Do not treat the visible Queue table as launch scope"]);
            const queueScopeIntentRow = Array.from(document.querySelectorAll("#launch-settings-intent-rows tr"))
              .find((row) => row.textContent.includes("Queue display scope"));
            if (!queueScopeIntentRow) throw new Error("missing queue display scope launch-intent row");
            queueScopeIntentRow.click();
            requireText("launch-settings-intent-detail", [
              "Queue display filter / backend launch scope",
              "hidden blocked rows: 1",
              "hidden review rows: 1",
              "Backend launch scope: unchanged",
            ]);
            const stagedSettingsIntentRow = Array.from(document.querySelectorAll("#launch-settings-intent-rows tr"))
              .find((row) => row.textContent.includes("Staged Settings patch"));
            if (!stagedSettingsIntentRow) throw new Error("missing staged settings launch-intent row");
            stagedSettingsIntentRow.click();
            requireText("launch-settings-intent-detail", ["Launch active policy boundary:", "First launch policy boundary row:"]);

            window.showPage("settings");
            click("settings-preview-patch-button");
            await waitFor(
              () => text("settings-patch-status").includes("Preview ready") && historyHasPreview(),
              "backend preview command evidence",
            );
            requireText("settings-patch-detail", ["Writes config: no", "Changed keys:", "RoutingProfile", "SizeGuardMode"]);
            requireText("settings-save-progress-bars", ["Settings save/reload", "20%", "Previewed 7 changed key(s)", "source: settings.preview_patch"]);
            requireText("settings-backend-result-summary", ["Preview: fresh preview", "Save: not saved"]);
            requireText("settings-backend-result-summary", ["Preview Patch is non-writing", "Launch uses saved backend settings only"]);
            requireText("settings-backend-result-detail", ["Signal: Backend preview", "Command result:", "OK: yes", "Writes config: no", "Risk summary:", "Settings save/reload progress:"]);
            requireText("settings-effective-policy-summary", ["Effective policy trust summary:", "previewed=", "Backend Preview Patch is non-writing"]);
            const riskRow = Array.from(document.querySelectorAll("#settings-backend-result-rows tr"))
              .find((row) => row.textContent.includes("Preview risk output"));
            if (!riskRow) throw new Error("missing backend result preview-risk row");
            riskRow.click();
            requireText("settings-backend-result-detail", ["Signal: Preview risk output", "Redacted diff lines:", "Changed keys:", "Evidence matches current JSON: yes"]);

            const historyBeforeCancel = window.getCommandHistory();
            const originalConfirm = window.confirm;
            let saveConfirmCount = 0;
            let saveConfirmMessage = "";
            window.confirm = (message) => {
              saveConfirmCount += 1;
              saveConfirmMessage = String(message || "");
              return false;
            };
            try {
              click("settings-save-patch-button");
              await new Promise((resolve) => setTimeout(resolve, 150));
            } finally {
              window.confirm = originalConfirm;
            }
            if (saveConfirmCount !== 1) throw new Error("expected exactly one Save Patch confirmation prompt; got " + saveConfirmCount);
            if (!saveConfirmMessage.includes("Save 7 setting patch key(s) to the active PSD1 config?")) {
              throw new Error("Save Patch confirmation did not include the staged-key count. Actual:\\n" + saveConfirmMessage);
            }
            if (!saveConfirmMessage.includes("A matching backend Preview Patch result is available for this staged JSON.")) {
              throw new Error("Save Patch confirmation did not mention matching preview evidence. Actual:\\n" + saveConfirmMessage);
            }
            requireText("settings-patch-status", ["Save cancelled"]);
            requireText("settings-patch-detail", ["Save Patch was cancelled before any backend save command was sent.", "No config backup was created", "no PSD1 file was written", "staged Changes JSON remains unsaved"]);
            requireText("settings-backend-result-detail", ["Signal: Save confirmation boundary", "The WebView sends Save Patch only after browser confirmation", "Mutation guardrail"]);

            window.showPage("launch");
            window.mediaPipelineLaunchView.renderAllLaunchPreflights();
            requireText("launch-policy-boundary-summary", ["Launch active media-policy boundary:", "Rows needing attention before launch:"]);
            requireText("launch-settings-intent-summary", ["Staged Settings patch", "unsaved effective change(s)", "Save Patch must succeed"]);
            requireText("launch-settings-intent-summary", ["Recent command evidence", "saved backend settings"]);

            const history = window.getCommandHistory();
            if (history.length !== historyBeforeCancel.length) {
              throw new Error("cancelled Save Patch changed command history length from " + historyBeforeCancel.length + " to " + history.length);
            }
            if (history.some((entry) => entry.command === "settings.save_patch" || entry.raw?.command === "settings.save_patch")) {
              throw new Error("settings save command was unexpectedly invoked by the browser smoke");
            }

            return {
              ok: true,
              patchStatus: text("settings-patch-status"),
              effectivePolicyStatus: text("settings-effective-policy-status"),
              effectivePolicyDetail: text("settings-effective-policy-detail"),
              backendResult: text("settings-backend-result-status"),
              launchIntent: text("launch-settings-intent-status"),
              launchRiskDetail: text("launch-settings-risk-detail"),
              policyBoundaryStatus: text("launch-policy-boundary-status"),
              policyBoundarySummary: text("launch-policy-boundary-summary"),
              policyBoundaryDetail: text("launch-policy-boundary-detail"),
              saveConfirmCount,
              saveConfirmMessage,
              commandHistoryCount: history.length,
              commandHistory: history.map((entry) => entry.command || entry.raw?.command || ""),
            };
          })()
          `;
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
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.readyState === "complete" && document.getElementById("settings-patch-json") && document.getElementById("launch-settings-intent-summary") && typeof window.renderSettings === "function" && typeof window.externalDependencyRows === "function" && typeof window.markSettingsPatchTouched === "function" && typeof window.getCommandHistory === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.readyState === "complete" && document.getElementById("settings-patch-json") && document.getElementById("launch-settings-intent-summary") && typeof window.renderSettings === "function" && typeof window.externalDependencyRows === "function" && typeof window.markSettingsPatchTouched === "function" && typeof window.getCommandHistory === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Settings/Launch WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: settingsLaunchScript({ settings: payload.settings, patch: payload.patch }),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(750);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_settings_launch_smoke(
    *,
    browser_path: str,
    url: str,
    settings: dict[str, object],
    patch: dict[str, object],
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView settings/launch smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-settings-launch-payload.json"
        runner_path = tmp / "browser-settings-launch-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "settings": settings,
                    "patch": patch,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_settings_launch_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView settings/launch smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserSettingsLaunchSmoke(unittest.TestCase):
    def test_real_browser_hands_staged_settings_patch_to_launch_without_saving(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView settings/launch smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-settings-launch-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            patch = {
                "RoutingProfile": "plex_direct_play",
                "SizeGuardMode": "strict",
                "OutputContainer": "mp4",
                "AudioDownmixMode": "stereo",
                "CleanupRemoteStaging": True,
                "ConvertTx3gToSrt": False,
                "DropTx3gAfterConversion": True,
            }
            try:
                server.start()
                settings_status, settings = _get_json(f"{server.url}/api/settings/workspace", token=server.token)
                self.assertEqual(settings_status, 200)
                result = _run_browser_settings_launch_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    settings=settings,
                    patch=patch,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        self.assertEqual(browser_result["patchStatus"], "Save cancelled")
        self.assertEqual(browser_result["effectivePolicyStatus"], "Blocked review")
        self.assertIn("Staged WebView patch activity", browser_result["effectivePolicyDetail"])
        self.assertEqual(browser_result["backendResult"], "Review")
        self.assertIn(browser_result["launchIntent"], {"Blocked", "Review", "High review"})
        self.assertEqual(browser_result["policyBoundaryStatus"], "Blocked staged policy")
        self.assertIn("Launch Risk Handoff detail:", browser_result["launchRiskDetail"])
        self.assertIn("Remux / encode size posture", browser_result["launchRiskDetail"])
        self.assertIn("Launch active media-policy boundary:", browser_result["policyBoundarySummary"])
        self.assertIn("Staged publish/source candidate", browser_result["policyBoundaryDetail"])
        self.assertIn("settings.preview_patch", browser_result["commandHistory"])
        self.assertNotIn("settings.save_patch", browser_result["commandHistory"])
        self.assertEqual(browser_result["saveConfirmCount"], 1)
        self.assertIn("A matching backend Preview Patch result is available", browser_result["saveConfirmMessage"])




