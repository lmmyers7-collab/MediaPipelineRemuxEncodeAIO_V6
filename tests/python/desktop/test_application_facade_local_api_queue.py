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


class LocalApiQueueTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_local_api_queue_state_routes_are_contracted_journaled_and_source_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movie = root / "Movies" / "Movie.mkv"
            source_tv = root / "TV" / "Show" / "Show S01E01.mkv"
            outside = root / "Other" / "Outside.mkv"
            source_movie.parent.mkdir(parents=True, exist_ok=True)
            source_tv.parent.mkdir(parents=True, exist_ok=True)
            outside.parent.mkdir(parents=True, exist_ok=True)
            source_movie.write_bytes(b"movie")
            source_tv.write_bytes(b"tv")
            outside.write_bytes(b"outside")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            resolved.queue_strategy_path = resolved.state_root / "queue_strategy.json"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-state-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                strategy_status, strategy = self._get_json(f"{server.url}/api/queue/strategy", token=server.token)
                invalid_status, invalid_priority = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"path": str(outside), "level": "high"},
                    token=server.token,
                )
                priority_status, priority = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"path": str(source_movie), "level": "high", "reason": "test"},
                    token=server.token,
                )
                override_invalid_status, override_invalid = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(outside), "audio": {"maxChannels": 2}},
                    token=server.token,
                )
                override_status, override = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source_tv), "audio": {"maxChannels": 2}},
                    token=server.token,
                )
                override_read_status, override_read = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source_tv))}",
                    token=server.token,
                )
                strategy_save_status, strategy_save = self._post_json(
                    f"{server.url}/api/queue/strategy",
                    {"strategy": "FreshestFirst"},
                    token=server.token,
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token=server.token)
            finally:
                server.stop()

        self.assertEqual(strategy_status, 200)
        self.assertTrue(strategy["ok"])
        self.assertEqual(invalid_status, 200)
        self.assertFalse(invalid_priority["ok"])
        self.assertEqual(invalid_priority["schema_version"], "desktop_command_result.v1")
        self.assertIn("outside configured source roots", invalid_priority["errors"][0])
        self.assertEqual(priority_status, 200)
        self.assertTrue(priority["ok"])
        self.assertEqual(priority["schema_version"], "desktop_command_result.v1")
        self.assertEqual(priority["entry_count"], 1)
        self.assertEqual(override_invalid_status, 200)
        self.assertFalse(override_invalid["ok"])
        self.assertEqual(override_invalid["schema_version"], "desktop_command_result.v1")
        self.assertIn("outside configured source roots", override_invalid["errors"][0])
        self.assertEqual(override_status, 200)
        self.assertTrue(override["ok"])
        self.assertEqual(override["schema_version"], "desktop_command_result.v1")
        self.assertEqual(override["entry_count"], 1)
        self.assertEqual(override_read_status, 200)
        self.assertTrue(override_read["has_override"])
        self.assertEqual(override_read["path"], str(source_tv))
        self.assertEqual(strategy_save_status, 200)
        self.assertTrue(strategy_save["ok"])
        self.assertEqual(strategy_save["schema_version"], "desktop_command_result.v1")
        self.assertEqual(commands_status, 200)
        journaled = {entry["command"] for entry in commands["entries"]}
        self.assertIn("queue.priority", journaled)
        self.assertIn("queue.file_overrides", journaled)
        self.assertIn("queue.strategy", journaled)

    def test_local_api_queue_priority_clear_all_clears_entire_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movie = root / "Movies" / "Movie.mkv"
            source_tv = root / "TV" / "Show" / "Show S01E01.mkv"
            source_movie.parent.mkdir(parents=True, exist_ok=True)
            source_tv.parent.mkdir(parents=True, exist_ok=True)
            source_movie.write_bytes(b"movie")
            source_tv.write_bytes(b"tv")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            resolved.priority_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.priority_manifest_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            str(source_movie).replace("\\", "/").lower(): {
                                "level": "high",
                                "reason": "visible row",
                                "set_at": "2026-06-02T00:00:00+00:00",
                            },
                            str(source_tv).replace("\\", "/").lower(): {
                                "level": "hold",
                                "reason": "not currently visible",
                                "set_at": "2026-06-02T00:00:00+00:00",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-priority-clear-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                clear_status, clear_payload = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"clear_all": True},
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/priority",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(clear_status, 200)
        self.assertTrue(clear_payload["ok"])
        self.assertEqual(clear_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(clear_payload["entry_count"], 0)
        self.assertIn("All priority manifest entries cleared", clear_payload["message"])
        self.assertEqual(read_status, 200)
        self.assertEqual(read_payload["entry_count"], 0)
        self.assertEqual(read_payload["entries"], {})

    def test_local_api_queue_priority_read_fails_closed_when_manifest_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            resolved.priority_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.priority_manifest_path.write_text("{not-json", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-priority-corrupt-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/priority",
                    token=server.token,
                )
                clear_status, clear_payload = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"clear_all": True},
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(read_status, 200)
        self.assertFalse(read_payload["ok"])
        self.assertEqual(read_payload["schema_version"], "desktop_command_result.v1")
        self.assertIn("Priority manifest is unreadable", read_payload["errors"][0])
        self.assertEqual(clear_status, 200)
        self.assertTrue(clear_payload["ok"])
        self.assertEqual(clear_payload["entry_count"], 0)

    def test_local_api_queue_priority_bulk_accepts_manual_order_positions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movie = root / "Movies" / "Movie.mkv"
            source_tv = root / "TV" / "Show" / "Show S01E01.mkv"
            source_movie.parent.mkdir(parents=True, exist_ok=True)
            source_tv.parent.mkdir(parents=True, exist_ok=True)
            source_movie.write_bytes(b"movie")
            source_tv.write_bytes(b"tv")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-manual-position-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                position_status, position_payload = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {
                        "items": [
                            {"path": str(source_movie), "level": "normal", "position": 2},
                            {"path": str(source_tv), "level": "normal", "position": 1},
                        ],
                    },
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/priority",
                    token=server.token,
                )
            finally:
                server.stop()

        movie_key = str(source_movie).replace("\\", "/").lower()
        tv_key = str(source_tv).replace("\\", "/").lower()
        self.assertEqual(position_status, 200)
        self.assertTrue(position_payload["ok"])
        self.assertEqual(read_status, 200)
        self.assertEqual(read_payload["entries"][movie_key]["position"], 2.0)
        self.assertEqual(read_payload["entries"][tv_key]["position"], 1.0)
        self.assertEqual(read_payload["entries"][movie_key]["level"], "normal")

    def test_local_api_file_override_clear_fields_preserves_save_and_full_clear(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-clear-fields-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                save_status, save = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [{"language": "eng"}],
                            "maxChannels": 6,
                        },
                        "subtitles": {
                            "keepTracks": [{"language": "eng"}],
                            "stripAll": True,
                        },
                    },
                    token=server.token,
                )
                clear_status, clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "clear_fields": ["audio.maxChannels", "subtitles.stripAll"],
                    },
                    token=server.token,
                )
                unknown_status, unknown = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["audio.loudnessMode"]},
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                full_clear_status, full_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear": True},
                    token=server.token,
                )
                read_cleared_status, read_cleared = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                save_again_status, save_again = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": 2}},
                    token=server.token,
                )
                read_saved_status, read_saved = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(save_status, 200)
        self.assertTrue(save["ok"])
        self.assertEqual(clear_status, 200)
        self.assertTrue(clear["ok"])
        self.assertEqual(clear["entry_count"], 1)
        self.assertEqual(unknown_status, 200)
        self.assertFalse(unknown["ok"])
        self.assertEqual(unknown["schema_version"], "desktop_command_result.v1")
        self.assertIn("Unsupported clear_fields path", unknown["message"])
        self.assertEqual(read_status, 200)
        self.assertTrue(read_payload["has_override"])
        entry = read_payload["entry"]
        self.assertEqual(entry["audio"], {"keepTracks": [{"language": "eng"}]})
        self.assertEqual(entry["subtitles"], {"keepTracks": [{"language": "eng"}]})
        self.assertEqual(full_clear_status, 200)
        self.assertTrue(full_clear["ok"])
        self.assertEqual(read_cleared_status, 200)
        self.assertFalse(read_cleared["has_override"])
        self.assertEqual(save_again_status, 200)
        self.assertTrue(save_again["ok"])
        self.assertEqual(read_saved_status, 200)
        self.assertEqual(read_saved["entry"]["audio"], {"maxChannels": 2})

    def test_local_api_file_override_validates_current_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            strip_true_source = root / "TV" / "Show" / "Show S01E02.mkv"
            strip_false_source = root / "TV" / "Show" / "Show S01E03.mkv"
            for path in (source, strip_true_source, strip_false_source):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-override-validation-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                valid_status, valid = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [{"language": "eng"}],
                            "dropTracks": [{"language": "jpn"}],
                            "renameTracks": [{"language": "eng", "channels": 6, "newTitle": "English 5.1"}],
                            "maxChannels": 6,
                            "downmixMode": "max_channels",
                            "transcodeCodec": "eac3",
                            "transcodeBitrate": "640k",
                            "preferDefaultLanguage": "eng",
                        },
                        "subtitles": {
                            "keepTracks": [{"language": "eng"}],
                            "dropTracks": [{"language": "und"}],
                            "stripAll": False,
                        },
                    },
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                max_channel_results = []
                for max_channels in (2, 6, 8):
                    max_channel_results.append(
                        self._post_json(
                            f"{server.url}/api/queue/file-overrides",
                            {"path": str(source), "audio": {"maxChannels": max_channels}},
                            token=server.token,
                        )
                    )
                strip_true_status, strip_true = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(strip_true_source), "subtitles": {"stripAll": True}},
                    token=server.token,
                )
                strip_false_status, strip_false = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(strip_false_source), "subtitles": {"stripAll": False}},
                    token=server.token,
                )
                invalid_string_status, invalid_string = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": "6"}},
                    token=server.token,
                )
                invalid_zero_status, invalid_zero = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": 0}},
                    token=server.token,
                )
                invalid_negative_status, invalid_negative = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": -1}},
                    token=server.token,
                )
                invalid_top_status, invalid_top = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": 2}, "route": "encode"},
                    token=server.token,
                )
                invalid_nested_status, invalid_nested = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"loudnessMode": "night"}},
                    token=server.token,
                )
                invalid_selector_status, invalid_selector = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"keepTracks": [{"language": 5}]}},
                    token=server.token,
                )
                invalid_safe_field_status, invalid_safe_field = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"preferDefaultLanguage": 5}},
                    token=server.token,
                )
                invalid_deferred_enum_status, invalid_deferred_enum = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"downmixMode": "invalid"}},
                    token=server.token,
                )
                invalid_deferred_bitrate_status, invalid_deferred_bitrate = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"transcodeBitrate": "not-a-bitrate"}},
                    token=server.token,
                )
                invalid_clear_status, invalid_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["subtitles.renameTracks"]},
                    token=server.token,
                )
                clear_all_status, clear_all = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"clear_all": True},
                    token=server.token,
                )
                manifest_status, manifest = self._get_json(
                    f"{server.url}/api/queue/file-overrides",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(valid_status, 200)
        self.assertTrue(valid["ok"])
        self.assertEqual(read_status, 200)
        entry = read_payload["entry"]
        self.assertEqual(entry["audio"]["keepTracks"], [{"language": "eng"}])
        self.assertEqual(entry["audio"]["dropTracks"], [{"language": "jpn"}])
        self.assertEqual(entry["audio"]["renameTracks"], [{"language": "eng", "channels": 6, "newTitle": "English 5.1"}])
        self.assertEqual(entry["audio"]["maxChannels"], 6)
        self.assertEqual(entry["audio"]["downmixMode"], "max_channels")
        self.assertEqual(entry["audio"]["transcodeCodec"], "eac3")
        self.assertEqual(entry["audio"]["transcodeBitrate"], "640k")
        self.assertEqual(entry["audio"]["preferDefaultLanguage"], "eng")
        self.assertEqual(entry["subtitles"]["keepTracks"], [{"language": "eng"}])
        self.assertEqual(entry["subtitles"]["dropTracks"], [{"language": "und"}])
        self.assertFalse(entry["subtitles"]["stripAll"])
        for status, payload in max_channel_results:
            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
        self.assertEqual(strip_true_status, 200)
        self.assertTrue(strip_true["ok"])
        self.assertEqual(strip_false_status, 200)
        self.assertTrue(strip_false["ok"])
        for status, payload, expected in [
            (invalid_string_status, invalid_string, "'audio.maxChannels' must be an integer."),
            (invalid_zero_status, invalid_zero, "'audio.maxChannels' must be one of: 2, 6, 8."),
            (invalid_negative_status, invalid_negative, "'audio.maxChannels' must be one of: 2, 6, 8."),
            (invalid_top_status, invalid_top, "Unsupported file override request field(s): route"),
            (invalid_nested_status, invalid_nested, "Unsupported audio field(s): loudnessMode"),
            (invalid_selector_status, invalid_selector, "'audio.keepTracks[0].language' must be a string."),
            (invalid_safe_field_status, invalid_safe_field, "'audio.preferDefaultLanguage' must be a string."),
            (invalid_deferred_enum_status, invalid_deferred_enum, "'audio.downmixMode' must be one of:"),
            (invalid_deferred_bitrate_status, invalid_deferred_bitrate, "'audio.transcodeBitrate' must match"),
            (invalid_clear_status, invalid_clear, "Unsupported clear_fields path(s): subtitles.renameTracks"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(status, 200)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
                self.assertIn(expected, "\n".join(payload.get("errors", [])))
        self.assertEqual(clear_all_status, 200)
        self.assertTrue(clear_all["ok"])
        self.assertEqual(manifest_status, 200)
        self.assertTrue(manifest["ok"])
        self.assertEqual(manifest["entry_count"], 0)

    def test_local_api_file_override_effective_read_reports_match_sources_and_library_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tv_root = root / "Anime"
            legacy_tv_root = root / "TV"
            movies_root = root / "Movies"
            source = tv_root / "Show" / "Season 01" / "Show S01E01.mkv"
            source_no_override = tv_root / "Show" / "Season 01" / "Show S01E02.mkv"
            folder_source = tv_root / "Folder" / "Folder Episode.mkv"
            outside = root / "Other" / "Outside.mkv"
            for path in (source, source_no_override, folder_source, outside):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            movies_root.mkdir(parents=True, exist_ok=True)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = movies_root
            resolved.source_tv = legacy_tv_root
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            resolved.config_data = {
                "SourceMovies": str(movies_root),
                "SourceTV": str(legacy_tv_root),
                "PreferredDefaultAudioLanguages": ["jpn"],
                "AudioMaxChannels": 8,
                "SubKeepLanguages": ["spa"],
                "LibraryProfiles": [
                    {
                        "id": "anime",
                        "name": "Anime",
                        "enabled": True,
                        "designation": "tv",
                        "source_path": str(tv_root),
                        "overrides": {
                            "audio": {
                                "PreferredDefaultAudioLanguages": ["eng"],
                                "AudioMaxChannels": 6,
                            },
                            "subtitles": {"SubKeepLanguages": ["eng"]},
                        },
                    }
                ],
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-effective-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                missing_status, missing = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective",
                    token=server.token,
                )
                invalid_status, invalid = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(outside))}",
                    token=server.token,
                )
                no_override_status, no_override = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source_no_override))}",
                    token=server.token,
                )
                self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [{"language": "jpn"}],
                            "preferDefaultLanguage": "jpn",
                        },
                        "subtitles": {"stripAll": False},
                    },
                    token=server.token,
                )
                exact_status, exact = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source))}",
                    token=server.token,
                )
                manifest_before = resolved.file_overrides_path.read_text(encoding="utf-8")
                repeat_status, repeat = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source))}",
                    token=server.token,
                )
                manifest_after = resolved.file_overrides_path.read_text(encoding="utf-8")
                self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(folder_source.parent),
                        "audio": {"preferDefaultLanguage": "spa"},
                        "subtitles": {"dropTracks": [{"language": "und"}]},
                    },
                    token=server.token,
                )
                folder_status, folder = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(folder_source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(missing_status, 200)
        self.assertFalse(missing["ok"])
        self.assertIn("'path' is required", missing["message"])
        self.assertEqual(invalid_status, 200)
        self.assertFalse(invalid["ok"])
        self.assertIn("outside configured source roots", invalid["message"])
        self.assertEqual(no_override_status, 200)
        self.assertTrue(no_override["ok"])
        self.assertFalse(no_override["has_file_override"])
        self.assertEqual(no_override["library"]["name"], "Anime")
        self.assertEqual(no_override["inherited"]["audioKeepLanguages"]["display"], "eng")
        self.assertEqual(no_override["inherited"]["audioMaxChannels"]["display"], "6 channels")
        self.assertEqual(no_override["inherited"]["subtitleKeepLanguages"]["display"], "eng")
        self.assertFalse(no_override["inherited"]["audioDropLanguages"]["available"])
        self.assertEqual(no_override["sources"]["audio.maxChannels"], "library")
        self.assertEqual(no_override["sources"]["audio.preferDefaultLanguage"], "library")
        self.assertIn("resolved_track_actions", no_override)
        self.assertIn("audio", no_override["resolved_track_actions"])
        self.assertIn("subtitles", no_override["resolved_track_actions"])
        self.assertIn("track_selection_preview", no_override)
        no_override_prefer = no_override["expanded_effective_fields"]["audioPreferDefaultLanguage"]
        self.assertEqual(no_override_prefer["field_path"], "audio.preferDefaultLanguage")
        self.assertTrue(no_override_prefer["available"])
        self.assertEqual(no_override_prefer["display"], "eng")
        self.assertEqual(no_override_prefer["source"], "library")
        self.assertEqual(no_override_prefer["source_key"], "PreferredDefaultAudioLanguages")
        self.assertFalse(no_override_prefer["can_clear_file_field"])
        self.assertEqual(no_override_prefer["inherited"]["display"], "eng")
        self.assertEqual(no_override_prefer["effective"]["source"], "library")
        self.assertEqual(exact_status, 200)
        self.assertTrue(exact["has_file_override"])
        self.assertEqual(exact["file_override_scope"], "file")
        self.assertEqual(exact["sources"]["audio.keepTracks"], "file_override")
        self.assertEqual(exact["sources"]["audio.preferDefaultLanguage"], "file_override")
        self.assertEqual(exact["sources"]["subtitles.stripAll"], "file_override")
        self.assertFalse(exact["effective_drawer_fields"]["subtitleStripAll"]["value"])
        self.assertEqual(exact["effective_drawer_fields"]["audioMaxChannels"]["source"], "library")
        exact_prefer = exact["expanded_effective_fields"]["audioPreferDefaultLanguage"]
        self.assertEqual(exact_prefer["display"], "jpn")
        self.assertEqual(exact_prefer["source"], "file_override")
        self.assertEqual(exact_prefer["source_key"], "audio.preferDefaultLanguage")
        self.assertTrue(exact_prefer["can_clear_file_field"])
        self.assertEqual(exact_prefer["inherited"]["display"], "eng")
        self.assertEqual(exact_prefer["effective"]["can_clear_file_field"], True)
        self.assertEqual(repeat_status, 200)
        self.assertTrue(repeat["ok"])
        self.assertEqual(manifest_after, manifest_before)
        self.assertEqual(folder_status, 200)
        self.assertTrue(folder["has_file_override"])
        self.assertEqual(folder["file_override_scope"], "folder")
        self.assertEqual(folder["sources"]["subtitles.dropTracks"], "folder_override")
        self.assertEqual(folder["sources"]["audio.preferDefaultLanguage"], "folder_override")
        folder_prefer = folder["expanded_effective_fields"]["audioPreferDefaultLanguage"]
        self.assertEqual(folder_prefer["display"], "spa")
        self.assertEqual(folder_prefer["source"], "folder_override")
        self.assertFalse(folder_prefer["can_clear_file_field"])

    def test_local_api_file_override_revalidates_merged_route_video_edits(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-merged-override-validation-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                video_status, video = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "video": {
                            "codec": "h264_nvenc",
                            "container": "mp4",
                        },
                    },
                    token=server.token,
                )
                remux_status, remux = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"profile": "remux"},
                    },
                    token=server.token,
                )
                read_after_reject_status, read_after_reject = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                transcode_status, transcode = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"profile": "transcode"},
                    },
                    token=server.token,
                )
                threshold_status, threshold = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"routeThresholdMode": "bitrate"},
                    },
                    token=server.token,
                )
                audio_status, audio = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {"maxChannels": 6},
                    },
                    token=server.token,
                )
                read_after_valid_status, read_after_valid = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(video_status, 200)
        self.assertTrue(video["ok"])
        self.assertEqual(remux_status, 200)
        self.assertFalse(remux["ok"])
        self.assertEqual(remux["message"], "Invalid file override payload.")
        self.assertIn("cannot be combined", "\n".join(remux.get("errors", [])))
        self.assertEqual(read_after_reject_status, 200)
        rejected_entry = read_after_reject["entry"]
        self.assertEqual(rejected_entry["video"], {"codec": "h264_nvenc", "container": "mp4"})
        self.assertNotIn("routing", rejected_entry)
        self.assertEqual(transcode_status, 200)
        self.assertTrue(transcode["ok"])
        self.assertEqual(threshold_status, 200)
        self.assertTrue(threshold["ok"])
        self.assertEqual(audio_status, 200)
        self.assertTrue(audio["ok"])
        self.assertEqual(read_after_valid_status, 200)
        valid_entry = read_after_valid["entry"]
        self.assertEqual(valid_entry["video"], {"codec": "h264_nvenc", "container": "mp4"})
        self.assertEqual(valid_entry["routing"], {"profile": "transcode", "routeThresholdMode": "bitrate"})
        self.assertEqual(valid_entry["audio"], {"maxChannels": 6})

    def test_local_api_file_override_route_preview_is_read_only_and_validates_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            missing_row_source = root / "TV" / "Show" / "Show S01E02.mkv"
            outside = root / "Other" / "Outside.mkv"
            for path in (source, missing_row_source, outside):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            resolved.queue_snapshot_path = resolved.state_root / "Progress" / "queue_snapshot.json"
            resolved.config_data = {
                "SourceMovies": str(resolved.source_movies),
                "SourceTV": str(resolved.source_tv),
                "RoutingProfile": "plex_direct_stream",
                "RouteThresholdMode": "compatibility_advisory",
                "SizeGuardMode": "advisory",
                "VideoCodec": "h264_nvenc",
                "OutputContainer": "mkv",
                "EncodeTuningPreset": "balanced_nvenc",
                "EncodeLadder": "auto",
                "RemuxSafeVideoCodecs": ["h264", "hevc"],
            }
            resolved.file_overrides_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.file_overrides_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            str(source).replace("\\", "/").lower(): {
                                "set_at": "2026-05-31T00:00:00+00:00",
                                "audio": {"maxChannels": 6},
                            }
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            resolved.queue_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.queue_snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-31T12:00:00-04:00",
                        "rows": [
                            {
                                "source_path": str(source),
                                "root_path": str(resolved.source_tv),
                                "media_kind": "tv",
                                "phase": "tv",
                                "relative_path": "Show/Show S01E01.mkv",
                                "display_name": "Show S01E01",
                                "route": "remux",
                                "route_reason": "source is compatible",
                                "route_reason_code": "compatible_source",
                                "queue_index": 1,
                                "queue_total": 1,
                                "global_order": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest_before = resolved.file_overrides_path.read_text(encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-route-preview-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                missing_status, missing = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {},
                    token=server.token,
                )
                invalid_path_status, invalid_path = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(outside)},
                    token=server.token,
                )
                current_status, current = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source)},
                    token=server.token,
                )
                remux_status, remux = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"routing": {"forceRoute": "remux"}}},
                    token=server.token,
                )
                transcode_status, transcode = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"routing": {"forceRoute": "transcode"}}},
                    token=server.token,
                )
                bad_route_status, bad_route = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"routing": {"forceRoute": "copy"}}},
                    token=server.token,
                )
                bad_codec_status, bad_codec = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"video": {"codec": "vp9"}}},
                    token=server.token,
                )
                bad_container_status, bad_container = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"video": {"container": "avi"}}},
                    token=server.token,
                )
                video_only_status, video_only = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"video": {"codec": "h264_nvenc"}}},
                    token=server.token,
                )
                burn_status, burn = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {
                        "path": str(source),
                        "proposed_override": {"subtitles": {"burnTrack": {"streamIndex": 3, "language": "eng"}}},
                    },
                    token=server.token,
                )
                burn_remux_status, burn_remux = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {
                        "path": str(source),
                        "proposed_override": {
                            "routing": {"forceRoute": "remux"},
                            "subtitles": {"burnTrack": {"streamIndex": 3}},
                        },
                    },
                    token=server.token,
                )
                missing_row_status, missing_row = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(missing_row_source)},
                    token=server.token,
                )
            finally:
                server.stop()
            manifest_after = resolved.file_overrides_path.read_text(encoding="utf-8")

        self.assertEqual(missing_status, 200)
        self.assertFalse(missing["ok"])
        self.assertIn("'path' is required", "\n".join(missing.get("errors", [])))
        self.assertEqual(invalid_path_status, 200)
        self.assertFalse(invalid_path["ok"])
        self.assertIn("outside configured source roots", "\n".join(invalid_path.get("errors", [])))
        self.assertEqual(current_status, 200)
        self.assertTrue(current["ok"])
        self.assertEqual(current["schema_version"], "queue_file_override_route_preview.v1")
        self.assertEqual(current["current"]["route"], "remux")
        self.assertEqual(current["current"]["videoCodec"], "copy")
        self.assertEqual(current["proposed"]["route"], "remux")
        self.assertEqual(current["proposed"]["decisionSource"], "current_queue_snapshot")
        self.assertFalse(current["impact"]["will_force_transcode"])
        self.assertEqual(current["impact"]["route_decision_helper"], "queue_snapshot_current_route")
        self.assertEqual(remux_status, 200)
        self.assertTrue(remux["ok"])
        self.assertEqual(remux["proposed"]["route"], "remux")
        self.assertEqual(remux["proposed"]["decisionSource"], "forced_route_preview")
        self.assertFalse(remux["impact"]["will_force_transcode"])
        self.assertEqual(remux["impact"]["estimated_risk"], "low")
        self.assertEqual(transcode_status, 200)
        self.assertTrue(transcode["ok"])
        self.assertEqual(transcode["proposed"]["route"], "transcode")
        self.assertEqual(transcode["proposed"]["videoCodec"], "h264_nvenc")
        self.assertEqual(transcode["proposed"]["decisionSource"], "forced_route_preview")
        self.assertTrue(transcode["impact"]["will_force_transcode"])
        self.assertTrue(transcode["impact"]["will_prevent_remux"])
        self.assertTrue(transcode["impact"]["requires_confirmation"])
        self.assertEqual(bad_route_status, 200)
        self.assertFalse(bad_route["ok"])
        self.assertIn("routing.forceRoute", "\n".join(bad_route.get("errors", [])))
        self.assertEqual(bad_codec_status, 200)
        self.assertFalse(bad_codec["ok"])
        self.assertIn("video.codec", "\n".join(bad_codec.get("errors", [])))
        self.assertEqual(bad_container_status, 200)
        self.assertFalse(bad_container["ok"])
        self.assertIn("video.container", "\n".join(bad_container.get("errors", [])))
        self.assertEqual(video_only_status, 200)
        self.assertTrue(video_only["ok"])
        self.assertEqual(video_only["proposed"]["route"], "transcode")
        self.assertEqual(video_only["proposed"]["source"], "proposed_file_override")
        self.assertEqual(video_only["proposed"]["decisionSource"], "proposed_file_override")
        self.assertTrue(video_only["impact"]["will_force_transcode"])
        self.assertEqual(burn_status, 200)
        self.assertTrue(burn["ok"])
        self.assertEqual(burn["proposed"]["route"], "transcode")
        self.assertTrue(burn["impact"]["will_force_transcode"])
        self.assertTrue(burn["impact"]["will_prevent_remux"])
        burn_warnings = "\n".join(item["message"] for item in burn.get("warnings", []))
        self.assertIn("Subtitle burn-in forces ENCODE", burn_warnings)
        self.assertIn("All selectable output subtitle streams will be dropped", burn_warnings)
        self.assertIn("subtitle-burn encode profile", burn_warnings)
        self.assertEqual(burn_remux_status, 200)
        self.assertFalse(burn_remux["ok"])
        self.assertIn("subtitles.burnTrack", "\n".join(burn_remux.get("errors", [])))
        self.assertEqual(missing_row_status, 200)
        self.assertFalse(missing_row["ok"])
        self.assertIn("queue snapshot row", "\n".join(missing_row.get("errors", [])).lower())
        self.assertEqual(manifest_after, manifest_before)

    def test_local_api_file_override_route_video_persistence_validation_and_effective_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            resolved.config_data = {
                "SourceMovies": str(resolved.source_movies),
                "SourceTV": str(resolved.source_tv),
                "RoutingProfile": "plex_direct_stream",
                "RouteThresholdMode": "compatibility_advisory",
                "VideoCodec": "hevc_nvenc",
                "OutputContainer": "mkv",
                "EncodeTuningPreset": "balanced_nvenc",
                "EncodeLadder": "auto",
                "CompatibleAudioCodecs": ["aac"],
                "SubKeepLanguages": ["eng"],
                "RemuxSafeVideoCodecs": ["h264", "hevc"],
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-route-video-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                valid_status, valid = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {
                            "profile": "transcode",
                            "routeThresholdMode": "bitrate",
                        },
                        "video": {
                            "codec": "h264_nvenc",
                            "container": "mp4",
                            "encodePreset": "balanced_nvenc",
                            "encodeLadder": "plex_compat",
                        },
                    },
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                effective_status, effective = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source))}",
                    token=server.token,
                )
                raw_manifest = json.loads(resolved.file_overrides_path.read_text(encoding="utf-8"))
                bad_profile_status, bad_profile = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "routing": {"profile": "transcode;Remove-Item"}},
                    token=server.token,
                )
                bad_codec_status, bad_codec = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "video": {"codec": "vp9"}},
                    token=server.token,
                )
                bad_container_status, bad_container = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "video": {"container": "avi"}},
                    token=server.token,
                )
                unknown_nested_status, unknown_nested = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "routing": {"forceRoute": "transcode"}},
                    token=server.token,
                )
                bad_combo_status, bad_combo = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"profile": "remux"},
                        "video": {"codec": "h264_nvenc"},
                    },
                    token=server.token,
                )
                clear_one_status, clear_one = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["video.codec"]},
                    token=server.token,
                )
                read_after_clear_status, read_after_clear = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                unsupported_clear_status, unsupported_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["video.rawArgs"]},
                    token=server.token,
                )
                clear_remaining_status, clear_remaining = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "clear_fields": [
                            "routing.profile",
                            "routing.routeThresholdMode",
                            "video.container",
                            "video.encodePreset",
                            "video.encodeLadder",
                        ],
                    },
                    token=server.token,
                )
                read_empty_status, read_empty = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                audio_status, audio = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {"maxChannels": 6},
                        "subtitles": {"stripAll": False},
                    },
                    token=server.token,
                )
                full_clear_status, full_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear": True},
                    token=server.token,
                )
                read_full_clear_status, read_full_clear = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(valid_status, 200)
        self.assertTrue(valid["ok"])
        self.assertTrue(any("routing.profile" in warning for warning in valid.get("warnings", [])))
        self.assertTrue(any("video.container" in warning for warning in valid.get("warnings", [])))
        self.assertEqual(read_status, 200)
        self.assertTrue(read_payload["has_override"])
        entry = read_payload["entry"]
        self.assertEqual(entry["routing"], {"profile": "transcode", "routeThresholdMode": "bitrate"})
        self.assertEqual(
            entry["video"],
            {
                "codec": "h264_nvenc",
                "container": "mp4",
                "encodePreset": "balanced_nvenc",
                "encodeLadder": "plex_compat",
            },
        )
        manifest_entry = next(iter(raw_manifest["entries"].values()))
        self.assertEqual(sorted(manifest_entry.keys()), ["routing", "set_at", "video"])
        self.assertEqual(effective_status, 200)
        self.assertTrue(effective["ok"])
        route_fields = effective["route_video_effective_fields"]
        self.assertEqual(route_fields["routeProfile"]["source"], "file_override")
        self.assertEqual(route_fields["routeProfile"]["value"], "transcode")
        self.assertTrue(route_fields["routeProfile"]["can_clear_file_field"])
        self.assertTrue(route_fields["routeProfile"]["warnings"])
        self.assertIn({"value": "transcode", "label": "Transcode"}, route_fields["routeProfile"]["choices"])
        self.assertIn({"value": "bitrate", "label": "Bitrate"}, route_fields["routingRouteThresholdMode"]["choices"])
        self.assertEqual(route_fields["videoCodec"]["source"], "file_override")
        self.assertEqual(route_fields["videoCodec"]["inherited"]["value"], "hevc_nvenc")
        self.assertIn({"value": "h264_nvenc", "label": "H264 Nvenc"}, route_fields["videoCodec"]["choices"])
        self.assertIn({"value": "mp4", "label": "Mp4"}, route_fields["videoContainer"]["choices"])
        self.assertIn({"value": "balanced_nvenc", "label": "Balanced Nvenc"}, route_fields["videoEncodePreset"]["choices"])
        self.assertIn({"value": "plex_compat", "label": "Plex Compat"}, route_fields["videoEncodeLadder"]["choices"])
        self.assertEqual(effective["sources"]["video.container"], "file_override")
        self.assertEqual(effective["route_video_processing"]["route"], "transcode")
        self.assertTrue(effective["route_video_processing"]["will_force_transcode"])
        self.assertEqual(effective["route_video_processing"]["container"], "mp4")
        for status, payload, expected in [
            (bad_profile_status, bad_profile, "routing.profile"),
            (bad_codec_status, bad_codec, "video.codec"),
            (bad_container_status, bad_container, "video.container"),
            (unknown_nested_status, unknown_nested, "Unsupported routing field(s): forceRoute"),
            (bad_combo_status, bad_combo, "cannot be combined"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(status, 200)
                self.assertFalse(payload["ok"])
                self.assertIn(expected, "\n".join(payload.get("errors", [])))
        self.assertEqual(clear_one_status, 200)
        self.assertTrue(clear_one["ok"])
        self.assertEqual(read_after_clear_status, 200)
        self.assertNotIn("codec", read_after_clear["entry"]["video"])
        self.assertEqual(read_after_clear["entry"]["video"]["container"], "mp4")
        self.assertEqual(read_after_clear["entry"]["routing"]["profile"], "transcode")
        self.assertEqual(unsupported_clear_status, 200)
        self.assertFalse(unsupported_clear["ok"])
        self.assertIn("Unsupported clear_fields path(s): video.rawArgs", "\n".join(unsupported_clear.get("errors", [])))
        self.assertEqual(clear_remaining_status, 200)
        self.assertTrue(clear_remaining["ok"])
        self.assertEqual(read_empty_status, 200)
        self.assertFalse(read_empty["has_override"])
        self.assertEqual(audio_status, 200)
        self.assertTrue(audio["ok"])
        self.assertEqual(full_clear_status, 200)
        self.assertTrue(full_clear["ok"])
        self.assertEqual(read_full_clear_status, 200)
        self.assertFalse(read_full_clear["has_override"])

    def test_queue_route_contracts_are_exposed_with_expected_effect_metadata(self) -> None:
        workflow = exercise_local_api_route_workflow()

        self.assertEqual(workflow.queue_status, 200)
        self.assertEqual(workflow.queue_payload["schema_version"], "desktop_queue_preview.v1")
        self.assertEqual(workflow.queue_payload["rows"][0]["route_name"], "encode")



if __name__ == "__main__":
    unittest.main()
