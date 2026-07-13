from __future__ import annotations

from datetime import datetime, timezone, UTC
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.parse import quote
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer as _LocalApiServer  # noqa: E402
from mediapipeline.core.api.commands_file_overrides import (  # noqa: E402
    LocalApiFileOverridesCommandPayloadMixin,
    _file_override_effective_payload,
    _file_override_tracks_payload_from_probe_result,
)
from mediapipeline.core.api.file_overrides.remux_pilot import (  # noqa: E402
    file_override_remux_pilot_auto_promote_payload,
)
from mediapipeline.contracts.stages import ProbeResult, make_stage_result  # noqa: E402
from mediapipeline.core.queue.file_overrides import (  # noqa: E402
    FILE_OVERRIDE_BATCH_METADATA_KEY,
    FileOverrideManifestReadError,
    FileOverrideValidationError,
)
from mediapipeline.core.queue.file_overrides import normalize_file_override_path, read_file_overrides, resolve_file_override_match  # noqa: E402
from mediapipeline.core.queue.file_overrides import set_file_override_entry  # noqa: E402
from mediapipeline.core.queue.remux_pilot_auto_service import RemuxPilotAutoPromotionServiceMixin  # noqa: E402
from mediapipeline.desktop.api.routes_read import GET_ROUTE_HANDLERS  # noqa: E402
from mediapipeline.desktop.api.routes_command import POST_ROUTE_HANDLERS  # noqa: E402
from mediapipeline.desktop.models import ResolvedPaths  # noqa: E402


class _TrackMetadataHarness(LocalApiFileOverridesCommandPayloadMixin):
    def __init__(self, resolved: ResolvedPaths) -> None:
        self._resolved_paths = resolved
        self.logger = logging.getLogger("test-file-override-tracks")

    def _resolved(self) -> ResolvedPaths:
        return self._resolved_paths


class _Facade:
    service = object()


class _RemuxPilotAutoPromotionHarness(RemuxPilotAutoPromotionServiceMixin):
    def __init__(self, resolved: ResolvedPaths) -> None:
        self.logger = logging.getLogger("test-remux-pilot-auto-promotion")
        self._initialize_remux_pilot_auto_promotion()
        self.configure_remux_pilot_auto_promotion(
            resolved_provider=lambda: resolved,
            payload_builder=file_override_remux_pilot_auto_promote_payload,
        )


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
        completed_manifest_path=root / "State" / "Completed" / "completed_jobs.jsonl",
    )


