# Worker 02 Config/Settings High-Risk Independent Attestation

Reviewer: `/root/w02_highrisk_independent`  
First reviewer: `/root/w02_static_completion`  
Date: 2026-07-21

## Result

PASS for the complete assigned current-hash scope. All 212 high-risk, achieved first-pass rows owned by `worker-02-config-settings-library` that lacked a current independent attestation were independently reviewed and attested. No new independently supportable root-cause finding was identified. The exact 10 existing path-local findings were confirmed with their central dispositions.

No product code, source media, LocalBase data, central audit ledger, change packet, or external system was modified.

## Scope

| Class | Files | Bytes | Physical lines |
|---|---:|---:|---:|
| Generated summaries | 120 | 135,523 | 2,353 |
| First-party executable source | 79 | included below | included below |
| Behavior-defining config/schema | 13 | included below | included below |
| Non-generated subtotal | 92 | 955,418 | 23,795 |
| Total | 212 | 1,090,941 | 26,148 |

The non-generated set comprised 63 Python files, 16 PowerShell files, 2 PowerShell data files, and 11 JSON files. The terminal first-pass states were 120 `generated_verified`, 77 `line_reviewed_no_findings`, and 15 `line_reviewed_with_findings`.

Every physical line was read. The generated lane additionally passed source existence, normalized source hash, schema-v2, generator fingerprint, and exact `render_summary()` equality checks for 120/120 summaries. The generator fingerprint was `d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d`; the generated-scope tuple manifest SHA256 was `d650b69939bee5b98414c7bd3d9df4643f0b6e37d18b50ede97e4da71713b6f1`.

The production-audit discipline materially shaped the evidence: errors and truncations were recorded before retry, source hashes were rechecked, mutation boundaries were preserved, and conclusions were tied to exact current paths and hashes.

## Confirmed Findings

| Finding | Severity | Attested rows | Disposition | Summary |
|---|---:|---:|---|---|
| `AUDIT-FIND-W02-002` | P1 | 1 | confirmed | Settings preview reports no write while authority loading rewrites active artifacts. |
| `AUDIT-FIND-W02-006` | P1 | 4 | confirmed | The setup wizard CPU default generates a `VideoPreset` rejected by the canonical contract. |
| `AUDIT-FIND-W02-008` | P1 | 3 | confirmed | PresetV2 apply silently ignores most audio, subtitle, verification, filter, and publish policy. |
| `AUDIT-FIND-W02-001` | P2 | 2 | confirmed | Effective-config dump omits registered runtime safety and autonomy settings. |
| `AUDIT-FIND-W02-003` | P2 | 1 | confirmed | Idempotent settings replay bypasses complete review confirmation and still rewrites authority. |
| `AUDIT-FIND-W02-007` | P2 | 1 | confirmed | Incomplete encoder capability evidence is still labeled Ready. |
| `AUDIT-FIND-W02-009` | P2 | 1 | confirmed | A malformed preset-library `records` field is treated as empty and overwritten on save. |
| `AUDIT-FIND-W02-010` | P2 | 2 | confirmed | Deployment validation rejects five values accepted by the canonical config contract. |
| `AUDIT-FIND-W16-002` | P2 | 3 | confirmed | Duplicated encoder maps disagree on `h264_amf`, causing a supported-codec fallback rejection. |
| `AUDIT-FIND-W02-005` | P3 | 1 | confirmed | A JavaScript generated summary fabricates an import graph from quoted runtime text. |

There are 19 finding occurrences across the 15 with-findings rows. Attestation finding sets exactly equal their first-pass path-local finding sets.

## Validation

- Raw current SHA256 and physical-line reconciliation: 212/212 passed; zero missing files or baseline/hash mismatches.
- Python AST parse: 63/63 passed.
- JSON parse: 11/11 passed.
- PowerShell parser validation: 18/18 PowerShell/PSD1 files passed with zero parse errors.
- Generated provenance and exact rendering: 120/120 passed.
- Bundled-Python config/settings/preset/library-profile test bundle: 275/275 passed in 9.409 seconds.
- `pwsh -NoLogo -NoProfile -File .\ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1`: passed; 206 keys and 166 PowerShell config-reference files scanned.
- Official scoped `second_review_attestation_findings`: zero problems.
- Exact required-set join: 212 required, 212 attested, 212 unique paths, 14 fragments, zero missing, foreign, duplicate, or stale-hash rows.
- Worker-owned `error_record_findings`: zero problems across 7 recorded nonblocking audit errors.

The global `prepare_error_records` join remains nonzero because three pre-existing coordinator-owned records use classifications rejected by the current schema: `AUDIT-ERR-COORD-120`, `AUDIT-ERR-COORD-122`, and `AUDIT-ERR-COORD-123`. They were preserved because they are outside this worker's write scope. This does not block the exact W02 high-risk attestation scope.

Representative real-media validation was not required: this was a read-only semantic/provenance audit and made no behavior or media-policy change.

## Artifacts And Worktree

Attestations are in `worker-02-config-settings-high-risk-01-independent-attestation.jsonl` through `worker-02-config-settings-high-risk-14-independent-attestation.jsonl`. Audit command/retry records are in `worker-02-config-settings-high-risk-01-independent-errors.jsonl`.

Before this report was added, 906 unrelated dirty paths were present and preserved; the worker owned 15 new audit artifacts. No unrelated path was absorbed. Strict change-packet coverage was not run because this delegated task permitted only worker audit artifacts and prohibited editing the shared change packet or central ledgers.
