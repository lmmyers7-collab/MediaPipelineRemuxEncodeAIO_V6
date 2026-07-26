from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from collections.abc import Callable, Mapping

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.rename.file_io import atomic_write_text
from mediapipeline.core.rename.cleaning_policy import normalize_rename_cleaning_policy
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


def build_naming_preview_request(
    paths: list[Path],
    *,
    media_kind: str,
    cleaning_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "naming_preview_request.v2",
        "rename_cleaning_policy": normalize_rename_cleaning_policy(cleaning_policy),
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


def _naming_preview_leaf(value: object) -> str:
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    return PureWindowsPath(PurePosixPath(text).name).name


def build_synthetic_naming_preview_request(
    *,
    filename: str,
    source_folder: str,
    media_kind: str,
    cleaning_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    input_name = _naming_preview_leaf(filename)
    folder_context = str(source_folder or "").strip().strip('"')
    candidate_suffix = PureWindowsPath(input_name).suffix.lower()
    has_media_suffix = candidate_suffix in MEDIA_FILE_SUFFIXES
    planner_name = input_name if has_media_suffix else f"{input_name}.mkv"
    planner_extension = candidate_suffix if has_media_suffix else ".mkv"
    synthetic_path = str(PureWindowsPath(folder_context) / planner_name) if folder_context else planner_name
    return {
        "schema_version": "naming_preview_request.v2",
        "rename_cleaning_policy": normalize_rename_cleaning_policy(cleaning_policy),
        "items": [
            {
                "path": synthetic_path,
                "original_name": planner_name,
                "input_name": input_name,
                "extension": planner_extension,
                "media_kind": media_kind,
                "synthetic": True,
                "source_folder": folder_context,
                "assumed_media_extension": not has_media_suffix,
            }
        ],
    }


def _synthetic_naming_preview_failure(
    *,
    media_kind: str,
    requested_policy_fingerprint: str,
    applied_policy_fingerprint: str = "",
    error: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "media_kind": media_kind,
        "requested_policy_fingerprint": requested_policy_fingerprint,
        "applied_policy_fingerprint": applied_policy_fingerprint,
        "policy_fingerprint_match": False,
        "row": {},
        "error": error,
    }


def parse_synthetic_naming_preview_result(
    data: Any,
    *,
    media_kind: str,
    expected_policy_fingerprint: str,
    expected_source_path: str = "",
) -> dict[str, Any]:
    requested_fingerprint = str(expected_policy_fingerprint or "")
    if not isinstance(data, dict):
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview returned no payload",
        )
    schema_version = str(data.get("schema_version") or "")
    applied_fingerprint = str(data.get("applied_policy_fingerprint") or "")
    if schema_version != "naming_preview.v2":
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            applied_policy_fingerprint=applied_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview returned unsupported schema {schema_version or '(missing)'}",
        )
    if not requested_fingerprint or applied_fingerprint != requested_fingerprint:
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            applied_policy_fingerprint=applied_fingerprint,
            error=f"pipeline {media_kind.lower()} naming preview policy fingerprint mismatch",
        )
    rows = data.get("rows")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            applied_policy_fingerprint=applied_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview returned no single usable row",
        )
    row = dict(rows[0])
    if row.get("synthetic") is not True:
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            applied_policy_fingerprint=applied_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview omitted synthetic evidence",
        )
    requested_source_key = str(expected_source_path or "").casefold()
    returned_source_key = str(row.get("source_path") or "").casefold()
    if requested_source_key and returned_source_key != requested_source_key:
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            applied_policy_fingerprint=applied_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview row did not match the requested synthetic input",
        )
    returned_media_kind = str(row.get("media_kind") or "").strip()
    parsed_identity = row.get("parsed_identity")
    identity_media_kind = (
        str(parsed_identity.get("media_kind") or "").strip()
        if isinstance(parsed_identity, Mapping)
        else ""
    )
    expected_media_key = str(media_kind or "").casefold()
    if returned_media_kind.casefold() != expected_media_key or (
        identity_media_kind and identity_media_kind.casefold() != expected_media_key
    ):
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            applied_policy_fingerprint=applied_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview row returned the wrong media kind",
        )
    if row.get("ok") is not True or not str(row.get("file_name") or "").strip():
        detail = str(row.get("error") or "").strip() or "production destination plan returned no filename"
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            applied_policy_fingerprint=applied_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview failed: {detail}",
        )
    return {
        "ok": True,
        "media_kind": media_kind,
        "requested_policy_fingerprint": requested_fingerprint,
        "applied_policy_fingerprint": applied_fingerprint,
        "policy_fingerprint_match": True,
        "row": row,
        "error": "",
    }


