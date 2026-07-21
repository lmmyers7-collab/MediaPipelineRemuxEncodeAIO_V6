---
file: apps/desktop/webview/static/assets/queue/rerunApi.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: orchestration
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: 814b724d3dc69b776ba3f7e563994e79bf592839978e2873023a9406beedaa34
---
# `apps/desktop/webview/static/assets/queue/rerunApi.js`

**Purpose:** JavaScript implementation for rerun api; exposes createQueueRerunApiModule, currentApiGet, currentApiPost.

**Public symbols:** `createQueueRerunApiModule`, `currentApiGet`, `currentApiPost`, `getCommandHistory`, `getRerunResults`, `postBackendRerunAction`, `postDiagnosticsOpen`, `postRerunContinue`, `postRerunControlPause`, `postRerunControlStopAfterCurrent`, `postRerunNetworkPreview`, `postRerunNetworkStart`, `postRerunNetworkStartDryRun`, `postRerunOpen`, `postRerunPreview`, `postRerunPromote`, `postRerunPromoteDryRun`, `postRerunStart`, `requireApiGet`, `requireApiPost`
**In-repo imports:** `window.__queueRerunApiModule`, `window.apiGet`, `window.apiPost`
**HTTP routes:** `/api/commands?limit=20`, `/api/diagnostics/open`, `/api/rerun/continue`, `/api/rerun/control`, `/api/rerun/network-preview`, `/api/rerun/network/retry`, `/api/rerun/network/start`, `/api/rerun/network/start-dry-run`, `/api/rerun/open`, `/api/rerun/preview`, `/api/rerun/promote`, `/api/rerun/promote-dry-run`, `/api/rerun/results?limit=24`, `/api/rerun/start`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/queue/rerunApi.js`._
