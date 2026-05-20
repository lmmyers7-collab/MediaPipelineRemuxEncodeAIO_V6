# God File Split Plan

> **Status:** Wave 6 complete — 2026-05-19. All 8 original Waves 1–3 god files, Wave 4 CSS/markup, Wave 5 test-file splitting, and Wave 6 JS child splits are complete; command-adjacent Queue priority/strategy/file-overrides behavior intentionally remains in `queueView.js`.
> **Scope:** Production-owned code only. Excludes bundled runtimes, generated Rust `target/`, MKVToolnix docs, and `Docs/archive/`.
> **Goal:** Reduce the largest god files in the codebase into focused, single-responsibility modules without breaking behaviour, inventories, or smoke coverage.

### Split progress at a glance

| # | God file | Children planned | Children done | Status |
|---|---|---:|---:|---|
| 1 | `facade_sample_validation_policy.py` | 8 (+ deferred `_shared.py`) | 8 | ✅ **Complete** — `_shared.py` deferred until 3+ siblings share helpers |
| 2 | `completedView.js` | 4 | 4 | ✅ **Complete** |
| 3 | `settingsView.js` | 8 | 8 | ✅ **Complete** |
| 4 | `launchView.js` | 4 | 4 | ✅ **Complete** |
| 5 | `pendingPublishView.js` | 4 | 4 | ✅ **Complete** |
| 6 | `crossPageContextView.js` | 4 | 4 | ✅ **Complete** — `.conflict.js`, `.sample.js`, `.settings.js`, `.sampleValidation.js` all done |
| 7 | `MediaPipeline_chatgpt.ps1` | 6 | 6 | ✅ **Complete** for planned scope — `Do-Remux`, `Do-Encode`, `Process-File` stay per red line |
| 8 | `lib.rs` | 6 | 6 | ✅ **Complete** |
| 9 | `queueView.js` | 4 | 4 | ✅ **Wave 6 split complete** — summary/review/detail/launch children done; priority/strategy/file-overrides command paths stay in parent |
| 10 | `crossPageContextView.sampleValidation.js` | 3 | 3 | ✅ **Wave 6 split complete** — worksheet/runbook/records nested children done |
| 11 | `settingsView.js` | 2 | 2 | ✅ **Wave 6 split complete** — raw-triage/safety-lock read-only children done |
| 12 | `diagnosticsView.js` | 3 | 3 | ✅ **Wave 6 split complete** — active-jobs/log/investigation read-only children done |

**Waves 1–3 are complete.** All original production-code god-file splits landed.
**Wave 4** is complete for low-risk CSS/markup splits. **Wave 5** test-file splitting is complete.
**Wave 6** is complete for safe child splits. The narrowed `queueView.detail.js` child owns read-only selected-row detail/diagnostics/open-history rendering only; Queue priority, strategy, file-overrides, queue open, and diagnostics open/tail dispatch stay in `queueView.js`.

---

## 1. Why split, and what "god file" means here

A **god file** in this codebase has one or more of:

1. **>1,500 lines.** Reviewing any change requires scrolling past dozens of unrelated concerns.
2. **>80 function/method definitions.** Cross-function reasoning is overwhelmed.
3. **Mixed responsibilities** — at minimum two of: rendering, command dispatch, evidence parsing, policy, business logic, IO, mutation orchestration.
4. **Mixed risk tiers** — pure read-only helpers live next to mutation commands. A reviewer who touches a render helper has to re-verify the safety of every mutation path in the same file.

Splitting reduces the **blast radius** of any change. Pure read-only evidence helpers can be moved with mechanical certainty; command/mutation flows need careful contract preservation. We extract the safe layer first.

### 1.1 Guiding principles (in order)

1. **Read-only / pure helpers first.** They have no side effects, so refactor risk is mechanical.
2. **Keep the namespace export shape stable.** `window.mediaPipelineQueueView.fn()` must still work — the IIFE re-exports moved functions from sub-modules. Flat exports stay flat. **No call-site changes** in the first pass.
3. **One file per coherent concern.** A 600-line file that does one thing well is better than a 1,800-line file split into three confusingly-named modules.
4. **Inventory parity.** Every split must keep `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`, `WEBVIEW_DOM_ID_INVENTORY.md`, `API_ROUTE_INVENTORY.md`, and `TEST_COVERAGE_MATRIX.md` accurate **in the same chunk** as the split.
5. **No new behaviour in a split chunk.** Splits are pure refactors. Feature work goes in a separate chunk after the split lands.
6. **Tests-as-contracts.** Existing tests must pass unchanged. If a test relies on a private helper, expose that helper through the existing namespace object before moving it.

### 1.2 What is explicitly **not** a god file (yet)

- `index.html` (5,061 lines) — markup-only god; splitting requires a partial/include layer. Defer until JS splits land and demonstrate the include pattern via JS modules.
- `styles.css` (2,595 lines) — defer until JS splits stabilise. The split target shape (`tokens.css`, `layout.css`, `components.css`, `pages/*.css`) is well-known; this is a known-late task.
- `network_tab.py`, `coordinator.py`, `worker.py` — chunky but not priority unless actively under change.
- Large test files (`test_application_facade.py`, etc.) — split after production-code parents stabilise.

---

## 2. Priority order

| # | File | Lines | Defs | Risk to split | Safe-first extraction | Final module count |
|---|---|---:|---:|---|---|---:|
| 1 | `application/facade_sample_validation_policy.py` | 4,125 | 102 | **Low** — almost all helpers are pure | Worksheet parsing, reconciliation, evidence packets | 6 modules |
| 2 | `ui_web/static/assets/completedView.js` | 4,850 | 195 | **Medium** — read-only but rendering chains | Acceptance / route-agreement / pending-proof / reconciliation | 5 modules |
| 3 | `ui_web/static/assets/settingsView.js` | 4,743 | 212 | **Medium** — per-domain builders are clean boundaries | One builder module per domain (audio, video, subtitle, queue, runtime, file-safety, pending, network) | 9 modules |
| 4 | `ui_web/static/assets/launchView.js` | 4,366 | 175 | **High** for command flow, **Low** for read-only | Risk handoff / boundary / intent / preflight / real-media proof | 5 modules (commands stay in `launchView.js`) |
| 5 | `ui_web/static/assets/pendingPublishView.js` | 3,815 | 174 | **Medium** | Drain evidence / guard / recovery-plan / diagnostics handoff | 5 modules |
| 6 | `ui_web/static/assets/crossPageContextView.js` | 3,642 | 182 | **Low** — context boards are independent | Conflict board, sample correlation, settings evidence, sample-validation integration | 5 modules |
| 7 | `Pipeline/MediaPipeline_chatgpt.ps1` | 2,629 | 23 | **High** for orchestration, **Low** for pure helpers | Scratch copy, output path planning, executable resolution, show overrides → already-extracted-style `Modules/*.ps1` files | 5 new module files |
| 8 | `DesktopApp/tauri_shell/src-tauri/src/lib.rs` | 1,997 | — | **Medium** — Rust module boundaries are clean | `backend_process`, `backend_contract`, `close_readiness`, `debug_webview`, `dialogs` | 5 sub-modules |

**Total post-split:** roughly 8 god files → ~45 focused modules.

---

## 3. Detailed split plans

### 3.1 `application/facade_sample_validation_policy.py` (4,125 lines / 102 defs)

This is the cleanest split target: most functions are pure mapping/parsing helpers with no shared state beyond the `ResolvedPaths` argument. The public surface (functions called from other modules) is the dozen top-level `sample_validation_*_payload` functions — everything else is `_private`.

**Proposed module layout** (all under `application/sample_validation/`):

| Module | Owns | Approx. lines | Functions moved |
|---|---|---:|---|
| `__init__.py` | Re-exports the public surface for backwards compatibility | 80 | `sample_validation_preview`, `append_sample_validation_record`, `sample_validation_log_payload`, all `sample_validation_*_payload` functions |
| `worksheet.py` | Worksheet-run parsing, markdown tables, sample/packet rows | ~600 | `_worksheet_*`, `_extract_markdown_table_rows`, `_split_markdown_row`, `_is_markdown_separator_cell`, `_sample_set_worksheet_samples` |
| `reconciliation.py` | Validation-record reconciliation and current-evidence comparison against pending/completed artifacts | ~700 | `sample_validation_reconciliation_payload`, `sample_validation_current_evidence_payload`, `_reconcile_validation_record`, `_current_validation_artifact_index`, `_pending_publish_*`, `_row_path_values`, path-token helpers |
| `evidence.py` | Evidence packet / post-run capture and evidence counting | ~600 | `sample_validation_evidence_packet_payload`, `sample_validation_post_run_capture_payload`, `_evidence_packet_row`, `_record_evidence_list`; normalization helpers stay with append-record validation until `_shared.py` lands |
| `readiness.py` | Readiness checks across queue/completed/diagnostics/pending/settings/log | ~500 | `sample_validation_readiness_payload`, all `_*_readiness_row` helpers, `_readiness_row`, `sample_validation_append_readiness_payload` |
| `pilot_plan.py` | Pilot plan / cutover gate / sample-set guide / pilot runbook | ~700 | `sample_validation_pilot_plan_payload`, `sample_validation_cutover_gate_payload`, `sample_validation_sample_set_guide_payload`, `sample_validation_pilot_runbook_payload`, `_pilot_plan_row`, `_pilot_execution_row`, `_pilot_status_from_row`, `_cutover_gate_row`, `_sample_set_guide_row`, `_sample_record_matches_category`, `_sample_set_category_matches` |
| `policy_alignment.py` | Policy alignment + validation audit + evidence gap | ~400 | `sample_validation_policy_alignment_payload`, `sample_validation_validation_audit_payload`, `sample_validation_evidence_gap_payload`, `_policy_alignment_row`, `_policy_alignment_guardrail` |
| `summary.py` | Validation-log summary counts and latest-record rollup | ~100 | `sample_validation_log_summary`, `SAMPLE_VALIDATION_CHECK_KEYS`, `_count_values` |
| `record.py` | Record schema, preview/request normalization, path-safety warnings | ~225 | `_normalized_sample_validation_record`, `_normalize_*` helpers, `_json_size`, `_utc_now` |
| `log_payload.py` | Read-only validation-log payload, log path, bounded tail parsing, history envelope | ~300 | `sample_validation_log_path`, `sample_validation_log_payload`, `_read_tail_text`, `_sample_validation_read_guardrail`, `_dedupe` |
| `_shared.py` | Future tiny helpers used by 3+ siblings — **explicitly deferred until 3+ siblings provably share a helper** | ~150 | `_config_bool`, `_read_tail_text`, `_read_head_text`, `_dedupe`, `_safe_mtime`, `_safe_leaf`, `_yes_no` |

**Public-surface preservation contract:** Every name currently importable as `from .facade_sample_validation_policy import X` must remain importable from that path. Implement this by making `facade_sample_validation_policy.py` a 30-line re-export shim:

```python
from .sample_validation import *  # noqa: F401,F403
```

That guarantees zero call-site changes outside the split.

**Safe-first extraction (chunk 1):** `worksheet.py` only. The worksheet-parsing helpers (`_worksheet_run_row`, `_worksheet_sample_rows`, `_worksheet_packet_rows`, `_extract_markdown_table_rows`, `_split_markdown_row`) are referenced only inside this file. Moving them costs nothing and removes 600 lines.

**Execution note — 2026-05-18:** Done. `sample_validation_worksheet_runs_payload`, worksheet markdown parsing helpers, and `_sample_set_worksheet_samples` now live in `application/sample_validation/worksheet.py`; `facade_sample_validation_policy.py` keeps the old import surface by importing those names.

**Execution note — 2026-05-18:** `readiness.py` is done for sample-validation readiness and append-readiness advisory payloads. `sample_validation_readiness_payload`, `sample_validation_append_readiness_payload`, readiness row helpers, bounded log/pending-publish evidence readers, and the shared acceptance-check table now live in `application/sample_validation/readiness.py`; `facade_sample_validation_policy.py` keeps the old import surface by importing those names and still owns preview/append orchestration plus the remaining reconciliation/evidence/pilot/policy helpers.

**Execution note — 2026-05-18:** `reconciliation.py` is done for sample-validation reconciliation and current-evidence payloads. `sample_validation_reconciliation_payload`, `sample_validation_current_evidence_payload`, current artifact indexing, bounded pending-publish clue scanning, path-token helpers, and row reconciliation now live in `application/sample_validation/reconciliation.py`; `facade_sample_validation_policy.py` keeps the old import surface by importing those names and still owns preview/append orchestration plus the remaining evidence/pilot/policy helpers.

**Execution note — 2026-05-18:** `evidence.py` is done for sample-validation evidence packet and post-run capture payloads. `sample_validation_evidence_packet_payload`, `sample_validation_post_run_capture_payload`, `_evidence_packet_row`, `_record_evidence_list`, and the shared evidence-key tuple now live in `application/sample_validation/evidence.py`; normalization helpers intentionally remain in `facade_sample_validation_policy.py` because preview/append record validation still owns request normalization and path-safety warnings.

**Execution note — 2026-05-18:** `pilot_plan.py` is started for the low-risk sample-set guide slice. `sample_validation_sample_set_guide_payload`, the representative sample category table, sample-category key set, worksheet/category matching helpers, and sample-label/path leaf helper now live in `application/sample_validation/pilot_plan.py`; `facade_sample_validation_policy.py` imports that payload builder and constants while still owning pilot-plan, cutover-gate, pilot-runbook, evidence-gap, audit, policy-alignment, preview, and append-record orchestration.

