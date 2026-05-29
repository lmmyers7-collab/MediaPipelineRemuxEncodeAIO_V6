from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .api import LocalApiServer
from .application import MediaPipelineApplicationFacade
from .config_keys import KEY_LOCAL_BASE, KEY_PRIORITY_MARKERS, KEY_SOURCE_MOVIES, KEY_SOURCE_TV
from .models import ResolvedPaths
from app.storage.state_migration import app_state_path_for_state_root
from .services import DesktopAppService


EXPECTED_READINESS_AREAS = {
    "Routing / size guard",
    "Container / subtitle preservation",
    "Subtitle language routing",
    "TX3G / mov_text SRT",
    "BDPGS OCR to SRT",
    "ASS / SSA preservation",
    "Audio language / default track",
    "Audio passthrough / channels",
    "Publish / recovery safety",
    "Source preservation",
}


def _get_text(url: str, token: str | None = None) -> tuple[int, str, str]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost smoke server
            return response.status, response.read().decode("utf-8"), response.headers.get("Content-Type", "")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), exc.headers.get("Content-Type", "")


def _get_json(url: str, token: str | None = None) -> tuple[int, dict[str, Any]]:
    status, body, _content_type = _get_text(url, token)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} did not return JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} returned a non-object JSON payload.")
    return status, payload


def _path_from_config(config: dict[str, Any], key: str) -> Path | None:
    value = config.get(key)
    if value is None or str(value).strip() == "":
        return None
    return Path(str(value))


def _resolved_from_config(
    service: DesktopAppService,
    *,
    pipeline_path: Path,
    config_path: Path,
    powershell_host: str | None,
    config: dict[str, Any],
) -> ResolvedPaths:
    resolved = ResolvedPaths(
        app_root=service.app_root,
        workspace_root=service.workspace_root,
        pipeline_path=pipeline_path,
        config_path=config_path,
        audit_script_path=service.default_audit_script_path(),
        rerun_script_path=service.default_rerun_script_path(),
        powershell_host=powershell_host,
        config_data=dict(config),
    )
    local_base = _path_from_config(config, KEY_LOCAL_BASE)
    if local_base is not None:
        state_root = service._state_root_for_local_base(local_base)
        resolved.local_base = local_base
        resolved.state_root = state_root
        resolved.active_jobs_path = state_root / "ActiveJobs"
        resolved.app_state_path = app_state_path_for_state_root(state_root)
        resolved.log_file = local_base / "pipeline_debug.log"
        resolved.progress_file = state_root / "Progress" / "pipeline_progress.json"
        resolved.event_file = state_root / "Progress" / "pipeline_events.jsonl"
        resolved.pause_flag = state_root / "Pipeline" / "pipeline_pause.flag"
        resolved.stop_flag = state_root / "Pipeline" / "pipeline_stop.flag"
        resolved.rescan_flag = state_root / "Pipeline" / "pipeline_rescan.flag"
        resolved.failed_reports_path = state_root / "Failures" / "Reports"
        resolved.failed_markers_path = state_root / "Failures" / "Markers"
        resolved.pending_push_path = state_root / "PendingServerPush"
        resolved.audit_reports_path = local_base / "AuditReports"
        resolved.queue_snapshot_path = state_root / "Progress" / "queue_snapshot.json"
        resolved.completed_manifest_path = state_root / "Completed" / "completed_jobs.jsonl"
    resolved.source_movies = _path_from_config(config, KEY_SOURCE_MOVIES)
    resolved.source_tv = _path_from_config(config, KEY_SOURCE_TV)
    if resolved.audit_reports_path is None:
        resolved.audit_reports_path = service.app_root / "AuditReports"
    markers = config.get(KEY_PRIORITY_MARKERS)
    if isinstance(markers, list) and markers:
        resolved.priority_markers = [str(item) for item in markers if str(item).strip()]
    return resolved


def _require_fragment(body: str, fragment: str, label: str) -> None:
    if fragment not in body:
        raise RuntimeError(f"Missing WebView fragment for {label}: {fragment}")


def _require_status(status: int, route: str) -> None:
    if status != 200:
        raise RuntimeError(f"{route} returned HTTP {status}; expected 200.")


