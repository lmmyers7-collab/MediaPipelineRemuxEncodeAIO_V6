# Phase 7 - Finalization

## Goal

Finalize `V6.0.0` release metadata after package validation and real-media
pilot evidence pass.

## Scope

- Complete intended change packets.
- Run strict coverage.
- Generate changelog and release manifest.
- Finalize release metadata through existing change-control tooling.
- Archive release evidence under existing release/change-control locations.

## Steps

1. Confirm Phase 5 and Phase 6 evidence is complete.
2. Complete all intended change packets under `changes/unreleased/`.
3. Run change-control validation.
4. Run strict worktree coverage and resolve only intended release files.
5. Run release preparation dry-run for `V6.0.0`.
6. Run finalization dry-run for `V6.0.0`.
7. Review planned moves and archive output.
8. Finalize `V6.0.0`.
9. Regenerate release history.
10. Record artifact folder and validation evidence in release notes.

## Commands

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py --require-worktree-coverage
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\prepare_release.py --version V6.0.0 --channel local --dry-run
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\finalize_release.py --version V6.0.0 --channel local --dry-run
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\finalize_release.py --version V6.0.0 --channel local
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\list_releases.py
```

## Exit Criteria

- `changes/released/V6.0.0/` contains finalized complete packets.
- Generated changelog and release manifest identify `V6.0.0`.
- Portable candidate folder and zip path are recorded.
- Package/open/close validation evidence is recorded.
- Real-media pilot evidence is recorded.
- No unrelated dirty files were swept into the release.

