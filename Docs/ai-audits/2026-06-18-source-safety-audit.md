# Source-Safety Audit

Date: 2026-06-18
Change packet: MP-CHANGE-2026-0618-009
Audit type: evidence-first static audit plus targeted existing tests

## Outcome

No confirmed path was found that deletes, overwrites, renames, or transcodes original source media during normal pipeline operation. The reviewed implementation keeps source media read/probe/copy-only by default, with intentional mutation surfaces routed through backend-owned commands, explicit confirmations, path-boundary checks, and rollback or park behavior.

This is not proof that every future source path is safe. The residual risks are listed below as evidence gaps and follow-up work.

## Scope

In scope:

- Source scan and queue planning.
- Copy-to-scratch and scratch cleanup.
- Remux/encode publish completion.
- Pending publish park and drain.
- CSV rerun defaults.
- Rename preview and apply.
- Final-library promotion.
- Failure-marker cleanup.
- WebView/Tauri command submission boundaries.
- Destructive-operation inventory across Python, PowerShell, Rust, and WebView code.

Out of scope:

- Code fixes or behavior changes.
- New mutation routes, schemas, commands, UI, config, or media policy.
- Real-media processing.
- Production source, scratch, output, or final-library paths.

## Source-Safety Invariant

The active invariant is:

> Source media must be read, probed, or copied only unless a specifically named, intentionally enabled safe-delete policy is active. Frontend code must not own filesystem mutation or media policy.

Primary sources for this invariant:

- `AGENTS.md`: source mutation is forbidden by default; backend owns media policy.
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`: source deletion, scratch-copy behavior, pending publish drain, and strict command handling are high-risk boundaries.
- `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`: command authority and frontend limits.
- `docs/inventories/API_ROUTE_INVENTORY.md`: public route surface and route tests.
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`: command ownership, mutation class, confirmation fields, and criticality.
- `docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`: rename safety coverage and known gaps.

## Evidence Checked

High-risk implementation files reviewed:

- `ops/pipeline/engine/storage/scratch_copy.ps1`
- `ops/pipeline/engine/publish/pending_drain_transaction.ps1`
- `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1`
- `ops/pipeline/engine/shared/path_helpers.ps1`
- `src/mediapipeline/core/paths/layout.py`
- `src/mediapipeline/core/processes/source_path_policy.py`
- `src/mediapipeline/core/processes/pipeline_policy.py`
- `src/mediapipeline/core/processes/rerun_policy.py`
- `src/mediapipeline/core/rename/apply.py`
- `src/mediapipeline/core/final_library/promotion.py`
- `src/mediapipeline/core/final_library/facade.py`
- `src/mediapipeline/core/final_library/service.py`
- `src/mediapipeline/core/final_library/promotion_parts/planning.py`
- `src/mediapipeline/core/final_library/promotion_parts/transfer.py`
- `src/mediapipeline/core/final_library/promotion_parts/cleanup.py`
- `src/mediapipeline/core/api/commands.py`
- `src/mediapipeline/core/api/commands_final_library.py`
- `tests/python/desktop/test_final_library_promotion.py`

Searches included destructive and path-sensitive APIs such as `Remove-Item`, `Move-Item`, `Copy-Item`, `robocopy`, `.unlink`, `.replace`, `.rename`, `shutil.copy2`, `shutil.rmtree`, `Remove-`, `Delete`, `rename`, `safe delete`, `stage_mode`, `original_mode`, `return_mode`, `confirm_apply`, and `confirm_promote`.

## Destructive-Operation Inventory

