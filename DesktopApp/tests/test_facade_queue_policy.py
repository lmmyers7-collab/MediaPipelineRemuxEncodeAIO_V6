from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.queue.policy import (
    EMPTY_QUEUE_SNAPSHOT_WARNING,
    INVALID_QUEUE_SNAPSHOT_WARNING,
    NO_QUEUE_SNAPSHOT_WARNING,
    QUEUE_PREVIEW_SERVICE_WARNING,
    queue_preview_metadata,
    queue_preview_rows,
    queue_preview_warnings,
    queue_record_to_row,
    queue_source_scan_progress_payload,
)
from mediapipeline_desktop_app.models import QueueRecord


def _record() -> QueueRecord:
    return QueueRecord(
        source_path=Path("C:/Source/TV/Show/Season 01/Show - S01E01.mkv"),
        source_root=Path("C:/Source/TV"),
        media_type="TV",
        is_priority=True,
        priority_reasons=["manual marker"],
        priority_rank=1.5,
        sort_name="show",
        display_name="Show - S01E01.mkv",
        relative_path="Show\\Season 01\\Show - S01E01.mkv",
        show_folder="Show",
        season_folder="Season 01",
        season_number=1,
        episode_number=1,
        source_mtime=1778173200.0,
        size_gb=1.25,
        route_name="remux",
        route_reason="already compatible",
        matched_show_override="",
        queue_index=1,
        queue_total=12,
        phase="tv",
        global_order=7,
    )


