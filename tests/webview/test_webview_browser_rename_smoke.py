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


def _browser_rename_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function browserRenameScript() {
          return `
          (async () => {
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function setValue(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function setChecked(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing checkbox " + id);
              node.checked = Boolean(value);
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function setCheckedBySelector(selector, value) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing checkbox selector " + selector);
              node.checked = Boolean(value);
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireTextAbsent(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (actual.includes(fragment)) throw new Error(id + " unexpectedly included " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function click(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            function requireRenameScrollPreservedOnSelection(fragment) {
              const row = Array.from(document.querySelectorAll('#rename-rows tr[data-selectable-row="true"]'))
                .find((candidate) => (candidate.textContent || "").includes(fragment));
              if (!row) throw new Error("rename table missing row containing " + fragment);
              const wrap = row.closest(".table-wrap");
              if (!wrap) throw new Error("missing rename table scroll wrapper");
              wrap.style.height = "220px";
              wrap.style.maxHeight = "220px";
              wrap.style.overflow = "auto";
              wrap.scrollTop = wrap.scrollHeight;
              const before = wrap.scrollTop;
              if (before <= 0) throw new Error("rename table did not become scrollable");
              row.click();
              const after = wrap.scrollTop;
              if (after < Math.max(1, before - 3)) {
                throw new Error("rename table scroll reset after row selection: before=" + before + " after=" + after);
              }
            }
            function readinessCells() {
              return Array.from(document.querySelectorAll("#rename-apply-readiness-rows td")).map((cell) => cell.textContent || "").join("\\n");
            }
            function outcomeCells() {
              return Array.from(document.querySelectorAll("#rename-apply-outcome-rows td")).map((cell) => cell.textContent || "").join("\\n");
            }
            function previewCells() {
              return Array.from(document.querySelectorAll("#rename-rows td")).map((cell) => cell.textContent || "").join("\\n");
            }
            function requireReadiness(fragments) {
              const actual = readinessCells();
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error("readiness table missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            [
              "showPage",
              "renderRenamePreview",
              "selectRenameRow",
              "checkApplicableRenameRows",
              "applySelectedRename",
              "renameApplyReadinessRows",
              "renameApplyScopeBlockers",
              "renderRenamePipelineHandoff",
              "renderRenameApplyResult",
              "renameApplyOutcomeRows",
              "renameApplyProgressBars",
            ].forEach(requireFunction);
            if (typeof window.mediaPipelineSettingsView?.saveSettingsPatch !== "function") {
              throw new Error("missing settings save namespace function");
            }
            if (typeof window.mediaPipelineRenameView?.renameOpenResultDialog !== "function") {
              throw new Error("missing rename result dialog namespace function");
            }
            window.getLastSettings = () => ({
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

            window.showPage("settings");
            localStorage.removeItem("mediapipeline.rename.cleaningFilters.v1");
            setValue("settings-patch-json", "{}");
            setValue("settings-rename-filter-release-groups", "rarbg, yify, codexrg, neonoir");
            setValue("settings-rename-filter-languages-subs-dubs", "eng, ita, sub, dub, multisub");
            setCheckedBySelector('[data-rename-movie-filter="release_groups"]', false);
            click("#settings-save-header-save-button", "main settings save");
            await new Promise((resolve) => setTimeout(resolve, 150));
            requireText("settings-patch-detail", ["Rename filter draft retained in this browser", "Stage Rename Filter Patch", "Preview Patch and Save Settings"]);
            const storedRenameFilters = JSON.parse(localStorage.getItem("mediapipeline.rename.cleaningFilters.v1") || "null");
            if (Object.prototype.hasOwnProperty.call(storedRenameFilters || {}, "use_editable_filters")) {
              throw new Error("removed editable rename filter toggle was saved");
            }
            if (storedRenameFilters?.movie_filter_options?.release_groups !== false) {
              throw new Error("release-group checkbox state was not saved: " + JSON.stringify(storedRenameFilters?.movie_filter_options));
            }
            if (!String(storedRenameFilters?.movie_filter_terms_text?.release_groups || "").includes("codexrg")) {
              throw new Error("release-group terms were not saved: " + JSON.stringify(storedRenameFilters?.movie_filter_terms_text));
            }
            if (!String(storedRenameFilters?.movie_filter_terms_text?.languages_subs_dubs || "").includes("multisub")) {
              throw new Error("language/sub-dub terms were not saved: " + JSON.stringify(storedRenameFilters?.movie_filter_terms_text));
            }
            setValue("settings-rename-filter-release-groups", "temporary lost value");
            setCheckedBySelector('[data-rename-movie-filter="release_groups"]', true);
            window.mediaPipelineRenameView.initRenameCleaningFilterEditorEvents();
            if (document.querySelector('[data-rename-movie-filter="release_groups"]').checked) {
              throw new Error("release-group checkbox state was not restored");
            }
            if (!byId("settings-rename-filter-release-groups").value.includes("codexrg")) {
              throw new Error("release-group terms did not reload from browser storage: " + byId("settings-rename-filter-release-groups").value);
            }
            requireText("settings-rename-cleaning-filter-summary", ["Unsaved cleaning filter draft loaded from browser storage", "release groups=4", "Browser storage is local draft recovery only"]);
            const savedReleaseGroups = byId("settings-rename-filter-release-groups").value;

            const originalSettingsApiPost = window.apiPost;
            const settingsPosts = [];
            const settingsConfirmMessages = [];
            window.apiPost = async (url, body) => {
              if (String(url || "").startsWith("/api/settings/")) {
                settingsPosts.push({ url: String(url || ""), body: body || {} });
                if (String(url || "") === "/api/settings/preview-patch") {
                  return {
                    command: "settings.preview_patch",
                    ok: true,
                    message: "Preview ready.",
                    data: {
                      writes_config: false,
                      changed_keys: Object.keys(body?.changes || {}),
                      removed_keys: [],
                    },
                  };
                }
                if (String(url || "") === "/api/settings/save-patch") {
                  return {
                    command: "settings.save_patch",
                    ok: true,
                    message: "Settings saved.",
                    data: {
                      writes_config: true,
                      changed_keys: Object.keys(body?.changes || {}),
                      removed_keys: [],
                      config_path: "C:/Config/Local.psd1",
                      backup_path: "C:/Config/Local.psd1.bak",
                      reloaded: false,
                    },
                  };
                }
              }
              return originalSettingsApiPost(url, body);
            };
            const originalConfirm = window.confirm;
            window.confirm = (message) => {
              settingsConfirmMessages.push(String(message || ""));
              return true;
            };
            click("#settings-rename-cleaning-filters-save-button", "stage rename filters");
            await new Promise((resolve) => setTimeout(resolve, 250));
            if (settingsPosts.length !== 0) {
              throw new Error("rename filter staging called backend settings routes: " + JSON.stringify(settingsPosts));
            }
            const stagedChanges = JSON.parse(byId("settings-patch-json").value || "{}");
            if (!stagedChanges.RenameMovieFilterOptions || !stagedChanges.RenameMovieFilterTerms || !stagedChanges.RenameMovieRemoveTerms) {
              throw new Error("rename filter staging did not write persisted setting keys to Settings Changes JSON: " + JSON.stringify(stagedChanges));
            }
            if (!String((stagedChanges.RenameMovieFilterTerms.release_groups || []).join(",")).includes("codexrg")) {
              throw new Error("rename filter staging omitted edited release group terms: " + JSON.stringify(stagedChanges.RenameMovieFilterTerms));
            }
            if (!String((stagedChanges.RenameMovieFilterTerms.languages_subs_dubs || []).join(",")).includes("multisub")) {
              throw new Error("rename filter staging omitted language/sub-dub terms: " + JSON.stringify(stagedChanges.RenameMovieFilterTerms));
            }
            if (localStorage.getItem("mediapipeline.rename.cleaningFilters.v1") === null) {
              throw new Error("rename filter staging should retain browser draft storage");
            }
            requireText("settings-rename-cleaning-filter-summary", ["Rename cleaning filters staged into Settings Changes JSON.", "Next step: run Preview Patch, then Save Settings from Settings.", "Browser storage is local draft recovery only"]);
            click("#settings-save-header-preview-button", "preview staged rename filter patch");
            await new Promise((resolve) => setTimeout(resolve, 250));
            click("#settings-save-header-save-button", "save staged rename filter patch");
            await new Promise((resolve) => setTimeout(resolve, 250));
            if (settingsPosts.length !== 2 || settingsPosts[0].url !== "/api/settings/preview-patch" || settingsPosts[1].url !== "/api/settings/save-patch") {
              throw new Error("staged rename filters were not saved through settings preview/save routes: " + JSON.stringify(settingsPosts));
            }
            const saveChanges = settingsPosts[1].body?.changes || {};
            if (!saveChanges.RenameMovieFilterOptions || !saveChanges.RenameMovieFilterTerms || !saveChanges.RenameMovieRemoveTerms || settingsPosts[1].body?.confirm_save !== true) {
              throw new Error("settings save did not submit rename filter persisted keys with confirmation: " + JSON.stringify(settingsPosts[1]));
            }
            if (!settingsConfirmMessages.join("\\n").includes("Save 3 setting patch key(s) to the active PSD1 config?")) {
              throw new Error("settings save confirmation did not run for staged rename filters: " + JSON.stringify(settingsConfirmMessages));
            }
            requireText("settings-patch-status", ["Saved"]);
            window.confirm = originalConfirm;
            window.apiPost = originalSettingsApiPost;

            setCheckedBySelector('[data-rename-movie-filter="release_groups"]', true);
            setValue("settings-rename-preview-input", "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv");
            click("#settings-rename-preview-button", "backend filename cleaner test");
            await new Promise((resolve) => setTimeout(resolve, 600));
            requireText("settings-rename-preview-output", ["Together (2025).mkv", "Movie filter policy: staged.", "Source: backend clean_pipeline_movie_name."]);
            requireText("settings-rename-preview-status", ["Backend clean preview complete"]);

            window.showPage("rename");
            requireText("rename-browse-folder-button", ["Add files from folder"]);
            requireText("rename-clear-paths-button", ["Clear staged paths"]);
            requireText("rename-add-path-button", ["Add manual path"]);
            requireText("rename-confirm-title", ["Confirm filesystem rename"]);
            requireText("rename-confirm-mutation-warning", ["This will rename files on disk", "Review every source and destination path"]);
            requireText("rename-confirm-apply-button", ["Apply filesystem rename"]);
            const originalApiPost = window.apiPost;
            const browsePosts = [];
            window.apiPost = async (url, body) => {
              if (String(url || "") === "/api/rename/browse") {
                browsePosts.push({ url: String(url || ""), body: body || {} });
                return {
                  command: "rename.browse",
                  ok: true,
                  message: "Windows file browser selected 2 files.",
                  data: {
                    paths: ["C:/Browse/Selected Rename A.mkv", "C:/Browse/Selected Rename B.mkv"],
                    selection_mode: "files",
                    canceled: false,
                    path_count: 2,
                  },
                };
              }
              return originalApiPost(url, body);
            };
            click("#rename-browse-files-button", "browse rename files");
            await new Promise((resolve) => setTimeout(resolve, 100));
            requireText("rename-file-source-summary", ["Windows file browser added 2 paths", "Source paths staged: 2", "Origins: browse=2", "C:/Browse/Selected Rename A.mkv"]);
            if (browsePosts.length !== 1 || browsePosts[0].body.selection_mode !== "files") {
              throw new Error("rename browse did not submit expected file-browser request: " + JSON.stringify(browsePosts));
            }
            window.apiPost = originalApiPost;
            click("#rename-clear-paths-button", "clear browsed rename paths");
            setValue("rename-add-path-input", "C:/Manual/Typed Rename Source.mkv");
            click("#rename-add-path-button", "add typed rename path");
            requireText("rename-file-source-summary", ["Manual path added 1 path", "Source paths staged: 1", "Origins: manual=1"]);
            click("#rename-clear-paths-button", "clear typed rename paths");
            requireText("rename-file-source-summary", ["Cleared staged rename paths.", "No source paths staged."]);
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
              source_parent: "C:/TV/Season 02",
              destination: "C:/TV/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
              destination_parent: "C:/TV/Season 02",
              target_name: "Serial Experiments Lain - S02E01 - Weird.mkv",
              pipeline_guess: "Serial Experiments Lain - S02E01 - Weird.mkv",
              status: "ready",
              confidence: "high",
              preview_source: "auto_tv_heuristic",
              confidence_reasons: ["folder season 02", "episode token E01"],
              change_kind: "rename",
              sidecar_count: 0,
              destination_exists: false,
              matches_target: false,
              warnings: [],
              errors: [],
            };
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [first], counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
            requireText("rename-apply-button", ["Apply all 1 safe rename"]);
            requireText("rename-apply-status-hint", ["No rows checked", "all safe rows"]);
            setValue("rename-show", "Serial Experiments Lain Changed");
            window.mediaPipelineRenameView.syncRenameCommandButtons();
            requireText("rename-apply-button", ["Preview out of date"]);
            requireText("rename-apply-status-hint", ["Preview out of date", "Run Preview again"]);
            if (!byId("rename-apply-button").disabled) {
              throw new Error("stale preview did not disable Apply");
            }
            setValue("rename-show", "Serial Experiments Lain");
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [first], counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
            click('#rename-rows tr[data-selectable-row="true"]', "rename preview row");
            requireText("rename-detail", ["Serial Experiments Lain - S02E01 - Weird.mkv", "Confidence reason(s): folder season 02 | episode token E01"]);
            requireText("rename-apply-readiness-status", ["Ready"]);
            requireReadiness(["Apply scope", "all applicable preview rows", "Mutation boundary", "/api/rename/apply"]);
            requireText("rename-batch-safety", ["Apply scope", "if none are checked", "all applicable safe preview rows"]);
            requireTextAbsent("rename-batch-safety", ["selected detail row"]);
            const posted = [];
            window.apiPost = async (url, body) => {
              posted.push({ url: String(url || ""), body: JSON.parse(JSON.stringify(body || {})) });
              return { ok: false, command: "rename.apply", message: "mocked browser rename apply" };
            };
            const second = {
              ...first,
              source: "C:/TV/Season 02/Serial Experiments Lain E02 Girls.mkv",
              source_name: "Serial Experiments Lain E02 Girls.mkv",
              destination: "C:/TV/Season 02/Serial Experiments Lain - S02E02 - Girls.mkv",
              target_name: "Serial Experiments Lain - S02E02 - Girls.mkv",
              pipeline_guess: "Serial Experiments Lain - S02E02 - Girls.mkv",
            };
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [first, second], counts: { total: 2, ready: 2 }, confidence_counts: { high: 2 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
            click('#rename-rows tr[data-selectable-row="true"]', "first rename preview row");
            requireText("rename-apply-button", ["Apply all 2 safe renames"]);
            click("#rename-apply-button", "apply all safe rename rows");
            await new Promise((resolve) => setTimeout(resolve, 100));
            if (!byId("rename-confirm-dialog").open) {
              throw new Error("rename confirm dialog did not open for unchecked all-safe scope");
            }
            requireText("rename-confirm-count", ["Renaming 2 file(s)."]);
            requireText("rename-confirm-warning", ["No rows were checked", "all safe rows"]);
            click("#rename-confirm-apply-button", "confirm all-safe rename apply");
            await new Promise((resolve) => setTimeout(resolve, 250));
            const applyPost = posted.find((entry) => entry.url === "/api/rename/apply");
            if (!applyPost) throw new Error("unchecked all-safe rename apply did not post /api/rename/apply");
            if (JSON.stringify(applyPost.body.selected_sources || []) !== JSON.stringify([first.source, second.source])) {
              throw new Error("unchecked apply selected_sources did not match all applicable rows: " + JSON.stringify(applyPost.body));
            }
            if (applyPost.body.confirm_apply !== true) throw new Error("rename apply post omitted confirm_apply=true");
            if (byId("rename-result-dialog").open) byId("rename-result-dialog").close();
            requireText("rename-pipeline-handoff-status", ["Ready"]);
            requireText("rename-pipeline-handoff", ["Rename-to-pipeline handoff", "Saved routing profile: plex_direct_stream", "output container: mkv", "renaming changes filenames only"]);
            window.mediaPipelineRenameView.renderRenameApplyResult({
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
                rename_progress: {
                  schema_version: "desktop_rename_apply_progress.v1",
                  status: "complete",
                  selected: 1,
                  renamed: 1,
                  unchanged: 0,
                  sidecars: 1,
                  media_operations: 1,
                  sidecar_operations: 1,
                  updated_at: "2026-05-17T12:00:00",
                  progress_bars: [{
                    id: "rename_apply",
                    label: "Rename apply",
                    mode: "determinate",
                    percent: 100,
                    status: "complete",
                    detail: "1 renamed / 1 planned; unchanged 0; media ops 1; sidecar ops 1; sidecars 1",
                    source: "rename.apply",
                    updated_at: "2026-05-17T12:00:00",
                    stale: false,
                  }],
                },
                rows: [{ source: first.source, destination: first.destination, status: "renamed", sidecar_count: 1 }],
              },
              request: { mode: "tv", confirm_apply: true, selected_sources: [first.source] },
            });
            requireText("rename-apply-outcome-status", ["Applied"]);
            requireText("rename-apply-outcome-summary", ["Backend rename apply outcome review", "selected=1", "Undo manifest: C:/State/Rename/undo.json", "read-only"]);
            requireText("rename-apply-progress-bars", ["Rename apply", "complete", "100%", "1 renamed / 1 planned", "source: rename.apply"]);
            window.mediaPipelineRenameView.renameOpenResultDialog({
              ok: true,
              message: "Applied selected rename.",
              data: { applied_count: 1, undo_manifest: "C:/State/Rename/undo.json", rows: [{ status: "renamed" }] },
            });
            requireText("rename-result-summary", ["Applied selected rename.", "Undo manifest: C:/State/Rename/undo.json"]);
            byId("rename-result-dialog").close();
            for (const fragment of ["Backend result", "Selected scope", "Sidecar operations", "Undo / rollback evidence", "Mutation boundary"]) {
              if (!outcomeCells().includes(fragment)) throw new Error("outcome table missing " + fragment + "\\nActual:\\n" + outcomeCells());
            }
            const appliedOutcomeStatus = text("rename-apply-outcome-status");

            posted.length = 0;
            window.apiPost = async (url) => {
              posted.push({ url: String(url || ""), body: {} });
              return { ok: false, message: "browser smoke should not post rename apply" };
            };

            const largeRows = Array.from({ length: 260 }, (_value, index) => {
              const episode = String(index + 1).padStart(2, "0");
              return {
                ...first,
                source: \`C:/TV/S02/Serial Experiments Lain E\${episode}.mkv\`,
                source_name: \`Serial Experiments Lain E\${episode}.mkv\`,
                destination: \`C:/TV/S02/Serial Experiments Lain - S02E\${episode}.mkv\`,
                target_name: \`Serial Experiments Lain - S02E\${episode}.mkv\`,
                pipeline_guess: \`Serial Experiments Lain - S02E\${episode}.mkv\`,
              };
            });
            setValue("rename-paths", largeRows.map((row) => row.source).join("\\n"));
            window.mediaPipelineRenameView.renderRenamePreview({ rows: largeRows, counts: { total: 260, ready: 260 }, confidence_counts: { high: 260 }, preview_source_counts: { auto_tv_heuristic: 260 }, change_kind_counts: { rename: 260 } });
            requireText("rename-status", ["260 ready", "250 shown / 260 preview rows"]);
            requireText("rename-table-legend", ["Display cap: 250 shown / 260 preview rows rendered", "not visible in the table"]);
            requireRenameScrollPreservedOnSelection("S02E240");
            requireText("rename-detail", ["Serial Experiments Lain - S02E240.mkv"]);
            click("#rename-check-applicable-button", "check all applicable large rename rows");
            requireText("rename-selected-count", ["260 checked"]);
            requireText("rename-apply-button", ["Apply 260 checked renames"]);
            requireText("rename-selection-audit", ["Rows in scope: 260", "Rendered rows: 250 of 260", "checked scope may include rows not currently rendered"]);
            requireReadiness(["Render cap visibility", "250 of 260 preview row(s) are rendered", "unrendered backend preview rows"]);

            const blockedExisting = { ...first, status: "blocked", errors: ["destination already exists"], warnings: [] };
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [blockedExisting], counts: { total: 1, blocked: 1 }, confidence_counts: { blocked: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { blocked: 1 } });
            if (!previewCells().includes("Blocked: destination already exists")) {
              throw new Error("preview table did not expose blocked destination reason\\nActual:\\n" + previewCells());
            }

            const duplicateA = { ...first, source: "C:/TV/S02/E01.mkv", source_name: "E01.mkv" };
            const duplicateB = { ...first, source: "C:/TV/S02/E02.mkv", source_name: "E02.mkv" };
            setValue("rename-paths", "C:/TV/S02/E01.mkv\\nC:/TV/S02/E02.mkv");
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [duplicateA, duplicateB], counts: { total: 2, ready: 2 }, confidence_counts: { high: 2 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
            click("#rename-check-applicable-button", "check applicable rename rows");
            requireText("rename-selected-count", ["2 checked"]);
            requireText("rename-apply-readiness-status", ["Blocked"]);
            requireReadiness(["Duplicate destinations", "duplicate target", "selected_sources"]);
            requireText("rename-apply-button", ["Resolve blockers before apply"]);
            requireText("rename-apply-status-hint", ["Blocked by readiness", "duplicate destination target"]);
            if (!byId("rename-apply-button").disabled) {
              throw new Error("duplicate-target scope did not disable Apply");
            }
            click("#rename-apply-button", "apply rename");
            await new Promise((resolve) => setTimeout(resolve, 100));
            if (posted.some((entry) => entry.url.includes("rename") && entry.url.includes("apply"))) {
              throw new Error("blocked duplicate-target scope still posted a rename apply request");
            }
            return {
              ok: true,
              readyStatus: "Ready",
              duplicateStatus: text("rename-apply-readiness-status"),
              blockerHint: text("rename-apply-status-hint"),
              applyDisabled: byId("rename-apply-button").disabled,
              appliedOutcomeStatus,
              outcomeStatus: text("rename-apply-outcome-status"),
              detail: text("rename-detail"),
              browsePosts,
              posted,
              savedReleaseGroups,
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
                expression: `Boolean(document.getElementById("rename-apply-readiness-rows") && typeof window.showPage === "function" && typeof window.mediaPipelineRenameView.renderRenamePreview === "function" && typeof window.mediaPipelineRenameView.applySelectedRename === "function" && typeof window.mediaPipelineSettingsView?.saveSettingsPatch === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("rename-apply-readiness-rows") && typeof window.showPage === "function" && typeof window.mediaPipelineRenameView.renderRenamePreview === "function" && typeof window.mediaPipelineRenameView.applySelectedRename === "function" && typeof window.mediaPipelineSettingsView?.saveSettingsPatch === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Rename WebView globals or readiness DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: browserRenameScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              const exception = details.exception || {};
              throw new Error(exception.description || exception.value || details.text || "browser evaluation failed");
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


def _run_browser_rename_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView rename smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-rename-payload.json"
        runner_path = tmp / "browser-rename-runner.cjs"
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
        runner_path.write_text(_browser_rename_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView rename smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=45,
        )


class WebViewBrowserRenameSmoke(unittest.TestCase):
    def test_real_browser_renders_rename_readiness_and_blocks_duplicate_apply(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView rename smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-rename-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_rename_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["duplicateStatus"], "Blocked")
        self.assertEqual(browser_result["browsePosts"][0]["body"]["selection_mode"], "files")
        self.assertEqual(browser_result["appliedOutcomeStatus"], "Applied")
        self.assertEqual(browser_result["outcomeStatus"], "Applied")
        self.assertIn("codexrg", browser_result["savedReleaseGroups"])
        self.assertIn("neonoir", browser_result["savedReleaseGroups"].lower())
        self.assertTrue(browser_result["applyDisabled"])
        self.assertIn("duplicate destination target", browser_result["blockerHint"])
        self.assertEqual(browser_result["posted"], [])


if __name__ == "__main__":
    unittest.main()
