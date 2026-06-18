from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.library_roots import (
    auto_source_path_map_from_libraries,
    libraries_response_from_config,
    merge_manual_and_auto_path_maps,
)
from mediapipeline.desktop.network.path_map import apply_source_path_map, parse_source_path_map
from mediapipeline.desktop.network.worker import WorkerDispatcher


def _config(*, movies: str, tv: str, anime: str) -> dict[str, object]:
    return {
        "SourceMovies": movies,
        "SourceTV": tv,
        "Outsource": r"D:\Processed",
        "LibraryProfiles": [
            {
                "id": "anime",
                "name": "Anime",
                "enabled": True,
                "designation": "tv",
                "source_path": anime,
                "output_path": r"D:\Processed\Anime",
            }
        ],
    }


def _worker(config: dict[str, object], manual_map: str = "") -> WorkerDispatcher:
    worker = WorkerDispatcher.__new__(WorkerDispatcher)
    worker.app = SimpleNamespace(resolved=SimpleNamespace(config_data=config))
    worker._base_url = "http://coordinator.test:7830"
    worker._auth_token = "token"
    worker._manual_source_path_map = parse_source_path_map(manual_map)
    worker._auto_source_path_map = []
    worker._source_path_map = list(worker._manual_source_path_map)
    worker._active_job_lock = threading.Lock()
    worker._wakeup = threading.Event()
    worker._library_auto_map_last_refresh = 0.0
    worker._library_auto_map_refresh_seconds = 300.0
    worker._library_auto_map_last_error = ""
    return worker


