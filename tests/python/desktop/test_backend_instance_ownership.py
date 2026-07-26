from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mediapipeline.desktop.backend_instance import (
    BACKEND_INSTANCE_METADATA_FILENAME,
    BackendInstanceAlreadyRunning,
    BackendInstanceGuard,
)


class _FakeLockRegistry:
    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self.held = False

    def create(self, _state_root: Path) -> "_FakeInstanceLock":
        return _FakeInstanceLock(self)

    def force_backend_crash(self) -> None:
        with self._mutex:
            self.held = False


class _FakeInstanceLock:
    def __init__(self, registry: _FakeLockRegistry) -> None:
        self.registry = registry
        self.owns = False

    def try_acquire(self) -> bool:
        with self.registry._mutex:
            if self.registry.held:
                return False
            self.registry.held = True
            self.owns = True
            return True

    def release(self) -> None:
        with self.registry._mutex:
            if self.owns:
                self.registry.held = False
                self.owns = False


class BackendInstanceOwnershipTests(unittest.TestCase):
    def _acquire(
        self,
        root: Path,
        registry: _FakeLockRegistry,
        *,
        owner_id: str,
        pid: int,
        now: float = 1000.0,
    ) -> BackendInstanceGuard:
        return BackendInstanceGuard.acquire(
            root,
            shell_surface="tauri",
            lock_factory=registry.create,
            owner_id_factory=lambda: owner_id,
            pid=pid,
            clock=lambda: now,
        )

    @staticmethod
    def _metadata(root: Path) -> dict[str, object]:
        return json.loads((root / BACKEND_INSTANCE_METADATA_FILENAME).read_text(encoding="utf-8"))

    def test_normal_close_holds_ownership_through_cleanup_then_allows_restart(self) -> None:
        with TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            registry = _FakeLockRegistry()
            guard = self._acquire(root, registry, owner_id="owner-a", pid=101)
            guard.mark_listening("http://127.0.0.1:41001")
            guard.mark_cleanup()

            cleanup_metadata = self._metadata(root)
            self.assertEqual(cleanup_metadata["phase"], "cleanup")
            self.assertTrue(registry.held)

            guard.release()
            restarted = self._acquire(root, registry, owner_id="owner-b", pid=102, now=1001.0)

            self.assertEqual(self._metadata(root)["owner_id"], "owner-b")
            restarted.release()
            self.assertFalse((root / BACKEND_INSTANCE_METADATA_FILENAME).exists())

    def test_shell_hard_crash_with_live_backend_blocks_second_backend(self) -> None:
        with TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            registry = _FakeLockRegistry()
            survivor = self._acquire(root, registry, owner_id="surviving-backend", pid=201)
            survivor.mark_listening("http://127.0.0.1:42001")

            with self.assertRaises(BackendInstanceAlreadyRunning) as raised:
                self._acquire(root, registry, owner_id="unsafe-second", pid=202)

            metadata = self._metadata(root)
            self.assertEqual(metadata["owner_id"], "surviving-backend")
            self.assertEqual(metadata["owner_pid"], 201)
            self.assertEqual(metadata["phase"], "listening")
            self.assertIn("surviving-backend", str(raised.exception))
            survivor.release()

    def test_backend_crash_leaves_stale_metadata_but_immediate_restart_recovers(self) -> None:
        with TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            registry = _FakeLockRegistry()
            crashed = self._acquire(root, registry, owner_id="crashed-backend", pid=301)
            crashed.mark_listening("http://127.0.0.1:43001")
            registry.force_backend_crash()

            restarted = self._acquire(root, registry, owner_id="restart-backend", pid=302, now=1002.0)
            metadata = self._metadata(root)

            self.assertEqual(metadata["owner_id"], "restart-backend")
            self.assertEqual(metadata["recovered_metadata_status"], "stale_valid")
            self.assertEqual(metadata["recovered_owner_id"], "crashed-backend")
            restarted.release()

    def test_malformed_stale_singleton_metadata_is_recovered_only_after_lock_acquisition(self) -> None:
        with TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            root.mkdir(parents=True, exist_ok=True)
            (root / BACKEND_INSTANCE_METADATA_FILENAME).write_text("{not-json", encoding="utf-8")
            registry = _FakeLockRegistry()

            guard = self._acquire(root, registry, owner_id="recovered-backend", pid=401)
            metadata = self._metadata(root)

            self.assertEqual(metadata["recovered_metadata_status"], "stale_malformed")
            self.assertEqual(metadata["owner_id"], "recovered-backend")
            guard.release()

    def test_second_shell_starting_during_cleanup_fails_closed_until_release(self) -> None:
        with TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            registry = _FakeLockRegistry()
            guard = self._acquire(root, registry, owner_id="cleanup-owner", pid=501)
            cleanup_started = threading.Barrier(2)
            allow_release = threading.Barrier(2)

            def cleanup() -> None:
                guard.mark_cleanup()
                cleanup_started.wait(timeout=2.0)
                allow_release.wait(timeout=2.0)
                guard.release()

            thread = threading.Thread(target=cleanup, name="fake-backend-cleanup")
            thread.start()
            cleanup_started.wait(timeout=2.0)
            try:
                with self.assertRaises(BackendInstanceAlreadyRunning):
                    self._acquire(root, registry, owner_id="racing-shell", pid=502)
                self.assertEqual(self._metadata(root)["phase"], "cleanup")
            finally:
                allow_release.wait(timeout=2.0)
                thread.join(timeout=2.0)

            self.assertFalse(thread.is_alive())
            restarted = self._acquire(root, registry, owner_id="post-cleanup", pid=503)
            restarted.release()


if __name__ == "__main__":
    unittest.main()
