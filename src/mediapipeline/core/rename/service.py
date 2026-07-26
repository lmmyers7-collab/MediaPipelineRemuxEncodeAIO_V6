from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

from mediapipeline.core.rename.apply import (
    build_rename_operations,
    pipeline_sidecar_paths_for_destination,
    read_json_dict_for_rename,
    rename_path_case_safe,
    rollback_rename_operations,
    update_pipeline_sidecar_after_rename,
    update_rename_sidecar_metadata,
    write_rename_undo_manifest,
)
from mediapipeline.core.rename.apply_runner import apply_rename_path_plan_for_service
from mediapipeline.core.rename.constants import RENAME_TOOL_SIDECAR_SCHEMA_VERSION
from mediapipeline.core.rename.discovery import discover_rename_media_files as discover_rename_media_files_helper
from mediapipeline.core.rename.movie import (
    clean_pipeline_movie_name,
    movie_filter_enabled,
    movie_filter_options_are_default,
    movie_filter_term_pattern,
    normalize_movie_filter_terms,
    normalize_movie_filter_options,
    remove_movie_filter_terms,
    strip_movie_release_groups,
    title_case_movie_name,
)
from mediapipeline.core.rename.plan_policy import (
    build_movie_rename_name as build_movie_rename_name_policy,
    normalise_manual_final_name,
)
from mediapipeline.core.rename.planner import plan_rename_paths_for_service
from mediapipeline.core.rename.preview_runner import (
    load_pipeline_movie_name_previews_for_service,
    load_pipeline_name_previews_for_service,
    load_pipeline_tv_name_previews_for_service,
    load_synthetic_pipeline_name_preview_for_service,
    naming_preview_script_path_for_service,
)
from mediapipeline.core.rename.tv import (
    apply_tv_episode_title_template,
    build_auto_tv_rename_name,
    build_tv_rename_name,
    clean_pipeline_tv_name_part,
    normalize_tv_filter_options,
    normalize_tv_filter_terms,
    rename_tv_filter_default_terms,
    extract_confident_tv_episode_title,
    resolve_tv_folder_season_info,
)
from mediapipeline.core.rename.undo_runner import undo_rename_manifest_for_service
from mediapipeline.core.rename.utils import (
    associated_sidecar_candidates,
    casefold_path,
    natural_sort_key,
    normalize_plex_filename_component,
    parse_rename_number,
    parse_rename_remove_terms,
    pipeline_sidecar_path,
    remove_default_priority_markers,
    rename_override_sidecar_path,
    resolve_same_file,
    strip_known_media_suffix,
)
from mediapipeline.core.kernel.runtime.subprocess_runner import run_capture

if TYPE_CHECKING:
    from mediapipeline.core.queue.contracts import QueueRecord


