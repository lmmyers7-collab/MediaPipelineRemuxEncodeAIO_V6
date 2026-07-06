from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.processes.rerun_preview import (  # noqa: E402
    materialize_scoped_rerun_csv,
    recent_rerun_csv_candidates,
    rerun_import_csv_root,
    rerun_csv_preview_payload,
    rerun_network_csv_preview_payload,
)
from mediapipeline.core.processes.rerun_rules import (  # noqa: E402
    AUDIO_LANGUAGE_REMEDIATION,
    BAD_DOWNLOAD_FULL_RERUN,
    CONTAINER_CODEC_REMEDIATION,
    LEGACY_PIPELINE_STANDARDIZE,
    SUBTITLE_REMEDIATION,
)
from mediapipeline.desktop.models import ResolvedPaths  # noqa: E402


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "MediaPipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host="pwsh",
        local_base=root / "LocalBase",
        state_root=root / "LocalBase" / "State",
        audit_reports_path=root / "LocalBase" / "AuditReports",
        config_data={"Outsource": str(root / "Outsource")},
    )


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "enabled",
        "source_path",
        "audit_issue_codes",
        "stage_mode",
        "post_success_original",
        "return_mode",
        "effective_bucket",
        "notes",
    ]
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _media_file(root: Path, name: str, *, suffix: str = ".mkv") -> Path:
    path = root / "Media" / f"{name}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"media")
    return path


