# V5 UI Design Reference

**Purpose:** This document defines how the MediaPipeline V5 WebView UI should look and behave. It is the single source of truth for any AI agent or contributor building, extending, or reviewing V5 UI code. All decisions here are grounded in *Refactoring UI* by Adam Wathan & Steve Schoger and adapted to the operator context of this application.

**Scope:** WebView (HTML/CSS/JS) pages only. The removed legacy desktop shell is outside this V6 design reference.

---

## 0. Who is the operator and what do they need

The V5 operator is a technically capable person managing a media processing pipeline. They run batches, review output, make publish decisions, and diagnose failures. They are not a casual consumer. The UI does not need to feel playful. It needs to feel **clear, trustworthy, and efficient** — closer to a professional monitoring dashboard than a marketing site.

Every design decision should serve one of these three operator goals:

1. **Understand current state at a glance** — what is the queue doing, what succeeded, what needs attention
2. **Make a safe decision** — what evidence supports this action before I commit to it
3. **Find the problem** — when something went wrong, where do I look next

If a design element does not serve at least one of these goals, it should not be there.

---

## 1. Personality

### Tone

- **Professional, calm, neutral.** Not playful. Not corporate-cold either. Think a well-built internal ops tool that respects the operator's intelligence.
- Language in the UI should be direct and specific. Not "Something went wrong." — "Rename failed: target path already exists." Not "Processing…" — "Remuxing 3 of 12 files."
- Labels on buttons and chips must say what will actually happen, not what the user hopes will happen. "Submit rename to backend" not "Apply." "Ready-looking — verify before drain" not "Ready."

### Visual personality

- **No rounded corners on primary containers.** Panels, cards, and table rows use `border-radius: 0` or at most `2px`. Reserve `4–6px` radius only for small chips and badges where a pill shape communicates status at a glance.
- **No decorative gradients.** The UI uses flat color. Depth is communicated through shadow and background contrast, not gradients.
- **No illustrations or background patterns.** The operator is working, not being onboarded. Reserve decorative elements for empty states only (see Section 8).
- **Accent color is used sparingly** — for active states, status chips, and accent borders on selected rows. It is not used to make things look interesting.

---

## 2. Color System

### Define all shades up front. Never use one-off hex values.

The palette is built in HSL and defined as CSS custom properties. Every color used in the UI must be one of these named tokens — never a raw hex or an inline `hsl()` call.

### Greys (primary surface and text colors)

Use 9 grey shades, cool-tinted (blue-saturated) to feel like a tool rather than a document editor. Saturation ~5–8% throughout.

```css
--grey-900: hsl(220, 7%, 11%);   /* primary text, headings */
--grey-800: hsl(220, 6%, 20%);   /* strong secondary text */
--grey-700: hsl(220, 5%, 30%);   /* secondary text, labels */
--grey-600: hsl(220, 5%, 40%);   /* de-emphasized labels */
--grey-500: hsl(220, 5%, 52%);   /* placeholder, hints */
--grey-400: hsl(220, 4%, 64%);   /* disabled text */
--grey-300: hsl(220, 4%, 75%);   /* subtle borders */
--grey-200: hsl(220, 4%, 87%);   /* dividers, inactive row bg */
--grey-100: hsl(220, 4%, 94%);   /* page background, panel bg */
--grey-50:  hsl(220, 4%, 97%);   /* lightest surface */
```

True black (`#000`) and true white (`#fff`) are never used directly. Start from `--grey-900` and `--grey-50`.

### Primary color (blue — action, active state, selection)

```css
--blue-900: hsl(215, 60%, 18%);
--blue-800: hsl(215, 55%, 28%);
--blue-700: hsl(215, 52%, 38%);
--blue-600: hsl(215, 50%, 48%);
--blue-500: hsl(215, 55%, 56%);  /* base — use for buttons, selected rows */
--blue-400: hsl(215, 60%, 67%);
--blue-300: hsl(215, 65%, 77%);
--blue-200: hsl(215, 70%, 86%);
--blue-100: hsl(215, 75%, 93%);  /* tinted background for alerts */
```

### Status / accent colors

Each semantic state has its own fixed palette. Never improvise a warning color.

```css
/* Success / green */
--green-700: hsl(145, 55%, 25%);
--green-500: hsl(145, 52%, 42%);
--green-100: hsl(145, 55%, 92%);

/* Warning / amber */
--amber-700: hsl(38, 80%, 30%);
--amber-500: hsl(38, 85%, 50%);
--amber-100: hsl(38, 90%, 93%);

/* Error / red */
--red-700: hsl(5, 65%, 30%);
--red-500: hsl(5, 68%, 48%);
--red-100: hsl(5, 70%, 94%);

/* Advisory / purple — for read-only evidence panels and advisory hints */
--purple-700: hsl(265, 45%, 30%);
--purple-500: hsl(265, 48%, 52%);
--purple-100: hsl(265, 52%, 94%);
```

### Color rules

- **Never use grey text on a colored background.** If text sits on `--blue-500` or a status-colored panel, hand-pick a text color that shares the panel's hue. Do not use `color: white; opacity: 0.7` — it looks faded and disabled.
- **Color alone is never the only signal.** Every status chip or severity indicator must also use a text label, an icon, or a distinct shape. Operators with color blindness must be able to read the state.
- **De-emphasize with color, not just size.** A secondary label in a data row should be `--grey-600`, not 11px in `--grey-900`. Reducing contrast communicates hierarchy more naturally than shrinking text.

---

## 3. Typography System

### Font

**System font stack only.** No custom web fonts. Loading fonts from the network adds latency and is unnecessary for a desktop tool.

```css
font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
```

Segoe UI is the Windows system font and will be used on every supported machine. It is a neutral sans-serif with 5+ weights — exactly right for a dense operator UI.

### Type scale

Define all font sizes as custom properties. Never use an arbitrary pixel value inline.

```css
--text-xs:   11px;   /* metadata, footnotes, timestamps in rows */
--text-sm:   13px;   /* table cell content, secondary labels */
--text-base: 15px;   /* default body text, form inputs, panel body */
--text-md:   17px;   /* panel headings, section titles */
--text-lg:   20px;   /* page-level section headings */
--text-xl:   24px;   /* page title */
--text-2xl:  30px;   /* reserved — use only for single-stat callouts */
```

Do not use `em` units for font sizes anywhere in this UI. Use `px` or `rem` mapped to the scale above.

### Font weights

Two weights only for 95% of the UI:

- **Normal (400)** — body text, table cell content, labels
- **Semibold (600)** — headings, column headers, emphasized values, button labels

Bold (700) is reserved for the most critical status callouts — never use it for regular hierarchy.

Never use weights below 400. For de-emphasis, use a lighter color (`--grey-600` or `--grey-500`), not a thinner weight.

### Line height

Line height is proportional to line length and font size:

| Context | Font size | Line height |
|---|---|---|
| Table rows, chips | `--text-sm` | 1.3 |
| Panel body text | `--text-base` | 1.6 |
| Wider prose blocks | `--text-base` | 1.75 |
| Section headings | `--text-md / --text-lg` | 1.2 |
| Page title | `--text-xl` | 1.15 |

