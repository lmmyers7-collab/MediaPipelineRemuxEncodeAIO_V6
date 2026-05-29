from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from app.processes.control_flags import (
    control_flag_age_seconds,
    new_control_flag_payload,
    read_control_flag_payload,
    remove_control_flag,
    write_control_flag,
)


class ServiceProcessControlFlagTests(unittest.TestCase):
    def test_new_control_flag_payload_uses_contract_shape(self) -> None:
        payload = new_control_flag_payload("Stop")

        self.assertEqual(payload["schema_version"], "pipeline_control_flag.v1")
        self.assertEqual(payload["action"], "stop")
        self.assertEqual(payload["label"], "Stop")
        self.assertTrue(payload["request_id"])
        self.assertTrue(payload["created_at"])
        self.assertIsInstance(payload["app_pid"], int)

    def test_write_read_and_remove_control_flag_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            flag_path = Path(temp_dir) / "State" / "Pipeline" / "pipeline_stop.flag"

            payload = write_control_flag(flag_path, "Stop")
            read_back = read_control_flag_payload(flag_path)
            remove_control_flag(flag_path, "Stop")

        self.assertEqual(read_back, payload)
        self.assertFalse(flag_path.exists())

    def test_control_flag_age_prefers_created_at_when_present(self) -> None:
        created_at = (datetime.now().astimezone() - timedelta(seconds=30)).isoformat(timespec="seconds")
        with tempfile.TemporaryDirectory() as temp_dir:
            flag_path = Path(temp_dir) / "pipeline_pause.flag"
            flag_path.write_text("{}", encoding="utf-8")

            age = control_flag_age_seconds(
                flag_path,
                {"created_at": created_at},
                parse_datetime=lambda raw: datetime.fromisoformat(raw),
            )

        self.assertIsNotNone(age)
        self.assertGreaterEqual(float(age), 20.0)


if __name__ == "__main__":
    unittest.main()
