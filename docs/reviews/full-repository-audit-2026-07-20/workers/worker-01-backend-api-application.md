# Worker 01 — Backend API and Application

Assigned rows: 170. Overall first-pass slice status is **complete** at the
current coverage hashes. Durable completion is 170/170: 169 validated rows in
the worker fragment plus the separately reconciled `backend_instance.py` row
in the prior-production fragment. No assigned rows remain pending.

## Final first-pass checkpoint 2026-07-21-B

Reviewer: `/root/w01_static_completion`.

- Completed summary-first, bounded every-line review of every assigned path.
  All closing SHA-256 values match the coverage baseline; the effective set is
  169 local rows plus one current-hash prior-production row, with no missing or
  extra W01 paths.
- The worker fragment has 33 `line_reviewed_with_findings` rows and 136
  `line_reviewed_no_findings` rows. Exact assembled finding-location
  reconciliation and the official fragment validator both returned zero
  issues.
- The worker finding fragment contains 29 confirmed findings: 13 P1, 8 P2,
  and 8 P3. The final tranche added `AUDIT-FIND-W01-022` through
  `AUDIT-FIND-W01-029`, covering remote rerun artifact locality, rerun rollback
  split state, active-claim coordinator switching, failed abort callbacks,
  stale worker-state backup recovery, watch-registry TTL ordering, settings
  smoke isolation order, and rerun batch path containment.
- The worker error fragment contains 28 ordinary audit-operation records
  through `AUDIT-ERR-W01-028`. All failed or truncated operations were recorded
  before bounded correction; none blocks coverage. Global finding and error
  record validation returned zero issues.
- This was a defensive, read-only audit. No product code, source media,
  operator state, network service, or central audit ledger was changed.

## Durable continuation checkpoint 2026-07-21-A

Reviewer: `/root/w01_static_completion`.

- Completed summary-first, every-line review of all 33 assigned
  `src/mediapipeline/core/api/**` paths, 28 assigned desktop/API entry and
  contract/server paths, and all 23 assigned desktop/application paths, in
  addition to the six original rows below.
- The worker review fragment now has 90 rows: 10
  `line_reviewed_with_findings`, 80 `line_reviewed_no_findings`, and zero
  official fragment-validator issues. Including the separately reconciled
  `src/mediapipeline/desktop/backend_instance.py` row yields 91/170 effective
  completion.
- Current-hash review added `AUDIT-FIND-W01-005` through
  `AUDIT-FIND-W01-008`; exact-location reconciliation also carries
  `CSW-2026-07-09-NETWORK-003` and `AUDIT-FIND-W16-003` on the reviewed
  desktop contract rows.
- `AUDIT-ERR-W01-012` records and discards a truncated whole-file source read;
  the affected 461-line file was then completely reread in bounded,
  nonoverlapping chunks. `AUDIT-ERR-W01-015` records a tool-truncated bulk
  review-row patch; the malformed row was replaced, missing rows were appended
  individually, and official validation returned zero issues. Every current
  hash still matches the coverage baseline. No product behavior, operator
  state, or media was changed.

The original six-row review packet follows unchanged for provenance. Its
historical reviewer was `/root/prior_audit_recon`.

## Semantic review slice 2026-07-20-A

Review method: each generated summary was read first, then every physical line
of each assigned source was inspected with numbered output. Related registries,
contracts, server integration, redaction code, and tests were used only as
supporting evidence and are **not** claimed complete here. Initial and closing
SHA-256 values were identical and matched the generated summaries.

