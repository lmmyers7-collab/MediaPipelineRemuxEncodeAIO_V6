# Prior Audit Reconciliation

Status: the 19 findings from the 2026-07-19 production audit are reconciled to current source; 13 remain present, five are fixed with focused regression proof (including completed distinct W02 settings review), and one requires packaged native runtime proof. The June 2026 function/module audit and July CodeQL snapshot remain prior evidence, not current exhaustive coverage.

## Evidence rule

No historical status was inherited. Each disposition required:

- current source bytes and Git state;
- generated summary first where present, treated only as navigation when stale;
- exact current source/test lines;
- comparison to the historical baseline where available;
- focused execution when it materially distinguished present/fixed/runtime-proof outcomes.

Prior no-finding claims never grant a terminal current review. Current content hashes and current line review control `COVERAGE_MATRIX.jsonl`.

Detailed reconciliation evidence is in:

- `workers/prior-production-audit-reconciliation.md`
- `workers/prior-production-audit-findings.jsonl`
- `workers/prior-production-audit-review.jsonl`
- `workers/prior-production-audit-errors.jsonl`

## 2026-07-19 production audit

The production-audit comparison used current HEAD `039658158d8439a868eff3c8c37e314845e9e22a`, the current worktree overlay, and historical comparison point `a8bf6e1dda9629e6f818ba12f2c8274362923372`. The non-settings worker compared all 45 unique paths named by its 16 assigned findings. “Unchanged” means byte/Git identity with the historical baseline; changed paths received fresh source review.

### Current disposition of all 19 IDs

| Prior finding | Current disposition | Current proof boundary |
|---|---|---|
| `CSW-2026-07-09-SETTINGS-001` | **Still present** | Candidate construction accepts a real registered sensitive value and rejects only the literal redaction placeholder; response redaction does not prevent request/JS-heap exposure. |
| `CSW-2026-07-09-SETTINGS-002` | **Still present** | `legacy_extras` still enter active PSD1 projection and every non-reserved key is materialized into PowerShell script scope; a no-write probe materialized `LegacyLabOnlyToggle`. |
| `CSW-2026-07-09-SETTINGS-003` | **Fixed and independently revalidated** | Cross-process authority lock covers digest comparison and projection transaction; 11 multiprocessing/crash/timeout/rollback/rebase/idempotent tests passed, and a distinct exact-hash W02 reviewer found no current defect in the lock/CAS slice. |
| `CSW-2026-07-09-SCHEDULE-001` | **Still present** | Watch baseline, tracker, and pending intent remain process-memory-only and an existing candidate is rebased on a fresh manager; no restart-inside-debounce regression exists. |
| `CSW-2026-07-09-MAINTENANCE-002` | **Still present** | WebView says checkpoints are not rewritten while dry-run backfill intentionally creates/returns an external RunLogs checkpoint. |
| `CPA-2026-07-19-001` | **Fixed** | Smoke inventory generator now discovers 25 wrappers, 34 modules, and nine direct-only modules and checks prose totals. Current unrelated line drift makes the check red rather than false-green; seven behavior tests pass. |
| `CPA-2026-07-19-002` | **Still present** | HDR metadata caller supplies heartbeat/interval, but callee declares only `FilePath` and reads unbound poll variables; no-write mock captured null handler and interval. |
| `CPA-2026-07-19-003` | **Fixed** | Scratch identity v2 recomputes SHA-256 and binds reuse; 15 adversarial cases passed with unchanged source hashes. Representative real-media proof remains a release gate, not an open source defect. |
| `CPA-2026-07-19-004` | **Needs native runtime proof** | Backend-owned cross-process singleton is implemented and five focused tests pass, including simulated hard crashes/races; packaged Windows hard-crash/relaunch census was not run. |
| `CPA-2026-07-19-005` | **Fixed** | Forced shutdown treats missing/false/malformed/exceptional cleanup evidence and unsafe post-cleanup readiness as failure; 13 lifecycle tests pass. |
| `CPA-2026-07-19-006` | **Fixed** | Rust child wait errors now become failed shutdown while ownership is retained; 18 focused Rust tests pass. |
| `CSW-2026-07-09-HOME-003` | **Still present** | Refresh fan-out passes raw close-readiness while lifecycle/topbar truth-test it; the normalizer is bypassed at that boundary and the new contract smoke is red. |
| `CSW-2026-07-09-TELEMETRY-004` | **Still present** | First backend `stale=true` sample is intentionally rendered `stale=false`/active until a second sample. |
| `CPA-2026-07-19-007` | **Still present** | Nine persistent subtitle/native prerequisite families remain retryable; registry query returned `Retryable=true` for all nine. |
| `CPA-2026-07-19-008` | **Still present** | Current settings counts are 206 backend / 156 bindings / 146 unique / 10 duplicates / 60 missing, while active inventories report inconsistent older totals and have no enforcing freshness check. |
| `CSW-2026-07-09-PENDING-003` | **Still present** | Ordinary orphan discovery emits no proposal, dry-run only consumes injected proposal fields, and WebView enables the action from selection alone; the safe consumer has no production producer. |
| `CSW-2026-07-09-RENAME-004` | **Still present** | History replay routes the newest apply through a state-mutating renderer that restores the apply manifest and clears successful undo completion state. |
| `CSW-2026-07-09-NETWORK-001` | **Still present** | Join-token preflight sizes a shorter placeholder, then rotates token authority before final exact encoding; final oversize failure has no compensation. |
| `CSW-2026-07-09-NETWORK-003` | **Still present** | Join-token creation reads role only for response metadata; backend route and WebView availability do not authorize against configured role. |

