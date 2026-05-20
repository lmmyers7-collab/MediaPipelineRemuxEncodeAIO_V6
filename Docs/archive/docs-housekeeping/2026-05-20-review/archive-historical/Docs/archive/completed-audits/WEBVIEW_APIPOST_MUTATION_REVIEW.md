# WebView apiPost Mutation Boundary Review

Date: 2026-05-14

Classifies every `apiPost` call found in the frontend JavaScript layer by mutation class and documents which guardrails apply. Source of truth: grep of all `*.js` files under `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/` for the literal string `apiPost`.

Total calls: 23 (22 unique route calls + 1 function definition). Total unique routes called: 22.

---

## Classification Legend

| Class | Risk | What it means |
|---|---|---|
| `none` | Safe | Preview or validation only; no state change |
| `shell-open` | Low | Opens a path in the OS shell; backend resolves path from its own state |
| `validation-log-write` | Low | Appends to the operator evidence log only; no manifest or media change |
| `control-flag-write` | Medium | Writes a control flag file the running pipeline reads |
| `config-write` | High | Writes the live config PSD1 or schedule; requires `confirm_save` |
| `filesystem-mutation` | Critical | Renames files on disk; requires `confirm_apply`; backend rebuilds plan |
| `process-launch` | High | Spawns a backend process; backend owns launch-lock |
| `backend-lifecycle` | Critical | Initiates graceful backend shutdown |

---

## All apiPost Calls

### Class: none — Preview / Validation (No State Change)

| JS File | ~Line | Route | Notes |
|---|---|---|---|
| `settingsView.js` | 3498 | `POST /api/settings/validate` | Validates staged config values; no config written |
| `settingsView.js` | 3573 | `POST /api/settings/preview-patch` | Returns redacted diff; no config written |
| `settingsView.js` | 3763 | `POST /api/settings/reload` | Reloads in-memory backend state; no config written |
| `scheduleView.js` | 432 | `POST /api/schedule/preview` | Preview schedule without writing |
| `renameView.js` | 1221 | `POST /api/rename/preview` | Rename predictions only; no files touched |
| `pendingPublishView.js` | 2843 | `POST /api/pending-publish/recovery-plan` | Dry-run recovery plan; no drain/repair/publish |
| `maintenanceView.js` | 539 | `POST /api/maintenance/release-dry-run` | Builder with `-DryRun`; no release zip written |
| `maintenanceView.js` | 598 | `POST /api/maintenance/completed-backfill-dry-run` | Dry-run backfill; no manifest written |
| `crossPageContextView.js` | 1398 | `POST /api/sample-validation/preview` | Preview warnings only; no log written |

### Class: shell-open — OS Shell Open (No Media Mutation)

| JS File | ~Line | Route | Frontend sends | Allowed targets |
|---|---|---|---|---|
| `queueView.js` | 1925 | `POST /api/queue/open` | `row_key` + `target` | `source_file`, `source_folder`, `source_root` |
| `pendingPublishView.js` | 2800 | `POST /api/pending-publish/open` | `row_key` + `target` | `local_file`, `manifest`, `destination_folder`, `source_folder` |
| `diagnosticsView.js` | 1410 | `POST /api/diagnostics/open` | `target` key only | 22-target allowlist (see `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`) |
| `completedView.js` | 3413 | `POST /api/completed/open` | `row_key` + `target` | `output_folder`, `sidecar`, `source_folder` |

The frontend never passes a raw filesystem path. It passes a `row_key` (identifying a backend state entry) and a `target` key (an allowlisted label). The backend resolves the actual path from its own state.

### Class: validation-log-write — Evidence Log Append (Low Risk)

| JS File | ~Line | Route | Notes |
|---|---|---|---|
| `crossPageContextView.js` | 1422 | `POST /api/sample-validation/append` | Appends to `sample_validation_log.jsonl` only; does not mark jobs accepted, clear failures, or touch media |

### Class: control-flag-write — Control Flag (Medium Risk)

| JS File | ~Line | Route | Allowed actions |
|---|---|---|---|
| `launchView.js` | 1794 | `POST /api/pipeline/control` | `action`: `pause`, `stop`, `rescan` only |

Writes a flag file the running pipeline reads. Does not kill processes directly.

### Class: config-write — Live Config Write (High Risk)

| JS File | ~Line | Route | Guardrail |
|---|---|---|---|
| `settingsView.js` | 3701 | `POST /api/settings/save-patch` | `confirm_save: true` required; backend backs up before writing |
| `scheduleView.js` | 469 | `POST /api/schedule/save` | `confirm_save: true` required |

Both require explicit `confirm_save` at the backend contract layer. The frontend cannot write config without this flag. The backend always creates a timestamped backup before writing.

### Class: filesystem-mutation — File Rename on Disk (Critical)

| JS File | ~Line | Route | Guardrails |
|---|---|---|---|
| `renameView.js` | 1053 | `POST /api/rename/apply` | `confirm_apply: true` required; backend rebuilds plan from state, not from frontend-submitted plan |

The frontend enforces Apply Readiness (blocks apply when blockers exist) and passes `confirm_apply = true` only after operator action. The backend independently rebuilds the rename plan from its own state — the frontend-computed table is not trusted for path resolution.

### Class: process-launch — Spawns Backend Process (High Risk)

| JS File | ~Line | Route | Mode / Notes |
|---|---|---|---|
| `launchView.js` | 1889 | `POST /api/pipeline/start` | `mode`: `once`, `continuous`, or `validate` |
| `launchView.js` | 1957 | `POST /api/pipeline/start` | `mode`: `drain_pending_pushes` |
| `launchView.js` | 2014 | `POST /api/audit/start` | Audit script invocation |
| `launchView.js` | 2082 | `POST /api/rerun/start` | Default safe: `stage_mode: copy`, `original_mode: keep`, `return_mode: park` |

