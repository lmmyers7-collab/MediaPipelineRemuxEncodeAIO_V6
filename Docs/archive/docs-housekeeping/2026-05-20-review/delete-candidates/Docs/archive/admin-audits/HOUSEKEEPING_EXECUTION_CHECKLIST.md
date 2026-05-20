# Housekeeping Execution Checklist

Created: 2026-05-15

Repository: `C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Purpose: step-by-step cleanup plan for reducing clutter without breaking V5 behavior. Do not perform destructive cleanup without explicit operator approval for the specific phase.

## Guardrails

- [ ] Do not touch V4.
- [ ] Do not weaken Tk fallback.
- [ ] Do not change FFmpeg, subtitle, audio, remux/encode, pending publish, source/scratch/output, queue, settings persistence, or backend lifecycle behavior as part of housekeeping.
- [ ] Do not delete logs, backups, generated folders, or state files without approval.
- [ ] Archive before delete.
- [ ] Keep `Docs\CURRENT_PROJECT_STATE.md`, `Docs\ACTIVE_FIX_CHECKLIST.md`, `Docs\DOCS_INDEX.md`, and `Docs\ARCHIVED_MD_INDEX.md` current after doc moves.
- [ ] Run validation for each phase before calling it complete.

## Phase H0 - Baseline Snapshot

Goal: make cleanup reversible and evidence-based.

Risk: Low.

Files affected: none.

Tasks:

- [ ] Confirm the app, local API, Tauri preview, and pipeline jobs are stopped.
- [ ] Record current top-level file/folder inventory.
- [ ] Record current `Docs` Markdown count.
- [ ] Record current `DesktopApp\RunLogs` count and latest timestamp.
- [ ] Record current config backup count.
- [ ] Run baseline release check:

```powershell
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Completion criteria:

- [ ] Baseline counts recorded.
- [ ] Release check result recorded.
- [ ] No cleanup performed yet.

## Phase H1 - Documentation Archive Pass

Status: completed on 2026-05-15 for completed/archive-classified Markdown files. Human-review and source-of-truth documents were left in place.

Goal: reduce stale AI/docs noise while preserving recoverability.

Risk: Low to Medium.

Likely files affected:

