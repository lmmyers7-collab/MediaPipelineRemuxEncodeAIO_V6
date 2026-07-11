# General-Public Usability Review

Review date: 2026-07-09  
Application: 2026.06.04.001, commit `c5519e6ae`  
Environment: Windows Tauri development preview with Local API running at `127.0.0.1:52654`; review-only, no application, configuration, runtime, or media state was changed.

## Scope, assignments, and limitations

| Tab              | Assigned review worker  | Evidence status                                                                               |
| ---------------- | ----------------------- | --------------------------------------------------------------------------------------------- |
| Home             | Home worker             | Static/source-confirmed; direct page observation also captured an expired-session error state |
| Launch           | Launch worker           | Static/source-confirmed                                                                       |
| Telemetry        | Telemetry worker        | Static/source-confirmed                                                                       |
| Metrics          | Metrics worker          | Static/source-confirmed; non-mutating degraded-state smoke passed                             |
| Queue            | Queue worker            | Static/source-confirmed                                                                       |
| Completed Output | Completed Output worker | Not assessed: no attachable browser surface                                                   |
| Pending Publish  | Pending Publish worker  | Static semantic review; browser bridge timed out                                              |
| Rename           | Rename worker           | Static/source-confirmed                                                                       |
| Reports          | Reports worker          | Static/source-confirmed                                                                       |
| Network Workers  | Network Workers worker  | Static/source-confirmed                                                                       |
| Libraries        | Libraries worker        | Static/source-confirmed                                                                       |
| Schedule         | Schedule worker         | Static/source-confirmed                                                                       |
| Settings         | Settings worker         | Static/source-confirmed                                                                       |
| Diagnostics      | Diagnostics worker      | Static/source-confirmed                                                                       |
| Maintenance      | Maintenance worker      | Static/source-confirmed                                                                       |

The Tauri preview and Local API were running. A direct localhost browser session rendered the shell and Home page, but it did not inherit the desktop bootstrap session and received `HTTP 401: Session expired while loading backend snapshot`. Other workers could not obtain or maintain an attachable browser surface. Therefore desktop/narrow screenshots, live focus traversal, contrast, screen-reader output, loading/error transitions, and real command dialogs are **not verified** except for that observed expired-session state. Findings below are source-confirmed interface/interaction risks, not assertions about unobserved backend behavior. Re-run this review in an authenticated desktop session after fixes.

## Executive summary

The application has a strong backend-owned safety model, but its operator surface assumes substantial media-pipeline and engineering knowledge. A first-time home user is routinely shown implementation evidence, raw JSON/paths, developer tooling, or dense tables before a clear answer to: “What is this page for?”, “What should I do next?”, and “Will this change my original files?”

The greatest risks are not source-media mutation defects. They are unsafe comprehension failures: a user can misunderstand a replacement-oriented CSV rerun, approve unseen rename rows, choose the wrong save path in Guided Setup, or lose recovery time in Diagnostics/Reports. Accessibility also needs focused work: nested interactive controls, incomplete tab/listbox models, canvas-only trends, hundreds of schedule keyboard stops, and wide tables that rely on horizontal scrolling.

## Top 10 prioritized recommendations

1. **P1 — Make CSV rerun safe and intelligible by default.** Change Queue's replacement-oriented default to a non-replacing review path; name the exact final-output impact and put replacement in Advanced.
2. **P1 — Do not auto-select rename rows a user cannot review.** For previews beyond 250 rows, leave unseen rows unselected or require an explicit expanded full-scope acknowledgement before apply.
3. **P1 — Give Guided Setup one save path.** Suppress or redirect the global Settings save action while the wizard is active; use the wizard's reviewed save path only.
4. **P1 — Make first launch understandable.** Show a backend-derived start summary beside Launch's CTA: selected scope/count, readiness, what happens next, and that sources remain read-only.
5. **IGNORE
6. **P1 IGNORE
7. **P1 — Separate public recovery from developer tooling.** Remove or clearly isolate Diagnostics Tdarr proof packs, Maintenance release/dependency tools, and similar engineering workflows from normal operator routes.
8. **P1 — Make Reports task-oriented.** Default to review results, separate audit execution and policy administration, and introduce a real narrow-table detail pattern.
9. **P1 — Simplify Libraries and Settings setup.** Lead with a purpose and one next action; replace patches/PSD1/encoder jargon with outcome language and postpone advanced choices until compatible hardware has been detected.
10. **P1 — Protect personal configuration in package creation.** Move “Keep personal config” into Advanced and relabel it “Include private personal configuration — do not share this package.”

