"""Canonical PSD1 loader and converter for `mediapipeline.contracts.config`.

PowerShell remains the PSD1 parser because `Import-PowerShellDataFile` is
the format authority. DesktopApp compatibility wrappers call into this
module instead of composing separate import/serialize logic.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from mediapipeline.contracts.config import CONFIG_KEY_ORDER, Config
from mediapipeline.tools.paths import find_repo_root

RunCaptureCallable = Callable[..., Any]


class ConfigLoadError(RuntimeError):
    """Raised when a PSD1 config cannot be parsed or validated."""


@dataclass(frozen=True)
class Psd1LoadResult:
    data: dict[str, Any]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    kill_message: str = ""

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0 and not self.stderr and bool(self.data)

    @property
    def error(self) -> str:
        if self.timed_out:
            return self.kill_message or "Config import timed out."
        if self.stderr:
            return self.stderr.strip()
        if self.returncode != 0:
            return "Config import failed."
        if not self.data:
            return "Config import produced no object data."
        return ""


def default_powershell_host(repo_root: Path | None = None) -> str:
    root = repo_root or find_repo_root(Path(__file__))
    bundled = root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
    if bundled.exists():
        return str(bundled)
    return "pwsh"


def build_psd1_import_args(config_path: Path, powershell_host: str) -> list[str]:
    quoted_path = psd1_quote(str(config_path))
    command = (
        "$ErrorActionPreference='Stop'; "
        f"$cfg = Import-PowerShellDataFile -LiteralPath {quoted_path}; "
        "$cfg | ConvertTo-Json -Depth 100 -Compress"
    )
    return [
        powershell_host,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        command,
    ]


def parse_psd1_json(stdout: str) -> dict[str, Any]:
    data = json.loads(stdout)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("PSD1 import did not produce a JSON object.")
    return data


def load_psd1_mapping(
    config_path: Path,
    powershell_host: str | None = None,
    *,
    run_capture_func: RunCaptureCallable | None = None,
    timeout_seconds: int = 30,
    extra_popen_kwargs: dict[str, Any] | None = None,
    label: str = "config import",
    encoding: str = "utf-8",
    errors: str = "replace",
) -> Psd1LoadResult:
    if not config_path.exists():
        return Psd1LoadResult(data={}, stderr=f"Config path does not exist: {config_path}")

    host = powershell_host or default_powershell_host()
    args = build_psd1_import_args(config_path, host)

    if run_capture_func is not None:
        result = run_capture_func(
            args,
            timeout_seconds=timeout_seconds,
            encoding=encoding,
            errors=errors,
            extra_popen_kwargs=extra_popen_kwargs or {},
            label=label,
        )
        timed_out = bool(getattr(result, "timed_out", False))
        stdout = str(getattr(result, "stdout", "") or "")
        stderr = str(getattr(result, "stderr", "") or "")
        returncode = int(getattr(result, "returncode", 1) or 0)
        kill_message = str(getattr(result, "kill_message", "") or "")
    else:
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding=encoding,
                errors=errors,
                timeout=timeout_seconds,
                **(extra_popen_kwargs or {}),
            )
        except subprocess.TimeoutExpired as exc:
            return Psd1LoadResult(
                data={},
                returncode=1,
                stdout=str(exc.stdout or ""),
                stderr=str(exc.stderr or ""),
                timed_out=True,
                kill_message=f"Timed out after {timeout_seconds} seconds.",
            )
        timed_out = False
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        returncode = completed.returncode
        kill_message = ""

    if timed_out:
        return Psd1LoadResult(
            data={},
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
            kill_message=kill_message,
        )
    if returncode != 0:
        return Psd1LoadResult(data={}, returncode=returncode, stdout=stdout, stderr=stderr)
    if not stdout.strip():
        return Psd1LoadResult(data={}, returncode=returncode, stdout=stdout, stderr="Empty config JSON output.")

    try:
        data = parse_psd1_json(stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        return Psd1LoadResult(data={}, returncode=returncode, stdout=stdout, stderr=str(exc))
    return Psd1LoadResult(data=data, returncode=returncode, stdout=stdout, stderr=stderr)


def config_from_mapping(data: Mapping[str, Any]) -> Config:
    return Config.model_validate(dict(data))


def load_config(config_path: Path, powershell_host: str | None = None) -> Config:
    result = load_psd1_mapping(config_path, powershell_host)
    if not result.ok:
        raise ConfigLoadError(result.error)
    return config_from_mapping(result.data)


def config_to_flat_dict(config: Config | Mapping[str, Any], *, exclude_none: bool = False) -> dict[str, Any]:
    if isinstance(config, Config):
        data = config.model_dump(mode="json", exclude_none=exclude_none)
    else:
        data = dict(config)
    return order_top_level_config(data)


def config_to_psd1(config: Config | Mapping[str, Any], *, exclude_none: bool = False) -> str:
    return serialize_psd1_document(config_to_flat_dict(config, exclude_none=exclude_none))


def serialize_psd1_document(data: Config | Mapping[str, Any]) -> str:
    ordered = config_to_flat_dict(data)
    body = "\n".join(psd1_lines(ordered, indent=0, top_level=True))
    header = [
        "# Generated by MediaPipelineRemuxEncodeAIO Desktop App.",
        "# Unknown keys are preserved, but original comments/formatting are not.",
        body,
        "",
    ]
    return "\n".join(header)


def order_top_level_config(data: Mapping[str, Any]) -> dict[str, Any]:
    order_map = {key: index for index, key in enumerate(CONFIG_KEY_ORDER)}
    ordered_keys = sorted(
        data.keys(),
        key=lambda key: (order_map.get(str(key), len(order_map) + 1000), str(key).casefold()),
    )
    return {str(key): data[key] for key in ordered_keys}


def psd1_lines(value: Any, indent: int, top_level: bool = False) -> list[str]:
    _ = top_level
    pad = " " * indent
    child_pad = " " * (indent + 4)

    if isinstance(value, Mapping):
        lines = [f"{pad}@{{"]
        for key, item_value in value.items():
            rendered = psd1_lines(item_value, indent + 4)
            key_text = psd1_key(str(key))
            if len(rendered) == 1:
                lines.append(f"{child_pad}{key_text} = {rendered[0].lstrip()}")
                continue
            lines.append(f"{child_pad}{key_text} = {rendered[0].lstrip()}")
            lines.extend(rendered[1:])
        lines.append(f"{pad}}}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{pad}@()"]
        lines = [f"{pad}@("]
        for index, item in enumerate(value):
            is_last = index == len(value) - 1
            rendered = psd1_lines(item, indent + 4)
            if len(rendered) == 1:
                suffix = "" if is_last else ","
                lines.append(f"{child_pad}{rendered[0].lstrip()}{suffix}")
                continue
            lines.append(f"{child_pad}{rendered[0].lstrip()}")
            lines.extend(rendered[1:])
            if not is_last:
                lines[-1] = f"{lines[-1]},"
        lines.append(f"{pad})")
        return lines

    if isinstance(value, bool):
        return [f"{pad}{'$true' if value else '$false'}"]
    if value is None:
        return [f"{pad}$null"]
    if isinstance(value, int):
        return [f"{pad}{value}"]
    if isinstance(value, float):
        return [f"{pad}{format(value, 'g')}"]
    return [f"{pad}{psd1_quote(str(value))}"]


def psd1_key(key: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return key
    return psd1_quote(key)


def psd1_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


__all__ = [
    "ConfigLoadError",
    "Psd1LoadResult",
    "build_psd1_import_args",
    "config_from_mapping",
    "config_to_flat_dict",
    "config_to_psd1",
    "default_powershell_host",
    "load_config",
    "load_psd1_mapping",
    "order_top_level_config",
    "parse_psd1_json",
    "psd1_key",
    "psd1_lines",
    "psd1_quote",
    "serialize_psd1_document",
]
