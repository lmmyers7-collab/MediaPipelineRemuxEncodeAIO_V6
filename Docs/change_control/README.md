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
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\new_change.py --title "Short change title" --type tooling --risk low --version-target 0.1.0-dev
```

The script creates a new packet in `changes/unreleased/` with the next
available `MP-CHANGE-YYYY-MMDD-###` identifier. Missing arguments use safe
defaults. New packets include their own packet path in `files_touched` so
coverage checks can see the packet file itself.

## Record Touched Files

Use the packet-update helper as work progresses. Add explicit paths when you
know exactly what belongs to the change:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\record_change_touch.py MP-CHANGE-YYYY-MMDD-### app/maintenance/change_ledger.py --area maintenance --note "Maintenance coverage warning added."
```

After staging the intended commit set, use staged coverage capture to avoid
absorbing unrelated dirty files:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\record_change_touch.py MP-CHANGE-YYYY-MMDD-### --from-staged --validation "targeted tests - passed" --status in_progress
```

Complete a packet only after validation evidence and rollback details are
current:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\record_change_touch.py MP-CHANGE-YYYY-MMDD-### --complete --validation "validate_changes.py --require-worktree-coverage - passed"
```

## Validate Changes

Run from the repository root:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py
```

Validation checks required fields, allowed `status`, `type`, and `risk_level`
values, and complete-packet evidence fields.

Strict coverage modes enforce that changed files are listed in
`files_touched` of unreleased packets:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py --require-worktree-coverage
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py --require-staged-coverage
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py --require-diff-coverage origin/main
```

Released packets are historical and do not satisfy current worktree, staged, or
branch-diff coverage. Coverage paths are exact repo-relative forward-slash paths
from `files_touched`; no glob matching is used.

## Rebuild the Index

Run from the repository root:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\build_change_index.py
```

This regenerates `Docs/change_control/CHANGE_INDEX.md` from all unreleased and
released change packets.

## Phase 2 Commands

Run from the repository root:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\build_change_index.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\build_changelog.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\build_release_manifest.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\prepare_release.py --version 0.1.0-dev --channel dev
```

`build_changelog.py` regenerates `Docs/change_control/CHANGELOG.md`.
`build_release_manifest.py` regenerates `release/RELEASE_MANIFEST.json`.
`prepare_release.py` updates release metadata, rebuilds generated outputs, and
prints a release-preparation summary. Use `--dry-run` to skip version-file and
change-packet updates.

## Phase 3 Commands

Run a dry-run finalization before moving any change packets:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\prepare_release.py --version 0.1.0-dev --channel dev --dry-run
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\finalize_release.py --version 0.1.0-dev --channel dev --dry-run
```

When the planned moves and archive output are correct, finalize and rebuild the
release history:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\finalize_release.py --version 0.1.0-dev --channel dev
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\list_releases.py
```

`finalize_release.py` moves complete unreleased packets into
`changes/released/<version>/`, regenerates release artifacts, and archives them
under `release/history/<version>/`. `list_releases.py` regenerates
`Docs/change_control/RELEASE_HISTORY.md`.

## Rule

Every meaningful code, config, UI, deployment, documentation, schema, test, or
tooling change must have an unreleased change packet with current
`files_touched`, affected areas, validation evidence, rollback detail, status,
and Python-impact notes where Python files are affected.
