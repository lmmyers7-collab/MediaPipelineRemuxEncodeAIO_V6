# Diagnostics review — 2026-07-09

## Executive assessment

**Assessment: not ready to rely on Diagnostics close-readiness for every active
Diagnostics workload.** The normal Diagnostics refresh, bounded tail, ActiveJobs,
command-history, investigation, and stale-rendering paths are generally deliberate
and well covered. However, a Tdarr Proof Pack started in the Diagnostics tab can run
in the background without entering the close-readiness authority chain. The backend
can consequently approve close while that diagnostic process is still running.

Findings: **0 P0, 1 P1, 2 P2, 1 P3.** This was a source-and-test review only. No
Diagnostics route, shell-open action, rerun, audit, cleanup, or delete action was
invoked.

## Scope and evidence

Reviewed the required operating, architecture, route-inventory, boundary, validation,
and generated-summary material, then traced the Diagnostics WebView, local API,
facade, process guards, command journal, ActiveJobs, Tdarr console, and tests. Key
surfaces included:

- `partials/page-diagnostics.html`; `diagnosticsView.js`, its log, active-job, and
  investigation modules; `diagnosticsTailView.js`; `diagnosticsBridge.js`; command
  history; and lifecycle bridge/rendering.
- `desktop/api/routes_read.py`, `read_payloads_status.py`, `handler.py`,
  `command_journal.py`, and `command_journal_policy.py`.
- Diagnostics facade/policy/open policy, ActiveJobs status/process services, process
  close guard, backend-shutdown route, and Tdarr Matrix service/facade.
- Diagnostics, journal, close-readiness, ActiveJobs, browser handoff, and Tdarr tests.

`GET /api/diagnostics`, `/tail`, `/state-summary`, `/commands`, and
`/backend/close-readiness` are inventory-declared read routes. The `POST`
Diagnostics routes are explicit shell-open or diagnostic-process commands; they are
not implicit side effects of refresh or row selection.

## Workflow traces

### 1. Diagnostics refresh

The page Refresh button invokes `refreshAll`, which reads Diagnostics alongside the
other backend read models. `renderDiagnostics` receives the backend DTO and renders
triage, drilldown, log rows, raw summaries, ActiveJobs, and the pipeline/launch log
states. A rejected read is passed to `renderDiagnosticsRefreshFailures`, which labels
the affected panels as a failed refresh and explicitly says that prior data may be
stale. This preserves the previous display rather than silently treating it as fresh.

The investigation trail combines the loaded Diagnostics DTO with state-summary,
command-history, Queue, Completed, Pending Publish, and refresh-failure inputs. Its
actions are allowlisted target keys; owner-page navigation is local UI selection only.

### 2. Log-tail and follow behavior

The file-tail control submits only a target key and a bounded byte request to
`GET /api/diagnostics/tail`. Backend policy clamps the request to 1 KiB–256 KiB,
resolves only an allowlisted target, rejects arbitrary paths, reads only the end of a
regular file, and reports missing, folder/non-regular, read-error, empty, and
truncated conditions. The UI disables concurrent tail reads and displays returned
authority as backend evidence; its text-scanning fallback is visibly labelled
advisory.

There is no continuous streaming/follow request in the reviewed Diagnostics tab.
“Follow” behavior is therefore bounded re-read/refresh behavior, not a background
file watcher. This is safe for refresh load but should not be described as a live
stream guarantee.

### 3. Active-job rendering

The facade builds ActiveJobs rows from persisted records; malformed, legacy, and
unreadable records become explicit review rows. The table renders at most 50 rows,
while the backend detail reader limits its source read to 20 records. Selecting a row
only displays detail and allowlisted Open/Tail actions. Process identity reconciliation
uses PID plus command-line/CWD checks and fails closed when identity cannot be
inspected.

### 4. Command-history rendering and persistence

Command results are normalized before journal storage: 50 entries maximum, bounded
strings/lists/maps/depth, atomic JSON replacement, and a best-effort SQLite mirror.
The live journal/JSON history is returned by `/api/commands`; SQLite status is
reported as a mirror and is never read back as command-history authority. Mirror
failure is surfaced as degraded persistence without replacing the JSON/in-memory
history.

The WebView renders journal entries as evidence, derives owner and issue views, and
keeps retry/mutation actions on their owning pages. It correctly distinguishes a
background Tdarr launch from a completed Tdarr run in its immediate status text.

### 5. Investigation details and open actions

Row detail actions are constructed from a finite list of target identifiers. Tail
actions call the read-only tail route; open actions call the explicit, token-protected
OS-shell route. Diagnostics Bridge selection itself only changes the selected target
and page, without reading/opening a path. The Tdarr evidence opener is also keyed by
run ID, finding key, and an allowed evidence target.

### 6. Empty, stale, unavailable, malformed, oversized, and redacted evidence

- Empty/missing/unavailable/truncated/read-error states have distinct backend payload
  and frontend labels for logs and file tails.
- State-summary directory enumeration and recent entries are capped; tail bytes are
  capped; command journal values are bounded.
