# Metrics Tab Full Code Sweep — 2026-07-09

## Executive assessment

**Result: not ready to use as decision-quality operational evidence.** `GET /api/metrics` is correctly registered as a read-only backend route and derives its primary history from the completed-jobs manifest. Route and storage percentages have explicit arithmetic and safe zero-denominator behavior.

However, the page merges a generated, operator-triggered sidecar-cache mirror into those completed records without distinguishing it from the manifest, can silently replace a complete cache with a partial one while reporting the aggregate backfill as complete, and does not make a failed, unavailable, or malformed metrics refresh visibly unavailable. Those conditions can undercount, overcount, or retain stale values while implying a current, authoritative view. The tab also contains two documented state-writing controls, so only the `GET /api/metrics` read is read-only—not the whole Metrics tab.

Scope was static/source/contract/test inspection only. No Local API mutation route, backfill, source update, media action, or state-changing operator workflow was invoked.

## Scope and evidence map

| Surface | Evidence reviewed | Role in trace |
| --- | --- | --- |
| Metrics shell | `apps/desktop/webview/static/partials/page-metrics.html`, `assets/metricsView.js`, and the Metrics references in `assets/app.js` | Labels, rendering, commands, initial/periodic refresh, empty-state behavior |
| Read route and DTO | `src/mediapipeline/desktop/api/routes_read.py`, `read_payloads_inventory.py`, `contract_read.py`, and the API route inventories | Route registration, route effect, schema claim, unavailable response |
| Aggregation | `src/mediapipeline/core/metrics/facade.py`, `policy.py`, and `sources.py` | Input authority, deduplication, counters, storage, throughput, coverage, workers, cache/backfill behavior |
| Upstream state | completed manifest/service, Pending Publish facade, Network worker facade, final-library service/facade, and telemetry/system-metrics modules | Authority boundary and Home/Telemetry relationship |
| Tests/docs | `tests/python/desktop/test_metrics_feature.py`, API inventories, generated summaries/index/graph, current-state, module map, and validation ladder | Existing assurances and coverage gaps |

Generated summaries were read before their corresponding source. They identify Metrics as a separate core domain with dependencies on Completed and Paths; their current content is mostly metadata-only, so exact behavior was verified in source.

## Workflow traces

### 1. Initial load and refresh

Startup invokes `refreshAll({ automatic: true })`, then repeats on the shared 15-second refresh interval (`apps/desktop/webview/static/assets/app.js:2012-2013`). The concurrent refresh set includes optional `GET /api/metrics` (`app.js:902-930`); a fulfilled value is rendered only when `values.metrics` exists (`app.js:933-941`, `997-1000`). `metricsView.renderMetrics` renders all five subtabs from the received object (`metricsView.js:735-744`). There is no Metrics-specific refresh button; source/backfill commands request a full refresh after their command returns (`metricsView.js:476-512`).

The GET handler calls `facade.get_metrics(resolved)` (`src/mediapipeline/desktop/api/read_payloads_inventory.py:62-66`). The facade loads completed-manifest records, cached backfill records, pending-publish preview, worker runtime state, and final-library state, then builds the DTO (`src/mediapipeline/core/metrics/facade.py:36-52`).

### 2. Counters, storage, rates, and aggregation

- **Jobs/routes:** each merged completed record is assigned `remux`, `encode`, or `other`; route counts and percentages use all merged rows as the denominator (`src/mediapipeline/core/metrics/policy.py:160-198`, `212-238`).
- **Storage:** a row is measured only when both source and output sizes are positive. Savings, growth, and their percentage use measured rows/source bytes; the DTO separately supplies measured and excluded counts (`policy.py:241-323`).
- **Production/throughput:** output bytes are summed from all rows; daily buckets use the record completion date. The displayed rate is total jobs/output divided by the number of recent distinct date buckets, with at most seven buckets (`policy.py:326-371`; `metricsView.js:314-345`).
- **Workers:** worker encoded GB is summed, while average GB/h is a simple mean of positive per-worker rates (`policy.py:478-514`). Session complete/failed are counts from the network-worker read model, not a calculated pipeline job success/failure rate.
- **Null/zero:** `_percent` returns `None` on a non-positive denominator (`policy.py:58-61`), which renders as `-` (`metricsView.js:82-86`). Integer/float formatters otherwise coerce invalid or absent values to zero (`metricsView.js:73-80`, `98-109`).

### 3. Authority and state inputs

