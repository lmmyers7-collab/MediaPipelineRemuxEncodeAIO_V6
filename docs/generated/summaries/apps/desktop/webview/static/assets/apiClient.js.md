---
file: apps/desktop/webview/static/assets/apiClient.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-22
last_reviewed: 2026-06-04
sha256: 32331269e918749609b07d3749dfb7a57d232ba59930e7a05216af42f4f5a63c
---
# `apps/desktop/webview/static/assets/apiClient.js`

**Purpose:** JavaScript implementation for api client; exposes acquireDurableCommandState, actionDescriptor, ambiguousCommandError.

**Public symbols:** `acquireDurableCommandState`, `actionDescriptor`, `ambiguousCommandError`, `apiClientError`, `apiGet`, `apiHeaders`, `apiPost`, `apiRequest`, `backendDetail`, `backendEnvelopeObject`, `backendErrorCode`, `bootstrapWithoutToken`, `boundedText`, `canonicalCommandValue`, `categoryCodeText`, `categoryForStatus`, `commandStateKey`, `durationText`, `endpointLabel`, `fetchWithTimeout`, `finishDurableCommandState`, `genericPostAction`, `gerundForAction`, `httpError`, `humanizeSegment`, `invalidJsonError`, `looksLikeRawSql`, `looksLikeSensitivePayload`, `looksLikeStackTrace`, `newDurableCommandId`, `nextStepForCategory`, `normalizeApiBase`, `normalizeApiPath`, `parseResponse`, `readBootstrapElement`
**In-repo imports:** `exporting`, `importing`, `window.apiGet`, `window.apiPost`, `window.clearTimeout`, `window.crypto`, `window.MEDIA_PIPELINE_BOOTSTRAP`, `window.MEDIA_PIPELINE_TAURI_BOOTSTRAP`, `window.mediaPipelineApi`, `window.setTimeout`
**DOM selectors:** `#media-pipeline-bootstrap`
**Exports:** `window.crypto.randomUUID`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/apiClient.js`._
