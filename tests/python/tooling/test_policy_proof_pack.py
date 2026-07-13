from __future__ import annotations

import hashlib
import json
import csv
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from mediapipeline.tools.dev import policy_proof_pack


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_catalog(root: Path, *, expected_hash: str) -> Path:
    catalog = {
        "schema_version": policy_proof_pack.CATALOG_SCHEMA,
        "fixtures": [
            {
                "id": "subtitle-ass-ssa",
                "source_key": "subtitle-ass-ssa",
                "sha256": expected_hash,
                "source_facts": {
                    "stream_counts": {"video": 1, "audio": 1, "subtitle": 1},
                    "subtitle_codecs": ["ass"],
                },
                "scenario": "subtitle_ass_preserve",
                "expectations": {"output": {"subtitle_codecs": ["ass"]}},
                "manual_playback": True,
            }
        ],
    }
    path = root / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return path


def write_mapping(root: Path, *, relative_path: str = "owned/ass-sample.mkv") -> Path:
    path = root / policy_proof_pack.SOURCE_MAPPING_NAME
    path.write_text(
        json.dumps(
            {
                "schema_version": policy_proof_pack.SOURCE_MAPPING_SCHEMA,
                "sources": {"subtitle-ass-ssa": relative_path},
            }
        ),
        encoding="utf-8",
    )
    return path


