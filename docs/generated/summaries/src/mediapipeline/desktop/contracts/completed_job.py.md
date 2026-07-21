---
file: src/mediapipeline/desktop/contracts/completed_job.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 1c3dc2c461fdc263037f554f541c74d2a39323363badc33e0ab0659d596d12c7
---
# `src/mediapipeline/desktop/contracts/completed_job.py`

**Purpose:** Compatibility shim. Moved to `mediapipeline.core.kernel.contracts.completed_job` by ADR-0013 (Wave 5). Re-exports the public namespace from the new home. New code should import from `mediapipeline.core.kernel.contracts.completed_job` directly; removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/contracts/completed_job.py`._
