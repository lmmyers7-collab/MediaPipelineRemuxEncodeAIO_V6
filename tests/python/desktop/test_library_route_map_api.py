from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.queue.source_inventory import (
    queue_scan_status_path,
    queue_scan_status_payload,
    queue_source_inventory_path,
    write_json_artifact,
)
from tests.python.desktop.application_facade_test_support import DummyFacadeService, _resolved


def _route_map_config() -> dict[str, object]:
    return {
        "SourceMovies": "C:/Media/Movies",
        "SourceTV": "C:/Media/TV",
        "Outsource": "D:/Out",
        "RoutingProfile": "plex_direct_stream",
        "RouteThresholdMode": "size_or_bitrate",
        "SizeGuardMode": "warn",
        "VideoCodec": "hevc_nvenc",
        "OutputContainer": "mkv",
        "LibraryProfiles": [
            {
                "id": "movies",
                "name": "Movies",
                "enabled": True,
                "designation": "movie",
                "source_path": "C:/Media/Movies",
                "output_path": "D:/Out/Movies",
            },
            {
                "id": "tv-child",
                "name": "TV Child",
                "enabled": True,
                "designation": "tv",
                "source_path": "C:/Media/TV/Shows",
                "output_path": "D:/Out/TV",
            },
        ],
    }


