# Worker 11 — Tests and Tooling

Assigned rows: 558. Overall slice status remains **in review**; this entry is terminal only for the two exact file hashes below.

## Independent coverage-engine review

Review method: direct line-by-line inspection because neither source currently has a generated summary; targeted unit execution; pure-function adversarial probes against completion, risk, error-record, and finding-record validation. Reviewer: `/root/coverage_universe`.

| File | SHA-256 | Lines | Review status | Depth | Findings |
|---|---|---:|---|---|---|
| `src/mediapipeline/tools/dev/repository_audit_ledger.py` | `a77c3d49abc19da3d1af67c0a85e3a2ccf931af696729cfae1630b62d02b6609` | 1,141 | `line_reviewed_with_findings` (terminal for this hash) | Every line, branch, schema, and CLI action | AUDIT-FIND-W11-001 through AUDIT-FIND-W11-007 |
| `tests/python/tooling/test_repository_audit_ledger.py` | `837cbb866ff0721ca63c4fca103a437a5c06e58c474b3c1e31e62d4cb6555451` | 219 | `line_reviewed_with_findings` (terminal for this hash) | Every line, assertion, and all 12 test methods | Test gaps linked below |

### Reviewed symbols and sections

- Status/category/row/error/finding/review-fragment schemas; extension and path-prefix policy; preserved and override fields.
- `canonical_path`, `run_git`, `nul_paths`, `git_tracked_paths`, `git_untracked_paths`, `git_blob_map`, and `audit_owned_untracked_paths`.
- `sha256_file`, `is_probably_text`, `text_line_counts`, `bool_path_marker`, `classification_for`, `fallback_owner_and_layer`, `fallback_risk_tier`, and `worker_for`.
- `load_project_index`, `load_existing_rows`, `load_rows`, `build_rows`, `jsonl_text`, `csv_text`, and `baseline_markdown`.
- `load_error_fragments`, `error_record_findings`, `error_ledger_markdown`, and `merge_error_ledgers`.
- `load_finding_fragments`, `finding_record_findings`, `findings_markdown`, and `merge_finding_ledgers`.
- `load_review_fragments`, `review_fragment_findings`, and `merge_review_ledgers`.
- `validation_findings`, `current_content_findings`, `write_outputs`, `check_outputs`, `parse_args`, and `main`.
- `RepositoryAuditLedgerTests` and all 12 current test methods, covering path normalization, classification, fallback risk, terminal validation, owned-untracked scope, error shape, review fragments, and finding shape.

## Findings

### AUDIT-FIND-W11-001 — P1 — Blocked rows satisfy strict completion

Lines `30-39`, `994-1010`: `blocked_with_reason` is terminal, and `--require-complete` accepts it after checking only for a note, reviewer, and non-inventory depth. A first-party row that was never reviewed can therefore be marked blocked while the exhaustive achieved-completion check passes. The adversarial probe returned no findings for this state. Strict achieved-completion must reject blocked rows; a separate incomplete/blocked report may retain them.

### AUDIT-FIND-W11-002 — P1 — Metadata has no compatible terminal status

Lines `42-55`, `1000-1008`: `metadata/packaging` is neither a line-review category nor present in `expected_terminal`. There is no metadata-specific status, so a metadata row marked `generated_verified`, `vendor_verified`, or any other terminal status passes strict completion. The probe confirmed `metadata/packaging + generated_verified` returns no finding. Define and enforce an appropriate metadata terminal status.

### AUDIT-FIND-W11-003 — P1 — Required semantic and reconciliation evidence is not enforced

Lines `56-90`, `594-638`, `978-1018`: required-row validation omits the generated/vendor/archive/binary/runtime/evidence-snapshot flags, file size/mode, and `project_index_present`/`project_index_hash_matches`. A terminal first-party row may also retain empty `reviewed_symbols_or_sections`, placeholder responsibility text, default evidence, and `prior_audit_coverage: not_reconciled`. The probe confirmed such a `line_reviewed_no_findings` row passes `require_complete=True`. This can falsely satisfy tracked-file, symbol, special-category, PROJECT_INDEX, and prior-audit gates. Require nonempty semantic evidence and explicit terminal reconciliation fields, including all applicable dual obligations.

### AUDIT-FIND-W11-004 — P1 — Registry-critical files can miss independent review

Lines `466-492`, `590-593`, `1017-1018`: fallback risk is a filename-substring heuristic and does not consume `docs/inventories/RISKY_FILE_REGISTRY.v1.json`. The registry classifies `ops/pipeline/engine/storage/**` as critical, but `fallback_risk_tier("ops/pipeline/engine/storage/move.ps1", ...)` returns `medium`; if its generated-index record is absent or degraded, strict completion does not require a second review. The test covers only a publish path. Merge the registry/boundary rules into risk derivation and test representative globs from every critical/high entry.