| Operation class | Main reviewed locations | Classification | Source-safety result |
| --- | --- | --- | --- |
| Source-to-scratch copy | `scratch_copy.ps1`, `Invoke-RerunCsv.ps1` | Source media read/copy | Uses copy-only staging. Source identity, size, and modified time are checked before reuse or rerun. Cleanup targets scratch or staging artifacts only. |
| Scratch cleanup | `scratch_copy.ps1` | Scratch | Cleanup is bounded to `LocalBase` processing containers and guarded by `Test-MediaPipelinePathBoundarySafe`. |
| Publish partial/reveal cleanup | PowerShell publish engine files | Output or pending publish | Partial and sidecar cleanup targets publish artifacts, not source roots. Pending drains leave parked artifacts for retry on failure. |
| Pending drain cleanup | `pending_drain_transaction.ps1` | Pending publish | Local parked media, sidecars, and manifest are removed only under the pending artifact root after trusted-manifest and published-copy checks. |
| Rename apply | `src/mediapipeline/core/rename/apply.py` | Intentional filesystem rename | Backend rebuilds the operation plan, requires confirmation, checks source and destination boundaries, blocks duplicate/existing destinations, and rolls back completed operations on failure. |
| Final-library promotion copy/cleanup | `promotion_parts/planning.py`, `transfer.py`, `cleanup.py` | Publish-output and final-library | Plans only files under publish root, copies transactionally, verifies before cleanup, and deletes only verified publish-root files when cleanup is explicitly enabled. |
| Queue and settings state writes | Python queue/settings services and inventories | State | Queue state and settings persistence are backend-owned state mutations, not source media mutation. |
| WebView string replacement and DOM operations | `apps/desktop/webview/static/**` | Frontend UI only | Many `replace` hits are JavaScript string/DOM operations. WebView submits API commands and does not directly mutate filesystem paths. |
| Test and tooling cleanup | `tests/**`, `ops/scripts/**`, developer tools | Fixture/tooling | Cleanup is limited to test temp directories, generated docs, release artifacts, or tool-owned state. |

No destructive-operation hit was confirmed to target original source media under the normal pipeline flow.

## Flow Trace

| Flow | Backend owner and path authority | Frontend authority and request fields | Gates, rollback, or park behavior | Existing evidence |
| --- | --- | --- | --- | --- |
| Source scan and queue planning | `source_path_policy.py`, queue facade, PowerShell scan helpers. Source roots come from configured `SourceMovies`, `SourceTV`, and enabled library profile roots. | Frontend can request scan/queue actions through Local API commands, but cannot resolve arbitrary media policy or mutate paths directly. | Queue source validation requires absolute paths under configured source roots, existing files, supported suffixes, and backend-owned state writes. | Route inventories, command ownership matrix, `tests/python/desktop/test_queue_source_path_policy.py`. |
| Copy-to-scratch and scratch cleanup | `scratch_copy.ps1` owns scratch identity under `LocalBase` processing directories. | Frontend has no scratch path authority. | Scratch names reject rooted, parent, separator, and invalid leaf names. Cleanup is bounded under processing containers; source is copied with `robocopy` and never deleted. | Full source review of `scratch_copy.ps1`; PowerShell unit and reliability checks planned. |
| Remux/encode publish completion | PowerShell publish engine owns partial output, reveal, sidecars, and final publish decisions. | Frontend can start pipeline modes through backend commands, not construct FFmpeg output mutation directly. | Publish uses partial/reveal and sidecar rollback patterns. Unsafe final roots route to pending publish park instead of direct final output. | Boundary register, publish summaries, command ownership matrix, publish/pending tests planned. |
| Pending publish park and drain | `pending_drain_transaction.ps1` owns trusted-manifest checks, copy to server partial, reveal, and local pending cleanup. | Frontend can request drain through backend-owned command paths only. | Missing local payload marks manifest for review. Sidecar or reveal failure removes partial work and leaves parked local artifacts for retry. Cleanup is under the pending artifact root only. | Full source review of `pending_drain_transaction.ps1`; pending publish tests planned. |
| Rerun defaults | `rerun_policy.py` and `Invoke-RerunCsv.ps1` own rerun policy. | Local API and CSV entrypoint accept only safe default modes for rerun source handling. | Rerun defaults are `stage_mode=copy`, `original_mode=keep`, and `return_mode=park`. Source-mutating row overrides are rejected. | Full source review of `rerun_policy.py` and `Invoke-RerunCsv.ps1`; rerun policy tests planned. |
| Rename preview/apply | Rename backend owns preview planning and `apply.py` owns filesystem rename. | Frontend submits command payloads. Apply requires `confirm_apply: true`; frontend cannot execute rename locally. | Backend rebuilds plan, checks path boundaries, blocks duplicate or existing destinations, supports case-only rename, writes undo manifest, and rolls back completed operations on failure. | Full source review of `apply.py`; rename inventories and tests planned. |
| Final-library promotion | `final_library` facade/service/planning/transfer/cleanup own promotion from publish root to destination root. | Frontend selects eligible row keys and must send `confirm_promote: true`; it does not provide arbitrary copy/delete plans. | Active work blocks apply. Promotion requires completed published rows under publish root, destination root planning, transactional verified copy, and optional cleanup only inside publish root. | Full source review of promotion files and `test_final_library_promotion.py`. |
| Failure-marker cleanup | Backend maintenance/process tooling owns markers and failure cleanup. | Frontend can request maintenance-style commands only through Local API contracts. | Reviewed evidence treats marker cleanup as state/tooling cleanup, not source media cleanup. This remains an evidence gap until each cleanup path is mapped to an allowlist. | Route inventories and destructive-operation search. |
| WebView/Tauri command boundaries | Local API command registry and Tauri backend lifecycle own command submission. | WebView calls API routes; Tauri manages backend lifecycle. Neither should implement filesystem mutation or media policy. | Public inventories show repair/reconcile mutation routes absent. Mutation commands require backend contracts and confirmations. | `commands.py`, route inventories, frontend mutation-boundary tests planned. |

