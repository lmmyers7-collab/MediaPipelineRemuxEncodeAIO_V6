---
file: src/mediapipeline/core/publish/pending_service.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-06-29
last_reviewed: 2026-06-04
sha256: 52d9f5d8a8f4dfc2f53d4fd00b6fd2bb728e5e585419471fd773f2aba786452d
---
# `src/mediapipeline/core/publish/pending_service.py`

**Purpose:** Python implementation for pending service; exposes mark_duplicate_pending_targets, pending_drain_summary_path, pending_file_inventory.

**Public symbols:** `mark_duplicate_pending_targets`, `pending_drain_summary_path`, `pending_file_inventory`, `PendingPublishServiceMixin`, `read_pending_drain_summary`
**In-repo imports:** `mediapipeline.core.paths.contracts`, `mediapipeline.core.publish.file_io`, `mediapipeline.core.publish.pending_format`, `mediapipeline.core.publish.pending_manifest`, `mediapipeline.core.publish.pending_paths`
**State/config identifiers:** `.manifest.json`, `pending_drain_summary.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/core/publish/pending_service.py`._
