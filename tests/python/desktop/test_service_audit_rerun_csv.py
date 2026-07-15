from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import AuditRecord, ResolvedPaths
from mediapipeline.core.audit.rerun_service import AuditRerunServiceMixin
from mediapipeline.core.audit.rerun_csv import (
    apply_rerun_source_metadata,
    build_rerun_csv_row,
    source_stat_to_rerun_values,
)


def _audit_record(**row: str) -> AuditRecord:
    return AuditRecord(source_csv=Path("audit.csv"), row=row)


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
    )


class RerunCsvService(AuditRerunServiceMixin):
    def __init__(self, metadata: dict[str, dict[str, object]] | None = None) -> None:
        self.metadata = metadata or {}

    def _load_rerun_source_metadata(self, resolved: ResolvedPaths, source_paths: list[Path]) -> dict[str, dict[str, object]]:
        return self.metadata


class AuditRerunCsvHelperTests(unittest.TestCase):
    def test_build_rerun_csv_row_preserves_audit_policy_fields(self) -> None:
        record = _audit_record(
            Path=r"C:\Media\TV\Show\Season 02\Episode.mkv",
            MediaType="TV",
            NonSidecarIssueCodes="bad-subtitle",
            IssueCodes="fallback",
            PriorityFixLevel="High",
            EffectiveBucket="priority",
            PrimaryIssueCode="primary",
            LookupTitle="Show",
            RelativePath=r"TV\Show\Season 02\Episode.mkv",
            PlannedOutputPath=r"C:\Out\TV\Show\S02E01.mkv",
            SourceIdentityV2="identity-1",
            SourceContentSha256="A" * 64,
            SourceContentSha256Algorithm="sha256-full-file",
        )

        row = build_rerun_csv_row(record, stage_mode="copy", original_mode="keep", return_mode="park")

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["enabled"], "true")
        self.assertEqual(row["media_kind"], "TV")
        self.assertEqual(row["audit_issue_codes"], "bad-subtitle")
        self.assertEqual(row["plex_planned_path"], r"C:\Out\TV\Show\S02E01.mkv")
        self.assertEqual(row["source_identity_v2"], "identity-1")
        self.assertEqual(row["source_content_sha256"], "a" * 64)
        self.assertEqual(row["source_content_sha256_algorithm"], "sha256-full-file")
        self.assertEqual(row["priority_fix_level"], "High")
        self.assertEqual(row["return_mode"], "park")

    def test_build_rerun_csv_row_returns_none_for_rows_without_source_path(self) -> None:
        self.assertIsNone(build_rerun_csv_row(_audit_record(MediaType="Movie"), stage_mode="copy", original_mode="keep", return_mode="park"))

    def test_apply_rerun_source_metadata_fills_identity_and_disables_missing_source(self) -> None:
        row = {
            "enabled": "true",
            "source_size": "",
            "source_mtime_utc": "",
            "source_identity_v2": "",
            "source_content_sha256": "",
            "source_content_sha256_algorithm": "",
            "notes": "",
        }

        updated = apply_rerun_source_metadata(
            row,
            {
                "exists": False,
                "source_size": 123,
                "source_mtime_utc": "2026-05-08T12:00:00+00:00",
                "source_identity_v2": "identity-from-helper",
                "source_content_sha256": "B" * 64,
                "source_content_sha256_algorithm": "sha256-full-file",
                "error": "locked",
            },
        )

        self.assertEqual(updated["enabled"], "false")
        self.assertEqual(updated["source_size"], "123")
        self.assertEqual(updated["source_mtime_utc"], "2026-05-08T12:00:00+00:00")
        self.assertEqual(updated["source_identity_v2"], "identity-from-helper")
        self.assertEqual(updated["source_content_sha256"], "b" * 64)
        self.assertEqual(updated["source_content_sha256_algorithm"], "sha256-full-file")
        self.assertEqual(updated["notes"], "source metadata failed: locked")
        self.assertEqual(row["enabled"], "true")

    def test_source_stat_to_rerun_values_formats_utc_timestamp(self) -> None:
        size, timestamp = source_stat_to_rerun_values(42, 0.0)

        self.assertEqual(size, "42")
        self.assertEqual(timestamp, "1970-01-01T00:00:00+00:00")

    def test_service_csv_writer_uses_helper_rows_and_preserves_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movie.mkv"
            source.write_bytes(b"media")
            output_csv = root / "rerun.csv"
            record = _audit_record(
                Path=str(source),
                MediaType="Movie",
                LookupTitle="Movie",
                IssueCodes="needs-rerun",
            )
            service = RerunCsvService(
                {
                    str(source).casefold(): {
                        "exists": True,
                        "source_size": source.stat().st_size,
                        "source_mtime_utc": "2026-07-14T00:00:00+00:00",
                        "source_identity_v2": "sample-identity-v2",
                        "source_content_sha256": "C" * 64,
                        "source_content_sha256_algorithm": "sha256-full-file",
                    }
                }
            )

            count = service.save_rerun_records_csv(
                output_csv,
                [record],
                _resolved(root),
                stage_mode="move",
                original_mode="delete",
                return_mode="publish",
            )
            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["enabled"], "true")
        self.assertEqual(rows[0]["stage_mode"], "copy")
        self.assertEqual(rows[0]["post_success_original"], "keep")
        self.assertEqual(rows[0]["return_mode"], "park")
        self.assertEqual(rows[0]["source_size"], "5")
        self.assertTrue(rows[0]["source_mtime_utc"].endswith("+00:00"))
        self.assertEqual(rows[0]["source_content_sha256"], "c" * 64)
        self.assertEqual(rows[0]["source_content_sha256_algorithm"], "sha256-full-file")

    def test_apply_rerun_source_metadata_disables_invalid_full_content_hash(self) -> None:
        updated = apply_rerun_source_metadata(
            {
                "enabled": "true",
                "source_identity_v2": "sample-v2",
                "source_content_sha256": "",
                "source_content_sha256_algorithm": "",
                "notes": "",
            },
            {
                "exists": True,
                "source_identity_v2": "sample-v2",
                "source_content_sha256": "not-a-sha256",
                "source_content_sha256_algorithm": "sha256-full-file",
            },
        )

        self.assertEqual(updated["enabled"], "false")
        self.assertEqual(updated["source_content_sha256"], "")
        self.assertIn("full-content SHA-256", updated["notes"])

    def test_apply_rerun_source_metadata_disables_missing_metadata(self) -> None:
        updated = apply_rerun_source_metadata(
            {
                "enabled": "true",
                "source_identity_v2": "sample-v2",
                "source_content_sha256": "",
                "source_content_sha256_algorithm": "",
                "notes": "",
            },
            None,
        )

        self.assertEqual(updated["enabled"], "false")
        self.assertIn("metadata unavailable", updated["notes"])

    def test_apply_rerun_source_metadata_rejects_non_full_file_hash_algorithm(self) -> None:
        updated = apply_rerun_source_metadata(
            {
                "enabled": "true",
                "source_identity_v2": "sample-v2",
                "source_content_sha256": "",
                "source_content_sha256_algorithm": "",
                "notes": "",
            },
            {
                "exists": True,
                "source_identity_v2": "sample-v2",
                "source_content_sha256": "d" * 64,
                "source_content_sha256_algorithm": "sha256-sample-v2",
            },
        )

        self.assertEqual(updated["enabled"], "false")
        self.assertEqual(updated["source_content_sha256"], "")
        self.assertEqual(updated["source_content_sha256_algorithm"], "")
        self.assertIn("sha256-full-file", updated["notes"])

    def test_service_csv_writer_disables_duplicate_planned_output_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            correct = root / "Movies" / "Jurassic World Fallen Kingdom (2018)" / "Jurassic World Fallen Kingdom (2018).mkv"
            typo = root / "Movies" / "Jurrasic World Fallen Kingdom (2018)" / "Jurassic World Fallen Kingdom (2018).mkv"
            for path in (correct, typo):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            output_csv = root / "rerun.csv"
            records = [
                _audit_record(Path=str(correct), MediaType="Movie", LookupTitle="Jurassic World Fallen Kingdom (2018)"),
                _audit_record(Path=str(typo), MediaType="Movie", LookupTitle="Jurassic World Fallen Kingdom (2018)"),
            ]
            service = RerunCsvService(
                {
                    str(path).casefold(): {
                        "exists": True,
                        "source_content_sha256": f"{index + 1:x}" * 64,
                        "source_content_sha256_algorithm": "sha256-full-file",
                    }
                    for index, path in enumerate((correct, typo))
                }
            )

            count = service.save_rerun_records_csv(
                output_csv,
                records,
                _resolved(root),
                stage_mode="copy",
                original_mode="keep",
                return_mode="park",
            )
            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(count, 2)
        self.assertEqual(rows[0]["enabled"], "true")
        self.assertEqual(rows[1]["enabled"], "false")
        self.assertIn("disabled duplicate planned output path", rows[1]["notes"])
        self.assertIn("kept_row_index=0", rows[1]["notes"])
        self.assertIn("jurassic world fallen kingdom (2018)", rows[1]["notes"])


if __name__ == "__main__":
    unittest.main()
