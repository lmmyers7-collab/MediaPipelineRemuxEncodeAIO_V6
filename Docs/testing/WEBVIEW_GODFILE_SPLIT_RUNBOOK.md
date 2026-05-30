# WebView God-File Split Runbook

This runbook covers future split passes for `app.js` and `settingsView.js`.
It is prework only; do not create child assets until a split pass is explicitly
approved.

## Baseline Before Slicing

Run the full prework gate from the repository root:

```powershell
npm run webview:prework:check
```

If the source files intentionally changed before a split pass, regenerate the
affected generated baselines first:

```powershell
npm run webview:map
npm run webview:contract
npm run webview:slices
npm run webview:dom-gaps
npm run webview:routes
npm run webview:lint:budget
```

Do not regenerate baselines to hide regressions. Regenerate only when the
underlying WebView contract intentionally changed.

## Candidate Selection

Use `Docs/generated/WEBVIEW_SPLIT_CANDIDATES.json` as the first decision point.
Prefer candidates with:

- `movement_assessment` set to `safe_to_move_now`
- no `parent_state_writes`
- small `parent_state_reads`
- small `outside_local_functions`
- no `/api/settings/*` route ownership notes
- no required parent wrapper unless the wrapper is part of the explicit split

For `settingsView.js`, keep persistence commands in the parent until route
ownership tests are deliberately updated. This includes settings validate,
preview, save, reload, and browse-path flows.

## Split Rules

- Keep the plain ordered `<script>` runtime model.
- Add child scripts before their parent file in `index.html`.
- Keep existing `window.*` namespace exports and transitional flat exports.
- Preserve parent wrappers for public functions until tests prove they are
  unused.
- Move one cohesive group per pass.
- Do not mix `app.js` and `settingsView.js` splits in the same pass.
- Do not introduce a bundler, ES module migration, or TypeScript conversion in
  this lane.

## Validation Per Pass

Before edits:

```powershell
npm run webview:prework:check
```

After edits:

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

Then run the targeted Python tests for the surface being split. For `app.js`,
include WebView static, inventory docs, frontend mutation boundary, and the
layout/home browser smoke when script order changes. For `settingsView.js`,
include settings workspace/static tests, settings libraries tests, mutation
boundary tests, and settings browser smoke.

## Stop Conditions

Stop the split and restore the previous shape if:

- script-order smoke loses `showPage`, `refreshAll`, `refreshAllNow`, or
  `window.mediaPipelineSettingsView`
- route ownership guard reports a settings route outside settings-owned assets
- a confirmation-gated route loses its confirmation flag
- DOM gap review count changes without an intentional markup explanation
- ESLint error count becomes nonzero
- the public contract baseline changes unexpectedly
