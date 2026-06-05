# CSS and Settings Partial Surfaces

## Current Strain

- `styles.components.css`: about 2,230 lines.
- `styles.queue.css`: about 1,220 lines.
- `styles.pages.css`: about 789 lines.
- `partials/page-settings.html`: about 1,774 lines.
- Risk level: low-medium.
- Mixed concerns: shared components, page-specific styles, queue controls,
  settings wizard, settings tabs, library profile controls, rename settings,
  and large static Settings markup.

## Ideal Split

- CSS:
  - `assets/styles/progress.css`
  - `assets/styles/panels.css`
  - `assets/styles/launch.css`
  - `assets/styles/settings.css`
  - `assets/styles/settings-libraries.css`
  - `assets/styles/queue-priority.css`
  - `assets/styles/queue-file-overrides.css`
- Settings partials:
  - `partials/settings/status.html`
  - `partials/settings/guided-setup.html`
  - `partials/settings/routing.html`
  - `partials/settings/media-policy.html`
  - `partials/settings/library-profiles.html`
  - `partials/settings/rename.html`
  - keep `partials/page-settings.html` as the include shell if the loader
    supports partial composition.

## Extraction Order

1. Split CSS by existing comment/page boundaries.
2. Update asset order guards.
3. Split `page-settings.html` only after the partial loader and DOM-ID tests
   can prove IDs remain present.
4. Avoid visual redesign during the split.

## Validation

- WebView asset/script-order checks.
- DOM-ID inventory checks.
- Settings and Queue browser smokes.
- Visual/manual browser check for Settings, Queue, Launch, and Home.

## Must Not Change

DOM IDs, panel types, evidence-vs-interactive classification, accessible labels,
and Settings/Queue command boundaries.

