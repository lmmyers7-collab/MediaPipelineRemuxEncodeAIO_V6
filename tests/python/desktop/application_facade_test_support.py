from __future__ import annotations

import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.tools.paths import find_repo_root
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.api.command_journal import CommandJournal
from mediapipeline.core.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
from mediapipeline.desktop.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline.desktop.api.handler import build_local_api_handler_class
from mediapipeline.desktop.api.http_helpers import (
    content_type_for,
    query_bool,
    query_int,
    query_value,
    read_json_body,
    request_authorized,
    resolve_asset_path,
)
from mediapipeline.desktop.api.routes import GET_ROUTE_HANDLERS, POST_ROUTE_HANDLERS
from mediapipeline.desktop.api.static_files import local_api_bootstrap, read_static_asset, render_index
from mediapipeline.desktop.application import CommandResult, MediaPipelineApplicationFacade
from mediapipeline.desktop.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend
from mediapipeline.desktop.models import AuditRecord, ConfigSaveResult, FailureRecord, ResolvedPaths, Snapshot, TelemetrySnapshot
from mediapipeline.core.schedule.app_state import AppStateScheduleServiceMixin
from mediapipeline.core.completed.service import CompletedJobsServiceMixin
from mediapipeline.core.publish.pending_service import PendingPublishServiceMixin
from mediapipeline.core.processes.lifecycle import ProcessLifecycleServiceMixin
from mediapipeline.core.queue.service import QueueServiceMixin
from mediapipeline.core.rename.service import RenameServiceMixin
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult
from tests.css_import_resolver import resolve_css_imports


