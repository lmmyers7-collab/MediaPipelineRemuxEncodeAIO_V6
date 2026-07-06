# Adversarial Review

Status: run before declaring the split complete

## Purpose

Assume the split broke the test suite in a subtle way. Use this checklist to
look for lost assertions, duplicate tests, weakened safety checks, and hidden
coupling introduced by helpers.

## Lost Assertion Checks

- Compare the prework method inventory against final test methods.
- Compare the prework assertion-target inventory for the giant Web prototype
  test against final Web static modules.
- Confirm `ASSERTION_MIGRATION_LEDGER.md` has no unresolved `pending` rows or
  stray `TBD` placeholders.
- Search for old assertion literals that disappeared unexpectedly.
- Verify route names from the original tests still appear in a target test.
- Verify each WebView page asset bundle has at least one focused target module.

Useful searches:

```powershell
rg "test_local_api_serves_read_only_web_prototype|test_local_api_queue_and_rename_preview_contracts" tests\python\desktop
rg "confirm_apply|confirm_save|command journal|CommandJournal|strict" tests\python\desktop\test_application_facade_local_api*.py
rg "window\.mediaPipeline|__.*Module|Public namespace" tests\python\desktop\test_application_facade_web_static*.py
```

## Duplicate Test Checks

- Run `unittest discover` for the old and new patterns.
- Confirm the old module does not import test classes from the new modules.
- Confirm support modules are not named `test_*.py`.
- Confirm helper classes do not subclass `unittest.TestCase` unless they own
  actual tests.

## Safety Regression Checks

Review the route-domain modules for these invariants:

- missing or false strict confirmations are rejected;
- non-boolean truthy confirmation values are rejected;
- command journal entries are present or suppressed exactly as before;
- read-only dry-run routes do not write command journal entries when the old
  tests required no journal entry;
- source/root scope checks are still asserted;
- active-work blocks still prove no mutation happened;
- WebView static tests still distinguish advisory UI from backend-owned
  mutation policy.

## Helper Risk Checks

Shared helpers are useful only when they reduce repetition without hiding the
contract. Review for:

- broad helpers named `assert_ok` that obscure required fields;
- helpers that start servers without guaranteed cleanup;
- helpers that mutate shared state between tests;
- helper defaults that add auth tokens when a test is supposed to prove missing
  auth is rejected;
- helper defaults that add confirmation fields when a test is supposed to prove
  missing confirmation is rejected.

## Documentation Drift Checks

- `docs/testing/TEST_COVERAGE_MATRIX.md` no longer describes the old file as the
  single Local API route owner.
- `docs/DOCS_INDEX.md` includes the planning pack if it remains active.
- Generated summaries match the new files.
- No generated summary was hand-edited.

## Final Review Questions

Before final response, answer:

1. Which old tests moved to which files?
2. Which assertions were intentionally deleted, if any?
3. Does targeted invocation work for every new module?
4. Does discovery avoid duplicate tests?
5. Are strict JSON, command journal, close-readiness, and backend-owned mutation
   guardrails still pinned?
6. Does the assertion migration ledger reconcile every moved or deleted
   assertion?
7. Are unrelated dirty files excluded from the split packet?

If any answer is unclear, the split is not done.
