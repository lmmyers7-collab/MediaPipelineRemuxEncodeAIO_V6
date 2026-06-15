# Worker Review: worker-12-docs-generated-unknown

## Scope

- Worker ID: `worker-12-docs-generated-unknown`
- Assigned slice: W12 docs/generated/unknown.
- Assigned files: 153 paths from `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`.
- Review focus: active generated docs, unknown-domain source/config entries, inventories that encode route/test/operator behavior, root/project metadata, stale launcher/path guidance, unsafe media/source guidance, and generated drift.
- Required first reads completed: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, and `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`.

## Coverage Ledger

| Area | Coverage | Evidence |
|---|---:|---|
| W12 assignment list | 153/153 summary-first reviewed | Parsed W12 table: 57 active-doc/generated-doc, 11 contract/config, 85 code-symbol paths. |
| Generated summaries | 153/153 assigned paths have summaries | Summary existence check found 0 missing summaries for assigned W12 paths. |
| Active docs and inventories | Search/targeted line review | Scanned for legacy launchers, removed `app`/`DesktopApp`/`Pipeline` paths, unsafe source/publish wording, and route inventory drift. |
| Unknown-domain source/config | Summary/search review; targeted full-source for high-signal modules | Opened full source for file opening, folder policy, schedule state, sample validation append, UI preferences, release planning, and guardrail/risky registry helpers. |
| Generated drift checks | Read-only validators | Ran `refresh_summaries --check`, `generate_project_index --check`, `generate_pipeline_map --check`, WebView generated checks, route inventory test, risky registry check, lifecycle/config/stage schema checks. |
| Media/source safety wording | Search/targeted review | No assigned active doc told operators or agents to bypass source preservation, pending publish park/drain, or backend mutation boundaries. |

Coverage is complete for W12 at summary/search/validator level and partial for line-by-line full-source review. I did not fully read every large active Markdown file end to end.

## Findings Summary

