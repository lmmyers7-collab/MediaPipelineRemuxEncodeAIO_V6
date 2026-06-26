# Worker Review: W12-docs-generated-unknown

## Scope
- Assigned domain: docs-generated-unknown
- Assigned files: 153 files from the original generated assignment list.
- Explicit exclusions: none intentionally excluded. Coverage is partial because the time box ended before full source/body review for every assigned file.
- Edit policy followed: only this W12 ledger was edited.

## Review Method Used
- Read required session entry docs: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, and `docs/generated/PROJECT_INDEX.md`.
- Read every available generated summary for the 153 assigned files before opening full source.
- Ran targeted `rg` scans across assigned files for stale layout names, removed launcher/module paths, hardcoded local paths, mutation verbs, design-only/future/stale language, and source/scratch/output guardrail wording.
- Opened full or targeted source for the files needed to verify findings and sampled high-risk Python helpers in the W12 code group.
- Did not implement fixes, commit, or mutate runtime/media state.

## Commands / Evidence
- `mediapipeline.tools.dev.generate_pipeline_map --check`: failed; `docs/generated/PIPELINE_MAP.md` is stale and still names `app/contracts/stages.py` plus `app/<domain>` paths where expected output uses `src/mediapipeline/...`.
- `mediapipeline.tools.dev.generate_project_index --check`: failed; `docs/generated/PROJECT_INDEX.md` and `docs/generated/DEPENDENCY_GRAPH.md` are stale. Expected source count was 1408 vs current 1296.
- `mediapipeline.tools.dev.check_active_doc_references`: passed, despite active docs still containing stale removed-layout guidance. This is a guardrail gap.
- `npm run webview:prework:check`: launched in the interrupted parallel batch, but no result was returned before the user time-box update. No conclusion recorded from it.

## Coverage Ledger

