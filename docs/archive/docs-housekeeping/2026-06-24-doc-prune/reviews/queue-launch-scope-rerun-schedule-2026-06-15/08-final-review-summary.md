# Final Review Summary

## Overall Verdict

The reviewed system is mostly well-guarded for normal queue launches. Backend queue launch scope is authoritative, Queue filters/selected rows are not submitted, dry-run queue evidence exists, priority `hold` is separated from runnable work, schedule gates run before launch, duplicate launch/control locks are present, ActiveJobs and related process checks provide layered active-work protection, and command journaling is bounded and redacted.

Three issues remain open.

## Findings

| Severity | Finding | Risk |
| --- | --- | --- |
| High | Single-file launch can process an arbitrary existing local file outside configured source roots. | Wrong-file processing and queue/source-root scope bypass. |
| Medium | WebView CSV rerun has no dry-run control or dry-run evidence path and hard-codes live launch. | Operator can start live rerun without UI-visible dry-run proof. |
| Medium | Force Stop wording understates backend termination scope. | Operator may expect pipeline-only termination while backend can kill audit/rerun too. |

## Strong Areas

- Queue preview uses live queue planner/dry-run evidence rather than UI table state.
- Launch scope UI explicitly warns that Queue filters and selected rows do not constrain backend launch.
- Priority path updates are constrained to configured source roots.
- Low priority remains runnable; hold is display-only/non-runnable.
- CSV rerun backend script rejects unsafe row policy overrides and verifies source identity.
- Schedule continuous launch requires watcher ownership unless explicitly bypassed.
- Stop After Current is cooperative and flag-based.
- Duplicate process protection is layered: launch lock, related process scan, ActiveJobs, progress state, and queue scan duplicate handling.
- Command journaling captures bounded request/result evidence and redacts sensitive fields.

## Main Boundary to Fix First

Fix single-file launch scope before adding any new launch convenience. It is the only reviewed path that can process an arbitrary existing local file outside configured source roots.

## Validation Completed

Targeted Python validation passed after setting `PYTHONPATH=src`:

- 33 launch/control tests, OK.
- 37 queue/priority/dry-run tests, OK.
- 66 schedule/ActiveJobs/spawn/kill/journal tests, OK.
- 38 rerun/report/API contract tests, OK.

Total: 174 targeted tests, OK.

## Recommended Order

1. P0: validate and preflight `single_file` against configured source roots.
2. P1: add WebView CSV rerun dry-run evidence flow.
3. P1: align Force Stop scope, UI wording, and journal evidence.
4. P2: add contract tests for selected-vs-filtered scope and active-work fallback edges.