- Malformed ActiveJobs records appear as invalid/unreadable evidence rather than being
  converted to a completed result.
- Stale refresh failure is labelled stale in the UI. Stale progress is intentionally
  non-blocking only after the backend’s related-process, watcher, and fresh-progress
  checks have found no live work.
- Command-journal `data` and `request` fields redact sensitive-key values and free
  text URL/token assignments. The redaction boundary does not extend to all raw
  Diagnostics evidence; see finding 002.

### 7. Backend crash/restart behavior

On Local API failure, refresh leaves prior UI evidence visible with an explicit stale
warning. On backend restart, the journal reloads its bounded JSON history and ActiveJobs
records remain available to the status reader. Process guard detection scans matching
PowerShell pipeline/audit/rerun processes, so it can protect a restarted backend that
lost an in-memory `Popen` handle. Missing process-inspection capability fails closed.

The exception is the Diagnostics-created background Tdarr process in finding 001:
its persisted metadata supports the Tdarr console, but close-readiness does not
consult it.

## Findings

### CSW-2026-07-09-DIAGNOSTICS-001 — P1: Close-readiness omits active background Tdarr proof runs

**Evidence.** `TdarrMatrixAuditServiceMixin._run_tdarr_matrix_audit_background`
launches a separate Python process and persists its PID/start-time metadata under
`Scratch/TestLibraries/TdarrMatrixRuns/_background`. The successful result declares
`background_started=true` and the Tdarr progress model reports `active`.
`ProcessGuardFacadeMixin.get_close_readiness`, however, only consults related
PowerShell pipeline/audit/rerun processes, promotion/queue/network state, watcher,
and normal pipeline/audit progress. It does not query Tdarr background metadata or
the Tdarr process state. The background runner also does not create an ActiveJobs
record.

**Impact.** During a running Proof Pack (or a targeted rerun using that background
path), `/api/backend/close-readiness` can report `safe_to_close=true`; the Diagnostics
view then enables backend shutdown. Closing hides/abandons an active diagnostic process
and contradicts the close-readiness contract’s active-work claim. A backend restart
does not repair the gap, because the persisted Tdarr metadata is still ignored by the
guard.

**Required remediation.** Make the process guard consume the existing keyed Tdarr
background-process state (including PID identity/start time), or register the run as a
first-class ActiveJob and reconcile it after restart. While the state is live or
unverifiable, report `safe_to_close=false`; report stale/incomplete runs as review
evidence rather than active work only after identity is definitively absent. Add this
same state to the Diagnostics Live/close evidence so the operator sees why close is
blocked.

**Tests to add.** Start a mocked Tdarr background Proof Pack, assert close-readiness
blocks before and after facade/server reconstruction, assert the close route refuses
normal shutdown, then assert terminal/stale-verified process state becomes
non-blocking. Include PID-reuse and unreadable metadata fail-closed cases.

### CSW-2026-07-09-DIAGNOSTICS-002 — P2: Raw Diagnostics evidence has no comparable secret-redaction boundary

**Evidence.** Journal policy redacts sensitive-key values in `data`/`request` and
redacts token-like free text. In contrast, `diagnostics_tail_file_payload` returns
decoded allowed log content verbatim, and `active_job_detail_rows` exposes persisted
`command_line`, stdout/stderr paths, CWD, metadata, and legacy/invalid-record fields.
The selected ActiveJobs and tail detail renderers insert those values directly into
Diagnostics text. No redaction helper is applied on either backend evidence path.

**Impact.** A tool that writes a bearer token, password assignment, signed URL, or
credential-bearing command line to an otherwise allowlisted log/ActiveJobs record
will expose it to the WebView and its diagnostics response. Local token authentication
narrows access, but does not meet the stronger “diagnostics evidence must not leak
sensitive data” boundary, especially for screen sharing, copied evidence, or an
in-page compromise.

**Required remediation.** Apply one shared display-redaction policy before emitting
tail text and ActiveJobs detail fields, with an explicit, reviewable list of fields
that may remain raw. Preserve the fact that redaction occurred and keep full raw
evidence only in the local artifact subject to OS access controls. Extend the same
policy to journal `log_paths`, whose map values are bounded but not structurally
redacted when a sensitive key is supplied.

**Tests to add.** Seed an allowlisted log and valid/legacy/malformed ActiveJobs
records with `Authorization: Bearer`, `WorkerAuthToken=`, URL userinfo/query, and
password fields. Assert the API payload, journal history, and WebView detail text
exclude the secret while retaining a deterministic `<redacted>` marker.

### CSW-2026-07-09-DIAGNOSTICS-003 — P2: Shell-open results overstate an unobservable outcome

**Evidence.** `open_diagnostics_location` returns success when `service.open_path`
returns without raising. `diagnostics_open_success_message` says `Opened …`, and the
command result/journal mark `ok=true`. On Windows an OS shell dispatch can be accepted
without proving that the selected application opened the path or that the user saw it.
The equivalent Tdarr evidence-open helper has the same acknowledgement-only boundary.