def _render_static_index_html(static_root: Path) -> str:
    response = render_index(
        static_root,
        {"token": "test-token", "appVersion": "v5-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    return response.body.decode("utf-8")


def assert_namespace_export(testcase: unittest.TestCase, source: str, namespace: str, symbol: str) -> None:
    testcase.assertRegex(
        source,
        rf"window\.{re.escape(namespace)}\s*=\s*\{{[\s\S]*?\b{re.escape(symbol)}\b\s*(?:,|:|\n\s*\}})",
    )


COMMAND_HISTORY_ASSET_ORDER = [
    "/assets/commandHistory/formatters.js",
    "/assets/commandHistory/diagnostics.js",
    "/assets/commandHistory.js",
]


_LOCAL_API_ROUTE_WORKFLOW_CACHE: SimpleNamespace | None = None


def exercise_local_api_route_workflow() -> SimpleNamespace:
    global _LOCAL_API_ROUTE_WORKFLOW_CACHE
    if _LOCAL_API_ROUTE_WORKFLOW_CACHE is not None:
        return _LOCAL_API_ROUTE_WORKFLOW_CACHE

    client = LocalApiHttpTestMixin()
    with tempfile.TemporaryDirectory() as raw_root:
        root = Path(raw_root)
        media = root / "TV" / "Season 02" / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
        media.parent.mkdir(parents=True, exist_ok=True)
        (root / "Movies").mkdir(parents=True, exist_ok=True)
        media.write_bytes(b"media")
        snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(
                {
                    "schema_version": "queue_plan_snapshot.v1",
                    "produced_at": "2026-05-07T21:00:00-04:00",
                    "config_path": str(root / "config.psd1"),
                    "local_base": str(root),
                    "source_movies": str(root / "Movies"),
                    "source_tv": str(root / "TV"),
                    "outsource": str(root / "Outsource"),
                    "movie_count_total": 0,
                    "tv_count_total": 1,
                    "priority_count": 0,
                    "runnable_count": 1,
                    "rows": [
                        {
                            "global_order": 1,
                            "phase": "tv",
                            "media_kind": "tv",
                            "queue_index": 1,
                            "queue_total": 1,
                            "is_priority": False,
                            "source_path": str(media),
                            "root_path": str(root / "TV"),
                            "relative_path": "Season 02\\Serial Experiments Lain E01 Weird.mkv",
                            "display_name": media.name,
                            "size_gb": 1.25,
                            "route": "encode",
                            "route_reason_code": "subtitle_srt_required",
                            "route_reason": "needs preferred-language SRT",
                            "blocked_reason": "",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        resolved = _resolved(root)
        resolved.source_movies = root / "Movies"
        resolved.source_tv = root / "TV"
        resolved.config_data = {
            "RoutingProfile": "plex_direct_stream",
            "SizeGuardMode": "advisory",
            "NetworkRole": "standalone",
            "ApiToken": "secret-token",
            "SourceMovies": str(root / "Movies"),
            "SourceTV": str(root / "TV"),
            "Outsource": str(root / "Outsource"),
            "MinFreeSpaceGB": 0,
            "OutsourceMinFreeSpaceGB": 0,
        }
        resolved.queue_snapshot_path = snapshot_path
        pending_root = root / "PendingServerPush"
        pending_root.mkdir()
        (pending_root / "Movie.mkv").write_bytes(b"abc")
        resolved.pending_push_path = pending_root
        completed_output = root / "Outsource" / "Movie.mkv"
        completed_output.parent.mkdir(parents=True, exist_ok=True)
        completed_output.write_bytes(b"media")
        completed_manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
        completed_manifest.parent.mkdir(parents=True, exist_ok=True)
        completed_manifest.write_text(
            json.dumps(
                {
                    "source_path": str(media),
                    "output_path": str(completed_output),
                    "route": "remux",
                    "encoded_at": "2026-05-07T21:30:00-04:00",
                    "elapsed_seconds": 30,
                    "output_size": completed_output.stat().st_size,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        resolved.completed_manifest_path = completed_manifest
        (root / "failures.json").write_text(
            json.dumps(
                [
                    {
                        "SourcePath": str(media),
                        "JobId": "job-local-encode",
                        "Stage": "encode",
                        "Reason": "No NVENC capable devices found",
                        "Classification": "operator_required",
                        "ErrorCode": "ENCODE_NVENC_FAILED",
                        "RecordedAt": "2026-05-07T22:00:00-04:00",
                        "RetryCount": 3,
                        "RetryLimit": 3,
                        "video_stream_evidence": {
                            "schema_version": "pipeline_failure_video_stream_evidence.v1",
                            "source_real_video_stream_count": 2,
                            "source_attached_picture_stream_count": 0,
                            "source_streams": [
                                {
                                    "source": "source",
                                    "index": 0,
                                    "ordinal": 0,
                                    "codec": "hevc",
                                    "width": 1920,
                                    "height": 1080,
                                    "attached_picture": False,
                                },
                                {
                                    "source": "source",
                                    "index": 1,
                                    "ordinal": 1,
                                    "codec": "h264",
                                    "width": 1280,
                                    "height": 720,
                                    "attached_picture": False,
                                },
                            ],
                        },
                    }
                ]
            ),
            encoding="utf-8",
        )
        failure_markers = root / "State" / "Failed" / "Markers"
        failure_markers.mkdir(parents=True)
        (failure_markers / "marker-1.json").write_text(
            json.dumps(
                {
                    "source_full_path": str(media),
                    "job_id": "job-local-publish",
                    "stage": "publish",
                    "reason": "Network destination unavailable",
                    "classification": "transient",
                    "error_code": "PUBLISH_UNAVAILABLE",
                    "recorded_at": "2026-05-07T22:30:00-04:00",
                    "retry_count": 1,
                    "retry_limit": 5,
                }
            ),
            encoding="utf-8",
        )
        resolved.failed_markers_path = failure_markers
        audit_csv = root / "audit_summary_latest.csv"
        audit_priority_csv = root / "audit_priority_latest.csv"
        with audit_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "Path",
                    "RelativePath",
                    "LookupTitle",
                    "MediaType",
                    "EffectiveBucket",
                    "PriorityFixLevel",
                    "PriorityScore",
                    "PrimaryIssueCode",
                    "PrimarySuggestedAction",
                    "IssueMessages",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Path": str(media),
                    "RelativePath": "Season 02\\Serial Experiments Lain E01 Weird.mkv",
                    "LookupTitle": "Serial Experiments Lain",
                    "MediaType": "TV",
                    "EffectiveBucket": "RERUN_PIPELINE",
                    "PriorityFixLevel": "HIGH",
                    "PriorityScore": "75",
                    "PrimaryIssueCode": "subtitle_srt_required",
                    "PrimarySuggestedAction": "Rerun pipeline.",
                    "IssueMessages": "Preferred-language SRT missing.",
                }
            )
        with audit_priority_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "Path",
                    "RelativePath",
                    "LookupTitle",
                    "MediaType",
                    "EffectiveBucket",
                    "PriorityFixLevel",
                    "PriorityScore",
                    "PrimaryIssueCode",
                    "PrimarySuggestedAction",
                    "IssueMessages",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Path": str(media),
                    "RelativePath": "Season 02\\Serial Experiments Lain E01 Weird.mkv",
                    "LookupTitle": "Serial Experiments Lain",
                    "MediaType": "TV",
                    "EffectiveBucket": "REVIEW",
                    "PriorityFixLevel": "HIGH",
                    "PriorityScore": "99",
                    "PrimaryIssueCode": "priority_only_issue",
                    "PrimarySuggestedAction": "Use latest priority report.",
                    "IssueMessages": "Priority report row.",
                }
            )
        (root / "RunLogs").mkdir()
        service = DummyWorkflowFacadeService(root)
        service.cleanup_stale_launch_guards = lambda _resolved_arg: []  # type: ignore[method-assign]
        service.find_related_pipeline_processes = lambda _resolved_arg, **_kwargs: []  # type: ignore[method-assign]
        service.active_job_close_block_messages = lambda _resolved_arg, job_kinds=None: []  # type: ignore[method-assign]
        service.read_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
        service.read_audit_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
        service.backfill_completed_manifest = lambda resolved, **_kwargs: (  # type: ignore[method-assign]
            True,
            "\n".join(
                [
                    "Backfill dry run complete.",
                    "  Sidecars ingested : 4",
                    "  Skipped (bad JSON): 0",
                    f"  Manifest          : {resolved.completed_manifest_path}",
                ]
            ),
        )
        facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
        facade._autonomy_health_for_resolved = lambda _resolved_arg, **_kwargs: {"overall_status": "ready"}  # type: ignore[method-assign]
        reload_calls = {"count": 0}

        def reload_resolved() -> ResolvedPaths:
            reload_calls["count"] += 1
            resolved.config_data["Reloaded"] = True
            return resolved

        server = LocalApiServer(
            facade,
            token="workflow-token",
            resolved_provider=lambda: resolved,
            resolved_reload=reload_resolved,
            audit_root_provider=lambda: str(root),
        )
        server._rename_path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
            "ok": True,
            "canceled": False,
            "selection_mode": "files",
            "paths": [str(media)],
            "message": "Selected 1 file.",
            "errors": [],
        }
        server._settings_path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
            "ok": True,
            "canceled": False,
            "selection_mode": "folder",
            "paths": [str(root / "TV")],
            "message": "Selected 1 folder.",
            "errors": [],
        }
        server._pipeline_file_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
            "ok": True,
            "canceled": False,
            "selection_mode": "files",
            "paths": [str(media)],
            "message": "Selected 1 file.",
            "errors": [],
        }
        try:
            server.start()
            queue_status, queue_payload = client._get_json(f"{server.url}/api/queue", token="workflow-token")
            completed_status, completed_payload = client._get_json(f"{server.url}/api/completed", token="workflow-token")
            completed_open_status, completed_open_payload = client._post_json(
                f"{server.url}/api/completed/open",
                {"row_key": completed_payload["rows"][0]["row_key"], "target": "output_folder"},
                token="workflow-token",
            )
            failures_status, failures_payload = client._get_json(f"{server.url}/api/failures", token="workflow-token")
            failure_markers_status, failure_markers_payload = client._get_json(
                f"{server.url}/api/failures?source=markers",
                token="workflow-token",
            )
            audit_results_status, audit_results_payload = client._get_json(
                f"{server.url}/api/audit-results",
                token="workflow-token",
            )
            priority_audit_status, priority_audit_payload = client._get_json(
                f"{server.url}/api/audit-results?priority_only=true",
                token="workflow-token",
            )
            pending_status, pending_payload = client._get_json(
                f"{server.url}/api/pending-publish",
                token="workflow-token",
            )
            pending_recovery_plan_status, pending_recovery_plan_payload = client._post_json(
                f"{server.url}/api/pending-publish/recovery-plan",
                {"scope": "all"},
                token="workflow-token",
            )
            close_readiness_status, close_readiness_payload = client._get_json(
                f"{server.url}/api/backend/close-readiness",
                token="workflow-token",
            )
            maintenance_status, maintenance_payload = client._get_json(
                f"{server.url}/api/maintenance",
                token="workflow-token",
            )
            maintenance_progress_status, maintenance_progress_payload = client._get_json(
                f"{server.url}/api/maintenance/progress",
                token="workflow-token",
            )
            release_dry_run_status, release_dry_run_payload = client._post_json(
                f"{server.url}/api/maintenance/release-dry-run",
                {"destination_root": str(root / "Deploy"), "include_optional_tools": True},
                token="workflow-token",
            )
            backfill_dry_run_status, backfill_dry_run_payload = client._post_json(
                f"{server.url}/api/maintenance/completed-backfill-dry-run",
                {},
                token="workflow-token",
            )
            dependency_atlas_status, dependency_atlas_payload = client._post_json(
                f"{server.url}/api/maintenance/dependency-atlas",
                {"timeout_seconds": 99999, "min_overview_edge_count": 5},
                token="workflow-token",
            )
            (root / "docs/generated/dependency-atlas").mkdir(parents=True, exist_ok=True)
            dependency_atlas_open_status, dependency_atlas_open_payload = client._post_json(
                f"{server.url}/api/maintenance/dependency-atlas/open-folder",
                {},
                token="workflow-token",
            )
            schedule_status, schedule_payload = client._get_json(f"{server.url}/api/schedule", token="workflow-token")
            schedule_preview_status, schedule_preview_payload = client._post_json(
                f"{server.url}/api/schedule/preview",
                {"enabled": True, "day_windows": {"Monday": "9:00 AM - 10:00 AM"}},
                token="workflow-token",
            )
            schedule_save_status, schedule_save_payload = client._post_json(
                f"{server.url}/api/schedule/save",
                {
                    "enabled": True,
                    "day_windows": {"Monday": "9:00 AM - 10:00 AM"},
                    "confirm_save": True,
                },
                token="workflow-token",
            )
            denied_status, denied = client._post_json(
                f"{server.url}/api/rename/preview",
                {"paths": [str(media)], "mode": "tv", "season": "S02"},
            )
            rename_status, rename_payload = client._post_json(
                f"{server.url}/api/rename/preview",
                {"paths": [str(media)], "mode": "tv", "season": "S02", "use_pipeline_naming_preview": False},
                token="workflow-token",
            )
            rename_browse_status, rename_browse_payload = client._post_json(
                f"{server.url}/api/rename/browse",
                {"selection_mode": "files", "initial_path": str(media.parent)},
                token="workflow-token",
            )
            pipeline_browse_status, pipeline_browse_payload = client._post_json(
                f"{server.url}/api/pipeline/browse-file",
                {"selection_mode": "files", "initial_path": str(media.parent)},
                token="workflow-token",
            )
            settings_browse_status, settings_browse_payload = client._post_json(
                f"{server.url}/api/settings/browse-path",
                {"setting_key": "SourceTV", "selection_mode": "folder", "initial_path": str(root)},
                token="workflow-token",
            )
            rename_apply_status, rename_apply_payload = client._post_json(
                f"{server.url}/api/rename/apply",
                {
                    "paths": [str(media)],
                    "mode": "tv",
                    "season": "S02",
                    "use_pipeline_naming_preview": False,
                    "selected_sources": [str(media)],
                    "confirm_apply": True,
                },
                token="workflow-token",
            )
            validate_status, validate_payload = client._post_json(
                f"{server.url}/api/settings/validate",
                {"values": {"LocalBase": str(root / "Scratch"), "SourceTV": str(root / "TV")}},
                token="workflow-token",
            )
            settings_patch_status, settings_patch_payload = client._post_json(
                f"{server.url}/api/settings/preview-patch",
                {"changes": {"RoutingProfile": "plex_direct_play"}},
                token="workflow-token",
            )
            settings_save_patch_request = facade.settings_patch_request_with_review_confirmation(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}},
            )
            settings_save_patch_status, settings_save_patch_payload = client._post_json(
                f"{server.url}/api/settings/save-patch",
                {**settings_save_patch_request, "confirm_save": True},
                token="workflow-token",
            )
            settings_reload_status, settings_reload_payload = client._post_json(
                f"{server.url}/api/settings/reload",
                {},
                token="workflow-token",
            )
            diagnostics_open_status, diagnostics_open_payload = client._post_json(
                f"{server.url}/api/diagnostics/open",
                {"target": "run_logs"},
                token="workflow-token",
            )
            control_status, control_payload = client._post_json(
                f"{server.url}/api/pipeline/control",
                {"action": "stop"},
                token="workflow-token",
            )
            stop_flag_exists = resolved.stop_flag.exists()
            start_status, start_payload = client._post_json(
                f"{server.url}/api/pipeline/start",
                {"mode": "validate", "sleep_seconds": 3},
                token="workflow-token",
            )
            audit_status, audit_payload = client._post_json(
                f"{server.url}/api/audit/start",
                {"library_root": str(root / "Outsource"), "include_sidecars": True},
                token="workflow-token",
            )
            rerun_csv = root / "rerun.csv"
            rerun_csv.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            rerun_status, rerun_payload = client._post_json(
                f"{server.url}/api/rerun/start",
                {"csv_path": str(rerun_csv)},
                token="workflow-token",
            )
            command_history_status, command_history_payload = client._get_json(
                f"{server.url}/api/commands?limit=20",
                token="workflow-token",
            )
        finally:
            server.stop()

        Path(str(rename_apply_payload["data"]["undo_manifest"])).unlink(missing_ok=True)
        excluded = {"client", "server", "excluded"}
        _LOCAL_API_ROUTE_WORKFLOW_CACHE = SimpleNamespace(
            **{name: value for name, value in locals().items() if name not in excluded}
        )
        return _LOCAL_API_ROUTE_WORKFLOW_CACHE


