# Worker 15 — Failure and Recovery Map

## Scope and result

This worker reconciled the current PowerShell failure/outcome registries with backend contracts, state schemas, handlers, recovery paths, logs/journals, and tests. It did not edit product source, generated navigation, the central audit maps, or another worker's coverage rows.

Artifacts:

- `worker-15-failure-recovery-map.jsonl` — 272 machine-readable join records.
- `worker-15-failure-recovery-findings.jsonl` — four schema-valid, source-backed findings.
- `worker-15-failure-recovery-errors.jsonl` — 18 command errors, test failures, no-match results, and confidence-affecting truncation warnings.
- This file — method, cross-layer interpretation, findings, and validation summary.

The registry snapshot is bound to:

- `ops/pipeline/engine/shared/failure_codes.ps1`: `be0c9f17cbb6cf89014c8a8805139ffb7edcc96ccaa4026926ba6305676c7de7`
- `ops/pipeline/tests/Unit/Invoke-FailureCodeRegistryChecks.ps1`: `6c56f02cb2509611bdf4ba59738957592c71abf407e9554eb27d7e1198f09819`
- `src/mediapipeline/core/kernel/contracts/pending_publish.py`: `a222be79ac0d88d9905185d73ac6051e3ef42ea03247139fd36900c5b695281d`
- `ops/pipeline/engine/publish/pending_manifest_store.ps1`: `71fe395a741430a49d118ca0a63833b4ec4c7d14368713f2c0bfbfb2fb7286c8`

## Machine-readable map shape

The JSONL contains four record types/scopes:

| Record type | Rows | Meaning |
| --- | ---: | --- |
| `registry_code` / failure namespace | 46 | Every row returned by `Get-MediaPipelineFailureCodeRegistry` |
| `registry_code` / outcome namespace | 215 | Every row returned by `Get-MediaPipelineOutcomeCodeRegistry` |
| `unregistered_emission` | 4 | Confirmed operational codes emitted by current source but absent from the outcome registry |
| `workflow_surface` | 7 | Cross-layer recovery joins required by the assignment |
| **Total** | **272** | One JSON object per line |

Shared codes intentionally have one row per namespace. This preserves the actual registry outputs and makes seven namespace-dependent metadata conflicts observable instead of collapsing them.

Every registered-code row includes:

- namespace, code, family, stage, trigger, retryability, severity, operator guidance, and registry handler;
- owning implementation sources;
- state, journal, and log evidence;
- recovery/retry/repair paths;
- test evidence with worker-15 execution status;
- source locations;
- shared-registry parity status and exact mismatched fields;
- linked current-audit finding IDs.

The four unregistered emissions are not counted among the 215 registered outcomes:

- `OUTPUT_HASH_MISSING`
- `SIDECAR_HASH_INVALID`
- `SIDECAR_SIZE_INVALID`
- `OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED`

The first three are reported by the repository's registry test. The fourth is a live fail-closed verifier result that the current scanner misses because it appears in a snake_case `error_code` field.

## Registry universe

### Failure registry

| Family | Codes |
| --- | ---: |
| `source_media` | 13 |
| `encode` | 11 |
| `remux` | 10 |
| `native_tool` | 6 |
| `encode_cpu` | 5 |
| `output` | 1 |
| **Total** | **46** |

Thirty-seven rows are retryable warnings. Nine are nonretryable errors.

### Outcome registry

| Family | Codes |
| --- | ---: |
| `subtitle` | 49 |
| `source_media` | 45 |
| `encode` | 43 |
| `publish` | 22 |
| `remux` | 17 |
| `generic_failure` | 13 |
| `encode_cpu` | 7 |
| `process_lifecycle` | 7 |
| `audio` | 6 |
| `non_failure_outcome` | 4 |
| `destination_naming` | 2 |
| **Total** | **215** |

The outcome registry has 176 retryable warnings, 35 nonretryable errors, and four informational non-failure outcomes.

## Evidence chain

The common failure chain is:

```text
PowerShell stage/tool/verification result
  -> canonical ErrorCode + classification
  -> source-bound failure marker and round failure artifact
  -> ProcessFileResult/local worker result
  -> failure_recorded runtime event
  -> backend retry/operator-guidance projection
  -> resolution journal acknowledge/start/complete/waive/resolve/reopen
```

Publish and lifecycle flows add independent durable evidence:

```text
Pending Publish:
park intent -> hash-bound manifest -> drain attempt/transaction phases
-> partial/hash/sidecar/reveal/completion proof -> completed sidecar/manifest -> cleanup

Process/Network:
strict command -> ActiveJobs/lifecycle lease or coordinator claim
-> heartbeat/result/done/reclaim evidence -> queue terminal/retry decision
-> cleanup, quarantine, recovery, or operator review
```

The frontend is not a recovery authority. It displays backend state, collects strict confirmations, and invokes backend routes. Path trust, manifest qualification, queue mutation, process identity, repair safety, and publish policy remain backend/PowerShell responsibilities.

## Required recovery surfaces

