# V5 Migration Risk Register

Date: 2026-05-14

Administrative risk register for the V5 Tauri/WebView2 transition. Each risk entry includes severity, current mitigation, owner area, next action, and a "do not do" warning.

Key mitigation across all risks: V5 remains the external rollback workspace, and V6 must not be treated as daily-driver complete until package-mode and representative real-media validation are complete.

---

## Risk Classification

| Severity | Meaning |
|---|---|
| **Low** | Unlikely to cause operator harm; monitor |
| **Medium** | May cause operator confusion or data quality issues |
| **High** | May cause data loss, corrupted state, or blocked pipeline |
| **Critical** | Irreversible harm to media files or operator data |

---

## Runtime and Process Safety

### R-001: Mid-Encode Kill via WebView Close

**Severity**: High

**Description**: If the operator closes the WebView while the pipeline is actively encoding, a partial output may be left on disk. The Tauri shell mitigates this via close-readiness checks, but an unexpected crash bypasses the close flow.

**Current mitigation**: `GET /api/backend/close-readiness` returns unsafe when active processing is in progress. The Tauri shell only issues shutdown after confirmed safe. `Pipeline/Tests/Invoke-AdversarialForceKillEncodeChecks.ps1` now force-kills a real backend process tree during a generated-media CPU fallback encode, verifies the source hash is unchanged, verifies the byte-bearing `encode_temp_cpu_*.mkv` partial is not accepted as Outsource/local encoded/completed-manifest/pending-publish output, and confirms the source remains in a backend-authored queue plan.

**Owner area**: Tauri shell + backend close-readiness service + pipeline runtime safety tests.

**Next action**: Run the adversarial force-kill smoke after changes to encode execution, publish completion, completed-manifest writes, pending publish parking, process-tree termination, or restart/recovery behavior. Real-media validation and clean-machine PG-3 remain separate promotion gates.

**Do not do**: Do not weaken close-readiness checks to make closing faster. Do not bypass them in any new shell variant.

---

### R-002: Duplicate Pipeline Launch

**Severity**: High

**Description**: If the operator launches a second pipeline instance while one is running, both processes may write to the same output paths, producing partial files or manifest corruption.

**Current mitigation**: Launch-lock and active-process guards prevent a second start if one is already running. Unit coverage includes process-guard policy and a 2026-05-19 facade test that starts one pipeline, reports its child PID as still running from the same bundle, and confirms the second start is rejected before the launcher is called again.

**Owner area**: Process launch service + facade guard policy.

**Next action**: Optional hardening: add a Local API command-history variant that posts the second start through `/api/pipeline/start` and confirms the rejection is journaled for operator review.

**Do not do**: Do not add a "force launch" button in the WebView that bypasses the launch-lock guard.

---

### R-003: Pipeline Version Mismatch (v4.000 vs V5 label)

**Severity**: Medium

**Description**: the PowerShell versioning helper historically returned `'v4.000'` while the UI displayed `V5`. `GET /api/snapshot` reported `v4.000`, which could confuse operators about which version was running. The active implementation now lives at `engine/shared/versioning.ps1`; `Pipeline/Modules/Versioning.ps1` is only a compatibility shim.

**Current mitigation**: Documented in `Docs/archive/admin-audits/STALE_VERSION_LABEL_AUDIT.md`. The mismatch is cosmetic — no pipeline behavior is affected.

**Owner area**: Pipeline PS layer (`Versioning.ps1`).

**Next action**: Bump `Versioning.ps1` to `'v5.000'` and update `Pipeline/Audit-MediaLibrary.ps1` and `DesktopApp/tests/test_contracts.py` in the same change.

**Do not do**: Do not update `MinPipelineVersion` config values — that is a per-operator sidecar freshness gate, not a display label.

---

## WebView Parity Risks

### R-004: Operator Mistakes WebView for Production Shell

**Severity**: Medium

**Description**: As parity improves, operators may use the WebView/Tauri preview as a daily driver before it has been validated for real-media routing, subtitle conversion, and audio policy.

**Current mitigation**: TLDR.md, Tauri Preview bat, and all operator-facing docs clearly state the Tauri/WebView2 shell is still validation-gated. V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md documents the required validation before trust.

**Owner area**: Documentation + operator communication.

**Next action**: Before any public release of the Tauri shell as non-preview, complete the real-media validation playbook.

**Do not do**: Do not remove the "preview" label from any Tauri/WebView2 launcher or doc until real-media validation is complete.

---

