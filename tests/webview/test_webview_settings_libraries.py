from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))
sys.path.insert(0, str(find_repo_root(Path(__file__))))

from mediapipeline.core.config.library_profiles import LIBRARY_OVERRIDE_KEYS_BY_GROUP
from mediapipeline.core.config.metadata_parts.field_definitions import CONFIG_FIELD_DEFINITIONS
from mediapipeline.core.config.preset_migration import LABEL_ONLY_RENAMES


STATIC_ROOT = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static"
VOBSUB_LIBRARY_OVERRIDE_KEYS = {
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "VobSubExtractLanguages",
    "VobSubOcrToolPath",
    "VobSubOcrTimeoutSeconds",
    "TreatVobSubSignsSongsAsForced",
}
def _backend_library_override_keys() -> set[str]:
    return {key for keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.values() for key in keys}


def _backend_field_metadata() -> dict[str, dict[str, object]]:
    return {str(field["key"]): field for field in CONFIG_FIELD_DEFINITIONS}


def _backend_library_override_group_by_key() -> dict[str, str]:
    return {
        key: group
        for group, keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.items()
        for key in keys
    }


def _settings_metadata_keys() -> set[str]:
    js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
    return set(re.findall(r'\["([A-Za-z0-9_]+)"\s*,\s*"settings-', js))