### AUDIT-FIND-W11-005 — P2 — Error records can be malformed and stale without blocking completion

Lines `92-108`, `832-849`, `1068-1090`, `1117-1130`: error validation checks field presence, unique ID, one array, and one boolean only. It accepts empty required strings, an invented classification, and a nonnumeric `exit_code`; the adversarial malformed record returned no findings. `check_outputs --require-complete` also does not verify that worker fragments were merged, that the central ledger is current, that blocking errors are resolved, or that linked finding IDs exist. Add finite classifications/types/nonempty checks, fragment-to-central freshness evidence, linkage validation, and an explicit blocking-error completion gate.

### AUDIT-FIND-W11-006 — P2 — Review merge can report success against a stale baseline

Lines `773-829`, `1025-1052`, `1121-1124`: fragment hashes are compared only with the existing matrix. `merge_review_ledgers` does not call `current_content_findings` before mutating and writing the matrix, so a fragment matching a stale baseline can be reported as successfully merged; only a later separate `--check` detects worktree drift. Validate baseline hashes, tracked state, and Git blob identity immediately before applying fragments and before printing merge success.

### AUDIT-FIND-W11-007 — P2 — Finding merge claims root-cause deduplication but does not perform it

Lines `109-138`, `704-770`, `1126-1128`: finding validation rejects duplicate IDs but never compares root cause, location, scenario, or related evidence. `merge_finding_ledgers` sorts and writes every unique-ID record while its Markdown and CLI claim the result is deduplicated. A probe submitted two distinct IDs with the same root cause and evidence; validation returned no findings. It also does not validate nonempty semantic text, current/existing location paths and line ranges, relationship targets, or central-ledger freshness. Define a deterministic root-cause identity/merge policy and validate the retained record and provenance.

## Confirmed strengths

- NUL-delimited Git queries and exact set reconciliation preserve tracked path identity; exact packet ownership prevents unrelated untracked files from entering coverage.
- Current content SHA-256, Git blob, tracked-state, missing-file, duplicate-path, and worker/hash review-fragment checks fail closed during the dedicated check.
- Generated artifacts, runtime/tool prefixes, requirements, ignore files, and evidence snapshots receive explicit classifications.
- Tracked audit-output self-reference is detected and rejected pending a non-self-referential freeze ledger; untracked audit evidence is excluded from the covered universe without losing explicitly owned source/tool files.
- Review rows start pending, and same-content regeneration alone does not claim semantic review.

## Test execution

`apps/desktop/runtime/Python/python.exe -m unittest tests.python.tooling.test_repository_audit_ledger -q` — **PASS**, 12 tests.

Adversarial pure-function probes confirmed five false-success conditions: metadata with an unrelated terminal status, blocked first-party completion, empty semantic/reconciliation evidence, malformed error records, and duplicate-root-cause finding records all returned no validation findings. A registry-critical storage path also returned only `medium` risk.

The final legacy-ID search produced the expected no-match exit code after an initial wildcard-shaped invocation left the combined shell at exit 1. The retry used `rg --glob`, confirmed no legacy IDs remain, and is recorded as `AUDIT-ERR-W11-001`; it does not block coverage.

## Missing tests

- Reject `blocked_with_reason` under achieved-completion mode.
- Enforce a metadata-specific terminal status and all dual flag obligations for generated/archive/runtime/vendor files that are also binary.
- Require reviewed symbols/sections, meaningful evidence commands, non-placeholder responsibility, flags, PROJECT_INDEX reconciliation, and prior-audit disposition on terminal rows.
- Load and test every high/critical risky-file registry glob, including storage, paths, cleanup, repair/reconcile, and lifecycle boundaries.
- Validate current hashes, tracked state, and blobs during `--merge-reviews`, not only in a later check.
- Validate error field types, finite classifications, nonempty values, finding linkage, blocking disposition, fragment-to-central freshness, and merge output consistency.
- Validate actual finding root-cause deduplication, nonempty semantic fields, location ranges/currentness, relationship targets, and fragment-to-central freshness.
- Exercise `build_rows` and `check_outputs` in isolated temporary Git repositories for staged deletion, rename, unmerged index stages, owned versus unrelated untracked paths, malformed change packets, and tracked audit-output self-reference.
- Test corrupt/malformed PROJECT_INDEX and coverage JSONL with file/line diagnostics, plus duplicate existing coverage rows.

## Remaining status

The two files above are fully reviewed at the recorded hashes. The overall 558-row Worker 11 slice remains nonterminal. Neither reviewed file has a generated summary. The central coverage matrix still records their prior hashes, so the coordinator must refresh the baseline before merging the companion review fragment. No implementation fix was authorized or made by this reviewer.
