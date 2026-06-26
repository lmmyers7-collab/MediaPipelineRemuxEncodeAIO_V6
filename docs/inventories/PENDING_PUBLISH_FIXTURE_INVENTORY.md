# Pending Publish Fixture Inventory

Purpose: inventory all pending-publish test files, describe what each covers and does not cover, document the fixture data patterns used, and note safety-property gaps. This is an observational document.

Total pending-publish test files: 7 dedicated + 10 files with incidental pending-publish coverage, plus PowerShell transaction coverage in `ops/pipeline/tests`.
No dedicated fixture JSON/JSONL files exist — all fixture data is generated dynamically in temporary directories or hardcoded as inline Python dicts.

---

## Module Ownership Guardrail

Pending publish is a backend-owned media safety path. Future work should keep media policy, copy/reveal decisions, sidecar preservation, weak-identity discard rules, and drain completion in PowerShell/backend modules. WebView/Tauri surfaces may display backend-authored rows and invoke documented backend commands only; they must not infer drain safety or mutate parked payloads.

| Module | Owns | Must not own |
|---|---|---|
| `ops/pipeline/engine/publish/publish_completion.ps1` | Immediate publish flow, low-space/unknown-space deferred parking decision, calls into pending park helpers when verified output must be parked. | Pending drain loop, manifest row presentation, WebView readiness decisions. |
| `ops/pipeline/engine/publish/publish_partial.ps1` | Partial media reveal and sidecar backup/restore primitives shared by immediate and pending drain publish. | Publish policy, source identity validation, manifest indexing. |
| `ops/pipeline/engine/publish/publish_sidecars.ps1` | Sidecar publish helper mechanics shared by immediate and pending paths. | Deciding whether a parked output is safe to discard or drain. |
| `ops/pipeline/engine/publish/pending_manifest_store.ps1` | Pending manifest read/write/round-trip validation and retry-state serialization. | Moving media, copying sidecars, or publishing final output. |
| `ops/pipeline/engine/publish/pending_transactions.ps1` | Durable media-plus-sidecar park transaction, drain transaction, server-copy validation, sidecar rollback, and `pending_move` crash recovery. | Public operator command routing, UI row formatting, or frontend policy. |
| `ops/pipeline/engine/publish/pending_push.ps1` | Public PowerShell facade for park and retry/drain commands, drain summary, event/log emission, and index refresh calls. | Low-level copy/reveal rollback details already owned by `PendingTransactions.ps1`. |
| `ops/pipeline/engine/publish/pending_publish_index.ps1` | Read-only in-memory index and health rows for parked manifests and missing payloads. | Moving, deleting, draining, or repairing payloads. |
| `app/publish/pending_*.py` | Read-only desktop scan, row shaping, open-target support, and API DTO normalization. | Media copy/reveal policy, discard decisions, manifest repair side effects. |

---

## Dedicated Pending-Publish Test Files

### Service Layer — Utilities

| Test file | Lines | What it covers |
|---|---|---|
| `test_service_pending_publish_format.py` | 54 | Formatting utilities: `format_bytes_compact`, `format_pending_timestamp`, `parse_pending_datetime`, `pending_age_text` |
| `test_service_pending_publish_paths.py` | 58 | Path resolution: `path_from_manifest`, `path_from_texts`, `pending_item_mtime`, `build_pending_orphan_payload_row`; orphan payload error reporting |
| `test_service_pending_publish_manifest.py` | 54 | Manifest parsing: unreadable manifest handling; legacy schema (no `schema_version`) tolerance; sidecar health check; missing file detection |
| `test_service_pending_publish_manifest_rows.py` | 80+ | Row structure building: `unreadable_pending_manifest_row`, `invalid_contract_pending_manifest_row`, `pending_sidecar_status`, `pending_output_size`; health shape preservation; error text prioritization |

### Service Integration

| Test file | Lines | What it covers |
|---|---|---|
| `test_pending_publish_service.py` | 180+ | 5 core scenarios: missing payload health row; parked media-plus-sidecar row evidence; unknown state detection (`invalid_contract`); legacy manifest tolerance; duplicate manifest target detection |
| `test_repair_reconcile_dry_run.py` | 200+ | Pending Publish repair/reconcile dry-run route builders: required response schema, strict no-mutation evidence, selected-row missing behavior, invalid manifest, duplicate target, orphan payload, active-work precondition, and command-journal suppression |
| `test_repair_reconcile_apply.py` | 320+ | Confirmed repair/reconcile apply routes: strict fingerprint and `confirm_apply=true` gating, manifest/sidecar/orphan-manifest-only writes, source/payload/output hash preservation, command journaling, frontend-path rejection, and repaired/reconciled pending manifests remaining parked/drain-ready without writing durable drain-summary evidence |

