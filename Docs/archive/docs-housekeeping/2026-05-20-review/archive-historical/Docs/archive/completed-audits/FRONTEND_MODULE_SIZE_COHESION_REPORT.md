# Frontend Module Size / Cohesion Report

Date: 2026-05-14

Inventories all JavaScript modules under `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/`. Reports file size, primary responsibility, and flags files approaching god-file territory. Does not propose immediate refactors.

Architecture: all modules use the IIFE (Immediately Invoked Function Expression) pattern and export globals via `window.*`. There is no bundler; files are served directly.

---

## Full Module Inventory

| File | Size (bytes) | Size (KB) | Primary Responsibility |
|---|---|---|---|
| `settingsView.js` | 220,217 | 215K | Settings builder (all pages), preview-patch, save-patch, reload, staged media-policy delta, Active Media Policy Boundary, Settings-to-Launch handoff |
| `completedView.js` | 209,870 | 205K | Completed table, row detail, size evidence, route agreement, real-media proof ladder, pending-publish overlap proof, publish reconciliation, diagnostics handoff |
| `pendingPublishView.js` | 171,620 | 168K | Pending publish table, row detail, drain guard, Publish Button Guard, filter-scope chain, recovery plan, open targets |
| `launchView.js` | 110,646 | 108K | Pipeline/drain/audit/rerun launch, control flags (pause/stop/rescan), launch readiness, launch history |
| `queueView.js` | 120,703 | 118K | Queue table, row detail, investigation signals, filter-scope launch-decision evidence, file-open operations |
| `commandHistory.js` | 86,900 | 85K | Command journal rendering, owner/issue cross-page linking, resolution posture, evidence checklist across all pages |
| `diagnosticsView.js` | 82,862 | 81K | Diagnostics tail, state summary, open targets (20 allowlisted), owning-page handoff, Go To Owner Row |
| `crossPageContextView.js` | 77,713 | 76K | Home cross-page context, daily-driver readiness, sample validation record flow, real-media readiness |
| `renameView.js` | 68,595 | 67K | Rename table, TV + Movie preview, Apply Readiness ledger, sidecar overrides, bulk actions |
| `reportsView.js` | 53,210 | 52K | Audit/reports view, failure markers, priority CSV, rerun preview |
| `app.js` | 52,234 | 51K | App shell, sidebar navigation, polling, backend lifecycle (close-readiness, shutdown), button wiring |
| `networkView.js` | 42,850 | 42K | Network readiness, worker rows, worker detail, worker filter warnings |
| `scheduleView.js` | 32,757 | 32K | Schedule grid, block detail, schedule preview and save |
| `maintenanceView.js` | 32,627 | 32K | Maintenance tools, environment probe, release dry-run, backfill dry-run |
| `diagnosticsStateSummaryView.js` | 30,672 | 30K | Diagnostics state summary panel (artifact health, state file status) |
| `progressView.js` | 27,649 | 27K | Live progress view, active jobs table, live events stream |
| `launchHistoryView.js` | 27,622 | 27K | Launch history table and row detail |
| `settingsMetadata.js` | 25,630 | 25K | Settings field metadata, combo choices, help text, field definitions |
| `settingsOverview.js` | 18,325 | 18K | Settings read-only overview, media-policy readiness rows |
| `launchReadinessView.js` | 13,410 | 13K | Launch readiness ledger, preflight rows |
| `telemetryView.js` | 11,341 | 11K | Telemetry panel, GPU/CPU detail rows, NVENC idle display |
| `domHelpers.js` | 10,337 | 10K | DOM utility functions: `byId()`, `setText()`, `setHtml()`, etc. |
| `diagnosticsBridge.js` | 10,271 | 10K | Diagnostics bridge / tail rendering helpers |
| `diagnosticsTailView.js` | 9,101 | 8.9K | Tail rendering panel |
| `contractView.js` | 9,027 | 8.8K | API contract viewer, method/scope/route filter |
| `settingsCommandHistory.js` | 3,887 | 3.8K | Settings-specific command history rendering |
| `renameHistoryView.js` | 2,865 | 2.8K | Rename apply history panel |
| `renameLabels.js` | 2,581 | 2.5K | Rename label and status-text constants |
| `formatters.js` | 2,478 | 2.4K | Shared format helpers: dates, file sizes, labels |
| `apiClient.js` | 2,458 | 2.4K | HTTP client: `apiGet`, `apiPost`, timeout, token headers, error parsing |

**Total JS surface**: ~1.57 MB across 30 files.

---

## God-File Territory (>100 KB)

Five files each exceed 100 KB. Each is the sole module for a major WebView page, accumulating all page-specific logic as new panels are added.

### `settingsView.js` — 215K

Responsibilities: Settings builder UI for all config pages (Basic, Video, Audio, Subtitles, Advanced, Network); staged changes JSON; preview-patch; save-patch; reload; settings-to-launch intent; active media policy boundary panel; backend preview/save result panel; staged media-policy delta.