The primary input is the completed-manifest service with `limit=None` and summary proof (`metrics/facade.py:118-140`). Pending Publish and Network state are read through their existing read facades (`metrics/facade.py:142-160`), and final-library status is read with a bounded 500-record input (`metrics/facade.py:162-196`). These are backend-owned reads.

The facade then deduplicates and merges cached Metrics sidecar records alongside manifest records (`metrics/facade.py:86-116`). The cache is loaded from `State/Metrics/metrics_sidecar_backfill.jsonl`, constructed from configured sidecars by a separate backfill command (`metrics/sources.py:680-717`). That cache is a generated mirror, not the completed-manifest authority.

### 4. Partial, stale, empty, unavailable, and malformed states

The aggregator creates warnings for unavailable completed/pending/worker/final-library inputs, supplies an empty-row warning, and exposes measurement coverage/attention (`metrics/facade.py:118-196`; `metrics/policy.py:564-736`). Empty route percentages display a dash rather than divide by zero.

But the GET route returns only `{ "error": "metrics unavailable" }` when paths cannot resolve (`read_payloads_inventory.py:62-66`; `read_payloads_policy.py:10-11`). The view has no schema/error/availability gate and renders fallback zeros from any object. A rejected optional refresh does not call the Metrics renderer, leaving prior DOM values in place. These conditions are findings below.

### 5. Home and Telemetry relationship

Home is driven by `/api/snapshot`, Queue, Completed, and Pending Publish rendering (`app.js:961-1017`); it does not consume the Metrics DTO. Telemetry is a separate optional GET and renderer (`app.js:906`, `977-988`), with CPU/memory sampled into `TelemetrySnapshot` by `system_metrics.py:184-209`. Metrics does not claim or consume those live CPU/GPU/memory samples.

The Metrics Workers subtab independently reads the same class of network runtime state that the Network surface reads. Because all GETs are concurrent and no shared snapshot/version is exposed, a fast-changing worker count can legitimately differ between Metrics, Home progress, and Network in one refresh. The page does not claim a common sample time, so this is a scope/freshness limit rather than a finding by itself.

## Findings

### P1 — CSW-2026-07-09-METRICS-001: Generated sidecar-cache records are aggregated as authoritative completed history

- **Evidence:** `get_metrics` merges completed-manifest records and `load_metrics_backfill_records` results before every counter is calculated (`src/mediapipeline/core/metrics/facade.py:36-52`, `86-100`). Backfill records are loaded from the Metrics cache (`src/mediapipeline/core/metrics/sources.py:680-717`), which is written from configured `*.pipeline.json` sidecars (`sources.py:491-554`, `619-621`). The payload labels the combined count as the completed manifest’s `record_count` and calls its authority `completed_jobs.jsonl` (`src/mediapipeline/core/metrics/policy.py:526-560`), while the UI repeats it as “Completed records” (`apps/desktop/webview/static/assets/metricsView.js:360-375`).
- **Impact:** stale, malformed-at-ingest, source-side, or non-manifest sidecar rows can alter job counts, route mix, storage, throughput, production totals, and route reasons while the UI implies that those numbers came solely from the completed manifest. The cache may be useful supplemental evidence, but it is a generated mirror and has no final-output proof in this path.
- **Required handoff:** make authority explicit in the DTO and UI; either keep manifest metrics separate from backfill-derived discovery metrics, or require a documented validation/provenance rule before a cache record can enter operational totals. Report manifest, cache, merged, deduplicated, stale, and excluded counts independently. Add mixed-manifest/cache collision, stale-cache, invalid-cache, and authority-label tests.

### P1 — CSW-2026-07-09-METRICS-002: A partial backfill replaces a source’s full cache but can report global status `complete`

- **Evidence:** hitting `max_sidecars` returns a root result with `status="partial"` (`src/mediapipeline/core/metrics/sources.py:510-515`). The subsequent write drops every prior cache entry for that source and replaces it with only scanned entries (`sources.py:619-621`). The aggregate status is `warning` only for errors or oversized files, not partial roots (`sources.py:642-659`). Coverage and source rendering display that global status as the last-backfill status (`metricsView.js:269-282`, `437-452`).
- **Impact:** a previous complete source cache can be silently reduced to a prefix of the scan, then operational totals undercount history while the overview says the backfill is complete. No output calls or media mutation are required for this misleading state.
- **Required handoff:** preserve prior cache entries on partial scans, or mark partial/replaced cache data as incomplete and exclude it from authoritative totals. Propagate root-level partial status, scan limit, cache replacement count, and last successful full-scan timestamp to the DTO/UI. Add a regression test that starts with a complete cache, runs a limited backfill, and verifies both retained records and an unmistakable partial status.

