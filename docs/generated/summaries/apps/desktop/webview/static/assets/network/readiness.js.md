---
file: apps/desktop/webview/static/assets/network/readiness.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: network
token_priority: medium
owner_domain: webview
last_modified: 2026-07-12
last_reviewed: 2026-07-11
sha256: b478fc89848a8f9dba1b3919c99a255f7088000eb83cea926957935f84be8ad7
---
# `apps/desktop/webview/static/assets/network/readiness.js`

**Purpose:** JavaScript implementation for readiness; exposes closeReadinessLine, createNetworkReadinessModule, networkReadinessLines.

**Public symbols:** `closeReadinessLine`, `createNetworkReadinessModule`, `networkReadinessLines`, `networkReadinessStatus`, `renderNetworkReadiness`, `snapshotStateLine`
**In-repo imports:** `window.__networkReadinessModule`
**HTTP routes:** `/api/diagnostics/open`, `/api/network/workers`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/network/readiness.js`._
