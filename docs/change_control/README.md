# Change Control

This lightweight change-control system gives the project a centralized record
of software changes, bug-fix references, generated changelog entries, and
future release-note material. In Phase 3 it remains limited to JSON change
packets, version files, validation tooling, generated documentation, release
finalization, release history, and machine-readable release manifests. It does
not alter runtime media-processing behavior.

## Create a Change Packet

Run from the repository root:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.new_change --title "Short change title" --type tooling --risk low --version-target 2026.06.04.001
```

The script creates a new packet in `ops/release/changes/unreleased/` with the next
available `MP-CHANGE-YYYY-MMDD-###` identifier. Missing arguments use safe
defaults. New packets include their own packet path in `files_touched` so
coverage checks can see the packet file itself.

`unreleased/` is the active authoring surface. Validated completed packets may
be moved to `ops/release/changes/archived/YYYY-MM/` before release finalization
so planned and in-progress work remains easy to inspect. Archived packets are
still unreleased evidence: release manifests, changelog generation, validation,
and finalization continue to include them, but they never satisfy current
worktree coverage.

## Record Touched Files

Use the packet-update helper as work progresses. Add explicit paths when you
know exactly what belongs to the change:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### src/mediapipeline/core/maintenance/change_ledger.py --area maintenance --note "Maintenance coverage warning added."
```

After staging the intended commit set, use staged coverage capture to avoid
absorbing unrelated dirty files:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### --from-staged --validation "targeted tests - passed" --status in_progress
```

Complete a packet only after validation evidence and rollback details are
current:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### --complete --validation "validate_changes.py --require-worktree-coverage - passed"
```

## Validate Changes

Run from the repository root:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes
```

Validation checks required fields, allowed `status`, `type`, and `risk_level`
values, and complete-packet evidence fields.

Strict coverage modes enforce that changed files are listed in
`files_touched` of unreleased packets:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-staged-coverage
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-diff-coverage origin/main
```

Released packets are historical and do not satisfy current worktree, staged, or
branch-diff coverage. Coverage paths are repo-relative forward-slash paths from
`files_touched`; a file path covers only itself, while a directory path covers
descendant files. No wildcard/glob matching is used.

## Archive Completed Unreleased Packets

Preview a deterministic oldest-first tranche before applying it:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.archive_completed --completed-through 2026-07-20 --limit 25
```

For an idempotent bounded migration, review the preview and apply the exact IDs:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.archive_completed --packet-id MP-CHANGE-YYYY-MMDD-### --apply
```

The tool refuses explicitly selected planned or in-progress packets, reports
invalid/incomplete completed packets, never overwrites an archive target, moves
eligible packets into their `date_completed` month, prunes their derived packet
summaries, and regenerates the change index and changelog transactionally.
Re-running the same exact-ID command is a no-op once the packet is archived.
Rollback is a move back to `ops/release/changes/unreleased/`, followed by
`build_change_index`, `build_changelog`, and the relevant summary refresh.

## Rebuild the Index

Run from the repository root:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.build_change_index
```

This regenerates `docs/change_control/CHANGE_INDEX.md` from active unreleased,
archived completed-unreleased, and released change packets. The index records
each packet path so an ID remains directly discoverable after archival.

## Phase 2 Commands

Run from the repository root:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.build_change_index
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.build_changelog
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.build_release_manifest
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.prepare_release --version 2026.06.04.001 --channel local
```

`build_changelog.py` regenerates `docs/change_control/CHANGELOG.md`.
`build_release_manifest.py` regenerates `ops/release/metadata/RELEASE_MANIFEST.json`.
`prepare_release.py` updates release metadata, rebuilds generated outputs, and
prints a release-preparation summary. Use `--dry-run` to skip version-file and
change-packet updates.

## Phase 3 Commands

Run a dry-run finalization before moving any change packets:

```powershell
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.change_control.prepare_release --version 2026.06.04.001 --channel local --dry-run
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.change_control.finalize_release --version 2026.06.04.001 --channel local --dry-run
```

When the planned moves and archive output are correct, finalize and rebuild the
release history:

```powershell
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.change_control.finalize_release --version 2026.06.04.001 --channel local
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.change_control.list_releases
```

`finalize_release.py` moves complete active and archived-unreleased packets into
`ops/release/changes/released/<version>/`, regenerates release artifacts, and archives them
under `ops/release/metadata/history/<version>/`. `list_releases.py` regenerates
`docs/change_control/RELEASE_HISTORY.md`.

Version-history directories are immutable. Finalization refuses a version when
`ops/release/metadata/history/<version>/` already exists, including a partial
directory from an interrupted or manually copied release. Inspect and preserve
that evidence, then either finish recovery under incident/change control or use
a new version label; do not delete or overwrite history merely to retry. New
history is assembled in an owned sibling staging directory and published only
after every metadata file and `RELEASE_SUMMARY.md` is complete.

## Rule

Every meaningful code, config, UI, deployment, documentation, schema, test, or
tooling change must have an unreleased change packet with current
`files_touched`, affected areas, validation evidence, rollback detail, status,
and Python-impact notes where Python files are affected.
