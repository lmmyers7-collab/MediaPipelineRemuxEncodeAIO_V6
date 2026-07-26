# Worker 02 independent configuration/settings attestation

Reviewer: `/root/validation_spine`  
First reviewer: `/root/coverage_universe`  
Scope: eight current-hash high-risk configuration/settings paths  
Result: independent line review complete; `AUDIT-FIND-W02-002`, `AUDIT-FIND-W02-003`, and `AUDIT-FIND-W02-004` confirmed; no new root-cause finding emitted

## Independence and scope

This pass was performed by a canonical agent identity distinct from the first reviewer. I read the generated summary for every assigned and directly controlling support file before opening exact source, then independently read every physical line of the eight assigned paths at the hashes recorded below. I did not treat the first-pass conclusions as proof: the preview mutation, partial-confirmation replay, Windows test failure, production-writer comparison, runtime unknown-key materialization, runtime-dump omissions, and concurrency behavior were re-executed or independently derived from current source.

| Path | SHA-256 | First-pass finding IDs | Independent disposition |
| --- | --- | --- | --- |
| `src/mediapipeline/core/config/authority_lock.py` | `4cea2d52711a827ca5d0b30a7792bc7ab609538d8daf3b5abeed9b9c343aba2a` | none | No new defect; cross-process lock/CAS evidence passed |
| `src/mediapipeline/core/config/file_io.py` | `a8fb7888d6eed414066150380f3ccec156dafdc4f818108bb848caf9c5d7158f` | `AUDIT-FIND-W02-004` | Confirmed; production writer is newline-stable, unlike the test double |
| `src/mediapipeline/core/config/load.py` | `15c0b6fe88ade008b937b151d8676d9628a11a10dfb9a1979e46e35fc167bf06` | none | No new defect |
| `src/mediapipeline/core/config/settings_store.py` | `e81e307d2ded0ecd866c906b580748d583662fecf5348d637fe85951ff569688` | `AUDIT-FIND-W02-002`, `AUDIT-FIND-W02-003`, `AUDIT-FIND-W02-004` | All confirmed |
| `src/mediapipeline/core/config/settings_patch_candidate_facade.py` | `23ad2ae07a81d6c6c8c43496bb02abf454625dc5504cb708671af991fb45158e` | none | No duplicate finding; prior sensitive-evidence and legacy-extra roots remain present |
| `src/mediapipeline/core/orchestration/settings_patch_facade.py` | `25fe92be19d2ed457340962aefe3fe2437520fe927d8a5bdfa2985cb90d48f80` | `AUDIT-FIND-W02-002`, `AUDIT-FIND-W02-003` | Both confirmed |
| `ops/pipeline/engine/config/config_schema.ps1` | `381b7b144080d898eefb480e8e8041adab8890ca700cd43a7b1d523bdbed510c` | none | No duplicate finding; unknown top-level keys are not rejected here |
| `ops/pipeline/engine/config/runtime_merge.ps1` | `e8d79570feeb612023b9b9ea8068ca6c8370e84e66608dc80bef49d02bbaec62` | none | No duplicate finding; nonreserved unknown keys still become script variables |

All eight hashes still matched the baseline immediately before artifact generation, and targeted `git status --short -- <path>` returned clean for every assigned source path.

## Independent finding dispositions

### `AUDIT-FIND-W02-002` — confirmed, P1

`SettingsPatchFacadeMixin.preview_settings_patch` advertises a no-write preview but calls `load_settings_authority`. For an existing JSON store, `_load_settings_authority_for_service_unlocked` unconditionally calls `_promote_envelope_and_projection`, which replaces/verifies the JSON store, active PSD1, projection manifest, backups, and last-good snapshots. The result constructor then hard-codes `writes_config: false`.

A fresh disposable probe established a JSON authority, deliberately drifted the PSD1, and called the production facade preview through the real store loader and newline-stable writer. The preview succeeded and reported `writes_config=false`, while the PSD1 SHA-256 changed from `6860f485daa8e2de7077b8448a44d89ee6fd90069842a1dd28e83ed5cb06799c` to `9fde1ce61fde8b7ace4d4d54883d66ba1c9fce6e30ea6f23b40147632e7187d3`, the manual drift was overwritten, and one projection write occurred during preview. The first-pass root cause and P1 severity are retained.

### `AUDIT-FIND-W02-003` — confirmed, P2

The save facade classifies idempotent replay before it calls `settings_save_review_confirmation_error`. Replay checks only current/candidate/request digests, then invokes `save_settings_authority` even though current authority already equals the candidate. The complete normal validator requires schema version, preview ID, base digest, authority digest, candidate digest, review-entry digest, and exact changed/removed lists.

A fresh disposable probe first durably applied a valid `VideoQuality` change, then retried with a forged partial confirmation containing only `authority_config_digest`, `candidate_config_digest`, and `request_digest`. The response was `ok=true`, `idempotent_replay=true`, and the authority saver was invoked once. The omitted fields were `base_config_digest`, `changed_keys`, `preview_id`, `removed_keys`, `review_entries_digest`, and `schema_version`; the replay response reported an empty changed-key list. The configuration value itself remained constrained to the already-durable value, so P2 remains proportionate.

### `AUDIT-FIND-W02-004` — confirmed, P2