| File | SHA-256 | Lines | Review status | Findings |
|---|---|---:|---|---|
| `src/mediapipeline/desktop/api/handler.py` | `e171e38e543e6b98c9435ab132eadee6abc3c495373dab35bddf4db5b45cd064` | 281 | `line_reviewed_with_findings` (terminal for this hash) | W01-CMD-001, W01-CMD-002 |
| `src/mediapipeline/desktop/api/handler_policy.py` | `d8514e563b676eb39b45482f3dd37a0715c0c1ebf482be3baa02a7afb0239572` | 194 | `line_reviewed_with_findings` (terminal for this hash) | W01-CMD-002 |
| `src/mediapipeline/desktop/api/routes_command.py` | `c2076f99607d577a9a145ff3ce28d458dc7395ca66e5aabbbc07f448c5cf4c86` | 11 | `line_reviewed_no_findings` (terminal for this hash) | None |
| `src/mediapipeline/desktop/api/contract_command.py` | `fede395da954882e17f110854382cd619800ffbe82514b777e826f91cef12cb2` | 37 | `line_reviewed_no_findings` (terminal for this hash) | None |
| `src/mediapipeline/desktop/api/command_journal.py` | `f6ce6e3b58c71ef1e2b18abe7e6f333e22a5b57de446ab714af412d38e1144fa` | 202 | `line_reviewed_with_findings` (terminal for this hash) | W01-CMD-001, W01-CMD-003 |
| `src/mediapipeline/desktop/api/command_journal_policy.py` | `62efa97f9b5a68805392d7136459f16c7dff99e231644fb3ad7f0a59a6386faa` | 152 | `line_reviewed_with_findings` (terminal for this hash) | W01-SEC-004 |

## Per-file semantic evidence

### `handler.py`

- Reviewed imports and handler construction; `do_OPTIONS`, `do_GET`, and
  `do_POST`; route matching, authorization/origin gates, JSON decoding and
  validation; strict accepted/terminal evidence; exception responses; CORS and
  response serialization; `_strict_command_evidence_payload`; and
  `_with_strict_command_evidence`.
- Dependencies considered: `server.py` authorization, journal adapter, and
  indeterminate-marker path; `routes_command.py`; `handler_policy.py`; contract
  validation; application-facade mutation methods.
- Tests considered: `test_api_handler_policy.py`,
  `test_application_facade_local_api_process_commands.py`, and the current
  `test_command_replay_adversarial.py` as supporting evidence only.
- Exact concerns: fresh server command identity at lines 120-121; accepted
  write and mutation dispatch at lines 122-149; terminal evidence only on the
  normal-return branch at lines 150-169; generic exception branch at lines
  171-179.

### `handler_policy.py`

- Reviewed the complete strict-route set; strict-route predicate; route-to-
  command contract mapping; `OperatorRouteError`; CORS/security headers; all
  validation, route, and persistence error payload builders; exception journal
  payload; validation-journal suppression; and automatic result-journal policy.
- Dependencies considered: canonical command route registry and all command
  contract fragments; `handler.py`; secret redaction policy.
- Tests considered: strict-route and payload-helper assertions in
  `test_api_handler_policy.py`, strict confirmation tests in
  `test_api_command_contracts.py`, and HTTP exception evidence in
  `test_application_facade_local_api_process_commands.py`.
- Exact concern: `route_exception_journal_payload` at lines 127-155 emits a
  generic route error without the accepted strict command ID or terminal phase.

### `routes_command.py`

- Reviewed all imports and construction of `POST_ROUTE_HANDLERS` from
  `COMMAND_ROUTE_METHODS`.
- A read-only runtime comparison found 117 registered command routes, 117 POST
  handlers, and no registry/handler differences.
- Dependencies considered: `src/mediapipeline/core/api/commands.py` and handler
  route lookup. Those evidence files are not marked complete by this entry.
- No defect was found in this wrapper at the recorded hash.

### `contract_command.py`

- Reviewed all five contract-fragment imports, concatenation order, public
  contract aliases, and `__all__`.
- A read-only runtime comparison found 117 contract rows, 117 unique contract
  paths, 117 POST handlers, and no handler/contract set differences.
- Dependencies considered: summaries for all five `contract_command_*`
  fragments, route registry, validation boundary, and contract tests. The child
  contracts and tests are supporting evidence only and remain unreviewed rows.
- No defect was found in this aggregation wrapper at the recorded hash.

### `command_journal.py`

- Reviewed constants, construction/loading, `record`, history mapping,
  persistence-health reporting, `_load`, atomic JSON save/rollback behavior,
  strict versus best-effort persistence, and SQLite mirroring.
