---
file: apps/desktop/webview/static/assets/launchView.preflight.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-20
last_reviewed: 2026-07-10
sha256: a676f0d947bb9158e65eb8a8accdcd03123b126f6831b81516cd3aa4230f9d3e
---
# `apps/desktop/webview/static/assets/launchView.preflight.js`

**Purpose:** JavaScript implementation for launch view preflight; exposes createLaunchPreflightModule, getLastLaunchBackendPreflightPayloads, getLastLaunchBackendPreflightRefreshInfo.

**Public symbols:** `createLaunchPreflightModule`, `getLastLaunchBackendPreflightPayloads`, `getLastLaunchBackendPreflightRefreshInfo`, `getLaunchRealMediaContext`, `isPipelineControlCommand`, `launchBackendPreflightCandidateRequests`, `launchBackendPreflightDetailLines`, `launchBackendPreflightEncoderActivationLines`, `launchBackendPreflightEncoderCapabilityDetails`, `launchBackendPreflightEncoderHardwareRuntimeLines`, `launchBackendPreflightIncludedPayloads`, `launchBackendPreflightIsStale`, `launchBackendPreflightList`, `launchBackendPreflightOverallStatus`, `launchBackendPreflightPayloadForTarget`, `launchBackendPreflightPipelineBlockers`, `launchBackendPreflightQuery`, `launchBackendPreflightQueueScanRecoveryReason`, `launchBackendPreflightRequestActivity`, `launchBackendPreflightRequestIsActive`, `launchBackendPreflightRequests`, `launchBackendPreflightRequestSetSignature`, `launchBackendPreflightRequestSignature`, `launchBackendPreflightRows`, `launchBackendPreflightRowStatus`, `launchBackendPreflightScopeLabel`, `launchBackendPreflightStartupAlertDetail`, `launchBackendPreflightStartupAlertRecovery`, `launchBackendPreflightStartupAlertSuppressesRow`, `launchBackendPreflightStatusRank`, `launchBackendPreflightStatusState`, `launchBackendPreflightSummaryLines`, `launchBackendPreflightTargetLabel`, `pipelineControlHistoryLine`, `pipelineLaunchPreflightLines`
**In-repo imports:** `window.__launchPilotReadinessModule`, `window.__launchViewPreflightModule`, `window.mediaPipelineLaunchReadinessView`, `window.mediaPipelineQueueView`
**HTTP routes:** `/api/diagnostics/encoder-capabilities/refresh`, `/api/launch/preflight.`, `/api/launch/preflight?`
**DOM selectors:** `.launch-preflight-startup-alert`, `.topbar`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/launchView.preflight.js`._
