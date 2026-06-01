from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.config.load import load_psd1_mapping
from app.config.contracts import ConfigDocumentServiceProtocol, RunCaptureFunc

def load_config_data_for_service(
    service: ConfigDocumentServiceProtocol,
    config_path: Path,
    powershell_host: str | None,
    *,
    run_capture_func: RunCaptureFunc,
) -> dict[str, Any]:
    if not powershell_host or not config_path.exists():
        return {}

    result = load_psd1_mapping(
        config_path,
        powershell_host,
        run_capture_func=run_capture_func,
        timeout_seconds=30,
        extra_popen_kwargs=service._subprocess_kwargs_hidden(),
        label="config import",
    )
    if result.timed_out:
        service.logger.warning("Config load timed out for %s: %s", config_path, result.kill_message)
        return {}
    if not result.ok:
        service.logger.warning("Config load failed for %s: %s", config_path, result.error)
        return {}
    return result.data


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