- Dependencies considered: `command_journal_policy.py`, SQLite mirror storage,
  `server.py`, and strict evidence marker integration.
- Tests considered: journal persistence/redaction/degraded-state tests in
  `test_application_facade_core_contracts.py`, policy tests, atomic-write tests,
  and current adversarial replay/corruption tests as supporting evidence only.
- Exact concerns: append-only `record` at lines 49-68 has no reservation or
  replay lookup; persistence status at lines 70-123 reflects save failures but
  not load corruption; `_load` silently substitutes an empty history after a
  malformed/unreadable file at lines 125-134; the next save can replace that
  file at lines 136-185.

### `command_journal_policy.py`

- Reviewed schema/bound constants; sensitive-key normalization; scalar and text
  redaction; recursive bounded evidence; summary construction; history bounds;
  and loaded-entry sanitation.
- Dependencies considered: network URL/secret redactor and every current direct
  caller listed by the project index.
- Tests considered: `test_api_command_journal_policy.py`, journal redaction
  assertions in `test_api_command_contracts.py`, and facade persistence tests.
- Exact concern: the depth cap stringifies a value at lines 75-76 before the
  mapping-sensitive-key traversal at lines 77-84.

## Candidate findings

### W01-CMD-001 — P1 — Strict mutations have no request-stable replay or duplicate-command guard

- **Confidence:** high.
- **Category:** data integrity / command lifecycle.
- **Locations:** `handler.py:120-149`; `command_journal.py:49-68`.
- **Root cause:** every strict request receives a new server-generated UUID at
  `handler.py:121`. The handler does not consume a request-stable command ID,
  and `CommandJournal.record` only prepends an entry and persists it. There is no
  atomic reserve, fingerprint comparison, in-progress response, completed-result
  replay, or cross-route conflict check.
- **Failure scenario:** a strict mutation succeeds but the HTTP response is
  lost, or two identical requests arrive concurrently. Both attempts receive
  distinct IDs and both reach the mutation method at line 149. This affects all
  routes in the strict set, including commands whose repeated execution may
  move, rename, publish, reconcile, or stop resources.
- **Evidence:** repository search found `X-MediaPipeline-Command-ID`,
  `strict_command_fingerprint`, `reserve_strict_command`, and
  `complete_strict_command` only in
  `tests/python/desktop/test_command_replay_adversarial.py`, not in `src/`.
  That supporting test specifies simultaneous duplicate, lost-response,
  restart-replay, and cross-route-conflict cases at lines 193-298 and 434-472.
- **Existing safeguards:** token/origin checks, strict JSON confirmations,
  accepted evidence, and some domain-specific guards reduce unauthorized or
  obvious duplicate actions. None supplies uniform request-level replay across
  the 23 strict routes or resolves a lost response.
- **Test gap:** the normal HTTP tests assert that a fresh 32-hex command ID is
  returned, but do not prove one mutation for concurrent/retried requests.
  The current adversarial file describes the missing coverage but was not run
  or marked complete in this slice.
- **Recommended remediation:** accept a validated idempotency/command ID header;
  fingerprint canonical route plus validated payload; atomically reserve it in
  the authoritative journal; return in-progress, replay the persisted terminal
  response, and reject same-ID/different-fingerprint use. Define retention and
  crash recovery without weakening per-route domain guards.
- **Validation rung:** targeted journal unit tests plus concurrent HTTP tests,
  restart/lost-response tests, strict confirmation/command-journal tests, and
  affected Local API smokes. Exercise representative rename, publish, network,
  and lifecycle routes without real source mutation.
- **Prior-audit relationship/disposition:** not reconciled; new candidate for
  coordinator deduplication. No code change made.

### W01-CMD-002 — P1 — Mutation exceptions leave accepted strict commands without linked terminal or indeterminate evidence

