# Operator Copy Vocabulary Consistency Review

Date: 2026-05-14

Reviews operator-facing text in WebView JavaScript assets and docs against the established vocabulary documented in `Docs\WEBVIEW_OPERATOR_COPY_AUDIT.md`. Source: full audit of the copy audit findings; cross-reference with TERMINOLOGY_CONSISTENCY_GUIDE.md.

This is an observational document. It does not propose mass edits.

---

## Established Vocabulary Status

All established vocabulary patterns from `WEBVIEW_OPERATOR_COPY_AUDIT.md` are confirmed consistent.

| Pattern | Status | Rule |
|---|---|---|
| `"Mutation guardrail:"` prefix | Consistent — 20+ locations | All read-only panels that could be mistaken for mutation controls use this prefix |
| `"read-only"` (hyphenated) | Consistent | Unhyphenated "read only" does not appear in operator-facing text |
| `"backend-owned"` (hyphenated) | Consistent | "backend owned" (unhyphenated) does not appear in operator-facing text |
| `"Do not drain"` (sentence case) | Consistent | Lowercase form used only in internal token comparisons, not display |
| Risk labels: Critical risk / High risk / Review / Warning / Ready | Consistent | "danger" does not appear as a status label |
| `"start"` as action verb | Consistent | "launch pipeline" and "process media" do not appear as action verbs |
| `"Save Patch"` (title case in workflow) | Consistent | "save-patch" (hyphenated) does not appear in displayed text |
| `"save settings"` (lowercase in guardrail lists) | Consistent | Intentional distinction from "Save Patch" feature name |

---

## Known Intentional Distinctions (Not Inconsistencies)

The following apparent variations are documented as intentional in `WEBVIEW_OPERATOR_COPY_AUDIT.md`:

### "launch" vs "start" in cross-context references

"launch" appears as a noun ("the Launch page," "launch evidence," "backend-owned launch locks") while "start" is the action verb ("start pipeline work," "Start pipeline mode"). This maps cleanly to the Launch page noun vs button action verb and is correct.

### Confirm dialog phrasing variations

Three `window.confirm()` dialogs exist with different lengths:
- "Start pipeline mode: [label]?" — context-length
- "Start audit?" — short
- "Start CSV rerun with copy / keep / park policy?" — full policy detail

All use "Start" and end with "?". The length difference is appropriate to action complexity.

### "warning" vs "Warning" in telemetry

Telemetry alerts use "Telemetry warning:" (heading) while the readiness status system uses lowercase `"warning"` as a severity token. The title-vs-token distinction mirrors the same pattern as "Do not drain" / "do not drain".

---

## Terms Confirmed Absent (Must Not Be Introduced)

The following terms do not appear in current operator-facing text and must not be introduced:

| Absent term | Use instead |
|---|---|
| `"danger"` (as a label) | `"Critical risk"` or `"High risk"` |
| `"launch pipeline"` (as action verb) | `"start pipeline"` |
| `"process media"` | `"start pipeline"` or `"pipeline work"` |
| `"save-patch"` (hyphenated in display) | `"Save Patch"` (title case, spaced) |
| `"read only"` (unhyphenated) | `"read-only"` |
| `"backend owned"` (unhyphenated) | `"backend-owned"` |
| First-person `"I"` or `"we"` | Second person or passive construction |

---

## Docs Vocabulary Cross-Check

The TERMINOLOGY_CONSISTENCY_GUIDE.md documents preferred terms for docs copy alongside the established JS patterns. No cross-cutting inconsistencies found between JS copy and docs wording in the inspected files.

---

## New Panel Copy Rules (For Reference)

When adding operator-facing text to a new or existing WebView panel, apply in order:

1. Add `"Mutation guardrail:"` if any input could be mistaken for a mutation control
2. Use `"read-only"` (hyphenated) for non-mutation posture description
3. Use `"backend-owned"` for routes, buttons, and data originating from backend
4. Use `"Do not drain"` (sentence case) for blocking drain safety messages
5. Use the five risk labels (Critical risk / High risk / Review / Warning / Ready) for status displays
6. Use `"start"` as the action verb for pipeline/audit/rerun operations
7. Use `"Save Patch"` in workflow descriptions; use `"save settings"` in guardrail enumeration lists

---

## Conclusion

No inconsistencies found. The established vocabulary from `WEBVIEW_OPERATOR_COPY_AUDIT.md` is uniformly applied in the WebView JS assets. Docs copy does not introduce conflicting terms.

No wording changes are recommended at this time.

---

## Task Output

```
Task ID: CLN-026
Files inspected: Docs\WEBVIEW_OPERATOR_COPY_AUDIT.md, Docs\TERMINOLOGY_CONSISTENCY_GUIDE.md
Files changed: Docs\OPERATOR_COPY_CONSISTENCY_REVIEW.md (created)
Validation: Reviewed all established patterns and absent-terms tables. Cross-referenced with TERMINOLOGY_CONSISTENCY_GUIDE.md.
Findings: All patterns consistent. Three intentional distinctions documented (launch/start, confirm phrasing, warning casing). No forbidden terms found.
Open questions: None.
Risk: Low — documentation only.
```