### Facade / Policy Layer

| Test file | Lines | What it covers |
|---|---|---|
| `test_facade_pending_publish_policy.py` | 80+ | Normalization: `normalize_pending_publish_open_target`, `normalize_pending_publish_row_key`, `pending_publish_row_key`; recovery plan action derivation; row filtering; preview field normalization |

---

## Incidental Pending-Publish Coverage In Other Test Files

| Test file | What it tests for pending-publish |
|---|---|
| `test_webview_row_detail_smoke.py` | High-risk row rendering: `unreadable_manifest` state, `do_not_drain` recommendation, operator guidance text, 5 health blockers, 4 filter scenarios (text / status / investigation / mutation guardrail) |
| `test_webview_browser_high_risk_smoke.py` | Real browser rendering of `do_not_drain` guidance; `operator_trust_state = "do-not-drain"`; `diagnostic_status = "unreadable_manifest"`; `drain_recommendation = "do_not_drain"` |
| `test_webview_command_evidence_smoke.py` | Pending-publish row in command-evidence fixture |
| `test_webview_browser_diagnostics_handoff_smoke.py` | Diagnostics bridge from Pending Publish selected row |
| `test_facade_diagnostics_open_policy.py` | `pending_publish_open` target in diagnostics open policy |
| `test_application_facade.py` | Facade-level pending-publish workspace calls |
| `test_controllers.py` | Historical legacy desktop-shell controller integration |
| `test_network_persistence.py` | Network/pending-publish interaction at persistence layer |
| `test_sample_validation_api.py` | Sample validation cross-reference with pending publish state |
| `test_tauri_shell_scaffold.py` | Layout gate (wrapper scripts and release file presence) |

---

## PowerShell Transaction Coverage

| Test file | What it tests for pending-publish |
|---|---|
| `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` | Legacy pending manifests, transactional park, parked tx3g SRT sidecars, missing sidecar retry state, network-copy retry preservation, media reveal failure rollback, drain summary readback, and retry success cleanup |
| `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` | Real deferred-publish processing followed by `-DrainPendingPushes`; verifies pending manifests drain away and generated media reaches output destinations |

---

## Fixture Data Patterns

All pending-publish fixture data is inline — no external JSON/JSONL fixture files.

### Inline Row Dicts (most tests)

Service-layer tests hardcode rows directly in test methods:

```python
{
    "state": "unreadable_manifest",
    "diagnostic_status": "unreadable_manifest",
    "diagnostic_severity": "error",
    "drain_recommendation": "do_not_drain",
    "ready_to_drain": False,
    "local_exists": False,
    "missing_sidecar_count": 2,
    "operator_trust_state": "do-not-drain",
    "operator_guidance": "Do not drain; repair or regenerate the pending manifest first.",
    "recovery_class": "manifest_repair",
    "issue_summary": "Unreadable manifest, missing payload, and missing sidecars.",
}
```

### Temporary Directory Fixtures (integration tests)

`test_pending_publish_service.py` creates `tempfile.TemporaryDirectory()` instances and writes minimal manifest JSON files (both legacy and v1 schemas) to exercise the scan path.

### Dynamic Fixture State (WebView smokes)

`test_webview_row_detail_smoke.py` and `test_webview_browser_high_risk_smoke.py` call helper functions like `_write_high_risk_fixture_state()` to populate a temporary local API server with prepared pending-publish rows including the `do_not_drain` state.

---

## Observed Pending-Publish States

| State value | Meaning | Tested |
|---|---|---|
| `parked` | Normal parked payload awaiting drain | Yes — service integration and PowerShell transaction coverage |
| `unreadable_manifest` | Manifest file cannot be parsed | Yes — service tests and WebView smokes |
| `invalid_contract` | Manifest schema version mismatch or shape error | Yes — `test_pending_publish_service.py` |
| `orphan_payload` | Payload file exists without a manifest | Yes — `test_service_pending_publish_paths.py` |

---

## Safety Properties And Where They Are Tested