Counts:

| Disposition class | Findings |
|---|---:|
| Still present | 13 |
| Fixed with focused proof, including required independent review | 5 |
| Needs packaged/native runtime proof | 1 |
| **Total** | **19** |

The 13 current root causes are retained in current finding fragments. Fixed items are preserved here with their proof rather than emitted as current defects. `CPA-2026-07-19-004` remains an external release-evidence requirement.

## Focused execution used for reconciliation

| Surface | Result |
|---|---|
| Settings authority concurrency/recovery | 11/11 passed; distinct W02 exact-hash attestation complete |
| Backend singleton ownership | 5/5 Python tests passed |
| Forced-shutdown lifecycle | 13/13 Python tests passed; expected injected exceptions were evidence-bearing |
| Rust backend-process lifecycle | 18/18 passed |
| Scratch identity | 15/15 PowerShell adversarial cases passed with source hash proof |
| Maintenance backfill dry-run | Passed and showed the intentional external checkpoint |
| HDR heartbeat no-write mock | Reproduced null handler and interval |
| Subtitle registry query | All nine persistent prerequisite codes remained retryable |
| Settings count reproduction | 206 / 156 / 146 / 10 / 60 |
| Close-readiness contract smoke | Failed, corroborating the open normalization gap |
| Smoke-map check and renderer equality | Failed on current line-number drift elsewhere; seven generator behavior tests passed |

No source media, production settings, queue state, pending state, network-token authority, or live process lifecycle was mutated.

## Root-cause separation

- `CPA-2026-07-19-001` and `CPA-2026-07-19-008` share an inventory-drift theme but differ: smoke inventory now has an enforcing generator; settings inventories remain stale and manually unenforced.
- `CPA-2026-07-19-004`, `-005`, and `-006` cover separate lifecycle boundaries: cross-process singleton ownership, backend cleanup acknowledgement, and Rust child-exit verification.
- `HOME-003` and `TELEMETRY-004` are different frontend evidence failures: a normalization bypass versus intentional stale-state hysteresis.
- `NETWORK-001` and `NETWORK-003` are different authority failures: mutation/encoding transaction order versus missing configured-role authorization.
- `SCHEDULE-001` is independent of singleton ownership: preventing duplicate backends does not persist debounce intent across a legitimate restart.
- `PENDING-003` (no production proposal producer) is distinct from current `AUDIT-FIND-W15-001` (the injected/current Python proposal contract is weaker than the PowerShell drain contract).
- `SCHEDULE-001` is also distinct from current `AUDIT-FIND-W03-014`: the historical root is restart loss of in-memory debounce intent, while W03-014 is destructive partial save over corrupt shared app-state authority.
- `HOME-003` is distinct from current `AUDIT-FIND-W03-015`: the historical WebView path bypasses normalization of a close-readiness result, while W03-015 is a backend reducer that discards active-audit snapshot evidence before the UI receives it.

## 2026-06-11 function/module audit

The archived final synthesis explicitly says **partial audit complete**:

- universe: 1,296 indexed files with summaries and roughly 15,625 detected symbols;
- every worker reported partial/time-boxed coverage;
- at least 112 then-current generator files were unassigned because the index was stale;
- WebView pages and tests/tooling held the largest line-review gaps;
- active register: 61 deduplicated root causes, 59 called fixed and two deferred-with-reason;
- only 51 of 61 IDs have distinct row-level disposition entries.

Therefore the following claimed-fixed IDs receive priority revalidation rather than inherited closure: `FR-004`, `FR-008`, `FR-010`, `FR-015`, `FR-024`, `FR-026`, `FR-030`, `FR-033`, `FR-046`, and `FR-049`. Later current-state/checklist decisions for `FR-016` and `FR-042` likewise require source verification.

Current delta from that partial audit:

- Git-tracked universe: 6,061 files at audit baseline.
- Generated source index: 2,410 records at audit baseline.
- Old inventory overlaps 1,281 current index paths, contains 15 paths outside it, and omits 1,129 now-indexed paths.
- Rename-aware comparison from the nearest committed capture to current HEAD spans 277 commits and 6,151 tree changes: 3,253 additions, 723 deletions, 1,017 modifications, and 1,158 renames.

The old assignment matrix cannot prove current coverage.

## CodeQL baseline

- The 2026-07-12 ledger records 1,921 alerts in 32 rule groups against `main@34e4076720bde468ba9cb221ec617920724c587e`.
- A 2026-07-20 read-only remote-main query returned 1,857 open alerts in 14 groups: 74 baseline alerts closed and 10 new `py/ineffectual-statement` alerts appeared.
- The current audit branch had no CodeQL analysis. A zero branch-alert query is missing evidence, not a clean scan.
- Local audit HEAD and remote `main` diverged by 26 remote-only and five local-only commits at capture time.

A current-branch remote scan and location-level disposition of the 10 new alerts remain external completion requirements.

## Closure requirements

1. Preserve the completed W02/settings exact-hash attestation and rebind it only if the reviewed bytes change before final freeze.
2. Obtain packaged Windows hard-crash/relaunch proof for `CPA-2026-07-19-004` or retain it as an explicit external release requirement.
3. Revalidate the ten June findings without row-level dispositions and the two later-decision deferred items.
4. Rebind all still-present findings to final current hashes after concurrent edits freeze.
5. Do not convert historical coverage into current line-review status; only current worker fragments may do that.