class PolicyProofPackTests(unittest.TestCase):
    def test_checked_in_catalog_declares_every_required_policy_scenario(self) -> None:
        catalog_path = policy_proof_pack.DEFAULT_CATALOG
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        fixture_ids = {fixture["id"] for fixture in payload["fixtures"]}

        self.assertEqual(payload["schema_version"], policy_proof_pack.CATALOG_SCHEMA)
        self.assertTrue(
            {
                "subtitle-ass-ssa",
                "subtitle-tx3g",
                "subtitle-bdpgs",
                "audio-multilang-commentary",
                "topology-chapters-attachments",
                "timing-interlaced-vfr",
                "sdr-2160p-10bit",
                "hdr10-pq",
                "hlg",
                "dovi-p81",
                "hdr10plus",
                "dovi-p5",
                "dovi-p7",
                "deferred-publish-sidecar",
                "resilience-interrupt-rerun",
            }.issubset(fixture_ids)
        )

    def test_cli_defaults_to_the_bundled_ffprobe(self) -> None:
        args = policy_proof_pack.parse_args(["verify"])

        self.assertEqual(
            Path(args.ffprobe),
            policy_proof_pack.REPO_ROOT / "ops" / "pipeline" / "tools" / "ffmpeg" / "bin" / "ffprobe.exe",
        )

    def test_ffprobe_facts_capture_dynamic_hdr_and_stream_policy_axes(self) -> None:
        facts = policy_proof_pack.facts_from_ffprobe_payload(
            {
                "chapters": [{"id": 0}],
                "streams": [
                    {
                        "codec_type": "video",
                        "height": 2160,
                        "bits_per_raw_sample": "10",
                        "field_order": "tt",
                        "r_frame_rate": "24000/1001",
                        "avg_frame_rate": "30000/1001",
                        "side_data_list": [{"side_data_type": "DOVI configuration record", "dv_profile": 8, "dv_bl_signal_compatibility_id": 1}],
                    },
                    {"codec_type": "audio", "channels": 6, "tags": {"language": "eng"}},
                    {"codec_type": "subtitle", "codec_name": "ass"},
                    {"codec_type": "attachment"},
                ],
            }
        )

        self.assertEqual(facts["dovi_profile"], "8.1")
        self.assertEqual(facts["resolution"], "2160p")
        self.assertEqual(facts["bit_depth"], 10)
        self.assertTrue(facts["interlaced_or_vfr"])
        self.assertEqual(facts["max_audio_channels"], 6)
        self.assertEqual(facts["stream_counts"], {"attachment": 1, "audio": 1, "subtitle": 1, "video": 1})

    def test_ffprobe_facts_capture_hdr10plus_from_frame_side_data(self) -> None:
        facts = policy_proof_pack.facts_from_ffprobe_payload(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "height": 2160,
                        "color_transfer": "smpte2084",
                    }
                ],
                "frames": [
                    {
                        "side_data_list": [
                            {"side_data_type": "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)"}
                        ]
                    }
                ],
            }
        )

        self.assertEqual(facts["hdr"], "hdr10plus")

    def test_ffprobe_facts_do_not_treat_other_dynamic_metadata_as_hdr10plus(self) -> None:
        facts = policy_proof_pack.facts_from_ffprobe_payload(
            {
                "streams": [{"codec_type": "video", "color_transfer": "smpte2084"}],
                "frames": [
                    {
                        "side_data_list": [
                            {"side_data_type": "HDR Dynamic Metadata SMPTE2094-10"}
                        ]
                    }
                ],
            }
        )

        self.assertEqual(facts["hdr"], "hdr10")

    def test_ffprobe_facts_require_pq_base_transfer_for_hdr10plus(self) -> None:
        for color_transfer, expected_hdr in (("", ""), ("arib-std-b67", "hlg")):
            with self.subTest(color_transfer=color_transfer):
                facts = policy_proof_pack.facts_from_ffprobe_payload(
                    {
                        "streams": [{"codec_type": "video", "color_transfer": color_transfer}],
                        "frames": [
                            {
                                "side_data_list": [
                                    {"side_data_type": "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)"}
                                ]
                            }
                        ],
                    }
                )

                self.assertEqual(facts["hdr"], expected_hdr)

    def test_ffprobe_facts_associate_hdr10plus_with_zero_index_pq_stream(self) -> None:
        facts = policy_proof_pack.facts_from_ffprobe_payload(
            {
                "streams": [
                    {"index": 0, "codec_type": "video", "color_transfer": "smpte2084"},
                    {"index": 1, "codec_type": "video", "color_transfer": "arib-std-b67"},
                ],
                "frames": [
                    {
                        "stream_index": 0,
                        "side_data_list": [
                            {"side_data_type": "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)"}
                        ],
                    }
                ],
            }
        )

        self.assertEqual(facts["hdr"], "hdr10plus")

    def test_ffprobe_facts_infer_ten_bit_depth_from_pixel_format(self) -> None:
        facts = policy_proof_pack.facts_from_ffprobe_payload(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "height": 2160,
                        "pix_fmt": "yuv420p10le",
                        "bits_per_raw_sample": "",
                    }
                ]
            }
        )

        self.assertEqual(facts["bit_depth"], 10)

    def test_ffprobe_facts_keep_explicit_bit_depth_over_pixel_format(self) -> None:
        facts = policy_proof_pack.facts_from_ffprobe_payload(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "pix_fmt": "yuv420p10le",
                        "bits_per_raw_sample": "12",
                    }
                ]
            }
        )

        self.assertEqual(facts["bit_depth"], 12)

    def test_ffprobe_facts_compare_valid_frame_rate_rationals(self) -> None:
        cases = (
            ("24/1", "24000/1000", False),
            ("24/1", "0/0", False),
            ("24/1", "30000/1001", True),
        )
        for real_rate, average_rate, expected in cases:
            with self.subTest(real_rate=real_rate, average_rate=average_rate):
                facts = policy_proof_pack.facts_from_ffprobe_payload(
                    {
                        "streams": [
                            {
                                "codec_type": "video",
                                "field_order": "progressive",
                                "r_frame_rate": real_rate,
                                "avg_frame_rate": average_rate,
                            }
                        ]
                    }
                )

                self.assertEqual(facts["interlaced_or_vfr"], expected)

    @patch("mediapipeline.tools.dev.policy_proof_pack.subprocess.run")
    def test_probe_source_requests_bounded_frame_metadata(self, run_mock) -> None:
        run_mock.side_effect = [
            CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_type": "video",
                                "height": 4000,
                                "disposition": {"attached_pic": 1},
                            },
                            {"codec_type": "video", "height": 1080, "color_transfer": "smpte2084"},
                            {"codec_type": "audio", "channels": 6},
                        ],
                        "chapters": [{"id": 0}],
                    }
                ),
                stderr="",
            ),
            CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        "frames": [
                            {
                                "side_data_list": [
                                    {"side_data_type": "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)"}
                                ]
                            }
                        ]
                    }
                ),
                stderr="",
            ),
        ]

        facts = policy_proof_pack.probe_source_ffprobe(Path("sample.mkv"), ffprobe="ffprobe-test")

        self.assertEqual(run_mock.call_count, 2)
        inventory_command = run_mock.call_args_list[0].args[0]
        frame_command = run_mock.call_args_list[1].args[0]
        self.assertIn("-show_streams", inventory_command)
        self.assertIn("-show_frames", frame_command)
        self.assertEqual(frame_command[frame_command.index("-select_streams") + 1], "V")
        self.assertEqual(frame_command[frame_command.index("-read_intervals") + 1], "%+#120")
        self.assertEqual(facts["stream_counts"], {"audio": 1, "video": 2})
        self.assertTrue(facts["chapters"])
        self.assertEqual(facts["hdr"], "hdr10plus")
        self.assertEqual(facts["resolution"], "1080p")

    @patch("mediapipeline.tools.dev.policy_proof_pack.subprocess.run")
    def test_probe_source_skips_frame_metadata_for_non_pq_video(self, run_mock) -> None:
        run_mock.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"streams": [{"codec_type": "video", "color_transfer": "arib-std-b67"}]}
            ),
            stderr="",
        )

        facts = policy_proof_pack.probe_source_ffprobe(Path("sample.mkv"), ffprobe="ffprobe-test")

        self.assertEqual(run_mock.call_count, 1)
        self.assertEqual(facts["hdr"], "hlg")

    @patch("mediapipeline.tools.dev.policy_proof_pack.subprocess.run")
    def test_probe_source_fails_closed_when_frame_metadata_probe_fails(self, run_mock) -> None:
        run_mock.side_effect = [
            CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {"streams": [{"codec_type": "video", "color_transfer": "smpte2084"}]}
                ),
                stderr="",
            ),
            CompletedProcess(args=[], returncode=1, stdout="", stderr="frame decode failed"),
        ]

        with self.assertRaisesRegex(RuntimeError, "frame metadata probe failed"):
            policy_proof_pack.probe_source_ffprobe(Path("sample.mkv"), ffprobe="ffprobe-test")

    @patch("mediapipeline.tools.dev.policy_proof_pack.subprocess.run")
    def test_probe_source_fails_closed_when_frame_metadata_has_no_frames(self, run_mock) -> None:
        run_mock.side_effect = [
            CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {"streams": [{"codec_type": "video", "color_transfer": "smpte2084"}]}
                ),
                stderr="",
            ),
            CompletedProcess(args=[], returncode=0, stdout=json.dumps({"frames": []}), stderr=""),
        ]

        with self.assertRaisesRegex(RuntimeError, "frame metadata probe returned no video frames"):
            policy_proof_pack.probe_source_ffprobe(Path("sample.mkv"), ffprobe="ffprobe-test")

    @patch("mediapipeline.tools.dev.policy_proof_pack.subprocess.run")
    def test_probe_source_fails_closed_when_frame_metadata_shape_is_invalid(self, run_mock) -> None:
        run_mock.side_effect = [
            CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {"streams": [{"codec_type": "video", "color_transfer": "smpte2084"}]}
                ),
                stderr="",
            ),
            CompletedProcess(args=[], returncode=0, stdout=json.dumps({"frames": None}), stderr=""),
        ]

        with self.assertRaisesRegex(RuntimeError, "frame metadata probe returned invalid frames"):
            policy_proof_pack.probe_source_ffprobe(Path("sample.mkv"), ffprobe="ffprobe-test")

    def test_materialize_copies_owned_fixture_and_writes_sentinel_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "PolicyProofPack"
            source = root / "owned" / "ass-sample.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"owned-fixture")
            catalog_path = write_catalog(root, expected_hash=source_hash(source))
            write_mapping(root)

            summary = policy_proof_pack.materialize_policy_proof_pack(
                fixture_root=root,
                catalog_path=catalog_path,
                run_id="unit-materialize",
                allowed_root=root,
            )

            run_root = root / "runs" / "unit-materialize"
            self.assertTrue(summary["ok"])
            self.assertTrue((run_root / policy_proof_pack.RUN_SENTINEL).exists())
            self.assertTrue((run_root / "manifests" / "materialized_library.csv").exists())
            self.assertEqual((run_root / "source" / "Movies" / "subtitle-ass-ssa.mkv").read_bytes(), source.read_bytes())
            self.assertNotEqual((run_root / "source" / "Movies" / "subtitle-ass-ssa.mkv").resolve(), source.resolve())
            with (run_root / "manifests" / "materialized_library.csv").open(encoding="utf-8", newline="") as handle:
                manifest_row = next(csv.DictReader(handle))
            self.assertTrue(Path(manifest_row["source_path"]).resolve().is_relative_to(run_root.resolve()))

    def test_verify_rejects_hash_mismatch_and_source_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "PolicyProofPack"
            source = root / "owned" / "ass-sample.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"owned-fixture")
            catalog_path = write_catalog(root, expected_hash="0" * 64)
            write_mapping(root)

            result = policy_proof_pack.verify_policy_proof_pack(
                fixture_root=root,
                catalog_path=catalog_path,
                allowed_root=root,
                probe_source=lambda _path: {"stream_counts": {"video": 1, "audio": 1, "subtitle": 1}, "subtitle_codecs": ["ass"]},
            )
            self.assertFalse(result["ok"])
            self.assertIn("source_hash_mismatch", [item["code"] for item in result["findings"]])

            write_mapping(root, relative_path="../outside.mkv")
            with self.assertRaisesRegex(ValueError, "fixture-root-relative"):
                policy_proof_pack.load_source_mapping(root, allowed_root=root)

    def test_verify_marks_disabled_condition_not_applicable_and_strict_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "PolicyProofPack"
            source = root / "owned" / "ass-sample.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"owned-fixture")
            catalog_path = write_catalog(root, expected_hash=source_hash(source))
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["fixtures"][0]["applicability"] = {"config": {"ConvertTx3gToSrt": True}}
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            write_mapping(root)

            result = policy_proof_pack.verify_policy_proof_pack(
                fixture_root=root,
                catalog_path=catalog_path,
                allowed_root=root,
                effective_config={"ConvertTx3gToSrt": False},
                probe_source=lambda _path: {"stream_counts": {"video": 1, "audio": 1, "subtitle": 1}, "subtitle_codecs": ["ass"]},
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["fixtures"][0]["status"], "not_applicable")

            result["findings"].append({"severity": "error", "code": "output_stream_mismatch", "message": "wrong output"})
            self.assertEqual(policy_proof_pack.exit_code_for_policy_result(result, strict=True), 1)

    def test_output_assertions_cover_streams_sidecars_and_publish_state(self) -> None:
        fixture = {
            "id": "publish",
            "expectations": {
                "output": {"stream_counts": {"video": 1}, "subtitle_codecs": ["subrip"], "sidecar_kinds": ["tx3g_srt"]},
                "publish": {"terminal_state": "drained", "sidecars": True},
            },
        }

        findings = policy_proof_pack.assert_output_expectations(
            fixture,
            output_facts={"stream_counts": {"video": 1}, "subtitle_codecs": ["subrip"]},
            worker_result={"PublishState": "drained", "SidecarKinds": ["tx3g_srt"]},
        )
        self.assertEqual(findings, [])

        findings = policy_proof_pack.assert_output_expectations(
            fixture,
            output_facts={"stream_counts": {"video": 2}, "subtitle_codecs": []},
            worker_result={"PublishState": "parked", "SidecarKinds": []},
        )
        self.assertEqual({item["code"] for item in findings}, {"output_fact_mismatch", "output_sidecar_mismatch", "publish_state_mismatch", "publish_sidecar_mismatch"})

    def test_run_writes_policy_report_from_backend_owned_fixture_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "PolicyProofPack"
            source = root / "owned" / "ass-sample.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"owned-fixture")
            catalog_path = write_catalog(root, expected_hash=source_hash(source))
            write_mapping(root)

            result = policy_proof_pack.run_policy_proof_pack(
                fixture_root=root,
                catalog_path=catalog_path,
                run_id="unit-run",
                allowed_root=root,
                process_fixture=lambda fixture, _run_root: {
                    "output_facts": {"subtitle_codecs": ["ass"]},
                    "worker_result": {},
                },
            )

            self.assertTrue(result["ok"])
            self.assertTrue((root / "runs" / "unit-run" / "manifests" / policy_proof_pack.REPORT_NAME).exists())
            self.assertEqual(result["fixtures"][0]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
