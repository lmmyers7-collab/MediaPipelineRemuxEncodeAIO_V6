from __future__ import annotations

from typing import Any

from ..application.dto import CommandResult
from ..application.facade_rename_policy import (
    rename_configured_media_roots_from_resolved,
    rename_undo_manifest_root_from_resolved,
)
from .path_dialogs import select_windows_paths_with_dialog


class LocalApiRenameCommandPayloadMixin:
    def _rename_request_with_backend_authority(self, request: dict[str, Any]) -> dict[str, Any]:
        backend_owned_keys = {"_configured_media_roots", "_rename_undo_manifest_root"}
        enriched = {key: value for key, value in dict(request).items() if key not in backend_owned_keys}
        resolved_provider = getattr(self, "resolved_provider", None)
        resolved = resolved_provider() if callable(resolved_provider) else None
        if resolved is not None:
            enriched["_configured_media_roots"] = rename_configured_media_roots_from_resolved(resolved)
            undo_manifest_root = rename_undo_manifest_root_from_resolved(resolved)
            if undo_manifest_root is not None:
                enriched["_rename_undo_manifest_root"] = str(undo_manifest_root)
        return enriched

    def _rename_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.get_rename_preview(self._rename_request_with_backend_authority(request)).to_mapping()

    def _rename_browse_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        picker = getattr(self, "_rename_path_picker", None)
        selection_mode = "folder" if str(request.get("selection_mode") or "").strip().lower() == "folder" else "files"
        initial_path = str(request.get("initial_path") or "")
        if callable(picker):
            result = picker(selection_mode=selection_mode, initial_path=initial_path)
        else:
            result = select_windows_paths_with_dialog(selection_mode=selection_mode, initial_path=initial_path)
        paths = [str(path).strip() for path in result.get("paths", []) if str(path).strip()]
        canceled = bool(result.get("canceled", False))
        ok = bool(result.get("ok", False))
        if canceled:
            message = "Windows file browser canceled."
            severity = "info"
        elif ok:
            label = "folder" if selection_mode == "folder" else "file"
            message = f"Windows file browser selected {len(paths)} {label}{'' if len(paths) == 1 else 's'}."
            severity = "info"
        else:
            message = str(result.get("message") or "Windows file browser failed.")
            severity = "error"
        return CommandResult(
            command="rename.browse",
            ok=ok,
            severity=severity,
            message=message,
            errors=[str(error) for error in result.get("errors", [])],
            data={
                "paths": paths,
                "selection_mode": selection_mode,
                "canceled": canceled,
                "path_count": len(paths),
                "source": "windows_file_browser",
            },
        ).to_mapping()

    def _rename_apply_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.apply_rename_selection(self._rename_request_with_backend_authority(request)).to_mapping()