def _scan_js_array(source: str, array_start: int) -> tuple[str, int]:
    depth = 0
    quote = ""
    escaped = False
    for index in range(array_start, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'", "`"}:
            quote = char
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return source[array_start : index + 1], index + 1
    raise AssertionError("Unclosed JavaScript array in settingsLibraries.js")


def _settings_library_layout_keys_by_group() -> dict[str, set[str]]:
    js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
    start = js.index("const overrideLayouts = {")
    end = js.index("const fallbackGroupByField", start)
    layout_text = js[start:end]
    groups: dict[str, set[str]] = {}
    for group in LIBRARY_OVERRIDE_KEYS_BY_GROUP:
        group_start = layout_text.index(f"    {group}: [")
        array_start = layout_text.index("[", group_start)
        group_text, _array_end = _scan_js_array(layout_text, array_start)
        keys: set[str] = set()
        for match in re.finditer(r"\b(?:fields|gridFields):\s*\[([^\]]*)\]", group_text):
            keys.update(re.findall(r'"([A-Za-z][A-Za-z0-9_]*)"', match.group(1)))
        groups[group] = keys
    return groups


def _settings_library_override_group_order() -> tuple[str, ...]:
    js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
    match = re.search(r"const overrideGroupOrder = \[([^\]]+)\]", js)
    if match is None:
        raise AssertionError("overrideGroupOrder was not found in settingsLibraries.js")
    return tuple(re.findall(r'"([A-Za-z0-9_]+)"', match.group(1)))


def _settings_library_layout_keys() -> set[str]:
    return {key for keys in _settings_library_layout_keys_by_group().values() for key in keys}


class WebViewSettingsLibrariesStaticTests(unittest.TestCase):
    def test_settings_metadata_covers_backend_library_override_keys(self) -> None:
        metadata_keys = _settings_metadata_keys()
        backend_keys = _backend_library_override_keys()

        self.assertEqual(sorted(backend_keys - metadata_keys), [])
        self.assertLessEqual(VOBSUB_LIBRARY_OVERRIDE_KEYS, metadata_keys)

    def test_settings_library_layout_covers_backend_library_override_keys(self) -> None:
        layout_keys = _settings_library_layout_keys()
        backend_keys = _backend_library_override_keys()

        self.assertEqual(sorted(backend_keys - layout_keys), [])
        self.assertLessEqual(VOBSUB_LIBRARY_OVERRIDE_KEYS, layout_keys)

    def test_settings_library_layout_keys_are_backend_known_and_editable(self) -> None:
        metadata = _backend_field_metadata()
        group_by_key = _backend_library_override_group_by_key()
        layout_by_group = _settings_library_layout_keys_by_group()

        self.assertEqual(_settings_library_override_group_order(), tuple(LIBRARY_OVERRIDE_KEYS_BY_GROUP))
        for group, keys in layout_by_group.items():
            with self.subTest(group=group):
                self.assertEqual(sorted(keys - set(metadata)), [])
            for key in keys:
                with self.subTest(group=group, key=key):
                    field = metadata[key]
                    self.assertTrue(field["library_override_allowed"])
                    self.assertEqual(field["override_group"], group)
                    self.assertEqual(group_by_key[key], group)

        rendered_keys = {key for keys in layout_by_group.values() for key in keys}
        self.assertEqual(sorted(_backend_library_override_keys() - rendered_keys), [])

    def test_settings_libraries_asset_uses_backend_metadata_for_override_rows(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        for token in (
            "function overrideFieldsForGroup(groupKey)",
            "function overrideGroupList()",
            "function overrideStatus(groupKey, key, profile = null)",
            "function fieldLibraryDesignations(field)",
            "function fieldAppliesToProfile(profile, key)",
            "library_profile_designations",
            "field?.library_override_allowed === true",
            'String(field?.override_group || "") === groupKey',
            "field?.allowed_values",
            "field?.help_text || field?.help",
            "metadataTags(field?.rule_taxonomy)",
            '"default_value"',
            "field.default_value",
            "buildOverrideControl(fieldKey, value, !editable)",
            'data-library-persisted-key="${escapeHtml(persistedKey)}"',
            'data-library-override-eligible="${editable ? "true" : "false"}"',
            'data-library-section="${escapeHtml(section)}"',
            'data-library-advanced-visibility="${escapeHtml(advancedVisibility)}"',
            'data-library-unavailable-reason="${escapeHtml(unavailableReason)}"',
            "Only shown for",
            "Global-only — unavailable",
            "Source/computed — read-only",
            "fieldIsAdvanced(fieldKey, field) ? \" data-advanced\" : \"\"",
            "return fields.filter((fieldKey) => overrideStatus(groupKey, fieldKey, profile).render);",
            "settingsAdvancedFallbackKeys",
            "function fieldIsAdvanced(key, field)",
            "metadataTags(field?.rule_taxonomy)",
            "metadataTags(field?.strictness)",
        ):
            self.assertIn(token, js)
        for token in (
            'data-library-rule-taxonomy="${escapeHtml(ruleTaxonomy)}"',
            'data-library-strictness="${escapeHtml(strictness)}"',
            "renderMetadataBadges",
            "settings-library-metadata-badge",
            "settings-library-metadata-badges",
            "rule-badge settings-library",
            "data-metadata-kind",
            "Display-only backend metadata; not a saved config key.",
        ):
            self.assertNotIn(token, js)

    def test_phase3_library_override_labels_match_backend_metadata(self) -> None:
        metadata = _backend_field_metadata()
        expected = {
            "RoutingProfile": "Library goal",
            "SizeGuardMode": "If encoded output is too large",
            "RouteThresholdMode": "What forces an encode?",
            "VideoPreset": "Encoder Speed Preset",
            "ConvertVobSubToSrt": "OCR VobSub to SRT",
        }

        for key, label in expected.items():
            with self.subTest(key=key):
                self.assertEqual(metadata[key]["label"], label)
                self.assertTrue(metadata[key]["library_override_allowed"])

        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        self.assertIn("if (field?.label) return field.label;", js)
        self.assertIn("fieldHelpText(field)", js)

    def test_library_route_size_editor_replicates_settings_route_surface(self) -> None:
        libraries_js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        route_model_js = (STATIC_ROOT / "assets" / "settings" / "routePolicyModel.js").read_text(encoding="utf-8")
        html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

        for token in (
            'type: "routeSize"',
            "function renderLibraryRouteSizeLayout(profile, groupKey, block)",
            "function renderLibraryRouteRail(boundaries)",
            "function renderLibraryRouteBoundaryControls(boundaries, describedBy)",
            "function renderLibraryRouteBucket(profile, bucket, boundaries)",
            "function syncLibraryRouteReadouts(card)",
            "function applyLibraryRouteBoundary(card, boundary, rawHeight, options = {})",
            "settings-library-route-editor",
            "settings-library-route-rail",
            "settings-library-route-visual",
            "settings-library-route-target-editor",
            "settings-library-route-boundary-grid",
            "settings-library-route-boundary-actions",
            "data-library-route-boundary-input=\"first\"",
            "data-library-route-boundary-input=\"second\"",
            "aria-describedby",
            "data-library-route-source-summary",
            "function routeMetadataMissingKeys(values)",
            "function routeSourceSummary(values)",
            "function routeValueFromBackendSource(values, key)",
            'fieldOwnValue(field, "min")',
            'fieldOwnValue(field, "max")',
            'fieldOwnValue(field, "step")',
            'fieldOwnValue(field, "unit")',
            'data-settings-unit="${escapeHtml(unitValue)}"',
            "data-library-route-boundary-reset=\"first\"",
            "data-library-route-boundary-reset=\"second\"",
            "data-library-route-summary=\"trigger\"",
            "data-library-route-summary=\"pixel\"",
            "data-library-route-summary=\"consequence\"",
            "data-library-route-summary=\"unknown\"",
            "data-library-route-readout=\"range-1080p\"",
            "data-library-route-readout=\"range-1440p\"",
            "data-library-route-readout=\"range-4k\"",
            'routeRole: "height-tolerance"',
            "setLibraryRouteOverrideValue(card, key, routeFormatPercent(value))",
            "resetLibraryRouteBoundary(card, boundaryReset)",
            "syncLibraryRouteReadouts(card)",
        ):
            self.assertIn(token, libraries_js)
        for token in (
            "function startLibraryRouteDrag(event)",
            "function handleLibraryRouteKeydown(event)",
            "list.addEventListener(\"pointerdown\", startLibraryRouteDrag)",
            "data-library-route-drag-boundary",
            "settings-route-slider-hit",
            'role="slider"',
            "routeValuesWithDefaults",
        ):
            self.assertNotIn(token, libraries_js)

        for key in (
            "Route1080pUpperHeightTolerancePercent",
            "Route1440pLowerHeightTolerancePercent",
            "Route1440pUpperHeightTolerancePercent",
            "Route4KLowerHeightTolerancePercent",
        ):
            self.assertIn(key, libraries_js)
            self.assertIn(key, route_model_js)

        for key in (
            "MovieRoute1080pTargetSizeGB",
            "TVRoute1080pTargetSizeGB",
            "Route1080pMaxVideoBitrateMbps",
            "Route1440pMaxVideoBitrateMbps",
            "Route4KMaxVideoBitrateMbps",
        ):
            self.assertIn(key, libraries_js)
            self.assertNotIn(f"{key}:", route_model_js)

        for token in (
            "window.mediaPipelineRoutePolicyModel",
            "function numberValue(value, fallback = 0)",
            "function boundariesFromValues(values = {})",
            "function valuesFromFirstBoundary(route1440pMinHeight)",
            "function valuesFromSecondBoundary(route4kMinHeight)",
            "function consequenceSummary(boundaries, values = {})",
            "function unknownHeightSummary()",
        ):
            self.assertIn(token, route_model_js)
        for token in (
            "const DEFAULTS",
            "DEFAULTS,",
            "routeValuesWithDefaults",
        ):
            self.assertNotIn(token, route_model_js)

        self.assertLess(html.index("/assets/settings/routePolicyModel.js"), html.index("/assets/settings/patchReview.js"))
        self.assertLess(html.index("/assets/settings/routePolicyModel.js"), html.index("/assets/settingsLibraries.js"))

    def test_library_designation_filtering_omits_inapplicable_override_rows(self) -> None:
        metadata = _backend_field_metadata()
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        self.assertEqual(metadata["MovieRoute1080pTargetSizeGB"]["library_profile_designations"], ("movie", "auto"))
        self.assertEqual(metadata["MovieRoute1440pTargetSizeGB"]["library_profile_designations"], ("movie", "auto"))
        self.assertEqual(metadata["MovieRoute4KTargetSizeGB"]["library_profile_designations"], ("movie", "auto"))
        self.assertEqual(metadata["TVRoute1080pTargetSizeGB"]["library_profile_designations"], ("tv", "auto"))
        self.assertEqual(metadata["TVRoute1440pTargetSizeGB"]["library_profile_designations"], ("tv", "auto"))
        self.assertEqual(metadata["TVRoute4KTargetSizeGB"]["library_profile_designations"], ("tv", "auto"))
        self.assertNotIn("library_profile_designations", metadata["Route1080pMaxVideoBitrateMbps"])
        for token in (
            "fieldAppliesToProfile(profile, key)",
            "inapplicableOverrideKeys(profile)",
            "libraryPrunedOverrides",
            "prunedOverrideWarningLines()",
            "omitted designation-specific override(s) from staged LibraryProfiles",
            "rerenderLibraryCard(card)",
            'field === "designation"',
        ):
            self.assertIn(token, js)

    def test_phase3_label_only_keys_are_rendered_as_persisted_library_overrides(self) -> None:
        metadata = _backend_field_metadata()
        layout_keys = _settings_library_layout_keys()
        group_by_key = _backend_library_override_group_by_key()
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        for key, label in LABEL_ONLY_RENAMES.items():
            with self.subTest(key=key):
                field = metadata[key]
                self.assertEqual(field["label"], label)
                self.assertEqual(field["persisted_key"], key)
                self.assertEqual(field["override_group"], group_by_key[key])
                self.assertTrue(field["library_override_allowed"])
                self.assertIn(key, layout_keys)
                self.assertTrue(str(field["help_text"]).strip())

        for token in (
            'data-library-override-group="${escapeHtml(groupKey)}"',
            'data-library-override-key="${escapeHtml(fieldKey)}"',
            'data-library-persisted-key="${escapeHtml(persistedKey)}"',
            'overrides[group][key] = readOverrideControlValue(control, key)',
            'if (row.dataset.libraryOverride !== "true") return;',
        ):
            self.assertIn(token, js)

    def test_library_override_unavailable_and_read_only_copy_is_display_only(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        for token in (
            'field.library_override_allowed !== true',
            'scope === "source_derived" || scope === "computed_only"',
            "Source/computed — read-only",
            "Global-only — unavailable",
            "buildOverrideControl(fieldKey, value, !editable)",
            'data-library-override-eligible="${editable ? "true" : "false"}"',
            'if (!status.render) return "";',
        ):
            self.assertIn(token, js)

    def test_library_override_validation_hints_reuse_backend_metadata_and_persisted_groups(self) -> None:
        libraries_js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        patch_review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for token in (
            "settingsPatchLibraryOverrideValidationHints",
            '["editor", "video", "subtitles", "audio"].forEach((group) => {',
            "{ libraryOverride: true, overrideGroup: group }",
            "field.library_override_allowed !== true",
            "global-only and cannot be saved as a library override",
            "read-only source/effective metadata and cannot be saved as a library override",
            "belongs in overrides.",
        ):
            self.assertIn(token, patch_review_js)

        for token in (
            "settingsPatchLocalValidationHintLines(changes)",
        ):
            self.assertIn(token, settings_js)

        for token in (
            "overrideStatus(groupKey, key, profile = null)",
            "field?.library_override_allowed === true",
            'String(field?.override_group || "") === groupKey',
            'overrides[group][key] = readOverrideControlValue(control, key)',
            'data-library-override-group="${escapeHtml(groupKey)}"',
            'data-library-override-key="${escapeHtml(fieldKey)}"',
            'data-library-persisted-key="${escapeHtml(persistedKey)}"',
            "Reset to inherited removes the persisted library override key",
            "window.writeSettingsPatchJson(patch",
            "libraryProfileResetRequest",
        ):
            self.assertIn(token, libraries_js)

    def test_libraries_page_is_main_nav_surface(self) -> None:
        shell_html = (STATIC_ROOT / "partials" / "app-shell-start.html").read_text(encoding="utf-8")
        libraries_html = (STATIC_ROOT / "partials" / "page-libraries.html").read_text(encoding="utf-8")
        settings_html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        self.assertLess(shell_html.index('data-page="libraries"'), shell_html.index('data-page="settings"'))
        self.assertIn('data-page-panel="libraries"', libraries_html)
        self.assertNotIn('data-settings-tab="libraries"', settings_html)
        self.assertIn("Routing &amp; Size", settings_html)
        self.assertIn(">Media Output</button>", settings_html)
        self.assertIn("settings-library-actions-panel", libraries_html)
        self.assertIn("settings-library-command-box", libraries_html)
        self.assertIn("settings-library-active-title", libraries_html)
        self.assertIn("settings-library-active-detail", libraries_html)
        self.assertNotIn("Movie and TV are always present.", libraries_html)
        self.assertNotIn("Movie and TV cannot be deleted.", libraries_html)
        self.assertIn("settings-library-editor-status", libraries_html)
        self.assertIn("settings-library-profile-nav", libraries_html)
        self.assertIn("settings-library-feedback", libraries_html)
        self.assertIn('id="settings-library-warning-summary"', libraries_html)
        self.assertIn("hidden", libraries_html)
        self.assertLess(
            libraries_html.index("settings-library-profile-nav"),
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
        self.assertIn("settings-library-build-patch-button", libraries_html)
        self.assertIn("settings-library-preview-button", libraries_html)
        self.assertIn("settings-library-save-button", libraries_html)
        self.assertLess(
            libraries_html.index("settings-library-build-patch-button"),
            libraries_html.index("settings-library-preview-button"),
        )
        self.assertLess(
            libraries_html.index("settings-library-preview-button"),
            libraries_html.index("settings-library-save-button"),
        )

    def test_settings_libraries_asset_stages_profile_patch(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")

        for token in (
            "LibraryProfiles",
            "SourceMovies",
            "SourceTV",
            "Outsource",
            "Default Editor Overrides",
            "Default Video / Media Overrides",
            "Default Subtitle Overrides",
            "Default Audio Overrides",
            "overrides",
            "editor: {}",
            "video: {}",
            "subtitles: {}",
            "audio: {}",
            'const overrideGroupOrder = ["editor", "video", "subtitles", "audio"]',
            "emptyOverrides",
            "normalizeOverrides",
            "data-library-override-control",
            "data-library-use-default-override",
            "settings-library-override-use-default",
            "settings-library-override-summary",
            "settings-library-override-label-text",
            "settings-library-state",
            "openOverrideSectionsByLibrary",
            "captureOpenOverrideSections",
            "closeOverrideSections(activeLibraryTabId)",
            "Use global default",
            "Reset to inherited",
            "promotion_destination",
            "promotion_enabled",
            "settings-library-promotion-toggle",
            "data-library-profile-nav",
            "data-library-profile-pane",
            "library_profile_state",
            "library_compatibility_presets",
            "settingsLibraryCompatibilityPresets",
            "mp4_compatibility",
            'type: "compatibility"',
            "renderCompatibilityPresetEditorControl",
            "Compatibility mode",
            "Standard library overrides",
            "data-library-compatibility-select",
            "syncLibraryCompatibilityAvailability",
            "libraryCardMp4CompatibilityActive",
            "mp4CompatibilityWarningLines",
            "mp4CompatibilityConsequences",
            "Optional lossy MP4 reset preset.",
            "profileState",
            "pathEvidence",
            "pathCanReset",
            "data-library-path-source",
            "data-library-can-reset",
            "data-library-path-reset-pending",
            "localInheritedFields",
            "libraryProfileResetRequest",
            "collectLibraryProfileResetsFromDom",
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
        self.assertIn('hidden disabled"}>Reset to inherited</button>', js)
        build_patch_body = js[js.index("function buildPatchFromLibraries") : js.index("function currentSettingsPatchKeys")]
        self.assertIn("LibraryProfiles: libraryProfiles", build_patch_body)
        self.assertNotIn("patch.SourceMovies", build_patch_body)
        self.assertNotIn("patch.SourceTV", build_patch_body)
        self.assertNotIn("patch.Outsource", build_patch_body)
        self.assertNotIn("patch.FinalLibraryPromotionEnabled", build_patch_body)
        self.assertNotIn("patch.FinalLibraryPromotionRules", build_patch_body)
        self.assertNotIn("generatedPromotionRules", js)
        self.assertNotIn('["movie", "tv", "mixed", "custom"]', js)
        self.assertNotIn("editor_overrides:", js)
        self.assertNotIn("media_overrides:", js)

    def test_settings_libraries_asset_tracks_explicit_override_state(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        css = (STATIC_ROOT / "assets" / "styles.pages.css").read_text(encoding="utf-8")

        for token in (
            'data-library-override="${isOverride ? "true" : "false"}"',
            'data-library-override-state-label',
            "Inherited from global",
            "Library override",
            "Library override — currently same as global",
            "Global-only — unavailable",
            "Source/computed — read-only",
            'row.dataset.libraryOverride = isOverride ? "true" : "false"',
            'row.classList.toggle("is-custom", isOverride)',
            'button.hidden = !isOverride',
            "Reset to inherited removes the persisted library override key",
            'row.dataset.libraryResetPending = "true"',
            'delete row.dataset.libraryResetPending',
            'const isOpen = openSections instanceof Set && openSections.has(group.key)',
            '${isOpen ? " open" : ""}',
            'list.addEventListener("toggle"',
            'updateOverrideRowState(row, true)',
            'updateOverrideRowState(row, false)',
            'defaultSettingValue(key)',
            'overrides[group][key] = readOverrideControlValue(control, key)',
            'if (row.dataset.libraryOverride !== "true") return;',
            'setOverrideControlValue(control, key, defaultSettingValue(key))',
            'row.classList.toggle("is-forced", forced)',
            'control.disabled = true',
            'data-library-compatibility-preset="${escapeHtml(preset.id)}"',
            'target.getAttribute?.("data-library-compatibility-select")',
        ):
            self.assertIn(token, js)
        self.assertRegex(css, r"\.settings-library-state\s*\{[^}]*display: inline;")
        self.assertRegex(css, r"\.settings-library-state\.is-inherited\s*\{[^}]*color: var\(--grey-400\);")
        self.assertRegex(css, r"\.settings-library-state\.is-custom\s*\{[^}]*color: var\(--semantic-info-muted-text\);")
        self.assertRegex(css, r"\.settings-library-state\.is-readonly\s*\{[^}]*color: var\(--semantic-warning-text\);")
        self.assertNotIn(".settings-library-metadata-badges", css)
        self.assertNotIn(".settings-library-metadata-badge", css)
        self.assertRegex(css, r"\.settings-library-override-unavailable\s*\{[^}]*color: var\(--semantic-disabled-text\);")
        self.assertNotRegex(css, r"\.settings-library-state\s*\{[^}]*background:")
        self.assertNotRegex(css, r"\.settings-library-state\.is-inherited\s*\{[^}]*background:")
        self.assertNotRegex(css, r"\.settings-library-state\.is-custom\s*\{[^}]*background:")
        self.assertRegex(css, r"\.settings-library-promotion-toggle\s*\{[^}]*display: inline-flex;")
        self.assertRegex(css, r"\.settings-library-promotion-toggle\s+input\s*\{[^}]*width: 16px;")
        self.assertRegex(css, r"\.settings-library-promotion-toggle\s+input\s*\{[^}]*flex: 0 0 16px;")
        self.assertRegex(css, r"\.settings-library-compatibility-field\s*\{[^}]*display: grid;")
        self.assertNotIn(".settings-library-compatibility-panel", css)
        self.assertRegex(css, r"\.settings-library-override-row\.is-forced\s*\{[^}]*color: var\(--semantic-warning-text\);")
        self.assertNotIn('data-library-override-state="${isOverride ? "custom" : "inherited"}"', js)
        self.assertNotIn("Settings overrides:", js)
        self.assertNotIn("Inherited path fields:", js)
        self.assertNotIn("card.dataset.inheritedFields", js)

    def test_phase4e_library_inheritance_display_and_reset_wiring_is_backend_evidence_based(self) -> None:
        libraries_js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for token in (
            "return Array.isArray(lastSettings?.library_profile_state) ? lastSettings.library_profile_state : [];",
            "function profileState(profile)",
            "profileState(profile)?.path_fields?.[field]",
            "profileState(profile)?.setting_overrides?.[groupKey]?.[fieldKey]",
            'state === "synthesized_builtin_default"',
            'state === "invalid_unresolved"',
            'state === "not_configured"',
            'if (field === "promotion_destination") return false;',
            'if (field === "source_path") return profile.id === "movies" || profile.id === "tv";',
            'if (field === "output_path") return Boolean(evidence);',
            'data-library-can-reset="${canReset ? "true" : "false"}"',
            'input.dataset.libraryPathResetPending = "true";',
            'delete target.dataset.libraryPathResetPending;',
            'row.dataset.libraryResetPending = "true";',
            'delete row.dataset.libraryResetPending;',
            "card.dataset.localInheritedFields = JSON.stringify(Array.from(inherited));",
            "function localInheritedFields(card)",
            "function setLocalInheritedFields(card, inherited)",
            'return Boolean(parsed && typeof parsed === "object" && !Array.isArray(parsed) && Object.prototype.hasOwnProperty.call(parsed, "LibraryProfiles"));',
            "if (!currentPatchIncludesLibraryProfiles()) return [];",
        ):
            self.assertIn(token, libraries_js)

        for token in (
            "function settingsPatchRequestExtras()",
            "window.mediaPipelineSettingsLibraries?.libraryProfileResetRequest",
            "library_profile_resets",
            "const libraryProfileResetCount = Array.isArray(requestExtras.library_profile_resets) ? requestExtras.library_profile_resets.length : 0;",
            "if (!keys.length && !hasLibraryProfileResets)",
            "if (!changedKeys.length && !hasLibraryProfileResets)",
            "`Changed keys: ${changedKeys.length}; staged patch keys: ${keys.length}; library profile resets: ${libraryProfileResetCount}.`",
            "No direct setting key overwrites are staged; backend will apply requested library profile reset(s).",
            'apiPost("/api/settings/preview-patch", { changes, ...requestExtras })',
            'apiPost("/api/settings/save-patch", { changes, ...requestExtras, confirm_save: true })',
            "settingsPatchRequestSignature(changes, requestExtras)",
        ):
            self.assertIn(token, settings_js)

        save_start = settings_js.index("async function saveSettingsPatch()")
        self.assertLess(
            settings_js.index("const requestExtras = settingsPatchRequestExtras();", save_start),
            settings_js.index("if (!keys.length && !hasLibraryProfileResets)", save_start),
        )

    def test_settings_libraries_asset_preserves_unsaved_cards_during_refresh(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        app_js = (STATIC_ROOT / "assets" / "app.js").read_text(encoding="utf-8")

        for token in (
            "if (libraryEditorDirty && profileCardsFromDom().length)",
            "function libraryEditorHasActiveControl()",
            "function shouldDeferAutomaticLibraryRender(options = {})",
            "options?.automatic === true && profileCardsFromDom().length && libraryEditorHasActiveControl()",
            "if (shouldDeferAutomaticLibraryRender(options)) return;",
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
        self.assertIn(
            "window.mediaPipelineSettingsLibraries?.renderSettingsLibraries?.(values.settings, refreshOptions);",
            app_js,
        )

    def test_libraries_tab_contains_read_only_route_map_panels_after_profile_editor(self) -> None:
        partial = (STATIC_ROOT / "partials" / "page-libraries.html").read_text(encoding="utf-8")
        route_map_js = (STATIC_ROOT / "assets" / "librariesRouteMap.js").read_text(encoding="utf-8")
        app_js = (STATIC_ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        route_panel_start = partial.index("settings-library-route-map-panel")
        route_panel = partial[route_panel_start:]

        self.assertLess(partial.index("settings-libraries-panel"), route_panel_start)
        self.assertIn('data-panel-type="evidence"', route_panel)
        self.assertIn('data-table-ui="off"', route_panel)
        for token in (
            "Library Route Map",
            "Decision Matrix",
            "Node Evidence",
            "Selected-File Trace",
            "Profile Compare",
            "Guided Policy Navigation",
            "Validation Handoff",
            "library-route-map-graph",
            "library-route-decision-rows",
            "library-route-node-rows",
            "library-route-trace-rows",
            "library-route-compare-rows",
            "library-route-navigation-rows",
            "library-route-validation-rows",
        ):
            self.assertIn(token, route_panel)
        self.assertNotIn("<button", route_panel)

        for token in (
            '"/api/libraries/route-map"',
            '"/api/libraries/route-map/validation?limit=20"',
            "/api/libraries/route-map/trace",
            "/api/libraries/route-map/compare",
            "window.mediaPipelineLibraryRouteMap",
            "collectEvidenceRows(context = {})",
            "context.queue?.rows",
            "context.completed?.rows",
            "context.sampleValidation?.records",
            "data-library-route-navigate",
            "row.handoff ||",
            "rows.slice(0, 120)",
            "rows.slice(0, 80)",
        ):
            self.assertIn(token, route_map_js)
        self.assertNotIn("apiPost", route_map_js)
        self.assertNotIn("/api/settings/save-patch", route_map_js)
        self.assertNotIn("/api/pipeline/start", route_map_js)
        self.assertIn('["libraries route map", refreshGet("/api/libraries/route-map", refreshOptions), false]', app_js)
        self.assertIn("window.mediaPipelineLibraryRouteMap?.renderRouteMap?", app_js)
        self.assertIn("queue: values.queue || {}", app_js)
        self.assertIn("completed: values.completed || {}", app_js)
        self.assertIn('sampleValidation: values["sample validation"] || {}', app_js)

    def test_settings_libraries_asset_is_loaded_after_settings_view(self) -> None:
        html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertLess(html.index("/assets/settingsView.js"), html.index("/assets/settingsLibraries.js"))
        self.assertLess(html.index("/assets/settings/routePolicyModel.js"), html.index("/assets/settingsLibraries.js"))
        self.assertLess(html.index("/assets/settingsLibraries.js"), html.index("/assets/settingsWizard.js"))
        self.assertLess(html.index("/assets/settingsLibraries.js"), html.index("/assets/librariesRouteMap.js"))
        self.assertLess(html.index("/assets/librariesRouteMap.js"), html.index("/assets/settingsWizard.js"))

    def test_settings_wizard_library_rows_collect_backend_profile_model(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsWizard.js").read_text(encoding="utf-8")

        for token in (
            "section.dataset.defaultTracking = safeJson(library.default_tracking);",
            "section.dataset.overrides = safeJson(library.overrides);",
            'data-library-field="designation"',
            'data-library-field="output_path"',
            'data-library-field="promotion_destination"',
            'data-library-field="promotion_enabled"',
            "default_tracking: readRowJson",
            "overrides: readRowJson",
            'apiPostLocal("/api/settings/wizard/preview", { wizard: collectWizardPayload() })',
            'apiPostLocal("/api/settings/wizard/save", { wizard: collectWizardPayload(), confirm_save: true })',
        ):
            self.assertIn(token, js)
        self.assertNotIn("ProcessingStrategy", js)
        self.assertNotIn("OutputSizeCheck", js)


if __name__ == "__main__":
    unittest.main()
