# Reports Review — Full Code Sweep 2026-07-09

## Executive assessment

**Assessment: Reports is not ready to be treated as authoritative triage evidence.**

The Reports tab has strong backend ownership: reads are backend-resolved; open actions are allowlisted and row-key based; mutations use authenticated strict-JSON routes; destructive artifact cleanup is confirmation/fingerprint protected; and POST results are journaled with secret-style fields redacted. Audit rerun export hands off to Queue preview and does not start work.

Three P1 defects can nevertheless make a clean Reports view unsafe to interpret: rejected subrequests leave prior data rendered without a local stale state; failure-read errors are represented as warnings rather than unavailable evidence; and the 100-row failure cap computes critical posture only over the first 100 records. Audit row freshness is also a known P2 gap: current display is a CSV snapshot, not current-file evidence.

No P0 finding was identified. No live Reports command was invoked. This review assessed the supplied dirty worktree and changed only this file.

## Evidence map

| Area | Evidence reviewed | Assessment |
| --- | --- | --- |
| UI | `page-reports.html`, `reportsView.js`, all `assets/reports/*.js` | Traced failure, audit, locations, progress, filters, selection, open, and command paths. |
| Refresh | `assets/app.js`, `assets/app/refresh.js` | Normal refresh requests failure/audit previews at `limit=100`; rejected optional reads only affect global Refresh Health. |
| Backend reads | `read_payloads_inventory.py`, audit/failure facades, policies, DTOs, route contracts | Authenticated and bounded. Audit carries explicit errors/full aggregates; failure does not carry an error and aggregates only capped rows. |
| Backend commands | Command contracts, handler, audit/failure mixins and facades | Validation, backend ownership, confirmation, journaling, and open-path limits traced without execution. |
| Artifacts/docs | Runtime Artifact Inventory, Log Artifact Catalog, Audit Tool Current-Data Plan | Ownership is documented; row-level audit freshness remains planned. |
| Tests | Reports static/facade tests, command contract/journal tests, browser Maintenance/Reports smoke, command-boundary audit | Good structural/command coverage; gaps remain for failed reads, failure error rendering, and critical rows after the cap. |

## Workflow traces

### 1. Load and refresh

`refreshAllNow` builds `/api/failures?limit=100` and `/api/audit-results?limit=100`, executes them with the dashboard read fan-out, and renders a Reports pane only if the corresponding result is fulfilled. Failed optional reads go to the global `failures` array and Refresh Health. There is no Reports-local unavailable replacement, stale label, or rendered last-successful timestamp.

Successful audit reads return source, all-record counts, category counts, truncation warnings, and errors. Successful failure reads return a total count and truncation warning, but important group/posture calculations are based only on the delivered rows.

### 2. Failure triage and filtering

The backend reads markers or the latest failure JSON, enriches rows with retry state and evidence, and builds Resolution Center groups. The browser then applies search and chips. Hidden selected rows block selected-row actions. The 250-row DOM render cap is disclosed; it is separate from the earlier 100-row API cap.

Failure resolver/loader/JSON/marker failures return warning-only DTOs. The UI checks `failures.error` to decide unavailable status, so those warning-only failures can be interpreted as loaded empty results.

### 3. Audit/evidence presentation

The backend chooses the latest audit CSV, parses records, applies the audit-ignore manifest, returns counts and duplicate metadata over all visible records, and returns explicit error text for unavailable/malformed CSV states. Diagnostics handoffs open only backend-selected locations.

The audit table is a snapshot of the chosen CSV. It does not compare displayed media with current files or show audit-time identity/current-data status.

### 4. Open/export/download

Failure evidence open submits only `row_key`, `target`, and `source_kind`; the backend re-loads the current row and validates an allowed evidence root. Report location buttons use Diagnostics target keys.

Audit export submits selected row keys, or no keys. With no keys, the confirmation correctly says it will export all non-ignored latest-CSV rows. The backend reloads the current CSV, writes only its own rerun-import CSV, then Reports opens Queue's preview flow. It does not call rerun start or normal pipeline start.

