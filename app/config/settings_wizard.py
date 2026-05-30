"""Settings setup wizard helpers.

The wizard is a guided front end over the existing settings patch pipeline.
It produces normal settings `changes` and then delegates preview/save to the
same backend-owned PSD1 validation, backup, serialization, and reload flow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.config_keys import (
    KEY_ALLOW_NO_AUDIO,
    KEY_ALLOW_SYSTEM_TOOLS,
    KEY_AUDIO_PASSTHROUGH_PROFILE,
    KEY_AUDIO_TRANSCODE_CODEC,
    KEY_CLEANUP_REMOTE_STAGING,
    KEY_DEFERRED_PUBLISH,
    KEY_ENABLE_INTEGRITY_CHECK,
    KEY_ENCODE_TUNING_PRESET,
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
from mediapipeline_desktop_app.models import ResolvedPaths


WIZARD_REFRESH_HINT = "settings"
WIZARD_SCHEMA_VERSION = "desktop_settings_wizard.v1"
WIZARD_STATUS_SCHEMA_VERSION = "desktop_settings_wizard_status.v1"


def settings_wizard_status(resolved: ResolvedPaths, service: object) -> dict[str, Any]:
    config = dict(resolved.config_data or {})
    config_exists = bool(getattr(resolved, "config_path", Path()).exists())
    app_state = _read_app_state(service)
    completed = bool(app_state.get("settings_wizard_completed", False))
    should_open = (not config_exists or not config) and not completed
    if should_open:
        status = "First-run setup recommended"
        message = "No loaded config was found. Use the Settings Wizard to build the initial PSD1 safely."
    elif completed:
        status = "Completed"
        message = "Settings Wizard was completed previously. You can reopen it for reconfiguration."
    else:
        status = "Available"
        message = "Settings Wizard is available for guided reconfiguration."
    return {
        "schema_version": WIZARD_STATUS_SCHEMA_VERSION,
        "status": status,
        "message": message,
        "should_open_wizard": should_open,
        "wizard_completed": completed,
        "config_exists": config_exists,
        "config_key_count": len(config),
    }


def settings_wizard_defaults(resolved: ResolvedPaths, service: object) -> dict[str, Any]:
    config = dict(resolved.config_data or {})
    return {
        "schema_version": WIZARD_SCHEMA_VERSION,
        "wizard": {
            "mode": "first_run" if not config else "reconfigure",
            "output_container": _value(config, KEY_OUTPUT_CONTAINER, "mkv"),
            "libraries": _default_libraries(config),
            "output": {
                "root": _value(config, KEY_OUTSOURCE, ""),
                "publish_mode": "staged_pending" if _value(config, KEY_DEFERRED_PUBLISH, True) else "immediate",
                "folder_structure": "plex_tv_folders",
                "existing_policy": "reprocess_all_once" if _value(config, KEY_REPROCESS_ALL, False) else "skip_existing",
            },
            "scratch": {"path": _value(config, KEY_LOCAL_BASE, "")},
            "tools": _tool_defaults(resolved, config),
            "hardware": {
                "strategy": "remux_when_possible",
                "preferred_codec": _value(config, KEY_VIDEO_CODEC, "hevc_nvenc"),
            },
            "audio": {
                "policy": "preserve_compatible_convert_incompatible",
                "transcode_codec": _value(config, KEY_AUDIO_TRANSCODE_CODEC, "eac3"),
                "keep_51": True,
                "prefer_first_english": True,
                "keep_all_audio_tracks": _value(config, KEY_AUDIO_PASSTHROUGH_PROFILE, "") == "lossless_passthrough",
            },
            "subtitles": {
                "policy": "keep_english_convert_supported",
                "languages": _language_list(_value(config, KEY_SUB_KEEP_LANGUAGES, ["eng", "en", "english", "und"])),
                "keep_unknown": True,
                "preserve_forced": True,
            },
            "hdr": {"policy": "preserve_hdr"},
            "workers": {
                "max_parallel_encodes": _value(config, KEY_MAX_PARALLEL_ENCODES, 1),
                "parallel_encode_mode": _value(config, KEY_PARALLEL_ENCODE_MODE, "single"),
            },
            "safety": {
                "integrity_check": _value(config, KEY_ENABLE_INTEGRITY_CHECK, True),
                "file_stability_checks": not _value(config, KEY_SKIP_STABILITY_CHECK, False),
                "pending_publish": _value(config, KEY_DEFERRED_PUBLISH, True),
                "skip_already_processed": not _value(config, KEY_REPROCESS_ALL, False),
                "retry_limit": _value(config, KEY_TRANSIENT_FAILURE_RETRY_LIMIT, 3),
                "allow_system_tools": _value(config, KEY_ALLOW_SYSTEM_TOOLS, False),
                "allow_no_audio": _value(config, KEY_ALLOW_NO_AUDIO, False),
                "cleanup_remote_staging": _value(config, KEY_CLEANUP_REMOTE_STAGING, False),
                "danger_ack": [],
            },
            "min_free_space_gb": _value(config, KEY_MIN_FREE_SPACE_GB, 50),
            "outsource_min_free_space_gb": _value(config, KEY_OUTSOURCE_MIN_FREE_SPACE_GB, 50),
        },
        "tool_candidates": tool_candidates(resolved),
        "status": settings_wizard_status(resolved, service),
    }


def preview_settings_wizard(facade: object, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
    wizard = _wizard_from_request(request)
    validation = validate_wizard_payload(wizard)
    patch_request = {"changes": wizard_changes(wizard)}
    preview = facade.preview_settings_patch(resolved, patch_request)
    data = dict(preview.data)
    data["wizard"] = _wizard_preview_payload(wizard, validation, data, writes_config=False)
    ok = bool(preview.ok) and validation["ok"]
    return CommandResult(
        command="settings.wizard.preview",
        ok=ok,
        message="Settings Wizard preview completed." if ok else "Settings Wizard preview found blockers.",
        severity="info" if ok else "error",
        warnings=list(preview.warnings) + validation["warnings"],
        errors=list(preview.errors) + validation["errors"],
        refresh_hint=WIZARD_REFRESH_HINT,
        data=data,
    )


def save_settings_wizard(facade: object, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
    if not bool(request.get("confirm_save", False)):
        return CommandResult(
            command="settings.wizard.save",
            ok=False,
            message="Settings Wizard save requires explicit confirmation.",
            severity="warning",
            warnings=["confirm_save must be true."],
            refresh_hint=WIZARD_REFRESH_HINT,
        )
    wizard = _wizard_from_request(request)
    validation = validate_wizard_payload(wizard)
    if not validation["ok"]:
        return CommandResult(
            command="settings.wizard.save",
            ok=False,
            message="Settings Wizard save blocked by validation errors.",
            severity="error",
            errors=validation["errors"],
            warnings=validation["warnings"],
            refresh_hint=WIZARD_REFRESH_HINT,
            data={"wizard": _wizard_preview_payload(wizard, validation, {}, writes_config=False)},
        )
    saved = facade.save_settings_patch(resolved, {"changes": wizard_changes(wizard), "confirm_save": True})
    data = dict(saved.data)
    completion = mark_settings_wizard_completed(getattr(facade, "service", None)) if saved.ok else {"wizard_completed": False}
    data["wizard"] = _wizard_preview_payload(wizard, validation, data, writes_config=bool(saved.ok))
    data["wizard_completion"] = completion
    return CommandResult(
        command="settings.wizard.save",
        ok=bool(saved.ok),
        message=saved.message,
        severity=saved.severity,
        warnings=list(saved.warnings) + validation["warnings"],
        errors=list(saved.errors) + validation["errors"],
        refresh_hint=WIZARD_REFRESH_HINT,
        data=data,
    )


def validate_wizard_payload(wizard: dict[str, Any]) -> dict[str, Any]:
    path_validation = validate_wizard_paths(wizard)
    worker_validation = validate_worker_settings(wizard.get("workers", {}))
    errors = [*path_validation["errors"], *worker_validation["errors"]]
    warnings = [*path_validation["warnings"], *worker_validation["warnings"]]
    safety = wizard.get("safety", {}) if isinstance(wizard.get("safety"), dict) else {}
    for key, label in (
        ("allow_system_tools", "AllowSystemTools"),
        ("allow_no_audio", "AllowNoAudio"),
        ("cleanup_remote_staging", "CleanupRemoteStaging"),
    ):
        if safety.get(key) and label not in set(safety.get("danger_ack") or []):
            warnings.append(f"{label} is enabled; acknowledge it on the Save step before relying on this config.")
    return {
        "schema_version": "desktop_settings_wizard_validation.v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "path_validation": path_validation,
        "worker_validation": worker_validation,
    }


def validate_wizard_paths(wizard: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []

    def check(label: str, raw_path: Any, *, must_exist: bool) -> None:
        text = str(raw_path or "").strip()
        row = {"label": label, "path": text, "exists": False, "is_dir": False, "status": "blocked"}
        if not text:
            errors.append(f"{label} path is required.")
        else:
            path = Path(text)
            row["exists"] = path.exists()
            row["is_dir"] = path.is_dir()
            if not path.is_absolute():
                errors.append(f"{label} path must be absolute.")
            elif must_exist and not path.exists():
                errors.append(f"{label} folder does not exist: {text}")
            elif path.exists() and not path.is_dir():
                errors.append(f"{label} path is not a folder: {text}")
            elif not must_exist and not path.exists():
                warnings.append(f"{label} folder does not exist yet: {text}")
            else:
                row["status"] = "ready"
        rows.append(row)

    for library in wizard.get("libraries", []) if isinstance(wizard.get("libraries"), list) else []:
        if library.get("enabled", True):
            check(f"Library {library.get('name') or 'source'}", library.get("source_path"), must_exist=True)
    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    scratch = wizard.get("scratch", {}) if isinstance(wizard.get("scratch"), dict) else {}
    check("Final output", output.get("root"), must_exist=False)
    check("Scratch / LocalBase", scratch.get("path"), must_exist=False)
    source_paths = {str(row.get("source_path") or "").strip().casefold() for row in wizard.get("libraries", []) if row.get("enabled", True)}
    scratch_path = str(scratch.get("path") or "").strip().casefold()
    if scratch_path and scratch_path in source_paths:
        errors.append("Scratch / LocalBase cannot be the same folder as an enabled source library.")
    return {
        "schema_version": "desktop_settings_wizard_path_validation.v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "rows": rows,
    }


def validate_worker_settings(workers: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    max_parallel = _int_value(workers.get("max_parallel_encodes"), 1)
    mode = str(workers.get("parallel_encode_mode") or "single")
    if max_parallel < 1:
        errors.append("MaxParallelEncodes must be at least 1.")
    if max_parallel > 2:
        errors.append("MaxParallelEncodes above 2 requires a separate worker-mode validation plan.")
    if mode not in {"single", "local_worker_slots"}:
        errors.append(f"ParallelEncodeMode is unsupported: {mode}")
    if mode == "local_worker_slots":
        warnings.append("Local worker slots increase disk, CPU, and GPU pressure; validate with real media before daily use.")
    return {
        "schema_version": "desktop_settings_wizard_worker_validation.v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "max_parallel_encodes": max_parallel,
        "parallel_encode_mode": mode,
    }


def validate_ffmpeg_tools(resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
    wizard = _wizard_from_request(request)
    tools = wizard.get("tools", {}) if isinstance(wizard.get("tools"), dict) else {}
    return {
        "schema_version": "desktop_settings_wizard_tools.v1",
        "ok": True,
        "ffmpeg": _tool_status(tools.get("ffmpeg_path") or _tool_defaults(resolved, {})["ffmpeg_path"]),
        "ffprobe": _tool_status(tools.get("ffprobe_path") or _tool_defaults(resolved, {})["ffprobe_path"]),
        "warnings": [],
        "errors": [],
        "blocks_unrelated_settings_save": False,
    }


def probe_ffmpeg_hardware(resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
    _ = (resolved, request)
    return {
        "schema_version": "desktop_settings_wizard_hardware_probe.v1",
        "ok": True,
        "detected_encoders": [],
        "nvenc_encoders": [],
        "cpu_fallback_encoders": [],
        "warnings": ["Hardware probe is conservative in this build; run a real-media pilot before trusting NVENC throughput."],
        "errors": [],
    }


def tool_candidates(resolved: ResolvedPaths) -> dict[str, list[dict[str, Any]]]:
    pipeline_root = Path(getattr(resolved, "pipeline_root", getattr(resolved, "workspace_root", ".")))
    bundle_bin = pipeline_root / "Tools" / "ffmpeg" / "bin"
    return {
        "ffmpeg": [_candidate(bundle_bin / "ffmpeg.exe", "portable_bundle")],
        "ffprobe": [_candidate(bundle_bin / "ffprobe.exe", "portable_bundle")],
    }


def mark_settings_wizard_completed(service: object | None) -> dict[str, Any]:
    if service is None:
        return {"wizard_completed": False, "error": "service unavailable"}
    loader = getattr(service, "load_app_state", None)
    saver = getattr(service, "save_app_state", None)
    if not callable(loader) or not callable(saver):
        return {"wizard_completed": False, "error": "app state saver unavailable"}
    try:
        state = dict(loader() or {})
        state["settings_wizard_completed"] = True
        saver(state)
    except Exception as exc:  # pragma: no cover - defensive service boundary
        return {"wizard_completed": False, "error": str(exc)}
    return {"wizard_completed": True}


def wizard_changes(wizard: dict[str, Any]) -> dict[str, Any]:
    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    scratch = wizard.get("scratch", {}) if isinstance(wizard.get("scratch"), dict) else {}
    hardware = wizard.get("hardware", {}) if isinstance(wizard.get("hardware"), dict) else {}
    audio = wizard.get("audio", {}) if isinstance(wizard.get("audio"), dict) else {}
    subtitles = wizard.get("subtitles", {}) if isinstance(wizard.get("subtitles"), dict) else {}
    workers = wizard.get("workers", {}) if isinstance(wizard.get("workers"), dict) else {}
    safety = wizard.get("safety", {}) if isinstance(wizard.get("safety"), dict) else {}
    libraries = [row for row in wizard.get("libraries", []) if isinstance(row, dict) and row.get("enabled", True)]
    changes: dict[str, Any] = {
        KEY_SOURCE_MOVIES: _first_library_path(libraries, "source_movies", "movie"),
        KEY_SOURCE_TV: _first_library_path(libraries, "source_tv", "tv"),
        KEY_OUTSOURCE: str(output.get("root") or ""),
        KEY_LOCAL_BASE: str(scratch.get("path") or ""),
        KEY_OUTPUT_CONTAINER: str(wizard.get("output_container") or "mkv"),
        KEY_DEFERRED_PUBLISH: str(output.get("publish_mode") or "staged_pending") == "staged_pending",
        KEY_REPROCESS_ALL: str(output.get("existing_policy") or "") == "reprocess_all_once",
        KEY_MIN_FREE_SPACE_GB: _int_value(wizard.get("min_free_space_gb"), 50),
        KEY_OUTSOURCE_MIN_FREE_SPACE_GB: _int_value(wizard.get("outsource_min_free_space_gb"), 50),
        KEY_VIDEO_CODEC: str(hardware.get("preferred_codec") or "hevc_nvenc"),
        KEY_VIDEO_PRESET: str(hardware.get("video_preset") or "p5"),
        KEY_VIDEO_QUALITY: _int_value(hardware.get("video_quality"), 22),
        KEY_ENCODE_TUNING_PRESET: _encode_tuning_for_strategy(str(hardware.get("strategy") or "")),
        KEY_AUDIO_PASSTHROUGH_PROFILE: "lossless_passthrough" if audio.get("keep_all_audio_tracks") else "plex_balanced",
        KEY_AUDIO_TRANSCODE_CODEC: str(audio.get("transcode_codec") or "eac3"),
        KEY_SUB_KEEP_LANGUAGES: _language_list(subtitles.get("languages") or subtitles.get("language_text")),
        KEY_TX3G_EXTRACT_LANGUAGES: _language_list(subtitles.get("languages") or subtitles.get("language_text")),
        KEY_MAX_PARALLEL_ENCODES: _int_value(workers.get("max_parallel_encodes"), 1),
        KEY_PARALLEL_ENCODE_MODE: str(workers.get("parallel_encode_mode") or "single"),
        KEY_ENABLE_INTEGRITY_CHECK: bool(safety.get("integrity_check", True)),
        KEY_SKIP_STABILITY_CHECK: not bool(safety.get("file_stability_checks", True)),
        KEY_TRANSIENT_FAILURE_RETRY_LIMIT: _int_value(safety.get("retry_limit"), 3),
        KEY_ALLOW_SYSTEM_TOOLS: bool(safety.get("allow_system_tools", False)),
        KEY_ALLOW_NO_AUDIO: bool(safety.get("allow_no_audio", False)),
        KEY_CLEANUP_REMOTE_STAGING: bool(safety.get("cleanup_remote_staging", False)),
    }
    return {key: value for key, value in changes.items() if value not in ("", None)}


def _wizard_from_request(request: dict[str, Any]) -> dict[str, Any]:
    wizard = request.get("wizard", request)
    return dict(wizard) if isinstance(wizard, dict) else {}


def _wizard_preview_payload(wizard: dict[str, Any], validation: dict[str, Any], preview_data: dict[str, Any], *, writes_config: bool) -> dict[str, Any]:
    changes = wizard_changes(wizard)
    categories = [
        {"category": "Paths", "status": "blocked" if validation["path_validation"]["errors"] else "ready", "detail": f"{len(validation['path_validation']['rows'])} path(s) checked."},
        {"category": "Workers", "status": "blocked" if validation["worker_validation"]["errors"] else "ready", "detail": validation["worker_validation"]["parallel_encode_mode"]},
        {"category": "Generated patch", "status": "ready", "detail": f"{len(changes)} setting key(s) generated."},
    ]
    return {
        "schema_version": WIZARD_SCHEMA_VERSION,
        "candidate": changes,
        "changes": changes,
        "changed_keys": preview_data.get("changed_keys", sorted(changes)),
        "writes_config": writes_config,
        "touches_media": False,
        "summary": {"categories": categories},
        "path_validation": validation["path_validation"],
        "worker_validation": validation["worker_validation"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }


def _read_app_state(service: object) -> dict[str, Any]:
    loader = getattr(service, "load_app_state", None)
    if not callable(loader):
        return {}
    try:
        state = loader()
    except Exception:
        return {}
    return dict(state or {}) if isinstance(state, dict) else {}


def _value(config: dict[str, Any], key: str, fallback: Any) -> Any:
    value = config.get(key, fallback)
    return fallback if value in (None, "") else value


def _default_libraries(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": "movies", "name": "Movies", "media_kind": "movie", "category": "movies", "default_source_role": "source_movies", "source_path": _value(config, KEY_SOURCE_MOVIES, ""), "enabled": True, "profile": "general_plex_direct_play"},
        {"id": "tv", "name": "TV", "media_kind": "tv", "category": "tv", "default_source_role": "source_tv", "source_path": _value(config, KEY_SOURCE_TV, ""), "enabled": True, "profile": "general_plex_direct_play"},
    ]


def _tool_defaults(resolved: ResolvedPaths, config: dict[str, Any]) -> dict[str, str]:
    candidates = tool_candidates(resolved)
    ffmpeg = next((row["path"] for row in candidates["ffmpeg"] if row["exists"]), "")
    ffprobe = next((row["path"] for row in candidates["ffprobe"] if row["exists"]), "")
    return {"ffmpeg_path": str(config.get("FFmpegPath") or ffmpeg), "ffprobe_path": str(config.get("FFprobePath") or ffprobe)}


def _candidate(path: Path, source: str) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists(), "source": source}


def _tool_status(raw_path: Any) -> dict[str, Any]:
    path = Path(str(raw_path or ""))
    return {"path": str(path), "ok": path.exists() and path.is_file(), "exists": path.exists(), "version": "", "errors": [] if path.exists() else ["tool path not found"]}


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
    "wizard_changes",
]
