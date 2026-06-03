# Settings View Split Plan

Date: 2026-06-03

## Scope

Target file:
`DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.js`

Current audit signal:

- 2,195 lines.
- Highest dependency-surface score from the 2026-06-03 god-file audit.
- 300 top-level declarations, 93 public exports, 5 backend routes, 9 DOM IDs,
  and 1 event type in the generated WebView public contract baseline.

This is a WebView split only. Do not move settings persistence, media policy,
queue mutation, pending-publish drain, rename apply, filesystem mutation, or
process lifecycle authority into frontend code.

## Placement

Use the existing foldered Settings asset area:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settings/`

Do not add more root-level `settingsView.*.js` files for new slices unless a
compatibility wrapper is deliberately required by script-order or public-contract
tests.

## Proposed Slices

1. `settings/metadataFields.js`
   - Move field label, persisted-key display, help-text, metadata tag,
     advanced-field, default-value, and allowed-value display helpers.
   - Candidate functions include `settingsFieldLabel`,
     `settingsPersistedKeyDisplay`, `settingsPersistedKeyDisplayList`,
     `settingsFieldHelpText`, `settingsMetadataTags`,
     `settingsFieldIsAdvanced`, `settingsMetadataValue`,
     `settingsFieldDefaultValue`, `settingsFieldDefinition`,
     `settingsFieldAllowedValues`, and `formatSettingsChoiceLabel`.

2. `settings/builderControls.js`
   - Move generic builder-control plumbing only.
   - Candidate functions include `settingsBuilderFieldGroups`,
     `settingsAllBuilderFields`, `applySettingsFieldMetadataToControl`,
     `applySettingsFieldMetadataToControls`, `refreshSettingsSelectChoices`,
     `refreshSettingsBuilderChoices`, `ensureSettingsAdvancedToggle`, and
     `syncSettingsAdvancedPane`.
   - Keep domain-specific builders in their existing builder files.

3. `settings/patchReview.js`
   - Existing file. Finish moving local patch-review helpers if any remain in
     the parent.
   - Candidate helpers include `settingsPatchLocalValidationHintsForKey`,
     `settingsPatchLibraryOverrideValidationHints`,
     `settingsPatchLocalValidationHints`, and
     `settingsPatchLocalValidationHintLines`.

4. `settings/commands.js`
   - Deferred slice. Move only after route ownership tests are updated
     deliberately.
   - Candidate functions include `validateCurrentSettings`,
     `previewSettingsPatch`, `saveSettingsPatch`, `reloadSettingsFromDisk`,
     and `browseSettingsPath`.
   - Keep `/api/settings/*` route ownership explicit and confirmation-gated.

## Parent Responsibilities To Preserve

- `window.mediaPipelineSettingsView` remains the public namespace.
- Existing flat compatibility exports remain until the public-contract baseline
  proves they can be removed.
- The parent keeps high-level orchestration and cross-slice state while child
  files are introduced.
- Backend Preview/Save remains authoritative for persisted settings.

## Validation

Before editing:

```powershell
npm run webview:prework:check
```

After each slice:

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

Focused tests:

```powershell
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_application_facade_settings_workspace -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_settings_patch_smoke -q
.\DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_webview_frontend_mutation_boundary -q
```
