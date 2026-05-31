from __future__ import annotations

import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from app.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline_desktop_app.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.handler import build_local_api_handler_class
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from mediapipeline_desktop_app.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend
from mediapipeline_desktop_app.models import ResolvedPaths, Snapshot
from DesktopApp.tests.test_application_facade import (
    DummyFacadeService,
    DummyProc,
    DummyWorkflowFacadeService,
    _render_static_index_html,
    _resolved,
)


def _read_queue_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "queueView.summary.js",
            "queueView.review.js",
            "queueView.detail.js",
            "queueView.launch.js",
            "queueView.js",
        ]
    )


def _read_diagnostics_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "diagnosticsView.activejobs.js",
            "diagnosticsView.log.js",
            "diagnosticsView.investigation.js",
            "diagnosticsView.js",
        ]
    )


def _read_command_history_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "commandHistory/formatters.js",
            "commandHistory/diagnostics.js",
            "commandHistory.js",
        ]
    )


def _read_completed_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "completed/table.js",
            "completedView.review.js",
            "completedView.evidence.js",
            "completedView.proof.js",
            "completedView.js",
        ]
    )


def _read_pending_publish_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "pendingPublish/details.js",
            "pendingPublish/summary.js",
            "pendingPublishView.drain.js",
            "pendingPublishView.confidence.js",
            "pendingPublishView.recovery.js",
            "pendingPublishView.js",
        ]
    )


def _read_settings_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "settings/backendResult.js",
            "settings/patchReview.js",
            "settings/policyImpact.js",
            "settingsView.rawTriage.js",
            "settingsView.js",
        ]
    )


def _read_rename_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "rename/preview.js",
            "rename/applyReadiness.js",
            "rename/applyResult.js",
            "renameView.js",
        ]
    )


def _assert_namespace_export(testcase: unittest.TestCase, source: str, namespace: str, symbol: str) -> None:
    testcase.assertRegex(
        source,
        rf"window\.{re.escape(namespace)}\s*=\s*\{{[\s\S]*?\b{re.escape(symbol)}\b\s*(?:,|:|\n\s*\}})",
    )


