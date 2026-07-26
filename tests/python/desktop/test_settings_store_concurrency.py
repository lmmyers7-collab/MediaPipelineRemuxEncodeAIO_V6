from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path
from queue import Empty
from unittest import mock

from mediapipeline.core.config.load import serialize_psd1_document
from mediapipeline.core.config.authority_lock import (
    SettingsAuthorityLockError,
    settings_authority_lock,
)
from mediapipeline.core.config.settings_patch_policy import settings_config_digest
from mediapipeline.core.config.settings_store import (
    SETTINGS_STORE_SCHEMA_VERSION,
    SettingsAuthorityConflictError,
    SettingsStoreError,
    migrate_imported_settings_mapping,
    save_settings_authority_for_service,
)
from mediapipeline.core.kernel.config_locations import PER_USER_APP_DIR_NAME, SETTINGS_STORE_NAME
from mediapipeline.desktop.models import ConfigSaveResult, ResolvedPaths


class _ProcessStoreService:
    def __init__(self) -> None:
        self.serialized_values: dict[str, object] = {}

    def serialize_psd1_document(self, values: dict[str, object]) -> str:
        self.serialized_values = dict(values)
        return serialize_psd1_document(values)

    def validate_config_document_for_save(
        self,
        document_text: str,
        *,
        config_values: dict[str, object] | None = None,
        powershell_host: str | None = None,
    ) -> tuple[list[str], list[str]]:
        _ = document_text, config_values, powershell_host
        return [], []

    def load_candidate(self, _path: Path, _host: str | None) -> dict[str, object]:
        return dict(self.serialized_values)

    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict[str, object] | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult:
        _ = create_backup, config_values, powershell_host
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document_text, encoding="utf-8", newline="")
        return ConfigSaveResult(output_path=output_path, backup_path=None)


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "MediaPipeline.ps1",
        config_path=root / "MediaPipeline_config.psd1",
        audit_script_path=root / "Audit.ps1",
        rerun_script_path=root / "Rerun.ps1",
        powershell_host="pwsh",
    )


def _store_path(root: Path) -> Path:
    return root / "LocalAppData" / PER_USER_APP_DIR_NAME / SETTINGS_STORE_NAME


def _initial_settings() -> dict[str, object]:
    return {
        "ConfigSchemaVersion": 1,
        "SourceMovies": r"C:\Fixture\Movies",
        "SourceTV": r"C:\Fixture\TV",
        "Outsource": r"D:\Fixture\Output",
        "LocalBase": r"E:\Fixture\Scratch",
        "RoutingProfile": "plex_direct_stream",
        "VideoQuality": 22,
    }


def _library_profile_settings() -> dict[str, object]:
    settings = _initial_settings()
    settings["LibraryProfiles"] = [
        {
            "id": "movies",
            "name": "Movies",
            "enabled": True,
            "designation": "movie",
            "source_path": r"C:\Fixture\Movies",
            "output_path": r"D:\Fixture\Output",
            "promotion_enabled": False,
            "promotion_destination": "",
            "overrides": {"editor": {}, "video": {}, "subtitles": {}, "audio": {}},
        },
        {
            "id": "tv",
            "name": "TV",
            "enabled": True,
            "designation": "tv",
            "source_path": r"C:\Fixture\TV",
            "output_path": r"D:\Fixture\Output",
            "promotion_enabled": False,
            "promotion_destination": "",
            "overrides": {"editor": {}, "video": {}, "subtitles": {}, "audio": {}},
        },
    ]
    return settings


def _read_authority_settings(root: Path) -> dict[str, object]:
    return dict(json.loads(_store_path(root).read_text(encoding="utf-8"))["settings"])


