# Local API Security Surface

Last reviewed: 2026-06-16

This document records the security boundary for the local Python API that serves
the WebView and Tauri shell. It is an architecture note, not a route inventory.
Route-level mutation classes remain in
`docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`.

## Scope

The Local API is a localhost operator-control surface. It serves startup health,
static WebView assets, read routes, and backend-owned command routes. The
WebView and Tauri shell may render evidence and submit allowlisted command
payloads, but media policy, queue mutation, settings persistence, pending
publish drain, rename apply, lifecycle, and filesystem mutation remain
backend-owned.

Primary implementation files:

- `src/mediapipeline/desktop/api/server.py`
- `src/mediapipeline/desktop/api/handler.py`
- `src/mediapipeline/desktop/api/http_helpers.py`
- `src/mediapipeline/desktop/api/handler_policy.py`
- `src/mediapipeline/desktop/api/static_files.py`
- `src/mediapipeline/desktop/api/static_files_policy.py`

## Bind and Token Defaults

- The default bind host is `127.0.0.1`.
- The default requested port is `0`, so the operating system selects an
  available local port.
- The server generates a per-run token with `secrets.token_urlsafe(24)` when no
  token is supplied.
- API route authentication is enabled by default.
- Disabling token authentication is a developer-only mode gated by
  `MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV` and a loopback host check.

Public unauthenticated routes are intentionally limited:

- `GET /`
- `GET /index.html`
- `GET /assets/*`
- `GET /api/health`

All other read routes and all command routes require the per-run token unless
the explicit loopback-only developer no-token mode is active.

## Accepted Credentials

Authenticated requests may present the per-run token in one of these forms:

- `X-MediaPipeline-Token`
- `Authorization: Bearer <token>`
- `MediaPipelineAuth` HTTP-only cookie for the browser WebView surface

Token comparison uses constant-time comparison. Tauri initialization uses the
shell initialization path instead of the browser cookie bootstrap.

## Host, Origin, and CORS Boundary

Every request is checked against the bind host and selected port before route
handling. Accepted host names are loopback aliases plus the explicit bind host
when it is not a wildcard bind.

Command routes also require an allowed origin. Accepted origins are exact
`http://<allowed-loopback-host>:<api-port>` origins. The Tauri shell surface may
also use `tauri://localhost`. Empty `Origin` is accepted for local non-browser
clients, but non-empty origins must match exactly and may not carry path, query,
or fragment components.

OPTIONS responses reflect only the resolved allowed origin and expose the
minimal headers required by the local client:

- `Authorization`
- `X-MediaPipeline-Token`
- `Content-Type`

## Static Asset Boundary

Static assets are resolved only under `apps/desktop/webview/static/assets`.
Requests containing parent traversal or backslash path components are rejected.

The served `index.html` expands only allowlisted `partials/*.html` include
markers under the static root, rejects absolute paths or parent traversal, and
requires the backend bootstrap placeholder to remain present before rendering.

The bootstrap payload carries local client initialization data only. When auth is
required, the browser surface receives an HTTP-only cookie and the Tauri surface
uses initialization-script token delivery.

## JSON and Command Validation

POST requests must use `Content-Type: application/json`; request bodies are
bounded to 1,000,000 bytes by default. JSON parsing uses the strict JSON helper,
requires an object payload, rejects invalid content length, and returns bounded
400/413 errors for invalid requests.

Before dispatching a command route, the Local API validates the payload through
the backend API payload validator. Validation failures return 400 responses and,
for journalable command routes, write sanitized command-journal evidence.

Successful command responses and journalable failures are recorded through the
backend command journal. Command-journal evidence is bounded and redacts keys
containing secret-like terms such as token, secret, password, credential,
authorization, API key, and join blob.

## Response Security Headers

Local API responses include:

- `Cache-Control: no-store`
- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`

The current content security policy allows same-origin scripts, same-origin
connects, same-origin/data images, inline styles for the existing WebView CSS
surface, and blocks object embedding, frame ancestors, base URI, and form
submission.

## Error Handling and Logging

Route exceptions return an internal-error payload with a short generated
`error_id` rather than raw exception detail. The server logs the exception with
the route and error ID for diagnostics.

Expected local client disconnects are suppressed at the server write/error hook
so browser shutdown or test-client disconnects do not look like production route
crashes. Unexpected server exceptions still use normal error handling.

## Mutation Boundary

The Local API security boundary does not make frontend command behavior safe by
itself. Mutating operations are safe only because command routes delegate to
backend-owned policy, validation, journaling, confirmation fields, allowlisted
targets, and filesystem safeguards.

For route-by-route mutation classes, command ownership, and frontend
prohibitions, use these active references:

- `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`

## Release Review Checklist

Before changing this surface, verify:

- Public routes are still limited to startup health and static shell assets.
- Authenticated routes still require token evidence by default.
- Host and Origin checks still reject non-loopback or wrong-port requests.
- Command routes still validate strict JSON before dispatch.
- Command-journal evidence remains bounded and secret-redacted.
- Static asset resolution cannot escape the WebView static root.
- Any new command route is classified in the mutation matrix, route inventory,
  ownership map, and command contract.
- Browser/Tauri smokes and Local API route tests cover the changed behavior.
