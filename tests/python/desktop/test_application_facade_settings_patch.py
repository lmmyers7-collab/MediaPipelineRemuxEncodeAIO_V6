from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ConfigSaveResult
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.config.load import config_from_mapping, config_to_flat_dict
from mediapipeline.core.config.library_profiles import normalize_library_profile_config_values
from mediapipeline.core.config.settings_patch_policy import settings_config_digest
from mediapipeline.core.config.settings_store import SettingsAuthorityConflictError
from tests.python.desktop.application_facade_test_support import DummyFacadeService, _resolved
from tests.python.desktop.test_service_config_validation import (
    _path_key,
    _path_within_root,
    _valid_config_values,
    validate_config_values,
)


class AuthoritySaveService(DummyFacadeService):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.authority_save_calls: list[dict[str, object]] = []

    def save_settings_authority(
        self,
        resolved,
        candidate_settings: dict[str, object],
        *,
        expected_authority_digest: str,
    ) -> ConfigSaveResult:
        self.authority_save_calls.append(
            {
                "config_path": resolved.config_path,
                "candidate_settings": dict(candidate_settings),
                "expected_authority_digest": expected_authority_digest,
            }
        )
        return ConfigSaveResult(output_path=resolved.config_path, backup_path=None)


class StatefulAuthoritySaveService(AuthoritySaveService):
    def __init__(self, root: Path, authority: dict[str, object]) -> None:
        super().__init__(root)
        self.authority = json.loads(json.dumps(authority))

    def load_settings_authority(self, config_path: Path, powershell_host: str | None) -> dict[str, object]:
        _ = config_path, powershell_host
        return json.loads(json.dumps(self.authority))

    def read_settings_authority(self, config_path: Path, powershell_host: str | None) -> dict[str, object]:
        _ = config_path, powershell_host
        return json.loads(json.dumps(self.authority))

    def save_settings_authority(
        self,
        resolved,
        candidate_settings: dict[str, object],
        *,
        expected_authority_digest: str,
    ) -> ConfigSaveResult:
        current_digest = settings_config_digest(self.authority)
        candidate_digest = settings_config_digest(candidate_settings)
        if candidate_digest != current_digest and expected_authority_digest != current_digest:
            raise SettingsAuthorityConflictError(
                expected_digest=expected_authority_digest,
                current_digest=current_digest,
                candidate_digest=candidate_digest,
            )
        result = super().save_settings_authority(
            resolved,
            candidate_settings,
            expected_authority_digest=expected_authority_digest,
        )
        self.authority = json.loads(json.dumps(candidate_settings))
        return result


class ImportSettingsService(DummyFacadeService):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.import_calls = 0

    def import_psd1_settings_preview(self, resolved) -> dict[str, object]:
        return {
            "schema_version": "desktop_settings_import_psd1_preview.v1",
            "source_psd1_path": str(resolved.config_path),
            "settings": {"RoutingProfile": "plex_direct_stream"},
            "legacy_extras": {},
            "legacy_extras_count": 0,
            "migrations_applied": [],
            "errors": [],
            "warnings": [],
            "can_import": True,
            "writes_config": False,
            "writes_store": False,
        }

    def import_psd1_settings(self, resolved) -> dict[str, object]:
        self.import_calls += 1
        return {
            "schema_version": "desktop_settings_import_psd1_result.v1",
            "source_psd1_path": str(resolved.config_path),
            "settings_store_path": str(resolved.workspace_root / "settings.v1.json"),
            "projection_path": str(resolved.workspace_root / "settings_projection.v1.json"),
            "config_path": str(resolved.config_path),
            "backup_path": "",
            "legacy_extras_count": 0,
            "migrations_applied": [],
            "writes_config": True,
            "writes_store": True,
        }


def _confirmed_patch_request(facade: MediaPipelineApplicationFacade, resolved, request: dict[str, object]) -> dict[str, object]:
    preview = facade.preview_settings_patch(resolved, request)
    data = preview.data if isinstance(preview.data, dict) else {}
    confirmed = dict(request)
    confirmed["confirm_save"] = True
    if isinstance(data.get("review_confirmation"), dict):
        confirmed["review_confirmation"] = dict(data["review_confirmation"])
    return confirmed


LIBRARY_PROFILE_ROUND_TRIP_FIXTURE = (
    find_repo_root(Path(__file__)) / "tests" / "fixtures" / "settings" / "library_profiles_round_trip_cases.json"
)


