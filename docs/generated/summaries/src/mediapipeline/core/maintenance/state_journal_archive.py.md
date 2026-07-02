---
file: src/mediapipeline/core/maintenance/state_journal_archive.py
pipeline_stage: n/a
token_priority: medium
owner_domain: maintenance
last_modified: 2026-07-02
last_reviewed: 2026-06-18
sha256: 0d6371fe28cb725e2ae210afd1fc24595b44a58a9b3cd9f91490cd4370694b53
---
# `src/mediapipeline/core/maintenance/state_journal_archive.py`

**Purpose:** Confirmed archive action for oversized runtime event journals.

**Public functions:** `archive_state_journals_payload()`, `close_readiness_blocked_archive_payload()`, `unconfirmed_state_journal_archive_payload()`
**In-repo imports:** `mediapipeline.core.diagnostics.autonomy_health`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/maintenance/state_journal_archive.py`._
