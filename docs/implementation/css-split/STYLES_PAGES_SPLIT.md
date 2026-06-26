# Split Plan - styles.pages.css

Date: 2026-06-25
Status: planning only
Change packet: MP-CHANGE-2026-0625-003

## Target

Split:

```text
apps/desktop/webview/static/assets/styles.pages.css
```

Current measured shape:

| Metric | Count |
|---|---:|
| Lines | 3,027 |
| Top-level rule blocks | 427 |
| Selector arms, comma-split | 549 |
| Top-level media/support blocks | 9 |

Run this only after `STYLES_COMPONENTS_SPLIT.md` is complete and validated.

## Current Selector Families

| Selector family | Approx selector arms | Current line range | Notes |
|---|---:|---:|---|
| `settings-*` | 280 | 247-2633 | Settings tabs, wizard, library cards, readiness/result rows, save header, advanced/settings page surfaces. |
| `network-*` | 139 | 328-1087 | Network status, lifecycle, topology, setup, worker, state-file, and route evidence panels. |
| `failure-*` | 53 | 2673-2948 | Reports failure resolution, lifecycle strip, playbook, record tables. |
| `home-*` | 34 | 2-233 | Home quick controls, next queue, recent completed detail, promotion entry message. |
| `profile-*` | 13 | 256-1264 | Settings profile navigation and profile rows. |
| `rename-*` | 7 | 2499-2547 | Small rename separator/filter preview rules that are not yet in `styles.rename.css`. |
| reports scoped rules | 7 | 2637-2669 | Reports metric grid and triage panel. |
| compact/guided helpers | 6 | 2954-2986 | Shared disclosure/guided action helpers at the end of the reports/failure block. |
| `launch-*` | 1 | 3024 | Launch tab-bar margin fragment. |

## Target Child Files

Final target shape:

```text
apps/desktop/webview/static/assets/styles.pages.css
apps/desktop/webview/static/assets/styles/pages/home.css
apps/desktop/webview/static/assets/styles/pages/settings-tabs.css
apps/desktop/webview/static/assets/styles/pages/settings-library-profiles.css
apps/desktop/webview/static/assets/styles/pages/settings-wizard.css
apps/desktop/webview/static/assets/styles/pages/settings-save-header.css
apps/desktop/webview/static/assets/styles/pages/network.css
apps/desktop/webview/static/assets/styles/pages/rename-adjacent.css
apps/desktop/webview/static/assets/styles/pages/reports-failures.css
apps/desktop/webview/static/assets/styles/pages/responsive.css
```

Keep `styles.pages.css` as the parent wrapper:

```css
@import url("./styles/pages/home.css");
@import url("./styles/pages/settings-tabs.css");
@import url("./styles/pages/settings-library-profiles.css");
@import url("./styles/pages/settings-wizard.css");
@import url("./styles/pages/settings-save-header.css");
@import url("./styles/pages/network.css");
@import url("./styles/pages/rename-adjacent.css");
@import url("./styles/pages/reports-failures.css");
@import url("./styles/pages/responsive.css");
```

Do not move the small rename-adjacent block into `styles.rename.css` during the
first split. Moving it there would change its cascade position from before
controls/layout-manager/queue to after queue, which needs a separate cascade
decision.

## Phase 0 - Baseline And Preconditions

Preconditions:

- Component split is complete and validated.
- Tests already have a resolved-CSS helper for parent import wrappers.
- `styles.css` still imports `styles.pages.css` in its original order.

Baseline commands:

```powershell
git status --short
rg -n 'styles\.pages\.css|settings-tab-bar|network-status-banner|failure-resolution|home-next-queue' tests apps\desktop\webview\static
```

Minimum validation before selector movement:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_settings_libraries -q
& $py -m unittest tests.webview.test_webview_network_read_only_boundary -q
```

## Phase 1 - Home Page Rules

Move:

| Move to | Rule families |
|---|---|
| `styles/pages/home.css` | `.home-quick-*`, `.home-next-queue-*`, `.home-start-result`, `#home-next-queue-detail`, `#home-recent-completed-detail`, `#home-promotion-entry-message`, and Home-specific responsive rules. |

Keep the Home responsive block near the moved Home rules if it references only
Home selectors. If it shares breakpoint context with non-Home selectors, put it
in `styles/pages/responsive.css` during the final responsive phase instead.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_browser_home_live_state_smoke -q
```

Record a browser skip if Chrome/Edge is unavailable.

## Phase 2 - Settings Tabs And Save Header

Move page-level Settings shell rules:

| Move to | Rule families |
|---|---|
| `styles/pages/settings-tabs.css` | `.settings-tab-bar`, `.settings-tab-btn`, `.settings-tab-pane`, `.settings-section-nav-*`, tab/pane state rules, profile nav button rules only if they are tab-navigation behavior. |
| `styles/pages/settings-save-header.css` | Settings save header, save-state strips, review status rows that are page-header behavior rather than reusable builder controls. |

Do not move shared Settings builder controls already handled by the components
split.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_handbrake_settings_ui -q
& $py -m unittest tests.webview.test_webview_settings_libraries -q
```

