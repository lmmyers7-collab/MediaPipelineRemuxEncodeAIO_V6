# Completed Output Review — 2026-07-09

## Executive assessment

Completed Output has a strong backend-owned design. The page reads the
authoritative local JSONL completion history, makes proof freshness explicit,
separates historical rows from currently present output, and treats acceptance,
reconciliation, and diagnostics as evidence rather than frontend authority.
Selected-row repair routes are narrowly scoped, re-run their backend dry-run,
require a matching fingerprint and strict `confirm_apply: true`, and only write
manifest/sidecar metadata. I found no path from table filters, rendered-row
caps, evidence selection, or diagnostics links to backend processing scope.

Two findings remain. The more important is a contract violation in the apply
journaling sequence: a metadata repair can commit and return success even when
the journal persistence path has failed, although the published contract says
journaling is required and journal failure is a rollback condition. The other
is observability: malformed JSONL lines are intentionally skipped but never
become completed-preview warning/evidence, so an operator cannot distinguish a
clean partial history from a silently truncated/corrupt one.

Scope: read-only source, contract, and test review. No repair/apply, publish,
drain, open, or diagnostic route was invoked.

## Workflow traces

### 1. Load, filtering, selection, and evidence display

1. `GET /api/completed` calls the facade preview with a bounded proof mode and
   overlays the read-only Completed-to-Pending reconciliation result
   ([read_payloads_inventory.py](../../../src/mediapipeline/desktop/api/read_payloads_inventory.py:23),
   [read_payloads_inventory.py](../../../src/mediapipeline/desktop/api/read_payloads_inventory.py:38)).
2. The service uses `completed_jobs.jsonl` as the authority, not a share walk;
   it caches for 60 seconds but invalidates on manifest mtime or force refresh
   ([service.py](../../../src/mediapipeline/core/completed/service.py:40),
   [service.py](../../../src/mediapipeline/core/completed/service.py:61)).
3. The reader returns recent JSONL records newest-first and stamps each row
   `live` or `deferred` proof; deferred rows present as not checked rather than
   claimed present ([manifest.py](../../../src/mediapipeline/core/completed/manifest.py:55),
   [manifest.py](../../../src/mediapipeline/core/completed/manifest.py:137)). The
   DTO carries path, presence/proof status, consistency, route, size,
   audio/subtitle decisions, validation, and trust fields
   ([policy.py](../../../src/mediapipeline/core/completed/policy.py:475),
   [policy.py](../../../src/mediapipeline/core/completed/policy.py:542)).
4. The Current table derives a local subset and applies text/status/
   investigation/library filters only in the WebView
   ([table.js](../../../apps/desktop/webview/static/assets/completed/table.js:669)).
   Filter-scope evidence explicitly says actions receive neither filter state
   nor visible-row subsets, and names reconciliation, diagnostics, rerun, and
   manifest authority as unchanged ([filterScope.js](../../../apps/desktop/webview/static/assets/completed/evidence/filterScope.js:80),
   [filterScope.js](../../../apps/desktop/webview/static/assets/completed/evidence/filterScope.js:90)).
5. Selection is client state keyed by backend `row_key`; the render cap retains
   a selected row in the table window, while **Show Selected** only clears local
   filters/pins rendering and says backend scopes are unchanged
   ([table.js](../../../apps/desktop/webview/static/assets/completed/table.js:446),
   [completedView.js](../../../apps/desktop/webview/static/assets/completedView.js:1004)).
6. Evidence distinguishes exact path proof from same-leaf review and turns a
   missing output without exact pending/drain proof into a blocker
   ([completedView.evidence.js](../../../apps/desktop/webview/static/assets/completedView.evidence.js:727),
   [completedView.evidence.js](../../../apps/desktop/webview/static/assets/completedView.evidence.js:830)).
   The acceptance board separately surfaces display-filter scope and declares
   acceptance an operator judgment rather than a WebView mutation
   ([acceptance.js](../../../apps/desktop/webview/static/assets/completed/evidence/acceptance.js:119),
   [acceptance.js](../../../apps/desktop/webview/static/assets/completed/evidence/acceptance.js:243)).

### 2. Output acceptance, proof, and diagnostics controls

