from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processes.audit_policy import (
    AUDIT_LIBRARY_ROOT_ERROR,
    audit_missing_library_root_result,
    audit_start_active_work_result,
    audit_start_exception_result,
    audit_start_success_data,
    audit_start_success_message,
    audit_start_success_result,
    resolve_audit_library_root,
)


class AuditLaunchPolicyTests(unittest.TestCase):
    def test_library_root_prefers_request_then_config_outsource(self) -> None:
        self.assertEqual(
            resolve_audit_library_root({"library_root": "  C:/Library  "}, {"Outsource": "D:/Outsource"}),
            "C:/Library",
        )
        self.assertEqual(resolve_audit_library_root({}, {"Outsource": "  D:/Outsource  "}), "D:/Outsource")
        self.assertEqual(resolve_audit_library_root({"library_root": ""}, {"Outsource": ""}), "")
        self.assertEqual(AUDIT_LIBRARY_ROOT_ERROR, "Audit library root is unavailable.")

    def test_success_message_and_payload_are_stable(self) -> None:
        payload = audit_start_success_data(
            library_root="//server/library",
            include_sidecars=True,
            pid=24681,
            launch_prep_messages=["audit runtime ready"],
            launch_logs="stdout: audit.stdout.log",
        )

        self.assertEqual(audit_start_success_message(24681), "Started audit via PID 24681.")
        self.assertEqual(payload["library_root"], "//server/library")
        self.assertTrue(payload["include_sidecars"])
        self.assertEqual(payload["pid"], 24681)
        self.assertEqual(payload["launch_prep"], ["audit runtime ready"])
        self.assertEqual(payload["logs"], "stdout: audit.stdout.log")

    def test_command_result_helpers_preserve_audit_start_contract(self) -> None:
        missing = audit_missing_library_root_result()
        active = audit_start_active_work_result("Audit start blocked by active work.")
        failure = audit_start_exception_result(RuntimeError("audit spawn failed"))
        success = audit_start_success_result(
            library_root="//server/library",
            include_sidecars=True,
            pid=24681,
            launch_prep_messages=["audit runtime ready"],
            launch_logs="stdout: audit.stdout.log",
        )

        self.assertEqual(missing.command, "audit.start")
        self.assertFalse(missing.ok)
        self.assertEqual(missing.errors, [AUDIT_LIBRARY_ROOT_ERROR])
        self.assertEqual(active.refresh_hint, "snapshot")
        self.assertEqual(active.warnings, ["Audit start blocked by active work."])
        self.assertEqual(failure.errors, ["audit spawn failed"])
        self.assertTrue(success.ok)
        self.assertEqual(success.message, "Started audit via PID 24681.")
        self.assertEqual(success.data["library_root"], "//server/library")


if __name__ == "__main__":
    unittest.main()
