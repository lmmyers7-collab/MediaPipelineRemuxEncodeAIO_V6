# WebView CSS Split Planning Pack

Date: 2026-06-25
Status: planning only
Change packet: MP-CHANGE-2026-0625-003

## Purpose

This planning pack describes how to split the three largest WebView CSS files
without changing operator behavior, backend authority, media policy, or the
current plain-CSS runtime model.

The requested targets are:

| File | Current lines | Current top-level rule blocks | Current selector arms | Primary pressure |
|---|---:|---:|---:|---|
| `apps/desktop/webview/static/assets/styles.components.css` | 5,611 | 807 | 1,082 | Shared component rules mixed with Completed, Launch, Pending, Schedule, Settings, Telemetry, and responsive overrides. |
| `apps/desktop/webview/static/assets/styles.pages.css` | 3,027 | 427 | 549 | Page-specific rules for Home, Settings, Network, Reports, Failures, and small rename/launch fragments. |
| `apps/desktop/webview/static/assets/styles.queue.css` | 1,827 | 316 | 402 | Queue table, queue controls, and File Override drawer rules sharing one failure surface. |

The line and rule counts above were collected from the current repo on
2026-06-25. The selector-arm count is comma-split and is intentionally higher
than the user's approximate selector counts.

## Authority And Scope

