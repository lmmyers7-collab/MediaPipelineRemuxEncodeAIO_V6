# Phase 5: Cleanup, Docs, And Discovery

Status: execute after all tests have moved

## Purpose

Finish the split by removing the old god-file role, updating documentation, and
proving test discovery is clean.

## Old File Policy

After the split, `tests/python/desktop/test_application_facade_local_api.py`
should not continue as a catch-all.

Acceptable final states:

| Final state | When to choose it |
|---|---|
| Delete the file | No current tooling directly invokes the old module and docs have been updated. |
| Keep a short no-test orientation module | External notes still point to the filename and deletion would create avoidable confusion. |
| Keep a tiny smoke | Only if there is one truly cross-cutting Local API smoke that does not fit a domain module. |

Avoid compatibility imports such as `from new_module import *` because they can
duplicate tests or hide ownership.

## Documentation Updates

Update:

- `docs/testing/TEST_COVERAGE_MATRIX.md`
- `docs/DOCS_INDEX.md`, if this planning pack or new test ownership needs to
  stay discoverable
- any inventory that explicitly names the old file as the sole Local API route
  test owner

Do not hand-edit generated summaries. Regenerate them.

## Generated Summary Refresh

After source/test edits:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
```

If the summary generator tries to include unrelated dirty files, stop and
record that the generated refresh was skipped because the worktree was not
isolated. Do not absorb unrelated generated summaries into the split packet.

## Discovery Validation

Run:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_local_api*.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_web_static*.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

Also verify old targeted commands from docs have been updated or intentionally
retired.

## Assertion Ledger Closure

Before deleting or reducing the old Local API test file, review
`ASSERTION_MIGRATION_LEDGER.md`:

- no row should remain `pending`;
- no `TBD` placeholder should remain unless the row is an explicitly documented
  intentional deletion;
- every intentionally deleted assertion should include a reason and risk note;
- validation commands in the ledger should match the change packet evidence.

## Change Packet Closure

Before final response:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

If unrelated dirty files make strict worktree coverage infeasible, run normal
packet validation and report the unrelated dirty files separately. Do not add
unrelated dirty files to the split packet to make validation pass.

## Exit Criteria

- Old file is deleted or reduced to a non-god-file role.
- New test ownership is documented.
- Assertion migration ledger is resolved.
- Generated summaries are refreshed or the skip reason is documented.
- Discovery finds all new modules.
- Discovery does not duplicate tests.
- Change packet records all touched files and validation evidence.
