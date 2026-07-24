from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.registry import InFlightRegistry


def _job(**overrides):
    row = {
        "job_id": "job-1",
        "worker_id": "worker-1",
        "worker_name": "Worker 1",
        "source_path": r"C:\Media\movie.mkv",
        "claimed_at": "2026-05-08T00:00:00+00:00",
        "last_heartbeat": "2026-05-08T00:01:00+00:00",
        "progress_percent": 10,
        "encode_config": {},
        "claim_metadata": {},
    }
    row.update(overrides)
    return row


class NetworkRegistryRecoveryFailClosedTests(unittest.TestCase):
    def test_mixed_valid_and_malformed_jobs_fail_without_partial_activation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight.json"
            original = json.dumps({"jobs": [_job(), _job(job_id="bad", progress_percent="bad")]})
            path.write_text(original, encoding="utf-8")
            registry = InFlightRegistry()
            registry.claim(job_id="existing", worker_id="w0", worker_name="W0", source_path=r"C:\existing.mkv", encode_config={})

            with self.assertLogs("mediapipeline.desktop.network.registry", level="ERROR") as logs:
                loaded = registry.load(path)

            self.assertFalse(loaded)
            with registry._lock:
                self.assertEqual(sorted(registry._jobs), ["existing"])
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertIn("invalid active job at index 1", "\n".join(logs.output))

    def test_active_claim_shape_identity_and_metadata_errors_fail_closed(self) -> None:
        cases = {
            "non-object": ["not", "an", "object"],
            "missing-worker": _job(worker_id=""),
            "invalid-config": _job(encode_config=["bad"]),
            "invalid-rerun-metadata": _job(job_kind="csv_rerun_row", claim_metadata=["bad"]),
        }
        for label, row in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "inflight.json"
                original = json.dumps({"jobs": [row]})
                path.write_text(original, encoding="utf-8")
                registry = InFlightRegistry()
                self.assertFalse(registry.load(path))
                with registry._lock:
                    self.assertEqual(registry._jobs, {})
                self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_coordinator_startup_refuses_partially_recoverable_claims(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "coordinator_inflight.json"
            path.write_text(json.dumps({"jobs": [_job(worker_id="")]}), encoding="utf-8")
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = InFlightRegistry()
            dispatcher._inflight_state_path = lambda: path  # type: ignore[method-assign]

            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs:
                with self.assertRaisesRegex(RuntimeError, "refusing to start"):
                    dispatcher._restore_inflight_state()
            self.assertIn("confirming workers are idle", "\n".join(logs.output))
