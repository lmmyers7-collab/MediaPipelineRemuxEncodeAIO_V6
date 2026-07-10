# Queue Tab Full Code Sweep — 2026-07-09

## Executive assessment

**Result: not release-ready.** The Queue tab is architecturally well aligned in the inspected implementation: it treats display filters, table paging, selection, row detail, route preview, and scope panels as local/read-only presentation; backend routes own queue-state writes, process launch, path opening, and media policy. The PowerShell queue planner consumes the same priority, strategy, and override artifacts that the Python API writes.

However, the current working tree contains a **P0 import blocker** in the CSV-rerun policy module. This prevents a trustworthy end-to-end validation of rerun safety and can prevent the Local API from loading any code path that imports the rerun facade/preview/results modules. A second finding shows that a malformed `file_overrides.json` fails open as an empty manifest, which can silently remove routing/audio/subtitle intent from both Queue display and PowerShell processing. Two P2 contract/evidence issues follow.

Scope: static/source/test/inventory review only. No queue scans, launches, reruns, route previews, opens, or state mutations were invoked.

## Workflow traces

### 1. Queue snapshot display and refresh

`GET /api/queue` is registered in `src/mediapipeline/desktop/api/routes_read.py` and is fulfilled by `QueueFacadeMixin.get_queue_preview`. It reads the existing snapshot, applies priority-manifest state, correlates runtime events, exposes exclusions and freshness metadata, and does not spawn a dry run. The WebView consumes it through the common refresh path and `renderQueue` in `apps/desktop/webview/static/assets/queueView.js`.

`requestQueueScan` is the explicit refresh path. It posts only the backend-owned plan command `POST /api/queue/scan` with `inventory_then_curate`; the UI displays the prior snapshot while a scan is in progress and polls backend state. The message explicitly says no media mutation was submitted. Stale, absent, invalid, empty, blocked, and backend-error payloads receive distinct readiness/workflow text and diagnostics handoffs.

### 2. Filters, selection, render cap, and scope boundary

The Queue table keeps the complete loaded payload in `lastQueueRows`; text/status/investigation filters run only in `queueFilteredRowsForCurrentDisplay`. `QUEUE_RENDER_LIMIT` is 250 and page controls operate on the filtered display slice. `page-queue.html` and the pagination status repeatedly say that display filters, checked rows, and render caps do not define backend launch scope. The dedicated Backend Launch Scope Boundary panel is recalculated from the unfiltered backend payload.

Selected-row priority writes are limited to selected loaded rows. “All Loaded Movies/TV” deliberately ignores filters and the cap, with a confirmation spelling out that behavior. Manual ordering stages local rearrangement only until it posts manifest positions; it is phase-scoped and pauses during a fresh scan.

### 3. Priority and strategy

The frontend posts priority to `POST /api/queue/priority` and strategy to `POST /api/queue/strategy`; it does not write JSON itself. `commands_queue_priority.py` validates level, finite manual position, and source-root containment before atomically updating `priority_manifest.json`. `commands_queue_strategy.py` validates names against `VALID_STRATEGIES` before atomically writing `queue_strategy.json`.

PowerShell consumes these artifacts in `priority_manifest.ps1`, `strategy_sorting.ps1`, and `phase_plan.ps1`. The priority manifest is explicitly fail-closed for queue planning; hold rows are kept out of runnable entries. Strategy resolution is state file → config default → `Standard`, and planning applies it only after phase construction.

### 4. Per-file overrides, tracks, and series controls

The drawer modules use backend reads for exact/effective override data and track metadata, then post only Queue command routes for save/clear. Route-impact preview is backend-owned and is required before saving route/video-impacting fields. File, folder, series, and remux-pilot command handlers validate allowable keys and source roots; series apply/clear and pilot promotion require strict `confirm_apply is True`, with preview fingerprint checks where applicable.

At process time, `ops/pipeline/engine/queue/file_overrides.ps1` resolves exact then deepest-folder overrides and merges them into active processing overrides. It rejects unsafe route/video combinations such as forced remux plus encode-required video or subtitle burn-in.

### 5. Rerun and launch handoffs

The Queue CSV Rerun UI stages target, execution, lifecycle, and scope intent. Preview, Network preview, and Network start dry-run remain backend calls. Local `rerun/start` goes through `RerunLaunchFacadeMixin`, which is designed to use active-work and launch-lock guards, backend CSV/scoped-CSV planning, lifecycle validation, scratch staging, and the PowerShell `Invoke-RerunCsv.ps1` entry point. Network confirmed start is documented as a coordinator-state write, not worker/media launch.

