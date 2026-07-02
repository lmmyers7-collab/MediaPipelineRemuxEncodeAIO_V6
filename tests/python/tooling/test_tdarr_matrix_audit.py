from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mediapipeline.tools.dev import tdarr_matrix_audit as audit


BUCKETS = (
    "audio-only",
    "h264-h265-direct",
    "av1-vp-modern",
    "legacy-video",
    "mjpeg-large",
    "container-stress",
)


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_template(root: Path) -> Path:
    template = root / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
    template.parent.mkdir(parents=True)
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


def manifest_row(
    root: Path,
    *,
    view: str = "movies",
    bucket: str = "h264-h265-direct",
    case_id: str = "tdarr-0001",
    generated_path: str | None = None,
    source_path: Path | None = None,
    medium: str = "video",
    container: str = "mkv",
    video_codec: str = "h264",
    audio_codec: str = "aac",
    size: int = 10,
    sha256: str = "a" * 64,
) -> dict[str, str]:
    extension = ".mkv"
    if generated_path is None:
        if view == "movies":
            generated_path = f"source/Movies/{bucket}/Fake Title {case_id[-4:]} (2026) [Tdarr 1080p h264 aac mkv {case_id}]{extension}"
        else:
            generated_path = f"source/TV/TDDirect/Season 01/TDDirect - S01E01 - Fake Episode [Tdarr 1080p h264 aac mkv {case_id}]{extension}"
    if source_path is None:
        source_path = root / "cache" / f"{case_id}{extension}"
    return {
        "schema_version": "tdarr_matrix_materialized_library.v1",
        "view": view,
        "case_id": case_id,
        "diagnostic_bucket": bucket,
        "generated_path": generated_path,
        "source_path": str(source_path),
        "original_name": f"{case_id}{extension}",
        "source_url": f"https://samples.tdarr.io/api/v1/samples/{case_id}{extension}",
        "source_page": "https://home.tdarr.io/samples/",
        "medium": medium,
        "container": container,
        "resolution": "1080p",
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "duration": "30s",
        "advertised_size_mb": "1.0",
        "actual_size_bytes": str(size),
        "sha256": sha256,
        "link_mode": "hardlink",
    }


