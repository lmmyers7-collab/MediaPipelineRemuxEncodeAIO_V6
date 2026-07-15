from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import mediapipeline.core.processes.lifecycle_lease as lifecycle_lease_module
import mediapipeline.core.processes.lifecycle_reconciliation as lifecycle_reconciliation_module
from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseError, LifecycleLeaseStore
from mediapipeline.core.processes.lifecycle_reconciliation import LifecycleReconciliationService


PidAlive = Callable[[int], bool | None]


class LifecycleReconciliationTests(unittest.TestCase):
    def _build_failed_recovery_chain(
        self,
        state_root: Path,
        *,
        pid_alive: PidAlive = lambda _pid: False,
    ) -> tuple[LifecycleReconciliationService, dict[str, Path]]:
        store = LifecycleLeaseStore(state_root, pid_alive=pid_alive)
        recovery_request = {
            "library_root": r"\\server\share\Video",
            "include_sidecars": True,
            "show_console": False,
        }
        interrupted = store.acquire(scope="Audit start", command_id="audit-command-1")
        interrupted.set_recovery_descriptor(
            route="/api/audit/start",
            request=recovery_request,
        )
        descriptor = store.begin_one_recovery_attempt()
        recovery_attempt = store.acquire(
            scope="Audit start",
            command_id=str(descriptor["recovery_command_id"]),
            resource_claims=[r"\\server\share\Video"],
        )
        recovery_attempt.set_recovery_descriptor(route="/api/audit/start", request=recovery_request)
        terminal_path = store.root / f"{recovery_attempt.lease_id}.terminal.json"
        recovery_attempt.release(outcome="launch_failed")
        # Match the final coordinator write after its real replay returns a
        # failed command result.
        store.mark_indeterminate(
            command_id="audit-command-1",
            route="/api/audit/start",
            reason="Automatic recovery did not produce a successful terminal result.",
        )
        return (
            LifecycleReconciliationService(state_root, pid_alive=pid_alive),
            {
                "marker": store.indeterminate_path,
                "recovery": store.recovery_path,
                "terminal": terminal_path,
                "lock": store.lock_path,
                "active": store.record_path,
            },
        )

    @staticmethod
    def _rewrite(path: Path, update: Callable[[dict[str, object]], None]) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        update(payload)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _rewrite_recovery_reference(path: Path, key: str, value: str) -> None:
        def update(payload: dict[str, object]) -> None:
            recovery_attempt = payload.get("recovery_attempt")
            if not isinstance(recovery_attempt, dict):
                raise AssertionError("terminal fixture is missing recovery_attempt evidence")
            recovery_attempt[key] = value

        LifecycleReconciliationTests._rewrite(path, update)

    @staticmethod
    def _rewrite_recovery_descriptor(path: Path, key: str, value: object) -> None:
        def update(payload: dict[str, object]) -> None:
            recovery = payload.get("recovery")
            if not isinstance(recovery, dict):
                raise AssertionError("fixture is missing recovery descriptor evidence")
            recovery[key] = value

        LifecycleReconciliationTests._rewrite(path, update)

    def test_preview_accepts_only_correlated_dead_failed_recovery_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            service, _paths = self._build_failed_recovery_chain(Path(raw_root) / "State")

            preview = service.preview()

            self.assertTrue(preview["safe_to_apply"])
            self.assertTrue(preview["dry_run_fingerprint"])
            self.assertEqual(preview["blockers"], [])

    def test_preview_fails_closed_for_missing_or_uncorrelated_evidence(self) -> None:
        mutations: list[tuple[str, Callable[[dict[str, Path]], None]]] = [
            ("missing marker", lambda paths: paths["marker"].unlink()),
            ("missing recovery", lambda paths: paths["recovery"].unlink()),
            ("missing terminal", lambda paths: paths["terminal"].unlink()),
            (
                "marker command mismatch",
                lambda paths: self._rewrite(paths["marker"], lambda payload: payload.update(command_id="other-command")),
            ),
            (
                "marker route mismatch",
                lambda paths: self._rewrite(paths["marker"], lambda payload: payload.update(route="/api/pipeline/start")),
            ),
            (
                "terminal command mismatch",
                lambda paths: self._rewrite(paths["terminal"], lambda payload: payload.update(command_id="other-recovery")),
            ),
            (
                "terminal recovery lease mismatch",
                lambda paths: self._rewrite_recovery_reference(
                    paths["terminal"],
                    "recovery_of_lease_id",
                    "other-lease",
                ),
            ),
            (
                "terminal recovery command mismatch",
                lambda paths: self._rewrite_recovery_reference(
                    paths["terminal"],
                    "recovery_of_command_id",
                    "other-command",
                ),
            ),
            (
                "terminal recovery route mismatch",
                lambda paths: self._rewrite_recovery_descriptor(
                    paths["terminal"],
                    "route",
                    "/api/pipeline/start",
                ),
            ),
            (
                "terminal recovery request mismatch",
                lambda paths: self._rewrite_recovery_descriptor(
                    paths["terminal"],
                    "request",
                    {
                        "library_root": r"\\server\share\Other",
                        "include_sidecars": False,
                        "show_console": False,
                    },
                ),
            ),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as raw_root:
                service, paths = self._build_failed_recovery_chain(Path(raw_root) / "State")
                mutate(paths)

                preview = service.preview()

                self.assertFalse(preview["safe_to_apply"])
                self.assertTrue(preview["blockers"])
                result = service.apply(
                    dry_run_fingerprint=str(preview.get("dry_run_fingerprint") or ""),
                    confirm_apply=True,
                    reason="Operator-approved audit lifecycle recovery",
                )
                self.assertFalse(result["ok"])
                self.assertFalse(result["applied"])

    def test_preview_fails_closed_unless_every_recorded_pid_is_dead(self) -> None:
        live_pid_cases = (
            ("recovery owner", "recovery", "owner_pid", 41001),
            ("recovery child", "recovery", "child_pid", 41002),
            ("terminal owner", "terminal", "owner_pid", 41003),
        )
        for label, evidence_key, field, live_pid in live_pid_cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as raw_root:
                state_root = Path(raw_root) / "State"
                _service, paths = self._build_failed_recovery_chain(state_root)
                self._rewrite(
                    paths[evidence_key],
                    lambda payload, field=field, live_pid=live_pid: payload.update({field: live_pid}),
                )
                service = LifecycleReconciliationService(
                    state_root,
                    pid_alive=lambda pid, expected=live_pid: pid == expected,
                )

                preview = service.preview()

                self.assertFalse(preview["safe_to_apply"])
                self.assertTrue(any("PID" in str(item).upper() for item in preview["blockers"]))
                result = service.apply(
                    dry_run_fingerprint=str(preview.get("dry_run_fingerprint") or ""),
                    confirm_apply=True,
                    reason="Operator-approved audit lifecycle recovery",
                )
                self.assertFalse(result["ok"])
                self.assertFalse(result["applied"])

    def test_preview_requires_launch_failed_terminal_with_zero_child_pid(self) -> None:
        mutations: list[tuple[str, Callable[[dict[str, Path]], None]]] = [
            (
                "wrong terminal outcome",
                lambda paths: self._rewrite(paths["terminal"], lambda payload: payload.update(status="completed")),
            ),
            (
                "nonzero child pid",
                lambda paths: self._rewrite(paths["terminal"], lambda payload: payload.update(child_pid=4242)),
            ),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as raw_root:
                service, paths = self._build_failed_recovery_chain(Path(raw_root) / "State")
                mutate(paths)

                preview = service.preview()

                self.assertFalse(preview["safe_to_apply"])
                self.assertTrue(preview["blockers"])
                result = service.apply(
                    dry_run_fingerprint=str(preview.get("dry_run_fingerprint") or ""),
                    confirm_apply=True,
                    reason="Operator-approved audit lifecycle recovery",
                )
                self.assertFalse(result["ok"])
                self.assertFalse(result["applied"])

    def test_apply_requires_strict_confirmation_and_current_fingerprint(self) -> None:
        for confirmation in (None, False, "true", 1):
            with self.subTest(confirmation=confirmation), tempfile.TemporaryDirectory() as raw_root:
                state_root = Path(raw_root) / "State"
                service, paths = self._build_failed_recovery_chain(state_root)
                preview = service.preview()

                result = service.apply(
                    dry_run_fingerprint=str(preview["dry_run_fingerprint"]),
                    confirm_apply=confirmation,
                    reason="Operator-approved audit lifecycle recovery",
                )

                self.assertFalse(result["ok"])
                self.assertFalse(result["applied"])
                self.assertTrue(result["errors"])
                self.assertTrue(paths["marker"].exists())
                self.assertTrue(paths["recovery"].exists())

        with tempfile.TemporaryDirectory() as raw_root:
            state_root = Path(raw_root) / "State"
            service, paths = self._build_failed_recovery_chain(state_root)

            result = service.apply(
                dry_run_fingerprint="stale-fingerprint",
                confirm_apply=True,
                reason="Operator-approved audit lifecycle recovery",
            )

            self.assertFalse(result["ok"])
            self.assertFalse(result["applied"])
            self.assertTrue(result["errors"])
            self.assertTrue(paths["marker"].exists())
            self.assertTrue(paths["recovery"].exists())

    def test_apply_archives_correlated_evidence_before_clearing_only_lifecycle_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            source_media = root / "Source" / "Movie.mkv"
            source_sidecar = root / "Source" / "Movie.json"
            source_media.parent.mkdir(parents=True)
            source_media.write_bytes(b"source-media-must-not-change")
            source_sidecar.write_text('{"operator":"owned"}\n', encoding="utf-8")
            source_before = {
                source_media: source_media.read_bytes(),
                source_sidecar: source_sidecar.read_bytes(),
            }
            service, paths = self._build_failed_recovery_chain(state_root)
            evidence_before = {
                key: path.read_bytes()
                for key, path in paths.items()
                if key in {"marker", "recovery", "terminal"}
            }
            preview = service.preview()

            result = service.apply(
                dry_run_fingerprint=str(preview["dry_run_fingerprint"]),
                confirm_apply=True,
                reason="Operator-approved audit lifecycle recovery",
            )

            self.assertTrue(result["ok"])
            self.assertTrue(result["applied"])
            archive_path = Path(str(result["archive_path"]))
            self.assertTrue(archive_path.is_dir())
            archived_paths = [Path(str(item)) for item in result["archived_paths"]]
            expected_names = {paths["marker"].name, paths["recovery"].name, paths["terminal"].name}
            self.assertTrue(
                expected_names.issubset({path.name for path in archived_paths}),
            )
            archived_evidence = {path.name: path.read_bytes() for path in archived_paths if path.name in expected_names}
            self.assertEqual(
                archived_evidence,
                {paths[key].name: value for key, value in evidence_before.items()},
            )
            self.assertFalse(paths["marker"].exists())
            self.assertFalse(paths["recovery"].exists())
            self.assertFalse(paths["terminal"].exists())
            self.assertFalse(paths["lock"].exists())
            self.assertFalse(paths["active"].exists())
            self.assertEqual(
                LifecycleLeaseStore(state_root, pid_alive=lambda _pid: False).status()["status"],
                "idle",
            )
            self.assertEqual({path: path.read_bytes() for path in source_before}, source_before)

    def test_incomplete_reconciliation_intent_blocks_new_lifecycle_work(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            state_root = Path(raw_root) / "State"
            state_root.mkdir(parents=True)
            (state_root / "LifecycleReconciliationPending.json").write_text(
                '{"schema_version":"desktop_lifecycle_reconciliation_transaction.v1","status":"prepared"}\n',
                encoding="utf-8",
            )
            store = LifecycleLeaseStore(state_root, pid_alive=lambda _pid: False)

            self.assertEqual(store.status()["status"], "indeterminate")
            with self.assertRaises(LifecycleLeaseError):
                store.acquire(scope="Audit start", command_id="new-audit")

    def test_acquire_rechecks_reconciliation_guard_after_creating_its_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            state_root = Path(raw_root) / "State"
            store = LifecycleLeaseStore(state_root, pid_alive=lambda _pid: False)
            store.root.mkdir(parents=True)
            real_open = lifecycle_lease_module.os.open

            def create_guard_then_open(path: object, flags: int, *args: object) -> int:
                if Path(path) == store.lock_path:
                    store.reconciliation_pending_path.write_text(
                        '{"schema_version":"desktop_lifecycle_reconciliation_transaction.v1","status":"prepared"}\n',
                        encoding="utf-8",
                    )
                return real_open(path, flags, *args)

            with patch.object(lifecycle_lease_module.os, "open", side_effect=create_guard_then_open):
                with self.assertRaises(LifecycleLeaseError):
                    store.acquire(scope="Audit start", command_id="racing-audit")

            self.assertFalse(store.lock_path.exists())
            self.assertFalse(store.record_path.exists())

    def test_reconcile_revalidates_after_publishing_guard_before_archive(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            state_root = Path(raw_root) / "State"
            service, paths = self._build_failed_recovery_chain(state_root)
            preview = service.preview()
            real_atomic_write = lifecycle_reconciliation_module._atomic_write_json

            def inject_active_reservation(path: Path, payload: dict[str, object]) -> None:
                real_atomic_write(path, payload)
                if path == service.pending_intent_path:
                    paths["lock"].write_bytes(b"")
                    paths["active"].write_text(
                        '{"schema_version":"desktop_lifecycle_lease.v1","lease_id":"racing-live-lease"}\n',
                        encoding="utf-8",
                    )

            with patch.object(lifecycle_reconciliation_module, "_atomic_write_json", side_effect=inject_active_reservation):
                result = service.apply(
                    dry_run_fingerprint=str(preview["dry_run_fingerprint"]),
                    confirm_apply=True,
                    reason="Race regression",
                )

            self.assertFalse(result["ok"])
            self.assertFalse(result["applied"])
            self.assertTrue(paths["marker"].exists())
            self.assertTrue(paths["lock"].exists())
            self.assertFalse(service.pending_intent_path.exists())


if __name__ == "__main__":
    unittest.main()
