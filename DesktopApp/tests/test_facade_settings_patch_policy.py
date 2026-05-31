from __future__ import annotations

from types import SimpleNamespace
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings_patch_policy import (
    SETTINGS_DIFF_LINE_LIMIT,
    SETTINGS_PATCH_CHANGES_ERROR,
    SETTINGS_PATCH_REMOVE_KEYS_ERROR,
    settings_diff_truncated,
    settings_patch_changes_from_request,
    settings_patch_missing_changes_result,
    settings_patch_preview_message,
    settings_patch_preview_result,
    settings_patch_remove_keys_from_request,
    settings_patch_remove_keys_type_error_result,
    settings_patch_severity,
    settings_save_confirmation_required_result,
    settings_save_exception_result,
    settings_save_no_changes_result,
    settings_save_service_unavailable_result,
    settings_save_success_result,
    settings_save_validation_error_result,
    sorted_patch_keys,
    truncated_diff_lines,
)
from mediapipeline_desktop_app.models import ResolvedPaths


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "MediaPipeline_config.psd1",
        audit_script_path=root / "Pipeline" / "Audit-MediaLibrary.ps1",
        rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
        powershell_host="pwsh.exe",
    )


def _patch(diff_count: int = 2) -> dict[str, object]:
    return {
        "base_config": {"A": 1},
        "merged": {"A": 2, "B": 3},
        "errors": [],
        "warnings": [],
        "changed_keys": ["B", "A", "A"],
        "removed_keys": ["Old"],
        "diff_lines": [f"line-{index}" for index in range(diff_count)],
        "risk_summary": {"risk": "low"},
        "library_profile_state": [{"library_id": "movies"}],
    }


class SettingsPatchPolicyTests(unittest.TestCase):
    def test_patch_key_and_diff_helpers_are_stable(self) -> None:
        diff_lines = [str(index) for index in range(SETTINGS_DIFF_LINE_LIMIT + 2)]

        self.assertEqual(sorted_patch_keys(["b", "A", "b"]), ["A", "b"])
        self.assertEqual(len(truncated_diff_lines(diff_lines)), SETTINGS_DIFF_LINE_LIMIT)
        self.assertTrue(settings_diff_truncated(diff_lines))
        self.assertFalse(settings_diff_truncated(["only"]))
        self.assertEqual(settings_patch_severity(["bad"], []), "error")
        self.assertEqual(settings_patch_severity([], ["warn"]), "warning")
        self.assertEqual(settings_patch_severity([], []), "info")

    def test_candidate_request_shape_helpers_preserve_error_contract(self) -> None:
        changes, error = settings_patch_changes_from_request({"changes": {"A": 1}}, command="settings.preview_patch")
        self.assertEqual(changes, {"A": 1})
        self.assertIsNone(error)

        changes, error = settings_patch_changes_from_request({"changes": []}, command="settings.preview_patch")
        self.assertIsNone(changes)
        self.assertIsNotNone(error)
        self.assertEqual(error.command, "settings.preview_patch")
        self.assertEqual(error.errors, [SETTINGS_PATCH_CHANGES_ERROR])
        self.assertEqual(error.refresh_hint, "settings")
        self.assertEqual(
            settings_patch_missing_changes_result("settings.save_patch").message,
            "Settings patch requires a JSON object named changes.",
        )

        remove_keys, error = settings_patch_remove_keys_from_request(
            {"remove_keys": ["Old", "Legacy"]},
            command="settings.save_patch",
        )
        self.assertEqual(remove_keys, ["Old", "Legacy"])
        self.assertIsNone(error)
        self.assertEqual(settings_patch_remove_keys_from_request({}, command="settings.save_patch"), ([], None))
        self.assertEqual(settings_patch_remove_keys_from_request({"remove_keys": ""}, command="settings.save_patch"), ([], None))

        remove_keys, error = settings_patch_remove_keys_from_request(
            {"remove_keys": "Old"},
            command="settings.save_patch",
        )
        self.assertIsNone(remove_keys)
        self.assertIsNotNone(error)
        self.assertEqual(error.errors, [SETTINGS_PATCH_REMOVE_KEYS_ERROR])
        self.assertEqual(
            settings_patch_remove_keys_type_error_result("settings.preview_patch").message,
            "remove_keys must be a JSON array when supplied.",
        )

    def test_preview_message_and_result_shape_counts_and_truncation(self) -> None:
        root = Path("C:/MediaPipeline")
        patch = _patch(diff_count=SETTINGS_DIFF_LINE_LIMIT + 1)

        result = settings_patch_preview_result(_resolved(root), patch)

        self.assertTrue(result.ok)
        self.assertEqual(result.message, f"Settings patch preview produced {SETTINGS_DIFF_LINE_LIMIT + 1} redacted diff line(s).")
        self.assertEqual(result.data["changed_keys"], ["A", "B"])
        self.assertEqual(result.data["removed_keys"], ["Old"])
        self.assertEqual(result.data["base_key_count"], 1)
        self.assertEqual(result.data["preview_key_count"], 2)
        self.assertEqual(len(result.data["redacted_diff_lines"]), SETTINGS_DIFF_LINE_LIMIT)
        self.assertTrue(result.data["diff_truncated"])
        self.assertEqual(result.data["library_profile_state"], [{"library_id": "movies"}])
        self.assertFalse(result.data["writes_config"])

    def test_preview_message_handles_error_and_no_change_states(self) -> None:
        self.assertEqual(settings_patch_preview_message(["bad"], [], [], []), "Settings patch preview failed with 1 error(s).")
        self.assertEqual(settings_patch_preview_message([], [], [], []), "Settings patch preview has no changes.")

    def test_save_error_results_are_stable(self) -> None:
        self.assertEqual(settings_save_confirmation_required_result().warnings, ["confirm_save must be true."])
        self.assertEqual(settings_save_validation_error_result(["bad"], ["warn"]).message, "Settings patch save failed validation with 1 error(s).")
        self.assertEqual(settings_save_no_changes_result([]).warnings, ["No settings changes were proposed."])
        self.assertEqual(
            settings_save_service_unavailable_result().errors,
            ["serialize_psd1_document and save_config_document are required."],
        )
        self.assertIn("offline", settings_save_exception_result(RuntimeError("offline"), ["warn"]).message)

    def test_save_success_result_shapes_write_payload(self) -> None:
        root = Path("C:/MediaPipeline")
        save_result = SimpleNamespace(
            output_path=root / "Pipeline" / "MediaPipeline_config.psd1",
            backup_path=root / "Pipeline" / "MediaPipeline_config.psd1.bak",
        )

        result = settings_save_success_result(save_result, _patch(), ["same disk warning"])

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Settings saved to MediaPipeline_config.psd1.")
        self.assertEqual(result.warnings, ["same disk warning"])
        self.assertEqual(result.data["changed_keys"], ["A", "B"])
        self.assertEqual(result.data["removed_keys"], ["Old"])
        self.assertEqual(result.data["key_count"], 2)
        self.assertEqual(result.data["library_profile_state"], [{"library_id": "movies"}])
        self.assertTrue(result.data["writes_config"])


if __name__ == "__main__":
    unittest.main()