| Workflow | Trigger and authority | Recovery rule | Audit result |
| --- | --- | --- | --- |
| Pending publish park/drain | `pending_push_manifest.v1`, transaction phase, hash/sidecar proof, drain summary | Drain only current, trusted, drainable, collision-free manifests below retry limit; repair stale attempts with exact proof | Safety/fault suites passed; repair-then-drain integration fails due W15-001; three trust codes are unregistered |
| Rename undo | Backend-owned `rename_undo.v1` manifest and strict `confirm_undo` | Preflight root, source/destination, collision, duplicate target, metadata pairing; undo reverse order once | Targeted tests passed; existing W01 strict replay/terminal-evidence findings still apply |
| Process crash/orphan cleanup | ActiveJobs, lifecycle lease, PID/cwd/cmdline proof, heartbeat/result | Mark only definitely dead/mismatched records orphaned; ambiguous identity stays blocking; auto-resume only no-media/plan-only work | ActiveJobs and lifecycle tests passed |
| Queue claims/results | Exact job/worker/source identity, coordinator in-flight registry, worker pending-done state | Persist failed done/release reports; reclaim into quarantine; accept exact late terminal evidence; remove terminal rows, bounded-retry others | Network crash/done tests passed |
| Repair/reconcile | Backend dry-run, exact fingerprint, candidate-only diff, `confirm_apply=true`, strict journal | Backup metadata, validate exact paths/contracts, roll back mutation or journal failure | Dry-run/apply tests mostly passed; one deterministic repair/drain defect |
| Strict command failures | Accepted and terminal command journal evidence keyed by command ID | Reject before mutation if accepted evidence cannot persist; indeterminate means do not retry/close until reconciliation | Policy tests passed; W01-001 through W01-004 remain the authoritative strict-command defects |
| Fail-closed media verification | Duration, video topology, audio/subtitle track plan, HDR, Dynamic HDR, quality proof | Any unresolved mismatch returns a terminal failure/review before publish | Media and track verification checks passed; one emitted verification code is absent and scan-blind |

## Findings

### AUDIT-FIND-W15-001 — P1

The Python current pending-manifest contract accepts missing `output_sha256`, and orphan reconcile writes such a manifest with `applied=true`. PowerShell requires SHA-256 proof before automatic drain. The bundled end-to-end test reproduced a successful strict repair followed by a zero-exit drain that created no output, twice.

The drain remains fail-closed, so this is not a source-corruption result. It is a broken recovery contract and misleading successful mutation result.

### AUDIT-FIND-W15-002 — P2

`OUTPUT_HASH_MISSING`, `SIDECAR_HASH_INVALID`, and `SIDECAR_SIZE_INVALID` are current Pending Publish trust outcomes without registry metadata. The authoritative registry check is red on all three.

### AUDIT-FIND-W15-003 — P2

Seven of the 46 shared failure/outcome codes have conflicting metadata:

| Code | Conflict |
| --- | --- |
| `ENCODER_UNAVAILABLE` | `native_tool` vs `encode` family |
| `FFMPEG_FAILED` | family, stage, trigger, handler |
| `FFMPEG_INVALID_ARGUMENT` | family, stage, trigger, handler |
| `FFMPEG_STOPPED` | family, stage, handler |
| `FFMPEG_TIMEOUT` | family, stage, handler |
| `OUTPUT_DISK_FULL` | `output` vs `publish` family |
| `SYSTEM_OUT_OF_MEMORY` | family, stage, trigger, handler |

Retryability and severity agree, but code-keyed grouping and ownership do not.

### AUDIT-FIND-W15-004 — P2

The emitted-code scan omits current prefixes including `DYNAMIC`, `DOVI`, `DESTINATION`, and `LOCAL`, and its line prefilter omits `error_code` / `reason_code`. It therefore misses `OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED`, even though encode/remux verification passes that code into a source failure record and blocks publish.

## Validation

| Command/suite | Result |
| --- | --- |
| `Invoke-FailureCodeRegistryChecks.ps1` | **FAIL** — three emitted pending trust codes missing from registry |
| `Invoke-FailureStateIdentityChecks.ps1` | PASS |
| `Invoke-MediaVerificationSafetyChecks.ps1` | PASS |
| `Invoke-MediaTrackOutputVerificationChecks.ps1` | PASS |
| `Invoke-PendingPublishSafetyChecks.ps1` | PASS |
| `Invoke-PendingPublishTransactionFaultInjectionChecks.ps1` | PASS, including all park/drain seams, collision, idempotency, rollback, corrupted manifest, and tampered sidecar cases |
| Bundled Python targeted suite across 15 modules | **190 passed, 1 failed, 13 subtests passed** |
| Isolated repair-then-drain retry | **FAIL reproduced** |
| Custom map/schema check | PASS — 272 rows; exact 46/215/4/7 split; 261 unique namespace/code keys |
| Repository finding/error schema validation | PASS — no worker-15 issues |

The Python run covered failure markers/retry projection, Pending Publish, rename, ActiveJobs/lifecycle, network crash/done handling, repair/reconcile, and command journal/handler policy. Its sole failure is the W15-001 end-to-end repair/drain case.

No real media was processed. Source mutation, production publish, and product/source edits were outside this worker's scope.

## Error ledger

Eighteen incidents are recorded:

| Classification | Count |
| --- | ---: |
| Informational warning | 9 |
| Environment/setup issue | 5 |
| Expected negative-path result | 1 |
| Test failure | 3 |

Nine informational warnings are output-truncation or broad-worktree finalization events; each was recovered with bounded reads, exact-path checks, or mechanical registry extraction. The three test-failure records represent two root causes: the registry-completeness failure and the deterministic repair-then-drain failure plus its isolated reproduction.

## Handoff priorities

1. Reconcile the Python and PowerShell pending-manifest contracts without weakening SHA-256 fail-closed drain policy.
2. Register the three pending trust codes and `OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED`.
3. Replace the partial emitted-code regex with structured or comprehensive enforcement.
4. Collapse shared-code metadata to one canonical table and add exact parity tests.
5. Rerun the registry check and the failing repair-then-drain integration before treating recovery mapping as green.