The intended PowerShell rerun path uses an isolated rerun workspace, nested per-chunk `LocalBase`, staged source roots, and output parking; it also records manifests and stop-after-current evidence. The active Python rerun-policy corruption below means this intended chain cannot presently be trusted or exercised.

### 6. Open-file/open-location actions

Queue open actions submit `row_key`, `row_scope`, and allowlisted `target`, never a raw browser path. `QueueFacadeMixin.open_queue_location` reloads the backend preview, finds the row by key and scope, derives the allowed path server-side, verifies it exists, then calls the backend opener. Rerun opens follow the equivalent backend-known `row_key`/`csv_key` target policy.

## Findings

### P0 — CSW-2026-07-09-QUEUE-001: Active rerun-policy module is entirely NUL bytes

- Evidence: `src/mediapipeline/core/processes/rerun_policy.py` is 25,032 bytes and every byte is `0x00`; its generated summary `docs/generated/summaries/src/mediapipeline/core/processes/rerun_policy.py.md` is likewise NUL-filled. `git diff --numstat` reports the working-copy file as binary/no-text. The committed `HEAD` version is normal Python source.
- Impact: Python raises a null-byte source/import error. `rerun_facade.py`, `rerun_preview.py`, `rerun_results.py`, the local API contracts, and Queue CSV Rerun all depend on symbols from this module. The active tree therefore cannot provide the claimed rerun lifecycle, source-root, final-output-root, confirmation, duplicate-command, or scratch-isolation safeguards. This is a release blocker, not a presentation defect.
- Required handoff: restore the intended Python content from the owner’s active change/recovery source; verify no other zero-filled files; regenerate summaries; then run the rerun policy, preview, local-API, and relevant WebView tests before any Queue/rerun acceptance. Do not use the UI to launch reruns until that gate passes.

### P1 — CSW-2026-07-09-QUEUE-002: Malformed `file_overrides.json` silently disables overrides

- Evidence: `src/mediapipeline/core/queue/file_overrides.py` (`read_file_overrides`, lines 199–213) returns `_empty_manifest()` for I/O, JSON, encoding, version, or entry-shape failures. `QueueFacadeMixin.get_queue_preview` reads that value directly (lines 572–584) and continues. `ops/pipeline/engine/queue/file_overrides.ps1` documents and implements the same “empty manifest on any error” behavior (lines 174–225).
- Impact: a corrupt/unsupported override manifest looks like “no overrides” in both Queue display and the processing consumer. Audio, subtitle, and routing exceptions can disappear without an operator-visible blocker; a subsequent save can overwrite the broken artifact with a new partial manifest. This differs from the priority-manifest consumer, which fails closed to preserve holds and priority intent.
- Required handoff: introduce a typed read result/error or fail-closed processing gate for an existing malformed override artifact; surface the error in `/api/queue`, drawer reads, and processing logs; add backend + PowerShell parity tests for invalid JSON, wrong version, wrong entry shape, and recovery/write behavior.

### P2 — CSW-2026-07-09-QUEUE-003: Manual-order `position` is accepted and used but omitted from route contracts and inventories

- Evidence: `QueuePriorityCommandPayload` exposes `position` (`src/mediapipeline/contracts/api_commands.py`, lines 85–91); `commands_queue_priority.py` validates and persists single/bulk positions (lines 82–91 and 148–153); `queueView.js` posts them for Save Loaded Backend Order (line 2561). But `src/mediapipeline/contracts/api_routes_command.py` line 12, `docs/inventories/API_ROUTE_INVENTORY.md` line 105, and `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` line 93 omit `position` from the declared request keys.
- Impact: generated route consumers and reviewers receive an incomplete public command contract for a real, backend-mutating Queue feature. This weakens command-boundary auditing and can break schema-driven tooling.
- Required handoff: add `position` (and clarify that it is allowed in each `items[]` member) to the canonical route contract and regenerate/update inventories; add an assertion that the route contract, payload model, and manual-order frontend use agree.

### P2 — CSW-2026-07-09-QUEUE-004: Generated navigation evidence for rerun files/tests is corrupted

- Evidence: the generated summaries for `rerun_policy.py`, `rerun_preview.py`, `test_facade_process_rerun_policy.py`, and `test_rerun_csv_preview.py` are NUL-filled. This violates the repository’s required summary-first navigation workflow and is presently indistinguishable from absent evidence without byte-level inspection.
- Impact: reviewers cannot use the generated context to identify rerun behavior or verify summaries against changed source. It also masks the P0 source corruption until the full source is opened.
- Required handoff: restore source first, then regenerate all affected summaries and run the summary integrity/check tooling. Treat NUL-only generated files as a generator/working-tree integrity failure rather than as empty summaries.