class QueueFacadePolicyTests(unittest.TestCase):
    def test_queue_record_to_row_preserves_operator_fields(self) -> None:
        row = queue_record_to_row(_record())

        self.assertEqual(row["source_path"], str(Path("C:/Source/TV/Show/Season 01/Show - S01E01.mkv")))
        self.assertEqual(row["source_root"], str(Path("C:/Source/TV")))
        self.assertEqual(row["media_type"], "TV")
        self.assertTrue(row["is_priority"])
        self.assertEqual(row["priority_reasons"], ["manual marker"])
        self.assertEqual(row["priority_rank"], 1.5)
        self.assertEqual(row["display_name"], "Show - S01E01.mkv")
        self.assertEqual(row["relative_path"], "Show\\Season 01\\Show - S01E01.mkv")
        self.assertEqual(row["show_folder"], "Show")
        self.assertEqual(row["season_folder"], "Season 01")
        self.assertEqual(row["season_number"], 1)
        self.assertEqual(row["episode_number"], 1)
        self.assertEqual(row["size_gb"], 1.25)
        self.assertEqual(row["route_name"], "remux")
        self.assertEqual(row["route_reason"], "already compatible")
        self.assertEqual(row["queue_index"], 1)
        self.assertEqual(row["queue_total"], 12)
        self.assertEqual(row["phase"], "tv")
        self.assertEqual(row["global_order"], 7)
        self.assertEqual(row["available_open_targets"], ["source_file", "source_folder", "source_root"])

    def test_queue_preview_rows_filter_non_dicts_and_keep_invalid_rows(self) -> None:
        def factory(raw: dict[str, object]) -> object:
            if raw.get("source_path") == "bad":
                raise ValueError("bad source")
            if raw.get("source_path") == "not-record":
                return {"ignored": True}
            return _record()

        rows = queue_preview_rows(
            [
                {"source_path": "ok"},
                "not-a-row",
                {"source_path": "bad", "raw_value": 5},
                {"source_path": "not-record"},
            ],
            factory,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["route_name"], "remux")
        self.assertEqual(rows[1]["status"], "invalid")
        self.assertEqual(rows[1]["error"], "bad source")
        self.assertEqual(rows[1]["raw"], {"source_path": "bad", "raw_value": 5})
        self.assertEqual(rows[1]["available_open_targets"], [])

    def test_queue_preview_rows_surface_library_profile_evidence(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Anime/Show/Season 01/Show - S01E01.mkv",
                    "root_path": "C:/Anime",
                    "library_id": "anime",
                    "library_name": "Anime",
                    "library_designation": "tv",
                    "library_output_root": "D:/AnimeProcessed",
                    "library_settings_override_keys": ["AudioMaxChannels", "SubKeepLanguages"],
                    "library_settings_overrides": {"AudioMaxChannels": 6},
                    "library_effective_settings": {"AudioMaxChannels": 6, "VideoQuality": 22},
                    "route_decision_trace": [{"code": "routing_profile_selected"}, {"code": "size_evaluated"}],
                    "estimated_bitrate_mbps": 12.5,
                    "route_size_threshold_gb": 3,
                    "route_bitrate_threshold_mbps": 18,
                    "route_threshold_mode": "bitrate",
                    "size_over_threshold": False,
                    "bitrate_over_threshold": False,
                }
            ],
            factory,
        )

        self.assertEqual(rows[0]["library_id"], "anime")
        self.assertEqual(rows[0]["library_designation"], "tv")
        self.assertEqual(rows[0]["library_source_root"], "C:/Anime")
        self.assertEqual(rows[0]["library_output_root"], "D:/AnimeProcessed")
        self.assertEqual(rows[0]["library_settings_overrides"], {"AudioMaxChannels": 6})
        self.assertEqual(rows[0]["library_effective_settings"]["VideoQuality"], 22)
        self.assertEqual(rows[0]["estimated_bitrate_mbps"], 12.5)
        self.assertEqual(rows[0]["route_size_threshold_gb"], 3.0)
        self.assertEqual(rows[0]["route_bitrate_threshold_mbps"], 18.0)
        self.assertEqual(rows[0]["route_threshold_mode"], "bitrate")
        self.assertIn("Library profile: Anime (anime)", rows[0]["route_evidence_lines"])
        self.assertIn("Library source root: C:/Anime", rows[0]["route_evidence_lines"])
        self.assertIn("Library output root: D:/AnimeProcessed", rows[0]["route_evidence_lines"])
        self.assertIn("Library override keys: AudioMaxChannels, SubKeepLanguages", rows[0]["route_evidence_lines"])
        self.assertIn("Route threshold mode: bitrate", rows[0]["route_evidence_lines"])
        self.assertIn("Size threshold: 3 GB; over threshold: no", rows[0]["route_evidence_lines"])
        self.assertIn("Bitrate estimate: 12.5 Mbps; threshold: 18 Mbps; over threshold: no", rows[0]["route_evidence_lines"])
        self.assertIn("Route trace: routing_profile_selected, size_evaluated", rows[0]["route_evidence_lines"])

    def test_queue_preview_library_effective_settings_stays_library_only(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Anime/Show/Season 01/Show - S01E01.mkv",
                    "root_path": "C:/Anime",
                    "library_id": "anime",
                    "library_name": "Anime",
                    "library_output_root": "D:/AnimeProcessed",
                    "library_settings_overrides": {"VideoPreset": "p5"},
                    "library_effective_settings": {"VideoPreset": "p5", "RoutingProfile": "plex"},
                    "runtime_effective_settings": {"VideoPreset": "p7", "FolderOverride": "not-library"},
                }
            ],
            factory,
        )

        self.assertEqual(rows[0]["library_effective_settings"], {"VideoPreset": "p5", "RoutingProfile": "plex"})
        self.assertNotIn("runtime_effective_settings", rows[0])

    def test_queue_preview_metadata_counts_backend_open_targets(self) -> None:
        rows = [queue_record_to_row(_record())]
        metadata = queue_preview_metadata(
            {
                "movie_count_total": 0,
                "tv_count_total": 1,
                "runnable_count": 1,
                "excluded_rows": [
                    {
                        "source_path": "C:/Source/TV/Show/Season 01/Already Done.mkv",
                        "root_path": "C:/Source/TV",
                        "reason_code": "completed_manifest",
                    }
                ],
            },
            rows,
        )

        self.assertEqual(
            metadata["available_open_target_counts"],
            {"source_file": 1, "source_folder": 1, "source_root": 1},
        )
        self.assertEqual(metadata["excluded_rows"][0]["available_open_targets"], ["source_file", "source_folder", "source_root"])

    def test_queue_source_scan_progress_is_backend_authored_indeterminate(self) -> None:
        payload = queue_source_scan_progress_payload(
            source="C:/State/Progress/queue_snapshot.json",
            row_count=2,
            metadata={
                "produced_at": "2026-05-17T10:00:00Z",
                "source_count_total": 3,
                "movie_count_total": 1,
                "tv_count_total": 2,
                "runnable_count": 2,
                "snapshot_file_freshness_status": "fresh",
                "produced_freshness_status": "fresh",
            },
        )

        self.assertEqual(payload["schema_version"], "desktop_queue_source_scan_progress.v1")
        self.assertEqual(payload["status"], "complete")
        self.assertFalse(payload["stale"])
        self.assertIn("indeterminate until backend scanner telemetry", "\n".join(payload["summary_lines"]))
        self.assertEqual(payload["progress_bars"][0]["id"], "queue_source_scan")
        self.assertEqual(payload["progress_bars"][0]["mode"], "indeterminate")
        self.assertEqual(payload["progress_bars"][0]["status"], "complete")

    def test_queue_preview_warning_constants_are_stable(self) -> None:
        self.assertEqual(queue_preview_warnings([]), [EMPTY_QUEUE_SNAPSHOT_WARNING])
        self.assertEqual(queue_preview_warnings([{"source_path": "C:/Source/file.mkv"}]), [])
        self.assertEqual(NO_QUEUE_SNAPSHOT_WARNING, "No queue snapshot is available yet.")
        self.assertEqual(QUEUE_PREVIEW_SERVICE_WARNING, "Queue preview service is not available.")
        self.assertEqual(INVALID_QUEUE_SNAPSHOT_WARNING, "Queue snapshot is missing or invalid.")


if __name__ == "__main__":
    unittest.main()
