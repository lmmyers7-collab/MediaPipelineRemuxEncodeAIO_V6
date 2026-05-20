from __future__ import annotations

import logging
from pathlib import Path
import tempfile
import unittest

from mediapipeline_desktop_app.service_process_launch_cleanup import (
    prepare_control_flags_for_launch,
    prepare_stale_progress_cleanup,
)


class ServiceProcessLaunchCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("test_service_process_launch_cleanup")

    def test_stale_progress_cleanup_skips_callbacks_when_not_stale(self) -> None:
        calls: list[str] = []

        messages = prepare_stale_progress_cleanup(
            progress_label="pipeline",
            is_stale=False,
            find_related_processes=lambda: calls.append("related") or [],
            clear_artifacts=lambda: calls.append("clear") or [],
            logger=self.logger,
        )

        self.assertEqual(messages, [])
        self.assertEqual(calls, [])

    def test_stale_progress_cleanup_blocks_when_related_process_exists(self) -> None:
        messages = prepare_stale_progress_cleanup(
            progress_label="audit",
            is_stale=True,
            find_related_processes=lambda: [type("Proc", (), {"pid": 5432})()],
            clear_artifacts=lambda: ["audit progress"],
            logger=self.logger,
        )

        self.assertEqual(len(messages), 1)
        self.assertIn("Stale audit progress was not cleared", messages[0])
        self.assertIn("PID(s) 5432", messages[0])

    def test_stale_progress_cleanup_reports_removed_artifacts(self) -> None:
        messages = prepare_stale_progress_cleanup(
            progress_label="pipeline",
            is_stale=True,
            find_related_processes=lambda: [],
            clear_artifacts=lambda: ["pipeline progress", "legacy pipeline progress"],
            logger=self.logger,
        )

        self.assertEqual(messages, ["Cleared stale pipeline progress before launch: pipeline progress, legacy pipeline progress."])

    def test_prepare_control_flags_removes_stop_and_stale_flags_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pause_flag = root / "pipeline_pause.flag"
            stop_flag = root / "pipeline_stop.flag"
            rescan_flag = root / "pipeline_rescan.flag"
            for flag_path in (pause_flag, stop_flag, rescan_flag):
                flag_path.write_text("flag", encoding="utf-8")
            removed: list[tuple[Path, str]] = []

            messages = prepare_control_flags_for_launch(
                (
                    ("Pause", pause_flag, False),
                    ("Stop", stop_flag, True),
                    ("Rescan", rescan_flag, False),
                ),
                stale_after_seconds=60,
                read_payload=lambda _path: {},
                age_seconds=lambda path, _payload: 120 if path == pause_flag else 10,
                remove_flag=lambda path, label: removed.append((path, label)) or path.unlink(),
                logger=self.logger,
            )

        self.assertEqual([label for _path, label in removed], ["Pause", "Stop"])
        self.assertTrue(any("Removed stale pause flag" in message for message in messages))
        self.assertTrue(any("Removed pre-existing stop flag" in message for message in messages))
        self.assertTrue(any("Existing rescan flag remains active" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
