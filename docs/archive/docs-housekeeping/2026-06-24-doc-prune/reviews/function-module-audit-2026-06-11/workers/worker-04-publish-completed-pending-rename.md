# Worker Review: worker-04-publish-completed-pending-rename

## Scope

Worker ID: `worker-04-publish-completed-pending-rename`

Assigned slice: completed output services, pending publish park/drain logic, publish reconciliation, sidecar/manifest handling, rename preview/apply/undo planning, and related backend DTO/policy surfaces where needed to determine exposure.

Review mode: review-only source audit. I did not fix code, refactor, commit, start the app, drain pending publish, rename files, mutate media/runtime state, or edit aggregate review files.

Required context read before source review:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` because this slice touches pending publish, output placement, sidecars, and rename mutation boundaries.

Summaries checked before source: generated summaries were checked for all 66 assigned files under `docs/generated/summaries/` before opening source files.

Ancillary exposure check, not counted as assigned coverage: `src/mediapipeline/core/api/commands_rename.py` and related rename tests were read to scope the rename authority finding against the Local API enrichment path.

## Coverage Ledger

Coverage result: complete for assigned W04 source slice, 66/66 assigned files reviewed at source level after generated summary checks.

PowerShell publish files reviewed:

- `ops/pipeline/engine/publish/pending_drain_transaction.ps1` - finding W04-001
- `ops/pipeline/engine/publish/pending_manifest_store.ps1` - no finding
- `ops/pipeline/engine/publish/pending_park_transaction.ps1` - finding W04-002 evidence
- `ops/pipeline/engine/publish/pending_publish_index.ps1` - no finding
- `ops/pipeline/engine/publish/pending_push.ps1` - finding W04-002 evidence
- `ops/pipeline/engine/publish/pending_repair.ps1` - no finding
- `ops/pipeline/engine/publish/pending_sidecar_transactions.ps1` - no finding
- `ops/pipeline/engine/publish/pending_transactions.ps1` - no finding
- `ops/pipeline/engine/publish/publish_completion.ps1` - findings W04-001 and W04-002
- `ops/pipeline/engine/publish/publish_completion/context_builders.ps1` - no finding
- `ops/pipeline/engine/publish/publish_partial.ps1` - finding W04-001
- `ops/pipeline/engine/publish/publish_result.ps1` - finding W04-002 evidence
- `ops/pipeline/engine/publish/publish_sidecars.ps1` - no finding
- `ops/pipeline/engine/publish/sidecar.ps1` - no finding

Completed Python files reviewed:

- `src/mediapipeline/core/completed/__init__.py` - no finding
- `src/mediapipeline/core/completed/backfill.py` - no finding
- `src/mediapipeline/core/completed/facade.py` - no finding
- `src/mediapipeline/core/completed/manifest.py` - no finding
- `src/mediapipeline/core/completed/open_facade.py` - no finding
- `src/mediapipeline/core/completed/open_policy.py` - no finding
- `src/mediapipeline/core/completed/policy.py` - no finding
- `src/mediapipeline/core/completed/service.py` - no finding
- `src/mediapipeline/core/completed/trust_fields.py` - no finding
- `src/mediapipeline/core/completed/validation_state.py` - no finding

Publish Python files reviewed:

- `src/mediapipeline/core/publish/__init__.py` - no finding
- `src/mediapipeline/core/publish/file_io.py` - no finding
- `src/mediapipeline/core/publish/pending_drain_confidence.py` - no finding
- `src/mediapipeline/core/publish/pending_facade.py` - no finding
- `src/mediapipeline/core/publish/pending_format.py` - no finding
- `src/mediapipeline/core/publish/pending_manifest.py` - no finding
- `src/mediapipeline/core/publish/pending_manifest_rows.py` - no finding
- `src/mediapipeline/core/publish/pending_open_policy.py` - no finding
- `src/mediapipeline/core/publish/pending_paths.py` - no finding
- `src/mediapipeline/core/publish/pending_policy.py` - no finding
- `src/mediapipeline/core/publish/pending_policy_parts/__init__.py` - no finding
- `src/mediapipeline/core/publish/pending_policy_parts/status_rules.py` - no finding
- `src/mediapipeline/core/publish/pending_policy_parts/trust_fields.py` - no finding
- `src/mediapipeline/core/publish/pending_recovery.py` - no finding
- `src/mediapipeline/core/publish/pending_results.py` - no finding
- `src/mediapipeline/core/publish/pending_rows.py` - no finding
- `src/mediapipeline/core/publish/pending_service.py` - no finding
- `src/mediapipeline/core/publish/reconciliation_facade.py` - no finding
- `src/mediapipeline/core/publish/reconciliation_policy.py` - no finding

Rename Python files reviewed:

- `src/mediapipeline/core/rename/__init__.py` - no finding
- `src/mediapipeline/core/rename/apply.py` - no finding
- `src/mediapipeline/core/rename/apply_results.py` - no finding
- `src/mediapipeline/core/rename/apply_runner.py` - no finding
- `src/mediapipeline/core/rename/cleaning_policy.py` - no finding
- `src/mediapipeline/core/rename/constants.py` - no finding
- `src/mediapipeline/core/rename/contracts.py` - no finding
- `src/mediapipeline/core/rename/discovery.py` - no finding
- `src/mediapipeline/core/rename/facade.py` - finding W04-003
- `src/mediapipeline/core/rename/file_io.py` - no finding
- `src/mediapipeline/core/rename/filename_preview.py` - no finding
- `src/mediapipeline/core/rename/movie.py` - no finding
- `src/mediapipeline/core/rename/path_authority.py` - finding W04-003
- `src/mediapipeline/core/rename/plan_policy.py` - no finding
- `src/mediapipeline/core/rename/planner.py` - no finding
- `src/mediapipeline/core/rename/policy.py` - no finding
- `src/mediapipeline/core/rename/preview.py` - no finding
- `src/mediapipeline/core/rename/preview_policy.py` - no finding
- `src/mediapipeline/core/rename/preview_runner.py` - no finding
- `src/mediapipeline/core/rename/service.py` - no finding
- `src/mediapipeline/core/rename/tv.py` - no finding
- `src/mediapipeline/core/rename/tv_folder.py` - no finding
- `src/mediapipeline/core/rename/utils.py` - no finding

## Findings Summary

| ID | Severity | Area | Summary |
| --- | --- | --- | --- |
| W04-001 | High | Publish sidecar carry-forward | A pre-existing final `.pipeline.json` can be deleted if sidecar backup fails and later sidecar write or media reveal fails. |
| W04-002 | Medium | Pending publish result proof | Deferred/output-space pending publish returns `OutputSizeBytes = 0` after successful park because size is read from the moved local path. |
| W04-003 | High | Rename authority boundary | Direct rename facade apply does not fail closed when configured media roots are absent; unscoped rows are review-only but not apply-blocking. |

## Detailed Findings

### W04-001 - High - Existing final sidecar can be deleted after backup failure and publish/reveal failure

File: `ops/pipeline/engine/publish/publish_partial.ps1`

Symbols/sections: `Backup-PublishSidecarForReveal`, `Restore-PublishSidecarAfterRevealFailure`

Evidence:

- `Backup-PublishSidecarForReveal` returns an empty string when copying an existing final sidecar backup fails: lines 24-41.
- `Restore-PublishSidecarAfterRevealFailure` restores only when `BackupPath` is non-empty and exists; otherwise it removes the current sidecar if present: lines 71-92.
- Immediate publish takes the empty-string backup result and proceeds to write a replacement sidecar before final reveal: `ops/pipeline/engine/publish/publish_completion.ps1` lines 212-217.
- Immediate publish then calls restore with the maybe-empty backup on sidecar-write failure and reveal failure: `ops/pipeline/engine/publish/publish_completion.ps1` lines 228-230 and 246-247.
- Pending drain uses the same backup, write, and restore pattern: `ops/pipeline/engine/publish/pending_drain_transaction.ps1` lines 228-230 and 243-244.

Impact:

If an output path already has a valid final sidecar and the backup copy is denied, locked, or otherwise fails, the publish/drain path logs a warning and continues. If the newly written sidecar or final media reveal later fails, restore receives no backup and deletes the current sidecar. That can erase the previous output proof even though final media was not safely committed, weakening completed/pending evidence and sidecar carry-forward. This is especially risky for publish reconciliation and operator trust because sidecar proof is one of the key final-placement signals.

Fix direction:

Make the backup result explicit rather than overloading empty string for "no existing sidecar" and "existing sidecar backup failed". For example return fields such as `HadExistingSidecar`, `BackupOk`, `BackupPath`, and `Error`. If an existing final sidecar cannot be backed up, fail closed before writing a replacement sidecar or final reveal. At minimum, the restore path should never delete a sidecar when an existing sidecar was known to exist but backup was unavailable.

Validation:

Add a PowerShell fixture that creates a final output sidecar, forces backup failure, allows replacement sidecar write, then forces sidecar-write failure or reveal failure. Assert the original sidecar remains intact, the final media is not revealed, pending park behavior remains safe, and completed/pending reconciliation still reports the prior sidecar proof.

### W04-002 - Medium - Deferred/output-space pending publish reports zero output size after successful park

Files: `ops/pipeline/engine/publish/publish_completion.ps1`, `ops/pipeline/engine/publish/pending_park_transaction.ps1`, `ops/pipeline/engine/publish/pending_push.ps1`, `ops/pipeline/engine/publish/publish_result.ps1`

Symbols/sections: deferred publish branch, output-space-deferred branch, `Invoke-PendingParkTransaction`, `Invoke-ParkPendingPush`, `New-PipelinePublishResult`

Evidence:

- Deferred publish parks the local output, then reads `$Paths.LocalOut` for size and casts that value into `OutputSizeBytes`: `publish_completion.ps1` lines 36-46.
- Output-space-deferred publish repeats the same pattern after parking: `publish_completion.ps1` lines 98-129.
- Parking moves the file from `$LocalOut` to the pending path before returning: `pending_park_transaction.ps1` line 244.
- The park transaction already has the accurate parked-file size in `OutputSize`: `pending_park_transaction.ps1` lines 255-258.
- The wrapper logs `output_size` in the pipeline event but returns only `$true`, dropping the transaction object: `pending_push.ps1` lines 331-382.
- `New-PipelinePublishResult` defaults/casts `OutputSizeBytes` as `[long]`, so a missing post-move `.Length` becomes zero: `publish_result.ps1` lines 4-27.

Impact:

A successful deferred or output-space-deferred publish can produce an accurate pending manifest and event but return a publish result with `OutputSizeBytes = 0`. Downstream process result evidence and operator diagnostics can then disagree with the parked manifest/disk payload. This does not appear to lose the parked output, but it creates manifest/result drift exactly on safety-sensitive pending-publish paths.

Fix direction:

Capture the local output size before the park transaction, or return the transaction object from `Invoke-ParkPendingPushWithTx3gSidecars`/`Invoke-ParkPendingPush` so the caller can use `transaction.OutputSize`. Avoid reading `$Paths.LocalOut` after the move. Keep the pending manifest, publish result, and pipeline event size fields sourced from the same proof.

Validation:

Extend pending-publish PowerShell tests with real temporary files for both `DeferredPublish` and output-space-deferred copy failure. Assert `OutputSizeBytes` equals the original/parked file length, matches the pending manifest `output_size`, and is propagated into process-result publish evidence.

### W04-003 - High - Direct rename apply does not fail closed when configured roots are absent

Files: `src/mediapipeline/core/rename/path_authority.py`, `src/mediapipeline/core/rename/facade.py`

Symbols/sections: `rename_authority_fields_for_source`, `annotate_rename_plan_path_authority`, `rename_plan_outside_configured_roots`, `apply_rename_selection`

Evidence:

- When no configured roots are supplied, `rename_authority_fields_for_source` returns `path_authority = "unscoped_operator_path"` and `path_authority_status = "review"`: `path_authority.py` lines 47-55.
- `annotate_rename_plan_path_authority` only adds warning/status downgrades for `outside_configured_roots`, not for `unscoped_operator_path`: `path_authority.py` lines 72-97.
- The apply blocker only returns rows where `path_authority == "outside_configured_roots"`: `path_authority.py` lines 100-105.
- `apply_rename_selection` checks confirmation, selected rows, row errors, and outside-root blockers before calling `apply_rename_path_plan`; unscoped rows are not blocked by this path: `facade.py` lines 101-129.
- `_build_rename_plan_from_request` gets configured roots solely from request metadata: `facade.py` lines 137-147.
- Current Local API command enrichment strips caller-owned backend keys and injects resolved configured roots before facade calls, which narrows exposure for `/api/rename/apply`: `src/mediapipeline/core/api/commands_rename.py` lines 17-39. However, the facade remains a backend mutation boundary and can be invoked directly by tests or future non-API callers.
- Tests cover configured outside-root blocking and API spoof rejection, but `rg -n "unscoped_operator_path" tests` returned no tests for absent roots.

Impact:

A direct backend facade caller with `confirm_apply: true`, selected sources, and no `_configured_media_roots` can rename files in an operator-supplied folder even though the authority layer says roots were unavailable and marks the row review-only. The lower-level rename primitive constrains each rename to the source file's parent directory, so this is not a cross-directory move bug, but it is still a fail-open configured-root authority gap for source-file mutation.

Fix direction:

Treat `unscoped_operator_path` as apply-blocking unless a separate explicit confirmation exists, or make facade apply derive configured roots from resolved backend configuration rather than trusting request metadata. Keep the existing Local API enrichment, but enforce the safety rule at the facade layer so future backend callers cannot bypass it.

Validation:

Add a direct facade test with `confirm_apply: true`, selected source outside configured roots, and no `_configured_media_roots`; assert the result is blocked and the file remains unchanged. Keep the existing API spoof tests to prove WebView/API callers still receive server-owned roots and undo manifest roots.

## Test Coverage Gaps

- No executable fixture appears to cover the sidecar backup-failure branch where a pre-existing final sidecar cannot be backed up and publish/drain later fails before reveal. Existing legacy checks are mostly text/pattern assertions for the presence of backup/restore helpers.
- Pending publish safety tests assert output-space-deferred mode and parked success, but I did not find a fixture assertion that `OutputSizeBytes` remains non-zero and matches the parked manifest after the local output has moved.
- Rename tests cover explicit outside-root blocking and Local API backend-key spoof rejection, but there is no direct facade absent-root test for the `unscoped_operator_path` branch.
- Pending repair/reconciliation has good read-model and UI diagnostic coverage, but representative real-media validation would still be required for any fix touching publish/drain/sidecar/media movement behavior.

## Boundary Risks

- W04-001 risks loss of existing sidecar proof next to final output during immediate publish or pending drain failure handling.
- W04-002 risks drift between process-result evidence and pending manifest/disk payload size on parked outputs.
- W04-003 is a backend rename mutation boundary gap at the facade layer, narrowed by current Local API enrichment but still unsafe as a reusable backend entry point.
- I did not observe source deletion paths in the reviewed publish/pending modules. Park/drain paths move pipeline-produced local outputs and pending payloads, not original source media.
- Pending drain trust checks in `pending_manifest_store.ps1` are conservative around output roots, source roots, LocalBase, pending root, sidecars, manifest state, and original local output. No additional drain-trust bypass was found in the assigned files.

## Files Reviewed With No Findings

- `ops/pipeline/engine/publish/pending_manifest_store.ps1`
- `ops/pipeline/engine/publish/pending_publish_index.ps1`
- `ops/pipeline/engine/publish/pending_repair.ps1`
- `ops/pipeline/engine/publish/pending_sidecar_transactions.ps1`
- `ops/pipeline/engine/publish/pending_transactions.ps1`
- `ops/pipeline/engine/publish/publish_completion/context_builders.ps1`
- `ops/pipeline/engine/publish/publish_sidecars.ps1`
- `ops/pipeline/engine/publish/sidecar.ps1`
- `src/mediapipeline/core/completed/__init__.py`
- `src/mediapipeline/core/completed/backfill.py`
- `src/mediapipeline/core/completed/facade.py`
- `src/mediapipeline/core/completed/manifest.py`
- `src/mediapipeline/core/completed/open_facade.py`
- `src/mediapipeline/core/completed/open_policy.py`
- `src/mediapipeline/core/completed/policy.py`
- `src/mediapipeline/core/completed/service.py`
- `src/mediapipeline/core/completed/trust_fields.py`
- `src/mediapipeline/core/completed/validation_state.py`
- `src/mediapipeline/core/publish/__init__.py`
- `src/mediapipeline/core/publish/file_io.py`
- `src/mediapipeline/core/publish/pending_drain_confidence.py`
- `src/mediapipeline/core/publish/pending_facade.py`
- `src/mediapipeline/core/publish/pending_format.py`
- `src/mediapipeline/core/publish/pending_manifest.py`
- `src/mediapipeline/core/publish/pending_manifest_rows.py`
- `src/mediapipeline/core/publish/pending_open_policy.py`
- `src/mediapipeline/core/publish/pending_paths.py`
- `src/mediapipeline/core/publish/pending_policy.py`
- `src/mediapipeline/core/publish/pending_policy_parts/__init__.py`
- `src/mediapipeline/core/publish/pending_policy_parts/status_rules.py`
- `src/mediapipeline/core/publish/pending_policy_parts/trust_fields.py`
- `src/mediapipeline/core/publish/pending_recovery.py`
- `src/mediapipeline/core/publish/pending_results.py`
- `src/mediapipeline/core/publish/pending_rows.py`
- `src/mediapipeline/core/publish/pending_service.py`
- `src/mediapipeline/core/publish/reconciliation_facade.py`
- `src/mediapipeline/core/publish/reconciliation_policy.py`
- `src/mediapipeline/core/rename/__init__.py`
- `src/mediapipeline/core/rename/apply.py`
- `src/mediapipeline/core/rename/apply_results.py`
- `src/mediapipeline/core/rename/apply_runner.py`
- `src/mediapipeline/core/rename/cleaning_policy.py`
- `src/mediapipeline/core/rename/constants.py`
- `src/mediapipeline/core/rename/contracts.py`
- `src/mediapipeline/core/rename/discovery.py`
- `src/mediapipeline/core/rename/file_io.py`
- `src/mediapipeline/core/rename/filename_preview.py`
- `src/mediapipeline/core/rename/movie.py`
- `src/mediapipeline/core/rename/plan_policy.py`
- `src/mediapipeline/core/rename/planner.py`
- `src/mediapipeline/core/rename/policy.py`
- `src/mediapipeline/core/rename/preview.py`
- `src/mediapipeline/core/rename/preview_policy.py`
- `src/mediapipeline/core/rename/preview_runner.py`
- `src/mediapipeline/core/rename/service.py`
- `src/mediapipeline/core/rename/tv.py`
- `src/mediapipeline/core/rename/tv_folder.py`
- `src/mediapipeline/core/rename/utils.py`

## Files Marked Out Of Scope

- `src/mediapipeline/core/api/commands_rename.py` was read only as an ancillary exposure check for W04-003 and is not counted as part of the 66 assigned files.
- WebView page assets were not reviewed as W04 assigned files because related UI ownership was delegated outside this worker except where backend DTO exposure required checking.
- Existing aggregate review files and other worker reports were not edited.

## Incomplete Coverage

None for assigned W04 files. Coverage is complete for the 66 assigned files. No implementation tests, smokes, release gates, runtime commands, pending drains, rename applies, or real-media validation were run because this was a review-only documentation task.
