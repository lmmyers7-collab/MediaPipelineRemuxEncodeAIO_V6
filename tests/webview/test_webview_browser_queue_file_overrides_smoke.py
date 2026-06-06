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
    from .test_webview_real_media_smoke import _write_fixture_state
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
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_queue_file_overrides_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function queueFileOverridesScript() {
          return `
          (async () => {
            const originalApiGet = window.apiGet;
            const originalApiPost = window.apiPost;
            const originalConfirm = window.confirm;
            const previousRefreshAllForQueueOverrideSmoke = window.refreshAll;
            const posts = [];
            const confirms = [];
            const sourcePath = "C:/Smoke/Example Show/Season 01/Queue Drawer Sample S01E01.mkv";
            let savedEntry = null;
            let failNextOverridePost = false;
            const confirmResponses = [false, true, true];
            window.__queueOverrideMarkerCalls = [];

            function clone(value) {
              return JSON.parse(JSON.stringify(value));
            }
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function statusTone() { return byId("fo-drawer-status")?.dataset.tone || ""; }
            function statusRole() { return byId("fo-drawer-status")?.getAttribute("role") || ""; }
            function overrideChipState() { return document.querySelector(".queue-override-chip")?.dataset.state || ""; }
            function overrideChipText() { return document.querySelector(".queue-override-chip")?.textContent || ""; }
            function saveDisabled() { return Boolean(byId("fo-drawer-save")?.disabled); }
            function drawerHidden() { return Boolean(byId("fo-drawer")?.hidden); }
            function overlayHidden() { return Boolean(byId("fo-overlay")?.hidden); }
            function seriesModalHidden() { return Boolean(byId("fo-series-modal")?.hidden); }
            function require(condition, message) {
              if (!condition) throw new Error(message);
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function setControlValue(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing control " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 12000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error(
                "Timed out waiting for " + label
                + (lastError ? ": " + lastError.message : "")
                + "\\nStatus:\\n" + text("fo-drawer-status")
                + "\\nOverride chip:\\n" + overrideChipState() + " " + overrideChipText()
                + "\\nMarker calls:\\n" + JSON.stringify(window.__queueOverrideMarkerCalls || [])
                + "\\nQueue rows:\\n" + (document.querySelector("#queue-rows")?.innerHTML || "")
                + "\\nPosts:\\n" + JSON.stringify(posts)
              );
            }
            function applyClearFields(entry, fields) {
              if (!entry) return null;
              const next = clone(entry);
              for (const field of fields || []) {
                const parts = String(field || "").split(".");
                if (parts.length !== 2) continue;
                const section = next[parts[0]];
                if (section && typeof section === "object") {
                  delete section[parts[1]];
                  if (!Object.keys(section).length) delete next[parts[0]];
                }
              }
              return Object.keys(next).length ? next : null;
            }
            function mergeOverride(entry, override) {
              const next = entry ? clone(entry) : {};
              for (const [section, value] of Object.entries(override || {})) {
                if (section === "path") continue;
                next[section] = clone(value);
              }
              return next;
            }
            function effectiveField(fieldKey, value, source, choices = []) {
              const field = {
                effective: { available: true, display: String(value), value, source },
                inherited: { available: true, display: "saved policy", value: "saved policy", source: "global_default" },
              };
              if (choices.length) {
                field.choices = choices;
                field.effective.choices = choices;
              }
              return field;
            }
            function routeVideoProcessing() {
              const profile = String(savedEntry?.routing?.profile || "").toLowerCase();
              if (profile === "transcode" || profile === "encode") {
                return {
                  route: "transcode",
                  videoCodec: "h264_nvenc",
                  will_force_transcode: true,
                  warnings: ["Effective route/video override may force a full video transcode during processing."],
                };
              }
              return { route: "remux", videoCodec: "copy", will_force_transcode: false, warnings: [] };
            }
            function effectivePayload() {
              const sources = {};
              if (savedEntry?.audio?.keepTracks) sources["audio.keepTracks"] = "file_override";
              if (savedEntry?.audio?.maxChannels) sources["audio.maxChannels"] = "file_override";
              if (savedEntry?.audio?.preferDefaultLanguage) sources["audio.preferDefaultLanguage"] = "file_override";
              if (Object.prototype.hasOwnProperty.call(savedEntry?.subtitles || {}, "stripAll")) sources["subtitles.stripAll"] = "file_override";
              if (savedEntry?.routing?.profile) sources["routing.profile"] = "file_override";
              return {
                ok: true,
                file_override_scope: savedEntry ? "file" : "none",
                file_override: savedEntry ? clone(savedEntry) : null,
                sources,
                inherited: {
                  audioKeepLanguages: { available: true, display: "eng", value: ["eng"], source: "global_default" },
                  audioMaxChannels: { available: true, display: "2", value: 2, source: "global_default" },
                  audioPreferDefaultLanguage: { available: true, display: "eng", value: "eng", source: "global_default" },
                  subtitleStripAll: { available: true, display: "disabled", value: false, source: "global_default" },
                },
                expanded_effective_fields: {
                  audioKeepLanguages: effectiveField("audioKeepLanguages", "eng", sources["audio.keepTracks"] || "global_default"),
                  audioMaxChannels: effectiveField("audioMaxChannels", savedEntry?.audio?.maxChannels || 2, sources["audio.maxChannels"] || "global_default"),
                  audioPreferDefaultLanguage: effectiveField("audioPreferDefaultLanguage", savedEntry?.audio?.preferDefaultLanguage || "eng", sources["audio.preferDefaultLanguage"] || "global_default"),
                  subtitleStripAll: effectiveField("subtitleStripAll", savedEntry?.subtitles?.stripAll ? "enabled" : "disabled", sources["subtitles.stripAll"] || "global_default"),
                },
                route_video_effective_fields: {
                  routeProfile: effectiveField("routeProfile", savedEntry?.routing?.profile || "plex_direct_stream", sources["routing.profile"] || "global_default", [
                    { value: "plex_direct_stream", label: "Plex direct stream" },
                    { value: "remux", label: "Remux" },
                    { value: "transcode", label: "Transcode" },
                  ]),
                  routingRouteThresholdMode: effectiveField("routingRouteThresholdMode", savedEntry?.routing?.routeThresholdMode || "compatibility_advisory", sources["routing.routeThresholdMode"] || "global_default", [
                    { value: "compatibility_advisory", label: "Compatibility advisory" },
                    { value: "bitrate", label: "Bitrate" },
                    { value: "size_or_bitrate", label: "Size or bitrate" },
                  ]),
                },
                route_video_processing: routeVideoProcessing(),
                track_metadata: {
                  available: true,
                  probe_available: true,
                  probe_source: "smoke_fixture",
                  source_info: { available: false, probe_source: "smoke_fixture" },
                  audio_tracks: [],
                  subtitle_tracks: [],
                  warnings: [],
                },
                track_selection_preview: {},
              };
            }

            window.apiGet = async (path, options) => {
              const rawPath = String(path || "");
              if (rawPath === "/api/queue" || rawPath.startsWith("/api/queue?")) return fixtureQueuePayload();
              if (rawPath.startsWith("/api/queue/file-overrides/effective")) return effectivePayload();
              if (rawPath.startsWith("/api/queue/file-overrides/tracks")) {
                return {
                  ok: true,
                  probe_available: true,
                  probe_source: "smoke_fixture",
                  source_info: { available: false, probe_source: "smoke_fixture" },
                  audio_tracks: [],
                  subtitle_tracks: [],
                  warnings: [],
                };
              }
              if (rawPath.startsWith("/api/queue/file-overrides?")) {
                return { ok: true, entry: savedEntry ? clone(savedEntry) : null };
              }
              return originalApiGet(path, options);
            };
            window.apiPost = async (path, body, options) => {
              const rawPath = String(path || "");
              const payload = clone(body || {});
              posts.push({ path: rawPath, body: payload });
              if (rawPath === "/api/queue/file-overrides") {
                if (failNextOverridePost) {
                  failNextOverridePost = false;
                  return { ok: false, message: "Injected file override save failure." };
                }
                if (payload.clear === true) {
                  savedEntry = null;
                  return { ok: true, command: "queue.file_overrides", message: "Override cleared." };
                }
                if (Array.isArray(payload.clear_fields)) {
                  savedEntry = applyClearFields(savedEntry, payload.clear_fields);
                  return { ok: true, command: "queue.file_overrides", message: "Override field cleared." };
                }
                savedEntry = mergeOverride(savedEntry, payload);
                return { ok: true, command: "queue.file_overrides", message: "Override saved." };
              }
              if (rawPath === "/api/queue/file-overrides/route-preview") {
                const proposedRoute = String(payload.proposed_override?.routing?.forceRoute || "").toLowerCase();
                if (proposedRoute === "transcode" || proposedRoute === "encode") {
                  return {
                    ok: true,
                    current: { route: "remux" },
                    proposed: { route: "transcode", videoCodec: "h264_nvenc" },
                    impact: {
                      estimated_risk: "high",
                      requires_confirmation: true,
                      will_force_transcode: true,
                      will_prevent_remux: true,
                    },
                    warnings: [{ message: "This route preview would force a full video transcode for this file." }],
                  };
                }
                return {
                  ok: true,
                  current: { route: "remux" },
                  proposed: { route: "remux", videoCodec: "copy" },
                  impact: { estimated_risk: "low", requires_confirmation: false, will_force_transcode: false },
                  warnings: [],
                };
              }
              if (rawPath === "/api/queue/file-overrides/series-preview") {
                return {
                  ok: true,
                  command: "queue.file_overrides.series_preview",
                  schema_version: "queue_file_override_series_preview.v1",
                  message: "Series override preview ready: 2 rows will update; 1 manual row protected.",
                  detected: {
                    show_name: "Example Show",
                    show_root: "C:/Smoke/Example Show",
                    confidence: "high",
                  },
                  proposed_fields: ["audio.maxChannels", "subtitles.stripAll"],
                  counts: {
                    total_rows: 3,
                    will_update: 2,
                    replace_prior_batch: 0,
                    protected_manual: 1,
                    skipped: 0,
                    issue: 0,
                    eligible_update_count: 2,
                  },
                  rows: [
                    {
                      action: "will_update",
                      display_name: "Queue Drawer Sample S01E01.mkv",
                      relative_path: "Example Show/Season 01/Queue Drawer Sample S01E01.mkv",
                      source_path: sourcePath,
                      season_number: 1,
                      episode_number: 1,
                      reason: "Current queue row matches the detected series root.",
                    },
                    {
                      action: "will_update",
                      display_name: "Queue Drawer Sample S01E02.mkv",
                      relative_path: "Example Show/Season 01/Queue Drawer Sample S01E02.mkv",
                      source_path: "C:/Smoke/Example Show/Season 01/Queue Drawer Sample S01E02.mkv",
                      season_number: 1,
                      episode_number: 2,
                      reason: "Current queue row matches the detected series root.",
                    },
                    {
                      action: "protected_manual",
                      display_name: "Queue Drawer Sample S01E03.mkv",
                      relative_path: "Example Show/Season 01/Queue Drawer Sample S01E03.mkv",
                      source_path: "C:/Smoke/Example Show/Season 01/Queue Drawer Sample S01E03.mkv",
                      season_number: 1,
                      episode_number: 3,
                      reason: "Exact manual file override is protected.",
                    },
                  ],
                  warnings: [],
                  blockers: [],
                  preview_fingerprint: "series-preview-fingerprint",
                };
              }
              if (rawPath === "/api/queue/file-overrides/series-apply") {
                require(payload.confirm_apply === true, "series apply did not include confirm_apply=true");
                require(payload.preview_fingerprint === "series-preview-fingerprint", "series apply fingerprint mismatch");
                return {
                  ok: true,
                  command: "queue.file_overrides.series_apply",
                  message: "Series override applied to 2 current queue rows; 1 manual row protected.",
                  batch: { batch_id: "series-smoke" },
                };
              }
              return originalApiPost(path, body, options);
            };
            window.confirm = (message) => {
              confirms.push(String(message || ""));
              return confirmResponses.length ? confirmResponses.shift() : true;
            };

            function fixtureQueuePayload() {
              return {
                ok: true,
                count: 1,
                rows: [{
                  row_key: "queue-drawer-sample",
                  global_order: 1,
                  queue_index: 1,
                  queue_total: 1,
                  media_type: "tv",
                  media_kind: "tv",
                  display_name: "Queue Drawer Sample S01E01.mkv",
                  relative_path: "Example Show/Season 01/Queue Drawer Sample S01E01.mkv",
                  source_path: sourcePath,
                  source_root: "C:/Smoke",
                  root_path: "C:/Smoke",
                  season_number: 1,
                  episode_number: 1,
                  route_name: "remux",
                  route_reason: "drawer smoke fixture",
                  operator_status: "ready for launch",
                  operator_trust_state: "ready",
                  proof_summary: ["drawer smoke row"],
                  has_file_override: false,
                }],
                source_roots: ["C:/Smoke"],
                snapshot_exists: true,
                produced_at: "2026-06-04T00:00:00Z",
              };
            }
            function renderFixtureQueue() {
              window.renderQueue(fixtureQueuePayload());
            }
            window.refreshAll = async () => {
              renderFixtureQueue();
            };

            await waitFor(
              () => document.readyState === "complete"
                && typeof window.renderQueue === "function"
                && document.querySelector("#queue-rows")
                && document.querySelector("#fo-drawer-save"),
              "Queue globals and drawer DOM",
            );
            const markerFn = window.mediaPipelineQueueView?.applyDisplayedQueueFileOverrideMarker;
            require(typeof markerFn === "function", "Queue marker update helper is not exported.");
            window.mediaPipelineQueueView.applyDisplayedQueueFileOverrideMarker = (path, hasOverride) => {
              window.__queueOverrideMarkerCalls.push({ path, hasOverride });
              return markerFn(path, hasOverride);
            };

            renderFixtureQueue();
            const openButton = document.querySelector(".fo-open-btn");
            require(openButton, "missing Queue file settings button");
            require(overrideChipState() === "none", "Override chip should start inactive.");
            require(overrideChipText() === "", "Inactive override chip should not show marker text.");
            openButton.click();
            await waitFor(() => !drawerHidden() && text("fo-drawer-status").includes("No override set"), "drawer empty override load");
            require(!byId("fo-route-risk-confirm"), "Old route-impact confirmation checkbox should not render.");
            require(saveDisabled(), "Save should be disabled while the empty loaded form is clean.");

            setControlValue("fo-audio-keep-langs", "eng");
            setControlValue("fo-audio-max-channels", "6");
            await waitFor(() => !saveDisabled() && text("fo-drawer-status").includes("Unsaved changes"), "dirty state before first override save");
            byId("fo-drawer-save").click();
            await waitFor(() => text("fo-drawer-status").includes("Override saved."), "first override save status");
            await waitFor(() => overrideChipState() === "active" && overrideChipText().includes("Override"), "visible override marker after save");
            require(document.querySelector(".fo-open-btn")?.dataset.hasOverride === "true", "File settings button should show override state after save.");
            require(saveDisabled(), "Save should be disabled again after first successful save.");
            require(statusTone() === "success", "Save status should use success tone, got " + statusTone());
            require(statusRole() === "status", "Save status should use status role, got " + statusRole());

            setControlValue("fo-audio-max-channels", "");
            await waitFor(() => !saveDisabled() && text("fo-drawer-status").includes("Unsaved changes"), "dirty state after neutral max channels");
            require(statusTone() === "warning", "Dirty status should use warning tone, got " + statusTone());
            byId("fo-drawer-save").click();
            await waitFor(() => text("fo-drawer-status").includes("Override saved."), "save status after clear_fields");
            await waitFor(() => overrideChipState() === "active", "visible override marker remains after partial clear");
            require(saveDisabled(), "Save should be disabled again after successful save.");
            require(statusTone() === "success", "Save status should use success tone, got " + statusTone());
            const clearFieldPost = posts.find((entry) => Array.isArray(entry.body.clear_fields));
            require(clearFieldPost, "Save did not submit clear_fields for a neutral saved field.");
            require(clearFieldPost.body.clear_fields.includes("audio.maxChannels"), "clear_fields did not include audio.maxChannels: " + JSON.stringify(clearFieldPost));

            byId("fo-series-preview-open").click();
            await waitFor(() => !seriesModalHidden() && text("fo-series-summary").includes("Series override preview ready"), "series preview modal");
            require(drawerHidden(), "Series preview should hide the file override drawer.");
            require(overlayHidden(), "Series preview should hide the drawer backdrop.");
            requireText("fo-series-detected", ["Example Show", "C:/Smoke/Example Show", "high"]);
            requireText("fo-series-counts", ["Will update: 2", "Protected: 1"]);
            requireText("fo-series-rows", ["Queue Drawer Sample S01E01.mkv", "Queue Drawer Sample S01E03.mkv", "Protected"]);
            byId("fo-series-cancel").click();
            await waitFor(() => seriesModalHidden(), "series preview cancel close");
            require(!drawerHidden(), "Cancel should restore the file override drawer.");
            require(!overlayHidden(), "Cancel should restore the drawer backdrop.");
            require(!posts.some((entry) => entry.path === "/api/queue/file-overrides/series-apply"), "Cancel should not post series apply.");

            byId("fo-series-preview-open").click();
            await waitFor(() => !seriesModalHidden() && !byId("fo-series-apply").disabled, "series preview apply enabled");
            byId("fo-series-apply").click();
            await waitFor(() => seriesModalHidden() && drawerHidden() && overlayHidden(), "series apply closes drawer and modal");
            const seriesApplyPosts = posts.filter((entry) => entry.path === "/api/queue/file-overrides/series-apply");
            require(seriesApplyPosts.length === 1, "Series apply should post exactly once: " + JSON.stringify(seriesApplyPosts));

            const reopenButton = document.querySelector(".fo-open-btn");
            require(reopenButton, "missing Queue file settings button after series apply");
            reopenButton.click();
            await waitFor(() => !drawerHidden() && text("fo-drawer-status").includes("Override loaded."), "drawer reload after series apply");

            setControlValue("fo-audio-prefer-default-language", "jpn");
            await waitFor(() => !saveDisabled(), "dirty state before close guard");
            byId("fo-overlay").click();
            require(!drawerHidden(), "Overlay close should be cancelled when discard is rejected.");
            requireText("fo-drawer-status", ["Unsaved changes kept."]);
            byId("fo-overlay").click();
            await waitFor(() => drawerHidden(), "drawer closes after discard confirmation");

            const clearOpenButton = document.querySelector(".fo-open-btn");
            require(clearOpenButton, "missing Queue file settings button before full clear");
            clearOpenButton.click();
            await waitFor(() => !drawerHidden() && text("fo-drawer-status").includes("Override loaded."), "drawer reload before full clear");
            byId("fo-drawer-clear").click();
            await waitFor(() => text("fo-drawer-status").includes("Override cleared."), "full clear status");
            await waitFor(() => overrideChipState() === "none" && overrideChipText() === "", "visible override marker cleared");
            require(statusTone() === "success", "Full clear status should use success tone, got " + statusTone());
            const fullClearPost = posts.find((entry) => entry.body.clear === true);
            require(fullClearPost, "Clear Override did not submit clear=true.");

            setControlValue("fo-route-profile", "transcode");
            await waitFor(() => text("fo-route-encode-advisory").includes("Force encode:"), "forced encode footer advisory");
            const confirmsBeforeRouteSave = confirms.length;
            byId("fo-drawer-save").click();
            await waitFor(() => text("fo-drawer-status").includes("Override saved."), "route override save without confirmation checkbox");
            require(confirms.length === confirmsBeforeRouteSave, "Route override save should not ask for confirmation; confirms=" + JSON.stringify(confirms));
            requireText("fo-route-encode-advisory", ["Force encode:", "full video encode/transcode"]);
            const routePost = posts.find((entry) => entry.path === "/api/queue/file-overrides" && entry.body.routing?.profile === "transcode");
            require(routePost, "Forced encode route override was not saved: " + JSON.stringify(posts));

            setControlValue("fo-audio-max-channels", "2");
            await waitFor(() => !saveDisabled(), "dirty state before injected save failure");
            failNextOverridePost = true;
            byId("fo-drawer-save").click();
            await waitFor(() => statusRole() === "alert" && text("fo-drawer-status").includes("Error:"), "error status after failed save");
            require(statusTone() === "error", "Failed save should use error tone, got " + statusTone());
            require(statusRole() === "alert", "Failed save should use alert role, got " + statusRole());

            window.apiGet = originalApiGet;
            window.apiPost = originalApiPost;
            window.confirm = originalConfirm;
            window.refreshAll = previousRefreshAllForQueueOverrideSmoke;
            return {
              ok: true,
              posts,
              confirms,
              routeAdvisory: text("fo-route-encode-advisory"),
              status: text("fo-drawer-status"),
              statusTone: statusTone(),
              statusRole: statusRole(),
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
                expression: `Boolean(document.getElementById("queue-rows") && document.getElementById("fo-drawer") && typeof window.renderQueue === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("queue-rows") && document.getElementById("fo-drawer") && typeof window.renderQueue === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Queue drawer DOM or globals did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: queueFileOverridesScript(),
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


def _run_browser_queue_file_overrides_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView Queue file-overrides smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-queue-file-overrides-payload.json"
        runner_path = tmp / "browser-queue-file-overrides-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_queue_file_overrides_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Queue file-overrides drawer smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=45,
        )


class WebViewBrowserQueueFileOverridesSmoke(unittest.TestCase):
    def test_real_browser_exercises_queue_file_override_drawer_feedback_without_media_mutation(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView Queue file-overrides smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-queue-file-overrides-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_queue_file_overrides_smoke(browser_path=browser_path, url=f"{server.url}/")
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        posts = browser_result["posts"]
        self.assertTrue(result["ok"])
        self.assertTrue(any(post["body"].get("clear_fields") == ["audio.maxChannels"] for post in posts))
        self.assertTrue(any(post["body"].get("clear") is True for post in posts))
        self.assertTrue(any(post["body"].get("routing", {}).get("profile") == "transcode" for post in posts))
        self.assertIn("Force encode:", browser_result["routeAdvisory"])
        self.assertGreaterEqual(len(browser_result["confirms"]), 3)
        self.assertIn("Discard unsaved file override changes", browser_result["confirms"][0])
        self.assertIn("Clear all saved file override fields", browser_result["confirms"][-1])
        self.assertEqual(browser_result["statusTone"], "error")
        self.assertEqual(browser_result["statusRole"], "alert")
        self.assertIn("Error:", browser_result["status"])


if __name__ == "__main__":
    unittest.main()
