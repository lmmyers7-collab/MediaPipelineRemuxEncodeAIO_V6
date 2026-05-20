from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .models import ResolvedPaths
from .service_runner_protocols import RerunMetadataServiceProtocol, RunCaptureFunc
from .service_utils import _atomic_write_text, _read_json_file
from .subprocess_runner import run_capture


def rerun_source_metadata_script_path_for_service(service: RerunMetadataServiceProtocol, resolved: ResolvedPaths) -> Path:
    return service._first_existing(
        resolved.rerun_script_path.parent / "Get-RerunSourceMetadata.ps1",
        service.workspace_root / "Pipeline" / "Get-RerunSourceMetadata.ps1",
        service.app_root / "Pipeline" / "Get-RerunSourceMetadata.ps1",
        service.workspace_root / "Get-RerunSourceMetadata.ps1",
        service.app_root / "Get-RerunSourceMetadata.ps1",
    )


def deduplicate_source_paths(source_paths: list[Path]) -> list[Path]:
    unique_paths: list[Path] = []
    seen: set[str] = set()
    for source_path in source_paths:
        key = str(source_path).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(source_path)
    return unique_paths


def load_rerun_source_metadata_for_service(
    service: RerunMetadataServiceProtocol,
    resolved: ResolvedPaths,
    source_paths: list[Path],
    *,
    run_capture_func: RunCaptureFunc = run_capture,
) -> dict[str, dict[str, Any]]:
    unique_paths = deduplicate_source_paths(source_paths)
    if not unique_paths:
        return {}

    script_path = service._rerun_source_metadata_script_path(resolved)
    if not resolved.powershell_host or not script_path.exists():
        service.logger.warning("Rerun source metadata helper unavailable; exported CSV will rely on source size/mtime only.")
        return {}

    with tempfile.TemporaryDirectory(prefix="mediapipeline-rerun-metadata-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        request_path = tmp_path / "request.json"
        output_path = tmp_path / "metadata.json"
        payload = {
            "schema_version": "rerun_source_metadata_request.v1",
            "source_paths": [str(path) for path in unique_paths],
        }
        _atomic_write_text(request_path, json.dumps(payload), encoding="utf-8")
        args = [
            resolved.powershell_host,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-InputJsonPath",
            str(request_path),
            "-OutputJsonPath",
            str(output_path),
        ]
        timeout_seconds = max(30.0, min(1800.0, 15.0 * len(unique_paths)))
        launch_cwd = service.workspace_root if service.workspace_root.exists() else service.app_root
        try:
            result = run_capture_func(
                args,
                timeout_seconds=timeout_seconds,
                cwd=launch_cwd,
                env=service._build_launch_environment(),
                extra_popen_kwargs=service._subprocess_kwargs_hidden(),
                encoding="utf-8",
                errors="replace",
                label="rerun source metadata",
                kill_tree=getattr(service, "kill_process_tree", None),
            )
            if result.timed_out:
                service.logger.warning("Rerun source metadata helper timed out: %s", result.kill_message)
                return {}
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip().splitlines()[-1:] or [f"exit {result.returncode}"]
                service.logger.warning("Rerun source metadata helper failed: %s", detail[0])
                return {}
            data = _read_json_file(output_path)
        except (OSError, json.JSONDecodeError) as exc:
            service.logger.warning("Rerun source metadata helper failed: %s", exc)
            return {}

    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_path = str(row.get("source_path") or "").strip()
        if source_path:
            metadata[source_path.casefold()] = row
    return metadata
