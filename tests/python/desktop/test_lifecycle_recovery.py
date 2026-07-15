from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
from mediapipeline.core.processes.recovery import LifecycleRecoveryCoordinator


class LifecycleRecoveryTests(unittest.TestCase):
    def test_recovery_resumes_only_safe_validate_boundary_once(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)
            lease = store.acquire(scope="Pipeline start", command_id="command-1")
            lease.set_recovery_descriptor(route="/api/pipeline/start", request={"mode": "validate"})
            resolved = SimpleNamespace(state_root=root)
            calls: list[tuple[str, dict, str]] = []
            status = LifecycleRecoveryCoordinator(store_factory=lambda state_root: LifecycleLeaseStore(state_root, pid_alive=lambda _pid: False)).run(
                resolved,
                resume=lambda route, request, command_id: calls.append((route, request, command_id)) or {"ok": True},
            )

            self.assertEqual(status["status"], "complete")
            self.assertEqual(status["classification"], "recovered")
            self.assertEqual(calls[0][0], "/api/pipeline/start")

    def test_recovery_retires_interrupted_media_work_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)
            lease = store.acquire(scope="Pipeline start", command_id="command-1")
            lease.set_recovery_descriptor(route="/api/pipeline/start", request={"mode": "once"})
            replay_calls: list[tuple[object, ...]] = []
            status = LifecycleRecoveryCoordinator(store_factory=lambda state_root: LifecycleLeaseStore(state_root, pid_alive=lambda _pid: False)).run(
                SimpleNamespace(state_root=root),
                resume=lambda *args: replay_calls.append(args) or {"ok": True},
            )

            self.assertEqual(status["status"], "complete")
            self.assertEqual(status["classification"], "interrupted")
            self.assertEqual(status["operator_action_required"], "")
            self.assertEqual(replay_calls, [])
            self.assertEqual(LifecycleLeaseStore(root, pid_alive=lambda _pid: False).status()["status"], "idle")
            terminal_paths = list((root / "Lifecycle").glob("*.terminal.json"))
            self.assertEqual(len(terminal_paths), 1)
            terminal = terminal_paths[0].read_text(encoding="utf-8")
            self.assertIn('"status": "interrupted"', terminal)
            self.assertIn('"recovery_replayed": false', terminal)

    def test_failed_safe_recovery_leaves_durable_blocking_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)
            lease = store.acquire(scope="Pipeline start", command_id="command-1")
            lease.set_recovery_descriptor(route="/api/pipeline/start", request={"mode": "validate"})

            status = LifecycleRecoveryCoordinator(
                store_factory=lambda state_root: LifecycleLeaseStore(state_root, pid_alive=lambda _pid: False)
            ).run(
                SimpleNamespace(state_root=root),
                resume=lambda *_args: {"ok": False, "message": "simulated recovery failure"},
            )

            self.assertEqual(status["status"], "blocked")
            self.assertEqual(LifecycleLeaseStore(root, pid_alive=lambda _pid: False).status()["status"], "indeterminate")
