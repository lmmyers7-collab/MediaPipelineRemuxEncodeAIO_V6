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


def preview_settings_wizard(facade: object, resolved: ResolvedPaths, request: object) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    raw_wizard = settings_wizard_payload_from_request(request)
    validation = validate_wizard_payload(raw_wizard)
    wizard = _wizard_mapping(raw_wizard)
    base_config = _wizard_base_config(facade, resolved)
    preview_resolved = _resolved_with_wizard_base(resolved, base_config)
    patch_request = _wizard_patch_request(wizard, base_config)
    preview = facade.preview_settings_patch(preview_resolved, patch_request)
    data = dict(preview.data)
    data["errors"] = list(preview.errors)
    data["warnings"] = list(preview.warnings)
    data["wizard"] = _wizard_preview_payload(wizard, validation, data, writes_config=False, base_config=base_config)
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


def save_settings_wizard(facade: object, resolved: ResolvedPaths, request: object) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    confirm_save = request.get("confirm_save") is True if isinstance(request, dict) else False
    if not confirm_save:
        return CommandResult(
            command="settings.wizard.save",
            ok=False,
            message="Settings Wizard save requires explicit confirmation.",
            severity="warning",
            warnings=["confirm_save must be true."],
            refresh_hint=WIZARD_REFRESH_HINT,
        )
    config_identity = dict(getattr(resolved, "config_identity", {}) or {})
    if config_identity.get("blocks_operations") is True:
        return settings_save_config_blocked_result(
            config_operation_block_message(config_identity, "Settings Wizard save"),
            config_operation_block_data(config_identity),
        )
    raw_wizard = settings_wizard_payload_from_request(request)
    validation = validate_wizard_payload(raw_wizard)
    wizard = _wizard_mapping(raw_wizard)
    if not validation["ok"]:
        return CommandResult(
            command="settings.wizard.save",
            ok=False,
            message="Settings Wizard save blocked by validation errors.",
            severity="error",
            errors=validation["errors"],
            warnings=validation["warnings"],
            refresh_hint=WIZARD_REFRESH_HINT,
            data={"wizard": _wizard_preview_payload(wizard, validation, {}, writes_config=False, base_config=dict(resolved.config_data or {}))},
        )
    missing_ack = _missing_wizard_danger_acknowledgements(wizard)
    if missing_ack:
        errors = [
            f"{key} is enabled and requires matching safety.danger_ack before Settings Wizard save."
            for key in missing_ack
        ]
        return CommandResult(
            command="settings.wizard.save",
            ok=False,
            message="Settings Wizard save blocked by missing danger acknowledgement.",
            severity="error",
            errors=errors,
            warnings=validation["warnings"],
            refresh_hint=WIZARD_REFRESH_HINT,
            data={"wizard": _wizard_preview_payload(wizard, validation, {}, writes_config=False, base_config=dict(resolved.config_data or {}))},
        )
    current_preview = preview_settings_wizard(facade, resolved, {"wizard": raw_wizard})
    expected_confirmation = (
        current_preview.data.get("review_confirmation")
        if isinstance(current_preview.data, dict)
        else None
    )
    submitted_confirmation = request.get("review_confirmation") if isinstance(request, dict) else None
    if isinstance(expected_confirmation, dict) and submitted_confirmation != expected_confirmation:
        return CommandResult(
            command="settings.wizard.save",
            ok=False,
            message="Settings Wizard save requires review_confirmation from the exact latest backend preview.",
            severity="warning",
            warnings=["review_confirmation is missing or does not match the current wizard/config candidate."],
            refresh_hint=WIZARD_REFRESH_HINT,
            data={"writes_config": False, "expected_review_preview_id": expected_confirmation.get("preview_id", "")},
        )
    base_config = _wizard_base_config(facade, resolved)
    if _is_missing_initial_config(resolved):
        saved = _save_initial_settings_wizard(facade, resolved, wizard, base_config)
    else:
        patch_request = _wizard_patch_request(wizard, base_config)
        saved = facade.save_settings_patch(
            resolved,
            {
                **patch_request,
                "review_confirmation": submitted_confirmation,
                "confirm_save": True,
            },
        )
    data = dict(saved.data)
    data["errors"] = list(saved.errors)
    data["warnings"] = list(saved.warnings)
    completion = mark_settings_wizard_completed(getattr(facade, "service", None)) if saved.ok else {"wizard_completed": False}
    data["wizard"] = _wizard_preview_payload(wizard, validation, data, writes_config=bool(saved.ok), base_config=base_config)
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


