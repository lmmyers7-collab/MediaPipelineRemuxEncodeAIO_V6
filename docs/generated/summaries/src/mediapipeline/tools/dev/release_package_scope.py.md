---
file: src/mediapipeline/tools/dev/release_package_scope.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-15
last_reviewed: 2026-06-12
sha256: 76c26de7747b2580b3a2eabc8685bc4e4a9dcbd3be23acf0933a3d7a04ca8c25
---
# `src/mediapipeline/tools/dev/release_package_scope.py`

**Purpose:** Detect release-package exclusions so source/CI freshness checks can tolerate intentionally-stripped files (for example a tests-excluded release package). A normal source tree has no root ``release_manifest.json``, so these helpers return no exclusions and behavior is unchanged. Inside a shipped release package the manifest records which optional sets were excluded (see ``ops/scripts/release/build.ps1``); the summary-freshness, project-index, and feature-file-map checks consult this so they do not flag deliberately-omitted files (whose generated summaries still ship) as missing or orphaned.

**Public symbols:** `is_release_excluded_path`, `release_excluded_prefixes`
**State/config identifiers:** `release_manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/release_package_scope.py`._
