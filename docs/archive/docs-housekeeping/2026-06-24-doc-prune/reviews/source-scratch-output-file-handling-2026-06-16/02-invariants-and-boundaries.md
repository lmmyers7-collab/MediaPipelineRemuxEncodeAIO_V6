# Invariants and Boundaries

## Core Invariants

I-001: Normal processing must treat source media as read-only.

- `Copy-FileRobocopy` verifies the source is inside allowed source roots before copy (`ops/pipeline/engine/storage/disk.ps1:414-421`).
- Scratch creation reads from source and writes to processing-local scratch (`ops/pipeline/engine/storage/scratch_copy.ps1:171-276`).
- Publish, pending drain, sidecar, and final-library promotion paths operate on local outputs, server outputs, pending outputs, or final-library destinations, not original source media.
- The only reviewed intentional source mutation path is rename apply; it is explicit, same-folder, previewed, undo-manifested, and gated by path authority (`src/mediapipeline/core/rename/apply.py:19-178`, `src/mediapipeline/core/rename/path_authority.py:48-132`).

I-002: Scratch copies are disposable derivatives, not authorities.

- Scratch leaf names reject rooted paths and separators (`ops/pipeline/engine/storage/scratch_copy.ps1:33-50`).
- Scratch paths are under `processingDir/src_<identity>` (`ops/pipeline/engine/storage/scratch_copy.ps1:52-59`).
- Reuse requires fingerprint match on full source path, size, and mtime (`ops/pipeline/engine/storage/scratch_copy.ps1:139-160`).
- Corrupt or mismatched scratch files are removed only after scratch-path and processing-root boundary checks (`ops/pipeline/engine/storage/scratch_copy.ps1:70-119`, `ops/pipeline/engine/storage/scratch_copy.ps1:211-237`).

I-003: Destination writes must be under configured output, processing, pending, or release roots.

- Copy destinations are matched against configured roots (`ops/pipeline/engine/storage/disk.ps1:330-380`).
- Destinations outside matched roots fail closed (`ops/pipeline/engine/storage/disk.ps1:422-437`).
- Output path planning places local output under `LocalEncoded` and server output under active output/library roots (`ops/pipeline/engine/paths/output_path_planning.ps1:32-67`).
- Final-library promotion rejects publish sources outside publish root and destinations outside destination root (`src/mediapipeline/core/final_library/promotion_parts/planning.py:93-143`).

I-004: Reveals must be staged, verified, and rollbackable.

- General copies land in a unique staging directory, validate file size, move through partial/final names, and clean partial/backup files on failures (`ops/pipeline/engine/storage/disk.ps1:514-664`).
- Publish writes server partial files and reveals after sidecar success (`ops/pipeline/engine/publish/publish_completion.ps1:87-287`).
- Final-library transfer copies to destination-local temp files, verifies temps, backs up existing files if overwrite is allowed, reveals, verifies finals, and rolls back revealed files on transaction failure (`src/mediapipeline/core/final_library/promotion_parts/transfer.py:62-371`).

I-005: Local outputs may be deleted only after an explicit success gate.

- Immediate publish returns `DeleteLocalOutput=true` only after final reveal and completed-manifest write (`ops/pipeline/engine/publish/publish_completion.ps1:276-287`).
- Pending drain removes local artifacts only after validating or successfully publishing the server copy (`ops/pipeline/engine/publish/pending_drain_transaction.ps1:167-175`, `ops/pipeline/engine/publish/pending_drain_transaction.ps1:265-270`).
- Final-library cleanup deletes publish-root outputs only after verified transfer and never deletes the publish root itself (`src/mediapipeline/core/final_library/promotion_parts/cleanup.py:9-64`).

I-006: Boundary checks must be segment-aware and must reject roots as mutation targets.

- PowerShell helpers normalize paths, detect UNC share roots, and compare with separator-aware child checks (`ops/pipeline/engine/shared/path_helpers.ps1:18-78`).
- PowerShell mutation guard rejects missing roots, missing paths, root target mutation, outside-root paths, and reparse points (`ops/pipeline/engine/shared/path_helpers.ps1:138-175`).
- Python helpers apply equivalent root, outside-root, root-target, missing-path, and reparse protections (`src/mediapipeline/core/paths/layout.py:48-167`).

I-007: UNC cleanup is opt-in for remote staging.

- Stale partial cleanup skips UNC roots unless `CleanupRemoteStaging` is enabled (`ops/pipeline/engine/storage/disk.ps1:679-681`).
- UNC/share-root parsing exists in `path_helpers.ps1` and is used by boundary comparisons (`ops/pipeline/engine/shared/path_helpers.ps1:18-31`).

## Boundary Matrix

| Boundary | Allowed mutation | Guard evidence | Residual risk |
| --- | --- | --- | --- |
| Source roots | Rename only through explicit rename feature; normal processing read-only. | `src/mediapipeline/core/rename/path_authority.py:48-132`; `ops/pipeline/engine/storage/disk.ps1:414-421` | Rename remains a real source mutation path and must keep user confirmation and undo tests. |
| Processing scratch | Create, overwrite, delete scratch and fingerprint files. | `ops/pipeline/engine/storage/scratch_copy.ps1:70-119` | Failure artifact move should assert artifact-root boundary directly. |
| Local output roots | Create outputs, partials, publish backups, cleanup stale partials. | `ops/pipeline/engine/storage/disk.ps1:422-664` | Stale cleanup is overbroad. See F-001. |
| Server/publish roots | Create partials, reveal final, sidecar backup/restore. | `ops/pipeline/engine/publish/publish_completion.ps1:87-287`; `ops/pipeline/engine/publish/publish_partial.ps1:4-175` | Caller-derived partial paths are safe in reviewed flows; helper-level boundary assertions would harden defense. |
| Pending push root | Park local output and sidecars, remove after drain. | `ops/pipeline/engine/publish/pending_park_transaction.ps1:170-272`; `ops/pipeline/engine/publish/pending_drain_transaction.ps1:88-270` | Cleanup uses manifest-derived paths but validates trust before drain. |
| Final library destination | Transactional copies and optional overwrite backups. | `src/mediapipeline/core/final_library/promotion_parts/planning.py:93-143`; `src/mediapipeline/core/final_library/promotion_parts/transfer.py:232-371` | Good coverage; keep destination-root tests. |
| Release destination | Delete only if release marker/in-progress marker policy allows. | `ops/scripts/release/build.ps1:162-221`, `ops/scripts/release/build.ps1:320-390` | Good release-output guard. |