def validate_wizard_payload(wizard: object) -> dict[str, Any]:
    if not isinstance(wizard, dict):
        path_validation = validate_wizard_paths(wizard)
        worker_validation = validate_worker_settings({})
        errors = [*path_validation["errors"], *worker_validation["errors"]]
        warnings = [*path_validation["warnings"], *worker_validation["warnings"]]
        return {
            "schema_version": "desktop_settings_wizard_validation.v1",
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "path_validation": path_validation,
            "worker_validation": worker_validation,
        }
    wizard = _wizard_mapping(wizard)
    path_validation = validate_wizard_paths(wizard)
    worker_validation = validate_worker_settings(wizard.get("workers", {}))
    errors = [*path_validation["errors"], *worker_validation["errors"]]
    warnings = [*path_validation["warnings"], *worker_validation["warnings"]]
    safety = wizard.get("safety", {}) if isinstance(wizard.get("safety"), dict) else {}
    danger_ack = set(safety.get("danger_ack") or [])
    for key, label in (
        ("allow_system_tools", "AllowSystemTools"),
        ("allow_no_audio", "AllowNoAudio"),
        ("cleanup_remote_staging", "CleanupRemoteStaging"),
    ):
        if safety.get(key) and label not in danger_ack:
            warnings.append(f"{label} is enabled; acknowledge it on the Save step before relying on this config.")
    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    if output.get("existing_policy") == "reprocess_all_once" and "ReprocessAll" not in danger_ack:
        warnings.append("ReprocessAll is enabled; acknowledge it on the Save step before relying on this config.")
    return {
        "schema_version": "desktop_settings_wizard_validation.v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "path_validation": path_validation,
        "worker_validation": worker_validation,
    }


def _missing_wizard_danger_acknowledgements(wizard: dict[str, Any]) -> list[str]:
    safety = wizard.get("safety", {}) if isinstance(wizard.get("safety"), dict) else {}
    danger_ack = {str(item) for item in safety.get("danger_ack") or []}
    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    checks = (
        (bool(safety.get("allow_system_tools")), "AllowSystemTools"),
        (bool(safety.get("allow_no_audio")), "AllowNoAudio"),
        (bool(safety.get("cleanup_remote_staging")), "CleanupRemoteStaging"),
        (output.get("existing_policy") == "reprocess_all_once", "ReprocessAll"),
    )
    return [key for enabled, key in checks if enabled and key not in danger_ack]