## Tab findings

### Home

- **P2 — Ambiguous first action.** `Quick Controls > Start / Launch` does not visibly say it opens a readiness review rather than immediately starting work. Rename it to “Review & start processing” and state that originals remain unchanged.
- **P2 — Routine readiness is hidden as Advanced evidence.** A compact normal-mode health banner should show Ready/Needs attention/Can't refresh and one next step.
- **P2 — Selection and status feedback are weak.** Next Queue and Recently Completed invite row selection but do not visibly expose enough resulting detail; zero Pending/Failed counts can look healthy before data loads.
- **P2 — Listbox semantics do not match keyboard behavior.** Next 5 Videos declares a listbox but supports only Tab plus Enter/Space, not expected arrow-key movement.

### Launch

- **P1 — Start lacks a plain-language scope and safety summary.** `Start Run Once` posts the start command after technical readiness gates, without clearly naming the selected queue/count or source-read-only protection.
- **P2 — Readiness is overly dense.** Ten status/gate objects precede the main action; lead with one overall state and recommended recovery action.
- **P2 — Tab semantics are incomplete.** `Pipeline Processor`/`History` lack linked tabpanels and standard arrow/Home/End behavior.
- **P2 — Validate is underspecified.** Present it as “Check setup only — does not process media,” with an explicit selected-mode state.

### Telemetry

- **P1 — Trend charts lack an equivalent accessible data view.** CPU, encoder, and RAM history is canvas-only beyond a generic image label; add concise trends and an expandable data list/table.
- **P1 — GPU Details becomes a wide horizontal-scroll table at narrow widths.** Use compact cards or an explicitly focusable, instructed scroll region.
- **P2 — Specialist labels obscure health.** Lead with plain-language health (“graphics card is the limit”) before NVENC/GPU-bound terminology, and make recovery destinations direct actions.

### Metrics

- **P2 — Purpose and first-run state are unclear.** Introduce Metrics as a read-only history view and explain that it becomes useful after completed jobs exist.
- **P2 — Raw authority/path/cache evidence is visible by default.** Replace with a human-readable freshness/coverage summary and disclose technical evidence.
- **P2 — Attention rows are not actionable.** Turn the Subtab cell into “View [area] details,” moving focus to the relevant panel.
- **P2 — Backfill controls lack scope/safety explanation.** Say that they read history only, never alter media, and show understandable result/progress feedback.

### Queue

- **P1 — CSV rerun defaults imply replacement.** The default handling includes final-output replacement language beside `Review & Start`; use a non-replacing default and plainly distinguish final outputs from source media.
- **P2 — Core recovery content is buried.** Many sequential evidence panels obscure “what needs attention / what do I do next?” after a scan.
- **P2 — File override entry is cryptic.** An icon-only gear opens advanced route, codec, subtitle, and language controls; label it “File overrides,” explain scope, and show a plain-language save summary.
- **P2 — Main and rerun-state tables remain wide on narrow displays.** Reuse the existing stacked-preview pattern for core rows.

### Completed Output

Not assessed. The assigned worker could not attach to a live application surface, and source-only inference was deliberately not substituted. Revisit normal, empty, final-placement, error, keyboard, and narrow states in the authenticated desktop shell.

### Pending Publish

- **P1 — Nested interactive controls in the action center.** `Pending Publish Operations` is an element with `role=button` and `tabindex=0` containing three native buttons. Make the container noninteractive and retain only native action controls.
- **P2 — Potential duplicate drain affordances.** The action center routes to a second progress-panel drain control. Validate live whether the two labels/scope cues confuse cautious users before changing it.

### Rename

- **P1 — Check Applicable can select unrendered rows.** The table limits rendering to 250 rows but selection/apply operates over the complete preview. Do not select unseen rows without a clear full-scope review/acknowledgement.
- **P2 — The safe naming decision is buried in technical evidence.** Keep selected count, warnings, source-to-name comparison, and next action visible; disclose review board, handoff, and technical proof.
- **P2 — Sidecar/pipeline controls are jargon-heavy.** “Rename sidecar preview” and “Force pipeline name preview” need outcome language and advanced placement for force behavior.
- **P2 — Keyboard users reach a non-operable drop zone.** Either remove it from tab order or provide an equivalent browse action.

