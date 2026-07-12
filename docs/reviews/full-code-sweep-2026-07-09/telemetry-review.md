# Telemetry Tab Review — 2026-07-09

## Executive assessment

The live-observation path has good foundations: PowerShell atomically replaces the authoritative progress JSON; event and log reads are bounded; and the WebView creates nodes and writes text rather than interpolating event/log values as HTML. SQLite is correctly non-authoritative.

However, the current workflow misses core observation-trust boundaries. A polling GET /api/snapshot can rewrite ActiveJobs records; unreadable progress becomes apparently idle; a terminal failure becomes generic stale state after five seconds; and the first stale progress render is deliberately changed to active. These are behavioral/operator-trust defects, not style concerns.

No P0 finding was identified. Findings: 3 P1, 1 P2.

## Scope and evidence map

| Layer | Evidence reviewed | Role |
|---|---|---|
| Telemetry markup | apps/desktop/webview/static/partials/page-telemetry.html | Readiness, age/source trust strip, charts, GPU detail. |
| WebView | telemetryView.js, progressView.js, app.js | Refresh orchestration; telemetry/progress/event/log-derived rendering. |
| Client/formatting | apiClient.js, formatters.js, DOM helpers | Authenticated no-store GETs, timeouts, formatting, safe DOM construction. |
| Read routes | routes_read.py, read_payloads_status.py, API_ROUTE_INVENTORY.md | Snapshot, telemetry, diagnostics, bounded tail, close-readiness. |
| Python state | status readers, snapshot runner, facade, progress, events, ActiveJobs | JSON validation, stale policy, DTO/derived worker/ETA/FFmpeg evidence. |
| Pipeline writers | progress_state.ps1, logging.ps1, pipeline_engine.ps1 | Atomic progress state, append-locked events, terminal/hold state. |
| Tests | Focused Python, WebView, PowerShell tests | Input/contract/render/persistence coverage. |
| Derived mirror | STATE_FILE_SCHEMA_REFERENCE.md | SQLite shadow-mirror boundary. |

Generated summaries were read before the corresponding source where available. Most relevant summaries are structural/unparsed, so conclusions below use exact source and test evidence.

## Workflow traces

### 1. Initial telemetry load and polling

DOMContentLoaded starts refresh plus a 15-second automatic interval (apps/desktop/webview/static/assets/app.js:2012-2013). The refresh fans out through Promise.allSettled to snapshot, telemetry, diagnostics, close-readiness, and other reads (app.js:902-940). Snapshot is required; telemetry is optional. The shared client uses authenticated cache:no-store GETs with abortable timeouts (apiClient.js:506-531). In-flight refreshes are serialized (app.js:856-883).

A failed telemetry request calls the renderer with null and an unavailable reason instead of retaining the previous numeric sample (app.js:981-988; telemetryView.js:894-906). This creates a chart gap and is correct.

### 2. Progress, phase, ETA, throughput, and events

PowerShell writes pipeline_progress.json to a temporary file, then uses File.Replace/File.Move retry logic (ops/pipeline/engine/status/progress_state.ps1:769-793, 795-889). The JSON includes stage, percentage, queue values, copy bytes/rate, control flags, counts, and write-health fields (progress_state.ps1:812-878).

Python reads with a short bounded retry and validates the progress contract (src/mediapipeline/core/status/file_io.py:14-27; readers.py:16-27). The facade derives progress bars, worker state, FFmpeg log parsing, and ETA (src/mediapipeline/core/status/facade.py:79-118). The WebView creates progress DOM nodes with replaceChildren/textContent (progressView.js:939-997); ETA and FFmpeg evidence remain backend-derived (progressView.js:1872-1948).

### 3. Log excerpts and ActiveJobs

Snapshot log tail reads 150 lines and the low-level helper caps a tail at 262,144 bytes (readers.py:43-50; file_io.py:10-63). The live quick path requests a 64-KB allowlisted stdout tail (app.js:835-854). JSONL events are append-locked (ops/pipeline/engine/observability/logging.ps1:261-320); readers cap at 100 records and drop malformed/contract-invalid rows (readers.py:53-74). Snapshot retains 25 recent events (src/mediapipeline/core/observability/status_policy.py:712-713), and the UI renders 25 at most (progressView.js:1504-1521).

ActiveJobs readers preserve invalid, unreadable, legacy, and orphan-like evidence as review rows (src/mediapipeline/core/status/active_jobs.py:82-190, 399-412). Finding 001 shows that snapshot construction itself violates the passive-read boundary.

### 4. Holds and terminal state

