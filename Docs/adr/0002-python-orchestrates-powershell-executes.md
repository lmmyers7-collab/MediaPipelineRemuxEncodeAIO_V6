# 0002. Python orchestrates, PowerShell executes

Status: accepted
Date: 2026-05-28

## Context

The repository today carries pipeline behavior in two engines:

1. `Pipeline/Modules/` (168 `.ps1`) — media policy, FFmpeg argument
   construction, queue, probe, audit, naming, publish.
2. `DesktopApp/mediapipeline_desktop_app/application/facade_*.py` (65) +
   flat `service_*.py` (108) — DTOs, state, config, status, telemetry,
   process lifecycle adapters.

The Python side calls itself a "facade" but encodes pipeline
*decisions*: settings risk policy, queue priority, folder policy, pending
publish manifests, rename plans, audit rerun. Several decisions appear in
both engines with the same intent and slightly different expression. The
PSD1 config has three Python representations (`config_schema.py` plus
four siblings) — none generated from a common source.

`Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md` §Drift risks ranks
"PowerShell pipeline behavior ↔ Python facade descriptions ↔ Markdown
narrative" as drift risk #2.

## Decision

Establish a hard separation:

- **Python (`app/`) orchestrates.** It owns: API surface, job lifecycle,
  queue, scheduling, retries, state DB, command journal, config schema,
  contracts, logging, metrics, coordinator/worker control plane. Python
  decides *what* runs and *in what order*.
- **PowerShell (`engine/`) executes.** It owns: FFmpeg invocation,
  MKVToolNix invocation, PgsToSrt invocation, subtitle conversion,
  audio mixing, remux/encode argument generation, file moves on disk.
  PowerShell decides *how* to run a single stage when handed a payload.

The wire contract between them is a single entrypoint:

```
engine/entrypoint.ps1 <stage> <payload-json>
```

`<stage>` is one of the values in
`app/contracts/stages.py::StageName`:

```
ingest | probe | decide | transcode | subtitle-convert |
audio-mix | publish | drain | rename
```

`<payload-json>` is the stage's `*Payload` dataclass from
`app/contracts/stages.py`, serialized as a single JSON document on
stdin or as the second argument. The engine returns the stage's
`*Result` dataclass as a JSON document on stdout. Logs go to stderr as
JSON Lines (one record per line).

Each payload carries `schema_version` (currently `"v1"`). The engine
rejects unknown versions. Breaking changes bump the version and ship a
new payload class alongside the old one; the orchestrator emits the
version it understands.

PowerShell may not read PSD1 config directly. The orchestrator resolves
the relevant config slice into the payload before dispatch. This makes
the PSD1 round-trip Python's single responsibility (ADR-0004) and stops
PowerShell from carrying its own config parser.

## Open questions

- Stage `subtitle-convert` may eventually split into PGS-OCR (slow,
  optional) and ASS/TX3G (fast, always). Deferred.
- The optional network/coordinator-worker plane already has a partial
  Python presence; whether worker-side execution stays in PowerShell or
  moves into Python is deferred to a later ADR.

## Consequences

Code and structure:

- `app/contracts/stages.py` is the wire contract. Any field added there
  must be honored by `engine/entrypoint.ps1` and by the corresponding
  domain module. `STAGE_REGISTRY` lets the orchestrator enumerate stages
  at runtime.
- PowerShell modules become smaller: they get told what to do, they do
  it, they return a `*Result`. No reading config files, no walking the
  queue, no writing to JSON state files.
- The Python `facade_*.py` / `service_*.py` tree no longer holds
  decision logic — it migrates into `app/<domain>/` per ADR-0001.

Operational surface:

- Diagnostics queries one place (the SQLite event store, per ADR-0003)
  instead of correlating PowerShell run logs with Python state.
- A single subprocess boundary is easier to instrument, time, and
  replay.

Testing and CI:

- Contract tests per stage become straightforward: build a payload,
  invoke `entrypoint.ps1`, validate the result against
  `schemas/<stage>.v1.schema.json` (generated from the dataclass per
  ADR-0004).
- The PowerShell side can be tested with a fake `entrypoint.ps1` that
  returns canned `*Result` payloads, decoupling Python tests from
  FFmpeg.

Migration cost:

- Phase 3 of the overhaul plan stands up `engine/entrypoint.ps1` and
  moves stages one at a time. Existing call sites in
  `DesktopApp/.../service_*.py` continue to work until Phase 6.

Reversibility:

- Medium. Once the engine has been thinned to "executor" shape, putting
  decision logic back in PowerShell is mostly a deletion in `app/`.

## Alternatives considered

**Make PowerShell the orchestrator and shrink Python to a UI.** The PS
side already runs FFmpeg, so this would minimize the subprocess
boundary. Rejected because operator-facing surfaces (HTTP API, WebView,
Tauri shell, network plane) are easier and safer in Python, and because
PSD1 round-trip plus pydantic generation is much weaker on the
PowerShell side.

**Rewrite the PowerShell engine in Python.** A year of risk for no
shipping behavior change. The PowerShell engine already correctly
invokes FFmpeg, handles edge cases discovered over many real-media
runs, and is the working production code path. Rejected.

**Use a workflow engine (Dagster/Prefect/Celery) between the two.**
Overkill for a single-operator desktop pipeline. Plan §Recommended
Tools explicitly defers any workflow engine until multi-host
coordination is a hard requirement.

## Validation

- `app/contracts/stages.py` exists and defines `STAGE_REGISTRY`
  (commit `77b8b4c`).
- `engine/entrypoint.ps1` (Phase 3 — not yet created) accepts the
  stages enumerated above.
- `tests/python/contract/test_<stage>.py` (Phase 5 — planned) round-trip
  every stage's payload through schema validation, dispatch, and result
  validation.
