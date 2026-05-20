from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .service_runner_protocols import ConfigDocumentServiceProtocol, RunCaptureFunc

def load_config_data_for_service(
    service: ConfigDocumentServiceProtocol,
    config_path: Path,
    powershell_host: str | None,
    *,
    run_capture_func: RunCaptureFunc,
) -> dict[str, Any]:
    if not powershell_host or not config_path.exists():
        return {}

    quoted_path = str(config_path).replace("'", "''")
    command = (
        f"$cfg = Import-PowerShellDataFile -LiteralPath '{quoted_path}'; "
        "$cfg | ConvertTo-Json -Depth 20 -Compress"
    )
    result = run_capture_func(
        [powershell_host, "-NoProfile", "-Command", command],
        timeout_seconds=30,
        encoding="utf-8",
        errors="replace",
        extra_popen_kwargs=service._subprocess_kwargs_hidden(),
        label="config import",
    )
    if result.timed_out:
        service.logger.warning("Config load timed out for %s: %s", config_path, result.kill_message)
        return {}
    if result.returncode != 0 or not result.stdout.strip():
        stderr = result.stderr.strip() or "Config import failed"
        service.logger.warning("Config load failed for %s: %s", config_path, stderr)
        return {}

    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as exc:
        service.logger.warning("Config JSON decode failed for %s: %s", config_path, exc)
    return {}


def validate_config_document_for_save_for_service(
    service: ConfigDocumentServiceProtocol,
    document_text: str,
    *,
    config_values: dict[str, Any] | None,
    powershell_host: str | None,
    run_capture_func: RunCaptureFunc,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not document_text.strip():
        errors.append("Config document is empty.")
    if config_values is not None:
        value_errors, value_warnings = service.validate_config_values(config_values)
        errors.extend(value_errors)
        warnings.extend(value_warnings)
    host = powershell_host or service.resolve_powershell_host()
    if not host:
        errors.append("PowerShell is required to validate config syntax before saving.")
        return errors, warnings
    if document_text.strip():
        with tempfile.TemporaryDirectory(prefix="mediapipeline-config-validate-") as tmp_dir:
            candidate = Path(tmp_dir) / "candidate.psd1"
            candidate.write_text(document_text, encoding="utf-8", newline="")
            quoted_path = str(candidate).replace("'", "''")
            command = f"$ErrorActionPreference='Stop'; $null = Import-PowerShellDataFile -LiteralPath '{quoted_path}'"
            result = run_capture_func(
                [host, "-NoProfile", "-NonInteractive", "-Command", command],
                timeout_seconds=15,
                extra_popen_kwargs=service._subprocess_kwargs_hidden(),
                label="config syntax validation",
            )
            if result.timed_out:
                errors.append("Config syntax validation timed out.")
            elif result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                errors.append(f"Config syntax validation failed: {detail or 'Import-PowerShellDataFile returned a nonzero exit code.'}")
    return errors, warnings