**Impact.** Command History can present a successful open as completed evidence when
it only proves that the backend requested an OS shell operation. This is a limited
operator-trust issue, but matters when the tab is used to establish whether supporting
evidence was actually reviewed.

**Required remediation.** Change success wording and result data to “open request
submitted to the OS shell” (or equivalent), with a `delivery_acknowledged=true` /
`opened_unverified=true` field. Keep `ok=true` for successful dispatch but do not use
“Opened” as proof of client application completion.

**Tests to add.** Update the open-policy and command-history tests to assert the
acknowledgement wording and evidence boundary for normal Diagnostics and Tdarr evidence
open paths.

### CSW-2026-07-09-DIAGNOSTICS-004 — P3: API route inventory lists stale Tdarr actions

**Evidence.** `API_ROUTE_INVENTORY.md` describes the Tdarr audit actions as
`report`, `smoke`, `matrix`, `full`, and `strict-report`. The executable contract and
the page use `prepare-proof-pack`, `smoke-pack`, `proof-pack`, `strict-report`,
`cleanup-plan`, `cleanup-archive`, and `cleanup-delete`.

**Impact.** The route inventory is misleading exactly where Diagnostics exposes a
process and a guarded delete action. This weakens review/validation planning and
conceals the current cleanup surface from readers of the authoritative inventory.

**Required remediation.** Update the inventory in the implementation change that
addresses finding 001, including the cleanup actions, isolated proof-run-root write
scope, and backend confirmation/precondition rules.

## No-finding coverage

- **Refresh and stale rendering:** Diagnostics refresh failures are made visible and
  do not silently transform stale content into fresh success.
- **Tail confinement and bounds:** UI sends target keys, backend allowlists paths,
  rejects arbitrary paths, clamps bytes, and returns explicit non-file/missing/error
  states. Concurrent tail requests are suppressed.
- **ActiveJobs malformed state:** invalid, legacy, unreadable, orphaned, and stale
  process evidence is represented as review evidence; identity uncertainty is not
  treated as a matching process.
- **Command journal authority and bounds:** bounded JSON/in-memory journal is the
  served history; SQLite is a status-reporting mirror only. Atomic JSON writes,
  persistence degradation reporting, and bounded request/data evidence are present.
- **Investigation and handoff:** owner navigation and bridge selection do not send
  backend commands or arbitrary paths. Open/tail actions are finite allowlisted keys.
- **Hidden mutation boundary:** ordinary Diagnostics refresh, investigation rows,
  state summaries, command history, and tail reads are read-only. The Tdarr process,
  rerun, archive, and delete actions are explicit buttons/routes with backend-owned
  action allowlists; they are not hidden refresh side effects. Their close-readiness
  integration remains the P1 exception above.
- **Normal active-work close guard:** fresh pipeline/audit progress, live matching
  PowerShell processes, armed watcher state, network rerun batches, and guard
  inspection failures block closure. The backend rechecks readiness at shutdown rather
  than trusting the WebView button state.

## Test and contract assessment

Strong coverage exists for allowlisted tail reads, path rejection, byte clamping,
truncation, missing/non-file states, backend versus advisory evidence, stale refresh
labels, malformed ActiveJobs, command-journal bounds/redaction for request/data,
owner handoff, and normal close-readiness process/watcher failure modes. Browser smoke
also checks Diagnostics stale panels and UI duplicate suppression.

Material gaps:

- No integration test makes a background Tdarr process block close-readiness or
  validates behavior across Local API restart.
- No end-to-end redaction tests cover raw tail content, ActiveJobs detail, or sensitive
  `log_paths` keys.
- No test asserts that shell-open results are acknowledgement-only rather than proof
  of OS application completion.
- The browser Diagnostics smoke mocks Tdarr POST responses; it does not exercise
  close-readiness while the real persisted Tdarr background metadata is live.

## Coordinator handoff

1. Assign **CSW-2026-07-09-DIAGNOSTICS-001** to the process-lifecycle/Diagnostics
   owner first. Treat it as a release gate for any Diagnostics-background Proof Pack
   workflow.
2. Pair the lifecycle work with a route-contract and browser/API regression that proves
   safe shutdown is unavailable during a live Tdarr background run and after server
   restart.
3. Assign **002–003** to the Diagnostics/API evidence owner; use one shared
   presentation-redaction/acknowledgement vocabulary rather than separate frontend
   heuristics.
4. Update the API inventory with **004** in the same change packet as the actual route
   behavior change. Do not alter the inventory as a standalone workaround.

## Limits

- Review was static and read-only. I did not launch the Local API, open files, tail
  logs, start Tdarr, rerun cases, archive, delete, request shutdown, or process real
  media.
- No test suite was run because the requested audit explicitly prohibited invoking
  Diagnostics commands; findings are based on executable source, contracts, and the
  existing test suite.
- Existing worktree changes are extensive and unrelated to this review. This review
  created only this report and did not create or update a change packet, per the
  user’s file-scope restriction.
