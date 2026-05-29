from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from mediapipeline_desktop_app.models import ConfigSaveResult, ResolvedPaths
from app.shared.protocols import ConfigSaveServiceProtocol
from app.shared.utils import _atomic_write_text, _normalize_open_path_text


def config_backup_path(output_path: Path) -> Path:
    backup_dir = output_path.parent / "ConfigBackups"
    for _ in range(20):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        candidate = backup_dir / f"{output_path.stem}.backup_{stamp}{output_path.suffix}"
        if not candidate.exists():
            return candidate
        time.sleep(0.001)
    raise RuntimeError(f"Unable to choose a unique backup path for {output_path}")


def save_config_document_for_service(
    service: ConfigSaveServiceProtocol,
    output_path: Path,
    document_text: str,
    create_backup: bool,
    *,
    config_values: dict[str, Any] | None,
    powershell_host: str | None,
) -> ConfigSaveResult:
    backup_path: Path | None = None
    validation_errors, _ = service.validate_config_document_for_save(
        document_text,
        config_values=config_values,
        powershell_host=powershell_host,
    )
    if validation_errors:
        detail = "\n".join(f"- {item}" for item in validation_errors)
        raise ValueError(f"Config document failed validation before save:\n{detail}")
    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(f"Config save target is a directory: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if create_backup and output_path.exists():
        backup_path = service._config_backup_path(output_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, backup_path)

    _atomic_write_text(output_path, document_text)
    return ConfigSaveResult(output_path=output_path, backup_path=backup_path)


def list_config_profiles_for_service(service: ConfigSaveServiceProtocol, config_path: Path) -> list[str]:
    profiles_dir = service.config_profiles_dir(config_path)
    if not profiles_dir.is_dir():
        return []
    names: list[str] = []
    for profile_path in profiles_dir.glob("*.psd1"):
        try:
            safe_name = service.normalize_profile_name(profile_path.stem)
        except ValueError:
            service.logger.warning("Ignoring unsafe config profile name: %s", profile_path.name)
            continue
        if safe_name == profile_path.stem:
            names.append(safe_name)
    return sorted(names, key=str.casefold)


def normalize_config_path_value(path_text: str) -> str:
    cleaned = _normalize_open_path_text(path_text)
    if not cleaned:
        return ""
    path = Path(cleaned).expanduser()
    try:
        if path.is_absolute():
            return str(path.resolve(strict=False))
    except OSError:
        pass
    return str(path)


def save_config_profile_for_service(
    service: ConfigSaveServiceProtocol,
    resolved: ResolvedPaths,
    profile_name: str,
) -> tuple[str, Path]:
    if not resolved.config_path.exists():
        raise FileNotFoundError(f"Config file not found: {resolved.config_path}")
    safe_name, profile_path = service.config_profile_path(resolved.config_path, profile_name)
    source_text = resolved.config_path.read_text(encoding="utf-8", errors="replace")
    validation_errors, _ = service.validate_config_document_for_save(
        source_text,
        powershell_host=resolved.powershell_host,
    )
    if validation_errors:
        detail = "\n".join(f"- {item}" for item in validation_errors)
        raise ValueError(f"Current config failed validation before profile save:\n{detail}")
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(profile_path, source_text)
    return safe_name, profile_path


def load_config_profile_for_service(
    service: ConfigSaveServiceProtocol,
    resolved: ResolvedPaths,
    profile_name: str,
) -> tuple[str, Path, ConfigSaveResult]:
    safe_name, profile_path = service.config_profile_path(resolved.config_path, profile_name)
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile file not found: {profile_path}")
    profile_text = profile_path.read_text(encoding="utf-8", errors="replace")
    profile_data = service.load_config_data(profile_path, resolved.powershell_host)
    validation_errors, _ = service.validate_config_document_for_save(
        profile_text,
        config_values=profile_data,
        powershell_host=resolved.powershell_host,
    )
    if validation_errors:
        detail = "\n".join(f"- {item}" for item in validation_errors)
        raise ValueError(f"Profile failed validation before load:\n{detail}")
    result = service.save_config_document(
        resolved.config_path,
        profile_text,
        create_backup=True,
        config_values=profile_data,
        powershell_host=resolved.powershell_host,
    )
    return safe_name, profile_path, result
