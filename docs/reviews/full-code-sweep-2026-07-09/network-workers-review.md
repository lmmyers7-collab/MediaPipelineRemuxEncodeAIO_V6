# Network / Workers Deep Review — 2026-07-09

## Executive assessment

The Network Workers surface has a sound primary authority split: the WebView renders backend evidence and submits only documented Local API routes; the backend owns lifecycle providers, claims, done/release, settings persistence, media execution, state files, and command evidence. The coordinator protocol has strong defensive controls (HMAC request signing with nonce replay protection, strict JSON, capped bodies, identity validation, atomic claim/save rollback, redaction, and preserved pending-done recovery).

No P0 finding was identified. One P1 recovery defect and three evidence/authority defects need correction before treating the Network command history and join setup path as fully trustworthy. In particular, confirmed lifecycle responses currently describe a real mutation as `effect: none`; a failed token-rotation blob request can rotate the active/configured coordinator token without delivering the replacement token to a worker.

Scope was read-only. No worker/coordinator lifecycle endpoint, network mutation endpoint, process, or test suite was run.

## Workflow traces

| Trace | Evidence and result |
|---|---|
| Provider availability and state | `GET /api/network/workers` reads persisted `coordinator_inflight.json`, `worker_state.json`, and `cluster.log` through `NetworkFacadeMixin.get_network_workers`; it deliberately labels lifecycle state as session-memory evidence and warns on unreadable/stale state. Lifecycle dry-runs require the configured role, callable provider, duplicate guard, close-readiness, role-specific URL/token/path-map checks, and pending-done posture. |
| Lifecycle dry-run/start/stop | `LocalApiNetworkCommandPayloadMixin` routes all four role/action pairs to `request_network_lifecycle`. Dry-runs are no-touch. Confirmed calls require literal `confirm_start`/`confirm_stop`, provider availability, and strict journal recording; provider failure and journal failure fail closed. Active stop requests drain/preserve work: coordinator disables claims while keeping reporting routes; worker stops polling while retaining heartbeat/done reporting. See finding NETWORK-002 for response evidence drift. |
| Worker test connection | The backend performs L1 TCP, L2 signed `/api/ping`, and L3 configured source/output path checks. It validates the coordinator URL before TCP, returns a redacted URL, suppresses command journaling, and does not claim/start/save/media-mutate. |
| Coordinator discovery | Backend mDNS discovery is bounded by timeout, validates each discovered URL before returning it, and returns only selectable rows. WebView selection stages `WorkerCoordinatorUrl`; persistence remains the existing backend Settings path. Missing `zeroconf` is a warning rather than a crash. |
| Join-blob creation/import | Blob codec bounds encoded/decoded size, field size, library count, schema, token length, and coordinator URL. Creation/import require literal confirmations and are unjournaled because the blob contains the token. Import saves through backend Settings then runs read-only connection testing; it does not launch polling. See findings NETWORK-001, NETWORK-003, and NETWORK-004. |
| Auth redaction | Local API command-journal redaction includes `join_blob`/token-like keys. URL redaction strips userinfo/query/fragment; free-text redaction covers token-like assignments and Bearer values. Cluster logging sanitizes and redacts rendered fields. Coordinator requests are HMAC-signed over method/path/timestamp/nonce/body hash and nonce replay is rejected. |
| Restart, retry, cleanup, rollback, orphan handling | Worker startup flushes a pending done report before claims and crash recovery keeps unreadable/undeliverable state rather than overwriting it. Claim response serialization or registry-save failure rolls the claim back. Coordinator stale reaper reclaims expired leases; late terminal evidence is handled. Start cleanup removes partially created dispatcher runtime; confirmed start compensates by stopping the provider if strict journaling fails. Active stop uses drain/preserve behavior rather than releasing/aborting silently. A post-restart lifecycle state is intentionally not authoritative because the exposed lifecycle state is session-memory only; persisted files are the recovery evidence. |

## Findings

### P0 — none

No source-media mutation path, unauthenticated coordinator mutation path, direct WebView process/lifecycle implementation, or claim/done/release ownership bypass was found in the reviewed scope.

### P1

#### CSW-2026-07-09-NETWORK-001 — token rotation commits before join-blob validation and has no compensating rollback

