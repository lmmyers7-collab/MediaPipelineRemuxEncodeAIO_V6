# Worker 07 — WebView Common Surface

First-pass coverage is complete for the 122 rows that were pending when this slice began. The 123rd assigned row, `apps/desktop/webview/static/assets/app/closeReadiness.js`, already had a current-hash first-pass record in `prior-production-audit-review.jsonl` and was not duplicated.

## Exact scope

- Newly reviewed rows: **122 / 122**
- Total W07 first-pass rows including the prior record: **123 / 123**
- Exact source: **49,432 physical lines**, **2,316,404 bytes**
- File types: **82 JavaScript**, **20 HTML**, **20 CSS**
- Risk tiers in the newly reviewed slice: **12 high**, **110 low**
- Review outcomes: **115 no-findings**, **7 with path-local findings**
- W07-local findings added: **2**
- W07-local execution/error records: **10**
- Independent second review: pending

All 122 baseline SHA-256 values and line counts matched current bytes at publication. Every available generated summary was read before its source, its embedded source hash matched, and exact `refresh_summaries.render_summary` reproduction matched for all 122 paths. No product, test, generated, configuration, media, operator-state, or central audit-ledger file was edited by this worker.

## Findings

- `AUDIT-FIND-W07-002` (**P1**) — `apiClient.js` sends no caller-stable identity for strict mutations and turns network loss, timeout, invalid JSON, and `COMMAND_OUTCOME_UNKNOWN` into generic retry advice. The focused replay smoke reproduces simultaneous and lost-response duplicate-command risk. This is the frontend half of `AUDIT-FIND-W01-001`/`W01-002`, but has a distinct path-local root cause.
- `AUDIT-FIND-W07-001` (**P3**) — `page-network.html` exposes the deliberately promoted, backend-owned Network lifecycle controls while the active no-touch register and browser runbook still describe the pre-promotion outside/read-only boundary. Current-state docs, inventories, tests, and completed change control prove the controls are intentional; the defect is stale canonical safety guidance.
- Existing exact-hash findings reconciled without duplication:
  - `CSW-2026-07-09-HOME-003` on `app/refreshCoordinator.js`, `app/lifecycle.js`, and `app/lifecycle/topbar.js`.
  - `CSW-2026-07-09-MAINTENANCE-002` on `maintenance/releaseCommands.js`.
  - `CSW-2026-07-09-TELEMETRY-004` on `progress/barState.js`.

## Line-review and validation evidence

- Ordered provenance pass: **189,663 generated-summary bytes** read before **2,316,404 source bytes**; exact summary regeneration, generator fingerprints, source hashes, physical lines, and baseline joins all matched.
- JavaScript: Node `--check` passed all 82 files. Acorn parsed all 82 files and the custom recursive traversal covered **266,135 tokens**, **276 comments**, **3,777 functions**, and **97 catch clauses**. All 31 empty catches were reconciled to bounded localStorage/UI/pointer cleanup behavior rather than silently swallowed backend mutations.
- HTML: all 20 partials parsed with balanced structure, no duplicate IDs, no inline event handlers, no unsafe `_blank` targets, and no untyped buttons.
- CSS: all 20 stylesheets had balanced braces and resolved local imports/tokens; outline-removal cases retained explicit focus box-shadow or border treatments.
- Focused unit/static/browser validation: **111 test methods**, **108 passed**, **3 failed**.
  - The API-client replay failure confirms `AUDIT-FIND-W07-002`.
  - The close-readiness contract failure confirms existing `CSW-2026-07-09-HOME-003`.
  - The generated command-boundary check reports already-isolated concurrent priority-export inventory/owner drift; 43 other API/mutation/Network boundary tests in that command passed and no new W07 root cause was assigned.
  - Navigation, CSS tokens, pipeline-log, maintenance, diagnostics, Network browser, lifecycle reconciliation, Home live-state, and large-table modules passed: **65 / 65**.
- Scoped ledger validation passed with **122 unique expected paths**, exact worker ownership, current hashes, required schema fields, exact path-local finding-set equality, valid finding/error references, valid W07 finding/error schemas, and no duplicate root-cause fingerprint.

## Artifacts

- `worker-07-webview-common-review.jsonl` — 122 current-hash first-pass records.
- `worker-07-webview-common-findings.jsonl` — 2 deduplicated W07 findings.
- `worker-07-webview-common-errors.jsonl` — 10 command/error records, including resolved audit-command issues and the three preserved validation failures.

Central `COVERAGE_MATRIX.*`, `FINDINGS.*`, and `ERROR_LEDGER.*` publication is intentionally left to the coordinator. W07 remaining first-pass scope is **zero**; independent attestation remains outside this task.