| Safety property | Where tested | Coverage assessment |
|---|---|---|
| `do_not_drain` recommendation blocks drain in WebView | `test_webview_row_detail_smoke.py`, `test_webview_browser_high_risk_smoke.py` | Covered at UI layer (Node VM and real browser) |
| Unreadable manifest triggers `do_not_drain` | `test_service_pending_publish_manifest.py`, `test_pending_publish_service.py` | Covered at service layer |
| Missing payload triggers health row | `test_pending_publish_service.py` | Covered |
| Invalid manifest schema triggers `invalid_contract` | `test_pending_publish_service.py` | Covered |
| Legacy manifest (no `schema_version`) is tolerated | `test_service_pending_publish_manifest.py`, `test_pending_publish_service.py` | Covered |
| Orphan payload (no manifest) reported as error | `test_service_pending_publish_paths.py` | Covered at path-utility level |
| Duplicate manifest targets detected | `test_pending_publish_service.py` | Covered |
| Drain does not run from WebView directly | Route contract + `test_webview_row_detail_smoke.py` (mutation guardrail filter confirms no backend drain called) | Covered — no drain route exists in command contract |
| Parked media plus tx3g SRT sidecars are visible as one media-plus-sidecars unit before drain | `test_pending_publish_service.py` | Covered at service scan/row layer |
| Parked media plus tx3g SRT sidecars drain together | `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` | Covered at PowerShell transaction layer |
| Drain summary records media-plus-sidecar success and retryable failures | `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` | Covered at PowerShell transaction layer |
| Failed media reveal preserves parked media, parked sidecar, and manifest while removing partial/server-side artifacts | `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` | Covered at PowerShell transaction layer |
| Real deferred-publish drain command moves generated media out of pending state | `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` | Covered by generated-media smoke |
| Recovery plan is dry-run only (no files moved) | Route contract (`effect: "none"`) + `src/mediapipeline/core/api/commands_files.py` (`recovery_plan_dry_run` command name) | Contract-level only |
| Pending Publish repair/reconcile dry-runs are no-mutation evidence only | `test_repair_reconcile_dry_run.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py`, `test_application_facade_local_api_repair.py`, `test_webview_frontend_mutation_boundary.py` | Covered for strict request fields, required dry-run schema, blocked preconditions, command-journal suppression, no WebView callers, and fixture hash/mtime preservation |
| Pending Publish repair/reconcile apply keeps repaired payloads in backend drain posture | `test_repair_reconcile_apply.py` | Covered for temp-fixture manifest repair and orphan-payload reconcile: apply rewrites or creates only the backend-validated pending manifest, preserves source/output/payload bytes, preserves an existing durable drain summary, and rescans the repaired/reconciled row as `parked` / `ready_to_drain` |
| Open targets are allowlisted | `test_facade_diagnostics_open_policy.py` | Covered |

---

## Known Gaps

### 1. Recovery Plan Action Coverage

`test_facade_pending_publish_policy.py` tests recovery plan action derivation, but the specific action types (e.g., `repair_manifest`, `skip_orphan`, `drain_ready`) are not all exercised in isolation with their conditions. The gap matters if a new state type is added that should produce a different action but maps to a wrong existing action.

### 2. Completed Manifest Cross-Check

PowerShell regression coverage now reads `pending_drain_summary.json` for drain outcomes and sidecar counts, but it does not deeply compare every completed-manifest field against the drain summary for all media classes.

### 3. Coordinator-Mode Pending-Publish Interaction

When a worker finishes encoding, it parks the output for the coordinator to publish. The pending-publish tests do not cover this worker-to-coordinator publish handoff. The gap is consistent with the experimental status of coordinator/worker mode.

---

## What Pending-Publish Tests Do NOT Prove

- Completed-manifest fields fully reconcile with every pending-drain summary field across all media classes.
- Coordinator-mode worker output parking — experimental; no coverage.
- Recovery plan actions cause the correct drain behavior when a drain is later run — dry-run only; effect not verified.
- Repair/reconcile mutation behavior — covered only for backend-owned temp-fixture manifest/sidecar writes. It does not prove representative real-media source/payload/output validation or the full deferred-publish drain lifecycle.

---

## See Also

- Pending-publish command routes: `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` (`POST /api/pending-publish/open`, `POST /api/pending-publish/recovery-plan`, `GET /api/pending-publish`)
- Pending-publish diagnostics targets: `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` (`pending_publish`, `last_stderr_log`, `latest_failure_json`)
- Real-media validation for drain proof: `docs/implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`
