from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


WEB_STATIC = Path(__file__).resolve().parents[1] / "mediapipeline_desktop_app" / "ui_web" / "static" / "assets"


def _schedule_runner_source() -> str:
    return textwrap.dedent(
        r"""
        const fs = require("fs");
        const vm = require("vm");

        const payload = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
        const elements = new Map();
        const selectorElements = new Map();
        const errors = [];

        function makeClassList() {
          const values = new Set();
          return {
            contains(value) { return values.has(value); },
            toggle(value, enabled) {
              if (enabled === false) values.delete(value);
              else values.add(value);
            },
            add(...items) { items.forEach((value) => values.add(value)); },
            remove(...items) { items.forEach((value) => values.delete(value)); },
          };
        }

        function makeElement(id = "") {
          const node = {
            id,
            textContent: "",
            value: "",
            checked: false,
            disabled: false,
            colSpan: 0,
            dataset: {},
            style: {},
            children: [],
            classList: makeClassList(),
            appendChild(child) { this.children.push(child); child.parentNode = this; return child; },
            append(...children) { children.forEach((child) => this.appendChild(child)); },
            replaceChildren(...children) { this.children = children; children.forEach((child) => { child.parentNode = this; }); },
            querySelectorAll(selector) {
              if (selector === 'tr[data-selectable-row="true"]') {
                return this.children.filter((child) => child?.dataset?.selectableRow === "true");
              }
              return [];
            },
            querySelector() { return null; },
            closest() { return null; },
            eventHandlers: {},
            addEventListener(type, handler) { this.eventHandlers[type] = handler; },
            click() {
              const handler = this.eventHandlers.click;
              if (typeof handler === "function") handler({ preventDefault() {} });
            },
            setAttribute(name, value) { this[name] = String(value); },
            scrollIntoView() {},
            focus() {},
          };
          return node;
        }

        function selectorElement(selector) {
          if (!selectorElements.has(selector)) selectorElements.set(selector, makeElement(selector));
          return selectorElements.get(selector);
        }

        function scheduleCopyTarget(day) {
          const selector = `[data-schedule-copy-target="${day}"]`;
          const node = selectorElement(selector);
          node.dataset.scheduleCopyTarget = day;
          return node;
        }

        const context = {
          console: {
            log() {},
            warn(...args) { errors.push(`warn:${args.join(" ")}`); },
            error(...args) { errors.push(`error:${args.join(" ")}`); },
          },
          setTimeout,
          clearTimeout,
          requestAnimationFrame(fn) { fn(); },
        };
        context.window = context;
        context.globalThis = context;
        context.document = {
          getElementById(id) {
            if (!elements.has(id)) elements.set(id, makeElement(id));
            return elements.get(id);
          },
          createElement(tag) {
            const node = makeElement();
            node.tagName = String(tag || "").toUpperCase();
            return node;
          },
          querySelectorAll(selector) {
            if (selector === "[data-schedule-copy-target]") {
              return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map(scheduleCopyTarget);
            }
            return [];
          },
          querySelector(selector) {
            if (selector === "[data-schedule-copy-source]") return selectorElement(selector);
            if (selector === "[data-schedule-copy-apply]") return selectorElement(selector);
            if (selector.startsWith('[data-schedule-copy-target="')) {
              return scheduleCopyTarget(selector.slice(28, -2));
            }
            return null;
          },
          addEventListener() {},
        };

        vm.createContext(context);
        for (const asset of payload.assets) {
          vm.runInContext(asset.source, context, { filename: asset.name });
        }
        function promoteMediaPipelineNamespaces() {
          Object.keys(context)
            .filter((key) => key.startsWith("mediaPipeline"))
            .forEach((namespace) => {
              const namespaceExports = context[namespace];
              if (!namespaceExports || typeof namespaceExports !== "object") return;
              Object.entries(namespaceExports).forEach(([name, value]) => {
                if (context[name] === undefined) context[name] = value;
              });
            });
        }
        promoteMediaPipelineNamespaces();
        const apiPosts = [];
        const commandResults = [];
        context.apiPost = async (url, body) => {
          apiPosts.push({ url, body });
          if (url === "/api/schedule/preview") {
            return {
              schema_version: "desktop_command_result.v1",
              command: "schedule.preview",
              ok: true,
              severity: "info",
              message: "Schedule patch preview is valid.",
              refresh_hint: "schedule",
              warnings: [],
              errors: [],
              data: {
                writes_app_state: false,
                enabled: Boolean(body.enabled),
                changed_enabled: false,
                changed_days: ["Monday"],
              },
            };
          }
          if (url === "/api/schedule/save") {
            return {
              schema_version: "desktop_command_result.v1",
              command: "schedule.save",
              ok: true,
              severity: "info",
              message: "Schedule saved.",
              refresh_hint: "schedule",
              warnings: [],
              errors: [],
              data: {
                writes_app_state: true,
                enabled: Boolean(body.enabled),
                changed_enabled: false,
                changed_days: ["Monday"],
              },
            };
          }
          throw new Error(`unexpected apiPost ${url}`);
        };
        context.appendCommandResult = (result) => { commandResults.push(result); };
        context.refreshAllNow = async () => {};
        context.confirm = () => true;

        function text(id) {
          return context.document.getElementById(id).textContent || "";
        }
        function tableText(id) {
          const tbody = context.document.getElementById(id);
          return tbody.children.flatMap((row) => row.children.map((cell) => cell.textContent || "")).join("\n");
        }
        function requireContains(label, value, fragments) {
          for (const fragment of fragments) {
            if (!String(value).includes(fragment)) {
              throw new Error(`${label} missing ${fragment}\nActual:\n${value}`);
            }
          }
        }

        async function main() {
        const schedule = {
          schema_version: "desktop_schedule_workspace.v1",
          enabled: true,
          evaluation: {
            allowed_now: false,
            status_text: "Schedule: Waiting | next allowed Tuesday 01:00",
            next_allowed_start: "2026-05-19T01:00:00",
            current_window_end: null,
            next_allowed_end: "2026-05-19T03:00:00",
          },
          app_state_path: "C:/MediaPipeline/State/app_state.json",
          continuous_watcher: {
            status: "armed",
            pid: 2222,
            deadline: "2026-05-19T03:00:00",
            stop_requested: false,
            message: "Backend schedule-stop watcher armed for PID 2222 at 2026-05-19T03:00:00.",
            error: "",
          },
          warnings: [],
          day_summaries: [
            { day: "Monday", allowed_blocks: 0, allowed_hours: 0, windows: [], windows_text: "None" },
            { day: "Tuesday", allowed_blocks: 4, allowed_hours: 2, windows: ["01:00 - 03:00"], windows_text: "01:00 - 03:00" },
            { day: "Wednesday", allowed_blocks: 48, allowed_hours: 24, windows: ["All day"], windows_text: "All day" },
          ],
        };

        context.renderSchedule(schedule);
        requireContains("coverage status", text("schedule-coverage-status"), ["Outside window"]);
        requireContains("coverage rows", tableText("schedule-coverage-rows"), ["Schedule payload", "Current window", "Continuous watcher", "Weekly coverage", "Save boundary"]);
        requireContains("coverage detail default", text("schedule-coverage-detail"), ["Coverage check: Schedule payload", "App state path: C:/MediaPipeline/State/app_state.json"]);
        requireContains("guidance", text("schedule-guidance"), ["Backend continuous watcher: armed for PID 2222"]);
        requireContains("day legend", text("schedule-day-legend"), ["Weekly windows table: 3 selectable rows", "match=1", "ready=1", "review=1"]);
        requireContains("day detail default", text("schedule-day-detail"), ["Day: Monday", "no allowed window"]);
        requireContains("editor rows", tableText("schedule-editor-rows"), ["Monday", "Tuesday", "Wednesday", "01:00 - 03:00", "All day"]);
        requireContains("editor result", text("schedule-editor-result"), ["No schedule preview or save result loaded", "Backend validation owns time parsing"]);

        const weeklyCoverage = context.scheduleCoverageRows(schedule).find((row) => row.key === "weekly-coverage");
        context.selectScheduleCoverageRow(weeklyCoverage);
        requireContains("weekly coverage detail", text("schedule-coverage-detail"), ["Allowed days: 2", "Allowed half-hour blocks: 52", "Allowed hours: 26.0"]);

        const watcherCoverage = context.scheduleCoverageRows(schedule).find((row) => row.key === "continuous-watcher");
        context.selectScheduleCoverageRow(watcherCoverage);
        requireContains("watcher coverage detail", text("schedule-coverage-detail"), ["PID: 2222", "Deadline:", "Launch backend start arms this watcher"]);

        context.selectScheduleDay(schedule.day_summaries[2]);
        requireContains("all-day detail", text("schedule-day-detail"), ["Day: Wednesday", "allowed all day", "Schedule Editor panel"]);

        context.clearScheduleEditorWeek();
        let request = context.scheduleEditorRequest();
        if (request.day_windows.Monday !== "" || request.day_windows.Tuesday !== "") {
          throw new Error(`clear week did not blank schedule editor windows: ${JSON.stringify(request.day_windows)}`);
        }
        context.scheduleSetDayBlocks("Monday", [18, 19]);
        request = context.scheduleEditorRequest();
        if (request.day_windows.Monday !== "09:00 - 10:00") {
          throw new Error(`block editor did not generate a 30-minute window draft: ${JSON.stringify(request.day_windows)}`);
        }
        context.initScheduleViewEvents();
        context.document.querySelector("[data-schedule-copy-source]").value = "Monday";
        context.document.querySelector('[data-schedule-copy-target="Tuesday"]').checked = true;
        context.document.querySelector('[data-schedule-copy-target="Wednesday"]').checked = true;
        context.document.querySelector("[data-schedule-copy-apply]").click();
        request = context.scheduleEditorRequest();
        if (request.day_windows.Tuesday !== "09:00 - 10:00" || request.day_windows.Wednesday !== "09:00 - 10:00") {
          throw new Error(`copy-day did not stage target days: ${JSON.stringify(request.day_windows)}`);
        }
        requireContains("copy-day result", text("schedule-editor-result"), ["Copied Monday schedule to Tuesday, Wednesday", "Mutation guardrail"]);
        await context.previewScheduleEditor();
        await context.saveScheduleEditor();
        if (!apiPosts.some((item) => item.url === "/api/schedule/preview")) {
          throw new Error("schedule preview did not call backend preview route");
        }
        const savePost = apiPosts.find((item) => item.url === "/api/schedule/save");
        if (!savePost || savePost.body.confirm_save !== true) {
          throw new Error(`schedule save did not send confirmed backend payload: ${JSON.stringify(savePost || null)}`);
        }
        if (!commandResults.some((item) => item.command === "schedule.save")) {
          throw new Error("schedule save command result was not appended");
        }
        requireContains("save result", text("schedule-editor-result"), ["Command: schedule.save", "Writes app state: yes", "Mutation guardrail"]);

        if (errors.length) {
          throw new Error(`console errors were recorded: ${errors.join("; ")}`);
        }
        console.log(JSON.stringify({ ok: true, coverage: text("schedule-coverage-status") }));
        }
        main().catch((error) => {
          console.error(error && error.stack ? error.stack : error);
          process.exit(1);
        });
        """
    )


class WebViewScheduleSmokeTests(unittest.TestCase):
    def test_schedule_coverage_and_day_detail_render_in_node(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not available")

        assets = [
            "domHelpers.js",
            "scheduleView.js",
        ]
        payload = {
            "assets": [
                {"name": name, "source": (WEB_STATIC / name).read_text(encoding="utf-8")}
                for name in assets
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = tmp_path / "runner.js"
            data = tmp_path / "payload.json"
            runner.write_text(_schedule_runner_source(), encoding="utf-8")
            data.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [node, str(runner), str(data)],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
        if completed.returncode != 0:
            self.fail(
                "WebView schedule smoke failed.\n"
                f"STDOUT:\n{completed.stdout}\n"
                f"STDERR:\n{completed.stderr}"
            )
        self.assertIn('"ok":true', completed.stdout)


if __name__ == "__main__":
    unittest.main()