`request_network_coordinator_join_blob()` calls `_coordinator_join_token(..., rotate=True)` before `encode_network_join_blob()`. With an existing `CoordinatorAuthToken`, `_coordinator_join_token()` saves a newly generated token before the later blob encoding validates the supplied coordinator URL (`src/mediapipeline/core/network/facade.py:1423-1465`, `:1504-1524`). A malformed or unusable `coordinator_url` therefore produces an error response after the token has already changed. If a coordinator is running, its auth token is also hot-swapped before blob encoding completes.

Impact: a confirmed “rotate + create blob” attempt can strand existing workers immediately (or at next coordinator restart) without returning a replacement blob/token to distribute. The response reports only blob-creation failure; it supplies neither rollback evidence nor an actionable token-rotation recovery record. This is a lifecycle availability and recovery defect, not a media mutation issue.

Recommendation: validate the complete blob input and prepare the blob before any token/config/runtime mutation; then make rotation + persistence + runtime update a transaction with explicit compensation. If atomicity across the settings store and running dispatcher is impossible, return a durable, redacted recovery record containing rotation status and rollback/redistribution instructions. Add tests for invalid URL, encoding failure, settings-save failure, and running-coordinator update failure, asserting no token change or verified restoration.

### P2

#### CSW-2026-07-09-NETWORK-002 — confirmed lifecycle result falsely reports `effect: none`

`_network_lifecycle_dry_run_data()` sets `effect` to `NETWORK_LIFECYCLE_EFFECT_NONE` (`src/mediapipeline/core/network/lifecycle_facade.py:547`). `request_network_lifecycle()` reuses that data unchanged for confirmed success and failure results (`:606-846`). Consequently a successful start or stop can create a provider, change session lifecycle state, and strictly journal the command while its returned `data.effect` remains `none`.

This conflicts with the published contract: confirmed routes are `backend-lifecycle` in `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md:17,61-64`, `docs/inventories/API_ROUTE_INVENTORY.md:314-317`, and `src/mediapipeline/desktop/api/contract_command.py:1202-1247`. The WebView displays `data.effect` in its command result, so it can show an actual lifecycle mutation as “Backend effect: none.”

Impact: operator evidence, diagnostics, and any contract consumer relying on command-result payloads misclassify a real lifecycle mutation as a dry-run/no-effect action. This weakens the command journal’s explanatory value during restart and orphan-worker investigations.

Recommendation: set confirmed result `effect` to `backend-lifecycle` (including blocked/failed confirmed attempt semantics if that is the chosen result convention), preserve `none` only for dry-runs, and add API-level assertions for all four confirmed routes. The current tests assert dry-run `none` and published route metadata, but do not assert the returned confirmed-result effect.

#### CSW-2026-07-09-NETWORK-003 — coordinator join-blob route does not enforce coordinator role

The join-blob command captures `role = _network_role(resolved)` only for response metadata, then continues regardless of role (`src/mediapipeline/core/network/facade.py:1487-1559`). A Local API caller in `standalone` or `worker` mode can therefore invoke the coordinator-named route and, with rotation confirmed, mutate `CoordinatorAuthToken`/app state and mint a cluster join blob without an active or configured coordinator role.

Impact: this is a role-authority bypass within the already authenticated Local API boundary. It can create confusing or invalid cluster credentials and compounds NETWORK-001; it does not expose a remote unauthenticated control path.

Recommendation: fail closed unless `NetworkRole == coordinator` (and define whether an active coordinator is required), or rename/reclassify the command as an explicit offline bootstrap operation with its own documented preconditions. Add negative role tests for standalone and worker modes, including `rotate_token=true` no-write assertions.

### P3

#### CSW-2026-07-09-NETWORK-004 — join-import response effect is outside the published route vocabulary

The route contract and inventories define `POST /api/network/worker/join-cluster` as `config-write` (`src/mediapipeline/desktop/api/contract_command.py:1186-1196`; `docs/inventories/API_ROUTE_INVENTORY.md:313`). The implementation returns `effect: "config-write-and-read-only-test"` (`src/mediapipeline/core/network/facade.py:1574`), a value not advertised by the route contract/effect taxonomy.

Impact: consumers cannot rely on a stable effect enum when classifying command results. The behavior itself is accurately described—settings write followed by a no-touch test—but the evidence field drifts from the contract.

Recommendation: retain `effect: config-write` and add a separate `follow_up_effects: ["none"]`/`test_connection_performed: true` field, or promote the composite effect to every contract/inventory/schema consumer in the same change. Add a response-contract test.

