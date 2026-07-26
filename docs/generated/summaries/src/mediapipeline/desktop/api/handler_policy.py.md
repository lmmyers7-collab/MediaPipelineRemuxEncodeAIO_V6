---
file: src/mediapipeline/desktop/api/handler_policy.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: api
token_priority: medium
owner_domain: api
last_modified: 2026-07-24
last_reviewed: 2026-06-04
sha256: 7270f5af50c92afa982920087e080eca0d41193f155cc27534d76aaf983ed2b3
---
# `src/mediapipeline/desktop/api/handler_policy.py`

**Purpose:** Python implementation for handler policy; exposes bounded_error_text, cors_response_headers, not_found_payload.

**Public symbols:** `bounded_error_text`, `cors_response_headers`, `not_found_payload`, `OperatorRouteError`, `options_response_headers`, `requires_strict_durable_command_journal`, `route_exception_journal_payload`, `route_exception_payload`, `route_exception_status`, `route_validation_error_payload`, `route_validation_journal_payload`, `should_record_command_payload`, `should_record_route_exception_journal`, `should_record_validation_failure_journal`, `strict_command_fingerprint`, `unauthorized_payload`, `validated_strict_command_id`
**In-repo imports:** `.command_journal_policy`, `.contract_command`, `.http_helpers`
**HTTP routes:** `/api/audit/start`, `/api/audit/stop`, `/api/backend/lifecycle/reconcile`, `/api/backend/shutdown`, `/api/completed/reconcile-manifest`, `/api/completed/repair-sidecar-metadata`, `/api/final-library-promotion/promote-queue`, `/api/network/coordinator/start`, `/api/network/coordinator/stop`, `/api/network/worker/start`, `/api/network/worker/stop`, `/api/pending-publish/reconcile-orphan-payloads`, `/api/pending-publish/repair-manifest`, `/api/pipeline/control`, `/api/pipeline/start`, `/api/rename/apply`, `/api/rename/undo`, `/api/rerun/continue`, `/api/rerun/control`, `/api/rerun/network/retry`, `/api/rerun/network/start`, `/api/rerun/promote`, `/api/rerun/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/api/handler_policy.py`._
