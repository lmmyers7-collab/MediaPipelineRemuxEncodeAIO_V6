# Current-misc operational independent review

Reviewer: `/root/current_misc_delta_independent`

First reviewer: `/root/w01_static_completion`

Current audited HEAD: `2494bea1fd6280f41bec3f56e21b8bd98dd20829`

Scope: existing `AUDIT-FIND-W01-017`, `018`, `019`, `021`, `023`, `024`, and `025` only, plus exact path-local ledger reconciliation.

This pass is restricted to local correctness and reliability: registry durability and recovery, concurrent rollback, duplicate-work prevention, claim routing stability, and process containment. It does not expand authentication, authorization, secret handling, replay, path-trust, or broader cybersecurity analysis. No product, generated, central-ledger, or change-packet file was edited, and no network request, external system, real media, or launched media process was used.

## Exact-current coverage

The ten attested source files were read completely after their generated summaries: 7,357 physical source lines plus 205 summary lines. Two required routing/done callers, `worker_http.py` and `worker_claims.py`, were also read completely (398 lines), and focused test sections were inspected.

| Path | Lines | SHA-256 | Path-local findings |
| --- | ---: | --- | --- |
| `src/mediapipeline/desktop/network/registry_persistence.py` | 297 | `fcb51582e70f46a90c5fb757cc71e16fb3d8191ab3c7c065865207493142b4c0` | W01-017, W01-018 |
| `src/mediapipeline/desktop/network/registry_recovery.py` | 357 | `7ac0e1db234697acc66c577c034b76288f00dab30b7f114eb1bf34f95824435c` | W01-019, W01-020 |
| `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | 906 | `dccc069793b13c4e364843f869bf3dad3497e26e9a171d2211f5d6b9c359954d` | W01-019, W01-020, W01-023 |
| `src/mediapipeline/desktop/network/coordinator_queue.py` | 594 | `fadce5dbdaff86530d2ffd6dadbd5fed947e7b823f7e07ded884d3a2815f84a5` | W01-021, W01-023 |
| `src/mediapipeline/desktop/network/use_cases/done_outcome.py` | 239 | `3f3a0687e4e1fe77c2371a7fdb5f94ba0bae8376fb6f5d7f7be8724b52d93bb8` | W01-021 |
| `src/mediapipeline/desktop/network/rerun_claims.py` | 2,772 | `6edb11218e9d84f565e0b0cdc32a45ce0d1c8697f3092af1c6a8a0f340f897bc` | W01-022, W01-023, W01-029 |
| `src/mediapipeline/desktop/network/worker.py` | 600 | `8cf8b420055193948ad55d061c35cbfa3a29384318697e50510ead95041fca7a` | W01-024 |
| `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | 1,007 | `d1d97be684a44ce45e533b799148a482c184dfac7004fafe18b9e8c9abcbff86` | W01-008, W01-022, W01-024 |
| `src/mediapipeline/desktop/network/worker_parts/reporting.py` | 71 | `5dc0549f89fb9d3370c62f63de2329035a766108aabdc107a733171c99b4dd3a` | W01-025 |
| `src/mediapipeline/desktop/network/worker_loops.py` | 514 | `4103b102bc6be64145482463d9a9536801bacabf0dd6d4cfc2e661204d269266` | W01-025 |

An exact Git-tree join counted 6,499 paths at the audited HEAD. All ten paths are present, clean, byte-identical to their Git blobs, and match both the first-pass hashes and generated-summary source hashes.

## Independent dispositions

All seven assigned P1 findings remain `confirmed`:

- W01-017: a controlled save interleaving persisted the older captured snapshot after the newer save, dropping the later in-memory claim from disk.
- W01-018: a two-job file with one malformed active job returned `True` from `load()` while recovering only one job.
- W01-019: restoring an earlier whole-registry snapshot erased an unrelated post-snapshot claim and resurrected the target job.
- W01-021: coordinator-local `mark_done()` removed the active job before persistence; an injected save failure raised while the job remained absent.
- W01-023: an injected batch-state write failure occurred after registry rollback, leaving the registry unclaimed while the durable rerun row remained `claimed`.
- W01-024: with an active job present, hot-applying a coordinator URL redirected the next heartbeat to the new route; the claim has no pinned coordinator affinity.
- W01-025: a reclaimed heartbeat plus callback-scheduler failure exited heartbeat processing without invoking the process-abort callback.

The exact path-local sets also include W01-008, W01-020, W01-022, and W01-029, whose central dispositions remain `confirmed`. W01-008 and W01-022 were reconciled as operational evidence dependencies. W01-020 and W01-029 were included only to keep the machine join exact; this pass did not expand their auth/path-trust framing.

No distinct new finding was opened.

## Validation

- Isolated bundled-Python seven-finding probe: all expected-defect assertions passed in temporary state.
- `test_network_inflight_registry`, `test_network_coordinator_http`, and `test_network_workflow`: 98 passed.
- `test_network_rerun_claims`: 42 passed.
- `test_network_lifecycle_fixes` and `test_network_protocol_runtime`: 52 passed.
- `test_network_done_release` and `test_network_worker_runtime`: 64 passed.
- Total focused regressions: 256 passed.
- Generated summary/source joins: 10/10 matched; 7,357 source lines and 205 summary lines reconciled.
- Current tracked universe: exactly 6,499 paths; 10/10 attested paths match HEAD Git bytes and have clean target status.

The passing suites establish current intended behavior and adjacent regression stability; they do not negate the isolated failure interleavings. Existing tests either omit those interleavings or explicitly accept/log the partial failure behavior.

## Error accounting

`worker-current-misc-operational-independent-errors.jsonl` records every command issue and expected error-bearing probe: one clipped broad search, six corrected query/orchestration mistakes, and seven expected negative-path reproductions. All are closed, none blocks coverage, and no failed command changed repository state.

Representative real-media validation was not required because this was a read-only audit-evidence pass and did not exercise or change media policy or filesystem mutation behavior.
