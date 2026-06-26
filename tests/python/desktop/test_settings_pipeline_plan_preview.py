from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.contracts.source_media import source_media_from_ffprobe  # noqa: E402
from mediapipeline.desktop.api import LocalApiServer  # noqa: E402
from mediapipeline.desktop.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT  # noqa: E402
from mediapipeline.desktop.application import MediaPipelineApplicationFacade  # noqa: E402
from tests.python.desktop.application_facade_test_support import DummyFacadeService, _resolved  # noqa: E402


REPO_ROOT = find_repo_root(Path(__file__))
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def source_media_payload(name: str = "tv_h264_1080p_12mbps_mkv.json") -> dict:
    raw = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    return source_media_from_ffprobe(raw).model_dump(mode="json")


def post_json(url: str, payload: dict, token: str) -> tuple[int, dict]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class SettingsPipelinePlanPreviewTests(unittest.TestCase):
    def test_command_contract_reports_non_mutating_pipeline_plan_preview(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_COMMAND_ROUTE_CONTRACT}

        route = routes["/api/settings/pipeline-plan-preview"]

        self.assertEqual(route["method"], "POST")
        self.assertTrue(route["auth_required"])
        self.assertEqual(route["effect"], "none")
        self.assertEqual(route["response_schema"], "desktop_command_result.v1")
        self.assertEqual(route["data_schema"], "pipeline_plan.v1")
        self.assertIn("source_media", route["request_keys"])

    def test_facade_returns_dry_run_pipeline_plan_without_saving_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"OutputContainer": "mkv"}

            result = facade.preview_settings_pipeline_plan(resolved, {"source_media": source_media_payload()})

        self.assertTrue(result.ok)
        self.assertEqual(result.schema_version, "desktop_command_result.v1")
        self.assertEqual(result.command, "settings.pipeline_plan_preview")
        self.assertEqual(result.data["schemaVersion"], "pipeline_plan.v1")
        self.assertEqual(result.data["routeSummary"], "REMUX")
        self.assertEqual(result.data["verificationResult"]["schemaVersion"], "verification_result.v1")
        self.assertEqual(result.data["verificationResult"]["outputSizeCheck"]["status"], "disabled")
        self.assertTrue(any(item["code"] == "PENDING_PUBLISH_SAFETY_REQUIRED" for item in result.data["publishRequirements"]))
        preview = result.data["effectivePresetSnapshot"]["settingsPreview"]
        self.assertTrue(preview["dryRunOnly"])
        self.assertFalse(preview["canExecute"])
        self.assertEqual(preview["authority"], "python_preview_legacy_execution_still_authoritative")
        self.assertFalse(preview["writesConfig"])
        self.assertFalse(preview["mutatesMedia"])
        rollout = result.data["effectivePresetSnapshot"]["rollout"]
        self.assertEqual(rollout["stage"], "legacy")
        self.assertEqual(rollout["executionAuthority"], "legacy_powershell")
        self.assertFalse(rollout["newPlannerExecutionEnabled"])
        comparison = result.data["effectivePresetSnapshot"]["plannerComparison"]
        self.assertFalse(comparison["enabled"])
        self.assertEqual(comparison["status"], "disabled")
        self.assertEqual(service.saved_config_calls, [])

    def test_staged_patch_changes_preview_result_without_saving(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"OutputContainer": "mkv"}
            source = source_media_payload()

            base = facade.preview_settings_pipeline_plan(resolved, {"source_media": source})
            patched = facade.preview_settings_pipeline_plan(
                resolved,
                {"source_media": source, "changes": {"H264RemuxMaxHeight": 720}},
            )

        self.assertEqual(base.data["routeSummary"], "REMUX")
        self.assertEqual(patched.data["routeSummary"], "ENCODE")
        actions = {item["streamType"]: item["action"] for item in patched.data["streamActions"]}
        self.assertEqual(actions["video"], "encode")
        self.assertIn("H264RemuxMaxHeight", patched.data["effectivePresetSnapshot"]["settingsPreview"]["changedKeys"])
        self.assertEqual(service.saved_config_calls, [])

    def test_mp4_patch_preview_reports_compatibility_consequences(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"OutputContainer": "mkv"}

            result = facade.preview_settings_pipeline_plan(
                resolved,
                {"source_media": source_media_payload("multi_audio_tracks.json"), "changes": {"OutputContainer": "mp4"}},
            )

        self.assertTrue(result.ok)
        summary = result.data["decisionSnapshot"]["plannedOutputSummary"]["mp4_compatibility"]
        self.assertTrue(summary["active"])
        self.assertEqual(summary["selected_audio_streams"], [2])
        self.assertEqual(summary["audio_output_codec"], "eac3")
        self.assertEqual(summary["dropped_audio_count"], 2)
        self.assertTrue(summary["metadata_stripped"])
        self.assertTrue(summary["faststart_enabled"])
        risk = result.data["effectivePresetSnapshot"]["settingsPreview"]["riskSummary"]
        self.assertTrue(any(item["code"] == "mp4_container_limits" and item["severity"] == "high" for item in risk["items"]))
        self.assertEqual(service.saved_config_calls, [])

    def test_invalid_staged_patch_returns_structured_preview_error_without_saving(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"OutputContainer": "mkv"}

            result = facade.preview_settings_pipeline_plan(
                resolved,
                {"source_media": source_media_payload(), "changes": {"OutputContainer": "avi"}},
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "settings.pipeline_plan_preview")
        self.assertEqual(result.severity, "error")
        self.assertEqual(result.data["schema_version"], "pipeline_plan_preview_error.v1")
        self.assertTrue(result.data["dry_run_only"])
        self.assertFalse(result.data["can_execute"])
        self.assertFalse(result.data["writes_config"])
        self.assertFalse(result.data["mutates_media"])
        self.assertIn("OutputContainer", result.data["changed_keys"])
        self.assertTrue(any("Input should be 'mkv' or 'mp4'" in error for error in result.errors))
        self.assertEqual(service.saved_config_calls, [])

    def test_local_api_route_returns_command_result_with_pipeline_plan(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"OutputContainer": "mkv"}
            server = LocalApiServer(facade, token="plan-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, payload = post_json(
                    f"{server.url}/api/settings/pipeline-plan-preview",
                    {"source_media": source_media_payload(), "changes": {"H264RemuxMaxHeight": 720}},
                    "plan-token",
                )
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "settings.pipeline_plan_preview")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["schemaVersion"], "pipeline_plan.v1")
        self.assertEqual(payload["data"]["routeSummary"], "ENCODE")
        self.assertEqual(payload["data"]["verificationResult"]["outputSizeCheck"]["action"], "warn_only")
        self.assertTrue(any(guard["code"] == "OUTPUT_SIZE_CHECK" for guard in payload["data"]["verificationGuards"]))
        self.assertTrue(payload["data"]["commandPlans"][0]["dryRunOnly"])
        self.assertFalse(payload["data"]["commandPlans"][0]["canExecute"])
        self.assertEqual(service.saved_config_calls, [])

    def test_rollout_comparison_can_be_enabled_for_preview_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"OutputContainer": "mkv"}

            result = facade.preview_settings_pipeline_plan(
                resolved,
                {
                    "source_media": source_media_payload(),
                    "changes": {
                        "PlannerRolloutStage": "shadow",
                        "PlannerComparisonLogging": True,
                    },
                },
            )

        rollout = result.data["effectivePresetSnapshot"]["rollout"]
        comparison = result.data["effectivePresetSnapshot"]["plannerComparison"]

        self.assertTrue(result.ok)
        self.assertEqual(rollout["stage"], "shadow")
        self.assertEqual(rollout["executionAuthority"], "legacy_powershell_with_python_preview")
        self.assertFalse(rollout["newPlannerExecutionEnabled"])
        self.assertTrue(rollout["dryRunOnly"])
        self.assertTrue(comparison["enabled"])
        self.assertEqual(comparison["status"], "match")
        self.assertEqual(comparison["legacyRoute"], "REMUX")
        self.assertEqual(comparison["pythonRoute"], "REMUX")
        self.assertEqual(service.saved_config_calls, [])

    def test_local_api_route_rejects_malformed_source_facts_before_facade(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(facade, token="plan-token", resolved_provider=lambda: _resolved(root))
            try:
                server.start()
                status, payload = post_json(
                    f"{server.url}/api/settings/pipeline-plan-preview",
                    {"source_media": {"schema_version": "source_media.v1", "unexpected": True}},
                    "plan-token",
                )
            finally:
                server.stop()

        self.assertEqual(status, 400)
        self.assertIn("invalid API command payload", payload["error"])
        self.assertEqual(service.saved_config_calls, [])


if __name__ == "__main__":
    unittest.main()