**Execution note — 2026-05-18:** `pilot_plan.py` now also owns the pilot-plan payload slice. `sample_validation_pilot_plan_payload`, its pilot stage/status row helpers, execution-checklist row helper, and pilot-plan/execution-checklist schemas moved into `application/sample_validation/pilot_plan.py`; `facade_sample_validation_policy.py` imports the payload builder while cutover-gate, pilot-runbook, log parsing, preview/append normalization, and remaining shared helpers stay in the facade.

**Execution note — 2026-05-18:** `pilot_plan.py` now also owns the cutover-gate payload slice. `sample_validation_cutover_gate_payload`, the cutover row helper, and the cutover-gate schema moved into `application/sample_validation/pilot_plan.py`; `facade_sample_validation_policy.py` imports the payload builder while pilot-runbook, log parsing, preview/append normalization, and remaining shared helpers stay in the facade.

**Execution note — 2026-05-19:** `pilot_plan.py` now also owns the pilot-runbook payload slice. `sample_validation_pilot_runbook_payload` and the pilot-runbook schema moved into `application/sample_validation/pilot_plan.py`; `facade_sample_validation_policy.py` imports the payload builder while log parsing, preview/append normalization, and remaining shared helpers stay in the facade.

**Execution note — 2026-05-19:** `summary.py` is done for the validation-log summary slice. `sample_validation_log_summary`, the validation check-key tuple, summary schema, and local value-count helper now live in `application/sample_validation/summary.py`; `facade_sample_validation_policy.py` imports the summary builder while JSONL reading, preview/append normalization, and remaining shared helpers stay in the facade.

**Execution note — 2026-05-19:** `record.py` is done for the sample-validation record-normalization slice. `SAMPLE_VALIDATION_RECORD_SCHEMA`, `SAMPLE_VALIDATION_REQUEST_MAX_BYTES`, `_normalized_sample_validation_record`, request field normalization helpers, path-root warning helpers, and the strict JSON-size helper now live in `application/sample_validation/record.py`; `facade_sample_validation_policy.py` imports the schema/size/normalization helpers while append/write behavior, JSONL reading, log payload assembly, and remaining shared helpers stay in the facade.

**Execution note — 2026-05-19:** `log_payload.py` is done for the read-only sample-validation history slice. `sample_validation_log_path`, `sample_validation_log_payload`, the log schema/limit constants, bounded tail reader, read guardrail, and local dedupe helper now live in `application/sample_validation/log_payload.py`; `facade_sample_validation_policy.py` imports the path/payload helpers while preview normalization and append/write behavior stay in the facade.

**Execution note — 2026-05-18:** `policy_alignment.py` is started for the saved-policy alignment slice. `sample_validation_policy_alignment_payload`, `_policy_alignment_row`, `_policy_alignment_guardrail`, and the tiny config/text helpers needed by that payload now live in `application/sample_validation/policy_alignment.py`; `facade_sample_validation_policy.py` imports that payload builder while still owning evidence-gap and validation-audit rollups until a later chunk.

**Execution note — 2026-05-18:** `policy_alignment.py` now also owns the evidence-gap summary slice. `sample_validation_evidence_gap_payload` and its local status/row mapping helpers moved into `application/sample_validation/policy_alignment.py`; `facade_sample_validation_policy.py` imports the payload builder while validation-audit remains in the facade for a later chunk.

**Execution note — 2026-05-18:** `policy_alignment.py` now also owns the validation-audit rollup slice. `sample_validation_validation_audit_payload` moved into `application/sample_validation/policy_alignment.py`; `facade_sample_validation_policy.py` imports the payload builder while log parsing, preview/append normalization, pilot-plan/cutover/runbook orchestration, and remaining shared helpers stay in the facade.

**Test impact:** `test_application_facade.py` and any `test_sample_validation_*` files import from `facade_sample_validation_policy`. The re-export shim keeps those imports valid. Add `test_sample_validation_worksheet.py` for the new module (or fold worksheet-specific test cases into a renamed file).

---

### 3.2 `ui_web/static/assets/completedView.js` (4,850 lines / 195 funcs)

The file has clean **sub-domain clusters** with distinct prefixes. Functions in each cluster only reference each other plus a few shared lookups (`lastCompletedPayload`, `lastCompletedRows`, etc.).

**Function-cluster analysis** (from the grep):

| Cluster | Prefix | Approx. lines | Func count |
|---|---|---:|---:|
| Main render + table | `renderCompleted`, `renderCompletedRows`, `renderCompletedDetail` | ~400 | ~10 |
| Inventory/freshness/empty-state | `completedInventory*`, `completedEmpty*`, `completedFreshness*` | ~200 | ~6 |
| Integrity + workflow + breakdown + runtime + consistency + validation | `completedIntegrity*`, `completedWorkflow*`, `completedBreakdown*`, `completedRuntime*`, `completedConsistency*`, `completedValidation*` | ~600 | ~25 |
| Review board + digest | `completedReview*` | ~400 | ~10 |
| Investigation + filter visibility | `completedInvestigation*`, `completedFilter*`, `completedFocusedInvestigation*`, `completedFilterVisibility*` | ~250 | ~10 |
| Size review + size evidence | `completedSizeReview*`, `completedSizeEvidence*`, `selectedCompletedSizeEvidence*` | ~500 | ~10 |
| Real-media proof + policy alignment | `completedRealMediaProof*`, `completedPolicy*`, `completedRealMediaTrace*` | ~700 | ~20 |
| Final trust + pilot evidence | `completedFinalTrust*`, `completedPilotEvidence*`, `selectedCompleted*Trust*` | ~700 | ~25 |
| Output acceptance + route agreement | `completedAcceptance*`, `completedRouteAgreement*` | ~700 | ~30 |
| Pending proof + publish reconciliation | `completedProof*`, `completedPendingProof*`, `publishReconciliation*` | ~700 | ~30 |
| Diagnostics handoff + open commands | `completedDiagnostics*`, `isCompletedOpenCommand`, `completedOpenHistory*` | ~200 | ~10 |

**Proposed module layout** (flat in `ui_web/static/assets/`, dotted names — see §4.5.2; all IIFEs hang off the same `window.mediaPipelineCompletedView` namespace via the stash-global pattern):

| Module | Owns | Approx. lines |
|---|---|---:|
| `completedView.js` (kept) | Main `renderCompleted`, table rendering, filter/state, and the namespace object + flat exports | ~1,150 |
| `completedView.evidence.js` | Acceptance + route agreement + pending proof + publish reconciliation (largest, lowest-risk cluster — all read-only) | ~1,300 |
| `completedView.proof.js` | Real-media proof + policy alignment + final trust + pilot evidence packet | ~1,400 |
| `completedView.review.js` | Review board + investigation/filter visibility + size review/evidence + integrity/workflow/breakdown/runtime/consistency/validation | ~1,450 |
| `completedView.diagnostics.js` | Diagnostics handoff + open commands + open history | ~250 |

**Safe-first extraction (chunk 1):** `completedView.evidence.js` — the acceptance + route-agreement + pending-proof cluster. These are all pure read-only renderers. Moving them removes 1,300 lines from the parent and exposes zero new stable public globals (the namespace object and flat exports stay in `completedView.js`; the child uses a temporary stash global consumed during parent load).

**Critical:** the sub-module files must load **before** `completedView.js` in `index.html` so the parent IIFE can read the stash global (`window.__completedViewEvidenceModule`) and re-export the functions onto `window.mediaPipelineCompletedView`. The stash is deleted after consumption — see §4.5.2 for the exact pattern.

**Execution note — 2026-05-18:** `completedView.evidence.js` is implemented for the acceptance, route-agreement, pending-proof, and publish-reconciliation read-only cluster. `completedView.js` still owns the canonical namespace/flat exports, selected row/table state, proof/final-trust/pilot evidence renderers, diagnostics/open command surfaces, and the parent render orchestration. No API routes, backend publish behavior, DOM IDs, media policy, or mutation controls changed.

**Execution note — 2026-05-18:** `completedView.diagnostics.js` is implemented for selected-row diagnostics actions, backend-allowlisted diagnostics open/tail handoff, guidance copy, and Diagnostics bridge button rendering. `completedView.js` still owns the canonical namespace/flat exports, selected row/table/detail state, completed open command history, proof/final-trust/pilot evidence renderers, and the parent render orchestration. No API routes, backend publish behavior, DOM IDs, media policy, or mutation controls changed.

**Execution note — 2026-05-18:** `completedView.proof.js` is implemented for the real-media output proof ladder, saved-policy alignment comparison, final output trust walkthrough, and selected pilot evidence packet. `completedView.js` still owns the canonical namespace/flat exports, selected row/table/detail state, review/size boards, selected-row sample-validation comparison, completed open command history, and parent render orchestration. No API routes, backend publish behavior, DOM IDs, media policy, or mutation controls changed.

**Execution note — 2026-05-18:** `completedView.review.js` is implemented for the integrity/workflow/breakdown/runtime/consistency/validation panels, review board/digest, investigation/filter visibility, size review/evidence, and selected-row review/trust/sample-validation comparison helpers. `completedView.js` still owns the canonical namespace/flat exports, parent render orchestration, selected row/table state, backend-selected open commands/history, and child-module stash consumption/deletion. No API routes, backend publish behavior, DOM IDs, media policy, or mutation controls changed.

---

### 3.3 `ui_web/static/assets/settingsView.js` (4,743 lines / 212 funcs)

The cleanest god file in the codebase — each domain has its **own self-contained builder block** with a 4-function shape:

- `set{Domain}BuilderControl(id, key, kind, fallback)`
- `sync{Domain}SettingsBuilderFromConfig()`
- `mark{Domain}SettingsBuilderDirty()`
- `read{Domain}BuilderValue(id, kind, label)`
- `collect{Domain}SettingsBuilderPatch()`
- `apply{Domain}SettingsBuilderToPatch()`
- `render{Domain}SettingsBuilderGuidance()`

Domains identified: **video-detail**, **file-safety**, **pending-publish**, **network**, **queue**, **runtime**, **subtitle**, **audio**. Each block is ~150–250 lines.

**Proposed module layout** (flat in `ui_web/static/assets/`, dotted names — see §4.5.2):

| Module | Owns | Approx. lines |
|---|---|---:|
| `settingsView.js` (kept) | Raw triage, action plan, safety locks, save review, save progress, backend result, patch impact summary, policy delta, launch impact handoff, top-level `renderSettings` | ~1,800 |
| `settingsView.builders.audio.js` | All audio builder functions | ~200 |
| `settingsView.builders.video.js` | Video-detail builder | ~200 |
| `settingsView.builders.subtitle.js` | Subtitle builder (largest — ~300 lines, includes BDPGS OCR evidence) | ~300 |
| `settingsView.builders.queue.js` | Queue builder | ~150 |
| `settingsView.builders.runtime.js` | Runtime builder | ~200 |
| `settingsView.builders.file_safety.js` | File-safety builder | ~150 |
| `settingsView.builders.pending.js` | Pending-publish builder | ~200 |
| `settingsView.builders.network.js` | Network builder (includes JSON text input handling) | ~250 |

**Shared helpers each builder needs:** `settingsBuilderConfigValue`, `settingsFieldDefinition`, `readSettingsBuilderNumber`, `readSettingsBuilderFloat`, `markSettingsBuilderDirty`, `parseSettingsPatchJson`. These stay in `settingsView.js` and are accessed via `window.*` guards.

**Safe-first extraction (chunk 1):** `settingsView.builders.audio.js`. Audio is mid-size, no special parsing, and currently lives between unrelated subtitle and file-safety blocks. Once that lands cleanly, the same pattern applies to all other domains.

**Execution note — 2026-05-18:** `settingsView.builders.audio.js` is done. The audio builder implementation now lives in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.audio.js` as a split-child factory stash consumed by `settingsView.js`; the parent still owns the canonical `window.mediaPipelineSettingsView` namespace, flat compatibility exports, builder state object, event wiring, and backend-owned preview/save command flow.

**Execution note — 2026-05-18:** `settingsView.builders.video.js` is done. The video-detail builder implementation now lives in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.video.js` as a sibling split-child factory stash consumed and deleted by `settingsView.js`; the parent still owns public Settings exports, event wiring, settings patch preview/save, and backend-authored media policy boundaries.

**Execution note — 2026-05-18:** `settingsView.builders.subtitle.js` is done. The subtitle builder and BDPGS OCR evidence helpers now live in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.subtitle.js` as a sibling split-child factory stash consumed and deleted by `settingsView.js`; the parent still owns public Settings exports, event wiring, settings patch preview/save, and backend-authored subtitle/OCR policy boundaries.

**Execution note — 2026-05-18:** `settingsView.builders.queue.js` is done. The queue builder implementation now lives in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.queue.js` as a sibling split-child factory stash consumed and deleted by `settingsView.js`; the parent still owns public Settings exports, event wiring, settings patch preview/save, and backend-authored queue discovery/reprocess decisions.

**Execution note — 2026-05-18:** `settingsView.builders.runtime.js` is done. The runtime builder implementation now lives in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.runtime.js` as a sibling split-child factory stash consumed and deleted by `settingsView.js`; the parent still owns public Settings exports, event wiring, settings patch preview/save, and backend-authored process/tool/runtime behavior.

**Execution note — 2026-05-18:** `settingsView.builders.file_safety.js` is done. The file-safety builder implementation now lives in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.file_safety.js` as a sibling split-child factory stash consumed and deleted by `settingsView.js`; the parent still owns public Settings exports, event wiring, settings patch preview/save, and backend-authored source/scratch/output safety behavior.

**Execution note — 2026-05-18:** `settingsView.builders.pending.js` is done. The pending-publish builder implementation now lives in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.pending.js` as a sibling split-child factory stash consumed and deleted by `settingsView.js`; the parent still owns public Settings exports, event wiring, settings patch preview/save, and backend-authored deferred-publish/drain behavior.

**Execution note — 2026-05-18:** `settingsView.builders.network.js` is done. The network builder implementation now lives in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.builders.network.js` as a sibling split-child factory stash consumed and deleted by `settingsView.js`; the parent still owns public Settings exports, event wiring, settings patch preview/save, and backend-authored worker/coordinator lifecycle behavior.