class LocalApiHttpTestMixin:
    def _get_json(self, url: str, token: str | None = None, extra_headers: dict[str, str] | None = None) -> tuple[int, dict]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        headers = dict(extra_headers or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _post_json(self, url: str, payload: dict, token: str | None = None, extra_headers: dict[str, str] | None = None) -> tuple[int, dict]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        headers = {"Content-Type": "application/json", **dict(extra_headers or {})}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _options(self, url: str, extra_headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        request = Request(url, headers=dict(extra_headers or {}), method="OPTIONS")
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()

    def _get_raw(self, url: str, extra_headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        request = Request(url, headers=dict(extra_headers or {}))
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()



def served_webview_static_contract_bundle() -> SimpleNamespace:
    from urllib.request import urlopen

    with tempfile.TemporaryDirectory() as raw_root:
        root = Path(raw_root)
        assets_root = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static" / "assets"
        service = DummyFacadeService(root)
        facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
        server = LocalApiServer(facade, token="web-token", resolved_provider=lambda: _resolved(root))
        try:
            server.start()
            with urlopen(f"{server.url}/", timeout=5) as response:  # noqa: S310 - localhost test server
                html = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")
                set_cookie = response.headers.get("Set-Cookie", "")
            with urlopen(f"{server.url}/assets/app/lifecycle.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_lifecycle_js = response.read().decode("utf-8")
                app_lifecycle_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/topbar.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_topbar_js = response.read().decode("utf-8")
                app_topbar_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/closeReadiness.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_close_readiness_js = response.read().decode("utf-8")
                app_close_readiness_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/tauriLifecycle.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_tauri_lifecycle_js = response.read().decode("utf-8")
                app_tauri_lifecycle_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/refresh.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_refresh_js = response.read().decode("utf-8")
                app_refresh_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/home.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_home_js = response.read().decode("utf-8")
                app_home_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/homeReadiness.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_home_readiness_js = response.read().decode("utf-8")
                app_home_readiness_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/rowOpenActions.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_row_open_actions_js = response.read().decode("utf-8")
                app_row_open_actions_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app/layoutManager.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_layout_manager_js = response.read().decode("utf-8")
                app_layout_manager_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/app.js", timeout=5) as response:  # noqa: S310 - localhost test server
                app_parent_js = response.read().decode("utf-8")
                js_content_type = response.headers.get("Content-Type", "")
            js = "\n".join((
                app_lifecycle_js,
                app_topbar_js,
                app_close_readiness_js,
                app_tauri_lifecycle_js,
                app_refresh_js,
                app_home_js,
                app_home_readiness_js,
                app_row_open_actions_js,
                app_layout_manager_js,
                app_parent_js,
            ))
            with urlopen(f"{server.url}/assets/apiClient.js", timeout=5) as response:  # noqa: S310 - localhost test server
                api_client_js = response.read().decode("utf-8")
                api_client_content_type = response.headers.get("Content-Type", "")
            dom_helper_asset_paths = [
                "assets/dom/query.js",
                "assets/dom/text.js",
                "assets/dom/status.js",
                "assets/dom/filtering.js",
                "assets/dom/table.js",
            ]
            dom_helper_parts = []
            dom_helper_child_content_types = {}
            for asset_path in dom_helper_asset_paths:
                with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                    dom_helper_parts.append(response.read().decode("utf-8"))
                    dom_helper_child_content_types[asset_path] = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/domHelpers.js", timeout=5) as response:  # noqa: S310 - localhost test server
                dom_helper_parts.append(response.read().decode("utf-8"))
                dom_helpers_content_type = response.headers.get("Content-Type", "")
            dom_helpers_js = "\n".join(dom_helper_parts)
            with urlopen(f"{server.url}/assets/formatters.js", timeout=5) as response:  # noqa: S310 - localhost test server
                formatters_js = response.read().decode("utf-8")
                formatters_content_type = response.headers.get("Content-Type", "")
            command_history_parts = []
            command_history_content_type = ""
            for asset_path in COMMAND_HISTORY_ASSET_ORDER:
                with urlopen(f"{server.url}{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                    command_history_parts.append(response.read().decode("utf-8"))
                    if asset_path == "/assets/commandHistory.js":
                        command_history_content_type = response.headers.get("Content-Type", "")
            command_history_js = "\n".join(command_history_parts)
            with urlopen(f"{server.url}/assets/diagnosticsBridge.js", timeout=5) as response:  # noqa: S310 - localhost test server
                diagnostics_bridge_js = response.read().decode("utf-8")
                diagnostics_bridge_content_type = response.headers.get("Content-Type", "")
            completed_view_evidence_parts = []
            completed_view_evidence_child_content_types = {}
            for asset_path in (
                "/assets/completed/evidence/commands.js",
                "/assets/completed/evidence/filterScope.js",
                "/assets/completed/evidence/acceptance.js",
                "/assets/completed/evidence/routeAgreement.js",
            ):
                with urlopen(f"{server.url}{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_evidence_parts.append(response.read().decode("utf-8"))
                    completed_view_evidence_child_content_types[asset_path] = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completedView.evidence.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_evidence_parts.append(response.read().decode("utf-8"))
                completed_view_evidence_content_type = response.headers.get("Content-Type", "")
            completed_view_evidence_js = "\n".join(completed_view_evidence_parts)
            with urlopen(f"{server.url}/assets/completedView.proof.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_proof_js = response.read().decode("utf-8")
                completed_view_proof_content_type = response.headers.get("Content-Type", "")
            completed_view_review_asset_paths = [
                "assets/completed/review/integrity.js",
                "assets/completed/review/sizeReview.js",
                "assets/completed/review/healthSignals.js",
                "assets/completed/review/reviewRows.js",
                "assets/completed/review/investigationFilters.js",
            ]
            completed_view_review_parts = []
            completed_view_review_child_content_types = {}
            for asset_path in completed_view_review_asset_paths:
                with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_review_parts.append(response.read().decode("utf-8"))
                    completed_view_review_child_content_types[asset_path] = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completedView.review.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_review_parts.append(response.read().decode("utf-8"))
                completed_view_review_content_type = response.headers.get("Content-Type", "")
            completed_view_review_js = "\n".join(completed_view_review_parts)
            with urlopen(f"{server.url}/assets/completedView.diagnostics.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_diagnostics_js = response.read().decode("utf-8")
                completed_view_diagnostics_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completed/statusBoards.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_status_boards_js = response.read().decode("utf-8")
                completed_view_status_boards_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completed/openActions.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_open_actions_js = response.read().decode("utf-8")
                completed_view_open_actions_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completed/selection.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_selection_js = response.read().decode("utf-8")
                completed_view_selection_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completed/filters.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_filters_js = response.read().decode("utf-8")
                completed_view_filters_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completed/table.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_table_js = response.read().decode("utf-8")
                completed_view_table_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/completedView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                completed_view_js = response.read().decode("utf-8")
                completed_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queueView.summary.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_summary_js = response.read().decode("utf-8")
                queue_view_summary_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queueView.review.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_review_js = response.read().decode("utf-8")
                queue_view_review_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queueView.detail.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_detail_js = response.read().decode("utf-8")
                queue_view_detail_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queueView.launch.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_launch_js = response.read().decode("utf-8")
                queue_view_launch_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queue/selection.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_selection_js = response.read().decode("utf-8")
                queue_view_selection_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queue/openActions.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_open_actions_js = response.read().decode("utf-8")
                queue_view_open_actions_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queue/table.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_table_js = response.read().decode("utf-8")
                queue_view_table_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/queueView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                queue_view_js = response.read().decode("utf-8")
                queue_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublish/summary.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_summary_js = response.read().decode("utf-8")
                pending_publish_summary_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublish/details.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_details_js = response.read().decode("utf-8")
                pending_publish_details_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublish/filters.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_filters_js = response.read().decode("utf-8")
                pending_publish_filters_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublishView.recovery.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_recovery_js = response.read().decode("utf-8")
                pending_publish_recovery_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublishView.diagnostics.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_diagnostics_js = response.read().decode("utf-8")
                pending_publish_diagnostics_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublishView.drain.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_drain_js = response.read().decode("utf-8")
                pending_publish_drain_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublishView.confidence.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_confidence_js = response.read().decode("utf-8")
                pending_publish_confidence_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/pendingPublishView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                pending_publish_view_js = response.read().decode("utf-8")
                pending_publish_view_content_type = response.headers.get("Content-Type", "")
            pending_publish_view_js = "\n".join([
                pending_publish_summary_js,
                pending_publish_details_js,
                pending_publish_filters_js,
                pending_publish_recovery_js,
                pending_publish_diagnostics_js,
                pending_publish_drain_js,
                pending_publish_confidence_js,
                pending_publish_view_js,
            ])
            with urlopen(f"{server.url}/assets/crossPageContextView.conflict.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_conflict_js = response.read().decode("utf-8")
                cross_page_conflict_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/crossPageContextView.sample.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_sample_js = response.read().decode("utf-8")
                cross_page_sample_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/crossPageContextView.settings.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_settings_js = response.read().decode("utf-8")
                cross_page_settings_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.worksheet.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_sample_validation_worksheet_js = response.read().decode("utf-8")
                cross_page_sample_validation_worksheet_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.runbook.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_sample_validation_runbook_js = response.read().decode("utf-8")
                cross_page_sample_validation_runbook_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.records.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_sample_validation_records_js = response.read().decode("utf-8")
                cross_page_sample_validation_records_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_sample_validation_parent_js = response.read().decode("utf-8")
                cross_page_sample_validation_content_type = response.headers.get("Content-Type", "")
            cross_page_sample_validation_js = "\n".join((
                cross_page_sample_validation_worksheet_js,
                cross_page_sample_validation_runbook_js,
                cross_page_sample_validation_records_js,
                cross_page_sample_validation_parent_js,
            ))
            with urlopen(f"{server.url}/assets/crossPageContextView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                cross_page_context_view_js = response.read().decode("utf-8")
                cross_page_context_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/renameLabels.js", timeout=5) as response:  # noqa: S310 - localhost test server
                rename_labels_js = response.read().decode("utf-8")
                rename_labels_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/renameHistoryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                rename_history_view_js = response.read().decode("utf-8")
                rename_history_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/rename/preview.js", timeout=5) as response:  # noqa: S310 - localhost test server
                rename_preview_js = response.read().decode("utf-8")
                rename_preview_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/rename/applyReadiness.js", timeout=5) as response:  # noqa: S310 - localhost test server
                rename_apply_readiness_js = response.read().decode("utf-8")
                rename_apply_readiness_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/rename/applyResult.js", timeout=5) as response:  # noqa: S310 - localhost test server
                rename_apply_result_js = response.read().decode("utf-8")
                rename_apply_result_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/renameView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                rename_view_parent_js = response.read().decode("utf-8")
                rename_view_content_type = response.headers.get("Content-Type", "")
            rename_view_js = "\n".join((
                rename_preview_js,
                rename_apply_readiness_js,
                rename_apply_result_js,
                rename_view_parent_js,
            ))
            with urlopen(f"{server.url}/assets/settingsOverview.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_overview_js = response.read().decode("utf-8")
                settings_overview_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsCommandHistory.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_command_history_js = response.read().decode("utf-8")
                settings_command_history_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsMetadata.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_metadata_js = response.read().decode("utf-8")
                settings_metadata_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settings/metadataFields.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_metadata_fields_js = response.read().decode("utf-8")
                settings_metadata_fields_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settings/builderControls.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_builder_controls_js = response.read().decode("utf-8")
                settings_builder_controls_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.audio.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_audio_builder_js = response.read().decode("utf-8")
                settings_view_audio_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.video.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_video_builder_js = response.read().decode("utf-8")
                settings_view_video_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.subtitle.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_subtitle_builder_js = response.read().decode("utf-8")
                settings_view_subtitle_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.queue.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_queue_builder_js = response.read().decode("utf-8")
                settings_view_queue_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.runtime.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_runtime_builder_js = response.read().decode("utf-8")
                settings_view_runtime_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.file_safety.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_file_safety_builder_js = response.read().decode("utf-8")
                settings_view_file_safety_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.pending.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_pending_builder_js = response.read().decode("utf-8")
                settings_view_pending_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.builders.network.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_network_builder_js = response.read().decode("utf-8")
                settings_view_network_builder_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.rawTriage.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_raw_triage_js = response.read().decode("utf-8")
                settings_view_raw_triage_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.safetyLocks.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_safety_locks_js = response.read().decode("utf-8")
                settings_view_safety_locks_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settings/backendResult.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_backend_result_js = response.read().decode("utf-8")
                settings_backend_result_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settings/patchReview.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_patch_review_js = response.read().decode("utf-8")
                settings_patch_review_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settings/policyImpact.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_policy_impact_js = response.read().decode("utf-8")
                settings_policy_impact_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/settingsView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                settings_view_parent_js = response.read().decode("utf-8")
                settings_view_content_type = response.headers.get("Content-Type", "")
            settings_view_js = "\n".join((
                settings_metadata_fields_js,
                settings_builder_controls_js,
                settings_view_raw_triage_js,
                settings_view_safety_locks_js,
                settings_backend_result_js,
                settings_patch_review_js,
                settings_policy_impact_js,
                settings_view_parent_js,
            ))
            with urlopen(f"{server.url}/assets/networkView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                network_view_js = response.read().decode("utf-8")
                network_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/diagnosticsTailView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                diagnostics_tail_view_js = response.read().decode("utf-8")
                diagnostics_tail_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/diagnosticsStateSummaryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                diagnostics_state_summary_view_js = response.read().decode("utf-8")
                diagnostics_state_summary_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/diagnosticsView.activejobs.js", timeout=5) as response:  # noqa: S310 - localhost test server
                diagnostics_view_active_jobs_js = response.read().decode("utf-8")
                diagnostics_view_active_jobs_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/diagnosticsView.log.js", timeout=5) as response:  # noqa: S310 - localhost test server
                diagnostics_view_log_js = response.read().decode("utf-8")
                diagnostics_view_log_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/diagnosticsView.investigation.js", timeout=5) as response:  # noqa: S310 - localhost test server
                diagnostics_view_investigation_js = response.read().decode("utf-8")
                diagnostics_view_investigation_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/diagnosticsView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                diagnostics_view_parent_js = response.read().decode("utf-8")
                diagnostics_view_content_type = response.headers.get("Content-Type", "")
            diagnostics_view_js = "\n".join((
                diagnostics_view_active_jobs_js,
                diagnostics_view_log_js,
                diagnostics_view_investigation_js,
                diagnostics_view_parent_js,
            ))
            with urlopen(f"{server.url}/assets/reportsView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_view_js = response.read().decode("utf-8")
                reports_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/state.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_state_js = response.read().decode("utf-8")
                reports_state_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/shared.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_shared_js = response.read().decode("utf-8")
                reports_shared_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/shell.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_shell_js = response.read().decode("utf-8")
                reports_shell_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/failureModel.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_failure_model_js = response.read().decode("utf-8")
                reports_failure_model_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/failureCommands.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_failure_commands_js = response.read().decode("utf-8")
                reports_failure_commands_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/failureView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_failure_view_js = response.read().decode("utf-8")
                reports_failure_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/auditModel.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_audit_model_js = response.read().decode("utf-8")
                reports_audit_model_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/auditView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_audit_view_js = response.read().decode("utf-8")
                reports_audit_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/auditCommands.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_audit_commands_js = response.read().decode("utf-8")
                reports_audit_commands_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/reports/triage.js", timeout=5) as response:  # noqa: S310 - localhost test server
                reports_triage_js = response.read().decode("utf-8")
                reports_triage_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/scheduleView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                schedule_view_js = response.read().decode("utf-8")
                schedule_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/maintenanceView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                maintenance_view_js = response.read().decode("utf-8")
                maintenance_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/telemetryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                telemetry_view_js = response.read().decode("utf-8")
                telemetry_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/progressView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                progress_view_js = response.read().decode("utf-8")
                progress_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/launchReadinessView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                launch_readiness_view_js = response.read().decode("utf-8")
                launch_readiness_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/launchHistoryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                launch_history_view_js = response.read().decode("utf-8")
                launch_history_view_content_type = response.headers.get("Content-Type", "")
            launch_view_risk_asset_paths = [
                "assets/launch/risk/settingsAccess.js",
                "assets/launch/risk/mediaPolicyValues.js",
                "assets/launch/risk/riskRows.js",
                "assets/launch/risk/policyPatch.js",
                "assets/launch/risk/policyBoundary.js",
            ]
            launch_view_risk_parts = []
            launch_view_risk_child_content_types = {}
            for asset_path in launch_view_risk_asset_paths:
                with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_view_risk_parts.append(response.read().decode("utf-8"))
                    launch_view_risk_child_content_types[asset_path] = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/launchView.risk.js", timeout=5) as response:  # noqa: S310 - localhost test server
                launch_view_risk_parts.append(response.read().decode("utf-8"))
                launch_view_risk_content_type = response.headers.get("Content-Type", "")
            launch_view_risk_js = "\n".join(launch_view_risk_parts)
            with urlopen(f"{server.url}/assets/launchView.scope.js", timeout=5) as response:  # noqa: S310 - localhost test server
                launch_view_scope_js = response.read().decode("utf-8")
                launch_view_scope_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/launchView.realmedia.js", timeout=5) as response:  # noqa: S310 - localhost test server
                launch_view_realmedia_js = response.read().decode("utf-8")
                launch_view_realmedia_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/launchView.preflight.js", timeout=5) as response:  # noqa: S310 - localhost test server
                launch_view_preflight_js = response.read().decode("utf-8")
                launch_view_preflight_content_type = response.headers.get("Content-Type", "")
            launch_view_child_asset_paths = [
                "assets/launch/controllerState.js",
                "assets/launch/statusRender.js",
                "assets/launch/startRequest.js",
                "assets/launch/scopeControls.js",
                "assets/launch/commandButtons.js",
            ]
            launch_view_child_parts = []
            launch_view_child_content_types = {}
            for asset_path in launch_view_child_asset_paths:
                with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_view_child_parts.append(response.read().decode("utf-8"))
                    launch_view_child_content_types[asset_path] = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/launchView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                launch_view_parent_js = response.read().decode("utf-8")
                launch_view_content_type = response.headers.get("Content-Type", "")
            launch_view_js = "\n".join([*launch_view_child_parts, launch_view_parent_js])
            with urlopen(f"{server.url}/assets/contractView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                contract_view_js = response.read().decode("utf-8")
                contract_view_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css = response.read().decode("utf-8")
                css_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.tokens.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_tokens = response.read().decode("utf-8")
                css_tokens_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.theme.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_theme = response.read().decode("utf-8")
                css_theme_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.layout.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_layout = response.read().decode("utf-8")
                css_layout_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.components.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_components = response.read().decode("utf-8")
                css_components_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.pages.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_pages = response.read().decode("utf-8")
                css_pages_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.controls.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_controls = response.read().decode("utf-8")
                css_controls_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.layout-manager.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_layout_manager = response.read().decode("utf-8")
                css_layout_manager_content_type = response.headers.get("Content-Type", "")
            with urlopen(f"{server.url}/assets/styles.queue.css", timeout=5) as response:  # noqa: S310 - localhost test server
                css_queue = response.read().decode("utf-8")
                css_queue_content_type = response.headers.get("Content-Type", "")
        finally:
            server.stop()

    css_components = resolve_css_imports(assets_root / "styles.components.css", assets_root)
    css_pages = resolve_css_imports(assets_root / "styles.pages.css", assets_root)
    css_queue = resolve_css_imports(assets_root / "styles.queue.css", assets_root)
    css_split_assets = "\n".join(
        [
            css_layout,
            css_components,
            css_pages,
            css_controls,
            css_layout_manager,
            css_queue,
        ]
    )
    queue_view_parent_js = queue_view_js
    queue_view_js = "\n".join([
        queue_view_summary_js,
        queue_view_review_js,
        queue_view_detail_js,
        queue_view_launch_js,
        queue_view_selection_js,
        queue_view_open_actions_js,
        queue_view_table_js,
        queue_view_parent_js,
    ])

    excluded = {"raw_root", "root", "service", "facade", "server", "urlopen", "excluded"}
    return SimpleNamespace(**{name: value for name, value in locals().items() if name not in excluded})

def _read_queue_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "queueView.summary.js",
            "queueView.review.js",
            "queueView.detail.js",
            "queueView.launch.js",
            "queue/selection.js",
            "queue/openActions.js",
            "queue/table.js",
            "queueView.js",
        ]
    )


def _read_queue_file_overrides_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "queueView.js",
            "queue/fileOverrides.routePreview.js",
            "queue/fileOverrides.drawer.state.js",
            "queue/fileOverrides.drawer.form.js",
            "queue/fileOverrides.drawer.series.js",
            "queue/fileOverrides.drawer.tracks.js",
            "queue/fileOverrides.drawer.api.js",
            "queue/fileOverrides.drawer.focus.js",
            "queue/fileOverrides.drawer.js",
        ]
    )


def _read_diagnostics_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "diagnosticsView.activejobs.js",
            "diagnosticsView.log.js",
            "diagnosticsView.investigation.js",
            "diagnosticsView.js",
        ]
    )


def _read_command_history_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "commandHistory/formatters.js",
            "commandHistory/diagnostics.js",
            "commandHistory.js",
        ]
    )


def _read_dom_helpers_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "dom/query.js",
            "dom/text.js",
            "dom/status.js",
            "dom/filtering.js",
            "dom/table.js",
            "domHelpers.js",
        ]
    )


def _read_completed_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "completed/evidence/commands.js",
            "completed/evidence/filterScope.js",
            "completed/evidence/acceptance.js",
            "completed/evidence/routeAgreement.js",
            "completedView.evidence.js",
            "completedView.proof.js",
            "completed/review/integrity.js",
            "completed/review/sizeReview.js",
            "completed/review/healthSignals.js",
            "completed/review/reviewRows.js",
            "completed/review/investigationFilters.js",
            "completedView.review.js",
            "completedView.diagnostics.js",
            "completed/statusBoards.js",
            "completed/promotionCommands.js",
            "completed/openActions.js",
            "completed/selection.js",
            "completed/filters.js",
            "completed/table.js",
            "completedView.js",
        ]
    )


def _read_completed_evidence_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "completed/evidence/commands.js",
            "completed/evidence/filterScope.js",
            "completed/evidence/acceptance.js",
            "completed/evidence/routeAgreement.js",
            "completedView.evidence.js",
        ]
    )


