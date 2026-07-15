from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
from mediapipeline.core.processes.recovery import LifecycleRecoveryCoordinator
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.application_facade_test_support import DummyWorkflowFacadeService, _resolved


class LifecycleRecoveryReplayTests(unittest.TestCase):
    def test_real_audit_recovery_replay_does_not_self_block_matching_recovery_lease(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root
            resolved.config_data = {
                "NetworkRole": "standalone",
                "Outsource": str(root / "Outsource"),
            }
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            store = LifecycleLeaseStore(root, pid_alive=lambda _pid: False)
            interrupted = store.acquire(scope="Audit start", command_id="audit-command-1")
            interrupted.set_recovery_descriptor(
                route="/api/audit/start",
                request={
                    "library_root": str(root / "Outsource"),
                    "include_sidecars": True,
                    "show_console": False,
                },
            )

            def replay(route: str, request: dict[str, object], original_command_id: str) -> dict[str, object]:
                self.assertEqual(route, "/api/audit/start")
                return facade.start_audit_process(
                    resolved,
                    {**request, "_command_id": f"{original_command_id}-recovery"},
                ).to_mapping()

            status = LifecycleRecoveryCoordinator(
                store_factory=lambda state_root: LifecycleLeaseStore(
                    state_root,
                    pid_alive=lambda _pid: False,
                )
            ).run(SimpleNamespace(state_root=root), resume=replay)

            self.assertEqual(status["status"], "complete")
            self.assertEqual(status["classification"], "recovered")
            self.assertEqual(service.started_audit["library_root"], str(root / "Outsource"))
            self.assertTrue(service.started_audit["include_sidecars"])

            service.started_audit_proc.complete()
            self.assertEqual(LifecycleLeaseStore(root, pid_alive=lambda _pid: False).status()["status"], "idle")


if __name__ == "__main__":
    unittest.main()