---

### 3.4 `ui_web/static/assets/launchView.js` (4,366 lines / 175 funcs)

This file is **dangerous to split casually** because it owns mutation commands (`pipeline/start`, `audit/start`, `rerun/start`, `pipeline/control`). The good news: the function clusters separate cleanly into **read-only checklists** vs **command flow**.

**Function-cluster analysis:**

| Cluster | Prefix | Risk | Approx. lines |
|---|---|---|---:|
| Command dispatch + busy/lock + control confirm | `setLaunchCommandBusy`, `rejectLaunchCommandWhileBusy`, `confirmControlAction`, `collect*StartRequest` | **High** (mutation) | ~500 |
| Result rendering + correlation lines | `renderLaunchCommandResult`, `launchCommandResultCorrelationLines` | Low | ~150 |
| Settings risk handoff | `launchSettingsRisk*`, `launchSettingsDecision*` | Low (read-only) | ~700 |
| Policy boundary | `launchPolicyBoundary*`, `launchPolicyFormat*` | Low | ~400 |
| Settings intent checklist | `launchSettingsIntent*` | Low | ~500 |
| Scope reconciliation | `launchScopeReconciliation*`, `launchScope*Posture` | Low | ~400 |
| Start decision summary | `launchStartDecision*` | Low | ~400 |
| Real-media proof handoff | `launchRealMediaProof*`, `launchSampleExecution*`, `launchWorksheet*`, `launchSampleValidation*`, `launchPolicyAlignment*`, `launchSampleSetGuide*` | Low (all read-only) | ~900 |
| Pilot run readiness | `launchPilot*` | Low | ~400 |
| Backend preflight | `launchBackendPreflight*` | Low | ~400 |
| Pre-flight summary | `pipelineLaunchPreflightLines`, `auditLaunchPreflightLines`, `rerunLaunchPreflightLines`, `renderLaunch*Preflight*` | Low | ~150 |
| Pipeline control history | `isPipelineControlCommand`, `pipelineControlHistoryLine`, `renderPipelineControlHistory` | Low | ~50 |

**Proposed module layout:**

| Module | Owns | Lines |
|---|---|---:|
| `launchView.js` (kept) | Command dispatch (busy/lock/confirm), `collect*StartRequest`, result rendering, top-level `initLaunchViewEvents` | ~1,500 |
| `launchView.risk.js` | Settings risk handoff + policy boundary + settings intent checklist | ~1,600 |
| `launchView.scope.js` | Scope reconciliation + start decision summary | ~800 |
| `launchView.realmedia.js` | Real-media proof handoff + sample execution + worksheet + sample-validation evidence + policy alignment + sample-set guide | ~900 |
| `launchView.preflight.js` | Pilot run readiness + backend preflight + pre-flight summary lines + pipeline control history | ~700 |

**Red line:** the mutation cluster — `collectPipelineStartRequest`, `collectAuditStartRequest`, `collectRerunStartRequest`, command busy/lock/confirm — **must stay in `launchView.js`** until every read-only extraction is stable and covered. These functions control what the backend actually receives.

**Safe-first extraction (chunk 1):** `launchView.realmedia.js`. The real-media proof handoff is the largest read-only chunk (~900 lines, ~25 functions) and has the cleanest boundary — every function takes `context = lastLaunchRealMediaProofContext` as its anchoring argument.

**Execution note — 2026-05-18:** `launchView.realmedia.js` is implemented for the Launch real-media proof handoff, generated worksheet evidence, Sample Validation record evidence, sample-set coverage, saved-policy-vs-Queue-route comparison, and sample execution checklist. `launchView.js` still owns the canonical `window.mediaPipelineLaunchView` namespace, flat compatibility exports, start/control command dispatch, start request collection, busy/confirmation locks, backend preflight, pilot readiness orchestration, and child-module stash consumption/deletion. No API routes, backend launch/drain behavior, DOM IDs, media policy, or mutation controls changed.

**Execution note — 2026-05-18:** `launchView.scope.js` is implemented for Launch scope reconciliation and start decision summary helpers. `launchView.js` still owns the canonical `window.mediaPipelineLaunchView` namespace, flat compatibility exports, start/control command dispatch, start request collection, busy/confirmation locks, risk/settings/preflight/pilot orchestration, and child-module stash consumption/deletion. No API routes, backend launch/drain behavior, DOM IDs, media policy, or mutation controls changed.

**Execution note — 2026-05-18:** `launchView.risk.js` is implemented for saved-settings risk handoff, active media-policy boundary, staged-vs-saved policy comparison, and saved-settings launch-intent checklist helpers. `launchView.js` still owns the canonical `window.mediaPipelineLaunchView` namespace, flat compatibility exports, start/control command dispatch, start request collection, busy/confirmation locks, backend preflight/pilot orchestration, and child-module stash consumption/deletion. No API routes, backend launch/drain behavior, DOM IDs, media policy, or mutation controls changed.

**Execution note — 2026-05-18:** `launchView.preflight.js` is implemented for Launch pilot run readiness, backend preflight, pre-flight summary lines, audit progress rendering, and pipeline control history helpers. `launchView.js` still owns the canonical `window.mediaPipelineLaunchView` namespace, flat compatibility exports, start/control command dispatch, start request collection, busy/confirmation locks, confirmation prompts, and child-module stash consumption/deletion. No API routes, backend launch/drain behavior, DOM IDs, media policy, or mutation controls changed.

---

### 3.5 `ui_web/static/assets/pendingPublishView.js` (3,815 lines / 174 funcs)

Similar pattern to `completedView.js`: read-only renderers around a small mutation surface (`/api/pending-publish/open`, drain orchestration). Splits cleanly into:

| Module | Owns | Lines |
|---|---|---:|
| `pendingPublishView.js` (kept) | Main render, table, selection, drain command dispatch | ~1,200 |
| `pendingPublishView.drain.js` | Drain evidence + backend drain scope preview + drain history/events/summary + drain correlation | ~750 |
| `pendingPublishView.confidence.js` | Confidence scoring + readiness signals + Publish Button Guard | ~500 |
| `pendingPublishView.recovery.js` | Recovery plan + completed correlation | ~800 |
| `pendingPublishView.diagnostics.js` | Diagnostics handoff + open commands | ~400 |

**Safe-first extraction (chunk 1):** `pendingPublishView.recovery.js` (recovery plan is the most isolated cluster — calls only `/api/pending-publish/recovery-plan`).

**Execution note — 2026-05-18:** `pendingPublishView.recovery.js` is implemented for backend-authored recovery dry-run planning, recovery-plan row rendering/detail, recovery-plan history, busy-state protection, and the `/api/pending-publish/recovery-plan` command handoff. `pendingPublishView.js` still owns the canonical `window.mediaPipelinePendingPublishView` namespace, flat compatibility exports, main Pending table, selected row state, drain command dispatch, drain guard/decision/confidence surfaces, and child-module stash consumption/deletion. No backend drain behavior, DOM IDs, media policy, file movement, repair, delete, publish, or manifest mutation controls changed.

**Execution note — 2026-05-18:** `pendingPublishView.diagnostics.js` is implemented for selected-row diagnostics guidance, backend allowlisted Diagnostics bridge actions, Pending Publish open/tail handoff, open busy-state protection, open command history, and the `/api/pending-publish/open` command handoff. `pendingPublishView.js` still owns the canonical namespace/flat compatibility exports, main Pending table/filter/selection, detail orchestration, drain command dispatch, drain guard/decision/confidence surfaces, recovery child consumption, and diagnostics child consumption/deletion. No backend drain behavior, DOM IDs, media policy, arbitrary path construction, file movement, repair, delete, publish, or manifest mutation controls changed.

**Execution note — 2026-05-18:** `pendingPublishView.confidence.js` is implemented for drain action confidence, drain decision checklist, post-drain trust review, and the frontend Publish Button Guard's evidence-only guard state. `pendingPublishView.js` still owns the canonical namespace/flat compatibility exports, main Pending table/filter/selection state, backend drain command dispatch, recovery/diagnostics child consumption, and confidence child consumption/deletion. The child receives parent-authored evidence helpers through dependency injection and adds no API route, media policy, file movement, repair, delete, publish, or manifest mutation control.

**Execution note — 2026-05-18:** `pendingPublishView.drain.js` is implemented for backend drain scope preview, drain evidence rows, backend-authored drain command history, recent drain events, durable drain summary, and drain correlation. `pendingPublishView.js` still owns the canonical namespace/flat compatibility exports, main Pending table/filter/selection state, backend drain command dispatch, recovery/diagnostics/confidence child consumption, and drain child consumption/deletion. The child is read-only and receives state/evidence helpers through dependency injection; no API routes, backend drain behavior, media policy, file movement, repair, delete, publish, or manifest mutation controls changed.

---

### 3.6 `ui_web/static/assets/crossPageContextView.js` (3,642 lines / 182 funcs)

Each cross-page board is independent — they share only a small set of context-helper functions. The initial queue/completed/pending naming was replaced during execution with the actual low-coupling clusters found in the post-sampleValidation parent: conflict board, sample correlation, settings evidence, and sample-validation integration.

| Module | Owns | Lines |
|---|---|---:|
| `crossPageContextView.js` (kept) | Top-level orchestration, context-line composition, navigation handoffs, namespace/flat exports | ~700 |
| `crossPageContextView.conflict.js` | Exact-path/same-leaf conflict detection across Queue/Completed/Pending and conflict-board rendering | ~300 |
| `crossPageContextView.sample.js` | Selected/recent sample correlation, diagnostics matching, validation-template helpers | ~300 |
| `crossPageContextView.settings.js` | Saved-settings/media-policy evidence extraction used by the cross-page and sample-validation surfaces | ~120 |
| `crossPageContextView.sampleValidation.js` | Sample-validation cross-page integration | ~700 |

**Safe-first extraction (chunk 1):** `crossPageContextView.sampleValidation.js` (most self-contained — least intersection with other boards). The final pass then moved the remaining coherent clusters into `conflict`, `sample`, and `settings` children instead of forcing artificial queue/completed/pending module names.

**Execution note — 2026-05-18:** `crossPageContextView.sampleValidation.js` is done. The Home sample-validation worksheet, runbook, cutover, sample-set, category, completed-packet, acceptance-gate, record-review, preview, and append helpers now live in the split child factory. `crossPageContextView.js` retains the public namespace/flat exports, the selected-state accessors, and the parent-owned cross-page context helpers.

**Execution note — 2026-05-19:** `crossPageContextView.conflict.js` is done. Cross-page conflict detection engine (exact-path and same-leaf matching across Queue/Completed/Pending), all conflict board helpers, and `renderCrossPageConflictBoard` now live in the split child factory. All 17 shared utilities (DOM helpers, path accessors, crossPageRows/Count/Normalize/Leaf) are injected at factory call time — no window reads inside the child.

**Execution note — 2026-05-19:** `crossPageContextView.sample.js` is done. Cross-page sample correlation engine (seed collection from selected + recent rows, page match collection, diagnostics match handoff), sample evidence scoring, sample status/lines helpers, validation-template helpers, and both render functions now live in the split child factory. `crossPagePendingLocal` is in the factory parameter list and used in `crossPageSampleAddSeed` for parked-payload paths.

**Execution note — 2026-05-19:** `crossPageContextView.settings.js` is done. Settings payload accessors, config-key evidence extraction (`crossPageSettingsPolicyEvidence`), and settings-policy status/summary logic now live in the split child factory. Only `crossPageCount` is injected; no other window reads inside the child. Stash consumption order in the rewritten parent: conflict → sample → settings → sampleValidation, so `crossPageSettingsPolicyEvidence` is available when the sampleValidation factory is called.

All four `crossPageContextView` children are now in `index.html` in the correct load order and all stashes are consumed and deleted by the parent IIFE. Split complete — this was the last open item in Waves 1–3.

---

### 3.7 `Pipeline/MediaPipeline_chatgpt.ps1` (2,629 lines / 23 funcs)

The script has already extracted ~34 modules into `Pipeline/Modules/`. Remaining functions in the main script:

| Cluster | Lines | Funcs |
|---|---:|---:|
| Config getters (`Get-ConfigBool`, `Get-ConfigInt`, `Get-ConfigDouble`, `Get-ConfigLogLevel`, `Get-ConfigChoice`) | 382–500 | 5 |
| Show overrides (`Resolve-ShowOverrides`) | 802–900 | 1 |
| Tool resolution (`Resolve-BundledExecutable`) | 946–1014 | 1 |
| Old temp cleanup (`Clear-OldTempFiles`) | 1036–1048 | 1 |
| Scratch copy (`Get-SourceFingerprint` through `Ensure-ScratchCopy`) | 1152–1300 | 8 |
| Output path planning (`Get-OutputPaths`, `Test-PathComponentSupport`, `Test-OutputPathCapability`) | 1304–1407 | 3 |
| Remux orchestration (`Invoke-Tx3gSidecarExportForExistingOutput`, `Do-Remux`) | 1411–1810 | 2 |
| Encode orchestration (`Do-Encode`) | 1813–2338 | 1 |
| Process-File wrapper | 2346–2360 | 1 |

**Proposed extractions (low-risk, in order):**

