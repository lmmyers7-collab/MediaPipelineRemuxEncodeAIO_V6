# Ruff B/C4/UP Findings Remediation Ledger

Date started: 2026-07-02

Change packet: `MP-CHANGE-2026-0702-005`

## Purpose

This ledger tracks the full cleanup needed before the candidate Ruff rule
families can be considered for blocking enforcement on `src` and `tests`.
It is intentionally placed under `docs/implementation/` so it can support this
work without becoming a new canonical status source. The durable rule remains:
only `pyproject.toml`, the Python lint wrapper, CI/pre-commit wiring, and the
release/change-control gates define what is actually blocking.

The requested target is to fix all current findings from:

```powershell
.\apps\desktop\runtime\Python\python.exe -m ruff check --select B,C4,UP src tests
```

This cleanup must not:

- enable `ruff format`;
- add `--fix` to regular gates;
- weaken existing Ruff, pre-commit, CI, release, or change-control gates;
- change media policy, source/scratch/output movement, publish/drain behavior,
  network lifecycle policy, strict JSON confirmation behavior, or command
  journal semantics while making lint-only edits.

## Baseline

The post-B033 baseline from the current worktree is 486 candidate findings:

| Family | Count | Main rule codes |
| --- | ---: | --- |
| `B` | 46 | `B023`, `B009`, `B010`, `B017`, `B007`, `B904`, `B027`, `B905` |
| `C4` | 18 | `C420`, `C401`, `C414`, `C405`, `C416` |
| `UP` | 422 | `UP017`, `UP037`, `UP035`, `UP022`, `UP006`, `UP045`, `UP032`, `UP012`, `UP042` |

## Remediation Policy

Use the least risky code transformation that makes the lint finding false
while preserving runtime behavior.

Prefer these transformations:

- `B009` and `B010`: replace constant-name `getattr` or `setattr` calls with
  direct attribute reads or assignments.
- `B023`: bind loop-local state explicitly in lambdas or small local functions.
- `B017`: assert a concrete project exception where possible; when the test is
  deliberately exercising "any exception from this user-supplied hook", use a
  narrow `# noqa: B017` on that one assertion with a comment.
- `B027`: mark intentionally abstract empty methods with `@abstractmethod`, or
  make the base method raise `NotImplementedError` if the class is not already
  abstract-method based.
- `B904`: preserve exception context with `raise ... from exc` or suppress it
  intentionally with `raise ... from None`.
- `B905`: add an explicit `strict=` argument to `zip`.
- `C4`: use the equivalent set/dict/list form only when it preserves ordering,
  laziness, and value identity.
- `UP017`: use `datetime.UTC` where the file already targets Python 3.11.
- `UP035`: move collection ABC imports from `typing` to `collections.abc`.
- `UP037`: remove unnecessary quoted annotations only when future annotations
  or import order make the unquoted name available at evaluation time.
- `UP022`: use `capture_output=True` only when both stdout and stderr are
  already independently piped and no custom stream handling is involved.
- `UP042`: convert `str, Enum` to `StrEnum` only if tests prove serialized
  values and equality behavior are unchanged; otherwise leave a targeted
  compatibility suppression.

Avoid broad suppressions. If a suppression is necessary, it must be local to
one line, mention the compatibility reason nearby, and avoid hiding unrelated
rule families.

## Rule-Family Readiness Criteria

A rule family can become blocking only when this command is clean for that
family across `src` and `tests`:

```powershell
.\apps\desktop\runtime\Python\python.exe -m ruff check --select <family> src tests
```

The full candidate gate can become clean only when this command exits zero:

```powershell
.\apps\desktop\runtime\Python\python.exe -m ruff check --select B,C4,UP src tests
```

Blocking config changes are separate from cleanup. The cleanup may make a
family eligible, but the final decision to edit `tool.ruff.lint.select` must
still verify that the selected family is clean and that the wrapper continues
to rely on `pyproject.toml`.

## Validation Plan

Run these at minimum after the cleanup:

```powershell
.\apps\desktop\runtime\Python\python.exe -m ruff check --select B,C4,UP src tests
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.check_python_lint
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

Focused tests should cover edited high-risk or shared modules. For pure
mechanical modernization in tests, run the touched test modules or the closest
owning suite. For shared tooling or contract edits, run the relevant
`tests/python/tooling`, contract, or desktop suites in addition to Ruff.

## Work Log

- Created this ledger before the broad cleanup so the scope, policy, and
  validation expectations are explicit.
- The previous narrow cleanup removed duplicate set literals from
  `tests/webview/test_webview_frontend_mutation_boundary.py` under
  `MP-CHANGE-2026-0702-003`.
- Applied safe Ruff rewrites for candidate `B`, `C4`, and `UP` findings,
  then manually resolved the remaining late-bound test lambdas, concrete
  validation exceptions, worker-state exception chaining, abstract dispatcher
  no-op method, and test loop-variable names.
- Re-ran the full candidate audit until
  `ruff check --select B,C4,UP src tests` passed.
- Enabled only `B` in `tool.ruff.lint.select` because it is the bug-risk
  family and is now clean. `C4` and `UP` remain advisory despite being clean
  after this pass because reaching cleanliness required broad mechanical
  modernization churn.

## Result

Final candidate status:

| Family | Status | Blocking decision |
| --- | --- | --- |
| `B` | Clean on `src tests` | Enabled as blocking |
| `C4` | Clean on `src tests` | Left advisory |
| `UP` | Clean on `src tests` | Left advisory |

The regular lint gate still runs Ruff check only through the existing wrapper.
No `ruff format` command and no `--fix` flag were added to regular gates.
