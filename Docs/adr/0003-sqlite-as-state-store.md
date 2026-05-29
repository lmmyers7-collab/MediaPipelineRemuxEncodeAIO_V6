# 0003. SQLite as state store

Status: proposed
Date: 2026-05-28

## Context

Runtime state today lives as JSON files in `LocalBase/State/`: queue
snapshots, command journal records, completed-job manifests, pending
publish manifests, audit history, probe results, control flags. Roughly
ten distinct readers and writers each parse a file, mutate the dict,
write the file back. This pattern leaks in three ways:

- **No filtering by age or status.** Diagnostics rebuilds queries by
  reading every JSON file. As history grows, listing the last 50 jobs
  costs O(all jobs).
- **Concurrent writers collide.** Two paths writing the same JSON race;
  the loser is overwritten silently. Today this is rare because most
  flows are single-threaded, but the coordinator/worker plane wants
  concurrent writes.
- **No durability guarantee on partial writes.** A crash mid-write leaves
  truncated JSON that the next reader refuses, requiring manual repair.

`Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md` §Storage strategy
recommends SQLite.

## Decision

Use **SQLite** (stdlib `sqlite3`, or `aiosqlite` for the API layer) as
the canonical state store, located at `state/state.sqlite` (per the
target layout) or its current-tree equivalent under `LocalBase/State/`
during transition.

Tables (initial):

| Table             | Replaces (JSON file)                          |
| ----------------- | --------------------------------------------- |
| `jobs`            | queue snapshot rows, completed manifest rows  |
| `attempts`        | transcode attempt history (was in run logs)   |
| `events`          | structured logs (per ADR-0005)                |
| `commands`        | command journal                               |
| `pending_publish` | pending publish index (manifest stays as file)|
| `audit_records`   | audit rerun records                           |
| `probe_cache`     | probe results keyed by `(path, mtime, size)`  |
| `config_history`  | PSD1 versions written through the API         |

Rules in force:

- **WAL mode.** `PRAGMA journal_mode=WAL` on connect. Readers don't
  block writers; one writer at a time.
- **One writer per process.** The orchestrator process owns writes. The
  API layer wraps writes in a serialized executor.
- **Advisory file lock for the active job.** `filelock` on
  `state/active.lock` prevents two pipeline runs from racing the same
  job, independent of the DB.
- **File-state files retained** only when the artifact is genuinely
  external — e.g. `pending_publish/<id>/manifest.json` lives next to its
  parked payload because the directory itself is the durable artifact.
- **Schema migrations in `app/storage/migrations/`** as numbered SQL
  files; `app/storage/db.py` applies them in order on startup.
- **No ORM at the start.** Plain `sqlite3` with parameterized queries
  and pydantic-validated rows (ADR-0004). An ORM may be revisited if
  query complexity grows.

## Consequences

Code and structure:

- `app/storage/db.py` becomes the single read/write surface. Existing
  `service_queue_snapshot.py`, `service_status_*`,
  `service_audit_rerun_records.py`, `service_completed_manifest.py`,
  `command_journal.py` collapse into thin DB queries.
- Diagnostics queries SQL instead of scraping JSON files and run logs.

Operational surface:

- One file to back up (`state.sqlite` + WAL).
- One file to truncate when starting fresh.
- Crash recovery is automatic via WAL.

Testing and CI:

- Integration tests run against a real SQLite file in a `tmp_path`
  fixture. No mocks; SQLite is fast and reliable in tests.
- Contract tests for stage payloads continue to use pydantic; DB
  schema is tested separately with golden migrations.

Migration cost:

- One-shot importer reads the existing JSON files at start of Phase 4
  and seeds the DB. The JSON files become read-only history during
  transition, then archived.

Reversibility:

- Low-medium. Once the DB has accumulated history not present in any
  JSON file (concurrent writes, events, probe cache), reverting to JSON
  loses data. The cost is paid up front in Phase 4.

## Alternatives considered

**Keep JSON files, add file locks and atomic-rename writes.** Fixes
durability and concurrency but not the query-by-attribute problem.
Diagnostics still scrapes files. Rejected for half-measure.

**PostgreSQL.** Overkill for a single-operator desktop. Adds a server
process to start, monitor, back up, and version. Plan §Recommended Tools
explicitly recommends against. Rejected.

**DuckDB.** Excellent for analytics; not optimized for many small
writes. Could replace SQLite later if queue volume justifies it.
Rejected for now.

**Embedded key-value store (LMDB, RocksDB).** Faster writes but loses
SQL query surface and adds a native dependency that complicates the
Windows portable bundle. Rejected.

## Validation

- `app/storage/db.py` (Phase 4 — not yet created) exposes a
  documented connection factory with WAL pragma.
- `tests/python/integration/storage/test_db_migrations.py` (planned)
  applies each migration to an empty DB and asserts the final schema.
- `tests/python/contract/test_journal_durability.py` (planned) crashes a
  write mid-transaction and asserts the next reader sees a consistent
  state.
