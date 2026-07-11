from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseError, LifecycleLeaseStore


class LifecycleLeaseTests(unittest.TestCase):
    def test_second_live_lease_is_rejected_and_terminal_release_reopens_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = LifecycleLeaseStore(root, pid_alive=lambda _pid: True)
            lease = store.acquire(scope="Pipeline start", command_id="command-1", resource_claims=["C:/Media/a.mkv"])
            with self.assertRaises(LifecycleLeaseError):
                store.acquire(scope="Pipeline start", command_id="command-2")
            lease.release()
            next_lease = store.acquire(scope="Pipeline start", command_id="command-2")
            next_lease.release()

    def test_ambiguous_stale_owner_blocks_reclaim(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            first = LifecycleLeaseStore(root, pid_alive=lambda _pid: True).acquire(scope="Pipeline start", command_id="command-1")
            self.assertFalse(first.released)
            uncertain = LifecycleLeaseStore(root, pid_alive=lambda _pid: None)
            with self.assertRaises(LifecycleLeaseError):
                uncertain.acquire(scope="Pipeline start", command_id="command-2")

    def test_conclusively_stale_lease_requires_recovery_before_new_launch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            LifecycleLeaseStore(root, pid_alive=lambda _pid: True).acquire(scope="Pipeline start", command_id="command-1")
            stale = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)

            with self.assertRaisesRegex(LifecycleLeaseError, "recovery reconciliation"):
                stale.acquire(scope="Pipeline start", command_id="command-2")

    def test_one_recovery_attempt_consumes_conclusively_stale_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)
            lease = store.acquire(scope="Pipeline start", command_id="command-1")
            lease.set_recovery_descriptor(route="/api/pipeline/start", request={"mode": "validate"})
            descriptor = store.begin_one_recovery_attempt()

            self.assertEqual(descriptor["route"], "/api/pipeline/start")
            self.assertEqual(descriptor["attempt_count"], 1)
            self.assertEqual(store.status()["status"], "recovering")
            with self.assertRaisesRegex(LifecycleLeaseError, "recovery is pending"):
                store.acquire(scope="Pipeline start", command_id="command-2")

            recovery_lease = store.acquire(scope="Pipeline start", command_id=descriptor["recovery_command_id"])
            recovery_lease.release(outcome="completed")

            self.assertEqual(store.status()["status"], "idle")

    def test_interrupted_recovery_remains_blocked_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)
            lease = store.acquire(scope="Pipeline start", command_id="command-1")
            lease.set_recovery_descriptor(route="/api/pipeline/start", request={"mode": "validate"})
            store.begin_one_recovery_attempt()

            restarted = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)

            self.assertEqual(restarted.status()["status"], "recovering")
            with self.assertRaisesRegex(LifecycleLeaseError, "recovery is pending"):
                restarted.acquire(scope="Pipeline start", command_id="command-2")
