# Phase 4H - Publish Pending Reads

Previous: [05g_phase_4_queue_ownership_subphase.md](05g_phase_4_queue_ownership_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves pending-publish JSON read helper ownership out of
`app.shared.utils` and into the publish domain.

It does not change pending-publish park/drain behavior, manifest schema,
manifest row classification, duplicate target detection, pending root scanning,
drain summary path resolution, queue behavior, settings persistence, source
movement, cleanup, process lifecycle behavior, rename behavior, FFmpeg policy,
subtitle policy, audio policy, media policy, or WebView/Tauri ownership.

## Inventory Baseline

Baseline command:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
```

Checker baseline before this sub-phase:

| Import group | App import entries |
|---|---:|
| `app.shared` | 0 |
| `app.shared.utils` | 15 |
| `app.shared.constants` | 17 |
| `app.shared.protocols` | 0 |

The targeted publish imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `_read_json_file` | `app.shared.utils` | 2 | pending-publish manifest and drain-summary JSON read helper | `app.publish.file_io` |

## Sub-Phase Definition

```text
Sub-phase: 4H - Publish pending reads
Symbols targeted: pending-publish JSON read helper
Current import count: 15 app.shared.utils entries before the sub-phase
Target owner: app.publish.file_io
Risk category: high boundary, mechanical read-helper move only; pending-publish drain and manifest mutation behavior is protected
Files expected: publish file IO owner; pending manifest and pending service consumers; refreshed summaries and docs
Validation: focused pending-publish service/facade/policy tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after app.publish has no direct app.shared.* imports and the checker records the reduced shared-utils count
```

## Handoff

```text
Sub-phase: 4H - Publish pending reads
Status: Complete
Files changed: app/publish/file_io.py; app/publish/pending_manifest.py; app/publish/pending_service.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05h_phase_4_publish_pending_reads_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Pending manifest and pending drain summary JSON reads use the same retry count, delay, UTF-8 decode, JSON parsing, and exception behavior under the publish-owned helper. Pending-publish park/drain behavior, manifest row classification, duplicate detection, scan ordering, drain summary shape, and mutation authority were intentionally untouched.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_pending_publish_service.py DesktopApp\tests\test_application_facade_pending_publish.py DesktopApp\tests\test_facade_pending_publish_policy.py (27 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with line-ending warnings only).
Dependency checker result: app.shared.utils imports dropped from 15 to 13; app.shared.constants remains 17; app.shared.protocols remains 0; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: app.publish has no direct app.shared.* imports after this pass, but the copied JSON read helper remains duplicated until the planned 4L final shared-shrink/consolidation review. Pending-publish drain and manifest mutation paths were intentionally untouched.
Remaining shared hotspots: app.shared.utils has 13 app import entries after this pass across config save, failure cleanup, file opening, folder-policy IO, maintenance release, rename writes, and schedule app-state reads/writes; app.shared.constants has 17 app import entries across file/media, rename, folder-policy, failure, and storage constants; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later shrink/final cleanup pass.
Next: Continue Phase 4 with 4I rename ownership; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
