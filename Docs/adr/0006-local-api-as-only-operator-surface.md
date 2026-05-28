# 0006. Local API as the only operator surface

Status: accepted
Date: 2026-05-28

## Context

The product today has one operator surface: a Python HTTP API bound to
`127.0.0.1`, consumed by a WebView SPA (vanilla JS) loaded inside a
Tauri/WebView2 shell. There is no CLI for operator actions, no
direct-edit JSON state surface that bypasses the API, and no second
client. `AGENTS.md §3` already names "backend owns media policy" as a
hard rule: the WebView/Tauri shell must not implement filesystem
mutation, settings persistence, queue mutation, pending-publish drain,
rename apply, or media policy independently.

This is the de-facto architecture but has never been written down as a
decision. The drift risk is that, without an ADR, a future contributor
adds a "convenience CLI" that bypasses the journal, command guards, or
close-readiness checks.

## Decision

The local HTTP API at `127.0.0.1:<port>` is the **only** supported
operator surface. Every operator action — settings change, queue
mutation, pipeline start/stop/pause, pending publish drain, rename
apply, audit rerun — goes through an API route, hits the command
journal, and respects duplicate-command guards and close-readiness
checks.

Rules in force:

- **No alternate operator paths.** Direct edits to `LocalBase/State/*`
  JSON files, direct PowerShell entry points that mutate state, or CLI
  commands that bypass the API are not supported. Maintenance scripts
  used by the operator (e.g. environment verify, release build) are
  acceptable because they do not mutate runtime state.
- **The WebView is a thin client.** It renders state pulled from the
  API and sends commands to the API. It does not own any media policy,
  validation, persistence, or filesystem mutation.
- **One transport.** JSON over HTTP. No WebSocket push, no SSE, no
  shared-memory channel. Polling is the operator-facing pattern.
- **One bind address.** `127.0.0.1`. The API is never exposed on a LAN
  interface. The optional network/coordinator-worker plane has its own
  authenticated transport, separate from the operator API.
- **Strict JSON route handling.** Routes parse with strict JSON; unknown
  fields are rejected. This is already in place via
  `command_payloads_*.py` and the contract validation layer; ADR-0004
  swaps the validator to pydantic without changing the rule.

## Consequences

Code and structure:

- `app/api/` is the only entry point for operator commands.
- The command journal, duplicate-command guard, and close-readiness
  check live behind the API and are never bypassed by a "developer
  shortcut".

Operational surface:

- Logs and audit show every operator action because every action passes
  the journal.
- Crash recovery has a single state to recover (the journal + SQLite).

Testing and CI:

- Contract tests cover every route. The route is the only behavior
  surface that operators reach, so route coverage is the canonical
  measure.

Migration cost:

- None for new work; existing call sites already obey the rule. The ADR
  exists primarily to prevent regressions.

Reversibility:

- High in principle (an alternate surface can be added) but the cost of
  doing so is exactly what this ADR is preventing — a second source of
  state mutations that journaling, guards, and checks cannot see.

## Alternatives considered

**Add a CLI for operator actions.** Useful for scripting and remote
ops. Rejected because the project is a single-operator desktop tool
and the cost of duplicating the API's safety surfaces (journal,
guards, close-readiness) into a second client outweighs the benefit.
If automation is ever needed, the answer is a script that calls the
HTTP API, not a parallel command surface.

**WebSocket push for state updates.** Lower latency than polling, but
adds a stateful connection that complicates the Tauri/WebView lifecycle
and the optional network plane. Polling is fine at this scale.
Rejected.

**Network-bound API for remote operator access.** Out of scope; the
network/coordinator-worker plane handles the multi-host case under its
own ADR (future).

## Validation

- Route contract tests under `tests/python/contract/api/` (Phase 5 —
  planned) cover every route in `app/api/routes/*.py`.
- A naming-lint check (Phase 5) flags new files under
  `DesktopApp/.../scripts/` or `Pipeline/` that mutate state outside
  the API path (heuristic — needs human review).