The markup separates read-only proof/acceptance boards from backend actions:
acceptance readiness has no mutation button
([page-completed.html](../../../apps/desktop/webview/static/partials/page-completed.html:482)),
and the evidence packet is explicitly rendered/copy-only
([page-completed.html](../../../apps/desktop/webview/static/partials/page-completed.html:511)).
The proof board labels missing output with pending proof, drain proof, or no
proof separately, then exposes a read-only backend reconciliation refresh
([page-completed.html](../../../apps/desktop/webview/static/partials/page-completed.html:545),
[page-completed.html](../../../apps/desktop/webview/static/partials/page-completed.html:575)).

Diagnostics actions use fixed targets (`completed_manifest`, `run_logs`,
`last_stderr_log`, conditional failure/pending targets), not row paths
([completedView.diagnostics.js](../../../apps/desktop/webview/static/assets/completedView.diagnostics.js:17)).
The module delegates those targets to Diagnostics open/tail helpers and never
forms a filesystem path ([completedView.diagnostics.js](../../../apps/desktop/webview/static/assets/completedView.diagnostics.js:68)).

### 3. Open actions

The UI posts only `{row_key, target}` to `/api/completed/open`
([openActions.js](../../../apps/desktop/webview/static/assets/completed/openActions.js:62)).
The facade reloads all manifest records, rejects a missing row or non-allowlisted
target, derives the path from the manifest record, and then calls the designated
open service ([open_facade.py](../../../src/mediapipeline/core/completed/open_facade.py:31)).
Targets are limited to output file/folder, sidecar, and source folder
([open_policy.py](../../../src/mediapipeline/core/completed/open_policy.py:55)).

### 4. Dry-run repair/reconcile

The Completed controls offer only selected-row dry-runs for manifest
reconciliation and sidecar metadata repair; both Apply buttons start disabled
([page-completed.html](../../../apps/desktop/webview/static/partials/page-completed.html:177)).
The browser request body is bounded to `scope=selected`, `row_key`, `limit=1`,
and a reason—no paths or patches ([completedView.repair.js](../../../apps/desktop/webview/static/assets/completedView.repair.js:230)).

The server-side dry-run looks up the submitted key only in freshly loaded
backend preview rows ([dry_run.py](../../../src/mediapipeline/core/repair_reconcile/dry_run.py:688)).
It records idle-pipeline and backend-path-authority preconditions, publishes
no-touch evidence for source/scratch/output/pending payload bytes, and suppresses
the command journal for dry-run only
([dry_run.py](../../../src/mediapipeline/core/repair_reconcile/dry_run.py:93),
[dry_run.py](../../../src/mediapipeline/core/repair_reconcile/dry_run.py:118)).

For manifest repair, missing output is a hard block; only
`manifest_missing_output_path` and `output_sidecar_mismatch` form candidates
([dry_run.py](../../../src/mediapipeline/core/repair_reconcile/dry_run.py:845)).
For sidecar repair, missing/unreadable sidecars are hard blocks and only the
three metadata fields (`source_path`, `output_path`, `output_file`) are proposed
([dry_run.py](../../../src/mediapipeline/core/repair_reconcile/dry_run.py:934),
[dry_run.py](../../../src/mediapipeline/core/repair_reconcile/dry_run.py:988)).

### 5. Apply, fingerprint, refresh, and no-media boundary

The WebView enables Apply only when its selected key, expected candidate command,
`safe_to_apply`, and dry-run fingerprint all agree
([completedView.repair.js](../../../apps/desktop/webview/static/assets/completedView.repair.js:67),
[completedView.repair.js](../../../apps/desktop/webview/static/assets/completedView.repair.js:175)).
Apply posts that fingerprint plus the literal boolean `confirm_apply: true`
([completedView.repair.js](../../../apps/desktop/webview/static/assets/completedView.repair.js:241)).