### Line length

Prose text inside evidence panels should be constrained to 60–75 characters per line. Use `max-width: 65ch` on paragraph elements inside panels. Table columns and row detail lines are exempt.

### Alignment

- All UI text is **left-aligned** by default.
- Center-align only for empty-state messages (2–3 lines max) and single-stat callouts.
- **Right-align numbers** in table columns: file sizes, durations, row counts, percentages. This makes columns scannable.
- **Baseline-align** when mixing font sizes on the same line (e.g., a large value next to a small unit label). Never vertically center-align mixed sizes — align by baseline.

### Letter spacing

- Default for all UI text: trust the font designer, do not adjust.
- All-caps labels (status chips, column headers): add `letter-spacing: 0.04em` to compensate for the reduced visual variety of all-caps text.
- Never use all-caps for body text or evidence content — only for short labels (≤ 3 words).

---

## 4. Spacing and Sizing System

### The scale

All margins, paddings, gaps, and component dimensions must use values from this scale. Never use an arbitrary pixel value.

```css
--space-1:  2px;
--space-2:  4px;
--space-3:  6px;
--space-4:  8px;
--space-5:  12px;
--space-6:  16px;
--space-7:  20px;
--space-8:  24px;
--space-9:  32px;
--space-10: 40px;
--space-11: 48px;
--space-12: 64px;
--space-13: 80px;
--space-14: 96px;
```

Adjacent values are always at least 25% apart. This ensures that choosing between two values always produces a visually distinct result.

### White space philosophy

**Start with too much white space, then remove — never start tight and add.** Elements given only the minimum breathing room to not look bad will always look mediocre. If something looks "a little too roomy," it probably is about right in context.

### Group spacing rule

When spacing is used to group related elements: **the space inside a group must always be smaller than the space between groups.** If a label and its value share `--space-4` of vertical gap, then consecutive field groups must be separated by at least `--space-6`. Ambiguous spacing is one of the most common causes of an interface feeling hard to read.

---

## 5. Visual Hierarchy

### The core rule

Not all elements in an interface are equally important. The design must make the hierarchy obvious without the operator having to think about it. If everything competes for attention, nothing is communicated.

### Three levels of content

Every piece of content in the V5 UI falls into one of three levels:

| Level | Examples | Treatment |
|---|---|---|
| **Primary** | Output filename, job status, current route, drain/launch target | `--grey-900`, `--text-base` or `--text-md`, weight 600 where appropriate |
| **Secondary** | File size, timestamp, sidecar path, secondary status | `--grey-700`, `--text-sm`, weight 400 |
| **Tertiary** | Metadata footnotes, evidence provenance, "last updated" | `--grey-500`, `--text-xs`, weight 400 |

### Hierarchy tools — in order of preference

1. **Font weight** — bold is the strongest tool. Use it for one thing per row or panel section.
2. **Color / contrast** — lighter color recedes; darker color advances. Use `--grey-600` to `--grey-500` to de-emphasize without removing content.
3. **Font size** — use sparingly. Jumping more than one step in the type scale for a hierarchy signal is usually excessive.
4. **Positioning** — primary information appears first (top-left for LTR). Supporting detail follows.

Never use font size alone to communicate hierarchy in a data-dense table.

### Labels are a last resort

Before adding a "Label: Value" pair:
- Can the value speak for itself in context? (`2026-05-14T22:31:07` is self-evidently a timestamp)
- Can the label be baked into the value? ("12 files remaining" not "Remaining: 12")
- Can context of the surrounding row make it clear?

When labels are required (e.g., the Settings page, Diagnostics detail panels), treat the label as **secondary** content. The value is what the operator needs — the label is only there to remove ambiguity. Make labels smaller, lighter, and less contrasted than the values they describe.

Exception: when the operator is scanning *for* the label (e.g., a technical spec page where they are looking for "Subtitle mode"), emphasize the label slightly and de-emphasize the value slightly.

### Section titles are not headings

Section titles inside panels (e.g., "Output Proof", "Size Policy", "Pending Publish Posture") are supportive content — they frame the section but are not the point of it. They should be `--text-sm`, `--grey-600`, weight 600, all-caps with letter spacing. They must not dominate the content below them.

Use semantic heading tags (`h2`, `h3`) for accessibility reasons, but override all browser-default sizing. The element's visual style is determined by its role in the hierarchy, not its HTML tag.

### Emphasize by de-emphasizing

When a key piece of information is not standing out enough, the first instinct of adding more emphasis (bolder, bigger, brighter) is usually wrong. Instead, **reduce the prominence of everything competing with it.** A selected row stands out because inactive rows are softer — not because the selected row is louder.

### Primary vs. secondary vs. tertiary actions

Every interactive control sits in a pyramid:

- **Primary action** (one per context): solid filled background, `--blue-500`, white label, full contrast. Examples: "Start Pipeline", "Submit Rename to Backend", "Confirm Drain".
- **Secondary action** (a few per context): outline or low-contrast fill, `--blue-200` background with `--blue-700` text, or `--grey-200` background with `--grey-800` text. Examples: "Clear Filter", "Reset to Defaults", "Cancel".
- **Tertiary action** (seldom used): looks like a text link. `--blue-600`, no background, underline on hover. Examples: "View sidecar", "Open log file".

Destructive actions (drain, delete, overwrite) are **not automatically red and large**. If the destructive action is not the primary action on the page, give it secondary or tertiary treatment. Only make it red and prominent in the confirmation step where it is the only action.

---

## 6. Layout Principles

### Don't fill the screen

V5 panels should only be as wide as their content requires. A diagnostics detail panel that needs 600px should be 600px — not stretched to fill the available sidebar width. Spreading content unnecessarily makes it harder to read and harder to scan.

If a narrow component sits in a wider context, it is acceptable for it not to fill the full width. Trying to force everything to match the widest element makes each component worse.

### Use fixed widths where it makes sense

Not every column needs to be a percentage of the parent. Sidebar widths, filter panel widths, and status chip widths should be fixed at their natural content size. The main content area flexes to fill remaining space.

### Columns over stretching

If a panel has a narrow optimal width but the page has wider space available, split it into two columns rather than stretching it. Example: a settings form that is optimal at 480px can have a description/context column on the left and the form fields on the right — this uses space without degrading the form.

### Navigation

The page navigation (Home, Queue, Launch, Completed, Pending Publish, Rename, Settings, Diagnostics, Network) is a sidebar or top nav. The active item uses an accent border on the left edge (3–4px, `--blue-500`) and a slightly tinted background (`--blue-100`). Inactive items are `--grey-700` text with no background. No colored pill or badge on inactive items.

### Table layout

Tables are the primary data surface in V5. Rules:

- Columns have fixed or content-driven widths — not all equal.
- The filename/title column is the widest and left-aligned.
- Numeric columns (size, duration, count) are right-aligned.
- Status columns (route, state, mode) use chips and are center-aligned.
- Row height is consistent within a table. Use `--space-5` vertical padding per cell (`12px` top + `12px` bottom = `24px` minimum row height for `--text-sm` content).
- Selected row: `--blue-100` background, left accent border `3px solid --blue-500`. Do not change the text color of the selected row — the background change is sufficient.
- Hover row (unselected): `--grey-100` background. No border change.
- Column headers: `--text-xs`, all-caps, `letter-spacing: 0.04em`, `--grey-600`, `font-weight: 600`. Sortable columns get a sort indicator icon.

