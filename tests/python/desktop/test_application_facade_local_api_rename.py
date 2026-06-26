from __future__ import annotations

import contextlib
import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.core.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline.desktop.api.handler import build_local_api_handler_class
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend, main as local_api_main
from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from tests.python.desktop.application_facade_test_support import (
    COMMAND_HISTORY_ASSET_ORDER,
    DummyFacadeService,
    DummyProc,
    DummyWorkflowFacadeService,
    LocalApiHttpTestMixin,
    exercise_local_api_route_workflow,
    served_webview_static_contract_bundle,
    assert_namespace_export as _assert_namespace_export,
    _render_static_index_html,
    _resolved,
)


class LocalApiRenameTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_rename_browse_resolves_dropped_folder_paths_without_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            folder = root / "Season 02"
            nested = folder / "Nested"
            nested.mkdir(parents=True)
            media_one = folder / "Ranma - S01E01.mkv"
            media_two = folder / "Ranma - S01E02.mp4"
            sidecar = folder / "Ranma - S01E01.pipeline.json"
            note = folder / "notes.txt"
            nested_media = nested / "Ranma - S01E03.mkv"
            for path in (media_one, media_two, sidecar, note, nested_media):
                path.write_text("fixture", encoding="utf-8")

            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token")

            def picker_should_not_run(**_kwargs: object) -> dict:
                raise AssertionError("dropped folder browse should not open the native picker")

            server._rename_path_picker = picker_should_not_run  # type: ignore[attr-defined]
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/rename/browse",
                    {"selection_mode": "folder_files", "paths": [str(folder)]},
                    token="rename-token",
                )
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "rename.browse")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["selection_mode"], "folder_files")
        self.assertEqual(payload["data"]["source"], "dropped_paths")
        self.assertEqual(payload["data"]["paths"], [str(media_one), str(media_two)])
        self.assertNotIn(str(folder), payload["data"]["paths"])
        self.assertNotIn(str(nested_media), payload["data"]["paths"])
        self.assertEqual(payload["data"]["raw_path_count"], 4)
        self.assertEqual(payload["data"]["ignored_path_count"], 2)
        self.assertEqual(payload["data"]["ignored_sidecar_count"], 1)

    def test_rename_clean_filename_preview_get_route_uses_backend_cleaner_without_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token")
            try:
                server.start()
                query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "filename": "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv",
                        "movie_filter_terms": json.dumps({"release_groups": ["neonoir"]}),
                    }.items()
                )
                status, payload = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{query}",
                    token="rename-token",
                )
                catalog_status, catalog = self._get_json(
                    f"{server.url}/api/rename/movie-cleaning-filters",
                    token="rename-token",
                )
                split_catalog_status, split_catalog = self._get_json(
                    f"{server.url}/api/rename/cleaning-filters",
                    token="rename-token",
                )
                tv_query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "mode": "tv",
                        "source_folder": "The Web S01 1080p WEB-DL-TTGA",
                        "filename": "S01E01-Pilot.1080p.WEB-DL-TTGA.mkv",
                        "tv_filter_terms": json.dumps({"release_groups": ["TTGA"]}),
                    }.items()
                )
                tv_status, tv_payload = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{tv_query}",
                    token="rename-token",
                )
                history_status, history = self._get_json(f"{server.url}/api/commands?limit=5", token="rename-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_rename_clean_filename_preview.v1")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["target_name"], "Together (2025).mkv")
        self.assertEqual(payload["preview_source"], "backend_movie_cleaner")
        self.assertTrue(payload["movie_filter_terms_enabled"])
        self.assertEqual(payload["movie_filter_terms_mode"], "staged")
        self.assertEqual(payload["rename_cleaning_policy_source"], "staged")
        self.assertIn("no filesystem paths", payload["mutation_boundary"])
        self.assertEqual(catalog_status, 200)
        self.assertEqual(catalog["schema_version"], "desktop_rename_movie_filter_catalog.v1")
        self.assertEqual(catalog["movie_filter_terms_mode"], "saved")
        self.assertIn("cmrg", catalog["default_terms"]["release_groups"])
        self.assertIn("neonoir", catalog["default_terms"]["release_groups"])
        self.assertEqual(split_catalog_status, 200)
        self.assertEqual(split_catalog["schema_version"], "desktop_rename_cleaning_filter_catalog.v1")
        self.assertIn("movie", split_catalog)
        self.assertIn("tv", split_catalog)
        self.assertIn("ttga", split_catalog["tv"]["default_terms"]["release_groups"])
        self.assertEqual(tv_status, 200)
        self.assertEqual(tv_payload["target_name"], "The Web - S01E01 - Pilot.mkv")
        self.assertEqual(tv_payload["preview_source"], "backend_tv_cleaner")
        self.assertEqual(tv_payload["tv_filter_terms_mode"], "staged")
        self.assertEqual(history_status, 200)
        self.assertEqual(history["entries"], [])

    def test_rename_clean_filename_preview_rejects_invalid_query_json_without_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token")
            try:
                server.start()
                rejected: list[tuple[int, dict]] = []
                for key, value in (
                    ("movie_filter_options", "NaN"),
                    ("movie_filter_options", "Infinity"),
                    ("movie_filter_terms", '{"release_groups":'),
                ):
                    query = "&".join(
                        f"{query_key}={quote(query_value, safe='')}"
                        for query_key, query_value in {
                            "filename": "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv",
                            key: value,
                        }.items()
                    )
                    rejected.append(
                        self._get_json(
                            f"{server.url}/api/rename/clean-filename-preview?{query}",
                            token="rename-token",
                        )
                    )
                history_status, history = self._get_json(f"{server.url}/api/commands?limit=5", token="rename-token")
            finally:
                server.stop()

        for status, payload in rejected:
            self.assertEqual(status, 400)
            self.assertEqual(payload["path"], "/api/rename/clean-filename-preview")
            self.assertIn("invalid query parameter", payload["error"])
        self.assertIn("non-finite JSON value is not allowed", rejected[0][1]["error"])
        self.assertIn("non-finite JSON value is not allowed", rejected[1][1]["error"])
        self.assertIn("movie_filter_terms", rejected[2][1]["error"])
        self.assertEqual(history_status, 200)
        self.assertEqual(history["entries"], [])

    def test_rename_filter_settings_persist_and_feed_saved_preview_policy(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "OutputContainer": "mkv",
            }
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            changes = {
                "RenameMovieFilterOptions": {
                    "video_source": True,
                    "audio_channels": True,
                    "editions": True,
                    "file_size": True,
                    "services_containers": True,
                    "languages_subs_dubs": True,
                    "release_groups": True,
                },
                "RenameMovieFilterTerms": {
                    "release_groups": ["SupaCvnt", "BYNDR"],
                    "services_containers": ["MA"],
                    "languages_subs_dubs": ["ita", "eng", "sub", "dub"],
                    "unknown": ["ignored"],
                },
                "RenameMovieRemoveTerms": ["sample", "", "sample", "behind the scenes"],
                "RenameTVFilterOptions": {
                    "video_source": True,
                    "audio_channels": True,
                    "release_flags": True,
                    "services_containers": True,
                    "languages_subs_dubs": True,
                    "release_groups": True,
                },
                "RenameTVFilterTerms": {
                    "release_groups": ["TTGA", "ttga"],
                    "release_flags": ["uncensored"],
                    "unknown": ["ignored"],
                },
                "RenameTVRemoveTerms": ["ova", "", "ova", "special"],
            }
            try:
                server.start()
                preview_status, preview_payload = self._post_json(
                    f"{server.url}/api/settings/preview-patch",
                    {"changes": changes},
                    token="rename-token",
                )
                save_request_payload = facade.settings_patch_request_with_review_confirmation(
                    resolved,
                    {"changes": changes},
                )
                save_status, save_payload = self._post_json(
                    f"{server.url}/api/settings/save-patch",
                    {**save_request_payload, "confirm_save": True},
                    token="rename-token",
                )
                saved_values = dict(service.saved_config_calls[-1]["config_values"])
                resolved.config_data = saved_values
                catalog_status, catalog = self._get_json(
                    f"{server.url}/api/rename/cleaning-filters",
                    token="rename-token",
                )
                filename_query = quote(
                    "Hoppers.2026.2160p.MA.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-BYNDR.mkv",
                    safe="",
                )
                saved_preview_status, saved_preview = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?filename={filename_query}",
                    token="rename-token",
                )
                tv_filename_query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "mode": "tv",
                        "source_folder": "The Web S01 1080p WEB-DL-TTGA",
                        "filename": "S01E01-Pilot.1080p.WEB-DL-TTGA.mkv",
                    }.items()
                )
                saved_tv_preview_status, saved_tv_preview = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{tv_filename_query}",
                    token="rename-token",
                )
                staged_query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "filename": "Iron.Lung.2026.1080p.WEBRip.x265.6CH-SupaCvnt.mkv",
                        "movie_filter_terms": json.dumps({"release_groups": ["SupaCvnt"]}),
                    }.items()
                )
                staged_preview_status, staged_preview = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{staged_query}",
                    token="rename-token",
                )
            finally:
                server.stop()

        self.assertEqual(preview_status, 200)
        self.assertTrue(preview_payload["ok"])
        self.assertEqual(save_status, 200)
        self.assertTrue(save_payload["ok"])
        self.assertEqual(saved_values["RenameMovieFilterTerms"]["release_groups"], ["SupaCvnt", "BYNDR"])
        self.assertEqual(saved_values["RenameMovieFilterTerms"]["services_containers"], ["MA"])
        self.assertEqual(saved_values["RenameMovieFilterTerms"]["languages_subs_dubs"], ["ita", "eng", "sub", "dub"])
        self.assertNotIn("unknown", saved_values["RenameMovieFilterTerms"])
        self.assertEqual(saved_values["RenameMovieRemoveTerms"], ["sample", "behind the scenes"])
        self.assertEqual(saved_values["RenameTVFilterTerms"]["release_groups"], ["TTGA"])
        self.assertEqual(saved_values["RenameTVFilterTerms"]["release_flags"], ["uncensored"])
        self.assertNotIn("unknown", saved_values["RenameTVFilterTerms"])
        self.assertEqual(saved_values["RenameTVRemoveTerms"], ["ova", "special"])
        self.assertEqual(catalog_status, 200)
        self.assertEqual(catalog["schema_version"], "desktop_rename_cleaning_filter_catalog.v1")
        self.assertEqual(catalog["movie"]["saved_terms"]["release_groups"], ["SupaCvnt", "BYNDR"])
        self.assertEqual(catalog["movie"]["saved_remove_terms"], ["sample", "behind the scenes"])
        self.assertEqual(catalog["tv"]["saved_terms"]["release_groups"], ["TTGA"])
        self.assertEqual(catalog["tv"]["saved_remove_terms"], ["ova", "special"])
        self.assertEqual(saved_preview_status, 200)
        self.assertEqual(saved_preview["target_name"], "Hoppers (2026).mkv")
        self.assertEqual(saved_preview["rename_cleaning_policy_source"], "saved")
        self.assertEqual(saved_tv_preview_status, 200)
        self.assertEqual(saved_tv_preview["target_name"], "The Web - S01E01 - Pilot.mkv")
        self.assertEqual(saved_tv_preview["rename_cleaning_policy_source"], "saved")
        self.assertEqual(staged_preview_status, 200)
        self.assertEqual(staged_preview["target_name"], "Iron Lung (2026).mkv")
        self.assertEqual(staged_preview["rename_cleaning_policy_source"], "staged")

    def test_local_api_rename_apply_rejects_absent_or_false_confirmation_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Serial Experiments Lain E01 Weird.mkv"
            media.write_text("media", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: _resolved(root))
            payload = {
                "paths": [str(media)],
                "mode": "tv",
                "show_name": "Serial Experiments Lain",
                "season": "S01",
                "start_episode": "E01",
                "selected_sources": [str(media)],
                "use_pipeline_naming_preview": False,
            }
            try:
                server.start()
                missing_status, missing = self._post_json(
                    f"{server.url}/api/rename/apply",
                    payload,
                    token="rename-token",
                )
                false_status, false = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**payload, "confirm_apply": False},
                    token="rename-token",
                )
                string_false_status, string_false = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**payload, "confirm_apply": "false"},
                    token="rename-token",
                )
            finally:
                server.stop()
            destination = root / "Serial Experiments Lain - S01E01 - Weird.mkv"
            media_still_exists = media.exists()
            destination_exists = destination.exists()

        self.assertEqual(missing_status, 200)
        self.assertEqual(false_status, 200)
        self.assertEqual(string_false_status, 400)
        for result in (missing, false):
            self.assertEqual(result["schema_version"], "desktop_command_result.v1")
            self.assertEqual(result["command"], "rename.apply")
            self.assertFalse(result["ok"])
            self.assertEqual(result["severity"], "warning")
            self.assertIn("confirmation", result["message"].lower())
            self.assertIn("confirm_apply must be true.", result["warnings"])
        self.assertIn("invalid API command payload", string_false["error"])
        self.assertIn("confirm_apply", string_false["error"])
        self.assertTrue(media_still_exists)
        self.assertFalse(destination_exists)

    def test_local_api_rename_apply_blocks_active_work_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Serial Experiments Lain E01 Weird.mkv"
            media.write_text("media", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            resolved = _resolved(root)
            service.cleanup_stale_launch_guards = lambda _resolved_arg: []  # type: ignore[method-assign]
            service.find_related_pipeline_processes = lambda _resolved_arg, job_kinds=None: []  # type: ignore[method-assign]
            service.active_job_close_block_messages = (  # type: ignore[method-assign]
                lambda _resolved_arg, job_kinds=None: ["ActiveJobs record launch.json reports pipeline work as active."]
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, result = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {
                        "paths": [str(media)],
                        "mode": "tv",
                        "show_name": "Serial Experiments Lain",
                        "season": "S01",
                        "start_episode": "E01",
                        "selected_sources": [str(media)],
                        "use_pipeline_naming_preview": False,
                        "confirm_apply": True,
                    },
                    token="rename-token",
                )
            finally:
                server.stop()
            destination = root / "Serial Experiments Lain - S01E01 - Weird.mkv"
            media_still_exists = media.exists()
            destination_exists = destination.exists()

        self.assertEqual(status, 200)
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "rename.apply")
        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "error")
        self.assertEqual(result["errors"], ["active_work"])
        self.assertIn("ActiveJobs still reports active work", result["message"])
        self.assertTrue(media_still_exists)
        self.assertFalse(destination_exists)

    def test_local_api_injects_rename_media_roots_and_requires_outside_root_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            configured = root / "ConfiguredMovies"
            outside = root / "StandaloneFolder"
            configured.mkdir()
            outside.mkdir()
            media = outside / "Example Movie 2024 1080p BluRay.mkv"
            media.write_text("media", encoding="utf-8")
            resolved = _resolved(root)
            resolved.local_base = root / "Scratch"
            resolved.state_root = resolved.local_base / "State"
            resolved.source_movies = configured
            resolved.source_tv = root / "ConfiguredTV"
            resolved.config_data = {"Outsource": str(root / "Outsource")}
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            spoofed_undo_root = root / "SpoofedUndo"
            apply_payload = {
                "paths": [str(media)],
                "mode": "movie",
                "movie_title": "Example Movie",
                "movie_year": "2024",
                "selected_sources": [str(media)],
                "confirm_apply": True,
                "use_pipeline_naming_preview": False,
            }
            spoofed_apply_payload = {
                **apply_payload,
                "_configured_media_roots": [str(outside)],
                "_rename_undo_manifest_root": str(spoofed_undo_root),
            }
            try:
                server.start()
                preview_status, preview = self._post_json(
                    f"{server.url}/api/rename/preview",
                    {
                        "paths": [str(media)],
                        "mode": "movie",
                        "movie_title": "Example Movie",
                        "movie_year": "2024",
                        "_configured_media_roots": [str(outside)],
                        "_rename_undo_manifest_root": str(spoofed_undo_root),
                    },
                    token="rename-token",
                )
                spoofed_apply_status, spoofed_apply = self._post_json(
                    f"{server.url}/api/rename/apply",
                    spoofed_apply_payload,
                    token="rename-token",
                )
                rejected_status, rejected = self._post_json(
                    f"{server.url}/api/rename/apply",
                    apply_payload,
                    token="rename-token",
                )
                string_rejected_status, string_rejected = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**apply_payload, "allow_outside_configured_roots": "false"},
                    token="rename-token",
                )
                allowed_status, allowed = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**apply_payload, "allow_outside_configured_roots": True},
                    token="rename-token",
                )
            finally:
                server.stop()
            destination = outside / "Example Movie (2024).mkv"
            destination_exists = destination.exists()
            media_exists = media.exists()
            undo_manifest = Path(str(allowed["data"]["undo_manifest"]))
            undo_parent = undo_manifest.parent
            undo_manifest_exists = undo_manifest.exists()
            undo_manifest.unlink(missing_ok=True)

        self.assertEqual(preview_status, 200)
        self.assertEqual(preview["rows"][0]["path_authority"], "outside_configured_roots")
        self.assertNotEqual(preview["rows"][0]["status"], "warning")
        self.assertNotIn("outside configured", " ".join(preview["rows"][0].get("warnings", [])).casefold())
        self.assertEqual(spoofed_apply_status, 400)
        self.assertIn("_configured_media_roots", spoofed_apply["error"])
        self.assertEqual(rejected_status, 200)
        self.assertFalse(rejected["ok"])
        self.assertIn("outside configured media roots", rejected["message"])
        self.assertEqual(string_rejected_status, 400)
        self.assertIn("allow_outside_configured_roots", string_rejected["error"])
        self.assertEqual(allowed_status, 200)
        self.assertTrue(allowed["ok"])
        self.assertTrue(destination_exists)
        self.assertFalse(media_exists)
        self.assertTrue(undo_manifest_exists)
        self.assertEqual(undo_parent, root / "Scratch" / "State" / "RenameUndo")
        self.assertFalse(spoofed_undo_root.exists())

    def test_local_api_injects_library_profile_roots_for_rename_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile_source = root / "ProfileTV"
            profile_output = root / "ProfileOut"
            profile_final = root / "ProfileFinal"
            spoofed = root / "SpoofedRoot"
            for directory in (profile_source, profile_output, profile_final, spoofed):
                directory.mkdir()
            media = profile_final / "Example Movie 2024 1080p BluRay.mkv"
            media.write_text("media", encoding="utf-8")
            resolved = _resolved(root)
            resolved.source_movies = root / "ConfiguredMovies"
            resolved.source_tv = root / "ConfiguredTV"
            resolved.config_data = {
                "SourceMovies": str(root / "ConfiguredMovies"),
                "SourceTV": str(root / "ConfiguredTV"),
                "Outsource": str(root / "Outsource"),
                "LibraryProfiles": [
                    {
                        "id": "profile-tv",
                        "enabled": True,
                        "source_path": str(profile_source),
                        "output_path": str(profile_output),
                        "promotion_enabled": True,
                        "promotion_destination": str(profile_final),
                    }
                ],
            }
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                preview_status, preview = self._post_json(
                    f"{server.url}/api/rename/preview",
                    {
                        "paths": [str(media)],
                        "mode": "movie",
                        "movie_title": "Example Movie",
                        "movie_year": "2024",
                        "use_pipeline_naming_preview": False,
                        "_configured_media_roots": [str(spoofed)],
                    },
                    token="rename-token",
                )
            finally:
                server.stop()

        self.assertEqual(preview_status, 200)
        row = preview["rows"][0]
        self.assertEqual(row["path_authority"], "configured_media_root")
        self.assertEqual(row["path_authority_status"], "ready")
        self.assertNotIn("outside configured", " ".join(row.get("warnings", [])).casefold())

    def test_local_api_rename_undo_uses_backend_root_and_strict_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            configured = root / "ConfiguredMovies"
            configured.mkdir()
            media = configured / "Example Movie 2024 1080p BluRay.mkv"
            media.write_text("media", encoding="utf-8")
            resolved = _resolved(root)
            resolved.local_base = root / "Scratch"
            resolved.state_root = resolved.local_base / "State"
            resolved.source_movies = configured
            resolved.source_tv = root / "ConfiguredTV"
            resolved.config_data = {"SourceMovies": str(configured), "Outsource": str(root / "Outsource")}
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            spoofed_undo_root = root / "SpoofedUndo"
            apply_payload = {
                "paths": [str(media)],
                "mode": "movie",
                "movie_title": "Example Movie",
                "movie_year": "2024",
                "selected_sources": [str(media)],
                "confirm_apply": True,
                "use_pipeline_naming_preview": False,
            }
            try:
                server.start()
                apply_status, applied = self._post_json(
                    f"{server.url}/api/rename/apply",
                    apply_payload,
                    token="rename-token",
                )
                undo_manifest = str(applied["data"]["undo_manifest"])
                string_rejected_status, string_rejected = self._post_json(
                    f"{server.url}/api/rename/undo",
                    {"undo_manifest": undo_manifest, "confirm_undo": "true"},
                    token="rename-token",
                )
                undo_status, undo = self._post_json(
                    f"{server.url}/api/rename/undo",
                    {
                        "undo_manifest": undo_manifest,
                        "confirm_undo": True,
                        "_rename_undo_manifest_root": str(spoofed_undo_root),
                    },
                    token="rename-token",
                )
            finally:
                server.stop()
            destination = configured / "Example Movie (2024).mkv"
            media_exists_after_undo = media.exists()
            destination_exists_after_undo = destination.exists()
            spoofed_undo_root_exists = spoofed_undo_root.exists()

        self.assertEqual(apply_status, 200)
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(string_rejected_status, 400)
        self.assertIn("confirm_undo", string_rejected["error"])
        self.assertEqual(undo_status, 200)
        self.assertTrue(undo["ok"], undo)
        self.assertEqual(undo["command"], "rename.undo")
        self.assertEqual(undo["data"]["schema_version"], "desktop_rename_undo_result.v1")
        self.assertEqual(undo["data"]["media_operations"], 1)
        self.assertTrue(media_exists_after_undo)
        self.assertFalse(destination_exists_after_undo)
        self.assertFalse(spoofed_undo_root_exists)

    def test_rename_preview_browse_and_apply_contracts_use_backend_policy(self) -> None:
        workflow = exercise_local_api_route_workflow()

        self.assertEqual(workflow.denied_status, 401)
        self.assertEqual(workflow.denied["error"], "unauthorized")
        self.assertEqual(workflow.rename_status, 200)
        self.assertEqual(workflow.rename_payload["schema_version"], "desktop_rename_preview.v1")
        self.assertEqual(
            workflow.rename_payload["rows"][0]["pipeline_guess"],
            "Serial Experiments Lain - S02E01 - Weird.mkv",
        )
        self.assertEqual(workflow.rename_payload["confidence_counts"], {"medium": 1})
        self.assertEqual(workflow.rename_payload["preview_source_counts"], {"auto_tv_heuristic": 1})
        self.assertEqual(workflow.rename_payload["change_kind_counts"], {"rename": 1})
        self.assertEqual(workflow.rename_payload["active_template"], "tv_standard")
        self.assertTrue(any(item["key"] == "tv_no_episode_title" for item in workflow.rename_payload["template_catalog"]))
        self.assertEqual(workflow.rename_browse_status, 200)
        self.assertEqual(workflow.rename_browse_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(workflow.rename_browse_payload["command"], "rename.browse")
        self.assertTrue(workflow.rename_browse_payload["ok"])
        self.assertEqual(workflow.rename_browse_payload["data"]["paths"], [str(workflow.media)])
        self.assertEqual(workflow.rename_browse_payload["data"]["selection_mode"], "files")
        self.assertEqual(workflow.rename_apply_status, 200)
        self.assertEqual(workflow.rename_apply_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(workflow.rename_apply_payload["command"], "rename.apply")
        self.assertTrue(workflow.rename_apply_payload["ok"], workflow.rename_apply_payload)


if __name__ == "__main__":
    unittest.main()