def _get_json(url: str, token: str | None = None) -> tuple[int, dict[str, object]]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class LibraryRouteMapLocalApiTests(unittest.TestCase):
    def test_route_map_read_routes_are_token_protected_schema_strict_and_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = _route_map_config()
            resolved.state_root = None
            server = LocalApiServer(
                facade,
                token="library-token",
                resolved_provider=lambda: resolved,
                command_journal_path=root / "command_history.json",
            )
            routes = {
                "/api/libraries/summary": "desktop_libraries_summary.v1",
                "/api/libraries/route-map": "library_route_map.v1",
                "/api/libraries/route-map/trace": "library_route_trace.v1",
                "/api/libraries/route-map/compare": "library_profile_compare.v1",
                "/api/libraries/route-map/validation": "library_route_validation_handoff.v1",
            }
            queries = {
                "/api/libraries/summary": {},
                "/api/libraries/route-map": {},
                "/api/libraries/route-map/trace": {
                    "source_path": "C:/Media/TV/Shows/Show/S01E01.mkv",
                },
                "/api/libraries/route-map/compare": {
                    "left_id": "movies",
                    "right_id": "tv-child",
                },
                "/api/libraries/route-map/validation": {
                    "limit": "5",
                },
            }
            try:
                server.start()
                unauthorized_status, unauthorized = _get_json(f"{server.url}/api/libraries/route-map")
                payloads: dict[str, dict[str, object]] = {}
                for route, schema in routes.items():
                    query = urlencode(queries[route])
                    suffix = f"?{query}" if query else ""
                    status, payload = _get_json(f"{server.url}{route}{suffix}", token="library-token")
                    self.assertEqual(status, 200, route)
                    self.assertEqual(payload["schema_version"], schema, route)
                    self.assertEqual(payload["evidence_authority"], "backend", route)
                    self.assertTrue(payload["read_only"], route)
                    self.assertFalse(payload["mutation_enabled"], route)
                    self.assertEqual(payload["effects"], [], route)
                    self.assertIn("No launch", payload["guardrail"], route)
                    payloads[route] = payload
                no_state_status, no_state_summary = _get_json(f"{server.url}/api/libraries/summary", token="library-token")
                resolved.state_root = root / "State"
                resolved.queue_snapshot_path = resolved.state_root / "Progress" / "queue_snapshot.json"
                status_path = queue_scan_status_path(resolved)
                inventory_path = queue_source_inventory_path(resolved)
                assert status_path is not None
                assert inventory_path is not None
                write_json_artifact(
                    status_path,
                    queue_scan_status_payload(
                        scan_id="scan-active",
                        status="running",
                        phase="inventory",
                        mode="inventory_then_curate",
                        started_at_utc="2026-06-28T10:00:00Z",
                        updated_at_utc="2026-06-28T10:01:00Z",
                        status_path=status_path,
                        inventory_path=inventory_path,
                        queue_snapshot_path=resolved.queue_snapshot_path,
                    ),
                )
                active_status, active_summary = _get_json(f"{server.url}/api/libraries/summary", token="library-token")
                write_json_artifact(
                    inventory_path,
                    {
                        "schema_version": "desktop_queue_source_inventory.v1",
                        "scan_id": "scan-complete",
                        "status": "inventory_complete",
                        "curation_state": "uncurated",
                        "evidence_authority": "backend_source_inventory",
                        "launchable": False,
                        "produced_at_utc": "2026-06-28T10:03:00Z",
                        "row_count": 3,
                        "row_limit": 5000,
                        "rows_truncated": False,
                        "sidecar_count": 8,
                        "sidecar_counts_truncated": False,
                        "sidecar_source_key_counts": {
                            "LibraryProfiles:tv-child": 5,
                            "SourceMovies": 3,
                        },
                        "source_key_counts": {
                            "LibraryProfiles:tv-child": 1,
                            "SourceMovies": 2,
                        },
                        "roots": [
                            {
                                "path": "C:/Media/Movies",
                                "media_kind": "movie",
                                "source_key": "SourceMovies",
                                "label": "Configured movie source",
                            },
                            {
                                "path": "C:/Media/TV/Shows",
                                "media_kind": "tv",
                                "source_key": "LibraryProfiles:tv-child",
                                "label": "Library profile tv-child",
                            },
                        ],
                        "rows": [],
                        "summary_lines": [],
                        "warnings": [],
                    },
                )
                write_json_artifact(
                    status_path,
                    queue_scan_status_payload(
                        scan_id="scan-complete",
                        status="completed",
                        phase="complete",
                        mode="inventory_then_curate",
                        started_at_utc="2026-06-28T10:00:00Z",
                        updated_at_utc="2026-06-28T10:04:00Z",
                        completed_at_utc="2026-06-28T10:04:00Z",
                        inventory_count=3,
                        curated_row_count=3,
                        status_path=status_path,
                        inventory_path=inventory_path,
                        queue_snapshot_path=resolved.queue_snapshot_path,
                    ),
                )
                complete_status, complete_summary = _get_json(f"{server.url}/api/libraries/summary", token="library-token")
                history_status, history = _get_json(f"{server.url}/api/commands?limit=10", token="library-token")
            finally:
                server.stop()

        self.assertEqual(unauthorized_status, 401)
        self.assertIn("auth", json.dumps(unauthorized).casefold())
        self.assertEqual(history_status, 200)
        self.assertEqual(history["schema_version"], "desktop_command_history.v1")
        self.assertEqual(history["entries"], [])
        self.assertEqual(no_state_status, 200)
        self.assertEqual(no_state_summary["schema_version"], "desktop_libraries_summary.v1")
        self.assertTrue(all(row["scan_status"] == "not_scanned" for row in no_state_summary["rows"]))
        self.assertIsNone(no_state_summary["rows"][0]["media_file_count"])
        self.assertEqual(active_status, 200)
        self.assertTrue(all(row["scan_status"] == "scanning" for row in active_summary["rows"]))
        self.assertEqual(complete_status, 200)
        self.assertEqual(complete_summary["totals"]["media_file_count"], 3)
        self.assertEqual(complete_summary["totals"]["sidecar_file_count"], 8)
        rows_by_id = {row["library_id"]: row for row in complete_summary["rows"]}
        self.assertEqual(rows_by_id["movies"]["source_key"], "SourceMovies")
        self.assertEqual(rows_by_id["movies"]["media_file_count"], 2)
        self.assertEqual(rows_by_id["movies"]["sidecar_file_count"], 3)
        self.assertEqual(rows_by_id["tv-child"]["source_key"], "LibraryProfiles:tv-child")
        self.assertEqual(rows_by_id["tv-child"]["media_file_count"], 1)
        self.assertEqual(rows_by_id["tv-child"]["sidecar_file_count"], 5)
        self.assertTrue(all(row["scan_status"] == "complete" for row in complete_summary["rows"]))
        self.assertGreaterEqual(payloads["/api/libraries/route-map"]["profile_count"], 2)
        self.assertIn("library_match", payloads["/api/libraries/route-map/trace"])
        self.assertEqual(payloads["/api/libraries/route-map/compare"]["compare_status"], "changed")
        self.assertIn("proof_sections", payloads["/api/libraries/route-map/validation"])


if __name__ == "__main__":
    unittest.main()
