from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer as _LocalApiServer  # noqa: E402
from app.api.commands_file_overrides import (  # noqa: E402
    LocalApiFileOverridesCommandPayloadMixin,
    _file_override_effective_payload,
    _file_override_tracks_payload_from_probe_result,
)
from app.contracts.stages import ProbeResult, make_stage_result  # noqa: E402
from app.queue.file_overrides import normalize_file_override_path, read_file_overrides, resolve_file_override_match  # noqa: E402
from app.queue.file_overrides import set_file_override_entry  # noqa: E402
from mediapipeline_desktop_app.api.routes_read import GET_ROUTE_HANDLERS  # noqa: E402
from mediapipeline_desktop_app.api.routes_command import POST_ROUTE_HANDLERS  # noqa: E402
from mediapipeline_desktop_app.models import ResolvedPaths  # noqa: E402


class _TrackMetadataHarness(LocalApiFileOverridesCommandPayloadMixin):
    def __init__(self, resolved: ResolvedPaths) -> None:
        self._resolved_paths = resolved
        self.logger = logging.getLogger("test-file-override-tracks")

    def _resolved(self) -> ResolvedPaths:
        return self._resolved_paths


class _Facade:
    service = object()


def _get_json(url: str, token: str) -> tuple[int, dict]:
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
        return response.status, json.loads(response.read().decode("utf-8"))


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
        source_movies=root / "Movies",
        source_tv=root / "TV",
        state_root=root / "State",
        file_overrides_path=root / "State" / "file_overrides.json",
    )


def _probe_result() -> ProbeResult:
    return ProbeResult.model_validate(
        {
            "probe_ok": True,
            "probe_error": "",
            "tool_path": r"C:\Tools\ffprobe.exe",
            "container": "matroska",
            "streams": [
                {
                    "index": 1,
                    "kind": "audio",
                    "codec": "ac3",
                    "language": "ENG",
                    "channels": 6,
                    "title": "English 5.1",
                    "default": True,
                    "forced": False,
                },
                {
                    "index": 2,
                    "kind": "audio",
                    "codec": "truehd",
                    "language": "eng",
                    "channels": 8,
                    "title": "Director Commentary",
                    "default": False,
                    "forced": False,
                },
                {
                    "index": 3,
                    "kind": "subtitle",
                    "codec": "subrip",
                    "language": "",
                    "title": "English Forced",
                    "default": False,
                    "forced": True,
                },
                {
                    "index": 4,
                    "kind": "subtitle",
                    "codec": "hdmv_pgs_subtitle",
                    "language": "eng",
                    "title": "English SDH",
                    "default": True,
                    "forced": False,
                },
            ],
        }
    )


def _track_payload() -> dict:
    return {
        "ok": True,
        "probe_available": True,
        "probe_source": "cache",
        "audio_tracks": [
            {
                "stream_index": 1,
                "language": "eng",
                "title": "English 5.1",
                "codec": "ac3",
                "channels": 6,
                "default": True,
                "forced": False,
            },
            {
                "stream_index": 2,
                "language": "eng",
                "title": "English Commentary",
                "codec": "ac3",
                "channels": 2,
                "default": False,
                "forced": False,
            },
            {
                "stream_index": 5,
                "language": "jpn",
                "title": "Japanese",
                "codec": "aac",
                "channels": 2,
                "default": False,
                "forced": False,
            },
        ],
        "subtitle_tracks": [
            {
                "stream_index": 3,
                "language": "eng",
                "title": "English Forced",
                "codec": "subrip",
                "default": False,
                "forced": True,
                "image_based": False,
            },
            {
                "stream_index": 4,
                "language": "eng",
                "title": "English SDH",
                "codec": "hdmv_pgs_subtitle",
                "default": True,
                "forced": False,
                "image_based": True,
            },
            {
                "stream_index": 6,
                "language": "spa",
                "title": "Spanish",
                "codec": "subrip",
                "default": False,
                "forced": False,
                "image_based": False,
            },
        ],
        "warnings": [],
    }


def _write_queue_snapshot(resolved: ResolvedPaths, rows: list[dict]) -> Path:
    snapshot_path = resolved.state_root / "Progress" / "queue_snapshot.json"  # type: ignore[operator]
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps({"produced_at": "2026-05-31T00:00:00Z", "rows": rows}, indent=2),
        encoding="utf-8",
    )
    resolved.queue_snapshot_path = snapshot_path
    return snapshot_path


