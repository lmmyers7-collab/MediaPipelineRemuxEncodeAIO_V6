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


def _browser_schedule_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function scheduleScript() {
          return `
          (async () => {
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
              const deadline = Date.now() + 15000;
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
                "scheduleStatus=" + text("schedule-status"),
                "editorStatus=" + text("schedule-editor-status"),
                "editorResult=" + text("schedule-editor-result"),
                "launchTimingStatus=" + text("launch-timing-status"),
                "launchTiming=" + text("launch-timing"),
              ].join("\\n"));
            }
            function setCheckbox(id, checked) {
              const node = byId(id);
              if (!node) throw new Error("missing checkbox " + id);
              node.checked = Boolean(checked);
              node.dispatchEvent(new Event("change", { bubbles: true }));
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
            function commandHistory(command) {
              const entries = typeof window.getCommandHistory === "function" ? window.getCommandHistory() : [];
              return entries.filter((entry) => entry.command === command || entry.raw?.command === command);
            }
            [
              "showPage",
              "renderSchedule",
              "scheduleEditorRequest",
              "scheduleSetDayBlocks",
              "previewScheduleEditor",
              "saveScheduleEditor",
              "renderAllLaunchPreflights",
              "getCommandHistory",
            ].forEach(requireFunction);

            const today = new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(new Date());
            const todayInputId = "schedule-editor-" + today.toLowerCase() + "-windows";

            window.showPage("schedule");
            await waitFor(
              () => Boolean(byId(todayInputId)) && text("schedule-editor-result").includes("No schedule preview"),
              "schedule editor initial render",
            );
            const editHeading = Array.from(document.querySelectorAll('[data-page-panel="schedule"] h2')).map((node) => node.textContent || "");
            if (editHeading.indexOf("Edit Schedule") < 0 || editHeading.indexOf("Current Schedule") < 0 || editHeading.indexOf("Edit Schedule") > editHeading.indexOf("Current Schedule")) {
              throw new Error("Edit Schedule is not the first Schedule panel: " + JSON.stringify(editHeading));
            }
            requireText("schedule-coverage-detail", ["Use Schedule Editor for backend-owned preview/save"]);
            requireText("schedule-editor-result", ["No schedule preview or save result loaded", "Backend validation owns time parsing"]);
            requireText("schedule-editor-impact", ["Launch impact:", "Preview the draft before saving schedule changes"]);
            requireText("schedule-editor-save-state", ["Preview required before save"]);
            if (!byId("schedule-editor-save-button").disabled) {
              throw new Error("Save Schedule should be disabled before backend preview.");
            }
            requireText("schedule-guidance", ["Backend continuous watcher: idle"]);
            requireText("schedule-coverage-rows", ["Continuous watcher"]);

            const originalConfirm = window.confirm;
            let bulkConfirmCount = 0;
            window.confirm = () => {
              bulkConfirmCount += 1;
              return true;
            };
            try {
              click("schedule-editor-clear-button");
            } finally {
              window.confirm = originalConfirm;
            }
            if (bulkConfirmCount !== 1) throw new Error("expected one bulk Schedule confirmation; got " + bulkConfirmCount);
            setCheckbox("schedule-editor-enabled", true);
            click("schedule-editor-" + today.toLowerCase() + "-block-18");
            click("schedule-editor-" + today.toLowerCase() + "-block-19");
            let draft = window.mediaPipelineScheduleView.scheduleEditorRequest();
            if (draft.day_windows[today] !== "09:00 - 10:00") {
              throw new Error("schedule block editor did not stage a 30-minute range: " + JSON.stringify(draft.day_windows));
            }
            if (!byId("schedule-editor-" + today.toLowerCase() + "-copy-day")) {
              throw new Error("schedule editor did not render Copy Day for " + today);
            }
            if (!byId("schedule-editor-" + today.toLowerCase() + "-paste-day").disabled) {
              throw new Error("Paste Day should be disabled before a day is copied.");
            }
            click("schedule-editor-" + today.toLowerCase() + "-copy-day");
            if (byId("schedule-editor-" + today.toLowerCase() + "-paste-day").disabled) {
              throw new Error("Paste Day should be enabled after copying " + today);
            }
            click("schedule-editor-" + today.toLowerCase() + "-paste-day");
            draft = window.mediaPipelineScheduleView.scheduleEditorRequest();
            if (draft.day_windows[today] !== "09:00 - 10:00") {
              throw new Error("Paste Day changed the copied day unexpectedly: " + JSON.stringify(draft.day_windows));
            }
            requireText("schedule-editor-status", ["Pasted " + today + " into " + today]);
            click("schedule-editor-" + today.toLowerCase() + "-allow-day");
            draft = window.mediaPipelineScheduleView.scheduleEditorRequest();
            if (!draft.enabled) throw new Error("schedule editor did not stage enabled=true");
            if (draft.day_windows[today] !== "all day") {
              throw new Error("schedule editor did not stage today as all day: " + JSON.stringify(draft.day_windows));
            }

            click("schedule-editor-preview-button");
            await waitFor(
              () => text("schedule-editor-result").includes("Command: schedule.preview") && commandHistory("schedule.preview").length >= 1,
              "schedule preview command result",
            );
            if (byId("schedule-editor-save-button").disabled) {
              throw new Error("Save Schedule should be enabled after successful backend preview.");
            }
            requireText("schedule-editor-save-state", ["Preview accepted", "Save Schedule is available"]);
            requireText("schedule-editor-result", [
              "Command: schedule.preview",
              "Writes app state: no",
              "Changed day(s): " + today,
              today + " is allowed all day.",
              "Mutation guardrail",
            ]);
            click("schedule-editor-" + today.toLowerCase() + "-block-0");
            if (!byId("schedule-editor-save-button").disabled) {
              throw new Error("Save Schedule should be disabled after changing a previewed draft.");
            }
            requireText("schedule-editor-save-state", ["Draft changed", "Preview required"]);
            click("schedule-editor-" + today.toLowerCase() + "-block-0");
            click("schedule-editor-preview-button");
            await waitFor(
              () => commandHistory("schedule.preview").length >= 2 && !byId("schedule-editor-save-button").disabled,
              "second schedule preview command result",
            );

            let confirmCount = 0;
            let confirmMessage = "";
            window.confirm = (message) => {
              confirmCount += 1;
              confirmMessage = String(message || "");
              return true;
            };
            try {
              click("schedule-editor-save-button");
              await waitFor(
                () => text("schedule-editor-result").includes("Command: schedule.save") && commandHistory("schedule.save").length >= 1,
                "schedule save command result",
              );
            } finally {
              window.confirm = originalConfirm;
            }
            if (confirmCount !== 1) throw new Error("expected one Schedule save confirmation; got " + confirmCount);
            if (!confirmMessage.includes("writes schedule_enabled and schedule_grid")) {
              throw new Error("Schedule save confirmation did not describe app-state keys. Actual:\\n" + confirmMessage);
            }
            requireText("schedule-editor-result", [
              "Command: schedule.save",
              "Writes app state: yes",
              "Enabled candidate: yes",
              "Changed day(s): " + today,
            ]);

            window.showPage("launch");
            setInput("pipeline-start-mode", "once");
            setInput("pipeline-start-schedule-override", "");
            window.mediaPipelineLaunchView.renderAllLaunchPreflights();
            await waitFor(
              () => text("launch-timing").includes("Schedule enforcement: on") && text("launch-timing").includes("Allowed now: yes"),
              "launch timing trust after schedule save refresh",
            );
            requireText("launch-timing", [
              "Launch timing trust:",
              "Selected pipeline mode: Run Once",
              "Schedule enforcement: on",
              "Allowed now: yes",
              "Backend continuous watcher: idle",
              "Run Once is inside the current window",
              "Mutation guardrail",
            ]);

            const history = window.getCommandHistory();
            const preview = commandHistory("schedule.preview")[0] || {};
            const save = commandHistory("schedule.save")[0] || {};
            return {
              ok: true,
              today,
              editorStatus: text("schedule-editor-status"),
              editorResult: text("schedule-editor-result"),
              launchTimingStatus: text("launch-timing-status"),
              launchTiming: text("launch-timing"),
              confirmCount,
              confirmMessage,
              commandHistory: history.map((entry) => entry.command || entry.raw?.command || ""),
              schedulePreviewOwner: typeof window.commandHistoryOwnerPage === "function" ? window.commandHistoryOwnerPage(preview) : "",
              scheduleSaveOwner: typeof window.commandHistoryOwnerPage === "function" ? window.commandHistoryOwnerPage(save) : "",
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
                expression: `Boolean(document.getElementById("schedule-editor-rows") && document.getElementById("launch-timing") && typeof window.mediaPipelineScheduleView.previewScheduleEditor === "function" && typeof window.mediaPipelineScheduleView.saveScheduleEditor === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("schedule-editor-rows") && document.getElementById("launch-timing") && typeof window.mediaPipelineScheduleView.previewScheduleEditor === "function" && typeof window.mediaPipelineScheduleView.saveScheduleEditor === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Schedule/Launch WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: scheduleScript(),
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


def _run_browser_schedule_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView schedule smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-schedule-payload.json"
        runner_path = tmp / "browser-schedule-runner.cjs"
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
        runner_path.write_text(_browser_schedule_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView schedule smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserScheduleSmoke(unittest.TestCase):
    def test_real_browser_saves_schedule_through_backend_and_updates_launch_timing(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView schedule smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": False, "machine_id": "browser-schedule-node"})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-schedule-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                schedule_status, schedule = _get_json(f"{server.url}/api/schedule", token=server.token)
                self.assertEqual(schedule_status, 200)
                self.assertFalse(schedule["enabled"])
                result = _run_browser_schedule_smoke(browser_path=browser_path, url=f"{server.url}/")
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

            state = service.load_app_state()

        browser_result = result["result"]
        today = str(browser_result["today"])
        self.assertEqual(browser_result["confirmCount"], 1)
        self.assertIn("schedule_enabled and schedule_grid", browser_result["confirmMessage"])
        self.assertIn("schedule.preview", browser_result["commandHistory"])
        self.assertIn("schedule.save", browser_result["commandHistory"])
        self.assertEqual(browser_result["schedulePreviewOwner"], "Schedule")
        self.assertEqual(browser_result["scheduleSaveOwner"], "Schedule")
        self.assertIn(browser_result["launchTimingStatus"], {"Ready", "Active work"})
        self.assertIn("Allowed now: yes", browser_result["launchTiming"])
        self.assertTrue(state["schedule_enabled"])
        self.assertEqual(state["machine_id"], "browser-schedule-node")
        self.assertEqual(sum(1 for item in state["schedule_grid"][today] if item), 48)
        for day, values in state["schedule_grid"].items():
            if day != today:
                self.assertEqual(sum(1 for item in values if item), 0, day)


if __name__ == "__main__":
    unittest.main()