- **Confidence:** high.
- **Category:** recovery / observability / command lifecycle.
- **Locations:** `handler.py:149-179`; `handler_policy.py:127-155`.
- **Root cause:** the strict terminal journal block runs only after the mutation
  method returns. An exception from line 149 jumps to the generic outer handler,
  which records `local_api.route_exception` without `strict=True`, without the
  strict command ID, and without a completed/failed/indeterminate evidence
  phase. The indeterminate marker is used only when the post-return terminal
  journal write itself fails.
- **Failure scenario:** a mutation performs some or all side effects and then
  raises. The durable history contains an `accepted` record plus an unlinked
  generic 500 record. After restart, an operator or replay mechanism cannot tell
  whether retrying is safe.
- **Evidence:** the current HTTP test at
  `test_application_facade_local_api_process_commands.py:257-281` explicitly
  observes this shape: a strict `pipeline.start` accepted entry followed by a
  generic route-exception entry, while persistence still reports healthy.
- **Existing safeguards:** the accepted record and redacted error ID preserve
  some evidence; normal-return terminal write failure returns 503 and attempts
  an indeterminate marker. They do not cover an exception thrown by the command
  implementation itself.
- **Test gap:** no test requires a linked terminal failure/indeterminate record
  or recovery marker when a strict command raises after possible side effects.
- **Recommended remediation:** keep the strict command context around dispatch;
  on any dispatch exception, durably record a linked terminal failure only when
  non-application is proven, otherwise persist an indeterminate lease/recovery
  marker before responding. If that persistence fails, fail closed and expose
  persistence degradation without leaking the internal exception.
- **Validation rung:** targeted handler policy/unit tests, HTTP fault-injection
  before and after a synthetic side effect, restart/recovery-status checks,
  command journal/strict JSON tests, and affected Local API smokes.
- **Prior-audit relationship/disposition:** not reconciled; new candidate for
  coordinator deduplication. No code change made.

### W01-CMD-003 — P1 — Malformed command history is treated as empty and can be overwritten while health reports clean

- **Confidence:** high.
- **Category:** durable evidence / fail-closed recovery.
- **Locations:** `command_journal.py:70-134`, `command_journal.py:136-185`.
- **Root cause:** `_load` catches malformed JSON and I/O failures, logs a warning,
  and returns `[]` without recording load degradation. `to_mapping` therefore
  reports JSON persistence as `not_attempted` and `degraded: false`. A later
  record serializes the replacement in-memory list over the authoritative path.
- **Failure scenario:** a partial/corrupt journal exists at server startup. The
  API appears healthy, accepts a strict mutation, and replaces prior accepted or
  terminal evidence, erasing the record needed to decide whether retry is safe.
- **Evidence:** direct line inspection establishes the load-to-empty and later
  replace path. Current adversarial coverage at
  `test_command_replay_adversarial.py:400-432` expects malformed history to
  block mutation and surface degraded status; the production class has no
  corresponding load-error state.
- **Existing safeguards:** atomic temp-file replacement protects ordinary saves,
  and save-time errors can report degraded/raise in strict mode. Those controls
  begin only after a successful or silently discarded load.
- **Test gap:** existing journal tests cover save failure, SQLite mirror failure,
  reload of valid JSON, and temp cleanup, but not malformed/unreadable startup
  followed by a strict command.
- **Recommended remediation:** preserve/quarantine the unreadable file; retain a
  durable load-error state in `journal_persistence`; block strict mutations until
  explicit repair/recovery establishes authority; never overwrite the only
  evidence copy as an implicit recovery action.
- **Validation rung:** corrupt/truncated/permission-denied startup tests,
  strict-mutation fail-closed HTTP tests, recovery and backup preservation tests,
  plus command history and Local API smokes.
- **Prior-audit relationship/disposition:** not reconciled; new candidate for
  coordinator deduplication. No code change made.

### W01-SEC-004 — P2 — Depth limiting can persist sensitive mapping values in plaintext

- **Confidence:** high for the mechanism; medium for reachability from every
  validated route payload.
