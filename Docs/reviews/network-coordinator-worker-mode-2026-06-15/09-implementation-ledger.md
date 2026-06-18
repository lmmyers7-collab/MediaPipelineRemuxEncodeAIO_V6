# Implementation Ledger

Primary implementation packets:

- `MP-CHANGE-2026-0615-011`: Batch 1 state safety.
- `MP-CHANGE-2026-0615-012`: Batch 2 auth, secret, and journal safety.
- `MP-CHANGE-2026-0615-014`: Batch 3 lifecycle and provider semantics.
- `MP-CHANGE-2026-0615-015`: Batch 4 path-map and read DTO safety.
- `MP-CHANGE-2026-0615-016`: Batch 5 WebView, docs, contracts, and fixtures.
- `MP-CHANGE-2026-0615-018`: Remaining remediation implementation for `REM-NCW-01` through `REM-NCW-09`.

| Issue ID | Source Markdown file | Severity | Affected files/modules | Confirmed / invalid / already fixed / blocked | Required tests | Risk boundary touched | Implementation status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NCW Batch 1 | `FINDINGS_REGISTER.md`; `FIX_BATCH_PLAN.md` | P1/P2 | Coordinator HTTP handlers, registry, done outcome, worker claims/state/runtime | Confirmed | Coordinator HTTP/workflow/registry/worker-state/crash-recovery/done-release/worker-runtime adversarial tests | Claim ownership; source identity; done/release durability; worker crash recovery | Fixed and validated by `MP-CHANGE-2026-0615-011` for NCW-P1-03, NCW-P1-04, NCW-P1-05, NCW-P1-06, NCW-P1-07, NCW-P1-08, NCW-P1-09, NCW-P1-10, NCW-P1-14, NCW-P2-02, NCW-P2-03, and NCW-P2-04. |
| NCW Batch 2 | `FINDINGS_REGISTER.md`; `FIX_BATCH_PLAN.md` | P1/P2 | Coordinator auth, cluster logs, Local API handler/journal policy, protocol, join blob handling | Confirmed | Network security/protocol/coordinator HTTP/join and Local API command contract tests | Auth; secret redaction; command journal; strict protocol parsing | Fixed and validated by `MP-CHANGE-2026-0615-012` for NCW-P1-01, NCW-P1-02, NCW-P1-11, NCW-P2-01, NCW-P2-05, and NCW-P2-17. |
| NCW Batch 3 | `FINDINGS_REGISTER.md`; `FIX_BATCH_PLAN.md` | P1/P2 | Network lifecycle facade/provider, PowerShell worker-result bridge, local-worker slot evidence | Confirmed | Network lifecycle/provider tests, PowerShell local-worker slot/claim tests, result-to-done mapping tests | Lifecycle stop semantics; active work preservation; worker result evidence | Fixed and validated by `MP-CHANGE-2026-0615-014` for NCW-P1-12, NCW-P1-13, NCW-P2-06, NCW-P2-07, NCW-P2-18, and NCW-P2-19. |
| NCW Batch 4 | `FINDINGS_REGISTER.md`; `FIX_BATCH_PLAN.md` | P2 | Join path-map import, source path map policy, network read DTOs and drift evidence | Confirmed | Join/path-map/library-relative claim/application facade network DTO tests | Path-map correctness; source path safety; read DTO trust | Fixed and validated by `MP-CHANGE-2026-0615-015` for NCW-P2-09, NCW-P2-10, NCW-P2-13, NCW-P2-14, and NCW-P2-15. |
| NCW Batch 5 | `FINDINGS_REGISTER.md`; `FIX_BATCH_PLAN.md` | P2/P3 | Tauri route metadata, WebView network wording/smoke fixtures, active docs and inventories | Confirmed | Tauri scaffold, API route inventory, contract payload, command contracts, WebView network boundary/browser smoke, docs checks | Backend route authority; WebView mutation boundary; docs/contract drift | Fixed and validated by `MP-CHANGE-2026-0615-016` for NCW-P2-08, NCW-P2-11, NCW-P2-12, NCW-P2-16, NCW-P3-01, and NCW-P3-02. |
| REM-NCW-01 through REM-NCW-09 | `REMEDIATION_MASTER_PLAN.md`; `plans/*.md` | P1/P2/P3 | Network lifecycle active-claim evidence, cooperative drain, provider cleanup, worker-state preservation, strict integer parsing, local redaction, WebView stop copy | Confirmed | Network lifecycle/worker-state/crash-recovery/protocol/process-launch/security/drift/watch/API/Tauri/WebView tests plus browser smoke and PowerShell smoke | Network lifecycle; active work preservation; auth/redaction; worker-state recovery | Fixed and validated by `MP-CHANGE-2026-0615-018`: 161 focused tests, 405 broader network-adjacent tests, WebView browser network smoke, PowerShell browser smoke, summary refresh, and strict change-control validation passed at that time. |

## Validation Notes

- The network root uses a multi-packet implementation trail rather than one `05-findings.md` file.
- The high-risk remaining remediation packet `MP-CHANGE-2026-0615-018` records strict change-control coverage passing before later unrelated dirty worktree changes.
- No additional source edits were needed in this pass for the network root.
