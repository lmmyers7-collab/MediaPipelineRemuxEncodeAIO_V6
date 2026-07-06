# Phase 7 - Finalization

## Goal

Finalize `2026.06.04.001` release metadata after package validation and real-media
pilot evidence pass.

## Scope

- Complete intended change packets.
- Run strict coverage.
- Generate changelog and release manifest.
- Finalize release metadata through existing change-control tooling.
- Archive release evidence under existing ops/release/metadata/change-control locations.
- Treat generated release metadata as source-side release history unless Phase 4
  is rerun to rebuild a package that includes the finalized metadata.

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm Phase 5 package/open/close evidence and Phase 6 real-media pilot
  evidence both exist for the same candidate folder and app version.
- Confirm release evidence has been sanitized so personal source/output paths
  are not copied into clean handoff artifacts.
- Confirm every intended change packet is complete and every unrelated dirty
  file is either covered by its own packet or explicitly excluded from this
  finalization.
- Stop if package evidence, real-media evidence, sanitization, or change-packet
  coverage is missing.
- Stop if finalized metadata is intended to ship inside the portable candidate;
  in that case finalize metadata first, rebuild in Phase 4, rerun Phase 5, and
  rerun or reconcile Phase 6 against the rebuilt candidate.

## Steps

1. Confirm Phase 5 and Phase 6 evidence is complete.
2. Complete all intended change packets under `ops/ops/release/metadata/changes/unreleased/`.
3. Run change-control validation.
4. Run strict worktree coverage and resolve only intended release files.
5. Run release preparation dry-run for `2026.06.04.001`.
6. Run finalization dry-run for `2026.06.04.001`.
7. Review planned moves and archive output.
8. Finalize `2026.06.04.001`.
9. Regenerate release history.
10. Run post-finalization validation.
11. Record artifact folder and validation evidence in release notes.
12. If final metadata must be included in the portable artifact, return to
    Phase 4 instead of accepting the previously validated candidate.

## Commands

```powershell
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\prepare_release.py --version 2026.06.04.001 --channel local --dry-run
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\finalize_release.py --version 2026.06.04.001 --channel local --dry-run
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\finalize_release.py --version 2026.06.04.001 --channel local
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\list_releases.py
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\check_active_doc_references.py
```

## Change Ledger And Rollback

- Complete every intended packet before finalization.
- Record Phase 5 and Phase 6 evidence references, candidate folder, zip path,
  release manifest, generated changelog, and post-finalization validation.
- If dry-run output is wrong, stop before finalization. If finalization has
  already run and metadata is wrong, restore through version control or the
  existing change-control layout, then rerun post-finalization validation. Do
  not hand-edit released metadata without a new change packet.

## Exit Criteria

- `ops/ops/release/metadata/changes/released/2026.06.04.001/` contains finalized complete packets.
- Generated changelog and release manifest identify `2026.06.04.001`.
- Portable candidate folder and zip path are recorded.
- Package/open/close validation evidence is recorded.
- Real-media pilot evidence is recorded.
- Finalized metadata is either source-side release history only, or a rebuilt
  candidate containing that metadata has fresh Phase 5 evidence and reconciled
  Phase 6 evidence.
- No unrelated dirty files were swept into the release.
