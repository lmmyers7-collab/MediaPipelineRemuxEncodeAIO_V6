from __future__ import annotations

from pathlib import Path
from typing import Callable

from .models import ResolvedPaths

RuntimeArtifactSpec = tuple[str, Path | None, list[Path]]
PathKeyFunc = Callable[[Path], str]
StateRootFunc = Callable[[Path], Path]


def runtime_state_root_for_resolved(
    resolved: ResolvedPaths,
    *,
    state_root_for_local_base: StateRootFunc,
) -> Path | None:
    if resolved.local_base:
        return state_root_for_local_base(resolved.local_base)
    return resolved.state_root


def runtime_artifact_specs(
    resolved: ResolvedPaths,
    *,
    include_pipeline: bool,
    include_audit: bool,
    state_root_for_local_base: StateRootFunc,
    normalized_path_key: PathKeyFunc,
) -> list[RuntimeArtifactSpec]:
    specs: list[RuntimeArtifactSpec] = []
    state_root = runtime_state_root_for_resolved(
        resolved,
        state_root_for_local_base=state_root_for_local_base,
    )
    progress_root = state_root / "Progress" if state_root else None
    pipeline_root = state_root / "Pipeline" if state_root else None
    local_base = resolved.local_base

    def add(label: str, target: Path | None, expected: list[Path | None]) -> None:
        specs.append((label, target, [path for path in expected if path is not None]))

    if include_pipeline:
        progress_expected = [
            progress_root / "pipeline_progress.json" if progress_root else None,
            local_base / "pipeline_progress.json" if local_base else None,
        ]
        add("pipeline progress", resolved.progress_file, progress_expected)
        add("pipeline progress", progress_expected[0], progress_expected)
        add("legacy pipeline progress", progress_expected[1], progress_expected)

        control_specs = (
            ("pause flag", "pipeline_pause.flag", resolved.pause_flag),
            ("stop flag", "pipeline_stop.flag", resolved.stop_flag),
            ("rescan flag", "pipeline_rescan.flag", resolved.rescan_flag),
        )
        for label, filename, target in control_specs:
            expected = [
                pipeline_root / filename if pipeline_root else None,
                local_base / filename if local_base else None,
            ]
            add(label, target, expected)
            add(label, expected[0], expected)
            add(f"legacy {label}", expected[1], expected)

    if include_audit:
        audit_expected = [local_base / "AuditReports" / "audit_progress.json" if local_base else None]
        if not audit_expected[0] and resolved.audit_reports_path:
            audit_expected.append(resolved.audit_reports_path / "audit_progress.json")
        audit_progress = resolved.audit_reports_path / "audit_progress.json" if resolved.audit_reports_path else None
        add("audit progress", audit_progress, audit_expected)
        add("audit progress", audit_expected[0], audit_expected)

    unique: list[RuntimeArtifactSpec] = []
    seen: set[str] = set()
    for label, target, expected in specs:
        if target is None:
            continue
        key = normalized_path_key(target)
        if key in seen:
            continue
        unique.append((label, target, expected))
        seen.add(key)
    return unique


def validate_runtime_artifact_target(
    label: str,
    path: Path,
    expected_paths: list[Path],
    *,
    normalized_path_key: PathKeyFunc,
) -> None:
    if not expected_paths:
        raise RuntimeError(f"Refusing to clear {label}; no expected runtime state paths are available.")
    expected_names = {candidate.name for candidate in expected_paths}
    if path.name not in expected_names:
        expected = ", ".join(sorted(expected_names)) or "<none>"
        raise RuntimeError(f"Refusing to clear {label} with unexpected filename: {path}. Expected: {expected}")
    expected_keys = {normalized_path_key(candidate) for candidate in expected_paths}
    if normalized_path_key(path) not in expected_keys:
        expected = ", ".join(str(candidate) for candidate in expected_paths)
        raise RuntimeError(f"Refusing to clear {label} outside expected runtime state paths: {path}. Expected paths: {expected}")


def clear_runtime_artifact_specs(
    specs: list[RuntimeArtifactSpec],
    *,
    normalized_path_key: PathKeyFunc,
) -> list[str]:
    removed: list[str] = []
    for label, path, expected_paths in specs:
        if path is None:
            continue
        validate_runtime_artifact_target(label, path, expected_paths, normalized_path_key=normalized_path_key)
        existed = path.exists()
        try:
            path.unlink(missing_ok=True)
            if existed and not path.exists():
                removed.append(label)
        except FileNotFoundError:
            continue
    return removed


def filter_runtime_artifact_specs(
    specs: list[RuntimeArtifactSpec],
    *,
    labels: set[str],
) -> list[RuntimeArtifactSpec]:
    return [spec for spec in specs if spec[0] in labels]
