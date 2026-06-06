from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.metrics.policy import METRICS_SCHEMA_VERSION, build_metrics_payload
from mediapipeline.contracts.api_commands import validate_api_command_payload
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.routes import GET_ROUTE_HANDLERS, POST_ROUTE_HANDLERS
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import CompletedJobRecord
from tests.python.desktop.test_application_facade import DummyWorkflowFacadeService, _resolved


WEBVIEW_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"


class MetricsFeatureTests(unittest.TestCase):
    def _get_json(self, url: str, token: str) -> tuple[int, dict]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        request = Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _post_json(self, url: str, token: str, payload: dict) -> tuple[int, dict]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_metrics_payload_aggregates_route_storage_production_and_workers(self) -> None:
        records = [
            CompletedJobRecord(
                sidecar_path=Path("Remux.pipeline.json"),
                payload={
                    "source_path": "Source/Remux.mkv",
                    "output_path": "Out/Remux.mkv",
                    "route": "remux",
                    "encoded_at": "2026-06-01T10:00:00-04:00",
                    "source_size": 1000,
                    "output_size": 1000,
                    "publish_state": "published",
                    "media_type": "movie",
                },
            ),
            CompletedJobRecord(
                sidecar_path=Path("Encode.pipeline.json"),
                payload={
                    "source_path": "Source/Encode.mkv",
                    "output_path": "Out/Encode.mkv",
                    "route": "encode",
                    "encoded_at": "2026-06-02T10:00:00-04:00",
                    "source_size": 3000,
                    "output_size": 1000,
                    "publish_state": "published",
                    "media_type": "tv",
                    "route_reason_code": "subtitle_srt_required",
                    "encode_selected_encoder": "hevc_nvenc",
                },
            ),
        ]

        payload = build_metrics_payload(
            records,
            completed_source="State/Completed/completed_jobs.jsonl",
            pending_publish={
                "schema_version": "desktop_pending_publish_preview.v1",
                "pending_root": "State/PendingPublish",
                "exists": True,
                "count": 1,
                "payload_count": 1,
                "total_bytes": 512,
                "total_size_text": "512 B",
                "state_counts": {"parked": 1},
                "route_counts": {"encode": 1},
                "issue_count": 0,
                "ready_count": 1,
            },
            network_workers={
                "schema_version": "desktop_network_workers.v1",
                "role": "coordinator",
                "source": "runtime_state_files",
                "rows": [
                    {
                        "worker_name": "worker-a",
                        "status": "idle",
                        "files_completed": 2,
                        "total_gb_encoded": 3.5,
                        "avg_speed_gbh": 7.0,
                    }
                ],
                "active_count": 1,
                "idle_count": 1,
                "total_count": 2,
                "session_completed": 4,
                "session_failed": 1,
            },
            final_library={
                "schema_version": "desktop_final_library_promotion_status.v1",
                "enabled": True,
                "pause_state": "idle",
                "counts": {"total": 2, "eligible": 1},
            },
            generated_at="2026-06-05T12:00:00Z",
        )

        self.assertEqual(payload["schema_version"], METRICS_SCHEMA_VERSION)
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["overview"]["total_jobs"], 2)
        self.assertEqual(payload["route_mix"]["remux_count"], 1)
        self.assertEqual(payload["route_mix"]["encode_count"], 1)
        self.assertEqual(payload["storage"]["total_data_produced_bytes"], 2000)
        self.assertEqual(payload["storage"]["gross_storage_saved_bytes"], 2000)
        self.assertEqual(payload["storage"]["net_storage_saved_bytes"], 2000)
        self.assertEqual(payload["storage"]["measurement_row_count"], 2)
        self.assertEqual(payload["coverage"]["completed_rows"], 2)
        self.assertEqual(payload["coverage"]["measured_rows"], 2)
        self.assertEqual(payload["coverage"]["measurement_percent"], 100.0)
        self.assertEqual(payload["production"]["pending_publish_bytes"], 512)
        self.assertEqual(payload["production"]["known_output_plus_pending_bytes"], 2512)
        self.assertEqual(payload["production"]["throughput"]["recent_completed_count"], 2)
        self.assertEqual(payload["production"]["throughput"]["recent_output_bytes"], 2000)
        self.assertEqual(payload["production"]["throughput"]["last_completed_at"], "2026-06-02T10:00:00-04:00")
        self.assertEqual(payload["workers"]["role"], "coordinator")
        self.assertEqual(payload["workers"]["session_completed"], 4)
        self.assertEqual(payload["workers"]["coordinator"]["session_failed"], 1)
        self.assertEqual(payload["workers"]["posture"]["failed_session_count"], 1)
        self.assertEqual(payload["workers"]["posture"]["handoff_target"], "network")
        reason_groups = {row["key"]: row for row in payload["route_mix"]["reason_groups"]}
        self.assertEqual(reason_groups["subtitle_policy"]["label"], "Subtitle requirement")
        self.assertEqual(reason_groups["unknown"]["severity"], "warning")
        attention_ids = {item["id"] for item in payload["attention_items"]}
        self.assertIn("unknown-route-reasons", attention_ids)
        self.assertIn("pending-publish-backlog", attention_ids)
        self.assertIn("worker-failures", attention_ids)
        self.assertEqual(payload["source_evidence"]["completed_manifest"]["proof_mode"], "summary")
        self.assertEqual(payload["source_evidence"]["metrics_backfill"]["source_count"], 0)

    def test_metrics_route_contracts_define_read_and_backfill_boundaries(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        self.assertIn("/api/metrics", GET_ROUTE_HANDLERS)
        self.assertEqual(GET_ROUTE_HANDLERS["/api/metrics"].method_name, "_metrics_payload")
        self.assertEqual(routes["/api/metrics"]["method"], "GET")
        self.assertEqual(routes["/api/metrics"]["effect"], "none")
        self.assertEqual(routes["/api/metrics"]["response_schema"], "desktop_metrics.v1")
        self.assertIn("without launching work", routes["/api/metrics"]["purpose"])
        self.assertIn("touching media files", routes["/api/metrics"]["purpose"])
        self.assertIn("/api/metrics/sources", POST_ROUTE_HANDLERS)
        self.assertIn("/api/metrics/backfill", POST_ROUTE_HANDLERS)
        self.assertEqual(POST_ROUTE_HANDLERS["/api/metrics/sources"].method_name, "_metrics_sources_payload")
        self.assertEqual(POST_ROUTE_HANDLERS["/api/metrics/backfill"].method_name, "_metrics_backfill_payload")
        self.assertEqual(routes["/api/metrics/sources"]["effect"], "metrics-state-write")
        self.assertEqual(routes["/api/metrics/backfill"]["effect"], "metrics-backfill-state-write")
        self.assertIn("Recursively read *.pipeline.json sidecars", routes["/api/metrics/backfill"]["purpose"])
        self.assertIn("does not rewrite sidecars", routes["/api/metrics/backfill"]["purpose"])
        self.assertEqual(
            validate_api_command_payload(
                "/api/metrics/sources",
                {"action": "add", "path": r"D:\Media", "label": "Drive D", "enabled": True},
            ),
            {"action": "add", "path": r"D:\Media", "label": "Drive D", "enabled": True},
        )
        self.assertEqual(
            validate_api_command_payload("/api/metrics/backfill", {"scope": "enabled", "max_sidecars": 100}),
            {"scope": "enabled", "max_sidecars": 100},
        )

    def test_local_api_metrics_route_returns_backend_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(root / "Source" / "Movie.mkv"),
                        "output_path": str(root / "Out" / "Movie.mkv"),
                        "route": "encode",
                        "encoded_at": "2026-06-05T10:00:00-04:00",
                        "source_size": 4096,
                        "output_size": 2048,
                        "publish_state": "published",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="metrics-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/metrics", "metrics-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_metrics.v1")
        self.assertEqual(payload["overview"]["total_jobs"], 1)
        self.assertEqual(payload["overview"]["encode_count"], 1)
        self.assertEqual(payload["storage"]["net_storage_saved_bytes"], 2048)
        self.assertEqual(payload["coverage"]["completed_rows"], 1)
        self.assertEqual(payload["route_mix"]["reason_groups"][0]["label"], "Unknown decision reason")
        self.assertEqual(payload["production"]["throughput"]["recent_completed_count"], 1)
        self.assertEqual(payload["workers"]["posture"]["handoff_label"], "Open Workers")
        self.assertEqual(payload["source_evidence"]["completed_manifest"]["source"], str(manifest))

    def test_local_api_metrics_sources_backfill_multiple_recursive_roots(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            drive_a = root / "DriveA"
            drive_b = root / "DriveB"
            sidecar_a = drive_a / "Movies" / "Movie A" / "MovieA.pipeline.json"
            sidecar_b = drive_b / "TV" / "Show" / "Season 01" / "Episode.pipeline.json"
            payload_a = {
                "source_identity_v2": "movie-a",
                "source_path": str(drive_a / "Movies" / "Movie A" / "MovieA.mkv"),
                "output_path": str(root / "Out" / "MovieA.mkv"),
                "route": "remux",
                "encoded_at": "2026-06-01T10:00:00Z",
                "source_size": 1000,
                "output_size": 1000,
                "publish_state": "published",
                "media_type": "movie",
            }
            payload_b = {
                "source_identity_v2": "episode-b",
                "source_path": str(drive_b / "TV" / "Show" / "Season 01" / "Episode.mkv"),
                "output_path": str(root / "Out" / "Episode.mkv"),
                "route": "encode",
                "encoded_at": "2026-06-02T10:00:00Z",
                "source_size": 3000,
                "output_size": 1000,
                "publish_state": "published",
                "media_type": "tv",
            }
            sidecar_a.parent.mkdir(parents=True)
            sidecar_b.parent.mkdir(parents=True)
            sidecar_a.write_text(json.dumps(payload_a, sort_keys=True), encoding="utf-8")
            sidecar_b.write_text(json.dumps(payload_b, sort_keys=True), encoding="utf-8")
            original_a = sidecar_a.read_text(encoding="utf-8")
            original_b = sidecar_b.read_text(encoding="utf-8")
            resolved = _resolved(root)
            resolved.state_root = state_root
            resolved.completed_manifest_path = root / "State" / "Completed" / "completed_jobs.jsonl"
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="metrics-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                add_a_status, add_a = self._post_json(
                    f"{server.url}/api/metrics/sources",
                    "metrics-token",
                    {"action": "add", "path": str(drive_a), "label": "Drive A", "enabled": True},
                )
                add_b_status, add_b = self._post_json(
                    f"{server.url}/api/metrics/sources",
                    "metrics-token",
                    {"action": "add", "path": str(drive_b), "label": "Drive B", "enabled": True},
                )
                backfill_status, backfill = self._post_json(
                    f"{server.url}/api/metrics/backfill",
                    "metrics-token",
                    {"scope": "enabled"},
                )
                metrics_status, metrics = self._get_json(f"{server.url}/api/metrics", "metrics-token")
            finally:
                server.stop()
            sources_file_exists = (state_root / "Metrics" / "metrics_sources.json").exists()
            cache_file_exists = (state_root / "Metrics" / "metrics_sidecar_backfill.jsonl").exists()
            status_file_exists = (state_root / "Metrics" / "metrics_backfill_status.json").exists()
            sidecar_a_unchanged = sidecar_a.read_text(encoding="utf-8") == original_a
            sidecar_b_unchanged = sidecar_b.read_text(encoding="utf-8") == original_b

        self.assertEqual(add_a_status, 200)
        self.assertTrue(add_a["ok"])
        self.assertEqual(add_b_status, 200)
        self.assertTrue(add_b["ok"])
        self.assertEqual(backfill_status, 200)
        self.assertTrue(backfill["ok"])
        self.assertEqual(backfill["data"]["backfill"]["loaded_count"], 2)
        self.assertEqual(metrics_status, 200)
        self.assertEqual(metrics["overview"]["total_jobs"], 2)
        self.assertEqual(metrics["route_mix"]["remux_count"], 1)
        self.assertEqual(metrics["route_mix"]["encode_count"], 1)
        self.assertEqual(metrics["storage"]["total_data_produced_bytes"], 2000)
        self.assertEqual(metrics["storage"]["net_storage_saved_bytes"], 2000)
        self.assertEqual(metrics["coverage"]["source_count"], 2)
        self.assertEqual(metrics["coverage"]["enabled_source_count"], 2)
        self.assertEqual(metrics["coverage"]["cached_backfill_count"], 2)
        self.assertEqual(metrics["source_backfill"]["source_count"], 2)
        self.assertEqual(metrics["source_backfill"]["enabled_source_count"], 2)
        self.assertEqual(metrics["source_backfill"]["enabled_cache_record_count"], 2)
        self.assertEqual(metrics["source_evidence"]["metrics_backfill"]["enabled_cache_record_count"], 2)
        self.assertTrue(sources_file_exists)
        self.assertTrue(cache_file_exists)
        self.assertTrue(status_file_exists)
        self.assertTrue(sidecar_a_unchanged)
        self.assertTrue(sidecar_b_unchanged)

    def test_webview_metrics_tab_keeps_approved_subtabs_with_source_backfill_controls(self) -> None:
        shell = (WEBVIEW_ROOT / "partials" / "app-shell-start.html").read_text(encoding="utf-8")
        index = (WEBVIEW_ROOT / "index.html").read_text(encoding="utf-8")
        page = (WEBVIEW_ROOT / "partials" / "page-metrics.html").read_text(encoding="utf-8")
        app_js = (WEBVIEW_ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        metrics_js = (WEBVIEW_ROOT / "assets" / "metricsView.js").read_text(encoding="utf-8")
        styles = (WEBVIEW_ROOT / "assets" / "styles.components.css").read_text(encoding="utf-8")

        self.assertIn('data-page="metrics"', shell)
        self.assertIn("partials/page-metrics.html", index)
        self.assertIn('/assets/metricsView.js', index)
        self.assertIn('apiGet("/api/metrics")', app_js)
        self.assertIn("window.mediaPipelineMetricsView?.renderMetrics?.(values.metrics)", app_js)
        self.assertIn('postMetricsCommand("/api/metrics/sources"', metrics_js)
        self.assertIn('postMetricsCommand("/api/metrics/backfill"', metrics_js)
        self.assertNotIn("data-control-action", page)
        self.assertIn('id="metrics-source-path"', page)
        self.assertIn('id="metrics-source-add-button"', page)
        self.assertIn('id="metrics-backfill-button"', page)
        self.assertIn('id="metrics-sources-rows"', page)
        self.assertIn("Completed Jobs", page)
        self.assertIn("Net Saved", page)
        self.assertIn("Output Written", page)
        self.assertIn('id="metrics-attention-rows"', page)
        self.assertIn('id="metrics-coverage-rows"', page)
        self.assertIn('id="metrics-reason-group-rows"', page)
        self.assertIn('id="metrics-storage-breakdown-rows"', page)
        self.assertIn("<th scope=\"col\" class=\"num\">Source</th>", page)
        self.assertIn("<th scope=\"col\" class=\"num\">Excluded</th>", page)
        self.assertIn('id="metrics-throughput-rows"', page)
        self.assertIn('id="metrics-worker-posture"', page)
        self.assertIn('data-cross-page-target="network"', page)
        self.assertIn('document.createElementNS(SVG_NS, "svg")', metrics_js)
        self.assertIn('setAttribute("role", "img")', metrics_js)
        self.assertIn('const chartEntries = entries.filter((row) => !row.valueOnly);', metrics_js)
        self.assertIn('const countFormatter = new Intl.NumberFormat("en-US"', metrics_js)
        self.assertIn('function percentText(value)', metrics_js)
        self.assertIn('function gbhText(value)', metrics_js)
        self.assertIn('renderAttentionRows(payload.attention_items || [])', metrics_js)
        self.assertIn('renderCoverageRows(payload.coverage || {})', metrics_js)
        self.assertIn('renderReasonGroupRows(routeMix.reason_groups || [])', metrics_js)
        self.assertIn('renderThroughputRows(production.throughput || {})', metrics_js)
        self.assertIn('renderWorkerPosture(workers)', metrics_js)
        self.assertIn('label: "Output written", value: storage.output_written_bytes || 0, text: storage.output_written_text || "0 B", tone: "pending", valueOnly: true', metrics_js)
        self.assertIn(".metrics-chart-image", styles)
        self.assertIn(".metrics-chart-svg-fill", styles)
        self.assertIn(".metrics-handoff-row", styles)
        for tab in ("overview", "routes", "storage", "production", "workers"):
            self.assertIn(f'data-metrics-tab="{tab}"', page)
            self.assertIn(f'data-metrics-tab-panel="{tab}"', page)
        self.assertNotIn('data-metrics-tab="review"', page.lower())
        self.assertIn("window.mediaPipelineMetricsView = {", metrics_js)


if __name__ == "__main__":
    unittest.main()
