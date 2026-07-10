# Pending Publish Review — 2026-07-09

## Executive assessment

**Disposition: needs targeted boundary remediation before the Pending Publish
surface can be considered fully compliant with its documented ownership model.**

The deferred-publish transaction is materially defensive: a parked item is
manifest-backed, media and sidecars are handled as one transaction, PowerShell
revalidates manifest trust immediately before a drain, and cleanup happens only
after a validated copy/reveal path succeeds (or an already-published proof is
accepted). The local API repair/reconcile routes also re-run their dry-runs,
require an exact fingerprint and `confirm_apply: true`, and restrict their
writes to manifests.

Two P2 boundary findings remain. The WebView computes and enforces a local
drain eligibility decision, contrary to the stated rule that it must not infer
drain safety. Separately, the PowerShell `pending_publish_index.ps1` module is
documented as read-only but runs crash recovery that moves files and rewrites
manifests while refreshing the index. A P3 operability finding notes that the
orphan-payload apply flow is correctly fail-closed but has no production
provider for the complete backend proposal that makes it usable.

No P0 or P1 finding was identified in the reviewed code. This was a static,
read-only review; no drain, repair, reconcile, or mutation route was invoked.

## Scope and method

I read the required operating, architecture, route-inventory, validation, and
no-touch documents before inspecting the requested Pending Publish WebView,
Python, PowerShell, DTO/contract, and test surfaces. I used generated summaries
before opening source where available. The inspected implementation included:

- `partials/page-pending.html`, `pendingPublishView.js`, and every
  `pendingPublishView.*.js` slice;
- `GET /api/pending-publish`, open/recovery, repair, and orphan-reconcile
  routes; the pipeline-start drain route; contracts and command journal flow;
- `core/publish/pending_*.py`, pending DTOs, repair/reconcile dry-run/apply;
- PowerShell pending manifest store, park, sidecar, drain, retry, repair, and
  index modules; and
- relevant Python, browser, mutation-boundary, and PowerShell safety tests.

## Workflow traces

| Trace | Observed control path | Assessment |
|---|---|---|
| 1. Discovery and health | `PendingPublishServiceMixin.scan_pending_publish()` enumerates the resolved pending root, parses manifests, adds orphan payload rows only after a complete manifest scan, detects duplicate local/destination targets, and exposes file-inventory/drain-summary evidence. `pending_publish_rows()` derives stable row keys, status, readiness, evidence fields, guidance, and allowed open targets. | Strong read-model coverage; scan errors, missing roots, malformed manifests, missing payloads/sidecars, legacy manifests, duplicate targets, retry exhaustion, and orphans are classified rather than treated as drain-ready. |
| 2. Evidence display | The partial contains row, selected-item, file-inventory, durable-summary, recovery, confidence, decision, repair, and post-drain evidence panels. The view modules render backend DTO evidence and use allowlisted row-key/target opens. | Good evidence separation. Display filters explicitly do not narrow drain scope. Finding 001 applies to the separately computed button guard. |
| 3. Recovery diagnostics | `POST /api/pending-publish/recovery-plan` rescans through the facade and returns a backend-authored `pending_publish_recovery_plan.v1` dry-run with `would_mutate: false`. Scan unavailable, invalid result, and selected-row-missing cases return explicit command errors. | Correctly read-only and failure-aware. |
| 4. Drain | WebView submits only `mode=drain_pending_pushes` to `/api/pipeline/start`; the Python launch facade serializes launches and checks active work. The PowerShell retry loop builds a durable summary, verifies trust per manifest, copies to a partial, writes/backs up sidecars, reveals media, then removes parked artifacts only after success. | Transactional PowerShell decision and movement authority are sound; see Finding 001 for the premature WebView authority decision. |
| 5. Repair/reconcile | Dry-runs use only backend scan/preview evidence and suppress the journal. Apply re-runs the dry-run, requires matching fingerprint plus strict `confirm_apply is True`, validates the proposed v1 manifest, uses atomic writes, and journals confirmed operations. Orphan apply creates only the payload-adjacent manifest and verifies payload size and sidecars. | Strong mutation containment. Finding 003 concerns the missing production source for a usable orphan proposal. |
| 6. Degraded states | Python row policy blocks missing/invalid/unreadable manifests, missing payloads, duplicate targets, and retry exhaustion; the durable summary marks unreadable/stopped/error state. PowerShell independently refuses untrusted paths/state/schema/sidecars and preserves the parked artifacts on error or partial reveal failure. | Fail-closed in the decision and media-movement paths. Backend/service-unavailable states are surfaced as errors and the page’s default guard is blocked. |

