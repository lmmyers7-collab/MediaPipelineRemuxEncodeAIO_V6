# Worker Review: W04-publish-completed-pending-rename

## Scope
- Assigned domain: publish-completed-pending-rename
- Assigned files: 66 files listed below
- Explicit exclusions: full source/symbol review is incomplete for the files listed in Incomplete Coverage; generated summaries only were reviewed for those files.

## Assigned File List

- `ops/pipeline/engine/publish/pending_drain_transaction.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/pending_manifest_store.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/pending_park_transaction.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/pending_publish_index.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/pending_push.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/pending_repair.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/pending_sidecar_transactions.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/pending_transactions.ps1` (publish, high, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/publish_completion.ps1` (publish, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/publish_completion/context_builders.ps1` (publish, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/publish_partial.ps1` (publish, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/publish_result.ps1` (publish, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/publish_sidecars.ps1` (publish, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/publish/sidecar.ps1` (publish, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/__init__.py` (completed, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/backfill.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/facade.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/manifest.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/open_facade.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/open_policy.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/policy.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/service.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/trust_fields.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/completed/validation_state.py` (completed, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/__init__.py` (publish, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/file_io.py` (publish, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_drain_confidence.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_facade.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_format.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_manifest.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_manifest_rows.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_open_policy.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_paths.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_policy.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_policy_parts/__init__.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_policy_parts/status_rules.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_policy_parts/trust_fields.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_recovery.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_results.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_rows.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/pending_service.py` (publish, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/reconciliation_facade.py` (publish, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/publish/reconciliation_policy.py` (publish, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/__init__.py` (rename, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/apply.py` (rename, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/apply_results.py` (rename, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/apply_runner.py` (rename, high, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/cleaning_policy.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/constants.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/contracts.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/discovery.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/facade.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/file_io.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/filename_preview.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/movie.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/path_authority.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/plan_policy.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/planner.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/policy.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/preview.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/preview_policy.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/preview_runner.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/service.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/tv.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/tv_folder.py` (rename, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/rename/utils.py` (rename, medium, code-symbol-review, summary=yes)

## Coverage Ledger

| File | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|
| `ops/pipeline/engine/publish/pending_drain_transaction.ps1` | all listed | complete | Finding W04-1. |
| `ops/pipeline/engine/publish/pending_manifest_store.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/pending_park_transaction.ps1` | all listed | complete | Finding W04-2 supporting evidence. |
| `ops/pipeline/engine/publish/pending_publish_index.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/pending_push.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/pending_repair.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/pending_sidecar_transactions.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/pending_transactions.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/publish_completion.ps1` | all listed | complete | Findings W04-1, W04-2. |
| `ops/pipeline/engine/publish/publish_completion/context_builders.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/publish_partial.ps1` | all listed | complete | Finding W04-1. |
| `ops/pipeline/engine/publish/publish_result.ps1` | all listed | complete | Finding W04-2 supporting evidence. |
| `ops/pipeline/engine/publish/publish_sidecars.ps1` | all listed | complete | Reviewed: no findings. |
| `ops/pipeline/engine/publish/sidecar.ps1` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/__init__.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/backfill.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/facade.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/manifest.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/open_facade.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/open_policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/service.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/trust_fields.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/completed/validation_state.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/__init__.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/file_io.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: publish file I/O helpers. |
| `src/mediapipeline/core/publish/pending_drain_confidence.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_facade.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_format.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_manifest.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_manifest_rows.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_open_policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_paths.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_policy_parts/__init__.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: pending policy package exports. |
| `src/mediapipeline/core/publish/pending_policy_parts/status_rules.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: pending status/rule helpers. |
| `src/mediapipeline/core/publish/pending_policy_parts/trust_fields.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: pending trust-field helpers. |
| `src/mediapipeline/core/publish/pending_recovery.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_results.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_rows.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/pending_service.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/reconciliation_facade.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/publish/reconciliation_policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/__init__.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: rename package exports. |
| `src/mediapipeline/core/rename/apply.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/apply_results.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/apply_runner.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/cleaning_policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/constants.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: rename constants. |
| `src/mediapipeline/core/rename/contracts.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: rename dataclasses/contracts. |
| `src/mediapipeline/core/rename/discovery.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: rename discovery symbols. |
| `src/mediapipeline/core/rename/facade.py` | all listed | complete | Finding W04-3. |
| `src/mediapipeline/core/rename/file_io.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: rename file I/O helpers. |
| `src/mediapipeline/core/rename/filename_preview.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/movie.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/path_authority.py` | all listed | complete | Finding W04-3. |
| `src/mediapipeline/core/rename/plan_policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/planner.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/preview.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/preview_policy.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/preview_runner.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/service.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/tv.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/tv_folder.py` | all listed | complete | Reviewed: no findings. |
| `src/mediapipeline/core/rename/utils.py` | summary only | partial | Not full-source reviewed before time-box cutoff; unreviewed group: rename utility helpers. |

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|
| W04-1 | High | `ops/pipeline/engine/publish/publish_partial.ps1:35`; `ops/pipeline/engine/publish/publish_completion.ps1:212`; `ops/pipeline/engine/publish/pending_drain_transaction.ps1:228` | `Backup-PublishSidecarForReveal` / `Restore-PublishSidecarAfterRevealFailure` call sites | Existing final sidecar can be removed after a failed reveal when the pre-existing sidecar backup failed. | Simulate backup failure plus reveal failure with an existing sidecar; assert original sidecar remains and publish/drain fails closed. |
| W04-2 | Medium | `ops/pipeline/engine/publish/publish_completion.ps1:36`; `ops/pipeline/engine/publish/publish_completion.ps1:98`; `ops/pipeline/engine/publish/pending_park_transaction.ps1:244`; `ops/pipeline/engine/publish/publish_result.ps1:12` | Deferred/output-space pending publish result construction | Successful pending park moves the local output before result size is read, so the returned `OutputSizeBytes` can collapse to `0`. | Add deferred and output-space-deferred publish tests asserting result size equals the pre-park output length. |
| W04-3 | High | `src/mediapipeline/core/rename/path_authority.py:47`; `src/mediapipeline/core/rename/path_authority.py:100`; `src/mediapipeline/core/rename/facade.py:125` | Rename path-authority apply gate | Rename apply blocks only `outside_configured_roots`; requests with no configured roots become `unscoped_operator_path` and can proceed with normal confirm-apply. | Add apply-route/unit test with no `_configured_media_roots` and selected outside-root path; assert rejection before filesystem rename. |

## Detailed Findings

### W04-1 - High - publish sidecar backup failure can delete existing final sidecar

- File/line/symbol: `ops/pipeline/engine/publish/publish_partial.ps1:35-40` (`Backup-PublishSidecarForReveal`), `ops/pipeline/engine/publish/publish_partial.ps1:71-88` (`Restore-PublishSidecarAfterRevealFailure`), `ops/pipeline/engine/publish/publish_completion.ps1:212-247`, `ops/pipeline/engine/publish/pending_drain_transaction.ps1:228-244`.
- Problem: a failed backup of an existing final sidecar returns an empty path, but callers still write the replacement sidecar before final media reveal. If reveal then fails, restore receives an empty backup and deletes the sidecar at `publish_partial.ps1:85-87`.
- Impact: an existing completed output can lose its prior sidecar during a failed immediate publish or pending drain, weakening completed/pending proof and sidecar carry-forward.
- Evidence: backup failure returns `''` after warning at `publish_partial.ps1:35-40`; restore deletes any current sidecar when no backup is available at `publish_partial.ps1:85-87`; immediate publish calls backup then `Write-Sidecar` without fail-closed handling at `publish_completion.ps1:212-217`; reveal failure restores with that possibly-empty backup at `publish_completion.ps1:239-247`; pending drain does the same at `pending_drain_transaction.ps1:228-244`.
- Fix direction: make backup state explicit (`had_existing`, `backup_ok`, `backup_path`, `error`) and fail closed before `Write-Sidecar` when an existing sidecar cannot be backed up, or preserve the current sidecar on reveal failure when backup was required but unavailable.
- Validation: PowerShell fixture that locks/denies backup of an existing sidecar, allows new sidecar write, forces reveal failure, then asserts the original sidecar content remains and immediate publish/pending drain returns a failure without committing media.

### W04-2 - Medium - deferred pending publish result size is read after local output is moved

- File/line/symbol: `ops/pipeline/engine/publish/publish_completion.ps1:36-46` and `publish_completion.ps1:98-129` deferred/output-space branches; `ops/pipeline/engine/publish/pending_park_transaction.ps1:244`; `ops/pipeline/engine/publish/publish_result.ps1:12-26`.
- Problem: successful pending park moves `$Paths.LocalOut` to the parked path before `publish_completion.ps1` reads `$Paths.LocalOut` for the result size. The missing path yields `$null`, and `New-PipelinePublishResult` casts the default/argument to `[long]`, producing `0`.
- Impact: successful `pending_publish` results for deferred/output-space-deferred publishes can report `OutputSizeBytes = 0` even though the parked manifest carries a real output size, making result evidence misleading for completed/pending validation and operator diagnostics.
- Evidence: deferred branch parks at `publish_completion.ps1:38-39` then reads `$Paths.LocalOut` at `publish_completion.ps1:45`; output-space branch parks at `publish_completion.ps1:98-124` then reads `$Paths.LocalOut` at `publish_completion.ps1:128`; the park transaction moves the file at `pending_park_transaction.ps1:244`; result helper defaults/casts `OutputSizeBytes` as `[long]` at `publish_result.ps1:12` and `publish_result.ps1:26`.
- Fix direction: capture output length before park, return parked transaction details from `Invoke-ParkPendingPushWithTx3gSidecars`, or read the parked manifest/parked file after successful park instead of the moved local path.
- Validation: targeted tests for `DeferredPublish` and output-space-deferred publish success asserting `OutputSizeBytes` matches the pre-park local output length and the pending manifest `output_size`.

### W04-3 - High - rename apply does not fail closed when configured roots are absent

- File/line/symbol: `src/mediapipeline/core/rename/path_authority.py:47-55`, `src/mediapipeline/core/rename/path_authority.py:100-101`, `src/mediapipeline/core/rename/facade.py:125-127`.
- Problem: missing configured media roots are annotated as `path_authority = "unscoped_operator_path"` with review status, but `rename_plan_outside_configured_roots` returns only `outside_configured_roots`. The apply facade blocks only that outside-root list, so unscoped paths can proceed when normal `confirm_apply` is present.
- Impact: if request/root resolution omits `_configured_media_roots`, rename apply can mutate selected paths without the explicit outside-root confirmation intended by the path-authority warning. This is a filesystem movement guard gap.
- Evidence: no roots return `unscoped_operator_path` at `path_authority.py:49-55`; outside-root filtering only selects `outside_configured_roots` at `path_authority.py:100-101`; apply blocks only that filtered list at `facade.py:125-127`.
- Fix direction: treat `unscoped_operator_path` as apply-blocking unless a separate explicit confirmation is present, and prefer deriving configured roots server-side on the apply path rather than trusting request metadata.
- Validation: route/unit test with `confirm_apply: true`, a selected path outside configured roots, and no `_configured_media_roots`; assert apply returns a blocking result and no filesystem rename occurs. Add a companion test proving the explicit outside-root confirmation still works only for known outside-root rows.

## Test Coverage Gaps

- Static review only; no tests or runtime/media mutations were run for this worker audit.
- Missing targeted coverage for W04-1: existing-sidecar backup failure followed by final reveal failure in both immediate publish and pending drain.
- Missing targeted coverage for W04-2: deferred/output-space-deferred success result size after pending park.
- Missing targeted coverage for W04-3: rename apply with absent configured roots must fail closed before filesystem mutation.
- Full-source/symbol review was not completed for the files listed in Incomplete Coverage.

## Boundary Risks

- No source media, runtime state, queue state, pending publish directories, or rename targets were mutated during this review.
- Pending publish park/drain and sidecar carry-forward remain high-risk areas; findings W04-1 and W04-2 should be fixed with real fixture coverage before operator-facing validation claims.
- Rename apply is a filesystem mutation boundary; finding W04-3 should be treated as a fail-closed safety defect.
- No release change packet was created because the assignment explicitly restricted edits to this one worker markdown file.

## Files With No Findings

Reviewed: no findings.

- `ops/pipeline/engine/publish/pending_manifest_store.ps1`
- `ops/pipeline/engine/publish/pending_publish_index.ps1`
- `ops/pipeline/engine/publish/pending_push.ps1`
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
- `src/mediapipeline/core/publish/pending_drain_confidence.py`
- `src/mediapipeline/core/publish/pending_facade.py`
- `src/mediapipeline/core/publish/pending_format.py`
- `src/mediapipeline/core/publish/pending_manifest.py`
- `src/mediapipeline/core/publish/pending_manifest_rows.py`
- `src/mediapipeline/core/publish/pending_open_policy.py`
- `src/mediapipeline/core/publish/pending_paths.py`
- `src/mediapipeline/core/publish/pending_policy.py`
- `src/mediapipeline/core/publish/pending_recovery.py`
- `src/mediapipeline/core/publish/pending_results.py`
- `src/mediapipeline/core/publish/pending_rows.py`
- `src/mediapipeline/core/publish/pending_service.py`
- `src/mediapipeline/core/publish/reconciliation_facade.py`
- `src/mediapipeline/core/publish/reconciliation_policy.py`
- `src/mediapipeline/core/rename/apply.py`
- `src/mediapipeline/core/rename/apply_results.py`
- `src/mediapipeline/core/rename/apply_runner.py`
- `src/mediapipeline/core/rename/cleaning_policy.py`
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

## Incomplete Coverage

Generated summaries were read, but full source/symbol review was not completed before the time-box update for these assigned files:

- `src/mediapipeline/core/publish/file_io.py` - unreviewed symbol group: publish file I/O helpers.
- `src/mediapipeline/core/publish/pending_policy_parts/__init__.py` - unreviewed symbol group: pending policy package exports.
- `src/mediapipeline/core/publish/pending_policy_parts/status_rules.py` - unreviewed symbol group: pending status/rule helpers.
- `src/mediapipeline/core/publish/pending_policy_parts/trust_fields.py` - unreviewed symbol group: pending trust-field helpers.
- `src/mediapipeline/core/rename/__init__.py` - unreviewed symbol group: rename package exports.
- `src/mediapipeline/core/rename/constants.py` - unreviewed symbol group: rename constants.
- `src/mediapipeline/core/rename/contracts.py` - unreviewed symbol group: rename dataclasses/contracts.
- `src/mediapipeline/core/rename/discovery.py` - unreviewed symbol group: rename discovery symbols.
- `src/mediapipeline/core/rename/file_io.py` - unreviewed symbol group: rename file I/O helpers.
- `src/mediapipeline/core/rename/utils.py` - unreviewed symbol group: rename utility helpers.

Reason: the user time-boxed the audit and requested the worker file be written immediately with coverage actually completed.
