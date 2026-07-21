from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mediapipeline.tools.paths import find_repo_root

from mediapipeline.core.config.load import load_psd1_mapping, serialize_psd1_document
from mediapipeline.core.config.settings_patch_policy import settings_config_digest
from mediapipeline.core.config.settings_store import (
    SETTINGS_PROJECTION_SCHEMA_VERSION,
    SETTINGS_STORE_SCHEMA_VERSION,
    SettingsStoreError,
    import_psd1_settings_preview_for_service,
    load_settings_authority_for_service,
    migrate_imported_settings_mapping,
    save_settings_authority_for_service,
)
from mediapipeline.core.kernel.config_locations import (
    SETTINGS_PROJECTION_NAME,
    SETTINGS_STORE_NAME,
    PER_USER_APP_DIR_NAME,
)
from mediapipeline.desktop.models import ConfigSaveResult, ResolvedPaths


REPO_ROOT = find_repo_root(Path(__file__))
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "settings_store"


class _StoreDummyService:
    def __init__(self) -> None:
        self.saved_config_calls: list[dict[str, object]] = []
        self.validation_errors: list[str] = []
        self.fail_save = False

    def serialize_psd1_document(self, values: dict) -> str:
        return serialize_psd1_document(values)

    def validate_config_document_for_save(
        self,
        document_text: str,
        *,
        config_values: dict | None = None,
        powershell_host: str | None = None,
    ) -> tuple[list[str], list[str]]:
        _ = document_text, config_values, powershell_host
        return list(self.validation_errors), []

    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult:
        self.saved_config_calls.append(
            {
                "output_path": output_path,
                "document_text": document_text,
                "create_backup": create_backup,
                "config_values": dict(config_values or {}),
                "powershell_host": powershell_host,
            }
        )
        if self.fail_save:
            raise RuntimeError("projection write failed")
        backup_path = output_path.with_suffix(".backup.psd1") if create_backup and output_path.exists() else None
        if backup_path is not None:
            backup_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document_text, encoding="utf-8")
        return ConfigSaveResult(output_path=output_path, backup_path=backup_path)


def _resolved(root: Path, config_path: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "MediaPipeline.ps1",
        config_path=config_path,
        audit_script_path=root / "Audit.ps1",
        rerun_script_path=root / "Rerun.ps1",
        powershell_host="pwsh",
    )


def _loader(mapping: dict[str, object]):
    def load(_path: Path, _host: str | None) -> dict[str, object]:
        return dict(mapping)

    return load


def _source_then_projection_loader(mapping: dict[str, object]):
    def load(path: Path, host: str | None) -> dict[str, object]:
        if path.name == "candidate.psd1":
            result = load_psd1_mapping(path, host)
            if not result.ok:
                raise AssertionError(result.error)
            return dict(result.data)
        return dict(mapping)

    return load


def _store_paths(root: Path) -> tuple[Path, Path]:
    user_root = root / "LocalAppData" / PER_USER_APP_DIR_NAME
    return user_root / SETTINGS_STORE_NAME, user_root / SETTINGS_PROJECTION_NAME


