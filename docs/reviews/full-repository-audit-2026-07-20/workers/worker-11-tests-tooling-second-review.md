# Worker 11 Tests/Tooling — Independent Second Review

Date: 2026-07-20  
Reviewer: `/root/validation_spine`  
Method: generated-summary-first navigation, complete line review of both current files, prior-finding reconciliation, focused unit execution, and isolated temporary-repository adversarial probes. The `ecc:production-audit` evidence discipline was used. No application, tool, test, central ledger, or coverage-review row was edited.

## Outcome

The current hardening resolves the stated root causes of W11-001 through W11-007. The direct cases now fail closed: blocked rows cannot satisfy achieved completion; metadata has an explicit terminal state; semantic, reconciliation, and multi-flag obligations are checked; authoritative high/critical registry globs raise risk; error schemas, aliases, links, freshness, and blocking state are checked; review merge refuses stale content before writing; and direct exact root-cause duplicates are rejected.

Four new boundary defects remain:

1. `AUDIT-FIND-W11-SR-001` (P1): strict completion ignores current review fragments changed after their last merge.
2. `AUDIT-FIND-W11-SR-002` (P2): mixed pre-normalized/new historical links are silently overwritten during normalization.
3. `AUDIT-FIND-W11-SR-003` (P2): parent-segment path aliases evade exact finding deduplication and resolved-root containment.
4. `AUDIT-FIND-W11-SR-004` (P2): output pairs are only atomically replaced per file; an interrupted coverage merge can leave the CSV absent while a later strict check passes.

These are recorded separately in `worker-11-tests-tooling-second-review-findings.jsonl`; the original worker-11 fragment was not modified.

## Exact current review baseline

| Path | Current SHA-256 | Bytes | Physical lines | Generated-summary SHA-256 | Summary status |
|---|---|---:|---:|---|---|
| `src/mediapipeline/tools/dev/repository_audit_ledger.py` | `e43023564fc0ed364dec6cf3497cea07be8d48b66ddde62be964fbdf32c8a233` | 79,965 | 1,733 | `a77c3d49abc19da3d1af67c0a85e3a2ccf931af696729cfae1630b62d02b6609` | stale after hardening; read before source as navigation only |
| `tests/python/tooling/test_repository_audit_ledger.py` | `c581e7ad06cb8dcdf2719bf60117fb01d3526624013f8fd88618d19065d9b5e4` | 21,184 | 438 | `837cbb866ff0721ca63c4fca103a437a5c06e58c474b3c1e31e62d4cb6555451` | stale after hardening; read before test source as navigation only |

The prior worker report was terminal only for its old 1,141-line/219-line hashes. This review treats the new bytes above as a fresh line-review baseline.

## Original finding dispositions

| Original finding | Current disposition | Confidence | Decisive current evidence |
|---|---|---|---|
| `AUDIT-FIND-W11-001` | resolved at stated root cause | high | `ACHIEVED_STATUSES` excludes `blocked_with_reason` (lines 36-49); strict validation explicitly rejects a blocked row (1460-1464); test lines 199-202 covers it. Probe returned the expected blocked-completion finding. |
| `AUDIT-FIND-W11-002` | resolved at stated root cause | high | `metadata_verified` exists (44), metadata maps only to it (174-182), and compatibility-table completeness is checked (1432-1438). The category cross-product test is lines 204-223. Probe rejected metadata plus `generated_verified`. |
| `AUDIT-FIND-W11-003` | resolved at stated root cause | high | Schema fields include classification/reconciliation/obligation evidence (64-114); obligations derive from every true flag (672-699); strict checks enforce semantics, non-default evidence, prior-audit/index reconciliation, and exact verified obligations (1482-1548). A generated+binary probe failed until both obligations were verified. |
| `AUDIT-FIND-W11-004` | resolved at stated root cause | high | The registry is loaded and shape-validated fail-closed (598-620), globs map critical to the strict high tier (623-634), and fallback risk composes registry plus conservative markers (637-669). Test lines 158-179 covers storage and malformed registry. Representative samples from every high/critical registry glob all returned `high`. |
| `AUDIT-FIND-W11-005` | resolved at stated root cause; new normalization boundary recorded separately | high | Error fields/types/timestamps/classifications/current-or-historical links are validated (1208-1280); legacy classifications retain source provenance (1327-1348); current fragments are compared with central JSONL/Markdown and blocking errors fail strict completion (1599-1648). Test lines 267-335 covers malformed values, stale central state, and blocking semantics. |
| `AUDIT-FIND-W11-006` | resolved at stated root cause; post-merge freshness and publication gaps recorded separately | high | `merge_review_ledgers` validates the current universe and source/blob freshness before and after fragment application, then writes (1172-1205). Test lines 366-417 proves stale worktree refusal without matrix mutation. |
| `AUDIT-FIND-W11-007` | resolved for direct exact duplicates; path-identity bypass recorded separately | high | Deterministic fingerprinting exists (936-955), duplicate fingerprints and stale stored fingerprints are rejected (957-1069), and preparation writes a stable fingerprint (1099-1123). Test lines 427-434 covers direct duplicate IDs with identical normalized identity. |