### Reports

- **P1 — Audit combines review, execution, and policy administration.** Split default “Review results” from “Run an audit” and Advanced “Audit policy.”
- **P1 — Failure/Audit tables are desktop-width at narrow sizes.** Implement cards or summary-plus-details instead of relying only on horizontal scroll.
- **P2 — Tabs and audit setup have avoidable interaction failures.** Complete ARIA tabs behavior; make a typed audit location easy to add-and-select before Start.
- **P2 — Evidence-clearing operations need a separate visible dry-run review step.** Reuse existing backend confirmation/fingerprint protection, but show item count/scope before the confirm action.

### Network Workers

- **P1 — Normal setup exposes JSON and a backend-disabled override.** Move encoder mapping to Advanced/hardware compatibility and render unavailable overrides as explanatory read-only content.
- **P2 — Readiness details are hover-only chips.** Expand TCP/Auth labels and provide visible, keyboard-accessible failure reasons and next steps.
- **P2 — Workflow continuity and narrow triage need work.** Rename the mixed `Needs Attention` filter, link Network CSV Rerun to Queue's controls, and provide a compact Worker Board view.

### Libraries

- **P1 — No clear purpose or first safe action.** Profile navigation, scan, and seven configuration actions arrive without “Start here” guidance. Explain scan as inventory refresh only.
- **P1 — Patch/stage/save vocabulary is confusing and inconsistent.** Replace with “Review changes” and “Save changes”; show whether edits are unsaved or saved just now.
- **P2 — Automation and route-map complexity need progressive disclosure.** Explain what auto-run will do before enabling it, and collapse the large route map into Advanced diagnostics.

### Schedule

- **P1 — The editor creates 336 keyboard stops.** The seven 48-cell day rails require an accessible start/end range editor as the primary interaction.
- **P1 — The grid is not responsive.** Replace the horizontal 48-column rail with day cards/range fields at narrow widths.
- **P1 — Status, editing, and diagnostic evidence compete on the first screen.** Start with schedule enforcement, current availability, next start, and one action.
- **P2 — `Allowed Now: Yes` can conflict with `Enforcement: Off`.** Use unambiguous states such as “Schedule is off — time windows are not enforced.”

### Settings

- **P1 — Guided Setup has competing save actions.** The persistent header save bypasses the wizard's reviewed `Save & Reload` journey; show one completion path while the wizard is active.
- **P1 — Encoder choices precede compatibility discovery.** Make “Check this computer” the first step, apply a recommended profile, and move codec/preset overrides to Advanced.
- **P2 — Internal terminology and raw JSON dominate ordinary configuration.** Lead Status with a single setup state; make JSON an advanced, clearly bounded option; simplify Media Output and Naming into outcomes.

### Diagnostics

- **P1 — Developer/test-matrix functions are reachable from public diagnostics.** Tdarr Proof Pack includes reruns, cleanup, archive, and guarded delete controls. Isolate this as developer test tooling.
- **P1 — Default Overview combines multiple urgent jobs.** Begin with task choices for failed job, stuck job, safe close, or status check; reveal raw logs/evidence after the choice.
- **P2 — Technical evidence and repeated log routes obscure recovery.** Make one “Find reason for failed job” journey select the appropriate bounded log, with technical file selection secondary.

### Maintenance

- **P1 — This is chiefly a developer/release console.** Change ledger, changelog hygiene, dependency atlas, and packaging should not lead a public maintenance surface; default to a plain system check.
- **P1 — Personal configuration can be unintentionally included in a shareable package.** Relabel, explain, and move `Keep personal config` to Advanced before preview/build.
- **P2 — Abstract status and raw output do not guide recovery.** Use action-oriented health outcomes and outcome cards ahead of raw command results.

## Cross-tab findings

### Navigation and workflow continuity

Pages often name a destination without providing an action: Telemetry tells users to open Diagnostics; Network CSV Rerun points to Queue; Schedule describes Launch choices; Metrics Attention lists a subtab. Add contextual, read-only navigation that focuses the destination's heading. Do not recreate backend command ownership in the frontend.

### Terminology and information hierarchy