def _probe_result() -> ProbeResult:
    return ProbeResult.model_validate(
        {
            "probe_ok": True,
            "probe_error": "",
            "tool_path": r"C:\Tools\ffprobe.exe",
            "container": "matroska",
            "duration_seconds": 5400.0,
            "bitrate_bps": 17_200_000,
            "video_codec": "hevc",
            "width": 3840,
            "height": 2160,
            "is_hdr": True,
            "color_transfer": "smpte2084",
            "container_bitrate_mbps": 17.2,
            "estimated_bitrate_mbps": 15.907,
            "size_bytes": 10 * 1024 * 1024 * 1024,
            "streams": [
                {
                    "index": 0,
                    "kind": "video",
                    "codec": "hevc",
                    "bitrate_bps": 18_000_000,
                    "width": 3840,
                    "height": 2160,
                },
                {
                    "index": 1,
                    "kind": "audio",
                    "codec": "ac3",
                    "language": "ENG",
                    "bitrate_bps": 640_000,
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
                    "bitrate_bps": 3_200_000,
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


def _probe_result_without_stream(stream_index: int) -> ProbeResult:
    data = _probe_result().model_dump(mode="json")
    data["streams"] = [
        stream for stream in data.get("streams", [])
        if int(stream.get("index", -1)) != stream_index
    ]
    return ProbeResult.model_validate(data)


def _track_payload() -> dict:
    return {
        "ok": True,
        "probe_available": True,
        "probe_source": "cache",
        "source_info": {
            "available": True,
            "probe_source": "cache",
            "path": r"C:\Media\Movie.mkv",
            "file_size_bytes": 10 * 1024 * 1024 * 1024,
            "file_size_display": "10 GB",
            "duration_seconds": 5400.0,
            "duration_display": "1h 30m",
            "container": "matroska",
            "overall_bitrate_bps": 17_200_000,
            "overall_bitrate_mbps": 17.2,
            "overall_bitrate_display": "17.2 Mbps",
            "estimated_bitrate_mbps": 15.907,
            "estimated_bitrate_display": "15.907 Mbps",
            "estimated_bitrate_basis": "file_size_duration",
            "primary_video": {
                "available": True,
                "stream_index": 0,
                "codec": "hevc",
                "width": 3840,
                "height": 2160,
                "resolution_display": "3840x2160",
                "is_hdr": True,
                "hdr_format": "smpte2084",
                "bitrate_bps": 18_000_000,
                "bitrate_mbps": 18.0,
                "bitrate_display": "18 Mbps",
            },
            "missing_facts": [],
        },
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


def _write_completed_manifest(resolved: ResolvedPaths, rows: list[dict]) -> Path:
    manifest_path = resolved.completed_manifest_path  # type: ignore[assignment]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _completed_pilot_row(
    source_path: Path,
    *,
    route: str = "remux",
    route_reason_code: str = "oversized_encode_remux_fallback",
    media_type: str = "tv",
    publish_state: str = "published",
    size_policy: dict | None = None,
) -> dict:
    return {
        "source_path": str(source_path),
        "output_path": str(source_path.with_suffix(".mkv")),
        "encoded_at": "2026-06-19T12:00:00Z",
        "media_type": media_type,
        "route": route,
        "route_reason_code": route_reason_code,
        "publish_state": publish_state,
        "size_policy": size_policy if size_policy is not None else {
            "mode": "fallback_remux",
            "should_fallback_remux": True,
            "fallback_remux_triggered": True,
        },
    }


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


def _tv_snapshot_row(
    tv_root: Path,
    show_name: str,
    season_folder: str,
    file_name: str,
    *,
    season_number: int = 1,
    episode_number: int = 1,
    root_path: Path | None = None,
    media_kind: str = "tv",
) -> dict:
    source_root = root_path or tv_root
    source_path = source_root / show_name / season_folder / file_name
    return {
        "source_path": str(source_path),
        "root_path": str(source_root),
        "display_name": file_name,
        "relative_path": str(Path(show_name) / season_folder / file_name),
        "media_kind": media_kind,
        "route": "Remux",
        "season_number": season_number,
        "episode_number": episode_number,
    }


def _series_action_by_file(payload: dict, file_name: str) -> str:
    for row in payload.get("rows", []):
        if str(row.get("display_name") or "") == file_name:
            return str(row.get("action") or "")
    raise AssertionError(f"Preview row not found for {file_name}")


def _effective_payload(
    source_path: str,
    entry: dict,
    *,
    config: dict | None = None,
    manifest_entries: dict[str, dict] | None = None,
    track_payload: dict | None = None,
) -> dict:
    entries = manifest_entries if manifest_entries is not None else {normalize_file_override_path(source_path): entry}
    return _file_override_effective_payload(
        manifest={"version": 1, "entries": entries},
        manifest_path=Path("State/file_overrides.json"),
        source_path=source_path,
        config=config or {},
        track_payload=track_payload if track_payload is not None else _track_payload(),
    )


def _resolved_track(payload: dict, kind: str, stream_index: int) -> dict:
    section_key = "audio" if kind == "audio" else "subtitles"
    tracks = payload["resolved_track_actions"][section_key]["tracks"]
    for track in tracks:
        if track["stream_index"] == stream_index:
            return track
    raise AssertionError(f"resolved {kind} stream {stream_index} not found")


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

    def test_series_preview_and_apply_routes_are_registered_as_post_only(self) -> None:
        self.assertEqual(
            POST_ROUTE_HANDLERS["/api/queue/file-overrides/series-preview"].method_name,
            "_file_overrides_series_preview_payload",
        )
        self.assertEqual(
            POST_ROUTE_HANDLERS["/api/queue/file-overrides/series-apply"].method_name,
            "_file_overrides_series_apply_payload",
        )
        self.assertEqual(
            POST_ROUTE_HANDLERS["/api/queue/file-overrides/series-clear-preview"].method_name,
            "_file_overrides_series_clear_preview_payload",
        )
        self.assertEqual(
            POST_ROUTE_HANDLERS["/api/queue/file-overrides/series-clear-apply"].method_name,
            "_file_overrides_series_clear_apply_payload",
        )
        self.assertEqual(
            POST_ROUTE_HANDLERS["/api/queue/file-overrides/remux-pilot-promote"].method_name,
            "_file_overrides_remux_pilot_promote_payload",
        )

    def test_series_preview_detects_show_root_protects_manual_and_apply_replaces_prior_batch(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            alt_tv_root = root / "AltTV"
            rows = [
                _tv_snapshot_row(tv_root, "Example Show", "Season 01", "Example.Show.S01E01.mkv", season_number=1, episode_number=1),
                _tv_snapshot_row(tv_root, "Example Show", "Season 01", "Example.Show.S01E02.mkv", season_number=1, episode_number=2),
                _tv_snapshot_row(tv_root, "Example Show", "Specials", "Example.Show.S00E01.mkv", season_number=0, episode_number=1),
                _tv_snapshot_row(alt_tv_root, "Example Show", "Season 01", "Example.Show.S01E03.mkv", root_path=alt_tv_root, season_number=1, episode_number=3),
                _tv_snapshot_row(tv_root, "Other Show", "Season 01", "Other.Show.S01E01.mkv", season_number=1, episode_number=1),
            ]
            _write_queue_snapshot(resolved, rows)
            harness = _TrackMetadataHarness(resolved)
            selected = Path(rows[0]["source_path"])
            manual = Path(rows[1]["source_path"])
            special = Path(rows[2]["source_path"])
            show_folder = tv_root / "Example Show"

            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                show_folder,
                {"subtitles": {"keepTracks": [{"language": "eng"}]}},
            )
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                manual,
                {"audio": {"maxChannels": 6}},
            )
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                special,
                {"audio": {"maxChannels": 8}},
                batch_metadata={"origin": "series_batch", "batch_id": "series-old"},
                replace_existing=True,
            )

            preview = harness._file_overrides_series_preview_payload(
                {
                    "path": str(selected),
                    "proposed_override": {"audio": {"maxChannels": 2}, "routing": {"profile": "remux"}},
                }
            )
            applied = harness._file_overrides_series_apply_payload(
                {
                    "path": str(selected),
                    "proposed_override": {"audio": {"maxChannels": 2}, "routing": {"profile": "remux"}},
                    "confirm_apply": True,
                    "preview_fingerprint": preview["preview_fingerprint"],
                }
            )
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            entries = manifest["entries"]

        self.assertTrue(preview["ok"])
        self.assertEqual(preview["schema_version"], "queue_file_override_series_preview.v1")
        self.assertEqual(preview["detected"]["show_name"], "Example Show")
        self.assertEqual(preview["counts"]["will_update"], 1)
        self.assertEqual(preview["counts"]["replace_prior_batch"], 1)
        self.assertEqual(preview["counts"]["protected_manual"], 1)
        self.assertEqual(preview["counts"]["skipped"], 1)
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S01E01.mkv"), "will_update")
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S01E02.mkv"), "protected_manual")
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S00E01.mkv"), "replace_prior_batch")
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S01E03.mkv"), "skipped")
        self.assertFalse(any(row.get("display_name") == "Other.Show.S01E01.mkv" for row in preview["rows"]))

        self.assertTrue(applied["ok"])
        self.assertEqual(applied["command"], "queue.file_overrides.series_apply")
        selected_entry = entries[normalize_file_override_path(selected)]
        manual_entry = entries[normalize_file_override_path(manual)]
        special_entry = entries[normalize_file_override_path(special)]
        self.assertEqual(selected_entry["audio"]["maxChannels"], 2)
        self.assertEqual(special_entry["audio"]["maxChannels"], 2)
        self.assertEqual(manual_entry["audio"]["maxChannels"], 6)
        self.assertIn(FILE_OVERRIDE_BATCH_METADATA_KEY, selected_entry)
        self.assertIn(FILE_OVERRIDE_BATCH_METADATA_KEY, special_entry)
        self.assertNotIn(FILE_OVERRIDE_BATCH_METADATA_KEY, manual_entry)
        self.assertNotEqual(special_entry[FILE_OVERRIDE_BATCH_METADATA_KEY]["batch_id"], "series-old")

    def test_series_clear_preview_and_apply_clear_exact_current_series_entries_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            alt_tv_root = root / "AltTV"
            rows = [
                _tv_snapshot_row(tv_root, "Example Show", "Season 01", "Example.Show.S01E01.mkv", season_number=1, episode_number=1),
                _tv_snapshot_row(tv_root, "Example Show", "Season 01", "Example.Show.S01E02.mkv", season_number=1, episode_number=2),
                _tv_snapshot_row(tv_root, "Example Show", "Specials", "Example.Show.S00E01.mkv", season_number=0, episode_number=1),
                _tv_snapshot_row(alt_tv_root, "Example Show", "Season 01", "Example.Show.S01E03.mkv", root_path=alt_tv_root, season_number=1, episode_number=3),
                _tv_snapshot_row(tv_root, "Other Show", "Season 01", "Other.Show.S01E01.mkv", season_number=1, episode_number=1),
            ]
            _write_queue_snapshot(resolved, rows)
            harness = _TrackMetadataHarness(resolved)
            selected = Path(rows[0]["source_path"])
            manual = Path(rows[1]["source_path"])
            special = Path(rows[2]["source_path"])
            other = Path(rows[4]["source_path"])
            show_folder = tv_root / "Example Show"

            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                show_folder,
                {"subtitles": {"keepTracks": [{"language": "eng"}]}},
            )
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                manual,
                {"audio": {"maxChannels": 6}},
            )
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                special,
                {"audio": {"maxChannels": 8}},
                batch_metadata={"origin": "series_batch", "batch_id": "series-old"},
                replace_existing=True,
            )
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                other,
                {"routing": {"profile": "encode"}},
            )

            preview = harness._file_overrides_series_clear_preview_payload({"path": str(selected)})
            cleared = harness._file_overrides_series_clear_apply_payload(
                {
                    "path": str(selected),
                    "confirm_apply": True,
                    "preview_fingerprint": preview["preview_fingerprint"],
                }
            )
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            entries = manifest["entries"]

        self.assertTrue(preview["ok"])
        self.assertEqual(preview["schema_version"], "queue_file_override_series_clear_preview.v1")
        self.assertEqual(preview["detected"]["show_name"], "Example Show")
        self.assertEqual(preview["counts"]["clear_manual"], 1)
        self.assertEqual(preview["counts"]["clear_batch"], 1)
        self.assertEqual(preview["counts"]["inherited"], 1)
        self.assertEqual(preview["counts"]["skipped"], 1)
        self.assertEqual(preview["counts"]["eligible_clear_count"], 2)
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S01E01.mkv"), "inherited")
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S01E02.mkv"), "clear_manual")
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S00E01.mkv"), "clear_batch")
        self.assertEqual(_series_action_by_file(preview, "Example.Show.S01E03.mkv"), "skipped")

        self.assertTrue(cleared["ok"])
        self.assertEqual(cleared["command"], "queue.file_overrides.series_clear_apply")
        self.assertIn(normalize_file_override_path(show_folder), entries)
        self.assertIn(normalize_file_override_path(other), entries)
        self.assertNotIn(normalize_file_override_path(manual), entries)
        self.assertNotIn(normalize_file_override_path(special), entries)

    def test_series_preview_blocks_exact_track_selectors_that_do_not_validate_for_every_row(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            rows = [
                _tv_snapshot_row(tv_root, "Exact Show", "Season 01", "Exact.Show.S01E01.mkv"),
                _tv_snapshot_row(tv_root, "Exact Show", "Season 01", "Exact.Show.S01E02.mkv", episode_number=2),
            ]
            for row in rows:
                source = Path(str(row["source_path"]))
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(b"fake media")
            _write_queue_snapshot(resolved, rows)
            harness = _TrackMetadataHarness(resolved)
            selected = Path(str(rows[0]["source_path"]))
            missing_exact_stream = Path(str(rows[1]["source_path"]))
            selected_probe = make_stage_result(
                stage="probe",
                ok=True,
                started_at=datetime.now(UTC),
                data=_probe_result(),
            )
            missing_probe = make_stage_result(
                stage="probe",
                ok=True,
                started_at=datetime.now(UTC),
                data=_probe_result_without_stream(4),
            )

            def probe_side_effect(payload: dict, _options: object):
                source_path = str(payload.get("scratch_path") or "")
                return selected_probe if source_path == str(selected) else missing_probe

            proposed_override = {
                "subtitles": {
                    "burnTrack": {
                        "streamIndex": 4,
                        "language": "eng",
                        "codec": "hdmv_pgs_subtitle",
                        "forced": False,
                    }
                }
            }
            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage", side_effect=probe_side_effect):
                preview = harness._file_overrides_series_preview_payload(
                    {"path": str(selected), "proposed_override": proposed_override}
                )
                applied = harness._file_overrides_series_apply_payload(
                    {
                        "path": str(selected),
                        "proposed_override": proposed_override,
                        "confirm_apply": True,
                        "preview_fingerprint": str(preview.get("preview_fingerprint") or ""),
                    }
                )
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

        preview_text = json.dumps(preview)
        self.assertFalse(preview["ok"])
        self.assertIn(missing_exact_stream.name, preview_text)
        self.assertIn("not available in detected subtitle streams", preview_text)
        self.assertEqual(_series_action_by_file(preview, missing_exact_stream.name), "issue")
        self.assertFalse(applied["ok"])
        self.assertEqual(manifest["entries"], {})

    def test_malformed_file_overrides_fail_closed_and_are_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"fake media")
            manifest_path = resolved.file_overrides_path  # type: ignore[assignment]
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{not-json", encoding="utf-8")

            with self.assertRaisesRegex(FileOverrideManifestReadError, "invalid JSON"):
                read_file_overrides(manifest_path)
            with self.assertRaises(FileOverrideManifestReadError):
                set_file_override_entry(
                    manifest_path,
                    source,
                    {"audio": {"maxChannels": 2}},
                )
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), "{not-json")

    def test_series_apply_write_failure_does_not_partially_update_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            rows = [
                _tv_snapshot_row(tv_root, "Atomic Show", "Season 01", "Atomic.Show.S01E01.mkv"),
                _tv_snapshot_row(tv_root, "Atomic Show", "Season 01", "Atomic.Show.S01E02.mkv", episode_number=2),
            ]
            _write_queue_snapshot(resolved, rows)
            harness = _TrackMetadataHarness(resolved)
            selected = Path(rows[0]["source_path"])
            preview = harness._file_overrides_series_preview_payload(
                {
                    "path": str(selected),
                    "proposed_override": {"audio": {"maxChannels": 2}},
                }
            )
            before = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

            with patch("mediapipeline.core.queue.file_overrides._write_atomic", side_effect=OSError("disk full")):
                failed = harness._file_overrides_series_apply_payload(
                    {
                        "path": str(selected),
                        "proposed_override": {"audio": {"maxChannels": 2}},
                        "confirm_apply": True,
                        "preview_fingerprint": preview["preview_fingerprint"],
                    }
                )
            after = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

        self.assertFalse(failed["ok"])
        self.assertIn("Failed to write series overrides", failed["message"])
        self.assertEqual(after, before)

    def test_series_preview_apply_rejects_invalid_stale_non_tv_and_no_eligible_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            movie = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            rows = [
                _tv_snapshot_row(tv_root, "Manual Show", "Season 01", "Manual.Show.S01E01.mkv"),
                _tv_snapshot_row(tv_root, "Stale Show", "Season 01", "Stale.Show.S01E01.mkv"),
                _tv_snapshot_row(tv_root, "Stale Show", "Season 01", "Stale.Show.S01E02.mkv", episode_number=2),
                {
                    **_snapshot_row(movie),
                    "root_path": str(resolved.source_movies),
                    "relative_path": "Movie.mkv",
                    "media_kind": "movie",
                },
            ]
            _write_queue_snapshot(resolved, rows)
            harness = _TrackMetadataHarness(resolved)
            selected = Path(rows[0]["source_path"])
            stale_selected = Path(rows[1]["source_path"])
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                selected,
                {"audio": {"maxChannels": 6}},
            )

            blocked_preview = harness._file_overrides_series_preview_payload(
                {"path": str(selected), "proposed_override": {"audio": {"maxChannels": 2}}}
            )
            missing_confirm = harness._file_overrides_series_apply_payload(
                {
                    "path": str(selected),
                    "proposed_override": {"audio": {"maxChannels": 2}},
                    "preview_fingerprint": blocked_preview.get("preview_fingerprint", ""),
                }
            )
            stale = harness._file_overrides_series_apply_payload(
                {
                    "path": str(stale_selected),
                    "proposed_override": {"audio": {"maxChannels": 2}},
                    "confirm_apply": True,
                    "preview_fingerprint": "stale",
                }
            )
            invalid = harness._file_overrides_series_preview_payload(
                {"path": str(selected), "proposed_override": {"audio": {"maxChannels": "two"}}}
            )
            non_tv = harness._file_overrides_series_preview_payload(
                {"path": str(movie), "proposed_override": {"audio": {"maxChannels": 2}}}
            )
            clear_blocked = harness._file_overrides_series_clear_preview_payload({"path": str(stale_selected)})
            clear_missing_confirm = harness._file_overrides_series_clear_apply_payload(
                {"path": str(selected), "preview_fingerprint": "unused"}
            )
            clear_stale = harness._file_overrides_series_clear_apply_payload(
                {"path": str(selected), "confirm_apply": True, "preview_fingerprint": "stale"}
            )
            clear_non_tv = harness._file_overrides_series_clear_preview_payload({"path": str(movie)})

        self.assertFalse(blocked_preview["ok"])
        self.assertIn("No eligible current queue rows", "\n".join(item["message"] for item in blocked_preview["blockers"]))
        self.assertFalse(missing_confirm["ok"])
        self.assertIn("confirm_apply", "\n".join(missing_confirm["errors"]))
        self.assertFalse(stale["ok"])
        self.assertIn("stale", "\n".join(stale["errors"]).lower())
        self.assertFalse(invalid["ok"])
        self.assertIn("maxChannels", "\n".join(invalid["errors"]))
        self.assertFalse(non_tv["ok"])
        self.assertIn("only for TV", non_tv["message"])
        self.assertFalse(clear_blocked["ok"])
        self.assertIn("No exact current queue file overrides", "\n".join(item["message"] for item in clear_blocked["blockers"]))
        self.assertFalse(clear_missing_confirm["ok"])
        self.assertIn("confirm_apply", "\n".join(clear_missing_confirm["errors"]))
        self.assertFalse(clear_stale["ok"])
        self.assertIn("stale", "\n".join(clear_stale["errors"]).lower())
        self.assertFalse(clear_non_tv["ok"])
        self.assertIn("only for TV", clear_non_tv["message"])

    def test_remux_pilot_promote_applies_current_queue_only_and_protects_manual_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            pilots = [
                tv_root / "Fallback Show" / "Season 01" / f"Fallback.Show.S01E0{episode}.mkv"
                for episode in range(1, 4)
            ]
            rows = [
                _tv_snapshot_row(tv_root, "Fallback Show", "Season 01", "Fallback.Show.S01E04.mkv", episode_number=4),
                _tv_snapshot_row(tv_root, "Fallback Show", "Season 01", "Fallback.Show.S01E05.mkv", episode_number=5),
                _tv_snapshot_row(tv_root, "Fallback Show", "Specials", "Fallback.Show.S00E01.mkv", season_number=0, episode_number=1),
                _tv_snapshot_row(tv_root, "Other Show", "Season 01", "Other.Show.S01E01.mkv"),
            ]
            _write_queue_snapshot(resolved, rows)
            _write_completed_manifest(resolved, [_completed_pilot_row(path) for path in pilots])
            manual = Path(rows[1]["source_path"])
            prior_batch = Path(rows[2]["source_path"])
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                manual,
                {"routing": {"profile": "encode"}},
            )
            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                prior_batch,
                {"routing": {"profile": "encode"}},
                batch_metadata={"origin": "series_batch", "batch_id": "series-old"},
                replace_existing=True,
            )
            harness = _TrackMetadataHarness(resolved)

            promoted = harness._file_overrides_remux_pilot_promote_payload(
                {
                    "pilot_source_paths": [str(path) for path in pilots],
                    "confirm_apply": True,
                    "reason": "operator verified fallback pilots",
                }
            )
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            entries = manifest["entries"]

        self.assertTrue(promoted["ok"], promoted)
        self.assertEqual(promoted["command"], "queue.file_overrides.remux_pilot_promote")
        self.assertEqual(promoted["schema_version"], "desktop_command_result.v1")
        self.assertEqual(promoted["data_schema"], "queue_remux_pilot_promotion.v1")
        self.assertEqual(promoted["detected_series"]["show_name"], "Fallback Show")
        self.assertEqual(promoted["counts"]["eligible_update_count"], 2)
        self.assertEqual(promoted["counts"]["protected_manual"], 1)
        self.assertEqual(promoted["counts"]["replace_prior_batch"], 1)
        self.assertEqual(len(promoted["pilot_evidence"]), 3)
        self.assertEqual(entries[normalize_file_override_path(rows[0]["source_path"])]["routing"]["profile"], "remux")
        self.assertEqual(entries[normalize_file_override_path(rows[2]["source_path"])]["routing"]["profile"], "remux")
        self.assertEqual(entries[normalize_file_override_path(manual)]["routing"]["profile"], "encode")
        self.assertFalse(any(normalize_file_override_path(path) in entries for path in pilots))

    def test_remux_pilot_auto_promote_applies_after_three_current_queue_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            rows = [
                _tv_snapshot_row(
                    tv_root,
                    "Pilot Auto",
                    "Season 01",
                    f"Pilot.Auto.S01E{episode:02d}.mkv",
                    episode_number=episode,
                )
                for episode in range(1, 6)
            ]
            _write_queue_snapshot(resolved, rows)
            _write_completed_manifest(
                resolved,
                [_completed_pilot_row(Path(row["source_path"])) for row in rows[:3]],
            )

            result = file_override_remux_pilot_auto_promote_payload(resolved=resolved)
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            entries = manifest["entries"]

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["command"], "queue.file_overrides.remux_pilot_auto_promote")
        self.assertEqual(result["promoted_series_count"], 1)
        self.assertEqual(result["results"][0]["counts"]["eligible_update_count"], 2)
        self.assertFalse(any(normalize_file_override_path(row["source_path"]) in entries for row in rows[:3]))
        self.assertEqual(entries[normalize_file_override_path(rows[3]["source_path"])]["routing"]["profile"], "remux")
        self.assertEqual(entries[normalize_file_override_path(rows[4]["source_path"])]["routing"]["profile"], "remux")

    def test_remux_pilot_auto_promote_catches_up_and_skips_completed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            rows = [
                _tv_snapshot_row(
                    tv_root,
                    "Pilot Catchup",
                    "Season 01",
                    f"Pilot.Catchup.S01E{episode:02d}.mkv",
                    episode_number=episode,
                )
                for episode in range(1, 7)
            ]
            _write_queue_snapshot(resolved, rows)
            _write_completed_manifest(
                resolved,
                [_completed_pilot_row(Path(row["source_path"])) for row in rows[:4]],
            )

            result = file_override_remux_pilot_auto_promote_payload(resolved=resolved)
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            entries = manifest["entries"]
            second_result = file_override_remux_pilot_auto_promote_payload(resolved=resolved)
            after_second = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["promoted_series_count"], 1)
        self.assertEqual(result["results"][0]["counts"]["eligible_update_count"], 2)
        self.assertFalse(any(normalize_file_override_path(row["source_path"]) in entries for row in rows[:4]))
        self.assertEqual(
            {
                normalize_file_override_path(rows[4]["source_path"]),
                normalize_file_override_path(rows[5]["source_path"]),
            },
            set(entries),
        )
        self.assertTrue(second_result["ok"], second_result)
        self.assertEqual(second_result["promoted_series_count"], 0)
        self.assertEqual(after_second, manifest)

    def test_remux_pilot_auto_promotion_service_runs_once_and_debounces_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            rows = [
                _tv_snapshot_row(
                    tv_root,
                    "Pilot Service",
                    "Season 01",
                    f"Pilot.Service.S01E{episode:02d}.mkv",
                    episode_number=episode,
                )
                for episode in range(1, 5)
            ]
            _write_queue_snapshot(resolved, rows)
            _write_completed_manifest(
                resolved,
                [_completed_pilot_row(Path(row["source_path"])) for row in rows[:3]],
            )
            harness = _RemuxPilotAutoPromotionHarness(resolved)

            result = harness.run_remux_pilot_auto_promotion_once()
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]
            second_result = harness.run_remux_pilot_auto_promotion_once()

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["promoted_series_count"], 1)
        self.assertEqual(manifest["entries"][normalize_file_override_path(rows[3]["source_path"])]["routing"]["profile"], "remux")
        self.assertEqual(second_result["skipped"], "state_unchanged")

    def test_remux_pilot_promote_blocks_invalid_pilot_counts_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            rows = [_tv_snapshot_row(tv_root, "Count Show", "Season 01", "Count.Show.S01E04.mkv", episode_number=4)]
            pilots = [
                tv_root / "Count Show" / "Season 01" / f"Count.Show.S01E0{episode}.mkv"
                for episode in range(1, 5)
            ]
            _write_queue_snapshot(resolved, rows)
            _write_completed_manifest(resolved, [_completed_pilot_row(path) for path in pilots])
            harness = _TrackMetadataHarness(resolved)

            too_few = harness._file_overrides_remux_pilot_promote_payload(
                {"pilot_source_paths": [str(path) for path in pilots[:2]], "confirm_apply": True}
            )
            too_many = harness._file_overrides_remux_pilot_promote_payload(
                {"pilot_source_paths": [str(path) for path in pilots], "confirm_apply": True}
            )
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

        self.assertFalse(too_few["ok"])
        self.assertIn("exactly 3", "\n".join(too_few["errors"]))
        self.assertFalse(too_many["ok"])
        self.assertIn("exactly 3", "\n".join(too_many["errors"]))
        self.assertEqual(manifest["entries"], {})

    def test_remux_pilot_promote_blocks_mixed_series_and_missing_completed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            fallback_pilots = [
                tv_root / "Fallback Show" / "Season 01" / f"Fallback.Show.S01E0{episode}.mkv"
                for episode in range(1, 3)
            ]
            other_pilot = tv_root / "Other Show" / "Season 01" / "Other.Show.S01E01.mkv"
            _write_queue_snapshot(
                resolved,
                [_tv_snapshot_row(tv_root, "Fallback Show", "Season 01", "Fallback.Show.S01E04.mkv", episode_number=4)],
            )
            _write_completed_manifest(
                resolved,
                [_completed_pilot_row(path) for path in [*fallback_pilots, other_pilot]],
            )
            harness = _TrackMetadataHarness(resolved)

            mixed = harness._file_overrides_remux_pilot_promote_payload(
                {"pilot_source_paths": [*(str(path) for path in fallback_pilots), str(other_pilot)], "confirm_apply": True}
            )
            missing = harness._file_overrides_remux_pilot_promote_payload(
                {
                    "pilot_source_paths": [str(path) for path in [*fallback_pilots, tv_root / "Fallback Show" / "Season 01" / "Fallback.Show.S01E03.mkv"]],
                    "confirm_apply": True,
                }
            )

        self.assertFalse(mixed["ok"])
        self.assertIn("same detected series", "\n".join(mixed["errors"]))
        self.assertFalse(missing["ok"])
        self.assertIn("completed", "\n".join(missing["errors"]).lower())

    def test_remux_pilot_promote_blocks_non_fallback_or_forced_encode_pilot_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            pilots = [
                tv_root / "Evidence Show" / "Season 01" / f"Evidence.Show.S01E0{episode}.mkv"
                for episode in range(1, 4)
            ]
            _write_queue_snapshot(
                resolved,
                [_tv_snapshot_row(tv_root, "Evidence Show", "Season 01", "Evidence.Show.S01E04.mkv", episode_number=4)],
            )
            harness = _TrackMetadataHarness(resolved)

            _write_completed_manifest(
                resolved,
                [
                    _completed_pilot_row(pilots[0], route_reason_code="manual_remux"),
                    _completed_pilot_row(pilots[1]),
                    _completed_pilot_row(pilots[2]),
                ],
            )
            non_fallback = harness._file_overrides_remux_pilot_promote_payload(
                {"pilot_source_paths": [str(path) for path in pilots], "confirm_apply": True}
            )
            _write_completed_manifest(
                resolved,
                [
                    _completed_pilot_row(pilots[0], route="encode", route_reason_code="operator_forced_encode"),
                    _completed_pilot_row(pilots[1]),
                    _completed_pilot_row(pilots[2]),
                ],
            )
            forced_encode = harness._file_overrides_remux_pilot_promote_payload(
                {"pilot_source_paths": [str(path) for path in pilots], "confirm_apply": True}
            )
            _write_completed_manifest(
                resolved,
                [
                    _completed_pilot_row(pilots[0], media_type="movie"),
                    _completed_pilot_row(pilots[1]),
                    _completed_pilot_row(pilots[2]),
                ],
            )
            non_tv = harness._file_overrides_remux_pilot_promote_payload(
                {"pilot_source_paths": [str(path) for path in pilots], "confirm_apply": True}
            )

        self.assertFalse(non_fallback["ok"])
        self.assertIn("oversized_encode_remux_fallback", "\n".join(non_fallback["errors"]))
        self.assertFalse(forced_encode["ok"])
        self.assertIn("final route", "\n".join(forced_encode["errors"]).lower())
        self.assertFalse(non_tv["ok"])
        self.assertIn("not completed TV media", "\n".join(non_tv["errors"]))

    def test_remux_pilot_promote_blocks_stale_queue_snapshot_without_current_series_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            pilots = [
                tv_root / "Gone Show" / "Season 01" / f"Gone.Show.S01E0{episode}.mkv"
                for episode in range(1, 4)
            ]
            _write_queue_snapshot(
                resolved,
                [_tv_snapshot_row(tv_root, "Other Show", "Season 01", "Other.Show.S01E01.mkv")],
            )
            _write_completed_manifest(resolved, [_completed_pilot_row(path) for path in pilots])
            harness = _TrackMetadataHarness(resolved)

            promoted = harness._file_overrides_remux_pilot_promote_payload(
                {"pilot_source_paths": [str(path) for path in pilots], "confirm_apply": True}
            )

        self.assertFalse(promoted["ok"])
        self.assertIn("current queue", "\n".join(promoted["errors"]).lower())

    def test_remux_pilot_promote_write_failure_leaves_manifest_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_root = resolved.source_tv  # type: ignore[assignment]
            pilots = [
                tv_root / "Atomic Pilot Show" / "Season 01" / f"Atomic.Pilot.Show.S01E0{episode}.mkv"
                for episode in range(1, 4)
            ]
            rows = [
                _tv_snapshot_row(tv_root, "Atomic Pilot Show", "Season 01", "Atomic.Pilot.Show.S01E04.mkv", episode_number=4),
                _tv_snapshot_row(tv_root, "Atomic Pilot Show", "Season 01", "Atomic.Pilot.Show.S01E05.mkv", episode_number=5),
            ]
            _write_queue_snapshot(resolved, rows)
            _write_completed_manifest(resolved, [_completed_pilot_row(path) for path in pilots])
            harness = _TrackMetadataHarness(resolved)
            before = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

            with patch("mediapipeline.core.queue.file_overrides._write_atomic", side_effect=OSError("disk full")):
                failed = harness._file_overrides_remux_pilot_promote_payload(
                    {"pilot_source_paths": [str(path) for path in pilots], "confirm_apply": True}
                )
            after = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

        self.assertFalse(failed["ok"])
        self.assertIn("Failed to write series overrides", failed["message"])
        self.assertEqual(after, before)

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

            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage") as run_probe:
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
            relative_payload = harness._file_overrides_folder_preview_payload(
                {"folder_path": "Franchise", "proposed_override": {"audio": {"keepTracks": [{"language": "eng"}]}}}
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
            burn_payload = harness._file_overrides_folder_preview_payload(
                {
                    "folder_path": str(folder),
                    "proposed_override": {"subtitles": {"burnTrack": {"streamIndex": 3, "language": "eng"}}},
                }
            )

            self.assertFalse(outside_payload["ok"])
            self.assertIn("outside configured", outside_payload["message"].lower())
            self.assertFalse(relative_payload["ok"])
            self.assertIn("'folder_path' must be an absolute path", relative_payload["message"])
            self.assertFalse(stream_index_payload["ok"])
            self.assertIn("streamIndex", "\n".join(stream_index_payload["errors"]))
            self.assertFalse(raw_map_payload["ok"])
            self.assertIn("map", "\n".join(raw_map_payload["errors"]))
            self.assertFalse(title_contains_payload["ok"])
            self.assertIn("titleContains", "\n".join(title_contains_payload["errors"]))
            self.assertFalse(burn_payload["ok"])
            self.assertIn("burnTrack", "\n".join(burn_payload["errors"]))

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

    def test_folder_entry_revalidates_merged_route_video_edits(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            folder = resolved.source_movies / "Franchise"  # type: ignore[operator]
            folder.mkdir(parents=True)

            set_file_override_entry(
                resolved.file_overrides_path,  # type: ignore[arg-type]
                folder,
                {
                    "video": {
                        "codec": "h264_nvenc",
                        "container": "mp4",
                    }
                },
            )
            before = resolved.file_overrides_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
            with self.assertRaises(FileOverrideValidationError) as caught:
                set_file_override_entry(
                    resolved.file_overrides_path,  # type: ignore[arg-type]
                    folder,
                    {"routing": {"profile": "remux"}},
                )
            after = resolved.file_overrides_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
            manifest = read_file_overrides(resolved.file_overrides_path)  # type: ignore[arg-type]

        self.assertIn("cannot be combined", "\n".join(caught.exception.errors))
        self.assertEqual(after, before)
        folder_entry = manifest["entries"][normalize_file_override_path(folder)]
        self.assertEqual(folder_entry["video"], {"codec": "h264_nvenc", "container": "mp4"})
        self.assertNotIn("routing", folder_entry)

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
            burn_track = harness._file_overrides_folder_rule_payload(
                {
                    "folder_path": str(folder),
                    "override": {"subtitles": {"burnTrack": {"streamIndex": 3, "language": "eng"}}},
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
        self.assertFalse(burn_track["ok"])
        self.assertIn("burnTrack", "\n".join(burn_track["errors"]))
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
        self.assertTrue(payload["source_info"]["available"])
        self.assertEqual(payload["source_info"]["file_size_bytes"], 10 * 1024 * 1024 * 1024)
        self.assertEqual(payload["source_info"]["file_size_display"], "10 GB")
        self.assertEqual(payload["source_info"]["duration_display"], "1h 30m")
        self.assertEqual(payload["source_info"]["container"], "matroska")
        self.assertEqual(payload["source_info"]["overall_bitrate_display"], "17.2 Mbps")
        self.assertEqual(payload["source_info"]["estimated_bitrate_basis"], "file_size_duration")
        self.assertEqual(payload["source_info"]["estimated_bitrate_display"], "15.907 Mbps")
        self.assertEqual(payload["source_info"]["primary_video"]["codec"], "hevc")
        self.assertEqual(payload["source_info"]["primary_video"]["resolution_display"], "3840x2160")
        self.assertTrue(payload["source_info"]["primary_video"]["is_hdr"])
        self.assertEqual(payload["source_info"]["primary_video"]["bitrate_display"], "18 Mbps")
        self.assertEqual(len(payload["audio_tracks"]), 2)
        self.assertEqual(payload["audio_tracks"][0]["stream_index"], 1)
        self.assertEqual(payload["audio_tracks"][0]["language"], "eng")
        self.assertEqual(payload["audio_tracks"][0]["bitrate_bps"], 640_000)
        self.assertEqual(payload["audio_tracks"][0]["bitrate_display"], "0.64 Mbps")
        self.assertTrue(payload["audio_tracks"][0]["default"])
        self.assertFalse(payload["audio_tracks"][0]["forced"])
        self.assertFalse(payload["audio_tracks"][0]["commentary"])
        self.assertEqual(payload["audio_tracks"][1]["language"], "eng")
        self.assertEqual(payload["audio_tracks"][1]["bitrate_display"], "3.2 Mbps")
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
                started_at=datetime.now(UTC),
                data=_probe_result(),
            )

            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage", return_value=stage_result) as run_probe:
                payload = harness._file_overrides_tracks_read_payload({"path": [str(source)]})

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["probe_available"])
            run_probe.assert_called_once()
            runner_options = run_probe.call_args.args[1]
            self.assertEqual(runner_options.state_db_root, resolved.state_root)
            self.assertFalse(resolved.file_overrides_path.exists())  # type: ignore[union-attr]

            outside = root / "Outside" / "Movie.mkv"
            invalid = harness._file_overrides_tracks_read_payload({"path": [str(outside)]})
            self.assertFalse(invalid["ok"])
            self.assertIn("outside configured", invalid["message"].lower())

    def test_effective_endpoint_runs_bounded_read_only_probe_without_writing_manifest(self) -> None:
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
                started_at=datetime.now(UTC),
                data=_probe_result(),
            )

            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage", return_value=stage_result) as run_probe:
                payload = harness._file_overrides_effective_read_payload({"path": [str(source)]})

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["command"], "queue.file_overrides.effective")
            self.assertTrue(payload["track_metadata"]["available"])
            self.assertEqual(payload["track_metadata"]["source_info"]["probe_source"], "stage_probe")
            run_probe.assert_called_once()
            runner_options = run_probe.call_args.args[1]
            self.assertEqual(runner_options.state_db_root, resolved.state_root)
            self.assertFalse(resolved.file_overrides_path.exists())  # type: ignore[union-attr]

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
                started_at=datetime.now(UTC),
                data=_probe_result(),
            )
            server = _LocalApiServer(_Facade(), token="tracks-token", resolved_provider=lambda: resolved)

            try:
                server.start()
                with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
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

            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage") as run_probe:
                payload = harness._file_overrides_tracks_read_payload({"path": [str(missing)]})

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["probe_available"])
            self.assertFalse(payload["source_info"]["available"])
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
                started_at=datetime.now(UTC),
                error={"code": "stage.timeout", "message": "Stage process exceeded timeout."},
            )

            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
                payload = harness._file_overrides_tracks_read_payload({"path": [str(source)]})

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["probe_available"])
            self.assertEqual(payload["probe_source"], "stage_probe")
            self.assertFalse(payload["source_info"]["available"])
            self.assertEqual(payload["source_info"]["probe_source"], "stage_probe")
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
                started_at=datetime.now(UTC),
                data=_probe_result(),
            )

            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
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
                burn_saved = harness._file_overrides_payload(
                    {
                        "path": str(source),
                        "subtitles": {
                            "burnTrack": {
                                "streamIndex": 4,
                                "language": "eng",
                                "codec": "hdmv_pgs_subtitle",
                                "forced": False,
                            }
                        },
                    }
                )
                burn_missing = harness._file_overrides_payload(
                    {"path": str(source), "subtitles": {"burnTrack": {"streamIndex": 99}}}
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
            self.assertTrue(burn_saved["ok"])
            self.assertEqual(
                burn_saved["entries"][normalize_file_override_path(source)]["subtitles"]["burnTrack"]["streamIndex"],
                4,
            )
            self.assertIn("Subtitle burn-in selected for stream 4", burn_saved["message"])
            self.assertEqual(burn_saved["confirmation"]["type"], "subtitle_burn_in")
            self.assertEqual(burn_saved["confirmation"]["source_path"], str(source))
            self.assertEqual(burn_saved["confirmation"]["streamIndex"], 4)
            self.assertFalse(burn_missing["ok"])
            self.assertIn("subtitles.burnTrack.streamIndex", "\n".join(burn_missing["errors"]))
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
                started_at=datetime.now(UTC),
                error={"code": "stage.timeout", "message": "Stage process exceeded timeout."},
            )

            with patch("mediapipeline.core.api.commands_file_overrides.run_probe_stage", return_value=stage_result):
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
        self.assertEqual(payload["track_metadata"]["source_info"]["container"], "matroska")
        self.assertEqual(payload["track_metadata"]["source_info"]["primary_video"]["resolution_display"], "3840x2160")
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
        self.assertEqual(_resolved_track(payload, "audio", 1)["label"], "Resolved: keep by file override")
        self.assertEqual(_resolved_track(payload, "audio", 5)["label"], "Resolved: drop by file override")
        self.assertEqual(_resolved_track(payload, "subtitle", 6)["label"], "Resolved: drop by file override")
        self.assertEqual(_resolved_track(payload, "subtitle", 3)["label"], "Resolved: keep by normal subtitle policy")

    def test_effective_payload_title_glob_fails_closed_for_oversized_probe_metadata(self) -> None:
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {"audio": {"keepTracks": [{"title": "*"}]}},
            track_payload={
                "ok": True,
                "probe_available": True,
                "probe_source": "cache",
                "audio_tracks": [
                    {
                        "stream_index": 1,
                        "language": "eng",
                        "title": "x" * 1025,
                        "codec": "ac3",
                        "channels": 6,
                    }
                ],
                "subtitle_tracks": [],
                "warnings": [],
            },
        )

        self.assertEqual(payload["track_selection_preview"]["audio"]["kept_stream_indexes"], [])
        self.assertEqual(payload["track_selection_preview"]["audio"]["dropped_stream_indexes"], [1])

    def test_effective_payload_burn_track_marks_one_subtitle_and_drops_others(self) -> None:
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {
                "subtitles": {
                    "burnTrack": {
                        "streamIndex": 4,
                        "language": "eng",
                        "codec": "hdmv_pgs_subtitle",
                        "forced": False,
                    }
                }
            },
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sources"]["subtitles.burnTrack"], "file_override")
        subtitle_preview = payload["track_selection_preview"]["subtitles"]
        self.assertEqual(subtitle_preview["burned_stream_indexes"], [4])
        self.assertEqual(subtitle_preview["dropped_stream_indexes"], [3, 6])
        self.assertEqual(subtitle_preview["burned_stream_sources"]["4"]["field"], "subtitles.burnTrack")
        self.assertEqual(_resolved_track(payload, "subtitle", 4)["action"], "burn")
        self.assertEqual(_resolved_track(payload, "subtitle", 4)["label"], "Resolved: burn by file override")
        self.assertEqual(_resolved_track(payload, "subtitle", 3)["action"], "drop")
        self.assertTrue(payload["route_video_processing"]["subtitle_burn_in"])
        self.assertTrue(payload["route_video_processing"]["drops_selectable_subtitles"])

    def test_effective_payload_normalizes_language_aliases_for_selection_preview(self) -> None:
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {
                "audio": {"keepTracks": [{"language": "eng"}]},
                "subtitles": {"keepTracks": [{"language": "eng"}]},
            },
            track_payload={
                "ok": True,
                "probe_available": True,
                "probe_source": "cache",
                "audio_tracks": [
                    {
                        "stream_index": 1,
                        "language": "en",
                        "title": "English 5.1",
                        "codec": "ac3",
                        "channels": 6,
                        "default": True,
                        "forced": False,
                    },
                    {
                        "stream_index": 2,
                        "language": "japanese",
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
                        "language": "english",
                        "title": "English SDH",
                        "codec": "subrip",
                        "default": False,
                        "forced": False,
                        "image_based": False,
                    }
                ],
                "warnings": [],
            },
        )

        audio_preview = payload["track_selection_preview"]["audio"]
        self.assertEqual(audio_preview["kept_stream_indexes"], [1])
        self.assertEqual(audio_preview["dropped_stream_indexes"], [2])
        audio_warnings = "\n".join(item["message"] for item in audio_preview["warnings"])
        self.assertNotIn("matches no audio tracks", audio_warnings)

        subtitle_preview = payload["track_selection_preview"]["subtitles"]
        self.assertEqual(subtitle_preview["kept_stream_indexes"], [3])
        subtitle_warnings = "\n".join(item["message"] for item in subtitle_preview["warnings"])
        self.assertNotIn("matches no subtitle tracks", subtitle_warnings)

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
        self.assertFalse(payload["track_metadata"]["source_info"]["available"])
        self.assertEqual(payload["track_metadata"]["audio_tracks"], [])
        self.assertFalse(payload["track_selection_preview"]["audio"]["available"])
        self.assertIn("not available", payload["track_selection_preview"]["audio"]["warnings"][0]["message"])
        self.assertFalse(payload["resolved_track_actions"]["audio"]["available"])
        self.assertFalse(payload["resolved_track_actions"]["subtitles"]["available"])
        self.assertEqual(payload["resolved_track_actions"]["audio"]["tracks"], [])

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
        self.assertEqual(_resolved_track(payload, "audio", 2)["source"], "file_override")
        self.assertEqual(_resolved_track(payload, "subtitle", 3)["source"], "file_override")

    def test_effective_payload_resolved_actions_report_folder_override_source(self) -> None:
        source_path = r"C:\Media\Folder\Movie.mkv"
        folder_path = r"C:\Media\Folder"
        payload = _effective_payload(
            source_path,
            {},
            manifest_entries={
                normalize_file_override_path(folder_path): {
                    "audio": {"dropTracks": [{"streamIndex": 5, "language": "jpn"}]},
                    "subtitles": {"keepTracks": [{"streamIndex": 3, "language": "eng", "forced": True}]},
                }
            },
        )

        audio = _resolved_track(payload, "audio", 5)
        subtitle_kept = _resolved_track(payload, "subtitle", 3)
        subtitle_dropped = _resolved_track(payload, "subtitle", 6)
        self.assertEqual(audio["action"], "drop")
        self.assertEqual(audio["source"], "folder_override")
        self.assertEqual(audio["label"], "Resolved: drop by folder override")
        self.assertEqual(subtitle_kept["source"], "folder_override")
        self.assertEqual(subtitle_kept["label"], "Resolved: keep by folder override")
        self.assertEqual(subtitle_dropped["source"], "folder_override")
        self.assertEqual(subtitle_dropped["label"], "Resolved: drop by folder override")

    def test_effective_payload_resolved_actions_report_subtitle_language_policy_drop(self) -> None:
        track_payload = _track_payload()
        track_payload["subtitle_tracks"].extend(
            [
                {
                    "stream_index": 15,
                    "language": "ger",
                    "title": "German SDH",
                    "codec": "hdmv_pgs_subtitle",
                    "default": False,
                    "forced": False,
                    "hearing_impaired": True,
                    "image_based": True,
                },
                {
                    "stream_index": 20,
                    "language": "ita",
                    "title": "Italian SDH",
                    "codec": "hdmv_pgs_subtitle",
                    "default": False,
                    "forced": False,
                    "hearing_impaired": True,
                    "image_based": True,
                },
                {
                    "stream_index": 35,
                    "language": "ger",
                    "title": "German SDH Commentary",
                    "codec": "hdmv_pgs_subtitle",
                    "default": False,
                    "forced": False,
                    "hearing_impaired": True,
                    "image_based": True,
                },
                {
                    "stream_index": 36,
                    "language": "jpn",
                    "title": "Japanese Forced ASS",
                    "codec": "ass",
                    "default": False,
                    "forced": True,
                    "image_based": False,
                },
                {
                    "stream_index": 37,
                    "language": "jpn",
                    "title": "Japanese SDH TX3G",
                    "codec": "mov_text",
                    "default": False,
                    "forced": True,
                    "hearing_impaired": True,
                    "image_based": False,
                },
                {
                    "stream_index": 38,
                    "language": "ita",
                    "title": "Italian SDH VobSub",
                    "codec": "dvd_subtitle",
                    "default": False,
                    "forced": True,
                    "hearing_impaired": True,
                    "image_based": True,
                },
            ]
        )
        payload = _effective_payload(
            r"C:\Media\Movie.mkv",
            {},
            config={
                "SubKeepLanguages": ["eng"],
                "Tx3gExtractLanguages": ["eng", "en", "und"],
                "BdpgsExtractLanguages": ["eng", "en", "und"],
                "VobSubExtractLanguages": ["eng", "en", "und"],
                "ConvertBdpgsToSrt": True,
                "ConvertTx3gToSrt": True,
                "ConvertVobSubToSrt": True,
            },
            track_payload=track_payload,
        )

        spanish = _resolved_track(payload, "subtitle", 6)
        english_pgs = _resolved_track(payload, "subtitle", 4)
        german_sdh_pgs = _resolved_track(payload, "subtitle", 15)
        italian_sdh_pgs = _resolved_track(payload, "subtitle", 20)
        german_sdh_commentary_pgs = _resolved_track(payload, "subtitle", 35)
        japanese_forced_ass = _resolved_track(payload, "subtitle", 36)
        japanese_sdh_tx3g = _resolved_track(payload, "subtitle", 37)
        italian_sdh_vobsub = _resolved_track(payload, "subtitle", 38)
        self.assertEqual(spanish["action"], "drop")
        self.assertEqual(spanish["source"], "global_default")
        self.assertEqual(spanish["field"], "SubKeepLanguages")
        self.assertEqual(spanish["label"], "Resolved: drop by normal subtitle policy")
        self.assertIn("outside saved SubKeepLanguages policy", spanish["reason"])
        self.assertEqual(english_pgs["action"], "convert")
        self.assertEqual(english_pgs["field"], "ConvertBdpgsToSrt")
        self.assertEqual(english_pgs["label"], "Resolved: convert by normal subtitle policy")
        for resolved in (german_sdh_pgs, italian_sdh_pgs, german_sdh_commentary_pgs):
            self.assertEqual(resolved["action"], "drop")
            self.assertEqual(resolved["source"], "global_default")
            self.assertEqual(resolved["field"], "BdpgsExtractLanguages")
            self.assertEqual(resolved["label"], "Resolved: drop by normal subtitle policy")
            self.assertIn("outside saved BdpgsExtractLanguages policy", resolved["reason"])
        self.assertEqual(japanese_forced_ass["action"], "drop")
        self.assertEqual(japanese_forced_ass["field"], "SubKeepLanguages")
        self.assertIn("outside saved SubKeepLanguages policy", japanese_forced_ass["reason"])
        self.assertEqual(japanese_sdh_tx3g["action"], "drop")
        self.assertEqual(japanese_sdh_tx3g["field"], "Tx3gExtractLanguages")
        self.assertIn("outside saved Tx3gExtractLanguages policy", japanese_sdh_tx3g["reason"])
        self.assertEqual(italian_sdh_vobsub["action"], "drop")
        self.assertEqual(italian_sdh_vobsub["field"], "VobSubExtractLanguages")
        self.assertIn("outside saved VobSubExtractLanguages policy", italian_sdh_vobsub["reason"])


if __name__ == "__main__":
    unittest.main()