The facade does not trust the browser’s saved preview: it creates a fresh
backend dry-run immediately before applying
([facade.py](../../../src/mediapipeline/core/repair_reconcile/facade.py:110)).
The apply function rejects a non-boolean/non-true confirmation, mismatch,
unsafe current dry-run, or no selected candidate
([apply.py](../../../src/mediapipeline/core/repair_reconcile/apply.py:350)).
It takes a backup and uses atomic replacement for sidecar/manifest metadata,
then compares the protected source/output/payload paths before and after
([apply.py](../../../src/mediapipeline/core/repair_reconcile/apply.py:225),
[apply.py](../../../src/mediapipeline/core/repair_reconcile/apply.py:402)).

The completed writers themselves validate sidecar round trips before emitting a
best-effort append-only local manifest mirror; failed appends are logged/events,
not treated as media failure ([sidecar.ps1](../../../ops/pipeline/engine/publish/sidecar.ps1:241),
[sidecar.ps1](../../../ops/pipeline/engine/publish/sidecar.ps1:265)). This explains
why a valid output can be absent from Completed history and why backfill is a
separate recovery path.

## Findings

### P1 — CSW-2026-07-09-COMPLETED-001: confirmed repair can commit without required durable journal evidence

**Evidence.** The published contract says confirmed applies are journaled and
requires rollback on command-journal failure
([REPAIR_RECONCILE_MUTATION_CONTRACT.md](../../architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md:21),
[contract_payload.py](../../../src/mediapipeline/desktop/api/contract_payload.py:400)).
The generic HTTP response path performs repair after the handler returns, then
calls the journal in non-strict mode ([handler.py](../../../src/mediapipeline/desktop/api/handler.py:148)).
Non-strict `CommandJournal.record()` deliberately does not raise for an
unconfigured JSON journal or persistence failure
([command_journal.py](../../../src/mediapipeline/desktop/api/command_journal.py:136),
[command_journal.py](../../../src/mediapipeline/desktop/api/command_journal.py:175)).
The apply code has already atomically written state and returns `ok=True` before
that generic journaling call occurs ([apply.py](../../../src/mediapipeline/core/repair_reconcile/apply.py:452)).

**Impact.** An operator can receive success for a completed manifest/sidecar
repair with no durable command-history evidence, contrary to the stated
release-critical journal/rollback guarantee. This does not permit media,
publish, drain, source, or output mutation, but it weakens evidence and recovery
for a state-changing route.

**Required coordinator handoff.** Make the four apply handlers provide a strict
journal recorder to the repair facade (as lifecycle and network-rerun applies
already do), and arrange rollback/failed result if that recorder fails. Add a
Local API test that forces both JSON-journal and SQLite-mirror persistence
failure after a candidate write and proves backup restoration, no success reply,
and diagnostic evidence.

### P2 — CSW-2026-07-09-COMPLETED-002: malformed completed-manifest rows are silently omitted from operator evidence

**Evidence.** The JSONL reader logs and skips malformed lines
([manifest.py](../../../src/mediapipeline/core/completed/manifest.py:120)); it does
not return skipped-line count, byte/line identifier, or preview warning. The
existing test intentionally asserts that bad rows are skipped
([test_service_completed_manifest.py](../../../tests/python/desktop/test_service_completed_manifest.py:40)).
The UI’s empty/partial history therefore receives only the remaining rows and
the normal counts ([policy.py](../../../src/mediapipeline/core/completed/policy.py:1427)).

**Impact.** Partial JSONL corruption can look like a legitimately shorter
Completed history. The page correctly treats missing output, sidecars, stale
manifest age, and deferred live proof as evidence states, but it cannot tell the
operator that rows were lost during parsing. This matters when using Completed
as proof before repair/reconcile or when reconciling an apparent missing row.

**Required coordinator handoff.** Preserve tolerant reads, but return bounded
parse-health evidence (skipped count and recent line identifiers/error class)
in the completed DTO, surface it in Integrity/Diagnostics, and block
manifest-reconcile dry-run when parse loss is present. Add fixtures covering a
valid row before/after a malformed line and verify that the warning remains
visible through `/api/completed`, publish reconciliation, and dry-run.

### P3 — CSW-2026-07-09-COMPLETED-003: sidecar dry-run guidance contradicts the exposed apply route

**Evidence.** A detected sidecar metadata candidate says “no sidecar write route
exists” ([dry_run.py](../../../src/mediapipeline/core/repair_reconcile/dry_run.py:1007)),
but the same module lists the candidate’s write path and the API exposes the
confirmed sidecar apply route ([commands.py](../../../src/mediapipeline/core/api/commands.py:51)).