Terms such as pipeline, preflight, sidecar, manifest, evidence authority, PSD1, NVENC, patch, backfill, and dependency atlas appear before their user outcome. Put plain-language outcome, scope, and next step first; keep precise technical evidence in an Advanced/Technical details disclosure.

### Error recovery

Status surfaces tend to show many parallel cards/tables rather than a single answer and recovery path. Standardize a compact pattern: **status**, **what it means**, **safe next step**, and **open details**. The observed expired-session Home state should name whether the user must reopen the desktop app/sign in again and provide the exact recovery path.

### Accessibility and narrow layouts

Fix semantic defects first (nested controls; incomplete tabs/listbox; non-operable focusable drop zone). Then provide text alternatives for visual trends and replace wide, action-heavy tables with responsive summaries/cards at tested narrow and high-zoom widths. Horizontal scrolling alone is insufficient when the next action or final status falls off-screen.

## Prioritized implementation backlog

| Priority | Work item                                                                               | Effort | Expected user benefit                                         |
| -------- | --------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------- |
| P1       | Queue CSV rerun safe defaults and impact preview                                        | M      | Prevents mistaken replacement of final outputs                |
| P1       | Rename unseen-row selection guard                                                       | M      | Restores meaningful preview-before-apply safety               |
| P1       | Settings Guided Setup single-save journey and hardware-first setup                      | M      | Makes first-time configuration comprehensible                 |
| P1       | Launch plain-language scope/safety/readiness summary                                    | S      | Enables confident first safe start                            |
| P1       | Pending nested-control fix; Telemetry trend alternative                                 | S      | Removes core keyboard/AT barriers                             |
| P1       | Schedule range editor, status summary, and narrow layout                                | L      | Makes scheduling feasible with keyboard/zoom/narrow windows   |
| P1       | Reports task split and responsive action-table pattern                                  | L      | Makes failure/audit recovery usable on ordinary displays      |
| P1       | Separate developer tooling from Diagnostics/Maintenance public paths                    | M      | Reduces wrong-context actions and intimidation                |
| P1       | Libraries guided first action and simplified save vocabulary                            | M      | Reduces setup uncertainty and accidental abandonment of edits |
| P1       | Private-config package warning/advanced placement                                       | S      | Reduces accidental private-data sharing                       |
| P2       | Shared status/next-step component and contextual navigation                             | M      | Creates consistent recovery across tabs                       |
| P2       | Progressive disclosure for raw evidence/JSON/path blocks                                | M      | Preserves evidence while reducing cognitive load              |
| P2       | Shared responsive data-card pattern for Queue, Telemetry, Network, Reports, Diagnostics | L      | Enables low-vision/narrow use without horizontal hunting      |
| P2       | Plain-language terminology pass with technical details/tooltips secondary               | M      | Lowers expertise barrier throughout the product               |

## Quick wins

- Rename the most ambiguous calls to action: `Start / Launch`, `Validate`, `Backfill Enabled`, `Allow All`, `Keep personal config`, and the Queue gear.
- Add one visible outcome/safety sentence beside Launch, Libraries scan/auto-run, Metrics backfill, and Maintenance packaging controls.
- Remove the Pending Publish outer faux button and correct tab/listbox/drop-zone semantics.
- Change unloaded zeroes to `Checking…`/`Unavailable` rather than `0` on Home and clarify `Schedule off` vs `Allowed now`.
- Add direct, read-only “Open [owner]” links wherever a page names another tab as the next step.

## Validation after fixes

- Test every fixed tab in the authenticated Tauri/WebView shell with normal, empty, loading, disabled, and server-error states; capture desktop and 390px screenshots.
- Complete keyboard-only task runs: first setup, start a safe queue, investigate a failed/interrupted job, review output, schedule time, and rename preview/apply dry-run.
- Run automated accessibility checks and manually verify focus order/visible focus, tab/listbox semantics, canvas text alternatives, dialogs, and screen-reader announcements.
- Test 200%, 300%, and narrow-window reflow; confirm status, next action, and row-level action remain visible without relying on horizontal scrolling.
- Exercise backend dry-run/confirmation paths for Queue rerun, Rename, Reports evidence clearing, Settings, Schedule, and packaging; verify UI wording does not imply frontend ownership or add redundant confirmations.
- Re-run no-mutation browser/API smoke coverage and relevant targeted tests; use representative real-media validation only if a change affects media policy, movement, or processing behavior.
