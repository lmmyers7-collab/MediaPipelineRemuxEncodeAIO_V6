from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))
sys.path.insert(0, str(find_repo_root(Path(__file__))))

from mediapipeline.core.config.metadata_parts.field_definitions import CONFIG_FIELD_DEFINITIONS
from mediapipeline.core.config.preset_migration import (
    FRIENDLY_LABEL_PERSISTED_KEY_ALIASES,
    LABEL_ONLY_RENAMES,
    LABEL_ONLY_RENAME_POLICIES,
)


STATIC_ROOT = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static"
REPRESENTATIVE_SETTINGS_METADATA_KEYS = {
    "VideoPreset",
    "ConvertBdpgsToSrt",
    "CompatibleAudioCodecs",
    "RemuxSafeVideoCodecs",
    "RoutingProfile",
    "SizeGuardMode",
    "OutputContainer",
    "ConvertVobSubToSrt",
}
REPRESENTATIVE_DEFAULT_KEYS = {
    "RoutingProfile",
    "RouteThresholdMode",
    "SizeGuardMode",
    "VideoQuality",
}
SETTINGS_METADATA_ADVISORY_ONLY_KEYS = {
    "DeleteSourceAfterProcessing",
    "ScratchRoot",
}
EDITOR_BUILDER_KEYS = {
    "RoutingProfile",
    "RouteThresholdMode",
    "SizeGuardMode",
    "EncodeLadder",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
    "EncodeThresholdGB",
    "TVEncodeThresholdGB",
    "MovieRoute1080pTargetSizeGB",
    "MovieRoute1440pTargetSizeGB",
    "MovieRoute4KTargetSizeGB",
    "TVRoute1080pTargetSizeGB",
    "TVRoute1440pTargetSizeGB",
    "TVRoute4KTargetSizeGB",
    "MovieRouteMaxVideoBitrateMbps",
    "TVRouteMaxVideoBitrateMbps",
    "Route1080pBucketMaxHeight",
    "Route1080pUpperHeightTolerancePercent",
    "Route1080pMaxVideoBitrateMbps",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route1440pMaxVideoBitrateMbps",
    "Route4KLowerHeightTolerancePercent",
    "Route4KBucketMinHeight",
    "Route4KMaxVideoBitrateMbps",
}
VIDEO_DETAIL_BUILDER_KEYS = {
    "EncodeTuningPreset",
    "VideoPreset",
    "ExtraVideoFlags",
    "RemuxSafeVideoCodecs",
}


def _backend_metadata_by_key() -> dict[str, dict[str, object]]:
    return {str(field["key"]): field for field in CONFIG_FIELD_DEFINITIONS}


def _settings_metadata_builder_keys() -> set[str]:
    js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
    return set(re.findall(r'\["([A-Za-z0-9_]+)"\s*,\s*"settings-', js))


def _settings_metadata_config_key_mentions() -> set[str]:
    js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
    keys = set(re.findall(r'\["([A-Za-z][A-Za-z0-9_]*)"\s*,\s*"settings-', js))
    keys.update(re.findall(r'\bkey:\s*"([A-Za-z][A-Za-z0-9_]*)"', js))

    impact_start = js.index("const settingsImpactGroups = [")
    impact_end = js.index("];", impact_start)
    impact_block = js[impact_start:impact_end]
    for match in re.finditer(r"keys:\s*\[([^\]]*)\]", impact_block, re.S):
        keys.update(re.findall(r'"([A-Za-z][A-Za-z0-9_]*)"', match.group(1)))

    hints_start = js.index("const settingsSpecificImpactHints = {")
    hints_end = js.index("};", hints_start)
    hints_block = js[hints_start:hints_end]
    keys.update(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*):\s*\"", hints_block))
    return keys


def _settings_friendly_alias_entries() -> dict[str, str]:
    js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
    start = js.index("const settingsFriendlyPersistedKeyAliases = {")
    end = js.index("};", start)
    block = js[start:end]
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r'(?m)^\s*"([^"]+)":\s*"([^"]+)"', block)
    }


def _settings_builder_fallback_default(key: str) -> str | None:
    sources = [
        STATIC_ROOT / "assets" / "settingsView.js",
        STATIC_ROOT / "assets" / "settings" / "patchReview.js",
        STATIC_ROOT / "assets" / "settingsView.builders.video.js",
        STATIC_ROOT / "assets" / "settingsView.builders.audio.js",
        STATIC_ROOT / "assets" / "settingsView.builders.subtitle.js",
    ]
    for path in sources:
        js = path.read_text(encoding="utf-8")
        match = re.search(rf'settingsBuilderConfigValue\("{re.escape(key)}",\s*([^)]+)\)', js)
        if match:
            return match.group(1).strip()
        match = re.search(rf'set[A-Za-z]+BuilderControl\("[^"]+",\s*"{re.escape(key)}",\s*"[^"]+",\s*([^)]+)\)', js)
        if match:
            return match.group(1).strip()
    return None


