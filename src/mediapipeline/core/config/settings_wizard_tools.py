"""Settings setup wizard helpers.

The wizard is a guided front end over the existing settings patch pipeline.
It produces normal settings `changes` and then delegates preview/save to the
same backend-owned PSD1 validation, backup, serialization, and reload flow.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from mediapipeline.core.config.encoding_capabilities import EncodingCapabilityFacts
from mediapipeline.core.config.identity import (
    MIN_OPERATOR_CONFIG_KEY_COUNT,
    REQUIRED_OPERATOR_ROOT_KEYS,
    config_looks_like_template,
    config_template_candidates,
    config_operation_block_data,
    config_operation_block_message,
)
from mediapipeline.core.config.library_profiles import (
    library_profiles_from_config,
    library_profiles_from_wizard_payload,
    normalize_library_profile_config_values,
)
from mediapipeline.core.config.settings_patch_policy import (
    settings_save_busy_result,
    settings_save_config_blocked_result,
    settings_save_exception_result,
    settings_save_service_unavailable_result,
    settings_save_success_result,
    settings_save_validation_error_result,
)
from mediapipeline.core.kernel.config_keys import (
    KEY_ALLOW_NO_AUDIO,
    KEY_ALLOW_SYSTEM_TOOLS,
    KEY_AUDIO_PASSTHROUGH_PROFILE,
    KEY_AUDIO_TRANSCODE_CODEC,
    KEY_CLEANUP_REMOTE_STAGING,
    KEY_DEFERRED_PUBLISH,
    KEY_ENABLE_INTEGRITY_CHECK,
    KEY_ENCODE_TUNING_PRESET,
    KEY_FINAL_LIBRARY_PROMOTION_ENABLED,
    KEY_LIBRARY_PROFILES,
    KEY_LOCAL_BASE,
    KEY_MAX_PARALLEL_ENCODES,
    KEY_MIN_FREE_SPACE_GB,
    KEY_OUTPUT_CONTAINER,
    KEY_OUTSOURCE,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_PARALLEL_ENCODE_MODE,
    KEY_REPROCESS_ALL,
    KEY_SKIP_STABILITY_CHECK,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
    KEY_SUB_KEEP_LANGUAGES,
    KEY_TRANSIENT_FAILURE_RETRY_LIMIT,
    KEY_TX3G_EXTRACT_LANGUAGES,
    KEY_VIDEO_CODEC,
    KEY_VIDEO_PRESET,
    KEY_VIDEO_QUALITY,
)
from mediapipeline.core.paths.contracts import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult


WIZARD_REFRESH_HINT = "settings"
WIZARD_SCHEMA_VERSION = "desktop_settings_wizard.v1"
WIZARD_STATUS_SCHEMA_VERSION = "desktop_settings_wizard_status.v1"

_CPU_FALLBACK_ENCODERS = {"libx264", "libx265", "libsvtav1", "libaom-av1", "mpeg4"}
_ENCODER_BACKENDS_BY_NAME = {
    "libx264": "x264",
    "libx265": "x265",
    "libaom-av1": "libaom",
    "libsvtav1": "svtav1",
    "mpeg4": "mpeg4",
}
_ENCODER_CODECS_BY_NAME = {
    "h264_nvenc": "h264",
    "h264_qsv": "h264",
    "h264_amf": "h264",
    "libx264": "h264",
    "hevc_nvenc": "hevc",
    "hevc_qsv": "hevc",
    "hevc_amf": "hevc",
    "libx265": "hevc",
    "av1_nvenc": "av1",
    "av1_qsv": "av1",
    "av1_amf": "av1",
    "libaom-av1": "av1",
    "libsvtav1": "av1",
}



def _tool_candidate_roots(resolved: ResolvedPaths) -> list[Path]:
    roots: list[Path] = []

    pipeline_path = getattr(resolved, "pipeline_path", None)
    if pipeline_path:
        pipeline_root = Path(pipeline_path).parent
        if pipeline_root.name.casefold() == "entrypoints":
            pipeline_root = pipeline_root.parent
        roots.append(pipeline_root / "tools" / "ffmpeg" / "bin")
        roots.append(pipeline_root / "Tools" / "ffmpeg" / "bin")

    workspace_root = Path(getattr(resolved, "workspace_root", "."))
    roots.append(workspace_root / "ops" / "pipeline" / "tools" / "ffmpeg" / "bin")
    roots.append(workspace_root / "Tools" / "ffmpeg" / "bin")

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _candidate(path: Path, source: str) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists(), "source": source}


def _tool_status(raw_path: Any) -> dict[str, Any]:
    path_text = _path_text(raw_path)
    if not path_text:
        return {"path": "", "ok": False, "exists": False, "version": "", "errors": ["tool path is not configured"]}
    path = Path(path_text)
    exists = path.exists()
    is_file = path.is_file()
    if is_file:
        errors: list[str] = []
    elif exists:
        errors = ["tool path is not a file"]
    else:
        errors = ["tool path not found"]
    return {"path": str(path), "ok": exists and is_file, "exists": exists, "version": "", "errors": errors}


def _run_ffmpeg_encoder_listing(ffmpeg_path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [ffmpeg_path, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )


def _parse_ffmpeg_encoder_names(output: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        parts = line.split()
        if len(parts) < 2:
            continue
        flags, name = parts[0], parts[1]
        if not flags or flags[0] != "V" or "." not in flags:
            continue
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _encoding_capability_facts_from_encoder_names(encoder_names: list[str]) -> EncodingCapabilityFacts:
    codecs: set[str] = set()
    backends: set[str] = {"copy"}
    for name in encoder_names:
        codec = _ENCODER_CODECS_BY_NAME.get(name)
        if codec:
            codecs.add(codec)
            if codec == "hevc":
                codecs.add("h265")
        backend = _encoder_backend_for_name(name)
        if backend:
            backends.add(backend)
    return EncodingCapabilityFacts(
        supported_video_codecs=sorted(codecs),
        supported_encoder_backends=sorted(backends),
    )


def _encoder_backend_for_name(name: str) -> str:
    if name.endswith("_nvenc"):
        return "nvenc"
    if name.endswith("_qsv"):
        return "qsv"
    if name.endswith("_amf"):
        return "amf"
    return _ENCODER_BACKENDS_BY_NAME.get(name, "")


def _encoder_backend_rows(encoder_names: list[str]) -> list[dict[str, Any]]:
    by_backend: dict[str, list[str]] = {}
    for name in encoder_names:
        backend = _encoder_backend_for_name(name)
        if not backend:
            continue
        by_backend.setdefault(backend, []).append(name)
    return [
        {
            "backend": backend,
            "available": bool(by_backend.get(backend)),
            "encoders": by_backend.get(backend, []),
        }
        for backend in ("nvenc", "qsv", "amf", "x264", "x265", "libaom", "svtav1", "mpeg4")
    ]


def _language_list(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace(";", ",").split(",")]
    elif isinstance(value, list):
        parts = [str(part).strip() for part in value]
    else:
        parts = ["eng", "en", "english", "und"]
    normalized = [part for part in parts if part]
    return normalized or ["eng", "en", "english", "und"]


def _first_library_path(libraries: list[dict[str, Any]], role: str, media_kind: str) -> str:
    for library in libraries:
        if library.get("default_source_role") == role:
            return str(library.get("source_path") or "")
    for library in libraries:
        if library.get("media_kind") == media_kind:
            return str(library.get("source_path") or "")
    return ""


def _int_value(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _path_text(raw_path: Any) -> str:
    text = str(raw_path or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _path_identity_key(raw_path: Any) -> str:
    text = _path_text(raw_path)
    if not text:
        return ""
    normalized = str(Path(text)).replace("/", "\\")
    while len(normalized) > 3 and normalized.endswith("\\"):
        normalized = normalized[:-1]
    return normalized.casefold()


def _encode_tuning_for_strategy(strategy: str) -> str:
    if strategy == "cpu_fallback":
        return "compatibility"
    if strategy == "prefer_nvenc_cpu_fallback":
        return "balanced_nvenc"
    return "balanced_nvenc"


__all__ = [
    "settings_wizard_status",
    "settings_wizard_defaults",
    "preview_settings_wizard",
    "save_settings_wizard",
    "validate_wizard_payload",
    "validate_wizard_paths",
    "validate_worker_settings",
    "validate_ffmpeg_tools",
    "probe_ffmpeg_hardware",
    "tool_candidates",
    "mark_settings_wizard_completed",
    "settings_wizard_payload_from_request",
    "wizard_changes",
]

__all__ = (
    "_tool_candidate_roots",
    "_candidate",
    "_tool_status",
    "_run_ffmpeg_encoder_listing",
    "_parse_ffmpeg_encoder_names",
    "_encoding_capability_facts_from_encoder_names",
    "_encoder_backend_for_name",
    "_encoder_backend_rows",
    "_language_list",
    "_first_library_path",
    "_int_value",
    "_path_text",
    "_path_identity_key",
    "_encode_tuning_for_strategy",
)
