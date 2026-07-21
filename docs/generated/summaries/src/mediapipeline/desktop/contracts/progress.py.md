---
file: src/mediapipeline/desktop/contracts/progress.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: contracts
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 5810265d962e27520dad01f19586122d1c36cb2d126280144ef8aedd84653f88
---
# `src/mediapipeline/desktop/contracts/progress.py`

**Purpose:** Compatibility shim. Moved to `mediapipeline.core.kernel.contracts.progress` by ADR-0013 (Wave 5). Re-exports the public namespace from the new home. New code should import from `mediapipeline.core.kernel.contracts.progress` directly; removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/contracts/progress.py`._
