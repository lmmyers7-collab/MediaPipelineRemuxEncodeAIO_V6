# Claude Review Targets: Recent WebView Evidence Hardening

Date: 2026-05-15  
Project: `MediaPipelineRemuxEncodeAIO_V5`  
Purpose: Give Claude a focused review checklist for recent WebView/Tauri parity work that is most likely to fail, drift, or need hardening.

## Ground Rules For Claude

- Work only in `MediaPipelineRemuxEncodeAIO_V5`.
- Do not touch V4.
- Do not remove, freeze, weaken, or bypass the Tk fallback.
- Do not add frontend-owned filesystem mutation.
- Do not add frontend-only business logic for media, rename, settings, drain, publish, queue, or sample-validation append.
- Treat Network mode as read-only.
- Treat all media policy, FFmpeg, subtitle, audio, queue, pending-publish, rename, and settings mutation paths as backend-owned.
- Prefer review findings first. Only propose patches for clearly safe frontend/test/doc hardening.
- If proposing code changes, keep them small, testable, and limited to the files listed in the target section.

## Highest-Risk Review Targets

### 1. Sample Validation Guide-To-Category Handoff

Files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/crossPageContextView.js`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`
- `DesktopApp/tests/test_webview_browser_sample_validation_smoke.py`
- `DesktopApp/tests/test_sample_validation_api.py`
- `DesktopApp/tauri_shell/src-tauri/src/lib.rs`

Why this is likely to fail:

- It stores selected guide-row state in frontend module globals.
- Row selection and category application are intentionally separate actions; accidental auto-apply would be bad.
- Re-rendering can reset selected row state if the backend payload changes.
- The local Pilot Category selector feeds backend preview/append requests, so stale or mismatched UI state could record the wrong category.

What to check:

- Selecting a Real-Media Sample Set Guide row does not change the Pilot Category selector until `Use Selected Category` is clicked.
- `Use Selected Category` uses `category_key`, not display text.
- Re-rendering sample-validation panels preserves or safely resets selected guide-row state.
- Unknown/missing category keys do not silently write misleading values.
- Browser smoke verifies exactly one preview POST and no append/mutation routes.

Suggested hardening if needed:

- Add a visible result message when no selected guide row exists.
- Add a static/browser assertion for row click without category change.
- Add a browser assertion that selecting a different guide row then clicking the button changes the category to that row's key.

## 2. Sample Validation Records Table Current/Gap Columns

Files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/crossPageContextView.js`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`
- `DesktopApp/tests/test_sample_validation_api.py`

Why this is likely to fail:

- The records table now merges persisted records with reconciliation rows by `record_id`.
- Missing reconciliation rows produce local fallback labels.
- Stale/review/current wording must not imply backend acceptance.
- Column count changed from 4 to 7; empty-state/table tests may miss layout regressions.

What to check:

- Records with no reconciliation row show `not checked`, not `current`.
- Stale accepted records render warning posture.
- Current records render match posture.
- Missing-proof count is accurate when `missing_current_evidence` is present.
- Empty-state `colspan` matches the visible columns.

Suggested hardening if needed:

- Add a unit/static test fixture for current, stale, and no-reconciliation records.
- Add a browser smoke assertion that a stale record shows `stale` and `N missing` in the table, not only in detail.

## 3. Pending Publish Sample Validation Handoff

Files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/pendingPublishView.js`
- `DesktopApp/tests/test_application_facade.py`
- `DesktopApp/tests/test_tauri_shell_scaffold.py`
- `DesktopApp/tests/test_webview_row_detail_smoke.py`
- `DesktopApp/tests/test_webview_browser_completed_pending_proof_smoke.py`

Why this is likely to fail:

- The handoff is display-only but references the controlled `deferred-publish` category used by Sample Validation.
- It uses pending row flags such as `ready_to_drain`, `drain_recommendation`, `diagnostic_status`, `diagnostic_severity`, and `local_exists`.
- A ready-looking pending row could be misworded as accepted proof before durable drain evidence exists.
- A blocked row could accidentally appear as acceptable if string matching misses a backend status.

What to check:

- `do_not_drain`, missing payload, invalid/unreadable manifest, orphan payload, and diagnostic error rows all recommend hold/review.
- Ready-looking rows still require Completed output proof and durable drain summary agreement before accepted evidence.
- The text never implies Home Sample Validation can drain, publish, mark complete, accept output, or mutate media.
- Browser smoke checks a representative row and a blocked/adversarial row.

Suggested hardening if needed:

- Add direct tests for `pendingSampleValidationHandoffLines()` with ready, blocked, missing-payload, invalid-manifest, and orphan-payload fixtures.
- Include `sample_category=deferred-publish` guidance in one browser smoke path only as display guidance, not a POST.

## 4. Completed Real-Media Output Proof Ladder And Sample Validation Handoff

Files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js`
- `DesktopApp/tests/test_webview_row_detail_smoke.py`
- `DesktopApp/tests/test_webview_browser_completed_pending_proof_smoke.py`

