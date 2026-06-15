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
    if summary.get("tests_included") is False:
        # Mirrors the test-suite exclusion in ops/scripts/release/release_policy.ps1.
        prefixes.extend(("tests/", "ops/pipeline/tests/"))
    return tuple(prefixes)


def is_release_excluded_path(rel_path: str, prefixes: tuple[str, ...]) -> bool:
    """True if ``rel_path`` falls under one of the package-excluded prefixes."""
    rel = rel_path.replace("\\", "/").lstrip("/")
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in prefixes)
