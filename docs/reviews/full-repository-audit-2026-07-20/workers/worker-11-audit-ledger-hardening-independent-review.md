# W11 audit-ledger hardening independent review

Status: complete at the exact final hash lock. The canonical two-row independent attestation is worker-11-audit-ledger-hardening-independent-attestation.jsonl.

## Exact scope and lock

- Tool: src/mediapipeline/tools/dev/repository_audit_ledger.py
  - SHA-256: ad2805d45ef9cb64dcf7aa4f33d1c16234833efcba2f0c038a7a829eb31db5a9
  - Physical lines: 2,420
- Test: tests/python/tooling/test_repository_audit_ledger.py
  - SHA-256: d1cc3dd4de40558317e19a065e3fede4861530ae3f0d4d99de58cd2e1c41b6c2
  - Physical lines: 980
- First reviewer: /root/coverage_universe
- Independent reviewer: /root/validation_spine/ledger_adversarial
- Assigned slice: worker-11-tests-tooling

Both files were reread at the final lock through bounded exact-line and control-flow review. Neither file was edited by the independent review. Rehashes after all tests and probes matched the values above.

## Finding disposition

Every W11 finding remains centrally recorded with disposition confirmed because each describes a defect that existed at a reviewed historical hash. Every item below is resolved in the final implementation and regression-bound at the exact lock:

- SR-001: strict checking reconstructs review fragments and rejects fragment drift after merge.
- SR-002: normalization preserves and unions existing historical finding links.
- SR-003: repository identity rejects parent aliases and Windows-ambiguous spellings.
- SR-004: coverage artifacts publish as an atomic set and strict checking requires every mirror.
- SR-005: second review requires a distinct canonical reviewer and a current-hash attestation.
- SR-006: the established prior-production review fragment is included deterministically.
- SR-007: absent tracked files use stage-0 Git object evidence.
- SR-008: baseline completed-review counts derive truthfully from merged rows.
- SR-009: BASELINE.md participates in the same three-artifact atomic transaction.
- HIR-001: attestation IDs exactly match the first-pass set and are scoped to finding locations.
- HIR-002: first-pass finding and error IDs join to current central records.
- HIR-003: trailing dot/space, ADS colon, reserved-device variants, available 8.3 aliases, and casefold Git collisions fail closed.
- HIR-004: unresolved or duplicate Git index stages cannot produce coverage rows.
- HIR-005: symlink, gitlink, regular-mode link, unknown-mode, and ancestor-containment evidence are mode-aware and do not follow unsafe targets.

The five HIR records were updated to current, exact final-lock source/test locations. No additional root-cause finding was discovered during the final independent pass.

## Validation evidence

- apps/desktop/runtime/Python/python.exe -m unittest tests.python.tooling.test_repository_audit_ledger -v: PASS, 33/33 tests.
- apps/desktop/runtime/Python/python.exe -m ruff check src/mediapipeline/tools/dev/repository_audit_ledger.py tests/python/tooling/test_repository_audit_ledger.py: PASS.
- apps/desktop/runtime/Python/python.exe -m py_compile src/mediapipeline/tools/dev/repository_audit_ledger.py tests/python/tooling/test_repository_audit_ledger.py: PASS.
- Live tracked-universe probe: 6,061 tracked paths, 76 absent worktree paths, all 76 reconstructed as git_index_blob, zero empty content hashes, zero freshness findings, zero casefold collisions, and zero special Git modes.
- Adversarial attestation probe: mismatched first-pass sets, unrelated finding locations, and missing P1 dispositions were all rejected.
- Adversarial Windows identity probe: parent segments, trailing dot/space, ADS colon, COM¹, LPT³, and case-colliding Git paths were rejected.
- Structured finding validation: 68 current records, zero schema/location/deduplication issues after restoration of the five HIR records.
- Final exact-lock rehash: PASS for both frozen files.

The passing unit run emitted one benign Git warning that the temporary fixture path src/a.py would be normalized from LF to CRLF when Git next touched it. It is recorded as AUDIT-ERR-W11-HIR-012; it did not affect the isolated fixture result or either frozen hash. All W11 HIR error records are nonblocking and closed or informational.

## Attestation result

The source attestation exactly matches its 21 first-pass finding IDs: W11-001 through W11-007, HIR-001 through HIR-005, and SR-001 through SR-009. The test attestation exactly matches its 13 first-pass finding IDs: W11-001 through W11-007, HIR-001, SR-001, SR-003, SR-005, SR-008, and SR-009. Every attested disposition is confirmed, every claimed finding is path-located, the reviewers are distinct canonical agent identities, and second_review_status is complete.
