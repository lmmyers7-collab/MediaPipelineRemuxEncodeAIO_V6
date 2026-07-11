# Audit Tool Current-Data Plan

Verified against active source, route inventories, and focused tests on
2026-07-09.

Purpose: make every operator-facing Audit feature traceable to the backend or
PowerShell owner that supplies its evidence, and close the stale-data risks that
can make the Reports table disagree with the current library.

## Scope

Audit features in scope:

- Audit process launch, duplicate/concurrency guards, progress, and stop:
  `POST /api/audit/start`, `POST /api/audit/stop`, snapshot audit progress, and
  `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1`.
- Audit source registry, selection, and read-only source counts:
  `GET /api/audit-sources`, `POST /api/audit/sources`,
  `POST /api/audit/sources/scan`, and
  `src/mediapipeline/core/audit/sources.py`.
- Media enumeration, ffprobe execution, probe-cache identity, cache rebuild,
  scoring, duplicate grouping, and report generation under
  `ops/pipeline/engine/audit/`.
- Audit progress and latest report pointers: `audit_progress.json` and
  `src/mediapipeline/core/observability/status_files.py`.
- Reports audit preview and controls: `GET /api/audit-results`,
  `GET /api/audit-controls`, `POST /api/audit/score-policy`,
  `POST /api/audit/ignore`, `src/mediapipeline/core/audit/`, and
  `apps/desktop/webview/static/assets/reports/audit*.js`.
- Audit-to-rerun handoff: `POST /api/audit/export-rerun-csv`,
  `src/mediapipeline/core/audit/rerun_*`, and Queue CSV Rerun preview/start
  routes.
- Diagnostics handoff: latest audit CSV, priority CSV, audit report folder,
  queue snapshot, completed manifest, run logs, and failure reports.

## Verified Current State

- A fresh audit enumerates media files currently present under the selected or
  configured library roots and calls `Invoke-FfprobeJsonCached` for each file.
- Enumeration filters media and captures cache-identity metadata in the bounded
  scan job, avoiding a second parent-process `Get-Item` pass. Probe-cache
  identity is sampled once per lookup, and uncached ffprobe work uses two
  bounded workers by default (`-ProbeConcurrency 1..8` for measured overrides)
  before classification and report generation continue in deterministic order.
- Latest standard and priority CSV selection prefers the pointers from a
  completed, non-failed `audit_progress.json` when each pointer stays inside the
  configured audit report root and resolves to the expected report kind.
- The compatibility fallback orders timestamped `audit_summary_*.csv` names
  before filesystem mtime, so touching an older timestamped report does not make
  it newest. The fallback does not independently prove run completion.
- Probe-cache identity contains normalized path, byte length, last-write UTC,
  and SHA-256 over the first and last 1 MiB. A fresh audit re-probes when any of
  those values changes. `-RebuildProbeCache` bypasses existing entries for a
  direct PowerShell audit run, but that switch is not exposed by the Local API
  audit-start contract.
- A replacement that preserves path, length, last-write time, and both sampled
  regions is not distinguishable by the current probe-cache identity. The
  active test proves the common same-path/same-size/same-mtime case only when
  sampled content differs; it is not a full-file identity guarantee.
- Reports audit preview is a snapshot of the selected CSV, not a live view of
  current file state. It does not currently stat displayed rows or flag files
  changed after the audit.
- Successful audit process exit triggers a read-only Audit source metric scan.
  The sync identifies roots missing from the source registry, but those
  warnings are not retained as durable row-level latest-audit evidence.
- Rerun export reads current source size, mtime, and `source_identity_v2`,
  disables unavailable sources, and Queue later validates that export-time
  identity before execution. This protects against changes after export; it
  does not prove that the audit issue codes still describe the file at export
  time because audit CSV rows do not contain equivalent audit-time identity.
- Reports preview and source scans do not mutate media. Rerun export writes only
  a backend-owned import CSV artifact and handoff metadata; Queue owns any later
  rerun preview/start decision.

## Status

| Phase | Status | Current boundary |
| --- | --- | --- |
| 1. Latest Report Authority | Partial | Completed progress pointers and timestamp-first fallback are implemented; fallback completion proof is still missing. |
| 2. Replaced-File Rescan Guard | Partial | Sampled-content identity and an active replacement test are implemented; an exhaustive replacement guarantee or operator-facing cache rebuild mode is still missing. |
| 3. Row-Level Current-Data Evidence | Planned | Audit CSV rows lack audit-time mtime and a comparable content identity, and preview does not stat current files. |
| 4. Audit Source Consistency | Partial | Successful runs refresh configured source metrics and detect unmatched roots; durable operator-visible mismatch evidence remains. |
| 5. Rerun Handoff Freshness Gate | Partial | Export-time identity and execution-time validation exist; audit-time-to-export-time comparison remains. |

