# WebView God-File Split Guardrails

This is a companion to `docs/testing/WEBVIEW_GODFILE_SPLIT_RUNBOOK.md`.
It exists to keep future `app.js` and `settingsView.js` slice passes
conservative, reviewable, and reversible. It does not replace `AGENTS.md`,
`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, or the generated WebView
baselines under `docs/generated/`.

## Existing Guardrails Checked First

Before this file was added, the repo already had these related safeguards:

- `python -m mediapipeline.tools.dev.ai_guardrail`: generic AI preflight/postflight checks.
- `python -m mediapipeline.tools.dev.check_architecture_guardrails`: architecture layout checks.
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`: media and mutation safety
  boundaries.
- `docs/testing/WEBVIEW_GODFILE_SPLIT_RUNBOOK.md`: WebView split procedure.
- `docs/generated/WEBVIEW_ROUTE_OWNERSHIP_GUARD.json`: settings route ownership
  and confirmation-gate baseline.

No dedicated WebView god-file split guardrail file existed.

## Non-Negotiable Scope

- Do not split files until a slice pass is explicitly requested.
- Do not introduce a bundler, TypeScript, JSX, ES modules, or a production asset
  pipeline change in this lane.
- Keep the plain ordered `<script>` model in `index.html`.
- Keep child scripts loading before their parent orchestration file.
- Keep backend-owned behavior backend-owned: settings persistence, media policy,
  queue mutation, pending-publish drain, rename apply, filesystem mutation, and
  process control must not move into WebView JavaScript.
- Do not touch media-policy, FFmpeg, subtitle, audio, publish/drain, source,
  scratch, output, or cleanup behavior as part of a WebView split.

## File Placement

Future slices should use folders under the current WebView asset root instead
of adding more root-level dotted files.

- `app.js` children: `apps/desktop/webview/static/assets/app/`
- `settingsView.js` children:
  `apps/desktop/webview/static/assets/settings/`

Prefer cohesive names such as `lifecycle.js`, `refresh.js`, `home.js`,
`layoutManager.js`, `backendResult.js`, `patchReview.js`, and
`policyImpact.js`. The parent files should remain the bootstrap/orchestration
owners until a later pass proves a smaller ownership boundary is safe.

## Required Preflight

Run this before editing a split candidate:

```powershell
npm run webview:prework:check
```

If that fails, stop and fix the baseline/tooling issue before moving code.
Do not begin a split from a failing prework gate.

Use `docs/generated/WEBVIEW_SPLIT_CANDIDATES.json` to choose the next slice.
Prefer candidates marked `safe_to_move_now` with small parent-state reads, no
parent-state writes, few outside-local references, and no settings route
ownership warnings.

## Slice Limits

- Move one cohesive group per pass.
- Do not mix `app.js` and `settingsView.js` in the same split pass.
- Do not combine a split with UI redesign, route changes, copy changes, CSS
  cleanup, dead-export removal, or behavior cleanup.
- Preserve public globals and transitional compatibility aliases until tests
  prove they are unused.
- Keep parent wrappers when an existing public function or inline handler may
  still call the parent.
- Treat generated baseline drift as a review event, not as routine churn.

## Stop Conditions

Stop immediately if any of these happen:

- `showPage`, `refreshAll`, `refreshAllNow`, or
  `window.mediaPipelineSettingsView` disappears from the script-order smoke.
- A settings route appears outside settings-owned assets.
- A confirmation-gated route loses its confirmation flag.
- ESLint errors become nonzero.
- ESLint warning budget increases without an intentional follow-up note.
- `WEBVIEW_PUBLIC_CONTRACT_BASELINE.json` changes unexpectedly.
- `WEBVIEW_DOM_ID_GAP_REPORT.json` review counts change without an intentional
  markup explanation.
- A moved function starts owning backend behavior instead of rendering,
  orchestration, or API request delegation.

## Required Postflight

After each split pass, run:

```powershell
npm run webview:check
npm run webview:lint:budget:check
npm run webview:map
npm run webview:contract
npm run webview:slices
npm run webview:dom-gaps
npm run webview:routes
npm run webview:prework:check
```

Then run the focused Python and browser smoke tests named in
`docs/testing/WEBVIEW_GODFILE_SPLIT_RUNBOOK.md` for the surface being split.

## Review Checklist

Before handing off a split pass, confirm:

- New child script paths are under the correct folder.
- `index.html` loads children before the parent.
- The parent still owns bootstrap wiring and cross-page orchestration.
- Public globals are unchanged or intentionally documented.
- Backend command routes, confirmation gates, and mutation boundaries are
  unchanged.
- Generated files were regenerated only for intentional drift.
- No unrelated dirty worktree changes were reverted or absorbed.
