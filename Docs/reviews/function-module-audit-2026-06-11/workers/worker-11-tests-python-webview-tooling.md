# Worker Review: worker-11-tests-python-webview-tooling

## Scope

Assigned slice: Python/WebView tests, test helpers and fixtures, Python developer tooling under `src/mediapipeline/tools/`, and Node developer tooling under `ops/scripts/dev/*.mjs`.

Reviewed as source coverage:

| Area | Files |
|---|---:|
| `tests/python/**/*.py` | 234 |
| `tests/webview/**/*.py` | 41 |
| `src/mediapipeline/tools/**/*.py` | 34 |
| `ops/scripts/dev/*.mjs` | 10 |
| `tests/__init__.py` | 1 |
| `tests/fixtures/source_media/*.json` | 10 |

The assignment table listed 299 W11 source rows. I included 21 additional live source files that match the user scope but were not in the assignment table: the 10 `.mjs` dev tools, TDarr materializer/audit tools and tests added under `src/mediapipeline/tools/dev/` and `tests/python/*`, `tests/python/core/library/*`, `test_library_route_map_api.py`, `test_metrics_feature.py`, `test_subtitle_qa_feature.py`, and `tests/webview/test_webview_dropdown_remediation_static.py`.

## Coverage Ledger

| Check | Result |
|---|---|
| Required first reads | Completed: `AGENTS.md`, `CURRENT_PROJECT_STATE.md`, `OPEN_WORK_CHECKLIST.md`, `PROJECT_INDEX.md`, W11 assignment section. |
| Summary pre-read | 320/320 source files had generated summaries; 4 high priority, 304 medium, 12 low. Fixtures have no generated summaries and were reviewed as data. |
| Assertion scan | 0 test functions without assertions/raises/unittest assertions. |
| Skip/xfail scan | 3 Windows-only skips, all platform-specific. No xfail found. |
| Broad exception scan | 1 `BaseException` test path in `test_network_inflight_registry.py`; reviewed as intentional exception-boundary coverage. |
| Fixture scan | 10/10 JSON fixtures parsed. Source-media fixture references had no missing files; `interlaced_source.json` is covered by `test_source_media_contract.py`. |
| Warning-hardening probe | `py_compile` under `-W error::SyntaxWarning` fails on two invalid escape literals; recorded below. |
| TDarr safety probes | Two isolated temp-directory reproductions confirmed hardlink/path escape behavior without touching repo runtime or media state. |
| WebView parser probe | Node probe confirmed `parseScript()` can return recovered ASTs with `ast.errors` for duplicate lexical declarations. |

Opened source for high-priority or finding-adjacent files included:
`tests/python/core/decide/test_processing_decision.py`,
`tests/python/core/subtitles/test_ass_to_srt_helpers.py`,
`src/mediapipeline/tools/dev/materialize_tdarr_test_library.py`,
`src/mediapipeline/tools/dev/tdarr_matrix_audit.py`,
`tests/python/tooling/test_materialize_tdarr_test_library.py`,
`tests/python/tooling/test_tdarr_matrix_audit.py`,
`tests/python/tooling/test_change_control.py`,
`tests/webview/webview_browser_smoke_support.py`,
`tests/webview/test_webview_browser_high_risk_smoke.py`,
`tests/webview/test_webview_frontend_mutation_boundary.py`,
`ops/scripts/dev/webview-tooling-common.mjs`,
`ops/scripts/dev/analyze-webview-godfiles.mjs`,
`ops/scripts/dev/check-webview-assets.mjs`,
`ops/scripts/dev/check-webview-route-ownership.mjs`,
`ops/scripts/dev/check-webview-dom-id-gaps.mjs`,
`ops/scripts/dev/webview-public-contract.mjs`,
`ops/scripts/dev/webview-split-candidates.mjs`,
and `ops/scripts/dev/smoke-webview-script-order.mjs`.

## Findings Summary

| Severity | Count | Findings |
|---|---:|---|
| High | 1 | TDarr audit run materialization can write a hardlink outside the guarded run root. |
| Medium | 2 | TDarr library materializer can hardlink arbitrary inventory paths; individual WebView generated-artifact checks ignore recovered parser errors. |
| Low | 1 | Two tests fail under SyntaxWarning-as-error due invalid escape literals. |

## Detailed Findings

### F-11-01 - High - TDarr audit run materialization trusts manifest paths before writing hardlinks

File: `src/mediapipeline/tools/dev/tdarr_matrix_audit.py`

Symbol/section: `ManifestRow.from_record()` and `materialize_run_subset()`