| New module | Owns | Lines | Risk |
|---|---|---:|---|
| `Modules/ConfigGetters.ps1` | All `Get-Config*` helpers | ~150 | **Lowest** — pure functions, no shared state |
| `Modules/ShowOverrides.ps1` | `Resolve-ShowOverrides` | ~50 | Low — reads script-scope config at call time |
| `Modules/ScratchCopy.ps1` | `Get-SourceFingerprint`, `Get-FingerprintPath`, `Get-ScratchInputPath`, `Remove-EmptyScratchContainer`, `Write-ScratchFingerprint`, `Test-ScratchFingerprintMatches`, `Remove-ScratchFingerprint`, `Ensure-ScratchCopy` | ~200 | Low — reads `$script:LocalBase`, `$script:ScratchRoot` at call time |
| `Modules/OutputPathPlanning.ps1` | `Get-OutputPaths`, `Test-PathComponentSupport`, `Test-OutputPathCapability` | ~150 | Low |
| `Modules/ExecutableResolution.ps1` | `Resolve-BundledExecutable`; temp-cleanup helper can follow separately | ~100 | Low |
| `Modules/TempCleanup.ps1` | `Clear-OldTempFiles` | ~25 | Low |

**Red line:** `Do-Remux`, `Do-Encode`, and `Process-File` **stay in the main script** until the remux/encode call paths have a dedicated test harness. These functions own the entire ffmpeg orchestration and any drift in error propagation is a real-media failure.

**Safe-first extraction (chunk 1):** `Modules/ConfigGetters.ps1`. Five pure functions, zero side effects, used everywhere — dot-source the module first in the module-load array.

**Execution note — 2026-05-18:** Done. `Get-ConfigBool`, `Get-ConfigInt`, `Get-ConfigDouble`, `Get-ConfigLogLevel`, and `Get-ConfigChoice` now live in `Pipeline/Modules/ConfigGetters.ps1`; `MediaPipeline_chatgpt.ps1` dot-sources that module immediately after `Logging.ps1`.

**Execution note — 2026-05-18:** `ShowOverrides.ps1` is done. `Resolve-ShowOverrides` now lives in `Pipeline/Modules/ShowOverrides.ps1`; `MediaPipeline_chatgpt.ps1` dot-sources it after `MediaConstants.ps1`, preserving the FLAC codec helper dependency while keeping `$script:ShowOverrides` initialization and `$script:ActiveOverrides` ownership in the runtime config section.

**Execution note — 2026-05-18:** `ExecutableResolution.ps1` first pass is done. `Resolve-BundledExecutable` now lives in `Pipeline/Modules/ExecutableResolution.ps1`; `MediaPipeline_chatgpt.ps1` dot-sources it before dependency validation and still calls it only after `$scriptDir` and `$script:AllowSystemTools` are initialized.

**Execution note — 2026-05-18:** `OutputPathPlanning.ps1` is done. `Get-OutputPaths`, `Test-PathComponentSupport`, and `Test-OutputPathCapability` now live in `Pipeline/Modules/OutputPathPlanning.ps1`; `MediaPipeline_chatgpt.ps1` dot-sources it after `Naming.ps1` so destination naming helpers are available before remux, encode, library index, and processing preflight calls.

**Execution note — 2026-05-18:** `ScratchCopy.ps1` is done. `Get-SourceFingerprint`, `Get-FingerprintPath`, `Get-ScratchInputPath`, `Remove-EmptyScratchContainer`, `Write-ScratchFingerprint`, `Test-ScratchFingerprintMatches`, `Remove-ScratchFingerprint`, and `Ensure-ScratchCopy` now live in `Pipeline/Modules/ScratchCopy.ps1`; `MediaPipeline_chatgpt.ps1` dot-sources it after `SourceIdentity.ps1` and before `FailureState.ps1`, preserving scratch-copy ownership and failure registration dependencies. The focused smoke also caught and fixed timestamp normalization in `Test-ScratchFingerprintMatches` so PowerShell's JSON `DateTime` materialization does not force unnecessary scratch recopy.

**Execution note — 2026-05-18:** `TempCleanup.ps1` is done. `Clear-OldTempFiles` now lives in `Pipeline/Modules/TempCleanup.ps1`; `MediaPipeline_chatgpt.ps1` dot-sources it before startup cleanup and still calls it after state layout initialization and directory creation.

---

### 3.8 `DesktopApp/tauri_shell/src-tauri/src/lib.rs` (1,997 lines)

Rust has the cleanest split mechanism — `mod foo;` in `lib.rs` and the new file lives at `src/foo.rs` (or `src/foo/mod.rs`). Splitting is **mechanical** as long as visibility (`pub`/`pub(crate)`) is correct.

**Proposed modules** (each as `src/<name>.rs`):

| Module | Functions | Lines |
|---|---|---:|
| `lib.rs` (kept) | `run()`, top-level `tauri::Builder` wiring, panic hook setup | ~250 |
| `backend_process.rs` | `BackendProcess`, `start_backend`, `read_backend_bootstrap`, `push_bootstrap_stdout_context`, `bootstrap_error`, `spawn_backend_stdout_reader`, `spawn_pipe_drain`, `terminate_child`, `wait_for_child_exit`, `request_backend_shutdown`, `confirm_close_if_needed`, `shutdown_backend_state` | ~450 |
| `backend_contract.rs` | `validate_backend_health`, `validate_backend_contract`, `validate_backend_web_ui`, `format_list_preview`, `format_route_sample` | ~500 |
| `close_readiness.rs` | `request_close_readiness`, `close_readiness_warning_detail`, `close_readiness_watcher_lines` | ~250 |
| `debug_webview.rs` | `maybe_schedule_debug_webview_autolaunch` (both cfg branches), `debug_sample_validation_append_script`, `debug_webview_autolaunch_script` | ~250 |
| `dialogs.rs` | `confirm_close_dialog` (both cfg branches), `shell_error`, `display_bounded_path`, `format_path_candidates`, `resolve_desktop_root`, `desktop_root_candidates_from_exe_dir`, `resolve_python` | ~300 |
| `http_helpers.rs` | `request_backend_json`, `backend_response_body_preview`, `bounded_text`, `read_backend_response_capped` | ~150 |

**Visibility plan:** all extracted functions become `pub(crate)`. Types they share (`ShellResult`, `BackendBootstrap`, `BackendRoute`, `CloseReadiness`, `ContinuousWatcher`) need a `pub(crate) struct` declaration in a `types.rs` or stay inline in their owning module and get re-exported.

**Safe-first extraction (chunk 1):** `dialogs.rs`. Small, self-contained, no shared mutable state, and the cfg-gated dialog functions are already a natural unit.

**Execution note — 2026-05-18:** Done. `confirm_close_dialog`, `shell_error`, bounded path display helpers, DesktopApp root candidate resolution, and bundled-Python resolution now live in `src-tauri/src/dialogs.rs`; `lib.rs` imports those names at crate root so existing call sites and tests keep the same lookup shape.

**Execution note — 2026-05-18:** `http_helpers.rs` is also done. `request_backend_json`, `bounded_text`, and capped backend-response reads now live in `src-tauri/src/http_helpers.rs`; `lib.rs` keeps crate-root imports so validation and close-readiness call sites do not chase the helper module.

**Execution note — 2026-05-18:** `backend_contract.rs` first pass is done. Backend health validation, Local API route-contract validation, route/capability preview formatting, and `BackendRoute` now live in `src-tauri/src/backend_contract.rs`.

**Execution note — 2026-05-18:** `backend_contract.rs` planned validation scope is done. The backend-served WebView asset fragment gate, `validate_backend_web_ui`, now also lives in `src-tauri/src/backend_contract.rs`; startup wiring and tests keep the same crate-root import shape.

**Execution note — 2026-05-18:** `debug_webview.rs` is done. Debug-only WebView autolaunch scheduling and PG-2 sample-validation append/launch script builders now live in `src-tauri/src/debug_webview.rs`; `lib.rs` keeps root imports for startup wiring and tests.

**Execution note — 2026-05-18:** `close_readiness.rs` is partially done. Close-readiness DTOs, backend close-readiness request parsing, warning detail formatting, and continuous-watcher line formatting now live in `src-tauri/src/close_readiness.rs`. `confirm_close_if_needed` and `shutdown_backend_state` remain in `lib.rs` until the backend process state moves.

**Execution note — 2026-05-18:** `backend_process.rs` is partially done. Backend bootstrap payload parsing, bounded pre-bootstrap stdout context, and bootstrap error construction now live in `src-tauri/src/backend_process.rs`. `start_backend`, stdout/stderr reader setup, child termination, shutdown request, and close-window process state remain in `lib.rs` until the lifecycle owner can move as one reviewable chunk.

**Execution note — 2026-05-18:** `backend_process.rs` planned lifecycle scope is done. `BackendProcess`, backend startup, stdout/stderr pipe draining, child termination, backend shutdown request, and close-window state handling now live in `src-tauri/src/backend_process.rs`. `confirm_close_if_needed` and `shutdown_backend_state` moved with `BackendProcess` because they depend on Tauri-managed backend state; `close_readiness.rs` stays focused on close-readiness DTO/request/formatting.

**Test impact:** the `mod tests { … }` block at the bottom of `lib.rs` should be reviewed — tests covering moved functions move with them.

---

## 4. Recommended migration order

The order minimises risk by **always landing a pure read-only extraction first** in each major area, then layering on mid-risk extractions only after tests confirm the first split is stable.

### Wave 1 — Low-risk pure-helper extractions (parallelisable)

1. `application/facade_sample_validation_policy.py` → `application/sample_validation/worksheet.py` — **done 2026-05-18**
2. `ui_web/static/assets/completedView.js` → `completedView.evidence.js` — done 2026-05-18
3. `ui_web/static/assets/crossPageContextView.js` → `crossPageContextView.sampleValidation.js` — **done 2026-05-18**
4. `Pipeline/Modules/ConfigGetters.ps1` (new) extracted from `MediaPipeline_chatgpt.ps1` — **done 2026-05-18**
5. `src-tauri/src/dialogs.rs` (new) extracted from `lib.rs` — **done 2026-05-18**

**Execution note — 2026-05-18:** `crossPageContextView.sampleValidation.js` is done. The Home sample-validation worksheet, runbook, cutover, sample-set, category, completed-packet, acceptance-gate, record-review, preview, and append helpers now live in the split child factory. `crossPageContextView.js` retains the public namespace/flat exports, the selected-state accessors, and the parent-owned cross-page context helpers.

**Wave 1 gate:** every existing test passes; inventory files updated; smoke suite green. If any of these breaks, stop and diagnose before continuing.

### Wave 2 — Domain extractions (sequential within each area, parallel across areas)