- **Category:** security / secret handling.
- **Locations:** `command_journal_policy.py:66-87`, especially lines 75-84.
- **Root cause:** `bounded_command_evidence` applies `depth >= 4` first and
  stringifies the entire value. A mapping reached at that depth therefore skips
  sensitive-key matching. The downstream URL/text redactor handles URLs,
  `key=value`, and bearer text, but not Python/JSON mapping syntax such as
  `{'password': 'value'}`.
- **Failure scenario:** request, result, or loaded journal evidence contains a
  sensitive key in a mapping at the depth boundary. Its plaintext value is
  embedded in the bounded string and saved to JSON history/SQLite evidence.
- **Evidence:** a read-only bundled-Python probe with the fake value
  `AUDIT_FAKE_SECRET_7e2` produced
  `{'a': {'b': {'c': {'d': "{'password': 'AUDIT_FAKE_SECRET_7e2'}"}}}}`
  and `FAKE_SECRET_PRESENT=True`.
- **Existing safeguards:** sensitive keys are redacted at shallower mapping
  depths; scalar URL/assignment/bearer redaction and secret-transfer validation
  journal suppression cover known common shapes. The ordering at the cap
  bypasses all of those key-aware controls.
- **Test gap:** current tests cover root and shallow nested secret keys but not a
  mapping/list at or beyond the recursion cap.
- **Recommended remediation:** inspect mapping keys before applying a depth cap;
  replace over-depth structures with a constant truncation sentinel or retain a
  bounded key-aware shape, never `str`/`repr` an uninspected container. Apply the
  same rule while sanitizing loaded legacy entries.
- **Validation rung:** focused policy tests for depths 3-6, mappings nested in
  lists, all sensitive-key aliases, long values, URL/bearer text, loaded-entry
  sanitation, and an on-disk assertion that the fake secret never appears.
- **Prior-audit relationship/disposition:** not reconciled; new candidate for
  coordinator deduplication. No code change made.

## Confirmed strengths

- Command handler and contract wrappers are derived from canonical registries;
  the observed route/handler/contract sets are complete and duplicate-free.
- Authentication/origin checks precede body validation and mutation dispatch.
- Strict validation occurs before accepted evidence or side effects, and
  confirmation values remain strict booleans through the contract boundary.
- Normal strict command flow records accepted and terminal phases; terminal
  persistence failure returns an explicit indeterminate 503 response.
- Journal writes use same-directory temporary files, flush/fsync, atomic replace,
  bounded history, and in-memory rollback on raised strict save failure.
- Error payloads avoid returning raw internal exceptions, and common secret keys
  and network credential forms are redacted at ordinary depths.

## Evidence commands and outcomes

- Numbered `Get-Content` passes over all six assigned sources — complete; every
  physical line inspected.
- `Get-FileHash -Algorithm SHA256` plus physical line counts before and after
  review — complete; no source changed during review.
- Bundled-Python registry comparison — 117 command registry rows, 117 POST
  handlers, 117 unique contract paths, no set differences.
- `rg` symbol/header search across `src` and tests — replay/reservation API and
  client command-ID header absent from production source and present in the
  current adversarial test.
- Bundled-Python deep-redaction probe — completed successfully and reproduced
  W01-SEC-004 with a synthetic fake secret.
- No test suite was executed in this slice; supporting test source was inspected
  only. Consequently no test file receives terminal coverage here.

## Remaining gaps and irregularities

- 164 of Worker 01's 170 assigned rows remain pending.
- Related `server.py`, command registries, five child command-contract modules,
  validation boundary, URL redactor, storage mirror, and all cited tests remain
  under their assigned owners; this entry does not mark them reviewed.
- `tests/python/desktop/test_command_replay_adversarial.py` had no generated
  summary at review time, so it was opened directly as supporting evidence. That
  generated-navigation omission should be reconciled by the generated-docs
  owner; the test itself is not complete here.
- The four candidates require coordinator prior-audit reconciliation,
  deduplication, and final disposition. W01-SEC-004 also needs route-reachability
  enumeration to calibrate final severity.
- The production-audit skill's data-integrity, security, operational, and
  observability lenses drove the replay, corrupt-load, exception-evidence, and
  redaction probes. It did not authorize application changes.
