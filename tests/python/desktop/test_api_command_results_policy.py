from __future__ import annotations

from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.api.command_results import (
    BACKEND_SHUTDOWN_BLOCKED_MESSAGE,
    BACKEND_SHUTDOWN_SCHEDULING_FAILED_MESSAGE,
    BACKEND_SHUTDOWN_UNAVAILABLE_MESSAGE,
    RESOLVED_PIPELINE_PATHS_UNAVAILABLE_MESSAGE,
    SETTINGS_RELOAD_MISSING_RESOLVED_MESSAGE,
    SETTINGS_RELOAD_UNAVAILABLE_MESSAGE,
    backend_shutdown_scheduling_failure_payload,
    backend_shutdown_success_payload,
    backend_shutdown_unavailable_payload,
    resolved_paths_unavailable_payload,
    settings_reload_exception_payload,
    settings_reload_missing_resolved_payload,
    settings_reload_success_payload,
    settings_reload_unavailable_payload,
    settings_save_reload_failure_payload,
    settings_save_reload_success_payload,
)


class LocalApiCommandResultsPolicyTests(unittest.TestCase):
    def test_resolved_paths_unavailable_payload_preserves_command_contract(self) -> None:
        payload = resolved_paths_unavailable_payload("pipeline.start", "snapshot")

        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "pipeline.start")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["message"], RESOLVED_PIPELINE_PATHS_UNAVAILABLE_MESSAGE)
        self.assertEqual(payload["errors"], [RESOLVED_PIPELINE_PATHS_UNAVAILABLE_MESSAGE])
        self.assertEqual(payload["refresh_hint"], "snapshot")

    def test_backend_shutdown_payloads_are_stable(self) -> None:
        unavailable = backend_shutdown_unavailable_payload()
        success = backend_shutdown_success_payload()

        self.assertEqual(unavailable["command"], "backend.shutdown")
        self.assertFalse(unavailable["ok"])
        self.assertEqual(unavailable["message"], BACKEND_SHUTDOWN_UNAVAILABLE_MESSAGE)
        self.assertEqual(unavailable["refresh_hint"], "none")
        self.assertTrue(success["ok"])
        self.assertEqual(success["refresh_hint"], "shutdown")
        self.assertEqual(success["severity"], "info")
        self.assertEqual(success["warnings"], [])
        self.assertEqual(success["errors"], [])
        self.assertEqual(success["data"], {"shutdown_scheduled": True})

    def test_backend_shutdown_scheduling_failure_retains_ownership_and_retry(self) -> None:
        payload = backend_shutdown_scheduling_failure_payload(
            {"safe_to_close": True, "active_work": False, "reason": "No active work."},
            scheduling_error=RuntimeError("timer unavailable"),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["message"], BACKEND_SHUTDOWN_SCHEDULING_FAILED_MESSAGE)
        self.assertEqual(payload["refresh_hint"], "close-readiness")
        self.assertFalse(payload["data"]["shutdown_scheduled"])
        self.assertTrue(payload["data"]["backend_ownership_retained"])
        self.assertTrue(payload["data"]["shutdown_retry_allowed"])
        self.assertTrue(payload["data"]["close_readiness"]["safe_to_close"])
        self.assertIn("timer unavailable", payload["errors"][0])

    def test_backend_shutdown_payload_blocks_when_close_readiness_is_not_safe(self) -> None:
        payload = backend_shutdown_success_payload(
            {
                "safe_to_close": False,
                "state": "processing",
                "active_work": True,
                "reason": "Shell close blocked because current pipeline state is processing.",
                "continuous_watcher": {"status": "armed", "pid": 24680},
            }
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["message"], BACKEND_SHUTDOWN_BLOCKED_MESSAGE)
        self.assertEqual(payload["refresh_hint"], "close-readiness")
        self.assertEqual(payload["data"]["safe_to_close"], False)
        self.assertEqual(payload["data"]["state"], "processing")
        self.assertEqual(payload["data"]["reason"], "Shell close blocked because current pipeline state is processing.")
        self.assertEqual(payload["data"]["continuous_watcher"]["status"], "armed")
        self.assertEqual(payload["data"]["continuous_watcher"]["pid"], 24680)
        self.assertIn("processing", payload["errors"][0])

    def test_backend_shutdown_success_payload_records_forced_cleanup_messages(self) -> None:
        payload = backend_shutdown_success_payload(
            {
                "safe_to_close": False,
                "state": "processing",
                "active_work": True,
                "reason": "Active pipeline process is running.",
            },
            force_active_work_shutdown=True,
            cleanup_messages=["Force-killed pipeline process tree (PID 1234)."],
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["severity"], "warning")
        self.assertEqual(payload["message"], "Backend shutdown requested with forced active-work cleanup.")
        self.assertEqual(payload["refresh_hint"], "shutdown")
        self.assertTrue(payload["data"]["forced_active_work_shutdown"])
        self.assertEqual(payload["data"]["cleanup_messages"], ["Force-killed pipeline process tree (PID 1234)."])
        self.assertEqual(payload["warnings"][0], "Active pipeline process is running.")
        self.assertIn("Force-killed pipeline", payload["warnings"][1])

    def test_settings_reload_payloads_preserve_contracts(self) -> None:
        unavailable = settings_reload_unavailable_payload()
        exception = settings_reload_exception_payload(RuntimeError("reload failed"))
        missing = settings_reload_missing_resolved_payload()
        resolved = SimpleNamespace(
            config_path=Path("C:/MediaPipeline/ops/pipeline/config/MediaPipeline_config.psd1"),
            config_data={"A": 1, "B": 2},
            local_base=Path("C:/MediaPipeline/Local"),
        )
        success = settings_reload_success_payload(resolved)

        self.assertEqual(unavailable["message"], SETTINGS_RELOAD_UNAVAILABLE_MESSAGE)
        self.assertEqual(exception["errors"], ["reload failed"])
        self.assertEqual(missing["errors"], [SETTINGS_RELOAD_MISSING_RESOLVED_MESSAGE])
        self.assertTrue(success["ok"])
        self.assertEqual(success["data"]["key_count"], 2)
        self.assertEqual(success["data"]["local_base"], str(Path("C:/MediaPipeline/Local")))

    def test_settings_save_reload_payload_helpers_preserve_existing_result_data(self) -> None:
        base_payload = {
            "schema_version": "desktop_command_result.v1",
            "command": "settings.save_patch",
            "ok": True,
            "severity": "info",
            "message": "Settings saved.",
            "data": {"writes_config": True},
        }
        reloaded = SimpleNamespace(config_data={"A": 1})

        success = settings_save_reload_success_payload(base_payload, reloaded)
        failure = settings_save_reload_failure_payload(base_payload, RuntimeError("reload failed"))

        self.assertTrue(success["ok"])
        self.assertTrue(success["data"]["writes_config"])
        self.assertTrue(success["data"]["reloaded"])
        self.assertEqual(success["data"]["reloaded_key_count"], 1)
        self.assertFalse(failure["ok"])
        self.assertEqual(failure["severity"], "warning")
        self.assertEqual(failure["errors"], ["reload failed"])
        self.assertTrue(base_payload["ok"], "helpers should not mutate the original payload")


if __name__ == "__main__":
    unittest.main()