class SettingsStoreTests(unittest.TestCase):
    def test_missing_json_imports_psd1_and_writes_canonical_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "MediaPipeline_config.psd1"
            config_path.write_text((FIXTURE_ROOT / "unknown_legacy_extras.psd1").read_text(encoding="utf-8"), encoding="utf-8")
            store_path, projection_path = _store_paths(root)
            mapping = {
                "ConfigSchemaVersion": 1,
                "SourceMovies": r"C:\Media\Movies",
                "SourceTV": r"C:\Media\TV",
                "Outsource": r"D:\MediaOut",
                "LocalBase": r"E:\MediaScratch",
                "RoutingProfile": "plex_direct_stream",
                "LegacyLabOnlyToggle": "keep-for-projection",
            }

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                loaded = load_settings_authority_for_service(
                    _StoreDummyService(),
                    config_path,
                    "pwsh",
                    psd1_loader=_source_then_projection_loader(mapping),
                )

            envelope = json.loads(store_path.read_text(encoding="utf-8"))
            projection = json.loads(projection_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["SourceMovies"], r"C:\Media\Movies")
            self.assertEqual(envelope["schema_version"], SETTINGS_STORE_SCHEMA_VERSION)
            self.assertEqual(envelope["legacy_extras"], {"LegacyLabOnlyToggle": "keep-for-projection"})
            self.assertIn("CoordinatorMaxJobRetries", envelope["settings"])
            self.assertEqual(projection["schema_version"], SETTINGS_PROJECTION_SCHEMA_VERSION)
            self.assertEqual(projection["legacy_extras_count"], 1)

    def test_existing_json_wins_over_psd1_drift_and_reports_projection_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "MediaPipeline_config.psd1"
            config_path.write_text("@{ RoutingProfile = 'manual-edit' }\n", encoding="utf-8")
            store_path, _projection_path = _store_paths(root)
            store_path.parent.mkdir(parents=True)
            store_path.write_text(
                json.dumps(
                    {
                        "schema_version": SETTINGS_STORE_SCHEMA_VERSION,
                        "config_schema_version": 1,
                        "settings": {
                            "ConfigSchemaVersion": 1,
                            "SourceMovies": r"C:\Json\Movies",
                            "SourceTV": r"C:\Json\TV",
                            "Outsource": r"D:\JsonOut",
                            "LocalBase": r"E:\JsonScratch",
                            "RoutingProfile": "plex_direct_play",
                        },
                        "legacy_extras": {},
                        "migrations_applied": [],
                        "source_psd1_path": str(config_path),
                        "source_psd1_sha256": "old",
                        "updated_at_utc": "2026-06-23T00:00:00Z",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                loaded = load_settings_authority_for_service(
                    _StoreDummyService(),
                    config_path,
                    "pwsh",
                    psd1_loader=_source_then_projection_loader({"RoutingProfile": "manual-edit"}),
                )

            self.assertEqual(loaded["RoutingProfile"], "plex_direct_play")
            self.assertIn("plex_direct_play", config_path.read_text(encoding="utf-8"))
            self.assertNotIn("manual-edit", config_path.read_text(encoding="utf-8"))

    def test_invalid_json_restores_last_good_or_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "MediaPipeline_config.psd1"
            store_path, _projection_path = _store_paths(root)
            last_good = store_path.parent / "ConfigSnapshots" / SETTINGS_STORE_NAME
            store_path.parent.mkdir(parents=True)
            store_path.write_text("{not-json", encoding="utf-8")
            last_good.parent.mkdir(parents=True)
            last_good.write_text(
                json.dumps(
                    {
                        "schema_version": SETTINGS_STORE_SCHEMA_VERSION,
                        "config_schema_version": 1,
                        "settings": {
                            "ConfigSchemaVersion": 1,
                            "SourceMovies": r"C:\Good\Movies",
                            "SourceTV": r"C:\Good\TV",
                            "Outsource": r"D:\GoodOut",
                            "LocalBase": r"E:\GoodScratch",
                        },
                        "legacy_extras": {},
                        "migrations_applied": [],
                        "source_psd1_path": str(config_path),
                        "source_psd1_sha256": "",
                        "updated_at_utc": "2026-06-23T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                loaded = load_settings_authority_for_service(_StoreDummyService(), config_path, "pwsh")

            self.assertEqual(loaded["SourceMovies"], r"C:\Good\Movies")
            store_path.write_text("{not-json", encoding="utf-8")
            last_good.unlink()
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                with self.assertRaises(SettingsStoreError):
                    load_settings_authority_for_service(_StoreDummyService(), config_path, "pwsh")

    def test_save_rollback_restores_json_and_psd1_when_projection_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "MediaPipeline_config.psd1"
            config_path.write_text("@{ RoutingProfile = 'old' }\n", encoding="utf-8")
            store_path, _projection_path = _store_paths(root)
            store_path.parent.mkdir(parents=True)
            old_store = {
                "schema_version": SETTINGS_STORE_SCHEMA_VERSION,
                "config_schema_version": 1,
                "settings": {
                    "ConfigSchemaVersion": 1,
                    "SourceMovies": r"C:\Old\Movies",
                    "SourceTV": r"C:\Old\TV",
                    "Outsource": r"D:\OldOut",
                    "LocalBase": r"E:\OldScratch",
                    "RoutingProfile": "old",
                },
                "legacy_extras": {},
                "migrations_applied": [],
                "source_psd1_path": str(config_path),
                "source_psd1_sha256": "",
                "updated_at_utc": "2026-06-23T00:00:00Z",
            }
            store_path.write_text(json.dumps(old_store), encoding="utf-8")
            service = _StoreDummyService()
            service.fail_save = True

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                with self.assertRaisesRegex(RuntimeError, "projection write failed"):
                    save_settings_authority_for_service(
                        service,
                        _resolved(root, config_path),
                        {
                            "ConfigSchemaVersion": 1,
                            "SourceMovies": r"C:\New\Movies",
                            "SourceTV": r"C:\New\TV",
                            "Outsource": r"D:\NewOut",
                            "LocalBase": r"E:\NewScratch",
                            "RoutingProfile": "plex_direct_play",
                        },
                        expected_authority_digest=settings_config_digest(old_store["settings"]),
                    )

            self.assertEqual(json.loads(store_path.read_text(encoding="utf-8"))["settings"]["RoutingProfile"], "old")
            self.assertEqual(config_path.read_text(encoding="utf-8"), "@{ RoutingProfile = 'old' }\n")

    def test_migration_aliases_preserve_unknowns_and_reject_case_duplicates(self) -> None:
        renamed = migrate_imported_settings_mapping(
            {
                "SourceMovies": r"C:\Media\Movies",
                "SourceTV": r"C:\Media\TV",
                "OutputRoot": r"D:\MediaOut",
                "ScratchRoot": r"E:\MediaScratch",
                "LegacyLabOnlyToggle": "keep",
            }
        )
        duplicate = migrate_imported_settings_mapping({"RoutingProfile": "plex_direct_stream", "routingprofile": "manual"})

        self.assertEqual(renamed.settings["Outsource"], r"D:\MediaOut")
        self.assertEqual(renamed.settings["LocalBase"], r"E:\MediaScratch")
        self.assertEqual(renamed.legacy_extras, {"LegacyLabOnlyToggle": "keep"})
        self.assertIn("alias:OutputRoot->Outsource", renamed.migrations_applied)
        self.assertTrue(any("duplicate keys for RoutingProfile" in error for error in duplicate.errors))

    def test_migration_reports_only_exact_legacy_movie_remove_term_normalization(self) -> None:
        defaults = ["sample", "trailer", "extras", "featurette", "deleted scenes", "behind the scenes"]
        legacy = [*defaults, *(f"{value:02d}" for value in range(1, 13))]
        exact = migrate_imported_settings_mapping(
            {"RenameMovieRemoveTerms": [term.upper() for term in reversed(legacy)]}
        )
        incomplete = migrate_imported_settings_mapping({"RenameMovieRemoveTerms": legacy[:-1]})
        extended = migrate_imported_settings_mapping(
            {"RenameMovieRemoveTerms": [*legacy, "operator custom term"]}
        )

        self.assertEqual(exact.settings["RenameMovieRemoveTerms"], defaults)
        self.assertIn("normalize:RenameMovieRemoveTerms:legacy-packaged-default", exact.migrations_applied)
        self.assertEqual(incomplete.settings["RenameMovieRemoveTerms"], legacy[:-1])
        self.assertNotIn("normalize:RenameMovieRemoveTerms:legacy-packaged-default", incomplete.migrations_applied)
        self.assertEqual(extended.settings["RenameMovieRemoveTerms"], [*legacy, "operator custom term"])
        self.assertNotIn("normalize:RenameMovieRemoveTerms:legacy-packaged-default", extended.migrations_applied)

    def test_import_preview_does_not_write_and_import_apply_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "MediaPipeline_config.psd1"
            config_path.write_text((FIXTURE_ROOT / "missing_new_keys.psd1").read_text(encoding="utf-8"), encoding="utf-8")
            store_path, _projection_path = _store_paths(root)
            mapping = {
                "ConfigSchemaVersion": 1,
                "SourceMovies": r"C:\Media\Movies",
                "SourceTV": r"C:\Media\TV",
                "Outsource": r"D:\MediaOut",
                "LocalBase": r"E:\MediaScratch",
                "RoutingProfile": "plex_direct_stream",
            }

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                preview = import_psd1_settings_preview_for_service(
                    _StoreDummyService(),
                    _resolved(root, config_path),
                    psd1_loader=_loader(mapping),
                )

            self.assertFalse(store_path.exists())
            self.assertEqual(preview["settings"]["SourceMovies"], r"C:\Media\Movies")
            self.assertIn("CoordinatorMaxJobRetries", preview["settings"])


if __name__ == "__main__":
    unittest.main()
