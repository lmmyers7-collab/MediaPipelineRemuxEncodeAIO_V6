from __future__ import annotations

import copy
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.kernel.contracts import accepted_run_rows_fingerprint  # noqa: E402
from mediapipeline.core.paths.queue_input_fingerprint import queue_input_fingerprint  # noqa: E402
from mediapipeline.core.processes.launch_plans import build_pipeline_launch_plan  # noqa: E402
from mediapipeline.core.status.run_monitor import RunMonitorStore  # noqa: E402
from mediapipeline.core.validation.boundary import ValidationFailure, validate_api_payload  # noqa: E402
from mediapipeline.desktop.application import MediaPipelineApplicationFacade  # noqa: E402
from tests.python.desktop.application_facade_test_support import (  # noqa: E402
    DummyWorkflowFacadeService,
    _resolved,
)


PIPELINE_START_ROUTE = "/api/pipeline/start"
PRIORITY_EXPORT_ROUTE = "/api/queue/priority-export"


def _priority_export_store_type() -> type[Any]:
    module = importlib.import_module("mediapipeline.core.queue.priority_export")
    return module.PriorityQueueExportStore


def _accepted_row(index: int, source_path: str) -> dict[str, Any]:
    return {
        "run_queue_index": index,
        "run_queue_total": 7,
        "source_identity": f"source-{index}",
        "source_identity_algorithm": "path_size_mtime_sha256.v1",
        "source_path": source_path,
        "display_name": Path(source_path).name,
        "planned_display_name": Path(source_path).name,
        "planned_display_name_source": "plex_destination_plan.v1",
        "parent_context": str(Path(source_path).parent),
        "route": "remux",
        "route_reason_code": "copy_compatible",
        "route_reason": "Already compatible",
        "intended_final_path": str(Path("C:/Out") / Path(source_path).name),
    }


def _queue_snapshot() -> dict[str, Any]:
    candidates = [
        ("C:/Media/ExplicitHigh.mkv", True, "high", ["manifest"], "", "ready", False),
        ("C:/Media/! MarkerHigh.mkv", True, "normal", ["file"], "", "ready", False),
        ("C:/Media/Normal.mkv", False, "normal", [], "", "ready", False),
        ("C:/Media/Low.mkv", False, "low", ["manifest"], "", "ready", False),
        ("C:/Media/Held.mkv", True, "high", ["manifest"], "operator_hold", "ready", False),
        ("C:/Media/Completed.mkv", True, "high", ["manifest"], "", "completed", False),
        ("C:/Media/PendingExcluded.mkv", True, "high", ["manifest"], "", "ready", True),
    ]
    accepted_rows = [_accepted_row(index, item[0]) for index, item in enumerate(candidates, start=1)]
    return {
        "schema_version": "queue_plan_snapshot.v1",
        "queue_plan_fingerprint_schema": "queue_plan_fingerprint.v1",
        "queue_plan_fingerprint": "queue-plan-fingerprint-1",
        "queue_input_fingerprint_schema": "queue_input_fingerprint.v1",
        "queue_input_fingerprint": "queue-input-fingerprint-1",
        "accepted_run_rows_fingerprint_schema": "accepted_run_rows_fingerprint.v1",
        "accepted_run_rows_fingerprint": accepted_run_rows_fingerprint(accepted_rows),
        "accepted_run_rows": accepted_rows,
        "rows": [
            {
                "source_path": source_path,
                "is_priority": is_priority,
                "effective_priority": effective_priority,
                "priority_reasons": priority_reasons,
                "blocked_reason": blocked_reason,
                "status": status,
                "pending_publish_excluded": pending_publish_excluded,
            }
            for (
                source_path,
                is_priority,
                effective_priority,
                priority_reasons,
                blocked_reason,
                status,
                pending_publish_excluded,
            ) in candidates
        ],
    }