### P3

No P3 findings were recorded. The remaining observations are covered by the no-finding review below.

## No-finding coverage

- **Frontend ownership:** inspected Queue scripts only stage intent, render backend payloads, call API routes, and make local display/order changes. They do not perform filesystem writes, media decisions, process spawning, or direct `fetch` outside the shared client boundary.
- **Scope clarity:** filtering, selection, paging, and the 250-row cap are repeatedly labeled display-only; the scope boundary and launch-checklist paths use the complete backend payload rather than the visible slice.
- **Backend command validation:** priority, strategy, file overrides, series/folder/pilot actions, Queue open, rerun control, and rerun promotion have distinct backend handlers. Source-root checks, key allowlists, confirmation fields, row-key allowlists, and command journaling are present in the inspected contracts/handlers.
- **Priority and strategy consumer parity:** the JSON path names, versions, strategy vocabulary, manual positions, phase treatment, and hold exclusion match the inspected PowerShell planner behavior. Priority reads/planning fail closed on malformed state.
- **Open actions:** Queue and rerun opens use backend-derived identifiers and allowlisted targets rather than browser-supplied paths.
- **Empty/stale/partial/backend-unavailable display:** Queue readiness/review/workflow text distinguishes unavailable payloads, stale snapshots, empty candidates, no runnable rows, invalid rows, scan-in-progress prior snapshots, exclusions, and runtime-history warnings.

## Test and contract assessment

Existing coverage is substantive:

- `test_application_facade_local_api_queue.py` exercises Queue route auth/contract/journal behavior, source-root rejection, priority corruption handling, manual positions, override writes/clears, and effective override reads.
- `test_application_facade_queue.py`, `test_facade_queue_policy.py`, and queue service tests cover snapshots, stale/blocked/excluded rows, dry-run/scan state, and backend open allowlists.
- `test_file_override_tracks.py` covers track metadata, selector validation, route preview, and series/pilot behavior. `Invoke-FileOverrideSubtitleBurnChecks.ps1` covers PowerShell enforcement.
- `test_rerun_csv_preview.py`, `test_facade_process_rerun_policy.py`, `test_process_rerun_results.py`, `Invoke-RerunPlanOnlyChecks.ps1`, and `Invoke-RerunSourceIdentityChecks.ps1` are the intended rerun safety suite; `Invoke-PipelineQueueEngineChecks.ps1` covers priority corruption, holds, manual ordering, caps, and queue-engine behavior.
- WebView coverage includes the file-overrides browser smoke, queue state-chip smoke, launch-queue readiness smoke, and frontend mutation-boundary static audit.

The P0 means these tests were **not run**: the current Python import graph is not viable. The P1/P2 gaps also show missing negative tests for malformed override artifacts and contract/payload/inventory agreement on `position`.

## Coordinator handoff

1. **Stop acceptance/release work for Queue CSV rerun** until CSW-2026-07-09-QUEUE-001 is resolved and verified.
2. Assign the rerun owner to restore `rerun_policy.py`, inspect all NUL-only source/summary files, and refresh generated context; retain the current working tree for forensic comparison rather than silently overwriting unrelated work.
3. Assign Queue/override policy ownership to resolve CSW-2026-07-09-QUEUE-002 with explicit malformed-artifact behavior agreed by Python and PowerShell before implementation.
4. Assign contract/inventory ownership to resolve CSW-2026-07-09-QUEUE-003 in the canonical contract and generated docs.
5. After fixes, run targeted Python Queue/rerun tests, PowerShell queue/rerun unit checks, Queue file-overrides browser smoke, and a representative real-media rerun validation before promotion. The P0/P1 changes affect high-risk rerun/media-policy paths, so a real-media validation is required by the validation ladder.

## Limits

- This was a static, read-only audit; no live Local API, browser, PowerShell pipeline, queue scan, filesystem open, route preview, launch, or rerun was invoked.
- The workspace was already extensively dirty across Queue/WebView, backend, PowerShell, tests, inventories, and generated files. Those changes were not modified or attributed to this review.
- The NUL-filled active source and summaries prevented normal source-summary inspection and any meaningful execution validation of the rerun chain. Where useful, the committed `HEAD` version was read only to establish the intended policy surface; it is not evidence that the active working tree is safe.