def _snapshot_row(source_path: Path, *, audio_tracks: list[dict] | None = None, subtitle_tracks: list[dict] | None = None) -> dict:
    return {
        "source_path": str(source_path),
        "root_path": str(source_path.parents[1] if len(source_path.parents) > 1 else source_path.parent),
        "display_name": source_path.name,
        "relative_path": source_path.name,
        "media_kind": "movie",
        "route": "Remux",
        "queue_index": 1,
        "queue_total": 1,
        "audio_tracks": list(audio_tracks or []),
        "subtitle_tracks": list(subtitle_tracks or []),
    }


def _effective_payload(
    source_path: str,
    entry: dict,
    *,
    track_payload: dict | None = None,
) -> dict:
    return _file_override_effective_payload(
        manifest={"version": 1, "entries": {normalize_file_override_path(source_path): entry}},
        manifest_path=Path("State/file_overrides.json"),
        source_path=source_path,
        config={},
        track_payload=track_payload if track_payload is not None else _track_payload(),
    )


class FileOverrideTrackMetadataTests(unittest.TestCase):
    def test_tracks_read_route_is_registered_as_get_only(self) -> None:
        self.assertEqual(
            GET_ROUTE_HANDLERS["/api/queue/file-overrides/tracks"].method_name,
            "_file_overrides_tracks_read_payload",
        )

    def test_folder_preview_route_is_registered_as_post_only(self) -> None:
        self.assertEqual(
            POST_ROUTE_HANDLERS["/api/queue/file-overrides/folder-preview"].method_name,
            "_file_overrides_folder_preview_payload",
        )

    def test_folder_rule_route_is_registered_as_post_only(self) -> None:
        self.assertEqual(
            POST_ROUTE_HANDLERS["/api/queue/file-overrides/folder-rule"].method_name,
            "_file_overrides_folder_rule_payload",
        )

    def test_folder_preview_reports_known_files_from_queue_snapshot_without_probe_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            folder.mkdir(parents=True)
            source_a = folder / "Movie A.mkv"
            source_b = folder / "Movie B.mkv"
            source_c = resolved.source_movies / "Other" / "Movie C.mkv"  # type: ignore[operator]
            source_c.parent.mkdir(parents=True)
            audio_tracks = [
                {"stream_index": 1, "language": "eng", "codec": "ac3", "channels": 6, "title": "English 5.1"},
                {"stream_index": 2, "language": "eng", "codec": "ac3", "channels": 2, "title": "Director Commentary"},
                {"stream_index": 5, "language": "jpn", "codec": "aac", "channels": 2, "title": "Japanese"},
            ]
            subtitle_tracks = [
                {"stream_index": 3, "language": "eng", "codec": "subrip", "forced": True, "title": "English Forced"},
                {"stream_index": 4, "language": "eng", "codec": "hdmv_pgs_subtitle", "title": "English SDH"},
            ]
            _write_queue_snapshot(
                resolved,
                [
                    _snapshot_row(source_a, audio_tracks=audio_tracks, subtitle_tracks=subtitle_tracks),
                    _snapshot_row(source_b),
                    _snapshot_row(source_c, audio_tracks=audio_tracks),
                ],
            )
            harness = _TrackMetadataHarness(resolved)

            with patch("app.api.commands_file_overrides.run_probe_stage") as run_probe:
                payload = harness._file_overrides_folder_preview_payload(
                    {
                        "folder_path": str(folder),
                        "proposed_override": {
                            "audio": {"keepTracks": [{"language": "eng"}]},
                            "subtitles": {"keepTracks": [{"language": "eng", "forced": True}]},
                        },
                        "options": {"sample_limit": 1, "use_cached_track_metadata_only": True},
                    }
                )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["preview_only"])
            self.assertEqual(payload["schema_version"], "queue_file_override_folder_preview.v1")
            self.assertEqual(payload["impact"]["known_file_count"], 2)
            self.assertEqual(payload["impact"]["previewed_file_count"], 1)
            self.assertTrue(payload["impact"]["partial"])
            self.assertTrue(payload["impact"]["future_files_would_match"])
            self.assertEqual(payload["sample_rows"][0]["audio_track_count"], 3)
            self.assertTrue(payload["sample_rows"][0]["matched_audio_tracks"])
            warning_text = "\n".join(item["message"] for item in payload["warnings"])
            self.assertIn("multiple audio tracks", warning_text)
            self.assertFalse(resolved.file_overrides_path.exists())  # type: ignore[union-attr]
            run_probe.assert_not_called()

    def test_folder_preview_validates_folder_scope_and_rejects_file_only_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            folder.mkdir(parents=True)
            harness = _TrackMetadataHarness(resolved)

            outside = root / "Outside"
            outside.mkdir()
            outside_payload = harness._file_overrides_folder_preview_payload(
                {"folder_path": str(outside), "proposed_override": {"audio": {"keepTracks": [{"language": "eng"}]}}}
            )
            stream_index_payload = harness._file_overrides_folder_preview_payload(
                {
                    "folder_path": str(folder),
                    "proposed_override": {"audio": {"keepTracks": [{"streamIndex": 1, "language": "eng"}]}},
                }
            )
            raw_map_payload = harness._file_overrides_folder_preview_payload(
                {
                    "folder_path": str(folder),
                    "proposed_override": {"audio": {"keepTracks": [{"language": "eng", "map": "0:a:0"}]}},
                }
            )
            title_contains_payload = harness._file_overrides_folder_preview_payload(
                {
                    "folder_path": str(folder),
                    "proposed_override": {"subtitles": {"dropTracks": [{"language": "eng", "titleContains": "SDH"}]}},
                }
            )

            self.assertFalse(outside_payload["ok"])
            self.assertIn("outside configured", outside_payload["message"].lower())
            self.assertFalse(stream_index_payload["ok"])
            self.assertIn("streamIndex", "\n".join(stream_index_payload["errors"]))
            self.assertFalse(raw_map_payload["ok"])
            self.assertIn("map", "\n".join(raw_map_payload["errors"]))
            self.assertFalse(title_contains_payload["ok"])
            self.assertIn("titleContains", "\n".join(title_contains_payload["errors"]))

    def test_folder_preview_reports_exact_and_deeper_folder_override_conflicts_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            nested = folder / "Subfolder"
            nested.mkdir(parents=True)
            exact_source = folder / "Movie A.mkv"
            nested_source = nested / "Movie B.mkv"
            _write_queue_snapshot(
                resolved,
                [
                    _snapshot_row(exact_source, audio_tracks=[{"stream_index": 1, "language": "eng", "codec": "ac3"}]),
                    _snapshot_row(nested_source, audio_tracks=[{"stream_index": 1, "language": "eng", "codec": "ac3"}]),
                ],
            )
            resolved.file_overrides_path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                exact_source,
                {"audio": {"keepTracks": [{"language": "jpn"}]}},
            )
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                nested,
                {"audio": {"dropTracks": [{"language": "eng"}]}},
            )
            before = resolved.file_overrides_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
            harness = _TrackMetadataHarness(resolved)

            payload = harness._file_overrides_folder_preview_payload(
                {
                    "folder_path": str(folder),
                    "proposed_override": {"audio": {"keepTracks": [{"language": "eng"}]}},
                    "options": {"sample_limit": 25},
                }
            )
            after = resolved.file_overrides_path.read_text(encoding="utf-8")  # type: ignore[union-attr]

            self.assertTrue(payload["ok"])
            reasons = {conflict["reason"] for conflict in payload["conflicts"]}
            self.assertIn("exact_file_override_wins", reasons)
            self.assertIn("deeper_folder_override_wins", reasons)
            self.assertEqual(before, after)

    def test_folder_preview_reports_missing_snapshot_as_partial_preview(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            folder.mkdir(parents=True)
            harness = _TrackMetadataHarness(resolved)

            payload = harness._file_overrides_folder_preview_payload(
                {"folder_path": str(folder), "proposed_override": {"audio": {"keepTracks": [{"language": "eng"}]}}}
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["impact"]["known_file_count"], 0)
            self.assertTrue(payload["impact"]["partial"])
            warning_text = "\n".join(item["message"] for item in payload["warnings"])
            self.assertIn("Queue snapshot", warning_text)

    def test_folder_rule_saves_valid_language_rule_and_preserves_resolver_precedence(self) -> None:
        confirmation = {
            "acknowledged_future_files": True,
            "acknowledged_file_overrides_win": True,
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            nested = folder / "Season 01"
            nested.mkdir(parents=True)
            exact_source = folder / "Movie A.mkv"
            nested_source = nested / "Episode 01.mkv"
            harness = _TrackMetadataHarness(resolved)

            saved = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(folder),
                    "override": {
                        "audio": {"keepTracks": [{"language": "ENG"}]},
                        "subtitles": {"keepTracks": [{"language": "eng", "forced": True}]},
                    },
                    "confirmation": confirmation,
                }
            )
            nested_saved = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(nested),
                    "override": {"audio": {"dropTracks": [{"language": "jpn"}]}},
                    "confirmation": confirmation,
                }
            )
            exact_saved = harness._file_overrides_payload(
                {
                    "path": str(exact_source),
                    "audio": {"keepTracks": [{"language": "spa"}]},
                }
            )

            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            folder_entry = manifest["entries"][normalize_file_override_path(folder)]
            exact_match = resolve_file_override_match(manifest, exact_source)
            nested_match = resolve_file_override_match(manifest, nested_source)

        self.assertTrue(saved["ok"])
        self.assertEqual(saved["command"], "queue.file_overrides.folder_rule")
        self.assertEqual(saved["folder_rule"]["normalized_folder_path"], normalize_file_override_path(folder))
        self.assertEqual(folder_entry["audio"]["keepTracks"], [{"language": "eng"}])
        self.assertEqual(folder_entry["subtitles"]["keepTracks"], [{"language": "eng", "forced": True}])
        self.assertTrue(nested_saved["ok"])
        self.assertTrue(exact_saved["ok"])
        self.assertEqual(exact_match["scope"], "file")
        self.assertEqual(exact_match["entry"]["audio"]["keepTracks"], [{"language": "spa"}])
        self.assertEqual(nested_match["scope"], "folder")
        self.assertEqual(nested_match["matched_path"], normalize_file_override_path(nested))
        self.assertEqual(nested_match["entry"]["audio"]["dropTracks"], [{"language": "jpn"}])

    def test_folder_rule_rejects_unsafe_selectors_invalid_scope_and_missing_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            folder.mkdir(parents=True)
            harness = _TrackMetadataHarness(resolved)
            confirmation = {
                "acknowledged_future_files": True,
                "acknowledged_file_overrides_win": True,
            }
            outside = root / "Outside"
            outside.mkdir()

            missing_confirmation = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(folder),
                    "override": {"audio": {"keepTracks": [{"language": "eng"}]}},
                }
            )
            stream_index = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(folder),
                    "override": {"audio": {"keepTracks": [{"streamIndex": 1, "language": "eng"}]}},
                    "confirmation": confirmation,
                }
            )
            raw_map = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(folder),
                    "override": {"audio": {"keepTracks": [{"language": "eng", "map": "0:a:0"}]}},
                    "confirmation": confirmation,
                }
            )
            invalid_path = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(outside),
                    "override": {"audio": {"keepTracks": [{"language": "eng"}]}},
                    "confirmation": confirmation,
                }
            )
            library_root = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(resolved.source_movies),
                    "override": {"audio": {"keepTracks": [{"language": "eng"}]}},
                    "confirmation": confirmation,
                }
            )

        self.assertFalse(missing_confirmation["ok"])
        self.assertIn("confirmation", "\n".join(missing_confirmation["errors"]))
        self.assertFalse(stream_index["ok"])
        self.assertIn("streamIndex", "\n".join(stream_index["errors"]))
        self.assertFalse(raw_map["ok"])
        self.assertIn("map", "\n".join(raw_map["errors"]))
        self.assertFalse(invalid_path["ok"])
        self.assertIn("outside configured", invalid_path["message"].lower())
        self.assertFalse(library_root["ok"])
        self.assertIn("Library settings", library_root["message"])

    def test_folder_rule_clear_only_removes_that_folder_entry_and_file_clear_preserves_folder_rule(self) -> None:
        confirmation = {
            "acknowledged_future_files": True,
            "acknowledged_file_overrides_win": True,
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            nested = folder / "Season 01"
            nested.mkdir(parents=True)
            source = folder / "Movie A.mkv"
            harness = _TrackMetadataHarness(resolved)

            folder_saved = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(folder),
                    "override": {"audio": {"keepTracks": [{"language": "eng"}]}},
                    "confirmation": confirmation,
                }
            )
            nested_saved = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(nested),
                    "override": {"subtitles": {"dropTracks": [{"language": "und"}]}},
                    "confirmation": confirmation,
                }
            )
            file_saved = harness._file_overrides_payload(
                {
                    "path": str(source),
                    "audio": {"dropTracks": [{"language": "jpn"}]},
                }
            )
            file_cleared = harness._file_overrides_payload({"path": str(source), "clear": True})
            after_file_clear = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            folder_cleared = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(folder),
                    "clear": True,
                }
            )
            after_folder_clear = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

        self.assertTrue(folder_saved["ok"])
        self.assertTrue(nested_saved["ok"])
        self.assertTrue(file_saved["ok"])
        self.assertTrue(file_cleared["ok"])
        self.assertIn(normalize_file_override_path(folder), after_file_clear["entries"])
        self.assertNotIn(normalize_file_override_path(source), after_file_clear["entries"])
        self.assertTrue(folder_cleared["ok"])
        self.assertTrue(folder_cleared["folder_rule"]["cleared"])
        self.assertNotIn(normalize_file_override_path(folder), after_folder_clear["entries"])
        self.assertIn(normalize_file_override_path(nested), after_folder_clear["entries"])

    def test_probe_result_normalizes_audio_and_subtitle_tracks(self) -> None:
        payload = _file_override_tracks_payload_from_probe_result(
            source_path=r"C:\Media\Movie.mkv",
            probe_result=_probe_result(),
            probe_source="stage_probe",
        )

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["probe_available"])
        self.assertEqual(payload["probe_source"], "stage_probe")
        self.assertEqual(len(payload["audio_tracks"]), 2)
        self.assertEqual(payload["audio_tracks"][0]["stream_index"], 1)
        self.assertEqual(payload["audio_tracks"][0]["language"], "eng")
        self.assertTrue(payload["audio_tracks"][0]["default"])
        self.assertFalse(payload["audio_tracks"][0]["forced"])
        self.assertFalse(payload["audio_tracks"][0]["commentary"])
        self.assertEqual(payload["audio_tracks"][1]["language"], "eng")
        self.assertTrue(payload["audio_tracks"][1]["commentary"])
        self.assertIn("Commentary", payload["audio_tracks"][1]["display"])

        self.assertEqual(len(payload["subtitle_tracks"]), 2)
        self.assertEqual(payload["subtitle_tracks"][0]["language"], "und")
        self.assertTrue(payload["subtitle_tracks"][0]["forced"])
        self.assertFalse(payload["subtitle_tracks"][0]["image_based"])
        self.assertTrue(payload["subtitle_tracks"][1]["default"])
        self.assertTrue(payload["subtitle_tracks"][1]["hearing_impaired"])
        self.assertTrue(payload["subtitle_tracks"][1]["image_based"])

    def test_tracks_endpoint_validates_path_and_does_not_write_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            source.parent.mkdir(parents=True)
            source.write_bytes(b"fake media")
            harness = _TrackMetadataHarness(resolved)
            stage_result = make_stage_result(
                stage="probe",
                ok=True,
                started_at=datetime.now(timezone.utc),
                data=_probe_result(),
            )

            with patch("app.api.commands_file_overrides.run_probe_stage", return_value=stage_result) as run_probe:
                payload = harness._file_overrides_tracks_read_payload({"path": [str(source)]})

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["probe_available"])
            run_probe.assert_called_once()
            self.assertFalse(resolved.file_overrides_path.exists())  # type: ignore[union-attr]

            outside = root / "Outside" / "Movie.mkv"
            invalid = harness._file_overrides_tracks_read_payload({"path": [str(outside)]})
            self.assertFalse(invalid["ok"])
            self.assertIn("outside configured", invalid["message"].lower())

    def test_tracks_endpoint_is_available_through_local_api_get_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            source.parent.mkdir(parents=True)
            source.write_bytes(b"fake media")
            stage_result = make_stage_result(
                stage="probe",
                ok=True,
                started_at=datetime.now(timezone.utc),
                data=_probe_result(),
            )
            server = _LocalApiServer(_Facade(), token="tracks-token", resolved_provider=lambda: resolved)

            try:
                server.start()
                with patch("app.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
                    status, payload = _get_json(
                        f"{server.url}/api/queue/file-overrides/tracks?path={quote(str(source))}",
                        "tracks-token",
                    )
            finally:
                server.stop()

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["schema_version"], "queue_file_override_tracks.v1")
            self.assertEqual(payload["audio_tracks"][0]["stream_index"], 1)

    def test_tracks_endpoint_returns_unavailable_for_missing_file_without_probe(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            missing = resolved.source_tv / "Show" / "Missing.mkv"  # type: ignore[operator]
            harness = _TrackMetadataHarness(resolved)

            with patch("app.api.commands_file_overrides.run_probe_stage") as run_probe:
                payload = harness._file_overrides_tracks_read_payload({"path": [str(missing)]})

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["probe_available"])
            self.assertEqual(payload["audio_tracks"], [])
            self.assertEqual(payload["subtitle_tracks"], [])
            self.assertTrue(payload["warnings"])
            run_probe.assert_not_called()

    def test_tracks_endpoint_returns_unavailable_for_probe_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            source.parent.mkdir(parents=True)
            source.write_bytes(b"fake media")
            harness = _TrackMetadataHarness(resolved)
            stage_result = make_stage_result(
                stage="probe",
                ok=False,
                started_at=datetime.now(timezone.utc),
                error={"code": "stage.timeout", "message": "Stage process exceeded timeout."},
            )

            with patch("app.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
                payload = harness._file_overrides_tracks_read_payload({"path": [str(source)]})

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["probe_available"])
            self.assertEqual(payload["probe_source"], "stage_probe")
            self.assertIn("timeout", payload["warnings"][0]["message"].lower())

    def test_save_exact_track_selectors_validates_against_probe_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            source.parent.mkdir(parents=True)
            source.write_bytes(b"fake media")
            harness = _TrackMetadataHarness(resolved)
            stage_result = make_stage_result(
                stage="probe",
                ok=True,
                started_at=datetime.now(timezone.utc),
                data=_probe_result(),
            )

            with patch("app.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
                saved = harness._file_overrides_payload(
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [
                                {"streamIndex": 1, "language": "eng", "codec": "ac3", "channels": 6}
                            ]
                        },
                        "subtitles": {
                            "keepTracks": [
                                {"streamIndex": 3, "language": "und", "codec": "subrip", "forced": True}
                            ]
                        },
                    }
                )
                wrong_type = harness._file_overrides_payload(
                    {"path": str(source), "audio": {"keepTracks": [{"streamIndex": 3}]}}
                )
                missing = harness._file_overrides_payload(
                    {"path": str(source), "subtitles": {"keepTracks": [{"streamIndex": 99}]}}
                )
                signature_mismatch = harness._file_overrides_payload(
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [
                                {"streamIndex": 1, "language": "jpn", "codec": "ac3", "channels": 6}
                            ]
                        },
                    }
                )
                raw_map = harness._file_overrides_payload(
                    {
                        "path": str(source),
                        "audio": {"keepTracks": [{"streamIndex": 1, "map": "0:a:0"}]},
                    }
                )

            self.assertTrue(saved["ok"])
            entry = saved["entries"][normalize_file_override_path(source)]
            self.assertEqual(entry["audio"]["keepTracks"][0]["streamIndex"], 1)
            self.assertFalse(wrong_type["ok"])
            self.assertIn("does not target an audio stream", "\n".join(wrong_type["errors"]))
            self.assertFalse(missing["ok"])
            self.assertIn("not available in detected subtitle streams", "\n".join(missing["errors"]))
            self.assertFalse(signature_mismatch["ok"])
            self.assertIn("does not match detected stream 1 language 'eng'", "\n".join(signature_mismatch["errors"]))
            self.assertFalse(raw_map["ok"])
            self.assertIn("Unsupported audio.keepTracks[0] field(s): map", "\n".join(raw_map["errors"]))

    def test_save_exact_track_selector_warns_when_probe_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            source.parent.mkdir(parents=True)
            source.write_bytes(b"fake media")
            harness = _TrackMetadataHarness(resolved)
            stage_result = make_stage_result(
                stage="probe",
                ok=False,
                started_at=datetime.now(timezone.utc),
                error={"code": "stage.timeout", "message": "Stage process exceeded timeout."},
            )

            with patch("app.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
                payload = harness._file_overrides_payload(
                    {"path": str(source), "audio": {"keepTracks": [{"streamIndex": 1}]}}
                )

            self.assertTrue(payload["ok"])
            self.assertIn("Track metadata is unavailable", "\n".join(payload.get("warnings", [])))

    def test_effective_payload_includes_track_metadata_and_selection_preview(self) -> None:
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {
                "audio": {"keepTracks": [{"language": "eng"}]},
                "subtitles": {"dropTracks": [{"language": "spa"}]},
            },
        )

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["track_metadata"]["available"])
        self.assertEqual(payload["track_metadata"]["probe_source"], "cache")
        self.assertEqual(len(payload["track_metadata"]["audio_tracks"]), 3)
        self.assertEqual(payload["effective_drawer_fields"]["audioKeepLanguages"]["source"], "file_override")
        self.assertEqual(payload["sources"]["audio.keepTracks"], "file_override")

        audio_preview = payload["track_selection_preview"]["audio"]
        self.assertEqual(audio_preview["kept_stream_indexes"], [1, 2])
        self.assertEqual(audio_preview["dropped_stream_indexes"], [5])
        self.assertEqual(audio_preview["kept_stream_sources"]["1"]["field"], "audio.keepTracks")
        self.assertEqual(audio_preview["dropped_stream_sources"]["5"]["field"], "audio.keepTracks")
        self.assertIn("multiple audio tracks", "\n".join(item["message"] for item in audio_preview["warnings"]))

        subtitle_preview = payload["track_selection_preview"]["subtitles"]
        self.assertEqual(subtitle_preview["kept_stream_indexes"], [3, 4])
        self.assertEqual(subtitle_preview["dropped_stream_indexes"], [6])
        self.assertEqual(subtitle_preview["dropped_stream_sources"]["6"]["field"], "subtitles.dropTracks")

    def test_effective_payload_marks_track_metadata_unavailable_when_probe_unavailable(self) -> None:
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {"audio": {"keepTracks": [{"language": "eng"}]}},
            track_payload={
                "probe_available": False,
                "probe_source": "unavailable",
                "audio_tracks": [],
                "subtitle_tracks": [],
                "warnings": [{"field": "track_metadata", "message": "Track metadata is not available."}],
            },
        )

        self.assertFalse(payload["track_metadata"]["available"])
        self.assertEqual(payload["track_metadata"]["audio_tracks"], [])
        self.assertFalse(payload["track_selection_preview"]["audio"]["available"])
        self.assertIn("not available", payload["track_selection_preview"]["audio"]["warnings"][0]["message"])

    def test_effective_payload_warns_for_missing_languages_and_forced_rules(self) -> None:
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {
                "audio": {
                    "dropTracks": [{"language": "fra"}],
                    "keepTracks": [{"streamIndex": 99}],
                },
                "subtitles": {"keepTracks": [{"language": "spa", "forced": True}]},
            },
        )

        audio_warnings = "\n".join(
            item["message"] for item in payload["track_selection_preview"]["audio"]["warnings"]
        )
        subtitle_warnings = "\n".join(
            item["message"] for item in payload["track_selection_preview"]["subtitles"]["warnings"]
        )
        self.assertIn("Language 'fra' matches no audio tracks.", audio_warnings)
        self.assertIn("Stream index 99 is not available", audio_warnings)
        self.assertIn("Forced subtitle selector matches no detected forced subtitle tracks.", subtitle_warnings)

    def test_effective_payload_exact_selector_disambiguates_duplicate_languages(self) -> None:
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {
                "audio": {"keepTracks": [{"streamIndex": 2, "language": "eng", "codec": "ac3", "channels": 2}]},
                "subtitles": {"keepTracks": [{"streamIndex": 3, "language": "eng", "forced": True}]},
            },
        )

        audio_preview = payload["track_selection_preview"]["audio"]
        subtitle_preview = payload["track_selection_preview"]["subtitles"]
        self.assertEqual(audio_preview["kept_stream_indexes"], [2])
        self.assertEqual(audio_preview["dropped_stream_indexes"], [1, 5])
        self.assertEqual(subtitle_preview["kept_stream_indexes"], [3])
        self.assertEqual(subtitle_preview["dropped_stream_indexes"], [4, 6])
        audio_warnings = "\n".join(item["message"] for item in audio_preview["warnings"])
        self.assertNotIn("multiple audio tracks", audio_warnings)


if __name__ == "__main__":
    unittest.main()