class PipelineStartPriorityScopeContractTests(unittest.TestCase):
    def test_priority_export_creation_route_accepts_only_an_empty_object(self) -> None:
        self.assertEqual(validate_api_payload(PRIORITY_EXPORT_ROUTE, {}), {})
        with self.assertRaises(ValidationFailure):
            validate_api_payload(PRIORITY_EXPORT_ROUTE, {"selected_rows": []})

    def test_backend_queue_scope_is_the_compatible_default(self) -> None:
        self.assertEqual(validate_api_payload(PIPELINE_START_ROUTE, {"mode": "once"}), {"mode": "once"})
        self.assertEqual(
            validate_api_payload(
                PIPELINE_START_ROUTE,
                {"mode": "once", "queue_scope": "backend_queue"},
            ),
            {"mode": "once", "queue_scope": "backend_queue"},
        )

    def test_priority_export_scope_requires_an_export_id(self) -> None:
        for export_id in (None, "", "   "):
            payload: dict[str, Any] = {"mode": "once", "queue_scope": "priority_export"}
            if export_id is not None:
                payload["priority_export_id"] = export_id
            with self.subTest(export_id=export_id), self.assertRaises(ValidationFailure):
                validate_api_payload(PIPELINE_START_ROUTE, payload)

    def test_priority_export_scope_is_run_once_without_single_file(self) -> None:
        valid = {
            "mode": "once",
            "queue_scope": "priority_export",
            "priority_export_id": "priority-export-20260720-001",
        }
        self.assertEqual(validate_api_payload(PIPELINE_START_ROUTE, valid), valid)

        invalid_payloads = (
            {**valid, "mode": "continuous"},
            {**valid, "mode": "validate"},
            {**valid, "mode": "drain_pending_pushes"},
            {**valid, "single_file": "C:/Media/One.mkv"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationFailure):
                validate_api_payload(PIPELINE_START_ROUTE, payload)

    def test_pipeline_start_rejects_scope_id_mismatches_and_unknown_fields(self) -> None:
        invalid_payloads = (
            {
                "mode": "once",
                "queue_scope": "backend_queue",
                "priority_export_id": "priority-export-20260720-001",
            },
            {"mode": "once", "queue_scope": "browser_rows"},
            {
                "mode": "once",
                "queue_scope": "priority_export",
                "priority_export_id": "priority-export-20260720-001",
                "selected_rows": ["client-owned-row"],
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationFailure):
                validate_api_payload(PIPELINE_START_ROUTE, payload)


class PriorityQueueExportStoreTests(unittest.TestCase):
    def test_create_selects_only_runnable_effective_high_rows_and_persists_latest(self) -> None:
        store_type = _priority_export_store_type()
        with tempfile.TemporaryDirectory() as raw_root:
            store = store_type(Path(raw_root))
            created = store.create_from_snapshot(_queue_snapshot())
            latest = store.latest_status()

        self.assertEqual(created["status"], "ready")
        self.assertEqual(created["count"], 2)
        self.assertEqual(
            [row["source_path"] for row in created["accepted_rows"]],
            ["C:/Media/ExplicitHigh.mkv", "C:/Media/! MarkerHigh.mkv"],
        )
        self.assertEqual(created["queue_plan_fingerprint"], "queue-plan-fingerprint-1")
        self.assertEqual(created["queue_input_fingerprint"], "queue-input-fingerprint-1")
        self.assertTrue(created["accepted_run_rows_fingerprint"])
        self.assertTrue(created["export_id"])
        self.assertTrue(created["created_at"])
        self.assertEqual(latest, created)

    def test_empty_priority_selection_is_blocked_without_replacing_latest(self) -> None:
        store_type = _priority_export_store_type()
        snapshot = _queue_snapshot()
        for row in snapshot["rows"]:
            row["is_priority"] = False
            row["effective_priority"] = "normal"
            row["priority_reasons"] = []

        with tempfile.TemporaryDirectory() as raw_root:
            store = store_type(Path(raw_root))
            blocked = store.create_from_snapshot(snapshot)
            latest = store.latest_status()

        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("empty", str(blocked["reason_code"]).casefold())
        self.assertEqual(latest["status"], "missing")

    def test_launch_validation_blocks_missing_and_malformed_exports(self) -> None:
        store_type = _priority_export_store_type()
        snapshot = _queue_snapshot()
        with tempfile.TemporaryDirectory() as raw_root:
            store = store_type(Path(raw_root))
            missing = store.validate_for_launch(
                export_id="priority-export-missing",
                current_snapshot=snapshot,
            )
            created = store.create_from_snapshot(snapshot)
            store.path_for_export(created["export_id"]).write_text("{not-json", encoding="utf-8")
            malformed = store.validate_for_launch(
                export_id=created["export_id"],
                current_snapshot=snapshot,
            )

        self.assertEqual(missing["status"], "blocked")
        self.assertIn("missing", str(missing["reason_code"]).casefold())
        self.assertEqual(malformed["status"], "blocked")
        self.assertIn("malformed", str(malformed["reason_code"]).casefold())

    def test_launch_validation_blocks_stale_queue_or_input_fingerprints(self) -> None:
        store_type = _priority_export_store_type()
        snapshot = _queue_snapshot()
        with tempfile.TemporaryDirectory() as raw_root:
            store = store_type(Path(raw_root))
            created = store.create_from_snapshot(snapshot)
            changed_input = copy.deepcopy(snapshot)
            changed_input["queue_input_fingerprint"] = "queue-input-fingerprint-2"
            input_result = store.validate_for_launch(
                export_id=created["export_id"],
                current_snapshot=changed_input,
            )
            changed_plan = copy.deepcopy(snapshot)
            changed_plan["queue_plan_fingerprint"] = "queue-plan-fingerprint-2"
            plan_result = store.validate_for_launch(
                export_id=created["export_id"],
                current_snapshot=changed_plan,
            )

        for result in (input_result, plan_result):
            self.assertEqual(result["status"], "blocked")
            self.assertRegex(str(result["reason_code"]).casefold(), r"(stale|mismatch)")

    def test_launch_validation_blocks_tampered_membership_and_never_falls_back(self) -> None:
        store_type = _priority_export_store_type()
        snapshot = _queue_snapshot()
        with tempfile.TemporaryDirectory() as raw_root:
            store = store_type(Path(raw_root))
            created = store.create_from_snapshot(snapshot)
            artifact_path = store.path_for_export(created["export_id"])
            tampered = json.loads(artifact_path.read_text(encoding="utf-8"))
            tampered["accepted_rows"] = tampered["accepted_rows"][:1]
            tampered["count"] = 1
            artifact_path.write_text(json.dumps(tampered), encoding="utf-8")
            result = store.validate_for_launch(
                export_id=created["export_id"],
                current_snapshot=snapshot,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("mismatch", str(result["reason_code"]).casefold())
        self.assertNotIn("accepted_rows", result)
        self.assertNotEqual(result.get("queue_scope"), "backend_queue")

    def test_priority_only_snapshot_uses_uncapped_backend_membership(self) -> None:
        store_type = _priority_export_store_type()
        snapshot = _queue_snapshot()
        snapshot["priority_only_scope"] = True
        snapshot["accepted_run_rows"] = snapshot["accepted_run_rows"][:2]
        snapshot["accepted_run_rows_fingerprint"] = accepted_run_rows_fingerprint(
            snapshot["accepted_run_rows"]
        )
        snapshot["rows"] = snapshot["rows"][:1]
        snapshot["rows_truncated"] = True

        with tempfile.TemporaryDirectory() as raw_root:
            created = store_type(Path(raw_root)).create_from_snapshot(snapshot)

        self.assertEqual(created["status"], "ready")
        self.assertEqual(created["count"], 2)
        self.assertEqual(
            [row["source_path"] for row in created["accepted_rows"]],
            ["C:/Media/ExplicitHigh.mkv", "C:/Media/! MarkerHigh.mkv"],
        )

    def test_strict_artifact_validation_rejects_state_id_schema_and_time_tampering(self) -> None:
        mutations = (
            lambda payload: payload.update(status="blocked"),
            lambda payload: payload.update(ready=False),
            lambda payload: payload.update(export_id="priority-export-different"),
            lambda payload: payload.update(queue_plan_fingerprint_schema="queue_plan_fingerprint.v0"),
            lambda payload: payload.update(created_at="not-a-time"),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate), tempfile.TemporaryDirectory() as raw_root:
                store = _priority_export_store_type()(Path(raw_root))
                created = store.create_from_snapshot(_queue_snapshot())
                artifact_path = store.path_for_export(created["export_id"])
                payload = json.loads(artifact_path.read_text(encoding="utf-8"))
                mutate(payload)
                artifact_path.write_text(json.dumps(payload), encoding="utf-8")
                result = store.validate_for_launch(export_id=created["export_id"])

            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason_code"], "priority_export_malformed")

    def test_public_status_is_allowlisted_and_never_exposes_membership(self) -> None:
        module = importlib.import_module("mediapipeline.core.queue.priority_export")
        with tempfile.TemporaryDirectory() as raw_root:
            created = _priority_export_store_type()(Path(raw_root)).create_from_snapshot(_queue_snapshot())
        created["unexpected_state_value"] = "private"
        public = module.priority_export_public_status(created)

        self.assertNotIn("accepted_rows", public)
        self.assertNotIn("unexpected_state_value", public)
        self.assertTrue(public["accepted_membership_backend_owned"])


class PriorityQueueExportLaunchTests(unittest.TestCase):
    def test_latest_status_becomes_stale_when_queue_inputs_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="priority-export-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            snapshot = _queue_snapshot()
            snapshot["queue_input_fingerprint"] = queue_input_fingerprint(resolved)["fingerprint"]
            _priority_export_store_type()(resolved.state_root).create_from_snapshot(snapshot)
            ready = facade.get_priority_queue_export(resolved)
            resolved.config_path.write_text("@{}", encoding="utf-8")
            stale = facade.get_priority_queue_export(resolved)

        self.assertEqual(ready["status"], "ready")
        self.assertTrue(ready["ready"])
        self.assertEqual(stale["status"], "stale")
        self.assertFalse(stale["ready"])
        self.assertEqual(stale["reason_code"], "priority_export_input_stale")

    def test_preflight_blocks_invalid_priority_scope_combinations(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="priority-export-test")
            resolved = _resolved(root)
            for request in (
                {"target": "pipeline", "mode": "continuous", "queue_scope": "priority_export", "priority_export_id": "priority-export-test"},
                {"target": "pipeline", "mode": "once", "queue_scope": "priority_export", "priority_export_id": "priority-export-test", "single_file": str(root / "one.mkv")},
                {"target": "pipeline", "mode": "once", "queue_scope": "priority_export"},
                {"target": "pipeline", "mode": "once", "queue_scope": "backend_queue", "priority_export_id": "priority-export-test"},
            ):
                with self.subTest(request=request):
                    payload = facade.get_launch_preflight(resolved, request)
                    queue_scope_check = next(check for check in payload["checks"] if check["key"] == "queue_scope")
                    self.assertEqual(queue_scope_check["status"], "blocked")

    def test_priority_launch_plan_passes_internal_priority_only_switch(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolved = _resolved(Path(raw_root))
            resolved.pipeline_path.write_text("# test pipeline", encoding="utf-8")
            plan = build_pipeline_launch_plan(
                resolved,
                mode="once",
                show_config=False,
                sleep_seconds=30,
                extra_args="",
                priority_only=True,
                expected_queue_plan_fingerprint="priority-plan-fingerprint",
            )

        self.assertIn("-PriorityOnly", plan.args)
        self.assertIn("-ExpectedQueuePlanFingerprint", plan.args)
        self.assertTrue(plan.metadata["priority_only"])

    def test_run_once_seeds_exact_export_membership_and_blocks_duplicate_launch(self) -> None:
        class PriorityAwareService(DummyWorkflowFacadeService):
            def start_pipeline(
                self,
                *args: Any,
                expected_queue_plan_fingerprint: str = "",
                priority_only: bool = False,
                **kwargs: Any,
            ) -> Any:
                process = super().start_pipeline(
                    *args,
                    expected_queue_plan_fingerprint=expected_queue_plan_fingerprint,
                    **kwargs,
                )
                self.started_pipeline["priority_only"] = priority_only
                return process

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = PriorityAwareService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="priority-export-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            current_inputs = queue_input_fingerprint(resolved)
            snapshot = _queue_snapshot()
            snapshot["queue_input_fingerprint"] = current_inputs["fingerprint"]
            artifact = _priority_export_store_type()(resolved.state_root).create_from_snapshot(snapshot)
            request = {
                "mode": "once",
                "queue_scope": "priority_export",
                "priority_export_id": artifact["export_id"],
                "_command_id": "priority-export-command-1",
            }

            first = facade.start_pipeline_process(resolved, request).to_mapping()
            duplicate = facade.start_pipeline_process(resolved, request).to_mapping()
            self.assertTrue(first["ok"], first)
            monitor = RunMonitorStore(resolved.state_root).read(first["data"]["run_id"])

        self.assertFalse(duplicate["ok"])
        self.assertTrue(service.started_pipeline["priority_only"])
        self.assertEqual(service.started_pipeline["expected_queue_plan_fingerprint"], artifact["queue_plan_fingerprint"])
        self.assertIsNotNone(monitor)
        assert monitor is not None
        self.assertEqual(monitor.run.accepted_queue.accepted_count, 2)
        self.assertEqual(
            [item.source_path for item in monitor.items],
            ["C:/Media/ExplicitHigh.mkv", "C:/Media/! MarkerHigh.mkv"],
        )

    def test_direct_facade_rejects_export_id_with_backend_queue_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="priority-export-test")
            result = facade.start_pipeline_process(
                _resolved(root),
                {
                    "mode": "once",
                    "queue_scope": "backend_queue",
                    "priority_export_id": "priority-export-direct-mismatch",
                },
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["data"]["normal_queue_scope"]["reason_code"],
            "priority_export_scope_mismatch",
        )
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_priority_scope_blocks_launcher_without_explicit_priority_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="priority-export-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            snapshot = _queue_snapshot()
            snapshot["queue_input_fingerprint"] = queue_input_fingerprint(resolved)["fingerprint"]
            artifact = _priority_export_store_type()(resolved.state_root).create_from_snapshot(snapshot)
            result = facade.start_pipeline_process(
                resolved,
                {
                    "mode": "once",
                    "queue_scope": "priority_export",
                    "priority_export_id": artifact["export_id"],
                },
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["data"]["normal_queue_scope"]["reason_code"],
            "priority_export_launcher_capability_missing",
        )
        self.assertFalse(hasattr(service, "started_pipeline"))


if __name__ == "__main__":
    unittest.main()
