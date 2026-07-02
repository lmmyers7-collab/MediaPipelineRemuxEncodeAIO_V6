from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from pathlib import Path
from typing import Any
from collections.abc import Iterable


COVERAGE_FAILURE_HINT = (
    "apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py "
    "mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### <path>"
)
COVERAGE_GIT_HINT = "Run strict coverage from a Git checkout with git available, or omit the strict coverage flag."
CANONICAL_ROOT_SEGMENTS = {
    "docs": "docs",
}


@dataclass(frozen=True)
class CoverageResult:
    scope: str
    available: bool
    changed_files: tuple[str, ...]
    covered_files: tuple[str, ...]
    uncovered_files: tuple[str, ...]
    packet_paths: tuple[str, ...]
    errors: tuple[str, ...] = ()

    @property
    def changed_count(self) -> int:
        return len(self.changed_files)

    @property
    def covered_count(self) -> int:
        return len(self.covered_files)

    @property
    def uncovered_count(self) -> int:
        return len(self.uncovered_files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "available": self.available,
            "changed_count": self.changed_count,
            "covered_count": self.covered_count,
            "uncovered_count": self.uncovered_count,
            "changed_paths": list(self.changed_files),
            "covered_paths": list(self.covered_files),
            "uncovered_paths": list(self.uncovered_files),
            "packet_paths_considered": list(self.packet_paths),
            "errors": list(self.errors),
        }


def normalize_repo_path(value: str) -> str:
    text = str(value or "").strip().strip('"').replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    text = text.strip("/")
    if not text:
        return ""
    parts = text.split("/", 1)
    root = parts[0]
    canonical_root = CANONICAL_ROOT_SEGMENTS.get(root.lower())
    if canonical_root:
        parts[0] = canonical_root
    text = "/".join(parts)
    summary_prefix = "docs/generated/summaries/"
    if text.lower().startswith(summary_prefix):
        summary_parts = text.split("/")
        if len(summary_parts) > 3:
            canonical_summary_root = CANONICAL_ROOT_SEGMENTS.get(summary_parts[3].lower())
            if canonical_summary_root:
                summary_parts[3] = canonical_summary_root
                text = "/".join(summary_parts)
    return text


def parse_git_status_short(output: str) -> list[str]:
    paths: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        path_text = line[3:] if len(line) > 3 else line[2:].strip()
        if " -> " in path_text:
            path_text = path_text.rsplit(" -> ", 1)[1]
        path = normalize_repo_path(path_text)
        if path:
            paths.append(path)
    return sorted(set(paths))


def parse_git_name_status(output: str) -> list[str]:
    paths: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            path = parts[-1]
        else:
            path = parts[-1]
        normalized = normalize_repo_path(path)
        if normalized:
            paths.append(normalized)
    return sorted(set(paths))


def _run_git(root: Path, args: list[str], *, require_git: bool) -> tuple[str, str]:
    if not (root / ".git").exists():
        message = "Git metadata is unavailable; cannot evaluate change-packet coverage."
        return "", message if require_git else ""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
    except Exception as exc:
        return "", f"Git command failed: {exc}"
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        return "", f"Git command failed: git {' '.join(args)}: {detail}"
    return result.stdout, ""


def changed_files_from_worktree(root: Path, *, require_git: bool = True) -> tuple[list[str], str]:
    output, error = _run_git(root, ["status", "--short", "--untracked-files=all"], require_git=require_git)
    if error:
        return [], error
    return parse_git_status_short(output), ""


def changed_files_from_staged(root: Path, *, require_git: bool = True) -> tuple[list[str], str]:
    output, error = _run_git(root, ["diff", "--cached", "--name-status", "-M"], require_git=require_git)
    if error:
        return [], error
    return parse_git_name_status(output), ""


def changed_files_from_diff(root: Path, base_ref: str, *, require_git: bool = True) -> tuple[list[str], str]:
    base = str(base_ref or "").strip()
    if not base:
        return [], "Base ref is required for diff coverage."
    output, error = _run_git(root, ["diff", "--name-status", "-M", f"{base}...HEAD"], require_git=require_git)
    if error:
        return [], error
    return parse_git_name_status(output), ""


def unreleased_packet_paths(root: Path) -> list[Path]:
    packet_dir = root / "ops" / "release" / "changes" / "unreleased"
    if not packet_dir.exists():
        return []
    return sorted(path for path in packet_dir.glob("*.json") if path.is_file())


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return normalize_repo_path(path.as_posix())


def _files_touched_from_packet(packet: Any) -> list[str]:
    if not isinstance(packet, dict):
        return []
    files = packet.get("files_touched")
    if not isinstance(files, list):
        return []
    return [normalize_repo_path(str(item)) for item in files if normalize_repo_path(str(item))]


def _path_covered_by_touched(path: str, touched: set[str], *, allow_directory_coverage: bool = True) -> bool:
    normalized = normalize_repo_path(path)
    if normalized in touched:
        return True
    if not allow_directory_coverage:
        return False
    return any(normalized.startswith(prefix + "/") for prefix in touched if prefix)


