from __future__ import annotations

from datetime import datetime, timedelta
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.test_application_facade import DummyFacadeService, DummyProc, _resolved


class ApplicationFacadeScheduleTests(unittest.TestCase):
    def test_schedule_workspace_reads_persisted_app_state_without_saving(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            monday = [False] * 48
            monday[18] = True
            monday[19] = True
            service.save_app_state(
                {
                    "schedule_enabled": True,
                    "schedule_grid": {
                        "Monday": monday,
                    },
                }
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            schedule = facade.get_schedule_workspace().to_mapping()

        self.assertEqual(schedule["schema_version"], "desktop_schedule_workspace.v1")
        self.assertTrue(schedule["read_only"])
        self.assertTrue(schedule["enabled"])
        monday_row = next(row for row in schedule["day_summaries"] if row["day"] == "Monday")
        self.assertEqual(monday_row["allowed_blocks"], 2)
        self.assertIn("9:00 AM", monday_row["windows_text"])
        self.assertEqual(schedule["grid"]["Monday"][18], True)
        self.assertEqual(schedule["continuous_watcher"]["status"], "idle")
        self.assertEqual(schedule["continuous_watcher"]["generation"], 0)
        self.assertIn("No backend schedule-stop watcher", schedule["continuous_watcher"]["message"])

    def test_schedule_workspace_reports_backend_schedule_stop_watcher_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            deadline = datetime.now() + timedelta(seconds=30)

            facade._schedule_stop_watcher.arm(  # type: ignore[attr-defined]
                service=service,
                resolved=resolved,
                proc=DummyProc(98765),
                deadline=deadline,
            )
            try:
                schedule = facade.get_schedule_workspace().to_mapping()
            finally:
                facade._schedule_stop_watcher.cancel("test cleanup")  # type: ignore[attr-defined]

        self.assertEqual(schedule["continuous_watcher"]["status"], "armed")
        self.assertEqual(schedule["continuous_watcher"]["pid"], 98765)
        self.assertEqual(schedule["continuous_watcher"]["deadline"], deadline.isoformat())
        self.assertFalse(schedule["continuous_watcher"]["stop_requested"])
        self.assertGreater(schedule["continuous_watcher"]["generation"], 0)
        self.assertIn("armed for PID 98765", schedule["continuous_watcher"]["message"])

    def test_schedule_preview_and_save_use_backend_app_state_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.save_app_state({"schedule_enabled": False, "machine_id": "node-1"})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            preview = facade.preview_schedule_patch(
                {
                    "enabled": True,
                    "day_windows": {
                        "Monday": "9:00 AM - 10:00 AM",
                        "Tuesday": "all day",
                    },
                }
            )
            no_confirm = facade.save_schedule_patch(
                {
                    "enabled": True,
                    "day_windows": {"Monday": "9:00 AM - 10:00 AM"},
                }
            )
            saved = facade.save_schedule_patch(
                {
                    "enabled": True,
                    "day_windows": {
                        "Monday": "9:00 AM - 10:00 AM",
                        "Tuesday": "all day",
                    },
                    "confirm_save": True,
                }
            )
            state = service.load_app_state()

        self.assertEqual(preview.command, "schedule.preview")
        self.assertTrue(preview.ok)
        self.assertFalse(preview.data["writes_app_state"])
        self.assertIn("Monday", preview.data["changed_days"])
        self.assertIn("Tuesday", preview.data["changed_days"])
        self.assertTrue(preview.data["changed_enabled"])
        self.assertTrue(any("Tuesday is allowed all day" in item for item in preview.warnings))
        self.assertEqual(no_confirm.command, "schedule.save")
        self.assertFalse(no_confirm.ok)
        self.assertIn("confirm_save", no_confirm.warnings[0])
        self.assertEqual(saved.command, "schedule.save")
        self.assertTrue(saved.ok)
        self.assertTrue(saved.data["writes_app_state"])
        self.assertTrue(state["schedule_enabled"])
        self.assertTrue(state["schedule_grid"]["Monday"][18])
        self.assertTrue(state["schedule_grid"]["Monday"][19])
        self.assertEqual(sum(1 for item in state["schedule_grid"]["Tuesday"] if item), 48)
        self.assertEqual(state["machine_id"], "node-1")

    def test_schedule_preview_rejects_invalid_time_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.save_app_state({"schedule_enabled": False, "machine_id": "node-1"})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            preview = facade.preview_schedule_patch(
                {
                    "enabled": True,
                    "day_windows": {"Monday": "9:15 AM - 10:00 AM"},
                }
            )
            saved = facade.save_schedule_patch(
                {
                    "enabled": True,
                    "day_windows": {"Monday": "9:15 AM - 10:00 AM"},
                    "confirm_save": True,
                }
            )
            state = service.load_app_state()

        self.assertEqual(preview.command, "schedule.preview")
        self.assertFalse(preview.ok)
        self.assertIn("30-minute blocks", "\n".join(preview.errors))
        self.assertEqual(saved.command, "schedule.save")
        self.assertFalse(saved.ok)
        self.assertIn("30-minute blocks", "\n".join(saved.errors))
        self.assertFalse(state["schedule_enabled"])
        self.assertEqual(state["machine_id"], "node-1")