Evidence: `ManifestRow.from_record()` copies `generated_path` directly from CSV and computes `generated_abs = library_root / generated_path` without rejecting absolute paths or `..` traversal at lines 166-179. `materialize_run_subset()` then writes each sample to `destination = run_root / row.generated_path` and hardlinks `row.source_path` into that destination at lines 649-656. The only root guard is `assert_allowed_run_root()` at lines 607-612, which checks the run directory, not each generated destination. I reproduced this in a temporary directory: a row with an absolute `generated_path` created `outside-linked.mkv` outside the allowed run root, and `os.path.samefile(source, outside)` returned true.

Impact: A stale or malicious `materialized_library.csv` can cause the audit run to create hardlinks outside `LocalBase\Scratch\TestLibraries\TdarrMatrixRuns\<run>`. Because the command then prepares queue/effective-config evidence and can run sample processing against those paths, the test harness can escape its advertised scratch boundary and can alias arbitrary local media through hardlinks. This undermines the "test library only" safety posture and can produce false confidence in real-media validation evidence.

Fix direction: Normalize and validate manifest paths when loading rows. Reject absolute `generated_path`, `..` segments, and any resolved `run_root / generated_path` outside the active run root. Also require `source_path` to resolve under the source materialized library root when consuming the source manifest. Prefer copying over hardlinking unless the source is inside the approved fixture/materialized-library root.

Validation: Add unit tests with absolute and parent-traversal `generated_path` values and external `source_path` values; assert `materialize_run_subset()` raises before creating parent directories or links. Rerun `tests/python/tooling/test_tdarr_matrix_audit.py` and the diagnostics TDarr matrix tests.

### F-11-02 - Medium - TDarr library materializer can hardlink arbitrary inventory paths into the generated test library

File: `src/mediapipeline/tools/dev/materialize_tdarr_test_library.py`

Symbol/section: `materialized_rows()` and `link_or_copy()`

Evidence: `materialized_rows()` resolves each inventory `local_path` with `resolve_repo_path(sample.local_path, repo_root=inventory_root)` at line 246. `resolve_repo_path()` accepts absolute paths unchanged, and there is no `relative_to(inventory_root)` containment check before `link_or_copy()` hardlinks by default at lines 274-281. The current materializer test confirms hardlink behavior with `os.path.samefile(first, generated_first)` at `tests/python/tooling/test_materialize_tdarr_test_library.py:179`, but there is no rejection test for absolute or `../` inventory paths. I reproduced the issue in a temporary directory: an inventory row whose `local_path` was an absolute external file produced one materialized file, and the generated file was the same hardlink as the external source.

Impact: The fixture materialization tool can silently pull non-fixture local media into a scratch test library and alias it by hardlink. A later sample run or manual inspection may then treat arbitrary production media as sanctioned Tdarr sample evidence. If any downstream operation writes through the generated hardlink, it can mutate the original file despite the repository's source-mutation boundary.

Fix direction: Treat inventory `local_path` as inventory-relative data only. Reject absolute paths and resolved paths outside `inventory_root`; add explicit tests for absolute path, `..` traversal, symlink/junction escapes where practical, and copy/hardlink modes. Consider making `copy` the safer default for test-library materialization.

Validation: Add containment tests to `tests/python/tooling/test_materialize_tdarr_test_library.py`, then rerun that test module and the TDarr audit tooling tests.

### F-11-03 - Medium - Individual WebView generated-artifact checks ignore recoverable parser errors

Files: `ops/scripts/dev/webview-tooling-common.mjs`, `ops/scripts/dev/analyze-webview-godfiles.mjs`

Symbol/section: `parseScript()`, `analyzeScriptAsset()`, and godfile analyzer parsing

Evidence: `parseScript()` enables Babel `errorRecovery: true` at `webview-tooling-common.mjs:125-131`, and `analyzeScriptAsset()` traverses the returned AST without inspecting `ast.errors` at lines 134-173. `analyze-webview-godfiles.mjs` repeats the same recovered parse mode at lines 268-275. A read-only Node probe confirmed `parseScript('const x = 1; const x = 2;')` returns an AST with `errors: ["VarRedeclaration"]` instead of throwing. The route, DOM gap, public-contract, and split-candidate scripts all consume this analysis output. `npm run webview:prework:check` mitigates the release path by running `check-webview-assets.mjs` first, but the individual `webview:*:check` generated-artifact commands can still appear current if a baseline was generated after a recoverable syntax error.

Impact: Developers can get false confidence from standalone generated-artifact checks such as `webview:contract:check`, `webview:routes:check`, `webview:dom-gaps:check`, or `webview:slices:check`; those checks may not fail on recoverable JavaScript parse errors even though the browser/runtime syntax check would fail. This weakens generated artifact drift checks when run outside the aggregate prework command.

Fix direction: Make `parseScript()` throw or return a fatal result when `ast.errors.length > 0`, or have every consumer fail with file and parser-error details. Add a Node tooling test that feeds a recoverable parser error and asserts each generated-artifact check fails.