**Flag**: Covers both the interactive builder AND multiple read-only evidence panels. If the builder and the evidence panels were separated, the module would be substantially smaller.

### `completedView.js` — 205K

Responsibilities: main table; row selection; size evidence; route agreement; real-media output proof ladder; completed-to-pending publish overlap proof; backend publish reconciliation; diagnostics handoff from completed rows.

**Flag**: Real-media proof ladder and publish reconciliation are standalone read-only panels that could be isolated. The main table + row selection is the load-bearing core; the panels were accumulated on top.

### `pendingPublishView.js` — 168K

Responsibilities: main table; row detail; recovery plan; drain action confidence; Publish Button Guard; filter-scope chain; diagnostics handoff.

**Flag**: Filter-scope chain and drain guard logic are tightly coupled to the table but span a significant portion of the file. The Publish Button Guard logic is the most safety-critical section.

### `queueView.js` — 118K

Responsibilities: main queue table; row detail; investigation signals; filter-scope launch decision evidence; open-source-file/folder operations.

**Flag**: Investigation signals and filter-scope launch decision are page-specific logic that grew substantially with the V5 transition.

### `launchView.js` — 108K

Responsibilities: pipeline start (once/continuous/validate); pending drain launch; audit start; rerun start; control flags (pause/stop/rescan); launch readiness panel; launch history.

**Flag**: Audit and rerun launch are secondary use cases but are bundled into the same file as primary pipeline start. Launch history was added later and is now a significant subsection.

---

## Moderate Concern (50–100 KB)

| File | Size | Note |
|---|---|---|
| `commandHistory.js` | 85K | Spans command rendering, owner-page cross-linking, resolution posture, and evidence checklist across all pages. It is used as a helper by multiple views, not a standalone page view — its breadth is a design choice. |
| `diagnosticsView.js` | 81K | Spans tail, state summary, open targets, and owning-page handoff. Each section is distinct. |
| `crossPageContextView.js` | 76K | Spans Home page, daily-driver readiness, sample validation record flow, and real-media readiness. Each section was added in a separate V5 phase. |
| `renameView.js` | 67K | TV + Movie rename are distinct modes but share the Apply Readiness ledger and table infrastructure. |

---

## Healthy / Single-Responsibility (<32 KB)

| File | Size | Assessment |
|---|---|---|
| `apiClient.js` | 2.4K | Excellent — single responsibility, single function group |
| `formatters.js` | 2.4K | Good — shared format utilities only |
| `renameLabels.js` | 2.5K | Good — constants file |
| `renameHistoryView.js` | 2.8K | Good — narrow scope |
| `settingsCommandHistory.js` | 3.9K | Good — narrow scope |
| `domHelpers.js` | 10K | Good — DOM utilities only |
| `diagnosticsBridge.js` | 10K | Good |
| `diagnosticsTailView.js` | 8.9K | Good |
| `contractView.js` | 8.8K | Good |
| `telemetryView.js` | 11K | Good |
| `launchReadinessView.js` | 13K | Good — bounded responsibility |
| `settingsOverview.js` | 18K | Reasonable |
| `settingsMetadata.js` | 25K | Reasonable — data-heavy but bounded |
| `launchHistoryView.js` | 27K | Reasonable |
| `progressView.js` | 27K | Reasonable |
| `diagnosticsStateSummaryView.js` | 30K | Reasonable |
| `maintenanceView.js` | 32K | Reasonable |
| `scheduleView.js` | 32K | Reasonable |
| `networkView.js` | 43K | Reasonable given network-mode complexity |

---

## Refactoring Policy

**Do not refactor** unless at least one of the following triggers applies:

1. A file exceeds ~300 KB and becomes unnavigable during active development.
2. A panel within a god-file requires isolated unit testing that would be materially simpler with a separate module.
3. A future framework migration makes smaller modules the natural migration unit.
4. A critical safety-path panel (e.g., Publish Button Guard) is obscured within a 200K file to the point where reviewers cannot reliably locate it.

The current 5 god-files are all operable and tested. The IIFE architecture does not prevent factoring — but premature splitting creates more entry points, more global state coordination, and more surface for introduction of cross-module bugs.

---

## Summary

| Tier | Files | Total KB |
|---|---|---|
| God-file (>100 KB) | 5 | ~813K |
| Moderate (50–100 KB) | 4 | ~309K |
| Healthy (<50 KB) | 21 | ~451K |
| **Total** | **30** | **~1,573K** |

The five god-files account for ~52% of the total JS surface. All five are page-view modules that accumulated panels in place rather than splitting. This is consistent with the IIFE module architecture — there is no current reason to split until a triggering event occurs.

---

## See Also

- Module ownership and fragmentation: `Docs/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md`
- Mutation boundary review: `Docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- DOM ID namespace: `Docs/archive/admin-audits/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`
