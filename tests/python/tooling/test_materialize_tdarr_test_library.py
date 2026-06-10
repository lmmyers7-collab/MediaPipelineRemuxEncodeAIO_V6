from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev import materialize_tdarr_test_library as tdarr_matrix


TEMPLATE_TEXT = """@{
    SourceMovies = 'C:\\MediaPipeline\\Incoming\\Movies'
    SourceTV = 'C:\\MediaPipeline\\Incoming\\TV'
    Outsource = 'C:\\MediaPipeline\\Processed'
    LocalBase = 'C:\\MediaPipeline\\Scratch'
    FinalLibraryPromotionEnabled = $true
    FinalLibraryPromotionRules = @(@{ source = 'old' })
    FinalLibraryPromotionCleanupAfterVerified = $true
    FinalLibraryPromotionOverwriteExisting = $true
    OutputContainer = 'mp4'
    EncodeLadder = 'movie_archive'
    ValidExtensions = @('.mkv', '.mp4')
}
"""


def sample(
    *,
    name: str = "sample__1080__h264__aac__30s__video.mkv",
    local_path: str = "files/sample__1080__h264__aac__30s__video.mkv",
    medium: str = "video",
    container: str = "mkv",
    resolution: str = "1080p",
    video_codec: str = "h264",
    audio_codec: str = "aac",
    video_decodable: str = "",
) -> tdarr_matrix.TdarrSample:
    return tdarr_matrix.TdarrSample(
        name=name,
        local_path=local_path,
        source_url=f"https://samples.tdarr.io/api/v1/samples/{name}",
        source_page="https://home.tdarr.io/samples/",
        medium=medium,
        container=container,
        resolution=resolution,
        video_codec=video_codec,
        audio_codec=audio_codec,
        duration="30s",
        advertised_size_mb="1.0",
        actual_size_bytes="7",
        sha256="a" * 64,
        video_decodable=video_decodable,
    )