### P1 — CSW-2026-07-09-METRICS-003: Failed, unavailable, and malformed metrics reads can look current, stale, or zero-valued rather than unavailable

- **Evidence:** Metrics is optional in the shared refresh (`apps/desktop/webview/static/assets/app.js:902-930`); rejected requests are omitted from `values` (`app.js:933-941`), and the existing Metrics DOM is re-rendered only on a successful value (`app.js:997-1000`). The unavailable route response is just an error object (`src/mediapipeline/desktop/api/read_payloads_inventory.py:62-66`; `read_payloads_policy.py:10-11`). `renderMetrics` accepts any object (`metricsView.js:735-743`), while formatters convert absent/non-finite numbers to zero (`metricsView.js:73-80`, `98-109`) and overview labels use zero fallbacks (`metricsView.js:514-527`).
- **Impact:** a transport failure retains the last metrics indefinitely, while a 200 error object or malformed shape replaces operational values with plausible-looking zeros. Neither case shows a Metrics-specific stale/unavailable banner, schema mismatch, component timestamp, or safe next action. An operator can therefore infer zero backlog, zero failures, or current output incorrectly.
- **Required handoff:** require `desktop_metrics.v1`, `read_only=true`, and a valid generated timestamp before rendering; render a distinct unavailable/invalid/stale state on failed or malformed reads; retain prior payload only with its timestamp and a stale badge. Add browser/static coverage for rejected GET, `{error: ...}`, wrong schema, missing sections, null/NaN-like values, and recovery after a valid refresh.

### P2 — CSW-2026-07-09-METRICS-004: “Jobs/day” and “GB/day” use observed date buckets, not a stated calendar window

- **Evidence:** the production policy uses the last seven *dated buckets*, divides by their count, and labels the result `recent_*_per_day` (`src/mediapipeline/core/metrics/policy.py:352-371`). Dates use the host-local `astimezone()` date without declaring the zone (`policy.py:77-88`). The UI calls the output “Jobs/day,” “GB/day,” and “Recent window: N day(s)” (`apps/desktop/webview/static/assets/metricsView.js:314-345`) without displaying elapsed calendar span, empty dates, or timezone.
- **Impact:** jobs completed on two non-consecutive days over months display as a two-day rate; the same UTC completion can move between buckets across hosts/time-zone changes. This is a denominator/time-window ambiguity, not a mathematical divide-by-zero fault.
- **Required handoff:** choose and name one basis: rolling seven calendar days (including zero days), last seven active days, or a stated elapsed interval. Supply `window_start`, `window_end`, timezone/basis, bucket count, and zero-day treatment in the DTO; update labels and test sparse, cross-midnight, and unknown-date fixtures.

### P2 — CSW-2026-07-09-METRICS-005: Worker “GB/h” is an unweighted mean with an undisclosed denominator

- **Evidence:** only strictly positive per-worker speeds enter `speed_values`, then `average_speed_gbh` is their arithmetic mean (`src/mediapipeline/core/metrics/policy.py:478-514`). The UI presents this as a top-level “GB/h” metric and chart value without its worker/time denominator (`apps/desktop/webview/static/partials/page-metrics.html:293-321`; `apps/desktop/webview/static/assets/metricsView.js:675-708`).
- **Impact:** the displayed value is neither aggregate cluster throughput nor an all-worker average; idle/zero-rate workers are excluded and a short-lived fast worker has equal weight to a long-lived slow worker. Operators can overestimate sustained cluster capacity or compare it incorrectly with total GB encoded.
- **Required handoff:** label it “mean reported active-worker GB/h” and display qualifying-worker count, or calculate an explicitly time/bytes-weighted aggregate with source timestamps. Add fixtures for zero, idle, stale, and heterogeneous worker-rate rows.

### P2 — CSW-2026-07-09-METRICS-006: The Metrics tab is not wholly read-only, despite its read-only aggregate route

- **Evidence:** the page exposes Add Source and Backfill Enabled controls (`apps/desktop/webview/static/partials/page-metrics.html:100-130`); their handlers POST `/api/metrics/sources` and `/api/metrics/backfill` (`apps/desktop/webview/static/assets/metricsView.js:456-512`). The route inventory correctly classifies `GET /api/metrics` as `none` but these POSTs as Metrics-state writes (`docs/inventories/API_ROUTE_INVENTORY.md:52`, `215-218`).
- **Impact:** the core aggregate read is read-only, and the commands do not touch media, but “Metrics is read-only” is not true for the page as an operator surface. This can weaken command-boundary reviews and surprises operators who expect viewing Metrics to have no persistence/scanning action available.
- **Required handoff:** retain the backend-owned command boundary, but document/label the tab as “read-only metrics with separate Metrics-state management” or move source/backfill administration to an explicitly mutable settings/maintenance surface. Keep command-journal and mutation-boundary coverage for both POST routes.

