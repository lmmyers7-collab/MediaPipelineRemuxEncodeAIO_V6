# Release Process

This process uses JSON change packets to generate reviewable release
documentation, finalize complete unreleased changes, and archive release
artifacts. Phase 3 finalization moves only complete unreleased packets and
should always be previewed with `--dry-run` first.

1. Create or complete change packets in `changes/unreleased/`.
2. Keep packet coverage current with
   `.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\record_change_touch.py MP-CHANGE-YYYY-MMDD-### --from-staged`.
3. Run `.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py`.
4. Run `.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py --require-worktree-coverage`.
5. Run `.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\build_change_index.py`.
6. Run `.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\build_changelog.py`.
7. Run `.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\build_release_manifest.py`.
8. Run `.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\prepare_release.py --version 0.1.0-dev --channel dev` when ready.
9. Review `release/RELEASE_MANIFEST.json` and `Docs/change_control/CHANGELOG.md`.

## Phase 3 Finalization

1. Complete all intended change packets.
2. Run validation and strict worktree coverage.
3. Run `prepare_release.py`.
4. Run `finalize_release.py` with `--dry-run`.
5. Review planned moves and archive output.
6. Run `finalize_release.py` without `--dry-run`.
7. Run `list_releases.py`.
8. Confirm `RELEASE_HISTORY.md` updated.

Example commands:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py --require-worktree-coverage
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\prepare_release.py --version 0.1.0-dev --channel dev --dry-run
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\finalize_release.py --version 0.1.0-dev --channel dev --dry-run
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\finalize_release.py --version 0.1.0-dev --channel dev
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\list_releases.py
```

Complete changes must include enough validation and rollback detail for a
future release reviewer to understand what changed and how to back it out.
Before merging a pull request, CI runs
`validate_changes.py --require-diff-coverage origin/<base-branch>` so branch
changes cannot ship without unreleased packet coverage.
