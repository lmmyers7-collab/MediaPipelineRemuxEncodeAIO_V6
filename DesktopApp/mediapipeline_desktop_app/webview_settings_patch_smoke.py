from __future__ import annotations

import argparse
import json
import tempfile
import threading
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .api import LocalApiServer
from .application import MediaPipelineApplicationFacade
from .config_keys import KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT, KEY_MAX_ENCODE_GROWTH_PERCENT
from .models import ResolvedPaths
from .services import DesktopAppService
from .webview_settings_live_smoke import (
    _resolved_from_config,
    _require_fragment,
    _require_status,
    _validate_static_assets,
)


PATCH_CHANGES = {
    KEY_MAX_ENCODE_GROWTH_PERCENT: 6,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT: 16,
}


def _ps_quote(path: Path) -> str:
    return str(path).replace("'", "''")


def _post_json(url: str, payload: dict[str, Any], token: str) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - localhost smoke server
            data = response.read().decode("utf-8")
            status = response.status
    except HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} did not return JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{url} returned a non-object JSON payload.")
    return status, parsed


def _get_json(url: str, token: str) -> tuple[int, dict[str, Any]]:
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - localhost smoke server
            data = response.read().decode("utf-8")
            status = response.status
    except HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} did not return JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{url} returned a non-object JSON payload.")
    return status, parsed


