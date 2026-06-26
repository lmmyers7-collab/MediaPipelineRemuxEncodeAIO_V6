# Local API Test Split Planning Pack

Date: 2026-06-24
Status: executed; retained as the split runbook and audit trail
Planning packet: MP-CHANGE-2026-0624-024
Execution packet: MP-CHANGE-2026-0624-032

## Purpose

This planning pack describes how to split
`tests/python/desktop/test_application_facade_local_api.py` into smaller,
troubleshooting-oriented test modules without changing product behavior.

At planning time, the file was too broad to maintain professionally:

| Original surface | Original shape |
|---|---:|
| File | `tests/python/desktop/test_application_facade_local_api.py` |
| Approximate size | 8,679 lines / 592 KB |
| Test class | one `LocalApiServerTests` class |
| Test methods | 51 |
| Largest test | `test_local_api_serves_read_only_web_prototype` |
| Largest test size | about 4,836 lines |

The goal is not to create many files for its own sake. The goal is one clear
failure boundary per test file so a failing test tells the maintainer whether
the issue is HTTP transport, auth/security, lifecycle, queue routes, rename
routes, diagnostics routes, network routes, repair/reconcile routes, or WebView
static contract drift.

This pack is subordinate to:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/change_control/README.md`

If this pack conflicts with those authority docs or executable source/tests,
stop and update the stale planning text before continuing.

## Split Principles

- Front-load testing and inventory before moving code.
- Preserve every current assertion before deleting or renaming the old file.
- Move tests by ownership boundary, not by line count.
- Keep test modules flat under `tests/python/desktop/` to match the current
  repository convention and avoid test discovery churn.
- Do not hide assertions in helper functions unless the helper expresses a
  reusable contract with clear failure messages.
- Do not introduce compatibility import shims that run the same test twice.
- Keep direct `unittest` invocation ergonomic for failed slices.
- Treat route mutation tests as safety-critical even when only moving test code.
- Do not touch product code unless the split exposes a real defect; if that
  happens, stop and re-scope the change packet and validation rung.

## Target Shape

The final shape should leave the old god-file either removed or reduced to a
short no-test orientation module. It must not remain a catch-all for new tests.

Preferred target files:

| Target file | Ownership |
|---|---|
| `tests/python/desktop/application_facade_test_support.py` | Shared fixtures, Local API HTTP helpers, asset readers, namespace-export assertion helpers. This is not a test module. |
| `tests/python/desktop/test_application_facade.py` | Legacy fixture-provider module to retire or reduce to no-test orientation after importers move to `application_facade_test_support.py`. |
| `tests/python/desktop/test_application_facade_local_api_http.py` | Local API HTTP transport, auth, public/private route boundary, CORS, JSON envelopes, static file serving smoke. |
| `tests/python/desktop/test_application_facade_local_api_lifecycle.py` | Close readiness, shutdown blocking, force cleanup, schedule-stop watcher, shutdown logging. |
| `tests/python/desktop/test_application_facade_local_api_process_commands.py` | Process command authentication, strict payload rejection, command journal exception behavior, scheduled continuous start watcher. |
| `tests/python/desktop/test_application_facade_local_api_queue.py` | Queue state, priority manifest, queue strategy, file overrides, route preview, source-scope and journaling route contracts. |
| `tests/python/desktop/test_application_facade_local_api_rename.py` | Rename browse, clean-filename preview, filter settings, preview/apply/undo confirmation, root injection, active-work blocking. |
| `tests/python/desktop/test_application_facade_local_api_diagnostics.py` | Diagnostics tail and state-summary Local API route handling. |
| `tests/python/desktop/test_application_facade_local_api_network.py` | Network lifecycle/setup dry-run route metadata and no-journal behavior. |
| `tests/python/desktop/test_application_facade_local_api_repair.py` | Repair/reconcile dry-run route schema and no-journal behavior. |
| `tests/python/desktop/test_application_facade_web_static_shell.py` | Served index, bootstrap, asset order, content-type, command-history shell contracts. |
| `tests/python/desktop/test_application_facade_web_static_completed.py` | Completed page/static asset guardrails extracted from the giant Web prototype test. |
| `tests/python/desktop/test_application_facade_web_static_queue.py` | Queue page/static asset guardrails extracted from the giant Web prototype test. |
| `tests/python/desktop/test_application_facade_web_static_pending_publish.py` | Pending Publish page/static asset guardrails extracted from the giant Web prototype test. |
| `tests/python/desktop/test_application_facade_web_static_settings.py` | Settings page/static asset guardrails extracted from the giant Web prototype test. |
| `tests/python/desktop/test_application_facade_web_static_launch.py` | Launch, launch readiness, launch history, real-media handoff, and control-state static contracts. |
| `tests/python/desktop/test_application_facade_web_static_diagnostics_reports.py` | Diagnostics, Reports, Schedule, Maintenance, Telemetry, Progress, and Contract static contracts. |
| `tests/python/desktop/test_application_facade_web_static_cross_page.py` | Cross-page context, sample-validation, evidence-correlation, layout-manager, and topbar static contracts. |

Do not create every target file in one mechanical move if the phase can be
smaller. Create a file when there is enough migrated behavior to justify it.

## Phase Order

Execute these in order. Do not start moving assertions until the prework and
baseline evidence are recorded.

| Order | File | Purpose |
|---:|---|---|
| 0 | `PRE_WORK_AND_BASELINE.md` | Inventory current tests, capture baseline outcomes, identify exact method-to-target mapping, and define stop conditions. |
| 1 | `PHASE_1_TEST_HARNESS_AND_SHARED_FIXTURES.md` | Extract reusable test support first while leaving behavior and test ownership unchanged. |
| 2 | `PHASE_2_WEB_STATIC_EXTRACTION.md` | Split the 4,836-line Web prototype method into page/asset-focused Web static modules. |
| 3 | `PHASE_3_LOCAL_API_ROUTE_DOMAIN_EXTRACTION.md` | Split Local API route tests by backend ownership domain. |
| 4 | `PHASE_4_QUEUE_RENAME_CONTRACT_DECOMPOSITION.md` | Decompose the remaining long queue/rename contract tests into smaller route-contract tests. |
| 5 | `PHASE_5_CLEANUP_DOCS_AND_DISCOVERY.md` | Retire the old god-file role, update docs/inventories, refresh generated summaries, and prove discovery paths. |
| Gate | `VALIDATION.md` | Commands and expected evidence for every phase. |
| Gate | `ASSERTION_MIGRATION_LEDGER.md` | Fill-in ledger proving old assertions/methods moved before source assertions are deleted. |
| Gate | `ADVERSARIAL_REVIEW.md` | Failure-first review checklist before declaring the split complete. |
| Handoff | `EXECUTION_PROMPTS.md` | Ready-to-run prompts for executing each phase with a fresh agent. |

## Dependency Graph

```text
PRE_WORK_AND_BASELINE
  -> PHASE_1_TEST_HARNESS_AND_SHARED_FIXTURES
      -> PHASE_2_WEB_STATIC_EXTRACTION
          -> PHASE_3_LOCAL_API_ROUTE_DOMAIN_EXTRACTION
              -> PHASE_4_QUEUE_RENAME_CONTRACT_DECOMPOSITION
                  -> PHASE_5_CLEANUP_DOCS_AND_DISCOVERY
                      -> VALIDATION final pass
                      -> ADVERSARIAL_REVIEW final pass
```

Phase 2 comes before route-domain extraction because the single largest method
is mostly WebView/static contract coverage. Removing that method first makes the
remaining Local API route tests much easier to reason about.

## Definition Of Done

The split is done only when:

- No `test_application_facade_local_api*.py` file is a broad catch-all.
- No individual test remains near the current 4,836-line scale.
- The old `test_application_facade_local_api.py` no longer owns unrelated
  domains.
- Every original test assertion is either preserved in a target file or
  intentionally deleted with a documented reason.
- Targeted invocation of each new module works with bundled Python.
- `unittest discover` over `test_application_facade*.py` does not duplicate
  tests.
- `ASSERTION_MIGRATION_LEDGER.md` has no unresolved rows for moved or deleted
  assertions.
- `docs/testing/TEST_COVERAGE_MATRIX.md` and `docs/DOCS_INDEX.md` describe the
  new ownership accurately.
- Generated summaries are refreshed through tooling after source/test edits.
- Change-packet coverage records every touched file.

## Required Phase Report

Every implementation phase should finish with:

- change packet ID
- files touched
- tests moved, added, or intentionally removed
- validation commands and outcomes
- strict change-packet coverage status
- generated-summary refresh status
- unrelated dirty files not absorbed into the packet
- rollback plan
