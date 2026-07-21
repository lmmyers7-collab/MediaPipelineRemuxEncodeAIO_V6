# Worker 01 Backend/API High-Risk Slice — Independent Second Review

Date: 2026-07-20
Reviewer: independent validation-spine second reviewer
Scope: six exact baseline files owned by worker-01-backend-api-application
Review depth: every physical line of all six assigned files, plus bounded supporting reads and synthetic temporary-state probes
Mutation policy: source/application behavior remained read-only; only this review artifact and its worker-specific error ledger were created

## Outcome

Independent review confirms W01-001, W01-002, W01-003, and W01-004. W01-002 needs a factual wording correction, and W01-004 now has accepted-route and persisted-file proof sufficient to move from needs-runtime-proof to confirmed.

One additional fail-safe gap was found in the same command-evidence invariant as W01-002: if terminal journal persistence fails, the indeterminate-marker adapter can fail or have no state root and only logs the failure. This should be folded into W01-002 rather than opened as a duplicate root-cause record.

Recommended coordinator dispositions:

| Finding | Independent disposition | Severity | Confidence | Coordinator action |
| --- | --- | --- | --- | --- |
| AUDIT-FIND-W01-001 | confirmed | P1 | high | Retain; add executed adversarial-suite evidence |
| AUDIT-FIND-W01-002 | confirmed with factual correction and expanded evidence | P1 | high | Retain; correct the claim that no command-ID link exists and add the marker-durability extension |
| AUDIT-FIND-W01-003 | confirmed | P1 | high | Retain; add direct corrupt-startup and HTTP evidence |
| AUDIT-FIND-W01-004 | confirmed | P2 | high | Change disposition from needs-runtime-proof to confirmed |

No original finding was refuted. No independent alias is needed.

## Exact assigned files and baseline identity

Each generated summary was read before its source. The summary SHA-256, worker-01 review-fragment SHA-256, and current file SHA-256 agreed before semantic review.

| Path | Physical lines | SHA-256 |
| --- | ---: | --- |
| src/mediapipeline/desktop/api/handler.py | 281 | e171e38e543e6b98c9435ab132eadee6abc3c495373dab35bddf4db5b45cd064 |
| src/mediapipeline/desktop/api/handler_policy.py | 194 | d8514e563b676eb39b45482f3dd37a0715c0c1ebf482be3baa02a7afb0239572 |
| src/mediapipeline/desktop/api/routes_command.py | 11 | c2076f99607d577a9a145ff3ce28d458dc7395ca66e5aabbbc07f448c5cf4c86 |
| src/mediapipeline/desktop/api/contract_command.py | 37 | fede395da954882e17f110854382cd619800ffbe82514b777e826f91cef12cb2 |
| src/mediapipeline/desktop/api/command_journal.py | 202 | f6ce6e3b58c71ef1e2b18abe7e6f333e22a5b57de446ab714af412d38e1144fa |
| src/mediapipeline/desktop/api/command_journal_policy.py | 152 | 62efa97f9b5a68805392d7136459f16c7dff99e231644fb3ad7f0a59a6386faa |

The supporting generated summaries for server.py, contracts/api_commands.py, core/validation/boundary.py, core/api/commands.py, all five contract-command fragments, core/network/url_policy.py, local_api_main.py, and cited tests were also read before bounded source inspection. Supporting files are evidence only and are not claimed complete by this review.

## Cross-file route, contract, and journal semantics

Read-only runtime introspection produced these current invariants:

- Canonical command registry: 117 paths.
- POST_ROUTE_HANDLERS: 117 paths.
- LOCAL_API_COMMAND_ROUTE_CONTRACT: 117 rows and 117 unique paths.
- Registry minus handler: empty.
- Handler minus registry: empty.
- Registry minus contract: empty.
- Contract minus registry: empty.
- STRICT_DURABLE_COMMAND_ROUTES: 23 paths; every path exists in both registry and contract.
- All 23 strict routes currently resolve to Pydantic models with extra=forbid.
- Fourteen non-strict, automatically journaled routes use additive extra=allow models; this provides a real accepted-route path for deep evidence structures.
- Contract rows marked journaled=false suppress validation/exception journaling through handler_policy. Successful-response suppression remains payload-flag driven through data.suppress_command_journal, so metadata and result producers must stay aligned. Existing network tests cover the sensitive join paths; no current mismatch was demonstrated.
- The strict-route set is hand-maintained separately from command metadata. Current parity is correct, but the focused policy test samples six routes rather than proving all intended effect classes. This is a drift risk, not a current defect at these hashes.

