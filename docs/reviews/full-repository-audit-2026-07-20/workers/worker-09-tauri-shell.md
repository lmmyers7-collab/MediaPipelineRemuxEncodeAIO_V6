# Worker 09 — Tauri Shell

Assigned coverage is complete: **43 / 43 terminal paths** at their exact frozen SHA-256 values. The current W09 fragment contributes 42 rows; `single_instance_guard.rs` was already covered by a current-hash terminal row in `prior-production-audit-review.jsonl`, so the duplicate was removed. The deterministic combined result is 43 unique terminal paths: 26 `line_reviewed_no_findings` and 17 `line_reviewed_with_findings`.

Reviewer: `/root/validation_spine/ledger_adversarial`.

## Findings

The W09 fragment records 13 confirmed findings: **7 P1, 5 P2, and 1 P3**.

- `AUDIT-FIND-W09-001` (P1): the NSIS installer contains only the shell executable and cannot satisfy the required backend/WebView application layout.
- `AUDIT-FIND-W09-002` (P1): backend ownership does not survive hard shell death or failed startup cleanup verification.
- `AUDIT-FIND-W09-003` (P1): release startup can execute ambient Python and inherited `PYTHONPATH` code.
- `AUDIT-FIND-W09-004` (P2): stdout/stderr physical lines are unbounded before truncation or logging.
- `AUDIT-FIND-W09-005` (P2): loopback HTTP calls have per-operation timeouts but no total request deadline.
- `AUDIT-FIND-W09-006` (P2): bearer-token initialization runs on every WebView navigation without an origin guard.
- `AUDIT-FIND-W09-007` (P1): updater artifacts/plugin scaffolding have no check, prompt, download, close-gated install, or restart path.
- `AUDIT-FIND-W09-008` (P1): PG-2 sample automation fabricates exact media/publish evidence it never checks.
- `AUDIT-FIND-W09-009` (P1): five native harnesses can classify and force-kill an unrelated backend started after their baseline.
- `AUDIT-FIND-W09-010` (P1): a package-included Rust test exposes a personal server, identity, and media topology.
- `AUDIT-FIND-W09-011` (P2): prerequisite validation can report an unrelated `link.exe` as the MSVC linker.
- `AUDIT-FIND-W09-012` (P3): the canonical Tauri wrapper omits rustfmt while current Rust files fail `cargo fmt --check`.
- `AUDIT-FIND-W09-013` (P2): Rust startup contract validation omits GET and POST `/api/queue/priority-export`.

All finding locations are current, within file bounds, and exactly joined to the affected review rows. Six assigned high-risk paths remain correctly marked `second_review_status: pending`: Pending Publish and Settings contract gates, lifecycle monitor, backend process, backend-process tests, and close readiness.

## Error Ledger

`worker-09-tauri-shell-errors.jsonl` contains 28 records covering every observed failed, stderr-bearing, truncated, and expected-negative command. All classifications use the canonical vocabulary; all records are nonblocking, either closed by a bounded retry/alternate proof, linked to a confirmed finding, or identified as concurrent central-mirror staleness after a clean frozen checkpoint.

Notable retained limitations:

- `cargo audit` is not installed. Cargo.lock was structurally parsed across all 5,014 lines and 476 packages, and bounded official RustSec checks found sampled relevant versions patched, but this is not a comprehensive advisory scan.
- Native package launch, installer execution, active-work close, and real-media operation were not run during this static worker audit. The existing installer was inspected in 7-Zip list-only mode; no extraction or execution occurred.

## Validation Evidence

- Mandatory navigation fallback completed with the exact task and 2,000-token budget; `NO_TOUCH_BOUNDARY_REGISTER.md`, the Tauri lifecycle boundary, Rung 5 requirements, all available generated summaries, and every exact assigned source file were read.
- All ten PowerShell files passed parser validation.
- Four JSON and three TOML/lock inputs parsed successfully; Cargo.lock had 476 package records and 475 registry checksums.
- `cargo check --locked`: passed.
- `cargo test --locked --lib`: 56 / 56 passed.
- `cargo fmt --check`: failed reproducibly with the diffs recorded by W09-012.
- `Test-TauriShell-Build.ps1 -SkipLinkCheck`: passed its JavaScript, npm/Cargo check, and 56-test scope.
- `Test-TauriShell-Prereqs.ps1 -CheckOnly -RequireToolchain -RequireBuildTools`: passed on this machine; W09-011 documents its static false-positive path.
- `Test-TauriShell-ProductionSurface.ps1`: passed.
- `pytest -q tests/python/desktop/test_tauri_pg1_close_adversarial_scaffold.py`: 26 passed.
- Private-beta preflight, installed-layout, and release-artifact tests: 8 passed.
- `pytest -q tests/python/desktop/test_tauri_shell_scaffold.py`: 95 passed, 1 failed exactly on the two missing priority-export routes recorded by W09-013.
- Existing NSIS archive, list-only inspection: six NSIS support files plus `mediapipeline-tauri-shell.exe`; no backend/WebView/runtime resources.
- Final exact W09 hash check: 43 checked, 0 mismatches.
- Final combined review identity check: 43 rows, 43 unique paths.
- Final exact path-local finding-set check: 0 mismatches.
- Read-only audit preparation before publication: finding issues 0, error issues 0, review issues 0; W09 43 / 43 terminal with six high-risk second reviews pending.
- Coordinator publication checkpoint after W09 stabilization: 6,064 rows, 764 achieved, 112 findings, 442 errors, 97 second reviews complete; repository-audit `--check` passed.
- A later read-only `--check` observed stale central error mirrors after coordinator/W04/W06 fragment writing resumed; W09-028 records that concurrency result. It was not retried and this worker did not alter central files.

No product code, package, media, operator state, current runtime configuration, or central ledger was edited by this worker. Only the three W09 JSONL fragments and this worker report were changed.