Paused, stopped, idle, and completed stages are intentionally exempt from the normal stale check (src/mediapipeline/core/status/progress.py:58-72). The facade recognizes paused, stopped, completed, and failed state strings (src/mediapipeline/core/application/utilities.py:53-86). An operator-requested stop becomes a specific warning bar, not a failure (progressView.js:1159-1229). PowerShell writes paused, stopped, blocked, and unexpected-round-failure state/events (progress_state.ps1:196-234; pipeline_engine.ps1:323-364).

The failure/cancellation terminal semantics are not retained after the stale window; see Finding 003.

### 5. Missing, malformed, stale, or partial JSON

Atomic replacement reduces partial-file exposure. Reader failures return no progress, invalid trailing JSONL is ignored, and all tail handling is bounded. The missing semantic is a structured, operator-visible invalid/unavailable state: reader failure is discarded before DTO construction (Finding 002).

Telemetry independently detects stale samples, clock skew, degradation, and unavailable data (telemetryView.js:23-28, 253-285, 545-599). It handles failed fetches safely. The stale-progress path is weaker because terminal state is downgraded and first render suppresses stale status (Findings 003-004).

### 6. SQLite/derived state

State\mediapipeline_state.sqlite3 is explicitly a shadow mirror; JSON/state artifacts remain authoritative and mirror failures must not alter pipeline/queue/media behavior (docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md:586-605). It is not used to drive reviewed WebView observation decisions (STATE_FILE_SCHEMA_REFERENCE.md:617-620). No SQLite-authority finding was identified.

## Findings

### CSW-2026-07-09-TELEMETRY-001 — P1: Snapshot polling rewrites ActiveJobs records

GET /api/snapshot is registered as a read route (src/mediapipeline/desktop/api/routes_read.py:8) and is polled every 15 seconds (apps/desktop/webview/static/assets/app.js:2012-2013). Snapshot construction calls reconcile_active_job_records (src/mediapipeline/core/status/snapshot_runner.py:10-15). That helper changes dead/mismatched active records to orphaned, updates timestamps/reason fields, and writes them back (src/mediapipeline/core/processes/active_jobs.py:309-316).

Impact: observing Telemetry/Home/Live can change later ActiveJobs, launch, close-readiness, or Diagnostics evidence. It conflicts with the route inventory's claim that GET routes return data only (docs/inventories/API_ROUTE_INVENTORY.md:13-15). It does not mutate media, but it is a persistent pipeline-state mutation.

Required direction: make snapshot passive. Move reconciliation to an explicit command or independently scheduled lifecycle task with disclosed/journaled mutation; expose read-only would-reconcile evidence to observers.

### CSW-2026-07-09-TELEMETRY-002 — P1: Invalid/unreadable progress is shown as idle, not unavailable

Missing, malformed, partially read, or contract-invalid progress is logged and reduced to None (src/mediapipeline/core/status/readers.py:16-27). Snapshot building proceeds with that value (snapshot_runner.py:17-24), then the state resolver falls through to idle when there is no usable progress/audit state (src/mediapipeline/core/application/utilities.py:53-86). The facade returns empty raw progress and does not carry reader failure into DTO warnings (src/mediapipeline/core/status/facade.py:79-119).

Impact: a live process with an unreadable authoritative progress file can show idle/no active work. Telemetry can then infer no active work and call a zero NVENC reading expected idle. ActiveJobs/close-readiness may contain contradictory evidence, but the primary snapshot loses why it is uncertain.

Required direction: carry structured reader health into desktop_app_snapshot.v1 and return unavailable/invalid_state when a progress document exists but cannot be read. Use idle only after positive absence and corroborating ActiveJobs/close-readiness evidence.

### CSW-2026-07-09-TELEMETRY-003 — P1: Terminal failure is downgraded to stale/review after five seconds

The stale predicate exempts idle, sleeping, paused, stopped, and completed, but not failed, blocked, cancelled, or similar terminal-error stages (src/mediapipeline/core/status/progress.py:58-72). A failure aged beyond five seconds therefore becomes stale. Snapshot construction then replaces current activity with stale wording (src/mediapipeline/core/status/snapshot_runner.py:42-53); facade pipeline state gives stale precedence (src/mediapipeline/core/application/utilities.py:57-58). Progress policy returns warning for any stale state before evaluating failure tokens (src/mediapipeline/core/observability/status_policy.py:206-218).

Impact: terminal failure is not durable as terminal state in the main snapshot. Bounded events/failure reports might still contain the truth, but are not guaranteed to be present or primary. Cancelled/blocked terminal forms share the gap.

Required direction: classify failed, blocked, cancelled, and orphaned states as terminal first; add separate evidence-age/stale-terminal fields. Preserve stable error code/reason in current_work/terminal-outcome.

### CSW-2026-07-09-TELEMETRY-004 — P2: First stale progress poll is rendered active