### Panel layout

Evidence panels and detail sections beneath a selected row:

- White or `--grey-50` background.
- `--space-8` (`24px`) internal padding.
- Grouped sections within the panel are separated by a `1px --grey-200` divider or by `--space-9` (`32px`) of space — not both.
- Panel headings: `--text-sm`, all-caps, `--grey-600`, `letter-spacing: 0.04em`. Not `--text-md` or `--text-lg` — panel headings are labels, not titles.

---

## 7. Component Patterns

### Status chips

Status chips (route decision, job state, drain posture, OCR readiness) are the primary at-a-glance signal in table rows.

**Anatomy:** `[Icon] Label text` inside a rounded pill (`border-radius: 4px`), `--text-xs`, all-caps, `letter-spacing: 0.04em`, `font-weight: 600`, `--space-2` vertical padding, `--space-3` horizontal padding.

| State | Background | Text | Icon |
|---|---|---|---|
| Success / done | `--green-100` | `--green-700` | ✓ checkmark |
| Warning / review | `--amber-100` | `--amber-700` | ⚠ triangle |
| Error / blocked | `--red-100` | `--red-700` | ✕ cross |
| Advisory / read-only | `--purple-100` | `--purple-700` | ℹ info |
| Neutral / idle | `--grey-200` | `--grey-700` | — none |
| Active / in progress | `--blue-100` | `--blue-700` | spinner |

Never rely on color alone — every chip has a text label. If the text label is self-sufficient without the color (e.g., "H.264 Remux"), a neutral chip is fine. Only use semantic color when the state itself (success/warning/error) is the message.

### Buttons

- Buttons have no border-radius (or `2px` max).
- Button labels are `--text-sm`, `font-weight: 600`.
- Vertical padding: `--space-4` (`8px`). Horizontal padding: `--space-7` (`20px`).
- Primary buttons: `background: --blue-500`, `color: white`. On hover: `--blue-600`. On active: `--blue-700` with a slightly reduced top border shadow (simulates pressing into the page).
- Secondary buttons: `background: --grey-200`, `color: --grey-800`. On hover: `--grey-300`.
- Destructive primary buttons (confirmation step only): `background: --red-500`, `color: white`.
- Disabled buttons: `background: --grey-200`, `color: --grey-400`, `cursor: not-allowed`. Do not reduce opacity — change color instead.

### Form inputs

- Inputs are inset elements. Use a subtle inset box-shadow: `inset 0 1px 2px hsl(220, 5%, 0%, 0.08)` and a `1px --grey-300` border.
- On focus: border becomes `--blue-500`, inset shadow increases slightly.
- Labels above inputs: `--text-sm`, `--grey-700`, `font-weight: 600`.
- Helper text below inputs: `--text-xs`, `--grey-500`.
- Error state: border `--red-500`, helper text `--red-700`.
- Space between label and input: `--space-2` (`4px`). Space between consecutive field groups: `--space-8` (`24px`) — must be clearly more than the label-to-input gap so groups feel grouped.

### Shadows / elevation

Five shadow levels only. Never invent a shadow outside this set.

```css
--shadow-1: 0 1px 2px hsl(220, 6%, 0%, 0.08);                          /* subtle lift — buttons, input focus */
--shadow-2: 0 2px 4px hsl(220, 6%, 0%, 0.10);                          /* card, selected row panel */
--shadow-3: 0 4px 8px hsl(220, 6%, 0%, 0.12), 0 1px 3px hsl(220,6%,0%,0.08);  /* dropdown menus */
--shadow-4: 0 8px 24px hsl(220, 6%, 0%, 0.14), 0 2px 6px hsl(220,6%,0%,0.10); /* drawer / slide-out panel */
--shadow-5: 0 16px 48px hsl(220, 6%, 0%, 0.18), 0 4px 12px hsl(220,6%,0%,0.12); /* modal dialog */
```

Rule: elements closer to the operator (modal > drawer > dropdown > card > button) get higher shadow numbers. On click/press, a button switches from `--shadow-1` to no shadow to simulate pressing in.

### Borders

Use borders sparingly. Before adding a border between two elements, try these alternatives in order:
1. Different background colors (adjacent panels at `--grey-50` vs `white`)
2. Extra spacing (`--space-9` or `--space-10` gap)
3. Box shadow (`--shadow-1` on the inner element)
4. Only then: a `1px --grey-200` divider

When a border is used, it is always `1px` and always `--grey-200` or `--grey-300`. Never use a `2px` border as a separator — reserve `2px+` borders for accent purposes only (selected row left edge, active nav item, section accent).

### Accent borders

Use a `3–4px` colored left border to draw attention to:
- The selected row in a table
- The active navigation item
- Alert or warning banners in panels
- Evidence sections that need operator review

This is a cheap but effective way to add color and visual anchoring without redesigning the component.

### Empty states

Every page and panel that can have zero content (empty queue, no completed rows, no pending publish items) must have an explicit empty state. Empty states are not afterthoughts.

An empty state has three parts:
1. A simple icon or small illustration (monochrome, 48–64px, centered)
2. A short headline: `--text-md`, `--grey-800`, centered, 1 line
3. A short explanation: `--text-sm`, `--grey-500`, centered, 2–3 lines max, constrained to ~40ch

If the empty state implies a next action (e.g., "No files in queue — add some"), include a primary button below the explanation. If the empty state is purely informational (e.g., "No completed runs yet"), no button is needed.

Do not show filter controls, sort headers, or column headers when the list is empty. Hide that supporting UI — it is pointless until there is content.

### Read-only evidence panels

Evidence panels are the signature component of V5. They surface backend-authored proof without allowing frontend mutation. Their design must communicate that they are informational, not interactive.

Rules:
- Evidence panels use `--purple-100` as a very faint background tint, or `--grey-50` if purple feels too heavy for the context. The tint must be subtle — it is there to distinguish the panel from the surrounding surface, not to decorate it.
- The panel heading includes a read-only indicator: a lock icon (`🔒`) or an `[evidence only]` chip in tertiary treatment.
- No buttons inside an evidence panel except "Copy" (to copy the evidence checklist text to clipboard). Copy is a tertiary action — text link style.
- Evidence items within the panel use a consistent left-icon + label + value layout. Icons are `--grey-400` (de-emphasized to not compete with the value text).
- Missing evidence (not yet recorded) is shown explicitly as "Not recorded" in `--grey-400`, not left blank.

---

## 8. Page-Specific Rules

This section covers all 13 pages. For each page: the canonical nav label, the page title shown as the H1, the correct names for every panel and subsection, and any page-specific design rules.

### Naming authority

The names in this section are the canonical names for the UI. If the HTML, JS, or a doc file uses a different name, the name here is correct and the file should be updated to match. Do not invent new panel names; use the names defined here.

---