| ID | Severity | File / section | Problem |
|---|---|---|---|
| W12-001 | Medium | `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`, `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | Local API route inventories and mutation matrix omit five active Tdarr Matrix routes. |
| W12-002 | Medium | `docs/generated/*`, `docs/generated/summaries/**`, WebView generated guard files | Generated context is stale across summaries, project index, dependency graph, pipeline map, and WebView guard baselines. |
| W12-003 | Medium | `docs/generated/PROJECT_INDEX.md`, `docs/generated/summaries/src/mediapipeline/**` | Active source domains are misclassified as `unknown`, including 82 current `src/mediapipeline` paths. |
| W12-004 | Medium | `docs/architecture/MODULE_MAP.md`, `docs/README_MediaPipelineRemuxEncodeAIO.md`, `docs/generated/FEATURE_FILE_MAP.md`, `docs/testing/VALIDATION_LADDER_RUNBOOK.md` | Active guidance still directs agents/operators to removed `app`, `DesktopApp`, `Pipeline`, and `ui_web` paths. |
| W12-005 | Medium | `docs/inventories/GOD_FILE_GUARDRAIL.v1.json` | God-file guardrail policy does not include current `src/mediapipeline/**/*.py` source, so oversized current Python files pass unexamined. |
| W12-006 | Medium | `docs/inventories/RISKY_FILE_REGISTRY.v1.json` | Risky file registry validation fails because `docs/generated/summaries/**` matches no files under the validator. |

## Detailed Findings

### W12-001 - Route inventories omit active Tdarr Matrix routes

- Severity: Medium
- File / section: `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`, `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Evidence: `PYTHONPATH=src .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_route_inventory -q` fails all three inventory/matrix assertions. Missing contract routes are `GET /api/diagnostics/tdarr-matrix/latest`, `GET /api/diagnostics/tdarr-matrix/runs`, `GET /api/diagnostics/tdarr-matrix/compare`, `POST /api/diagnostics/tdarr-matrix/evidence/open`, and `POST /api/diagnostics/tdarr-matrix/rerun`. The docs currently list only `POST /api/diagnostics/tdarr-matrix-audit`.
- Impact: Operator and agent route inventories understate the Local API surface, and the evidence/mutation matrix misses two POST routes. That weakens route ownership review and mutation-boundary review for Diagnostics.
- Fix direction: Regenerate or update all three docs from `LOCAL_API_ROUTE_CONTRACT`, including route type, owner, command/evidence semantics, tests, and mutation boundary for the new Tdarr Matrix read/command routes.
- Validation: Rerun `PYTHONPATH=src .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_route_inventory -q` and confirm all three assertions pass.

### W12-002 - Generated context artifacts are stale

- Severity: Medium
- File / section: `docs/generated/PROJECT_INDEX.md`, `docs/generated/DEPENDENCY_GRAPH.md`, `docs/generated/PIPELINE_MAP.md`, `docs/generated/summaries/**`, `docs/generated/WEBVIEW_*`
- Evidence: `refresh_summaries --check` reports 2 missing summaries and 62 stale summaries, including W12-owned docs/inventories/generated JSON files. `generate_project_index --check` reports `docs/generated/PROJECT_INDEX.md` stale, with expected source count 1408 versus current 1296, and `docs/generated/DEPENDENCY_GRAPH.md` stale. `generate_pipeline_map --check` reports stale `app/contracts/stages.py` and `app/<domain>` paths that should be `src/mediapipeline/...`. WebView checks report stale `WEBVIEW_GODFILE_SPLIT_MAP.md`, `WEBVIEW_PUBLIC_CONTRACT_BASELINE.json`, `WEBVIEW_SPLIT_CANDIDATES.json`, `WEBVIEW_ROUTE_OWNERSHIP_GUARD.json`, and an ESLint budget drift of 649 warnings versus a budget of 644.
- Impact: The repo's generated navigation layer is no longer a reliable audit source. Agents using `PROJECT_INDEX.md`, summaries, or WebView guard baselines can miss new files, follow removed paths, or trust stale warning budgets.
- Fix direction: Refresh summaries, project index/dependency graph, pipeline map, and WebView generated guard artifacts after deciding whether new lint warnings should be fixed or budgeted. Keep packet coverage for regenerated outputs.
- Validation: Rerun `refresh_summaries --check`, `generate_project_index --check`, `generate_pipeline_map --check`, and `npm run webview:prework:check`.

### W12-003 - Active source modules are still classified as `unknown`

- Severity: Medium
- File / section: `docs/generated/PROJECT_INDEX.md`; generated summaries under `docs/generated/summaries/src/mediapipeline/**`
- Evidence: The W12 assignment includes 82 active `src/mediapipeline` paths with domain `unknown`: `core/kernel` (27), `core/maintenance` (14), `core/folder_policy` (7), `core/paths` (7), `core/schedule` (7), plus `files`, `shared`, `sample_validation`, `application`, `ui`, `validation`, and `pipeline/__init__.py`. Representative summaries such as `src/mediapipeline/core/maintenance/change_ledger.py`, `src/mediapipeline/core/paths/service.py`, `src/mediapipeline/core/schedule/facade.py`, and `src/mediapipeline/core/folder_policy/service.py` also show `owner_domain: unknown`.
- Impact: Function/module audit assignment and generated navigation can route behavior-bearing source modules to the docs/unknown worker instead of the owning backend domain worker. That creates review blind spots for maintenance, paths, schedule, folder policy, and shared/kernel behavior.
- Fix direction: Extend the owner-domain classifier used by summary/index generation to cover the current domain folders, then regenerate summaries and `PROJECT_INDEX.md`.
- Validation: Rerun summary/index generation checks and verify the `unknown` count no longer includes active `src/mediapipeline/core/<domain>` packages with clear owners.

### W12-004 - Active guidance still points to removed layout paths

- Severity: Medium
- File / section: `docs/architecture/MODULE_MAP.md`, `docs/README_MediaPipelineRemuxEncodeAIO.md`, `docs/generated/FEATURE_FILE_MAP.md`, `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- Evidence: `docs/architecture/MODULE_MAP.md` instructs new route/feature work to use `app/api/commands_*.py`, `app/<domain>/`, `src/mediapipeline/desktop/ui_web/`, and `PipelineProcessing.ps1`. `docs/README_MediaPipelineRemuxEncodeAIO.md` lists `DesktopApp\` and `Pipeline\` as top-level layout and links `Pipeline\NEW_PC_CHECKLIST_MediaPipelineRemuxEncodeAIO.md`, `Pipeline\README_MediaPipelineRemuxEncodeAIO_Deployment.md`, and `DesktopApp\docs\README.md`; those roots do not exist in the current workspace. `docs/generated/FEATURE_FILE_MAP.md` maps active features to removed `app/sample_validation`, `app/diagnostics`, `app/maintenance`, and `app/publish` files. `docs/testing/VALIDATION_LADDER_RUNBOOK.md` still references temporary `Pipeline\Modules\*.ps1` compatibility shims.
- Impact: These are active docs, so future agents/operators can create files in removed locations, miss current implementations under `src/mediapipeline/core`, or trust nonexistent setup/deployment docs. This directly conflicts with `AGENTS.md` and `docs/CURRENT_PROJECT_STATE.md`.
- Fix direction: Rewrite or archive the stale active guidance. Active docs should name `src/mediapipeline/core/<domain>`, `src/mediapipeline/desktop`, `apps/desktop/webview/static`, `ops/pipeline/entrypoints/MediaPipeline/`, and `ops/pipeline/engine/<domain>`.
- Validation: Run active-doc reference checks after unrelated concurrent review files are clean, plus targeted file-existence checks for every launcher/path named in active operator docs.

### W12-005 - God-file guardrail misses current Python source

- Severity: Medium
- File / section: `docs/inventories/GOD_FILE_GUARDRAIL.v1.json`
- Evidence: The policy includes `app/**/*.py`, `DesktopApp/**/*.py`, `scripts/**/*.py`, and `Pipeline/**/*.ps1`, but not `src/mediapipeline/**/*.py`. `Test-Path` confirms `app`, `DesktopApp`, and `Pipeline` roots are absent. A current oversized file exists at `src/mediapipeline/core/library/route_map.py` with 1068 lines, but `check_godfiles --paths src/mediapipeline/core/library/route_map.py --new --json` returns `ok: true` with no findings because the path is not included by policy.
- Impact: The guardrail intended to prevent new/expanded god files does not cover the current Python package layout, so the split campaign can regress without warning.
- Fix direction: Replace removed-root globs with current roots such as `src/mediapipeline/**/*.py` and broaden `ops/scripts/**/*.ps1` as intended. Add a policy test proving representative current source paths are included.
- Validation: Rerun `check_godfiles --all --strict` or targeted `--paths` checks against current `src/mediapipeline` files and confirm oversized files are reported.

### W12-006 - Risky file registry summary glob fails validation

- Severity: Medium
- File / section: `docs/inventories/RISKY_FILE_REGISTRY.v1.json`
- Evidence: `check_risky_file_registry` fails with `RISK010: ai_guardrails_and_generated_context: path_glob matched no files: docs/generated/summaries/**`. In the current repo, `Path.glob("docs/generated/summaries/**")` yields 0 files, while `Path.glob("docs/generated/summaries/**/*.md")` yields 1408 files.
- Impact: A required guardrail in `.pre-commit-config.yaml` and the GitHub workflow fails, and the risky-file registry cannot prove generated summary files are covered by the AI/generated-context risk entry.
- Fix direction: Change the registry glob to a file-matching pattern such as `docs/generated/summaries/**/*.md`, or update the validator to treat directory-recursive globs as file-bearing. Add a focused test for this registry entry.
- Validation: Rerun `check_risky_file_registry` and `tests.python.tooling.test_risky_file_registry`.