def validate_wizard_paths(wizard: object) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []

    if not isinstance(wizard, dict):
        return {
            "schema_version": "desktop_settings_wizard_path_validation.v1",
            "ok": False,
            "errors": ["Settings Wizard payload must be a JSON object."],
            "warnings": [],
            "rows": [],
        }
    wizard = _wizard_mapping(wizard)

    def check(label: str, raw_path: Any, *, must_exist: bool, target: str = "") -> None:
        text = _path_text(raw_path)
        row = {
            "label": label,
            "path": text,
            "exists": False,
            "is_dir": False,
            "status": "blocked",
            "target": target,
            "will_create": False,
        }
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
                row["status"] = "will_create"
                row["will_create"] = True
                warnings.append(f"{label} folder does not exist yet and will be created during first-run save: {text}")
            else:
                row["status"] = "ready"
        rows.append(row)

    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    raw_libraries = wizard.get("libraries", [])
    if raw_libraries in (None, ""):
        raw_libraries = []
    if not isinstance(raw_libraries, list):
        errors.append("Wizard libraries must be a JSON array.")
        raw_libraries = []
    enabled_libraries: list[tuple[int, dict[str, Any]]] = []
    for index, library in enumerate(raw_libraries, start=1):
        if not isinstance(library, dict):
            errors.append(f"Wizard library row {index} must be a JSON object.")
            continue
        if library.get("enabled", True):
            enabled_libraries.append((index, library))

    for index, library in enabled_libraries:
        check(f"Library {library.get('name') or 'source'}", library.get("source_path"), must_exist=True, target=f"library:{index}:source_path")
        output_target = f"library:{index}:output_path" if library.get("output_path") else "#wizard-output-root"
        check(f"Library {library.get('name') or 'output'} output", library.get("output_path") or output.get("root"), must_exist=False, target=output_target)
        if library.get("promotion_enabled", False):
            check(f"Library {library.get('name') or 'promotion'} promotion", library.get("promotion_destination"), must_exist=False, target=f"library:{index}:promotion_destination")
    scratch = wizard.get("scratch", {}) if isinstance(wizard.get("scratch"), dict) else {}
    check("Final output", output.get("root"), must_exist=False, target="#wizard-output-root")
    check("Scratch / LocalBase", scratch.get("path"), must_exist=False, target="#wizard-scratch-path")
    source_paths: dict[str, str] = {}
    for _index, row in enabled_libraries:
        source_key = _path_identity_key(row.get("source_path"))
        if source_key:
            source_paths[source_key] = str(row.get("name") or "source")

    def block_if_source(label: str, raw_path: Any) -> None:
        path_key = _path_identity_key(raw_path)
        if path_key and path_key in source_paths:
            errors.append(f"{label} cannot be the same folder as enabled source library {source_paths[path_key]}.")

    scratch_key = _path_identity_key(scratch.get("path"))
    if scratch_key and scratch_key in source_paths:
        errors.append("Scratch / LocalBase cannot be the same folder as an enabled source library.")
    block_if_source("Final output root", output.get("root"))
    for _index, library in enabled_libraries:
        if library.get("output_path"):
            block_if_source(f"Library {library.get('name') or 'output'} output", library.get("output_path"))
        if library.get("promotion_enabled", False):
            block_if_source(
                f"Library {library.get('name') or 'promotion'} promotion destination",
                library.get("promotion_destination"),
            )
    return {
        "schema_version": "desktop_settings_wizard_path_validation.v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "rows": rows,
    }


def validate_worker_settings(workers: object) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(workers, dict):
        return {
            "schema_version": "desktop_settings_wizard_worker_validation.v1",
            "ok": False,
            "errors": ["Wizard workers must be a JSON object."],
            "warnings": [],
            "max_parallel_encodes": 1,
            "parallel_encode_mode": "single",
        }
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
    ffmpeg = _tool_status(tools.get("ffmpeg_path") or _tool_defaults(resolved, {})["ffmpeg_path"])
    ffprobe = _tool_status(tools.get("ffprobe_path") or _tool_defaults(resolved, {})["ffprobe_path"])
    errors = [f"FFmpeg: {error}" for error in ffmpeg["errors"]]
    errors.extend(f"ffprobe: {error}" for error in ffprobe["errors"])
    return {
        "schema_version": "desktop_settings_wizard_tools.v1",
        "ok": bool(ffmpeg["ok"] and ffprobe["ok"]),
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
        "warnings": [],
        "errors": errors,
        "blocks_unrelated_settings_save": False,
    }