6. `settingsView.js` → `settingsView.builders.audio.js` / `settingsView.builders.video.js` / `settingsView.builders.subtitle.js` / `settingsView.builders.queue.js` / `settingsView.builders.runtime.js` / `settingsView.builders.file_safety.js` / `settingsView.builders.pending.js` / `settingsView.builders.network.js` (audio builder **done 2026-05-18**; video-detail builder **done 2026-05-18**; subtitle builder **done 2026-05-18**; queue builder **done 2026-05-18**; runtime builder **done 2026-05-18**; file-safety builder **done 2026-05-18**; pending-publish builder **done 2026-05-18**; network builder **done 2026-05-18**)
7. `completedView.js` → `completedView.proof.js`, `completedView.review.js`, `completedView.diagnostics.js` (`completedView.proof.js` **done 2026-05-18**; `completedView.review.js` **done 2026-05-18**; `completedView.diagnostics.js` **done 2026-05-18**)
8. `crossPageContextView.js` → `crossPageContextView.conflict.js`, `crossPageContextView.sample.js`, `crossPageContextView.settings.js`, `crossPageContextView.sampleValidation.js` — ✅ **Complete** (`sampleValidation` **done 2026-05-18**; `conflict`, `sample`, and `settings` **done 2026-05-19**)
9. `application/sample_validation/` → `reconciliation.py`, `evidence.py`, `readiness.py`, `pilot_plan.py`, `policy_alignment.py`, `summary.py`, `record.py`, `log_payload.py`, `_shared.py` (`readiness.py` **done 2026-05-18**; `reconciliation.py` **done 2026-05-18**; `evidence.py` **done 2026-05-18**; `pilot_plan.py` sample-set guide, pilot-plan, cutover-gate, and pilot-runbook slices **done 2026-05-19**; `policy_alignment.py` saved-policy alignment, evidence-gap, and validation-audit slices **done 2026-05-18**; `summary.py` validation-log summary slice **done 2026-05-19**; `record.py` record-normalization slice **done 2026-05-19**; `log_payload.py` read-only history slice **done 2026-05-19**; `_shared.py` **deferred** — create only once 3+ siblings share a helper that doesn't already live in a named module) ✅ **Complete for planned active scope**
10. `MediaPipeline_chatgpt.ps1` → `Modules/ShowOverrides.ps1`, `Modules/ScratchCopy.ps1`, `Modules/OutputPathPlanning.ps1`, `Modules/ExecutableResolution.ps1`, `Modules/TempCleanup.ps1` (`ShowOverrides.ps1` **done 2026-05-18**; `ScratchCopy.ps1` **done 2026-05-18**; `TempCleanup.ps1` **done 2026-05-18**; `OutputPathPlanning.ps1` **done 2026-05-18**; `Resolve-BundledExecutable` portion of `ExecutableResolution.ps1` **done 2026-05-18**)
11. `lib.rs` → `backend_process.rs`, `backend_contract.rs`, `close_readiness.rs`, `debug_webview.rs`, `http_helpers.rs` (`debug_webview.rs` **done 2026-05-18**; `http_helpers.rs` **done 2026-05-18**; close-readiness DTO/request/formatting portion of `close_readiness.rs` **done 2026-05-18**; backend health/route-contract and WebView asset-gate portions of `backend_contract.rs` **done 2026-05-18**; backend bootstrap parsing/error-context and process lifecycle portions of `backend_process.rs` **done 2026-05-18**)

### Wave 3 — Highest-risk extractions (one at a time, with full smoke proof)

12. `launchView.js` → `launchView.realmedia.js` (largest read-only cluster; **done 2026-05-18**)
13. `launchView.js` → `launchView.risk.js`, `launchView.scope.js`, `launchView.preflight.js` (`launchView.scope.js` **done 2026-05-18**; `launchView.risk.js` **done 2026-05-18**; `launchView.preflight.js` **done 2026-05-18**)
14. `pendingPublishView.js` → `pendingPublishView.recovery.js`, `pendingPublishView.drain.js`, `pendingPublishView.confidence.js`, `pendingPublishView.diagnostics.js` (`pendingPublishView.recovery.js` **done 2026-05-18**; `pendingPublishView.diagnostics.js` **done 2026-05-18**; `pendingPublishView.confidence.js` **done 2026-05-18**; `pendingPublishView.drain.js` **done 2026-05-18**)

### Wave 4 — Markup and styles (after JS proves the include pattern)

15. `index.html` split via `<script type="text/template">` partials or a backend include layer (`partials/app-shell-start.html` + `partials/app-shell-end.html` shell include starter split **done 2026-05-19**; `partials/page-home.html` Home page panel split **done 2026-05-19**; `partials/page-telemetry.html` Telemetry page panel split **done 2026-05-19**; `partials/page-queue.html` Queue page panel split **done 2026-05-19**; `partials/page-completed.html` Completed/Output page panel split **done 2026-05-19**; `partials/page-pending.html` Pending Publish page panel split **done 2026-05-19**; `partials/page-rename.html` Rename page panel split **done 2026-05-19**; `partials/page-launch.html` Launch page panel split **done 2026-05-19**; `partials/page-reports.html` Reports page panel split **done 2026-05-19**; `partials/page-schedule.html` Schedule page panel split **done 2026-05-19**; `partials/page-maintenance.html` Maintenance page panel split **done 2026-05-19**; `partials/page-network.html` Workers page panel split **done 2026-05-19**; `partials/page-diagnostics.html` Diagnostics page panel split **done 2026-05-19**; `partials/page-settings.html` Settings page panel split **done 2026-05-19**).
16. `styles.css` → `styles.tokens.css`, `styles.theme.css`, `styles.layout.css`, `styles.components.css`, `styles.pages.css`/`pages/*.css`, `styles.controls.css`, `styles.layout-manager.css`, `styles.queue.css` (`styles.tokens.css` **done 2026-05-19**; `styles.theme.css` **done 2026-05-19**; `styles.layout.css` **done 2026-05-19**; `styles.components.css` **done 2026-05-19**; `styles.pages.css` starter split **done 2026-05-19**; `styles.controls.css` **done 2026-05-19**; `styles.layout-manager.css` **done 2026-05-19**; `styles.queue.css` **done 2026-05-19**).

**Execution note — 2026-05-19:** `styles.tokens.css` is done for the first Wave 4 CSS chunk. The root design tokens, dark-mode defaults, and `body.light-mode` variable overrides moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.tokens.css`; `styles.css` now imports that file first and continues to own light-mode component overrides, layout rules, component rules, and page-specific styling. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** `styles.theme.css` is done for the light-mode component override layer. The contiguous light-mode override rules moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.theme.css`; `styles.css` now imports tokens first and theme second before the remaining base/layout/component/page rules. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** `styles.layout.css` is done for the base element and application-shell layout layer. Global box sizing, body/form/button base rules, scrollbars, sidebar/nav/topbar layout, status pills, and page visibility moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.layout.css`; `styles.css` now imports tokens, theme, and layout before the remaining component/page rules. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** `styles.components.css` is done for the first shared component layer. Metric, progress, panel, text-block, form, option-panel, summary-grid, action-row, workflow-table, schedule-block, empty-state, and page-panel empty-window rules moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.components.css`; `styles.css` now imports tokens, theme, layout, and components before the remaining page/feature rules. During recovery from a bad intermediate mechanical rewrite, the remaining page/feature rules were restored from the latest PG3 handoff stylesheet and the later status-chip/per-file override drawer additions were re-applied. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** `styles.pages.css` is started for the first page-specific layer. Home page component rules and Settings tab navigation moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.pages.css`; `styles.css` now imports tokens, theme, layout, components, and pages before the remaining command/control and queue feature rules. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** `styles.controls.css` is done for the first command/control utility layer. Tertiary and primary buttons, advanced/evidence toggles, numeric/path cells, route/status chips, pipeline sparkline, launch evidence collapse, keyboard shortcut help, collapsible summary toggles, settings impact chips, and semantic row backgrounds moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.controls.css`; `styles.css` now imports tokens, theme, layout, components, pages, and controls before the remaining layout-manager customization and queue feature rules. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** `styles.layout-manager.css` is done for the S50 panel customization layer. Panel advanced/hidden display rules, customize-layout active/reset states, injected panel customize bar rules, drag/drop states, reset-warning styling, and light-mode customize bar adjustments moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.layout-manager.css`; `styles.css` now imports tokens, theme, layout, components, pages, controls, and layout-manager before the remaining queue feature rules. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** `styles.queue.css` is done for the S60/S70/S80 queue feature layer. Queue priority badges/menus/toolbars, queue ordering strategy controls, and per-file override drawer rules moved out of `styles.css` into `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/styles.queue.css`; `styles.css` now imports tokens, theme, layout, components, pages, controls, layout-manager, and queue before the remaining global reduced-motion and responsive tail rules. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** the first `index.html` backend include layer is done for the stable application shell. The sidebar/topbar/opening workspace wrapper moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/app-shell-start.html`, the closing workspace wrapper moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/app-shell-end.html`, and `index.html` now carries `<!-- mp-include: ... -->` markers that the Local API render path expands before bootstrap injection. DOM/navigation inventory tests now parse the rendered template, and the release self-test verifies include references are safe and present. No DOM IDs, JS globals, API routes, media policy, command behavior, or mutation controls changed.

**Execution note — 2026-05-19:** the second `index.html` backend include chunk is done for the Telemetry page panel. The read-only Telemetry markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-telemetry.html`, and `index.html` now carries an include marker for `data-page-panel="live"` while keeping the JS script registry in the parent file. Rendered-template tests verify the app shell plus Telemetry IDs are expanded before bootstrap injection. No DOM IDs, JS globals, API routes, media policy, command behavior, script order, or mutation controls changed.

**Execution note — 2026-05-19:** the third `index.html` backend include chunk is done for the Schedule page panel. The Schedule metrics, evidence panels, editor controls, and weekly view markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-schedule.html`, and `index.html` now carries an include marker for `data-page-panel="schedule"` while keeping Schedule JS and route contracts unchanged. Rendered-template tests verify Schedule editor/table IDs are expanded before bootstrap injection. No DOM IDs, JS globals, API routes, app-state write semantics, command behavior, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the fourth `index.html` backend include chunk is done for the Maintenance page panel. The Maintenance health, release dry-run, backfill dry-run, and history markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-maintenance.html`, and `index.html` now carries an include marker for `data-page-panel="maintenance"` while keeping Maintenance JS and backend dry-run routes unchanged. The Workers read-only boundary test now parses rendered HTML so page partials cannot hide lifecycle-control regressions. No DOM IDs, JS globals, API routes, release/backfill dry-run semantics, command behavior, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the fifth `index.html` backend include chunk is done for the Workers page panel. The Workers/Network role metrics, diagnostics-open buttons, worker state table, network config evidence, lifecycle handoff, evidence checklist, state files, and API contract markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-network.html`. `index.html` now carries an include marker for `data-page-panel="network"` while keeping Network JS, `/api/network/workers`, diagnostics-open ownership, and read-only lifecycle boundaries unchanged. Rendered-template tests verify worker filter/table/lifecycle IDs expand before bootstrap injection. No DOM IDs, JS globals, API routes, lifecycle controls, command behavior, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the sixth `index.html` backend include chunk is done for the Reports page panel. The Reports metrics, audit progress, failure preview, audit preview, report path/root evidence, and recent-open history markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-reports.html`. `index.html` now carries an include marker for `data-page-panel="reports"` while keeping `reportsView.js`, diagnostics-open ownership, report navigation handoff, route contracts, and read-only report evidence boundaries unchanged. Rendered-template tests verify Reports failure/audit/open-history IDs expand before bootstrap injection. No DOM IDs, JS globals, API routes, command behavior, report-open semantics, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the seventh `index.html` backend include chunk is done for the Rename page panel. The Rename pipeline handoff, bulk edit controls, preview table, plan form, apply-readiness review, outcome review, and command-history evidence markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-rename.html`. `index.html` now carries an include marker for `data-page-panel="rename"` while keeping `renameView.js`, `/api/rename/preview`, `/api/rename/apply`, backend transactional rename ownership, selection/apply readiness semantics, and script order unchanged. Rendered-template tests verify Rename table/apply-readiness/outcome IDs expand before bootstrap injection. No DOM IDs, JS globals, API routes, command behavior, rename/apply semantics, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the eighth `index.html` backend include chunk is done for the Launch page panel. The Launch readiness, settings-risk handoff, policy boundary, launch scope, real-media proof, sample checklist, pilot readiness, backend preflight, pipeline/audit/rerun start controls, pipeline control, and command-history markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-launch.html`. `index.html` now carries an include marker for `data-page-panel="launch"` while keeping `launchView*.js`, `/api/launch/preflight`, `/api/pipeline/start`, `/api/pipeline/control`, `/api/audit/start`, `/api/rerun/start`, backend-owned launch policy, command preconditions, and script order unchanged. Rendered-template tests verify Launch preflight/start-decision/command-review IDs expand before bootstrap injection, and the real-media WebView smoke still sees Launch proof/readiness IDs through the served page. No DOM IDs, JS globals, API routes, command behavior, launch/control/audit/rerun semantics, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the ninth `index.html` backend include chunk is done for the Completed/Output page panel. The Completed metrics, review/size boards, completed table, selected-output open handoff, evidence/proof/history tabs, publish reconciliation, route agreement, diagnostics links, and output-acceptance markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-completed.html`. `index.html` now carries an include marker for `data-page-panel="completed"` while keeping `completedView*.js`, `/api/completed`, `/api/publish-reconciliation`, `/api/completed/open`, backend-selected open targets, output proof policy, and script order unchanged. Rendered-template tests verify Completed table/proof/acceptance IDs expand before bootstrap injection, and browser smoke coverage still exercises Completed proof/detail surfaces through the served page. No DOM IDs, JS globals, API routes, command behavior, output/publish policy, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the tenth `index.html` backend include chunk is done for the Queue page panel. The Queue filters, source-scan progress, readiness/history/checklist panels, backend launch scope preview, launch decision checklist, review/exclusion tables, priority and ordering controls, queue table, selected-row diagnostics/open handoff, and per-file override drawer markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-queue.html`. `index.html` now carries an include marker for `data-page-panel="queue"` while keeping `queueView.js`, queue priority/strategy/file override/open routes, backend-authored queue/launch scope decisions, source-open allowlists, and script order unchanged. Rendered-template tests verify Queue table/scope/checklist IDs expand before bootstrap injection, and browser smoke coverage still exercises Queue table, launch-readiness, row-detail, and diagnostics-handoff surfaces through the served page. No DOM IDs, JS globals, API routes, command behavior, queue planning policy, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the eleventh `index.html` backend include chunk is done for the Pending Publish page panel. The Pending metrics, drain recommendations, recovery/diagnostics/confidence evidence, guarded publish/drain controls, drain history/events/summary, post-drain trust checks, pending table, selected-row diagnostics, and backend-selected open handoff markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-pending.html`. `index.html` now carries an include marker for `data-page-panel="pending"` while keeping `pendingPublishView*.js`, `/api/pending-publish`, `/api/pending-publish/open`, `/api/pending-publish/recovery-plan`, guarded drain launch behavior, backend-authored drain safety, source/open allowlists, and script order unchanged. Rendered-template tests verify Pending table/drain/decision/post-drain IDs expand before bootstrap injection, and browser smoke coverage still exercises drain guard, large table, row detail, diagnostics handoff, and Completed/Pending proof surfaces through the served page. No DOM IDs, JS globals, API routes, command behavior, drain/publish policy, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the twelfth `index.html` backend include chunk is done for the Diagnostics page panel. The Diagnostics tabs, triage/progress/state evidence, structured log access, command drilldown and failure-resolution evidence, backend close-readiness/shutdown surface, diagnostics-open allowlist controls, owner handoff, and API contract review markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-diagnostics.html`. `index.html` now carries an include marker for `data-page-panel="diagnostics"` while keeping `diagnosticsView*.js`, `diagnosticsBridge.js`, backend lifecycle/shutdown routes, diagnostics open/tail target-key allowlists, API contract reads, and script order unchanged. Rendered-template tests verify Diagnostics triage/log/command/lifecycle/contract IDs expand before bootstrap injection, and browser smoke coverage still exercises diagnostics handoff, lifecycle, command evidence, and Home live-state surfaces through the served page. No DOM IDs, JS globals, API routes, command behavior, diagnostics/open/tail policy, script order, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** the thirteenth `index.html` backend include chunk is done for the Settings page panel. The Settings tabs, current config/config health/policy readiness, settings editor, patch preview/save controls, command history, media/system builders, raw key triage, and advanced diagnostics markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-settings.html`. `index.html` now carries an include marker for `data-page-panel="settings"` while keeping `settingsView*.js`, settings builder child load order, settings preview/save routes, backend validation, command history, and script order unchanged. Rendered-template tests verify Settings validation/patch/save/audio-builder/network-builder/raw-triage IDs expand before bootstrap injection, and browser smoke coverage still exercises Settings-to-Launch handoff, Launch/Queue readiness, sample-validation handoff, real-media evidence, and Home live-state surfaces through the served page. No DOM IDs, JS globals, API routes, command behavior, settings preview/save policy, script order, or media/source-file mutation behavior changed. Home remains the only raw page panel in `index.html`.

**Execution note — 2026-05-19:** the fourteenth and final `index.html` backend include chunk is done for the Home page panel. The Daily Driver checklist, operator readiness, active work, command results, cross-page context, sample-validation evidence, generated worksheet, acceptance gate, record review, preview/append controls, and sample-validation history markup moved into `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-home.html`. `index.html` now carries an include marker for `data-page-panel="home"` while keeping `crossPageContextView*.js`, sample-validation routes, command-history reads, preview/append command ownership, and script order unchanged. Rendered-template tests verify Daily Driver, active-work, and sample-validation IDs expand before bootstrap injection, and browser smoke coverage still exercises Home live-state, sample-validation, command evidence, and real-media surfaces through the served page. No DOM IDs, JS globals, API routes, command behavior, sample-validation append policy, script order, or media/source-file mutation behavior changed. All 13 WebView page panels now load through backend static partials.

### Wave 5 — Test files

17. Split `test_application_facade.py`, `test_network_persistence.py`, `test_controllers.py` along their natural sub-suite boundaries — but only after the production modules they test have stabilised. (`test_application_facade_core_contracts.py`, `test_application_facade_close_readiness.py`, `test_application_facade_diagnostics.py`, `test_application_facade_settings_patch.py`, `test_application_facade_settings_workspace.py`, `test_application_facade_network.py`, `test_application_facade_process_control.py`, `test_application_facade_process_launch.py`, `test_application_facade_local_api.py`, `test_application_facade_web_static.py`, `test_application_facade_rename.py`, `test_application_facade_snapshot.py`, `test_application_facade_queue.py`, `test_application_facade_pending_publish.py`, `test_application_facade_completed.py`, `test_application_facade_reports.py`, `test_application_facade_maintenance.py`, and `test_application_facade_schedule.py` extracted from `test_application_facade.py`; `test_network_security.py`, `test_network_workflow.py`, `test_network_worker_runtime.py`, `test_network_coordinator_helpers.py`, `test_network_coordinator_http.py`, `test_network_protocol_runtime.py`, `test_network_firewall.py`, `test_network_worker_state.py`, `test_network_inflight_registry.py`, `test_network_crash_recovery.py`, `test_network_done_release.py`, and final `test_network_coordinator_startup.py` rename extracted from `test_network_persistence.py`; `test_controllers_status_server.py`, `test_controllers_app_state.py`, `test_controllers_work_guard.py`, `test_controllers_rerun.py`, `test_controllers_pending_publish.py`, `test_controllers_release.py`, `test_controllers_folder_policy.py`, `test_controllers_maintenance.py`, `test_controllers_file_actions.py`, `test_controllers_settings.py`, `test_controllers_completed.py`, `test_controllers_failure.py`, `test_controllers_audit.py`, `test_controllers_worker_board.py`, `test_controllers_feedback.py`, `test_controllers_diagnostics.py`, `test_controllers_home.py`, `test_controllers_status_presentation.py`, `test_controllers_telemetry.py`, `test_controllers_notification.py`, and `test_controllers_pipeline.py` extracted from `test_controllers.py` **done 2026-05-19**)

**Execution note — 2026-05-19:** Wave 5 is started with the lowest-risk network test split. `NetworkSecurityTests` moved from `DesktopApp/tests/test_network_persistence.py` into `DesktopApp/tests/test_network_security.py`, covering auth-token validation, rotated-token persistence failures, registry foreign-worker rejection, recent-completion grace, capped worker HTTP reads, coordinator URL validation, coordinator request body caps/read failures, worker ID/name validation, hostname fallback, and log-entry sanitization. The original network persistence module now continues with worker/coordinator lifecycle and workflow tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network workflow split. `WorkflowEnhancementTests` moved from `DesktopApp/tests/test_network_persistence.py` into `DesktopApp/tests/test_network_workflow.py`, covering local claim/release save-failure resilience, heartbeat and done/release HTTP outcomes, queue-removal scheduling, coordinator reaper/shutdown/startup hardening, claim/done/release edge cases, cluster-log formatting, retry-hint calculation, and worker wait policy. The original network persistence module now keeps the broader worker/coordinator lifecycle and persistence suite. No production code, WebView assets, API routes, command behavior, network runtime behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network worker-runtime split. The first worker runtime/resilience block moved from `DesktopApp/tests/test_network_persistence.py` into `DesktopApp/tests/test_network_worker_runtime.py`, covering diagnostic preview bounds, daemon-thread start failures, worker source-path mapping, worker status callback failures, cluster-log posting failures, poll-loop claim/release behavior, heartbeat start/post/snapshot failures, malformed claim responses, reclaimed heartbeat aborts, and worker claim handoff diagnostics. The original network persistence module now keeps protocol/registry sanitization, coordinator helpers, worker-state persistence, crash recovery, done/release reporting, and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network coordinator-helper split. `test_network_coordinator_helpers.py` now owns coordinator URL/share-block formatting, coordinator and worker auth probes, coordinator HTTP helper parsing/body validation, coordinator policy coercion and retry hints, heartbeat/reaper fallback logging, encode-config snapshot overrides, coordinator encode-config snapshot delegation, and prior-failure policy coverage. The original network persistence module now keeps protocol/registry sanitization, HTTP JSON/coordinator handler behavior, worker-state persistence, crash recovery, done/release reporting, firewall helpers, and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network coordinator-HTTP split. `test_network_coordinator_http.py` now owns bounded authenticated HTTP JSON GET/POST helpers, non-finite payload rejection, invalid/non-strict JSON response handling, coordinator `_send_json` and OPTIONS failure handling, invalid coordinator request-body and identifier rejection, heartbeat/done registry failure responses, reclaimed heartbeat cluster-log failure handling, `/api/log` missing/sanitized field handling, worker timestamp preservation warnings, cluster-log append failures, and bounded HTTP error previews. The original network persistence module now keeps protocol/registry sanitization, worker-state persistence, crash recovery, done/release reporting, firewall helpers, and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network protocol/runtime split. `test_network_protocol_runtime.py` now owns heartbeat and done-request non-finite validation, in-flight registry runtime snapshot sanitization, reclaimed heartbeat abort scheduling, worker claim-record construction and invalid-claim diagnostics, path remap handoff behavior, worker completion/release/crash done-request builders, and worker poll interval/retry-hint policy. The original network persistence module now keeps firewall helpers, worker-state persistence, in-flight registry persistence, crash recovery, done/release reporting, and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network firewall split. `test_network_firewall.py` now owns firewall rule parsing, add-rule command construction, bounded `netsh` subprocess checks, nonzero check warnings, admin-failure messaging, and `netsh` output surfacing. The original network persistence module now keeps worker-state persistence, in-flight registry persistence, crash recovery, done/release reporting, and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, firewall behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network worker-state split. `test_network_worker_state.py` now owns worker-state atomic write replacement, job identity and pending done-report round trips, worker-state and pending-done save-failure operator visibility, non-finite worker-state JSON rejection, temporary-file cleanup diagnostics, guarded worker-state clear failure visibility, and accepted-report cleanup context. The original network persistence module now keeps in-flight registry persistence, crash recovery, done/release reporting, and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, worker-state behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network in-flight registry split. `test_network_inflight_registry.py` now owns concurrent registry saves, registry temporary-file cleanup diagnostics, coordinator state-transition diagnostics on registry save failure, non-finite estimated-size sanitization, non-finite network config JSON rejection, and malformed registry-row load handling. The original network persistence module now keeps crash recovery, done/release reporting, and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, in-flight registry behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network crash-recovery split. `test_network_crash_recovery.py` now owns crash recovery done-post retry/fallback behavior, pending done-report recovery, bounded failure diagnostics, malformed/unreadable worker-state cleanup, cluster-log failure handling, and accepted-report cleanup failure handling. The original network persistence module now keeps done/release reporting and coordinator startup tests. No production code, WebView assets, API routes, command behavior, network runtime behavior, crash-recovery behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the network done/release split. `test_network_done_release.py` now owns worker done/release reporting, accepted-report cleanup behavior, pending done-report save failures, bounded done/release diagnostics, unstartable-claim release reporting, and `DoneRequest` completion/publish/queue-terminal field preservation. The original network persistence module now keeps only coordinator startup behavior and its imports were trimmed to that ownership. No production code, WebView assets, API routes, command behavior, network runtime behavior, done/release behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 completed the network persistence split by renaming the final coordinator startup block from `test_network_persistence.py` to `test_network_coordinator_startup.py` and updating the class name to `NetworkCoordinatorStartupTests`. No test assertions changed. No production code, WebView assets, API routes, command behavior, network runtime behavior, coordinator startup behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller status-server split. `test_controllers_status_server.py` now owns status-server redaction, shutdown-failure logging, pause-flag read-failure logging, and non-finite telemetry JSON-safety coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, controller behavior, process lifecycle behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller app-state split. `test_controllers_app_state.py` now owns persisted view state, widget failure logging, refresh-state snapshot/autoload, poll completed-manifest refresh, and apply-snapshot-to-UI coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, controller behavior, app-state persistence behavior, process lifecycle behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller work-guard split. `test_controllers_work_guard.py` now owns active external progress and related-process close/start blocking coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, controller behavior, process lifecycle behavior, close-readiness behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller rerun split. `test_controllers_rerun.py` now owns rerun CSV preview coverage for disabled rows, unsafe policy overrides, and duplicate output hints. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, rerun controller behavior, CSV handling behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller pending-publish split. `test_controllers_pending_publish.py` now owns pending-publish dashboard summary and tree/detail rendering coverage. `test_controllers.py` keeps the broader Tk controller boundary suite and its shared fake tree fixture for remaining report/navigation tests. No production code, WebView assets, API routes, command behavior, pending-publish controller behavior, publish/drain behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller release split. `test_controllers_release.py` now owns release package result formatting, manifest/zip path storage, success status/action reporting, and timeout reporting coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, release controller behavior, release package behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller folder-policy split. `test_controllers_folder_policy.py` now owns folder-policy validation result status, action recording, success info dialog, and error/warning dialog detail coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, folder-policy controller behavior, folder-policy validation behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller maintenance split. `test_controllers_maintenance.py` now owns progress-file skeleton reset coverage, resolved progress-path updates, reset action/status recording, confirmation dialogs, environment-health background dispatch, and environment-health result formatting. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, maintenance controller behavior, progress-file behavior, environment-check behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller file-actions split. `test_controllers_file_actions.py` now owns resolved log/local-base/report/config open handoffs, latest failure/audit CSV lookups, loaded audit CSV handoff, and empty path warning coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, file-actions controller behavior, open-path behavior, diagnostics/report open behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller settings split. `test_controllers_settings.py` now owns settings profile save/load, list/path helper behavior, dirty-state and structured-control toggles, structured-control failure logging, unsaved-start prompt handling, config form validation/preview, missing saved-config diff logging, and save-in-place reload behavior. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, settings controller behavior, config persistence behavior, launch/start policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller completed split. `test_controllers_completed.py` now owns completed-tree sorting/tags/detail rendering, CPU fallback encoder display, route breakdown chart updates, encode-speed history read/write/migration behavior, and backfill result handling. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, completed controller behavior, completed manifest behavior, analytics history behavior, backfill behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller failure split. `test_controllers_failure.py` now owns failure report filtering/detail/trend rendering, clear-filter behavior, JSON/marker/clear-result application, selected-source open/copy/priority/audit-match actions, context menu behavior, and selected-failure re-run prioritization coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, failure controller behavior, audit matching behavior, rerun/priority behavior, diagnostics/report open behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller audit split. `test_controllers_audit.py` now owns audit report filtering/detail rendering, duplicate index behavior, multi-selection summaries, quick-view filters, context menu behavior, CSV apply/report metadata handling, creation-time failure logging, selected-row copy/open/priority actions, and selected/filtered CSV export coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, audit controller behavior, CSV handling behavior, priority marker behavior, diagnostics/report open behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller worker-board split. `test_controllers_worker_board.py` now owns live worker-board snapshot rendering, stale-row cleanup logging, snapshot failure fail-closed behavior, missing-worker-id logging, and per-row render failure isolation coverage. `test_controllers.py` keeps the broader Tk controller boundary suite plus WorkerController completion/report/abort coverage for a later split. No production code, WebView assets, API routes, command behavior, worker-board behavior, worker completion behavior, network dispatcher behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller feedback split. `test_controllers_feedback.py` now owns action-status toast display, previous-toast cancellation, auto-dismiss scheduling, toast dismissal, recent-action recording, and recent-action text propagation coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, feedback controller behavior, notification behavior, diagnostics behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller diagnostics split. `test_controllers_diagnostics.py` now owns diagnostics log-search reset failure logging and current-match reset failure logging coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, diagnostics controller behavior, log-tail/open behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller Home split. `test_controllers_home.py` now owns Home dashboard idle-state rendering, pending-publish summary/timing, pending payload stat failure logging, and live queue overview/selection coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, Home controller behavior, pending-publish behavior, queue behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller status-presentation split. `test_controllers_status_presentation.py` now owns topbar chip/window title/taskbar/command-bar updates, audit current-file formatting, and taskbar progress failure logging coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, status presentation behavior, taskbar behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller telemetry split. `test_controllers_telemetry.py` now owns telemetry dashboard non-finite CPU/GPU/RAM display sanitization and ffmpeg GPU-note coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, telemetry controller behavior, telemetry collection behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller notification split. `test_controllers_notification.py` now owns background completion/failure notifications, test toast delivery, Windows notification failure logging, and focus-check failure logging coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, notification controller behavior, Windows notification behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller pipeline split. `test_controllers_pipeline.py` now owns pause/stop/rescan flag command-surface coverage and sleep-second parsing coverage. `test_controllers.py` keeps the broader Tk controller boundary suite. No production code, WebView assets, API routes, command behavior, pipeline controller behavior, process lifecycle behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller process-lifecycle split. `test_controllers_process_lifecycle.py` now owns completed pipeline/audit handle synchronization, shutdown cleanup failure logging, pipeline/audit launch prep, schedule-window launch state, and kill-and-quit cleanup coverage. `test_controllers.py` keeps the broader Tk controller boundary suite plus queue, navigation, network, and worker completion/report/abort coverage for later splits. No production code, WebView assets, API routes, command behavior, process lifecycle behavior, launch/kill behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller worker-jobs split. `test_controllers_worker_jobs.py` now owns worker completion event matching, fail-closed completion reports, malformed event skipping, dispatcher completion reporting, single-file launch failure handling, start UI failure handling, and worker abort/reclaim kill coverage. `test_controllers.py` keeps queue, navigation, and network controller boundary coverage for later splits. No production code, WebView assets, API routes, command behavior, worker dispatch behavior, process lifecycle behavior, launch/kill behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller network split. `test_controllers_network.py` now owns coordinator status notice rendering, coordinator notice failure logging, coordinator button update failure logging, dispatcher error/shutdown failure logging, and worker status post failure logging. `test_controllers.py` keeps queue and navigation controller boundary coverage for later splits. No production code, WebView assets, API routes, command behavior, NetworkController behavior, coordinator/worker dispatcher behavior, network runtime behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with the controller navigation split. `test_controllers_navigation.py` now owns view routing/refresh/sidebar behavior, Network tab lifecycle failure logging, sidebar badge rendering, shortcut overlay guards, global shortcut bindings, filter trace/sort-heading/detail-copy wiring, and detail-copy failure logging. `test_controllers.py` now keeps only queue controller boundary coverage. No production code, WebView assets, API routes, command behavior, NavigationController behavior, route/view behavior, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 started the `test_application_facade.py` split with the core-contract slice. `test_application_facade_core_contracts.py` now owns command-result serialization, runtime outcome normalization, bounded command-journal persistence, strict JSON/non-finite rejection, Local API HTTP helper guards, static bootstrap/asset helper behavior, and documented route-map coverage. `test_application_facade.py` keeps facade workflow, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, backend policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the close-readiness slice. `test_application_facade_close_readiness.py` now owns active/unknown runtime state blocking, fresh progress blocking, pipeline/audit progress verification failures, ActiveJobs blocking and failure logging, schedule-stop watcher blocking, and related-process inspection failure coverage. `test_application_facade.py` keeps diagnostics, settings, queue, pending/completed, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, close-readiness behavior, backend policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the diagnostics slice. `test_application_facade_diagnostics.py` now owns diagnostics open allowlist coverage, diagnostics tail allowlist coverage, read-only diagnostics state-summary artifact coverage, blocked BDPGS OCR path surfacing, and diagnostics path lookup failure logging. `test_application_facade.py` keeps settings, queue, pending/completed, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, diagnostics behavior, backend policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the settings patch slice. `test_application_facade_settings_patch.py` now owns Settings Preview Patch/Save Patch behavior, redacted diff fallback logging, risk summaries for high-risk, pending-publish, audio, and subtitle settings, save confirmation/backup/secret preservation, backend save-lock guarding, and no-op same-value handling. `test_application_facade.py` keeps telemetry, rename, queue, pending/completed, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, settings behavior, config persistence behavior, backend policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the rename slice. `test_application_facade_rename.py` now owns rename preview behavior, selected-only apply confirmation, multiple selected-source apply handling, undo-manifest cleanup in temp fixtures, and backend apply-lock guarding. `test_application_facade.py` keeps telemetry, queue, pending/completed, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, rename behavior, backend policy, or real media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the snapshot/progress/telemetry slice. `test_application_facade_snapshot.py` now owns facade snapshot assembly without a Tk root, progress bar shaping for pipeline publish/audit/subtitle work, pending-publish copy byte progress, and zero-percent GPU telemetry presence. `test_application_facade.py` keeps queue, pending/completed, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, snapshot/telemetry behavior, backend policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the queue slice. `test_application_facade_queue.py` now owns queue preview snapshot-read behavior, stale snapshot evidence, visible blocked rows versus exclusions, exact source-path runtime outcome correlation, and backend row-key queue open allowlists. `test_application_facade.py` keeps pending/completed, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, queue behavior, backend policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the pending-publish slice. `test_application_facade_pending_publish.py` now owns pending-publish preview classification, durable drain-summary evidence, publish reconciliation correlation, read-only reconciliation endpoint behavior, backend row-key open allowlists, orphan row-key support, scan-failure surfacing, and backend-authored recovery dry-run planning. `test_application_facade.py` keeps completed, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, pending-publish behavior, drain/publish policy, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the completed/output slice. `test_application_facade_completed.py` now owns completed preview manifest loading, stale manifest and inventory progress evidence, size-growth and missing-output review classification, exact source-path runtime outcome correlation, backend row-key completed-open allowlists, and completed-manifest backfill dry-run behavior. `test_application_facade.py` keeps failure/audit, maintenance/release, schedule/settings workspace, network worker state, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, completed/output behavior, backfill behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the Reports slice. `test_application_facade_reports.py` now owns read-only failure JSON/marker preview behavior and audit CSV preview behavior. `test_application_facade.py` keeps maintenance/release, schedule/settings workspace, network worker state, process launch, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, failure/audit behavior, rerun/audit launch behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the maintenance/release slice. `test_application_facade_maintenance.py` now owns maintenance workspace environment-health rows and release dry-run plan/count/progress behavior. A later large process-launch chunk also moved the maintenance dry-run command-lock test into this module. No production code, WebView assets, API routes, command behavior, maintenance/release behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the Schedule workspace/app-state slice. `test_application_facade_schedule.py` now owns Schedule workspace rendering, backend schedule-stop watcher evidence, Schedule preview behavior, Schedule save confirmation, app-state preservation, and invalid-time rejection without writes. `test_application_facade.py` keeps settings workspace, network worker state, process launch, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, schedule app-state behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the Settings workspace slice. `test_application_facade_settings_workspace.py` now owns Settings workspace redaction, path/field metadata, validation warning surfacing, backend media-policy readiness evidence, tool-path evidence, and Settings Validate command-result envelope coverage. `test_application_facade.py` keeps network worker state, process launch, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, settings/config write behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the Network worker-state slice. `test_application_facade_network.py` now owns read-only `/api/network/workers` facade behavior for persisted coordinator in-flight state, worker-state metadata, progress bars, state-file evidence, and lifecycle-control absence. `test_application_facade.py` keeps process launch/control, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, network lifecycle behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued the `test_application_facade.py` split with the process-control slice. `test_application_facade_process_control.py` now owns pipeline control pause/rescan flag contract coverage, invalid control-action rejection, and process-control lock fail-closed coverage. `test_application_facade.py` keeps process launch, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and WebView static integration coverage. No production code, WebView assets, API routes, command behavior, process lifecycle behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with a larger `test_application_facade.py` split chunk. `test_application_facade_process_launch.py` now owns pipeline/audit/rerun launch facade coverage, schedule-gated continuous launch behavior, backend launch-lock fail-closed behavior, schedule-stop watcher preservation, and read-only launch preflight guard coverage. The remaining maintenance command-lock test moved into `test_application_facade_maintenance.py`. `test_application_facade.py` keeps Local API server behavior and backend-served WebView static integration coverage. No production code, WebView assets, API routes, command behavior, process lifecycle behavior, maintenance behavior, backend media policy, or media/source-file behavior changed.

**Execution note — 2026-05-19:** Wave 5 continued with a final large `test_application_facade.py` split chunk. `test_application_facade_local_api.py` now owns the Local API server route/auth/shutdown/command-history workflow tests, and `test_application_facade_web_static.py` now owns backend-served WebView/static asset, Tauri route-reference, panel-boundary, selection-helper, and headless bootstrap coverage. `test_application_facade.py` is now a shared fixture module for the focused application-facade tests and owns no direct tests. No production code, WebView assets, API routes, command behavior, Local API behavior, backend media policy, or media/source-file behavior changed.

### Wave 6 — Post-split JS view files

18. Split `queueView.js`, `crossPageContextView.sampleValidation.js`, `settingsView.raw.js`, and other post-split WebView assets that still exceed the line/function threshold. Keep parent namespaces and flat exports stable; child modules use the established stash-global factory pattern and parent deletion after consumption.

**Execution note — 2026-05-19:** Wave 6 started with a large read-only `queueView.js` split. `queueView.summary.js`, `queueView.review.js`, and `queueView.launch.js` now own Queue progress/readiness/workflow summaries, review/exclusion evidence, selected-row at-a-glance evidence, backend launch-scope preview, and launch-decision checklist helpers. The parent still owns module-scope queue state, row rendering/selection, event wiring, queue-open, priority, strategy, and file-override mutation paths. No API routes, backend queue planning, launch/drain policy, media policy, command behavior, source/open allowlists, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** Wave 6 completed the narrowed Queue detail split. `queueView.detail.js` now owns read-only selected-row review/checklist/detail text, diagnostics-link rendering, excluded-row detail, route reasoning text, and queue-open history rendering. `queueView.js` consumes/deletes the child stash before creating `queueView.launch.js` because launch-decision helpers depend on selected-row issue/detail helpers. Queue open, Diagnostics open/tail dispatch, priority, strategy, file-overrides, state variables, selection, row rendering, event wiring, and all POST routes remain in `queueView.js`. No API routes, backend queue planning, launch/drain policy, media policy, command behavior, source/open allowlists, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** Wave 6 continued with the nested `crossPageContextView.sampleValidation.js` split. `crossPageContextView.sampleValidation.worksheet.js`, `crossPageContextView.sampleValidation.runbook.js`, and `crossPageContextView.sampleValidation.records.js` now own the read-only worksheet/policy/sample-set, runbook/cutover/pilot, and completed-record/acceptance evidence helper clusters. `crossPageContextView.sampleValidation.js` now keeps the preview/append backend command routes, request/result handling, record panel orchestration, child stash consumption/deletion, and the final `window.__crossPageSampleValidationModule` export for `crossPageContextView.js`. No API routes, backend sample-validation policy, queue/launch/publish behavior, DOM IDs, or media/source-file mutation behavior changed.

**Execution note — 2026-05-19:** Wave 6 continued with the read-only `settingsView.js` split. `settingsView.rawTriage.js` now owns settings-row filtering, raw-key triage, and raw action-plan evidence; `settingsView.safetyLocks.js` now owns saved safety-lock review evidence. `settingsView.js` keeps Settings state, builder orchestration, event wiring, Preview/Save/Reload/Validate command routes, command busy guards, child stash consumption/deletion, and the canonical namespace/flat exports. No API routes, backend settings validation, PSD1 persistence behavior, media policy, DOM IDs, or media/source-file mutation behavior changed.

---

## 4.5. Module organization & cross-reference policy

The biggest risk in splitting god files is creating **file sprawl** — dozens of small files where you can't find anything and where call-sites end up importing from arbitrary nested paths. This section is the **binding rule set** for every split chunk. Follow these and the post-split codebase is easier to navigate than the pre-split one, not harder.

### 4.5.1. The one-registry rule

Every language already has (or will have) **exactly one place** that lists every module and dictates load order. Splits add entries to that one registry — never invent a second discovery mechanism.

| Language | Registry | Behaviour |
|---|---|---|
| **PS1** | `MediaPipeline_chatgpt.ps1` line 321 — the `foreach ($module in @(...))` array | New modules append to the array in dependency order. Dot-sourced into the same script scope, so cross-references are by function name only. |
| **Python** | `application/<package>/__init__.py` re-exports for split god files; existing flat imports for unrelated modules | Callers continue to import from the original path; the `__init__.py` is the seam. |
| **JS** | `index.html` `<script src="...">` tags | New scripts inserted **immediately above** their parent god-file's `<script>` tag so the parent IIFE can read the stash global at load time. |
| **Rust** | `lib.rs` `mod` declarations + `pub use` re-exports | Sub-modules declared in `lib.rs`; types they share live in a `types.rs` re-exported at crate root. |

If a module isn't in the registry, **it doesn't exist** and the loader can't reach it. The inventory files (`WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` etc.) document the registry — they are not a parallel discovery mechanism.

### 4.5.2. Directory layout per language

**Hard rule:** a sub-folder is only created when **3 or more related files** would otherwise share a prefix. Two siblings stay flat.

#### Python — sub-packages for split god files only

```
application/
├── facade_sample_validation_policy.py       ← becomes a 30-line re-export shim
├── sample_validation/                       ← NEW sub-package (6+ siblings → folder)
│   ├── __init__.py                          ← re-exports the public surface
│   ├── _shared.py                           ← tiny helpers used by 3+ siblings
│   ├── evidence.py
│   ├── pilot_plan.py
│   ├── policy_alignment.py
│   ├── readiness.py
│   ├── reconciliation.py
│   └── worksheet.py
├── facade_completed_policy.py               ← stays flat (not being split)
├── service_file_overrides.py                ← stays flat
└── service_queue_strategy.py                ← stays flat
```

**Import contract:** `from application.facade_sample_validation_policy import X` continues to work because the shim re-exports. **Nothing outside `application/sample_validation/` imports from `application/sample_validation/evidence` directly.** The package is opaque from the outside.

#### JS — flat with dotted names (NOT sub-folders)

This codebase has **no JS bundler and no JS sub-folders** in `ui_web/static/assets/` today. Introducing sub-folders means every `<script src="...">` tag, every `test_webview_*` scan path, and every dev-tools breakpoint path changes. That's a lot of churn for a refactor that's supposed to be invisible.

**Decision: keep `assets/` flat. Use dotted names for split children.**

```
ui_web/static/assets/
├── completedView.js                         ← parent (thinned)
├── completedView.evidence.js                ← split child
├── completedView.proof.js
├── completedView.review.js
├── completedView.diagnostics.js
├── settingsView.js                          ← parent (thinned)
├── settingsView.builders.audio.js
├── settingsView.builders.video.js
├── settingsView.builders.subtitle.js
├── settingsView.builders.queue.js
├── settingsView.builders.runtime.js
├── settingsView.builders.file_safety.js
├── settingsView.builders.pending.js
├── settingsView.builders.network.js
├── launchView.js                            ← parent (thinned)
├── launchView.risk.js
├── launchView.scope.js
├── launchView.realmedia.js
├── launchView.preflight.js
└── ...
```

**Why dotted not sub-folder:**

1. Alphabetical sort groups siblings naturally (all `completedView.*.js` files cluster).
2. `<script src="assets/completedView.evidence.js">` keeps a single path component — no nested paths.
3. The existing inventory scanner (`test_webview_inventory_docs.py`) walks `assets/*.js` — no glob change.
4. Dev-tools "Sources" panel shows the cluster grouped by prefix automatically.
5. The naming reads as "`completedView`, the `evidence` slice" — the parent owner is unmistakable.

**Cross-reference contract for JS splits:**

Split children **never** export onto `window.mediaPipeline*View` directly. They expose a temporary stash global which the parent IIFE consumes:

```js
// In completedView.evidence.js — runs BEFORE completedView.js loads
(function () {
  function completedAcceptanceRows(...) { /* ... */ }
  function completedRouteAgreementRows(...) { /* ... */ }
  // ... ~30 functions

  // Stash for the parent to pick up. The parent deletes this after consuming.
  window.__completedViewEvidenceModule = {
    completedAcceptanceRows,
    completedRouteAgreementRows,
    // ...
  };
})();
```

Then `completedView.js` reads the stash, re-exports onto the canonical namespace, and **deletes the stash**:

```js
// In completedView.js, near the bottom
const __evidence = window.__completedViewEvidenceModule || {};
delete window.__completedViewEvidenceModule;