## Findings

### Blocker

None confirmed.

### High

None confirmed.

### Medium

None confirmed as a source-media safety defect.

### Low

None confirmed.

### Evidence Gaps

1. Failure-marker and maintenance cleanup paths were reviewed by destructive-operation search and route inventories, but not every individual cleanup target was manually traced to a written allowlist in this audit.
2. Rename safety has known residual gaps already documented in `docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`: WorkerSourcePathMap path rewriting, undo manifest verification, real filesystem rename coverage in CI, and active-pipeline lock scenarios.
3. Final-library promotion cleanup is intentionally destructive when `FinalLibraryPromotionCleanupAfterVerified` is enabled. Current evidence shows it is bounded to publish root, but any future change to publish-root planning or cleanup defaults should rerun focused tests and real-media validation.
4. Browser smokes are optional in this audit. If unavailable or not run, frontend evidence rests on static WebView tests and route inventory checks rather than live browser interaction.
5. `ops/pipeline/tests/Invoke-UnitChecks.ps1` was requested by the audit plan but is not present in the current tree. The `Unit` test folder exists, but the wrapper entrypoint is unavailable.
6. `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` currently fails in media route selection: an unknown-height movie over 22 Mbps was expected to encode but returned remux. This does not demonstrate source mutation, but it prevents a clean reliability-regression gate for this audit.
7. The worktree contains unrelated dirty changes. This audit did not absorb or revert those changes, so source-safety conclusions are based on reviewed current files plus recorded inventories, not on a clean baseline.

## Follow-Up Only

These are recommendations, not implemented changes:

- Add a generated destructive-operation allowlist that maps every `Remove-*`, `Move-*`, `Copy-*`, `.unlink`, `.rename`, `.replace`, and cleanup helper to one of: source, scratch, output, pending publish, state, fixture, tooling, or release artifact.
- Add a narrow test that asserts final-library cleanup refuses original configured source roots even when a malformed promotion row is supplied.
- Close the rename evidence gaps listed in `RENAME_SAFETY_TEST_INVENTORY.md`.
- Add a maintenance-cleanup route inventory section that names each cleanup root and whether it allows root deletion.

## Validation Status

No real-media validation was run for this docs-only audit.

- Passed: targeted Python/API unittests listed in the audit plan. The run covered 12 modules and 157 tests.
- Unavailable: `ops/pipeline/tests/Invoke-UnitChecks.ps1` is absent from the current tree, so the exact requested PowerShell unit wrapper could not be run.
- Failed: `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` failed in `Invoke-MediaRouteSelectionChecks.ps1` with `Unknown-height movie should use 1080p cap and encode over 22 Mbps. Expected 'encode' but got 'remux'.`
- Passed: `ops/pipeline/tests/Invoke-AdversarialForceKillEncodeChecks.ps1`; the check reported that a force-killed encode was not accepted as complete and the source remained queued.
- Passed: `ops/scripts/smoke/Test-LocalApiMaintenanceDryRunContractSmoke.ps1`; the smoke reported temporary-state-only dry-run boundaries.
- Passed: optional browser smokes `Test-WebViewBrowserHighRiskSmoke.ps1`, `Test-WebViewBrowserPendingDrainGuardSmoke.ps1`, and `Test-WebViewBrowserRenameSmoke.ps1`.

## Residual Risk Statement

The current evidence supports the claim that original source media is protected from default delete, overwrite, in-place transcode, unsafe rename, unsafe cleanup, and frontend-owned mutation. Residual risk remains in the missing unit-check wrapper, the failing media route reliability check, broad cleanup surfaces that do not yet have a generated allowlist, and future changes to media policy, publish/drain, rename, cleanup, or source path planning.
