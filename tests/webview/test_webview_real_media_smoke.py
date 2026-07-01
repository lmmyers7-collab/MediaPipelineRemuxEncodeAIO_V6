from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService, _resolved
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService, _resolved


LAUNCH_RISK_ASSET_PATHS = [
    "assets/launch/risk/settingsAccess.js",
    "assets/launch/risk/mediaPolicyValues.js",
    "assets/launch/risk/riskRows.js",
    "assets/launch/risk/policyPatch.js",
    "assets/launch/risk/policyBoundary.js",
]

LAUNCH_VIEW_ASSET_PATHS = [
    "assets/launch/controllerState.js",
    "assets/launch/statusRender.js",
    "assets/launch/startRequest.js",
    "assets/launch/scopeControls.js",
    "assets/launch/commandButtons.js",
]


def _get_text(url: str, token: str | None = None) -> tuple[int, str, str]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, response.read().decode("utf-8"), response.headers.get("Content-Type", "")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), exc.headers.get("Content-Type", "")


def _get_json(url: str, token: str | None = None) -> tuple[int, dict[str, object]]:
    status, body, _content_type = _get_text(url, token)
    return status, json.loads(body)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _write_fixture_state(root: Path) -> tuple[object, Path, Path]:
    source = root / "TV" / "Serial Experiments Lain" / "Season 02" / "Serial Experiments Lain S02E01 Weird.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source-media")

    output = root / "Outsource" / "TV" / "Serial Experiments Lain" / "Season 02" / "Serial Experiments Lain - S02E01 - Weird.mkv"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"output-media")
    output_sidecar = output.with_name(output.name + ".pipeline.json")
    _write_json(output_sidecar, {"schema_version": "pipeline_sidecar.v1", "source_path": str(source), "output_path": str(output)})

    queue_snapshot = root / "State" / "Progress" / "queue_snapshot.json"
    _write_json(
        queue_snapshot,
        {
            "schema_version": "queue_plan_snapshot.v1",
            "produced_at": "2026-05-13T22:00:00-04:00",
            "config_path": str(root / "config.psd1"),
            "local_base": str(root),
            "source_movies": str(root / "Movies"),
            "source_tv": str(root / "TV"),
            "outsource": str(root / "Outsource"),
            "movie_count_total": 0,
            "tv_count_total": 1,
            "priority_count": 0,
            "runnable_count": 1,
            "rows": [
                {
                    "global_order": 1,
                    "phase": "tv",
                    "media_kind": "tv",
                    "queue_index": 1,
                    "queue_total": 1,
                    "source_path": str(source),
                    "root_path": str(root / "TV"),
                    "relative_path": "Serial Experiments Lain\\Season 02\\Serial Experiments Lain S02E01 Weird.mkv",
                    "display_name": source.name,
                    "size_gb": 0.01,
                    "route": "remux",
                    "route_reason_code": "h264_direct_stream_safe",
                    "route_reason": "H.264 source is within configured Plex Direct/Stream copy limits.",
                    "blocked_reason": "",
                }
            ],
        },
    )

    completed_manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
    completed_manifest.parent.mkdir(parents=True, exist_ok=True)
    completed_manifest.write_text(
        json.dumps(
            {
                "source_path": str(source),
                "output_path": str(output),
                "sidecar_path": str(output_sidecar),
                "route": "remux",
                "route_reason": "H.264 source is within configured Plex Direct/Stream copy limits.",
                "route_reason_code": "h264_direct_stream_safe",
                "encoder": "copy",
                "audio_summary": "passthrough english default",
                "subtitle_summary": "kept original TX3G and added preferred-language SRT",
                "source_size": source.stat().st_size,
                "output_size": output.stat().st_size,
                "encoded_at": "2026-05-13T22:05:00-04:00",
                "elapsed_seconds": 45,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    pending_root = root / "PendingServerPush"
    pending_payload = pending_root / output.name
    pending_sidecar = pending_root / output_sidecar.name
    pending_payload.parent.mkdir(parents=True, exist_ok=True)
    pending_payload.write_bytes(output.read_bytes())
    pending_sidecar.write_text(output_sidecar.read_text(encoding="utf-8"), encoding="utf-8")
    _write_json(
        pending_root / f"{output.name}.manifest.json",
        {
            "schema_version": "pending_push_manifest.v1",
            "manifest_state": "parked",
            "parked_at": "2026-05-13T22:06:00-04:00",
            "product_version": "v5-test",
            "pipeline_version": "v5-test",
            "publish_transaction_id": "tx-webview-fixture",
            "publish_mode": "server",
            "route": "remux",
            "route_reason_code": "h264_direct_stream_safe",
            "route_reason": "H.264 source is within configured Plex Direct/Stream copy limits.",
            "local_file": str(pending_payload),
            "original_local_file": str(root / "State" / "Encoded" / output.name),
            "parked_file": str(pending_payload),
            "server_out": str(output),
            "source_identity": "fixture-source-v1",
            "source_identity_v2": "fixture-source-v2",
            "source_identity_v2_algorithm": "fixture-v2",
            "source_path": str(source),
            "source_size": source.stat().st_size,
            "source_mtime_utc": "2026-05-13T22:00:00Z",
            "output_size": pending_payload.stat().st_size,
            "sidecar_files": [
                {
                    "kind": "tx3g_srt",
                    "local_file": str(pending_sidecar),
                    "parked_file": str(pending_sidecar),
                    "server_out": str(output_sidecar),
                    "preserve_existing": False,
                }
            ],
            "tx3g_srt_tracks": [],
            "tx3g_srt_failures": [],
            "bdpgs_srt_failures": [],
            "vobsub_srt_failures": [],
            "tx3g_embedded_srt_tracks": [],
            "bdpgs_embedded_srt_tracks": [],
            "vobsub_embedded_srt_tracks": [],
            "tx3g_srt_conversion_enabled": True,
            "tx3g_external_srt_sidecars_enabled": True,
            "drop_tx3g_after_conversion": False,
            "bdpgs_srt_conversion_enabled": True,
            "drop_bdpgs_after_conversion": False,
            "vobsub_srt_conversion_enabled": True,
            "drop_vobsub_after_conversion": False,
        },
    )

    (root / "RunLogs").mkdir(exist_ok=True)
    (root / "RunLogs" / "run.stdout.log").write_text(f"remux complete for {source}\n", encoding="utf-8")
    (root / "RunLogs" / "run.stderr.log").write_text("ffmpeg exited with code 0\n", encoding="utf-8")
    worksheet = root / "Docs" / "RealMediaValidationRuns" / "real_media_validation_fixture.md"
    worksheet.parent.mkdir(parents=True, exist_ok=True)
    worksheet.write_text(
        "\n".join(
            [
                "<!--",
                "Generated by New-RealMediaValidationWorksheet.ps1.",
                "-->",
                "# Real-Media Validation Evidence Template",
                "## Validation Run Identity",
                "| Field | Value |",
                "|---|---|",
                "| Operator | Fixture Operator |",
                "| Launch surface | WebView preview |",
                "## Sample Batch",
                "| # | Source file | Category | Expected route |",
                "|---|---|---|---|",
                f"| 1 | {source} | subtitle-bearing | remux-plus-srt |",
                "## WebView Pilot Evidence Packet Capture",
                "| Sample # | Sample label | Packet status | Queue route proof | Completed output/sidecar proof | Diagnostics/run-log proof | Pending Publish posture | Playback/subtitle/audio/size proof | Stop condition hit? |",
                "|---|---|---|---|---|---|---|---|---|",
                "| 1 | Serial Experiments Lain - S02E01 - Weird.mkv | review-before-append | ready | ready | ready | review | checked | no |",
            ]
        ),
        encoding="utf-8",
    )

    resolved = _resolved(root)
    resolved.queue_snapshot_path = queue_snapshot
    resolved.completed_manifest_path = completed_manifest
    resolved.pending_push_path = pending_root
    resolved.config_data = {
        "RoutingProfile": "plex_direct_stream",
        "SizeGuardMode": "advisory",
        "VideoCodec": "hevc_nvenc",
        "OutputContainer": "mkv",
        "AllowH264RemuxIfPlexCompatible": True,
        "MaxEncodeGrowthPercent": 5,
        "CompatibilityEncodeGrowthPercent": 15,
        "SubKeepLanguages": ["eng", "und"],
        "Tx3gExtractLanguages": ["eng", "und"],
        "BdpgsExtractLanguages": ["eng", "und"],
        "VobSubExtractLanguages": ["eng", "und"],
        "ConvertTx3gToSrt": True,
        "DropTx3gAfterConversion": False,
        "ConvertBdpgsToSrt": True,
        "DropBdpgsAfterConversion": False,
        "ConvertVobSubToSrt": True,
        "DropVobSubAfterConversion": False,
        "VobSubOcrToolPath": r"tools\SubtitleEditLegacy\SubtitleEdit.exe",
        "DropAssAfterConversion": False,
        "StripFormatting": True,
        "RemoveKaraoke": True,
        "KeepSignsAndSongs": True,
        "AudioPassthroughProfile": "plex_balanced",
        "CompatibleAudioCodecs": ["aac", "ac3", "eac3"],
        "PreferredDefaultAudioLanguages": ["english"],
        "AudioTranscodeCodec": "eac3",
        "AudioDownmixMode": "max_channels",
        "AudioMaxChannels": 6,
        "AllowNoAudio": False,
        "DeferredPublish": True,
        "CleanupRemoteStaging": False,
        "SkipStabilityCheck": False,
        "EnableIntegrityCheck": True,
        "TransientFailureRetryLimit": 3,
        "RobocopyTimeoutSeconds": 14400,
        "OutsourceMinFreeSpaceGB": 20,
        "OutputSizeMultiplier": 1.15,
    }
    return resolved, source, output


def _write_high_risk_fixture_state(root: Path) -> tuple[object, list[dict[str, object]]]:
    queue_source = root / "TV" / "Show" / "Show Episode One.mkv"
    queue_source.parent.mkdir(parents=True, exist_ok=True)
    queue_source.write_bytes(b"queue-source-media")

    completed_source = root / "Source" / "Missing Source.mkv"
    completed_source.parent.mkdir(parents=True, exist_ok=True)
    completed_source.write_bytes(b"completed-source-media")
    missing_output = root / "Outsource" / "Movies" / "Missing Output.mkv"

    queue_snapshot = root / "State" / "Progress" / "queue_snapshot.json"
    _write_json(
        queue_snapshot,
        {
            "schema_version": "queue_plan_snapshot.v1",
            "produced_at": "2026-05-13T22:10:00-04:00",
            "config_path": str(root / "config.psd1"),
            "local_base": str(root),
            "source_movies": str(root / "Movies"),
            "source_tv": str(root / "TV"),
            "outsource": str(root / "Outsource"),
            "movie_count_total": 0,
            "tv_count_total": 1,
            "priority_count": 0,
            "runnable_count": 1,
            "rows": [
                {
                    "global_order": 1,
                    "phase": "tv",
                    "media_kind": "tv",
                    "queue_index": 1,
                    "queue_total": 1,
                    "is_priority": False,
                    "source_path": str(queue_source),
                    "root_path": str(root / "TV"),
                    "relative_path": "Show\\Show Episode One.mkv",
                    "display_name": queue_source.name,
                    "size_gb": 0.01,
                    "route": "",
                    "route_reason_code": "",
                    "route_reason": "",
                    "blocked_reason_code": "tv_parse_unreliable",
                    "blocked_reason": "tv-parse: missing season/episode",
                    "season_number": 0,
                    "episode_number": 0,
                    "last_write_utc": "2026-05-13T22:10:00Z",
                }
            ],
        },
    )

    completed_manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
    completed_manifest.parent.mkdir(parents=True, exist_ok=True)
    completed_manifest.write_text(
        json.dumps(
            {
                "source_path": str(completed_source),
                "output_path": str(missing_output),
                "route": "remux",
                "route_reason": "H.264 source is within configured Plex Direct/Stream copy limits.",
                "route_reason_code": "h264_direct_stream_safe",
                "encoder": "copy",
                "audio_summary": "passthrough english default",
                "subtitle_summary": "kept original subtitles",
                "encoded_at": "2026-05-13T22:11:00-04:00",
                "source_size": completed_source.stat().st_size,
                "output_size": completed_source.stat().st_size * 2,
                "publish_state": "published",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    pending_root = root / "PendingServerPush"
    pending_root.mkdir(parents=True, exist_ok=True)
    (pending_root / "Broken.mkv.manifest.json").write_text("{not json", encoding="utf-8")

    event_file = root / "State" / "Progress" / "pipeline_events.jsonl"
    events: list[dict[str, object]] = [
        {
            "schema_version": "pipeline_event.v1",
            "event_id": "evt-queue-source-locked",
            "event_type": "job_completed",
            "timestamp": "2999-01-01T00:00:00Z",
            "created_at": "2999-01-01T00:00:00Z",
            "stage": "source-stability",
            "route": "remux",
            "status": "failed",
            "source_path": str(queue_source),
            "data": {
                "success": False,
                "completion_status": "skipped",
                "queue_terminal": False,
                "retryable": True,
                "reason": "Source changed during probe.",
                "error_code": "source_locked",
                "route": "remux",
            },
        },
        {
            "schema_version": "pipeline_event.v1",
            "event_id": "evt-completed-missing-output",
            "event_type": "job_completed",
            "timestamp": "2999-01-01T00:00:00Z",
            "created_at": "2999-01-01T00:00:00Z",
            "stage": "publish-verification",
            "route": "remux",
            "status": "failed",
            "source_path": str(completed_source),
            "data": {
                "success": False,
                "completion_status": "failed",
                "retryable": False,
                "reason": "Completed manifest points at a missing file.",
                "error_code": "publish_missing_output",
                "output_path": str(missing_output),
                "output_size_bytes": completed_source.stat().st_size * 2,
            },
        },
    ]
    event_file.parent.mkdir(parents=True, exist_ok=True)
    event_file.write_text("\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events), encoding="utf-8")

    (root / "RunLogs").mkdir(exist_ok=True)
    (root / "RunLogs" / "run.stdout.log").write_text("queue blocked and completed proof conflict fixture\n", encoding="utf-8")
    (root / "RunLogs" / "run.stderr.log").write_text("source_locked\npublish_missing_output\n", encoding="utf-8")

    resolved = _resolved(root)
    resolved.state_root = root / "State"
    resolved.queue_snapshot_path = queue_snapshot
    resolved.completed_manifest_path = completed_manifest
    resolved.pending_push_path = pending_root
    resolved.event_file = event_file
    resolved.config_data = {
        "RoutingProfile": "plex_direct_stream",
        "SizeGuardMode": "advisory",
        "DeferredPublish": True,
        "OutputSizeMultiplier": 1.15,
    }
    return resolved, events


class WebViewRealMediaSmoke(unittest.TestCase):
    def test_backend_served_webview_fixture_has_real_media_validation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, source, output = _write_fixture_state(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(facade, token="smoke-token", resolved_provider=lambda: resolved, audit_root_provider=lambda: str(root))
            try:
                server.start()
                html_status, html, html_type = _get_text(f"{server.url}/")
                app_status, app_js, app_type = _get_text(f"{server.url}/assets/app.js")
                cross_status, cross_js, cross_type = _get_text(f"{server.url}/assets/crossPageContextView.js")
                cross_conflict_status, cross_conflict_js, cross_conflict_type = _get_text(f"{server.url}/assets/crossPageContextView.conflict.js")
                cross_sample_child_status, cross_sample_child_js, cross_sample_child_type = _get_text(f"{server.url}/assets/crossPageContextView.sample.js")
                cross_settings_status, cross_settings_js, cross_settings_type = _get_text(f"{server.url}/assets/crossPageContextView.settings.js")
                cross_sample_worksheet_status, cross_sample_worksheet_js, cross_sample_worksheet_type = _get_text(f"{server.url}/assets/crossPageContextView.sampleValidation.worksheet.js")
                cross_sample_runbook_status, cross_sample_runbook_js, cross_sample_runbook_type = _get_text(f"{server.url}/assets/crossPageContextView.sampleValidation.runbook.js")
                cross_sample_records_status, cross_sample_records_js, cross_sample_records_type = _get_text(f"{server.url}/assets/crossPageContextView.sampleValidation.records.js")
                cross_sample_status, cross_sample_parent_js, cross_sample_type = _get_text(f"{server.url}/assets/crossPageContextView.sampleValidation.js")
                cross_sample_js = "\n".join((cross_sample_worksheet_js, cross_sample_runbook_js, cross_sample_records_js, cross_sample_parent_js))
                launch_risk_parts = []
                launch_risk_child_results = {}
                for asset_path in LAUNCH_RISK_ASSET_PATHS:
                    child_status, child_js, child_type = _get_text(f"{server.url}/{asset_path}")
                    launch_risk_parts.append(child_js)
                    launch_risk_child_results[asset_path] = (child_status, child_type)
                launch_risk_status, launch_risk_parent_js, launch_risk_type = _get_text(f"{server.url}/assets/launchView.risk.js")
                launch_risk_js = "\n".join([*launch_risk_parts, launch_risk_parent_js])
                launch_scope_status, launch_scope_js, launch_scope_type = _get_text(f"{server.url}/assets/launchView.scope.js")
                launch_realmedia_status, launch_realmedia_js, launch_realmedia_type = _get_text(f"{server.url}/assets/launchView.realmedia.js")
                launch_preflight_status, launch_preflight_js, launch_preflight_type = _get_text(f"{server.url}/assets/launchView.preflight.js")
                launch_view_parts = []
                launch_view_child_results = {}
                for asset_path in LAUNCH_VIEW_ASSET_PATHS:
                    child_status, child_js, child_type = _get_text(f"{server.url}/{asset_path}")
                    launch_view_parts.append(child_js)
                    launch_view_child_results[asset_path] = (child_status, child_type)
                launch_view_status, launch_view_parent_js, launch_view_type = _get_text(f"{server.url}/assets/launchView.js")
                launch_view_js = "\n".join([*launch_view_parts, launch_view_parent_js])
                queue_status, queue = _get_json(f"{server.url}/api/queue", token="smoke-token")
                completed_status, completed = _get_json(f"{server.url}/api/completed", token="smoke-token")
                pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="smoke-token")
                diagnostics_status, diagnostics = _get_json(f"{server.url}/api/diagnostics", token="smoke-token")
                settings_status, settings = _get_json(f"{server.url}/api/settings/workspace", token="smoke-token")
                sample_validation_status, sample_validation = _get_json(f"{server.url}/api/sample-validation?limit=10", token="smoke-token")
                commands_status, commands = _get_json(f"{server.url}/api/commands?limit=20", token="smoke-token")
                contract_status, contract = _get_json(f"{server.url}/api/contract", token="smoke-token")
            finally:
                server.stop()

        self.assertEqual(html_status, 200)
        self.assertIn("text/html", html_type)
        self.assertIn('"token": ""', html)
        self.assertIn('"tokenSource": "http-only-cookie"', html)
        self.assertNotIn("smoke-token", html)
        self.assertNotIn("__MEDIA_PIPELINE_BOOTSTRAP__", html)
        for fragment in (
            'id="cross-page-real-media-status"',
            'id="cross-page-real-media-rows"',
            'id="cross-page-real-media-detail"',
            'id="sample-validation-execution-rows"',
            'id="sample-validation-execution-detail"',
            'id="sample-validation-worksheet-rows"',
            'id="sample-validation-worksheet-detail"',
            'id="sample-validation-gap-summary"',
            'id="sample-validation-gap-rows"',
            'id="sample-validation-runbook-summary"',
            'id="sample-validation-runbook-rows"',
            'id="sample-validation-runbook-markdown"',
            'id="sample-validation-completed-packet-summary"',
            'id="sample-validation-completed-packet-rows"',
            'id="sample-validation-completed-packet-detail"',
            'id="sample-validation-completed-packet-markdown"',
            'id="sample-validation-acceptance-gate-summary"',
            'id="sample-validation-acceptance-gate-rows"',
            'id="sample-validation-acceptance-gate-detail"',
            'id="sample-validation-record-review-summary"',
            'id="sample-validation-record-review-rows"',
            'id="sample-validation-record-review-detail"',
            'id="sample-validation-category-summary"',
            'id="sample-validation-category-summary-rows"',
            'id="sample-validation-category-summary-detail"',
            'id="launch-sample-execution-rows"',
            'id="launch-sample-execution-detail"',
            'id="launch-pilot-readiness-summary"',
            'id="launch-pilot-readiness-rows"',
            'id="launch-pilot-readiness-detail"',
            'id="launch-start-decision-rows"',
            'id="launch-start-decision-detail"',
            "Validation Worksheet",
            "Pilot Worksheets",
        ):
            self.assertIn(fragment, html)

        self.assertEqual(app_status, 200)
        self.assertIn("javascript", app_type)
        self.assertIn("const crossPageContext = {", app_js)
        self.assertIn("renderCrossPageContext(crossPageContext)", app_js)
        self.assertIn("window.mediaPipelineLaunchView?.renderLaunchRealMediaProofHandoff?.(crossPageContext)", app_js)
        self.assertIn("settings: values.settings || getLastSettings()", app_js)

        self.assertEqual(cross_status, 200)
        self.assertIn("javascript", cross_type)
        self.assertEqual(cross_conflict_status, 200)
        self.assertIn("javascript", cross_conflict_type)
        self.assertEqual(cross_sample_child_status, 200)
        self.assertIn("javascript", cross_sample_child_type)
        self.assertEqual(cross_settings_status, 200)
        self.assertIn("javascript", cross_settings_type)
        self.assertEqual(cross_sample_worksheet_status, 200)
        self.assertIn("javascript", cross_sample_worksheet_type)
        self.assertEqual(cross_sample_runbook_status, 200)
        self.assertIn("javascript", cross_sample_runbook_type)
        self.assertEqual(cross_sample_records_status, 200)
        self.assertIn("javascript", cross_sample_records_type)
        self.assertEqual(cross_sample_status, 200)
        self.assertIn("javascript", cross_sample_type)
        self.assertIn("/assets/crossPageContextView.conflict.js", html)
        self.assertIn("/assets/crossPageContextView.sample.js", html)
        self.assertIn("/assets/crossPageContextView.settings.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.worksheet.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.runbook.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.records.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.js", html)
        self.assertIn("window.__crossPageConflictModule", cross_conflict_js)
        self.assertIn("window.__crossPageSampleModule", cross_sample_child_js)
        self.assertIn("window.__crossPageSettingsModule", cross_settings_js)
        self.assertIn("window.__crossPageSampleValidationModule", cross_sample_js)
        self.assertIn("window.__crossPageSvWorksheetModule", cross_sample_js)
        self.assertIn("window.__crossPageSvRunbookModule", cross_sample_js)
        self.assertIn("window.__crossPageSvRecordsModule", cross_sample_js)
        cross_js = cross_js + "\n" + cross_settings_js + "\n" + cross_sample_js
        for fragment in (
            "function crossPageRealMediaWorksheetRows",
            "function crossPageSettingsPolicyEvidence",
            "function crossPageSampleValidationEvidence",
            "function sampleValidationPilotPlanLines",
            "function renderSampleValidationGapSummary",
            "function renderSampleValidationRunbook",
            "function renderSampleValidationExecutionChecklist",
            "function renderSampleValidationWorksheets",
            "sampleValidationWorksheetRunMatchesSample",
            "sampleValidationRecordMatchesSample",
            "Real-media pilot plan:",
            "Real-media evidence gap summary:",
            "Real-media pilot runbook:",
            "# Real-Media WebView Pilot Runbook",
            "Post-run evidence capture:",
            "Copyable post-run Markdown:",
            "function sampleValidationCompletedPacketRows",
            "function sampleValidationCompletedPolicyReconciliationRow",
            "function sampleValidationCompletedPolicyReconciliationStatus",
            "function renderSampleValidationCompletedPacketHandoff",
            "Completed evidence handoff for Sample Validation:",
            "Saved-policy reconciliation:",
            "Decision rule: keep Sample Validation at hold/review",
            "function sampleValidationAcceptanceGateRows",
            "function renderSampleValidationAcceptanceGate",
            "Sample Validation acceptance readiness gate:",
            "Saved policy reconciliation",
            "Decision rule: accepted sample evidence should not be appended",
            "function sampleValidationRecordReviewRows",
            "function renderSampleValidationRecordReview",
            "Accepted sample-validation record proof review:",
            "Decision rule: treat accepted records as current proof only",
            "function sampleValidationCategorySummaryRows",
            "function renderSampleValidationCategorySummary",
            "Pilot category validation summary:",
            "Decision rule: a category is ready only when an accepted validation record",
            "Operator-selected real-media sample execution:",
            "Generated real-media worksheets:",
            "Queue route intent, Completed output proof, Pending Publish final-destination proof",
            "Sample Validation evidence posture",
            "Sample Validation readiness",
            "Sample validation:",
            "Boundary: this worksheet does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files.",
        ):
            self.assertIn(fragment, cross_js)

        self.assertEqual(launch_view_status, 200)
        self.assertIn("javascript", launch_view_type)
        self.assertEqual(launch_risk_status, 200)
        self.assertIn("javascript", launch_risk_type)
        for asset_path, (child_status, child_type) in launch_risk_child_results.items():
            self.assertEqual(child_status, 200, asset_path)
            self.assertIn("javascript", child_type, asset_path)
        self.assertEqual(launch_scope_status, 200)
        self.assertIn("javascript", launch_scope_type)
        self.assertEqual(launch_realmedia_status, 200)
        self.assertIn("javascript", launch_realmedia_type)
        self.assertEqual(launch_preflight_status, 200)
        self.assertIn("javascript", launch_preflight_type)
        for asset_path, (child_status, child_type) in launch_view_child_results.items():
            self.assertEqual(child_status, 200, asset_path)
            self.assertIn("javascript", child_type, asset_path)
        self.assertIn("/assets/launchView.risk.js", html)
        self.assertIn("window.__launchViewRiskModule", launch_risk_js)
        self.assertIn("/assets/launchView.scope.js", html)
        self.assertIn("window.__launchViewScopeModule", launch_scope_js)
        self.assertIn("/assets/launchView.realmedia.js", html)
        self.assertIn("window.__launchViewRealMediaModule", launch_realmedia_js)
        self.assertIn("/assets/launchView.preflight.js", html)
        self.assertIn("window.__launchViewPreflightModule", launch_preflight_js)
        for asset_path in LAUNCH_VIEW_ASSET_PATHS:
            self.assertIn(f"/{asset_path}", html)
        launch_view_js = launch_view_js + "\n" + launch_risk_js + "\n" + launch_scope_js + "\n" + launch_realmedia_js + "\n" + launch_preflight_js
        for fragment in (
            "function renderLaunchRealMediaProofHandoff",
            "function launchWorksheetEvidence",
            "function launchSampleValidationRecordEvidence",
            "Launch real-media sample proof handoff:",
            "Home Real-Media Validation Worksheet",
            "Generated worksheet evidence:",
            "Sample Validation record evidence:",
            "Pilot category coverage:",
            "Pre-run boundary: Launch can prove selected intent",
            "daily-driver trust still requires post-run output",
            "function launchSampleSetCoverageEvidence",
            "function launchSampleSetCoverageLine",
            "function launchPolicyAlignmentQueueIntentEvidence",
            "Saved policy vs Queue route:",
            "Advisory boundary: queue-route matching uses loaded route/status text only.",
            "function renderLaunchSampleExecutionChecklist",
            "Launch sample execution checklist:",
            "Home's backend-authored operator sample execution checklist",
            "function launchPilotRunReadinessRows",
            "function renderLaunchPilotRunReadiness",
            "Launch pilot run readiness:",
            "function renderLaunchStartDecisionSummary",
            "Launch start decision summary:",
            "treat these signals as advisory evidence for Start; backend start remains authoritative",
        ):
            self.assertIn(fragment, launch_view_js)

        self.assertEqual(queue_status, 200)
        self.assertEqual(completed_status, 200)
        self.assertEqual(pending_status, 200)
        self.assertEqual(diagnostics_status, 200)
        self.assertEqual(settings_status, 200)
        self.assertEqual(sample_validation_status, 200)
        self.assertEqual(commands_status, 200)
        self.assertEqual(contract_status, 200)

        queue_row = queue["rows"][0]  # type: ignore[index]
        completed_row = completed["rows"][0]  # type: ignore[index]
        pending_row = pending["rows"][0]  # type: ignore[index]
        settings_config = settings["config"]  # type: ignore[index]

        self.assertEqual(queue_row["source_path"], str(source))
        self.assertEqual(queue_row["route_name"], "remux")
        self.assertEqual(completed_row["source_path"], str(source))
        self.assertEqual(completed_row["output_path"], str(output))
        self.assertEqual(pending_row["source_path"], str(source))
        self.assertEqual(pending_row["server_out"], str(output))
        self.assertEqual(settings_config["RoutingProfile"], "plex_direct_stream")
        self.assertEqual(settings_config["ConvertTx3gToSrt"], True)
        self.assertEqual(settings_config["DropTx3gAfterConversion"], False)
        self.assertEqual(settings_config["AudioPassthroughProfile"], "plex_balanced")
        self.assertEqual(sample_validation["pilot_plan"]["schema_version"], "desktop_real_media_pilot_plan.v1")  # type: ignore[index]
        self.assertIn(sample_validation["pilot_plan"]["operator_status"], {"review", "pilot-needed", "current-evidence"})  # type: ignore[index]
        self.assertIn("next_required_action", sample_validation["pilot_plan"])  # type: ignore[operator]
        self.assertIn("pilot_attention", sample_validation["pilot_plan"])  # type: ignore[operator]
        self.assertGreaterEqual(sample_validation["pilot_plan"]["required_stage_count"], 1)  # type: ignore[index]
        self.assertIn("Read-only real-media pilot plan", sample_validation["pilot_plan"]["guardrail"])  # type: ignore[index]
        worksheet_runs = sample_validation["worksheet_runs"]  # type: ignore[index]
        self.assertEqual(worksheet_runs["schema_version"], "desktop_real_media_worksheet_runs.v1")  # type: ignore[index]
        self.assertEqual(worksheet_runs["run_count"], 1)  # type: ignore[index]
        self.assertEqual(worksheet_runs["rows"][0]["file_name"], "real_media_validation_fixture.md")  # type: ignore[index]
        self.assertEqual(worksheet_runs["rows"][0]["samples"][0]["source_path"], str(source))  # type: ignore[index]
        self.assertIn("Read-only generated worksheet evidence", worksheet_runs["guardrail"])  # type: ignore[index]

        self.assertEqual(diagnostics["schema_version"], "desktop_diagnostics.v1")
        self.assertEqual(commands["count"], 0)
        contract_paths = {route["path"]: route["effect"] for route in contract["routes"]}  # type: ignore[index]
        self.assertEqual(contract_paths["/api/queue"], "none")
        self.assertEqual(contract_paths["/api/completed"], "none")
        self.assertEqual(contract_paths["/api/pending-publish"], "none")
        self.assertEqual(contract_paths["/api/settings/workspace"], "none")
        self.assertEqual(contract_paths["/api/rename/apply"], "filesystem-mutation")

    def test_backend_served_webview_fixture_has_settings_launch_policy_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(facade, token="smoke-token", resolved_provider=lambda: resolved, audit_root_provider=lambda: str(root))
            try:
                server.start()
                html_status, html, html_type = _get_text(f"{server.url}/")
                settings_policy_impact_status, settings_policy_impact_js, settings_policy_impact_type = _get_text(
                    f"{server.url}/assets/settings/policyImpact.js"
                )
                settings_view_status, settings_view_js, settings_view_type = _get_text(f"{server.url}/assets/settingsView.js")
                settings_overview_status, settings_overview_js, settings_overview_type = _get_text(f"{server.url}/assets/settingsOverview.js")
                launch_risk_parts = []
                for asset_path in LAUNCH_RISK_ASSET_PATHS:
                    _child_status, child_js, _child_type = _get_text(f"{server.url}/{asset_path}")
                    launch_risk_parts.append(child_js)
                launch_risk_status, launch_risk_parent_js, launch_risk_type = _get_text(f"{server.url}/assets/launchView.risk.js")
                launch_risk_js = "\n".join([*launch_risk_parts, launch_risk_parent_js])
                launch_view_parts = []
                for asset_path in LAUNCH_VIEW_ASSET_PATHS:
                    _child_status, child_js, _child_type = _get_text(f"{server.url}/{asset_path}")
                    launch_view_parts.append(child_js)
                launch_view_status, launch_view_parent_js, launch_view_type = _get_text(f"{server.url}/assets/launchView.js")
                launch_view_js = "\n".join([*launch_view_parts, launch_view_parent_js])
                cross_status, cross_js, cross_type = _get_text(f"{server.url}/assets/crossPageContextView.js")
                cross_settings_status, cross_settings_js, cross_settings_type = _get_text(f"{server.url}/assets/crossPageContextView.settings.js")
                settings_status, settings = _get_json(f"{server.url}/api/settings/workspace", token="smoke-token")
            finally:
                server.stop()

        self.assertEqual(html_status, 200)
        self.assertIn("text/html", html_type)
        for fragment in (
            'id="settings-backend-media-policy-status"',
            'id="settings-backend-media-policy-rows"',
            "Policy Readiness",
            'id="settings-policy-delta-status"',
            'id="settings-policy-delta-rows"',
            'id="launch-settings-risk-rows"',
        ):
            self.assertIn(fragment, html)

        self.assertEqual(settings_policy_impact_status, 200)
        self.assertIn("javascript", settings_policy_impact_type)
        for fragment in (
            "function settingsBackendMediaPolicyReadiness",
            "function renderSettingsBackendMediaPolicyReadiness",
            "Backend media-policy readiness:",
            "function settingsPolicyDeltaRows",
            "Save-candidate media-policy delta:",
            "Mutation guardrail: this delta is read-only and cannot save settings, launch work, mutate queues, publish, rename, or touch media",
        ):
            self.assertIn(fragment, settings_policy_impact_js)

        self.assertEqual(settings_view_status, 200)
        self.assertIn("javascript", settings_view_type)
        for fragment in (
            "function settingsBackendPolicyImpact",
            "function settingsBackendMediaPolicyReadiness",
            "function settingsPolicyDeltaRows",
        ):
            self.assertIn(fragment, settings_view_js)

        self.assertEqual(settings_overview_status, 200)
        self.assertIn("javascript", settings_overview_type)
        self.assertIn("function settingsMediaPolicyReadinessLine", settings_overview_js)
        self.assertIn("settings.media_policy_readiness", settings_overview_js)

        self.assertEqual(launch_risk_status, 200)
        self.assertIn("javascript", launch_risk_type)
        self.assertIn("Backend media-policy readiness", launch_risk_js)
        self.assertIn("media_policy_readiness", launch_risk_js)
        self.assertIn("Resolve blocked saved media-policy rows before launching unattended work.", launch_risk_js)

        self.assertEqual(launch_view_status, 200)
        self.assertIn("javascript", launch_view_type)
        self.assertIn("window.__launchViewRiskModule", launch_risk_js)
        self.assertIn("const launchRiskModule = window.__launchViewRiskModule || {}", launch_view_js)

        self.assertEqual(cross_status, 200)
        self.assertIn("javascript", cross_type)
        self.assertIn("createCrossPageSettingsModule", cross_js)
        self.assertEqual(cross_settings_status, 200)
        self.assertIn("javascript", cross_settings_type)
        self.assertIn("Backend media-policy readiness", cross_settings_js)
        self.assertIn("media readiness=", cross_settings_js)

        self.assertEqual(settings_status, 200)
        readiness = settings["media_policy_readiness"]  # type: ignore[index]
        policy_impact = settings["policy_impact"]  # type: ignore[index]
        self.assertEqual(policy_impact["schema_version"], "settings_policy_impact.v1")  # type: ignore[index]
        self.assertEqual(policy_impact["launch_risk_handoff"]["schema_version"], "settings_launch_risk_handoff.v1")  # type: ignore[index]
        self.assertEqual(readiness["schema_version"], "settings_media_policy_readiness.v1")  # type: ignore[index]
        self.assertEqual(readiness["operator_status"], "Ready")  # type: ignore[index]
        self.assertEqual(readiness["counts"]["blocked"], 0)  # type: ignore[index]
        self.assertEqual(readiness["counts"]["review"], 0)  # type: ignore[index]
        areas = {row["area"] for row in readiness["rows"]}  # type: ignore[index]
        for area in (
            "Routing / Output Size Check",
            "Container / subtitle preservation",
            "Subtitle language routing",
            "TX3G / mov_text SRT",
            "BDPGS OCR to SRT",
            "VobSub OCR to SRT",
            "ASS / SSA preservation",
            "Audio language / default track",
            "Audio passthrough / channels",
            "Publish / recovery safety",
            "Source preservation",
        ):
            self.assertIn(area, areas)


if __name__ == "__main__":
    unittest.main()