## Test Coverage Gaps

- Route inventory tests correctly catch the Tdarr Matrix route drift, but the generated docs were still stale at review time.
- God-file guard tests validate schema shape and a WebView allowlist only; they do not prove current `src/mediapipeline/**/*.py` files are included.
- Risky registry tests did not prevent the non-file-matching `docs/generated/summaries/**` pattern from landing.
- Generated context checks exist in pre-commit/CI, but the current workspace fails them, so the generated layer has drifted despite the guardrails.
- Active-doc reference checks do not currently catch several removed-path references, or they were blocked first by unrelated concurrent review files.

## Boundary Risks

- No reviewed W12 file instructed operators to delete/overwrite source media or bypass pending-publish park/drain evidence.
- The route inventory drift hides active Diagnostics POST routes from the mutation matrix, which is a boundary-documentation risk even if the routes are backend-owned.
- Stale active docs that tell agents to add code under removed `app`, `DesktopApp`, or `Pipeline` paths can reintroduce legacy surfaces that `AGENTS.md` explicitly forbids.
- Stale generated summaries/indexes can cause future workers to miss high-risk code after media-policy or route changes.

## Files Reviewed With No Findings

Summary/search reviewed with no direct finding recorded:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/FILE_LIFECYCLE_MAP.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`
- `docs/architecture/QUEUE_SOURCE_SCAN_AND_CURATION_PLAN.md`
- `docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`
- `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- `docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`
- `docs/RealMediaValidationRuns/README.md`
- `docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`
- `docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`
- `docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- `docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`
- `docs/testing/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md`
- `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- `docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`
- `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- `.github/workflows/phase1-drift.yml`
- `.pre-commit-config.yaml`
- `package.json`
- `eslint.config.js`

Targeted full-source reviewed with no direct finding recorded:

- `src/mediapipeline/core/files/open_plan.py`
- `src/mediapipeline/core/files/opening.py`
- `src/mediapipeline/core/folder_policy/file_io.py`
- `src/mediapipeline/core/folder_policy/io.py`
- `src/mediapipeline/core/folder_policy/service.py`
- `src/mediapipeline/core/kernel/runtime/subprocess_runner.py`
- `src/mediapipeline/core/maintenance/release_plan.py`
- `src/mediapipeline/core/sample_validation/policy.py`
- `src/mediapipeline/core/schedule/app_state.py`
- `src/mediapipeline/core/ui_preferences.py`

## Files Marked Out Of Scope

- `src/mediapipeline/contracts/schemas/stages.v1.schema.json`: `generate_stage_schema --check` failed because `fallback_remux` is missing from `size_guard_mode`, but this schema is not listed in W12 assignments.
- `docs/reviews/function-module-audit-2026-06-11/FINDINGS_REGISTER.md` and other workers' reports: active-doc reference check failures came from concurrent review artifacts outside this worker output.
- Implementation fixes for Tdarr Matrix routes, WebView lint warnings, and summary/index generators are out of scope for this review-only worker.

## Incomplete Coverage

- I did not perform end-to-end operator GUI validation or real-media validation; this was a review-only documentation/generated/unknown-domain audit.
- I did not fully read every large Markdown inventory/changelog line by line. Coverage for those files is summary-first plus targeted searches and validators.
- I did not regenerate any stale artifact because the user explicitly requested review-only and no aggregate file edits.
- Full-source review was targeted to high-signal W12 source/config modules, not all 85 code-symbol assigned files.