class TdarrMatrixAuditTests(unittest.TestCase):
    def test_load_manifest_rows_normalizes_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            row = manifest_row(root)
            write_manifest(library_root / "manifests" / "materialized_library.csv", [row])

            rows = audit.load_manifest_rows(library_root / "manifests" / "materialized_library.csv", library_root=library_root)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].view, "movies")
            self.assertEqual(rows[0].generated_path, row["generated_path"])
            self.assertEqual(rows[0].generated_abs, library_root / row["generated_path"])

    def test_load_manifest_rows_rejects_unsafe_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            manifest_path = library_root / "manifests" / "materialized_library.csv"
            for index, generated_path in enumerate(
                (
                    str(root / "outside-linked.mkv"),
                    "../outside-linked.mkv",
                    "source/Movies/../outside-linked.mkv",
                    "C:outside-linked.mkv",
                ),
                start=1,
            ):
                row = manifest_row(root, case_id=f"tdarr-{index:04d}", generated_path=generated_path)
                write_manifest(manifest_path, [row])

                with self.subTest(generated_path=generated_path):
                    with self.assertRaisesRegex(ValueError, "generated_path"):
                        audit.load_manifest_rows(manifest_path, library_root=library_root)

    def test_audit_queue_snapshot_flags_missing_kind_mismatch_and_missing_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            movie = audit.ManifestRow.from_record(manifest_row(root, view="movies"), library_root=library_root)
            tv = audit.ManifestRow.from_record(
                manifest_row(root, view="tv", case_id="tdarr-0002"),
                library_root=library_root,
            )
            snapshot = {
                "schema_version": "queue_plan_snapshot.v1",
                "rows": [
                    {
                        "source_path": str(movie.generated_abs),
                        "media_kind": "tv",
                        "library_designation": "tv",
                        "run_queue_index": 1,
                        "blocked_reason_code": "",
                        "route": "",
                    }
                ],
                "excluded_rows": [],
            }

            findings = audit.audit_queue_snapshot([movie, tv], snapshot)
            codes = {finding.code for finding in findings}

            self.assertIn("media_kind_mismatch", codes)
            self.assertIn("route_preview_missing", codes)
            self.assertIn("queue_row_missing", codes)

    def test_exit_status_is_strict_by_default(self) -> None:
        findings = [
            audit.Finding(severity="warning", code="classified_processing_failure", message="classified"),
            audit.Finding(severity="error", code="queue_row_missing", message="missing"),
        ]

        self.assertEqual(audit.exit_code_for_findings(findings, strict=True), 1)
        self.assertEqual(audit.exit_code_for_findings(findings, strict=False), 0)
        self.assertEqual(audit.exit_code_for_findings(findings[:1], strict=True), 0)

    def test_sample_selection_is_balanced_and_spread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            rows: list[audit.ManifestRow] = []
            case_number = 1
            for bucket in BUCKETS:
                for index in range(8):
                    view = "movies" if index % 2 == 0 else "tv"
                    rows.append(
                        audit.ManifestRow.from_record(
                            manifest_row(
                                root,
                                view=view,
                                bucket=bucket,
                                case_id=f"tdarr-{case_number:04d}",
                                generated_path=f"source/{'Movies' if view == 'movies' else 'TV'}/{bucket}/sample-{case_number:04d}.mkv",
                                size=index + 1,
                            ),
                            library_root=library_root,
                        )
                    )
                    case_number += 1

            selected = audit.select_sample_rows(rows, samples_per_bucket=5)

            self.assertEqual(len(selected), 30)
            for bucket in BUCKETS:
                bucket_rows = [row for row in selected if row.diagnostic_bucket == bucket]
                self.assertEqual(len(bucket_rows), 5)
                self.assertEqual({row.view for row in bucket_rows}, {"movies", "tv"})
                self.assertIn(1, {row.actual_size_bytes for row in bucket_rows})
                self.assertIn(8, {row.actual_size_bytes for row in bucket_rows})

    def test_all_sample_selection_keeps_every_manifest_row_in_bucket_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            rows = [
                audit.ManifestRow.from_record(
                    manifest_row(root, bucket="container-stress", case_id="tdarr-0003", size=3),
                    library_root=library_root,
                ),
                audit.ManifestRow.from_record(
                    manifest_row(root, bucket="audio-only", case_id="tdarr-0001", medium="audio", video_codec="", size=1),
                    library_root=library_root,
                ),
                audit.ManifestRow.from_record(
                    manifest_row(root, bucket="h264-h265-direct", case_id="tdarr-0002", size=2),
                    library_root=library_root,
                ),
            ]

            selected = audit.select_all_sample_rows(rows)

            self.assertEqual(len(selected), 3)
            self.assertEqual([row.case_id for row in selected], ["tdarr-0001", "tdarr-0002", "tdarr-0003"])
            self.assertTrue(audit.parse_args(["run-samples", "--all-samples"]).all_samples)

    def test_auto_sample_selection_skips_probe_mismatched_mjpeg_mp2_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            bad = audit.ManifestRow.from_record(
                manifest_row(
                    root,
                    bucket="mjpeg-large",
                    case_id="tdarr-1222",
                    generated_path="source/TV/TDMjpeg/Season 01/TDMjpeg - S18E22 - Fake Episode [Tdarr 240p mjpeg mp3 mp2 tdarr-1222].mp2",
                    source_path=root / "cache" / "tdarr-1222.mp2",
                    container="mp2",
                    video_codec="mjpeg",
                    audio_codec="mp3",
                    size=1,
                ),
                library_root=library_root,
            )
            valid = audit.ManifestRow.from_record(
                manifest_row(
                    root,
                    bucket="mjpeg-large",
                    case_id="tdarr-1223",
                    generated_path="source/Movies/mjpeg-large/Fake Title 1223 (2026) [Tdarr 480p mjpeg aac mov tdarr-1223].mov",
                    source_path=root / "cache" / "tdarr-1223.mov",
                    container="mov",
                    video_codec="mjpeg",
                    audio_codec="aac",
                    size=2,
                ),
                library_root=library_root,
            )
            original_available = audit.ffprobe_command_available
            original_probe = audit.probe_fixture_row

            def fake_probe(row: audit.ManifestRow, **_kwargs):
                if audit.manifest_case_key(row) == audit.manifest_case_key(bad):
                    return audit.FixtureProbeResult(
                        expected_video=True,
                        probe_ok=True,
                        has_video=False,
                        format_name="mp3",
                        streams=({"index": 0, "codec_type": "audio", "codec_name": "mp3"},),
                    )
                return audit.FixtureProbeResult(
                    expected_video=True,
                    probe_ok=True,
                    has_video=True,
                    format_name="mov,mp4,m4a,3gp,3g2,mj2",
                    streams=({"index": 0, "codec_type": "video", "codec_name": "mjpeg"},),
                )

            try:
                audit.ffprobe_command_available = lambda _ffprobe: True
                audit.probe_fixture_row = fake_probe
                selected, findings, probes = audit.select_sample_rows_with_fixture_probe_filter(
                    [bad, valid],
                    samples_per_bucket=1,
                    ffprobe="ffprobe",
                )
            finally:
                audit.ffprobe_command_available = original_available
                audit.probe_fixture_row = original_probe

            self.assertEqual([audit.manifest_case_key(row) for row in selected], [audit.manifest_case_key(valid)])
            self.assertEqual([finding.code for finding in findings], ["fixture_probe_mismatch"])
            self.assertTrue(probes[audit.manifest_case_key(valid)].has_video)

    def test_explicit_case_selection_records_fixture_probe_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            row = audit.ManifestRow.from_record(
                manifest_row(
                    root,
                    bucket="mjpeg-large",
                    case_id="tdarr-1222",
                    generated_path="source/TV/TDMjpeg/Season 01/TDMjpeg - S18E22 - Fake Episode [Tdarr 240p mjpeg mp3 mp2 tdarr-1222].mp2",
                    source_path=root / "cache" / "tdarr-1222.mp2",
                    container="mp2",
                    video_codec="mjpeg",
                    audio_codec="mp3",
                ),
                library_root=library_root,
            )
            original_available = audit.ffprobe_command_available
            original_probe = audit.probe_fixture_row

            def fake_probe(*_args, **_kwargs):
                return audit.FixtureProbeResult(
                    expected_video=True,
                    probe_ok=True,
                    has_video=False,
                    format_name="mp3",
                    streams=({"index": 0, "codec_type": "audio", "codec_name": "mp3"},),
                )

            try:
                audit.ffprobe_command_available = lambda _ffprobe: True
                audit.probe_fixture_row = fake_probe
                selected = audit.select_case_key_rows([row], [audit.manifest_case_key(row)])
                _probes, findings = audit.audit_fixture_video_probes(selected, ffprobe="ffprobe")
            finally:
                audit.ffprobe_command_available = original_available
                audit.probe_fixture_row = original_probe

            self.assertEqual(selected, [row])
            self.assertEqual([finding.code for finding in findings], ["fixture_probe_mismatch"])
            self.assertEqual(findings[0].severity, "warning")
            self.assertEqual(findings[0].evidence["format_name"], "mp3")
            self.assertTrue(findings[0].evidence["expected_negative"])
            self.assertEqual(findings[0].evidence["classification"], "fixture_metadata_no_usable_video")

    def test_fixture_probe_mismatch_is_warning_not_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            row = audit.ManifestRow.from_record(
                manifest_row(root, bucket="mjpeg-large", case_id="tdarr-1222", container="mp2", video_codec="mjpeg"),
                library_root=library_root,
            )
            finding = audit.fixture_probe_mismatch_finding(
                row,
                audit.FixtureProbeResult(expected_video=True, probe_ok=True, has_video=False, format_name="mp3"),
            )

            self.assertEqual(finding.code, "fixture_probe_mismatch")
            self.assertEqual(finding.severity, "warning")
            self.assertTrue(finding.evidence["expected_negative"])
            self.assertEqual(audit.exit_code_for_findings([finding], strict=True), 0)

    def test_materialize_run_subset_uses_hardlinks_and_guarded_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "LocalBase" / "TestFixtures" / "TdarrSamples" / "files" / "sample.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"sample")
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            row_record = manifest_row(
                root,
                source_path=source,
                generated_path="source/Movies/h264-h265-direct/Fake Title 0001 (2026) [Tdarr 1080p h264 aac mkv tdarr-0001].mkv",
                sha256=audit.sha256_file(source),
            )
            row = audit.ManifestRow.from_record(row_record, library_root=library_root)
            template = write_template(root)
            run_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns" / "run-001"

            audit.materialize_run_subset(
                rows=[row],
                run_root=run_root,
                repo_root=root,
                template_path=template,
                rebuild=False,
            )

            generated = run_root / row.generated_path
            self.assertTrue(generated.exists())
            self.assertTrue(os.path.samefile(source, generated))
            self.assertTrue((run_root / audit.AUDIT_RUN_SENTINEL).exists())
            self.assertTrue((run_root / "config" / audit.CONFIG_NAME).exists())

            unsafe = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns" / "manual"
            unsafe.mkdir(parents=True)
            (unsafe / "manual.txt").write_text("manual", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                audit.prepare_run_root(unsafe, repo_root=root, rebuild=True)

    def test_materialize_run_subset_rejects_forged_generated_path_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "LocalBase" / "TestFixtures" / "TdarrSamples" / "files" / "sample.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"sample")
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            row = audit.ManifestRow.from_record(
                manifest_row(
                    root,
                    source_path=source,
                    generated_path="source/Movies/h264-h265-direct/sample.mkv",
                    sha256=audit.sha256_file(source),
                ),
                library_root=library_root,
            )
            template = write_template(root)
            run_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns" / "run-unsafe"
            outside_target = root / "outside-linked.mkv"

            for generated_path in ("../outside-linked.mkv", str(outside_target)):
                with self.subTest(generated_path=generated_path):
                    unsafe_row = replace(row, generated_path=generated_path)

                    with self.assertRaisesRegex(ValueError, "generated_path"):
                        audit.materialize_run_subset(
                            rows=[unsafe_row],
                            run_root=run_root,
                            repo_root=root,
                            template_path=template,
                            rebuild=False,
                        )

                    self.assertFalse(run_root.exists())
                    self.assertFalse(outside_target.exists())

    def test_materialize_run_subset_rejects_external_source_path_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_source = root / "LocalBase" / "TestFixtures" / "TdarrSamples" / "files" / "sample.mkv"
            fixture_source.parent.mkdir(parents=True)
            fixture_source.write_bytes(b"sample")
            external_source = root / "external-media" / "production.mkv"
            external_source.parent.mkdir(parents=True)
            external_source.write_bytes(b"production")
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            row = audit.ManifestRow.from_record(
                manifest_row(
                    root,
                    source_path=fixture_source,
                    generated_path="source/Movies/h264-h265-direct/sample.mkv",
                    sha256=audit.sha256_file(fixture_source),
                ),
                library_root=library_root,
            )
            unsafe_row = replace(row, source_path=external_source)
            template = write_template(root)
            run_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns" / "run-external-source"

            with self.assertRaisesRegex(ValueError, "source_path"):
                audit.materialize_run_subset(
                    rows=[unsafe_row],
                    run_root=run_root,
                    repo_root=root,
                    template_path=template,
                    rebuild=False,
                )

            self.assertFalse(run_root.exists())

    def test_command_builders_use_pipeline_entrypoint_and_worker_result(self) -> None:
        config = Path("C:/matrix/config/MediaPipeline_config.tdarr-matrix.psd1")
        entry = Path("C:/repo/ops/pipeline/entrypoints/MediaPipeline.ps1")
        queue = Path("C:/matrix/manifests/audit/queue_snapshot.json")
        worker_result = Path("C:/matrix/manifests/audit/files/tdarr-0001/worker_result.json")

        validate = audit.build_validate_command("powershell", entry, config)
        queue_command = audit.build_queue_snapshot_command("powershell", entry, config, queue)
        single = audit.build_single_file_command(
            "powershell",
            entry,
            config,
            Path("C:/matrix/source/Movies/sample.mkv"),
            worker_result,
            run_id="run-001",
            claim_id="tdarr-0001-movies",
        )

        self.assertIn("-ValidateOnly", validate)
        self.assertIn("-EmitQueuePlan", queue_command)
        self.assertIn(str(queue), queue_command)
        self.assertIn("-SingleFile", single)
        self.assertIn("-WorkerChild", single)
        self.assertIn("-WorkerResultPath", single)
        self.assertIn(str(worker_result), single)

    def test_source_hash_and_containment_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns" / "run-001"
            generated = library_root / "source" / "Movies" / "sample.mkv"
            generated.parent.mkdir(parents=True)
            generated.write_bytes(b"changed")
            row = audit.ManifestRow.from_record(
                manifest_row(
                    root,
                    generated_path="source/Movies/sample.mkv",
                    source_path=generated,
                    sha256="0" * 64,
                ),
                library_root=library_root,
            )
            completed = library_root / "scratch" / "State" / "Completed" / "completed_jobs.jsonl"
            completed.parent.mkdir(parents=True)
            completed.write_text(json.dumps({"output_path": str(root / "outside" / "movie.mkv")}) + "\n", encoding="utf-8")

            findings = audit.audit_source_hashes([row]) + audit.audit_path_containment(library_root)
            codes = {finding.code for finding in findings}

            self.assertIn("source_hash_changed", codes)
            self.assertIn("path_escaped_test_root", codes)

    @staticmethod
    def _make_outcome(tmp_dir: Path, *, returncode: int | None = 0, timed_out: bool = False) -> audit.ProcessOutcome:
        return audit.ProcessOutcome(
            command=["pwsh", "-File", "MediaPipeline.ps1"],
            returncode=returncode,
            timed_out=timed_out,
            duration_seconds=1.0,
            stdout_path=tmp_dir / "stdout.log",
            stderr_path=tmp_dir / "stderr.log",
        )

    @staticmethod
    def _write_worker(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_command_failure_finding_classifies_timeout_and_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                audit.command_failure_finding("validate", self._make_outcome(root, returncode=None, timed_out=True)).code,
                "subprocess_timeout",
            )
            self.assertEqual(
                audit.command_failure_finding("validate", self._make_outcome(root, returncode=2)).code,
                "subprocess_failed",
            )
            self.assertIsNone(audit.command_failure_finding("validate", self._make_outcome(root, returncode=0)))
            self.assertIsNone(audit.command_failure_finding("validate", self._make_outcome(root, returncode=None)))

    def test_audit_worker_result_success_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            result_path = library_root / "manifests" / "audit" / "files" / "worker_result.json"
            direct = audit.ManifestRow.from_record(manifest_row(root, bucket="h264-h265-direct"), library_root=library_root)
            self._write_worker(result_path, {"Success": True, "Status": "Completed"})
            self.assertEqual(
                audit.audit_worker_result(direct, result_path=result_path, outcome=self._make_outcome(root), library_root=library_root),
                [],
            )
            audio = audit.ManifestRow.from_record(
                manifest_row(root, bucket="audio-only", case_id="tdarr-0002"), library_root=library_root
            )
            findings = audit.audit_worker_result(audio, result_path=result_path, outcome=self._make_outcome(root), library_root=library_root)
            self.assertEqual([finding.code for finding in findings], ["audio_only_processed_successfully"])
            self.assertEqual(findings[0].severity, "warning")

    def test_audit_worker_result_missing_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            row = audit.ManifestRow.from_record(manifest_row(root), library_root=library_root)
            missing = library_root / "absent.json"
            findings = audit.audit_worker_result(row, result_path=missing, outcome=self._make_outcome(root), library_root=library_root)
            self.assertEqual([finding.code for finding in findings], ["worker_result_missing"])
            self.assertEqual(findings[0].severity, "error")
            findings = audit.audit_worker_result(
                row, result_path=missing, outcome=self._make_outcome(root, returncode=None, timed_out=True), library_root=library_root
            )
            self.assertEqual([finding.code for finding in findings], ["subprocess_timeout"])
            self.assertEqual(findings[0].severity, "critical")

    def test_audit_worker_result_classifies_startup_config_failure_from_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            row = audit.ManifestRow.from_record(manifest_row(root), library_root=library_root)
            missing = library_root / "absent.json"
            stdout = root / "stdout.log"
            stderr = root / "stderr.log"
            stdout.write_text("ERROR: Config missing key: DynamicHdrPolicy\n", encoding="utf-8")
            stderr.write_text("", encoding="utf-8")
            outcome = audit.ProcessOutcome(
                command=["pwsh", "-File", "MediaPipeline.ps1"],
                returncode=1,
                timed_out=False,
                duration_seconds=0.1,
                stdout_path=stdout,
                stderr_path=stderr,
            )

            findings = audit.audit_worker_result(row, result_path=missing, outcome=outcome, library_root=library_root)

            self.assertEqual([finding.code for finding in findings], ["worker_startup_config_invalid"])
            self.assertEqual(findings[0].severity, "error")
            self.assertEqual(findings[0].evidence["missing_config_key"], "DynamicHdrPolicy")

    def test_audit_existing_worker_evidence_replays_file_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            audit_dir = library_root / "manifests" / "audit"
            row = audit.ManifestRow.from_record(manifest_row(root), library_root=library_root)
            item_dir = audit_dir / "files" / audit.safe_slug(f"{row.case_id}-{row.view}")
            item_dir.mkdir(parents=True)
            (item_dir / "stdout.log").write_text("ERROR: Config missing key: DynamicHdrPolicy\n", encoding="utf-8")
            (item_dir / "stderr.log").write_text("", encoding="utf-8")

            findings = audit.audit_existing_worker_evidence([row], library_root=library_root, audit_dir=audit_dir)

            self.assertEqual([finding.code for finding in findings], ["worker_startup_config_invalid"])
            self.assertEqual(findings[0].case_id, row.case_id)

    def test_audit_worker_result_failure_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            row = audit.ManifestRow.from_record(manifest_row(root), library_root=library_root)
            result_path = library_root / "worker_result.json"
            self._write_worker(result_path, {"Success": False, "Status": "Skipped", "Reason": "File already processed"})
            findings = audit.audit_worker_result(row, result_path=result_path, outcome=self._make_outcome(root, returncode=1), library_root=library_root)
            self.assertEqual([finding.code for finding in findings], ["already_processed_skip"])
            self._write_worker(result_path, {"Success": False, "Reason": "ffmpeg crashed", "ErrorCode": "ENCODE_FAIL"})
            findings = audit.audit_worker_result(row, result_path=result_path, outcome=self._make_outcome(root, returncode=1), library_root=library_root)
            self.assertEqual([finding.code for finding in findings], ["classified_processing_failure"])
            self._write_worker(result_path, {"Success": False})
            findings = audit.audit_worker_result(row, result_path=result_path, outcome=self._make_outcome(root, returncode=1), library_root=library_root)
            self.assertEqual([finding.code for finding in findings], ["processing_failure_unclassified"])
            self.assertEqual(findings[0].severity, "error")

    def test_audit_worker_result_classifies_worker_child_guard_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            row = audit.ManifestRow.from_record(manifest_row(root), library_root=library_root)
            result_path = library_root / "worker_result.json"

            for error_code in ("WORKER_CHILD_SINGLE_FILE_EXCEPTION", "WORKER_CHILD_RESULT_FALLBACK"):
                with self.subTest(error_code=error_code):
                    self._write_worker(
                        result_path,
                        {
                            "Success": False,
                            "Status": "failed",
                            "Reason": "SingleFile worker-child guard wrote structured failure evidence.",
                            "ErrorCode": error_code,
                        },
                    )

                    findings = audit.audit_worker_result(
                        row,
                        result_path=result_path,
                        outcome=self._make_outcome(root, returncode=1),
                        library_root=library_root,
                    )

                    self.assertEqual([finding.code for finding in findings], ["classified_processing_failure"])
                    self.assertEqual(findings[0].severity, "warning")
                    self.assertEqual(findings[0].evidence["worker_result"]["ErrorCode"], error_code)
                    self.assertEqual(findings[0].evidence["worker_result_classification"], "worker_child_result_guard")

    def test_audit_bucket_classification_flags_unmapped_codec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            known = audit.ManifestRow.from_record(
                manifest_row(root, bucket="h264-h265-direct"), library_root=library_root
            )
            unmapped_record = manifest_row(root, bucket="legacy-video", case_id="tdarr-0002")
            unmapped_record["video_codec"] = "prores"
            unmapped = audit.ManifestRow.from_record(unmapped_record, library_root=library_root)
            findings = audit.audit_bucket_classification([known, unmapped])
            self.assertEqual([finding.code for finding in findings], ["bucket_classification_fallback"])
            self.assertEqual(findings[0].severity, "warning")
            self.assertEqual(findings[0].case_id, "tdarr-0002")

    def test_prune_run_roots_keeps_newest_and_guards_non_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns"
            runs_root.mkdir(parents=True)
            run_dirs = []
            for index in range(3):
                run_dir = runs_root / f"run-{index:03d}"
                run_dir.mkdir()
                (run_dir / audit.AUDIT_RUN_SENTINEL).write_text("{}", encoding="utf-8")
                os.utime(run_dir, (1000 + index, 1000 + index))  # ascending mtime; run-002 newest
                run_dirs.append(run_dir)
            manual = runs_root / "manual"
            manual.mkdir()
            (manual / "keep.txt").write_text("x", encoding="utf-8")

            preview = audit.prune_run_roots(runs_root, keep_last=2, repo_root=root, dry_run=True)
            self.assertEqual([Path(path).name for path in preview["removed"]], ["run-000"])
            self.assertTrue(run_dirs[0].exists())  # dry-run deletes nothing

            result = audit.prune_run_roots(runs_root, keep_last=2, repo_root=root)
            self.assertEqual([Path(path).name for path in result["removed"]], ["run-000"])
            self.assertFalse(run_dirs[0].exists())
            self.assertTrue(run_dirs[1].exists())
            self.assertTrue(run_dirs[2].exists())
            self.assertTrue(manual.exists())  # non-sentinel directory is never touched

            with self.assertRaises(ValueError):
                audit.prune_run_roots(runs_root, keep_last=0, repo_root=root)

    def test_path_containment_scans_all_declared_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_root = root / "lib"
            outside = str(root / "outside" / "escaped.mkv")
            for index, parts in enumerate(audit.CONTAINMENT_SCAN_SUBDIRS):
                scan_root = library_root.joinpath(*parts)
                scan_root.mkdir(parents=True, exist_ok=True)
                (scan_root / f"evidence-{index}.json").write_text(json.dumps({"output_path": outside}), encoding="utf-8")
            findings = audit.audit_path_containment(library_root)
            self.assertEqual(
                [finding.code for finding in findings],
                ["path_escaped_test_root"] * len(audit.CONTAINMENT_SCAN_SUBDIRS),
            )
            scanned = {Path(finding.evidence["evidence_path"]).parent.resolve() for finding in findings}
            expected = {library_root.joinpath(*parts).resolve() for parts in audit.CONTAINMENT_SCAN_SUBDIRS}
            self.assertEqual(scanned, expected)


if __name__ == "__main__":
    unittest.main()
