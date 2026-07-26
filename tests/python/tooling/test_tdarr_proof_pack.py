from __future__ import annotations

import csv
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.core.diagnostics.tdarr_matrix_proof import (
    TDARR_PROOF_CASE_IDS_BY_BUCKET,
    TDARR_PROOF_PACK_SENTINEL,
    tdarr_case_ids_for_pack,
    tdarr_case_keys_for_pack,
    tdarr_expected_manifest_count,
    tdarr_expected_source_count,
    tdarr_legacy_cleanup_targets,
)
from mediapipeline.tools.dev import tdarr_matrix_audit
from mediapipeline.tools.dev import tdarr_proof_pack


MANIFEST_FIELDNAMES = [
    "schema_version",
    "view",
    "case_id",
    "diagnostic_bucket",
    "generated_path",
    "source_path",
    "original_name",
    "source_url",
    "source_page",
    "medium",
    "container",
    "resolution",
    "video_codec",
    "audio_codec",
    "duration",
    "advertised_size_mb",
    "actual_size_bytes",
    "sha256",
    "link_mode",
]


def write_template(root: Path) -> Path:
    template = root / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(
        "@{\n"
        "    SourceMovies = 'C:\\Media\\Movies'\n"
        "    SourceTV = 'C:\\Media\\TV'\n"
        "    Outsource = 'C:\\Media\\Out'\n"
        "    LocalBase = 'C:\\Media\\Scratch'\n"
        "    FinalLibraryPromotionEnabled = $true\n"
        "    FinalLibraryPromotionRules = @()\n"
        "    FinalLibraryPromotionCleanupAfterVerified = $true\n"
        "    FinalLibraryPromotionOverwriteExisting = $true\n"
        "    OutputContainer = 'mp4'\n"
        "    DynamicHdrPolicy = 'off'\n"
        "    EncodeLadder = 'movie_archive'\n"
        "    ValidExtensions = @('.mkv')\n"
        "}\n",
        encoding="utf-8",
    )
    return template


def write_source_manifest(root: Path) -> tuple[Path, dict[str, Path]]:
    source_library = root / "source-library"
    source_files: dict[str, Path] = {}
    rows: list[dict[str, str]] = []
    for bucket, case_ids in TDARR_PROOF_CASE_IDS_BY_BUCKET.items():
        for case_id in case_ids:
            source = source_library / "files" / f"{case_id}.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(f"{case_id}-source".encode())
            source_files[case_id] = source
            sha256 = tdarr_matrix_audit.sha256_file(source)
            for view in ("movies", "tv"):
                generated_path = (
                    f"source/Movies/Fake Title {case_id[-4:]} (2026) [Tdarr 1080p h264 aac mkv {case_id}].mkv"
                    if view == "movies"
                    else f"source/TV/TDProof/Season 01/TDProof - S01E01 - Fake Episode [Tdarr 1080p h264 aac mkv {case_id}].mkv"
                )
                rows.append(
                    {
                        "schema_version": "tdarr_matrix_materialized_library.v1",
                        "view": view,
                        "case_id": case_id,
                        "diagnostic_bucket": bucket,
                        "generated_path": generated_path,
                        "source_path": str(source),
                        "original_name": source.name,
                        "source_url": f"https://samples.tdarr.io/api/v1/samples/{source.name}",
                        "source_page": "https://home.tdarr.io/samples/",
                        "medium": "video",
                        "container": "mkv",
                        "resolution": "1080p",
                        "video_codec": "h264",
                        "audio_codec": "aac",
                        "duration": "1",
                        "advertised_size_mb": "1",
                        "actual_size_bytes": str(source.stat().st_size),
                        "sha256": sha256,
                        "link_mode": "hardlink",
                    }
                )
    manifest = source_library / "manifests" / "materialized_library.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return manifest, source_files


