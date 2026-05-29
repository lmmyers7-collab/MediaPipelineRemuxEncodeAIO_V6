from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rename.preview import (
    build_naming_preview_request,
    find_naming_preview_script,
    load_pipeline_name_previews,
    parse_naming_preview_rows,
)
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


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
            script = root / "Pipeline" / "Get-NamingPreview.ps1"
            script.parent.mkdir()
            script.write_text("# test", encoding="utf-8")

            found = find_naming_preview_script(root, root)

        self.assertEqual(found, script)

    def test_build_naming_preview_request_shapes_items(self) -> None:
        path = Path(r"C:\Media\Movie.Name.mkv")

        payload = build_naming_preview_request([path], media_kind="Movie")

        self.assertEqual(payload["schema_version"], "naming_preview_request.v1")
        self.assertEqual(payload["items"][0]["path"], str(path))
        self.assertEqual(payload["items"][0]["original_name"], "Movie.Name.mkv")
        self.assertEqual(payload["items"][0]["extension"], ".mkv")
        self.assertEqual(payload["items"][0]["media_kind"], "Movie")

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


if __name__ == "__main__":
    unittest.main()