- `Docs\*.md`
- `Docs\archive\old-ai-directives\`
- `Docs\archive\admin-audits\`
- `Docs\archive\historical-reviews\`
- `Docs\archive\completed-checklists\`
- `Docs\DOCS_INDEX.md`
- `Docs\ARCHIVED_MD_INDEX.md`
- `Docs\CURRENT_PROJECT_STATE.md`
- `Docs\ACTIVE_FIX_CHECKLIST.md`

Tasks:

- [ ] Create archive folders only after approval:
  - [ ] `Docs\archive\old-ai-directives\`
  - [ ] `Docs\archive\admin-audits\`
  - [ ] `Docs\archive\historical-reviews\`
  - [ ] `Docs\archive\completed-checklists\`
- [ ] Move only Markdown files classified as `ARCHIVE` in `HOUSEKEEPING_AUDIT_REPORT.md` and `Docs\MD_CLEANUP_AUDIT_REPORT.md`.
- [ ] Do not move source-of-truth docs.
- [ ] Do not move files classified `NEEDS HUMAN REVIEW`.
- [ ] Update `Docs\ARCHIVED_MD_INDEX.md` with one-line summaries and new archive paths.
- [ ] Update `Docs\DOCS_INDEX.md` so active docs point to current locations.
- [ ] Update `Docs\CURRENT_PROJECT_STATE.md` if source-of-truth paths change.
- [ ] Update `Docs\ACTIVE_FIX_CHECKLIST.md` if human-review docs are resolved or remain active.

Validation:

- [ ] Run a file-existence sweep for indexed docs.
- [ ] Search for moved filenames in docs and update references.
- [ ] Confirm `Docs\DOCS_INDEX.md` starts with current source-of-truth docs.

Completion criteria:

- [ ] Completed/historical docs are archived, not deleted.
- [ ] Active docs are easier to scan.
- [ ] Future agents have one obvious starting path.

## Phase H2 - Project Cache Cleanup

Goal: remove regenerable Python cache artifacts outside bundled/vendor trees.

Risk: Low.

Likely files affected:

- `DesktopApp\mediapipeline_desktop_app\**\__pycache__`
- `DesktopApp\tests\__pycache__`
- `Pipeline\__pycache__`
- Project-authored `.pyc` files outside excluded trees.

Do not touch:

- `DesktopApp\Runtime\Python\**`
- `DesktopApp\tauri_shell\node_modules\**`
- `DesktopApp\tauri_shell\src-tauri\target\**`
- `Pipeline\Tools\**`
- `Pipeline\PowerShell-7.6.0-win-x64\**`

Tasks:

- [ ] Confirm app/tests are stopped.
- [ ] List project cache directories to be removed.
- [ ] Remove only project-authored `__pycache__` and `.pyc`.
- [ ] Do not remove bundled runtime caches unless a release rebuild is planned.

Validation:

- [ ] Run targeted Python test import check:

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

- [ ] Run a quick app import or targeted desktop test if relevant.

Completion criteria:

- [ ] Project cache artifacts removed.
- [ ] Tests regenerate bytecode successfully.

## Phase H3 - Runtime Log Retention

Status: completed on 2026-05-15 after the V5 local API was closed. The 50 newest `DesktopApp\RunLogs\*.log` files were kept in place; 975 older logs were moved to `DesktopApp\RunLogs\archive\2026-05-15\`. PID files and non-log runtime artifacts were not moved.

Goal: reduce `RunLogs` noise while preserving recent diagnostics.

Risk: Medium.

Likely files affected:

- `DesktopApp\RunLogs\*.log`
- `DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.log`
- stale-looking `DesktopApp\RunLogs\*.pid`

Tasks:

- [ ] Confirm no pipeline/local API/Tauri preview process is running.
- [ ] Identify latest successful run log.
- [ ] Identify latest failed/error run log.
- [ ] Keep latest diagnostic evidence in place or copy to archive.
- [ ] Move older logs to an approved archive folder by date.
- [ ] Do not delete `.pid` files until confirming no matching process exists.
- [ ] Document retained log policy in `Docs\LOG_ARTIFACT_CATALOG.md` or `Docs\RUNTIME_ARTIFACT_INVENTORY.md`.

Validation:

- [ ] Launch Tk fallback and confirm it writes fresh logs.
- [ ] Open WebView/Tauri preview if relevant and confirm Diagnostics handles log targets.
- [ ] Run diagnostics-related targeted smoke if log target behavior changed:

```powershell
.\SmokeTests\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1
```

Completion criteria:

- [ ] Old logs are archived, not deleted.
- [ ] New logs still appear normally.
- [ ] Diagnostics remains useful when old logs are absent.

## Phase H4 - Config Backup Retention

Status: completed on 2026-05-15. The 10 newest config backups were kept beside the live config; 24 older backups were moved to `Pipeline\ConfigBackups\archive\2026-05-15\`. The live config was not modified.

Goal: make active config easier to find while retaining rollback history.

Risk: Medium.

Likely files affected:

- `Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1`
- `Pipeline\MediaPipeline_config_chatgpt.psd1.bak.*`
- possible new backup archive folder.

Tasks:

- [ ] Decide retention policy, for example keep latest 10 in `Pipeline\`.
- [ ] Move older backups to an archive folder, not delete.
- [ ] Create a small backup index with timestamp and original filename.
- [ ] Do not modify `Pipeline\MediaPipeline_config_chatgpt.psd1`.

Validation:

- [ ] Run config/schema tests if available.
- [ ] Run release self-test:

```powershell
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Completion criteria:

- [ ] Live config remains untouched.
- [ ] Backups remain recoverable.
- [ ] Release check still passes.

## Phase H5 - Search And Agent Ergonomics

Status: completed on 2026-05-15. Added root `.rgignore` to exclude bundled/runtime/vendor/build/log/archive clutter from routine `rg` searches while preserving source/docs/test visibility. `rg --files` now reports the normal maintenance surface instead of the full generated tree.

Follow-up: root `AI_AGENT_START_HERE.md` was added on 2026-05-15 as a redirect-only entry point for future AI/code agents.

Goal: make future code audits faster and less noisy.

Risk: Low.

Likely files affected:

- Possible `.rgignore`
- `Docs\CURRENT_PROJECT_STATE.md`
- `Docs\DOCS_INDEX.md`
- `Docs\TLDR.md`

Tasks:

- [ ] Decide whether to add `.rgignore`.
- [ ] If added, mirror generated/runtime exclusions from `.gitignore`.
- [ ] Ensure source/test/docs are still searchable by default.
- [ ] Document how to include generated/vendor trees for packaging audits.
- [ ] Consider adding root `AI_AGENT_START_HERE.md` as a redirect-only doc.

Validation:

- [ ] Run `rg --files` and confirm active source files appear.
- [ ] Run sample searches for Python, PowerShell, WebView JS, and docs.
- [ ] Confirm generated logs no longer pollute routine searches.

Completion criteria:

- [ ] Future agents can search the project without reading runtime/vendor clutter by default.

## Phase H6 - Optional Tauri Build Artifact Prune

