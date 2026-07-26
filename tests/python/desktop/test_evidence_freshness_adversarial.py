from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest import mock

from mediapipeline.core.status.run_monitor import (
    backend_activity_state_for_run,
    project_run_monitor,
    read_backend_correlated_run_monitor_projection,
)
from mediapipeline.core.status.run_monitor_storage import RunMonitorStore
from mediapipeline.core.status.progress import (
    datetime_is_stale,
    is_audit_progress_stale,
    is_progress_stale,
)
from tests.python.core.contract.test_run_monitor_contract import (
    RUN_ID,
    _item,
    _payload,
    _route,
    _worker,
)


NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
TIMESTAMP_FIELDS = frozenset(
    {
        "started_at",
        "updated_at",
        "completed_at",
        "ended_at",
        "requested_at",
        "recorded_at",
    }
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp_nonblank_timestamps(value: Any, timestamp: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in TIMESTAMP_FIELDS and isinstance(nested, str) and nested.strip():
                value[key] = timestamp
            else:
                _stamp_nonblank_timestamps(nested, timestamp)
    elif isinstance(value, list):
        for nested in value:
            _stamp_nonblank_timestamps(nested, timestamp)


def _active_payload_at(timestamp: datetime, *, run_id: str = RUN_ID) -> dict[str, Any]:
    item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
    payload = _payload([item], workers=[_worker(1, str(item["job_id"]))])
    payload["run"]["run_id"] = run_id
    payload["run"]["command_id"] = f"command-{run_id}"
    payload["items"][0]["job_id"] = f"{run_id}:item:1"
    payload["current_workers"][0]["run_id"] = run_id
    payload["current_workers"][0]["job_id"] = f"{run_id}:item:1"
    _stamp_nonblank_timestamps(payload, _iso(timestamp))
    return payload


def _terminal_payload(*, run_id: str, final_route: str, published_path: str) -> dict[str, Any]:
    item = _item(1, 1, lifecycle_state="completed")
    item["job_id"] = f"{run_id}:item:1"
    item["routes"]["final"] = _route(
        "available",
        route=final_route,
        reason="Verified terminal route.",
        source="completed_sidecar",
    )
    item["output"].update(
        {
            "state": "published",
            "published_path": published_path,
            "intended_final_path": published_path,
            "verification_state": "completed",
            "evidence": _route(
                "available",
                route=final_route,
                source="completed_sidecar",
            )["evidence"],
        }
    )
    payload = _payload([item], lifecycle_state="completed")
    payload["run"]["run_id"] = run_id
    payload["run"]["command_id"] = f"command-{run_id}"
    return payload


class EvidenceFreshnessAdversarialTests(unittest.TestCase):
    def test_legacy_status_timestamps_fail_closed_across_clock_boundaries(self) -> None:
        exact_stale_boundary = _iso(NOW - timedelta(seconds=45))
        beyond_stale_boundary = _iso(NOW - timedelta(seconds=45, microseconds=1))
        exact_future_tolerance = _iso(NOW + timedelta(seconds=5))
        beyond_future_tolerance = _iso(NOW + timedelta(seconds=5, microseconds=1))

        self.assertFalse(datetime_is_stale(exact_stale_boundary, 45, now=NOW, future_tolerance_seconds=5))
        self.assertTrue(datetime_is_stale(beyond_stale_boundary, 45, now=NOW, future_tolerance_seconds=5))
        self.assertFalse(datetime_is_stale(exact_future_tolerance, 45, now=NOW, future_tolerance_seconds=5))
        self.assertTrue(datetime_is_stale(beyond_future_tolerance, 45, now=NOW, future_tolerance_seconds=5))
        self.assertTrue(
            is_progress_stale(
                {"CurrentStage": "encode", "LastUpdate": beyond_future_tolerance},
                stale_after_seconds=45,
                now=NOW,
                future_tolerance_seconds=5,
            )
        )
        for raw in ("", "not-a-timestamp"):
            with self.subTest(audit_timestamp=raw):
                self.assertTrue(
                    is_audit_progress_stale(
                        {"status": "scanning", "completed": False, "failed": False, "last_update": raw},
                        stale_after_seconds=45,
                        now=NOW,
                        future_tolerance_seconds=5,
                    )
                )

    def test_late_old_run_write_cannot_reclaim_latest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            store = RunMonitorStore(Path(raw_root))
            old = _active_payload_at(NOW - timedelta(seconds=2), run_id="old-run")
            new = _active_payload_at(NOW - timedelta(seconds=1), run_id="new-run")
            store.write(old)
            store.write(new)

            late_old = copy.deepcopy(old)
            late_old["write_sequence"] = 2
            late_old["run"]["updated_at"] = _iso(NOW)
            store.write(late_old)

            latest = store.read()
            persisted_old = store.read("old-run")

        self.assertIsNotNone(latest)
        self.assertIsNotNone(persisted_old)
        assert latest is not None and persisted_old is not None
        self.assertEqual(latest.run.run_id, "new-run")
        self.assertEqual(persisted_old.write_sequence, 2)

    def test_terminal_run_rejects_higher_sequence_final_evidence_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            store = RunMonitorStore(Path(raw_root))
            terminal = _terminal_payload(
                run_id="terminal-run",
                final_route="remux",
                published_path=r"D:\Library\Movie.mkv",
            )
            store.write(terminal)

            contradictory = _terminal_payload(
                run_id="terminal-run",
                final_route="encode_hardware",
                published_path=r"D:\Different\Movie.mkv",
            )
            contradictory["write_sequence"] = 2

            with self.assertRaisesRegex(ValueError, "terminal.*immutable"):
                store.write(contradictory)

            persisted = store.read("terminal-run")

        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted.items[0].routes.final.route, "remux")
        self.assertEqual(persisted.items[0].output.published_path, r"D:\Library\Movie.mkv")

    def test_dead_pid_active_job_correlation_is_unavailable(self) -> None:
        checked_pids: list[int] = []
        rows = [
            {
                "source": "contract",
                "job_kind": "pipeline",
                "mode": "once",
                "status": "active",
                "pid": 3210,
                "metadata": {"run_id": RUN_ID},
            }
        ]

        def pid_alive(pid: int) -> bool:
            checked_pids.append(pid)
            return False

        with mock.patch(
            "mediapipeline.core.status.run_monitor.active_job_detail_rows",
            return_value=rows,
        ):
            state = backend_activity_state_for_run(
                Path("unused"),
                RUN_ID,
                pid_alive=pid_alive,
            )

        self.assertEqual(checked_pids, [3210])
        self.assertEqual(state, "unavailable")

    def test_stale_boundary_is_inclusive_and_one_microsecond_beyond_is_stale(self) -> None:
        exact = project_run_monitor(
            _active_payload_at(NOW - timedelta(seconds=45)),
            now=NOW,
            backend_activity_state="confirmed_active",
            stale_after_seconds=45,
        )
        beyond = project_run_monitor(
            _active_payload_at(NOW - timedelta(seconds=45, microseconds=1)),
            now=NOW,
            backend_activity_state="confirmed_active",
            stale_after_seconds=45,
        )

        self.assertEqual(exact["freshness"]["state"], "current")
        self.assertEqual(len(exact["current_workers"]), 1)
        self.assertEqual(beyond["freshness"]["state"], "stale")
        self.assertEqual(beyond["current_workers"], [])
        self.assertIsNone(beyond["items"][0]["current_stage"])

    def test_future_tolerance_is_inclusive_and_one_microsecond_beyond_is_unknown(self) -> None:
        exact = project_run_monitor(
            _active_payload_at(NOW + timedelta(seconds=5)),
            now=NOW,
            backend_activity_state="confirmed_active",
            future_tolerance_seconds=5,
        )
        beyond = project_run_monitor(
            _active_payload_at(NOW + timedelta(seconds=5, microseconds=1)),
            now=NOW,
            backend_activity_state="confirmed_active",
            future_tolerance_seconds=5,
        )

        self.assertEqual(exact["freshness"]["state"], "current")
        self.assertEqual(len(exact["current_workers"]), 1)
        self.assertEqual(beyond["freshness"]["state"], "unknown")
        self.assertEqual(beyond["freshness"]["reason_code"], "future_timestamp")
        self.assertEqual(beyond["current_workers"], [])
        self.assertIsNone(beyond["items"][0]["current_stage"])

    def test_old_monitor_cannot_bind_to_new_run_active_job(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            state_root = Path(raw_root)
            store = RunMonitorStore(state_root)
            store.write(_active_payload_at(NOW - timedelta(seconds=1), run_id="old-monitor-run"))
            rows = [
                {
                    "source": "contract",
                    "job_kind": "pipeline",
                    "mode": "once",
                    "status": "active",
                    "pid": 6543,
                    "metadata": {"run_id": "new-active-run"},
                }
            ]
            with mock.patch(
                "mediapipeline.core.status.run_monitor.active_job_detail_rows",
                return_value=rows,
            ):
                projection = read_backend_correlated_run_monitor_projection(
                    state_root,
                    Path("unused"),
                    now=NOW,
                )

        self.assertEqual(projection["run"]["run_id"], "old-monitor-run")
        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "backend_activity_unknown")
        self.assertEqual(projection["current_workers"], [])
        self.assertEqual(projection["items"][0]["lifecycle_state"], "unknown")
        self.assertIsNone(projection["items"][0]["current_stage"])
        self.assertEqual(projection["last_known"]["label"], "Last known — not current")


if __name__ == "__main__":
    unittest.main()
