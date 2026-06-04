# Phase 2 - File Layout Cleanup

## Goal

Make release-related file placement predictable without moving media behavior
or reviving removed legacy surfaces.

## Placement Rules

| Work Type | Location |
|---|---|
| Python app/domain code | `app/<domain>/` |
| Local API host and WebView backend integration | `DesktopApp/mediapipeline_desktop_app/` |
| PowerShell implementation | `engine/<domain>/` |
| Stable backend entry scripts/config/templates/tools | `Pipeline/` |
| Release/package scripts | `scripts/release/` |
| Developer/agent helper scripts | `scripts/dev/` |
| Operator helper scripts | `scripts/operator/` |
| Tauri shell source and shell checks | `DesktopApp/tauri_shell/` |
| Smoke wrappers | `SmokeTests/` |
| Active docs | existing `Docs/<topic>/` folders |
| Release metadata | `changes/` and `release/` |
| Large release artifacts | outside the repo, for example `C:\MediaPipelineReleases\V6.0.0\` |

## Document Placement Helper

Use the developer helper before adding or moving active docs:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\suggest_doc_location.py --title "Unsigned manual update runbook" --kind operator
```

The script should recommend an existing `Docs/` topic folder when confidence is
high. It should print a warning and require human choice when the title/content
is ambiguous, looks like a new top-level status/checklist/report, or appears to
belong in archive/history rather than active docs.

## Out Of Scope

- No root launcher shims.
- No new `Pipeline/Modules` implementation files.
- No movement of authoritative JSON state, pending-publish manifests, completed
  manifests, source media, output media, scratch files, or sidecars.
- No package behavior change until Phase 4.

## Steps

1. Inventory proposed new docs/scripts before adding them.
2. Run the document placement helper for any new Markdown file.
3. Put large built artifacts outside the repo.
4. Keep release output folders named with `V6.0.0`.
5. Update inventories only when actual layout rules change.

## Validation

Minimum:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\suggest_doc_location.py --title "Release foundation phase plan" --kind implementation
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_architecture_guardrails.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py
```

If this phase changes only docs and helper tooling, do not run real-media
validation.

