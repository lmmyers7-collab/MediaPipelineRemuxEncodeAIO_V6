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

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


WEB_STATIC = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static" / "assets"


def _rename_readiness_runner_source() -> str:
    return textwrap.dedent(
        r"""
        const fs = require("fs");
        const vm = require("vm");

        const payload = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
        const elements = new Map();
        const errors = [];

        function makeClassList() {
          const values = new Set();
          return {
            contains(value) { return values.has(value); },
            toggle(value, enabled) {
              if (enabled === false) values.delete(value);
              else values.add(value);
            },
            add(value) { values.add(value); },
            remove(value) { values.delete(value); },
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
            replaceChildren(...children) { this.children = children; children.forEach((child) => { child.parentNode = this; }); },
            querySelectorAll(selector) {
              if (selector === 'tr[data-selectable-row="true"]') {
                return this.children.filter((child) => child?.dataset?.selectableRow === "true");
              }
              return [];
            },
            querySelector() { return null; },
            closest() { return null; },
            addEventListener() {},
            setAttribute(name, value) { this[name] = String(value); },
            scrollIntoView() {},
            focus() {},
          };
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
          confirm() { return true; },
        };
        context.__renameApplyPosts = [];
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
            if (selector === "[data-movie-filter]") return [];
            return [];
          },
          querySelector() { return null; },
          addEventListener() {},
        };
        context.apiPost = async (url) => {
          context.__renameApplyPosts.push(String(url || ""));
          return { ok: false, message: "mocked" };
        };
        context.appendCommandResult = () => {};
        context.commandResultDisplayMessage = (value) => value?.message || "";
        context.getLastSettings = () => ({
          config: {
            RoutingProfile: "plex_direct_stream",
            SizeGuardMode: "advisory",
            OutputContainer: "mkv",
            ConvertTx3gToSrt: true,
            DropTx3gAfterConversion: false,
            ConvertBdpgsToSrt: true,
            DropBdpgsAfterConversion: false,
            DropAssAfterConversion: false,
            DeferredPublish: true,
          },
        });

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

        function setValue(id, value) {
          context.document.getElementById(id).value = value;
        }
        function setChecked(id, value) {
          context.document.getElementById(id).checked = Boolean(value);
        }
        function text(id) {
          return context.document.getElementById(id).textContent || "";
        }
        function readinessCellText() {
          const tbody = context.document.getElementById("rename-apply-readiness-rows");
          return tbody.children.flatMap((row) => row.children.map((cell) => cell.textContent || "")).join("\n");
        }
        function outcomeCellText() {
          const tbody = context.document.getElementById("rename-apply-outcome-rows");
          return tbody.children.flatMap((row) => row.children.map((cell) => cell.textContent || "")).join("\n");
        }
        function previewCellText() {
          const tbody = context.document.getElementById("rename-rows");
          return tbody.children.flatMap((row) => row.children.map((cell) => cell.textContent || "")).join("\n");
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
              throw new Error(`${label} unexpectedly included ${fragment}\nActual:\n${value}`);
            }
          }
        }

        (async () => {
        context.getSelectedQueueRow = () => ({
          source_path: "C:/Queue/Selected Rename Source.mkv",
          display_name: "Selected Rename Source.mkv",
        });
        context.getLastQueueRows = () => [
          { source_path: "C:/Queue/Selected Rename Source.mkv", display_name: "Selected Rename Source.mkv" },
          { source_path: "C:/Queue/Second Rename Source.mkv", display_name: "Second Rename Source.mkv" },
          { source_path: "", display_name: "Missing source path" },
        ];
        setValue("rename-add-path-input", "C:/Manual/Typed Rename Source.mkv");
        context.addRenamePathFromInput();
        requireContains("manual path add", context.document.getElementById("rename-paths").value, ["C:/Manual/Typed Rename Source.mkv"]);
        requireContains("manual path summary", text("rename-file-source-summary"), ["Manual path added 1 path", "Source paths staged: 1", "Origins: manual=1"]);
        context.clearRenamePaths();
        requireContains("clear path summary", text("rename-file-source-summary"), ["Cleared staged rename paths.", "No source paths staged."]);
        context.useSelectedQueueRowForRename();
        requireContains("selected queue import paths", context.document.getElementById("rename-paths").value, ["C:/Queue/Selected Rename Source.mkv"]);
        requireContains("selected queue import summary", text("rename-file-source-summary"), ["Selected Rename Source.mkv added 1 path", "Source paths staged: 1", "Origins: queue=1"]);
        context.useLoadedQueueRowsForRename();
        requireContains("loaded queue import paths", context.document.getElementById("rename-paths").value, ["C:/Queue/Selected Rename Source.mkv", "C:/Queue/Second Rename Source.mkv"]);
        requireContains("loaded queue import summary", text("rename-file-source-summary"), ["Loaded Queue rows added 1 path", "Source paths staged: 2", "Origins: queue=2", "Loaded Queue rows: 3"]);

        setValue("rename-mode", "tv");
        setValue("rename-show", "Serial Experiments Lain");
        setValue("rename-season", "S02");
        setValue("rename-start", "E01");
        setValue("rename-paths", "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv");
        setChecked("rename-sidecars", true);
        setChecked("rename-force-pipeline", false);
        setChecked("rename-pipeline-preview", true);

        const first = {
          source: "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv",
          source_name: "Serial Experiments Lain E01 Weird.mkv",
          destination: "C:/TV/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
          target_name: "Serial Experiments Lain - S02E01 - Weird.mkv",
          pipeline_guess: "Serial Experiments Lain - S02E01 - Weird.mkv",
          status: "ready",
          confidence: "high",
          preview_source: "auto_tv_heuristic",
          change_kind: "rename",
          sidecar_count: 0,
          destination_exists: false,
          matches_target: false,
          warnings: [],
          errors: [],
        };
        context.renderRenamePreview({ rows: [first], counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
        context.selectRenameRow(first);
        context.renderRenameApplyReadiness();
        if (context.document.getElementById("rename-log-bad-case-button").disabled) {
          throw new Error("bad rename case log button did not enable after selecting a preview row");
        }
        const logPayload = context.mediaPipelineRenameView.renameBadCasePayloadFromRow(first);
        if (logPayload.source_folder !== "Season 02") throw new Error("bad case source_folder was not derived from selected source path: " + JSON.stringify(logPayload));
        if (logPayload.source_file !== "Serial Experiments Lain E01 Weird.mkv") throw new Error("bad case source_file was not derived from selected source path: " + JSON.stringify(logPayload));
        if (logPayload.expected_name !== "Serial Experiments Lain - S02E01 - Weird.mkv") throw new Error("bad case expected_name did not use current final name: " + JSON.stringify(logPayload));
        if (logPayload.confirm_append !== true) throw new Error("bad case payload omitted confirm_append=true: " + JSON.stringify(logPayload));
        context.mediaPipelineRenameView.openRenameBadCaseDialog();
        setValue("rename-log-case-expected-name", "Serial Experiments Lain - S02E01 - Weird Fixed.mkv");
        setValue("rename-log-case-status-select", "pending");
        const badCasePosts = [];
        const originalApiPost = context.apiPost;
        context.apiPost = async (url, body) => {
          badCasePosts.push({ url: String(url || ""), body: JSON.parse(JSON.stringify(body || {})) });
          return { ok: true, command: "rename.filter_case.append", message: "logged", data: { case_id: "serial-experiments-lain-e01", status: "pending" } };
        };
        await context.mediaPipelineRenameView.submitRenameBadCaseDialog();
        context.apiPost = originalApiPost;
        const badCasePost = badCasePosts.find((entry) => entry.url === "/api/rename/filter-cases");
        if (!badCasePost) throw new Error("bad rename case logging did not post /api/rename/filter-cases");
        if (badCasePost.body.confirm_append !== true) throw new Error("bad rename case post omitted confirm_append=true: " + JSON.stringify(badCasePost.body));
        if (badCasePost.body.expected_name !== "Serial Experiments Lain - S02E01 - Weird Fixed.mkv") throw new Error("bad rename case post did not use edited expected name: " + JSON.stringify(badCasePost.body));
        requireContains("bad case visible result", text("rename-log-case-message"), ["logged", "no filesystem rename"]);
        const logDialog = context.document.getElementById("rename-log-case-dialog");
        if (logDialog && logDialog.open) logDialog.close("done");
        requireContains("batch safety unchecked scope", text("rename-batch-safety"), ["Apply scope", "checked rows are required", "selected_sources"]);
        requireNotContains("batch safety unchecked scope", text("rename-batch-safety"), ["selected detail row"]);
        requireContains("no checked readiness", text("rename-apply-readiness-status"), ["Blocked"]);
        requireContains("unchecked apply button", text("rename-apply-button"), ["Check rows before apply"]);
        requireContains("unchecked apply hint", text("rename-apply-status-hint"), ["No rows checked", "Check Applicable"]);
        context.checkApplicableRenameRows();
        requireContains("ready status", text("rename-apply-readiness-status"), ["Ready"]);
        requireContains("ready cells", readinessCellText(), ["Apply scope", "checked rows", "Mutation boundary", "/api/rename/apply"]);
        requireContains("checked apply button", text("rename-apply-button"), ["Apply 1 checked rename"]);
        requireContains("checked apply hint", text("rename-apply-status-hint"), ["Checked 1 ready/match row", "skipped 0"]);
        setValue("rename-show", "Serial Experiments Lain Changed");
        context.syncRenameCommandButtons();
        requireContains("stale apply button", text("rename-apply-button"), ["Preview out of date"]);
        requireContains("stale apply hint", text("rename-apply-status-hint"), ["Preview out of date", "Run Preview again"]);
        if (!context.document.getElementById("rename-apply-button").disabled) {
          throw new Error("stale preview did not disable Apply");
        }
        setValue("rename-show", "Serial Experiments Lain");
        context.renderRenamePreview({ rows: [first], counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
        requireContains("pipeline handoff status", text("rename-pipeline-handoff-status"), ["Ready"]);
        requireContains("pipeline handoff", text("rename-pipeline-handoff"), ["Rename-to-pipeline handoff", "Saved routing profile: plex_direct_stream", "output container: mkv", "renaming changes filenames only", "Mutation guardrail"]);
        context.renderRenameApplyResult({
          command: "rename.apply",
          ok: true,
          message: "Applied selected rename.",
          data: {
            selected: 1,
            applied_count: 1,
            renamed: 1,
            unchanged: 0,
            sidecars: 1,
            media_operations: 1,
            sidecar_operations: 1,
            undo_manifest: "C:/State/Rename/undo.json",
            rows: [{ source: first.source, destination: first.destination, status: "renamed", sidecar_count: 1 }],
          },
          request: { mode: "tv", confirm_apply: true, selected_sources: [first.source] },
        });
        requireContains("apply outcome status", text("rename-apply-outcome-status"), ["Applied"]);
        requireContains("apply outcome summary", text("rename-apply-outcome-summary"), ["Backend rename apply outcome review", "selected=1", "Undo manifest: C:/State/Rename/undo.json", "read-only"]);
        requireContains("apply outcome rows", outcomeCellText(), ["Backend result", "Selected scope", "Sidecar operations", "Undo / rollback evidence", "Mutation boundary"]);

        const largeRows = Array.from({ length: 260 }, (_value, index) => {
          const episode = String(index + 1).padStart(2, "0");
          return {
            ...first,
            source: `C:/TV/S02/Serial Experiments Lain E${episode}.mkv`,
            source_name: `Serial Experiments Lain E${episode}.mkv`,
            destination: `C:/TV/S02/Serial Experiments Lain - S02E${episode}.mkv`,
            target_name: `Serial Experiments Lain - S02E${episode}.mkv`,
            pipeline_guess: `Serial Experiments Lain - S02E${episode}.mkv`,
          };
        });
        setValue("rename-paths", largeRows.map((row) => row.source).join("\n"));
        context.renderRenamePreview({ rows: largeRows, counts: { total: 260, ready: 260 }, confidence_counts: { high: 260 }, preview_source_counts: { auto_tv_heuristic: 260 }, change_kind_counts: { rename: 260 } });
        requireContains("large preview status", text("rename-status"), ["260 ready", "250 shown / 260 preview rows"]);
        requireContains("large preview legend", text("rename-table-legend"), ["Display cap: 250 shown / 260 preview rows rendered", "not visible in the table"]);
        context.checkApplicableRenameRows();
        requireContains("large checked count", text("rename-selected-count"), ["260 checked"]);
        requireContains("checked apply button", text("rename-apply-button"), ["Apply 260 checked renames"]);
        requireContains("large selection audit", text("rename-selection-audit"), ["Rows in scope: 260", "Rendered rows: 250 of 260", "checked scope may include rows not currently rendered"]);
        requireContains("large readiness cells", readinessCellText(), ["Render cap visibility", "250 of 260 preview row(s) are rendered", "unrendered backend preview rows"]);

        const blockedExisting = { ...first, status: "blocked", errors: ["destination already exists"], warnings: [] };
        context.renderRenamePreview({ rows: [blockedExisting], counts: { total: 1, blocked: 1 }, confidence_counts: { blocked: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { blocked: 1 } });
        requireContains("blocked status cell reason", previewCellText(), ["Blocked: destination already exists"]);

        const duplicateA = { ...first, source: "C:/TV/S02/E01.mkv", source_name: "E01.mkv" };
        const duplicateB = { ...first, source: "C:/TV/S02/E02.mkv", source_name: "E02.mkv" };
        setValue("rename-paths", "C:/TV/S02/E01.mkv\nC:/TV/S02/E02.mkv");
        context.renderRenamePreview({ rows: [duplicateA, duplicateB], counts: { total: 2, ready: 2 }, confidence_counts: { high: 2 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
        context.checkApplicableRenameRows();
        context.renderRenameApplyReadiness();
        requireContains("duplicate checked count", text("rename-selected-count"), ["0 checked"]);
        requireContains("duplicate status", text("rename-apply-readiness-status"), ["Blocked"]);
        requireContains("duplicate cells", readinessCellText(), ["Duplicate destinations", "duplicate target", "selected_sources"]);
        context.applySelectedRename();
        requireContains("duplicate apply detail", text("rename-detail"), ["No rows checked", "duplicate"]);
        if (context.__renameApplyPosts.some((url) => url === "/api/rename/apply")) {
          throw new Error("duplicate-target apply readiness blocker still posted to /api/rename/apply");
        }

        if (errors.length) {
          throw new Error(`console errors were recorded: ${errors.join("; ")}`);
        }
        console.log(JSON.stringify({ ok: true, status: text("rename-apply-readiness-status") }));
        })().catch((error) => {
          console.error(error && error.stack ? error.stack : String(error));
          process.exitCode = 1;
        });
        """
    )


def _run_rename_readiness_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the WebView rename readiness smoke.")
    assets = []
    for name in (
        "dom/query.js",
        "dom/text.js",
        "dom/status.js",
        "dom/filtering.js",
        "dom/table.js",
        "domHelpers.js",
        "renameLabels.js",
        "renameHistoryView.js",
        "rename/preview.js",
        "rename/applyReadiness.js",
        "rename/applyResult.js",
        "renameView.js",
    ):
        assets.append({"name": name, "source": (WEB_STATIC / name).read_text(encoding="utf-8")})
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "rename-readiness-payload.json"
        runner_path = tmp / "rename-readiness-runner.cjs"
        payload_path.write_text(json.dumps({"assets": assets}, ensure_ascii=False), encoding="utf-8")
        runner_path.write_text(_rename_readiness_runner_source(), encoding="utf-8")
        result = subprocess.run(
            [node, str(runner_path), str(payload_path)],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "WebView rename readiness smoke failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return json.loads(result.stdout)


class WebViewRenameReadinessSmoke(unittest.TestCase):
    def test_rename_apply_readiness_distinguishes_ready_and_duplicate_scope(self) -> None:
        result = _run_rename_readiness_smoke()
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Blocked")


if __name__ == "__main__":
    unittest.main()
