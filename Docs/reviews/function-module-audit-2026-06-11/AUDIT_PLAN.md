# Function/Module Audit Plan - 2026-06-11

## Mission
Perform a review-only function/module-level audit of the repository using `docs/generated/PROJECT_INDEX.md` as the coverage universe. Every indexed Python, JavaScript, PowerShell, Rust, test helper, contract, route, tool entrypoint, UI asset, and active behavior document must be reviewed by an assigned worker or explicitly marked out of scope with a reason in that worker's ledger.

## Repository Rules Applied
- Read order completed before planning: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`.
- High-risk boundaries read: `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`.
- Review-only: no implementation fixes, refactors, commits, media/runtime-state mutation, source mutation, queue/publish/rename/settings execution, or launcher promotion actions.
- Before full source inspection, workers must check `docs/generated/summaries/<path>.md` when present.
- Output is confined to `docs/reviews/function-module-audit-2026-06-11/` and the change packet `MP-CHANGE-2026-0610-002`.

## Coverage Universe
- Indexed source files: 1296
- Generated summaries present for indexed files: 1296
- Token priorities: high=77, low=57, medium=1162
- Review classes: active-doc/generated-doc-review=57, code-symbol-review=1184, contract/config-review=28, ui/static-review=27

## Domain Counts
| Domain | Files |
|---|---:|
| api | 52 |
| application | 22 |
| audio | 2 |
| audit | 22 |
| completed | 10 |
| config | 73 |
| contracts | 35 |
| decide | 18 |
| diagnostics | 5 |
| failures | 9 |
| final_library | 9 |
| library | 1 |
| naming | 5 |
| network | 48 |
| observability | 32 |
| orchestration | 4 |
| paths | 5 |
| policy | 1 |
| probe | 2 |
| process | 43 |
| publish | 33 |
| queue | 43 |
| rename | 23 |
| scripts | 91 |
| shared | 9 |
| shell | 22 |
| status | 1 |
| storage | 8 |
| subtitles | 20 |
| tests | 305 |
| unknown | 190 |
| webview | 153 |


## Extension Counts
| Extension | Files |
|---|---:|
| `.bat` | 7 |
| `.css` | 10 |
| `.html` | 17 |
| `.js` | 127 |
| `.json` | 24 |
| `.md` | 57 |
| `.mjs` | 10 |
| `.ps1` | 210 |
| `.psd1` | 2 |
| `.py` | 815 |
| `.rs` | 15 |
| `.yaml` | 1 |
| `.yml` | 1 |


## Review Method
1. Use `ASSIGNMENTS.md` as the non-overlapping worker ownership map.
2. Each worker reads summaries first, inventories symbols, then opens full source only where needed for symbol-level review and findings evidence.
3. Each worker writes only `workers/<worker-id>-<domain>.md`.
4. The coordinator merges completed worker ledgers into `COVERAGE_MATRIX.md`, deduplicates findings into `FINDINGS_REGISTER.md`, and writes `FINAL_SYNTHESIS.md`.
5. Coverage is `complete` only when every indexed file has a worker ledger row with either reviewed symbols, `Reviewed: no findings`, or explicit out-of-scope rationale.

## Explicit Out-of-Scope Policy
The following are out of scope unless present in `PROJECT_INDEX.md` or explicitly pulled in by a worker as evidence:
- `LocalBase/`, run logs, live runtime state, scratch/output/source media, generated release packages, dependency folders, and gitignored runtime artifacts.
- Historical archived docs unless an assigned active file depends on them for current behavior.
- External rollback/fallback workspaces.

## Severity Policy
- P0: likely data loss, source mutation, unsafe publish/drain, or command/process lifecycle corruption requiring immediate stop.
- P1: high-risk boundary violation or likely incorrect media/settings/queue/publish/rename behavior with realistic operator impact.
- P2: correctness, stale-contract, path/Windows/UNC, error-handling, or misleading-test issue with bounded blast radius.
- P3: maintainability or coverage issue that creates real future risk but no immediate behavior break.

## Current Status
Initial status: assignments generated; worker reviews pending.