def files_touched_from_unreleased_packets(root: Path) -> tuple[set[str], list[str], list[str]]:
    touched: set[str] = set()
    packet_paths: list[str] = []
    errors: list[str] = []
    for path in unreleased_packet_paths(root):
        relative_path = _relative(root, path)
        packet_paths.append(relative_path)
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{relative_path}: could not load change packet for coverage: {exc}")
            continue
        touched.update(_files_touched_from_packet(packet))
    return touched, packet_paths, errors


def _index_packet_paths(root: Path) -> tuple[list[str], str]:
    output, error = _run_git(root, ["ls-files", "--cached", "--", ":(glob)ops/release/changes/unreleased/*.json"], require_git=True)
    if error:
        return [], error
    return [normalize_repo_path(line) for line in output.splitlines() if normalize_repo_path(line)], ""


def _index_file_text(root: Path, path: str) -> tuple[str, str]:
    output, error = _run_git(root, ["show", f":{path}"], require_git=True)
    return output, error


def files_touched_from_staged_unreleased_packets(root: Path) -> tuple[set[str], list[str], list[str]]:
    touched: set[str] = set()
    packet_paths, error = _index_packet_paths(root)
    errors: list[str] = [error] if error else []
    for path in packet_paths:
        text, read_error = _index_file_text(root, path)
        if read_error:
            errors.append(f"{path}: could not read staged change packet: {read_error}")
            continue
        try:
            packet = json.loads(text)
        except Exception as exc:
            errors.append(f"{path}: could not load staged change packet for coverage: {exc}")
            continue
        touched.update(_files_touched_from_packet(packet))
    return touched, packet_paths, errors


def coverage_for_paths(
    *,
    root: Path,
    scope: str,
    changed_files: Iterable[str],
    packet_source: str = "worktree",
    initial_errors: Iterable[str] = (),
    allow_directory_coverage: bool = True,
) -> CoverageResult:
    normalized_changed = sorted({normalize_repo_path(path) for path in changed_files if normalize_repo_path(path)})
    if packet_source == "index":
        touched, packet_paths, packet_errors = files_touched_from_staged_unreleased_packets(root)
    else:
        touched, packet_paths, packet_errors = files_touched_from_unreleased_packets(root)
    covered = sorted(
        path
        for path in normalized_changed
        if _path_covered_by_touched(path, touched, allow_directory_coverage=allow_directory_coverage)
    )
    uncovered = sorted(
        path
        for path in normalized_changed
        if not _path_covered_by_touched(path, touched, allow_directory_coverage=allow_directory_coverage)
    )
    errors = tuple(str(error) for error in [*initial_errors, *packet_errors] if str(error))
    return CoverageResult(
        scope=scope,
        available=not errors,
        changed_files=tuple(normalized_changed),
        covered_files=tuple(covered),
        uncovered_files=tuple(uncovered),
        packet_paths=tuple(packet_paths),
        errors=errors,
    )


def coverage_for_worktree(root: Path, *, require_git: bool = True) -> CoverageResult:
    changed, error = changed_files_from_worktree(root, require_git=require_git)
    return coverage_for_paths(
        root=root,
        scope="worktree",
        changed_files=changed,
        initial_errors=[error] if error else [],
        allow_directory_coverage=False,
    )


def coverage_for_staged(root: Path) -> CoverageResult:
    changed, error = changed_files_from_staged(root, require_git=True)
    return coverage_for_paths(
        root=root,
        scope="staged",
        changed_files=changed,
        packet_source="index",
        initial_errors=[error] if error else [],
    )


def coverage_for_diff(root: Path, base_ref: str) -> CoverageResult:
    changed, error = changed_files_from_diff(root, base_ref, require_git=True)
    return coverage_for_paths(root=root, scope=f"diff:{base_ref}", changed_files=changed, initial_errors=[error] if error else [])


def coverage_failure_lines(result: CoverageResult) -> list[str]:
    lines: list[str] = []
    for error in result.errors:
        lines.append(f"change coverage {result.scope}: {error}")
    if result.errors:
        lines.append(f"Hint: {COVERAGE_GIT_HINT}")
    if result.uncovered_files:
        coverage_mode = (
            "in files_touched of any unreleased change packet"
            if result.scope == "worktree"
            else "in files_touched of any unreleased change packet or covered by a listed directory"
        )
        lines.append(
            f"change coverage {result.scope}: {len(result.uncovered_files)} changed file(s) are not listed "
            f"{coverage_mode}"
        )
        lines.extend(f"  - {path}" for path in result.uncovered_files)
        lines.append(f"Hint: {COVERAGE_FAILURE_HINT}")
    return lines


__all__ = [
    "COVERAGE_FAILURE_HINT",
    "COVERAGE_GIT_HINT",
    "CoverageResult",
    "changed_files_from_diff",
    "changed_files_from_staged",
    "changed_files_from_worktree",
    "coverage_failure_lines",
    "coverage_for_diff",
    "coverage_for_paths",
    "coverage_for_staged",
    "coverage_for_worktree",
    "files_touched_from_staged_unreleased_packets",
    "files_touched_from_unreleased_packets",
    "normalize_repo_path",
    "parse_git_name_status",
    "parse_git_status_short",
    "unreleased_packet_paths",
]