class TdarrProofPackTests(unittest.TestCase):
    def test_proof_and_smoke_case_sets_are_fixed_and_nested(self) -> None:
        smoke_ids = set(tdarr_case_ids_for_pack("smoke-pack"))
        proof_ids = set(tdarr_case_ids_for_pack("proof-pack"))

        self.assertEqual(tdarr_expected_source_count("proof-pack"), 46)
        self.assertEqual(tdarr_expected_manifest_count("proof-pack"), 92)
        self.assertEqual(tdarr_expected_source_count("smoke-pack"), 12)
        self.assertEqual(tdarr_expected_manifest_count("smoke-pack"), 24)
        self.assertTrue(smoke_ids.issubset(proof_ids))
        self.assertIn("tdarr-0063:movies", tdarr_case_keys_for_pack("smoke-pack"))
        self.assertIn("tdarr-2125:tv", tdarr_case_keys_for_pack("proof-pack"))

    def test_materialize_proof_pack_copies_cache_and_writes_verified_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_manifest, source_files = write_source_manifest(root)
            proof_root = root / "proof-pack"

            summary = tdarr_proof_pack.materialize_proof_pack(
                proof_root=proof_root,
                source_manifest=source_manifest,
                template_path=write_template(root),
                allowed_test_parent=root,
            )
            verification = tdarr_proof_pack.verify_proof_pack(proof_root)

            cache = proof_root / "cache" / "files" / "tdarr-0002" / "tdarr-0002.mkv"
            generated = proof_root / "source" / "Movies" / "Fake Title 0002 (2026) [Tdarr 1080p h264 aac mkv tdarr-0002].mkv"

            self.assertTrue(summary["ok"])
            self.assertTrue(verification["ok"])
            self.assertEqual(summary["source_count"], 46)
            self.assertEqual(summary["manifest_count"], 92)
            self.assertTrue((proof_root / TDARR_PROOF_PACK_SENTINEL).exists())
            self.assertTrue((proof_root / "manifests" / "proof_pack_cases.json").exists())
            self.assertTrue((proof_root / "manifests" / "pass_history.json").exists())
            self.assertTrue(cache.exists())
            self.assertTrue(generated.exists())
            self.assertFalse(os.path.samefile(source_files["tdarr-0002"], cache))
            self.assertTrue(os.path.samefile(cache, generated))

    def test_cleanup_flow_refuses_delete_until_proof_is_verified_and_archived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_manifest, _source_files = write_source_manifest(root)
            proof_root = root / "proof-pack"
            tdarr_proof_pack.materialize_proof_pack(
                proof_root=proof_root,
                source_manifest=source_manifest,
                template_path=write_template(root),
                allowed_test_parent=root,
            )
            targets = tdarr_legacy_cleanup_targets(root)
            matrix_root = targets["legacy_matrix_library"]
            matrix_root.mkdir(parents=True)
            (matrix_root / tdarr_proof_pack.materializer.SENTINEL_NAME).write_text("{}", encoding="utf-8")
            (matrix_root / "manifests").mkdir()
            (matrix_root / "manifests" / "materialized_library.csv").write_text("case_id\n", encoding="utf-8")
            runs_root = targets["legacy_matrix_runs"]
            run_root = runs_root / "run-001"
            (run_root / "manifests" / "audit").mkdir(parents=True)
            (run_root / tdarr_matrix_audit.AUDIT_RUN_SENTINEL).write_text(
                json.dumps({"schema_version": "tdarr_matrix_audit.v1"}),
                encoding="utf-8",
            )
            (run_root / "manifests" / "audit" / "tdarr_matrix_audit_report.json").write_text("{}", encoding="utf-8")
            cache_root = targets["legacy_download_cache"]
            cache_root.mkdir(parents=True)
            (cache_root / "inventory.csv").write_text("name\n", encoding="utf-8")

            plan = tdarr_proof_pack.cleanup_plan(workspace_root=root, proof_root=proof_root)
            with self.assertRaisesRegex(ValueError, "confirm_delete_full_matrix"):
                tdarr_proof_pack.delete_full_matrix(workspace_root=root, proof_root=proof_root, confirm_delete=False)
            with self.assertRaisesRegex(ValueError, "archive"):
                tdarr_proof_pack.delete_full_matrix(workspace_root=root, proof_root=proof_root, confirm_delete=True)
            archive = tdarr_proof_pack.archive_full_matrix_reports(workspace_root=root, proof_root=proof_root)
            deleted = tdarr_proof_pack.delete_full_matrix(workspace_root=root, proof_root=proof_root, confirm_delete=True)

        self.assertTrue(plan["ok"])
        self.assertFalse(plan["archive_exists"])
        self.assertGreaterEqual(archive["copied_count"], 2)
        self.assertEqual(deleted["removed_count"], 3)
        self.assertFalse(matrix_root.exists())
        self.assertFalse(runs_root.exists())
        self.assertFalse(cache_root.exists())

    def test_rebuild_rejects_untrusted_roots_and_sentinels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_manifest, _source_files = write_source_manifest(root)
            template = write_template(root)
            outside = root / "outside-cli-root"
            keep = outside / "keep.txt"
            keep.parent.mkdir(parents=True)
            keep.write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "canonical Tdarr Proof Pack root"):
                tdarr_proof_pack.materialize_proof_pack(
                    proof_root=outside,
                    source_manifest=source_manifest,
                    template_path=template,
                    rebuild=True,
                )
            self.assertEqual(keep.read_text(encoding="utf-8"), "preserve")

            schema_only = root / "schema-only"
            schema_only.mkdir()
            schema_keep = schema_only / "keep.txt"
            schema_keep.write_text("preserve", encoding="utf-8")
            (schema_only / TDARR_PROOF_PACK_SENTINEL).write_text(
                json.dumps({"schema_version": tdarr_proof_pack.TDARR_PROOF_PACK_SCHEMA_VERSION}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "has no root identity"):
                tdarr_proof_pack.prepare_proof_root(
                    schema_only,
                    rebuild=True,
                    allowed_test_parent=root,
                )
            self.assertEqual(schema_keep.read_text(encoding="utf-8"), "preserve")

            malformed = root / "malformed-sentinel"
            malformed.mkdir()
            malformed_keep = malformed / "keep.txt"
            malformed_keep.write_text("preserve", encoding="utf-8")
            (malformed / TDARR_PROOF_PACK_SENTINEL).write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unreadable or malformed"):
                tdarr_proof_pack.prepare_proof_root(
                    malformed,
                    rebuild=True,
                    allowed_test_parent=root,
                )
            self.assertEqual(malformed_keep.read_text(encoding="utf-8"), "preserve")

            wrong_purpose = root / "wrong-purpose"
            wrong_purpose.mkdir()
            wrong_purpose_keep = wrong_purpose / "keep.txt"
            wrong_purpose_keep.write_text("preserve", encoding="utf-8")
            wrong_purpose_payload = {
                "schema_version": tdarr_proof_pack.TDARR_PROOF_PACK_SCHEMA_VERSION,
                "proof_root": str(wrong_purpose),
                "root_identity": tdarr_proof_pack.proof_root_identity_payload(wrong_purpose),
            }
            wrong_purpose_payload["root_identity"]["purpose"] = "unrelated_directory"
            (wrong_purpose / TDARR_PROOF_PACK_SENTINEL).write_text(
                json.dumps(wrong_purpose_payload),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "purpose does not match"):
                tdarr_proof_pack.prepare_proof_root(
                    wrong_purpose,
                    rebuild=True,
                    allowed_test_parent=root,
                )
            self.assertEqual(wrong_purpose_keep.read_text(encoding="utf-8"), "preserve")

            trusted = root / "trusted"
            tdarr_proof_pack.materialize_proof_pack(
                proof_root=trusted,
                source_manifest=source_manifest,
                template_path=template,
                allowed_test_parent=root,
            )
            copied = root / "copied-sentinel"
            copied.mkdir()
            copied_keep = copied / "keep.txt"
            copied_keep.write_text("preserve", encoding="utf-8")
            (copied / TDARR_PROOF_PACK_SENTINEL).write_text(
                (trusted / TDARR_PROOF_PACK_SENTINEL).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "proof_root_sha256 does not match"):
                tdarr_proof_pack.prepare_proof_root(
                    copied,
                    rebuild=True,
                    allowed_test_parent=root,
                )
            self.assertEqual(copied_keep.read_text(encoding="utf-8"), "preserve")

            allowed = root / "allowed"
            allowed.mkdir()
            link_target = root / "link-target"
            link_target.mkdir()
            link_keep = link_target / "keep.txt"
            link_keep.write_text("preserve", encoding="utf-8")
            link = allowed / "proof-link"
            try:
                link.symlink_to(link_target, target_is_directory=True)
            except OSError as exc:
                if os.name != "nt":
                    self.skipTest(f"directory symlink creation unavailable: {exc}")
                junction = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(link_target)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if junction.returncode != 0:
                    self.skipTest(f"directory junction creation unavailable: {junction.stderr.strip() or exc}")
            with self.assertRaisesRegex(ValueError, "symlink or junction"):
                tdarr_proof_pack.prepare_proof_root(
                    link,
                    rebuild=True,
                    allowed_test_parent=allowed,
                )
            self.assertEqual(link_keep.read_text(encoding="utf-8"), "preserve")

    def test_rebuild_quarantines_prior_root_and_rolls_back_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_manifest, _source_files = write_source_manifest(root)
            template = write_template(root)
            proof_root = root / "proof-pack"
            tdarr_proof_pack.materialize_proof_pack(
                proof_root=proof_root,
                source_manifest=source_manifest,
                template_path=template,
                allowed_test_parent=root,
            )
            (proof_root / "old-only.txt").write_text("recoverable", encoding="utf-8")

            rebuilt = tdarr_proof_pack.materialize_proof_pack(
                proof_root=proof_root,
                source_manifest=source_manifest,
                template_path=template,
                rebuild=True,
                allowed_test_parent=root,
            )
            quarantine = Path(rebuilt["quarantine_root"])
            self.assertTrue(rebuilt["ok"])
            self.assertTrue((quarantine / "old-only.txt").exists())
            self.assertTrue(tdarr_proof_pack.verify_proof_pack(proof_root)["ok"])

            (proof_root / "restore-me.txt").write_text("restore", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                tdarr_proof_pack.materialize_proof_pack(
                    proof_root=proof_root,
                    source_manifest=source_manifest,
                    template_path=root / "missing-template.psd1",
                    rebuild=True,
                    allowed_test_parent=root,
                )
            self.assertEqual((proof_root / "restore-me.txt").read_text(encoding="utf-8"), "restore")
            self.assertEqual(len(list(root.glob("proof-pack.failed.*"))), 1)


if __name__ == "__main__":
    unittest.main()
