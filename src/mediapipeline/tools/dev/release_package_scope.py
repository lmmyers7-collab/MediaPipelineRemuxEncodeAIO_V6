"""Detect release-package exclusions so source/CI freshness checks can tolerate
intentionally-stripped files (for example a tests-excluded release package).

A normal source tree has no root ``release_manifest.json``, so these helpers
return no exclusions and behavior is unchanged. Inside a shipped release package
the manifest records which optional sets were excluded (see
``ops/scripts/release/build.ps1``); the summary-freshness, project-index, and
feature-file-map checks consult this so they do not flag deliberately-omitted
files (whose generated summaries still ship) as missing or orphaned.
"""

from __future__ import annotations

import json
from pathlib import Path


def _append_unique(prefixes: list[str], *values: str) -> None:
    for value in values:
        if value not in prefixes:
            prefixes.append(value)


def release_excluded_prefixes(repo_root: Path) -> tuple[str, ...]:
    """Return repo-relative path prefixes a shipped release package omitted.

    Returns an empty tuple when there is no root ``release_manifest.json`` (the
    normal source/CI case) or when it cannot be parsed, so callers behave exactly
    as before outside a package.
    """
    manifest_path = repo_root / "release_manifest.json"
    if not manifest_path.is_file():
        return ()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    summary = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return ()
    prefixes: list[str] = []
    _append_unique(
        prefixes,
        ".git/",
        ".github/",
        ".codex/",
        ".codex-plugin/",
        "CodexVerification/",
        "LocalBase/",
        "RunLogs/",
        "artifacts/",
        "node_modules/",
        "apps/desktop/runlogs/",
        "apps/desktop/tauri/node_modules/",
        "apps/desktop/tauri/src-tauri/gen/",
        "apps/desktop/tauri/src-tauri/target/",
        "docs/PG3CleanMachineReports/",
        "docs/reviews/",
        "docs/archive/root-artifacts/",
        "ops/pipeline/config/backups/",
    )
    if summary.get("tests_included") is False:
        # Mirrors the test-suite exclusion in ops/scripts/release/release_policy.ps1.
        _append_unique(prefixes, "tests/", "ops/pipeline/tests/")
    if summary.get("dev_docs_included") is False:
        _append_unique(prefixes, "docs/archive/docs-housekeeping/")
    if summary.get("optional_tools_included") is False:
        _append_unique(
            prefixes,
            "ops/pipeline/tools/ffmpeg/bin/ffplay.exe",
            "ops/pipeline/tools/MKVToolNix/mkvtoolnix-gui.exe",
            "ops/pipeline/tools/MKVToolNix/mkvextract.exe",
            "ops/pipeline/tools/MKVToolNix/mkvinfo.exe",
            "ops/pipeline/tools/MKVToolNix/mkvpropedit.exe",
            "ops/pipeline/tools/MKVToolNix/uninst.exe",
            "ops/pipeline/tools/MKVToolNix/MKVToolNix.url",
            "ops/pipeline/tools/MKVToolNix/tools/",
            "ops/pipeline/tools/MKVToolNix/data/",
            "ops/pipeline/tools/MKVToolNix/locale/libqt/",
        )
    if summary.get("tool_docs_included") is False:
        _append_unique(
            prefixes,
            "ops/pipeline/tools/MKVToolNix/doc/",
            "ops/pipeline/tools/MKVToolNix/examples/",
        )
    return tuple(prefixes)


def is_release_excluded_path(rel_path: str, prefixes: tuple[str, ...]) -> bool:
    """True if ``rel_path`` falls under one of the package-excluded prefixes."""
    rel = rel_path.replace("\\", "/").lstrip("/")
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in prefixes)
