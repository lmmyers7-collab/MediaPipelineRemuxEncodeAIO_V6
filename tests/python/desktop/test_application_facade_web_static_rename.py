from __future__ import annotations

import unittest

from tests.python.desktop.application_facade_test_support import served_webview_static_contract_bundle


def _assert_contains_all(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertIn(snippet, text)


def _assert_not_contains_any(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertNotIn(snippet, text)


class ApplicationFacadeWebStaticRenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = served_webview_static_contract_bundle()

    def test_rename_assets_dom_and_page_placement_are_static_pinned(self) -> None:
        html = self.bundle.html

        _assert_contains_all(
            self,
            html,
            (
                "/assets/renameLabels.js",
                "/assets/renameHistoryView.js",
                "/assets/renameView.js",
                "settings-rename-remove-terms",
                "Rename Cleaning Filters",
                "Movie Filters",
                'data-rename-movie-filter="video_source"',
                'data-rename-movie-filter="languages_subs_dubs"',
                "settings-rename-filter-languages-subs-dubs",
                "rename-workbench",
                "Choose Files",
                "rename-stage-files-heading",
                "rename-file-source-status",
                "rename-file-source-summary",
                "rename-browse-files-button",
                "rename-browse-folder-button",
                "rename-clear-paths-button",
                "rename-check-all-button",
                "rename-drop-zone",
                "rename-stage-mode-heading",
                "rename-mode",
                "rename-force-pipeline",
                "rename-pipeline-preview",
                "rename-template-preset",
                "tv_no_episode_title",
                "Movie: Title (Year)",
                "rename-stage-preview-heading",
                "rename-preview-status",
                "rename-preview-button",
                "rename-rows",
                "rename-table-legend",
                "rename-apply-button",
                "rename-apply-status-hint",
                "rename-apply-readiness-status",
                "rename-apply-readiness-rows",
                "rename-apply-progress-bars",
                "rename-apply-outcome-status",
                "rename-apply-outcome-rows",
                "rename-apply-outcome-summary",
                "rename-summary",
                "rename-confirm-dialog",
                "rename-confirm-apply-button",
                "rename-result-dialog",
                "rename-result-open-log-button",
                "rename-last-apply-status",
                "rename-last-apply-detail",
                "rename-apply-history",
            ),
        )

        queue_start = html.index('data-page-panel="queue"')
        completed_start = html.index('data-page-panel="completed"')
        rename_start = html.index('data-page-panel="rename"')
        launch_start = html.index('data-page-panel="launch"')
        self.assertNotIn("rename-apply-button", html[queue_start:completed_start])
        _assert_contains_all(
            self,
            html[rename_start:launch_start],
            (
                "rename-workbench",
                "rename-preview-button",
                "rename-apply-button",
                "rename-summary",
                "rename-apply-readiness-rows",
                "rename-apply-outcome-rows",
                "rename-result-dialog",
                "rename-browse-files-button",
                "rename-clear-paths-button",
                "rename-check-all-button",
            ),
        )

    def test_rename_labels_and_history_namespaces_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.rename_labels_js,
            (
                "window.mediaPipelineRenameLabels",
                "function renameStatusExplanation",
                "function renamePreviewSourceLabel",
                "function renameConfidenceExplanation",
                "function renameConfidenceLabel",
                "Pipeline TV preview",
                "Movie scrub filters",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.rename_labels_js,
            (
                "window.renameStatusExplanation = renameStatusExplanation",
                "window.renamePreviewSourceLabel = renamePreviewSourceLabel",
                "window.renameConfidenceExplanation = renameConfidenceExplanation",
                "window.renameConfidenceLabel = renameConfidenceLabel",
            ),
        )
        _assert_contains_all(
            self,
            bundle.rename_history_view_js,
            (
                "window.mediaPipelineRenameHistoryView",
                "function renderRenameApplyHistory",
                "function isRenameApplyCommand",
                "rename.apply",
                "if (entries[0] && typeof renderRenameApplyResult === \"function\")",
                "renderRenameApplyResult(entries[0])",
                "Backend rename preview/apply remains the source of truth for filesystem changes.",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.rename_history_view_js,
            (
                "window.isRenameApplyCommand = isRenameApplyCommand",
                "window.renameApplyHistoryLine = renameApplyHistoryLine",
                "window.renderRenameApplyHistory = renderRenameApplyHistory",
            ),
        )

    def test_rename_view_filters_and_settings_save_hooks_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.rename_view_js,
            (
                "window.mediaPipelineRenameView",
                "mediaPipelineRenameLabels",
                "mediaPipelineRenameHistoryView",
                "function collectRenameRequest",
                "function renameCleaningFilterConfigPatch",
                "RenameMovieFilterOptions: collectRenameMovieFilterOptions()",
                "RenameMovieFilterTerms: collectRenameMovieFilterTerms()",
                "RenameMovieRemoveTerms: parseRenameFilterTerms",
                "RenameTVFilterOptions: collectRenameTvFilterOptions()",
                "RenameTVFilterTerms: collectRenameTvFilterTerms()",
                "RenameTVRemoveTerms: parseRenameFilterTerms",
                "stageRenameCleaningFilterPatch(changes)",
                "no backend save route was called",
                "function collectRenameMovieFilterTerms",
                "function collectRenameTvFilterTerms",
                "movie_filter_terms_text: collectRenameMovieFilterTermsText()",
                "tv_filter_terms_text: collectRenameTvFilterTermsText()",
                'RENAME_FILTER_CATALOG_ROUTE = "/api/rename/cleaning-filters"',
                'RENAME_MOVIE_FILTER_CATALOG_ROUTE = "/api/rename/movie-cleaning-filters"',
                'RENAME_CLEAN_FILENAME_PREVIEW_ROUTE = "/api/rename/clean-filename-preview"',
                "Source: backend clean_pipeline_movie_name.",
                "Source: backend build_auto_tv_rename_name.",
                "Saved filters affect future pipeline output naming",
                "Movie filter policy:",
                "TV filter policy:",
                "function initRenameCleaningFilterEditorEvents",
                "RENAME_CLEANING_FILTER_STORAGE_KEY",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.rename_view_js,
            (
                "window.renameStatusExplanation = renameStatusExplanation",
                "window.renamePreviewSourceLabel = renamePreviewSourceLabel",
                "window.renameConfidenceExplanation = renameConfidenceExplanation",
                "window.renameConfidenceLabel = renameConfidenceLabel",
                "window.isRenameApplyCommand = isRenameApplyCommand",
                "window.renameApplyHistoryLine = renameApplyHistoryLine",
                "window.renderRenameApplyHistory = renderRenameApplyHistory",
                "movie_filter_terms_enabled",
            ),
        )
        _assert_contains_all(
            self,
            bundle.settings_view_js,
            (
                "function saveRenameCleaningFiltersFromSettingsSave(",
                "function mergeRenameCleaningFiltersForSave",
                "function openSettingsSaveReviewDialog",
                "renameView.saveRenameCleaningFilterDraft",
                "Rename filters are included in the current Save Settings review.",
                "function settingsRenameLogCasePayload()",
                "renameView.submitRenameBadCasePayload(payload)",
                "initSettingsRenameLogCaseEvents()",
            ),
        )
        _assert_contains_all(
            self,
            bundle.html,
            (
                "settings-rename-filter-video-source",
                "settings-rename-filter-languages-subs-dubs",
                "settings-rename-filter-release-groups",
                "settings-rename-tv-filter-video-source",
                "settings-rename-tv-filter-release-groups",
                "settings-rename-tv-remove-terms",
                "Rename Filter Case Workbench",
                "make a bad case fail first",
                "New terms to stage",
                "Current Draft Filters",
                'class="rename-workbench-source-title"',
                'data-rename-workbench-required-modes="movie tv"',
                "settings-rename-workbench-form",
                "settings-rename-workbench-mode",
                "settings-rename-workbench-template",
                "settings-rename-workbench-source-folder",
                "settings-rename-workbench-source-file",
                "settings-rename-workbench-expected-show",
                "settings-rename-workbench-expected-season",
                "settings-rename-workbench-expected-episode",
                "settings-rename-workbench-expected-episode-title",
                "settings-rename-workbench-expected-movie-title",
                "settings-rename-workbench-expected-year",
                "settings-rename-workbench-notes",
                "settings-rename-workbench-test-button",
                "settings-rename-workbench-save-case-button",
                "settings-rename-workbench-stage-suggestions-button",
                "settings-rename-workbench-retest-button",
                "settings-rename-workbench-save-filters-button",
                "Save New Filters",
                "settings-rename-workbench-save-state",
                "settings-rename-workbench-suggestions",
                "settings-rename-cleaning-filters-details",
                "settings-rename-cleaning-filters-reset-button",
            ),
        )
        workbench_order = (
            bundle.html.index("Case input"),
            bundle.html.index("Expected output"),
            bundle.html.index("Backend comparison"),
            bundle.html.index("New terms to stage"),
        )
        self.assertEqual(tuple(sorted(workbench_order)), workbench_order)
        _assert_contains_all(
            self,
            bundle.rename_view_js,
            (
                "rename-workbench-required",
                "rename-workbench-inactive",
                "already_filtered",
                "coverage_reason",
                "stage_recommended",
                "setRenameWorkbenchSaveState",
                "Staged in draft; retest required.",
                "Save New Filters is ready.",
                "settings-save-header-save-button",
            ),
        )
        _assert_contains_all(
            self,
            bundle.css_pages,
            (
                'tr[data-suggestion-state="existing"]',
                'tr[data-suggestion-state="new"]',
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.html,
            (
                "settings-rename-use-editable-cleaning-filters",
                "Stage Rename Filter Patch",
                "settings-rename-cleaning-filters-save-button",
                "settings-rename-workbench-case-status",
                "settings-rename-workbench-existing-suggestions",
                "Already filtered or already handled",
                "Case status",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.css_pages,
            (
                'content: "required"',
                "label.rename-workbench-required::after",
            ),
        )

    def test_rename_preview_apply_and_outcome_contracts_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.rename_view_js,
            (
                "function renameBatchSafetyLines",
                "function renderRenameBatchSafety",
                "function renderRenameReviewBoard",
                "function renameReviewBoardLines",
                "function renameReviewBoardStatus",
                "function renamePreviewAggregateObject",
                "function renameTemplateLabel",
                "function renderRenameBulkEditor",
                "function stageRenameBulkEdit",
                "function usePipelineNamesForRenameScope",
                "function setRenameBulkForce",
                "function clearRenameBulkOverrides",
                "function renameBulkScopeRows",
                "Stage Bulk Edit uses the current backend preview final names",
                "function renderRenameSelectionAudit",
                "function renameSelectionAuditStatus",
                "function renderRenameApplyReadiness",
                "function renameApplyReadinessRows",
                "function renameApplyReadinessStatus",
                "function renameApplyScopeBlockers",
                "const RENAME_PREVIEW_RENDER_LIMIT = 250",
                "function renameRenderedRowsCount",
                "Render cap visibility",
                "checked scope may include rows not currently rendered",
                "Rename selection is blocked by apply readiness",
                "Apply posts confirm_apply plus selected_sources",
                "backend rename.apply remains the only filesystem mutation path",
                "function renameApplyResultLines",
                "function renderRenameApplyResult",
                "function renameApplyProgressBars",
                "function renderRenameApplyProgress",
                'renderProgressBarsInto("rename-apply-progress-bars"',
                "function renderRenameApplyOutcomeReview",
                "function renameApplyOutcomeRows",
                "function renameApplyOutcomeStatus",
                "Backend rename apply outcome review:",
                "Undo / rollback evidence",
                "Change kind:",
                "Sidecar moves planned:",
                "Undo manifest:",
                "TV ordering: backend preview follows the current Paths textarea order.",
                "Preview-wide review board.",
                "template_preset",
                "active_template",
                "template_catalog",
                "confidence_counts",
                "preview_source_counts",
                "change_kind_counts",
                "Backend rename preview/apply remains the source of truth for filesystem changes.",
            ),
        )
        _assert_contains_all(
            self,
            bundle.html,
            (
                "rename-apply-readiness-rows",
                "rename-apply-readiness-status",
                "Preview before apply",
                "rename-apply-progress-bars",
                "rename-apply-outcome-status",
                "rename-apply-outcome-summary",
                "rename-apply-outcome-rows",
                "Outcome Checkpoint",
            ),
        )

    def test_rename_browse_selection_and_busy_guards_are_backend_owned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.rename_view_js,
            (
                "/api/rename/browse",
                "function browseRenamePaths",
                "Windows file browser",
                "Rename path browser route is not available in the running backend",
                "function renderRenamePreview",
                "lastRenamePreviewFingerprint",
                "request.preview_fingerprint = lastRenamePreviewFingerprint",
                "function renderRenameSummary",
                "Preview source:",
                "Confidence reason(s):",
                "Checked-row apply still rebuilds the plan through the backend",
                "function getCheckedRenameRows",
                "function checkApplicableRenameRows",
                "function checkAllRenameRows",
                "function clearCheckedRenameRows",
                "function moveCheckedRenamePaths",
                "function naturalSortRenamePaths",
                "Run Preview to rebuild TV sequence numbering",
                "checked rows are required and are sent as selected_sources",
                "function applyRenameSelectedOverride",
                "function clearRenameSelectedOverride",
                "function selectRenameRow",
                "visibleResult = { ...result, request }",
                "let renamePreviewRequestId = 0",
                "let renamePreviewInFlight = false",
                "let renameBrowseInFlight = false",
                "let renameApplyInFlight = false",
                "function setRenamePreviewBusy",
                "function setRenameApplyBusy",
                "function syncRenameCommandButtons",
                '"rename-preview-button"',
                '"rename-preview-top-button"',
                "if (renamePreviewInFlight || renameApplyInFlight)",
                "setRenameApplyBusy(true)",
                "renamePreviewInFlight || renameBrowseInFlight || renameApplyInFlight",
                "requestId !== activeRenamePreviewRequestId",
                "/api/rename/apply",
                "confirm_apply",
                "String(item?.source || \"\").toLowerCase()",
            ),
        )
        self.assertNotIn("toLocaleLowerCase", bundle.rename_view_js)
        removed_rename_flat_exports = (
            "refreshRenamePreview",
            "renderRenameBulkEditor",
            "stageRenameBulkEdit",
            "usePipelineNamesForRenameScope",
            "setRenameBulkForce",
            "clearRenameBulkOverrides",
            "syncRenameCommandButtons",
            "checkApplicableRenameRows",
            "checkAllRenameRows",
            "clearCheckedRenameRows",
            "moveCheckedRenamePaths",
            "naturalSortRenamePaths",
            "renderRenameFileSourceSummary",
            "useSelectedQueueRowForRename",
            "useLoadedQueueRowsForRename",
            "addRenamePathFromInput",
            "clearRenamePaths",
            "applyRenameSelectedOverride",
            "clearRenameSelectedOverride",
        )
        for export_name in removed_rename_flat_exports:
            with self.subTest(export_name=export_name):
                self.assertNotIn(f"window.{export_name} =", bundle.rename_view_js)

    def test_rename_app_shell_wiring_uses_rename_namespace(self) -> None:
        _assert_contains_all(
            self,
            self.bundle.js,
            (
                "const renameView = window.mediaPipelineRenameView || {}",
                "renameView.checkApplicableRenameRows?.()",
                "renameView.checkAllRenameRows?.()",
                "renameView.clearCheckedRenameRows?.()",
                "renameView.moveCheckedRenamePaths?.(-1)",
                "renameView.moveCheckedRenamePaths?.(1)",
                "renameView.naturalSortRenamePaths?.()",
                "initRenameCleaningFilterEditorEvents",
                "renameView.stageRenameBulkEdit?.()",
                "renameView.setRenameBulkForce?.(true)",
                "renameView.clearRenameBulkOverrides?.()",
            ),
        )


if __name__ == "__main__":
    unittest.main()
