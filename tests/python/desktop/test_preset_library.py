from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.contracts.config import Config
from mediapipeline.core.config.preset_migration import preset_v2_from_legacy_config
from mediapipeline.core.config.preset_policy import PresetV2
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.validation.boundary import ValidationFailure, validate_api_payload
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.application_facade_test_support import DummyWorkflowFacadeService, _resolved


def _preset(name: str = "Archive Quality") -> dict[str, object]:
    return PresetV2(
        name=name,
        impactLevel="moderate",
        presetCategory="archive",
        processingStrategy="archive_quality",
        compatibilityTarget="archive",
    ).model_dump(mode="json", by_alias=True)


class PresetLibraryTests(unittest.TestCase):
    def test_save_list_export_compare_and_apply_preview_use_state_json_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.config_data = {"NetworkRole": "standalone"}
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preset = _preset()

            save = facade.save_preset_library(
                resolved,
                {
                    "id": "archive-quality",
                    "name": "Archive Quality",
                    "description": "Quality archival policy.",
                    "tags": ["archive", "quality"],
                    "source": "operator",
                    "preset_v2": preset,
                },
            ).to_mapping()
            listing = facade.list_preset_library(resolved).to_mapping()
            exported = facade.export_preset_library(resolved, {"id": "archive-quality"}).to_mapping()
            compared = facade.compare_preset_library(
                resolved,
                {"left_id": "archive-quality", "right_preset_v2": _preset("Archive Quality Copy")},
            ).to_mapping()
            apply_preview = facade.preview_preset_library_apply(resolved, {"id": "archive-quality"}).to_mapping()
            library_path = resolved.state_root / "PresetLibrary" / "presets.json"
            library_existed = library_path.exists()
            saved_json = json.loads(library_path.read_text(encoding="utf-8"))

        self.assertTrue(save["ok"])
        self.assertEqual(save["data"]["schema_version"], "preset_library.v1")
        self.assertEqual(save["data"]["record"]["id"], "archive-quality")
        self.assertTrue(library_existed)
        self.assertEqual(saved_json["schema_version"], "preset_library.v1")
        self.assertEqual(listing["data"]["records"][0]["id"], "archive-quality")
        self.assertEqual(exported["data"]["record"]["preset_v2"]["name"], "Archive Quality")
        self.assertTrue(compared["ok"])
        self.assertEqual(compared["data"]["left"]["id"], "archive-quality")
        self.assertEqual(apply_preview["data"]["schema_version"], "preset_library_apply_preview.v1")
        self.assertFalse(apply_preview["data"]["writes_config"])
        self.assertTrue(apply_preview["data"]["legacy_patch"])

    def test_apply_preview_discloses_unsupported_policy_and_confirmed_apply_never_saves(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.config_data = Config().model_dump(mode="json")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preset = preset_v2_from_legacy_config(resolved.config_data, name="Blocked partial apply").model_dump(
                mode="json",
                by_alias=True,
            )
            preset["audio"]["forceTranscode"] = True
            preset["subtitles"]["convertBdpgsToSrt"] = not preset["subtitles"]["convertBdpgsToSrt"]
            preset["verification"]["sourceIntegrityPreflightEnabled"] = not preset["verification"][
                "sourceIntegrityPreflightEnabled"
            ]

            with patch.object(facade, "save_settings_patch") as save:
                preview = facade.preview_preset_library_apply(resolved, {"preset_v2": preset}).to_mapping()
                applied = facade.apply_preset_library(
                    resolved,
                    {"preset_v2": preset, "confirm_apply": True},
                ).to_mapping()

        expected_paths = [
            "audio.forceTranscode",
            "subtitles.convertBdpgsToSrt",
            "verification.sourceIntegrityPreflightEnabled",
        ]
        self.assertTrue(preview["ok"])
        self.assertFalse(preview["data"]["apply_supported"])
        self.assertEqual(preview["data"]["unsupported_paths"], expected_paths)
        self.assertEqual(
            [difference["path"] for difference in preview["data"]["unsupported_differences"]],
            expected_paths,
        )
        self.assertFalse(applied["ok"])
        self.assertEqual(applied["data"]["unsupported_paths"], expected_paths)
        self.assertFalse(applied["data"]["writes_config"])
        save.assert_not_called()

    def test_confirmed_apply_saves_when_unsupported_policy_matches_current_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.config_data = Config().model_dump(mode="json")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preset = preset_v2_from_legacy_config(resolved.config_data, name="Supported legacy apply").model_dump(
                mode="json",
                by_alias=True,
            )
            saved = CommandResult(
                command="settings.patch.save",
                ok=True,
                message="Settings saved.",
                data={"writes_config": True},
            )

            with patch.object(facade, "save_settings_patch", return_value=saved) as save:
                preview = facade.preview_preset_library_apply(resolved, {"preset_v2": preset}).to_mapping()
                applied = facade.apply_preset_library(
                    resolved,
                    {"preset_v2": preset, "confirm_apply": True},
                ).to_mapping()

        self.assertTrue(preview["data"]["apply_supported"])
        self.assertEqual(preview["data"]["unsupported_differences"], [])
        self.assertTrue(applied["ok"])
        save.assert_called_once()

    def test_import_preview_validates_without_writing_library(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.import_preset_library_preview(
                resolved,
                {"records": [{"id": "plex-direct", "name": "Plex Direct", "preset_v2": _preset("Plex Direct")}]},
            ).to_mapping()

        self.assertTrue(preview["ok"])
        self.assertEqual(preview["data"]["schema_version"], "preset_library_import_preview.v1")
        self.assertEqual(preview["data"]["candidate_records"][0]["id"], "plex-direct")
        self.assertFalse((resolved.state_root / "PresetLibrary" / "presets.json").exists())

    def test_malformed_persisted_library_blocks_list_and_save_without_changing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            library_path = resolved.state_root / "PresetLibrary" / "presets.json"
            library_path.parent.mkdir(parents=True)

            valid_record = {
                "schema_version": "preset_library_record.v1",
                "id": "keep-me",
                "name": "Keep Me",
                "description": "",
                "tags": [],
                "source": "operator",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "imported_from": "",
                "preset_v2": _preset("Keep Me"),
            }
            malformed_payloads = {
                "unsupported library schema": {
                    "schema_version": "preset_library.v0",
                    "records": [valid_record],
                },
                "records object": {
                    "schema_version": "preset_library.v1",
                    "records": {"keep-me": valid_record},
                },
                "mixed records": {
                    "schema_version": "preset_library.v1",
                    "records": [valid_record, "not-an-object"],
                },
                "invalid preset": {
                    "schema_version": "preset_library.v1",
                    "records": [{**valid_record, "preset_v2": None}],
                },
                "duplicate ids": {
                    "schema_version": "preset_library.v1",
                    "records": [valid_record, {**valid_record, "id": "KEEP-ME"}],
                },
            }

            for label, payload in malformed_payloads.items():
                with self.subTest(label=label):
                    original = (json.dumps(payload, indent=1) + "\n  ").encode("utf-8")
                    library_path.write_bytes(original)

                    listing = facade.list_preset_library(resolved).to_mapping()
                    saved = facade.save_preset_library(
                        resolved,
                        {"id": "new", "name": "New", "preset_v2": _preset("New")},
                    ).to_mapping()

                    self.assertFalse(listing["ok"])
                    self.assertFalse(saved["ok"])
                    self.assertTrue(listing["data"]["recovery_required"])
                    self.assertTrue(listing["data"]["error"])
                    self.assertTrue(saved["data"]["original_bytes_preserved"])
                    self.assertIn("will not overwrite", saved["data"]["safe_next_action"])
                    self.assertEqual(library_path.read_bytes(), original)

    def test_local_api_malformed_preset_library_get_and_save_preserve_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            library_path = resolved.state_root / "PresetLibrary" / "presets.json"
            library_path.parent.mkdir(parents=True)
            original = b'{"schema_version":"preset_library.v1","records":{"keep-me":{}}}\n'
            library_path.write_bytes(original)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                list_request = Request(
                    f"{server.url}/api/settings/preset-library",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(list_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    listing = json.loads(response.read().decode("utf-8"))
                save_request = Request(
                    f"{server.url}/api/settings/preset-library/save",
                    data=json.dumps(
                        {
                            "id": "new",
                            "name": "New",
                            "preset_v2": _preset("New"),
                            "confirm_save": True,
                        }
                    ).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(save_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    saved = json.loads(response.read().decode("utf-8"))
            finally:
                server.stop()

            self.assertFalse(listing["ok"])
            self.assertFalse(saved["ok"])
            self.assertTrue(saved["data"]["recovery_required"])
            self.assertEqual(library_path.read_bytes(), original)

    def test_atomic_replace_failure_preserves_existing_library_and_removes_temp(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            library_path = resolved.state_root / "PresetLibrary" / "presets.json"
            initial = facade.save_preset_library(
                resolved,
                {"id": "keep-me", "name": "Keep Me", "preset_v2": _preset("Keep Me")},
            ).to_mapping()
            self.assertTrue(initial["ok"])
            original = library_path.read_bytes()

            with patch(
                "mediapipeline.core.config.preset_library.os.replace",
                side_effect=OSError("injected replace failure"),
            ):
                saved = facade.save_preset_library(
                    resolved,
                    {"id": "new", "name": "New", "preset_v2": _preset("New")},
                ).to_mapping()

            self.assertFalse(saved["ok"])
            self.assertEqual(library_path.read_bytes(), original)
            self.assertEqual(list(library_path.parent.glob(".presets.json.*.tmp")), [])

    def test_preset_library_payload_contracts_are_strict(self) -> None:
        save_payload = {"id": "archive-quality", "name": "Archive Quality", "preset_v2": _preset(), "confirm_save": True}
        apply_payload = {"id": "archive-quality", "confirm_apply": True}

        self.assertEqual(validate_api_payload("/api/settings/preset-library/save", save_payload), save_payload)
        self.assertEqual(validate_api_payload("/api/settings/preset-library/apply", apply_payload), apply_payload)
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/settings/preset-library/save", {**save_payload, "path": "C:/preset.json"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/settings/preset-library/apply", {**apply_payload, "confirm_apply": "true"})

    def test_local_api_preset_library_get_and_save_routes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                save_request = Request(
                    f"{server.url}/api/settings/preset-library/save",
                    data=json.dumps(
                        {
                            "id": "archive-quality",
                            "name": "Archive Quality",
                            "tags": ["archive"],
                            "preset_v2": _preset(),
                            "confirm_save": True,
                        }
                    ).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(save_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    saved = json.loads(response.read().decode("utf-8"))
                list_request = Request(
                    f"{server.url}/api/settings/preset-library",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(list_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    listing = json.loads(response.read().decode("utf-8"))
            finally:
                server.stop()

        self.assertTrue(saved["ok"])
        self.assertEqual(saved["data"]["record"]["id"], "archive-quality")
        self.assertEqual(listing["data"]["records"][0]["id"], "archive-quality")


if __name__ == "__main__":
    unittest.main()
