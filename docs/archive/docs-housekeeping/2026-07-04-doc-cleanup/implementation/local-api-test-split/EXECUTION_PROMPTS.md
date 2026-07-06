# Execution Prompts

Use these prompts to run each phase with a fresh AI coding tool. Each prompt is
bounded on purpose. A dirty worktree is acceptable only when unrelated dirty
files are identified up front and kept out of the split packet. Do not start the
next phase until the current phase validation passes, touched files are recorded
in the change packet, and `ASSERTION_MIGRATION_LEDGER.md` is updated for moved
or deleted assertions.

## Recommended Execution Prompt

Use this when handing the whole planning pack to an implementation agent:

```text
You are working from the repository root.

Execute the Local API test split from docs/implementation/local-api-test-split/ in strict phase order. First read AGENTS.md, docs/DOCS_INDEX.md, docs/architecture/ARCHITECTURE.md, docs/architecture/MODULE_MAP.md, docs/testing/VALIDATION_LADDER_RUNBOOK.md, docs/testing/TEST_COVERAGE_MATRIX.md, and every markdown file in docs/implementation/local-api-test-split/.

Use the bundled Python runtime at .\apps\desktop\runtime\Python\python.exe. Start with PRE_WORK_AND_BASELINE.md: capture git status, identify unrelated dirty files, create or continue the implementation change packet, generate the method inventory, run the baseline unittest commands, and stop if any baseline failure is not understood.

Then execute exactly one phase at a time. For each phase: make only the changes allowed by that phase document; update ASSERTION_MIGRATION_LEDGER.md before deleting source assertions or methods; record touched files in the change packet; run the validation commands for the specific module being moved plus the old module; refresh generated summaries after source/test edits when feasible; and report the phase result before starting the next phase.

Preserve every assertion unless there is a documented intentional deletion with a reason and risk note. Keep strict JSON confirmations, command-journal behavior, close-readiness, source/root-scope checks, backend-owned mutation policy, and served-vs-file-read Web static distinctions at least as strict as before. Do not change product code unless the split exposes a real defect; if that happens, stop and re-scope the change and validation rung.

Finish with Phase 5 cleanup, final discovery validation, change-packet validation, generated-summary status, and the ADVERSARIAL_REVIEW.md checklist. In the final report include the change packet ID, files touched, moved tests/assertions, validation outcomes, unresolved/skipped validation, unrelated dirty files excluded from the packet, and rollback plan.
```

## Full Pack Prompt

```text
Read AGENTS.md, docs/implementation/local-api-test-split/README.md,
PRE_WORK_AND_BASELINE.md, ASSERTION_MIGRATION_LEDGER.md, VALIDATION.md, and
ADVERSARIAL_REVIEW.md. Execute the
Local API test split exactly in phase order. Start with prework only: inventory
the current test methods, capture baseline test results with the bundled Python
runtime, identify unrelated dirty files, and stop if baseline failures are not
understood. Then proceed one phase at a time: Phase 1 shared fixture/support
extraction, Phase 2 Web static extraction, Phase 3 Local API route-domain
extraction, Phase 4 queue/rename contract decomposition, and Phase 5 cleanup,
docs, discovery, generated summaries, and adversarial review. Do not move tests
before baseline evidence exists. Do not change product code unless a real defect
is exposed; if that happens, stop and re-scope. Preserve strict JSON
confirmation, command-journal, source/root-scope, close-readiness, and
backend-owned mutation guardrails. After each phase, run the validation commands
named by that phase, update the change packet with touched files and evidence,
update the assertion migration ledger, and report unrelated dirty files
separately. Do not start the next phase when validation fails or when a ledger
row cannot be mapped confidently.
```

## Phase 0 Prompt

```text
Read AGENTS.md and docs/implementation/local-api-test-split/PRE_WORK_AND_BASELINE.md.
Do not edit files yet except the change packet if needed. Run the baseline
inventory and validation commands with the bundled Python runtime. Report the
method inventory, baseline results, assertion-target inventory for
test_local_api_serves_read_only_web_prototype, the selected change packet, and
any unrelated dirty files. Stop if baseline tests fail for an unknown reason.
```

## Phase 1 Prompt

```text
Read AGENTS.md and docs/implementation/local-api-test-split/PHASE_1_TEST_HARNESS_AND_SHARED_FIXTURES.md.
Implement only the shared test support extraction. Create
tests/python/desktop/application_facade_test_support.py, move the shared dummy
fixtures from tests/python/desktop/test_application_facade.py, move reusable
Local API HTTP helpers and namespace/static helper constants, and update active
test importers to use the support module. Do not move test methods yet. Run the
Phase 1 validation commands, including the import scan, refresh generated
summaries for changed tests if feasible, update the change packet, and report
unrelated dirty files separately.
```

## Phase 2 Prompt

```text
Read AGENTS.md and docs/implementation/local-api-test-split/PHASE_2_WEB_STATIC_EXTRACTION.md.
Split test_local_api_serves_read_only_web_prototype into focused
test_application_facade_web_static_*.py modules by page/asset ownership. Keep
only a small served-static Local API smoke if needed. Preserve assertion intent,
avoid a new giant method, update ASSERTION_MIGRATION_LEDGER.md before deleting
source assertions, and run validation after each page group. Update
docs/testing/TEST_COVERAGE_MATRIX.md if ownership descriptions change, refresh
generated summaries if feasible, update the change packet, and report unrelated
dirty files separately.
```

## Phase 3 Prompt

```text
Read AGENTS.md and docs/implementation/local-api-test-split/PHASE_3_LOCAL_API_ROUTE_DOMAIN_EXTRACTION.md.
Move the remaining Local API route tests into domain modules in the documented
order: HTTP, diagnostics, network, repair, settings, lifecycle, process
commands, queue, rename. Move one domain at a time and validate the new module
plus the old module after each group. Do not change product code. Preserve
strict JSON, command journal, source scope, and active-work assertions. Update
ASSERTION_MIGRATION_LEDGER.md, update the change packet, and report unrelated
dirty files separately.
```

## Phase 4 Prompt

```text
Read AGENTS.md and docs/implementation/local-api-test-split/PHASE_4_QUEUE_RENAME_CONTRACT_DECOMPOSITION.md.
Decompose test_local_api_queue_and_rename_preview_contracts into smaller queue
and rename route-contract tests. Keep confirmation and command-journal
assertions visible. Run queue, rename, and Local API discovery validation.
Update ASSERTION_MIGRATION_LEDGER.md and docs/testing/TEST_COVERAGE_MATRIX.md
if coverage ownership changed, refresh generated summaries if feasible, update
the change packet, and report unrelated dirty files separately.
```

## Phase 5 Prompt

```text
Read AGENTS.md and docs/implementation/local-api-test-split/PHASE_5_CLEANUP_DOCS_AND_DISCOVERY.md plus VALIDATION.md and ADVERSARIAL_REVIEW.md.
Retire the old god-file role, update docs/inventories that reference the old
Local API test ownership, refresh generated summaries through tooling if
feasible, run final discovery validation, run change-packet validation, then run
the adversarial review checklist. Confirm ASSERTION_MIGRATION_LEDGER.md has no
pending rows or unresolved TBD placeholders. Report final files touched,
validation results, strict coverage status, skipped validation, unrelated dirty
files, and rollback plan.
```