class RerunCsvPreviewTests(unittest.TestCase):
    def test_preview_blocks_outside_root_plex_planned_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            source = _media_file(root, "Movie")
            outside = root / "OutsideFinal" / "Movie.mkv"
            _write_csv(
                csv_path,
                [
                    {
                        "enabled": "true",
                        "source_path": str(source),
                        "audit_issue_codes": "AUDIO",
                        "plex_planned_path": str(outside),
                    }
                ],
            )

            payload = rerun_csv_preview_payload(_resolved(root), {"csv_path": str(csv_path), "confirm_replace_final": True})

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["rows"][0]["status"], "blocked")
        self.assertIn("outside configured output root", payload["rows"][0]["reason"])
        self.assertIn("plex_planned_path", payload["rows"][0]["reason"])

    def test_preview_blocks_outside_root_server_out(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            source = _media_file(root, "Movie")
            outside = root / "OutsideServerOut" / "Movie.mkv"
            _write_csv(
                csv_path,
                [
                    {
                        "enabled": "true",
                        "source_path": str(source),
                        "audit_issue_codes": "AUDIO",
                        "server_out": str(outside),
                    }
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "destination_mode": "pending_publish",
                    "collision_policy": "suffix",
                },
            )

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["rows"][0]["status"], "blocked")
        self.assertIn("outside configured output root", payload["rows"][0]["reason"])
        self.assertIn("server_out", payload["rows"][0]["reason"])

    def test_preview_allows_library_profile_output_root_override(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            source = source_root / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            _write_csv(
                csv_path,
                [
                    {
                        "enabled": "true",
                        "source_path": str(source),
                        "audit_issue_codes": "AUDIO",
                        "plex_planned_path": str(profile_out / "Movie.mkv"),
                    }
                ],
            )
            resolved = _resolved(root)
            resolved.config_data = {
                "Outsource": str(root / "Outsource"),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }

            payload = rerun_csv_preview_payload(resolved, {"csv_path": str(csv_path), "confirm_replace_final": True})

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertNotIn("outside configured output root", payload["rows"][0]["reason"])

    def test_network_preview_models_claimable_blocked_skipped_and_handoff_readiness_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            source = source_root / "Movie.mkv"
            duplicate_source = source_root / "Duplicate.mkv"
            disabled_source = source_root / "Disabled.mkv"
            for path in (source, duplicate_source, disabled_source):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            _write_csv(
                csv_path,
                [
                    {
                        "enabled": "true",
                        "source_path": str(source),
                        "audit_issue_codes": "AUDIO",
                        "plex_planned_path": str(profile_out / "Movie.mkv"),
                    },
                    {
                        "enabled": "true",
                        "source_path": str(duplicate_source),
                        "audit_issue_codes": "AUDIO",
                    },
                    {
                        "enabled": "true",
                        "source_path": str(duplicate_source),
                        "audit_issue_codes": "AUDIO",
                    },
                    {
                        "enabled": "false",
                        "source_path": str(disabled_source),
                        "audit_issue_codes": "AUDIO",
                    },
                ],
            )
            resolved = _resolved(root)
            resolved.config_data = {
                "Outsource": str(root / "Outsource"),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }

            payload = rerun_network_csv_preview_payload(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            )

        self.assertEqual(payload["schema_version"], "desktop_rerun_network_preview.v1")
        self.assertEqual(payload["effect"], "none")
        self.assertFalse(payload["touches_media"])
        self.assertFalse(payload["writes_queue"])
        self.assertFalse(payload["writes_network_state"])
        self.assertFalse(payload["launches_work"])
        self.assertFalse(payload["can_start_network_batch"])
        self.assertEqual(payload["local_preview_schema_version"], "desktop_rerun_csv_preview.v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["counts"]["claimable_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_rows"], 2)
        self.assertEqual(payload["counts"]["skipped_rows"], 1)
        self.assertEqual(payload["counts"]["duplicate_rows"], 2)
        self.assertEqual(payload["counts"]["output_handoff_ready_rows"], 0)

        claimable = next(row for row in payload["rows"] if row["claimable"])
        self.assertTrue(claimable["row_key"])
        self.assertEqual(claimable["source_mapping"]["status"], "library_relative")
        self.assertEqual(claimable["source_mapping"]["library_id"], "profile")
        self.assertEqual(claimable["source_mapping"]["relative_path"], "Movie.mkv")
        self.assertEqual(claimable["output_handoff"]["status"], "not_configured")
        self.assertFalse(claimable["start_ready"])
        self.assertIn("output_handoff_not_configured", claimable["start_blockers"])
        self.assertIn("destination_behavior:auto_replace_clean_else_pending_review", claimable["destination_policy"]["risk_codes"])

    def test_preview_allows_confirmed_same_file_source_overwrite_override(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            source = _media_file(root, "Movie")
            _write_csv(
                csv_path,
                [
                    {
                        "enabled": "true",
                        "source_path": str(source),
                        "audit_issue_codes": "AUDIO",
                        "plex_planned_path": str(source),
                    }
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "destination_mode": "publish_replace_final",
                    "collision_policy": "replace_final",
                    "confirm_replace_final": True,
                    "confirm_source_overwrite": True,
                },
            )

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertNotIn("outside configured output root", payload["rows"][0]["reason"])

    def test_preview_counts_blocked_disabled_duplicate_and_scoped_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            one = _media_file(root, "One")
            two = _media_file(root, "Two")
            three = _media_file(root, "Three")
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": str(one), "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "false", "source_path": str(two), "audit_issue_codes": "SUBTITLE", "effective_bucket": "REVIEW"},
                    {"enabled": "true", "source_path": str(three), "stage_mode": "move", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "true", "source_path": str(one), "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "true", "source_path": "", "audit_issue_codes": "MISSING", "effective_bucket": "RERUN_PIPELINE"},
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "scope": {
                        "enabled_only": True,
                        "skip_blocked": True,
                        "skip_warning_rows": False,
                        "issue_filter": "AUDIO",
                        "preview_limit": 3,
                    },
                },
            )

        self.assertEqual(payload["schema_version"], "desktop_rerun_csv_preview.v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["counts"]["total_rows"], 5)
        self.assertEqual(payload["counts"]["disabled_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_rows"], 4)
        self.assertEqual(payload["counts"]["blocked_mode_rows"], 1)
        self.assertEqual(payload["counts"]["duplicate_source_rows"], 2)
        self.assertEqual(payload["counts"]["missing_source_rows"], 1)
        self.assertEqual(payload["counts"]["missing_file_rows"], 0)
        self.assertEqual(payload["counts"]["nonexistent_source_rows"], 0)
        self.assertEqual(payload["counts"]["relative_source_rows"], 0)
        self.assertEqual(payload["counts"]["invalid_extension_rows"], 0)
        self.assertEqual(payload["counts"]["effective_scoped_rows"], 0)
        self.assertEqual(len(payload["rows"]), 3)
        self.assertEqual(payload["rows"][0]["status"], "blocked")
        self.assertIn("duplicate source_path", payload["rows"][0]["reason"])
        self.assertEqual(payload["execution_mode"], "one_at_a_time")
        self.assertEqual(payload["destination_mode"], "auto_replace_clean_else_pending_review")
        self.assertEqual(payload["collision_policy"], "replace_final")
        self.assertIn("AUDIO", [item["value"] for item in payload["filter_options"]["issue_filters"]])
        self.assertEqual(Path(payload["import_csv_root"]), root / "LocalBase" / "State" / "Rerun" / "ImportCsv")

    def test_preview_blocks_duplicate_planned_output_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            correct = root / "Media" / "Jurassic World Fallen Kingdom (2018)" / "Jurassic World Fallen Kingdom (2018).mkv"
            typo = root / "Media" / "Jurrasic World Fallen Kingdom (2018)" / "Jurassic World Fallen Kingdom (2018).mkv"
            for path in (correct, typo):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": str(correct), "media_kind": "Movie", "effective_bucket": "REVIEW"},
                    {"enabled": "true", "source_path": str(typo), "media_kind": "Movie", "effective_bucket": "REVIEW"},
                ],
            )

            payload = rerun_csv_preview_payload(_resolved(root), {"csv_path": str(csv_path), "confirm_replace_final": True})

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["counts"]["duplicate_planned_output_rows"], 2)
        self.assertEqual(payload["rows"][0]["status"], "blocked")
        self.assertEqual(payload["rows"][1]["status"], "blocked")
        self.assertTrue(payload["rows"][0]["duplicate_planned_output"])
        self.assertEqual(payload["rows"][1]["duplicate_planned_output_first_row_index"], 0)
        self.assertIn("duplicate planned output path", payload["rows"][0]["reason"])
        self.assertIn("duplicate planned output path", "\n".join(payload["errors"]))

    def test_pending_publish_destination_does_not_block_rows_without_legacy_override(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            one = _media_file(root, "One")
            two = _media_file(root, "Two")
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": str(one), "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {
                        "enabled": "true",
                        "source_path": str(two),
                        "audit_issue_codes": "SUBTITLE",
                        "effective_bucket": "RERUN_PIPELINE",
                        "return_mode": "replace_original",
                    },
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "destination_mode": "pending_publish",
                    "collision_policy": "suffix",
                    "original_policy": "keep",
                    "scope": {
                        "enabled_only": True,
                        "skip_blocked": True,
                        "preview_limit": 10,
                    },
                },
            )

        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["safe_modes"])
        self.assertEqual(payload["destination_mode"], "pending_publish")
        self.assertEqual(payload["return_mode"], "pending_publish")
        self.assertEqual(payload["counts"]["total_rows"], 2)
        self.assertEqual(payload["counts"]["blocked_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_mode_rows"], 1)
        self.assertEqual(payload["counts"]["effective_scoped_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_scoped_rows"], 0)
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertEqual(payload["rows"][0]["return_mode"], "pending_publish")
        self.assertEqual(payload["rows"][1]["status"], "blocked")
        self.assertIn("blocked source-mutating", payload["rows"][1]["reason"])

    def test_preview_keeps_review_bucket_remediation_rows_ready(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            subtitle_source = _media_file(root, "Subtitle")
            audio_source = _media_file(root, "Audio")
            video_source = _media_file(root, "Video")
            _write_csv(
                csv_path,
                [
                    {
                        "enabled": "true",
                        "source_path": str(subtitle_source),
                        "audit_issue_codes": "vobsub-only-subtitles,subtitle-track-titles-missing",
                        "effective_bucket": "REVIEW",
                    },
                    {
                        "enabled": "true",
                        "source_path": str(audio_source),
                        "audit_issue_codes": "audio-track-titles-missing,audio-default-policy-mismatch",
                        "effective_bucket": "REVIEW",
                    },
                    {
                        "enabled": "true",
                        "source_path": str(video_source),
                        "audit_issue_codes": "codec-remux-needed",
                        "effective_bucket": "REVIEW",
                    },
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "confirm_replace_final": True,
                    "scope": {"enabled_only": True, "preview_limit": 10},
                },
            )

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["counts"]["warning_rows"], 0)
        self.assertEqual(payload["counts"]["rule_warning_rows"], 0)
        self.assertEqual([row["status"] for row in payload["rows"]], ["ready", "ready", "ready"])
        self.assertEqual(payload["rows"][0]["rerun_rule_id"], SUBTITLE_REMEDIATION)
        self.assertEqual(payload["rows"][1]["rerun_rule_id"], AUDIO_LANGUAGE_REMEDIATION)
        self.assertEqual(payload["rows"][2]["rerun_rule_id"], CONTAINER_CODEC_REMEDIATION)
        self.assertTrue(payload["rows"][0]["rerun_rule_evidence"]["review_bucket_present"])
        self.assertIn("remains runnable", payload["rows"][0]["rerun_rule_reason"])

    def test_preview_normalizes_legacy_review_bucket_rule_warning_to_ready(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            source = _media_file(root, "Subtitle")
            _write_csv(
                csv_path,
                [
                    {
                        "enabled": "true",
                        "source_path": str(source),
                        "audit_issue_codes": "subtitle-track-titles-missing",
                        "effective_bucket": "REVIEW",
                        "rerun_rule_id": SUBTITLE_REMEDIATION,
                        "rerun_rule_label": "Subtitle Remediation",
                        "rerun_rule_status": "warning",
                        "rerun_rule_reason": (
                            "Issue evidence is subtitle-focused; rerun uses backend subtitle policy and normal clean-return destination handling. "
                            "Audit bucket requests operator review before launch scope is finalized."
                        ),
                        "rerun_rule_replacement_eligible": "true",
                    }
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            )

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertEqual(payload["counts"]["warning_rows"], 0)
        self.assertEqual(payload["counts"]["rule_warning_rows"], 0)
        self.assertEqual(payload["rows"][0]["rerun_rule_status"], "ready")
        self.assertIn("remains runnable", payload["rows"][0]["rerun_rule_reason"])

    def test_materialize_scoped_csv_writes_only_filtered_rows_under_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            one = _media_file(root, "One")
            two = _media_file(root, "Two")
            three = _media_file(root, "Three")
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": str(one), "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "true", "source_path": str(two), "audit_issue_codes": "SUBTITLE", "effective_bucket": "REVIEW"},
                    {"enabled": "true", "source_path": str(three), "stage_mode": "move", "effective_bucket": "RERUN_PIPELINE"},
                ],
            )
            resolved = _resolved(root)
            request = {
                "csv_path": str(csv_path),
                "confirm_replace_final": True,
                "scope": {
                    "enabled_only": True,
                    "skip_blocked": True,
                    "issue_filter": "AUDIO",
                    "preview_limit": 10,
                },
            }
            preview = rerun_csv_preview_payload(resolved, request)

            scoped = materialize_scoped_rerun_csv(resolved, request, preview=preview)
            scoped_path = Path(scoped["scoped_csv_path"])
            with scoped_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertTrue(scoped_path.exists())
            self.assertIn("State", str(scoped_path))
            self.assertEqual(scoped["row_count"], 1)
            self.assertEqual(rows[0]["source_path"], str(one))
            self.assertEqual(rows[0]["rerun_rule_id"], AUDIO_LANGUAGE_REMEDIATION)
            self.assertEqual(rows[0]["rerun_rule_destination_behavior"], "auto_replace_clean_else_pending_review")
            self.assertEqual(rows[0]["rerun_rule_replacement_eligible"], "true")

    def test_preview_adds_backend_rule_decisions_and_blocks_bad_download_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            bad = _media_file(root, "BadDownload")
            old = _media_file(root, "OldPipeline")
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": str(bad), "audit_issue_codes": "bad_download,ffprobe_error", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "true", "source_path": str(old), "audit_issue_codes": "", "effective_bucket": "RERUN_PIPELINE"},
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "confirm_replace_final": True,
                    "scope": {
                        "enabled_only": True,
                        "skip_blocked": False,
                        "preview_limit": 10,
                    },
                },
            )

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["rule_schema_version"], "desktop_rerun_rule_decision.v1")
        self.assertEqual(payload["counts"]["rule_blocked_rows"], 1)
        self.assertEqual(payload["rule_summary"]["counts"][BAD_DOWNLOAD_FULL_RERUN], 1)
        self.assertEqual(payload["rule_summary"]["counts"][LEGACY_PIPELINE_STANDARDIZE], 1)
        self.assertEqual(payload["rows"][0]["status"], "blocked")
        self.assertEqual(payload["rows"][0]["rerun_rule_id"], BAD_DOWNLOAD_FULL_RERUN)
        self.assertFalse(payload["rows"][0]["rerun_rule_replacement_eligible"])
        self.assertIn("manual source review", payload["rows"][0]["rerun_rule_reason"])
        self.assertEqual(payload["rows"][1]["rerun_rule_id"], LEGACY_PIPELINE_STANDARDIZE)
        self.assertTrue(payload["rows"][1]["rerun_rule_replacement_eligible"])

    def test_preview_blocks_csv_structure_errors(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)

            empty_csv = root / "empty.csv"
            empty_csv.write_text("", encoding="utf-8")
            empty = rerun_csv_preview_payload(resolved, {"csv_path": str(empty_csv)})

            missing_header_csv = root / "missing-header.csv"
            missing_header_csv.write_text("enabled,not_source\ntrue,value\n", encoding="utf-8")
            missing_header = rerun_csv_preview_payload(resolved, {"csv_path": str(missing_header_csv)})

            malformed_csv = root / "malformed.csv"
            malformed_csv.write_text('source_path,notes\n"unterminated\n', encoding="utf-8")
            malformed = rerun_csv_preview_payload(resolved, {"csv_path": str(malformed_csv)})

        self.assertEqual(empty["status"], "blocked")
        self.assertIn("CSV has no header columns.", empty["errors"])
        self.assertIn("CSV contains no data rows.", empty["errors"])
        self.assertEqual(missing_header["status"], "blocked")
        self.assertIn("CSV is missing source_path header.", missing_header["errors"])
        self.assertEqual(malformed["status"], "blocked")
        self.assertIn("CSV could not be read", malformed["message"])

    def test_preview_blocks_bad_source_paths_but_preserves_scoped_valid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            valid = _media_file(root, "Movie With Spaces")
            invalid_extension = _media_file(root, "Not Media", suffix=".txt")
            missing = root / "Media" / "Missing.mkv"
            fieldnames = ["enabled", "source_path", "audit_issue_codes", "extra_header"]
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow({"enabled": "true", "source_path": str(valid), "audit_issue_codes": "AUDIO", "extra_header": "allowed"})
                writer.writerow({"enabled": "true", "source_path": "relative/movie.mkv", "audit_issue_codes": "AUDIO", "extra_header": "blocked"})
                writer.writerow({"enabled": "true", "source_path": str(missing), "audit_issue_codes": "AUDIO", "extra_header": "blocked"})
                writer.writerow({"enabled": "true", "source_path": str(invalid_extension), "audit_issue_codes": "AUDIO", "extra_header": "blocked"})
                writer.writerow({"enabled": "true", "source_path": "", "audit_issue_codes": "AUDIO", "extra_header": "blocked"})

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "confirm_replace_final": True,
                    "scope": {
                        "enabled_only": True,
                        "skip_blocked": True,
                        "issue_filter": "AUDIO",
                        "preview_limit": 10,
                    },
                },
            )

        self.assertEqual(payload["status"], "ready")
        self.assertIn("extra_header", payload["fieldnames"])
        self.assertEqual(payload["counts"]["total_rows"], 5)
        self.assertEqual(payload["counts"]["effective_scoped_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_rows"], 4)
        self.assertEqual(payload["counts"]["relative_source_rows"], 1)
        self.assertEqual(payload["counts"]["nonexistent_source_rows"], 1)
        self.assertEqual(payload["counts"]["missing_file_rows"], 1)
        self.assertEqual(payload["counts"]["invalid_extension_rows"], 1)
        self.assertEqual(payload["counts"]["missing_source_rows"], 1)
        self.assertEqual(payload["rows"][0]["source_path"], str(valid))
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertEqual(payload["rows"][1]["status"], "blocked")
        self.assertEqual(payload["rows"][2]["status"], "blocked")
        self.assertEqual(payload["rows"][3]["status"], "blocked")
        self.assertEqual(payload["rows"][4]["status"], "blocked")
        reasons = "\n".join(str(row.get("reason") or "") for row in payload["rows"])
        self.assertIn("relative source_path", reasons)
        self.assertIn("source file not found", reasons)
        self.assertIn("invalid media extension", reasons)

    def test_preview_correlates_completed_pending_publish_and_prior_rerun_state(self) -> None:
        class PendingScanService:
            def __init__(self, source: Path, manifest: Path) -> None:
                self.source = source
                self.manifest = manifest

            def scan_pending_publish(self, _resolved: ResolvedPaths) -> dict[str, object]:
                return {
                    "rows": [
                        {
                            "source_path": str(self.source),
                            "state": "parked",
                            "manifest_path": str(self.manifest),
                            "server_out": r"\\server\Media\Movie.mkv",
                            "local_file": str(self.manifest.with_suffix(".mkv")),
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            _write_csv(csv_path, [{"enabled": "true", "source_path": str(source), "audit_issue_codes": "AUDIO"}])
            resolved = _resolved(root)

            completed_manifest = root / "LocalBase" / "State" / "Completed" / "completed_jobs.jsonl"
            completed_manifest.parent.mkdir(parents=True, exist_ok=True)
            completed_manifest.write_text(
                json.dumps({"source_path": str(source), "output_path": str(root / "Out" / "Movie.mkv"), "route": "remux", "job_id": "job-1"})
                + "\n",
                encoding="utf-8",
            )
            resolved.completed_manifest_path = completed_manifest

            rerun_manifest = root / "LocalBase" / "RerunManifests" / "rerun-1.json"
            rerun_manifest.parent.mkdir(parents=True, exist_ok=True)
            rerun_manifest.write_text(
                json.dumps(
                    {
                        "batch_id": "batch-1",
                        "destination_mode": "review_workspace",
                        "rows": [{"source_path": str(source), "status": "parked"}],
                    }
                ),
                encoding="utf-8",
            )

            pending_manifest = root / "PendingServerPush" / "Movie.manifest.json"
            payload = rerun_csv_preview_payload(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
                service=PendingScanService(source, pending_manifest),
            )

        row = payload["rows"][0]
        self.assertEqual(payload["state_correlation"]["status"], "complete")
        self.assertEqual(payload["state_correlation"]["counts"]["requested_source_rows"], 1)
        self.assertEqual(payload["state_correlation"]["counts"]["matched_source_rows"], 1)
        self.assertEqual(set(row["state_flags"]), {"completed", "pending_publish", "prior_rerun"})
        evidence_kinds = {item["kind"] for item in row["state_evidence"]}
        self.assertEqual(evidence_kinds, {"completed", "pending_publish", "prior_rerun"})
        self.assertFalse(payload["state_correlation"]["touches_media"])

    def test_preview_reports_state_correlation_scan_unavailable_without_blocking_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            _write_csv(csv_path, [{"enabled": "true", "source_path": str(source), "audit_issue_codes": "AUDIO"}])

            payload = rerun_csv_preview_payload(_resolved(root), {"csv_path": str(csv_path), "confirm_replace_final": True})

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertEqual(payload["state_correlation"]["status"], "warning")
        self.assertTrue(
            any("scan service is not available" in item for item in payload["state_correlation"]["warnings"]),
            payload["state_correlation"]["warnings"],
        )

    def test_recent_candidates_are_limited_to_import_and_scoped_rerun_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            import_root = rerun_import_csv_root(resolved)
            assert import_root is not None
            import_csv = import_root / "audit_rerun_export_20260701_120000.csv"
            scoped_csv = resolved.state_root / "Rerun" / "ScopedCsv" / "rerun_scoped_20260701.csv"
            audit_csv = resolved.audit_reports_path / "audit_full_20260701.csv"
            for path in (import_csv, scoped_csv, audit_csv):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("source_path\nC:/Media/Movie.mkv\n", encoding="utf-8")

            candidates = recent_rerun_csv_candidates(resolved)
            paths = {Path(item["path"]) for item in candidates}

        self.assertIn(import_csv, paths)
        self.assertIn(scoped_csv, paths)
        self.assertNotIn(audit_csv, paths)


if __name__ == "__main__":
    unittest.main()