“Resolved at stated root cause” means the original failure mechanism is no longer reproducible in the current bytes. It does not absorb the four distinct hardening-boundary defects into the old findings.

## Complete line review

### `repository_audit_ledger.py`

Reviewed every physical line, including:

- Lines 29-415: output paths, schema v2 status/category/row/error/finding domains, compatibility tables, canonical/legacy aliases, historical-ID policy, classifications, and review override fields.
- Lines 418-595: path normalization, read-only Git inventory, owned-untracked scope, hashing/text classification, file-category precedence, ownership, and layers.
- Lines 598-729: risky registry parsing/glob matching, fallback risk, all category/flag obligations, and worker assignment.
- Lines 732-885: project-index and row loading, universe construction, review-evidence preservation/reset, deterministic JSONL, and per-file atomic replacement.
- Lines 888-933: worker error/review/finding fragment discovery and JSON diagnostics.
- Lines 936-1132: semantic normalization, historical ID recognition, root-cause identity, finding schema/location/relation checks, alias normalization, deterministic finding preparation, and central output writes.
- Lines 1135-1205: review fragment ownership/hash/override validation, current-universe and current-content preflight, merge, post-merge freshness recheck, and matrix/CSV replacement.
- Lines 1208-1361: error schema/types/classification provenance/current/historical links, deterministic normalization, Markdown, and central merge.
- Lines 1364-1422: CSV and baseline rendering.
- Lines 1425-1552: schema v2 coverage validation, achieved-state semantics, category compatibility, flags/array types, multi-flag obligations, semantic evidence, prior-audit and project-index reconciliation, path universe, and second review.
- Lines 1555-1648: current file/hash/tracked/blob identity; current finding/error fragment reconstruction; central JSONL/Markdown freshness; unresolved blocking errors.
- Lines 1651-1733: baseline writes, strict check aggregation, CLI actions, output claims, and exit behavior.

No additional source defect was found outside the four new candidates. Notable non-findings:

- Alias normalization works for the tested legacy finding confidence, legacy `still_present` disposition, and legacy error classification, retaining `source_*` provenance.
- Every current high/critical registry glob matched a representative path at the strict `high` tier.
- Multi-flag obligations are a set derived from both category and all true flags; a generated binary cannot pass with only generated verification.
- Error `coverage_blocked=true` is deliberately unconditional under `--require-complete`; a resolved incident must explicitly set the field false rather than relying on free-form disposition text.
- Finding and error central ledgers are byte-compared against deterministic current fragment preparation; missing/stale rendered Markdown is detected.
- Individual output replacement uses a destination-directory temporary file, flush, `fsync`, and `os.replace`, with cleanup in `finally`.

### `test_repository_audit_ledger.py`

Reviewed every physical line and all 19 test methods:

- Lines 34-121 construct schema-v2 coverage/finding fixtures with real obligations and non-default completion evidence.
- Lines 124-184 cover path/classification, registry risk/fail-closed parsing, and worker assignment.
- Lines 186-246 cover strict status compatibility, blocked completion, every category, semantic defaults, multi-obligation state, and project-index reconciliation.
- Lines 248-299 cover baseline claims, owned untracked scope, and error types/classification/linkage.
- Lines 301-335 cover central error freshness and unresolved blocking errors.
- Lines 337-417 cover review ownership/hash checks and stale-worktree merge refusal without writes.
- Lines 419-434 cover finding shape, exact duplicate root causes, and stale fingerprints.

The new candidate gaps are not exercised: no post-merge review-fragment drift, mixed preexisting/new historical arrays, `..` location aliases/containment, or injected failure after the first member of an artifact set is replaced.

