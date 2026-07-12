"""Rename Workbench static + backend tests.

Asserts the standalone-tool redesign:
  - header stepper removed, three workflow sections retained, queue controls removed
  - staged-path controls use explicit safe labels
  - single Title/Show field, Movie Title removed
  - Template labels match the new copy
  - Confirm + Result dialogs present
  - Browse Folder JS handler uses folder_files mode
  - Backend folder_files browse mode returns ok shape
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

REPO_ROOT = find_repo_root(Path(__file__))
STATIC_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
PARTIAL = STATIC_ROOT / "partials" / "page-rename.html"
RENAME_JS = STATIC_ROOT / "assets" / "renameView.js"
APP_JS = STATIC_ROOT / "assets" / "app.js"
RENAME_ASSET_NAMES = (
    "rename/cleaningFilters.js",
    "rename/cleaningWorkbench.js",
    "rename/selection.js",
    "rename/paths.js",
    "rename/preview.js",
    "rename/applyReadiness.js",
    "rename/editing.js",
    "rename/applyResult.js",
    "rename/commandEvidence.js",
    "rename/previewLifecycle.js",
    "rename/interactions.js",
    "rename/confirmSummary.js",
    "rename/dialogs.js",
    "renameView.js",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rename_asset_bundle() -> str:
    return "\n".join(_read(STATIC_ROOT / "assets" / name) for name in RENAME_ASSET_NAMES)


class RenameWorkbenchHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = _read(PARTIAL)

    def test_header_stepper_removed_but_workflow_sections_remain(self) -> None:
        self.assertNotIn("rename-status-strip", self.html)
        self.assertNotIn("rename-status-chip", self.html)
        for heading_id, label in (
            ("rename-stage-files-heading", "Choose Files"),
            ("rename-stage-mode-heading", "Naming Mode"),
            ("rename-stage-preview-heading", "Preview / Apply"),
        ):
            self.assertIn(heading_id, self.html)
            self.assertIn(label, self.html)
        # Removed legacy workflow chips:
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
        self.assertIn("Confirm filesystem rename", self.html)
        self.assertIn("Backend rename.apply will rename the checked media and matching sidecars", self.html)
        self.assertIn("Apply Renames", self.html)
        self.assertIn('id="rename-undo-button"', self.html)
        self.assertIn('id="rename-result-dialog"', self.html)
        for counter in ("rename-result-success", "rename-result-unchanged", "rename-result-failed", "rename-result-skipped", "rename-result-protected"):
            self.assertIn(counter, self.html)
        for label in ("rename-result-success-label", "rename-result-unchanged-label", "rename-result-protected-label"):
            self.assertIn(label, self.html)
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
        for label in ("Add files from folder", "Clear staged paths", "Add manual path"):
            self.assertIn(label, self.html)
        for old_label in (">Browse Folder<", ">Clear<", ">Add Path<", ">Apply Rename<"):
            self.assertNotIn(old_label, self.html)

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

    def test_bad_case_logging_dialog_present(self) -> None:
        for node_id in (
            "rename-log-bad-case-button",
            "rename-log-bad-case-status",
            "rename-log-case-dialog",
            "rename-log-case-source-folder",
            "rename-log-case-source-file",
            "rename-log-case-expected-name",
            "rename-log-case-expected-show",
            "rename-log-case-expected-season",
            "rename-log-case-status-select",
            "rename-log-case-notes",
            "rename-log-case-submit-button",
        ):
            self.assertIn(node_id, self.html)
        self.assertIn("Log Bad Rename Case", self.html)
        self.assertIn("Append Case writes a backend bad-case corpus entry only", self.html)
        self.assertIn('<option value="pending">Pending</option>', self.html)
        self.assertIn('<option value="active">Active</option>', self.html)


class RenameWorkbenchJsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.js = _rename_asset_bundle()
        self.app_js = _read(APP_JS)

    def test_browse_folder_uses_folder_files_mode(self) -> None:
        # The workbench init wires the Browse Folder button to call browseRenamePaths("folder_files").
        self.assertIn('browseRenamePaths("folder_files")', self.js)

    def test_browse_handler_accepts_folder_files(self) -> None:
        # browseRenamePaths normalizes the mode list to include folder_files.
        self.assertIn('"folder_files"', self.js)
        # selection_mode in the API request is the normalized mode (no string-literal replacement).
        self.assertIn("selection_mode: mode", self.js)

    def test_workbench_init_exported(self) -> None:
        self.assertIn("renameInitWorkbenchEvents", self.js)
        self.assertIn("renameOpenConfirmDialog", self.js)
        self.assertIn("renameOpenResultDialog", self.js)
        self.assertIn("renameSyncModeFieldVisibility", self.js)
        # The lifecycle orchestration slice calls the public Rename facade.
        orchestration_js = _read(STATIC_ROOT / "assets" / "app" / "lifecycleOrchestration.js")
        self.assertIn("renameView.renameInitWorkbenchEvents?.()", orchestration_js)
        self.assertIn("renameUsesStandaloneWorkbench", orchestration_js)
        self.assertIn("renameBrowseFolderButton && !renameUsesStandaloneWorkbench", orchestration_js)

    def test_apply_workbench_requires_checked_preview_rows(self) -> None:
        self.assertIn("applyRenameWorkbench", self.js)
        self.assertIn("renameApplicablePreviewRows", self.js)
        self.assertIn('source: "none; check intended rows before apply"', self.js)
        self.assertIn("Check rows before apply", self.js)
        self.assertIn("Apply ${rowsToApply.length} checked rename", self.js)
        self.assertIn("Preview out of date. Run Preview again before applying.", self.js)
        self.assertIn("No rows checked. Check intended rows before applying", self.js)
        self.assertNotIn("Apply all ${rowsToApply.length} safe rename", self.js)
        self.assertNotIn("No rows were checked; this will apply all safe rows in the current preview.", self.js)
        self.assertIn("renameRequestSignatureFromRequest", self.js)
        self.assertIn("renamePathOrigins", self.js)

    def test_result_dialog_does_not_direct_open_file_urls(self) -> None:
        self.assertNotIn("window.open(`file://", self.js)
        self.assertIn("Open logs through the backend-owned Diagnostics targets.", self.js)
        self.assertIn('requestOpen("run_logs")', self.js)

    def test_bad_case_logging_posts_backend_command(self) -> None:
        self.assertIn("renameBadCasePayloadFromRow", self.js)
        self.assertIn("submitRenameBadCasePayload", self.js)
        self.assertIn("openRenameBadCaseDialog", self.js)
        self.assertIn("submitRenameBadCaseDialog", self.js)
        self.assertIn('apiPost("/api/rename/filter-cases", request)', self.js)
        self.assertIn("confirm_append: true", self.js)

    def test_undo_last_apply_button_posts_backend_command(self) -> None:
        self.assertIn("undoLastRenameApply", self.js)
        self.assertIn("renameOpenUndoConfirmDialog", self.js)
        self.assertIn('apiPost("/api/rename/undo"', self.js)
        self.assertIn("confirm_undo: true", self.js)
        self.assertIn("state.lastUndoManifest = payload.ok ? renameUndoManifestFromApplyResult(payload) : \"\";", self.js)
        self.assertIn('if (undoButton) undoButton.addEventListener("click", () => undoLastRenameApply());', self.js)
        self.assertIn("Undo canceled. No rename.undo request was sent.", self.js)
        self.assertIn("syncRenameUndoButton", self.js)

    def test_rename_apply_uses_honest_inflight_activity(self) -> None:
        self.assertIn("startRenameCommandActivity", self.js)
        self.assertIn("This is command activity, not row-by-row progress.", self.js)
        self.assertIn("Undoing last apply... waiting for backend result", self.js)
        self.assertNotIn("mode: \"indeterminate\"", _read(STATIC_ROOT / "assets" / "rename" / "applyResult.js"))


class RenameBackendBrowseModeTests(unittest.TestCase):
    """Backend command boundary should accept the new folder_files mode."""

    def test_command_mixin_normalizes_folder_files(self) -> None:
        # Bootstrap the api package once so the mixin import does not race the
        # legitimate intra-package cycle (server imports the mixin, mixin needs
        # path_dialogs, path_dialogs imports trigger api/__init__).
        import mediapipeline.desktop.api  # noqa: F401
        from mediapipeline.core.api.commands_rename import LocalApiRenameCommandPayloadMixin

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
        import mediapipeline.desktop.api  # noqa: F401
        from mediapipeline.core.api.commands_rename import LocalApiRenameCommandPayloadMixin

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

    def test_command_mixin_reports_selected_folder(self) -> None:
        import mediapipeline.desktop.api  # noqa: F401
        from mediapipeline.core.api.commands_rename import LocalApiRenameCommandPayloadMixin

        def fake_picker(*, selection_mode: str, initial_path: str) -> dict:
            return {
                "ok": True,
                "canceled": False,
                "paths": [r"C:\Media"],
                "message": "",
                "errors": [],
            }

        mixin = LocalApiRenameCommandPayloadMixin()
        mixin._rename_path_picker = fake_picker  # type: ignore[attr-defined]

        payload = mixin._rename_browse_payload({"selection_mode": "folder", "initial_path": ""})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["message"], "Windows file browser selected 1 folder.")

    def test_filter_case_command_appends_to_configured_fixture(self) -> None:
        import mediapipeline.desktop.api  # noqa: F401
        from mediapipeline.core.api.commands_rename import LocalApiRenameCommandPayloadMixin

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "bad_rename_cases.jsonl"
            mixin = LocalApiRenameCommandPayloadMixin()
            mixin._rename_bad_case_fixture_path = fixture_path  # type: ignore[attr-defined]

            payload = mixin._rename_filter_case_payload(
                {
                    "source_folder": "Ascendance of a Bookworm S03+SP 1080p Dual Audio BD Remux FLAC-TTGA",
                    "source_file": "S03E01-The Beginning of Winter.mkv",
                    "expected_name": "Ascendance of a Bookworm - S03E01 - The Beginning of Winter.mkv",
                    "expected_show": "Ascendance of a Bookworm",
                    "expected_season": 3,
                    "status": "pending",
                    "notes": "UI smoke",
                    "confirm_append": True,
                }
            )

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["command"], "rename.filter_case.append")
            self.assertEqual(payload["data"]["status"], "pending")
            rows = [
                json.loads(line)
                for line in fixture_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_file"], "S03E01-The Beginning of Winter.mkv")
            self.assertEqual(rows[0]["expected_show"], "Ascendance of a Bookworm")

    def test_filter_case_command_requires_confirmation(self) -> None:
        import mediapipeline.desktop.api  # noqa: F401
        from mediapipeline.core.api.commands_rename import LocalApiRenameCommandPayloadMixin

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_path = Path(temp_dir) / "bad_rename_cases.jsonl"
            mixin = LocalApiRenameCommandPayloadMixin()
            mixin._rename_bad_case_fixture_path = fixture_path  # type: ignore[attr-defined]

            payload = mixin._rename_filter_case_payload(
                {
                    "source_folder": "Show S01",
                    "source_file": "S01E01.mkv",
                    "expected_name": "Show - S01E01.mkv",
                }
            )

            self.assertFalse(payload["ok"])
            self.assertIn("confirm_append", payload["message"])
            self.assertFalse(fixture_path.exists())


class RenameBackendPathDialogScriptTests(unittest.TestCase):
    """The PowerShell payload script branch should know about folder_files."""

    def test_powershell_script_branches_on_folder_files(self) -> None:
        import mediapipeline.desktop.api.path_dialogs as path_dialogs

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
