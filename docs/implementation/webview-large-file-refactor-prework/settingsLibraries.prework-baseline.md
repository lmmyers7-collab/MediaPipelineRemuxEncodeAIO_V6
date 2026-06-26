# Settings Libraries Refactor Prework Baseline

Date: 2026-06-26
Change packet: MP-CHANGE-2026-0626-011
Scope: prework only

## Scope

This note records the live `settingsLibraries.js` contract before any
troubleshooting-oriented extraction. It does not move functions, rename exports,
add child scripts, change backend routes, change Library Profile semantics, or
alter UI behavior.

The WebView remains a staging/display surface. Backend Settings preview/save,
Library Profile validation, inheritance semantics, effective media policy,
active config writes, and final-library promotion policy remain backend-owned.

The worktree was already broadly dirty before this packet. This prework must
stay limited to this note and its change packet.

## Asset Baseline

| Item | Current value |
|---|---|
| Source file | `apps/desktop/webview/static/assets/settingsLibraries.js` |
| Current line count | 2,528 |
| Public namespace | `window.mediaPipelineSettingsLibraries` |
| Namespace export count | 13 |
| Flat export count | 0 |
| Inventory row | `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` records namespace `mediaPipelineSettingsLibraries` and 0 flat exports |
| Script order | `/assets/settings/routePolicyModel.js` before `/assets/settingsView.js`; `/assets/settingsView.js` before `/assets/settingsLibraries.js`; `/assets/settingsLibraries.js` before `/assets/librariesRouteMap.js` and `/assets/settingsWizard.js` |
| Main Library partial | `apps/desktop/webview/static/partials/page-libraries.html` |
| Explicit read-first Settings partial | `apps/desktop/webview/static/partials/page-settings.html`; no `settings-library-*` IDs are present there |

## Public Export Ledger

All future extraction phases must keep the
`window.mediaPipelineSettingsLibraries` facade as the compatibility wrapper.
No child module may require loading after `settingsLibraries.js`.

| Export | Current signature | Source line | Known direct callers | Proposed owner | Wrapper requirement |
|---|---|---:|---|---|---|
| `renderSettingsLibraries` | `function renderSettingsLibraries(settings, options = {})` | 1504 | `app.js` refresh at line 842; browser settings/launch smoke | `assets/settings/libraries.view.js` plus state helper | Keep namespace wrapper; parent passes current settings/options |
| `initSettingsLibrariesEvents` | `function initSettingsLibrariesEvents()` | 2333 | `app.js` startup at line 1668 | parent facade or `libraries.view.js` | Keep wrapper; one event binding owner only |
| `activateLibraryProfile` | `function activateLibraryProfile(libraryId, options = {})` | 1570 | `librariesRouteMap.js` guided navigation at line 534 | `libraries.state.js` or `libraries.view.js` | Keep wrapper; selected-profile owner must remain single |
| `buildPatchFromLibraries` | `function buildPatchFromLibraries()` | 2085 | Browser settings/launch smoke; action button | `libraries.patch.js` | Keep wrapper; build only, no save |
| `stageLibraryWatchAutoRunPatch` | `function stageLibraryWatchAutoRunPatch()` | 729 | Watch stage button; public namespace | `libraries.watch.js` | Keep wrapper; delegates Settings patch write only |
| `previewLibraryWatchAutoRunPatch` | `async function previewLibraryWatchAutoRunPatch()` | 745 | Watch preview button | `libraries.watch.js` or `libraries.commands.js` | Keep wrapper; must call Settings preview |
| `saveLibraryWatchAutoRunPatch` | `async function saveLibraryWatchAutoRunPatch()` | 759 | Watch save button | `libraries.watch.js` or `libraries.commands.js` | Keep wrapper; must call Settings save |
| `deleteActiveLibrary` | `function deleteActiveLibrary()` | 2249 | Delete button | `libraries.view.js` with state owner | Keep wrapper; editor-only staged delete |
| `replaceActiveLibraryValuesWithDefaults` | `function replaceActiveLibraryValuesWithDefaults()` | 2282 | Defaults button | `libraries.reset.js` | Keep wrapper; reset-to-inherited only |
| `libraryProfileResetRequest` | `function libraryProfileResetRequest()` | 2079 | `settingsView.js` request extras at line 1029 | `libraries.reset.js` | Keep wrapper; Settings pulls reset evidence before preview/save |
| `previewLibraryProfiles` | `async function previewLibraryProfiles()` | 2143 | Preview button; static/browser tests | `libraries.commands.js` | Keep wrapper; must call Settings preview |
| `saveLibraryProfiles` | `async function saveLibraryProfiles()` | 2176 | Save button; browser LibraryProfiles smoke | `libraries.commands.js` | Keep wrapper; must call Settings save |
| `handleSettingsPostSaveRefreshFailure` | `function handleSettingsPostSaveRefreshFailure(message)` | 2212 | `settingsView.js` callback at line 200 | `libraries.commands.js` or parent facade | Keep wrapper; no retry/write behavior |