def _write_initial_authority(root: Path, settings: dict[str, object] | None = None) -> None:
    initial = dict(settings or _initial_settings())
    store_path = _store_path(root)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(
        json.dumps(
            {
                "schema_version": SETTINGS_STORE_SCHEMA_VERSION,
                "config_schema_version": 1,
                "settings": initial,
                "legacy_extras": {},
                "migrations_applied": [],
                "source_psd1_path": str(_resolved(root).config_path),
                "source_psd1_sha256": "",
                "updated_at_utc": "2026-07-20T00:00:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _resolved(root).config_path.write_text("@{ RoutingProfile = 'plex_direct_stream' }\n", encoding="utf-8")


def _process_save(
    root: Path,
    candidate: dict[str, object],
    expected_digest: str,
) -> None:
    service = _ProcessStoreService()
    save_settings_authority_for_service(
        service,
        _resolved(root),
        candidate,
        expected_authority_digest=expected_digest,
        psd1_loader=service.load_candidate,
    )


def _cas_actor(
    root_text: str,
    actor: str,
    candidate: dict[str, object],
    start_barrier: object,
    result_queue: object,
) -> None:
    root = Path(root_text)
    os.environ["LOCALAPPDATA"] = str(root / "LocalAppData")
    try:
        expected_digest = settings_config_digest(_read_authority_settings(root))
        start_barrier.wait(timeout=10)  # type: ignore[attr-defined]
        _process_save(root, candidate, expected_digest)
        result_queue.put(  # type: ignore[attr-defined]
            {"actor": actor, "status": "success", "observed_digest": expected_digest}
        )
    except Exception as exc:
        result_queue.put(  # type: ignore[attr-defined]
            {
                "actor": actor,
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "observed_digest": locals().get("expected_digest", ""),
            }
        )


def _interrupted_writer_actor(
    root_text: str,
    candidate: dict[str, object],
    expected_digest: str,
    validated_event: object,
    never_release_event: object,
) -> None:
    root = Path(root_text)
    os.environ["LOCALAPPDATA"] = str(root / "LocalAppData")
    from mediapipeline.core.config import settings_store as store_module

    original_atomic_write = store_module.atomic_write_text

    def interrupt_before_first_replace(path: Path, text: str, *, encoding: str = "utf-8") -> None:
        if Path(path) == _store_path(root):
            validated_event.set()  # type: ignore[attr-defined]
            never_release_event.wait(timeout=60)  # type: ignore[attr-defined]
        original_atomic_write(path, text, encoding=encoding)

    with mock.patch.object(store_module, "atomic_write_text", interrupt_before_first_replace):
        _process_save(root, candidate, expected_digest)


def _lock_holder_actor(root_text: str, ready_event: object, release_event: object) -> None:
    root = Path(root_text)
    os.environ["LOCALAPPDATA"] = str(root / "LocalAppData")
    with settings_authority_lock(_store_path(root), timeout_seconds=5):
        ready_event.set()  # type: ignore[attr-defined]
        release_event.wait(timeout=30)  # type: ignore[attr-defined]


def _waiting_writer_actor(
    root_text: str,
    candidate: dict[str, object],
    expected_digest: str,
    started_event: object,
    result_queue: object,
) -> None:
    root = Path(root_text)
    os.environ["LOCALAPPDATA"] = str(root / "LocalAppData")
    started_event.set()  # type: ignore[attr-defined]
    try:
        _process_save(root, candidate, expected_digest)
        result_queue.put({"status": "success"})  # type: ignore[attr-defined]
    except Exception as exc:
        result_queue.put(  # type: ignore[attr-defined]
            {"status": "error", "error_type": type(exc).__name__, "message": str(exc)}
        )


def _locked_authority_mutator_actor(
    root_text: str,
    ready_event: object,
    mutate_event: object,
    mutated_event: object,
    replacement_settings: dict[str, object],
) -> None:
    root = Path(root_text)
    os.environ["LOCALAPPDATA"] = str(root / "LocalAppData")
    store_path = _store_path(root)
    with settings_authority_lock(store_path, timeout_seconds=5):
        ready_event.set()  # type: ignore[attr-defined]
        if not mutate_event.wait(timeout=20):  # type: ignore[attr-defined]
            raise TimeoutError("authority mutation was not released")
        envelope = json.loads(store_path.read_text(encoding="utf-8"))
        envelope["settings"] = dict(replacement_settings)
        envelope["updated_at_utc"] = "2026-07-20T00:00:01Z"
        store_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        mutated_event.set()  # type: ignore[attr-defined]


def _lost_update_actor(
    root_text: str,
    actor: str,
    after_read_barrier: object,
    first_writer_done: object,
    result_queue: object,
) -> None:
    root = Path(root_text)
    os.environ["LOCALAPPDATA"] = str(root / "LocalAppData")
    service = _ProcessStoreService()
    candidate = _initial_settings()
    if actor == "first":
        candidate["RoutingProfile"] = "plex_direct_play"
    else:
        candidate["VideoQuality"] = 24

    try:
        initial = json.loads(_store_path(root).read_text(encoding="utf-8"))["settings"]
        expected_digest = settings_config_digest(initial)
        after_read_barrier.wait(timeout=10)  # type: ignore[attr-defined]
        if actor == "second" and not first_writer_done.wait(timeout=10):  # type: ignore[attr-defined]
            raise TimeoutError("first settings writer did not finish")
        save_settings_authority_for_service(
            service,
            _resolved(root),
            candidate,
            expected_authority_digest=expected_digest,
            psd1_loader=service.load_candidate,
        )
        if actor == "first":
            first_writer_done.set()  # type: ignore[attr-defined]
        result_queue.put({"actor": actor, "status": "success"})  # type: ignore[attr-defined]
    except Exception as exc:
        result_queue.put(  # type: ignore[attr-defined]
            {"actor": actor, "status": "error", "error_type": type(exc).__name__, "message": str(exc)}
        )


class SettingsStoreConcurrencyTests(unittest.TestCase):
    def _collect_results(
        self,
        processes: list[multiprocessing.Process],
        result_queue: object,
    ) -> list[dict[str, object]]:
        for process in processes:
            process.join(timeout=20)
            self.assertFalse(process.is_alive(), "settings concurrency child did not terminate")
            self.assertEqual(process.exitcode, 0)
        results: list[dict[str, object]] = []
        for _ in processes:
            try:
                results.append(result_queue.get(timeout=5))  # type: ignore[attr-defined]
            except Empty as exc:
                self.fail(f"settings concurrency child returned no result: {exc}")
        return results

    def test_two_processes_cannot_both_succeed_while_losing_disjoint_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            context = multiprocessing.get_context("spawn")
            barrier = context.Barrier(2)
            first_writer_done = context.Event()
            result_queue = context.Queue()
            processes = [
                context.Process(
                    target=_lost_update_actor,
                    args=(str(root), actor, barrier, first_writer_done, result_queue),
                )
                for actor in ("first", "second")
            ]

            for process in processes:
                process.start()
            results = self._collect_results(processes, result_queue)

            final_settings = json.loads(_store_path(root).read_text(encoding="utf-8"))["settings"]
            successful_actors = {str(item["actor"]) for item in results if item["status"] == "success"}
            both_changes_are_durable = (
                final_settings["RoutingProfile"] == "plex_direct_play" and final_settings["VideoQuality"] == 24
            )

            self.assertFalse(
                successful_actors == {"first", "second"} and not both_changes_are_durable,
                "both processes reported success after reading the same revision, but the later full-candidate write "
                f"silently lost a disjoint update: results={results!r}, final={final_settings!r}",
            )
            by_actor = {str(item["actor"]): item for item in results}
            self.assertEqual(by_actor["first"]["status"], "success", results)
            self.assertEqual(by_actor["second"]["error_type"], "SettingsAuthorityConflictError", results)
            self.assertEqual(final_settings["RoutingProfile"], "plex_direct_play")
            self.assertEqual(final_settings["VideoQuality"], 22)

    def test_two_processes_same_key_contention_has_one_winner_and_one_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            context = multiprocessing.get_context("spawn")
            barrier = context.Barrier(2)
            result_queue = context.Queue()
            choices = {"direct-play": "plex_direct_play", "archive": "archive_quality"}
            processes: list[multiprocessing.Process] = []
            for actor, value in choices.items():
                candidate = _initial_settings()
                candidate["RoutingProfile"] = value
                processes.append(
                    context.Process(
                        target=_cas_actor,
                        args=(str(root), actor, candidate, barrier, result_queue),
                    )
                )

            for process in processes:
                process.start()
            results = self._collect_results(processes, result_queue)

            successes = [item for item in results if item["status"] == "success"]
            conflicts = [item for item in results if item.get("error_type") == "SettingsAuthorityConflictError"]
            self.assertEqual(len(successes), 1, results)
            self.assertEqual(len(conflicts), 1, results)
            self.assertEqual(
                {str(item["observed_digest"]) for item in results},
                {settings_config_digest(_initial_settings())},
            )
            self.assertEqual(
                _read_authority_settings(root)["RoutingProfile"],
                choices[str(successes[0]["actor"])],
            )

    def test_stale_writer_conflicts_then_refreshed_writer_preserves_both_disjoint_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            initial_digest = settings_config_digest(_initial_settings())
            current_candidate = _initial_settings()
            current_candidate["RoutingProfile"] = "plex_direct_play"
            stale_candidate = _initial_settings()
            stale_candidate["VideoQuality"] = 24

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                _process_save(root, current_candidate, initial_digest)
                with self.assertRaises(SettingsAuthorityConflictError):
                    _process_save(root, stale_candidate, initial_digest)
                refreshed = _read_authority_settings(root)
                refreshed_digest = settings_config_digest(refreshed)
                refreshed["VideoQuality"] = 24
                _process_save(root, refreshed, refreshed_digest)

            final_settings = _read_authority_settings(root)
            self.assertEqual(final_settings["RoutingProfile"], "plex_direct_play")
            self.assertEqual(final_settings["VideoQuality"], 24)

    def test_three_processes_read_one_revision_and_only_one_can_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            context = multiprocessing.get_context("spawn")
            barrier = context.Barrier(3)
            result_queue = context.Queue()
            choices = {"quality-18": 18, "quality-24": 24, "quality-30": 30}
            processes: list[multiprocessing.Process] = []
            for actor, value in choices.items():
                candidate = _initial_settings()
                candidate["VideoQuality"] = value
                processes.append(
                    context.Process(
                        target=_cas_actor,
                        args=(str(root), actor, candidate, barrier, result_queue),
                    )
                )

            for process in processes:
                process.start()
            results = self._collect_results(processes, result_queue)

            successes = [item for item in results if item["status"] == "success"]
            conflicts = [item for item in results if item.get("error_type") == "SettingsAuthorityConflictError"]
            self.assertEqual(len(successes), 1, results)
            self.assertEqual(len(conflicts), 2, results)
            self.assertEqual(
                {str(item["observed_digest"]) for item in results},
                {settings_config_digest(_initial_settings())},
            )
            self.assertEqual(
                _read_authority_settings(root)["VideoQuality"],
                choices[str(successes[0]["actor"])],
            )

    def test_library_profile_disjoint_edits_conflict_then_rebase_preserves_both(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            initial = _library_profile_settings()
            _write_initial_authority(root, initial)
            candidates: dict[str, dict[str, object]] = {}
            for actor, profile_id, source_path in (
                ("movies", "movies", r"F:\NewMovies"),
                ("tv", "tv", r"G:\NewTV"),
            ):
                candidate = json.loads(json.dumps(initial))
                for profile in candidate["LibraryProfiles"]:
                    if profile["id"] == profile_id:
                        profile["source_path"] = source_path
                candidates[actor] = candidate

            context = multiprocessing.get_context("spawn")
            barrier = context.Barrier(2)
            result_queue = context.Queue()
            processes = [
                context.Process(
                    target=_cas_actor,
                    args=(str(root), actor, candidate, barrier, result_queue),
                )
                for actor, candidate in candidates.items()
            ]
            for process in processes:
                process.start()
            results = self._collect_results(processes, result_queue)
            successes = [item for item in results if item["status"] == "success"]
            conflicts = [item for item in results if item.get("error_type") == "SettingsAuthorityConflictError"]
            self.assertEqual(len(successes), 1, results)
            self.assertEqual(len(conflicts), 1, results)

            loser = str(conflicts[0]["actor"])
            loser_path = r"F:\NewMovies" if loser == "movies" else r"G:\NewTV"
            rebased = _read_authority_settings(root)
            rebased_digest = settings_config_digest(rebased)
            for profile in rebased["LibraryProfiles"]:  # type: ignore[index]
                if profile["id"] == loser:
                    profile["source_path"] = loser_path
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                _process_save(root, rebased, rebased_digest)

            profiles = {
                str(profile["id"]): profile
                for profile in _read_authority_settings(root)["LibraryProfiles"]  # type: ignore[index]
            }
            self.assertEqual(profiles["movies"]["source_path"], r"F:\NewMovies")
            self.assertEqual(profiles["tv"]["source_path"], r"G:\NewTV")

    def test_interrupted_process_before_replacement_releases_lock_and_leaves_authority_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            store_before = _store_path(root).read_bytes()
            config_before = _resolved(root).config_path.read_bytes()
            candidate = _initial_settings()
            candidate["VideoQuality"] = 24
            expected_digest = settings_config_digest(_initial_settings())
            context = multiprocessing.get_context("spawn")
            validated = context.Event()
            never_release = context.Event()
            process = context.Process(
                target=_interrupted_writer_actor,
                args=(str(root), candidate, expected_digest, validated, never_release),
            )
            process.start()
            self.assertTrue(validated.wait(timeout=15), "writer never reached the validation/replacement boundary")
            process.terminate()
            process.join(timeout=10)
            self.assertFalse(process.is_alive())
            self.assertNotEqual(process.exitcode, 0)
            self.assertEqual(_store_path(root).read_bytes(), store_before)
            self.assertEqual(_resolved(root).config_path.read_bytes(), config_before)

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                _process_save(root, candidate, expected_digest)
            self.assertEqual(_read_authority_settings(root)["VideoQuality"], 24)

    def test_lock_acquisition_timeout_fails_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            store_before = _store_path(root).read_bytes()
            context = multiprocessing.get_context("spawn")
            ready = context.Event()
            release = context.Event()
            holder = context.Process(target=_lock_holder_actor, args=(str(root), ready, release))
            holder.start()
            self.assertTrue(ready.wait(timeout=10), "lock holder did not acquire the authority lock")
            service = _ProcessStoreService()
            service._settings_authority_lock_timeout_seconds = 0.1  # type: ignore[attr-defined]
            candidate = _initial_settings()
            candidate["VideoQuality"] = 24
            try:
                with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                    with self.assertRaises(SettingsAuthorityLockError) as raised:
                        save_settings_authority_for_service(
                            service,
                            _resolved(root),
                            candidate,
                            expected_authority_digest=settings_config_digest(_initial_settings()),
                            psd1_loader=service.load_candidate,
                        )
            finally:
                release.set()
                holder.join(timeout=10)
            self.assertEqual(holder.exitcode, 0)
            self.assertIn("another settings transaction is active", str(raised.exception))
            self.assertEqual(_store_path(root).read_bytes(), store_before)

    def test_malformed_current_json_authority_blocks_save_without_exposing_or_overwriting_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            malformed = "{ definitely-not-valid-json\n"
            _store_path(root).write_text(malformed, encoding="utf-8")
            config_before = _resolved(root).config_path.read_bytes()
            candidate = _initial_settings()
            candidate["VideoQuality"] = 24

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                with self.assertRaises(SettingsStoreError) as raised:
                    _process_save(root, candidate, settings_config_digest(_initial_settings()))

            self.assertEqual(_store_path(root).read_text(encoding="utf-8"), malformed)
            self.assertEqual(_resolved(root).config_path.read_bytes(), config_before)
            self.assertNotIn(r"C:\Fixture\Movies", str(raised.exception))
            self.assertNotIn(r"D:\Fixture\Output", str(raised.exception))

    def test_digest_change_while_waiting_for_lock_becomes_explicit_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            initial_digest = settings_config_digest(_initial_settings())
            replacement = _initial_settings()
            replacement["RoutingProfile"] = "plex_direct_play"
            waiting_candidate = _initial_settings()
            waiting_candidate["VideoQuality"] = 24
            context = multiprocessing.get_context("spawn")
            ready = context.Event()
            mutate = context.Event()
            mutated = context.Event()
            started = context.Event()
            result_queue = context.Queue()
            holder = context.Process(
                target=_locked_authority_mutator_actor,
                args=(str(root), ready, mutate, mutated, replacement),
            )
            waiter = context.Process(
                target=_waiting_writer_actor,
                args=(str(root), waiting_candidate, initial_digest, started, result_queue),
            )
            holder.start()
            self.assertTrue(ready.wait(timeout=10))
            waiter.start()
            self.assertTrue(started.wait(timeout=10))
            mutate.set()
            self.assertTrue(mutated.wait(timeout=10))
            holder.join(timeout=10)
            waiter.join(timeout=20)
            self.assertEqual(holder.exitcode, 0)
            self.assertEqual(waiter.exitcode, 0)
            result = result_queue.get(timeout=5)
            self.assertEqual(result["error_type"], "SettingsAuthorityConflictError", result)
            final_settings = _read_authority_settings(root)
            self.assertEqual(final_settings["RoutingProfile"], "plex_direct_play")
            self.assertEqual(final_settings["VideoQuality"], 22)

    def test_atomic_store_replace_failure_rolls_back_and_retry_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            store_path = _store_path(root)
            config_path = _resolved(root).config_path
            store_before = store_path.read_bytes()
            config_before = config_path.read_bytes()
            candidate = _initial_settings()
            candidate["VideoQuality"] = 24
            expected_digest = settings_config_digest(_initial_settings())
            from mediapipeline.core.config import file_io

            original_replace = file_io.os.replace

            def fail_store_replace(source: str, destination: str | os.PathLike[str]) -> None:
                if Path(destination) == store_path:
                    raise OSError("fixture atomic replacement failure")
                original_replace(source, destination)

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                with mock.patch.object(file_io.os, "replace", fail_store_replace):
                    with self.assertRaises(OSError):
                        _process_save(root, candidate, expected_digest)
                self.assertEqual(store_path.read_bytes(), store_before)
                self.assertEqual(config_path.read_bytes(), config_before)
                self.assertEqual(list(store_path.parent.glob(f".{store_path.name}.*")), [])
                _process_save(root, candidate, expected_digest)

            self.assertEqual(_read_authority_settings(root)["VideoQuality"], 24)

    def test_retry_after_ambiguous_response_is_idempotent_when_candidate_is_already_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_initial_authority(root)
            candidate = _initial_settings()
            candidate["VideoQuality"] = 24
            expected_digest = settings_config_digest(_initial_settings())
            normalized_candidate = migrate_imported_settings_mapping(candidate).settings

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}):
                _process_save(root, candidate, expected_digest)
                first_durable = _read_authority_settings(root)
                _process_save(root, candidate, expected_digest)
                second_durable = _read_authority_settings(root)

            self.assertEqual(first_durable, normalized_candidate)
            self.assertEqual(second_durable, normalized_candidate)


if __name__ == "__main__":
    unittest.main()
