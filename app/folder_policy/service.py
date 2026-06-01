from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.folder_policy.contracts import (
    default_folder_policy as default_folder_policy_payload,
    stream_signature,
    stream_topology,
)
from app.folder_policy.io import (
    folder_policy_path as folder_policy_path_file,
    load_folder_policy_file,
    save_folder_policy_file,
)
from app.folder_policy.probe import parse_ffprobe_stream_signature
from app.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline_desktop_app.subprocess_runner import run_capture


class FolderPolicyServiceMixin:
    def resolve_ffprobe_executable(self) -> Path | None:
        for rel in (
            "Pipeline/Tools/ffmpeg/bin/ffprobe.exe",
            "Pipeline/Tools/ffmpeg/bin/ffprobe",
        ):
            for base in (self.workspace_root, self.app_root):
                candidate = base / rel
                if candidate.exists():
                    return candidate
        found = shutil.which("ffprobe.exe") or shutil.which("ffprobe")
        return Path(found) if found else None

    def default_folder_policy(self, folder: Path) -> dict[str, Any]:
        return default_folder_policy_payload(folder)

    def folder_policy_path(self, folder: Path) -> Path:
        return folder_policy_path_file(folder)

    def load_folder_policy(self, folder: Path) -> dict[str, Any]:
        return load_folder_policy_file(folder, default_policy=self.default_folder_policy(folder))

    def save_folder_policy(self, folder: Path, policy: dict[str, Any]) -> Path:
        return save_folder_policy_file(folder, policy)

    def _stream_signature(self, stream: dict[str, Any]) -> dict[str, Any]:
        return stream_signature(stream)

    def probe_media_stream_signature(self, media_path: Path, *, timeout: int = 30) -> dict[str, Any]:
        ffprobe = self.resolve_ffprobe_executable()
        if not ffprobe:
            raise RuntimeError("ffprobe not found in bundled Tools or PATH.")
        result = run_capture(
            [
                str(ffprobe),
                "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,channels,disposition:stream_tags=language,title",
                "-of", "json",
                "--",
                str(media_path),
            ],
            errors="replace",
            timeout_seconds=timeout,
            extra_popen_kwargs=self._subprocess_kwargs_hidden(),
            label="folder policy ffprobe",
        )
        if result.timed_out:
            raise RuntimeError(f"ffprobe timed out after {timeout}s for {media_path}: {result.kill_message}")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"ffprobe failed for {media_path}: {detail or result.returncode}")
        return parse_ffprobe_stream_signature(media_path, result.stdout or "{}")

    def validate_folder_policy(self, folder: Path, *, sample_path: Path | None = None, max_files: int = 8) -> dict[str, Any]:
        if not folder.exists() or not folder.is_dir():
            raise NotADirectoryError(f"Folder does not exist: {folder}")
        policy = self.load_folder_policy(folder)
        media_files = sorted(
            [path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_FILE_SUFFIXES],
            key=lambda path: str(path).casefold(),
        )
        if not media_files:
            return {"ok": False, "policy": policy, "errors": ["No media files found under folder."], "warnings": [], "files": []}

        if sample_path is None:
            raw_sample = str((policy.get("validation") or {}).get("sample_file") or "").strip() if isinstance(policy.get("validation"), dict) else ""
            sample_path = folder / raw_sample if raw_sample else media_files[0]
        sample_path = sample_path if sample_path.is_absolute() else folder / sample_path
        if not sample_path.exists():
            return {"ok": False, "policy": policy, "errors": [f"Sample file does not exist: {sample_path}"], "warnings": [], "files": []}

        selected = [sample_path] + [path for path in media_files if path != sample_path]
        selected = selected[: max(1, max_files)]
        errors: list[str] = []
        warnings: list[str] = []
        probed: list[dict[str, Any]] = []
        sample_signature: dict[str, Any] | None = None
        validation = policy.get("validation") if isinstance(policy.get("validation"), dict) else {}
        require_uniform = bool(validation.get("require_uniform_stream_topology", True)) if isinstance(validation, dict) else True
        for path in selected:
            try:
                signature = self.probe_media_stream_signature(path)
            except Exception as exc:
                errors.append(f"{path.name}: probe failed: {exc}")
                continue
            probed.append(signature)
            topology = stream_topology(signature)
            signature["topology"] = topology
            if sample_signature is None:
                sample_signature = topology
                continue
            if topology != sample_signature:
                message = f"{Path(signature['path']).name}: stream topology differs from sample."
                if require_uniform:
                    errors.append(message)
                else:
                    warnings.append(message)

        saved_policy_path = ""
        if sample_signature is not None and not errors:
            validation_payload = dict(validation or {})
            validation_payload["sample_file"] = str(sample_path.relative_to(folder)) if sample_path.is_relative_to(folder) else str(sample_path)
            validation_payload["require_uniform_stream_topology"] = require_uniform
            validation_payload["expected_topology"] = sample_signature
            validation_payload["checked_count"] = len(probed)
            validation_payload["validated_at"] = datetime.now(timezone.utc).isoformat()
            if warnings:
                validation_payload["warnings"] = warnings
            else:
                validation_payload.pop("warnings", None)
            policy["validation"] = validation_payload
            saved_policy_path = str(self.save_folder_policy(folder, policy))

        return {
            "ok": not errors,
            "policy": policy,
            "errors": errors,
            "warnings": warnings,
            "files": probed,
            "sample": str(sample_path),
            "checked_count": len(probed),
            "saved_policy_path": saved_policy_path,
        }