def parse_naming_preview_rows(
    data: Any,
    *,
    media_kind: str,
    logger: logging.Logger,
    expected_policy_fingerprint: str = "",
) -> tuple[dict[str, str], str]:
    previews: dict[str, str] = {}
    schema_version = str(data.get("schema_version") or "naming_preview.v1") if isinstance(data, dict) else ""
    if schema_version not in {"naming_preview.v1", "naming_preview.v2"}:
        return {}, f"pipeline {media_kind.lower()} naming preview returned unsupported schema {schema_version or '(missing)'}"
    if schema_version == "naming_preview.v2" and expected_policy_fingerprint:
        applied_fingerprint = str(data.get("applied_policy_fingerprint") or "")
        if applied_fingerprint != expected_policy_fingerprint:
            return {}, f"pipeline {media_kind.lower()} naming preview policy fingerprint mismatch"
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
    cleaning_policy: Mapping[str, Any] | None = None,
) -> tuple[dict[str, str], str]:
    if not paths or not powershell_host:
        return {}, ""
    if script_path is None:
        return {}, ""

    with tempfile.TemporaryDirectory(prefix="mediapipeline-naming-preview-") as td:
        temp_root = Path(td)
        input_path = temp_root / "input.json"
        output_path = temp_root / "output.json"
        effective_policy = normalize_rename_cleaning_policy(cleaning_policy)
        payload = build_naming_preview_request(paths, media_kind=media_kind, cleaning_policy=effective_policy)
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

    return parse_naming_preview_rows(
        data,
        media_kind=media_kind,
        logger=logger,
        expected_policy_fingerprint=str(effective_policy.get("policy_fingerprint") or ""),
    )


def load_synthetic_pipeline_name_preview(
    *,
    filename: str,
    source_folder: str,
    media_kind: str,
    powershell_host: str | None,
    script_path: Path | None,
    timeout_seconds: int,
    hidden_kwargs: dict[str, Any],
    logger: logging.Logger,
    run_capture_func: RunCaptureFunc,
    cleaning_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    effective_policy = normalize_rename_cleaning_policy(cleaning_policy)
    requested_fingerprint = str(effective_policy.get("policy_fingerprint") or "")
    if not str(filename or "").strip():
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview requires a filename",
        )
    if not powershell_host:
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview unavailable: PowerShell host is not configured",
        )
    if script_path is None:
        return _synthetic_naming_preview_failure(
            media_kind=media_kind,
            requested_policy_fingerprint=requested_fingerprint,
            error=f"pipeline {media_kind.lower()} synthetic naming preview unavailable: production preview script was not found",
        )

    payload = build_synthetic_naming_preview_request(
        filename=filename,
        source_folder=source_folder,
        media_kind=media_kind,
        cleaning_policy=effective_policy,
    )
    with tempfile.TemporaryDirectory(prefix="mediapipeline-synthetic-naming-preview-") as td:
        temp_root = Path(td)
        input_path = temp_root / "input.json"
        output_path = temp_root / "output.json"
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
                label=f"pipeline {media_kind.lower()} synthetic naming preview",
            )
        except Exception as exc:
            logger.warning("Pipeline %s synthetic naming preview failed to launch: %s", media_kind.lower(), exc)
            return _synthetic_naming_preview_failure(
                media_kind=media_kind,
                requested_policy_fingerprint=requested_fingerprint,
                error=f"pipeline {media_kind.lower()} synthetic naming preview unavailable: {exc}",
            )
        if result.timed_out:
            detail = result.kill_message or f"timeout after {timeout_seconds}s"
            logger.warning("Pipeline %s synthetic naming preview timed out: %s", media_kind.lower(), detail)
            return _synthetic_naming_preview_failure(
                media_kind=media_kind,
                requested_policy_fingerprint=requested_fingerprint,
                error=f"pipeline {media_kind.lower()} synthetic naming preview unavailable: {detail}",
            )
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
            detail = " ".join(line.strip() for line in tail if line.strip()) or f"exit {result.returncode}"
            logger.warning("Pipeline %s synthetic naming preview failed: %s", media_kind.lower(), detail)
            return _synthetic_naming_preview_failure(
                media_kind=media_kind,
                requested_policy_fingerprint=requested_fingerprint,
                error=f"pipeline {media_kind.lower()} synthetic naming preview unavailable: {detail}",
            )
        if not output_path.exists():
            return _synthetic_naming_preview_failure(
                media_kind=media_kind,
                requested_policy_fingerprint=requested_fingerprint,
                error=f"pipeline {media_kind.lower()} synthetic naming preview did not return output",
            )
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _synthetic_naming_preview_failure(
                media_kind=media_kind,
                requested_policy_fingerprint=requested_fingerprint,
                error=f"pipeline {media_kind.lower()} synthetic naming preview returned invalid JSON: {exc}",
            )

    return parse_synthetic_naming_preview_result(
        data,
        media_kind=media_kind,
        expected_policy_fingerprint=requested_fingerprint,
        expected_source_path=str(payload["items"][0]["path"]),
    )
