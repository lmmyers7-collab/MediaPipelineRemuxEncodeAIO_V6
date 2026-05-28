# 0007. WebView framework choice (vanilla vs Lit/Preact)

Status: deferred
Date: 2026-05-28

## Context

The WebView SPA today is hand-written vanilla JS under
`DesktopApp/mediapipeline_desktop_app/ui_web/static/`. There is no
build step, no framework dependency, no bundler. Panels (Queue, Launch,
Settings, Diagnostics, etc.) share a small set of fetch and DOM
helpers; each panel owns its DOM manipulation.

This works at the current scale but has known costs:

- DOM ownership is implicit — multiple panels can touch the same
  element if they're loaded together; bugs are eventual.
- Re-render strategy is hand-rolled per panel.
- Component reuse is by copy-paste.
- Accessibility passes are manual.

`ARCHITECTURAL_OVERHAUL_PLAN.md` flags this as ADR-0007 to be decided
during the overhaul; the plan does not pick a winner.

## Decision

**Defer.** Continue with vanilla JS until at least one of these is
true:

- A new panel takes more than a week to ship and DOM management is the
  named cause.
- An accessibility regression makes it past review because manual DOM
  patches did not consider focus order or ARIA roles.
- The settings panel's "form generated from contracts" idea (Phase 4)
  proves impractical to maintain by hand.

When any of those lands, write **0012-webview-framework-choice.md**
and pick:

- **Lit** if the choice is driven by component encapsulation and
  Shadow DOM is acceptable.
- **Preact (signals + HTM, no JSX)** if the choice is driven by
  reactive state and bundle size matters more than encapsulation.
- **Stay vanilla** if the cost calculus has changed (e.g. all panels
  refactored to a small shared helper that handles the actual
  pain points).

No frontend framework lands without an explicit ADR. No bundler lands
without an explicit ADR. No new framework dependency lands as a
drive-by.

Rules in force during deferral:

- New panels follow the existing patterns in
  `DesktopApp/mediapipeline_desktop_app/ui_web/static/`. They do not
  import a framework from a CDN, vendor a framework into `static/`, or
  start a build step.
- Panels share helpers only via the existing JS modules under
  `ui_web/static/`. No second utility tree.
- Accessibility (keyboard nav, ARIA roles, focus order) is reviewed on
  every new panel, framework or not. The lack of a framework does not
  excuse skipping the review.

## Open questions

Open until 0012:

- Is the form-from-contract render feasible in vanilla JS at the
  settings panel's complexity?
- Does the Tauri shell impose constraints on Shadow DOM behavior that
  would rule Lit out?
- Does the WebView2 version in use affect framework choice?

## Consequences

Code and structure:

- No new dependencies in the frontend.
- Existing patterns continue; pain is logged but not solved.

Operational surface:

- WebView assets stay copyable into the bundle without a build step,
  which simplifies packaging.

Testing and CI:

- Existing smoke catalog
  (`Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`) continues to be the
  truth source for behavior coverage.

Migration cost:

- None now. Future migration will be bounded by the trigger ADR.

Reversibility:

- High — deferral is reversible by writing 0012.

## Alternatives considered

**Pick Lit now.** Component encapsulation is genuinely valuable, but
the cost of converting current panels is large and the pain is not
yet acute. Premature.

**Pick Preact now.** Same objection. Plus Preact + JSX would
introduce a build step.

**Pick neither, ban the question.** Worse than deferring; future-pain
data does accumulate, and the team should be allowed to revisit when
the pain is concrete.

## Validation

- ADR remains in `deferred` status until 0012 is written.
- No frontend `package.json`, no new framework imports in
  `ui_web/static/`, no CDN script tags pointing at framework URLs.