Validation: Add a focused Node/unit smoke for duplicate lexical declarations, then run `npm run webview:prework:check` plus each individual `webview:*:check` command.

### F-11-04 - Low - Two assigned tests fail under SyntaxWarning-as-error

Files: `tests/python/desktop/test_application_facade.py`, `tests/python/desktop/test_legacy_removal_readiness.py`

Symbol/section: test fixture strings in `DummyWorkflowFacadeService.run_release_build()` and `test_pipeline_module_report_classifies_shims()`

Evidence: `test_application_facade.py:272` contains `"scripts\\ops\release\metadata\\build.ps1"`, where `\m` is an invalid Python escape. `test_legacy_removal_readiness.py:138` contains `"Compatibility shim\n. ops\pipeline\engine\\decide\\routing.ps1"`, where `\p` is invalid. A scoped probe using `py_compile` with `warnings.simplefilter('error', SyntaxWarning)` failed on exactly these two files.

Impact: The normal suite may still pass today, but warning-hardened CI, pre-commit, or a future Python version can fail before the tests run. This is a tooling reliability issue: release/test safety checks become environment-sensitive.

Fix direction: Use raw strings or double escaping for Windows-style paths in those fixture strings.

Validation: Re-run the scoped `py_compile` warning-hardening probe and the affected test modules.

## Test Coverage Gaps

- TDarr tooling tests cover happy-path hardlinking and sentinel rebuild guards, but they do not cover hostile manifest `generated_path`, external `source_path`, absolute inventory `local_path`, parent traversal, or symlink/junction escapes.
- ASS-to-SRT tests exercise helper behavior and fake loader fallback, but there is no end-to-end CLI test with a real `.ass` input file and no test proving conversion failure routes to review rather than silent publish. That broader publish/review behavior may be covered outside this worker slice, but it is not covered in `tests/python/core/subtitles/test_ass_to_srt_helpers.py`.
- WebView browser smokes correctly fail on nonzero Node runner exit and check no-mutation snapshots, but most browser smoke modules still have one Python test method that delegates assertions into large inline JavaScript payloads. Failures are actionable, but coverage is hard to reason about at function level.
- Individual WebView generated-artifact checks lack direct tests for parser-error handling. The aggregate `webview:prework:check` mitigates this by running JavaScript syntax checking first.
- No full browser launch, full Python suite, release gate, or real-media validation was run for this review-only report.

## Boundary Risks

- The two TDarr findings are developer-tooling boundary risks, not production pipeline edits, but they matter because the tools can create hardlinks and launch sample processing evidence under the "test library" label.
- No repository media, LocalBase runtime state, queue state, pending publish state, or source media was intentionally mutated during review. Reproductions used temporary directories outside the repository.
- Backend/media policy was not changed. Any future fix touching hardlink/copy behavior or sample-run execution should be validated at the high rung appropriate for source/scratch/output movement.

## Files Reviewed With No Findings

No detailed finding was recorded for the remaining in-scope source and fixture set:

- 232 of 234 `tests/python/**/*.py` files, excluding `test_application_facade.py` and `test_legacy_removal_readiness.py` which are listed in F-11-04.
- 41 of 41 `tests/webview/**/*.py` files.
- 32 of 34 `src/mediapipeline/tools/**/*.py` files, excluding `materialize_tdarr_test_library.py` and `tdarr_matrix_audit.py` which are listed in F-11-01/F-11-02.
- 8 of 10 `ops/scripts/dev/*.mjs` files, excluding `webview-tooling-common.mjs` and `analyze-webview-godfiles.mjs` which are listed in F-11-03.
- 10 of 10 `tests/fixtures/source_media/*.json` fixtures.
- `tests/__init__.py`.

## Files Marked Out Of Scope

- `__pycache__` directories and `.pyc` bytecode under the reviewed trees.
- `ops/scripts/dev/*.bat`, `ops/scripts/dev/*.ps1`, and `ops/scripts/dev/run-python-tool.py`; the user scope only assigned Node `.mjs` developer tooling in that directory.
- Production implementation files outside `src/mediapipeline/tools/`; they were cited only when tests imported them.
- Aggregate review files such as `FINDINGS_REGISTER.md`, `COVERAGE_MATRIX.md`, and `FINAL_SYNTHESIS.md`; this worker wrote only its own report.

## Incomplete Coverage

Review coverage is complete for the scoped source/fixture inventory above. Runtime execution coverage is partial: I ran static/compile probes and isolated temp-directory reproductions, but did not run the full test suite, release gate, browser smokes, or real-media validation. CodeRabbit CLI review was not run because the available skill is diff-oriented and does not match this exhaustive assigned-slice audit.
