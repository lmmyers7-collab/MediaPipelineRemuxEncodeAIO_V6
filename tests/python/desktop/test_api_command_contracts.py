from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.contracts.api_commands import COMMAND_ROUTE_PAYLOAD_MODELS, validate_api_command_payload  # noqa: E402
from mediapipeline.core.api.commands import COMMAND_ROUTE_METHODS  # noqa: E402
from mediapipeline.core.validation.boundary import ValidationFailure, validate_api_payload  # noqa: E402
from mediapipeline.desktop.api.command_journal_policy import bounded_command_evidence  # noqa: E402
from mediapipeline.desktop.api.handler_policy import should_record_validation_failure_journal  # noqa: E402
from mediapipeline.desktop.api.routes_command import POST_ROUTE_HANDLERS  # noqa: E402


FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def _source_media_payload() -> dict:
    from mediapipeline.contracts.source_media import source_media_from_ffprobe

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
            "position": 2,
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
            "/api/queue/file-overrides/remux-pilot-promote": {
                "pilot_source_paths": [
                    r"C:\Media\TV\Show\Season 01\Show.S01E01.mkv",
                    r"C:\Media\TV\Show\Season 01\Show.S01E02.mkv",
                    r"C:\Media\TV\Show\Season 01\Show.S01E03.mkv",
                ],
                "confirm_apply": True,
                "future_rule": True,
            },
            "/api/backend/shutdown": {"force_active_work_shutdown": True, "token": "client-owned"},
            "/api/rename/apply": {"paths": [], "selected_sources": [], "confirm_apply": True, "selected_ids": ["1"]},
            "/api/rename/undo": {
                "undo_manifest": r"C:\State\RenameUndo\rename-undo.json",
                "confirm_undo": True,
                "client_owned": True,
            },
            "/api/rename/filter-cases": {
                "source_folder": "Show S01",
                "source_file": "S01E01.mkv",
                "expected_name": "Show - S01E01.mkv",
                "confirm_append": True,
                "fixture_path": "client-owned",
            },
            "/api/settings/preview-patch": {"changes": {}, "values": {}},
            "/api/settings/save-patch": {"changes": {}, "confirm_save": True, "values": {}},
            "/api/settings/import-psd1-preview": {"path": r"C:\Media\Movie.mkv"},
            "/api/settings/import-psd1": {"confirm_import": True, "path": r"C:\Media\Movie.mkv"},
            "/api/settings/wizard/save": {"wizard": {}, "confirm_save": True, "values": {}},
            "/api/schedule/preview": {"enabled": True, "values": {}},
            "/api/schedule/save": {"enabled": True, "confirm_save": True, "values": {}},
            "/api/maintenance/release-dry-run": {"destination_root": "C:/Deploy", "output_root": "C:/Other"},
            "/api/maintenance/release-build": {"destination_root": "C:/Deploy", "output_root": "C:/Other"},
            "/api/maintenance/completed-backfill-dry-run": {"timeout_seconds": 600, "output_root": "C:/Other"},
            "/api/maintenance/retention-dry-run": {"limit": 25, "path": r"C:\Media\Movie.mkv"},
            "/api/maintenance/dependency-atlas": {"timeout_seconds": 600, "output_root": "C:/Other"},
            "/api/maintenance/dependency-atlas/open-folder": {"path": "C:/Other"},
            "/api/maintenance/archive-state-journals": {"confirm_archive": True, "path": "C:/Other"},
            "/api/diagnostics/tdarr-matrix-audit": {"action": "report", "path": "C:/Other"},
            "/api/diagnostics/tdarr-matrix/evidence/open": {
                "run_id": "run-1",
                "finding_key": "finding-1",
                "target": "stdout",
                "path": "C:/Other",
            },
            "/api/diagnostics/tdarr-matrix/rerun": {
                "source_run_id": "run-1",
                "selection": "selected",
                "finding_keys": ["finding-1"],
                "generated_path": "source/Movies/Movie.mkv",
            },
            "/api/metrics/sources": {"action": "add", "path": r"D:\Media", "label": "Drive D", "root": r"E:\Other"},
            "/api/metrics/backfill": {"scope": "enabled", "recursive": True},
            "/api/completed/reconcile-manifest-dry-run": {"scope": "selected", "row_key": "row-1", "manifest_path": r"C:\Other\completed.jsonl"},
            "/api/completed/repair-sidecar-metadata-dry-run": {"scope": "selected", "row_key": "row-1", "sidecar_json": {"output_path": "client-owned"}},
            "/api/pending-publish/repair-manifest-dry-run": {"scope": "selected", "row_key": "row-1", "patch": [{"op": "replace"}]},
            "/api/pending-publish/reconcile-orphan-payloads-dry-run": {"scope": "selected", "row_key": "row-1", "payload_path": r"C:\Other\Movie.mkv"},
            "/api/network/coordinator/start-dry-run": {"reason": "check", "path": r"C:\Media\Movie.mkv"},
            "/api/network/coordinator/stop-dry-run": {"reason": "check", "path": r"C:\Media\Movie.mkv"},
            "/api/network/coordinator/join-blob": {"confirm_create": True, "token": "client-owned"},
            "/api/network/worker/start-dry-run": {"reason": "check", "path": r"C:\Media\Movie.mkv"},
            "/api/network/worker/stop-dry-run": {"reason": "check", "path": r"C:\Media\Movie.mkv"},
            "/api/network/worker/test-connection": {"timeout_seconds": 5, "path": r"C:\Media\Movie.mkv"},
            "/api/network/worker/discover-coordinators": {"timeout_seconds": 5, "path": r"C:\Media\Movie.mkv"},
            "/api/network/worker/join-cluster": {"join_blob": "client-owned", "confirm_import": True, "path": r"C:\Media\Movie.mkv"},
            "/api/network/coordinator/start": {"confirm_start": True, "path": r"C:\Media\Movie.mkv"},
            "/api/network/coordinator/stop": {"confirm_stop": True, "path": r"C:\Media\Movie.mkv"},
            "/api/network/worker/start": {"confirm_start": True, "path": r"C:\Media\Movie.mkv"},
            "/api/network/worker/stop": {"confirm_stop": True, "path": r"C:\Media\Movie.mkv"},
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
            validate_api_payload(
                "/api/queue/file-overrides/remux-pilot-promote",
                {
                    "pilot_source_paths": [
                        r"C:\Media\TV\Show\Season 01\Show.S01E01.mkv",
                        r"C:\Media\TV\Show\Season 01\Show.S01E02.mkv",
                        r"C:\Media\TV\Show\Season 01\Show.S01E03.mkv",
                    ],
                    "confirm_apply": True,
                    "reason": "operator verified three fallback pilots",
                },
            ),
            {
                "pilot_source_paths": [
                    r"C:\Media\TV\Show\Season 01\Show.S01E01.mkv",
                    r"C:\Media\TV\Show\Season 01\Show.S01E02.mkv",
                    r"C:\Media\TV\Show\Season 01\Show.S01E03.mkv",
                ],
                "confirm_apply": True,
                "reason": "operator verified three fallback pilots",
            },
        )
        with self.assertRaises(ValidationFailure):
            validate_api_payload(
                "/api/queue/file-overrides/remux-pilot-promote",
                {
                    "pilot_source_paths": [
                        r"C:\Media\TV\Show\Season 01\Show.S01E01.mkv",
                        r"C:\Media\TV\Show\Season 01\Show.S01E02.mkv",
                        r"C:\Media\TV\Show\Season 01\Show.S01E03.mkv",
                    ],
                    "confirm_apply": "true",
                },
            )
        self.assertEqual(
            validate_api_payload("/api/settings/save-patch", {"changes": {}, "confirm_save": True}),
            {"changes": {}, "confirm_save": True},
        )
        self.assertEqual(validate_api_payload("/api/settings/import-psd1-preview", {}), {})
        self.assertEqual(
            validate_api_payload("/api/settings/import-psd1", {"confirm_import": True}),
            {"confirm_import": True},
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
                    "force": True,
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
                "force": True,
                "timeout_seconds": 900,
            },
        )
        self.assertEqual(
            validate_api_payload("/api/maintenance/completed-backfill-dry-run", {"timeout_seconds": 600}),
            {"timeout_seconds": 600},
        )
        self.assertEqual(
            validate_api_payload("/api/maintenance/retention-dry-run", {"limit": 25, "reason": "soak prep"}),
            {"limit": 25, "reason": "soak prep"},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/maintenance/dependency-atlas",
                {"timeout_seconds": 600, "min_overview_edge_count": 4, "min_overview_files": 2},
            ),
            {"timeout_seconds": 600, "min_overview_edge_count": 4, "min_overview_files": 2},
        )
        self.assertEqual(validate_api_payload("/api/maintenance/dependency-atlas/open-folder", {}), {})
        self.assertEqual(
            validate_api_payload("/api/maintenance/archive-state-journals", {"confirm_archive": True, "reason": "launch recovery"}),
            {"confirm_archive": True, "reason": "launch recovery"},
        )
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/maintenance/archive-state-journals", {"confirm_archive": "true"})
        self.assertEqual(
            validate_api_payload(
                "/api/diagnostics/tdarr-matrix-audit",
                {"action": "cleanup-delete", "confirm_delete_full_matrix": True},
            ),
            {"action": "cleanup-delete", "confirm_delete_full_matrix": True},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/diagnostics/tdarr-matrix/evidence/open",
                {"run_id": "run-1", "finding_key": "finding-1", "target": "stdout"},
            ),
            {"run_id": "run-1", "finding_key": "finding-1", "target": "stdout"},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/diagnostics/tdarr-matrix/rerun",
                {"source_run_id": "run-1", "selection": "selected", "finding_keys": ["finding-1"]},
            ),
            {"source_run_id": "run-1", "selection": "selected", "finding_keys": ["finding-1"]},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/metrics/sources",
                {"action": "add", "path": r"D:\Media", "label": "Drive D", "enabled": True},
            ),
            {"action": "add", "path": r"D:\Media", "label": "Drive D", "enabled": True},
        )
        self.assertEqual(
            validate_api_payload("/api/metrics/backfill", {"scope": "enabled", "max_sidecars": 100}),
            {"scope": "enabled", "max_sidecars": 100},
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
            validate_api_payload(
                "/api/rename/filter-cases",
                {
                    "source_folder": "Show S01",
                    "source_file": "S01E01.mkv",
                    "expected_name": "Show - S01E01.mkv",
                    "expected_show": "Show",
                    "expected_season": 1,
                    "season_number": 1,
                    "status": "pending",
                    "notes": "bad source title suffix",
                    "confirm_append": True,
                },
            ),
            {
                "source_folder": "Show S01",
                "source_file": "S01E01.mkv",
                "expected_name": "Show - S01E01.mkv",
                "expected_show": "Show",
                "expected_season": 1,
                "season_number": 1,
                "status": "pending",
                "notes": "bad source title suffix",
                "confirm_append": True,
            },
        )
        self.assertEqual(
            validate_api_payload(
                "/api/rename/apply",
                {
                    "paths": [],
                    "selected_sources": [],
                    "confirm_apply": True,
                    "rename_sidecars": False,
                    "force_pipeline_name": True,
                    "force_pipeline_name_overrides": {"C:/Media/Show E01.mkv": False},
                    "use_pipeline_naming_preview": False,
                },
            ),
            {
                "paths": [],
                "selected_sources": [],
                "confirm_apply": True,
                "rename_sidecars": False,
                "force_pipeline_name": True,
                "force_pipeline_name_overrides": {"C:/Media/Show E01.mkv": False},
                "use_pipeline_naming_preview": False,
            },
        )
        self.assertEqual(
            validate_api_payload("/api/network/coordinator/start-dry-run", {"reason": "operator check"}),
            {"reason": "operator check"},
        )
        for route in [
            "/api/completed/reconcile-manifest-dry-run",
            "/api/completed/repair-sidecar-metadata-dry-run",
            "/api/pending-publish/repair-manifest-dry-run",
            "/api/pending-publish/reconcile-orphan-payloads-dry-run",
        ]:
            with self.subTest(route=route):
                self.assertEqual(
                    validate_api_payload(route, {"scope": "selected", "row_key": "row-1", "limit": 25, "reason": "operator review"}),
                    {"scope": "selected", "row_key": "row-1", "limit": 25, "reason": "operator review"},
                )
                with self.assertRaises(ValidationFailure):
                    validate_api_payload(route, {"scope": "selected", "limit": 25})
                with self.assertRaises(ValidationFailure):
                    validate_api_payload(route, {"scope": "selected", "row_key": "   "})
        self.assertEqual(
            validate_api_payload("/api/startup/reconcile-dry-run", {"scope": "all", "limit": 25, "reason": "operator review"}),
            {"scope": "all", "limit": 25, "reason": "operator review"},
        )
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/startup/reconcile-dry-run", {"scope": "selected", "row_key": "row-1"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/startup/reconcile-dry-run", {"scope": "all", "manifest_path": r"C:\Other\pending.json"})
        self.assertEqual(
            validate_api_payload("/api/network/coordinator/start", {"confirm_start": True, "reason": "operator start"}),
            {"confirm_start": True, "reason": "operator start"},
        )
        self.assertEqual(
            validate_api_payload("/api/network/worker/stop", {"confirm_stop": True}),
            {"confirm_stop": True},
        )
        self.assertEqual(
            validate_api_payload("/api/network/worker/test-connection", {"timeout_seconds": 5}),
            {"timeout_seconds": 5},
        )
        self.assertEqual(
            validate_api_payload("/api/network/worker/discover-coordinators", {"timeout_seconds": 1}),
            {"timeout_seconds": 1},
        )
        self.assertEqual(
            validate_api_payload(
                "/api/network/coordinator/join-blob",
                {
                    "coordinator_url": "http://coordinator.test:7830",
                    "confirm_create": True,
                    "rotate_token": True,
                    "confirm_rotate": True,
                },
            ),
            {
                "coordinator_url": "http://coordinator.test:7830",
                "confirm_create": True,
                "rotate_token": True,
                "confirm_rotate": True,
            },
        )
        self.assertEqual(
            validate_api_payload(
                "/api/network/worker/join-cluster",
                {"join_blob": "client-owned", "confirm_import": True, "timeout_seconds": 5},
            ),
            {"join_blob": "client-owned", "confirm_import": True, "timeout_seconds": 5},
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

    def test_network_lifecycle_payloads_require_route_specific_strict_confirmation(self) -> None:
        self.assertEqual(
            validate_api_payload("/api/network/coordinator/start-dry-run", {"reason": "operator check"}),
            {"reason": "operator check"},
        )
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/network/coordinator/start-dry-run", {"confirm_start": True})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/network/coordinator/start", {"reason": "missing confirmation"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/network/coordinator/start", {"confirm_start": "true"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/network/coordinator/stop", {"confirm_start": True})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/network/worker/stop", {"confirm_stop": "1"})

    def test_secret_transfer_validation_failures_are_not_journaled(self) -> None:
        self.assertFalse(should_record_validation_failure_journal("/api/network/coordinator/join-blob"))
        self.assertFalse(should_record_validation_failure_journal("/api/network/worker/join-cluster"))
        self.assertFalse(should_record_validation_failure_journal("/api/network/worker/test-connection"))
        self.assertTrue(should_record_validation_failure_journal("/api/pipeline/control"))

    def test_command_journal_evidence_redacts_join_blob_keys(self) -> None:
        evidence = bounded_command_evidence(
            {
                "join_blob": "secret-blob-value",
                "nested": {
                    "JoinBlob": "secret-nested-value",
                    "safe": "visible",
                },
            }
        )

        self.assertEqual(evidence["join_blob"], "<redacted>")
        self.assertEqual(evidence["nested"]["JoinBlob"], "<redacted>")
        self.assertEqual(evidence["nested"]["safe"], "visible")
        self.assertNotIn("secret-blob-value", json.dumps(evidence, sort_keys=True))
        self.assertNotIn("secret-nested-value", json.dumps(evidence, sort_keys=True))

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

    def test_rename_and_final_library_confirmations_require_strict_boolean(self) -> None:
        cases = [
            ("/api/rename/apply", "confirm_apply", {"paths": [], "selected_sources": []}),
            ("/api/rename/apply", "rename_sidecars", {"paths": [], "selected_sources": [], "confirm_apply": True}),
            ("/api/rename/apply", "force_pipeline_name", {"paths": [], "selected_sources": [], "confirm_apply": True}),
            ("/api/rename/apply", "use_pipeline_naming_preview", {"paths": [], "selected_sources": [], "confirm_apply": True}),
            (
                "/api/rename/apply",
                "allow_outside_configured_roots",
                {"paths": [], "selected_sources": [], "confirm_apply": True},
            ),
            (
                "/api/rename/filter-cases",
                "confirm_append",
                {
                    "source_folder": "Show S01",
                    "source_file": "S01E01.mkv",
                    "expected_name": "Show - S01E01.mkv",
                },
            ),
            (
                "/api/rename/undo",
                "confirm_undo",
                {"undo_manifest": r"C:\State\RenameUndo\rename-undo.json"},
            ),
            ("/api/final-library-promotion/promote-queue", "confirm_promote", {"row_keys": ["row-1"]}),
        ]

        for route, field, base_payload in cases:
            for value in ("true", "false", 1, 0):
                with self.subTest(route=route, field=field, value=value):
                    with self.assertRaises(ValidationFailure):
                        validate_api_payload(route, {**base_payload, field: value})

        for value in ("true", "false", 1, 0):
            with self.subTest(route="/api/rename/apply", field="force_pipeline_name_overrides", value=value):
                with self.assertRaises(ValidationFailure):
                    validate_api_payload(
                        "/api/rename/apply",
                        {
                            "paths": [],
                            "selected_sources": [],
                            "confirm_apply": True,
                            "force_pipeline_name_overrides": {"C:/Media/Show E01.mkv": value},
                        },
                    )

    def test_settings_schedule_and_maintenance_booleans_require_strict_boolean(self) -> None:
        cases = [
            ("/api/settings/save-patch", "confirm_save", {"changes": {}}),
            ("/api/settings/import-psd1", "confirm_import", {}),
            ("/api/settings/wizard/save", "confirm_save", {"wizard": {}}),
            ("/api/schedule/preview", "enabled", {}),
            ("/api/schedule/save", "enabled", {"confirm_save": True}),
            ("/api/schedule/save", "confirm_save", {"enabled": True}),
            ("/api/maintenance/release-dry-run", "zip_package", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "verify", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "include_tests", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "include_dev_docs", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "include_optional_tools", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "include_tool_docs", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "include_tauri_preview_binary", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "keep_personal_config", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-dry-run", "force", {"destination_root": "C:/Deploy"}),
            ("/api/maintenance/release-build", "zip_package", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "verify", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "include_tests", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "include_dev_docs", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "include_optional_tools", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "include_tool_docs", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "include_tauri_preview_binary", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "keep_personal_config", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "force", {"destination_root": "C:/Deploy", "confirm_create": True}),
            ("/api/maintenance/release-build", "confirm_create", {"destination_root": "C:/Deploy"}),
            ("/api/metrics/sources", "enabled", {"action": "add", "path": r"D:\Media"}),
        ]

        for route, field, base_payload in cases:
            for value in ("true", "false", 1, 0):
                with self.subTest(route=route, field=field, value=value):
                    with self.assertRaises(ValidationFailure):
                        validate_api_payload(route, {**base_payload, field: value})

    def test_command_ownership_matrix_lists_every_post_command_route(self) -> None:
        matrix = (REPO_ROOT / "docs" / "inventories" / "COMMAND_OWNERSHIP_MATRIX.md").read_text(encoding="utf-8")

        self.assertIn(f"Total command routes: {len(COMMAND_ROUTE_METHODS)} POST routes across 11 contract groups.", matrix)
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
