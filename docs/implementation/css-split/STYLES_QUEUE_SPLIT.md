# Split Plan - styles.queue.css

Date: 2026-06-25
Status: planning only
Change packet: MP-CHANGE-2026-0625-003

## Target

Split:

```text
apps/desktop/webview/static/assets/styles.queue.css
```

Current measured shape:

| Metric | Count |
|---|---:|
| Lines | 1,827 |
| Top-level rule blocks | 316 |
| Selector arms, comma-split | 402 |
| Top-level media/support blocks | 4 |

Run this only after the component and pages splits are complete and validated.

## Current Selector Families

| Selector family | Approx selector arms | Current line range | Notes |
|---|---:|---:|---|
| `fo-*` | 201 | 957-1826 | File Override drawer, source info, track controls, route advisory, series modal, light-mode overrides. |
| `[data-page-panel="queue"] ...` | 140 | 40-944 | Queue table scoped rows, drag state, scope preview, queue decision/proof panels. |
| `queue-*` | 49 | 51-971 | Priority menu, strategy toolbar, manual-order toolbar, table pagination, filter summaries. |
| `priority-*` | 8 | 3-106 | Priority badge chip and light-mode overrides. |
| queue IDs | 3 | 97-198 | Priority/manual-order/table page statuses. |
| `.settings-col` | 1 | 954 | Queue settings column. |

## Target Child Files

Final target shape:

```text
apps/desktop/webview/static/assets/styles.queue.css
apps/desktop/webview/static/assets/styles/queue/priority.css
apps/desktop/webview/static/assets/styles/queue/ordering.css
apps/desktop/webview/static/assets/styles/queue/table.css
apps/desktop/webview/static/assets/styles/queue/scope-and-decision.css
apps/desktop/webview/static/assets/styles/queue/file-overrides-shell.css
apps/desktop/webview/static/assets/styles/queue/file-overrides-form.css
apps/desktop/webview/static/assets/styles/queue/file-overrides-route.css
apps/desktop/webview/static/assets/styles/queue/file-overrides-tracks.css
apps/desktop/webview/static/assets/styles/queue/file-overrides-series.css
apps/desktop/webview/static/assets/styles/queue/light-mode.css
apps/desktop/webview/static/assets/styles/queue/responsive.css
```

Keep `styles.queue.css` as the parent wrapper:

```css
@import url("./styles/queue/priority.css");
@import url("./styles/queue/ordering.css");
@import url("./styles/queue/table.css");
@import url("./styles/queue/scope-and-decision.css");
@import url("./styles/queue/file-overrides-shell.css");
@import url("./styles/queue/file-overrides-form.css");
@import url("./styles/queue/file-overrides-route.css");
@import url("./styles/queue/file-overrides-tracks.css");
@import url("./styles/queue/file-overrides-series.css");
@import url("./styles/queue/light-mode.css");
@import url("./styles/queue/responsive.css");
```

Do not move queue CSS into component files during this split. Queue owns its
queue-specific styling even when selectors use shared component concepts.

## Queue Safety Boundary

CSS movement must not alter:

- queue launch scope;
- priority manifest routes;
- strategy persistence;
- manual-order manifest writes;
- file override staging;
- preview/apply route calls;
- backend-owned source/path/media policy;
- any strict confirmation field.

The split is CSS-only. If a failing test requires JS/API changes, stop and open
a separate implementation plan.

## Phase 0 - Baseline And Preconditions

Preconditions:

- Components split is complete and validated.
- Pages split is complete and validated.
- Direct CSS tests already resolve parent import wrappers.

Baseline commands:

```powershell
git status --short
rg -n 'styles\.queue\.css|priority-badge|queue-strategy-select|fo-drawer|fo-route|fo-track|fo-series' tests apps\desktop\webview\static
```

