# 0005. Structured JSON logging

Status: proposed
Date: 2026-05-28

## Context

Logs today are unstructured text written by PowerShell modules under
`RunLogs/` and ad-hoc `print` / `logging` calls in Python services.
Diagnostics rebuilds its picture by re-parsing those logs — a fragile
process that loses any structure the producer had, fails on slightly
different phrasings, and burns CPU on every Diagnostics refresh.

`Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md` §Logging strategy
proposes structured JSON logs read by the orchestrator and persisted to
SQLite.

## Decision

Every log emitted by `app/` or `engine/` is a single-line JSON record.

Schema (minimum required keys):

```json
{
  "ts": "2026-05-28T14:03:11.482Z",
  "stage": "transcode",
  "level": "info",
  "msg": "ffmpeg exited 0",
  "run_id": "r-2026-05-28-001",
  "job_id": "j-7f2",
  "data": { "exit_code": 0, "duration_ms": 84210 }
}
```

- `level` is one of `debug | info | warn | error | critical`.
- `data` is a free-form object for structured context. Keys at the top
  level are reserved.
- Timestamps are ISO-8601 UTC.

Producers:

- **Python**: `structlog` with a JSON renderer (or stdlib `logging` with
  a JSON formatter — either is fine, pick one per
  `app/observability/log.py`). All `print()` is forbidden in
  `app/` for non-CLI output.
- **PowerShell**: `engine/entrypoint.ps1` and every module log to
  stderr as JSON Lines. Module logging is a thin wrapper that takes a
  level, a message, and a hash of context; it composes the line.

Consumer:

- The orchestrator runs `engine/entrypoint.ps1` as a subprocess and
  reads its stderr line-by-line. Each line is parsed and inserted into
  the `events` table in `state.sqlite` (per ADR-0003). Per-run logs are
  also tee'd to `runlogs/<run_id>.jsonl` for offline forensics and
  operator hand-off.

Diagnostics queries the `events` table; it does not scrape logs.

Rules in force:

- **One line = one record.** Multi-line stack traces are folded into a
  `data.exception` field with the formatted traceback as a single
  string.
- **Never log-and-swallow.** Either retry, mark failure with a stable
  code, or re-raise. Logging an error and continuing silently is
  forbidden.
- **Stable `code` field for errors.** Use the
  `MediaPipelineError` hierarchy from `app/common/errors.py`
  (Phase 4); the `code` on each subclass is wire-stable so Diagnostics
  filters work across versions.

## Consequences

Code and structure:

- `app/observability/log.py` is the canonical logger factory.
- `engine/common/log.ps1` (Phase 3) is the PowerShell equivalent.
- Existing Python `logging.getLogger(...)` calls migrate; existing
  PowerShell `Write-Host` / `Write-Output` calls in module code
  migrate.

Operational surface:

- One log file per run, machine-readable. Operators see human-readable
  Diagnostics output; engineers and AI sessions read the JSONL.
- Log rotation is per-run (one file per run id) rather than by size or
  date.

Testing and CI:

- Contract tests assert that every stage emits at least one event of
  the declared type (per ADR-0002 `Validation`).
- A formatter test asserts that exception logging does not produce
  multi-line records.

Migration cost:

- Phase 4. Existing log producers migrate behind a thin shim during
  transition; the shim is removed in Phase 6.

Reversibility:

- High. The producer-side change is one-line per call site. Reverting
  the consumer (SQLite ingest) is also straightforward; the JSONL files
  on disk remain readable.

## Alternatives considered

**Plain `logging` with the default format string.** What we have today
in Python. Loses structure, requires regex parsing in Diagnostics,
forces every log statement to encode context as English prose.
Rejected.

**OpenTelemetry.** Industry-standard structured telemetry, but its
collector and storage stack is heavyweight for a single-operator
desktop. Plan §Recommended Tools explicitly defers it. Rejected.

**Binary log format (e.g. protobuf, msgpack).** Faster to parse, but
the operator and AI use cases value `tail -f` and `jq` over speed.
Rejected.

**Logs straight into SQLite skipping the JSONL file.** Loses an
on-disk record of any event that didn't make it into the DB (e.g.
during a crash). Keep both. Rejected as primary path.

## Validation

- `app/observability/log.py` (Phase 4 — planned) emits a record that
  passes a JSON Schema test.
- `engine/common/log.ps1` (Phase 3 — planned) ditto.
- A formatter test under `tests/python/unit/observability/` asserts:
  single-line records, all required keys present, exception folded
  into one field.