### 5. Retry/repair/command controls

Reports does not directly retry, repair, drain, publish, rename, or process media. It can clear/archive failure state, clean failure artifacts, write failure lifecycle events, manage audit state, start/stop Audit, and generate a rerun import CSV. Later processing remains backend/Queue owned.

| Command class | Verified backend protection |
| --- | --- |
| Failure open | Current backend row + allowlisted target/root; frontend cannot submit a raw path. |
| Clear/archive | Strict booleans, apply confirmation, backend scope/path checks, manifest-backed archive. |
| Artifact cleanup | Strict booleans, confirmation, backend-root-only targets, preview fingerprint for selected files. |
| Lifecycle | Active backend group, allowed transition, current blocker recomputation, required reason/confirmation, append-only journal. |
| Audit start/stop | Backend launch lock/active-work policy; strict `confirm_stop` for stop. |
| Audit export | Backend current-record/ignore reconciliation; output only a CSV and Queue handoff. |
| Journal/redaction | POST handler validates before dispatch and journals outcomes/validation failures; journal policy redacts credentials, tokens, authorization, and password-like keys and bounds evidence. |

## Findings

### P1 — CSW-2026-07-09-REPORTS-001: Failed Reports reads leave stale evidence on screen without a local warning

**Evidence:** `assets/app.js` lines 930–940 records failed optional requests only in the global refresh list, while lines 1018–1030 render Reports panes only for fulfilled values. `assets/app/refresh.js` lines 183–195 renders the issue solely in global Refresh Health. Reports does not consume the attached refresh metadata or display a local last-successful timestamp.

**Impact:** A timeout/failure of failures, audit results, artifacts, controls, or audit-source reads can leave prior rows and statuses visible as though they were current. This can support stale triage and leave selection-dependent controls visually actionable against obsolete context.

**Required remediation:** Render a typed unavailable/stale DTO per failed Reports read. Preserve old data only with a prominent stale state and last successful time, and disable or revalidate selection-dependent commands until fresh data arrives. Add browser coverage that succeeds once, rejects each Reports route, then asserts local stale/unavailable state and safe command behavior.

### P1 — CSW-2026-07-09-REPORTS-002: Failure read errors are misclassified as empty/ready evidence

**Evidence:** `FailurePreviewDto` (`dto_inventory.py` lines 226–241) lacks an `error` field. Failure helpers in `failures/policy.py` lines 1376–1414 return warning-only DTOs. Audit has an explicit `error`. `failureModel.js` and `triage.js` branch on `failures.error`; a warning-only empty failure payload can therefore render `No rows`, `Clear`, `No action rows`, or `Ready`.

**Impact:** Unreadable/malformed failure JSON, unreadable marker state, or unavailable failure service can be presented as a clean failure result. This hides a failure of the evidence path itself.

**Required remediation:** Add typed failure `error`/unavailable status for resolver, loader, JSON, marker, and journal-read failures; propagate it to resolution summary; and make Failure/cross-tab triage fail closed to `Unavailable`/`Review needed`. Add facade, route, static, and browser tests for each unavailable/malformed state.

### P1 — CSW-2026-07-09-REPORTS-003: The 100-row failure cap can hide blocking posture and groups

**Evidence:** normal refresh hard-codes `limit=100` in `assets/app.js` lines 898–901. `failure_preview_fields` limits records to rows before calculating classifications, retry state, and resolution groups (`failures/policy.py` lines 1344–1372). `count` reports all records and a warning says “Showing 100 of N,” but `operator_required_count`, `permanent_count`, `transient_count`, primary group, and Resolution Center groups describe only the first 100.

**Impact:** An operator-required, permanent, or blocking failure after record 100 is absent from the top-level posture and cannot be recovered by browser filters. The warning does not disclose the omitted rows' severity or owner.

**Required remediation:** Page/cursor failures with full-set aggregates, or return full-set posture/group summaries with an explicit incomplete-detail state. A primary blocking state must remain blocking if omitted records are blocking. Test more than 100 records with an operator-required/permanent record after the cap.

