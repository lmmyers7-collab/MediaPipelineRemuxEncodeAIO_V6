---
file: tests/python/desktop/application_facade_test_support.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-22
last_reviewed: 2026-06-24
sha256: eea20bb9d7f2158b278f39d64c4f47264345a893cb1e304a74ce2f5bd458943d
---
# `tests/python/desktop/application_facade_test_support.py`

**Purpose:** Python implementation for application facade test support; exposes assert_namespace_export, DummyFacadeService, DummyProc.

**Public symbols:** `assert_namespace_export`, `DummyFacadeService`, `DummyProc`, `DummyWorkflowFacadeService`, `exercise_local_api_route_workflow`, `fresh_generated_at`, `LocalApiHttpTestMixin`, `served_webview_static_contract_bundle`, `write_test_media_file`
**In-repo imports:** `mediapipeline.core.completed.service`, `mediapipeline.core.processes.lifecycle`, `mediapipeline.core.publish.pending_service`, `mediapipeline.core.queue.service`, `mediapipeline.core.rename.service`, `mediapipeline.core.schedule.app_state`, `mediapipeline.desktop.api`, `mediapipeline.desktop.api.static_files`, `mediapipeline.desktop.application`, `mediapipeline.desktop.models`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/audit-results`, `/api/audit-results?priority_only=true`, `/api/audit/start`, `/api/backend/close-readiness`, `/api/commands?limit=20`, `/api/completed`, `/api/completed/open`, `/api/diagnostics/open`, `/api/failures`, `/api/failures?source=markers`, `/api/maintenance`, `/api/maintenance/completed-backfill-dry-run`, `/api/maintenance/dependency-atlas`, `/api/maintenance/dependency-atlas/open-folder`, `/api/maintenance/progress`, `/api/maintenance/release-dry-run`, `/api/pending-publish`, `/api/pending-publish/recovery-plan`, `/api/pipeline/browse-file`, `/api/pipeline/control`, `/api/pipeline/start`, `/api/queue`, `/api/rename/apply`, `/api/rename/browse`
**State/config identifiers:** `config.psd1`, `desktop_app_state.json`, `queue_snapshot.json`, `release_manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/application_facade_test_support.py`._
