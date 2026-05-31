# Phase 08 UI Plan

Date: 2026-05-30

Scope: display-only WebView settings reframe for the HandBrake/remux rewrite.
This phase updates the static Settings UI, frontend metadata, frontend static
tests, and this approved rewrite doc. It does not change backend settings
persistence, PowerShell execution, FFmpeg command generation, subtitle/audio
policy, queue launch scope, publish/drain behavior, command journaling, source
movement, cleanup, or Tauri lifecycle behavior.

## Inputs

- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/08_HANDBRAKE_STYLE_UI_REWRITE.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- `Docs/rewrite/handbrake-remux/01_repo_audit.md` through
  `Docs/rewrite/handbrake-remux/07B_plan_executor.md`
- `Docs/audits/latest.md`

## UI Decision Brief

- Surface type: repeated-use desktop WebView settings/tool surface.
- Direction: restrained industrial/systematic, matching the existing V6
  operator UI.
- Implementation track: existing static HTML/CSS/vanilla JavaScript. No new
  framework, dependency, or motion library was added.
- Specific job: help the operator distinguish source facts, output settings,
  route-affecting policy, verification/publish safety, and preset/patch flow.
- Proof surface: backend settings workspace evidence, existing
  Preview/Save Patch commands, and explicit planner-preview honesty text.
- Required states: loaded saved settings, no source selected, planner preview
  unavailable, dirty staged patch, backend preview/save result, and advanced
  encoder disclosure.
- Scan-speed decision: top Settings tabs now follow the Phase 08 conceptual
  order with grouped tabs where the existing static UI should not be split
  into new behavior.

## Implemented Grouping

The phase requested twelve conceptual sections. The current WebView keeps fewer
actual tabs where splitting would create duplicate controls or new persistence
behavior:

| Phase 08 concept | Current WebView home |
| --- | --- |
| Summary | `Summary` tab |
| Source / Compatibility | `Source / Compatibility` tab |
| Routing | `Routing` tab |
| Dimensions | `Dimensions` tab, read-only pending backend exposure |
| Filters | `Filters` tab, read-only pending backend exposure |
| Video | `Video / Audio / Subtitles` tab |
| Audio | `Video / Audio / Subtitles` tab |
| Subtitles | `Video / Audio / Subtitles` tab |
| Container | `Container / Size Guards` tab, linked to Routing controls |
| Size & Bitrate Guards | `Container / Size Guards` tab, linked to Routing controls |
| Verification / Publish | `Verification / Publish` tab |
| Presets | `Presets` tab, using the existing Settings Wizard and patch flow |

## Preview Honesty

The Settings workspace does not yet expose a backend Local API route that
returns a `pipeline_plan.v1` preview for a selected `SourceMediaInfo` payload.
Phase 08 therefore does not invent a JavaScript decision engine.

The new Decision Preview panel:

- marks the preview as `Predicted pending cutover`;
- keeps the derived decision at `UNKNOWN`;
- states that the legacy path still executes;
- shows saved output policy as orientation only;
- states that backend planner preview is unavailable from Settings in this
  build;
- states that the WebView does not compute copy/remux/encode routing.

This preserves the Phase 08 rule that the UI must not show a confident preview
that the legacy executor could contradict.

## UI Map

- `Summary`
  - Decision Preview
  - Current Config
  - Config Health
  - Policy Readiness
  - Settings Overview
- `Source / Compatibility`
  - Read-only source fact placeholders separated from editable output settings
- `Routing`
  - Processing strategy, route threshold mode, size guard mode
  - Encoding strategy profile, encoding ladder, video encoder, output container
  - Movie/TV source-size route gates and bitrate caps
  - Active policy and existing backend Preview/Save Patch flow
- `Dimensions`
  - Read-only policy map pending backend exposure
- `Filters`
  - Read-only policy map pending backend exposure with forces-encode warning
- `Video / Audio / Subtitles`
  - Video controls with advanced encoder controls collapsed by default
  - File safety, recovery, subtitle, audio, and audio/subtitle check panels
- `Container / Size Guards`
  - Read-only summary linking the operator back to Routing
- `Verification / Publish`
  - Final Library Promotion settings and backend-owned validation/save flow
- `Presets`
  - Existing Settings Wizard, review, and backend save path

## Guardrails Preserved

- Existing element IDs for patch-staged settings controls were preserved.
- `Apply To Patch JSON`, `Preview Patch`, and `Save Settings` still use the
  existing backend validation/save paths.
- Source facts are displayed in evidence/read-only panels, not editable form
  controls.
- Advanced encoder flags, CPU fallback CRF, CPU preset, CPU priority, CPU
  threads, and remux-safe codec lists are behind the Advanced encoder controls
  disclosure.
- Rule taxonomy and strictness remain backend-owned display metadata, but the
  Library Profiles override UI does not render them as per-field chips. Library
  inherited/default versus explicit override state is text-only and color-coded
  across all override subtabs so the control rows stay compact.

## Validation

Targeted checks added or updated:

- `DesktopApp/tests/test_webview_handbrake_settings_ui.py`
- `DesktopApp/tests/test_webview_settings_libraries.py`

Passing validation:

- `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_webview_handbrake_settings_ui DesktopApp.tests.test_webview_settings_libraries`
- `npm run webview:check`
- `npm run webview:map:check`
- `npm run webview:contract:check`
- `npm run webview:dom-gaps:check`
- `npm run webview:routes:check`
- `npm run webview:slices:check`
- `npm run webview:script-order:smoke`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`
- `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`
- Local API plus in-app browser smoke: Settings rendered with the Phase 08 tab
  order, Decision Preview, predicted status, legacy-authority warning,
  planner-unavailable text, and closed advanced encoder disclosure. The
  temporary API process was stopped.

Known red baseline checks outside this phase:

- `npm run webview:prework:check` stops at the lint-budget gate:
  `warnings increased: 653 > 651` and
  `no-undef warnings increased: 392 > 390`.
- The broader static unittest batch that includes non-Settings WebView
  contracts remains red on unrelated Rename/Tauri/static-helper assertions and
  pre-existing CSS token violations in `styles.rename.css`.
- `DesktopApp/Runtime/Python/python.exe scripts/dev/refresh_summaries.py --check`
  remains red from the existing summary baseline: one missing summary, one
  stale summary, and existing WebView summary orphan records.

## Remaining Limits

- No backend planner preview route is exposed to Settings yet. A later phase
  must add a backend-owned preview surface before the UI can render real
  per-stream actions and a derived COPY/REMUX/ENCODE summary for a selected
  source.
- Dimensions and Filters remain read-only placeholders because this phase must
  not add new settings persistence fields or future-phase behavior.
- Production cutover remains blocked by the Phase 07B parity and rollout gates
  recorded in the tracker.