def write_inventory(path: Path, samples: list[tdarr_matrix.TdarrSample]) -> None:
    fieldnames = [
        "name",
        "local_path",
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
        "video_decodable",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in samples:
            writer.writerow({field: getattr(item, field) for field in fieldnames})


class TdarrMatrixMaterializerTests(unittest.TestCase):
    def test_bucket_assignment_and_paths_are_diagnostic(self) -> None:
        direct = sample()
        container = sample(
            name="sample__1080__h264__aac__30s__video.avi",
            local_path="files/sample__1080__h264__aac__30s__video.avi",
            container="avi",
        )
        audio = sample(
            name="sample__-__-__flac__30s__audio.mkv",
            local_path="files/sample__-__-__flac__30s__audio.mkv",
            medium="audio",
            resolution="-",
            video_codec="-",
            audio_codec="flac",
        )

        self.assertEqual(tdarr_matrix.diagnostic_bucket(direct), "h264-h265-direct")
        self.assertEqual(tdarr_matrix.diagnostic_bucket(container), "container-stress")
        self.assertEqual(tdarr_matrix.diagnostic_bucket(audio), "audio-only")
        # Remaining buckets + precedence + the silent catch-all (G6).
        self.assertEqual(tdarr_matrix.diagnostic_bucket(sample(video_codec="mjpeg")), "mjpeg-large")
        self.assertEqual(tdarr_matrix.diagnostic_bucket(sample(video_codec="vp9")), "av1-vp-modern")
        self.assertEqual(tdarr_matrix.diagnostic_bucket(sample(video_codec="libaom-av1")), "av1-vp-modern")
        self.assertEqual(tdarr_matrix.diagnostic_bucket(sample(video_codec="mpeg2video")), "legacy-video")
        self.assertEqual(tdarr_matrix.diagnostic_bucket(sample(video_codec="flv")), "legacy-video")
        # mjpeg classification beats container-stress.
        self.assertEqual(tdarr_matrix.diagnostic_bucket(sample(video_codec="mjpeg", container="avi")), "mjpeg-large")
        # Unknown codec in a non-stress container silently falls through to legacy-video.
        self.assertEqual(tdarr_matrix.diagnostic_bucket(sample(video_codec="prores", container="mkv")), "legacy-video")
        self.assertEqual(
            str(tdarr_matrix.movie_relative_path(1, direct)).replace("\\", "/"),
            "source/Movies/h264-h265-direct/Fake Title 0001 (2026) [Tdarr 1080p h264 aac mkv tdarr-0001].mkv",
        )
        self.assertIn(
            "source/TV/TDDirect/Season 01/TDDirect - S01E01 - Fake Episode",
            str(tdarr_matrix.tv_relative_path(1, direct)).replace("\\", "/"),
        )

    def test_classify_bucket_reports_fallback(self) -> None:
        # G6: classify_bucket returns (bucket, is_fallback); diagnostic_bucket is unchanged.
        self.assertEqual(tdarr_matrix.classify_bucket("video", "h264", "mkv"), ("h264-h265-direct", False))
        self.assertEqual(tdarr_matrix.classify_bucket("audio", "-", "mkv"), ("audio-only", False))
        self.assertEqual(tdarr_matrix.classify_bucket("video", "mjpeg", "avi"), ("mjpeg-large", False))
        self.assertEqual(tdarr_matrix.classify_bucket("video", "prores", "mkv"), ("legacy-video", True))

    def test_materialize_hardlinks_manifest_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_root = root / "LocalBase" / "TestFixtures" / "TdarrSamples"
            files_root = inventory_root / "files"
            files_root.mkdir(parents=True)
            first = files_root / "sample__1080__h264__aac__30s__video.mkv"
            second = files_root / "sample__720__mjpeg__flac__30s__video.wmv"
            first.write_bytes(b"movie-one")
            second.write_bytes(b"movie-two")
            inventory_path = inventory_root / "inventory.csv"
            write_inventory(
                inventory_path,
                [
                    sample(),
                    sample(
                        name=second.name,
                        local_path=f"files/{second.name}",
                        container="wmv",
                        resolution="720p",
                        video_codec="mjpeg",
                        audio_codec="flac",
                    ),
                ],
            )
            template_path = root / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
            template_path.parent.mkdir(parents=True)
            template_path.write_text(TEMPLATE_TEXT, encoding="utf-8")
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"

            summary = tdarr_matrix.materialize(
                inventory_path=inventory_path,
                library_root=library_root,
                repo_root=root,
                mode="hardlink",
                views=("movies", "tv"),
                rebuild=False,
                write_config_file=True,
                template_path=template_path,
            )

            self.assertEqual(summary["materialized_files"], 4)
            manifest_csv = Path(str(summary["manifest_csv"]))
            manifest_json = Path(str(summary["manifest_json"]))
            self.assertTrue(manifest_csv.exists())
            self.assertTrue(manifest_json.exists())
            with manifest_csv.open(newline="", encoding="utf-8") as handle:
                manifest_rows = list(csv.DictReader(handle))
            self.assertEqual(len(manifest_rows), 4)
            generated_first = library_root / manifest_rows[0]["generated_path"]
            self.assertTrue(generated_first.exists())
            self.assertTrue(os.path.samefile(first, generated_first))
            manifest_payload = json.loads(manifest_json.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload["count"], 4)
            self.assertEqual(manifest_payload["link_mode"], "hardlink")
            config_text = Path(str(summary["config_path"])).read_text(encoding="utf-8")
            self.assertIn("LibraryProfiles = @(", config_text)
            self.assertIn("designation = 'movie'", config_text)
            self.assertIn("designation = 'tv'", config_text)
            self.assertIn("OutputContainer = 'mkv'", config_text)
            self.assertIn("EncodeLadder = 'auto'", config_text)
            self.assertIn("'.wmv'", config_text)
            self.assertIn("'.mp2'", config_text)
            self.assertTrue((library_root / tdarr_matrix.SENTINEL_NAME).exists())

    def test_is_quarantined_sample_matches_only_false(self) -> None:
        self.assertTrue(tdarr_matrix.is_quarantined_sample(sample(video_decodable="false")))
        self.assertTrue(tdarr_matrix.is_quarantined_sample(sample(video_decodable="FALSE")))
        self.assertTrue(tdarr_matrix.is_quarantined_sample(sample(video_decodable=" false ")))
        self.assertFalse(tdarr_matrix.is_quarantined_sample(sample(video_decodable="true")))
        self.assertFalse(tdarr_matrix.is_quarantined_sample(sample(video_decodable="n/a")))
        self.assertFalse(tdarr_matrix.is_quarantined_sample(sample(video_decodable="unknown")))
        self.assertFalse(tdarr_matrix.is_quarantined_sample(sample(video_decodable="")))
        self.assertFalse(tdarr_matrix.is_quarantined_sample(sample()))

    def test_materialize_skips_quarantined_undecodable_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_root = root / "LocalBase" / "TestFixtures" / "TdarrSamples"
            files_root = inventory_root / "files"
            files_root.mkdir(parents=True)
            good = files_root / "sample__1080__h264__aac__30s__video.mkv"
            broken = files_root / "sample__2160__h265__alac__30s__video.mkv"
            good.write_bytes(b"good-one")
            broken.write_bytes(b"broken-one")
            inventory_path = inventory_root / "inventory.csv"
            write_inventory(
                inventory_path,
                [
                    sample(video_decodable="true"),
                    sample(
                        name=broken.name,
                        local_path=f"files/{broken.name}",
                        resolution="2160p",
                        video_codec="h265",
                        audio_codec="alac",
                        video_decodable="false",
                    ),
                ],
            )
            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"

            summary = tdarr_matrix.materialize(
                inventory_path=inventory_path,
                library_root=library_root,
                repo_root=root,
                mode="hardlink",
                views=("movies", "tv"),
                rebuild=False,
                write_config_file=False,
            )

            # Two inventory samples; the undecodable one is quarantined, so only
            # the good sample is materialized across both views (movies + tv) = 2.
            self.assertEqual(summary["samples"], 2)
            self.assertEqual(summary["quarantined_samples"], 1)
            self.assertEqual(summary["materialized_files"], 2)
            # The quarantined source is never linked into the generated library.
            materialized = [p.name for p in (library_root / "source").rglob("*") if p.is_file()]
            self.assertTrue(materialized)
            self.assertFalse(any("2160" in name for name in materialized))

    def test_rebuild_requires_sentinel_under_scratch_test_libraries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsafe = root / "LocalBase" / "Scratch" / "Wrong"
            with self.assertRaises(ValueError):
                tdarr_matrix.prepare_library_root(unsafe, repo_root=root, rebuild=False)

            library_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
            library_root.mkdir(parents=True)
            (library_root / "manual.txt").write_text("not generated", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                tdarr_matrix.prepare_library_root(library_root, repo_root=root, rebuild=True)


if __name__ == "__main__":
    unittest.main()
