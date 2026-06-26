---
file: src/mediapipeline/core/maintenance/state_journal_archive.py
pipeline_stage: n/a
token_priority: medium
owner_domain: maintenance
last_modified: 2026-06-18
last_reviewed: 2026-06-18
sha256: 98be38fa898978bbb289297baf7743ccc57126eecc930edfdd55110c45e6be5d
---
# `src/mediapipeline/core/maintenance/state_journal_archive.py`

**Purpose:** Confirmed archive action for oversized runtime event journals.

**Public functions:** `archive_state_journals_payload()`, `close_readiness_blocked_archive_payload()`, `unconfirmed_state_journal_archive_payload()`
**In-repo imports:** `mediapipeline.core.diagnostics.autonomy_health`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/maintenance/state_journal_archive.py`._