Minimum validation before selector movement:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
```

## Phase 1 - Priority And Ordering Controls

Move:

| Move to | Rule families |
|---|---|
| `styles/queue/priority.css` | `.priority-badge`, priority row emphasis, `.queue-priority-menu`, `.queue-priority-toolbar`, `#queue-priority-status`, priority light-mode overrides if they are tightly coupled. |
| `styles/queue/ordering.css` | `.queue-strategy-*`, `.queue-manual-order-*`, `.queue-table-pagination`, `#queue-manual-order-status`, `#queue-table-page-status`, `.queue-filter-summary`, drag state. |

Preserve the current S60/S70 order. Priority must continue to precede strategy
and manual-order controls.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
```

## Phase 2 - Queue Table And Scope/Decision Evidence

Move:

| Move to | Rule families |
|---|---|
| `styles/queue/table.css` | Queue table scoped selectors, table row state, selected/held/blocked row treatments, settings column. |
| `styles/queue/scope-and-decision.css` | Queue backend launch scope preview, queue decision/proof strips, queue review/scope evidence panels if present in this file. |

Do not alter table class names or data attributes. Existing tests and browser
smokes rely on them.

Validation:

```powershell
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_browser_large_table_smoke -q
```

## Phase 3 - File Override Drawer Shell And Form

Move:

| Move to | Rule families |
|---|---|
| `styles/queue/file-overrides-shell.css` | `.fo-open-btn`, drawer backdrop, drawer layout, header/body/footer/status shell, focus states. |
| `styles/queue/file-overrides-form.css` | `.fo-section-*`, `.fo-label-*`, `.fo-input`, `.fo-select`, inherited status/hints, use-inherited controls. |

The drawer is a high-use operator surface. Do not change widths, max heights,
focus outlines, z-index, hidden state, or status tones except by moving rules.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_browser_queue_file_overrides_smoke -q
```

## Phase 4 - Route Advisory And Track Metadata

Move:

| Move to | Rule families |
|---|---|
| `styles/queue/file-overrides-route.css` | `.fo-route-*`, route override controls, route preview/advisory status, remux pilot proof. |
| `styles/queue/file-overrides-tracks.css` | `.fo-source-info-*`, `.fo-track-*`, exact track action controls, track warning badges, loading states. |

Do not change warning/success/error tone selectors. These are evidence colors
used by tests and operator review.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
```

## Phase 5 - Series Modal And Batch Preview

Move:

| Move to | Rule families |
|---|---|
| `styles/queue/file-overrides-series.css` | `.fo-series-*`, `.fo-remux-pilot-proof`, series modal/backdrop/table, detected fields/counts/issues. |

Validation:

```powershell
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_browser_queue_file_overrides_smoke -q
```

## Phase 6 - Light Mode And Responsive Rules

Move light-mode and responsive rules last:

| Move to | Rule families |
|---|---|
| `styles/queue/light-mode.css` | `body.light-mode .priority-*`, `body.light-mode .queue-*`, `body.light-mode .fo-*` overrides. |
| `styles/queue/responsive.css` | Queue/file-override media blocks and reduced-motion blocks. |

Rules:

- Keep light-mode overrides after base queue/file-override imports.
- Keep responsive blocks after light-mode only if that matches current cascade.
  If current responsive rules must override light-mode, preserve that order.
- Keep `@media (prefers-reduced-motion: reduce)` contents intact.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.webview.test_webview_browser_queue_file_overrides_smoke -q
npm run webview:check
```

## Final Queue Split Exit Criteria

The queue split is complete only when:

- `styles.queue.css` is an import-only wrapper.
- All child imports point under `./styles/queue/`.
- No child imports `styles.queue.css`.
- Resolved queue CSS still contains the selectors currently pinned by tests:
  `.priority-badge`, `.queue-strategy-select`, `.fo-drawer`,
  `.fo-route-encode-advisory`, `.fo-track-group`, `.fo-series-modal`, and
  `.fo-series-table`.
- File Override drawer browser smoke passes or a browser-prerequisite skip is
  explicitly recorded.
- Queue table large-payload smoke passes or a browser-prerequisite skip is
  explicitly recorded.
- Generated summaries are refreshed.

Recommended final validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_browser_queue_file_overrides_smoke -q
& $py -m unittest tests.webview.test_webview_browser_large_table_smoke -q
npm run webview:prework:check
```
