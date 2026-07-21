---
file: tests/python/desktop/test_application_facade_local_api_http.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-19
last_reviewed: 2026-06-24
sha256: 53fe51568411283009f2c35e896fe1d7788a7c19d8962e7be4a5f9c8b6fecab6
---
# `tests/python/desktop/test_application_facade_local_api_http.py`

**Purpose:** Python implementation for test application facade local api http; exposes LocalApiHttpTests.

**Public symbols:** `LocalApiHttpTests`
**In-repo imports:** `mediapipeline.core.api.commands_process`, `mediapipeline.core.failures.cleanup_service`, `mediapipeline.core.paths.layout`, `mediapipeline.core.status.run_monitor`, `mediapipeline.desktop.api`, `mediapipeline.desktop.api.handler`, `mediapipeline.desktop.application`, `mediapipeline.desktop.local_api_main`, `mediapipeline.desktop.models`, `mediapipeline.tools.paths`
**HTTP routes:** `/api/audit-controls`, `/api/audit-results`, `/api/audit/export-rerun-csv`, `/api/audit/ignore`, `/api/audit/score-policy`, `/api/backend/close-readiness`, `/api/backend/close-readiness?token=test-token`, `/api/backend/shutdown`, `/api/commands`, `/api/commands?limit=10`, `/api/completed`, `/api/completed/open`, `/api/completed/reconcile-manifest-dry-run`, `/api/completed/repair-sidecar-metadata-dry-run`, `/api/contract`, `/api/diagnostics/open`, `/api/diagnostics/tdarr-matrix-audit`, `/api/failures`, `/api/failures/artifacts`, `/api/failures/artifacts/cleanup`, `/api/failures/open`, `/api/health`, `/api/launch/preflight`, `/api/launch/preflight?target=pipeline&mode=validate&sleep_seconds=3`
**State/config identifiers:** `.mkv.manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths tests/python/desktop/test_application_facade_local_api_http.py`._
