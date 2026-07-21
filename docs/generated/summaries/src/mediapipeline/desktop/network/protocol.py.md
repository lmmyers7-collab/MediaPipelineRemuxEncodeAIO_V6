---
file: src/mediapipeline/desktop/network/protocol.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-07-05
last_reviewed: 2026-06-04
sha256: a929201e68ea499ccd66fb4b1248d22218df3cd84bdf68dd8d34c52981977b77
---
# `src/mediapipeline/desktop/network/protocol.py`

**Purpose:** network.protocol ================ Request and response dataclasses for the coordinator HTTP API. All dataclasses are stdlib-only (no third-party deps) and serialise to/from plain dicts so they can be JSON-encoded with the standard ``json`` module. This module is imported by both the coordinator (server side) and the worker dispatcher (client side) so the wire format is defined in one place.

**Public symbols:** `ClaimResponse`, `coerce_finite_float`, `coerce_library_id_list`, `coerce_nonnegative_int`, `coerce_optional_bool`, `coerce_progress_percent`, `DoneRequest`, `HeartbeatRequest`, `HeartbeatResponse`, `LogEntryRequest`, `PingResponse`, `WorkerEntry`, `WorkersResponse`
**In-repo imports:** `.failure_reasons`
**HTTP routes:** `/api/claim`, `/api/done`, `/api/heartbeat`, `/api/log`, `/api/ping`, `/api/workers`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/protocol.py`._