def _validate_static_assets(base_url: str) -> None:
    html_status, html, _html_type = _get_text(f"{base_url}/")
    _require_status(html_status, "/")
    for fragment, label in (
        ('id="settings-backend-media-policy-status"', "settings policy status"),
        ('id="settings-backend-media-policy-rows"', "settings policy rows"),
        ('id="settings-backend-result-status"', "settings backend result status"),
        ('id="settings-backend-result-rows"', "settings backend result rows"),
        ('id="launch-settings-risk-rows"', "launch risk rows"),
        ('data-page-panel="settings"', "settings panel"),
        ('data-page-panel="launch"', "launch panel"),
    ):
        _require_fragment(html, fragment, label)

    settings_status, settings_js, _settings_type = _get_text(f"{base_url}/assets/settingsView.js")
    _require_status(settings_status, "/assets/settingsView.js")
    for fragment, label in (
        ("function settingsBackendMediaPolicyReadiness", "settings readiness source"),
        ("function renderSettingsBackendMediaPolicyReadiness", "settings readiness renderer"),
        ("function settingsProfileSummaryLines", "settings profile summary renderer"),
        ("Backend media-policy readiness:", "settings readiness heading"),
        ("function settingsBackendResultRows", "settings backend result handoff rows"),
        ("function renderSettingsBackendResultFromEntries", "settings backend result renderer"),
        ("Patch JSON changed after the last preview. Preview again before saving.", "settings stale preview guidance"),
        ("Save Patch is the only persistence command", "settings save persistence boundary"),
        ("Preview/Save remains backend-owned", "settings save ownership boundary"),
    ):
        _require_fragment(settings_js, fragment, label)

    overview_status, overview_js, _overview_type = _get_text(f"{base_url}/assets/settingsOverview.js")
    _require_status(overview_status, "/assets/settingsOverview.js")
    for fragment, label in (
        ("function settingsMediaPolicyReadinessLine", "settings overview readiness line"),
        ("settings.media_policy_readiness", "settings overview backend readiness access"),
    ):
        _require_fragment(overview_js, fragment, label)

    launch_status, launch_js, _launch_type = _get_text(f"{base_url}/assets/launchView.risk.js")
    _require_status(launch_status, "/assets/launchView.risk.js")
    for fragment, label in (
        ("Backend media-policy readiness", "launch readiness handoff"),
        ("media_policy_readiness", "launch backend readiness access"),
        ("Resolve blocked saved media-policy rows before launching unattended work.", "launch blocked guidance"),
    ):
        _require_fragment(launch_js, fragment, label)

    cross_status, cross_js, _cross_type = _get_text(f"{base_url}/assets/crossPageContextView.settings.js")
    _require_status(cross_status, "/assets/crossPageContextView.settings.js")
    for fragment, label in (
        ("Backend media-policy readiness", "home cross-page readiness handoff"),
        ("media readiness=", "home readiness compact summary"),
    ):
        _require_fragment(cross_js, fragment, label)


def _validate_settings_workspace(base_url: str, token: str, config_path: Path) -> dict[str, Any]:
    settings_status, settings = _get_json(f"{base_url}/api/settings/workspace", token)
    _require_status(settings_status, "/api/settings/workspace")
    if settings.get("schema_version") != "desktop_settings_workspace.v1":
        raise RuntimeError("Settings workspace schema mismatch.")
    if Path(str(settings.get("config_path") or "")) != config_path:
        raise RuntimeError("Settings workspace config_path does not match the smoke config.")
    readiness = settings.get("media_policy_readiness")
    if not isinstance(readiness, dict):
        raise RuntimeError("Settings workspace is missing media_policy_readiness.")
    if readiness.get("schema_version") != "settings_media_policy_readiness.v1":
        raise RuntimeError("Media-policy readiness schema mismatch.")
    if readiness.get("read_only") is not True:
        raise RuntimeError("Media-policy readiness must be read-only.")
    rows = readiness.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Media-policy readiness did not return any rows.")
    areas = {str(row.get("area") or "") for row in rows if isinstance(row, dict)}
    missing = sorted(EXPECTED_READINESS_AREAS - areas)
    if missing:
        raise RuntimeError(f"Media-policy readiness is missing area(s): {', '.join(missing)}")
    counts = readiness.get("counts")
    if not isinstance(counts, dict):
        raise RuntimeError("Media-policy readiness counts are missing.")
    total = sum(int(counts.get(key, 0) or 0) for key in ("coherent", "review", "blocked"))
    if total != len(rows):
        raise RuntimeError(f"Media-policy readiness count mismatch: counts={total}; rows={len(rows)}.")
    if str(readiness.get("operator_status") or "") not in {"Ready", "Review", "Blocked review"}:
        raise RuntimeError("Media-policy readiness returned an unknown operator_status.")
    config = settings.get("config")
    if not isinstance(config, dict) or not config:
        raise RuntimeError("Settings workspace returned an empty redacted config.")
    if "WorkerAuthToken" in config and config["WorkerAuthToken"] not in {"", "<redacted>"}:
        raise RuntimeError("Settings workspace did not redact WorkerAuthToken.")
    if "CoordinatorAuthToken" in config and config["CoordinatorAuthToken"] not in {"", "<redacted>"}:
        raise RuntimeError("Settings workspace did not redact CoordinatorAuthToken.")
    profile_summary = settings.get("profile_summary")
    if not isinstance(profile_summary, dict):
        raise RuntimeError("Settings workspace is missing profile_summary.")
    if profile_summary.get("schema_version") != "desktop_settings_profile_summary.v1":
        raise RuntimeError("Settings profile summary schema mismatch.")
    if profile_summary.get("read_only") is not True:
        raise RuntimeError("Settings profile summary must be read-only.")
    operations = profile_summary.get("webview_profile_operations")
    if not isinstance(operations, dict) or operations.get("save_default_profile") is not False or operations.get("load_profile") is not False:
        raise RuntimeError("Settings profile summary exposed unsupported profile mutation operations.")
    return settings