class ApplicationFacadeSettingsPatchTests(unittest.TestCase):
    def test_settings_preview_uses_pure_authority_reader_and_never_repair_loader(self) -> None:
        class PreviewAuthorityService(DummyFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.read_calls = 0
                self.repair_calls = 0

            def read_settings_authority(self, config_path: Path, powershell_host: str | None) -> dict[str, object]:
                _ = config_path, powershell_host
                self.read_calls += 1
                return {"RoutingProfile": "plex_direct_stream"}

            def load_settings_authority(self, config_path: Path, powershell_host: str | None) -> dict[str, object]:
                _ = config_path, powershell_host
                self.repair_calls += 1
                return {"RoutingProfile": "repair-path-must-not-run"}

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = PreviewAuthorityService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "stale-resolved-value"}

            preview = facade.preview_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}},
            )

        self.assertTrue(preview.ok)
        self.assertEqual(service.read_calls, 1)
        self.assertEqual(service.repair_calls, 0)
        routing_entry = next(entry for entry in preview.data["review_entries"] if entry["key"] == "RoutingProfile")
        self.assertEqual(routing_entry["current_value"], "plex_direct_stream")

    def test_legacy_movie_remove_terms_persist_only_on_next_explicit_settings_save(self) -> None:
        legacy_terms = [
            "sample",
            "trailer",
            "extras",
            "featurette",
            "deleted scenes",
            "behind the scenes",
            *(f"{value:02d}" for value in range(1, 13)),
        ]
        expected_terms = legacy_terms[:6]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            original_text = "@{ RenameMovieRemoveTerms = @('sample', '01', '12'); RoutingProfile = 'plex_direct_stream' }\n"
            config_path.write_text(original_text, encoding="utf-8")
            loaded_config = config_to_flat_dict(
                config_from_mapping(
                    {
                        "RoutingProfile": "plex_direct_stream",
                        "RenameMovieRemoveTerms": legacy_terms,
                    }
                )
            )
            self.assertEqual(loaded_config["RenameMovieRemoveTerms"], expected_terms)
            self.assertEqual(config_path.read_text(encoding="utf-8"), original_text)

            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = loaded_config
            request = {"changes": {"RoutingProfile": "plex_direct_play"}}
            saved = facade.save_settings_patch(resolved, _confirmed_patch_request(facade, resolved, request))

            self.assertTrue(saved.ok)
            self.assertEqual(service.saved_config_calls[-1]["config_values"]["RenameMovieRemoveTerms"], expected_terms)
            self.assertNotEqual(config_path.read_text(encoding="utf-8"), original_text)

    def test_settings_save_rejects_stale_preview_when_authority_generation_changed(self) -> None:
        class CasService(DummyFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.authority_reads = 0

            def read_settings_authority(self, config_path, powershell_host):
                _ = (config_path, powershell_host)
                self.authority_reads += 1
                if self.authority_reads == 1:
                    return {"RoutingProfile": "plex_direct_stream"}
                return {"RoutingProfile": "external_new_value"}

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = CasService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}
            request = _confirmed_patch_request(
                facade,
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}},
            )

            result = facade.save_settings_patch(resolved, request)

        self.assertFalse(result.ok)
        self.assertIn("authority changed after preview", result.message)
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_patch_coerces_coordinator_local_string_true_to_real_bool(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorAlsoEncodeLocally": False,
            }

            patch = facade._settings_patch_candidate(
                resolved,
                {"changes": {"CoordinatorAlsoEncodeLocally": "true"}},
                command="settings.preview_patch",
            )
            numeric_patch = facade._settings_patch_candidate(
                resolved,
                {"changes": {"CoordinatorAlsoEncodeLocally": 1}},
                command="settings.preview_patch",
            )

        self.assertIs(patch["merged"]["CoordinatorAlsoEncodeLocally"], True)
        self.assertEqual(numeric_patch["merged"]["CoordinatorAlsoEncodeLocally"], 1)
        self.assertIsNot(numeric_patch["merged"]["CoordinatorAlsoEncodeLocally"], True)

    def test_settings_patch_preview_uses_backend_config_and_redacts_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "SizeGuardMode": "advisory",
                "CoordinatorAuthToken": "secret-token",
            }

            preview = facade.preview_settings_patch(resolved, {"changes": {"RoutingProfile": "plex_direct_play"}})
            secret_attempts = [
                facade.preview_settings_patch(
                    resolved,
                    {"changes": {"CoordinatorAuthToken": "new-coordinator-secret"}},
                ),
                facade.preview_settings_patch(
                    resolved,
                    {"changes": {"WorkerAuthToken": "new-worker-secret"}},
                ),
                facade.preview_settings_patch(
                    resolved,
                    {"changes": {"CoordinatorAuthToken": "<redacted>"}},
                ),
                facade.preview_settings_patch(
                    resolved,
                    {"changes": {}, "remove_keys": ["WorkerAuthToken"]},
                ),
                facade.preview_settings_patch(
                    resolved,
                    {
                        "changes": {"CoordinatorAuthToken": "request-field-cannot-authorize"},
                        "allow_network_credentials": True,
                    },
                ),
            ]

        self.assertTrue(preview.ok)
        self.assertEqual(preview.command, "settings.preview_patch")
        self.assertIn("RoutingProfile", preview.data["changed_keys"])
        self.assertFalse(preview.data["writes_config"])
        self.assertEqual(preview.data["review_entries_schema_version"], "desktop_settings_patch_review_entries.v1")
        self.assertEqual(
            preview.data["review_confirmation"]["schema_version"],
            "desktop_settings_save_review_confirmation.v1",
        )
        self.assertTrue(preview.data["review_confirmation"]["preview_id"])
        self.assertEqual(preview.data["settings_progress"]["schema_version"], "desktop_settings_save_reload_progress.v1")
        self.assertEqual(preview.data["progress_bars"][0]["id"], "settings_save_reload")
        self.assertEqual(preview.data["progress_bars"][0]["percent"], 20.0)
        diff_text = "\n".join(preview.data["redacted_diff_lines"])
        self.assertIn("plex_direct_play", diff_text)
        self.assertIn("<redacted>", diff_text)
        self.assertNotIn("secret-token", diff_text)
        review_entry = next(entry for entry in preview.data["review_entries"] if entry["key"] == "RoutingProfile")
        self.assertEqual(review_entry["status"], "changed")
        self.assertEqual(review_entry["source"], "submitted")
        self.assertEqual(review_entry["current_value"], "plex_direct_stream")
        self.assertEqual(review_entry["submitted_value"], "plex_direct_play")
        self.assertEqual(review_entry["new_value"], "plex_direct_play")
        self.assertEqual(preview.data["risk_summary"]["total_count"], 0)
        for attempt in secret_attempts:
            with self.subTest(errors=attempt.errors):
                self.assertFalse(attempt.ok)
                self.assertIn("cannot be changed through Settings Patch", "\n".join(attempt.errors))
        serialized_attempts = json.dumps([attempt.to_mapping() for attempt in secret_attempts], sort_keys=True)
        for secret in (
            "secret-token",
            "new-coordinator-secret",
            "new-worker-secret",
            "request-field-cannot-authorize",
        ):
            self.assertNotIn(secret, serialized_attempts)

    def test_settings_save_patch_uses_json_authority_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = AuthoritySaveService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "SizeGuardMode": "advisory",
            }

            saved = facade.save_settings_patch(
                resolved,
                _confirmed_patch_request(facade, resolved, {"changes": {"RoutingProfile": "plex_direct_play"}}),
            )

        self.assertTrue(saved.ok)
        self.assertEqual(len(service.authority_save_calls), 1)
        self.assertEqual(service.authority_save_calls[0]["candidate_settings"]["RoutingProfile"], "plex_direct_play")
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_save_patch_rejects_missing_false_and_non_boolean_confirmation_before_authority_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = StatefulAuthoritySaveService(
                root,
                {"RoutingProfile": "plex_direct_stream", "VideoQuality": 22},
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = dict(service.authority)
            requests = [
                {"changes": {"VideoQuality": 24}},
                *(
                    {"changes": {"VideoQuality": 24}, "confirm_save": value}
                    for value in (False, "true", "false", 1, 0, None, [], {})
                ),
            ]

            results = [facade.save_settings_patch(resolved, request) for request in requests]

        self.assertTrue(all(not result.ok for result in results))
        self.assertTrue(all("confirm_save must be true" in "\n".join(result.warnings) for result in results))
        self.assertEqual(service.authority_save_calls, [])
        self.assertEqual(service.authority["VideoQuality"], 22)

    def test_settings_save_patch_retry_after_lost_response_reports_idempotent_durable_success(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = StatefulAuthoritySaveService(
                root,
                {"RoutingProfile": "plex_direct_stream", "VideoQuality": 22},
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = dict(service.authority)
            confirmed = _confirmed_patch_request(
                facade,
                resolved,
                {"changes": {"VideoQuality": 24}},
            )

            first = facade.save_settings_patch(resolved, confirmed)
            retry = facade.save_settings_patch(resolved, confirmed)

        self.assertTrue(first.ok)
        self.assertTrue(retry.ok)
        self.assertTrue(retry.data["idempotent_replay"])
        self.assertEqual(retry.data["schema_version"], "desktop_settings_save_replay.v1")
        self.assertEqual(retry.data["changed_keys"], ["VideoQuality"])
        self.assertEqual(service.authority["VideoQuality"], 24)
        self.assertEqual(len(service.authority_save_calls), 1)
        self.assertFalse(retry.data["writes_config"])

    def test_settings_save_patch_durable_retry_requires_every_review_confirmation_field(self) -> None:
        required_fields = (
            "schema_version",
            "preview_id",
            "request_digest",
            "base_config_digest",
            "authority_config_digest",
            "candidate_config_digest",
            "review_entries_digest",
            "changed_keys",
            "removed_keys",
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = StatefulAuthoritySaveService(
                root,
                {"RoutingProfile": "plex_direct_stream", "VideoQuality": 22},
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = dict(service.authority)
            confirmed = _confirmed_patch_request(
                facade,
                resolved,
                {"changes": {"VideoQuality": 24}},
            )
            first = facade.save_settings_patch(resolved, confirmed)
            results = []
            for missing_field in required_fields:
                partial = dict(confirmed)
                partial_confirmation = dict(confirmed["review_confirmation"])
                partial_confirmation.pop(missing_field)
                partial["review_confirmation"] = partial_confirmation
                with self.subTest(missing_field=missing_field):
                    results.append(facade.save_settings_patch(resolved, partial))
            for tampered_field, tampered_value in (
                ("preview_id", "0" * 64),
                ("base_config_digest", "1" * 64),
                ("review_entries_digest", "2" * 64),
                ("changed_keys", ["RoutingProfile", "VideoQuality"]),
            ):
                tampered = dict(confirmed)
                tampered_confirmation = dict(confirmed["review_confirmation"])
                tampered_confirmation[tampered_field] = tampered_value
                tampered["review_confirmation"] = tampered_confirmation
                with self.subTest(tampered_field=tampered_field):
                    results.append(facade.save_settings_patch(resolved, tampered))

        self.assertTrue(first.ok)
        self.assertTrue(all(not result.ok for result in results))
        self.assertTrue(all(result.data.get("writes_config") is False for result in results))
        self.assertEqual(len(service.authority_save_calls), 1)

    def test_settings_save_patch_conflict_response_is_digest_only_and_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = StatefulAuthoritySaveService(
                root,
                {"RoutingProfile": "plex_direct_stream", "VideoQuality": 22},
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = dict(service.authority)
            confirmed = _confirmed_patch_request(
                facade,
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}},
            )
            service.authority["VideoQuality"] = 24

            conflict = facade.save_settings_patch(resolved, confirmed)

        self.assertFalse(conflict.ok)
        self.assertEqual(
            set(conflict.data),
            {
                "schema_version",
                "conflict",
                "refresh_required",
                "expected_authority_digest",
                "current_authority_digest",
                "candidate_config_digest",
                "writes_config",
            },
        )
        self.assertTrue(conflict.data["conflict"])
        self.assertFalse(conflict.data["writes_config"])
        self.assertEqual(service.authority_save_calls, [])
        self.assertNotIn("RoutingProfile", json.dumps(conflict.data, sort_keys=True))
        self.assertNotIn("VideoQuality", json.dumps(conflict.data, sort_keys=True))

    def test_settings_psd1_import_preview_is_read_only_and_apply_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = ImportSettingsService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            preview = facade.preview_settings_psd1_import(resolved)
            denied = facade.import_settings_psd1(resolved, {"confirm_import": "true"})
            applied = facade.import_settings_psd1(resolved, {"confirm_import": True})

        self.assertTrue(preview.ok)
        self.assertFalse(preview.data["writes_config"])
        self.assertFalse(denied.ok)
        self.assertIn("confirm_import must be true", "\n".join(denied.warnings))
        self.assertTrue(applied.ok)
        self.assertTrue(applied.data["writes_store"])
        self.assertEqual(service.import_calls, 1)

    def test_settings_patch_rejects_noncanonical_known_key_spelling(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}

            canonical = facade.preview_settings_patch(resolved, {"changes": {"RoutingProfile": "plex_direct_play"}})
            case_variant = facade.preview_settings_patch(resolved, {"changes": {"routingprofile": "not-a-real-choice"}})
            remove_variant = facade.preview_settings_patch(resolved, {"changes": {}, "remove_keys": ["routingprofile"]})
            unknown = facade.preview_settings_patch(resolved, {"changes": {"UnknownExperimentalKey": "enabled"}})

        self.assertTrue(canonical.ok)
        self.assertIn("RoutingProfile", canonical.data["changed_keys"])
        self.assertFalse(case_variant.ok)
        self.assertIn("Invalid settings key: 'routingprofile'; use canonical key RoutingProfile.", "\n".join(case_variant.errors))
        self.assertNotIn("routingprofile", case_variant.data["changed_keys"])
        self.assertFalse(remove_variant.ok)
        self.assertIn("Invalid remove key: 'routingprofile'; use canonical key RoutingProfile.", "\n".join(remove_variant.errors))
        self.assertFalse(unknown.ok)
        self.assertIn("Unknown config key UnknownExperimentalKey", "\n".join(unknown.errors))
        self.assertNotIn("UnknownExperimentalKey", unknown.data["changed_keys"])

    def test_settings_patch_rejects_existing_case_duplicate_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ RoutingProfile = 'old' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {"RoutingProfile": "plex_direct_stream", "routingprofile": "plex_direct_play"}

            preview = facade.preview_settings_patch(resolved, {"changes": {"SizeGuardMode": "advisory"}})
            saved = facade.save_settings_patch(resolved, {"changes": {"SizeGuardMode": "advisory"}, "confirm_save": True})

        self.assertFalse(preview.ok)
        self.assertIn("use canonical key RoutingProfile", "\n".join(preview.errors))
        self.assertIn("duplicate keys for RoutingProfile", "\n".join(preview.errors))
        self.assertFalse(saved.ok)
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_patch_reports_existing_ocr_blocker_on_unrelated_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            original_text = "@{ RoutingProfile = 'plex_direct_stream' }\n"
            config_path.write_text(original_text, encoding="utf-8")
            service = DummyFacadeService(root)
            service.validate_config_values = lambda values: validate_config_values(
                values,
                normalized_path_key=_path_key,
                path_within_root=_path_within_root,
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = _valid_config_values()
            resolved.config_data["ConvertBdpgsToSrt"] = True
            resolved.config_data["BdpgsOcrToolPath"] = " "

            preview = facade.preview_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}},
            )
            saved = facade.save_settings_patch(
                resolved,
                _confirmed_patch_request(facade, resolved, {"changes": {"RoutingProfile": "plex_direct_play"}}),
            )
            saved_document_text = config_path.read_text(encoding="utf-8")

        self.assertFalse(preview.ok)
        self.assertIn("ConvertBdpgsToSrt requires BdpgsOcrToolPath.", "\n".join(preview.errors))
        self.assertIn("RoutingProfile", preview.data["changed_keys"])
        self.assertFalse(saved.ok)
        self.assertIn("ConvertBdpgsToSrt requires BdpgsOcrToolPath.", "\n".join(saved.errors))
        self.assertEqual(service.saved_config_calls, [])
        self.assertEqual(saved_document_text, original_text)

    def test_settings_patch_preview_and_save_allow_missing_defaulted_network_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ RoutingProfile = 'plex_direct_stream' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            service.validate_config_values = lambda values: validate_config_values(
                values,
                normalized_path_key=_path_key,
                path_within_root=_path_within_root,
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = _valid_config_values()
            resolved.config_data.pop("CoordinatorMaxJobRetries")

            preview = facade.preview_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}},
            )
            saved = facade.save_settings_patch(
                resolved,
                _confirmed_patch_request(facade, resolved, {"changes": {"RoutingProfile": "plex_direct_play"}}),
            )

        self.assertTrue(preview.ok, preview.errors)
        self.assertNotIn("CoordinatorMaxJobRetries must be an integer.", "\n".join(preview.errors))
        self.assertTrue(saved.ok, saved.errors)
        self.assertNotIn("CoordinatorMaxJobRetries must be an integer.", "\n".join(saved.errors))

    def test_settings_save_patch_rejects_relative_root_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            original_text = "@{ SourceMovies = 'C:\\Media\\Movies' }\n"
            config_path.write_text(original_text, encoding="utf-8")
            service = DummyFacadeService(root)
            service.validate_config_values = lambda values: validate_config_values(
                values,
                normalized_path_key=_path_key,
                path_within_root=_path_within_root,
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = _valid_config_values()

            saved = facade.save_settings_patch(resolved, {"changes": {"SourceMovies": "Movies"}, "confirm_save": True})
            saved_document_text = config_path.read_text(encoding="utf-8")

        self.assertFalse(saved.ok)
        self.assertIn("SourceMovies must be an absolute path.", "\n".join(saved.errors))
        self.assertEqual(service.saved_config_calls, [])
        self.assertEqual(saved_document_text, original_text)

    def test_settings_redacted_diff_logs_psd1_serialization_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)

            def fail_serialize(_values: dict) -> str:
                raise RuntimeError("serializer offline")

            service.serialize_psd1_document = fail_serialize  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            with self.assertLogs("test_application_facade", level="WARNING") as logs:
                text = facade._redacted_settings_text(facade._redacted_config({"Token": "secret", "A": 1}))

        self.assertIn('"A": 1', text)
        self.assertIn('"Token": "<redacted>"', text)
        self.assertIn("Settings PSD1 serialization failed for redacted diff", "\n".join(logs.output))
        self.assertIn("serializer offline", "\n".join(logs.output))

    def test_settings_patch_preview_reports_risky_settings(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "AllowNoAudio": False,
                "AllowSystemTools": False,
                "SizeGuardMode": "advisory",
                "DropBdpgsAfterConversion": False,
                "OutputContainer": "mkv",
                "ReprocessAll": False,
                "EncodeTuningPreset": "balanced_nvenc",
                "ExtraVideoFlags": [],
            }

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "AllowNoAudio": True,
                        "AllowSystemTools": True,
                        "SizeGuardMode": "off",
                        "DropBdpgsAfterConversion": True,
                        "OutputContainer": "mp4",
                        "ReprocessAll": True,
                        "EncodeTuningPreset": "custom_legacy_flags",
                        "ExtraVideoFlags": ["-spatial-aq", "1"],
                    }
                },
            )

        self.assertTrue(preview.ok)
        self.assertEqual(preview.severity, "warning")
        summary = preview.data["risk_summary"]
        self.assertEqual(summary["schema_version"], "settings_patch_risk_summary.v1")
        self.assertEqual(summary["highest_severity"], "high")
        self.assertGreaterEqual(summary["counts"]["high"], 3)
        self.assertTrue(any(item["code"] == "no_audio_allowed" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "system_tool_fallback" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "size_guard_disabled" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "full_reprocess_enabled" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "custom_video_flags_enabled" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "raw_video_flags_present" for item in summary["items"]))
        self.assertIn("Settings risk", "\n".join(preview.warnings))

    def test_settings_patch_preview_rejects_new_unknown_config_key(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}
            preview = facade.preview_settings_patch(resolved, {"changes": {"UnknownExperimentalKey": "enabled"}})
        self.assertFalse(preview.ok)
        self.assertIn("Unknown config key UnknownExperimentalKey", "\n".join(preview.errors))
        self.assertNotIn("UnknownExperimentalKey", preview.data["changed_keys"])
        self.assertFalse(any(item["code"] == "unknown_key" for item in preview.data["risk_summary"]["items"]))

    def test_settings_save_patch_rejects_new_unknown_config_key_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            original_text = "@{ RoutingProfile = 'plex_direct_stream' }\n"
            config_path.write_text(original_text, encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}
            saved = facade.save_settings_patch(resolved, {"changes": {"UnknownExperimentalKey": "enabled"}, "confirm_save": True})
            saved_document_text = config_path.read_text(encoding="utf-8")
        self.assertFalse(saved.ok)
        self.assertIn("Unknown config key UnknownExperimentalKey", "\n".join(saved.errors))
        self.assertEqual(service.saved_config_calls, [])
        self.assertEqual(saved_document_text, original_text)

    def test_settings_patch_rejects_existing_unknown_key_edits_and_removals(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream", "LegacyUnknownKey": "keep"}
            edited = facade.preview_settings_patch(resolved, {"changes": {"LegacyUnknownKey": "changed"}})
            removed = facade.preview_settings_patch(resolved, {"changes": {}, "remove_keys": ["LegacyUnknownKey"]})
        self.assertFalse(edited.ok)
        self.assertFalse(removed.ok)
        self.assertIn("Unknown config key LegacyUnknownKey", "\n".join(edited.errors))
        self.assertIn("Unknown config key LegacyUnknownKey", "\n".join(removed.errors))
        self.assertNotIn("LegacyUnknownKey", edited.data["changed_keys"])
        self.assertNotIn("LegacyUnknownKey", removed.data["removed_keys"])

    def test_settings_patch_remove_keys_rejects_unknown_and_removes_known_key(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream", "RenameMovieRemoveTerms": ["sample"]}
            known = facade.preview_settings_patch(resolved, {"changes": {}, "remove_keys": ["RenameMovieRemoveTerms"]})
            unknown = facade.preview_settings_patch(resolved, {"changes": {}, "remove_keys": ["UnknownExperimentalKey"]})
        self.assertTrue(known.ok)
        self.assertIn("RenameMovieRemoveTerms", known.data["removed_keys"])
        self.assertFalse(unknown.ok)
        self.assertIn("Unknown config key UnknownExperimentalKey", "\n".join(unknown.errors))
        self.assertNotIn("UnknownExperimentalKey", unknown.data["removed_keys"])

    def test_settings_save_patch_preserves_existing_unknown_keys_when_saving_known_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ RoutingProfile = 'old'; LegacyUnknownKey = 'keep' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {"RoutingProfile": "plex_direct_stream", "LegacyUnknownKey": "keep"}
            preview = facade.preview_settings_patch(resolved, {"changes": {"RoutingProfile": "plex_direct_play"}})
            saved = facade.save_settings_patch(
                resolved,
                _confirmed_patch_request(facade, resolved, {"changes": {"RoutingProfile": "plex_direct_play"}}),
            )
            saved_document_text = config_path.read_text(encoding="utf-8")
            self.assertTrue(preview.ok)
            self.assertEqual(preview.data["preserved_unknown_keys"], ["LegacyUnknownKey"])
            self.assertIn("Existing unknown config key LegacyUnknownKey is preserved but not validated.", preview.warnings)
            self.assertTrue(saved.ok)
            self.assertEqual(saved.data["preserved_unknown_keys"], ["LegacyUnknownKey"])
            self.assertIn("Existing unknown config key LegacyUnknownKey is preserved but not validated.", saved.warnings)
            saved_values = service.saved_config_calls[-1]["config_values"]
            self.assertEqual(saved_values["LegacyUnknownKey"], "keep")
            self.assertIn("LegacyUnknownKey = 'keep'", saved_document_text)

    def test_settings_save_patch_rejects_source_mutation_key_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            original_text = "@{ RoutingProfile = 'plex_direct_stream' }\n"
            config_path.write_text(original_text, encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}
            saved = facade.save_settings_patch(resolved, {"changes": {"DeleteSourceAfterProcessing": True}, "confirm_save": True})
            self.assertFalse(saved.ok)
            self.assertIn("source/original-file mutation", "\n".join(saved.errors))
            self.assertEqual(service.saved_config_calls, [])
            self.assertEqual(config_path.read_text(encoding="utf-8"), original_text)

    def test_settings_patch_preview_treats_queue_and_show_policy_keys_as_known_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {}

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "MixPriorityPhase": True,
                        "QueueOrderingStrategy": "ManualOrder",
                        "ShowOverrides": {"Example Show": {"VideoCodec": "hevc_nvenc"}},
                    }
                },
            )

        self.assertTrue(preview.ok)
        self.assertEqual(
            sorted(preview.data["changed_keys"]),
            ["MixPriorityPhase", "QueueOrderingStrategy", "ShowOverrides"],
        )
        self.assertFalse(any(item["code"] == "unknown_key" for item in preview.data["risk_summary"]["items"]))

    def test_settings_patch_preview_reports_pending_publish_recovery_risks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "DeferredPublish": False,
                "CleanupRemoteStaging": False,
                "TransientFailureRetryLimit": 3,
                "RobocopyTimeoutSeconds": 14400,
            }

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "DeferredPublish": True,
                        "CleanupRemoteStaging": True,
                        "TransientFailureRetryLimit": 12,
                        "RobocopyTimeoutSeconds": 120,
                    }
                },
            )

        self.assertTrue(preview.ok)
        summary = preview.data["risk_summary"]
        codes = {item["code"] for item in summary["items"]}
        self.assertIn("pending_publish_monitor_required", codes)
        self.assertIn("remote_staging_cleanup_enabled", codes)
        self.assertIn("high_transient_retry_limit", codes)
        self.assertIn("short_copy_timeout", codes)
        self.assertEqual(summary["highest_severity"], "medium")
        self.assertIn("remote_staging_cleanup_enabled", "\n".join(preview.warnings))

    def test_settings_patch_preview_reports_audio_subtitle_policy_risks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "PreferredDefaultAudioLanguages": ["english"],
                "CompatibleAudioCodecs": ["aac", "ac3", "eac3"],
                "AudioPassthroughProfile": "plex_balanced",
                "AudioDownmixMode": "max_channels",
                "AudioMaxChannels": 6,
                "SubKeepLanguages": ["eng", "und"],
                "ConvertTx3gToSrt": True,
                "ConvertBdpgsToSrt": True,
            }

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "PreferredDefaultAudioLanguages": [],
                        "CompatibleAudioCodecs": [],
                        "AudioPassthroughProfile": "lossless_passthrough",
                        "AudioDownmixMode": "stereo",
                        "AudioMaxChannels": 2,
                        "SubKeepLanguages": [],
                        "ConvertTx3gToSrt": False,
                        "ConvertBdpgsToSrt": False,
                    }
                },
            )

        self.assertTrue(preview.ok)
        summary = preview.data["risk_summary"]
        codes = {item["code"] for item in summary["items"]}
        self.assertIn("empty_default_audio_languages", codes)
        self.assertIn("empty_audio_passthrough_codecs", codes)
        self.assertIn("lossless_audio_passthrough_profile", codes)
        self.assertIn("forced_stereo_downmix", codes)
        self.assertIn("low_audio_channel_cap", codes)
        self.assertIn("empty_subtitle_keep_languages", codes)
        self.assertIn("tx3g_srt_conversion_disabled", codes)
        self.assertIn("bdpgs_srt_conversion_disabled", codes)
        self.assertEqual(summary["highest_severity"], "medium")
        self.assertIn("PreferredDefaultAudioLanguages is empty", "\n".join(preview.warnings))

    def test_settings_save_patch_requires_confirmation_writes_backup_and_preserves_secret(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ RoutingProfile = 'old' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "CoordinatorAuthToken": "secret-token",
            }

            rejected = facade.save_settings_patch(resolved, {"changes": {"RoutingProfile": "plex_direct_play"}})
            unreviewed = facade.save_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}, "confirm_save": True},
            )
            tampered_request = _confirmed_patch_request(
                facade,
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}},
            )
            tampered_request["review_confirmation"] = {
                **dict(tampered_request["review_confirmation"]),
                "preview_id": "stale-preview-id",
            }
            tampered = facade.save_settings_patch(resolved, tampered_request)
            saved = facade.save_settings_patch(
                resolved,
                _confirmed_patch_request(facade, resolved, {"changes": {"RoutingProfile": "plex_direct_play"}}),
            )
            secret_rejected = facade.save_settings_patch(
                resolved,
                {"changes": {"CoordinatorAuthToken": "<redacted>"}, "confirm_save": True},
            )
            real_secret_rejected = facade.save_settings_patch(
                resolved,
                {"changes": {"CoordinatorAuthToken": "new-coordinator-secret"}, "confirm_save": True},
            )
            worker_secret_rejected = facade.save_settings_patch(
                resolved,
                {"changes": {"WorkerAuthToken": "new-worker-secret"}, "confirm_save": True},
            )

            self.assertFalse(rejected.ok)
            self.assertIn("confirmation", rejected.message)
            self.assertFalse(unreviewed.ok)
            self.assertIn("review_confirmation", "\n".join(unreviewed.warnings))
            self.assertFalse(tampered.ok)
            self.assertIn("review_confirmation", "\n".join(tampered.warnings))
            self.assertTrue(saved.ok)
            self.assertEqual(saved.command, "settings.save_patch")
            self.assertTrue(saved.data["writes_config"])
            self.assertEqual(saved.data["review_entries_schema_version"], "desktop_settings_patch_review_entries.v1")
            self.assertEqual(saved.data["save_verification"]["config_digest_written"], saved.data["config_digest_written"])
            self.assertIn("RoutingProfile", saved.data["changed_keys"])
            self.assertEqual(saved.data["risk_summary"]["total_count"], 0)
            self.assertTrue(saved.data["backup_path"])
            self.assertEqual(saved.data["settings_progress"]["schema_version"], "desktop_settings_save_reload_progress.v1")
            self.assertEqual(saved.data["progress_bars"][0]["id"], "settings_save_reload")
            self.assertEqual(saved.data["progress_bars"][0]["percent"], 60.0)
            self.assertEqual(service.saved_config_calls[-1]["config_values"]["CoordinatorAuthToken"], "secret-token")
            self.assertIn("plex_direct_play", config_path.read_text(encoding="utf-8"))
            for secret_result in (secret_rejected, real_secret_rejected, worker_secret_rejected):
                self.assertFalse(secret_result.ok)
                self.assertIn("cannot be changed through Settings Patch", "\n".join(secret_result.errors))
            secret_results = json.dumps(
                [secret_rejected.to_mapping(), real_secret_rejected.to_mapping(), worker_secret_rejected.to_mapping()],
                sort_keys=True,
            )
            self.assertNotIn("new-coordinator-secret", secret_results)
            self.assertNotIn("new-worker-secret", secret_results)
            self.assertEqual(len(service.saved_config_calls), 1)

    def test_settings_save_patch_uses_backend_save_lock_before_candidate_build(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}

            self.assertTrue(facade._settings_save_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                result = facade.save_settings_patch(
                    resolved,
                    {"changes": {"RoutingProfile": "plex_direct_play"}, "confirm_save": True},
                )
            finally:
                facade._settings_save_lock.release()  # type: ignore[attr-defined]

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "settings.save_patch")
        self.assertEqual(result.severity, "warning")
        self.assertIn("another settings save command is already in progress", result.message)
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_save_patch_blocks_unverified_active_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}
            resolved.config_identity = {
                "schema_version": "desktop_config_identity.v1",
                "blocks_operations": True,
                "operator_status": "Config requires recovery",
                "reasons": ["Active config matches the deployment template/default paths."],
            }

            result = facade.save_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}, "confirm_save": True},
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "settings.save_patch")
        self.assertEqual(result.severity, "error")
        self.assertIn("not a verified operator config", result.message)
        self.assertFalse(result.data["writes_config"])
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_patch_same_value_is_not_treated_as_changed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ RoutingProfile = 'plex_direct_stream' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}

            preview = facade.preview_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_stream"}},
            )
            saved = facade.save_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_stream"}, "confirm_save": True},
            )

        self.assertTrue(preview.ok)
        self.assertEqual(preview.data["changed_keys"], [])
        self.assertEqual(preview.data["redacted_diff_lines"], [])
        self.assertIn("no changes", preview.message)
        self.assertFalse(saved.ok)
        self.assertIn("no changes", saved.message)
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_patch_filters_library_profiles_after_backend_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ LibraryProfiles = @() }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path

            raw_profiles = [
                {
                    "id": "movies",
                    "name": "Movies",
                    "designation": "movie",
                    "source_path": r"C:\Incoming\Movies",
                    "output_path": r"D:\Processed",
                    "default_tracking": {
                        "schema_version": "library_profile_default_tracking.v1",
                        "inherited_fields": ["source_path"],
                        "field_default_keys": {
                            "source_path": "SourceMovies",
                            "output_path": "Outsource",
                        },
                    },
                },
                {
                    "id": "tv",
                    "name": "TV",
                    "designation": "tv",
                    "source_path": r"C:\Incoming\TV",
                    "output_path": r"D:\Processed",
                    "default_tracking": {
                        "schema_version": "library_profile_default_tracking.v1",
                        "inherited_fields": ["source_path"],
                        "field_default_keys": {
                            "source_path": "SourceTV",
                            "output_path": "Outsource",
                        },
                    },
                },
            ]
            resolved.config_data = normalize_library_profile_config_values(
                {
                    "SourceMovies": r"C:\Incoming\Movies",
                    "SourceTV": r"C:\Incoming\TV",
                    "Outsource": r"D:\Processed",
                    "LibraryProfiles": raw_profiles,
                },
                require_profiles=True,
            )
            request = {"changes": {"LibraryProfiles": raw_profiles}}

            preview = facade.preview_settings_patch(resolved, request)
            saved = facade.save_settings_patch(
                resolved,
                {**request, "confirm_save": True},
            )

        self.assertTrue(preview.ok)
        self.assertEqual(preview.data["changed_keys"], [])
        self.assertEqual(preview.data["redacted_diff_lines"], [])
        self.assertIn("no changes", preview.message)
        self.assertFalse(saved.ok)
        self.assertIn("no changes", saved.message)
        self.assertEqual(service.saved_config_calls, [])

    def test_library_profile_fixture_corpus_round_trips_after_normalization(self) -> None:
        fixture = json.loads(LIBRARY_PROFILE_ROUND_TRIP_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["schema_version"], "settings_library_profiles_round_trip_cases.v1")
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                input_config = json.loads(json.dumps(case["input_config"]))
                normalized = normalize_library_profile_config_values(input_config, require_profiles=True)
                renormalized = normalize_library_profile_config_values(
                    json.loads(json.dumps(normalized)),
                    require_profiles=True,
                )
                self.assertEqual(
                    json.dumps(normalized, sort_keys=True),
                    json.dumps(renormalized, sort_keys=True),
                )
                if "expected_profile_ids" in case:
                    self.assertEqual(
                        [profile["id"] for profile in normalized["LibraryProfiles"]],
                        case["expected_profile_ids"],
                    )
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    service = DummyFacadeService(root)
                    facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
                    resolved = _resolved(root)
                    resolved.config_data = normalized

                    preview = facade.preview_settings_patch(
                        resolved,
                        {"changes": {"LibraryProfiles": normalized["LibraryProfiles"]}},
                    )
                    self.assertTrue(preview.ok, preview.errors)
                    self.assertEqual(preview.data["changed_keys"], [])

                    if case.get("reset_request"):
                        reset_preview = facade.preview_settings_patch(
                            resolved,
                            {"changes": {}, "library_profile_resets": case["reset_request"]},
                        )
                        self.assertTrue(reset_preview.ok, reset_preview.errors)
                        self.assertIn("LibraryProfiles", reset_preview.data["changed_keys"])
                        state_by_id = {
                            state["library_id"]: state
                            for state in reset_preview.data["library_profile_state"]
                        }
                        for library_id, fields in case["expected_inherited_fields"].items():
                            for field in fields:
                                self.assertEqual(
                                    state_by_id[library_id]["path_fields"][field]["state"],
                                    "inherited",
                                )

    def test_settings_patch_review_entries_include_library_profile_mirrored_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "SourceMovies": r"C:\OldMovies",
                "SourceTV": r"C:\OldTV",
                "Outsource": r"D:\Processed",
                "LibraryProfiles": [
                    {
                        "id": "movies",
                        "name": "Movies",
                        "designation": "movie",
                        "source_path": r"C:\OldMovies",
                        "output_path": r"D:\Processed",
                    },
                    {
                        "id": "tv",
                        "name": "TV",
                        "designation": "tv",
                        "source_path": r"C:\OldTV",
                        "output_path": r"D:\Processed",
                    },
                ],
            }
            request = {
                "changes": {
                    "LibraryProfiles": [
                        {
                            "id": "movies",
                            "name": "Movies",
                            "designation": "movie",
                            "source_path": r"E:\NewMovies",
                            "output_path": r"D:\Processed",
                        },
                        {
                            "id": "tv",
                            "name": "TV",
                            "designation": "tv",
                            "source_path": r"C:\OldTV",
                            "output_path": r"D:\Processed",
                        },
                    ]
                }
            }

            preview = facade.preview_settings_patch(resolved, request)

        self.assertTrue(preview.ok)
        self.assertEqual(preview.data["changed_keys"], ["LibraryProfiles", "SourceMovies"])
        entries = {entry["key"]: entry for entry in preview.data["review_entries"]}
        self.assertEqual(entries["SourceMovies"]["source"], "mirrored_from_library_profiles")
        self.assertEqual(entries["SourceMovies"]["current_value"], r"C:\OldMovies")
        self.assertIsNone(entries["SourceMovies"]["submitted_value"])
        self.assertEqual(entries["SourceMovies"]["new_value"], r"E:\NewMovies")
        self.assertEqual(entries["LibraryProfiles"]["source"], "submitted")

    def test_movie_profile_alias_save_keeps_canonical_id_and_size_guard_override(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ LibraryProfiles = @() }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {
                "SourceMovies": r"C:\Incoming\Movies",
                "SourceTV": r"C:\Incoming\TV",
                "Outsource": r"D:\Processed",
                "SizeGuardMode": "advisory",
                "LibraryProfiles": [
                    {
                        "id": "movies",
                        "name": "Movies",
                        "designation": "movie",
                        "source_path": r"C:\Incoming\Movies",
                        "output_path": r"D:\Processed",
                        "overrides": {"editor": {}, "video": {}, "subtitles": {}, "audio": {}},
                    },
                    {
                        "id": "tv",
                        "name": "TV",
                        "designation": "tv",
                        "source_path": r"C:\Incoming\TV",
                        "output_path": r"D:\Processed",
                        "overrides": {"editor": {}, "video": {}, "subtitles": {}, "audio": {}},
                    },
                ],
            }
            request = {
                "changes": {
                    "LibraryProfiles": [
                        {
                            "id": "movie",
                            "name": "Movies",
                            "designation": "movie",
                            "source_path": r"C:\Incoming\Movies",
                            "output_path": r"D:\Processed",
                            "overrides": {
                                "editor": {"SizeGuardMode": "fallback_remux"},
                                "video": {},
                                "subtitles": {},
                                "audio": {},
                            },
                        },
                        {
                            "id": "tv",
                            "name": "TV",
                            "designation": "tv",
                            "source_path": r"C:\Incoming\TV",
                            "output_path": r"D:\Processed",
                            "overrides": {"editor": {}, "video": {}, "subtitles": {}, "audio": {}},
                        },
                    ]
                }
            }

            preview = facade.preview_settings_patch(resolved, request)
            saved = facade.save_settings_patch(resolved, _confirmed_patch_request(facade, resolved, request))

        self.assertTrue(preview.ok, preview.errors)
        self.assertEqual(preview.data["changed_keys"], ["LibraryProfiles"])
        preview_profiles = {profile["id"]: profile for profile in preview.data["review_entries"][0]["new_value"]}
        self.assertIn("movies", preview_profiles)
        self.assertNotIn("movie", preview_profiles)
        self.assertEqual(preview_profiles["movies"]["overrides"]["editor"]["SizeGuardMode"], "fallback_remux")
        self.assertTrue(saved.ok, saved.errors)
        saved_profiles = {profile["id"]: profile for profile in service.saved_config_calls[-1]["config_values"]["LibraryProfiles"]}
        self.assertIn("movies", saved_profiles)
        self.assertNotIn("movie", saved_profiles)
        self.assertEqual(saved_profiles["movies"]["overrides"]["editor"]["SizeGuardMode"], "fallback_remux")

    def test_library_profile_resets_preview_and_save_remove_explicit_state_without_copying_globals(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ LibraryProfiles = @() }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {
                "SourceMovies": r"C:\Incoming\Movies",
                "SourceTV": r"C:\Incoming\TV",
                "Outsource": r"D:\Processed",
                "RoutingProfile": "plex_direct_stream",
                "VideoPreset": "p5",
                "ConvertVobSubToSrt": False,
                "LibraryProfiles": [
                    {
                        "id": "movies",
                        "designation": "movie",
                        "source_path": r"C:\Incoming\Movies",
                        "output_path": r"D:\Processed",
                        "overrides": {
                            "editor": {"RoutingProfile": "manual"},
                            "video": {"VideoPreset": "p5"},
                            "subtitles": {"ConvertVobSubToSrt": True},
                            "audio": {},
                        },
                    },
                    {
                        "id": "concerts",
                        "designation": "auto",
                        "source_path": r"F:\Concerts",
                        "output_path": r"G:\ConcertsProcessed",
                    },
                ],
            }
            request = {
                "changes": {},
                "library_profile_resets": [
                    {
                        "library_id": "movies",
                        "overrides": {
                            "editor": ["RoutingProfile"],
                            "video": ["VideoPreset"],
                            "subtitles": ["ConvertVobSubToSrt"],
                        },
                    },
                    {"library_id": "concerts", "path_fields": ["output_path"]},
                ],
            }

            preview = facade.preview_settings_patch(resolved, request)
            saved = facade.save_settings_patch(resolved, _confirmed_patch_request(facade, resolved, request))

        self.assertTrue(preview.ok)
        self.assertIn("LibraryProfiles", preview.data["changed_keys"])
        state_by_id = {state["library_id"]: state for state in preview.data["library_profile_state"]}
        self.assertEqual(state_by_id["concerts"]["path_fields"]["output_path"]["state"], "inherited")
        self.assertTrue(saved.ok)
        profiles = {profile["id"]: profile for profile in service.saved_config_calls[-1]["config_values"]["LibraryProfiles"]}
        movie = profiles["movies"]
        concerts = profiles["concerts"]
        self.assertNotIn("RoutingProfile", movie["overrides"]["editor"])
        self.assertNotIn("VideoPreset", movie["overrides"]["video"])
        self.assertNotIn("ConvertVobSubToSrt", movie["overrides"]["subtitles"])
        self.assertEqual(concerts["output_path"], r"D:\Processed")
        self.assertIn("output_path", concerts["default_tracking"]["inherited_fields"])
        self.assertEqual(concerts["default_tracking"]["field_default_keys"]["output_path"], "Outsource")
