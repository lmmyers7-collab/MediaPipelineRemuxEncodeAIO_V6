# Stale Schedule Read-Only Wording Audit

Date: 2026-05-14

Searches documentation and WebView assets for wording that incorrectly implies the WebView Schedule page has no editor, or that Schedule is entirely read-only, after the backend-owned Schedule Editor was added.

---

## Search Scope

Files inspected:
- `Docs\*.md`
- `DesktopApp\tauri_shell\README.md`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js`

Search patterns used:
- `"no WebView schedule editor"`
- `"read-only Schedule"`
- `"Schedule page is read-only"`
- `"until backend save contract"`

---

## Findings

### Stale Phrases Found: None

No matches for any of the four search patterns were found in the active docs or WebView assets.

The two matches found in `REMEDIATION_CHANGELOG.md` are historical changelog entries documenting what was *added*:

| File | Line | Text | Assessment |
|---|---|---|---|
| `REMEDIATION_CHANGELOG.md` | ~476 | "Added a read-only Schedule Coverage Review panel..." | Historical — accurately describes the coverage panel as read-only evidence (correct). The editor was added later and is documented separately. |
| `REMEDIATION_CHANGELOG.md` | ~23045 | "Added a read-only Schedule Timing Trust panel..." | Historical — the timing trust panel IS read-only and correctly described as such. |

These are not stale — they accurately describe read-only sub-panels within the Schedule page, which remain read-only even after the editor was added.

---

## Schedule Page Current State (From scheduleView.js)

The `scheduleView.js` code confirms the Schedule editor is implemented:
- `scheduleEditorDirty` variable tracks editor state
- `lastScheduleEditorResult` stores the last save/preview result
- The editor handles day-window staging and routes to `/api/schedule/preview` and `/api/schedule/save`
- The continuous watcher detail lines include: `"Mutation guardrail: Schedule and Launch views only display watcher state; they cannot directly write stop flags or start work."` — this correctly reflects that stop-watcher control remains backend-only.

---

## Acceptance Criteria Status

| Criterion | Status |
|---|---|
| "It is still okay to say 'coverage detail is evidence-only.'" | Pass — coverage panels are correctly described as read-only evidence |
| "It is not okay to say 'no WebView schedule editor' unless clearly historical." | Pass — no active docs use this phrase |
| "It must still say WebView does not own continuous schedule-stop watcher behavior." | Pass — scheduleView.js guardrail text states this clearly |

---

## Conclusion

No stale wording found. Schedule documentation correctly reflects the current state:
- Coverage and timing trust panels are read-only evidence
- The Schedule Editor exists and is backend-owned (preview/save routing)
- The continuous watcher cannot be written from WebView

No documentation changes are required.

---

## Task Output

```
Task ID: CLN-003
Files inspected: Docs\*.md (grep), DesktopApp\tauri_shell\README.md, DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js
Files changed: Docs\SCHEDULE_STALE_READONLY_WORDING_AUDIT.md (created)
Validation: Grep search for all four patterns. Zero active-doc matches.
Findings: No stale Schedule read-only wording found. Changelog entries are historical and accurate.
Open questions: None.
Risk: Low — documentation only.
```