### P3

No P3 findings recorded.

## No-finding coverage

- `GET /api/metrics` is registered as a GET read handler (`src/mediapipeline/desktop/api/routes_read.py:29`) with `effect: none` and schema `desktop_metrics.v1` in the Local API contract (`src/mediapipeline/desktop/api/contract_read.py:235-240`) and API route inventory (`docs/inventories/API_ROUTE_INVENTORY.md:52`). The handler only requests the facade read model.
- Core aggregation does not write media, manifests, queue state, or final-library state. Pending Publish, worker, and final-library failures are caught and carried as warnings into the payload (`src/mediapipeline/core/metrics/facade.py:142-196`).
- Route shares use a named total and zero denominator safely becomes `null`/`-` (`src/mediapipeline/core/metrics/policy.py:58-61`, `212-238`; `metricsView.js:82-86`). Storage-savings percentages use measured source bytes and render measured/excluded rows (`policy.py:273-323`; `metricsView.js:269-289`, `590-613`).
- There is no displayed end-to-end job success/failure percentage or duration metric falsely claiming a denominator. The displayed worker session complete/failed values are raw runtime counts; they should not be interpreted as pipeline success rate.
- Metrics uses a dedicated WebView namespace and local rendering only; no direct filesystem or media-processing code was found in `page-metrics.html` or `metricsView.js`. Its POST actions go through the shared API client and backend handlers.

## Test and contract assessment

Existing coverage establishes basic aggregation, route registration/contract text, GET route output, streaming cache counts, oversized-sidecar warnings, recursive backfill, source-state writes, and static WebView wiring (`tests/python/desktop/test_metrics_feature.py:64-405`). The test also asserts the two POST controls exist (`test_metrics_feature.py:406-463`), consistent with the inventory.

This review ran, with `PYTHONDONTWRITEBYTECODE=1`, only read-safe targeted tests:

```powershell
apps\desktop\runtime\Python\python.exe -m unittest -q `
  tests.python.desktop.test_metrics_feature.MetricsFeatureTests.test_metrics_payload_aggregates_route_storage_production_and_workers `
  tests.python.desktop.test_metrics_feature.MetricsFeatureTests.test_metrics_route_contracts_define_read_and_backfill_boundaries `
  tests.python.desktop.test_metrics_feature.MetricsFeatureTests.test_local_api_metrics_route_returns_backend_aggregate
```

Result: **3 tests passed**. No Metrics POST route was invoked.

Coverage gaps materially connected to the findings: no test for cache authority separation, deduplication provenance, partial `max_sidecars` replacement, stale/failed/malformed Metrics rendering, schema validation, sparse-calendar throughput, timezone bucketing, or weighted worker throughput. The validation ladder calls for targeted Local API tests plus relevant WebView smokes when these surfaces change; a future fix touching only UI/DTO behavior does not require real-media validation unless it changes media/publish policy.

## Coordinator handoff

1. Treat CSW-2026-07-09-METRICS-001 through -003 as the first remediation set: authority separation, partial-cache integrity, then explicit unavailable/stale rendering.
2. Assign Metrics/backend ownership to decide whether sidecar backfill is discovery-only or eligible operational evidence; retain manifest-backed completion as the clearly named primary source.
3. Assign WebView/API contract ownership to add a typed degraded Metrics DTO/render state and component freshness/provenance fields.
4. Resolve throughput/window and worker-rate definitions before using them for capacity or operations targets; add fixtures that make the intended denominators executable.
5. Keep Metrics source/backfill commands backend-owned. If they remain on this tab, ensure operator documentation and route inventories state that they write only `State\\Metrics` and are not part of the read-only aggregate request.

## Limits

- Static/read-only review only; no live browser session, source scan, backfill, POST, pipeline launch, pending drain, final-library action, media probe, or filesystem mutation was invoked.
- The worktree was already extensively dirty, including `apps/desktop/webview/static/assets/app.js`, inventories, generated summaries, backend, PowerShell, and tests. Those changes were neither modified nor attributed to this report; the cited behavior is from the current checkout.
- The review did not compare live state files, run an end-to-end WebView smoke, or inspect a real completed manifest/cache. Findings are source-backed behavior risks that need targeted negative tests and fixture proof before remediation acceptance.
