# WebView completedView.evidence.js

## Current Strain

- Approximate size: 1,715 lines, about 104 symbol matches.
- Risk level: medium-high.
- Mixed concerns: output acceptance posture, command evidence, filter scope,
  proof rows, route agreement, selected-row detail, summary lines, and DOM
  rendering.

## Ideal Split

- `assets/completed/evidence/acceptance.js`: acceptance rows, status, summary,
  and detail helpers.
- `assets/completed/evidence/filterScope.js`: local filter scope evidence and
  action text.
- `assets/completed/evidence/routeAgreement.js`: queue/completed route
  agreement rows and summaries.
- `assets/completed/evidence/commands.js`: acceptance command history helpers.
- Keep existing `completedView.evidence.js` as module coordinator initially.

## Extraction Order

1. Extract command-history helpers.
2. Extract filter-scope helpers.
3. Extract acceptance row builders.
4. Extract route-agreement helpers.
5. Move render functions after row builders are tested.

## Validation

- Completed/Pending proof browser smoke.
- Completed static tests.
- Command evidence smoke if command rows change.

## Must Not Change

Completed remains evidence-only. It must not accept, rerun, publish, repair, or
touch media from frontend code.