## Plan

### Phase 1: Latest Report Authority

Goal: the Reports audit table must use the latest completed audit report, not a
stale CSV that happened to have the newest filesystem mtime.

Implemented:

- Prefer a completed `audit_progress.json` latest CSV pointer when it is inside
  the configured audit report root, has the expected standard/priority kind,
  and exists as a file.
- Fall back to timestamped `audit_summary_*.csv` names before mtime.
- Keep priority and standard reports separate.

Remaining:

- Add per-report completion evidence or a completed-report ledger so fallback
  can reject a CSV left by a run that failed after partially writing reports.
- Keep the previous completed report authoritative while a newer audit is
  running or has failed.

Validation:

- `tests.python.desktop.test_service_status_files`
- Reports facade preview tests

### Phase 2: Replaced-File Rescan Guard

Goal: a replaced video at the same path must be treated as new probe input.

Implemented:

- `Get-ProbeCacheIdentity` includes path, size, mtime, and first/tail sampled
  content.
- The active guard covers same path, same size, same mtime, and different
  sampled bytes producing a different cache identity.

Remaining:

- Choose and implement the authoritative behavior for the preserved-metadata,
  unchanged-samples edge case: a full-file identity, a backend-exposed
  `rebuild_probe_cache` audit mode, or unconditional re-probe for authoritative
  runs.
- Add an API/WebView contract and focused test if cache rebuild becomes an
  operator-facing Audit option.

Validation:

- `ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1`
- Audit run smoke with a copied/replaced temporary media file when tool
  integration is in scope

### Phase 3: Row-Level Current-Data Evidence

Goal: the Reports table should make stale row evidence visible when a file
changes after the latest audit.

Work:

- Add audit CSV identity columns for source byte length, last-write UTC, and a
  content identity comparable with a current source file.
- Have `GET /api/audit-results` compare loaded rows against current file state
  for displayed rows and mark missing, changed, or unverifiable rows.
- Render stale/missing audit rows as warning or blocker rows and require a fresh
  audit before decisions that depend on old issue codes.

Validation:

- Audit preview unit tests with current, missing, changed-size, changed-mtime,
  changed-identity, and legacy-unverifiable CSV rows
- Reports WebView static/browser smoke for stale-row rendering

### Phase 4: Audit Source Consistency

Goal: the Audit source table and latest audit table should describe the same
current library roots after an audit completes.

Implemented:

- Successful audit process exit calls
  `sync_audit_sources_after_process_exit` and reuses the read-only source scan.
- The sync result identifies completed audit roots that are not configured as
  Audit source rows.

Remaining:

- Persist and surface unmatched-root evidence in the Audit source or latest
  audit payload instead of leaving it only in callback results/logging.

Validation:

- `tests.python.desktop.test_audit_sources`
- Browser-backed Maintenance/Reports smoke

### Phase 5: Rerun Handoff Freshness Gate

Goal: CSV rerun export must not quietly hand stale audit decisions to Queue.

Implemented:

- Export captures current source size, mtime, and `source_identity_v2` and
  disables rows whose source metadata cannot be read.
- Queue rerun validates exported source identity before execution.

Remaining:

- Reuse Phase 3 audit-time identity to compare the selected audit row with the
  file at export time.
- Block export for missing or changed rows, or return explicit stale-row
  warnings that require a fresh audit before export.

Validation:

- `tests.python.desktop.test_application_facade_reports`
- `tests.python.desktop.test_rerun_csv_preview`
- `tests/webview/test_webview_browser_maintenance_reports_smoke.py`

## Target Acceptance

These are completion criteria for the full plan, not claims that every item is
already implemented:

- Latest audit preview resolves only to a completed report, including fallback
  behavior after a running or failed audit.
- An authoritative fresh audit cannot reuse old probe data for any same-path
  replacement.
- Reports rows explicitly identify current, missing, changed, and legacy
  unverifiable source evidence before audit-to-rerun export.
- Audit source counts refresh after successful runs and unmatched roots are
  visible to the operator.
- Audit-to-rerun export compares audit-time and export-time identity, while
  Queue continues to validate export-time identity before execution.
- No Audit feature mutates source media; state and report writes remain within
  the documented backend-owned boundaries.
