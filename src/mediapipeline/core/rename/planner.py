from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES, VLC_LONG_PATH_THRESHOLD
from mediapipeline.core.rename.plan_policy import (
    casefold_bool_override_map,
    casefold_override_map,
    normalize_rename_template_preset,
    rename_row_status,
    rename_template_includes_tv_episode_title,
)
from mediapipeline.core.rename.contracts import RenamePlannerServiceProtocol
from mediapipeline.core.rename.input_classification import classify_rename_input_paths
from mediapipeline.core.rename.tv import (
    build_manual_tv_hierarchy_destination,
    parse_formatted_tv_identity,
    tv_identity_key,
)
from mediapipeline.core.rename.cleaning_policy import normalize_rename_cleaning_policy


def plan_rename_paths_for_service(
    service: RenamePlannerServiceProtocol,
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
    classified_inputs = classify_rename_input_paths(paths)
    paths = classified_inputs.media_paths
    if not paths:
        return []
    media_mode = str(mode or "tv").strip().casefold()
    if media_mode not in {"tv", "movie"}:
        raise ValueError("Rename mode must be tv or movie.")
    active_template = normalize_rename_template_preset(template_preset, media_mode)
    include_tv_episode_title = rename_template_includes_tv_episode_title(active_template)
    effective_cleaning_policy = normalize_rename_cleaning_policy(
        cleaning_policy
        or {
            "movie_filter_options": movie_filter_options,
            "movie_filter_terms": movie_filter_terms,
            "remove_terms": remove_terms if media_mode == "movie" else None,
            "tv_filter_options": tv_filter_options,
            "tv_filter_terms": tv_filter_terms,
            "tv_remove_terms": remove_terms if media_mode == "tv" else None,
        }
    )

    season_number = 0
    start_episode = 0
    if media_mode == "tv":
        season_number = service.parse_rename_number(
            season_value,
            label="Season",
            prefix_pattern=r"season|s",
            minimum=0,
            maximum=99,
        )
        start_episode = service.parse_rename_number(
            start_episode_value,
            label="Start episode",
            prefix_pattern=r"episode|ep|e",
            minimum=0,
            maximum=999,
        )

    planned: list[dict[str, Any]] = []
    destination_keys: set[str] = set()
    destination_rows_by_key: dict[str, list[dict[str, Any]]] = {}
    override_map = casefold_override_map(final_name_overrides)
    force_override_map = casefold_bool_override_map(force_pipeline_name_overrides)
    movie_preview_map: dict[str, str] = {}
    movie_preview_warning = ""
    tv_preview_map: dict[str, str] = {}
    tv_preview_warning = ""
    manual_movie_template = bool(str(movie_title or "").strip() or str(movie_year or "").strip())
    if (
        media_mode == "movie"
        and use_pipeline_naming_preview
        and not manual_movie_template
    ):
        movie_preview_map, movie_preview_warning = service._load_pipeline_movie_name_previews(
            [Path(path) for path in paths],
            powershell_host=powershell_host,
            cleaning_policy=effective_cleaning_policy,
        )
    manual_tv_template = bool(str(show_name or "").strip())
    if media_mode == "tv" and use_pipeline_naming_preview and not manual_tv_template:
        tv_preview_map, tv_preview_warning = service._load_pipeline_tv_name_previews(
            [Path(path) for path in paths],
            powershell_host=powershell_host,
            cleaning_policy=effective_cleaning_policy,
        )

    for offset, raw_path in enumerate(paths):
        source = Path(raw_path)
        source_key = service._casefold_path(source)
        row_force_pipeline_name = force_override_map.get(source_key, force_pipeline_name)
        warnings: list[str] = []
        errors: list[str] = []
        confidence_reasons: list[str] = []
        sidecar_moves: list[dict[str, str]] = []
        pipeline_guess = ""
        preview_source = ""
        target_name = ""
        hierarchy_destination: dict[str, Any] | None = None
        tv_identity: dict[str, Any] | None = None
        destination_identity_key = ""
        destination = source
        mutation_root = source.parent
        matches_target = False

        try:
            if media_mode == "tv":
                pipeline_guess = tv_preview_map.get(source_key, "")
                if pipeline_guess:
                    preview_source = "pipeline_tv_preview"
                    confidence_reasons.append("Backend pipeline naming preview returned a TV filename.")
                    pipeline_guess = service.normalize_plex_filename_component(Path(pipeline_guess).stem, remove_terms) + source.suffix.lower()
                    pipeline_guess = service._apply_tv_episode_title_template(
                        pipeline_guess,
                        include_episode_title=include_tv_episode_title,
                    )
                elif manual_tv_template:
                    preview_source = "manual_tv_sequence"
                    confidence_reasons.append("Operator supplied show/season/start episode; numbering follows the current row order.")
                    pipeline_guess = service._build_tv_rename_name(
                        source,
                        show_name=show_name,
                        season_number=season_number,
                        episode_number=start_episode + offset,
                        remove_terms=remove_terms,
                        tv_filter_options=tv_filter_options,
                        tv_filter_terms=tv_filter_terms,
                        include_episode_title=include_tv_episode_title,
                    )
                else:
                    preview_source = "auto_tv_heuristic"
                    confidence_reasons.append("Auto TV scrub inferred show, season, episode, and optional title from filename/folder context.")
                    pipeline_guess = service._build_auto_tv_rename_name(
                        source,
                        season_number=season_number,
                        remove_terms=remove_terms,
                        tv_filter_options=tv_filter_options,
                        tv_filter_terms=tv_filter_terms,
                        include_episode_title=include_tv_episode_title,
                    )
                    if tv_preview_warning:
                        warnings.append(tv_preview_warning)
            else:
                pipeline_guess = movie_preview_map.get(source_key, "")
                if pipeline_guess:
                    preview_source = "pipeline_movie_preview"
                    confidence_reasons.append("Backend pipeline naming preview returned a movie filename.")
                    cleaned_preview = service._clean_pipeline_movie_name(Path(pipeline_guess).name, remove_terms, movie_filter_options, movie_filter_terms)
                    pipeline_guess = f"{cleaned_preview}{source.suffix.lower()}" if cleaned_preview else service.normalize_plex_filename_component(Path(pipeline_guess).stem, remove_terms) + source.suffix.lower()
                else:
                    preview_source = "manual_movie_template" if manual_movie_template else "movie_scrub_heuristic"
                    confidence_reasons.append(
                        "Operator supplied movie title/year fields."
                        if manual_movie_template
                        else "Movie scrub filters removed release, source, audio, size, service, and group tags."
                    )
                    pipeline_guess = service._build_movie_rename_name(
                        source,
                        movie_title=movie_title,
                        movie_year=movie_year,
                        remove_terms=remove_terms,
                        movie_filter_options=movie_filter_options,
                        movie_filter_terms=movie_filter_terms,
                    )
                    if movie_preview_warning:
                        warnings.append(movie_preview_warning)
            target_name = pipeline_guess
            manual_name = override_map.get(source_key, "")
            if manual_name:
                target_name = service._normalise_manual_final_name(source, manual_name)
                confidence_reasons.append("Selected final-name override is staged for this row.")
            if media_mode == "tv" and manual_tv_template and target_name:
                hierarchy_destination = build_manual_tv_hierarchy_destination(
                    source,
                    target_name=target_name,
                    show_name=show_name,
                    season_number=season_number,
                    remove_terms=remove_terms,
                    tv_filter_options=tv_filter_options,
                    tv_filter_terms=tv_filter_terms,
                )
            if hierarchy_destination:
                destination = Path(hierarchy_destination["destination"])
                mutation_root = Path(hierarchy_destination["mutation_root"])
                confidence_reasons.append("TV hierarchy aligns the show folder, season folder, and episode filename.")
            else:
                destination = source.with_name(target_name)
            if media_mode == "tv" and target_name:
                tv_identity = parse_formatted_tv_identity(target_name)
                if tv_identity is not None:
                    destination_identity_key = tv_identity_key(tv_identity)
        except Exception as exc:
            preview_source = preview_source or "error"
            errors.append(str(exc))

        if not source.exists():
            errors.append("source file is missing")
        elif not source.is_file():
            errors.append("source path is not a file")
        if source.suffix.lower() not in MEDIA_FILE_SUFFIXES:
            warnings.append(f"extension {source.suffix or '(none)'} is not a configured media extension")
        if service._casefold_path(source) == service._casefold_path(destination) and source.name == target_name:
            matches_target = True
        if target_name:
            key = service._casefold_path(destination)
            if key in destination_keys:
                errors.append("two selected files would produce the same destination")
            destination_keys.add(key)
            if destination.exists() and not service._resolve_same_file(destination, source):
                errors.append("destination already exists")
            if len(str(destination)) >= VLC_LONG_PATH_THRESHOLD:
                warnings.append("destination path is long; Windows tools may need long-path support")

        if rename_sidecars and target_name:
            sidecar_moves = service._plan_sidecar_moves(source, destination)
            for move in sidecar_moves:
                src = Path(move["source"])
                dst = Path(move["destination"])
                if dst.exists() and not service._resolve_same_file(src, dst):
                    errors.append(f"sidecar destination already exists: {dst.name}")
            if not sidecar_moves and row_force_pipeline_name:
                warnings.append("no existing sidecar found; force override sidecar will be created")
        if row_force_pipeline_name:
            confidence_reasons.append("Pipeline force override sidecar will be used if this row is applied.")

        status = rename_row_status(errors=errors, warnings=warnings, matches_target=matches_target)
        change_kind = "blocked"
        if status != "blocked":
            if matches_target:
                change_kind = "unchanged"
            elif (
                service._casefold_path(source.parent) == service._casefold_path(destination.parent)
                and source.name.casefold() == target_name.casefold()
            ):
                change_kind = "case_only"
            else:
                change_kind = "rename"
        if status == "blocked":
            confidence = "blocked"
            confidence_reasons.append("Blocked rows cannot be applied until errors are fixed.")
        elif status == "warning":
            confidence = "review"
            confidence_reasons.append("Warnings require operator review before applying.")
        elif preview_source in {"pipeline_tv_preview", "pipeline_movie_preview", "manual_tv_sequence", "manual_movie_template"}:
            confidence = "high"
        else:
            confidence = "medium"

        row = {
            "status": status,
            "mode": media_mode,
            "source": source,
            "destination": destination,
            "source_name": source.name,
            "source_parent": str(source.parent),
            "destination_parent": str(destination.parent),
            "mutation_root": str(mutation_root),
            "hierarchy_aligned": bool(hierarchy_destination),
            "series_folder": str(hierarchy_destination.get("series_folder", "")) if hierarchy_destination else "",
            "season_folder": str(hierarchy_destination.get("season_folder", "")) if hierarchy_destination else "",
            "pipeline_guess": pipeline_guess,
            "target_name": target_name,
            "change_kind": change_kind,
            "destination_exists": bool(destination.exists()),
            "sidecar_count": len(sidecar_moves),
            "warnings": warnings,
            "errors": errors,
            "preview_source": preview_source,
            "confidence": confidence,
            "confidence_reasons": confidence_reasons,
            "matches_target": matches_target,
            "sidecar_moves": sidecar_moves,
            "rename_sidecars": rename_sidecars,
            "force_pipeline_name": row_force_pipeline_name,
            "template_preset": active_template,
            "rename_cleaning_policy_fingerprint": effective_cleaning_policy["policy_fingerprint"],
            "tv_identity": tv_identity,
            "parsed_identity": tv_identity,
            "destination_identity_key": destination_identity_key,
        }
        planned.append(row)
        if target_name:
            destination_rows_by_key.setdefault(key, []).append(row)
    for duplicate_rows in destination_rows_by_key.values():
        if len(duplicate_rows) < 2:
            continue
        for row in duplicate_rows:
            errors = row.setdefault("errors", [])
            if "two selected files would produce the same destination" not in errors:
                errors.append("two selected files would produce the same destination")
            row["status"] = "blocked"
            row["change_kind"] = "blocked"
            row["confidence"] = "blocked"
            reasons = row.setdefault("confidence_reasons", [])
            if "Blocked rows cannot be applied until errors are fixed." not in reasons:
                reasons.append("Blocked rows cannot be applied until errors are fixed.")
    if media_mode == "tv":
        identified = [row for row in planned if isinstance(row.get("tv_identity"), dict)]
        for index, left in enumerate(identified):
            left_identity = left["tv_identity"]
            left_show = str(left_identity.get("show") or "").casefold()
            left_season = int(left_identity.get("season") or 0)
            left_start = int(left_identity.get("episode_start") or 0)
            left_end = int(left_identity.get("episode_end") or left_start)
            for right in identified[index + 1 :]:
                right_identity = right["tv_identity"]
                if str(right_identity.get("show") or "").casefold() != left_show:
                    continue
                if int(right_identity.get("season") or 0) != left_season:
                    continue
                right_start = int(right_identity.get("episode_start") or 0)
                right_end = int(right_identity.get("episode_end") or right_start)
                if left_start > right_end or right_start > left_end:
                    continue
                for row in (left, right):
                    errors = row.setdefault("errors", [])
                    if "overlapping TV episode interval" not in errors:
                        errors.append("overlapping TV episode interval")
                    row["status"] = "blocked"
                    row["change_kind"] = "blocked"
                    row["confidence"] = "blocked"
                    reasons = row.setdefault("confidence_reasons", [])
                    if "Blocked rows cannot be applied until errors are fixed." not in reasons:
                        reasons.append("Blocked rows cannot be applied until errors are fixed.")
    return planned