Why this is likely to fail:

- It joins Completed output proof, sidecar proof, route/size/media decisions, Pending Publish proof, diagnostics/runtime proof, and Sample Validation guidance.
- It relies on selected Completed row state plus pending proof rows.
- Same-leaf matches can be confused with exact path matches.
- Size-policy wording can drift back toward hardcoded +5% interpretation.

What to check:

- Missing output with no pending proof is blocked.
- Same-leaf matches are always labeled duplicate-title hints only.
- Output/sidecar proof does not imply Plex playback success or operator acceptance.
- Sample Validation handoff remains evidence-only.
- Route/size/media proof distinguishes backend size policy from legacy +5% warning.

Suggested hardening if needed:

- Add one fixture where output growth is within policy and verify the proof ladder says review/within-policy, not blocked.
- Add one fixture where sidecar is missing but output exists and verify it does not become ready proof.

## 5. Completed-To-Pending And Pending-To-Completed Correlation

Files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/pendingPublishView.js`
- `DesktopApp/tests/test_webview_browser_completed_pending_proof_smoke.py`

Why this is likely to fail:

- There are two inverse correlation paths:
  - Completed proof board checks Completed output/source against Pending Publish and drain summary.
  - Pending selected-row detail checks Pending destination/source against loaded Completed rows.
- Path normalization is duplicated in frontend JS.
- UNC, slash direction, same filename in different folders, and missing path fields are common failure cases.

What to check:

- Exact normalized full-path matches are treated stronger than same-leaf matches.
- Same-leaf matches never become proof.
- Empty Pending Publish is not treated as proof of publish success.
- Pending row correlation works when Completed rows are not loaded.
- UNC paths and mixed slash paths normalize consistently.

Suggested hardening if needed:

- Add frontend helper tests or smoke fixture cases for UNC paths and mixed slash paths.
- Consider centralizing path-normalization helpers only if duplication begins causing test failures; do not refactor broadly just for style.

## 6. Tauri Startup Asset Gate Coverage

Files:

- `DesktopApp/tauri_shell/src-tauri/src/lib.rs`
- `DesktopApp/tests/test_tauri_shell_scaffold.py`
- `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat`

Why this is likely to fail:

- The Rust asset gate is intentionally string-fragment based.
- New WebView controls/functions can be missed by the gate.
- Overly strict fragments could make startup brittle after harmless wording changes.

What to check:

- Critical DOM IDs and exported functions for new handoffs are covered.
- Gate failures do not leak backend token values.
- Gate wording is not so exact that minor text edits break startup.
- `-CheckOnly` still imports backend module and does not imply WebView/media proof.

Suggested hardening if needed:

- Gate stable IDs/function names, not long prose.
- Keep prose checks in Python/browser tests rather than Rust startup unless truly startup-critical.

## 7. Browser Smoke No-Mutation Boundaries

Files:

- `DesktopApp/tests/test_webview_browser_sample_validation_smoke.py`
- `DesktopApp/tests/test_webview_browser_completed_pending_proof_smoke.py`
- `DesktopApp/tests/test_webview_row_detail_smoke.py`
- `Docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`

Why this is likely to fail:

- Browser smokes mock or intercept POST routes differently.
- A newly added button or event handler could accidentally post a mutation route.
- Some smokes are browser-backed, others are Node/DOM simulation; they do not cover identical runtime surfaces.

What to check:

- Sample Validation smoke allows preview only, never append.
- Completed/Pending proof smoke does not call drain/publish/start/rename/settings-save.
- Row-detail smoke remains non-mutating.
- No tests accidentally rely on frontend state mutation that would hide real backend route calls.

Suggested hardening if needed:

- Add a shared forbidden-route list helper for browser smokes if duplication grows.
- Add explicit assertions for `/api/pending-publish/drain`, `/api/pipeline/start`, `/api/sample-validation/append`, `/api/rename/apply`, and `/api/settings/save-patch`.

## 8. Documentation Drift Around Evidence Versus Authority

Files:

- `Docs/CURRENT_PROJECT_STATE.md`
- `Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- `Docs/TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs/REMEDIATION_CHANGELOG.md`

