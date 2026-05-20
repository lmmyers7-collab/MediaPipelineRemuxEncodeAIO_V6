# Local API Security Surface

Purpose: document the current localhost API, WebView, and Tauri token boundary so future changes do not accidentally weaken command authorization or move mutation authority into the frontend.

Last updated: 2026-05-20

## Current Posture

- The Local API binds to `127.0.0.1` by default.
- A per-run bearer token is generated unless a launcher supplies one.
- Read and command API routes require the token by default.
- `GET /api/health` and startup web assets are public so the shell can bootstrap and verify readiness.
- Tauri receives the token from Rust-controlled backend bootstrap and injects it into the WebView initialization script.
- Tauri public index HTML must not contain the bearer token.
- Browser launcher mode may include bootstrap token data in the backend-served page because the browser path has no Rust injection layer.
- Query-string tokens are rejected; token auth is header-only.
- The explicit `--no-token`/`-NoTokenDevMode` path is browser-development only and must not become a packaged default.

## Security Headers

Local API responses add:

- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`

The current CSP intentionally still allows inline/eval-compatible script behavior because the present WebView bootstrap and test automation rely on it. A stricter nonce or external-bootstrap design is future hardening, not a current authority-boundary requirement.

## Mutation Boundary

The frontend may render state, stage operator input, and submit authenticated requests. It must not:

- Rename, move, copy, publish, delete, or repair media files directly.
- Write settings, app-state, queue priority, queue strategy, failure markers, completed manifests, pending publish manifests, sidecars, or control flags directly.
- Decide launch scope, close-readiness, pending-publish drain scope, rename apply authority, or source/root safety on its own.
- Expose auth tokens through Settings builders, Network controls, command history, logs, diagnostic panels, or operator copy text.

Backend-owned routes remain the source of truth for mutation. See `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` for route-by-route classification.

## Tauri/WebView Boundary

Tauri owns shell lifetime, backend process startup, startup validation, token handoff, single-instance protection, close-readiness checks, and graceful shutdown requests.

The WebView owns presentation and authenticated API calls only. The Tauri event bridge is event-only and must not call shell/process APIs or mutate files/state.

See `TAURI_BACKEND_LIFECYCLE_BOUNDARY.md` for the lifecycle contract.

## Guardrails

- `DesktopApp/tests/test_application_facade_core_contracts.py` verifies security headers.
- `DesktopApp/tests/test_application_facade_local_api.py` verifies token enforcement, query-token rejection, Tauri public-index token withholding, and Local API shutdown behavior.
- `DesktopApp/tests/test_tauri_shell_scaffold.py` verifies Tauri token injection, no public-index token leakage, and non-null CSP configuration.
- `DesktopApp/tauri_shell/Test-TauriShell-ProductionSurface.ps1` checks production-surface posture for token/devtools/single-instance behavior.
- `DesktopApp/tests/test_webview_frontend_mutation_boundary.py` and no-mutation browser smokes guard that frontend controls use backend-owned command routes rather than direct mutation.
