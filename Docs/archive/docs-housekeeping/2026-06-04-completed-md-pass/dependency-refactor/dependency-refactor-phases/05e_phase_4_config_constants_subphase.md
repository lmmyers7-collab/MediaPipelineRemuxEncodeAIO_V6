# Phase 4E - Config Constants

Previous: [05d_phase_4_protocol_ownership_subphase.md](05d_phase_4_protocol_ownership_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves config-owned option, schema, and profile constants
out of direct `app.shared.constants` consumers and into the config boundary.

It does not change settings save behavior, media policy, queue behavior,
publish/drain behavior, source movement, cleanup, process lifecycle behavior,
rename behavior, FFmpeg policy, subtitle policy, audio policy, or WebView/Tauri
ownership.

## Inventory Baseline

Baseline command:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
```

Checker baseline before this sub-phase:

| Import group | App import entries |
|---|---:|
| `app.shared` | 0 |
| `app.shared.utils` | 22 |
| `app.shared.constants` | 35 |
| `app.shared.protocols` | 0 |

The targeted config constant imports were:

| Symbol or constant | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `AUDIO_PASSTHROUGH_PROFILE_CODECS` | `app.shared.constants` | 2 | config option/profile constant | `app.config.constants` |
| `AUDIO_PASSTHROUGH_PROFILE_DEFAULT` | `app.shared.constants` | 2 | config option/profile constant | `app.config.constants` |
| `AUDIO_PASSTHROUGH_PROFILE_NAMES` | `app.shared.constants` | 1 | config option/profile constant | `app.config.constants` |
| `LOG_LEVEL_VALUES` | `app.shared.constants` | 1 | config option constant | `app.config.constants` |
| `ROUTE_THRESHOLD_MODE_NAMES` | `app.shared.constants` | 1 | config option constant | `app.config.constants` |
| `ROUTING_PROFILE_NAMES` | `app.shared.constants` | 1 | config option constant | `app.config.constants` |
| `SIZE_GUARD_MODE_NAMES` | `app.shared.constants` | 1 | config option constant | `app.config.constants` |
| `PROFILE_NAME_PATTERN` | `app.shared.constants` | 1 | config profile-name constant | `app.config.constants` |
| `CONFIG_SCHEMA_VERSION` | `app.shared.constants` | 1 | config schema contract | `app.contracts.config` |

The compatibility service module also imported `CONFIG_SCHEMA_VERSION` and
`LOG_LEVEL_VALUES` from `app.shared.constants`; those imports were repointed to
their owning modules while leaving the service module globals available.

## Sub-Phase Definition

```text
Sub-phase: 4E - Config constants
Symbols targeted: config option/profile constants and config schema version imports from app.shared.constants
Current import count: 35 app.shared.constants entries before the sub-phase
Target owner: app.config.constants for option/profile constants; app.contracts.config for CONFIG_SCHEMA_VERSION
Risk category: low/medium; constants-only move, but audio/routing/settings-save surfaces are sensitive and behavior must stay identical
Files expected: app.config constants owner; config option, preview, profiles, metadata policy consumers; service compatibility import; focused config tests; summaries and docs
Validation: focused config tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after app.config no longer imports app.shared.constants and the checker records the reduced constants count
```

## Handoff

```text
Sub-phase: 4E - Config constants
Status: Complete
Files changed: app/config/constants.py; app/config/option_policy.py; app/config/preview.py; app/config/profiles.py; app/config/metadata_parts/policy.py; DesktopApp/mediapipeline_desktop_app/services.py; DesktopApp/tests/test_service_config_option_policy.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05e_phase_4_config_constants_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Config option/profile constants and schema-version imports were repointed to config/contract owners with values preserved. Settings save helpers, open-path normalization, audio policy, and routing behavior were not changed.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_config_option_policy.py DesktopApp\tests\test_service_config_preview.py DesktopApp\tests\test_service_config_profiles.py DesktopApp\tests\test_config_keys.py tests\contract\test_config_contract.py (34 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed, 752 source files current); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed; CRLF normalization warnings only).
Dependency checker result: app.shared.constants imports dropped from 35 to 24; app.shared.utils remains 22; app.shared.protocols remains 0; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 752 summaries.
Summaries refreshed: Targeted refresh wrote 7 summaries for the Phase 4E touched source and test files. Final .\scripts\dev\refresh_summaries.py --check reported 752 source files current with no orphan summaries.
Known risks: app.shared.constants still contains dead config constant exports until the planned 4L final shared-shrink pass. The compatibility service still imports other non-config app.shared.constants symbols for later process/file/rename/folder-policy sub-phases.
Remaining shared hotspots: app.shared.utils has 22 app import entries; app.shared.constants has 24 app import entries after this pass across process, file/media, rename, folder-policy, failure, and storage constants; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later shrink/final cleanup pass.
Next: Continue Phase 4 with 4F process runtime state; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