class ApplicationFacadeWebStaticTests(unittest.TestCase):
    def test_web_and_tauri_shell_reference_all_local_api_contract_routes(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        asset_text = _render_static_index_html(static_root)
        for asset in (static_root / "assets").glob("*.js"):
            asset_text += "\n" + asset.read_text(encoding="utf-8")
        tauri_lib = desktop_root / "tauri_shell" / "src-tauri" / "src" / "lib.rs"
        shell_text = tauri_lib.read_text(encoding="utf-8") if tauri_lib.exists() else ""
        combined = asset_text + "\n" + shell_text

        route_paths = [route["path"] for route in LOCAL_API_READ_ROUTE_CONTRACT + LOCAL_API_COMMAND_ROUTE_CONTRACT]
        missing = [path for path in route_paths if path not in combined]

        self.assertEqual(missing, [])

    def test_web_controls_expose_local_api_command_allowlists(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        app_js = (static_root / "assets" / "app.js").read_text(encoding="utf-8")
        reports_js = (static_root / "assets" / "reportsView.js").read_text(encoding="utf-8")
        command_routes = {str(route["path"]): route for route in LOCAL_API_COMMAND_ROUTE_CONTRACT}

        def row_open_targets(scope: str) -> set[str]:
            key = f'"{scope}"' if "-" in scope else scope
            pattern = rf"{re.escape(key)}:\s*\{{.*?actions:\s*\[(.*?)\],\s*onOpen"
            match = re.search(pattern, app_js, re.S)
            self.assertIsNotNone(match, f"row open action config missing for {scope}")
            return set(re.findall(r'target:\s*"([^"]+)"', match.group(1)))

        diagnostics_targets = set(re.findall(r'data-open-diagnostics="([^"]+)"', html))
        report_target_match = re.search(r"function reportOpenTarget\(key\).*?const targets = \{(.*?)\};", reports_js, re.S)
        self.assertIsNotNone(report_target_match)
        diagnostics_targets.update(re.findall(r':\s*"([^"]+)"', report_target_match.group(1)))
        self.assertEqual(set(command_routes["/api/diagnostics/open"]["allowed_targets"]) - diagnostics_targets, set())

        queue_targets = row_open_targets("queue")
        self.assertEqual(set(command_routes["/api/queue/open"]["allowed_targets"]) - queue_targets, set())
        queue_excluded_targets = row_open_targets("queue-excluded")
        self.assertEqual(set(command_routes["/api/queue/open"]["allowed_targets"]) - queue_excluded_targets, set())
        self.assertEqual(set(command_routes["/api/queue/open"]["allowed_row_scopes"]), {"runnable", "excluded"})

        completed_targets = row_open_targets("completed")
        self.assertEqual(set(command_routes["/api/completed/open"]["allowed_targets"]) - completed_targets, set())

        pending_targets = row_open_targets("pending")
        self.assertEqual(set(command_routes["/api/pending-publish/open"]["allowed_targets"]) - pending_targets, set())
        self.assertEqual(set(command_routes["/api/pending-publish/recovery-plan"]["allowed_scopes"]), {"all", "selected"})

        control_actions = set(re.findall(r'data-control-action="([^"]+)"', html))
        self.assertEqual(set(command_routes["/api/pipeline/control"]["allowed_actions"]) - control_actions, set())

        mode_match = re.search(r'<select id="pipeline-start-mode">(.*?)</select>', html, re.S)
        self.assertIsNotNone(mode_match)
        mode_options = set(re.findall(r'<option value="([^"]*)"', mode_match.group(1)))
        self.assertEqual(set(command_routes["/api/pipeline/start"]["allowed_modes"]) - mode_options, set())

        schedule_match = re.search(r'<select id="pipeline-start-schedule-override">(.*?)</select>', html, re.S)
        self.assertIsNotNone(schedule_match)
        schedule_options = set(re.findall(r'<option value="([^"]*)"', schedule_match.group(1)))
        self.assertEqual(set(command_routes["/api/pipeline/start"]["allowed_schedule_overrides"]) - schedule_options, set())

    def test_dashboard_quick_controls_stay_simple_and_backend_owned(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        home_match = re.search(
            r'<section class="page is-visible" data-page-panel="home">(.*?)<section class="page" data-page-panel="live">',
            html,
            re.S,
        )
        self.assertIsNotNone(home_match)
        home_html = home_match.group(1)
        for forbidden in [
            "home-pipeline-start-button",
            "home-drain-button",
            "home-schedule-toggle-button",
            "Run Controls",
            "Quick Actions",
            "Hard Kill",
            "Publish Parked Outputs",
        ]:
            self.assertNotIn(forbidden, home_html)
        home_actions = set(re.findall(r'data-control-action="([^"]+)"', home_html))
        self.assertEqual(home_actions, {"pause", "stop", "kill"})
        self.assertNotIn('data-control-action="rescan"', home_html)
        self.assertIn("Pause / Resume", home_html)
        self.assertIn("Stop After Current", home_html)
        self.assertIn("Force Stop", home_html)
        self.assertIn("submit backend-owned pipeline control requests", home_html)
        self.assertIn('data-cross-page-target="completed" data-home-promotion-entry', home_html)
        self.assertIn("Promote Files", home_html)
        self.assertIn('id="pipeline-start-button"', html)
        self.assertIn('id="pending-drain-button"', html)
        self.assertIn('data-control-action="kill"', html)

    def test_launch_controls_are_state_aware_and_topbar_kill_is_emergency_only(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        launch_js = (static_root / "assets" / "launchView.js").read_text(encoding="utf-8")
        app_js = (static_root / "assets" / "app.js").read_text(encoding="utf-8")

        self.assertIn('class="danger-button emergency-button topbar-emergency-control"', html)
        self.assertIn('hidden aria-label="Emergency force stop active pipeline"', html)
        self.assertIn("function updateLaunchCommandButtonStates", launch_js)
        self.assertIn("launchPipelineIsActive", launch_js)
        self.assertIn("function launchButtonGate", launch_js)
        self.assertIn("launchBackendPreflightPayloadForTarget", launch_js)
        self.assertIn("launchStartDecisionGate", launch_js)
        self.assertIn("Resolve blocked Backend Preflight checks", launch_js)
        self.assertIn("Resolve blocked Launch Start Summary rows", launch_js)
        self.assertIn("Refresh Backend Preflight before using this start control", launch_js)
        self.assertIn('button.hidden = !active', launch_js)
        self.assertIn('setButtonClass(button, active ? "primary-button" : "secondary-button")', launch_js)
        self.assertIn("window.mediaPipelineLaunchView?.updateLaunchCommandButtonStates", app_js)

    def test_command_surfaces_do_not_treat_backend_rejections_as_success(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        assets_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static" / "assets"
        settings_js = _read_settings_asset_bundle(assets_root)
        launch_js = (assets_root / "launchView.js").read_text(encoding="utf-8")
        helpers_js = (assets_root / "domHelpers.js").read_text(encoding="utf-8")

        self.assertIn('setText("settings-patch-status", result.ok ? "Saved" : result.severity || "Save failed")', settings_js)
        self.assertIn("lastSettingsPatchSaveEvidence = {", settings_js)
        self.assertIn("signature,", settings_js)
        self.assertIn("result,", settings_js)
        self.assertIn("if (result.ok) await refreshAll();", settings_js)
        self.assertNotIn('setText("settings-patch-status", "Saved")', settings_js)

        self.assertIn('if (result.ok) return result.severity === "warning" ? "Warning" : successLabel;', launch_js)
        self.assertIn('return result.severity || "Blocked";', launch_js)
        self.assertIn('`Result: ${payload.ok ? "ok" : "blocked"}', launch_js)
        self.assertIn('command: "pending_publish.drain"', launch_js)
        self.assertIn('renderLaunchCommandResult("pending-drain-status", "pending-drain-detail", drainResult, request)', launch_js)
        self.assertIn('renderLaunchCommandResult("pipeline-launch-status", "pipeline-launch-detail", result, request)', launch_js)
        self.assertIn("function jsonDetailText", helpers_js)
        self.assertIn("function renderJsonDetail", helpers_js)
        self.assertIn("Read-only structured detail", helpers_js)
        self.assertIn("Backend data JSON", settings_js)
        self.assertIn('renderJsonDetail("pipeline-launch-detail"', launch_js)
        self.assertIn('renderJsonDetail("pending-drain-detail"', launch_js)
        self.assertIn("jsonDetailText({", launch_js)

    def test_ui_polish_error_and_tooltip_guards_are_wired(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        app_js = (static_root / "assets" / "app.js").read_text(encoding="utf-8")
        launch_js = (static_root / "assets" / "launchView.js").read_text(encoding="utf-8")
        helpers_js = (static_root / "assets" / "domHelpers.js").read_text(encoding="utf-8")
        telemetry_js = (static_root / "assets" / "telemetryView.js").read_text(encoding="utf-8")
        progress_js = (static_root / "assets" / "progressView.js").read_text(encoding="utf-8")
        completed_review_js = (static_root / "assets" / "completedView.review.js").read_text(encoding="utf-8")
        completed_proof_js = (static_root / "assets" / "completedView.proof.js").read_text(encoding="utf-8")

        self.assertIn("function applyDefaultActionTooltips", app_js)
        self.assertIn("function renderTelemetrySafely", app_js)
        self.assertIn('recordLocalUiDiagnostic("telemetry.render"', app_js)
        self.assertIn("function launchCommandRootCauseLines", launch_js)
        self.assertIn("Stack traces are intentionally omitted", launch_js)
        self.assertIn("span.title = `Status:", helpers_js)
        self.assertIn("function telemetryCanvasColors", telemetry_js)
        self.assertIn("function telemetryGpuUsagePayload", telemetry_js)
        self.assertIn("desktop_gpu_encoder_usage.v1", telemetry_js)
        self.assertIn("Encoder sessions", telemetry_js)
        self.assertNotIn("#65a7ff", telemetry_js)
        self.assertIn("function progressWorkerPayload", progress_js)
        self.assertIn("function progressWorkerRows", progress_js)
        self.assertIn("desktop_worker_progress.v1", progress_js)
        self.assertIn("Worker progress", progress_js)
        self.assertIn("function progressFfmpegPayload", progress_js)
        self.assertIn("desktop_ffmpeg_progress.v1", progress_js)
        self.assertIn("FFmpeg progress proof", progress_js)
        self.assertIn("function progressEtaPayload", progress_js)
        self.assertIn("desktop_eta.v1", progress_js)
        self.assertIn("No ETA is shown until backend worker progress reports usable percent", progress_js)
        self.assertIn("desktop_validation_state.v1", completed_review_js)
        self.assertIn("Validation state proof", completed_proof_js)
        self.assertIn("does not run ffprobe, hash files, or mark playback accepted", completed_review_js)
        self.assertIn("renderDiagnosticsProgress?.(values.snapshot || lastSnapshot, values.diagnostics || null)", app_js)
        self.assertIn("progressWorkerPayload?.(snapshot, diagnostics)", app_js)
        self.assertIn("CSV rerun stages files by copying to scratch first", html)
        self.assertIn("Custom negative terms are added to the backend rename planner", html)

    def test_tk_legacy_showerror_callers_route_through_structured_helper(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        package_root = desktop_root / "mediapipeline_desktop_app"
        offenders: list[str] = []
        for path in package_root.rglob("*.py"):
            rel = path.relative_to(package_root).as_posix()
            source = path.read_text(encoding="utf-8")
            if "messagebox.showerror" not in source:
                continue
            if rel == "widgets.py":
                continue
            offenders.append(rel)
        self.assertEqual(offenders, [])

    def test_webview_panel_types_and_evidence_panels_are_read_only(self) -> None:
        from html.parser import HTMLParser

        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)

        class PanelParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.panel_stack: list[dict[str, object]] = []
                self.panels: list[dict[str, object]] = []

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                attr_map = {key: value or "" for key, value in attrs}
                if tag == "section" and "panel" in attr_map.get("class", "").split():
                    panel = {"type": attr_map.get("data-panel-type"), "buttons": []}
                    self.panel_stack.append(panel)
                    self.panels.append(panel)
                    return
                if tag == "button" and self.panel_stack:
                    self.panel_stack[-1]["buttons"].append(attr_map)  # type: ignore[index, union-attr]

            def handle_endtag(self, tag: str) -> None:
                if tag == "section" and self.panel_stack:
                    self.panel_stack.pop()

        parser = PanelParser()
        parser.feed(html)
        invalid_types = [panel.get("type") for panel in parser.panels if panel.get("type") not in {"evidence", "interactive"}]
        evidence_buttons = [panel for panel in parser.panels if panel.get("type") == "evidence" and panel.get("buttons")]
        self.assertEqual(invalid_types, [])
        self.assertEqual(evidence_buttons, [])

    def test_webview_page_h1_titles_match_design_reference(self) -> None:
        from html.parser import HTMLParser

        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        expected = {
            "home": "Pipeline Dashboard",
            "live": "Hardware Telemetry",
            "queue": "Processing Queue",
            "completed": "Pipeline Output",
            "pending": "Pending Publish",
            "rename": "Rename Files",
            "launch": "Launch Pipeline",
            "reports": "Reports & Audit",
            "schedule": "Pipeline Schedule",
            "network": "Distributed Workers",
            "maintenance": "Maintenance Tools",
            "diagnostics": "System Diagnostics",
            "libraries": "Library Profiles",
            "settings": "Pipeline Settings",
        }

        class PageTitleParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__(convert_charrefs=True)
                self.current_page = ""
                self.in_h1 = False
                self.buffer: list[str] = []
                self.titles: dict[str, str] = {}

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                attr_map = {key: value or "" for key, value in attrs}
                if tag == "section" and "page" in attr_map.get("class", "").split():
                    self.current_page = attr_map.get("data-page-panel", "")
                if tag == "h1" and self.current_page:
                    self.in_h1 = True
                    self.buffer = []

            def handle_data(self, data: str) -> None:
                if self.in_h1:
                    self.buffer.append(data)

            def handle_endtag(self, tag: str) -> None:
                if tag == "h1" and self.in_h1:
                    self.titles[self.current_page] = "".join(self.buffer).strip()
                    self.in_h1 = False

        parser = PageTitleParser()
        parser.feed(html)
        self.assertEqual(parser.titles, expected)

    def test_settings_subtitle_builder_covers_bdpgs_ocr_path_keys_and_keyword_lists(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        metadata_js = (assets_root / "settingsMetadata.js").read_text(encoding="utf-8")
        subtitle_js = (assets_root / "settingsView.builders.subtitle.js").read_text(encoding="utf-8")
        raw_triage_js = (assets_root / "settingsView.rawTriage.js").read_text(encoding="utf-8")

        self.assertIn('id="settings-subtitle-bdpgs-ocr-tool-path"', html)
        self.assertIn('id="settings-subtitle-bdpgs-ocr-tessdata-path"', html)
        self.assertIn('id="settings-subtitle-vobsub-ocr-tool-path"', html)
        self.assertIn('id="settings-subtitle-sdh-keywords"', html)
        self.assertIn('id="settings-subtitle-supplemental-keywords"', html)
        self.assertNotIn("settings-subtitle-bdpgs-ocr-browse", html)
        self.assertNotIn("settings-subtitle-vobsub-ocr-browse", html)
        self.assertIn('["BdpgsOcrToolPath", "settings-subtitle-bdpgs-ocr-tool-path", "text"]', metadata_js)
        self.assertIn('["BdpgsOcrTessdataPath", "settings-subtitle-bdpgs-ocr-tessdata-path", "text"]', metadata_js)
        self.assertIn('["VobSubOcrToolPath", "settings-subtitle-vobsub-ocr-tool-path", "text"]', metadata_js)
        self.assertIn('["SubSDHTitleKeywords", "settings-subtitle-sdh-keywords", "list"]', metadata_js)
        self.assertIn('["SubSupplementalKeywords", "settings-subtitle-supplemental-keywords", "list"]', metadata_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tool-path", "BdpgsOcrToolPath", "text"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-bdpgs-ocr-tessdata-path", "BdpgsOcrTessdataPath", "text"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-vobsub-ocr-tool-path", "VobSubOcrToolPath", "text"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-sdh-keywords", "SubSDHTitleKeywords", "list"', subtitle_js)
        self.assertIn('setSubtitleBuilderControl("settings-subtitle-supplemental-keywords", "SubSupplementalKeywords", "list"', subtitle_js)
        self.assertIn('if (kind === "text") return String(element.value || "").trim();', subtitle_js)
        self.assertIn('if (kind === "list") return parseSettingsListText(element.value);', subtitle_js)
        self.assertIn("WebView does not browse arbitrary paths, resolve paths, or run OCR.", subtitle_js)
        self.assertIn("WebView does not classify subtitle tracks.", subtitle_js)
        self.assertIn("are covered by the Subtitle builder", raw_triage_js)
        self.assertIn("subtitle keyword builder coverage", raw_triage_js)
        self.assertIn("backend subtitle classification remains authoritative", raw_triage_js)
        self.assertIn("do not add a frontend-owned path picker", raw_triage_js)
        self.assertIn("Any folder picker must be backend-owned and allowlisted", raw_triage_js)

    def test_settings_file_safety_path_browse_is_backend_owned_staging(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        settings_js = (assets_root / "settingsView.js").read_text(encoding="utf-8")
        app_js = (assets_root / "app.js").read_text(encoding="utf-8")
        settings_history_js = (assets_root / "settingsCommandHistory.js").read_text(encoding="utf-8")

        for key, input_id in [
            ("SourceMovies", "settings-file-safety-source-movies"),
            ("SourceTV", "settings-file-safety-source-tv"),
            ("Outsource", "settings-file-safety-outsource"),
            ("LocalBase", "settings-file-safety-local-base"),
        ]:
            with self.subTest(key=key):
                self.assertIn(f'data-settings-path-key="{key}"', html)
                self.assertIn(f'data-settings-path-input="{input_id}"', html)
        self.assertIn('"/api/settings/browse-path"', settings_js)
        self.assertIn('selection_mode: "folder"', settings_js)
        self.assertIn("writes_config", settings_js)
        self.assertIn("stages_only", settings_js)
        self.assertIn("Merge File Safety Patch, then Preview Patch before Save Patch", settings_js)
        self.assertIn("It cannot save settings, launch work, rewrite queue state, publish, rename, delete, or touch media files.", settings_js)
        self.assertIn("[data-settings-path-key]", app_js)
        self.assertIn('command === "settings.browse_path"', settings_history_js)

    def test_web_command_feedback_preserves_backend_warnings_and_errors(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static" / "assets"
        command_history_js = _read_command_history_asset_bundle(static_root)
        diagnostics_bridge_js = (static_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        queue_view_js = _read_queue_asset_bundle(static_root)
        completed_view_evidence_js = (static_root / "completedView.evidence.js").read_text(encoding="utf-8")
        completed_view_js = (static_root / "completedView.js").read_text(encoding="utf-8")
        rename_view_js = _read_rename_asset_bundle(static_root)
        rename_history_view_js = (static_root / "renameHistoryView.js").read_text(encoding="utf-8")
        maintenance_view_js = (static_root / "maintenanceView.js").read_text(encoding="utf-8")
        settings_command_history_js = (static_root / "settingsCommandHistory.js").read_text(encoding="utf-8")
        pending_publish_diagnostics_js = (static_root / "pendingPublishView.diagnostics.js").read_text(encoding="utf-8")
        pending_publish_drain_js = (static_root / "pendingPublishView.drain.js").read_text(encoding="utf-8")
        pending_publish_view_js = (static_root / "pendingPublishView.js").read_text(encoding="utf-8")
        launch_history_view_js = (static_root / "launchHistoryView.js").read_text(encoding="utf-8")
        launch_preflight_view_js = (static_root / "launchView.preflight.js").read_text(encoding="utf-8")
        launch_view_js = (static_root / "launchView.js").read_text(encoding="utf-8")
        diagnostics_view_js = _read_diagnostics_asset_bundle(static_root)
        reports_view_js = (static_root / "reportsView.js").read_text(encoding="utf-8")
        network_view_js = (static_root / "networkView.js").read_text(encoding="utf-8")
        app_js = (static_root / "app.js").read_text(encoding="utf-8")

        self.assertIn("const COMMAND_RESULT_LIST_LIMIT = 5", command_history_js)
        self.assertIn("const COMMAND_RESULT_ITEM_CHARS = 240", command_history_js)
        self.assertIn("function commandResultDisplayMessage", command_history_js)
        self.assertIn("function commandResultFeedbackLines", command_history_js)
        self.assertIn("function commandHistoryCompactEvidenceLine", command_history_js)
        self.assertIn("function commandHistoryDiagnosticLine", command_history_js)
        self.assertIn("function compactCommandHistoryEntries", command_history_js)
        self.assertIn("function compactCommandHistoryBlockText", command_history_js)
        self.assertIn("function renderCompactCommandHistoryBlock", command_history_js)
        self.assertIn("owner=${commandHistoryOwnerPage(item)}", command_history_js)
        self.assertIn("issue=${commandHistoryIssueLevel(item)}", command_history_js)
        self.assertIn("window.commandHistoryCompactEvidenceLine = commandHistoryCompactEvidenceLine", command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "renderCompactCommandHistoryBlock")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryDiagnosticLine")
        self.assertIn("commandHistoryCompactEvidenceLine(entry", settings_command_history_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", rename_history_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", launch_history_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", pending_publish_diagnostics_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", pending_publish_drain_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", queue_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", completed_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", diagnostics_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", reports_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", network_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(item", maintenance_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", launch_preflight_view_js)
        self.assertIn("commandHistoryCompactEvidenceLine(entry", app_js)
        self.assertIn("renderCompactCommandHistoryBlock({", settings_command_history_js)
        self.assertIn("renderCompactCommandHistoryBlock({", launch_history_view_js)
        self.assertIn("renderCompactCommandHistoryBlock({", reports_view_js)
        self.assertIn("renderCompactCommandHistoryBlock({", maintenance_view_js)
        self.assertIn("renderCompactCommandHistoryBlock({", pending_publish_drain_js)
        self.assertIn("renderCompactCommandHistoryBlock: window.mediaPipelineCommandHistory?.renderCompactCommandHistoryBlock", pending_publish_view_js)
        self.assertIn("function commandHistoryIsPendingPublishCommand", command_history_js)
        self.assertIn("function commandHistoryPendingPublishCommandKind", command_history_js)
        self.assertIn("function commandHistoryPendingPublishSuggestedAction", command_history_js)
        self.assertIn("function commandHistoryPendingPublishDataLines", command_history_js)
        self.assertIn("function commandHistoryPendingPublishDigestLines", command_history_js)
        self.assertIn("function commandHistoryPendingPublishEntries", command_history_js)
        self.assertIn("Pending Publish command digest:", command_history_js)
        self.assertIn("commandHistoryPendingPublishDigestLines(commandHistory)", command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryPendingPublishDigestLines")
        self.assertIn("Pending Publish command triage:", command_history_js)
        self.assertIn("Command kind: ${kind}", command_history_js)
        self.assertIn("Read-first order: Last Stderr -> Latest Failure Report -> Pending Publish state.", command_history_js)
        self.assertIn("Open-next order: Pending Publish -> Run Logs -> State Folder", command_history_js)
        self.assertIn("Do not drain yet. Inspect blocker rows in Pending Publish", command_history_js)
        self.assertIn("Treat the drain as failed or incomplete. Refresh Pending Publish", command_history_js)
        self.assertIn("Mutation guardrail: command history never repairs, drains, rewrites, moves, deletes, or publishes files by itself.", command_history_js)
        self.assertIn("function requestCommandDiagnosticsAction", command_history_js)
        self.assertIn("appendDiagnosticsBridgeGroupedButtons(container, actions", command_history_js)
        self.assertIn('datasetPrefix: "commandDiagnostics"', command_history_js)
        self.assertIn('datasetPrefix: "diagnosticsCommandDrilldown"', command_history_js)
        self.assertIn("renderDiagnosticsCommandDrilldown(commandHistory)", command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "renderDiagnosticsCommandDrilldown")
        self.assertIn("function mergeCommandHistory", command_history_js)
        self.assertIn("local: true", command_history_js)
        self.assertIn("raw: payload", command_history_js)
        self.assertIn("raw: entry", command_history_js)
        self.assertIn("commandResultList(payload.warnings)", command_history_js)
        self.assertIn("commandResultList(payload.errors)", command_history_js)
        self.assertIn("commandResultList(entry.warnings)", command_history_js)
        self.assertIn("commandResultList(entry.errors)", command_history_js)
        self.assertIn('Errors: ${errors.join(" | ")}', command_history_js)
        self.assertIn('Warnings: ${warnings.join(" | ")}', command_history_js)
        self.assertIn('row.dataset.status = ["error", "blocked"].includes(issue) ? "blocked" : issue === "warning" ? "warning" : item.ok ? "match" : "blocked"', command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandResultDisplayMessage")
        self.assertIn("window.mediaPipelineDiagnosticsBridge", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgePrimaryAction", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeActionGroups", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeReviewAction", diagnostics_bridge_js)
        self.assertIn("function appendDiagnosticsBridgeButton", diagnostics_bridge_js)
        self.assertIn("Review in Diagnostics", diagnostics_bridge_js)
        self.assertIn("bridge selection does not read files, open paths, mutate queue state, or publish outputs", diagnostics_bridge_js)
        self.assertIn("window.diagnosticsBridgeActions = diagnosticsBridgeActions", diagnostics_bridge_js)

        self.assertIsNotNone(
            re.search(
                r'const result = await apiPost\("/api/queue/open".*?appendCommandResult\(result\);',
                queue_view_js,
                re.S,
            )
        )
        self.assertIsNotNone(
            re.search(
                r'const result = await apiPost\("/api/completed/open".*?appendCommandResult\(result\);',
                completed_view_js,
                re.S,
            )
        )
        self.assertIsNotNone(
            re.search(
                r'const result = await apiPost\("/api/rename/apply".*?appendCommandResult\(visibleResult\);',
                rename_view_js,
                re.S,
            )
        )
        self.assertIn("commandResultDisplayMessage(result) || \"Rename apply failed.\"", rename_view_js)
        self.assertIn("function renderRenamePipelineHandoff", rename_view_js)
        self.assertIn("Rename-to-pipeline handoff:", rename_view_js)
        self.assertIn("renaming changes filenames only", rename_view_js)
        self.assertIn('renameConfigValue(config, "DeleteSourceAfterProcessing", "false")', rename_view_js)
        self.assertNotIn("DeleteOriginalAfterProcessing", rename_view_js)
        self.assertIn("Apply Checked / Selected still rebuilds the plan", rename_view_js)
        self.assertGreaterEqual(
            maintenance_view_js.count('lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));'),
            2,
        )

    def test_web_tables_share_accessible_selection_helpers(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        dom_helpers_js = (assets_root / "domHelpers.js").read_text(encoding="utf-8")
        styles_css = "\n".join(path.read_text(encoding="utf-8") for path in sorted(assets_root.glob("styles*.css")))
        queue_view_js = _read_queue_asset_bundle(assets_root)
        completed_view_evidence_js = (assets_root / "completedView.evidence.js").read_text(encoding="utf-8")
        completed_view_review_js = (assets_root / "completedView.review.js").read_text(encoding="utf-8")
        completed_view_js = _read_completed_asset_bundle(assets_root)
        pending_view_drain_js = (assets_root / "pendingPublishView.drain.js").read_text(encoding="utf-8")
        pending_view_confidence_js = (assets_root / "pendingPublishView.confidence.js").read_text(encoding="utf-8")
        pending_view_js = _read_pending_publish_asset_bundle(assets_root)
        rename_view_js = _read_rename_asset_bundle(assets_root)
        command_history_js = _read_command_history_asset_bundle(assets_root)
        diagnostics_bridge_js = (assets_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        reports_view_js = (assets_root / "reportsView.js").read_text(encoding="utf-8")
        diagnostics_view_js = _read_diagnostics_asset_bundle(assets_root)
        diagnostics_state_js = (assets_root / "diagnosticsStateSummaryView.js").read_text(encoding="utf-8")
        network_view_js = (assets_root / "networkView.js").read_text(encoding="utf-8")
        contract_view_js = (assets_root / "contractView.js").read_text(encoding="utf-8")
        launch_view_risk_js = (assets_root / "launchView.risk.js").read_text(encoding="utf-8")
        launch_view_scope_js = (assets_root / "launchView.scope.js").read_text(encoding="utf-8")
        launch_view_preflight_js = (assets_root / "launchView.preflight.js").read_text(encoding="utf-8")
        launch_view_js = (assets_root / "launchView.js").read_text(encoding="utf-8")
        app_js = (assets_root / "app.js").read_text(encoding="utf-8")

        for node_id in [
            "command-table-legend",
            "queue-table-legend",
            "queue-excluded-table-legend",
            "queue-backend-scope-legend",
            "queue-launch-decision-legend",
            "completed-table-legend",
            "completed-history-table-legend",
            "completed-size-evidence-legend",
            "completed-pending-proof-legend",
            "publish-reconciliation-legend",
            "completed-output-acceptance-legend",
            "completed-route-agreement-legend",
            "pending-table-legend",
            "pending-backend-scope-legend",
            "pending-drain-decision-legend",
            "rename-table-legend",
            "failure-table-legend",
            "audit-preview-table-legend",
            "network-worker-table-legend",
            "diagnostics-first-response-legend",
            "diagnostics-state-summary-table-legend",
            "diagnostics-owner-handoff-legend",
            "diagnostics-log-table-legend",
            "active-job-table-legend",
            "diagnostics-command-resolution-legend",
            "launch-settings-intent-legend",
            "launch-scope-reconciliation-legend",
            "launch-start-decision-legend",
            "launch-backend-preflight-legend",
            "api-contract-safety-legend",
            "api-contract-table-legend",
        ]:
            self.assertIn(f'id="{node_id}"', html)

        self.assertIn("function makeRowSelectable", dom_helpers_js)
        self.assertIn('row.dataset.selectableRow = "true"', dom_helpers_js)
        self.assertIn('row.setAttribute("aria-selected"', dom_helpers_js)
        self.assertIn('event.key === "ArrowDown"', dom_helpers_js)
        self.assertIn('event.key === "ArrowUp"', dom_helpers_js)
        self.assertIn("options.scrollOnRender === true", dom_helpers_js)
        self.assertIn("function updateTableStatusLegend", dom_helpers_js)
        self.assertIn("function tableStatusLegendText", dom_helpers_js)
        self.assertIn("function filterResultSummaryLines", dom_helpers_js)
        self.assertIn("function countRowsByStatus", dom_helpers_js)
        self.assertIn("function filterRowsByStatus", dom_helpers_js)
        self.assertIn("function filterRowsByInvestigation", dom_helpers_js)
        self.assertIn("function tableStatusMatchesFilter", dom_helpers_js)
        self.assertIn("function tableStatusFilterLabel", dom_helpers_js)
        self.assertIn("function tableInvestigationFilterLabel", dom_helpers_js)
        self.assertIn("function reviewFlagExplanationLines", dom_helpers_js)
        self.assertIn("expected output proof is missing", dom_helpers_js)
        self.assertIn("translate already-loaded backend markers", dom_helpers_js)
        self.assertIn("function selectedRowDetailDrawerLines", dom_helpers_js)
        self.assertIn("Hidden review rows:", dom_helpers_js)
        self.assertIn("filters are display-only", dom_helpers_js)
        self.assertIn("window.makeRowSelectable = makeRowSelectable", dom_helpers_js)
        self.assertIn("window.filterRowsByStatus = filterRowsByStatus", dom_helpers_js)
        self.assertIn("window.filterRowsByInvestigation = filterRowsByInvestigation", dom_helpers_js)
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "filterResultSummaryLines")
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "reviewFlagExplanationLines")
        _assert_namespace_export(self, dom_helpers_js, "mediaPipelineDom", "selectedRowDetailDrawerLines")
        _assert_namespace_export(self, diagnostics_bridge_js, "mediaPipelineDiagnosticsBridge", "diagnosticsBridgeActions")
        self.assertIn("function diagnosticsOwnerHandoffRows", diagnostics_view_js)
        self.assertIn("function diagnosticsCompletedFinalTrustStepForRow", diagnostics_view_js)
        self.assertIn("function diagnosticsCompletedFinalTrustLines", diagnostics_view_js)
        self.assertIn("function diagnosticsCompletedPolicyReconciliationLines", diagnostics_view_js)
        self.assertIn("function navigateDiagnosticsOwnerHandoffRow", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsOwnerHandoff", diagnostics_view_js)
        self.assertIn("Completed final trust handoff:", diagnostics_view_js)
        self.assertIn("Completed saved-policy reconciliation handoff:", diagnostics_view_js)
        self.assertIn("Completed > Selected Pilot Evidence Packet > Saved policy reconciliation", diagnostics_view_js)
        self.assertIn("function diagnosticsSampleValidationComparisonLines", diagnostics_view_js)
        self.assertIn("Sample Validation context for this Diagnostics handoff:", diagnostics_view_js)
        self.assertIn('step: "2. Output and sidecar on disk"', diagnostics_view_js)
        self.assertIn("Final trust step: ${step.step}", diagnostics_view_js)
        self.assertIn("After Go To Owner Row, read Completed > Final Output Trust Walkthrough", diagnostics_view_js)
        self.assertIn("window.selectCompletedFinalTrustStep(item.completedFinalTrust.step)", diagnostics_view_js)
        self.assertIn("Selected Completed > Final Output Trust Walkthrough step", diagnostics_view_js)
        _assert_namespace_export(self, diagnostics_view_js, "mediaPipelineDiagnosticsView", "navigateDiagnosticsOwnerHandoffRow")
        _assert_namespace_export(self, diagnostics_view_js, "mediaPipelineDiagnosticsView", "renderDiagnosticsOwnerHandoff")
        self.assertIn("Read/open boundary: diagnostics targets are backend allowlist identifiers", diagnostics_view_js)
        self.assertIn("Row file/folder opens belong to the owning page and require row_key plus target only.", diagnostics_view_js)
        self.assertIn("Go To Owner Row is local UI selection over already-loaded data", diagnostics_view_js)
        self.assertIn("Diagnostics artifact JSON", diagnostics_state_js)
        self.assertIn("Diagnostics triage JSON", diagnostics_state_js)
        self.assertIn("jsonDetailText({", diagnostics_state_js)
        self.assertIn("renderDiagnosticsOwnerHandoffFn({", app_js)
        self.assertIn("sampleValidation: values[\"sample validation\"]", app_js)
        self.assertIn("function renderBrandVersion", app_js)
        self.assertIn("renderBrandVersion();", app_js)
        self.assertIn("function keyboardShortcutRegistry", app_js)
        self.assertIn("function focusActivePageSearch", app_js)
        self.assertIn("function clearActivePageFilters", app_js)
        self.assertIn("function moveActivePageSelection", app_js)
        self.assertIn("function _movePanelByStep", app_js)
        self.assertIn("pcb-btn-move-up", app_js)
        self.assertIn("pcb-btn-move-down", app_js)
        self.assertIn("panel-layout-moved", styles_css)
        self.assertIn("@keyframes panel-hold-pulse", styles_css)
        self.assertIn("function focusActivePageDetail", app_js)
        self.assertIn("Read-only shortcuts. They navigate, refresh, filter, focus, or select rows", app_js)
        self.assertIn('key: "/"', app_js)
        self.assertIn('key: "c"', app_js)
        self.assertIn('key: "j"', app_js)
        self.assertIn('key: "k"', app_js)
        self.assertIn('key: "d"', app_js)
        self.assertIn("startup HTML/assets are a separate shell bootstrap surface", contract_view_js)
        self.assertIn("/ and /assets/* are served for startup", contract_view_js)
        self.assertIn("Route contract JSON", contract_view_js)
        self.assertIn("jsonDetailText({", contract_view_js)
        self.assertIn("formats already-loaded route data only", contract_view_js)
        self.assertNotIn("Only /api/health is public; all operator routes stay token-protected.", contract_view_js)
        self.assertIn("window.mediaPipelineDom?.selectedRowDetailDrawerLines", queue_view_js)
        self.assertIn("Queue selected-row detail", queue_view_js)
        self.assertIn("reviewFlagExplanationLines(reviewFlags", queue_view_js)
        self.assertIn("No Queue review flags were reported for this row.", queue_view_js)
        self.assertIn("window.mediaPipelineDom?.selectedRowDetailDrawerLines", completed_view_js)
        self.assertIn("Completed selected-row detail", completed_view_js)
        self.assertIn("reviewFlagExplanationLines(reviewMarkers", completed_view_review_js)
        self.assertIn("No Completed review flags or consistency issues were reported for this row.", completed_view_review_js)
        self.assertIn(".inline-actions", styles_css)
        self.assertIn('tr[data-selectable-row="true"]:focus-visible td', styles_css)
        self.assertIn('tr[data-status="failed"] td', styles_css)
        self.assertIn(".output-overview-section-current", styles_css)
        self.assertIn(".output-overview-section-history", styles_css)
        self.assertIn('.completed-table tr[data-status="changed"] td', styles_css)

        for view_js, legend_id in [
            (queue_view_js, "queue-table-legend"),
            (queue_view_js, "queue-excluded-table-legend"),
            (queue_view_js, "queue-backend-scope-legend"),
            (queue_view_js, "queue-launch-decision-legend"),
            (completed_view_js, "completed-table-legend"),
            (completed_view_js, "completed-history-table-legend"),
            (completed_view_review_js, "completed-size-evidence-legend"),
            (completed_view_evidence_js, "completed-pending-proof-legend"),
            (completed_view_evidence_js, "publish-reconciliation-legend"),
            (completed_view_evidence_js, "completed-output-acceptance-legend"),
            (completed_view_evidence_js, "completed-route-agreement-legend"),
            (pending_view_js, "pending-table-legend"),
            (pending_view_drain_js, "pending-backend-scope-legend"),
            (pending_view_confidence_js, "pending-drain-decision-legend"),
            (rename_view_js, "rename-table-legend"),
            (command_history_js, "command-table-legend"),
            (reports_view_js, "failure-table-legend"),
            (reports_view_js, "audit-preview-table-legend"),
            (network_view_js, "network-worker-table-legend"),
            (diagnostics_view_js, "diagnostics-first-response-legend"),
            (diagnostics_state_js, "diagnostics-state-summary-table-legend"),
            (diagnostics_view_js, "diagnostics-owner-handoff-legend"),
            (diagnostics_view_js, "diagnostics-log-table-legend"),
            (diagnostics_view_js, "active-job-table-legend"),
            (command_history_js, "diagnostics-command-resolution-legend"),
            (launch_view_risk_js, "launch-settings-intent-legend"),
            (launch_view_scope_js, "launch-scope-reconciliation-legend"),
            (launch_view_scope_js, "launch-start-decision-legend"),
            (launch_view_preflight_js, "launch-backend-preflight-legend"),
            (contract_view_js, "api-contract-safety-legend"),
            (contract_view_js, "api-contract-table-legend"),
        ]:
            self.assertIn("makeRowSelectable(row", view_js)
            if f'updateTableStatusLegend("{legend_id}"' not in view_js:
                self.assertIn(f'legendId: "{legend_id}"', view_js)
                self.assertIn("updateTableStatusLegend(", view_js)
            else:
                self.assertIn(f'updateTableStatusLegend("{legend_id}"', view_js)

    def test_web_selected_rows_share_diagnostics_handoff(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        assets_root = static_root / "assets"
        diagnostics_bridge_js = (assets_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        queue_view_js = _read_queue_asset_bundle(assets_root)
        completed_view_js = _read_completed_asset_bundle(assets_root)
        pending_view_js = _read_pending_publish_asset_bundle(assets_root)
        reports_view_js = (assets_root / "reportsView.js").read_text(encoding="utf-8")
        command_history_js = _read_command_history_asset_bundle(assets_root)

        for node_id in [
            "command-diagnostics-actions",
            "failure-diagnostics-actions",
            "audit-preview-diagnostics-actions",
        ]:
            self.assertIn(f'id="{node_id}"', html)

        self.assertIn("function diagnosticsBridgeHandoffLines", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeTargetLabel", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeOrderedActions", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeActionGroups", diagnostics_bridge_js)
        self.assertIn("function diagnosticsBridgeRowTrustLines", diagnostics_bridge_js)
        self.assertIn("function appendDiagnosticsBridgeGroupedButtons", diagnostics_bridge_js)
        self.assertIn("Operator trust summary:", diagnostics_bridge_js)
        self.assertIn("Read first:", diagnostics_bridge_js)
        self.assertIn("Open next:", diagnostics_bridge_js)
        self.assertIn("renderOpenTargetActionGroups?.(container, groups", diagnostics_bridge_js)
        self.assertIn('groupDataset: "diagnosticsActionGroup"', diagnostics_bridge_js)
        self.assertIn("targetDataset: `${datasetPrefix}Target`", diagnostics_bridge_js)
        self.assertIn("Guardrail: this handoff selects or invokes backend allowlisted diagnostics targets only", diagnostics_bridge_js)
        self.assertIn("window.diagnosticsBridgeHandoffLines = diagnosticsBridgeHandoffLines", diagnostics_bridge_js)

        self.assertIn('diagnosticsBridgeHandoffLines("Queue selected row"', queue_view_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Completed selected row"', completed_view_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Pending Publish selected row"', pending_view_js)

        self.assertIn("function failureDiagnosticsActionsForRow", reports_view_js)
        self.assertIn("function auditDiagnosticsActionsForRow", reports_view_js)
        self.assertIn("function renderReportDiagnosticsActions", reports_view_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Reports failure selected row"', reports_view_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Reports audit selected row"', reports_view_js)
        self.assertIn("button.dataset.reportDiagnosticsTarget = action.target", reports_view_js)
        self.assertIn("appendDiagnosticsBridgeButton(container, actions, sourceLabel)", reports_view_js)

        self.assertIn("function commandHistoryDiagnosticsActions", command_history_js)
        self.assertIn("function commandHistoryDiagnosticsTargetAllowed", command_history_js)
        self.assertIn("commandHistoryDiagnosticsTargetAllowed(requestedTarget)", command_history_js)
        self.assertIn('diagnosticsBridgeHandoffLines("Command result selected row"', command_history_js)
        self.assertIn('byId("command-diagnostics-actions")', command_history_js)
        self.assertIn("button.dataset.commandDiagnosticsTarget = action.target", command_history_js)

    def test_diagnostics_bridge_flat_exports_cover_legacy_helper_consumers(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        assets_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static" / "assets"
        diagnostics_bridge_js = (assets_root / "diagnosticsBridge.js").read_text(encoding="utf-8")
        helper_names = {
            "diagnosticsBridgeActions",
            "diagnosticsBridgeActionLabel",
            "diagnosticsBridgeOrderedActions",
            "diagnosticsBridgeRowTrustLines",
            "diagnosticsBridgeHandoffLines",
            "appendDiagnosticsBridgeGroupedButtons",
            "appendDiagnosticsBridgeButton",
        }
        consumer_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(assets_root.glob("*.js"))
            if path.name != "diagnosticsBridge.js"
        )
        consumed_helpers = sorted(
            name
            for name in helper_names
            if re.search(rf"(?<![A-Za-z0-9_$]){re.escape(name)}(?![A-Za-z0-9_$])", consumer_text)
        )
        self.assertEqual(
            consumed_helpers,
            [
                "appendDiagnosticsBridgeButton",
                "appendDiagnosticsBridgeGroupedButtons",
                "diagnosticsBridgeActionLabel",
                "diagnosticsBridgeActions",
                "diagnosticsBridgeHandoffLines",
                "diagnosticsBridgeOrderedActions",
                "diagnosticsBridgeRowTrustLines",
            ],
        )
        missing_exports = [
            name
            for name in consumed_helpers
            if f"window.{name} = {name}" not in diagnostics_bridge_js
        ]
        self.assertEqual(missing_exports, [])

    def test_static_page_scoped_ids_remain_in_their_own_pages(self) -> None:
        desktop_root = Path(__file__).resolve().parents[1]
        static_root = desktop_root / "mediapipeline_desktop_app" / "ui_web" / "static"
        html = _render_static_index_html(static_root)
        page_pattern = re.compile(
            r'<section class="page(?:\s+is-visible)?" data-page-panel="([^"]+)">(.*?)(?=\n\s*<section class="page(?:\s+is-visible)?" data-page-panel=|\n\s*</main>)',
            re.S,
        )
        pages = dict(page_pattern.findall(html))
        scoped_prefixes = {
            "completed-": "completed",
            "pending-": "pending",
            "rename-": "rename",
            "failure-": "reports",
            "audit-preview-": "reports",
            "report-": "reports",
            "schedule-": "schedule",
            "maintenance-": "maintenance",
            "release-dry-run-": "maintenance",
            "release-build-": "maintenance",
            "backfill-": "maintenance",
            "dependency-atlas-": "maintenance",
            "diagnostics-": "diagnostics",
            "settings-network-": "network",
            "settings-library-": "libraries",
            "settings-libraries-": "libraries",
            "settings-": "settings",
            "cpu-": "live",
            "gpu-": "live",
            "ram-": "live",
        }
        id_locations: dict[str, str] = {}
        for page_name, body in pages.items():
            for node_id in re.findall(r'id="([^"]+)"', body):
                id_locations[node_id] = page_name

        misplaced = {}
        for node_id, page_name in id_locations.items():
            for prefix, expected_page in scoped_prefixes.items():
                if node_id.startswith(prefix):
                    if page_name != expected_page:
                        misplaced[node_id] = {"actual": page_name, "expected": expected_page}
                    break

        self.assertEqual(misplaced, {})

    def test_headless_local_api_backend_builds_bootstrap_payload(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            app_root = Path(raw_root) / "DesktopApp"
            app_root.mkdir(parents=True)
            emitted_progress: list[dict[str, object]] = []
            service, resolved, server = build_backend(
                app_root=app_root,
                token="headless-token",
                startup_progress_callback=emitted_progress.append,
            )
            try:
                server.start()
                payload = bootstrap_payload(server, resolved, include_token=True)
            finally:
                server.stop()
                service.stop_background_tasks()
                for handler in list(service.logger.handlers):
                    service.logger.removeHandler(handler)
                    handler.close()

        self.assertEqual(payload["schema_version"], BOOTSTRAP_SCHEMA_VERSION)
        self.assertEqual(payload["token"], "headless-token")
        self.assertTrue(str(payload["url"]).startswith("http://127.0.0.1:"))
        self.assertEqual(Path(str(payload["config_path"])).name, "MediaPipeline_config.psd1")
        self.assertEqual(payload["shell_surface"], "webview")
        self.assertEqual(payload["startup_progress"]["schema_version"], "desktop_startup_progress.v1")
        self.assertTrue(payload["startup_progress"]["steps"])
        self.assertGreaterEqual(len(emitted_progress), 1)
        self.assertEqual(emitted_progress[-1]["schema_version"], "desktop_startup_progress.v1")
        self.assertIn("resolve_app_root", {step["id"] for step in payload["startup_progress"]["steps"]})
        self.assertIn("verify_ffmpeg", {step["id"] for step in payload["startup_progress"]["steps"]})
        self.assertIn("verify_ffprobe", {step["id"] for step in payload["startup_progress"]["steps"]})
        self.assertIn("verify_mkvmerge", {step["id"] for step in payload["startup_progress"]["steps"]})
        self.assertIn("create_local_api", {step["id"] for step in payload["startup_progress"]["steps"]})


if __name__ == "__main__":
    unittest.main()