### R-005: WebView Mutation Guard Bypass

**Severity**: High

**Description**: A frontend regression could allow the WebView to submit a command route (rename apply, settings save, drain) before the operator has confirmed the readiness checklist. The backend would still validate, but the operator would lose the pre-check context.

**Current mitigation**: Apply Readiness, Publish Button Guard, Save-Readiness checklist, and `confirm_apply` / `confirm_save` backend requirements all prevent premature submission. Browser smokes verify the guards.

**Owner area**: WebView JS + backend command contracts.

**Next action**: Run browser smokes after any WebView JS change that touches confirmation or button-enable logic.

**Do not do**: Do not remove or weaken `confirm_apply` or `confirm_save` requirements to make the UI flow faster.

---

### R-006: Schedule Editing Contract Regression

**Severity**: Medium

**Description**: WebView now has backend-owned schedule preview/save and backend-owned schedule-stop watcher support for WebView-started continuous runs. The remaining risk is regression: future edits could bypass backend parsing, write raw app-state JSON, imply the Schedule page itself can launch/arm watchers, or miss watcher shutdown/crash edge cases.

**Current mitigation**: Schedule preview/save routes are declared in the Local API contract, use backend schedule parsing/validation, require `confirm_save` for app-state writes, preserve unrelated app-state keys, and write only `schedule_enabled`/`schedule_grid` through the app-state service. Launch backend preflight emits a `continuous_schedule_stop_watcher` row with timing evidence and labels `Ignore Schedule` continuous starts as high-review bypasses. Backend start arms the watcher only after the process launches and only when schedule enforcement is enabled, `Ignore Schedule` is not selected, and a current stop boundary exists. `/api/schedule` and `/api/backend/close-readiness` now expose the backend watcher's read-only current state so Schedule, Launch, Diagnostics, and Backend Lifecycle can show whether it is idle, armed, completed, canceled, stop-requested, unavailable, or failed. Close-readiness treats armed watcher state as active work so the shell does not report safe close while shutdown would cancel the future stop-at-boundary guard. Warning `backend.shutdown` command results preserve the close reason and watcher state for command-history diagnosis. The local API server cancels the watcher on shutdown.

**Owner area**: Schedule service + backend command contract design.

**Next action**: Add longer browser/API validation for continuous watcher arming/cancel paths and document the limitation that killing the local API process before the deadline prevents a later stop request.

**Do not do**: Do not add frontend-owned schedule file writes, raw state JSON patches, unconfirmed schedule saves, frontend-owned watcher timers, or watcher behavior that bypasses backend start/stop contracts.

---

## Settings and Config Risks

### R-007: Personal Config in Release Package

**Severity**: High

**Description**: If a clean release package accidentally includes `Pipeline/MediaPipeline_config_chatgpt.psd1`, the recipient gets the operator's private UNC paths, source/output locations, and potentially auth tokens.

**Current mitigation**: Release self-test gate explicitly fails if the live config is found in the package. Default release builder strips it and includes the template instead.

**Owner area**: Release builder + self-test.

**Next action**: Always run `scripts\release\test.ps1` before sharing any release package. Use `-KeepPersonalConfig` only for private machine-to-machine mirrors.

**Do not do**: Do not remove the live-config-in-package check from the release self-test.

---

### R-008: Settings Save Without Backup

**Severity**: High

**Description**: A `POST /api/settings/save-patch` that fails mid-write (crash, disk full) could leave the config in a partially-written state.

**Current mitigation**: `save-patch` performs an automatic backup (`MediaPipeline_config_chatgpt.backup_*.psd1`) before writing, then does an atomic write. The backup can be restored manually if the write fails.

**Owner area**: Config save service (`service_config_save_runner.py`).

**Next action**: Test: simulate disk-full during save; verify backup exists and live config is unchanged.

**Do not do**: Do not skip the backup step to speed up save. Do not allow the frontend to write the PSD1 directly.

---

## Diagnostics and Operator Trust Risks

### R-009: Clean Diagnostics Misread as Real-Media Proof

**Severity**: Medium

**Description**: An operator may trust that clean Diagnostics evidence (no errors, no warnings) proves the pipeline routed and encoded media correctly.

**Current mitigation**: Diagnostics page, Maintenance dry-run, and real-media docs all explicitly state that clean Diagnostics is not FFmpeg route proof.

**Owner area**: Operator documentation + WebView copy.

**Next action**: Ensure any new Diagnostics panel language continues to include the "does not prove FFmpeg behavior" disclaimer.

