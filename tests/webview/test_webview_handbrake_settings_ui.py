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
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
    "MovieRoute1080pTargetSizeGB",
    "MovieRoute1440pTargetSizeGB",
    "MovieRoute4KTargetSizeGB",
    "TVRoute1080pTargetSizeGB",
    "TVRoute1440pTargetSizeGB",
    "TVRoute4KTargetSizeGB",
    "Route1080pUpperHeightTolerancePercent",
    "Route1080pMaxVideoBitrateMbps",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route1440pMaxVideoBitrateMbps",
    "Route4KLowerHeightTolerancePercent",
    "Route4KMaxVideoBitrateMbps",
}
VIDEO_DETAIL_BUILDER_KEYS = {
    "EncodeLadder",
    "VideoCodec",
    "EncoderBackend",
    "OutputContainer",
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
    def test_settings_tabs_follow_operator_workflow_grouping(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        expected_order = [
            "Status",
            "Guided Setup",
            "Paths &amp; Safety",
            "Routing &amp; Size",
            "Media Output",
            "Publish &amp; Recovery",
            "Naming",
            "Queue &amp; Runtime",
            "Evidence",
        ]
        cursor = -1
        for label in expected_order:
            position = html.index(f">{label}</button>")
            self.assertGreater(position, cursor)
            cursor = position

        for tab in (
            'data-settings-tab="status"',
            'data-settings-tab="guided-setup"',
            'data-settings-tab="paths-safety"',
            'data-settings-tab="routing-size"',
            'data-settings-tab="media-output"',
            'data-settings-tab="publish-recovery"',
            'data-settings-tab="naming"',
            'data-settings-tab="queue-runtime"',
            'data-settings-tab="advanced-evidence"',
        ):
            self.assertIn(tab, html)

        for retired_tab in (
            ">Summary / Effective Decision</button>",
            ">Routing</button>",
            ">Dimensions</button>",
            ">Filters</button>",
            ">Video</button>",
            ">Audio</button>",
            ">Subtitles</button>",
            ">Container</button>",
            ">Verification / Publish</button>",
            ">Presets</button>",
            ">Rename</button>",
            ">Advanced</button>",
            ">Video / Audio / Subtitles</button>",
            ">Container / Output Size Check</button>",
            ">Size / Bitrate Guards</button>",
            ">Wizard</button>",
            ">Rename Filters</button>",
            ">Source / Compatibility</button>",
            ">System</button>",
            'data-settings-tab="editor"',
            'data-settings-tab="dimensions"',
            'data-settings-tab="filters"',
            'data-settings-tab="video"',
            'data-settings-tab="audio"',
            'data-settings-tab="subtitles"',
            'data-settings-tab="container"',
            'data-settings-tab="paths"',
            'data-settings-tab="presets"',
            'data-settings-tab="rename"',
            'data-settings-tab="advanced"',
            'data-settings-tab="media"',
            'data-settings-tab="container-size"',
            'data-settings-tab="size-bitrate"',
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
            'formatSettingsSummaryValue("MovieRoute1080pTargetSizeGB"',
            'formatSettingsSummaryValue("TVRoute1080pTargetSizeGB"',
            'formatSettingsSummaryValue("Route1080pMaxVideoBitrateMbps"',
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
            "function wizardCapabilityFactsText(data)",
            'label: "Capability facts"',
            'label: "Hardware backends"',
            'label: "CPU fallbacks"',
            'return "Review Policy";',
            'if (label === "Review Policy")',
            'apiPostLocal("/api/settings/wizard/preview", { wizard: collectWizardPayload() })',
            'apiPostLocal("/api/settings/wizard/save", { wizard: collectWizardPayload(), confirm_save: true })',
        ):
            self.assertIn(token, wizard_js)

        toolchain_block = re.search(
            r"if \(state\.currentStep === 2\) \{(?P<body>.*?)\n    \}\n    if \(state\.currentStep === 3\)",
            wizard_js,
            re.S,
        )
        self.assertIsNotNone(toolchain_block)
        toolchain_body = toolchain_block.group("body")
        self.assertIn('return "Review Policy";', toolchain_body)
        self.assertNotIn('return "Preview Config";', toolchain_body)
        self.assertIn(
            '} else if (label === "Review Policy") {\n'
            '      setCurrentStep(3);\n'
            '    } else if (label === "Save & Reload")',
            wizard_js,
        )

    def test_settings_deployment_action_path_is_visible_and_backend_owned(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        wizard_js = (STATIC_ROOT / "assets" / "settingsWizard.js").read_text(encoding="utf-8")

        for token in (
            "settings-deployment-path-panel",
            "Deployment Path",
            "settings-deployment-start-button",
            "settings-deployment-verify-button",
            "settings-deployment-repair-button",
            "settings-deployment-launch-button",
            "settings-deployment-action-status",
        ):
            self.assertIn(token, html)

        for token in (
            "function bindDeploymentActionPath()",
            'byIdLocal("settings-deployment-start-button")?.addEventListener("click", openWizard)',
            'byIdLocal("settings-deployment-verify-button")?.addEventListener("click", verifyDeploymentSettings)',
            'byIdLocal("settings-deployment-repair-button")?.addEventListener("click", showDeploymentRepairGuidance)',
            'byIdLocal("settings-deployment-launch-button")?.addEventListener("click", openDeploymentLaunchReadiness)',
            'document.getElementById("settings-validate-button")?.click();',
            'window.showPage("launch");',
            'window.mediaPipelineLaunchView?.activateLaunchTab?.("readiness");',
            "Repair guidance is read-only",
        ):
            self.assertIn(token, wizard_js)

        forbidden = [
            "/api/settings/save-patch",
            "/api/settings/wizard/save",
            "/api/pipeline/start",
            "apiPostLocal(",
        ]
        repair_block = re.search(
            r"function showDeploymentRepairGuidance\(\) \{(?P<body>.*?)\n  \}",
            wizard_js,
            re.S,
        )
        self.assertIsNotNone(repair_block)
        for token in forbidden:
            self.assertNotIn(token, repair_block.group("body"))

    def test_encoder_capability_report_is_read_only_settings_evidence(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        video_builder_js = (STATIC_ROOT / "assets" / "settingsView.builders.video.js").read_text(encoding="utf-8")

        for token in (
            "Encoder Capability Evidence",
            'id="settings-encoder-capability-status"',
            'id="settings-encoder-capability-summary"',
            'id="settings-encoder-capability-rows"',
            "No encoder capability rows are loaded.",
            "read-only annotations from backend diagnostic evidence",
            "unavailable rows do not remove saved choices",
        ):
            self.assertIn(token, html)

        for token in (
            "encoder_capability_report",
            "function settingsEncoderCapabilityReport",
            "function settingsEncoderCapabilityActivationLines",
            "function settingsEncoderCapabilityHardwareRuntimeLines",
            "function renderSettingsEncoderCapabilityReport",
            "settingsEncoderCapabilitySummaryLines",
            "Descriptor activation: active=",
            "Hardware runtime proof:",
            "runtime skipped=",
            "Active hardware descriptors without runtime proof",
            "Available but not active for descriptor-owned attempts",
            "descriptor flags active",
            "descriptor flags inactive",
            "Read-only annotation: dropdown choices stay visible",
            "backend Save and encode planning remain authoritative",
            "Unavailable",
            "Available",
        ):
            self.assertIn(token, video_builder_js)

        self.assertIn("renderSettingsEncoderCapabilityReport(lastSettings);", settings_js)
        self.assertIn("getLastSettings,", settings_js)

        render_block = re.search(
            r"function renderSettingsEncoderCapabilityReport\(settings = getLastSettings\(\)\) \{(?P<body>.*?)\n    \}",
            video_builder_js,
            re.S,
        )
        self.assertIsNotNone(render_block)
        for forbidden in ("apiPost(", "apiGet(", "writeSettingsPatchJson", "settingsBuilderInputValue"):
            self.assertNotIn(forbidden, render_block.group("body"))

    def test_routing_labels_are_visible_without_taxonomy_badges(self) -> None:
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")
        review_js = (STATIC_ROOT / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        builder_controls_js = (STATIC_ROOT / "assets" / "settings" / "builderControls.js").read_text(encoding="utf-8")

        for token in (
            "Library goal",
            "Saved routing profile",
            "What forces an encode?",
            "Encode trigger",
            "settings-route-trigger-summary",
            "TV / Movie targets by height",
            "Target GB is the encoded output budget",
            "Encoded output size (GB)",
            "Movie 1080p encoded output size in GB",
            "TV 1080p encoded output size in GB",
            "Movie 1440p encoded output size in GB",
            "TV 1440p encoded output size in GB",
            "Movie 4K encoded output size in GB",
            "TV 4K encoded output size in GB",
            "Direct-copy limits",
            "Max Mbps",
            "If constant",
            "30m TV",
            "2h movie",
            "Height range",
            "Derived",
            "tolerance",
            "ends at",
            "starts at",
            "Derived height range",
            "Editable route height slider by bucket",
            "TV and movie route target bucket editor",
            "settings-route-range-rail",
            "settings-route-height-slider",
            "settings-route-slider-labels",
            "settings-route-slider",
            "settings-route-slider-track",
            "settings-route-slider-fill-1080p",
            "settings-route-slider-fill-1440p",
            "settings-route-slider-fill-4k",
            'id="settings-height-1440p-range" class="visually-hidden"',
            "settings-route-slider-thumb",
            "settings-route-slider-hit",
            "settings-route-boundary-1080p-end-input",
            "settings-route-boundary-4k-start-input",
            "data-route-drag-boundary",
            "1080p upper route height boundary",
            "4K lower route height boundary",
            "settings-route-target-editor",
            "settings-route-bucket-card",
            "settings-route-bucket-grid",
            "settings-route-card-range-1080p",
            "settings-route-card-range-1440p",
            "settings-route-card-range-4k",
            "uses &lt;=1200p",
            "uses 1201-1799p",
            "uses &gt;=1800p",
            "settings-route-consequence-summary",
            "If encoded output is too large",
            "Oversize result",
            "Oversize result descriptions",
            "If an automatic size/bitrate-threshold encode grows past the buffer, try safe remux/direct copy.",
            "Stop an oversized encode before publish",
            "Record the size overage and continue",
            "Encode target calculation",
            "Encode target calculation descriptions",
            "Uses TV balanced for TV sources and movie balanced for movie sources.",
            "One step smaller/softer than the base quality, with 90M maxrate and 180M buffer.",
            "Two steps smaller/softer than the base quality, with 80M maxrate and 160M buffer.",
            "Uses the configured base quality unchanged, with 120M maxrate and 240M buffer.",
            "One step cleaner/larger than the base quality, with 160M maxrate and 320M buffer.",
            "conservative encoder flags for broader Plex playback",
            "Video encoder",
            "settings-routing-video-codec-readout",
            "settings-routing-output-container-readout",
            "Movie 1080p encoded output size in GB",
            "TV 1080p encoded output size in GB",
            "Movie 1440p encoded output size in GB",
            "TV 1440p encoded output size in GB",
            "Movie 4K encoded output size in GB",
            "TV 4K encoded output size in GB",
            "TV / Movie targets by height",
            "settings-builder-1080p-route-bitrate",
            "Bitrate strict, size flexible",
            "Target size strict",
            "Direct-copy bitrate strict",
            "Block publish",
            "NVENC tuning bundle descriptions",
            "Default HEVC NVENC bundle: VBR, 60-frame lookahead, spatial and temporal AQ",
            "raising AQ strength for larger/slower encodes",
            "shorter 20-frame lookahead, temporal AQ off",
            "disabled multipass, 2 B-frames, and low-latency tune",
            "fragile hardware or Plex compatibility",
            "passes raw ExtraVideoFlags to FFmpeg exactly as entered",
        ):
            self.assertIn(token, html)

        self.assertNotIn("settings-route-target-table", html)
        self.assertNotIn("settings-route-target-wrap", html)

        for token in (
            'id="settings-builder-1440p-lower-tolerance" type="hidden"',
            'id="settings-builder-1440p-upper-tolerance" type="hidden"',
            'id="settings-boundary-1080p-end" type="hidden"',
            'id="settings-boundary-1440p-start" type="hidden"',
            'id="settings-boundary-1440p-end" type="hidden"',
            'id="settings-boundary-4k-start" type="hidden"',
            'id="settings-builder-1080p-upper-tolerance" type="hidden"',
            'id="settings-builder-4k-lower-tolerance" type="hidden"',
            'data-settings-preserve-input-type="true"',
            'id="settings-route-boundary-1080p-end-input" type="number" min="1080" max="1439" step="1" value="1200"',
            'id="settings-route-boundary-4k-start-input" type="number" min="1441" max="2160" step="1" value="1800"',
            'id="settings-bitrate-estimate-1080p"',
            'id="settings-bitrate-estimate-1440p"',
            'id="settings-bitrate-estimate-4k"',
        ):
            self.assertIn(token, html)

        for token in (
            'id="settings-builder-1080p-upper-tolerance" type="hidden" min="0" max="33.240741" step="1"',
            'id="settings-builder-4k-lower-tolerance" type="hidden" min="0" max="33.287037" step="1"',
        ):
            self.assertIn(token, html)

        for token in (
            "Movie GB",
            "TV GB",
            "1080p +",
            "Derived buffer",
            "4K -",
            'id="settings-builder-1080p-upper-tolerance" type="number"',
            'id="settings-builder-4k-lower-tolerance" type="number"',
        ):
            self.assertNotIn(token, html)

        for token in (
            'id="settings-builder-1080p-upper-tolerance-readout">11%</output>',
            'id="settings-builder-1440p-lower-tolerance-readout">17%</output>',
            'id="settings-builder-1440p-upper-tolerance-readout">25%</output>',
            'id="settings-builder-4k-lower-tolerance-readout">17%</output>',
        ):
            self.assertIn(token, html)

        editor_start = html.index('<div class="settings-tab-pane" data-settings-tab="routing-size">')
        active_policy_start = html.index("<h2>Active Policy</h2>", editor_start)
        routing_builder_html = html[editor_start:active_policy_start]
        media_output_start = html.index('<div class="settings-tab-pane" data-settings-tab="media-output">')
        queue_runtime_start = html.index('<div class="settings-tab-pane" data-settings-tab="queue-runtime">')
        media_output_html = html[media_output_start:queue_runtime_start]

        self.assertNotIn('<details class="settings-advanced-disclosure">', routing_builder_html)
        self.assertNotIn('id="settings-builder-video-codec"', routing_builder_html)
        self.assertNotIn('id="settings-builder-output-container"', routing_builder_html)
        self.assertIn('id="settings-builder-video-codec"', media_output_html)
        self.assertIn('id="settings-builder-output-container"', media_output_html)

        for token in (
            "Processing Strategy",
            "Enforcement Mode",
            "Output Size Check",
            "Encoder Quality Preset",
            "Encode Target Mode",
            "Hard route gate",
            "Post-encode guard",
            "Direct-copy cap Mbps",
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
            "setRouteFirstBoundary",
            "setRouteSecondBoundary",
            "renderRouteConsequenceSummary",
            "renderRouteAdvancedSummary",
            "renderRouteBitrateSizeEstimates",
            "routeEstimatedSizeGb",
            "routeFormatDisplayPercent",
            "settingsBuilderPreciseInputValue",
            "routePreciseValue",
            "routeDisplayValue",
            "syncRouteSliderVisuals",
            "routeRailHeightFromPointer",
            "bindRouteRangeRailControls",
            "applyRouteRailBoundaryHeight",
            "routeRailStartDrag",
            "routeRailApplyDrag",
            "settings-route-boundary-1080p-end-input",
            "settings-route-boundary-4k-start-input",
            "settings-route-card-range-1080p",
            "settings-route-card-range-1440p",
            "settings-route-card-range-4k",
            "settings-boundary-1080p-end",
            "settings-boundary-1440p-start",
            "settings-boundary-1440p-end",
            "settings-boundary-4k-start",
        ):
            self.assertIn(token, review_js)

        self.assertIn("settingsPreserveInputType", builder_controls_js)

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
        self.assertIn("Prepares the values in this Video builder for Save Settings.", html)
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
        self.assertIn('["EncoderBackend", "settings-builder-encoder-backend", "select"]', metadata_js)
        self.assertIn('["VideoQuality", "settings-video-quality", "quality_slider"]', metadata_js)
        self.assertIn('id="settings-builder-encoder-backend"', html)
        self.assertIn(
            'setVideoDetailBuilderControl("settings-builder-encoder-backend", "EncoderBackend", "select", "auto")',
            builder_js,
        )
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
            "Local validation hints (advisory only; backend Save remains authoritative):",
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
        self.assertIn("Backend Save remains authoritative", patch_review_js)
        self.assertNotIn("return settingsPatchLocalValidationHintLines(changes);", settings_js)
        self.assertIn("settingsResultStatusLabel(result, \"Preview ready\", \"Preview failed\")", settings_js)
        self.assertIn("settingsResultStatusLabel(result, \"Saved\", \"Save failed\")", settings_js)

    def test_settings_patch_validation_hints_are_namespace_only_exports(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        self.assertIn("settingsPatchLocalValidationHints, settingsPatchLocalValidationHintLines,", settings_js)
        self.assertNotIn("window.settingsPatchLocalValidationHints =", settings_js)
        self.assertNotIn("window.settingsPatchLocalValidationHintLines =", settings_js)

    def test_settings_runtime_restart_helpers_are_namespace_only_exports(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")
        settings_wizard_js = (STATIC_ROOT / "assets" / "settingsWizard.js").read_text(encoding="utf-8")

        self.assertIn(
            "settingsRuntimeRestartConfirmationLine, settingsRuntimeRestartNoticeLines, maybeShowSettingsRuntimeRestartNotice,",
            settings_js,
        )
        self.assertIn("window.mediaPipelineSettingsView?.settingsRuntimeRestartConfirmationLine?.()", settings_wizard_js)
        self.assertIn("window.mediaPipelineSettingsView.settingsRuntimeRestartNoticeLines(result)", settings_wizard_js)
        self.assertNotIn("window.settingsRuntimeRestartConfirmationLine =", settings_js)
        self.assertNotIn("window.settingsRuntimeRestartNoticeLines =", settings_js)

    def test_settings_ocr_path_evidence_helpers_are_namespace_only_exports(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for helper in (
            "settingsBdpgsOcrPathEvidence",
            "settingsBdpgsOcrPathEvidenceStatus",
            "settingsBdpgsOcrPathEvidenceLines",
            "renderSettingsBdpgsOcrPathEvidence",
            "settingsVobSubOcrPathEvidence",
            "settingsVobSubOcrPathEvidenceStatus",
            "settingsVobSubOcrPathEvidenceLines",
            "renderSettingsVobSubOcrPathEvidence",
        ):
            self.assertIn(helper, settings_js)
            self.assertNotIn(f"window.{helper} =", settings_js)

    def test_settings_audio_subtitle_builder_helpers_are_namespace_only_exports(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for helper in (
            "syncSubtitleSettingsBuilderFromConfig",
            "collectSubtitleSettingsBuilderPatch",
            "applySubtitleSettingsBuilderToPatch",
            "renderSubtitleSettingsBuilderGuidance",
            "markSubtitleSettingsBuilderDirty",
            "syncAudioSettingsBuilderFromConfig",
            "collectAudioSettingsBuilderPatch",
            "applyAudioSettingsBuilderToPatch",
            "renderAudioSettingsBuilderGuidance",
            "markAudioSettingsBuilderDirty",
        ):
            self.assertIn(helper, settings_js)
            self.assertNotIn(f"window.{helper} =", settings_js)

    def test_settings_safety_lock_helpers_are_namespace_only_exports(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for helper in (
            "settingsSafetyLockRows",
            "settingsSafetyLockStatus",
            "settingsSafetyLockSummaryLines",
            "renderSettingsSafetyLocks",
        ):
            self.assertIn(helper, settings_js)
            self.assertNotIn(f"window.{helper} =", settings_js)

    def test_settings_raw_triage_helpers_are_namespace_only_exports(self) -> None:
        settings_js = (STATIC_ROOT / "assets" / "settingsView.js").read_text(encoding="utf-8")

        for helper in (
            "settingsRawTriageRows",
            "settingsRawTriageStatus",
            "settingsRawTriageSummaryLines",
            "settingsRawTriageDetailLines",
            "renderSettingsRawTriage",
        ):
            self.assertIn(helper, settings_js)
            self.assertNotIn(f"window.{helper} =", settings_js)

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
            "Backend Save remains authoritative",
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

        for key, label in LABEL_ONLY_RENAMES.items():
            with self.subTest(key=key):
                self.assertEqual(backend[key]["label"], label)
        self.assertIn("if (!field || !element) return;", builder_controls_js)
        self.assertIn("return field?.label || fallback || key;", metadata_fields_js)
        self.assertIn("settingsDisplayLabel(key, field?.label || key)", review_js)

    def test_size_target_and_direct_copy_bitrate_labels_are_not_swapped(self) -> None:
        backend = _backend_metadata_by_key()

        self.assertEqual(backend["MovieRoute1080pTargetSizeGB"]["label"], "Movie 1080p target output size")
        self.assertEqual(backend["MovieRoute1080pTargetSizeGB"]["unit"], "GB")
        self.assertEqual(backend["MovieRoute1440pTargetSizeGB"]["label"], "Movie 1440p target output size")
        self.assertEqual(backend["MovieRoute4KTargetSizeGB"]["label"], "Movie 4K target output size")
        self.assertEqual(backend["TVRoute1080pTargetSizeGB"]["label"], "TV 1080p target output size")
        self.assertEqual(backend["TVRoute1080pTargetSizeGB"]["unit"], "GB")
        self.assertEqual(backend["TVRoute1440pTargetSizeGB"]["label"], "TV 1440p target output size")
        self.assertEqual(backend["TVRoute4KTargetSizeGB"]["label"], "TV 4K target output size")
        self.assertIn("Unknown-height movies use this 1080p target", backend["MovieRoute1080pTargetSizeGB"]["help_text"])
        self.assertIn("Unknown-height TV uses this 1080p target", backend["TVRoute1080pTargetSizeGB"]["help_text"])
        self.assertIn("known-height movie sources", backend["MovieRoute1440pTargetSizeGB"]["help_text"])
        self.assertIn("known-height TV sources", backend["TVRoute1440pTargetSizeGB"]["help_text"])
        self.assertEqual(backend["Route1080pMaxVideoBitrateMbps"]["unit"], "Mbps")
        self.assertEqual(backend["Route4KMaxVideoBitrateMbps"]["unit"], "Mbps")

    def test_phase3e_help_text_disambiguates_routing_encode_and_publish_copy(self) -> None:
        backend = _backend_metadata_by_key()
        metadata_js = (STATIC_ROOT / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")
        libraries_js = (STATIC_ROOT / "assets" / "settingsLibraries.js").read_text(encoding="utf-8")
        html = (STATIC_ROOT / "partials" / "page-settings.html").read_text(encoding="utf-8")

        self.assertIn("Used before processing to decide copy/remux versus encode.", backend["RouteThresholdMode"]["help_text"])
        self.assertNotIn("threshold", backend["RouteThresholdMode"]["help_text"].lower())
        self.assertIn("Checked after encode.", backend["SizeGuardMode"]["help_text"])
        self.assertIn("Warn-only records oversized output", backend["SizeGuardMode"]["help_text"])
        self.assertIn("Strict blocks publish", backend["SizeGuardMode"]["help_text"])
        self.assertIn("Fallback remux applies existing growth buffers", backend["SizeGuardMode"]["help_text"])
        self.assertIn("Forced route overrides warn only", backend["SizeGuardMode"]["help_text"])
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
            "Try remux fallback",
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
