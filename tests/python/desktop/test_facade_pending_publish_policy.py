from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.publish.pending_policy import (
    PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
    PENDING_PUBLISH_OPEN_TARGETS,
    PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
    int_value,
    normalize_pending_publish_open_target,
    normalize_pending_publish_row_key,
    pending_publish_open_path,
    pending_publish_open_scan_exception_result,
    pending_publish_open_scan_service_unavailable_result,
    pending_publish_open_success_result,
    pending_publish_invalid_result,
    pending_publish_error_warning,
    pending_publish_preview_fields,
    pending_publish_preview_result,
    pending_publish_recovery_plan_action,
    pending_publish_recovery_plan_result,
    pending_publish_row_key,
    pending_publish_row_trust_fields,
    pending_publish_rows,
    pending_publish_scan_exception_fields,
    pending_publish_scan_exception_result,
    pending_publish_service_unavailable_result,
)
from mediapipeline.core.publish.pending_policy_parts.trust_fields import build_pending_publish_row_trust_fields


class PendingPublishFacadePolicyTests(unittest.TestCase):
    def test_int_value_matches_facade_coercion(self) -> None:
        self.assertEqual(int_value(None), 0)
        self.assertEqual(int_value(""), 0)
        self.assertEqual(int_value("bad"), 0)
        self.assertEqual(int_value("3.9"), 3)
        self.assertEqual(int_value(4.2), 4)

    def test_rows_filter_non_dicts_and_json_safe_values(self) -> None:
        rows = pending_publish_rows(
            [
                {"state": "parked", "path": Path("C:/Pending/Movie.mkv"), "nested": {"path": Path("C:/Sidecar.srt")}},
                "not-a-row",
                {"state": "orphan_payload", "size": 123},
            ]
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["path"], str(Path("C:/Pending/Movie.mkv")))
        self.assertEqual(rows[0]["nested"]["path"], str(Path("C:/Sidecar.srt")))
        self.assertIn("row_key", rows[0])
        self.assertEqual(rows[1]["state"], "orphan_payload")

    def test_pending_publish_trust_fields_fixture_parity_for_ready_row(self) -> None:
        row = {
            "manifest_path": r"C:\Pending\Ready.mkv.manifest.json",
            "local_file": r"C:\Pending\Ready.mkv",
            "server_out": r"\\nas\Movies\Ready.mkv",
            "state": "parked",
            "local_exists": True,
            "missing_sidecar_count": 0,
        }
        diagnostics = {
            "diagnostic_status": "ready",
            "diagnostic_severity": "ok",
            "drain_recommendation": "ready_to_drain",
            "recovery_class": "ready_to_validate",
        }
        expected = {
            "operator_trust_state": "ready-looking",
            "primary_concern": "row has no blocker in the loaded pending publish scan",
            "safe_next_action": "Use only backend-owned Publish Parked Outputs after page-level validation still agrees.",
            "unsafe_if_ignored": "Draining review or blocker rows can lose parked output context, overwrite the wrong destination, or strand payload/sidecar evidence.",
            "proof_summary": [
                "diagnostic=ready / ok",
                "drain=ready_to_drain",
                "recovery=ready_to_validate",
                r"payload=C:\Pending\Ready.mkv",
                r"manifest=C:\Pending\Ready.mkv.manifest.json",
                r"destination=\\nas\Movies\Ready.mkv",
            ],
            "recommended_diagnostics_targets": ["pending_publish", "run_logs", "last_stderr_log"],
        }

        self.assertEqual(
            build_pending_publish_row_trust_fields(row, diagnostics, missing_sidecars=0, ready_to_drain=True),
            expected,
        )
        self.assertEqual(pending_publish_row_trust_fields(row, diagnostics), expected)

    def test_pending_publish_trust_fields_fixture_parity_for_do_not_drain_row(self) -> None:
        row = {
            "manifest_path": r"C:\Pending\Broken.mkv.manifest.json",
            "local_file": "",
            "server_out": r"\\nas\Movies\Broken.mkv",
            "state": "unreadable",
            "local_exists": False,
            "missing_sidecar_count": "2",
            "error": "bad json",
        }
        diagnostics = {
            "diagnostic_status": "unreadable_manifest",
            "diagnostic_severity": "error",
            "drain_recommendation": "do_not_drain",
            "recovery_class": "manifest_repair",
        }
        expected = {
            "operator_trust_state": "do-not-drain",
            "primary_concern": "backend marked do_not_drain; diagnostic severity is error; local payload missing; 2 missing sidecars; manifest unreadable or invalid; row error: bad json",
            "safe_next_action": "Do not drain; inspect pending manifest/payload/sidecar evidence, Last Stderr, and Run Logs first.",
            "unsafe_if_ignored": "Draining review or blocker rows can lose parked output context, overwrite the wrong destination, or strand payload/sidecar evidence.",
            "proof_summary": [
                "diagnostic=unreadable_manifest / error",
                "drain=do_not_drain",
                "recovery=manifest_repair",
                "payload=not reported",
                r"manifest=C:\Pending\Broken.mkv.manifest.json",
                r"destination=\\nas\Movies\Broken.mkv",
            ],
            "recommended_diagnostics_targets": ["pending_publish", "run_logs", "last_stderr_log", "state"],
        }

        self.assertEqual(
            build_pending_publish_row_trust_fields(row, diagnostics, missing_sidecars=2, ready_to_drain=False),
            expected,
        )
        self.assertEqual(pending_publish_row_trust_fields(row, diagnostics), expected)

    def test_preview_fields_normalize_raw_scan_result(self) -> None:
        raw = {
            "pending_root": Path("C:/Pending"),
            "exists": "yes",
            "rows": [{"state": "parked"}, "bad"],
            "health_rows": [{"state": "missing_local"}],
            "count": "2.0",
            "payload_count": 3.2,
            "total_bytes": "4096",
            "total_size_text": "",
            "missing_local_count": "1",
            "health_count": "1",
            "file_inventory": {
                "rows": [{"path": Path("C:/Pending/Movie.mkv"), "role": "orphan_payload"}],
                "total_count": 1,
            },
            "error": " partial scan ",
        }

        fields = pending_publish_preview_fields(raw)

        self.assertEqual(fields["pending_root"], str(Path("C:/Pending")))
        self.assertTrue(fields["exists"])
        self.assertEqual(fields["rows"][0]["state"], "parked")
        self.assertIn("row_key", fields["rows"][0])
        self.assertEqual(fields["health_rows"][0]["state"], "missing_local")
        self.assertIn("row_key", fields["health_rows"][0])
        self.assertEqual(fields["count"], 2)
        self.assertEqual(fields["payload_count"], 3)
        self.assertEqual(fields["total_bytes"], 4096)
        self.assertEqual(fields["total_size_text"], "0 B")
        self.assertEqual(fields["missing_local_count"], 1)
        self.assertEqual(fields["health_count"], 1)
        self.assertEqual(fields["file_inventory"]["schema_version"], "desktop_pending_publish_file_inventory.v1")
        self.assertEqual(fields["file_inventory"]["rows"][0]["path"], str(Path("C:/Pending/Movie.mkv")))
        self.assertEqual(fields["file_inventory"]["total_count"], 1)
        self.assertEqual(fields["available_open_target_counts"], {})
        self.assertEqual(fields["warnings"], ["partial scan"])
        self.assertEqual(fields["error"], "partial scan")

    def test_empty_error_and_exception_fields_are_stable(self) -> None:
        self.assertEqual(pending_publish_error_warning(""), [])
        self.assertEqual(pending_publish_error_warning("network share unavailable"), ["network share unavailable"])

        exc = RuntimeError("directory read failed")
        fields = pending_publish_scan_exception_fields(Path("C:/Pending"), True, exc)

        self.assertEqual(fields["pending_root"], str(Path("C:/Pending")))
        self.assertTrue(fields["exists"])
        self.assertEqual(fields["error"], "directory read failed")
        self.assertEqual(fields["warnings"], ["Pending publish scan failed: directory read failed"])

    def test_pending_publish_dto_helpers_preserve_warning_contracts(self) -> None:
        unavailable = pending_publish_service_unavailable_result()
        invalid = pending_publish_invalid_result()
        exception = pending_publish_scan_exception_result(Path("C:/Pending"), True, RuntimeError("directory read failed"))

        self.assertEqual(unavailable.warnings, [PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE])
        self.assertEqual(invalid.warnings, [PENDING_PUBLISH_INVALID_RESULT_MESSAGE])
        self.assertEqual(exception.pending_root, str(Path("C:/Pending")))
        self.assertEqual(exception.error, "directory read failed")
        self.assertEqual(exception.warnings, ["Pending publish scan failed: directory read failed"])

    def test_pending_publish_preview_result_wraps_fields_in_dto(self) -> None:
        preview = pending_publish_preview_result(
            {
                "pending_root": Path("C:/Pending"),
                "exists": True,
                "rows": [{"state": "parked"}],
                "count": "1",
                "total_bytes": "1024",
                "total_size_text": "1.0 KB",
            }
        )

        self.assertEqual(preview.pending_root, str(Path("C:/Pending")))
        self.assertTrue(preview.exists)
        self.assertEqual(preview.count, 1)
        self.assertEqual(preview.rows[0]["state"], "parked")
        self.assertIn("row_key", preview.rows[0])
        self.assertEqual(preview.available_open_target_counts, {})

    def test_pending_publish_open_policy_uses_row_keyed_backend_paths(self) -> None:
        row = {
            "manifest_path": r"C:\Pending\Movie.mkv.manifest.json",
            "local_file": r"C:\Pending\Movie.mkv",
            "server_out": r"\\nas\Movies\Movie.mkv",
            "source_path": r"D:\Source\Movie.mkv",
            "state": "parked",
        }
        row_key = pending_publish_row_key(row)
        rows = pending_publish_rows([row])

        self.assertIn("local_file", PENDING_PUBLISH_OPEN_TARGETS)
        self.assertEqual(
            rows[0]["available_open_targets"],
            ["local_file", "manifest", "destination_folder", "source_folder"],
        )
        self.assertEqual(normalize_pending_publish_open_target(" Local_File "), "local_file")
        self.assertEqual(normalize_pending_publish_row_key(f" {row_key.upper()} "), row_key)
        self.assertEqual(pending_publish_open_path(row, "local_file"), Path(row["local_file"]))
        self.assertEqual(pending_publish_open_path(row, "manifest"), Path(row["manifest_path"]))
        self.assertEqual(pending_publish_open_path(row, "destination_folder"), Path(row["server_out"]).parent)
        self.assertEqual(pending_publish_open_path(row, "source_folder"), Path(row["source_path"]).parent)

        opened = pending_publish_open_success_result("local_file", row_key, Path(row["local_file"]))
        self.assertTrue(opened.ok)
        self.assertEqual(opened.command, "pending_publish.open")
        self.assertEqual(opened.data["row_key"], row_key)

        scan_failed = pending_publish_open_scan_exception_result(row_key, RuntimeError("scan locked"))
        self.assertFalse(scan_failed.ok)
        self.assertEqual(scan_failed.severity, "error")
        self.assertIn("scan locked", scan_failed.message)
        self.assertEqual(scan_failed.data["row_key"], row_key)

        scan_unavailable = pending_publish_open_scan_service_unavailable_result(row_key)
        self.assertFalse(scan_unavailable.ok)
        self.assertEqual(scan_unavailable.severity, "error")
        self.assertEqual(scan_unavailable.message, PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE)
        self.assertEqual(scan_unavailable.errors, [PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE])
        self.assertEqual(scan_unavailable.data["row_key"], row_key)

    def test_recovery_plan_result_is_dry_run_and_classifies_rows(self) -> None:
        rows = pending_publish_rows(
            [
                {
                    "manifest_path": r"C:\Pending\Ready.mkv.manifest.json",
                    "local_file": r"C:\Pending\Ready.mkv",
                    "server_out": r"\\nas\Movies\Ready.mkv",
                    "state": "parked",
                    "local_exists": True,
                },
                {
                    "manifest_path": r"C:\Pending\Broken.mkv.manifest.json",
                    "state": "unreadable",
                    "local_exists": False,
                    "error": "bad json",
                },
            ]
        )

        result = pending_publish_recovery_plan_result(rows, {"scope": "all"})

        self.assertTrue(result.ok)
        self.assertEqual(result.command, "pending_publish.recovery_plan_dry_run")
        self.assertEqual(result.severity, "warning")
        self.assertEqual(result.data["schema_version"], "pending_publish_recovery_plan.v1")
        self.assertEqual(result.data["scope"], "all")
        self.assertEqual(result.data["row_count"], 2)
        self.assertEqual(result.data["blocker_count"], 1)
        self.assertEqual(result.data["review_count"], 0)
        self.assertEqual(result.data["ready_count"], 1)
        self.assertTrue(result.data["dry_run_only"])
        self.assertFalse(result.data["would_mutate"])
        self.assertIn("unlock_or_repair_manifest_json", result.data["action_counts"])
        self.assertTrue(all(row["dry_run_only"] for row in result.data["rows"]))
        self.assertTrue(all(row["would_mutate"] is False for row in result.data["rows"]))
        self.assertEqual(pending_publish_recovery_plan_action(rows[1]), "unlock_or_repair_manifest_json")
        self.assertIn("does not move, delete, drain", result.data["mutation_guardrail"])

    def test_recovery_plan_selected_scope_requires_current_backend_row(self) -> None:
        rows = pending_publish_rows(
            [
                {
                    "manifest_path": r"C:\Pending\Ready.mkv.manifest.json",
                    "local_file": r"C:\Pending\Ready.mkv",
                    "server_out": r"\\nas\Movies\Ready.mkv",
                    "state": "parked",
                    "local_exists": True,
                }
            ]
        )
        row_key = pending_publish_row_key(rows[0])

        selected = pending_publish_recovery_plan_result(rows, {"scope": "selected", "row_key": row_key})
        missing = pending_publish_recovery_plan_result(rows, {"scope": "selected", "row_key": "missing"})

        self.assertTrue(selected.ok)
        self.assertEqual(selected.data["scope"], "selected")
        self.assertEqual(selected.data["selected_row_key"], row_key)
        self.assertEqual(selected.data["row_count"], 1)
        self.assertFalse(missing.ok)
        self.assertEqual(missing.severity, "warning")
        self.assertTrue(missing.data["dry_run_only"])
        self.assertFalse(missing.data["would_mutate"])

    def test_row_key_normalization_preserves_empty_field_separators_for_orphans(self) -> None:
        rows = pending_publish_rows(
            [
                {
                    "manifest_path": "",
                    "local_file": r"C:\Pending\Orphan.mkv",
                    "server_out": "",
                    "state": "orphan_payload",
                }
            ]
        )
        row_key = pending_publish_row_key(rows[0])

        self.assertTrue(row_key.startswith("\x1f"))
        self.assertEqual(normalize_pending_publish_row_key(f" \t{row_key}\r\n"), row_key)
        selected = pending_publish_recovery_plan_result(rows, {"scope": "selected", "row_key": row_key})
        self.assertTrue(selected.ok)
        self.assertEqual(selected.data["row_count"], 1)


if __name__ == "__main__":
    unittest.main()