def _normalize_js_literal(value: str | None) -> object:
    if value is None:
        return None
    text = value.strip().rstrip(";")
    if len(text) >= 2 and text[0] in {'"', "'"} and text[-1] == text[0]:
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    if text == "true":
        return True
    if text == "false":
        return False
    return text


class WebViewHandBrakeSettingsUiTests(unittest.TestCase):
    def test_settings_tabs_follow_phase_08_grouping(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        expected_order = [
            "Summary / Effective Decision",
            "Guided Setup",
            "Routing",
            "Dimensions",
            "Filters",
            "Video",
            "Audio",
            "Subtitles",
            "Container",
            "Size / Bitrate Guards",
            "Verification / Publish",
            "Presets",
            "Advanced",
        ]
        cursor = -1
        for label in expected_order:
            position = html.index(f">{label}</button>")
            self.assertGreater(position, cursor)
            cursor = position

        for tab in (
            'data-settings-tab="status"',
            'data-settings-tab="guided-setup"',
            'data-settings-tab="editor"',
            'data-settings-tab="dimensions"',
            'data-settings-tab="filters"',
            'data-settings-tab="video"',
            'data-settings-tab="audio"',
            'data-settings-tab="subtitles"',
            'data-settings-tab="container"',
            'data-settings-tab="size-bitrate"',
            'data-settings-tab="paths"',
            'data-settings-tab="presets"',
            'data-settings-tab="advanced"',
        ):
            self.assertIn(tab, html)

        for retired_tab in (
            ">Video / Audio / Subtitles</button>",
            ">Container / Output Size Check</button>",
            ">Wizard</button>",
            ">Rename Filters</button>",
            ">Source / Compatibility</button>",
            ">System</button>",
            'data-settings-tab="media"',
            'data-settings-tab="container-size"',
            'data-settings-tab="wizard"',
            'data-settings-tab="rename-filters"',
            'data-settings-tab="source-compat"',
            'data-settings-tab="system"',
        ):
            self.assertNotIn(retired_tab, html)

    def test_decision_preview_is_honest_and_read_only(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        for token in (
            "Decision Preview",
            "NOT EVALUATED",
            "Effective Intent Summary",
            "Predicted pending cutover",
            "Legacy path still executes",
            "Processing strategy",
            "Copy/remux-first intent",
            "Encode if required",
            "Size / bitrate guards",
            "Evidence scope",
            "data-settings-summary-key=\"RoutingProfile\"",
            "data-settings-summary-key=\"OutputContainer\"",
            "data-settings-summary-key=\"VideoCodec\"",
            "data-settings-summary-key=\"SizeGuardMode\"",
            "library_effective_settings is library-only",
            "final runtime decision is resolved during queue/job processing",
            "The WebView does not compute copy/remux/encode routing",
            "This panel shows saved output policy for orientation only",
            "cannot launch, save settings, encode, remux, publish, rename, drain pending publish, or touch media files",
        ):
            self.assertIn(token, html)

    def test_summary_panel_uses_persisted_keys_without_runtime_authority(self) -> None:
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for token in (
            "function renderSettingsEffectiveIntentSummary(options = {})",
            'formatSettingsSummaryValue("RoutingProfile"',
            'formatSettingsSummaryValue("RouteThresholdMode"',
            'formatSettingsSummaryValue("OutputContainer"',
            'formatSettingsSummaryValue("VideoCodec"',
            'formatSettingsSummaryValue("VideoPreset"',
            'formatSettingsSummaryValue("SizeGuardMode"',
            'formatSettingsSummaryValue("EncodeThresholdGB"',
            'formatSettingsSummaryValue("MovieRouteMaxVideoBitrateMbps"',
            'persisted key RoutingProfile',
            'persisted key OutputContainer',
            "Applies only when encoding is required.",
            "library_effective_settings is library-only",
            "Final runtime decision is resolved during queue/job processing.",
            "The WebView does not compute copy/remux/encode routing.",
            "renderSettingsEffectiveIntentSummary,",
        ):
            self.assertIn(token, review_js)

        for forbidden in (
            "ProcessingStrategy:",
            "OutputSizeCheck:",
            "runtime_effective_settings:",
            "backend pipeline_plan.v1 preview, diagnostic-only",
            "preview failed; saved settings orientation only",
        ):
            self.assertNotIn(forbidden, review_js + settings_js)

    def test_source_compatibility_tab_and_preview_call_are_removed(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")

        for token in (
            "Source / Compatibility",
            'data-settings-tab="source-compat"',
            'id="settings-source-media-json"',
            'id="settings-preview-plan-button"',
            'id="settings-source-facts-rows"',
            "SourceMediaInfo source facts JSON",
            "Backend validation remains authoritative",
        ):
            self.assertNotIn(token, html)

        for token in (
            'apiPost("/api/settings/pipeline-plan-preview", {',
            "source_media: sourceMedia",
            "renderSettingsPipelinePlanPreview(result, sourceMedia)",
            "Stream actions:",
            "Verification / publish:",
            "Output Size Check:",
            "Command preview:",
            "Preview label remains Predicted pending cutover",
        ):
            self.assertNotIn(token, settings_js)

        self.assertNotIn('bindSettingsClick("settings-preview-plan-button", addSettingsEventHandlers.previewSettingsPipelinePlan)', review_js)
        self.assertIn("Source-specific route previews are not exposed in Settings", review_js)

    def test_guided_setup_tab_uses_five_phase_backend_owned_flow(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        wizard_js = (STATIC_ROOT / "assets" / "settingsWizard.js").read_text(encoding="utf-8")

        for token in (
            'data-settings-tab="guided-setup"',
            "settings-wizard-readiness-strip",
            "settings-wizard-phase-0-status",
            "settings-wizard-phase-4-status",
            "settings-wizard-path-rows",
            "settings-wizard-next-button",
            "settings-open-wizard-button",
            'data-risk-ack-row="AllowSystemTools"',
            'data-risk-ack-row="ReprocessAll"',
            "Save &amp; Reload",
        ):
            self.assertIn(token, html)

        for token in (
            'const WIZARD_TAB_ID = "guided-setup";',
            'const stepLabels = ["Start", "Paths", "Toolchain", "Policy", "Review & Save"];',
            "function settingsWizardSaveReadinessIssues()",
            "function handlePrimaryWizardAction()",
            "function syncRiskAckRows()",
            "Wizard draft changed after the last preview. Preview Config again before saving.",
            'apiPostLocal("/api/settings/wizard/preview", { wizard: collectWizardPayload() })',
            'apiPostLocal("/api/settings/wizard/save", { wizard: collectWizardPayload(), confirm_save: true })',
        ):
            self.assertIn(token, wizard_js)

    def test_routing_labels_are_visible_without_taxonomy_badges(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")

        for token in (
            "Library goal",
            "Saved routing profile",
            "What forces an encode?",
            "Encode trigger",
            "settings-route-trigger-summary",
            "TV / Movie targets by height",
            "Target GB is the encoded output budget",
            "Encoded target size",
            "Movie GB",
            "TV GB",
            "Direct-copy limits",
            "Max Mbps",
            "Height boundary",
            "1080p ends at",
            "1440p starts at",
            "1440p ends at",
            "4K starts at",
            "Upper tolerance",
            "Lower tolerance",
            "Derived height range",
            "settings-route-consequence-summary",
            "If encoded output is too large",
            "Oversize result",
            "Video encoding",
            "Video encoder",
            "settings-routing-video-codec-readout",
            "settings-routing-output-container-readout",
            "Movie 1080p target output size",
            "TV 1080p target output size",
            "Movie 1440p target output size",
            "TV 1440p target output size",
            "Movie 4K target output size",
            "TV 4K target output size",
            "Advanced Routing Details",
            "settings-advanced-routing-summary",
            "How encode targets are calculated",
            "Unknown-height movie size fallback",
            "Unknown-height TV size fallback",
            "Unknown-height movie bitrate fallback",
            "Unknown-height TV bitrate fallback",
            "Legacy 1080p bucket max height",
            "Legacy 4K bucket min height",
            "Bitrate strict, size flexible",
            "Target size strict",
            "Direct-copy bitrate strict",
            "Block publish",
        ):
            self.assertIn(token, html)

        for token in (
            'id="settings-builder-1080p-upper-tolerance" type="hidden"',
            'id="settings-builder-1440p-lower-tolerance" type="hidden"',
            'id="settings-builder-1440p-upper-tolerance" type="hidden"',
            'id="settings-builder-4k-lower-tolerance" type="hidden"',
        ):
            self.assertIn(token, html)

        editor_start = html.index('<div class="settings-tab-pane" data-settings-tab="editor">')
        active_policy_start = html.index("<h2>Active Policy</h2>", editor_start)
        routing_builder_html = html[editor_start:active_policy_start]
        advanced_start = routing_builder_html.index('<details class="settings-advanced-disclosure">')
        visible_routing_html = routing_builder_html[:advanced_start]
        advanced_routing_html = routing_builder_html[advanced_start:]

        self.assertIn('id="settings-builder-video-codec"', advanced_routing_html)
        self.assertIn('id="settings-builder-output-container"', advanced_routing_html)
        self.assertNotIn('id="settings-builder-video-codec"', visible_routing_html)
        self.assertNotIn('id="settings-builder-output-container"', visible_routing_html)

        for token in (
            "Processing Strategy",
            "Enforcement Mode",
            "Output Size Check",
            "Encoder Quality Preset",
            "Encode Target Mode",
            "Hard route gate",
            "Post-encode guard",
            "Direct-copy cap Mbps",
            "Height tolerance",
            "Movie target output size",
            "TV target output size",
            "Movie fallback max bitrate",
            "TV fallback max bitrate",
            "1080-ish max height",
            "1080-ish max bitrate",
            "4K min height",
        ):
            self.assertNotIn(token, routing_builder_html)

        self.assertNotIn(">Default Editor</button>", html)
        self.assertNotIn(">Default Media</button>", html)
        self.assertNotIn(">Encode tuning", html)
        self.assertNotIn("Compatibility advisory", html)
        self.assertNotIn("fallback tuning", html)
        self.assertNotIn("settings-rule-badge-row", html)
        self.assertNotIn("rule-badge", html)
        self.assertNotIn("data-rule-kind", html)
        self.assertNotIn("FORCES ENCODE", html)

        for token in (
            "routeHeightBoundaryControlFields",
            "normalizeRouteHeightBoundary",
            "renderRouteConsequenceSummary",
            "renderRouteAdvancedSummary",
            "settings-boundary-1080p-end",
            "settings-boundary-1440p-start",
            "settings-boundary-1440p-end",
            "settings-boundary-4k-start",
        ):
            self.assertIn(token, review_js)

    def test_advanced_encoder_controls_are_collapsed_by_default(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        details_start = html.index('<details class="settings-advanced-disclosure">')
        summary_index = html.index("<summary>Advanced encoder controls</summary>", details_start)
        extra_flags_index = html.index('id="settings-video-extra-flags"', summary_index)
        details_end = html.index("</details>", extra_flags_index)

        self.assertLess(details_start, summary_index)
        self.assertLess(summary_index, extra_flags_index)
        self.assertLess(extra_flags_index, details_end)

    def test_video_detail_merge_button_has_hover_hint(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        self.assertIn('id="settings-video-apply-button"', html)
        self.assertIn('aria-describedby="settings-video-apply-hint"', html)
        self.assertIn('id="settings-video-apply-hint" class="action-hover-hint" role="tooltip"', html)
        self.assertIn("Stages the values in this Video builder into Changes JSON.", html)
        self.assertIn("backend owns routing, codec, container, and encoder policy", html)

    def test_video_speed_and_quality_targets_use_descriptive_sliders(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        builder_js = (STATIC_ROOT / "assets" / "settingsView.builders.video.js").read_text(encoding="utf-8")
        builder_controls_js = (STATIC_ROOT / "assets" / "settings" / "builderControls.js").read_text(encoding="utf-8")
        styles = (STATIC_ROOT / "assets" / "styles.components.css").read_text(encoding="utf-8")

        for token in (
            'id="settings-video-preset"',
            'type="range"',
            'min="1"',
            'max="7"',
            'settings-video-preset-value',
            'P1 fastest',
            'P7 slowest',
            'settings-video-quality-value',
            'Cleaner / larger',
            'Smaller / softer',
        ):
            self.assertIn(token, html)

        self.assertIn('["VideoPreset", "settings-video-preset", "preset_slider"]', metadata_js)
        self.assertIn('["VideoQuality", "settings-video-quality", "quality_slider"]', metadata_js)
        self.assertIn(
            'setVideoDetailBuilderControl("settings-video-preset", "VideoPreset", "preset_slider", "p5")',
            builder_js,
        )
        self.assertIn(
            'setVideoDetailBuilderControl("settings-video-quality", "VideoQuality", "quality_slider", 22)',
            builder_js,
        )
        self.assertIn('return `p${clampedInteger(value, 5, 1, 7)}`;', builder_js)
        self.assertIn('if (kind === "preset_slider") return videoPresetKeyFromSliderValue', builder_js)
        self.assertIn('if (kind === "quality_slider") return Number(videoQualitySliderValue', builder_js)
        self.assertIn('element.dataset.settingsPreserveRangeLimits === "true"', builder_controls_js)
        self.assertIn('.settings-slider-field input[type="range"]', styles)

    def test_successful_settings_save_resyncs_saved_builder_values(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        self.assertIn("function resetSettingsBuilderSyncState(options = {})", settings_js)
        self.assertIn("videoDetailSettingsBuilderState,", settings_js)
        self.assertIn("state.dirty = false;", settings_js)
        self.assertIn("resetSettingsBuilderSyncState();\n      await refreshAll();", settings_js)
        self.assertIn(
            "resetSettingsBuilderSyncState({ includeFinalLibraryPromotion: true });\n      await refreshAll();",
            settings_js,
        )

    def test_advanced_fields_use_metadata_and_fallback_toggle(self) -> None:
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        metadata_fields_js = (STATIC_ROOT / "assets" / "settings" / "metadataFields.js").read_text(encoding="utf-8")
        builder_controls_js = (STATIC_ROOT / "assets" / "settings" / "builderControls.js").read_text(encoding="utf-8")
        settings_support_js = settings_js + metadata_fields_js + builder_controls_js
        styles = (STATIC_ROOT / "assets" / "styles.components.css").read_text(encoding="utf-8")

        for key in (
            "ExtraVideoFlags",
            "CpuEncodePreset",
            "CpuEncodeProcessPriority",
            "CpuEncodeMaxThreads",
            "FallbackCpuQuality",
            "BdpgsOcrToolPath",
            "BdpgsOcrTimeoutSeconds",
            "VobSubOcrToolPath",
            "VobSubOcrTimeoutSeconds",
            "ExcludeSubtitleStyles",
            "IncludeSubtitleStyles",
        ):
            self.assertIn(f'"{key}"', metadata_js)

        advanced_fallback_start = metadata_js.index("const settingsAdvancedFallbackKeys = [")
        advanced_fallback_end = metadata_js.index("];", advanced_fallback_start)
        advanced_fallback_source = metadata_js[advanced_fallback_start:advanced_fallback_end]
        for key in (
            "DropAssAfterConversion",
            "RemoveKaraoke",
            "StripFormatting",
            "MergeAdjacent",
            "KeepSignsAndSongs",
            "TreatAssSignsSongsAsForced",
        ):
            self.assertNotIn(f'"{key}"', advanced_fallback_source)

        for token in (
            "settingsAdvancedFallbackKeys",
            "function settingsFieldIsAdvanced(key, field)",
            "field?.advanced_visibility",
            "field?.rule_taxonomy",
            "field?.strictness",
            "section === \"advanced\"",
            "settingsAdvancedFallbackKeys.has",
            "dataset.settingsAdvancedControl",
            "function renderSettingsAdvancedControls()",
            "data-settings-advanced-toggle",
            "Show advanced controls",
            "Hide advanced controls",
            "node.hidden = !expanded",
            "document.addEventListener(\"click\", handleSettingsAdvancedToggleClick)",
        ):
            self.assertIn(token, settings_support_js)

        for token in (
            ".settings-advanced-toggle-row",
            ".settings-advanced-toggle-note",
            ".settings-advanced-field[hidden]",
            "display: none !important;",
        ):
            self.assertIn(token, styles)

    def test_rule_and_strictness_badges_are_not_rendered(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        styles = (STATIC_ROOT / "assets" / "styles.components.css").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        video_builder_js = (STATIC_ROOT / "assets" / "settingsView.builders.video.js").read_text(encoding="utf-8")

        combined_tag_sources = html + settings_js + styles
        for token in (
            "settingsMetadataBadgeLabels",
            "settingsMetadataBadgeKind",
            "settingsMetadataBadgeText",
            "renderSettingsFieldTaxonomyBadges",
            "settings-field-metadata-badge",
            "settings-field-metadata-badges",
            "settings-rule-badge-row",
            "rule-badge",
            "data-rule-kind",
            "Display-only backend metadata; not a saved config key.",
        ):
            self.assertNotIn(token, combined_tag_sources)

        self.assertNotIn("settingsRuleTaxonomy", review_js)
        self.assertNotIn("settingsStrictness", review_js)
        self.assertNotIn("settingsAdvancedVisibility", review_js)
        self.assertIn("patch[key] = readVideoDetailBuilderValue", video_builder_js)

    def test_display_label_metadata_overrides_legacy_terms(self) -> None:
        js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        metadata_fields_js = (STATIC_ROOT / "assets" / "settings" / "metadataFields.js").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")

        self.assertNotIn("settingsDisplayLabels", js)
        for key, label in LABEL_ONLY_RENAMES.items():
            with self.subTest(key=key):
                self.assertEqual(_backend_metadata_by_key()[key]["label"], label)
        self.assertIn("return field?.label || fallback || key;", metadata_fields_js)
        self.assertIn("settingsDisplayLabel(key", review_js)
        self.assertIn("if (field?.label) return field.label;", review_js)
        self.assertIn("renderHandbrakePreviewSummary(settings)", review_js)

    def test_static_settings_metadata_keys_have_backend_metadata(self) -> None:
        metadata_keys = _settings_metadata_builder_keys()
        backend_keys = set(_backend_metadata_by_key())

        self.assertEqual(sorted(metadata_keys - backend_keys), [])
        self.assertLessEqual(REPRESENTATIVE_SETTINGS_METADATA_KEYS, metadata_keys)

    def test_settings_metadata_key_mentions_are_backend_known_or_explicitly_advisory(self) -> None:
        mentioned_keys = _settings_metadata_config_key_mentions()
        backend_keys = set(_backend_metadata_by_key())

        self.assertEqual(sorted(mentioned_keys - backend_keys), sorted(SETTINGS_METADATA_ADVISORY_ONLY_KEYS))
        self.assertLessEqual(REPRESENTATIVE_SETTINGS_METADATA_KEYS, mentioned_keys)

    def test_main_settings_ui_prefers_backend_field_metadata(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        metadata_fields_js = (STATIC_ROOT / "assets" / "settings" / "metadataFields.js").read_text(encoding="utf-8")
        builder_controls_js = (STATIC_ROOT / "assets" / "settings" / "builderControls.js").read_text(encoding="utf-8")

        self.assertIn("Backend field_definitions owns labels, options, defaults, constraints", metadata_js)
        for token in (
            "function settingsFieldDefaultValue(key, fallback)",
            "field.default_value",
            "function settingsFieldAllowedValues(field)",
            "field?.allowed_values",
            "function settingsFieldLabel(key, fallback = \"\")",
            "function settingsFieldHelpText(field)",
            "field?.help_text || field?.help",
        ):
            self.assertIn(token, metadata_fields_js)
        for token in (
            "function applySettingsFieldMetadataToControl([key, id, fallbackKind])",
            "if (!field || !element) return;",
            "dataset.settingsKey",
            "dataset.settingsPersistedKey",
            "dataset.settingsValueType",
            "dataset.settingsDefaultValue",
            "dataset.settingsAdvancedVisibility",
            "dataset.settingsSection",
            "field.min",
            "field.max",
            "field.step",
        ):
            self.assertIn(token, builder_controls_js)
        for token in (
            "applySettingsFieldMetadataToControls();",
        ):
            self.assertIn(token, settings_js)
        for token in (
            "function renderSettingsFieldTaxonomyBadges(label, control, field)",
            "settings-field-metadata-badge",
            "dataset.settingsRuleTaxonomy",
            "dataset.settingsStrictness",
        ):
            self.assertNotIn(token, settings_js)
        self.assertNotIn("rule_taxonomy", metadata_js)
        self.assertNotIn("strictness", metadata_js)

    def test_settings_workspace_payload_exposes_phase3_display_metadata(self) -> None:
        helper = (find_repo_root(Path(__file__)) / "src" / "mediapipeline" / "core" / "config" / "settings_helpers_facade.py").read_text(encoding="utf-8")

        for token in (
            '"short_label"',
            '"help_text"',
            '"rule_taxonomy"',
            '"strictness"',
            '"unavailable_reason"',
        ):
            self.assertIn(token, helper)

    def test_patch_preview_keeps_persisted_keys_for_backend_labels(self) -> None:
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        metadata_fields_js = (STATIC_ROOT / "assets" / "settings" / "metadataFields.js").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for key in ("RoutingProfile", "RouteThresholdMode", "SizeGuardMode"):
            self.assertIn(f"{key}: settingsBuilderInputValue", review_js)
        for renamed_key in ("ProcessingStrategy", "EnforcementMode", "OutputSizeCheck"):
            self.assertIsNone(re.search(rf"\b{renamed_key}\s*:", review_js))
        self.assertIn("key,", review_js)
        self.assertIn("settingsDisplayLabel(key, field?.label || key)", review_js)
        self.assertIn("function settingsPersistedKeyDisplay", review_js)
        self.assertIn("function settingsPersistedKeyDisplay", metadata_fields_js)
        self.assertIn("Changed persisted keys:", review_js)
        self.assertIn("Unknown persisted keys needing backend validation:", review_js)
        self.assertIn("Preview/save uses persisted keys. Friendly labels are display only and are not saved keys.", review_js)
        self.assertIn("Preview/save uses persisted keys. Friendly labels are display only and are not saved keys.", settings_js)
        self.assertIn("settingsPersistedKeyDisplayList(data.changed_keys || [])", settings_js)
        self.assertIn("settingsPersistedKeyDisplayList(data.removed_keys || [])", settings_js)
        self.assertIn("Active preset:", review_js)
        self.assertIn("Preset scope:", review_js)
        self.assertIn("Backend validation errors are authoritative; this WebView did not save or bypass them.", settings_js)

    def test_label_only_renames_remain_display_only_in_main_settings_and_patch_builders(self) -> None:
        backend = _backend_metadata_by_key()
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        metadata_fields_js = (STATIC_ROOT / "assets" / "settings" / "metadataFields.js").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        video_builder_js = (STATIC_ROOT / "assets" / "settingsView.builders.video.js").read_text(encoding="utf-8")
        patch_sources = review_js + video_builder_js

        self.assertIn("return field?.label || fallback || key;", metadata_fields_js)
        self.assertIn("applySettingsFieldMetadataToControls();", settings_js)
        self.assertIn("patch[key] = readVideoDetailBuilderValue", video_builder_js)
        for key, label in LABEL_ONLY_RENAMES.items():
            with self.subTest(key=key):
                field = backend[key]
                self.assertEqual(field["label"], label)
                self.assertEqual(field["persisted_key"], key)
                if key in EDITOR_BUILDER_KEYS:
                    self.assertRegex(review_js, rf"\b{key}\s*:")
                if key in VIDEO_DETAIL_BUILDER_KEYS:
                    self.assertIn(f'"{key}"', metadata_js)
                    self.assertIn("patch[key]", video_builder_js)
                renamed_identifier = re.sub(r"[^A-Za-z0-9]", "", label)
                self.assertIsNone(re.search(rf"\b{renamed_identifier}\s*:", patch_sources))

    def test_backend_migration_policy_matches_display_label_renames(self) -> None:
        policies = {str(policy["persisted_key"]): policy for policy in LABEL_ONLY_RENAME_POLICIES}

        self.assertEqual(set(policies), set(LABEL_ONLY_RENAMES))
        for key, label in LABEL_ONLY_RENAMES.items():
            with self.subTest(key=key):
                self.assertEqual(_backend_metadata_by_key()[key]["label"], label)
                self.assertEqual(policies[key]["display_label"], label)
                self.assertEqual(policies[key]["status"], "label_only_rename")
                self.assertFalse(policies[key]["accepted_as_persisted_key"])

        self.assertEqual(FRIENDLY_LABEL_PERSISTED_KEY_ALIASES["ProcessingStrategy"], "RoutingProfile")
        self.assertEqual(FRIENDLY_LABEL_PERSISTED_KEY_ALIASES["OutputSizeCheck"], "SizeGuardMode")
        self.assertEqual(FRIENDLY_LABEL_PERSISTED_KEY_ALIASES["EncoderSpeedPreset"], "VideoPreset")

    def test_webview_validation_hints_are_advisory_and_share_backend_alias_policy(self) -> None:
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        self.assertEqual(_settings_friendly_alias_entries(), FRIENDLY_LABEL_PERSISTED_KEY_ALIASES)
        for token in (
            "settingsFriendlyPersistedKeyAliases",
            '"ProcessingStrategy": "RoutingProfile"',
            '"OutputSizeCheck": "SizeGuardMode"',
            '"EncoderSpeedPreset": "VideoPreset"',
        ):
            self.assertIn(token, metadata_js)

        for token in (
            "function settingsPatchLocalValidationHints(changes)",
            "function settingsPatchLocalValidationHintLines(changes)",
            "settingsPatchLocalValidationHintsForKey",
            "settingsAllowedValueHint(field, key, value, context)",
            "settingsNumericConstraintHints(field, key, value, context)",
            "settingsFieldAllowedValues(field)",
            "field.min",
            "field.max",
            "field.step",
            "display label only; use persisted key",
            "Local validation hints (advisory only; backend preview/save remains authoritative):",
        ):
            self.assertIn(token, review_js)

        for token in (
            'apiPost("/api/settings/preview-patch", { changes, ...requestExtras })',
            'apiPost("/api/settings/save-patch", { changes, ...requestExtras, confirm_save: true })',
        ):
            self.assertIn(token, settings_js)

    def test_webview_validation_hints_do_not_replace_backend_preview_or_save_authority(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        patch_review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")

        self.assertIn("const localHintLines = settingsPatchLocalValidationHintLines(changes);", settings_js)
        self.assertIn('"Requesting backend patch preview. This will not save the PSD1."', settings_js)
        self.assertIn("await apiPost", settings_js)
        self.assertIn("Backend preview/save remains authoritative", patch_review_js)
        self.assertNotIn("return settingsPatchLocalValidationHintLines(changes);", settings_js)
        self.assertIn("setText(\"settings-patch-status\", result.ok ? \"Preview ready\" : result.severity || \"Preview failed\");", settings_js)
        self.assertIn("setText(\"settings-patch-status\", result.ok ? \"Saved\" : result.severity || \"Save failed\");", settings_js)

    def test_phase5_completion_gate_webview_surfaces_backend_errors_without_save_authority(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        patch_review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        settings_validation_js = settings_js + patch_review_js
        libraries_js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        wizard_js = (STATIC_ROOT / "assets" / "settingsWizard.js").read_text(encoding="utf-8")

        for token in (
            'apiPost("/api/settings/preview-patch", { changes, ...requestExtras })',
            'apiPost("/api/settings/save-patch", { changes, ...requestExtras, confirm_save: true })',
            'if ((result.errors || []).length) {',
            'lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));',
            "Backend validation errors are authoritative; this WebView did not save or bypass them.",
            "Backend preview/save remains authoritative",
            "settingsPatchLocalValidationHintLines(changes)",
            "is not in backend field metadata loaded by this WebView",
            "display label only; use persisted key",
        ):
            self.assertIn(token, settings_validation_js)

        for token in (
            "previewLibraryProfiles",
            "saveLibraryProfiles",
            "buildPatchFromLibraries",
            "window.writeSettingsPatchJson(patch",
            "Previewing staged LibraryProfiles through backend validation.",
            "Saving staged LibraryProfiles through the backend settings route.",
        ):
            self.assertIn(token, libraries_js)

        for token in (
            'apiPostLocal("/api/settings/wizard/preview", { wizard: collectWizardPayload() })',
            'apiPostLocal("/api/settings/wizard/save", { wizard: collectWizardPayload(), confirm_save: true })',
            "overrides: readRowJson",
            "default_tracking: readRowJson",
        ):
            self.assertIn(token, wizard_js)

    def test_removed_static_label_fallback_cannot_create_editable_keys(self) -> None:
        backend = _backend_metadata_by_key()
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        metadata_fields_js = (STATIC_ROOT / "assets" / "settings" / "metadataFields.js").read_text(encoding="utf-8")
        builder_controls_js = (STATIC_ROOT / "assets" / "settings" / "builderControls.js").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")

        self.assertNotIn("settingsDisplayLabels", metadata_js)
        for key, label in LABEL_ONLY_RENAMES.items():
            with self.subTest(key=key):
                self.assertEqual(backend[key]["label"], label)
        self.assertIn("if (!field || !element) return;", builder_controls_js)
        self.assertIn("return field?.label || fallback || key;", metadata_fields_js)
        self.assertIn("settingsDisplayLabel(key, field?.label || key)", review_js)

    def test_size_target_and_direct_copy_bitrate_labels_are_not_swapped(self) -> None:
        backend = _backend_metadata_by_key()

        self.assertEqual(backend["EncodeThresholdGB"]["label"], "Movie target output size")
        self.assertEqual(backend["EncodeThresholdGB"]["unit"], "GB")
        self.assertIn("GB target output size", backend["EncodeThresholdGB"]["help_text"])
        self.assertIn("not the Mbps max bitrate for direct copy", backend["EncodeThresholdGB"]["help_text"])
        self.assertEqual(backend["TVEncodeThresholdGB"]["label"], "TV target output size")
        self.assertEqual(backend["TVEncodeThresholdGB"]["unit"], "GB")
        self.assertIn("GB target output size", backend["TVEncodeThresholdGB"]["help_text"])
        self.assertIn("not the Mbps max bitrate for direct copy", backend["TVEncodeThresholdGB"]["help_text"])
        self.assertEqual(backend["MovieRoute1080pTargetSizeGB"]["label"], "Movie 1080p target output size")
        self.assertEqual(backend["MovieRoute1440pTargetSizeGB"]["label"], "Movie 1440p target output size")
        self.assertEqual(backend["MovieRoute4KTargetSizeGB"]["label"], "Movie 4K target output size")
        self.assertEqual(backend["TVRoute1080pTargetSizeGB"]["label"], "TV 1080p target output size")
        self.assertEqual(backend["TVRoute1440pTargetSizeGB"]["label"], "TV 1440p target output size")
        self.assertEqual(backend["TVRoute4KTargetSizeGB"]["label"], "TV 4K target output size")
        self.assertIn("known-height movie sources", backend["MovieRoute1440pTargetSizeGB"]["help_text"])
        self.assertIn("known-height TV sources", backend["TVRoute1440pTargetSizeGB"]["help_text"])
        self.assertEqual(backend["MovieRouteMaxVideoBitrateMbps"]["label"], "Movie fallback max bitrate")
        self.assertEqual(backend["MovieRouteMaxVideoBitrateMbps"]["unit"], "Mbps")
        self.assertIn("Fallback movie bitrate cap", backend["MovieRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertIn("source height is unknown", backend["MovieRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertEqual(backend["TVRouteMaxVideoBitrateMbps"]["label"], "TV fallback max bitrate")
        self.assertEqual(backend["TVRouteMaxVideoBitrateMbps"]["unit"], "Mbps")
        self.assertIn("Fallback TV bitrate cap", backend["TVRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertIn("source height is unknown", backend["TVRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertEqual(backend["Route1080pBucketMaxHeight"]["label"], "Legacy 1080p bucket max height")
        self.assertIn("Compatibility pixel height", backend["Route1080pBucketMaxHeight"]["help_text"])
        self.assertEqual(backend["Route1080pMaxVideoBitrateMbps"]["unit"], "Mbps")
        self.assertEqual(backend["Route4KBucketMinHeight"]["unit"], "pixels")
        self.assertEqual(backend["Route4KMaxVideoBitrateMbps"]["unit"], "Mbps")

    def test_phase3e_help_text_disambiguates_routing_encode_and_publish_copy(self) -> None:
        backend = _backend_metadata_by_key()
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        libraries_js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        self.assertIn("Used before processing to decide copy/remux versus encode.", backend["RouteThresholdMode"]["help_text"])
        self.assertNotIn("threshold", backend["RouteThresholdMode"]["help_text"].lower())
        self.assertIn("Checked after encode.", backend["SizeGuardMode"]["help_text"])
        self.assertIn("Warns but does not block", backend["SizeGuardMode"]["help_text"])
        self.assertIn("Blocks publish when configured to block", backend["SizeGuardMode"]["help_text"])
        self.assertIn("Applies only when encoding is required.", backend["EncodeTuningPreset"]["help_text"])
        self.assertIn("Applies only when encoding is required.", backend["VideoPreset"]["help_text"])

        for source in (metadata_js, libraries_js, html):
            with self.subTest(source=source[:24]):
                self.assertNotIn("Compatibility advisory", source)
                self.assertNotIn("fallback tuning", source)

        for token in (
            "Bitrate strict, size flexible",
            "Warn only",
            "Block publish",
            "direct-copy allowlists and fallback encode controls",
        ):
            self.assertIn(token, metadata_js + libraries_js + html)

    def test_representative_backend_defaults_match_js_fallbacks(self) -> None:
        backend = _backend_metadata_by_key()

        for key in REPRESENTATIVE_DEFAULT_KEYS:
            with self.subTest(key=key):
                default_value = backend[key].get("default_value")
                self.assertIsNotNone(default_value)
                fallback = _settings_builder_fallback_default(key)
                self.assertIsNotNone(fallback)
                self.assertEqual(_normalize_js_literal(fallback), default_value)


if __name__ == "__main__":
    unittest.main()

