# Worker 02 — Config, Settings, and Library

## Exhaustive first-pass outcome

Worker 02 completed first-pass review of the exact frozen assignment:

- 226 of 226 assigned paths reviewed.
- 120 generated summaries read in full, freshness-checked, reproduced from their bound sources, and semantically compared.
- 106 first-party configuration, schema, PowerShell, Python, settings, preset, and library files read line by line.
- 226 current worktree SHA-256 values match the frozen coverage baseline.
- 226 unique review rows are present; no missing, duplicate, unexpected, or cross-worker path is claimed.
- No product source, test, operator config, media, central ledger, change packet, commit, or external system was modified.

The review followed the repository navigation contract: context slice, no-touch boundary, generated-summary-first navigation, bounded full reads, current-hash binding, prior-finding reconciliation, focused no-write reproduction, and local fragment validation.

## Review-state counts

| Review state | Count |
|---|---:|
| Generated provenance/reproducibility verified | 120 |
| Line reviewed with no current path-local finding | 87 |
| Line reviewed with current path-local findings | 19 |
| Total achieved first-pass rows | 226 |
| High-risk rows awaiting independent review | 219 |
| Medium-risk rows with second review not required | 7 |

One generated summary has a current finding, so 20 paths in total carry path-local finding IDs.

## Worker-02 findings

| ID | Severity | Result |
|---|---|---|
| AUDIT-FIND-W02-002 | P1 | Settings preview reports no write while the production authority loader can promote/write store, PSD1, projection, and snapshots. |
| AUDIT-FIND-W02-003 | P2 | Idempotent settings replay precedes complete review-confirmation validation and still invokes authority persistence. |
| AUDIT-FIND-W02-004 | P2 | The direct settings-store test double changes LF bytes on Windows and does not inject failure at the rollback boundary named by the test. |
| AUDIT-FIND-W02-005 | P3 | The current presetLibrary.js summary deterministically fabricates an import graph from quoted/runtime text despite no module imports. |
| AUDIT-FIND-W02-006 | P1 | CPU/no-GPU setup persists VideoPreset=medium, while the canonical schema, model, and engine registry require p1-p7. |
| AUDIT-FIND-W02-007 | P2 | Missing all five required encoder capability evidence sections still returns operator status Ready/ready plus errors. |
| AUDIT-FIND-W02-008 | P1 | PresetV2 apply persists only a 26-key routing/video subset and silently ignores most audio, subtitle, filter, verification, and publish policy. |
| AUDIT-FIND-W02-009 | P2 | A non-list preset-library records value is normalized to empty and overwritten by the next successful save. |
| AUDIT-FIND-W02-010 | P2 | Deployment validation rejects five zero/null values accepted by the canonical schema and Config model. |

All nine local finding records pass the current schema, path containment, line-range, severity, confidence, disposition, and fingerprint checks.

## Reconciled external findings on assigned paths

The review rows also retain every current path-local finding owned elsewhere:

- AUDIT-FIND-W02-001 on runtime_config.ps1 and runtime_paths.ps1.
- AUDIT-FIND-W16-002 on encoding_capabilities.py, settings_wizard.py, and settings_wizard_tools.py.
- CSW-2026-07-09-SETTINGS-001 on settings_patch_candidate_facade.py.
- CSW-2026-07-09-SETTINGS-002 on settings_store.py and runtime_merge.ps1.

No duplicate finding was created for those root causes.

## Decisive reproductions

- Setup compatibility returned libx265_medium=true and libx265_p5=false; the canonical Config model rejected medium.
- A valid v2 capability payload with no evidence returned Ready/ready while listing all five required evidence sections as missing.
- A validated PresetV2 carrying AAC force-transcode, BDPGS conversion, and changed verification policy produced no audio, BDPGS, or verification keys in its apply patch.
- A temporary malformed preset library containing keep-me was successfully saved as a library containing only new; the original payload was not preserved.
- The canonical Config model accepted the five boundary/null values that the equivalent setup predicates reject.
- The generated presetLibrary.js summary lists impossible imports; a source search found no ES-module import/export/dynamic-import declaration.
- Existing no-write authority, replay, atomic-write, rollback, and Windows fixture reproductions remain recorded in the finding and error fragments.

## Validation evidence

| Validation | Outcome |
|---|---|
| Exact assignment/path/hash reconciliation | PASS — 226 rows, 226 unique owned paths, 0 missing, 0 unexpected, 0 hash mismatches |
| review_fragment_findings with complete path-local finding map | PASS — 0 issues |
| finding_record_findings against current repository paths | PASS — 9 records, 0 issues |
| error_record_findings with complete current finding universe | PASS — 31 records, 0 issues |
| Scoped generated-summary freshness | PASS — 120 source files current, no orphan summaries |
| Direct render_summary reproduction | PASS — 120/120 exact |
| Focused Python config/preset/library/settings suite | PASS — 160 tests |
| PowerShell config-key registry checks | PASS — 206 keys; 166 PowerShell config-reference files scanned |
| Final physical worktree hash check | PASS — all 226 assigned artifacts still match the review hashes |

The Python suite covered preset policy, preset library, settings policy, settings wizard policy, numeric policy, option policy, and library profiles.

## Error ledger and residual limits

The local error fragment contains 31 records:

- 6 expected negative-path results.
- 12 environment/setup issues.
- 2 test failures.
- 11 informational warnings.

Three records retain coverage_blocked=true:

- AUDIT-ERR-W02-005 and AUDIT-ERR-W02-006: clean direct-module evidence for the affected settings-store recovery cases remains blocked by the confirmed Windows test-fixture defect in AUDIT-FIND-W02-004.
- AUDIT-ERR-W02-014: global central merge remains coordinator-owned and was blocked by unrelated fragment/baseline conditions during the earlier attempt.

Those limitations do not hide or downgrade the first-pass line coverage. Independent review is still required for 219 high-risk rows. Representative real-media validation was not run because this was a read-only audit; remediation of AUDIT-FIND-W02-008 would require it before enabling newly mapped audio, subtitle, verification, or publish behavior.

## Artifacts

- worker-02-config-settings-library-review.jsonl — 226 exact hash-bound first-pass rows.
- worker-02-config-settings-library-findings.jsonl — 9 schema-complete confirmed findings.
- worker-02-config-settings-library-errors.jsonl — 31 recorded audit/test/tool incidents.
