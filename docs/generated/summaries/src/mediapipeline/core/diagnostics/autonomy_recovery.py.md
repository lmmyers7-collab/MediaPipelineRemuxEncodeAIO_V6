---
file: src/mediapipeline/core/diagnostics/autonomy_recovery.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: observability
token_priority: medium
owner_domain: diagnostics
last_modified: 2026-07-02
last_reviewed: 2026-07-02
sha256: d7603cd1ea2c2531967973f66e598041bdb72f0861ac032d4815038ae77b74b7
---
# `src/mediapipeline/core/diagnostics/autonomy_recovery.py`

**Purpose:** Recovery action factories for autonomy diagnostics.

**Public symbols:** `journal_archive_action`, `pending_publish_drain_action`, `pending_publish_recovery_plan_action`
**In-repo imports:** `mediapipeline.core.diagnostics.autonomy_types`
**HTTP routes:** `/api/maintenance/archive-state-journals`, `/api/pending-publish/recovery-plan`, `/api/pipeline/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/diagnostics/autonomy_recovery.py`._