### Page: Dashboard
**Nav label:** `Dashboard`
**Page title:** `Pipeline Dashboard`
**data-page value (HTML):** `home` *(do not rename the data attribute — it is wired to backend routing)*

This is the morning-briefing page. The operator opens it to understand the full current state before doing anything else. It is also where transition-phase validation evidence lives until the WebView is promoted to daily-driver status.

**Panel names:**

| Canonical name | Notes |
|---|---|
| System Readiness | Was "Operator Readiness". Shows whether the pipeline and backend are ready. |
| Readiness Checklist | Was "Daily-Driver Checklist". Row-by-row checklist of pipeline readiness gates. |
| Settings Health | Was "Saved Settings Trust". Health check on whether saved config is coherent. |
| Tool Status | Was "External Dependency Digest". Whether FFmpeg, MKVToolNix, PgsToSrt, etc. are present. |
| Current Run | Was "Active Work". Active job status and in-progress evidence. |
| Pipeline Overview | Was "Cross-Page Context". Cross-cutting view of queue/completed/pending state together. |
| — Conflict Summary | Was "Queue / Completed / Pending Conflict Board". Rows showing cross-page state conflicts. |
| — Evidence Correlation | Was "Sample Evidence Correlation". |
| — Validation Template | Was "Validation Log Template". |
| — Validation Worksheet | Was "Real-Media Validation Worksheet". |
| — Validation Record | Was "Sample Validation Record". |
| — Evidence Handoff | Was "Completed Evidence Handoff". |
| — Evidence Gaps | Was "Real-Media Evidence Gaps". |
| — Pilot Runbook | Was "Real-Media Pilot Runbook". |
| — Cutover Gate | Was "WebView Cutover Gate". |
| — Sample Guide | Was "Real-Media Sample Set Guide". |
| — Category Summary | Was "Pilot Category Validation Summary". |
| — Sample Checklist | Was "Operator Sample Execution Checklist". |
| — Pilot Worksheets | Was "Generated Pilot Worksheets". |
| — Acceptance Gate | Was "Acceptance Readiness Gate". |
| — Accepted Records | Was "Accepted Record Proof Review". |
| Runtime Files | Was "Runtime Artifacts". State files and sidecar paths. |
| Run Progress | Was "Progress Details". Current job progress detail. |
| Progress Proof | Was "Progress Evidence". Evidence-trail panel for the active run. |
| Recent Events | Was "Recent Pipeline Events". Event stream. |
| Recent Commands | Was "Command Results". Last N backend command results. |

**Design rules:**
- Metric grid (pipeline state, queue count, processed count, failed count) sits above all panels. These four numbers are the first thing the operator reads.
- Pipeline Overview (formerly Cross-Page Context) is a read-only evidence panel. No buttons inside it except Copy.
- The many subsections of Pipeline Overview are collapsed by default. Only the Conflict Summary is expanded by default — that is the most time-sensitive information.
- Empty state for Conflict Summary when no conflicts: "No conflicts detected across Queue, Output, and Publish." No icon needed here — a clean text message is sufficient.

---

### Page: Telemetry
**Nav label:** `Telemetry`
**Page title:** `Hardware Telemetry`
**data-page value (HTML):** `live`

Shows real-time hardware resource usage while the pipeline runs. CPU, NVENC encoder, and RAM only. This is a monitoring page, not a control page.

**Panel names:**

| Canonical name | Notes |
|---|---|
| CPU Usage | Was "CPU". Add the word "Usage" to be explicit. |
| NVENC Usage | Was "NVENC". GPU encoder utilization. |
| RAM Usage | Was "RAM". |
| Monitoring Status | Was "Telemetry Readiness". Is the telemetry feed live and healthy. |
| GPU Details | Was "GPU Detail". Plural is more natural. |

**Design rules:**
- All panels are read-only. No controls on this page.
- The three usage meters (CPU, NVENC, RAM) are always visible regardless of pipeline state. Show 0% / idle state when nothing is running — do not hide the panels.
- Usage values are right-aligned numbers. Units (`%`, `MB`, `GB`) are secondary color (`--grey-600`).
- Empty state for GPU Details when NVENC is not available: "NVENC not detected — CPU encoding only." Use the neutral chip style.

---

### Page: Queue
**Nav label:** `Queue`
**Page title:** `Processing Queue`
**data-page value (HTML):** `queue`

Shows every file waiting to be processed, with route decisions, blockers, and warnings. The operator reviews this before launching a run.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Queue | Was "Queue Preview". It is the queue — no qualifier needed. |
| Readiness | Was "Queue Readiness". |
| Queue Summary | Was "Queue Breakdown". Count breakdown by state/route. |
| Run History | Was "Runtime Outcome History". |
| Pre-Launch Checklist | Was "Validation Checklist". |
| Next Step | Was "Workflow Next Step". |
| Launch Scope | Was "Backend Launch Scope Preview". |
| Launch Checklist | Was "Launch Decision Checklist". |
| Flagged Items | Was "Operator Review Board". Rows that need operator attention before launch. |
| Collision Risk | Was "Completed Collision / Exclusion Risk". |
| Excluded Files | Was "Excluded Source Rows". |
| Selected File | Was "Selected Row At A Glance". |
| Diagnostics Links | Was "Diagnostics Cross-Links". |

**Design rules:**
- Queue table columns: filename (primary, widest), route hint (chip), size estimate (right-aligned), status (chip).
- Rows with warnings (oversize, route conflict, blocked) show `--amber-100` row background. The background draws attention; the chip provides detail. Do not rely on the chip alone.
- Launch Scope panel is read-only advisory. It must include explicit loaded-row vs. visible-filtered-row language and must never contain a launch button.
- Empty state for the Queue table: "Queue is empty — no files waiting to process." Include a neutral icon (e.g. inbox outline).

---

### Page: Output
**Nav label:** `Output`
**Page title:** `Pipeline Output`
**data-page value (HTML):** `completed`

Shows every file that has been processed by the pipeline. The operator reviews output quality, size, route, and evidence before accepting or publishing.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Output Files | Was "Completed Jobs". The table of processed files. |
| Integrity Check | Was "Output Integrity". |
| Route Summary | Was "Route / Publish Breakdown". |
| Run History | Was "Runtime Outcome History". |
| Manifest Check | Was "Manifest Consistency". |
| Output Checklist | Was "Validation Checklist". |
| Next Step | Was "Workflow Next Step". |
| Flagged Items | Was "Operator Review Board". |
| Size Check | Was "Size Growth Review". |
| Size Evidence | Was "Size Growth Evidence". |
| Proof Check | Was "Output Proof Cross-Check". |
| Publish Reconciliation | Was "Backend Publish Reconciliation". |
| Output Proof | Was "Real-Media Output Proof". |
| Output Verification | Was "Final Output Trust Walkthrough". |
| Evidence Packet | Was "Selected Pilot Evidence Packet". |
| Acceptance Checklist | Was "Output Acceptance Checklist". |
| Route Agreement | Was "Queue / Completed Route Agreement". |
| Selected File | Was "Selected Row At A Glance". |
| Diagnostics Links | Was "Diagnostics Cross-Links". |

