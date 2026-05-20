# WebView Operator Copy Consistency Audit

Purpose: audit operator-facing text patterns in the WebView JavaScript assets for consistency, identify established vocabulary, and note any divergences that could confuse operators or future contributors. This is an observational document.

All findings are derived from grepping across the 31 JS asset files in `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/`.

---

## Established Patterns (Consistent — Follow These)

### "Mutation guardrail:" prefix

The phrase "Mutation guardrail:" is the standard header for any text that explains what a WebView panel cannot do. It appears in over 20 locations across view files. All instances use the exact prefix followed by a declarative list of prohibited actions.

**Pattern**: `Mutation guardrail: [panel name/context] is read-only; it does not [action 1], [action 2], or [action n].`

**Examples**:
- `"Mutation guardrail: this checklist is read-only and does not launch, repair, drain, save, rename, delete, publish, or touch media files."`
- `"Mutation guardrail: this Launch timing panel is read-only; it does not bypass backend launch locks, schedule gates, or settings validation."`
- `"Mutation guardrail: WebView Maintenance remains dry-run only; it must not write release packages, rewrite completed manifests, repair files, or mutate media."`

**Verdict**: Consistent. New panels that add non-mutation guardrail text must use this prefix.

### "read-only" (hyphenated)

All operator-facing uses of this adjective are hyphenated. The unhyphenated form "read only" does not appear in operator-facing text.

**Verdict**: Consistent. Use "read-only" in all new copy.

### "backend-owned" (hyphenated)

All operator-facing uses of this adjective are hyphenated. Variants follow the same hyphenation convention: "backend-selected," "backend-allowlisted," "backend-authored."

**Verdict**: Consistent. Use "backend-owned" and its variants with a hyphen in new copy.

### "Do not drain" (sentence case)

The drain safety block always uses sentence case "Do not drain" when displayed as a status message or heading, and lowercase "do not drain" when used as a status token in code comparisons. The distinction is consistent across `pendingPublishView.js`, `completedView.js`, `commandHistory.js`, and `crossPageContextView.js`.

**Verdict**: Consistent. Use "Do not drain" (sentence case) in operator-visible messages. Reserve lowercase for internal token comparisons.

### Risk level vocabulary

The status / readiness system uses these severity labels in order of severity:

1. `"Critical risk"` — highest severity; blocks launch
2. `"High risk"` — review required before proceeding
3. `"Review"` — advisory; operator attention needed
4. `"Warning"` — non-blocking informational alert (used in telemetry context)
5. `"Ready"` — all checks passed

The word "danger" does not appear as a status label in any operator-facing text.

**Verdict**: Use the five labels above. Do not introduce "danger," "error" (for severity labels), or "fail" in operator-facing status strings — these are for internal severity tokens, not display labels.

### Action verb for starting work

The system uses "start" as the verb for initiating pipeline/audit/rerun operations, not "launch pipeline" or "process media." Examples: "Start pipeline mode," "Start audit?", "Start CSV rerun," "start pipeline work."

**Verdict**: Use "start" as the verb. Reserve "launch" for the Launch page noun ("the Launch page," "launch evidence") and for internal route references (`/api/pipeline/start`).

---

## The One Intentional Distinction: "Save Patch" vs "save settings"

Two phrases are used for the settings-save operation:

**"Save Patch"** (title case, two words):
- Used when referring to the named feature or the backend action: "Use Preview Patch, then Save Patch," "backend Save Patch succeeds."
- Appears in settings workflow guidance and launch decision checklists.

**"save settings"** (lowercase):
- Used in guardrail lists enumerating prohibited actions: "cannot start, retry, drain, save settings, rewrite queue state, or touch files."
- Appears in mutation guardrail statements where brevity matters.

This distinction is intentional: "Save Patch" is the feature name; "save settings" is the layperson description used alongside other prohibited actions in guardrail lists where the technical name would be verbose.

**Rule**: Use "Save Patch" (title case) when describing the two-step workflow ("Preview Patch → Save Patch"). Use "save settings" (lowercase) in guardrail enumeration lists where it appears alongside "rename," "drain," "launch," etc.

---

## Patterns Not Found (Do Not Introduce)

The following terms do not appear in current operator-facing text. Adding them would create inconsistency:

| Absent term | Use instead |
|---|---|
| "danger" (as a label) | "Critical risk" or "High risk" |
| "launch pipeline" | "start pipeline" |
| "process media" | "start pipeline" or "pipeline work" |
| "save-patch" (hyphenated) in displayed text | "Save Patch" (title case, spaced) |
| "read only" (unhyphenated) | "read-only" |
| "backend owned" (unhyphenated) | "backend-owned" |
| "Invoke-Expression" reference in UI copy | (prohibited) |
| First-person "I" or "we" | Use second person ("you") or passive construction |

---

## Minor Inconsistencies (Low Impact)

### "launch" vs "start" in cross-context references

In launch decision checkpoints and preflight guidance, the text occasionally uses "launch" as a verb when referring to the pipeline start action (e.g., "backend-owned launch locks"). This usage is consistent within the Launch page context but differs from the "start" verb used in button labels. The distinction maps cleanly to UX context (the page is called "Launch," but the action verb in button text is "Start"), so this is not a bug.

### Confirm dialog phrasing

The three `window.confirm()` dialogs use slightly different formats:
- "Start pipeline mode: [label]?" — modal question with context
- "Start audit?" — shorter form
- "Start CSV rerun with copy / keep / park policy?" — longer form with policy detail

These three forms all use "Start" as the verb and end with "?" — the length difference is appropriate to the complexity of each action.

### "warning" vs "Warning" in telemetry

Telemetry alerts use "Telemetry warning:" and "Warning:" (sentence case in headings) while readiness status uses lowercase `"warning"` as a severity token. The same title-vs-token distinction as "Do not drain" — intentional, not a bug.

---

## Copy Rules For New Panels

When adding operator-facing text to a new or existing WebView panel:

1. Add a "Mutation guardrail:" statement if the panel has any inputs or buttons that could be mistaken for mutation controls.
2. Use "read-only" (hyphenated) when describing a panel's non-mutation posture.
3. Use "backend-owned" for routes, buttons, and data that originate from the backend.
4. Use "Do not drain" (sentence case) for blocking drain safety messages.
5. Use the five risk labels (Critical risk / High risk / Review / Warning / Ready) for status displays.
6. Use "start" as the action verb for pipeline/audit/rerun operations.
7. Use "Save Patch" in workflow descriptions; use "save settings" in guardrail lists.

---

## See Also

- DOM ID naming convention: `WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`
- Route ownership and mutation risk: `LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Smoke tests that verify guardrail text: `WEBVIEW_SMOKE_TEST_CATALOG.md`