## Findings

### CSW-2026-07-09-PENDING-001 — P2: WebView makes a drain eligibility decision and prevents the backend from evaluating it

**Evidence.** `apps/desktop/webview/static/assets/pendingPublishView.confidence.js`
computes `pendingDrainGuardState()` from page rows, summaries, filters, command
history, and snapshot context, then returns `allowed` and labels the outcome
“allowed” or “blocked locally” (lines 899–1008). It disables both drain
buttons. `apps/desktop/webview/static/assets/launchView.js` consumes that value
and, when it is false, appends a local `pending_publish.drain` result and exits
without posting `/api/pipeline/start` (lines 1117–1136). The browser smoke
explicitly requires this behavior in
`tests/webview/test_webview_browser_pending_drain_guard_smoke.py`.

**Why this matters.** `AGENTS.md`, `MODULE_MAP.md`, and the Pending Publish
fixture inventory require that WebView/Tauri not infer drain safety. A local
interlock can be useful as advisory UX, but it is still an authority decision
when it prevents the sole backend drain path from running. The browser’s
derived view can be stale, incomplete, capped, or differ from the actual
PowerShell manifest set. The PowerShell drain already owns the authoritative
per-manifest trust validation and safely rejects blockers.

**Recommendation.** Retain the local evidence as `advisory` / `review
required`, but do not produce a frontend `allowed`/`blocked` safety verdict or
short-circuit submission. Submit the unchanged all-scope drain request after
operator confirmation, and present the backend launch/drain result as the
decision. If an availability interlock is required for a specific hazard,
replace it with a backend-authored preflight contract and test it as such.

### CSW-2026-07-09-PENDING-002 — P2: The documented read-only pending index performs file and manifest mutation during refresh

**Evidence.** `docs/architecture/MODULE_MAP.md` and
`docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md` assign
`pending_publish_index.ps1` a read-only in-memory index/health role and say it
must not move, delete, drain, or repair payloads. In contrast,
`ops/pipeline/engine/publish/pending_publish_index.ps1:78` invokes
`Repair-PendingManifestState()` from `Refresh-PendingPublishIndex()`.
`ops/pipeline/engine/publish/pending_repair.ps1:16–44` can move parked
sidecars, and lines 68–85 can move `original_local_file` to `local_file`, write
`manifest_state=parked_recovered`, and timestamp the manifest. Index refresh is
called by startup/queue and retry/drain paths.

**Why this matters.** The crash-recovery transaction itself is defensively
implemented and trust-gated, but an operation named and documented as an index
refresh has side effects. That makes a reader unexpectedly mutate local encoded
output and pending manifests, weakens safe read-only diagnostics expectations,
and hides recovery from a distinct command/evidence boundary.

**Recommendation.** Split crash recovery from index construction. Invoke an
explicit backend-owned recovery step at the authorized pipeline lifecycle
boundary, record its outcome, then have `Refresh-PendingPublishIndex()` only
read the post-recovery state. If automatic recovery remains intentional, update
the ownership contract and make the mutation explicit in its function name,
callers, progress/event evidence, and test matrix.

### CSW-2026-07-09-PENDING-003 — P3: Orphan-payload reconcile is correctly fail-closed but has no production proposal producer

**Evidence.** Normal orphan discovery in
`src/mediapipeline/core/publish/pending_paths.py` returns only observed payload
facts; it does not attach a backend manifest proposal. The reconcile dry-run
accepts a candidate only if a row already contains
`backend_manifest_proposal`, `orphan_manifest_proposal`, or
`proposed_manifest` (`core/repair_reconcile/dry_run.py:1232–1248`). Repository
search found these fields only in that consumer and test fixtures, not in a
production proposal builder. The ordinary-orphan tests intentionally assert
`proposed_manifest_available=False`; candidate tests inject the field into the
row.

**Why this matters.** The safe default is excellent—ordinary orphan payloads
cannot be turned into a guessed manifest. Operationally, however, the exposed
reconcile apply control cannot succeed from the normal Pending Publish scan,
so operators reach a permanent dry-run-only dead end.

**Recommendation.** Either mark the production control unavailable until a
trusted backend evidence producer exists, or add a narrowly scoped producer
that derives a complete proposal from durable transaction/sidecar evidence and
validates pending/output roots before it reaches the dry-run. Do not relax the
current no-inference rule or let WebView/request payloads supply proposal
fields.