## Settings Handoff Ledger

| Handoff | Source line | Direction | Current behavior |
|---|---:|---|---|
| `const settingsView = window.mediaPipelineSettingsView || {}` | 5 | Libraries reads Settings namespace | Captures available preview/save/write helpers after `settingsView.js` loads |
| `rejectSettingsCommandWhileBusy` | 171 | Libraries -> Settings | Library preview/save refuses to rebuild while a shared Settings command is in flight |
| `settingsView.writeSettingsPatchJson` in watch staging | 731, 736 | Libraries -> Settings | Writes watch-folder patch keys into shared Changes JSON only |
| `previewSettingsPatch` in watch preview | 748, 755 | Libraries -> Settings | Delegates backend preview to Settings route path |
| `saveSettingsPatch` in watch save | 762, 769 | Libraries -> Settings | Delegates backend save to Settings route path |
| `markSettingsPatchTouched` | 2069 | Libraries -> Settings | Marks shared patch dirty after removing staged `LibraryProfiles` |
| `renderSettingsPatchSummary` | 2070 | Libraries -> Settings | Refreshes shared Settings patch summary after reset-from-current |
| `settingsView.writeSettingsPatchJson` in profile patch build | 2093, 2094 | Libraries -> Settings | Writes `{ LibraryProfiles }` into shared Changes JSON |
| `previewSettingsPatch` in profile preview | 2147, 2157 | Libraries -> Settings | Delegates LibraryProfiles preview to backend Settings preview |
| `saveSettingsPatch` in profile save | 2180, 2190 | Libraries -> Settings | Delegates LibraryProfiles save to backend Settings save |
| `handleSettingsPostSaveRefreshFailure` | `settingsView.js:200` | Settings -> Libraries | Reports stale Library Profile display after successful save with failed refresh |
| `libraryProfileResetRequest` | `settingsView.js:1029` | Settings -> Libraries | Adds `library_profile_resets` request extras when a `LibraryProfiles` patch is staged |

Stop rule: any save path that bypasses
`window.mediaPipelineSettingsView.saveSettingsPatch` is invalid.

## Library Profile State Ledger

