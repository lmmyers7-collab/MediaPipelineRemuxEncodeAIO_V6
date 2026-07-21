---
file: src/mediapipeline/desktop/network/auth.py
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Python
pipeline_stage: network
token_priority: medium
owner_domain: network
last_modified: 2026-06-19
last_reviewed: 2026-06-04
sha256: a2910972f2dc45edf0cce4a9bc16c89fc73779c099a9fe81a2069a385ac76012
---
# `src/mediapipeline/desktop/network/auth.py`

**Purpose:** network.auth ============ Token generation and validation for the coordinator HTTP API. Designed to be simple and stdlib-only. The coordinator token is a shared secret used to sign requests with HMAC-SHA256 so the token is not sent on the LAN for normal worker/coordinator traffic. For future TLS support, wrap the ``ThreadingHTTPServer`` with an ``ssl.SSLContext`` in ``network/coordinator.py`` — no changes needed here.

**Public symbols:** `AuthValidationResult`, `body_sha256_hex`, `canonical_request`, `generate_token`, `sign_request`, `validate_header`, `validate_request_auth`, `validate_request_auth_result`, `validate_signed_request`, `validate_signed_request_result`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths src/mediapipeline/desktop/network/auth.py`._
