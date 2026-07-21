"""Report legacy-surface removal readiness by migration family.

This is intentionally report-only by default. Use ``--strict`` with one or
more ``--family`` values when a migration slice is ready to enforce deletion.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from collections.abc import Callable, Iterable


REPO_ROOT = find_repo_root(Path(__file__))

SKIP_REFERENCE_PREFIXES = (
    ".git/",
    "docs/archive/",
    "LocalBase/",
    "apps/desktop/runtime/",
    "node_modules/",
    "docs/generated/summaries/",
)

SKIP_REFERENCE_PATHS = {
    "docs/SESSION.md",
    "src/mediapipeline/tools/dev/check_legacy_removal_readiness.py",
    "src/mediapipeline/tools/dev/check_architecture_guardrails.py",
    "src/mediapipeline/tools/lint_naming.py",
    "tests/python/desktop/test_architecture_guardrails.py",
    "tests/python/desktop/test_legacy_removal_readiness.py",
    "tests/python/tooling/test_lint_naming.py",
}

HISTORICAL_REFERENCE_GLOBS = (
    ".claude/CLAUDE.md",
    "AGENTS.md",
    "docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md",
    "CHANGELOG.md",
    "docs/DOC_TOUCH_LOG.md",
    # Compact history navigation repeats legacy symbol names by design; the
    # detailed sections live under the skipped docs/archive prefix.
    "docs/REMEDIATION_CHANGELOG.md",
    "docs/adr/*.md",
    "docs/audits/*.md",
)


@dataclass(frozen=True)
class LegacyFamily:
    name: str
    description: str
    file_globs: tuple[str, ...]
    search_terms: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceMatch:
    path: str
    category: str
    term: str


@dataclass(frozen=True)
class FamilyStatus:
    family: str
    description: str
    files: tuple[str, ...]
    references: tuple[ReferenceMatch, ...]
    file_kind_counts: tuple[tuple[str, int], ...] = ()

    @property
    def ready(self) -> bool:
        return not self.files and not self.references


LEGACY_FAMILIES: dict[str, LegacyFamily] = {
    "config_schema": LegacyFamily(
        name="config_schema",
        description="Desktop config_schema*.py compatibility modules",
        file_globs=(
            "src/mediapipeline/desktop/config_schema.py",
            "src/mediapipeline/desktop/config_schema_*.py",
        ),
        search_terms=(
            "config_schema_",
            "config_schema*.py",
            "config_schema import",
            "mediapipeline.desktop.config_schema",
        ),
    ),
    "command_payloads": LegacyFamily(
        name="command_payloads",
        description="Desktop API command_payloads*.py validation/adapter modules",
        file_globs=(
            "src/mediapipeline/desktop/api/command_payloads.py",
            "src/mediapipeline/desktop/api/command_payloads_*.py",
        ),
        search_terms=(
            "command_payloads",
            "LocalApiCommandPayloadMixin",
        ),
    ),
    "python_facades": LegacyFamily(
        name="python_facades",
        description="Flat Desktop application/facade_*.py modules",
        file_globs=("src/mediapipeline/desktop/application/facade_*.py",),
        search_terms=(
            "src/mediapipeline/desktop/application/facade_",
            "application/facade_",
            "application\\facade_",
            "mediapipeline.desktop.application.facade_",
            "from .facade_",
            "import .facade_",
            "application/facade_*.py",
            "application\\facade_*.py",
        ),
    ),
    "python_services": LegacyFamily(
        name="python_services",
        description="Flat Desktop service_*.py modules",
        file_globs=("src/mediapipeline/desktop/service_*.py",),
        search_terms=(
            "src/mediapipeline/desktop/service_",
            "mediapipeline.desktop.service_",
            "from .service_",
            "import .service_",
        ),
    ),
    "root_launchers": LegacyFamily(
        name="root_launchers",
        description="Deprecated repository-root launcher shims",
        file_globs=(
            "Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
            "Test-MediaPipelineRemuxEncodeAIO-Release.ps1",
            "Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1",
            "Verify-MediaPipelineRemuxEncodeAIO-Environment.bat",
            "Run-MediaPipelineRemuxEncodeAIO.bat",
            "Setup-MediaPipelineRemuxEncodeAIO.bat",
            "Start-MediaPipelineRemuxEncodeAIO-*.bat",
            "New-RealMediaValidationWorksheet.ps1",
        ),
        search_terms=(
            ".\\Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
            "./Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
            "`Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
            ".\\Test-MediaPipelineRemuxEncodeAIO-Release.ps1",
            "./Test-MediaPipelineRemuxEncodeAIO-Release.ps1",
            "`Test-MediaPipelineRemuxEncodeAIO-Release.ps1",
            ".\\Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1",
            ".\\Verify-MediaPipelineRemuxEncodeAIO-Environment.bat",
            ".\\Run-MediaPipelineRemuxEncodeAIO.bat",
            ".\\Setup-MediaPipelineRemuxEncodeAIO.bat",
            ".\\Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat",
            ".\\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat",
            ".\\Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat",
            ".\\New-RealMediaValidationWorksheet.ps1",
            "./New-RealMediaValidationWorksheet.ps1",
            "`New-RealMediaValidationWorksheet.ps1",
        ),
    ),
    "pipeline_root_launchers": LegacyFamily(
        name="pipeline_root_launchers",
        description="Deprecated Pipeline/ root launcher shims",
        file_globs=(
            "Pipeline/Run-MediaPipelineRemuxEncodeAIO.bat",
            "ops/pipeline/config/setupRemuxEncodeAIO.bat",
            "Pipeline/Run-MediaPipeline_chatgpt.bat",
        ),
        search_terms=(
            "Pipeline/Run-MediaPipelineRemuxEncodeAIO.bat",
            "Pipeline\\Run-MediaPipelineRemuxEncodeAIO.bat",
            "ops/pipeline/config/setupRemuxEncodeAIO.bat",
            "Pipeline\\Setup-MediaPipelineRemuxEncodeAIO.bat",
            "Pipeline/Run-MediaPipeline_chatgpt.bat",
            "Pipeline\\Run-MediaPipeline_chatgpt.bat",
        ),
    ),
    "pipeline_modules": LegacyFamily(
        name="pipeline_modules",
        description="PowerShell Pipeline/Modules/*.ps1 media engine modules",
        file_globs=("Pipeline/Modules/*.ps1",),
        search_terms=(
            "Pipeline/Modules",
            "Pipeline\\Modules",
        ),
    ),
}


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _filesystem_ls_files() -> list[str]:
    """Enumerate files by walking the filesystem when git metadata is unavailable.

    Used when ``REPO_ROOT`` is not a git work tree (for example a shipped release
    package, where the release self-test runs this check but no ``.git`` exists).
    Directories matching ``SKIP_REFERENCE_PREFIXES`` are pruned so generated,
    vendored, and runtime trees are not traversed, matching the reference scan.
    """
    skip_prefixes = tuple(prefix.rstrip("/") for prefix in SKIP_REFERENCE_PREFIXES)
    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        rel_dir = normalize_path(os.path.relpath(dirpath, REPO_ROOT))
        if rel_dir == ".":
            rel_dir = ""
        kept_dirs = []
        for name in dirnames:
            child = normalize_path(f"{rel_dir}/{name}" if rel_dir else name)
            if any(child == prefix or child.startswith(prefix + "/") for prefix in skip_prefixes):
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in filenames:
            paths.append(normalize_path(f"{rel_dir}/{name}" if rel_dir else name))
    return paths


def _git_ls_files(*, include_untracked: bool = False) -> list[str]:
    args = ["git", "ls-files"]
    if include_untracked:
        args.extend(["-co", "--exclude-standard"])
    try:
        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        # git is not installed; fall back to a filesystem scan so the check still runs.
        return _filesystem_ls_files()
    except subprocess.CalledProcessError as exc:
        # Exit 128 means REPO_ROOT is not a git work tree (for example a shipped
        # release package). Fall back to a filesystem scan rather than crashing the
        # release self-test; re-raise any other git failure.
        if exc.returncode == 128:
            return _filesystem_ls_files()
        raise
    return [normalize_path(line) for line in result.stdout.splitlines() if line.strip()]


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    rel = normalize_path(path)
    return any(fnmatchcase(rel, normalize_path(pattern)) for pattern in patterns)


def _reference_category(path: str) -> str:
    rel = normalize_path(path)
    suffix = Path(rel).suffix.lower()
    if rel.startswith("ops/release/metadata/") or rel in LEGACY_FAMILIES["root_launchers"].file_globs:
        return "release"
    if rel.startswith("apps/desktop/tauri/"):
        return "package"
    if (
        rel.startswith("tests/")
        or rel.startswith("tests/python/desktop/")
        or "/tests/" in rel.lower()
        or "/Tests/" in rel
    ):
        return "tests"
    if suffix == ".md" or rel.startswith("docs/"):
        return "docs"
    return "code"


def _is_reference_candidate(path: str) -> bool:
    rel = normalize_path(path)
    if rel in SKIP_REFERENCE_PATHS:
        return False
    if any(fnmatchcase(rel, normalize_path(pattern)) for pattern in HISTORICAL_REFERENCE_GLOBS):
        return False
    return not any(rel.startswith(prefix) for prefix in SKIP_REFERENCE_PREFIXES)


def _read_text(path: str) -> str:
    try:
        return (REPO_ROOT / path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def family_files(
    family: LegacyFamily,
    known_paths: Iterable[str],
    *,
    file_exists: Callable[[str], bool] | None = None,
) -> tuple[str, ...]:
    exists = file_exists or (lambda path: (REPO_ROOT / path).is_file())
    return tuple(
        sorted(
            path
            for path in known_paths
            if _matches_any(path, family.file_globs) and exists(path)
        )
    )


def reference_matches(
    family: LegacyFamily,
    known_paths: Iterable[str],
    family_owned_files: Iterable[str],
    *,
    read_text: Callable[[str], str] = _read_text,
) -> tuple[ReferenceMatch, ...]:
    owned = {normalize_path(path) for path in family_owned_files}
    matches: list[ReferenceMatch] = []
    for path in sorted({normalize_path(item) for item in known_paths}):
        if path in owned or not _is_reference_candidate(path):
            continue
        text = read_text(path)
        if not text:
            continue
        for term in family.search_terms:
            if term in text:
                matches.append(ReferenceMatch(path=path, category=_reference_category(path), term=term))
                break
    return tuple(matches)


def _file_kind_counts(
    family: LegacyFamily,
    files: Iterable[str],
    *,
    read_text: Callable[[str], str] = _read_text,
) -> tuple[tuple[str, int], ...]:
    if family.name != "pipeline_modules":
        return ()

    counts: dict[str, int] = {}
    for path in files:
        text = read_text(path)
        kind = "compatibility_shim" if _is_pipeline_module_shim(text) else "implementation"
        counts[kind] = counts.get(kind, 0) + 1
    return tuple(sorted(counts.items()))


def _is_pipeline_module_shim(text: str) -> bool:
    return "Compatibility shim" in text


def collect_family_statuses(
    selected_families: Iterable[str] | None = None,
    *,
    known_paths: Iterable[str] | None = None,
    read_text: Callable[[str], str] = _read_text,
    file_exists: Callable[[str], bool] | None = None,
    include_untracked: bool = False,
) -> list[FamilyStatus]:
    paths = tuple(sorted(set(_git_ls_files(include_untracked=include_untracked) if known_paths is None else known_paths)))
    names = tuple(selected_families or LEGACY_FAMILIES)
    statuses: list[FamilyStatus] = []
    for name in names:
        family = LEGACY_FAMILIES[name]
        files = family_files(family, paths, file_exists=file_exists)
        refs = reference_matches(family, paths, files, read_text=read_text)
        statuses.append(
            FamilyStatus(
                family=family.name,
                description=family.description,
                files=files,
                references=refs,
                file_kind_counts=_file_kind_counts(family, files, read_text=read_text),
            )
        )
    return statuses


def _counts_by_category(references: Iterable[ReferenceMatch]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ref in references:
        counts[ref.category] = counts.get(ref.category, 0) + 1
    return dict(sorted(counts.items()))


def render_report(statuses: Iterable[FamilyStatus], *, example_limit: int = 6) -> str:
    lines = ["Legacy removal readiness:"]
    for status in statuses:
        category_counts = _counts_by_category(status.references)
        ready_label = "ready" if status.ready else "blocked"
        counts = ", ".join(f"{name}={count}" for name, count in category_counts.items()) or "none"
        lines.append(
            f"- {status.family}: {ready_label}; {len(status.files)} file(s), "
            f"{len(status.references)} external reference(s) [{counts}]"
        )
        if status.files:
            if status.file_kind_counts:
                kind_counts = ", ".join(f"{kind}={count}" for kind, count in status.file_kind_counts)
                lines.append(f"  File kinds: {kind_counts}")
            lines.append("  Files:")
            for path in status.files[:example_limit]:
                lines.append(f"    - {path}")
            if len(status.files) > example_limit:
                lines.append(f"    - ... {len(status.files) - example_limit} more")
        if status.references:
            lines.append("  Reference examples:")
            for ref in status.references[:example_limit]:
                lines.append(f"    - {ref.path} ({ref.category}, term={ref.term})")
            if len(status.references) > example_limit:
                lines.append(f"    - ... {len(status.references) - example_limit} more")
    return "\n".join(lines)


def statuses_to_json(statuses: Iterable[FamilyStatus]) -> str:
    return json.dumps(
        {"families": [asdict(status) for status in statuses]},
        indent=2,
        sort_keys=True,
    )


def strict_failures(statuses: Iterable[FamilyStatus]) -> list[FamilyStatus]:
    return [status for status in statuses if not status.ready]


def _family_names(values: list[str]) -> list[str]:
    names: list[str] = []
    for value in values:
        for item in value.split(","):
            name = item.strip()
            if not name:
                continue
            if name not in LEGACY_FAMILIES:
                raise argparse.ArgumentTypeError(
                    f"unknown family {name!r}; choose from {', '.join(LEGACY_FAMILIES)}"
                )
            names.append(name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="Family to report; may be repeated or comma-separated. Defaults to all families.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail if selected families are not deletion-ready.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--include-untracked", action="store_true", help="Include untracked files in family counts.")
    args = parser.parse_args(argv)

    try:
        selected = _family_names(args.family) if args.family else list(LEGACY_FAMILIES)
        statuses = collect_family_statuses(selected, include_untracked=args.include_untracked)
    except (OSError, subprocess.CalledProcessError, argparse.ArgumentTypeError) as exc:
        print(f"ERROR: unable to collect legacy readiness: {exc}", file=sys.stderr)
        return 2

    print(statuses_to_json(statuses) if args.json else render_report(statuses))
    return 1 if args.strict and strict_failures(statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
