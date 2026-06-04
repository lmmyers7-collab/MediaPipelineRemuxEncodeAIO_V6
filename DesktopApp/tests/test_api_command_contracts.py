from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "DesktopApp"))

from app.contracts.api_commands import COMMAND_ROUTE_PAYLOAD_MODELS, validate_api_command_payload  # noqa: E402
from app.api.commands import COMMAND_ROUTE_METHODS  # noqa: E402
from app.validation.boundary import ValidationFailure, validate_api_payload  # noqa: E402
from mediapipeline_desktop_app.api.routes_command import POST_ROUTE_HANDLERS  # noqa: E402


FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def _source_media_payload() -> dict:
    from app.contracts.source_media import source_media_from_ffprobe

    raw = json.loads((FIXTURE_ROOT / "tv_h264_1080p_12mbps_mkv.json").read_text(encoding="utf-8"))
    return source_media_from_ffprobe(raw).model_dump(mode="json")


class ApiCommandContractsTests(unittest.TestCase):
    def test_every_post_command_route_has_a_contract_model(self) -> None:
        self.assertEqual(sorted(COMMAND_ROUTE_PAYLOAD_MODELS), sorted(POST_ROUTE_HANDLERS))
        self.assertEqual(sorted(COMMAND_ROUTE_METHODS), sorted(POST_ROUTE_HANDLERS))
        self.assertEqual(
            {route: spec.method_name for route, spec in POST_ROUTE_HANDLERS.items()},
            COMMAND_ROUTE_METHODS,
        )

    def test_known_route_payload_validation_preserves_wire_payload_and_extra_fields(self) -> None:
        payload = {
            "path": r"C:\Media\Movie.mkv",
            "level": "high",
            "reason": "operator request",
            "client_trace_id": "trace-1",
        }

        validated = validate_api_payload("/api/queue/priority", payload)

        self.assertEqual(validated, payload)

    def test_missing_optional_fields_are_not_added_to_payload(self) -> None:
        self.assertEqual(validate_api_command_payload("/api/settings/reload", {}), {})
        self.assertEqual(validate_api_payload("/api/queue/strategy", {"strategy": "Standard"}), {"strategy": "Standard"})
        self.assertEqual(validate_api_payload("/api/queue/scan", {}), {})
        self.assertEqual(validate_api_payload("/api/queue/priority", {"clear_all": True}), {"clear_all": True})

    def test_schedule_day_window_payload_contract_preserves_active_wire_shape(self) -> None:
        payload = {
            "enabled": True,
            "day_windows": {"Monday": "9:00 AM - 10:00 AM"},
            "confirm_save": True,
        }

        self.assertEqual(validate_api_payload("/api/schedule/save", payload), payload)

    def test_failure_marker_clear_requires_strict_contract_fields(self) -> None:
        payload = {
            "scope": "selected",
            "marker_paths": [r"C:\LocalBase\State\Failures\Markers\one.json"],
            "dry_run": True,
        }

        self.assertEqual(validate_api_payload("/api/failures/clear", payload), payload)
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/failures/clear", {**payload, "path": r"C:\Media\Movie.mkv"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/failures/clear", {**payload, "confirm_clear": "false"})

    def test_failure_clear_contract_names_backend_marker_fields(self) -> None:
        payload = {
            "scope": "selected",
            "marker_path": r"C:\LocalBase\State\Failures\Markers\one.json",
            "marker_paths": [r"C:\LocalBase\State\Failures\Markers\one.json"],
            "source_json": r"C:\LocalBase\State\Failures\Markers\one.json",
            "dry_run": True,
            "confirm_clear": False,
        }

        self.assertEqual(validate_api_payload("/api/failures/clear", payload), payload)

    def test_audit_score_policy_contract_accepts_v2_issue_code_weights(self) -> None:
        payload = {
            "policy": {
                "high_issue": 90,
                "medium_issue": 40,
                "issue_code_weights": {
                    "audio-default-policy-mismatch": 123,
                    "bdpgs-subtitles-ocr-candidate": 44,
                    "unknown-code": 999,
                },
            },
            "reset": False,
        }

        self.assertEqual(validate_api_payload("/api/audit/score-policy", payload), payload)
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/audit/score-policy", {**payload, "path": r"C:\Media\Movie.mkv"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/audit/score-policy", {**payload, "reset": "false"})

    def test_unknown_routes_keep_generic_object_boundary_for_compatibility(self) -> None:
        payload = {"anything": {"nested": True}}

        self.assertEqual(validate_api_payload("/api/future/command", payload), payload)

    def test_high_risk_mutation_routes_reject_unknown_fields(self) -> None:
        high_risk_payloads = {
            "/api/pipeline/start": {"mode": "once", "extra_args": "-NoDeleteSource"},
            "/api/pipeline/control": {"action": "pause", "extra": True},
            "/api/queue/scan": {"mode": "inventory_then_curate", "path": r"C:\Media\Movie.mkv"},
            "/api/queue/file-overrides/series-apply": {
                "path": r"C:\Media\TV\Show\S01E01.mkv",
                "proposed_override": {"audio": {"maxChannels": 2}},
                "confirm_apply": True,
                "preview_fingerprint": "fp",
                "row_keys": ["client-owned"],
            },
            "/api/backend/shutdown": {"force_active_work_shutdown": True, "token": "client-owned"},
            "/api/rename/apply": {"paths": [], "selected_sources": [], "confirm_apply": True, "selected_ids": ["1"]},
            "/api/settings/preview-patch": {"changes": {}, "values": {}},
            "/api/settings/save-patch": {"changes": {}, "confirm_save": True, "values": {}},
            "/api/maintenance/release-dry-run": {"destination_root": "C:/Deploy", "output_root": "C:/Other"},
            "/api/maintenance/release-build": {"destination_root": "C:/Deploy", "output_root": "C:/Other"},
            "/api/maintenance/completed-backfill-dry-run": {"timeout_seconds": 600, "output_root": "C:/Other"},
            "/api/maintenance/dependency-atlas": {"timeout_seconds": 600, "output_root": "C:/Other"},
            "/api/final-library-promotion/promote-queue": {"confirm_promote": True, "row_key": "client-owned"},
            "/api/final-library-promotion/pause": {"run_id": "run-1", "row_key": "client-owned"},
            "/api/final-library-promotion/resume": {"run_id": "run-1", "row_key": "client-owned"},
        }

        for route, payload in high_risk_payloads.items():
            with self.subTest(route=route):
                with self.assertRaises(ValidationFailure):
                    validate_api_payload(route, payload)

    def test_high_risk_mutation_routes_accept_known_fields_only(self) -> None:
        self.assertEqual(validate_api_payload("/api/pipeline/start", {"mode": "once"}), {"mode": "once"})
        self.assertEqual(
            validate_api_payload("/api/backend/shutdown", {"reason": "operator-close", "force_active_work_shutdown": False}),
            {"reason": "operator-close", "force_active_work_shutdown": False},
        )
        self.assertEqual(
            validate_api_payload("/api/backend/shutdown", {"force_active_work_shutdown": True}),
            {"force_active_work_shutdown": True},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/queue/scan",
                {
                    "mode": "inventory_then_curate",
                    "force": True,
                    "scope": "all",
                    "reason": "operator_requested_queue_scan",
                },
            ),
            {
                "mode": "inventory_then_curate",
                "force": True,
                "scope": "all",
                "reason": "operator_requested_queue_scan",
            },
        )
        self.assertEqual(
            validate_api_payload(
                "/api/queue/file-overrides/series-apply",
                {
                    "path": r"C:\Media\TV\Show\S01E01.mkv",
                    "proposed_override": {"audio": {"maxChannels": 2}},
                    "confirm_apply": True,
                    "preview_fingerprint": "fp",
                },
            ),
            {
                "path": r"C:\Media\TV\Show\S01E01.mkv",
                "proposed_override": {"audio": {"maxChannels": 2}},
                "confirm_apply": True,
                "preview_fingerprint": "fp",
            },
        )
        self.assertEqual(
            validate_api_payload("/api/settings/save-patch", {"changes": {}, "confirm_save": True}),
            {"changes": {}, "confirm_save": True},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/maintenance/release-dry-run",
                {
                    "destination_root": "C:/Deploy",
                    "zip_package": True,
                    "verify": True,
                    "include_tests": False,
                    "include_dev_docs": False,
                    "include_optional_tools": False,
                    "include_tool_docs": False,
                    "keep_personal_config": False,
                    "timeout_seconds": 900,
                },
            ),
            {
                "destination_root": "C:/Deploy",
                "zip_package": True,
                "verify": True,
                "include_tests": False,
                "include_dev_docs": False,
                "include_optional_tools": False,
                "include_tool_docs": False,
                "keep_personal_config": False,
                "timeout_seconds": 900,
            },
        )
        self.assertEqual(
            validate_api_payload("/api/maintenance/completed-backfill-dry-run", {"timeout_seconds": 600}),
            {"timeout_seconds": 600},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/maintenance/dependency-atlas",
                {"timeout_seconds": 600, "min_overview_edge_count": 4, "min_overview_files": 2},
            ),
            {"timeout_seconds": 600, "min_overview_edge_count": 4, "min_overview_files": 2},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/settings/preview-patch",
                {"changes": {}, "library_profile_resets": [{"library_id": "movies", "overrides": {"editor": ["RoutingProfile"]}}]},
            ),
            {"changes": {}, "library_profile_resets": [{"library_id": "movies", "overrides": {"editor": ["RoutingProfile"]}}]},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/settings/save-patch",
                {"changes": {}, "library_profile_resets": [{"library_id": "movies", "path_fields": ["source_path"]}], "confirm_save": True},
            ),
            {"changes": {}, "library_profile_resets": [{"library_id": "movies", "path_fields": ["source_path"]}], "confirm_save": True},
        )
        self.assertEqual(
            validate_api_payload("/api/settings/pipeline-plan-preview", {"source_media": _source_media_payload()}),
            {"source_media": _source_media_payload(), "changes": {}, "remove_keys": []},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/rename/apply",
                {"paths": [], "selected_sources": [], "confirm_apply": True, "allow_outside_configured_roots": False},
            ),
            {"paths": [], "selected_sources": [], "confirm_apply": True, "allow_outside_configured_roots": False},
        )
        self.assertEqual(
            validate_api_payload("/api/final-library-promotion/promote-queue", {"confirm_promote": True}),
            {"confirm_promote": True},
        )
        self.assertEqual(
            validate_api_payload("/api/final-library-promotion/promote-queue", {"confirm_promote": True, "row_keys": ["row-1"]}),
            {"confirm_promote": True, "row_keys": ["row-1"]},
        )
        self.assertEqual(
            validate_api_payload("/api/final-library-promotion/pause", {"run_id": "run-1"}),
            {"run_id": "run-1"},
        )
        self.assertEqual(
            validate_api_payload("/api/final-library-promotion/resume", {"run_id": "run-1"}),
            {"run_id": "run-1"},
        )

    def test_backend_shutdown_force_cleanup_requires_strict_boolean(self) -> None:
        for value in ("true", "false", 1, 0):
            with self.subTest(value=value):
                with self.assertRaises(ValidationFailure):
                    validate_api_payload("/api/backend/shutdown", {"force_active_work_shutdown": value})

    def test_queue_scan_force_requires_strict_boolean(self) -> None:
        for value in ("true", "false", 1, 0):
            with self.subTest(value=value):
                with self.assertRaises(ValidationFailure):
                    validate_api_payload("/api/queue/scan", {"force": value})

    def test_command_ownership_matrix_lists_every_post_command_route(self) -> None:
        matrix = (REPO_ROOT / "Docs" / "inventories" / "COMMAND_OWNERSHIP_MATRIX.md").read_text(encoding="utf-8")

        self.assertIn("Total command routes: 51 POST routes across 9 contract groups.", matrix)
        for route in COMMAND_ROUTE_METHODS:
            with self.subTest(route=route):
                self.assertIn(f"`POST {route}`", matrix)

    def test_non_object_payload_still_fails_at_api_boundary(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/queue/priority", ["not", "an", "object"])  # type: ignore[arg-type]

    def test_settings_pipeline_plan_preview_rejects_malformed_source_and_unknown_keys(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_api_payload(
                "/api/settings/pipeline-plan-preview",
                {"source_media": {"schema_version": "source_media.v1", "unexpected": True}},
            )
        with self.assertRaises(ValidationFailure):
            validate_api_payload(
                "/api/settings/pipeline-plan-preview",
                {"source_media": _source_media_payload(), "path": "C:/Media/Movie.mkv"},
            )


if __name__ == "__main__":
    unittest.main()