Status: partially completed on 2026-05-15. Removed generated Rust build output at `DesktopApp\tauri_shell\src-tauri\target\` after confirming no V5 process was running. Kept `node_modules\` and `src-tauri\gen\` in place because they are small and useful for immediate Tauri preview work. Rebuild will recreate `target\`.

Goal: reclaim disk and reduce generated-tree scan noise.

Risk: Medium.

Likely files affected:

- `DesktopApp\tauri_shell\node_modules\`
- `DesktopApp\tauri_shell\src-tauri\target\`
- `DesktopApp\tauri_shell\src-tauri\gen\`

Tasks:

- [ ] Confirm Node/npm/Rust/Tauri tooling is installed or bundled as expected.
- [ ] Confirm commands to regenerate dependencies/build outputs.
- [ ] Decide whether local development benefits more from keeping `node_modules` than pruning it.
- [ ] If approved, prune one generated tree at a time.
- [ ] Reinstall/rebuild immediately after pruning.

Validation:

- [ ] Run Tauri preview check:

```powershell
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat -CheckOnly
```

- [ ] Run affected Tauri shell tests:

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

Completion criteria:

- [ ] Tauri preview/checks still work after prune/rebuild.

## Phase H7 - Smoke Test Inventory Maintenance

Status: completed as an ongoing policy on 2026-05-15. All smoke wrappers are under `SmokeTests\`, `Docs\SMOKE_TEST_INVENTORY.md` is current, and the release self-test checks the required wrapper paths.

Goal: keep smoke tests discoverable and prevent root clutter from returning.

Risk: Low.

Likely files affected:

- `SmokeTests\*.ps1`
- `SmokeTests\README.md`
- `Docs\SMOKE_TEST_INVENTORY.md`
- `Docs\DOCS_INDEX.md`
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`

Tasks:

- [ ] Keep every smoke wrapper under `SmokeTests\`.
- [ ] Add new wrapper to `Docs\SMOKE_TEST_INVENTORY.md`.
- [ ] Update release self-test if wrapper discovery or required wrapper list changes.
- [ ] Keep wrapper boundary text accurate.

Validation:

- [ ] Run one representative smoke wrapper:

```powershell
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1
```

- [ ] Run release self-test if wrapper list changed:

```powershell
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Completion criteria:

- [ ] No smoke wrappers live at repo root.
- [ ] Inventory and release checks agree with disk layout.

## Phase H8 - Code/Test Cohesion Cleanup Only When Triggered

Goal: improve maintainability of oversized source/test files without architecture churn.

Risk: Medium to High.

Trigger examples:

- A feature change touches a large WebView page module.
- A test failure requires editing a giant test file.
- A contract change requires updating repeated helpers across files.

Tasks:

- [ ] Identify the cohesive behavior being extracted.
- [ ] Avoid pass-through modules.
- [ ] Keep route contracts and DTO schemas stable.
- [ ] Preserve DOM IDs unless tests/docs are updated.
- [ ] Preserve Tk fallback.
- [ ] Add/update tests before considering extraction complete.

Validation:

- [ ] Run targeted unit tests for touched subsystem.
- [ ] Run affected smoke wrapper.
- [ ] Run Tauri shell check if WebView/Tauri files changed.
- [ ] Run release self-test for broad file-layout confidence.

Completion criteria:

- [ ] Extraction reduces actual cognitive load.
- [ ] No behavior changed unintentionally.
- [ ] Tests prove parity.

## Recommended Approval Order

1. [ ] H1 Documentation Archive Pass.
2. [ ] H2 Project Cache Cleanup.
3. [ ] H3 Runtime Log Retention.
4. [ ] H4 Config Backup Retention.
5. [ ] H5 Search And Agent Ergonomics.
6. [ ] H7 Smoke Test Inventory Maintenance as ongoing policy.
7. [ ] H6 Tauri Build Artifact Prune only if disk/search burden justifies rebuild cost.
8. [ ] H8 Code/Test Cohesion only when feature work provides a safe trigger.

## Stop Conditions

Stop cleanup and ask for direction if:

- [ ] A file appears to be active runtime state, pending-publish evidence, queue state, or command journal.
- [ ] A cleanup candidate is referenced by a release self-test.
- [ ] A config backup might be the only rollback for a recent settings change.
- [ ] Tauri/WebView rebuild tooling is missing after pruning generated artifacts.
- [ ] Tk fallback fails after a cleanup phase.
- [ ] Any test failure appears related to moved/archived docs, smoke wrappers, config, or runtime paths.

## Final Return-To-Transition Step

After approved housekeeping phases are complete:

- [x] Re-run the appropriate validation ladder.
- [x] Update `Docs\CURRENT_PROJECT_STATE.md`.
- [x] Update `Docs\ACTIVE_FIX_CHECKLIST.md`.
- [x] Update `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md` with a short housekeeping completion note.
- [x] Return-to-transition path restored: next work should prioritize real-media validation, WebView parity, diagnostics clarity, and backend-owned command safety.