Why this is likely to fail:

- Recent UI wording is intentionally nuanced: evidence, proof, readiness, accepted record, current record, and production cutover are different concepts.
- Docs can accidentally imply WebView is daily-driver ready.
- The changelog is large and easy to update inconsistently.

What to check:

- Docs still say Tk is fallback and WebView is not daily-driver approved.
- Sample Validation evidence is not described as output acceptance.
- Pending Publish handoff is not described as a drain/publish action.
- Real-media validation remains the major blocker.
- Changelog latest-entry table and full-entry index both include the new item.

Suggested hardening if needed:

- Update `Docs/DOCS_INDEX.md` only if this review target should become long-lived.
- Keep the current source-of-truth docs concise; avoid duplicating every changelog detail.

## 9. Selected-Row State And Re-Render Safety

Files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/crossPageContextView.js`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/pendingPublishView.js`

Why this is likely to fail:

- WebView pages keep selected row keys in module globals.
- Refreshes and re-renders can replace tables while detail panes still refer to old rows.
- Recently added handoffs depend on selected rows being coherent with current payloads.

What to check:

- When a selected row disappears after refresh/filtering, detail text clearly says it is hidden or not loaded.
- Sample Set Guide selected category does not become stale after payload shape changes.
- Completed/Pending proof panels recompute when pending/completed payloads refresh.
- No selected-row detail triggers backend mutation.

Suggested hardening if needed:

- Add a smoke case where the selected row disappears after re-render and verify guidance stays safe.
- Prefer resetting selected keys when row-key no longer exists rather than preserving stale detail as proof.

## 10. Path And Unicode Edge Cases In Frontend Proof Text

Files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/pendingPublishView.js`
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/crossPageContextView.js`

Why this is likely to fail:

- Proof correlation uses string path normalization in frontend JS.
- Real media paths may be UNC paths, long paths, mixed slash paths, case variants, Unicode, punctuation-heavy names, or duplicate filenames.
- Frontend should display evidence but not become the final authority.

What to check:

- UNC paths with `\\server\share` display without being mangled.
- Mixed `/` and `\` paths normalize enough for evidence matching.
- Same filename in different folders remains review-only.
- Unicode names do not break table rendering or detail text.

Suggested hardening if needed:

- Add one browser or Node smoke fixture using a UNC-like path and a Unicode filename.
- Keep final path authority backend-owned; frontend matching should remain evidence and guidance only.

## Recommended Commands For Claude

Run targeted checks first:

```powershell
node --check DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js
node --check DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js
node --check DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js
python -m unittest DesktopApp.tests.test_sample_validation_api -q
python -m unittest DesktopApp.tests.test_webview_browser_sample_validation_smoke -q
python -m unittest DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke -q
python -m unittest DesktopApp.tests.test_webview_row_detail_smoke -q
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

If those pass and time allows:

```powershell
python -m unittest discover DesktopApp\tests -q
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat -CheckOnly
```

## Expected Claude Output

Claude should return:

- Findings grouped by severity.
- Exact file/function/line references.
- Whether each issue is a real bug, test gap, wording risk, or future hardening suggestion.
- Minimal patch suggestions only where safe.
- Any tests run and their results.

Claude should not:

- Rewrite media policy.
- Add drain/publish/start/rename/settings-save controls.
- Move mutation logic into WebView.
- Remove Tk fallback.
- Touch V4.
