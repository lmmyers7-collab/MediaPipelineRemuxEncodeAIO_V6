# app/status/presentation.py

## Current Strain

- Approximate size: 500 lines.
- Risk level: medium.
- Mixed concerns: status DTO presentation, operator summary text, progress
  evidence display, lifecycle state labels, and UI-facing formatting.

## Ideal Split

- `app/status/presentation_labels.py`: status labels, severity mapping, and
  state text.
- `app/status/presentation_progress.py`: progress and current-work display
  helpers.
- `app/status/presentation_lifecycle.py`: lifecycle/close-readiness summaries.
- Keep `presentation.py` as the status facade used by `app/status/service.py`.

## Extraction Order

1. Extract label/severity helpers.
2. Extract progress display helpers.
3. Extract lifecycle summaries after close-readiness tests cover outputs.

## Validation

- Status service tests.
- Home live-state smoke if displayed fields change.
- Close-readiness tests if lifecycle labels change.

## Must Not Change

Backend-authored status meaning, close-readiness safety text, and WebView
display contracts.

