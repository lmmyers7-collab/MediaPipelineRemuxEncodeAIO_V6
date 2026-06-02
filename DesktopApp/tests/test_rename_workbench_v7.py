"""V7 Rename Workbench static + backend tests.

Asserts the standalone-tool redesign:
  - 3-step stepper, queue controls removed
  - manual-path / paste-paths removed
  - single Title/Show field, Movie Title removed
  - Template labels match the new copy
  - Confirm + Result dialogs present
  - Browse Folder JS handler uses folder_files mode
  - Backend folder_files browse mode returns ok shape
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = REPO_ROOT / "DesktopApp" / "mediapipeline_desktop_app" / "ui_web" / "static"
PARTIAL = STATIC_ROOT / "partials" / "page-rename.html"
RENAME_JS = STATIC_ROOT / "assets" / "renameView.js"
APP_JS = STATIC_ROOT / "assets" / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class RenameV7HtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = _read(PARTIAL)

    def test_stepper_has_only_three_chips(self) -> None:
        self.assertIn("1 Choose Files", self.html)
        self.assertIn("2 Naming Mode", self.html)
        self.assertIn("3 Preview / Apply", self.html)
        # Removed legacy chips:
        self.assertNotIn("4 Review Scope", self.html)
        self.assertNotIn("5 Apply", self.html)
        self.assertNotIn("6 Result", self.html)

    def test_queue_controls_removed_from_rename_tab(self) -> None:
        for legacy_id in (
            "rename-use-selected-queue-button",
            "rename-use-loaded-queue-button",
        ):
            self.assertNotIn(legacy_id, self.html, msg=f"queue control {legacy_id!r} still in Rename HTML")
        # No queue-prompt verbiage in the Rename tab:
        self.assertNotIn("Review Queue", self.html)
        self.assertNotIn("Use Selected Queue Row", self.html)
        self.assertNotIn("Use Loaded Queue Rows", self.html)
        self.assertNotIn("Open Queue Snapshot", self.html)
        # The word "queue" should not appear in the Rename tab partial at all.
        self.assertNotIn("queue", self.html.lower())

    def test_template_dropdown_labels(self) -> None:
        for label in (
            "Auto (backend decides)",
            "TV: Show - SxxEyy - Episode Title",
            "TV: Show - SxxEyy",
            "Movie: Title (Year)",
        ):
            self.assertIn(label, self.html, msg=f"template label {label!r} missing")
        # Auto maps to the empty value (backend default).
        self.assertIn('<option value="">Auto (backend decides)</option>', self.html)
        # Old label gone:
        self.assertNotIn("Backend default", self.html)

    def test_single_title_show_field(self) -> None:
        self.assertIn("Title / Show", self.html)
        self.assertIn('id="rename-show"', self.html)
        # Movie Title separate field removed:
        self.assertNotIn('id="rename-movie-title"', self.html)
        self.assertNotIn("Movie Title", self.html)

    def test_year_visible_for_both_modes(self) -> None:
        # Year label is unmarked => always visible. TV-only fields carry the marker.
        self.assertIn("Year", self.html)
        # Year input is NOT inside a label that is tagged data-rename-mode-field="tv".
        # Quick heuristic: the substring before id="rename-movie-year" does not contain
        # data-rename-mode-field="tv" within the same <label> block.
        idx = self.html.index('id="rename-movie-year"')
        label_start = self.html.rfind("<label", 0, idx)
        label_end = self.html.index("</label>", idx)
        year_label = self.html[label_start:label_end]
        self.assertNotIn('data-rename-mode-field="tv"', year_label)

    def test_tv_only_fields_tagged(self) -> None:
        # Season and Start carry the TV-only marker so JS can hide them in Movie mode.
        self.assertIn('data-rename-mode-field="tv"', self.html)
        for input_id in ('id="rename-season"', 'id="rename-start"'):
            idx = self.html.index(input_id)
            label_start = self.html.rfind("<label", 0, idx)
            label_end = self.html.index("</label>", idx)
            label_block = self.html[label_start:label_end]
            self.assertIn('data-rename-mode-field="tv"', label_block, msg=f"{input_id} not TV-tagged")

    def test_confirm_and_result_dialogs_present(self) -> None:
        self.assertIn('id="rename-confirm-dialog"', self.html)
        self.assertIn('id="rename-confirm-list"', self.html)
        self.assertIn('id="rename-confirm-count"', self.html)
        self.assertIn('id="rename-result-dialog"', self.html)
        for counter in ("rename-result-success", "rename-result-failed", "rename-result-skipped"):
            self.assertIn(counter, self.html)
        self.assertIn('id="rename-result-errors"', self.html)

    def test_apply_button_lives_in_preview_section(self) -> None:
        # New apply button.
        self.assertIn('id="rename-apply-button"', self.html)
        # Old apply button id is gone.
        self.assertNotIn("rename-apply-selected-button", self.html)
        # No separate Apply or Result section blocks:
        self.assertNotIn('class="rename-stage rename-stage-apply"', self.html)
        self.assertNotIn('class="rename-stage rename-stage-result"', self.html)

    def test_drop_zone_present(self) -> None:
        self.assertIn('id="rename-drop-zone"', self.html)

    def test_staged_path_controls_present(self) -> None:
        self.assertIn('id="rename-add-path-input"', self.html)
        self.assertIn('id="rename-add-path-button"', self.html)
        self.assertIn('id="rename-paths"', self.html)

    def test_preview_and_readiness_tables_match_rendered_columns(self) -> None:
        self.assertIn("<th scope=\"col\">Use</th>", self.html)
        self.assertIn("<th scope=\"col\">Scrubbed / Pipeline</th>", self.html)
        self.assertIn("<th scope=\"col\">Confidence</th>", self.html)
        self.assertIn('<tr><td colspan="6">No rename preview loaded.</td></tr>', self.html)
        self.assertIn("<th scope=\"col\">Checkpoint</th>", self.html)
        self.assertIn("<th scope=\"col\">Posture</th>", self.html)
        self.assertIn("<th scope=\"col\">Evidence</th>", self.html)
        self.assertIn('<tr><td colspan="4">No rename preview loaded.</td></tr>', self.html)

    def test_read_only_evidence_nodes_present(self) -> None:
        for node_id in (
            "rename-review-board-status",
            "rename-review-board",
            "rename-batch-safety",
            "rename-pipeline-handoff-status",
            "rename-pipeline-handoff",
            "rename-apply-outcome-status",
            "rename-apply-outcome-summary",
        ):
            self.assertIn(node_id, self.html)


class RenameV7JsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.js = _read(RENAME_JS)
        self.app_js = _read(APP_JS)

    def test_browse_folder_uses_folder_files_mode(self) -> None:
        # The v7 init wires the Browse Folder button to call browseRenamePaths("folder_files").
        self.assertIn('browseRenamePaths("folder_files")', self.js)

    def test_browse_handler_accepts_folder_files(self) -> None:
        # browseRenamePaths normalizes the mode list to include folder_files.
        self.assertIn('"folder_files"', self.js)
        # selection_mode in the API request is the normalized mode (no string-literal replacement).
        self.assertIn("selection_mode: mode", self.js)

    def test_workbench_init_exported(self) -> None:
        self.assertIn("renameInitWorkbenchV7Events", self.js)
        self.assertIn("renameOpenConfirmDialog", self.js)
        self.assertIn("renameOpenResultDialog", self.js)
        self.assertIn("renameSyncModeFieldVisibility", self.js)
        # app.js calls the init.
        self.assertIn("renameInitWorkbenchV7Events", self.app_js)
        self.assertIn("renameUsesV7Workbench", self.app_js)
        self.assertIn("renameBrowseFolderButton && !renameUsesV7Workbench", self.app_js)

    def test_apply_v7_targets_non_blocked_preview_rows(self) -> None:
        self.assertIn("applyRenameWorkbenchV7", self.js)
        self.assertIn("renameApplicablePreviewRows", self.js)
        self.assertIn('source: "all applicable preview rows"', self.js)


class RenameBackendBrowseModeTests(unittest.TestCase):
    """Backend command boundary should accept the new folder_files mode."""

    def test_command_mixin_normalizes_folder_files(self) -> None:
        # Bootstrap the api package once so the mixin import does not race the
        # legitimate intra-package cycle (server imports the mixin, mixin needs
        # path_dialogs, path_dialogs imports trigger api/__init__).
        import mediapipeline_desktop_app.api  # noqa: F401
        from app.api.commands_rename import LocalApiRenameCommandPayloadMixin

        captured: dict[str, str] = {}

        def fake_picker(*, selection_mode: str, initial_path: str) -> dict:
            captured["selection_mode"] = selection_mode
            captured["initial_path"] = initial_path
            return {
                "ok": True,
                "canceled": False,
                "paths": [r"C:\Media\one.mkv", r"C:\Media\two.mkv"],
                "message": "",
                "errors": [],
            }

        class _StubFacade:
            pass

        mixin = LocalApiRenameCommandPayloadMixin()
        mixin.facade = _StubFacade()  # type: ignore[attr-defined]
        mixin._rename_path_picker = fake_picker  # type: ignore[attr-defined]

        payload = mixin._rename_browse_payload({"selection_mode": "folder_files", "initial_path": ""})

        self.assertEqual(captured["selection_mode"], "folder_files")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["selection_mode"], "folder_files")
        self.assertEqual(payload["data"]["path_count"], 2)
        # Message references the folder-files label, not the legacy "file" label.
        self.assertIn("from selected folder", payload["message"])

    def test_command_mixin_rejects_unknown_mode_to_files(self) -> None:
        # Bootstrap the api package once so the mixin import does not race the
        # legitimate intra-package cycle (server imports the mixin, mixin needs
        # path_dialogs, path_dialogs imports trigger api/__init__).
        import mediapipeline_desktop_app.api  # noqa: F401
        from app.api.commands_rename import LocalApiRenameCommandPayloadMixin

        observed: dict[str, str] = {}

        def fake_picker(*, selection_mode: str, initial_path: str) -> dict:
            observed["selection_mode"] = selection_mode
            return {"ok": True, "canceled": True, "paths": [], "message": "", "errors": []}

        class _StubFacade:
            pass

        mixin = LocalApiRenameCommandPayloadMixin()
        mixin.facade = _StubFacade()  # type: ignore[attr-defined]
        mixin._rename_path_picker = fake_picker  # type: ignore[attr-defined]

        mixin._rename_browse_payload({"selection_mode": "bogus", "initial_path": ""})

        self.assertEqual(observed["selection_mode"], "files")


class RenameBackendPathDialogScriptTests(unittest.TestCase):
    """The PowerShell payload script branch should know about folder_files."""

    def test_powershell_script_branches_on_folder_files(self) -> None:
        from mediapipeline_desktop_app.api import path_dialogs

        script = path_dialogs._powershell_dialog_script(
            {
                "selection_mode": "folder_files",
                "initial_path": "",
                "dialog_title": "",
                "dialog_description": "",
                "file_filter": "",
            }
        )
        # Modern folder picker code path is referenced:
        self.assertIn("OpenFolderDialog", script)
        # folder_files branch enumerates direct children only (no -Recurse):
        self.assertIn("folder_files", script)
        self.assertIn("Get-ChildItem", script)
        self.assertNotIn("-Recurse", script)
        # Modes are validated:
        self.assertIn("folder_files", script)
        self.assertIn("'folder'", script)
        self.assertIn("'files'", script)


if __name__ == "__main__":
    unittest.main()
