from __future__ import annotations

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
                "/api/rename/apply",
                {"paths": [], "selected_sources": [], "confirm_apply": True, "allow_outside_configured_roots": False},
            ),
            {"paths": [], "selected_sources": [], "confirm_apply": True, "allow_outside_configured_roots": False},
        )

    def test_non_object_payload_still_fails_at_api_boundary(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/queue/priority", ["not", "an", "object"])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
