from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.command_journal_policy import (
    COMMAND_HISTORY_SCHEMA_VERSION,
    COMMAND_RESULT_SCHEMA_VERSION,
    bounded_command_evidence,
    command_history_mapping,
    is_command_result_payload,
    scalar_text,
    sanitize_journal_entry,
    string_dict,
    string_list,
    summarize_command_payload,
    valid_journal_entries,
)


class LocalApiCommandJournalPolicyTests(unittest.TestCase):
    def test_payload_detection_preserves_command_result_schema_contract(self) -> None:
        self.assertTrue(is_command_result_payload({"schema_version": COMMAND_RESULT_SCHEMA_VERSION}))
        self.assertFalse(is_command_result_payload({"schema_version": "desktop_snapshot.v1"}))
        self.assertFalse(is_command_result_payload({}))

    def test_scalar_text_normalizes_line_endings_and_truncates(self) -> None:
        self.assertEqual(scalar_text("one\r\ntwo\rthree", limit=40), "one\ntwo\nthree")
        self.assertEqual(scalar_text("abcdef", limit=4), "abc...")
        self.assertEqual(scalar_text(None, limit=4), "")

    def test_string_list_limits_and_scalarizes_values(self) -> None:
        values = ["one", 2, "three", "four"]

        self.assertEqual(string_list(values, limit=3), ["one", "2", "three"])
        self.assertEqual(string_list("not-a-list", limit=3), [])

    def test_string_dict_limits_and_scalarizes_keys_and_values(self) -> None:
        values = {
            "stdout": "C:/Temp/stdout.log",
            42: "answer",
            "ignored": "after limit",
        }

        self.assertEqual(
            string_dict(values, limit=2),
            {"stdout": "C:/Temp/stdout.log", "42": "answer"},
        )
        self.assertEqual(string_dict(["not", "dict"], limit=2), {})

    def test_summarize_command_payload_preserves_operator_feedback_fields(self) -> None:
        summary = summarize_command_payload(
            {
                "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
                "command": "pipeline.start",
                "ok": True,
                "severity": "info",
                "message": "started",
                "job_id": "job-1",
                "refresh_hint": "snapshot",
                "warnings": ["warn"],
                "errors": ["err"],
                "log_paths": {"stdout": "C:/Run/stdout.log"},
                "data": {"pid": 1234, "secret_token": "do-not-store"},
            },
            request={"mode": "once", "authorization": "Bearer secret"},
        )

        self.assertIn("at", summary)
        self.assertEqual(summary["command"], "pipeline.start")
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["severity"], "info")
        self.assertEqual(summary["message"], "started")
        self.assertEqual(summary["job_id"], "job-1")
        self.assertEqual(summary["refresh_hint"], "snapshot")
        self.assertEqual(summary["warnings"], ["warn"])
        self.assertEqual(summary["errors"], ["err"])
        self.assertEqual(summary["log_paths"], {"stdout": "C:/Run/stdout.log"})
        self.assertEqual(summary["data"]["pid"], 1234)
        self.assertEqual(summary["data"]["secret_token"], "<redacted>")
        self.assertEqual(summary["request"]["mode"], "once")
        self.assertEqual(summary["request"]["authorization"], "<redacted>")

    def test_summarize_command_payload_applies_defaults(self) -> None:
        summary = summarize_command_payload({"schema_version": COMMAND_RESULT_SCHEMA_VERSION})

        self.assertEqual(summary["command"], "unknown")
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["severity"], "info")
        self.assertEqual(summary["warnings"], [])
        self.assertEqual(summary["errors"], [])
        self.assertEqual(summary["log_paths"], {})

    def test_bounded_command_evidence_limits_nested_data_and_nonfinite_numbers(self) -> None:
        summary = bounded_command_evidence(
            {
                "rows": [{"path": f"C:/Media/{index}.mkv"} for index in range(25)],
                "nested": {"password": "secret", "score": float("nan")},
            }
        )

        self.assertEqual(len(summary["rows"]), 20)
        self.assertEqual(summary["nested"]["password"], "<redacted>")
        self.assertEqual(summary["nested"]["score"], "nan")

    def test_history_mapping_bounds_entries_and_copies_rows(self) -> None:
        entries = [{"command": "one"}, {"command": "two"}, {"command": "three"}]
        payload = command_history_mapping(entries, limit=2, max_entries=5)

        self.assertEqual(payload["schema_version"], COMMAND_HISTORY_SCHEMA_VERSION)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["entries"], [{"command": "one"}, {"command": "two"}])
        payload["entries"][0]["command"] = "changed"
        self.assertEqual(entries[0]["command"], "one")

    def test_valid_journal_entries_filters_non_dict_rows_and_bounds_count(self) -> None:
        self.assertEqual(valid_journal_entries("not-a-list", max_entries=3), [])
        rows = valid_journal_entries(
            [
                {"command": "one", "message": "x" * 2500, "warnings": ["w"]},
                "bad",
                {"command": "two"},
                {"command": "three"},
            ],
            max_entries=2,
        )

        self.assertEqual([row["command"] for row in rows], ["one", "two"])
        self.assertEqual(rows[0]["message"], "x" * 1999 + "...")
        self.assertEqual(rows[0]["warnings"], ["w"])
        self.assertNotIn("bad", rows)

    def test_sanitize_journal_entry_bounds_loaded_history_shape(self) -> None:
        row = sanitize_journal_entry(
            {
                "at": "2026-05-08T00:00:00Z",
                "command": "x" * 200,
                "ok": 1,
                "severity": "",
                "message": "ok",
                "job_id": "job-1",
                "refresh_hint": "snapshot",
                "warnings": ["w"] * 25,
                "errors": ["e"],
                "log_paths": {f"k{i}": f"v{i}" for i in range(20)},
                "data": {"large": "kept", "token": "hidden"},
                "request": {"changes": {"RoutingProfile": "plex_direct_play"}},
            }
        )

        self.assertEqual(row["at"], "2026-05-08T00:00:00Z")
        self.assertTrue(row["command"].endswith("..."))
        self.assertTrue(row["ok"])
        self.assertEqual(row["severity"], "info")
        self.assertEqual(len(row["warnings"]), 20)
        self.assertEqual(len(row["log_paths"]), 12)
        self.assertEqual(row["data"], {"large": "kept", "token": "<redacted>"})
        self.assertEqual(row["request"]["changes"]["RoutingProfile"], "plex_direct_play")


if __name__ == "__main__":
    unittest.main()
