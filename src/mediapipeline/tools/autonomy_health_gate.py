from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from mediapipeline.core.diagnostics.autonomy_health import autonomy_health_is_blocked, autonomy_health_payload
from mediapipeline.core.processes.path_evidence import LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS, configured_path_health
from mediapipeline.core.publish.pending_service import PendingPublishServiceMixin
from mediapipeline.desktop.models import ResolvedPaths


AUTONOMY_HEALTH_BLOCKED_EXIT_CODE = 76
AUTONOMY_HEALTH_GATE_PATH_HEALTH_TIMEOUT_SECONDS = LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS


class _PendingScanner(PendingPublishServiceMixin):
    pass


def _path(value: Any) -> Path:
    text = str(value or "").strip()
    return Path(text) if text else Path()


def _optional_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def resolved_paths_from_payload(payload: Mapping[str, Any]) -> ResolvedPaths:
    config_data = payload.get("config_data")
    return ResolvedPaths(
        app_root=_path(payload.get("app_root")),
        workspace_root=_path(payload.get("workspace_root")),
        pipeline_path=_path(payload.get("pipeline_path")),
        config_path=_path(payload.get("config_path")),
        audit_script_path=_path(payload.get("audit_script_path")),
        rerun_script_path=_path(payload.get("rerun_script_path")),
        powershell_host=str(payload.get("powershell_host") or ""),
        local_base=_optional_path(payload.get("local_base")),
        state_root=_optional_path(payload.get("state_root")),
        active_jobs_path=_optional_path(payload.get("active_jobs_path")),
        failed_reports_path=_optional_path(payload.get("failed_reports_path")),
        failed_markers_path=_optional_path(payload.get("failed_markers_path")),
        pending_push_path=_optional_path(payload.get("pending_push_path")),
        completed_manifest_path=_optional_path(payload.get("completed_manifest_path")),
        queue_snapshot_path=_optional_path(payload.get("queue_snapshot_path")),
        progress_file=_optional_path(payload.get("progress_file")),
        event_file=_optional_path(payload.get("event_file")),
        log_file=_optional_path(payload.get("log_file")),
        source_movies=_optional_path(payload.get("source_movies")),
        source_tv=_optional_path(payload.get("source_tv")),
        config_data=dict(config_data) if isinstance(config_data, Mapping) else {},
    )


def _read_payload(args: argparse.Namespace) -> Mapping[str, Any]:
    if args.paths_json_file:
        raw = Path(args.paths_json_file).read_text(encoding="utf-8-sig")
    else:
        raw = str(args.paths_json or "").strip()
    if not raw:
        raise ValueError("paths JSON payload is required")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("paths JSON root must be an object")
    return payload


def build_health_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    resolved = resolved_paths_from_payload(payload)
    pending_publish = _PendingScanner().scan_pending_publish(resolved)
    path_health = configured_path_health(
        resolved,
        timeout_seconds=AUTONOMY_HEALTH_GATE_PATH_HEALTH_TIMEOUT_SECONDS,
    )
    return autonomy_health_payload(
        resolved,
        pending_publish=pending_publish,
        path_health=path_health,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate MediaPipeline autonomy health for launch gating.")
    parser.add_argument("--paths-json", default="", help="Resolved path payload JSON.")
    parser.add_argument("--paths-json-file", default="", help="File containing resolved path payload JSON.")
    args = parser.parse_args(argv)
    try:
        health = build_health_from_payload(_read_payload(args))
    except Exception as exc:
        error_payload = {
            "schema_version": "desktop_autonomy_health_gate_error.v1",
            "ok": False,
            "error": str(exc),
        }
        print(json.dumps(error_payload, ensure_ascii=False))
        return 2
    print(json.dumps(health, ensure_ascii=False))
    return AUTONOMY_HEALTH_BLOCKED_EXIT_CODE if autonomy_health_is_blocked(health) else 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "AUTONOMY_HEALTH_BLOCKED_EXIT_CODE",
    "AUTONOMY_HEALTH_GATE_PATH_HEALTH_TIMEOUT_SECONDS",
    "build_health_from_payload",
    "main",
    "resolved_paths_from_payload",
]
