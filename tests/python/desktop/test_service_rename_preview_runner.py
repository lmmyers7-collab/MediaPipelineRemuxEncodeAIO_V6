from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.preview_runner import (
    load_pipeline_movie_name_previews_for_service,
    load_pipeline_name_previews_for_service,
    load_pipeline_tv_name_previews_for_service,
    naming_preview_script_path_for_service,
)
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


class DummyRenamePreviewRunnerService:
    def __init__(self, root: Path) -> None:
        self.workspace_root = root
        self.app_root = root / "apps" / "desktop"
        self.logger = logging.getLogger("test_service_rename_preview_runner")
        self.logger.addHandler(logging.NullHandler())

    def _naming_preview_script_path(self) -> Path | None:
        return naming_preview_script_path_for_service(self)

    def _subprocess_kwargs_hidden(self) -> dict[str, int]:
        return {"creationflags": 1}


class RenamePreviewRunnerTests(unittest.TestCase):
    def test_naming_preview_script_path_uses_service_roots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "ops" / "pipeline" / "entrypoints" / "Get-NamingPreview.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("# test", encoding="utf-8")
            service = DummyRenamePreviewRunnerService(root)

            found = naming_preview_script_path_for_service(service)

        self.assertEqual(found, script)

    def test_load_pipeline_name_previews_for_service_passes_hidden_kwargs_and_media_kind(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "ops" / "pipeline" / "entrypoints" / "Get-NamingPreview.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("# test", encoding="utf-8")
            source = root / "Show E01.mkv"
            source.write_text("media", encoding="utf-8")
            service = DummyRenamePreviewRunnerService(root)

            def fake_run(args, **kwargs):
                self.assertEqual(kwargs["extra_popen_kwargs"], {"creationflags": 1})
                self.assertEqual(kwargs["label"], "pipeline tv naming preview")
                output_path = Path(args[args.index("-OutputJsonPath") + 1])
                output_path.write_text(
                    json.dumps({"rows": [{"ok": True, "source_path": str(source), "file_name": "Show - S01E01.mkv"}]}),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="", stderr="")

            previews, message = load_pipeline_name_previews_for_service(
                service,
                [source],
                media_kind="TV",
                powershell_host="pwsh",
                timeout_seconds=8,
                run_capture_func=fake_run,
            )

        self.assertEqual(message, "")
        self.assertEqual(previews[str(source).casefold()], "Show - S01E01.mkv")

    def test_movie_and_tv_wrappers_preserve_media_kind_labels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "ops" / "pipeline" / "entrypoints" / "Get-NamingPreview.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("# test", encoding="utf-8")
            media = root / "Item.mkv"
            media.write_text("media", encoding="utf-8")
            service = DummyRenamePreviewRunnerService(root)
            labels: list[str] = []

            def fake_run(args, **kwargs):
                labels.append(str(kwargs["label"]))
                output_path = Path(args[args.index("-OutputJsonPath") + 1])
                output_path.write_text(
                    json.dumps({"rows": [{"ok": True, "source_path": str(media), "file_name": "Clean.mkv"}]}),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="", stderr="")

            load_pipeline_movie_name_previews_for_service(
                service,
                [media],
                powershell_host="pwsh",
                timeout_seconds=8,
                run_capture_func=fake_run,
            )
            load_pipeline_tv_name_previews_for_service(
                service,
                [media],
                powershell_host="pwsh",
                timeout_seconds=8,
                run_capture_func=fake_run,
            )

        self.assertEqual(labels, ["pipeline movie naming preview", "pipeline tv naming preview"])


if __name__ == "__main__":
    unittest.main()