**Design rules:**
- Output Files table columns: filename (primary), route taken (chip), size with growth % (right-aligned), completion timestamp (secondary), status (chip).
- Size coloring: within policy → `--grey-700`; advisory threshold exceeded → `--amber-700`; rejected → `--red-700`. Growth % displayed inline as `+3.1%` in the smaller secondary color.
- Evidence Packet is a read-only evidence panel. "Copy checklist" is the only control inside it — tertiary action style.
- Policy reconciliation inside Evidence Packet: mismatches between recorded output and saved Settings appear as `--amber-100` inline chips next to the specific evidence item.
- Empty state for Output Files: "No completed runs yet." Neutral icon, no filter controls visible.

---

### Page: Publish
**Nav label:** `Publish`
**Page title:** `Pending Publish`
**data-page value (HTML):** `pending`

Shows files that have been processed and are waiting for the final publish step. The operator reviews drain readiness and decides when to drain.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Pending Items | Was "Pending Publish" (the table heading). |
| Drain Status | Was "Drain Readiness". |
| Risk Summary | Was "Risk Breakdown". |
| Publish Checklist | Was "Validation Checklist". |
| Next Step | Was "Workflow Next Step". |
| Flagged Items | Was "Operator Review Board". |
| Drain Evidence | Was "Drain Evidence Board". |
| Recovery Preview | Was "Recovery Dry Run". |
| Drain Confidence | Was "Drain Action Confidence". |
| Drain Scope | Was "Backend Drain Scope Preview". |
| Drain Checklist | Was "Drain Decision Checklist". |
| Publish Guard | Was "Publish Button Guard". |
| Drain Comparison | Was "Drain Correlation". |
| Post-Drain Review | Was "Post-Drain Trust Review". |
| Recent Events | Was "Recent Drain Events". |
| Last Drain | Was "Last Drain Summary". |
| Selected Item | Was "Selected Row At A Glance". |
| Diagnostics Links | Was "Diagnostics Cross-Links". |

**Design rules:**
- Pending Items table columns: title (primary), manifest status (chip), drain posture (chip), file count (right-aligned), age (secondary).
- "Ready-looking" drain posture chip: `--amber-100 / --amber-700`. It is advisory, not confirmed — never use green for this chip. Only use `--green-100 / --green-700` when the backend explicitly confirms drain-safe.
- Drain Scope panel is read-only advisory. Same rules as Queue's Launch Scope panel — explicit parked-row vs. visible-filtered-row language, no drain button inside.
- Drain is a destructive-adjacent action. Drain button is secondary in the row actions area. It becomes primary only in the drain confirmation dialog.
- Empty state for Pending Items: "Nothing pending publish." Neutral icon.

---

### Page: Rename
**Nav label:** `Rename`
**Page title:** `Rename Files`
**data-page value (HTML):** `rename`

File rename planning and execution. The operator reviews proposed renames, checks for conflicts, and applies them via a backend command.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Rename Plan | Was "Rename Preview". It is a plan, not just a preview — it shows proposed final names. |
| Pipeline Context | Was "Pipeline Handoff". |
| Review | Was "Review Board". |
| Selection Check | Was "Selection Audit". |
| Apply Status | Was "Apply Readiness". |
| Name Overrides | Was "Bulk Final-Name Overrides". |
| Last Result | Was "Last Apply Result". |
| Outcome Review | Was "Apply Outcome Review". |

**Design rules:**
- Rename Plan table: original filename (primary), proposed final name (primary, second column), conflict status (chip), confidence (chip).
- Apply Status is the gate before the Apply button. If it shows any blockers, the Apply button is disabled.
- "Submit Rename to Backend" is the primary action label. Not "Apply" alone — the label must communicate that this triggers a backend command, not a frontend action.
- Duplicate-target conflicts: the conflicting row gets a `--red-100` row background and a "Conflict" error chip. The Apply button remains disabled until conflicts are resolved.

---

### Page: Launch
**Nav label:** `Launch`
**Page title:** `Launch Pipeline`
**data-page value (HTML):** `launch`

Pre-run readiness review and the pipeline start trigger. The operator works through evidence panels before committing to a run.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Readiness | Was "Launch Readiness". In context of the Launch page, "Launch" prefix is redundant. |
| Schedule Alignment | Was "Timing Trust". Whether launch timing aligns with the configured schedule. |
| Settings Check | Was "Saved Settings Trust" (on this page). |
| Risk Summary | Was "Launch Risk Handoff". |
| Policy Boundaries | Was "Active Media Policy Boundary". |
| Settings vs Intent | Was "Saved Settings vs Launch Intent". |
| Scope Check | Was "Launch Scope Reconciliation". |
| Sample Proof | Was "Real-Media Sample Proof Handoff". |
| Sample Checklist | Was "Sample Execution Checklist". |
| Pilot Readiness | Was "Pilot Run Readiness". |
| Preflight Check | Was "Backend Launch Preflight". |
| Start Pipeline | Was "Pipeline Launch". This is the control panel — label it with the action. |
| Start Summary | Was "Start Decision Summary". |
| Audit Mode Start | Was "Audit Launch". |
| Rerun from CSV | Was "CSV Rerun". |
| Command History | Was "Launch Command History". |
| Command Review | Was "Launch Command Review". |

**Design rules:**
- "Start Pipeline" is the only primary action on this page. Every other interactive element is secondary or tertiary.
- The Start Pipeline button is disabled with a clear disabled label until Preflight Check shows all gates green. The disabled state must explain why: "Waiting for preflight — 2 gates pending."
- Preflight gates use a consistent ladder format: icon (✓/⚠/✕) + gate name + one-line status. `--text-sm`, left-aligned, icon uses status chip color tokens.
- All panels above Start Pipeline are read-only evidence panels. No mutation buttons appear until the Start Pipeline panel.

---

### Page: Reports
**Nav label:** `Reports`
**Page title:** `Reports & Audit`
**data-page value (HTML):** `reports`

Historical run reports, failure review, and audit log access. The operator comes here after a failed run or to review pipeline history.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Report Summary | Was "Report Triage". |
| Investigation Steps | Was "Investigation Checklist". |
| Pre-Launch Context | Was "Launch Handoff". |
| Report Paths | Was "Latest Report Paths". |
| Failures | Was "Recent Failures". Simple is better. |
| Failure Details | Was "Failure Review Board". |
| Audit Log | Was "Latest Audit Rows". |
| Audit Entries | Was "Audit Review Board". |
| Report Locations | Was "Report Roots". |
| Recently Opened | Was "Report Open History". |
| Warnings | Was "Snapshot Warnings". |

**Design rules:**
- All content on this page is read-only. No controls except "Open report file" (tertiary, backend-allowlisted paths only).
- Failures table: timestamp (primary), job name (primary), error type (chip), severity (chip).
- Audit Log table: timestamp (secondary), event (primary), result (chip).
- Empty state for Failures: "No failures in this report period." Green or neutral indicator.

---

### Page: Schedule
**Nav label:** `Schedule`
**Page title:** `Pipeline Schedule`
**data-page value (HTML):** `schedule`

