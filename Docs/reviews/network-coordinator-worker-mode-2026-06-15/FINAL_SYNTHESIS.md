# Network Coordinator/Worker Mode Final Synthesis

Date: 2026-06-15

Workers included: 14 of 14.

Confirmed findings: 35 total: 14 P1, 19 P2, 2 P3.

## Executive Risk Summary

Network coordinator/worker mode is not ready for unguarded production distributed processing. The strongest risks are not direct source-file deletion, but distributed ownership and evidence loss: external done reports can bypass worker ownership with empty `worker_id`, source identity is keyed by raw path text, terminal done/release reports can be acknowledged without durable coordinator state, malformed claims can reach backend launch as `single_file='.'`, and a watcher-start failure can release a claim while the launched process may continue.

The auth and evidence surfaces also need hardening before broader use. Startup accepts weak configured coordinator tokens, cluster-log redaction is field-incomplete, and `join_blob` can be journaled on Local API validation failure. These are LAN/local-operator surfaces, but the leaked values are precisely the secrets that authorize network workers.

Lifecycle controls exist now and are backend-owned, but the stop semantics and dry-run evidence do not yet match the published contract. A normal confirmed stop can abort active work even though the contract says abort/partial cleanup is a separate explicit action, and stop dry-runs do not report active in-memory worker jobs.

## Confirmed High-Risk Boundaries

| Boundary | Status |
|---|---|
| Source mutation | No direct source delete/overwrite path was confirmed in worker reports. Risk is indirect through wrong `single_file`, duplicate processing, and stale rerun evidence. |
| Queue/claim ownership | High risk. `/api/done` empty-owner reports, raw source identity, duplicate job-id mutation, and concurrent claim coverage gaps can corrupt distributed ownership. |
| Pending publish / final output evidence | High risk. Network worker done reports do not consume PowerShell result artifacts, so publish/output/route evidence can be lost even when backend processing produced it. |
| Command journal / secrets | High risk. `join_blob` validation failures and incomplete cluster-log field redaction can leak network auth material into operator evidence surfaces. |
| Lifecycle stop / close safety | High risk. Confirmed Network stop can kill active pipeline work, while dry-run evidence can still present a clean path. |
| WebView authority boundary | Mostly preserved. The Network UI calls backend-owned routes and future dangerous controls remain disabled, but one path-map row Test overstates backend proof. |
| Docs and contracts | Drifted. Active docs, coverage matrix, route inventory totals, Tauri required routes, and some read DTO text no longer align with current backend-owned lifecycle/setup routes. |

## Stale Doc And Contract Drift

The current route contract has moved past the older design-only/read-only wording. Current Python metadata exposes worker board, dry-run lifecycle routes, confirmed lifecycle routes, worker test-connection, mDNS discovery, coordinator join blob, and worker join import. Active docs and some route inventories still say or imply the opposite.

Confirmed drift includes:

- `NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` still names `would_write_state` instead of `dry_run_writes` and `confirmed_route_would_write`.
- `CURRENT_PROJECT_STATE.md`, `OPEN_WORK_CHECKLIST.md`, and `DOCS_INDEX.md` still describe Network lifecycle controls as absent/design-only.
- `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` and route inventory totals are stale for the current 116 routes / 70 POST routes and omit Network setup rows.
- Tauri `REQUIRED_ROUTES` omits three active Network setup routes.
- `CONFIG_KEY_GLOSSARY.md` still describes `WorkerConfigOverrides` as applied at claim time even though backend policy ignores it.
- `NETWORK_WORKER_HARDENING_PLAN.md` mixes a not-started baseline with later completed 2026-06-14/2026-06-15 work.

## Test Coverage Gaps

The test suite is broad but not sufficient for the top risks:

