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
          const listeners = {};
          const node = {
            id,
            textContent: "",
            value: "",
            checked: false,
            disabled: false,
            hidden: false,
            open: false,
            returnValue: "",
            colSpan: 0,
            dataset: {},
            style: {},
            children: [],
            classList: makeClassList(),
            appendChild(child) {
              this.children.push(child);
              child.parentNode = this;
              this.textContent = this.children.map((item) => item?.textContent || "").join("");
              return child;
            },
            replaceChildren(...children) {
              this.children = children;
              children.forEach((child) => { child.parentNode = this; });
              this.textContent = children.map((item) => item?.textContent || "").join("");
            },
            querySelectorAll(selector) {
              if (selector === 'tr[data-selectable-row="true"]') {
                return this.children.filter((child) => child?.dataset?.selectableRow === "true");
              }
              return [];
            },
            querySelector() { return null; },
            closest() { return null; },
            addEventListener(type, callback) {
              if (!listeners[type]) listeners[type] = [];
              listeners[type].push(callback);
            },
            dispatchEvent(event) {
              const item = event || {};
              item.target = item.target || this;
              item.stopPropagation = item.stopPropagation || (() => {});
              item.preventDefault = item.preventDefault || (() => {});
              (listeners[item.type] || []).forEach((callback) => callback(item));
              return true;
            },
            click() {
              if (this.type === "checkbox" && !this.disabled) this.checked = !this.checked;
              this.dispatchEvent({ type: "click", target: this });
              if (this.type === "checkbox" && !this.disabled) this.dispatchEvent({ type: "change", target: this });
            },
            setAttribute(name, value) { this[name] = String(value); },
            showModal() { this.open = true; },
            close(value = "") {
              this.returnValue = String(value || "");
              this.open = false;
              this.dispatchEvent({ type: "close", target: this });
            },
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
        context.__renameApplyPosts = [];
        context.__renameBrowsePosts = [];
        context.apiPost = async (url, body = {}) => {
          if (String(url || "") === "/api/rename/browse") {
            context.__renameBrowsePosts.push({ url: String(url || ""), body });
            if ((body.paths || []).some((path) => String(path).includes("Season 02"))) {
              return {
                command: "rename.browse",
                ok: true,
                message: "Resolved dropped path(s) to 2 media files.",
                data: {
                  paths: ["C:/Drop/Season 02/Ranma - S01E01.mkv", "C:/Drop/Season 02/Ranma - S01E02.mkv"],
                  selection_mode: "folder_files",
                  source: "dropped_paths",
                  path_count: 2,
                  raw_path_count: 4,
                  ignored_path_count: 2,
                  ignored_sidecar_count: 2,
                },
              };
            }
            return {
              command: "rename.browse",
              ok: true,
              message: "Resolved dropped path(s) to 1 media file.",
              data: {
                paths: ["C:/Drop/Ranma - S01E01.mkv"],
                selection_mode: "folder_files",
                source: "dropped_paths",
                path_count: 1,
                raw_path_count: 2,
                ignored_path_count: 1,
                ignored_sidecar_count: 1,
              },
            };
          }
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
        context.mediaPipelineRenameView.addRenamePathFromInput();
        requireContains("manual path add", context.document.getElementById("rename-paths").value, ["C:/Manual/Typed Rename Source.mkv"]);
        requireContains("manual path summary", text("rename-file-source-summary"), ["Manual path added 1 path", "Source paths staged: 1", "Media paths eligible for preview/apply: 1", "Origins: manual=1"]);
        context.mediaPipelineRenameView.clearRenamePaths();
        requireContains("clear path summary", text("rename-file-source-summary"), ["Cleared staged rename paths.", "No source paths staged."]);
        context.mediaPipelineRenameView.useSelectedQueueRowForRename();
        requireContains("selected queue import paths", context.document.getElementById("rename-paths").value, ["C:/Queue/Selected Rename Source.mkv"]);
        requireContains("selected queue import summary", text("rename-file-source-summary"), ["Selected Rename Source.mkv added 1 path", "Source paths staged: 1", "Media paths eligible for preview/apply: 1", "Origins: queue=1"]);
        context.mediaPipelineRenameView.useLoadedQueueRowsForRename();
        requireContains("loaded queue import paths", context.document.getElementById("rename-paths").value, ["C:/Queue/Selected Rename Source.mkv", "C:/Queue/Second Rename Source.mkv"]);
        requireContains("loaded queue import summary", text("rename-file-source-summary"), ["Loaded Queue rows added 1 path", "Source paths staged: 2", "Media paths eligible for preview/apply: 2", "Origins: queue=2", "Loaded Queue rows: 3"]);
        context.mediaPipelineRenameView.clearRenamePaths();
        const tauriDropped = context.mediaPipelineRenameView.renameDroppedPathValuesFromBridgeDetail({
          kind: "drop",
          paths: [
            "C:/Drop/Ranma - S01E01.mkv",
            "C:/Drop/Ranma - S01E01.pipeline.json",
            "Ranma - S01E02.mkv",
          ],
        });
        if (tauriDropped.length !== 2 || !tauriDropped.includes("C:/Drop/Ranma - S01E01.mkv") || !tauriDropped.includes("C:/Drop/Ranma - S01E01.pipeline.json")) {
          throw new Error("Tauri dropped paths were not normalized correctly: " + JSON.stringify(tauriDropped));
        }
        if (context.mediaPipelineRenameView.renameDroppedPathFromFile({ name: "Ranma - S01E02.mkv" }) !== "") {
          throw new Error("bare browser File.name should not be accepted as a filesystem path");
        }
        await context.mediaPipelineRenameView.handleRenameDroppedPaths(tauriDropped, "Tauri drag and drop");
        requireContains("tauri drop summary", text("rename-file-source-summary"), ["Tauri drag and drop added 1 path", "Ignored 1 non-media path including 1 sidecar path", "Source paths staged: 1", "Media paths eligible for preview/apply: 1", "Origins: drop=1"]);
        if (context.__renameBrowsePosts[0].body.selection_mode !== "folder_files") {
          throw new Error("drop did not resolve through folder_files browse mode: " + JSON.stringify(context.__renameBrowsePosts[0]));
        }
        context.mediaPipelineRenameView.clearRenamePaths();
        await context.mediaPipelineRenameView.handleRenameDroppedPaths(["C:/Drop/Season 02"], "Drag and drop");
        requireContains("dropped folder summary", text("rename-file-source-summary"), ["Drag and drop added 2 paths", "Ignored 2 non-media paths including 2 sidecar paths", "Source paths staged: 2", "Media paths eligible for preview/apply: 2", "Origins: drop=2", "Ranma - S01E01.mkv"]);
        if (context.document.getElementById("rename-paths").value.includes("C:/Drop/Season 02\n") || context.document.getElementById("rename-paths").value === "C:/Drop/Season 02") {
          throw new Error("dropped folder path was staged instead of direct media children");
        }
        context.mediaPipelineRenameView.clearRenamePaths();
        await context.mediaPipelineRenameView.handleRenameDroppedPaths(["Ranma - S01E02.mkv"], "Drag and drop");
        requireContains("bare drop summary", text("rename-file-source-summary"), ["Drop did not expose full filesystem paths", "No source paths staged."]);

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
        setValue("rename-paths", [
          "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv",
          "C:/TV/Season 02/Serial Experiments Lain E01 Weird.pipeline.json",
        ].join("\n"));
        context.mediaPipelineRenameView.renderRenameFileSourceSummary("Sidecar classification check.");
        requireContains("sidecar path summary", text("rename-file-source-summary"), ["Source paths staged: 2", "Media paths eligible for preview/apply: 1", "Ignored by preview/apply: 1 (1 sidecar"]);
        context.renderRenamePreview({
          rows: [first],
          preview_fingerprint: "rename-preview-fp",
          counts: { total: 1, ready: 1 },
          input_counts: { raw: 2, media: 1, ignored: 1, ignored_sidecar: 1 },
          confidence_counts: { high: 1 },
          preview_source_counts: { auto_tv_heuristic: 1 },
          change_kind_counts: { rename: 1 },
          warnings: ["Ignored 1 staged rename sidecar path(s); sidecars are attached to media rows automatically."],
        });
        requireContains("sidecar preview summary", text("rename-summary"), ["Rows: 1", "Preview warnings: Ignored 1 staged rename sidecar path"]);
        requireNotContains("sidecar preview rows", previewCellText(), ["pipeline.json"]);
        setValue("rename-paths", "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv");
        context.renderRenamePreview({ rows: [first], preview_fingerprint: "rename-preview-fp", counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
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
        const warningSecond = {
          ...first,
          source: "C:/TV/Season 02/Serial Experiments Lain E02 Girls.mkv",
          source_name: "Serial Experiments Lain E02 Girls.mkv",
          destination: "C:/TV/Season 02/Serial Experiments Lain - S02E02 - Girls.mkv",
          target_name: "Serial Experiments Lain - S02E02 - Girls.mkv",
          pipeline_guess: "Serial Experiments Lain - S02E02 - Girls.mkv",
          status: "warning",
          confidence: "review",
          warnings: ["Manual review needed"],
        };
        context.renderRenamePreview({ rows: [first, warningSecond], preview_fingerprint: "rename-preview-fp", counts: { total: 2, ready: 1, warning: 1 }, confidence_counts: { high: 1, review: 1 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
        const manualFirstCheckbox = context.document.getElementById("rename-rows").children[0].children[0].children[0];
        manualFirstCheckbox.click();
        requireContains("manual checkbox count", text("rename-selected-count"), ["1 checked"]);
        requireContains("manual checkbox apply", text("rename-apply-button"), ["Apply 1 checked rename"]);
        manualFirstCheckbox.click();
        requireContains("manual checkbox unchecked count", text("rename-selected-count"), ["0 checked"]);
        const manualFirstCell = context.document.getElementById("rename-rows").children[0].children[0];
        manualFirstCell.click();
        requireContains("manual checkbox cell count", text("rename-selected-count"), ["1 checked"]);
        context.mediaPipelineRenameView.clearCheckedRenameRows();
        context.mediaPipelineRenameView.checkApplicableRenameRows();
        requireContains("ready status", text("rename-apply-readiness-status"), ["Ready"]);
        requireContains("ready cells", readinessCellText(), ["Apply scope", "checked rows", "Mutation boundary", "/api/rename/apply"]);
        requireContains("checked apply button", text("rename-apply-button"), ["Apply 1 checked rename"]);
        requireContains("checked apply hint", text("rename-apply-status-hint"), ["Checked 1 ready/match row", "warning=1"]);
        context.mediaPipelineRenameView.clearCheckedRenameRows();
        context.mediaPipelineRenameView.checkAllRenameRows();
        requireContains("check all status", text("rename-selection-audit-status"), ["Checked selectable rows"]);
        requireContains("check all count", text("rename-selected-count"), ["2 checked"]);
        requireContains("check all apply button", text("rename-apply-button"), ["Apply 2 checked renames"]);
        requireContains("check all hint", text("rename-apply-status-hint"), ["Checked 2 selectable rows", "skipped 0"]);
        requireContains("check all detail", text("rename-detail"), ["Review warnings before apply"]);
        context.mediaPipelineRenameView.clearCheckedRenameRows();
        context.renderRenamePreview({ rows: [first], preview_fingerprint: "rename-preview-fp", counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
        context.mediaPipelineRenameView.checkApplicableRenameRows();
        setValue("rename-show", "Serial Experiments Lain Changed");
        context.mediaPipelineRenameView.syncRenameCommandButtons();
        requireContains("stale apply button", text("rename-apply-button"), ["Preview out of date"]);
        requireContains("stale apply hint", text("rename-apply-status-hint"), ["Preview out of date", "Run Preview again"]);
        if (!context.document.getElementById("rename-apply-button").disabled) {
          throw new Error("stale preview did not disable Apply");
        }
        setValue("rename-show", "Serial Experiments Lain");
        context.renderRenamePreview({ rows: [first], preview_fingerprint: "rename-preview-fp", counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
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
        requireContains("apply outcome summary", text("rename-apply-outcome-summary"), ["Backend rename apply outcome review", "selected=1", "Undo manifest: C:/State/Rename/undo.json", "Mutation guardrail"]);
        requireContains("apply outcome rows", outcomeCellText(), ["Backend result", "Selected scope", "Sidecar operations", "Undo / rollback evidence", "Mutation boundary"]);
        requireContains("apply status panel", text("rename-apply-status-summary"), ["1 renamed / 1 applied"]);
        requireContains("undo status after apply", text("rename-undo-status"), ["Undo available for the last apply"]);
        const undoButton = context.document.getElementById("rename-undo-button");
        if (undoButton.hidden) throw new Error("undo button stayed hidden after apply result with undo manifest");
        if (undoButton.disabled) throw new Error("undo button stayed disabled after apply result with undo manifest");
        if (!String(undoButton.title || "").includes("C:/State/Rename/undo.json")) {
          throw new Error("undo button did not expose manifest evidence in its title: " + String(undoButton.title || ""));
        }
        const undoPosts = [];
        let resolveUndoPost = null;
        const delayedUndoPost = new Promise((resolve) => { resolveUndoPost = resolve; });
        const undoOriginalApiPost = context.apiPost;
        context.apiPost = async (url, body = {}) => {
          undoPosts.push({ url: String(url || ""), body: JSON.parse(JSON.stringify(body || {})) });
          if (String(url || "") === "/api/rename/undo") return delayedUndoPost;
          if (String(url || "") === "/api/rename/preview") return { rows: [], counts: {} };
          return { command: "unexpected", ok: false, message: "unexpected " + String(url || "") };
        };
        const cancelUndo = context.mediaPipelineRenameView.undoLastRenameApply();
        const confirmDialog = context.document.getElementById("rename-confirm-dialog");
        if (!confirmDialog.open) throw new Error("undo confirmation dialog did not open before posting");
        requireContains("undo confirm title", text("rename-confirm-title"), ["Confirm undo rename"]);
        requireContains("undo confirm count", text("rename-confirm-count"), ["Undo last apply", "2 operations"]);
        requireContains("undo confirm button", text("rename-confirm-apply-button"), ["Undo Last Apply"]);
        confirmDialog.close("cancel");
        await cancelUndo;
        if (undoPosts.some((entry) => entry.url === "/api/rename/undo")) {
          throw new Error("canceling undo confirmation still posted /api/rename/undo");
        }
        requireContains("undo status after cancel", text("rename-undo-status"), ["Undo available for the last apply"]);
        const confirmUndo = context.mediaPipelineRenameView.undoLastRenameApply();
        if (!confirmDialog.open) throw new Error("second undo confirmation dialog did not open");
        confirmDialog.close("confirm");
        await Promise.resolve();
        requireContains("undo activity", text("rename-apply-progress-bars"), ["Undoing last apply... waiting for backend result", "elapsed"]);
        resolveUndoPost({
          command: "rename.undo",
          ok: true,
          message: "Undo completed.",
          data: {
            schema_version: "desktop_rename_undo_result.v1",
            media_operations: 1,
            sidecar_operations: 1,
            undone: 2,
            skipped: 0,
            failed: 0,
            undo_manifest: "C:/State/Rename/undo.json",
            rows: [{ source: first.destination, destination: first.source, status: "undone", kind: "media" }],
          },
        });
        await confirmUndo;
        context.apiPost = undoOriginalApiPost;
        const undoPost = undoPosts.find((entry) => entry.url === "/api/rename/undo");
        if (!undoPost) throw new Error("undo button flow did not post /api/rename/undo");
        if (undoPost.body.confirm_undo !== true) throw new Error("undo post omitted confirm_undo=true: " + JSON.stringify(undoPost.body));
        if (undoPost.body.undo_manifest !== "C:/State/Rename/undo.json") throw new Error("undo post used wrong manifest: " + JSON.stringify(undoPost.body));
        requireContains("undo result summary", text("rename-apply-status-summary"), ["2 restored / 0 skipped"]);
        requireContains("undo status completed", text("rename-undo-status"), ["Undo completed"]);
        requireContains("undo progress result", text("rename-apply-progress-bars"), ["Rename undo", "complete", "100%", "2 restored / 0 skipped / 0 failed"]);
        if (!undoButton.disabled) throw new Error("undo button was not disabled after successful undo");

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
        context.renderRenamePreview({ rows: largeRows, preview_fingerprint: "rename-preview-fp", counts: { total: 260, ready: 260 }, confidence_counts: { high: 260 }, preview_source_counts: { auto_tv_heuristic: 260 }, change_kind_counts: { rename: 260 } });
        requireContains("large preview status", text("rename-status"), ["260 ready", "250 shown / 260 preview rows"]);
        requireContains("large preview legend", text("rename-table-legend"), ["Display cap: 250 shown / 260 preview rows rendered", "not visible in the table"]);
        context.mediaPipelineRenameView.checkApplicableRenameRows();
        requireContains("large checked count", text("rename-selected-count"), ["260 checked"]);
        requireContains("checked apply button", text("rename-apply-button"), ["Apply 260 checked renames"]);
        requireContains("large selection audit", text("rename-selection-audit"), ["Rows in scope: 260", "Rendered rows: 250 of 260", "checked scope may include rows not currently rendered"]);
        requireContains("large readiness cells", readinessCellText(), ["Render cap visibility", "250 of 260 preview row(s) are rendered", "unrendered backend preview rows"]);

        const blockedExisting = { ...first, status: "blocked", errors: ["destination already exists"], warnings: [] };
        context.renderRenamePreview({ rows: [blockedExisting], preview_fingerprint: "rename-preview-fp", counts: { total: 1, blocked: 1 }, confidence_counts: { blocked: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { blocked: 1 } });
        requireContains("blocked status cell reason", previewCellText(), ["Blocked: destination already exists"]);

        const duplicateA = { ...first, source: "C:/TV/S02/E01.mkv", source_name: "E01.mkv" };
        const duplicateB = { ...first, source: "C:/TV/S02/E02.mkv", source_name: "E02.mkv" };
        setValue("rename-paths", "C:/TV/S02/E01.mkv\nC:/TV/S02/E02.mkv");
        context.renderRenamePreview({ rows: [duplicateA, duplicateB], preview_fingerprint: "rename-preview-fp", counts: { total: 2, ready: 2 }, confidence_counts: { high: 2 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
        context.mediaPipelineRenameView.checkApplicableRenameRows();
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