| State | Current owner | Source lines | Notes |
|---|---|---:|---|
| Loaded settings | `lastSettings` in `settingsLibraries.js` | 118 | Updated from render/sync calls |
| Staged profiles | `profiles` array plus DOM cards | 119, 1977-1983 | DOM is collected into patch payload; saved config is not written here |
| Selected profile | `activeLibraryTabId`, active pane, localStorage key `mediapipeline-library-profile` | 120, 1533-1571 | Route-map handoff can select a profile without feedback loop |
| Dirty editor state | `libraryEditorDirty` | 121, 569-574 | Dirty state invalidates current patch and route-map saved-evidence scope |
| Patch freshness | `libraryProfilePatchCurrent`, `libraryProfilePatchSaved` | 122-123, 2018-2053 | Drives state strip: none, staged, stale, saved |
| Command in flight | `libraryProfileCommandInFlight` | 124, 152-178 | Separate guard layered with Settings busy guard |
| Reset request cache | `lastLibraryProfileResetRequest` | 125, 1985-2005, 2079-2083 | Settings reads this as request extras during preview/save |
| Open override sections | `openOverrideSectionsByLibrary` | 126, 1402-1417, 2476-2487 | Preserves troubleshooting context across render |
| Override groups | `editor`, `video`, `subtitles`, `audio` | 65-109, 254-266 | Backend metadata decides override eligibility and group ownership |
| Explicit override state | Row dataset `data-library-override` | 855-879, 1898-1915, 1940-1958 | Explicit keys stay explicit even when equal to global values |
| Reset-to-global | Row/path datasets `data-library-reset-pending`, `data-library-path-reset-pending` | 1886-2005, 2282-2316 | Reset removes override/path explicitness; it does not write global values as explicit profile values |
| Path inheritance | `default_tracking`, backend `library_profile_state.path_fields` | 322-346, 371-411 | Movies/TV source paths inherit `SourceMovies`/`SourceTV`; output inherits `Outsource`; promotion destination stays explicit |
| Route rules | Route size fields and `mediaPipelineRoutePolicyModel` | 12-34, 882-1229 | Local readouts are advisory/staging; backend route decisions remain authoritative |
| Watch controls | Library watch panel state and staged patch | 654-771 | Stages `EnableWatchFolders`, `WatchAction`, `WatchRespectScheduleWindow`, and optionally roots/debounce |
| Post-save refresh state | Save success flags and refresh failure callback | 2176-2218 | Save result comes from shared Settings status; failed refresh warns operator to reload |

## DOM Ledger

### Profile List And Editor

| ID or generated selector | Owner surface |
|---|---|
| `settings-library-profile-nav` | Profile tab navigation |
| `settings-library-profile-list` | Profile card host |
| `.settings-library-profile-pane`, `.settings-library-card` | Generated per-profile panes/cards |
| `data-library-field` | Generated profile fields such as name, designation, paths, promotion toggle |
| `data-library-override-row`, `data-library-override-control` | Generated override rows/controls |
| `data-library-use-default-override` | Reset explicit override to inherited |
| `data-library-use-default` | Reset path field to inherited where supported |

### Profile Actions And State

| ID | Purpose |
|---|---|
| `settings-libraries-status` | Page status in Libraries action panel |
| `settings-library-active-title` | Selected library display |
| `settings-library-active-detail` | Selected library detail/caution |
| `settings-library-state-strip` | Editor/patch/route-map state strip |
| `settings-library-editor-state` | Editor saved/dirty state |
| `settings-library-patch-state` | Patch none/staged/stale/saved state |
| `settings-library-route-map-scope` | Saved route-map evidence vs pending edits |
| `settings-library-add-button` | Add staged profile |
| `settings-library-delete-button` | Delete staged custom profile |
| `settings-library-defaults-button` | Reset explicit overrides to inherited/default |
| `settings-library-reset-button` | Reset editor from current loaded settings |
| `settings-library-build-patch-button` | Stage `LibraryProfiles` patch |
| `settings-library-preview-button` | Preview through Settings |
| `settings-library-save-button` | Save through Settings |
| `settings-library-editor-status` | Editor heading status |
| `settings-library-warning-summary` | Warning/patch handoff output |

### Watch Panel

| ID | Purpose |
|---|---|
| `settings-library-watch-panel` | Watch-folder auto-run panel |
| `settings-library-watch-status` | Watch status badge |
| `settings-library-watch-auto-run` | Auto-run checkbox |
| `settings-library-watch-respect-schedule` | Schedule-gate checkbox |
| `settings-library-watch-stage-button` | Stage watch patch |
| `settings-library-watch-preview-button` | Preview watch patch |
| `settings-library-watch-save-button` | Save watch patch |
| `settings-library-watch-summary` | Watch patch handoff text |

### Route Map Handoff IDs

These IDs belong to the read-only route-map panel and
`apps/desktop/webview/static/assets/librariesRouteMap.js`, not to future
Library Profile mutation modules.