class NetworkPathAutoMapTests(unittest.TestCase):
    def test_manual_path_map_rejects_relative_and_drive_relative_replacements(self) -> None:
        for replacement in (r"Relative\WorkerRoot", r"D:WorkerRoot", r"\WorkerRoot"):
            with self.subTest(replacement=replacement):
                mappings = parse_source_path_map(json.dumps({r"C:\Coordinator": replacement}))

                self.assertEqual(mappings, [])

    def test_manual_path_map_rejects_parent_traversal_in_roots_and_claim_tail(self) -> None:
        self.assertEqual(
            parse_source_path_map(json.dumps({r"C:\Coordinator\..\Secret": r"D:\Worker"})),
            [],
        )
        self.assertEqual(
            parse_source_path_map(json.dumps({r"C:\Coordinator": r"D:\Worker\..\Secret"})),
            [],
        )

        mappings = parse_source_path_map(json.dumps({r"C:\Coordinator": r"D:\Worker"}))

        with self.assertRaisesRegex(ValueError, "parent traversal"):
            apply_source_path_map(r"C:\Coordinator\..\Secret\Movie.mkv", mappings)

    def test_manual_path_map_handles_unc_case_and_exact_prefix_boundaries(self) -> None:
        mappings = parse_source_path_map(json.dumps({r"\\SERVER\Share\Media": r"D:\WorkerMedia"}))

        self.assertEqual(
            apply_source_path_map(r"\\server\share\media\Show\S01E01.mkv", mappings),
            r"D:\WorkerMedia\Show\S01E01.mkv",
        )
        self.assertEqual(
            apply_source_path_map(r"\\server\share\media-extra\Movie.mkv", mappings),
            r"\\server\share\media-extra\Movie.mkv",
        )

    def test_auto_path_maps_sort_deepest_prefix_after_manual_precedence(self) -> None:
        merged = merge_manual_and_auto_path_maps(
            [(r"C:\Coord\Shows", r"X:\ManualShows")],
            [
                (r"C:\Coord", r"D:\Broad"),
                (r"C:\Coord\Shows", r"D:\AutoShows"),
                (r"C:\Coord\Shows\Anime", r"D:\Anime"),
            ],
        )

        self.assertEqual(
            merged,
            [
                (r"C:\Coord\Shows", r"X:\ManualShows"),
                (r"C:\Coord\Shows\Anime", r"D:\Anime"),
                (r"C:\Coord", r"D:\Broad"),
            ],
        )

    def test_coordinator_libraries_response_exposes_enabled_library_roots(self) -> None:
        config = _config(
            movies=r"C:\Coord\Movies",
            tv=r"C:\Coord\TV",
            anime=r"E:\Coord\Anime",
        )
        payload = libraries_response_from_config(config)

        self.assertEqual(payload["schema_version"], "desktop_network_libraries.v1")
        rows = {row["library_id"]: row for row in payload["libraries"]}
        self.assertEqual(rows["movies"]["source_root"], r"C:\Coord\Movies")
        self.assertEqual(rows["movies"]["designation"], "movie")
        self.assertEqual(rows["tv"]["source_root"], r"C:\Coord\TV")
        self.assertEqual(rows["anime"]["source_root"], r"E:\Coord\Anime")
        self.assertEqual(rows["anime"]["output_root"], r"D:\Processed\Anime")

    def test_http_libraries_returns_coordinator_resolved_library_roots(self) -> None:
        sent: list[tuple[dict, int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._app = SimpleNamespace(
            resolved=SimpleNamespace(
                config_data=_config(
                    movies=r"C:\Coord\Movies",
                    tv=r"C:\Coord\TV",
                    anime=r"E:\Coord\Anime",
                )
            )
        )
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        CoordinatorDispatcher._http_libraries(dispatcher, handler, {})  # type: ignore[arg-type]

        self.assertEqual(sent[-1][1], 200)
        rows = {row["library_id"]: row for row in sent[-1][0]["libraries"]}
        self.assertEqual(rows["movies"]["source_root"], r"C:\Coord\Movies")
        self.assertEqual(rows["tv"]["source_root"], r"C:\Coord\TV")
        self.assertEqual(rows["anime"]["source_root"], r"E:\Coord\Anime")

    def test_auto_map_pairs_library_ids_and_preserves_manual_precedence(self) -> None:
        coordinator = libraries_response_from_config(
            _config(movies=r"C:\Coord\Movies", tv=r"C:\Coord\TV", anime=r"E:\Coord\Anime")
        )["libraries"]
        worker_config = _config(
            movies=r"\\WORKER\Movies",
            tv=r"\\WORKER\TV",
            anime=r"\\WORKER\Anime",
        )
        manual_map = json.dumps({r"C:\Coord\Movies": r"X:\ManualMovies"})
        worker = _worker(worker_config, manual_map=manual_map)

        worker.update_library_auto_map(coordinator)

        self.assertEqual(
            auto_source_path_map_from_libraries(coordinator, worker_config),
            [
                (r"C:\Coord\Movies", r"\\WORKER\Movies"),
                (r"C:\Coord\TV", r"\\WORKER\TV"),
                (r"E:\Coord\Anime", r"\\WORKER\Anime"),
            ],
        )
        self.assertEqual(worker.runtime_descriptor()["path_map_entries"], 3)
        self.assertEqual(worker._apply_path_map(r"C:\Coord\Movies\Movie.mkv"), r"X:\ManualMovies\Movie.mkv")
        self.assertEqual(worker._apply_path_map(r"C:\Coord\TV\Show\S01E01.mkv"), r"\\WORKER\TV\Show\S01E01.mkv")
        self.assertEqual(worker._apply_path_map(r"E:\Coord\Anime\Series\E01.mkv"), r"\\WORKER\Anime\Series\E01.mkv")

    def test_worker_refreshes_auto_map_from_coordinator_libraries_endpoint(self) -> None:
        coordinator_payload = libraries_response_from_config(
            _config(movies=r"C:\Coord\Movies", tv=r"C:\Coord\TV", anime=r"E:\Coord\Anime")
        )
        worker = _worker(
            _config(
                movies=r"\\WORKER\Movies",
                tv=r"\\WORKER\TV",
                anime=r"\\WORKER\Anime",
            )
        )
        requested_paths: list[str] = []

        def fake_get(path: str, params: dict[str, str] | None = None) -> dict:
            _ = params
            requested_paths.append(path)
            return coordinator_payload

        worker._http_get = fake_get  # type: ignore[method-assign]

        worker._maybe_refresh_library_auto_map(force=True)

        self.assertEqual(requested_paths, ["/api/libraries"])
        self.assertEqual(worker.runtime_descriptor()["path_map_entries"], 3)
        self.assertEqual(worker._apply_path_map(r"C:\Coord\TV\Show\S01E01.mkv"), r"\\WORKER\TV\Show\S01E01.mkv")


if __name__ == "__main__":
    unittest.main()