### P2 — CSW-2026-07-09-REPORTS-004: Audit rows are not time-qualified against current media

**Evidence:** audit DTO rows are CSV-derived and have no audit-time identity/current-file comparison. The active `docs/implementation/audit-tool-current-data-plan.md` says the preview is a selected-CSV snapshot that does not stat displayed rows or flag changed files (lines 55–57), and marks row-level current-data evidence as Planned (lines 133–151).

**Impact:** A rerun/redownload/duplicate/manual-review recommendation can describe a file that has changed, disappeared, or been replaced since audit. Export-time and Queue execution-time identity checks help prevent processing the wrong current file but do not prove the old audit issue is still true.

**Required remediation:** Implement the plan's audit-time identity columns and current-file comparison; display changed/missing/unverifiable states prominently; require fresh audit for decisions dependent on stale issue codes. Add current, missing, changed-size, changed-mtime, changed-identity, and legacy-unverifiable tests.

### P0/P3

No P0 finding was identified. No additional P3 finding was recorded: bounded displays such as the six-entry open history are explicitly labelled and do not claim operational completeness.

## Verified no-finding coverage

- The frontend does not mutate state/media directly; examined actions route through backend HTTP handlers.
- Failure evidence open is row-key/allowlist/root constrained, and report-location open uses Diagnostics allowlists.
- Clear/archive/cleanup/lifecycle retain backend-owned validation and applicable confirmation/fingerprint/journal protections.
- Reports audit export creates only the backend-owned CSV and Queue preview handoff; it does not launch work.
- Audit aggregate counts are computed before the preview cap, and the backend warns when a subset is shown. Its no-selection export confirmation accurately states the all-non-ignored scope.
- Command journal tests cover secret/token/password/authorization redaction and bounded nested evidence. Local operator paths are intentionally retained for local evidence/open workflows, not treated as secrets.
- Busy UI guards and the browser smoke cover duplicate-click suppression for covered controls; audit start additionally has backend launch locking/active-work protection.

## Test and contract assessment

The route inventory, route contracts, strict command models, command-boundary audit, journal tests, facade-policy tests, and browser Maintenance/Reports smoke provide substantial command and ownership coverage. Existing coverage verifies failure confirmations, path restrictions, export-to-Queue preview handoff, and redaction/bounds.

Missing authority coverage:

- rejected Reports reads after a successful render;
- failure DTO error-state parity with audit;
- a blocking failure after the first 100 rows;
- audit row-level freshness; and
- operator-visible report source timestamp/authority evidence.

Suggested post-fix checks:

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_facade_failures_policy tests.python.desktop.test_facade_audit_policy tests.python.desktop.test_application_facade_reports tests.python.desktop.test_api_command_contracts tests.python.desktop.test_api_command_journal_policy -q
& $py -m unittest tests.python.desktop.test_reports_view_static tests.webview.test_webview_browser_maintenance_reports_smoke tests.webview.test_webview_command_boundary_audit -q
.\ops\scripts\smoke\Test-WebViewBrowserMaintenanceReportsSmoke.ps1
```

## Coordinator handoff

1. Treat **CSW-2026-07-09-REPORTS-001 through 003** as one P1 Reports-authority packet: typed stale/unavailable rendering, typed failure errors, and full-set failure posture must land together.
2. Preserve existing backend command boundaries; do not replace missing authority with frontend retry/repair inference.
3. Schedule **CSW-2026-07-09-REPORTS-004** through the existing Audit Tool Current-Data Plan, exposing an explicit backend status/evidence contract rather than a new frontend heuristic.
4. Add the missing API/browser regression cases before accepting a Reports refactor.

## Limits

- Static, read-only review only. No server, PowerShell audit, report open, export, clear, archive, cleanup, start, stop, retry, or repair command was run.
- No real media or live report artifacts were exercised.
- The worktree had extensive unrelated modified/untracked files, including Reports modules. They were not changed or validated beyond static inspection.
- Only this report file was created.