The checked-in `_StoreDummyService.save_config_document` uses `Path.write_text` with platform newline translation, while production `atomic_write_text` opens with `newline=""`, flushes, fsyncs, retries replacement, and cleans the temporary file. On Windows, the direct module independently reproduced three `SettingsStoreError: Settings PSD1 projection verification failed after atomic replacement` errors out of seven tests. Replacing only the dummy writer in memory with production-like `atomic_write_text` behavior made all seven tests pass.

The named rollback test sets `fail_save` and raises before the dummy writes the PSD1, so it does not inject a failure at the later projection-manifest write its name implies. The import test likewise executes preview only despite claiming apply-confirmation coverage. The production transaction remains stronger than this test evidence; the finding is about unreliable and overstated regression coverage.

## Prior and coordinator finding reconciliation

- `AUDIT-FIND-W02-001` remains confirmed without duplication. A current-source comparison found 145 script-scope assignments and 150 dump names, with exactly 17 config-derived runtime assignments absent from the resolved dump: `AllowSubtitleHelperFallback`, `ConsecutiveRoundFailureBlockLimit`, `ConsecutiveRoundFailureProbeBackoffSeconds`, `InterruptedToolLogRetentionDays`, `LocalWorkerHeartbeatGraceSeconds`, `PauseFlagBlockSeconds`, `PauseFlagReviewSeconds`, `PendingPublishBacklogBlockThreshold`, `PendingPublishDeferredBlockThreshold`, `PendingPublishDrainBatchSize`, `PendingPublishDrainMode`, `PipelineDebugLogMaxBytes`, `QueueExecutionMaxRunnablePerRound`, `QueueLaunchSnapshotFreshnessSeconds`, `StateDbCompletedJobsMaxRows`, `StateDbMaintenanceIntervalSeconds`, and `StateDbWalReviewBytes`.
- `CSW-2026-07-09-SETTINGS-001` remains present/open. The candidate builder copies raw changes into `request_evidence`, accepts a real value for a registered sensitive key, and rejects only the literal `<redacted>` placeholder; response review entries are redacted later. This coordinator-owned root was not duplicated.
- `CSW-2026-07-09-SETTINGS-002` remains present/open. `legacy_extras` are merged into PSD1 projection, schema composition does not reject unknown top-level keys, and runtime merge materializes every nonreserved key. A direct no-write PowerShell probe produced `UnknownExists=true`, `UnknownValue=enabled`, retained `ErrorActionPreference=Stop`, and emitted the expected reserved-key warning. This coordinator-owned root was not duplicated.
- `CSW-2026-07-09-SETTINGS-003` is not a current reproducible lost-update defect at these hashes. All 11 real multiprocessing/CAS/timeout/crash/retry tests passed. The present lock, locked reread, digest comparison, and explicit conflict paths support the first pass's provisionally-fixed disposition; future changes still require high-risk concurrency validation.

## Controls that held

- Literal `confirm_save is True` is enforced before ordinary save mutation.
- The authority lock is OS-visible on Windows and POSIX and releases through the context manager.
- Save performs a locked reread, digest/CAS conflict check, serialization validation, PowerShell round-trip validation, atomic replacement, committed-artifact verification, and rollback on exception.
- Reserved PowerShell preference and automatic-variable names are denied with warnings.
- PSD1 quoting and load errors are bounded and explicit; no new parser injection or malformed-result acceptance issue was found.

## Validation evidence

| Command/evidence | Outcome |
| --- | --- |
| `python -m unittest tests.python.desktop.test_settings_store_concurrency -v` using bundled Python | PASS — 11/11 in 3.583s |
| `python -m unittest tests.python.desktop.test_application_facade_settings_patch -v` | PASS — 34/34 |
| Four-module policy/service/config-contract bundle | PASS — 39/39 in 1.524s after correcting one initially mistyped module path |
| `Invoke-ConfigKeyRegistryChecks.ps1` using bundled PowerShell | PASS — 206 keys, 166 current PowerShell files |
| `python -m unittest tests.python.desktop.test_settings_store -v` | FAIL — 4 passed, 3 errors; independently confirms `AUDIT-FIND-W02-004` |
| Same seven tests with the dummy writer replaced in memory by production-like `atomic_write_text` | PASS — 7/7 |
| Disposable production-like preview probe | CONFIRMED hidden preview mutation and false no-write evidence |
| Disposable partial-confirmation replay probe | CONFIRMED confirmation bypass and one no-op authority saver call |
| Direct runtime-merge no-write probe | CONFIRMED arbitrary nonreserved legacy-extra materialization while reserved preference remained protected |
| Runtime assignment/dump comparison | CONFIRMED the exact 17-key `AUDIT-FIND-W02-001` omission set |

Every nonzero command, output-truncation warning, missing expected output, and corrected invocation error encountered by this pass is recorded in `worker-02-config-settings-independent-errors.jsonl`. Failed setup/invocation attempts were not used as semantic evidence. No source media, operator authority, network service, or external system was touched; mutation probes used disposable temporary directories. Real-media validation is not required for this configuration-only independent review.

## Artifact disposition

- `worker-02-config-settings-independent-attestation.jsonl` contains eight current-hash attestations by `/root/validation_spine`, with exact first reviewer `/root/coverage_universe`, exact first-pass finding-ID sets, and canonical `confirmed` dispositions.
- `worker-02-config-settings-independent-findings.jsonl` is intentionally empty because this pass found no new root cause.
- The independent review is complete for all eight paths. Central gate completion must be derived from the attestation; no first-pass row should self-assert `second_review_status=complete`.
