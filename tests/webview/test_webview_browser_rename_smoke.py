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
            async function waitFor(condition, label, timeoutMs = 3000) {
              const deadline = Date.now() + timeoutMs;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (condition()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 50));
              }
              throw new Error("timed out waiting for " + label + (lastError ? ": " + lastError.message : ""));
            }
            function requireNoVisibleProseSummary(id) {
              const node = byId(id);
              if (!node) throw new Error("missing hidden summary " + id);
              const previous = node.previousElementSibling;
              if (previous?.classList?.contains("prose-box-summary-strip")) {
                throw new Error(id + " rendered a visible prose summary strip");
              }
              if (!node.hidden) throw new Error(id + " should stay hidden");
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
              "checkAllRenameRows",
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
            setValue("settings-rename-tv-filter-release-groups", "chotab, ttga, codextv");
            setCheckedBySelector('[data-rename-movie-filter="release_groups"]', false);
            setCheckedBySelector('[data-rename-tv-filter="release_groups"]', false);
            click("#settings-save-header-save-button", "main settings save");
            await waitFor(() => byId("settings-save-review-dialog").open, "initial save review dialog");
            requireText("settings-save-review-dialog", ["Review Settings Changes", "Save Settings"]);
            byId("settings-save-review-dialog").close("cancel");
            await waitFor(
              () => !byId("settings-save-review-dialog").open && !byId("settings-save-header-save-button").disabled,
              "initial save cancellation"
            );
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
            if (storedRenameFilters?.tv_filter_options?.release_groups !== false) {
              throw new Error("TV release-group checkbox state was not saved: " + JSON.stringify(storedRenameFilters?.tv_filter_options));
            }
            if (!String(storedRenameFilters?.tv_filter_terms_text?.release_groups || "").includes("codextv")) {
              throw new Error("TV release-group terms were not saved: " + JSON.stringify(storedRenameFilters?.tv_filter_terms_text));
            }
            setValue("settings-rename-filter-release-groups", "temporary lost value");
            setCheckedBySelector('[data-rename-movie-filter="release_groups"]', true);
            setValue("settings-rename-tv-filter-release-groups", "temporary tv lost value");
            setCheckedBySelector('[data-rename-tv-filter="release_groups"]', true);
            window.mediaPipelineRenameView.initRenameCleaningFilterEditorEvents();
            if (document.querySelector('[data-rename-movie-filter="release_groups"]').checked) {
              throw new Error("release-group checkbox state was not restored");
            }
            if (document.querySelector('[data-rename-tv-filter="release_groups"]').checked) {
              throw new Error("TV release-group checkbox state was not restored");
            }
            if (!byId("settings-rename-filter-release-groups").value.includes("codexrg")) {
              throw new Error("release-group terms did not reload from browser storage: " + byId("settings-rename-filter-release-groups").value);
            }
            if (!byId("settings-rename-tv-filter-release-groups").value.includes("codextv")) {
              throw new Error("TV release-group terms did not reload from browser storage: " + byId("settings-rename-tv-filter-release-groups").value);
            }
            requireText("settings-rename-cleaning-filter-summary", ["Unsaved cleaning filter draft loaded from browser storage", "release groups=4", "Browser storage is local draft recovery only"]);
            requireNoVisibleProseSummary("settings-rename-cleaning-filter-summary");
            const savedReleaseGroups = byId("settings-rename-filter-release-groups").value;

            function cloneValue(value) {
              return JSON.parse(JSON.stringify(value));
            }
            function currentRenameReviewValue(key, nextValue) {
              const current = cloneValue(nextValue);
              if (key === "RenameMovieFilterOptions" || key === "RenameTVFilterOptions") {
                current.release_groups = true;
                return current;
              }
              if (key === "RenameMovieFilterTerms") {
                current.release_groups = ["rarbg", "yify"];
                current.languages_subs_dubs = ["eng", "ita", "sub", "dub"];
                return current;
              }
              if (key === "RenameTVFilterTerms") {
                current.release_groups = ["chotab", "ttga"];
                return current;
              }
              return current;
            }
            const originalSettingsApiPost = window.apiPost;
            const settingsPosts = [];
            window.apiPost = async (url, body) => {
              if (String(url || "").startsWith("/api/settings/")) {
                settingsPosts.push({ url: String(url || ""), body: body || {} });
                if (String(url || "") === "/api/settings/preview-patch") {
                  const changedKeys = Object.keys(body?.changes || {});
                  return {
                    command: "settings.preview_patch",
                    ok: true,
                    message: "Settings patch preview produced backend-confirmed changes.",
                    data: {
                      writes_config: false,
                      changed_keys: changedKeys,
                      removed_keys: [],
                      review_entries_schema_version: "desktop_settings_patch_review_entries.v1",
                      review_entries: changedKeys.map((key) => ({
                        key,
                        status: "changed",
                        source: "submitted",
                        current_exists: true,
                        new_exists: true,
                        current_value: currentRenameReviewValue(key, body?.changes?.[key]),
                        new_value: body?.changes?.[key],
                      })),
                      review_confirmation: {
                        schema_version: "desktop_settings_save_review_confirmation.v1",
                        preview_id: "rename-smoke-preview",
                        request_digest: "request",
                        base_config_digest: "base",
                        candidate_config_digest: "candidate",
                        review_entries_digest: "review",
                        changed_keys: changedKeys,
                        removed_keys: [],
                      },
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
            const renameFilterSavePromise = window.mediaPipelineSettingsView.saveSettingsPatch();
            await waitFor(
              () => settingsPosts.filter((entry) => entry.url === "/api/settings/preview-patch").length === 1,
              "settings save preview before confirmation"
            );
            const previewPostsBeforeConfirm = settingsPosts.filter((entry) => entry.url === "/api/settings/preview-patch");
            const savePostsBeforeConfirm = settingsPosts.filter((entry) => entry.url === "/api/settings/save-patch");
            if (previewPostsBeforeConfirm.length !== 1 || savePostsBeforeConfirm.length !== 0) {
              throw new Error("settings save review did not limit pre-confirmation backend work to one preview: " + JSON.stringify(settingsPosts));
            }
            const stagedChanges = JSON.parse(byId("settings-patch-json").value || "{}");
            if (!stagedChanges.RenameMovieFilterOptions || !stagedChanges.RenameMovieFilterTerms || !stagedChanges.RenameMovieRemoveTerms || !stagedChanges.RenameTVFilterOptions || !stagedChanges.RenameTVFilterTerms || !stagedChanges.RenameTVRemoveTerms) {
              throw new Error("settings save review did not write rename filter persisted setting keys to Settings Changes JSON: " + JSON.stringify(stagedChanges));
            }
            if (!String((stagedChanges.RenameMovieFilterTerms.release_groups || []).join(",")).includes("codexrg")) {
              throw new Error("settings save review omitted edited release group terms: " + JSON.stringify(stagedChanges.RenameMovieFilterTerms));
            }
            if (!String((stagedChanges.RenameMovieFilterTerms.languages_subs_dubs || []).join(",")).includes("multisub")) {
              throw new Error("settings save review omitted language/sub-dub terms: " + JSON.stringify(stagedChanges.RenameMovieFilterTerms));
            }
            if (!String((stagedChanges.RenameTVFilterTerms.release_groups || []).join(",")).includes("codextv")) {
              throw new Error("settings save review omitted TV release group terms: " + JSON.stringify(stagedChanges.RenameTVFilterTerms));
            }
            if (localStorage.getItem("mediapipeline.rename.cleaningFilters.v1") === null) {
              throw new Error("settings save review should retain browser draft storage");
            }
            requireText("settings-rename-cleaning-filter-summary", ["Rename filters are included in the current Save Settings review.", "Next step: press Save Settings.", "Browser storage is local draft recovery only"]);
            requireNoVisibleProseSummary("settings-rename-cleaning-filter-summary");
            requireText("settings-save-review-dialog", ["Review Settings Changes", "RenameMovieFilterOptions", "RenameMovieFilterTerms", "RenameMovieRemoveTerms", "RenameTVFilterOptions", "RenameTVFilterTerms", "RenameTVRemoveTerms"]);
            requireText("settings-save-review-dialog", ["Changed toggles: release groups: on -> off", "Added terms:", "codexrg", "neonoir", "multisub", "codextv", "Unchanged terms hidden"]);
            requireTextAbsent("settings-save-review-dialog", ["audio_channels", "atmos"]);
            byId("settings-save-review-dialog").close("confirm");
            await renameFilterSavePromise;
            await new Promise((resolve) => setTimeout(resolve, 250));
            const previewPost = settingsPosts.find((entry) => entry.url === "/api/settings/preview-patch");
            const savePost = settingsPosts.find((entry) => entry.url === "/api/settings/save-patch");
            if (settingsPosts.length !== 2 || !previewPost || !savePost) {
              throw new Error("rename filters were not previewed and saved through settings routes: " + JSON.stringify(settingsPosts));
            }
            const saveChanges = savePost.body?.changes || {};
            if (!saveChanges.RenameMovieFilterOptions || !saveChanges.RenameMovieFilterTerms || !saveChanges.RenameMovieRemoveTerms || !saveChanges.RenameTVFilterOptions || !saveChanges.RenameTVFilterTerms || !saveChanges.RenameTVRemoveTerms || savePost.body?.confirm_save !== true || !savePost.body?.review_confirmation?.preview_id) {
              throw new Error("settings save did not submit rename filter persisted keys with confirmation: " + JSON.stringify(savePost));
            }
            requireText("settings-patch-status", ["Saved"]);
            window.apiPost = originalSettingsApiPost;

            setCheckedBySelector('[data-rename-movie-filter="video_source"]', false);
            setCheckedBySelector('[data-rename-movie-filter="release_groups"]', true);
            setValue("settings-rename-workbench-mode", "movie");
            setValue("settings-rename-workbench-source-file", "Scary Movie 2026 1080p DCPRip x264-FS.mkv");
            setValue("settings-rename-workbench-expected-movie-title", "Scary Movie");
            setValue("settings-rename-workbench-expected-year", "2026");
            click("#settings-rename-workbench-test-button", "backend filename cleaner workbench test");
            await new Promise((resolve) => setTimeout(resolve, 600));
            requireText("settings-rename-workbench-output", ["Actual: Scary Movie 1080p DCPRip X264-FS (2026).mkv", "Expected: Scary Movie (2026).mkv", "Result: Needs review", "Source: backend rename cleaner"]);
            requireText("settings-rename-workbench-status", ["Needs review"]);
            requireText("settings-rename-workbench-suggestions", ["1080p", "DCPRip", "movie filter category is off"]);
            click("#settings-rename-workbench-stage-suggestions-button", "stage backend workbench suggestions");
            await new Promise((resolve) => setTimeout(resolve, 150));
            requireText("settings-rename-workbench-message", ["draft only", "Retest"]);
            click("#settings-rename-workbench-retest-button", "retest staged backend workbench suggestions");
            await new Promise((resolve) => setTimeout(resolve, 700));
            requireText("settings-rename-workbench-output", ["Actual: Scary Movie (2026).mkv", "Expected: Scary Movie (2026).mkv", "Result: Pass"]);
            requireText("settings-rename-workbench-message", ["Retest passed", "Save New Filters"]);
            if (byId("settings-rename-workbench-save-filters-button").disabled) {
              throw new Error("Save New Filters should be enabled after staged filters pass retest.");
            }
            const workbenchPatch = JSON.parse(byId("settings-patch-json").value || "{}");
            if (!workbenchPatch.RenameMovieFilterTerms || !String((workbenchPatch.RenameMovieFilterTerms.video_source || []).join(",")).toLowerCase().includes("dcprip")) {
              throw new Error("workbench retest did not prepare staged movie video/source term for Save Settings: " + JSON.stringify(workbenchPatch));
            }
            setValue("settings-rename-workbench-mode", "tv");
            setValue("settings-rename-workbench-source-folder", "The Web S01 1080p WEB-DL-codextv");
            setValue("settings-rename-workbench-source-file", "S01E01-Pilot.1080p.WEB-DL-codextv.mkv");
            setValue("settings-rename-workbench-expected-show", "The Web");
            setValue("settings-rename-workbench-expected-season", "1");
            setValue("settings-rename-workbench-expected-episode", "1");
            setValue("settings-rename-workbench-expected-episode-title", "Pilot");
            setCheckedBySelector('[data-rename-tv-filter="release_groups"]', true);
            click("#settings-rename-workbench-test-button", "backend TV filename cleaner workbench test");
            await new Promise((resolve) => setTimeout(resolve, 600));
            requireText("settings-rename-workbench-output", ["Actual: The Web - S01E01 - Pilot.mkv", "Expected: The Web - S01E01 - Pilot.mkv", "Result: Pass"]);

            window.showPage("rename");
            requireText("rename-browse-folder-button", ["Add files from folder"]);
            requireText("rename-clear-paths-button", ["Clear staged paths"]);
            requireText("rename-add-path-button", ["Add manual path"]);
            requireText("rename-confirm-title", ["Confirm filesystem rename"]);
            requireText("rename-confirm-mutation-warning", ["Backend rename.apply", "matching sidecars"]);
            requireText("rename-confirm-apply-button", ["Apply Renames"]);
            const originalApiPost = window.apiPost;
            const browsePosts = [];
            window.apiPost = async (url, body) => {
              if (String(url || "") === "/api/rename/browse") {
                browsePosts.push({ url: String(url || ""), body: body || {} });
                if (Array.isArray(body?.paths)) {
                  if (body.paths.some((path) => String(path).includes("Season 02"))) {
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
            requireText("rename-file-source-summary", ["Windows file browser added 2 paths", "Source paths staged: 2", "Media paths eligible for preview/apply: 2", "Origins: browse=2", "C:/Browse/Selected Rename A.mkv"]);
            if (browsePosts.length !== 1 || browsePosts[0].body.selection_mode !== "files") {
              throw new Error("rename browse did not submit expected file-browser request: " + JSON.stringify(browsePosts));
            }
            click("#rename-clear-paths-button", "clear browsed rename paths");
            setValue("rename-add-path-input", "C:/Manual/Typed Rename Source.mkv");
            click("#rename-add-path-button", "add typed rename path");
            requireText("rename-file-source-summary", ["Manual path added 1 path", "Source paths staged: 1", "Media paths eligible for preview/apply: 1", "Origins: manual=1"]);
            click("#rename-clear-paths-button", "clear typed rename paths");
            requireText("rename-file-source-summary", ["Cleared staged rename paths.", "No source paths staged."]);
            const tauriDropped = window.mediaPipelineRenameView.renameDroppedPathValuesFromBridgeDetail({
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
            if (window.mediaPipelineRenameView.renameDroppedPathFromFile({ name: "Ranma - S01E02.mkv" }) !== "") {
              throw new Error("bare browser File.name should not be accepted as a filesystem path");
            }
            await window.mediaPipelineRenameView.handleRenameDroppedPaths(tauriDropped, "Tauri drag and drop");
            requireText("rename-file-source-summary", ["Tauri drag and drop added 1 path", "Ignored 1 non-media path including 1 sidecar path", "Source paths staged: 1", "Media paths eligible for preview/apply: 1", "Origins: drop=1"]);
            const fileDropPost = browsePosts[browsePosts.length - 1];
            if (fileDropPost.body.selection_mode !== "folder_files" || !Array.isArray(fileDropPost.body.paths)) {
              throw new Error("rename file drop did not submit expected folder_files request: " + JSON.stringify(fileDropPost));
            }
            click("#rename-clear-paths-button", "clear dropped rename paths");
            await window.mediaPipelineRenameView.handleRenameDroppedPaths(["C:/Drop/Season 02"], "Drag and drop");
            requireText("rename-file-source-summary", ["Drag and drop added 2 paths", "Ignored 2 non-media paths including 2 sidecar paths", "Source paths staged: 2", "Media paths eligible for preview/apply: 2", "Origins: drop=2", "Ranma - S01E01.mkv"]);
            if (byId("rename-paths").value === "C:/Drop/Season 02" || byId("rename-paths").value.includes("C:/Drop/Season 02\\n")) {
              throw new Error("dropped folder path was staged instead of direct media children: " + byId("rename-paths").value);
            }
            click("#rename-clear-paths-button", "clear dropped folder rename paths");
            await window.mediaPipelineRenameView.handleRenameDroppedPaths(["Ranma - S01E02.mkv"], "Drag and drop");
            requireText("rename-file-source-summary", ["Drop did not expose full filesystem paths", "No source paths staged."]);
            window.apiPost = originalApiPost;
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
            setValue("rename-paths", [
              "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv",
              "C:/TV/Season 02/Serial Experiments Lain E01 Weird.pipeline.json",
            ].join("\\n"));
            window.mediaPipelineRenameView.renderRenameFileSourceSummary("Sidecar classification check.");
            requireText("rename-file-source-summary", ["Source paths staged: 2", "Media paths eligible for preview/apply: 1", "Ignored by preview/apply: 1 (1 sidecar"]);
            window.mediaPipelineRenameView.renderRenamePreview({
              rows: [first],
              preview_fingerprint: "rename-preview-fp",
              counts: { total: 1, ready: 1 },
              input_counts: { raw: 2, media: 1, ignored: 1, ignored_sidecar: 1 },
              confidence_counts: { high: 1 },
              preview_source_counts: { auto_tv_heuristic: 1 },
              change_kind_counts: { rename: 1 },
              warnings: ["Ignored 1 staged rename sidecar path(s); sidecars are attached to media rows automatically."],
            });
            requireText("rename-summary", ["Rows: 1", "Preview warnings: Ignored 1 staged rename sidecar path"]);
            requireTextAbsent("rename-rows", ["pipeline.json"]);
            setValue("rename-paths", "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv");
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [first], preview_fingerprint: "rename-preview-fp", counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
            requireText("rename-apply-button", ["Check rows before apply"]);
            requireText("rename-apply-status-hint", ["No rows checked", "Check Applicable"]);
            if (!byId("rename-apply-button").disabled) {
              throw new Error("unchecked rename apply button was not disabled");
            }
            click("#rename-check-applicable-button", "check first applicable rename row");
            requireText("rename-selected-count", ["1 checked"]);
            requireText("rename-apply-button", ["Apply 1 checked rename"]);
            setValue("rename-show", "Serial Experiments Lain Changed");
            window.mediaPipelineRenameView.syncRenameCommandButtons();
            requireText("rename-apply-button", ["Preview out of date"]);
            requireText("rename-apply-status-hint", ["Preview out of date", "Run Preview again"]);
            if (!byId("rename-apply-button").disabled) {
              throw new Error("stale preview did not disable Apply");
            }
            setValue("rename-show", "Serial Experiments Lain");
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [first], preview_fingerprint: "rename-preview-fp", counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
            click('#rename-rows tr[data-selectable-row="true"]', "rename preview row");
            requireText("rename-detail", ["Serial Experiments Lain - S02E01 - Weird.mkv", "Confidence reason(s): folder season 02 | episode token E01"]);
            requireText("rename-apply-readiness-status", ["Ready"]);
            requireReadiness(["Apply scope", "checked rows", "Mutation boundary", "/api/rename/apply"]);
            requireText("rename-batch-safety", ["Apply scope", "checked rows are required", "selected_sources"]);
            requireTextAbsent("rename-batch-safety", ["selected detail row"]);
            const posted = [];
            let resolveApplyPost = null;
            const delayedApplyPost = new Promise((resolve) => {
              resolveApplyPost = resolve;
            });
            window.apiPost = async (url, body) => {
              posted.push({ url: String(url || ""), body: JSON.parse(JSON.stringify(body || {})) });
              if (String(url || "") === "/api/rename/apply") return delayedApplyPost;
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
            const warningSecond = {
              ...second,
              status: "warning",
              confidence: "review",
              warnings: ["Manual review needed"],
            };
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [first, warningSecond], preview_fingerprint: "rename-preview-fp", counts: { total: 2, ready: 1, warning: 1 }, confidence_counts: { high: 1, review: 1 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
            window.mediaPipelineRenameView.clearCheckedRenameRows();
            click('#rename-rows tr[data-selectable-row="true"] input[type="checkbox"]', "first rename checkbox");
            requireText("rename-selected-count", ["1 checked"]);
            requireText("rename-apply-button", ["Apply 1 checked rename"]);
            click('#rename-rows tr[data-selectable-row="true"] input[type="checkbox"]', "first rename checkbox uncheck");
            requireText("rename-selected-count", ["0 checked"]);
            click('#rename-rows tr[data-selectable-row="true"] td:first-child', "first rename checkbox cell");
            requireText("rename-selected-count", ["1 checked"]);
            click("#rename-clear-checks-button", "clear manually checked rename row");
            click('#rename-rows tr[data-selectable-row="true"]', "first rename preview row");
            click("#rename-clear-checks-button", "clear checked rename rows");
            requireText("rename-apply-button", ["Check rows before apply"]);
            if (!byId("rename-apply-button").disabled) {
              throw new Error("unchecked two-row rename apply button was not disabled");
            }
            click("#rename-check-applicable-button", "check applicable rename rows");
            requireText("rename-selected-count", ["1 checked"]);
            requireText("rename-apply-status-hint", ["Checked 1 ready/match row", "warning=1"]);
            click("#rename-clear-checks-button", "clear checked rename rows");
            click("#rename-check-all-button", "check all selectable rename rows");
            requireText("rename-selected-count", ["2 checked"]);
            requireText("rename-apply-status-hint", ["Checked 2 selectable rows", "skipped 0"]);
            requireText("rename-apply-button", ["Apply 2 checked renames"]);
            click("#rename-apply-button", "apply checked rename rows");
            await new Promise((resolve) => setTimeout(resolve, 100));
            if (!byId("rename-confirm-dialog").open) {
              throw new Error("rename confirm dialog did not open for checked scope");
            }
            requireText("rename-confirm-count", ["Renaming 2 checked media files."]);
            requireText("rename-confirm-apply-button", ["Apply 2 Renames"]);
            requireText("rename-confirm-list", ["2 media files ready", "0 matching sidecars will move", "Sequence", "Serial Experiments Lain - S02E01 - Weird.mkv -> Serial Experiments Lain - S02E02 - Girls.mkv", "0 blocked", "0 conflicts", "0 existing destinations", "Show details"]);
            requireTextAbsent("rename-confirm-list", ["C:/TV/Season 02", "authority=", "status=ready"]);
            const confirmDetails = document.querySelector(".rename-confirm-details");
            if (!confirmDetails || confirmDetails.open) throw new Error("rename confirm details should exist and be collapsed by default");
            const readyBadge = document.querySelector(".rename-confirm-detail-row-ready .rename-confirm-status-badge");
            if (!readyBadge || readyBadge.getAttribute("aria-label") !== "Ready" || !readyBadge.textContent.trim()) {
              throw new Error("ready status badge was not rendered with an accessible label");
            }
            const detailText = confirmDetails.textContent || "";
            if (!detailText.includes("Serial Experiments Lain E01 Weird.mkv") || !detailText.includes("Serial Experiments Lain - S02E01 - Weird.mkv")) {
              throw new Error("rename confirm details did not expose basename row evidence\\nActual:\\n" + detailText);
            }
            click("#rename-confirm-apply-button", "confirm checked rename apply");
            await new Promise((resolve) => setTimeout(resolve, 150));
            const applyPost = posted.find((entry) => entry.url === "/api/rename/apply");
            if (!applyPost) throw new Error("checked rename apply did not post /api/rename/apply");
            if (JSON.stringify(applyPost.body.selected_sources || []) !== JSON.stringify([first.source, second.source])) {
              throw new Error("checked apply selected_sources did not match checked rows: " + JSON.stringify(applyPost.body));
            }
            if (applyPost.body.confirm_apply !== true) throw new Error("rename apply post omitted confirm_apply=true");
            requireText("rename-apply-outcome-status", ["Applying"]);
            requireText("rename-apply-outcome-summary", ["Status: Applying", "does not prove any file was renamed"]);
            requireText("rename-apply-progress-bars", ["Renaming 2 media files... waiting for backend result", "elapsed"]);
            requireTextAbsent("rename-apply-progress-bars", ["source: rename.apply"]);
            resolveApplyPost({ ok: false, command: "rename.apply", message: "mocked browser rename apply" });
            await new Promise((resolve) => setTimeout(resolve, 250));
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
            requireText("rename-apply-outcome-summary", ["Backend rename apply outcome review", "selected=1", "Undo manifest: C:/State/Rename/undo.json", "Mutation guardrail"]);
            requireText("rename-apply-progress-bars", ["Rename apply", "complete", "100%", "1 renamed / 1 planned", "source: rename.apply"]);
            requireText("rename-apply-status-summary", ["1 renamed / 1 applied"]);
            const appliedOutcomeStatus = text("rename-apply-outcome-status");
            requireText("rename-undo-button", ["Undo Last Apply"]);
            requireText("rename-undo-status", ["Undo available for the last apply"]);
            if (byId("rename-undo-button").hidden) throw new Error("undo button stayed hidden after apply result with undo manifest");
            if (byId("rename-undo-button").disabled) throw new Error("undo button stayed disabled after apply result with undo manifest");
            window.mediaPipelineRenameView.renameOpenResultDialog({
              ok: true,
              message: "Applied selected rename.",
              data: { applied_count: 1, undo_manifest: "C:/State/Rename/undo.json", rows: [{ status: "renamed" }] },
            });
            requireText("rename-result-summary", ["Applied selected rename.", "Undo manifest: undo.json"]);
            byId("rename-result-dialog").close();
            posted.length = 0;
            let resolveUndoPost = null;
            const delayedUndoPost = new Promise((resolve) => { resolveUndoPost = resolve; });
            window.apiPost = async (url, body = {}) => {
              posted.push({ url: String(url || ""), body: JSON.parse(JSON.stringify(body || {})) });
              if (String(url || "") === "/api/rename/undo") return delayedUndoPost;
              if (String(url || "") === "/api/rename/preview") return { rows: [], counts: {} };
              return { ok: false, command: "unexpected", message: "unexpected " + String(url || "") };
            };
            click("#rename-undo-button", "undo last apply cancel path");
            await new Promise((resolve) => setTimeout(resolve, 100));
            if (!byId("rename-confirm-dialog").open) throw new Error("undo confirmation dialog did not open");
            requireText("rename-confirm-title", ["Confirm undo rename"]);
            requireText("rename-confirm-count", ["Undo last apply"]);
            requireText("rename-confirm-list", ["1 media file will restore", "1 matching sidecar will move back", "2 total operations", "Undo manifest", "undo.json"]);
            requireText("rename-confirm-apply-button", ["Undo Last Apply"]);
            byId("rename-confirm-dialog").close("cancel");
            await new Promise((resolve) => setTimeout(resolve, 100));
            if (posted.some((entry) => entry.url === "/api/rename/undo")) throw new Error("canceling undo still posted /api/rename/undo");
            requireText("rename-undo-status", ["Undo available for the last apply"]);
            click("#rename-undo-button", "undo last apply confirm path");
            await new Promise((resolve) => setTimeout(resolve, 100));
            if (!byId("rename-confirm-dialog").open) throw new Error("second undo confirmation dialog did not open");
            click("#rename-confirm-apply-button", "confirm undo last apply");
            await new Promise((resolve) => setTimeout(resolve, 150));
            const undoPost = posted.find((entry) => entry.url === "/api/rename/undo");
            if (!undoPost) throw new Error("undo confirm did not post /api/rename/undo");
            if (undoPost.body.confirm_undo !== true) throw new Error("rename undo post omitted confirm_undo=true");
            if (undoPost.body.undo_manifest !== "C:/State/Rename/undo.json") throw new Error("rename undo post used wrong manifest: " + JSON.stringify(undoPost.body));
            requireText("rename-apply-progress-bars", ["Undoing last apply... waiting for backend result", "elapsed"]);
            requireTextAbsent("rename-apply-progress-bars", ["Rename apply", "complete", "100%", "source: rename.apply"]);
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
            await new Promise((resolve) => setTimeout(resolve, 250));
            requireText("rename-result-title", ["Undo result"]);
            requireText("rename-result-summary", ["2 restored / 0 skipped / 0 failed", "Undo manifest: undo.json"]);
            requireText("rename-apply-progress-bars", ["Rename undo", "complete", "100%", "2 restored / 0 skipped / 0 failed"]);
            requireText("rename-undo-status", ["Undo completed"]);
            if (!byId("rename-undo-button").disabled) throw new Error("undo button was not disabled after successful undo");
            if (byId("rename-result-dialog").open) byId("rename-result-dialog").close();
            for (const fragment of ["Backend result", "Selected scope", "Sidecar operations", "Undo / rollback evidence", "Mutation boundary"]) {
              if (!outcomeCells().includes(fragment)) throw new Error("outcome table missing " + fragment + "\\nActual:\\n" + outcomeCells());
            }
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
            window.mediaPipelineRenameView.renderRenamePreview({ rows: largeRows, preview_fingerprint: "rename-preview-fp", counts: { total: 260, ready: 260 }, confidence_counts: { high: 260 }, preview_source_counts: { auto_tv_heuristic: 260 }, change_kind_counts: { rename: 260 } });
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
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [blockedExisting], preview_fingerprint: "rename-preview-fp", counts: { total: 1, blocked: 1 }, confidence_counts: { blocked: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { blocked: 1 } });
            if (!previewCells().includes("Blocked: destination already exists")) {
              throw new Error("preview table did not expose blocked destination reason\\nActual:\\n" + previewCells());
            }

            const duplicateA = { ...first, source: "C:/TV/S02/E01.mkv", source_name: "E01.mkv" };
            const duplicateB = { ...first, source: "C:/TV/S02/E02.mkv", source_name: "E02.mkv" };
            setValue("rename-paths", "C:/TV/S02/E01.mkv\\nC:/TV/S02/E02.mkv");
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [duplicateA, duplicateB], preview_fingerprint: "rename-preview-fp", counts: { total: 2, ready: 2 }, confidence_counts: { high: 2 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
            click("#rename-check-applicable-button", "check applicable rename rows");
            requireText("rename-selected-count", ["0 checked"]);
            requireText("rename-apply-readiness-status", ["Blocked"]);
            requireReadiness(["Duplicate destinations", "duplicate target", "selected_sources"]);
            requireText("rename-apply-button", ["Resolve blockers before apply"]);
            requireText("rename-apply-status-hint", ["Checked 0 ready/match rows", "duplicate=2"]);
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
              outcomeStatus: appliedOutcomeStatus,
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
        self.assertIn("duplicate=2", browser_result["blockerHint"])
        self.assertEqual(browser_result["posted"], [])


if __name__ == "__main__":
    unittest.main()
