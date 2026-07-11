from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.api.commands_path_picker import PATH_PICKER_TARGETS
from mediapipeline.desktop.api.static_files import render_index


WEBVIEW_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
ASSETS_ROOT = WEBVIEW_ROOT / "assets"

STATIC_BADGES = [
    ("pipeline-single-file-path-picker-badge", "launch.single_file", "pipeline-start-single-file", "files"),
    ("rerun-csv-path-picker-badge", "queue.rerun_csv", "rerun-start-csv-path", "files"),
    ("report-audit-library-root-picker-badge", "reports.audit_library_root", "report-audit-start-library-root", "folder"),
    ("metrics-source-path-picker-badge", "metrics.source_root", "metrics-source-path", "folder"),
    ("rename-manual-path-picker-badge", "rename.source.media_file", "rename-add-path-input", "files"),
    ("wizard-output-root-picker-badge", "settings.wizard.output_root", "wizard-output-root", "folder"),
    ("wizard-scratch-path-picker-badge", "settings.wizard.scratch_path", "wizard-scratch-path", "folder"),
    ("wizard-ffmpeg-path-picker-badge", "settings.wizard.ffmpeg_path", "wizard-ffmpeg-path", "files"),
    ("wizard-ffprobe-path-picker-badge", "settings.wizard.ffprobe_path", "wizard-ffprobe-path", "files"),
    (
        "settings-file-safety-source-movies-picker-badge",
        "settings.file_safety.SourceMovies",
        "settings-file-safety-source-movies",
        "folder",
    ),
    (
        "settings-file-safety-source-tv-picker-badge",
        "settings.file_safety.SourceTV",
        "settings-file-safety-source-tv",
        "folder",
    ),
    (
        "settings-file-safety-outsource-picker-badge",
        "settings.file_safety.Outsource",
        "settings-file-safety-outsource",
        "folder",
    ),
    (
        "settings-file-safety-local-base-picker-badge",
        "settings.file_safety.LocalBase",
        "settings-file-safety-local-base",
        "folder",
    ),
    (
        "settings-file-safety-watch-roots-picker-badge",
        "settings.file_safety.WatchFolderRoots",
        "settings-file-safety-watch-roots",
        "folder",
    ),
    (
        "settings-subtitle-bdpgs-ocr-tool-picker-badge",
        "settings.subtitle.bdpgs_ocr_tool_path",
        "settings-subtitle-bdpgs-ocr-tool-path",
        "files",
    ),
    (
        "settings-subtitle-bdpgs-tessdata-picker-badge",
        "settings.subtitle.bdpgs_ocr_tessdata_path",
        "settings-subtitle-bdpgs-ocr-tessdata-path",
        "folder",
    ),
    (
        "settings-subtitle-vobsub-ocr-tool-picker-badge",
        "settings.subtitle.vobsub_ocr_tool_path",
        "settings-subtitle-vobsub-ocr-tool-path",
        "files",
    ),
]

DYNAMIC_TARGETS_BY_ASSET = {
    "settings/wizard/libraryEditor.js": [
        "settings.wizard.library_source_path",
        "settings.wizard.library_output_path",
        "settings.wizard.library_promotion_destination",
    ],
    "settingsLibraries/model.js": [
        "settings.library.source_path",
        "settings.library.output_path",
        "settings.library.promotion_destination",
    ],
    "settings/finalLibraryPromotion.js": [
        "settings.final_library_promotion.source_root",
        "settings.final_library_promotion.destination_root",
    ],
    "settingsView.builders.network.js": [
        "network.path_map.from_prefix",
        "network.path_map.to_prefix",
    ],
}

EXCLUDED_INPUT_IDS = [
    "settings-rename-workbench-source-file",
    "settings-rename-workbench-source-folder",
    "rename-log-case-source-folder",
    "rename-log-case-source-file",
]


def _render_html() -> str:
    response = render_index(
        WEBVIEW_ROOT,
        {"token": "path-picker-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    return response.body.decode("utf-8")


def _ids(html: str) -> set[str]:
    return {match.group(2) for match in re.finditer(r"\bid=(['\"])(.*?)\1", html)}


def _attrs(tag: str) -> dict[str, str]:
    return {
        match.group("name"): match.group("value")
        for match in re.finditer(r"(?P<name>[\w:-]+)=(?P<quote>['\"])(?P<value>.*?)(?P=quote)", tag)
    }


class WebViewPathPickerBadgeTests(unittest.TestCase):
    def test_static_path_picker_badges_target_existing_inputs_and_allowlisted_targets(self) -> None:
        html = _render_html()
        rendered_ids = _ids(html)

        for badge_id, target_key, input_id, mode in STATIC_BADGES:
            with self.subTest(badge_id=badge_id):
                self.assertIn(badge_id, rendered_ids)
                self.assertIn(input_id, rendered_ids)
                self.assertIn(target_key, PATH_PICKER_TARGETS)
                self.assertIn(mode, PATH_PICKER_TARGETS[target_key]["selection_modes"])
                self.assertIn(f'id="{badge_id}"', html)
                self.assertIn(f'data-path-picker-target="{target_key}"', html)
                self.assertIn(f'data-path-picker-input="{input_id}"', html)
                self.assertIn(f'data-path-picker-mode="{mode}"', html)

    def test_all_rendered_path_picker_badges_are_allowlisted_and_point_to_inputs(self) -> None:
        html = _render_html()
        rendered_ids = _ids(html)
        button_tags = re.findall(r"<button\b[^>]*data-path-picker-target=[^>]*>", html)
        self.assertGreaterEqual(len(button_tags), len(STATIC_BADGES))

        for tag in button_tags:
            attrs = _attrs(tag)
            with self.subTest(badge=attrs.get("id", tag)):
                target_key = attrs["data-path-picker-target"]
                input_ref = attrs["data-path-picker-input"]
                mode = attrs.get("data-path-picker-mode", "")
                self.assertIn(target_key, PATH_PICKER_TARGETS)
                if mode:
                    self.assertIn(mode, PATH_PICKER_TARGETS[target_key]["selection_modes"])
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", input_ref):
                    self.assertIn(input_ref, rendered_ids)

    def test_dynamic_path_picker_targets_are_allowlisted(self) -> None:
        for asset_name, target_keys in DYNAMIC_TARGETS_BY_ASSET.items():
            source = (ASSETS_ROOT / asset_name).read_text(encoding="utf-8")
            with self.subTest(asset=asset_name):
                self.assertIn("path-picker-badge", source)
                self.assertTrue("pathPickerInput" in source or "data-path-picker-input" in source)
            for target_key in target_keys:
                with self.subTest(asset=asset_name, target_key=target_key):
                    self.assertIn(target_key, PATH_PICKER_TARGETS)
                    self.assertIn(target_key, source)

    def test_excluded_rename_workbench_and_bad_case_fields_have_no_picker_badge(self) -> None:
        html = _render_html()

        for input_id in EXCLUDED_INPUT_IDS:
            with self.subTest(input_id=input_id):
                self.assertIn(f'id="{input_id}"', html)
                self.assertNotIn(f'data-path-picker-input="{input_id}"', html)
                self.assertNotIn(f'id="{input_id}-picker-badge"', html)


if __name__ == "__main__":
    unittest.main()
