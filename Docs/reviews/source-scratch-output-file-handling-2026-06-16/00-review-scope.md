# Source/Scratch/Output File Handling Review Scope

Review date: 2026-06-16

Repository: current MediaPipelineRemuxEncodeAIO workspace

This is a review-only artifact. No source code, generated summaries, settings, state, queues, media files, or tests were edited as part of this review.

## Operator Request

Perform a full code review of source/scratch/output file handling, focused on:

- Source mutation and safe-delete gating.
- Scratch-copy invariants.
- Output placement and publish/final-library promotion placement.
- Cleanup, temporary files, partial-copy behavior, failure cleanup, delete and overwrite paths.
- Path normalization, same-disk layouts, UNC handling, and boundary guards.

The review treats source-file mutation as forbidden unless the operation is explicitly safe-delete gated.

## Required Project Reads

Before reading full source files, the following project-state and generated index material was read in accordance with `AGENTS.md`:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Generated summaries for the storage, scratch, publish, pending-drain, final-library promotion, rename, path-layout, subtitle, release-build, failure-state, and relevant test files reviewed below.

## Source Areas Reviewed

PowerShell pipeline:

- `ops/pipeline/entrypoints/MediaPipeline.ps1`
- `ops/pipeline/engine/storage/disk.ps1`
- `ops/pipeline/engine/storage/scratch_copy.ps1`
- `ops/pipeline/engine/shared/path_helpers.ps1`
- `ops/pipeline/engine/shared/temp_cleanup.ps1`
- `ops/pipeline/engine/paths/output_path_planning.ps1`
- `ops/pipeline/engine/paths/path_capability.ps1`
- `ops/pipeline/engine/publish/publish_completion.ps1`
- `ops/pipeline/engine/publish/publish_partial.ps1`
- `ops/pipeline/engine/publish/publish_sidecars.ps1`
- `ops/pipeline/engine/publish/pending_park_transaction.ps1`
- `ops/pipeline/engine/publish/pending_drain_transaction.ps1`
- `ops/pipeline/engine/publish/pending_sidecar_transactions.ps1`
- `ops/pipeline/engine/subtitles/ass.ps1`
- `ops/pipeline/engine/subtitles/srt.ps1`
- `ops/pipeline/engine/failures/failure_state.ps1`
- `ops/pipeline/engine/storage/state_store.ps1`
- `ops/scripts/release/build.ps1`

Python desktop/core:

- `src/mediapipeline/core/paths/layout.py`
- `src/mediapipeline/core/final_library/promotion.py`
- `src/mediapipeline/core/final_library/promotion_parts/planning.py`
- `src/mediapipeline/core/final_library/promotion_parts/transfer.py`
- `src/mediapipeline/core/final_library/promotion_parts/cleanup.py`
- `src/mediapipeline/core/rename/apply.py`
- `src/mediapipeline/core/rename/apply_runner.py`
- `src/mediapipeline/core/rename/path_authority.py`
- `src/mediapipeline/pipeline/ass_to_srt_cli.py`

Tests:

- `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1`
- `tests/python/desktop/test_final_library_promotion.py`
- `tests/python/desktop/test_service_path_layout.py`
- `tests/python/desktop/test_application_facade_rename.py`
- `tests/python/desktop/test_service_rename_apply.py`

## Review Standard

This review used the following standard:

- Source media files must not be deleted, overwritten, moved, renamed, or mutated by normal processing.
- Any source-affecting operation must be explicit, user-visible, bounded to an approved source root, reversible where practical, and covered by tests.
- Scratch files must be treated as disposable copies with identity/fingerprint checks before reuse.
- Output publication must use destination-local staging/partial names, verify size/integrity before reveal, and clean partials on failure.
- Cleanup must be provenance-aware enough to avoid deleting user-owned files that merely match a broad filename pattern.
- Boundary checks must reject sibling-prefix escapes, root deletion, missing roots, and reparse/junction targets where mutation is possible.
- UNC paths must fail closed unless a remote cleanup/write behavior is explicitly enabled.