## Phase 3 - Settings Library Profiles

Move library/profile-specific page rules:

| Move to | Rule families |
|---|---|
| `styles/pages/settings-library-profiles.css` | `.settings-library-*`, `.settings-wizard-library-row`, `.profile-*`, library profile cards, inheritance/override rows, output path/destination rows when page-specific. |

Stop if a rule is used outside Settings library/profile surfaces. Keep shared
form/card behavior in components.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_settings_libraries -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_browser_settings_launch_smoke -q
```

## Phase 4 - Settings Wizard And Readiness

Move wizard-specific rules:

| Move to | Rule families |
|---|---|
| `styles/pages/settings-wizard.css` | `.settings-wizard-*`, wizard step state rules, readiness strips, result rows, wizard library/profile rows that are not pure library cards. |

Keep data labels and backend-owned wording untouched.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_handbrake_settings_ui -q
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
```

## Phase 5 - Network Page Rules

Move Network page styling:

| Move to | Rule families |
|---|---|
| `styles/pages/network.css` | `.network-summary-list`, `.network-status-banner`, `.network-diagnostic-*`, `.network-topology-*`, `.network-lifecycle-*`, `.network-worker-*`, `.network-state-*`, setup/join/readiness/evidence page rules. |

Non-negotiable boundary:

- CSS movement must not change Network route logic, lifecycle safety,
  dry-run-confirmation logic, join/import setup, auth-token redaction, or worker
  state ownership.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_network_read_only_boundary -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_browser_network_smoke -q
```

If browser validation is unavailable, run static Network boundary tests and
record the browser gap.

## Phase 6 - Rename-Adjacent And Launch Fragment

Move small page fragments without changing their cascade owner:

| Move to | Rule families |
|---|---|
| `styles/pages/rename-adjacent.css` | `.rename-sep-*`, `.rename-filter-preview`, and other rename-adjacent rules currently in pages. |
| `styles/pages/settings-tabs.css` or `styles/pages/responsive.css` | `.launch-tab-bar` only if it is truly a tab-bar spacing helper shared with settings/reports tabs. |

Do not move these into `styles.rename.css` or Launch component files in this
phase.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_browser_rename_smoke -q
```

## Phase 7 - Reports And Failure Pages

Move Reports/Failures styling:

| Move to | Rule families |
|---|---|
| `styles/pages/reports-failures.css` | `[data-page-panel="reports"] ...`, `.report-triage-*`, `.reports-tab-bar`, `.failure-resolution-*`, `.failure-playbook-*`, `.failure-records-*`, `.compact-menu-disclosure`, `.guided-action-row`. |

Keep preview-first and backend-owned audit/failure behavior untouched.

Validation:

```powershell
& $py -m unittest tests.python.desktop.test_reports_view_static -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_browser_maintenance_reports_smoke -q
```

## Phase 8 - Pages Responsive Wrapper

Move remaining shared pages responsive blocks into
`styles/pages/responsive.css`.

Rules:

- Preserve breakpoint order exactly.
- Preserve combined selector lists at first.
- Do not pull Settings/Network/Reports responsive rules into owner files unless
  the moved block is exclusively scoped and validation already passed.

Validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_settings_libraries -q
& $py -m unittest tests.webview.test_webview_network_read_only_boundary -q
& $py -m unittest tests.python.desktop.test_reports_view_static -q
npm run webview:check
```

## Final Pages Split Exit Criteria

The pages split is complete only when:

- `styles.pages.css` is an import-only wrapper.
- All child imports point under `./styles/pages/`.
- No child imports `styles.pages.css`.
- Resolved pages CSS still contains the selectors currently pinned by tests:
  `.home-next-queue-panel`, `.settings-tab-bar`,
  `.settings-library-card`, `.settings-wizard-readiness-strip`,
  `.network-status-banner`, `.failure-resolution-summary-strip`, and
  `.rename-preview-output`.
- The component, controls, layout-manager, queue, and rename parent import order
  in `styles.css` is unchanged.
- Generated summaries are refreshed.

Recommended final validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_settings_libraries -q
& $py -m unittest tests.webview.test_webview_network_read_only_boundary -q
& $py -m unittest tests.python.desktop.test_reports_view_static -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
npm run webview:prework:check
```
