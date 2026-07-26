from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.preview import (
    build_naming_preview_request,
    build_synthetic_naming_preview_request,
    find_naming_preview_script,
    load_pipeline_name_previews,
    load_synthetic_pipeline_name_preview,
    parse_naming_preview_rows,
    parse_synthetic_naming_preview_result,
)
from mediapipeline.core.rename.cleaning_policy import rename_cleaning_policy_from_config
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


class RenamePreviewHelperTests(unittest.TestCase):
    def _logger(self) -> logging.Logger:
        logger = logging.getLogger("test_rename_preview")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    def test_find_naming_preview_script_prefers_workspace_pipeline_and_deduplicates_roots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "ops" / "pipeline" / "entrypoints" / "Get-NamingPreview.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("# test", encoding="utf-8")

            found = find_naming_preview_script(root, root)

        self.assertEqual(found, script)

    def test_build_naming_preview_request_shapes_items(self) -> None:
        path = Path(r"C:\Media\Movie.Name.mkv")

        payload = build_naming_preview_request([path], media_kind="Movie")

        self.assertEqual(payload["schema_version"], "naming_preview_request.v2")
        self.assertEqual(payload["items"][0]["path"], str(path))
        self.assertEqual(payload["items"][0]["original_name"], "Movie.Name.mkv")
        self.assertEqual(payload["items"][0]["extension"], ".mkv")
        self.assertEqual(payload["items"][0]["media_kind"], "Movie")

    def test_build_naming_preview_request_carries_normalized_policy_contract(self) -> None:
        policy = rename_cleaning_policy_from_config(
            {
                "RenameMovieFilterTerms": {"release_groups": ["SupaCvnt"]},
                "RenameTVFilterTerms": {"release_groups": ["TTGA"]},
            }
        )

        payload = build_naming_preview_request(
            [Path(r"C:\Media\Movie.Name.mkv")],
            media_kind="Movie",
            cleaning_policy=policy,
        )

        self.assertEqual(payload["schema_version"], "naming_preview_request.v2")
        self.assertEqual(payload["rename_cleaning_policy"], policy)
        self.assertEqual(payload["rename_cleaning_policy"]["schema_version"], "rename_cleaning_policy.v1")

    def test_build_synthetic_naming_preview_request_preserves_typed_folder_context_without_a_media_probe(self) -> None:
        policy = rename_cleaning_policy_from_config({})

        payload = build_synthetic_naming_preview_request(
            filename="Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
            source_folder="Movies",
            media_kind="Movie",
            cleaning_policy=policy,
        )

        self.assertEqual(payload["schema_version"], "naming_preview_request.v2")
        self.assertEqual(payload["rename_cleaning_policy"], policy)
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertTrue(item["synthetic"])
        self.assertEqual(item["source_folder"], "Movies")
        self.assertEqual(
            item["original_name"],
            "Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv",
        )
        self.assertEqual(
            item["input_name"],
            "Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
        )
        self.assertEqual(item["extension"], ".mkv")
        self.assertTrue(item["assumed_media_extension"])
        self.assertEqual(item["media_kind"], "Movie")

    def test_parse_synthetic_naming_preview_result_requires_matching_policy_and_synthetic_evidence(self) -> None:
        fingerprint = "a" * 64
        response = {
            "schema_version": "naming_preview.v2",
            "applied_policy_fingerprint": fingerprint,
            "rows": [
                {
                    "ok": True,
                    "synthetic": True,
                    "source_path": r"Movies\Edge.of.Tomorrow.2014.mkv",
                    "media_kind": "Movie",
                    "file_base_name": "Edge of Tomorrow (2014)",
                    "file_name": "Edge of Tomorrow (2014).mkv",
                    "parsed_identity": {"media_kind": "Movie", "title": "Edge of Tomorrow", "year": 2014},
                }
            ],
        }

        parsed = parse_synthetic_naming_preview_result(
            response,
            media_kind="Movie",
            expected_policy_fingerprint=fingerprint,
            expected_source_path=r"Movies\Edge.of.Tomorrow.2014.mkv",
        )
        mismatched = parse_synthetic_naming_preview_result(
            {**response, "applied_policy_fingerprint": "b" * 64},
            media_kind="Movie",
            expected_policy_fingerprint=fingerprint,
            expected_source_path=r"Movies\Edge.of.Tomorrow.2014.mkv",
        )
        non_synthetic = parse_synthetic_naming_preview_result(
            {**response, "rows": [{**response["rows"][0], "synthetic": False}]},
            media_kind="Movie",
            expected_policy_fingerprint=fingerprint,
            expected_source_path=r"Movies\Edge.of.Tomorrow.2014.mkv",
        )
        wrong_row = parse_synthetic_naming_preview_result(
            {
                **response,
                "rows": [
                    {
                        **response["rows"][0],
                        "source_path": r"Movies\Wrong.Release.2014.mkv",
                    }
                ],
            },
            media_kind="Movie",
            expected_policy_fingerprint=fingerprint,
            expected_source_path=r"Movies\Edge.of.Tomorrow.2014.mkv",
        )

        self.assertTrue(parsed["ok"], parsed)
        self.assertTrue(parsed["policy_fingerprint_match"])
        self.assertEqual(parsed["row"]["file_name"], "Edge of Tomorrow (2014).mkv")
        self.assertFalse(mismatched["ok"])
        self.assertFalse(mismatched["policy_fingerprint_match"])
        self.assertIn("policy fingerprint mismatch", mismatched["error"])
        self.assertFalse(non_synthetic["ok"])
        self.assertIn("synthetic evidence", non_synthetic["error"])
        self.assertFalse(wrong_row["ok"])
        self.assertIn("requested synthetic input", wrong_row["error"])

    def test_parse_naming_preview_rows_accepts_v1_and_v2_and_rejects_unknown_versions(self) -> None:
        for version in ("naming_preview.v1", "naming_preview.v2"):
            with self.subTest(version=version):
                previews, message = parse_naming_preview_rows(
                    {
                        "schema_version": version,
                        "applied_policy_fingerprint": "a" * 64,
                        "rows": [
                            {
                                "ok": True,
                                "source_path": r"C:\Media\Movie.mkv",
                                "file_name": "Movie (2020).mkv",
                                "parsed_identity": {"media_kind": "Movie", "movie_title": "Movie (2020)"},
                            }
                        ],
                    },
                    media_kind="Movie",
                    logger=self._logger(),
                )
                self.assertEqual(message, "")
                self.assertEqual(previews[r"c:\media\movie.mkv"], "Movie (2020).mkv")

        previews, message = parse_naming_preview_rows(
            {"schema_version": "naming_preview.v3", "rows": []},
            media_kind="Movie",
            logger=self._logger(),
        )
        self.assertEqual(previews, {})
        self.assertIn("unsupported schema", message)

    def test_parse_naming_preview_rows_rejects_a_mismatched_v2_policy_fingerprint(self) -> None:
        previews, message = parse_naming_preview_rows(
            {
                "schema_version": "naming_preview.v2",
                "applied_policy_fingerprint": "b" * 64,
                "rows": [
                    {"ok": True, "source_path": r"C:\Media\Movie.mkv", "file_name": "Wrong.mkv"}
                ],
            },
            media_kind="Movie",
            logger=self._logger(),
            expected_policy_fingerprint="a" * 64,
        )

        self.assertEqual(previews, {})
        self.assertIn("policy fingerprint mismatch", message)

    def test_parse_naming_preview_rows_skips_failures_and_maps_casefolded_paths(self) -> None:
        previews, message = parse_naming_preview_rows(
            {
                "rows": [
                    {"ok": False, "source_path": "bad.mkv", "error": "blocked"},
                    {"ok": True, "source_path": r"C:\Media\Movie.mkv", "file_name": "Movie (2020).mkv"},
                    "bad row",
                ]
            },
            media_kind="Movie",
            logger=self._logger(),
        )

        self.assertEqual(message, "")
        self.assertEqual(previews[r"c:\media\movie.mkv"], "Movie (2020).mkv")

    def test_load_pipeline_name_previews_runs_script_and_reads_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "Get-NamingPreview.ps1"
            script.write_text("# test", encoding="utf-8")
            source = root / "Movie.mkv"
            source.write_text("media", encoding="utf-8")

            def fake_run(args, **kwargs):
                self.assertEqual(kwargs["cwd"], str(script.parent))
                self.assertEqual(kwargs["label"], "pipeline movie naming preview")
                output_path = Path(args[args.index("-OutputJsonPath") + 1])
                output_path.write_text(
                    json.dumps({"rows": [{"ok": True, "source_path": str(source), "file_name": "Clean.mkv"}]}),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="", stderr="")

            previews, message = load_pipeline_name_previews(
                [source],
                media_kind="Movie",
                powershell_host="pwsh",
                script_path=script,
                timeout_seconds=8,
                hidden_kwargs={"creationflags": 1},
                logger=self._logger(),
                run_capture_func=fake_run,
            )

        self.assertEqual(message, "")
        self.assertEqual(previews[str(source).casefold()], "Clean.mkv")

    def test_load_pipeline_name_previews_reports_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "Get-NamingPreview.ps1"
            script.write_text("# test", encoding="utf-8")

            def fake_run(args, **_kwargs):
                return CapturedCommandResult(
                    args=args,
                    returncode=-9,
                    stdout="",
                    stderr="",
                    timed_out=True,
                    kill_message="killed process tree",
                )

            previews, message = load_pipeline_name_previews(
                [Path(td) / "Movie.mkv"],
                media_kind="Movie",
                powershell_host="pwsh",
                script_path=script,
                timeout_seconds=8,
                hidden_kwargs={},
                logger=self._logger(),
                run_capture_func=fake_run,
            )

        self.assertEqual(previews, {})
        self.assertIn("killed process tree", message)

    def test_load_synthetic_pipeline_name_preview_runs_the_production_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "Get-NamingPreview.ps1"
            script.write_text("# test", encoding="utf-8")
            policy = rename_cleaning_policy_from_config({})

            def fake_run(args, **kwargs):
                self.assertEqual(kwargs["label"], "pipeline movie synthetic naming preview")
                input_path = Path(args[args.index("-InputJsonPath") + 1])
                output_path = Path(args[args.index("-OutputJsonPath") + 1])
                request = json.loads(input_path.read_text(encoding="utf-8"))
                self.assertTrue(request["items"][0]["synthetic"])
                output_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "naming_preview.v2",
                            "applied_policy_fingerprint": policy["policy_fingerprint"],
                            "rows": [
                                {
                                    "ok": True,
                                    "synthetic": True,
                                    "source_path": request["items"][0]["path"],
                                    "media_kind": "Movie",
                                    "file_base_name": "Edge of Tomorrow (2014)",
                                    "file_name": "Edge of Tomorrow (2014)",
                                    "parsed_identity": {
                                        "media_kind": "Movie",
                                        "title": "Edge of Tomorrow",
                                        "year": 2014,
                                    },
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="", stderr="")

            result = load_synthetic_pipeline_name_preview(
                filename="Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
                source_folder="Movies",
                media_kind="Movie",
                powershell_host="pwsh",
                script_path=script,
                timeout_seconds=8,
                hidden_kwargs={},
                logger=self._logger(),
                run_capture_func=fake_run,
                cleaning_policy=policy,
            )

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["policy_fingerprint_match"])
        self.assertEqual(result["row"]["file_name"], "Edge of Tomorrow (2014)")


if __name__ == "__main__":
    unittest.main()