def _read_completed_review_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "completed/review/integrity.js",
            "completed/review/sizeReview.js",
            "completed/review/healthSignals.js",
            "completed/review/reviewRows.js",
            "completed/review/investigationFilters.js",
            "completedView.review.js",
        ]
    )


def _read_pending_publish_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "pendingPublish/details.js",
            "pendingPublish/summary.js",
            "pendingPublishView.drain.js",
            "pendingPublishView.confidence.js",
            "pendingPublishView.recovery.js",
            "pendingPublishView.js",
        ]
    )


def _read_settings_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "settings/metadataFields.js",
            "settings/builderControls.js",
            "settings/backendResult.js",
            "settings/patchReview.js",
            "settings/policyImpact.js",
            "settingsView.rawTriage.js",
            "settingsView.js",
        ]
    )


def _read_launch_risk_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "launch/risk/settingsAccess.js",
            "launch/risk/mediaPolicyValues.js",
            "launch/risk/riskRows.js",
            "launch/risk/policyPatch.js",
            "launch/risk/policyBoundary.js",
            "launchView.risk.js",
        ]
    )


def _read_launch_view_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "launch/controllerState.js",
            "launch/statusRender.js",
            "launch/startRequest.js",
            "launch/scopeControls.js",
            "launch/commandButtons.js",
            "launchView.js",
        ]
    )