Configures when the pipeline is allowed to run. Shows current schedule, coverage gaps, and weekly windows.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Current Schedule | Was "Schedule Status". |
| Launch Windows | Was "Launch Guidance". Specific windows when launch is permitted. |
| Schedule Trust | Was "Timing Trust" (on this page). Whether the saved schedule is coherent. |
| Coverage Review | Was "Schedule Coverage Review". |
| Edit Schedule | Was "Schedule Editor". Action-oriented label. |
| Weekly View | Was "Weekly Windows". |

**Design rules:**
- Edit Schedule is the only panel with mutation controls (save schedule). "Save Schedule" is the primary button inside it. All other panels are read-only.
- Weekly View displays the 7-day grid. Days where launch is permitted: `--green-100` background. Days with no window: `--grey-100`. Days with a partial/conditional window: `--amber-100`.
- Coverage Review rows: day/window (primary), status (chip), gap notes (secondary).

---

### Page: Workers
**Nav label:** `Workers`
**Page title:** `Distributed Workers`
**data-page value (HTML):** `network`

Read-only view of coordinator/worker distributed mode state. This page is fully read-only until lifecycle ownership is designed and tested.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Mode Status | Was "Network Mode". |
| Open History | Was "Network Open History". |
| Readiness | Was "Network Readiness". |
| Lifecycle Handoff | Was "Network Lifecycle Handoff". |
| Evidence Checklist | Was "Network Evidence Checklist". |
| State Files | Was "Network Runtime State Files". |
| Worker State | Was "Worker Runtime State". |
| Network Config | Was "Network Settings". |
| API Contract | Was "Local API Contract". |

**Design rules:**
- This page is fully read-only. No start, stop, promote, or demote controls. If any interactive control is mistakenly added, it violates the mutation boundary and must be removed.
- Lifecycle Handoff is a read-only evidence panel with `--purple-100` background tint to distinguish it from standard panels.
- Worker State table: worker ID (primary), role (chip), claimed job (secondary), last heartbeat (secondary), status (chip).
- Empty state for Worker State when no workers are registered: "No workers registered. Network mode requires manual coordinator setup — see documentation."

---

### Page: Maintenance
**Nav label:** `Maintenance`
**Page title:** `Maintenance Tools`
**data-page value (HTML):** `maintenance`

System health checks and dry-run maintenance operations. Operators use this to verify the environment and run safe pre-flight cleanup.

**Panel names:**

| Canonical name | Notes |
|---|---|
| System Health | Was "Environment Health". |
| Readiness | Was "Maintenance Readiness". |
| Tool Status | Was "Toolchain Readiness". |
| Check Detail | Was "Selected Check". Detail panel for a selected health check row. |
| Dry Run Status | Was "Dry-Run Confidence". |
| Release Check | Was "Release Dry Run". |
| Manifest Backfill | Was "Completed Manifest Backfill Dry Run". |
| History | Was "Maintenance Dry-Run History". |

**Design rules:**
- All operations on this page are dry-run only unless explicitly marked otherwise. Any panel that triggers a real mutation must show a `--red-100` accent border and a warning chip before the action button.
- System Health rows: area (primary), status (chip), detail (secondary).
- Tool Status rows: tool name (primary), path (secondary), availability (chip).
- Empty state for History when no dry runs have been run: "No maintenance runs recorded yet."

---

### Page: Diagnostics
**Nav label:** `Diagnostics`
**Page title:** `System Diagnostics`
**data-page value (HTML):** `diagnostics`

The primary triage surface when something goes wrong. The operator works through a first response checklist, then drills into state artifacts, logs, and command history.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Triage Overview | Was "Diagnostics Triage". |
| First Response | Was "First Response Checklist". |
| Investigation Path | Was "Investigation Trail". |
| Page Handoff | Was "Owning Page Evidence Handoff". |
| Artifact Detail | Was "Artifact Drilldown". |
| State Summary | Was "State Artifact Summary". |
| Recovery Steps | Was "Recovery Checklist". |
| Read Order | Was "Backend Read Order". |
| Shutdown Readiness | Was "Close Readiness". |
| Backend State | Was "Backend Lifecycle". |
| Current Progress | Was "Runtime Progress". |
| Log Access | Was "Log Triage". |
| Command History | Unchanged — already clear. |
| Command Detail | Was "Command Result Drilldown". |
| Impact Summary | Was "Owner Impact Board". |
| Related Evidence | Was "Related Diagnostics Evidence". |
| Failure Resolution | Was "Command Failure Resolution Checklist". |
| Errors | Was "Recent Errors". Simple is better. |
| Events | Was "Recent Events". |
| Active Jobs | Unchanged. |
| Pipeline Log | Was "Pipeline Log Tail". |
| File Log | Was "Allowlisted File Tail". |
| Launch Log | Was "Launch Logs". |
| Open Files | Was "Open Locations". |
| API Contract | Unchanged. |
| Contract Review | Was "Contract Safety Review". |

**Design rules:**
- First Response is the primary table. Each row: icon (✓/⚠/✕) + gate name + one-line status. Selected row expands to show: why this gate matters, what evidence was used, which page to go to next, and the mutation boundary reminder.
- Log Access controls (tail, open) are tertiary actions sourced from the backend-authored allowlist only. The UI must not construct arbitrary file paths — it displays only what the backend provides.
- State Summary is a read-only evidence panel.
- Empty state for Errors: "No errors recorded." Green chip.
- The First Response table should always show all rows even when all are green — the operator needs to see the full picture, not just problems.

---

### Page: Settings
**Nav label:** `Settings`
**Page title:** `Pipeline Settings`
**data-page value (HTML):** `settings`

All pipeline configuration. The operator reviews current config, stages changes via section editors, previews the impact, and saves.

**Panel names:**

| Canonical name | Notes |
|---|---|
| Current Config | Was "Settings Workspace". "Workspace" sounds like a UI framework concept; "Current Config" is what it is. |
| Config Health | Was "Saved Settings Trust". Health status of the currently saved config. |
| Policy Readiness | Was "Backend Media Policy Readiness". |
| Settings Overview | Was "Operational Settings Overview". |
| Settings Editor | Was "Structured Patch Builder". Operators don't think in "patches". |
| — Video Settings | Was "Video Detail Patch Builder". |
| — File Safety Settings | Was "File Safety / Publish Patch Builder". |
| — Recovery Settings | Was "Pending Publish / Recovery Patch Builder". |
| — Network Settings | Was "Network Patch Builder". |
| — Queue Settings | Was "Queue / Reprocess Patch Builder". |
| — Runtime Settings | Was "Runtime / Diagnostics Patch Builder". |
| — Subtitle Settings | Was "Subtitle Patch Builder". |
| — Audio Settings | Was "Audio Patch Builder". |
| Audio & Subtitle Check | Was "Audio / Subtitle Policy Cross-Check". |
| Active Policy | Was "Active Media Policy Handoff". |
| Change Preview | Was "Patch Preview". |
| — Staged Changes | Was "Staged Media Policy Delta". |
| — Active Policy | Was "Effective Policy Trust". |
| — Save Status | Was "Save Readiness". |
| — Launch Impact | Was "Launch Impact Handoff". |
| — Save Result | Was "Backend Preview / Save Result". |
| Command History | Was "Settings Command History". |
| Safety Locks | Was "Safety Lock Review". |
| Advanced Keys | Was "Raw-Key Triage". Operators see "triage" as emergency language; "Advanced Keys" is accurate and less alarming. |
| Advanced Key Plan | Was "Raw-Key Action Plan". |
| Raw Config | Was "Config Values". |