// ...assemble namespace as before, adding the stashed functions:
window.mediaPipelineCompletedView = {
  renderCompleted,
  // ... existing exports ...
  ...__evidence,                          // adds completedAcceptanceRows etc.
};

// Flat re-exports (existing pattern)
Object.assign(window, __evidence);
```

After load, the only globals are the canonical namespace + flat exports — **identical to pre-split**. The stash is invisible to the rest of the codebase.

#### PS1 — no change, already correct

`Pipeline/Modules/*.ps1` is the established pattern. New split modules drop into that folder and get appended to the dot-source array in `MediaPipeline_chatgpt.ps1`. Functions are dot-sourced into the same script scope — call them by name, no qualifier.

#### Rust — flat in `src/` for now, sub-folder if any module grows to 3+ children

```
src-tauri/src/
├── lib.rs                                   ← run(), tauri::Builder wiring, mod declarations
├── backend_process.rs                       ← Sibling module
├── backend_contract.rs
├── close_readiness.rs
├── debug_webview.rs
├── dialogs.rs
├── http_helpers.rs
└── types.rs                                 ← shared structs (BackendBootstrap, ShellResult, etc.)
```

**Visibility rule:** all moved functions become `pub(crate)`. Anything callable from `lib.rs::run()` is `pub(crate) fn`. Anything internal to a module stays `fn`. The shared types (`ShellResult`, `BackendBootstrap`, `BackendRoute`, `CloseReadiness`, `ContinuousWatcher`) live in `types.rs` and are re-exported in `lib.rs`:

```rust
// lib.rs
mod backend_process;
mod backend_contract;
mod close_readiness;
mod debug_webview;
mod dialogs;
mod http_helpers;
mod types;

pub(crate) use types::{BackendBootstrap, BackendRoute, CloseReadiness, ContinuousWatcher, ShellResult};
```

Callers inside the crate write `use crate::types::X;` or just `use crate::X;` thanks to the re-export. Outside the crate sees only what `pub fn run()` exposes.

### 4.5.3. The "no chase" rule

A call-site should never have to know which sub-module owns a function. Specifically:

- **Python:** `from application.facade_sample_validation_policy import X` — call-sites stay; the implementation may live in `application/sample_validation/evidence.py` but that's an implementation detail.
- **JS:** `window.mediaPipelineCompletedView.completedAcceptanceRows(...)` or the flat re-export `window.completedAcceptanceRows(...)`. Call-sites never reference the split child file name.
- **PS1:** `Get-FileOverrideAudioSettings` — same as today, dot-sourced functions are unqualified.
- **Rust:** `crate::X` if re-exported, else `crate::module::X`. Call-sites prefer the crate-root re-export.

**If you have to add a new import path in a call-site to use a function that already worked, you've broken the no-chase rule.** The split is wrong; rework the re-export layer until call-sites are untouched.

### 4.5.4. The "shared utilities" rule

Splits sometimes reveal helpers used by 3+ sibling modules. Those go in a dedicated shared module **inside the same package**, never bubbled up to the codebase root:

- Python: `application/sample_validation/_shared.py` (underscore prefix marks "package-internal").
- JS: a `_helpers` stash global consumed only by siblings of the same parent, or simply duplicated if trivial. **Do not create `assets/sharedHelpers.js` for one parent's children.** `domHelpers.js` is the project-wide DOM utility module — anything reaching for that is fine; anything narrower belongs to its parent.
- PS1: a new `Pipeline/Modules/<Domain>Helpers.ps1` only if shared by 3+ existing `Modules/*.ps1` files.
- Rust: `crate::types` for shared structs; private helpers stay in the module that needs them.

### 4.5.5. Inventory updates are part of the split

Every split chunk's PR-equivalent must show, in the same diff:

1. The new module file(s).
2. The thinned parent file.
3. **The registry update** — load-order array, `<script>` tag insertion, `__init__.py` re-export, or `mod` declaration.
4. The inventory file update (`WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`, `MODULE_INVENTORY.md` if we add one, etc.).
5. The `DOC_TOUCH_LOG.md` row and the `REMEDIATION_CHANGELOG.md` H2 entry.

A split chunk that updates the registry without the inventory, or vice versa, is rejected at review. They are inseparable.

### 4.5.6. Quick lookup: "where does X live?"

After every split chunk, a developer should be able to answer "where does function `X` live?" in **at most two lookups**:

1. **Grep the inventory file** (`WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` or equivalent) for the function name. The inventory says which parent module owns it.
2. **Grep the parent file's directory** (`assets/completedView.*.js`, `application/sample_validation/*.py`, `Pipeline/Modules/*.ps1`) for the function definition. The dotted prefix or sub-package narrows it to one or two candidates.

If the answer to "where does X live?" takes more than two lookups, the split was done wrong and must be undone or restructured before further splits in that area.

---

## 5. Per-chunk delivery checklist

For **every** split chunk:

- [ ] New module file(s) created under the correct path; old file thinned.
- [ ] No call-site changes outside the affected file unless the namespace shape required it.
- [ ] `WEBVIEW_DOM_ID_INVENTORY.md` updated if any new `id=` was introduced (splits should be zero-new-IDs).
- [ ] `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` updated for `window.*` re-export pattern. Counts must match scan.
- [ ] `API_ROUTE_INVENTORY.md` confirmed unchanged (splits should be zero-new-routes).
- [ ] `TEST_COVERAGE_MATRIX.md` updated if test files were renamed or split alongside.
- [ ] `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` confirmed unchanged.
- [ ] `DOC_TOUCH_LOG.md` row appended.
- [ ] `REMEDIATION_CHANGELOG.md` H2 entry appended.
- [ ] Full test suite passes locally (`pytest -x`, browser-smoke, PS1 dot-source smoke).
- [ ] Git diff reviewable: ideally `git diff --stat` shows additions in one new file and equal-sized deletions in the parent.

---

## 6. Anti-patterns and red lines

### Things that have failed in past splits — do not repeat

1. **Splitting a mutation cluster on a "looks isolated" basis.** Mutation flows usually share more state than they appear to (busy/lock state, command-history correlation, settings-workspace snapshots). Always split read-only first.
2. **Renaming functions during a split.** A split chunk that also renames is two changes. Land the move first; rename in a follow-up if needed.
3. **Adding new behaviour while "we're touching the file anyway."** This is how splits introduce regressions. New behaviour is always a separate chunk.
4. **Splitting JS into ES modules.** This codebase has no bundler; every module is a global-side-effect IIFE. Sub-modules must follow the same pattern (load order via `<script>` tags, communicate via `window.*` and `typeof === "function"` guards). Do **not** introduce `import`/`export`.
5. **Skipping the inventory update.** Every split that adds or relocates a `window.*` export must update `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` **in the same chunk**. The drift test (`test_webview_inventory_docs.py`) will catch it, but the goal is to never trigger that test.
6. **Splitting `Do-Remux` or `Do-Encode` "while we're in there".** These are the highest-trust functions in the pipeline. Leave them until there is a dedicated remux/encode test harness.

---

## 7. Secondary candidates (deferred)

| File | Lines | Why deferred |
|---|---:|---|
| `index.html` | 5,061 | Wave 4 started — backend include layer added and stable app shell plus Telemetry, Queue, Completed/Output, Pending Publish, Rename, Launch, Reports, Schedule, Workers, Maintenance, and Diagnostics page panels extracted to `partials/*.html`; Home and Settings page bodies remain in parent |
| `styles.css` | 2,595 | Wave 4 CSS split substantially complete — `styles.tokens.css`, `styles.theme.css`, `styles.layout.css`, `styles.components.css`, starter `styles.pages.css`, `styles.controls.css`, `styles.layout-manager.css`, and `styles.queue.css` extracted; parent keeps imports plus global reduced-motion/responsive tail rules |
| `network_tab.py` | — | Only split if actively under change |
| `coordinator.py` | — | Same |
| `worker.py` | — | Same |
| `test_application_facade.py` | — | Wave 5 split complete for direct test cases — `test_application_facade_core_contracts.py`, `test_application_facade_close_readiness.py`, `test_application_facade_diagnostics.py`, `test_application_facade_settings_patch.py`, `test_application_facade_settings_workspace.py`, `test_application_facade_network.py`, `test_application_facade_process_control.py`, `test_application_facade_process_launch.py`, `test_application_facade_local_api.py`, `test_application_facade_web_static.py`, `test_application_facade_rename.py`, `test_application_facade_snapshot.py`, `test_application_facade_queue.py`, `test_application_facade_pending_publish.py`, `test_application_facade_completed.py`, `test_application_facade_reports.py`, `test_application_facade_maintenance.py`, and `test_application_facade_schedule.py` extracted; parent is now a shared fixture module for focused application-facade tests |
| `test_network_coordinator_startup.py` | — | Split/rename complete; only revisit if coordinator startup coverage grows |
| `test_controllers.py` | — | Wave 5 active — status-server, app-state, work-guard, rerun, pending-publish, release, folder-policy, maintenance, file-actions, settings, completed, failure, audit, worker-board, feedback, diagnostics, Home, status-presentation, telemetry, notification, pipeline, process-lifecycle, worker-jobs, network, navigation, and queue tests extracted; parent now keeps only controller helper import-boundary coverage |

---

## Wave 6 — JS view files that crossed the threshold post-split (complete)

These files were not in the original Wave 1–3 table but exceed the 2,000-line / 80-function threshold as measured on 2026-05-19. Full split plans and exact function-cluster assignments are in `Docs/proposals/GOD_FILE_SPLIT_WAVE6_PLAN.md`.

| File | Lines | Functions | Children planned | Priority |
|---|---:|---:|---|---|
| `queueView.js` | 3,194 | 152 | `queueView.summary.js`, `queueView.launch.js`, `queueView.review.js`, `queueView.detail.js` | 1 — done |
| `crossPageContextView.sampleValidation.js` | 2,673 | 128 | `…sampleValidation.worksheet.js`, `…sampleValidation.runbook.js`, `…sampleValidation.records.js` | 2 — done |
| `settingsView.js` | 3,873 | 203 | `settingsView.rawTriage.js`, `settingsView.safetyLocks.js` (core coupling prevents further splits) | 3 — done |
| `diagnosticsView.js` | 2,325 | 110 | `diagnosticsView.activejobs.js`, `diagnosticsView.log.js`, `diagnosticsView.investigation.js` | 4 — clean functional boundaries |

Wave 6 is complete for the documented JS split scope. Future Queue feature work should keep command-adjacent priority, strategy, file-overrides, queue-open, and diagnostics dispatch behavior parent/backend-owned unless a separate safety review proves a narrower boundary.

---

## 8. Definition of done for the whole effort

The god-file split is complete when:

- No file in `application/`, `ui_web/static/assets/`, `Pipeline/Modules/`, or `src-tauri/src/` exceeds **2,000 lines**.
- No file has more than **80 function definitions** without a documented architectural reason.
- `MediaPipeline_chatgpt.ps1` is under 2,000 lines, with `Do-Remux`, `Do-Encode`, and `Process-File` remaining as the orchestration layer (these are allowed to stay large as the explicit "fat orchestrator" pattern).
- Each module file's top doc comment names a single responsibility.
- All inventory files (`WEBVIEW_*_INVENTORY.md`, `API_ROUTE_INVENTORY.md`) reflect post-split reality.
- All existing tests pass; no new tests were skipped to enable a split.
- `REMEDIATION_CHANGELOG.md` and `DOC_TOUCH_LOG.md` carry one entry per split chunk delivered.
