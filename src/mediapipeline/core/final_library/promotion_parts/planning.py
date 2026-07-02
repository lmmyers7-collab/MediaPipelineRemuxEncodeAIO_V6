from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any
from collections.abc import Iterable


@dataclass(frozen=True)
class PromotionFileTarget:
    source_path: Path
    destination_path: Path
    relative_path: Path

    def to_mapping(self) -> dict[str, str]:
        return {
            "source_path": str(self.source_path),
            "destination_path": str(self.destination_path),
            "relative_path": str(self.relative_path),
        }


@dataclass(frozen=True)
class PromotionCopyPlan:
    ok: bool
    files: tuple[PromotionFileTarget, ...] = ()
    failures: tuple[Any, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "files": [file.to_mapping() for file in self.files],
            "failures": list(self.failures),
        }


def normalized_path_key(path: str | Path | None) -> str:
    if path is None:
        return ""
    try:
        return os.path.normcase(os.path.abspath(os.fspath(path)))
    except (OSError, TypeError, ValueError):
        return str(path or "").strip().casefold()


def path_within_root(path: str | Path | None, root: str | Path | None) -> bool:
    path_key = normalized_path_key(path)
    root_key = normalized_path_key(root)
    if not path_key or not root_key:
        return False
    try:
        return os.path.commonpath([path_key, root_key]) == root_key
    except (OSError, ValueError):
        return False


def relative_path_under_root(path: str | Path | None, root: str | Path | None) -> Path | None:
    if not path_within_root(path, root):
        return None
    try:
        rel = os.path.relpath(os.path.abspath(os.fspath(path)), os.path.abspath(os.fspath(root)))
    except (OSError, TypeError, ValueError):
        return None
    if rel == "." or rel.startswith(".." + os.sep) or rel == "..":
        return None
    return Path(rel)


def match_rule_for_source(source_path: str | Path | None, rules: Iterable[Any]) -> Any | None:
    matches = [
        rule
        for rule in rules
        if getattr(rule, "enabled", False) and path_within_root(source_path, getattr(rule, "source_root", None))
    ]
    if not matches:
        return None
    return max(matches, key=lambda rule: len(normalized_path_key(getattr(rule, "source_root", None))))


def match_library_profile_for_source(source_path: str | Path | None, profiles: Iterable[Any]) -> Any | None:
    matches = [
        profile
        for profile in profiles
        if getattr(profile, "enabled", False)
        and getattr(profile, "source_root", None) is not None
        and path_within_root(source_path, getattr(profile, "source_root", None))
    ]
    if not matches:
        return None
    return max(matches, key=lambda profile: len(normalized_path_key(getattr(profile, "source_root", None))))


def destination_for_output(
    output_path: str | Path | None,
    publish_root: str | Path | None,
    destination_root: str | Path | None,
) -> Path | None:
    rel = relative_path_under_root(output_path, publish_root)
    if rel is None or destination_root is None:
        return None
    return Path(destination_root) / rel


def plan_promotion_file_targets(
    output_path: Path,
    publish_root: Path,
    destination_root: Path,
    sidecar_paths: Iterable[Path] = (),
) -> PromotionCopyPlan:
    files: list[PromotionFileTarget] = []
    destination_root_key = normalized_path_key(destination_root)
    for file_path in [output_path, *sidecar_paths]:
        rel = relative_path_under_root(file_path, publish_root)
        if rel is None:
            return PromotionCopyPlan(
                ok=False,
                failures=(f"Selected file is outside publish root: {file_path}",),
            )
        target = destination_root / rel
        if not path_within_root(target, destination_root):
            return PromotionCopyPlan(
                ok=False,
                failures=(
                    {
                        "source_path": str(file_path),
                        "destination_path": str(target),
                        "error": "Planned destination is outside final library destination root.",
                    },
                ),
            )
        if normalized_path_key(target) == destination_root_key:
            return PromotionCopyPlan(
                ok=False,
                failures=(
                    {
                        "source_path": str(file_path),
                        "destination_path": str(target),
                        "error": "Planned destination targets the final library destination root.",
                    },
                ),
            )
        files.append(PromotionFileTarget(source_path=file_path, destination_path=target, relative_path=rel))
    return PromotionCopyPlan(ok=True, files=tuple(files))


__all__ = [
    "PromotionCopyPlan",
    "PromotionFileTarget",
    "destination_for_output",
    "match_library_profile_for_source",
    "match_rule_for_source",
    "normalized_path_key",
    "path_within_root",
    "plan_promotion_file_targets",
    "relative_path_under_root",
]
