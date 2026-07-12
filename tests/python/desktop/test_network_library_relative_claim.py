from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.queue.snapshot import queue_record_from_snapshot_row
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.protocol import ClaimResponse
from mediapipeline.desktop.network.worker import WorkerDispatcher


def _config(*, movies: str = r"C:\Coord\Movies", tv: str = r"C:\Coord\TV") -> dict[str, object]:
    return {
        "SourceMovies": movies,
        "SourceTV": tv,
        "Outsource": r"D:\Processed",
    }


class NetworkLibraryRelativeClaimTests(unittest.TestCase):
    def test_claim_response_round_trips_additive_library_fields(self) -> None:
        claim = ClaimResponse(
            status="ok",
            job_id="job-1",
            source_path=r"C:\Coord\TV\Show\S01E01.mkv",
            library_id="tv",
            relative_path=r"Show\S01E01.mkv",
            priority=True,
            estimated_size_gb=2.5,
            retry_on_failure=False,
            retry_after_seconds=7,
        )

        round_tripped = ClaimResponse.from_dict(claim.to_dict())
        legacy = ClaimResponse.from_dict({"status": "ok", "source_path": r"C:\Coord\Movie.mkv"})

        self.assertEqual(round_tripped.library_id, "tv")
        self.assertEqual(round_tripped.relative_path, r"Show\S01E01.mkv")
        self.assertFalse(round_tripped.retry_on_failure)
        self.assertEqual(round_tripped.retry_after_seconds, 7)
        self.assertEqual(legacy.library_id, "")
        self.assertEqual(legacy.relative_path, "")

    def test_coordinator_claim_populates_library_relative_fields_from_record(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            state_path = Path(raw_root) / "coordinator_inflight.json"
            record = SimpleNamespace(
                source_path=Path(r"C:\Coord\TV\Show\S01E01.mkv"),
                source_root=Path(r"C:\Coord\TV"),
                library_id="tv",
                relative_path=r"Show\S01E01.mkv",
                is_priority=False,
                size_gb=1.25,
            )
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = __import__(
                "mediapipeline.desktop.network.registry",
                fromlist=["InFlightRegistry"],
            ).InFlightRegistry()
            dispatcher._claim_lock = threading.Lock()
            dispatcher._accepting_claims = True
            dispatcher._app = SimpleNamespace(
                resolved=SimpleNamespace(config_data=_config()),
                queue_records=[record],
                failure_records=[],
            )
            dispatcher._config = _config  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: state_path
            dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            CoordinatorDispatcher._http_claim(
                dispatcher,
                handler,  # type: ignore[arg-type]
                {"worker_id": "worker-1", "worker_name": "Worker One"},
            )

        payload = sent[-1][0]
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["library_id"], "tv")
        self.assertEqual(payload["relative_path"], r"Show\S01E01.mkv")

    def test_coordinator_claim_derives_library_fields_from_source_root_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            state_path = Path(raw_root) / "coordinator_inflight.json"
            record = SimpleNamespace(
                source_path=Path(r"C:\Coord\Movies\Movie.mkv"),
                source_root=Path(r"C:\Coord\Movies"),
                is_priority=False,
                size_gb=1.25,
            )
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = __import__(
                "mediapipeline.desktop.network.registry",
                fromlist=["InFlightRegistry"],
            ).InFlightRegistry()
            dispatcher._claim_lock = threading.Lock()
            dispatcher._accepting_claims = True
            dispatcher._app = SimpleNamespace(
                resolved=SimpleNamespace(config_data=_config()),
                queue_records=[record],
                failure_records=[],
            )
            dispatcher._config = _config  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: state_path
            dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            CoordinatorDispatcher._http_claim(
                dispatcher,
                handler,  # type: ignore[arg-type]
                {"worker_id": "worker-1", "worker_name": "Worker One"},
            )

        payload = sent[-1][0]
        self.assertEqual(payload["library_id"], "movies")
        self.assertEqual(payload["relative_path"], "Movie.mkv")

    def test_worker_prefers_library_relative_resolution_before_prefix_maps(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(
            resolved=SimpleNamespace(
                config_data=_config(movies=r"\\WORKER\Movies", tv=r"\\WORKER\TV")
            )
        )
        worker._manual_source_path_map = []
        worker._auto_source_path_map = []
        worker._source_path_map = []
        worker._active_job_lock = threading.Lock()
        claim = ClaimResponse(
            status="ok",
            job_id="job-1",
            source_path=r"C:\Coord\TV\Show\S01E01.mkv",
            library_id="tv",
            relative_path=r"Show\S01E01.mkv",
        )
        worker._apply_path_map = lambda _path: r"X:\ShouldNotWin.mkv"  # type: ignore[method-assign]

        resolved, mode = worker.resolve_claim_source_path(claim)

        self.assertEqual(mode, "library_relative")
        self.assertEqual(resolved, r"\\WORKER\TV\Show\S01E01.mkv")

    def test_worker_falls_back_to_prefix_map_for_legacy_claims(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(resolved=SimpleNamespace(config_data=_config()))
        claim = ClaimResponse(
            status="ok",
            job_id="job-1",
            source_path=r"C:\Coord\TV\Show\S01E01.mkv",
        )
        worker._apply_path_map = lambda _path: r"\\WORKER\TV\Show\S01E01.mkv"  # type: ignore[method-assign]

        resolved, mode = worker.resolve_claim_source_path(claim)

        self.assertEqual(mode, "path_map")
        self.assertEqual(resolved, r"\\WORKER\TV\Show\S01E01.mkv")

    def test_snapshot_queue_record_preserves_library_id_for_network_claims(self) -> None:
        record = queue_record_from_snapshot_row(
            {
                "source_path": r"C:\Coord\TV\Show\S01E01.mkv",
                "root_path": r"C:\Coord\TV",
                "media_kind": "tv",
                "display_name": "S01E01.mkv",
                "relative_path": r"Show\S01E01.mkv",
                "library_id": "tv",
            }
        )

        self.assertEqual(getattr(record, "library_id", ""), "tv")
        self.assertEqual(record.relative_path, r"Show\S01E01.mkv")

    def test_library_relative_resolution_rejects_absolute_or_parent_relative_path(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(resolved=SimpleNamespace(config_data=_config(tv=r"\\WORKER\TV")))
        worker._apply_path_map = lambda path: path  # type: ignore[method-assign]
        for relative_path in (r"C:\Escape.mkv", r"..\Escape.mkv", r"Show\..\Escape.mkv"):
            with self.subTest(relative_path=relative_path):
                claim = ClaimResponse(
                    status="ok",
                    job_id="job-1",
                    source_path=r"C:\Coord\TV\Show\S01E01.mkv",
                    library_id="tv",
                    relative_path=relative_path,
                )

                resolved, mode = worker.resolve_claim_source_path(claim)

                self.assertEqual(mode, "path_map")
                self.assertEqual(resolved, claim.source_path)
        self.assertNotIn("Escape", json.dumps(ClaimResponse.empty().to_dict()))


if __name__ == "__main__":
    unittest.main()
