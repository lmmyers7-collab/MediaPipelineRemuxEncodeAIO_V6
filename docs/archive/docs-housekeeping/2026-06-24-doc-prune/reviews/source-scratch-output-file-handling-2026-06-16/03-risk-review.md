# Risk Review

## Source Mutation

No normal encode/remux/publish path was found that deletes, overwrites, renames, or moves original source media. Source media is used as a copy input, and the scratch layer fingerprints derivatives before reuse.

The intentional source mutation surface is rename apply. It is explicit, previewed, same-folder, undo-manifested, and path-authority gated. The key controls are in `src/mediapipeline/core/rename/apply.py:19-178`, `src/mediapipeline/core/rename/apply_runner.py:17-131`, and `src/mediapipeline/core/rename/path_authority.py:48-132`.

Residual risk: rename is still a real source mutation feature. It must remain outside any automated processing path and must keep confirmation, undo, rollback, and outside-root tests.

## Scratch Copies

Scratch handling is strongly bounded:

- Scratch path construction uses safe leaf names and processing-root placement.
- Scratch reuse requires a fingerprint match on source path, size, and mtime.
- Scratch cleanup requires processing/local-base boundary checks and only removes empty `src_*` parents.
- Integrity failures delete scratch derivatives, not source media.

No source mutation issue was found in scratch copy handling.

## Output Placement

Output placement is generally explicit and root-derived. Local output is planned under `LocalEncoded`; server output is planned under active output/library roots; final-library promotion preserves relative layout from publish root to destination root.

The high-risk issue is not placement of new outputs, but cleanup of old matching filenames anywhere under broad output roots. See F-001.

## Partial-Copy and Reveal Behavior

The main copy path uses unique staging directories and partial/final moves. Publish and final-library transfer use partials, backups, validation, and rollback. Immediate publish parks local output instead of deleting it on copy or sidecar failure, and pending drain leaves manifest/local output in place on failures before success.

No final-reveal data-loss bug was found in the reviewed immediate publish, pending drain, sidecar, or final-library transfer flows.

## Cleanup and Delete Paths

Two cleanup concerns were found:

- F-001: stale partial cleanup deletes broad filename patterns under entire output roots, without proving the file is pipeline-owned.
- F-002: `Copy-FileRobocopy` can leave an empty `.mediapipeline-staging` directory after low-space or pre-attempt stop returns.

Processing-dir temp cleanup is better bounded: it first verifies `processingDir` under `LocalBase`, then only deletes candidate paths still inside `processingDir` (`ops/pipeline/engine/shared/temp_cleanup.ps1:19-73`).

Final-library cleanup is safe-delete gated: it deletes only copied source outputs under publish root after verified destination copy and never deletes the publish root itself (`src/mediapipeline/core/final_library/promotion_parts/cleanup.py:9-64`).

## Path Normalization and Boundary Guards

PowerShell and Python path helpers both protect against sibling-prefix escapes and root-target deletion. PowerShell helpers also include UNC share-root handling. Python helpers include reparse checks for mutation paths. These are the right primitives and are widely used in reviewed mutation paths.

Residual hardening opportunity: some lower-level publish helper functions rely on callers to pass already trusted paths. Reviewed call paths are safe, but helper-local boundary assertions would reduce future regression risk.

## Same-Disk Layouts

Copy and publish reveal paths stage partials near their destination roots, reducing cross-device rename risk. Final-library transfer uses destination-parent temporary files and per-file backups, which is the strongest reviewed same-disk pattern.

The release build uses an in-progress marker in the destination and rejects dangerous destination layouts before destructive replacement.

## UNC Paths

UNC cleanup is explicitly skipped unless remote cleanup is enabled. This is appropriate for remote roots where delete semantics and network errors are riskier.

The reviewed risk is configuration-driven: enabling remote cleanup extends F-001 to UNC output roots.

## Failure Cleanup

Failure cleanup is generally conservative:

- Publish failures park local outputs.
- Pending sidecar failures restore backups or remove newly written sidecars.
- Final-library transaction failures roll back revealed files.
- ASS/SRT conversion removes temporary helper files.

Watch item: failure artifact capture moves scratch paths into state failure artifacts using generated state layout, but the move path would be stronger with an explicit artifact-root mutation guard at the point of deletion/replacement (`ops/pipeline/engine/failures/failure_state.ps1:741-753`).