routes_command.py correctly derives every POST handler from COMMAND_ROUTE_METHODS. contract_command.py correctly concatenates the five contract fragments and exports the expected aliases. No defect was found in either wrapper.

## Finding verification

### AUDIT-FIND-W01-001 — confirmed

Claim: strict mutations have no request-stable replay or duplicate-command guard.

Exact assigned-source evidence:

- handler.py lines 120-121 decides strict evidence and generates a fresh uuid.uuid4().hex for each accepted request.
- handler.py lines 122-148 durably appends accepted evidence, then injects the new server ID into the body.
- handler.py line 149 invokes the mutation with no caller-ID lookup, route/payload fingerprint comparison, in-progress reservation, or terminal replay branch.
- command_journal.py lines 49-68 only summarize, prepend, bound, save, and mirror entries. No reservation or identity lookup exists.
- A precise production search found no X-MediaPipeline-Command-ID handling and no strict_command_fingerprint, reserve_strict_command, or complete_strict_command implementation under src.

Executed evidence:

- The 12-test command-replay adversarial module completed with 11 failures and 1 error.
- Simultaneous same-ID/same-payload requests mutated twice instead of once.
- Same-ID/different-payload requests mutated twice instead of conflicting.
- Lost-response retry and restart retry each mutated twice.
- Cross-route command-ID reuse returned HTTP 200 instead of 409.
- The caller-supplied IDs were replaced with fresh 32-hex server IDs.
- CommandJournal has no reserve_strict_command method or injected clock/identity-retention implementation.

Existing safeguards remain meaningful but do not close the defect: token/origin checks, strict payload models, boolean confirmations, accepted-before-mutation persistence, and some domain-specific process guards establish authorization and reduce selected races. They do not provide uniform request delivery idempotency or terminal replay across all 23 strict routes.

Disposition: confirmed, P1, high confidence.

### AUDIT-FIND-W01-002 — confirmed with correction

Claim: mutation exceptions leave accepted strict commands without linked terminal or indeterminate evidence.

Exact assigned-source evidence:

- handler.py line 149 dispatches the mutation.
- handler.py lines 150-169 create strict terminal evidence only after a normal return.
- handler.py lines 171-179 catch a dispatch exception through the generic route-exception path.
- The generic write at handler.py lines 174-178 does not use strict=True and does not invoke the indeterminate-marker adapter.
- handler_policy.py lines 127-155 builds local_api.route_exception data with path, status, error_id, and code, but no evidence_phase, journal_durability, or canonical command_id.
- command_journal_policy.py lines 105-110 separately copies the request into the summarized entry.

Independent correction to the original wording:

handler.py line 148 injects _command_id into the validated request before dispatch, and line 176 passes that body to generic exception journaling. A temporary HTTP probe proved that local_api.route_exception request._command_id equals the accepted entry data.command_id. The generic entry is therefore correlatable by a nested request field. It is not completely ID-unlinked.

The defect still holds because that correlatable entry is not a strict terminal state:

- HTTP status was 500.
- History contained local_api.route_exception followed by pipeline.start accepted.
- The generic entry had no evidence_phase.
- The generic entry had no journal_durability.
- Its write was best-effort rather than strict.
- It cannot state whether a mutation failed before side effects, partially applied, or completed before raising.

The existing passing process-command test explicitly asserts this accepted-plus-generic-exception history shape. It does not establish a durable failed or indeterminate lifecycle state.

Disposition: confirmed, P1, high confidence, with the observed-behavior/evidence text corrected to acknowledge request-level ID correlation.

### W01-002 fail-safe extension — confirmed and should be merged

This is not a new root-cause ID because it violates the same accepted-command terminal-state invariant.

Exact evidence:

- handler.py lines 152-154 catches terminal strict-journal persistence failure after the mutation returned.
- handler.py lines 155-157 calls an optional _mark_command_evidence_indeterminate adapter.
- handler.py lines 158-168 sends an indeterminate 503 without checking whether the marker became durable.
- Supporting server.py lines 233-238 returns after logging when no lifecycle state root exists.
- Supporting server.py lines 239-246 catches and logs marker persistence exceptions rather than returning failure to the handler.
- The call to resolved state at server.py line 235 is outside that inner persistence try; a provider exception can escape into the generic route-exception branch.
- The broader test search found lower-level LifecycleLeaseStore marker tests but no direct LocalApiServer test proving marker failure is reported or fail-closed.
- The adversarial terminal-write test emitted “Critical command evidence is indeterminate but no lifecycle state root is available” and the subsequent retry performed a second mutation.

