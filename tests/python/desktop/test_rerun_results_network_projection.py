from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.processes import rerun_results_network_projection as network_projection  # noqa: E402
from mediapipeline.core.processes import rerun_results_queue_projection as queue_projection  # noqa: E402


class RerunResultsNetworkProjectionTests(unittest.TestCase):
    def test_child_exports_only_the_extracted_projection_helpers(self) -> None:
        self.assertEqual(
            network_projection.__all__,
            (
                "_network_row_key",
                "_network_reducer_result",
                "_network_worker_result",
                "_network_verified_output",
                "_network_output_probe",
                "_network_lifecycle_counts",
                "_network_nonnegative_int",
                "_network_batch_queue_rows",
            ),
        )

    def test_network_row_key_preserves_supplied_identity_and_has_stable_fallback(self) -> None:
        state_path = Path("C:/State/Rerun/Network/batch-1.json")

        self.assertEqual(
            network_projection._network_row_key("batch-1", " row-7 ", state_path),
            "network:batch-1:row-7",
        )
        expected_hash = hashlib.sha256(str(state_path).encode("utf-8", errors="replace")).hexdigest()[:20]
        self.assertEqual(
            network_projection._network_row_key("batch-1", "", state_path),
            f"network:batch-1:{expected_hash}",
        )

    def test_worker_and_reducer_results_are_defensive_deep_copies(self) -> None:
        source = {
            "worker_result": {"output_path": "Movie.mkv", "nested": {"attempt": 1}},
            "reducer_result": {"classification": "success", "output_artifact": {"path": "Movie.mkv"}},
        }

        worker = network_projection._network_worker_result(source)
        reducer = network_projection._network_reducer_result(source)
        worker["nested"]["attempt"] = 9
        reducer["output_artifact"]["path"] = "Changed.mkv"

        self.assertEqual(source["worker_result"]["nested"]["attempt"], 1)
        self.assertEqual(source["reducer_result"]["output_artifact"]["path"], "Movie.mkv")
        self.assertEqual(network_projection._network_worker_result({"worker_result": "invalid"}), {})
        self.assertEqual(network_projection._network_reducer_result({"reducer_result": None}), {})

    def test_verified_output_uses_row_then_reducer_then_worker_precedence(self) -> None:
        cases = (
            ({"verified_output_path": " verified.mkv ", "review_output_path": "review.mkv"}, {}, {}, "verified.mkv"),
            ({"review_output_path": " review.mkv "}, {}, {}, "review.mkv"),
            ({}, {"output_path": "worker.mkv"}, {"output_artifact": {"path": " reducer.mkv "}}, "reducer.mkv"),
            ({}, {"output_path": " worker.mkv "}, {"output_artifact": "invalid"}, "worker.mkv"),
        )
        for row, worker, reducer, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    network_projection._network_verified_output(row, worker, reducer),
                    expected,
                )

    def test_output_probe_reports_absent_missing_failed_and_file_states(self) -> None:
        with mock.patch.object(network_projection, "run_source_probe") as probe:
            self.assertEqual(
                network_projection._network_output_probe(""),
                {
                    "path": "",
                    "status": "not_supplied",
                    "exists": False,
                    "is_file": False,
                    "stale": False,
                    "error": "",
                },
            )
            probe.assert_not_called()

        with mock.patch.object(network_projection, "run_source_probe", side_effect=FileNotFoundError):
            missing = network_projection._network_output_probe("missing.mkv")
        self.assertEqual(missing["status"], "missing")
        self.assertFalse(missing["stale"])

        with mock.patch.object(network_projection, "run_source_probe", side_effect=TimeoutError("probe timed out")) as probe:
            failed = network_projection._network_output_probe(r"\\server\handoff\Movie.mkv")
        self.assertEqual(failed["status"], "access_failed")
        self.assertTrue(failed["stale"])
        self.assertEqual(failed["error"], "probe timed out")
        probe.assert_called_once_with("stat", Path(r"\\server\handoff\Movie.mkv"), timeout_seconds=2.0)

        with mock.patch.object(
            network_projection,
            "run_source_probe",
            return_value={"kind": "file", "size": -4},
        ):
            present = network_projection._network_output_probe("Movie.mkv")
        self.assertEqual(present["status"], "ok")
        self.assertTrue(present["exists"])
        self.assertTrue(present["is_file"])
        self.assertEqual(present["size_bytes"], 0)

    def test_lifecycle_counts_cover_every_operator_bucket(self) -> None:
        statuses = (
            "pending_claim",
            "retryable",
            "blocked",
            "retry_scheduled",
            "staged",
            "running",
            "complete",
            "skipped",
            "retry_exhausted",
            "failed",
            "review_required",
            "pending_publish",
        )
        rows = [{"status": status, "is_terminal": status in {"complete", "retry_exhausted"}} for status in statuses]

        counts = network_projection._network_lifecycle_counts(rows)

        self.assertEqual(
            counts,
            {
                "total": 12,
                "executable": 2,
                "blocked": 1,
                "waiting": 1,
                "retrying": 1,
                "staged": 1,
                "active": 1,
                "completed": 1,
                "failed": 2,
                "review": 1,
                "pending_publish": 1,
                "pending": 2,
                "retry_scheduled": 1,
                "retry_exhausted": 1,
                "review_required": 1,
                "skipped": 1,
                "terminal": 2,
            },
        )

    def test_batch_projection_preserves_retry_destination_evidence_and_input(self) -> None:
        state_path = Path("C:/State/Rerun/Network/batch-retry.json")
        data = {
            "batch_id": "batch-retry",
            "status": "retry_exhausted",
            "destination_mode": "pending_publish",
            "collision_policy": "suffix",
            "created_at_utc": "2026-07-13T20:00:00Z",
            "rows": [
                {
                    "row_key": "row-retry",
                    "row_index": "4",
                    "status": "retry_exhausted",
                    "source_path": "Source.mkv",
                    "verified_output_path": "Handoff.mkv",
                    "attempt_count": "3",
                    "retry_count": 3,
                    "retry_limit": "3",
                    "retry_after_seconds": "30",
                    "manual_recovery_available": True,
                    "operator_action_required": True,
                    "reason_code": "SOURCE_UNAVAILABLE",
                    "last_error": "Source remained unavailable.",
                    "what": "Automatic retry stopped.",
                    "why": "The retry limit was exhausted.",
                    "when": "2026-07-13T20:00:30Z",
                    "next_action": "Wait for operator retry.",
                    "timeline": [{"state": "retry_exhausted", "detail": {"attempt": 3}}],
                    "retry_history": [{"attempt": 2}],
                    "source_replay_evidence": {"identity": {"sha256": "abc"}},
                    "reducer_result": {
                        "classification": "failed_retryable",
                        "accepted": False,
                        "reason_code": "SOURCE_UNAVAILABLE",
                        "pending_destination_policy": True,
                        "output_artifact": {"path": "Reducer.mkv"},
                    },
                    "worker_result": {"output_path": "Worker.mkv", "nested": {"attempt": 3}},
                    "destination_policy": {"mode": "pending_publish"},
                    "destination_policy_result": {
                        "status": "pending_publish",
                        "action": "pending_publish",
                        "ok": True,
                        "terminal": True,
                        "pending_publish_manifest_path": "Movie.manifest.json",
                        "pending_publish_payload_path": "Movie.payload.json",
                        "published_path": "Library/Movie.mkv",
                    },
                }
            ],
        }
        original = copy.deepcopy(data)

        with mock.patch.object(
            network_projection,
            "run_source_probe",
            return_value={"kind": "file", "size": 42},
        ):
            rows = network_projection._network_batch_queue_rows(state_path, data)

        self.assertEqual(data, original)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["row_key"], "network:batch-retry:row-retry")
        self.assertEqual(row["row_index"], 4)
        self.assertEqual(row["queue_status"], "failed")
        self.assertEqual(row["attempt_count"], 3)
        self.assertEqual(row["verified_output_path"], "Handoff.mkv")
        self.assertTrue(row["can_open_output"])
        self.assertFalse(row["destination_state"]["pending_destination_policy"])
        self.assertTrue(row["destination_state"]["destination_policy_applied"])
        self.assertTrue(row["destination_state"]["destination_policy_terminal"])
        self.assertEqual(row["pending_publish_manifest_path"], "Movie.manifest.json")
        retry = row["available_actions"][0]
        self.assertEqual(retry["route"], "/api/rerun/network/retry")
        self.assertEqual(retry["request"]["row_key"], "row-retry")

        row["timeline"][0]["detail"]["attempt"] = 99
        row["network_worker_result"]["nested"]["attempt"] = 99
        row["network_destination_policy_result"]["status"] = "changed"
        self.assertEqual(data, original)

    def test_parent_preserves_public_exports_and_direct_symbols(self) -> None:
        self.assertEqual(
            queue_projection.__all__,
            (
                "rerun_manifest_queue_rows",
                "_remaining_pending_count",
                "_manifest_entries",
                "_network_row_key",
                "_network_reducer_result",
                "_network_worker_result",
                "_network_verified_output",
                "_network_batch_queue_rows",
                "_network_manifest_entries",
                "rerun_results_payload",
            ),
        )
        self.assertIs(queue_projection._network_row_key, network_projection._network_row_key)
        self.assertIs(queue_projection._network_output_probe, network_projection._network_output_probe)
        self.assertIs(queue_projection._network_batch_queue_rows, network_projection._network_batch_queue_rows)


if __name__ == "__main__":
    unittest.main()
