---
file: apps/desktop/webview/static/assets/queue/openActions.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: orchestration
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 6a56c29a51ef42be149d05873c7b5b4f4b2c592dd0b1738fe7fae81044b2243e
---
# `apps/desktop/webview/static/assets/queue/openActions.js`

**Purpose:** JavaScript implementation for open actions; exposes createQueueOpenActionsModule, queueSelectedOpenTargetLines, rejectQueueOpenWhileBusy.

**Public symbols:** `createQueueOpenActionsModule`, `queueSelectedOpenTargetLines`, `rejectQueueOpenWhileBusy`, `requestQueueOpen`, `setQueueOpenBusy`
**In-repo imports:** `window.__queueOpenActionsModule`, `window.mediaPipelineAppRowOpenActions`
**HTTP routes:** `/api/queue/open`
**DOM selectors:** `[data-open-queue], [data-open-queue-excluded]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/queue/openActions.js`._