The renderer requires two stale observations before showing stale (apps/desktop/webview/static/assets/progressView.js:12, 161-173). On the first stale payload it clones the bar with stale:false and changes warning to active (progressView.js:168-173). Polling is every 15 seconds (app.js:2012-2013).

Impact: backend-confirmed stale progress displays as current for one additional poll interval, although the backend stale threshold is five seconds. This violates stale-data trust and makes Finding 003 worse.

Required direction: show backend-confirmed stale immediately. If anti-flicker is needed, suppress only visual animation, never warning/stale semantics.

## No-finding coverage

- JSON remains authoritative for reviewed progress/events/ActiveJobs behavior; SQLite is not an input to the reviewed live state.
- PowerShell progress replacement is atomic and retried (progress_state.ps1:769-889); Python retries once before rejecting JSON (file_io.py:14-27).
- JSONL integrity/bounds are sound: append lock, bounded tail, invalid-line/contract filtering (logging.ps1:261-320; file_io.py:66-85; readers.py:53-74).
- Event/log/progress/GPU rendering uses text nodes and replaceChildren; no reviewed payload is inserted through innerHTML (telemetryView.js:729-925, 977-1019; progressView.js:939-997, 1504-1521).
- Telemetry freshness handles stale, clock-skew, unavailable, and degraded samples and inserts chart gaps on failed fetch (telemetryView.js:253-285, 545-599, 894-906).
- Telemetry markup has no pipeline-control action and the frontend uses GET-only refresh. This no-finding is limited by Finding 001: the backend's GET path is not side-effect free.

## Test and contract assessment

Existing tests are meaningful but miss the end-to-end semantics at issue.

- tests/python/desktop/test_service_status_readers.py:100-205 covers malformed/invalid progress/events and bounded tails, but only reader logging/return values—not API unavailable-vs-idle semantics.
- tests/python/desktop/test_service_status_progress.py:41-84 covers stale/pause/publish-copy timing, but no failed/blocked/cancelled state that must remain terminal after the stale window.
- tests/python/desktop/test_service_status_snapshot_runner.py:134-171 covers stale activity; :342-351 only confirms reconciliation exceptions are logged, not that GET snapshot has no writes.
- tests/python/desktop/test_service_status_active_jobs.py:396-463 covers bad active-job updates/no evidence, not snapshot immutability or orphan terminal visibility.
- tests/webview/test_webview_browser_telemetry_smoke.py:190-250 covers expected idle NVENC, unavailable telemetry, clock skew, stale telemetry, and chart gaps. It does not exercise stale snapshot bars or first-poll rendering.
- PowerShell tests cover progress pause/block persistence and JSONL locking/rotation (ops/pipeline/tests/Unit/Invoke-ProgressStateTelemetryChecks.ps1:166-173; Invoke-LoggingJsonLineChecks.ps1:37-144), not Python/WebView terminal-state interpretation.

Recommended regression contracts:

1. Hash ActiveJobs before/after repeated GET /api/snapshot and assert no record/timestamp/process state changed.
2. A malformed/locked progress document plus active ActiveJobs must yield unavailable/invalid_state, never idle.
3. Failed, blocked, cancelled, and orphaned outcomes older than the stale window must retain terminal state plus a separate age signal.
4. Browser fixture: first stale:true progress response must never render active.

Per docs/testing/VALIDATION_LADDER_RUNBOOK.md:9-20, a repair needs targeted Python route/status tests plus non-browser/browser WebView smokes; PowerShell state changes also need focused pipeline/reliability checks. No tests were run for this read-only review.

## Cross-tab handoff

| Consumer | Handoff |
|---|---|
| Home / Live | Polls affected snapshot; may show false idle, stale-as-active, or stale terminal failure. |
| Launch / close-readiness | Do not treat snapshot as passive evidence while it reconciles ActiveJobs. |
| Diagnostics | Surface explicit progress-read health beside bounded logs/ActiveJobs; do not make Diagnostics the sole durable terminal-failure view. |
| Telemetry | Expected encoder mode derives from snapshot activity (telemetryView.js:498-525); fix snapshot uncertainty/terminal semantics before using it for operational guidance. |
| Queue / Completed / Pending Publish | Preserve failure/pending evidence outside the 25-event window; do not infer completion from stale/idle presentation. |

## Limits

- Static read-only review only: no pipeline start, mutation request, runtime-state change, or test execution.
- The worktree had extensive unrelated uncommitted work. Telemetry-specific files were clean; app.js had unrelated in-progress changes and was inspected only for its active refresh path.
- This review excludes real-media routing, FFmpeg/subtitle/audio policy, and production LocalBase runtime observation.
