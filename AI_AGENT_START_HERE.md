# AI Agent Start Here

This V6 folder is the active WebView-first remediation and Tauri/WebView2 refinement workspace. V5 remains the external fallback/rollback workspace and should not be modified from here.

Read these first, in order:

1. `Docs/CURRENT_PROJECT_STATE.md`
2. `V6_SPLIT_NOTES.md`
3. `OPEN_WORK_CHECKLIST.md`
4. `Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
5. `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
6. `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
7. `Docs/DOCS_INDEX.md`

Core rules:

- Keep V5 available externally as the trusted rollback/fallback workspace.
- Keep WebView/Tauri behind backend-owned routes and commands.
- Do not add frontend-owned filesystem mutation, settings persistence, queue mutation, pending-publish drain logic, rename apply logic, or media policy.
- Do not casually change FFmpeg, subtitle, audio, remux/encode, source/scratch/output, pending-publish, or queue behavior.
- Use `SmokeTests/` for smoke wrappers; do not place new smoke wrappers at the repository root.
- Use `.rgignore` for routine searches. Use `rg -u` only when intentionally auditing runtime, vendor, generated, or archived trees.

Current housekeeping status:

- `Docs/CURRENT_PROJECT_STATE.md` is the single current-state source, and `OPEN_WORK_CHECKLIST.md` is the single active task queue.
- `Docs/ACTIVE_FIX_CHECKLIST.md` and `V5_TRANSITION_REVIEW_FIX_CHECKLIST.md` are compatibility redirects. The old transition-plan and status-board bodies are quarantined under `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/historical-plans/`; `Docs/active-plans/` currently has no active Markdown files.
- Completed/stale Markdown files from the housekeeping catalog were quarantined under `Docs/archive/docs-housekeeping/2026-05-20-review/`.
- Old run logs and config backups were archived by date.
- Project Python caches were removed outside bundled/runtime/vendor trees.
- Tauri Rust build output `DesktopApp/tauri_shell/src-tauri/target/` may exist after local `cargo check`/build validation; it is generated output, not source, and repo hygiene may remove it after validation.
- `node_modules/` and `src-tauri/gen/` were intentionally kept for immediate Tauri preview work.
- 2026-05-18 source/dev validation passed for release self-test, bundled Python tests, browser no-mutation smokes, and Tauri prereq/build gates; this is not PG-3 clean-machine/package-mode or broad real-media daily-driver proof.
- 2026-05-20 V6 split removed the legacy desktop shell surface from this folder and preserved the Python local API, WebView assets, Tauri shell, backend pipeline, tests, docs, smoke wrappers, and bundled media tools. See `V6_SPLIT_NOTES.md`.

Return to transition work after reading the current-state docs. Prioritize real-media validation, WebView/Tauri lifecycle safety, diagnostics clarity, and backend-owned command safety.