## No-finding coverage

- **Manifest and path trust:** PowerShell requires `pending_push_manifest.v1`,
  required text/array fields, supported drain state, retry budget, pending-root
  containment, destination safety, and trusted sidecars before drain. Legacy,
  malformed, missing-payload, outside-root, and retry-exhausted manifests are
  rejected and retained.
- **Media-plus-sidecar lifecycle:** park creates a `pending_move` intent,
  parks sidecars, round-trips the manifest, then transitions to `parked`.
  Drain copies to a partial, publishes sidecars with rollback/backup handling,
  writes the final sidecar, reveals final media, and only then removes local
  payload/sidecars/manifest. Existing server copies require sidecar/identity
  proof before local cleanup.
- **Drain evidence and partial failure:** `pending_drain_summary.json` is
  atomically written and records counts, items, status/route counts, stopped,
  deferred, and remaining state. Event/progress evidence includes transaction,
  target, and sidecar information. Copy, sidecar, backup, and reveal failures
  retain the pending artifacts and record retry state.
- **Repair/reconcile controls:** apply re-runs its dry-run, checks a full
  fingerprint, requires literal boolean confirmation, validates v1 proposals,
  backs up rewrites where an original manifest exists, atomically writes, and
  reports source/payload/output unchanged evidence. No repair/reconcile route
  sends a drain or moves media bytes.
- **Unavailable/stale evidence:** scan exceptions and unavailable services
  produce error DTOs; missing root is distinct from an empty root; unreadable
  drain summaries are blocked evidence; stale summary row counts are treated
  as review evidence rather than current truth; display filters do not alter
  backend drain scope.
- **Command/process safeguards:** `/api/pipeline/start` uses the process launch
  lock and active-work checks, while confirmed repair/reconcile operations are
  journaled and dry-runs explicitly suppress journaling.

## Test and contract assessment

The reviewed suite has meaningful static and temp-fixture coverage:

- `Invoke-PendingPublishSafetyChecks.ps1` exercises trust rejection, legacy and
  missing-payload preservation, retry exhaustion, path boundaries, strict
  booleans, sidecar rollback, batch/deferred summaries, and drain evidence.
- `test_pending_publish_service.py` plus the manifest/path/row tests cover
  discovery and classification; `test_application_facade_pending_publish.py`
  covers read DTOs, durable summary presentation, open allowlists, recovery
  plans, and scan failures.
- `test_repair_reconcile_dry_run.py`, `test_repair_reconcile_apply.py`, API
  contract tests, and the Local API smoke cover allowlisted payloads,
  fingerprint/confirmation gating, no-media mutation, journaling, and
  manifest-only writes.
- Browser/mutation-boundary coverage verifies recovery, repair, and diagnostic
  request shapes. It also currently codifies Finding 001’s local drain gate,
  so those tests must change with the ownership correction.

Gaps to hand off: add a regression proving an index-only refresh cannot mutate
files (or explicitly tests and journals the separated recovery operation);
add an end-to-end production-source test for an orphan proposal if the feature
is retained; and preserve a real-media deferred publish → interrupted/partial
drain → successful drain validation rung for any change to the PowerShell
transaction path.

## Coordinator handoff

1. Assign **CSW-2026-07-09-PENDING-001** jointly to Pending Publish WebView and
   process-launch owners; it crosses `pendingPublishView.confidence.js`,
   `launchView.js`, browser smoke expectations, and the authority docs.
2. Assign **CSW-2026-07-09-PENDING-002** to the PowerShell publish/transaction
   owner. Treat it as a recovery-boundary refactor; select the validation rung
   before editing because it affects parked outputs and manifests.
3. Assign **CSW-2026-07-09-PENDING-003** to the Pending Publish
   repair/reconcile owner for a product decision: hide/label unavailable versus
   implement a provenance-checked backend proposal producer.
4. Do not merge a remediation that changes park, drain, sidecar, or recovery
   behavior without the pending-publish fixture tests and representative
   real-media deferred-publish/drain validation required by the no-touch and
   validation runbooks.

## Review limits

- Static code and test review only; I did not execute tests because the audit
  was read-only and the request prohibits mutations.
- I did not run drain, repair, reconcile, recovery, or any other mutation
  route, and did not inspect a live `LocalBase` runtime state or real media.
- The report is the only file created/changed by this review. No change packet
  was created because the request explicitly prohibits change-packet updates.