Impact: after a side effect and terminal-journal failure, the operator receives “do not retry” but the backend may have neither terminal journal evidence nor a durable indeterminate marker surviving restart. This is the same unsafe-retry/recovery ambiguity as W01-002.

Coordinator action: merge this evidence, safeguard gap, and missing tests into W01-002.

### AUDIT-FIND-W01-003 — confirmed

Claim: malformed command history is treated as empty, reports clean, and can be overwritten.

Exact assigned-source evidence:

- command_journal.py lines 125-132 catches OSError or JSONDecodeError, logs, and returns an empty list.
- command_journal.py lines 133-134 also treats a valid JSON document with the wrong top-level/entries shape as an empty valid history.
- command_journal.py lines 79-123 derives persistence health only from save and SQLite-mirror state; it has no load-error state.
- command_journal.py lines 136-174 serializes current memory and atomically replaces the configured path.
- Strict mode only fails on the new save at lines 137-185; it does not know startup authority was discarded.

Temporary corrupt-startup probe:

- loaded_count=0
- load_health_degraded=False
- load_json_status=not_attempted
- original_preserved_after_strict_record=False
- after_json_status=ok
- replacement_valid_json=True

The adversarial HTTP test independently returned HTTP 200 instead of the expected fail-closed 503 after malformed startup.

Atomic temporary-file replacement, fsync, strict save rollback, and degraded save/SQLite reporting are valid safeguards for new writes. They do not preserve or surface evidence discarded during load.

Disposition: confirmed, P1, high confidence. Expand the finding to include valid-JSON schema/shape corruption, not only JSON syntax errors.

### AUDIT-FIND-W01-004 — confirmed

Claim: depth limiting can persist sensitive mapping values in plaintext.

Exact assigned-source evidence:

- command_journal_policy.py lines 66-74 handles scalar values.
- At lines 75-76, the depth guard calls scalar_text on the entire value.
- Mapping key inspection and sensitive-key replacement occur later at lines 77-84.
- List recursion occurs at lines 85-86.
- command_journal_policy.py lines 103-110 applies this function to result data and request evidence.
- core/network/url_policy.py lines 41-52 stringifies free text and redacts URLs, bearer headers, and sensitive key=value assignments. It has no Python/JSON mapping-literal colon-value rule.

Accepted-route and persistence proof used only a synthetic fake secret and a temporary directory:

- Route: /api/settings/reload.
- The route’s additive EmptyCommandPayload accepted and preserved an arbitrary nested extra mapping.
- route_validation_preserved_extra=True.
- bounded_secret_present=True.
- json_secret_present=True.
- reloaded_secret_present=True.
- Persisted shape ended with d represented as the string {'password': 'AUDIT_FAKE_SECRET_W01_SR_4D91'}.

This proves request validation, command summarization, JSON persistence, and loaded-history sanitation all preserve the fake secret. SQLite receives the same summarized entry in command_journal.py lines 187-201, although no SQLite file was needed to establish the root cause.

Shallow sensitive-key redaction, network text patterns, size bounds, and secret-transfer failure suppression remain useful safeguards. None inspect a container after the depth guard has converted it to opaque text.

Disposition: confirmed, P2, high confidence. Change the finding disposition from needs-runtime-proof to confirmed.

## Per-file second-review notes

### handler.py

Every line was reviewed: authorization/origin gates, route lookup, strict validation ordering, accepted/terminal evidence, exception paths, serialization, automatic journaling, response writes, and strict evidence helpers.

Strengths:

- Host, origin, and token checks precede mutation.
- Strict validation precedes accepted evidence.
- Accepted evidence must persist before strict dispatch.
- Normal-return terminal evidence is correlated and strict.
- Internal exceptions are not returned raw.

Defects supported: W01-001, W01-002, and the W01-002 marker-durability extension.

### handler_policy.py

Every line was reviewed: strict route membership, response headers, bounded errors, validation/exception journal builders, and metadata-driven failure-journal policy.

Strengths:

- All 23 current strict paths are registered and contracted.
- Secret-transfer and join-cluster validation/exception journaling are suppressed.
- Generic internal exceptions expose only safe error IDs.

Defect supported: W01-002 lacks canonical terminal phase/durability in route_exception_journal_payload.

### routes_command.py

All 11 lines were reviewed. Its derived mapping exactly matches all 117 canonical command routes. No defect found.

### contract_command.py

All 37 lines were reviewed. Fragment aggregation yields 117 unique paths matching all POST handlers. No defect found.