`library-route-map-status`, `library-route-map-context`,
`library-route-map-warning-summary`, `library-route-map-profile-select`,
`library-route-trace-selector`, `library-route-compare-left`,
`library-route-compare-right`, `library-route-map-graph`,
`library-route-decision-rows`, `library-route-node-rows`,
`library-route-trace-rows`, `library-route-compare-rows`,
`library-route-navigation-rows`, and `library-route-validation-rows`.

## Direct Caller Search Results

| Surface | Direct usage |
|---|---|
| `apps/desktop/webview/static/assets/app.js` | Calls `renderSettingsLibraries(values.settings, refreshOptions)` during refresh and `initSettingsLibrariesEvents({ refreshAll })` at startup |
| `apps/desktop/webview/static/assets/librariesRouteMap.js` | Calls `activateLibraryProfile(nextId, { source: "route-map" })` for guided navigation |
| `apps/desktop/webview/static/assets/settingsView.js` | Calls `handleSettingsPostSaveRefreshFailure` and `libraryProfileResetRequest` |
| `tests/webview/test_webview_browser_library_profiles_save_smoke.py` | Browser save/reload flow; checks `saveLibraryProfiles` availability and actual `LibraryProfiles` save body |
| `tests/webview/test_webview_browser_settings_launch_smoke.py` | Calls `renderSettingsLibraries`, `buildPatchFromLibraries`, and Library Profile buttons |
| `tests/webview/test_webview_settings_libraries.py` | Source/static guardrail suite for Settings Libraries, route model order, state, reset, route-map read-only placement, and script order |
| `tests/webview/test_webview_handbrake_settings_ui.py` | Source assertions for namespace functions and backend preview/save wording |
| `tests/python/desktop/test_final_library_promotion.py` | Source assertion that Library Profile patch emits only `LibraryProfiles`, not final-promotion patch keys |
| `tests/python/desktop/test_api_static_files_policy.py` | Static served page must include `settings-library-profile-list` and `settings-library-save-button` |
| `tests/python/desktop/test_application_facade_web_static.py` | DOM prefix ownership maps `settings-library-` to Libraries |
| `apps/desktop/webview/static/assets/app/lifecycle.js` | Tooltip/help text for Library controls; no namespace call |
| Inventories | `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` and `WEBVIEW_DOM_ID_INVENTORY.md` record namespace and DOM surface |

No Launch/Home helper was found calling the Library namespace directly. Launch
handoff remains read-only through backend payloads and Settings/route-map
refresh data.

## Source-Only Guardrails

Future extraction must preserve or deliberately migrate these tests before any
function movement:

| Test | Source-only guardrail |
|---|---|
| `tests/webview/test_webview_settings_libraries.py` | Reads `settingsLibraries.js` directly for override group order, backend metadata usage, route-size editor tokens, designation pruning, display-only unavailable rows, reset wiring, stale patch state, unsaved-refresh preservation, watch staging, script order, and route-map read-only placement |
| `tests/webview/test_webview_handbrake_settings_ui.py` | Reads `settingsLibraries.js` for `previewLibraryProfiles`, `saveLibraryProfiles`, `buildPatchFromLibraries`, and backend Settings handoff text |
| `tests/python/desktop/test_final_library_promotion.py` | Reads `settingsLibraries.js` and asserts `LibraryProfiles: libraryProfiles`; must not generate final-promotion patch keys |
| `tests/python/desktop/test_api_static_files_policy.py` | Reads served static HTML for Library profile list/save IDs |
| `tests/python/desktop/test_application_facade_web_static.py` | Reads WebView static content and DOM prefix ownership |
| `tests/webview/test_webview_css_design_tokens.py` | Reads CSS for Library Profile card/state/route-map styling constraints |

## Target Troubleshooting Seams