All four gated by backend launch-lock. Command journaling records every call. The backend enforces duplicate-command protection independently of the frontend.

### Class: backend-lifecycle — Graceful Shutdown (Critical)

| JS File | ~Line | Route | Guardrail |
|---|---|---|---|
| `app.js` | 250 | `POST /api/backend/shutdown` | Shell must call `GET /api/backend/close-readiness` first; `reason` field required |

The shell must not decide to shut down unilaterally. Backend controls the shutdown sequence.

---

## Summary Table

| Class | Count | Routes |
|---|---|---|
| `none` (preview/validation) | 9 | settings/validate, settings/preview-patch, settings/reload, schedule/preview, rename/preview, pending-publish/recovery-plan, maintenance/release-dry-run, maintenance/completed-backfill-dry-run, sample-validation/preview |
| `shell-open` | 4 | queue/open, pending-publish/open, diagnostics/open, completed/open |
| `validation-log-write` | 1 | sample-validation/append |
| `control-flag-write` | 1 | pipeline/control |
| `config-write` | 2 | settings/save-patch, schedule/save |
| `filesystem-mutation` | 1 | rename/apply |
| `process-launch` | 4 | pipeline/start (×2 modes), audit/start, rerun/start |
| `backend-lifecycle` | 1 | backend/shutdown |
| **Total** | **23** | |

---

## Frontend Guardrails Before High-Risk Calls

| Route | Frontend guardrail | Backend guardrail |
|---|---|---|
| `rename/apply` | Apply Readiness ledger must show no blockers | `confirm_apply` required; backend rebuilds plan |
| `settings/save-patch` | Backend Preview Patch must succeed first; operator clicks Save | `confirm_save` required; backup written before overwrite |
| `schedule/save` | Preview must fire first | `confirm_save` required |
| `pipeline/start` | Launch Readiness must not show blockers | Launch-lock, command journal, duplicate-command guard |
| `audit/start` | Launch Readiness check | Backend owns launch-lock |
| `rerun/start` | Operator selects scope explicitly | Default safe-mode flags enforced |
| `backend/shutdown` | Close Readiness badge must be safe | Backend controls shutdown sequence |

Frontend guardrails are defense-in-depth. The backend independently enforces all contract constraints regardless of frontend state.

---

## What the Frontend Must Never Do

- Pass a raw filesystem path as a request parameter to any route
- Call `rename/apply` without `confirm_apply: true`
- Call `settings/save-patch` without `confirm_save: true`
- Call `pipeline/start` without a valid `mode` parameter
- Read arbitrary files from disk (only allowlisted diagnostics tail targets)
- Resolve paths from queue/completed/pending state itself
- Execute any subprocess or spawn any process directly

---

## Freshness Review — 2026-05-15 (CLN3-022)

Broad "read-only" claim audit across docs to confirm that no doc falsely describes a page or route as read-only when a backend mutation exists.

| Mutation class | Routes | "Read-only" claim accurate? |
|---|---|---|
| `config-write` | `schedule/save`, `settings/save-patch` | Pass — archive/admin-audits/SCHEDULE_STALE_READONLY_WORDING_AUDIT.md and archive/admin-audits/WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md both correctly say "backend app-state write" or "confirmed backend app-state write" for these routes |
| `filesystem-mutation` | `rename/apply` | Pass — all rename docs correctly say apply is backend-owned; rename smokes explicitly state "does not call rename.apply" |
| `validation-log-write` | `sample-validation/append` | Pass — SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md and V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md correctly classify append as a backend-owned log write, not a read-only route |
| `process-launch` | `pipeline/start`, `audit/start`, `rerun/start` | Pass — Launch page docs (COMMAND_OWNERSHIP_MATRIX.md, V5_TRANSITION_STATUS_BOARD.md) correctly say Launch triggers backend pipeline processes, not read-only |
| `backend-lifecycle` | `backend/shutdown` | Pass — archive/admin-audits/WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md correctly says shutdown is "posted through backend-owned route", not read-only |
| Network page | No `apiPost` calls | Pass — read-only claim is accurate; confirmed CLN3-026 |
| Pending Publish evidence panel | No direct drain route | Pass — read-only evidence panel claim is accurate; drain is backend-process-only (confirmed CLN3-023) |

No inaccurate read-only claims found in active documentation.

```
Task ID: CLN3-022
Files inspected: Docs\WEBVIEW_APIPOST_MUTATION_REVIEW.md, Docs\archive\admin-audits\SCHEDULE_STALE_READONLY_WORDING_AUDIT.md, Docs\archive\admin-audits\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md, Docs\archive\admin-audits\NETWORK_READONLY_WORDING_AUDIT.md, Docs\archive\admin-audits\PENDING_PUBLISH_DOCS_FRESHNESS_REVIEW.md
Files changed: Docs\WEBVIEW_APIPOST_MUTATION_REVIEW.md (CLN3-022 freshness note added)
Validation: Select-String -Path Docs\WEBVIEW_APIPOST_MUTATION_REVIEW.md -Pattern "read-only|config-write|filesystem-mutation|validation-log-write"
Findings: All read-only claims in active docs are accurate. No page is incorrectly called read-only when a backend mutation route exists.
Open questions: None.
Risk: Low — documentation only.
```

---

## See Also

- Route classification: `Docs/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Route detail: `Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- No-touch boundaries: `Docs/NO_TOUCH_BOUNDARY_REGISTER.md`
- Manual test script: `Docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`
