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
from app.validation import ValidationFailure, validate_api_payload  # noqa: E402
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

    def test_unknown_routes_keep_generic_object_boundary_for_compatibility(self) -> None:
        payload = {"anything": {"nested": True}}

        self.assertEqual(validate_api_payload("/api/future/command", payload), payload)

    def test_high_risk_mutation_routes_reject_unknown_fields(self) -> None:
        high_risk_payloads = {
            "/api/pipeline/start": {"mode": "once", "extra_args": "-NoDeleteSource"},
            "/api/pipeline/control": {"action": "pause", "extra": True},
            "/api/backend/shutdown": {"force_active_work_shutdown": True, "token": "client-owned"},
            "/api/rename/apply": {"paths": [], "selected_sources": [], "confirm_apply": True, "selected_ids": ["1"]},
            "/api/settings/preview-patch": {"changes": {}, "values": {}},
            "/api/settings/save-patch": {"changes": {}, "confirm_save": True, "values": {}},
            "/api/maintenance/release-build": {"destination_root": "C:/Deploy", "output_root": "C:/Other"},
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
            validate_api_payload("/api/settings/save-patch", {"changes": {}, "confirm_save": True}),
            {"changes": {}, "confirm_save": True},
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
