from __future__ import annotations

import unittest
from pathlib import Path


STATIC_ROOT = Path(__file__).resolve().parents[1] / "mediapipeline_desktop_app" / "ui_web" / "static"


class WebViewSettingsLibrariesStaticTests(unittest.TestCase):
    def test_libraries_page_is_main_nav_surface(self) -> None:
        shell_html = (STATIC_ROOT / "partials" / "app-shell-start.html").read_text(encoding="utf-8")
        libraries_html = (STATIC_ROOT / "partials" / "page-libraries.html").read_text(encoding="utf-8")
        settings_html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        self.assertLess(shell_html.index('data-page="libraries"'), shell_html.index('data-page="settings"'))
        self.assertIn('data-page-panel="libraries"', libraries_html)
        self.assertNotIn('data-settings-tab="libraries"', settings_html)
        self.assertIn("Default Editor", settings_html)
        self.assertIn("Default Media", settings_html)
        self.assertIn("settings-library-actions-panel", libraries_html)
        self.assertIn("settings-library-command-box", libraries_html)
        self.assertIn("settings-library-active-title", libraries_html)
        self.assertNotIn("Movie and TV are always present.", libraries_html)
        self.assertNotIn("Movie and TV cannot be deleted.", libraries_html)
        self.assertIn("settings-library-editor-status", libraries_html)
        self.assertIn("settings-library-tab-bar", libraries_html)
        self.assertIn("settings-library-feedback", libraries_html)
        self.assertIn('id="settings-library-warning-summary"', libraries_html)
        self.assertIn("hidden", libraries_html)
        self.assertLess(
            libraries_html.index("settings-library-tab-bar"),
            libraries_html.index("settings-library-actions-panel"),
        )
        self.assertLess(
            libraries_html.index("settings-library-actions-panel"),
            libraries_html.index("settings-libraries-panel"),
        )
        self.assertIn("settings-library-profile-list", libraries_html)
        self.assertIn("settings-library-add-button", libraries_html)
        self.assertIn("settings-library-delete-button", libraries_html)
        self.assertIn("settings-library-defaults-button", libraries_html)
        self.assertIn("settings-library-reset-button", libraries_html)
        self.assertIn("settings-library-save-button", libraries_html)

    def test_settings_libraries_asset_stages_profile_patch(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        for token in (
            "LibraryProfiles",
            "SourceMovies",
            "SourceTV",
            "Outsource",
            "FinalLibraryPromotionRules",
            "Default Editor Overrides",
            "Default Video / Media Overrides",
            "Default Subtitle Overrides",
            "Default Audio Overrides",
            "overrides",
            "emptyOverrides",
            "normalizeOverrides",
            "data-library-override-control",
            "data-library-use-default-override",
            "settings-library-override-use-default",
            "settings-library-override-summary",
            "settings-library-override-label-text",
            "openOverrideSectionsByLibrary",
            "captureOpenOverrideSections",
            "closeOverrideSections(activeLibraryTabId)",
            "Use default",
            "promotion_destination",
            "data-library-profile-tab",
            "data-library-profile-pane",
            "activateLibraryTab",
            "deleteActiveLibrary",
            "replaceActiveLibraryValuesWithDefaults",
            "previewLibraryProfiles",
            "saveLibraryProfiles",
            "libraryEditorDirty",
            "markLibraryEditorDirty",
            "profilesEquivalent",
            "comparableTracking",
            'const designationValues = ["movie", "tv", "auto"]',
            "normalizeDesignation",
        ):
            self.assertIn(token, js)
        self.assertIn("<details", js)
        self.assertIn('hidden disabled"}>Use default</button>', js)
        self.assertNotIn('["movie", "tv", "mixed", "custom"]', js)
        self.assertNotIn("editor_overrides:", js)
        self.assertNotIn("media_overrides:", js)

    def test_settings_libraries_asset_tracks_explicit_override_state(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        for token in (
            'data-library-override="${isOverride ? "true" : "false"}"',
            'row.dataset.libraryOverride = isOverride ? "true" : "false"',
            'row.classList.toggle("is-custom", isOverride)',
            'button.hidden = !isOverride',
            'const isOpen = openSections instanceof Set && openSections.has(group.key)',
            '${isOpen ? " open" : ""}',
            'list.addEventListener("toggle"',
            'updateOverrideRowState(row, true)',
            'updateOverrideRowState(row, false)',
            'defaultSettingValue(key)',
            'overrides[group][key] = readOverrideControlValue(control, key)',
            'if (row.dataset.libraryOverride !== "true") return;',
            'setOverrideControlValue(control, key, defaultSettingValue(key))',
        ):
            self.assertIn(token, js)
        self.assertNotIn("data-library-override-state", js)
        self.assertNotIn("Settings overrides:", js)
        self.assertNotIn("Inherited path fields:", js)

    def test_settings_libraries_asset_preserves_unsaved_cards_during_refresh(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        for token in (
            "if (libraryEditorDirty && profileCardsFromDom().length)",
            "const stagedProfiles = collectProfilesFromDom();",
            "if (!profilesEquivalent(stagedProfiles, incomingProfiles))",
            "default_tracking: comparableTracking(profile)",
            'setText("settings-libraries-status", `${profiles.length} library profile(s) staged`);',
            "renderActiveLibraryCommandState();",
            "libraryEditorDirty = false;",
            "markLibraryEditorDirty();",
            "Unsaved library edits were kept through refresh.",
        ):
            self.assertIn(token, js)

    def test_settings_libraries_asset_is_loaded_after_settings_view(self) -> None:
        html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertLess(html.index("/assets/settingsView.js"), html.index("/assets/settingsLibraries.js"))
        self.assertLess(html.index("/assets/settingsLibraries.js"), html.index("/assets/settingsWizard.js"))


if __name__ == "__main__":
    unittest.main()
