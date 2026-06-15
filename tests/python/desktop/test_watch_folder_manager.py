from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.watch.manager import WatchContext, WatchFolderManager  # noqa: E402


def _context(
    *,
    settings: dict[str, object],
    default_roots: list[str] | None = None,
    launches: list[dict[str, object]] | None = None,
    launch_result: object | None = None,
) -> WatchContext:
    def load_settings() -> dict[str, object]:
        payload = dict(settings)
        payload.setdefault("NetworkRole", "standalone")
        return payload

    def start_pipeline(request: dict[str, object]) -> dict[str, object]:
        if launches is not None:
            launches.append(dict(request))
        if callable(launch_result):
            return launch_result()
        return launch_result or {"ok": True, "message": "started", "data": {"pid": 1234}}

    return WatchContext(
        load_settings=load_settings,
        default_watch_roots=lambda: list(default_roots or []),
        start_pipeline=start_pipeline,
        log=lambda _message: None,
    )


class WatchFolderManagerTests(unittest.TestCase):
    def test_disabled_settings_keep_manager_idle_without_roots(self) -> None:
        manager = WatchFolderManager(poll_interval_seconds=3600)
        try:
            manager.start(_context(settings={"EnableWatchFolders": False, "WatchDebounceSeconds": 9}))
            state = manager.state_mapping()
        finally:
            manager.stop("test cleanup")

        self.assertFalse(state["enabled"])
        self.assertTrue(state["running"])
        self.assertEqual(state["status"], "idle")
        self.assertEqual(state["roots"], [])
        self.assertEqual(state["debounce_seconds"], 9)
        self.assertIn("disabled", state["reason"].lower())

    def test_worker_role_disables_watch_even_when_setting_enabled(self) -> None:
        manager = WatchFolderManager(poll_interval_seconds=3600)
        try:
            manager.start(_context(settings={"EnableWatchFolders": True, "NetworkRole": "worker"}))
            state = manager.state_mapping()
        finally:
            manager.stop("test cleanup")

        self.assertFalse(state["enabled"])
        self.assertEqual(state["network_role"], "worker")
        self.assertIn("worker", state["reason"])

    def test_baseline_then_stable_file_sets_pending_work_for_enqueue_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    _context(
                        settings={
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [str(root)],
                            "WatchDebounceSeconds": 5,
                            "WatchAction": "enqueue_only",
                            "ValidExtensions": ["mkv"],
                        }
                    )
                )
                media = root / "Movie.mkv"
                media.write_bytes(b"new media")
                manager.run_single_cycle(now=10)
                manager.run_single_cycle(now=14)
                state_before = manager.state_mapping()
                manager.run_single_cycle(now=15)
                state_after = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertFalse(state_before["pending_work"])
        self.assertTrue(state_after["pending_work"])
        self.assertEqual(state_after["effective_action"], "enqueue_only")
        self.assertEqual(len(state_after["recent_detections"]), 1)
        self.assertEqual(state_after["recent_detections"][0]["path"], str(media.resolve()))

    def test_enqueue_and_launch_dispatches_backend_run_once_when_stable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            launches: list[dict[str, object]] = []
            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    _context(
                        settings={
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [str(root)],
                            "WatchDebounceSeconds": 5,
                            "WatchAction": "enqueue_and_launch",
                            "WatchRespectScheduleWindow": True,
                            "ValidExtensions": ["mkv"],
                        },
                        launches=launches,
                    )
                )
                (root / "Movie.mkv").write_bytes(b"new media")
                manager.run_single_cycle(now=20)
                manager.run_single_cycle(now=25)
                state = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertEqual(len(launches), 1)
        self.assertEqual(launches[0]["mode"], "once")
        self.assertNotIn("schedule_override", launches[0])
        self.assertFalse(state["pending_work"])
        self.assertEqual(state["last_launch"]["pid"], 1234)

    def test_watch_can_explicitly_ignore_schedule_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            launches: list[dict[str, object]] = []
            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    _context(
                        settings={
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [str(root)],
                            "WatchDebounceSeconds": 5,
                            "WatchAction": "enqueue_and_launch",
                            "WatchRespectScheduleWindow": False,
                            "ValidExtensions": ["mkv"],
                        },
                        launches=launches,
                    )
                )
                (root / "Movie.mkv").write_bytes(b"new media")
                manager.run_single_cycle(now=30)
                manager.run_single_cycle(now=35)
            finally:
                manager.stop("test cleanup")

        self.assertEqual(launches[0]["schedule_override"], "ignore")

    def test_launch_refusal_keeps_pending_then_success_clears_pending_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            launches: list[dict[str, object]] = []
            results = [
                {"ok": False, "message": "schedule gate closed"},
                {"ok": True, "message": "started", "data": {"pid": 4321}},
            ]

            def next_launch_result() -> dict[str, object]:
                return results.pop(0)

            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    _context(
                        settings={
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [str(root)],
                            "WatchDebounceSeconds": 5,
                            "WatchAction": "enqueue_and_launch",
                            "ValidExtensions": ["mkv"],
                        },
                        launches=launches,
                        launch_result=next_launch_result,
                    )
                )
                (root / "Movie.mkv").write_bytes(b"new media")
                manager.run_single_cycle(now=40)
                manager.run_single_cycle(now=45)
                refused = manager.state_mapping()
                manager.run_single_cycle(now=46)
                manager.run_single_cycle(now=47)
                succeeded = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertTrue(refused["pending_work"])
        self.assertEqual(refused["last_refusal"]["reason"], "schedule gate closed")
        self.assertFalse(succeeded["pending_work"])
        self.assertEqual(succeeded["last_launch"]["pid"], 4321)
        self.assertEqual(len(launches), 2)

    def test_coordinator_role_forces_enqueue_only_even_when_launch_configured(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            launches: list[dict[str, object]] = []
            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    _context(
                        settings={
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [str(root)],
                            "WatchDebounceSeconds": 5,
                            "WatchAction": "enqueue_and_launch",
                            "NetworkRole": "coordinator",
                            "ValidExtensions": ["mkv"],
                        },
                        launches=launches,
                    )
                )
                (root / "Movie.mkv").write_bytes(b"new media")
                manager.run_single_cycle(now=50)
                manager.run_single_cycle(now=55)
                state = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertEqual(state["effective_action"], "enqueue_only")
        self.assertTrue(state["pending_work"])
        self.assertEqual(launches, [])

    def test_network_modes_force_no_launch_for_stable_watch_files(self) -> None:
        cases = [
            ("coordinator", {"NetworkRole": "coordinator"}, True),
            (
                "coordinator local worker",
                {"NetworkRole": "coordinator", "CoordinatorAlsoEncodeLocally": True},
                True,
            ),
            ("worker", {"NetworkRole": "worker"}, False),
            ("invalid", {"NetworkRole": "coordinator-only"}, True),
            ("null", {"NetworkRole": None}, True),
            ("empty", {"NetworkRole": ""}, True),
        ]
        for _label, network_settings, expect_pending in cases:
            with self.subTest(network_settings=network_settings):
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    launches: list[dict[str, object]] = []
                    manager = WatchFolderManager(poll_interval_seconds=3600)
                    try:
                        settings = {
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [str(root)],
                            "WatchDebounceSeconds": 5,
                            "WatchAction": "enqueue_and_launch",
                            "ValidExtensions": ["mkv"],
                            **network_settings,
                        }
                        manager.start(_context(settings=settings, launches=launches))
                        (root / "Movie.mkv").write_bytes(b"new media")
                        manager.run_single_cycle(now=70)
                        manager.run_single_cycle(now=75)
                        state = manager.state_mapping()
                    finally:
                        manager.stop("test cleanup")

                self.assertEqual(launches, [])
                self.assertEqual(state["effective_action"], "enqueue_only")
                self.assertEqual(state["network_role"], str(network_settings["NetworkRole"] or "").lower())
                self.assertEqual(state["pending_work"], expect_pending)

    def test_three_files_stabilizing_together_trigger_single_launch(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            launches: list[dict[str, object]] = []
            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    _context(
                        settings={
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [str(root)],
                            "WatchDebounceSeconds": 5,
                            "WatchAction": "enqueue_and_launch",
                            "ValidExtensions": ["mkv"],
                        },
                        launches=launches,
                    )
                )
                for name in ("MovieA.mkv", "MovieB.mkv", "MovieC.mkv"):
                    (root / name).write_bytes(b"new media")
                manager.run_single_cycle(now=20)
                manager.run_single_cycle(now=25)
                state = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertEqual(len(launches), 1)
        self.assertEqual(len(state["recent_detections"]), 3)
        self.assertFalse(state["pending_work"])

    def test_settings_toggle_takes_effect_without_restart(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            settings: dict[str, object] = {
                "EnableWatchFolders": True,
                "WatchFolderRoots": [str(root)],
                "WatchDebounceSeconds": 5,
                "ValidExtensions": ["mkv"],
            }
            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(_context(settings=settings))
                enabled_state = manager.state_mapping()
                settings["EnableWatchFolders"] = False
                manager.run_single_cycle(now=10)
                disabled_state = manager.state_mapping()
                settings["EnableWatchFolders"] = True
                manager.run_single_cycle(now=20)
                reenabled_state = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertTrue(enabled_state["enabled"])
        self.assertFalse(disabled_state["enabled"])
        self.assertEqual(disabled_state["status"], "idle")
        self.assertTrue(reenabled_state["enabled"])

    def test_settings_reload_failure_degrades_to_no_launch_then_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            settings: dict[str, object] = {
                "EnableWatchFolders": True,
                "WatchFolderRoots": [str(root)],
                "WatchDebounceSeconds": 5,
                "WatchAction": "enqueue_and_launch",
                "ValidExtensions": ["mkv"],
            }
            behavior = {"fail": False}
            launches: list[dict[str, object]] = []

            def load_settings() -> dict[str, object]:
                if behavior["fail"]:
                    raise RuntimeError("settings store offline")
                return dict(settings)

            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    WatchContext(
                        load_settings=load_settings,
                        default_watch_roots=lambda: [],
                        start_pipeline=lambda request: launches.append(dict(request))
                        or {"ok": True, "message": "started", "data": {}},
                        log=lambda _message: None,
                    )
                )
                (root / "Movie.mkv").write_bytes(b"new media")
                behavior["fail"] = True
                manager.run_single_cycle(now=10)
                manager.run_single_cycle(now=15)
                degraded_state = manager.state_mapping()
                behavior["fail"] = False
                manager.run_single_cycle(now=20)
                recovered_state = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertFalse(degraded_state["enabled"])
        self.assertEqual(degraded_state["effective_action"], "enqueue_only")
        self.assertEqual(degraded_state["network_role"], "__settings_reload_failed__")
        self.assertIn("settings reload failed", degraded_state["last_error"])
        self.assertEqual(launches, [])
        self.assertEqual(recovered_state["status"], "running")
        self.assertEqual(recovered_state["last_error"], "")

    def test_empty_watch_roots_derive_from_default_source_roots(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = WatchFolderManager(poll_interval_seconds=3600)
            try:
                manager.start(
                    _context(
                        settings={
                            "EnableWatchFolders": True,
                            "WatchFolderRoots": [],
                            "WatchDebounceSeconds": 5,
                            "ValidExtensions": ["mkv"],
                        },
                        default_roots=[str(root)],
                    )
                )
                state = manager.state_mapping()
            finally:
                manager.stop("test cleanup")

        self.assertTrue(state["enabled"])
        self.assertTrue(state["derived_roots_from_library_profiles"])
        self.assertEqual(state["roots"][0]["path"], str(root.resolve()))


if __name__ == "__main__":
    unittest.main()