| File / group | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|
| `.github/workflows/phase1-drift.yml` | 1 workflow | complete | Full file reviewed. No finding; generated drift gates exist. |
| `.pre-commit-config.yaml` | 18 hooks | complete | Full file reviewed. No finding; generated, naming, active-doc, change-packet, typing, and PowerShell hooks are present. |
| `AGENTS.md` | active agent rules | complete | Full entry doc reviewed. No finding. |
| `docs/CURRENT_PROJECT_STATE.md` | active state sections | partial | Required entry read plus targeted search. No finding in inspected sections. |
| `docs/architecture/ARCHITECTURE.md` | top-level architecture map | complete | Full file reviewed. No finding; current promoted paths mostly match actual layout. |
| `docs/architecture/MODULE_MAP.md` | layer map, feature-add guidance, state table | partial | Targeted full-section review found stale active guidance. See W12-002. |
| `docs/architecture/QUEUE_SOURCE_SCAN_AND_CURATION_PLAN.md` | queue scan plan, examples, validation | partial | Targeted sections reviewed. No finding; hardcoded `LAYNE-SERVER` paths are presented as dated investigation examples, not defaults. |
| `docs/README_MediaPipelineRemuxEncodeAIO.md` | operator bundle README | complete | Full file reviewed. See W12-001. |
| `docs/testing/VALIDATION_LADDER_RUNBOOK.md` | PowerShell/media validation rungs | partial | Targeted sections reviewed. Found stale `Pipeline\Modules` wording but less severe than W12-001/002. |
| `docs/generated/FEATURE_FILE_MAP.md` | feature inventory | partial | Targeted generated inventory review found stale promoted-layout drift. See W12-004. |
| `docs/generated/FILE_SUMMARIES.md` | summary system guide | complete | Full file reviewed. No finding. |
| `docs/generated/PIPELINE_MAP.md` | stage inventory | complete | Full file reviewed and generator check failed. See W12-003. |
| `package.json` | npm scripts/dependencies | complete | Full file reviewed. No finding. |
| `eslint.config.js` | ESLint config | complete | Full file reviewed. No finding. |
| `src/mediapipeline/core/files/open_plan.py` | VLC/explorer argument helpers | complete | Full file reviewed. No finding. |
| `src/mediapipeline/core/files/opening.py` | shell-open/VLC service mixin | complete | Full file reviewed. No confirmed issue; shell-open stays backend-owned and path-existence checked. |
| `src/mediapipeline/core/paths/layout.py` | path containment helpers | complete | Full file reviewed. No finding; root/reparse checks are present for mutation boundary helpers. |
| `src/mediapipeline/core/paths/service.py` | path-resolution facade mixin | complete | Full file reviewed. No finding. |
| `src/mediapipeline/core/paths/resolution_runner.py` | resolved path builder | complete | Full file reviewed. No finding; noted config snapshot write during resolution as existing backend-owned state behavior. |
| `src/mediapipeline/core/ui_preferences.py` and `src/mediapipeline/core/ui/preferences.py` | UI preference persistence | partial | Full `ui_preferences.py` reviewed; package export wrapper only summary-reviewed. No finding. |
| `src/mediapipeline/core/folder_policy/*` | contracts, io, probe, service | partial | Full contracts/io/probe/service reviewed. No confirmed issue; `validate_folder_policy` can write sidecar validation state, but no active route caller was found in the time box. |
| `src/mediapipeline/core/sample_validation/policy.py` | preview/append policy | complete | Full file reviewed. No finding; append remains evidence-only and guarded by preview errors. |
| Remaining assigned docs, inventories, generated WebView JSONs, kernel DTO/contracts, maintenance, network facade, schedule, shared, validation, schema JSON | summary/grep | incomplete | Summaries read and broad pattern scans run, but no full source/body review. Exact files are listed under Incomplete Coverage. |

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|
| W12-001 | P2 | `docs/README_MediaPipelineRemuxEncodeAIO.md` | active bundle README | Active operator doc still advertises removed `DesktopApp\`/`Pipeline\` layout and stale release/docs paths. | Extend active-doc reference checks to reject removed layout paths in active docs; rerun `check_active_doc_references`. |
| W12-002 | P2 | `docs/architecture/MODULE_MAP.md` | layer map / feature-add guidance | Architecture guidance directs new work into nonexistent `app/<domain>`, `Pipeline/`, and `src/mediapipeline/desktop/ui_web/` paths. | Add active-doc guard coverage for promoted `src/mediapipeline/core`, `apps/desktop/webview/static`, and `ops/pipeline` paths. |
| W12-003 | P2 | `docs/generated/PIPELINE_MAP.md` | generated stage map | Generated stage map is stale; `--check` fails and expected output replaces `app/*` references with `src/mediapipeline/*`. | Regenerate pipeline map and keep `generate_pipeline_map --check` in CI/pre-commit. |
| W12-004 | P2 | `docs/generated/FEATURE_FILE_MAP.md` | feature inventory | Generated/curated feature inventory maps many active features to nonexistent `app/*` and `Pipeline/*` paths, so agents following it will inspect or edit the wrong surface. | Regenerate or replace this map from current `PROJECT_INDEX`; add a check for nonexistent referenced paths. |
| W12-005 | P2 | `docs/generated/PROJECT_INDEX.md` | assignment/source universe | Required generated project index is stale by generator check: expected 1408 source files vs current 1296, with missing WebView, ops, tests, and release files. W12 assignment itself was generated from this stale index. | Regenerate `PROJECT_INDEX.md`/`DEPENDENCY_GRAPH.md`, rerun assignment generation, and require a clean project-index check before worker assignment. |

## Detailed Findings

### W12-001: Active README Points Operators At Removed Layout
- Severity: P2
- File: `docs/README_MediaPipelineRemuxEncodeAIO.md`
- Symbol: active bundle README
- Evidence:
  - Lines 15-16 list top-level `DesktopApp\` and `Pipeline\`, but `Test-Path DesktopApp`, `Test-Path Pipeline`, and `Test-Path app` all returned `False`; active roots are `src`, `apps`, `ops`, `tests`, and `docs`.
  - Lines 141-145 say releases include canonical `scripts\` launchers and pipeline modules, while `AGENTS.md` and current state require canonical `ops\scripts\...` launchers and `ops\pipeline\engine`.
  - Lines 158-160 point to `Pipeline\NEW_PC_CHECKLIST...`, `Pipeline\README...`, and `DesktopApp\docs\README.md`, which are absent from the promoted layout.
- Impact: Active operator onboarding can send maintainers or agents toward removed surfaces, increasing the chance of reintroducing root/legacy paths or missing the current `ops/scripts` and `apps/desktop` launcher surface.
- Suggested fix: Refresh this README against `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, and actual root directories; remove `DesktopApp\`, `Pipeline\`, and `scripts\` as active paths unless clearly marked historical.
- Suggested tests: `check_active_doc_references` should fail active docs that point to removed top-level layout paths outside explicit historical/removal context.

### W12-002: Module Map Still Teaches The Old `app`/`Pipeline` Architecture
- Severity: P2
- File: `docs/architecture/MODULE_MAP.md`
- Symbol: layer map, feature-add decision tree, state cross-reference
- Evidence:
  - Lines 42-68 identify application and service layers as `app/<domain>/` and examples like `app/queue/file_overrides.py`.
  - Lines 88 and 114 name `Pipeline/` and `src/mediapipeline/desktop/ui_web/` as active runtime/frontend roots.
  - Lines 171-176 instruct new feature work to add handlers/facades under `app/api` and `app/<domain>`.
  - Lines 301-302 say a new top-level directory under `DesktopApp/`, `Pipeline/`, or `ui_web/static/assets/` should update the map.
- Impact: This is an active architecture overview and feature-placement guide. Following it would violate current repository rules that implementation belongs under `src/mediapipeline`, WebView assets under `apps/desktop/webview/static`, and PowerShell under `ops/pipeline`.
- Suggested fix: Rewrite this map for promoted paths or convert it to a historical compatibility note. Use `src/mediapipeline/core/<domain>`, `src/mediapipeline/desktop`, `apps/desktop/webview/static`, and `ops/pipeline/entrypoints`/`ops/pipeline/engine`.
- Suggested tests: Add active-doc reference rules for `app/<domain>`, `app/api`, `Pipeline/`, `DesktopApp/`, and `ui_web` when used as current add-new-work guidance.

### W12-003: Pipeline Map Is Stale And Fails Its Own Check
- Severity: P2
- File: `docs/generated/PIPELINE_MAP.md`
- Symbol: generated stage map
- Evidence:
  - Current line 3 says generated from `app/contracts/stages.py`; `generate_pipeline_map --check` expected `src/mediapipeline/contracts/stages.py`.
  - Current lines 50, 76, 89, 128, 141, and 154 use `app/orchestration`, `app/decide`, `app/processes`, `app/publish`, and `app/rename`; the check expected `src/mediapipeline/core/...`.
  - The check command failed and printed a diff showing all stale path replacements.
- Impact: This generated file is part of the required agent read path and describes high-risk stage boundaries. Stale paths create audit drift and can hide where mutation-capable stage work actually lives.
- Suggested fix: Run the documented generator with the bundled Python/runtime and commit the regenerated map.
- Suggested tests: Keep CI/pre-commit `generate_pipeline_map --check`; fail assignment generation when this check is red.

### W12-004: Feature File Map References Nonexistent Active Files
- Severity: P2
- File: `docs/generated/FEATURE_FILE_MAP.md`
- Symbol: feature-to-file inventory
- Evidence:
  - Lines 41-45 map Local API command handlers, command results, close readiness, and UI preferences to `app/api`, `app/processes`, and `app/ui`.
  - Lines 54-66 map Launch, Queue, Completed, Pending Publish, Rename, Settings, Diagnostics, Maintenance, Network, Telemetry, Schedule, and Reports backend files to `app/*` paths.
  - Lines 75-90 map media behavior and high-risk publish/audio/subtitle/rename surfaces to `app/*`.
  - The actual root check returned no `app` directory.
- Impact: Agents and humans using the feature inventory can miss current `src/mediapipeline/core` and `src/mediapipeline/desktop` ownership, especially for high-risk queue, publish/drain, rename, settings, and media-policy work.
- Suggested fix: Regenerate or rewrite the map from current `docs/generated/PROJECT_INDEX.md` after the index is fresh. Prefer validated file existence over curated stale paths.
- Suggested tests: Add a feature-map existence check that allows globs only when at least one path exists and rejects removed top-level roots.

### W12-005: Project Index Is Stale, So Assignment Coverage Is Incomplete
- Severity: P2
- File: `docs/generated/PROJECT_INDEX.md`
- Symbol: generated source universe / assignment source
- Evidence:
  - `generate_project_index --check` failed.
  - Expected source count was 1408; current file says 1296.
  - Diff showed missing/currently unindexed files including new WebView assets, `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1`, `runtime_paths.ps1`, `startup_filesystem.ps1`, `startup_path_validation.ps1`, `ops/pipeline/tests/Unit/Invoke-ProgressStateTelemetryChecks.ps1`, and additional release packets.
- Impact: The 2026-06-11 worker assignments were generated from the stale index, so this audit cannot claim repository-wide coverage. New files may have no worker owner or summary row.
- Suggested fix: Regenerate `PROJECT_INDEX.md` and `DEPENDENCY_GRAPH.md`, then regenerate worker assignments or explicitly audit the delta files.
- Suggested tests: Make assignment generation require clean `generate_project_index --check` and summary freshness first.

## Test Coverage Gaps
- `check_active_doc_references` passed while `docs/README_MediaPipelineRemuxEncodeAIO.md` and `docs/architecture/MODULE_MAP.md` still use removed current-layout paths. The active-doc checker needs stricter context-aware stale-path rules.
- `FEATURE_FILE_MAP.md` appears to lack a file-existence guard. It can reference hundreds of nonexistent `app/*` files without failing the checks run in this time box.
- The worker assignment process did not appear to require a clean `PROJECT_INDEX.md` check first; the assignment source was stale by 112 files.
- WebView generated JSON artifacts (`WEBVIEW_*`) were not validated in this time box because `npm run webview:prework:check` was interrupted before returning.

## Boundary Risks
- Active docs that teach `app/<domain>` and `Pipeline/` as current paths conflict with the hard AGENTS rules forbidding new loose/root implementation and new `Pipeline/Modules` files.
- No confirmed Python behavior bug was found in the sampled `files`, `paths`, `folder_policy`, `ui_preferences`, and `sample_validation` helpers.
- `FolderPolicyServiceMixin.validate_folder_policy()` writes validation state to `mediapipeline.folder.json` after successful probe validation. No active route caller was found during this time box, but this should remain backend-owned and clearly documented if exposed later.

## Files With No Findings
- `.github/workflows/phase1-drift.yml`
- `.pre-commit-config.yaml`
- `AGENTS.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/generated/FILE_SUMMARIES.md`
- `eslint.config.js`
- `package.json`
- `src/mediapipeline/core/files/open_plan.py`
- `src/mediapipeline/core/files/opening.py`
- `src/mediapipeline/core/folder_policy/contracts.py`
- `src/mediapipeline/core/folder_policy/file_io.py`
- `src/mediapipeline/core/folder_policy/io.py`
- `src/mediapipeline/core/folder_policy/probe.py`
- `src/mediapipeline/core/folder_policy/service.py`
- `src/mediapipeline/core/paths/layout.py`
- `src/mediapipeline/core/paths/resolution_runner.py`
- `src/mediapipeline/core/paths/service.py`
- `src/mediapipeline/core/sample_validation/policy.py`
- `src/mediapipeline/core/ui_preferences.py`

## Incomplete Coverage

Summaries were read and broad pattern scans were run, but full source/body review was not completed for these assigned files:

- `CHANGELOG.md`
- `docs/architecture/CONFIG_KEY_GLOSSARY.md`
- `docs/architecture/FILE_LIFECYCLE_MAP.md`
- `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`
- `docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`
- `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
- `docs/ARCHIVED_MD_INDEX.md`
- `docs/change_control/CHANGE_INDEX.md`
- `docs/change_control/CHANGE_PACKET_SCHEMA.md`
- `docs/change_control/CHANGELOG.md`
- `docs/change_control/CURRENT_VERSION.md`
- `docs/change_control/README.md`
- `docs/change_control/RELEASE_PROCESS.md`
- `docs/DOCS_INDEX.md`
- `docs/generated/WEBVIEW_DOM_ID_GAP_REPORT.json`
- `docs/generated/WEBVIEW_ESLINT_WARNING_BUDGET.json`
- `docs/generated/WEBVIEW_GODFILE_SPLIT_MAP.md`
- `docs/generated/WEBVIEW_PUBLIC_CONTRACT_BASELINE.json`
- `docs/generated/WEBVIEW_ROUTE_OWNERSHIP_GUARD.json`
- `docs/generated/WEBVIEW_SPLIT_CANDIDATES.json`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/inventories/GOD_FILE_GUARDRAIL.v1.json`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/inventories/PACKAGING_DEPENDENCY_INVENTORY.md`
- `docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`
- `docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- `docs/inventories/RENAME_SAFETY_TEST_INVENTORY.md`
- `docs/inventories/RENAME_TOOL_EDGE_CASE_CATALOG.md`
- `docs/inventories/RISKY_FILE_REGISTRY.v1.json`
- `docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md`
- `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
- `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`
- `docs/inventories/SMOKE_TEST_INVENTORY.md`
- `docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md`
- `docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md`
- `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`
- `docs/RealMediaValidationRuns/README.md`
- `docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`
- `docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- `docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`
- `docs/testing/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md`
- `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- `docs/testing/TEST_COVERAGE_MATRIX.md`
- `docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`
- `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- `src/mediapipeline/contracts/schemas/risky_file_registry.v1.schema.json`
- `src/mediapipeline/core/__init__.py`
- `src/mediapipeline/core/application/__init__.py`
- `src/mediapipeline/core/application/utilities.py`
- `src/mediapipeline/core/files/__init__.py`
- `src/mediapipeline/core/files/constants.py`
- `src/mediapipeline/core/folder_policy/__init__.py`
- `src/mediapipeline/core/folder_policy/constants.py`
- `src/mediapipeline/core/kernel/__init__.py`
- `src/mediapipeline/core/kernel/config_key_aliases.py`
- `src/mediapipeline/core/kernel/config_key_groups.py`
- `src/mediapipeline/core/kernel/config_key_order.py`
- `src/mediapipeline/core/kernel/config_keys.py`
- `src/mediapipeline/core/kernel/config_locations.py`
- `src/mediapipeline/core/kernel/contracts/__init__.py`
- `src/mediapipeline/core/kernel/contracts/active_job.py`
- `src/mediapipeline/core/kernel/contracts/base.py`
- `src/mediapipeline/core/kernel/contracts/completed_job.py`
- `src/mediapipeline/core/kernel/contracts/control_flag.py`
- `src/mediapipeline/core/kernel/contracts/pending_publish.py`
- `src/mediapipeline/core/kernel/contracts/pipeline_events.py`
- `src/mediapipeline/core/kernel/contracts/process_result.py`
- `src/mediapipeline/core/kernel/contracts/progress.py`
- `src/mediapipeline/core/kernel/contracts/queue_snapshot.py`
- `src/mediapipeline/core/kernel/dto.py`
- `src/mediapipeline/core/kernel/dto_base.py`
- `src/mediapipeline/core/kernel/dto_commands.py`
- `src/mediapipeline/core/kernel/dto_inventory.py`
- `src/mediapipeline/core/kernel/dto_status.py`
- `src/mediapipeline/core/kernel/dto_workspaces.py`
- `src/mediapipeline/core/kernel/models.py`
- `src/mediapipeline/core/kernel/models_core.py`
- `src/mediapipeline/core/kernel/models_media_paths.py`
- `src/mediapipeline/core/kernel/runtime/__init__.py`
- `src/mediapipeline/core/kernel/runtime/subprocess_runner.py`
- `src/mediapipeline/core/maintenance/__init__.py`
- `src/mediapipeline/core/maintenance/backfill_facade.py`
- `src/mediapipeline/core/maintenance/change_ledger.py`
- `src/mediapipeline/core/maintenance/command_policy.py`
- `src/mediapipeline/core/maintenance/commands_facade.py`
- `src/mediapipeline/core/maintenance/dependency_atlas.py`
- `src/mediapipeline/core/maintenance/dependency_atlas_facade.py`
- `src/mediapipeline/core/maintenance/facade.py`
- `src/mediapipeline/core/maintenance/file_io.py`
- `src/mediapipeline/core/maintenance/policy.py`
- `src/mediapipeline/core/maintenance/release.py`
- `src/mediapipeline/core/maintenance/release_facade.py`
- `src/mediapipeline/core/maintenance/release_plan.py`
- `src/mediapipeline/core/maintenance/release_result.py`
- `src/mediapipeline/core/network/__init__.py`
- `src/mediapipeline/core/network/facade.py`
- `src/mediapipeline/core/paths/__init__.py`
- `src/mediapipeline/core/paths/contracts.py`
- `src/mediapipeline/core/paths/defaults.py`
- `src/mediapipeline/core/paths/host.py`
- `src/mediapipeline/core/sample_validation/__init__.py`
- `src/mediapipeline/core/sample_validation/facade.py`
- `src/mediapipeline/core/schedule/__init__.py`
- `src/mediapipeline/core/schedule/app_state.py`
- `src/mediapipeline/core/schedule/constants.py`
- `src/mediapipeline/core/schedule/facade.py`
- `src/mediapipeline/core/schedule/file_io.py`
- `src/mediapipeline/core/schedule/grid.py`
- `src/mediapipeline/core/schedule/policy.py`
- `src/mediapipeline/core/shared/__init__.py`
- `src/mediapipeline/core/shared/constants.py`
- `src/mediapipeline/core/shared/protocols.py`
- `src/mediapipeline/core/shared/utils.py`
- `src/mediapipeline/core/ui/__init__.py`
- `src/mediapipeline/core/ui/preferences.py`
- `src/mediapipeline/core/validation/__init__.py`
- `src/mediapipeline/core/validation/boundary.py`
- `src/mediapipeline/pipeline/__init__.py`

Not reviewed at all beyond the initially read summary/path grep because of the time-box update:
- WebView generated JSON internals (`WEBVIEW_*` files)
- Kernel DTO/model/contract symbol semantics
- Maintenance command/release/dependency-atlas behavior
- Schedule grid/policy behavior
- Network facade behavior
- Risky-file registry schema conformance