**Design rules:**
- "Save Settings" is the only primary action on this page. Label it "Save Settings" — not "Save" alone. The label must communicate scope.
- Settings Editor sections (Video Settings, Subtitle Settings, etc.) are collapsed by default. The operator expands only what they need.
- Fields that are raw-only (not in the structured editor) are shown in the Advanced Keys section with an `--amber-100` accent border and a warning chip: "Advanced — edit with care."
- Change Preview is always visible when there are staged changes. It must show a clear diff between current and staged values.
- Config Health and Policy Readiness are read-only evidence panels at the top of the page — the operator should see the health of their current config before making any changes.

---

## 9. What Not to Do

These are the most common mistakes that will make the V5 UI feel broken or unprofessional. Future agents: treat these as hard rules, not suggestions.

| Do not | Instead |
|---|---|
| Use grey text on a colored background (opacity trick) | Hand-pick a text color with the same hue as the background |
| Add borders between every section by default | Use space, background contrast, or shadow first |
| Make all columns equal width in a table | Size each column to its content's natural width |
| Scale icons up 2–3× from their intended size | Enclose small icons in a shaped container with a background |
| Use 10+ different font sizes across the UI | Pick from the 7-step type scale and no others |
| Create a new shade of blue for a one-off purpose | Use the defined palette token; if it doesn't exist, add it to the palette |
| Rely on color alone to communicate status | Every status must have a text label or icon in addition to color |
| Make a destructive action red and large by default | Red primary styling only in the confirmation step |
| Leave an empty table or panel with no empty state | Every zero-content view gets an explicit empty state treatment |
| Put mutation controls (rename, drain, launch) inside evidence panels | Evidence panels are read-only; mutation controls live in the main action row |
| Use `em` units for font sizes | Use `px` or `rem` mapped to the type scale tokens |
| Fill the full available width just because it is available | Size elements to their content; the content area flexes |
| Use `opacity` to de-emphasize an element | Change color (lightness/saturation) directly — opacity on text looks disabled |
| Center-align blocks of more than 2–3 lines | Left-align all prose; center only for single-line empty state headlines |
| Add a gradient to a background for visual interest | Use flat color; reserve gradients for nothing (not used in this UI) |
| Use `font-weight: 300` or lighter for de-emphasis | Use `--grey-500` or `--grey-600` color instead; thin weights are hard to read at small sizes |
| Design mutation features before their backend contracts exist | New controls require backend route, precondition validation, and command journal first |

---

## 10. Design Process Rules for AI Agents

These rules apply whenever a task involves adding or changing anything in the WebView UI — HTML, CSS, or JS. Each rule has an explicit verification step. Run the verification before marking the task done. A rule without a passing verification is not complete.

The path roots used in verification commands:

```
UI_ROOT  = DesktopApp\mediapipeline_desktop_app\ui_web\static
HTML     = DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html
CSS      = DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css
JS_DIR   = DesktopApp\mediapipeline_desktop_app\ui_web\static\assets
```

---

### Rule 1 — Panel names must match Section 8

Before writing any HTML for a new panel, look up its page in Section 8 of this document. Use the exact canonical panel name from the table. Do not invent a new name.

**Scope:** Any task that adds or renames a panel heading (`<h2>` or `<h3>` inside a `panel-heading` div).

**Verify:**
```powershell
# After writing, confirm the heading text matches the Section 8 canonical name.
# Replace YOUR_HEADING with the text you wrote.
Select-String -Path $HTML -Pattern "YOUR_HEADING"
# Must return exactly one match on the line you added.
# If the heading does not appear in Section 8, stop and add it to Section 8 first.
```

**Fail means:** The heading text is not in Section 8. Either use the canonical name or update Section 8 before proceeding — do not silently use a non-canonical name.

---

### Rule 2 — Every panel must declare its type

Every `<section class="panel">` must carry a `data-panel-type` attribute set to either `evidence` or `interactive`.

- `evidence` — read-only; the only permitted button inside is a tertiary Copy button
- `interactive` — contains operator controls (inputs, primary/secondary buttons)

Mixed panels (evidence content plus a mutation button in the same container) are not allowed. Split them into two panels if needed.

**Scope:** Any task that adds a new `<section class="panel">` to `index.html`.

**Verify:**
```powershell
# All panels must have data-panel-type. This must return zero results.
Select-String -Path $HTML -Pattern 'class="panel"' |
  Where-Object { $_.Line -notmatch 'data-panel-type=' }
```

**Fail means:** A panel is missing its type declaration. Add `data-panel-type="evidence"` or `data-panel-type="interactive"` to every `<section class="panel">` element.

---

### Rule 3 — Evidence panels must not contain mutation calls

No JS in a view file may call `apiPost` from inside a function that populates or responds to an `evidence`-typed panel, except for the single allowed Copy action.

**Scope:** Any task that adds JS behavior to a panel marked `data-panel-type="evidence"`.

**Verify:**
```powershell
# Find all apiPost calls in JS files.
Select-String -Path "$JS_DIR\*.js" -Pattern "apiPost\(" |
  Select-Object Filename, LineNumber, Line
# Review each result. Confirm none originate from evidence panel render/click handlers.
# Copy button calls are allowed (they write to clipboard, not to backend).
```

**Fail means:** An evidence panel is calling a mutation route. Move the control to an interactive panel or create a separate action row outside the evidence panel.

---

### Rule 4 — No raw hex or raw hsl() values in CSS

All colors must use CSS custom property tokens defined in Section 2 of this document (`--grey-*`, `--blue-*`, `--green-*`, `--amber-*`, `--red-*`, `--purple-*`). No raw `#rrggbb`, `#rgb`, or inline `hsl()` calls.

**Scope:** Any task that touches `styles.css` or adds a `style=` attribute in HTML.

**Verify:**
```powershell
# Find raw hex colors in CSS. Must return zero results.
Select-String -Path $CSS -Pattern '#[0-9a-fA-F]{3,8}\b'

# Find inline hsl() calls not using var(). Must return zero results.
Select-String -Path $CSS -Pattern 'hsl\s*\(' | Where-Object { $_.Line -notmatch 'var\(' }

# Find inline style attributes in HTML containing colors. Must return zero results.
Select-String -Path $HTML -Pattern 'style="[^"]*color' |
  Where-Object { $_.Line -notmatch 'var\(--' }
```

**Fail means:** Replace every raw color with the appropriate token from Section 2. If no token fits, add the shade to the palette in Section 2 first, then use the new token.

---

### Rule 5 — No font sizes outside the type scale

All font sizes must use one of the seven tokens defined in Section 3 (`--text-xs` through `--text-2xl`). No arbitrary `px`, `em`, or `rem` values for font size.

**Scope:** Any task that adds font-size rules to CSS.

