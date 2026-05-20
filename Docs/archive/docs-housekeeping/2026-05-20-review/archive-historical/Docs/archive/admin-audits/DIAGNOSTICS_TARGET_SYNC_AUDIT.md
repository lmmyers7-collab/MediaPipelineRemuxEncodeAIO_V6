# Diagnostics Target Docs Sync Audit

Date: 2026-05-14

Confirms diagnostics open/tail target keys in documentation match the backend allowlists. Source: `Docs\DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`, `Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`.

---

## Summary

All 20 allowlisted diagnostics targets are present in both `DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` and `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`. Tail-only vs open-only behavior is clearly documented. No discrepancies found. No documentation changes required.

---

## Allowlist Target Count

| Source | Count |
|---|---|
| `DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` (from contract_command.py) | 20 |
| `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` | 20 |
| Discrepancy | 0 |

---

## Target Categories and Behavior (From DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md)

### File Targets — Open and Tail Available (11)

| Target key | Behavior |
|---|---|
| `last_stderr_log` | Open (Explorer) + Tail (bounded read) |
| `last_stdout_log` | Open + Tail |
| `queue_snapshot` | Open + Tail |
| `completed_manifest` | Open + Tail |
| `latest_failure_json` | Open + Tail |
| `latest_failure_report` | Open + Tail |
| `cluster_log` | Open + Tail |
| `config` | Open + Tail |
| `latest_audit_csv` | Open + Tail |
| `latest_priority_csv` | Open + Tail |
| `sample_validation_log` | Open + Tail |

### Folder Targets — Open Only (9)

| Target key | Behavior |
|---|---|
| `run_logs` | Open (Explorer folder) only |
| `active_jobs` | Open only |
| `state` | Open only |
| `workspace` | Open only |
| `pending_publish` | Open only |
| `audit_reports` | Open only |
| `failed_markers` | Open only |
| `failed_reports` | Open only |
| `config_folder` | Open only |

---

## Safety Contract

All 20 targets share:
- No arbitrary path acceptance — frontend passes only a target key string
- No file modification, move, or delete on open or tail
- Tail is bounded (1 KB–256 KB, default 64 KB)
- Open is Explorer-only (no execution, no write)

This matches the stated contract in `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` and is verified by `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1`.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| All allowlisted targets appear in the runbook | Pass — 20 targets in both docs |
| Tail-only vs open-only behavior is clearly separated | Pass — 11 file targets (both); 9 folder targets (open only) |
| No arbitrary path wording is introduced | Pass — all routes validate against allowlist before resolving any path |

---

## Files Inspected

- `Docs\DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`: 20 targets; file vs folder split; safety contract
- `Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`: per-target use, mutation non-proof, investigation sequences

---

## Freshness Recheck — 2026-05-15 (CLN2-10)

Re-read `contract_command.py`, `facade_diagnostics_open_policy.py`, `facade_diagnostics.py`, and all three diagnostics target docs.

| Check | Result |
|---|---|
| `contract_command.py` `/api/diagnostics/open` target count | 20 — unchanged |
| `facade_diagnostics_open_policy.py` `DIAGNOSTICS_OPEN_TARGETS` count | 20 — unchanged |
| Tail route (`/api/diagnostics/tail`) uses separate allowlist | No — tail validation calls `diagnostics_open_target_label` from `DIAGNOSTICS_OPEN_TARGETS`; same 20 targets govern both routes |
| 11 file / 9 folder behavioral split | Confirmed — folder targets are behavioral distinction (directory path cannot be tailed meaningfully), not a separate code allowlist |
| `DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md` count | 20 — correct |
| `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` count | 20 — correct |
| `API_ROUTE_INVENTORY.md` claim | "20 allowlisted target keys" — correct |
| `COMMAND_OWNERSHIP_MATRIX.md` claim | "20 allowlisted keys" with full named list — correct |

No discrepancies. All sources agree at 20 targets. No documentation changes needed.

---

## Task Output

```
Task ID: CLN-014
Files inspected: Docs\DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md, Docs\DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md
Files changed: Docs\DIAGNOSTICS_TARGET_SYNC_AUDIT.md (created)
Validation: Compared target counts (20 in both). Verified file vs folder split and tail availability.
Findings: No discrepancies. Both docs are in sync at 20 targets. Safety contract is consistent.
Open questions: None.
Risk: Low — documentation only.
```
