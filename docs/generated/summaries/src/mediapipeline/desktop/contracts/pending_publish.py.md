---
file: src/mediapipeline/desktop/contracts/pending_publish.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: publish
token_priority: medium
owner_domain: contracts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: e339a59a32a1681dd5fa513dc21102913f599d87bd4e87b85399e7f744794705
---
# `src/mediapipeline/desktop/contracts/pending_publish.py`

**Purpose:** Compatibility shim. Moved to `mediapipeline.core.kernel.contracts.pending_publish` by ADR-0013 (Wave 5). Re-exports the public namespace from the new home. New code should import from `mediapipeline.core.kernel.contracts.pending_publish` directly; removed in the ADR-0013 Wave 6 cleanup.

**In-repo imports:** `mediapipeline.core.kernel.contracts`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/contracts/pending_publish.py`._
