# Tauri Preview Vs Daily Driver Wording Audit

Date: 2026-05-14

Checks whether documentation overstates Tauri/WebView2 readiness or implies the CustomTkinter fallback can be retired. Source files inspected: `Docs\TLDR.md`, `Docs\V5_TRANSITION_STATUS_BOARD.md`, `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`.

This document does not change any wording. It confirms the current state is correct.

---

## Summary

No stale "daily driver" or "production replacement" wording was found in active docs. All inspected files correctly describe Tauri/WebView2 as a preview path, and Tk as the current supported operator UI.

---

## TLDR.md

**Checked phrase**: "The supported operator UI is still `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat`. The Tauri/WebView2 shell is an explicit preview path for the V5 transition work and should not replace the current app yet."

**Assessment**: Correct. "Explicit preview path" is appropriately cautious. "Should not replace the current app yet" explicitly guards against daily-driver overreach.

---

## V5_TRANSITION_STATUS_BOARD.md

| Item | Documented Status | Assessment |
|---|---|---|
| `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` | **Stable fallback** | Correctly the primary production reference |
| CustomTkinter controllers / views | **Stable fallback** | Correctly preserved and not weakened |
| V4 backup workspace | **Stable fallback** | Correct; untouched known-good |
| Basic Tauri/WebView2 shell | **Preview** | Correctly limited to preview |
| Production daily-driver use | **Not started** | Explicitly blocked: "Needs real-media validation pass before daily-driver trust" |

**Assessment**: All statuses are correct. "Not started" for production daily-driver use, with an explicit validation gate, is the correct gate language.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| WebView/Tauri is described as preview or partial parity | Pass — "Preview" throughout |
| Tk fallback remains default/trusted | Pass — "Stable fallback" in status board; "supported operator UI" in TLDR |
| Daily-driver language includes validation caveats | Pass — daily-driver use is "Not started" with explicit validation gate |
| No doc implies Tk can be retired now | Pass — no such language found in inspected files |

---

## Files Inspected

- `Docs\TLDR.md`: Tauri described as "explicit preview path"
- `Docs\V5_TRANSITION_STATUS_BOARD.md`: Tauri shell "Preview"; daily-driver use "Not started"
- `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`: Parity matrix documents gaps; does not imply full parity

---

## Conclusion

No wording changes needed. Documentation correctly separates preview from daily-driver readiness and maintains explicit guardrails around Tk fallback primacy.

---

## Freshness Review — 2026-05-15 (CLN2-06)

Extended scope to include `DesktopApp\tauri_shell\README.md`. All five docs remain accurate.

| File | Key phrase | Status |
|---|---|---|
| `TLDR.md` | "Explicit preview path... should not replace the current app yet" | Pass |
| `V5_TRANSITION_STATUS_BOARD.md` | Tauri shell: **Preview**; production daily-driver: **Not started** | Pass |
| `TAURI_WEBVIEW_PARITY_MATRIX.md` | "Tk remains the supported fallback" | Pass |
| `TAURI_DAILY_DRIVER_WORDING_AUDIT.md` | Prior CLN-019 audit confirmed no stale phrases | Pass |
| `DesktopApp\tauri_shell\README.md` | "It is not the production UI yet… Tk should remain the daily-use UI until the preview completes parity…" | Pass |

No wording corrections needed. All docs continue to use `preview`, `fallback`, `supported operator UI`, and `real-media validation required` in the appropriate positions.

---

## Task Output

```
Task ID: CLN-019
Files inspected: Docs\TLDR.md, Docs\V5_TRANSITION_STATUS_BOARD.md, Docs\TAURI_WEBVIEW_PARITY_MATRIX.md
Files changed: Docs\TAURI_DAILY_DRIVER_WORDING_AUDIT.md (created)
Validation: Inspected key phrases in each doc. Cross-referenced status table entries.
Findings: No stale or overreaching wording found. All three files use correct preview/fallback language.
Open questions: None.
Risk: Low — documentation only.
```