## New candidate evidence

### `AUDIT-FIND-W11-SR-001` — P1 — review-fragment freshness

`evidence_ledger_findings` reconstructs current finding/error ledgers only. The isolated probe built a valid terminal matrix and clean empty central finding/error ledgers, then added a schema-valid current review fragment changing the same row to `blocked_with_reason`. Results:

```text
strict_before_fragment = []
current_fragment_validation = []
strict_after_current_fragment_withdraws_completion = []
matrix_status = line_reviewed_no_findings
fragment_status = blocked_with_reason
```

Thus the final proof gate can report achieved completion using a matrix that is no longer the merge of current review evidence.

### `AUDIT-FIND-W11-SR-002` — P2 — historical-link preservation

Schema-valid finding and error records each contained one already-normalized historical ID (`CPA-2026-07-19-OLD`) and one recognized historical ID in the compatibility/current-link array (`FR-NEW`). Alias normalization succeeded with zero issues, but both prepared outputs contained only:

```text
historical = [FR-NEW]
```

The existing CPA relationship was overwritten rather than unioned.

### `AUDIT-FIND-W11-SR-003` — P2 — path identity/containment

Two otherwise identical findings used `src/a.py` and `src/../src/a.py`. Both resolved to the same current temporary file, but:

```text
canonical_1 = src/a.py
canonical_2 = src/../src/a.py
fingerprints_equal = false
findings = []
```

The lexical alias therefore bypasses exact deduplication; the same missing containment check can admit an existing path outside the root.

### `AUDIT-FIND-W11-SR-004` — P2 — output-set publication

Two caught negative-path probes are recorded in the worker error ledger:

- Failure on the second finding artifact left `FINDINGS.jsonl` present with one record and `FINDINGS_REGISTER.md` absent.
- Failure on `COVERAGE_MATRIX.csv` left the JSON matrix advanced to `line_reviewed_no_findings`, the CSV absent, and a later `check_outputs(require_complete=True)` returned `[]`.

The command-level exception is visible, but the output set is partially mutated and the next strict gate does not detect the missing coverage mirror.

## Validation evidence

### Focused maintained suite

Command:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.tooling.test_repository_audit_ledger -v
```

Result: **PASS**, 19 tests in 0.403 seconds.

### Isolated/adversarial probes

- Original W11 false-success cases: all now rejected as expected.
- Multi-flag generated+binary row: rejected when binary obligation was omitted; passed when exact full obligations were verified.
- Registry high/critical globs: zero representative non-high matches.
- Malformed error: rejected for blank command, invented classification, string exit code, and missing current link.
- Direct exact duplicate finding: rejected by duplicate root-cause fingerprint.
- Legacy aliases: normalized to canonical values with source provenance.
- Post-merge review withdrawal: strict false-clean reproduced (`[]`).
- Mixed historical fields: silent overwrite reproduced for finding and error preparation.
- Parent-segment location alias: fingerprint bypass reproduced with no validation finding.
- Second-artifact failures: partial publication reproduced; coverage partial state passed a subsequent strict check.

All probes used temporary directories and synthetic data. They did not read or mutate live operator state, media, credentials, or central audit ledgers.

## Error and incident accounting

Worker ledger: `docs/reviews/full-repository-audit-2026-07-20/workers/worker-11-tests-tooling-second-review-errors.jsonl`

- `AUDIT-ERR-W11-SR-001`: expected caught failure on the second finding artifact.
- `AUDIT-ERR-W11-SR-002`: expected caught failure on the coverage CSV replacement, followed by a false-clean strict check.

Both use v2 canonical `expected negative-path result`, link to `AUDIT-FIND-W11-SR-004`, and do not block review coverage. No command timed out. No uncaught tool or test failure occurred.

## Integrity and handoff

- The two assigned source/test files remained read-only throughout this review.
- No central `COVERAGE_MATRIX`, `FINDINGS`, `ERROR_LEDGER`, baseline, or existing worker fragment was edited.
- No second-review coverage/review JSONL row was created, avoiding duplicate coverage claims.
- The generated summaries remain stale by design after the concurrent hardening and must be regenerated by the coordinator/change owner, not by this read-only reviewer.
- A full live-repository `--check --require-complete` was not used as a unit verdict because the repository-wide audit is concurrently in progress; all proof-gate behavior was isolated at the current code hashes.

