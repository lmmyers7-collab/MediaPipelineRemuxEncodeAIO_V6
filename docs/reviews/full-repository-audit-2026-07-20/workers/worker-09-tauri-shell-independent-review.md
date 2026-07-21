# Worker 09 High-Risk and P1 Independent Review

Reviewer: `/root/coordinator_w09`  
First reviewer: `/root/validation_spine/ledger_adversarial`

Ten current-hash W09 paths were independently reviewed across all 4,018 physical lines. The set contains all six assigned high-risk rows and the four additional finding-bearing paths needed to disposition every W09 P1. Generated summaries were read first where available; all ten exact SHA-256 values match the first-pass rows.

The exact path-local finding sets remain unchanged. `pending_publish.rs`, `settings.rs`, and `backend_lifecycle_monitor.rs` have empty sets. The other seven paths independently confirm `AUDIT-FIND-W09-001`, `AUDIT-FIND-W09-002`, `AUDIT-FIND-W09-003`, `AUDIT-FIND-W09-004`, `AUDIT-FIND-W09-006`, `AUDIT-FIND-W09-007`, `AUDIT-FIND-W09-008`, `AUDIT-FIND-W09-009`, `AUDIT-FIND-W09-010`, and `AUDIT-FIND-W09-012` at their current locations. This covers all seven W09 P1 findings; the additional P2/P3 IDs are present because exact path-local attestation sets cannot omit co-located findings.

## Independent evidence

- `cargo check --locked` passed.
- `cargo test --locked --lib` passed all 56 tests, including child/process-tree lifecycle cases.
- `cargo fmt --check` independently reproduced the current diffs in `backend_process/tests.rs` and `close_readiness.rs`; `AUDIT-ERR-W09-IR-001` records the failure and confirms `AUDIT-FIND-W09-012`.
- The PG-2 sample-validation script parsed with zero PowerShell AST errors; `tauri.conf.json` parsed successfully.
- 7-Zip 24.09 list-only inspection of the existing `2026.6.4+001` NSIS artifact showed six NSIS support plug-ins plus `mediapipeline-tauri-shell.exe`, with no backend, WebView, Python/runtime, `src`, or `ops` application tree. Nothing was extracted or launched.
- A bounded source/config search found updater dependency/config/plug-in scaffolding but no update check, prompt, download, install, close gate, or restart consumer.
- The current release-policy query returned `Exclusion=null` and `ScanEligible=false` for `src/lib_tests/mod.rs`, confirming that its personal UNC fixture is package-included and outside privacy scanning. `AUDIT-ERR-W09-IR-002` preserves the failed nested-shell query before the variable-safe retry.

The destructive process-ownership scenario and hard shell-crash scenario were confirmed by exact static control-flow review only. No application launch, installer execution, concurrent-backend kill probe, real-media work, product code change, operator-state mutation, or external-system action was performed.

## Validation boundary

The independent attestation file contains exactly ten unique paths, distinct reviewer identities, current hashes, achieved statuses, exact first-pass finding sets, and central dispositions. The direct official attestation validator returned zero issues, and the W09-scoped completion validator returned zero missing high-risk or P1 obligations across 43 rows and 13 findings. This does not claim installed-package startup, hard-crash containment, destructive harness isolation, or real-media proof.
