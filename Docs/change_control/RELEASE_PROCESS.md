# Release Process

This process uses JSON change packets to generate reviewable release
documentation, finalize complete unreleased changes, and archive release
artifacts. Phase 3 finalization moves only complete unreleased packets and
should always be previewed with `--dry-run` first.

1. Create or complete change packets in `ops/release/changes/unreleased/`.
2. Keep packet coverage current with
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### --from-staged`.
3. Run `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes`.
4. Run `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`.
5. Run `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.build_change_index`.
6. Run `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.build_changelog`.
7. Run `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.build_release_manifest`.
8. Run `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.prepare_release --version 2026.06.04.001 --channel local` when ready.
9. Review `ops/release/metadata/RELEASE_MANIFEST.json` and `docs/change_control/CHANGELOG.md`.

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
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.prepare_release --version 2026.06.04.001 --channel local --dry-run
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.finalize_release --version 2026.06.04.001 --channel local --dry-run
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.finalize_release --version 2026.06.04.001 --channel local
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.list_releases
```

Complete changes must include enough validation and rollback detail for a
future release reviewer to understand what changed and how to back it out.
Before merging a pull request, CI runs
`validate_changes.py --require-diff-coverage origin/<base-branch>` so branch
changes cannot ship without unreleased packet coverage.