def probe_ffmpeg_hardware(resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
    wizard = _wizard_from_request(request)
    tools = wizard.get("tools", {}) if isinstance(wizard.get("tools"), dict) else {}
    ffmpeg = _tool_status(tools.get("ffmpeg_path") or _tool_defaults(resolved, {})["ffmpeg_path"])
    warnings = [
        "Hardware probe enumerates configured FFmpeg encoder names only; it does not run a real encode. "
        "Keep CPU fallback enabled until normal queue evidence confirms throughput."
    ]
    errors = [f"FFmpeg: {error}" for error in ffmpeg["errors"]]
    detected_encoders: list[str] = []
    if not errors:
        try:
            result = _run_ffmpeg_encoder_listing(ffmpeg["path"])
        except subprocess.TimeoutExpired:
            errors.append("FFmpeg encoder probe timed out after 10 seconds.")
        except OSError as exc:
            errors.append(f"FFmpeg encoder probe failed to start: {exc}")
        else:
            output = "\n".join([str(getattr(result, "stdout", "") or ""), str(getattr(result, "stderr", "") or "")])
            if int(getattr(result, "returncode", 1) or 0) != 0:
                errors.append(f"FFmpeg encoder probe exited with code {getattr(result, 'returncode', 1)}.")
            detected_encoders = _parse_ffmpeg_encoder_names(output)
    nvenc_encoders = [name for name in detected_encoders if name.endswith("_nvenc")]
    cpu_fallback_encoders = [name for name in detected_encoders if name in _CPU_FALLBACK_ENCODERS]
    capability_facts = _encoding_capability_facts_from_encoder_names(detected_encoders)
    backend_rows = _encoder_backend_rows(detected_encoders)
    if not errors and not nvenc_encoders:
        warnings.append("No NVENC encoder was listed by configured FFmpeg.")
    if not errors and not cpu_fallback_encoders:
        warnings.append("No common CPU fallback encoder was listed by configured FFmpeg.")
    return {
        "schema_version": "desktop_settings_wizard_hardware_probe.v1",
        "ok": not errors,
        "ffmpeg": ffmpeg,
        "detected_encoders": detected_encoders,
        "nvenc_encoders": nvenc_encoders,
        "cpu_fallback_encoders": cpu_fallback_encoders,
        "capability_facts_scope": "video_encoder_names_only",
        "capability_facts": capability_facts.model_dump(),
        "encoder_backend_rows": backend_rows,
        "warnings": warnings,
        "errors": errors,
    }


def tool_candidates(resolved: ResolvedPaths) -> dict[str, list[dict[str, Any]]]:
    candidate_roots = _tool_candidate_roots(resolved)
    return {
        "ffmpeg": [_candidate(root / "ffmpeg.exe", "portable_bundle") for root in candidate_roots],
        "ffprobe": [_candidate(root / "ffprobe.exe", "portable_bundle") for root in candidate_roots],
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


def wizard_changes(wizard: dict[str, Any], base_config: dict[str, Any] | None = None) -> dict[str, Any]:
    wizard = _wizard_mapping(wizard)
    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    scratch = wizard.get("scratch", {}) if isinstance(wizard.get("scratch"), dict) else {}
    hardware = wizard.get("hardware", {}) if isinstance(wizard.get("hardware"), dict) else {}
    audio = wizard.get("audio", {}) if isinstance(wizard.get("audio"), dict) else {}
    subtitles = wizard.get("subtitles", {}) if isinstance(wizard.get("subtitles"), dict) else {}
    workers = wizard.get("workers", {}) if isinstance(wizard.get("workers"), dict) else {}
    safety = wizard.get("safety", {}) if isinstance(wizard.get("safety"), dict) else {}
    libraries = _enabled_wizard_libraries(wizard)
    outsource_root = str(output.get("root") or "")
    changes: dict[str, Any] = {
        KEY_SOURCE_MOVIES: _first_library_path(libraries, "source_movies", "movie"),
        KEY_SOURCE_TV: _first_library_path(libraries, "source_tv", "tv"),
        KEY_OUTSOURCE: outsource_root,
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
    library_profiles = library_profiles_from_wizard_payload(wizard, {**dict(base_config or {}), **changes})
    changes[KEY_LIBRARY_PROFILES] = library_profiles
    if any(profile.get("enabled", True) and profile.get("promotion_enabled") for profile in library_profiles):
        changes[KEY_FINAL_LIBRARY_PROMOTION_ENABLED] = True
    changes = normalize_library_profile_config_values(changes, require_profiles=True)
    if outsource_root:
        changes[KEY_OUTSOURCE] = outsource_root
    return {key: value for key, value in changes.items() if value not in ("", None)}


def settings_wizard_payload_from_request(request: object) -> object:
    wizard = request.get("wizard", request) if isinstance(request, dict) else request
    return wizard


def _wizard_from_request(request: object) -> dict[str, Any]:
    return _wizard_mapping(settings_wizard_payload_from_request(request))


def _wizard_mapping(wizard: object) -> dict[str, Any]:
    return _normalize_wizard_path_inputs(dict(wizard)) if isinstance(wizard, dict) else {}


def _normalize_wizard_path_inputs(wizard: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(wizard)
    for section_name, keys in (
        ("output", ("root",)),
        ("scratch", ("path",)),
        ("tools", ("ffmpeg_path", "ffprobe_path")),
    ):
        section = normalized.get(section_name)
        if not isinstance(section, dict):
            continue
        section_copy = dict(section)
        for key in keys:
            if key in section_copy:
                section_copy[key] = _path_text(section_copy.get(key))
        normalized[section_name] = section_copy

    raw_libraries = normalized.get("libraries")
    if isinstance(raw_libraries, list):
        libraries: list[Any] = []
        for row in raw_libraries:
            if not isinstance(row, dict):
                libraries.append(row)
                continue
            row_copy = dict(row)
            for key in ("source_path", "output_path", "promotion_destination"):
                if key in row_copy:
                    row_copy[key] = _path_text(row_copy.get(key))
            libraries.append(row_copy)
        normalized["libraries"] = libraries
    return normalized


def _enabled_wizard_libraries(wizard: dict[str, Any]) -> list[dict[str, Any]]:
    raw_libraries = wizard.get("libraries", [])
    if raw_libraries in (None, "") or not isinstance(raw_libraries, list):
        return []
    return [row for row in raw_libraries if isinstance(row, dict) and row.get("enabled", True)]


def _wizard_runtime_directory_targets(wizard: dict[str, Any]) -> list[tuple[str, Path]]:
    wizard = _wizard_mapping(wizard)
    targets: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(label: str, raw_path: Any) -> None:
        text = _path_text(raw_path)
        key = _path_identity_key(text)
        if not text or not key or key in seen:
            return
        seen.add(key)
        targets.append((label, Path(text)))

    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    scratch = wizard.get("scratch", {}) if isinstance(wizard.get("scratch"), dict) else {}
    add("Final output", output.get("root"))
    for library in _enabled_wizard_libraries(wizard):
        name = str(library.get("name") or "output")
        add(f"Library {name} output", library.get("output_path") or output.get("root"))
        if library.get("promotion_enabled", False):
            add(f"Library {name} promotion", library.get("promotion_destination"))
    add("Scratch / LocalBase", scratch.get("path"))
    return targets


def _ensure_wizard_runtime_directories(wizard: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for label, path in _wizard_runtime_directory_targets(wizard):
        if not path.is_absolute():
            errors.append(f"{label} folder path must be absolute before creation: {path}")
            continue
        if path.exists() and not path.is_dir():
            errors.append(f"{label} path is not a folder: {path}")
            continue
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                errors.append(f"{label} folder could not be created: {path} ({exc})")
                continue
            warnings.append(f"Created {label} folder: {path}")
        if not path.is_dir():
            errors.append(f"{label} path is not a folder after creation: {path}")
            continue
        probe_error = _directory_write_probe_error(path)
        if probe_error:
            errors.append(f"{label} folder is not writable: {path} ({probe_error})")
    return _unique_strings(errors), _unique_strings(warnings)


def _directory_write_probe_error(path: Path) -> str:
    probe_path = path / f".mediapipeline_wizard_write_probe_{uuid4().hex}.tmp"
    write_error = ""
    cleanup_error = ""
    try:
        probe_path.write_text("write probe\n", encoding="utf-8")
    except OSError as exc:
        write_error = str(exc)
    finally:
        if probe_path.exists():
            try:
                probe_path.unlink()
            except OSError as exc:
                cleanup_error = str(exc)
    return write_error or cleanup_error


def _wizard_patch_request(wizard: dict[str, Any], base_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "changes": wizard_changes(wizard, base_config),
        "preserve_outsource_root": True,
    }


def _is_missing_initial_config(resolved: ResolvedPaths) -> bool:
    config_path = Path(getattr(resolved, "config_path", ""))
    return not dict(getattr(resolved, "config_data", {}) or {}) and not config_path.is_file()


def _wizard_base_config(facade: object, resolved: ResolvedPaths) -> dict[str, Any]:
    active_config = dict(getattr(resolved, "config_data", {}) or {})
    if active_config:
        return active_config
    if not _is_missing_initial_config(resolved):
        return active_config
    return _load_first_run_template_config(facade, resolved)


def _load_first_run_template_config(facade: object, resolved: ResolvedPaths) -> dict[str, Any]:
    service = getattr(facade, "service", None)
    loader = getattr(service, "load_config_data", None)
    if not callable(loader):
        return {}
    for candidate in config_template_candidates(Path(resolved.app_root), Path(resolved.workspace_root)):
        if not candidate.is_file():
            continue
        try:
            data = dict(loader(candidate, resolved.powershell_host) or {})
        except Exception:
            continue
        if data:
            return data
    return {}


def _resolved_with_wizard_base(resolved: ResolvedPaths, base_config: dict[str, Any]) -> ResolvedPaths:
    if not base_config or dict(getattr(resolved, "config_data", {}) or {}):
        return resolved
    return replace(resolved, config_data=dict(base_config), config_identity={})


def _first_run_candidate_errors(candidate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing_required = [key for key in REQUIRED_OPERATOR_ROOT_KEYS if not str(candidate.get(key) or "").strip()]
    if missing_required:
        errors.append(f"Required operator root key(s) missing: {', '.join(missing_required)}.")
    if len(candidate) < MIN_OPERATOR_CONFIG_KEY_COUNT:
        errors.append(
            f"Initial Settings Wizard config key count {len(candidate)} is below the operator threshold {MIN_OPERATOR_CONFIG_KEY_COUNT}."
        )
    if config_looks_like_template(candidate):
        errors.append("Initial Settings Wizard config still matches the deployment template/default paths.")
    return errors


def _save_initial_settings_wizard(
    facade: object,
    resolved: ResolvedPaths,
    wizard: dict[str, Any],
    base_config: dict[str, Any],
) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    if not base_config:
        message = "Settings Wizard first-run save could not load the bundled config template."
        return CommandResult(
            command="settings.save_patch",
            ok=False,
            message=message,
            severity="error",
            errors=[message],
            refresh_hint=WIZARD_REFRESH_HINT,
            data={"writes_config": False, "config_path": str(resolved.config_path)},
        )
    if Path(resolved.config_path).exists():
        message = f"Settings Wizard first-run save refused to overwrite existing config: {resolved.config_path}"
        return CommandResult(
            command="settings.save_patch",
            ok=False,
            message=message,
            severity="error",
            errors=[message],
            refresh_hint=WIZARD_REFRESH_HINT,
            data={"writes_config": False, "config_path": str(resolved.config_path)},
        )

    candidate_builder = getattr(facade, "_settings_patch_candidate", None)
    service = getattr(facade, "service", None)
    serializer = getattr(service, "serialize_psd1_document", None)
    saver = getattr(service, "save_config_document", None)
    if not callable(candidate_builder) or not callable(serializer) or not callable(saver):
        return settings_save_service_unavailable_result()

    acquire_lock = getattr(facade, "_acquire_settings_save_lock", None)
    release_lock = getattr(facade, "_release_settings_save_lock", None)
    lock: object | None = None
    warnings: list[str] = []
    try:
        if callable(acquire_lock):
            lock, block_message = acquire_lock()
            if block_message:
                return settings_save_busy_result(block_message)
        if Path(resolved.config_path).exists():
            message = f"Settings Wizard first-run save refused to overwrite existing config: {resolved.config_path}"
            return CommandResult(
                command="settings.save_patch",
                ok=False,
                message=message,
                severity="error",
                errors=[message],
                refresh_hint=WIZARD_REFRESH_HINT,
                data={"writes_config": False, "config_path": str(resolved.config_path)},
            )

        candidate_resolved = _resolved_with_wizard_base(resolved, base_config)
        patch = candidate_builder(
            candidate_resolved,
            _wizard_patch_request(wizard, base_config),
            command="settings.wizard.save",
        )
        if patch["fatal_result"] is not None:
            return patch["fatal_result"]
        errors = list(patch["errors"])
        warnings = list(patch["warnings"])
        errors.extend(_first_run_candidate_errors(dict(patch["merged"])))
        errors = _unique_strings(errors)
        if errors:
            return settings_save_validation_error_result(errors, warnings)
        directory_errors, directory_warnings = _ensure_wizard_runtime_directories(wizard)
        errors = _unique_strings([*errors, *directory_errors])
        warnings = _unique_strings([*warnings, *directory_warnings])
        if errors:
            return settings_save_validation_error_result(errors, warnings)

        document_text = str(serializer(patch["merged"]))
        result = saver(
            resolved.config_path,
            document_text,
            False,
            config_values=dict(patch["merged"]),
            powershell_host=resolved.powershell_host,
        )
    except Exception as exc:
        return settings_save_exception_result(exc, warnings)
    finally:
        if callable(release_lock):
            release_lock(lock)
    return settings_save_success_result(result, patch, warnings)


def _wizard_preview_payload(wizard: dict[str, Any], validation: dict[str, Any], preview_data: dict[str, Any], *, writes_config: bool, base_config: dict[str, Any] | None = None) -> dict[str, Any]:
    changes = wizard_changes(wizard, base_config)
    path_validation = validation["path_validation"]
    worker_validation = validation["worker_validation"]
    safety = wizard.get("safety", {}) if isinstance(wizard.get("safety"), dict) else {}
    output = wizard.get("output", {}) if isinstance(wizard.get("output"), dict) else {}
    active_risks = [
        label
        for enabled, label in (
            (safety.get("allow_system_tools"), "AllowSystemTools"),
            (safety.get("allow_no_audio"), "AllowNoAudio"),
            (safety.get("cleanup_remote_staging"), "CleanupRemoteStaging"),
            (output.get("existing_policy") == "reprocess_all_once", "ReprocessAll"),
        )
        if enabled
    ]
    preview_errors = [str(item) for item in preview_data.get("errors", []) if str(item).strip()]
    preview_warnings = [str(item) for item in preview_data.get("warnings", []) if str(item).strip()]
    review_status = (
        "blocked"
        if validation["errors"] or preview_errors
        else "warning"
        if validation["warnings"] or preview_warnings
        else "ready"
    )
    categories = [
        {"category": "Start", "status": "ready", "detail": f"Mode {wizard.get('mode') or 'first_run'}; container {wizard.get('output_container') or 'mkv'}."},
        {"category": "Paths", "status": "blocked" if path_validation["errors"] else "warning" if path_validation["warnings"] else "ready", "detail": f"{len(path_validation['rows'])} path(s) checked."},
        {"category": "Toolchain", "status": "blocked" if worker_validation["errors"] else "warning" if worker_validation["warnings"] else "ready", "detail": f"Worker mode {worker_validation['parallel_encode_mode']}; tool and encoder checks use bounded wizard routes."},
        {"category": "Policy", "status": "warning" if active_risks else "ready", "detail": f"Active risk option(s): {', '.join(active_risks) if active_risks else 'none'}."},
        {
            "category": "Review & Save",
            "status": review_status,
            "detail": f"{len(changes)} setting key(s) generated; {len(preview_errors)} backend blocker(s).",
        },
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
        "errors": validation["errors"] + preview_errors,
        "warnings": validation["warnings"] + preview_warnings,
    }


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


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
    return [_wizard_library_row(profile) for profile in library_profiles_from_config(config)]


def _wizard_library_row(profile: dict[str, Any]) -> dict[str, Any]:
    designation = str(profile.get("designation") or "auto").strip().casefold()
    profile_id = str(profile.get("id") or "").strip()
    return {
        "id": profile_id,
        "name": str(profile.get("name") or ("TV" if profile_id == "tv" else "Movies" if profile_id == "movies" else "Library")),
        "designation": designation if designation in {"movie", "tv", "auto"} else "auto",
        "media_kind": "tv" if designation == "tv" else "movie" if designation == "movie" else "auto",
        "category": "tv" if profile_id == "tv" else "movies" if profile_id == "movies" else designation or "auto",
        "default_source_role": "source_tv" if profile_id == "tv" else "source_movies" if profile_id == "movies" else "",
        "source_path": str(profile.get("source_path") or ""),
        "output_path": str(profile.get("output_path") or ""),
        "promotion_enabled": bool(profile.get("promotion_enabled", False)),
        "promotion_destination": str(profile.get("promotion_destination") or ""),
        "enabled": True if profile_id in {"movies", "tv"} else bool(profile.get("enabled", True)),
        "profile": "general_plex_direct_play",
        "overrides": profile.get("overrides") or {},
        "default_tracking": profile.get("default_tracking") or {},
    }


def _tool_defaults(resolved: ResolvedPaths, config: dict[str, Any]) -> dict[str, str]:
    candidates = tool_candidates(resolved)
    ffmpeg = next((row["path"] for row in candidates["ffmpeg"] if row["exists"]), "")
    ffprobe = next((row["path"] for row in candidates["ffprobe"] if row["exists"]), "")
    return {"ffmpeg_path": _path_text(config.get("FFmpegPath") or ffmpeg), "ffprobe_path": _path_text(config.get("FFprobePath") or ffprobe)}



from mediapipeline.core.config.settings_wizard_tools import *  # noqa: F403
