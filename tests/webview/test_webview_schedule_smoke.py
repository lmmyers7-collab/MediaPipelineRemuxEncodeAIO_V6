from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from tests.css_import_resolver import resolve_css_imports

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


WEBVIEW_STATIC_ROOT = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static"
WEB_STATIC = WEBVIEW_STATIC_ROOT / "assets"
PAGE_SCHEDULE = WEBVIEW_STATIC_ROOT / "partials" / "page-schedule.html"


def _read_components_css() -> str:
    return resolve_css_imports(WEB_STATIC / "styles.components.css", WEB_STATIC)


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
          let elementId = "";
          const node = {
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
          Object.defineProperty(node, "id", {
            get() { return elementId; },
            set(value) {
              elementId = String(value || "");
              if (elementId) elements.set(elementId, node);
            },
            configurable: true,
          });
          node.id = id;
          return node;
        }

        function selectorElement(selector) {
          if (!selectorElements.has(selector)) selectorElements.set(selector, makeElement(selector));
          return selectorElements.get(selector);
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
            return [];
          },
          querySelector(selector) {
            return null;
          },
          addEventListener() {},
        };

        vm.createContext(context);
        for (const asset of payload.assets) {
          vm.runInContext(asset.source, context, { filename: asset.name });
        }
        const scheduleView = context.mediaPipelineScheduleView;
        if (!scheduleView || typeof scheduleView !== "object") {
          throw new Error("missing mediaPipelineScheduleView namespace");
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
        const SCHEDULE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        function emptyGrid() {
          const grid = {};
          SCHEDULE_DAYS.forEach((day) => { grid[day] = Array.from({ length: 48 }, () => false); });
          return grid;
        }
        function currentGridFixture() {
          const grid = emptyGrid();
          [2, 3, 4, 5].forEach((index) => { grid.Tuesday[index] = true; });
          grid.Wednesday = Array.from({ length: 48 }, () => true);
          return grid;
        }
        function gridFromDayWindows(dayWindows) {
          const grid = emptyGrid();
          SCHEDULE_DAYS.forEach((day) => {
            grid[day] = scheduleView.scheduleDraftBlocksFromText(dayWindows?.[day] || "");
          });
          return grid;
        }
        function changedDays(left, right) {
          return SCHEDULE_DAYS.filter((day) => JSON.stringify(left[day] || []) !== JSON.stringify(right[day] || []));
        }
        context.apiPost = async (url, body) => {
          apiPosts.push({ url, body });
          if (url === "/api/schedule/preview") {
            const currentGrid = currentGridFixture();
            const grid = gridFromDayWindows(body.day_windows || {});
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
                schema_version: "desktop_schedule_patch_preview.v1",
                writes_app_state: false,
                enabled: Boolean(body.enabled),
                current_enabled: true,
                changed_enabled: false,
                changed_days: changedDays(currentGrid, grid),
                current_grid: currentGrid,
                grid,
              },
            };
          }
          if (url === "/api/schedule/save") {
            const currentGrid = currentGridFixture();
            const grid = gridFromDayWindows(body.day_windows || {});
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
                schema_version: "desktop_schedule_save_result.v1",
                writes_app_state: true,
                enabled: Boolean(body.enabled),
                current_enabled: true,
                changed_enabled: false,
                changed_days: changedDays(currentGrid, grid),
                current_grid: currentGrid,
                grid,
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
        function nodeText(node) {
          if (!node) return "";
          const own = node.textContent || "";
          const childText = Array.isArray(node.children) ? node.children.map((child) => nodeText(child)).join("\n") : "";
          return [own, childText].filter(Boolean).join("\n");
        }
        function tableText(id) {
          const tbody = context.document.getElementById(id);
          return tbody.children.flatMap((row) => row.children.map((cell) => nodeText(cell))).join("\n");
        }
        function requireContains(label, value, fragments) {
          for (const fragment of fragments) {
            if (!String(value).includes(fragment)) {
              throw new Error(`${label} missing ${fragment}\nActual:\n${value}`);
            }
          }
        }
        function requireNotContains(label, value, fragments) {
          for (const fragment of fragments) {
            if (String(value).includes(fragment)) {
              throw new Error(`${label} unexpectedly contained ${fragment}\nActual:\n${value}`);
            }
          }
        }

        async function main() {
        const schedule = {
          schema_version: "desktop_schedule_workspace.v1",
          enabled: true,
          evaluation: {
            allowed_now: false,
            current_day: "Monday",
            current_block_index: 20,
            current_block_start: "2026-05-18T10:00:00",
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

        scheduleView.renderSchedule(schedule);
        requireContains("editor impact", text("schedule-editor-impact"), ["Launch impact:", "Selected Launch mode:", "Preview the draft before saving schedule changes"]);
        requireContains("draft summary", text("schedule-editor-draft-summary"), ["Editor draft:", "52/336 blocks staged", "matches saved/current payload"]);
        requireContains("saved scope", text("schedule-day-scope"), ["Weekly View: saved/current payload"]);
        requireContains("save state", text("schedule-editor-save-state"), ["Preview required before save"]);
        if (!context.document.getElementById("schedule-editor-save-button").disabled) {
          throw new Error("save button should be disabled before backend preview");
        }
        requireContains("coverage status", text("schedule-coverage-status"), ["Outside window"]);
        requireContains("coverage rows", tableText("schedule-coverage-rows"), ["Schedule payload", "Current window", "Continuous watcher", "Weekly coverage", "Save boundary"]);
        requireContains("coverage detail default", text("schedule-coverage-detail"), ["Coverage check: Schedule payload", "App state path: C:/MediaPipeline/State/app_state.json"]);
        requireContains("guidance", text("schedule-guidance"), ["Backend continuous watcher: armed for PID 2222"]);
        requireContains("day legend", text("schedule-day-legend"), ["Weekly windows table: 3 selectable rows", "match=1", "ready=1", "review=1"]);
        requireContains("day detail default", text("schedule-day-detail"), ["Day: Monday", "no allowed window"]);
        requireContains("editor rows", tableText("schedule-editor-rows"), ["Monday", "Tuesday", "Wednesday", "1:00 AM-3:00 AM", "All day"]);
        requireContains("editor result", text("schedule-editor-result"), ["No schedule preview or save result loaded", "Backend validation owns time parsing"]);
        const mondayRail = context.document.getElementById("schedule-editor-monday-block-0")?.parentNode;
        if (!mondayRail || !String(mondayRail.className || "").includes("schedule-time-rail")) {
          throw new Error("schedule editor did not render Monday thermostat rail");
        }
        if (!String(mondayRail.parentNode?.children?.[2]?.className || "").includes("schedule-time-ticks")) {
          throw new Error("schedule editor did not render 3-hour timeline ticks");
        }
        requireContains("tuesday rail summary", text("schedule-editor-tuesday-summary"), ["1:00 AM-3:00 AM"]);
        if (!context.document.getElementById("schedule-editor-monday-copy-day")) {
          throw new Error("schedule editor did not render Copy Day for Monday");
        }
        if (!context.document.getElementById("schedule-editor-tuesday-paste-day")?.disabled) {
          throw new Error("Paste Day should be disabled until a day is copied");
        }

        const weeklyCoverage = scheduleView.scheduleCoverageRows(schedule).find((row) => row.key === "weekly-coverage");
        scheduleView.selectScheduleCoverageRow(weeklyCoverage);
        requireContains("weekly coverage detail", text("schedule-coverage-detail"), ["Allowed days: 2", "Allowed half-hour blocks: 52", "Allowed hours: 26.0"]);

        const enforcementCoverage = scheduleView.scheduleCoverageRows(schedule).find((row) => row.key === "enforcement");
        scheduleView.selectScheduleCoverageRow(enforcementCoverage);
        requireContains("enforcement detail", text("schedule-coverage-detail"), ["backend schedule-stop watcher"]);
        requireNotContains("enforcement detail", text("schedule-coverage-detail"), ["V" + "5 remains", "fallback workspace"]);

        const watcherCoverage = scheduleView.scheduleCoverageRows(schedule).find((row) => row.key === "continuous-watcher");
        scheduleView.selectScheduleCoverageRow(watcherCoverage);
        requireContains("watcher coverage detail", text("schedule-coverage-detail"), ["PID: 2222", "Deadline:", "Launch backend start arms this watcher"]);

        scheduleView.selectScheduleDay(schedule.day_summaries[2]);
        requireContains("all-day detail", text("schedule-day-detail"), ["Day: Wednesday", "allowed all day", "Schedule Editor panel"]);

        const today = new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(new Date());
        scheduleView.renderSchedule({
          ...schedule,
          evaluation: { ...schedule.evaluation, allowed_now: true, current_day: today, current_block_index: 18, current_block_start: "2026-05-19T09:00:00" },
          day_summaries: [{ day: today, allowed_blocks: 2, allowed_hours: 1, windows: ["09:00 - 10:00"], windows_text: "09:00 - 10:00" }],
        });
        requireContains("current day row", tableText("schedule-day-rows"), [`${today} (current)`, "09:00 - 10:00"]);
        requireContains("current day detail", text("schedule-day-detail"), ["Current window marker: current saved window"]);
        if (context.document.getElementById("schedule-day-rows").children[0]?.dataset?.status !== "current") {
          throw new Error("partial current row should use current status");
        }
        scheduleView.renderSchedule({
          ...schedule,
          evaluation: { ...schedule.evaluation, allowed_now: true, current_day: today, current_block_index: 18, current_block_start: "2026-05-19T09:00:00" },
          day_summaries: [{ day: today, allowed_blocks: 48, allowed_hours: 24, windows: ["All day"], windows_text: "All day" }],
        });
        if (context.document.getElementById("schedule-day-rows").children[0]?.dataset?.status !== "current-match") {
          throw new Error("all-day current row should preserve all-day success status with current marker");
        }
        requireContains("current all-day row", tableText("schedule-day-rows"), [`${today} (current)`, "All day"]);
        context.document.getElementById("pipeline-start-mode").value = "once";
        scheduleView.renderSchedule({
          ...schedule,
          evaluation: { ...schedule.evaluation, allowed_now: true, current_day: "" },
          day_summaries: [{ day: today, allowed_blocks: 2, allowed_hours: 1, windows: ["09:00 - 10:00"], windows_text: "09:00 - 10:00" }],
        });
        requireNotContains("unknown current day row", tableText("schedule-day-rows"), [`${today} (current)`]);
        requireContains("unknown current day detail", text("schedule-day-detail"), ["backend current day was not reported"]);
        requireContains("unknown current trust", text("schedule-timing"), ["Backend current day: not reported", "refresh before trusting current-window highlighting"]);
        context.document.getElementById("pipeline-start-mode").value = "validate";
        scheduleView.renderSchedule(schedule);

        scheduleView.renderWatchFolderStatus({
          schema_version: "desktop_watch_folders.v1",
          status: "running",
          enabled: true,
          running: true,
          effective_action: "enqueue_only",
          network_role: "standalone",
          roots: [
            { path: "C:/Media/Movies", reachable: true },
            { path: "Z:/Missing", reachable: false, last_error: "path unavailable" },
            { path: "Y:/Unknown" },
          ],
          recent_detections: [{ detected_utc: "2026-05-19T01:05:00", path: "C:/Media/Movies/File.mkv" }],
          last_refusal: { utc: "2026-05-19T00:55:00", reason: "outside schedule window" },
          last_launch: { requested_utc: "2026-05-19T00:56:00", outcome: "refused", pid: 0, message: "schedule gate closed" },
        });
        requireContains("watch root rows", tableText("schedule-watch-folder-root-rows"), ["C:/Media/Movies", "Reachable", "Z:/Missing", "Unreachable", "path unavailable", "Y:/Unknown", "Unknown"]);
        requireContains("watch event rows", tableText("schedule-watch-folder-event-rows"), ["Last refusal", "outside schedule window", "Last launch", "refused", "schedule gate closed", "Stable detection", "File.mkv"]);
        const watchEvents = context.document.getElementById("schedule-watch-folder-event-rows").children;
        if (!Array.from(watchEvents).some((row) => row.children[0]?.textContent === "Last launch" && row.dataset.status === "blocked")) {
          throw new Error("refused watch-folder launch should render blocked");
        }

        scheduleView.clearScheduleEditorWeek();
        let request = scheduleView.scheduleEditorRequest();
        if (request.day_windows.Monday !== "" || request.day_windows.Tuesday !== "") {
          throw new Error(`clear week did not blank schedule editor windows: ${JSON.stringify(request.day_windows)}`);
        }
        requireContains("dirty save state", text("schedule-editor-save-state"), ["Draft changed", "Preview required"]);
        requireContains("clear result", text("schedule-editor-result"), ["Week cleared:", "0/336 blocks staged"]);
        requireContains("draft scope", text("schedule-day-scope"), ["unsaved draft is staged"]);
        scheduleView.allowAllScheduleEditorWeek();
        request = scheduleView.scheduleEditorRequest();
        if (request.day_windows.Monday !== "all day" || request.day_windows.Sunday !== "all day") {
          throw new Error(`allow all did not stage all days: ${JSON.stringify(request.day_windows)}`);
        }
        requireContains("allow all result", text("schedule-editor-result"), ["All week allowed:", "336/336 blocks staged"]);
        scheduleView.clearScheduleEditorWeek();
        scheduleView.scheduleSetDayBlocks("Monday", [18, 19]);
        request = scheduleView.scheduleEditorRequest();
        if (request.day_windows.Monday !== "09:00 - 10:00") {
          throw new Error(`block editor did not generate a 30-minute window draft: ${JSON.stringify(request.day_windows)}`);
        }
        context.document.getElementById("schedule-editor-monday-copy-day").click();
        if (context.document.getElementById("schedule-editor-tuesday-paste-day").disabled) {
          throw new Error("Paste Day should be enabled after copying a day");
        }
        context.document.getElementById("schedule-editor-tuesday-paste-day").click();
        request = scheduleView.scheduleEditorRequest();
        if (request.day_windows.Tuesday !== "09:00 - 10:00") {
          throw new Error(`Paste Day did not copy Monday windows into Tuesday: ${JSON.stringify(request.day_windows)}`);
        }
        requireContains("paste status", text("schedule-editor-status"), ["Pasted Monday into Tuesday"]);
        scheduleView.loadCurrentScheduleIntoEditor();
        if (!context.document.getElementById("schedule-editor-tuesday-paste-day").disabled) {
          throw new Error("Load Current should clear copied day clipboard and disable Paste Day");
        }
        scheduleView.clearScheduleEditorWeek();
        scheduleView.scheduleSetDayBlocks("Monday", [18, 19]);
        scheduleView.scheduleSetDayBlocks("Tuesday", [18, 19]);
        const draftCoverage = scheduleView.scheduleCoverageRows(schedule).find((row) => row.key === "draft-coverage");
        if (!draftCoverage) {
          throw new Error("staged Schedule draft did not add draft coverage row");
        }
        scheduleView.selectScheduleCoverageRow(draftCoverage);
        requireContains("draft coverage detail", text("schedule-coverage-detail"), ["Coverage check: Draft coverage", "local staging evidence only", "Saved/current Schedule Trust"]);
        if (!context.document.getElementById("schedule-editor-save-button").disabled) {
          throw new Error("save button should stay disabled for an unpreviewed draft");
        }
        scheduleView.initScheduleViewEvents();
        await scheduleView.previewScheduleEditor();
        if (context.document.getElementById("schedule-editor-save-button").disabled) {
          throw new Error("save button should be enabled after successful backend preview");
        }
        requireContains("preview save state", text("schedule-editor-save-state"), ["Preview accepted", "Save Schedule is available"]);
        requireContains("preview diff", text("schedule-editor-result"), [
          "Schedule diff:",
          "Current enforcement: on",
          "Proposed enforcement: on",
          "Monday:",
          "Current: none",
          "Proposed: 09:00 - 10:00",
          "Added: 09:00 - 10:00",
          "Tuesday:",
          "Removed: 01:00 - 03:00",
          "Wednesday:",
          "Removed: all day",
        ]);
        scheduleView.scheduleSetDayBlocks("Tuesday", [2, 3]);
        if (!context.document.getElementById("schedule-editor-save-button").disabled) {
          throw new Error("save button should be disabled after editing a previewed draft");
        }
        requireContains("post-edit save state", text("schedule-editor-save-state"), ["Draft changed", "Preview required"]);
        const originalApiPost = context.apiPost;
        let delayedPreviewCalls = 0;
        context.apiPost = async (url, body) => {
          if (url === "/api/schedule/preview") {
            delayedPreviewCalls += 1;
            await new Promise((resolve) => setTimeout(resolve, 50));
          }
          return originalApiPost(url, body);
        };
        const previewPending = scheduleView.previewScheduleEditor();
        if (context.document.getElementById("schedule-editor-panel")["aria-busy"] !== "true") {
          throw new Error("Schedule editor panel should expose aria-busy=true while previewing");
        }
        await Promise.all([previewPending, scheduleView.previewScheduleEditor()]);
        if (context.document.getElementById("schedule-editor-panel")["aria-busy"] !== "false") {
          throw new Error("Schedule editor panel should clear aria-busy after preview");
        }
        if (delayedPreviewCalls !== 1) {
          throw new Error(`duplicate preview guard expected 1 backend call, got ${delayedPreviewCalls}`);
        }
        context.apiPost = originalApiPost;
        let delayedSaveCalls = 0;
        context.apiPost = async (url, body) => {
          if (url === "/api/schedule/save") {
            delayedSaveCalls += 1;
            await new Promise((resolve) => setTimeout(resolve, 50));
          }
          return originalApiPost(url, body);
        };
        const savePending = scheduleView.saveScheduleEditor();
        if (context.document.getElementById("schedule-editor-panel")["aria-busy"] !== "true") {
          throw new Error("Schedule editor panel should expose aria-busy=true while saving");
        }
        await Promise.all([savePending, scheduleView.saveScheduleEditor()]);
        if (context.document.getElementById("schedule-editor-panel")["aria-busy"] !== "false") {
          throw new Error("Schedule editor panel should clear aria-busy after save");
        }
        if (delayedSaveCalls !== 1) {
          throw new Error(`duplicate save guard expected 1 backend call, got ${delayedSaveCalls}`);
        }
        context.apiPost = originalApiPost;
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
        requireContains("save result", text("schedule-editor-result"), ["Command: schedule.save", "Writes app state: yes", "Schedule diff:", "Mutation guardrail"]);

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


class WebViewScheduleSmoke(unittest.TestCase):
    def test_schedule_editor_is_first_panel_in_static_markup(self) -> None:
        markup = PAGE_SCHEDULE.read_text(encoding="utf-8")
        self.assertLess(markup.index("<h2>Edit Schedule</h2>"), markup.index("<h2>Current Schedule</h2>"))
        self.assertIn("schedule-editor-status-strip", markup)
        self.assertIn("Time of Day", markup)
        self.assertIn('id="schedule-editor-panel"', markup)
        self.assertIn('aria-busy="false"', markup)
        self.assertIn("schedule-editor-impact", markup)
        self.assertIn("schedule-editor-draft-summary", markup)
        self.assertIn("schedule-current-scope", markup)
        self.assertIn("schedule-watch-folder-root-rows", markup)
        self.assertIn("schedule-watch-folder-event-rows", markup)
        self.assertIn("schedule-editor-primary-actions", markup)
        self.assertIn("schedule-editor-bulk-actions", markup)
        self.assertIn('aria-live="polite"', markup)
        controls_css = (WEB_STATIC / "styles.controls.css").read_text(encoding="utf-8")
        self.assertIn('tr[data-status="current-match"]', controls_css)
        self.assertIn('tr[data-status="unknown"]', controls_css)
        components_css = _read_components_css()
        self.assertIn(".schedule-time-rail", components_css)
        self.assertIn("grid-template-columns: repeat(48", components_css)

    def test_schedule_coverage_and_day_detail_render_in_node(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not available")

        assets = [
            "dom/query.js",
            "dom/text.js",
            "dom/status.js",
            "dom/filtering.js",
            "dom/table.js",
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