class RenameServiceMixin:
    def _normalize_movie_filter_options(self, movie_filter_options: dict[str, bool] | None = None) -> dict[str, bool]:
        return normalize_movie_filter_options(movie_filter_options)

    def _normalize_movie_filter_terms(self, movie_filter_terms: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
        return normalize_movie_filter_terms(movie_filter_terms)

    def _movie_filter_enabled(self, movie_filter_options: dict[str, bool] | None, key: str) -> bool:
        return movie_filter_enabled(movie_filter_options, key)

    def _movie_filter_options_are_default(self, movie_filter_options: dict[str, bool] | None = None) -> bool:
        return movie_filter_options_are_default(movie_filter_options)

    def _normalize_tv_filter_options(self, tv_filter_options: dict[str, bool] | None = None) -> dict[str, bool]:
        return normalize_tv_filter_options(tv_filter_options)

    def _normalize_tv_filter_terms(self, tv_filter_terms: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
        return normalize_tv_filter_terms(tv_filter_terms)

    def _rename_tv_filter_default_terms(self) -> dict[str, list[str]]:
        return rename_tv_filter_default_terms()

    def _natural_sort_key(self, path: Path) -> tuple[object, ...]:
        return natural_sort_key(path)

    def normalize_plex_filename_component(self, value: str, remove_terms: list[str] | None = None) -> str:
        return normalize_plex_filename_component(value, remove_terms)

    def parse_rename_remove_terms(self, raw: str) -> list[str]:
        return parse_rename_remove_terms(raw)

    def parse_rename_number(self, raw: str | int, *, label: str, prefix_pattern: str, minimum: int, maximum: int) -> int:
        return parse_rename_number(raw, label=label, prefix_pattern=prefix_pattern, minimum=minimum, maximum=maximum)

    def pipeline_sidecar_path(self, media_path: Path) -> Path:
        return pipeline_sidecar_path(media_path)

    def rename_override_sidecar_path(self, media_path: Path) -> Path:
        return rename_override_sidecar_path(media_path)

    def associated_sidecar_candidates(self, media_path: Path):
        return associated_sidecar_candidates(media_path)

    def discover_rename_media_files(self, folder: Path, *, recursive: bool = False) -> list[Path]:
        return discover_rename_media_files_helper(folder, recursive=recursive)

    def _casefold_path(self, path: Path) -> str:
        return casefold_path(path)

    def _resolve_same_file(self, left: Path, right: Path) -> bool:
        return resolve_same_file(left, right)

    def _plan_sidecar_moves(self, source: Path, destination: Path) -> list[dict[str, str]]:
        moves: list[dict[str, str]] = []
        for sidecar_source, mapper in self.associated_sidecar_candidates(source):
            if not sidecar_source.exists():
                continue
            sidecar_destination = mapper(destination)
            moves.append({"source": str(sidecar_source), "destination": str(sidecar_destination)})
        return moves

    def _build_tv_rename_name(
        self,
        source: Path,
        *,
        show_name: str,
        season_number: int,
        episode_number: int,
        remove_terms: list[str] | None,
        tv_filter_options: dict[str, bool] | None = None,
        tv_filter_terms: dict[str, list[str]] | None = None,
        include_episode_title: bool = True,
    ) -> str:
        return build_tv_rename_name(
            source,
            show_name=show_name,
            season_number=season_number,
            episode_number=episode_number,
            remove_terms=remove_terms,
            tv_filter_options=tv_filter_options,
            tv_filter_terms=tv_filter_terms,
            include_episode_title=include_episode_title,
        )

    def _strip_known_media_suffix(self, value: str) -> str:
        return strip_known_media_suffix(value)

    def _clean_pipeline_tv_name_part(
        self,
        value: str,
        remove_terms: list[str] | None = None,
        tv_filter_options: dict[str, bool] | None = None,
        tv_filter_terms: dict[str, list[str]] | None = None,
    ) -> str:
        return clean_pipeline_tv_name_part(value, remove_terms, tv_filter_options, tv_filter_terms)

    def _resolve_tv_folder_season_info(
        self,
        source: Path,
        remove_terms: list[str] | None = None,
        tv_filter_options: dict[str, bool] | None = None,
        tv_filter_terms: dict[str, list[str]] | None = None,
    ) -> dict[str, Any] | None:
        return resolve_tv_folder_season_info(source, remove_terms, tv_filter_options, tv_filter_terms)

    def _extract_confident_tv_episode_title(
        self,
        stem: str,
        remove_terms: list[str] | None = None,
        tv_filter_options: dict[str, bool] | None = None,
        tv_filter_terms: dict[str, list[str]] | None = None,
    ) -> str:
        return extract_confident_tv_episode_title(stem, remove_terms, tv_filter_options, tv_filter_terms)

    def _build_auto_tv_rename_name(
        self,
        source: Path,
        *,
        season_number: int,
        remove_terms: list[str] | None,
        tv_filter_options: dict[str, bool] | None = None,
        tv_filter_terms: dict[str, list[str]] | None = None,
        include_episode_title: bool = True,
    ) -> str:
        return build_auto_tv_rename_name(
            source,
            season_number=season_number,
            remove_terms=remove_terms,
            tv_filter_options=tv_filter_options,
            tv_filter_terms=tv_filter_terms,
            include_episode_title=include_episode_title,
        )

    def _apply_tv_episode_title_template(self, file_name: str, *, include_episode_title: bool) -> str:
        return apply_tv_episode_title_template(file_name, include_episode_title=include_episode_title)

    def _build_movie_rename_name(
        self,
        source: Path,
        *,
        movie_title: str,
        movie_year: str,
        remove_terms: list[str] | None,
        movie_filter_options: dict[str, bool] | None = None,
        movie_filter_terms: dict[str, list[str]] | None = None,
    ) -> str:
        return build_movie_rename_name_policy(
            source,
            movie_title=movie_title,
            movie_year=movie_year,
            remove_terms=remove_terms,
            movie_filter_options=movie_filter_options,
            movie_filter_terms=movie_filter_terms,
            normalize_component=self.normalize_plex_filename_component,
            clean_movie_name=self._clean_pipeline_movie_name,
        )

    def _remove_default_priority_markers(self, text: str) -> str:
        return remove_default_priority_markers(text)

    def _title_case_movie_name(self, value: str) -> str:
        return title_case_movie_name(value)

    def _movie_filter_term_pattern(self, term: str, *, bounded: bool = True) -> str:
        return movie_filter_term_pattern(term, bounded=bounded)

    def _remove_movie_filter_terms(self, text: str, remove_terms: list[str] | None) -> str:
        return remove_movie_filter_terms(text, remove_terms)

    def _strip_movie_release_groups(
        self,
        text: str,
        movie_filter_options: dict[str, bool] | None = None,
        movie_filter_terms: dict[str, list[str]] | None = None,
    ) -> str:
        return strip_movie_release_groups(text, movie_filter_options, movie_filter_terms)

    def _clean_pipeline_movie_name(
        self,
        file_name: str,
        remove_terms: list[str] | None = None,
        movie_filter_options: dict[str, bool] | None = None,
        movie_filter_terms: dict[str, list[str]] | None = None,
    ) -> str:
        return clean_pipeline_movie_name(file_name, remove_terms, movie_filter_options, movie_filter_terms)

    def _naming_preview_script_path(self) -> Path | None:
        return naming_preview_script_path_for_service(self)

    def _load_pipeline_name_previews(
        self,
        paths: list[Path],
        *,
        media_kind: str,
        powershell_host: str | None = None,
        timeout_seconds: int = 8,
        cleaning_policy: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, str], str]:
        return load_pipeline_name_previews_for_service(
            self,
            paths,
            media_kind=media_kind,
            powershell_host=powershell_host,
            timeout_seconds=timeout_seconds,
            run_capture_func=run_capture,
            cleaning_policy=cleaning_policy,
        )

    def _load_pipeline_movie_name_previews(
        self,
        paths: list[Path],
        *,
        powershell_host: str | None = None,
        timeout_seconds: int = 8,
        cleaning_policy: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, str], str]:
        return load_pipeline_movie_name_previews_for_service(
            self,
            paths,
            powershell_host=powershell_host,
            timeout_seconds=timeout_seconds,
            run_capture_func=run_capture,
            cleaning_policy=cleaning_policy,
        )

    def _load_pipeline_tv_name_previews(
        self,
        paths: list[Path],
        *,
        powershell_host: str | None = None,
        timeout_seconds: int = 8,
        cleaning_policy: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, str], str]:
        return load_pipeline_tv_name_previews_for_service(
            self,
            paths,
            powershell_host=powershell_host,
            timeout_seconds=timeout_seconds,
            run_capture_func=run_capture,
            cleaning_policy=cleaning_policy,
        )

    def _load_synthetic_pipeline_name_preview(
        self,
        *,
        filename: str,
        source_folder: str,
        media_kind: str,
        powershell_host: str | None = None,
        timeout_seconds: int = 8,
        cleaning_policy: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return load_synthetic_pipeline_name_preview_for_service(
            self,
            filename=filename,
            source_folder=source_folder,
            media_kind=media_kind,
            powershell_host=powershell_host,
            timeout_seconds=timeout_seconds,
            run_capture_func=run_capture,
            cleaning_policy=cleaning_policy,
        )

    def _normalise_manual_final_name(self, source: Path, value: str) -> str:
        return normalise_manual_final_name(
            source,
            value,
            normalize_component=self.normalize_plex_filename_component,
        )

    def plan_rename_paths(
        self,
        paths: list[Path],
        *,
        mode: str,
        show_name: str = "",
        season_value: str | int = "S01",
        start_episode_value: str | int = "E01",
        movie_title: str = "",
        movie_year: str = "",
        remove_terms: list[str] | None = None,
        movie_filter_options: dict[str, bool] | None = None,
        movie_filter_terms: dict[str, list[str]] | None = None,
        tv_filter_options: dict[str, bool] | None = None,
        tv_filter_terms: dict[str, list[str]] | None = None,
        final_name_overrides: dict[str, str] | None = None,
        rename_sidecars: bool = True,
        force_pipeline_name: bool = False,
        force_pipeline_name_overrides: dict[str, bool] | None = None,
        powershell_host: str | None = None,
        use_pipeline_naming_preview: bool = True,
        template_preset: str = "",
        cleaning_policy: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return plan_rename_paths_for_service(
            self,
            paths,
            mode=mode,
            show_name=show_name,
            season_value=season_value,
            start_episode_value=start_episode_value,
            movie_title=movie_title,
            movie_year=movie_year,
            remove_terms=remove_terms,
            movie_filter_options=movie_filter_options,
            movie_filter_terms=movie_filter_terms,
            tv_filter_options=tv_filter_options,
            tv_filter_terms=tv_filter_terms,
            final_name_overrides=final_name_overrides,
            rename_sidecars=rename_sidecars,
            force_pipeline_name=force_pipeline_name,
            force_pipeline_name_overrides=force_pipeline_name_overrides,
            powershell_host=powershell_host,
            use_pipeline_naming_preview=use_pipeline_naming_preview,
            template_preset=template_preset,
            cleaning_policy=cleaning_policy,
        )

    def plan_batch_tv_rename(
        self,
        records: list[QueueRecord],
        *,
        show_name: str,
        season_number: int,
        start_episode: int,
        remove_terms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not records:
            raise ValueError("Select one or more queue files to rename.")
        return self.plan_rename_paths(
            [record.source_path for record in records],
            mode="tv",
            show_name=show_name,
            season_value=season_number,
            start_episode_value=start_episode,
            remove_terms=remove_terms,
            rename_sidecars=False,
            force_pipeline_name=False,
        )

    def _rename_path_case_safe(
        self,
        source: Path,
        destination: Path,
        *,
        boundary_root: Path | None = None,
    ) -> None:
        rename_path_case_safe(source, destination, same_file=self._resolve_same_file, boundary_root=boundary_root)

    def _read_json_dict_for_rename(self, path: Path) -> dict[str, Any]:
        return read_json_dict_for_rename(path)

    def _update_rename_sidecar_metadata(
        self,
        path: Path,
        payload: dict[str, Any],
        *,
        schema_default: str | None = RENAME_TOOL_SIDECAR_SCHEMA_VERSION,
    ) -> None:
        update_rename_sidecar_metadata(path, payload, schema_default=schema_default)

    def _update_pipeline_sidecar_after_rename(self, path: Path, payload: dict[str, Any], destination: Path) -> None:
        update_pipeline_sidecar_after_rename(path, payload, destination)

    def _pipeline_sidecar_paths_for_destination(self, destination: Path) -> list[Path]:
        return pipeline_sidecar_paths_for_destination(
            destination,
            pipeline_sidecar_path=self.pipeline_sidecar_path,
            casefold_path=self._casefold_path,
        )

    def _rename_undo_manifest_root(self) -> Path | None:
        app_state_path = getattr(self, "app_state_path", None)
        app_root = getattr(self, "app_root", None)
        if app_state_path is None:
            return Path(app_root) / "State" / "RenameUndo" if app_root else None
        app_state_dir = Path(app_state_path).parent
        if app_state_dir.name.casefold() == "app":
            return app_state_dir.parent / "RenameUndo"
        if app_root and app_state_dir == Path(app_root):
            return Path(app_root) / "State" / "RenameUndo"
        return app_state_dir / "RenameUndo"

    def _write_rename_undo_manifest(self, manifest: dict[str, Any], *, root: Path | None = None) -> Path:
        return write_rename_undo_manifest(manifest, root=root or self._rename_undo_manifest_root())

    def _build_rename_operations(self, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return build_rename_operations(
            plan,
            same_file=self._resolve_same_file,
            casefold_path=self._casefold_path,
        )

    def _rollback_rename_operations(self, completed_ops: list[dict[str, Any]]) -> list[str]:
        return rollback_rename_operations(
            completed_ops,
            rename_path=self._rename_path_case_safe,
            same_file=self._resolve_same_file,
        )

    def apply_rename_path_plan(
        self,
        plan: list[dict[str, Any]],
        *,
        undo_manifest_root: Path | None = None,
    ) -> dict[str, Any]:
        return apply_rename_path_plan_for_service(self, plan, undo_manifest_root=undo_manifest_root)

    def undo_rename_manifest(
        self,
        undo_manifest: Path,
        *,
        undo_manifest_root: Path | None = None,
    ) -> dict[str, Any]:
        return undo_rename_manifest_for_service(self, undo_manifest, undo_manifest_root=undo_manifest_root)

    def apply_batch_tv_rename_plan(self, plan: list[dict[str, Any]]) -> dict[str, Any]:
        return self.apply_rename_path_plan(plan)
