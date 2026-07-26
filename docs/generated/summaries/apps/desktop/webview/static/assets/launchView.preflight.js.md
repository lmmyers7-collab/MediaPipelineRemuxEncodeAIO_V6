---
file: apps/desktop/webview/static/assets/launchView.preflight.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-23
last_reviewed: 2026-07-10
sha256: 4f19dd8c59a3c48fc8330746b3c28c3ef4fb9d8eb6c20e17b7c9eabf3044a2a2
---
# `apps/desktop/webview/static/assets/launchView.preflight.js`

**Purpose:** JavaScript implementation for launch view preflight; exposes createLaunchPreflightModule, getLastLaunchBackendPreflightPayloads, getLastLaunchBackendPreflightRefreshInfo.

**Public symbols:** `createLaunchPreflightModule`, `getLastLaunchBackendPreflightPayloads`, `getLastLaunchBackendPreflightRefreshInfo`, `getLaunchRealMediaContext`, `isPipelineControlCommand`, `launchBackendPreflightCandidateRequests`, `launchBackendPreflightDetailLines`, `launchBackendPreflightEncoderActivationLines`, `launchBackendPreflightEncoderCapabilityDetails`, `launchBackendPreflightEncoderHardwareRuntimeLines`, `launchBackendPreflightIncludedPayloads`, `launchBackendPreflightIsStale`, `launchBackendPreflightList`, `launchBackendPreflightOverallStatus`, `launchBackendPreflightPayloadForTarget`, `launchBackendPreflightQuery`, `launchBackendPreflightRequestActivity`, `launchBackendPreflightRequestIsActive`, `launchBackendPreflightRequests`, `launchBackendPreflightRequestSetSignature`, `launchBackendPreflightRequestSignature`, `launchBackendPreflightRows`, `launchBackendPreflightRowStatus`, `launchBackendPreflightScopeLabel`, `launchBackendPreflightStatusRank`, `launchBackendPreflightStatusState`, `launchBackendPreflightSummaryLines`, `launchBackendPreflightTargetLabel`, `pipelineControlHistoryLine`, `pipelineLaunchPreflightLines`, `refreshLaunchBackendPreflight`, `refreshLaunchBackendPreflightEncoderCapability`, `renderAllLaunchPreflights`, `renderLaunchBackendPreflight`, `renderLaunchPreflight`
**In-repo imports:** `window.__launchPilotReadinessModule`, `window.__launchViewPreflightModule`, `window.mediaPipelineLaunchReadinessView`
**HTTP routes:** `/api/diagnostics/encoder-capabilities/refresh`, `/api/launch/preflight.`, `/api/launch/preflight?`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/launchView.preflight.js`._
