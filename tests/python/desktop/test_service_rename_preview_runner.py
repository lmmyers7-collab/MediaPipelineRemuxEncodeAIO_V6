from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.preview_runner import (
    load_pipeline_movie_name_previews_for_service,
    load_pipeline_name_previews_for_service,
    load_synthetic_pipeline_name_preview_for_service,
    load_pipeline_tv_name_previews_for_service,
    naming_preview_script_path_for_service,
)
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult, run_capture
from mediapipeline.core.rename.bad_case_corpus import (
    DEFAULT_RENAME_BAD_CASE_FIXTURE,
    load_bad_rename_cases,
)
from mediapipeline.core.rename.cleaning_policy import rename_cleaning_policy_from_config
from mediapipeline.core.rename.movie import clean_pipeline_movie_name


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
            policy = rename_cleaning_policy_from_config(
                {"RenameTVFilterTerms": {"release_groups": ["TTGA"]}}
            )

            def fake_run(args, **kwargs):
                self.assertEqual(kwargs["extra_popen_kwargs"], {"creationflags": 1})
                self.assertEqual(kwargs["label"], "pipeline tv naming preview")
                output_path = Path(args[args.index("-OutputJsonPath") + 1])
                input_path = Path(args[args.index("-InputJsonPath") + 1])
                request = json.loads(input_path.read_text(encoding="utf-8"))
                self.assertEqual(request["schema_version"], "naming_preview_request.v2")
                self.assertEqual(request["rename_cleaning_policy"], policy)
                output_path.write_text(
                    json.dumps({"schema_version": "naming_preview.v2", "applied_policy_fingerprint": policy["policy_fingerprint"], "rows": [{"ok": True, "source_path": str(source), "file_name": "Show - S01E01.mkv"}]}),
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
                cleaning_policy=policy,
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

    def test_real_powershell_preview_applies_the_same_tv_policy_contract(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        powershell_host = repo_root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
        if not powershell_host.exists():
            self.skipTest("bundled PowerShell host is unavailable")
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Example.Show.S02E04 - MoonSource.mkv"
            source.write_bytes(b"preview")
            service = DummyRenamePreviewRunnerService(repo_root)
            service._subprocess_kwargs_hidden = lambda: {}  # type: ignore[method-assign]
            policy = rename_cleaning_policy_from_config(
                {"RenameTVFilterTerms": {"video_source": ["MoonSource"]}}
            )

            previews, message = load_pipeline_tv_name_previews_for_service(
                service,
                [source],
                powershell_host=str(powershell_host),
                timeout_seconds=60,
                run_capture_func=run_capture,
                cleaning_policy=policy,
            )

        self.assertEqual(message, "")
        self.assertEqual(previews[str(source).casefold()], "Example Show - S02E04.mkv")

    def test_real_powershell_synthetic_preview_preserves_extensionless_release_tail(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        powershell_host = repo_root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
        if not powershell_host.exists():
            self.skipTest("bundled PowerShell host is unavailable")
        service = DummyRenamePreviewRunnerService(repo_root)
        service._subprocess_kwargs_hidden = lambda: {}  # type: ignore[method-assign]
        policy = rename_cleaning_policy_from_config({})

        result = load_synthetic_pipeline_name_preview_for_service(
            service,
            filename="Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
            source_folder="Movies",
            media_kind="Movie",
            powershell_host=str(powershell_host),
            timeout_seconds=60,
            run_capture_func=run_capture,
            cleaning_policy=policy,
        )

        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["requested_policy_fingerprint"], policy["policy_fingerprint"])
        self.assertEqual(result["applied_policy_fingerprint"], policy["policy_fingerprint"])
        self.assertTrue(result["policy_fingerprint_match"])
        self.assertEqual(result["row"]["file_base_name"], "Edge of Tomorrow (2014)")
        self.assertEqual(result["row"]["file_name"], "Edge of Tomorrow (2014).mkv")
        self.assertTrue(result["row"]["assumed_media_extension"])

    def test_real_powershell_movie_preview_matches_python_for_numeric_titles_and_metadata_tails(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        powershell_host = repo_root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
        if not powershell_host.exists():
            self.skipTest("bundled PowerShell host is unavailable")
        cases = {
            "2001 A Space Odyssey 1968.mkv": "2001 A Space Odyssey (1968).mkv",
            "Blade Runner 2049 2017.mkv": "Blade Runner 2049 (2017).mkv",
            "1917 2019.mkv": "1917 (2019).mkv",
            "1984 1984.mkv": "1984 (1984).mkv",
            "12 Angry Men 1957.mkv": "12 Angry Men (1957).mkv",
            "10 Cloverfield Lane 2016.mkv": "10 Cloverfield Lane (2016).mkv",
            "DC League of Super-Pets 2022.mkv": "DC League of Super-Pets (2022).mkv",
            "Ma 2019.mkv": "Ma (2019).mkv",
            "Cam 2018.mkv": "Cam (2018).mkv",
            "The Web 2013.mkv": "The Web (2013).mkv",
            "The DVD 2024.mkv": "The Dvd (2024).mkv",
            "Movie UpScaled 2024.mkv": "Movie UpScaled (2024).mkv",
            "4K Killer 2024.mkv": "4K Killer (2024).mkv",
            "Atmos Fear 2024.mkv": "Atmos Fear (2024).mkv",
            "AVC 2024.mkv": "AVC (2024).mkv",
            "The Remux 2024.mkv": "The Remux (2024).mkv",
            "Audio Drama 2024.mkv": "Audio Drama (2024).mkv",
            "A Proper Man (2024).mkv": "A Proper Man (2024).mkv",
            "Movie.PROPER.2024.mkv": "Movie (2024).mkv",
            "Movie.REPACK.2024.mkv": "Movie (2024).mkv",
            "Movie.RERIP.2024.mkv": "Movie (2024).mkv",
            "Cast Away (2000) UpScaled 2160p H265 10 bit DV HDR10+ ita eng AC3 5.1 sub ita eng Licdom.mkv": "Cast Away (2000).mkv",
            "Movie.2024.Asiimov.mkv": "Movie (2024).mkv",
            "Roundhay Garden Scene 1888.mkv": "Roundhay Garden Scene (1888).mkv",
            f"Far Future {date.today().year + 2}.mkv": f"Far Future {date.today().year + 2}.mkv",
            f"{date.today().year}.mkv": f"{date.today().year}.mkv",
            "Movie (2020) 2021.mkv": "Movie 2021 (2020).mkv",
        }
        with tempfile.TemporaryDirectory() as td:
            sources = []
            for source_name in cases:
                source = Path(td) / source_name
                source.write_bytes(b"preview")
                sources.append(source)
                self.assertEqual(
                    f"{clean_pipeline_movie_name(source.name)}{source.suffix.lower()}",
                    cases[source_name],
                    f"Python movie cleaner mismatch for {source_name}",
                )
            service = DummyRenamePreviewRunnerService(repo_root)
            service._subprocess_kwargs_hidden = lambda: {}  # type: ignore[method-assign]
            policy = rename_cleaning_policy_from_config({})

            previews, message = load_pipeline_movie_name_previews_for_service(
                service,
                sources,
                powershell_host=str(powershell_host),
                timeout_seconds=60,
                run_capture_func=run_capture,
                cleaning_policy=policy,
            )

        self.assertEqual(message, "")
        for source in sources:
            with self.subTest(source_name=source.name):
                self.assertEqual(previews[str(source).casefold()], cases[source.name])

    def test_active_bad_rename_corpus_cases_execute_through_real_powershell_preview(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        powershell_host = repo_root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
        if not powershell_host.exists():
            self.skipTest("bundled PowerShell host is unavailable")
        cases = [
            case
            for case in load_bad_rename_cases(repo_root / DEFAULT_RENAME_BAD_CASE_FIXTURE)
            if case.get("status") == "active" and case.get("kind") in {"movie_auto", "tv_auto"}
        ]
        self.assertTrue(cases, "The active bad-rename corpus should contain executable preview cases.")
        service = DummyRenamePreviewRunnerService(repo_root)
        service._subprocess_kwargs_hidden = lambda: {}  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            for case in cases:
                with self.subTest(case_id=case.get("id")):
                    source_folder = Path(td) / str(case["id"]) / str(case.get("source_folder") or "")
                    source_folder.mkdir(parents=True, exist_ok=True)
                    source = source_folder / str(case["source_file"])
                    source.write_bytes(b"bad-rename-corpus-preview")
                    config: dict[str, object] = {}
                    policy_fields = {
                        "movie_filter_options": "RenameMovieFilterOptions",
                        "movie_filter_terms": "RenameMovieFilterTerms",
                        "tv_filter_options": "RenameTVFilterOptions",
                        "tv_filter_terms": "RenameTVFilterTerms",
                        "tv_remove_terms": "RenameTVRemoveTerms",
                    }
                    for case_field, config_key in policy_fields.items():
                        if case.get(case_field) is not None:
                            config[config_key] = case[case_field]
                    if case.get("remove_terms") is not None:
                        config[
                            "RenameMovieRemoveTerms" if case["kind"] == "movie_auto" else "RenameTVRemoveTerms"
                        ] = case["remove_terms"]
                    if case.get("tv_remove_terms") is not None:
                        config["RenameTVRemoveTerms"] = case["tv_remove_terms"]
                    policy = rename_cleaning_policy_from_config(config)
                    loader = (
                        load_pipeline_movie_name_previews_for_service
                        if case["kind"] == "movie_auto"
                        else load_pipeline_tv_name_previews_for_service
                    )

                    previews, message = loader(
                        service,
                        [source],
                        powershell_host=str(powershell_host),
                        timeout_seconds=60,
                        run_capture_func=run_capture,
                        cleaning_policy=policy,
                    )

                    expected_blocked = bool(case.get("expected_blocked", False))
                    if expected_blocked:
                        self.assertNotIn(str(source).casefold(), previews)
                        self.assertNotEqual(message, "")
                        continue
                    self.assertEqual(message, "")
                    self.assertEqual(
                        previews.get(str(source).casefold()),
                        case["expected_name"],
                        f"real PowerShell preview mismatch for bad-rename case {case['id']}",
                    )


if __name__ == "__main__":
    unittest.main()
