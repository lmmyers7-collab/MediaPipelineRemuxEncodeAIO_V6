from __future__ import annotations

from datetime import datetime, timedelta, UTC
import os
from pathlib import Path
import tempfile
import unittest

from mediapipeline.core.queue.freshness import (
    QUEUE_SNAPSHOT_FRESHNESS_HANDOFF_GRACE_SECONDS,
    build_queue_snapshot_freshness_anchor,
    evaluate_queue_snapshot_freshness,
)


BASE_TIME = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)
FRESHNESS_SECONDS = 60.0


class QueueSnapshotFreshnessTests(unittest.TestCase):
    def _evaluate(
        self,
        root: Path,
        *,
        age_seconds: float = 0.0,
        produced_at: str | None = None,
        file_age_seconds: float | None = None,
        wall_now: datetime = BASE_TIME,
        monotonic_now: float = 100.0,
        anchor: object | None = None,
        scan_id: str = "scan-stable",
        request_id: str = "request-stable",
        plan_fingerprint: str = "plan-stable",
    ):
        snapshot_path = root / "queue_snapshot.json"
        produced = produced_at or (BASE_TIME - timedelta(seconds=age_seconds)).isoformat()
        snapshot = {
            "produced_at": produced,
            "desktop_queue_preview_request_id": request_id,
            "queue_plan_fingerprint": plan_fingerprint,
        }
        snapshot_path.write_text("{}", encoding="utf-8")
        mtime_age = age_seconds if file_age_seconds is None else file_age_seconds
        timestamp = (BASE_TIME - timedelta(seconds=mtime_age)).timestamp()
        os.utime(snapshot_path, (timestamp, timestamp))
        status = {
            "scan_id": scan_id,
            "queue_preview_request_id": request_id,
        }
        return evaluate_queue_snapshot_freshness(
            snapshot_path,
            snapshot,
            status,
            freshness_seconds=FRESHNESS_SECONDS,
            wall_now=wall_now,
            monotonic_now=monotonic_now,
            anchor=anchor,
        )

    def test_wall_clock_boundaries_include_a_small_launch_handoff_grace(self) -> None:
        grace = QUEUE_SNAPSHOT_FRESHNESS_HANDOFF_GRACE_SECONDS
        cases = (
            (FRESHNESS_SECONDS - 0.001, True, "queue_snapshot_fresh"),
            (FRESHNESS_SECONDS, True, "queue_snapshot_fresh"),
            (FRESHNESS_SECONDS + 0.001, True, "queue_snapshot_fresh"),
            (FRESHNESS_SECONDS + grace, True, "queue_snapshot_fresh"),
            (FRESHNESS_SECONDS + grace + 0.001, False, "queue_snapshot_produced_at_stale"),
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            for age_seconds, expected_fresh, expected_reason in cases:
                with self.subTest(age_seconds=age_seconds):
                    result = self._evaluate(root, age_seconds=age_seconds)
                    self.assertEqual(result.fresh, expected_fresh)
                    self.assertEqual(result.reason_code, expected_reason)
                    self.assertEqual(result.clock_model, "restart_wall_utc")

    def test_future_missing_timezone_malformed_and_file_time_evidence_fail_closed(self) -> None:
        cases = (
            (
                "future",
                (BASE_TIME + timedelta(seconds=5.001)).isoformat(),
                0.0,
                "queue_snapshot_produced_at_in_future",
            ),
            ("timezone_missing", "2026-07-20T12:00:00", 0.0, "queue_snapshot_timezone_missing"),
            ("malformed", "not-a-time", 0.0, "queue_snapshot_timestamp_invalid"),
            (
                "stale_file",
                BASE_TIME.isoformat(),
                FRESHNESS_SECONDS + QUEUE_SNAPSHOT_FRESHNESS_HANDOFF_GRACE_SECONDS + 0.001,
                "queue_snapshot_file_mtime_stale",
            ),
            (
                "future_file",
                BASE_TIME.isoformat(),
                -5.001,
                "queue_snapshot_file_mtime_in_future",
            ),
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            for label, produced_at, file_age_seconds, expected_reason in cases:
                with self.subTest(label=label):
                    result = self._evaluate(
                        root,
                        produced_at=produced_at,
                        file_age_seconds=file_age_seconds,
                    )
                    self.assertFalse(result.fresh)
                    self.assertEqual(result.reason_code, expected_reason)
                    self.assertIn("Run Queue scan again", result.operator_action)

    def test_matching_process_anchor_uses_monotonic_elapsed_time_across_wall_clock_jumps(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            snapshot_path = root / "queue_snapshot.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            os.utime(snapshot_path, (BASE_TIME.timestamp(), BASE_TIME.timestamp()))
            snapshot = {
                "produced_at": BASE_TIME.isoformat(),
                "desktop_queue_preview_request_id": "request-stable",
                "queue_plan_fingerprint": "plan-stable",
            }
            status = {
                "scan_id": "scan-stable",
                "queue_preview_request_id": "request-stable",
            }
            anchor = build_queue_snapshot_freshness_anchor(
                snapshot_path,
                snapshot,
                status,
                monotonic_now=100.0,
            )

            for wall_now in (BASE_TIME - timedelta(days=1), BASE_TIME + timedelta(days=1)):
                with self.subTest(wall_now=wall_now):
                    result = evaluate_queue_snapshot_freshness(
                        snapshot_path,
                        snapshot,
                        status,
                        freshness_seconds=FRESHNESS_SECONDS,
                        wall_now=wall_now,
                        monotonic_now=160.001,
                        anchor=anchor,
                    )
                    self.assertTrue(result.fresh)
                    self.assertEqual(result.clock_model, "process_monotonic")

            expired = evaluate_queue_snapshot_freshness(
                snapshot_path,
                snapshot,
                status,
                freshness_seconds=FRESHNESS_SECONDS,
                wall_now=BASE_TIME,
                monotonic_now=161.001,
                anchor=anchor,
            )
            self.assertFalse(expired.fresh)
            self.assertEqual(expired.reason_code, "queue_snapshot_monotonic_age_stale")

    def test_restart_and_anchor_identity_mismatch_fall_back_to_utc_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            rolled_back = self._evaluate(root, wall_now=BASE_TIME - timedelta(days=1))
            advanced = self._evaluate(root, wall_now=BASE_TIME + timedelta(days=1))

            snapshot_path = root / "queue_snapshot.json"
            snapshot = {
                "produced_at": BASE_TIME.isoformat(),
                "desktop_queue_preview_request_id": "request-stable",
                "queue_plan_fingerprint": "plan-stable",
            }
            status = {
                "scan_id": "scan-stable",
                "queue_preview_request_id": "request-stable",
            }
            anchor = build_queue_snapshot_freshness_anchor(
                snapshot_path,
                snapshot,
                status,
                monotonic_now=100.0,
            )
            mismatched = self._evaluate(
                root,
                wall_now=BASE_TIME + timedelta(minutes=2),
                monotonic_now=101.0,
                anchor=anchor,
                request_id="replacement-request",
            )

        self.assertFalse(rolled_back.fresh)
        self.assertEqual(rolled_back.reason_code, "queue_snapshot_produced_at_in_future")
        self.assertFalse(advanced.fresh)
        self.assertEqual(advanced.reason_code, "queue_snapshot_produced_at_stale")
        self.assertFalse(mismatched.fresh)
        self.assertEqual(mismatched.clock_model, "restart_wall_utc")
        self.assertEqual(mismatched.reason_code, "queue_snapshot_produced_at_stale")


if __name__ == "__main__":
    unittest.main()
