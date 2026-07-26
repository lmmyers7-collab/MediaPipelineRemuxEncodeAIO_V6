---
file: src/mediapipeline/desktop/network/coordinator.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 0c0ec095c4d073fb93ad9ec26843122db6bfaeb7c1cce13eced9b9742a0b6f6d
---
# `src/mediapipeline/desktop/network/coordinator.py`

**Purpose:** network.coordinator =================== ``CoordinatorDispatcher`` — manages the in-flight registry and serves the coordinator HTTP API on a dedicated ``ThreadingHTTPServer``. Architecture ------------ * Starts its own HTTP server on ``<CoordinatorBindAddress>:<CoordinatorPort>`` so workers on other LAN machines can reach it when the bind address allows LAN traffic. The existing status-display server (localhost) is left untouched. * HMAC-signed worker requests via :mod:`network.auth`. * ``InFlightRegistry`` handles all thread-safe job tracking. * A daemon *stale-reaper* thread runs every 60 s and reclaims jobs whose heartbeat has expired, returning them to the available queue. * mDNS advertisement via :mod:`network.mdns` (Phase 3 — requires zeroconf). * ``WorkerConfigOverrides`` remains loadable for compatibility but is ignored by backend encode snapshot policy until a real override authority is defined. * Retry policy: files already in the failure log get ``retry_on_failure=False`` so workers won't re-queue them on failure (Phase 3). Source-policy anchors retained for split HTTP-server warning checks: * "Failed to send coordinator JSON response status=%s" / "client may not receive response" * "Failed to send oversized coordinator request response" / "client may not receive 413" * "Failed to send malformed Content-Length coordinator request response" / "client may not receive 400" * "Failed to read coordinator request body after Content-Length %d" / "request handler will stop" * "Failed to send coordinator OPTIONS response" / "client may not receive 204" Phase 1 + Phase 3: full implementation.

**Public symbols:** `CoordinatorDispatcher`
**In-repo imports:** `.coordinator_auth`, `.coordinator_http_handlers`, `.coordinator_lifecycle`, `.coordinator_parts.http_server`, `.coordinator_policy`, `.coordinator_queue`, `.coordinator_state`, `.dispatcher`, `.identity`, `.registry`, `.rerun_claims`
**HTTP routes:** `/api/claim`, `/api/done`, `/api/health`, `/api/heartbeat`, `/api/workers`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/coordinator.py`._