**Do not do**: Do not add language that implies Diagnostics panel correctness means media output is correct.

---

### R-010: Stale Command Journal After Restart

**Severity**: Low

**Description**: The command journal is in-memory and resets on backend restart. An operator may read the command history and miss commands from a previous session.

**Current mitigation**: Documented in `Docs/archive/completed-audits/COMMAND_HISTORY_CONSISTENCY_AUDIT.md`. The journal is session context only, not a durable audit log.

**Owner area**: Command journal service.

**Next action**: If durable command history is needed, design a persistent command log as a separate backend artifact. The in-memory FIFO remains the current behavior.

**Do not do**: Do not add disk persistence to the command journal without designing the retention, rotation, and privacy model.

---

## Packaging and Release Risks

### R-011: Node_modules or Rust Target in Package

**Severity**: Medium

**Description**: If `node_modules/`, `src-tauri/gen/`, or `target/` are accidentally included in a release package, the package size balloons and may include platform-specific binaries.

**Current mitigation**: Release builder explicitly excludes these paths. Release self-test fails if they are found in the package.

**Owner area**: Release builder + self-test.

**Next action**: Run self-test after any release builder change.

**Do not do**: Do not add any Tauri build artifacts to the list of files the release builder includes.

---

## Tests and Smoke Risks

### R-012: Smoke Pass Misread as Real-Media Proof

**Severity**: Medium

**Description**: All WebView smokes use fixture data. A passing smoke does not prove FFmpeg routing, subtitle conversion, audio policy, or pending publish drain on real files.

**Current mitigation**: Every smoke wrapper, smoke result template, and smoke catalog entry includes explicit "does not prove real-media" language.

**Owner area**: Documentation + smoke output.

**Next action**: Maintain the "does not prove" sections in all smoke wrappers and the result template.

**Do not do**: Do not remove the "does not prove" disclaimers from smoke wrappers or catalog entries to make pass messages look cleaner.

---

### R-013: Browser Smoke Skip Misread as Pass

**Severity**: Low

**Description**: Browser smokes skip cleanly when Chrome/Edge is unavailable (exit 0). If an operator sees exit 0 and assumes the browser tests passed, they may trust coverage that was never exercised.

**Current mitigation**: Skip output explicitly says "skipped" not "passed". Smoke result template includes a skip-reason field.

**Owner area**: Smoke result logging process.

**Next action**: Record skips in the smoke result log and re-run on a machine with Chrome/Edge before final acceptance.

**Do not do**: Do not treat a skip as a pass when evaluating whether browser-backed behavior is validated.

---

## Over-Fragmentation Risks

### R-014: Module Micro-Splitting Beyond Justified Complexity

**Severity**: Medium

**Description**: Historically, the service layer had ~95 flat package-root service files, 30 facade mixins, and 7 single-line command payload files. Further micro-splitting reduced maintainability and made debugging harder.

**Current mitigation**: `Docs/archive/completed-audits/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md` documents the current fragmentation and advises against further splitting during V5 stabilization.

**Owner area**: Desktop app Python package structure.

**Next action**: Do not add new mixin files or split existing services until V5 stabilization is complete. Consolidate opportunistically only.

**Do not do**: Do not split modules during admin or WebView parity work. Do not merge facade mixins into one large facade.py.

---

## Real-Media Proof Gap

### R-015: No Confirmed Real-Media Run Through WebView Shell

**Severity**: High

**Description**: Representative real-media validation through the WebView/Tauri shell is still incomplete. Fixture-based validation is strong, but it does not prove daily-driver behavior on the operator's real media set.

**Current mitigation**: V5 remains the external rollback workspace. Real-media validation playbook (`Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`) provides the procedure. Sample validation record flow provides evidence tracking.

**Owner area**: Operator + engineering.

**Next action**: Before treating the WebView as a daily-driver shell, run the validation playbook with a small known batch and record evidence in `Docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`.

**Do not do**: Do not claim WebView is a production replacement until the real-media validation playbook is complete with documented evidence.

---

## See Also

- Current state: `Docs/CURRENT_PROJECT_STATE.md`; historical transition plan body: `Docs/archive/historical-plans/V5_TAURI_TRANSITION_CURRENT_PLAN_20260520_ARCHIVED.md`
- Historical parity matrix: `Docs/archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/Docs/architecture/TAURI_WEBVIEW_PARITY_MATRIX.md`
- No-touch boundaries: `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Validation ladder: `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- Module ownership: `Docs/archive/completed-audits/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md`
