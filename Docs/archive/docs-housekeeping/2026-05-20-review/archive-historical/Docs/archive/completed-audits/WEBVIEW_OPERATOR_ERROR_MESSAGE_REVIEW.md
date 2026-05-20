# WebView Operator Error Message Review

Date: 2026-05-14

Classifies the operator-facing warning, error, and status strings found in WebView JavaScript modules. Each entry states where the string appears, its message class, and an assessment of whether the next-action wording is clear and actionable. Source: JS files under `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/`.

---

## Message Classes

| Class | Meaning |
|---|---|
| `guardrail` | Mutation guardrail statement — explains what this panel does NOT do |
| `status` | State label — describes current system state without prescribing action |
| `warning` | Operator caution — identifies a condition that needs attention before proceeding |
| `error` | Blocking condition — something has failed or is preventing an action |
| `instruction` | Operator guidance — prescribes a next step |
| `confirmation` | Confirmation label — reflects a completed or safe state |

---

## Mutation Guardrail Strings

Mutation guardrails are displayed in read-only panels to explicitly document what the panel cannot do. The standard verbatim phrase is defined in `commandHistory.js`.

| String | Module | Assessment |
|---|---|---|
| `"Mutation guardrail: this checklist cannot retry, launch, drain, save, rename, repair, delete, publish, open arbitrary paths, or bypass backend validation."` | `commandHistory.js` | **Standard verbatim phrase** — do not paraphrase. Per `Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md`. |
| `"Mutation guardrail: this checklist is read-only and does not launch, repair, drain, save, rename, delete, publish, or touch media files."` | Multiple | Clear and consistent. Minor wording variant from standard phrase — acceptable in non-command-journal panels. |
| `"Mutation guardrail: filters are display-only and never change backend command scope."` | `queueView.js`, `pendingPublishView.js`, `completedView.js` | Clear. Reinforces that display filters are not processing filters. |
| `"Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control and backend locks remain the source of truth."` | `launchView.js` | Clear. Correctly attributes authority to backend. |
| `"Mutation guardrail: this Launch timing panel is read-only; it does not bypass backend launch locks, schedule gates, or settings validation."` | `launchView.js` | Clear. |
| `"Mutation guardrail: queue mutation and processing start remain backend-owned commands; this page is read-only."` | `queueView.js` | Clear. |
| `"Mutation guardrail: WebView controls must use backend-owned routes from this contract; no frontend filesystem mutation or process control belongs here."` | `contractView.js` | Acceptable for engineering audience; not operator-facing in daily use. |
| `"Mutation guardrail: this workflow panel is read-only. Launch commands remain backend-owned."` | Various | Clear. |
| `"Mutation guardrail: Queue only reads the cached backend preflight payload; it cannot reserve locks, clear flags, save settings, or start work."` | `queueView.js` | Clear. |
| `"Daily-driver checklist rows are read-only and do not launch, repair, drain, save, rename, or mutate files."` | `crossPageContextView.js` | Class: `guardrail`. Slightly different phrasing but semantically consistent. |

**Assessment**: Guardrail strings are consistently formatted and use the correct vocabulary. The standard verbatim phrase in `commandHistory.js` should not be shortened. Other panels may use condensed variants with "launch, drain, save, rename, delete, publish" scope lists.

---

## Close Readiness and Lifecycle Status Strings

| String | Module | Class | Assessment |
|---|---|---|---|
| `"Close: safe"` | `app.js` | `status` | Clear. Short enough for a compact indicator. |
| `"Close: active work"` | `app.js` | `status` | Clear. Indicates pipeline is running. |
| `"Safe to close: yes"` / `"Safe to close: no"` | `app.js` | `status` | Clear pair. Binary state is easy to scan. |
| `"Close readiness has not loaded yet."` | `app.js` | `warning` | Clear. Operator knows to wait. **Next action missing**: consider adding "Wait for next refresh." |
| `"Close-readiness: unknown"` | `app.js` | `status` | Acceptable. Covers the case where the status read failed. |
| `"Do not close unless intentionally interrupting active work. Check Home progress, ActiveJobs, and Run Logs."` | `app.js` | `instruction` | Clear. Names specific panels to check. Good specificity. |
| `"Disabled until close-readiness reports safe."` | `app.js` | `status` | Clear button title. Operator understands the condition. |
| `"Request backend-owned graceful shutdown. This is enabled only because close-readiness reports safe."` | `app.js` | `instruction` | Clear. Accurately attributes the enabling condition. |
| `"Active work, stale runtime state, or unverifiable close-readiness is blocking shutdown."` | `app.js` | `error` | **Improvement opportunity**: this string lists three possible causes without indicating which one applies. Consider splitting into cause-specific messages. |

---

## Queue and Launch Status Strings

| String | Module | Class | Assessment |
|---|---|---|---|
| `"Blocked review"` | `queueView.js` | `status` | Clear status label for rows with blocked conditions. |
| `"Review rows"` | `queueView.js` | `instruction` | Clear. Implies there are rows requiring operator attention. |
| `"Do not launch from an empty queue. Check Source settings, Completed, schedule state, and Run Logs first."` | `launchView.js` | `instruction` | Good specificity. Names all relevant panels. |
| `"This row is read-only and cannot start queued work."` | `queueView.js` | `guardrail` | Clear. |
| `"Open Queue and Diagnostics; queue payload reported an error."` | `queueView.js` | `error` | Clear. Names specific next panels. |
| `"Settings decision: launch should remain blocked until Settings validation/risk is clean."` | `launchView.js` | `warning` | Clear. Accurately attributes the decision to Settings state. |
| `"Settings decision: saved settings do not add a timing block; backend validation still has final authority."` | `launchView.js` | `confirmation` | Clear. Correctly qualifies that backend validation is still the authority. |
| `"Run Once and Continuous are schedule-blocked unless a deliberate override is selected."` | `launchView.js` | `warning` | Clear. Explains the schedule gate. |