def run_smoke(*, app_root: Path, config_path: Path | None = None, pipeline_path: Path | None = None) -> dict[str, Any]:
    app_root = app_root.resolve()
    service = DesktopAppService(app_root)
    selected_pipeline = (pipeline_path or service.default_pipeline_path()).resolve()
    selected_config = (config_path or service.default_config_path()).resolve()
    powershell_host = service.resolve_powershell_host()
    config = service.load_config_data(selected_config, powershell_host)
    if not config:
        raise RuntimeError(f"Live config did not load any keys: {selected_config}")
    resolved = _resolved_from_config(
        service,
        pipeline_path=selected_pipeline,
        config_path=selected_config,
        powershell_host=powershell_host,
        config=config,
    )
    facade = MediaPipelineApplicationFacade(service, app_version="v5-live-smoke")
    server = LocalApiServer(
        facade,
        token="live-config-smoke-token",
        resolved_provider=lambda: resolved,
        audit_root_provider=lambda: str(resolved.audit_reports_path or ""),
    )
    try:
        server.start()
        _validate_static_assets(server.url)
        settings = _validate_settings_workspace(server.url, server.token, selected_config)
    finally:
        server.stop()

    readiness = settings["media_policy_readiness"]
    return {
        "schema_version": "webview_settings_live_config_smoke.v1",
        "config_path": str(selected_config),
        "pipeline_path": str(selected_pipeline),
        "key_count": int(settings.get("key_count") or len(config)),
        "operator_status": str(readiness.get("operator_status") or ""),
        "counts": readiness.get("counts") or {},
        "review_rows": [
            {
                "area": str(row.get("area") or ""),
                "posture": str(row.get("posture") or ""),
                "operator_check": str(row.get("operator_check") or ""),
            }
            for row in readiness.get("rows", [])
            if isinstance(row, dict) and str(row.get("posture") or "").casefold() != "coherent"
        ],
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print("WebView settings/launch live-config smoke passed.")
    print(f"Config   : {summary['config_path']}")
    print(f"Pipeline : {summary['pipeline_path']}")
    print(f"Keys     : {summary['key_count']}")
    print(f"Readiness: {summary['operator_status']} {json.dumps(summary['counts'], sort_keys=True)}")
    review_rows = summary.get("review_rows")
    if isinstance(review_rows, list) and review_rows:
        print("Rows needing operator attention:")
        for row in review_rows[:8]:
            print(f"- {row['area']} [{row['posture']}]: {row['operator_check']}")
        if len(review_rows) > 8:
            print(f"- +{len(review_rows) - 8} more row(s).")
    else:
        print("Rows needing operator attention: none")
    print("Boundary: read-only HTTP/static/settings checks only; no launch, save, publish, rename, or media processing was requested.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test WebView Settings/Launch handoff using the current saved config.")
    parser.add_argument("--app-root", default="", help="DesktopApp root. Defaults to the bundled DesktopApp folder.")
    parser.add_argument("--config-path", default="", help="Optional config PSD1 path. Defaults to the bundled live config.")
    parser.add_argument("--pipeline-path", default="", help="Optional pipeline script path. Defaults to the bundled pipeline script.")
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    return parser.parse_args(argv)


def default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_smoke(
        app_root=Path(args.app_root).expanduser() if args.app_root else default_app_root(),
        config_path=Path(args.config_path).expanduser() if args.config_path else None,
        pipeline_path=Path(args.pipeline_path).expanduser() if args.pipeline_path else None,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