def _write_temp_config(root: Path) -> Path:
    local_base = root / "Scratch"
    source_movies = root / "Movies"
    source_tv = root / "TV"
    outsource = root / "Outsource"
    for directory in (local_base, source_movies, source_tv, outsource):
        directory.mkdir(parents=True, exist_ok=True)

    config_path = root / "MediaPipeline_config.psd1"
    config_path.write_text(
        "\n".join(
            [
                "@{",
                f"  LocalBase = '{_ps_quote(local_base)}'",
                f"  SourceMovies = '{_ps_quote(source_movies)}'",
                f"  SourceTV = '{_ps_quote(source_tv)}'",
                f"  Outsource = '{_ps_quote(outsource)}'",
                "  RoutingProfile = 'plex_direct_stream'",
                "  SizeGuardMode = 'advisory'",
                "  VideoCodec = 'hevc_nvenc'",
                "  VideoPreset = 'p5'",
                "  VideoQuality = 23",
                "  OutputContainer = 'mkv'",
                "  EncodeThresholdGB = 8",
                "  TVEncodeThresholdGB = 4",
                "  MinFreeSpaceGB = 20",
                "  AllowH264RemuxIfPlexCompatible = $true",
                "  MaxEncodeGrowthPercent = 5",
                "  CompatibilityEncodeGrowthPercent = 15",
                "  RemuxSafeVideoCodecs = @('h264', 'hevc')",
                "  SubKeepLanguages = @('eng', 'und')",
                "  Tx3gExtractLanguages = @('eng', 'und')",
                "  BdpgsExtractLanguages = @('eng', 'und')",
                "  ConvertTx3gToSrt = $true",
                "  DropTx3gAfterConversion = $false",
                "  ConvertBdpgsToSrt = $true",
                "  DropBdpgsAfterConversion = $false",
                "  DropAssAfterConversion = $false",
                "  StripFormatting = $true",
                "  RemoveKaraoke = $true",
                "  KeepSignsAndSongs = $true",
                "  PreferredDefaultAudioLanguages = @('english')",
                "  AudioPassthroughProfile = 'plex_balanced'",
                "  CompatibleAudioCodecs = @('aac', 'ac3', 'eac3')",
                "  AudioDownmixMode = 'max_channels'",
                "  AudioMaxChannels = 6",
                "  AllowNoAudio = $false",
                "  DeferredPublish = $true",
                "  CleanupRemoteStaging = $false",
                "  SkipStabilityCheck = $false",
                "  EnableIntegrityCheck = $true",
                "  MergeThresholdMs = 700",
                "  FFmpegEncodeTimeoutSeconds = 7200",
                "  FFmpegRemuxTimeoutSeconds = 3600",
                "  SubtitleExtractTimeoutSeconds = 900",
                "  SubtitleProbeTimeoutSeconds = 120",
                "  BdpgsOcrTimeoutSeconds = 3600",
                "  VobSubOcrTimeoutSeconds = 1800",
                "  SourceScanIntervalSeconds = 60",
                "  ProcessedIndexRefreshSeconds = 300",
                "  SourceScanTimeoutSeconds = 120",
                "  IndexScanTimeoutSeconds = 120",
                "  CleanupScanTimeoutSeconds = 120",
                "  CleanupStaleAgeHours = 72",
                "  TransientFailureRetryLimit = 3",
                "  RobocopyTimeoutSeconds = 14400",
                "  PriorityMarkers = @('!', '[NOW]')",
                "  ValidExtensions = @('.mkv', '.mp4', '.avi')",
                "  RobocopyFlags = @('/E', '/R:2', '/W:5')",
                "  OutsourceMinFreeSpaceGB = 20",
                "  OutputSizeMultiplier = 1.15",
                "  WorkerAuthToken = 'worker-secret'",
                "  CoordinatorAuthToken = ''",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


class _SmokeResolvedState:
    def __init__(
        self,
        service: DesktopAppService,
        *,
        pipeline_path: Path,
        config_path: Path,
        powershell_host: str | None,
    ) -> None:
        self.service = service
        self.pipeline_path = pipeline_path
        self.config_path = config_path
        self.powershell_host = powershell_host
        self._lock = threading.Lock()
        self._resolved = self._resolve()

    def _resolve(self) -> ResolvedPaths:
        config = self.service.load_config_data(self.config_path, self.powershell_host)
        return _resolved_from_config(
            self.service,
            pipeline_path=self.pipeline_path,
            config_path=self.config_path,
            powershell_host=self.powershell_host,
            config=config,
        )

    def get(self) -> ResolvedPaths:
        with self._lock:
            return self._resolved

    def reload(self) -> ResolvedPaths:
        resolved = self._resolve()
        with self._lock:
            self._resolved = resolved
        return resolved


def _validate_patch_static_assets(base_url: str) -> None:
    _validate_static_assets(base_url)
    status, settings_js = _get_json_text(f"{base_url}/assets/settingsView.js")
    _require_status(status, "/assets/settingsView.js")
    for fragment, label in (
        ("lastSettingsPatchPreviewEvidence", "preview evidence tracking"),
        ("lastSettingsPatchSaveEvidence", "save evidence tracking"),
        ("function settingsPatchSignature", "stable patch signature"),
        ("function settingsBackendResultRows", "backend result rows"),
        ("function settingsBackendResultDetailLines", "backend result detail lines"),
        ("function renderSettingsBackendResultFromEntries", "backend result renderer"),
        ("settings-backend-result-rows", "backend result table target"),
        ("settings-backend-result-detail", "backend result detail target"),
        ("Save Patch was cancelled before any backend save command was sent.", "cancelled save operator feedback"),
        ("The last save was for different JSON. Do not treat it as proof for the current patch.", "stale save guidance"),
        ("Evidence matches current JSON:", "backend result signature detail"),
    ):
        _require_fragment(settings_js, fragment, label)


def _get_json_text(url: str) -> tuple[int, str]:
    request = Request(url)
    with urlopen(request, timeout=10) as response:  # noqa: S310 - localhost smoke server
        return response.status, response.read().decode("utf-8")


def _require_command_result(payload: dict[str, Any], *, command: str, ok: bool) -> None:
    if payload.get("schema_version") != "desktop_command_result.v1":
        raise RuntimeError(f"{command} returned unexpected schema: {payload.get('schema_version')}")
    if payload.get("command") != command:
        raise RuntimeError(f"Expected {command}; got {payload.get('command')}")
    if bool(payload.get("ok")) is not ok:
        raise RuntimeError(f"{command} ok={payload.get('ok')}; expected {ok}.")


def _run_smoke_in_root(*, app_root: Path, pipeline_path: Path, work_root: Path) -> dict[str, Any]:
    config_path = _write_temp_config(work_root).resolve()
    service = DesktopAppService(app_root)
    powershell_host = service.resolve_powershell_host()
    resolved_state = _SmokeResolvedState(
        service,
        pipeline_path=pipeline_path,
        config_path=config_path,
        powershell_host=powershell_host,
    )
    facade = MediaPipelineApplicationFacade(service, app_version="v5-settings-patch-smoke")
    server = LocalApiServer(
        facade,
        token="settings-patch-smoke-token",
        resolved_provider=resolved_state.get,
        resolved_reload=resolved_state.reload,
        audit_root_provider=lambda: str(resolved_state.get().audit_reports_path or ""),
        command_journal_path=work_root / "RunLogs" / "local_api_command_history.json",
    )
    try:
        server.start()
        _validate_patch_static_assets(server.url)

        workspace_before_status, workspace_before = _get_json(f"{server.url}/api/settings/workspace", server.token)
        _require_status(workspace_before_status, "/api/settings/workspace")

        preview_status, preview = _post_json(
            f"{server.url}/api/settings/preview-patch",
            {"changes": PATCH_CHANGES},
            server.token,
        )
        _require_status(preview_status, "/api/settings/preview-patch")
        _require_command_result(preview, command="settings.preview_patch", ok=True)
        preview_data = preview.get("data") if isinstance(preview.get("data"), dict) else {}
        if preview_data.get("writes_config") is not False:
            raise RuntimeError("Preview Patch reported writes_config=true.")
        preview_progress = preview_data.get("settings_progress") if isinstance(preview_data.get("settings_progress"), dict) else {}
        if preview_progress.get("schema_version") != "desktop_settings_save_reload_progress.v1":
            raise RuntimeError("Preview Patch did not report settings save/reload progress.")
        for key in PATCH_CHANGES:
            if key not in preview_data.get("changed_keys", []):
                raise RuntimeError(f"Preview Patch did not report changed key {key}.")

        denied_status, denied_save = _post_json(
            f"{server.url}/api/settings/save-patch",
            {"changes": PATCH_CHANGES},
            server.token,
        )
        _require_status(denied_status, "/api/settings/save-patch denied")
        _require_command_result(denied_save, command="settings.save_patch", ok=False)
        if "confirm_save must be true." not in denied_save.get("warnings", []):
            raise RuntimeError("Denied Save Patch did not report the confirm_save boundary.")

        confirmed_status, confirmed_save = _post_json(
            f"{server.url}/api/settings/save-patch",
            {"changes": PATCH_CHANGES, "confirm_save": True},
            server.token,
        )
        _require_status(confirmed_status, "/api/settings/save-patch confirmed")
        _require_command_result(confirmed_save, command="settings.save_patch", ok=True)
        confirmed_data = confirmed_save.get("data") if isinstance(confirmed_save.get("data"), dict) else {}
        if confirmed_data.get("writes_config") is not True:
            raise RuntimeError("Confirmed Save Patch did not report writes_config=true.")
        if confirmed_data.get("reloaded") is not True:
            raise RuntimeError("Confirmed Save Patch did not report successful reload.")
        confirmed_progress = confirmed_data.get("settings_progress") if isinstance(confirmed_data.get("settings_progress"), dict) else {}
        if confirmed_progress.get("status") != "complete":
            raise RuntimeError("Confirmed Save Patch did not report complete save/reload progress.")
        confirmed_bars = confirmed_data.get("progress_bars") if isinstance(confirmed_data.get("progress_bars"), list) else []
        if not confirmed_bars or confirmed_bars[0].get("percent") != 100.0:
            raise RuntimeError("Confirmed Save Patch did not report a complete settings progress bar.")
        backup_path = Path(str(confirmed_data.get("backup_path") or ""))
        if not backup_path.is_file():
            raise RuntimeError("Confirmed Save Patch did not create a backup file.")

        workspace_after_status, workspace_after = _get_json(f"{server.url}/api/settings/workspace", server.token)
        _require_status(workspace_after_status, "/api/settings/workspace after save")
        after_config = workspace_after.get("config") if isinstance(workspace_after.get("config"), dict) else {}
        for key, value in PATCH_CHANGES.items():
            if str(after_config.get(key)) != str(value):
                raise RuntimeError(f"Workspace after save did not show {key}={value}.")

        commands_status, commands = _get_json(f"{server.url}/api/commands?limit=20", server.token)
        _require_status(commands_status, "/api/commands")
        entries = commands.get("entries") if isinstance(commands.get("entries"), list) else []
        command_names = [str(entry.get("command") or "") for entry in entries if isinstance(entry, dict)]
        if command_names.count("settings.save_patch") < 2 or "settings.preview_patch" not in command_names:
            raise RuntimeError("Command history did not capture preview, denied save, and confirmed save results.")
    finally:
        server.stop()

    return {
        "schema_version": "webview_settings_patch_evidence_smoke.v1",
        "config_path": str(config_path),
        "pipeline_path": str(pipeline_path),
        "patch": dict(PATCH_CHANGES),
        "before": {
            KEY_MAX_ENCODE_GROWTH_PERCENT: workspace_before.get("config", {}).get(KEY_MAX_ENCODE_GROWTH_PERCENT),
            KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT: workspace_before.get("config", {}).get(KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT),
        },
        "preview": {
            "ok": bool(preview.get("ok")),
            "changed_keys": preview_data.get("changed_keys", []),
            "writes_config": preview_data.get("writes_config"),
            "progress": preview_progress.get("status"),
            "diff_line_count": len(preview_data.get("redacted_diff_lines", []) if isinstance(preview_data.get("redacted_diff_lines"), list) else []),
        },
        "denied_save": {
            "ok": bool(denied_save.get("ok")),
            "warnings": denied_save.get("warnings", []),
        },
        "confirmed_save": {
            "ok": bool(confirmed_save.get("ok")),
            "writes_config": confirmed_data.get("writes_config"),
            "reloaded": confirmed_data.get("reloaded"),
            "progress": confirmed_progress.get("status"),
            "backup_path": str(backup_path),
            "backup_exists": backup_path.is_file(),
        },
        "after": {
            KEY_MAX_ENCODE_GROWTH_PERCENT: after_config.get(KEY_MAX_ENCODE_GROWTH_PERCENT),
            KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT: after_config.get(KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT),
        },
        "command_history": command_names[:8],
        "boundary": "Temporary config only; backend-owned settings preview/save commands exercised; no launch, media processing, publish, rename, queue mutation, or source/output/scratch media mutation was requested.",
    }


def run_smoke(
    *,
    app_root: Path,
    pipeline_path: Path | None = None,
    work_root: Path | None = None,
) -> dict[str, Any]:
    app_root = app_root.resolve()
    service = DesktopAppService(app_root)
    selected_pipeline = (pipeline_path or service.default_pipeline_path()).resolve()
    if work_root is not None:
        work_root.mkdir(parents=True, exist_ok=True)
        return _run_smoke_in_root(app_root=app_root, pipeline_path=selected_pipeline, work_root=work_root.resolve())
    with tempfile.TemporaryDirectory(prefix="mediapipeline-settings-patch-smoke-") as raw_root:
        return _run_smoke_in_root(app_root=app_root, pipeline_path=selected_pipeline, work_root=Path(raw_root).resolve())


def _print_summary(summary: dict[str, Any]) -> None:
    print("WebView settings preview/save evidence smoke passed.")
    print(f"Config   : {summary['config_path']}")
    print(f"Pipeline : {summary['pipeline_path']}")
    print(f"Patch    : {json.dumps(summary['patch'], sort_keys=True)}")
    print(f"Before   : {json.dumps(summary['before'], sort_keys=True)}")
    print(f"After    : {json.dumps(summary['after'], sort_keys=True)}")
    print(
        "Preview  : "
        f"ok={summary['preview']['ok']} writes_config={summary['preview']['writes_config']} "
        f"changed={summary['preview']['changed_keys']}"
    )
    print(
        "Save     : "
        f"denied_ok={summary['denied_save']['ok']} "
        f"confirmed_ok={summary['confirmed_save']['ok']} "
        f"reloaded={summary['confirmed_save']['reloaded']} "
        f"backup_exists={summary['confirmed_save']['backup_exists']}"
    )
    print(f"Commands : {', '.join(summary['command_history'])}")
    print(f"Boundary : {summary['boundary']}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test WebView Settings Preview/Save evidence using a temporary config.")
    parser.add_argument("--app-root", default="", help="DesktopApp root. Defaults to the bundled DesktopApp folder.")
    parser.add_argument("--pipeline-path", default="", help="Optional pipeline script path. Defaults to the bundled pipeline script.")
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    return parser.parse_args(argv)


def default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_smoke(
        app_root=Path(args.app_root).expanduser() if args.app_root else default_app_root(),
        pipeline_path=Path(args.pipeline_path).expanduser() if args.pipeline_path else None,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
