from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any
from collections.abc import Callable

from mediapipeline.core.rename.file_io import atomic_write_text
from mediapipeline.core.kernel.runtime.subprocess_runner import CapturedCommandResult


RunCaptureFunc = Callable[..., CapturedCommandResult]


def find_naming_preview_script(workspace_root: Path | None, app_root: Path | None) -> Path | None:
    candidates: list[Path] = []
    for root in (workspace_root, app_root):
        if not root:
            continue
        root_path = Path(root)
        candidates.extend(
            [
                root_path / "ops" / "pipeline" / "entrypoints" / "Get-NamingPreview.ps1",
                root_path / "entrypoints" / "Get-NamingPreview.ps1",
            ]
        )
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return None


def build_naming_preview_request(paths: list[Path], *, media_kind: str) -> dict[str, Any]:
    return {
        "schema_version": "naming_preview_request.v1",
        "items": [
            {
                "path": str(Path(path)),
                "original_name": Path(path).name,
                "extension": Path(path).suffix.lower(),
                "media_kind": media_kind,
            }
            for path in paths
        ],
    }


def parse_naming_preview_rows(data: Any, *, media_kind: str, logger: logging.Logger) -> tuple[dict[str, str], str]:
    previews: dict[str, str] = {}
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return {}, f"pipeline {media_kind.lower()} naming preview returned no rows"
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not row.get("ok"):
            error = str(row.get("error") or "").strip()
            if error:
                logger.warning(
                    "Pipeline %s naming preview skipped %s: %s",
                    media_kind.lower(),
                    row.get("source_path"),
                    error,
                )
            continue
        source_path = str(row.get("source_path") or "")
        file_name = str(row.get("file_name") or "")
        if source_path and file_name:
            previews[source_path.casefold()] = file_name
    return previews, "" if previews else f"pipeline {media_kind.lower()} naming preview returned no usable rows"


def load_pipeline_name_previews(
    paths: list[Path],
    *,
    media_kind: str,
    powershell_host: str | None,
    script_path: Path | None,
    timeout_seconds: int,
    hidden_kwargs: dict[str, Any],
    logger: logging.Logger,
    run_capture_func: RunCaptureFunc,
) -> tuple[dict[str, str], str]:
    if not paths or not powershell_host:
        return {}, ""
    if script_path is None:
        return {}, ""

    with tempfile.TemporaryDirectory(prefix="mediapipeline-naming-preview-") as td:
        temp_root = Path(td)
        input_path = temp_root / "input.json"
        output_path = temp_root / "output.json"
        payload = build_naming_preview_request(paths, media_kind=media_kind)
        atomic_write_text(input_path, json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            result = run_capture_func(
                [
                    powershell_host,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-InputJsonPath",
                    str(input_path),
                    "-OutputJsonPath",
                    str(output_path),
                ],
                encoding="utf-8",
                errors="replace",
                timeout_seconds=max(1, int(timeout_seconds)),
                cwd=str(script_path.parent),
                extra_popen_kwargs=hidden_kwargs,
                label=f"pipeline {media_kind.lower()} naming preview",
            )
        except Exception as exc:
            logger.warning("Pipeline %s naming preview failed to launch: %s", media_kind.lower(), exc)
            return {}, f"pipeline {media_kind.lower()} naming preview unavailable: {exc}"

        if result.timed_out:
            detail = result.kill_message or f"timeout after {timeout_seconds}s"
            logger.warning("Pipeline %s naming preview timed out: %s", media_kind.lower(), detail)
            return {}, f"pipeline {media_kind.lower()} naming preview unavailable: {detail}"
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
            detail = " ".join(line.strip() for line in tail if line.strip()) or f"exit {result.returncode}"
            logger.warning("Pipeline %s naming preview failed: %s", media_kind.lower(), detail)
            return {}, f"pipeline {media_kind.lower()} naming preview unavailable: {detail}"
        if not output_path.exists():
            logger.warning("Pipeline %s naming preview did not write %s", media_kind.lower(), output_path)
            return {}, f"pipeline {media_kind.lower()} naming preview did not return output"

        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Pipeline %s naming preview JSON decode failed: %s", media_kind.lower(), exc)
            return {}, f"pipeline {media_kind.lower()} naming preview returned invalid JSON: {exc}"

    return parse_naming_preview_rows(data, media_kind=media_kind, logger=logger)