## No-finding coverage

- The reviewed WebView (`partials/page-network.html` and `assets/networkView.js`) does not implement process spawning, worker polling, claims, done/release, state-file writes, queue mutation, media policy, publish/drain, or direct settings persistence. It calls backend routes and delegates settings save/preview to the backend Settings surface. Future retry/reclaim/release/abort controls remain disabled.
- Normal pipeline Launch is blocked in network roles; network provider starts use the backend single-file worker path rather than a normal local queue launch.
- Lifecycle commands have a backend lock, duplicate guards, literal boolean confirmation checks, provider-availability checks, close-readiness checks, and strict-journal-before-state-commit behavior. Start attempts compensate by stopping the provider if strict journal persistence fails.
- Worker claims are one-at-a-time, coordinator-assigned, atomic around select/claim, and rollback on response serialization/persist failure. Done/release validates worker ownership; worker failure paths persist pending reports for retry.
- Library-relative claims reject absolute, drive-qualified, and parent-traversal paths; source-path-map roots and mapped tails are validated as absolute Windows paths and constrained below the replacement root.
- Coordinator HTTP mutation routes require signed HMAC authentication, protect against nonce replay, reject malformed/non-finite JSON, and cap request body size. The health route is the intentionally unauthenticated low-sensitivity exception.
- Network state visibility is explicitly persisted-evidence-first. The UI identifies the source and warns when state files are malformed, missing, stale, or contradict the session lifecycle view.

## Test and contract assessment

The inventory lists all 13 reviewed Network routes, including the read-only workers route, four dry-runs, worker test/discovery, join create/import, and four confirmed lifecycle routes (`docs/inventories/API_ROUTE_INVENTORY.md:306-317`). Focused coverage is substantial:

- `test_application_facade_process_launch.py` exercises provider guarding, strict journaling, duplicate serialization, no-touch dry-runs, normal Launch network-mode blocking, lifecycle provider execution, and claimed-job completion.
- `test_network_lifecycle_fixes.py`, `test_network_workflow.py`, `test_network_crash_recovery.py`, and `test_network_done_release.py` cover active-stop preservation, drain finalization, stale reclaim, claim rollback, pending done retry, late terminal reports, and cleanup failures.
- `test_network_security.py`, `test_network_join.py`, `test_network_test_connection.py`, `test_network_mdns.py`, and `test_network_library_relative_claim.py` cover signing/redaction, blob bounds/confirmation/unjournaled behavior, L1-L3 probe behavior, discovery degradation, and path authority.
- `test_webview_network_read_only_boundary.py` and the browser smoke verify the UI boundary and controls.

Coverage gaps exposed by this review: no test asserts confirmed lifecycle result `data.effect`; no test covers rotate-then-invalid-blob transactional behavior; no test requires coordinator role for the coordinator join-blob route; and no test asserts join-import result effect equals the published contract value.

## Coordinator handoff

1. Fix **NETWORK-001** first. Preserve the old token until all blob inputs are valid and the replacement blob is ready, then commit rotation with compensation/recovery evidence.
2. Fix **NETWORK-002** next. Align confirmed command-result effect with the API contract and verify command journal/result rendering uses the corrected field.
3. Decide and enforce the intended offline-bootstrap policy for **NETWORK-003**. Prefer explicit coordinator-role preconditions unless offline minting is a deliberate supported workflow.
4. Resolve **NETWORK-004** by selecting one canonical effect vocabulary and updating implementation, route contract, schema/inventory, and tests together.
5. After code changes, run the targeted Python/WebView route and boundary tests, plus an isolated two-machine or mocked-provider lifecycle sequence: start coordinator, join worker, test connection, claim, worker stop with active job, coordinator drain, backend restart, pending-done replay, and token rotation failure. No real-media validation is required for these control/evidence fixes unless the change reaches worker media execution/publish policy.

## Limits

- This was static, read-only analysis. I did not start/stop a coordinator or worker, invoke mutation routes, alter config/state, or run tests because the requested audit allowed only this report file to change.
- Existing workspace edits—including edits to `networkView.js`, `page-network.html`, source, inventories, tests, generated docs, and change packets—were pre-existing and were not changed or attributed by this review.
- Runtime behavior across real hosts, firewalls, clock skew, SMB/UNC permissions, process-tree termination, and actual FFmpeg work was assessed from code and tests only; it requires the coordinator handoff validation above.