---

## Filter Visibility and Scope Strings

| String | Module | Class | Assessment |
|---|---|---|---|
| `"Operator note: clear or change this filter before [decision] decisions; blocked/warning rows are currently hidden."` | `queueView.js`, `completedView.js`, `pendingPublishView.js` | `warning` | Clear. The `[decision]` placeholder should be filled with the specific action (e.g., "launch", "drain", "rerun"). **Verify all callers fill this placeholder correctly.** |
| `"Operator note: this filter is not hiding blocked/warning rows in the loaded payload."` | Multiple | `status` | Clear. Reassures operator that visible rows are not being suppressed. |
| `"Active display filters do not change backend drain scope."` | `pendingPublishView.js` | `guardrail` | Clear. Uses correct terminology ("backend drain scope"). |
| `"Active display filters do not change backend launch scope."` | `queueView.js` | `guardrail` | Clear. |

---

## Diagnostics and Refresh Failure Strings

| String | Module | Class | Assessment |
|---|---|---|---|
| `"Refresh the page or open Diagnostics; required backend read failed: [name]."` | Multiple | `error` | Clear. Names next actions. `[name]` should be filled with the failing route name — **verify callers pass the route name**. |
| `"Core snapshot is available, but one or more supporting panels failed. Use Diagnostics for the failed read(s)."` | Multiple | `warning` | Clear. Distinguishes degraded state from total failure. |
| `"Use Diagnostics for supporting read issues; avoid unattended runs until important panels refresh cleanly."` | Multiple | `instruction` | Clear. Prescribes safe action (don't run unattended). |

---

## Pending Publish and Drain Guard Strings

| String | Module | Class | Assessment |
|---|---|---|---|
| `"Do not drain."` / `"Do not drain until [condition]."` | `pendingPublishView.js` | `warning` | Clear. The condition fill-in is key — **verify all callers supply a specific condition**. |
| `"Publish Button Guard: blocked."` | `pendingPublishView.js` | `status` | Clear. The "Guard" terminology is consistent with the mutation guardrail vocabulary. |
| `"Blocked clicks append local frontend_guard evidence without posting /api/pipeline/start."` | `pendingPublishView.js` | `guardrail` | Acceptable for engineering context. May be too technical for daily-operator use. |
| `"Recovery dry-run required before drain."` | `pendingPublishView.js` | `instruction` | Clear. Prescribes a specific prior step. |

---

## Settings and Rename Strings

| String | Module | Class | Assessment |
|---|---|---|---|
| `"Apply Readiness"` | `renameView.js` | `status` | Clear label for the rename readiness ledger. |
| `"Blocked: two selected files would produce the same destination."` | `renameView.js` | `error` | Clear. Names the exact cause of the block. |
| `"Save cancelled"` | `settingsView.js` | `confirmation` | Clear. Appears in command history after an operator cancels save. |
| `"Save Patch is not posted by the browser smoke."` | `settingsView.js` | `guardrail` | Engineering/smoke context only. Not operator-facing in daily use. |

---

## Strings Needing Improvement

| String | Issue | Recommendation |
|---|---|---|
| `"Active work, stale runtime state, or unverifiable close-readiness is blocking shutdown."` | Three possible causes; unclear which applies | Split into cause-specific messages or add a secondary diagnostic field |
| `"Operator note: clear or change this filter before [decision] decisions..."` | `[decision]` placeholder — verify all callers fill this | Audit callers in `queueView.js`, `completedView.js`, `pendingPublishView.js` |
| `"Refresh the page or open Diagnostics; required backend read failed: [name]."` | `[name]` placeholder — verify all callers supply the route name | Audit callers to confirm route name is passed |
| `"Do not drain until [condition]."` | `[condition]` fill-in — verify all callers supply a specific condition | Audit callers in `pendingPublishView.js` |
| `"Blocked clicks append local frontend_guard evidence without posting /api/pipeline/start."` | Too technical for operators unfamiliar with internals | Consider whether this is shown to operators or only in dev tools / command history |
| `"Close readiness has not loaded yet."` | No next action given | Add: "Wait for the next refresh before closing the app." |

---

## Vocabulary Compliance

All strings reviewed were checked against `Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md`. No violations of preferred vocabulary found in the strings above. Key observations:

- All strings use "drain" for the pending publish operation (not "send" or "publish" alone).
- All strings use "display filters" or "display-only" when referring to table filter controls.
- All strings use "backend-owned" or "backend launch scope" correctly.
- "Mutation guardrail" is used consistently and is not paraphrased in operator-facing contexts.

---

## See Also

- Terminology guide: `Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md`
- Mutation boundary review: `Docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- DOM ID inventory: `Docs/WEBVIEW_DOM_ID_INVENTORY.md`
- Manual operator test script: `Docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`
