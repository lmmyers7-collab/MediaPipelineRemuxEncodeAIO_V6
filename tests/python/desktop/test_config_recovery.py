from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest import mock

sys.path.insert(0, str(find_repo_root(Path(__file__))))
sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.recovery import (  # noqa: E402
    CANONICAL_CONFIG_NAME,
    LEGACY_CONFIG_NAME,
    ensure_canonical_config,
    restore_verified_last_good_config,
    seed_user_config,
)
from mediapipeline.core.paths.defaults import (  # noqa: E402
    PER_USER_APP_DIR_NAME,
    user_config_candidates,
    user_config_dir,
)


@contextmanager
def _localappdata(path: Path | None):
    """Control LOCALAPPDATA so per-user resolution is deterministic in tests."""
    env = {} if path is None else {"LOCALAPPDATA": str(path)}
    remove = ["LOCALAPPDATA"] if path is None else []
    with mock.patch.dict(os.environ, env, clear=False):
        for key in remove:
            os.environ.pop(key, None)
        yield


class ConfigRecoveryTests(unittest.TestCase):
    def _roots(self, tmp: Path) -> tuple[Path, Path]:
        # Mirror the runtime layout: app_root = <root>/apps/desktop,
        # workspace_root = <root>; live config lives in <root>/ops/pipeline/config.
        workspace_root = tmp
        app_root = tmp / "apps" / "desktop"
        (workspace_root / "ops" / "pipeline" / "config").mkdir(parents=True, exist_ok=True)
        app_root.mkdir(parents=True, exist_ok=True)
        # An empty, controlled per-user dir base unless a test fills it.
        (tmp / "LocalAppData").mkdir(parents=True, exist_ok=True)
        return app_root, workspace_root

    def _pipeline(self, workspace_root: Path) -> Path:
        return workspace_root / "ops" / "pipeline" / "config"

    def _user_dir(self, tmp: Path) -> Path:
        return tmp / "LocalAppData" / PER_USER_APP_DIR_NAME

    def test_present_seeds_and_selects_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            canonical = self._pipeline(workspace_root) / CANONICAL_CONFIG_NAME
            payload = "@{ A = 1 }\n"
            canonical.write_text(payload, encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "seeded_user")
            self.assertTrue(result.ok)
            self.assertEqual(result.canonical_path, self._user_dir(tmp) / CANONICAL_CONFIG_NAME)
            self.assertEqual((self._user_dir(tmp) / CANONICAL_CONFIG_NAME).read_text(encoding="utf-8"), payload)

    def test_migrated_from_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            legacy = self._pipeline(workspace_root) / LEGACY_CONFIG_NAME
            payload = "@{ Source = 'X'; library_profiles = @() }\n"
            legacy.write_text(payload, encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            canonical = self._pipeline(workspace_root) / CANONICAL_CONFIG_NAME
            self.assertEqual(result.action, "migrated_seeded_user")
            self.assertTrue(canonical.is_file())
            self.assertEqual(canonical.read_text(encoding="utf-8"), payload)
            self.assertTrue(legacy.is_file())
            self.assertEqual(result.canonical_path, self._user_dir(tmp) / CANONICAL_CONFIG_NAME)
            self.assertEqual((self._user_dir(tmp) / CANONICAL_CONFIG_NAME).read_text(encoding="utf-8"), payload)

    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            (self._pipeline(workspace_root) / LEGACY_CONFIG_NAME).write_text(
                "@{ A = 1 }\n", encoding="utf-8"
            )

            with _localappdata(tmp / "LocalAppData"):
                first = ensure_canonical_config(app_root, workspace_root)
                second = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(first.action, "migrated_seeded_user")
            self.assertEqual(second.action, "user_present")

    def test_user_present_when_no_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            user_dir = self._user_dir(tmp)
            user_dir.mkdir(parents=True, exist_ok=True)
            user_canonical = user_dir / CANONICAL_CONFIG_NAME
            user_canonical.write_text("@{ U = 1 }\n", encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "user_present")
            self.assertTrue(result.ok)
            self.assertEqual(result.canonical_path, user_canonical)

    def test_user_legacy_migrates_to_user_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            user_dir = self._user_dir(tmp)
            user_dir.mkdir(parents=True, exist_ok=True)
            user_legacy = user_dir / LEGACY_CONFIG_NAME
            user_legacy.write_text("@{ U = 2 }\n", encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "user_migrated")
            self.assertTrue((user_dir / CANONICAL_CONFIG_NAME).is_file())

    def test_user_config_wins_over_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            (self._pipeline(workspace_root) / CANONICAL_CONFIG_NAME).write_text(
                "@{ local = 1 }\n", encoding="utf-8"
            )
            user_dir = self._user_dir(tmp)
            user_dir.mkdir(parents=True, exist_ok=True)
            user_payload = "@{ user = 1 }\n"
            (user_dir / CANONICAL_CONFIG_NAME).write_text(user_payload, encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "user_present")
            self.assertEqual(result.canonical_path.parent, user_dir)
            self.assertEqual((user_dir / CANONICAL_CONFIG_NAME).read_text(encoding="utf-8"), user_payload)

    def test_local_config_wins_when_localappdata_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            canonical = self._pipeline(workspace_root) / CANONICAL_CONFIG_NAME
            canonical.write_text("@{ local = 1 }\n", encoding="utf-8")

            with _localappdata(None):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "present")
            self.assertEqual(result.canonical_path, canonical)

    def test_backup_available_when_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            backups = self._pipeline(workspace_root) / "ConfigBackups"
            backups.mkdir(parents=True, exist_ok=True)
            older = backups / "MediaPipeline_config_chatgpt.backup_20260101_000000_000000.psd1"
            newer = backups / "MediaPipeline_config_chatgpt.backup_20260601_000000_000000.psd1"
            older.write_text("old\n", encoding="utf-8")
            newer.write_text("new\n", encoding="utf-8")
            import time

            now = time.time()
            os.utime(older, (now - 1000, now - 1000))
            os.utime(newer, (now, now))

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "backup_available")
            self.assertFalse(result.ok)
            self.assertEqual(result.source_path, newer)
            self.assertFalse((self._pipeline(workspace_root) / CANONICAL_CONFIG_NAME).is_file())

    def test_setup_style_side_by_side_backup_is_recovery_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            config_dir = self._pipeline(workspace_root)
            setup_backup = config_dir / f"{CANONICAL_CONFIG_NAME}.bak.20260613-120000"
            setup_backup.write_text("@{ restored = 1 }\n", encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "backup_available")
            self.assertFalse(result.ok)
            self.assertEqual(result.source_path, setup_backup)
            self.assertEqual(result.canonical_path, self._user_dir(tmp) / CANONICAL_CONFIG_NAME)

    def test_missing_config_restores_last_good_snapshot_to_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            user_dir = self._user_dir(tmp)
            snapshot = user_dir / "ConfigSnapshots" / "last_good.psd1"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text("@{ restored = 1 }\n", encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            restored = user_dir / CANONICAL_CONFIG_NAME
            self.assertEqual(result.action, "restored_last_good")
            self.assertTrue(result.ok)
            self.assertEqual(result.source_path, snapshot)
            self.assertEqual(result.canonical_path, restored)
            self.assertEqual(restored.read_text(encoding="utf-8"), "@{ restored = 1 }\n")

    def test_restore_verified_last_good_replaces_blocked_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            user_dir = self._user_dir(tmp)
            target = user_dir / CANONICAL_CONFIG_NAME
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("@{ SourceMovies = 'C:\\MediaPipeline\\Incoming\\Movies' }\n", encoding="utf-8")
            snapshot = user_dir / "ConfigSnapshots" / "last_good.psd1"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text("@{ SourceMovies = '\\\\server\\Movies' }\n", encoding="utf-8")
            snapshot_data = {f"Key{index}": index for index in range(80)}
            snapshot_data.update(
                {
                    "SourceMovies": r"\\server\Movies",
                    "SourceTV": r"\\server\TV",
                    "Outsource": r"\\server\Out",
                    "LocalBase": str(tmp / "Scratch"),
                }
            )

            def load_config_data(path: Path, _powershell_host: str | None):
                if path == snapshot:
                    return snapshot_data
                return {}

            with _localappdata(tmp / "LocalAppData"):
                result = restore_verified_last_good_config(
                    target,
                    app_root=app_root,
                    workspace_root=workspace_root,
                    powershell_host="pwsh",
                    load_config_data=load_config_data,
                )

            self.assertEqual(result.action, "restored_verified_last_good")
            self.assertTrue(result.ok)
            self.assertEqual(result.source_path, snapshot)
            self.assertEqual(target.read_text(encoding="utf-8"), snapshot.read_text(encoding="utf-8"))

    def test_restore_verified_last_good_rejects_template_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)
            user_dir = self._user_dir(tmp)
            target = user_dir / CANONICAL_CONFIG_NAME
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("@{ bad = 1 }\n", encoding="utf-8")
            snapshot = user_dir / "ConfigSnapshots" / "last_good.psd1"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text("@{ SourceMovies = 'C:\\MediaPipeline\\Incoming\\Movies' }\n", encoding="utf-8")

            def load_config_data(_path: Path, _powershell_host: str | None):
                return {
                    "SourceMovies": r"C:\MediaPipeline\Incoming\Movies",
                    "SourceTV": r"C:\MediaPipeline\Incoming\TV",
                    "Outsource": r"C:\MediaPipeline\Processed",
                    "LocalBase": r"C:\MediaPipeline\Scratch",
                    **{f"Key{index}": index for index in range(80)},
                }

            with _localappdata(tmp / "LocalAppData"):
                result = restore_verified_last_good_config(
                    target,
                    app_root=app_root,
                    workspace_root=workspace_root,
                    powershell_host="pwsh",
                    load_config_data=load_config_data,
                )

            self.assertEqual(result.action, "last_good_rejected")
            self.assertFalse(result.ok)
            self.assertEqual(target.read_text(encoding="utf-8"), "@{ bad = 1 }\n")
            self.assertIn("template", result.message)

    def test_absent_when_nothing_present(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            app_root, workspace_root = self._roots(tmp)

            with _localappdata(tmp / "LocalAppData"):
                result = ensure_canonical_config(app_root, workspace_root)

            self.assertEqual(result.action, "absent")
            self.assertFalse(result.ok)

    def test_user_config_candidates_empty_without_localappdata(self) -> None:
        with _localappdata(None):
            self.assertIsNone(user_config_dir())
            self.assertEqual(user_config_candidates(), [])

    def test_seed_user_config_copies_into_per_user_dir(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "MediaPipeline_config.psd1"
            source.write_text("@{ seed = 1 }\n", encoding="utf-8")

            with _localappdata(tmp / "LocalAppData"):
                target = seed_user_config(source)

            self.assertIsNotNone(target)
            assert target is not None
            self.assertTrue(target.is_file())
            self.assertEqual(target.name, CANONICAL_CONFIG_NAME)
            self.assertEqual(target.read_text(encoding="utf-8"), "@{ seed = 1 }\n")

    def test_seed_user_config_none_without_localappdata(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "c.psd1"
            source.write_text("x\n", encoding="utf-8")
            with _localappdata(None):
                self.assertIsNone(seed_user_config(source))


if __name__ == "__main__":
    unittest.main()