This pack is subordinate to:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/change_control/README.md`
- executable source and tests

If this pack conflicts with those authority docs or with source/tests, stop and
update the stale planning text before implementation continues.

## Non-Goals

- No visual redesign.
- No color, spacing, typography, radius, or theme-token changes except where a
  moved rule must keep its existing declaration intact.
- No frontend route, command, API, queue, settings-save, publish, drain, rename,
  filesystem, source, scratch, output, or media-policy behavior changes.
- No JavaScript module conversion, bundler, Sass, PostCSS, Tailwind, CSS modules,
  CSS-in-JS, or framework migration.
- No introduction of CSS cascade layers. The first split should preserve the
  current cascade using plain ordered `@import` statements.
- No hand edits under `docs/generated/`; refresh generated summaries with the
  repository tooling after source edits.

## Current Runtime Contract

`apps/desktop/webview/static/index.html` loads one stylesheet:

```html
<link rel="stylesheet" href="/assets/styles.css">
```

`apps/desktop/webview/static/assets/styles.css` currently imports the CSS assets
in this order:

```css
@import url("./styles.tokens.css");
@import url("./styles.theme.css");
@import url("./styles.layout.css");
@import url("./styles.components.css");
@import url("./styles.pages.css");
@import url("./styles.controls.css");
@import url("./styles.layout-manager.css");
@import url("./styles.queue.css");
@import url("./styles.rename.css");
```

The split must preserve that order unless a separate behavior-change packet
explicitly proves and documents a cascade-order change. The safe target pattern
is:

```css
/* apps/desktop/webview/static/assets/styles.components.css */
@import url("./styles/components/base.css");
@import url("./styles/components/progress.css");
@import url("./styles/components/tables.css");
```

Keep `styles.css` importing the three parent CSS files until the entire split is
complete and tests prove direct child imports are safer.

## Target Placement

Use nested CSS folders under the existing assets root:

```text
apps/desktop/webview/static/assets/styles/components/*.css
apps/desktop/webview/static/assets/styles/pages/*.css
apps/desktop/webview/static/assets/styles/queue/*.css
```

Reasons:

- The top-level `assets/` folder is already crowded with CSS, JS, and HTML
  assets.
- The Local API asset resolver serves nested `assets/...` files as long as the
  resolved path remains under the static assets root.
- A parent wrapper per original CSS file lets the cascade and existing
  `styles.css` contract remain stable while tests migrate.

## Required Execution Order

Implement the split one parent file at a time:

1. `STYLES_COMPONENTS_SPLIT.md`
2. Run the full component split validation named in that document.
3. `STYLES_PAGES_SPLIT.md`
4. Run the full pages split validation named in that document.
5. `STYLES_QUEUE_SPLIT.md`
6. Run the full queue split validation named in that document.
7. Run the final integrity review in this README.

Do not start `styles.pages.css` until the component split is validated. Do not
start `styles.queue.css` until the pages split is validated.

## Baseline Commands Before Any Implementation

Run these before moving selectors:

```powershell
git status --short
rg -n 'styles\.(components|pages|queue)\.css|read_static\("assets/styles\.(components|pages|queue)\.css' tests ops\scripts apps\desktop\webview\static
rg -n '@import url\("\./styles\.(components|pages|queue)\.css"\)' apps\desktop\webview\static\assets\styles.css tests
```

Record the dirty-worktree caveat in the change packet without absorbing
unrelated files.

## Test-Helper Migration Comes First

Many tests read `styles.components.css`, `styles.pages.css`, or
`styles.queue.css` directly and assert that specific selectors are present in
that file. If a parent file becomes an import-only wrapper, those tests will
fail unless they read the resolved CSS bundle.

Before moving any selector, add or reuse a test helper that:

1. reads a CSS file;
2. resolves local `@import url("./...")` statements recursively;
3. rejects unsafe paths outside `apps/desktop/webview/static/assets`;
4. preserves import order;
5. returns concatenated CSS text for selector assertions.

Use that helper in tests that currently inspect these parent files directly.
Keep tests that intentionally verify the parent wrapper's import order reading
the parent wrapper itself.

The minimum direct-test migration surface currently includes:

- `tests/webview/test_webview_css_design_tokens.py`
- `tests/webview/test_webview_handbrake_settings_ui.py`
- `tests/webview/test_webview_dropdown_remediation_static.py`
- `tests/webview/test_webview_settings_libraries.py`
- `tests/webview/test_webview_network_read_only_boundary.py`
- `tests/webview/test_webview_schedule_smoke.py`
- `tests/python/desktop/test_application_facade_web_static.py`
- `tests/python/desktop/test_application_facade_web_static_shell.py`
- `tests/python/desktop/test_metrics_feature.py`
- `tests/python/desktop/test_reports_view_static.py`
- `tests/python/desktop/application_facade_test_support.py`

## Common Validation Commands

Use the bundled Python runtime:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
```

Core CSS/static checks:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static_shell -q
& $py -m unittest tests.python.desktop.test_api_static_files_policy -q
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
npm run webview:prework:check
npm run webview:check
```

After each parent split, run the document-specific tests and then:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

If strict worktree coverage fails because unrelated files were already dirty,
do not add unrelated files to the packet. Report them.

## Per-Phase Change Packet Notes

For each implementation phase, record:

- parent file split target;
- selector families moved;
- old line range and new child file path;
- whether the parent remains a wrapper or still contains rules;
- tests migrated to resolved CSS reads;
- validation commands and outcomes;
- generated summaries refreshed;
- rollback path;
- unrelated dirty files not covered by the packet.

## Final Integrity Review

After all three splits pass their own validation, re-open the repo as if the
implementation is unfamiliar:

1. Re-read `AGENTS.md`, `docs/DOCS_INDEX.md`, and this planning pack.
2. Re-run:

   ```powershell
   git status --short
   rg -n '@import url' apps\desktop\webview\static\assets\styles.css apps\desktop\webview\static\assets\styles.*.css apps\desktop\webview\static\assets\styles
   rg -n 'styles\.(components|pages|queue)\.css|assets/styles/(components|pages|queue)' tests apps\desktop\webview\static
   ```

3. Confirm each parent wrapper imports only its own child folder and preserves
   child order.
4. Confirm no child CSS file imports back to a parent wrapper.
5. Confirm every `@import` path exists on disk and is served by the Local API.
6. Confirm direct selector assertions read resolved CSS unless they are testing
   wrapper import order.
7. Confirm `styles.css` still imports tokens, theme, layout, components, pages,
   controls, layout-manager, queue, and rename in the original order.
8. Confirm generated summaries include the new CSS files and no generated files
   were hand edited.
9. Run:

   ```powershell
   & $py -m unittest tests.webview.test_webview_css_design_tokens -q
   & $py -m unittest tests.python.desktop.test_application_facade_web_static -q
   & $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
   & $py -m unittest tests.webview.test_webview_handbrake_settings_ui -q
   & $py -m unittest tests.webview.test_webview_settings_libraries -q
   & $py -m unittest tests.webview.test_webview_network_read_only_boundary -q
   & $py -m unittest tests.webview.test_webview_schedule_smoke -q
   & $py -m unittest tests.python.desktop.test_metrics_feature -q
   & $py -m unittest tests.python.desktop.test_reports_view_static -q
   npm run webview:prework:check
   npm run webview:check
   ```

10. Run browser-backed smokes if CSS layout changes were made beyond mechanical
    selector movement:

    ```powershell
    .\ops\scripts\smoke\Test-WebViewBrowserLargeTableSmoke.ps1
    .\ops\scripts\smoke\Test-WebViewBrowserLayoutManagerSmoke.ps1
    .\ops\scripts\smoke\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1
    .\ops\scripts\smoke\Test-WebViewBrowserQueueFileOverridesSmoke.ps1
    .\ops\scripts\smoke\Test-WebViewBrowserSettingsLaunchSmoke.ps1
    .\ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1
    ```

If browser prerequisites are unavailable, record the skip reason and rerun on a
browser-capable machine before release acceptance.

## Stop Conditions

Stop and reassess if any of these happen:

- A selector is edited while being moved.
- A rule moves across the parent-file import boundary and changes cascade
  order.
- A moved responsive rule no longer applies at the same breakpoint.
- A light-mode override moves before the base rule it overrides.
- A test is weakened from a concrete selector assertion to a broad existence
  assertion without an equivalent resolved-CSS check.
- A child CSS file imports the parent wrapper or creates a cycle.
- A nested CSS asset is not served by the Local API static file route.
- Any browser smoke shows text overlap, clipped controls, missing focus state,
  broken responsive layout, or unreadable table/drawer content.
- Any implementation phase touches backend route, command, queue, publish,
  rename, source, scratch, output, or media-policy code.