def _read_rename_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        (assets_root / name).read_text(encoding="utf-8")
        for name in [
            "rename/preview.js",
            "rename/applyReadiness.js",
            "rename/applyResult.js",
            "renameView.js",
        ]
    )


class DummyFacadeService(AppStateScheduleServiceMixin):
    def __init__(self, root: Path) -> None:
        self.app_root = root
        self.workspace_root = root
        self.app_state_path = root / "desktop_app_state.json"
        self.logger = logging.getLogger("test_application_facade")
        self.telemetry = TelemetrySnapshot(
            collected_at=datetime(2026, 5, 7, 21, 0, 0),
            cpu_percent=12.0,
            memory_percent=44.0,
            gpu_encoder_percent=0.0,
            gpu_name="NVIDIA GPU",
            gpu_count=1,
            gpu_rows=[{"index": "0", "name": "NVIDIA GPU", "encoder_percent": 0.0}],
            source="nvidia-smi",
        )
        self.snapshot: Snapshot | None = None
        self.opened_paths: list[Path] = []
        self.saved_config_calls: list[dict[str, object]] = []
        self.release_build_calls: list[dict[str, object]] = []
        self.dependency_atlas_calls: list[dict[str, object]] = []
        self._completed_history_cache_key: str | None = None
        self._completed_history_cache_limit_key = ""
        self._completed_history_cached_at = 0.0
        self._completed_history_manifest_mtime = 0.0
        self._completed_history_records = []

    def build_snapshot(self, resolved: ResolvedPaths, audit_root: str) -> Snapshot:
        _ = audit_root
        if self.snapshot is not None:
            return self.snapshot
        return Snapshot(
            resolved=resolved,
            current_activity="Current activity: Ready.",
            status_summary="Status OK",
            log_tail="log line",
            progress={
                "ProgressVersion": 2,
                "Status": "Processing",
                "CurrentQueueIndex": 2,
                "CurrentQueueTotal": 5,
                "TotalProcessed": 10,
                "Encoded": 3,
                "Remuxed": 7,
                "Failed": 1,
                "Movies": 4,
                "TVEpisodes": 6,
            },
            audit_progress=None,
            latest_failure_report=resolved.workspace_root / "failures.txt",
            latest_failure_json=resolved.workspace_root / "failures.json",
            latest_audit_csv=None,
            latest_priority_csv=None,
            pipeline_events=[
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "event-1",
                    "event_type": "job_started",
                    "timestamp": "2026-05-07T21:00:00-04:00",
                    "created_at": "2026-05-07T21:00:00-04:00",
                    "data": {"display_name": "Movie.mkv"},
                }
            ],
        )

    def get_cached_telemetry(self) -> TelemetrySnapshot:
        return self.telemetry

    def format_diagnostics_error_summary(self, snapshot: Snapshot) -> str:
        _ = snapshot
        return "No recent pipeline errors found."

    def format_diagnostics_event_summary(self, snapshot: Snapshot) -> str:
        return "\n".join(str(event.get("event_type") or "") for event in snapshot.pipeline_events)

    def _format_active_job_summary(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["pipeline once: active (pid 1234) launched 2026-05-07T21:00:00-04:00"]

    def launch_log_summary(self) -> str:
        return "stdout: run.stdout.log | stderr: run.stderr.log"

    def validate_config_values(self, values: dict) -> tuple[list[str], list[str]]:
        warnings = ["LocalBase shares a volume with SourceTV."] if values.get("LocalBase") and values.get("SourceTV") else []
        return [], warnings

    def serialize_psd1_document(self, values: dict) -> str:
        lines = ["@{"]
        for key, value in sorted(values.items()):
            escaped = str(value).replace("'", "''")
            lines.append(f"    {key} = '{escaped}'")
        lines.extend(["}", ""])
        return "\n".join(lines)

    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult:
        self.saved_config_calls.append(
            {
                "output_path": output_path,
                "document_text": document_text,
                "create_backup": create_backup,
                "config_values": dict(config_values or {}),
                "powershell_host": powershell_host,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = output_path.parent / "ConfigBackups" / f"{output_path.stem}.backup{output_path.suffix}" if create_backup and output_path.exists() else None
        if backup_path is not None:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        output_path.write_text(document_text, encoding="utf-8")
        return ConfigSaveResult(output_path=output_path, backup_path=backup_path)

    def list_config_profiles(self, config_path: Path) -> list[str]:
        _ = config_path
        return ["Default", "DirectPlay"]

    def check_environment_health(self, resolved: ResolvedPaths) -> list[tuple[str, bool, str]]:
        return [
            ("PowerShell (pwsh)", bool(resolved.powershell_host), str(resolved.powershell_host or "")),
            ("ffmpeg", True, str(self.workspace_root / "Pipeline" / "Tools" / "ffmpeg" / "bin" / "ffmpeg.exe")),
            ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable"),
        ]

    def latest_failure_json(self, resolved: ResolvedPaths) -> Path | None:
        path = resolved.workspace_root / "failures.json"
        return path if path.exists() else None

    def latest_failure_report(self, resolved: ResolvedPaths) -> Path | None:
        path = resolved.workspace_root / "failures.txt"
        return path if path.exists() else None

    def load_failure_records(self, json_path: Path) -> list[FailureRecord]:
        raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise RuntimeError("failure json must be a list")
        return [FailureRecord(source_json=Path(json_path), payload=item) for item in raw if isinstance(item, dict)]

    def load_failure_marker_records(self, resolved: ResolvedPaths) -> list[FailureRecord]:
        markers_path = resolved.failed_markers_path
        if not markers_path or not markers_path.exists():
            return []
        key_map = {
            "source_full_path": "SourcePath",
            "stage": "Stage",
            "reason": "Reason",
            "classification": "Classification",
            "error_code": "ErrorCode",
            "artifact_path": "ArtifactPath",
            "recorded_at": "RecordedAt",
            "suggested_action": "SuggestedAction",
            "suggested_rename": "SuggestedRename",
            "repro_path": "ReproPath",
            "retry_count": "RetryCount",
            "retry_limit": "RetryLimit",
            "escalated": "Escalated",
        }
        records: list[FailureRecord] = []
        for marker_file in sorted(markers_path.glob("*.json")):
            raw = json.loads(marker_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                records.append(FailureRecord(source_json=marker_file, payload={key_map.get(str(key), str(key)): value for key, value in raw.items()}))
        return records

    def latest_audit_csv(self, resolved: ResolvedPaths, priority_only: bool) -> Path | None:
        candidates = (
            ["audit_priority_latest.csv", "audit_summary_latest.csv"]
            if priority_only
            else ["audit_summary_latest.csv", "audit_priority_latest.csv"]
        )
        for name in candidates:
            path = resolved.workspace_root / name
            if path.exists():
                return path
        return None

    def load_audit_records(self, csv_path: Path) -> list[AuditRecord]:
        with Path(csv_path).open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            return [
                AuditRecord(source_csv=Path(csv_path), row={str(key): str(value or "") for key, value in row.items() if key is not None})
                for row in reader
            ]

    def build_release_package(self, **kwargs: object) -> dict[str, object]:
        self.release_build_calls.append(dict(kwargs))
        destination = Path(str(kwargs.get("destination_root") or self.workspace_root.parent / "MediaPipeline_Deployable_DryRun"))
        dry_run = bool(kwargs.get("dry_run", True))
        stdout = "\n".join(
            [
                f"Source      : {self.workspace_root}",
                f"Destination : {destination}",
                "Copy files  : 12",
                "Exclude     : 3",
                "",
                "Dry run only. No files copied." if dry_run else "Release build complete.",
            ]
        )
        return {
            "success": True,
            "timed_out": False,
            "returncode": 0,
            "command": "pwsh -File scripts\\ops\\release\\metadata\\build.ps1" + (" -DryRun" if dry_run else ""),
            "stdout": stdout,
            "stderr": "",
            "destination_root": str(destination),
            "manifest_path": str(destination / "release_manifest.json"),
            "manifest_exists": not dry_run,
            "zip_path": str(destination) + ".zip",
            "zip_exists": (not dry_run) and bool(kwargs.get("zip_package", True)),
            "dry_run": dry_run,
            "elapsed_seconds": 1.25,
            "manifest": {"schema_version": "mediapipeline_release_manifest.v1"} if not dry_run else None,
        }

    def generate_dependency_atlas(self, **kwargs: object) -> dict[str, object]:
        self.dependency_atlas_calls.append(dict(kwargs))
        atlas_dir = self.workspace_root / "docs/generated/dependency-atlas"
        assets_dir = atlas_dir / "assets"
        return {
            "success": True,
            "timed_out": False,
            "returncode": 0,
            "command": "python scripts\\dev\\generate_dependency_atlas.py",
            "stdout": "\n".join(
                [
                    "Graphviz dot: C:\\Program Files\\Graphviz\\bin\\dot.exe",
                    "Modules: 377",
                    "Module edges: 839",
                    "Domains: 47",
                    "Domain edges: 170",
                    "Detail diagrams: 46",
                    "HTML local links checked: 144",
                    f"Open: {atlas_dir / 'dependency-atlas.html'}",
                ]
            ),
            "stderr": "",
            "elapsed_seconds": 2.5,
            "atlas_html": str(atlas_dir / "dependency-atlas.html"),
            "atlas_png": str(atlas_dir / "dependency-atlas.png"),
            "atlas_svg": str(atlas_dir / "dependency-atlas.svg"),
            "assets_dir": str(assets_dir),
            "summary_csv": str(assets_dir / "dependency_summary.csv"),
            "domain_edges_csv": str(assets_dir / "dependency_edges.csv"),
            "module_edges_csv": str(assets_dir / "dependency_module_edges.csv"),
            "html_exists": True,
            "png_exists": True,
            "svg_exists": True,
            "summary_csv_exists": True,
            "domain_edges_csv_exists": True,
            "module_edges_csv_exists": True,
        }

    def open_path(self, path: Path | str | None) -> None:
        if path is None:
            raise FileNotFoundError("Path does not exist: <none>")
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {target}")
        self.opened_paths.append(target)


class DummyProc:
    def __init__(self, pid: int = 24680) -> None:
        self.pid = pid


class DummyWorkflowFacadeService(DummyFacadeService, QueueServiceMixin, RenameServiceMixin, PendingPublishServiceMixin, CompletedJobsServiceMixin, ProcessLifecycleServiceMixin):
    def prepare_pipeline_runtime_for_launch(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["runtime ready"]

    def prepare_pipeline_control_flags_for_launch(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["control flags ready"]

    def start_pipeline(
        self,
        resolved: ResolvedPaths,
        mode: str,
        show_config: bool,
        sleep_seconds: int,
        extra_args: str,
        show_console: bool,
        single_file: str | None = None,
        extra_argv: list[str] | tuple[str, ...] | None = None,
    ) -> DummyProc:
        self.started_pipeline = {
            "resolved": resolved,
            "mode": mode,
            "show_config": show_config,
            "sleep_seconds": sleep_seconds,
            "extra_args": extra_args,
            "extra_argv": [str(item) for item in (extra_argv or [])],
            "show_console": show_console,
            "single_file": single_file,
        }
        return DummyProc()

    def prepare_audit_runtime_for_launch(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["audit runtime ready"]

    def start_audit(
        self,
        resolved: ResolvedPaths,
        library_root: str,
        include_sidecars: bool,
        show_console: bool,
    ) -> DummyProc:
        self.started_audit = {
            "resolved": resolved,
            "library_root": library_root,
            "include_sidecars": include_sidecars,
            "show_console": show_console,
        }
        return DummyProc(24681)

    def start_rerun_csv(
        self,
        resolved: ResolvedPaths,
        csv_path: Path,
        *,
        dry_run: bool,
        plan_only: bool = False,
        stage_mode: str,
        original_mode: str,
        return_mode: str,
        show_console: bool,
    ) -> DummyProc:
        self.started_rerun = {
            "resolved": resolved,
            "csv_path": csv_path,
            "dry_run": dry_run,
            "plan_only": plan_only,
            "stage_mode": stage_mode,
            "original_mode": original_mode,
            "return_mode": return_mode,
            "show_console": show_console,
        }
        return DummyProc(24682)


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
            active_jobs_path=root / "State" / "ActiveJobs",
            pause_flag=root / "State" / "Pipeline" / "pipeline_pause.flag",
            stop_flag=root / "State" / "Pipeline" / "pipeline_stop.flag",
            rescan_flag=root / "State" / "Pipeline" / "pipeline_rescan.flag",
            config_data={"NetworkRole": "standalone"},
    )

if __name__ == "__main__":
    unittest.main()