**Impact.** The contradictory safe-next-action text may cause an operator to
abandon an available backend-controlled repair. Safety is unchanged because the
route remains fingerprint/confirmation gated.

**Required coordinator handoff.** Change only the dry-run guidance to direct
the operator to review the diff and use the matching confirmed apply route when
safe.

## Verified no-finding coverage

- **Filters and selected rows are not backend scope.** Current/History filters,
  selection, and 250-row rendering are local display evidence; explicit scope
  text says backend actions do not receive them. The repair payload is a single
  selected backend `row_key`, not a filtered list.
- **Dry-run/apply separation and strict confirmation.** Dry-runs have
  `effect=none`; apply re-runs the backend dry-run, requires equality of the
  fingerprint, and uses `request.get("confirm_apply") is not True` to reject
  missing/truthy strings ([apply.py](../../../src/mediapipeline/core/repair_reconcile/apply.py:360)).
- **Backend path authority and target allowlists.** Completed repair payload
  validation rejects client path/patch fields; open derives only an allowlisted
  target from a current manifest row. Tests cover unknown apply fields
  ([test_repair_reconcile_apply.py](../../../tests/python/desktop/test_repair_reconcile_apply.py:1038)).
- **No source/output/publish/drain mutation from repair.** Candidate generation
  blocks absent output/sidecar evidence; apply only atomic-writes the selected
  manifest or sidecar metadata and records before/after no-touch evidence for
  protected media/payload paths. No completed repair code calls process launch,
  publish, drain, move, delete, or media writer.
- **Missing/stale/inconsistent evidence.** Missing output, missing sidecar,
  output/sidecar mismatch, sidecar age, manifest missing output path, manifest
  freshness, deferred proof, pending/drain proof, and runtime outcome fields
  are carried into row/summary state
  ([policy.py](../../../src/mediapipeline/core/completed/policy.py:1461)).
- **Diagnostics and acceptance remain evidence-only.** The proof/acceptance
  panels and reconciliation refresh contain no mutation routes; browser smoke
  asserts forbidden publish/drain posts are absent
  ([test_webview_browser_completed_pending_proof_smoke.py](../../../tests/webview/test_webview_browser_completed_pending_proof_smoke.py:1106)).

## Test and contract assessment

The contract documentation is unusually specific and matches the happy-path
implementation for route names, strict request shape, fingerprint binding,
backup/atomic write, no-touch evidence, and dry-run suppression. The documented
test set covers malformed-row tolerance, source/output immutability for apply,
unknown client fields, browser request-body bounds, missing-output proof, and
no forbidden UI posts. The gaps are adverse-path coverage: no inspected test
forces command-journal persistence failure after a completed apply, and no
contract test requires malformed JSONL parse health to be returned to the
operator.

No tests were executed: this was a read-only code review, and the requested
deliverable is an assessment rather than a behavior change. The cited tests
were inspected as executable evidence.

## Coordinator handoff

1. Treat **COMPLETED-001** as the first repair/reconcile follow-up. Reconcile
   the generic handler’s best-effort journal policy with the contract’s strict
   mutation-journal/rollback promise.
2. Add parse-health observability before relying on Completed history as a
   complete repair/reconciliation inventory (**COMPLETED-002**).
3. Correct the sidecar candidate guidance (**COMPLETED-003**) with a focused
   docs/string test.
4. After implementation, run targeted repair apply/dry-run, Local API command
   journal, WebView mutation-boundary, and Completed/Pending browser-smoke
   tests. Real-media validation is not required for the proposed metadata and
   evidence changes unless the implementation touches PowerShell publish,
   media-policy, or drain behavior.

## Limits

- This review did not invoke mutation, diagnostic-open, or shell-open routes;
  it did not exercise a live Local API, media sample, UNC share, or a real
  command-journal failure.
- The workspace contained extensive unrelated, pre-existing modifications,
  including active Completed table/policy and generated-summary changes. They
  were not modified or attributed by this review.
- The report is the only file created/updated by this task; no change packet
  was created because the request explicitly prohibited change-packet updates.