| Seam | Candidate owner | Stable contract | Rollback rule |
|---|---|---|---|
| Profile state | `assets/settings/libraries.state.js` | Own selected profile, staged profile collection, dirty flags, patch freshness, open override sections, and reset request cache as one unit | Re-inline the state factory and keep `settingsLibraries.js` as the only owner if any second owner appears |
| Override groups | `assets/settings/libraries.overrides.js` | Pure helpers for backend metadata grouping, explicit/inherited labels, override value reading/writing, and reset-to-inherited display | Re-inline if helper needs DOM event ownership or backend validation |
| Patch builder | `assets/settings/libraries.patch.js` | Build `{ LibraryProfiles }` and reset extras; never call save routes | Re-inline if it starts knowing Settings route paths or persistence confirmation |
| Preview/save bridge | `assets/settings/libraries.commands.js` | Delegate busy guard, preview, save, and post-save refresh failure through `mediaPipelineSettingsView` | Re-inline if any path bypasses `saveSettingsPatch` or owns `confirm_save` |
| Route/promotion evidence | `assets/settings/libraries.routes.js` | Render local route-size readouts and promotion-destination display as staging/evidence only | Re-inline if it infers backend route decisions, final promotion eligibility, or path trust |
| Watch-folder panel | `assets/settings/libraries.watch.js` | Stage existing watch-folder Settings keys only; no scan, launch, queue, or schedule mutation | Re-inline if it calls non-Settings routes or starts work |
| Profile list/editor view | `assets/settings/libraries.view.js` | Render profile cards, navigation, state strip, empty/status text, and editor controls | Re-inline if event binding becomes split across multiple modules |
| Reset/default logic | `assets/settings/libraries.reset.js` | Mark reset-to-inherited requests and clear staged `LibraryProfiles` from Changes JSON | Re-inline if it writes global values as explicit overrides or mutates saved settings directly |

First extraction phase recommendation: extract only a pre-parent pure state/model
factory and source-test bundle helper, then keep all public wrappers in
`settingsLibraries.js`. Do not extract preview/save or event binding until the
state owner is single and tests read the parent-plus-child asset set.

## Validation Required Before Any Extraction

Baseline or future extraction work must run, or record a concrete environment
reason for skipping:

```powershell
git status --short
rg -n "mediaPipelineSettingsLibraries|settingsLibraries.js|settings-library-|LibraryProfiles|previewSettingsPatch|saveSettingsPatch" apps tests docs/inventories docs/implementation/library-route-map
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_libraries -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_library_profiles_save_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_settings_launch_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_final_library_promotion -q
npm run webview:prework:check
```

If files are extracted, also refresh generated summaries for changed source and
run change-control validation for the intended packet coverage.

Baseline run on 2026-06-26:

| Command | Result |
|---|---|
| `git status --short` | Ran; worktree was broadly dirty before this packet, with unrelated modified/deleted/untracked files across docs, generated summaries, WebView assets, PowerShell engine files, tests, and prior change packets |
| `rg -n "mediaPipelineSettingsLibraries\|settingsLibraries.js\|settings-library-\|LibraryProfiles\|previewSettingsPatch\|saveSettingsPatch" apps tests docs/inventories docs/implementation/library-route-map` | Ran; search results were used for the caller, DOM, Settings handoff, inventory, and source-only guardrail ledgers above |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_libraries -q` | Passed: 22 tests |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_library_profiles_save_smoke -q` | Passed: 1 browser-backed smoke |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_settings_launch_smoke -q` | Passed: 1 browser-backed smoke |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_final_library_promotion -q` | Passed: 35 tests |
| `npm run webview:prework:check` | Failed during `webview:lint:budget:check` after `webview:check` passed; current warning counts exceed budget: complexity `115 > 108`, max-lines-per-function `46 > 37`, no-extra-boolean-cast `1 > 0`, no-unused-vars `192 > 143` |
| `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes` | Passed: 774 packet(s) valid |
| `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage` | Failed: 11 unrelated generated files are not listed in any unreleased change packet |

## Stop Conditions

Stop extraction if a proposed module owns config persistence, backend profile
validation, final promotion policy, runtime media policy, path trust, scan or
launch behavior, source/output mutation, or strict save confirmation. Also stop
if a child script would load after `settingsLibraries.js`, if more than one
module owns Library Profile state, or if save no longer flows through
`mediaPipelineSettingsView.saveSettingsPatch`.

## Runtime Behavior

No runtime behavior changed in this prework packet.
