---
file: src/mediapipeline/desktop/network/coordinator_parts/http_server.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 2c4580c5a17fff4cba1261f3104f30b21c24cb7f1aab873ddb83355b24a6a459
---
# `src/mediapipeline/desktop/network/coordinator_parts/http_server.py`

**Purpose:** Coordinator HTTP server and request handler implementation. This module owns the HTTP connection/session handling for the coordinator facade. Keep log records on the historical ``network.coordinator`` logger so existing operator diagnostics and tests continue to observe the same source.

**In-repo imports:** `..auth`, `..coordinator_http`
**HTTP routes:** `/api/claim`, `/api/claim.`, `/api/done`, `/api/health`, `/api/heartbeat`, `/api/libraries`, `/api/log`, `/api/ping`, `/api/workers`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/coordinator_parts/http_server.py`._