### command_journal.py

Every line was reviewed: load, record, lock, bounds, health, atomic JSON save, retries, strict behavior, cleanup, and SQLite mirror.

Strengths:

- Bounded FIFO memory state.
- Same-directory temporary write, flush, fsync, and atomic replace.
- Strict save failure raises and restores the prior in-memory entries.
- SQLite mirror failure is non-authoritative and surfaced as degraded.

Defects supported: W01-001 append-only history and W01-003 fail-open corrupt load.

### command_journal_policy.py

Every line was reviewed: result detection, scalar/list/dict bounds, sensitive terms, recursive evidence, summaries, history output, loaded-entry sanitation.

Strengths:

- Shallow structured sensitive keys are consistently replaced.
- URL, bearer, and assignment text patterns are bounded and redacted.
- Nonfinite floats become strict-JSON-safe text.
- Loaded entries are bounded before operator display.

Defect supported: W01-004 depth-cap conversion occurs before container/key inspection.

## Validation evidence

### Passing focused regression suites

Command modules:

- tests.python.desktop.test_api_command_journal_policy
- tests.python.desktop.test_api_handler_policy
- tests.python.desktop.test_application_facade_local_api_process_commands
- tests.python.desktop.test_application_facade_core_contracts
- tests.python.desktop.test_api_command_contracts

Result: 74 tests ran in 3.707 seconds; overall status OK. The process-command suite intentionally logged the synthetic route-exception traceback that it asserts.

### Adversarial replay/corruption suite

Module: tests.python.desktop.test_command_replay_adversarial

Result: 12 tests ran in 6.087 seconds; 11 failures and 1 error. The nonzero result is expected evidence of the currently unimplemented replay/reservation and corrupt-history fail-closed invariants. It is recorded as AUDIT-ERR-W01-SR-001 rather than hidden.

### Static and synthetic checks

- Route/handler/contract equality: passed at 117/117/117.
- Contract duplicate paths: none.
- Strict-route registry/contract presence: 23/23.
- Production caller-ID/replay symbol search: no implementation matches.
- W01-002 dispatch-exception HTTP probe: reproduced 500 plus accepted/generic history and request-level ID correlation.
- W01-003 malformed-history probe: reproduced false-clean status and overwrite.
- W01-004 accepted-route JSON/reload probe: reproduced plaintext fake-secret persistence.
- Focused validation emitted no timeout.
- No real media, live operator state, credentials, or production release surface was used.

## Error and incident accounting

Worker-specific ledger:

docs/reviews/full-repository-audit-2026-07-20/workers/worker-01-backend-api-application-second-review-errors.jsonl

Recorded incidents:

- AUDIT-ERR-W01-SR-001: expected nonzero adversarial suite, 11 failures and 1 error.
- AUDIT-ERR-W01-SR-002: expected synthetic HTTP route exception and logger traceback.
- AUDIT-ERR-W01-SR-003: passing 74-test suite emitted its asserted synthetic error traceback.
- AUDIT-ERR-W01-SR-004: precise test-gap rg query returned an expected no-match before a broader handled search.
- AUDIT-ERR-W01-SR-005: the first final-ledger check identified four pre-v2 classification phrases; all were normalized to the canonical enum.
- AUDIT-ERR-W01-SR-006: a read-only schema inspection used a stale module path; `rg --files` found the active path and the retry succeeded.

None blocked coverage.

## Evidence gaps and recommended next tests

- Implemented-fix testing must use a caller-stable command identity and prove simultaneous duplicate, payload conflict, lost-response replay, restart replay, retention, and abandoned-reservation behavior.
- Dispatch-exception tests need explicit before-side-effect and after-side-effect hooks so failed versus indeterminate classification is evidence-based.
- Terminal journal failure tests must force no state root, state-root provider failure, marker write failure, and restart; the handler must know whether a durable block exists.
- Corrupt-history tests must cover malformed JSON, invalid UTF-8, wrong schema/version, wrong entries type, filtered invalid rows, permission denial, preservation/quarantine, and JSON/SQLite authority reconciliation.
- Redaction tests must cover depths 3-6, lists around mappings, every sensitive alias, accepted additive routes, JSON, SQLite, and loaded legacy evidence.
- A full validation run was not substituted for these focused checks, and no source-media mutation or real-media validation is required for these API/journal fixes.

## Final source-integrity statement

The six assigned source files were not edited. Their SHA-256 values were rechecked against the worker-01 baseline after evidence gathering. Only the independent second-review Markdown and worker-specific error JSONL are in this reviewer’s write scope.
