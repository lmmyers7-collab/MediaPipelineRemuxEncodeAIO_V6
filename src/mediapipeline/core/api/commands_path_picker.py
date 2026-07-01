from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.dto import CommandResult
from mediapipeline.core.processes.rerun_preview import rerun_import_csv_root
from mediapipeline.core.rename.input_classification import classify_rename_input_paths


MEDIA_FILE_EXTENSIONS = {
    ".avi",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".ts",
    ".webm",
}
MEDIA_FILE_FILTER = (
    "Media files (*.mkv;*.mp4;*.m4v;*.mov;*.avi;*.ts;*.m2ts;*.webm)|"
    "*.mkv;*.mp4;*.m4v;*.mov;*.avi;*.ts;*.m2ts;*.webm|All files (*.*)|*.*"
)
CSV_FILE_FILTER = "CSV files (*.csv)|*.csv|All files (*.*)|*.*"
EXE_FILE_FILTER = "Executable files (*.exe)|*.exe|All files (*.*)|*.*"


PATH_PICKER_TARGETS: dict[str, dict[str, Any]] = {
    "rename.source.media_file": {
        "label": "Rename source media file",
        "target_kind": "media_file",
        "selection_modes": ["files"],
        "file_filter": MEDIA_FILE_FILTER,
    },
    "rename.source.folder_files": {
        "label": "Rename source folder direct files",
        "target_kind": "folder_to_direct_files",
        "selection_modes": ["folder_files"],
        "file_filter": MEDIA_FILE_FILTER,
    },
    "launch.single_file": {
        "label": "Launch single media file",
        "target_kind": "media_file",
        "selection_modes": ["files"],
        "file_filter": MEDIA_FILE_FILTER,
    },
    "launch.rerun_csv": {
        "label": "Launch rerun CSV",
        "target_kind": "csv_file",
        "selection_modes": ["files"],
        "file_filter": CSV_FILE_FILTER,
    },
    "reports.audit_library_root": {
        "label": "Reports audit source root",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "metrics.source_root": {
        "label": "Metrics source root",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.wizard.output_root": {
        "label": "Settings wizard final output root",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.wizard.scratch_path": {
        "label": "Settings wizard scratch / LocalBase",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.wizard.ffmpeg_path": {
        "label": "Settings wizard FFmpeg executable",
        "target_kind": "executable_file",
        "selection_modes": ["files"],
        "file_filter": EXE_FILE_FILTER,
    },
    "settings.wizard.ffprobe_path": {
        "label": "Settings wizard FFprobe executable",
        "target_kind": "executable_file",
        "selection_modes": ["files"],
        "file_filter": EXE_FILE_FILTER,
    },
    "settings.wizard.library_source_path": {
        "label": "Settings wizard library source path",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.wizard.library_output_path": {
        "label": "Settings wizard library output destination",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.wizard.library_promotion_destination": {
        "label": "Settings wizard library promotion destination",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.file_safety.SourceMovies": {
        "label": "Movies source",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.file_safety.SourceTV": {
        "label": "TV source",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.file_safety.Outsource": {
        "label": "Final output",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.file_safety.LocalBase": {
        "label": "Scratch / LocalBase",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.file_safety.WatchFolderRoots": {
        "label": "Watch folder root",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.subtitle.bdpgs_ocr_tool_path": {
        "label": "BDPGS OCR tool executable",
        "target_kind": "executable_file",
        "selection_modes": ["files"],
        "file_filter": EXE_FILE_FILTER,
    },
    "settings.subtitle.bdpgs_ocr_tessdata_path": {
        "label": "BDPGS OCR tessdata folder",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.subtitle.vobsub_ocr_tool_path": {
        "label": "VobSub OCR tool executable",
        "target_kind": "executable_file",
        "selection_modes": ["files"],
        "file_filter": EXE_FILE_FILTER,
    },
    "settings.library.source_path": {
        "label": "Library source path",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.library.output_path": {
        "label": "Library output destination",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.library.promotion_destination": {
        "label": "Library promotion destination",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.final_library_promotion.source_root": {
        "label": "Final library promotion source root",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "settings.final_library_promotion.destination_root": {
        "label": "Final library promotion destination root",
        "target_kind": "folder_root",
        "selection_modes": ["folder"],
    },
    "network.path_map.from_prefix": {
        "label": "Network path map from prefix",
        "target_kind": "path_map_prefix_folder",
        "selection_modes": ["folder"],
    },
    "network.path_map.to_prefix": {
        "label": "Network path map to prefix",
        "target_kind": "path_map_prefix_folder",
        "selection_modes": ["folder"],
    },
}


def _ready_validation(target_key: str, info: dict[str, Any], paths: list[str], message: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_path_picker_validation.v1",
        "target_key": target_key,
        "label": info["label"],
        "target_kind": info["target_kind"],
        "status_state": "ready",
        "message": message,
        "paths": paths,
    }


def _blocked_validation(target_key: str, info: dict[str, Any], paths: list[str], message: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_path_picker_validation.v1",
        "target_key": target_key,
        "label": info["label"],
        "target_kind": info["target_kind"],
        "status_state": "blocked",
        "message": message,
        "paths": paths,
    }


def _path_facts(path_text: str) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "path": path_text,
        "exists": False,
        "is_absolute": False,
        "is_dir": False,
        "is_file": False,
        "suffix": "",
        "error": "",
    }
    if not path_text:
        facts["error"] = "No path was selected."
        return facts
    try:
        path = Path(path_text)
        facts["is_absolute"] = path.is_absolute()
        facts["exists"] = path.exists()
        facts["is_dir"] = path.is_dir()
        facts["is_file"] = path.is_file()
        facts["suffix"] = path.suffix.lower()
    except OSError as exc:
        facts["error"] = str(exc)
    return facts


def _validate_single_path(target_key: str, info: dict[str, Any], path_text: str) -> dict[str, Any]:
    facts = _path_facts(path_text)
    validation = _blocked_validation(target_key, info, [path_text] if path_text else [], "No path was selected.")
    validation.update(facts)
    label = info["label"]
    target_kind = info["target_kind"]
    if facts["error"]:
        validation["message"] = f"Selected {label} path could not be checked: {facts['error']}"
    elif not facts["is_absolute"]:
        validation["message"] = f"Selected {label} path is not absolute."
    elif target_kind in {"folder_root", "path_map_prefix_folder"}:
        if not facts["exists"]:
            validation["message"] = f"Selected {label} folder does not exist."
        elif not facts["is_dir"]:
            validation["message"] = f"Selected {label} path exists but is not a folder."
        else:
            validation["status_state"] = "ready"
            validation["message"] = f"Selected {label} folder exists."
    elif target_kind in {"media_file", "csv_file", "executable_file"}:
        if not facts["exists"]:
            validation["message"] = f"Selected {label} file does not exist."
        elif not facts["is_file"]:
            validation["message"] = f"Selected {label} path exists but is not a file."
        elif target_kind == "media_file" and facts["suffix"] not in MEDIA_FILE_EXTENSIONS:
            validation["message"] = f"Selected {label} file is not a supported media extension."
        elif target_kind == "csv_file" and facts["suffix"] != ".csv":
            validation["message"] = f"Selected {label} file is not a CSV file."
        elif target_kind == "executable_file" and facts["suffix"] != ".exe":
            validation["message"] = f"Selected {label} file is not an .exe executable."
        else:
            validation["status_state"] = "ready"
            validation["message"] = f"Selected {label} file exists."
    return validation


def _validate_folder_files(target_key: str, info: dict[str, Any], paths: list[str]) -> tuple[list[str], dict[str, Any]]:
    if not paths:
        return [], _blocked_validation(target_key, info, [], "No direct child files were selected.")
    classification = classify_rename_input_paths(paths)
    selected_paths = [str(path) for path in classification.media_paths]
    validation = _ready_validation(
        target_key,
        info,
        selected_paths,
        f"Selected {len(selected_paths)} media file{'' if len(selected_paths) == 1 else 's'} from folder.",
    )
    validation.update(
        {
            "raw_path_count": classification.raw_count,
            "ignored_path_count": classification.ignored_count,
            "ignored_sidecar_count": len(classification.ignored_sidecar_paths),
            "ignored_non_media_count": len(classification.ignored_non_media_paths),
            "ignored_duplicate_media_count": len(classification.ignored_duplicate_media_paths),
        }
    )
    if not selected_paths:
        validation["status_state"] = "blocked"
        validation["message"] = "The selected folder did not contain supported direct child media files."
    return selected_paths, validation


def _validate_path_picker_selection(
    target_key: str,
    info: dict[str, Any],
    paths: list[str],
) -> tuple[list[str], dict[str, Any]]:
    if info["target_kind"] == "folder_to_direct_files":
        return _validate_folder_files(target_key, info, paths)
    selected_path = paths[0] if paths else ""
    validation = _validate_single_path(target_key, info, selected_path)
    return ([selected_path] if selected_path else []), validation


def _target_default_initial_path(owner: Any, target_key: str) -> str:
    if target_key != "launch.rerun_csv":
        return ""
    resolver = getattr(owner, "_resolved", None)
    if not callable(resolver):
        return ""
    try:
        resolved = resolver()
    except Exception:
        return ""
    return str(rerun_import_csv_root(resolved) or "")


def _path_picker_initial_path(owner: Any, target_key: str, request: dict[str, Any]) -> str:
    initial_path = str(request.get("initial_path") or "").strip()
    if initial_path:
        return initial_path
    return _target_default_initial_path(owner, target_key)


class LocalApiPathPickerCommandPayloadMixin:
    def _path_picker_browse_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        target_key = str(request.get("target_key") or "").strip()
        info = PATH_PICKER_TARGETS.get(target_key)
        if info is None:
            return CommandResult(
                command="path_picker.browse",
                ok=False,
                severity="error",
                message="Path picker browse only supports allowlisted target keys.",
                errors=["unsupported_target_key"],
                data={
                    "schema_version": "desktop_path_picker_browse.v1",
                    "target_key": target_key,
                    "allowed_target_keys": sorted(PATH_PICKER_TARGETS),
                    "writes_config": False,
                    "stages_only": True,
                    "mutates_media": False,
                },
            ).to_mapping()

        allowed_modes = list(info["selection_modes"])
        default_mode = allowed_modes[0]
        requested_mode = str(request.get("selection_mode") or default_mode).strip().lower()
        if requested_mode not in allowed_modes:
            return CommandResult(
                command="path_picker.browse",
                ok=False,
                severity="error",
                message=f"{info['label']} only supports selection mode: {', '.join(allowed_modes)}.",
                errors=["unsupported_selection_mode"],
                data={
                    "schema_version": "desktop_path_picker_browse.v1",
                    "target_key": target_key,
                    "allowed_selection_modes": allowed_modes,
                    "writes_config": False,
                    "stages_only": True,
                    "mutates_media": False,
                },
            ).to_mapping()

        initial_path = _path_picker_initial_path(self, target_key, request)
        file_filter = str(request.get("file_filter") or info.get("file_filter") or "")
        picker = getattr(self, "_path_picker", None)
        picker_kwargs = {
            "selection_mode": requested_mode,
            "initial_path": initial_path,
            "dialog_title": f"Select {info['label']}",
            "dialog_description": f"Select the {info['label']}",
            "file_filter": file_filter,
        }
        if callable(picker):
            result = picker(target_key=target_key, **picker_kwargs)
        else:
            result = {
                "ok": False,
                "canceled": False,
                "selection_mode": requested_mode,
                "paths": [],
                "message": "Path picker backend adapter is unavailable.",
                "errors": ["path_picker_adapter_unavailable"],
            }

        raw_paths = [str(path).strip() for path in result.get("paths", []) if str(path).strip()]
        canceled = bool(result.get("canceled", False))
        picker_ok = bool(result.get("ok", False))
        paths, validation = _validate_path_picker_selection(target_key, info, raw_paths)
        selected_path = paths[0] if paths else ""
        validation_ready = validation.get("status_state") == "ready"
        ok = picker_ok and (canceled or validation_ready)
        if canceled:
            message = "Windows path picker canceled. No field was changed."
            severity = "info"
        elif picker_ok and validation_ready:
            message = f"Windows path picker selected {info['label']}: {selected_path or len(paths)}"
            severity = "info"
        elif picker_ok:
            message = str(validation.get("message") or "Selected path did not pass backend validation.")
            severity = "warning"
        else:
            message = str(result.get("message") or "Windows path picker failed.")
            severity = "error"
        return CommandResult(
            command="path_picker.browse",
            ok=ok,
            severity=severity,
            message=message,
            errors=[str(error) for error in result.get("errors", [])],
            data={
                "schema_version": "desktop_path_picker_browse.v1",
                "target_key": target_key,
                "label": info["label"],
                "target_kind": info["target_kind"],
                "paths": paths,
                "selected_path": selected_path,
                "selection_mode": requested_mode,
                "canceled": canceled,
                "path_count": len(paths),
                "source": "windows_file_browser",
                "validation": validation,
                "allowed_target_keys": sorted(PATH_PICKER_TARGETS),
                "allowed_selection_modes": allowed_modes,
                "writes_config": False,
                "stages_only": True,
                "launches_work": False,
                "mutates_media": False,
            },
        ).to_mapping()


__all__ = ["LocalApiPathPickerCommandPayloadMixin", "PATH_PICKER_TARGETS"]
