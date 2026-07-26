---
file: src/mediapipeline/tools/dev/check_python_typing.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 69264e2d09efd56f6286d2dc1ec977db3425370725812a499d95932b8eaf2c61
---
# `src/mediapipeline/tools/dev/check_python_typing.py`

**Purpose:** Run the Phase 4 Python typing boundary check. The target set is intentionally narrow while the overhaul is in progress: backend contracts, orchestration, storage, observability, and validation code. Desktop-facing modules are migrated behind compatibility shims before they become typing-enforced.

**Public symbols:** `main`
**In-repo imports:** `mediapipeline.tools.paths`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/tools/dev/check_python_typing.py`._
