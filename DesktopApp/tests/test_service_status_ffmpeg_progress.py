from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.status.ffmpeg_progress import FFMPEG_PROGRESS_SCHEMA_VERSION, ffmpeg_progress_payload


class FfmpegProgressPayloadTests(unittest.TestCase):
    def test_ffmpeg_progress_payload_parses_console_progress_line(self) -> None:
        payload = ffmpeg_progress_payload(
            {
                "Status": "Processing",
                "CurrentStage": "encode",
                "CurrentFileDisplay": "Movie.mkv",
                "LastUpdate": "2026-05-08T12:02:00-04:00",
            },
            "\n".join(
                [
                    "starting ffmpeg",
                    "2026-05-08 12:02:01 [INFO] frame=  240 fps=29.97 q=-1.0 size=1024kB time=00:00:08.01 bitrate=1450.5kbits/s speed=1.23x",
                ]
            ),
            worker_progress={
                "rows": [
                    {
                        "job_id": "launch-1",
                        "status_state": "running",
                        "stage": "encode",
                    }
                ]
            },
        )

        self.assertEqual(payload["schema_version"], FFMPEG_PROGRESS_SCHEMA_VERSION)
        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(payload["parsed_count"], 1)
        self.assertTrue(payload["read_only"])
        row = payload["rows"][0]
        self.assertEqual(row["job_id"], "launch-1")
        self.assertEqual(row["source"], "Movie.mkv")
        self.assertEqual(row["frame"], 240)
        self.assertEqual(row["fps"], 29.97)
        self.assertEqual(row["time"], "00:00:08.01")
        self.assertEqual(row["bitrate"], "1450.5kbits/s")
        self.assertEqual(row["speed"], "1.23x")
        self.assertEqual(row["speed_multiplier"], 1.23)
        self.assertEqual(row["updated_at"], "2026-05-08 12:02:01")
        self.assertEqual(row["parse_error"], "")
        self.assertIn("Mutation guardrail", "\n".join(payload["summary_lines"]))

    def test_ffmpeg_progress_payload_parses_progress_block(self) -> None:
        payload = ffmpeg_progress_payload(
            {
                "Status": "Processing",
                "CurrentStage": "remux",
                "CurrentFileDisplay": "Episode.mkv",
                "LastUpdate": "2026-05-08T12:02:00-04:00",
            },
            "\n".join(
                [
                    "frame=10",
                    "fps=0.00",
                    "out_time=00:00:01.667000",
                    "bitrate=N/A",
                    "speed=0.532x",
                    "progress=continue",
                ]
            ),
        )

        row = payload["rows"][0]
        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(row["frame"], 10)
        self.assertEqual(row["fps"], 0.0)
        self.assertEqual(row["time"], "00:00:01.667000")
        self.assertEqual(row["bitrate"], "N/A")
        self.assertEqual(row["speed"], "0.532x")
        self.assertEqual(row["updated_at"], "2026-05-08T12:02:00-04:00")

    def test_ffmpeg_progress_payload_parses_native_out_time_microseconds(self) -> None:
        payload = ffmpeg_progress_payload(
            {
                "Status": "Processing",
                "CurrentStage": "encode",
                "CurrentFileDisplay": "Movie.mkv",
                "LastUpdate": "2026-05-08T12:02:00-04:00",
            },
            "\n".join(
                [
                    "frame=240",
                    "fps=29.97",
                    "out_time_us=5000000",
                    "speed=1.23x",
                    "progress=continue",
                ]
            ),
        )

        row = payload["rows"][0]
        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(payload["parsed_count"], 1)
        self.assertEqual(payload["parse_error_count"], 0)
        self.assertEqual(row["time"], "00:00:05.000000")
        self.assertEqual(row["last_log_line"], "speed=1.23x")

    def test_ffmpeg_progress_payload_parses_native_out_time_ms_as_microseconds(self) -> None:
        payload = ffmpeg_progress_payload(
            {"Status": "Processing", "CurrentStage": "encode", "LastUpdate": "2026-05-08T12:02:00-04:00"},
            "out_time_ms=10000000\nprogress=continue\n",
        )

        self.assertEqual(payload["rows"][0]["time"], "00:00:10.000000")

    def test_ffmpeg_progress_payload_does_not_merge_older_block_fields_into_latest_partial_block(self) -> None:
        payload = ffmpeg_progress_payload(
            {
                "Status": "Processing",
                "CurrentStage": "encode",
                "CurrentFileDisplay": "Movie.mkv",
                "LastUpdate": "2026-05-08T12:05:00-04:00",
            },
            "\n".join(
                [
                    "2026-05-08 12:02:01 frame=240 fps=29.97 time=00:00:08.01 speed=1.23x",
                    "frame=260",
                ]
            ),
        )

        row = payload["rows"][0]
        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(row["frame"], 260)
        self.assertIsNone(row["fps"])
        self.assertEqual(row["time"], "")
        self.assertEqual(row["speed"], "")
        self.assertEqual(row["updated_at"], "2026-05-08T12:05:00-04:00")

    def test_ffmpeg_progress_payload_reports_parse_error_for_relevant_active_work(self) -> None:
        payload = ffmpeg_progress_payload(
            {
                "Status": "Processing",
                "CurrentStage": "encode",
                "CurrentFileDisplay": "Movie.mkv",
                "LastUpdate": "2026-05-08T12:02:00-04:00",
            },
            "starting ffmpeg for Movie.mkv\nwaiting for output\n",
        )

        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["parse_error_count"], 1)
        self.assertEqual(payload["rows"][0]["job_id"], "pipeline_progress")
        self.assertIn("No FFmpeg key/value progress fields", payload["rows"][0]["parse_error"])

    def test_ffmpeg_progress_payload_does_not_fake_rows_when_idle(self) -> None:
        payload = ffmpeg_progress_payload({"Status": "Idle", "CurrentStage": "idle"}, "")

        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["rows"], [])
        self.assertEqual(payload["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