**Verify:**
```powershell
# Find font-size declarations not using a token. Must return zero results.
Select-String -Path $CSS -Pattern 'font-size\s*:' |
  Where-Object { $_.Line -notmatch 'var\(--text-' }
```

**Fail means:** Replace the arbitrary size with the nearest token from the scale. If the scale genuinely needs a new step, add it to Section 3 with a justification comment before using it.

---

### Rule 6 — No spacing values outside the spacing scale

All margin, padding, and gap values must use one of the fourteen tokens defined in Section 4 (`--space-1` through `--space-14`). No arbitrary pixel values for spacing.

**Scope:** Any task that adds margin, padding, or gap rules to CSS.

**Verify:**
```powershell
# Find spacing declarations not using a token. Must return zero results.
Select-String -Path $CSS -Pattern '(margin|padding|gap)\s*:' |
  Where-Object { $_.Line -notmatch 'var\(--space-' -and $_.Line -notmatch ':\s*0' -and $_.Line -notmatch 'auto' }
```

**Fail means:** Replace the arbitrary value with the nearest token from the scale. Zero and `auto` are the only permitted raw values for spacing properties.

---

### Rule 7 — Every new button label must name its action and scope

Button labels must say what the action will actually do, not what the operator hopes. Labels that are acceptable: "Save Settings", "Submit Rename to Backend", "Confirm Drain", "Copy checklist". Labels that are not acceptable: "Save", "Apply", "Submit", "Go", "OK".

**Scope:** Any task that adds a `<button>` element to `index.html`.

**Verify:**
```powershell
# Find buttons with single-word generic labels. Review each result.
Select-String -Path $HTML -Pattern '<button[^>]*>(Save|Apply|Submit|Go|OK|Confirm|Run|Start|Done)</button>'
# Any match that does not include a qualifier (e.g. "Save Settings", "Start Pipeline") is a fail.
```

**Fail means:** Rewrite the label to include the action and its scope. "Save" → "Save Settings". "Apply" → "Submit Rename to Backend". "Confirm" → "Confirm Drain".

---

### Rule 8 — New backend route calls must be in API_ROUTE_INVENTORY.md

Every `apiPost` call that targets a route not already in `API_ROUTE_INVENTORY.md` is blocked. If the route does not exist in the backend yet, the control must be disabled with the label "Not yet available — backend route pending" rather than wired to a non-existent or improvised route.

**Scope:** Any task that adds a new `apiPost(` call referencing a route.

**Verify:**
```powershell
# Extract all apiPost route strings from JS files.
Select-String -Path "$JS_DIR\*.js" -Pattern "apiPost\s*\(\s*['\`"]([^'\`"]+)" |
  ForEach-Object { $_.Matches.Groups[1].Value } | Sort-Object -Unique

# Compare against API_ROUTE_INVENTORY.md.
Select-String -Path "Docs\inventories\API_ROUTE_INVENTORY.md" -Pattern "POST"
# Every route from the JS output must appear in the inventory. Any route that does not is a fail.
```

**Fail means:** Either add the route to `API_ROUTE_INVENTORY.md` (only if the backend route actually exists and is tested), or disable the control and label it as pending.

---

### Rule 9 — New DOM ids must be registered

Every new `id=` attribute added to `index.html` must be added to `WEBVIEW_DOM_ID_INVENTORY.md` in the same change. The inventory must be updated before the task is marked done.

**Scope:** Any task that adds a new `id="..."` attribute to `index.html`.

**Verify:**
```powershell
# Extract all id attributes from index.html.
$htmlIds = Select-String -Path $HTML -Pattern 'id="([^"]+)"' -AllMatches |
  ForEach-Object { $_.Matches | ForEach-Object { $_.Groups[1].Value } } | Sort-Object -Unique

# Check each new id appears in the inventory.
$inventory = Get-Content "Docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md" -Raw
$htmlIds | Where-Object { $inventory -notmatch [regex]::Escape($_) }
# Must return empty. Any id not in the inventory is a fail.
```

**Fail means:** Add the missing id(s) to `WEBVIEW_DOM_ID_INVENTORY.md` before closing the task.

---

### Rule 10 — New window.* exports must be registered

Every new `window.mediaPipeline*` export added in a JS file must be added to `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` in the same change.

**Scope:** Any task that adds a `window.` assignment to a JS file.

**Verify:**
```powershell
# Extract all window.* exports from JS files.
Select-String -Path "$JS_DIR\*.js" -Pattern "window\.mediaPipeline\w+" -AllMatches |
  ForEach-Object { $_.Matches.Value } | Sort-Object -Unique |
  ForEach-Object {
    $name = $_
    $inv = Get-Content "Docs\inventories\WEBVIEW_GLOBAL_EXPORT_INVENTORY.md" -Raw
    if ($inv -notmatch [regex]::Escape($name)) { "MISSING: $name" }
  }
# Must return empty.
```

**Fail means:** Add the missing export to `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`.

---

### Rule 11 — Append to DOC_TOUCH_LOG before closing the task

Every delivered chunk that changes anything visible to the operator (a panel, a label, a route, a DOM id, a global export, a smoke test) must have a row appended to `DOC_TOUCH_LOG.md`. The row must name every inventory file touched or explicitly mark each one n/a.

**Scope:** Every UI task.

**Verify:**
```powershell
# Confirm today's date appears in DOC_TOUCH_LOG.md for this chunk.
$today = Get-Date -Format "yyyy-MM-dd"
Select-String -Path "Docs\DOC_TOUCH_LOG.md" -Pattern $today
# Must return at least one result containing a description of this chunk.
```

**Fail means:** Append the row to `DOC_TOUCH_LOG.md`. Do not close the task without it.

---

### Rule 12 — Do not design beyond the task boundary

The task description defines the scope. If the task is "add an empty state to the Publish page," deliver exactly that — not a new empty state system for all 13 pages, not a refactor of the table layout, not a new chip style.

This is not a courtesy rule. Scope creep in AI-generated UI changes is the primary source of regression risk in this project, because a change that touches more than it intends to is harder to smoke-test and harder to review.

**Verify:**
```powershell
# Check which files were modified.
git diff --name-only
# Every file listed must be directly required by the task description.
# If a file appears that was not part of the stated task, explain the reason in the DOC_TOUCH_LOG row.
# If there is no explanation, revert the unrelated change.
```

**Fail means:** Revert changes to files outside the task boundary, or document explicitly why each out-of-scope file was necessary.

---

## See Also

- `TAURI_WEBVIEW_PARITY_MATRIX.md` — historical feature parity tracking between the removed legacy desktop shell and WebView
- `WEBVIEW_DOM_ID_INVENTORY.md` — all DOM ids in use
- `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` — all `window.*` exports
- `API_ROUTE_INVENTORY.md` — all backend routes (read and command)
- `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` — which smokes prove mutation boundaries
- `OPEN_WORK_CHECKLIST.md` — current open design and safety work
- `DOCS_INDEX.md` — full doc index

**Source:** All visual principles in this document are adapted from *Refactoring UI* by Adam Wathan & Steve Schoger, applied to the MediaPipeline V5 operator context.
