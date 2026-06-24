from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.desktop.api.path_dialogs import (
    select_rename_paths_from_known_paths,
    select_windows_paths_with_dialog,
)
from mediapipeline.desktop.application.dto import CommandResult
from mediapipeline.core.rename.bad_case_corpus import (
    DEFAULT_RENAME_BAD_CASE_FIXTURE,
    RenameBadCaseCorpusError,
    append_bad_rename_case_from_request,
)
from mediapipeline.core.rename.policy import (
    RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY,
    RENAME_MOVIE_FILTER_PUBLIC_REQUEST_KEYS,
    rename_cleaning_policy_from_resolved,
    rename_configured_media_roots_from_resolved,
    rename_request_with_cleaning_policy,
    rename_undo_manifest_root_from_resolved,
)


def _repo_root_from_here() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / "src").exists():
            return parent
    return Path.cwd()


class LocalApiRenameCommandPayloadMixin:
    def _rename_request_with_backend_authority(self, request: dict[str, Any], resolved: Any | None = None) -> dict[str, Any]:
        backend_owned_keys = {
            "_configured_media_roots",
            "_rename_undo_manifest_root",
            RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY,
            *RENAME_MOVIE_FILTER_PUBLIC_REQUEST_KEYS,
        }
        enriched = {key: value for key, value in dict(request).items() if key not in backend_owned_keys}
        if resolved is None:
            resolved_provider = getattr(self, "resolved_provider", None)
            resolved = resolved_provider() if callable(resolved_provider) else None
        if resolved is not None:
            enriched["_configured_media_roots"] = rename_configured_media_roots_from_resolved(resolved)
            enriched = rename_request_with_cleaning_policy(
                enriched,
                rename_cleaning_policy_from_resolved(resolved),
                source="saved",
                strip_existing=True,
            )
            undo_manifest_root = rename_undo_manifest_root_from_resolved(resolved)
            if undo_manifest_root is not None:
                enriched["_rename_undo_manifest_root"] = str(undo_manifest_root)
        return enriched

    def _rename_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.get_rename_preview(self._rename_request_with_backend_authority(request)).to_mapping()

    def _rename_browse_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        picker = getattr(self, "_rename_path_picker", None)
        raw_mode = str(request.get("selection_mode") or "").strip().lower()
        if raw_mode in ("folder", "folder_files"):
            selection_mode = raw_mode
        else:
            selection_mode = "files"
        initial_path = str(request.get("initial_path") or "")
        known_paths = [str(path).strip() for path in request.get("paths", []) if str(path).strip()] if isinstance(request.get("paths"), list) else []
        if known_paths:
            result = select_rename_paths_from_known_paths(known_paths, selection_mode=selection_mode)
            source = "dropped_paths"
        elif callable(picker):
            result = picker(selection_mode=selection_mode, initial_path=initial_path)
            source = "windows_file_browser"
        else:
            result = select_windows_paths_with_dialog(selection_mode=selection_mode, initial_path=initial_path)
            source = "windows_file_browser"
        paths = [str(path).strip() for path in result.get("paths", []) if str(path).strip()]
        canceled = bool(result.get("canceled", False))
        ok = bool(result.get("ok", False))
        ignored_path_count = int(result.get("ignored_path_count") or 0)
        ignored_sidecar_count = int(result.get("ignored_sidecar_count") or 0)
        if canceled:
            message = "Windows file browser canceled."
            severity = "info"
        elif ok:
            if source == "dropped_paths":
                message = str(result.get("message") or f"Resolved dropped path(s) to {len(paths)} media file(s).")
            elif selection_mode == "folder":
                label = "folder"
            else:
                label = "file from selected folder" if selection_mode == "folder_files" else "file"
                message = f"Windows file browser selected {len(paths)} {label}{'' if len(paths) == 1 else 's'}."
                if ignored_path_count:
                    message += (
                        f" Ignored {ignored_path_count} non-media path(s)"
                        f"{f' including {ignored_sidecar_count} sidecar path(s)' if ignored_sidecar_count else ''}."
                    )
            severity = "info"
        else:
            message = str(result.get("message") or "Windows file browser failed.")
            severity = "error"
        data = {
            "paths": paths,
            "selection_mode": selection_mode,
            "canceled": canceled,
            "path_count": len(paths),
            "raw_path_count": int(result.get("raw_path_count") or len(paths)),
            "ignored_path_count": ignored_path_count,
            "ignored_sidecar_count": ignored_sidecar_count,
            "source": source,
        }
        for key in ("ignored_non_media_count", "ignored_duplicate_media_count"):
            if key in result:
                data[key] = int(result.get(key) or 0)
        return CommandResult(
            command="rename.browse",
            ok=ok,
            severity=severity,
            message=message,
            errors=[str(error) for error in result.get("errors", [])],
            data=data,
        ).to_mapping()

    def _rename_bad_case_fixture_file(self) -> Path:
        configured = getattr(self, "_rename_bad_case_fixture_path_override", None)
        if configured is None:
            configured = getattr(self, "_rename_bad_case_fixture_path", None)
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else _repo_root_from_here() / path
        return _repo_root_from_here() / DEFAULT_RENAME_BAD_CASE_FIXTURE

    def _rename_filter_case_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            result = append_bad_rename_case_from_request(
                dict(request),
                fixture_path=self._rename_bad_case_fixture_file(),
                require_confirmation=True,
            )
        except RenameBadCaseCorpusError as exc:
            message = str(exc)
            return CommandResult(
                command="rename.filter_case.append",
                ok=False,
                severity="warning",
                message=message,
                errors=[message],
                data={"schema_version": "rename_bad_case_corpus_append.v1"},
            ).to_mapping()
        return CommandResult(
            command="rename.filter_case.append",
            ok=True,
            severity="info",
            message=f"Rename filter case logged as {result['case_id']}.",
            data=result,
        ).to_mapping()

    def _rename_apply_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved_provider = getattr(self, "resolved_provider", None)
        resolved = resolved_provider() if callable(resolved_provider) else None
        return self.facade.apply_rename_selection(
            self._rename_request_with_backend_authority(request, resolved=resolved),
            resolved=resolved,
        ).to_mapping()

    def _rename_undo_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved_provider = getattr(self, "resolved_provider", None)
        resolved = resolved_provider() if callable(resolved_provider) else None
        return self.facade.undo_rename_selection(
            self._rename_request_with_backend_authority(request, resolved=resolved),
            resolved=resolved,
        ).to_mapping()