- No concurrent two-worker `/api/claim` race test.
- No endpoint-level empty/omitted worker-id `/api/done` rejection tests.
- No post-save claim response serialization/write rollback tests.
- No done/release registry-save-failure acceptance tests that prove worker pending reports are retained.
- No watcher-thread startup failure after process launch test.
- No malformed `ok` claim identity test preventing `single_file='.'`.
- No crash-recovery-post-failure test proving polling stays blocked.
- No strict `ClaimResponse` boolean/int coercion tests.
- No malformed/hostile join blob tests proving no save, no journal entry, and no token/blob leak.
- No active-work dry-run tests and no cooperative-stop tests proving stop avoids process termination.
- No network worker result-artifact parsing tests.
- Browser Network smoke currently fails on `/api/ui-preferences`, and its join route fixture has stale confirmation metadata.

## No-Finding Areas

The workers did not confirm findings in these areas:

- HMAC request signing, nonce/cache/skew handling, and response read caps were reviewed without direct findings.
- Strict JSON rejection of `NaN` / `Infinity` and `DoneRequest` strict boolean handling were reviewed without direct findings.
- Library-relative claim resolution rejects absolute, drive-qualified, and parent-traversal relative paths.
- mDNS discovery, test-connection layer separation, local IP ranking, and share-block helpers had no direct findings.
- WebView Network settings save/preview delegates through backend Settings routes with `confirm_save`; auth-token settings are not rendered in clear text.
- Future WebView controls for drain, release, abort, reclaim, and quarantine remain disabled.
- Assigned PowerShell local-worker source did not rely on removed `Pipeline/Modules` or root launcher paths.

## Rejected Or Not Carried Forward

These worker observations were not entered as confirmed findings:

- Historical filename `NETWORK_MODE_READ_ONLY_DOCUMENTATION.md` is not a finding by itself; the body now documents current backend-owned boundaries accurately.
- CSS warning/confirmation hiding was checked by W10 and not confirmed.
- Direct source deletion, direct pending-publish drain bypass, direct publish bypass, and direct WebView filesystem mutation were not confirmed. Related risks are evidence/ownership risks, not direct media mutation findings.
- `src/mediapipeline/core/network/url_policy.py` missing generated summary was treated as incomplete navigation coverage, not a product defect.
- Worker-result evidence loss was not labeled as a direct publish/drain bypass; it remains a high-risk completion evidence gap.

## Incomplete Coverage

- No worker ran live two-machine LAN validation, real coordinator/worker lifecycle start/stop, real claims against media, FFmpeg/ffprobe media processing, publish/drain, rename, or real-media validation.
- The worktree already contained unrelated dirty source, docs/generated summaries, config, tests, and change packets. This synthesis did not edit or revert them.
- `tests/python/desktop/test_network_workflow.py` had a stale mock failure in assigned W01/W04 evidence.
- `tests/python/desktop/test_tauri_shell_scaffold.py` fails route parity for missing Network setup routes in Rust.
- `tests/python/desktop/test_api_route_inventory.py` fails route inventory/mutation matrix drift.
- `tests/webview/test_webview_browser_network_smoke.py` fails on the stale `/api/ui-preferences` POST allowlist.
- Generated-summary navigation was incomplete for `src/mediapipeline/core/network/url_policy.py`, `src/mediapipeline/desktop/network/processing_policy.py`, and untracked `tests/python/desktop/test_network_coordinator_policy_phase_e.py`.

## Recommended Fix Order

1. Source/claim/state corruption: fix empty-worker `/api/done`, normalized source identity, duplicate job ids, done/release durable acceptance, pending late done evidence, malformed claim identity, crash-recovery polling, and worker-release retry persistence.
2. Auth/secret safety: enforce configured token strength, redact every cluster-log field, and block secret-transfer request journaling on validation failures.
3. Lifecycle/provider correctness: make stop cooperative, report active work in dry-runs, remove worker startup race, and bridge network worker completion through PowerShell result artifacts.
4. Path-map/library safety: preserve path-map order, harden manual path-map traversal, split manual/auto/effective drift evidence, and correct worker-state read DTOs.
5. WebView/docs/tests: fix path-map row Test wording or backend route, update browser smoke allowlists/fixtures, refresh docs/inventories/Tauri route metadata, and add the missing race/hostile-input/lifecycle/result tests.
